from pathlib import Path

from app.services.job_application_portfolio_action_feed import build_portfolio_action_feed, what_should_i_do_next

ROOT=Path(__file__).resolve().parents[1]


def test_portfolio_action_can_compete_in_account_action_center_ranking():
    items=[{"job_id":"j1","title":"Engineer","company":"Example","priority_score":100,"pipeline_state":"submitted","next_action":{"type":"complete_followup"},"deadline":{"level":"overdue","at":"2026-08-23T10:00:00+00:00","hours_remaining":-5},"reconciliation":{"requires_write_reconciliation":False}}]
    feed=build_portfolio_action_feed(items)
    assert feed[0]["priority"]=="critical"
    assert feed[0]["score"]==100
    assert feed[0]["kind"]=="job_application_portfolio"


def test_what_should_i_do_next_never_returns_terminal_noop():
    items=[{"job_id":"j1","priority_score":0,"pipeline_state":"rejected","next_action":{"type":"none"},"deadline":{},"reconciliation":{}}]
    assert what_should_i_do_next(items) is None


def test_b19_8_modules_preserve_non_autonomous_boundary():
    portfolio=(ROOT/"app/services/job_application_portfolio.py").read_text()
    route=(ROOT/"app/routes/job_application_portfolio.py").read_text()
    corrective=(ROOT/"app/services/job_application_portfolio_reconciliation.py").read_text()
    assert '"auto_submit_allowed": False' in portfolio
    assert '"auto_contact_employer": False' in portfolio
    assert '"application_submission_performed":False' in route
    assert '"employer_contact_performed":False' in route
    assert "change_lifecycle_state" not in corrective


def test_b19_8_uses_existing_persistence_without_new_portfolio_table():
    loader=(ROOT/"app/services/job_application_portfolio_loader.py").read_text()
    assert "relocation_job_application_readiness" in loader
    assert "relocation_job_application_drafts" in loader
    assert "relocation_job_application_handoffs" in loader
    assert "relocation_job_application_lifecycles" in loader
    assert "relocation_job_application_followups" in loader
    assert "relocation_job_application_portfolio" not in loader
