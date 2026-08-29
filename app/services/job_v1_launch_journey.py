from __future__ import annotations

from typing import Any, Iterable, Mapping

CONTRACT_VERSION = "lq19.1-v1"


def _list(value: Any) -> list[Any]:
    if isinstance(value, list): return value
    if isinstance(value, tuple): return list(value)
    if isinstance(value, str): return [part.strip() for part in value.split(",") if part.strip()]
    return []


def build_v1_launch_journey(*, profile: Mapping[str, Any] | None, vacancies: Iterable[Mapping[str, Any]], portfolio: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    profile = dict(profile or {}); jobs = list(vacancies); items = list(portfolio)
    setup_complete = bool(_list(profile.get("target_roles") or profile.get("target_job_titles"))) and bool(_list(profile.get("target_countries")))
    discovered = bool(jobs)
    qualified_items = [row for row in items if str(row.get("readiness_state") or "not_started") not in {"", "not_started", "discovered"}]
    execution_items = [row for row in items if str(row.get("pipeline_state") or "preparing") not in {"preparing"}]
    mobility_items = [row for row in items if str(row.get("pipeline_state") or "") in {"offer", "hired"}]
    stages = [
        {"key": "setup", "label": "Set target", "complete": setup_complete, "href": "/jobs/setup"},
        {"key": "find", "label": "Find", "complete": discovered, "href": "/jobs"},
        {"key": "qualify", "label": "Qualify", "complete": bool(qualified_items), "href": "/jobs"},
        {"key": "execute", "label": "Execute", "complete": bool(execution_items), "href": "/jobs/execution"},
        {"key": "move", "label": "Move", "complete": bool(mobility_items), "href": "/jobs/execution"},
    ]
    if not setup_complete:
        action = {"stage": "setup", "title": "Complete your matching target", "summary": "Record at least one target role and country.", "href": "/jobs/setup"}
    elif not discovered:
        action = {"stage": "find", "title": "Find an evidence-backed vacancy", "summary": "Discover or monitor an official employer vacancy.", "href": "/jobs"}
    elif not qualified_items:
        job = jobs[0]; job_id = job.get("id")
        action = {"stage": "qualify", "title": "Qualify the first vacancy", "summary": "Review source, country, sponsorship and readiness evidence.", "href": f"/jobs/vacancies/{job_id}"}
    elif items and any(row.get("next_action", {}).get("type") != "none" for row in items):
        active = next(row for row in items if row.get("next_action", {}).get("type") != "none")
        command = active.get("next_action") if isinstance(active.get("next_action"), Mapping) else {}
        stage = "move" if str(active.get("pipeline_state") or "") in {"offer", "hired"} else "execute"
        action = {"stage": stage, "title": command.get("title") or ("Open mobility handoff" if stage == "move" else "Continue controlled execution"), "summary": "Follow the next evidence-bound action for this vacancy.", "href": command.get("href") or f"/jobs/execution?jobId={active.get('job_id')}"}
    elif not items:
        action = {"stage": "qualify", "title": "Start vacancy readiness", "summary": "Choose a vacancy and run its readiness check.", "href": "/jobs"}
    else:
        action = {"stage": "execute", "title": "Review recorded outcomes", "summary": "All current application actions are complete; review outcomes before choosing another vacancy.", "href": "/jobs/intelligence"}
    complete = sum(1 for stage in stages if stage["complete"])
    return {
        "contract_version": CONTRACT_VERSION, "scope": "v1_launch_only", "stages": stages,
        "completed_stage_count": complete, "stage_count": len(stages), "progress_percent": round(complete * 100 / len(stages)),
        "next_action": action,
        "counts": {"vacancies": len(jobs), "qualified": len(qualified_items), "in_execution": len(execution_items), "mobility_handoffs": len(mobility_items)},
        "excluded_from_v1": ["payments", "marketplace", "automatic_submission", "real_notification_delivery", "settlement_expansion", "provider_network", "travel_booking"],
        "safety": {"progress_is_record_based": True, "eligibility_or_approval_inferred": False, "automatic_external_action": False},
    }
