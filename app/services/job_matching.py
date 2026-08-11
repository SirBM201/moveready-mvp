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


def score_job(job: Dict[str, Any], profile: Dict[str, Any] | None) -> Tuple[int, List[str]]:
    """Return a transparent starter match score, not an employment prediction.

    The score is deliberately deterministic so Sprint 1 can rank user-saved
    opportunities without an AI provider. A later matching service can replace
    this function while preserving the API contract.
    """
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
        score += min(20, len(skill_overlap) * 5)
        reasons.append(f"Shared skills: {', '.join(sorted(skill_overlap)[:4])}.")

    if str(job.get("country") or "").casefold() == str(profile.get("primary_country") or "").casefold():
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

    sponsorship = str(job.get("visa_sponsorship_status") or "unknown")
    if sponsorship == "confirmed":
        score += 10
        reasons.append("Employer sponsorship is marked confirmed; verify it on the vacancy.")
    elif sponsorship == "possible":
        score += 5
        reasons.append("Sponsorship is marked possible and still requires vacancy-level verification.")

    if str(job.get("status") or "open") == "open":
        score += 5

    return min(score, 100), reasons or ["No strong match signal has been recorded yet."]


def rank_jobs(jobs: Sequence[Dict[str, Any]], profile: Dict[str, Any] | None) -> List[Dict[str, Any]]:
    ranked: List[Dict[str, Any]] = []
    for row in jobs:
        score, reasons = score_job(row, profile)
        ranked.append({**row, "match_score": score, "match_reasons": reasons})
    return sorted(
        ranked,
        key=lambda item: (int(item.get("match_score") or 0), str(item.get("updated_at") or "")),
        reverse=True,
    )
