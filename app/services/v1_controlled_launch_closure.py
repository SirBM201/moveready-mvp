from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

CONTRACT_VERSION = "lq21.1-v1"


def build_controlled_launch_closure(*, route_contract: Mapping[str, Any], admin_contract: Mapping[str, Any], migration_ledger: Mapping[str, Any], environment: Mapping[str, Any], email_otp_enabled: bool, payment_links_enabled: bool, external_alerts_enabled: bool) -> dict[str, Any]:
    automated = [
        {"key": "routes", "label": "V1 backend routes", "passed": route_contract.get("ok") is True, "evidence": f"{route_contract.get('expected_count', 0)} expected; {len(route_contract.get('missing_routes') or [])} missing"},
        {"key": "admin_boundary", "label": "Administrator boundary", "passed": admin_contract.get("ok") is True, "evidence": f"{admin_contract.get('protected_route_count', 0)} protected; {len(admin_contract.get('unprotected_routes') or [])} unprotected"},
        {"key": "environment", "label": "Production environment", "passed": environment.get("status") == "ready", "evidence": str(environment.get("status") or "unavailable")},
        {"key": "migration", "label": "Migration ledger", "passed": migration_ledger.get("frontier_matches") is True, "evidence": str(migration_ledger.get("latest_schema_file") or "unavailable")},
        {"key": "payment_boundary", "label": "Payments remain outside V1", "passed": not payment_links_enabled, "evidence": "disabled" if not payment_links_enabled else "unexpectedly enabled"},
        {"key": "external_alert_boundary", "label": "External alerts remain outside V1", "passed": not external_alerts_enabled, "evidence": "disabled" if not external_alerts_enabled else "unexpectedly enabled"},
    ]
    manual = [
        {"key": "otp_receipt", "label": "One-time email sign-in", "status": "ready_to_test" if email_otp_enabled else "blocked", "instruction": "A tester must request and enter their own six-digit OTP; never record it in a report."},
        {"key": "authenticated_journey", "label": "Authenticated V1 journey", "status": "manual_required", "instruction": "Complete Set target → Find → Qualify → Execute → Move using controlled records; do not submit a real application."},
        {"key": "mobile_keyboard", "label": "Mobile and keyboard", "status": "manual_required", "instruction": "Verify 320/375/420 px layouts and keyboard-only traversal."},
        {"key": "controlled_cohort", "label": "Controlled launch cohort", "status": "manual_required", "instruction": "Record product usability only; no immigration, employment, or approval outcome."},
    ]
    automated_ready = all(item["passed"] for item in automated)
    return {
        "ok": automated_ready,
        "contract_version": CONTRACT_VERSION,
        "scope": "v1_controlled_launch_only",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "decision": "controlled_launch_eligible" if automated_ready and email_otp_enabled else "hold_controlled_launch",
        "automated_gates": automated,
        "manual_gates": manual,
        "broad_public_launch_approved": False,
        "support": {"user_path": "/support-center", "status_path": "/deployment-status", "beta_path": "/beta"},
        "rollback": {"application": "Redeploy the last verified main commit.", "database": "Use forward repair unless an approved backup-restore plan exists."},
        "excluded_from_v1": ["payments", "real_notification_delivery", "provider_network", "marketplace", "document_vault", "student_admission_expansion", "travel_booking", "automatic_application_submission", "new_ai_modules"],
        "safety": {"read_only": True, "otp_requested": False, "record_mutated": False, "external_action_performed": False},
    }
