from __future__ import annotations

from typing import Any, Iterable, Mapping

from app.services.job_recruiter_followups import follow_up_status
from app.services.job_recruiter_intelligence import recruiter_identity, relationship_state

CONTRACT_VERSION = "b19.12.4-v1"


def build_recruiter_dashboard(*, recruiter: Mapping[str, Any], events: Iterable[Mapping[str, Any]] = (), vacancies: Iterable[Mapping[str, Any]] = (), applications: Iterable[Mapping[str, Any]] = ()) -> dict[str, Any]:
    event_rows = list(events)
    vacancy_rows = list(vacancies)
    application_rows = list(applications)
    return {
        "contract_version": CONTRACT_VERSION,
        "recruiter": recruiter_identity(recruiter),
        "relationship": relationship_state(recruiter),
        "follow_up": follow_up_status(recruiter, event_rows),
        "timeline": sorted(event_rows, key=lambda row: str(row.get("occurred_at") or ""), reverse=True),
        "relationships": {
            "vacancies": vacancy_rows,
            "applications": application_rows,
            "vacancy_count": len(vacancy_rows),
            "application_count": len(application_rows),
        },
        "safety": {
            "dashboard_is_private_and_descriptive": True,
            "recruiter_identity_not_verified": True,
            "employment_relationship_not_inferred": True,
            "sponsorship_not_inferred": True,
            "employer_interest_not_inferred": True,
            "automatic_contact": False,
        },
    }
