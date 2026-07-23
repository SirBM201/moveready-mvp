# MoveReady Private Workflow Activation

This release stage completes the private verified-account workflow from evidence preparation through application tracking, alerts, ranked next actions, journey progress, account settings, security, data export, and privacy requests.

## 1. Apply migrations in order

The database must already include migrations 001 through 026.

Run these files in order:

```text
supabase/migrations/027_evidence_inventory_and_packs.sql
supabase/migrations/028_application_case_manager.sql
supabase/migrations/029_application_case_alerts.sql
supabase/migrations/030_account_preferences_privacy_activity.sql
```

Migration 027 creates private document metadata and evidence-pack records.

Migration 028 creates private application cases and auditable case events.

Migration 029 creates private application deadline and risk alerts.

Migration 030 creates:

- `relocation_account_preferences`
- `relocation_privacy_requests`

All private tables remain backend-only. RLS is enabled, direct `public`, `anon`, and `authenticated` privileges are revoked, and only the service role receives table privileges.

## 2. Deploy the backend

The current backend must include:

- `app/routes/evidence_workflow.py`
- `app/routes/evidence_admin.py`
- `app/routes/application_cases.py`
- `app/routes/application_cases_admin.py`
- `app/routes/application_case_alerts.py`
- `app/routes/account_action_center.py`
- `app/routes/account_controls.py`
- `app/routes/account_controls_admin.py`
- `app/routes/source_governance.py`
- `app/routes/operations.py`
- `app/routes/health.py`
- `app/services/platform_account_modules_patch.py`
- the latest `app/__init__.py`

The build fingerprint release label is:

```text
moveready-account-journey-action-center-2026-07-24
```

After Railway deploys, `/api/build-info` must report:

- the current release label
- a passing route contract
- no missing expected routes
- the latest commit SHA when Railway exposes it
- feature flags for evidence, applications, application alerts, Action Center, My Journey, account activity, preferences, sessions, export, privacy requests, and settlement timeline

## 3. Deploy the frontend

The current frontend includes:

- `/onboarding`
- `/my-journey`
- `/action-center`
- `/applications`
- `/application-alerts`
- `/evidence-pack`
- `/activity`
- `/settings`
- `/admin/application-alerts`
- `/admin/privacy-requests`
- persistent accessibility preferences
- mobile quick navigation
- global loading, error, and not-found states
- manifest, robots, sitemap, and controlled private-route indexing

No payment, email, WhatsApp, booking, courier, or provider credential is required to render these interfaces.

## 4. GitHub Actions secrets

The unattended application-alert scan requires this repository secret:

```text
MOVEREADY_ADMIN_KEY
```

Its value must match Railway:

```text
MOVEREADY_ADMIN_API_KEY
```

Do not place either value in source code, workflow YAML, screenshots, chat, logs, or GitHub issues.

## 5. External notification boundary

Account preferences may record email, WhatsApp, marketing, source-change, document-expiry, opportunity, and application-deadline choices.

A saved preference does not activate delivery.

Keep external delivery disabled until all of the following are approved:

- provider credentials
- verified sender or business account
- approved message templates where required
- explicit channel opt-in
- unsubscribe and consent-withdrawal handling
- delivery and failure audit
- rate limits
- privacy disclosure
- production tests

The Action Center and Application Alert inbox remain available as private in-app tools without external delivery.

## 6. Privacy-request boundary

Submitting an account-deletion or consent-withdrawal request does not delete records automatically.

Before completion, verify:

- requester identity
- requested scope
- legal and financial retention duties
- billing, refund, dispute, and fraud records
- provider-held copies
- backups and restoration windows
- active support or legal holds
- deletion, correction, or restriction evidence
- the final communication sent to the user

The exact destructive-request phrase is:

```text
DELETE MY MOVEREADY ACCOUNT
```

This confirms the request only.

## 7. Read-only production verification

Run the public and anonymous-access test:

