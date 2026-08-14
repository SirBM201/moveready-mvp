from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple


Signal = Tuple[str, str]


def _first_match(text: str, patterns: List[Signal]) -> Signal | None:
    for pattern, evidence in patterns:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return pattern, evidence
    return None


def extract_authorization_signals(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """Extract conservative work-rights signals from official vacancy text.

    Unknown stays unknown. MoveReady only promotes a signal when the source text
    contains explicit wording; this prevents a skills match from being mistaken
    for legal/application viability.
    """
    text = " ".join(
        str(candidate.get(key) or "")
        for key in ("job_title", "description_summary")
    ).casefold()

    no_sponsorship = _first_match(text, [
        (r"\bno\s+(?:visa\s+)?sponsorship\b", "Vacancy explicitly says sponsorship is not available."),
        (r"\b(?:visa\s+)?sponsorship\s+(?:is\s+)?not\s+(?:available|provided|offered)\b", "Vacancy explicitly says sponsorship is not available."),
        (r"\b(?:we|employer|company)\s+(?:do|does)\s+not\s+sponsor\b", "Employer explicitly says it does not sponsor."),
        (r"\bunable\s+to\s+(?:provide\s+)?(?:visa\s+)?sponsorship\b", "Employer explicitly says it cannot provide sponsorship."),
    ])
    existing_authorization = _first_match(text, [
        (r"\bmust\s+(?:already\s+|currently\s+)?(?:be\s+)?(?:legally\s+)?authorized\s+to\s+work\b", "Vacancy requires existing work authorization."),
        (r"\bexisting\s+(?:work\s+)?authorization\s+(?:is\s+)?required\b", "Vacancy requires existing work authorization."),
        (r"\bmust\s+have\s+(?:the\s+)?(?:legal\s+)?right\s+to\s+work\b", "Vacancy requires an existing right to work."),
        (r"\bno\s+(?:current\s+or\s+)?future\s+sponsorship\b", "Vacancy requires existing work authorization and excludes future sponsorship."),
    ])
    sponsorship_confirmed = _first_match(text, [
        (r"\bvisa\s+sponsorship\s+(?:is\s+)?(?:available|provided|offered)\b", "Vacancy explicitly offers visa sponsorship."),
        (r"\b(?:we|employer|company)\s+will\s+sponsor\b", "Employer explicitly says it will sponsor."),
        (r"\bemployer[- ]sponsored\s+(?:visa|work\s+permit)\b", "Vacancy explicitly references employer-sponsored authorization."),
        (r"\blmia\s+(?:is\s+)?(?:available|provided|supported)\b", "Vacancy explicitly indicates LMIA support."),
    ])
    sponsorship_possible = _first_match(text, [
        (r"\bvisa\s+sponsorship\s+(?:may|might|can)\s+be\s+(?:available|provided|considered|offered)\b", "Vacancy says sponsorship may be considered."),
        (r"\bmay\s+(?:provide|offer|consider)\s+(?:visa\s+)?sponsorship\b", "Vacancy says sponsorship may be considered."),
        (r"\blmia\s+(?:may|might|can)\s+be\s+(?:available|provided|supported|considered)\b", "Vacancy says LMIA support may be considered."),
    ])
    relocation_confirmed = _first_match(text, [
        (r"\brelocation\s+(?:assistance|support|package)\s+(?:is\s+)?(?:available|provided|offered)\b", "Vacancy explicitly offers relocation support."),
        (r"\b(?:we|employer|company)\s+will\s+(?:provide|offer)\s+relocation\b", "Employer explicitly offers relocation support."),
    ])
    relocation_unavailable = _first_match(text, [
        (r"\bno\s+relocation\s+(?:assistance|support|package)\b", "Vacancy explicitly says relocation support is not available."),
        (r"\brelocation\s+(?:assistance|support|package)\s+(?:is\s+)?not\s+(?:available|provided|offered)\b", "Vacancy explicitly says relocation support is not available."),
    ])

    evidence: List[str] = []
    for match in (no_sponsorship, existing_authorization, sponsorship_confirmed, sponsorship_possible, relocation_confirmed, relocation_unavailable):
        if match and match[1] not in evidence:
            evidence.append(match[1])

    # Negative sponsorship language wins over positive/ambiguous wording.
    if no_sponsorship:
        sponsorship_status = "not_available"
        work_authorization = "existing_required"
    elif sponsorship_confirmed:
        sponsorship_status = "confirmed"
        work_authorization = "employer_support_confirmed"
    elif sponsorship_possible:
        sponsorship_status = "possible"
        work_authorization = "employer_support_possible"
    elif existing_authorization:
        sponsorship_status = "unknown"
        work_authorization = "existing_required"
    else:
        sponsorship_status = "unknown"
        work_authorization = "unknown"

    if relocation_unavailable:
        relocation_status = "not_available"
    elif relocation_confirmed:
        relocation_status = "confirmed"
    else:
        relocation_status = "unknown"

    return {
        "work_authorization_requirement": work_authorization,
        "visa_sponsorship_status": sponsorship_status,
        "relocation_support_status": relocation_status,
        "authorization_evidence": evidence[:8],
        "sponsorship_evidence": "; ".join(evidence[:8]) or None,
    }
