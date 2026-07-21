from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests

from app.core.config import (
    PASSPORT_INDEX_CACHE_MAX_DAYS,
    PASSPORT_INDEX_PROVIDER_AUTH_HEADER,
    PASSPORT_INDEX_PROVIDER_COUNTRY_CODE_FORMAT,
    PASSPORT_INDEX_PROVIDER_ENABLED,
    PASSPORT_INDEX_PROVIDER_EXTRA_HEADERS_JSON,
    PASSPORT_INDEX_PROVIDER_HOST_HEADER,
    PASSPORT_INDEX_PROVIDER_KEY,
    PASSPORT_INDEX_PROVIDER_METHOD,
    PASSPORT_INDEX_PROVIDER_NAME,
    PASSPORT_INDEX_PROVIDER_TIMEOUT_SECONDS,
    PASSPORT_INDEX_PROVIDER_URL,
    PASSPORT_INDEX_SYNC_WEEKDAYS,
)
from app.services.supabase_client import get_supabase

ACCESS_BUCKETS = {"visa_free", "visa_on_arrival", "evisa", "visa_required"}
ACCESS_LABELS = {
    "visa_free": "Visa-free",
    "visa_on_arrival": "Visa on arrival",
    "evisa": "eVisa / ETA",
    "visa_required": "Visa required",
}

COUNTRY_CODE_MAP: Dict[str, Dict[str, str]] = {
    "nigeria": {"alpha2": "NG", "alpha3": "NGA", "name": "Nigeria"},
    "ghana": {"alpha2": "GH", "alpha3": "GHA", "name": "Ghana"},
    "kenya": {"alpha2": "KE", "alpha3": "KEN", "name": "Kenya"},
    "india": {"alpha2": "IN", "alpha3": "IND", "name": "India"},
    "pakistan": {"alpha2": "PK", "alpha3": "PAK", "name": "Pakistan"},
    "philippines": {"alpha2": "PH", "alpha3": "PHL", "name": "Philippines"},
    "kuwait": {"alpha2": "KW", "alpha3": "KWT", "name": "Kuwait"},
}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return now_utc().isoformat()


def clean_text(value: Any, limit: int = 240) -> str:
    return str(value or "").strip()[:limit]


def country_key(value: Any) -> str:
    return clean_text(value, 160).lower().replace("-", " ").replace("_", " ").strip()


def _country_codes(country: str) -> Dict[str, str]:
    key = country_key(country)
    record = COUNTRY_CODE_MAP.get(key, {})
    name = clean_text(record.get("name") or country, 160)
    alpha2 = clean_text(record.get("alpha2") or country, 20).upper()
    alpha3 = clean_text(record.get("alpha3") or country, 20).upper()
    return {"country": name, "country_key": key, "alpha2": alpha2, "alpha3": alpha3}


def _provider_country_code(country: str) -> str:
    codes = _country_codes(country)
    fmt = (PASSPORT_INDEX_PROVIDER_COUNTRY_CODE_FORMAT or "alpha2").lower()
    if fmt in {"alpha3", "iso3"}:
        return codes["alpha3"]
    if fmt in {"name", "country"}:
        return codes["country"]
    if fmt in {"country_key", "key", "slug"}:
        return codes["country_key"]
    return codes["alpha2"]


def _sync_frequency_label() -> str:
    days = [item.strip().upper() for item in PASSPORT_INDEX_SYNC_WEEKDAYS.split(",") if item.strip()]
    return "weekly" if len(days) <= 1 else "twice weekly"


def next_sync_due_iso(from_dt: Optional[datetime] = None) -> str:
    base = from_dt or now_utc()
    configured = [item.strip().upper() for item in PASSPORT_INDEX_SYNC_WEEKDAYS.split(",") if item.strip()]
    weekday_map = {"MON": 0, "TUE": 1, "WED": 2, "THU": 3, "FRI": 4, "SAT": 5, "SUN": 6}
    target_days = sorted({weekday_map[item] for item in configured if item in weekday_map}) or [4]
    for offset in range(1, 8):
        candidate = base + timedelta(days=offset)
        if candidate.weekday() in target_days:
            return candidate.replace(hour=6, minute=0, second=0, microsecond=0).isoformat()
    return (base + timedelta(days=7)).isoformat()


