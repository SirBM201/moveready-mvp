-- Project MoveReady MVP
-- Account email OTP login foundation.
-- Run after the existing public account/profile/report/watchlist/timeline migrations.
-- Safe to rerun if the tables were partially created before this migration.

create extension if not exists pgcrypto;

create table if not exists public.relocation_auth_login_codes (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.relocation_auth_login_codes
  add column if not exists email text not null,
  add column if not exists code_hash text not null,
  add column if not exists status text not null default 'pending',
  add column if not exists attempts integer not null default 0,
  add column if not exists expires_at timestamptz not null,
  add column if not exists used_at timestamptz,
  add column if not exists source_page text,
  add column if not exists metadata jsonb not null default '{}'::jsonb;

alter table public.relocation_auth_login_codes
  alter column status set default 'pending',
  alter column attempts set default 0,
  alter column metadata set default '{}'::jsonb;

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'relocation_auth_login_codes_status_check'
  ) then
    alter table public.relocation_auth_login_codes
      add constraint relocation_auth_login_codes_status_check
      check (status in ('pending', 'used', 'expired', 'locked'));
  end if;

  if not exists (
    select 1 from pg_constraint where conname = 'relocation_auth_login_codes_attempts_check'
  ) then
    alter table public.relocation_auth_login_codes
      add constraint relocation_auth_login_codes_attempts_check
      check (attempts >= 0 and attempts <= 20);
  end if;
end $$;

create index if not exists relocation_auth_login_codes_email_idx on public.relocation_auth_login_codes (email);
create index if not exists relocation_auth_login_codes_status_idx on public.relocation_auth_login_codes (status);
create index if not exists relocation_auth_login_codes_expires_at_idx on public.relocation_auth_login_codes (expires_at);
create index if not exists relocation_auth_login_codes_created_at_idx on public.relocation_auth_login_codes (created_at desc);

drop trigger if exists relocation_auth_login_codes_set_updated_at on public.relocation_auth_login_codes;
create trigger relocation_auth_login_codes_set_updated_at
before update on public.relocation_auth_login_codes
for each row execute function public.relocation_set_updated_at();

create table if not exists public.relocation_user_sessions (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.relocation_user_sessions
  add column if not exists email text not null,
  add column if not exists token_hash text not null,
  add column if not exists status text not null default 'active',
  add column if not exists expires_at timestamptz not null,
  add column if not exists last_seen_at timestamptz,
  add column if not exists metadata jsonb not null default '{}'::jsonb;

alter table public.relocation_user_sessions
  alter column status set default 'active',
  alter column metadata set default '{}'::jsonb;

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'relocation_user_sessions_status_check'
  ) then
    alter table public.relocation_user_sessions
      add constraint relocation_user_sessions_status_check
      check (status in ('active', 'revoked', 'expired'));
  end if;

  if not exists (
    select 1 from pg_constraint where conname = 'relocation_user_sessions_token_hash_unique'
  ) then
    alter table public.relocation_user_sessions
      add constraint relocation_user_sessions_token_hash_unique unique (token_hash);
  end if;
end $$;

create index if not exists relocation_user_sessions_email_idx on public.relocation_user_sessions (email);
create index if not exists relocation_user_sessions_status_idx on public.relocation_user_sessions (status);
create index if not exists relocation_user_sessions_expires_at_idx on public.relocation_user_sessions (expires_at);
create index if not exists relocation_user_sessions_created_at_idx on public.relocation_user_sessions (created_at desc);

drop trigger if exists relocation_user_sessions_set_updated_at on public.relocation_user_sessions;
create trigger relocation_user_sessions_set_updated_at
before update on public.relocation_user_sessions
for each row execute function public.relocation_set_updated_at();
