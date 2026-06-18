-- Project MoveReady MVP
-- Corrected Finland D visa route enrichment.
-- Run after 001 through 011 migrations. Use this instead of rerunning 012 if 012 failed on document applies_to.
-- Sources reviewed: Finnish Immigration Service D visa and fast-track pages.

insert into public.relocation_countries (country_code, country_name, region, currency_code, official_language_codes, summary)
values ('FI', 'Finland', 'Europe', 'EUR', array['fi','sv'], 'Finland route record for D visa, fast-track residence permit, startup, work, study, research, and family readiness.')
on conflict (country_code) do update set
  country_name = excluded.country_name,
  region = excluded.region,
  currency_code = excluded.currency_code,
  official_language_codes = excluded.official_language_codes,
  summary = excluded.summary,
  updated_at = now();

with fi as (
  select id from public.relocation_countries where country_code = 'FI'
)
insert into public.relocation_trusted_sources (
  country_id,
  source_name,
  source_url,
  source_type,
  owner_organization,
  reliability_level,
  status,
  review_frequency_days,
  last_checked_at,
  next_review_due_at,
  notes
)
select id, 'Finnish Immigration Service - D visa', 'https://migri.fi/en/d-visa', 'government', 'Finnish Immigration Service', 'high', 'active', 14, now(), now() + interval '14 days',
  'Official Migri source for Finland D visa purpose, eligibility, application timing, validity, and passport handling.'
from fi
on conflict (source_url) do update set
  country_id = excluded.country_id,
  source_name = excluded.source_name,
  reliability_level = excluded.reliability_level,
  status = excluded.status,
  last_checked_at = excluded.last_checked_at,
  next_review_due_at = excluded.next_review_due_at,
  notes = excluded.notes,
  updated_at = now();

with fi as (
  select id from public.relocation_countries where country_code = 'FI'
)
insert into public.relocation_trusted_sources (
  country_id,
  source_name,
  source_url,
  source_type,
  owner_organization,
  reliability_level,
  status,
  review_frequency_days,
  last_checked_at,
  next_review_due_at,
  notes
)
select id, 'Finnish Immigration Service - Fast track', 'https://migri.fi/en/fast-track', 'government', 'Finnish Immigration Service', 'high', 'active', 14, now(), now() + interval '14 days',
  'Official Migri source for fast-track residence permit categories and related D visa workflow.'
from fi
on conflict (source_url) do update set
  country_id = excluded.country_id,
  source_name = excluded.source_name,
  reliability_level = excluded.reliability_level,
  status = excluded.status,
  last_checked_at = excluded.last_checked_at,
  next_review_due_at = excluded.next_review_due_at,
  notes = excluded.notes,
  updated_at = now();

insert into public.relocation_visa_routes (country_id, route_code, route_name, route_category, is_public)
select id, 'd-visa', 'Finland D visa pathway', 'work', true
from public.relocation_countries where country_code = 'FI'
on conflict (country_id, route_code) do update set
  route_name = excluded.route_name,
  route_category = excluded.route_category,
  is_public = excluded.is_public,
  updated_at = now();

with route as (
  select r.id
  from public.relocation_visa_routes r
  join public.relocation_countries c on c.id = r.country_id
  where c.country_code = 'FI' and r.route_code = 'd-visa'
)
update public.relocation_route_versions rv
set status = 'superseded', updated_at = now()
from route
where rv.route_id = route.id and rv.status = 'active' and rv.version_label <> 'finland-d-visa-2026-06';

with route as (
  select r.id
  from public.relocation_visa_routes r
  join public.relocation_countries c on c.id = r.country_id
  where c.country_code = 'FI' and r.route_code = 'd-visa'
)
insert into public.relocation_route_versions (
  route_id,
  version_label,
  status,
  risk_level,
  route_summary,
  eligibility_notes,
  proof_of_funds_notes,
  family_notes,
  processing_time_notes,
  validity_notes,
  official_fee_notes,
  refusal_risk_notes,
  source_confidence,
  verified_at,
  review_due_at,
  approved_at,
  approved_by,
  created_by
)
select id,
  'finland-d-visa-2026-06',
  'active',
  'medium',
  'Finland D visa route for eligible applicants who have been granted or hold a Finnish residence permit and need to travel to Finland before the residence permit card is received.',
  'The D visa is tied to an eligible Finnish residence permit route. It may be relevant for specialists, start-up entrepreneurs, EU Blue Card applicants, ICT specialists or managers, management roles, students, researchers, employed persons, and selected other work-based categories listed by Migri.',
  'Financial means depend on the underlying residence permit route. The D visa itself should be reviewed together with the main permit evidence, travel plan, family size, accommodation, and first-arrival budget.',
  'Family members may be able to apply for D visa handling with family-ties residence permit applications where Migri instructions allow. Check spouse and under-18 child handling for the exact main-applicant route.',
  'D visa does not shorten the residence permit processing time. It can support travel after a positive residence permit decision and D visa sticker handling. Fast-track may apply to selected permit categories.',
  'Migri describes the D visa as valid for up to 100 days. The residence permit card remains the main residence document after arrival.',
  'Official application and service fees must be checked on Migri and the relevant Finnish mission or VFS channel before payment.',
  'Main risk areas: treating D visa as a standalone visa, selecting a non-eligible residence permit route, incomplete passport handling, missing identity verification, weak underlying permit evidence, or booking travel before official confirmation.',
  'high',
  now(),
  now() + interval '14 days',
  now(),
  'system-seed-official-source-review',
  'system-seed-official-source-review'
