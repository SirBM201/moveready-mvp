from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List

from flask import jsonify, request

from app.routes import journey_planner
from app.services.supabase_client import get_supabase


def _timeline_due_date(stage: str, arrival_date: date) -> date:
    offsets = {
        "before_travel": -7,
        "first_72_hours": 1,
        "first_2_weeks": 7,
        "first_90_days": 45,
    }
    return arrival_date + timedelta(days=offsets.get(stage, 0))


def _timeline_rows(payload: Dict[str, Any], arrival_date: date, timeline: Dict[str, List[Dict[str, str]]]) -> List[Dict[str, Any]]:
    email = journey_planner._text(payload.get("email"), 255) or None
    phone = journey_planner._text(payload.get("phone"), 80) or None
    preferred_channel = journey_planner._text(payload.get("preferred_channel"), 40) or "email"
    source_page = journey_planner._text(payload.get("source_page"), 240) or "/journey-planner"
    full_name = journey_planner._text(payload.get("full_name"), 180) or None
    current_country = journey_planner._text(payload.get("current_country"), 120) or None
    target_country = journey_planner._text(payload.get("target_country"), 120) or None

    rows: List[Dict[str, Any]] = []
    for stage, tasks in timeline.items():
        due = _timeline_due_date(stage, arrival_date)
        reminder = due - timedelta(days=1)
        for task in tasks:
            title = journey_planner._text(task.get("task"), 180)
            if not title:
                continue
            rows.append(
                {
                    "full_name": full_name,
                    "email": email,
                    "phone": phone,
                    "current_country": current_country,
                    "target_country": target_country,
                    "route_or_goal": "post-arrival settlement",
                    "route_category": journey_planner._text(payload.get("route_category"), 80) or "settlement",
                    "event_type": "settlement_task",
                    "event_title": title,
                    "event_notes": f"Settlement stage: {stage.replace('_', ' ')}. Confirm the exact local authority, registration deadline, evidence, fee, and appointment rule before acting.",
                    "due_date": due.isoformat(),
                    "reminder_date": reminder.isoformat(),
                    "priority": task.get("priority") or "medium",
                    "preferred_channel": preferred_channel,
                    "consent_to_contact": True,
                    "source_page": source_page,
                    "metadata": {
                        "generated_by": "journey_settlement_planner",
                        "arrival_date": arrival_date.isoformat(),
                        "settlement_stage": stage,
                        "official_confirmation_required": True,
                    },
                }
            )
    return rows


def settlement_plan_with_timeline():
    payload = request.get_json(silent=True) or {}
    arrival_date = journey_planner._date(payload.get("arrival_date"))
    household_size = max(1, journey_planner._int(payload.get("household_size"), 1, 1, 30))
    temporary_accommodation = journey_planner._bool(payload.get("temporary_accommodation_confirmed"))
    permanent_housing = journey_planner._bool(payload.get("permanent_housing_confirmed"))
    insurance_active = journey_planner._bool(payload.get("insurance_active"))
    school_needed = journey_planner._bool(payload.get("school_needed"))
    employment_start = journey_planner._bool(payload.get("employment_or_business_start_planned"))
    medical_need = journey_planner._bool(payload.get("medical_or_accessibility_need"))
    pets = journey_planner._int(payload.get("pets_count"), 0, 0, 10)

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
    if not arrival_date:
        warnings.append("Arrival date is not recorded, so dated settlement tasks cannot be generated or saved.")
        risk_score += 20
    elif (arrival_date - date.today()).days < 0:
        warnings.append("The entered arrival date is in the past. Review all registration and reporting deadlines immediately.")
        risk_score += 35
    elif (arrival_date - date.today()).days <= 14:
        warnings.append("Arrival is close; unresolved accommodation, insurance, registration, or transport tasks need immediate attention.")
        risk_score += 20

    save_to_timeline = journey_planner._bool(payload.get("save_to_timeline"))
    consent_to_contact = journey_planner._bool(payload.get("consent_to_contact"))
    email = journey_planner._text(payload.get("email"), 255)
    phone = journey_planner._text(payload.get("phone"), 80)
    stored_timeline_count = 0
    timeline_storage_note = "Timeline saving was not requested."

    if save_to_timeline:
        if not arrival_date:
            timeline_storage_note = "Timeline events were not saved because an arrival date is required."
        elif not consent_to_contact:
            timeline_storage_note = "Timeline events were not saved because contact and storage consent was not confirmed."
        elif not email and not phone:
            timeline_storage_note = "Timeline events were not saved because an email or phone number is required for private lookup."
        else:
            try:
                rows = _timeline_rows(payload, arrival_date, timeline)
                response = get_supabase().table("relocation_timeline_events").insert(rows).execute()
                stored_timeline_count = len(response.data or [])
                timeline_storage_note = f"{stored_timeline_count} settlement timeline events saved."
            except Exception:
                timeline_storage_note = "The settlement plan was generated, but timeline-event storage is unavailable."

    risk_level = journey_planner._risk_level(risk_score)
    result: Dict[str, Any] = {
        "ok": True,
        "target_country": journey_planner._text(payload.get("target_country"), 120),
        "target_city": journey_planner._text(payload.get("target_city"), 120),
        "arrival_date": arrival_date.isoformat() if arrival_date else None,
        "household_size": household_size,
        "risk_level": risk_level,
        "readiness_status": journey_planner._readiness_status(risk_level),
        "summary": "A staged arrival checklist has been generated. Country- and city-specific registration deadlines still require official confirmation.",
        "timeline": timeline,
        "warnings": warnings,
        "timeline_saved_count": stored_timeline_count,
        "timeline_storage_note": timeline_storage_note,
        "fraud_checks": [
            "Verify landlord, agent, provider, address, contract, deposit, and refund terms before payment.",
            "Do not surrender a passport to an unverified employer, landlord, driver, agent, or service provider.",
            "Use official government, municipal, school, tax, health, transport, and immigration sources for mandatory registrations.",
            "Keep encrypted document backups and emergency contacts separate from original documents.",
        ],
        "safety_note": "Settlement guidance varies by status, city, family, work, study, housing, tax, insurance, and registration rules. Confirm every mandatory deadline with the competent authority.",
    }
    return jsonify(journey_planner._store_run("settlement_plan", payload, result))
