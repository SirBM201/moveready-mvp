-- MoveReady migration 034
-- Career search scope + international application viability.
-- Additive only: preserves all existing Jobs data and migration contracts.

alter table if exists public.relocation_job_search_profiles
  add column if not exists search_scope text not null default 'international',
  add column if not exists current_country text,
  add column if not exists work_authorized_countries text[] not null default '{}'::text[];

alter table if exists public.relocation_job_search_profiles
  drop constraint if exists relocation_job_search_profiles_search_scope_check;

alter table if exists public.relocation_job_search_profiles
  add constraint relocation_job_search_profiles_search_scope_check
  check (search_scope in ('local', 'international', 'both'));

alter table if exists public.relocation_jobs
  add column if not exists work_authorization_requirement text not null default 'unknown',
  add column if not exists sponsorship_evidence text,
  add column if not exists relocation_support_status text not null default 'unknown';

alter table if exists public.relocation_jobs
  drop constraint if exists relocation_jobs_work_authorization_requirement_check;

alter table if exists public.relocation_jobs
  add constraint relocation_jobs_work_authorization_requirement_check
  check (work_authorization_requirement in ('unknown', 'existing_required', 'employer_support_possible', 'employer_support_confirmed'));

alter table if exists public.relocation_jobs
  drop constraint if exists relocation_jobs_relocation_support_status_check;

alter table if exists public.relocation_jobs
  add constraint relocation_jobs_relocation_support_status_check
  check (relocation_support_status in ('unknown', 'not_available', 'possible', 'confirmed'));

create index if not exists relocation_job_profiles_search_scope_idx
  on public.relocation_job_search_profiles (search_scope);

create index if not exists relocation_jobs_authorization_requirement_idx
  on public.relocation_jobs (work_authorization_requirement);

comment on column public.relocation_job_search_profiles.search_scope is
  'User-selected job search scope: local, international, or both.';
comment on column public.relocation_job_search_profiles.current_country is
  'Country where the user currently lives/works; used to distinguish local from international vacancies.';
comment on column public.relocation_job_search_profiles.work_authorized_countries is
  'Countries where the user reports current legal work authorization; never inferred as citizenship or immigration status.';
comment on column public.relocation_jobs.work_authorization_requirement is
  'Vacancy-level authorization signal extracted from the official source.';
comment on column public.relocation_jobs.sponsorship_evidence is
  'Short source-derived evidence explaining the vacancy sponsorship/authorization classification.';
comment on column public.relocation_jobs.relocation_support_status is
  'Vacancy-level relocation support signal extracted from the official source.';
