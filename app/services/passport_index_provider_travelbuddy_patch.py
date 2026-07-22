from __future__ import annotations

from typing import Any, Dict, List

import pycountry

from app.services import passport_index_provider as provider


_PATCH_APPLIED = False

_ORIGINAL_NORMALIZE_DESTINATION_ROWS = provider.normalize_destination_rows
_ORIGINAL_NORMALIZE_PROVIDER_PAYLOAD = provider.normalize_provider_payload
_ORIGINAL_READ_CACHED_DESTINATION_ROWS = provider.read_cached_destination_rows
_ORIGINAL_WRITE_CACHE = provider.write_cache

_SPECIAL_COUNTRY_NAMES = {
    "XK": "Kosovo",
}

_COLOR_RULES: Dict[str, Dict[str, str]] = {
    "green": {
        "access_bucket": "visa_free",
        "access_label": "Visa-free",
        "access_type": "Visa not required or freedom of movement",
        "conditions": "TravelBuddy map category only. Confirm the destination-specific stay limit, passport-validity rule, exceptions, and entry conditions before booking.",
    },
    "blue": {
        "access_bucket": "visa_on_arrival",
        "access_label": "Visa on arrival / eVisa",
        "access_type": "Visa on arrival or eVisa",
        "conditions": "The provider map combines visa on arrival and eVisa in one blue category. Confirm which rule applies, the allowed stay, fees, and the official application route before travel.",
    },
    "yellow": {
        "access_bucket": "evisa",
        "access_label": "eTA / visa-waiver registration",
        "access_type": "eTA or visa-waiver registration",
        "conditions": "The provider map combines eTA and visa-waiver registration in one yellow category. Confirm the exact pre-travel authorization and official registration link before booking.",
    },
    "red": {
        "access_bucket": "visa_required",
        "access_label": "Visa required / restricted",
        "access_type": "Visa required, online visa required, or not admitted",
        "conditions": "The provider map combines visa required, online visa required, and not-admitted outcomes in one red category. Confirm the exact destination-specific rule before applying or travelling.",
    },
}


def _travelbuddy_color_data(provider_payload: Dict[str, Any]) -> Dict[str, Any]:
    data = provider_payload.get("data")
    if not isinstance(data, dict):
        return {}
    colors = data.get("colors")
    if not isinstance(colors, dict):
        return {}
    return {
        "passport": provider.clean_text(data.get("passport"), 8).upper(),
        "colors": colors,
        "generated_at": provider.clean_text(
            (provider_payload.get("meta") or {}).get("generated_at")
            if isinstance(provider_payload.get("meta"), dict)
            else "",
            120,
        ),
    }


def _split_country_codes(value: Any) -> List[str]:
    if isinstance(value, str):
        raw_items = value.split(",")
    elif isinstance(value, list):
        raw_items = value
    else:
        return []

    output: List[str] = []
    seen: set[str] = set()
    for item in raw_items:
        code = provider.clean_text(item, 8).upper()
        if len(code) != 2 or not code.isalpha() or code in seen:
            continue
        seen.add(code)
        output.append(code)
    return output


def _country_name(alpha2: str) -> str:
    code = provider.clean_text(alpha2, 8).upper()
    if code in _SPECIAL_COUNTRY_NAMES:
        return _SPECIAL_COUNTRY_NAMES[code]

    country = pycountry.countries.get(alpha_2=code)
    if country is None:
        return code
    return provider.clean_text(getattr(country, "common_name", None) or country.name or code, 180)


