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
- migration 038 Passport review lifecycle: executed successfully before B03; unrelated to B03 data mutations but part of the current database frontier.

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
- revokes only sessions created by the harness;
- archives the temporary case and document metadata;
- retains the generated evidence pack as an immutable metadata-only audit snapshot because no destructive pack-delete contract is exposed.

### Authenticated production acceptance

Status: **PENDING USER-RUN LAPTOP ACCEPTANCE**

Acceptance requires the refreshed `scripts/test-evidence-application-lifecycle.ps1` harness to finish with:

- `FAIL : 0`;
- `[B03 PASS] Evidence -> Evidence Pack -> Application Case lifecycle is operational.`

After the production output is reviewed, replace this pending status with the run timestamp, production commit, PASS/FAIL counts, and any bounded defect reference.

### Manual actions

- SQL: none for B03;
- environment variables: none for B03;
- phone actions: none required;
- laptop actions: run the refreshed PowerShell harness with an active MoveReady session or one controlled test OTP;
- blocker: authenticated production acceptance output has not yet been supplied.

### Do not do yet

- do not run the B17 comprehensive regression;
- do not upload real passports, bank statements, certificates, or refusal letters;
- do not paste session tokens or OTPs into chat, screenshots, issues, logs, or repository files;
- do not begin B04 until the B03 acceptance result is recorded or a bounded B03 defect is opened.
