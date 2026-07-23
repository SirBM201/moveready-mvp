from __future__ import annotations

from typing import Any, Dict


_PATCH_APPLIED = False


MODULE_UPDATES: Dict[str, Dict[str, Any]] = {
    "watchlist": {
        "availability": "available",
        "summary": "Save opt-in watches and review current in-app source alerts from a verified account.",
        "current_support": "The verified in-app inbox matches active watches to stored public opportunity records, shows source-review status, and links back to official pages. External email, WhatsApp, Telegram, or phone delivery remains disabled or controlled until credentials and approvals are ready.",
    },
    "legalization": {
        "availability": "available",
        "summary": "Organize translation, notarization, authentication, apostille, and embassy-legalization steps from confirmed receiving-authority instructions.",
        "current_support": "The live legalization planner generates an ordered document path, risk label, warnings, and source-confirmation questions. Provider handoff remains screened.",
    },
    "appointments": {
        "availability": "available",
        "summary": "Work backwards from embassy, visa-centre, biometrics, interview, submission, payment, or passport-collection dates.",
        "current_support": "The live appointment planner generates dated preparation tasks and can save them into the existing timeline with user consent.",
    },
    "family-relocation": {
        "availability": "available",
        "summary": "Plan spouse, children, other dependants, funds pressure, accommodation, insurance, school, custody, medical, and arrival tasks.",
        "current_support": "The live family planner produces member-level document checklists, warnings, household tasks, and a non-official planning-budget multiplier.",
    },
    "settlement": {
        "availability": "available",
        "summary": "Generate a staged before-travel, first-72-hours, first-two-weeks, and first-90-days settlement checklist.",
        "current_support": "The live settlement planner covers housing, connectivity, registration, banking, tax, health, school, transport, work, family, medical, pet, and fraud checks. Partner handoff remains approval-gated.",
    },
    "partners": {
        "availability": "partner_approval_pending",
        "summary": "Connect users only to providers that pass application screening and separate public-publication controls.",
        "current_support": "Provider applications, admin screening, privacy review, pricing review, refund review, sensitive-document handling review, affiliate disclosure, and explicit public-listing approval are implemented. No provider is public merely because an application status is approved.",
    },
}


JOURNEY_MODULE = {
    "slug": "journey-planner",
    "title": "Application-to-arrival Journey Planner",
    "category": "journey_management",
    "availability": "available",
    "flag": None,
    "summary": "Organize document legalization, family relocation, appointments, and post-arrival settlement in one source-first workspace.",
    "current_support": "Four live backend planners return risk labels, checklists, dated actions, warnings, optional timeline storage, and readiness-run persistence.",
}


STUDY_MODULE = {
    "slug": "study-planner",
    "title": "Study Admission and Visa Planner",
    "category": "education_planning",
    "availability": "available",
    "flag": None,
    "summary": "Assess academic fit, field changes, language evidence, affordability, scholarship dependency, intake timing, family pressure, refusals, and regulated-career risk.",
    "current_support": "The live planner generates programme-search strategy, application stages, evidence, funding-gap warnings, study-visa preparation, family tasks, and verified account storage without promising admission, scholarship, visa, work rights, licensing, or permanent residence.",
}


TRIP_MODULE = {
    "slug": "trip-planner",
    "title": "Trip Readiness and Booking Planner",
    "category": "travel_planning",
    "availability": "available",
    "flag": None,
    "summary": "Check passport, visa, authorization, transit, insurance, accommodation, funds, family, medical, and immigration-history risks before comparing travel bookings.",
    "current_support": "The live neutral planner returns booking readiness, warnings, a five-stage booking sequence, fraud checks, affiliate disclosure, and approved-provider handoff without claiming live inventory, price, refund, boarding, or entry permission.",
}


BILLING_MODULE = {
    "slug": "billing",
    "title": "Commercial Quotes and Payment Controls",
    "category": "commercial_operations",
    "availability": "available",
    "flag": None,
    "summary": "Request and review scope-based quotes with deliverables, exclusions, provider, separated service and platform fees, expiry, refund terms, acceptance, and payment status.",
    "current_support": "Verified account quote review, acceptance, decline, admin issuance, audit events, and manual payment verification are implemented. Checkout links remain disabled until PAYMENT_LINKS_ENABLED is explicitly activated after approved payment setup.",
}


def apply_journey_module_patch() -> None:
    global _PATCH_APPLIED
    if _PATCH_APPLIED:
        return

    from app.routes import account, admin_review_queue, platform_modules

    existing = {str(item.get("slug")): item for item in platform_modules.PLATFORM_MODULES}
    for slug, updates in MODULE_UPDATES.items():
        module = existing.get(slug)
        if module:
            module.update(updates)

    for module in (JOURNEY_MODULE, STUDY_MODULE, TRIP_MODULE, BILLING_MODULE):
        if module["slug"] not in existing:
            platform_modules.PLATFORM_MODULES.append(dict(module))

    platform_modules.MODULE_ENDPOINTS["journey-planner"] = (
        "Document legalization, family relocation, appointment preparation, timeline storage, and post-arrival settlement planning."
    )
    platform_modules.MODULE_ENDPOINTS["study-planner"] = (
        "Academic fit, funding, admission, study-visa, family, regulated-career, and arrival preparation."
    )
    platform_modules.MODULE_ENDPOINTS["trip-planner"] = (
        "Trip permission, transit, document, booking, fraud, affiliate-disclosure, and approved-provider handoff planning."
    )
    platform_modules.MODULE_ENDPOINTS["billing"] = (
        "Scope-controlled commercial quotes, separated fees, refund terms, acceptance, audit history, and gated checkout."
    )
    platform_modules.MODULE_ENDPOINTS["watchlist"] = (
        "Verified in-app source alerts are available now. External message delivery remains operationally gated."
    )
    platform_modules.MODULE_ENDPOINTS["partners"] = (
        "Provider screening and explicit public-publication controls are available. User handoff remains approval-gated."
    )

    if hasattr(account, "PLANNING_TOOL_SLUGS"):
        account.PLANNING_TOOL_SLUGS.add("trip_readiness_plan")
    if hasattr(admin_review_queue, "JOURNEY_TOOL_SLUGS"):
        admin_review_queue.JOURNEY_TOOL_SLUGS.add("trip_readiness_plan")

    platform_modules.PLATFORM_JOURNEY_PATCH_ACTIVE = True
    _PATCH_APPLIED = True
