-- Project MoveReady MVP
-- Partner and provider application storage.
-- Run after 001 through 010 migrations.
-- Safe to rerun if the table was partially created before this migration.

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

create table if not exists public.relocation_partner_applications (
  id uuid primary key default gen_random_uuid(),
  provider_type text not null default 'other' check (provider_type in (
    'courier',
    'insurance',
    'legalization',
    'translation',
    'expert_review',
    'admission_support',
    'accommodation',
    'airport_pickup',
    'settlement',
    'other'
  )),
  business_name text not null,
  contact_name text,
  email text,
  phone text,
  website_url text,
  country text,
  city text,
  service_countries text[] not null default '{}',
  service_summary text,
  credentials_summary text,
  compliance_notes text,
  pricing_notes text,
  preferred_contact_channel text not null default 'email' check (preferred_contact_channel in ('email', 'whatsapp', 'telegram', 'phone')),
  consent_to_contact boolean not null default false,
  status text not null default 'new' check (status in ('new', 'screening', 'approved', 'rejected', 'waitlist', 'suspended', 'spam')),
  internal_notes text,
  source_page text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.relocation_partner_applications
  add column if not exists provider_type text not null default 'other',
  add column if not exists business_name text,
  add column if not exists contact_name text,
  add column if not exists email text,
  add column if not exists phone text,
  add column if not exists website_url text,
  add column if not exists country text,
  add column if not exists city text,
  add column if not exists service_countries text[] not null default '{}',
  add column if not exists service_summary text,
  add column if not exists credentials_summary text,
  add column if not exists compliance_notes text,
  add column if not exists pricing_notes text,
  add column if not exists preferred_contact_channel text not null default 'email',
  add column if not exists consent_to_contact boolean not null default false,
  add column if not exists status text not null default 'new',
  add column if not exists internal_notes text,
  add column if not exists source_page text,
  add column if not exists metadata jsonb not null default '{}'::jsonb,
  add column if not exists created_at timestamptz not null default now(),
  add column if not exists updated_at timestamptz not null default now();

update public.relocation_partner_applications
set business_name = coalesce(nullif(business_name, ''), 'Unnamed provider')
where business_name is null or business_name = '';

alter table public.relocation_partner_applications
  alter column business_name set not null;

create index if not exists relocation_partner_applications_provider_type_idx on public.relocation_partner_applications (provider_type);
create index if not exists relocation_partner_applications_status_idx on public.relocation_partner_applications (status);
create index if not exists relocation_partner_applications_country_idx on public.relocation_partner_applications (country);
create index if not exists relocation_partner_applications_created_at_idx on public.relocation_partner_applications (created_at desc);

drop trigger if exists relocation_partner_applications_set_updated_at on public.relocation_partner_applications;
create trigger relocation_partner_applications_set_updated_at
before update on public.relocation_partner_applications
for each row
execute function public.relocation_set_updated_at();
