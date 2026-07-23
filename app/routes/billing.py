from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from flask import Blueprint, jsonify, request

from app.core.config import COMMERCIAL_QUOTES_ENABLED, PAYMENT_LINKS_ENABLED
from app.routes import account_auth
from app.services.supabase_client import get_supabase


bp = Blueprint("billing", __name__)

QUOTE_TERMS_VERSION = "moveready-commercial-quote-2026-07-23-v1"
REQUIRED_ACCEPTANCE_CONFIRMATIONS = (
    "scope_reviewed",
    "deliverables_reviewed",
    "exclusions_reviewed",
    "total_price_reviewed",
    "expiry_reviewed",
    "refund_terms_reviewed",
    "no_outcome_guarantee_understood",
    "payment_is_separate_understood",
)

CATALOG: List[Dict[str, Any]] = [
    {
        "slug": "readiness_report",
        "title": "Route readiness report",
        "pricing_mode": "quote_required",
        "summary": "A route-specific readiness report with evidence gaps, funds pressure, risk labels, source status, and next actions.",
    },
    {
        "slug": "expert_review",
        "title": "Expert or document review",
        "pricing_mode": "quote_required",
        "summary": "Manual review of route evidence, refusal risk, proof of funds, startup evidence, study plans, or document gaps.",
    },
    {
        "slug": "admission_support",
        "title": "Admission and scholarship support",
        "pricing_mode": "quote_required",
        "summary": "Programme research, application preparation, statement review, scholarship preparation, and study-visa document support.",
    },
    {
        "slug": "travel_booking",
        "title": "Travel booking support",
        "pricing_mode": "quote_required",
        "summary": "Neutral itinerary, accommodation, transport, insurance, and approved-provider handoff support after trip-readiness checks.",
    },
    {
        "slug": "legalization",
        "title": "Translation, notarization, apostille, or legalization support",
        "pricing_mode": "quote_required",
        "summary": "Document handling support after the receiving authority confirms the required authentication path.",
    },
    {
        "slug": "settlement",
        "title": "Post-arrival settlement support",
        "pricing_mode": "quote_required",
        "summary": "Accommodation, pickup, registration, banking, tax, school, transport, connectivity, and first-arrival support.",
    },
]

ALLOWED_QUOTE_STATUSES = {
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


def _text(value: Any, limit: int = 500) -> Optional[str]:
    cleaned = str(value or "").strip()
    return cleaned[:limit] or None


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


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _expired(row: Dict[str, Any]) -> bool:
    value = row.get("expires_at")
    if not value:
        return False
    try:
        expires = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return expires < datetime.now(timezone.utc)
    except Exception:
        return False


def _as_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [str(item)[:500] for item in value if str(item or "").strip()][:30]


def _acceptance_metadata(row: Dict[str, Any]) -> Dict[str, Any]:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    acceptance = metadata.get("quote_acceptance") if isinstance(metadata.get("quote_acceptance"), dict) else {}
    return acceptance


def _public_quote(row: Dict[str, Any]) -> Dict[str, Any]:
    status = str(row.get("status") or "draft")
    expired = _expired(row)
    effective_status = "expired" if expired and status in {"draft", "sent"} else status
    checkout_available = bool(
        PAYMENT_LINKS_ENABLED
        and row.get("checkout_url")
        and effective_status in {"accepted", "payment_pending"}
    )
    acceptance = _acceptance_metadata(row)
    return {
        "id": row.get("id"),
        "quote_ref": row.get("quote_ref"),
        "service_request_id": row.get("service_request_id"),
        "service_slug": row.get("service_slug"),
        "service_title": row.get("service_title"),
        "provider_name": row.get("provider_name"),
        "currency": row.get("currency") or "USD",
        "subtotal_amount": row.get("subtotal_amount") or 0,
        "platform_fee_amount": row.get("platform_fee_amount") or 0,
        "total_amount": row.get("total_amount") or 0,
        "scope_summary": row.get("scope_summary"),
        "deliverables": _as_list(row.get("deliverables")),
        "exclusions": _as_list(row.get("exclusions")),
        "refund_terms": row.get("refund_terms"),
        "status": effective_status,
        "payment_provider": row.get("payment_provider"),
        "checkout_available": checkout_available,
        "checkout_url": row.get("checkout_url") if checkout_available else None,
        "expires_at": row.get("expires_at"),
        "sent_at": row.get("sent_at"),
        "accepted_at": row.get("accepted_at"),
        "paid_at": row.get("paid_at"),
        "fulfilled_at": row.get("fulfilled_at"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "acceptance_required": effective_status == "sent",
        "acceptance_terms_version": QUOTE_TERMS_VERSION,
        "acceptance_confirmations": list(REQUIRED_ACCEPTANCE_CONFIRMATIONS),
        "acceptance_recorded": bool(acceptance.get("accepted")),
        "commercial_notice": "This quote describes a paid service. It does not guarantee visa, admission, scholarship, job, booking inventory, refund, provider performance, border entry, or approval.",
    }


def _quote_for_account(quote_ref: str, email: str) -> Optional[Dict[str, Any]]:
    response = (
        get_supabase()
        .table("relocation_commercial_quotes")
        .select("*")
        .eq("quote_ref", quote_ref)
        .eq("email", email)
        .maybe_single()
        .execute()
    )
    return response.data


def _record_event(quote: Dict[str, Any], event_type: str, *, status: str = "recorded", payload: Optional[Dict[str, Any]] = None) -> None:
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
                "actor_type": "user",
                "actor_reference": quote.get("email"),
                "event_payload": payload or {},
            }
        ).execute()
    except Exception:
        pass


