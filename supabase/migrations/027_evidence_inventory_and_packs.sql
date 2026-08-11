-- Project MoveReady MVP
-- Private document inventory metadata and generated evidence packs.
-- This migration does not create file-upload or raw-document storage and does
-- not store a full document number.
-- Run after migration 026. Safe to rerun.

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

create table if not exists public.relocation_user_document_inventory (
  id uuid primary key default gen_random_uuid(),
  email text not null,
  profile_id uuid references public.relocation_user_profiles(id) on delete set null,
  document_type text not null check (document_type in (
    'passport',
    'bank_statement',
    'proof_of_funds',
    'employment_letter',
    'payslip',
    'academic_certificate',
    'academic_transcript',
    'admission_letter',
    'language_test',
    'birth_certificate',
    'marriage_certificate',
    'civil_document',
    'police_certificate',
    'insurance',
    'accommodation',
    'business_plan',
    'company_document',
    'founder_evidence',
    'travel_itinerary',
    'purpose_evidence',
    'relationship_evidence',
    'consent_or_custody_document',
    'medical_document',
    'refusal_record',
    'other'
  )),
  document_label text not null,
  owner_scope text not null default 'main_applicant' check (owner_scope in (
    'main_applicant', 'spouse', 'child', 'dependant', 'sponsor', 'employer', 'school', 'other'
  )),
  name_on_document text,
  issuing_country text,
  document_language text,
  issue_date date,
  expiry_date date,
  status text not null default 'available' check (status in (
    'available',
    'missing',
    'renewal_needed',
    'translation_pending',
    'legalization_pending',
    'correction_pending',
    'ready',
    'expired',
    'archived'
  )),
  translation_status text not null default 'unknown' check (translation_status in (
    'not_required', 'unknown', 'pending', 'completed', 'rejected'
  )),
  legalization_status text not null default 'unknown' check (legalization_status in (
    'not_required', 'unknown', 'pending', 'completed', 'rejected'
  )),
  sensitive boolean not null default true,
  notes text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists relocation_user_document_inventory_email_idx
on public.relocation_user_document_inventory (email, status, created_at desc);

create index if not exists relocation_user_document_inventory_expiry_idx
on public.relocation_user_document_inventory (expiry_date)
where expiry_date is not null and status <> 'archived';

create index if not exists relocation_user_document_inventory_profile_idx
on public.relocation_user_document_inventory (profile_id)
where profile_id is not null;

drop trigger if exists relocation_user_document_inventory_set_updated_at
on public.relocation_user_document_inventory;

create trigger relocation_user_document_inventory_set_updated_at
before update on public.relocation_user_document_inventory
for each row execute function public.relocation_set_updated_at();

create table if not exists public.relocation_evidence_packs (
  id uuid primary key default gen_random_uuid(),
  pack_ref text not null unique,
  email text not null,
  profile_id uuid references public.relocation_user_profiles(id) on delete set null,
  route_category text not null check (route_category in (
    'visitor', 'study', 'work', 'startup', 'business', 'family', 'digital_nomad',
    'scholarship', 'permanent_residence', 'other'
  )),
  target_country text,
  application_stage text not null default 'research' check (application_stage in (
    'research', 'preparation', 'appointment_booked', 'submitted', 'decision_received', 'archived'
  )),
  status text not null default 'draft' check (status in (
    'draft', 'review_required', 'ready', 'submitted', 'stale', 'archived'
  )),
  completeness_score integer not null default 0 check (completeness_score between 0 and 100),
  risk_level text not null default 'medium' check (risk_level in ('low', 'medium', 'high', 'critical')),
  required_items jsonb not null default '[]'::jsonb,
  available_items jsonb not null default '[]'::jsonb,
  missing_items jsonb not null default '[]'::jsonb,
  expiring_items jsonb not null default '[]'::jsonb,
  warnings jsonb not null default '[]'::jsonb,
  official_source_notes text,
  generated_from_inventory_at timestamptz not null default now(),
  source_page text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists relocation_evidence_packs_email_idx
on public.relocation_evidence_packs (email, status, created_at desc);

create index if not exists relocation_evidence_packs_risk_idx
on public.relocation_evidence_packs (risk_level, status, created_at desc);

create index if not exists relocation_evidence_packs_profile_idx
on public.relocation_evidence_packs (profile_id)
where profile_id is not null;

drop trigger if exists relocation_evidence_packs_set_updated_at
on public.relocation_evidence_packs;

create trigger relocation_evidence_packs_set_updated_at
before update on public.relocation_evidence_packs
for each row execute function public.relocation_set_updated_at();

-- These tables contain identity, document-status, expiry, route, and application
-- information. They are backend-only and have no browser-accessible RLS policy.
alter table public.relocation_user_document_inventory enable row level security;
alter table public.relocation_evidence_packs enable row level security;

revoke all privileges on table public.relocation_user_document_inventory from public, anon, authenticated;
revoke all privileges on table public.relocation_evidence_packs from public, anon, authenticated;

grant all privileges on table public.relocation_user_document_inventory to service_role;
grant all privileges on table public.relocation_evidence_packs to service_role;

comment on table public.relocation_user_document_inventory is 'Private document inventory metadata only. MoveReady does not store raw document files in this table.';
comment on table public.relocation_evidence_packs is 'Private generated evidence-pack readiness summaries linked to a verified account.';

notify pgrst, 'reload schema';
