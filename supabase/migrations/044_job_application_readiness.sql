-- B19.2 Vacancy-to-Application Readiness persistence
create table if not exists public.relocation_job_application_readiness (
  id uuid primary key default gen_random_uuid(),
  email text not null,
  job_id uuid not null references public.relocation_jobs(id) on delete cascade,
  state text not null default 'discovered' check (state in ('discovered','review_required','blocked','materials_required','ready_for_review','ready_to_apply','application_started','applied','closed')),
  issues jsonb not null default '[]'::jsonb,
  blocking_issue_count integer not null default 0,
  cv_id uuid null references public.relocation_job_resume_assets(id) on delete set null,
  cover_letter_id uuid null references public.relocation_job_resume_assets(id) on delete set null,
  application_answers_ready boolean not null default false,
  requirements_verified boolean not null default false,
  user_confirmed_ready_at timestamptz null,
  application_started_at timestamptz null,
  submission_confirmed_at timestamptz null,
  closed_at timestamptz null,
  contract_version text not null default 'b19.1-v1',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(email, job_id)
);
create index if not exists relocation_job_application_readiness_email_state_idx on public.relocation_job_application_readiness(email, state);
create index if not exists relocation_job_application_readiness_job_idx on public.relocation_job_application_readiness(job_id);
alter table public.relocation_job_application_readiness enable row level security;
-- Backend uses the service role; keep the table inaccessible to anonymous/public clients.
comment on table public.relocation_job_application_readiness is 'B19.2 private per-account vacancy-to-application readiness state and audit boundary.';
