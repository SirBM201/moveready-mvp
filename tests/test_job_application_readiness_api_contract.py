from pathlib import Path


def test_b19_2_migration_defines_private_readiness_table():
    sql = Path("supabase/migrations/044_job_application_readiness.sql").read_text()
    assert "relocation_job_application_readiness" in sql
    assert "unique(email, job_id)" in sql
    assert "enable row level security" in sql.lower()
    assert "submission_confirmed_at" in sql


def test_readiness_routes_expose_required_contract():
    source = Path("app/routes/job_application_readiness.py").read_text()
    assert '@bp.get("/jobs/<job_id>/readiness")' in source
    assert '@bp.patch("/jobs/<job_id>/readiness/materials")' in source
    assert '@bp.post("/jobs/<job_id>/readiness/transition")' in source
    assert '@bp.get("/readiness")' in source
    assert "job_is_visible_to_account" in source
    assert "resume_asset_not_owned" in source
    assert "submission_confirmed_at" in source


def test_readiness_blueprint_is_registered():
    source = Path("app/main.py").read_text()
    assert "job_application_readiness.bp" in source
    assert 'url_prefix=f"{API_PREFIX}/jobs"' in source
