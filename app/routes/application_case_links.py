from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from flask import Blueprint, jsonify

from app.routes import account_auth
from app.services.supabase_client import get_supabase


bp = Blueprint("application_case_links", __name__)
CONTRACT_VERSION = "b12-v1"


def _auth_email() -> Tuple[Optional[str], Optional[str]]:
    try:
        token = account_auth._extract_session_token()
        if not token:
            return None, "session_token_required"
        session, error = account_auth._load_active_session(token)
        if not session:
            return None, error or "invalid_session"
        email = str(session.get("email") or "").strip().lower()
        return (email or None), (None if email else "session_email_missing")
    except Exception:
        return None, "session_validation_failed"


def _rows(table: str, email: str, limit: int = 100) -> List[Dict[str, Any]]:
    response = (
        get_supabase()
        .table(table)
        .select("*")
        .eq("email", email)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return response.data or []


@bp.get("/links")
def application_links():
    email, error = _auth_email()
    if not email:
        return jsonify({"ok": False, "error": error or "session_required"}), 401

    errors: Dict[str, str] = {}
    try:
        profile_rows = _rows("relocation_user_profiles", email, limit=50)
    except Exception:
        profile_rows = []
        errors["profiles"] = "profile_choices_unavailable"
    try:
        saved_route_rows = _rows("relocation_saved_routes", email, limit=100)
    except Exception:
        saved_route_rows = []
        errors["saved_routes"] = "saved_route_choices_unavailable"
    try:
        evidence_rows = _rows("relocation_evidence_packs", email, limit=100)
    except Exception:
        evidence_rows = []
        errors["evidence_packs"] = "evidence_pack_choices_unavailable"

    profiles = [
        {
            "id": row.get("id"),
            "label": row.get("full_name") or row.get("email") or row.get("phone") or "Saved profile",
            "status": row.get("status"),
            "target_country": row.get("target_country"),
            "route_category": row.get("route_category") or row.get("main_goal") or row.get("goal"),
        }
        for row in profile_rows
        if str(row.get("status") or "new").lower() != "closed"
    ]
    saved_routes = [
        {
            "id": row.get("id"),
            "label": row.get("saved_title") or row.get("route_name") or row.get("route_or_goal") or row.get("target_country") or "Saved route",
            "status": row.get("status"),
            "target_country": row.get("target_country"),
            "route_category": row.get("route_category"),
        }
        for row in saved_route_rows
        if str(row.get("status") or "active").lower() != "archived"
    ]
    evidence_packs = [
        {
            "id": row.get("id"),
            "label": row.get("pack_ref") or "Evidence pack",
            "status": row.get("status"),
            "risk_level": row.get("risk_level"),
            "completeness_score": row.get("completeness_score"),
            "target_country": row.get("target_country"),
            "route_category": row.get("route_category"),
            "application_stage": row.get("application_stage"),
        }
        for row in evidence_rows
        if str(row.get("status") or "draft").lower() != "archived"
    ]

    return jsonify(
        {
            "ok": True,
            "contract_version": CONTRACT_VERSION,
            "account_email": email,
            "profiles": profiles,
            "saved_routes": saved_routes,
            "evidence_packs": evidence_packs,
            "errors": errors,
            "privacy_note": "Only account-owned identifiers and short labels are returned. Raw documents and sensitive reference values are not exposed.",
        }
    )
