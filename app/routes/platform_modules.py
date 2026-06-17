from __future__ import annotations

from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

from app.core import config

bp = Blueprint("platform_modules", __name__)
planned_bp = Blueprint("planned_platform_modules", __name__)

PLATFORM_MODULES: List[Dict[str, Any]] = [
    {
        "slug": "opportunities",
        "title": "Official ballots and quota opportunities",
        "category": "opportunity_monitoring",
        "availability": "coming_soon",
        "flag": "OPPORTUNITY_ALERTS_ENABLED",
        "summary": "Track official lottery, ballot, invitation-pool, quota, and capped routes such as DV, youth mobility, IEC, and country-cap opportunities.",
        "current_support": "The workspace is prepared for official-source monitoring and route alerts.",
    },
    {
        "slug": "watchlist",
        "title": "Route watchlist and alerts",
        "category": "opportunity_monitoring",
        "availability": "coming_soon",
        "flag": "WHATSAPP_ALERTS_ENABLED",
        "summary": "Let users save routes and receive email, WhatsApp, Telegram, or in-app alerts when an opening, deadline, result window, or source change occurs.",
        "current_support": "The product surface is ready for user opt-in and notification preferences.",
    },
    {
        "slug": "documents",
        "title": "Document readiness and name consistency",
        "category": "readiness",
        "availability": "coming_soon",
        "flag": "DOCUMENT_CHECKS_ENABLED",
        "summary": "Check passport validity, missing documents, name mismatch, translation, notarization, apostille, legalization, and route-specific evidence gaps.",
        "current_support": "Route-level checklists are already supported by the live MVP.",
    },
    {
        "slug": "funds",
        "title": "Proof-of-funds planner",
        "category": "readiness",
        "availability": "coming_soon",
        "flag": "PROOF_OF_FUNDS_PLANNER_ENABLED",
        "summary": "Track required funds, available funds, shortfall, savings target, sponsor evidence, family-size adjustment, and large-deposit risk.",
        "current_support": "Starter budget estimates are already supported by the live MVP.",
    },
    {
        "slug": "refusal-risk",
        "title": "Refusal risk analyzer",
        "category": "risk_review",
        "availability": "coming_soon",
        "flag": "REFUSAL_ANALYZER_ENABLED",
        "summary": "Review previous refusals and weak application indicators such as unclear purpose, low funds, weak home ties, incomplete evidence, or wrong route selection.",
        "current_support": "Risk labels are already used on source-backed route pages and readiness reports.",
    },
    {
        "slug": "legalization",
        "title": "Notarization, apostille, and legalization",
        "category": "execution_services",
        "availability": "coming_soon",
        "flag": "LEGALIZATION_MODULE_ENABLED",
        "summary": "Guide users on whether documents need notarization, apostille, embassy legalization, translation, or ministry authentication.",
        "current_support": "Route document notes can already show legalization requirements where official sources confirm them.",
    },
    {
        "slug": "courier",
        "title": "Passport and document courier",
        "category": "execution_services",
        "availability": "partner_approval_pending",
        "flag": "COURIER_MODULE_ENABLED",
        "summary": "Coordinate trusted passport, certificate, embassy, and notarization courier workflows with tracking and insurance options.",
        "current_support": "The service slot is prepared for trusted provider onboarding.",
    },
    {
        "slug": "insurance",
        "title": "Insurance readiness and partners",
        "category": "execution_services",
        "availability": "coming_soon",
        "flag": "INSURANCE_PARTNER_ENABLED",
        "summary": "Track travel, health, student, family, work-permit, and Schengen-style insurance requirements and future partner quotes.",
        "current_support": "Insurance requirement records are already supported by the backend.",
    },
    {
        "slug": "appointments",
        "title": "Embassy and application appointment tracker",
        "category": "timeline",
        "availability": "coming_soon",
        "flag": "APPOINTMENT_TRACKER_ENABLED",
        "summary": "Save embassy, visa center, biometrics, document submission, collection, and deadline events for user reminders.",
        "current_support": "The first version can start with manual timelines and user reminders.",
    },
    {
        "slug": "family-relocation",
        "title": "Family relocation planner",
        "category": "readiness",
        "availability": "coming_soon",
        "flag": "FAMILY_PLANNER_ENABLED",
        "summary": "Model spouse, children, extra documents, extra funds, accommodation, school, insurance, and arrival tasks per family member.",
        "current_support": "Family count already affects starter budget estimates.",
    },
    {
        "slug": "settlement",
        "title": "Post-arrival settlement checklist",
        "category": "arrival",
        "availability": "coming_soon",
        "flag": "SETTLEMENT_MODULE_ENABLED",
        "summary": "Track airport pickup, accommodation, SIM, bank account, tax number, residence registration, school, health insurance, and local transport tasks.",
        "current_support": "The service flow is prepared for route-specific arrival checklists.",
    },
    {
        "slug": "partners",
        "title": "Partner and expert review network",
        "category": "marketplace",
        "availability": "partner_approval_pending",
        "flag": "PARTNER_MARKETPLACE_ENABLED",
        "summary": "Connect users to vetted experts, document reviewers, couriers, insurers, translators, admission support, and settlement providers.",
        "current_support": "The app is structured for provider onboarding and service requests.",
    },
]

