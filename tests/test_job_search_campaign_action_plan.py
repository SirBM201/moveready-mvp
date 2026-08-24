from app.services.job_search_campaign_action_plan import daily_action_plan

def campaign():return {"id":"c1","name":"Canada PET","status":"active"}
def test_portfolio_deadline_actions_rank_ahead_of_campaign_discovery():
 strategy={"recommended_actions":[{"type":"discover_more_qualified_vacancies","remaining":4}]}
 actions=[{"type":"follow_up","priority":"critical","due_at":"2026-08-24T10:00:00"}]
 result=daily_action_plan(campaign(),strategy,actions)
 assert result["what_should_i_do_today"][0]["type"]=="follow_up"
 assert result["what_should_i_do_today"][0]["origin"]=="portfolio_action_center"

def test_application_gap_is_high_priority_but_requires_user_action():
 strategy={"recommended_actions":[{"type":"prepare_or_submit_user_approved_applications","remaining":3}]}
 result=daily_action_plan(campaign(),strategy,[])
 assert result["what_should_i_do_today"][0]["priority"]=="high"
 assert result["safety"]["user_action_required"] is True
 assert result["safety"]["automatic_application_submission"] is False

def test_queue_limit_is_bounded():
 actions=[{"type":f"a{i}","priority":"medium"} for i in range(40)]
 result=daily_action_plan(campaign(),{"recommended_actions":[]},actions,limit=100)
 assert result["returned_count"]==25

def test_action_plan_never_inferrs_sponsorship_or_overrides_eligibility():
 result=daily_action_plan(campaign(),{"recommended_actions":[]},[])
 assert result["safety"]["sponsorship_inference_allowed"] is False
 assert result["safety"]["eligibility_override_allowed"] is False
 assert result["safety"]["automatic_external_contact"] is False
