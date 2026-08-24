from app.services.job_application_portfolio_action_feed import build_portfolio_action_feed, portfolio_action, what_should_i_do_next


def item(job_id, score, action_type, hours=None, state="submitted"):
    return {"job_id":job_id,"title":f"Job {job_id}","company":"Example","priority_score":score,"pipeline_state":state,"next_action":{"type":action_type},"deadline":{"level":"normal","at":None,"hours_remaining":hours},"reconciliation":{"requires_write_reconciliation":False}}


def test_terminal_no_action_is_not_added_to_feed():
    row=item("j1",0,"none",state="rejected")
    assert portfolio_action(row) is None


def test_feed_ranks_highest_application_priority_first():
    feed=build_portfolio_action_feed([item("j1",50,"schedule_followup"),item("j2",100,"complete_followup",-2),item("j3",85,"generate_application_draft",48)])
    assert [row["job_id"] for row in feed]==["j2","j3","j1"]


def test_equal_score_uses_nearest_deadline_first():
    feed=build_portfolio_action_feed([item("later",80,"submit_manually_and_confirm",72),item("sooner",80,"submit_manually_and_confirm",12)])
    assert feed[0]["job_id"]=="sooner"


def test_what_should_i_do_next_returns_single_top_action():
    result=what_should_i_do_next([item("j1",50,"schedule_followup"),item("j2",95,"complete_followup",1)])
    assert result["job_id"]=="j2"
    assert result["contract_version"]=="b19.8.5-v1"
    assert "Highest-ranked" in result["reason"]


def test_feed_preserves_non_autonomous_manual_submission_language():
    result=portfolio_action(item("j1",80,"submit_manually_and_confirm"))
    assert "manually" in result["title"].lower()
    assert result["source"]=="b19.8_application_portfolio"
