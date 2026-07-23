from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

from app.services.supabase_client import get_supabase


bp = Blueprint("journey_planner", __name__)


ROUTE_CATEGORIES = [
    "visitor",
    "study",
    "work",
    "startup",
    "business",
    "family",
    "permanent_residence",
]

DOCUMENT_TYPES = [
    "birth_certificate",
    "marriage_certificate",
    "academic_certificate",
    "police_certificate",
    "bank_document",
    "employment_document",
    "business_document",
    "court_or_custody_document",
    "medical_document",
    "other",
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



def _store_run(tool_slug: str, payload: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    result["stored"] = False
    try:
        row = {
            "tool_slug": tool_slug,
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
        result["storage_note"] = "The plan was generated but could not be saved. Run the readiness storage SQL if persistence is required."
    return result



def _parse_child_ages(value: Any, children_count: int) -> List[int]:
    if isinstance(value, list):
        raw_items = value
    else:
        raw_items = _text(value, 300).replace(";", ",").split(",")

    ages: List[int] = []
    for item in raw_items:
        text = _text(item, 20)
        if not text:
            continue
        try:
            age = int(text)
        except ValueError:
            continue
        ages.append(min(max(age, 0), 30))

    while len(ages) < children_count:
        ages.append(0)
    return ages[:children_count]



def _timeline_rows(payload: Dict[str, Any], appointment_date: date, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    email = _text(payload.get("email"), 255) or None
    phone = _text(payload.get("phone"), 80) or None
    preferred_channel = _text(payload.get("preferred_channel"), 40) or "email"
    source_page = _text(payload.get("source_page"), 240) or "/journey-planner"

    rows: List[Dict[str, Any]] = []
    for task in tasks:
        due = task.get("due_date")
        if not isinstance(due, date):
            continue
        reminder = due - timedelta(days=1)
        rows.append(
            {
                "full_name": _text(payload.get("full_name"), 180) or None,
                "email": email,
                "phone": phone,
                "current_country": _text(payload.get("current_country"), 120) or None,
                "target_country": _text(payload.get("target_country"), 120) or None,
                "route_or_goal": _text(payload.get("application_type") or payload.get("route_or_goal"), 180) or None,
                "route_category": _text(payload.get("route_category"), 80) or None,
                "event_type": task.get("event_type") or "task",
                "event_title": _text(task.get("title"), 180),
                "event_notes": _text(task.get("notes"), 1200) or None,
                "due_date": due.isoformat(),
                "reminder_date": reminder.isoformat(),
                "priority": task.get("priority") or "medium",
                "preferred_channel": preferred_channel,
                "consent_to_contact": True,
                "source_page": source_page,
                "metadata": {
                    "generated_by": "journey_appointment_planner",
                    "appointment_date": appointment_date.isoformat(),
                },
            }
        )
    return rows


@bp.get("/options")
def journey_options():
    return jsonify(
        {
            "ok": True,
            "route_categories": ROUTE_CATEGORIES,
            "document_types": DOCUMENT_TYPES,
            "tools": [
                "legalization_check",
                "family_plan",
                "appointment_plan",
                "settlement_plan",
            ],
            "safety_note": "These tools organize readiness. They do not replace current destination-government, embassy, visa-centre, school, tax, registration, or professional instructions.",
        }
    )


@bp.post("/legalization-check")
def legalization_check():
    payload = request.get_json(silent=True) or {}
    issuing_country = _text(payload.get("issuing_country"), 120)
    receiving_country = _text(payload.get("receiving_country"), 120)
    document_type = _text(payload.get("document_type"), 120) or "other"
    days_until_submission = _int(payload.get("days_until_submission"), 30, 0, 3650)

    has_original = _bool(payload.get("has_original_document"))
    translation_needed = _bool(payload.get("translation_needed"))
    translation_completed = _bool(payload.get("translation_completed"))
    notarization_confirmed = _bool(payload.get("notarization_confirmed"))
    ministry_authentication_confirmed = _bool(payload.get("ministry_authentication_confirmed"))
    apostille_confirmed = _bool(payload.get("apostille_confirmed"))
    embassy_legalization_confirmed = _bool(payload.get("embassy_legalization_confirmed"))
    receiving_authority_checked = _bool(payload.get("receiving_authority_checked"))

    steps: List[Dict[str, str]] = []
    steps.append(
        {
            "step": "Confirm the receiving authority's exact rule",
            "status": "confirmed" if receiving_authority_checked else "required",
            "detail": "Check the destination government, embassy or consulate, university, employer, licensing body, or visa centre that will receive the document.",
        }
    )
    steps.append(
        {
            "step": "Prepare an accepted original or certified copy",
            "status": "ready" if has_original else "missing",
            "detail": "Do not send an irreplaceable original until the receiving authority and handling provider confirm the required format and custody process.",
        }
    )

    if translation_needed:
        steps.append(
            {
                "step": "Complete an accepted translation",
                "status": "ready" if translation_completed else "pending",
                "detail": "Confirm accepted language, translator qualification, certification wording, stamps, and whether the original and translation must be bound together.",
            }
        )

    if notarization_confirmed:
        steps.append(
            {
                "step": "Arrange notarization",
                "status": "confirmed_path",
                "detail": "Confirm whether the notary must certify the signature, copy, translation, affidavit, or another fact.",
            }
        )
    if ministry_authentication_confirmed:
        steps.append(
            {
                "step": "Complete issuing-authority or ministry authentication",
                "status": "confirmed_path",
                "detail": "Confirm the correct ministry or issuing authority and the order of authentication before paying a provider.",
            }
        )
    if apostille_confirmed:
        steps.append(
            {
                "step": "Obtain an apostille",
                "status": "confirmed_path",
                "detail": "Use an apostille only when the competent authority and receiving institution confirm that the apostille route applies to this document and country pair.",
            }
        )
    if embassy_legalization_confirmed:
        steps.append(
            {
                "step": "Complete embassy or consular legalization",
                "status": "confirmed_path",
                "detail": "Confirm prior authentication, appointment, payment, courier, and passport-handling rules directly with the relevant mission.",
            }
        )

    if not any([notarization_confirmed, ministry_authentication_confirmed, apostille_confirmed, embassy_legalization_confirmed]):
        steps.append(
            {
                "step": "Determine the authentication path",
                "status": "official_confirmation_required",
                "detail": "MoveReady will not infer apostille or embassy legalization solely from country names. Obtain the current written instruction from the receiving authority.",
            }
        )

    warnings: List[str] = []
    risk_score = 0
    if not receiving_authority_checked:
        warnings.append("The receiving authority has not yet been checked; this can lead to paying for the wrong authentication path.")
        risk_score += 35
    if not has_original:
        warnings.append("An accepted original or certified copy is not ready.")
        risk_score += 25
    if translation_needed and not translation_completed:
        warnings.append("Translation is required but not completed.")
        risk_score += 20
    if apostille_confirmed and embassy_legalization_confirmed:
        warnings.append("Both apostille and embassy legalization were selected. Confirm whether both are truly required and in what order.")
        risk_score += 15
    if days_until_submission <= 14:
        warnings.append("The submission deadline is close for a cross-border document process.")
        risk_score += 20

    risk_level = _risk_level(risk_score)
    result = {
        "ok": True,
        "issuing_country": issuing_country,
        "receiving_country": receiving_country,
        "document_type": document_type,
        "purpose": _text(payload.get("purpose"), 180),
        "days_until_submission": days_until_submission,
        "risk_level": risk_level,
        "readiness_status": _readiness_status(risk_level),
        "summary": "A document-handling path has been organized from the information supplied. The final path still requires written confirmation from the receiving authority.",
        "steps": steps,
        "warnings": warnings,
        "questions_to_confirm": [
            "Will the authority accept the original, a certified copy, or an electronically issued document?",
            "Is translation required, and who is qualified to translate or certify it?",
            "Is notarization needed before authentication?",
            "Does apostille recognition apply to this document and country pair?",
            "Is embassy or consular legalization required after local authentication?",
            "Are appointment, courier, payment, return-envelope, or document-validity rules involved?",
        ],
        "safety_note": "Do not post passports, certificates, or irreplaceable originals until custody, insurance, tracking, authority, and return arrangements are confirmed.",
    }
    return jsonify(_store_run("legalization_check", payload, result))


@bp.post("/family-plan")
def family_plan():
    payload = request.get_json(silent=True) or {}
    spouse_count = _int(payload.get("spouse_count"), 0, 0, 2)
    children_count = _int(payload.get("children_count"), 0, 0, 15)
    child_ages = _parse_child_ages(payload.get("child_ages"), children_count)
    other_dependants = _int(payload.get("other_dependants"), 0, 0, 10)
    travelling_together = _bool(payload.get("travelling_together"))
    custody_or_consent_issue = _bool(payload.get("custody_or_consent_issue"))
    special_medical_or_support_need = _bool(payload.get("special_medical_or_support_need"))
    accommodation_confirmed = _bool(payload.get("accommodation_confirmed"))
    family_insurance_confirmed = _bool(payload.get("family_insurance_confirmed"))

    school_age_children = [age for age in child_ages if 5 <= age <= 18]
    under_five_children = [age for age in child_ages if age < 5]
    adult_household = 1 + spouse_count + other_dependants
    household_size = adult_household + children_count

    planning_multiplier = round(1 + spouse_count * 0.35 + children_count * 0.25 + other_dependants * 0.30, 2)
    base_budget = _float(payload.get("base_budget_amount"), 0)
    adjusted_budget = round(base_budget * planning_multiplier, 2) if base_budget else None

    member_checklists: List[Dict[str, Any]] = [
        {
            "member": "Main applicant",
            "documents": ["passport", "route eligibility evidence", "funds evidence", "application forms", "insurance where required"],
        }
    ]
    for index in range(spouse_count):
        member_checklists.append(
            {
                "member": f"Spouse {index + 1}",
                "documents": ["passport", "marriage or partnership evidence", "civil-status records", "insurance", "route-specific dependant forms"],
            }
        )
    for index, age in enumerate(child_ages):
        documents = ["passport or accepted travel document", "birth certificate", "insurance", "route-specific dependant forms"]
        if age >= 5:
            documents.append("school or academic records")
        if custody_or_consent_issue:
            documents.extend(["custody evidence", "parental consent or court documents where required"])
        member_checklists.append({"member": f"Child {index + 1}", "age": age, "documents": documents})
    for index in range(other_dependants):
        member_checklists.append(
            {
                "member": f"Other dependant {index + 1}",
                "documents": ["passport", "dependency evidence", "relationship evidence", "financial-support evidence", "insurance"],
            }
        )

    tasks = [
        "Confirm whether family members apply together, later, or through a separate reunification route.",
        "Confirm official funds, income, accommodation, and insurance requirements for the full household.",
        "Check passport validity and name consistency for every family member.",
        "Prepare civil documents and confirm translation, notarization, apostille, or legalization requirements.",
        "Plan travel consent, custody, or court documentation where a child will travel with one parent or guardian.",
        "Prepare a first-90-days arrival budget separate from visa proof-of-funds evidence.",
    ]
    if school_age_children:
        tasks.append("Collect school records and check enrolment, language support, catchment, fees, transport, and start-date rules.")
    if under_five_children:
        tasks.append("Plan childcare, vaccination records, paediatric care, and age-appropriate travel arrangements.")
    if special_medical_or_support_need:
        tasks.append("Confirm medication carriage, prescriptions, medical records, accessibility, insurance coverage, and continuity of care before travel.")
    if not travelling_together:
        tasks.append("Create separate document, travel, consent, accommodation, and reunification timelines for family members travelling later.")

    warnings: List[str] = []
    risk_score = 0
    if custody_or_consent_issue:
        warnings.append("Custody or parental-consent evidence may require early legal and official-route review.")
        risk_score += 30
    if not accommodation_confirmed and household_size > 1:
        warnings.append("Family-appropriate accommodation is not yet confirmed.")
        risk_score += 20
    if not family_insurance_confirmed and household_size > 1:
        warnings.append("Family insurance requirements are not yet confirmed.")
        risk_score += 15
    if special_medical_or_support_need:
        warnings.append("Medical or support continuity needs an early destination-specific plan.")
        risk_score += 20
    if household_size >= 5:
        warnings.append("A larger household increases funds, accommodation, insurance, school, travel, and document complexity.")
        risk_score += 15

    risk_level = _risk_level(risk_score)
    result = {
        "ok": True,
        "target_country": _text(payload.get("target_country"), 120),
        "route_category": _text(payload.get("route_category"), 80) or "family",
        "household_size": household_size,
        "adult_household_members": adult_household,
        "children_count": children_count,
        "child_ages": child_ages,
        "school_age_children_count": len(school_age_children),
        "planning_budget_multiplier": planning_multiplier,
        "base_budget_amount": base_budget or None,
        "adjusted_planning_budget": adjusted_budget,
        "currency": _text(payload.get("currency"), 20) or "USD",
        "risk_level": risk_level,
        "readiness_status": _readiness_status(risk_level),
        "summary": "A household-level relocation checklist has been generated. The budget multiplier is a planning pressure estimate, not an official funds requirement.",
        "member_checklists": member_checklists,
        "tasks": tasks,
        "warnings": warnings,
        "safety_note": "Confirm official dependant eligibility, custody, consent, funds, accommodation, insurance, school, medical, and travel rules for the selected route and country.",
    }
    return jsonify(_store_run("family_plan", payload, result))


@bp.post("/appointment-plan")
def appointment_plan():
    payload = request.get_json(silent=True) or {}
    appointment_date = _date(payload.get("appointment_date"))
    if not appointment_date:
        return jsonify({"ok": False, "error": "valid_appointment_date_required"}), 400

    biometrics_required = _bool(payload.get("biometrics_required"))
    original_documents_required = _bool(payload.get("original_documents_required"))
    translation_pending = _bool(payload.get("translation_pending"))
    payment_pending = _bool(payload.get("payment_pending"))
    family_members = _int(payload.get("family_members_count"), 0, 0, 15)
    travel_time_hours = _float(payload.get("travel_time_hours"), 1, 0, 72)

    task_specs: List[Dict[str, Any]] = [
        {
            "title": "Confirm appointment instructions and location",
            "days_before": 21,
            "priority": "high",
            "event_type": "appointment",
            "notes": "Re-open the official appointment confirmation. Check address, entry time, prohibited items, applicant attendance, photos, copies, payment, and rescheduling rules.",
        },
        {
            "title": "Complete document pack review",
            "days_before": 14,
            "priority": "high",
            "event_type": "document",
            "notes": "Match every document against the current official checklist and arrange originals, copies, translations, forms, signatures, and supporting evidence.",
        },
        {
            "title": "Confirm payment and receipt requirements",
            "days_before": 7,
            "priority": "medium" if not payment_pending else "high",
            "event_type": "payment",
            "notes": "Confirm fee amount, payment channel, accepted card or cash, receipt, refund rules, and whether payment must be completed before arrival.",
        },
        {
            "title": "Plan travel to the appointment centre",
            "days_before": 3,
            "priority": "medium" if travel_time_hours <= 3 else "high",
            "event_type": "travel",
            "notes": "Plan transport, border or city travel time, accommodation if needed, weather, traffic, parking, and an arrival buffer.",
        },
        {
            "title": "Attend appointment",
            "days_before": 0,
            "priority": "critical",
            "event_type": "appointment",
            "notes": "Carry only permitted items and all required documents. Keep submission, biometric, payment, tracking, and collection evidence.",
        },
        {
            "title": "Check submission tracking and next action",
            "days_before": -2,
            "priority": "medium",
            "event_type": "follow_up",
            "notes": "Review tracking instructions, document requests, interview notices, passport collection, courier return, and decision communication channels.",
        },
    ]

    tasks: List[Dict[str, Any]] = []
    for item in task_specs:
        due = appointment_date - timedelta(days=int(item["days_before"]))
        tasks.append({**item, "due_date": due})

    checklist = [
        "Current passport and any previous passports required by the checklist",
        "Appointment confirmation and application or reference number",
        "Completed forms, declarations, signatures, and consent documents",
        "Official checklist plus correctly ordered originals and copies",
        "Payment proof and accepted payment method",
        "Return courier or collection instructions where applicable",
    ]
    if biometrics_required:
        checklist.append("Biometrics attendance requirements, clean fingertips, and any photo restrictions")
    if original_documents_required:
        checklist.append("Original documents plus secure return, custody, tracking, and copy arrangements")
    if family_members:
        checklist.append("Separate appointment, form, passport, consent, and document pack for each accompanying family member")

    warnings: List[str] = []
    risk_score = 0
    today = date.today()
    days_remaining = (appointment_date - today).days
    if days_remaining < 0:
        warnings.append("The entered appointment date is in the past.")
        risk_score += 70
    elif days_remaining <= 7:
        warnings.append("The appointment is within seven days; incomplete tasks require immediate attention.")
        risk_score += 35
    if translation_pending:
        warnings.append("Required translation is still pending.")
        risk_score += 25
    if payment_pending:
        warnings.append("Payment or fee confirmation is still pending.")
        risk_score += 15
    if travel_time_hours >= 5:
        warnings.append("Long travel time increases late-arrival and overnight-accommodation risk.")
        risk_score += 15

    stored_timeline_count = 0
    timeline_storage_note = "Timeline saving was not requested."
    save_to_timeline = _bool(payload.get("save_to_timeline"))
    email = _text(payload.get("email"), 255)
    phone = _text(payload.get("phone"), 80)
    consent_to_contact = _bool(payload.get("consent_to_contact"))

    if save_to_timeline:
        if not consent_to_contact:
            timeline_storage_note = "Timeline events were not saved because contact consent was not confirmed."
        elif not email and not phone:
            timeline_storage_note = "Timeline events were not saved because an email or phone number is required for lookup."
        else:
            try:
                rows = _timeline_rows(payload, appointment_date, tasks)
                response = get_supabase().table("relocation_timeline_events").insert(rows).execute()
                stored_timeline_count = len(response.data or [])
                timeline_storage_note = f"{stored_timeline_count} timeline events saved."
            except Exception:
                timeline_storage_note = "The appointment plan was generated, but timeline-event storage is unavailable."

    risk_level = _risk_level(risk_score)
    public_tasks = [
        {
            "title": item["title"],
            "due_date": item["due_date"].isoformat(),
            "priority": item["priority"],
            "event_type": item["event_type"],
            "notes": item["notes"],
        }
        for item in tasks
    ]
    result = {
        "ok": True,
        "appointment_date": appointment_date.isoformat(),
        "days_remaining": days_remaining,
        "application_type": _text(payload.get("application_type"), 180),
        "target_country": _text(payload.get("target_country"), 120),
        "risk_level": risk_level,
        "readiness_status": _readiness_status(risk_level),
        "summary": "A dated appointment-preparation plan has been generated from the appointment date and selected risks.",
        "tasks": public_tasks,
        "appointment_checklist": checklist,
        "warnings": warnings,
        "timeline_saved_count": stored_timeline_count,
        "timeline_storage_note": timeline_storage_note,
        "safety_note": "Always use the latest official embassy, visa-centre, application-provider, biometrics, submission, payment, and collection instructions.",
    }
    return jsonify(_store_run("appointment_plan", payload, result))


@bp.post("/settlement-plan")
def settlement_plan():
    payload = request.get_json(silent=True) or {}
    arrival_date = _date(payload.get("arrival_date"))
    household_size = max(1, _int(payload.get("household_size"), 1, 1, 30))
    temporary_accommodation = _bool(payload.get("temporary_accommodation_confirmed"))
    permanent_housing = _bool(payload.get("permanent_housing_confirmed"))
    insurance_active = _bool(payload.get("insurance_active"))
    school_needed = _bool(payload.get("school_needed"))
    employment_start = _bool(payload.get("employment_or_business_start_planned"))
    medical_need = _bool(payload.get("medical_or_accessibility_need"))
    pets = _int(payload.get("pets_count"), 0, 0, 10)

    timeline: Dict[str, List[Dict[str, str]]] = {
        "before_travel": [
            {"task": "Confirm entry documents and travel conditions", "priority": "critical"},
            {"task": "Keep arrival accommodation address and host or landlord contact", "priority": "critical"},
            {"task": "Prepare accessible money, cards, emergency funds, and payment alternatives", "priority": "high"},
            {"task": "Save insurance evidence, prescriptions, school, employment, and civil records", "priority": "high"},
        ],
        "first_72_hours": [
            {"task": "Reach verified accommodation and complete a safety check", "priority": "critical"},
            {"task": "Set up local phone or connectivity", "priority": "high"},
            {"task": "Confirm emergency numbers, local transport, food, and medicine access", "priority": "high"},
            {"task": "Review the first mandatory registration or reporting deadline", "priority": "critical"},
        ],
        "first_2_weeks": [
            {"task": "Complete residence, address, immigration, municipal, or local registration where required", "priority": "critical"},
            {"task": "Start bank, payment, tax-number, social-security, or identity setup where applicable", "priority": "high"},
            {"task": "Activate or confirm health coverage and primary-care access", "priority": "high"},
            {"task": "Secure stable transport and daily-living arrangements", "priority": "medium"},
        ],
        "first_90_days": [
            {"task": "Stabilize housing, employment, business, study, or family routine", "priority": "high"},
            {"task": "Track permit-card, renewal, tax, reporting, school, insurance, and address deadlines", "priority": "critical"},
            {"task": "Build an emergency contact, document-backup, and local support plan", "priority": "medium"},
            {"task": "Review actual spending against the relocation budget", "priority": "medium"},
        ],
    }

    if school_needed:
        timeline["before_travel"].append({"task": "Collect school records, vaccination evidence, translations, and enrolment documents", "priority": "high"})
        timeline["first_2_weeks"].append({"task": "Complete school or childcare enrolment and transport planning", "priority": "high"})
    if employment_start:
        timeline["before_travel"].append({"task": "Confirm work or business start conditions and required local registrations", "priority": "high"})
        timeline["first_2_weeks"].append({"task": "Complete employer, payroll, tax, social-security, or business onboarding", "priority": "high"})
    if medical_need:
        timeline["before_travel"].append({"task": "Prepare medical records, prescriptions, accessibility arrangements, and continuity-of-care contacts", "priority": "critical"})
    if pets:
        timeline["before_travel"].append({"task": "Confirm pet import, vaccination, microchip, carrier, airline, quarantine, and accommodation rules", "priority": "critical"})

    warnings: List[str] = []
    risk_score = 0
    if not temporary_accommodation:
        warnings.append("Temporary arrival accommodation is not confirmed.")
        risk_score += 35
    if not permanent_housing:
        warnings.append("Longer-term housing is not confirmed; avoid paying unverified landlords or agents.")
        risk_score += 15
    if not insurance_active:
        warnings.append("Health or route-required insurance is not confirmed as active for arrival.")
        risk_score += 25
    if household_size >= 5:
        warnings.append("A larger household increases housing, transport, registration, school, insurance, and emergency-budget pressure.")
        risk_score += 15
    if arrival_date and (arrival_date - date.today()).days <= 14:
        warnings.append("Arrival is close; unresolved accommodation, insurance, registration, or transport tasks need immediate attention.")
        risk_score += 20

    risk_level = _risk_level(risk_score)
    result = {
        "ok": True,
        "target_country": _text(payload.get("target_country"), 120),
        "target_city": _text(payload.get("target_city"), 120),
        "arrival_date": arrival_date.isoformat() if arrival_date else None,
        "household_size": household_size,
        "risk_level": risk_level,
        "readiness_status": _readiness_status(risk_level),
        "summary": "A staged arrival checklist has been generated. Country- and city-specific registration deadlines still require official confirmation.",
        "timeline": timeline,
        "warnings": warnings,
        "fraud_checks": [
            "Verify landlord, agent, provider, address, contract, deposit, and refund terms before payment.",
            "Do not surrender a passport to an unverified employer, landlord, driver, agent, or service provider.",
            "Use official government, municipal, school, tax, health, transport, and immigration sources for mandatory registrations.",
            "Keep encrypted document backups and emergency contacts separate from original documents.",
        ],
        "safety_note": "Settlement guidance varies by status, city, family, work, study, housing, tax, insurance, and registration rules. Confirm every mandatory deadline with the competent authority.",
    }
    return jsonify(_store_run("settlement_plan", payload, result))
