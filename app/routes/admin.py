from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.services.supabase_client import get_supabase
from app.utils.admin_auth import require_admin_access

bp = Blueprint("admin", __name__)

REQUEST_STATUSES = {"new", "reviewing", "contacted", "closed", "spam"}


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


@bp.get("/service-requests")
@require_admin_access
def service_requests():
    status = (request.args.get("status") or "").strip()
    service_slug = (request.args.get("service_slug") or "").strip()
    limit = min(max(int(request.args.get("limit") or 50), 1), 100)

    try:
        query = (
            get_supabase()
            .table("relocation_service_interest_requests")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
        )
        if status:
            query = query.eq("status", status)
        if service_slug:
            query = query.eq("service_slug", service_slug)
        response = query.execute()
        return jsonify({"ok": True, "service_requests": response.data or []})
    except Exception as exc:
        return jsonify({"ok": False, "error": "service_requests_unavailable", "details": str(exc)}), 503


@bp.patch("/service-requests/<request_id>")
@require_admin_access
def update_service_request(request_id: str):
    payload = request.get_json(silent=True) or {}
    status = (payload.get("status") or "").strip()

    if status not in REQUEST_STATUSES:
        return jsonify({"ok": False, "error": "invalid_status", "allowed_statuses": sorted(REQUEST_STATUSES)}), 400

    row = {"status": status}
    try:
        response = (
            get_supabase()
            .table("relocation_service_interest_requests")
            .update(row)
            .eq("id", request_id)
            .execute()
        )
        updated = (response.data or [None])[0]
        if not updated:
            return jsonify({"ok": False, "error": "service_request_not_found"}), 404
        return jsonify({"ok": True, "service_request": updated})
    except Exception as exc:
        return jsonify({"ok": False, "error": "service_request_update_failed", "details": str(exc)}), 500


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
