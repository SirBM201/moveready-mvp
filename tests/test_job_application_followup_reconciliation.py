from datetime import datetime, timezone

from app.services.job_application_followup_reconciliation import active_duplicate, reconcile_due_status, reconcile_outcome, terminal_followup_updates

NOW=datetime(2026,8,23,12,0,tzinfo=timezone.utc)


def test_scheduled_followup_becomes_due_idempotently():
    row={"status":"scheduled","scheduled_for":"2026-08-23T10:00:00+00:00"}
    first=reconcile_due_status(row,now=NOW)
    second=reconcile_due_status({**row,"status":first["status"]},now=NOW)
    assert first["changed"] is True and first["status"]=="due"
    assert second["changed"] is False and second["status"]=="due"


def test_future_followup_remains_scheduled():
    result=reconcile_due_status({"status":"scheduled","scheduled_for":"2026-08-24T10:00:00+00:00"},now=NOW)
    assert result["changed"] is False


def test_duplicate_active_action_is_detected():
    rows=[{"id":"1","lifecycle_id":"l1","action_type":"check_portal","status":"due"}]
    assert active_duplicate(rows,lifecycle_id="l1",action_type="check_portal") is True
    assert active_duplicate(rows,lifecycle_id="l1",action_type="contact_recruiter") is False


def test_terminal_lifecycle_supersedes_pending_actions():
    rows=[{"id":"1","status":"scheduled"},{"id":"2","status":"due"},{"id":"3","status":"completed"}]
    assert terminal_followup_updates(rows,"hired")=={"1":"superseded","2":"superseded"}


def test_non_employer_no_response_does_not_change_lifecycle():
    result=reconcile_outcome({"state":"submitted"},"no_response")
    assert result["ok"] is True
    assert result["lifecycle_changed"] is False


def test_interview_outcome_requires_evidence():
    result=reconcile_outcome({"state":"under_review"},"interview")
    assert result["ok"] is False
    assert result["error"]=="outcome_evidence_required"


def test_evidence_bound_interview_updates_lifecycle():
    proof={"type":"interview_invite","summary":"Interview invitation received","observed_at":"2026-08-23T11:00:00+00:00"}
    result=reconcile_outcome({"state":"under_review"},"interview",evidence=proof)
    assert result["ok"] is True
    assert result["transition"]["state"]=="interview"


def test_withdrawal_cannot_change_lifecycle_without_confirmation():
    denied=reconcile_outcome({"state":"submitted"},"withdrawn",user_confirmed=False)
    allowed=reconcile_outcome({"state":"submitted"},"withdrawn",user_confirmed=True)
    assert denied["ok"] is False
    assert allowed["ok"] is True
