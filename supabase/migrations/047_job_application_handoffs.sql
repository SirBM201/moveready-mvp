-- B19.6 approved application package handoff persistence and audit
create table if not exists public.relocation_job_application_handoffs (
  id uuid primary key default gen_random_uuid(),
  email text not null,
  job_id uuid not null references public.relocation_jobs(id) on delete cascade,
  draft_id uuid not null references public.relocation_job_application_drafts(id) on delete cascade,
  status text not null default 'prepared' check (status in ('prepared','opened','submitted_manual','withdrawn')),
  contract_version text not null default 'b19.6-v1',
  destination_url text null,
  package_snapshot jsonb not null default '{}'::jsonb,
  safety jsonb not null default '{}'::jsonb,
  prepared_at timestamptz not null default now(),
  opened_at timestamptz null,
  submitted_manual_at timestamptz null,
  withdrawn_at timestamptz null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (email, draft_id)
);

create table if not exists public.relocation_job_application_handoff_events (
  id uuid primary key default gen_random_uuid(),
  handoff_id uuid not null references public.relocation_job_application_handoffs(id) on delete cascade,
  email text not null,
  event_type text not null check (event_type in ('prepared','opened','submitted_manual','withdrawn')),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists relocation_job_application_handoffs_email_job_idx
  on public.relocation_job_application_handoffs(email, job_id, created_at desc);
create index if not exists relocation_job_application_handoffs_status_idx
  on public.relocation_job_application_handoffs(email, status, updated_at desc);
create index if not exists relocation_job_application_handoff_events_handoff_idx
  on public.relocation_job_application_handoff_events(handoff_id, created_at asc);

alter table public.relocation_job_application_handoffs enable row level security;
alter table public.relocation_job_application_handoff_events enable row level security;

comment on table public.relocation_job_application_handoffs is 'B19.6 private approved-draft handoff records. Handoff never performs employer submission.';
comment on table public.relocation_job_application_handoff_events is 'B19.6 immutable audit trail for user-controlled application handoff lifecycle.';
