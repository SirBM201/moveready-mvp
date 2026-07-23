from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from flask import Blueprint, jsonify, request

from app.routes import account_auth
from app.routes.billing_admin import _provider_handoff_errors
from app.services.supabase_client import get_supabase
from app.utils.admin_auth import require_admin_access


user_bp = Blueprint("service_handoffs", __name__)
admin_bp = Blueprint("service_handoffs_admin", __name__)

HANDOFF_CONSENT_VERSION = "moveready-provider-handoff-2026-07-23-v1"
SHAREABLE_FIELDS = {
    "full_name",
    "email",
    "phone",
    "current_country",
    "target_country",
    "route_or_goal",
    "service_request_summary",
    "quote_scope",
    "preferred_contact_channel",
    "deadline_summary",
    "family_context_summary",
    "document_types_summary",
}

HANDOFF_STATUSES = {
    "draft",
    "pending_user_consent",
    "consent_confirmed",
    "ready_to_share",
    "shared",
    "provider_acknowledged",
    "in_progress",
    "completed",
    "cancelled",
    "blocked",
    "disputed",
}

CASE_TYPES = {
    "general_support",
    "complaint",
    "refund_request",
    "payment_dispute",
    "provider_issue",
    "privacy_issue",
    "service_quality",
    "technical_issue",
    "other",
}

CASE_STATUSES = {
    "open",
    "reviewing",
    "waiting_user",
    "waiting_provider",
    "escalated",
    "resolved",
    "rejected",
    "closed",
}

CASE_PRIORITIES = {"low", "medium", "high", "critical"}


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


def _reference(prefix: str) -> str:
    return f"{prefix}-{_now().strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"


