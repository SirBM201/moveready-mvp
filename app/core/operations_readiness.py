from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List

from app.core import config


OPERATIONS_CONTRACT_VERSION = "b16-v1"
ADMIN_HEADER_NAME = "X-MoveReady-Admin-Key"
MIGRATION_LEDGER_PATH = Path(__file__).resolve().parents[2] / "docs" / "MIGRATION_LEDGER.json"

SCHEDULE_CONTRACTS = [
    {
        "code": "job_monitoring",
        "workflow": "job-monitoring-schedule.yml",
        "cadence": "daily",
        "cron": "17 5 * * *",
        "endpoint": "/api/admin/jobs/automation/scheduled-scan",
        "effect": "private in-app job monitoring records only",
    },
    {
        "code": "passport_index",
        "workflow": "passport-index-weekly-sync.yml",
        "cadence": "weekly",
        "cron": "17 6 * * 5",
        "endpoint": "/api/visa-power/provider/scheduled-sync",
        "effect": "bounded provider-cache refresh",
    },
    {
        "code": "source_governance",
        "workflow": "source-governance-weekly.yml",
        "cadence": "weekly",
        "cron": "47 6 * * 1",
        "endpoint": "/api/admin/source-governance/scan-due",
        "effect": "review-due alerts; route facts are not changed automatically",
    },
    {
        "code": "application_alerts",
        "workflow": "application-case-alerts-daily.yml",
        "cadence": "daily",
        "cron": "7 7 * * *",
        "endpoint": "/api/admin/application-cases/alerts/scan",
        "effect": "private in-app application alerts only",
    },
]


def _production_runtime() -> bool:
    mode = (config.ENV_MODE or "").strip().lower()
    flask_mode = (config.FLASK_ENV or "").strip().lower()
    return bool(os.getenv("RAILWAY_ENVIRONMENT_ID")) or mode in {"prod", "production"} or flask_mode == "production"


def _check(code: str, ready: bool, severity: str, detail: str) -> Dict[str, Any]:
    return {
        "code": code,
        "ready": bool(ready),
        "severity": severity,
        "status": "ready" if ready else ("blocked" if severity == "critical" else "controlled_rollout"),
        "detail": detail,
    }


def environment_checks(email_status: Dict[str, Any]) -> List[Dict[str, Any]]:
    production = _production_runtime()
    cors = (config.CORS_ORIGINS or "").strip()
    checks = [
        _check("secret_key", bool(config.SECRET_KEY), "critical", "A non-empty server session secret is configured."),
        _check(
            "supabase_server_credentials",
            bool(config.SUPABASE_URL and config.SUPABASE_SERVICE_ROLE_KEY),
            "critical",
            "Supabase URL and server-only service-role credentials are configured.",
        ),
        _check(
            "admin_key",
            bool(config.ADMIN_API_KEY),
            "critical",
            f"Protected operations use only the {ADMIN_HEADER_NAME} request header in production.",
        ),
        _check(
            "cors_policy",
            bool(cors) and (not production or cors != "*"),
            "critical",
            "Production CORS uses an explicit frontend origin allow-list rather than a wildcard.",
        ),
        _check(
            "otp_development_mode",
            not (production and config.AUTH_OTP_DEV_MODE),
            "critical",
            "Development OTP bypass is disabled outside development.",
        ),
        _check(
            "email_otp_provider",
            not email_status.get("enabled") or bool(email_status.get("configured")),
            "critical",
            "Email OTP is either disabled for controlled rollout or fully configured.",
        ),
        _check(
            "passport_provider",
            not config.PASSPORT_INDEX_PROVIDER_ENABLED
            or bool(config.PASSPORT_INDEX_PROVIDER_URL and config.PASSPORT_INDEX_PROVIDER_KEY),
            "optional",
            "Passport provider sync remains fail-closed unless its URL and server-only key are configured.",
        ),
        _check(
            "payment_boundary",
            not config.PAYMENT_LINKS_ENABLED or config.COMMERCIAL_QUOTES_ENABLED,
            "critical",
            "Payment links cannot be enabled unless the controlled commercial-quote workflow is enabled.",
        ),
    ]
    return checks


def environment_summary(checks: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    items = list(checks)
    blocked = [item["code"] for item in items if not item["ready"] and item["severity"] == "critical"]
    controlled = [item["code"] for item in items if not item["ready"] and item["severity"] != "critical"]
    return {
        "status": "blocked" if blocked else ("controlled_rollout" if controlled else "ready"),
        "production_runtime": _production_runtime(),
        "check_count": len(items),
        "blocked_checks": blocked,
        "controlled_checks": controlled,
    }



def migration_ledger_contract() -> Dict[str, Any]:
    """Return the repository migration frontier without pinning release numbers in code."""
    try:
        ledger = json.loads(MIGRATION_LEDGER_PATH.read_text(encoding="utf-8"))
        latest = str(ledger.get("latest_schema_file") or "").strip()
        confirmation = ledger.get("production_confirmation") or {}
        confirmed = str(confirmation.get("manually_confirmed_frontier") or "").strip()
        if not latest:
            raise ValueError("latest_schema_file is missing")
        return {
            "version": str(ledger.get("ledger_version") or OPERATIONS_CONTRACT_VERSION),
            "latest_schema_file": latest,
            "manually_confirmed_frontier": confirmed or None,
            "frontier_matches": bool(confirmed and confirmed == latest),
            "source": "docs/MIGRATION_LEDGER.json",
            "status": "confirmed" if confirmed and confirmed == latest else "verification_required",
            "database_history_note": "Protected schema checks remain authoritative; the repository ledger does not replace Supabase history.",
        }
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return {
            "version": OPERATIONS_CONTRACT_VERSION,
            "latest_schema_file": None,
            "manually_confirmed_frontier": None,
            "frontier_matches": False,
            "source": "docs/MIGRATION_LEDGER.json",
            "status": "unavailable",
            "error": f"{type(exc).__name__}: {exc}",
            "database_history_note": "Migration ledger unavailable; verify Supabase history before launch.",
        }

def operations_contract_payload() -> Dict[str, Any]:
    return {
        "version": OPERATIONS_CONTRACT_VERSION,
        "deployment_targets": {
            "backend": "Railway",
            "frontend": "Vercel",
            "database": "Supabase",
        },
        "admin_boundary": {
            "path_prefix": "/api/admin",
            "header": ADMIN_HEADER_NAME,
            "comparison": "constant_time",
            "browser_storage": "session_only; never localStorage",
        },
        "schedule_count": len(SCHEDULE_CONTRACTS),
        "schedules": SCHEDULE_CONTRACTS,
        "migration_ledger": migration_ledger_contract(),
        "rollback_policy": "Application deployments may roll back to a previously verified commit. Applied Supabase migrations use forward repair unless a reviewed backup-restore plan explicitly authorizes otherwise.",
    }


def admin_route_contract(app: Any) -> Dict[str, Any]:
    protected: List[str] = []
    missing: List[str] = []
    for rule in app.url_map.iter_rules():
        if not rule.rule.startswith("/api/admin"):
            continue
        view = app.view_functions.get(rule.endpoint)
        if view is not None and getattr(view, "_moveready_admin_protected", False):
            protected.append(rule.rule)
        else:
            missing.append(rule.rule)
    return {
        "ok": not missing,
        "protected_route_count": len(set(protected)),
        "unprotected_routes": sorted(set(missing)),
    }
