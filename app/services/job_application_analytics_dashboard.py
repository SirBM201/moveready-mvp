from __future__ import annotations

from typing import Any, Iterable, Mapping

from app.services.job_application_analytics import metrics
from app.services.job_application_pattern_intelligence import detect_patterns
from app.services.job_application_performance_intelligence import performance_overview
from app.services.job_search_feedback import build_feedback_profile

CONTRACT_VERSION = "b19.9.6-v1"


def build_dashboard(items: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows=list(items)
    summary=metrics(rows);performance=performance_overview(rows);patterns=detect_patterns(rows);feedback=build_feedback_profile(rows)
    return {
        "contract_version":CONTRACT_VERSION,
        "applications_analyzed":len(rows),
        "summary":{"funnel":summary["funnel"],"rates":summary["rates"],"terminal_outcomes":summary["terminal_outcomes"]},
        "observed_leaders":performance["observed_leaders"],
        "recommendations":patterns["recommendations"],
        "insufficient_evidence":patterns["insufficient_evidence"],
        "search_learning":{"applications_analyzed":feedback["applications_analyzed"],"policy":feedback["policy"],"active":bool(rows)},
        "safety":{"descriptive_analytics":True,"causal_employer_claims":False,"automatic_application_change":False,"ranking_adjustments_bounded":True,"eligibility_override_allowed":False,"evidence_override_allowed":False},
    }
