from __future__ import annotations

import unittest

from app import create_app
from app.services.job_v1_launch_journey import build_v1_launch_journey


class LQ20V1LaunchAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = create_app().test_client()

    def test_public_operational_contracts_are_reachable(self):
        for path in ("/api/health", "/api/build-info", "/api/auth/health", "/api/operations/status"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.is_json)
                self.assertTrue(response.get_json().get("ok"), response.get_json())

    def test_anonymous_jobs_boundary_fails_closed(self):
        response = self.client.get("/api/jobs/options")
        self.assertEqual(response.status_code, 401)
        self.assertTrue(response.is_json)

    def test_v1_journey_never_infers_or_executes(self):
        journey = build_v1_launch_journey(profile={}, vacancies=[], portfolio=[])
        self.assertEqual(journey["scope"], "v1_launch_only")
        self.assertFalse(journey["safety"]["eligibility_or_approval_inferred"])
        self.assertFalse(journey["safety"]["automatic_external_action"])
        for deferred in ("payments", "marketplace", "automatic_submission", "real_notification_delivery", "provider_network"):
            self.assertIn(deferred, journey["excluded_from_v1"])


if __name__ == "__main__":
    unittest.main()
