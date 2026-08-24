from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ROUTE=ROOT/"app/routes/job_application_analytics.py"


def source(): return ROUTE.read_text(encoding="utf-8")


def test_analytics_api_requires_verified_account():
    text=source();assert "get_verified_session_email" in text;assert "verified_session_required" in text


def test_analytics_api_uses_account_owned_portfolio_loader():
    text=source();assert "load_account_portfolio(email)" in text


def test_analytics_exposes_summary_funnel_and_attribution_routes():
    text=source();assert '@bp.get("/application-analytics")' in text;assert '@bp.get("/application-analytics/funnel")' in text;assert '@bp.get("/application-analytics/attribution")' in text


def test_attribution_dimension_is_allowlisted():
    text=source();assert 'ALLOWED_DIMENSIONS = ("country", "occupation", "employer", "source")' in text;assert "unsupported_attribution_dimension" in text


def test_analytics_api_is_read_only_and_non_autonomous():
    text=source();assert "@bp.post" not in text;assert "@bp.patch" not in text;assert "@bp.delete" not in text;assert '"employer_feedback_inferred": False' in text;assert '"ranking_modified": False' in text;assert '"application_submission_performed": False' in text


def test_analytics_blueprint_registered_once():
    app=(ROOT/"app/__init__.py").read_text(encoding="utf-8");assert "job_application_analytics" in app;assert app.count("app.register_blueprint(job_application_analytics.bp")==1
