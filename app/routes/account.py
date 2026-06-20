from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from flask import Blueprint, jsonify

from app.routes import account_auth
from app.routes.reports import _public_report
from app.services.supabase_client import get_supabase

bp = Blueprint("account", __name__)


def _auth_session() -> Tuple[Optional[Dict[str, Any]], Optional[Any]]:
    token = account_auth._auth._extract_session_token()
    if not token:
        return None, (jsonify({"ok": False, "error": "session_token_required"}), 401)
    session, error = account_auth._auth._load_active_session(token)
    if not session:
        return None, (jsonify({"ok": False, "error": error or "invalid_session"}), 401)
    return session, None


def _select_for_email(table: str, email: str, *, status: Optional[str] = None, limit: int = 25) -> List[Dict[str, Any]]:
    query = (
        get_supabase()
        .table(table)
        .select("*")
        .eq("email", email)
        .order("created_at", desc=True)
        .limit(limit)
    )
    if status:
        query = query.eq("status", status)
    response = query.execute()
    return response.data or []


def _safe_rows(table: str, email: str, *, status: Optional[str] = None, limit: int = 25) -> Dict[str, Any]:
    try:
        rows = _select_for_email(table, email, status=status, limit=limit)
        return {"ok": True, "rows": rows, "count": len(rows)}
    except Exception as exc:
        return {"ok": False, "rows": [], "count": 0, "error": str(exc)}


def _report_matches_email(row: Dict[str, Any], email: str) -> bool:
    direct_email = str(row.get("email") or "").strip().lower()
    if direct_email and direct_email == email.lower():
        return True
    payload = row.get("input_payload") or {}
    return str(payload.get("email") or "").strip().lower() == email.lower()


def _reports_for_email(email: str, limit: int = 10) -> Dict[str, Any]:
    try:
        try:
            response = (
                get_supabase()
                .table("relocation_generated_reports")
                .select("*")
                .eq("email", email)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            rows = [_public_report(row) for row in response.data or []]
            return {"ok": True, "rows": rows, "count": len(rows)}
        except Exception:
            response = (
                get_supabase()
                .table("relocation_generated_reports")
                .select("*")
                .order("created_at", desc=True)
                .limit(100)
                .execute()
            )
            rows = []
            for row in response.data or []:
                if _report_matches_email(row, email):
                    rows.append(_public_report(row))
                if len(rows) >= limit:
                    break
            return {"ok": True, "rows": rows, "count": len(rows)}
    except Exception as exc:
        return {"ok": False, "rows": [], "count": 0, "error": str(exc)}


def _first(rows: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    return rows[0] if rows else None


def _summary_counts(sections: Dict[str, Dict[str, Any]]) -> Dict[str, int]:
    return {name: int(section.get("count") or 0) for name, section in sections.items()}


@bp.get("/health")
def health():
    return jsonify({"ok": True, "service": "MoveReady authenticated account"})


@bp.get("/summary")
def account_summary():
    session, error_response = _auth_session()
    if error_response:
        return error_response

    email = str(session.get("email") or "").strip().lower()
    if not email:
        return jsonify({"ok": False, "error": "session_email_missing"}), 401

    profiles = _safe_rows("relocation_user_profiles", email, limit=5)
    saved_routes = _safe_rows("relocation_saved_routes", email, status="active", limit=10)
    watchlist = _safe_rows("relocation_watchlist_subscriptions", email, status="active", limit=10)
    timeline = _safe_rows("relocation_timeline_events", email, limit=10)
    service_requests = _safe_rows("relocation_service_interest_requests", email, limit=10)
    reports = _reports_for_email(email, limit=10)

    sections = {
        "profiles": profiles,
        "saved_routes": saved_routes,
        "watchlist": watchlist,
        "timeline": timeline,
        "reports": reports,
        "service_requests": service_requests,
    }

    latest_profile = _first(profiles.get("rows") or [])
    return jsonify({
        "ok": True,
        "session": {
            "email": email,
            "status": session.get("status"),
            "expires_at": session.get("expires_at"),
        },
        "counts": _summary_counts(sections),
        "latest_profile": latest_profile,
        "sections": sections,
        "next_actions": [
            "Create or update relocation profile.",
            "Save at least one serious route or country option.",
            "Generate a readiness report from the route checker.",
            "Create opt-in watchlist alerts for deadline or source changes.",
            "Add timeline events for documents, appointments, and reminders.",
        ],
    })
