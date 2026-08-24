from pathlib import Path
from app.services.job_application_analytics_dashboard import build_dashboard
from app.services.job_search_feedback import build_feedback_profile,optimize_rank

ROOT=Path(__file__).resolve().parents[1]
def app(i,state):return {"job_id":str(i),"pipeline_state":state,"readiness_state":"ready","source":"official","country":"Canada","occupation":"Engineer","company":"A"}

def test_dashboard_unifies_funnel_performance_recommendations_and_learning():
    result=build_dashboard([app(1,"interview"),app(2,"interview"),app(3,"submitted")])
    assert "summary" in result and "observed_leaders" in result and "recommendations" in result and "search_learning" in result
    assert result["safety"]["ranking_adjustments_bounded"] is True

def test_search_learning_is_bounded_and_cannot_override_eligibility():
    rows=[app(1,"interview"),app(2,"interview"),app(3,"interview")];feedback=build_feedback_profile(rows)
    result=optimize_rank(app(9,"preparing"),base_score=75,feedback=feedback,eligible=False)
    assert result["optimized_score"]==75 and result["analytics_adjustment"]==0

def test_analytics_routes_are_read_only():
    text=(ROOT/"app/routes/job_application_analytics.py").read_text()
    assert "@bp.post" not in text and "@bp.patch" not in text and "@bp.delete" not in text
    assert '@bp.get("/application-analytics/dashboard")' in text

def test_no_duplicate_analytics_persistence_contract():
    services=(ROOT/"app/services/job_application_analytics.py").read_text()+(ROOT/"app/services/job_application_analytics_dashboard.py").read_text()
    assert "relocation_job_application_analytics" not in services
