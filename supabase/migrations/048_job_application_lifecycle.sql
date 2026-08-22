-- B19.7 post-submission application lifecycle persistence and immutable event history
create table if not exists public.relocation_job_application_lifecycles (
  id uuid primary key default gen_random_uuid(),
  email text not null,
  job_id uuid not null references public.relocation_jobs(id) on delete cascade,
  draft_id uuid null references public.relocation_job_application_drafts(id) on delete set null,
  handoff_id uuid not null references public.relocation_job_application_handoffs(id) on delete cascade,
  state text not null default 'submitted' check (state in ('submitted','acknowledged','under_review','assessment','interview','offer','hired','rejected','withdrawn','closed')),
  contract_version text not null default 'b19.7-v1',
  latest_evidence jsonb not null default '{}'::jsonb,
  submitted_at timestamptz not null,
  state_changed_at timestamptz not null default now(),
  terminal_at timestamptz null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (email, handoff_id)
);

create table if not exists public.relocation_job_application_lifecycle_events (
  id uuid primary key default gen_random_uuid(),
  lifecycle_id uuid not null references public.relocation_job_application_lifecycles(id) on delete cascade,
  email text not null,
  previous_state text null,
  state text not null check (state in ('submitted','acknowledged','under_review','assessment','interview','offer','hired','rejected','withdrawn','closed')),
  evidence jsonb not null default '{}'::jsonb,
  user_confirmed boolean not null default false,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists relocation_job_application_lifecycles_email_state_idx
  on public.relocation_job_application_lifecycles(email, state, updated_at desc);
create index if not exists relocation_job_application_lifecycles_email_job_idx
  on public.relocation_job_application_lifecycles(email, job_id, created_at desc);
create index if not exists relocation_job_application_lifecycle_events_lifecycle_idx
  on public.relocation_job_application_lifecycle_events(lifecycle_id, created_at asc);

alter table public.relocation_job_application_lifecycles enable row level security;
alter table public.relocation_job_application_lifecycle_events enable row level security;

comment on table public.relocation_job_application_lifecycles is 'B19.7 private post-submission application tracking. Lifecycle begins only from a user-confirmed manual submission.';
comment on table public.relocation_job_application_lifecycle_events is 'B19.7 immutable application lifecycle audit events with employer evidence/user confirmation.';
