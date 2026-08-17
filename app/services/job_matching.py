from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Sequence, Set, Tuple

from app.services.job_authorization import extract_authorization_signals
from app.services.job_scope import (
    country_key,
    job_scope_classification,
    profile_scope_contract,
)


IGNORED_TOKENS = {
    "a", "an", "and", "for", "in", "lead", "of", "or", "the", "to",
}


def _tokens(values: Iterable[Any]) -> Set[str]:
    tokens: Set[str] = set()
    for value in values:
        normalized = str(value or "").lower().replace("mould", "mold")
        for token in re.findall(r"[a-z0-9]+", normalized):
            if len(token) > 1 and token not in IGNORED_TOKENS:
                tokens.add(token)
    return tokens


def _is_local(job: Dict[str, Any], profile: Dict[str, Any]) -> bool:
    return job_scope_classification(job, profile) == "local"


def _authorized_for_job(job: Dict[str, Any], profile: Dict[str, Any]) -> bool:
    country = country_key(job.get("country"))
    authorized = {
        country_key(item) for item in profile.get("work_authorized_countries") or []
    }
    if country and country in authorized:
        return True
    if country == country_key(profile.get("primary_country")):
        return str(profile.get("work_authorization_status") or "") in {
            "citizen", "permanent_resident", "open_permit",
        }
    return False


def _with_authorization_signals(job: Dict[str, Any]) -> Dict[str, Any]:
    """Fill unknown vacancy authorization fields from explicit source wording."""
    extracted = extract_authorization_signals(job)
    enriched = dict(job)
    for key in (
        "work_authorization_requirement",
        "visa_sponsorship_status",
        "relocation_support_status",
    ):
        if (
            not str(enriched.get(key) or "").strip()
            or str(enriched.get(key)).casefold() == "unknown"
        ):
            enriched[key] = extracted[key]
    if extracted.get("authorization_evidence"):
        enriched["authorization_evidence"] = extracted["authorization_evidence"]
        enriched["sponsorship_evidence"] = extracted.get("sponsorship_evidence")
    return enriched


def score_job(
    job: Dict[str, Any],
    profile: Dict[str, Any] | None,
) -> Tuple[int, List[str]]:
    """Return transparent skills/role fit, not an employment or visa prediction."""
    if not profile:
        return 0, ["Complete a job-search profile to calculate a match."]

    score = 0
    reasons: List[str] = []
    title_tokens = _tokens([job.get("job_title")])
    role_tokens = _tokens(profile.get("target_roles") or [])
    skill_tokens = _tokens(job.get("skills") or [])
    profile_skill_tokens = _tokens(profile.get("skills") or [])

    role_overlap = title_tokens & role_tokens
    if role_overlap:
        score += min(50, 20 + (len(role_overlap) * 10))
        reasons.append("Title overlaps your target role profile.")

    skill_overlap = skill_tokens & profile_skill_tokens
    if skill_overlap:
        score += min(25, len(skill_overlap) * 5)
        reasons.append(f"Shared skills: {', '.join(sorted(skill_overlap)[:4])}.")

    contract = profile_scope_contract(profile)
    target_countries = {
        country_key(item) for item in contract["target_countries"]
    }
    if country_key(job.get("country")) in target_countries:
        score += 10
        reasons.append("Matches one of your selected job-search countries.")

    preferred_provinces = {
        str(item).casefold() for item in profile.get("preferred_provinces") or []
    }
    province = str(job.get("province") or "").casefold()
    if province and province in preferred_provinces:
        score += 5
        reasons.append("Matches a preferred province or region.")

    years = int(profile.get("years_experience") or 0)
    if years >= 10 and {
        "supervisor", "manager", "specialist", "senior",
    } & title_tokens:
        score += 10
        reasons.append("Seniority aligns with your recorded experience.")

    if str(job.get("status") or "open") == "open":
        score += 5

    return min(score, 100), reasons or [
        "No strong match signal has been recorded yet."
    ]


