from __future__ import annotations

from typing import Any, Dict, Optional

from app.services.supabase_client import get_supabase


def _safe_profile(email: str) -> Optional[Dict[str, Any]]:
    """Return the account job-search profile without PostgREST singular semantics.

    PostgREST returns HTTP 406 for a singular request when no row exists (and
    some client versions surface that as a None response). Automation overview
    must treat a missing profile as normal onboarding state rather than as a
    missing-schema failure.
    """
    response = (
        get_supabase()
        .table("relocation_job_search_profiles")
        .select("*")
        .eq("email", email)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    return rows[0] if rows else None


def apply_job_automation_profile_patch(job_automation_module: Any) -> None:
    job_automation_module._profile = _safe_profile