def _travelbuddy_rows(provider_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    color_data = _travelbuddy_color_data(provider_payload)
    colors = color_data.get("colors")
    if not isinstance(colors, dict):
        return []

    passport_code = provider.clean_text(color_data.get("passport"), 8).upper()
    generated_at = provider.clean_text(color_data.get("generated_at"), 120)
    output: List[Dict[str, Any]] = []
    seen_codes: set[str] = set()

    for color in ("green", "blue", "yellow", "red"):
        rule = _COLOR_RULES[color]
        for destination_code in _split_country_codes(colors.get(color)):
            if destination_code == passport_code or destination_code in seen_codes:
                continue
            seen_codes.add(destination_code)
            output.append(
                {
                    "destination": _country_name(destination_code),
                    "destination_region": "",
                    "access_bucket": rule["access_bucket"],
                    "access_label": rule["access_label"],
                    "access_type": rule["access_type"],
                    "maximum_stay": "",
                    "conditions": rule["conditions"],
                    "official_source_name": "TravelBuddyAI Visa Requirement API map overview",
                    "official_source_url": "",
                    "last_verified": generated_at,
                    "confidence": "provider_map_pending_destination_rule_check",
                    "source_status": "provider_map_pending_destination_rule_check",
                    "provider_payload": {
                        "provider_color": color,
                        "destination_iso_alpha2": destination_code,
                        "passport_iso_alpha2": passport_code,
                        "provider_rule_summary": rule["access_type"],
                        "generated_at": generated_at,
                    },
                }
            )

    return output


def _patched_normalize_destination_rows(provider_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = _ORIGINAL_NORMALIZE_DESTINATION_ROWS(provider_payload)
    if rows:
        return rows
    return _travelbuddy_rows(provider_payload)


def _patched_normalize_provider_payload(
    passport_country: str,
    provider_payload: Dict[str, Any],
) -> Dict[str, Any]:
    normalized = _ORIGINAL_NORMALIZE_PROVIDER_PAYLOAD(passport_country, provider_payload)
    color_data = _travelbuddy_color_data(provider_payload)
    colors = color_data.get("colors")
    if not isinstance(colors, dict):
        return normalized

    rows = list(normalized.get("destination_access_rows") or [])
    counts = {
        color: len(_split_country_codes(colors.get(color)))
        for color in ("green", "blue", "yellow", "red")
    }
    passport_code = provider.clean_text(color_data.get("passport"), 8).upper()
    for color in counts:
        if passport_code and passport_code in _split_country_codes(colors.get(color)):
            counts[color] = max(0, counts[color] - 1)

    passport_index = dict(normalized.get("passport_index") or {})
    passport_index.update(
        {
            "destination_access_rows": rows,
            "visa_free_count": counts["green"],
            "visa_on_arrival_count": counts["blue"],
            "evisa_count": counts["yellow"],
            "visa_required_count": counts["red"],
            "visa_free_count_estimate": counts["green"],
            "visa_on_arrival_count_estimate": f"{counts['blue']} blue-map destinations: visa on arrival or eVisa",
            "evisa_count_estimate": f"{counts['yellow']} yellow-map destinations: eTA or visa-waiver registration",
            "visa_required_count_estimate": f"{counts['red']} red-map destinations: visa required, online visa required, or not admitted",
            "summary": "Travel access loaded from the TravelBuddyAI map overview. Blue, yellow, and red are combined provider categories, so users must confirm the detailed destination rule, duration, exceptions, and official application source before booking.",
            "confidence": "provider_map_pending_destination_rule_check",
            "provider_map_color_counts": counts,
            "provider_map_semantics": {
                "green": "Visa not required or freedom of movement",
                "blue": "Visa on arrival or eVisa",
                "yellow": "eTA or visa-waiver registration",
                "red": "Visa required, online visa required, or not admitted",
            },
        }
    )
    normalized["passport_index"] = passport_index
    normalized["destination_access_rows"] = rows
    return normalized


def _patched_read_cached_destination_rows(country: str) -> List[Dict[str, Any]]:
    rows = _ORIGINAL_READ_CACHED_DESTINATION_ROWS(country)
    for row in rows:
        access_type = provider.clean_text(row.get("access_type"), 240).lower()
        if "visa on arrival or evisa" in access_type:
            row["access_label"] = "Visa on arrival / eVisa"
        elif "eta or visa-waiver registration" in access_type:
            row["access_label"] = "eTA / visa-waiver registration"
        elif "visa required, online visa required, or not admitted" in access_type:
            row["access_label"] = "Visa required / restricted"
        elif "evisa" in access_type or "eta" in access_type:
            row["access_label"] = "eVisa / ETA"
        elif "arrival" in access_type:
            row["access_label"] = "Visa on arrival"
        elif "free" in access_type or "freedom" in access_type:
            row["access_label"] = "Visa-free"
    return rows


def _existing_destination_details(passport_country: str) -> Dict[str, Dict[str, Any]]:
    """Read destination-detail caches before the weekly map rows are replaced."""
    try:
        response = (
            provider.get_supabase()
            .table("relocation_passport_destination_access")
            .select("destination,provider_payload")
            .eq("country_key", provider.country_key(passport_country))
            .execute()
        )
    except Exception:
        return {}

    output: Dict[str, Dict[str, Any]] = {}
    for row in response.data or []:
        destination = provider.clean_text(row.get("destination"), 180).lower()
        provider_payload = row.get("provider_payload")
        if not destination or not isinstance(provider_payload, dict):
            continue
        detail = provider_payload.get("destination_detail")
        if isinstance(detail, dict):
            output[destination] = detail
    return output


def _preserve_destination_details(passport_country: str, rows: List[Dict[str, Any]]) -> None:
    existing = _existing_destination_details(passport_country)
    if not existing:
        return

    for row in rows:
        destination = provider.clean_text(row.get("destination"), 180).lower()
        detail = existing.get(destination)
        if not detail:
            continue
        row_payload = row.get("provider_payload")
        merged_payload = dict(row_payload) if isinstance(row_payload, dict) else {}
        merged_payload["destination_detail"] = detail
        row["provider_payload"] = merged_payload


def _patched_write_cache(
    passport_country: str,
    normalized: Dict[str, Any],
    provider_payload: Dict[str, Any],
) -> Dict[str, Any]:
    rows = list(normalized.get("destination_access_rows") or [])
    if not rows:
        raise RuntimeError(
            "passport_provider_zero_rows_cache_write_blocked: provider returned data but no destination rows were normalized"
        )

    _preserve_destination_details(passport_country, rows)
    normalized["destination_access_rows"] = rows
    passport_index = dict(normalized.get("passport_index") or {})
    passport_index["destination_access_rows"] = rows
    normalized["passport_index"] = passport_index
    return _ORIGINAL_WRITE_CACHE(passport_country, normalized, provider_payload)


def apply_patch() -> None:
    global _PATCH_APPLIED
    if _PATCH_APPLIED:
        return

    provider.normalize_destination_rows = _patched_normalize_destination_rows
    provider.normalize_provider_payload = _patched_normalize_provider_payload
    provider.read_cached_destination_rows = _patched_read_cached_destination_rows
    provider.write_cache = _patched_write_cache
    provider.TRAVELBUDDY_COLOR_PATCH_ACTIVE = True
    _PATCH_APPLIED = True
