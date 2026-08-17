# MoveReady B09 — Financial Readiness V1 backend

Status: implementation and acceptance contract.

## Batch boundary

B09 completes the Financial Readiness V1 backend by extending the current readiness architecture. It salvages the reusable calculation idea from stale PR #11 without carrying forward its invented family multiplier or treating an unsourced number as an official requirement.

B10 frontend integration, account UX, and mobile acceptance remain outside this batch.

## B09 contract

Both `POST /api/financial-readiness/check` and the backward-compatible `POST /api/readiness/funds-plan` expose `contract_version=b09-v1`.

The model keeps these inputs and outputs explicit:

- current savings;
- expected funding, shown separately from current savings;
- the entered proof-of-funds requirement and its HTTPS source reference;
- fees, tuition, relocation, flight, accommodation, and settlement reserve;
- family size as planning context;
- target date or target timeline;
- combined entered target, funding gap, surplus, and monthly savings target.

Family size never changes a funds requirement through a MoveReady percentage or formula. The user must enter the current authority requirement for the exact route and household. If that requirement is missing, the assessment fails closed with `requirements_needed`. If the amount has no HTTPS source reference, it returns `source_review_required`.

The calculator does not convert currencies. A proof-of-funds or cost currency mismatch blocks the combined target, funding-gap, and monthly-target calculation.

## Route estimates and user scenarios

`/api/financial-readiness/check` continues to return the original route cost range used by the current budget-calculator UI. It also returns `financial_plan`, the complete B09 result.

Route budget records are planning estimates and use their maximum value as the scenario amount. A user-entered category replaces the same route-estimate category. The response labels every cost item with its source type and amount basis; it never represents a route estimate as an official fee or proof-of-funds threshold.

The calculation adds the entered proof-of-funds amount and planned costs. Because authority rules may allow some amounts to overlap, the response explicitly requires the user to confirm overlap against the cited source.

## Backward compatibility

The legacy readiness response still includes `available_funds`, `required_funds_adjusted`, `shortfall`, `monthly_savings_target`, `risk_level`, and `readiness_status`.

`required_funds_adjusted` now equals the exact user-entered requirement. It is no longer multiplied by 45% per additional family member. Existing readiness-run storage remains available through `relocation_readiness_check_runs`.

## Database and environment decision

- Supabase migration: none;
- Railway environment variables: none;
- new secrets: none.

The existing route-budget records and readiness-run JSON payload columns already support the B09 contract. No new table or schema column is required.

## Automated acceptance

Run:

```bash
python -m compileall -q app
python -m unittest discover -s tests -p "test_financial_readiness*.py" -v
```

GitHub Actions workflow `Financial Readiness Integration` verifies:

- sourced and unsourced proof-of-funds boundaries;
- all six V1 cost categories;
- savings plus expected-funding totals;
- family-size context without an invented multiplier;
- target-date and monthly-savings calculations;
- currency-mismatch fail-closed behavior;
- invalid input rejection;
- route-estimate and user-override behavior;
- legacy response compatibility;
- registered API and build-info contracts.

## Production acceptance to perform later

1. Confirm Railway serves a commit containing `contract_versions.financial_readiness=b09-v1` in `/api/build-info`.
2. Run one route-backed plan with a current HTTPS authority source and matching currencies.
3. Confirm a missing requirement returns `requirements_needed` and an unsourced amount returns `source_review_required`.
4. Confirm changing family size alone does not change the entered proof-of-funds amount.
5. Confirm expected funding remains separate from current savings.
6. Confirm a currency mismatch produces no combined target or funding gap.

Do not paste bank statements, account numbers, transaction histories, session tokens, or private financial documents into chat, issues, logs, or repository files.
