from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import pycountry
import requests

from app.core.config import (
    PASSPORT_INDEX_PROVIDER_AUTH_HEADER,
    PASSPORT_INDEX_PROVIDER_ENABLED,
    PASSPORT_INDEX_PROVIDER_EXTRA_HEADERS_JSON,
    PASSPORT_INDEX_PROVIDER_HOST_HEADER,
    PASSPORT_INDEX_PROVIDER_KEY,
    PASSPORT_INDEX_PROVIDER_TIMEOUT_SECONDS,
    PASSPORT_INDEX_PROVIDER_URL,
    env,
    env_int,
)
from app.services.passport_index_provider import clean_text, country_key, normalize_access_bucket
from app.services.supabase_client import get_supabase


DETAIL_CACHE_MAX_DAYS = max(1, env_int("PASSPORT_INDEX_DETAIL_CACHE_MAX_DAYS", 7))
DETAIL_PROVIDER_URL = env("PASSPORT_INDEX_DETAIL_PROVIDER_URL")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return now_utc().isoformat()


def _parse_iso(value: Any) -> Optional[datetime]:
    raw = clean_text(value, 120)
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _detail_url() -> str:
    if DETAIL_PROVIDER_URL:
        return DETAIL_PROVIDER_URL

    base = clean_text(PASSPORT_INDEX_PROVIDER_URL, 700)
    if not base:
        return ""
    if "/v2/visa/map" in base:
        return base.replace("/v2/visa/map", "/v2/visa/check")
    if base.rstrip("/").endswith("/map"):
        return base.rstrip("/")[:-4] + "/check"
    return ""


def detail_provider_status() -> Dict[str, Any]:
    url = _detail_url()
    return {
        "provider_enabled": bool(PASSPORT_INDEX_PROVIDER_ENABLED),
        "provider_configured": bool(url and PASSPORT_INDEX_PROVIDER_KEY),
        "detail_url_configured": bool(url),
        "detail_cache_max_days": DETAIL_CACHE_MAX_DAYS,
        "cache_strategy": "one provider request per passport-destination pair when its detail cache is missing or stale",
        "safety_note": "Detailed provider rules are planning guidance. Confirm the destination government, embassy, airline document checker, and current entry conditions before travel.",
    }


def _provider_headers() -> Dict[str, str]:
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if PASSPORT_INDEX_PROVIDER_KEY:
        auth_header = PASSPORT_INDEX_PROVIDER_AUTH_HEADER or "X-RapidAPI-Key"
        if auth_header.lower() == "authorization":
            headers[auth_header] = f"Bearer {PASSPORT_INDEX_PROVIDER_KEY}"
        else:
            headers[auth_header] = PASSPORT_INDEX_PROVIDER_KEY
    if PASSPORT_INDEX_PROVIDER_HOST_HEADER:
        headers["X-RapidAPI-Host"] = PASSPORT_INDEX_PROVIDER_HOST_HEADER

    try:
        import json

        extra = json.loads(PASSPORT_INDEX_PROVIDER_EXTRA_HEADERS_JSON or "{}")
        if isinstance(extra, dict):
            for key, value in extra.items():
                clean_key = clean_text(key, 120)
                clean_value = clean_text(value, 500)
                if clean_key and clean_value:
                    headers[clean_key] = clean_value
    except Exception:
        pass
    return headers


def _passport_alpha2(passport_country: str, cache_row: Dict[str, Any] | None = None) -> str:
    provider_payload = (cache_row or {}).get("provider_payload")
    if isinstance(provider_payload, dict):
        data = provider_payload.get("data")
        if isinstance(data, dict):
            code = clean_text(data.get("passport"), 8).upper()
            if len(code) == 2:
                return code

    try:
        record = pycountry.countries.lookup(passport_country)
        return clean_text(record.alpha_2, 8).upper()
    except Exception:
        return clean_text(passport_country, 8).upper()


def _destination_alpha2(destination: str, access_row: Dict[str, Any]) -> str:
    provider_payload = access_row.get("provider_payload")
    if isinstance(provider_payload, dict):
        code = clean_text(provider_payload.get("destination_iso_alpha2"), 8).upper()
        if len(code) == 2:
            return code
        detail = provider_payload.get("destination_detail")
        if isinstance(detail, dict):
            code = clean_text(detail.get("destination_code"), 8).upper()
            if len(code) == 2:
                return code

    if destination.strip().lower() == "kosovo":
        return "XK"
    try:
        record = pycountry.countries.lookup(destination)
        return clean_text(record.alpha_2, 8).upper()
    except Exception:
        return ""


def _read_passport_cache(passport_country: str) -> Dict[str, Any] | None:
    response = (
        get_supabase()
        .table("relocation_passport_index_cache")
        .select("*")
        .eq("country_key", country_key(passport_country))
        .limit(1)
        .execute()
    )
    return (response.data or [None])[0]


