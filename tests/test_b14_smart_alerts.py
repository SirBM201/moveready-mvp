from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app import create_app
from app.routes import smart_alerts
from app.services.smart_alerts import (
    SmartAlertPreferenceError,
    alert,
    dedupe_and_rank,
    normalize_preferences,
    preferences_from_payload,
)


class SmartAlertContractTests(unittest.TestCase):
    def test_defaults_are_quiet_and_bounded(self):
        preferences = normalize_preferences(None)
        self.assertTrue(preferences["jobs_enabled"])
        self.assertTrue(preferences["application_followups_enabled"])
        self.assertFalse(preferences["language_reminders_enabled"])
        self.assertEqual(preferences["document_expiry_lead_days"], 180)

        bounded = normalize_preferences({
            "document_expiry_lead_days": 999,
            "language_inactive_days": -5,
            "evidence_refresh_days": "bad",
        })
        self.assertEqual(bounded["document_expiry_lead_days"], 365)
        self.assertEqual(bounded["language_inactive_days"], 1)
        self.assertEqual(bounded["evidence_refresh_days"], 30)

    def test_update_payload_rejects_unknown_or_out_of_range_fields(self):
        with self.assertRaises(SmartAlertPreferenceError) as unknown:
            preferences_from_payload({"send_sms_now": True})
        self.assertEqual(unknown.exception.code, "unsupported_smart_alert_preference")

        with self.assertRaises(SmartAlertPreferenceError) as invalid:
            preferences_from_payload({"language_inactive_days": 0})
        self.assertEqual(invalid.exception.code, "language_inactive_days_out_of_range")

    def test_deduplication_keeps_stronger_alert_and_nearest_due_date(self):
        duplicate = alert(
            category="applications",
            source="application_alert",
            record_id="case-1",
            marker="deadline-1",
            priority="medium",
            title="Application follow-up",
            summary="Review it.",
            href="/application-alerts",
            due_at="2026-08-25",
        )
        stronger = {**duplicate, "priority": "critical", "title": "Critical application follow-up"}
        later = alert(
            category="applications",
            source="application_alert",
            record_id="case-2",
            marker="deadline-2",
            priority="critical",
            title="Later follow-up",
            summary="Review it.",
            href="/application-alerts",
            due_at="2026-09-01",
        )

        ranked = dedupe_and_rank([duplicate, later, stronger])
        self.assertEqual(len(ranked), 2)
        self.assertEqual(ranked[0]["title"], "Critical application follow-up")
        self.assertEqual(ranked[1]["title"], "Later follow-up")

    def test_document_alert_uses_metadata_only_and_never_document_label(self):
        expiry = (datetime.now(timezone.utc) + timedelta(days=8)).date().isoformat()
        rows = smart_alerts._document_alerts([{
            "id": "document-1",
            "document_type": "passport",
            "document_label": "Passport 123456789",
            "expiry_date": expiry,
            "status": "available",
        }], 180)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["priority"], "critical")
        self.assertNotIn("123456789", rows[0]["title"])
        self.assertNotIn("123456789", rows[0]["summary"])

    def test_verified_change_preferences_are_signal_specific(self):
        source_only = {
            "category": "verified_rule_changes",
            "metadata": {"event_type": "review_due", "review_due": True, "source_stale": False},
        }
        opening = {
            "category": "verified_rule_changes",
            "metadata": {"event_type": "opens", "review_due": False, "source_stale": False},
        }
        account = {"source_change_alerts_enabled": True, "opportunity_alerts_enabled": False}
        smart = normalize_preferences(None)
        self.assertTrue(smart_alerts._alert_enabled(source_only, account, smart))
        self.assertFalse(smart_alerts._alert_enabled(opening, account, smart))

    def test_private_endpoint_fails_closed_without_session(self):
        with patch.dict(os.environ, {"FLASK_ENV": "development"}):
            client = create_app().test_client()
        response = client.get("/api/account/smart-alerts")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "session_token_required")

    def test_database_failure_is_not_exposed(self):
        class BrokenClient:
            def table(self, _name):
                raise RuntimeError("secret database address")

        with patch.object(smart_alerts, "get_supabase", return_value=BrokenClient()):
            result = smart_alerts._safe_rows("relocation_example", "person@example.com")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "source_unavailable")
        self.assertNotIn("secret", str(result))


if __name__ == "__main__":
    unittest.main()
