-- MoveReady Stage 2F.5D.2B
-- Seed authoritative destination-entry sources and map them to Passport Index destinations.
--
-- IMPORTANT:
-- * Only government / embassy authorities belong in this layer.
-- * RapidAPI and other third-party provider URLs remain provider evidence, never official sources.
-- * Seeded mappings start pending_review (fail closed). A later review step may mark them verified.
-- * This migration is intentionally idempotent.

-- ---------------------------------------------------------------------------
-- 1. Seed reviewed government authority records
-- ---------------------------------------------------------------------------

insert into public.relocation_trusted_sources
  (source_name, owner_organization, source_type, reliability_level, status, source_url, notes)
values
  (
    'Government of Canada - Visit Canada',
    'Immigration, Refugees and Citizenship Canada (IRCC)',
    'government',
    'high',
    'active',
    'https://www.canada.ca/en/immigration-refugees-citizenship/services/visit-canada.html',
    'Official Government of Canada entry/visitor information. Stage 2F.5D.2B seed; web-reviewed 2026-08-16.'
  ),
  (
    'German Federal Foreign Office - Visa requirements for entry',
    'Federal Foreign Office (Auswärtiges Amt)',
    'government',
    'high',
    'active',
    'https://www.auswaertiges-amt.de/en/visa-service/231148-231148',
    'Official German Federal Foreign Office country list for visa requirements/exemptions. Stage 2F.5D.2B seed; web-reviewed 2026-08-16.'
  ),
  (
    'Benin Government - Official e-Visa portal',
    'Government of the Republic of Benin / Direction de l''Emigration et de l''Immigration',
    'government',
    'high',
    'active',
    'https://evisa.bj/?_locale=en',
    'Official Republic of Benin e-Visa portal. Stage 2F.5D.2B seed; web-reviewed 2026-08-16.'
  ),
  (
    'Seychelles Electronic Border System',
    'Government of Seychelles',
    'government',
    'high',
    'active',
    'https://seychelles.govtas.com/',
    'Official Government of Seychelles Travel Authorisation and immigration platform, linked from gov.sc. Stage 2F.5D.2B seed; web-reviewed 2026-08-16.'
  )
on conflict do nothing;

-- If a source with the same canonical URL already existed under another name,
-- keep that record rather than creating a second authority record.

-- ---------------------------------------------------------------------------
-- 2. Map destination countries to the authoritative sources
-- ---------------------------------------------------------------------------

with seed(destination_name, source_url, purpose, priority, notes) as (
  values
    ('Canada',
     'https://www.canada.ca/en/immigration-refugees-citizenship/services/visit-canada.html',
     'entry_requirements', 10,
     'Primary official source for Canada visitor entry and visa/eTA routing.'),
    ('Germany',
     'https://www.auswaertiges-amt.de/en/visa-service/231148-231148',
     'visa_requirements', 10,
     'Primary official source for German entry visa requirement/exemption status.'),
    ('Benin',
     'https://evisa.bj/?_locale=en',
     'visa_requirements', 10,
     'Primary official Benin e-Visa authority source.'),
    ('Seychelles',
     'https://seychelles.govtas.com/',
     'entry_requirements', 10,
     'Primary official Seychelles Travel Authorisation / border-system source.')
), resolved as (
  select
    c.id as destination_country_id,
    s.id as source_id,
    seed.purpose,
    seed.priority,
    seed.notes
  from seed
  join public.relocation_countries c
    on lower(trim(c.country_name)) = lower(seed.destination_name)
  join public.relocation_trusted_sources s
    on s.source_url = seed.source_url
   and s.source_type in ('government', 'embassy')
   and s.status <> 'retired'
)
insert into public.relocation_passport_official_source_mappings
  (destination_country_id, source_id, purpose, priority, status,
   verification_status, review_due_at, notes)
select
  destination_country_id,
  source_id,
  purpose,
  priority,
  'active',
  'pending_review',
  now() + interval '30 days',
  notes
from resolved
on conflict (destination_country_id, source_id, purpose)
do update set
  priority = excluded.priority,
  status = 'active',
  review_due_at = excluded.review_due_at,
  notes = excluded.notes,
  updated_at = now();

-- ---------------------------------------------------------------------------
-- 3. Safety assertions
-- ---------------------------------------------------------------------------

do $$
declare
  expected integer := 4;
  mapped integer;
  invalid integer;
begin
  select count(*) into mapped
  from public.relocation_passport_official_source_mappings m
  join public.relocation_countries c on c.id = m.destination_country_id
  where lower(c.country_name) in ('benin','canada','germany','seychelles')
    and m.status = 'active';

  if mapped < expected then
    raise exception 'Stage 2F.5D.2B expected at least % active destination mappings, found %. Check relocation_countries country_name values and trusted-source seed compatibility.', expected, mapped;
  end if;

  select count(*) into invalid
  from public.relocation_passport_official_source_mappings m
  join public.relocation_trusted_sources s on s.id = m.source_id
  where m.status = 'active'
    and s.source_type not in ('government','embassy');

  if invalid > 0 then
    raise exception 'Stage 2F.5D.2B safety failure: % active official-source mappings point to non-government/non-embassy sources.', invalid;
  end if;
end;
$$;

comment on table public.relocation_passport_official_source_mappings is
  'Maps Passport Index destinations to reviewed government/embassy records in relocation_trusted_sources. Provider links are never official-source mappings. Stage 2F.5D.2B seeds Canada, Germany, Benin and Seychelles authorities pending explicit verification.';
