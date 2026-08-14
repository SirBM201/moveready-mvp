from __future__ import annotations

from typing import Any, Dict, Optional

from app.services.job_visibility import job_is_visible_to_account
from app.services.supabase_client import get_supabase


def _first_row(query: Any) -> Optional[Dict[str, Any]]:
    response = query.limit(1).execute()
    rows = response.data or []
    return rows[0] if rows else None


def _safe_profile(email: str) -> Optional[Dict[str, Any]]:
    return _first_row(get_supabase().table("relocation_job_search_profiles").select("*").eq("email", email))


def _safe_owned_row(table: str, record_id: str, email: str) -> Optional[Dict[str, Any]]:
    owner_column = "owner_email" if table in {"relocation_job_recruiters", "relocation_jobs"} else "email"
    return _first_row(get_supabase().table(table).select("*").eq("id", record_id).eq(owner_column, email))


def _safe_visible_company(company_id: str, email: str) -> Optional[Dict[str, Any]]:
    row = _first_row(get_supabase().table("relocation_job_companies").select("*").eq("id", company_id))
    if not row:
        return None
    if row.get("is_curated") or str(row.get("owner_email") or "").casefold() == email.casefold():
        return row
    return None


def _safe_visible_job(job_id: str, email: str) -> Optional[Dict[str, Any]]:
    row = _first_row(get_supabase().table("relocation_jobs").select("*").eq("id", job_id))
    return row if job_is_visible_to_account(row, email) else None


def apply_job_automation_profile_patch(job_automation_module: Any) -> None:
    """Harden zero-row Jobs lookups and attach additive career-scope endpoints."""
    job_automation_module._profile = _safe_profile

    from app.routes import jobs as jobs_module
    from app.routes.job_search_scope import update_search_scope

    jobs_module._profile = _safe_profile
    jobs_module._owned_row = _safe_owned_row
    jobs_module._visible_company = _safe_visible_company
    jobs_module._visible_job = _safe_visible_job

    # create_app invokes this patch once before registering user_bp.
    job_automation_module.user_bp.add_url_rule(
        "/profile/search-scope",
        endpoint="update_search_scope",
        view_func=update_search_scope,
        methods=["PATCH"],
    )
