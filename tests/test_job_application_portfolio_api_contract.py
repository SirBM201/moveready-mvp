from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTE = ROOT / "app/routes/job_application_portfolio.py"


def source():
    return ROUTE.read_text(encoding="utf-8")


def test_portfolio_api_requires_verified_account():
    text = source()
    assert "get_verified_session_email" in text
    assert "verified_session_required" in text


def test_all_application_artifact_queries_are_account_scoped():
    text = source()
    assert 'def _owned_rows(table: str, email: str)' in text
    assert '.eq("email", email)' in text
    for table in ["READINESS_TABLE", "DRAFT_TABLE", "HANDOFF_TABLE", "LIFECYCLE_TABLE", "FOLLOWUP_TABLE"]:
        assert table in text


def test_portfolio_exposes_collection_and_job_detail_routes():
    text = source()
    assert '@bp.get("/application-portfolio")' in text
    assert '@bp.get("/application-portfolio/<job_id>")' in text
    assert "application_portfolio_item_not_found" in text


def test_collection_supports_state_and_actionable_filters():
    text = source()
    assert 'request.args.get("state")' in text
    assert 'request.args.get("actionable")' in text
    assert '"due_followups"' in text


def test_portfolio_remains_read_only_and_non_autonomous():
    text = source()
    assert '"read_model_only": True' in text
    assert '"auto_submit_allowed": False' in text
    assert '"auto_contact_employer": False' in text
    assert "@bp.post" not in text
    assert "@bp.patch" not in text
    assert "@bp.delete" not in text


def test_portfolio_blueprint_registered_once():
    app = (ROOT / "app/__init__.py").read_text(encoding="utf-8")
    assert "job_application_portfolio" in app
    assert app.count("app.register_blueprint(job_application_portfolio.bp") == 1
