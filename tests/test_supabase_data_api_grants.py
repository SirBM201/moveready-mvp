from pathlib import Path
import re

MIGRATIONS = Path(__file__).resolve().parents[1] / "supabase" / "migrations"
CREATE_TABLE = re.compile(r"\bcreate\s+table\b", re.IGNORECASE)
EXPLICIT_ACCESS = re.compile(r"\b(?:grant|revoke)\b[\s\S]*?\bon\s+(?:table\s+)?public\.", re.IGNORECASE)

def test_new_table_migrations_declare_data_api_access():
    """New public tables must make Data API exposure an explicit code decision."""
    for path in sorted(MIGRATIONS.glob("*.sql")):
        # Historical migrations predate the Supabase 2026 explicit-grant rollout.
        # Do not rewrite migration history; enforce the contract from this guard onward.
        if path.name < "057_":
            continue
        sql = path.read_text(encoding="utf-8")
        if CREATE_TABLE.search(sql):
            assert EXPLICIT_ACCESS.search(sql), (
                f"{path.name} creates a public table without an explicit GRANT/REVOKE. "
                "Declare the intended anon/authenticated/service_role access in the same migration."
            )

def test_launch_beta_grants_only_operations_used_by_the_api():
    """LQ12 needs reads and report inserts; its backend has no update/delete path."""
    sql = (MIGRATIONS / "057_supabase_explicit_data_api_grants.sql").read_text(encoding="utf-8")
    normalized = re.sub(r"\s+", " ", sql.lower())
    assert "alter table if exists public.relocation_launch_beta_reports enable row level security" in normalized
    assert (
        "revoke all privileges on table public.relocation_launch_beta_reports "
        "from public, anon, authenticated, service_role"
    ) in normalized
    assert (
        "grant select, insert on table public.relocation_launch_beta_reports "
        "to service_role"
    ) in normalized
    grant_statements = re.findall(r"\bgrant\b([^;]*);", normalized)
    assert len(grant_statements) == 1
    assert "update" not in grant_statements[0]
    assert "delete" not in grant_statements[0]
