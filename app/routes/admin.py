from __future__ import annotations

from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request

from app.services.supabase_client import get_supabase
from app.utils.admin_auth import require_admin_access

bp = Blueprint("admin", __name__)

REQUEST_STATUSES = {"new", "reviewing", "contacted", "closed", "spam"}
WATCHLIST_STATUSES = {"active", "paused", "unsubscribed", "closed", "spam"}
PROFILE_STATUSES = {"new", "reviewing", "contacted", "active", "closed", "spam"}
REPORT_STATUSES = {"generated", "paid", "delivered", "stale", "refreshed", "archived"}
SAVED_ROUTE_STATUSES = {"active", "archived", "closed", "spam"}
TIMELINE_EVENT_STATUSES = {"pending", "in_progress", "done", "missed", "cancelled", "archived"}
TIMELINE_PRIORITIES = {"low", "medium", "high", "critical"}
PARTNER_APPLICATION_STATUSES = {"new", "screening", "approved", "rejected", "waitlist", "suspended", "spam"}
PARTNER_PROVIDER_TYPES = {"courier", "insurance", "legalization", "translation", "expert_review", "admission_support", "accommodation", "airport_pickup", "settlement", "other"}
SOURCE_TYPES = {"government", "embassy", "visa_center", "university", "scholarship_body", "insurance", "courier", "news", "partner", "other"}
SOURCE_RELIABILITY_LEVELS = {"high", "medium", "low"}
SOURCE_STATUSES = {"active", "watching", "needs_review", "retired"}
REVIEW_TASK_TYPES = {"source_review", "route_review", "scholarship_review", "insurance_review", "report_review", "manual"}
REVIEW_TASK_STATUSES = {"open", "in_progress", "approved", "rejected", "dismissed"}
REVIEW_TASK_PRIORITIES = {"low", "medium", "high", "urgent"}
FINAL_REVIEW_TASK_STATUSES = {"approved", "rejected", "dismissed"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _review_due_iso(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


@bp.get("/status")
@require_admin_access
def admin_status():
    return jsonify({"ok": True, "service": "MoveReady admin", "status": "protected"})


@bp.get("/review-tasks")
@require_admin_access
def review_tasks():
    status = (request.args.get("status") or "").strip()
    task_type = (request.args.get("task_type") or "").strip()
    priority = (request.args.get("priority") or "").strip()
    limit = min(max(int(request.args.get("limit") or 50), 1), 100)

    try:
        query = (
            get_supabase()
            .table("relocation_admin_review_tasks")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
        )
        if status:
            query = query.eq("status", status)
        if task_type:
            query = query.eq("task_type", task_type)
        if priority:
            query = query.eq("priority", priority)
        response = query.execute()
        return jsonify({"ok": True, "review_tasks": response.data or []})
    except Exception as exc:
        return jsonify({"ok": False, "error": "review_tasks_unavailable", "details": str(exc)}), 503


@bp.patch("/review-tasks/<task_id>")
@require_admin_access
def update_review_task(task_id: str):
    payload = request.get_json(silent=True) or {}
    status = (payload.get("status") or "").strip()
    priority = (payload.get("priority") or "").strip()
    assigned_to = payload.get("assigned_to")
    description = payload.get("description")

    update_fields = {}
    if status:
        if status not in REVIEW_TASK_STATUSES:
            return jsonify({"ok": False, "error": "invalid_status", "allowed_statuses": sorted(REVIEW_TASK_STATUSES)}), 400
        update_fields["status"] = status
        update_fields["completed_at"] = _now_iso() if status in FINAL_REVIEW_TASK_STATUSES else None
    if priority:
        if priority not in REVIEW_TASK_PRIORITIES:
            return jsonify({"ok": False, "error": "invalid_priority", "allowed_priorities": sorted(REVIEW_TASK_PRIORITIES)}), 400
        update_fields["priority"] = priority
    if assigned_to is not None:
        update_fields["assigned_to"] = str(assigned_to).strip()[:160] or None
    if description is not None:
        update_fields["description"] = str(description).strip()[:1200] or None

    if not update_fields:
        return jsonify({"ok": False, "error": "no_update_fields"}), 400

    try:
        response = (
            get_supabase()
            .table("relocation_admin_review_tasks")
            .update(update_fields)
            .eq("id", task_id)
            .execute()
        )
        updated = (response.data or [None])[0]
        if not updated:
            return jsonify({"ok": False, "error": "review_task_not_found"}), 404
        return jsonify({"ok": True, "review_task": updated})
    except Exception as exc:
        return jsonify({"ok": False, "error": "review_task_update_failed", "details": str(exc)}), 500


@bp.get("/trusted-sources")
@require_admin_access
def trusted_sources():
    status = (request.args.get("status") or "").strip()
    source_type = (request.args.get("source_type") or "").strip()
    reliability_level = (request.args.get("reliability_level") or "").strip()
    review_due = (request.args.get("review_due") or "").strip().lower() in {"1", "true", "yes"}
    search = (request.args.get("q") or "").strip()
    limit = min(max(int(request.args.get("limit") or 75), 1), 100)

    try:
        query = (
            get_supabase()
            .table("relocation_trusted_sources")
            .select("*")
            .order("next_review_due_at", desc=False)
            .order("created_at", desc=True)
            .limit(limit)
        )
        if status:
            query = query.eq("status", status)
        if source_type:
            query = query.eq("source_type", source_type)
        if reliability_level:
            query = query.eq("reliability_level", reliability_level)
        if review_due:
            query = query.lte("next_review_due_at", _now_iso())
        if search:
            query = query.or_(f"source_name.ilike.%{search}%,owner_organization.ilike.%{search}%,source_url.ilike.%{search}%")
        response = query.execute()
        return jsonify({"ok": True, "trusted_sources": response.data or []})
    except Exception as exc:
        return jsonify({"ok": False, "error": "trusted_sources_unavailable", "details": str(exc)}), 503


@bp.patch("/trusted-sources/<source_id>")
@require_admin_access
def update_trusted_source(source_id: str):
    payload = request.get_json(silent=True) or {}
    update_fields = {}

    status = (payload.get("status") or "").strip()
    reliability_level = (payload.get("reliability_level") or "").strip()
    source_type = (payload.get("source_type") or "").strip()
    review_frequency_days = payload.get("review_frequency_days")

    if status:
        if status not in SOURCE_STATUSES:
            return jsonify({"ok": False, "error": "invalid_status", "allowed_statuses": sorted(SOURCE_STATUSES)}), 400
        update_fields["status"] = status
    if reliability_level:
        if reliability_level not in SOURCE_RELIABILITY_LEVELS:
            return jsonify({"ok": False, "error": "invalid_reliability_level", "allowed_reliability_levels": sorted(SOURCE_RELIABILITY_LEVELS)}), 400
        update_fields["reliability_level"] = reliability_level
    if source_type:
        if source_type not in SOURCE_TYPES:
            return jsonify({"ok": False, "error": "invalid_source_type", "allowed_source_types": sorted(SOURCE_TYPES)}), 400
        update_fields["source_type"] = source_type
    if review_frequency_days is not None:
        try:
            days = max(1, min(int(review_frequency_days), 365))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "invalid_review_frequency_days"}), 400
        update_fields["review_frequency_days"] = days
    else:
        days = 30

    for text_field in ("source_name", "source_url", "owner_organization", "notes"):
        if text_field in payload:
            value = str(payload.get(text_field) or "").strip()
            update_fields[text_field] = value or None

    if payload.get("mark_checked"):
        try:
            days = max(1, min(int(payload.get("review_frequency_days") or update_fields.get("review_frequency_days") or 30), 365))
        except (TypeError, ValueError):
            days = 30
        update_fields["last_checked_at"] = _now_iso()
        update_fields["next_review_due_at"] = _review_due_iso(days)

    if not update_fields:
        return jsonify({"ok": False, "error": "no_update_fields"}), 400

    try:
        response = (
            get_supabase()
            .table("relocation_trusted_sources")
            .update(update_fields)
            .eq("id", source_id)
            .execute()
        )
        updated = (response.data or [None])[0]
        if not updated:
            return jsonify({"ok": False, "error": "trusted_source_not_found"}), 404
        return jsonify({"ok": True, "trusted_source": updated})
    except Exception as exc:
        return jsonify({"ok": False, "error": "trusted_source_update_failed", "details": str(exc)}), 500


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

    try:
        response = (
            get_supabase()
            .table("relocation_service_interest_requests")
            .update({"status": status})
            .eq("id", request_id)
            .execute()
        )
        updated = (response.data or [None])[0]
        if not updated:
            return jsonify({"ok": False, "error": "service_request_not_found"}), 404
        return jsonify({"ok": True, "service_request": updated})
    except Exception as exc:
        return jsonify({"ok": False, "error": "service_request_update_failed", "details": str(exc)}), 500


