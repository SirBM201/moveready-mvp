from app.routes import paystack_billing


def test_paystack_status_mapping():
    assert paystack_billing._status("success") == "succeeded"
    assert paystack_billing._status("failed") == "failed"
    assert paystack_billing._status("abandoned") == "failed"
    assert paystack_billing._status("reversed") == "refunded"
    assert paystack_billing._status("pending") == "pending"


def test_event_id_is_deterministic_and_payload_sensitive():
    body = b'{"event":"charge.success","data":{"reference":"MR-123"}}'
    event = {"event": "charge.success", "data": {"reference": "MR-123"}}
    first = paystack_billing._event_id(body, event)
    second = paystack_billing._event_id(body, event)
    changed = paystack_billing._event_id(body + b" ", event)
    assert first == second
    assert first != changed


def test_verified_payment_rejects_reference_mismatch(monkeypatch):
    monkeypatch.setattr(paystack_billing, "_payment", lambda ref: {
        "id": "p1", "provider_reference": ref, "amount": 1000, "currency": "NGN",
        "metadata": {}, "customer_id": "c1", "price_id": "price1"
    })
    ok, reason = paystack_billing._sync_verified_payment("MR-123", {
        "reference": "MR-WRONG", "amount": 1000, "currency": "NGN", "status": "success"
    })
    assert ok is False
    assert reason == "reference_mismatch"


def test_verified_payment_rejects_amount_or_currency_mismatch(monkeypatch):
    monkeypatch.setattr(paystack_billing, "_payment", lambda ref: {
        "id": "p1", "provider_reference": ref, "amount": 1000, "currency": "NGN",
        "metadata": {}, "customer_id": "c1", "price_id": "price1"
    })
    ok, reason = paystack_billing._sync_verified_payment("MR-123", {
        "reference": "MR-123", "amount": 999, "currency": "NGN", "status": "success"
    })
    assert ok is False
    assert reason == "amount_or_currency_mismatch"
