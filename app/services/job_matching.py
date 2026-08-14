from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Sequence, Set, Tuple


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


def _country(value: Any) -> str:
    return str(value or "").strip().casefold()


def _is_local(job: Dict[str, Any], profile: Dict[str, Any]) -> bool:
    current_country = _country(profile.get("current_country"))
    return bool(current_country) and _country(job.get("country")) == current_country


def _authorized_for_job(job: Dict[str, Any], profile: Dict[str, Any]) -> bool:
    country = _country(job.get("country"))
    authorized = {_country(item) for item in profile.get("work_authorized_countries") or []}
    if country and country in authorized:
        return True
    if country == _country(profile.get("primary_country")):
        return str(profile.get("work_authorization_status") or "") in {
            "citizen", "permanent_resident", "open_permit",
        }
    return False


def score_job(job: Dict[str, Any], profile: Dict[str, Any] | None) -> Tuple[int, List[str]]:
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
    elif {"production", "manufacturing", "injection", "pet", "process"} & title_tokens:
        score += 15
        reasons.append("Role is in your target manufacturing field.")

    skill_overlap = skill_tokens & profile_skill_tokens
    if skill_overlap:
        score += min(25, len(skill_overlap) * 5)
        reasons.append(f"Shared skills: {', '.join(sorted(skill_overlap)[:4])}.")

    if _country(job.get("country")) == _country(profile.get("primary_country")):
        score += 10
        reasons.append("Matches your primary target country.")

    preferred_provinces = {str(item).casefold() for item in profile.get("preferred_provinces") or []}
    province = str(job.get("province") or "").casefold()
    if province and province in preferred_provinces:
        score += 5
        reasons.append("Matches a preferred province.")

    years = int(profile.get("years_experience") or 0)
    if years >= 10 and {"supervisor", "manager", "specialist", "senior"} & title_tokens:
        score += 10
        reasons.append("Seniority aligns with your recorded experience.")

    if str(job.get("status") or "open") == "open":
        score += 5

    return min(score, 100), reasons or ["No strong match signal has been recorded yet."]


def application_viability(job: Dict[str, Any], profile: Dict[str, Any] | None, skill_score: int) -> Tuple[int, str, List[str]]:
    """Score whether applying is realistic, separately from technical fit."""
    if not profile:
        return 0, "unknown", ["Complete your work-location and authorization profile before prioritizing this vacancy."]

    scope = str(profile.get("search_scope") or "international").casefold()
    local = _is_local(job, profile)
    reasons: List[str] = []

    if scope == "local" and not local:
        return 0, "out_of_scope", ["This vacancy is outside your selected local job-search scope."]
    if scope == "international" and local:
        return 0, "out_of_scope", ["This vacancy is local, while your current search is set to international only."]

    if local:
        return skill_score, "recommended" if skill_score >= 65 else "consider", ["Local vacancy: immigration sponsorship is not used to reduce its priority."]

    authorized = _authorized_for_job(job, profile)
    sponsorship = str(job.get("visa_sponsorship_status") or "unknown").casefold()
    requirement = str(job.get("work_authorization_requirement") or "unknown").casefold()

    if authorized:
        reasons.append("You have recorded work authorization for this vacancy country.")
        return skill_score, "recommended" if skill_score >= 65 else "consider", reasons

    if sponsorship == "not_available" or requirement == "existing_required":
        reasons.append("The vacancy requires existing work authorization or explicitly does not offer sponsorship.")
        return min(skill_score, 20), "not_recommended", reasons

    if sponsorship == "confirmed" or requirement == "employer_support_confirmed":
        reasons.append("Employer support is recorded as confirmed; verify the official vacancy before applying.")
        return min(100, skill_score + 10), "recommended" if skill_score >= 55 else "consider", reasons

    if sponsorship == "possible" or requirement == "employer_support_possible":
        reasons.append("Employer support may be possible but still needs vacancy-level verification.")
        return min(skill_score, 75), "consider", reasons

    reasons.append("Your work authorization for this country is not recorded and sponsorship is not confirmed.")
    return min(skill_score, 50), "verify_authorization", reasons


def rank_jobs(jobs: Sequence[Dict[str, Any]], profile: Dict[str, Any] | None) -> List[Dict[str, Any]]:
    ranked: List[Dict[str, Any]] = []
    for row in jobs:
        score, reasons = score_job(row, profile)
        viability_score, priority, viability_reasons = application_viability(row, profile, score)
        local = bool(profile and _is_local(row, profile))
        ranked.append({
            **row,
            "match_score": score,
            "match_reasons": reasons,
            # Canonical V1 names used by the UI and analytics.
            "application_viability_score": viability_score,
            "application_priority_score": viability_score,
            "application_priority": priority,
            "viability_reasons": viability_reasons,
            "application_priority_reasons": viability_reasons,
            "search_scope_classification": "local" if local else "international",
            # Backward-compatible convenience flag for existing consumers.
            "is_local_job": local,
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