MODULE_ENDPOINTS = {
    "opportunities": "Official lottery, ballot, invitation-pool, quota, and capped-route monitoring.",
    "watchlist": "Saved route and opportunity monitoring for users.",
    "alerts": "Email, WhatsApp, Telegram, and in-app notification preferences and logs.",
    "documents": "Document readiness, name consistency, translation, notarization, apostille, and legalization checks.",
    "funds": "Proof-of-funds planning, shortfall tracking, sponsor evidence, and savings targets.",
    "refusal-risk": "Refusal-letter review and refusal-risk repair planning.",
    "courier": "Trusted passport and sensitive-document courier requests.",
    "legalization": "Notarization, apostille, attestation, translation, and embassy legalization service requests.",
    "insurance": "Insurance requirement matching and future quote/provider integrations.",
    "appointments": "Embassy, visa-center, biometrics, submission, and collection timeline tracking.",
    "family-relocation": "Dependent, spouse, children, family funds, insurance, school, and arrival planning.",
    "settlement": "Post-arrival settlement tasks and local-service partner slots.",
    "partners": "Expert review, consultant, courier, insurer, translator, and service-provider integration slots.",
}


def _flag_value(flag_name: Optional[str]) -> bool:
    if not flag_name:
        return False
    return bool(getattr(config, flag_name, False))


def _public_module(module: Dict[str, Any]) -> Dict[str, Any]:
    flag = module.get("flag")
    enabled = _flag_value(flag)
    availability = "available" if enabled else module.get("availability", "coming_soon")
    return {
        "slug": module.get("slug"),
        "title": module.get("title"),
        "category": module.get("category"),
        "availability": availability,
        "enabled": enabled,
        "summary": module.get("summary"),
        "current_support": module.get("current_support"),
    }


def _module_response(slug: str):
    module = next((item for item in PLATFORM_MODULES if item["slug"] == slug), None)
    description = MODULE_ENDPOINTS.get(slug) or (module or {}).get("summary") or "MoveReady platform service."
    public_module = _public_module(module) if module else {"slug": slug, "title": slug.replace("-", " ").title(), "availability": "coming_soon", "enabled": False}
    availability = public_module.get("availability")
    return jsonify({
        "ok": True,
        "availability": availability,
        "module": public_module,
        "message": "This service is being prepared for launch and will be available once official-source checks, provider approval, user consent, and audit rules are ready.",
        "description": description,
        "launch_requirements": [
            "Official-source rules confirmed.",
            "User opt-in and audit trail ready.",
            "Provider approval completed where a partner is required.",
        ],
    })


@bp.get("/status")
def platform_status():
    return jsonify({
        "ok": True,
        "platform": "MoveReady",
        "modules_enabled": config.PLATFORM_MODULES_ENABLED,
        "available_services": ["countries", "routes", "route_detail", "checklist", "budget_estimate", "scholarships", "insurance_requirements", "reports"],
        "services": [_public_module(module) for module in PLATFORM_MODULES],
    })


@bp.get("/modules")
def platform_modules():
    category = (request.args.get("category") or "").strip()
    rows = [_public_module(module) for module in PLATFORM_MODULES]
    if category:
        rows = [row for row in rows if row.get("category") == category]
    return jsonify({"ok": True, "modules": rows})


@bp.get("/modules/<slug>")
def platform_module(slug: str):
    module = next((item for item in PLATFORM_MODULES if item["slug"] == slug), None)
    if not module:
        return jsonify({"ok": False, "error": "module_not_found"}), 404
    return jsonify({"ok": True, "module": _public_module(module)})


@planned_bp.get("/<slug>")
def module_endpoint(slug: str):
    if slug not in MODULE_ENDPOINTS:
        return jsonify({"ok": False, "error": "module_endpoint_not_found"}), 404
    return _module_response(slug)
