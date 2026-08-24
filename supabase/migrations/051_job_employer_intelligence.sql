-- MoveReady B19.11.2 — Employer persistence, vacancy linking and evidence-safe identity resolution
begin;

create table if not exists public.relocation_job_employers (
  id uuid primary key default gen_random_uuid(),
  canonical_key text not null unique,
  canonical_name text not null,
  normalized_name text not null,
  domain text,
  country text,
  industry text,
  aliases jsonb not null default '[]'::jsonb,
  identity_basis text not null check (identity_basis in ('verified_domain','normalized_name_and_country')),
  domain_verified boolean not null default false,
  domain_evidence_url text,
  domain_evidence_observed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (not domain_verified or (domain is not null and domain_evidence_url is not null and domain_evidence_observed_at is not null))
);
create index if not exists relocation_job_employers_name_country_idx on public.relocation_job_employers(normalized_name,country);
create index if not exists relocation_job_employers_domain_idx on public.relocation_job_employers(domain) where domain is not null;

create table if not exists public.relocation_job_employer_vacancies (
  employer_id uuid not null references public.relocation_job_employers(id) on delete cascade,
  job_id uuid not null,
  resolution_basis text not null check (resolution_basis in ('domain','name_and_country','manual_review')),
  resolution_confidence text not null check (resolution_confidence in ('high','reviewed')),
  evidence_url text,
  resolved_at timestamptz not null default now(),
  primary key(employer_id,job_id)
);
create unique index if not exists relocation_job_employer_vacancies_job_unique on public.relocation_job_employer_vacancies(job_id);

alter table public.relocation_job_employers enable row level security;
alter table public.relocation_job_employer_vacancies enable row level security;
revoke all privileges on table public.relocation_job_employers from public,anon,authenticated;
revoke all privileges on table public.relocation_job_employer_vacancies from public,anon,authenticated;
grant all privileges on table public.relocation_job_employers to service_role;
grant all privileges on table public.relocation_job_employer_vacancies to service_role;

comment on table public.relocation_job_employers is 'Canonical employer identities. Identity resolution does not itself verify the employer, sponsorship, relocation support, hiring intent, or vacancy claims.';
comment on table public.relocation_job_employer_vacancies is 'Evidence-safe vacancy-to-employer resolution. A link is identity metadata only and does not transfer unsupported employer claims to a vacancy.';
commit;
