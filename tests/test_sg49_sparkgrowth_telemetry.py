from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest import mock

from app.services import sparkgrowth_telemetry as telemetry


class FakeResponse:
    def __init__(self, status_code=201, payload=None):
        self.status_code = status_code
        self._payload = payload or {
            "touchpoint_id": 1,
            "accepted": True,
            "deduplicated": False,
            "attribution_status": None,
        }
        self.content = json.dumps(self._payload).encode()

    def json(self):
        return self._payload


class SparkGrowthTelemetryTests(unittest.TestCase):
    def setUp(self):
        self.config = mock.patch.multiple(
            telemetry,
            SECRET_KEY="unit-test-secret",
            SPARKGROWTH_TELEMETRY_ENABLED=True,
            SPARKGROWTH_API_BASE="https://sparkgrowth.example",
            SPARKGROWTH_INGESTION_KEY="server-secret-ingestion-key",
            SPARKGROWTH_WORKSPACE_ID="11111111-1111-1111-1111-111111111111",
            SPARKGROWTH_TELEMETRY_TIMEOUT_SECONDS=2,
        )
        self.config.start()
        self.addCleanup(self.config.stop)

    def test_subject_is_stable_pseudonymous_and_visitors_do_not_merge(self):
        a1 = telemetry.subject_id_for_login_code("login-code-a")
        a2 = telemetry.subject_id_for_login_code("login-code-a")
        b = telemetry.subject_id_for_login_code("login-code-b")
        self.assertEqual(a1, a2)
        self.assertNotEqual(a1, b)
        self.assertTrue(a1.startswith("mr_subject_"))
        self.assertNotIn("login-code-a", a1)
        self.assertNotIn("@", a1)

    def test_session_registration_activation_use_same_subject_and_deterministic_ids(self):
        meta = telemetry.telemetry_session_metadata("login-code-123", {})
        subject = meta["growth_subject_id"]
        session = meta["growth_session_id"]
        captured = []

        def fake_post(_url, json=None, **_kwargs):
            captured.append(json)
            return FakeResponse()

        with mock.patch.object(telemetry.requests, "post", side_effect=fake_post):
            for event_name in ("session", "registration", "activation"):
                telemetry.track_event(
                    event_name,
                    subject,
                    session,
                    {},
                    attribution_model="last_touch" if event_name == "activation" else None,
                )

        self.assertEqual([item["event_name"] for item in captured], [
            "session", "registration", "activation"
        ])
        self.assertEqual({item["anonymous_id"] for item in captured}, {subject})
        self.assertEqual({item["session_id"] for item in captured}, {session})
        self.assertEqual(len({item["idempotency_key"] for item in captured}), 3)
        self.assertEqual(
            captured[0]["idempotency_key"],
            telemetry.event_id(subject, "session"),
        )

    def test_real_utm_context_is_preserved_and_absent_context_is_not_fabricated(self):
        context = telemetry.capture_attribution_context(
            {"utm_source": "linkedin"},
            source_page="https://moveready.example/login?utm_campaign=sg49-real&utm_content=post-1",
            referrer="https://moveready.example/?utm_medium=social&utm_term=relocation",
        )
        self.assertEqual(context, {
            "utm_medium": "social",
            "utm_term": "relocation",
            "utm_campaign": "sg49-real",
            "utm_content": "post-1",
            "utm_source": "linkedin",
        })
        self.assertEqual(telemetry.capture_attribution_context({}, "/login", None), {})

    def test_server_secret_is_header_only_and_direct_pii_is_not_in_payload(self):
        subject = telemetry.subject_id_for_login_code("opaque-login-id")
        captured = {}

        def fake_post(url, json=None, headers=None, timeout=None):
            captured.update(url=url, body=json, headers=headers, timeout=timeout)
            return FakeResponse()

        with mock.patch.object(telemetry.requests, "post", side_effect=fake_post):
            result = telemetry.track_event(
                "session",
                subject,
                telemetry.session_id_for_login_code("opaque-login-id"),
                {"utm_source": "linkedin"},
            )

        self.assertTrue(result["sent"])
        self.assertEqual(
            captured["headers"]["X-Ingestion-Key"],
            "server-secret-ingestion-key",
        )
        rendered = json.dumps(captured["body"])
        self.assertNotIn("server-secret-ingestion-key", rendered)
        self.assertNotIn("person@example.com", rendered)
        self.assertNotIn("+965", rendered)

    def test_refresh_or_retry_reuses_same_idempotency_key(self):
        subject = telemetry.subject_id_for_login_code("login-code-retry")
        self.assertEqual(
            telemetry.event_id(subject, "session"),
            telemetry.event_id(subject, "session"),
        )
        self.assertNotEqual(
            telemetry.event_id(subject, "session"),
            telemetry.event_id(subject, "registration"),
        )

    def test_network_failure_is_best_effort_and_does_not_raise(self):
        with mock.patch.object(
            telemetry.requests,
            "post",
            side_effect=TimeoutError("temporary outage"),
        ):
            result = telemetry.track_event(
                "activation",
                telemetry.subject_id_for_login_code("login-code-timeout"),
                telemetry.session_id_for_login_code("login-code-timeout"),
                {},
                attribution_model="last_touch",
            )
        self.assertFalse(result["sent"])
        self.assertEqual(result["reason"], "unavailable")

    def test_contract_probe_is_read_only_get(self):
        captured = {}

        def fake_get(url, headers=None, timeout=None):
            captured.update(url=url, headers=headers, timeout=timeout)
            return FakeResponse(
                200,
                {
                    "workspace_id": telemetry.SPARKGROWTH_WORKSPACE_ID,
                    "allowed_events": ["session", "registration", "activation"],
                    "idempotency_required": True,
                },
            )

        with mock.patch.object(telemetry.requests, "get", side_effect=fake_get):
            result = telemetry.probe_contract()
        self.assertTrue(result["ok"])
        self.assertIn("/ingest/contract/", captured["url"])


