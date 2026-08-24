-- MoveReady B19.10.2 — Job Search Campaign persistence and vacancy association
-- Migration 050. Account-private, service-role-only persistence. Idempotent.
begin;
create table if not exists public.relocation_job_search_campaigns (
  id uuid primary key default gen_random_uuid(), email text not null, name text not null,
  status text not null default 'draft' check (status in ('draft','active','paused','completed','archived')),
  target_countries jsonb not null default '[]'::jsonb, target_occupations jsonb not null default '[]'::jsonb,
  target_employers jsonb not null default '[]'::jsonb, work_authorized_countries jsonb not null default '[]'::jsonb,
  sponsorship_required boolean not null default false, relocation_support_preferred boolean not null default false,
  search_intensity text not null default 'standard' check (search_intensity in ('light','standard','intensive')),
  notes text, contract_version text not null default 'b19.10.1-v1', created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
create index if not exists relocation_job_search_campaigns_email_status_idx on public.relocation_job_search_campaigns(email,status,updated_at desc);
create table if not exists public.relocation_job_search_campaign_vacancies (
  id uuid primary key default gen_random_uuid(), campaign_id uuid not null references public.relocation_job_search_campaigns(id) on delete cascade,
  email text not null, job_id uuid not null references public.relocation_jobs(id) on delete cascade, association_reason text,
  user_confirmed boolean not null default true, created_at timestamptz not null default now(), unique(campaign_id,job_id)
);
create index if not exists relocation_job_search_campaign_vacancies_email_idx on public.relocation_job_search_campaign_vacancies(email,campaign_id,created_at desc);
create index if not exists relocation_job_search_campaign_vacancies_job_idx on public.relocation_job_search_campaign_vacancies(job_id);
alter table public.relocation_job_search_campaigns enable row level security;
alter table public.relocation_job_search_campaign_vacancies enable row level security;
revoke all privileges on table public.relocation_job_search_campaigns from public,anon,authenticated;
revoke all privileges on table public.relocation_job_search_campaign_vacancies from public,anon,authenticated;
grant all privileges on table public.relocation_job_search_campaigns to service_role;
grant all privileges on table public.relocation_job_search_campaign_vacancies to service_role;
comment on table public.relocation_job_search_campaigns is 'B19.10 account-private job-search campaigns. Campaign targeting is planning data and never evidence of work authorization, sponsorship, relocation support or application submission.';
comment on table public.relocation_job_search_campaign_vacancies is 'B19.10 explicit account-owned campaign-to-vacancy associations. Association does not verify vacancy claims or authorize application submission.';
commit;
