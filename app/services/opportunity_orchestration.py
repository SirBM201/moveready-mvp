from __future__ import annotations

from typing import Any, Dict, List, Optional


def _score(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return max(0, min(100, int(round(float(value)))))
    except (TypeError, ValueError):
        return None


def _dimension(label: str, value: Any) -> Dict[str, Any]:
    score = _score(value)
    return {"label": label, "score": score, "status": "needs_assessment" if score is None else "assessed"}


def next_best_action(signals: Dict[str, Any]) -> Dict[str, str]:
    if signals.get("hard_blocker"):
        return {"type": "resolve_blocker", "label": str(signals["hard_blocker"]), "workspace": str(signals.get("blocker_workspace") or "/route-checker")}
    if signals.get("deadline_action"):
        return {"type": "deadline", "label": str(signals["deadline_action"]), "workspace": str(signals.get("deadline_workspace") or "/timeline")}
    if signals.get("missing_document"):
        return {"type": "document", "label": f"Prepare {signals['missing_document']}", "workspace": "/evidence-pack"}
    financial = _score(signals.get("financial_readiness"))
    if financial is not None and financial < 100 and signals.get("known_funds_requirement"):
        return {"type": "financial", "label": "Close your funding gap", "workspace": "/readiness-tools"}
    language = _score(signals.get("language_readiness"))
    if language is not None and language < int(signals.get("language_target_threshold") or 80):
        return {"type": "language", "label": "Improve your language readiness", "workspace": "/language-coach"}
    if signals.get("career_action"):
        return {"type": "career", "label": str(signals["career_action"]), "workspace": str(signals.get("career_workspace") or "/jobs")}
    return {"type": "continue", "label": "Review requirements and continue", "workspace": "/my-journey"}


def build_opportunity_view(opportunity: Dict[str, Any], signals: Dict[str, Any] | None = None) -> Dict[str, Any]:
    signals = signals or {}
    dimensions: List[Dict[str, Any]] = [
        _dimension("Opportunity Fit", signals.get("opportunity_fit")),
        _dimension("Eligibility / Readiness", signals.get("eligibility_readiness")),
    ]
    if signals.get("is_job"):
        dimensions.extend([
            _dimension("Career Match", signals.get("career_match")),
            _dimension("Application Viability", signals.get("application_viability")),
        ])
    if signals.get("financial_readiness") is not None or signals.get("known_funds_requirement"):
        dimensions.append(_dimension("Financial Readiness", signals.get("financial_readiness")))
    return {
        "opportunity": opportunity,
        "dimensions": dimensions,
        "top_blocker": signals.get("hard_blocker") or signals.get("top_blocker"),
        "next_best_action": next_best_action(signals),
        "why_recommended": signals.get("why_recommended") or opportunity.get("summary"),
        "provenance": {
            "official_url": opportunity.get("official_url"),
            "source_confidence": opportunity.get("source_confidence"),
            "last_verified_at": opportunity.get("last_verified_at"),
            "next_review_due_at": opportunity.get("next_review_due_at"),
        },
        "advisory": "Scores are decision-support indicators, not guarantees of visa approval, admission, employment or entry.",
    }