@bp.get("/partner-applications")
@require_admin_access
def partner_applications():
    status = (request.args.get("status") or "").strip()
    provider_type = (request.args.get("provider_type") or "").strip()
    country = (request.args.get("country") or "").strip()
    limit = min(max(int(request.args.get("limit") or 50), 1), 100)

    try:
        query = (
            get_supabase()
            .table("relocation_partner_applications")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
        )
        if status:
            query = query.eq("status", status)
        if provider_type:
            query = query.eq("provider_type", provider_type)
        if country:
            query = query.ilike("country", country)
        response = query.execute()
        return jsonify({"ok": True, "partner_applications": response.data or []})
    except Exception as exc:
        return jsonify({"ok": False, "error": "partner_applications_unavailable", "details": str(exc)}), 503


@bp.patch("/partner-applications/<application_id>")
@require_admin_access
def update_partner_application(application_id: str):
    payload = request.get_json(silent=True) or {}
    status = (payload.get("status") or "").strip()
    internal_notes = payload.get("internal_notes")

    update_fields = {}
    if status:
        if status not in PARTNER_APPLICATION_STATUSES:
            return jsonify({"ok": False, "error": "invalid_status", "allowed_statuses": sorted(PARTNER_APPLICATION_STATUSES)}), 400
        update_fields["status"] = status
    if internal_notes is not None:
        update_fields["internal_notes"] = str(internal_notes).strip()[:1200]

    if not update_fields:
        return jsonify({"ok": False, "error": "no_update_fields"}), 400

    try:
        response = (
            get_supabase()
            .table("relocation_partner_applications")
            .update(update_fields)
            .eq("id", application_id)
            .execute()
        )
        updated = (response.data or [None])[0]
        if not updated:
            return jsonify({"ok": False, "error": "partner_application_not_found"}), 404
        return jsonify({"ok": True, "partner_application": updated})
    except Exception as exc:
        return jsonify({"ok": False, "error": "partner_application_update_failed", "details": str(exc)}), 500


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


