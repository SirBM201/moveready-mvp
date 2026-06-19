-- Project MoveReady MVP
-- Official ballot, lottery, invitation-pool, and quota opportunities.
-- Run after 001 through 015 migrations.
-- Safe to rerun.

create extension if not exists pgcrypto;

create table if not exists public.relocation_opportunities (
  id uuid primary key default gen_random_uuid(),
  opportunity_code text not null,
  country_code text not null,
  country_name text not null,
  opportunity_name text not null,
  opportunity_type text not null,
  route_category text,
  availability_status text not null default 'monitoring',
  official_url text,
  result_check_url text,
  summary text,
  eligibility_summary text,
  application_window_summary text,
  safety_notes text,
  source_confidence text not null default 'medium',
  last_verified_at timestamptz,
  next_review_due_at timestamptz,
  tags text[] not null default '{}',
  is_public boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.relocation_opportunities add column if not exists opportunity_code text;
alter table public.relocation_opportunities add column if not exists country_code text;
alter table public.relocation_opportunities add column if not exists country_name text;
alter table public.relocation_opportunities add column if not exists opportunity_name text;
alter table public.relocation_opportunities add column if not exists opportunity_type text;
alter table public.relocation_opportunities add column if not exists route_category text;
alter table public.relocation_opportunities add column if not exists availability_status text default 'monitoring';
alter table public.relocation_opportunities add column if not exists official_url text;
alter table public.relocation_opportunities add column if not exists result_check_url text;
alter table public.relocation_opportunities add column if not exists summary text;
alter table public.relocation_opportunities add column if not exists eligibility_summary text;
alter table public.relocation_opportunities add column if not exists application_window_summary text;
alter table public.relocation_opportunities add column if not exists safety_notes text;
alter table public.relocation_opportunities add column if not exists source_confidence text default 'medium';
alter table public.relocation_opportunities add column if not exists last_verified_at timestamptz;
alter table public.relocation_opportunities add column if not exists next_review_due_at timestamptz;
alter table public.relocation_opportunities add column if not exists tags text[] not null default '{}';
alter table public.relocation_opportunities add column if not exists is_public boolean not null default true;
alter table public.relocation_opportunities add column if not exists created_at timestamptz not null default now();
alter table public.relocation_opportunities add column if not exists updated_at timestamptz not null default now();

create unique index if not exists relocation_opportunities_code_uidx
  on public.relocation_opportunities (opportunity_code);

insert into public.relocation_opportunities (
  opportunity_code,
  country_code,
  country_name,
  opportunity_name,
  opportunity_type,
  route_category,
  availability_status,
  official_url,
  result_check_url,
  summary,
  eligibility_summary,
  application_window_summary,
  safety_notes,
  source_confidence,
  last_verified_at,
  next_review_due_at,
  tags,
  is_public
)
values
(
  'US-DV',
  'US',
  'United States',
  'Diversity Visa Program',
  'lottery',
  'immigrant_lottery',
  'monitoring',
  'https://travel.state.gov/content/travel/en/us-visas/immigrate/diversity-visa-program-entry.html',
  'https://dvprogram.state.gov/',
  'Annual Diversity Visa route for eligible people from qualifying countries. MoveReady tracks official entry, result-check, document, and scam-safety reminders.',
  'Eligibility depends on country rules plus education or work-experience requirements published by the U.S. Department of State.',
  'Registration and result-check windows must be verified from the official Department of State pages for each program year.',
  'There is no paid advantage, no guaranteed selection, and duplicate entries can create serious risk. Users should keep their confirmation number and use the official E-DV website only.',
  'high',
  '2026-06-19 00:00:00+00',
  '2026-07-19 00:00:00+00',
  array['usa','diversity visa','lottery','green card','official-only','scam-warning'],
  true
),
(
  'CA-IEC',
  'CA',
  'Canada',
  'International Experience Canada invitation pools',
  'invitation_pool',
  'working_holiday',
  'open',
  'https://ircc.canada.ca/english/work/iec/selections.asp',
  null,
  'Invitation-pool system for eligible youth from partner countries and territories to work and travel in Canada.',
  'Eligibility depends on citizenship or territory, age, category, quota, admissibility, and season rules.',
  'IRCC publishes country-specific key dates, available spots, invitation chances, and normally updates pool numbers weekly during the season.',
  'Creating a profile or entering a pool does not guarantee an invitation or final approval. Users must follow official IRCC deadlines after invitation.',
  'high',
  '2026-06-19 00:00:00+00',
  '2026-07-03 00:00:00+00',
  array['canada','iec','working holiday','invitation pool','youth mobility'],
  true
),
(
  'AU-462-BALLOT',
  'AU',
  'Australia',
  'Work and Holiday subclass 462 ballot and country caps',
  'ballot',
  'working_holiday',
  'monitoring',
  'https://immi.homeaffairs.gov.au/what-we-do/whm-program/status-of-country-caps',
  null,
  'Work and Holiday route with annual caps for some countries and ballot arrangements for selected high-demand countries.',
  'Eligibility depends on passport country, age, education, funds, health, character, and country-specific subclass 462 rules.',
  'Program year runs from 1 July to 30 June. Country cap status may be open, paused, or closed and must be checked on Home Affairs.',
  'A ballot or open cap only allows a person to apply. It does not guarantee visa grant.',
  'high',
  '2026-06-19 00:00:00+00',
  '2026-07-03 00:00:00+00',
  array['australia','subclass 462','work and holiday','ballot','country cap'],
  true
),
(
  'UK-IYPS',
  'GB',
  'United Kingdom',
  'India Young Professionals Scheme ballot',
  'ballot',
  'youth_mobility',
  'monitoring',
  'https://www.gov.uk/guidance/india-young-professionals-scheme-visa-ballot-system',
  null,
  'Ballot route for eligible Indian citizens who want to apply under the India Young Professionals Scheme visa.',
  'Eligibility includes Indian citizenship, age rules, qualification and savings requirements, and ballot selection before application.',
  'GOV.UK publishes ballot opening and closing dates before each round. The first 2026 ballot has closed and the page should be monitored for the next 2026 ballot.',
  'Entering the ballot is not approval. Users should use GOV.UK only and must still meet all visa requirements if selected.',
  'high',
  '2026-06-19 00:00:00+00',
  '2026-07-19 00:00:00+00',
  array['uk','india','young professionals','ballot','youth mobility'],
  true
),
(
  'NZ-PAC',
  'NZ',
  'New Zealand',
  'Pacific Access Category Resident Visa ballot',
  'ballot',
  'resident_quota',
  'monitoring',
  'https://www.immigration.govt.nz/visas/pacific-access-category-resident-visa/',
  'https://www.immigration.govt.nz/live/resident-visas-to-live-in-new-zealand/resident-visas-for-samoa-kiribati-tuvalu-tonga-and-fiji-nationals/pacific-access-category-resident-visa-ballot-results/',
  'Annual ballot route that can lead selected eligible citizens of Fiji, Kiribati, Tonga, and Tuvalu toward New Zealand residence.',
  'Eligibility is limited to eligible citizens of Fiji, Kiribati, Tonga, or Tuvalu, with age, birth/parentage, location, health, character, job offer, and family requirements.',
  'The 2026 ballot results have been published. Future registration reopening dates should be checked directly with Immigration New Zealand.',
  'A drawn ballot number is not final residence approval. Users should keep their registration number and follow official INZ invitation instructions.',
  'high',
  '2026-06-19 00:00:00+00',
  '2026-07-19 00:00:00+00',
  array['new zealand','pacific access category','pac','ballot','quota','residence'],
  true
),
(
  'NZ-SQ',
  'NZ',
  'New Zealand',
  'Samoan Quota Resident Visa ballot',
  'ballot',
  'resident_quota',
  'monitoring',
  'https://www.immigration.govt.nz/visas/samoan-quota-resident-visa/',
  'https://www.immigration.govt.nz/live/resident-visas-to-live-in-new-zealand/resident-visas-for-samoa-kiribati-tuvalu-tonga-and-fiji-nationals/samoan-quota-resident-visa-ballot-results/',
  'Annual quota ballot allowing selected eligible Samoan citizens to apply for New Zealand residence.',
  'Eligibility is limited to eligible Samoan citizens, with age, birth/parentage, location, health, character, job offer, income, English, and family requirements.',
  'The 2026 ballot results have been published. Future opening dates should be monitored directly on Immigration New Zealand.',
  'A ballot draw is not final approval. Users should keep their registration number and follow official INZ instructions if selected.',
  'high',
  '2026-06-19 00:00:00+00',
  '2026-07-19 00:00:00+00',
  array['new zealand','samoan quota','sq','ballot','quota','residence'],
  true
)
on conflict (opportunity_code) do update set
  country_code = excluded.country_code,
  country_name = excluded.country_name,
  opportunity_name = excluded.opportunity_name,
  opportunity_type = excluded.opportunity_type,
  route_category = excluded.route_category,
  availability_status = excluded.availability_status,
  official_url = excluded.official_url,
  result_check_url = excluded.result_check_url,
  summary = excluded.summary,
  eligibility_summary = excluded.eligibility_summary,
  application_window_summary = excluded.application_window_summary,
  safety_notes = excluded.safety_notes,
  source_confidence = excluded.source_confidence,
  last_verified_at = excluded.last_verified_at,
  next_review_due_at = excluded.next_review_due_at,
  tags = excluded.tags,
  is_public = excluded.is_public,
  updated_at = now();
