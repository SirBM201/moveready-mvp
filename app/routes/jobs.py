from __future__ import annotations

import hashlib
import logging
import re
import secrets
from datetime import date, datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

from flask import Blueprint, jsonify, request
from werkzeug.utils import secure_filename

from app.services.account_identity import get_verified_session_email
from app.services.job_actions import build_job_actions, count_job_actions
from app.services.job_matching import rank_jobs
from app.services.supabase_client import get_supabase


bp = Blueprint("jobs", __name__)

APPLICATION_STATUSES = ["saved", "applied", "interview", "rejected", "offer", "visa"]
COMPANY_PRIORITIES = ["high", "medium", "low", "watch"]
COMPANY_TARGET_STATUSES = ["researching", "targeting", "contacted", "applied", "interview", "offer", "paused", "archived"]
CONNECTION_STATUSES = ["not_contacted", "connection_requested", "connected", "contacted", "responded", "follow_up", "inactive"]
DOCUMENT_TYPES = ["executive_resume", "ats_resume", "cover_letter", "manufacturing_portfolio"]
JOB_STATUSES = ["discovered", "open", "closed", "expired", "archived"]
SPONSORSHIP_STATUSES = ["unknown", "not_verified", "possible", "confirmed", "not_available"]
SOURCE_STATUSES = ["verified", "review_required", "stale", "unavailable"]
WORK_AUTHORIZATION_STATUSES = ["citizen", "permanent_resident", "open_permit", "employer_specific_permit", "requires_sponsorship", "not_recorded"]
ALLOWED_RESUME_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}
RESUME_BUCKET = "job-resume-vault"
MAX_RESUME_BYTES = 5 * 1024 * 1024


def _text(value: Any, limit: int = 500) -> Optional[str]:
    cleaned = str(value or "").strip()
    return cleaned[:limit] or None


def _string_list(value: Any, limit: int = 20, item_limit: int = 100) -> List[str]:
    if value in (None, ""):
        return []
    values = value if isinstance(value, list) else str(value).split(",")
    result: List[str] = []
    seen = set()
    for item in values:
        cleaned = _text(item, item_limit)
        key = str(cleaned or "").casefold()
        if cleaned and key not in seen:
            seen.add(key)
            result.append(cleaned)
        if len(result) >= limit:
            break
    return result


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _number(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        parsed = round(float(value), 2)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _integer(value: Any, minimum: int = 0, maximum: int = 60) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if minimum <= parsed <= maximum else None


def _date(value: Any) -> Optional[str]:
    raw = _text(value, 40)
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10]).isoformat()
    except ValueError:
        return None


def _datetime(value: Any) -> Optional[str]:
    raw = _text(value, 80)
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()
    except ValueError:
        return None


def _url(value: Any) -> Optional[str]:
    cleaned = _text(value, 1000)
    if not cleaned:
        return None
    parsed = urlparse(cleaned)
    return cleaned if parsed.scheme in {"http", "https"} and bool(parsed.netloc) else None


def _json_payload() -> Dict[str, Any]:
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else {}


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")[:80] or "company"


def _account() -> Tuple[Optional[str], Optional[Tuple[Any, int]]]:
    email = get_verified_session_email()
    if email:
        return email, None
    return None, (
        jsonify({
            "ok": False,
            "error": "verified_session_required",
            "hint": "Sign in with your MoveReady email code before using the private Jobs workspace.",
        }),
        401,
    )


def _database_error(action: str, error: Exception):
    logging.exception("Jobs module database error during %s: %s", action, error)
    return jsonify({
        "ok": False,
        "error": "jobs_schema_unavailable",
        "hint": "Apply Supabase migration 031, refresh the schema, and retry.",
    }), 503


def _profile(email: str) -> Optional[Dict[str, Any]]:
    response = (
        get_supabase()
        .table("relocation_job_search_profiles")
        .select("*")
        .eq("email", email)
        .maybe_single()
        .execute()
    )
    return response.data


def _owned_row(table: str, record_id: str, email: str) -> Optional[Dict[str, Any]]:
    response = (
        get_supabase()
        .table(table)
        .select("*")
        .eq("id", record_id)
        .eq("owner_email" if table in {"relocation_job_recruiters", "relocation_jobs"} else "email", email)
        .maybe_single()
        .execute()
    )
    return response.data


def _visible_company(company_id: str, email: str) -> Optional[Dict[str, Any]]:
    response = (
        get_supabase()
        .table("relocation_job_companies")
        .select("*")
        .eq("id", company_id)
        .maybe_single()
        .execute()
    )
    row = response.data
    if not row:
        return None
    if row.get("is_curated") or str(row.get("owner_email") or "").casefold() == email.casefold():
        return row
    return None


