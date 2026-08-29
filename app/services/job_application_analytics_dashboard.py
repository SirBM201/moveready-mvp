from __future__ import annotations

from typing import Any, Iterable, Mapping

from app.services.job_application_analytics import metrics
from app.services.job_application_pattern_intelligence import detect_patterns
from app.services.job_application_performance_intelligence import performance_overview
from app.services.job_search_feedback import build_feedback_profile

CONTRACT_VERSION = "b19.9.6-v1"
OUTCOME_LEARNING_VERSION = "lq17.1-v1"
MINIMUM_LEARNING_SAMPLE = 3


def evidence_integrity(items: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows = list(items)
    confirmed_states = {"screening", "interview", "offer", "hired", "rejected", "withdrawn"}
    confirmed = sum(1 for row in rows if str(row.get("pipeline_state") or "").lower() in confirmed_states)
    unknown = sum(1 for row in rows if str(row.get("pipeline_state") or "").lower() in {"submitted", "under_review"})
    return {
        "applications_recorded": len(rows),
        "confirmed_outcomes": confirmed,
        "unknown_after_submission": unknown,
        "minimum_sample_for_pattern": MINIMUM_LEARNING_SAMPLE,
        "sample_sufficient": len(rows) >= MINIMUM_LEARNING_SAMPLE,
        "coverage_percent": round(confirmed * 100 / len(rows)) if rows else 0,
        "policy": "unknown_outcomes_remain_unknown",
    }


def build_dashboard(items: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows=list(items)
    summary=metrics(rows);performance=performance_overview(rows);patterns=detect_patterns(rows);feedback=build_feedback_profile(rows);integrity=evidence_integrity(rows)
    return {
        "contract_version":CONTRACT_VERSION,
        "outcome_learning_version":OUTCOME_LEARNING_VERSION,
        "applications_analyzed":len(rows),
        "summary":{"funnel":summary["funnel"],"rates":summary["rates"],"terminal_outcomes":summary["terminal_outcomes"]},
        "observed_leaders":performance["observed_leaders"],
        "recommendations":patterns["recommendations"],
        "insufficient_evidence":patterns["insufficient_evidence"],
        "search_learning":{"applications_analyzed":feedback["applications_analyzed"],"policy":feedback["policy"],"active":bool(rows)},
        "evidence_integrity":integrity,
        "next_learning_actions":[
            "Record confirmed employer responses and keep unknown outcomes unknown." if integrity["unknown_after_submission"] else "Keep application lifecycle evidence current.",
            "Build at least three recorded applications before interpreting patterns." if not integrity["sample_sufficient"] else "Compare observed patterns by source, country, occupation and employer.",
            "Use observed patterns to refine search effort, never to infer sponsorship or employer intent.",
        ],
        "safety":{"descriptive_analytics":True,"causal_employer_claims":False,"automatic_application_change":False,"ranking_adjustments_bounded":True,"eligibility_override_allowed":False,"evidence_override_allowed":False,"success_probability_generated":False,"sponsorship_inferred":False},
    }
