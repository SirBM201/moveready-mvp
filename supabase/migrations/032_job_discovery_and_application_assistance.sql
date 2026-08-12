-- MoveReady Jobs automation: private official-source monitors, alerts,
-- truthful application drafts, and user-confirmed application handoffs.
-- Run after migration 031. Safe to rerun.

create extension if not exists pgcrypto;

alter table public.relocation_job_search_profiles
  add column if not exists career_facts text[] not null default '{}'::text[];

alter table public.relocation_jobs
  add column if not exists source_fingerprint text,
  add column if not exists source_content_hash text,
  add column if not exists first_seen_at timestamptz,
  add column if not exists last_seen_at timestamptz,
  add column if not exists last_checked_at timestamptz;

-- Point the starter monitors at the official listing pages that expose the
-- vacancies rather than at the surrounding employer-culture pages.
update public.relocation_job_companies
set career_page = 'https://career.alpla.com/en/jobs',
    source_url = 'https://career.alpla.com/en/jobs',
    source_status = 'verified',
    last_verified_at = '2026-08-12T00:00:00Z',
    updated_at = now()
where slug = 'alpla';

update public.relocation_job_companies
set career_page = 'https://www.winpak.com/job-listings',
    source_url = 'https://www.winpak.com/job-listings',
    source_status = 'verified',
    last_verified_at = '2026-08-12T00:00:00Z',
    updated_at = now()
where slug = 'winpak';

update public.relocation_job_companies
set career_page = 'https://www.amcor.com/careers/job-search',
    source_url = 'https://www.amcor.com/careers/job-search',
    source_status = 'verified',
    last_verified_at = '2026-08-12T00:00:00Z',
    updated_at = now()
where slug in ('amcor', 'berry-global');

create unique index if not exists relocation_jobs_owner_source_fingerprint_uidx
on public.relocation_jobs (owner_email, source_fingerprint)
where owner_email is not null and source_fingerprint is not null;