def _clean_shared_fields(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    output: List[str] = []
    for item in value:
        field = _text(item, 80)
        if field in SHAREABLE_FIELDS and field not in output:
            output.append(field)
    return output


def _public_handoff(row: Dict[str, Any]) -> Dict[str, Any]:
    consent_payload = row.get("consent_payload") if isinstance(row.get("consent_payload"), dict) else {}
    return {
        "id": row.get("id"),
        "handoff_ref": row.get("handoff_ref"),
        "quote_id": row.get("quote_id"),
        "service_request_id": row.get("service_request_id"),
        "provider_application_id": row.get("provider_application_id"),
        "service_slug": row.get("service_slug"),
        "service_title": row.get("service_title"),
        "provider_name": row.get("provider_name"),
        "status": row.get("status"),
        "payment_required": bool(row.get("payment_required")),
        "shared_fields": row.get("shared_fields") or [],
        "handoff_summary": row.get("handoff_summary"),
        "user_consent_required": bool(row.get("user_consent_required")),
        "user_consent_confirmed": bool(row.get("user_consent_confirmed")),
        "consent_version": row.get("consent_version") or HANDOFF_CONSENT_VERSION,
        "consent_recorded": bool(consent_payload.get("confirmed")),
        "consented_at": row.get("consented_at"),
        "prepared_at": row.get("prepared_at"),
        "shared_at": row.get("shared_at"),
        "provider_acknowledged_at": row.get("provider_acknowledged_at"),
        "completed_at": row.get("completed_at"),
        "delivery_channel": row.get("delivery_channel"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "consent_notice": "MoveReady may share only the listed fields with the named provider after your explicit consent. Passports, bank records, certificates, refusal letters, medical records, and other documents are not included unless a separately reviewed document type is explicitly listed and you agree through an approved secure process.",
    }


def _public_case(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row.get("id"),
        "case_ref": row.get("case_ref"),
        "quote_id": row.get("quote_id"),
        "handoff_id": row.get("handoff_id"),
        "case_type": row.get("case_type"),
        "status": row.get("status"),
        "priority": row.get("priority"),
        "subject": row.get("subject"),
        "description": row.get("description"),
        "requested_resolution": row.get("requested_resolution"),
        "resolution_summary": row.get("resolution_summary"),
        "resolved_at": row.get("resolved_at"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _record_handoff_event(
    handoff: Dict[str, Any],
    event_type: str,
    *,
    actor_type: str,
    actor_reference: Optional[str],
    status: str = "recorded",
    payload: Optional[Dict[str, Any]] = None,
) -> None:
    try:
        get_supabase().table("relocation_service_handoff_events").insert(
            {
                "handoff_id": handoff.get("id"),
                "event_type": event_type,
                "event_status": status,
                "actor_type": actor_type,
                "actor_reference": actor_reference,
                "event_payload": payload or {},
            }
        ).execute()
    except Exception:
        pass


def _quote_by_reference_or_id(value: str) -> Optional[Dict[str, Any]]:
    query = get_supabase().table("relocation_commercial_quotes").select("*")
    if value.upper().startswith("MRQ-"):
        query = query.eq("quote_ref", value)
    else:
        query = query.eq("id", value)
    response = query.maybe_single().execute()
    return response.data


def _provider(provider_id: str) -> Optional[Dict[str, Any]]:
    response = (
        get_supabase()
        .table("relocation_partner_applications")
        .select("*")
        .eq("id", provider_id)
        .maybe_single()
        .execute()
    )
    return response.data


def _handoff_by_ref_for_email(handoff_ref: str, email: str) -> Optional[Dict[str, Any]]:
    response = (
        get_supabase()
        .table("relocation_service_handoffs")
        .select("*")
        .eq("handoff_ref", handoff_ref)
        .eq("email", email)
        .maybe_single()
        .execute()
    )
    return response.data


def _case_link_id(table: str, reference_field: str, reference: Optional[str], email: str) -> Optional[str]:
    if not reference:
        return None
    response = (
        get_supabase()
        .table(table)
        .select("id,email")
        .eq(reference_field, reference)
        .eq("email", email)
        .maybe_single()
        .execute()
    )
    return (response.data or {}).get("id")


@user_bp.get("")
@user_bp.get("/")
def my_handoffs():
    email, error = _auth_email()
    if not email:
        return jsonify({"ok": False, "error": error or "session_required"}), 401
    try:
        response = (
            get_supabase()
            .table("relocation_service_handoffs")
            .select("*")
            .eq("email", email)
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )
        rows = [_public_handoff(row) for row in (response.data or [])]
        return jsonify(
            {
                "ok": True,
                "account_email": email,
                "handoff_count": len(rows),
                "handoffs": rows,
                "consent_version": HANDOFF_CONSENT_VERSION,
            }
        )
    except Exception as exc:
        return jsonify({"ok": False, "error": "service_handoffs_unavailable", "details": str(exc)}), 503


@user_bp.post("/<handoff_ref>/consent")
def consent_to_handoff(handoff_ref: str):
    email, error = _auth_email()
    if not email:
        return jsonify({"ok": False, "error": error or "session_required"}), 401
    payload = request.get_json(silent=True) or {}
    if payload.get("confirm_share") is not True:
        return jsonify({"ok": False, "error": "handoff_share_confirmation_required"}), 400
    if _text(payload.get("consent_version"), 120) != HANDOFF_CONSENT_VERSION:
        return jsonify({"ok": False, "error": "handoff_consent_version_mismatch", "consent_version": HANDOFF_CONSENT_VERSION}), 400
    if payload.get("provider_identity_reviewed") is not True:
        return jsonify({"ok": False, "error": "provider_identity_review_confirmation_required"}), 400
    if payload.get("no_unlisted_documents_understood") is not True:
        return jsonify({"ok": False, "error": "unlisted_document_protection_confirmation_required"}), 400

    try:
        handoff = _handoff_by_ref_for_email(handoff_ref, email)
        if not handoff:
            return jsonify({"ok": False, "error": "handoff_not_found"}), 404
        if handoff.get("status") not in {"pending_user_consent", "consent_confirmed"}:
            return jsonify({"ok": False, "error": "handoff_not_open_for_consent", "status": handoff.get("status")}), 409

        expected_fields = sorted(str(item) for item in (handoff.get("shared_fields") or []))
        acknowledged_fields = sorted(str(item) for item in (payload.get("acknowledged_fields") or []))
        if expected_fields != acknowledged_fields:
            return jsonify(
                {
                    "ok": False,
                    "error": "handoff_shared_fields_mismatch",
                    "expected_fields": expected_fields,
                }
            ), 400

        consented_at = _now_iso()
        consent_payload = {
            "confirmed": True,
            "confirmed_at": consented_at,
            "consent_version": HANDOFF_CONSENT_VERSION,
            "provider_name": handoff.get("provider_name"),
            "shared_fields": expected_fields,
            "provider_identity_reviewed": True,
            "no_unlisted_documents_understood": True,
        }
        response = (
            get_supabase()
            .table("relocation_service_handoffs")
            .update(
                {
                    "status": "consent_confirmed",
                    "user_consent_confirmed": True,
                    "consent_version": HANDOFF_CONSENT_VERSION,
                    "consent_payload": consent_payload,
                    "consented_at": consented_at,
                }
            )
            .eq("id", handoff.get("id"))
            .eq("email", email)
            .execute()
        )
        updated = (response.data or [handoff])[0]
        _record_handoff_event(
            updated,
            "user_consent_confirmed",
            actor_type="user",
            actor_reference=email,
            payload=consent_payload,
        )
        return jsonify({"ok": True, "handoff": _public_handoff(updated)})
    except Exception as exc:
        return jsonify({"ok": False, "error": "handoff_consent_failed", "details": str(exc)}), 503


@user_bp.post("/<handoff_ref>/decline")
def decline_handoff(handoff_ref: str):
    email, error = _auth_email()
    if not email:
        return jsonify({"ok": False, "error": error or "session_required"}), 401
    payload = request.get_json(silent=True) or {}
    try:
        handoff = _handoff_by_ref_for_email(handoff_ref, email)
        if not handoff:
            return jsonify({"ok": False, "error": "handoff_not_found"}), 404
        if handoff.get("status") in {"shared", "provider_acknowledged", "in_progress", "completed"}:
            return jsonify({"ok": False, "error": "handoff_already_shared_or_started"}), 409

        reason = _text(payload.get("reason"), 600)
        response = (
            get_supabase()
            .table("relocation_service_handoffs")
            .update(
                {
                    "status": "cancelled",
                    "user_consent_confirmed": False,
                    "consent_payload": {
                        "confirmed": False,
                        "declined_at": _now_iso(),
                        "reason": reason,
                    },
                }
            )
            .eq("id", handoff.get("id"))
            .eq("email", email)
            .execute()
        )
        updated = (response.data or [handoff])[0]
        _record_handoff_event(updated, "user_handoff_declined", actor_type="user", actor_reference=email, payload={"reason": reason})
        return jsonify({"ok": True, "handoff": _public_handoff(updated)})
    except Exception as exc:
        return jsonify({"ok": False, "error": "handoff_decline_failed", "details": str(exc)}), 503


@user_bp.get("/support-cases")
def my_support_cases():
    email, error = _auth_email()
    if not email:
        return jsonify({"ok": False, "error": error or "session_required"}), 401
    try:
        response = (
            get_supabase()
            .table("relocation_support_cases")
            .select("*")
            .eq("email", email)
            .order("created_at", desc=True)
            .limit(75)
            .execute()
        )
        rows = [_public_case(row) for row in (response.data or [])]
        return jsonify({"ok": True, "account_email": email, "case_count": len(rows), "support_cases": rows})
    except Exception as exc:
        return jsonify({"ok": False, "error": "support_cases_unavailable", "details": str(exc)}), 503


@user_bp.post("/support-cases")
def create_support_case():
    email, error = _auth_email()
    if not email:
        return jsonify({"ok": False, "error": error or "session_required"}), 401
    payload = request.get_json(silent=True) or {}
    case_type = _text(payload.get("case_type"), 80) or "general_support"
    subject = _text(payload.get("subject"), 180)
    description = _text(payload.get("description"), 3000)
    if case_type not in CASE_TYPES:
        return jsonify({"ok": False, "error": "invalid_case_type", "allowed_case_types": sorted(CASE_TYPES)}), 400
    if not subject or not description:
        return jsonify({"ok": False, "error": "case_subject_and_description_required"}), 400

    try:
        quote_id = _case_link_id("relocation_commercial_quotes", "quote_ref", _text(payload.get("quote_ref"), 120), email)
        handoff_id = _case_link_id("relocation_service_handoffs", "handoff_ref", _text(payload.get("handoff_ref"), 120), email)
        priority = "high" if case_type in {"payment_dispute", "privacy_issue"} else "medium"
        row = {
            "case_ref": _reference("MRC"),
            "quote_id": quote_id,
            "handoff_id": handoff_id,
            "full_name": _text(payload.get("full_name"), 180),
            "email": email,
            "phone": _text(payload.get("phone"), 80),
            "case_type": case_type,
            "status": "open",
            "priority": priority,
            "subject": subject,
            "description": description,
            "requested_resolution": _text(payload.get("requested_resolution"), 1200),
            "source_page": _text(payload.get("source_page"), 240) or "/support-center",
            "metadata": {
                "verified_account": True,
                "quote_ref_submitted": _text(payload.get("quote_ref"), 120),
                "handoff_ref_submitted": _text(payload.get("handoff_ref"), 120),
                "attachment_notice": "No file attachment is stored by this endpoint.",
            },
        }
        response = get_supabase().table("relocation_support_cases").insert(row).execute()
        stored = (response.data or [None])[0]
        return jsonify(
            {
                "ok": True,
                "support_case": _public_case(stored or row),
                "safety_note": "Do not place passwords, OTP codes, full card details, private keys, or unrequested identity documents in a support case.",
            }
        )
    except Exception as exc:
        return jsonify({"ok": False, "error": "support_case_create_failed", "details": str(exc)}), 503


@admin_bp.get("/service-handoffs")
@require_admin_access
def admin_handoffs():
    status = _text(request.args.get("status"), 40)
    email = _text(request.args.get("email"), 255)
    try:
        limit = max(1, min(int(request.args.get("limit") or 75), 100))
    except (TypeError, ValueError):
        limit = 75
    try:
        query = (
            get_supabase()
            .table("relocation_service_handoffs")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
        )
        if status:
            query = query.eq("status", status)
        if email:
            query = query.eq("email", email.lower())
        response = query.execute()
        rows = [_public_handoff(row) for row in (response.data or [])]
        return jsonify({"ok": True, "handoff_count": len(rows), "service_handoffs": rows})
    except Exception as exc:
        return jsonify({"ok": False, "error": "admin_handoffs_unavailable", "details": str(exc)}), 503


@admin_bp.post("/service-handoffs")
@require_admin_access
def create_handoff():
    payload = request.get_json(silent=True) or {}
    quote_reference = _text(payload.get("quote_ref") or payload.get("quote_id"), 120)
    provider_id = _text(payload.get("provider_application_id"), 80)
    shared_fields = _clean_shared_fields(payload.get("shared_fields"))
    handoff_summary = _text(payload.get("handoff_summary"), 1600)
    payment_required = True if payload.get("payment_required") is None else _bool(payload.get("payment_required"))

    if not quote_reference or not provider_id:
        return jsonify({"ok": False, "error": "quote_and_provider_required"}), 400
    if not shared_fields:
        return jsonify({"ok": False, "error": "at_least_one_approved_shared_field_required", "allowed_shared_fields": sorted(SHAREABLE_FIELDS)}), 400
    if not handoff_summary:
        return jsonify({"ok": False, "error": "handoff_summary_required"}), 400

    try:
        quote = _quote_by_reference_or_id(quote_reference)
        provider = _provider(provider_id)
        if not quote:
            return jsonify({"ok": False, "error": "quote_not_found"}), 404
        if not provider:
            return jsonify({"ok": False, "error": "provider_not_found"}), 404

        provider_errors = _provider_handoff_errors(provider)
        if not provider.get("public_listing_enabled"):
            provider_errors.append("provider_public_listing_not_enabled")
        if provider_errors:
            return jsonify({"ok": False, "error": "provider_handoff_not_ready", "provider_errors": provider_errors}), 409

        quote_metadata = quote.get("metadata") if isinstance(quote.get("metadata"), dict) else {}
        quote_acceptance = quote_metadata.get("quote_acceptance") if isinstance(quote_metadata.get("quote_acceptance"), dict) else {}
        if not quote_acceptance.get("accepted"):
            return jsonify({"ok": False, "error": "auditable_quote_acceptance_required"}), 409
        if payment_required and quote.get("status") not in {"paid", "fulfilled"}:
            return jsonify({"ok": False, "error": "paid_quote_required_for_handoff", "quote_status": quote.get("status")}), 409
        if not payment_required and quote.get("status") not in {"accepted", "paid", "fulfilled"}:
            return jsonify({"ok": False, "error": "accepted_quote_required_for_no_payment_handoff", "quote_status": quote.get("status")}), 409
        assigned_provider = str(quote.get("provider_application_id") or "").strip()
        if assigned_provider and assigned_provider != provider_id:
            return jsonify({"ok": False, "error": "quote_provider_mismatch"}), 409

        existing_response = (
            get_supabase()
            .table("relocation_service_handoffs")
            .select("id,handoff_ref,status")
            .eq("quote_id", quote.get("id"))
            .eq("provider_application_id", provider_id)
            .limit(10)
            .execute()
        )
        active_existing = next(
            (
                row
                for row in (existing_response.data or [])
                if row.get("status") not in {"cancelled", "completed", "blocked"}
            ),
            None,
        )
        if active_existing:
            return jsonify({"ok": False, "error": "active_handoff_already_exists", "handoff": active_existing}), 409

        row = {
            "handoff_ref": _reference("MRH"),
            "quote_id": quote.get("id"),
            "service_request_id": quote.get("service_request_id"),
            "provider_application_id": provider_id,
            "full_name": quote.get("full_name"),
            "email": str(quote.get("email") or "").strip().lower(),
            "phone": quote.get("phone"),
            "service_slug": quote.get("service_slug"),
            "service_title": quote.get("service_title"),
            "provider_name": provider.get("business_name"),
            "status": "pending_user_consent",
            "payment_required": payment_required,
            "shared_fields": shared_fields,
            "handoff_summary": handoff_summary,
            "user_consent_required": True,
            "user_consent_confirmed": False,
            "consent_version": HANDOFF_CONSENT_VERSION,
            "admin_owner": _text(payload.get("admin_owner"), 180) or "MoveReady admin",
            "metadata": {
                "quote_ref": quote.get("quote_ref"),
                "quote_status_at_preparation": quote.get("status"),
                "provider_publication_checked": True,
                "no_raw_documents_in_handoff": True,
            },
        }
        response = get_supabase().table("relocation_service_handoffs").insert(row).execute()
        stored = (response.data or [None])[0]
        if not stored:
            return jsonify({"ok": False, "error": "handoff_not_stored"}), 503
        _record_handoff_event(
            stored,
            "handoff_prepared",
            actor_type="admin",
            actor_reference=row["admin_owner"],
            payload={"shared_fields": shared_fields, "provider_name": row["provider_name"]},
        )
        return jsonify({"ok": True, "service_handoff": _public_handoff(stored)})
    except Exception as exc:
        return jsonify({"ok": False, "error": "handoff_create_failed", "details": str(exc)}), 503


@admin_bp.post("/service-handoffs/<handoff_id>/mark-shared")
@require_admin_access
def mark_handoff_shared(handoff_id: str):
    payload = request.get_json(silent=True) or {}
    delivery_channel = _text(payload.get("delivery_channel"), 80)
    delivery_reference = _text(payload.get("delivery_reference"), 300)
    if not delivery_channel or not delivery_reference:
        return jsonify({"ok": False, "error": "delivery_channel_and_reference_required"}), 400

    try:
        handoff_response = (
            get_supabase()
            .table("relocation_service_handoffs")
            .select("*")
            .eq("id", handoff_id)
            .maybe_single()
            .execute()
        )
        handoff = handoff_response.data
        if not handoff:
            return jsonify({"ok": False, "error": "handoff_not_found"}), 404
        if handoff.get("status") not in {"consent_confirmed", "ready_to_share"}:
            return jsonify({"ok": False, "error": "confirmed_user_consent_required_before_sharing", "status": handoff.get("status")}), 409
        consent_payload = handoff.get("consent_payload") if isinstance(handoff.get("consent_payload"), dict) else {}
        if not handoff.get("user_consent_confirmed") or not consent_payload.get("confirmed"):
            return jsonify({"ok": False, "error": "auditable_handoff_consent_required"}), 409

        provider = _provider(str(handoff.get("provider_application_id")))
        if not provider:
            return jsonify({"ok": False, "error": "provider_not_found"}), 404
        provider_errors = _provider_handoff_errors(provider)
        if not provider.get("public_listing_enabled"):
            provider_errors.append("provider_public_listing_not_enabled")
        if provider_errors:
            return jsonify({"ok": False, "error": "provider_no_longer_ready", "provider_errors": provider_errors}), 409

        shared_at = _now_iso()
        response = (
            get_supabase()
            .table("relocation_service_handoffs")
            .update(
                {
                    "status": "shared",
                    "shared_at": shared_at,
                    "delivery_channel": delivery_channel,
                    "delivery_reference": delivery_reference,
                }
            )
            .eq("id", handoff_id)
            .execute()
        )
        updated = (response.data or [handoff])[0]
        _record_handoff_event(
            updated,
            "provider_handoff_shared",
            actor_type="admin",
            actor_reference=_text(payload.get("admin_owner"), 180) or "MoveReady admin",
            payload={
                "delivery_channel": delivery_channel,
                "delivery_reference": delivery_reference,
                "shared_fields": handoff.get("shared_fields") or [],
            },
        )
        return jsonify({"ok": True, "service_handoff": _public_handoff(updated)})
    except Exception as exc:
        return jsonify({"ok": False, "error": "handoff_share_failed", "details": str(exc)}), 503


@admin_bp.patch("/service-handoffs/<handoff_id>")
@require_admin_access
def update_handoff_status(handoff_id: str):
    payload = request.get_json(silent=True) or {}
    status = _text(payload.get("status"), 40)
    if status not in HANDOFF_STATUSES:
        return jsonify({"ok": False, "error": "invalid_handoff_status", "allowed_statuses": sorted(HANDOFF_STATUSES)}), 400
    if status == "shared":
        return jsonify({"ok": False, "error": "use_mark_shared_endpoint_for_shared_status"}), 400

    updates: Dict[str, Any] = {"status": status}
    if status == "provider_acknowledged":
        updates["provider_acknowledged_at"] = _now_iso()
    elif status == "completed":
        updates["completed_at"] = _now_iso()

    try:
        response = (
            get_supabase()
            .table("relocation_service_handoffs")
            .update(updates)
            .eq("id", handoff_id)
            .execute()
        )
        updated = (response.data or [None])[0]
        if not updated:
            return jsonify({"ok": False, "error": "handoff_not_found"}), 404
        _record_handoff_event(
            updated,
            "handoff_status_updated",
            actor_type="admin",
            actor_reference=_text(payload.get("admin_owner"), 180) or "MoveReady admin",
            payload={"status": status},
        )
        return jsonify({"ok": True, "service_handoff": _public_handoff(updated)})
    except Exception as exc:
        return jsonify({"ok": False, "error": "handoff_update_failed", "details": str(exc)}), 503


@admin_bp.get("/support-cases")
@require_admin_access
def admin_support_cases():
    status = _text(request.args.get("status"), 40)
    case_type = _text(request.args.get("case_type"), 80)
    try:
        limit = max(1, min(int(request.args.get("limit") or 100), 150))
    except (TypeError, ValueError):
        limit = 100
    try:
        query = (
            get_supabase()
            .table("relocation_support_cases")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
        )
        if status:
            query = query.eq("status", status)
        if case_type:
            query = query.eq("case_type", case_type)
        response = query.execute()
        rows = [_public_case(row) | {"email": row.get("email"), "phone": row.get("phone"), "assigned_to": row.get("assigned_to")} for row in (response.data or [])]
        return jsonify({"ok": True, "case_count": len(rows), "support_cases": rows})
    except Exception as exc:
        return jsonify({"ok": False, "error": "admin_support_cases_unavailable", "details": str(exc)}), 503


@admin_bp.patch("/support-cases/<case_id>")
@require_admin_access
def update_support_case(case_id: str):
    payload = request.get_json(silent=True) or {}
    updates: Dict[str, Any] = {}
    status = _text(payload.get("status"), 40)
    priority = _text(payload.get("priority"), 40)
    if status:
        if status not in CASE_STATUSES:
            return jsonify({"ok": False, "error": "invalid_case_status", "allowed_statuses": sorted(CASE_STATUSES)}), 400
        updates["status"] = status
        if status in {"resolved", "closed"}:
            updates["resolved_at"] = _now_iso()
    if priority:
        if priority not in CASE_PRIORITIES:
            return jsonify({"ok": False, "error": "invalid_case_priority", "allowed_priorities": sorted(CASE_PRIORITIES)}), 400
        updates["priority"] = priority
    for field, limit in (("resolution_summary", 2000), ("assigned_to", 180)):
        if field in payload:
            updates[field] = _text(payload.get(field), limit)
    if not updates:
        return jsonify({"ok": False, "error": "no_update_fields"}), 400

    try:
        response = (
            get_supabase()
            .table("relocation_support_cases")
            .update(updates)
            .eq("id", case_id)
            .execute()
        )
        updated = (response.data or [None])[0]
        if not updated:
            return jsonify({"ok": False, "error": "support_case_not_found"}), 404
        return jsonify({"ok": True, "support_case": _public_case(updated) | {"email": updated.get("email"), "phone": updated.get("phone"), "assigned_to": updated.get("assigned_to")}})
    except Exception as exc:
        return jsonify({"ok": False, "error": "support_case_update_failed", "details": str(exc)}), 503
