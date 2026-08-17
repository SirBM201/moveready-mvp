-- MoveReady Stage 2F.5D.2A
-- Passport Index -> trusted official-source mapping.
--
-- This migration adds the mapping layer only. It does not seed country sources.
-- Provider/third-party links must never be promoted into this table as official
-- sources. Mappings point only to relocation_trusted_sources records whose
-- source_type is government or embassy.

create table if not exists public.relocation_passport_official_source_mappings (
  id uuid primary key default gen_random_uuid(),
  destination_country_id uuid not null references public.relocation_countries(id) on delete cascade,
  source_id uuid not null references public.relocation_trusted_sources(id) on delete restrict,
  purpose text not null default 'entry_requirements'
    check (purpose in ('entry_requirements','visa_requirements','passport_validity','health_entry','customs_entry','other')),
  priority integer not null default 100 check (priority between 1 and 10000),
  status text not null default 'active'
    check (status in ('active','watching','needs_review','retired')),
  verification_status text not null default 'pending_review'
    check (verification_status in ('pending_review','verified','needs_review','retired')),
  verified_at timestamptz,
  review_due_at timestamptz,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (destination_country_id, source_id, purpose)
);

create index if not exists relocation_passport_official_source_destination_idx
  on public.relocation_passport_official_source_mappings(destination_country_id, status, purpose, priority);

create index if not exists relocation_passport_official_source_source_idx
  on public.relocation_passport_official_source_mappings(source_id, status);

create or replace function public.relocation_validate_passport_official_source_mapping()
returns trigger
language plpgsql
as $$
declare
  trusted_source_type text;
  trusted_source_status text;
begin
  select source_type, status
    into trusted_source_type, trusted_source_status
  from public.relocation_trusted_sources
  where id = new.source_id;

  if trusted_source_type is null then
    raise exception 'Passport official-source mapping requires an existing trusted source';
  end if;

  if trusted_source_type not in ('government', 'embassy') then
    raise exception 'Passport official-source mapping requires government or embassy source_type, got %', trusted_source_type;
  end if;

  if trusted_source_status = 'retired' and new.status <> 'retired' then
    raise exception 'A retired trusted source cannot have an active passport official-source mapping';
  end if;

  if new.verification_status = 'verified' and new.verified_at is null then
    new.verified_at = now();
  end if;

  if new.verification_status <> 'verified' then
    new.verified_at = null;
  end if;

  return new;
end;
$$;

drop trigger if exists relocation_passport_official_source_mapping_validate
  on public.relocation_passport_official_source_mappings;

create trigger relocation_passport_official_source_mapping_validate
before insert or update of source_id, status, verification_status, verified_at
on public.relocation_passport_official_source_mappings
for each row
execute function public.relocation_validate_passport_official_source_mapping();

drop trigger if exists relocation_passport_official_source_mapping_updated_at
  on public.relocation_passport_official_source_mappings;

create trigger relocation_passport_official_source_mapping_updated_at
before update on public.relocation_passport_official_source_mappings
for each row
execute function public.relocation_set_updated_at();

alter table public.relocation_passport_official_source_mappings enable row level security;

-- Backend-only table. The service-role backend resolves mappings and returns a
-- deliberately limited public verification object through the Passport Index API.
revoke all on table public.relocation_passport_official_source_mappings from anon, authenticated;

comment on table public.relocation_passport_official_source_mappings is
  'Maps Passport Index destinations to reviewed government/embassy records in relocation_trusted_sources. Provider links are not official-source mappings.';

comment on column public.relocation_passport_official_source_mappings.verification_status is
  'Fail-closed review state. Only verified mappings may be presented as officially verified by MoveReady.';