@bp.get("/saved-routes")
@require_admin_access
def saved_routes():
    status = (request.args.get("status") or "").strip()
    save_type = (request.args.get("save_type") or "").strip()
    target_country = (request.args.get("target_country") or "").strip()
    limit = min(max(int(request.args.get("limit") or 50), 1), 100)

    try:
        query = (
            get_supabase()
            .table("relocation_saved_routes")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
        )
        if status:
            query = query.eq("status", status)
        if save_type:
            query = query.eq("save_type", save_type)
        if target_country:
            query = query.ilike("target_country", target_country)
        response = query.execute()
        return jsonify({"ok": True, "saved_routes": response.data or []})
    except Exception as exc:
        return jsonify({"ok": False, "error": "saved_routes_unavailable", "details": str(exc)}), 503


@bp.patch("/saved-routes/<saved_route_id>")
@require_admin_access
def update_saved_route(saved_route_id: str):
    payload = request.get_json(silent=True) or {}
    status = (payload.get("status") or "").strip()

    if status not in SAVED_ROUTE_STATUSES:
        return jsonify({"ok": False, "error": "invalid_status", "allowed_statuses": sorted(SAVED_ROUTE_STATUSES)}), 400

    try:
        response = (
            get_supabase()
            .table("relocation_saved_routes")
            .update({"status": status})
            .eq("id", saved_route_id)
            .execute()
        )
        updated = (response.data or [None])[0]
        if not updated:
            return jsonify({"ok": False, "error": "saved_route_not_found"}), 404
        return jsonify({"ok": True, "saved_route": updated})
    except Exception as exc:
        return jsonify({"ok": False, "error": "saved_route_update_failed", "details": str(exc)}), 500


