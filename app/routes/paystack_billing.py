from __future__ import annotations

import hashlib
import json
import os
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from flask import Blueprint, jsonify, request

from app.routes import account_auth
from app.services import paystack_gateway
from app.services.supabase_client import get_supabase

bp = Blueprint("paystack_billing", __name__)
PRODUCT_CODE = "moveready"
CALLBACK_URL = (os.getenv("PAYSTACK_CALLBACK_URL") or "").strip()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _auth_email() -> Tuple[Optional[str], Optional[str]]:
    try:
        token = account_auth._auth._extract_session_token()
        if not token:
            return None, "session_token_required"
        session, error = account_auth._auth._load_active_session(token)
        if not session:
            return None, error or "invalid_session"
        email = str(session.get("email") or "").strip().lower()
        return (email or None), (None if email else "session_email_missing")
    except Exception:
        return None, "session_validation_failed"


def _one(response: Any) -> Optional[Dict[str, Any]]:
    data = getattr(response, "data", None)
    if isinstance(data, list):
        return data[0] if data else None
    return data if isinstance(data, dict) else None


def _price_for_checkout(price_id: str) -> Optional[Dict[str, Any]]:
    price = _one(get_supabase().table("billing_prices").select("*").eq("id", price_id).eq("active", True).maybe_single().execute())
    if not price:
        return None
    plan = _one(get_supabase().table("billing_plans").select("*").eq("id", price.get("plan_id")).eq("active", True).maybe_single().execute())
    if not plan:
        return None
    product = _one(get_supabase().table("billing_products").select("*").eq("id", plan.get("product_id")).eq("code", PRODUCT_CODE).eq("active", True).maybe_single().execute())
    if not product:
        return None
    price["plan"] = plan
    price["product"] = product
    return price


def _customer(email: str) -> Dict[str, Any]:
    existing = _one(get_supabase().table("billing_customers").select("*").eq("account_email", email).maybe_single().execute())
    if existing:
        return existing
    created = get_supabase().table("billing_customers").insert({"account_email": email}).execute()
    row = _one(created)
    if not row:
        # Concurrent first checkout can race the unique account_email constraint.
        row = _one(get_supabase().table("billing_customers").select("*").eq("account_email", email).maybe_single().execute())
    if not row:
        raise RuntimeError("billing_customer_create_failed")
    return row


def _payment(reference: str) -> Optional[Dict[str, Any]]:
    return _one(get_supabase().table("billing_payments").select("*").eq("provider", "paystack").eq("provider_reference", reference).maybe_single().execute())


def _status(paystack_status: str) -> str:
    value = (paystack_status or "").lower()
    if value == "success": return "succeeded"
    if value in {"failed", "abandoned"}: return "failed"
    if value in {"reversed"}: return "refunded"
    return "pending"


def _sync_verified_payment(reference: str, data: Dict[str, Any]) -> Tuple[bool, str]:
    payment = _payment(reference)
    if not payment:
        return False, "payment_reference_not_initialized_by_moveready"
    remote_reference = str(data.get("reference") or "")
    if remote_reference != reference:
        return False, "reference_mismatch"
    remote_amount = int(data.get("amount") or -1)
    remote_currency = str(data.get("currency") or "").upper()
    if remote_amount != int(payment.get("amount") or -2) or remote_currency != str(payment.get("currency") or "").upper():
        return False, "amount_or_currency_mismatch"
    new_status = _status(str(data.get("status") or ""))
    update: Dict[str, Any] = {"status": new_status, "updated_at": _now(), "metadata": {**(payment.get("metadata") or {}), "paystack_transaction_id": data.get("id"), "gateway_response": data.get("gateway_response"), "channel": data.get("channel")}}
    if new_status == "succeeded":
        update["paid_at"] = data.get("paid_at") or _now()
    get_supabase().table("billing_payments").update(update).eq("id", payment["id"]).execute()
    # Entitlements are intentionally not granted here until MR Billing 03 defines approved plan-feature mappings.
    return True, new_status


def _event_id(raw_body: bytes, event: Dict[str, Any]) -> str:
    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    reference = str(data.get("reference") or data.get("subscription_code") or data.get("id") or "")
    material = f"{event.get('event','unknown')}:{reference}:".encode("utf-8") + raw_body
    return hashlib.sha256(material).hexdigest()


@bp.get("/paystack/status")
def paystack_status():
    return jsonify({"ok": True, "provider": "paystack", "configured": paystack_gateway.configured(), "callback_configured": bool(CALLBACK_URL), "secret_exposed": False})


