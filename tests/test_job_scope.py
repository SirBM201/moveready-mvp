from __future__ import annotations

import unittest

from app.services.job_scope import (
    country_is_in_scope,
    default_job_country,
    profile_scope_contract,
    profile_scope_update,
    ranked_job_is_alertable,
    ranked_job_is_handoff_ready,
)


PROFILE = {
    "search_scope": "both",
    "current_country": "Kuwait",
    "primary_country": "Canada",
    "later_countries": ["Germany", "Portugal"],
    "work_authorized_countries": ["Kuwait"],
}


class JobScopeContractTests(unittest.TestCase):
    def test_both_scope_separates_local_and_international_targets(self):
        contract = profile_scope_contract(PROFILE)
        self.assertTrue(contract["ready"])
        self.assertEqual(contract["version"], "b05-v1")
        self.assertEqual(contract["local_target_countries"], ["Kuwait"])
        self.assertEqual(
            contract["international_target_countries"],
            ["Canada", "Germany", "Portugal"],
        )
        self.assertEqual(
            contract["target_countries"],
            ["Kuwait", "Canada", "Germany", "Portugal"],
        )

    def test_scope_update_requires_current_country(self):
        row, contract, error = profile_scope_update(
            {"search_scope": "local"},
            {"primary_country": "Canada"},
        )
        self.assertEqual(row, {})
        self.assertEqual(error, "current_country_required")
        self.assertIn("current_country", contract["missing_fields"])

    def test_international_scope_requires_a_foreign_target(self):
        row, contract, error = profile_scope_update(
            {
                "search_scope": "international",
                "current_country": "Kuwait",
            },
            {},
        )
        self.assertEqual(row, {})
        self.assertEqual(error, "international_target_country_required")
        self.assertFalse(contract["ready"])

    def test_clearing_all_foreign_targets_is_rejected(self):
        row, contract, error = profile_scope_update(
            {
                "primary_country": "",
                "later_countries": [],
            },
            PROFILE,
        )
        self.assertEqual(row, {})
        self.assertEqual(error, "international_target_country_required")
        self.assertFalse(contract["ready"])

    def test_country_lists_are_deduplicated_without_inventing_status(self):
        row, contract, error = profile_scope_update(
            {
                "search_scope": "both",
                "current_country": "Kuwait",
                "work_authorized_countries": [
                    "Kuwait",
                    "kuwait",
                    "United Kingdom",
                ],
            },
            PROFILE,
        )
        self.assertIsNone(error)
        self.assertEqual(
            row["work_authorized_countries"],
            ["Kuwait", "United Kingdom"],
        )
        self.assertNotIn("citizenship", row)
        self.assertTrue(contract["ready"])

    def test_default_country_uses_user_scope_not_canada_constant(self):
        self.assertEqual(
            default_job_country({
                **PROFILE,
                "search_scope": "local",
                "primary_country": "Australia",
            }),
            "Kuwait",
        )
        self.assertEqual(
            default_job_country({
                **PROFILE,
                "search_scope": "international",
                "primary_country": "Australia",
            }),
            "Australia",
        )

    def test_country_scope_and_automation_gates_are_bounded(self):
        self.assertTrue(country_is_in_scope("Kuwait", PROFILE))
        self.assertTrue(country_is_in_scope("Germany", PROFILE))
        self.assertFalse(country_is_in_scope("United States", PROFILE))
        self.assertFalse(ranked_job_is_alertable({
            "match_score": 95,
            "application_priority": "out_of_scope",
        }, 60))
        self.assertTrue(ranked_job_is_alertable({
            "match_score": 70,
            "application_priority": "verify_authorization",
        }, 60))
        self.assertFalse(ranked_job_is_handoff_ready({
            "application_priority": "verify_authorization",
        }))
        self.assertTrue(ranked_job_is_handoff_ready({
            "application_priority": "consider",
        }))


if __name__ == "__main__":
    unittest.main()
