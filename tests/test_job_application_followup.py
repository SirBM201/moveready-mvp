from app.services.job_application_followup import default_followup_at, record_outcome, validate_followup


def test_default_followup_is_after_submission():
    assert default_followup_at("2026-08-23T00:00:00+00:00", 7).startswith("2026-08-30")


def test_terminal_application_cannot_schedule_followup():
    result=validate_followup(lifecycle_state="rejected",action_type="follow_up_email",scheduled_for="2026-08-30T10:00:00+00:00")
    assert result["ok"] is False
    assert result["error"]=="terminal_application_followup_not_allowed"


def test_external_followup_is_user_controlled():
    result=validate_followup(lifecycle_state="submitted",action_type="contact_recruiter",scheduled_for="2026-08-30T10:00:00+00:00")
    assert result["ok"] is True
    assert result["safety"]["auto_contact_employer"] is False


def test_employer_outcome_requires_evidence():
    result=record_outcome("interview")
    assert result["ok"] is False
    assert result["error"]=="outcome_evidence_required"


def test_no_response_can_be_recorded_without_employer_claim():
    result=record_outcome("no_response")
    assert result["ok"] is True


def test_offer_with_evidence_is_valid():
    result=record_outcome("offer",evidence={"type":"offer_document","summary":"Offer received"})
    assert result["ok"] is True
    assert result["outcome"]=="offer"
