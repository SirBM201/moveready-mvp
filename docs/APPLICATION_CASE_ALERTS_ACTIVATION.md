# MoveReady Application Case Alerts Activation

This runbook covers private in-app application alerts, migration 029, the protected daily scan, verified-user dismissal controls, administrator review, and production testing.

## 1. Implemented code

MoveReady now includes private alerts for:

- Overdue application deadlines
- Deadlines within 72 hours
- Deadlines within 14 days
- Appointments due within seven days or just missed
- Additional-document requests
- Official source review required
- Stale or unavailable official sources
- Pending or disputed application payments
- Refusal follow-up
- Approval and decision follow-up

The scan reads application case metadata only. It does not read, upload, or store raw authority correspondence, passport scans, bank statements, certificates, payment-card data, OTPs, passwords, or private keys.

## 2. Apply migrations in order

Apply migration 028 first:

```text
supabase/migrations/028_application_case_manager.sql
```

Then apply:

```text
supabase/migrations/029_application_case_alerts.sql
```

Migration 029 creates:

```text
relocation_application_case_alerts
```

The table is backend-only:

- Row-level security is enabled.
- `public`, `anon`, and `authenticated` privileges are revoked.
- The backend service role retains access.
- No browser-accessible RLS policy is created.
- Alert keys are unique for deduplication.
- Resolved or expired alerts require a resolution timestamp.

Do not add a public Supabase policy merely to make the frontend work.

## 3. User alert inbox

Page:

```text
/application-alerts
```

API:

```text
GET   /api/applications/alerts
PATCH /api/applications/alerts/<alert_id>
```

Both routes require a verified account session.

The user can:

- Review open private alerts
- Include dismissed alerts
- Dismiss an alert
- Reopen a dismissed alert
- Return to the Application Center or Timeline

A dismissed alert may reopen when a later scan detects a higher severity. This prevents a previously low-risk reminder from hiding a later critical deadline.

## 4. Administrator alert console

Page:

```text
/admin/application-alerts
```

Protected API:

```text
GET   /api/admin/application-case-alerts
PATCH /api/admin/application-case-alerts/<alert_id>
POST  /api/admin/application-cases/alerts/scan
```

The administrator can:

- Review all private alerts
- Filter through API by status, severity, or account email
- Run a protected scan
- Change an alert to open, dismissed, resolved, or expired
- Review critical and high workloads

The administrator must not paste raw authority correspondence into an alert summary or metadata.

## 5. Alert deduplication and lifecycle

The stable alert key is derived from:

- Application case ID
- Alert category
- Relevant deadline, appointment, stage, source status, payment status, or decision marker

It does not contain a private authority reference.

During each scan:

1. Current candidates are calculated from active application cases.
2. Existing matching alerts are updated rather than duplicated.
3. A more severe detection can reopen a dismissed, resolved, or expired alert.
4. Obsolete generated alerts are resolved automatically.
5. Manual alerts are not automatically resolved by the generated scan.

## 6. Daily unattended scan

Workflow:

```text
.github/workflows/application-case-alerts-daily.yml
```

Schedule:

```text
Daily at 07:07 UTC
```

Required GitHub repository secret:

```text
MOVEREADY_ADMIN_KEY
```

Its value must equal Railway:

```text
MOVEREADY_ADMIN_API_KEY
```

Optional repository variable:

```text
MOVEREADY_API_BASE=https://moveready-mvp-production.up.railway.app
```

The workflow:

- Validates the protected configuration
- Wakes the Railway backend
- Calls the protected alert scan
- Validates the scan status and case errors
- Publishes a GitHub Actions summary
- Opens or updates a GitHub issue when the scan fails
- Closes the issue after a later successful run

The workflow does not activate email, WhatsApp, Telegram, SMS, or push notifications. It refreshes the private in-app alert inbox only.

## 7. Alert interpretation

Alerts are prioritization signals, not legal decisions or approval predictions.

For every alert, confirm:

- The actual authority notice
- Correct time zone
- Exact deadline
- Required evidence
- Translation and legalization rules
- Payment recipient, amount, currency, and reference
- Submission or appointment channel
- Review, appeal, remedy, or rescheduling options

An alert generated from a user-entered date cannot override an official deadline.

## 8. Production testing

Authentication barriers only:

```powershell
.\scripts\test-application-alerts-release.ps1
```

Verified user inbox read:

```powershell
.\scripts\test-application-alerts-release.ps1 -SessionToken $SessionToken
```

Protected administrator read:

```powershell
$AdminKey = Read-Host "Enter MoveReady admin key"
.\scripts\test-application-alerts-release.ps1 -AdminKey $AdminKey
```

Protected scan:

```powershell
.\scripts\test-application-alerts-release.ps1 `
  -AdminKey $AdminKey `
  -RunScan
```

Full optional read and scan:

```powershell
.\scripts\test-application-alerts-release.ps1 `
  -SessionToken $SessionToken `
  -AdminKey $AdminKey `
  -RunScan
```

Do not paste session or admin keys into chat, screenshots, support cases, GitHub issues, or repository files.

## 9. Accurate activation status

Use these labels:

- **Code ready:** routes, pages, scan logic, workflow, CI, and scripts exist.
- **Schema ready:** migrations 028 and 029 are applied.
- **Scheduled ready:** `MOVEREADY_ADMIN_KEY` exists in GitHub Actions and the manual workflow run passes.
- **Deployment verified:** current Railway and Vercel builds are successful.
- **Controlled rollout:** code exists but schema, scheduled secret, or production verification is incomplete.
- **Available:** code, schema, authentication, privacy, daily scan, issue handling, and production tests have passed.

Do not call external application notifications available. This implementation provides private in-app alerts only.
