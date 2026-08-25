from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from app import create_app
from app.routes import smart_alerts


class LQ11LaunchReadinessTests(unittest.TestCase):
    def test_daily_digest_contract_is_stable_and_private(self):
        self.assertEqual(smart_alerts.DAILY_DIGEST_TIME_UTC, "07:07")
        self.assertEqual(smart_alerts.DAILY_DIGEST_TIMEZONE, "UTC")

    def test_external_delivery_remains_fail_closed(self):
        source = open("app/routes/smart_alerts.py", encoding="utf-8").read()
        self.assertIn('"mode": "private_in_app"', source)
        self.assertIn('"external_delivery_enabled": False', source)
        for channel in ("email", "whatsapp", "sms", "telegram", "push"):
            self.assertIn(f'"{channel}": "not_enabled"', source)

    def test_private_inbox_requires_verified_session(self):
        with patch.dict(os.environ, {"FLASK_ENV": "development"}):
            client = create_app().test_client()
        response = client.get("/api/account/smart-alerts")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "session_token_required")

    def test_launch_contract_has_no_new_schema_dependency(self):
        source = open("app/routes/smart_alerts.py", encoding="utf-8").read()
        self.assertNotIn("relocation_lq11", source)
        self.assertIn('"generated_at": _now().isoformat()', source)
        self.assertIn('"refresh_available": True', source)


if __name__ == "__main__":
    unittest.main()