def provider_status_payload() -> Dict[str, Any]:
    return {
        "provider_enabled": bool(PASSPORT_INDEX_PROVIDER_ENABLED),
        "provider_configured": bool(PASSPORT_INDEX_PROVIDER_URL and PASSPORT_INDEX_PROVIDER_KEY),
        "provider_name": PASSPORT_INDEX_PROVIDER_NAME,
        "sync_frequency": _sync_frequency_label(),
        "sync_weekdays": PASSPORT_INDEX_SYNC_WEEKDAYS,
        "cache_max_days": PASSPORT_INDEX_CACHE_MAX_DAYS,
        "country_code_format": PASSPORT_INDEX_PROVIDER_COUNTRY_CODE_FORMAT,
        "auth_header": PASSPORT_INDEX_PROVIDER_AUTH_HEADER,
        "host_header_configured": bool(PASSPORT_INDEX_PROVIDER_HOST_HEADER),
        "safety_note": "Passport access changes. MoveReady uses cached provider data plus official-source review fields instead of calling paid APIs on every user click.",
    }


def _safe_int(value: Any) -> Optional[int]:
    try:
        if value is None or value == "":
            return None
        return int(float(value))
    except Exception:
        return None


def _as_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _first_dict(*values: Any) -> Dict[str, Any]:
    for value in values:
        if isinstance(value, dict):
            return value
    return {}


def _get_nested(payload: Dict[str, Any], *keys: str) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def normalize_access_bucket(value: Any) -> str:
    raw = clean_text(value, 120).lower().replace("-", "_").replace(" ", "_")
    if raw in ACCESS_BUCKETS:
        return raw
    if "arrival" in raw or "voa" in raw:
        return "visa_on_arrival"
    if "electronic" in raw or "evisa" in raw or "eta" in raw or "e_visa" in raw:
        return "evisa"
    if "free" in raw or "exempt" in raw or "no_visa" in raw or "not_required" in raw:
        return "visa_free"
    if "required" in raw or "visa" in raw:
        return "visa_required"
    return "visa_required"


def _row_destination(row: Dict[str, Any]) -> str:
    destination = (
        row.get("destination")
        or row.get("country")
        or row.get("destination_country")
        or row.get("destination_name")
        or row.get("name")
        or row.get("to")
    )
    if isinstance(destination, dict):
        destination = destination.get("name") or destination.get("country") or destination.get("common")
    return clean_text(destination, 180)