def application_viability(
    job: Dict[str, Any],
    profile: Dict[str, Any] | None,
    skill_score: int,
) -> Tuple[int, str, List[str]]:
    """Score whether applying is realistic, separately from technical fit."""
    if not profile:
        return 0, "profile_incomplete", [
            "Complete your work-location and authorization profile before prioritizing this vacancy."
        ]

    job = _with_authorization_signals(job)
    contract = profile_scope_contract(profile)
    if not contract["ready"]:
        return 0, "profile_incomplete", [
            "Complete the missing job-search scope fields before prioritizing vacancies."
        ]

    scope = contract["search_scope"]
    classification = job_scope_classification(job, profile)
    reasons: List[str] = []

    if scope == "local" and classification != "local":
        return 0, "out_of_scope", [
            "This vacancy is outside your selected local job-search scope."
        ]
    if scope == "international" and classification == "local":
        return 0, "out_of_scope", [
            "This vacancy is local, while your search is international only."
        ]

    job_country = country_key(job.get("country"))
    international_targets = {
        country_key(item)
        for item in contract["international_target_countries"]
    }
    if classification == "international" and job_country not in international_targets:
        return 0, "out_of_scope", [
            "This vacancy country is outside your selected international targets."
        ]

    authorized = _authorized_for_job(job, profile)
    if classification == "local":
        if authorized:
            return (
                skill_score,
                "recommended" if skill_score >= 65 else "consider",
                [
                    "Local vacancy: you recorded work authorization for its country."
                ],
            )
        return min(skill_score, 50), "verify_authorization", [
            "Local vacancy: your work authorization for the country is not recorded."
        ]

    sponsorship = str(
        job.get("visa_sponsorship_status") or "unknown"
    ).casefold()
    requirement = str(
        job.get("work_authorization_requirement") or "unknown"
    ).casefold()

    if authorized:
        reasons.append(
            "You recorded work authorization for this vacancy country."
        )
        return (
            skill_score,
            "recommended" if skill_score >= 65 else "consider",
            reasons,
        )

    if sponsorship == "not_available" or requirement == "existing_required":
        reasons.append(
            "The vacancy requires existing work authorization or explicitly does not offer sponsorship."
        )
        return min(skill_score, 20), "not_recommended", reasons

    if (
        sponsorship == "confirmed"
        or requirement == "employer_support_confirmed"
    ):
        reasons.append(
            "Employer support is recorded as confirmed; verify the official vacancy before applying."
        )
        return (
            min(100, skill_score + 10),
            "recommended" if skill_score >= 55 else "consider",
            reasons,
        )

    if sponsorship == "possible" or requirement == "employer_support_possible":
        reasons.append(
            "Employer support may be possible but still needs vacancy-level verification."
        )
        return min(skill_score, 75), "consider", reasons

    reasons.append(
        "Your work authorization for this country is not recorded and sponsorship is not confirmed."
    )
    return min(skill_score, 50), "verify_authorization", reasons


def rank_jobs(
    jobs: Sequence[Dict[str, Any]],
    profile: Dict[str, Any] | None,
) -> List[Dict[str, Any]]:
    ranked: List[Dict[str, Any]] = []
    contract = profile_scope_contract(profile)
    for row in jobs:
        enriched_row = _with_authorization_signals(row)
        score, reasons = score_job(enriched_row, profile)
        viability_score, priority, viability_reasons = application_viability(
            enriched_row, profile, score
        )
        classification = job_scope_classification(enriched_row, profile)
        ranked.append({
            **enriched_row,
            "match_score": score,
            "match_reasons": reasons,
            "application_viability_score": viability_score,
            "application_priority_score": viability_score,
            "application_priority": priority,
            "viability_reasons": viability_reasons,
            "application_priority_reasons": viability_reasons,
            "search_scope_classification": classification,
            "search_contract_version": contract["version"],
            "is_local_job": classification == "local",
        })
    return sorted(
        ranked,
        key=lambda item: (
            int(item.get("application_priority_score") or 0),
            int(item.get("match_score") or 0),
            str(item.get("updated_at") or ""),
        ),
        reverse=True,
    )
