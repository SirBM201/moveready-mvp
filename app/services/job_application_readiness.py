from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional, Set

CONTRACT_VERSION = "b19.1-v1"

READINESS_STATES = (
    "discovered",
    "review_required",
    "blocked",
    "materials_required",
    "ready_for_review",
    "ready_to_apply",
    "application_started",
    "applied",
    "closed",
)

TERMINAL_STATES = {"applied", "closed"}

STATE_TRANSITIONS: Dict[str, Set[str]] = {
    "discovered": {"review_required", "blocked", "materials_required", "ready_for_review", "closed"},
    "review_required": {"blocked", "materials_required", "ready_for_review", "closed"},
    "blocked": {"review_required", "materials_required", "ready_for_review", "closed"},
    "materials_required": {"review_required", "blocked", "ready_for_review", "closed"},
    "ready_for_review": {"review_required", "blocked", "materials_required", "ready_to_apply", "closed"},
    "ready_to_apply": {"review_required", "blocked", "materials_required", "application_started", "closed"},
    "application_started": {"ready_to_apply", "applied", "closed"},
    "applied": {"closed"},
    "closed": set(),
}

BLOCKING_CODES = {
    "vacancy_closed",
    "source_unavailable",
    "work_authorization_required",
    "sponsorship_not_confirmed",
    "mandatory_requirement_missing",
}

MATERIAL_CODES = {
    "cv_required",
    "cover_letter_required",
    "application_answers_required",
}

REVIEW_CODES = {
    "source_verification_required",
    "work_rights_verification_required",
    "sponsorship_verification_required",
    "requirements_review_required",
}


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _issue(code: str, message: str, *, blocking: bool = False) -> Dict[str, Any]:
    return {"code": code, "message": message, "blocking": blocking}


def evaluate_application_readiness(
    vacancy: Mapping[str, Any],
    *,
    profile: Optional[Mapping[str, Any]] = None,
    materials: Optional[Mapping[str, Any]] = None,
    existing_application: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Return a conservative, auditable readiness decision for one vacancy.

    This contract never claims eligibility, sponsorship, submission, or application
    success merely because data is absent. Unknown material facts remain review
    requirements. Submission states only come from an existing application record.
    """

    profile = profile or {}
    materials = materials or {}
    existing_application = existing_application or {}
    issues: List[Dict[str, Any]] = []

    vacancy_status = _text(vacancy.get("status") or "open").lower()
    source_status = _text(vacancy.get("source_status") or vacancy.get("scan_status") or "").lower()
    sponsorship = _text(vacancy.get("relocation_support_status") or vacancy.get("sponsorship_status") or "").lower()
    authorization = _text(profile.get("work_authorization") or profile.get("authorization_status") or "").lower()

    if vacancy_status in {"closed", "archived", "expired", "withdrawn"}:
        issues.append(_issue("vacancy_closed", "The vacancy is no longer recorded as open.", blocking=True))

    if source_status in {"failed", "unavailable", "persistent_failure", "disabled"}:
        issues.append(_issue("source_unavailable", "The official vacancy source is not currently reliable.", blocking=True))
    elif source_status not in {"healthy", "completed", "verified", "ok"}:
        issues.append(_issue("source_verification_required", "Verify the vacancy on the official source before applying."))

    if authorization in {"authorized", "citizen", "permanent_resident", "open_work_permit", "unrestricted"}:
        pass
    elif sponsorship in {"confirmed", "available", "sponsored", "yes"}:
        pass
    elif sponsorship in {"not_available", "not_sponsored", "no", "none"}:
        issues.append(_issue("work_authorization_required", "This vacancy does not record sponsorship; valid work authorization is required.", blocking=True))
    elif authorization in {"not_authorized", "none", "requires_sponsorship"}:
        issues.append(_issue("sponsorship_not_confirmed", "Work authorization is not recorded and employer sponsorship is not confirmed.", blocking=True))
    else:
        issues.append(_issue("work_rights_verification_required", "Confirm work authorization or employer sponsorship before applying."))

    requirements_checked = _truthy(vacancy.get("requirements_verified")) or _truthy(existing_application.get("requirements_verified"))
    if not requirements_checked:
        issues.append(_issue("requirements_review_required", "Review the official vacancy requirements before application."))

    if not (_truthy(materials.get("cv_ready")) or _text(materials.get("cv_id"))):
        issues.append(_issue("cv_required", "Prepare or select a vacancy-appropriate CV."))
    if _truthy(vacancy.get("cover_letter_required")) and not (_truthy(materials.get("cover_letter_ready")) or _text(materials.get("cover_letter_id"))):
        issues.append(_issue("cover_letter_required", "Prepare the required cover letter."))
    if _truthy(vacancy.get("application_questions_required")) and not _truthy(materials.get("application_answers_ready")):
        issues.append(_issue("application_answers_required", "Complete the employer application questions."))

    application_status = _text(existing_application.get("status")).lower()
    submission_confirmed = _truthy(existing_application.get("submission_confirmed"))
    if application_status in {"applied", "submitted"} and submission_confirmed:
        state = "applied"
    elif application_status in {"started", "in_progress", "application_started"}:
        state = "application_started"
    else:
        codes = {item["code"] for item in issues}
        if codes & BLOCKING_CODES:
            state = "blocked"
        elif codes & MATERIAL_CODES:
            state = "materials_required"
        elif codes & REVIEW_CODES:
            state = "review_required"
        else:
            state = "ready_for_review"

    can_mark_ready = state == "ready_for_review"
    can_start_application = state == "ready_to_apply"
    can_record_submission = state == "application_started"

    return {
        "contract_version": CONTRACT_VERSION,
        "state": state,
        "terminal": state in TERMINAL_STATES,
        "issues": issues,
        "blocking_issue_count": sum(1 for item in issues if item["blocking"]),
        "can_mark_ready": can_mark_ready,
        "can_start_application": can_start_application,
        "can_record_submission": can_record_submission,
        "requires_user_confirmation": state in {"ready_for_review", "ready_to_apply", "application_started"},
        "safety": {
            "auto_submit_allowed": False,
            "submission_claim_requires_confirmation": True,
            "eligibility_is_not_guaranteed": True,
        },
    }


def transition_readiness(current_state: str, target_state: str, *, user_confirmed: bool = False) -> Dict[str, Any]:
    current = _text(current_state).lower()
    target = _text(target_state).lower()
    if current not in STATE_TRANSITIONS or target not in READINESS_STATES:
        return {"ok": False, "error": "invalid_readiness_state", "state": current}
    if target not in STATE_TRANSITIONS[current]:
        return {"ok": False, "error": "invalid_readiness_transition", "state": current}
    if target in {"ready_to_apply", "application_started", "applied"} and not user_confirmed:
        return {"ok": False, "error": "user_confirmation_required", "state": current}
    return {"ok": True, "state": target, "previous_state": current}
