from __future__ import annotations

from typing import Any, Dict, Optional

from app.services.job_visibility import job_is_visible_to_account
from app.services.supabase_client import get_supabase


def _first_row(query: Any) -> Optional[Dict[str, Any]]:
    """Execute a bounded PostgREST query without singular-response semantics."""
    response = query.limit(1).execute()
    rows = response.data or []
    return rows[0] if rows else None


def _safe_profile(email: str) -> Optional[Dict[str, Any]]:
    """Return the account job-search profile, treating zero rows as onboarding."""
    return _first_row(
        get_supabase()
        .table("relocation_job_search_profiles")
        .select("*")
        .eq("email", email)
    )


def _safe_owned_row(table: str, record_id: str, email: str) -> Optional[Dict[str, Any]]:
    """Return one account-owned row or None without PostgREST HTTP 406 behavior."""
    owner_column = "owner_email" if table in {"relocation_job_recruiters", "relocation_jobs"} else "email"
    return _first_row(
        get_supabase()
        .table(table)
        .select("*")
        .eq("id", record_id)
        .eq(owner_column, email)
    )


def _safe_visible_company(company_id: str, email: str) -> Optional[Dict[str, Any]]:
    """Return a curated or account-owned company when it is visible to the account."""
    row = _first_row(
        get_supabase()
        .table("relocation_job_companies")
        .select("*")
        .eq("id", company_id)
    )
    if not row:
        return None
    if row.get("is_curated") or str(row.get("owner_email") or "").casefold() == email.casefold():
        return row
    return None


def _safe_visible_job(job_id: str, email: str) -> Optional[Dict[str, Any]]:
    """Return a job only when the existing account-visibility contract permits it."""
    row = _first_row(
        get_supabase()
        .table("relocation_jobs")
        .select("*")
        .eq("id", job_id)
    )
    return row if job_is_visible_to_account(row, email) else None


def apply_job_automation_profile_patch(job_automation_module: Any) -> None:
    """Harden zero-row lookups used by Automation and the core Jobs workspace.

    Some Supabase/PostgREST client versions surface a zero-row ``maybe_single``
    request as HTTP 406 followed by a ``None`` response. A missing profile or
    record is normal application state, not a schema failure, so all affected
    Jobs lookups use bounded list queries instead.
    """
    job_automation_module._profile = _safe_profile

    # ``app.routes.jobs`` is already imported by create_app before this patch is
    # applied. Importing it here avoids another app-factory wiring change while
    # preserving the existing authorization and visibility contracts.
    from app.routes import jobs as jobs_module

    jobs_module._profile = _safe_profile
    jobs_module._owned_row = _safe_owned_row
    jobs_module._visible_company = _safe_visible_company
    jobs_module._visible_job = _safe_visible_job
