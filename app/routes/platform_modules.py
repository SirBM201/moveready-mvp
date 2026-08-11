from __future__ import annotations

from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

from app.core import config
from app.services.supabase_client import get_supabase

bp = Blueprint("platform_modules", __name__)
planned_bp = Blueprint("platform_service_modules", __name__)

PLATFORM_MODULES: List[Dict[str, Any]] = [
    {
        "slug": "opportunities",
        "title": "Official ballots and quota opportunities",
        "category": "opportunity_monitoring",
        "availability": "available",
        "flag": "OPPORTUNITY_ALERTS_ENABLED",
        "summary": "Track official lottery, ballot, invitation-pool, quota, and capped routes such as DV, youth mobility, IEC, and country-cap opportunities.",
        "current_support": "The official-opportunities page and API are live. External delivery remains controlled until an approved notification provider is configured.",
    },
    {
        "slug": "watchlist",
        "title": "Route watchlist and alerts",
        "category": "opportunity_monitoring",
        "availability": "available",
        "flag": "WHATSAPP_ALERTS_ENABLED",
        "summary": "Let users save routes and receive email, WhatsApp, Telegram, or in-app alerts when an opening, deadline, result window, or source change occurs.",
        "current_support": "Users can save watchlist preferences and review verified in-app alerts. External message delivery requires approved credentials, templates, opt-in, and delivery audit.",
    },
    {
        "slug": "source-health",
        "title": "Source freshness and route-version governance",
        "category": "trust_and_sources",
        "availability": "available",
        "flag": None,
        "summary": "Show whether official sources and route versions are current, overdue, low-confidence, or waiting for review.",
        "current_support": "The public source-health page, protected review queue, snapshot recording, content-change alerts, and weekly due-source scan are implemented.",
    },
    {
        "slug": "visa-power",
        "title": "Visa Power and Travel Benefits",
        "category": "passport_index",
        "availability": "available",
        "flag": "VISA_POWER_ENABLED",
        "summary": "Check whether visas a user already holds can unlock easier travel, no separate visa, or simplified entry in selected destinations.",
        "current_support": "Visa Power uses provider-backed passport data, destination checks, and server-side refusal, denied-admission, cancellation, and visa-validity safety gates.",
    },
    {
        "slug": "documents",
        "title": "Document readiness and name consistency",
        "category": "readiness",
        "availability": "available",
        "flag": "DOCUMENT_CHECKS_ENABLED",
        "summary": "Check passport validity, missing documents, name mismatch, translation, notarization, apostille, legalization, and route-specific evidence gaps.",
        "current_support": "The readiness page includes document and name checks. The private Evidence Center adds metadata-only document inventory, expiry tracking, and evidence packs after migration 027.",
    },
    {
        "slug": "evidence",
        "title": "Private Evidence Center",
        "category": "readiness",
        "availability": "available",
        "flag": None,
        "summary": "Organize document metadata, expiry, translation, legalization, route-based evidence packs, and structured refusal repair without uploading raw files.",
        "current_support": "The verified-account Evidence Center and API are implemented. Migration 027 is required for private inventory and evidence-pack storage.",
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
        "title": "Refusal risk and repair planning",
        "category": "risk_review",
        "availability": "available",
        "flag": "REFUSAL_ANALYZER_ENABLED",
        "summary": "Review previous refusals, denied admission, visa status, disclosure readiness, written reasons, and evidence-repair tasks.",
        "current_support": "The readiness screener covers broad risk indicators. The Evidence Center adds structured refusal-repair planning and redaction controls.",
    },
    {
        "slug": "study-planner",
        "title": "Study admission and visa planner",
        "category": "education",
        "availability": "available",
        "flag": None,
        "summary": "Assess academic fit, field changes, regulated careers, tuition, funding, language readiness, family pressure, and application stages.",
        "current_support": "The Study Planner is live and can save planning history to a verified account.",
    },
    {
        "slug": "journey-planner",
        "title": "Application-to-arrival Journey Planner",
        "category": "execution_services",
        "availability": "available",
        "flag": None,
        "summary": "Plan legalization, family relocation, appointments, biometrics, application tasks, and post-arrival settlement.",
        "current_support": "Legalization, family, appointment, and settlement planners are live. Appointment tasks can be saved to the timeline with consent.",
    },
    {
        "slug": "trip-planner",
        "title": "Trip readiness and booking planner",
        "category": "travel",
        "availability": "available",
        "flag": None,
        "summary": "Check entry, transit, passport, visa, accommodation, funds, insurance, family, medical, and prior-admission risks before booking.",
        "current_support": "The Trip Planner is live. Booking handoff remains limited to approved public providers with affiliate disclosure.",
    },
    {
        "slug": "jobs",
        "title": "Jobs execution workspace",
        "category": "employment_execution",
        "availability": "available",
        "flag": None,
        "summary": "Research target employers and recruiters, record vacancies, track applications, manage resume versions, and prepare for interviews.",
        "current_support": "The verified-account Jobs workspace and private Resume Vault are implemented. Migration 031 is required for storage.",
    },
    {
        "slug": "legalization",
        "title": "Notarization, apostille, and legalization",
        "category": "execution_services",
        "availability": "available",
        "flag": "LEGALIZATION_MODULE_ENABLED",
        "summary": "Guide users on whether documents may need notarization, apostille, embassy legalization, translation, or ministry authentication.",
        "current_support": "The Journey Planner has a live legalization planner that refuses to infer the correct authentication path without written receiving-authority confirmation.",
    },
    {
        "slug": "courier",
        "title": "Passport and document courier",
        "category": "execution_services",
        "availability": "partner_approval_pending",
        "flag": "COURIER_MODULE_ENABLED",
        "summary": "Coordinate trusted passport, certificate, embassy, and notarization courier workflows with tracking and insurance options.",
        "current_support": "Service requests, provider applications, quote controls, exact-field consent, and auditable handoff are implemented. A courier must still pass provider approval and publication controls.",
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
        "availability": "available",
        "flag": "APPOINTMENT_TRACKER_ENABLED",
        "summary": "Save embassy, visa centre, biometrics, document submission, collection, and deadline events for user reminders.",
        "current_support": "The Journey Planner generates dated appointment tasks and can save them to the private timeline with consent. External appointment-slot monitoring is not enabled.",
    },
    {
        "slug": "family-relocation",
        "title": "Family relocation planner",
        "category": "readiness",
        "availability": "available",
        "flag": "FAMILY_PLANNER_ENABLED",
        "summary": "Model spouse, children, extra documents, extra funds, accommodation, school, insurance, and arrival tasks per family member.",
        "current_support": "The Journey Planner includes a live household-size, child-age, custody, accommodation, school, insurance, and support-needs planner.",
    },
    {
        "slug": "settlement",
        "title": "Post-arrival settlement checklist",
        "category": "arrival",
        "availability": "available",
        "flag": "SETTLEMENT_MODULE_ENABLED",
        "summary": "Track airport pickup, accommodation, SIM, bank account, tax number, residence registration, school, health insurance, and local transport tasks.",
        "current_support": "The Journey Planner includes a staged before-travel, first-72-hours, first-two-weeks, and first-90-days settlement plan.",
    },
    {
        "slug": "billing",
        "title": "Commercial quotes and controlled payment readiness",
        "category": "commercial",
        "availability": "available",
        "flag": "COMMERCIAL_QUOTES_ENABLED",
        "summary": "Request, issue, review, accept, decline, and audit scope-controlled quotes with separated service and platform fees.",
        "current_support": "Quote workflows are implemented. Checkout remains fail closed while PAYMENT_LINKS_ENABLED is false.",
    },
    {
        "slug": "partners",
        "title": "Partner and expert review network",
        "category": "marketplace",
        "availability": "partner_approval_pending",
        "flag": "PARTNER_MARKETPLACE_ENABLED",
        "summary": "Connect users to vetted experts, document reviewers, couriers, insurers, translators, admission support, and settlement providers.",
        "current_support": "Provider application, screening, publication, quote, consent, handoff, complaint, refund, and dispute controls exist. Public execution requires an approved provider.",
    },
]

