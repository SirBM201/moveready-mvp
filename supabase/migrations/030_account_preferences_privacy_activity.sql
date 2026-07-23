-- Project MoveReady MVP
-- Verified-account preferences, onboarding, notification consent, and privacy requests.
-- Run after migration 029. Safe to rerun.

create extension if not exists pgcrypto;

create or replace function public.relocation_set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create table if not exists public.relocation_account_preferences (
  id uuid primary key default gen_random_uuid(),
  email text not null unique,
  preferred_language text not null default 'en',
  preferred_currency text not null default 'USD',
  timezone text not null default 'UTC',
  date_format text not null default 'day_month_year' check (date_format in (
    'day_month_year', 'month_day_year', 'year_month_day'
  )),
  reminder_lead_days integer not null default 7 check (reminder_lead_days between 0 and 90),
  in_app_notifications_enabled boolean not null default true,
  email_notifications_enabled boolean not null default false,
  whatsapp_notifications_enabled boolean not null default false,
  marketing_messages_enabled boolean not null default false,
  source_change_alerts_enabled boolean not null default true,
  application_deadline_alerts_enabled boolean not null default true,
  document_expiry_alerts_enabled boolean not null default true,
  opportunity_alerts_enabled boolean not null default false,
  reduced_motion boolean not null default false,
  high_contrast boolean not null default false,
  simple_language boolean not null default false,
  larger_text boolean not null default false,
  onboarding_status text not null default 'not_started' check (onboarding_status in (
    'not_started', 'in_progress', 'completed', 'skipped'
  )),
  onboarding_step text not null default 'profile' check (onboarding_step in (
    'profile', 'route', 'evidence', 'application', 'alerts', 'completed'
  )),
  consent_version text,
  consent_recorded_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists relocation_account_preferences_email_idx
on public.relocation_account_preferences (email);

drop trigger if exists relocation_account_preferences_set_updated_at
on public.relocation_account_preferences;

create trigger relocation_account_preferences_set_updated_at
before update on public.relocation_account_preferences
for each row execute function public.relocation_set_updated_at();

create table if not exists public.relocation_privacy_requests (
  id uuid primary key default gen_random_uuid(),
  request_ref text not null unique,
  email text not null,
  request_type text not null check (request_type in (
    'data_export', 'correction', 'restriction', 'account_deletion', 'consent_withdrawal', 'other'
  )),
  status text not null default 'received' check (status in (
    'received', 'identity_verification_required', 'reviewing', 'in_progress', 'completed', 'rejected', 'cancelled'
  )),
  priority text not null default 'normal' check (priority in ('low', 'normal', 'high', 'urgent')),
  request_summary text not null,
  requested_scope text,
  user_confirmation boolean not null default false,
  identity_reverification_required boolean not null default true,
  administrator_note text,
  completed_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists relocation_privacy_requests_email_idx
on public.relocation_privacy_requests (email, status, created_at desc);

create index if not exists relocation_privacy_requests_status_idx
on public.relocation_privacy_requests (status, priority, created_at);

drop trigger if exists relocation_privacy_requests_set_updated_at
on public.relocation_privacy_requests;

create trigger relocation_privacy_requests_set_updated_at
before update on public.relocation_privacy_requests
for each row execute function public.relocation_set_updated_at();

-- Destructive or consent-withdrawal requests require explicit user confirmation.
alter table public.relocation_privacy_requests
  drop constraint if exists relocation_privacy_requests_confirmation_check;

alter table public.relocation_privacy_requests
  add constraint relocation_privacy_requests_confirmation_check
  check (
    request_type not in ('account_deletion', 'consent_withdrawal')
    or user_confirmation = true
  );

-- Completed requests must retain a completion timestamp.
alter table public.relocation_privacy_requests
  drop constraint if exists relocation_privacy_requests_completed_check;

alter table public.relocation_privacy_requests
  add constraint relocation_privacy_requests_completed_check
  check (status <> 'completed' or completed_at is not null);

-- These tables are private and backend-only. The browser must never access them
-- directly with Supabase anon or authenticated credentials.
alter table public.relocation_account_preferences enable row level security;
alter table public.relocation_privacy_requests enable row level security;

revoke all privileges on table public.relocation_account_preferences from public, anon, authenticated;
revoke all privileges on table public.relocation_privacy_requests from public, anon, authenticated;

grant all privileges on table public.relocation_account_preferences to service_role;
grant all privileges on table public.relocation_privacy_requests to service_role;

comment on table public.relocation_account_preferences is 'Private verified-account preferences, onboarding state, accessibility choices, and notification consent.';
comment on table public.relocation_privacy_requests is 'Private data-export, correction, restriction, deletion, and consent-withdrawal requests requiring verified-account access.';
comment on column public.relocation_account_preferences.email_notifications_enabled is 'Preference only. External delivery remains unavailable until the configured provider and consent controls pass production checks.';
comment on column public.relocation_account_preferences.whatsapp_notifications_enabled is 'Preference only. WhatsApp delivery remains unavailable until approved credentials, templates, opt-in, and audit controls pass.';

notify pgrst, 'reload schema';
