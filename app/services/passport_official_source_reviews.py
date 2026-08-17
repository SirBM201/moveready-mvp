from __future__ import annotations

from typing import Any, Dict, List

from app.services.passport_index_provider import clean_text
from app.services.supabase_client import get_supabase

_ALLOWED_DECISIONS = {"verified", "needs_review", "retired"}


def _rows(response: Any) -> List[Dict[str, Any]]:
    return [row for row in (getattr(response, "data", None) or []) if isinstance(row, dict)]


def list_review_candidates(status: str = "", limit: int = 100) -> List[Dict[str, Any]]:
    db = get_supabase()
    query = db.table("relocation_passport_official_source_mappings").select(
        "id,destination_country_id,source_id,purpose,priority,status,verification_status,verified_at,review_due_at,notes,updated_at"
    ).order("priority").limit(max(1, min(int(limit or 100), 250)))
    normalized = clean_text(status, 40).lower()
    if normalized:
        query = query.eq("verification_status", normalized)
    mappings = _rows(query.execute())
    output: List[Dict[str, Any]] = []
    for mapping in mappings:
        source_rows = _rows(
            db.table("relocation_trusted_sources")
            .select("id,source_name,owner_organization,source_type,reliability_level,status,source_url")
            .eq("id", mapping.get("source_id"))
            .limit(1).execute()
        )
        country_rows = _rows(
            db.table("relocation_countries").select("id,country_name")
            .eq("id", mapping.get("destination_country_id")).limit(1).execute()
        )
        source = source_rows[0] if source_rows else {}
        country = country_rows[0] if country_rows else {}
        output.append({**mapping, "destination_country": country.get("country_name"), "source": source})
    return output


def review_history(mapping_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    return _rows(
        get_supabase().table("relocation_passport_official_source_reviews")
        .select("id,mapping_id,previous_verification_status,decision,reviewer,evidence_note,reviewed_source_url,reviewed_at,next_review_due_at,created_at")
        .eq("mapping_id", mapping_id).order("reviewed_at", desc=True)
        .limit(max(1, min(int(limit or 100), 250))).execute()
    )


def record_review(mapping_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    decision = clean_text(payload.get("decision"), 40).lower()
    reviewer = clean_text(payload.get("reviewer"), 200)
    evidence_note = clean_text(payload.get("evidence_note"), 4000)
    source_url = clean_text(payload.get("reviewed_source_url"), 700)
    try:
        interval = int(payload.get("review_interval_days") or 90)
    except (TypeError, ValueError):
        raise ValueError("review_interval_days must be an integer")
    if decision not in _ALLOWED_DECISIONS:
        raise ValueError("decision must be verified, needs_review, or retired")
    if len(reviewer) < 2:
        raise ValueError("reviewer identity is required")
    if len(evidence_note) < 10:
        raise ValueError("evidence_note must contain at least 10 characters")
    if not source_url.startswith("https://"):
        raise ValueError("reviewed_source_url must use HTTPS")
    if interval < 1 or interval > 365:
        raise ValueError("review_interval_days must be between 1 and 365")
    response = get_supabase().rpc("relocation_review_passport_official_source_mapping", {
        "p_mapping_id": mapping_id,
        "p_decision": decision,
        "p_reviewer": reviewer,
        "p_evidence_note": evidence_note,
        "p_reviewed_source_url": source_url,
        "p_review_interval_days": interval,
    }).execute()
    data = getattr(response, "data", None)
    if isinstance(data, list):
        return data[0] if data else {}
    return data if isinstance(data, dict) else {}


def expire_due_reviews() -> int:
    response = get_supabase().rpc("relocation_expire_passport_official_source_reviews", {}).execute()
    data = getattr(response, "data", 0)
    if isinstance(data, list):
        data = data[0] if data else 0
    if isinstance(data, dict):
        data = next(iter(data.values()), 0)
    return int(data or 0)
