from __future__ import annotations

from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

from app.services.supabase_client import get_supabase

bp = Blueprint("watchlist", __name__)

ALERT_TYPES = [
    {"code": "opens", "label": "Application opens"},
    {"code": "closing_soon", "label": "Closing soon"},
    {"code": "results_open", "label": "Results/check status opens"},
    {"code": "eligibility_change", "label": "Eligibility changes"},
    {"code": "document_change", "label": "Document requirement changes"},
    {"code": "funds_change", "label": "Proof-of-funds changes"},
    {"code": "fee_change", "label": "Fee changes"},
    {"code": "review_due", "label": "Source review due"},
]

WATCH_TYPES = {"route", "opportunity", "scholarship", "country", "service"}
CHANNELS = {"email", "whatsapp", "telegram", "phone", "in_app"}
STATUSES = {"active", "paused", "unsubscribed", "closed", "spam"}


def _clean_text(value: Any, limit: int = 500) -> Optional[str]:
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    return cleaned[:limit]


def _clean_list(value: Any, allowed: Optional[set[str]] = None, limit: int = 12) -> List[str]:
    if not isinstance(value, list):
        return []
    out: List[str] = []
    for item in value:
        cleaned = _clean_text(item, 80)
        if not cleaned:
            continue
        if allowed and cleaned not in allowed:
            continue
        if cleaned not in out:
            out.append(cleaned)
        if len(out) >= limit:
            break
    return out


@bp.get("/options")
def watchlist_options():
    return jsonify({
        "ok": True,
        "watch_types": sorted(WATCH_TYPES),
        "channels": sorted(CHANNELS),
        "alert_types": ALERT_TYPES,
    })


@bp.post("/subscriptions")
def create_subscription():
    payload = request.get_json(silent=True) or {}
    watch_type = _clean_text(payload.get("watch_type"), 40) or "route"
    preferred_channel = _clean_text(payload.get("preferred_channel"), 40) or "email"
    email = _clean_text(payload.get("email"), 255)
    phone = _clean_text(payload.get("phone"), 80)
    consent_to_contact = bool(payload.get("consent_to_contact"))

    if watch_type not in WATCH_TYPES:
        return jsonify({"ok": False, "error": "invalid_watch_type", "allowed_watch_types": sorted(WATCH_TYPES)}), 400
    if preferred_channel not in CHANNELS:
        return jsonify({"ok": False, "error": "invalid_channel", "allowed_channels": sorted(CHANNELS)}), 400
    if not email and not phone:
        return jsonify({"ok": False, "error": "contact_required"}), 400
    if not consent_to_contact:
        return jsonify({"ok": False, "error": "contact_consent_required"}), 400

    alert_types = _clean_list(payload.get("alert_types"), {item["code"] for item in ALERT_TYPES})
    if not alert_types:
        alert_types = ["opens", "closing_soon", "eligibility_change"]

    row = {
        "watch_type": watch_type,
        "watch_code": _clean_text(payload.get("watch_code"), 120),
        "watch_title": _clean_text(payload.get("watch_title"), 180),
        "full_name": _clean_text(payload.get("full_name"), 180),
        "email": email,
        "phone": phone,
        "preferred_channel": preferred_channel,
        "current_country": _clean_text(payload.get("current_country"), 120),
        "target_country": _clean_text(payload.get("target_country"), 120),
        "route_or_goal": _clean_text(payload.get("route_or_goal"), 180),
        "alert_types": alert_types,
        "consent_to_contact": consent_to_contact,
        "source_page": _clean_text(payload.get("source_page"), 240),
        "metadata": {
            "user_agent": request.headers.get("User-Agent"),
            "remote_addr": request.headers.get("X-Forwarded-For") or request.remote_addr,
        },
    }

    try:
        response = get_supabase().table("relocation_watchlist_subscriptions").insert(row).execute()
        stored = (response.data or [None])[0]
        return jsonify({"ok": True, "stored": True, "subscription": stored})
    except Exception as exc:
        return jsonify({
            "ok": False,
            "stored": False,
            "error": "watchlist_storage_unavailable",
            "details": str(exc),
        }), 503


@bp.patch("/subscriptions/<subscription_id>")
def update_subscription(subscription_id: str):
    payload = request.get_json(silent=True) or {}
    status = _clean_text(payload.get("status"), 40)
    email = _clean_text(payload.get("email"), 255)
    phone = _clean_text(payload.get("phone"), 80)

    if status not in STATUSES:
        return jsonify({"ok": False, "error": "invalid_status", "allowed_statuses": sorted(STATUSES)}), 400
    if not email and not phone:
        return jsonify({"ok": False, "error": "contact_required"}), 400

    try:
        query = get_supabase().table("relocation_watchlist_subscriptions").update({"status": status}).eq("id", subscription_id)
        if email:
            query = query.eq("email", email)
        if phone:
            query = query.eq("phone", phone)
        response = query.execute()
        updated = (response.data or [None])[0]
        if not updated:
            return jsonify({"ok": False, "error": "subscription_not_found"}), 404
        return jsonify({"ok": True, "subscription": updated})
    except Exception as exc:
        return jsonify({"ok": False, "error": "watchlist_update_failed", "details": str(exc)}), 500