def _validate_documents(email: str, document_ids: Sequence[Any]) -> Tuple[List[str], Optional[str]]:
    cleaned = [_text(item, 80) for item in document_ids]
    ids = [item for item in cleaned if item]
    if not ids:
        return [], None
    response = (
        get_supabase()
        .table("relocation_job_resume_assets")
        .select("id")
        .eq("email", email)
        .in_("id", ids)
        .execute()
    )
    allowed = {str(row.get("id")) for row in response.data or []}
    if allowed != set(ids):
        return [], "One or more selected resume documents do not belong to this account."
    return ids, None


def _companies_for_account(email: str) -> List[Dict[str, Any]]:
    supabase = get_supabase()
    curated = (
        supabase.table("relocation_job_companies")
        .select("*")
        .eq("is_curated", True)
        .order("company_name")
        .execute()
    ).data or []
    owned = (
        supabase.table("relocation_job_companies")
        .select("*")
        .eq("owner_email", email)
        .order("company_name")
        .execute()
    ).data or []
    targets = (
        supabase.table("relocation_job_company_targets")
        .select("*")
        .eq("email", email)
        .execute()
    ).data or []
    target_by_company = {str(row.get("company_id")): row for row in targets}
    recruiters = (
        supabase.table("relocation_job_recruiters")
        .select("id,company_id,recruiter_name,recruitment_company,specialization,connection_status,connected")
        .eq("owner_email", email)
        .order("updated_at", desc=True)
        .execute()
    ).data or []
    recruiters_by_company: Dict[str, List[Dict[str, Any]]] = {}
    for recruiter in recruiters:
        company_key = str(recruiter.get("company_id") or "")
        if company_key:
            recruiters_by_company.setdefault(company_key, []).append(recruiter)
    return [
        {
            **row,
            "tracking": target_by_company.get(str(row.get("id"))),
            "recruiter": (recruiters_by_company.get(str(row.get("id"))) or [None])[0],
            "recruiter_count": len(recruiters_by_company.get(str(row.get("id"))) or []),
        }
        for row in [*curated, *owned]
    ]


def _jobs_for_account(email: str) -> List[Dict[str, Any]]:
    supabase = get_supabase()
    curated = (
        supabase.table("relocation_jobs")
        .select("*")
        .eq("is_curated", True)
        .order("updated_at", desc=True)
        .execute()
    ).data or []
    owned = (
        supabase.table("relocation_jobs")
        .select("*")
        .eq("owner_email", email)
        .order("updated_at", desc=True)
        .execute()
    ).data or []
    companies = {str(row.get("id")): row for row in _companies_for_account(email)}
    recruiters = {
        str(row.get("id")): row
        for row in (
            supabase.table("relocation_job_recruiters")
            .select("id,recruiter_name,recruitment_company")
            .eq("owner_email", email)
            .execute()
        ).data or []
    }
    return [
        {
            **row,
            "company_name": (companies.get(str(row.get("company_id"))) or {}).get("company_name"),
            "recruiter_name": (recruiters.get(str(row.get("recruiter_id"))) or {}).get("recruiter_name"),
        }
        for row in [*curated, *owned]
    ]


@bp.get("/options")
def jobs_options():
    email, error = _account()
    if error:
        return error
    return jsonify({
        "ok": True,
        "account_email": email,
        "options": {
            "application_statuses": APPLICATION_STATUSES,
            "company_priorities": COMPANY_PRIORITIES,
            "company_target_statuses": COMPANY_TARGET_STATUSES,
            "connection_statuses": CONNECTION_STATUSES,
            "document_types": DOCUMENT_TYPES,
            "job_statuses": JOB_STATUSES,
            "source_statuses": SOURCE_STATUSES,
            "sponsorship_statuses": SPONSORSHIP_STATUSES,
            "work_authorization_statuses": WORK_AUTHORIZATION_STATUSES,
        },
        "storage": {"max_file_bytes": MAX_RESUME_BYTES, "allowed_mime_types": sorted(ALLOWED_RESUME_MIME_TYPES)},
    })


@bp.get("/profile")
def get_job_profile():
    email, error = _account()
    if error:
        return error
    try:
        return jsonify({"ok": True, "profile": _profile(email)})
    except Exception as exc:
        return _database_error("load profile", exc)


