from app.services.job_search_campaign_strategy import adaptive_strategy,execution_status,weekly_targets

def campaign(intensity="standard"):return {"id":"c1","search_intensity":intensity}
def test_intensity_sets_weekly_execution_targets():
 assert weekly_targets(campaign("light"))["applications"]==2
 assert weekly_targets(campaign("intensive"))["applications"]==10

def test_user_target_overrides_are_bounded():
 result=weekly_targets(campaign(),{"applications":500,"followups":-3})
 assert result["applications"]==100 and result["followups"]==0

def test_execution_status_reports_remaining_work():
 result=execution_status({"applications":5},{"applications":2})
 assert result["metrics"]["applications"]["remaining"]==3
 assert result["metrics"]["applications"]["completion_percent"]==40

def test_adaptive_strategy_uses_only_sufficient_observed_leaders():
 performance={"observed_leaders":{"source":{"value":"official","sample_sufficient":True,"signal":"strong_observed_performance"},"country":None}}
 result=adaptive_strategy(campaign(),performance,{"qualified_vacancies":10,"applications":5,"followups":2},{"qualified_vacancies":4,"applications":2,"followups":0})
 assert any(a["type"]=="test_more_observed_segment" for a in result["recommended_actions"])
 assert result["safety"]["historical_performance_is_not_causation"] is True
 assert result["safety"]["automatic_application_submission"] is False
 assert result["safety"]["automatic_campaign_retargeting"] is False
