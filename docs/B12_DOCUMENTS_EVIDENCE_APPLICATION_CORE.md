# MoveReady B12 — Documents, Evidence and Application Core

Status: implementation and automated acceptance contract.

## Batch boundary

B12 closes the private preparation journey from document metadata to an immutable evidence-pack snapshot and then to an auditable application case. It builds on the already-proven B03 lifecycle and does not replace its migration or production test harness. B13 dashboard orchestration remains out of scope.

## `b12-v1` contract

The evidence options, document list, evidence-pack list/generation, application options/cases/events/timeline actions, and account-owned link choices expose the `b12-v1` contract marker. `/api/build-info` publishes it as `contract_versions.documents_applications`.

The combined contract preserves these boundaries:

- verified account ownership is required for every private record;
- document inventory stores metadata, not files or complete document numbers;
- evidence packs are retained as historical metadata-only snapshots;
- application references must be masked and raw authority correspondence is rejected;
- application events and deadline reminders remain factual planning records, not authority decisions;
- link-choice failures expose stable error codes instead of database exception details.

## Existing database prerequisites

B12 creates no new database migration and no environment variable. It uses migrations `027_evidence_inventory_and_packs.sql`, `028_application_case_manager.sql`, and `029_application_case_alerts.sql`, which already underpin the B03 lifecycle and alerting.

## Automated acceptance

The evidence, application-case, application-links/privacy, deployment-contract, and Python completion tests verify:

- public options advertise `b12-v1`;
- private endpoints remain fail-closed without a verified session;
- forbidden raw/sensitive fields and unmasked references remain rejected;
- lifecycle transitions, terminal invariants, event history, deadlines, and timeline task safety remain intact;
- `/api/applications/links` is part of the deployment route contract;
- public build information exposes the version and privacy boundary without secrets.

## Production acceptance to perform later

1. Confirm `/api/build-info` reports `contract_versions.documents_applications=b12-v1`.
2. Sign in, record metadata for one non-sensitive test document, and generate an evidence pack.
3. Open Application Center, choose that pack without copying its UUID, and create a private case.
4. Record a stage change and a short event, then verify the auditable history and deadline display.
5. Confirm signed-out, empty, partial-failure, and retry states are distinct on a phone-sized screen.

Never paste or upload passports, bank statements, certificates, complete references, raw authority correspondence, OTPs, session tokens, passwords, card data, or private keys.
