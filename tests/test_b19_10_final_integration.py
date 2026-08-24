from pathlib import Path
from app.services.job_search_campaign_dashboard import build_campaign_dashboard

def campaign():return {"id":"c1","name":"Canada PET","status":"active","search_intensity":"standard"}
def test_dashboard_unifies_progress_goals_strategy_and_daily_actions():
 result=build_campaign_dashboard(campaign=campaign(),vacancies=[{"job_id":"j1"}],applications=[{"state":"interview"}],analytics={},portfolio_actions=[{"type":"complete_followup","priority":"critical"}])
 assert result["progress"]["applications_tracked"]==1
 assert result["weekly_execution"]["targets"]["applications"]==5
 assert result["action_center"]["what_should_i_do_today"][0]["type"]=="complete_followup"
 assert result["safety"]["automatic_application_submission"] is False

def test_dashboard_does_not_convert_analytics_into_eligibility_or_sponsorship_claims():
 result=build_campaign_dashboard(campaign=campaign(),vacancies=[],applications=[],analytics={"applications_analyzed":10})
 assert result["safety"]["historical_performance_is_not_causation"] is True
 assert result["safety"]["eligibility_override_allowed"] is False
 assert result["safety"]["sponsorship_inference_allowed"] is False

def test_campaign_persistence_is_single_source_not_duplicate_dashboard_storage():
 source=Path("app/services/job_search_campaign_dashboard.py").read_text()
 assert "relocation_job_search_campaign_dashboard" not in source
 assert "insert(" not in source and "update(" not in source

def test_b19_10_contract_files_exist():
 for path in ("app/services/job_search_campaign.py","app/services/job_search_campaign_progress.py","app/services/job_search_campaign_strategy.py","app/services/job_search_campaign_action_plan.py","app/services/job_search_campaign_dashboard.py","app/routes/job_search_campaigns.py","supabase/migrations/040_job_search_campaign_persistence.sql"):
  assert Path(path).exists()
