from app.services.job_application_readiness import evaluate_application_readiness, vacancy_fingerprint


def vacancy(**overrides):
    row = {
        "status": "open",
        "source_status": "verified",
        "relocation_support_status": "confirmed",
        "source_url": "https://example.com/jobs/1",
        "description_summary": "Production role with documented requirements.",
        "expires_at": "2099-01-01T23:59:59+00:00",
    }
    row.update(overrides)
    return row


def test_returns_explainable_prioritized_gap_plan():
    result = evaluate_application_readiness(
        vacancy(requirements_verified=False),
        profile={},
        materials={},
    )
    assert result["readiness_engine_version"] == "lq15.1-v1"
    assert result["score"] < 100
    assert result["evidence_coverage"] > 0
    assert result["gaps"]
    assert result["next_actions"][0]["priority"] == 1
    assert result["unknown_is_not_ready"] is True
    assert result["gap_summary"]["materials"] >= 1


def test_unverified_mandatory_barrier_blocks_application_readiness():
    result = evaluate_application_readiness(
        vacancy(metadata={"mandatory_barriers": ["433A Industrial Mechanic licence"]}),
        profile={"work_authorization": "authorized"},
        materials={"cv_ready": True},
    )
    gap = next(item for item in result["gaps"] if item["code"] == "mandatory_requirement_missing")
    assert gap["blocking"] is True
    assert gap["category"] == "qualification"
    assert gap["action"] == "verify_requirements"
    assert result["state"] == "blocked"


def test_readiness_fingerprint_changes_when_qualification_evidence_changes():
    before = vacancy(metadata={"mandatory_barriers": []})
    after = vacancy(metadata={"mandatory_barriers": ["433A licence"]})
    assert vacancy_fingerprint(before) != vacancy_fingerprint(after)


def test_clean_evidence_reaches_human_review_boundary_without_claiming_eligibility():
    result = evaluate_application_readiness(
        vacancy(requirements_verified=True),
        profile={"work_authorization": "authorized"},
        materials={"cv_ready": True},
    )
    assert result["state"] == "ready_for_review"
    assert result["score"] == 100
    assert result["safety"]["eligibility_is_not_guaranteed"] is True

