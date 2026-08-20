from __future__ import annotations

from typing import Any, Dict, List, Mapping, MutableMapping, Tuple


ACTIONABLE_JOB_ALERT_TYPES = {"new_match", "job_changed", "job_reopened", "closing_soon"}
ACTIVE_JOB_STATUSES = {"open", "discovered"}
VISIBLE_ALERT_STATUSES = {"unread", "read"}


def _created_key(row: Mapping[str, Any]) -> Tuple[str, str]:
    return (str(row.get("created_at") or ""), str(row.get("id") or ""))


def reconcile_job_alert_payload(payload: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
    """Return only the live/actionable job-alert inbox and make its count agree.

    Migration 042 preserves historical rows by marking them dismissed.  This runtime
    guard keeps the API contract equally strict even when old rows remain in the
    table or a client refresh lands between reconciliation/deployment steps.

    Operational alerts such as scan_failed have no job_id and remain visible.
    Vacancy-bound alerts are visible only for an active canonical/current vacancy.
    For canonical vacancies, only the newest alert of each semantic type survives.
    """
    alerts = payload.get("alerts") or []
    jobs = payload.get("jobs") or []
    if not isinstance(alerts, list) or not isinstance(jobs, list):
        return payload

    jobs_by_id: Dict[str, Mapping[str, Any]] = {
        str(row.get("id")): row
        for row in jobs
        if isinstance(row, Mapping) and row.get("id")
    }

    candidates: List[Dict[str, Any]] = []
    for raw in alerts:
        if not isinstance(raw, dict):
            continue
        if str(raw.get("status") or "") not in VISIBLE_ALERT_STATUSES:
            continue

        job_id = str(raw.get("job_id") or "")
        if not job_id:
            # Operational/source-health alerts are not tied to vacancy lifecycle.
            candidates.append(raw)
            continue

        job = jobs_by_id.get(job_id)
        if not job or str(job.get("status") or "") not in ACTIVE_JOB_STATUSES:
            continue

        alert_type = str(raw.get("alert_type") or "")
        if alert_type == "job_closed":
            continue
        candidates.append(raw)

    # Newest first, matching the overview query.  Collapse historical duplicate
    # alerts that refer to the same canonical vacancy and semantic alert type.
    candidates.sort(key=_created_key, reverse=True)
    live: List[Dict[str, Any]] = []
    seen = set()
    for alert in candidates:
        job_id = str(alert.get("job_id") or "")
        if not job_id:
            live.append(alert)
            continue

        job = jobs_by_id.get(job_id) or {}
        canonical = str(job.get("canonical_identity") or "").strip()
        alert_type = str(alert.get("alert_type") or "")
        if canonical and alert_type in ACTIONABLE_JOB_ALERT_TYPES:
            key = (canonical, alert_type)
            if key in seen:
                continue
            seen.add(key)
        live.append(alert)

    payload["alerts"] = live
    counts = payload.get("counts")
    if not isinstance(counts, dict):
        counts = {}
        payload["counts"] = counts
    counts["unread_alerts"] = sum(1 for row in live if row.get("status") == "unread")
    return payload


def apply_job_alert_reconciliation(app: Any) -> None:
    """Wrap the registered automation overview without changing its public route."""
    endpoint = "job_automation.automation_overview"
    original = app.view_functions.get(endpoint)
    if original is None or getattr(original, "_moveready_alert_reconciled", False):
        return

    def reconciled_overview(*args: Any, **kwargs: Any):
        result = original(*args, **kwargs)

        # Flask views may return Response or (Response, status[/headers]).  Only
        # successful JSON overview responses are rewritten; errors pass through.
        response = result[0] if isinstance(result, tuple) else result
        status = result[1] if isinstance(result, tuple) and len(result) > 1 else getattr(response, "status_code", 200)
        if int(status or 200) >= 400 or not hasattr(response, "get_json"):
            return result

        payload = response.get_json(silent=True)
        if not isinstance(payload, dict) or not payload.get("ok"):
            return result

        from flask import jsonify

        rewritten = jsonify(reconcile_job_alert_payload(payload))
        rewritten.status_code = int(status or 200)
        if isinstance(result, tuple):
            if len(result) == 3:
                return rewritten, result[1], result[2]
            return rewritten, result[1]
        return rewritten

    reconciled_overview._moveready_alert_reconciled = True
    app.view_functions[endpoint] = reconciled_overview
