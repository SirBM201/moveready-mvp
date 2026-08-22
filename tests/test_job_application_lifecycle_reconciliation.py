from app.services.job_application_lifecycle_reconciliation import reconcile_lifecycle_state, validate_employer_evidence


def evidence(kind="email"):
    return {"type":kind,"summary":"Employer confirmed the application status.","observed_at":"2026-08-23T10:00:00+00:00"}


def test_employer_state_requires_structured_evidence():
    result=reconcile_lifecycle_state({"state":"submitted"},target_state="interview",employer_evidence={})
    assert result["ok"] is False
    assert result["error"]=="invalid_employer_evidence_type"


def test_valid_evidence_allows_integrity_bound_transition():
    result=reconcile_lifecycle_state({"state":"submitted"},target_state="interview",employer_evidence=evidence("interview_invite"))
    assert result["ok"] is True
    assert result["state"]=="interview"
    assert result["integrity"]["evidence_validated"] is True
    assert result["integrity"]["autonomous_employer_status_detection"] is False


def test_offer_and_hired_cannot_be_claimed_without_evidence():
    offer=reconcile_lifecycle_state({"state":"interview"},target_state="offer",employer_evidence={})
    hired=reconcile_lifecycle_state({"state":"offer"},target_state="hired",employer_evidence={})
    assert not offer["ok"] and not hired["ok"]


def test_terminal_state_is_locked_against_reconciliation():
    result=reconcile_lifecycle_state({"state":"rejected"},target_state="interview",employer_evidence=evidence("interview_invite"))
    assert result["ok"] is False
    assert result["error"]=="application_lifecycle_is_terminal"


def test_withdrawal_remains_user_controlled():
    denied=reconcile_lifecycle_state({"state":"submitted"},target_state="withdrawn",user_confirmed=False)
    allowed=reconcile_lifecycle_state({"state":"submitted"},target_state="withdrawn",user_confirmed=True)
    assert denied["error"]=="explicit_user_confirmation_required"
    assert allowed["ok"] is True


def test_evidence_schema_rejects_unsupported_claim_source():
    result=validate_employer_evidence("offer",{"type":"guessed","summary":"maybe","observed_at":"2026-08-23"})
    assert result["ok"] is False
    assert result["error"]=="invalid_employer_evidence_type"
