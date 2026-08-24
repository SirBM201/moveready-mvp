from pathlib import Path
from app.services.job_employer_targeting import campaign_employer_policy,employer_campaign_fit,normalize_target

def test_priority_watch_and_excluded_lists_are_canonical_employer_ids():
 result=campaign_employer_policy([{"employer_id":"e1","target_type":"priority"},{"employer_id":"e2","target_type":"watch"},{"employer_id":"e3","target_type":"excluded"}])
 assert result["priority"]==["e1"] and result["watch"]==["e2"] and result["excluded"]==["e3"]

def test_exclusion_wins_over_positive_targeting():
 result=campaign_employer_policy([{"employer_id":"e1","target_type":"priority"},{"employer_id":"e1","target_type":"excluded"}])
 assert "e1" not in result["priority"] and "e1" in result["excluded"]

def test_campaign_fit_controls_discovery_not_job_eligibility():
 result=employer_campaign_fit("e1",[{"employer_id":"e1","target_type":"priority"}])
 assert result["priority_boost"] is True and result["watch_for_new_vacancies"] is True
 assert result["safety"]["campaign_fit_is_not_job_eligibility"] is True
 assert result["safety"]["sponsorship_not_inferred"] is True

def test_excluded_employer_is_removed_from_campaign_discovery():
 result=employer_campaign_fit("e9",[{"employer_id":"e9","target_type":"excluded"}])
 assert result["eligible_for_campaign_discovery"] is False

def test_invalid_target_type_is_rejected():
 try:
  normalize_target({"employer_id":"e1","target_type":"guaranteed_sponsor"})
 except ValueError:
  return
 raise AssertionError("normalize_target must reject unsupported target types")

def test_target_persistence_is_private_and_claim_safe():
 sql=Path("supabase/migrations/053_job_employer_campaign_targets.sql").read_text()
 assert "relocation_job_campaign_employer_targets" in sql
 assert "references public.relocation_job_search_campaigns" in sql
 assert "references public.relocation_job_employers" in sql
 assert "enable row level security" in sql and "revoke all privileges" in sql
 assert "not employer endorsement" in sql
