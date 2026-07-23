-- Project MoveReady MVP
-- Private in-app alerts generated from application case deadlines, appointments,
-- source status, additional-document requests, refusals, and payment disputes.
-- Run after migration 028. Safe to rerun.

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

create table if not exists public.relocation_application_case_alerts (
  id uuid primary key default gen_random_uuid(),
  application_case_id uuid not null references public.relocation_application_cases(id) on delete cascade,
  email text not null,
  alert_key text not null unique,
  alert_type text not null check (alert_type in (
    'deadline_overdue',
    'deadline_due_72h',
    'deadline_due_14d',
    'appointment_due_7d',
    'additional_documents_requested',
    'source_review_required',
    'source_stale_or_unavailable',
    'payment_attention',
    'refusal_followup',
    'decision_followup',
    'manual'
  )),
  severity text not null default 'medium' check (severity in ('low', 'medium', 'high', 'critical')),
  status text not null default 'open' check (status in ('open', 'dismissed', 'resolved', 'expired')),
  title text not null,
  summary text not null,
  due_at timestamptz,
  first_detected_at timestamptz not null default now(),
  last_detected_at timestamptz not null default now(),
  resolved_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists relocation_application_case_alerts_email_idx
on public.relocation_application_case_alerts (email, status, severity, updated_at desc);

create index if not exists relocation_application_case_alerts_case_idx
on public.relocation_application_case_alerts (application_case_id, status, updated_at desc);

create index if not exists relocation_application_case_alerts_open_due_idx
on public.relocation_application_case_alerts (due_at, severity)
where status = 'open';

drop trigger if exists relocation_application_case_alerts_set_updated_at
on public.relocation_application_case_alerts;

create trigger relocation_application_case_alerts_set_updated_at
before update on public.relocation_application_case_alerts
for each row execute function public.relocation_set_updated_at();

alter table public.relocation_application_case_alerts
  drop constraint if exists relocation_application_case_alerts_resolution_check;

alter table public.relocation_application_case_alerts
  add constraint relocation_application_case_alerts_resolution_check
  check (
    status not in ('resolved', 'expired')
    or resolved_at is not null
  );

-- Alerts contain private account, application, deadline, refusal, payment, and
-- source-review context. They are backend-only and have no public browser policy.
alter table public.relocation_application_case_alerts enable row level security;

revoke all privileges on table public.relocation_application_case_alerts from public, anon, authenticated;
grant all privileges on table public.relocation_application_case_alerts to service_role;

comment on table public.relocation_application_case_alerts is 'Private in-app application alerts generated from deadlines, appointments, source status, additional-document requests, payment issues, refusals, and decisions.';
comment on column public.relocation_application_case_alerts.alert_key is 'Stable deduplication key derived from case, alert type, and the relevant date or stage. It must not contain a private authority reference.';

notify pgrst, 'reload schema';
