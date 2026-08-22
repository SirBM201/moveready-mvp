from pathlib import Path

from app.services.job_application_lifecycle import initial_lifecycle_from_handoff, transition_application_lifecycle
from app.services.job_application_followup_reconciliation import reconcile_outcome, terminal_followup_updates


def test_confirmed_handoff_to_terminal_hired_chain_preserves_evidence_boundary():
    started = initial_lifecycle_from_handoff({
        "id": "h1",
        "job_id": "j1",
        "draft_id": "d1",
        "status": "submitted_manual",
        "submitted_at": "2026-08-23T10:00:00Z",
    })
    assert started["ok"] is True
    assert started["state"] == "submitted"
    assert started["safety"]["auto_submit_allowed"] is False

    review = transition_application_lifecycle(
        "submitted", "under_review", employer_evidence={"source": "employer_portal"}
    )
    assert review["ok"] is True

    interview = reconcile_outcome(
        {"state": "under_review"},
        "interview",
        evidence={
            "type": "interview_invite",
            "summary": "Interview invitation received",
            "observed_at": "2026-08-23T11:00:00+00:00",
        },
    )
    assert interview["ok"] is True
    assert interview["transition"]["state"] == "interview"

    offer = transition_application_lifecycle(
        "interview", "offer", employer_evidence={"source": "signed_offer"}
    )
    assert offer["ok"] is True
    assert offer["terminal"] is False

    hired = transition_application_lifecycle(
        "offer", "hired", employer_evidence={"source": "signed_offer"}
    )
    assert hired["ok"] is True
    assert hired["terminal"] is True

    pending = [
        {"id": "f1", "status": "scheduled"},
        {"id": "f2", "status": "due"},
        {"id": "f3", "status": "completed"},
    ]
    assert terminal_followup_updates(pending, "hired") == {
        "f1": "superseded",
        "f2": "superseded",
    }


def test_no_response_cannot_fabricate_employer_progression():
    result = reconcile_outcome({"state": "submitted"}, "no_response")
    assert result["ok"] is True
    assert result["lifecycle_changed"] is False


def test_terminal_lifecycle_cannot_be_silently_reopened():
    result = transition_application_lifecycle(
        "rejected", "interview", employer_evidence={"source": "email"}
    )
    assert result["ok"] is False
    assert result["error"] == "application_lifecycle_is_terminal"


def test_user_withdrawal_remains_explicitly_confirmed():
    denied = reconcile_outcome({"state": "submitted"}, "withdrawn", user_confirmed=False)
    allowed = reconcile_outcome({"state": "submitted"}, "withdrawn", user_confirmed=True)
    assert denied["ok"] is False
    assert allowed["ok"] is True


def test_b19_7_persistence_and_api_contract_is_complete():
    app_factory = Path("app/__init__.py").read_text()
    lifecycle_route = Path("app/routes/job_application_lifecycle.py").read_text()
    followup_route = Path("app/routes/job_application_followups.py").read_text()
    lifecycle_sql = Path("supabase/migrations/048_job_application_lifecycle.sql").read_text()
    followup_sql = Path("supabase/migrations/049_job_application_followups.sql").read_text()

    assert "job_application_lifecycle.bp" in app_factory
    assert "job_application_followups.bp" in app_factory
    assert "relocation_job_application_lifecycles" in lifecycle_sql
    assert "relocation_job_application_lifecycle_events" in lifecycle_sql
    assert "relocation_job_application_followups" in followup_sql
    assert "lifecycle" in lifecycle_route.lower()
    assert "followup" in followup_route.lower() or "follow-up" in followup_route.lower()
