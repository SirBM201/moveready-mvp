from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "app" / "services" / "job_matching.py"
SPEC = importlib.util.spec_from_file_location("job_matching", MODULE_PATH)
assert SPEC and SPEC.loader
JOB_MATCHING = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(JOB_MATCHING)
rank_jobs = JOB_MATCHING.rank_jobs
score_job = JOB_MATCHING.score_job
application_viability = JOB_MATCHING.application_viability


PROFILE = {
    "target_roles": ["Production Supervisor", "PET Injection Moulding Specialist", "Injection Moulding Process Technician"],
    "skills": ["PET preforms", "injection moulding", "Husky", "process troubleshooting"],
    "primary_country": "Canada",
    "preferred_provinces": ["Ontario", "Manitoba"],
    "years_experience": 19,
    "search_scope": "both",
    "current_country": "Kuwait",
    "work_authorized_countries": ["Kuwait"],
}


class JobMatchingTests(unittest.TestCase):
    def test_relevant_pet_supervisor_role_scores_highly(self):
        score, reasons = score_job({"job_title": "PET Injection Molding Production Supervisor", "skills": ["PET preforms", "Husky", "process troubleshooting"], "country": "Canada", "province": "Ontario", "status": "open"}, PROFILE)
        self.assertGreaterEqual(score, 75)
        self.assertTrue(any("target role" in reason for reason in reasons))
        self.assertTrue(any("Shared skills" in reason for reason in reasons))

    def test_moulding_and_molding_are_treated_as_the_same_skill(self):
        score, reasons = score_job({"job_title": "Injection Molding Process Technician", "skills": ["injection molding"], "country": "Canada", "status": "open"}, PROFILE)
        self.assertGreater(score, 40)
        self.assertTrue(reasons)

    def test_missing_profile_does_not_invent_a_match(self):
        score, reasons = score_job({"job_title": "Production Supervisor"}, None)
        self.assertEqual(score, 0)
        self.assertIn("Complete a job-search profile", reasons[0])

    def test_rank_jobs_orders_by_realistic_application_priority(self):
        ranked = rank_jobs([
            {"id": "blocked", "job_title": "PET Production Supervisor", "country": "Canada", "province": "Ontario", "status": "open", "work_authorization_requirement": "existing_required", "visa_sponsorship_status": "not_available"},
            {"id": "supported", "job_title": "Injection Molding Process Technician", "country": "Germany", "status": "open", "work_authorization_requirement": "employer_support_confirmed", "visa_sponsorship_status": "confirmed"},
        ], PROFILE)
        self.assertEqual(ranked[0]["id"], "supported")
        self.assertGreater(ranked[0]["application_priority_score"], ranked[1]["application_priority_score"])

    def test_ranked_payload_exposes_ui_viability_contract(self):
        ranked = rank_jobs([{
            "id": "supported",
            "job_title": "Injection Molding Process Technician",
            "country": "Germany",
            "status": "open",
            "work_authorization_requirement": "employer_support_confirmed",
            "visa_sponsorship_status": "confirmed",
        }], PROFILE)
        job = ranked[0]
        self.assertEqual(job["search_scope_classification"], "international")
        self.assertEqual(job["application_viability_score"], job["application_priority_score"])
        self.assertEqual(job["viability_reasons"], job["application_priority_reasons"])
        self.assertIn(job["application_priority"], {"recommended", "consider"})

    def test_high_skill_match_is_not_recommended_when_sponsorship_refused(self):
        score, _ = score_job({"job_title": "PET Injection Molding Production Supervisor", "skills": ["PET preforms", "Husky", "process troubleshooting"], "country": "Canada", "province": "Ontario", "status": "open"}, PROFILE)
        viability, priority, reasons = application_viability({"country": "Canada", "work_authorization_requirement": "existing_required", "visa_sponsorship_status": "not_available"}, PROFILE, score)
        self.assertGreaterEqual(score, 75)
        self.assertLessEqual(viability, 20)
        self.assertEqual(priority, "not_recommended")
        self.assertTrue(reasons)

    def test_discovered_no_sponsorship_text_blocks_high_match(self):
        ranked = rank_jobs([{
            "id": "source-blocked",
            "job_title": "PET Injection Molding Production Supervisor",
            "skills": ["PET preforms", "Husky", "process troubleshooting"],
            "country": "Canada",
            "province": "Ontario",
            "status": "open",
            "description_summary": "Applicants must currently be authorized to work in Canada. No visa sponsorship is available.",
        }], PROFILE)
        job = ranked[0]
        self.assertGreaterEqual(job["match_score"], 75)
        self.assertEqual(job["visa_sponsorship_status"], "not_available")
        self.assertEqual(job["work_authorization_requirement"], "existing_required")
        self.assertEqual(job["application_priority"], "not_recommended")
        self.assertLessEqual(job["application_viability_score"], 20)

    def test_discovered_sponsorship_text_can_raise_viability(self):
        ranked = rank_jobs([{
            "id": "source-supported",
            "job_title": "Injection Molding Process Technician",
            "country": "Germany",
            "status": "open",
            "description_summary": "Visa sponsorship is available for this position. Relocation assistance is provided.",
        }], PROFILE)
        job = ranked[0]
        self.assertEqual(job["visa_sponsorship_status"], "confirmed")
        self.assertEqual(job["work_authorization_requirement"], "employer_support_confirmed")
        self.assertEqual(job["relocation_support_status"], "confirmed")
        self.assertIn(job["application_priority"], {"recommended", "consider"})

    def test_local_job_does_not_require_sponsorship(self):
        viability, priority, reasons = application_viability({"country": "Kuwait"}, PROFILE, 80)
        self.assertEqual(viability, 80)
        self.assertEqual(priority, "recommended")
        self.assertIn("Local vacancy", reasons[0])

    def test_local_only_scope_rejects_foreign_vacancy(self):
        profile = {**PROFILE, "search_scope": "local"}
        viability, priority, _ = application_viability({"country": "Canada"}, profile, 90)
        self.assertEqual(viability, 0)
        self.assertEqual(priority, "out_of_scope")

    def test_international_only_scope_rejects_current_country_vacancy(self):
        profile = {**PROFILE, "search_scope": "international"}
        viability, priority, _ = application_viability({"country": "Kuwait"}, profile, 90)
        self.assertEqual(viability, 0)
        self.assertEqual(priority, "out_of_scope")


if __name__ == "__main__":
    unittest.main()
