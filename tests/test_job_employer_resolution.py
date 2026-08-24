from pathlib import Path
from app.services.job_employer_resolution import domain_verification_update,resolve_employer

def test_domain_resolution_links_identity_without_inheriting_claims():
 result=resolve_employer({"company_name":"Example Ltd","company_url":"https://example.com/jobs","country":"Canada"},{"name":"Example Manufacturing","domain":"example.com","country":"Canada"})
 assert result["resolved"] is True and result["resolution_basis"]=="domain"
 assert result["safety"]["claims_inherited"] is False
 assert result["safety"]["sponsorship_inferred"] is False

def test_cross_country_name_only_collision_requires_review():
 result=resolve_employer({"company_name":"Acme Ltd","country":"Canada"},{"name":"Acme Limited","country":"Germany"})
 assert result["resolved"] is False and result["review_required"] is True

def test_domain_verification_requires_evidence_and_observation_time():
 assert domain_verification_update(domain="example.com",evidence_url=None,observed_at="2026-08-24T00:00:00Z")["domain_verified"] is False
 assert domain_verification_update(domain="example.com",evidence_url="https://example.com/careers",observed_at="2026-08-24T00:00:00Z")["domain_verified"] is True

def test_migration_is_private_and_evidence_safe():
 sql=Path("supabase/migrations/051_job_employer_intelligence.sql").read_text()
 assert "relocation_job_employers" in sql and "relocation_job_employer_vacancies" in sql
 assert "enable row level security" in sql and "revoke all privileges" in sql
 assert "domain_evidence_url" in sql and "domain_evidence_observed_at" in sql
 assert "does not transfer unsupported employer claims" in sql
