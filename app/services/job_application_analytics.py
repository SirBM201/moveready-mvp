from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Mapping

CONTRACT_VERSION = "b19.9.1-v1"
FUNNEL_STAGES = ("tracked", "ready", "drafted", "submitted", "interview", "offer", "hired")
TERMINAL_STATES = frozenset({"hired", "rejected", "withdrawn"})
POSITIVE_STATES = frozenset({"interview", "offer", "hired"})


def _text(value: Any) -> str | None:
    value = str(value or "").strip()
    return value or None


def outcome_attribution(item: Mapping[str, Any]) -> dict[str, Any]:
    state = _text(item.get("pipeline_state")) or "preparing"
    job = item.get("job") if isinstance(item.get("job"), Mapping) else item
    return {
        "job_id": item.get("job_id") or job.get("id"),
        "pipeline_state": state,
        "terminal": state in TERMINAL_STATES,
        "positive_outcome": state in POSITIVE_STATES,
        "country": _text(job.get("country") or job.get("country_code") or job.get("location_country")),
        "occupation": _text(job.get("occupation") or job.get("occupation_title") or job.get("title")),
        "employer": _text(job.get("company") or job.get("company_name")),
        "source": _text(job.get("source") or job.get("source_name") or job.get("provider")),
        "source_url": _text(job.get("source_url") or job.get("url")),
        "evidence_basis": "recorded_application_and_vacancy_data_only",
        "employer_feedback_inferred": False,
    }


def funnel_flags(item: Mapping[str, Any]) -> dict[str, bool]:
    state = _text(item.get("pipeline_state")) or "preparing"
    readiness = _text(item.get("readiness_state")) or "not_started"
    return {
        "tracked": True,
        "ready": readiness in {"ready", "application_ready", "ready_to_apply"} or state not in {"preparing"},
        "drafted": bool(item.get("draft_id")) or state in {"draft_ready", "handoff_ready", "submitted", "under_review", "interview", "offer", "hired", "rejected", "withdrawn"},
        "submitted": state in {"submitted", "under_review", "interview", "offer", "hired", "rejected", "withdrawn"},
        "interview": state in {"interview", "offer", "hired"},
        "offer": state in {"offer", "hired"},
        "hired": state == "hired",
    }


def metrics(items: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows = list(items)
    flags = [funnel_flags(row) for row in rows]
    counts = {stage: sum(1 for flag in flags if flag[stage]) for stage in FUNNEL_STAGES}
    submitted = counts["submitted"]
    return {
        "contract_version": CONTRACT_VERSION,
        "applications_tracked": counts["tracked"],
        "funnel": counts,
        "rates": {
            "submission_rate": round(submitted / counts["tracked"], 4) if counts["tracked"] else 0.0,
            "interview_per_submission": round(counts["interview"] / submitted, 4) if submitted else 0.0,
            "offer_per_submission": round(counts["offer"] / submitted, 4) if submitted else 0.0,
            "hire_per_submission": round(counts["hired"] / submitted, 4) if submitted else 0.0,
        },
        "terminal_outcomes": dict(Counter((_text(row.get("pipeline_state")) or "preparing") for row in rows if (_text(row.get("pipeline_state")) or "") in TERMINAL_STATES)),
        "safety": {"descriptive_only": True, "employer_feedback_inferred": False, "auto_submit_allowed": False},
    }


def attribution_breakdown(items: Iterable[Mapping[str, Any]], dimension: str) -> list[dict[str, Any]]:
    if dimension not in {"country", "occupation", "employer", "source"}:
        raise ValueError("unsupported_attribution_dimension")
    buckets: dict[str, list[Mapping[str, Any]]] = {}
    for item in items:
        key = outcome_attribution(item).get(dimension) or "unknown"
        buckets.setdefault(str(key), []).append(item)
    result = []
    for key, rows in buckets.items():
        summary = metrics(rows)
        result.append({"dimension": dimension, "value": key, "applications": len(rows), "funnel": summary["funnel"], "rates": summary["rates"]})
    return sorted(result, key=lambda row: (-row["applications"], row["value"].lower()))