def _read_access_row(passport_country: str, destination: str) -> Dict[str, Any] | None:
    query = (
        get_supabase()
        .table("relocation_passport_destination_access")
        .select("*")
        .eq("country_key", country_key(passport_country))
        .eq("destination", destination)
        .limit(1)
        .execute()
    )
    row = (query.data or [None])[0]
    if row:
        return row

    try:
        fallback = (
            get_supabase()
            .table("relocation_passport_destination_access")
            .select("*")
            .eq("country_key", country_key(passport_country))
            .ilike("destination", destination)
            .limit(1)
            .execute()
        )
        return (fallback.data or [None])[0]
    except Exception:
        return None


def _cached_detail(access_row: Dict[str, Any]) -> Dict[str, Any] | None:
    provider_payload = access_row.get("provider_payload")
    if not isinstance(provider_payload, dict):
        return None
    detail = provider_payload.get("destination_detail")
    if not isinstance(detail, dict):
        return None
    cached_at = _parse_iso(detail.get("cached_at"))
    if not cached_at:
        return None
    if now_utc() - cached_at >= timedelta(days=DETAIL_CACHE_MAX_DAYS):
        return None
    return detail


def _rule_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _combine_rule_names(primary: Dict[str, Any], secondary: Dict[str, Any]) -> str:
    names = []
    for rule in (primary, secondary):
        name = clean_text(rule.get("name"), 160)
        if name and name not in names:
            names.append(name)
    return " / ".join(names) or "Check current destination rule"


def _rule_bucket(primary: Dict[str, Any], secondary: Dict[str, Any]) -> str:
    primary_name = clean_text(primary.get("name"), 160)
    if primary_name:
        return normalize_access_bucket(primary_name)

    color = clean_text(primary.get("color") or secondary.get("color"), 40).lower()
    if color == "green":
        return "visa_free"
    if color == "yellow":
        return "evisa"
    if color == "blue":
        secondary_name = clean_text(secondary.get("name"), 160).lower()
        return "evisa" if "evisa" in secondary_name or "eta" in secondary_name else "visa_on_arrival"
    return "visa_required"


