from __future__ import annotations

import io
import re
from typing import Any, Dict, List, Sequence, Tuple


MAX_EXTRACTED_RESUME_CHARS = 30000
ACHIEVEMENT_HINTS = {
    "achieved", "built", "delivered", "improved", "increased", "introduced", "led", "managed",
    "optimized", "reduced", "resolved", "saved", "supervised", "trained",
}


def _clean(value: Any, limit: int = 4000) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _lines(value: str) -> List[str]:
    output: List[str] = []
    seen = set()
    for raw in re.split(r"[\r\n]+|(?<=[.;])\s+(?=[A-Z0-9])", value or ""):
        line = _clean(raw, 360).lstrip("•-* ")
        key = line.casefold()
        if 18 <= len(line) <= 360 and key not in seen:
            seen.add(key)
            output.append(line)
    return output


def extract_resume_text(contents: bytes, mime_type: str) -> str:
    if mime_type == "text/plain":
        return contents.decode("utf-8", errors="replace")[:MAX_EXTRACTED_RESUME_CHARS]
    if mime_type == "application/pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:  # pragma: no cover - deployment dependency guard
            raise RuntimeError("pdf_resume_extraction_unavailable") from exc
        reader = PdfReader(io.BytesIO(contents))
        text = "\n".join((page.extract_text() or "") for page in reader.pages[:20])
        return text[:MAX_EXTRACTED_RESUME_CHARS]
    if mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        try:
            from docx import Document
        except ImportError as exc:  # pragma: no cover - deployment dependency guard
            raise RuntimeError("docx_resume_extraction_unavailable") from exc
        document = Document(io.BytesIO(contents))
        text = "\n".join(paragraph.text for paragraph in document.paragraphs)
        return text[:MAX_EXTRACTED_RESUME_CHARS]
    raise RuntimeError("unsupported_resume_file_type")


def evidence_from_resume(resume_text: str, *, limit: int = 8) -> List[str]:
    candidates: List[Tuple[int, str]] = []
    for line in _lines(resume_text):
        lowered = line.casefold()
        score = 0
        if any(hint in lowered for hint in ACHIEVEMENT_HINTS):
            score += 2
        if re.search(r"\b\d+(?:\.\d+)?\s*(?:%|tonnes?|hours?|minutes?|people|operators?|machines?|cavities)\b", lowered):
            score += 3
        if len(line) <= 220:
            score += 1
        if score:
            candidates.append((score, line))
    candidates.sort(key=lambda item: (item[0], len(item[1])), reverse=True)
    return [line for _score, line in candidates[:limit]]


def _tokens(value: Any) -> set[str]:
    text = " ".join(str(item or "") for item in value) if isinstance(value, list) else str(value or "")
    return {
        token for token in re.findall(r"[a-z0-9]+", text.casefold().replace("mould", "mold"))
        if len(token) > 2 and token not in {"and", "for", "from", "the", "this", "with"}
    }


