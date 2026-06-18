from __future__ import annotations

from typing import Any, Optional

from flask import Blueprint, jsonify, request

from app.services.supabase_client import get_supabase

bp = Blueprint("saved_routes", __name__)

SAVE_TYPES = {"route", "opportunity", "scholarship", "country", "service"}
STATUSES = {"active", "archived", "closed", "spam"}
PUBLIC_STATUSES = {"active", "archived", "closed"}


def _clean_text(value: Any, limit: int = 500) -> Optional[str]:
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    return cleaned[:limit]


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


@bp.post("/", strict_slashes=False)
def save_route():
    payload = request.get_json(silent=True) or {}
    save_type = _clean_text(payload.get("save_type"), 40) or "route"
    saved_title = _clean_text(payload.get("saved_title") or payload.get("route_name") or payload.get("opportunity_title"), 180)
    email = _clean_text(payload.get("email"), 255)
    phone = _clean_text(payload.get("phone"), 80)
    consent_to_contact = _bool(payload.get("consent_to_contact"))
    notify_on_changes = _bool(payload.get("notify_on_changes"))

    if save_type not in SAVE_TYPES:
        return jsonify({"ok": False, "error": "invalid_save_type", "allowed_types": sorted(SAVE_TYPES)}), 400
    if not saved_title:
        return jsonify({"ok": False, "error": "saved_title_required"}), 400
    if not email and not phone:
        return jsonify({"ok": False, "error": "email_or_phone_required"}), 400
    if not consent_to_contact:
        return jsonify({"ok": False, "error": "contact_consent_required"}), 400

    row = {
        "save_type": save_type,
        "route_id": payload.get("route_id"),
        "route_version_id": payload.get("route_version_id"),
        "opportunity_id": payload.get("opportunity_id"),
        "country_id": payload.get("country_id"),
        "route_code": _clean_text(payload.get("route_code"), 120),
        "country_code": _clean_text(payload.get("country_code"), 20),
        "saved_title": saved_title,
        "full_name": _clean_text(payload.get("full_name"), 180),
        "email": email,
        "phone": phone,
        "current_country": _clean_text(payload.get("current_country"), 120),
        "target_country": _clean_text(payload.get("target_country"), 120),
        "main_goal": _clean_text(payload.get("main_goal"), 80),
        "route_category": _clean_text(payload.get("route_category"), 80),
        "notes": _clean_text(payload.get("notes"), 1200),
        "notify_on_changes": notify_on_changes,
        "consent_to_contact": consent_to_contact,
        "source_page": _clean_text(payload.get("source_page"), 240),
        "metadata": {
            "user_agent": request.headers.get("User-Agent"),
            "remote_addr": request.headers.get("X-Forwarded-For") or request.remote_addr,
        },
    }

    try:
        response = get_supabase().table("relocation_saved_routes").insert(row).execute()
        saved = (response.data or [None])[0]
        return jsonify({"ok": True, "saved_route": saved})
    except Exception as exc:
        return jsonify({"ok": False, "error": "saved_route_storage_unavailable", "details": str(exc)}), 503


@bp.get("/", strict_slashes=False)
def list_saved_routes():
    email = _clean_text(request.args.get("email"), 255)
    phone = _clean_text(request.args.get("phone"), 80)
    status = _clean_text(request.args.get("status"), 40) or "active"
    limit = min(max(int(request.args.get("limit") or 25), 1), 100)

    if not email and not phone:
        return jsonify({"ok": False, "error": "email_or_phone_required"}), 400
    if status not in STATUSES:
        return jsonify({"ok": False, "error": "invalid_status", "allowed_statuses": sorted(STATUSES)}), 400

    try:
        query = (
            get_supabase()
            .table("relocation_saved_routes")
            .select("*")
            .eq("status", status)
            .order("created_at", desc=True)
            .limit(limit)
        )
        if email:
            query = query.eq("email", email)
        if phone:
            query = query.eq("phone", phone)
        response = query.execute()
        return jsonify({"ok": True, "saved_routes": response.data or []})
    except Exception as exc:
        return jsonify({"ok": False, "error": "saved_routes_unavailable", "details": str(exc)}), 503


@bp.patch("/<saved_route_id>")
def update_saved_route(saved_route_id: str):
    payload = request.get_json(silent=True) or {}
    status = _clean_text(payload.get("status"), 40)
    email = _clean_text(payload.get("email"), 255)
    phone = _clean_text(payload.get("phone"), 80)

    if status not in PUBLIC_STATUSES:
        return jsonify({"ok": False, "error": "invalid_public_status", "allowed_statuses": sorted(PUBLIC_STATUSES)}), 400
    if not email and not phone:
        return jsonify({"ok": False, "error": "email_or_phone_required"}), 400

    try:
        query = get_supabase().table("relocation_saved_routes").update({"status": status}).eq("id", saved_route_id)
        if email:
            query = query.eq("email", email)
        if phone:
            query = query.eq("phone", phone)
        response = query.execute()
        saved = (response.data or [None])[0]
        if not saved:
            return jsonify({"ok": False, "error": "saved_route_not_found"}), 404
        return jsonify({"ok": True, "saved_route": saved})
    except Exception as exc:
        return jsonify({"ok": False, "error": "saved_route_update_failed", "details": str(exc)}), 500
