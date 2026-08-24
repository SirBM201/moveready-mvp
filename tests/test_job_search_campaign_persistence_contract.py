from pathlib import Path

def test_campaign_migration_is_private_and_account_scoped():
    sql=Path("supabase/migrations/050_job_search_campaign_persistence.sql").read_text();assert "relocation_job_search_campaigns" in sql;assert "relocation_job_search_campaign_vacancies" in sql;assert "email text not null" in sql;assert "enable row level security" in sql;assert "revoke all privileges" in sql;assert "grant all privileges" in sql
def test_campaign_api_requires_verified_account_and_ownership_filters():
    source=Path("app/routes/job_search_campaigns.py").read_text();assert "get_verified_session_email" in source;assert 'verified_session_required' in source;assert '.eq("email",email)' in source;assert '@bp.post("/campaigns")' in source;assert '@bp.get("/campaigns")' in source;assert '@bp.patch("/campaigns/<campaign_id>")' in source;assert '@bp.delete("/campaigns/<campaign_id>")' in source
def test_vacancy_association_is_explicit_and_safe():
    source=Path("app/routes/job_search_campaigns.py").read_text();assert '@bp.post("/campaigns/<campaign_id>/vacancies")' in source;assert 'job_id_required' in source;assert 'vacancy_claims_verified_by_association' in source;assert '"application_submitted":False' in source
def test_campaign_blueprint_is_registered():
    source=Path("app/__init__.py").read_text();assert "job_search_campaigns" in source;assert 'app.register_blueprint(job_search_campaigns.bp,url_prefix=f"{API_PREFIX}/jobs")' in source
