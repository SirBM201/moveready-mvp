from __future__ import annotations

from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

from app.services.account_identity import get_verified_session_email
from app.services.supabase_client import get_supabase

bp = Blueprint("job_search_scope", __name__)
SEARCH_SCOPES = {"local", "international", "both"}


def _text(value: Any, limit: int = 120) -> Optional[str]:
    cleaned = str(value or "").strip()
    return cleaned[:limit] or None


def _countries(value: Any) -> List[str]:
    values = value if isinstance(value, list) else str(value or "").split(",")
    result: List[str] = []
    seen = set()
    for item in values:
        cleaned = _text(item, 100)
        key = str(cleaned or "").casefold()
        if cleaned and key not in seen:
            seen.add(key)
            result.append(cleaned)
        if len(result) >= 30:
            break
    return result


@bp.patch("/profile/search-scope")
def update_search_scope():
    email = get_verified_session_email()
    if not email:
        return jsonify({"ok": False, "error": "verified_session_required"}), 401

    payload = request.get_json(silent=True)
    payload = payload if isinstance(payload, dict) else {}
    scope = _text(payload.get("search_scope"), 30) or "both"
    if scope not in SEARCH_SCOPES:
        return jsonify({"ok": False, "error": "invalid_search_scope"}), 400

    current_country = _text(payload.get("current_country"), 100)
    if not current_country:
        return jsonify({"ok": False, "error": "current_country_required"}), 400

    row: Dict[str, Any] = {
        "email": email,
        "search_scope": scope,
        "current_country": current_country,
        "work_authorized_countries": _countries(payload.get("work_authorized_countries")),
    }
    try:
        response = (
            get_supabase()
            .table("relocation_job_search_profiles")
            .upsert(row, on_conflict="email")
            .execute()
        )
        profile = (response.data or [None])[0]
        return jsonify({"ok": True, "profile": profile})
    except Exception:
        return jsonify({
            "ok": False,
            "error": "career_search_scope_schema_unavailable",
            "hint": "Apply Supabase migration 034, refresh the schema, and retry.",
        }), 503
