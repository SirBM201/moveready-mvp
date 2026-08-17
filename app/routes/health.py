from __future__ import annotations

import os
import platform
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

from flask import Blueprint, current_app, jsonify

from app.core import config

bp = Blueprint("health", __name__)
_PROCESS_STARTED_AT = datetime.now(timezone.utc)
_PROCESS_STARTED_MONOTONIC = time.monotonic()
_RELEASE_LABEL = "moveready-v1-completion-2026-08-14"

def _env(name: str, default: str = "") -> str: return (os.getenv(name, default) or "").strip()
def _first_env(*names: str) -> str:
    for name in names:
        value=_env(name)
        if value:return value
    return ""
def _commit_sha() -> str: return _first_env("RAILWAY_GIT_COMMIT_SHA","GIT_COMMIT_SHA","SOURCE_COMMIT","COMMIT_SHA")
def _deployment_environment() -> str: return _first_env("RAILWAY_ENVIRONMENT_NAME","ENV_MODE","FLASK_ENV") or "unknown"
def _schedule_summary() -> Dict[str, Any]:
    countries=[item.strip() for item in str(config.PASSPORT_INDEX_SCHEDULED_COUNTRIES or "Nigeria").split(",") if item.strip()]
    return {"cadence":"weekly","weekdays":config.PASSPORT_INDEX_SYNC_WEEKDAYS,"hour_utc":config.PASSPORT_INDEX_SYNC_HOUR_UTC,"minute_utc":config.PASSPORT_INDEX_SYNC_MINUTE_UTC,"scheduled_countries":countries,"maximum_countries_per_run":config.PASSPORT_INDEX_MAX_COUNTRIES_PER_SYNC,"cache_max_days":config.PASSPORT_INDEX_CACHE_MAX_DAYS,"execution_model":"scheduled sync plus stale-cache refresh protection"}
def _feature_flags() -> Dict[str, Any]:
    return {"account_auth":True,"account_summary":True,"guided_onboarding":True,"my_journey":True,"account_action_center":True,"account_activity":True,"account_preferences":True,"account_session_controls":True,"account_data_export":True,"privacy_requests":True,"profiles":True,"saved_routes":True,"reports":True,"watchlist":True,"in_app_alerts":True,"application_cases":True,"application_case_alerts":True,"service_requests":True,"study_planner":True,"journey_planner":True,"trip_planner":True,"settlement_timeline":True,"evidence_inventory":True,"evidence_packs":True,"refusal_repair":True,"source_health":True,"source_governance_admin":True,"opportunity_finder":True,"route_comparison":True,"financial_readiness":True,"account_outcomes":True,"readiness_command_center":True,"language_coach":True,"commercial_quotes":bool(config.COMMERCIAL_QUOTES_ENABLED),"payment_links":bool(config.PAYMENT_LINKS_ENABLED),"provider_publication_controls":True,"provider_handoffs":True,"support_cases":True,"jobs_workspace":True,"jobs_resume_vault":True,"jobs_official_source_monitoring":True,"jobs_truthful_document_drafts":True,"jobs_controlled_application_handoff":True,"visa_power":bool(config.VISA_POWER_ENABLED),"passport_index":bool(config.VISA_POWER_ENABLED),"passport_provider_cache":True,"passport_weekly_sync":True,"external_passport_provider_enabled":bool(config.PASSPORT_INDEX_PROVIDER_ENABLED),"external_email_alerts":bool(config.OPPORTUNITY_ALERTS_ENABLED),"whatsapp_alerts":bool(config.WHATSAPP_ALERTS_ENABLED)}
def _expected_endpoints() -> List[str]:
    p=config.API_PREFIX
    return [f"{p}/auth/health",f"{p}/account/summary",f"{p}/account/preferences",f"{p}/account/sessions",f"{p}/account/activity",f"{p}/account/action-center",f"{p}/account/outcomes",f"{p}/account/data-export",f"{p}/account/privacy-requests",f"{p}/operations/status",f"{p}/platform/modules",f"{p}/source-health/summary",f"{p}/opportunity-finder/recommendations",f"{p}/financial-readiness/check",f"{p}/route-comparison",f"{p}/evidence/options",f"{p}/evidence/documents",f"{p}/evidence/packs",f"{p}/evidence/packs/generate",f"{p}/evidence/refusal-repair",f"{p}/applications/options",f"{p}/applications",f"{p}/applications/links",f"{p}/applications/alerts",f"{p}/jobs/options",f"{p}/jobs/profile",f"{p}/jobs/profile/search-scope",f"{p}/jobs/profile/bootstrap",f"{p}/jobs/summary",f"{p}/jobs/companies",f"{p}/jobs/recruiters",f"{p}/jobs",f"{p}/jobs/applications",f"{p}/jobs/resume-vault",f"{p}/jobs/automation/overview",f"{p}/jobs/automation/watches/bootstrap",f"{p}/jobs/automation/scan",f"{p}/language-coach/options",f"{p}/language-coach/profile",f"{p}/language-coach/diagnostic",f"{p}/language-coach/diagnostic/complete",f"{p}/language-coach/practice",f"{p}/language-coach/adaptive-practice",f"{p}/language-coach/daily-challenge",f"{p}/language-coach/attempts",f"{p}/language-coach/mistakes",f"{p}/language-coach/review",f"{p}/language-coach/progress",f"{p}/language-coach/qualification-actions",f"{p}/billing/status",f"{p}/handoffs",f"{p}/handoffs/support-cases",f"{p}/journey/options",f"{p}/journey/settlement-plan",f"{p}/visa-power/provider/status",f"{p}/visa-power/provider/schedule/status",f"{p}/visa-power/passport-index/check",f"{p}/visa-power/check",f"{p}/admin/operations/status",f"{p}/admin/source-governance/queue",f"{p}/admin/review-queue",f"{p}/admin/application-cases",f"{p}/admin/application-case-alerts",f"{p}/admin/application-cases/alerts/scan",f"{p}/admin/jobs/automation/scheduled-scan",f"{p}/admin/privacy-requests"]
