from __future__ import annotations

from typing import Any, Mapping
from urllib.parse import quote

CONTRACT_VERSION = "lq18.1-v1"
OFFER_STATES = {"offer", "hired"}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _countries(profile: Mapping[str, Any]) -> set[str]:
    values = profile.get("work_authorized_countries") or []
    if isinstance(values, str): values = [part.strip() for part in values.split(",")]
    return {_text(value).lower() for value in values if _text(value)}


def build_offer_mobility_handoff(*, job: Mapping[str, Any], lifecycle: Mapping[str, Any] | None, profile: Mapping[str, Any] | None = None) -> dict[str, Any]:
    lifecycle = dict(lifecycle or {}); profile = dict(profile or {})
    state = _text(lifecycle.get("state")).lower()
    evidence = lifecycle.get("latest_evidence") if isinstance(lifecycle.get("latest_evidence"), Mapping) else {}
    destination = _text(job.get("country") or job.get("location_country") or job.get("destination_country"))
    sponsorship = _text(job.get("visa_sponsorship_status") or job.get("sponsorship_status")).lower()
    relocation = _text(job.get("relocation_support_status")).lower()
    authorized = destination.lower() in _countries(profile) if destination else False
    offer_confirmed = state in OFFER_STATES and bool(evidence)
    gaps: list[dict[str, Any]] = []

    def gap(code: str, message: str, action: str, href: str, *, blocking: bool = True) -> None:
        gaps.append({"code": code, "message": message, "action": action, "href": href, "blocking": blocking})

    if state not in OFFER_STATES:
        gap("confirmed_offer_required", "A user-recorded offer or hire state with employer evidence is required before mobility planning starts.", "record_offer_evidence", f"/jobs/execution?jobId={job.get('id')}")
    elif not evidence:
        gap("offer_evidence_required", "Record employer evidence for the offer before relying on it.", "record_offer_evidence", f"/jobs/execution?jobId={job.get('id')}")
    if not destination:
        gap("destination_country_required", "Confirm the employment destination country.", "confirm_destination", f"/jobs/vacancies/{job.get('id')}")
    if destination and not authorized and sponsorship not in {"confirmed", "available", "sponsored", "yes"}:
        gap("work_route_unconfirmed", "Work authorization or employer sponsorship for the destination is not confirmed.", "verify_work_route", f"/route-checker?country={quote(destination)}")
    if sponsorship not in {"confirmed", "available", "sponsored", "yes"}:
        gap("sponsorship_terms_unconfirmed", "Employer sponsorship terms are not confirmed in the vacancy evidence.", "verify_sponsorship_terms", f"/jobs/vacancies/{job.get('id')}", blocking=not authorized)
    if relocation not in {"confirmed", "available", "provided", "yes"}:
        gap("relocation_support_unconfirmed", "Relocation support and covered costs are not confirmed.", "verify_relocation_support", f"/jobs/vacancies/{job.get('id')}", blocking=False)
    if not any(evidence.get(key) for key in ("start_date", "expected_start_date", "joining_date")):
        gap("start_date_unconfirmed", "The employment start date is not recorded in the offer evidence.", "record_start_date", f"/jobs/execution?jobId={job.get('id')}", blocking=False)

    blocking = sum(1 for row in gaps if row["blocking"])
    return {
        "contract_version": CONTRACT_VERSION,
        "job_id": job.get("id"), "job_title": job.get("job_title") or job.get("title"),
        "company_name": job.get("company_name") or job.get("company"), "destination_country": destination or None,
        "lifecycle_state": state or "not_started", "offer_evidence_recorded": bool(evidence),
        "work_authorized": authorized, "sponsorship_status": sponsorship or "unknown", "relocation_support_status": relocation or "unknown",
        "available": state in OFFER_STATES, "ready_for_mobility_planning": state in OFFER_STATES and blocking == 0,
        "blocking_gap_count": blocking, "gaps": gaps,
        "next_actions": gaps[:5] if gaps else [{"code": "build_mobility_plan", "message": "Build the evidence-backed mobility plan.", "action": "build_mobility_plan", "href": "/journey-planner", "blocking": False}],
        "planning_links": {"route": f"/route-checker?country={quote(destination)}" if destination else "/route-checker", "evidence": "/evidence-pack", "finances": "/readiness", "journey": "/journey-planner"},
        "safety": {"offer_is_not_immigration_approval": True, "eligibility_inferred": False, "sponsorship_inferred": False, "authority_application_submitted": False, "travel_booking_performed": False},
    }
