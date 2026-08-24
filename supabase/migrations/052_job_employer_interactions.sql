-- MoveReady B19.11.3 — recorded employer/application interaction timeline
begin;
create table if not exists public.relocation_job_employer_interactions (
 id uuid primary key default gen_random_uuid(),
 employer_id uuid not null references public.relocation_job_employers(id) on delete cascade,
 job_id uuid,
 application_id uuid,
 email text not null,
 interaction_type text not null check (interaction_type in ('application_submitted','employer_email','user_email','portal_update','recruiter_contact','assessment','interview','offer','rejection','withdrawal','other')),
 direction text not null default 'system' check (direction in ('inbound','outbound','system')),
 channel text check (channel is null or channel in ('email','portal','phone','video','in_person','other')),
 summary text,
 evidence_url text,
 occurred_at timestamptz not null,
 recorded_at timestamptz not null default now(),
 metadata jsonb not null default '{}'::jsonb
);
create index if not exists relocation_job_employer_interactions_employer_time_idx on public.relocation_job_employer_interactions(employer_id,occurred_at desc);
create index if not exists relocation_job_employer_interactions_application_idx on public.relocation_job_employer_interactions(application_id) where application_id is not null;
alter table public.relocation_job_employer_interactions enable row level security;
revoke all privileges on table public.relocation_job_employer_interactions from public,anon,authenticated;
grant all privileges on table public.relocation_job_employer_interactions to service_role;
comment on table public.relocation_job_employer_interactions is 'User-scoped recorded interactions and evidence. Absence of a row is not evidence that an interaction did not occur; records do not imply employer intent, sponsorship or relocation support.';
commit;
