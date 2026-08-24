from datetime import date
from pathlib import Path

from app.services.job_recruiter_dashboard import build_recruiter_dashboard
from app.services.job_recruiter_followups import follow_up_status
from app.services.job_recruiter_intelligence import recruiter_identity, relationship_state
from app.services.job_recruiter_outreach import outreach_brief, outreach_plan


def recruiter(**overrides):
    row = {"id": "r1", "recruiter_name": "Ada Recruiter", "company_id": "c1", "connection_status": "contacted"}
    row.update(overrides)
    return row


def test_recruiter_identity_is_deterministic_but_not_verification():
    left = recruiter_identity({"recruiter_name": "Ada Recruiter", "email_address": "ADA@EXAMPLE.COM"})
    right = recruiter_identity({"name": "Ada Recruiter", "email": "ada@example.com"})
    assert left["canonical_key"] == right["canonical_key"]
    assert left["safety"]["identity_is_user_recorded_not_verified"] is True
    assert left["safety"]["private_contact_discovery_allowed"] is False


def test_relationship_state_never_turns_connection_into_endorsement():
    result = relationship_state(recruiter(connection_status="responded", connected=True))
    assert result["state"] == "responded"
    assert result["safety"]["connected_does_not_mean_endorsement"] is True
    assert result["safety"]["response_does_not_mean_job_interest"] is True


def test_outreach_requires_destination_and_user_confirmation():
    blocked = outreach_plan({"channel": "email", "purpose": "vacancy_question", "destination": "ada@example.com"})
    assert blocked["ready_for_manual_send"] is False
    assert "user_confirmation_required" in blocked["blocking_reasons"]
    ready = outreach_plan({"channel": "email", "purpose": "vacancy_question", "destination": "ada@example.com", "user_confirmed": True})
    assert ready["ready_for_manual_send"] is True
    assert ready["safety"]["automatic_send"] is False


def test_outreach_brief_preserves_truth_and_manual_review_boundaries():
    result = outreach_brief({"recruiter_name": "Ada", "vacancy_title": "Production Supervisor", "verified_candidate_facts": ["PET preform production"]})
    assert result["verified_candidate_facts"] == ["PET preform production"]
    assert result["drafting_rules"]["fabricate_referral"] is False
    assert result["drafting_rules"]["claim_sponsorship"] is False
    assert result["safety"]["manual_review_required"] is True


def test_due_follow_up_is_advisory_and_never_auto_messages():
    result = follow_up_status(recruiter(follow_up_date="2026-08-20"), today=date(2026, 8, 24))
    assert result["due"] is True
    assert result["recommended_action"] == "review_follow_up"
    assert result["safety"]["automatic_message"] is False
    assert result["safety"]["silence_is_not_rejection"] is True


def test_inactive_relationship_suppresses_follow_up():
    result = follow_up_status(recruiter(follow_up_date="2026-08-20"), [{"event_type": "declined_contact"}], today=date(2026, 8, 24))
    assert result["due"] is False
    assert result["recommended_action"] == "none_relationship_inactive"


def test_dashboard_unifies_private_recorded_relationships():
    result = build_recruiter_dashboard(
        recruiter=recruiter(),
        events=[{"event_type": "outreach_sent", "occurred_at": "2026-08-20T00:00:00Z"}],
        vacancies=[{"id": "j1"}],
        applications=[{"id": "a1"}],
    )
    assert result["relationships"]["vacancy_count"] == 1
    assert result["relationships"]["application_count"] == 1
    assert result["safety"]["automatic_contact"] is False
    assert result["safety"]["sponsorship_not_inferred"] is True


def test_migration_and_authenticated_route_are_private_and_claim_safe():
    sql = Path("supabase/migrations/054_job_recruiter_relationships.sql").read_text()
    route = Path("app/routes/job_recruiter_relationships.py").read_text()
    init = Path("app/__init__.py").read_text()
    assert "relocation_job_recruiter_relationship_events" in sql
    assert "enable row level security" in sql and "revoke all privileges" in sql
    assert "never sends outreach automatically" in sql
    assert "get_verified_session_email" in route and "verified_session_required" in route
    assert "automatic_recruiter_contact_not_allowed" in route
    assert "job_recruiter_relationships" in init
