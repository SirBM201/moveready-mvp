# MoveReady Launch Runbook

This document keeps the launch steps in the repo so deployment and Supabase setup do not depend on chat history.

## Required SQL order

Run the Supabase migrations in order:

1. `supabase/migrations/001_initial_relocation_schema.sql`
2. `supabase/migrations/002_seed_starter_relocation_data.sql`
3. `supabase/migrations/003_seed_estonia_startup_route.sql`
4. `supabase/migrations/004_service_interest_requests.sql`
5. `supabase/migrations/005_opportunities.sql`
6. `supabase/migrations/006_readiness_check_runs.sql`
7. `supabase/migrations/007_watchlist_subscriptions.sql`
8. `supabase/migrations/008_user_profiles.sql`
9. `supabase/migrations/009_saved_routes.sql`
10. `supabase/migrations/010_timeline_events.sql`
11. `supabase/migrations/011_partner_applications.sql`
12. `supabase/migrations/013_seed_finland_d_visa_route_fixed.sql`

Use `013_seed_finland_d_visa_route_fixed.sql` for the Finland D visa route. Do not rerun the older broken Finland seed if it contains `applies_to = 'family_member'` for `relocation_document_requirements`.

## Finland D visa SQL fix

The schema check constraint for `relocation_document_requirements.applies_to` accepts values such as:

- `main_applicant`
- `spouse`
- `child`
- `sponsor`
- `employer`
- `school`
- `other`

It does not accept `family_member`.

The fixed Finland migration splits family documents into valid rows:

- `Spouse family-ties documents` with `applies_to = 'spouse'`
- `Child family-ties documents` with `applies_to = 'child'`

## Backend checks

After Railway deploys, test:

```text
/health
/api/health
/api/relocation/countries
/api/relocation/routes
/api/relocation/routes/by-code/EE/startup-founder
/api/relocation/routes/by-code/FI/d-visa
/api/watchlist/options
/api/platform/status
```

Expected behavior:

- Health endpoints return `ok: true`.
- Countries include Portugal, Estonia, and Finland.
- Estonia startup and Finland D visa route details return live route records after seed SQL is active.
- Watchlist options return alert types, channels, and watch types.
- Platform status returns public-safe availability labels.

## Frontend checks

After Vercel deploys, test:

```text
/
/workspace
/trust
/sources
/launch-readiness
/route-checker
/country-checker
/routes/estonia-startup
/routes/finland-d-visa
/opportunities
/watchlist
/saved-routes
/timeline
/readiness
/services
/courier
/legalization
/family-planner
/settlement
/startup-evidence
/partners/apply
/my-reports
/admin
```

## Public wording rules

Use public-safe labels:

- `Available`
- `Coming soon`
- `Partner approval pending`
- `Source-backed`
- `Admin review required`

Avoid public UI labels such as:

- `planned`
- `phase 2`
- `phase 3`

Those are internal planning terms and should not appear in user-facing product pages.

## Safety rules

- Do not promise visa approval, lottery selection, residence approval, appointment availability, scholarship award, courier success, or provider quality.
- Use official links for lotteries and ballots.
- Require opt-in before notifications.
- Require provider review before any public handoff.
- Keep sensitive-document courier as a trusted service workflow, not a casual booking feature.
- Treat AI as an explanation layer, not the source of truth.
