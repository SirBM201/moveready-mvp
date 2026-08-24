from pathlib import Path
from app.services.job_employer_dashboard import build_employer_dashboard

def employer():return {"id":"e1","canonical_key":"k1","canonical_name":"Example","domain":"example.com"}
def test_dashboard_unifies_history_targeting_ranking_and_timeline():
 result=build_employer_dashboard(employer=employer(),vacancies=[{"id":"j1","title":"Engineer","created_at":"2026-08-01T00:00:00Z"}],applications=[{"id":"a1","job_id":"j1","state":"interview","updated_at":"2026-08-02T00:00:00Z"}],interactions=[{"interaction_type":"interview","occurred_at":"2026-08-03T00:00:00Z"}],campaign_targets=[{"employer_id":"e1","target_type":"priority"}],ranking_inputs={"vacancy_fit":.9,"evidence_quality":.9,"freshness":.9,"campaign_disposition":"priority"})
 assert result["opportunity_history"]["vacancies_observed"]==1
 assert result["timeline"]["event_count"]==3
 assert result["campaign_fit"]["priority_boost"] is True
 assert result["recommendation"]["score"]>0
 assert result["safety"]["automatic_application_submission"] is False

def test_dashboard_never_turns_identity_or_history_into_employer_claims():
 result=build_employer_dashboard(employer=employer())
 assert result["safety"]["canonical_identity_is_not_employer_verification"] is True
 assert result["safety"]["sponsorship_not_inferred"] is True
 assert result["safety"]["relocation_support_not_inferred"] is True
 assert result["safety"]["historical_outcomes_do_not_predict_future_outcomes"] is True

def test_authenticated_route_and_b19_11_files_exist():
 route=Path("app/routes/job_employers.py").read_text();init=Path("app/__init__.py").read_text()
 assert "get_verified_session_email" in route and "verified_session_required" in route
 assert '@bp.get("/employers/<employer_id>/dashboard")' in route
 assert "job_employers" in init
 for path in ("app/services/job_employer_intelligence.py","app/services/job_employer_resolution.py","app/services/job_employer_history.py","app/services/job_employer_targeting.py","app/services/job_employer_ranking.py","app/services/job_employer_dashboard.py","supabase/migrations/051_job_employer_intelligence.sql","supabase/migrations/052_job_employer_interactions.sql","supabase/migrations/053_job_employer_campaign_targets.sql"):
  assert Path(path).exists()
