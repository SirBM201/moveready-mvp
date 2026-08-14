from __future__ import annotations

from flask import Blueprint, jsonify

from app.services.account_identity import get_verified_session_email
from app.services.opportunity_finder import recommend_pathways
from app.services.supabase_client import get_supabase

bp = Blueprint("opportunity_finder", __name__)


@bp.get("/recommendations")
def recommendations():
    email = get_verified_session_email()
    if not email:
        return jsonify({"ok": False, "error": "verified_session_required", "hint": "Sign in so MoveReady can use your existing relocation profile instead of creating another profile silo."}), 401
    try:
        response = (get_supabase().table("relocation_user_profiles").select("*").eq("email", email).neq("status", "closed").order("created_at", desc=True).limit(25).execute())
        profiles = response.data or []
        profiles.sort(key=lambda row: 0 if str(row.get("status") or "").lower() == "active" else 1)
        profile = (profiles or [None])[0]
    except Exception:
        profile = None
    if not profile:
        return jsonify({"ok": False, "error": "relocation_profile_required", "next_href": "/onboarding"}), 404
    try:
        target = str(profile.get("target_country") or "").strip()
        query = get_supabase().table("relocation_opportunities").select("id,opportunity_code,opportunity_name,opportunity_type,route_category,country_name,availability_status,official_url,source_confidence,last_verified_at,next_review_due_at").eq("is_public", True).limit(100)
        if target:
            query = query.eq("country_name", target)
        opportunities = query.execute().data or []
    except Exception:
        opportunities = []
    result = recommend_pathways(profile, opportunities)
    return jsonify({"ok": True, "profile_id": profile.get("id"), **result})