@bp.patch("/profile")
def update_job_profile():
    email, error = _account()
    if error:
        return error
    payload = _json_payload()
    row: Dict[str, Any] = {"email": email}
    scalar_fields = {
        "display_name": 120,
        "headline": 180,
        "education_level": 160,
        "current_employer": 180,
        "previous_employer": 180,
        "primary_country": 100,
    }
    for field, limit in scalar_fields.items():
        if field in payload:
            row[field] = _text(payload.get(field), limit)
    try:
        existing_profile = _profile(email)
    except Exception as exc:
        return _database_error("load profile before update", exc)
    if not row.get("headline") and not existing_profile:
        return jsonify({"ok": False, "error": "headline_required"}), 400
    if "years_experience" in payload:
        years = _integer(payload.get("years_experience"))
        if years is None:
            return jsonify({"ok": False, "error": "years_experience_must_be_between_0_and_60"}), 400
        row["years_experience"] = years
    for field in ("target_roles", "skills", "later_countries", "preferred_provinces"):
        if field in payload:
            row[field] = _string_list(payload.get(field), 30, 120)
    if "work_authorization_status" in payload:
        status = _text(payload.get("work_authorization_status"), 80)
        if status not in WORK_AUTHORIZATION_STATUSES:
            return jsonify({"ok": False, "error": "invalid_work_authorization_status"}), 400
        row["work_authorization_status"] = status
    if "is_active" in payload:
        row["is_active"] = _bool(payload.get("is_active"))
    try:
        response = (
            get_supabase()
            .table("relocation_job_search_profiles")
            .upsert(row, on_conflict="email")
            .execute()
        )
        profile = (response.data or [None])[0] or _profile(email)
        return jsonify({"ok": True, "profile": profile})
    except Exception as exc:
        return _database_error("update profile", exc)


@bp.post("/profile/bootstrap")
def bootstrap_founder_profile():
    email, error = _account()
    if error:
        return error
    try:
        profile = _profile(email)
        created = False
        if not profile:
            response = (
                get_supabase()
                .table("relocation_job_search_profiles")
                .insert({
                    "email": email,
                    "display_name": "Moses",
                    "headline": "Production Supervisor and PET Injection Moulding Specialist",
                    "years_experience": 19,
                    "education_level": "OND, Mechanical Engineering Technology",
                    "current_employer": "Genoa Plastic Industries",
                    "previous_employer": "Sonnex Packaging",
                    "target_roles": [
                        "Production Supervisor",
                        "Shift Supervisor",
                        "PET Injection Moulding Specialist",
                        "Injection Moulding Process Technician",
                        "Manufacturing Production Lead",
                    ],
                    "skills": [
                        "PET preforms", "injection moulding", "production supervision",
                        "process troubleshooting", "Husky", "SIPA", "Netstal",
                        "Ferromatik", "Demark", "Sacmi", "operator training",
                        "startup and restart optimization",
                    ],
                    "primary_country": "Canada",
                    "later_countries": ["Portugal", "Finland", "Germany", "Australia", "New Zealand"],
                    "preferred_provinces": ["Ontario", "Manitoba"],
                    "work_authorization_status": "requires_sponsorship",
                })
                .execute()
            )
            profile = (response.data or [None])[0] or _profile(email)
            created = True

        companies = (
            get_supabase()
            .table("relocation_job_companies")
            .select("id")
            .eq("is_curated", True)
            .execute()
        ).data or []
        existing = (
            get_supabase()
            .table("relocation_job_company_targets")
            .select("company_id")
            .eq("email", email)
            .execute()
        ).data or []
        existing_ids = {str(row.get("company_id")) for row in existing}
        new_targets = [
            {"email": email, "company_id": row.get("id"), "priority": "high", "status": "researching"}
            for row in companies
            if str(row.get("id")) not in existing_ids
        ]
        if new_targets:
            get_supabase().table("relocation_job_company_targets").insert(new_targets).execute()
        return jsonify({
            "ok": True,
            "created": created,
            "profile": profile,
            "target_companies_added": len(new_targets),
            "message": "Canadian plastics-manufacturing search profile is ready.",
        }), 201 if created else 200
    except Exception as exc:
        return _database_error("bootstrap founder profile", exc)


@bp.get("/summary")
def jobs_summary():
    email, error = _account()
    if error:
        return error
    try:
        supabase = get_supabase()
        profile = _profile(email)
        jobs = _jobs_for_account(email)
        applications = (
            supabase.table("relocation_job_applications")
            .select("*")
            .eq("email", email)
            .order("updated_at", desc=True)
            .execute()
        ).data or []
        targets = (
            supabase.table("relocation_job_company_targets")
            .select("*")
            .eq("email", email)
            .execute()
        ).data or []
        recruiters = (
            supabase.table("relocation_job_recruiters")
            .select("*")
            .eq("owner_email", email)
            .execute()
        ).data or []
        resumes = (
            supabase.table("relocation_job_resume_assets")
            .select("*")
            .eq("email", email)
            .execute()
        ).data or []
        actions = build_job_actions(applications, recruiters)
        action_counts = count_job_actions(actions)
        ranked = rank_jobs([row for row in jobs if row.get("status") in {"open", "discovered"}], profile)
        by_status = {status: sum(1 for row in applications if row.get("status") == status) for status in APPLICATION_STATUSES}
        return jsonify({
            "ok": True,
            "profile": profile,
            "counts": {
                "recommended_jobs": len(ranked),
                "target_companies": len(targets),
                "recruiters": len(recruiters),
                "applications": len(applications),
                "resume_documents": len(resumes),
                "follow_ups_due": action_counts["total"],
            },
            "applications_by_status": by_status,
            "recommended_jobs": ranked[:8],
            "action_counts": action_counts,
            "action_items": actions[:12],
            "follow_ups": [item for item in applications if item.get("follow_up_date")][:8],
            "privacy_note": "Job-search records and resume files are private to the verified MoveReady account. Employer sponsorship and LMIA fields require source verification.",
        })
    except Exception as exc:
        return _database_error("load dashboard", exc)


