from __future__ import annotations
import os
import unittest
from unittest.mock import patch
from app import create_app
from app.routes import launch_beta

class LQ12LaunchBetaTests(unittest.TestCase):
    def test_locked_cohort_and_taxonomy(self):
        self.assertEqual(launch_beta.DEVICES, {"phone", "tablet", "desktop"})
        self.assertIn("full_journey", launch_beta.JOURNEYS)
        self.assertEqual(launch_beta.RESULTS, {"passed", "blocked", "needs_help"})

    def test_private_report_endpoint_requires_session(self):
        with patch.dict(os.environ, {"FLASK_ENV": "development"}):
            client = create_app().test_client()
        response = client.get("/api/beta/reports")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "verified_session_required")

    def test_admin_summary_is_guarded(self):
        with open("app/routes/launch_beta.py", encoding="utf-8") as handle:
            source = handle.read()
        self.assertIn("@require_admin_access", source)
        self.assertIn('"/admin/beta/summary"', source)

    def test_no_approval_inference(self):
        with open("app/routes/launch_beta.py", encoding="utf-8") as handle:
            source = handle.read()
        self.assertIn("not an immigration, employment or approval outcome", source)
        self.assertIn('"minimum":10,"maximum":20', source)

if __name__ == "__main__":
    unittest.main()
