from __future__ import annotations

from typing import Any, Iterable, Mapping

from app.services.job_application_analytics import attribution_breakdown

CONTRACT_VERSION = "b19.9.3-v1"
SUPPORTED_DIMENSIONS = ("source", "country", "occupation", "employer")
MIN_SAMPLE_FOR_SIGNAL = 3


def _signal(row: Mapping[str, Any]) -> str:
    applications = int(row.get("applications") or 0)
    rates = row.get("rates") if isinstance(row.get("rates"), Mapping) else {}
    if applications < MIN_SAMPLE_FOR_SIGNAL:
        return "insufficient_sample"
    hire = float(rates.get("hire_per_submission") or 0)
    offer = float(rates.get("offer_per_submission") or 0)
    interview = float(rates.get("interview_per_submission") or 0)
    if hire > 0 or offer >= 0.25 or interview >= 0.5:
        return "strong_observed_performance"
    if interview > 0 or offer > 0:
        return "some_observed_progression"
    return "no_observed_progression_yet"


def dimension_intelligence(items: Iterable[Mapping[str, Any]], dimension: str) -> dict[str, Any]:
    if dimension not in SUPPORTED_DIMENSIONS:
        raise ValueError("unsupported_performance_dimension")
    breakdown = attribution_breakdown(list(items), dimension)
    rows = []
    for row in breakdown:
        enriched = dict(row)
        enriched["signal"] = _signal(row)
        enriched["sample_sufficient"] = int(row.get("applications") or 0) >= MIN_SAMPLE_FOR_SIGNAL
        enriched["interpretation"] = "observed_user_application_history_only"
        rows.append(enriched)
    rows.sort(key=lambda row: (
        0 if row["signal"] == "strong_observed_performance" else 1 if row["signal"] == "some_observed_progression" else 2 if row["signal"] == "no_observed_progression_yet" else 3,
        -float(row.get("rates", {}).get("interview_per_submission") or 0),
        -int(row.get("applications") or 0),
        str(row.get("value") or "").lower(),
    ))
    return {"contract_version": CONTRACT_VERSION, "dimension": dimension, "rows": rows, "minimum_sample_for_signal": MIN_SAMPLE_FOR_SIGNAL}


def performance_overview(items: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows = list(items)
    dimensions = {dimension: dimension_intelligence(rows, dimension) for dimension in SUPPORTED_DIMENSIONS}
    leaders = {}
    for dimension, result in dimensions.items():
        eligible = [row for row in result["rows"] if row["sample_sufficient"]]
        leaders[dimension] = eligible[0] if eligible else None
    return {
        "contract_version": CONTRACT_VERSION,
        "applications_analyzed": len(rows),
        "dimensions": dimensions,
        "observed_leaders": leaders,
        "safety": {
            "causal_claims_allowed": False,
            "employer_quality_claims_allowed": False,
            "discrimination_inference_allowed": False,
            "ranking_modified": False,
            "basis": "user_recorded_application_outcomes_only",
        },
    }
