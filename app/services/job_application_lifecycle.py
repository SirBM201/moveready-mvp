from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Set

CONTRACT_VERSION = "b19.7-v1"

LIFECYCLE_STATES = (
    "submitted",
    "acknowledged",
    "under_review",
    "assessment",
    "interview",
    "offer",
    "hired",
    "rejected",
    "withdrawn",
    "closed",
)

TERMINAL_STATES = {"hired", "rejected", "withdrawn", "closed"}
POSITIVE_STATES = {"acknowledged", "under_review", "assessment", "interview", "offer", "hired"}

STATE_TRANSITIONS: Dict[str, Set[str]] = {
    "submitted": {"acknowledged", "under_review", "assessment", "interview", "offer", "rejected", "withdrawn", "closed"},
    "acknowledged": {"under_review", "assessment", "interview", "offer", "rejected", "withdrawn", "closed"},
    "under_review": {"assessment", "interview", "offer", "rejected", "withdrawn", "closed"},
    "assessment": {"under_review", "interview", "offer", "rejected", "withdrawn", "closed"},
    "interview": {"assessment", "interview", "offer", "rejected", "withdrawn", "closed"},
    "offer": {"hired", "rejected", "withdrawn", "closed"},
    "hired": set(),
    "rejected": set(),
    "withdrawn": set(),
    "closed": set(),
}

EMPLOYER_EVIDENCE_STATES = {"acknowledged", "under_review", "assessment", "interview", "offer", "hired", "rejected"}
USER_CONTROLLED_STATES = {"withdrawn"}


def _text(value: Any) -> str:
    return str(value or "").strip()


def normalize_state(value: Any) -> str:
    return _text(value).lower().replace("-", "_").replace(" ", "_")


def transition_application_lifecycle(
    current_state: str,
    target_state: str,
    *,
    employer_evidence: Optional[Mapping[str, Any]] = None,
    user_confirmed: bool = False,
) -> Dict[str, Any]:
    current = normalize_state(current_state)
    target = normalize_state(target_state)
    evidence = dict(employer_evidence or {})

    if current not in STATE_TRANSITIONS or target not in LIFECYCLE_STATES:
        return {"ok": False, "error": "invalid_application_lifecycle_state", "state": current, "contract_version": CONTRACT_VERSION}
    if current in TERMINAL_STATES:
        return {"ok": False, "error": "application_lifecycle_is_terminal", "state": current, "contract_version": CONTRACT_VERSION}
    if target not in STATE_TRANSITIONS[current]:
        return {"ok": False, "error": "invalid_application_lifecycle_transition", "state": current, "target_state": target, "contract_version": CONTRACT_VERSION}
    if target in EMPLOYER_EVIDENCE_STATES and not evidence:
        return {"ok": False, "error": "employer_evidence_required", "state": current, "target_state": target, "contract_version": CONTRACT_VERSION}
    if target in USER_CONTROLLED_STATES and not user_confirmed:
        return {"ok": False, "error": "explicit_user_confirmation_required", "state": current, "target_state": target, "contract_version": CONTRACT_VERSION}

    return {
        "ok": True,
        "contract_version": CONTRACT_VERSION,
        "previous_state": current,
        "state": target,
        "terminal": target in TERMINAL_STATES,
        "employer_evidence": evidence if target in EMPLOYER_EVIDENCE_STATES else None,
        "user_confirmed": bool(user_confirmed) if target in USER_CONTROLLED_STATES else None,
        "safety": {
            "auto_submit_allowed": False,
            "employer_response_must_not_be_invented": True,
            "offer_or_hire_status_requires_evidence": True,
            "user_controls_withdrawal": True,
        },
    }


def initial_lifecycle_from_handoff(handoff: Mapping[str, Any]) -> Dict[str, Any]:
    status = normalize_state(handoff.get("status"))
    if status != "submitted_manual":
        return {"ok": False, "error": "confirmed_manual_submission_required", "contract_version": CONTRACT_VERSION}
    if not handoff.get("submitted_at"):
        return {"ok": False, "error": "submission_timestamp_required", "contract_version": CONTRACT_VERSION}
    return {
        "ok": True,
        "contract_version": CONTRACT_VERSION,
        "state": "submitted",
        "terminal": False,
        "submission_source": "user_confirmed_manual_handoff",
        "handoff_id": handoff.get("id"),
        "job_id": handoff.get("job_id"),
        "draft_id": handoff.get("draft_id"),
        "submitted_at": handoff.get("submitted_at"),
        "safety": {"submission_claim_is_user_confirmed": True, "auto_submit_allowed": False},
    }
