from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Mapping, Optional

CONTRACT_VERSION = "b19.7.4-v1"
FOLLOWUP_STATUSES = {"scheduled", "due", "completed", "cancelled", "superseded"}
ACTION_TYPES = {"follow_up_email", "check_portal", "contact_recruiter", "prepare_assessment", "prepare_interview", "review_offer", "record_outcome", "other"}
OUTCOMES = {"no_response", "acknowledged", "under_review", "assessment", "interview", "offer", "hired", "rejected", "withdrawn", "closed", "unknown"}
TERMINAL_LIFECYCLE_STATES = {"hired", "rejected", "withdrawn", "closed"}


def _text(value: Any) -> str:
    return str(value or "").strip()


def normalize(value: Any) -> str:
    return _text(value).lower().replace("-", "_").replace(" ", "_")


def default_followup_at(submitted_at: str, days: int = 7) -> str:
    base = datetime.fromisoformat(submitted_at.replace("Z", "+00:00"))
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    return (base + timedelta(days=max(1, days))).isoformat()


def validate_followup(*, lifecycle_state: str, action_type: str, scheduled_for: str) -> Dict[str, Any]:
    state = normalize(lifecycle_state); action = normalize(action_type)
    if state in TERMINAL_LIFECYCLE_STATES:
        return {"ok": False, "error": "terminal_application_followup_not_allowed", "contract_version": CONTRACT_VERSION}
    if action not in ACTION_TYPES:
        return {"ok": False, "error": "invalid_followup_action_type", "allowed": sorted(ACTION_TYPES), "contract_version": CONTRACT_VERSION}
    try:
        when = datetime.fromisoformat(_text(scheduled_for).replace("Z", "+00:00"))
    except ValueError:
        return {"ok": False, "error": "valid_followup_schedule_required", "contract_version": CONTRACT_VERSION}
    return {"ok": True, "action_type": action, "scheduled_for": when.isoformat(), "contract_version": CONTRACT_VERSION,
            "safety": {"auto_contact_employer": False, "user_controls_external_action": True}}


def record_outcome(outcome: str, *, evidence: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    value = normalize(outcome); proof = dict(evidence or {})
    if value not in OUTCOMES:
        return {"ok": False, "error": "invalid_application_outcome", "contract_version": CONTRACT_VERSION}
    employer_claim = value in {"acknowledged", "under_review", "assessment", "interview", "offer", "hired", "rejected"}
    if employer_claim and not proof:
        return {"ok": False, "error": "outcome_evidence_required", "outcome": value, "contract_version": CONTRACT_VERSION}
    return {"ok": True, "outcome": value, "evidence": proof, "contract_version": CONTRACT_VERSION,
            "safety": {"employer_response_must_not_be_invented": True, "auto_submit_allowed": False}}
