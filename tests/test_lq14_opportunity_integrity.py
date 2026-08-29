import json

from app.services.job_discovery import extract_vacancy_evidence, parse_source
from app.services.job_matching import application_viability, deadline_state, rank_jobs
from app.services.job_scope import ranked_job_is_alertable


PROFILE = {
    "current_country": "Kuwait",
    "primary_country": "Kuwait",
    "job_search_scope": "international",
    "international_target_countries": ["Canada"],
    "target_countries": ["Canada"],
    "target_roles": ["Production Supervisor"],
    "skills": ["troubleshooting", "team leadership"],
    "years_experience": 12,
}


def test_extracts_explicit_qualifications_barrier_and_contextual_deadline():
    evidence = extract_vacancy_evidence(
        "433A licensed Industrial Mechanic required. Preventive maintenance and "
        "troubleshooting experience required. Application deadline: 12:00 pm EST "
        "on Friday, September 4, 2099."
    )
    assert "433A Industrial Mechanic (Millwright) licence" in evidence["mandatory_barriers"]
    assert "preventive maintenance" in evidence["skills"]
    assert "troubleshooting" in evidence["skills"]
    assert evidence["expires_at"] == "2099-09-04T23:59:59+00:00"


def test_greenhouse_parser_preserves_auditable_evidence():
    body = json.dumps({"jobs": [{
        "title": "Millwright (433A Licensed)",
        "absolute_url": "https://job-boards.greenhouse.io/example/jobs/1",
        "location": {"name": "Toronto, Ontario, Canada"},
        "content": "433A licence required. Apply by: July 17, 2020. Troubleshooting experience required.",
    }]})
    job = parse_source(
        body,
        content_type="application/json",
        source_url="https://boards-api.greenhouse.io/v1/boards/example/jobs?content=true",
        adapter="greenhouse",
        keywords=["Millwright"],
    )["jobs"][0]
    assert job["expires_at"] == "2020-07-17T23:59:59+00:00"
    assert job["skills"] == ["troubleshooting"]
    assert job["mandatory_barriers"] == ["433A Industrial Mechanic (Millwright) licence"]


def test_passed_deadlines_are_not_ranked_or_alerted():
    expired = {"id": "old", "status": "open", "job_title": "Production Supervisor", "country": "Canada", "expires_at": "2020-01-01T23:59:59+00:00"}
    active = {"id": "new", "status": "open", "job_title": "Production Supervisor", "country": "Canada", "expires_at": "2099-01-01T23:59:59+00:00"}
    ranked = rank_jobs([expired, active], PROFILE)
    assert [item["id"] for item in ranked] == ["new"]
    score, priority, reasons = application_viability(expired, PROFILE, 90)
    assert (score, priority) == (0, "deadline_passed")
    assert "deadline has passed" in reasons[0]
    assert deadline_state(expired) == "passed"
    assert not ranked_job_is_alertable({"match_score": 90, "application_priority": priority}, 50)

