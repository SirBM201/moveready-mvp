from __future__ import annotations

from typing import Any, Dict, List, Set

from app.services.supabase_client import get_supabase


PROVIDER_LABELS = {
    "courier": "Courier and document delivery",
    "insurance": "Insurance provider",
    "legalization": "Notary, apostille, attestation, or legalization",
    "translation": "Document translation",
    "expert_review": "Expert or consultant review",
    "admission_support": "Admission or scholarship support",
    "accommodation": "Accommodation support",
    "airport_pickup": "Airport pickup",
    "settlement": "Post-arrival settlement support",
    "travel_booking": "Travel booking support",
    "transport": "Local or intercity transport",
    "telecom": "SIM, connectivity, or telecom support",
    "other": "Other trusted service",
}

NEED_TOKENS = {
    "flight": {"flight", "airline", "ticket", "travel booking"},
    "hotel": {"hotel", "accommodation", "lodging"},
    "short_stay_apartment": {"apartment", "short stay", "accommodation", "airbnb"},
    "airport_pickup": {"airport pickup", "airport transfer", "pickup"},
    "intercity_transport": {"intercity", "transport", "bus", "rail", "train"},
    "travel_insurance": {"travel insurance", "insurance"},
    "local_sim": {"sim", "telecom", "connectivity"},
    "other": set(),
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _provider_matches_needs(service_text: str, requested: Set[str]) -> bool:
    if not requested or requested == {"other"}:
        return True
    for need in requested:
        tokens = NEED_TOKENS.get(need) or {need.replace("_", " ")}
        if any(token in service_text for token in tokens):
            return True
    return False


def approved_travel_providers(target_country: str, needs: List[str]) -> List[Dict[str, Any]]:
    """Return only explicitly published, approved travel-related providers.

    Migration 023 adds public_listing_enabled and publication-review fields. If
    that migration is not present, this function fails closed and returns no
    providers instead of exposing an unreviewed record.
    """
    try:
        response = (
            get_supabase()
            .table("relocation_partner_applications")
            .select(
                "id,provider_type,business_name,website_url,country,city,service_countries,"
                "service_summary,credentials_summary,preferred_contact_channel,status,"
                "public_listing_enabled,privacy_reviewed,pricing_reviewed,refund_policy_reviewed,"
                "sensitive_document_handling_reviewed,affiliate_relationship,affiliate_disclosure,"
                "public_notes,approved_at"
            )
            .eq("status", "approved")
            .eq("public_listing_enabled", True)
            .limit(100)
            .execute()
        )
    except Exception:
        return []

    target = _text(target_country).lower()
    requested = {_text(item).lower() for item in needs if _text(item)}
    providers: List[Dict[str, Any]] = []

    for row in response.data or []:
        if not all(
            bool(row.get(field))
            for field in (
                "privacy_reviewed",
                "pricing_reviewed",
                "refund_policy_reviewed",
                "sensitive_document_handling_reviewed",
            )
        ):
            continue

        provider_type = _text(row.get("provider_type")).lower() or "other"
        label = PROVIDER_LABELS.get(provider_type, "Trusted service")
        summary = _text(row.get("service_summary"))
        service_text = " ".join([provider_type.replace("_", " "), label.lower(), summary.lower()])
        service_countries = [_text(item).lower() for item in (row.get("service_countries") or []) if _text(item)]

        travel_match = provider_type in {"travel_booking", "accommodation", "airport_pickup", "transport", "insurance", "telecom", "settlement", "other"}
        need_match = _provider_matches_needs(service_text, requested)
        country_match = not target or not service_countries or target in service_countries or "global" in service_countries

        if not (travel_match and need_match and country_match):
            continue

        providers.append(
            {
                "id": row.get("id"),
                "provider_type": provider_type,
                "provider_label": label,
                "business_name": row.get("business_name"),
                "website_url": row.get("website_url"),
                "country": row.get("country"),
                "city": row.get("city"),
                "service_countries": row.get("service_countries") or [],
                "service_summary": row.get("service_summary"),
                "credentials_summary": row.get("credentials_summary"),
                "preferred_contact_channel": row.get("preferred_contact_channel"),
                "affiliate_relationship": bool(row.get("affiliate_relationship")),
                "affiliate_disclosure": row.get("affiliate_disclosure"),
                "public_notes": row.get("public_notes"),
                "approval_status": "approved_public",
                "approved_at": row.get("approved_at"),
            }
        )

    return providers[:20]


def apply_travel_provider_publication_patch() -> None:
    from app.routes import travel_planner

    travel_planner._approved_travel_providers = approved_travel_providers
