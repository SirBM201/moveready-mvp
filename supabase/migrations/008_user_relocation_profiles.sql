-- Project MoveReady MVP
-- User relocation profile storage.
-- Run after 001 through 007 migrations.
-- Safe to rerun if the table was partially created before this migration.

create extension if not exists pgcrypto;

create table if not exists public.relocation_user_profiles (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.relocation_user_profiles
  add column if not exists full_name text,
  add column if not exists email text,
  add column if not exists phone text,
  add column if not exists current_country text,
  add column if not exists nationality text,
  add column if not exists residence_country text,
  add column if not exists target_country text,
  add column if not exists target_city text,
  add column if not exists main_goal text not null default 'relocation',
  add column if not exists route_category text,
  add column if not exists timeline_months integer,
  add column if not exists family_members_count integer not null default 0,
  add column if not exists available_funds_amount numeric,
  add column if not exists available_funds_currency text default 'USD',
  add column if not exists education_level text,
  add column if not exists work_experience_years numeric,
  add column if not exists business_stage text,
  add column if not exists has_previous_refusal boolean not null default false,
  add column if not exists preferred_contact_channel text not null default 'email',
  add column if not exists consent_to_contact boolean not null default false,
  add column if not exists readiness_snapshot jsonb not null default '{}'::jsonb,
  add column if not exists notes text,
  add column if not exists source_page text,
  add column if not exists status text not null default 'new',
  add column if not exists metadata jsonb not null default '{}'::jsonb;

alter table public.relocation_user_profiles
  alter column main_goal set default 'relocation',
  alter column family_members_count set default 0,
  alter column available_funds_currency set default 'USD',
  alter column has_previous_refusal set default false,
  alter column preferred_contact_channel set default 'email',
  alter column consent_to_contact set default false,
  alter column readiness_snapshot set default '{}'::jsonb,
  alter column status set default 'new',
  alter column metadata set default '{}'::jsonb;

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'relocation_user_profiles_main_goal_check'
  ) then
    alter table public.relocation_user_profiles
      add constraint relocation_user_profiles_main_goal_check
      check (main_goal in ('study', 'scholarship', 'work', 'startup', 'business', 'digital_nomad', 'family', 'visit', 'opportunity', 'relocation'));
  end if;

  if not exists (
    select 1 from pg_constraint where conname = 'relocation_user_profiles_contact_channel_check'
  ) then
    alter table public.relocation_user_profiles
      add constraint relocation_user_profiles_contact_channel_check
      check (preferred_contact_channel in ('email', 'whatsapp', 'telegram', 'phone'));
  end if;

  if not exists (
    select 1 from pg_constraint where conname = 'relocation_user_profiles_status_check'
  ) then
    alter table public.relocation_user_profiles
      add constraint relocation_user_profiles_status_check
      check (status in ('new', 'reviewing', 'contacted', 'active', 'closed', 'spam'));
  end if;
end $$;

create index if not exists relocation_user_profiles_email_idx on public.relocation_user_profiles (email);
create index if not exists relocation_user_profiles_goal_idx on public.relocation_user_profiles (main_goal);
create index if not exists relocation_user_profiles_target_country_idx on public.relocation_user_profiles (target_country);
create index if not exists relocation_user_profiles_status_idx on public.relocation_user_profiles (status);
create index if not exists relocation_user_profiles_created_at_idx on public.relocation_user_profiles (created_at desc);

drop trigger if exists relocation_user_profiles_set_updated_at on public.relocation_user_profiles;
create trigger relocation_user_profiles_set_updated_at
before update on public.relocation_user_profiles
for each row execute function public.relocation_set_updated_at();
