-- Project MoveReady MVP
-- Initial Supabase schema for source-backed relocation readiness.
-- Run in Supabase SQL editor after reviewing.

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

create table if not exists public.relocation_users (
  id uuid primary key default gen_random_uuid(),
  email text unique,
  full_name text,
  phone text,
  home_country_code text,
  current_country_code text,
  preferred_language text default 'en',
  status text not null default 'active' check (status in ('active','blocked','deleted')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.relocation_user_profiles (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references public.relocation_users(id) on delete cascade,
  goal text not null check (goal in ('study','work','business','visit','family','scholarship','relocation','digital_nomad','other')),
  target_country_codes text[] default '{}',
  nationality_code text,
  residence_country_code text,
  education_level text,
  work_experience_years numeric(5,2),
  available_funds_amount numeric(14,2),
  available_funds_currency text,
  family_members_count integer default 0,
  timeline_months integer,
  profile_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.relocation_countries (
  id uuid primary key default gen_random_uuid(),
  country_code text not null unique,
  country_name text not null,
  region text,
  currency_code text,
  official_language_codes text[] default '{}',
  is_active boolean not null default true,
  summary text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.relocation_trusted_sources (
  id uuid primary key default gen_random_uuid(),
  country_id uuid references public.relocation_countries(id) on delete set null,
  source_name text not null,
  source_url text not null,
  source_type text not null check (source_type in ('government','embassy','visa_center','university','scholarship_body','insurance','courier','news','partner','other')),
  owner_organization text,
  reliability_level text not null default 'high' check (reliability_level in ('high','medium','low')),
  status text not null default 'active' check (status in ('active','watching','needs_review','retired')),
  review_frequency_days integer not null default 30,
  last_checked_at timestamptz,
  next_review_due_at timestamptz,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (source_url)
);

create table if not exists public.relocation_source_snapshots (
  id uuid primary key default gen_random_uuid(),
  source_id uuid not null references public.relocation_trusted_sources(id) on delete cascade,
  captured_at timestamptz not null default now(),
  content_hash text,
  snapshot_title text,
  extracted_text text,
  structured_payload jsonb not null default '{}'::jsonb,
  status text not null default 'captured' check (status in ('captured','changed','reviewed','rejected')),
  reviewed_at timestamptz,
  reviewed_by text,
  notes text,
  created_at timestamptz not null default now()
);

create table if not exists public.relocation_source_change_alerts (
  id uuid primary key default gen_random_uuid(),
  source_id uuid not null references public.relocation_trusted_sources(id) on delete cascade,
  old_snapshot_id uuid references public.relocation_source_snapshots(id) on delete set null,
  new_snapshot_id uuid references public.relocation_source_snapshots(id) on delete set null,
  alert_type text not null check (alert_type in ('new_source','content_changed','source_unavailable','review_due','manual')),
  severity text not null default 'medium' check (severity in ('low','medium','high','critical')),
  status text not null default 'open' check (status in ('open','in_review','resolved','dismissed')),
  summary text,
  created_at timestamptz not null default now(),
  resolved_at timestamptz
);

create table if not exists public.relocation_visa_routes (
  id uuid primary key default gen_random_uuid(),
  country_id uuid not null references public.relocation_countries(id) on delete cascade,
  route_code text not null,
  route_name text not null,
  route_category text not null check (route_category in ('study','work','business','startup','digital_nomad','visit','family','scholarship','permanent_residence','protection','other')),
  is_public boolean not null default true,
  active_version_id uuid,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (country_id, route_code)
);

create table if not exists public.relocation_route_versions (
  id uuid primary key default gen_random_uuid(),
  route_id uuid not null references public.relocation_visa_routes(id) on delete cascade,
  version_label text not null,
  status text not null default 'draft' check (status in ('draft','pending_review','active','superseded','retired')),
  risk_level text not null default 'medium' check (risk_level in ('low','medium','high','critical')),
  route_summary text,
  eligibility_notes text,
  proof_of_funds_notes text,
  family_notes text,
  processing_time_notes text,
  validity_notes text,
  official_fee_notes text,
  refusal_risk_notes text,
  source_confidence text not null default 'medium' check (source_confidence in ('high','medium','low')),
  verified_at timestamptz,
  review_due_at timestamptz,
  approved_at timestamptz,
  approved_by text,
  created_by text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (route_id, version_label)
);

alter table public.relocation_visa_routes
  add constraint relocation_visa_routes_active_version_fk
  foreign key (active_version_id)
  references public.relocation_route_versions(id)
  on delete set null;

create table if not exists public.relocation_route_sources (
  id uuid primary key default gen_random_uuid(),
  route_version_id uuid not null references public.relocation_route_versions(id) on delete cascade,
  source_id uuid not null references public.relocation_trusted_sources(id) on delete restrict,
  snapshot_id uuid references public.relocation_source_snapshots(id) on delete set null,
  usage_note text,
  created_at timestamptz not null default now(),
  unique (route_version_id, source_id)
);

create table if not exists public.relocation_route_facts (
  id uuid primary key default gen_random_uuid(),
  route_version_id uuid not null references public.relocation_route_versions(id) on delete cascade,
  fact_key text not null,
  fact_label text not null,
  fact_value text,
  fact_payload jsonb not null default '{}'::jsonb,
  display_order integer not null default 100,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (route_version_id, fact_key)
);

create table if not exists public.relocation_document_requirements (
  id uuid primary key default gen_random_uuid(),
  route_version_id uuid not null references public.relocation_route_versions(id) on delete cascade,
  document_name text not null,
  requirement_level text not null default 'required' check (requirement_level in ('required','conditional','recommended','optional')),
  applies_to text not null default 'main_applicant' check (applies_to in ('main_applicant','spouse','child','sponsor','employer','school','other')),
  details text,
  source_id uuid references public.relocation_trusted_sources(id) on delete set null,
  display_order integer not null default 100,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.relocation_budget_items (
  id uuid primary key default gen_random_uuid(),
  country_id uuid references public.relocation_countries(id) on delete cascade,
  route_version_id uuid references public.relocation_route_versions(id) on delete cascade,
  item_name text not null,
  item_category text not null check (item_category in ('visa_fee','proof_of_funds','insurance','flight','accommodation','document','courier','translation','notarization','settlement','other')),
  amount_min numeric(14,2),
  amount_max numeric(14,2),
  currency_code text,
  is_required boolean not null default false,
  notes text,
  source_id uuid references public.relocation_trusted_sources(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.relocation_scholarships (
  id uuid primary key default gen_random_uuid(),
  country_id uuid references public.relocation_countries(id) on delete set null,
  scholarship_name text not null,
  provider_name text,
  scholarship_url text,
  eligible_country_codes text[] default '{}',
  education_levels text[] default '{}',
  deadline_date date,
  funding_type text check (funding_type in ('full','partial','tuition','living_cost','travel','other')),
  status text not null default 'active' check (status in ('active','needs_review','closed','retired')),
  summary text,
  source_id uuid references public.relocation_trusted_sources(id) on delete set null,
  last_verified_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.relocation_insurance_requirements (
  id uuid primary key default gen_random_uuid(),
  country_id uuid references public.relocation_countries(id) on delete cascade,
  route_version_id uuid references public.relocation_route_versions(id) on delete cascade,
  insurance_type text not null check (insurance_type in ('travel','health','student','family','work','other')),
  is_required boolean not null default false,
  minimum_coverage_amount numeric(14,2),
  currency_code text,
  details text,
  source_id uuid references public.relocation_trusted_sources(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.relocation_generated_reports (
  id uuid primary key default gen_random_uuid(),
  report_ref text not null unique,
  user_id uuid references public.relocation_users(id) on delete set null,
  user_profile_id uuid references public.relocation_user_profiles(id) on delete set null,
  route_version_id uuid references public.relocation_route_versions(id) on delete set null,
  status text not null default 'generated' check (status in ('draft','generated','paid','delivered','stale','refreshed','archived')),
  report_title text not null,
  risk_level text not null default 'medium' check (risk_level in ('low','medium','high','critical')),
  source_snapshot_ids uuid[] default '{}',
  input_payload jsonb not null default '{}'::jsonb,
  report_payload jsonb not null default '{}'::jsonb,
  generated_at timestamptz not null default now(),
  stale_reason text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.relocation_report_sections (
  id uuid primary key default gen_random_uuid(),
  report_id uuid not null references public.relocation_generated_reports(id) on delete cascade,
  section_key text not null,
  section_title text not null,
  section_content text,
  section_payload jsonb not null default '{}'::jsonb,
  display_order integer not null default 100,
  created_at timestamptz not null default now(),
  unique (report_id, section_key)
);

create table if not exists public.relocation_ai_answer_cache (
  id uuid primary key default gen_random_uuid(),
  cache_key text not null unique,
  route_version_id uuid references public.relocation_route_versions(id) on delete set null,
  source_snapshot_ids uuid[] default '{}',
  prompt_hash text,
  answer_text text not null,
  answer_payload jsonb not null default '{}'::jsonb,
  status text not null default 'fresh' check (status in ('fresh','stale','superseded','blocked')),
  expires_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.relocation_admin_review_tasks (
  id uuid primary key default gen_random_uuid(),
  task_type text not null check (task_type in ('source_review','route_review','scholarship_review','insurance_review','report_review','manual')),
  status text not null default 'open' check (status in ('open','in_progress','approved','rejected','dismissed')),
  priority text not null default 'medium' check (priority in ('low','medium','high','urgent')),
  source_id uuid references public.relocation_trusted_sources(id) on delete set null,
  route_version_id uuid references public.relocation_route_versions(id) on delete set null,
  alert_id uuid references public.relocation_source_change_alerts(id) on delete set null,
  title text not null,
  description text,
  assigned_to text,
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.relocation_user_saved_routes (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.relocation_users(id) on delete cascade,
  route_id uuid not null references public.relocation_visa_routes(id) on delete cascade,
  notes text,
  created_at timestamptz not null default now(),
  unique (user_id, route_id)
);

create table if not exists public.relocation_user_alerts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.relocation_users(id) on delete cascade,
  route_id uuid references public.relocation_visa_routes(id) on delete cascade,
  alert_type text not null check (alert_type in ('route_changed','review_due','report_stale','deadline','manual')),
  status text not null default 'unread' check (status in ('unread','read','dismissed')),
  title text not null,
  message text,
  created_at timestamptz not null default now(),
  read_at timestamptz
);

create index if not exists idx_relocation_user_profiles_user_id on public.relocation_user_profiles(user_id);
create index if not exists idx_relocation_countries_code on public.relocation_countries(country_code);
create index if not exists idx_relocation_sources_country_status on public.relocation_trusted_sources(country_id, status);
create index if not exists idx_relocation_snapshots_source_captured on public.relocation_source_snapshots(source_id, captured_at desc);
create index if not exists idx_relocation_routes_country_category on public.relocation_visa_routes(country_id, route_category);
create index if not exists idx_relocation_route_versions_route_status on public.relocation_route_versions(route_id, status);
create index if not exists idx_relocation_documents_route_version on public.relocation_document_requirements(route_version_id);
create index if not exists idx_relocation_budget_country_route on public.relocation_budget_items(country_id, route_version_id);
create index if not exists idx_relocation_reports_user on public.relocation_generated_reports(user_id, generated_at desc);
create index if not exists idx_relocation_ai_cache_route_status on public.relocation_ai_answer_cache(route_version_id, status);
create index if not exists idx_relocation_review_tasks_status_priority on public.relocation_admin_review_tasks(status, priority);

create trigger relocation_users_set_updated_at
before update on public.relocation_users
for each row execute function public.relocation_set_updated_at();

create trigger relocation_user_profiles_set_updated_at
before update on public.relocation_user_profiles
for each row execute function public.relocation_set_updated_at();

create trigger relocation_countries_set_updated_at
before update on public.relocation_countries
for each row execute function public.relocation_set_updated_at();

create trigger relocation_trusted_sources_set_updated_at
before update on public.relocation_trusted_sources
for each row execute function public.relocation_set_updated_at();

create trigger relocation_visa_routes_set_updated_at
before update on public.relocation_visa_routes
for each row execute function public.relocation_set_updated_at();

create trigger relocation_route_versions_set_updated_at
before update on public.relocation_route_versions
for each row execute function public.relocation_set_updated_at();

create trigger relocation_route_facts_set_updated_at
before update on public.relocation_route_facts
for each row execute function public.relocation_set_updated_at();

create trigger relocation_document_requirements_set_updated_at
before update on public.relocation_document_requirements
for each row execute function public.relocation_set_updated_at();

create trigger relocation_budget_items_set_updated_at
before update on public.relocation_budget_items
for each row execute function public.relocation_set_updated_at();

create trigger relocation_scholarships_set_updated_at
before update on public.relocation_scholarships
for each row execute function public.relocation_set_updated_at();

create trigger relocation_insurance_requirements_set_updated_at
before update on public.relocation_insurance_requirements
for each row execute function public.relocation_set_updated_at();

create trigger relocation_generated_reports_set_updated_at
before update on public.relocation_generated_reports
for each row execute function public.relocation_set_updated_at();

create trigger relocation_ai_answer_cache_set_updated_at
before update on public.relocation_ai_answer_cache
for each row execute function public.relocation_set_updated_at();

create trigger relocation_admin_review_tasks_set_updated_at
before update on public.relocation_admin_review_tasks
for each row execute function public.relocation_set_updated_at();

alter table public.relocation_users enable row level security;
alter table public.relocation_user_profiles enable row level security;
alter table public.relocation_countries enable row level security;
alter table public.relocation_trusted_sources enable row level security;
alter table public.relocation_source_snapshots enable row level security;
alter table public.relocation_source_change_alerts enable row level security;
alter table public.relocation_visa_routes enable row level security;
alter table public.relocation_route_versions enable row level security;
alter table public.relocation_route_sources enable row level security;
alter table public.relocation_route_facts enable row level security;
alter table public.relocation_document_requirements enable row level security;
alter table public.relocation_budget_items enable row level security;
alter table public.relocation_scholarships enable row level security;
alter table public.relocation_insurance_requirements enable row level security;
alter table public.relocation_generated_reports enable row level security;
alter table public.relocation_report_sections enable row level security;
alter table public.relocation_ai_answer_cache enable row level security;
alter table public.relocation_admin_review_tasks enable row level security;
alter table public.relocation_user_saved_routes enable row level security;
alter table public.relocation_user_alerts enable row level security;

comment on table public.relocation_route_versions is 'Versioned route facts. Only active versions should be used for new public answers.';
comment on table public.relocation_source_snapshots is 'Captured source state used for freshness review and report audit trails.';
comment on table public.relocation_ai_answer_cache is 'Cached AI answers tied to route/source versions. Do not reuse stale, superseded, or blocked entries.';
comment on table public.relocation_generated_reports is 'Relocation readiness reports preserving source and route version context at generation time.';
