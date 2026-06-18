from __future__ import annotations

from typing import Any, Dict, Optional

from flask import Blueprint, jsonify, request

from app.services.supabase_client import get_supabase

bp = Blueprint("profiles", __name__)

GOALS = {"study", "scholarship", "work", "startup", "business", "digital_nomad", "family", "visit", "opportunity", "relocation"}
CHANNELS = {"email", "whatsapp", "telegram", "phone"}
STATUSES = {"new", "reviewing", "contacted", "active", "closed", "spam"}


def _clean_text(value: Any, limit: int = 500) -> Optional[str]:
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    return cleaned[:limit]


def _clean_number(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clean_int(value: Any) -> Optional[int]:
    number = _clean_number(value)
    if number is None:
        return None
    return int(number)


def _profile_snapshot(payload: Dict[str, Any]) -> Dict[str, Any]:
    funds = _clean_number(payload.get("available_funds_amount")) or 0
    timeline = _clean_int(payload.get("timeline_months")) or 0
    family_count = _clean_int(payload.get("family_members_count")) or 0
    has_refusal = bool(payload.get("has_previous_refusal"))

    readiness_points = 0
    if payload.get("target_country"):
        readiness_points += 20
    if payload.get("main_goal"):
        readiness_points += 15
    if funds > 0:
        readiness_points += 20
    if timeline > 0:
        readiness_points += 10
    if payload.get("education_level") or payload.get("work_experience_years"):
        readiness_points += 10
    if payload.get("email") or payload.get("phone"):
        readiness_points += 10
    if not has_refusal:
        readiness_points += 5
    if family_count >= 0:
        readiness_points += 10

    if readiness_points >= 75:
        level = "strong_start"
    elif readiness_points >= 45:
        level = "needs_detail"
    else:
        level = "early_stage"

    return {
        "readiness_score": min(readiness_points, 100),
        "readiness_level": level,
        "risk_flags": [flag for flag, active in {
            "previous_refusal": has_refusal,
            "no_contact": not (payload.get("email") or payload.get("phone")),
            "no_funds_entered": funds <= 0,
            "timeline_missing": timeline <= 0,
            "family_budget_needed": family_count > 0,
        }.items() if active],
        "next_actions": [
            "Run route checker for the preferred country and goal.",
            "Generate a readiness report after profile details are complete.",
            "Create watchlist alerts for route changes and opening dates.",
        ],
    }


@bp.post("")
def create_profile():
    payload = request.get_json(silent=True) or {}
    email = _clean_text(payload.get("email"), 255)
    phone = _clean_text(payload.get("phone"), 80)
    main_goal = _clean_text(payload.get("main_goal"), 40) or "relocation"
    preferred_channel = _clean_text(payload.get("preferred_contact_channel"), 40) or "email"
    consent_to_contact = bool(payload.get("consent_to_contact"))

    if main_goal not in GOALS:
        return jsonify({"ok": False, "error": "invalid_main_goal", "allowed_goals": sorted(GOALS)}), 400
    if preferred_channel not in CHANNELS:
        return jsonify({"ok": False, "error": "invalid_contact_channel", "allowed_channels": sorted(CHANNELS)}), 400
    if not email and not phone:
        return jsonify({"ok": False, "error": "contact_required"}), 400
    if not consent_to_contact:
        return jsonify({"ok": False, "error": "contact_consent_required"}), 400

    row = {
        "full_name": _clean_text(payload.get("full_name"), 180),
        "email": email,
        "phone": phone,
        "current_country": _clean_text(payload.get("current_country"), 120),
        "nationality": _clean_text(payload.get("nationality"), 120),
        "residence_country": _clean_text(payload.get("residence_country"), 120),
        "target_country": _clean_text(payload.get("target_country"), 120),
        "target_city": _clean_text(payload.get("target_city"), 120),
        "main_goal": main_goal,
        "route_category": _clean_text(payload.get("route_category"), 80),
        "timeline_months": _clean_int(payload.get("timeline_months")),
        "family_members_count": _clean_int(payload.get("family_members_count")) or 0,
        "available_funds_amount": _clean_number(payload.get("available_funds_amount")),
        "available_funds_currency": _clean_text(payload.get("available_funds_currency"), 12) or "USD",
        "education_level": _clean_text(payload.get("education_level"), 120),
        "work_experience_years": _clean_number(payload.get("work_experience_years")),
        "business_stage": _clean_text(payload.get("business_stage"), 120),
        "has_previous_refusal": bool(payload.get("has_previous_refusal")),
        "preferred_contact_channel": preferred_channel,
        "consent_to_contact": consent_to_contact,
        "notes": _clean_text(payload.get("notes"), 1200),
        "source_page": _clean_text(payload.get("source_page"), 240),
        "metadata": {
            "user_agent": request.headers.get("User-Agent"),
            "remote_addr": request.headers.get("X-Forwarded-For") or request.remote_addr,
        },
    }
    row["readiness_snapshot"] = _profile_snapshot(row)

    try:
        response = get_supabase().table("relocation_user_profiles").insert(row).execute()
        stored = (response.data or [None])[0]
        return jsonify({"ok": True, "stored": True, "profile": stored})
    except Exception as exc:
        return jsonify({"ok": False, "stored": False, "error": "profile_storage_unavailable", "details": str(exc)}), 503


@bp.get("")
def get_profile():
    email = _clean_text(request.args.get("email"), 255)
    phone = _clean_text(request.args.get("phone"), 80)

    if not email and not phone:
        return jsonify({"ok": False, "error": "email_or_phone_required"}), 400

    try:
        query = (
            get_supabase()
            .table("relocation_user_profiles")
            .select("*")
            .order("created_at", desc=True)
            .limit(1)
        )
        if email:
            query = query.eq("email", email)
        if phone:
            query = query.eq("phone", phone)
        response = query.execute()
        profile = (response.data or [None])[0]
        if not profile:
            return jsonify({"ok": False, "error": "profile_not_found"}), 404
        return jsonify({"ok": True, "profile": profile})
    except Exception as exc:
        return jsonify({"ok": False, "error": "profile_lookup_unavailable", "details": str(exc)}), 503


@bp.patch("/<profile_id>")
def update_profile_status(profile_id: str):
    payload = request.get_json(silent=True) or {}
    status = _clean_text(payload.get("status"), 40)
    email = _clean_text(payload.get("email"), 255)
    phone = _clean_text(payload.get("phone"), 80)

    if status not in {"closed", "active"}:
        return jsonify({"ok": False, "error": "invalid_public_status"}), 400
    if not email and not phone:
        return jsonify({"ok": False, "error": "contact_required"}), 400

    try:
        query = get_supabase().table("relocation_user_profiles").update({"status": status}).eq("id", profile_id)
        if email:
            query = query.eq("email", email)
        if phone:
            query = query.eq("phone", phone)
        response = query.execute()
        updated = (response.data or [None])[0]
        if not updated:
            return jsonify({"ok": False, "error": "profile_not_found"}), 404
        return jsonify({"ok": True, "profile": updated})
    except Exception as exc:
        return jsonify({"ok": False, "error": "profile_update_failed", "details": str(exc)}), 500
