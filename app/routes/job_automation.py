from __future__ import annotations

import hashlib
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

from flask import Blueprint, jsonify, request

from app.core.config import OPPORTUNITY_ALERTS_ENABLED
from app.services.account_identity import get_verified_session_email
from app.services.job_discovery import (
    candidate_content_hash,
    candidate_fingerprint,
    clean_text,
    detect_adapter,
    fetch_source,
    normalize_terms,
    source_host_is_allowed,
    validate_public_https_url,
)
from app.services.job_documents import (
    approval_confirmations_are_complete,
    build_application_drafts,
    extract_resume_text,
)
from app.services.job_matching import rank_jobs, score_job
from app.services.job_visibility import job_is_visible_to_account
from app.services.supabase_client import get_supabase
from app.utils.admin_auth import require_admin_access


user_bp = Blueprint("job_automation", __name__)
admin_bp = Blueprint("job_automation_admin", __name__)

WATCH_SOURCE_TYPES = {"auto", "jsonld", "greenhouse", "lever", "workday", "smartrecruiters", "generic"}
WATCH_CADENCES = {"manual", "daily", "weekly"}
ALERT_STATUSES = {"unread", "read", "dismissed"}
DRAFT_STATUSES = {"draft", "reviewed", "approved", "exported", "archived"}
MAX_WATCHES_PER_SCAN = 10
MAX_SCHEDULED_WATCHES = 25


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _account() -> Tuple[Optional[str], Optional[Tuple[Any, int]]]:
    email = get_verified_session_email()
    if email:
        return email, None
    return None, (
        jsonify({
            "ok": False,
            "error": "verified_session_required",
            "hint": "Sign in with your MoveReady email code before using private job automation.",
        }),
        401,
    )


def _database_error(action: str, error: Exception):
    logging.exception("Jobs automation database error during %s: %s", action, error)
    return jsonify({
        "ok": False,
        "error": "jobs_automation_schema_unavailable",
        "hint": "Apply Supabase migration 032, refresh the schema, and retry.",
    }), 503


def _payload() -> Dict[str, Any]:
    value = request.get_json(silent=True)
    return value if isinstance(value, dict) else {}


def _text(value: Any, limit: int = 500) -> Optional[str]:
    value = clean_text(value, limit)
    return value or None


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().casefold() in {"1", "true", "yes", "on"}


def _profile(email: str) -> Optional[Dict[str, Any]]:
    return (
        get_supabase().table("relocation_job_search_profiles")
        .select("*").eq("email", email).maybe_single().execute()
    ).data


def _owned(table: str, record_id: str, email: str) -> Optional[Dict[str, Any]]:
    owner_field = "email"
    return (
        get_supabase().table(table).select("*")
        .eq("id", record_id).eq(owner_field, email).maybe_single().execute()
    ).data


def _visible_company(company_id: str, email: str) -> Optional[Dict[str, Any]]:
    row = (
        get_supabase().table("relocation_job_companies")
        .select("*").eq("id", company_id).maybe_single().execute()
    ).data
    if not row:
        return None
    if row.get("is_curated") or str(row.get("owner_email") or "").casefold() == email.casefold():
        return row
    return None


def _visible_job(job_id: str, email: str) -> Optional[Dict[str, Any]]:
    row = (
        get_supabase().table("relocation_jobs")
        .select("*").eq("id", job_id).maybe_single().execute()
    ).data
    return row if job_is_visible_to_account(row, email) else None


def _company_name(company_id: Any, email: str) -> str:
    if not company_id:
        return "Employer"
    company = _visible_company(str(company_id), email)
    return str((company or {}).get("company_name") or "Employer")


def _next_scan(cadence: str, from_dt: Optional[datetime] = None) -> Optional[str]:
    base = from_dt or _now()
    if cadence == "daily":
        return (base + timedelta(days=1)).isoformat()
    if cadence == "weekly":
        return (base + timedelta(days=7)).isoformat()
    return None


def _dedupe_key(*parts: Any) -> str:
    value = "|".join(str(part or "") for part in parts)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _create_alert(
    *,
    email: str,
    watch_id: Optional[str],
    job_id: Optional[str],
    alert_type: str,
    severity: str,
    title: str,
    summary: str,
    source_url: Optional[str],
    marker: Any,
) -> Tuple[Optional[Dict[str, Any]], bool]:
    supabase = get_supabase()
    dedupe = _dedupe_key(email.casefold(), watch_id, job_id, alert_type, marker)
    existing = (
        supabase.table("relocation_job_alerts").select("*")
        .eq("dedupe_key", dedupe).maybe_single().execute()
    ).data
    if existing:
        return existing, False
    response = supabase.table("relocation_job_alerts").insert({
        "email": email,
        "watch_id": watch_id,
        "job_id": job_id,
        "alert_type": alert_type,
        "severity": severity,
        "title": clean_text(title, 180),
        "summary": clean_text(summary, 700),
        "source_url": source_url,
        "dedupe_key": dedupe,
        "delivery_status": "email_disabled" if not OPPORTUNITY_ALERTS_ENABLED else "in_app",
    }).execute()
    return (response.data or [None])[0], True


