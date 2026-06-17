-- Project MoveReady MVP
-- Service interest and launch-request capture.
-- Run after 001, 002, and 003 migrations.

create table if not exists public.relocation_service_interest_requests (
  id uuid primary key default gen_random_uuid(),
  service_slug text not null,
  service_title text,
  full_name text,
  email text,
  phone text,
  preferred_channel text not null default 'email' check (preferred_channel in ('email','whatsapp','telegram','phone','in_app')),
  current_country text,
  target_country text,
  route_or_goal text,
  message text,
  consent_to_contact boolean not null default false,
  source_page text,
  status text not null default 'new' check (status in ('new','reviewing','contacted','closed','spam')),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists relocation_service_interest_requests_service_idx
  on public.relocation_service_interest_requests (service_slug, status, created_at desc);

create index if not exists relocation_service_interest_requests_contact_idx
  on public.relocation_service_interest_requests (email, phone);

drop trigger if exists relocation_service_interest_requests_updated_at on public.relocation_service_interest_requests;
create trigger relocation_service_interest_requests_updated_at
before update on public.relocation_service_interest_requests
for each row execute function public.relocation_set_updated_at();
