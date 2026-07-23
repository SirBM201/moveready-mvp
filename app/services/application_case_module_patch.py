from __future__ import annotations

from app.routes import platform_modules


def apply_application_case_module_patch() -> None:
    existing = next((item for item in platform_modules.PLATFORM_MODULES if item.get("slug") == "applications"), None)
    if not existing:
        platform_modules.PLATFORM_MODULES.append(
            {
                "slug": "applications",
                "title": "Private Application Case Manager",
                "category": "application_execution",
                "availability": "available",
                "flag": None,
                "summary": "Track a verified account application from research to decision with route, evidence, authority, appointment, deadline, fee, source, event, and decision metadata.",
                "current_support": "The private Application Center, administrator deadline queue, event history, masked reference protection, evidence-pack links, and consent-based timeline tasks are implemented. Migration 028 is required for storage.",
            }
        )
    else:
        existing.update(
            {
                "availability": "available",
                "summary": "Track a verified account application from research to decision with route, evidence, authority, appointment, deadline, fee, source, event, and decision metadata.",
                "current_support": "The private Application Center, administrator deadline queue, event history, masked reference protection, evidence-pack links, and consent-based timeline tasks are implemented. Migration 028 is required for storage.",
            }
        )

    platform_modules.MODULE_ENDPOINTS["applications"] = (
        "Private application lifecycle, deadline, source, evidence, fee, payment, event, and decision tracking."
    )
