from __future__ import annotations

from typing import Any, Mapping

CONTRACT_VERSION = "b19.10.1-v1"
CAMPAIGN_STATUSES = ("draft", "active", "paused", "completed", "archived")
SEARCH_INTENSITIES = ("light", "standard", "intensive")


def _text(value: Any) -> str | None:
    value = str(value or "").strip()
    return value or None


def _strings(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    result=[]
    for item in value:
        text=_text(item)
        if text and text not in result:
            result.append(text)
    return result


def normalize_campaign(payload: Mapping[str, Any]) -> dict[str, Any]:
    status=str(payload.get("status") or "draft").strip().lower()
    intensity=str(payload.get("search_intensity") or "standard").strip().lower()
    if status not in CAMPAIGN_STATUSES:
        raise ValueError("unsupported_campaign_status")
    if intensity not in SEARCH_INTENSITIES:
        raise ValueError("unsupported_search_intensity")
    return {
        "name": _text(payload.get("name")) or "Job search campaign",
        "status": status,
        "target_countries": _strings(payload.get("target_countries")),
        "target_occupations": _strings(payload.get("target_occupations")),
        "target_employers": _strings(payload.get("target_employers")),
        "work_authorized_countries": _strings(payload.get("work_authorized_countries")),
        "sponsorship_required": bool(payload.get("sponsorship_required", False)),
        "relocation_support_preferred": bool(payload.get("relocation_support_preferred", False)),
        "search_intensity": intensity,
        "notes": _text(payload.get("notes")),
    }


def validate_campaign(campaign: Mapping[str, Any]) -> dict[str, Any]:
    normalized=normalize_campaign(campaign);errors=[];warnings=[]
    if not normalized["target_countries"]: errors.append("target_country_required")
    if not normalized["target_occupations"]: errors.append("target_occupation_required")
    if normalized["sponsorship_required"] and set(normalized["target_countries"]) & set(normalized["work_authorized_countries"]):
        warnings.append("sponsorship_requirement_may_not_apply_to_all_work_authorized_targets")
    if not normalized["target_employers"]:
        warnings.append("open_employer_targeting")
    return {"ok":not errors,"errors":errors,"warnings":warnings,"campaign":normalized,"contract_version":CONTRACT_VERSION}


def campaign_contract(campaign: Mapping[str, Any]) -> dict[str, Any]:
    validation=validate_campaign(campaign)
    return {
        **validation,
        "capabilities": {
            "vacancy_association": True,
            "application_association": True,
            "goal_tracking": True,
            "analytics_feedback": True,
            "daily_action_planning": True,
        },
        "safety": {
            "campaign_does_not_create_work_authorization": True,
            "campaign_does_not_guarantee_sponsorship": True,
            "campaign_does_not_guarantee_relocation_support": True,
            "automatic_application_submission": False,
            "vacancy_evidence_still_required": True,
        },
    }
