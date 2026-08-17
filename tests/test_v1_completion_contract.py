import os
import unittest
from unittest.mock import patch

from app import create_app


def _routes(app):
    return {rule.rule for rule in app.url_map.iter_rules()}


class V1CompletionContractTests(unittest.TestCase):
    def test_v1_completion_routes_are_registered(self):
        with patch.dict(os.environ, {"FLASK_ENV": "development"}):
            app = create_app()
        routes = _routes(app)
        expected = {
            "/api/opportunity-finder/recommendations",
            "/api/financial-readiness/check",
            "/api/route-comparison",
            "/api/account/outcomes",
            "/api/language-coach/profile",
        }
        self.assertTrue(expected.issubset(routes), sorted(expected - routes))

    def test_build_info_reports_v1_safety_contract(self):
        with patch.dict(os.environ, {"FLASK_ENV": "development"}):
            app = create_app()
        client = app.test_client()
        response = client.get("/api/build-info")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["route_contract"]["ok"])
        self.assertEqual(payload["contract_versions"]["financial_readiness"], "b09-v1")
        self.assertEqual(payload["contract_versions"]["opportunity_finder"], "b11-v1")
        self.assertEqual(payload["contract_versions"]["documents_applications"], "b12-v1")
        self.assertEqual(payload["contract_versions"]["dashboard_orchestration"], "b13-v1")
        safety = payload["safety_contract"]
        for key in ("opportunity_finder", "route_comparison", "financial_readiness", "documents_applications", "dashboard_orchestration", "account_outcomes"):
            self.assertIn(key, safety)
        self.assertIn("no invented family multiplier", safety["financial_readiness"].lower())
        features = payload["features"]
        for key in ("opportunity_finder", "route_comparison", "financial_readiness", "account_outcomes", "language_coach", "readiness_command_center"):
            self.assertTrue(features[key])


if __name__ == "__main__":
    unittest.main()
