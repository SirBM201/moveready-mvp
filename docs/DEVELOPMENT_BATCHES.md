# MoveReady Controlled Development Batches

Updated: 17 August 2026

## Purpose
This is the execution control plan for completing MoveReady without repeatedly stopping for routine decisions. The product direction remains FIND → QUALIFY → MOVE → SETTLE → GROW → FIND AGAIN.

## Standing execution protocol
For every batch: freeze exact scope → implement backend/database/frontend items in scope → run targeted regression only → open/review PR(s) → merge after checks → report manual actions separately → user performs required Supabase/env/deployment actions → laptop acceptance when the batch requires it → close batch → begin next unblocked batch.

Do not restart completed Jobs or Passport work. Do not rerun comprehensive suites unless affected code justifies it. Never invent immigration rules, sponsorship, work authorization, financial thresholds, language results, or user achievements. Preserve RLS/privacy and explicit user control over external applications.

Each batch report must state: commits/PRs; tests; migration(s); environment variables; PHONE ACTIONS; LAPTOP ACTIONS; blockers; acceptance criteria; and DO NOT DO YET.

## B00 — Control baseline and migration 038
Start: PR #17 merged; migration 037 confirmed executed.
Scope: execute and verify 038_passport_official_source_review_lifecycle.sql; record database frontier; no unrelated feature work.
End/acceptance: migration 038 succeeds and review table/functions exist.
Manual gate: Supabase execution required.

## B01 — Passport official-source review operations
Scope: wire backend/admin operations for controlled pending_review → verified/needs_review/retired decisions; immutable review history; expiry handling; authorization; targeted tests. Preserve fail-closed semantics. Benin remains unverified until authority is established.
End: administrators can review mappings through supported backend contracts without direct unsafe database manipulation.
Dependencies: B00.

## B02 — Passport provenance UX
Scope: destination-detail UI clearly separates provider/discovery data from MoveReady-reviewed government/embassy evidence; verified/pending/needs-review labels; source links; reviewed/review-due metadata; mobile/loading/empty/error states.
End: users can understand exactly what is provider data and what MoveReady has verified.
Dependencies: B01 backend contract.

## B03 — Evidence → Evidence Pack → Application Case production lifecycle
Scope: refresh the independently valuable PR #14 lifecycle harness against current main; validate authenticated create/read, pack generation/read, case creation/transitions/events, anonymous privacy barriers, cleanup; fix only demonstrated defects.
End: lifecycle passes targeted production/auth validation and test ledger is updated.
Dependencies: none beyond stable auth/database; may run after B00.

## B04 — Authentication delivery hardening
Scope: reconcile PR #13 Mailtrap Sandbox HTTPS OTP transport with current email/auth code; retain existing auth model; targeted OTP delivery/failure diagnostics tests; document required env vars without exposing secrets.
End: sandbox OTP has a Railway-compatible HTTPS delivery path and safe fallback/error behavior.
Dependencies: current auth baseline.

## B05 — General-user Jobs scope contract
Scope: reconcile stale PR #7 concepts with current Jobs implementation; LOCAL / INTERNATIONAL / BOTH; current-country context; target countries; country-specific work-authorization truth; migration only if current schema genuinely requires it; preserve existing automation and source controls.
End: backend/database contract supports general users without founder/PET assumptions.

## B06 — General-user Jobs UX
Scope: connect B05 to current Jobs setup/search/workspace; mobile UX; truthful scope/location/work-authorization states; preserve vacancy monitoring, tailoring, tracking and user-confirmed submission.
End: a user can intentionally search locally, internationally, or both.
Dependencies: B05.

## B07 — Language Coach backend completion
Scope: salvage current-value work from stale PR #10 rather than wholesale merge; English/French/Both; IELTS General and TEF Canada foundations; diagnostic, study allocation, practice/mistakes/review/progress/readiness contracts; original/licensed practice-content safeguards.
End: stable authenticated APIs/data model with targeted tests.

## B08 — Language Coach live frontend integration
Scope: connect existing Language Coach UI to B07 real APIs; diagnostic onboarding, daily challenge, short practice, mistakes/review, progress/readiness, 50/50–70/30–30/70 allocation; mobile/error/empty states.
End: Language Coach is genuinely usable rather than UI-only.
Dependencies: B07.

## B09 — Financial Readiness V1 backend
Scope: salvage valid work from stale PR #11 against current readiness architecture; proof-of-funds requirement as sourced input, fees/tuition/relocation/flight/accommodation/settlement reserve, family size, savings, expected funding, gap, target date, monthly savings. No invented official thresholds.
End: provenance-safe readiness calculation API with tests.

