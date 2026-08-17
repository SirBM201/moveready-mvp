from __future__ import annotations

import unittest

from app.services.language_coach import (
    LanguageCoachValidationError,
    adaptive_difficulty,
    build_learning_plan,
    diagnostic_placement,
    placement_level,
    practice_readiness,
    profile_row_from_payload,
    question_content_is_eligible,
)


class LanguageCoachServiceTests(unittest.TestCase):
    def test_both_languages_respects_supported_allocation(self):
        plan = build_learning_plan({
            "language_selection": "both",
            "allocation": {"english": 70, "french": 30},
            "daily_minutes": 20,
            "diagnostic": {"english": 5, "french": 3},
            "targets": {"english": 7, "french": 7},
        })
        self.assertEqual(plan["contract_version"], "b07-v1")
        self.assertEqual(plan["allocation"], {"english": 70, "french": 30})
        self.assertEqual(
            [item["exam"] for item in plan["languages"]],
            ["IELTS General", "TEF Canada"],
        )
        self.assertEqual(plan["languages"][0]["gap"], 2)
        self.assertEqual(plan["languages"][1]["gap"], 4)

    def test_single_language_choice_is_not_overridden_by_allocation(self):
        plan = build_learning_plan({
            "language_selection": "english",
            "allocation": {"english": 30, "french": 70},
            "diagnostic": {"english": 7, "french": 10},
        })
        self.assertEqual(plan["allocation"], {"english": 100, "french": 0})
        self.assertEqual([item["language"] for item in plan["languages"]], ["english"])

    def test_unsupported_choice_fails_closed(self):
        with self.assertRaisesRegex(LanguageCoachValidationError, "unsupported_language_selection"):
            build_learning_plan({"language_selection": "german"})

    def test_unsupported_both_allocation_fails_closed(self):
        with self.assertRaisesRegex(LanguageCoachValidationError, "unsupported_allocation"):
            build_learning_plan({
                "language_selection": "both",
                "allocation": {"english": 60, "french": 40},
            })

    def test_mismatched_allocation_fails_closed(self):
        with self.assertRaisesRegex(LanguageCoachValidationError, "allocation_must_total_100"):
            build_learning_plan({
                "language_selection": "both",
                "allocation": {"english": 70, "french": 70},
            })

    def test_invalid_numeric_input_does_not_raise_internal_conversion_error(self):
        with self.assertRaisesRegex(LanguageCoachValidationError, "invalid_daily_minutes"):
            build_learning_plan({"daily_minutes": "many"})

    def test_profile_update_preserves_diagnostic_placement(self):
        plan, row = profile_row_from_payload(
            {
                "language_selection": "both",
                "allocation": {"english": 50, "french": 50},
                "diagnostic": {"english": 12, "french": 12},
                "targets": {"english": 8},
            },
            {
                "english_current_level": 3,
                "french_current_level": 2,
                "english_target_level": 7,
                "french_target_level": 6,
            },
        )
        self.assertEqual(row["english_current_level"], 3)
        self.assertEqual(row["french_current_level"], 2)
        self.assertEqual(row["english_target_level"], 8)
        self.assertEqual(row["french_target_level"], 6)
        self.assertEqual(plan["languages"][0]["current_level"], 3)
        self.assertEqual(plan["languages"][1]["target_level"], 6)

    def test_daily_activity_minutes_do_not_exceed_allocated_minutes(self):
        plan = build_learning_plan({
            "language_selection": "both",
            "allocation": {"english": 30, "french": 70},
            "daily_minutes": 5,
        })
        for item in plan["daily_plan"]:
            self.assertEqual(
                sum(activity["minutes"] for activity in item["activities"]),
                item["minutes"],
            )

    def test_missed_day_policy_is_non_punitive(self):
        plan = build_learning_plan({"language_selection": "french"})
        self.assertIn("does not erase", plan["momentum_policy"])

    def test_placement_is_conservative_and_bounded(self):
        self.assertEqual(placement_level(0, 0), 0)
        self.assertEqual(placement_level(2, 10), 1)
        self.assertEqual(placement_level(4, 10), 2)
        self.assertEqual(placement_level(6, 10), 3)
        self.assertEqual(placement_level(8, 10), 4)
        self.assertEqual(placement_level(9, 10), 5)

    def test_diagnostic_does_not_award_level_from_too_few_answers(self):
        result = diagnostic_placement([{"is_correct": True}])
        self.assertFalse(result["complete"])
        self.assertIsNone(result["placement_level"])
        self.assertEqual(result["required_attempts"], 6)

    def test_completed_diagnostic_returns_internal_level(self):
        result = diagnostic_placement(
            [{"is_correct": True} for _ in range(5)]
            + [{"is_correct": False}]
        )
        self.assertTrue(result["complete"])
        self.assertEqual(result["placement_level"], 4)
        self.assertIn("not_official", result["purpose"])

    def test_adaptive_difficulty_moves_up_after_strong_recent_work(self):
        attempts = [{"difficulty": 2, "is_correct": True} for _ in range(8)] + [
            {"difficulty": 2, "is_correct": False} for _ in range(2)
        ]
        self.assertEqual(adaptive_difficulty(attempts), 3)

    def test_adaptive_difficulty_moves_down_after_weak_recent_work(self):
        attempts = [{"difficulty": 4, "is_correct": False} for _ in range(6)] + [
            {"difficulty": 4, "is_correct": True} for _ in range(4)
        ]
        self.assertEqual(adaptive_difficulty(attempts), 3)

    def test_adaptive_difficulty_never_exceeds_bounds(self):
        self.assertEqual(
            adaptive_difficulty([{"difficulty": 5, "is_correct": True} for _ in range(10)]),
            5,
        )
        self.assertEqual(
            adaptive_difficulty([{"difficulty": 1, "is_correct": False} for _ in range(10)]),
            1,
        )

    def test_readiness_requires_a_meaningful_practice_baseline(self):
        self.assertEqual(practice_readiness(1, 1)["readiness"], "building")
        self.assertEqual(practice_readiness(10, 9)["readiness"], "strong_practice_readiness")

    def test_content_provenance_fails_closed(self):
        self.assertTrue(question_content_is_eligible({"content_origin": "moveready_original"}))
        self.assertTrue(question_content_is_eligible({
            "content_origin": "official_released",
            "source_url": "https://authority.example/released-material",
        }))
        self.assertFalse(question_content_is_eligible({
            "content_origin": "official_released",
            "source_url": "http://authority.example/material",
        }))
        self.assertFalse(question_content_is_eligible({"content_origin": "recalled_live_exam"}))


if __name__ == "__main__":
    unittest.main()
