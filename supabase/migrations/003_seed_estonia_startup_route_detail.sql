-- Project MoveReady MVP
-- Estonia startup founder route enrichment.
-- Run after 001_initial_relocation_schema.sql and 002_seed_starter_relocation_data.sql.
-- Sources reviewed: Startup Estonia foreign founder/startup visa pages and Estonia MFA D visa page.

with ee as (
  select id from public.relocation_countries where country_code = 'EE'
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
select id, 'Startup Estonia - Foreign founder', 'https://startupestonia.ee/startup-visa/foreign-founder/', 'government', 'Startup Estonia', 'high', 'active', 14, now(), now() + interval '14 days',
  'Official Estonia startup visa source for non-EU founders and Startup Committee application process.'
from ee
on conflict (source_url) do update set
  country_id = excluded.country_id,
  source_name = excluded.source_name,
  reliability_level = excluded.reliability_level,
  status = excluded.status,
  last_checked_at = excluded.last_checked_at,
  next_review_due_at = excluded.next_review_due_at,
  notes = excluded.notes,
  updated_at = now();

with ee as (
  select id from public.relocation_countries where country_code = 'EE'
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
select id, 'Estonian Ministry of Foreign Affairs - Long-stay D visa', 'https://www.vm.ee/en/consular-visa-and-travel-information/visa-information/application-long-stay-d-visa', 'government', 'Estonian Ministry of Foreign Affairs', 'high', 'active', 14, now(), now() + interval '14 days',
  'Official Estonia source for long-stay D visa duration, application channel, insurance, financial means, and document requirements.'
from ee
on conflict (source_url) do update set
  country_id = excluded.country_id,
  source_name = excluded.source_name,
  reliability_level = excluded.reliability_level,
  status = excluded.status,
  last_checked_at = excluded.last_checked_at,
  next_review_due_at = excluded.next_review_due_at,
  notes = excluded.notes,
  updated_at = now();

with route as (
  select r.id
  from public.relocation_visa_routes r
  join public.relocation_countries c on c.id = r.country_id
  where c.country_code = 'EE' and r.route_code = 'startup-founder'
)
update public.relocation_route_versions rv
set status = 'superseded', updated_at = now()
from route
where rv.route_id = route.id and rv.status = 'active' and rv.version_label <> 'estonia-startup-founder-2026-06';

with route as (
  select r.id
  from public.relocation_visa_routes r
  join public.relocation_countries c on c.id = r.country_id
  where c.country_code = 'EE' and r.route_code = 'startup-founder'
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
  'estonia-startup-founder-2026-06',
  'active',
  'medium',
  'For non-EU founders building a technology-based, innovative, scalable startup with MVP/traction. Startup Committee approval and a unique application code are central before applying for visa and/or temporary residence permit steps.',
  'Startup Estonia describes the founder route around a technology-based, innovative, scalable business and Startup Committee approval. The committee reviews the startup-code application and, if successful, issues a verification letter with a unique application code.',
  'The Estonia D visa source requires proof of financial means according to the purpose of stay, including evidence of income for the three months immediately before application showing amount, regularity, and sources of income. Route-specific funds should be checked before final application.',
  'Family handling should be checked from the latest official Startup Estonia FAQ and the specific visa/residence-permit channel before application.',
  'Startup Estonia states the Startup Committee decision target as 10 working days. Visa/residence permit processing depends on the chosen channel and representation.',
  'The Estonia long-stay D visa may allow temporary stay up to 365 days within 12 consecutive months. Startup founders may also need to consider temporary residence permit options depending on company registration and relocation plan.',
  'Official fees and appointment channel must be checked at the exact time of application through the Estonian representation or Police and Border Guard Board instructions.',
  'Main risk areas: weak startup evidence, no MVP/traction, unclear scalability, incomplete Startup Committee application, insufficient funds evidence, weak insurance coverage, or missing legalization/translation of foreign public documents.',
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
    route_name = 'Estonia startup founder pathway',
    updated_at = now()
from public.relocation_route_versions rv
join public.relocation_countries c on c.id = r.country_id
where rv.route_id = r.id
  and c.country_code = 'EE'
  and r.route_code = 'startup-founder'
  and rv.version_label = 'estonia-startup-founder-2026-06';

with version as (
  select rv.id
  from public.relocation_route_versions rv
  join public.relocation_visa_routes r on r.id = rv.route_id
  join public.relocation_countries c on c.id = r.country_id
  where c.country_code = 'EE'
    and r.route_code = 'startup-founder'
    and rv.version_label = 'estonia-startup-founder-2026-06'
), sources as (
  select id from public.relocation_trusted_sources
  where source_url in (
    'https://startupestonia.ee/startup-visa/',
    'https://startupestonia.ee/startup-visa/foreign-founder/',
    'https://www.vm.ee/en/consular-visa-and-travel-information/visa-information/application-long-stay-d-visa'
  )
)
insert into public.relocation_route_sources (route_version_id, source_id, usage_note)
select version.id, sources.id, 'Official source used for Estonia startup founder pathway readiness facts.'
from version, sources
on conflict (route_version_id, source_id) do update set usage_note = excluded.usage_note;

with version as (
  select rv.id
  from public.relocation_route_versions rv
  join public.relocation_visa_routes r on r.id = rv.route_id
  join public.relocation_countries c on c.id = r.country_id
  where c.country_code = 'EE'
    and r.route_code = 'startup-founder'
    and rv.version_label = 'estonia-startup-founder-2026-06'
)
delete from public.relocation_route_facts where route_version_id in (select id from version);

with version as (
  select rv.id
  from public.relocation_route_versions rv
  join public.relocation_visa_routes r on r.id = rv.route_id
  join public.relocation_countries c on c.id = r.country_id
  where c.country_code = 'EE'
    and r.route_code = 'startup-founder'
    and rv.version_label = 'estonia-startup-founder-2026-06'
)
insert into public.relocation_route_facts (route_version_id, fact_key, fact_label, fact_value, display_order)
select id, 'startup_definition', 'Startup definition', 'Technology-based, innovative, scalable business with MVP/traction and global growth potential.', 10 from version
union all select id, 'committee_approval', 'Startup Committee approval', 'Founder should complete the startup-code application and obtain Startup Committee verification/application code before visa/residence next steps.', 20 from version
union all select id, 'committee_timeline', 'Committee timeline', 'Startup Estonia states the Startup Committee reviews the application and makes a decision within 10 working days.', 30 from version
union all select id, 'd_visa_duration', 'D visa duration', 'Estonia long-stay D visa may be issued for temporary stay up to 365 days within 12 consecutive months.', 40 from version
union all select id, 'financial_means', 'Financial means', 'D visa application requires proof of financial means according to purpose of stay, including recent income evidence.', 50 from version
union all select id, 'public_documents', 'Foreign public documents', 'Foreign public documents for D visa should be legalized/apostilled and translated into Estonian or English where required.', 60 from version;

with version as (
  select rv.id
  from public.relocation_route_versions rv
  join public.relocation_visa_routes r on r.id = rv.route_id
  join public.relocation_countries c on c.id = r.country_id
  where c.country_code = 'EE'
    and r.route_code = 'startup-founder'
    and rv.version_label = 'estonia-startup-founder-2026-06'
)
delete from public.relocation_document_requirements where route_version_id in (select id from version);

with version as (
  select rv.id
  from public.relocation_route_versions rv
  join public.relocation_visa_routes r on r.id = rv.route_id
  join public.relocation_countries c on c.id = r.country_id
  where c.country_code = 'EE'
    and r.route_code = 'startup-founder'
    and rv.version_label = 'estonia-startup-founder-2026-06'
)
insert into public.relocation_document_requirements (route_version_id, document_name, requirement_level, applies_to, details, display_order)
select id, 'Startup Committee verification letter / startup code', 'required', 'main_applicant', 'Evidence that the startup has been approved/verified through the Startup Committee process.', 10 from version
union all select id, 'Valid travel document / passport', 'required', 'main_applicant', 'For D visa, travel document should meet validity and blank-page requirements stated by Estonia MFA.', 20 from version
union all select id, 'Completed and signed visa application form', 'conditional', 'main_applicant', 'Required if applying through the long-stay D visa channel.', 30 from version
union all select id, 'Recent color photo', 'conditional', 'main_applicant', 'Required for D visa application; photo requirements should be checked at time of application.', 40 from version
union all select id, 'Travel medical insurance', 'conditional', 'main_applicant', 'D visa source requires travel medical insurance for costs related to treatment due to illness or injury during visa validity unless covered by applicable Estonian insurance timing.', 50 from version
union all select id, 'Proof of financial means', 'required', 'main_applicant', 'Prepare income/funds evidence matching the purpose of stay, including recent income evidence where required.', 60 from version
union all select id, 'Startup evidence pack', 'required', 'main_applicant', 'Pitch deck, MVP/demo, traction, product screenshots, team roles, roadmap, market evidence, and business model.', 70 from version
union all select id, 'Data concerning close relatives and family members', 'conditional', 'main_applicant', 'Listed among D visa application information requirements; family-route details should be reviewed separately.', 80 from version
union all select id, 'Legalized/apostilled and translated public documents', 'conditional', 'main_applicant', 'Foreign public documents submitted for D visa should be legalized/apostilled and translated into Estonian or English where required.', 90 from version;

with version as (
  select rv.id, r.country_id
  from public.relocation_route_versions rv
  join public.relocation_visa_routes r on r.id = rv.route_id
  join public.relocation_countries c on c.id = r.country_id
  where c.country_code = 'EE'
    and r.route_code = 'startup-founder'
    and rv.version_label = 'estonia-startup-founder-2026-06'
)
delete from public.relocation_budget_items where route_version_id in (select id from version);

with version as (
  select rv.id, r.country_id
  from public.relocation_route_versions rv
  join public.relocation_visa_routes r on r.id = rv.route_id
  join public.relocation_countries c on c.id = r.country_id
  where c.country_code = 'EE'
    and r.route_code = 'startup-founder'
    and rv.version_label = 'estonia-startup-founder-2026-06'
)
insert into public.relocation_budget_items (country_id, route_version_id, item_name, item_category, amount_min, amount_max, currency_code, is_required, notes)
select country_id, id, 'Startup application preparation', 'document', 0, 500, 'EUR', true, 'Includes pitch deck/MVP evidence preparation; platform estimate, not an official government fee.' from version
union all select country_id, id, 'Long-stay D visa / residence permit application costs', 'visa_fee', 100, 800, 'EUR', true, 'Placeholder range. Check official state fee at the exact application channel before submission.' from version
union all select country_id, id, 'Travel medical insurance', 'insurance', 80, 500, 'EUR', true, 'Estimate only. Coverage period and minimum requirements depend on visa/residence channel.' from version
union all select country_id, id, 'Document legalization / apostille / translation', 'document', 50, 600, 'EUR', false, 'Depends on country of document issue and whether public documents are submitted.' from version
union all select country_id, id, 'Initial arrival and accommodation buffer', 'settlement', 1200, 3500, 'EUR', true, 'Platform planning estimate for first-arrival readiness, not an official proof-of-funds figure.' from version;

with version as (
  select rv.id, r.country_id
  from public.relocation_route_versions rv
  join public.relocation_visa_routes r on r.id = rv.route_id
  join public.relocation_countries c on c.id = r.country_id
  where c.country_code = 'EE'
    and r.route_code = 'startup-founder'
    and rv.version_label = 'estonia-startup-founder-2026-06'
)
delete from public.relocation_insurance_requirements where route_version_id in (select id from version);

with version as (
  select rv.id, r.country_id
  from public.relocation_route_versions rv
  join public.relocation_visa_routes r on r.id = rv.route_id
  join public.relocation_countries c on c.id = r.country_id
  where c.country_code = 'EE'
    and r.route_code = 'startup-founder'
    and rv.version_label = 'estonia-startup-founder-2026-06'
)
insert into public.relocation_insurance_requirements (country_id, route_version_id, insurance_type, is_required, minimum_coverage_amount, currency_code, details)
select country_id, id, 'travel', true, null, 'EUR', 'D visa source requires travel medical insurance covering treatment costs due to illness or injury during visa validity, unless Estonian health insurance timing applies.' from version;

with version as (
  select rv.id
  from public.relocation_route_versions rv
  join public.relocation_visa_routes r on r.id = rv.route_id
  join public.relocation_countries c on c.id = r.country_id
  where c.country_code = 'EE'
    and r.route_code = 'startup-founder'
    and rv.version_label = 'estonia-startup-founder-2026-06'
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
select 'route_review', 'open', 'medium', id,
  'Next review: Estonia startup founder route',
  'Review Startup Estonia and Estonia MFA D visa sources again before the review due date. Update fees, proof-of-funds details, family rules, and application-channel instructions.',
  'admin'
from version;
