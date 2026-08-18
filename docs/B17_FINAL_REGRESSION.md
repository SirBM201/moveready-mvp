# B17 — Final full regression and launch-readiness verification

## Purpose

B17 is the final Launch V1 release gate. It does not add product scope. It proves that the already-merged FIND → QUALIFY → MOVE product remains coherent across backend, frontend, database, privacy and production operations.

## Baseline

- Backend baseline: B16 merged to `main`.
- Frontend baseline: B16 merged to `main`.
- Schema frontier: `039_language_coach_backend_completion.sql`.
- Operations contract: `b16-v1`.
- No B17 SQL migration is required unless regression testing discovers a real schema defect.
- Do not rotate secrets or manually trigger a paid/external provider merely to satisfy B17.

## Automated release gates

The final backend baseline must remain green for the existing GitHub Actions suites covering:

- backend smoke and route contracts;
- authentication and provider handoff;
- jobs and official-source automation;
- Passport Index and source governance;
- Language Coach;
- Financial Readiness;
- Opportunity / Route Finder;
- evidence and application cases;
- account controls and privacy;
- billing/provider fail-closed controls;
- dashboard orchestration;
- smart alerts;
- build/deployment fingerprinting; and
- B16 deployment/operations hardening.

The final frontend baseline must pass the production build and B06–B16 contract scripts already enforced by its build workflow.

## Production acceptance

Run `scripts/test-b17-final-regression.ps1` against Railway after the B16 merge is deployed. The script is deliberately read-only: it does not invoke scheduled scans, provider syncs, application submission, payment, external messaging or destructive account operations.

Production acceptance requires:

1. `/health`, `/api/health` and `/api/build-info` are healthy.
2. Railway reports `contract_versions.operations = b16-v1`.
3. The route contract and admin-boundary contract pass.
4. Exactly four canonical scheduled jobs are declared.
5. The migration ledger frontier is `039_language_coach_backend_completion.sql`.
6. Public operations status is B16-current.
7. Protected operations diagnostics report no launch blockers.
8. Production environment validation is not blocked.
9. Launch V1 optional schema checks are ready.
10. If an expected commit is supplied, Railway serves that exact commit.

## Manual browser acceptance

After automated production acceptance passes, perform one bounded browser walkthrough on the deployed Vercel site:

- signed-out public navigation and accessibility page;
- sign-in / OTP flow with a real test account;
- dashboard highest-ranked next action;
- Jobs discovery and saved/watchlist state;
- Opportunity / Route Finder evidence and official-source links;
- Language Coach English/French selection and progress state;
- Financial Readiness known/unknown inputs without fabricated exchange rates;
- Evidence Center → Application Center handoff;
- consolidated Smart Alerts preferences and safe states;
- mobile navigation at a 320–420px viewport and keyboard focus/skip navigation on desktop;
- sign-out and confirm private account data is no longer visible.

Do not use the final regression to submit a real immigration application, auto-apply to a job, make a payment, send external messages, or consume a paid Passport provider call.

## Release decision

MoveReady Launch V1 may be marked **B17 PASS / release-ready** only when:

- repository CI is green;
- production acceptance passes;
- the bounded browser walkthrough has no launch-blocking defect; and
- any provider intentionally left inactive is documented as fail-closed rather than represented as active.

Any regression found in B17 must be repaired through a bounded PR and the affected gate rerun before release-ready status is recorded.
