from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional, Tuple

from flask import Blueprint, jsonify, request

from app.services.account_identity import get_verified_session_email
from app.services.job_application_lifecycle import CONTRACT_VERSION, LIFECYCLE_STATES, initial_lifecycle_from_handoff, transition_application_lifecycle
from app.services.supabase_client import get_supabase

bp = Blueprint("job_application_lifecycle", __name__)
LIFECYCLE_TABLE = "relocation_job_application_lifecycles"
EVENT_TABLE = "relocation_job_application_lifecycle_events"
HANDOFF_TABLE = "relocation_job_application_handoffs"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _account() -> Tuple[Optional[str], Optional[Tuple[Any, int]]]:
    email = get_verified_session_email()
    if not email:
        return None, (jsonify({"ok": False, "error": "verified_session_required"}), 401)
    return email, None


def _payload() -> dict:
    value = request.get_json(silent=True)
    return value if isinstance(value, dict) else {}


def _handoff(handoff_id: str, email: str):
    return get_supabase().table(HANDOFF_TABLE).select("*").eq("id", handoff_id).eq("email", email).maybe_single().execute().data


def _lifecycle(lifecycle_id: str, email: str):
    return get_supabase().table(LIFECYCLE_TABLE).select("*").eq("id", lifecycle_id).eq("email", email).maybe_single().execute().data


def _events(lifecycle_id: str, email: str):
    return get_supabase().table(EVENT_TABLE).select("*").eq("lifecycle_id", lifecycle_id).eq("email", email).order("created_at").execute().data or []


@bp.post("/application-lifecycles")
def create_lifecycle():
    email, error = _account()
    if error:
        return error
    body = _payload()
    handoff_id = str(body.get("handoff_id") or "").strip()
    if not handoff_id:
        return jsonify({"ok": False, "error": "handoff_id_required"}), 400
    handoff = _handoff(handoff_id, email)
    if not handoff:
        return jsonify({"ok": False, "error": "handoff_not_found"}), 404
    normalized = dict(handoff)
    normalized["submitted_at"] = handoff.get("submitted_manual_at")
    initial = initial_lifecycle_from_handoff(normalized)
    if not initial["ok"]:
        return jsonify(initial), 409
    existing = get_supabase().table(LIFECYCLE_TABLE).select("*").eq("email", email).eq("handoff_id", handoff_id).maybe_single().execute().data
    if existing:
        return jsonify({"ok": True, "created": False, "lifecycle": existing, "events": _events(existing["id"], email)})
    now = _now()
    row = {
        "email": email,
        "job_id": handoff.get("job_id"),
        "draft_id": handoff.get("draft_id"),
        "handoff_id": handoff_id,
        "state": "submitted",
        "contract_version": CONTRACT_VERSION,
        "latest_evidence": {},
        "submitted_at": handoff.get("submitted_manual_at"),
        "state_changed_at": now,
        "created_at": now,
        "updated_at": now,
    }
    created = (get_supabase().table(LIFECYCLE_TABLE).insert(row).execute().data or [None])[0]
    event = {
        "lifecycle_id": created["id"], "email": email, "previous_state": None, "state": "submitted",
        "evidence": {}, "user_confirmed": True,
        "metadata": {"source": "b19.6_manual_handoff", "handoff_id": handoff_id}, "created_at": now,
    }
    get_supabase().table(EVENT_TABLE).insert(event).execute()
    return jsonify({"ok": True, "created": True, "lifecycle": created, "events": _events(created["id"], email)}), 201


@bp.get("/application-lifecycles")
def list_lifecycles():
    email, error = _account()
    if error:
        return error
    state = str(request.args.get("state") or "").strip().lower()
    query = get_supabase().table(LIFECYCLE_TABLE).select("*").eq("email", email)
    if state:
        if state not in LIFECYCLE_STATES:
            return jsonify({"ok": False, "error": "invalid_application_lifecycle_state"}), 400
        query = query.eq("state", state)
    rows = query.order("updated_at", desc=True).execute().data or []
    return jsonify({"ok": True, "count": len(rows), "items": rows, "contract_version": CONTRACT_VERSION})


@bp.get("/application-lifecycles/<lifecycle_id>")
def get_lifecycle(lifecycle_id: str):
    email, error = _account()
    if error:
        return error
    row = _lifecycle(lifecycle_id, email)
    if not row:
        return jsonify({"ok": False, "error": "application_lifecycle_not_found"}), 404
    return jsonify({"ok": True, "lifecycle": row, "events": _events(lifecycle_id, email), "contract_version": CONTRACT_VERSION})


@bp.post("/application-lifecycles/<lifecycle_id>/transition")
def transition_lifecycle(lifecycle_id: str):
    email, error = _account()
    if error:
        return error
    row = _lifecycle(lifecycle_id, email)
    if not row:
        return jsonify({"ok": False, "error": "application_lifecycle_not_found"}), 404
    body = _payload()
    target = str(body.get("target_state") or "").strip().lower()
    evidence = body.get("employer_evidence") if isinstance(body.get("employer_evidence"), dict) else {}
    user_confirmed = bool(body.get("user_confirmed"))
    result = transition_application_lifecycle(row.get("state"), target, employer_evidence=evidence, user_confirmed=user_confirmed)
    if not result["ok"]:
        return jsonify(result), 409
    now = _now()
    update = {
        "state": result["state"], "latest_evidence": evidence, "state_changed_at": now, "updated_at": now,
        "terminal_at": now if result["terminal"] else None,
    }
    updated = (get_supabase().table(LIFECYCLE_TABLE).update(update).eq("id", lifecycle_id).eq("email", email).execute().data or [None])[0]
    event = {
        "lifecycle_id": lifecycle_id, "email": email, "previous_state": result["previous_state"], "state": result["state"],
        "evidence": evidence, "user_confirmed": user_confirmed,
        "metadata": {"recorded_by": "verified_account", "autonomous_employer_status_detection": False}, "created_at": now,
    }
    get_supabase().table(EVENT_TABLE).insert(event).execute()
    return jsonify({"ok": True, "transition": result, "lifecycle": updated, "events": _events(lifecycle_id, email)})