def _validated_acceptance(payload: Dict[str, Any]) -> Tuple[Optional[Dict[str, bool]], Optional[str]]:
    if payload.get("accept_terms") is not True:
        return None, "quote_terms_acceptance_required"
    if _text(payload.get("terms_version"), 120) != QUOTE_TERMS_VERSION:
        return None, "quote_terms_version_mismatch"
    confirmations = payload.get("confirmations") if isinstance(payload.get("confirmations"), dict) else {}
    missing = [key for key in REQUIRED_ACCEPTANCE_CONFIRMATIONS if confirmations.get(key) is not True]
    if missing:
        return None, f"quote_acceptance_confirmations_missing:{','.join(missing)}"
    return {key: True for key in REQUIRED_ACCEPTANCE_CONFIRMATIONS}, None


@bp.get("/status")
def billing_status():
    return jsonify(
        {
            "ok": True,
            "commercial_quotes_enabled": COMMERCIAL_QUOTES_ENABLED,
            "payment_links_enabled": PAYMENT_LINKS_ENABLED,
            "checkout_mode": "admin_approved_payment_link" if PAYMENT_LINKS_ENABLED else "disabled_until_payment_setup",
            "quote_storage_migration": "023_provider_publication_and_commercial_quotes.sql",
            "private_table_hardening_migration": "024_private_backend_tables_rls.sql",
            "quote_terms_version": QUOTE_TERMS_VERSION,
            "safety_controls": [
                "No payment before scope, total price, provider, expiry, exclusions, and refund terms are shown.",
                "Quote acceptance requires explicit confirmation of scope, deliverables, exclusions, total, expiry, refund terms, no-guarantee notice, and separate payment.",
                "Payment links remain disabled until an approved payment process is configured.",
                "Official application fees, government charges, provider fees, and MoveReady fees must not be misrepresented as one another.",
                "No quote or payment can guarantee approval, selection, admission, employment, boarding, entry, or provider performance.",
            ],
        }
    )


@bp.get("/catalog")
def billing_catalog():
    return jsonify(
        {
            "ok": True,
            "catalog": CATALOG,
            "pricing_rule": "Service-specific pricing is issued only after scope review. No public amount should be presented as an official government, university, airline, hotel, or provider fee unless the source and date are stated.",
        }
    )