def _watch_keywords(profile: Optional[Dict[str, Any]], supplied: Any = None) -> List[str]:
    values: List[Any] = []
    if isinstance(supplied, list):
        values.extend(supplied)
    elif supplied:
        values.extend(str(supplied).split(","))
    if profile:
        values.extend(profile.get("target_roles") or [])
        values.extend(profile.get("skills") or [])
    return normalize_terms(values, limit=30)


def _watch_row(payload: Dict[str, Any], email: str, *, partial: bool = False) -> Tuple[Dict[str, Any], Optional[str]]:
    row: Dict[str, Any] = {"email": email}
    if not partial or "company_id" in payload:
        company_id = _text(payload.get("company_id"), 80)
        if not company_id:
            return {}, "company_id_required"
        company = _visible_company(company_id, email)
        if not company:
            return {}, "company_not_found"
        row["company_id"] = company_id
        source_url = _text(payload.get("source_url") or company.get("career_page"), 1000)
        if not source_url:
            return {}, "official_career_page_required"
        try:
            source_url = validate_public_https_url(source_url, resolve_dns=False)
        except ValueError as exc:
            return {}, str(exc)
        allowed_company_urls = [str(company.get("website") or ""), str(company.get("career_page") or "")]
        if not source_host_is_allowed(source_url, allowed_company_urls):
            return {}, "source_url_must_match_employer_or_supported_ats"
        if not company.get("is_curated") and not source_host_is_allowed(source_url, []):
            return {}, "custom_company_monitor_requires_supported_public_ats"
        row["source_url"] = source_url
        row["watch_name"] = _text(payload.get("watch_name"), 180) or f"{company.get('company_name')} careers"
        row["country"] = _text(payload.get("country"), 100) or str(company.get("country") or "Canada")
        row["province"] = _text(payload.get("province"), 100) or company.get("province")

    if "source_type" in payload or not partial:
        source_type = _text(payload.get("source_type"), 30) or "auto"
        if source_type not in WATCH_SOURCE_TYPES:
            return {}, "invalid_source_type"
        row["source_type"] = source_type
    if "cadence" in payload or not partial:
        cadence = _text(payload.get("cadence"), 30) or "daily"
        if cadence not in WATCH_CADENCES:
            return {}, "invalid_cadence"
        row["cadence"] = cadence
        row["next_scan_at"] = _next_scan(cadence, _now() - timedelta(days=1))
    if "keywords" in payload or not partial:
        row["keywords"] = _watch_keywords(_profile(email), payload.get("keywords"))
    if "min_match_score" in payload:
        try:
            score = int(payload.get("min_match_score"))
        except (TypeError, ValueError):
            return {}, "invalid_min_match_score"
        if score < 0 or score > 100:
            return {}, "invalid_min_match_score"
        row["min_match_score"] = score
    if "email_alerts" in payload:
        row["email_alerts"] = _bool(payload.get("email_alerts"))
    if "is_active" in payload:
        row["is_active"] = _bool(payload.get("is_active"))
        if not row["is_active"]:
            row["last_scan_status"] = "paused"
            row["next_scan_at"] = None
    return row, None


