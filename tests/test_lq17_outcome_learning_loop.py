from app.services.job_application_analytics_dashboard import build_dashboard, evidence_integrity


def test_unknown_submission_outcomes_remain_unknown():
    integrity = evidence_integrity([
        {"pipeline_state": "submitted"},
        {"pipeline_state": "interview"},
        {"pipeline_state": "rejected"},
    ])
    assert integrity["unknown_after_submission"] == 1
    assert integrity["confirmed_outcomes"] == 2
    assert integrity["coverage_percent"] == 67
    assert integrity["policy"] == "unknown_outcomes_remain_unknown"


def test_learning_dashboard_exposes_sufficiency_and_safety():
    dashboard = build_dashboard([{"pipeline_state": "submitted", "job": {}}])
    assert dashboard["outcome_learning_version"] == "lq17.1-v1"
    assert dashboard["evidence_integrity"]["sample_sufficient"] is False
    assert any("three recorded applications" in action for action in dashboard["next_learning_actions"])
    assert dashboard["safety"]["success_probability_generated"] is False
    assert dashboard["safety"]["sponsorship_inferred"] is False