@bp.post("/quote-requests")
def create_quote_request():
    if not COMMERCIAL_QUOTES_ENABLED:
        return jsonify({"ok": False, "error": "commercial_quotes_disabled"}), 503

    payload = request.get_json(silent=True) or {}
    email, auth_error = _auth_email()
    supplied_email = _text(payload.get("email"), 255)
    email = email or (supplied_email.lower() if supplied_email else None)
    phone = _text(payload.get("phone"), 80)
    consent = bool(payload.get("consent_to_contact"))
    service_slug = _text(payload.get("service_slug"), 120)

    if not email and not phone:
        return jsonify({"ok": False, "error": auth_error or "contact_required"}), 400
    if not consent:
        return jsonify({"ok": False, "error": "contact_consent_required"}), 400
    if not service_slug:
        return jsonify({"ok": False, "error": "service_slug_required"}), 400

    catalog_item = next((item for item in CATALOG if item["slug"] == service_slug), None)
    service_title = _text(payload.get("service_title"), 180) or (catalog_item or {}).get("title") or service_slug.replace("_", " ").title()
    row = {
        "service_slug": service_slug,
        "service_title": service_title,
        "full_name": _text(payload.get("full_name"), 180),
        "email": email,
        "phone": phone,
        "preferred_channel": _text(payload.get("preferred_channel"), 40) or "email",
        "current_country": _text(payload.get("current_country"), 120),
        "target_country": _text(payload.get("target_country"), 120),
        "route_or_goal": _text(payload.get("route_or_goal"), 180),
        "message": _text(payload.get("message"), 1200) or "Commercial quote requested.",
        "consent_to_contact": True,
        "source_page": _text(payload.get("source_page"), 240) or "/billing",
        "metadata": {
            "commercial_quote_requested": True,
            "identity_source": "verified_session" if auth_error is None else "submitted_contact",
            "requested_at": _iso_now(),
        },
    }

    try:
        response = get_supabase().table("relocation_service_interest_requests").insert(row).execute()
        stored = (response.data or [None])[0]
        return jsonify(
            {
                "ok": True,
                "stored": bool(stored),
                "quote_request": stored,
                "next_step": "MoveReady admin must review the requested scope before issuing a commercial quote.",
            }
        )
    except Exception as exc:
        return jsonify({"ok": False, "error": "quote_request_storage_unavailable", "details": str(exc)}), 503


@bp.get("/quotes")
def my_quotes():
    email, error = _auth_email()
    if not email:
        return jsonify({"ok": False, "error": error or "session_required"}), 401

    try:
        response = (
            get_supabase()
            .table("relocation_commercial_quotes")
            .select("*")
            .eq("email", email)
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )
        rows = [_public_quote(row) for row in (response.data or [])]
        return jsonify({"ok": True, "account_email": email, "quote_count": len(rows), "quotes": rows})
    except Exception as exc:
        return jsonify({"ok": False, "error": "commercial_quotes_unavailable", "details": str(exc)}), 503


@bp.get("/quotes/<quote_ref>")
def quote_detail(quote_ref: str):
    email, error = _auth_email()
    if not email:
        return jsonify({"ok": False, "error": error or "session_required"}), 401
    try:
        row = _quote_for_account(quote_ref, email)
        if not row:
            return jsonify({"ok": False, "error": "quote_not_found"}), 404
        return jsonify({"ok": True, "quote": _public_quote(row)})
    except Exception as exc:
        return jsonify({"ok": False, "error": "quote_lookup_failed", "details": str(exc)}), 503


@bp.post("/quotes/<quote_ref>/accept")
def accept_quote(quote_ref: str):
    email, error = _auth_email()
    if not email:
        return jsonify({"ok": False, "error": error or "session_required"}), 401

    payload = request.get_json(silent=True) or {}
    confirmations, validation_error = _validated_acceptance(payload)
    if validation_error:
        error_code, _, missing_text = validation_error.partition(":")
        response: Dict[str, Any] = {
            "ok": False,
            "error": error_code,
            "terms_version": QUOTE_TERMS_VERSION,
            "required_confirmations": list(REQUIRED_ACCEPTANCE_CONFIRMATIONS),
        }
        if missing_text:
            response["missing_confirmations"] = missing_text.split(",")
        return jsonify(response), 400

    try:
        row = _quote_for_account(quote_ref, email)
        if not row:
            return jsonify({"ok": False, "error": "quote_not_found"}), 404
        if _expired(row):
            return jsonify({"ok": False, "error": "quote_expired"}), 409
        if row.get("status") not in {"sent", "accepted"}:
            return jsonify({"ok": False, "error": "quote_not_open_for_acceptance", "status": row.get("status")}), 409

        accepted_at = _iso_now()
        current_metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        acceptance_record = {
            "accepted": True,
            "accepted_at": accepted_at,
            "terms_version": QUOTE_TERMS_VERSION,
            "confirmations": confirmations,
            "quote_ref": quote_ref,
            "quote_updated_at": row.get("updated_at"),
            "total_amount": row.get("total_amount"),
            "currency": row.get("currency"),
        }
        response = (
            get_supabase()
            .table("relocation_commercial_quotes")
            .update(
                {
                    "status": "accepted",
                    "accepted_at": accepted_at,
                    "metadata": {
                        **current_metadata,
                        "quote_acceptance": acceptance_record,
                    },
                }
            )
            .eq("id", row.get("id"))
            .eq("email", email)
            .execute()
        )
        updated = (response.data or [row])[0]
        _record_event(
            updated,
            "quote_accepted",
            payload={
                "quote_ref": quote_ref,
                "terms_version": QUOTE_TERMS_VERSION,
                "confirmations": confirmations,
                "total_amount": row.get("total_amount"),
                "currency": row.get("currency"),
            },
        )
        return jsonify({"ok": True, "quote": _public_quote(updated)})
    except Exception as exc:
        return jsonify({"ok": False, "error": "quote_acceptance_failed", "details": str(exc)}), 503


