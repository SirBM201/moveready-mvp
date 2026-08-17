from __future__ import annotations

from flask import Blueprint, jsonify

from app.routes import relocation_public
from app.services.account_identity import get_verified_session_email
from app.services.opportunity_finder import recommend_pathways
from app.services.supabase_client import get_supabase

bp = Blueprint("opportunity_finder", __name__)


def _route_candidates(profile):
    rows = relocation_public._route_summary_rows()
    if rows is None:
        return []

    target = str(profile.get("target_country") or "").strip().lower()
    goal = str(profile.get("main_goal") or profile.get("route_category_preference") or "").strip().lower()
    if target:
        rows = [
            row for row in rows
            if target in {str(row.get("country_code") or "").lower(), str(row.get("country_name") or "").lower()}
        ]
    rows.sort(key=lambda row: (0 if row.get("route_category") == goal else 1, str(row.get("route_name") or "")))

    details = []
    for row in rows[:8]:
        route = {
            **row,
            "relocation_countries": {
                "country_code": row.get("country_code"),
                "country_name": row.get("country_name"),
            },
            "relocation_route_versions": relocation_public._route_versions(row.get("id")),
        }
        details.append(relocation_public._route_detail(route))
    return details


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
        query = get_supabase().table("relocation_opportunities").select("id,opportunity_code,opportunity_name,opportunity_type,route_category,country_code,country_name,availability_status,official_url,summary,eligibility_summary,application_window_summary,safety_notes,source_confidence,last_verified_at,next_review_due_at").eq("is_public", True).limit(100)
        opportunities = query.execute().data or []
        if target:
            target_key = target.lower()
            opportunities = [
                item for item in opportunities
                if target_key in {
                    str(item.get("country_code") or "").strip().lower(),
                    str(item.get("country_name") or "").strip().lower(),
                }
            ]
    except Exception:
        opportunities = []
    try:
        routes = _route_candidates(profile)
    except Exception:
        routes = []
    result = recommend_pathways(profile, opportunities, routes)
    return jsonify({"ok": True, "profile_id": profile.get("id"), **result})
