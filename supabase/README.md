# MoveReady Supabase Setup

Run these files in order in the Supabase SQL editor for a fresh project.

## 1. Initial schema

`supabase/migrations/001_initial_relocation_schema.sql`

Creates the core relocation tables, indexes, triggers, row-level security flags, source versioning tables, route versioning tables, reports, AI cache, and admin review tasks.

## 2. Starter seed data

`supabase/migrations/002_seed_starter_relocation_data.sql`

Adds conservative starter records for Portugal, Estonia, and Finland plus broad route placeholders and admin review tasks.

## 3. Estonia startup founder route detail

`supabase/migrations/003_seed_estonia_startup_route_detail.sql`

Adds official-source-backed starter detail for the Estonia startup founder pathway, including route facts, document requirements, budget planning items, insurance notes, source links, and an admin review task.

## 4. Service interest requests

`supabase/migrations/004_service_interest_requests.sql`

Adds `relocation_service_interest_requests` so public platform service pages can collect opt-in requests for alerts, courier, insurance, legalization, document readiness, funds planning, refusal risk, and partner support.

## 5. Official opportunities

`supabase/migrations/005_official_opportunities.sql`

Adds `relocation_opportunities` for official lottery, ballot, invitation-pool, annual-quota, country-cap, first-come quota, and seasonal-intake routes. Starter records include USA DV, Canada IEC, Australia subclass 462 ballot/caps, UK India Young Professionals Scheme, New Zealand PAC/Samoan Quota, Hong Kong Working Holiday Scheme, and Japan Working Holiday Programmes.

## 6. Readiness check runs

`supabase/migrations/006_readiness_check_runs.sql`

Adds `relocation_readiness_check_runs` so name consistency, document readiness, proof-of-funds, and refusal-risk checks can be saved for audit, support, and follow-up. The tools still return results if this migration has not been run, but `stored` will remain false.

## Important

The seed data is for MVP testing only. It does not contain final legal or immigration guidance. Detailed route facts should be reviewed and approved from official sources before production use.

## Admin Header

Protected admin API routes accept one of these headers:

- `X-MoveReady-Admin-Key`
- `X-Relocation-Admin-Key`
- `X-Admin-Key`

The backend reads the key from:

- `MOVEREADY_ADMIN_API_KEY`
- `MOVE_READY_ADMIN_API_KEY`
- `ADMIN_API_KEY`
