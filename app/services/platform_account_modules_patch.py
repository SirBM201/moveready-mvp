from __future__ import annotations

from typing import Any, Dict, List

from app.routes import platform_modules


ACCOUNT_MODULES: List[Dict[str, Any]] = [
    {
        "slug": "onboarding",
        "title": "Guided relocation account setup",
        "category": "account",
        "availability": "available",
        "flag": None,
        "summary": "Guide a verified user through profile, route, evidence, application, and alert foundations without guessing which tool to open next.",
        "current_support": "The guided setup page and saved onboarding progress are implemented after migration 030.",
    },
    {
        "slug": "my-journey",
        "title": "Private end-to-end journey overview",
        "category": "account",
        "availability": "available",
        "flag": None,
        "summary": "Turn verified account records into a truthful narrative from profile and route selection through evidence, application, decision, and settlement.",
        "current_support": "My Journey reads the existing account summary and Action Center. It does not assume missing records are complete or create another data store.",
    },
    {
        "slug": "action-center",
        "title": "Private ranked Action Center",
        "category": "account",
        "availability": "available",
        "flag": None,
        "summary": "Rank deadlines, application risks, document expiry, evidence gaps, timeline tasks, quotes, provider handoffs, support, and privacy actions in one verified-account view.",
        "current_support": "The Action Center reads existing private records without creating a duplicate data store or activating external notifications.",
    },
    {
        "slug": "application-center",
        "title": "Private Application Case Manager",
        "category": "application_execution",
        "availability": "available",
        "flag": None,
        "summary": "Track a real application from research through appointment, submission, biometrics, document requests, decision, and closure.",
        "current_support": "The verified-account Application Center, case events, masked references, evidence linkage, timeline reminders, and protected administrator console are implemented after migration 028.",
    },
    {
        "slug": "application-alerts",
        "title": "Private application deadline and risk alerts",
        "category": "application_execution",
        "availability": "available",
        "flag": None,
        "summary": "Generate private in-app alerts for overdue or near deadlines, appointments, additional-document requests, source status, payments, refusal follow-up, and post-decision actions.",
        "current_support": "The verified inbox, protected review console, deduplication, automatic resolution, and daily scan are implemented after migration 029. External delivery remains controlled.",
    },
    {
        "slug": "account-activity",
        "title": "Unified private account activity",
        "category": "account",
        "availability": "available",
        "flag": None,
        "summary": "Show account-owned profile, route, evidence, application, alert, report, quote, handoff, support, timeline, and privacy activity in one chronological feed.",
        "current_support": "The verified activity API and filterable activity page are implemented after migration 030.",
    },
    {
        "slug": "account-settings",
        "title": "Account settings, accessibility, security, and privacy",
        "category": "account",
        "availability": "available",
        "flag": None,
        "summary": "Manage localization, accessibility, notification consent, active sessions, safe data export, and reviewed privacy requests.",
        "current_support": "Preferences, session revocation, JSON export, privacy requests, and protected privacy administration are implemented after migration 030. Email and WhatsApp preferences do not activate delivery by themselves.",
    },
]


def apply_platform_account_modules_patch() -> None:
    existing = {str(item.get("slug") or "") for item in platform_modules.PLATFORM_MODULES}
    for module in ACCOUNT_MODULES:
        if module["slug"] not in existing:
            platform_modules.PLATFORM_MODULES.append(module)
            existing.add(module["slug"])

    platform_modules.MODULE_ENDPOINTS.update(
        {
            "onboarding": "Guided verified-account setup across profile, route, evidence, applications, and alerts.",
            "my-journey": "Private narrative journey progress derived from account records without assuming missing stages are complete.",
            "action-center": "Ranked private next actions derived from existing applications, alerts, evidence, documents, timelines, quotes, handoffs, support, and privacy records.",
            "application-center": "Private application lifecycle, authority, evidence, deadline, fee, source, event, and decision tracking.",
            "application-alerts": "Private application deadline, source, payment, refusal, and post-decision alert inbox.",
            "account-activity": "Unified verified-account activity history without raw documents or security credentials.",
            "account-settings": "Localization, accessibility, notification consent, session security, data export, and privacy requests.",
        }
    )
