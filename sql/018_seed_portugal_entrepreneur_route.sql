-- Project MoveReady MVP
-- Portugal entrepreneur and independent work route enrichment.
-- Run after 001 through 017 migrations.
-- Safe to rerun.

create extension if not exists pgcrypto;

insert into public.relocation_countries (country_code, country_name, region, currency_code, official_language_codes, summary)
values (
  'PT',
  'Portugal',
  'Europe',
  'EUR',
  array['pt'],
  'Portugal route record for entrepreneur, independent work, startup, study, family, and residence readiness.'
)
on conflict (country_code) do update set
  country_name = excluded.country_name,
  region = excluded.region,
  currency_code = excluded.currency_code,
  official_language_codes = excluded.official_language_codes,
  summary = excluded.summary,
  is_active = true,
  updated_at = now();

do $$
declare
  v_country_id uuid;
  v_route_id uuid;
  v_version_id uuid;
begin
  select id into v_country_id
  from public.relocation_countries
  where country_code = 'PT'
  limit 1;

  select id into v_route_id
  from public.relocation_visa_routes
  where country_id = v_country_id
    and route_code = 'entrepreneur-independent-work'
  limit 1;

  if v_route_id is null then
    insert into public.relocation_visa_routes (
      country_id,
      route_code,
      route_name,
      route_category,
      is_public
    ) values (
      v_country_id,
      'entrepreneur-independent-work',
      'Portugal entrepreneur and independent work pathway',
      'business',
      true
    )
    returning id into v_route_id;
  else
    update public.relocation_visa_routes
    set route_name = 'Portugal entrepreneur and independent work pathway',
        route_category = 'business',
        is_public = true,
        updated_at = now()
    where id = v_route_id;
  end if;

  select id into v_version_id
  from public.relocation_route_versions
  where route_id = v_route_id
    and version_label = '2026-06-19-official-starter'
  limit 1;

  if v_version_id is null then
    insert into public.relocation_route_versions (
      route_id,
      version_label,
      status,
      risk_level,
      source_confidence,
      route_summary,
      verified_at,
      review_due_at
    ) values (
      v_route_id,
      '2026-06-19-official-starter',
      'active',
      'medium',
      'high',
      'For entrepreneurs, independent professionals, and startup applicants preparing Portugal residency visa evidence, funds, insurance, document legalization, and post-arrival residence permit steps.',
      now(),
      now() + interval '14 days'
    )
    returning id into v_version_id;
  else
    update public.relocation_route_versions
    set status = 'active',
        risk_level = 'medium',
        source_confidence = 'high',
        route_summary = 'For entrepreneurs, independent professionals, and startup applicants preparing Portugal residency visa evidence, funds, insurance, document legalization, and post-arrival residence permit steps.',
        verified_at = now(),
        review_due_at = now() + interval '14 days',
        updated_at = now()
    where id = v_version_id;
  end if;

  update public.relocation_visa_routes
  set active_version_id = v_version_id,
      updated_at = now()
  where id = v_route_id;

  delete from public.relocation_route_facts where route_version_id = v_version_id;
  insert into public.relocation_route_facts (route_version_id, fact_key, fact_label, fact_value, fact_payload, display_order)
  values
    (v_version_id, 'residency_visa_category', 'Residency visa category', 'Portugal national visa guidance lists residency visa documentation for independent work purposes or entrepreneurs.', '{}'::jsonb, 10),
    (v_version_id, 'independent_work_evidence', 'Independent work evidence', 'Applicants should prepare a service contract, written service proposal, or professional activity evidence where relevant.', '{}'::jsonb, 20),
    (v_version_id, 'entrepreneur_evidence', 'Entrepreneur evidence', 'Founder applicants should prepare investment activity evidence, available financial means in Portugal, and clear intention to invest in Portuguese territory.', '{}'::jsonb, 30),
    (v_version_id, 'startup_visa_distinction', 'Startup Visa distinction', 'Startup Visa applicants should separately verify whether IAPMEI and certified incubator evidence applies to their specific route.', '{}'::jsonb, 40),
    (v_version_id, 'residence_permit_step', 'Residence permit step', 'The residency visa is used before applying for the residence permit stage after arrival, according to current AIMA and consular instructions.', '{}'::jsonb, 50),
    (v_version_id, 'document_legalization', 'Document legalization', 'Foreign public documents may need apostille or legalization depending on issuing country and document type.', '{}'::jsonb, 60);

  delete from public.relocation_document_requirements where route_version_id = v_version_id;
  insert into public.relocation_document_requirements (route_version_id, document_name, requirement_level, applies_to, details, display_order)
  values
    (v_version_id, 'Passport', 'required', 'main_applicant', 'Confirm validity, blank-page rules, consular post instructions, and whether passport submission is required.', 10),
    (v_version_id, 'National visa application form', 'required', 'main_applicant', 'Complete the current Portugal national visa form or e-Visa flow used by the responsible consular post.', 20),
    (v_version_id, 'Entrepreneur or independent work evidence', 'required', 'main_applicant', 'Prepare service contract, written service proposal, investment evidence, company documents, or Startup Visa evidence depending on selected route.', 30),
    (v_version_id, 'Proof of financial means', 'required', 'main_applicant', 'Prepare bank statements, funds source explanation, sponsor evidence, or Portuguese financial means evidence as required.', 40),
    (v_version_id, 'Criminal record certificate', 'required', 'main_applicant', 'Check apostille, legalization, translation, and recency rules for the country where the record was issued.', 50),
    (v_version_id, 'Accommodation or address evidence', 'conditional', 'main_applicant', 'Prepare lease, invitation, booking, or address evidence according to the consular post instructions.', 60),
    (v_version_id, 'Travel or health insurance', 'conditional', 'main_applicant', 'Check insurance coverage, dates, territory, and refundability before purchase.', 70),
    (v_version_id, 'Family evidence', 'conditional', 'family_member', 'Spouse or child planning requires route-specific civil documents, translations, legalization, and extra funds review.', 80);

  delete from public.relocation_budget_items where route_version_id = v_version_id;
  insert into public.relocation_budget_items (route_version_id, country_id, item_name, item_category, amount_min, amount_max, currency_code, is_required, notes)
  values
    (v_version_id, v_country_id, 'National visa and consular fees', 'visa_fee', 90, 250, 'EUR', true, 'Starter estimate only. Verify current consular and service-provider fees.'),
    (v_version_id, v_country_id, 'Document preparation, translation, and legalization', 'document', 150, 900, 'EUR', true, 'Cost varies by document origin, translation needs, apostille/legalization, and courier handling.'),
    (v_version_id, v_country_id, 'Insurance', 'insurance', 80, 600, 'EUR', true, 'Verify travel or health insurance requirements for the application and arrival window.'),
    (v_version_id, v_country_id, 'Flight and first arrival costs', 'flight', 400, 1400, 'EUR', false, 'Do not book non-refundable travel before visa issue unless appropriate for the route.'),
    (v_version_id, v_country_id, 'Initial accommodation and settlement', 'accommodation', 800, 3000, 'EUR', true, 'Prepare first-arrival accommodation and funds buffer before appointment or travel planning.');

  delete from public.relocation_insurance_requirements where route_version_id = v_version_id;
  insert into public.relocation_insurance_requirements (route_version_id, country_id, insurance_type, is_required, minimum_coverage_amount, currency_code, details)
  values
    (v_version_id, v_country_id, 'Travel or health', true, null, 'EUR', 'Insurance requirements depend on visa type, consular post, travel date, and residence permit step. Verify before purchase.');
end $$;
