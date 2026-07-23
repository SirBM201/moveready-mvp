# MoveReady Application Case Manager Activation

This runbook covers the private Application Center, application lifecycle, deadlines, evidence-pack linkage, fees, source status, event history, administrator review, and opt-in timeline reminders.

## 1. Implemented code

The repositories contain:

- Verified-account application case creation and history
- Route, country, authority, stage, source, fee, payment, appointment, deadline, and decision metadata
- Optional links to profile, saved route, route version, and evidence pack
- Masked authority reference hints
- Stage-transition rules
- Terminal-stage decision requirements
- Dynamic deadline and source-risk warnings
- Additional-document request handling
- Refusal and decision history
- Auditable user and administrator events
- Consent-based appointment and deadline timeline tasks
- Duplicate timeline-task protection
- Account Center application summaries
- Protected administrator case and deadline queue
- Unified review-queue integration
- Operations diagnostics and CI protection

The Application Case Manager does not upload or store raw authority correspondence, passport scans, bank statements, certificates, payment-card data, OTPs, passwords, private keys, or full sensitive reference numbers.

## 2. Apply migration 028

Run every earlier migration first, including migration 027. Then run:

```text
supabase/migrations/028_application_case_manager.sql
```

Migration 028 creates:

```text
relocation_application_cases
relocation_application_case_events
```

Both tables are backend-only:

- Row-level security is enabled.
- `public`, `anon`, and `authenticated` privileges are revoked.
- The backend service role retains access.
- No browser-accessible RLS policy is created.

Do not add a public Supabase policy merely to make the frontend work. The frontend must use the authenticated Flask API.

## 3. Lifecycle safeguards

Supported stages:

```text
research
preparing
appointment_booked
submitted
biometrics_completed
interview_scheduled
additional_documents_requested
decision_pending
approved
refused
withdrawn
expired
closed
```

The API enforces forward or explicitly permitted transitions. It rejects unsupported stage jumps.

Terminal stages are:

```text
approved
refused
withdrawn
expired
closed
```

A terminal stage requires:

- Decision or closure date
- Factual result summary

A case cannot be marked `completed` unless its stage is terminal.

The application status and the immigration result must not be confused. For example:

- `status=attention_required` is an internal workflow status.
- `application_stage=refused` is an application result.
- Denied admission is a separate immigration-history event and is not a successful visit.

## 4. Privacy boundary

Supported stored information includes:

- Case title
- Target country and city
- Route category and route name
- Responsible authority
- Application stage and internal case status
- Source status
- Masked or partial authority reference hint
- Application, appointment, submission, deadline, and decision dates
- Fee and currency
- Payment status
- Official source URL and review note
- Short planning notes
- Factual result summary
- Short event summaries

The API rejects fields such as:

```text
file
file_content
file_url
passport_number
document_number
national_id_number
bank_account_number
card_number
cvv
otp
password
private_key
full_authority_reference
raw_correspondence
```

The authority-reference field accepts only a masked or partial hint. The user or administrator must confirm that it is masked, and the compact alphanumeric content is limited.

Do not ask users to bypass these controls through notes, general support cases, email, WhatsApp, chat, screenshots, or GitHub issues.

## 5. Verified-account workspace

User page:

```text
/applications
```

API routes:

```text
GET  /api/applications/options
GET  /api/applications
POST /api/applications
GET  /api/applications/<case_ref>
PATCH /api/applications/<case_ref>
POST /api/applications/<case_ref>/events
POST /api/applications/<case_ref>/timeline-tasks
```

All routes except `/options` require a verified account session.

The user can:

- Create a private case
- Update permitted stages
- Record source status and official link
- Record appointment and next deadline
- Record fee and payment status
- Link an evidence pack
- Record short events
- Save appointment and deadline reminders to the private timeline
- Record a final decision or closure

## 6. Administrator workspace

Admin page:

```text
/admin#application-cases
```

Protected API routes:

```text
GET   /api/admin/application-cases
GET   /api/admin/application-cases/<case_id>
PATCH /api/admin/application-cases/<case_id>
POST  /api/admin/application-cases/<case_id>/events
GET   /api/admin/application-cases/deadlines/due
```

The administrator can filter and review:

- Active and attention-required cases
- High or critical risk
- Additional-document requests
- Refusals
- Stale, unavailable, or unreviewed official sources
- Payment pending or disputed
- Deadlines due within a selected window or already overdue
- Decision and closure records
- Auditable event history

The administrator must not change a result to approved, refused, withdrawn, expired, or closed without the factual decision or closure date and result summary.

## 7. Dynamic risk logic

The API increases risk when:

- Official source is unavailable, stale, or still needs review
- Deadline is overdue, within 72 hours, or within 14 days
- Appointment is imminent or just missed
- Additional documents were requested
- Case is refused
- Submitted case lacks a submission date
- Active submitted case lacks an official source or tracking link
- Payment is pending or disputed

Risk is advisory workflow prioritization. It is not an approval prediction.

## 8. Timeline task creation

Timeline task creation requires:

```text
confirm_timeline_storage=true
```

It creates reminders only when the case has an appointment date or next deadline.

Generated timeline records use the existing allowed timeline type:

```text
event_type=task
```

Application provenance is retained in metadata:

```text
generated_by=application_case_manager
application_case_id
application_case_ref
application_event_kind
official_confirmation_required=true
```

Matching title and due-date tasks for the same case are not duplicated.

Generated reminders do not replace the authority’s exact deadline, time zone, appointment notice, evidence requirements, payment rule, or submission channel.

## 9. Operations verification

Run:

```powershell
$AdminKey = Read-Host "Enter MoveReady admin key"
.\scripts\test-operations-admin.ps1 -AdminKey $AdminKey
```

The protected response must show:

```text
application_cases
application_case_events
```

as ready.

Public operations status reports:

```text
application_case_manager=verified_account_only_after_migration_028
application_timeline_tasks=explicit_storage_confirmation_required
```

## 10. Release test

Public and authentication-barrier test:

```powershell
.\scripts\test-application-cases-release.ps1
```

Optional verified-account read:

```powershell
.\scripts\test-application-cases-release.ps1 -SessionToken $SessionToken
```

Optional protected administrator reads:

```powershell
$AdminKey = Read-Host "Enter MoveReady admin key"
.\scripts\test-application-cases-release.ps1 -AdminKey $AdminKey
```

Both optional reads:

```powershell
.\scripts\test-application-cases-release.ps1 `
  -SessionToken $SessionToken `
  -AdminKey $AdminKey
```

Do not paste the session token or admin key into chat, screenshots, support cases, GitHub issues, or repository files.

## 11. Accurate activation status

Use these labels:

- **Code ready:** backend and frontend routes exist.
- **Schema ready:** migration 028 is applied.
- **Deployment verified:** Railway and Vercel show successful current builds.
- **Controlled rollout:** code exists but schema, login delivery, or production verification is incomplete.
- **Available:** code, schema, deployment, authentication, privacy, lifecycle, timeline, and release tests have passed.

Do not call the Application Case Manager fully available until migration 028 is applied and the release tests pass against production.
