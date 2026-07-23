-- Project MoveReady MVP
-- Consent-based provider handoffs, handoff audit events, and private support cases.
-- Run after migrations 023 and 024.
-- Safe to rerun.

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

create table if not exists public.relocation_service_handoffs (
  id uuid primary key default gen_random_uuid(),
  handoff_ref text not null unique,
  quote_id uuid not null references public.relocation_commercial_quotes(id) on delete restrict,
  service_request_id uuid,
  provider_application_id uuid not null references public.relocation_partner_applications(id) on delete restrict,
  full_name text,
  email text not null,
  phone text,
  service_slug text not null,
  service_title text not null,
  provider_name text not null,
  status text not null default 'pending_user_consent' check (status in (
    'draft',
    'pending_user_consent',
    'consent_confirmed',
    'ready_to_share',
    'shared',
    'provider_acknowledged',
    'in_progress',
    'completed',
    'cancelled',
    'blocked',
    'disputed'
  )),
  payment_required boolean not null default true,
  shared_fields jsonb not null default '[]'::jsonb,
  handoff_summary text not null,
  user_consent_required boolean not null default true,
  user_consent_confirmed boolean not null default false,
  consent_version text,
  consent_payload jsonb not null default '{}'::jsonb,
  consented_at timestamptz,
  prepared_at timestamptz not null default now(),
  shared_at timestamptz,
  provider_acknowledged_at timestamptz,
  completed_at timestamptz,
  delivery_channel text,
  delivery_reference text,
  admin_owner text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists relocation_service_handoffs_ref_idx
on public.relocation_service_handoffs (handoff_ref);

create index if not exists relocation_service_handoffs_email_idx
on public.relocation_service_handoffs (email, created_at desc);

create index if not exists relocation_service_handoffs_status_idx
on public.relocation_service_handoffs (status, created_at desc);

create index if not exists relocation_service_handoffs_quote_idx
on public.relocation_service_handoffs (quote_id);

create index if not exists relocation_service_handoffs_provider_idx
on public.relocation_service_handoffs (provider_application_id);

drop trigger if exists relocation_service_handoffs_set_updated_at
on public.relocation_service_handoffs;

create trigger relocation_service_handoffs_set_updated_at
before update on public.relocation_service_handoffs
for each row execute function public.relocation_set_updated_at();

create table if not exists public.relocation_service_handoff_events (
  id uuid primary key default gen_random_uuid(),
  handoff_id uuid not null references public.relocation_service_handoffs(id) on delete cascade,
  event_type text not null,
  event_status text not null default 'recorded',
  actor_type text not null,
  actor_reference text,
  event_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists relocation_service_handoff_events_handoff_idx
on public.relocation_service_handoff_events (handoff_id, created_at desc);

create table if not exists public.relocation_support_cases (
  id uuid primary key default gen_random_uuid(),
  case_ref text not null unique,
  quote_id uuid references public.relocation_commercial_quotes(id) on delete set null,
  handoff_id uuid references public.relocation_service_handoffs(id) on delete set null,
  full_name text,
  email text not null,
  phone text,
  case_type text not null check (case_type in (
    'general_support',
    'complaint',
    'refund_request',
    'payment_dispute',
    'provider_issue',
    'privacy_issue',
    'service_quality',
    'technical_issue',
    'other'
  )),
  status text not null default 'open' check (status in (
    'open',
    'reviewing',
    'waiting_user',
    'waiting_provider',
    'escalated',
    'resolved',
    'rejected',
    'closed'
  )),
  priority text not null default 'medium' check (priority in ('low', 'medium', 'high', 'critical')),
  subject text not null,
  description text not null,
  requested_resolution text,
  resolution_summary text,
  assigned_to text,
  source_page text,
  metadata jsonb not null default '{}'::jsonb,
  resolved_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists relocation_support_cases_ref_idx
on public.relocation_support_cases (case_ref);

create index if not exists relocation_support_cases_email_idx
on public.relocation_support_cases (email, created_at desc);

create index if not exists relocation_support_cases_status_idx
on public.relocation_support_cases (status, priority, created_at desc);

create index if not exists relocation_support_cases_quote_idx
on public.relocation_support_cases (quote_id);

create index if not exists relocation_support_cases_handoff_idx
on public.relocation_support_cases (handoff_id);

drop trigger if exists relocation_support_cases_set_updated_at
on public.relocation_support_cases;

create trigger relocation_support_cases_set_updated_at
before update on public.relocation_support_cases
for each row execute function public.relocation_set_updated_at();

-- Handoffs and cases contain identities, provider relationships, payment or
-- refund context, consent records, delivery references, and complaint details.
-- They are backend-only and have no browser-accessible RLS policy.
alter table public.relocation_service_handoffs enable row level security;
alter table public.relocation_service_handoff_events enable row level security;
alter table public.relocation_support_cases enable row level security;

revoke all privileges on table public.relocation_service_handoffs from public, anon, authenticated;
revoke all privileges on table public.relocation_service_handoff_events from public, anon, authenticated;
revoke all privileges on table public.relocation_support_cases from public, anon, authenticated;

grant all privileges on table public.relocation_service_handoffs to service_role;
grant all privileges on table public.relocation_service_handoff_events to service_role;
grant all privileges on table public.relocation_support_cases to service_role;

comment on table public.relocation_service_handoffs is 'Private provider handoff records with exact shared-field consent and delivery audit.';
comment on table public.relocation_service_handoff_events is 'Private handoff lifecycle and consent audit events.';
comment on table public.relocation_support_cases is 'Private complaint, refund, payment dispute, provider issue, privacy, service quality, and technical support cases.';

notify pgrst, 'reload schema';