@bp.post("/paystack/checkout")
def initialize_checkout():
    email, error = _auth_email()
    if not email:
        return jsonify({"ok": False, "error": error or "session_required"}), 401
    if not paystack_gateway.configured():
        return jsonify({"ok": False, "error": "paystack_not_configured"}), 503
    payload = request.get_json(silent=True) or {}
    price_id = str(payload.get("price_id") or "").strip()
    if not price_id:
        return jsonify({"ok": False, "error": "price_id_required"}), 400
    try:
        price = _price_for_checkout(price_id)
        if not price:
            return jsonify({"ok": False, "error": "active_moveready_price_not_found"}), 404
        if str(price.get("billing_interval")) == "one_time":
            plan_code = None
        else:
            provider_prices = (price.get("metadata") or {}).get("provider_prices") or {}
            plan_code = str(provider_prices.get("paystack") or "").strip() or None
            if not plan_code:
                return jsonify({"ok": False, "error": "paystack_plan_code_not_configured_for_recurring_price"}), 409
        customer = _customer(email)
        reference = f"MR-{secrets.token_hex(12)}"
        payment_row = {"customer_id": customer["id"], "price_id": price["id"], "provider": "paystack", "provider_reference": reference, "status": "initialized", "currency": str(price["currency"]).upper(), "amount": int(price["unit_amount"]), "metadata": {"product_code": PRODUCT_CODE, "plan_code": price["plan"]["code"], "billing_interval": price["billing_interval"]}}
        get_supabase().table("billing_payments").insert(payment_row).execute()
        response = paystack_gateway.initialize_transaction(email=email, amount=int(price["unit_amount"]), currency=str(price["currency"]), reference=reference, callback_url=CALLBACK_URL or None, metadata={"moveready_reference": reference, "price_id": price["id"], "plan_code": price["plan"]["code"]}, plan_code=plan_code)
        data = response.get("data") or {}
        return jsonify({"ok": True, "provider": "paystack", "reference": reference, "authorization_url": data.get("authorization_url"), "access_code": data.get("access_code")})
    except paystack_gateway.PaystackAPIError as exc:
        return jsonify({"ok": False, "error": "paystack_initialize_failed", "details": str(exc)}), 502
    except Exception as exc:
        return jsonify({"ok": False, "error": "checkout_initialization_failed", "details": str(exc)}), 503


@bp.get("/paystack/verify/<reference>")
def verify_checkout(reference: str):
    email, error = _auth_email()
    if not email:
        return jsonify({"ok": False, "error": error or "session_required"}), 401
    payment = _payment(reference)
    if not payment:
        return jsonify({"ok": False, "error": "payment_not_found"}), 404
    customer = _one(get_supabase().table("billing_customers").select("account_email").eq("id", payment.get("customer_id")).maybe_single().execute())
    if not customer or str(customer.get("account_email") or "").lower() != email:
        return jsonify({"ok": False, "error": "payment_not_found"}), 404
    try:
        verified = paystack_gateway.verify_transaction(reference)
        ok, status = _sync_verified_payment(reference, verified.get("data") or {})
        if not ok:
            return jsonify({"ok": False, "error": status}), 409
        return jsonify({"ok": True, "reference": reference, "payment_status": status})
    except paystack_gateway.PaystackAPIError as exc:
        return jsonify({"ok": False, "error": "paystack_verify_failed", "details": str(exc)}), 502


@bp.post("/paystack/webhook")
def webhook():
    raw_body = request.get_data(cache=True)
    signature = request.headers.get("x-paystack-signature", "")
    if not paystack_gateway.verify_webhook_signature(raw_body, signature):
        return jsonify({"ok": False, "error": "invalid_paystack_signature"}), 401
    try:
        event = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return jsonify({"ok": False, "error": "invalid_json"}), 400
    provider_event_id = _event_id(raw_body, event)
    existing = _one(get_supabase().table("billing_provider_events").select("id,processing_status").eq("provider", "paystack").eq("provider_event_id", provider_event_id).maybe_single().execute())
    if existing and existing.get("processing_status") in {"processed", "ignored"}:
        return jsonify({"ok": True, "duplicate": True}), 200
    if not existing:
        stored = get_supabase().table("billing_provider_events").insert({"provider": "paystack", "provider_event_id": provider_event_id, "event_type": str(event.get("event") or "unknown"), "signature_verified": True, "processing_status": "received", "payload": event}).execute()
        existing = _one(stored)
    event_type = str(event.get("event") or "")
    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    processing_status = "ignored"
    error_message = None
    if event_type == "charge.success":
        reference = str(data.get("reference") or "")
        ok, result = _sync_verified_payment(reference, data)
        processing_status = "processed" if ok else "failed"
        error_message = None if ok else result
    update = {"processing_status": processing_status, "processed_at": _now(), "error_message": error_message}
    if existing and existing.get("id"):
        get_supabase().table("billing_provider_events").update(update).eq("id", existing["id"]).execute()
    # Return 200 after authentic Paystack events are durably classified; retries remain idempotent.
    return jsonify({"ok": True, "event": event_type, "processing_status": processing_status}), 200
