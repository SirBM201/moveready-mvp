# MoveReady Supabase Setup

Run these files in order in the Supabase SQL editor for a fresh project.

## 1. Initial schema

`supabase/migrations/001_initial_relocation_schema.sql`

Creates the core relocation tables, indexes, triggers, row-level security flags, source versioning tables, route versioning tables, reports, AI cache, and admin review tasks.

## 2. Starter seed data

`supabase/migrations/002_seed_starter_relocation_data.sql`

Adds conservative starter records for Portugal, Estonia, and Finland plus broad route placeholders and admin review tasks.

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
