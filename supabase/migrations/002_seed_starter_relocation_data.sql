-- Project MoveReady MVP
-- Starter seed data for early local testing.
-- This creates broad route placeholders only. Detailed route facts must be reviewed before production use.

insert into public.relocation_countries (country_code, country_name, region, currency_code, official_language_codes, summary)
values
  ('PT', 'Portugal', 'Europe', 'EUR', array['pt'], 'Starter country record for Portugal relocation and residence route research.'),
  ('EE', 'Estonia', 'Europe', 'EUR', array['et'], 'Starter country record for Estonia startup, study, work, and digital business route research.'),
  ('FI', 'Finland', 'Europe', 'EUR', array['fi','sv'], 'Starter country record for Finland startup, study, work, and family route research.')
on conflict (country_code) do update set
  country_name = excluded.country_name,
  region = excluded.region,
  currency_code = excluded.currency_code,
  official_language_codes = excluded.official_language_codes,
  summary = excluded.summary,
  updated_at = now();

insert into public.relocation_trusted_sources (
  country_id,
  source_name,
  source_url,
  source_type,
  owner_organization,
  reliability_level,
  status,
  review_frequency_days,
  notes
)
select id, 'AIMA - Portugal immigration and asylum agency', 'https://aima.gov.pt/', 'government', 'AIMA', 'high', 'active', 14,
  'Official Portugal immigration source. Use specific route pages for detailed requirements.'
from public.relocation_countries where country_code = 'PT'
on conflict (source_url) do update set
  source_name = excluded.source_name,
  country_id = excluded.country_id,
  status = excluded.status,
  updated_at = now();

insert into public.relocation_trusted_sources (
  country_id,
  source_name,
  source_url,
  source_type,
  owner_organization,
  reliability_level,
  status,
  review_frequency_days,
  notes
)
select id, 'Startup Estonia - Startup Visa', 'https://startupestonia.ee/startup-visa/', 'government', 'Startup Estonia', 'high', 'active', 14,
  'Official Estonia startup visa source. Use route-specific subpages for detailed founder and hiring guidance.'
from public.relocation_countries where country_code = 'EE'
on conflict (source_url) do update set
  source_name = excluded.source_name,
  country_id = excluded.country_id,
  status = excluded.status,
  updated_at = now();

insert into public.relocation_trusted_sources (
  country_id,
  source_name,
  source_url,
  source_type,
  owner_organization,
  reliability_level,
  status,
  review_frequency_days,
  notes
)
select id, 'Finnish Immigration Service - Startup Entrepreneur', 'https://migri.fi/en/start-up-entrepreneur', 'government', 'Finnish Immigration Service', 'high', 'active', 14,
  'Official Finland startup entrepreneur residence permit source.'
from public.relocation_countries where country_code = 'FI'
on conflict (source_url) do update set
  source_name = excluded.source_name,
  country_id = excluded.country_id,
  status = excluded.status,
  updated_at = now();

insert into public.relocation_visa_routes (country_id, route_code, route_name, route_category, is_public)
select id, 'general-residence', 'General residence readiness', 'other', true
from public.relocation_countries where country_code = 'PT'
on conflict (country_id, route_code) do update set
  route_name = excluded.route_name,
  route_category = excluded.route_category,
  is_public = excluded.is_public,
  updated_at = now();

insert into public.relocation_visa_routes (country_id, route_code, route_name, route_category, is_public)
select id, 'startup-founder', 'Startup founder pathway', 'startup', true
from public.relocation_countries where country_code = 'EE'
on conflict (country_id, route_code) do update set
  route_name = excluded.route_name,
  route_category = excluded.route_category,
  is_public = excluded.is_public,
  updated_at = now();

insert into public.relocation_visa_routes (country_id, route_code, route_name, route_category, is_public)
select id, 'startup-entrepreneur', 'Startup entrepreneur residence permit', 'startup', true
from public.relocation_countries where country_code = 'FI'
on conflict (country_id, route_code) do update set
  route_name = excluded.route_name,
  route_category = excluded.route_category,
  is_public = excluded.is_public,
  updated_at = now();

insert into public.relocation_route_versions (
  route_id,
  version_label,
  status,
  risk_level,
  route_summary,
  eligibility_notes,
  proof_of_funds_notes,
  source_confidence,
  verified_at,
  review_due_at,
  approved_at,
  approved_by,
  created_by
)
select r.id, 'starter-2026-06', 'active', 'medium',
  'Starter route placeholder for early MVP testing. Replace with detailed reviewed facts before production use.',
  'Eligibility facts are pending route-specific official review.',
  'Proof-of-funds facts are pending route-specific official review.',
  'low', now(), now() + interval '14 days', now(), 'system-seed', 'system-seed'
from public.relocation_visa_routes r
where r.route_code in ('general-residence', 'startup-founder', 'startup-entrepreneur')
on conflict (route_id, version_label) do update set
  status = excluded.status,
  risk_level = excluded.risk_level,
  route_summary = excluded.route_summary,
  eligibility_notes = excluded.eligibility_notes,
  proof_of_funds_notes = excluded.proof_of_funds_notes,
  source_confidence = excluded.source_confidence,
  verified_at = excluded.verified_at,
  review_due_at = excluded.review_due_at,
  approved_at = excluded.approved_at,
  approved_by = excluded.approved_by,
  updated_at = now();

update public.relocation_visa_routes r
set active_version_id = rv.id,
    updated_at = now()
from public.relocation_route_versions rv
where rv.route_id = r.id
  and rv.version_label = 'starter-2026-06'
  and rv.status = 'active';

insert into public.relocation_route_sources (route_version_id, source_id, usage_note)
select rv.id, s.id, 'Starter source link for route research. Detailed facts still require admin review.'
from public.relocation_route_versions rv
join public.relocation_visa_routes r on r.id = rv.route_id
join public.relocation_countries c on c.id = r.country_id
join public.relocation_trusted_sources s on s.country_id = c.id
where rv.version_label = 'starter-2026-06'
on conflict (route_version_id, source_id) do update set
  usage_note = excluded.usage_note;

insert into public.relocation_admin_review_tasks (
  task_type,
  status,
  priority,
  route_version_id,
  title,
  description,
  assigned_to
)
select 'route_review', 'open', 'high', rv.id,
  'Review starter route: ' || r.route_name,
  'Replace starter placeholder with detailed route facts, document requirements, budget items, proof-of-funds notes, and source snapshots before production use.',
  'admin'
from public.relocation_route_versions rv
join public.relocation_visa_routes r on r.id = rv.route_id
where rv.version_label = 'starter-2026-06'
on conflict do nothing;