@bp.get("/companies")
def list_companies():
    email, error = _account()
    if error:
        return error
    try:
        rows = _companies_for_account(email)
        search = str(request.args.get("search") or "").strip().casefold()
        province = str(request.args.get("province") or "").strip().casefold()
        priority = str(request.args.get("priority") or "").strip()
        status = str(request.args.get("status") or "").strip()
        if search:
            rows = [row for row in rows if search in " ".join(str(row.get(key) or "") for key in ("company_name", "industry", "province")).casefold()]
        if province:
            rows = [row for row in rows if str(row.get("province") or "").casefold() == province]
        if priority:
            rows = [row for row in rows if (row.get("tracking") or {}).get("priority") == priority]
        if status:
            rows = [row for row in rows if (row.get("tracking") or {}).get("status") == status]
        return jsonify({"ok": True, "companies": rows, "count": len(rows)})
    except Exception as exc:
        return _database_error("list companies", exc)


@bp.post("/companies")
def create_company():
    email, error = _account()
    if error:
        return error
    payload = _json_payload()
    name = _text(payload.get("company_name"), 180)
    industry = _text(payload.get("industry"), 180)
    if not name or not industry:
        return jsonify({"ok": False, "error": "company_name_and_industry_required"}), 400
    website = _url(payload.get("website"))
    career_page = _url(payload.get("career_page"))
    if payload.get("website") and not website or payload.get("career_page") and not career_page:
        return jsonify({"ok": False, "error": "company_urls_must_use_http_or_https"}), 400
    row = {
        "owner_email": email,
        "is_curated": False,
        "company_name": name,
        "slug": f"{_slug(name)}-{secrets.token_hex(4)}",
        "industry": industry,
        "country": _text(payload.get("country"), 100) or "Canada",
        "province": _text(payload.get("province"), 100),
        "website": website,
        "career_page": career_page,
        "source_url": career_page or website,
        "source_status": "review_required",
    }
    try:
        response = get_supabase().table("relocation_job_companies").insert(row).execute()
        company = (response.data or [None])[0]
        tracking = {
            "email": email,
            "company_id": company.get("id"),
            "priority": payload.get("priority") if payload.get("priority") in COMPANY_PRIORITIES else "medium",
            "status": payload.get("status") if payload.get("status") in COMPANY_TARGET_STATUSES else "researching",
            "notes": _text(payload.get("notes"), 3000),
        }
        target_response = get_supabase().table("relocation_job_company_targets").insert(tracking).execute()
        return jsonify({"ok": True, "company": {**company, "tracking": (target_response.data or [tracking])[0]}}), 201
    except Exception as exc:
        return _database_error("create company", exc)


@bp.put("/companies/<company_id>/tracking")
@bp.patch("/companies/<company_id>/tracking")
def update_company_tracking(company_id: str):
    email, error = _account()
    if error:
        return error
    payload = _json_payload()
    priority = _text(payload.get("priority"), 40) or "medium"
    status = _text(payload.get("status"), 40) or "researching"
    if priority not in COMPANY_PRIORITIES or status not in COMPANY_TARGET_STATUSES:
        return jsonify({"ok": False, "error": "invalid_company_tracking_status"}), 400
    try:
        company = _visible_company(company_id, email)
        if not company:
            return jsonify({"ok": False, "error": "company_not_found"}), 404
        response = (
            get_supabase()
            .table("relocation_job_company_targets")
            .upsert({
                "email": email,
                "company_id": company_id,
                "priority": priority,
                "status": status,
                "notes": _text(payload.get("notes"), 3000),
            }, on_conflict="email,company_id")
            .execute()
        )
        return jsonify({"ok": True, "tracking": (response.data or [None])[0]})
    except Exception as exc:
        return _database_error("update company tracking", exc)


@bp.get("/recruiters")
def list_recruiters():
    email, error = _account()
    if error:
        return error
    try:
        rows = (
            get_supabase().table("relocation_job_recruiters")
            .select("*")
            .eq("owner_email", email)
            .order("updated_at", desc=True)
            .execute()
        ).data or []
        return jsonify({"ok": True, "recruiters": rows, "count": len(rows)})
    except Exception as exc:
        return _database_error("list recruiters", exc)


