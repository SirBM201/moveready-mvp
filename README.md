# Project MoveReady MVP

Working name for a global visa, travel, and relocation readiness platform.

The final brand name and domain will be decided later. This repository holds the backend, database design, API planning, Supabase migrations, and source-verification architecture for the MVP.

## MVP Mission

Help users compare realistic relocation pathways, understand document and proof-of-funds requirements, estimate costs, and generate source-backed relocation readiness reports.

## Core Principle

AI is not the source of truth.

Approved source records, route versions, and admin-reviewed facts are the source of truth. AI may explain those facts, summarize them, and generate reports, but sensitive answers must be tied to approved source versions and freshness rules.

## Initial Scope

- Country and route data
- Visa route versions
- Trusted source records
- Source snapshots and review tasks
- Document checklist records
- Proof-of-funds guidance records
- Budget calculator records
- Scholarship records
- Insurance requirement records
- AI answer cache tied to route/source versions
- Generated relocation readiness reports

## First Files

- `docs/STEP_1A_MVP_SCOPE.md`
- `docs/STEP_1B_DATABASE_ARCHITECTURE.md`
- `supabase/migrations/001_initial_relocation_schema.sql`

## Not In V1

- Live courier booking
- Flight, hotel, or taxi booking
- Full consultant marketplace
- Full document vault
- Automated embassy appointment booking
- Legal representation
