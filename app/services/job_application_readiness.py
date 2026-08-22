from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Mapping, Optional, Set

CONTRACT_VERSION = "b19.3-v1"

READINESS_STATES = (
    "discovered", "review_required", "blocked", "materials_required",
    "ready_for_review", "ready_to_apply", "application_started", "applied", "closed",
)
TERMINAL_STATES = {"applied", "closed"}
USER_PROMOTED_STATES = {"ready_to_apply", "application_started"}

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
BLOCKING_CODES = {"vacancy_closed", "source_unavailable", "work_authorization_required", "sponsorship_not_confirmed", "mandatory_requirement_missing"}
MATERIAL_CODES = {"cv_required", "cover_letter_required", "application_answers_required"}
REVIEW_CODES = {"source_verification_required", "work_rights_verification_required", "sponsorship_verification_required", "requirements_review_required"}

# Only facts capable of changing the application decision belong in the fingerprint.
FINGERPRINT_FIELDS = (
    "status", "source_status", "scan_status", "relocation_support_status", "sponsorship_status",
    "cover_letter_required", "application_questions_required", "job_title", "country", "province", "city",
    "requirements", "description", "source_url", "apply_url", "canonical_identity", "updated_at",
)


def _truthy(value: Any) -> bool:
    if isinstance(value, bool): return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _issue(code: str, message: str, *, blocking: bool = False) -> Dict[str, Any]:
    return {"code": code, "message": message, "blocking": blocking}


def vacancy_fingerprint(vacancy: Mapping[str, Any]) -> str:
    canonical = {key: vacancy.get(key) for key in FINGERPRINT_FIELDS if key in vacancy}
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"), default=str, ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def reconcile_readiness(previous: Optional[Mapping[str, Any]], evaluation: Mapping[str, Any], fingerprint: str) -> Dict[str, Any]:
    previous = previous or {}
    old_state = _text(previous.get("state") or "discovered").lower()
    old_fingerprint = _text(previous.get("vacancy_fingerprint"))
    changed = bool(old_fingerprint and old_fingerprint != fingerprint)
    evaluated_state = _text(evaluation.get("state") or "review_required").lower()
    final_state = evaluated_state
    invalidated = False
    reason = None

    # Applied is historical truth and is never silently undone. Closed stays terminal.
    if old_state == "applied":
        final_state = "closed" if evaluated_state == "blocked" and any(i.get("code") == "vacancy_closed" for i in evaluation.get("issues", [])) else "applied"
    elif old_state == "closed":
        final_state = "closed"
    elif changed and old_state in USER_PROMOTED_STATES:
        # Any application-relevant vacancy change revokes prior readiness confirmation.
        # A submission already confirmed is protected above.
        invalidated = True
        reason = "vacancy_changed_after_user_confirmation"
        final_state = evaluated_state
    elif old_state == "ready_to_apply" and not changed and evaluated_state == "ready_for_review":
        # Preserve explicit user confirmation while the underlying facts are unchanged.
        final_state = "ready_to_apply"
    elif old_state == "application_started" and not changed and evaluated_state not in {"blocked", "closed"}:
        final_state = "application_started"

    return {
        "state": final_state,
        "previous_state": old_state,
        "vacancy_changed": changed,
        "invalidated": invalidated,
        "invalidation_reason": reason,
        "vacancy_fingerprint": fingerprint,
    }