def _recruiter_row(payload: Dict[str, Any], email: str, partial: bool = False) -> Tuple[Dict[str, Any], Optional[str]]:
    row: Dict[str, Any] = {"owner_email": email}
    name = _text(payload.get("recruiter_name"), 180)
    if not partial and not name:
        return {}, "recruiter_name_required"
    if name:
        row["recruiter_name"] = name
    for field, limit in (("recruitment_company", 180), ("province", 100), ("specialization", 300), ("email_address", 240), ("phone", 80), ("notes", 3000)):
        if field in payload:
            row[field] = _text(payload.get(field), limit)
    for field in ("linkedin_url", "website"):
        if field in payload:
            value = _url(payload.get(field))
            if payload.get(field) and not value:
                return {}, f"invalid_{field}"
            row[field] = value
    if "company_id" in payload:
        row["company_id"] = _text(payload.get("company_id"), 80)
    if "connected" in payload:
        row["connected"] = _bool(payload.get("connected"))
    if "connection_status" in payload:
        status = _text(payload.get("connection_status"), 60)
        if status not in CONNECTION_STATUSES:
            return {}, "invalid_connection_status"
        row["connection_status"] = status
        if status == "connected":
            row["connected"] = True
    if "last_contacted_at" in payload:
        row["last_contacted_at"] = _datetime(payload.get("last_contacted_at"))
    if "follow_up_date" in payload:
        row["follow_up_date"] = _date(payload.get("follow_up_date"))
    return row, None


@bp.post("/recruiters")
def create_recruiter():
    email, error = _account()
    if error:
        return error
    payload = _json_payload()
    row, validation_error = _recruiter_row(payload, email)
    if validation_error:
        return jsonify({"ok": False, "error": validation_error}), 400
    try:
        if row.get("company_id") and not _visible_company(str(row["company_id"]), email):
            return jsonify({"ok": False, "error": "company_not_found"}), 404
        response = get_supabase().table("relocation_job_recruiters").insert(row).execute()
        return jsonify({"ok": True, "recruiter": (response.data or [None])[0]}), 201
    except Exception as exc:
        return _database_error("create recruiter", exc)


@bp.patch("/recruiters/<recruiter_id>")
def update_recruiter(recruiter_id: str):
    email, error = _account()
    if error:
        return error
    payload = _json_payload()
    row, validation_error = _recruiter_row(payload, email, partial=True)
    row.pop("owner_email", None)
    if validation_error:
        return jsonify({"ok": False, "error": validation_error}), 400
    try:
        if not _owned_row("relocation_job_recruiters", recruiter_id, email):
            return jsonify({"ok": False, "error": "recruiter_not_found"}), 404
        if row.get("company_id") and not _visible_company(str(row["company_id"]), email):
            return jsonify({"ok": False, "error": "company_not_found"}), 404
        response = (
            get_supabase().table("relocation_job_recruiters")
            .update(row).eq("id", recruiter_id).eq("owner_email", email).execute()
        )
        return jsonify({"ok": True, "recruiter": (response.data or [None])[0]})
    except Exception as exc:
        return _database_error("update recruiter", exc)


@bp.get("")
def list_jobs():
    email, error = _account()
    if error:
        return error
    try:
        jobs = _jobs_for_account(email)
        status = _text(request.args.get("status"), 40)
        search = str(request.args.get("search") or "").strip().casefold()
        if status:
            jobs = [row for row in jobs if row.get("status") == status]
        if search:
            jobs = [row for row in jobs if search in " ".join(str(row.get(key) or "") for key in ("job_title", "province", "city", "description_summary")).casefold()]
        ranked = rank_jobs(jobs, _profile(email))
        return jsonify({"ok": True, "jobs": ranked, "count": len(ranked)})
    except Exception as exc:
        return _database_error("list jobs", exc)


