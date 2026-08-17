from __future__ import annotations

import io
import json
import logging
import socket
import unittest
import urllib.error
from unittest import mock

from app.services import email_delivery


BASE_ENV = {
    "EMAIL_OTP_DELIVERY_ENABLED": "true",
    "EMAIL_OTP_PROVIDER": "mailtrap_sandbox",
    "EMAIL_OTP_APP_NAME": "MoveReady",
    "EMAIL_OTP_LOGIN_URL": "https://example.com/login",
    "EMAIL_OTP_FROM": "MoveReady <login@example.com>",
    "EMAIL_OTP_REPLY_TO": "Support <support@example.com>",
    "MAILTRAP_SANDBOX_API_TOKEN": "sandbox-token-secret",
    "MAILTRAP_SANDBOX_ID": "7654321",
}


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class EmailDeliveryTests(unittest.TestCase):
    def test_sandbox_status_and_https_request_contract(self):
        captured = {}

        def fake_urlopen(request, timeout=0):
            captured["url"] = request.full_url
            captured["authorization"] = request.get_header("Authorization")
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            captured["timeout"] = timeout
            return FakeResponse({"message_ids": ["sandbox-message-1"]})

        with mock.patch.dict(email_delivery.os.environ, BASE_ENV, clear=True):
            status = email_delivery.email_delivery_status()
            with mock.patch.object(email_delivery.urllib.request, "urlopen", side_effect=fake_urlopen):
                result = email_delivery.deliver_login_code("owner@example.com", "123456", 10)

        self.assertTrue(status["enabled"])
        self.assertTrue(status["configured"])
        self.assertEqual(status["provider"], "mailtrap_sandbox")
        self.assertEqual(status["transport"], "https_api")
        self.assertEqual(status["missing_configuration"], [])
        self.assertEqual(captured["url"], "https://sandbox.api.mailtrap.io/api/send/7654321")
        self.assertEqual(captured["authorization"], "Bearer sandbox-token-secret")
        self.assertEqual(captured["timeout"], 20)
        self.assertEqual(captured["payload"]["to"], [{"email": "owner@example.com"}])
        self.assertEqual(captured["payload"]["reply_to"]["email"], "support@example.com")
        self.assertIn("123456", captured["payload"]["text"])
        self.assertTrue(result["ok"])
        self.assertEqual(result["provider"], "mailtrap_sandbox")

    def test_untrusted_sandbox_endpoint_is_rejected_before_network(self):
        env = {
            **BASE_ENV,
            "MAILTRAP_SANDBOX_API_URL": "https://attacker.example/api/send/7654321",
        }
        with mock.patch.dict(email_delivery.os.environ, env, clear=True):
            with mock.patch.object(email_delivery.urllib.request, "urlopen") as urlopen:
                status = email_delivery.email_delivery_status()
                result = email_delivery.deliver_login_code("owner@example.com", "123456", 10)

        self.assertFalse(status["configured"])
        self.assertIn("MAILTRAP_SANDBOX_ID_OR_VALID_API_URL", status["missing_configuration"])
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "email_delivery_not_configured")
        urlopen.assert_not_called()

    def test_http_failure_diagnostics_redact_secrets(self):
        leaked_values = [
            "sandbox-token-secret",
            "owner@example.com",
            "123456",
            "provider-private-response",
        ]
        error = urllib.error.HTTPError(
            "https://sandbox.api.mailtrap.io/api/send/7654321",
            401,
            "Unauthorized provider-private-response",
            {},
            io.BytesIO(b"provider-private-response owner@example.com 123456 sandbox-token-secret"),
        )

        with mock.patch.dict(email_delivery.os.environ, BASE_ENV, clear=True):
            with self.assertLogs(email_delivery.logger, level=logging.WARNING) as logs:
                with mock.patch.object(email_delivery.urllib.request, "urlopen", side_effect=error):
                    result = email_delivery.deliver_login_code("owner@example.com", "123456", 10)

        rendered = json.dumps(result) + "\n" + "\n".join(logs.output)
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "mailtrap_sandbox_http_401")
        self.assertEqual(result["detail"], "Mailtrap API returned HTTP 401.")
        for value in leaked_values:
            self.assertNotIn(value, rendered)

    def test_timeout_diagnostic_is_bounded_and_redacted(self):
        timeout = urllib.error.URLError(
            socket.timeout("owner@example.com 123456 sandbox-token-secret")
        )
        with mock.patch.dict(email_delivery.os.environ, BASE_ENV, clear=True):
            with self.assertLogs(email_delivery.logger, level=logging.WARNING) as logs:
                with mock.patch.object(email_delivery.urllib.request, "urlopen", side_effect=timeout):
                    result = email_delivery.deliver_login_code("owner@example.com", "123456", 10)

        rendered = json.dumps(result) + "\n" + "\n".join(logs.output)
        self.assertEqual(result["status"], "mailtrap_sandbox_timeout")
        self.assertEqual(result["detail"], "Mailtrap API request timed out.")
        self.assertNotIn("owner@example.com", rendered)
        self.assertNotIn("123456", rendered)
        self.assertNotIn("sandbox-token-secret", rendered)

    def test_production_mailtrap_path_and_reply_to_remain_supported(self):
        env = {
            **BASE_ENV,
            "EMAIL_OTP_PROVIDER": "mailtrap",
            "MAILTRAP_API_TOKEN": "production-token",
            "MAILTRAP_API_URL": "https://send.api.mailtrap.io/api/send",
        }
        captured = {}

        def fake_urlopen(request, timeout=0):
            captured["url"] = request.full_url
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse({"message_ids": ["production-message-1"]})

        with mock.patch.dict(email_delivery.os.environ, env, clear=True):
            with mock.patch.object(email_delivery.urllib.request, "urlopen", side_effect=fake_urlopen):
                result = email_delivery.deliver_login_code("owner@example.com", "123456", 10)

        self.assertTrue(result["ok"])
        self.assertEqual(result["provider"], "mailtrap")
        self.assertEqual(captured["url"], "https://send.api.mailtrap.io/api/send")
        self.assertEqual(captured["payload"]["reply_to"]["email"], "support@example.com")


if __name__ == "__main__":
    unittest.main()