@bp.get("/timeline-events")
@require_admin_access
def timeline_events():
    status = (request.args.get("status") or "").strip()
    event_type = (request.args.get("event_type") or "").strip()
    target_country = (request.args.get("target_country") or "").strip()
    limit = min(max(int(request.args.get("limit") or 50), 1), 100)

    try:
        query = (
            get_supabase()
            .table("relocation_timeline_events")
            .select("*")
            .order("due_date", desc=False)
            .order("created_at", desc=True)
            .limit(limit)
        )
        if status:
            query = query.eq("status", status)
        if event_type:
            query = query.eq("event_type", event_type)
        if target_country:
            query = query.ilike("target_country", target_country)
        response = query.execute()
        return jsonify({"ok": True, "timeline_events": response.data or []})
    except Exception as exc:
        return jsonify({"ok": False, "error": "timeline_events_unavailable", "details": str(exc)}), 503


@bp.patch("/timeline-events/<event_id>")
@require_admin_access
def update_timeline_event(event_id: str):
    payload = request.get_json(silent=True) or {}
    status = (payload.get("status") or "").strip()
    priority = (payload.get("priority") or "").strip()
    update_fields = {}

    if status:
        if status not in TIMELINE_EVENT_STATUSES:
            return jsonify({"ok": False, "error": "invalid_status", "allowed_statuses": sorted(TIMELINE_EVENT_STATUSES)}), 400
        update_fields["status"] = status
    if priority:
        if priority not in TIMELINE_PRIORITIES:
            return jsonify({"ok": False, "error": "invalid_priority", "allowed_priorities": sorted(TIMELINE_PRIORITIES)}), 400
        update_fields["priority"] = priority
    if not update_fields:
        return jsonify({"ok": False, "error": "no_update_fields"}), 400

    try:
        response = (
            get_supabase()
            .table("relocation_timeline_events")
            .update(update_fields)
            .eq("id", event_id)
            .execute()
        )
        updated = (response.data or [None])[0]
        if not updated:
            return jsonify({"ok": False, "error": "timeline_event_not_found"}), 404
        return jsonify({"ok": True, "timeline_event": updated})
    except Exception as exc:
        return jsonify({"ok": False, "error": "timeline_event_update_failed", "details": str(exc)}), 500


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

    source_type = payload["source_type"].strip()
    reliability_level = (payload.get("reliability_level") or "high").strip()
    status = (payload.get("status") or "active").strip()
    if source_type not in SOURCE_TYPES:
        return jsonify({"ok": False, "error": "invalid_source_type", "allowed_source_types": sorted(SOURCE_TYPES)}), 400
    if reliability_level not in SOURCE_RELIABILITY_LEVELS:
        return jsonify({"ok": False, "error": "invalid_reliability_level", "allowed_reliability_levels": sorted(SOURCE_RELIABILITY_LEVELS)}), 400
    if status not in SOURCE_STATUSES:
        return jsonify({"ok": False, "error": "invalid_status", "allowed_statuses": sorted(SOURCE_STATUSES)}), 400

    try:
        review_frequency_days = max(1, min(int(payload.get("review_frequency_days") or 30), 365))
    except (TypeError, ValueError):
        review_frequency_days = 30

    row = {
        "source_name": payload["source_name"].strip(),
        "source_url": payload["source_url"].strip(),
        "source_type": source_type,
        "owner_organization": payload.get("owner_organization"),
        "reliability_level": reliability_level,
        "status": status,
        "review_frequency_days": review_frequency_days,
        "last_checked_at": _now_iso() if payload.get("mark_checked") else None,
        "next_review_due_at": _review_due_iso(review_frequency_days),
        "notes": payload.get("notes"),
    }

    try:
        response = get_supabase().table("relocation_trusted_sources").insert(row).execute()
        return jsonify({"ok": True, "source": (response.data or [None])[0]})
    except Exception as exc:
        return jsonify({"ok": False, "error": "source_create_failed", "details": str(exc)}), 500
