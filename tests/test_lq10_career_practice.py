from pathlib import Path
ROUTE=Path("app/routes/job_career_practice.py").read_text(encoding="utf-8")
MIGRATION=Path("supabase/migrations/055_job_career_practice.sql").read_text(encoding="utf-8")
def test_lq10_private_practice_contract():
 assert "relocation_job_career_practice_sessions" in MIGRATION
 assert "enable row level security" in MIGRATION.lower()
 assert "linkedin_review" in MIGRATION and "mock_interview" in MIGRATION
 assert '@bp.post("/career-practice")' in ROUTE
 assert "user_confirmation_required" in ROUTE
 assert "selection_outcome_not_predicted" in ROUTE
 assert '.eq("email",email)' in ROUTE
