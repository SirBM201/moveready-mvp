from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ROUTE=ROOT/"app/routes/job_application_portfolio.py"
LOADER=ROOT/"app/services/job_application_portfolio_loader.py"
PORTFOLIO=ROOT/"app/services/job_application_portfolio.py"


def source(): return ROUTE.read_text(encoding="utf-8")


def test_portfolio_api_requires_verified_account():
    text=source();assert "get_verified_session_email" in text;assert "verified_session_required" in text


def test_all_application_artifact_queries_are_account_scoped():
    text=source();loader=LOADER.read_text(encoding="utf-8")
    assert '.eq("email",email)' in text
    assert '.eq("email",email)' in loader
    for table in ["READINESS_TABLE","DRAFT_TABLE","HANDOFF_TABLE","LIFECYCLE_TABLE","FOLLOWUP_TABLE"]:
        assert table in text or table in loader


def test_portfolio_exposes_collection_and_job_detail_routes():
    text=source();assert '@bp.get("/application-portfolio")' in text;assert '@bp.get("/application-portfolio/<job_id>")' in text;assert "application_portfolio_item_not_found" in text


def test_collection_supports_state_and_actionable_filters():
    text=source();assert 'request.args.get("state")' in text;assert 'request.args.get("actionable")' in text;assert '"due_followups"' in text


def test_portfolio_read_paths_remain_non_autonomous_and_only_safe_reconciliation_writes():
    text=source();model=PORTFOLIO.read_text(encoding="utf-8")
    assert '"read_model_only": True' in model
    assert '"auto_submit_allowed": False' in model
    assert '"auto_contact_employer": False' in model
    assert '@bp.post("/application-portfolio/<job_id>/reconcile")' in text
    assert "@bp.patch" not in text and "@bp.delete" not in text
    assert '"employer_contact_performed":False' in text
    assert '"application_submission_performed":False' in text
    assert '"lifecycle_state_modified":False' in text


def test_portfolio_blueprint_registered_once():
    app=(ROOT/"app/__init__.py").read_text(encoding="utf-8");assert "job_application_portfolio" in app;assert app.count("app.register_blueprint(job_application_portfolio.bp")==1
