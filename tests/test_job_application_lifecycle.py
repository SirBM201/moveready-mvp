from app.services.job_application_lifecycle import initial_lifecycle_from_handoff, transition_application_lifecycle


def test_lifecycle_starts_only_from_confirmed_manual_submission():
    result = initial_lifecycle_from_handoff({"id": "h1", "job_id": "j1", "draft_id": "d1", "status": "opened"})
    assert result["ok"] is False
    assert result["error"] == "confirmed_manual_submission_required"


def test_confirmed_manual_submission_creates_submitted_state():
    result = initial_lifecycle_from_handoff({"id": "h1", "job_id": "j1", "draft_id": "d1", "status": "submitted_manual", "submitted_at": "2026-08-23T10:00:00Z"})
    assert result["ok"] is True
    assert result["state"] == "submitted"
    assert result["safety"]["auto_submit_allowed"] is False


def test_employer_progress_requires_evidence():
    result = transition_application_lifecycle("submitted", "interview")
    assert result["ok"] is False
    assert result["error"] == "employer_evidence_required"


def test_interview_can_be_recorded_with_employer_evidence():
    result = transition_application_lifecycle("under_review", "interview", employer_evidence={"source": "email", "reference": "message-123"})
    assert result["ok"] is True
    assert result["state"] == "interview"
    assert result["employer_evidence"]["source"] == "email"


def test_offer_requires_evidence_and_is_not_terminal():
    result = transition_application_lifecycle("interview", "offer", employer_evidence={"source": "employer_portal"})
    assert result["ok"] is True
    assert result["state"] == "offer"
    assert result["terminal"] is False


def test_hired_requires_offer_and_evidence():
    result = transition_application_lifecycle("offer", "hired", employer_evidence={"source": "signed_offer"})
    assert result["ok"] is True
    assert result["terminal"] is True


def test_user_withdrawal_requires_explicit_confirmation():
    blocked = transition_application_lifecycle("under_review", "withdrawn", user_confirmed=False)
    assert blocked["ok"] is False
    assert blocked["error"] == "explicit_user_confirmation_required"
    allowed = transition_application_lifecycle("under_review", "withdrawn", user_confirmed=True)
    assert allowed["ok"] is True
    assert allowed["terminal"] is True


def test_terminal_state_cannot_be_reopened_silently():
    result = transition_application_lifecycle("rejected", "interview", employer_evidence={"source": "email"})
    assert result["ok"] is False
    assert result["error"] == "application_lifecycle_is_terminal"


def test_invalid_backward_transition_is_rejected():
    result = transition_application_lifecycle("offer", "under_review", employer_evidence={"source": "portal"})
    assert result["ok"] is False
    assert result["error"] == "invalid_application_lifecycle_transition"
