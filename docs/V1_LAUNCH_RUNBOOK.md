# MoveReady V1 production activation runbook

This runbook separates product completion from production activation. Do not mark a capability live merely because its code exists on `main`.

## 1. Database gate

1. Confirm every required Supabase migration through `034_language_coach_v1.sql` has been applied in numerical order.
2. Confirm the Language Coach tables exist: `relocation_language_profiles`, `relocation_language_questions`, `relocation_language_attempts`, `relocation_language_mistakes`, `relocation_language_daily_progress`.
3. Do not apply an ad-hoc production schema patch that is absent from versioned migrations.

## 2. Railway gate

1. Confirm Railway is deploying `SirBM201/moveready-mvp` `main`.
2. Set production `ENV_MODE` / `FLASK_ENV` and keep `AUTH_OTP_DEV_MODE=false`.
3. Open `/api/build-info` on the deployed API.
4. Require `route_contract.ok=true`.
5. Compare `deployment.commit_sha` with the current backend `main` commit.
6. Require the V1 completion routes: Opportunity Finder, Financial Readiness, Route Comparison, Account Outcomes and Language Coach.

## 3. Frontend gate

1. Require the latest `Frontend Production Build` workflow on `main` to pass.
2. Confirm `NEXT_PUBLIC_API_BASE_URL` points to the active Railway API.
3. Smoke: `/find`, `/compare`, `/qualify`, `/language-coach`, `/budget-calculator`, `/proof-of-funds`, `/readiness-hub`, `/move`, `/progress`, `/deployment-status`.

## 4. Verified-user smoke journey

Use a non-production-test identity or approved test account. Never place real passport scans or full financial documents into a test fixture.

1. Sign in through verified email OTP.
2. Complete/update a relocation profile.
3. Open FIND and obtain pathway recommendations.
4. Compare at least two structured routes.
5. Run route readiness and financial readiness.
6. Open Language Coach and confirm profile/practice/mistakes/progress surfaces load.
7. Add document metadata/evidence readiness without uploading prohibited raw sensitive material.
8. Create or update an application/job action and a timeline item.
9. Confirm Action Center and Progress reflect the recorded state.
10. Confirm logout/session controls work.

## 5. Fail-closed controls

Keep these unavailable until their external production controls are complete:

- payment links/checkout;
- unreviewed provider publication;
- automatic application submission;
- external email/WhatsApp/SMS/Telegram/push alerts without credentials, consent and delivery audit;
- claims that a readiness score, fit score or historical outcome percentage predicts visa/job/admission approval.

## 6. Source and content gate

Before public promotion, review promoted route, opportunity, travel, proof-of-funds and deadline records for freshness. Starter/fallback records must remain visibly provisional where official verification is outstanding.

## 7. Release decision

V1 is technically releasable only when the schema gate, Railway route contract, frontend production build and verified-user smoke journey all pass. Controlled-rollout features may remain disabled without blocking the core FIND → QUALIFY → MOVE release, provided the UI does not advertise them as active.
