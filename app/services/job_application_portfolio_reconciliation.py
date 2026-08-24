from __future__ import annotations

from typing import Any, Iterable, Mapping

from app.services.job_application_followup_reconciliation import terminal_followup_updates

CONTRACT_VERSION = "b19.8.4-v1"
ALLOWED_OPERATIONS = frozenset({"supersede_terminal_followups"})


def build_corrective_plan(*, lifecycle: Mapping[str, Any] | None, followups: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    state = str((lifecycle or {}).get("state") or "").strip().lower()
    rows = list(followups)
    updates = terminal_followup_updates(rows, state)
    operations = []
    if updates:
        operations.append({
            "operation": "supersede_terminal_followups",
            "lifecycle_id": (lifecycle or {}).get("id"),
            "followup_updates": updates,
            "requires_user_confirmation": False,
            "reason": "terminal_lifecycle_cannot_retain_active_followups",
        })
    return {"contract_version": CONTRACT_VERSION, "operations": operations, "safe_to_execute": all(op["operation"] in ALLOWED_OPERATIONS for op in operations)}


def validate_corrective_operation(operation: Mapping[str, Any]) -> dict[str, Any]:
    name = str(operation.get("operation") or "")
    if name not in ALLOWED_OPERATIONS:
        return {"ok": False, "error": "portfolio_corrective_operation_not_allowed", "contract_version": CONTRACT_VERSION}
    updates = operation.get("followup_updates")
    if not isinstance(updates, dict) or not updates:
        return {"ok": False, "error": "followup_updates_required", "contract_version": CONTRACT_VERSION}
    if any(status != "superseded" for status in updates.values()):
        return {"ok": False, "error": "unsafe_followup_target_status", "contract_version": CONTRACT_VERSION}
    return {"ok": True, "contract_version": CONTRACT_VERSION}