create table if not exists public.relocation_job_watches (
  id uuid primary key default gen_random_uuid(),
  email text not null,
  company_id uuid not null references public.relocation_job_companies(id) on delete cascade,
  watch_name text not null,
  source_url text not null,
  source_type text not null default 'auto' check (
    source_type in ('auto', 'jsonld', 'greenhouse', 'lever', 'workday', 'smartrecruiters', 'generic')
  ),
  keywords text[] not null default '{}'::text[],
  country text not null default 'Canada',
  province text,
  cadence text not null default 'daily' check (cadence in ('manual', 'daily', 'weekly')),
  min_match_score integer not null default 35 check (min_match_score between 0 and 100),
  email_alerts boolean not null default false,
  is_active boolean not null default true,
  last_scan_at timestamptz,
  next_scan_at timestamptz,
  last_scan_status text not null default 'not_run' check (
    last_scan_status in ('not_run', 'running', 'completed', 'partial', 'failed', 'paused')
  ),
  last_error text,
  consecutive_failures integer not null default 0 check (consecutive_failures between 0 and 1000),
  last_result_count integer not null default 0 check (last_result_count >= 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (email, source_url)
);

create index if not exists relocation_job_watches_due_idx
on public.relocation_job_watches (is_active, next_scan_at, last_scan_at);

create index if not exists relocation_job_watches_owner_idx
on public.relocation_job_watches (email, is_active, updated_at desc);

create table if not exists public.relocation_job_scan_runs (
  id uuid primary key default gen_random_uuid(),
  watch_id uuid not null references public.relocation_job_watches(id) on delete cascade,
  email text not null,
  trigger_type text not null check (trigger_type in ('user', 'scheduled', 'admin')),
  status text not null default 'running' check (status in ('running', 'completed', 'partial', 'failed')),
  source_adapter text,
  source_http_status integer,
  discovered_count integer not null default 0 check (discovered_count >= 0),
  new_count integer not null default 0 check (new_count >= 0),
  changed_count integer not null default 0 check (changed_count >= 0),
  closed_count integer not null default 0 check (closed_count >= 0),
  alert_count integer not null default 0 check (alert_count >= 0),
  error_code text,
  error_summary text,
  started_at timestamptz not null default now(),
  completed_at timestamptz,
  created_at timestamptz not null default now()
);

create index if not exists relocation_job_scan_runs_owner_idx
on public.relocation_job_scan_runs (email, created_at desc);

create table if not exists public.relocation_job_alerts (
  id uuid primary key default gen_random_uuid(),
  email text not null,
  watch_id uuid references public.relocation_job_watches(id) on delete set null,
  job_id uuid references public.relocation_jobs(id) on delete set null,
  alert_type text not null check (
    alert_type in ('new_match', 'job_changed', 'job_closed', 'job_reopened', 'closing_soon', 'scan_failed')
  ),
  severity text not null default 'info' check (severity in ('info', 'action', 'warning')),
  title text not null,
  summary text not null,
  source_url text,
  status text not null default 'unread' check (status in ('unread', 'read', 'dismissed')),
  dedupe_key text not null unique,
  delivery_status text not null default 'in_app' check (
    delivery_status in ('in_app', 'email_sent', 'email_failed', 'email_disabled')
  ),
  delivered_at timestamptz,
  read_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists relocation_job_alerts_owner_idx
on public.relocation_job_alerts (email, status, created_at desc);

create table if not exists public.relocation_job_document_drafts (
  id uuid primary key default gen_random_uuid(),
  email text not null,
  job_id uuid not null references public.relocation_jobs(id) on delete cascade,
  application_id uuid references public.relocation_job_applications(id) on delete set null,
  source_resume_asset_id uuid references public.relocation_job_resume_assets(id) on delete set null,
  draft_type text not null check (draft_type in ('tailored_resume', 'cover_letter')),
  title text not null,
  content text not null,
  status text not null default 'draft' check (status in ('draft', 'reviewed', 'approved', 'exported', 'archived')),
  generation_method text not null default 'verified_template' check (
    generation_method in ('verified_template', 'ai_assisted')
  ),
  truth_basis jsonb not null default '{}'::jsonb check (jsonb_typeof(truth_basis) = 'object'),
  warnings jsonb not null default '[]'::jsonb check (jsonb_typeof(warnings) = 'array'),
  user_confirmations jsonb not null default '{}'::jsonb check (jsonb_typeof(user_confirmations) = 'object'),
  approved_at timestamptz,
  exported_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (email, job_id, draft_type)
);

create index if not exists relocation_job_document_drafts_owner_idx
on public.relocation_job_document_drafts (email, status, updated_at desc);

create table if not exists public.relocation_job_application_assistance (
  id uuid primary key default gen_random_uuid(),
  email text not null,
  application_id uuid not null references public.relocation_job_applications(id) on delete cascade,
  job_id uuid not null references public.relocation_jobs(id) on delete cascade,
  status text not null default 'preparing' check (
    status in ('preparing', 'ready', 'official_site_opened', 'submission_confirmed', 'not_submitted', 'paused')
  ),
  readiness jsonb not null default '{}'::jsonb check (jsonb_typeof(readiness) = 'object'),
  last_handoff_at timestamptz,
  submission_confirmed_at timestamptz,
  submission_reference_hint text,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (email, application_id),
  unique (email, job_id),
  check (submission_reference_hint is null or char_length(submission_reference_hint) <= 80)
);

create table if not exists public.relocation_job_assistance_events (
  id uuid primary key default gen_random_uuid(),
  email text not null,
  assistance_id uuid not null references public.relocation_job_application_assistance(id) on delete cascade,
  event_type text not null check (
    event_type in ('prepared', 'documents_generated', 'documents_approved', 'official_site_opened', 'submission_confirmed', 'not_submitted', 'paused')
  ),
  event_payload jsonb not null default '{}'::jsonb check (jsonb_typeof(event_payload) = 'object'),
  created_at timestamptz not null default now()
);

create index if not exists relocation_job_assistance_events_owner_idx
on public.relocation_job_assistance_events (email, created_at desc);

drop trigger if exists relocation_job_watches_set_updated_at on public.relocation_job_watches;
create trigger relocation_job_watches_set_updated_at before update on public.relocation_job_watches
for each row execute function public.relocation_set_updated_at();

drop trigger if exists relocation_job_alerts_set_updated_at on public.relocation_job_alerts;
create trigger relocation_job_alerts_set_updated_at before update on public.relocation_job_alerts
for each row execute function public.relocation_set_updated_at();

drop trigger if exists relocation_job_document_drafts_set_updated_at on public.relocation_job_document_drafts;
create trigger relocation_job_document_drafts_set_updated_at before update on public.relocation_job_document_drafts
for each row execute function public.relocation_set_updated_at();

drop trigger if exists relocation_job_application_assistance_set_updated_at on public.relocation_job_application_assistance;
create trigger relocation_job_application_assistance_set_updated_at before update on public.relocation_job_application_assistance
for each row execute function public.relocation_set_updated_at();

alter table public.relocation_job_watches enable row level security;
alter table public.relocation_job_scan_runs enable row level security;
alter table public.relocation_job_alerts enable row level security;
alter table public.relocation_job_document_drafts enable row level security;
alter table public.relocation_job_application_assistance enable row level security;
alter table public.relocation_job_assistance_events enable row level security;

revoke all privileges on table public.relocation_job_watches from public, anon, authenticated;
revoke all privileges on table public.relocation_job_scan_runs from public, anon, authenticated;
revoke all privileges on table public.relocation_job_alerts from public, anon, authenticated;
revoke all privileges on table public.relocation_job_document_drafts from public, anon, authenticated;
revoke all privileges on table public.relocation_job_application_assistance from public, anon, authenticated;
revoke all privileges on table public.relocation_job_assistance_events from public, anon, authenticated;

grant all privileges on table public.relocation_job_watches to service_role;
grant all privileges on table public.relocation_job_scan_runs to service_role;
grant all privileges on table public.relocation_job_alerts to service_role;
grant all privileges on table public.relocation_job_document_drafts to service_role;
grant all privileges on table public.relocation_job_application_assistance to service_role;
grant all privileges on table public.relocation_job_assistance_events to service_role;

comment on table public.relocation_job_watches is 'Private official employer or public ATS vacancy monitors; arbitrary web search and automatic applications are out of scope.';
comment on table public.relocation_job_document_drafts is 'Private, editable application drafts generated only from account-owned profile, resume, and verified career facts.';
comment on table public.relocation_job_application_assistance is 'User-controlled employer-page handoff with no automatic submission; never evidence of submission without the user confirmation event.';

notify pgrst, 'reload schema';
