from app.services.job_application_portfolio import build_portfolio_item, pipeline_state, sort_portfolio


def test_portfolio_progresses_from_preparing_to_hired():
    assert pipeline_state(readiness={"state":"in_progress"},draft=None,handoff=None,lifecycle=None)=="preparing"
    assert pipeline_state(readiness={"state":"ready"},draft=None,handoff=None,lifecycle=None)=="ready_to_apply"
    assert pipeline_state(readiness={"state":"ready"},draft={"id":"d1"},handoff=None,lifecycle=None)=="draft_ready"
    assert pipeline_state(readiness={"state":"ready"},draft={"id":"d1"},handoff={"id":"h1","status":"prepared"},lifecycle=None)=="handoff_ready"
    assert pipeline_state(readiness=None,draft=None,handoff=None,lifecycle={"state":"hired"})=="hired"


def test_due_followup_becomes_top_action():
    item=build_portfolio_item(job={"id":"j1","title":"Engineer"},lifecycle={"id":"l1","state":"submitted"} if False else None,
        lifecycles=[{"id":"l1","state":"submitted"}],followups=[{"id":"f1","status":"due","scheduled_for":"2026-08-23T10:00:00Z"}])
    assert item["next_action"]["type"]=="complete_followup"
    assert item["priority_score"]==100
    assert item["due_followup_count"]==1


def test_terminal_application_has_no_next_action():
    item=build_portfolio_item(job={"id":"j1"},lifecycles=[{"id":"l1","state":"rejected"}],followups=[])
    assert item["terminal"] is True
    assert item["next_action"]["type"]=="none"
    assert item["priority_score"]==0


def test_handoff_ready_prioritizes_manual_submission():
    item=build_portfolio_item(job={"id":"j1"},handoffs=[{"id":"h1","status":"prepared"}])
    assert item["pipeline_state"]=="handoff_ready"
    assert item["next_action"]["type"]=="submit_manually_and_confirm"
    assert item["priority_score"]>=80
    assert item["safety"]["auto_submit_allowed"] is False


def test_stale_vacancy_is_deprioritized_without_changing_state():
    item=build_portfolio_item(job={"id":"j1","is_stale":True},readiness={"state":"ready"})
    assert item["pipeline_state"]=="ready_to_apply"
    assert item["priority_score"]<=20


def test_portfolio_sort_is_priority_first():
    rows=[{"title":"B","priority_score":25},{"title":"A","priority_score":100},{"title":"C","priority_score":50}]
    assert [row["title"] for row in sort_portfolio(rows)]==["A","C","B"]