from route
on conflict (route_id, version_label) do update set
  status = excluded.status,
  risk_level = excluded.risk_level,
  route_summary = excluded.route_summary,
  eligibility_notes = excluded.eligibility_notes,
  proof_of_funds_notes = excluded.proof_of_funds_notes,
  family_notes = excluded.family_notes,
  processing_time_notes = excluded.processing_time_notes,
  validity_notes = excluded.validity_notes,
  official_fee_notes = excluded.official_fee_notes,
  refusal_risk_notes = excluded.refusal_risk_notes,
  source_confidence = excluded.source_confidence,
  verified_at = excluded.verified_at,
  review_due_at = excluded.review_due_at,
  approved_at = excluded.approved_at,
  approved_by = excluded.approved_by,
  updated_at = now();

update public.relocation_visa_routes r
set active_version_id = rv.id,
    route_name = 'Finland D visa pathway',
    updated_at = now()
from public.relocation_route_versions rv,
     public.relocation_countries c
where rv.route_id = r.id
  and c.id = r.country_id
  and c.country_code = 'FI'
  and r.route_code = 'd-visa'
  and rv.version_label = 'finland-d-visa-2026-06';

with version as (
  select rv.id
  from public.relocation_route_versions rv
  join public.relocation_visa_routes r on r.id = rv.route_id
  join public.relocation_countries c on c.id = r.country_id
  where c.country_code = 'FI'
    and r.route_code = 'd-visa'
    and rv.version_label = 'finland-d-visa-2026-06'
), sources as (
  select id from public.relocation_trusted_sources
  where source_url in ('https://migri.fi/en/d-visa', 'https://migri.fi/en/fast-track')
)
insert into public.relocation_route_sources (route_version_id, source_id, usage_note)
select version.id, sources.id, 'Official Migri source used for Finland D visa readiness facts.'
from version, sources
on conflict (route_version_id, source_id) do update set usage_note = excluded.usage_note;

with version as (
  select rv.id
  from public.relocation_route_versions rv
  join public.relocation_visa_routes r on r.id = rv.route_id
  join public.relocation_countries c on c.id = r.country_id
  where c.country_code = 'FI'
    and r.route_code = 'd-visa'
    and rv.version_label = 'finland-d-visa-2026-06'
)
delete from public.relocation_route_facts where route_version_id in (select id from version);

with version as (
  select rv.id
  from public.relocation_route_versions rv
  join public.relocation_visa_routes r on r.id = rv.route_id
  join public.relocation_countries c on c.id = r.country_id
  where c.country_code = 'FI'
    and r.route_code = 'd-visa'
    and rv.version_label = 'finland-d-visa-2026-06'
)
insert into public.relocation_route_facts (route_version_id, fact_key, fact_label, fact_value, display_order)
select id, 'd_visa_purpose', 'D visa purpose', 'Travel to Finland after a positive residence permit decision before the residence permit card is received.', 10 from version
union all select id, 'not_standalone', 'Not standalone', 'The D visa is linked to an eligible Finnish residence permit route and does not replace the residence permit.', 20 from version
union all select id, 'validity', 'Validity', 'Migri describes the D visa as valid for up to 100 days.', 30 from version
union all select id, 'processing_time', 'Processing time', 'D visa does not shorten residence permit processing time; fast-track applies only to selected permit categories.', 40 from version
union all select id, 'passport_handling', 'Passport handling', 'Applicant may need to leave or present the passport for D visa sticker handling after a positive residence permit decision.', 50 from version
union all select id, 'family_members', 'Family members', 'Family members should check Migri family-ties D visa handling for the exact main-applicant route.', 60 from version;

