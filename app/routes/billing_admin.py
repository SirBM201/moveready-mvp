from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

from app.core.config import COMMERCIAL_QUOTES_ENABLED
from app.services.supabase_client import get_supabase
from app.utils.admin_auth import require_admin_access


bp = Blueprint("billing_admin", __name__)

QUOTE_STATUSES = {
    "draft",
    "sent",
    "accepted",
    "declined",
    "expired",
    "cancelled",
    "payment_pending",
    "paid",
    "fulfilled",
    "refunded",
    "disputed",
}

PROVIDER_TYPES = {
    "courier",
    "insurance",
    "legalization",
    "translation",
    "expert_review",
    "admission_support",
    "accommodation",
    "airport_pickup",
    "settlement",
    "travel_booking",
    "transport",
    "telecom",
    "other",
}

PUBLICATION_CHECKS = (
    "privacy_reviewed",
    "pricing_reviewed",
    "refund_policy_reviewed",
    "sensitive_document_handling_reviewed",
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _text(value: Any, limit: int = 500) -> Optional[str]:
    cleaned = str(value or "").strip()
    return cleaned[:limit] or None


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _money(value: Any, default: Decimal = Decimal("0.00")) -> Decimal:
    try:
        parsed = Decimal(str(value if value not in (None, "") else default)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError):
        parsed = default
    return max(parsed, Decimal("0.00"))


def _string_list(value: Any, limit: int = 30) -> List[str]:
    if isinstance(value, str):
        raw = [item.strip() for item in value.replace("\r", "").split("\n")]
    elif isinstance(value, list):
        raw = value
    else:
        raw = []
    output: List[str] = []
    for item in raw:
        cleaned = _text(item, 500)
        if cleaned and cleaned not in output:
            output.append(cleaned)
        if len(output) >= limit:
            break
    return output


def _quote_ref() -> str:
    return f"MRQ-{_now().strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"


def _event(quote: Dict[str, Any], event_type: str, *, status: str = "recorded", actor: str = "admin", payload: Optional[Dict[str, Any]] = None) -> None:
    try:
        get_supabase().table("relocation_payment_events").insert(
            {
                "quote_id": quote.get("id"),
                "event_type": event_type,
                "event_status": status,
                "amount": quote.get("total_amount"),
                "currency": quote.get("currency"),
                "payment_provider": quote.get("payment_provider"),
                "payment_reference": quote.get("payment_reference"),
                "actor_type": "admin",
                "actor_reference": actor,
                "event_payload": payload or {},
            }
        ).execute()
    except Exception:
        pass


def _service_request(request_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not request_id:
        return None
    response = (
        get_supabase()
        .table("relocation_service_interest_requests")
        .select("*")
        .eq("id", request_id)
        .maybe_single()
        .execute()
    )
    return response.data


def _provider(provider_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not provider_id:
        return None
    response = (
        get_supabase()
        .table("relocation_partner_applications")
        .select("*")
        .eq("id", provider_id)
        .maybe_single()
        .execute()
    )
    return response.data


def _provider_handoff_errors(provider: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if str(provider.get("status") or "") != "approved":
        errors.append("provider_status_not_approved")
    if not provider.get("consent_to_contact"):
        errors.append("provider_contact_consent_missing")
    for field in PUBLICATION_CHECKS:
        if not provider.get(field):
            errors.append(f"{field}_required")
    if not _text(provider.get("service_summary"), 1200):
        errors.append("provider_service_summary_required")
    if not _text(provider.get("pricing_notes"), 800):
        errors.append("provider_pricing_notes_required")
    return errors


def _safe_quote(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row.get("id"),
        "quote_ref": row.get("quote_ref"),
        "service_request_id": row.get("service_request_id"),
        "provider_application_id": row.get("provider_application_id"),
        "full_name": row.get("full_name"),
        "email": row.get("email"),
        "phone": row.get("phone"),
        "service_slug": row.get("service_slug"),
        "service_title": row.get("service_title"),
        "provider_name": row.get("provider_name"),
        "currency": row.get("currency"),
        "subtotal_amount": row.get("subtotal_amount"),
        "platform_fee_amount": row.get("platform_fee_amount"),
        "total_amount": row.get("total_amount"),
        "scope_summary": row.get("scope_summary"),
        "deliverables": row.get("deliverables") or [],
        "exclusions": row.get("exclusions") or [],
        "refund_terms": row.get("refund_terms"),
        "status": row.get("status"),
        "payment_provider": row.get("payment_provider"),
        "payment_reference": row.get("payment_reference"),
        "checkout_url": row.get("checkout_url"),
        "expires_at": row.get("expires_at"),
        "sent_at": row.get("sent_at"),
        "accepted_at": row.get("accepted_at"),
        "paid_at": row.get("paid_at"),
        "fulfilled_at": row.get("fulfilled_at"),
        "created_by": row.get("created_by"),
        "source_page": row.get("source_page"),
        "metadata": row.get("metadata") or {},
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


@bp.get("/commercial-quotes")
@require_admin_access
def commercial_quotes():
    status = _text(request.args.get("status"), 40)
    service_slug = _text(request.args.get("service_slug"), 120)
    email = _text(request.args.get("email"), 255)
    try:
        limit = max(1, min(int(request.args.get("limit") or 75), 100))
    except (TypeError, ValueError):
        limit = 75

    try:
        query = (
            get_supabase()
            .table("relocation_commercial_quotes")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
        )
        if status:
            query = query.eq("status", status)
        if service_slug:
            query = query.eq("service_slug", service_slug)
        if email:
            query = query.eq("email", email.lower())
        response = query.execute()
        rows = [_safe_quote(row) for row in (response.data or [])]
        return jsonify({"ok": True, "quote_count": len(rows), "commercial_quotes": rows})
    except Exception as exc:
        return jsonify({"ok": False, "error": "commercial_quotes_unavailable", "details": str(exc)}), 503


@bp.post("/commercial-quotes")
@require_admin_access
def create_commercial_quote():
    if not COMMERCIAL_QUOTES_ENABLED:
        return jsonify({"ok": False, "error": "commercial_quotes_disabled"}), 503

    payload = request.get_json(silent=True) or {}
    request_id = _text(payload.get("service_request_id"), 80)
    provider_id = _text(payload.get("provider_application_id"), 80)

    try:
        source_request = _service_request(request_id)
        provider = _provider(provider_id)
    except Exception as exc:
        return jsonify({"ok": False, "error": "quote_source_lookup_failed", "details": str(exc)}), 503

    if request_id and not source_request:
        return jsonify({"ok": False, "error": "service_request_not_found"}), 404
    if provider_id and not provider:
        return jsonify({"ok": False, "error": "provider_not_found"}), 404
    if provider:
        handoff_errors = _provider_handoff_errors(provider)
        if handoff_errors:
            return jsonify({"ok": False, "error": "provider_handoff_not_ready", "provider_errors": handoff_errors}), 409

    email = _text(payload.get("email"), 255) or _text((source_request or {}).get("email"), 255)
    phone = _text(payload.get("phone"), 80) or _text((source_request or {}).get("phone"), 80)
    full_name = _text(payload.get("full_name"), 180) or _text((source_request or {}).get("full_name"), 180)
    service_slug = _text(payload.get("service_slug"), 120) or _text((source_request or {}).get("service_slug"), 120)
    service_title = _text(payload.get("service_title"), 180) or _text((source_request or {}).get("service_title"), 180)
    scope_summary = _text(payload.get("scope_summary"), 2000)
    refund_terms = _text(payload.get("refund_terms"), 1600)

    if not email:
        return jsonify({"ok": False, "error": "quote_email_required"}), 400
    if not service_slug or not service_title:
        return jsonify({"ok": False, "error": "quote_service_required"}), 400
    if not scope_summary:
        return jsonify({"ok": False, "error": "scope_summary_required"}), 400
    if not refund_terms:
        return jsonify({"ok": False, "error": "refund_terms_required"}), 400

    subtotal = _money(payload.get("subtotal_amount"))
    platform_fee = _money(payload.get("platform_fee_amount"))
    total = subtotal + platform_fee
    currency = (_text(payload.get("currency"), 10) or "USD").upper()
    if len(currency) != 3:
        return jsonify({"ok": False, "error": "currency_must_be_three_letters"}), 400
    if total <= 0:
        return jsonify({"ok": False, "error": "positive_quote_total_required"}), 400

    send_now = _bool(payload.get("send_now"))
    expires_days = max(1, min(int(payload.get("expires_days") or 14), 90))
    status = "sent" if send_now else "draft"
    row = {
        "quote_ref": _quote_ref(),
        "service_request_id": request_id,
        "provider_application_id": provider_id,
        "full_name": full_name,
        "email": email.lower(),
        "phone": phone,
        "service_slug": service_slug,
        "service_title": service_title,
        "provider_name": _text((provider or {}).get("business_name"), 180) or _text(payload.get("provider_name"), 180),
        "currency": currency,
        "subtotal_amount": float(subtotal),
        "platform_fee_amount": float(platform_fee),
        "total_amount": float(total),
        "scope_summary": scope_summary,
        "deliverables": _string_list(payload.get("deliverables")),
        "exclusions": _string_list(payload.get("exclusions")),
        "refund_terms": refund_terms,
        "status": status,
        "payment_provider": _text(payload.get("payment_provider"), 80),
        "checkout_url": _text(payload.get("checkout_url"), 500),
        "expires_at": (_now() + timedelta(days=expires_days)).isoformat(),
        "sent_at": _now_iso() if send_now else None,
        "created_by": _text(payload.get("created_by"), 180) or "MoveReady admin",
        "source_page": _text(payload.get("source_page"), 240) or "/admin#commercial-quotes",
        "metadata": {
            "official_fee_included": _bool(payload.get("official_fee_included")),
            "provider_handoff_checked": bool(provider),
            "quote_notice_confirmed": _bool(payload.get("quote_notice_confirmed")),
        },
    }

    if not row["metadata"]["quote_notice_confirmed"]:
        return jsonify({"ok": False, "error": "commercial_quote_notice_confirmation_required"}), 400

    try:
        response = get_supabase().table("relocation_commercial_quotes").insert(row).execute()
        stored = (response.data or [None])[0]
        if not stored:
            return jsonify({"ok": False, "error": "quote_not_stored"}), 503
        _event(stored, "quote_sent" if send_now else "quote_created", payload={"service_request_id": request_id})

        if source_request and send_now:
            try:
                get_supabase().table("relocation_service_interest_requests").update({"status": "contacted"}).eq("id", request_id).execute()
            except Exception:
                pass

        return jsonify({"ok": True, "commercial_quote": _safe_quote(stored)})
    except Exception as exc:
        return jsonify({"ok": False, "error": "commercial_quote_create_failed", "details": str(exc)}), 503


@bp.patch("/commercial-quotes/<quote_id>")
@require_admin_access
def update_commercial_quote(quote_id: str):
    payload = request.get_json(silent=True) or {}
    try:
        current_response = (
            get_supabase()
            .table("relocation_commercial_quotes")
            .select("*")
            .eq("id", quote_id)
            .maybe_single()
            .execute()
        )
        current = current_response.data
        if not current:
            return jsonify({"ok": False, "error": "quote_not_found"}), 404

        updates: Dict[str, Any] = {}
        status = _text(payload.get("status"), 40)
        if status:
            if status not in QUOTE_STATUSES:
                return jsonify({"ok": False, "error": "invalid_quote_status", "allowed_statuses": sorted(QUOTE_STATUSES)}), 400
            updates["status"] = status
            if status == "sent":
                updates["sent_at"] = _now_iso()
            elif status == "paid":
                updates["paid_at"] = _now_iso()
            elif status == "fulfilled":
                updates["fulfilled_at"] = _now_iso()

        for field, limit in (
            ("service_title", 180),
            ("provider_name", 180),
            ("scope_summary", 2000),
            ("refund_terms", 1600),
            ("payment_provider", 80),
            ("payment_reference", 180),
            ("checkout_url", 500),
        ):
            if field in payload:
                updates[field] = _text(payload.get(field), limit)

        if "deliverables" in payload:
            updates["deliverables"] = _string_list(payload.get("deliverables"))
        if "exclusions" in payload:
            updates["exclusions"] = _string_list(payload.get("exclusions"))

        money_changed = any(field in payload for field in ("subtotal_amount", "platform_fee_amount"))
        if money_changed:
            if current.get("status") not in {"draft", "sent"}:
                return jsonify({"ok": False, "error": "accepted_or_paid_quote_amount_cannot_change"}), 409
            subtotal = _money(payload.get("subtotal_amount"), _money(current.get("subtotal_amount")))
            platform_fee = _money(payload.get("platform_fee_amount"), _money(current.get("platform_fee_amount")))
            updates.update(
                {
                    "subtotal_amount": float(subtotal),
                    "platform_fee_amount": float(platform_fee),
                    "total_amount": float(subtotal + platform_fee),
                }
            )

        if not updates:
            return jsonify({"ok": False, "error": "no_update_fields"}), 400

        response = (
            get_supabase()
            .table("relocation_commercial_quotes")
            .update(updates)
            .eq("id", quote_id)
            .execute()
        )
        updated = (response.data or [None])[0]
        if not updated:
            return jsonify({"ok": False, "error": "quote_not_found"}), 404
        _event(updated, "quote_updated", payload={"updated_fields": sorted(updates.keys())})
        return jsonify({"ok": True, "commercial_quote": _safe_quote(updated)})
    except Exception as exc:
        return jsonify({"ok": False, "error": "commercial_quote_update_failed", "details": str(exc)}), 503


@bp.post("/commercial-quotes/<quote_id>/mark-paid")
@require_admin_access
def mark_quote_paid(quote_id: str):
    payload = request.get_json(silent=True) or {}
    payment_reference = _text(payload.get("payment_reference"), 180)
    payment_provider = _text(payload.get("payment_provider"), 80)
    if not payment_reference or not payment_provider:
        return jsonify({"ok": False, "error": "payment_provider_and_reference_required"}), 400

    try:
        current_response = (
            get_supabase()
            .table("relocation_commercial_quotes")
            .select("*")
            .eq("id", quote_id)
            .maybe_single()
            .execute()
        )
        current = current_response.data
        if not current:
            return jsonify({"ok": False, "error": "quote_not_found"}), 404
        if current.get("status") not in {"accepted", "payment_pending", "paid"}:
            return jsonify({"ok": False, "error": "quote_not_ready_for_payment_confirmation", "status": current.get("status")}), 409

        expected = _money(current.get("total_amount"))
        received = _money(payload.get("amount"), expected)
        if received != expected:
            return jsonify(
                {
                    "ok": False,
                    "error": "payment_amount_mismatch",
                    "expected_amount": float(expected),
                    "received_amount": float(received),
                    "currency": current.get("currency"),
                }
            ), 409

        response = (
            get_supabase()
            .table("relocation_commercial_quotes")
            .update(
                {
                    "status": "paid",
                    "payment_reference": payment_reference,
                    "payment_provider": payment_provider,
                    "paid_at": _now_iso(),
                }
            )
            .eq("id", quote_id)
            .execute()
        )
        updated = (response.data or [None])[0]
        _event(updated or current, "payment_confirmed", status="confirmed", payload={"confirmation_mode": "admin_verified"})
        return jsonify({"ok": True, "commercial_quote": _safe_quote(updated or current)})
    except Exception as exc:
        return jsonify({"ok": False, "error": "payment_confirmation_failed", "details": str(exc)}), 503


@bp.patch("/provider-publication/<provider_id>")
@require_admin_access
def update_provider_publication(provider_id: str):
    payload = request.get_json(silent=True) or {}
    try:
        current_response = (
            get_supabase()
            .table("relocation_partner_applications")
            .select("*")
            .eq("id", provider_id)
            .maybe_single()
            .execute()
        )
        current = current_response.data
        if not current:
            return jsonify({"ok": False, "error": "provider_not_found"}), 404

        updates: Dict[str, Any] = {}
        if "provider_type" in payload:
            provider_type = _text(payload.get("provider_type"), 80)
            if provider_type not in PROVIDER_TYPES:
                return jsonify({"ok": False, "error": "invalid_provider_type", "allowed_provider_types": sorted(PROVIDER_TYPES)}), 400
            updates["provider_type"] = provider_type

        for field in PUBLICATION_CHECKS:
            if field in payload:
                updates[field] = _bool(payload.get(field))

        for field, limit in (
            ("affiliate_disclosure", 1200),
            ("handoff_terms", 1600),
            ("public_notes", 1200),
            ("pricing_notes", 800),
            ("internal_notes", 1200),
        ):
            if field in payload:
                updates[field] = _text(payload.get(field), limit)

        if "affiliate_relationship" in payload:
            updates["affiliate_relationship"] = _bool(payload.get("affiliate_relationship"))

        if "public_listing_enabled" in payload:
            enable = _bool(payload.get("public_listing_enabled"))
            candidate = {**current, **updates, "public_listing_enabled": enable}
            if enable:
                errors = _provider_handoff_errors(candidate)
                if candidate.get("affiliate_relationship") and not _text(candidate.get("affiliate_disclosure"), 1200):
                    errors.append("affiliate_disclosure_required")
                if errors:
                    return jsonify({"ok": False, "error": "provider_publication_not_ready", "provider_errors": errors}), 409
                updates["approved_at"] = current.get("approved_at") or _now_iso()
                updates["approved_by"] = _text(payload.get("approved_by"), 180) or "MoveReady admin"
            updates["public_listing_enabled"] = enable

        if not updates:
            return jsonify({"ok": False, "error": "no_update_fields"}), 400

        response = (
            get_supabase()
            .table("relocation_partner_applications")
            .update(updates)
            .eq("id", provider_id)
            .execute()
        )
        updated = (response.data or [None])[0]
        return jsonify({"ok": True, "partner_application": updated})
    except Exception as exc:
        return jsonify({"ok": False, "error": "provider_publication_update_failed", "details": str(exc)}), 503
