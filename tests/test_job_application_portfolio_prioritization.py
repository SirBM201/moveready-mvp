from datetime import datetime, timezone

from app.services.job_application_portfolio import build_portfolio_item, deadline_intelligence

NOW = datetime(2026, 8, 24, 3, 0, tzinfo=timezone.utc)


def test_vacancy_deadline_within_24_hours_is_critical():
    result = deadline_intelligence(job={"application_deadline": "2026-08-25T02:00:00Z"}, followups=[], now=NOW)
    assert result["level"] == "critical"
    assert result["source"] == "vacancy_deadline"


def test_overdue_followup_has_maximum_priority():
    item = build_portfolio_item(
        job={"id": "j1"}, lifecycles=[{"id": "l1", "state": "submitted"}],
        followups=[{"id": "f1", "status": "due", "scheduled_for": "2026-08-23T10:00:00Z"}], now=NOW,
    )
    assert item["deadline"]["level"] == "overdue"
    assert item["next_action"]["type"] == "complete_followup"
    assert item["priority_score"] == 100


def test_urgent_vacancy_deadline_promotes_preparation_action():
    item = build_portfolio_item(
        job={"id": "j1", "application_deadline": "2026-08-26T03:00:00Z"},
        readiness={"state": "ready"}, now=NOW,
    )
    assert item["deadline"]["level"] == "urgent"
    assert item["next_action"]["type"] == "generate_application_draft"
    assert item["next_action"]["urgency"] == "high"
    assert item["priority_score"] >= 85


def test_terminal_state_with_active_followup_requests_reconciliation_without_writing():
    item = build_portfolio_item(
        job={"id": "j1"}, lifecycles=[{"id": "l1", "state": "rejected"}],
        followups=[{"id": "f1", "status": "scheduled", "scheduled_for": "2026-08-27T03:00:00Z"}], now=NOW,
    )
    assert item["reconciliation"]["consistent"] is False
    assert "terminal_application_has_active_followups" in item["reconciliation"]["issues"]
    assert item["next_action"]["type"] == "reconcile_terminal_followups"
    assert item["safety"]["reconciliation_writes_performed"] is False


def test_stale_pre_submission_vacancy_is_flagged_for_review():
    item = build_portfolio_item(job={"id": "j1", "is_stale": True}, readiness={"state": "ready"}, now=NOW)
    assert "pre_submission_vacancy_is_stale" in item["reconciliation"]["issues"]
    assert item["next_action"]["type"] == "review_stale_vacancy"


def test_stale_flag_does_not_override_real_post_submission_lifecycle():
    item = build_portfolio_item(job={"id": "j1", "is_stale": True}, lifecycles=[{"id": "l1", "state": "interview"}], now=NOW)
    assert item["pipeline_state"] == "interview"
    assert "pre_submission_vacancy_is_stale" not in item["reconciliation"]["issues"]
    assert item["priority_score"] >= 85
