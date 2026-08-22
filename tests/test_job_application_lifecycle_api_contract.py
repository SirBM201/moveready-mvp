from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_migration_048_persists_lifecycle_and_immutable_events():
    migration = (ROOT / "supabase/migrations/048_job_application_lifecycle.sql").read_text(encoding="utf-8")
    assert "relocation_job_application_lifecycles" in migration
    assert "relocation_job_application_lifecycle_events" in migration
    assert "unique (email, handoff_id)" in migration
    assert "enable row level security" in migration
    assert "submitted" in migration and "interview" in migration and "offer" in migration and "hired" in migration


def test_lifecycle_api_requires_verified_account_and_owned_records():
    route = (ROOT / "app/routes/job_application_lifecycle.py").read_text(encoding="utf-8")
    assert "verified_session_required" in route
    # Ownership is enforced by email on every handoff/lifecycle/event query.
    assert '.eq("email",email)' in route
    assert "handoff_not_found" in route
    assert "application_lifecycle_not_found" in route


def test_lifecycle_creation_requires_confirmed_manual_handoff():
    route = (ROOT / "app/routes/job_application_lifecycle.py").read_text(encoding="utf-8")
    assert "initial_lifecycle_from_handoff" in route
    assert 'handoff.get("submitted_manual_at")' in route
    assert '"source":"b19.6_manual_handoff"' in route


def test_transition_api_records_evidence_and_event_history():
    route = (ROOT / "app/routes/job_application_lifecycle.py").read_text(encoding="utf-8")
    reconciliation = (ROOT / "app/services/job_application_lifecycle_reconciliation.py").read_text(encoding="utf-8")
    # The route delegates transition validation to the reconciliation service;
    # that service owns transition_application_lifecycle and the safety marker.
    assert "reconcile_lifecycle_state" in route
    assert "transition_application_lifecycle" in reconciliation
    assert 'body.get("employer_evidence")' in route
    assert 'table(EVENT_TABLE).insert(event)' in route
    assert '"autonomous_employer_status_detection": False' in reconciliation


def test_lifecycle_blueprint_is_registered():
    app_init = (ROOT / "app/__init__.py").read_text(encoding="utf-8")
    assert "job_application_lifecycle" in app_init
    assert "app.register_blueprint(job_application_lifecycle.bp" in app_init
