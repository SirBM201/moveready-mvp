-- Project MoveReady MVP
-- User relocation profile storage.
-- Run after 001 through 007 migrations.

create table if not exists public.relocation_user_profiles (
  id uuid primary key default gen_random_uuid(),
  full_name text,
  email text,
  phone text,
  current_country text,
  nationality text,
  residence_country text,
  target_country text,
  target_city text,
  main_goal text not null default 'relocation' check (main_goal in ('study', 'scholarship', 'work', 'startup', 'business', 'digital_nomad', 'family', 'visit', 'opportunity', 'relocation')),
  route_category text,
  timeline_months integer,
  family_members_count integer not null default 0,
  available_funds_amount numeric,
  available_funds_currency text default 'USD',
  education_level text,
  work_experience_years numeric,
  business_stage text,
  has_previous_refusal boolean not null default false,
  preferred_contact_channel text not null default 'email' check (preferred_contact_channel in ('email', 'whatsapp', 'telegram', 'phone')),
  consent_to_contact boolean not null default false,
  readiness_snapshot jsonb not null default '{}'::jsonb,
  notes text,
  source_page text,
  status text not null default 'new' check (status in ('new', 'reviewing', 'contacted', 'active', 'closed', 'spam')),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists relocation_user_profiles_email_idx on public.relocation_user_profiles (email);
create index if not exists relocation_user_profiles_goal_idx on public.relocation_user_profiles (main_goal);
create index if not exists relocation_user_profiles_target_country_idx on public.relocation_user_profiles (target_country);
create index if not exists relocation_user_profiles_status_idx on public.relocation_user_profiles (status);
create index if not exists relocation_user_profiles_created_at_idx on public.relocation_user_profiles (created_at desc);

drop trigger if exists relocation_user_profiles_set_updated_at on public.relocation_user_profiles;
create trigger relocation_user_profiles_set_updated_at
before update on public.relocation_user_profiles
for each row execute function public.relocation_set_updated_at();
