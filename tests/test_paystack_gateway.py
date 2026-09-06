from __future__ import annotations

import hashlib
import hmac

from app.services import paystack_gateway


def test_webhook_signature_validation(monkeypatch):
    monkeypatch.setattr(paystack_gateway, "PAYSTACK_SECRET_KEY", "sk_test_moveready")
    raw = b'{"event":"charge.success","data":{"reference":"MR-test"}}'
    signature = hmac.new(b"sk_test_moveready", raw, hashlib.sha512).hexdigest()
    assert paystack_gateway.verify_webhook_signature(raw, signature) is True
    assert paystack_gateway.verify_webhook_signature(raw + b"x", signature) is False
    assert paystack_gateway.verify_webhook_signature(raw, "bad") is False


def test_paystack_is_not_configured_without_secret(monkeypatch):
    monkeypatch.setattr(paystack_gateway, "PAYSTACK_SECRET_KEY", "")
    assert paystack_gateway.configured() is False
    assert paystack_gateway.verify_webhook_signature(b"{}", "anything") is False
