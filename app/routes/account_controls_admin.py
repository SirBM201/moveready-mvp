from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from flask import Blueprint, jsonify, request

from app.services.supabase_client import get_supabase
from app.utils.admin_auth import require_admin_access


bp = Blueprint("account_controls_admin", __name__)

ALLOWED_STATUSES = {
    "received",
    "identity_verification_required",
    "reviewing",
    "in_progress",
    "completed",
    "rejected",
    "cancelled",
}
ALLOWED_PRIORITIES = {"low", "normal", "high", "urgent"}


def _text(value: Any, limit: int = 1000):
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned[:limit] if cleaned else None


def _limit(value: Any, default: int = 100, maximum: int = 300) -> int:
    try:
        return max(1, min(int(value or default), maximum))
    except Exception:
        return default


def _public(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row.get("id"),
        "request_ref": row.get("request_ref"),
        "email": row.get("email"),
        "request_type": row.get("request_type"),
        "status": row.get("status"),
        "priority": row.get("priority"),
        "request_summary": row.get("request_summary"),
        "requested_scope": row.get("requested_scope"),
        "user_confirmation": row.get("user_confirmation"),
        "identity_reverification_required": row.get("identity_reverification_required"),
        "administrator_note": row.get("administrator_note"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "completed_at": row.get("completed_at"),
        "metadata": row.get("metadata") or {},
    }


@bp.get("/privacy-requests")
@require_admin_access
def list_requests():
    limit = _limit(request.args.get("limit"))
    status = _text(request.args.get("status"), 80)
    request_type = _text(request.args.get("request_type"), 80)
    email = _text(request.args.get("email"), 255)
    try:
        query = (
            get_supabase()
            .table("relocation_privacy_requests")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
        )
        if status:
            query = query.eq("status", status)
        if request_type:
            query = query.eq("request_type", request_type)
        if email:
            query = query.eq("email", email.lower())
        response = query.execute()
        rows = [_public(row) for row in (response.data or [])]
        counts: Dict[str, int] = {}
        for row in rows:
            key = str(row.get("status") or "unknown")
            counts[key] = counts.get(key, 0) + 1
        return jsonify({
            "ok": True,
            "requests": rows,
            "count": len(rows),
            "counts_by_status": counts,
            "safety_note": "A request record does not authorize automatic deletion. Verify identity, requested scope, applicable retention duties, provider-held copies, backups, billing records, disputes, and completion evidence before closing it.",
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": "privacy_request_queue_unavailable", "details": str(exc)[:1000]}), 503


@bp.patch("/privacy-requests/<request_id>")
@require_admin_access
def update_request(request_id: str):
    payload = request.get_json(silent=True) or {}
    status = _text(payload.get("status"), 80)
    priority = _text(payload.get("priority"), 40)
    note = _text(payload.get("administrator_note"), 3000)
    identity_reverified = bool(payload.get("identity_reverified"))

    if status and status not in ALLOWED_STATUSES:
        return jsonify({"ok": False, "error": "invalid_privacy_request_status"}), 400
    if priority and priority not in ALLOWED_PRIORITIES:
        return jsonify({"ok": False, "error": "invalid_privacy_request_priority"}), 400

    try:
        response = (
            get_supabase()
            .table("relocation_privacy_requests")
            .select("*")
            .eq("id", request_id)
            .limit(1)
            .execute()
        )
        current = (response.data or [None])[0]
        if not current:
            return jsonify({"ok": False, "error": "privacy_request_not_found"}), 404

        destructive = current.get("request_type") in {"account_deletion", "consent_withdrawal"}
        if destructive and status in {"in_progress", "completed"} and not identity_reverified:
            return jsonify({"ok": False, "error": "identity_reverification_required_for_destructive_request"}), 409
        if status == "completed" and not note:
            return jsonify({"ok": False, "error": "completion_note_required"}), 400

        update: Dict[str, Any] = {}
        if status:
            update["status"] = status
        if priority:
            update["priority"] = priority
        if note is not None:
            update["administrator_note"] = note
        if identity_reverified:
            metadata = current.get("metadata") if isinstance(current.get("metadata"), dict) else {}
            update["metadata"] = {
                **metadata,
                "identity_reverified": True,
                "identity_reverified_at": datetime.now(timezone.utc).isoformat(),
            }
        if status == "completed":
            update["completed_at"] = datetime.now(timezone.utc).isoformat()

        if not update:
            return jsonify({"ok": False, "error": "at_least_one_update_required"}), 400

        stored_response = (
            get_supabase()
            .table("relocation_privacy_requests")
            .update(update)
            .eq("id", request_id)
            .execute()
        )
        stored = (stored_response.data or [None])[0]
        return jsonify({
            "ok": True,
            "request": _public(stored or {**current, **update}),
            "automatic_data_deletion_performed": False,
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": "privacy_request_update_failed", "details": str(exc)[:1000]}), 503
