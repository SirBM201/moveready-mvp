# MoveReady Evidence Center and Source Governance Activation

This document covers the private Evidence Center, refusal-repair workflow, public Source Health page, protected source-review queue, weekly source scan, and settlement timeline persistence.

## 1. Implemented code

The backend and frontend repositories include:

- Private document inventory metadata
- Document expiry and renewal-risk calculation
- Translation and legalization status tracking
- Route-based evidence-pack generation
- Evidence-pack completeness and risk scoring
- Structured refusal and denied-admission repair planning
- Redaction confirmation for optional decision excerpts
- Public source-freshness and route-version health reporting
- Protected source and route review queue
- Source snapshot and content-hash recording
- Review-due and content-change alerts
- Weekly unattended review-due scanning
- Protected evidence-pack review and expiry queue
- Account Center evidence counts and summaries
- Unified admin queue integration
- Consent-based settlement task persistence to the private timeline

These workflows do not upload or store raw passport scans, bank statements, certificates, refusal letters, medical files, full document numbers, OTPs, passwords, card data, or private keys.

## 2. Apply migration 027

Run all earlier migrations first, including migrations 023 through 026. Then run:

```text
supabase/migrations/027_evidence_inventory_and_packs.sql
```

Migration 027 creates:

```text
relocation_user_document_inventory
relocation_evidence_packs
```

Both tables are backend-only:

- Row-level security is enabled.
- `public`, `anon`, and `authenticated` privileges are revoked.
- The backend service role retains access.
- No public browser RLS policy is created.

Do not create a public Supabase policy for these tables merely to make the frontend work. The frontend must use the authenticated Flask API.

## 3. Confirm protected operations diagnostics

Run:

```powershell
$AdminKey = Read-Host "Enter MoveReady admin key"
.\scripts\test-operations-admin.ps1 -AdminKey $AdminKey
```

The protected response should report these codes as ready:

```text
trusted_sources
source_change_alerts
route_versions
document_inventory
evidence_packs
```

The Evidence Center remains controlled if migration 027 is missing. It must not silently store records in browser-only storage as a substitute.

## 4. Evidence Center privacy boundary

The verified-account Evidence Center is available at:

```text
/evidence-pack
```

Supported stored information includes:

- Document type and user-defined label
- Owner scope such as main applicant, spouse, child, dependant, sponsor, employer, or school
- Name shown for consistency review
- Issuing country and language
- Issue and expiry dates
- Availability, renewal, correction, translation, legalization, readiness, expiry, or archive status
- User notes that do not contain private numbers or raw document text
- Evidence-pack route, target country, stage, completeness, missing categories, warnings, and official-source note

The API rejects fields such as:

```text
file
file_content
file_url
document_number
passport_number
national_id_number
bank_account_number
card_number
otp
password
private_key
```

Staff must not ask a user to bypass this restriction by placing raw documents in notes, support cases, ordinary email, WhatsApp, or chat.

## 5. Evidence-pack interpretation

The pack is a readiness organizer, not the controlling checklist.

Before changing a pack to `ready`, confirm:

- Current official authority and checklist
- Target country and route
- Application stage
- Required and conditional evidence categories
- Passport and document expiry rules
- Translation and legalization requirements
- Name consistency
- Family and dependant evidence
- Funds and transaction-history expectations
- Previous refusal, denied-admission, cancellation, revocation, or disclosure requirements

A 100% starter-category score does not prove that every country-specific requirement is satisfied.

## 6. Refusal and denied-admission repair

The refusal-repair workflow is private and verified-account only.

It distinguishes:

- Visa refusal
- Permit refusal
- Denied admission at a border or port of entry
- Admission refusal
- Startup endorsement refusal
- Scholarship refusal
- Visa or permit still valid, cancelled, revoked, unknown, or not applicable

The workflow must not:

- Describe denied admission as a successful visit
- Guess that a visa remains valid
- Guess whether a ban exists
- Hide a refusal or denied-admission event
- Recommend fabricated bookings, edited statements, invented employment evidence, or inconsistent explanations
- Predict approval

A misrepresentation concern is treated as critical and should prompt qualified legal advice before a further substantive application or response.

Optional decision excerpts require confirmation that names, passport numbers, addresses, bank details, case identifiers, barcodes, signatures, and third-party personal data were removed.

## 7. Source Health and protected source governance

Public source health:

```text
/source-health
GET /api/source-health/summary
```

Protected review queue:

```text
/admin#source-governance
GET /api/admin/source-governance/queue
```

Protected review-due scan:

```text
POST /api/admin/source-governance/scan-due
```

Protected source review record:

```text
POST /api/admin/source-governance/sources/<source_id>/mark-checked
```

Marking a source checked does not automatically update:

- Route facts
- Route versions
- Fees
- Deadlines
- Eligibility
- Reports
- Watchlist messages
- Provider claims
- User evidence packs

Review and approve affected records separately.

## 8. Weekly unattended source scan

Workflow:

```text
.github/workflows/source-governance-weekly.yml
```

Schedule:

```text
Monday at 06:47 UTC
```

Required GitHub repository secret:

```text
MOVEREADY_ADMIN_KEY
```

Its value must equal Railway `MOVEREADY_ADMIN_API_KEY`. Do not paste the value into code, documentation, issues, screenshots, or chat.

Optional GitHub repository variable:

```text
MOVEREADY_API_BASE=https://moveready-mvp-production.up.railway.app
```

The workflow:

- Wakes the Railway backend
- Calls the protected due-source scan
- Creates missing review-due alerts
- Preserves existing open alerts instead of duplicating them
- Opens or updates a GitHub issue when the scan fails
- Closes the issue after a later successful run
- Does not change route facts automatically

## 9. Settlement timeline persistence

The Journey Planner includes a focused settlement execution form.

Saving requires:

- Arrival date
- Email or phone for private lookup
- `save_to_timeline=true`
- Explicit `consent_to_contact=true`

The planner saves dated events for:

- Before travel
- First 72 hours
- First two weeks
- First 90 days

These dates are planning anchors, not substitutes for exact immigration, municipal, tax, school, health, or permit deadlines. Each saved event retains an official-confirmation-required flag.

External email, WhatsApp, or Telegram delivery remains disabled until its own delivery controls are approved.

## 10. Release tests

Public and private Evidence Center contract:

```powershell
.\scripts\test-evidence-release.ps1
```

Optional verified-session read test:

```powershell
.\scripts\test-evidence-release.ps1 -SessionToken $SessionToken
```

Do not paste the session token into chat, screenshots, support cases, or GitHub issues.

Protected source-governance test:

```powershell
$AdminKey = Read-Host "Enter MoveReady admin key"
.\scripts\test-source-governance-release.ps1 -AdminKey $AdminKey
```

To also create review-due alerts during the test:

```powershell
.\scripts\test-source-governance-release.ps1 -AdminKey $AdminKey -RunDueScan
```

Existing journey and timeline verification:

```powershell
.\scripts\test-journey-planner-release.ps1
```

## 11. Accurate launch status

Use these labels:

- **Code ready:** routes and interfaces exist in the repositories.
- **Schema ready:** migration 027 and required earlier migrations are applied.
- **Deployment verified:** Railway and Vercel show successful current production builds.
- **Controlled rollout:** code exists but migration, credentials, or operational verification is incomplete.
- **Available:** code, schema, deployment, privacy, source, and production tests have passed.

Do not call the Evidence Center or weekly source scan fully available until migration 027 is applied and the relevant production tests pass.
