-- MoveReady migration 041
-- Reconcile duplicate official-source vacancy rows created before canonical identity support.
-- Historical rows are preserved. One survivor remains active per owner/canonical vacancy;
-- duplicate rows are archived and their alerts are dismissed so the automation UI counts
-- one genuine opportunity rather than repeated scan records.

-- Recompute canonical identity using the same conservative identity contract introduced
-- in migration 040. Contract/full-time wording remains part of the title, so genuinely
-- distinct employer postings are not merged merely because their base role is similar.
update public.relocation_jobs
set canonical_identity = md5(
  lower(coalesce(company_id::text, '')) || '|' ||
  lower(regexp_replace(trim(coalesce(job_title, '')), '\s+', ' ', 'g')) || '|' ||
  lower(regexp_replace(trim(coalesce(city, '')), '\s+', ' ', 'g')) || '|' ||
  lower(regexp_replace(trim(coalesce(province, '')), '\s+', ' ', 'g')) || '|' ||
  lower(regexp_replace(trim(coalesce(country, '')), '\s+', ' ', 'g'))
)
where source_fingerprint is not null;

-- Record the chosen survivor and duplicate relationship without deleting history.
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
    'reconciled_by', 'migration_041'
  )
from duplicates d
where j.id = d.id;

-- Suppress duplicate historical alerts from the private-alert inbox while retaining them.
-- The surviving vacancy's alerts remain untouched.
update public.relocation_job_alerts a
set
  status = 'dismissed',
  read_at = coalesce(a.read_at, now())
from public.relocation_jobs j
where a.job_id = j.id
  and j.status = 'archived'
  and coalesce(j.metadata ->> 'reconciled_by', '') = 'migration_041'
  and a.status <> 'dismissed';

-- Prevent an accidental second active row for the same canonical vacancy at database level.
-- Archived historical duplicates remain valid and queryable.
create unique index if not exists relocation_jobs_owner_canonical_active_uidx
  on public.relocation_jobs (owner_email, canonical_identity)
  where canonical_identity is not null
    and source_fingerprint is not null
    and status in ('open', 'discovered');

-- Keep lookup/reconciliation efficient for historical records too.
create index if not exists relocation_jobs_canonical_status_idx
  on public.relocation_jobs (owner_email, canonical_identity, status)
  where canonical_identity is not null;
