from __future__ import annotations

from typing import Any, Dict, List, Mapping, MutableMapping, Tuple


ACTIONABLE_JOB_ALERT_TYPES = {"new_match", "job_changed", "job_reopened", "closing_soon"}
ACTIVE_JOB_STATUSES = {"open", "discovered"}
VISIBLE_ALERT_STATUSES = {"unread", "read"}
OPERATIONAL_ALERT_TYPES = {"scan_failed", "source_failed", "source_error"}
RECOVERED_WATCH_STATUSES = {"completed"}


def _created_key(row: Mapping[str, Any]) -> Tuple[str, str]:
    return (str(row.get("created_at") or ""), str(row.get("id") or ""))


def _operational_alert_is_live(alert: Mapping[str, Any], watches_by_id: Mapping[str, Mapping[str, Any]]) -> bool:
    """Return whether a source/scan failure still represents the watch's current state.

    A later successful scan supersedes the operational incident. Historical alert rows
    remain stored for audit/history, but they no longer occupy the live inbox.
    """
    watch_id = str(alert.get("watch_id") or "")
    if not watch_id:
        return True
    watch = watches_by_id.get(watch_id)
    if not watch:
        return True
    if str(watch.get("last_scan_status") or "") not in RECOVERED_WATCH_STATUSES:
        return True
    recovered_at = str(watch.get("last_scan_at") or "")
    failed_at = str(alert.get("created_at") or "")
    return not recovered_at or not failed_at or recovered_at <= failed_at


def reconcile_job_alert_payload(payload: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
    """Return the current alert inbox rather than an ever-growing event log.

    Historical rows remain stored. Vacancy alerts collapse to the newest actionable
    state per canonical vacancy. Operational failures collapse to the newest live
    incident per watch and disappear from the live inbox after a later successful scan.
    """
    alerts = payload.get("alerts") or []
    jobs = payload.get("jobs") or []
    watches = payload.get("watches") or []
    if not isinstance(alerts, list) or not isinstance(jobs, list):
        return payload

    jobs_by_id: Dict[str, Mapping[str, Any]] = {
        str(row.get("id")): row
        for row in jobs
        if isinstance(row, Mapping) and row.get("id")
    }
    watches_by_id: Dict[str, Mapping[str, Any]] = {
        str(row.get("id")): row
        for row in watches
        if isinstance(row, Mapping) and row.get("id")
    } if isinstance(watches, list) else {}

    candidates: List[Dict[str, Any]] = []
    for raw in alerts:
        if not isinstance(raw, dict):
            continue
        if str(raw.get("status") or "") not in VISIBLE_ALERT_STATUSES:
            continue

        alert_type = str(raw.get("alert_type") or "")
        if alert_type in OPERATIONAL_ALERT_TYPES and not _operational_alert_is_live(raw, watches_by_id):
            continue

        job_id = str(raw.get("job_id") or "")
        if not job_id:
            candidates.append(raw)
            continue

        job = jobs_by_id.get(job_id)
        if not job or str(job.get("status") or "") not in ACTIVE_JOB_STATUSES:
            continue
        if alert_type == "job_closed":
            continue
        candidates.append(raw)

    candidates.sort(key=_created_key, reverse=True)
    live: List[Dict[str, Any]] = []
    seen_actionable_vacancies = set()
    seen_operational_watches = set()

    for alert in candidates:
        alert_type = str(alert.get("alert_type") or "")
        if alert_type in OPERATIONAL_ALERT_TYPES:
            watch_id = str(alert.get("watch_id") or "")
            if watch_id:
                if watch_id in seen_operational_watches:
                    continue
                seen_operational_watches.add(watch_id)
            live.append(alert)
            continue

        job_id = str(alert.get("job_id") or "")
        if not job_id:
            live.append(alert)
            continue

        job = jobs_by_id.get(job_id) or {}
        canonical = str(job.get("canonical_identity") or "").strip()
        if alert_type in ACTIONABLE_JOB_ALERT_TYPES:
            vacancy_key = canonical or f"job:{job_id}"
            if vacancy_key in seen_actionable_vacancies:
                continue
            seen_actionable_vacancies.add(vacancy_key)
        live.append(alert)

    payload["alerts"] = live
    counts = payload.get("counts")
    if not isinstance(counts, dict):
        counts = {}
        payload["counts"] = counts

    unread = [row for row in live if row.get("status") == "unread"]
    unread_match_alerts = [
        row for row in unread
        if row.get("job_id") and str(row.get("alert_type") or "") in ACTIONABLE_JOB_ALERT_TYPES
    ]
    unread_scan_issues = [
        row for row in unread
        if str(row.get("alert_type") or "") in OPERATIONAL_ALERT_TYPES
    ]

    counts["unread_alerts"] = len(unread)
    counts["unread_match_alerts"] = len(unread_match_alerts)
    counts["unread_scan_issues"] = len(unread_scan_issues)
    counts["active_source_failures"] = len([
        row for row in live if str(row.get("alert_type") or "") in OPERATIONAL_ALERT_TYPES
    ])
    return payload


def apply_job_alert_reconciliation(app: Any) -> None:
    """Wrap the registered automation overview without changing its public route."""
    endpoint = "job_automation.automation_overview"
    original = app.view_functions.get(endpoint)
    if original is None or getattr(original, "_moveready_alert_reconciled", False):
        return

    def reconciled_overview(*args: Any, **kwargs: Any):
        result = original(*args, **kwargs)
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