def _route_contract() -> Dict[str, Any]:
    expected=_expected_endpoints();registered={rule.rule for rule in current_app.url_map.iter_rules()};missing=[route for route in expected if route not in registered]
    return {"ok":not missing,"expected_count":len(expected),"registered_route_count":len(registered),"missing_routes":missing}
def _deployment_payload() -> Dict[str, Any]:
    commit_sha=_commit_sha();uptime_seconds=max(0,int(time.monotonic()-_PROCESS_STARTED_MONOTONIC))
    return {"release_label":_RELEASE_LABEL,"commit_sha":commit_sha or None,"commit_short":commit_sha[:12] if commit_sha else None,"environment":_deployment_environment(),"railway_service":_env("RAILWAY_SERVICE_NAME") or None,"railway_environment_id_present":bool(_env("RAILWAY_ENVIRONMENT_ID")),"process_started_at":_PROCESS_STARTED_AT.isoformat(),"uptime_seconds":uptime_seconds,"python_version":platform.python_version()}
def _health_payload() -> Dict[str, Any]: return {"ok":True,"status":"healthy","service":"moveready-api","api_prefix":config.API_PREFIX,"deployment":_deployment_payload(),"features":_feature_flags(),"passport_index_schedule":_schedule_summary(),"checked_at":datetime.now(timezone.utc).isoformat()}
@bp.get("/health")
def health(): return jsonify(_health_payload())
@bp.get("/api/health")
def api_health(): return jsonify(_health_payload())
@bp.get("/api/build-info")
def build_info():
    payload=_health_payload();payload["expected_endpoints"]=_expected_endpoints();payload["route_contract"]=_route_contract();payload["contract_versions"]={"financial_readiness":"b09-v1","opportunity_finder":"b11-v1","documents_applications":"b12-v1","dashboard_orchestration":"b13-v1"};payload["deployment_verification"]={"commit_available":bool(payload["deployment"].get("commit_sha")),"instruction":"Compare deployment.commit_sha with the latest main-branch commit before treating production as current.","older_deploy_warning":"If an expected endpoint, route contract, current feature flag, or release label is missing, Railway is serving an older revision or the wrong service."};payload["safety_contract"]={"evidence_storage":"metadata only; raw files and full document numbers are not accepted","application_storage":"status and planning metadata only; raw authority correspondence and complete reference numbers are not accepted","documents_applications":"B12 links only account-owned evidence-pack metadata into private application cases; raw documents, complete references, and authority correspondence remain prohibited","action_center":"read-only ranking derived from existing private records; no duplicate data store","dashboard_orchestration":"B13 selects one next action and summarizes seven engines from existing private records; ready means ready for the next planning check, never eligible or approved","journey_progress":"reflects saved records only and never implies authority approval","opportunity_finder":"B11 ranks profile alignment, exposes route-specific gaps and official-source freshness, and never makes an eligibility or approval decision","route_comparison":"source-aware decision support; no best-country or approval-probability score","financial_readiness":"B09 uses sourced proof-of-funds input, no invented family multiplier, and no guessed currency conversion; all outputs remain planning-only","account_outcomes":"descriptive metrics use recorded user data and are not predictive success rates","privacy_requests":"reviewed workflow; no automatic destructive action","source_health":"freshness and confidence reporting does not guarantee that every rule is unchanged","public_provider_listing":"fail closed until schema and publication checks pass","provider_handoff":"exact-field user consent and delivery evidence required","payment_links":"disabled until payment activation controls pass" if not config.PAYMENT_LINKS_ENABLED else "enabled by production configuration","email_login":"controlled by provider readiness and abuse limits","external_notifications":"saved preference does not activate email, WhatsApp, SMS, Telegram, or push delivery","jobs_workspace":"verified-account data only; resume files use a private bucket and signed downloads","jobs_automation":"official employer and supported public ATS sources only; no automatic submission; document drafts require explicit truth confirmations"};return jsonify(payload)
