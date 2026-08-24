from pathlib import Path
from app.services.job_employer_history import employer_timeline,opportunity_history

def test_timeline_combines_vacancy_application_and_recorded_interaction():
 result=employer_timeline(employer={"id":"e1","canonical_key":"k"},vacancies=[{"id":"j1","title":"Engineer","created_at":"2026-08-01T00:00:00Z"}],applications=[{"id":"a1","job_id":"j1","state":"interview","updated_at":"2026-08-03T00:00:00Z"}],interactions=[{"interaction_type":"employer_email","occurred_at":"2026-08-02T00:00:00Z","summary":"Assessment invitation"}])
 assert result["event_count"]==3
 assert result["events"][0]["event_type"]=="application_state"
 assert result["safety"]["unrecorded_contact_not_inferred"] is True

def test_opportunity_history_is_descriptive_only():
 result=opportunity_history([{"id":"j1"},{"id":"j2"}],[{"state":"interview"},{"state":"rejected"}])
 assert result["vacancies_observed"]==2 and result["applications_recorded"]==2
 assert result["terminal_outcomes"]==1
 assert result["safety"]["success_rate_not_inferred_without_denominator_contract"] is True

def test_interaction_migration_is_private_and_evidence_safe():
 sql=Path("supabase/migrations/052_job_employer_interactions.sql").read_text()
 assert "relocation_job_employer_interactions" in sql
 assert "enable row level security" in sql and "revoke all privileges" in sql
 assert "evidence_url" in sql and "occurred_at" in sql
 assert "Absence of a row is not evidence" in sql
