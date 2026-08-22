-- B19.5 vacancy-specific application draft persistence
create table if not exists public.relocation_job_application_drafts (
  id uuid primary key default gen_random_uuid(),
  email text not null,
  job_id uuid not null references public.relocation_jobs(id) on delete cascade,
  readiness_id uuid null references public.relocation_job_application_readiness(id) on delete cascade,
  status text not null default 'draft' check (status in ('draft','reviewed','approved','stale','superseded')),
  contract_version text not null default 'b19.5-v1',
  source_fingerprint text not null,
  tailoring_brief jsonb not null default '{}'::jsonb,
  cv_draft jsonb not null default '{}'::jsonb,
  cover_letter_draft jsonb not null default '{}'::jsonb,
  application_answers jsonb not null default '{}'::jsonb,
  safety jsonb not null default '{}'::jsonb,
  reviewed_at timestamptz null,
  approved_at timestamptz null,
  stale_at timestamptz null,
  superseded_at timestamptz null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists relocation_job_application_drafts_email_job_idx on public.relocation_job_application_drafts(email, job_id, created_at desc);
create index if not exists relocation_job_application_drafts_status_idx on public.relocation_job_application_drafts(email, status, updated_at desc);
alter table public.relocation_job_application_drafts enable row level security;
comment on table public.relocation_job_application_drafts is 'B19.5 private vacancy-specific application draft packages; backend service-role access only.';
