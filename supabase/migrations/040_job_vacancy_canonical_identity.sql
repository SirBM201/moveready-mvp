-- MoveReady migration 040
-- Canonical identity support for official-source vacancies.
-- Additive and non-destructive: no historical vacancy, alert, application, or draft is deleted.

alter table if exists public.relocation_jobs
  add column if not exists canonical_identity text;

create index if not exists relocation_jobs_owner_canonical_identity_idx
  on public.relocation_jobs (owner_email, canonical_identity)
  where canonical_identity is not null;

comment on column public.relocation_jobs.canonical_identity is
  'Stable normalized identity for one genuine employer vacancy. Used to suppress duplicate source records without deleting historical rows.';

-- Backfill a conservative identity for existing monitored vacancies. The application
-- also recomputes identity from normalized source data at read/scan time, so this
-- backfill is intentionally non-destructive and does not merge referenced rows.
update public.relocation_jobs
set canonical_identity = md5(
  lower(coalesce(company_id::text, '')) || '|' ||
  lower(regexp_replace(coalesce(job_title, ''), '\\s+', ' ', 'g')) || '|' ||
  lower(regexp_replace(coalesce(city, ''), '\\s+', ' ', 'g')) || '|' ||
  lower(regexp_replace(coalesce(province, ''), '\\s+', ' ', 'g')) || '|' ||
  lower(regexp_replace(coalesce(country, ''), '\\s+', ' ', 'g'))
)
where source_fingerprint is not null
  and canonical_identity is null;