def _normalize_exception(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                return item
    return {}


def normalize_destination_detail(provider_payload: Dict[str, Any]) -> Dict[str, Any]:
    data = provider_payload.get("data") if isinstance(provider_payload.get("data"), dict) else {}
    passport = _rule_dict(data.get("passport"))
    destination = _rule_dict(data.get("destination"))
    registration = _rule_dict(data.get("mandatory_registration"))
    visa_rules = _rule_dict(data.get("visa_rules"))
    primary = _rule_dict(visa_rules.get("primary_rule"))
    secondary = _rule_dict(visa_rules.get("secondary_rule"))
    exception = _normalize_exception(visa_rules.get("exception_rule"))

    access_type = _combine_rule_names(primary, secondary)
    maximum_stay = clean_text(primary.get("duration") or secondary.get("duration"), 240)
    access_bucket = _rule_bucket(primary, secondary)

    conditions = []
    passport_validity = clean_text(destination.get("passport_validity"), 300)
    if passport_validity:
        conditions.append(f"Passport validity: {passport_validity}.")

    registration_name = clean_text(registration.get("name"), 180)
    if registration_name:
        conditions.append(f"Mandatory registration: {registration_name}.")

    exception_text = clean_text(
        exception.get("full_text")
        or exception.get("description")
        or exception.get("name")
        or exception.get("exception_type_name"),
        900,
    )
    if exception_text:
        conditions.append(f"Conditional exception: {exception_text}")

    conditions.append("Confirm current official rules, airline checks, travel purpose, funds, ticket, accommodation, and personal travel history before booking.")

    link_candidates = [
        secondary.get("link"),
        primary.get("link"),
        exception.get("link"),
        registration.get("link"),
        destination.get("embassy_url"),
    ]
    official_url = next((clean_text(item, 700) for item in link_candidates if clean_text(item, 700)), "")

    meta = provider_payload.get("meta") if isinstance(provider_payload.get("meta"), dict) else {}
    generated_at = clean_text(meta.get("generated_at"), 120) or now_iso()

    return {
        "passport_code": clean_text(passport.get("code"), 8).upper(),
        "passport_name": clean_text(passport.get("name"), 180),
        "destination_code": clean_text(destination.get("code"), 8).upper(),
        "destination": clean_text(destination.get("name"), 180),
        "destination_continent": clean_text(destination.get("continent"), 120),
        "capital": clean_text(destination.get("capital"), 180),
        "currency_code": clean_text(destination.get("currency_code"), 40),
        "currency": clean_text(destination.get("currency"), 180),
        "phone_code": clean_text(destination.get("phone_code"), 40),
        "timezone": clean_text(destination.get("timezone"), 80),
        "passport_validity": passport_validity,
        "embassy_url": clean_text(destination.get("embassy_url"), 700),
        "access_bucket": access_bucket,
        "access_type": access_type,
        "maximum_stay": maximum_stay,
        "primary_rule": primary,
        "secondary_rule": secondary,
        "exception_rule": exception,
        "mandatory_registration": registration,
        "conditions": " ".join(conditions),
        "official_source_name": "Destination rule link supplied by TravelBuddyAI" if official_url else "TravelBuddyAI Visa Requirement detail",
        "official_source_url": official_url,
        "provider_generated_at": generated_at,
        "cached_at": now_iso(),
        "confidence": "provider_detail_pending_official_confirmation",
        "source_status": "provider_detail_pending_official_confirmation",
        "safety_note": "This is planning guidance, not permission to travel. Verify the destination government, embassy or consulate, airline document checker, and current entry conditions.",
    }


def fetch_destination_detail(passport_code: str, destination_code: str) -> Dict[str, Any]:
    url = _detail_url()
    if not PASSPORT_INDEX_PROVIDER_ENABLED:
        raise RuntimeError("passport_detail_provider_disabled")
    if not url:
        raise RuntimeError("passport_detail_provider_url_missing")
    if not PASSPORT_INDEX_PROVIDER_KEY:
        raise RuntimeError("passport_detail_provider_key_missing")
    if not passport_code or not destination_code:
        raise RuntimeError("passport_or_destination_code_missing")
    if passport_code == destination_code:
        raise RuntimeError("passport_and_destination_must_differ")

    timeout = max(5, min(PASSPORT_INDEX_PROVIDER_TIMEOUT_SECONDS, 60))
    response = requests.post(
        url,
        headers=_provider_headers(),
        json={"passport": passport_code, "destination": destination_code},
        timeout=timeout,
    )
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        detail = clean_text(response.text, 900)
        raise RuntimeError(f"passport_detail_provider_http_{response.status_code}: {detail}") from exc

    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError("passport_detail_provider_payload_not_object")
    return payload


def _write_detail_cache(access_row: Dict[str, Any], detail: Dict[str, Any], provider_payload: Dict[str, Any]) -> None:
    original_payload = access_row.get("provider_payload")
    merged_payload = dict(original_payload) if isinstance(original_payload, dict) else {}
    detail_with_raw = dict(detail)
    detail_with_raw["raw_provider_payload"] = provider_payload
    merged_payload["destination_detail"] = detail_with_raw

    updated_at = now_iso()
    update_payload = {
        "destination_region": detail.get("destination_continent") or access_row.get("destination_region"),
        "access_bucket": detail.get("access_bucket") or access_row.get("access_bucket"),
        "access_type": detail.get("access_type") or access_row.get("access_type"),
        "maximum_stay": detail.get("maximum_stay"),
        "conditions": detail.get("conditions"),
        "official_source_name": detail.get("official_source_name"),
        "official_source_url": detail.get("official_source_url"),
        "last_verified_at": detail.get("provider_generated_at") or updated_at,
        "confidence": detail.get("confidence"),
        "source_status": detail.get("source_status"),
        "provider_payload": merged_payload,
        "updated_at": updated_at,
    }
    (
        get_supabase()
        .table("relocation_passport_destination_access")
        .update(update_payload)
        .eq("id", access_row.get("id"))
        .execute()
    )


def get_destination_detail(
    passport_country: str,
    destination: str,
    *,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    passport_country = clean_text(passport_country, 160)
    destination = clean_text(destination, 180)
    if not passport_country:
        raise ValueError("passport_country_required")
    if not destination:
        raise ValueError("destination_required")

    cache_row = _read_passport_cache(passport_country)
    access_row = _read_access_row(passport_country, destination)
    if not access_row:
        raise LookupError("destination_not_found_in_passport_cache")

    cached = None if force_refresh else _cached_detail(access_row)
    if cached:
        return {
            "ok": True,
            "status": "detail_cache_hit",
            "passport_country": passport_country,
            "destination": destination,
            "detail": cached,
            "cache_max_days": DETAIL_CACHE_MAX_DAYS,
            "provider_status": detail_provider_status(),
        }

    passport_code = _passport_alpha2(passport_country, cache_row)
    destination_code = _destination_alpha2(destination, access_row)
    provider_payload = fetch_destination_detail(passport_code, destination_code)
    detail = normalize_destination_detail(provider_payload)
    if not detail.get("destination"):
        detail["destination"] = destination
    if not detail.get("destination_code"):
        detail["destination_code"] = destination_code
    if not detail.get("passport_code"):
        detail["passport_code"] = passport_code

    _write_detail_cache(access_row, detail, provider_payload)
    return {
        "ok": True,
        "status": "detail_cache_refreshed",
        "passport_country": passport_country,
        "destination": detail.get("destination") or destination,
        "detail": detail,
        "cache_max_days": DETAIL_CACHE_MAX_DAYS,
        "provider_status": detail_provider_status(),
    }
