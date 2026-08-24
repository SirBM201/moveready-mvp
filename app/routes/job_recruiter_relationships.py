from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from app.services.account_identity import get_verified_session_email
from app.services.job_recruiter_dashboard import build_recruiter_dashboard
from app.services.supabase_client import get_supabase

bp = Blueprint("job_recruiter_relationships", __name__)
RECRUITERS = "relocation_job_recruiters"
EVENTS = "relocation_job_recruiter_relationship_events"
JOBS = "relocation_jobs"
APPLICATIONS = "relocation_job_applications"
EVENT_TYPES = {
    "connection_requested", "connected", "outreach_prepared", "outreach_sent",
    "response_received", "follow_up_scheduled", "follow_up_completed",
    "vacancy_discussed", "application_discussed", "interview_discussed",
    "declined_contact", "relationship_inactive", "note",
}
CHANNELS = {"email", "linkedin", "phone", "in_person", "other"}


def _account():
    email = get_verified_session_email()
    return (email, None) if email else (None, (jsonify({"ok": False, "error": "verified_session_required"}), 401))


def _recruiter(email: str, recruiter_id: str):
    return get_supabase().table(RECRUITERS).select("*").eq("id", recruiter_id).eq("owner_email", email).maybe_single().execute().data


@bp.get("/recruiters/<recruiter_id>/dashboard")
def dashboard(recruiter_id):
    email, error = _account()
    if error:
        return error
    recruiter = _recruiter(email, recruiter_id)
    if not recruiter:
        return jsonify({"ok": False, "error": "recruiter_not_found"}), 404
    db = get_supabase()
    events = db.table(EVENTS).select("*").eq("owner_email", email).eq("recruiter_id", recruiter_id).order("occurred_at", desc=True).execute().data or []
    vacancies = db.table(JOBS).select("*").eq("owner_email", email).eq("recruiter_id", recruiter_id).execute().data or []
    applications = db.table(APPLICATIONS).select("*").eq("email", email).eq("recruiter_id", recruiter_id).execute().data or []
    return jsonify({"ok": True, **build_recruiter_dashboard(recruiter=recruiter, events=events, vacancies=vacancies, applications=applications)})


@bp.post("/recruiters/<recruiter_id>/events")
def record_event(recruiter_id):
    email, error = _account()
    if error:
        return error
    recruiter = _recruiter(email, recruiter_id)
    if not recruiter:
        return jsonify({"ok": False, "error": "recruiter_not_found"}), 404
    payload = request.get_json(silent=True) or {}
    event_type = str(payload.get("event_type") or "").strip()
    channel = str(payload.get("channel") or "").strip() or None
    if event_type not in EVENT_TYPES:
        return jsonify({"ok": False, "error": "unsupported_event_type"}), 400
    if channel and channel not in CHANNELS:
        return jsonify({"ok": False, "error": "unsupported_channel"}), 400
    if payload.get("automatic_send") is True:
        return jsonify({"ok": False, "error": "automatic_recruiter_contact_not_allowed"}), 400
    row = {
        "owner_email": email,
        "recruiter_id": recruiter_id,
        "employer_id": recruiter.get("canonical_employer_id"),
        "job_id": payload.get("job_id"),
        "application_id": payload.get("application_id"),
        "event_type": event_type,
        "direction": str(payload.get("direction") or "system"),
        "channel": channel,
        "summary": str(payload.get("summary") or "").strip() or None,
        "evidence_url": str(payload.get("evidence_url") or "").strip() or None,
        "occurred_at": payload.get("occurred_at") or datetime.now(timezone.utc).isoformat(),
        "metadata": payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
    }
    if row["direction"] not in {"inbound", "outbound", "system"}:
        return jsonify({"ok": False, "error": "unsupported_direction"}), 400
    saved = get_supabase().table(EVENTS).insert(row).execute().data
    return jsonify({"ok": True, "event": saved[0] if saved else row, "automatic_contact": False}), 201