class SG49MoveReadyWiringContractTests(unittest.TestCase):
    def test_auth_and_activation_wiring_uses_one_stored_subject_without_backfill(self):
        root = Path(__file__).parents[1]
        auth = (root / "app/routes/account_auth.py").read_text()
        jobs = (root / "app/routes/jobs.py").read_text()
        service = (root / "app/services/sparkgrowth_telemetry.py").read_text()

        self.assertIn('track_event(\n            "session"', auth)
        self.assertIn('track_event(\n                "registration"', auth)
        self.assertIn('"growth_subject_id"', auth)
        self.assertIn('"growth_session_id"', auth)
        self.assertIn("is_first_registration", auth)
        self.assertIn('track_event(\n                    "activation"', jobs)
        self.assertIn('attribution_model="last_touch"', jobs)
        self.assertIn('"milestone": "jobs_profile_configured"', jobs)
        self.assertNotIn("backfill", service.lower())
        self.assertNotIn("relocation_user_profiles", service)
        self.assertNotIn("relocation_user_sessions", service)

    def test_activation_is_only_after_successful_profile_persistence(self):
        root = Path(__file__).parents[1]
        jobs = (root / "app/routes/jobs.py").read_text()
        upsert = jobs.index('.upsert(row, on_conflict="email")')
        activation = jobs.index('"jobs_profile_configured"')
        response = jobs.index('"search_contract": profile_scope_contract(profile)', activation)
        self.assertLess(upsert, activation)
        self.assertLess(activation, response)

    def test_configuration_names_are_server_side_only(self):
        env = (Path(__file__).parents[1] / ".env.example").read_text()
        for name in (
            "SPARKGROWTH_TELEMETRY_ENABLED",
            "SPARKGROWTH_API_BASE",
            "SPARKGROWTH_INGESTION_KEY",
            "SPARKGROWTH_WORKSPACE_ID",
            "SPARKGROWTH_TELEMETRY_TIMEOUT_SECONDS",
        ):
            self.assertIn(name, env)
        self.assertNotIn("NEXT_PUBLIC_SPARKGROWTH", env)


if __name__ == "__main__":
    unittest.main()
