from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.services.supabase_client import get_supabase
from app.utils.admin_auth import require_admin_access

bp = Blueprint("admin", __name__)

REQUEST_STATUSES = {"new", "reviewing", "contacted", "closed", "spam"}
WATCHLIST_STATUSES = {"active", "paused", "unsubscribed", "closed", "spam"}
PROFILE_STATUSES = {"new", "reviewing", "contacted", "active", "closed", "spam"}
REPORT_STATUSES = {"generated", "paid", "delivered", "stale", "refreshed", "archived"}


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


@bp.get("/readiness-checks")
@require_admin_access
def readiness_checks():
    tool_slug = (request.args.get("tool_slug") or "").strip()
    risk_level = (request.args.get("risk_level") or "").strip()
    readiness_status = (request.args.get("readiness_status") or "").strip()
    limit = min(max(int(request.args.get("limit") or 50), 1), 100)

    try:
        query = (
            get_supabase()
            .table("relocation_readiness_check_runs")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
        )
        if tool_slug:
            query = query.eq("tool_slug", tool_slug)
        if risk_level:
            query = query.eq("risk_level", risk_level)
        if readiness_status:
            query = query.eq("readiness_status", readiness_status)
        response = query.execute()
        return jsonify({"ok": True, "readiness_checks": response.data or []})
    except Exception as exc:
        return jsonify({"ok": False, "error": "readiness_checks_unavailable", "details": str(exc)}), 503


@bp.get("/generated-reports")
@require_admin_access
def generated_reports():
    status = (request.args.get("status") or "").strip()
    risk_level = (request.args.get("risk_level") or "").strip()
    report_ref = (request.args.get("report_ref") or "").strip()
    limit = min(max(int(request.args.get("limit") or 50), 1), 100)

    try:
        query = (
            get_supabase()
            .table("relocation_generated_reports")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
        )
        if status:
            query = query.eq("status", status)
        if risk_level:
            query = query.eq("risk_level", risk_level)
        if report_ref:
            query = query.ilike("report_ref", f"%{report_ref}%")
        response = query.execute()
        return jsonify({"ok": True, "generated_reports": response.data or []})
    except Exception as exc:
        return jsonify({"ok": False, "error": "generated_reports_unavailable", "details": str(exc)}), 503


@bp.patch("/generated-reports/<report_id>")
@require_admin_access
def update_generated_report(report_id: str):
    payload = request.get_json(silent=True) or {}
    status = (payload.get("status") or "").strip()

    if status not in REPORT_STATUSES:
        return jsonify({"ok": False, "error": "invalid_status", "allowed_statuses": sorted(REPORT_STATUSES)}), 400

    try:
        response = (
            get_supabase()
            .table("relocation_generated_reports")
            .update({"status": status})
            .eq("id", report_id)
            .execute()
        )
        updated = (response.data or [None])[0]
        if not updated:
            return jsonify({"ok": False, "error": "generated_report_not_found"}), 404
        return jsonify({"ok": True, "generated_report": updated})
    except Exception as exc:
        return jsonify({"ok": False, "error": "generated_report_update_failed", "details": str(exc)}), 500


@bp.get("/watchlist-subscriptions")
@require_admin_access
def watchlist_subscriptions():
    status = (request.args.get("status") or "").strip()
    watch_type = (request.args.get("watch_type") or "").strip()
    preferred_channel = (request.args.get("preferred_channel") or "").strip()
    limit = min(max(int(request.args.get("limit") or 50), 1), 100)

    try:
        query = (
            get_supabase()
            .table("relocation_watchlist_subscriptions")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
        )
        if status:
            query = query.eq("status", status)
        if watch_type:
            query = query.eq("watch_type", watch_type)
        if preferred_channel:
            query = query.eq("preferred_channel", preferred_channel)
        response = query.execute()
        return jsonify({"ok": True, "watchlist_subscriptions": response.data or []})
    except Exception as exc:
        return jsonify({"ok": False, "error": "watchlist_subscriptions_unavailable", "details": str(exc)}), 503


@bp.patch("/watchlist-subscriptions/<subscription_id>")
@require_admin_access
def update_watchlist_subscription(subscription_id: str):
    payload = request.get_json(silent=True) or {}
    status = (payload.get("status") or "").strip()

    if status not in WATCHLIST_STATUSES:
        return jsonify({"ok": False, "error": "invalid_status", "allowed_statuses": sorted(WATCHLIST_STATUSES)}), 400

    try:
        response = (
            get_supabase()
            .table("relocation_watchlist_subscriptions")
            .update({"status": status})
            .eq("id", subscription_id)
            .execute()
        )
        updated = (response.data or [None])[0]
        if not updated:
            return jsonify({"ok": False, "error": "watchlist_subscription_not_found"}), 404
        return jsonify({"ok": True, "watchlist_subscription": updated})
    except Exception as exc:
        return jsonify({"ok": False, "error": "watchlist_subscription_update_failed", "details": str(exc)}), 500


@bp.get("/user-profiles")
@require_admin_access
def user_profiles():
    status = (request.args.get("status") or "").strip()
    main_goal = (request.args.get("main_goal") or "").strip()
    target_country = (request.args.get("target_country") or "").strip()
    limit = min(max(int(request.args.get("limit") or 50), 1), 100)

    try:
        query = (
            get_supabase()
            .table("relocation_user_profiles")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
        )
        if status:
            query = query.eq("status", status)
        if main_goal:
            query = query.eq("main_goal", main_goal)
        if target_country:
            query = query.ilike("target_country", target_country)
        response = query.execute()
        return jsonify({"ok": True, "user_profiles": response.data or []})
    except Exception as exc:
        return jsonify({"ok": False, "error": "user_profiles_unavailable", "details": str(exc)}), 503


@bp.patch("/user-profiles/<profile_id>")
@require_admin_access
def update_user_profile(profile_id: str):
    payload = request.get_json(silent=True) or {}
    status = (payload.get("status") or "").strip()

    if status not in PROFILE_STATUSES:
        return jsonify({"ok": False, "error": "invalid_status", "allowed_statuses": sorted(PROFILE_STATUSES)}), 400

    try:
        response = (
            get_supabase()
            .table("relocation_user_profiles")
            .update({"status": status})
            .eq("id", profile_id)
            .execute()
        )
        updated = (response.data or [None])[0]
        if not updated:
            return jsonify({"ok": False, "error": "user_profile_not_found"}), 404
        return jsonify({"ok": True, "user_profile": updated})
    except Exception as exc:
        return jsonify({"ok": False, "error": "user_profile_update_failed", "details": str(exc)}), 500


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
