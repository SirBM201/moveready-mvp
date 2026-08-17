# MoveReady Targeted Test Ledger

Updated: 17 August 2026

This ledger records bounded batch validation. It does not replace the comprehensive Launch V1 regression reserved for B17.

## B03 — Evidence → Evidence Pack → Application Case production lifecycle

### Scope

- authenticated evidence metadata create/read;
- authenticated evidence pack generate/read;
- authenticated application case create/read;
- explicit and automatic case event persistence;
- valid `research` → `preparing` transition;
- anonymous privacy barriers for evidence documents, evidence packs, and application cases;
- conservative cleanup of temporary case and document metadata;
- no raw document upload, sensitive document number, session token, or OTP output.

### Baseline

- repository: `SirBM201/moveready-mvp`;
- production deployment checked on 17 August 2026;
- production commit: `cb65e66a251d336074192bd089b497be89358667`;
- migration 027 evidence inventory/packs: existing production prerequisite;
- migration 028 application case manager: existing production prerequisite;
- migration 038 Passport review lifecycle: executed successfully before B03; unrelated to B03 data mutations but part of the current database frontier;
- acceptance harness source includes B03 refresh merge `8c2fa1608bc5edc5a75ad8d27e58b6128132a1df` and placeholder-email guard merge `95b3e2563a48340ece9c0c772d04346eefa31695`.

### Pre-authenticated production contract checks

| Check | Expected | Result |
| --- | --- | --- |
| `GET /api/health` | HTTP 200, current deployment fingerprint | PASS |
| `GET /api/evidence/options` | HTTP 200, `ok=true` | PASS |
| `GET /api/applications/options` | HTTP 200, `ok=true` | PASS |
| Anonymous `GET /api/evidence/documents` | HTTP 401 | PASS |
| Anonymous `GET /api/evidence/packs` | HTTP 401 | PASS |
| Anonymous `GET /api/applications` | HTTP 401 | PASS |

### Harness refresh validation

- refreshed from PR #14 against current `main` contracts;
- validates response `ok` values and required option values;
- adds explicit case-event creation and a minimum event-history assertion;
- expands anonymous privacy coverage to document, pack, and case reads/writes;
- returns a failing process exit when any assertion or cleanup step fails;
- securely prompts for an existing session token when one is not supplied;
- optionally requests and verifies one OTP when `-TestEmail` is explicitly supplied;
- rejects placeholder login emails locally before requesting an OTP;
- revokes only sessions created by the harness;
- archives the temporary case and document metadata;
- retains the generated evidence pack as an immutable metadata-only audit snapshot because no destructive pack-delete contract is exposed.

### Authenticated production acceptance

Status: **PASS**

User-run PowerShell acceptance completed on 17 August 2026 against production commit `cb65e66a251d336074192bd089b497be89358667`.

| Result | Count |
| --- | ---: |
| PASS | 21 |
| FAIL | 0 |

The accepted run verified:

- production deployment health and account authentication;
- evidence and application contracts;
- temporary evidence create/read;
- evidence pack create/read with `completeness=17`;
- temporary application case create/read;
- explicit case event creation;
- persisted `research` → `preparing` transition;
- three lifecycle events retrieved;
- all five anonymous privacy barriers rejected with HTTP 401;
- case and evidence metadata cleanup;
- immutable metadata-only pack retention;
- OTP-created test-session revocation.

The harness printed neither the OTP nor the session token, and uploaded or stored no raw document.

### Manual actions

- SQL: none for B03;
- environment variables: none for B03;
- phone actions: none required;
- laptop actions: completed;
- blocker: none.

### Next batch boundary

- B03 is closed and B04 may begin;
- do not run the B17 comprehensive regression;
- do not upload real passports, bank statements, certificates, or refusal letters;
- do not paste session tokens or OTPs into chat, screenshots, issues, logs, or repository files.

## B04 — Authentication delivery hardening

### Scope

- reconcile stale PR #13 with current authentication and delivery code;
- add Railway-compatible Mailtrap Sandbox HTTPS transport for bounded test/staging use;
- preserve production Mailtrap, Resend, SMTP, reply-to, timeout, and fail-closed authentication behavior;
- constrain Mailtrap API credentials and OTP payloads to official HTTPS hosts and exact send paths;
- provide bounded, secret-free failure diagnostics;
- document the production/sandbox environment boundary.

### Implementation

Status: **PASS**

- pull request: #13, refreshed against current `main`;
- merge commit: `3739f9338c26753b141627d62510e02f0d6d4668`;
- production Mailtrap provider remains `EMAIL_OTP_PROVIDER=mailtrap`;
- test/staging sandbox provider is `EMAIL_OTP_PROVIDER=mailtrap_sandbox`;
- current sandbox send contract uses `/api/send/{sandbox_id}`;
- arbitrary/custom hosts are rejected before any network request;
- Mailtrap HTTP, connection, and timeout failures do not expose API tokens, recipients, OTPs, provider response bodies, or configured endpoints;
- stale unrelated Resend/SMTP rewrites were removed from the final PR diff.

### Targeted validation

| Check | Result |
| --- | --- |
| Python compile | PASS |
| Sandbox readiness and HTTPS payload contract | PASS |
| Untrusted sandbox endpoint rejected before network | PASS |
| HTTP failure diagnostic redaction | PASS |
| Timeout diagnostic redaction | PASS |
| Production Mailtrap path and reply-to regression | PASS |
| Mailtrap HTTPS API OTP Integration workflow | PASS |
| Backend Smoke Test workflow | PASS |
| Auth and Provider Handoff Integration workflow | PASS |

The bounded unit suite completed with 5 PASS / 0 FAIL. GitHub Actions run `32002802923` completed successfully, including the OTP route fail-closed assertion. No live OTP was sent by the automated B04 tests.

### Manual actions

- SQL: none for B04;
- current Railway production variables: no change required while production remains on the already-working `mailtrap` provider;
- do not set `EMAIL_OTP_PROVIDER=mailtrap_sandbox` in public production because sandbox messages are captured rather than delivered;
- optional test/staging variables: `MAILTRAP_SANDBOX_API_TOKEN` and `MAILTRAP_SANDBOX_ID`;
- blocker: none.

### Next batch boundary

- B04 is closed and B05 may begin;
- do not run the B17 comprehensive regression;
- do not expose OTPs, session tokens, API tokens, recipient addresses, or provider response bodies in chat, screenshots, issues, logs, or repository files.
