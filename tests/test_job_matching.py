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


PROFILE = {
    "target_roles": [
        "Production Supervisor",
        "PET Injection Moulding Specialist",
        "Injection Moulding Process Technician",
    ],
    "skills": ["PET preforms", "injection moulding", "Husky", "process troubleshooting"],
    "primary_country": "Canada",
    "preferred_provinces": ["Ontario", "Manitoba"],
    "years_experience": 19,
}


class JobMatchingTests(unittest.TestCase):
    def test_relevant_pet_supervisor_role_scores_highly(self):
        score, reasons = score_job({
            "job_title": "PET Injection Molding Production Supervisor",
            "skills": ["PET preforms", "Husky", "process troubleshooting"],
            "country": "Canada",
            "province": "Ontario",
            "status": "open",
            "visa_sponsorship_status": "unknown",
        }, PROFILE)

        self.assertGreaterEqual(score, 75)
        self.assertTrue(any("target role" in reason for reason in reasons))
        self.assertTrue(any("Shared skills" in reason for reason in reasons))

    def test_moulding_and_molding_are_treated_as_the_same_skill(self):
        score, reasons = score_job({
            "job_title": "Injection Molding Process Technician",
            "skills": ["injection molding"],
            "country": "Canada",
            "status": "open",
        }, PROFILE)

        self.assertGreater(score, 40)
        self.assertTrue(reasons)

    def test_missing_profile_does_not_invent_a_match(self):
        score, reasons = score_job({"job_title": "Production Supervisor"}, None)

        self.assertEqual(score, 0)
        self.assertIn("Complete a job-search profile", reasons[0])

    def test_rank_jobs_orders_highest_score_first(self):
        ranked = rank_jobs([
            {"id": "unrelated", "job_title": "Accountant", "country": "Germany", "status": "open"},
            {"id": "target", "job_title": "PET Production Supervisor", "country": "Canada", "province": "Ontario", "status": "open"},
        ], PROFILE)

        self.assertEqual(ranked[0]["id"], "target")
        self.assertGreater(ranked[0]["match_score"], ranked[1]["match_score"])


if __name__ == "__main__":
    unittest.main()
