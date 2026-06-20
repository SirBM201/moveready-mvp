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

## 7. Watchlist alert subscriptions

`supabase/migrations/007_watchlist_alert_subscriptions.sql`

Adds `relocation_watchlist_subscriptions` so users can opt in to route, opportunity, scholarship, country, or service alerts. This stores alert preferences and consent records. Actual WhatsApp, Telegram, email, or in-app message delivery should only be enabled after provider setup, opt-in flow, and audit logging are approved.

## 8. User relocation profiles

`supabase/migrations/008_user_relocation_profiles.sql`

Adds `relocation_user_profiles` so the public dashboard can save a user's relocation profile, target country, route category, timeline, family size, funds, contact preference, previous-refusal flag, notes, and computed readiness snapshot. Admin can review profile records and update follow-up status.

## 19. Account email OTP login

`supabase/migrations/019_account_login_otp.sql`

Adds `relocation_auth_login_codes` and `relocation_user_sessions` for backend-managed email OTP login. Codes and session tokens are stored as hashes. Email delivery remains disabled until an approved provider is configured.

## 20. Account workspace repairs

`supabase/migrations/020_account_workspace_repairs.sql`

Keeps old profile schemas compatible with the current app by making the legacy `goal` column optional/defaulted and aligned with `main_goal`. Also creates `relocation_timeline_events`, which powers Account Center summary and Timeline records.

## 22. Generated report account fields and sections

`supabase/migrations/022_report_account_fields_and_sections.sql`

Adds direct report ownership fields (`email`, `phone`), readiness summary fields, report lookup indexes, and trigger-based sync from `report_payload.sections` into `relocation_report_sections`.

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
