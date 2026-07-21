-- Project MoveReady MVP
-- Passport Index provider cache and destination access rows.
-- Safe to rerun.

create extension if not exists pgcrypto;

create table if not exists public.relocation_passport_index_cache (
    id uuid primary key default gen_random_uuid(),
    country_key text not null unique,
    passport_country text not null,
    source_provider text,
    provider_payload jsonb not null default '{}'::jsonb,
    passport_index_payload jsonb not null default '{}'::jsonb,
    passport_rank integer,
    passport_opportunity_score integer,
    passport_strength_band text,
    visa_free_count integer,
    visa_on_arrival_count integer,
    evisa_count integer,
    visa_required_count integer,
    last_synced_at timestamptz,
    last_reviewed_at timestamptz,
    next_sync_due_at timestamptz,
    source_status text default 'provider_cache_pending_admin_review',
    confidence text default 'provider_cache_pending_admin_review',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.relocation_passport_destination_access (
    id uuid primary key default gen_random_uuid(),
    country_key text not null,
    passport_country text not null,
    destination text not null,
    destination_region text,
    access_bucket text not null,
    access_type text,
    maximum_stay text,
    conditions text,
    official_source_name text,
    official_source_url text,
    last_verified_at timestamptz,
    confidence text default 'provider_cache_pending_admin_review',
    source_status text default 'provider_cache_pending_admin_review',
    source_provider text,
    provider_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint relocation_passport_destination_access_bucket_check check (
        access_bucket in ('visa_free', 'visa_on_arrival', 'evisa', 'visa_required')
    )
);

create table if not exists public.relocation_passport_provider_sync_runs (
    id uuid primary key default gen_random_uuid(),
    source_provider text,
    status text not null,
    details jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists relocation_passport_index_cache_country_idx
    on public.relocation_passport_index_cache (country_key);

create index if not exists relocation_passport_index_cache_sync_idx
    on public.relocation_passport_index_cache (next_sync_due_at, last_synced_at);

create index if not exists relocation_passport_destination_country_idx
    on public.relocation_passport_destination_access (country_key, access_bucket, destination);

create index if not exists relocation_passport_provider_sync_runs_created_idx
    on public.relocation_passport_provider_sync_runs (created_at desc);

create unique index if not exists relocation_passport_destination_unique_idx
    on public.relocation_passport_destination_access (country_key, lower(destination), access_bucket);
