from app.services.job_application_portfolio import build_portfolio_item
from app.services.job_application_portfolio_action_feed import portfolio_action


def test_highest_readiness_gap_becomes_direct_execution_command():
    item = build_portfolio_item(
        job={"id": "job-1", "job_title": "Production Supervisor", "company_name": "Example"},
        readiness={
            "state": "discovered",
            "issues": [
                {"code": "cv_missing", "message": "Choose an active résumé.", "severity": "medium", "action": "prepare_cv", "blocking": False},
                {"code": "work_rights_unknown", "message": "Record work-rights evidence.", "severity": "critical", "action": "record_work_rights", "category": "qualification", "blocking": True},
            ],
        },
    )
    assert item["execution_command_version"] == "lq16.1-v1"
    assert item["job_title"] == "Production Supervisor"
    assert item["company_name"] == "Example"
    assert item["next_action"]["type"] == "resolve_readiness_gap"
    assert item["next_action"]["gap_code"] == "work_rights_unknown"
    assert item["next_action"]["href"] == "/jobs/profile"
    assert item["next_action"]["blocking"] is True


def test_command_feed_keeps_direct_gap_destination():
    item = build_portfolio_item(
        job={"id": "job-2", "title": "Engineer"},
        readiness={"state": "discovered", "issues": [{"code": "requirements", "message": "Verify requirements.", "action": "verify_requirements", "blocking": True}]},
    )
    command = portfolio_action(item)
    assert command["href"] == "/jobs/vacancies/job-2/alignment"
    assert command["metadata"]["gap_code"] == "requirements"
    assert command["metadata"]["blocking"] is True


def test_execution_progress_and_safety_remain_explicit():
    item = build_portfolio_item(job={"id": "job-3"}, handoffs=[{"id": "handoff-1", "status": "prepared"}])
    assert item["progress"]["stage"] == "handoff_ready"
    assert 0 < item["progress"]["percent"] < 100
    assert item["next_action"]["type"] == "submit_manually_and_confirm"
    assert item["next_action"]["href"] == "/jobs/execution?jobId=job-3"
    assert item["safety"]["auto_submit_allowed"] is False
