# Project MoveReady MVP Backend

Working name for a global visa, travel, and relocation readiness platform.

The final brand name and domain will be decided later. This repository holds the backend, database design, API planning, Supabase migrations, and source-verification architecture for the MVP.

## Current Status

Starter Flask backend scaffold is in place, adapted from the working Naija Tax Guide backend pattern but cleaned for MoveReady.

Implemented foundation:

- Flask app factory
- Health endpoints
- Koyeb-ready `Procfile`
- Runtime requirements
- Environment example
- Supabase service-role helper
- Admin API guard
- Public relocation endpoints
- Starter readiness report generator
- Supabase schema and seed SQL

## MVP Mission

Help users compare realistic relocation pathways, understand document and proof-of-funds requirements, estimate costs, and generate source-backed relocation readiness reports.

## Core Principle

AI is not the source of truth.

Approved source records, route versions, and admin-reviewed facts are the source of truth. AI may explain those facts, summarize them, and generate reports, but sensitive answers must be tied to approved source versions and freshness rules.

## API Docs

See `docs/API_ROUTES.md`.

## Supabase Setup

Run these in order when ready:

1. `supabase/migrations/001_initial_relocation_schema.sql`
2. `supabase/migrations/002_seed_starter_relocation_data.sql`

See `supabase/README.md`.

## Not In V1

- Live courier booking
- Flight, hotel, or taxi booking
- Full consultant marketplace
- Full document vault
- Automated embassy appointment booking
- Legal representation

## Next Backend Work

- Add auth/session flow
- Save user profiles
- Connect route checker to approved route versions
- Add route fact admin CRUD
- Add source snapshot capture/review flow
- Add report sections persistence
- Add payment/report purchase flow later
