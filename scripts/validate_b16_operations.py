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
    # B16 established the ledger contract, but the ledger version advances as
    # later development stages add reviewed migrations. Validate the version
    # shape rather than pinning all future releases to the original b16-v1.
    ledger_version = str(ledger.get("ledger_version") or "")
    assert re.fullmatch(r"b\d+(?:\.\d+)*-v\d+", ledger_version), "Invalid migration ledger version"

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


def validate_operations_contract() -> None:
    # The B16 operations service was consolidated into the core readiness
    # contract. Validate the live architecture instead of requiring the
    # retired app/services/operations.py path.
    source = read("app/core/operations_readiness.py")
    required = [
        "deployment",
        "migration",
        "rollback",
        "environment",
    ]
    for marker in required:
        assert marker in source.lower(), f"Missing operations marker: {marker}"
    assert "operations_contract_payload" in source
    assert "environment_checks" in source


def validate_operations_routes() -> None:
    source = read("app/routes/operations.py")
    assert "Blueprint" in source
    assert "operations" in source.lower()
    assert "operations_contract_payload" in source


def validate_app_registration() -> None:
    source = read("app/__init__.py")
    assert "operations.public_bp" in source
    assert "operations.admin_bp" in source


def validate_b16_tests_exist() -> None:
    tests = [path.name for path in (ROOT / "tests").glob("*operations*")]
    assert tests, "B16 operations regression tests are missing"


def validate_safety_boundary() -> None:
    combined = "\n".join(
        read(path)
        for path in [
            "app/core/operations_readiness.py",
            "app/routes/operations.py",
        ]
    ).lower()
    # Operational observability must not turn into arbitrary remote execution.
    forbidden = ["subprocess.popen(", "os.system(", "eval(", "exec("]
    for marker in forbidden:
        assert marker not in combined, f"Unsafe operations capability found: {marker}"


def main() -> None:
    validate_migration_ledger()
    validate_operations_contract()
    validate_operations_routes()
    validate_app_registration()
    validate_b16_tests_exist()
    validate_safety_boundary()
    print("B16 operations foundation validated")


if __name__ == "__main__":
    main()
