from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Mapping, Optional

CONTRACT_VERSION = "b19.5-v1"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [_text(item) for item in value if _text(item)]
    if isinstance(value, str):
        return [part.strip() for part in value.split("\n") if part.strip()]
    return []


def source_fingerprint(vacancy: Mapping[str, Any], profile: Mapping[str, Any], materials: Mapping[str, Any]) -> str:
    payload = {
        "job_id": vacancy.get("id"),
        "canonical_identity": vacancy.get("canonical_identity"),
        "updated_at": vacancy.get("updated_at"),
        "title": vacancy.get("job_title") or vacancy.get("title"),
        "requirements": vacancy.get("requirements"),
        "description": vacancy.get("description"),
        "profile_updated_at": profile.get("updated_at"),
        "cv_id": materials.get("cv_id"),
        "cv_updated_at": (materials.get("cv") or {}).get("updated_at"),
        "cover_letter_id": materials.get("cover_letter_id"),
        "cover_letter_updated_at": (materials.get("cover_letter") or {}).get("updated_at"),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_tailoring_brief(vacancy: Mapping[str, Any], profile: Mapping[str, Any], materials: Mapping[str, Any]) -> Dict[str, Any]:
    title = _text(vacancy.get("job_title") or vacancy.get("title") or "the role")
    company = _text(vacancy.get("company_name") or vacancy.get("employer_name") or "the employer")
    requirements = _list(vacancy.get("requirements"))
    if not requirements:
        requirements = _list(vacancy.get("description"))[:12]
    skills = _list(profile.get("skills"))
    achievements = _list(profile.get("achievements") or profile.get("career_achievements"))
    experience = _list(profile.get("experience_summary") or profile.get("experience"))
    return {
        "role_title": title,
        "company_name": company,
        "requirements": requirements[:20],
        "candidate_skills": skills[:30],
        "candidate_achievements": achievements[:20],
        "candidate_experience": experience[:20],
        "bound_cv_id": materials.get("cv_id"),
        "bound_cover_letter_id": materials.get("cover_letter_id"),
    }


def build_application_draft(vacancy: Mapping[str, Any], profile: Mapping[str, Any], materials: Mapping[str, Any], *, readiness: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    readiness = readiness or {}
    state = _text(readiness.get("state")).lower()
    if state not in {"ready_for_review", "ready_to_apply", "application_started"}:
        return {"ok": False, "error": "vacancy_not_ready_for_drafting", "readiness_state": state, "contract_version": CONTRACT_VERSION}
    if not materials.get("cv_id") or materials.get("cv_valid") is False:
        return {"ok": False, "error": "valid_bound_cv_required", "contract_version": CONTRACT_VERSION}

    brief = build_tailoring_brief(vacancy, profile, materials)
    title, company = brief["role_title"], brief["company_name"]
    facts = brief["candidate_achievements"] + brief["candidate_experience"] + brief["candidate_skills"]
    supported = facts[:8]
    requirement_lines = brief["requirements"][:8]

    cv_draft = {
        "target_title": title,
        "professional_summary_guidance": f"Tailor the summary for {title} at {company} using only verified profile and bound-CV facts.",
        "evidence_to_prioritize": supported,
        "requirements_to_address": requirement_lines,
        "fabrication_prohibited": True,
    }
    cover_letter = {
        "opening": f"Application for {title} at {company}",
        "evidence_points": supported[:5],
        "requirements_to_address": requirement_lines[:5],
        "instruction": "Draft concise paragraphs using only supplied candidate facts; do not invent qualifications, work rights, sponsorship, metrics, employers, dates, or certifications.",
    }
    answers = {
        "status": "needs_employer_questions" if vacancy.get("application_questions_required") else "not_required_or_not_detected",
        "answering_rule": "Answer only from verified profile/material facts. Unknown facts must remain unanswered for user review.",
    }
    return {
        "ok": True,
        "contract_version": CONTRACT_VERSION,
        "source_fingerprint": source_fingerprint(vacancy, profile, materials),
        "brief": brief,
        "cv_draft": cv_draft,
        "cover_letter_draft": cover_letter,
        "application_answers": answers,
        "safety": {
            "user_review_required": True,
            "auto_submit_allowed": False,
            "fabrication_allowed": False,
            "eligibility_or_sponsorship_claims_must_be_verified": True,
        },
    }
