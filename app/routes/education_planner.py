from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

from app.services.supabase_client import get_supabase


bp = Blueprint("education_planner", __name__)


STUDY_LEVELS = [
    "foundation",
    "certificate",
    "diploma",
    "bachelor",
    "top_up_bachelor",
    "postgraduate_diploma",
    "masters",
    "phd",
    "professional_conversion",
    "healthcare_licensing",
]

LANGUAGE_EVIDENCE = [
    "none",
    "medium_of_instruction",
    "ielts",
    "toefl",
    "pte",
    "duolingo",
    "other",
]

GRADE_BANDS = [
    "distinction_or_first",
    "upper_second_or_credit",
    "lower_second",
    "third_class",
    "pass",
    "gpa_not_sure",
    "not_applicable",
]



def _text(value: Any, limit: int = 500) -> str:
    return str(value or "").strip()[:limit]



def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value, 20).lower() in {"1", "true", "yes", "y", "on"}



def _int(value: Any, default: int = 0, minimum: int = 0, maximum: int = 100) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = default
    return min(max(parsed, minimum), maximum)



def _float(value: Any, default: float = 0.0, minimum: float = 0.0, maximum: float = 1_000_000_000.0) -> float:
    try:
        parsed = float(value)
    except Exception:
        parsed = default
    return min(max(parsed, minimum), maximum)



def _date(value: Any) -> Optional[date]:
    raw = _text(value, 40)
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None



def _risk_level(score: int) -> str:
    if score >= 70:
        return "high"
    if score >= 35:
        return "medium"
    return "low"



def _readiness_status(risk_level: str) -> str:
    if risk_level == "high":
        return "needs_attention"
    if risk_level == "medium":
        return "review_recommended"
    return "ready_to_continue"