def evaluate_application_readiness(vacancy: Mapping[str, Any], *, profile: Optional[Mapping[str, Any]] = None, materials: Optional[Mapping[str, Any]] = None, existing_application: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    profile, materials, existing_application = profile or {}, materials or {}, existing_application or {}
    issues: List[Dict[str, Any]] = []
    vacancy_status = _text(vacancy.get("status") or "open").lower()
    source_status = _text(vacancy.get("source_status") or vacancy.get("scan_status") or "").lower()
    sponsorship = _text(vacancy.get("relocation_support_status") or vacancy.get("sponsorship_status") or "").lower()
    authorization = _text(profile.get("work_authorization") or profile.get("authorization_status") or "").lower()
    if vacancy_status in {"closed", "archived", "expired", "withdrawn"}: issues.append(_issue("vacancy_closed", "The vacancy is no longer recorded as open.", blocking=True))
    if source_status in {"failed", "unavailable", "persistent_failure", "disabled"}: issues.append(_issue("source_unavailable", "The official vacancy source is not currently reliable.", blocking=True))
    elif source_status not in {"healthy", "completed", "verified", "ok"}: issues.append(_issue("source_verification_required", "Verify the vacancy on the official source before applying."))
    if authorization in {"authorized", "citizen", "permanent_resident", "open_work_permit", "unrestricted"}: pass
    elif sponsorship in {"confirmed", "available", "sponsored", "yes"}: pass
    elif sponsorship in {"not_available", "not_sponsored", "no", "none"}: issues.append(_issue("work_authorization_required", "This vacancy does not record sponsorship; valid work authorization is required.", blocking=True))
    elif authorization in {"not_authorized", "none", "requires_sponsorship"}: issues.append(_issue("sponsorship_not_confirmed", "Work authorization is not recorded and employer sponsorship is not confirmed.", blocking=True))
    else: issues.append(_issue("work_rights_verification_required", "Confirm work authorization or employer sponsorship before applying."))
    requirements_checked = _truthy(vacancy.get("requirements_verified")) or _truthy(existing_application.get("requirements_verified"))
    if not requirements_checked: issues.append(_issue("requirements_review_required", "Review the official vacancy requirements before application."))
    if not (_truthy(materials.get("cv_ready")) or _text(materials.get("cv_id"))): issues.append(_issue("cv_required", "Prepare or select a vacancy-appropriate CV."))
    if _truthy(vacancy.get("cover_letter_required")) and not (_truthy(materials.get("cover_letter_ready")) or _text(materials.get("cover_letter_id"))): issues.append(_issue("cover_letter_required", "Prepare the required cover letter."))
    if _truthy(vacancy.get("application_questions_required")) and not _truthy(materials.get("application_answers_ready")): issues.append(_issue("application_answers_required", "Complete the employer application questions."))
    application_status = _text(existing_application.get("status")).lower()
    submission_confirmed = _truthy(existing_application.get("submission_confirmed"))
    if application_status in {"applied", "submitted"} and submission_confirmed: state = "applied"
    elif application_status in {"started", "in_progress", "application_started"}: state = "application_started"
    else:
        codes = {item["code"] for item in issues}
        if codes & BLOCKING_CODES: state = "blocked"
        elif codes & MATERIAL_CODES: state = "materials_required"
        elif codes & REVIEW_CODES: state = "review_required"
        else: state = "ready_for_review"
    return {"contract_version": CONTRACT_VERSION, "state": state, "terminal": state in TERMINAL_STATES, "issues": issues, "blocking_issue_count": sum(1 for i in issues if i["blocking"]), "can_mark_ready": state == "ready_for_review", "can_start_application": state == "ready_to_apply", "can_record_submission": state == "application_started", "requires_user_confirmation": state in {"ready_for_review", "ready_to_apply", "application_started"}, "safety": {"auto_submit_allowed": False, "submission_claim_requires_confirmation": True, "eligibility_is_not_guaranteed": True}}


def transition_readiness(current_state: str, target_state: str, *, user_confirmed: bool = False) -> Dict[str, Any]:
    current, target = _text(current_state).lower(), _text(target_state).lower()
    if current not in STATE_TRANSITIONS or target not in READINESS_STATES: return {"ok": False, "error": "invalid_readiness_state", "state": current}
    if target not in STATE_TRANSITIONS[current]: return {"ok": False, "error": "invalid_readiness_transition", "state": current}
    if target in {"ready_to_apply", "application_started", "applied"} and not user_confirmed: return {"ok": False, "error": "user_confirmation_required", "state": current}
    return {"ok": True, "state": target, "previous_state": current}
