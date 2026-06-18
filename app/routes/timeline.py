from __future__ import annotations

from datetime import date
from typing import Any, Optional

from flask import Blueprint, jsonify, request

from app.services.supabase_client import get_supabase

bp = Blueprint("timeline", __name__)

EVENT_TYPES = {"task", "deadline", "appointment", "document", "payment", "travel", "result", "follow_up"}
PRIORITIES = {"low", "medium", "high", "critical"}
STATUSES = {"pending", "in_progress", "done", "missed", "cancelled", "archived"}
PUBLIC_STATUSES = {"pending", "in_progress", "done", "cancelled", "archived"}
CHANNELS = {"email", "whatsapp", "telegram", "phone", "in_app"}


def _clean_text(value: Any, limit: int = 500) -> Optional[str]:
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    return cleaned[:limit]


def _clean_date(value: Any) -> Optional[str]:
    cleaned = _clean_text(value, 40)
    if not cleaned:
        return None
    try:
        return date.fromisoformat(cleaned[:10]).isoformat()
    except ValueError:
        return None


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


@bp.post("/", strict_slashes=False)
def create_timeline_event():
    payload = request.get_json(silent=True) or {}
    email = _clean_text(payload.get("email"), 255)
    phone = _clean_text(payload.get("phone"), 80)
    event_type = _clean_text(payload.get("event_type"), 40) or "task"
    priority = _clean_text(payload.get("priority"), 40) or "medium"
    preferred_channel = _clean_text(payload.get("preferred_channel"), 40) or "email"
    event_title = _clean_text(payload.get("event_title"), 180)
    consent_to_contact = _bool(payload.get("consent_to_contact"))

    if not email and not phone:
        return jsonify({"ok": False, "error": "email_or_phone_required"}), 400
    if not event_title:
        return jsonify({"ok": False, "error": "event_title_required"}), 400
    if event_type not in EVENT_TYPES:
        return jsonify({"ok": False, "error": "invalid_event_type", "allowed_types": sorted(EVENT_TYPES)}), 400
    if priority not in PRIORITIES:
        return jsonify({"ok": False, "error": "invalid_priority", "allowed_priorities": sorted(PRIORITIES)}), 400
    if preferred_channel not in CHANNELS:
        return jsonify({"ok": False, "error": "invalid_channel", "allowed_channels": sorted(CHANNELS)}), 400
    if not consent_to_contact:
        return jsonify({"ok": False, "error": "contact_consent_required"}), 400

    row = {
        "full_name": _clean_text(payload.get("full_name"), 180),
        "email": email,
        "phone": phone,
        "current_country": _clean_text(payload.get("current_country"), 120),
        "target_country": _clean_text(payload.get("target_country"), 120),
        "route_or_goal": _clean_text(payload.get("route_or_goal"), 180),
        "route_category": _clean_text(payload.get("route_category"), 80),
        "event_type": event_type,
        "event_title": event_title,
        "event_notes": _clean_text(payload.get("event_notes"), 1200),
        "due_date": _clean_date(payload.get("due_date")),
        "reminder_date": _clean_date(payload.get("reminder_date")),
        "priority": priority,
        "preferred_channel": preferred_channel,
        "consent_to_contact": consent_to_contact,
        "source_page": _clean_text(payload.get("source_page"), 240),
        "metadata": {
            "user_agent": request.headers.get("User-Agent"),
            "remote_addr": request.headers.get("X-Forwarded-For") or request.remote_addr,
        },
    }

    try:
        response = get_supabase().table("relocation_timeline_events").insert(row).execute()
        event = (response.data or [None])[0]
        return jsonify({"ok": True, "timeline_event": event})
    except Exception as exc:
        return jsonify({"ok": False, "error": "timeline_storage_unavailable", "details": str(exc)}), 503


@bp.get("/", strict_slashes=False)
def list_timeline_events():
    email = _clean_text(request.args.get("email"), 255)
    phone = _clean_text(request.args.get("phone"), 80)
    status = _clean_text(request.args.get("status"), 40)
    limit = min(max(int(request.args.get("limit") or 50), 1), 100)

    if not email and not phone:
        return jsonify({"ok": False, "error": "email_or_phone_required"}), 400
    if status and status not in STATUSES:
        return jsonify({"ok": False, "error": "invalid_status", "allowed_statuses": sorted(STATUSES)}), 400

    try:
        query = (
            get_supabase()
            .table("relocation_timeline_events")
            .select("*")
            .order("due_date", desc=False)
            .order("created_at", desc=True)
            .limit(limit)
        )
        if email:
            query = query.eq("email", email)
        if phone:
            query = query.eq("phone", phone)
        if status:
            query = query.eq("status", status)
        else:
            query = query.neq("status", "archived")
        response = query.execute()
        return jsonify({"ok": True, "timeline_events": response.data or []})
    except Exception as exc:
        return jsonify({"ok": False, "error": "timeline_unavailable", "details": str(exc)}), 503


@bp.patch("/<event_id>")
def update_timeline_event(event_id: str):
    payload = request.get_json(silent=True) or {}
    status = _clean_text(payload.get("status"), 40)
    email = _clean_text(payload.get("email"), 255)
    phone = _clean_text(payload.get("phone"), 80)

    if status not in PUBLIC_STATUSES:
        return jsonify({"ok": False, "error": "invalid_public_status", "allowed_statuses": sorted(PUBLIC_STATUSES)}), 400
    if not email and not phone:
        return jsonify({"ok": False, "error": "email_or_phone_required"}), 400

    try:
        query = get_supabase().table("relocation_timeline_events").update({"status": status}).eq("id", event_id)
        if email:
            query = query.eq("email", email)
        if phone:
            query = query.eq("phone", phone)
        response = query.execute()
        event = (response.data or [None])[0]
        if not event:
            return jsonify({"ok": False, "error": "timeline_event_not_found"}), 404
        return jsonify({"ok": True, "timeline_event": event})
    except Exception as exc:
        return jsonify({"ok": False, "error": "timeline_update_failed", "details": str(exc)}), 500
