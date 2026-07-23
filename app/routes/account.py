from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from flask import Blueprint, jsonify

from app.routes import account_auth
from app.routes.reports import _public_report
from app.services.supabase_client import get_supabase


bp = Blueprint("account", __name__)


JOURNEY_TOOL_SLUGS: Set[str] = {
    "legalization_check",
    "family_plan",
    "appointment_plan",
    "settlement_plan",
}



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



def _profile_status_priority(row: Dict[str, Any]) -> int:
    """Put the backend active profile first while preserving newest-first order."""
    status = str(row.get("status") or "new").lower()
    return 0 if status == "active" else 1



def _profiles_for_email(email: str, limit: int = 5) -> Dict[str, Any]:
    try:
        rows = _select_for_email("relocation_user_profiles", email, limit=50)
        visible_rows = [row for row in rows if str(row.get("status") or "new").lower() != "closed"]
        visible_rows.sort(key=_profile_status_priority)
        return {"ok": True, "rows": visible_rows[:limit], "count": len(visible_rows)}
    except Exception as exc:
        return {"ok": False, "rows": [], "count": 0, "error": str(exc)}



def _report_matches_email(row: Dict[str, Any], email: str) -> bool:
    lookup = email.lower()
    direct_email = str(row.get("email") or "").strip().lower()
    if direct_email and direct_email == lookup:
        return True
    payload = row.get("input_payload") or {}
    if str(payload.get("email") or "").strip().lower() == lookup:
        return True
    report_payload = row.get("report_payload") or {}
    summary = report_payload.get("input_summary") or {}
    return str(summary.get("email") or "").strip().lower() == lookup



def _dedupe_reports(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out: List[Dict[str, Any]] = []
    for row in rows:
        key = row.get("id") or row.get("report_ref")
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out



def _reports_for_email(email: str, limit: int = 10) -> Dict[str, Any]:
    try:
        rows: List[Dict[str, Any]] = []
        try:
            direct_response = (
                get_supabase()
                .table("relocation_generated_reports")
                .select("*")
                .eq("email", email)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            rows.extend(direct_response.data or [])
        except Exception:
            pass

        scan_response = (
            get_supabase()
            .table("relocation_generated_reports")
            .select("*")
            .order("created_at", desc=True)
            .limit(100)
            .execute()
        )
        for row in scan_response.data or []:
            if _report_matches_email(row, email):
                rows.append(row)

        rows = _dedupe_reports(rows)[:limit]
        return {"ok": True, "rows": [_public_report(row) for row in rows], "count": len(rows)}
    except Exception as exc:
        return {"ok": False, "rows": [], "count": 0, "error": str(exc)}



def _readiness_matches_email(row: Dict[str, Any], email: str) -> bool:
    lookup = email.lower()
    payload = row.get("input_payload") if isinstance(row.get("input_payload"), dict) else {}
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    candidates = [
        row.get("email"),
        payload.get("email"),
        metadata.get("verified_session_email"),
    ]
    return any(str(value or "").strip().lower() == lookup for value in candidates)



def _readiness_runs_for_email(
    email: str,
    *,
    journey_only: bool,
    limit: int = 10,
) -> Dict[str, Any]:
    try:
        response = (
            get_supabase()
            .table("relocation_readiness_check_runs")
            .select("*")
            .order("created_at", desc=True)
            .limit(150)
            .execute()
        )
        rows: List[Dict[str, Any]] = []
        for row in response.data or []:
            tool_slug = str(row.get("tool_slug") or "")
            is_journey = tool_slug in JOURNEY_TOOL_SLUGS
            if journey_only != is_journey:
                continue
            if not _readiness_matches_email(row, email):
                continue
            rows.append(row)
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

    profiles = _profiles_for_email(email, limit=5)
    saved_routes = _safe_rows("relocation_saved_routes", email, status="active", limit=10)
    watchlist = _safe_rows("relocation_watchlist_subscriptions", email, status="active", limit=10)
    timeline = _safe_rows("relocation_timeline_events", email, limit=10)
    service_requests = _safe_rows("relocation_service_interest_requests", email, limit=10)
    reports = _reports_for_email(email, limit=10)
    journey_plans = _readiness_runs_for_email(email, journey_only=True, limit=10)
    readiness_checks = _readiness_runs_for_email(email, journey_only=False, limit=10)

    sections = {
        "profiles": profiles,
        "saved_routes": saved_routes,
        "watchlist": watchlist,
        "timeline": timeline,
        "reports": reports,
        "service_requests": service_requests,
        "journey_plans": journey_plans,
        "readiness_checks": readiness_checks,
    }

    latest_profile = _first(profiles.get("rows") or [])
    return jsonify(
        {
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
                "Choose the profile you want to use now.",
                "Run route checker with the active profile.",
                "Generate a readiness report from the route checker.",
                "Use Journey Planner for documents, family, appointments, and settlement.",
                "Save at least one serious route or country option.",
                "Create opt-in watchlist alerts for deadline or source changes.",
            ],
        }
    )