def _job_row(payload: Dict[str, Any], email: str, partial: bool = False) -> Tuple[Dict[str, Any], Optional[str]]:
    row: Dict[str, Any] = {"owner_email": email, "is_curated": False}
    title = _text(payload.get("job_title"), 220)
    if not partial and not title:
        return {}, "job_title_required"
    if title:
        row["job_title"] = title
    for field, limit in (("country", 100), ("province", 100), ("city", 100), ("employment_type", 100), ("source_name", 180), ("description_summary", 4000)):
        if field in payload:
            row[field] = _text(payload.get(field), limit)
    for field in ("job_url", "source_url"):
        if field in payload:
            value = _url(payload.get(field))
            if payload.get(field) and not value:
                return {}, f"invalid_{field}"
            row[field] = value
    for field in ("company_id", "recruiter_id"):
        if field in payload:
            row[field] = _text(payload.get(field), 80)
    if "skills" in payload:
        row["skills"] = _string_list(payload.get("skills"), 30, 100)
    if "salary_min" in payload:
        row["salary_min"] = _number(payload.get("salary_min"))
    if "salary_max" in payload:
        row["salary_max"] = _number(payload.get("salary_max"))
    if row.get("salary_min") is not None and row.get("salary_max") is not None and row["salary_max"] < row["salary_min"]:
        return {}, "salary_max_must_not_be_less_than_salary_min"
    if "salary_currency" in payload:
        row["salary_currency"] = (_text(payload.get("salary_currency"), 3) or "").upper() or None
    if "workplace_type" in payload:
        workplace = _text(payload.get("workplace_type"), 30)
        if workplace not in {"onsite", "hybrid", "remote"}:
            return {}, "invalid_workplace_type"
        row["workplace_type"] = workplace
    if "visa_sponsorship_status" in payload:
        sponsorship = _text(payload.get("visa_sponsorship_status"), 40)
        if sponsorship not in SPONSORSHIP_STATUSES:
            return {}, "invalid_visa_sponsorship_status"
        row["visa_sponsorship_status"] = sponsorship
    if "status" in payload:
        status = _text(payload.get("status"), 40)
        if status not in JOB_STATUSES:
            return {}, "invalid_job_status"
        row["status"] = status
    if "source_status" in payload:
        source_status = _text(payload.get("source_status"), 40)
        if source_status not in SOURCE_STATUSES:
            return {}, "invalid_source_status"
        row["source_status"] = source_status
    for field in ("posted_at", "expires_at"):
        if field in payload:
            row[field] = _datetime(payload.get(field))
    return row, None


@bp.post("")
def create_job():
    email, error = _account()
    if error:
        return error
    payload = _json_payload()
    row, validation_error = _job_row(payload, email)
    if validation_error:
        return jsonify({"ok": False, "error": validation_error}), 400
    if not row.get("country"):
        row["country"] = "Canada"
    try:
        if row.get("company_id") and not _visible_company(str(row["company_id"]), email):
            return jsonify({"ok": False, "error": "company_not_found"}), 404
        if row.get("recruiter_id") and not _owned_row("relocation_job_recruiters", str(row["recruiter_id"]), email):
            return jsonify({"ok": False, "error": "recruiter_not_found"}), 404
        response = get_supabase().table("relocation_jobs").insert(row).execute()
        job = (response.data or [None])[0]
        ranked = rank_jobs([job], _profile(email))[0]
        return jsonify({"ok": True, "job": ranked}), 201
    except Exception as exc:
        return _database_error("create job", exc)


@bp.patch("/<job_id>")
def update_job(job_id: str):
    email, error = _account()
    if error:
        return error
    payload = _json_payload()
    row, validation_error = _job_row(payload, email, partial=True)
    row.pop("owner_email", None)
    row.pop("is_curated", None)
    if validation_error:
        return jsonify({"ok": False, "error": validation_error}), 400
    try:
        if not _owned_row("relocation_jobs", job_id, email):
            return jsonify({"ok": False, "error": "job_not_found_or_not_editable"}), 404
        response = get_supabase().table("relocation_jobs").update(row).eq("id", job_id).eq("owner_email", email).execute()
        job = (response.data or [None])[0]
        return jsonify({"ok": True, "job": rank_jobs([job], _profile(email))[0]})
    except Exception as exc:
        return _database_error("update job", exc)


@bp.get("/applications")
def list_job_applications():
    email, error = _account()
    if error:
        return error
    try:
        rows = (
            get_supabase().table("relocation_job_applications")
            .select("*")
            .eq("email", email)
            .order("updated_at", desc=True)
            .execute()
        ).data or []
        status = _text(request.args.get("status"), 40)
        if status:
            rows = [row for row in rows if row.get("status") == status]
        return jsonify({"ok": True, "applications": rows, "count": len(rows)})
    except Exception as exc:
        return _database_error("list job applications", exc)


def _application_row(payload: Dict[str, Any], email: str, partial: bool = False) -> Tuple[Dict[str, Any], Optional[str]]:
    row: Dict[str, Any] = {"email": email}
    for field, limit in (("job_title", 220), ("company_name", 180), ("country", 100), ("province", 100), ("notes", 4000)):
        if field in payload:
            row[field] = _text(payload.get(field), limit)
    if not partial and not row.get("job_title") and not payload.get("job_id"):
        return {}, "job_title_or_job_id_required"
    if "job_url" in payload:
        job_url = _url(payload.get("job_url"))
        if payload.get("job_url") and not job_url:
            return {}, "invalid_job_url"
        row["job_url"] = job_url
    for field in ("job_id", "company_id", "recruiter_id"):
        if field in payload:
            row[field] = _text(payload.get(field), 80)
    if "status" in payload:
        status = _text(payload.get("status"), 40)
        if status not in APPLICATION_STATUSES:
            return {}, "invalid_application_status"
        row["status"] = status
    for field in ("date_applied", "follow_up_date"):
        if field in payload:
            row[field] = _date(payload.get(field))
    if "interview_date" in payload:
        row["interview_date"] = _datetime(payload.get("interview_date"))
    if "documents_used" in payload:
        documents = payload.get("documents_used")
        if not isinstance(documents, list):
            return {}, "documents_used_must_be_an_array"
        row["documents_used"] = documents
    return row, None


