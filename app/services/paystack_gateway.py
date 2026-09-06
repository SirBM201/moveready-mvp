from __future__ import annotations

import hashlib
import hmac
import json
import os
from typing import Any, Dict, Optional
from urllib.parse import quote

import requests


PAYSTACK_API_BASE = (os.getenv("PAYSTACK_API_BASE") or "https://api.paystack.co").rstrip("/")
PAYSTACK_SECRET_KEY = (os.getenv("PAYSTACK_SECRET_KEY") or "").strip()
PAYSTACK_TIMEOUT_SECONDS = max(3, min(int(os.getenv("PAYSTACK_TIMEOUT_SECONDS") or "20"), 60))


class PaystackConfigurationError(RuntimeError):
    pass


class PaystackAPIError(RuntimeError):
    pass


def configured() -> bool:
    return bool(PAYSTACK_SECRET_KEY)


def _headers() -> Dict[str, str]:
    if not configured():
        raise PaystackConfigurationError("PAYSTACK_SECRET_KEY is not configured")
    return {
        "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _request(method: str, path: str, *, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    try:
        response = requests.request(
            method,
            f"{PAYSTACK_API_BASE}{path}",
            headers=_headers(),
            json=payload,
            timeout=PAYSTACK_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise PaystackAPIError("paystack_network_error") from exc
    try:
        body = response.json()
    except ValueError as exc:
        raise PaystackAPIError(f"paystack_invalid_response:{response.status_code}") from exc
    if response.status_code >= 400 or body.get("status") is not True:
        message = str(body.get("message") or "paystack_request_failed")[:300]
        raise PaystackAPIError(f"paystack_request_failed:{response.status_code}:{message}")
    return body


def initialize_transaction(*, email: str, amount: int, currency: str, reference: str, callback_url: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None, plan_code: Optional[str] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "email": email,
        "amount": str(int(amount)),
        "currency": currency.upper(),
        "reference": reference,
        "metadata": json.dumps(metadata or {}, separators=(",", ":")),
    }
    if callback_url:
        payload["callback_url"] = callback_url
    if plan_code:
        payload["plan"] = plan_code
    return _request("POST", "/transaction/initialize", payload=payload)


def verify_transaction(reference: str) -> Dict[str, Any]:
    safe_reference = quote(reference, safe="-.=")
    return _request("GET", f"/transaction/verify/{safe_reference}")


def verify_webhook_signature(raw_body: bytes, signature: str) -> bool:
    if not configured() or not signature:
        return False
    expected = hmac.new(PAYSTACK_SECRET_KEY.encode("utf-8"), raw_body, hashlib.sha512).hexdigest()
    return hmac.compare_digest(expected, signature.strip())
