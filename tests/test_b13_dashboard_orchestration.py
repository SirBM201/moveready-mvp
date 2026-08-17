from __future__ import annotations

import unittest

from app.routes import account_action_center


class DashboardOrchestrationContractTests(unittest.TestCase):
    def setUp(self):
        self.loaded = {
            "profiles": [{
                "id": "profile-1",
                "status": "active",
                "main_goal": "work",
                "nationality": "Nigeria",
                "available_funds_amount": 15000,
            }],
            "saved_routes": [{"id": "route-1", "status": "active"}],
            "job_profiles": [{"id": "job-profile-1", "is_active": True}],
            "job_applications": [],
            "job_recruiters": [],
            "language_profiles": [{"id": "language-profile-1"}],
            "language_attempts": [{"id": "attempt-1"}],
            "documents": [{"id": "document-1", "status": "available"}],
            "evidence_packs": [{"id": "pack-1", "status": "ready"}],
            "application_cases": [],
        }

    def test_seven_engines_are_grouped_into_three_phases(self):
        engines = account_action_center._engine_statuses(self.loaded, [])
        self.assertEqual(len(engines), 7)
        self.assertEqual({item["phase"] for item in engines}, {"FIND", "QUALIFY", "MOVE"})
        self.assertEqual(
            {item["key"] for item in engines},
            {"jobs", "route_finder", "passport", "language", "financial_readiness", "documents", "applications"},
        )
        self.assertEqual(next(item for item in engines if item["key"] == "financial_readiness")["state"], "ready")
        self.assertEqual(next(item for item in engines if item["key"] == "applications")["state"], "not_started")

    def test_urgent_private_record_wins_primary_action(self):
        actions = [
            account_action_center._item(
                kind="document",
                record_id="document-1",
                title="Passport expired",
                summary="Renewal is required.",
                priority="critical",
                href="/evidence-pack",
            )
        ]
        primary = account_action_center._primary_action(self.loaded, actions)
        self.assertEqual(primary["id"], "document-1")
        self.assertEqual(primary["source"], "ranked_record")
        self.assertEqual(primary["priority"], "critical")

    def test_foundations_precede_optional_workspaces(self):
        no_profile = {**self.loaded, "profiles": [], "saved_routes": []}
        primary = account_action_center._primary_action(no_profile, [])
        self.assertEqual(primary["kind"], "profile_foundation")
        self.assertEqual(primary["href"], "/onboarding")

        no_route = {**self.loaded, "saved_routes": []}
        primary = account_action_center._primary_action(no_route, [])
        self.assertEqual(primary["kind"], "route_foundation")
        self.assertEqual(primary["href"], "/find")

    def test_public_contract_does_not_expose_database_errors(self):
        original = account_action_center.get_supabase

        class BrokenClient:
            def table(self, _name):
                raise RuntimeError("secret connection detail")

        try:
            account_action_center.get_supabase = lambda: BrokenClient()
            result = account_action_center._safe_rows("example", "person@example.com")
        finally:
            account_action_center.get_supabase = original

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "source_unavailable")
        self.assertNotIn("secret", result["error"])


if __name__ == "__main__":
    unittest.main()
