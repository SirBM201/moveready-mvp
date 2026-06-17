from __future__ import annotations

from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

from app.core import config
from app.services.supabase_client import get_supabase

bp = Blueprint("platform_modules", __name__)
planned_bp = Blueprint("planned_platform_modules", __name__)

PLATFORM_MODULES: List[Dict[str, Any]] = [
    {
        "slug": "opportunities",
        "title": "Official ballots and quota opportunities",
        "category": "opportunity_monitoring",
        "availability": "available",
        "flag": "OPPORTUNITY_ALERTS_ENABLED",
        "summary": "Track official lottery, ballot, invitation-pool, quota, and capped routes such as DV, youth mobility, IEC, and country-cap opportunities.",
        "current_support": "The official-opportunities page and API are live. The database-backed list activates fully after the opportunities SQL is run.",
    },
    {
        "slug": "watchlist",
        "title": "Route watchlist and alerts",
        "category": "opportunity_monitoring",
        "availability": "coming_soon",
        "flag": "WHATSAPP_ALERTS_ENABLED",
        "summary": "Let users save routes and receive email, WhatsApp, Telegram, or in-app alerts when an opening, deadline, result window, or source change occurs.",
        "current_support": "Users can already submit service requests for route alerts and WhatsApp notification interest.",
    },
    {
        "slug": "documents",
        "title": "Document readiness and name consistency",
        "category": "readiness",
        "availability": "available",
        "flag": "DOCUMENT_CHECKS_ENABLED",
        "summary": "Check passport validity, missing documents, name mismatch, translation, notarization, apostille, legalization, and route-specific evidence gaps.",
        "current_support": "The readiness tools page includes live document and name checks through the backend.",
    },
    {
        "slug": "funds",
        "title": "Proof-of-funds planner",
        "category": "readiness",
        "availability": "available",
        "flag": "PROOF_OF_FUNDS_PLANNER_ENABLED",
        "summary": "Track required funds, available funds, shortfall, savings target, sponsor evidence, family-size adjustment, and large-deposit risk.",
        "current_support": "The readiness tools page includes a live proof-of-funds planner through the backend.",
    },
    {
        "slug": "refusal-risk",
        "title": "Refusal risk analyzer",
        "category": "risk_review",
        "availability": "available",
        "flag": "REFUSAL_ANALYZER_ENABLED",
        "summary": "Review previous refusals and weak application indicators such as unclear purpose, low funds, weak home ties, incomplete evidence, or wrong route selection.",
        "current_support": "The readiness tools page includes a live refusal-risk screener through the backend.",
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
        "current_support": "The service request form is live for early interest while trusted provider onboarding is handled.",
    },
    {
        "slug": "insurance",
        "title": "Insurance readiness and partners",
        "category": "execution_services",
        "availability": "available",
        "flag": "INSURANCE_PARTNER_ENABLED",
        "summary": "Track travel, health, student, family, work-permit, and Schengen-style insurance requirements and future partner quotes.",
        "current_support": "The insurance guide and backend insurance requirement endpoint are live. Partner quotes require approved providers.",
    },
    {
        "slug": "appointments",
        "title": "Embassy and application appointment tracker",
        "category": "timeline",
        "availability": "coming_soon",
        "flag": "APPOINTMENT_TRACKER_ENABLED",
        "summary": "Save embassy, visa center, biometrics, document submission, collection, and deadline events for user reminders.",
        "current_support": "Users can request this service while manual timeline tracking and reminders are prepared.",
    },
    {
        "slug": "family-relocation",
        "title": "Family relocation planner",
        "category": "readiness",
        "availability": "coming_soon",
        "flag": "FAMILY_PLANNER_ENABLED",
        "summary": "Model spouse, children, extra documents, extra funds, accommodation, school, insurance, and arrival tasks per family member.",
        "current_support": "Family count already affects starter budget estimates in the route checker.",
    },
    {
        "slug": "settlement",
        "title": "Post-arrival settlement checklist",
        "category": "arrival",
        "availability": "coming_soon",
        "flag": "SETTLEMENT_MODULE_ENABLED",
        "summary": "Track airport pickup, accommodation, SIM, bank account, tax number, residence registration, school, health insurance, and local transport tasks.",
        "current_support": "Users can request post-arrival support while route-specific arrival checklists are prepared.",
    },
    {
        "slug": "partners",
        "title": "Partner and expert review network",
        "category": "marketplace",
        "availability": "partner_approval_pending",
        "flag": "PARTNER_MARKETPLACE_ENABLED",
        "summary": "Connect users to vetted experts, document reviewers, couriers, insurers, translators, admission support, and settlement providers.",
        "current_support": "The app has service request capture and an admin dashboard for reviewing provider/service interest.",
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


def _clean_text(value: Any, limit: int = 500) -> Optional[str]:
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    return cleaned[:limit]


def _public_module(module: Dict[str, Any]) -> Dict[str, Any]:
    flag = module.get("flag")
    enabled = _flag_value(flag)
    availability = "available" if enabled else module.get("availability", "coming_soon")
    return {
        "slug": module.get("slug"),
        "title": module.get("title"),
        "category": module.get("category"),
        "availability": availability,
        "enabled": availability == "available" or enabled,
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
        "message": "This service is available now or being prepared for public access, depending on its status label.",
        "description": description,
        "activation_requirements": [
            "Official-source rules confirmed where required.",
            "User opt-in and audit trail ready where notifications are used.",
            "Provider approval completed where a partner is required.",
        ],
    })


@bp.get("/status")
def platform_status():
    return jsonify({
        "ok": True,
        "platform": "MoveReady",
        "modules_enabled": config.PLATFORM_MODULES_ENABLED,
        "available_services": [
            "countries",
            "routes",
            "route_detail",
            "checklist",
            "budget_estimate",
            "scholarships",
            "insurance_requirements",
            "reports",
            "opportunities",
            "name_consistency",
            "document_readiness",
            "funds_plan",
            "refusal_risk",
            "service_interest_requests",
        ],
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


@bp.post("/service-interest")
def create_service_interest():
    payload = request.get_json(silent=True) or {}
    service_slug = _clean_text(payload.get("service_slug"), 120)
    email = _clean_text(payload.get("email"), 255)
    phone = _clean_text(payload.get("phone"), 80)
    consent_to_contact = bool(payload.get("consent_to_contact"))

    if not service_slug:
        return jsonify({"ok": False, "error": "service_slug_required"}), 400
    if not email and not phone:
        return jsonify({"ok": False, "error": "contact_required"}), 400
    if not consent_to_contact:
        return jsonify({"ok": False, "error": "contact_consent_required"}), 400

    module = next((item for item in PLATFORM_MODULES if item["slug"] == service_slug), None)
    row = {
        "service_slug": service_slug,
        "service_title": _clean_text(payload.get("service_title"), 180) or (module or {}).get("title"),
        "full_name": _clean_text(payload.get("full_name"), 180),
        "email": email,
        "phone": phone,
        "preferred_channel": _clean_text(payload.get("preferred_channel"), 40) or "email",
        "current_country": _clean_text(payload.get("current_country"), 120),
        "target_country": _clean_text(payload.get("target_country"), 120),
        "route_or_goal": _clean_text(payload.get("route_or_goal"), 180),
        "message": _clean_text(payload.get("message"), 1200),
        "consent_to_contact": consent_to_contact,
        "source_page": _clean_text(payload.get("source_page"), 240),
        "metadata": {
            "user_agent": request.headers.get("User-Agent"),
            "remote_addr": request.headers.get("X-Forwarded-For") or request.remote_addr,
            "module_availability": (module or {}).get("availability"),
        },
    }

    try:
        response = get_supabase().table("relocation_service_interest_requests").insert(row).execute()
        stored = (response.data or [None])[0]
        return jsonify({"ok": True, "stored": True, "request": stored})
    except Exception as exc:
        return jsonify({
            "ok": False,
            "stored": False,
            "error": "service_interest_storage_unavailable",
            "details": str(exc),
        }), 503


@planned_bp.get("/<slug>")
def module_endpoint(slug: str):
    if slug not in MODULE_ENDPOINTS:
        return jsonify({"ok": False, "error": "module_endpoint_not_found"}), 404
    return _module_response(slug)