MODULE_ENDPOINTS = {
    "opportunities": "Official lottery, ballot, invitation-pool, quota, and capped-route monitoring.",
    "watchlist": "Saved route and opportunity monitoring for users.",
    "alerts": "Email, WhatsApp, Telegram, and in-app notification preferences and logs.",
    "source-health": "Official-source freshness, route-version review dates, and source-change governance.",
    "visa-power": "Passport index and existing-visa travel-benefit rules with official source records.",
    "documents": "Document readiness, name consistency, translation, notarization, apostille, and legalization checks.",
    "evidence": "Private metadata-only document inventory, evidence packs, expiry tracking, and refusal repair.",
    "funds": "Proof-of-funds planning, shortfall tracking, sponsor evidence, and savings targets.",
    "refusal-risk": "Refusal, denied-admission, visa-status, disclosure, and repair planning.",
    "study-planner": "Admission, academic fit, regulated career, funding, and study-visa preparation.",
    "journey-planner": "Legalization, family, appointment, and settlement planning.",
    "trip-planner": "Trip readiness and controlled booking-provider handoff.",
    "jobs": "Private company, recruiter, vacancy, application, resume, and interview-preparation execution.",
    "courier": "Trusted passport and sensitive-document courier requests.",
    "legalization": "Notarization, apostille, attestation, translation, and embassy legalization planning.",
    "insurance": "Insurance requirement matching and future quote/provider integrations.",
    "appointments": "Embassy, visa-centre, biometrics, submission, and collection timeline tracking.",
    "family-relocation": "Dependent, spouse, children, family funds, insurance, school, and arrival planning.",
    "settlement": "Post-arrival settlement tasks and local-service partner slots.",
    "billing": "Commercial quote, acceptance, payment-audit, refund, and dispute controls.",
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


def _payload_metadata(payload: Dict[str, Any]) -> Dict[str, Any]:
    metadata = payload.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


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
            "Private database migration applied where account storage is used.",
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
            "report_lookup",
            "admin_generated_reports",
            "opportunities",
            "source_health",
            "source_governance_queue",
            "visa_power_options",
            "visa_power_check",
            "watchlist_options",
            "watchlist_subscriptions",
            "saved_routes",
            "timeline_events",
            "name_consistency",
            "document_readiness",
            "document_inventory",
            "evidence_packs",
            "funds_plan",
            "refusal_risk",
            "refusal_repair_plan",
            "study_planner",
            "journey_planner",
            "trip_planner",
            "commercial_quotes",
            "provider_handoffs",
            "support_cases",
            "service_interest_requests",
            "partner_applications",
            "user_profiles",
            "profile_readiness_snapshot",
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
    metadata = {
        **_payload_metadata(payload),
        "user_agent": request.headers.get("User-Agent"),
        "remote_addr": request.headers.get("X-Forwarded-For") or request.remote_addr,
        "module_availability": (module or {}).get("availability"),
    }
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
        "metadata": metadata,
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
