from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.services.job_application_portfolio import build_portfolio_item, sort_portfolio
from app.services.supabase_client import get_supabase

JOB_TABLE="relocation_jobs";READINESS_TABLE="relocation_job_application_readiness";DRAFT_TABLE="relocation_job_application_drafts";HANDOFF_TABLE="relocation_job_application_handoffs";LIFECYCLE_TABLE="relocation_job_application_lifecycles";FOLLOWUP_TABLE="relocation_job_application_followups"


def _rows(table: str, email: str) -> list[dict[str, Any]]:
    return get_supabase().table(table).select("*").eq("email",email).execute().data or []


def _group(rows):
    result=defaultdict(list)
    for row in rows:
        job_id=str(row.get("job_id") or "").strip()
        if job_id: result[job_id].append(row)
    return result


def load_account_portfolio(email: str) -> list[dict[str, Any]]:
    readiness_rows=_rows(READINESS_TABLE,email);drafts=_group(_rows(DRAFT_TABLE,email));handoffs=_group(_rows(HANDOFF_TABLE,email));lifecycles=_group(_rows(LIFECYCLE_TABLE,email));followups=_group(_rows(FOLLOWUP_TABLE,email))
    readiness={str(row.get("job_id")):row for row in readiness_rows if row.get("job_id")}
    ids=set(readiness)|set(drafts)|set(handoffs)|set(lifecycles)|set(followups)
    jobs=[] if not ids else (get_supabase().table(JOB_TABLE).select("*").in_("id",sorted(ids)).execute().data or [])
    job_map={str(row.get("id")):row for row in jobs if row.get("id")}
    return sort_portfolio([build_portfolio_item(job=job_map.get(job_id) or {"id":job_id},readiness=readiness.get(job_id),drafts=drafts.get(job_id,[]),handoffs=handoffs.get(job_id,[]),lifecycles=lifecycles.get(job_id,[]),followups=followups.get(job_id,[])) for job_id in ids])