def ordered_skills(profile_skills: Sequence[Any], job: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    job_tokens = _tokens([
        job.get("job_title"),
        job.get("description_summary"),
        *(job.get("skills") or []),
    ])
    matched: List[str] = []
    other: List[str] = []
    for value in profile_skills:
        skill = _clean(value, 100)
        if not skill:
            continue
        if _tokens(skill) & job_tokens:
            matched.append(skill)
        else:
            other.append(skill)
    return matched, other


def build_application_drafts(
    *,
    profile: Dict[str, Any],
    job: Dict[str, Any],
    company_name: str,
    resume_asset_id: str,
    resume_text: str,
) -> List[Dict[str, Any]]:
    display_name = _clean(profile.get("display_name"), 120) or "Candidate"
    headline = _clean(profile.get("headline"), 180) or "Experienced professional"
    job_title = _clean(job.get("job_title"), 220) or "the advertised role"
    country = _clean(job.get("country"), 100)
    location = ", ".join(filter(None, [_clean(job.get("city"), 100), _clean(job.get("province"), 100), country]))
    years = int(profile.get("years_experience") or 0)
    current_employer = _clean(profile.get("current_employer"), 180)
    previous_employer = _clean(profile.get("previous_employer"), 180)
    education = _clean(profile.get("education_level"), 180)
    work_status = _clean(profile.get("work_authorization_status"), 80).replace("_", " ")
    recorded_facts = [_clean(item, 360) for item in profile.get("career_facts") or [] if _clean(item, 360)]
    resume_facts = evidence_from_resume(resume_text)
    facts: List[str] = []
    for value in [*recorded_facts, *resume_facts]:
        if value.casefold() not in {item.casefold() for item in facts}:
            facts.append(value)
        if len(facts) >= 10:
            break
    matched_skills, other_skills = ordered_skills(profile.get("skills") or [], job)
    selected_skills = [*matched_skills, *other_skills][:14]

    warnings: List[str] = [
        "Review every line against your base resume before approval.",
        "Add your real phone, email, address, dates, and complete employment history before use.",
        "Confirm the employer's current work-authorization and sponsorship requirements on the official vacancy.",
    ]
    if not facts:
        warnings.append("No verified achievement evidence was found. Add career facts or use a resume with selectable text before approval.")
    if not matched_skills:
        warnings.append("No strong recorded-skill overlap was found; do not add vacancy keywords unless they are genuinely yours.")

    experience_lines = "\n".join(f"- {fact}" for fact in facts) or "- Add verified achievements from your base resume."
    skills_line = " | ".join(selected_skills) or "Add verified skills from your profile."
    employer_lines = "\n".join(filter(None, [
        f"Current employer: {current_employer}" if current_employer else "",
        f"Previous employer: {previous_employer}" if previous_employer else "",
    ])) or "Add your verified employment history from the base resume."
    years_phrase = f"{years} years of recorded experience" if years else "recorded professional experience"

    resume_content = f"""{display_name}
[Use the verified contact details from your base resume]

TARGET ROLE
{job_title} — {company_name}{f" — {location}" if location else ""}

PROFESSIONAL SUMMARY
{headline} with {years_phrase}. Brings recorded strengths in {', '.join(selected_skills[:5]) or 'the skills listed in the saved profile'}. Interested in applying this verified background to the {job_title} opportunity at {company_name}.

CORE SKILLS
{skills_line}

VERIFIED EXPERIENCE HIGHLIGHTS
{experience_lines}

EMPLOYMENT
{employer_lines}
[Copy exact titles, dates, duties, and locations from the selected base resume, then remove this instruction.]

EDUCATION
{education or 'Copy the verified education entry from the selected base resume.'}

WORK AUTHORIZATION
Recorded status: {work_status or 'not recorded'}. Confirm the employer's current requirements and keep this wording accurate before use.

APPLICATION NOTE — REMOVE BEFORE USE
This editable draft reorders only saved profile skills and evidence extracted from the selected resume. It does not prove employer sponsorship, eligibility, or submission. Review the full vacancy and every claim before approval.
""".strip()

    fact_sentence = facts[0] if facts else "My saved profile and resume record relevant experience, which I will verify carefully before submitting."
    skills_sentence = ", ".join(matched_skills[:5] or selected_skills[:5]) or "the relevant skills recorded in my profile"
    cover_content = f"""Dear Hiring Team,

I am applying for the {job_title} position at {company_name}. I am a {headline.lower()} with {years_phrase}, and my recorded background includes {skills_sentence}.

One relevant example from my verified career information is: {fact_sentence}

My current and previous employment records include {current_employer or 'the employer shown in my base resume'}{f' and {previous_employer}' if previous_employer else ''}. I would welcome the opportunity to discuss how my documented production, process, leadership, and troubleshooting experience aligns with the requirements of this vacancy.

I am currently based outside the target market and my recorded work-authorization status is “{work_status or 'not recorded'}”. I will follow the employer's official process and will not assume sponsorship or eligibility unless the vacancy or employer confirms it.

Thank you for considering my application.

Sincerely,
{display_name}

[Review and remove all bracketed instructions before use.]
""".strip()

    truth_basis = {
        "source_resume_asset_id": resume_asset_id,
        "profile_fields_used": [
            "display_name", "headline", "years_experience", "education_level", "current_employer",
            "previous_employer", "skills", "career_facts", "work_authorization_status",
        ],
        "matched_skills": matched_skills,
        "verified_fact_count": len(facts),
        "resume_evidence_count": len(resume_facts),
        "vacancy_source_url": job.get("job_url") or job.get("source_url"),
    }

    return [
        {
            "draft_type": "tailored_resume",
            "title": f"Tailored resume — {job_title} at {company_name}",
            "content": resume_content,
            "generation_method": "verified_template",
            "truth_basis": truth_basis,
            "warnings": warnings,
        },
        {
            "draft_type": "cover_letter",
            "title": f"Cover letter — {job_title} at {company_name}",
            "content": cover_content,
            "generation_method": "verified_template",
            "truth_basis": truth_basis,
            "warnings": warnings,
        },
    ]


def approval_confirmations_are_complete(value: Any) -> bool:
    confirmations = value if isinstance(value, dict) else {}
    return all(confirmations.get(key) is True for key in (
        "facts_verified",
        "no_invented_claims",
        "contact_details_checked",
        "work_authorization_checked",
    ))
