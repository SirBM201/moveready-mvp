from __future__ import annotations

from flask import Blueprint, jsonify

from app.services.sparkgrowth_telemetry import probe_contract, telemetry_configured

bp = Blueprint("growth_telemetry", __name__)


@bp.get("/health")
def health():
    probe = probe_contract() if telemetry_configured() else {"ok": False, "reason": "not_configured"}
    return jsonify(
        {
            "ok": True,
            "telemetry_configured": telemetry_configured(),
            "upstream_contract_ok": bool(probe.get("ok")),
            "workspace_id": probe.get("workspace_id"),
            "idempotency_required": probe.get("idempotency_required"),
        }
    )