def _resolve_application_links(row: Dict[str, Any], email: str) -> Tuple[Dict[str, Any], Optional[str]]:
    if row.get("job_id"):
        job = _owned_row("relocation_jobs", str(row["job_id"]), email)
        if not job:
            return row, "job_not_found"
        row.setdefault("job_title", job.get("job_title"))
        row.setdefault("country", job.get("country"))
        row.setdefault("province", job.get("province"))
        row.setdefault("job_url", job.get("job_url"))
        row.setdefault("company_id", job.get("company_id"))
        row.setdefault("recruiter_id", job.get("recruiter_id"))
    if row.get("company_id"):
        company = _visible_company(str(row["company_id"]), email)
        if not company:
            return row, "company_not_found"
        row.setdefault("company_name", company.get("company_name"))
    if row.get("recruiter_id") and not _owned_row("relocation_job_recruiters", str(row["recruiter_id"]), email):
        return row, "recruiter_not_found"
    if not row.get("job_title") or not row.get("company_name"):
        return row, "job_title_and_company_name_required"
    documents, document_error = _validate_documents(email, row.get("documents_used") or [])
    if document_error:
        return row, document_error
    row["documents_used"] = documents
    status = row.get("status") or "saved"
    if status in {"applied", "interview", "rejected", "offer", "visa"} and not row.get("date_applied"):
        row["date_applied"] = date.today().isoformat()
    return row, None


@bp.post("/applications")
def create_job_application():
    email, error = _account()
    if error:
        return error
    row, validation_error = _application_row(_json_payload(), email)
    if validation_error:
        return jsonify({"ok": False, "error": validation_error}), 400
    try:
        row, link_error = _resolve_application_links(row, email)
        if link_error:
            return jsonify({"ok": False, "error": link_error}), 400
        row.setdefault("country", "Canada")
        response = get_supabase().table("relocation_job_applications").insert(row).execute()
        if row.get("company_id"):
            get_supabase().table("relocation_job_company_targets").upsert({
                "email": email,
                "company_id": row["company_id"],
                "priority": "high",
                "status": "applied" if row.get("status") != "saved" else "targeting",
            }, on_conflict="email,company_id").execute()
        return jsonify({"ok": True, "application": (response.data or [None])[0]}), 201
    except Exception as exc:
        return _database_error("create job application", exc)


@bp.patch("/applications/<application_id>")
def update_job_application(application_id: str):
    email, error = _account()
    if error:
        return error
    row, validation_error = _application_row(_json_payload(), email, partial=True)
    row.pop("email", None)
    if validation_error:
        return jsonify({"ok": False, "error": validation_error}), 400
    try:
        existing = _owned_row("relocation_job_applications", application_id, email)
        if not existing:
            return jsonify({"ok": False, "error": "application_not_found"}), 404
        merged = {**existing, **row}
        resolved, link_error = _resolve_application_links(merged, email)
        if link_error:
            return jsonify({"ok": False, "error": link_error}), 400
        update_fields = {key: value for key, value in resolved.items() if key in {
            "job_id", "company_id", "recruiter_id", "job_title", "company_name", "country", "province",
            "job_url", "status", "date_applied", "follow_up_date", "interview_date", "documents_used", "notes",
        }}
        response = (
            get_supabase().table("relocation_job_applications")
            .update(update_fields).eq("id", application_id).eq("email", email).execute()
        )
        return jsonify({"ok": True, "application": (response.data or [None])[0]})
    except Exception as exc:
        return _database_error("update job application", exc)


@bp.get("/resume-vault")
def list_resume_assets():
    email, error = _account()
    if error:
        return error
    try:
        rows = (
            get_supabase().table("relocation_job_resume_assets")
            .select("id,document_type,title,original_file_name,mime_type,size_bytes,version,is_active,notes,created_at,updated_at")
            .eq("email", email)
            .order("updated_at", desc=True)
            .execute()
        ).data or []
        return jsonify({"ok": True, "documents": rows, "count": len(rows), "max_file_bytes": MAX_RESUME_BYTES})
    except Exception as exc:
        return _database_error("list resume assets", exc)