def normalize_destination_rows(provider_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Normalize common passport/visa API shapes into MoveReady destination rows."""
    direct_rows: List[Any] = []
    candidates = [
        provider_payload.get("destination_access_rows"),
        provider_payload.get("destinations"),
        provider_payload.get("requirements"),
        provider_payload.get("results"),
        provider_payload.get("map"),
        _get_nested(provider_payload, "data", "destination_access_rows"),
        _get_nested(provider_payload, "data", "destinations"),
        _get_nested(provider_payload, "data", "requirements"),
        _get_nested(provider_payload, "data", "results"),
        _get_nested(provider_payload, "data", "map"),
        _get_nested(provider_payload, "passport_index", "destination_access_rows"),
        _get_nested(provider_payload, "passport_index", "destinations"),
    ]
    for candidate in candidates:
        if isinstance(candidate, list):
            direct_rows = candidate
            break

    grouped_rows: List[Tuple[str, Any]] = []
    grouped_sources = [provider_payload, provider_payload.get("data"), provider_payload.get("passport_index")]
    grouped_keys = {
        "visa_free": ["visa_free", "visa_free_countries", "visaFree", "Visa-free", "visa_free_examples"],
        "visa_on_arrival": ["visa_on_arrival", "visa_on_arrival_countries", "visaOnArrival", "Visa on arrival", "visa_on_arrival_examples"],
        "evisa": ["evisa", "evisa_countries", "eVisa", "eTA", "eta", "evisa_examples"],
        "visa_required": ["visa_required", "visa_required_countries", "visaRequired", "Visa required", "visa_required_examples"],
    }
    if not direct_rows:
        for source in grouped_sources:
            if not isinstance(source, dict):
                continue
            for bucket, keys in grouped_keys.items():
                for key in keys:
                    for item in _as_list(source.get(key)):
                        grouped_rows.append((bucket, item))

    output: List[Dict[str, Any]] = []
    iterable: Iterable[Tuple[Optional[str], Any]] = [(None, item) for item in direct_rows] if direct_rows else grouped_rows
    seen: set[Tuple[str, str]] = set()
    for default_bucket, raw_item in iterable:
        if isinstance(raw_item, str):
            row = {"destination": raw_item, "access_bucket": default_bucket}
        elif isinstance(raw_item, dict):
            row = dict(raw_item)
            if default_bucket and not row.get("access_bucket"):
                row["access_bucket"] = default_bucket
        else:
            continue

        destination = _row_destination(row)
        if not destination:
            continue
        primary_rule = row.get("primary_rule") if isinstance(row.get("primary_rule"), dict) else {}
        secondary_rule = row.get("secondary_rule") if isinstance(row.get("secondary_rule"), dict) else {}
        bucket_source = row.get("access_bucket") or row.get("visa_requirement") or row.get("requirement") or row.get("access_type") or row.get("type") or primary_rule.get("name")
        bucket = normalize_access_bucket(bucket_source)
        key = (destination.lower(), bucket)
        if key in seen:
            continue
        seen.add(key)

        output.append(
            {
                "destination": destination,
                "destination_region": clean_text(row.get("destination_region") or row.get("region") or row.get("continent"), 120),
                "access_bucket": bucket,
                "access_label": ACCESS_LABELS.get(bucket, bucket),
                "access_type": clean_text(row.get("access_type") or row.get("visa_requirement") or row.get("requirement") or primary_rule.get("name") or ACCESS_LABELS.get(bucket), 240),
                "maximum_stay": clean_text(row.get("maximum_stay") or row.get("stay") or row.get("duration") or row.get("max_stay") or primary_rule.get("duration") or secondary_rule.get("duration"), 240),
                "conditions": clean_text(row.get("conditions") or row.get("condition") or row.get("notes") or row.get("description"), 1000),
                "official_source_name": clean_text(row.get("official_source_name") or row.get("source_name") or row.get("source"), 240),
                "official_source_url": clean_text(row.get("official_source_url") or row.get("source_url") or row.get("url") or row.get("link") or secondary_rule.get("link"), 700),
                "last_verified": clean_text(row.get("last_verified") or row.get("last_reviewed") or row.get("updated_at"), 120),
                "confidence": clean_text(row.get("confidence") or row.get("source_status") or "provider_cache_pending_admin_review", 120),
                "source_status": clean_text(row.get("source_status") or row.get("confidence") or "provider_cache_pending_admin_review", 120),
                "provider_payload": row,
            }
        )
    return output


def _category_count(source: Dict[str, Any], *keys: str) -> Optional[int]:
    categories = source.get("categories") if isinstance(source.get("categories"), dict) else {}
    lookup_sources = [source, categories]
    for lookup in lookup_sources:
        for key in keys:
            value = lookup.get(key) if isinstance(lookup, dict) else None
            parsed = _safe_int(value)
            if parsed is not None:
                return parsed
    return None


def _extract_passport_index(provider_payload: Dict[str, Any], requested_country: str, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    passport_index = _first_dict(provider_payload.get("passport_index"), provider_payload.get("data"), provider_payload)
    counts = {
        "visa_free_count": _category_count(passport_index, "visa_free_count", "visaFreeCount", "visa_free", "Visa-free", "Visa not required", "Freedom of movement"),
        "visa_on_arrival_count": _category_count(passport_index, "visa_on_arrival_count", "visaOnArrivalCount", "visa_on_arrival", "Visa on arrival"),
        "evisa_count": _category_count(passport_index, "evisa_count", "eVisaCount", "eta_count", "evisa", "eVisa", "eTA", "Tourist card"),
        "visa_required_count": _category_count(passport_index, "visa_required_count", "visaRequiredCount", "visa_required", "Visa required"),
    }
    if not any(value is not None for value in counts.values()) and rows:
        counts = {
            "visa_free_count": sum(1 for row in rows if row.get("access_bucket") == "visa_free"),
            "visa_on_arrival_count": sum(1 for row in rows if row.get("access_bucket") == "visa_on_arrival"),
            "evisa_count": sum(1 for row in rows if row.get("access_bucket") == "evisa"),
            "visa_required_count": sum(1 for row in rows if row.get("access_bucket") == "visa_required"),
        }

    explicit_score = _safe_int(
        passport_index.get("passport_opportunity_score")
        or passport_index.get("mobility_score")
        or passport_index.get("passport_power_score")
        or passport_index.get("score")
    )
    if explicit_score is None:
        open_count = (counts.get("visa_free_count") or 0) + (counts.get("visa_on_arrival_count") or 0) + (counts.get("evisa_count") or 0)
        explicit_score = min(100, max(10, round(open_count / 2))) if open_count else None

    return {
        "country": clean_text(passport_index.get("country") or passport_index.get("passport_country") or requested_country, 160),
        "country_key": country_key(passport_index.get("country") or passport_index.get("passport_country") or requested_country),
        "region": clean_text(passport_index.get("region"), 120),
        "passport_rank": _safe_int(passport_index.get("passport_rank") or passport_index.get("rank") or passport_index.get("global_rank")),
        "passport_opportunity_score": explicit_score,
        "passport_strength_band": clean_text(passport_index.get("passport_strength_band") or passport_index.get("strength_band") or "provider_cache", 120),
        "summary": clean_text(passport_index.get("summary") or passport_index.get("description") or "Passport access loaded from provider cache. Confirm destination official rules before booking.", 1200),
        "visa_free_count": counts.get("visa_free_count"),
        "visa_on_arrival_count": counts.get("visa_on_arrival_count"),
        "evisa_count": counts.get("evisa_count"),
        "visa_required_count": counts.get("visa_required_count"),
        "visa_free_count_estimate": passport_index.get("visa_free_count_estimate") or counts.get("visa_free_count") or "Provider count pending",
        "visa_on_arrival_count_estimate": passport_index.get("visa_on_arrival_count_estimate") or counts.get("visa_on_arrival_count") or "Provider count pending",
        "evisa_count_estimate": passport_index.get("evisa_count_estimate") or counts.get("evisa_count") or "Provider count pending",
        "visa_required_count_estimate": passport_index.get("visa_required_count_estimate") or counts.get("visa_required_count") or "Provider count pending",
        "validity_notes": passport_index.get("validity_notes") or "Check passport validity and blank-page rules for every destination.",
        "renewal_notes": passport_index.get("renewal_notes") or "Renew early if passport validity is weak or the route may take months.",
        "official_source_priority": passport_index.get("official_source_priority") or ["Destination government immigration site", "Embassy or consulate page", "Airline document checker", "Official eVisa or ETA portal"],
        "last_reviewed": clean_text(passport_index.get("last_reviewed") or passport_index.get("last_verified") or now_utc().date().isoformat(), 120),
        "confidence": clean_text(passport_index.get("confidence") or passport_index.get("source_status") or "provider_cache_pending_admin_review", 120),
        "source_provider": PASSPORT_INDEX_PROVIDER_NAME,
        "last_synced_at": now_iso(),
        "sync_frequency": _sync_frequency_label(),
        "next_sync_due_at": next_sync_due_iso(),
    }


def _provider_headers() -> Dict[str, str]:
    headers = {"Accept": "application/json"}
    if PASSPORT_INDEX_PROVIDER_KEY:
        auth_header = PASSPORT_INDEX_PROVIDER_AUTH_HEADER or "X-API-Key"
        if auth_header.lower() == "authorization":
            headers[auth_header] = f"Bearer {PASSPORT_INDEX_PROVIDER_KEY}"
        else:
            headers[auth_header] = PASSPORT_INDEX_PROVIDER_KEY
    if PASSPORT_INDEX_PROVIDER_HOST_HEADER:
        headers["X-RapidAPI-Host"] = PASSPORT_INDEX_PROVIDER_HOST_HEADER
    try:
        extra_headers = json.loads(PASSPORT_INDEX_PROVIDER_EXTRA_HEADERS_JSON or "{}")
        if isinstance(extra_headers, dict):
            for key, value in extra_headers.items():
                clean_key = clean_text(key, 120)
                clean_value = clean_text(value, 500)
                if clean_key and clean_value:
                    headers[clean_key] = clean_value
    except Exception:
        pass
    return headers


def _provider_request_payload(passport_country: str) -> Dict[str, str]:
    codes = _country_codes(passport_country)
    provider_code = _provider_country_code(passport_country)
    return {
        "passport_country": codes["country"],
        "country": codes["country"],
        "country_key": codes["country_key"],
        "country_alpha2": codes["alpha2"],
        "country_alpha3": codes["alpha3"],
        "passport": provider_code,
        "nationality": provider_code,
    }


def fetch_provider_payload(passport_country: str) -> Dict[str, Any]:
    if not PASSPORT_INDEX_PROVIDER_ENABLED:
        raise RuntimeError("passport_provider_disabled")
    if not PASSPORT_INDEX_PROVIDER_URL:
        raise RuntimeError("passport_provider_url_missing")

    country = clean_text(passport_country, 160)
    payload = _provider_request_payload(country)
    url = PASSPORT_INDEX_PROVIDER_URL.format(**payload)
    headers = _provider_headers()
    method = PASSPORT_INDEX_PROVIDER_METHOD or "GET"
    timeout = max(5, min(PASSPORT_INDEX_PROVIDER_TIMEOUT_SECONDS, 60))
    if method == "POST":
        response = requests.post(url, headers=headers, json=payload, timeout=timeout)
    else:
        response = requests.get(url, headers=headers, params=payload, timeout=timeout)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise RuntimeError("passport_provider_payload_not_json_object")
    return data


def normalize_provider_payload(passport_country: str, provider_payload: Dict[str, Any]) -> Dict[str, Any]:
    rows = normalize_destination_rows(provider_payload)
    passport_index = _extract_passport_index(provider_payload, passport_country, rows)
    passport_index["destination_access_rows"] = rows
    return {"passport_index": passport_index, "destination_access_rows": rows}


def read_cached_passport(country: str) -> Optional[Dict[str, Any]]:
    key = country_key(country)
    if not key:
        return None
    response = (
        get_supabase()
        .table("relocation_passport_index_cache")
        .select("*")
        .eq("country_key", key)
        .limit(1)
        .execute()
    )
    row = (response.data or [None])[0]
    if not row:
        return None
    return row


def read_cached_destination_rows(country: str) -> List[Dict[str, Any]]:
    key = country_key(country)
    if not key:
        return []
    response = (
        get_supabase()
        .table("relocation_passport_destination_access")
        .select("*")
        .eq("country_key", key)
        .order("access_bucket")
        .order("destination")
        .execute()
    )
    rows: List[Dict[str, Any]] = []
    for row in response.data or []:
        rows.append(
            {
                "destination": row.get("destination"),
                "destination_region": row.get("destination_region"),
                "access_bucket": row.get("access_bucket"),
                "access_label": ACCESS_LABELS.get(row.get("access_bucket"), row.get("access_bucket")),
                "access_type": row.get("access_type"),
                "maximum_stay": row.get("maximum_stay"),
                "conditions": row.get("conditions"),
                "official_source_name": row.get("official_source_name"),
                "official_source_url": row.get("official_source_url"),
                "last_verified": row.get("last_verified_at"),
                "confidence": row.get("confidence"),
                "source_status": row.get("source_status"),
            }
        )
    return rows


def write_cache(passport_country: str, normalized: Dict[str, Any], provider_payload: Dict[str, Any]) -> Dict[str, Any]:
    key = country_key(passport_country)
    passport_index = dict(normalized.get("passport_index") or {})
    rows = list(normalized.get("destination_access_rows") or [])
    synced_at = now_iso()
    next_due = next_sync_due_iso()

    cache_payload = {
        "passport_country": passport_index.get("country") or passport_country,
        "country_key": key,
        "source_provider": PASSPORT_INDEX_PROVIDER_NAME,
        "provider_payload": provider_payload,
        "passport_index_payload": passport_index,
        "passport_rank": passport_index.get("passport_rank"),
        "passport_opportunity_score": passport_index.get("passport_opportunity_score"),
        "passport_strength_band": passport_index.get("passport_strength_band"),
        "visa_free_count": passport_index.get("visa_free_count"),
        "visa_on_arrival_count": passport_index.get("visa_on_arrival_count"),
        "evisa_count": passport_index.get("evisa_count"),
        "visa_required_count": passport_index.get("visa_required_count"),
        "last_synced_at": synced_at,
        "last_reviewed_at": synced_at,
        "next_sync_due_at": next_due,
        "source_status": passport_index.get("confidence") or "provider_cache_pending_admin_review",
        "confidence": passport_index.get("confidence") or "provider_cache_pending_admin_review",
        "updated_at": synced_at,
    }

    supabase = get_supabase()
    supabase.table("relocation_passport_index_cache").upsert(cache_payload, on_conflict="country_key").execute()
    supabase.table("relocation_passport_destination_access").delete().eq("country_key", key).execute()

    db_rows: List[Dict[str, Any]] = []
    for row in rows:
        db_rows.append(
            {
                "country_key": key,
                "passport_country": passport_index.get("country") or passport_country,
                "destination": row.get("destination"),
                "destination_region": row.get("destination_region"),
                "access_bucket": normalize_access_bucket(row.get("access_bucket")),
                "access_type": row.get("access_type"),
                "maximum_stay": row.get("maximum_stay"),
                "conditions": row.get("conditions"),
                "official_source_name": row.get("official_source_name"),
                "official_source_url": row.get("official_source_url"),
                "last_verified_at": row.get("last_verified") or synced_at,
                "confidence": row.get("confidence") or "provider_cache_pending_admin_review",
                "source_status": row.get("source_status") or row.get("confidence") or "provider_cache_pending_admin_review",
                "source_provider": PASSPORT_INDEX_PROVIDER_NAME,
                "provider_payload": row.get("provider_payload") or row,
                "updated_at": synced_at,
            }
        )
    if db_rows:
        supabase.table("relocation_passport_destination_access").insert(db_rows).execute()

    return {"country_key": key, "row_count": len(db_rows), "last_synced_at": synced_at, "next_sync_due_at": next_due}


def log_sync_run(status: str, details: Dict[str, Any]) -> None:
    try:
        get_supabase().table("relocation_passport_provider_sync_runs").insert(
            {
                "source_provider": PASSPORT_INDEX_PROVIDER_NAME,
                "status": clean_text(status, 80),
                "details": details,
                "created_at": now_iso(),
            }
        ).execute()
    except Exception:
        # Logging should never break the public or admin flow.
        pass
