from __future__ import annotations

from typing import Any, Dict, Optional

from flask import jsonify

from app.services.job_scope import JOB_PROFILE_COLUMNS, profile_scope_contract
from app.services.job_visibility import job_is_visible_to_account
from app.services.supabase_client import get_supabase


def _first_row(query: Any) -> Optional[Dict[str, Any]]:
    response = query.limit(1).execute()
    rows = response.data or []
    return rows[0] if rows else None


def _safe_profile(email: str) -> Optional[Dict[str, Any]]:
    return _first_row(
        get_supabase().table("relocation_job_search_profiles").select(JOB_PROFILE_COLUMNS).eq("email", email)
    )


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


def _automation_overview_with_search_contract(original_view: Any):
    def wrapped(*args: Any, **kwargs: Any):
        response = original_view(*args, **kwargs)
        if isinstance(response, tuple):
            return response
        try:
            payload = response.get_json(silent=True)
        except Exception:
            return response
        if not isinstance(payload, dict) or not payload.get("ok"):
            return response
        profile = payload.get("profile")
        payload["search_contract"] = profile_scope_contract(profile)
        watches = payload.get("watches") if isinstance(payload.get("watches"), list) else []
        health_counts = {"healthy": 0, "degraded": 0, "persistent_failure": 0, "checking": 0, "paused": 0, "unknown": 0}
        for watch in watches:
            state = str(watch.get("source_health") or "unknown")
            health_counts[state] = health_counts.get(state, 0) + 1
        payload.setdefault("counts", {}).update({
            "healthy_sources": health_counts.get("healthy", 0),
            "degraded_sources": health_counts.get("degraded", 0),
            "persistent_failure_sources": health_counts.get("persistent_failure", 0),
            "checking_sources": health_counts.get("checking", 0),
        })
        payload["source_health_summary"] = health_counts
        return jsonify(payload)

    wrapped.__name__ = getattr(original_view, "__name__", "automation_overview")
    wrapped.__doc__ = getattr(original_view, "__doc__", None)
    return wrapped


def apply_job_automation_profile_patch(job_automation_module: Any) -> None:
    """Harden Jobs lookups, search scope, and source reliability state."""
    job_automation_module._profile = _safe_profile

    from app.services.job_scan_lifecycle import install as install_scan_lifecycle
    from app.services.job_scan_backoff import install as install_scan_backoff
    from app.services.job_source_health import install as install_source_health
    install_scan_lifecycle(job_automation_module)
    install_scan_backoff(job_automation_module)
    install_source_health(job_automation_module)

    from app.routes import jobs as jobs_module
    from app.routes.job_search_scope import update_search_scope
    jobs_module._profile = _safe_profile
    jobs_module._owned_row = _safe_owned_row
    jobs_module._visible_company = _safe_visible_company
    jobs_module._visible_job = _safe_visible_job

    user_bp = getattr(job_automation_module, "user_bp", None)
    if user_bp is None:
        return
    overview_endpoint = "automation_overview"
    if not getattr(user_bp, "_got_registered_once", False):
        original_overview = getattr(user_bp, "view_functions", {}).get(overview_endpoint)
        if original_overview and not getattr(original_overview, "_moveready_scope_contract_patch", False):
            wrapped_overview = _automation_overview_with_search_contract(original_overview)
            setattr(wrapped_overview, "_moveready_scope_contract_patch", True)
            user_bp.view_functions[overview_endpoint] = wrapped_overview

    endpoint = "update_search_scope"
    if getattr(user_bp, "_got_registered_once", False) or endpoint in getattr(user_bp, "view_functions", {}):
        return
    user_bp.add_url_rule("/profile/search-scope", endpoint=endpoint, view_func=update_search_scope, methods=["PATCH"])
