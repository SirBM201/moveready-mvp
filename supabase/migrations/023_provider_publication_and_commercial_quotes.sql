-- Project MoveReady MVP
-- Provider publication controls, commercial quotes, and payment-event audit.
-- Run after migrations 001 through 022.
-- Safe to rerun.

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

-- Expand partner categories for the travel-commerce layer.
alter table public.relocation_partner_applications
  drop constraint if exists relocation_partner_applications_provider_type_check;

alter table public.relocation_partner_applications
  add constraint relocation_partner_applications_provider_type_check
  check (provider_type in (
    'courier',
    'insurance',
    'legalization',
    'translation',
    'expert_review',
    'admission_support',
    'accommodation',
    'airport_pickup',
    'settlement',
    'travel_booking',
    'transport',
    'telecom',
    'other'
  ));

alter table public.relocation_partner_applications
  add column if not exists public_listing_enabled boolean not null default false,
  add column if not exists approved_at timestamptz,
  add column if not exists approved_by text,
  add column if not exists privacy_reviewed boolean not null default false,
  add column if not exists pricing_reviewed boolean not null default false,
  add column if not exists refund_policy_reviewed boolean not null default false,
  add column if not exists sensitive_document_handling_reviewed boolean not null default false,
  add column if not exists affiliate_relationship boolean not null default false,
  add column if not exists affiliate_disclosure text,
  add column if not exists handoff_terms text,
  add column if not exists public_notes text;

create index if not exists relocation_partner_public_listing_idx
on public.relocation_partner_applications (public_listing_enabled, status, provider_type);

-- A quote is an admin-issued commercial offer. It is not a visa, admission,
-- booking, provider-performance, refund, or approval guarantee.
create table if not exists public.relocation_commercial_quotes (
  id uuid primary key default gen_random_uuid(),
  quote_ref text not null unique,
  service_request_id uuid,
  provider_application_id uuid,
  full_name text,
  email text not null,
  phone text,
  service_slug text not null,
  service_title text not null,
  provider_name text,
  currency text not null default 'USD',
  subtotal_amount numeric(14,2) not null default 0 check (subtotal_amount >= 0),
  platform_fee_amount numeric(14,2) not null default 0 check (platform_fee_amount >= 0),
  total_amount numeric(14,2) not null default 0 check (total_amount >= 0),
  scope_summary text not null,
  deliverables jsonb not null default '[]'::jsonb,
  exclusions jsonb not null default '[]'::jsonb,
  refund_terms text not null,
  status text not null default 'draft' check (status in (
    'draft',
    'sent',
    'accepted',
    'declined',
    'expired',
    'cancelled',
    'payment_pending',
    'paid',
    'fulfilled',
    'refunded',
    'disputed'
  )),
  payment_provider text,
  payment_reference text,
  checkout_url text,
  expires_at timestamptz,
  sent_at timestamptz,
  accepted_at timestamptz,
  paid_at timestamptz,
  fulfilled_at timestamptz,
  created_by text,
  source_page text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.relocation_commercial_quotes
  add column if not exists quote_ref text,
  add column if not exists service_request_id uuid,
  add column if not exists provider_application_id uuid,
  add column if not exists full_name text,
  add column if not exists email text,
  add column if not exists phone text,
  add column if not exists service_slug text,
  add column if not exists service_title text,
  add column if not exists provider_name text,
  add column if not exists currency text not null default 'USD',
  add column if not exists subtotal_amount numeric(14,2) not null default 0,
  add column if not exists platform_fee_amount numeric(14,2) not null default 0,
  add column if not exists total_amount numeric(14,2) not null default 0,
  add column if not exists scope_summary text,
  add column if not exists deliverables jsonb not null default '[]'::jsonb,
  add column if not exists exclusions jsonb not null default '[]'::jsonb,
  add column if not exists refund_terms text,
  add column if not exists status text not null default 'draft',
  add column if not exists payment_provider text,
  add column if not exists payment_reference text,
  add column if not exists checkout_url text,
  add column if not exists expires_at timestamptz,
  add column if not exists sent_at timestamptz,
  add column if not exists accepted_at timestamptz,
  add column if not exists paid_at timestamptz,
  add column if not exists fulfilled_at timestamptz,
  add column if not exists created_by text,
  add column if not exists source_page text,
  add column if not exists metadata jsonb not null default '{}'::jsonb,
  add column if not exists created_at timestamptz not null default now(),
  add column if not exists updated_at timestamptz not null default now();

create unique index if not exists relocation_commercial_quotes_ref_idx
on public.relocation_commercial_quotes (quote_ref);

create index if not exists relocation_commercial_quotes_email_idx
on public.relocation_commercial_quotes (email, created_at desc);

create index if not exists relocation_commercial_quotes_status_idx
on public.relocation_commercial_quotes (status, created_at desc);

create index if not exists relocation_commercial_quotes_service_request_idx
on public.relocation_commercial_quotes (service_request_id);

drop trigger if exists relocation_commercial_quotes_set_updated_at
on public.relocation_commercial_quotes;

create trigger relocation_commercial_quotes_set_updated_at
before update on public.relocation_commercial_quotes
for each row execute function public.relocation_set_updated_at();

create table if not exists public.relocation_payment_events (
  id uuid primary key default gen_random_uuid(),
  quote_id uuid not null references public.relocation_commercial_quotes(id) on delete cascade,
  event_type text not null,
  event_status text not null default 'recorded',
  amount numeric(14,2),
  currency text,
  payment_provider text,
  payment_reference text,
  actor_type text not null default 'system',
  actor_reference text,
  event_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists relocation_payment_events_quote_idx
on public.relocation_payment_events (quote_id, created_at desc);

create index if not exists relocation_payment_events_reference_idx
on public.relocation_payment_events (payment_reference);

notify pgrst, 'reload schema';