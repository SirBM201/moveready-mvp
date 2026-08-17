from __future__ import annotations

from typing import Any, Dict, List

from app.services.passport_index_provider import clean_text
from app.services.supabase_client import get_supabase


_ALLOWED_SOURCE_TYPES = {"government", "embassy"}


def _rows(response: Any) -> List[Dict[str, Any]]:
    return [row for row in (getattr(response, "data", None) or []) if isinstance(row, dict)]


def _destination_country(destination: str) -> Dict[str, Any] | None:
    db = get_supabase()
    exact = (
        db.table("relocation_countries")
        .select("id,country_name")
        .eq("country_name", destination)
        .limit(1)
        .execute()
    )
    rows = _rows(exact)
    if rows:
        return rows[0]
    try:
        fallback = (
            db.table("relocation_countries")
            .select("id,country_name")
            .ilike("country_name", destination)
            .limit(1)
            .execute()
        )
        rows = _rows(fallback)
        return rows[0] if rows else None
    except Exception:
        return None


def official_sources_for_destination(destination: str) -> List[Dict[str, Any]]:
    """Return the limited public government/embassy mapping contract.

    This deliberately keeps provider evidence separate from MoveReady's trusted
    source layer. Pending-review mappings are visible as candidates but are not
    described as verified. Any missing/partially deployed mapping schema fails
    closed to an empty list so Passport detail remains available.
    """
    destination = clean_text(destination, 180)
    if not destination:
        return []

    try:
        country = _destination_country(destination)
        if not country or not country.get("id"):
            return []

        mappings = _rows(
            get_supabase()
            .table("relocation_passport_official_source_mappings")
            .select("source_id,purpose,priority,status,verification_status,verified_at,review_due_at,notes")
            .eq("destination_country_id", country["id"])
            .neq("status", "retired")
            .order("priority")
            .execute()
        )
        if not mappings:
            return []

        output: List[Dict[str, Any]] = []
        for mapping in mappings:
            source_id = mapping.get("source_id")
            if not source_id:
                continue
            source_rows = _rows(
                get_supabase()
                .table("relocation_trusted_sources")
                .select("id,source_name,owner_organization,source_type,reliability_level,status,source_url")
                .eq("id", source_id)
                .limit(1)
                .execute()
            )
            if not source_rows:
                continue
            source = source_rows[0]
            source_type = clean_text(source.get("source_type"), 40).lower()
            if source_type not in _ALLOWED_SOURCE_TYPES or source.get("status") == "retired":
                continue

            verification_status = clean_text(mapping.get("verification_status"), 40) or "pending_review"
            output.append(
                {
                    "source_name": clean_text(source.get("source_name"), 240),
                    "organization": clean_text(source.get("owner_organization"), 240),
                    "source_type": source_type,
                    "source_url": clean_text(source.get("source_url"), 700),
                    "reliability_level": clean_text(source.get("reliability_level"), 40),
                    "purpose": clean_text(mapping.get("purpose"), 80),
                    "priority": mapping.get("priority"),
                    "verification_status": verification_status,
                    "verified": verification_status == "verified",
                    "verified_at": mapping.get("verified_at") if verification_status == "verified" else None,
                    "review_due_at": mapping.get("review_due_at"),
                }
            )
        return output
    except Exception:
        return []


def enrich_destination_result(result: Dict[str, Any]) -> Dict[str, Any]:
    enriched = dict(result or {})
    destination = clean_text(enriched.get("destination"), 180)
    detail = enriched.get("detail") if isinstance(enriched.get("detail"), dict) else {}
    if not destination:
        destination = clean_text(detail.get("destination"), 180)

    sources = official_sources_for_destination(destination)
    enriched["official_sources"] = sources
    enriched["official_source_layer"] = {
        "status": "available" if sources else "not_available",
        "verified_count": sum(1 for source in sources if source.get("verified")),
        "candidate_count": len(sources),
        "trust_rule": "Only government/embassy mappings with verification_status=verified are MoveReady-verified official sources.",
    }
    return enriched
