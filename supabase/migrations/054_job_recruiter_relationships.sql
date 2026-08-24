-- MoveReady B19.12 — recruiter relationship events and canonical employer linkage
begin;

alter table public.relocation_job_recruiters
  add column if not exists canonical_employer_id uuid references public.relocation_job_employers(id) on delete set null,
  add column if not exists normalized_name text,
  add column if not exists canonical_key text,
  add column if not exists identity_basis text,
  add column if not exists identity_evidence_url text;

create index if not exists relocation_job_recruiters_canonical_employer_idx
on public.relocation_job_recruiters(canonical_employer_id, updated_at desc)
where canonical_employer_id is not null;

create index if not exists relocation_job_recruiters_owner_canonical_key_idx
on public.relocation_job_recruiters(owner_email, canonical_key)
where canonical_key is not null;

create table if not exists public.relocation_job_recruiter_relationship_events (
  id uuid primary key default gen_random_uuid(),
  owner_email text not null,
  recruiter_id uuid not null references public.relocation_job_recruiters(id) on delete cascade,
  employer_id uuid references public.relocation_job_employers(id) on delete set null,
  job_id uuid references public.relocation_jobs(id) on delete set null,
  application_id uuid references public.relocation_job_applications(id) on delete set null,
  event_type text not null check (event_type in (
    'connection_requested','connected','outreach_prepared','outreach_sent',
    'response_received','follow_up_scheduled','follow_up_completed',
    'vacancy_discussed','application_discussed','interview_discussed',
    'declined_contact','relationship_inactive','note'
  )),
  direction text not null default 'system' check (direction in ('inbound','outbound','system')),
  channel text check (channel is null or channel in ('email','linkedin','phone','in_person','other')),
  summary text,
  evidence_url text,
  occurred_at timestamptz not null,
  recorded_at timestamptz not null default now(),
  metadata jsonb not null default '{}'::jsonb
);

create index if not exists relocation_job_recruiter_events_owner_time_idx
on public.relocation_job_recruiter_relationship_events(owner_email, occurred_at desc);

create index if not exists relocation_job_recruiter_events_recruiter_time_idx
on public.relocation_job_recruiter_relationship_events(recruiter_id, occurred_at desc);

alter table public.relocation_job_recruiter_relationship_events enable row level security;
revoke all privileges on table public.relocation_job_recruiter_relationship_events from public, anon, authenticated;
grant all privileges on table public.relocation_job_recruiter_relationship_events to service_role;

comment on table public.relocation_job_recruiter_relationship_events is
'Private user-recorded recruiter relationship evidence. Records do not prove recruiter identity, employment, employer interest, sponsorship, referral, vacancy availability, delivery, or response. MoveReady never sends outreach automatically.';

commit;
