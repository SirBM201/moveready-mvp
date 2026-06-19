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
- User relocation profile endpoint with readiness snapshot storage
- Saved report lookup endpoint by report reference, email, or phone
- Live readiness tools for name consistency, documents, funds, and refusal risk
- Optional readiness check persistence
- Starter readiness report generator
- Supabase schema and seed SQL
- Service availability endpoints and feature flags
- Service interest/request capture endpoint
- Admin endpoints for user profiles, generated reports, service requests, watchlist subscriptions, and readiness checks

## MVP Mission

Help users compare realistic relocation pathways, understand document and proof-of-funds requirements, estimate costs, and generate source-backed relocation readiness reports.

## Core Principle

AI is not the source of truth.

Approved source records, route versions, and admin-reviewed facts are the source of truth. AI may explain those facts, summarize them, and generate reports, but sensitive answers must be tied to approved source versions and freshness rules.

## Platform Direction

MoveReady is designed as a global relocation readiness and opportunity monitoring platform. The service architecture includes official ballots/quota opportunities, watchlists, alerts, document checks, proof-of-funds planning, refusal analysis, legalization, courier, appointments, family planning, settlement, and partner services.

Services that require provider approval, user opt-in, or additional compliance checks return launch-safe availability labels until they are ready.

See `docs/BATCH_2A_PLATFORM_ARCHITECTURE.md`.

## API Docs

See `docs/API_ROUTES.md` and `docs/ADMIN_GENERATED_REPORTS.md`.

## Account and Login Design

See `docs/ACCOUNT_LOGIN_DESIGN.md` for the phased identity plan: contact-based MVP lookup, email OTP login, and paid account features.

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

See `supabase/README.md`.

## Approval-Gated Services

- Live courier booking
- Flight, hotel, or taxi booking
- Full consultant marketplace
- Full document vault
- Automated embassy appointment monitoring
- Legal representation
- WhatsApp message delivery
- Partner insurance quotes

## Next Backend Work

- Add auth/session flow
- Add route fact admin CRUD
- Add source snapshot capture/review flow
- Add report sections persistence
- Add PDF report export
- Add payment/report purchase flow later
