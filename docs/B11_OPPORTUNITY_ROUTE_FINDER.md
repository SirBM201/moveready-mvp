# MoveReady B11 — Opportunity / Route Finder core

Status: implementation and acceptance contract.

## Batch boundary

B11 completes the current FIND → QUALIFY route-finding foundation. It extends the existing profile-driven Opportunity Finder and Route Checker; it does not create another profile store, predict approval, or introduce B12 document/application UX.

## Private recommendation contract

`GET /api/opportunity-finder/recommendations` requires a verified MoveReady account session and returns `contract_version=b11-v1`.

The response includes:

- a privacy-limited snapshot of relevant profile fields (never name, email or phone);
- ranked pathway alignment with an explicit `profile_alignment_not_eligibility` score kind;
- known signals and gaps, while keeping qualification `not_determined`;
- public route candidates for the recorded jurisdiction;
- route evidence requirements;
- recorded planning-cost ranges without currency conversion or invented multipliers;
- recorded processing/validity and refusal-risk notes;
- jurisdiction, verified/review-due dates, freshness, confidence and linked HTTPS official sources;
- exact Route Checker, Compare, Financial Readiness and Evidence next actions;
- reviewed public opportunity records for the target jurisdiction.

The response fails closed when a route lacks a current verification date, a current official-source link, or a reviewed route record. Missing provenance is labelled `source_review_required`; it is never silently presented as verified.

## Shared public route detail

`GET /api/relocation/routes/<route_id>` and `GET /api/relocation/routes/by-code/<country_code>/<route_code>` now expose one shared detail contract containing:

- route/version facts;
- document requirements;
- budget items;
- insurance requirements;
- linked trusted-source records.

Route Comparison and Financial Readiness use the same reusable route-detail helper. This removes the previous internal helper mismatch that could force database-backed reads into starter fallback data.

## Exact Route Checker binding

The frontend action `/route-checker?country=<code>&route=<code>` resolves the exact public route before report generation. When found, it submits `country_id` and `route_version_id` to checklist, budget and report endpoints. When the lookup fails, the UI warns that route-specific IDs will not be submitted instead of pretending the generic form is the requested route.

## Database and environment decision

- Supabase migration: none;
- Railway environment variables: none;
- frontend environment variables: none;
- new secrets: none.

Existing profile, country, route/version, document, budget, trusted-source, route-source and opportunity tables already support B11.

## Automated acceptance

Backend:

```bash
python -m compileall -q app
python -m unittest discover -s tests -p "test_opportunity_finder*.py" -v
python -m unittest discover -s tests -p "test_v1_completion_contract.py" -v
```

Frontend:

```bash
npm run test:b11
npm run build
```

GitHub Actions verifies the B11 response contract, verified-session privacy barrier, fail-closed source provenance, route evidence/cost/timeline/risk fields, exact Route Checker binding, regression contracts and the full Next.js production build.

## Production acceptance to perform later

1. Confirm Railway `/api/build-info` reports `contract_versions.opportunity_finder=b11-v1` at the merged backend commit.
2. Sign in with a profile that has a target country and open `/find`.
3. Confirm score copy says profile alignment, not eligibility.
4. Open a route candidate and verify evidence, costs, risk/timeline notes, freshness and official-source links.
5. Select **Check this exact route** and confirm Route Checker displays the same route/country before generating.
6. Confirm signed-out Finder access returns the sign-in state and does not expose private profile data.
7. Confirm a missing/expired source is labelled for review rather than current.

Do not paste passports, application documents, bank statements, session tokens or complete authority reference numbers into chat, issues, logs or repository files.