## B10 — Financial Readiness UX
Scope: connect frontend readiness experience to B09; source/provenance visibility; scenario inputs; funding gap and monthly target; mobile/error states.
End: users can create and understand a truthful financial readiness plan.
Dependencies: B09.

## B11 — Opportunity / Route Finder core
Scope: audit existing route checker and close Launch V1 gaps; profile inputs, route candidates, qualification/gaps, evidence, cost/timeline/risk fields, official sources and next actions; jurisdiction/date-aware provenance; never guarantee approval.
End: FIND → QUALIFY produces actionable, source-aware route outputs.
Dependencies: Passport provenance and readiness contracts where consumed.

## B12 — Documents, evidence and application UX closure
Scope: close remaining frontend/backend gaps around private document metadata, evidence packs, application cases, deadlines/events/status, privacy and failure states; build on B03 rather than replace it.
End: MOVE preparation workflow is coherent from evidence to tracked case.

## B13 — Unified Launch V1 dashboard/action center
Scope: reconcile valuable orchestration/design concepts from stale frontend PR #9 with current main; unify Jobs, Route Finder, Passport, Language, Financial Readiness, Documents and Applications; one obvious next action; progressive disclosure; no founder-specific content.
End: core engines feel like one MoveReady product.

## B14 — Smart alerts and critical monitoring
Scope: consolidate launch-critical alerts for jobs, application deadlines/follow-ups, document/passport/visa expiry, relevant verified-rule changes, language reminders and evidence refresh; dedupe and preference controls; no noisy unsupported alerts.
End: critical workflows can surface actionable changes safely.

## B15 — Mobile and accessibility closure
Scope: cross-engine responsive review, navigation, forms, signed-out/loading/empty/error states, keyboard/accessibility basics, low-width layouts and action clarity.
End: Launch V1 critical journeys are usable on phone.

## B16 — Deployment and operations hardening
Scope: Railway/frontend/Supabase contracts; scheduled jobs; admin key boundaries; environment validation; health/build info; secret contamination guardrails; migration ledger; rollback/runbook notes.
End: production operations have explicit checks and no hidden manual assumptions.

## B17 — Launch V1 integration acceptance
Scope: one final comprehensive regression only after preceding batches; auth, RLS/privacy, Jobs, Passport/provenance, Route Finder, Language Coach, Financial Readiness, documents/evidence, applications, dashboard, mobile, builds/deployment and critical schedules. Update TEST LEDGER with commit SHAs and touched-subsystem status.
End: documented PASS/FAIL launch gate and defects routed into bounded fix batches.

## B18 — Soft-launch readiness
Scope: onboarding copy, truthful limitations, support/error recovery, source/legal disclaimers, analytics/feedback hooks already approved, launch checklist and controlled initial-user flow.
End: Launch V1 is ready for controlled public soft launch.
Dependencies: B17 pass or accepted bounded exceptions.

# Post-Launch Product Batches
These remain in the Master Product Inventory and are not prerequisites for Launch V1 unless later promoted.

## P01 — Study Abroad Engine
Institution/program discovery, eligibility, tuition/intakes/scholarships, student visa evidence, dependants, post-study work and pathway context.

## P02 — Broader PR/Immigration Pathway Engine
Jurisdiction-specific EOI, nomination, work-experience, education/language/funds/dependant/PR/citizenship comparisons with dated official provenance.

## P03 — Travel Planner + accommodation/flight/transport
Entry planning, itinerary/budget and compliant partner/referral integrations.

## P04 — Courier and document delivery marketplace
DHL/UPS/EMS and lower-cost/local alternatives subject to partner/API terms and legal document-handling rules.

## P05 — Insurance + Partner Marketplace
Travel/health/student/relocation insurance and clearly separated third-party professional services.

## P06 — Settlement Assistant + family relocation
Arrival registrations, banking/SIM/tax/health/transport/schools/utilities/licensing plus family-specific rights/evidence/checklists.

## P07 — Cost-of-living/country comparison
Rent, tax, salary, transport, groceries, healthcare, childcare, education, immigration costs and savings assumptions with provenance.

## P08 — AI Mobility Assistant
Grounded assistant over verified MoveReady data, profile/goals/routes/documents/jobs/applications/readiness/travel state with provenance and permission boundaries.

## Batch execution rule
A prompt may authorize one batch or a contiguous range, e.g. “Implement B03–B04 without waiting for routine approval; stop only for an unavoidable external/manual gate or a materially destructive decision.” A batch must never silently cross its stated end boundary.
