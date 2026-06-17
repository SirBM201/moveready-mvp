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
        "phase": "phase_2",
        "status": "planned",
        "flag": "OPPORTUNITY_ALERTS_ENABLED",
        "summary": "Track official lottery, ballot, invitation-pool, quota, and capped routes such as DV, youth mobility, IEC, and country-cap opportunities.",
        "live_mvp_behavior": "Show planned route categories, scam warnings, and official-source requirements before alerts are activated.",
    },
    {
        "slug": "watchlist",
        "title": "Route watchlist and alerts",
        "category": "opportunity_monitoring",
        "phase": "phase_2",
        "status": "planned",
        "flag": "WHATSAPP_ALERTS_ENABLED",
        "summary": "Let users save routes and receive email, WhatsApp, Telegram, or in-app alerts when an opening, deadline, result window, or source change occurs.",
        "live_mvp_behavior": "Collect the product shape now; notification providers stay disabled until opt-in and provider setup are complete.",
    },
    {
        "slug": "documents",
        "title": "Document readiness and name consistency",
        "category": "readiness",
        "phase": "phase_2",
        "status": "planned",
        "flag": "DOCUMENT_CHECKS_ENABLED",
        "summary": "Check passport validity, missing documents, name mismatch, translation, notarization, apostille, legalization, and route-specific evidence gaps.",
        "live_mvp_behavior": "Use route checklists now; upload/scanning and automated checks come later.",
    },
    {
        "slug": "funds",
        "title": "Proof-of-funds planner",
        "category": "readiness",
        "phase": "phase_2",
        "status": "planned",
        "flag": "PROOF_OF_FUNDS_PLANNER_ENABLED",
        "summary": "Track required funds, available funds, shortfall, savings target, sponsor evidence, family-size adjustment, and large-deposit risk.",
        "live_mvp_behavior": "Budget estimates are live; deeper funds planning stays planned until the schema and rules are expanded.",
    },
    {
        "slug": "refusal-risk",
        "title": "Refusal risk analyzer",
        "category": "risk_review",
        "phase": "phase_2",
        "status": "planned",
        "flag": "REFUSAL_ANALYZER_ENABLED",
        "summary": "Review previous refusals and weak application indicators such as unclear purpose, low funds, weak home ties, incomplete evidence, or wrong route selection.",
        "live_mvp_behavior": "Surface honest risk labels now; refusal-letter upload and expert review come later.",
    },
    {
        "slug": "legalization",
        "title": "Notarization, apostille, and legalization",
        "category": "execution_services",
        "phase": "phase_2",
        "status": "planned",
        "flag": "LEGALIZATION_MODULE_ENABLED",
        "summary": "Guide users on whether documents need notarization, apostille, embassy legalization, translation, or ministry authentication.",
        "live_mvp_behavior": "Show route-level document notes now; provider workflows remain disabled.",
    },
    {
        "slug": "courier",
        "title": "Passport and document courier",
        "category": "execution_services",
        "phase": "phase_3",
        "status": "partner_pending",
        "flag": "COURIER_MODULE_ENABLED",
        "summary": "Coordinate trusted passport, certificate, embassy, and notarization courier workflows with tracking and insurance options.",
        "live_mvp_behavior": "Keep the service slot visible internally; booking and partner pricing come later.",
    },
    {
        "slug": "insurance",
        "title": "Insurance readiness and partners",
        "category": "execution_services",
        "phase": "phase_2",
        "status": "planned",
        "flag": "INSURANCE_PARTNER_ENABLED",
        "summary": "Track travel, health, student, family, work-permit, and Schengen-style insurance requirements and future partner quotes.",
        "live_mvp_behavior": "Insurance requirements endpoint is live; quote providers stay disabled.",
    },
    {
        "slug": "appointments",
        "title": "Embassy and application appointment tracker",
        "category": "timeline",
        "phase": "phase_2",
        "status": "planned",
        "flag": "APPOINTMENT_TRACKER_ENABLED",
        "summary": "Save embassy, visa center, biometrics, document submission, collection, and deadline events for user reminders.",
        "live_mvp_behavior": "No external appointment monitoring yet; manual timeline tracking comes first.",
    },
    {
        "slug": "family-relocation",
        "title": "Family relocation planner",
        "category": "readiness",
        "phase": "phase_2",
        "status": "planned",
        "flag": "FAMILY_PLANNER_ENABLED",
        "summary": "Model spouse, children, extra documents, extra funds, accommodation, school, insurance, and arrival tasks per family member.",
        "live_mvp_behavior": "Family count already affects starter budget estimates; detailed dependent planning comes later.",
    },
    {
        "slug": "settlement",
        "title": "Post-arrival settlement checklist",
        "category": "arrival",
        "phase": "phase_3",
        "status": "planned",
        "flag": "SETTLEMENT_MODULE_ENABLED",
        "summary": "Track airport pickup, accommodation, SIM, bank account, tax number, residence registration, school, health insurance, and local transport tasks.",
        "live_mvp_behavior": "Keep as a future module until pre-arrival readiness is stable.",
    },
    {
        "slug": "partners",
        "title": "Partner and expert review network",
        "category": "marketplace",
        "phase": "phase_3",
        "status": "partner_pending",
        "flag": "PARTNER_MARKETPLACE_ENABLED",
        "summary": "Connect users to vetted experts, document reviewers, couriers, insurers, translators, admission support, and settlement providers.",
        "live_mvp_behavior": "No marketplace claims yet; only the integration slot is defined.",
    },
]