@bp.post("/quotes/<quote_ref>/decline")
def decline_quote(quote_ref: str):
    email, error = _auth_email()
    if not email:
        return jsonify({"ok": False, "error": error or "session_required"}), 401
    payload = request.get_json(silent=True) or {}
    try:
        row = _quote_for_account(quote_ref, email)
        if not row:
            return jsonify({"ok": False, "error": "quote_not_found"}), 404
        if row.get("status") not in {"sent", "accepted"}:
            return jsonify({"ok": False, "error": "quote_not_open_for_decline", "status": row.get("status")}), 409

        response = (
            get_supabase()
            .table("relocation_commercial_quotes")
            .update(
                {
                    "status": "declined",
                    "metadata": {
                        **(row.get("metadata") if isinstance(row.get("metadata"), dict) else {}),
                        "decline_reason": _text(payload.get("reason"), 500),
                        "declined_at": _iso_now(),
                    },
                }
            )
            .eq("id", row.get("id"))
            .eq("email", email)
            .execute()
        )
        updated = (response.data or [row])[0]
        _record_event(updated, "quote_declined", payload={"reason": _text(payload.get("reason"), 500)})
        return jsonify({"ok": True, "quote": _public_quote(updated)})
    except Exception as exc:
        return jsonify({"ok": False, "error": "quote_decline_failed", "details": str(exc)}), 503


@bp.post("/quotes/<quote_ref>/checkout")
def quote_checkout(quote_ref: str):
    email, error = _auth_email()
    if not email:
        return jsonify({"ok": False, "error": error or "session_required"}), 401
    if not PAYMENT_LINKS_ENABLED:
        return jsonify(
            {
                "ok": False,
                "error": "payment_links_not_enabled",
                "next_step": "Accept the quote, then wait for MoveReady to activate an approved payment link or provide a documented alternative.",
            }
        ), 409

    try:
        row = _quote_for_account(quote_ref, email)
        if not row:
            return jsonify({"ok": False, "error": "quote_not_found"}), 404
        if _expired(row):
            return jsonify({"ok": False, "error": "quote_expired"}), 409
        if row.get("status") not in {"accepted", "payment_pending"}:
            return jsonify({"ok": False, "error": "quote_must_be_accepted_before_checkout", "status": row.get("status")}), 409
        if not _acceptance_metadata(row).get("accepted"):
            return jsonify({"ok": False, "error": "auditable_quote_acceptance_required"}), 409
        if not row.get("checkout_url"):
            return jsonify({"ok": False, "error": "approved_checkout_link_not_available"}), 409

        response = (
            get_supabase()
            .table("relocation_commercial_quotes")
            .update({"status": "payment_pending"})
            .eq("id", row.get("id"))
            .eq("email", email)
            .execute()
        )
        updated = (response.data or [row])[0]
        _record_event(updated, "checkout_opened", payload={"quote_ref": quote_ref, "terms_version": QUOTE_TERMS_VERSION})
        return jsonify(
            {
                "ok": True,
                "quote": _public_quote(updated),
                "checkout_url": row.get("checkout_url"),
                "payment_notice": "Confirm the domain, amount, currency, recipient, refund terms, and quote reference before paying.",
            }
        )
    except Exception as exc:
        return jsonify({"ok": False, "error": "checkout_lookup_failed", "details": str(exc)}), 503
