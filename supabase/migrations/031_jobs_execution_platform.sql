-- Project MoveReady
-- Jobs execution platform: reusable employer directory plus private account
-- search profiles, targets, recruiters, jobs, applications, and resume files.
-- Run after migration 030. Safe to rerun.

create extension if not exists pgcrypto;

create or replace function public.relocation_set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create table if not exists public.relocation_job_search_profiles (
  id uuid primary key default gen_random_uuid(),
  email text not null unique,
  relocation_profile_id uuid references public.relocation_user_profiles(id) on delete set null,
  display_name text,
  headline text not null,
  years_experience integer check (years_experience between 0 and 60),
  education_level text,
  current_employer text,
  previous_employer text,
  target_roles text[] not null default '{}'::text[],
  skills text[] not null default '{}'::text[],
  primary_country text not null default 'Canada',
  later_countries text[] not null default '{}'::text[],
  preferred_provinces text[] not null default '{}'::text[],
  work_authorization_status text not null default 'requires_sponsorship' check (
    work_authorization_status in ('citizen', 'permanent_resident', 'open_permit', 'employer_specific_permit', 'requires_sponsorship', 'not_recorded')
  ),
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.relocation_job_companies (
  id uuid primary key default gen_random_uuid(),
  owner_email text,
  is_curated boolean not null default false,
  company_name text not null,
  slug text not null,
  industry text not null,
  country text not null default 'Canada',
  province text,
  website text,
  career_page text,
  visa_sponsorship_status text not null default 'unknown' check (
    visa_sponsorship_status in ('unknown', 'not_verified', 'possible', 'confirmed', 'not_available')
  ),
  lmia_history_status text not null default 'unknown' check (
    lmia_history_status in ('unknown', 'not_verified', 'possible', 'confirmed', 'not_found')
  ),
  salary_min numeric(14,2),
  salary_max numeric(14,2),
  salary_currency text,
  source_url text,
  source_status text not null default 'review_required' check (
    source_status in ('verified', 'review_required', 'stale', 'unavailable')
  ),
  last_verified_at timestamptz,
  record_status text not null default 'active' check (record_status in ('active', 'watch', 'legacy', 'archived')),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check ((is_curated and owner_email is null) or (not is_curated and owner_email is not null)),
  check (salary_min is null or salary_min >= 0),
  check (salary_max is null or salary_max >= 0),
  check (salary_min is null or salary_max is null or salary_max >= salary_min)
);

create unique index if not exists relocation_job_companies_curated_slug_uidx
on public.relocation_job_companies (slug)
where is_curated;

create index if not exists relocation_job_companies_directory_idx
on public.relocation_job_companies (country, province, industry, company_name);

create index if not exists relocation_job_companies_owner_idx
on public.relocation_job_companies (owner_email, updated_at desc)
where owner_email is not null;

create table if not exists public.relocation_job_company_targets (
  id uuid primary key default gen_random_uuid(),
  email text not null,
  company_id uuid not null references public.relocation_job_companies(id) on delete cascade,
  priority text not null default 'medium' check (priority in ('high', 'medium', 'low', 'watch')),
  status text not null default 'researching' check (
    status in ('researching', 'targeting', 'contacted', 'applied', 'interview', 'offer', 'paused', 'archived')
  ),
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (email, company_id)
);

create index if not exists relocation_job_company_targets_email_idx
on public.relocation_job_company_targets (email, priority, status, updated_at desc);

create table if not exists public.relocation_job_recruiters (
  id uuid primary key default gen_random_uuid(),
  owner_email text not null,
  company_id uuid references public.relocation_job_companies(id) on delete set null,
  recruiter_name text not null,
  recruitment_company text,
  province text,
  specialization text,
  linkedin_url text,
  website text,
  email_address text,
  phone text,
  connected boolean not null default false,
  connection_status text not null default 'not_contacted' check (
    connection_status in ('not_contacted', 'connection_requested', 'connected', 'contacted', 'responded', 'follow_up', 'inactive')
  ),
  last_contacted_at timestamptz,
  follow_up_date date,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists relocation_job_recruiters_owner_idx
on public.relocation_job_recruiters (owner_email, connection_status, follow_up_date, updated_at desc);

create table if not exists public.relocation_jobs (
  id uuid primary key default gen_random_uuid(),
  owner_email text,
  is_curated boolean not null default false,
  company_id uuid references public.relocation_job_companies(id) on delete set null,
  recruiter_id uuid references public.relocation_job_recruiters(id) on delete set null,
  job_title text not null,
  country text not null default 'Canada',
  province text,
  city text,
  employment_type text,
  workplace_type text check (workplace_type is null or workplace_type in ('onsite', 'hybrid', 'remote')),
  job_url text,
  source_name text,
  source_url text,
  description_summary text,
  skills text[] not null default '{}'::text[],
  salary_min numeric(14,2),
  salary_max numeric(14,2),
  salary_currency text,
  visa_sponsorship_status text not null default 'unknown' check (
    visa_sponsorship_status in ('unknown', 'not_verified', 'possible', 'confirmed', 'not_available')
  ),
  posted_at timestamptz,
  expires_at timestamptz,
  status text not null default 'open' check (status in ('discovered', 'open', 'closed', 'expired', 'archived')),
  source_status text not null default 'review_required' check (
    source_status in ('verified', 'review_required', 'stale', 'unavailable')
  ),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check ((is_curated and owner_email is null) or (not is_curated and owner_email is not null)),
  check (salary_min is null or salary_min >= 0),
  check (salary_max is null or salary_max >= 0),
  check (salary_min is null or salary_max is null or salary_max >= salary_min)
);

create index if not exists relocation_jobs_discovery_idx
on public.relocation_jobs (country, province, status, posted_at desc);

create index if not exists relocation_jobs_owner_idx
on public.relocation_jobs (owner_email, status, updated_at desc)
where owner_email is not null;

create table if not exists public.relocation_job_resume_assets (
  id uuid primary key default gen_random_uuid(),
  email text not null,
  document_type text not null check (
    document_type in ('executive_resume', 'ats_resume', 'cover_letter', 'manufacturing_portfolio')
  ),
  title text not null,
  original_file_name text not null,
  mime_type text not null check (
    mime_type in ('application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain')
  ),
  size_bytes integer not null check (size_bytes between 1 and 5242880),
  storage_bucket text not null default 'job-resume-vault',
  storage_path text not null unique,
  version integer not null default 1 check (version > 0),
  is_active boolean not null default true,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists relocation_job_resume_assets_owner_idx
on public.relocation_job_resume_assets (email, document_type, is_active, updated_at desc);

create table if not exists public.relocation_job_applications (
  id uuid primary key default gen_random_uuid(),
  email text not null,
  job_id uuid references public.relocation_jobs(id) on delete set null,
  company_id uuid references public.relocation_job_companies(id) on delete set null,
  recruiter_id uuid references public.relocation_job_recruiters(id) on delete set null,
  job_title text not null,
  company_name text not null,
  country text not null default 'Canada',
  province text,
  job_url text,
  status text not null default 'saved' check (status in ('saved', 'applied', 'interview', 'rejected', 'offer', 'visa')),
  date_applied date,
  follow_up_date date,
  interview_date timestamptz,
  documents_used jsonb not null default '[]'::jsonb check (jsonb_typeof(documents_used) = 'array'),
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists relocation_job_applications_owner_idx
on public.relocation_job_applications (email, status, follow_up_date, updated_at desc);

create index if not exists relocation_job_applications_company_idx
on public.relocation_job_applications (company_id, status)
where company_id is not null;

drop trigger if exists relocation_job_search_profiles_set_updated_at on public.relocation_job_search_profiles;
create trigger relocation_job_search_profiles_set_updated_at before update on public.relocation_job_search_profiles
for each row execute function public.relocation_set_updated_at();

drop trigger if exists relocation_job_companies_set_updated_at on public.relocation_job_companies;
create trigger relocation_job_companies_set_updated_at before update on public.relocation_job_companies
for each row execute function public.relocation_set_updated_at();

drop trigger if exists relocation_job_company_targets_set_updated_at on public.relocation_job_company_targets;
create trigger relocation_job_company_targets_set_updated_at before update on public.relocation_job_company_targets
for each row execute function public.relocation_set_updated_at();

drop trigger if exists relocation_job_recruiters_set_updated_at on public.relocation_job_recruiters;
create trigger relocation_job_recruiters_set_updated_at before update on public.relocation_job_recruiters
for each row execute function public.relocation_set_updated_at();

drop trigger if exists relocation_jobs_set_updated_at on public.relocation_jobs;
create trigger relocation_jobs_set_updated_at before update on public.relocation_jobs
for each row execute function public.relocation_set_updated_at();

drop trigger if exists relocation_job_resume_assets_set_updated_at on public.relocation_job_resume_assets;
create trigger relocation_job_resume_assets_set_updated_at before update on public.relocation_job_resume_assets
for each row execute function public.relocation_set_updated_at();

drop trigger if exists relocation_job_applications_set_updated_at on public.relocation_job_applications;
create trigger relocation_job_applications_set_updated_at before update on public.relocation_job_applications
for each row execute function public.relocation_set_updated_at();

-- Resume files are private. Only the backend service role uses this bucket.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'job-resume-vault',
  'job-resume-vault',
  false,
  5242880,
  array[
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'text/plain'
  ]
)
on conflict (id) do update set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

-- Approved founder Tier-1 target directory. Priority and notes are never
-- stored here; those remain private in relocation_job_company_targets.
insert into public.relocation_job_companies (
  id, is_curated, company_name, slug, industry, country, province, website,
  career_page, source_url, source_status, last_verified_at, record_status, metadata
)
values
  ('10000000-0000-4000-8000-000000000001', true, 'ALPLA', 'alpla', 'Plastic packaging and PET preforms', 'Canada', 'Multiple', 'https://www.alpla.com/en', 'https://career.alpla.com/en', 'https://career.alpla.com/en', 'verified', '2026-08-11T00:00:00Z', 'active', '{"founder_tier":1}'::jsonb),
  ('10000000-0000-4000-8000-000000000002', true, 'Plastipak', 'plastipak', 'Rigid plastic packaging and PET preforms', 'Canada', 'Multiple', 'https://www.plastipak.com/', 'https://www.plastipak.com/careers/', 'https://www.plastipak.com/careers/', 'verified', '2026-08-11T00:00:00Z', 'active', '{"founder_tier":1}'::jsonb),
  ('10000000-0000-4000-8000-000000000003', true, 'Berry Global', 'berry-global', 'Plastic packaging', 'Canada', 'Multiple', 'https://www.amcor.com/', 'https://www.amcor.com/careers', 'https://www.amcor.com/careers', 'verified', '2026-08-11T00:00:00Z', 'legacy', '{"founder_tier":1,"note":"Legacy target retained after integration with Amcor."}'::jsonb),
  ('10000000-0000-4000-8000-000000000004', true, 'Amcor', 'amcor', 'Packaging manufacturing', 'Canada', 'Multiple', 'https://www.amcor.com/', 'https://www.amcor.com/careers', 'https://www.amcor.com/careers', 'verified', '2026-08-11T00:00:00Z', 'active', '{"founder_tier":1}'::jsonb),
  ('10000000-0000-4000-8000-000000000005', true, 'IPL Schoeller', 'ipl-schoeller', 'Rigid and reusable plastic packaging', 'Canada', 'Multiple', 'https://www.iplglobal.com/', 'https://www.iplglobal.com/careers', 'https://www.iplglobal.com/', 'verified', '2026-08-11T00:00:00Z', 'active', '{"founder_tier":1,"legacy_name":"IPL"}'::jsonb),
  ('10000000-0000-4000-8000-000000000006', true, 'Husky Technologies', 'husky-technologies', 'Injection moulding systems and tooling', 'Canada', 'Ontario', 'https://www.husky.co/', 'https://www.husky.co/en/careers/portal/', 'https://www.husky.co/en/careers/', 'verified', '2026-08-11T00:00:00Z', 'active', '{"founder_tier":1}'::jsonb),
  ('10000000-0000-4000-8000-000000000007', true, 'ABC Technologies', 'abc-technologies', 'Automotive plastics manufacturing', 'Canada', 'Ontario', 'https://abctechnologies.com/', 'https://abctechnologies.com/careers/', 'https://abctechnologies.com/careers/', 'verified', '2026-08-11T00:00:00Z', 'active', '{"founder_tier":1}'::jsonb),
  ('10000000-0000-4000-8000-000000000008', true, 'Magna', 'magna', 'Automotive manufacturing', 'Canada', 'Ontario', 'https://www.magna.com/', 'https://www.magna.com/careers', 'https://www.magna.com/careers', 'verified', '2026-08-11T00:00:00Z', 'active', '{"founder_tier":1}'::jsonb),
  ('10000000-0000-4000-8000-000000000009', true, 'Winpak', 'winpak', 'Flexible and rigid packaging', 'Canada', 'Manitoba', 'https://www.winpak.com/', 'https://www.winpak.com/careers', 'https://www.winpak.com/careers', 'verified', '2026-08-11T00:00:00Z', 'active', '{"founder_tier":1}'::jsonb),
  ('10000000-0000-4000-8000-000000000010', true, 'CCL Industries', 'ccl-industries', 'Labels and specialty packaging', 'Canada', 'Ontario', 'https://www.cclind.com/', 'https://www.cclind.com/careers/', 'https://www.cclind.com/careers/', 'review_required', null, 'active', '{"founder_tier":1}'::jsonb),
  ('10000000-0000-4000-8000-000000000011', true, 'Encore Custom Preforms', 'encore-custom-preforms', 'PET preform manufacturing', 'Canada', 'Ontario', 'https://www.encorecustompreforms.com/', 'https://www.encorecustompreforms.com/', 'https://www.encorecustompreforms.com/', 'verified', '2026-08-11T00:00:00Z', 'active', '{"founder_tier":1}'::jsonb),
  ('10000000-0000-4000-8000-000000000012', true, 'Trans-Atlantic Preforms', 'trans-atlantic-preforms', 'PET preform manufacturing', 'Canada', 'Nova Scotia', 'https://tapl.ca/', 'https://tapl.ca/', 'https://tapl.ca/', 'verified', '2026-08-11T00:00:00Z', 'active', '{"founder_tier":1}'::jsonb),
  ('10000000-0000-4000-8000-000000000013', true, 'Mitchell Plastics', 'mitchell-plastics', 'Automotive injection moulding', 'Canada', 'Ontario', 'https://www.mitchellplastics.com/', 'https://www.mitchellplastics.com/careers', 'https://www.mitchellplastics.com/careers', 'verified', '2026-08-11T00:00:00Z', 'active', '{"founder_tier":1}'::jsonb),
  ('10000000-0000-4000-8000-000000000014', true, 'StackTeck', 'stackteck', 'Injection mould manufacturing and qualification', 'Canada', 'Ontario', 'https://stackteck.com/', 'https://stackteck.com/careers/', 'https://stackteck.com/careers/', 'verified', '2026-08-11T00:00:00Z', 'active', '{"founder_tier":1}'::jsonb),
  ('10000000-0000-4000-8000-000000000015', true, 'Axiom Group', 'axiom-group', 'Automotive plastics, tooling, and engineering', 'Canada', 'Ontario', 'https://axiomex.com/', 'https://axiomex.com/search-apply/', 'https://axiomex.com/search-apply/', 'verified', '2026-08-11T00:00:00Z', 'active', '{"founder_tier":1}'::jsonb)
on conflict (id) do update set
  company_name = excluded.company_name,
  slug = excluded.slug,
  industry = excluded.industry,
  country = excluded.country,
  province = excluded.province,
  website = excluded.website,
  career_page = excluded.career_page,
  source_url = excluded.source_url,
  source_status = excluded.source_status,
  last_verified_at = excluded.last_verified_at,
  record_status = excluded.record_status,
  metadata = excluded.metadata,
  updated_at = now();

-- Every Jobs table is backend-only. The API authorizes each request from the
-- MoveReady session and uses the service role for database/storage access.
alter table public.relocation_job_search_profiles enable row level security;
alter table public.relocation_job_companies enable row level security;
alter table public.relocation_job_company_targets enable row level security;
alter table public.relocation_job_recruiters enable row level security;
alter table public.relocation_jobs enable row level security;
alter table public.relocation_job_resume_assets enable row level security;
alter table public.relocation_job_applications enable row level security;

revoke all privileges on table public.relocation_job_search_profiles from public, anon, authenticated;
revoke all privileges on table public.relocation_job_companies from public, anon, authenticated;
revoke all privileges on table public.relocation_job_company_targets from public, anon, authenticated;
revoke all privileges on table public.relocation_job_recruiters from public, anon, authenticated;
revoke all privileges on table public.relocation_jobs from public, anon, authenticated;
revoke all privileges on table public.relocation_job_resume_assets from public, anon, authenticated;
revoke all privileges on table public.relocation_job_applications from public, anon, authenticated;

grant all privileges on table public.relocation_job_search_profiles to service_role;
grant all privileges on table public.relocation_job_companies to service_role;
grant all privileges on table public.relocation_job_company_targets to service_role;
grant all privileges on table public.relocation_job_recruiters to service_role;
grant all privileges on table public.relocation_jobs to service_role;
grant all privileges on table public.relocation_job_resume_assets to service_role;
grant all privileges on table public.relocation_job_applications to service_role;

comment on table public.relocation_job_companies is 'Reusable employer directory; private priority, status, and notes live in relocation_job_company_targets.';
comment on table public.relocation_job_resume_assets is 'Private resume and cover-letter file metadata. File bytes remain in the private job-resume-vault bucket.';
comment on column public.relocation_job_companies.visa_sponsorship_status is 'Evidence status only; unknown is not a negative sponsorship determination.';
comment on column public.relocation_job_companies.lmia_history_status is 'Evidence status only; do not infer current LMIA eligibility without official verification.';

notify pgrst, 'reload schema';