PLANNED_ENDPOINTS = {
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
    "settlement": "Post-arrival settlement tasks and future local-service partner slots.",
    "partners": "Expert review, consultant, courier, insurer, translator, and service-provider integration slots.",
}


def _flag_value(flag_name: Optional[str]) -> bool:
    if not flag_name:
        return False
    return bool(getattr(config, flag_name, False))


def _with_flags(module: Dict[str, Any]) -> Dict[str, Any]:
    flag = module.get("flag")
    enabled = _flag_value(flag)
    return {
        **module,
        "enabled": enabled,
        "public_status": "available" if enabled else module.get("status", "planned"),
    }


def _planned_response(slug: str):
    module = next((item for item in PLATFORM_MODULES if item["slug"] == slug), None)
    description = PLANNED_ENDPOINTS.get(slug) or (module or {}).get("summary") or "Planned MoveReady platform module."
    return jsonify({
        "ok": True,
        "status": "planned",
        "module": _with_flags(module) if module else {"slug": slug, "title": slug.replace("-", " ").title(), "enabled": False},
        "message": "This module is part of the platform architecture but is not active for production use yet.",
        "description": description,
        "next_steps": [
            "Define official-source rules and data model.",
            "Add user opt-in, audit, and admin review workflow.",
            "Enable provider integration only after compliance and testing.",
        ],
    })


@bp.get("/status")
def platform_status():
    return jsonify({
        "ok": True,
        "platform": "MoveReady",
        "architecture_batch": "2A",
        "modules_enabled": config.PLATFORM_MODULES_ENABLED,
        "active_mvp_modules": ["countries", "routes", "route_detail", "checklist", "budget_estimate", "scholarships", "insurance_requirements", "reports"],
        "planned_modules": [_with_flags(module) for module in PLATFORM_MODULES],
    })


@bp.get("/modules")
def platform_modules():
    category = (request.args.get("category") or "").strip()
    rows = [_with_flags(module) for module in PLATFORM_MODULES]
    if category:
        rows = [row for row in rows if row.get("category") == category]
    return jsonify({"ok": True, "modules": rows})


@bp.get("/modules/<slug>")
def platform_module(slug: str):
    module = next((item for item in PLATFORM_MODULES if item["slug"] == slug), None)
    if not module:
        return jsonify({"ok": False, "error": "module_not_found"}), 404
    return jsonify({"ok": True, "module": _with_flags(module)})


@planned_bp.get("/<slug>")
def planned_module_endpoint(slug: str):
    if slug not in PLANNED_ENDPOINTS:
        return jsonify({"ok": False, "error": "planned_endpoint_not_found"}), 404
    return _planned_response(slug)
