from __future__ import annotations

from collections import defaultdict
from flask import Blueprint, jsonify, request

from app.services.account_identity import get_verified_session_email
from app.services.job_application_portfolio import CONTRACT_VERSION, build_portfolio_item, sort_portfolio
from app.services.supabase_client import get_supabase

bp = Blueprint("job_application_portfolio", __name__)

JOB_TABLE = "relocation_jobs"
READINESS_TABLE = "relocation_job_application_readiness"
DRAFT_TABLE = "relocation_job_application_drafts"
HANDOFF_TABLE = "relocation_job_application_handoffs"
LIFECYCLE_TABLE = "relocation_job_application_lifecycles"
FOLLOWUP_TABLE = "relocation_job_application_followups"


def _account():
    email = get_verified_session_email()
    return (email, None) if email else (None, (jsonify({"ok": False, "error": "verified_session_required"}), 401))


def _owned_rows(table: str, email: str) -> list[dict]:
    return get_supabase().table(table).select("*").eq("email", email).execute().data or []


def _jobs(job_ids: set[str]) -> list[dict]:
    if not job_ids:
        return []
    # Job rows are discovered/public records; account ownership is enforced on
    # every application artifact before a job id reaches this query.
    return get_supabase().table(JOB_TABLE).select("*").in_("id", sorted(job_ids)).execute().data or []


def _group(rows: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        job_id = str(row.get("job_id") or "").strip()
        if job_id:
            grouped[job_id].append(row)
    return grouped


def _latest_readiness(rows: list[dict]) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for row in rows:
        job_id = str(row.get("job_id") or "").strip()
        if job_id:
            result[job_id] = row
    return result


@bp.get("/application-portfolio")
def application_portfolio():
    email, error = _account()
    if error:
        return error

    readiness_rows = _owned_rows(READINESS_TABLE, email)
    draft_rows = _owned_rows(DRAFT_TABLE, email)
    handoff_rows = _owned_rows(HANDOFF_TABLE, email)
    lifecycle_rows = _owned_rows(LIFECYCLE_TABLE, email)
    followup_rows = _owned_rows(FOLLOWUP_TABLE, email)

    readiness = _latest_readiness(readiness_rows)
    drafts = _group(draft_rows)
    handoffs = _group(handoff_rows)
    lifecycles = _group(lifecycle_rows)
    followups = _group(followup_rows)

    job_ids = set(readiness) | set(drafts) | set(handoffs) | set(lifecycles) | set(followups)
    job_map = {str(row.get("id")): row for row in _jobs(job_ids) if row.get("id")}

    items = []
    for job_id in job_ids:
        job = job_map.get(job_id) or {"id": job_id, "title": None, "company": None, "location": None}
        items.append(build_portfolio_item(
            job=job,
            readiness=readiness.get(job_id),
            drafts=drafts.get(job_id, []),
            handoffs=handoffs.get(job_id, []),
            lifecycles=lifecycles.get(job_id, []),
            followups=followups.get(job_id, []),
        ))

    items = sort_portfolio(items)
    state_filter = str(request.args.get("state") or "").strip().lower()
    if state_filter:
        items = [row for row in items if str(row.get("pipeline_state") or "").lower() == state_filter]
    actionable = str(request.args.get("actionable") or "").strip().lower()
    if actionable in {"1", "true", "yes"}:
        items = [row for row in items if row.get("next_action", {}).get("type") != "none"]

    return jsonify({
        "ok": True,
        "contract_version": CONTRACT_VERSION,
        "count": len(items),
        "items": items,
        "summary": {
            "terminal": sum(1 for row in items if row.get("terminal")),
            "actionable": sum(1 for row in items if row.get("next_action", {}).get("type") != "none"),
            "due_followups": sum(int(row.get("due_followup_count") or 0) for row in items),
        },
        "safety": {"read_model_only": True, "auto_submit_allowed": False, "auto_contact_employer": False},
    })


@bp.get("/application-portfolio/<job_id>")
def application_portfolio_item(job_id: str):
    email, error = _account()
    if error:
        return error

    readiness = get_supabase().table(READINESS_TABLE).select("*").eq("job_id", job_id).eq("email", email).maybe_single().execute().data
    drafts = get_supabase().table(DRAFT_TABLE).select("*").eq("job_id", job_id).eq("email", email).execute().data or []
    handoffs = get_supabase().table(HANDOFF_TABLE).select("*").eq("job_id", job_id).eq("email", email).execute().data or []
    lifecycles = get_supabase().table(LIFECYCLE_TABLE).select("*").eq("job_id", job_id).eq("email", email).execute().data or []
    followups = get_supabase().table(FOLLOWUP_TABLE).select("*").eq("job_id", job_id).eq("email", email).execute().data or []

    if not any([readiness, drafts, handoffs, lifecycles, followups]):
        return jsonify({"ok": False, "error": "application_portfolio_item_not_found"}), 404

    jobs = _jobs({job_id})
    job = jobs[0] if jobs else {"id": job_id, "title": None, "company": None, "location": None}
    item = build_portfolio_item(job=job, readiness=readiness, drafts=drafts, handoffs=handoffs, lifecycles=lifecycles, followups=followups)
    return jsonify({"ok": True, "contract_version": CONTRACT_VERSION, "item": item})
