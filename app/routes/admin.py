from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.services.supabase_client import get_supabase
from app.utils.admin_auth import require_admin_access

bp = Blueprint("admin", __name__)


@bp.get("/status")
@require_admin_access
def admin_status():
    return jsonify({"ok": True, "service": "MoveReady admin", "status": "protected"})


@bp.get("/review-tasks")
@require_admin_access
def review_tasks():
    try:
        response = (
            get_supabase()
            .table("relocation_admin_review_tasks")
            .select("*")
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )
        return jsonify({"ok": True, "review_tasks": response.data or []})
    except Exception as exc:
        return jsonify({"ok": False, "error": "review_tasks_unavailable", "details": str(exc)}), 503


@bp.post("/trusted-sources")
@require_admin_access
def create_trusted_source():
    payload = request.get_json(silent=True) or {}
    required = ["source_name", "source_url", "source_type"]
    missing = [key for key in required if not str(payload.get(key) or "").strip()]
    if missing:
        return jsonify({"ok": False, "error": "missing_required_fields", "fields": missing}), 400

    row = {
        "source_name": payload["source_name"].strip(),
        "source_url": payload["source_url"].strip(),
        "source_type": payload["source_type"].strip(),
        "owner_organization": payload.get("owner_organization"),
        "reliability_level": payload.get("reliability_level") or "high",
        "status": payload.get("status") or "active",
        "notes": payload.get("notes"),
    }

    try:
        response = get_supabase().table("relocation_trusted_sources").insert(row).execute()
        return jsonify({"ok": True, "source": (response.data or [None])[0]})
    except Exception as exc:
        return jsonify({"ok": False, "error": "source_create_failed", "details": str(exc)}), 500
