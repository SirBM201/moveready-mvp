from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    target = ROOT / path
    if not target.is_file():
        raise AssertionError(f"Missing required B16 file: {path}")
    return target.read_text(encoding="utf-8")


def validate_migration_ledger() -> None:
    ledger = json.loads(read("docs/MIGRATION_LEDGER.json"))
    assert ledger["ledger_version"] == "b16-v1"

    actual_schema = sorted(path.name for path in (ROOT / "supabase/migrations").glob("*.sql"))
    actual_legacy = sorted(path.name for path in (ROOT / "sql").glob("*.sql"))
    assert actual_schema, "No canonical migrations found"
    assert ledger["latest_schema_file"] == actual_schema[-1], "Migration ledger latest_schema_file is stale"
    assert sorted(ledger["canonical_schema_files"]) == actual_schema, "Migration ledger and supabase/migrations differ"
    assert sorted(ledger["legacy_sql_only_files"]) == actual_legacy, "Migration ledger and legacy sql directory differ"

    empty = [
        str(path.relative_to(ROOT))
        for directory in (ROOT / "supabase/migrations", ROOT / "sql")
        for path in directory.glob("*.sql")
        if not path.read_text(encoding="utf-8").strip()
    ]
    assert not empty, f"Empty SQL files: {empty}"

    prefixes: dict[str, list[str]] = {}
    for name in actual_schema:
        match = re.match(r"^(\d{3})_[A-Za-z0-9_-]+\.sql$", name)
        assert match, f"Invalid migration filename: {name}"
        prefixes.setdefault(match.group(1), []).append(name)
    duplicates = {key: value for key, value in prefixes.items() if len(value) > 1}
    assert duplicates == ledger["intentional_prefix_exceptions"]["duplicate_historical_prefixes"]


def validate_environment_example() -> None:
    text = read(".env.example")
    sensitive = {
        "SECRET_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
        "OPENAI_API_KEY",
        "MOVEREADY_ADMIN_API_KEY",
        "MOVE_READY_ADMIN_API_KEY",
        "ADMIN_API_KEY",
        "MAILTRAP_API_TOKEN",
        "MAILTRAP_SANDBOX_API_TOKEN",
        "RESEND_API_KEY",
        "SMTP_PASSWORD",
        "PASSPORT_INDEX_PROVIDER_KEY",
    }
    assignments = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        assignments[key.strip()] = value.strip()
    for key in sensitive:
        assert assignments.get(key, "") in {"", "change-me"}, f"{key} must be blank in .env.example"
    assert assignments.get("AUTH_OTP_DEV_MODE") == "false"


def validate_secret_guardrails() -> None:
    strong_patterns = [
        re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
        re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{24,}"),
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    ]
    candidates = [
        ROOT / ".env.example",
        *ROOT.glob("app/**/*.py"),
        *ROOT.glob("scripts/*"),
        *ROOT.glob(".github/workflows/*.yml"),
    ]
    findings = []
    for path in candidates:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in strong_patterns:
            if pattern.search(text):
                findings.append(f"{path.relative_to(ROOT)}:{pattern.pattern}")
    assert not findings, f"Potential committed secret material: {findings}"


def validate_admin_boundary() -> None:
    auth = read("app/utils/admin_auth.py")
    assert "hmac.compare_digest" in auth
    assert 'request.headers.get("X-MoveReady-Admin-Key")' in auth
    assert 'config.ENV_MODE.lower() == "development"' in auth
    assert "_moveready_admin_protected" in auth
    assert 'request.headers.get("X-Admin-Key")' not in auth


def validate_deployment_and_schedules() -> None:
    railway = json.loads(read("railway.json"))
    deploy = railway["deploy"]
    assert deploy["healthcheckPath"] == "/health"
    assert "gunicorn" in deploy["startCommand"]
    assert deploy["restartPolicyType"] == "ON_FAILURE"

    expected = {
        "job-monitoring-schedule.yml": ("17 5 * * *", "/api/admin/jobs/automation/scheduled-scan"),
        "passport-index-weekly-sync.yml": ("17 6 * * 5", "/api/visa-power/provider/scheduled-sync"),
        "source-governance-weekly.yml": ("47 6 * * 1", "/api/admin/source-governance/scan-due"),
        "application-case-alerts-daily.yml": ("7 7 * * *", "/api/admin/application-cases/alerts/scan"),
    }
    for name, (cron, endpoint) in expected.items():
        workflow = read(f".github/workflows/{name}")
        assert cron in workflow, (name, cron)
        assert endpoint in workflow, (name, endpoint)
        assert "b16-v1" in workflow, f"{name} must fail closed on an older Railway contract"
        assert "secrets.MOVEREADY_ADMIN_KEY" in workflow
        assert "issues: write" in workflow
        assert "Open or update failure issue" in workflow
    assert not (ROOT / ".github/workflows/passport-index-sync.yml").exists(), "Duplicate Passport Index scheduler must be retired"


def validate_contract_and_runbook() -> None:
    contract = read("app/core/operations_readiness.py")
    health = read("app/routes/health.py")
    runbook = read("docs/B16_DEPLOYMENT_OPERATIONS.md")
    assert 'OPERATIONS_CONTRACT_VERSION = "b16-v1"' in contract
    assert '"operations":"b16-v1"' in health.replace(" ", "")
    for term in ["Railway", "Vercel", "Supabase", "Scheduled jobs", "Rollback", "secret exposure", "B17"]:
        assert term.lower() in runbook.lower(), term


def main() -> None:
    validate_migration_ledger()
    validate_environment_example()
    validate_secret_guardrails()
    validate_admin_boundary()
    validate_deployment_and_schedules()
    validate_contract_and_runbook()
    print("B16 deployment and operations repository contract: PASS")


if __name__ == "__main__":
    main()