```powershell
.\scripts\test-account-controls-release.ps1
```

Run protected schema diagnostics:

```powershell
$AdminKey = Read-Host "Enter MoveReady admin key"

.\scripts\test-account-controls-release.ps1 `
    -AdminKey $AdminKey
```

Include verified account reads:

```powershell
$AdminKey = Read-Host "Enter MoveReady admin key"
$SessionToken = Read-Host "Enter a verified MoveReady session token"

.\scripts\test-account-controls-release.ps1 `
    -AdminKey $AdminKey `
    -SessionToken $SessionToken
```

The account-control script checks:

- public operations status
- platform catalogue availability
- anonymous access barriers
- migrations 029 and 030 through protected diagnostics
- preferences
- active-session response safety
- account activity
- Action Center ranking response
- JSON export exclusions
- privacy-request history

It does not change preferences, revoke sessions, create privacy requests, delete data, modify Action Center source records, activate messaging, or enable payments.

## 8. Complete private workflow verification

Use the combined release command after migrations and deployment:

```powershell
$AdminKey = Read-Host "Enter MoveReady admin key"
$SessionToken = Read-Host "Enter a verified MoveReady session token"

.\scripts\test-evidence-application-stage.ps1 `
    -AdminKey $AdminKey `
    -SessionToken $SessionToken
```

This verifies:

1. Protected operations and schemas through migration 030
2. Evidence Center privacy and route barriers
3. Source Governance and source health
4. Application Case Manager
5. Application Alert inbox
6. Account settings, sessions, activity, Action Center, export, and privacy
7. Journey and settlement planning

Run the optional protected scans only when ready:

```powershell
.\scripts\test-evidence-application-stage.ps1 `
    -AdminKey $AdminKey `
    -SessionToken $SessionToken `
    -RunSourceScan `
    -RunApplicationAlertScan
```

The optional scans may create or refresh review alerts. They do not change route facts automatically and do not activate external messaging.

## 9. Manual interface checks

After migration and deployment:

1. Sign in with a verified account.
2. Open `/onboarding` and confirm progress loads.
3. Save or load one profile in `/dashboard`.
4. Open `/my-journey` and confirm missing stages are not shown as complete.
5. Confirm settlement remains inactive unless the latest application case records approval.
6. Open `/action-center` and verify each item links back to its underlying workspace.
7. Confirm resolved application alerts, completed timeline tasks, archived records, and closed support items are not incorrectly prioritized.
8. Open `/settings` and save language, currency, time zone, accessibility, and in-app notification choices.
9. Refresh another page and confirm accessibility choices are reapplied.
10. Review `/settings#security` and confirm token hashes and remote addresses are not displayed.
11. Download the JSON export and confirm OTP, session, password, secret, payment credential, and raw-document data is excluded.
12. Create a non-destructive correction request.
13. Open `/admin/privacy-requests` with the admin key and confirm it appears.
14. Confirm a destructive request cannot advance without identity reverification.
15. Open `/activity` and verify account-owned records are shown without raw documents or security credentials.
16. Open `/deployment-status` and confirm the route contract passes with no missing expected endpoint.
17. Open the mobile layout and confirm Home, Actions, Applications, Alerts, and Account are reachable from the bottom navigation.

## 10. Rollout state

After migrations 027–030, successful Railway deployment, successful Vercel deployment, and completed tests, these modules may be represented as implemented:

- Evidence Center
- Refusal Repair
- Source Health and Source Governance
- Guided Setup
- My Journey
- Action Center
- Application Case Manager
- Application Alerts
- Account Activity
- Account Settings and Privacy
- Active Session Controls
- Safe Account JSON Export
- Protected Privacy Administration
- Settlement Timeline Execution

Email, WhatsApp, Telegram, SMS, push notifications, payment links, provider execution, booking inventory, courier fulfillment, and automatic account deletion remain controlled until their separate production requirements pass.
