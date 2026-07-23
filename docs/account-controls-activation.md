# MoveReady Account Controls Activation

This stage adds account settings, onboarding progress, accessibility choices, notification consent, active-session management, unified activity history, safe JSON export, and reviewed privacy requests.

## 1. Apply migrations in order

The database must already include migrations 001 through 029.

Run:

```text
supabase/migrations/030_account_preferences_privacy_activity.sql
```

Migration 030 creates:

- `relocation_account_preferences`
- `relocation_privacy_requests`

Both tables are backend-only. RLS is enabled, direct `public`, `anon`, and `authenticated` privileges are revoked, and only the service role receives table privileges.

## 2. Deploy the backend

The backend must include:

- `app/routes/account_controls.py`
- `app/routes/account_controls_admin.py`
- `app/services/platform_account_modules_patch.py`
- the latest `app/__init__.py`
- the latest `app/routes/operations.py`

The same backend deployment also registers the previously implemented Application Case Alert API.

## 3. Deploy the frontend

The frontend includes:

- `/settings`
- `/activity`
- `/onboarding`
- `/admin/privacy-requests`
- persistent accessibility preferences
- mobile quick navigation
- global loading, error, and not-found states
- manifest, robots, and sitemap metadata

No provider credential is required to render these pages.

## 4. External notification boundary

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

## 5. Privacy-request boundary

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

## 6. Production verification

Run the read-only public test:

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

Do not paste either value into chat, screenshots, logs, GitHub issues, or source files.

The script does not change preferences, revoke sessions, create privacy requests, delete data, activate messaging, or enable payments.

## 7. Manual interface checks

After migration and deployment:

1. Sign in with a verified account.
2. Open `/onboarding` and confirm progress loads.
3. Open `/settings` and save language, currency, time zone, accessibility, and in-app notification choices.
4. Refresh another page and confirm accessibility choices are reapplied.
5. Review `/settings#security` and confirm token hashes and remote addresses are not displayed.
6. Download the JSON export and confirm OTP, session, password, secret, payment credential, and raw-document data is excluded.
7. Create a non-destructive correction request.
8. Open `/admin/privacy-requests` with the admin key and confirm it appears.
9. Confirm a destructive request cannot advance without identity reverification.
10. Open `/activity` and verify account-owned records are shown without raw documents or security credentials.

## 8. Rollout state

These modules may be displayed as implemented after migration 030 and successful deployment tests:

- Guided Setup
- Application Center
- Application Alerts
- Account Activity
- Account Settings and Privacy

Email, WhatsApp, push notifications, payment links, and provider execution remain controlled until their separate production requirements pass.
