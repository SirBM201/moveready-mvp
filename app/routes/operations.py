from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from flask import Blueprint, jsonify

from app.core import config
from app.services.email_delivery import email_delivery_status
from app.services.supabase_client import get_supabase
from app.utils.admin_auth import require_admin_access


public_bp = Blueprint("operations_public", __name__)
admin_bp = Blueprint("operations_admin", __name__)


SCHEMA_CHECKS = [
    {
        "code": "profiles",
        "table": "relocation_user_profiles",
        "columns": "id,email,status",
        "required_for": "verified account profiles",
        "migration": "008_user_relocation_profiles.sql",
        "critical": True,
    },
    {
        "code": "auth_login_codes",
        "table": "relocation_auth_login_codes",
        "columns": "id,email,status,attempts,expires_at",
        "required_for": "email OTP login",
        "migration": "019_account_login_otp.sql",
        "critical": True,
    },
    {
        "code": "user_sessions",
        "table": "relocation_user_sessions",
        "columns": "id,email,status,expires_at",
        "required_for": "verified account sessions",
        "migration": "019_account_login_otp.sql",
        "critical": True,
    },
    {
        "code": "reports",
        "table": "relocation_generated_reports",
        "columns": "id,report_ref,status",
        "required_for": "readiness reports",
        "migration": "001_initial_relocation_schema.sql and 022_report_account_fields_and_sections.sql",
        "critical": True,
    },
    {
        "code": "readiness_runs",
        "table": "relocation_readiness_check_runs",
        "columns": "id,tool_slug,status",
        "required_for": "study, journey, trip, and readiness history",
        "migration": "006_readiness_check_runs.sql",
        "critical": True,
    },
    {
        "code": "watchlist",
        "table": "relocation_watchlist_subscriptions",
        "columns": "id,email,status",
        "required_for": "verified alerts",
        "migration": "007_watchlist_alert_subscriptions.sql",
        "critical": False,
    },
    {
        "code": "partner_publication",
        "table": "relocation_partner_applications",
        "columns": "id,status,public_listing_enabled,privacy_reviewed,pricing_reviewed,refund_policy_reviewed,sensitive_document_handling_reviewed",
        "required_for": "safe public provider listings",
        "migration": "023_provider_publication_and_commercial_quotes.sql",
        "critical": False,
    },
    {
        "code": "commercial_quotes",
        "table": "relocation_commercial_quotes",
        "columns": "id,quote_ref,email,status,total_amount",
        "required_for": "commercial quotes and account billing",
        "migration": "023_provider_publication_and_commercial_quotes.sql",
        "critical": False,
    },
    {
        "code": "payment_events",
        "table": "relocation_payment_events",
        "columns": "id,quote_id,event_type,event_status",
        "required_for": "payment and quote audit history",
        "migration": "023_provider_publication_and_commercial_quotes.sql",
        "critical": False,
    },
    {
        "code": "service_handoffs",
        "table": "relocation_service_handoffs",
        "columns": "id,handoff_ref,email,status,user_consent_confirmed",
        "required_for": "consent-controlled provider handoffs",
        "migration": "025_service_handoffs_and_support_cases.sql",
        "critical": False,
    },
    {
        "code": "handoff_events",
        "table": "relocation_service_handoff_events",
        "columns": "id,handoff_id,event_type,event_status",
        "required_for": "provider handoff audit history",
        "migration": "025_service_handoffs_and_support_cases.sql",
        "critical": False,
    },
    {
        "code": "support_cases",
        "table": "relocation_support_cases",
        "columns": "id,case_ref,email,case_type,status,priority",
        "required_for": "complaints, refunds, disputes, privacy, and support cases",
        "migration": "025_service_handoffs_and_support_cases.sql",
        "critical": False,
    },
]


def _check_schema(item: Dict[str, Any]) -> Dict[str, Any]:
    try:
        response = (
            get_supabase()
            .table(item["table"])
            .select(item["columns"])
            .limit(1)
            .execute()
        )
        return {
            **item,
            "ok": True,
            "status": "ready",
            "sample_row_present": bool(response.data),
            "error": None,
        }
    except Exception as exc:
        return {
            **item,
            "ok": False,
            "status": "missing_or_unavailable",
            "sample_row_present": False,
            "error": str(exc)[:1200],
        }


def _configuration() -> Dict[str, Any]:
    email_status = email_delivery_status()
    return {
        "supabase_configured": bool(config.SUPABASE_URL and config.SUPABASE_SERVICE_ROLE_KEY),
        "admin_key_configured": bool(config.ADMIN_API_KEY),
        "email_otp_delivery_enabled": bool(email_status["enabled"]),
        "email_otp_delivery_configured": bool(email_status["configured"]),
        "email_otp_provider": email_status["provider"],
        "email_otp_missing_configuration": email_status["missing_configuration"],
        "email_otp_login_url_configured": email_status["login_url_configured"],
        "otp_dev_mode_requested": bool(config.AUTH_OTP_DEV_MODE),
        "opportunity_alerts_enabled": bool(config.OPPORTUNITY_ALERTS_ENABLED),
        "whatsapp_alerts_enabled": bool(config.WHATSAPP_ALERTS_ENABLED),
        "passport_provider_enabled": bool(config.PASSPORT_INDEX_PROVIDER_ENABLED),
        "passport_provider_credentials_present": bool(config.PASSPORT_INDEX_PROVIDER_URL and config.PASSPORT_INDEX_PROVIDER_KEY),
        "commercial_quotes_enabled": bool(config.COMMERCIAL_QUOTES_ENABLED),
        "payment_links_enabled": bool(config.PAYMENT_LINKS_ENABLED),
    }


