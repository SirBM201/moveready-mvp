# Project MoveReady MVP Backend

Working name for a global visa, travel, and relocation readiness platform.

The final brand name and domain will be decided later. This repository holds the backend, database design, API planning, Supabase migrations, and source-verification architecture for the MVP.

## Current Status

Starter Flask backend scaffold is in place, adapted from the working Naija Tax Guide backend pattern but cleaned for MoveReady.

Implemented foundation:

- Flask app factory
- Health endpoints
- Koyeb/Railway-ready `Procfile`
- Runtime requirements
- Environment example
- Supabase service-role helper
- Admin API guard
- Public relocation endpoints
- Stable route detail by country and route code
- Official opportunities endpoint for lotteries, ballots, invitation pools, caps, and quotas
- Watchlist subscription endpoint for routes, opportunities, scholarships, countries, and services
- Visa Power API for passport-index and existing-visa travel-benefit checks
- Provider-ready Passport Index cache with twice-weekly sync design
- Passport rating, passport opportunity score, access buckets, source status, and last-synced fields
- User relocation profile endpoint with readiness snapshot storage
- Account email OTP and session-token foundation
- Authenticated account summary endpoint
- Session-token ownership attachment for account-owned writes
- Saved report lookup endpoint by report reference, email, or phone
- Deterministic readiness report generator with score, risk flags, route-fit questions, document gaps, funds pressure, and action plan
- Report account ownership fields and report-section persistence
- Live readiness tools for name consistency, documents, funds, and refusal risk
- Optional readiness check persistence
- Supabase schema and seed SQL
- Service availability endpoints and feature flags
- Service interest/request capture endpoint
- Admin endpoints for user profiles, generated reports, service requests, watchlist subscriptions, and readiness checks
- Authenticated Jobs workspace for companies, recruiters, recorded vacancies, applications, resume versions, and interview preparation
- Private Resume Vault storage with PDF, DOCX, and TXT validation and short-lived signed downloads

## MVP Mission

Help users compare realistic relocation pathways, understand document and proof-of-funds requirements, estimate costs, check visa/travel benefits they may already have, and generate source-backed relocation readiness reports.

## Core Principle

AI is not the source of truth.

Approved source records, route versions, visa-benefit rules, passport provider cache records, and admin-reviewed facts are the source of truth. AI may explain those facts, summarize them, and generate reports, but sensitive answers must be tied to approved source versions and freshness rules.

## Platform Direction

MoveReady is designed as a global relocation readiness and opportunity monitoring platform. The service architecture includes official ballots/quota opportunities, passport-index and Visa Power checks, watchlists, alerts, document checks, proof-of-funds planning, refusal analysis, legalization, courier, appointments, family planning, settlement, and partner services.

Services that require provider approval, user opt-in, or additional compliance checks return launch-safe availability labels until they are ready.

See `docs/BATCH_2A_PLATFORM_ARCHITECTURE.md`.

## API Docs

See `docs/API_ROUTES.md`, `docs/VISA_POWER_API.md`, and `docs/ADMIN_GENERATED_REPORTS.md`.

Visa Power endpoints now include:

- `GET /api/visa-power/options`
- `GET /api/visa-power/provider/status`
- `POST /api/visa-power/provider/sync`
- `GET /api/visa-power/passport-index/options`
- `POST /api/visa-power/passport-index/check`
- `POST /api/visa-power/check`

Jobs endpoints now include:

- `GET /api/jobs/options`
- `GET|PATCH /api/jobs/profile`
- `POST /api/jobs/profile/bootstrap`
- `GET /api/jobs/summary`
- `GET|POST /api/jobs/companies`
- `PATCH /api/jobs/companies/<company_id>/tracking`
- `GET|POST /api/jobs/recruiters`
- `PATCH /api/jobs/recruiters/<recruiter_id>`
- `GET|POST /api/jobs`
- `PATCH /api/jobs/<job_id>`
- `GET|POST /api/jobs/applications`
- `PATCH /api/jobs/applications/<application_id>`
- `GET|POST /api/jobs/resume-vault`
- `PATCH /api/jobs/resume-vault/<document_id>`
- `GET /api/jobs/resume-vault/<document_id>/download`

