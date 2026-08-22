-- MoveReady migration 043
-- Align production scan identity with the canonical vacancy reconciliation contract.
-- Safe after 040-042. Historical rows are preserved; duplicate rows are archived.
-- Safe to rerun after a failed attempt: the active canonical uniqueness guard is
-- temporarily removed before identities are recomputed, then restored at the end.

-- The pre-043 unique index can reject the canonical-identity rewrite before duplicate
-- rows have had a chance to be archived. Remove the guard first, reconcile the rows,
-- then reassert the invariant after cleanup.
drop index if exists public.relocation_jobs_owner_canonical_active_uidx;

-- Runtime identity is watch + normalized title + normalized location. A watch belongs
-- to one employer/source, and this avoids URL/tracking changes creating new vacancies.
update public.relocation_jobs
set canonical_identity = md5(
  lower(coalesce(metadata ->> 'automation_watch_id', '')) || '|' ||
  lower(regexp_replace(trim(coalesce(job_title, '')), '\s+', ' ', 'g')) || '|' ||
  lower(regexp_replace(trim(coalesce(city, '')), '\s+', ' ', 'g')) || '|' ||
  lower(regexp_replace(trim(coalesce(province, '')), '\s+', ' ', 'g')) || '|' ||
  lower(regexp_replace(trim(coalesce(country, '')), '\s+', ' ', 'g'))
)
where source_fingerprint is not null
  and coalesce(metadata ->> 'automation_watch_id', '') <> '';

-- Choose one survivor for every canonical monitored vacancy. This repeats the
-- reconciliation after the corrected identity is applied, so duplicates created by
-- repeated production scans are cleaned without deleting application history.
with ranked as (
  select
    id,
    owner_email,
    canonical_identity,
    first_value(id) over (
      partition by owner_email, canonical_identity
      order by
        case when status in ('open', 'discovered') then 0 else 1 end,
        last_seen_at desc nulls last,
        updated_at desc nulls last,
        created_at desc nulls last,
        id
    ) as survivor_id,
    row_number() over (
      partition by owner_email, canonical_identity
      order by
        case when status in ('open', 'discovered') then 0 else 1 end,
        last_seen_at desc nulls last,
        updated_at desc nulls last,
        created_at desc nulls last,
        id
    ) as rn
  from public.relocation_jobs
  where source_fingerprint is not null
    and canonical_identity is not null
    and coalesce(metadata ->> 'automation_watch_id', '') <> ''
), duplicates as (
  select id, survivor_id
  from ranked
  where rn > 1
)
update public.relocation_jobs j
set
  status = 'archived',
  metadata = coalesce(j.metadata, '{}'::jsonb) || jsonb_build_object(
    'canonical_duplicate', true,
    'canonical_survivor_job_id', d.survivor_id,
    'reconciled_by', 'migration_043'
  )
from duplicates d
where j.id = d.id;

-- Keep duplicate historical alerts but remove them from the actionable inbox.
update public.relocation_job_alerts a
set
  status = 'dismissed',
  read_at = coalesce(a.read_at, now())
from public.relocation_jobs j
where a.job_id = j.id
  and j.status = 'archived'
  and coalesce(j.metadata ->> 'reconciled_by', '') = 'migration_043'
  and a.status <> 'dismissed';

-- Critical runtime bridge: job_automation already looks up source_fingerprint before
-- insert. Make the surviving active row use the same value emitted by the corrected
-- Python fingerprint function, so the next scan updates instead of inserts.
update public.relocation_jobs
set source_fingerprint = canonical_identity
where source_fingerprint is not null
  and canonical_identity is not null
  and coalesce(metadata ->> 'automation_watch_id', '') <> ''
  and status in ('open', 'discovered');

-- Reassert the database invariant after reconciliation.
create unique index relocation_jobs_owner_canonical_active_uidx
  on public.relocation_jobs (owner_email, canonical_identity)
  where canonical_identity is not null
    and source_fingerprint is not null
    and status in ('open', 'discovered');

comment on index public.relocation_jobs_owner_canonical_active_uidx is
  'Guarantees one active monitored vacancy per owner and canonical watch/title/location identity.';