def _store_run(payload: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    result["stored"] = False
    try:
        row = {
            "tool_slug": "study_admission_plan",
            "status": "completed",
            "risk_level": result.get("risk_level"),
            "readiness_status": result.get("readiness_status"),
            "input_payload": payload,
            "result_payload": result,
            "source_page": _text(payload.get("source_page"), 240) or None,
        }
        response = get_supabase().table("relocation_readiness_check_runs").insert(row).execute()
        stored = (response.data or [None])[0]
        if stored:
            result["stored"] = True
            result["id"] = stored.get("id")
    except Exception:
        result["storage_note"] = "The study plan was generated but could not be saved. Run the readiness storage SQL if persistence is required."
    return result



def _months_until(value: Optional[date]) -> Optional[int]:
    if not value:
        return None
    today = date.today()
    return (value.year - today.year) * 12 + (value.month - today.month)



def _field_change_strategy(desired_level: str, field_change: bool, regulated_profession: bool) -> List[str]:
    strategies: List[str] = []
    if regulated_profession:
        strategies.extend(
            [
                "Check whether the programme leads to professional registration or only an academic qualification.",
                "Confirm regulator recognition, clinical placement, licensing examination, language, health, character, and local-practice requirements.",
                "Do not assume that a health-related master's degree qualifies a graduate to practise as a nurse, pharmacist, doctor, or other regulated professional.",
            ]
        )
    if field_change:
        strategies.extend(
            [
                "Prioritize conversion, foundation, bridging, pre-master's, postgraduate diploma, or interdisciplinary programmes that explicitly accept unrelated degrees.",
                "Prepare a coherent statement explaining the field change, transferable skills, relevant work or volunteer evidence, and realistic career outcome.",
                "Avoid applying to programmes whose published prerequisites require substantial prior study that the applicant does not have.",
            ]
        )
    elif desired_level in {"masters", "postgraduate_diploma", "phd"}:
        strategies.append("Prioritize programmes whose published academic prerequisites match the previous qualification and subject background.")
    else:
        strategies.append("Confirm entry level, progression route, credit recognition, and whether the qualification supports the intended career or further study.")
    return strategies


@bp.get("/options")
def education_options():
    return jsonify(
        {
            "ok": True,
            "study_levels": STUDY_LEVELS,
            "language_evidence": LANGUAGE_EVIDENCE,
            "grade_bands": GRADE_BANDS,
            "safety_note": "Institution, programme, scholarship, visa, professional-registration, and family rules must be confirmed from current official sources.",
        }
    )


@bp.post("/study-plan")
def study_plan():
    payload = request.get_json(silent=True) or {}

    target_country = _text(payload.get("target_country"), 120)
    desired_level = _text(payload.get("desired_level"), 80) or "masters"
    highest_qualification = _text(payload.get("highest_qualification"), 160)
    qualification_field = _text(payload.get("qualification_field"), 180)
    graduation_year = _int(payload.get("graduation_year"), 0, 1950, 2100)
    grade_band = _text(payload.get("grade_band"), 80) or "gpa_not_sure"
    desired_field = _text(payload.get("desired_field"), 180)
    field_change = _bool(payload.get("field_change"))
    regulated_profession = _bool(payload.get("regulated_profession"))
    language_evidence = _text(payload.get("language_evidence"), 80) or "none"
    work_experience_years = _int(payload.get("work_experience_years"), 0, 0, 60)
    scholarship_required = _bool(payload.get("scholarship_required"))
    family_members_count = _int(payload.get("family_members_count"), 0, 0, 20)
    prior_admission_refusal = _bool(payload.get("prior_admission_refusal"))
    prior_visa_refusal = _bool(payload.get("prior_visa_refusal"))
    target_intake_date = _date(payload.get("target_intake_date"))
    months_until_intake = _months_until(target_intake_date)

    available_funds = _float(payload.get("available_funds_amount"), 0)
    tuition_budget = _float(payload.get("annual_tuition_budget"), 0)
    living_budget = _float(payload.get("annual_living_budget"), 0)
    currency = _text(payload.get("currency"), 20) or "EUR"
    estimated_annual_budget = tuition_budget + living_budget
    funding_gap = max(0.0, estimated_annual_budget - available_funds) if estimated_annual_budget else None

    risk_score = 0
    warnings: List[str] = []

    if not target_country:
        warnings.append("Target country is not selected, so visa, funds, institution, and family rules cannot yet be narrowed.")
        risk_score += 10
    if not highest_qualification:
        warnings.append("Highest qualification is not recorded.")
        risk_score += 15
    if not qualification_field:
        warnings.append("Previous field of study is not recorded.")
        risk_score += 10
    if not desired_field:
        warnings.append("Desired study field is not recorded.")
        risk_score += 10
    if grade_band in {"third_class", "pass"}:
        warnings.append("The recorded grade may narrow direct-entry options. Search for institutions that explicitly publish flexible, pathway, experience-based, or conversion entry routes.")
        risk_score += 20
    elif grade_band == "gpa_not_sure":
        warnings.append("Academic grade equivalence has not been checked against institution-specific requirements.")
        risk_score += 10
    if field_change:
        warnings.append("The planned subject change needs programmes that explicitly accept unrelated academic backgrounds.")
        risk_score += 15
    if regulated_profession:
        warnings.append("The desired field is regulated or practice-sensitive. Academic admission alone may not create professional practice rights.")
        risk_score += 25
    if language_evidence in {"none", "medium_of_instruction"}:
        warnings.append("A waiver or medium-of-instruction letter may not be accepted by every institution, visa authority, regulator, or programme.")
        risk_score += 15
    if scholarship_required:
        warnings.append("The plan depends on scholarship or major funding support. Keep an affordable alternative and do not treat scholarship applications as guaranteed funding.")
        risk_score += 20
    if estimated_annual_budget and funding_gap and funding_gap > 0:
        warnings.append(f"The planning figures show a {currency} {funding_gap:,.2f} gap between available funds and the entered first-year tuition plus living budget.")
        risk_score += 25
    if family_members_count > 0:
        warnings.append("Accompanying family members can increase funds, accommodation, insurance, school, childcare, and dependant-visa complexity.")
        risk_score += 15
    if prior_admission_refusal:
        warnings.append("A previous admission refusal should be compared with the new programme, academic fit, documents, statement, and funding evidence.")
        risk_score += 10
    if prior_visa_refusal:
        warnings.append("A previous visa refusal requires truthful disclosure and a documented repair plan before a new study-visa application.")
        risk_score += 20
    if months_until_intake is not None:
        if months_until_intake < 0:
            warnings.append("The selected intake date is in the past.")
            risk_score += 70
        elif months_until_intake < 4:
            warnings.append("The intake is less than four months away, which may be too tight for course research, applications, offers, funds, documents, visa processing, and travel.")
            risk_score += 30
        elif months_until_intake < 7:
            warnings.append("The intake is approaching. Prioritize programmes with confirmed open applications and realistic visa timing.")
            risk_score += 15

    if graduation_year and date.today().year - graduation_year >= 8 and work_experience_years == 0:
        warnings.append("There is a long period since graduation but no work experience was recorded. Prepare a clear activity history and current academic-readiness evidence.")
        risk_score += 10

    risk_level = _risk_level(risk_score)

    stages = [
        {
            "stage": "1. Academic profile audit",
            "actions": [
                "Collect official certificate, transcript, grading scale, course descriptions where needed, and name-consistency evidence.",
                "Check programme prerequisites, minimum grade, subject credits, experience requirements, and accepted qualification equivalence on each institution's official page.",
                "Record any academic gap, employment, business, caregiving, training, volunteering, or professional development truthfully.",
            ],
        },
        {
            "stage": "2. Programme and institution shortlist",
            "actions": [
                "Shortlist accredited or officially recognized institutions and verify the exact campus, delivery mode, awarding body, programme duration, intake, and tuition.",
                "Separate ambitious, realistic, and safer academic-fit options instead of applying only to one institution.",
                "Check whether the programme supports the intended profession, post-study route, licensing path, or further study outcome.",
            ],
        },
        {
            "stage": "3. Admission evidence",
            "actions": [
                "Prepare statement of purpose, CV, references, portfolio or research proposal where required.",
                "Explain field changes, study gaps, low grades, previous refusals, and career logic without hiding material facts.",
                "Confirm application fee, document format, certified copy, translation, legalization, deadline, and interview requirements.",
            ],
        },
        {
            "stage": "4. Funding and affordability",
            "actions": [
                "Separate tuition, living costs, visa proof-of-funds, deposits, insurance, travel, family, housing, and emergency funds.",
                "Confirm scholarship eligibility, deadline, coverage, renewal conditions, and whether a separate admission application is required.",
                "Avoid unexplained large deposits, borrowed-funds misrepresentation, fake sponsorship, or treating a conditional scholarship as guaranteed money.",
            ],
        },
        {
            "stage": "5. Offer verification and acceptance",
            "actions": [
                "Verify the offer through the institution's official account or contact channel before paying.",
                "Check conditions, deposit, refund, deferral, credibility interview, document verification, and final-enrolment requirements.",
                "Use only official payment instructions and retain receipts and written refund terms.",
            ],
        },
        {
            "stage": "6. Study-visa preparation",
            "actions": [
                "Use the destination government's current student-visa checklist and confirm application location, biometrics, medical, police, insurance, funds, and interview requirements.",
                "Align course choice, previous education, work history, finances, family plan, and future intentions consistently.",
                "Disclose refusals, immigration history, dependants, sponsors, and source of funds truthfully.",
            ],
        },
        {
            "stage": "7. Family and arrival",
            "actions": [
                "Confirm whether dependants are allowed for the exact study level and route, and whether they can accompany or join later.",
                "Plan accommodation, school or childcare, insurance, transport, registration, banking, tax, and first-90-days expenses.",
                "Do not assume student work rights, dependant work rights, post-study work, permanent residence, or professional registration without checking the current rule.",
            ],
        },
    ]

    evidence_checklist = [
        "Passport and previous passports where requested",
        "Certificate, transcript, grading scale, and programme-specific prerequisites",
        "English or other language evidence accepted by the institution and visa route",
        "CV, statement of purpose, references, portfolio, research proposal, or work evidence where required",
        "Official funds evidence, sponsor relationship and capacity, source-of-funds explanation, and payment records",
        "Civil documents for spouse or children where family is included",
        "Previous refusal letters and evidence showing how the new application addresses the reasons",
        "Offer verification, deposit receipt, tuition schedule, refund rules, and accommodation plan",
    ]

    result = {
        "ok": True,
        "target_country": target_country,
        "desired_level": desired_level,
        "highest_qualification": highest_qualification,
        "qualification_field": qualification_field,
        "graduation_year": graduation_year or None,
        "grade_band": grade_band,
        "desired_field": desired_field,
        "field_change": field_change,
        "regulated_profession": regulated_profession,
        "language_evidence": language_evidence,
        "work_experience_years": work_experience_years,
        "family_members_count": family_members_count,
        "target_intake_date": target_intake_date.isoformat() if target_intake_date else None,
        "months_until_intake": months_until_intake,
        "currency": currency,
        "available_funds_amount": available_funds,
        "annual_tuition_budget": tuition_budget,
        "annual_living_budget": living_budget,
        "estimated_annual_budget": estimated_annual_budget or None,
        "planning_funding_gap": funding_gap,
        "risk_level": risk_level,
        "readiness_status": _readiness_status(risk_level),
        "summary": "A study-admission and visa preparation plan has been generated from the information supplied. It does not identify a guaranteed university, scholarship, admission outcome, visa result, work right, licensing outcome, or permanent-residence pathway.",
        "programme_strategy": _field_change_strategy(desired_level, field_change, regulated_profession),
        "stages": stages,
        "evidence_checklist": evidence_checklist,
        "warnings": warnings,
        "official_checks": [
            "Institution recognition and official programme page",
            "Programme prerequisites and application deadline",
            "Tuition, deposit, scholarship, and refund terms",
            "Destination-government student-visa rules",
            "Professional regulator rules for regulated careers",
            "Dependant eligibility and work or school conditions",
            "Post-study work and residence rules, without assuming they will remain unchanged",
        ],
        "safety_note": "Use official institutions, government immigration pages, recognized regulators, and verified payment channels. Never pay for guaranteed admission, scholarship, visa, job, licensing, or permanent residence.",
    }
    return jsonify(_store_run(payload, result))
