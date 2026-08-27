from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


SEARCH_SCOPES = ("local", "international", "both")
WORK_AUTHORIZATION_REQUIREMENTS = (
    "unknown",
    "existing_required",
    "employer_support_possible",
    "employer_support_confirmed",
)
RELOCATION_SUPPORT_STATUSES = ("unknown", "not_available", "possible", "confirmed")
PROFILE_SCOPE_FIELDS = {
    "search_scope",
    "current_country",
    "work_authorized_countries",
    "primary_country",
    "later_countries",
}
JOB_PROFILE_COLUMNS = ",".join(
    (
        "id",
        "email",
        "relocation_profile_id",
        "display_name",
        "headline",
        "years_experience",
        "education_level",
        "current_employer",
        "previous_employer",
        "target_roles",
        "skills",
        "career_facts",
        "primary_country",
        "later_countries",
        "preferred_provinces",
        "work_authorization_status",
        "search_scope",
        "current_country",
        "work_authorized_countries",
        "is_active",
        "created_at",
        "updated_at",
    )
)


def _text(value: Any, limit: int = 100) -> Optional[str]:
    cleaned = str(value or "").strip()
    return cleaned[:limit] or None


def country_key(value: Any) -> str:
    return str(value or "").strip().casefold()


def country_list(value: Any, *, limit: int = 30) -> List[str]:
    values = value if isinstance(value, list) else str(value or "").split(",")
    result: List[str] = []
    seen = set()
    for item in values:
        cleaned = _text(item)
        key = country_key(cleaned)
        if cleaned and key not in seen:
            seen.add(key)
            result.append(cleaned)
        if len(result) >= limit:
            break
    return result


def profile_scope_contract(profile: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    value = profile or {}
    raw_scope = str(value.get("search_scope") or "international").strip().casefold()
    scope = raw_scope if raw_scope in SEARCH_SCOPES else "international"
    current_country = _text(value.get("current_country"))
    primary_country = _text(value.get("primary_country"))
    later_countries = country_list(value.get("later_countries"))
    work_authorized_countries = country_list(value.get("work_authorized_countries"))

    international_target_countries = country_list(
        [primary_country, *later_countries]
    )
    current_key = country_key(current_country)
    international_target_countries = [
        country
        for country in international_target_countries
        if country_key(country) != current_key
    ]

    if scope == "local":
        target_countries = country_list([current_country])
    elif scope == "international":
        target_countries = international_target_countries
    else:
        target_countries = country_list(
            [current_country, *international_target_countries]
        )

    missing: List[str] = []
    if not current_country:
        missing.append("current_country")
    if scope in {"international", "both"} and not international_target_countries:
        missing.append("international_target_country")

    return {
        "version": "b05-v1",
        "ready": not missing,
        "search_scope": scope,
        "current_country": current_country,
        "local_target_countries": country_list([current_country]),
        "international_target_countries": international_target_countries,
        "target_countries": target_countries,
        "work_authorized_countries": work_authorized_countries,
        "missing_fields": missing,
        "truth_note": (
            "Work authorization is user-reported and vacancy sponsorship is "
            "source-derived; neither is a guarantee of employment or immigration approval."
        ),
    }


def profile_scope_update(
    payload: Dict[str, Any],
    existing: Optional[Dict[str, Any]],
) -> Tuple[Dict[str, Any], Dict[str, Any], Optional[str]]:
    row: Dict[str, Any] = {}
    touched = any(field in payload for field in PROFILE_SCOPE_FIELDS)

    if "search_scope" in payload:
        scope = str(payload.get("search_scope") or "").strip().casefold()
        if scope not in SEARCH_SCOPES:
            return {}, profile_scope_contract(existing), "invalid_search_scope"
        row["search_scope"] = scope

    if "current_country" in payload:
        row["current_country"] = _text(payload.get("current_country"))

    if "work_authorized_countries" in payload:
        row["work_authorized_countries"] = country_list(
            payload.get("work_authorized_countries")
        )

    if "primary_country" in payload:
        row["primary_country"] = _text(payload.get("primary_country"))

    if "later_countries" in payload:
        row["later_countries"] = country_list(payload.get("later_countries"))

    effective = {**(existing or {}), **row}
    contract = profile_scope_contract(effective)
    if touched and "current_country" in contract["missing_fields"]:
        return {}, contract, "current_country_required"
    if touched and "international_target_country" in contract["missing_fields"]:
        return {}, contract, "international_target_country_required"
    return row, contract, None


def default_job_country(profile: Optional[Dict[str, Any]]) -> Optional[str]:
    contract = profile_scope_contract(profile)
    if contract["search_scope"] == "local":
        return contract["current_country"]
    international = contract["international_target_countries"]
    if international:
        return international[0]
    return contract["current_country"]


def employer_monitor_country(country: Any, profile: Optional[Dict[str, Any]]) -> Optional[str]:
    """Choose one in-scope country for the existing single-country monitor model."""
    countries = country_list(country)
    if not countries:
        return default_job_country(profile)
    keys = {country_key(item) for item in countries}
    preferred = country_list([default_job_country(profile), *profile_scope_contract(profile)["target_countries"]])
    return next((item for item in preferred if country_key(item) in keys), None)


def country_is_in_scope(country: Any, profile: Optional[Dict[str, Any]]) -> bool:
    contract = profile_scope_contract(profile)
    key = country_key(country)
    return bool(key) and key in {
        country_key(item) for item in contract["target_countries"]
    }


def job_scope_classification(
    job: Dict[str, Any],
    profile: Optional[Dict[str, Any]],
) -> str:
    job_country = country_key(job.get("country"))
    current_country = country_key((profile or {}).get("current_country"))
    if not job_country or not current_country:
        return "unknown"
    return "local" if job_country == current_country else "international"


def ranked_job_is_alertable(job: Dict[str, Any], min_match_score: int) -> bool:
    priority = str(job.get("application_priority") or "unknown")
    return (
        int(job.get("match_score") or 0) >= int(min_match_score)
        and priority not in {"out_of_scope", "not_recommended", "profile_incomplete"}
    )


def ranked_job_is_handoff_ready(job: Dict[str, Any]) -> bool:
    return str(job.get("application_priority") or "") in {
        "recommended",
        "consider",
    }


