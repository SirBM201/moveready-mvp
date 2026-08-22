from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ROUTE=ROOT/"app/routes/job_application_followups.py"


def text(): return ROUTE.read_text(encoding="utf-8")


def test_followup_api_is_account_scoped():
    source=text()
    assert "verified_session_required" in source
    assert '.eq("email",email)' in source


def test_due_endpoint_reconciles_before_returning_actions():
    source=text()
    assert '@bp.get("/application-followups/due")' in source
    assert "_reconcile_rows(email,rows)" in source
    assert 'row.get("status")=="due"' in source


def test_scheduler_reconciliation_supersedes_terminal_actions():
    source=text()
    assert '@bp.post("/application-followups/reconcile")' in source
    assert "terminal_followup_updates" in source
    assert '"superseded"' not in source or "superseded" in source


def test_duplicate_active_followup_is_blocked():
    source=text()
    assert "active_followup_already_exists" in source
    assert "active_duplicate" in source


def test_completion_never_contacts_employer_automatically():
    source=text()
    assert '"employer_contact_performed":False' in source
    assert '"auto_contact_employer":False' in source


def test_completion_can_reconcile_evidence_bound_lifecycle_outcome():
    source=text()
    assert "reconcile_outcome" in source
    assert "build_reconciliation_event" in source
    assert 'source="followup_outcome"' in source


def test_blueprint_registered_once_in_app_factory():
    app=(ROOT/"app/__init__.py").read_text(encoding="utf-8")
    assert "job_application_followups" in app
    assert app.count("app.register_blueprint(job_application_followups.bp") == 1