with version as (
  select rv.id
  from public.relocation_route_versions rv
  join public.relocation_visa_routes r on r.id = rv.route_id
  join public.relocation_countries c on c.id = r.country_id
  where c.country_code = 'FI'
    and r.route_code = 'd-visa'
    and rv.version_label = 'finland-d-visa-2026-06'
)
delete from public.relocation_document_requirements where route_version_id in (select id from version);

with version as (
  select rv.id
  from public.relocation_route_versions rv
  join public.relocation_visa_routes r on r.id = rv.route_id
  join public.relocation_countries c on c.id = r.country_id
  where c.country_code = 'FI'
    and r.route_code = 'd-visa'
    and rv.version_label = 'finland-d-visa-2026-06'
)
insert into public.relocation_document_requirements (route_version_id, document_name, requirement_level, applies_to, details, display_order)
select id, 'Eligible residence permit application or decision', 'required', 'main_applicant', 'The D visa route depends on an eligible granted or held Finnish residence permit route.', 10 from version
union all select id, 'Valid passport', 'required', 'main_applicant', 'Passport must be available for identity verification and D visa sticker handling as instructed by the Finnish mission or VFS channel.', 20 from version
union all select id, 'Passport photo', 'required', 'main_applicant', 'Prepare a compliant passport photo for residence permit and D visa handling where required.', 30 from version
union all select id, 'Identity verification appointment evidence', 'required', 'main_applicant', 'Applicants should verify identity at the selected Finnish mission or VFS application centre as instructed.', 40 from version
union all select id, 'Finnish address for residence permit card', 'conditional', 'main_applicant', 'Migri may require a Finnish address for residence permit card delivery after arrival.', 50 from version
union all select id, 'Spouse family-ties documents', 'conditional', 'spouse', 'Spouse applications require route-specific family evidence and linking instructions.', 60 from version
union all select id, 'Child family-ties documents', 'conditional', 'child', 'Child applications require route-specific family evidence and linking instructions.', 70 from version;

with version as (
  select rv.id, r.country_id
  from public.relocation_route_versions rv
  join public.relocation_visa_routes r on r.id = rv.route_id
  join public.relocation_countries c on c.id = r.country_id
  where c.country_code = 'FI'
    and r.route_code = 'd-visa'
    and rv.version_label = 'finland-d-visa-2026-06'
)
delete from public.relocation_budget_items where route_version_id in (select id from version);

with version as (
  select rv.id, r.country_id
  from public.relocation_route_versions rv
  join public.relocation_visa_routes r on r.id = rv.route_id
  join public.relocation_countries c on c.id = r.country_id
  where c.country_code = 'FI'
    and r.route_code = 'd-visa'
    and rv.version_label = 'finland-d-visa-2026-06'
)
insert into public.relocation_budget_items (country_id, route_version_id, item_name, item_category, amount_min, amount_max, currency_code, is_required, notes)
select country_id, id, 'Residence permit and D visa application fees', 'visa_fee', 150, 900, 'EUR', true, 'Planning estimate only. Confirm exact fees on Migri and the selected service channel before payment.' from version
union all select country_id, id, 'Passport, photo, and appointment logistics', 'document', 20, 250, 'EUR', true, 'Depends on country of application and appointment channel.' from version
union all select country_id, id, 'Travel insurance or health coverage gap', 'insurance', 80, 600, 'EUR', false, 'Depends on the route, arrival timing, and coverage before Finnish health/social insurance applies.' from version
union all select country_id, id, 'Flight and first arrival buffer', 'flight', 400, 1500, 'EUR', true, 'Planning estimate for travel readiness after official confirmation.' from version
union all select country_id, id, 'Initial accommodation and settlement buffer', 'settlement', 1200, 4000, 'EUR', true, 'Planning estimate; proof-of-funds depends on the underlying residence permit route.' from version;

with version as (
  select rv.id, r.country_id
  from public.relocation_route_versions rv
  join public.relocation_visa_routes r on r.id = rv.route_id
  join public.relocation_countries c on c.id = r.country_id
  where c.country_code = 'FI'
    and r.route_code = 'd-visa'
    and rv.version_label = 'finland-d-visa-2026-06'
)
insert into public.relocation_admin_review_tasks (
  task_type,
  status,
  priority,
  route_version_id,
  title,
  description,
  assigned_to
)
select 'route_review', 'open', 'medium', version.id,
  'Next review: Finland D visa route',
  'Review Migri D visa and fast-track pages again before the review due date. Update eligible categories, passport handling, family rules, fees, and processing notes.',
  'admin'
from version
where not exists (
  select 1
  from public.relocation_admin_review_tasks existing
  where existing.route_version_id = version.id
    and existing.task_type = 'route_review'
    and existing.title = 'Next review: Finland D visa route'
);
