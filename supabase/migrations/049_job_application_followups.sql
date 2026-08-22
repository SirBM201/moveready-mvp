-- MoveReady B19.7.4 — application follow-up scheduling, user actions and outcomes
create table if not exists public.relocation_job_application_followups (
  id uuid primary key default gen_random_uuid(),
  email text not null,
  lifecycle_id uuid not null references public.relocation_job_application_lifecycles(id) on delete cascade,
  job_id uuid not null references public.relocation_jobs(id) on delete cascade,
  action_type text not null check (action_type in ('follow_up_email','check_portal','contact_recruiter','prepare_assessment','prepare_interview','review_offer','record_outcome','other')),
  status text not null default 'scheduled' check (status in ('scheduled','due','completed','cancelled','superseded')),
  scheduled_for timestamptz not null,
  completed_at timestamptz,
  note text,
  outcome text check (outcome is null or outcome in ('no_response','acknowledged','under_review','assessment','interview','offer','hired','rejected','withdrawn','closed','unknown')),
  outcome_evidence jsonb not null default '{}'::jsonb,
  user_confirmed boolean not null default false,
  contract_version text not null default 'b19.7.4-v1',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists relocation_job_application_followups_owner_due_idx
  on public.relocation_job_application_followups(email, status, scheduled_for);
create index if not exists relocation_job_application_followups_lifecycle_idx
  on public.relocation_job_application_followups(lifecycle_id, created_at desc);

alter table public.relocation_job_application_followups enable row level security;
drop policy if exists relocation_job_application_followups_owner_select on public.relocation_job_application_followups;
create policy relocation_job_application_followups_owner_select on public.relocation_job_application_followups for select using (lower(email)=lower(coalesce(auth.jwt()->>'email','')));
drop policy if exists relocation_job_application_followups_owner_insert on public.relocation_job_application_followups;
create policy relocation_job_application_followups_owner_insert on public.relocation_job_application_followups for insert with check (lower(email)=lower(coalesce(auth.jwt()->>'email','')));
drop policy if exists relocation_job_application_followups_owner_update on public.relocation_job_application_followups;
create policy relocation_job_application_followups_owner_update on public.relocation_job_application_followups for update using (lower(email)=lower(coalesce(auth.jwt()->>'email',''))) with check (lower(email)=lower(coalesce(auth.jwt()->>'email','')));
