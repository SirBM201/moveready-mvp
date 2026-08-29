from app.services.job_v1_launch_journey import build_v1_launch_journey


def test_v1_journey_starts_with_matching_target():
    result=build_v1_launch_journey(profile={},vacancies=[],portfolio=[])
    assert result["scope"]=="v1_launch_only"
    assert result["next_action"]["stage"]=="setup"
    assert result["progress_percent"]==0


def test_v1_journey_moves_from_find_to_qualify():
    result=build_v1_launch_journey(profile={"target_roles":["Engineer"],"target_countries":["Canada"]},vacancies=[{"id":"j1"}],portfolio=[])
    assert result["next_action"]["stage"]=="qualify"
    assert result["next_action"]["href"]=="/jobs/vacancies/j1"


def test_v1_journey_uses_existing_execution_command():
    item={"job_id":"j1","readiness_state":"ready_to_apply","pipeline_state":"ready_to_apply","next_action":{"type":"generate_application_draft","title":"Prepare draft","href":"/jobs/execution?jobId=j1"}}
    result=build_v1_launch_journey(profile={"target_roles":["Engineer"],"target_countries":["Canada"]},vacancies=[{"id":"j1"}],portfolio=[item])
    assert result["next_action"]["stage"]=="execute"
    assert result["next_action"]["title"]=="Prepare draft"
    assert "payments" in result["excluded_from_v1"]
    assert result["safety"]["automatic_external_action"] is False


def test_v1_journey_does_not_reopen_a_terminal_item():
    item={"job_id":"j1","readiness_state":"ready_to_apply","pipeline_state":"rejected","next_action":{"type":"none"}}
    result=build_v1_launch_journey(profile={"target_roles":["Engineer"],"target_countries":["Canada"]},vacancies=[{"id":"j1"}],portfolio=[item])
    assert result["next_action"]["title"]=="Review recorded outcomes"
    assert result["next_action"]["href"]=="/jobs/intelligence"
