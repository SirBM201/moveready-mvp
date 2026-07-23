from __future__ import annotations

from typing import Any, Dict


_PATCH_APPLIED = False


MODULE_UPDATES: Dict[str, Dict[str, Any]] = {
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


def apply_journey_module_patch() -> None:
    global _PATCH_APPLIED
    if _PATCH_APPLIED:
        return

    from app.routes import platform_modules

    existing = {str(item.get("slug")): item for item in platform_modules.PLATFORM_MODULES}
    for slug, updates in MODULE_UPDATES.items():
        module = existing.get(slug)
        if module:
            module.update(updates)

    if "journey-planner" not in existing:
        platform_modules.PLATFORM_MODULES.append(dict(JOURNEY_MODULE))

    platform_modules.MODULE_ENDPOINTS["journey-planner"] = (
        "Document legalization, family relocation, appointment preparation, timeline storage, and post-arrival settlement planning."
    )
    platform_modules.PLATFORM_JOURNEY_PATCH_ACTIVE = True
    _PATCH_APPLIED = True
