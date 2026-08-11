-- Project MoveReady MVP
-- Private application case records and lifecycle events.
-- Stores planning and status metadata only; no raw application files or full document number.
-- Passport, bank, card, OTP, password, and private-key values are also excluded.
-- Run after migration 027. Safe to rerun.

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

create table if not exists public.relocation_application_cases (
  id uuid primary key default gen_random_uuid(),
  case_ref text not null unique,
  email text not null,
  profile_id uuid references public.relocation_user_profiles(id) on delete set null,
  saved_route_id uuid references public.relocation_saved_routes(id) on delete set null,
  route_version_id uuid references public.relocation_route_versions(id) on delete set null,
  evidence_pack_id uuid references public.relocation_evidence_packs(id) on delete set null,
  case_title text not null,
  target_country text,
  target_city text,
  route_category text not null check (route_category in (
    'visit', 'study', 'work', 'startup', 'business', 'digital_nomad', 'family',
    'scholarship', 'permanent_residence', 'citizenship', 'other'
  )),
  route_name text,
  responsible_authority text,
  application_stage text not null default 'research' check (application_stage in (
    'research',
    'preparing',
    'appointment_booked',
    'submitted',
    'biometrics_completed',
    'interview_scheduled',
    'additional_documents_requested',
    'decision_pending',
    'approved',
    'refused',
    'withdrawn',
    'expired',
    'closed'
  )),
  status text not null default 'active' check (status in (
    'active', 'attention_required', 'completed', 'archived'
  )),
  risk_level text not null default 'medium' check (risk_level in ('low', 'medium', 'high', 'critical')),
  source_status text not null default 'review_required' check (source_status in (
    'verified', 'review_required', 'stale', 'unavailable'
  )),
  authority_reference_hint text,
  application_date date,
  appointment_date timestamptz,
  submission_date date,
  next_deadline_at timestamptz,
  decision_date date,
  fee_amount numeric(14,2),
  fee_currency text,
  payment_status text not null default 'not_recorded' check (payment_status in (
    'not_recorded', 'not_required', 'planned', 'pending', 'paid', 'refunded', 'disputed'
  )),
  official_source_url text,
  official_source_note text,
  result_summary text,
  notes text,
  consent_to_store boolean not null default true,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists relocation_application_cases_email_idx
on public.relocation_application_cases (email, status, updated_at desc);

create index if not exists relocation_application_cases_stage_idx
on public.relocation_application_cases (application_stage, status, next_deadline_at);

create index if not exists relocation_application_cases_deadline_idx
on public.relocation_application_cases (next_deadline_at)
where next_deadline_at is not null and status in ('active', 'attention_required');

create index if not exists relocation_application_cases_evidence_pack_idx
on public.relocation_application_cases (evidence_pack_id)
where evidence_pack_id is not null;

drop trigger if exists relocation_application_cases_set_updated_at
on public.relocation_application_cases;

create trigger relocation_application_cases_set_updated_at
before update on public.relocation_application_cases
for each row execute function public.relocation_set_updated_at();

create table if not exists public.relocation_application_case_events (
  id uuid primary key default gen_random_uuid(),
  application_case_id uuid not null references public.relocation_application_cases(id) on delete cascade,
  event_type text not null check (event_type in (
    'case_created',
    'status_changed',
    'deadline_added',
    'appointment',
    'submission',
    'biometrics',
    'interview',
    'additional_documents_request',
    'payment',
    'communication',
    'decision',
    'note',
    'timeline_tasks_created',
    'case_archived'
  )),
  event_status text not null default 'recorded' check (event_status in (
    'recorded', 'pending', 'completed', 'cancelled', 'disputed'
  )),
  event_title text not null,
  event_summary text,
  event_at timestamptz not null default now(),
  due_at timestamptz,
  actor_type text not null default 'user' check (actor_type in ('user', 'admin', 'provider', 'system', 'authority')),
  actor_reference text,
  event_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists relocation_application_case_events_case_idx
on public.relocation_application_case_events (application_case_id, event_at desc);

create index if not exists relocation_application_case_events_due_idx
on public.relocation_application_case_events (due_at)
where due_at is not null and event_status in ('recorded', 'pending');

-- Terminal stages require a decision or closure date and result summary.
alter table public.relocation_application_cases
  drop constraint if exists relocation_application_cases_terminal_check;

alter table public.relocation_application_cases
  add constraint relocation_application_cases_terminal_check
  check (
    application_stage not in ('approved', 'refused', 'withdrawn', 'expired', 'closed')
    or (
      decision_date is not null
      and nullif(btrim(coalesce(result_summary, '')), '') is not null
    )
  );

-- Completed cases must be at a terminal application stage.
alter table public.relocation_application_cases
  drop constraint if exists relocation_application_cases_completed_check;

alter table public.relocation_application_cases
  add constraint relocation_application_cases_completed_check
  check (
    status <> 'completed'
    or application_stage in ('approved', 'refused', 'withdrawn', 'expired', 'closed')
  );

-- Reference hints must remain partial or masked. Existing records are not
-- blocked during rollout, while all new and updated records are enforced.
alter table public.relocation_application_cases
  drop constraint if exists relocation_application_cases_reference_hint_check;

alter table public.relocation_application_cases
  add constraint relocation_application_cases_reference_hint_check
  check (
    authority_reference_hint is null
    or length(regexp_replace(authority_reference_hint, '[^[:alnum:]]', '', 'g')) <= 8
  ) not valid;

-- Only web URLs can be attached as application authority sources.
alter table public.relocation_application_cases
  drop constraint if exists relocation_application_cases_source_url_check;

alter table public.relocation_application_cases
  add constraint relocation_application_cases_source_url_check
  check (
    official_source_url is null
    or official_source_url ~* '^https?://'
  ) not valid;

-- A recorded fee must be non-negative and paired with an ISO-style currency.
alter table public.relocation_application_cases
  drop constraint if exists relocation_application_cases_fee_currency_check;

alter table public.relocation_application_cases
  add constraint relocation_application_cases_fee_currency_check
  check (
    (fee_amount is null and fee_currency is null)
    or (
      fee_amount is not null
      and fee_amount >= 0
      and fee_currency ~ '^[A-Z]{3}$'
    )
  ) not valid;

-- Application records are stored only after affirmative account consent.
alter table public.relocation_application_cases
  drop constraint if exists relocation_application_cases_storage_consent_check;

alter table public.relocation_application_cases
  add constraint relocation_application_cases_storage_consent_check
  check (consent_to_store = true) not valid;

-- These tables contain personal application status, deadlines, authority,
-- payment, refusal, and decision context. They are backend-only.
alter table public.relocation_application_cases enable row level security;
alter table public.relocation_application_case_events enable row level security;

revoke all privileges on table public.relocation_application_cases from public, anon, authenticated;
revoke all privileges on table public.relocation_application_case_events from public, anon, authenticated;

grant all privileges on table public.relocation_application_cases to service_role;
grant all privileges on table public.relocation_application_case_events to service_role;

comment on table public.relocation_application_cases is 'Private application case metadata linking route, evidence pack, deadlines, payment status, stage, and decision.';
comment on table public.relocation_application_case_events is 'Private auditable application case lifecycle events without raw authority correspondence or documents.';
comment on column public.relocation_application_cases.authority_reference_hint is 'Optional masked or partial reference hint only; do not store a full passport number, bank number, card number, OTP, password, or private key.';

notify pgrst, 'reload schema';