## Passport Provider Cache

MoveReady is provider-ready without forcing paid API calls on every user click.

Recommended launch behaviour:

1. A twice-weekly scheduled job calls `POST /api/visa-power/provider/sync`.
2. The backend fetches passport access data from the configured provider.
3. The backend stores the provider payload, normalized passport rating, country access buckets, source fields, and sync timestamps in Supabase.
4. Public users click **Check my passport** and read cached results immediately.
5. If no provider is configured yet, MoveReady safely falls back to starter guidance and clearly labels it as starter/pending review.

Required provider environment variables when a paid/free provider is selected:

- `PASSPORT_INDEX_PROVIDER_ENABLED=true`
- `PASSPORT_INDEX_PROVIDER_NAME=Provider name`
- `PASSPORT_INDEX_PROVIDER_URL=https://provider-endpoint.example/path/{country_key}`
- `PASSPORT_INDEX_PROVIDER_KEY=provider-secret-key`
- `PASSPORT_INDEX_PROVIDER_METHOD=GET` or `POST`

GitHub Actions workflow `.github/workflows/passport-index-sync.yml` runs Tuesday and Friday at 06:00 UTC. Add repository secrets:

- `MOVEREADY_ADMIN_API_KEY`
- Optional: `MOVEREADY_API_BASE` if the Railway URL changes.

## Account and Login Design

See `docs/ACCOUNT_LOGIN_DESIGN.md` for the phased identity plan: contact-based MVP lookup, email OTP login, and paid account features.

Auth endpoints now include:

- `GET /api/auth/health`
- `POST /api/auth/request-code`
- `POST /api/auth/verify-code`
- `GET /api/auth/me`
- `POST /api/auth/logout`

Authenticated account endpoints now include:

- `GET /api/account/health`
- `GET /api/account/summary`

Email delivery is disabled until an approved provider is configured. Codes and session tokens are stored as hashes.

## Supabase Setup

Run these in order when ready:

1. `supabase/migrations/001_initial_relocation_schema.sql`
2. `supabase/migrations/002_seed_starter_relocation_data.sql`
3. `supabase/migrations/003_seed_estonia_startup_route_detail.sql`
4. `supabase/migrations/004_service_interest_requests.sql`
5. `supabase/migrations/005_official_opportunities.sql`
6. `supabase/migrations/006_readiness_check_runs.sql`
7. `supabase/migrations/007_watchlist_alert_subscriptions.sql`
8. `supabase/migrations/008_user_relocation_profiles.sql`
9. `supabase/migrations/019_account_login_otp.sql`
10. `supabase/migrations/020_account_workspace_repairs.sql`
11. `supabase/migrations/022_report_account_fields_and_sections.sql`
12. `sql/026_generated_reports_account_owner.sql`
13. `supabase/migrations/027_passport_index_provider_cache.sql`
14. Continue applying the numbered migrations in order through `supabase/migrations/031_jobs_execution_platform.sql`.

Migration 020 keeps legacy `goal` profile schemas compatible with the current `main_goal` payload and creates the account timeline-events table used by Account Center summaries.

Migration 022 adds direct generated-report account fields and syncs report sections from `report_payload.sections` into `relocation_report_sections`.

SQL 026 backfills generated-report account ownership fields from stored input/report payloads and adds indexes for account report lookup.

Migration 027 adds the provider-cache tables for passport ratings, destination access buckets, provider payloads, source review fields, and sync-run logs.

Migration 031 creates the private Jobs data model, the curated company directory, account-owned recruiter and application records, and the private `job-resume-vault` Storage bucket.