def _operational_assessment(checks: List[Dict[str, Any]], configuration: Dict[str, Any]) -> Dict[str, Any]:
    critical_missing = [item for item in checks if item.get("critical") and not item.get("ok")]
    optional_missing = [item for item in checks if not item.get("critical") and not item.get("ok")]
    blockers: List[str] = []
    controlled: List[str] = []

    if not configuration["supabase_configured"]:
        blockers.append("Supabase credentials are not configured.")
    if not configuration["admin_key_configured"]:
        blockers.append("MoveReady admin API key is not configured.")
    for item in critical_missing:
        blockers.append(f"Required schema is unavailable for {item['required_for']}: run {item['migration']}.")
    for item in optional_missing:
        controlled.append(f"Feature remains fail-closed for {item['required_for']}: run {item['migration']}.")

    if configuration["email_otp_delivery_enabled"] and not configuration["email_otp_delivery_configured"]:
        blockers.append(
            "OTP email delivery is enabled but incomplete. Missing configuration: "
            + ", ".join(configuration["email_otp_missing_configuration"])
            + "."
        )
    elif not configuration["email_otp_delivery_enabled"]:
        controlled.append("Production email OTP delivery is disabled; verified public account login must remain in controlled rollout.")

    if configuration["otp_dev_mode_requested"] and config.ENV_MODE.lower() != "development":
        blockers.append("AUTH_OTP_DEV_MODE is set outside development. Remove it from production configuration.")
    if configuration["passport_provider_enabled"] and not configuration["passport_provider_credentials_present"]:
        controlled.append("Passport provider is enabled without a complete provider URL and key; provider sync remains unavailable.")
    if configuration["payment_links_enabled"] and not configuration["commercial_quotes_enabled"]:
        blockers.append("Payment links cannot be enabled while commercial quotes are disabled.")
    if not configuration["payment_links_enabled"]:
        controlled.append("Checkout links are disabled; quote acceptance and manual verified payment records remain separate.")
    if not configuration["opportunity_alerts_enabled"]:
        controlled.append("External email opportunity alerts are disabled; verified in-app alerts remain available.")
    if not configuration["whatsapp_alerts_enabled"]:
        controlled.append("WhatsApp alerts are disabled until credentials, templates, opt-in, and delivery audit are approved.")

    if blockers:
        overall = "blocked_or_degraded"
    elif optional_missing or controlled:
        overall = "core_operational_controlled_rollout"
    else:
        overall = "operational"

    return {
        "overall_status": overall,
        "launch_blockers": blockers,
        "controlled_rollout_items": controlled,
        "critical_schema_ready": not critical_missing,
        "optional_schema_ready": not optional_missing,
    }


@public_bp.get("/status")
def public_operations_status():
    configuration = _configuration()
    return jsonify(
        {
            "ok": True,
            "service": "MoveReady operations",
            "status": "code_operational_external_integrations_controlled",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "public_capabilities": {
                "verified_email_login": bool(
                    configuration["email_otp_delivery_enabled"]
                    and configuration["email_otp_delivery_configured"]
                ),
                "commercial_quote_requests": configuration["commercial_quotes_enabled"],
                "online_checkout": configuration["payment_links_enabled"],
                "in_app_alerts": True,
                "external_email_alerts": configuration["opportunity_alerts_enabled"],
                "whatsapp_alerts": configuration["whatsapp_alerts_enabled"],
                "provider_publication": "fail_closed_until_schema_and_admin_review_pass",
                "provider_handoffs": "consent_required_and_fail_closed_until_schema_passes",
            },
            "protected_diagnostics": "/api/admin/operations/status",
            "safety_note": "A feature shown as controlled or disabled must not be represented as live until its database, credentials, provider approval, consent, audit, and refund or delivery controls are verified.",
        }
    )


@admin_bp.get("/operations/status")
@require_admin_access
def admin_operations_status():
    configuration = _configuration()
    checks = [_check_schema(item) for item in SCHEMA_CHECKS]
    assessment = _operational_assessment(checks, configuration)
    return jsonify(
        {
            "ok": True,
            "service": "MoveReady protected operations diagnostics",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "configuration": configuration,
            "schema_checks": checks,
            **assessment,
            "recommended_sequence": [
                "Apply Supabase migrations through 026, including provider publication, quotes, payment audit, private-table RLS, consent-based handoffs, support cases, and database invariants.",
                "Confirm the admin key, production SECRET_KEY, CORS origin, and an approved OTP email provider before inviting public account users.",
                "Keep PAYMENT_LINKS_ENABLED false until checkout domains, amounts, currencies, references, webhooks or manual verification, refunds, and dispute handling are approved.",
                "Approve providers internally, then separately complete publication controls before making any listing public or preparing a handoff.",
                "Require explicit user consent for the exact handoff field list and record a delivery channel and reference before marking information shared.",
                "Run backend, auth, billing, handoff, study, trip, journey, Passport Index, and frontend deployment smoke tests after each production change.",
            ],
        }
    )
