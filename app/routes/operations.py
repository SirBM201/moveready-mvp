from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from flask import Blueprint, current_app, jsonify

from app.core import config
from app.core.operations_readiness import (
    admin_route_contract,
    environment_checks,
    environment_summary,
    operations_contract_payload,
)
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
        "code": "trusted_sources",
        "table": "relocation_trusted_sources",
        "columns": "id,source_name,source_url,status,last_checked_at,next_review_due_at",
        "required_for": "official-source governance and freshness",
        "migration": "001_initial_relocation_schema.sql",
        "critical": True,
    },
    {
        "code": "source_change_alerts",
        "table": "relocation_source_change_alerts",
        "columns": "id,source_id,alert_type,severity,status",
        "required_for": "source change and review-due alerts",
        "migration": "001_initial_relocation_schema.sql",
        "critical": True,
    },
    {
        "code": "route_versions",
        "table": "relocation_route_versions",
        "columns": "id,route_id,status,source_confidence,verified_at,review_due_at",
        "required_for": "versioned route guidance and review deadlines",
        "migration": "001_initial_relocation_schema.sql",
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
        "required_for": "study, journey, trip, refusal-repair, and readiness history",
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
    {
        "code": "document_inventory",
        "table": "relocation_user_document_inventory",
        "columns": "id,email,document_type,status,expiry_date",
        "required_for": "private document metadata and expiry tracking",
        "migration": "027_evidence_inventory_and_packs.sql",
        "critical": False,
    },
    {
        "code": "evidence_packs",
        "table": "relocation_evidence_packs",
        "columns": "id,pack_ref,email,status,completeness_score,risk_level",
        "required_for": "private evidence-pack generation and account history",
        "migration": "027_evidence_inventory_and_packs.sql",
        "critical": False,
    },
    {
        "code": "application_cases",
        "table": "relocation_application_cases",
        "columns": "id,case_ref,email,application_stage,status,risk_level,next_deadline_at",
        "required_for": "private application lifecycle, deadlines, fees, source status, and decisions",
        "migration": "028_application_case_manager.sql",
        "critical": False,
    },
    {
        "code": "application_case_events",
        "table": "relocation_application_case_events",
        "columns": "id,application_case_id,event_type,event_status,event_at,due_at",
        "required_for": "auditable application case event history",
        "migration": "028_application_case_manager.sql",
        "critical": False,
    },
    {
        "code": "application_case_alerts",
        "table": "relocation_application_case_alerts",
        "columns": "id,application_case_id,email,alert_type,severity,status,due_at",
        "required_for": "private application deadline and risk alerts",
        "migration": "029_application_case_alerts.sql",
        "critical": False,
    },
    {
        "code": "account_preferences",
        "table": "relocation_account_preferences",
        "columns": "id,email,onboarding_status,onboarding_step,in_app_notifications_enabled",
        "required_for": "account settings, onboarding, accessibility, and notification consent",
        "migration": "030_account_preferences_privacy_activity.sql",
        "critical": False,
    },
    {
        "code": "privacy_requests",
        "table": "relocation_privacy_requests",
        "columns": "id,request_ref,email,request_type,status,priority",
        "required_for": "verified data access, correction, restriction, consent withdrawal, and deletion requests",
        "migration": "030_account_preferences_privacy_activity.sql",
        "critical": False,
    },
    {
        "code": "language_profiles",
        "table": "relocation_language_profiles",
        "columns": "id,email,language_selection,english_allocation,french_allocation,daily_minutes,english_current_level,french_current_level,english_target_level,french_target_level",
        "required_for": "private Language Coach choices, allocations, placement, and targets",
        "migration": "034_language_coach_v1.sql and 039_language_coach_backend_completion.sql",
        "critical": False,
    },
    {
        "code": "language_questions",
        "table": "relocation_language_questions",
        "columns": "id,language,exam,skill,difficulty,content_origin,source_url,is_active",
        "required_for": "original or permitted official-release Language Coach practice content",
        "migration": "034_language_coach_v1.sql, 035_language_coach_starter_bank.sql, and 039_language_coach_backend_completion.sql",
        "critical": False,
    },
    {
        "code": "language_attempts",
        "table": "relocation_language_attempts",
        "columns": "id,email,question_id,is_correct,difficulty,response_seconds,attempted_at",
        "required_for": "private Language Coach diagnostic and practice attempts",
        "migration": "034_language_coach_v1.sql and 039_language_coach_backend_completion.sql",
        "critical": False,
    },
    {
        "code": "language_mistakes",
        "table": "relocation_language_mistakes",
        "columns": "id,email,question_id,mistake_count,correct_streak,next_review_at,mastered_at",
        "required_for": "private Language Coach mistakes and spaced-review queue",
        "migration": "034_language_coach_v1.sql and 039_language_coach_backend_completion.sql",
        "critical": False,
    },
    {
        "code": "language_daily_progress",
        "table": "relocation_language_daily_progress",
        "columns": "id,email,activity_date,english_minutes,french_minutes,questions_attempted,questions_correct,momentum_points",
        "required_for": "private Language Coach progress and non-punitive momentum",
        "migration": "034_language_coach_v1.sql and 039_language_coach_backend_completion.sql",
        "critical": False,
    },
    {
        "code": "job_search_profiles",
        "table": "relocation_job_search_profiles",
        "columns": "id,email,headline,primary_country,career_facts,search_scope,current_country,work_authorized_countries,is_active",
        "required_for": "private general-user job-search scope, targeting, and matching",
        "migration": "031_jobs_execution_platform.sql, 032_job_discovery_and_application_assistance.sql, and 034_career_search_scope_and_viability.sql",
        "critical": False,
    },
    {
        "code": "job_companies",
        "table": "relocation_job_companies",
        "columns": "id,company_name,country,is_curated,record_status",
        "required_for": "the Jobs company directory",
        "migration": "031_jobs_execution_platform.sql",
        "critical": False,
    },
    {
        "code": "job_recruiters",
        "table": "relocation_job_recruiters",
        "columns": "id,owner_email,recruiter_name,connection_status",
        "required_for": "private recruiter relationship tracking",
        "migration": "031_jobs_execution_platform.sql",
        "critical": False,
    },
    {
        "code": "job_company_targets",
        "table": "relocation_job_company_targets",
        "columns": "id,email,company_id,priority,status",
        "required_for": "private target-company priority and status tracking",
        "migration": "031_jobs_execution_platform.sql",
        "critical": False,
    },
    {
        "code": "jobs",
        "table": "relocation_jobs",
        "columns": "id,job_title,country,status,source_status,source_fingerprint,last_checked_at,work_authorization_requirement,sponsorship_evidence,relocation_support_status",
        "required_for": "vacancy recording, scope matching, and source-derived work-authorization truth",
        "migration": "031_jobs_execution_platform.sql, 032_job_discovery_and_application_assistance.sql, and 034_career_search_scope_and_viability.sql",
        "critical": False,
    },
    {
        "code": "job_resume_assets",
        "table": "relocation_job_resume_assets",
        "columns": "id,email,document_type,storage_path,is_active",
        "required_for": "the private Resume Vault",
        "migration": "031_jobs_execution_platform.sql",
        "critical": False,
    },
    {
        "code": "job_applications",
        "table": "relocation_job_applications",
        "columns": "id,email,job_title,company_name,status,follow_up_date",
        "required_for": "private job application tracking",
        "migration": "031_jobs_execution_platform.sql",
        "critical": False,
    },
    {
        "code": "job_watches",
        "table": "relocation_job_watches",
        "columns": "id,email,company_id,source_url,cadence,is_active,last_scan_status",
        "required_for": "official-source vacancy monitoring",
        "migration": "032_job_discovery_and_application_assistance.sql",
        "critical": False,
    },
    {
        "code": "job_scan_runs",
        "table": "relocation_job_scan_runs",
        "columns": "id,watch_id,email,trigger_type,status,discovered_count",
        "required_for": "auditable vacancy scan history",
        "migration": "032_job_discovery_and_application_assistance.sql",
        "critical": False,
    },
    {
        "code": "job_alerts",
        "table": "relocation_job_alerts",
        "columns": "id,email,watch_id,job_id,alert_type,status,delivery_status",
        "required_for": "private vacancy and source-change alerts",
        "migration": "032_job_discovery_and_application_assistance.sql",
        "critical": False,
    },
    {
        "code": "job_document_drafts",
        "table": "relocation_job_document_drafts",
        "columns": "id,email,job_id,draft_type,status,user_confirmations",
        "required_for": "truth-reviewed resume and cover-letter drafts",
        "migration": "032_job_discovery_and_application_assistance.sql",
        "critical": False,
    },
    {
        "code": "job_application_assistance",
        "table": "relocation_job_application_assistance",
        "columns": "id,email,application_id,job_id,status,readiness",
        "required_for": "controlled employer-page application handoffs",
        "migration": "032_job_discovery_and_application_assistance.sql",
        "critical": False,
    },
    {
        "code": "job_assistance_events",
        "table": "relocation_job_assistance_events",
        "columns": "id,email,assistance_id,event_type,created_at",
        "required_for": "application assistance audit history",
        "migration": "032_job_discovery_and_application_assistance.sql",
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
    checks = environment_checks(email_status)
    return {
        "environment_validation": environment_summary(checks),
        "environment_checks": checks,
        "secret_key_configured": bool(config.SECRET_KEY),
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
        "cors_policy": "explicit_allow_list" if config.CORS_ORIGINS and config.CORS_ORIGINS != "*" else "wildcard_or_missing",
    }


def _operational_assessment(checks: List[Dict[str, Any]], configuration: Dict[str, Any]) -> Dict[str, Any]:
    critical_missing = [item for item in checks if item.get("critical") and not item.get("ok")]
    optional_missing = [item for item in checks if not item.get("critical") and not item.get("ok")]
    blockers: List[str] = []
    controlled: List[str] = []

    if not configuration.get("supabase_configured"):
        blockers.append("Supabase credentials are not configured.")
    if not configuration.get("secret_key_configured"):
        blockers.append("Production SECRET_KEY is not configured.")
    if not configuration.get("admin_key_configured"):
        blockers.append("MoveReady admin API key is not configured.")
    for item in critical_missing:
        blockers.append(f"Required schema is unavailable for {item['required_for']}: run {item['migration']}.")
    for item in optional_missing:
        controlled.append(f"Feature remains fail-closed for {item['required_for']}: run {item['migration']}.")

    email_enabled = bool(configuration.get("email_otp_delivery_enabled"))
    email_configured = bool(configuration.get("email_otp_delivery_configured"))
    if email_enabled and not email_configured:
        missing = configuration.get("email_otp_missing_configuration") or []
        blockers.append(
            "OTP email delivery is enabled but incomplete. Missing configuration: "
            + (", ".join(missing) if missing else "provider credentials or sender")
            + "."
        )
    elif not email_enabled:
        controlled.append("Production email OTP delivery is disabled; verified public account login must remain in controlled rollout.")

    if configuration.get("otp_dev_mode_requested") and config.ENV_MODE.lower() != "development":
        blockers.append("AUTH_OTP_DEV_MODE is set outside development. Remove it from production configuration.")
    if configuration.get("passport_provider_enabled") and not configuration.get("passport_provider_credentials_present"):
        controlled.append("Passport provider is enabled without a complete provider URL and key; provider sync remains unavailable.")
    if configuration.get("payment_links_enabled") and not configuration.get("commercial_quotes_enabled"):
        blockers.append("Payment links cannot be enabled while commercial quotes are disabled.")
    if not configuration.get("payment_links_enabled"):
        controlled.append("Checkout links are disabled; quote acceptance and manual verified payment records remain separate.")
    if not configuration.get("opportunity_alerts_enabled"):
        controlled.append("External email opportunity alerts are disabled; verified in-app alerts remain available.")
    if not configuration.get("whatsapp_alerts_enabled"):
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
    operations_contract = operations_contract_payload()
    operations_contract["admin_boundary"].update(admin_route_contract(current_app))
    return jsonify(
        {
            "ok": True,
            "service": "MoveReady operations",
            "status": "code_operational_external_integrations_controlled",
            "contract_version": operations_contract["version"],
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "environment_validation": configuration["environment_validation"],
            "operations_contract": operations_contract,
            "public_capabilities": {
                "verified_email_login": bool(
                    configuration.get("email_otp_delivery_enabled")
                    and configuration.get("email_otp_delivery_configured")
                ),
                "source_freshness": True,
                "private_evidence_pack": "verified_account_only_after_migration_027",
                "refusal_repair": "verified_account_only_and_no_raw_documents",
                "application_case_manager": "verified_account_only_after_migration_028",
                "application_alert_inbox": "verified_account_only_after_migration_029",
                "application_timeline_tasks": "explicit_storage_confirmation_required",
                "account_settings_and_privacy": "verified_account_only_after_migration_030",
                "account_data_export": "verified_account_json_export_excluding_security_secrets",
                "jobs_workspace": "verified_account_only_after_migrations_031_032_034",
                "resume_vault": "private_files_signed_downloads_after_migration_031",
                "commercial_quote_requests": bool(configuration.get("commercial_quotes_enabled")),
                "online_checkout": bool(configuration.get("payment_links_enabled")),
                "in_app_alerts": True,
                "external_email_alerts": bool(configuration.get("opportunity_alerts_enabled")),
                "whatsapp_alerts": bool(configuration.get("whatsapp_alerts_enabled")),
                "provider_publication": "fail_closed_until_schema_and_admin_review_pass",
                "provider_handoff": "fail_closed_until_schema_and_explicit_consent_pass",
                "provider_handoffs": "consent_required_and_fail_closed_until_schema_passes",
                "support_cases": "verified_account_only_after_migration_025",
            },
            "source_health_endpoint": "/api/source-health/summary",
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
    operations_contract = operations_contract_payload()
    operations_contract["admin_boundary"].update(admin_route_contract(current_app))
    return jsonify(
        {
            "ok": True,
            "service": "MoveReady protected operations diagnostics",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "configuration": configuration,
            "operations_contract": operations_contract,
            "schema_checks": checks,
            **assessment,
            "recommended_sequence": [
                "Follow docs/MIGRATION_LEDGER.json through migration 039, including provider publication, quotes, payment audit, private-table RLS, consent-based handoffs, support cases, evidence packs, application cases, alerts, account controls, Jobs, Passport official-source governance, and Language Coach completion.",
                "Run the source-governance queue and resolve overdue official sources and route versions before promoting guidance as current.",
                "Use the Application Case Manager and daily private alert scan without storing raw authority correspondence or complete reference numbers.",
                "Review privacy requests manually; never treat a deletion request as authorization for immediate unaudited destruction.",
                "Confirm the admin key, production SECRET_KEY, CORS origin, and an approved OTP email provider before inviting public account users.",
                "Keep PAYMENT_LINKS_ENABLED false until checkout domains, amounts, currencies, references, webhooks or manual verification, refunds, and dispute handling are approved.",
                "Approve providers internally, then separately complete publication controls before making any listing public or preparing a handoff.",
                "Require explicit user consent for the exact handoff field list and record a delivery channel and reference before marking information shared.",
                "Run backend, auth, evidence, applications, alerts, settings, privacy, source-governance, billing, handoff, study, trip, journey, Passport Index, and frontend deployment smoke tests after each production change.",
            ],
        }
    )
