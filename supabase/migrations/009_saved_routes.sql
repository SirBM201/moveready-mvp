-- Project MoveReady MVP
-- Saved route and opportunity storage.
-- Run after 001 through 008 migrations.
-- Safe to rerun if the table was partially created before this migration.

create extension if not exists pgcrypto;

create table if not exists public.relocation_saved_routes (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.relocation_saved_routes add column if not exists save_type text not null default 'route';
alter table public.relocation_saved_routes add column if not exists route_id uuid;
alter table public.relocation_saved_routes add column if not exists route_version_id uuid;
alter table public.relocation_saved_routes add column if not exists opportunity_id uuid;
alter table public.relocation_saved_routes add column if not exists country_id uuid;
alter table public.relocation_saved_routes add column if not exists route_code text;
alter table public.relocation_saved_routes add column if not exists country_code text;
alter table public.relocation_saved_routes add column if not exists saved_title text;
alter table public.relocation_saved_routes add column if not exists full_name text;
alter table public.relocation_saved_routes add column if not exists email text;
alter table public.relocation_saved_routes add column if not exists phone text;
alter table public.relocation_saved_routes add column if not exists current_country text;
alter table public.relocation_saved_routes add column if not exists target_country text;
alter table public.relocation_saved_routes add column if not exists main_goal text;
alter table public.relocation_saved_routes add column if not exists route_category text;
alter table public.relocation_saved_routes add column if not exists notes text;
alter table public.relocation_saved_routes add column if not exists notify_on_changes boolean not null default false;
alter table public.relocation_saved_routes add column if not exists consent_to_contact boolean not null default false;
alter table public.relocation_saved_routes add column if not exists status text not null default 'active';
alter table public.relocation_saved_routes add column if not exists source_page text;
alter table public.relocation_saved_routes add column if not exists metadata jsonb not null default '{}'::jsonb;

alter table public.relocation_saved_routes alter column save_type set default 'route';
alter table public.relocation_saved_routes alter column notify_on_changes set default false;
alter table public.relocation_saved_routes alter column consent_to_contact set default false;
alter table public.relocation_saved_routes alter column status set default 'active';
alter table public.relocation_saved_routes alter column metadata set default '{}'::jsonb;

update public.relocation_saved_routes
set saved_title = coalesce(saved_title, route_code, country_code, 'Saved route')
where saved_title is null;

alter table public.relocation_saved_routes alter column saved_title set not null;

create or replace function public.relocation_set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'relocation_saved_routes_save_type_check'
      and conrelid = 'public.relocation_saved_routes'::regclass
  ) then
    alter table public.relocation_saved_routes
      add constraint relocation_saved_routes_save_type_check
      check (save_type in ('route', 'opportunity', 'scholarship', 'country', 'service'));
  end if;
end $$;

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'relocation_saved_routes_status_check'
      and conrelid = 'public.relocation_saved_routes'::regclass
  ) then
    alter table public.relocation_saved_routes
      add constraint relocation_saved_routes_status_check
      check (status in ('active', 'archived', 'closed', 'spam'));
  end if;
end $$;

create index if not exists relocation_saved_routes_email_idx on public.relocation_saved_routes (email);
create index if not exists relocation_saved_routes_phone_idx on public.relocation_saved_routes (phone);
create index if not exists relocation_saved_routes_status_idx on public.relocation_saved_routes (status);
create index if not exists relocation_saved_routes_save_type_idx on public.relocation_saved_routes (save_type);
create index if not exists relocation_saved_routes_route_code_idx on public.relocation_saved_routes (route_code);
create index if not exists relocation_saved_routes_country_code_idx on public.relocation_saved_routes (country_code);
create index if not exists relocation_saved_routes_created_at_idx on public.relocation_saved_routes (created_at desc);

drop trigger if exists relocation_saved_routes_set_updated_at on public.relocation_saved_routes;
create trigger relocation_saved_routes_set_updated_at
before update on public.relocation_saved_routes
for each row execute function public.relocation_set_updated_at();
