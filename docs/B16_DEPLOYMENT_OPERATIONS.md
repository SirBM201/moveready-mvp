# B16 — Deployment and operations hardening

## Release contract

B16 fixes the operational contract for the three production systems:

- Railway runs the Flask backend and exposes `/health`, `/api/health`, `/api/build-info`, and the protected operations diagnostics.
- Vercel runs the Next.js frontend and exposes a sanitized frontend build fingerprint.
- Supabase stores the controlled schema. `docs/MIGRATION_LEDGER.json` inventories every repository SQL file without pretending to replace database history.

`/api/build-info` must report `contract_versions.operations = b16-v1`, a passing route contract, a passing admin-boundary contract, four scheduled-job contracts, and the Railway commit SHA before production is treated as current.

## Canonical environment names

| Location | Name | Purpose |
| --- | --- | --- |
| Railway | `SECRET_KEY` | Server session signing; never public |
| Railway | `SUPABASE_URL` | Supabase project URL |
| Railway | `SUPABASE_SERVICE_ROLE_KEY` | Server-only database access |
| Railway | `MOVEREADY_ADMIN_API_KEY` | Protected backend operations |
| Railway | `CORS_ORIGINS` | Comma-separated Vercel production origins; never `*` in production |
| Railway | `AUTH_OTP_DEV_MODE=false` | Prevent development-code authentication in production |
| GitHub Actions | `MOVEREADY_ADMIN_KEY` | Same value as Railway `MOVEREADY_ADMIN_API_KEY` |
| GitHub Actions | `MOVEREADY_API_BASE` | Optional repository variable for the Railway base URL |
| Vercel | `NEXT_PUBLIC_BACKEND_URL` | Public HTTPS Railway base URL used by Next.js rewrites |

Do not put an admin key, Supabase service-role key, email-provider token, SMTP password, or payment secret in any `NEXT_PUBLIC_*` variable. Do not paste these values into chat, screenshots, issues, workflow summaries, logs, or repository files.

## Scheduled jobs

| Workflow | UTC schedule | Protected endpoint | Boundary |
| --- | --- | --- | --- |
| Official job monitoring | Daily 05:17 | `/api/admin/jobs/automation/scheduled-scan` | Official employer/supported ATS records; no auto-submit |
| Passport Index refresh | Friday 06:17 | `/api/visa-power/provider/scheduled-sync` | Maximum configured passports per run; launch default one |
| Source governance | Monday 06:47 | `/api/admin/source-governance/scan-due` | Creates review alerts; never changes route facts automatically |
| Application alerts | Daily 07:07 | `/api/admin/application-cases/alerts/scan` | Private in-app alerts; no external delivery |

There is one canonical Passport Index scheduler. The older duplicate 06:00 workflow was retired in B16 to prevent two paid provider calls for the same weekly refresh.

## Release sequence

1. Confirm the backend and frontend worktrees contain only the intended B16 files.
2. Run `python scripts/validate_b16_operations.py` and the B16 backend test.
3. Run frontend B06–B16 contracts and the Next.js production build.
4. Merge the backend only after GitHub checks pass; wait for Railway `/api/build-info` to report the merged commit and `b16-v1`.
5. Merge the frontend only after its checks pass; wait for the Vercel deployment status to succeed.
6. Run `scripts/test-b16-operations-release.ps1` with the admin key read securely from the terminal.
7. Verify the four scheduled workflows are enabled and inspect their most recent successful or intentionally not-yet-run state.

## Rollback

### Backend or frontend defect

1. Disable only the affected scheduled workflow if it could write incorrect records.
2. Redeploy the last verified Railway or Vercel commit.
3. Confirm the live commit fingerprint and route contract match that rollback commit.
4. Open a bounded repair PR; do not edit production directly.

### Database defect

1. Stop affected write paths and schedules.
2. Preserve logs and take a reviewed Supabase backup/export before corrective work.
3. Do not rename, rewrite, delete, or blindly reverse an applied migration.
4. Prefer a new forward-repair migration. Use backup restore or destructive reversal only after explicit review of the exact affected data and recovery window.
5. Rerun protected schema checks and the affected release tests before re-enabling writes.

### Suspected secret exposure

1. Rotate the affected Railway, Supabase, email, payment, or GitHub secret immediately.
2. Update the matching server/scheduler configuration without copying it into a public variable.
3. Revoke old sessions or tokens where supported.
4. Review GitHub logs, deployment logs, browser storage, and audit records without reposting the exposed value.

## B16 boundaries

- No new Supabase migration is introduced.
- B16 validates operations; it does not claim every optional external provider is active.
- External email, WhatsApp, SMS, Telegram, push, payment, or authority submission remains fail-closed unless its separate activation contract passes.
- B17 remains the final complete product regression and TEST LEDGER update.