@bp.post("/resume-vault")
def upload_resume_asset():
    email, error = _account()
    if error:
        return error
    uploaded = request.files.get("file")
    document_type = _text(request.form.get("document_type"), 80)
    title = _text(request.form.get("title"), 180)
    notes = _text(request.form.get("notes"), 2000)
    if document_type not in DOCUMENT_TYPES:
        return jsonify({"ok": False, "error": "invalid_document_type"}), 400
    if not uploaded or not uploaded.filename:
        return jsonify({"ok": False, "error": "resume_file_required"}), 400
    mime_type = str(uploaded.mimetype or "").lower()
    if mime_type not in ALLOWED_RESUME_MIME_TYPES:
        return jsonify({"ok": False, "error": "unsupported_resume_file_type", "allowed": sorted(ALLOWED_RESUME_MIME_TYPES)}), 400
    contents = uploaded.stream.read(MAX_RESUME_BYTES + 1)
    if not contents or len(contents) > MAX_RESUME_BYTES:
        return jsonify({"ok": False, "error": "resume_file_must_be_between_1_byte_and_5_mb"}), 400
    file_name = secure_filename(uploaded.filename)[:180] or "resume-file"
    account_key = hashlib.sha256(email.encode("utf-8")).hexdigest()[:20]
    storage_path = f"{account_key}/{secrets.token_hex(16)}/{file_name}"
    supabase = get_supabase()
    try:
        latest = (
            supabase.table("relocation_job_resume_assets")
            .select("version")
            .eq("email", email)
            .eq("document_type", document_type)
            .order("version", desc=True)
            .limit(1)
            .execute()
        ).data or []
        version = int(latest[0].get("version") or 0) + 1 if latest else 1
        supabase.storage.from_(RESUME_BUCKET).upload(
            path=storage_path,
            file=contents,
            file_options={"content-type": mime_type, "upsert": "false"},
        )
        try:
            response = supabase.table("relocation_job_resume_assets").insert({
                "email": email,
                "document_type": document_type,
                "title": title or f"{document_type.replace('_', ' ').title()} v{version}",
                "original_file_name": file_name,
                "mime_type": mime_type,
                "size_bytes": len(contents),
                "storage_bucket": RESUME_BUCKET,
                "storage_path": storage_path,
                "version": version,
                "is_active": True,
                "notes": notes,
            }).execute()
        except Exception:
            try:
                supabase.storage.from_(RESUME_BUCKET).remove([storage_path])
            finally:
                raise
        document = (response.data or [None])[0]
        return jsonify({"ok": True, "document": {key: value for key, value in document.items() if key not in {"email", "storage_bucket", "storage_path"}}}), 201
    except Exception as exc:
        return _database_error("upload resume asset", exc)


@bp.patch("/resume-vault/<document_id>")
def update_resume_asset(document_id: str):
    email, error = _account()
    if error:
        return error
    payload = _json_payload()
    row: Dict[str, Any] = {}
    if "title" in payload:
        row["title"] = _text(payload.get("title"), 180)
        if not row["title"]:
            return jsonify({"ok": False, "error": "document_title_required"}), 400
    if "notes" in payload:
        row["notes"] = _text(payload.get("notes"), 2000)
    if "is_active" in payload:
        row["is_active"] = _bool(payload.get("is_active"))
    if not row:
        return jsonify({"ok": False, "error": "no_supported_fields_supplied"}), 400
    try:
        existing = _owned_row("relocation_job_resume_assets", document_id, email)
        if not existing:
            return jsonify({"ok": False, "error": "resume_document_not_found"}), 404
        response = (
            get_supabase().table("relocation_job_resume_assets")
            .update(row).eq("id", document_id).eq("email", email).execute()
        )
        document = (response.data or [None])[0]
        return jsonify({"ok": True, "document": {key: value for key, value in document.items() if key not in {"email", "storage_bucket", "storage_path"}}})
    except Exception as exc:
        return _database_error("update resume asset", exc)


@bp.get("/resume-vault/<document_id>/download")
def download_resume_asset(document_id: str):
    email, error = _account()
    if error:
        return error
    try:
        row = _owned_row("relocation_job_resume_assets", document_id, email)
        if not row:
            return jsonify({"ok": False, "error": "resume_document_not_found"}), 404
        signed = get_supabase().storage.from_(str(row.get("storage_bucket") or RESUME_BUCKET)).create_signed_url(str(row.get("storage_path")), 120)
        signed_url = signed.get("signedURL") or signed.get("signedUrl") or signed.get("signed_url")
        if not signed_url:
            raise RuntimeError("Storage provider did not return a signed URL")
        return jsonify({"ok": True, "download_url": signed_url, "expires_in_seconds": 120, "file_name": row.get("original_file_name")})
    except Exception as exc:
        return _database_error("sign resume download", exc)
