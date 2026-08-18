from __future__ import annotations

from flask import Flask, jsonify

from app import create_app
from app.core import config
from app.core.operations_readiness import (
    ADMIN_HEADER_NAME,
    OPERATIONS_CONTRACT_VERSION,
    SCHEDULE_CONTRACTS,
    admin_route_contract,
    environment_checks,
    environment_summary,
)
from app.utils.admin_auth import require_admin_access


def test_build_info_exposes_sanitized_b16_contract() -> None:
    app = create_app()
    client = app.test_client()
    response = client.get("/api/build-info")
    assert response.status_code == 200
    payload = response.get_json()

    assert payload["contract_versions"]["operations"] == OPERATIONS_CONTRACT_VERSION
    assert payload["route_contract"]["ok"] is True
    contract = payload["operations_contract"]
    assert contract["version"] == "b16-v1"
    assert contract["schedule_count"] == 4
    assert {item["code"] for item in contract["schedules"]} == {
        "job_monitoring",
        "passport_index",
        "source_governance",
        "application_alerts",
    }
    assert contract["admin_boundary"]["ok"] is True
    assert contract["admin_boundary"]["unprotected_routes"] == []

    rendered = response.get_data(as_text=True)
    for secret_value in [
        config.SECRET_KEY,
        config.SUPABASE_SERVICE_ROLE_KEY,
        config.ADMIN_API_KEY,
        config.PASSPORT_INDEX_PROVIDER_KEY,
    ]:
        if secret_value:
            assert secret_value not in rendered


def test_every_admin_route_has_the_protection_marker() -> None:
    app = create_app()
    contract = admin_route_contract(app)
    assert contract["protected_route_count"] >= 30
    assert contract["ok"] is True
    assert contract["unprotected_routes"] == []


def test_admin_auth_uses_canonical_header_and_constant_time_comparison(monkeypatch) -> None:
    monkeypatch.setattr(config, "ADMIN_API_KEY", "b16-admin-test-key")
    monkeypatch.setattr(config, "ENV_MODE", "production")
    app = Flask(__name__)

    @app.get("/protected")
    @require_admin_access
    def protected():
        return jsonify({"ok": True})

    client = app.test_client()
    assert client.get("/protected").status_code == 401
    assert client.get("/protected", headers={"X-Admin-Key": "b16-admin-test-key"}).status_code == 401
    assert client.get("/protected", headers={ADMIN_HEADER_NAME: "wrong"}).status_code == 401
    assert client.get("/protected", headers={ADMIN_HEADER_NAME: "b16-admin-test-key"}).status_code == 200


def test_environment_validation_is_explicit_and_secret_free(monkeypatch) -> None:
    monkeypatch.setattr(config, "ENV_MODE", "production")
    monkeypatch.setattr(config, "FLASK_ENV", "production")
    monkeypatch.setattr(config, "SECRET_KEY", "never-return-secret")
    monkeypatch.setattr(config, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(config, "SUPABASE_SERVICE_ROLE_KEY", "never-return-service-role")
    monkeypatch.setattr(config, "ADMIN_API_KEY", "never-return-admin-key")
    monkeypatch.setattr(config, "CORS_ORIGINS", "https://example.vercel.app")
    monkeypatch.setattr(config, "AUTH_OTP_DEV_MODE", False)
    monkeypatch.setattr(config, "PASSPORT_INDEX_PROVIDER_ENABLED", False)
    monkeypatch.setattr(config, "PAYMENT_LINKS_ENABLED", False)

    checks = environment_checks({"enabled": False, "configured": False})
    summary = environment_summary(checks)
    assert summary["production_runtime"] is True
    assert summary["status"] == "ready"
    text = str(checks) + str(summary)
    for secret in ["never-return-secret", "never-return-service-role", "never-return-admin-key"]:
        assert secret not in text


def test_schedule_contracts_are_unique() -> None:
    assert len(SCHEDULE_CONTRACTS) == 4
    assert len({item["workflow"] for item in SCHEDULE_CONTRACTS}) == 4
    assert len({item["cron"] for item in SCHEDULE_CONTRACTS}) == 4