def _public_watch(row: Dict[str, Any], companies: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    return {
        **row,
        "company_name": (companies.get(str(row.get("company_id"))) or {}).get("company_name"),
        "email": None,
    }


def _application_readiness(email: str, assistance: Dict[str, Any]) -> Dict[str, Any]:
    job = _visible_job(str(assistance.get("job_id") or ""), email)
    application = _owned("relocation_job_applications", str(assistance.get("application_id") or ""), email)
    approved = (
        get_supabase().table("relocation_job_document_drafts")
        .select("draft_type,status").eq("email", email).eq("job_id", assistance.get("job_id"))
        .in_("status", ["approved", "exported"]).execute()
    ).data or []
    approved_types = {str(row.get("draft_type")) for row in approved}
    url = str((job or {}).get("job_url") or (application or {}).get("job_url") or "")
    parsed = urlparse(url)
    checks = [
        {"code": "job_available", "label": "Vacancy is still recorded as open", "passed": bool(job and job.get("status") in {"open", "discovered"})},
        {"code": "official_link", "label": "Official HTTPS vacancy link is available", "passed": parsed.scheme == "https" and bool(parsed.netloc)},
        {"code": "application_saved", "label": "Opportunity is saved in Applications", "passed": bool(application)},
        {"code": "tailored_resume_approved", "label": "Tailored resume was reviewed and approved", "passed": "tailored_resume" in approved_types},
        {"code": "cover_letter_approved", "label": "Cover letter was reviewed and approved", "passed": "cover_letter" in approved_types},
    ]
    return {
        "ready": all(item["passed"] for item in checks),
        "checks": checks,
        "official_url": url if parsed.scheme == "https" and parsed.netloc else None,
        "safety_note": "MoveReady opens the employer site only. It does not submit forms, answer declarations, or claim an application was sent.",
    }


def _refresh_assistance(email: str, assistance: Dict[str, Any]) -> Dict[str, Any]:
    readiness = _application_readiness(email, assistance)
    current_status = str(assistance.get("status") or "preparing")
    terminal = current_status in {"official_site_opened", "submission_confirmed", "not_submitted", "paused"}
    status = current_status if terminal else ("ready" if readiness["ready"] else "preparing")
    response = (
        get_supabase().table("relocation_job_application_assistance")
        .update({"readiness": readiness, "status": status})
        .eq("id", assistance.get("id")).eq("email", email).execute()
    )
    return (response.data or [None])[0] or {**assistance, "readiness": readiness, "status": status}


def _record_event(email: str, assistance_id: str, event_type: str, payload: Optional[Dict[str, Any]] = None) -> None:
    get_supabase().table("relocation_job_assistance_events").insert({
        "email": email,
        "assistance_id": assistance_id,
        "event_type": event_type,
        "event_payload": payload or {},
    }).execute()


def _prepare_assistance(email: str, job: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    supabase = get_supabase()
    existing_apps = (
        supabase.table("relocation_job_applications").select("*")
        .eq("email", email).eq("job_id", job.get("id")).limit(1).execute()
    ).data or []
    if existing_apps:
        application = existing_apps[0]
    else:
        company_name = _company_name(job.get("company_id"), email)
        application = (supabase.table("relocation_job_applications").insert({
            "email": email,
            "job_id": job.get("id"),
            "company_id": job.get("company_id"),
            "recruiter_id": job.get("recruiter_id"),
            "job_title": job.get("job_title"),
            "company_name": company_name,
            "country": job.get("country") or "Canada",
            "province": job.get("province"),
            "job_url": job.get("job_url"),
            "status": "saved",
        }).execute().data or [None])[0]
    existing_assistance = (
        supabase.table("relocation_job_application_assistance").select("*")
        .eq("email", email).eq("job_id", job.get("id")).maybe_single().execute()
    ).data
    if existing_assistance:
        assistance = existing_assistance
    else:
        assistance = (supabase.table("relocation_job_application_assistance").insert({
            "email": email,
            "application_id": application.get("id"),
            "job_id": job.get("id"),
            "status": "preparing",
        }).execute().data or [None])[0]
        _record_event(email, str(assistance.get("id")), "prepared", {"job_id": job.get("id")})
    return application, _refresh_assistance(email, assistance)


def _scan_watch(watch: Dict[str, Any], *, trigger_type: str) -> Dict[str, Any]:
    supabase = get_supabase()
    watch_id = str(watch.get("id"))
    email = str(watch.get("email"))
    started_at = _now()
    run = (supabase.table("relocation_job_scan_runs").insert({
        "watch_id": watch_id,
        "email": email,
        "trigger_type": trigger_type,
        "status": "running",
        "started_at": started_at.isoformat(),
    }).execute().data or [None])[0]
    supabase.table("relocation_job_watches").update({
        "last_scan_status": "running",
        "last_error": None,
    }).eq("id", watch_id).eq("email", email).execute()
    new_count = changed_count = closed_count = alert_count = 0
    adapter = detect_adapter(str(watch.get("source_url") or ""), str(watch.get("source_type") or "auto"))
    try:
        fetched = fetch_source(str(watch.get("source_url") or ""), str(watch.get("source_type") or "auto"), watch.get("keywords") or [])
        adapter = str(fetched.get("adapter") or adapter)
        company = _visible_company(str(watch.get("company_id") or ""), email) or {}
        company_name = str(company.get("company_name") or "Employer")
        allowed_job_hosts = [str(watch.get("source_url") or ""), str(company.get("website") or ""), str(company.get("career_page") or "")]
        profile = _profile(email)
        seen_fingerprints = set()
        for candidate in fetched.get("jobs") or []:
            if not source_host_is_allowed(str(candidate.get("job_url") or ""), allowed_job_hosts):
                continue
            candidate["country"] = candidate.get("country") or watch.get("country") or "Canada"
            candidate["province"] = candidate.get("province") or watch.get("province")
            fingerprint = candidate_fingerprint(candidate, watch_id)
            content_hash = candidate_content_hash(candidate)
            seen_fingerprints.add(fingerprint)
            existing = (
                supabase.table("relocation_jobs").select("*")
                .eq("owner_email", email).eq("source_fingerprint", fingerprint).maybe_single().execute()
            ).data
            now_iso = _now_iso()
            metadata = {
                "automation_watch_id": watch_id,
                "source_adapter": adapter,
                "official_source": True,
                "company_name_from_source": candidate.get("company_name"),
                "monitor_misses": 0,
            }
            base_row = {
                "owner_email": email,
                "is_curated": False,
                "company_id": watch.get("company_id"),
                "job_title": candidate.get("job_title"),
                "country": candidate.get("country"),
                "province": candidate.get("province"),
                "city": candidate.get("city"),
                "employment_type": candidate.get("employment_type"),
                "job_url": candidate.get("job_url"),
                "source_name": candidate.get("source_name"),
                "source_url": candidate.get("source_url"),
                "description_summary": candidate.get("description_summary"),
                "skills": candidate.get("skills") or [],
                "posted_at": candidate.get("posted_at"),
                "expires_at": candidate.get("expires_at"),
                "status": "open",
                "source_status": "verified",
                "source_fingerprint": fingerprint,
                "source_content_hash": content_hash,
                "last_seen_at": now_iso,
                "last_checked_at": now_iso,
                "metadata": metadata,
            }
            if existing:
                prior_hash = str(existing.get("source_content_hash") or "")
                prior_status = str(existing.get("status") or "open")
                merged_metadata = {**(existing.get("metadata") if isinstance(existing.get("metadata"), dict) else {}), **metadata}
                base_row["metadata"] = merged_metadata
                response = (
                    supabase.table("relocation_jobs").update(base_row)
                    .eq("id", existing.get("id")).eq("owner_email", email).execute()
                )
                job = (response.data or [None])[0] or {**existing, **base_row}
                if prior_status in {"closed", "expired"}:
                    _alert, created = _create_alert(
                        email=email, watch_id=watch_id, job_id=str(job.get("id")), alert_type="job_reopened",
                        severity="action", title=f"Reopened: {job.get('job_title')}",
                        summary=f"{company_name} lists this vacancy again. Recheck the official page before preparing an application.",
                        source_url=job.get("job_url"), marker=content_hash,
                    )
                    alert_count += int(created)
                elif prior_hash and prior_hash != content_hash:
                    changed_count += 1
                    _alert, created = _create_alert(
                        email=email, watch_id=watch_id, job_id=str(job.get("id")), alert_type="job_changed",
                        severity="action", title=f"Vacancy changed: {job.get('job_title')}",
                        summary=f"The official {company_name} vacancy content changed. Review the source before using an earlier application draft.",
                        source_url=job.get("job_url"), marker=content_hash,
                    )
                    alert_count += int(created)
            else:
                base_row["first_seen_at"] = now_iso
                job = (supabase.table("relocation_jobs").insert(base_row).execute().data or [None])[0]
                new_count += 1
                match_score, reasons = score_job(job, profile)
                if match_score >= int(watch.get("min_match_score") or 0):
                    _alert, created = _create_alert(
                        email=email, watch_id=watch_id, job_id=str(job.get("id")), alert_type="new_match",
                        severity="action", title=f"New {match_score}% match: {job.get('job_title')}",
                        summary=f"{company_name} published a potential match. {reasons[0] if reasons else 'Review the official vacancy.'}",
                        source_url=job.get("job_url"), marker=fingerprint,
                    )
                    alert_count += int(created)

        if fetched.get("complete_listing"):
            monitored = (
                supabase.table("relocation_jobs").select("*")
                .eq("owner_email", email).execute()
            ).data or []
            for job in monitored:
                metadata = job.get("metadata") if isinstance(job.get("metadata"), dict) else {}
                if str(metadata.get("automation_watch_id") or "") != watch_id:
                    continue
                fingerprint = str(job.get("source_fingerprint") or "")
                if not fingerprint or fingerprint in seen_fingerprints:
                    continue
                misses = min(1000, int(metadata.get("monitor_misses") or 0) + 1)
                updates: Dict[str, Any] = {
                    "last_checked_at": _now_iso(),
                    "metadata": {**metadata, "monitor_misses": misses},
                }
                if misses >= 2 and job.get("status") not in {"closed", "archived"}:
                    updates["status"] = "closed"
                    updates["source_status"] = "unavailable"
                    closed_count += 1
                    _alert, created = _create_alert(
                        email=email, watch_id=watch_id, job_id=str(job.get("id")), alert_type="job_closed",
                        severity="warning", title=f"Vacancy no longer listed: {job.get('job_title')}",
                        summary=f"The role was absent from two complete {company_name} scans. Confirm on the official page before taking action.",
                        source_url=job.get("job_url"), marker=f"closed-{misses}",
                    )
                    alert_count += int(created)
                supabase.table("relocation_jobs").update(updates).eq("id", job.get("id")).eq("owner_email", email).execute()

        completed = _now_iso()
        status = "completed"
        result = {
            "watch_id": watch_id,
            "status": status,
            "adapter": adapter,
            "discovered_count": len(fetched.get("jobs") or []),
            "new_count": new_count,
            "changed_count": changed_count,
            "closed_count": closed_count,
            "alert_count": alert_count,
            "http_status": fetched.get("http_status"),
        }
        supabase.table("relocation_job_scan_runs").update({
            "status": status,
            "source_adapter": adapter,
            "source_http_status": fetched.get("http_status"),
            "discovered_count": result["discovered_count"],
            "new_count": new_count,
            "changed_count": changed_count,
            "closed_count": closed_count,
            "alert_count": alert_count,
            "completed_at": completed,
        }).eq("id", run.get("id")).execute()
        supabase.table("relocation_job_watches").update({
            "last_scan_at": completed,
            "next_scan_at": _next_scan(str(watch.get("cadence") or "manual")),
            "last_scan_status": status,
            "last_error": None,
            "consecutive_failures": 0,
            "last_result_count": result["discovered_count"],
        }).eq("id", watch_id).eq("email", email).execute()
        return result
    except Exception as exc:
        error_code = clean_text(str(exc), 100) or exc.__class__.__name__
        completed = _now_iso()
        failures = min(1000, int(watch.get("consecutive_failures") or 0) + 1)
        try:
            supabase.table("relocation_job_scan_runs").update({
                "status": "failed",
                "source_adapter": adapter,
                "error_code": error_code,
                "error_summary": "Official source could not be checked. The previous vacancy records were not changed.",
                "completed_at": completed,
            }).eq("id", run.get("id")).execute()
            supabase.table("relocation_job_watches").update({
                "last_scan_at": completed,
                "next_scan_at": _next_scan(str(watch.get("cadence") or "manual")),
                "last_scan_status": "failed",
                "last_error": error_code,
                "consecutive_failures": failures,
            }).eq("id", watch_id).eq("email", email).execute()
            _create_alert(
                email=email, watch_id=watch_id, job_id=None, alert_type="scan_failed", severity="warning",
                title=f"Could not check {watch.get('watch_name')}",
                summary="The official career source could not be read. Saved vacancies were left unchanged; try again later or update the source URL.",
                source_url=watch.get("source_url"), marker=f"{date.today().isoformat()}-{error_code}",
            )
        except Exception:
            logging.exception("Unable to record failed job scan for watch %s", watch_id)
        return {"watch_id": watch_id, "status": "failed", "adapter": adapter, "error": error_code}


@user_bp.get("/automation/overview")
def automation_overview():
    email, error = _account()
    if error:
        return error
    try:
        supabase = get_supabase()
        companies_list = (
            supabase.table("relocation_job_companies").select("id,company_name,website,career_page,country,province")
            .execute()
        ).data or []
        companies = {str(row.get("id")): row for row in companies_list}
        watches = (
            supabase.table("relocation_job_watches").select("*").eq("email", email)
            .order("updated_at", desc=True).execute()
        ).data or []
        jobs = (
            supabase.table("relocation_jobs").select("*").eq("owner_email", email)
            .order("updated_at", desc=True).limit(100).execute()
        ).data or []
        automation_jobs = [row for row in jobs if row.get("source_fingerprint")]
        ranked = rank_jobs(automation_jobs, _profile(email))
        for job in ranked:
            job["company_name"] = (companies.get(str(job.get("company_id"))) or {}).get("company_name")
        alerts = (
            supabase.table("relocation_job_alerts").select("*").eq("email", email)
            .order("created_at", desc=True).limit(100).execute()
        ).data or []
        drafts = (
            supabase.table("relocation_job_document_drafts").select("*").eq("email", email)
            .order("updated_at", desc=True).execute()
        ).data or []
        documents = (
            supabase.table("relocation_job_resume_assets")
            .select("id,document_type,title,original_file_name,mime_type,version,is_active,updated_at")
            .eq("email", email).order("updated_at", desc=True).execute()
        ).data or []
        applications = (
            supabase.table("relocation_job_applications").select("*").eq("email", email)
            .order("updated_at", desc=True).execute()
        ).data or []
        assistance = (
            supabase.table("relocation_job_application_assistance").select("*").eq("email", email)
            .order("updated_at", desc=True).execute()
        ).data or []
        refreshed_assistance = [_refresh_assistance(email, row) for row in assistance]
        return jsonify({
            "ok": True,
            "profile": _profile(email),
            "watches": [_public_watch(row, companies) for row in watches],
            "jobs": ranked,
            "alerts": alerts,
            "drafts": drafts,
            "documents": documents,
            "applications": applications,
            "assistance": refreshed_assistance,
            "counts": {
                "active_watches": sum(1 for row in watches if row.get("is_active")),
                "open_jobs": sum(1 for row in ranked if row.get("status") in {"open", "discovered"}),
                "unread_alerts": sum(1 for row in alerts if row.get("status") == "unread"),
                "approved_drafts": sum(1 for row in drafts if row.get("status") == "approved"),
                "ready_applications": sum(1 for row in refreshed_assistance if (row.get("readiness") or {}).get("ready")),
            },
            "capabilities": {
                "source_policy": "official_employer_and_supported_public_ats_only",
                "adapters": sorted(WATCH_SOURCE_TYPES),
                "email_alert_delivery": "controlled_rollout" if OPPORTUNITY_ALERTS_ENABLED else "not_enabled",
                "automatic_submission": False,
                "scheduled_scan_endpoint_ready": True,
            },
        })
    except Exception as exc:
        return _database_error("load automation overview", exc)


@user_bp.post("/automation/watches/bootstrap")
def bootstrap_watches():
    email, error = _account()
    if error:
        return error
    try:
        supabase = get_supabase()
        targets = (
            supabase.table("relocation_job_company_targets").select("company_id")
            .eq("email", email).execute()
        ).data or []
        profile = _profile(email)
        keywords = _watch_keywords(profile)
        created = updated = skipped = 0
        for target in targets[:30]:
            company = _visible_company(str(target.get("company_id") or ""), email)
            if not company or not company.get("career_page"):
                skipped += 1
                continue
            source_url = str(company.get("career_page"))
            try:
                source_url = validate_public_https_url(source_url, resolve_dns=False)
            except ValueError:
                skipped += 1
                continue
            if not company.get("is_curated") and not source_host_is_allowed(source_url, []):
                skipped += 1
                continue
            existing = (
                supabase.table("relocation_job_watches").select("*")
                .eq("email", email).eq("source_url", source_url).maybe_single().execute()
            ).data
            row = {
                "email": email,
                "company_id": company.get("id"),
                "watch_name": f"{company.get('company_name')} careers",
                "source_url": source_url,
                "source_type": "auto",
                "keywords": keywords,
                "country": company.get("country") or (profile or {}).get("primary_country") or "Canada",
                "province": company.get("province"),
                "cadence": "daily",
                "next_scan_at": _now_iso(),
                "is_active": True,
            }
            if existing:
                supabase.table("relocation_job_watches").update(row).eq("id", existing.get("id")).eq("email", email).execute()
                updated += 1
            else:
                supabase.table("relocation_job_watches").insert(row).execute()
                created += 1
        return jsonify({
            "ok": True,
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "message": "Official career-page monitors are ready for your selected target employers.",
        }), 201 if created else 200
    except Exception as exc:
        return _database_error("bootstrap official job watches", exc)


@user_bp.post("/automation/watches")
def create_watch():
    email, error = _account()
    if error:
        return error
    row, validation_error = _watch_row(_payload(), email)
    if validation_error:
        return jsonify({"ok": False, "error": validation_error}), 400
    try:
        response = get_supabase().table("relocation_job_watches").insert(row).execute()
        return jsonify({"ok": True, "watch": (response.data or [None])[0]}), 201
    except Exception as exc:
        return _database_error("create official job watch", exc)


@user_bp.patch("/automation/watches/<watch_id>")
def update_watch(watch_id: str):
    email, error = _account()
    if error:
        return error
    if not _owned("relocation_job_watches", watch_id, email):
        return jsonify({"ok": False, "error": "watch_not_found"}), 404
    row, validation_error = _watch_row(_payload(), email, partial=True)
    row.pop("email", None)
    if validation_error:
        return jsonify({"ok": False, "error": validation_error}), 400
    if not row:
        return jsonify({"ok": False, "error": "no_supported_fields_supplied"}), 400
    try:
        response = (
            get_supabase().table("relocation_job_watches").update(row)
            .eq("id", watch_id).eq("email", email).execute()
        )
        return jsonify({"ok": True, "watch": (response.data or [None])[0]})
    except Exception as exc:
        return _database_error("update official job watch", exc)


@user_bp.post("/automation/watches/<watch_id>/scan")
def scan_one_watch(watch_id: str):
    email, error = _account()
    if error:
        return error
    try:
        watch = _owned("relocation_job_watches", watch_id, email)
        if not watch:
            return jsonify({"ok": False, "error": "watch_not_found"}), 404
        if not watch.get("is_active"):
            return jsonify({"ok": False, "error": "watch_is_paused"}), 409
        result = _scan_watch(watch, trigger_type="user")
        status = 200 if result.get("status") != "failed" else 502
        return jsonify({"ok": status == 200, "scan": result}), status
    except Exception as exc:
        return _database_error("scan official job watch", exc)


@user_bp.post("/automation/scan")
def scan_active_watches():
    email, error = _account()
    if error:
        return error
    try:
        watches = (
            get_supabase().table("relocation_job_watches").select("*")
            .eq("email", email).eq("is_active", True).order("last_scan_at").limit(MAX_WATCHES_PER_SCAN).execute()
        ).data or []
        if not watches:
            return jsonify({"ok": False, "error": "no_active_watches", "hint": "Create monitors from your target employers first."}), 409
        results = [_scan_watch(watch, trigger_type="user") for watch in watches]
        succeeded = sum(1 for item in results if item.get("status") == "completed")
        return jsonify({
            "ok": succeeded > 0,
            "status": "completed" if succeeded == len(results) else "partial",
            "watch_count": len(results),
            "successful_count": succeeded,
            "results": results,
        }), 200 if succeeded else 502
    except Exception as exc:
        return _database_error("scan active official job watches", exc)


@user_bp.patch("/automation/alerts/<alert_id>")
def update_alert(alert_id: str):
    email, error = _account()
    if error:
        return error
    status = _text(_payload().get("status"), 30)
    if status not in ALERT_STATUSES:
        return jsonify({"ok": False, "error": "invalid_alert_status"}), 400
    try:
        if not _owned("relocation_job_alerts", alert_id, email):
            return jsonify({"ok": False, "error": "alert_not_found"}), 404
        updates = {"status": status, "read_at": _now_iso() if status == "read" else None}
        response = (
            get_supabase().table("relocation_job_alerts").update(updates)
            .eq("id", alert_id).eq("email", email).execute()
        )
        return jsonify({"ok": True, "alert": (response.data or [None])[0]})
    except Exception as exc:
        return _database_error("update job alert", exc)


@user_bp.post("/automation/jobs/<job_id>/prepare")
def prepare_application(job_id: str):
    email, error = _account()
    if error:
        return error
    try:
        job = _visible_job(job_id, email)
        if not job:
            return jsonify({"ok": False, "error": "job_not_found"}), 404
        application, assistance = _prepare_assistance(email, job)
        return jsonify({"ok": True, "job": job, "application": application, "assistance": assistance})
    except Exception as exc:
        return _database_error("prepare controlled job application", exc)


@user_bp.post("/automation/jobs/<job_id>/documents")
def generate_documents(job_id: str):
    email, error = _account()
    if error:
        return error
    resume_asset_id = _text(_payload().get("source_resume_asset_id"), 80)
    if not resume_asset_id:
        return jsonify({"ok": False, "error": "source_resume_asset_id_required"}), 400
    try:
        job = _visible_job(job_id, email)
        if not job:
            return jsonify({"ok": False, "error": "job_not_found"}), 404
        resume = _owned("relocation_job_resume_assets", resume_asset_id, email)
        if not resume or not resume.get("is_active"):
            return jsonify({"ok": False, "error": "active_resume_document_not_found"}), 404
        profile = _profile(email)
        if not profile:
            return jsonify({"ok": False, "error": "job_profile_required"}), 409
        contents = get_supabase().storage.from_(str(resume.get("storage_bucket") or "job-resume-vault")).download(str(resume.get("storage_path")))
        resume_text = extract_resume_text(contents, str(resume.get("mime_type") or ""))
        if len(clean_text(resume_text, 1000)) < 80:
            return jsonify({
                "ok": False,
                "error": "resume_text_could_not_be_extracted",
                "hint": "Upload a text-based PDF, DOCX, or TXT resume rather than a scanned image.",
            }), 422
        application, assistance = _prepare_assistance(email, job)
        drafts = build_application_drafts(
            profile=profile,
            job=job,
            company_name=_company_name(job.get("company_id"), email),
            resume_asset_id=resume_asset_id,
            resume_text=resume_text,
        )
        saved: List[Dict[str, Any]] = []
        for draft in drafts:
            row = {
                "email": email,
                "job_id": job_id,
                "application_id": application.get("id"),
                "source_resume_asset_id": resume_asset_id,
                **draft,
                "status": "draft",
                "user_confirmations": {},
                "approved_at": None,
                "exported_at": None,
            }
            response = get_supabase().table("relocation_job_document_drafts").upsert(
                row, on_conflict="email,job_id,draft_type"
            ).execute()
            saved.append((response.data or [None])[0])
        _record_event(email, str(assistance.get("id")), "documents_generated", {
            "draft_types": [row.get("draft_type") for row in saved],
            "source_resume_asset_id": resume_asset_id,
        })
        assistance = _refresh_assistance(email, assistance)
        return jsonify({
            "ok": True,
            "drafts": saved,
            "application": application,
            "assistance": assistance,
            "safety_note": "These are editable drafts, not final application documents. Review every claim before approval.",
        }), 201
    except RuntimeError as exc:
        return jsonify({"ok": False, "error": clean_text(str(exc), 100)}), 422
    except Exception as exc:
        return _database_error("generate truthful application documents", exc)


@user_bp.patch("/automation/documents/<draft_id>")
def update_document_draft(draft_id: str):
    email, error = _account()
    if error:
        return error
    payload = _payload()
    try:
        existing = _owned("relocation_job_document_drafts", draft_id, email)
        if not existing:
            return jsonify({"ok": False, "error": "document_draft_not_found"}), 404
        updates: Dict[str, Any] = {}
        if "content" in payload:
            content = _text(payload.get("content"), 30000)
            if not content or len(content) < 100:
                return jsonify({"ok": False, "error": "document_content_too_short"}), 400
            updates["content"] = content
            if existing.get("status") in {"approved", "exported"}:
                updates["status"] = "reviewed"
                updates["approved_at"] = None
        if "title" in payload:
            title = _text(payload.get("title"), 180)
            if not title:
                return jsonify({"ok": False, "error": "document_title_required"}), 400
            updates["title"] = title
        if "user_confirmations" in payload:
            confirmations = payload.get("user_confirmations")
            if not isinstance(confirmations, dict):
                return jsonify({"ok": False, "error": "user_confirmations_must_be_an_object"}), 400
            updates["user_confirmations"] = confirmations
        if "status" in payload:
            status = _text(payload.get("status"), 30)
            if status not in DRAFT_STATUSES:
                return jsonify({"ok": False, "error": "invalid_document_status"}), 400
            merged_content = str(updates.get("content") or existing.get("content") or "")
            confirmations = updates.get("user_confirmations", existing.get("user_confirmations"))
            if status == "approved":
                if not approval_confirmations_are_complete(confirmations):
                    return jsonify({"ok": False, "error": "all_truth_confirmations_are_required"}), 409
                remaining_instructions = [marker for marker in ("[Use ", "[Copy ", "[Review ", "[Add ") if marker.casefold() in merged_content.casefold()]
                if remaining_instructions:
                    return jsonify({
                        "ok": False,
                        "error": "remove_draft_instructions_before_approval",
                        "remaining_markers": remaining_instructions,
                    }), 409
                basis = existing.get("truth_basis") if isinstance(existing.get("truth_basis"), dict) else {}
                if int(basis.get("verified_fact_count") or 0) <= 0:
                    return jsonify({"ok": False, "error": "verified_career_evidence_required_before_approval"}), 409
                updates["approved_at"] = _now_iso()
            elif status == "exported" and existing.get("status") not in {"approved", "exported"}:
                return jsonify({"ok": False, "error": "approve_document_before_export"}), 409
            elif status != "exported":
                updates["approved_at"] = None
            if status == "exported":
                updates["exported_at"] = _now_iso()
            updates["status"] = status
        if not updates:
            return jsonify({"ok": False, "error": "no_supported_fields_supplied"}), 400
        response = (
            get_supabase().table("relocation_job_document_drafts").update(updates)
            .eq("id", draft_id).eq("email", email).execute()
        )
        draft = (response.data or [None])[0]
        assistance = (
            get_supabase().table("relocation_job_application_assistance").select("*")
            .eq("email", email).eq("job_id", existing.get("job_id")).maybe_single().execute()
        ).data
        if assistance:
            assistance = _refresh_assistance(email, assistance)
            if updates.get("status") == "approved":
                _record_event(email, str(assistance.get("id")), "documents_approved", {"draft_id": draft_id, "draft_type": draft.get("draft_type")})
        return jsonify({"ok": True, "draft": draft, "assistance": assistance})
    except Exception as exc:
        return _database_error("update application document draft", exc)


@user_bp.post("/automation/applications/<application_id>/handoff")
def open_official_application(application_id: str):
    email, error = _account()
    if error:
        return error
    try:
        application = _owned("relocation_job_applications", application_id, email)
        if not application:
            return jsonify({"ok": False, "error": "application_not_found"}), 404
        assistance = (
            get_supabase().table("relocation_job_application_assistance").select("*")
            .eq("email", email).eq("application_id", application_id).maybe_single().execute()
        ).data
        if not assistance:
            return jsonify({"ok": False, "error": "application_assistance_not_prepared"}), 409
        assistance = _refresh_assistance(email, assistance)
        readiness = assistance.get("readiness") if isinstance(assistance.get("readiness"), dict) else {}
        if not readiness.get("ready"):
            return jsonify({"ok": False, "error": "application_not_ready", "readiness": readiness}), 409
        official_url = str(readiness.get("official_url") or "")
        validate_public_https_url(official_url, resolve_dns=False)
        updated = (
            get_supabase().table("relocation_job_application_assistance").update({
                "status": "official_site_opened",
                "last_handoff_at": _now_iso(),
            }).eq("id", assistance.get("id")).eq("email", email).execute()
        ).data or []
        assistance = updated[0] if updated else assistance
        _record_event(email, str(assistance.get("id")), "official_site_opened", {"host": urlparse(official_url).hostname})
        return jsonify({
            "ok": True,
            "official_url": official_url,
            "assistance": assistance,
            "submission_status": "not_confirmed",
            "safety_note": "Complete the employer form yourself. Return to MoveReady afterward and record whether it was actually submitted.",
        })
    except ValueError as exc:
        return jsonify({"ok": False, "error": clean_text(str(exc), 100)}), 409
    except Exception as exc:
        return _database_error("open official employer application", exc)


@user_bp.post("/automation/applications/<application_id>/confirm")
def confirm_application_result(application_id: str):
    email, error = _account()
    if error:
        return error
    payload = _payload()
    outcome = _text(payload.get("outcome"), 30)
    if outcome not in {"submitted", "not_submitted"}:
        return jsonify({"ok": False, "error": "outcome_must_be_submitted_or_not_submitted"}), 400
    if outcome == "submitted" and not _bool(payload.get("i_confirm_submitted")):
        return jsonify({"ok": False, "error": "explicit_submission_confirmation_required"}), 409
    try:
        application = _owned("relocation_job_applications", application_id, email)
        if not application:
            return jsonify({"ok": False, "error": "application_not_found"}), 404
        assistance = (
            get_supabase().table("relocation_job_application_assistance").select("*")
            .eq("email", email).eq("application_id", application_id).maybe_single().execute()
        ).data
        if not assistance:
            return jsonify({"ok": False, "error": "application_assistance_not_prepared"}), 409
        notes = _text(payload.get("notes"), 2000)
        reference_hint = _text(payload.get("submission_reference_hint"), 80)
        if outcome == "submitted":
            application = (
                get_supabase().table("relocation_job_applications").update({
                    "status": "applied",
                    "date_applied": date.today().isoformat(),
                    "notes": notes or application.get("notes"),
                }).eq("id", application_id).eq("email", email).execute().data or [application]
            )[0]
            assistance_updates = {
                "status": "submission_confirmed",
                "submission_confirmed_at": _now_iso(),
                "submission_reference_hint": reference_hint,
                "notes": notes,
            }
            event_type = "submission_confirmed"
        else:
            assistance_updates = {
                "status": "not_submitted",
                "submission_confirmed_at": None,
                "submission_reference_hint": None,
                "notes": notes,
            }
            event_type = "not_submitted"
        assistance = (
            get_supabase().table("relocation_job_application_assistance").update(assistance_updates)
            .eq("id", assistance.get("id")).eq("email", email).execute().data or [assistance]
        )[0]
        _record_event(email, str(assistance.get("id")), event_type, {
            "application_id": application_id,
            "reference_hint_recorded": bool(reference_hint and outcome == "submitted"),
        })
        return jsonify({
            "ok": True,
            "outcome": outcome,
            "application": application,
            "assistance": assistance,
            "message": "Application recorded as submitted." if outcome == "submitted" else "Application remains unsubmitted and can be revisited.",
        })
    except Exception as exc:
        return _database_error("confirm controlled application result", exc)


@admin_bp.post("/jobs/automation/scheduled-scan")
@require_admin_access
def scheduled_job_scan():
    try:
        now_iso = _now_iso()
        rows = (
            get_supabase().table("relocation_job_watches").select("*")
            .eq("is_active", True).lte("next_scan_at", now_iso)
            .order("next_scan_at").limit(MAX_SCHEDULED_WATCHES).execute()
        ).data or []
        results = [_scan_watch(row, trigger_type="scheduled") for row in rows]
        succeeded = sum(1 for item in results if item.get("status") == "completed")
        return jsonify({
            "ok": succeeded == len(results),
            "status": "completed" if succeeded == len(results) else "partial",
            "due_watch_count": len(rows),
            "successful_count": succeeded,
            "results": results,
            "next_action": "Run this protected endpoint from one approved scheduler; do not expose the admin key in a client application.",
        }), 200 if succeeded or not rows else 502
    except Exception as exc:
        return _database_error("run scheduled official job monitoring", exc)
