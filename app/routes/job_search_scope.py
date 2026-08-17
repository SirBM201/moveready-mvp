from __future__ import annotations

from typing import Any, Dict, Optional

from flask import Blueprint, jsonify, request

from app.services.account_identity import get_verified_session_email
from app.services.job_scope import (
    JOB_PROFILE_COLUMNS,
    profile_scope_contract,
    profile_scope_update,
)
from app.services.supabase_client import get_supabase


bp = Blueprint("job_search_scope", __name__)


def _load_profile(email: str) -> Optional[Dict[str, Any]]:
    response = (
        get_supabase()
        .table("relocation_job_search_profiles")
        .select(JOB_PROFILE_COLUMNS)
        .eq("email", email)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    return rows[0] if rows else None


@bp.patch("/profile/search-scope")
def update_search_scope():
    email = get_verified_session_email()
    if not email:
        return jsonify({"ok": False, "error": "verified_session_required"}), 401

    payload = request.get_json(silent=True)
    payload = payload if isinstance(payload, dict) else {}
    try:
        existing = _load_profile(email)
        if not existing:
            return jsonify({
                "ok": False,
                "error": "job_profile_required",
                "hint": "Create the main Jobs profile before saving its search scope.",
            }), 409

        row, contract, validation_error = profile_scope_update(payload, existing)
        if validation_error:
            return jsonify({
                "ok": False,
                "error": validation_error,
                "search_contract": contract,
            }), 400
        if not row:
            return jsonify({
                "ok": False,
                "error": "no_supported_scope_fields_supplied",
            }), 400

        response = (
            get_supabase()
            .table("relocation_job_search_profiles")
            .update(row)
            .eq("email", email)
            .execute()
        )
        profile = (response.data or [None])[0] or {**existing, **row}
        return jsonify({
            "ok": True,
            "profile": profile,
            "search_contract": profile_scope_contract(profile),
        })
    except Exception:
        return jsonify({
            "ok": False,
            "error": "career_search_scope_schema_unavailable",
            "hint": "Apply Supabase migration 034_career_search_scope_and_viability.sql, refresh the schema, and retry.",
        }), 503
