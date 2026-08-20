-- MoveReady migration 042
-- Reconcile the private job-alert inbox with canonical vacancy state.
-- Historical alerts are preserved. Superseded/non-actionable vacancy alerts are dismissed;
-- current vacancy alerts and operational scan failures remain available.
-- Safe to rerun after migrations 040 and 041.

-- 1) Dismiss every vacancy-bound alert whose referenced vacancy is no longer active.
-- This covers canonical duplicates archived by migration 041 as well as other historical
-- vacancy rows that have become closed/archived. Scan failures have no job_id and are not touched.
update public.relocation_job_alerts a
set
  status = 'dismissed',
  read_at = coalesce(a.read_at, now()),
  updated_at = now()
from public.relocation_jobs j
where a.job_id = j.id
  and a.status <> 'dismissed'
  and j.status not in ('open', 'discovered');

-- 2) For active canonical vacancies, retain only the newest actionable alert of each semantic
-- type. This protects the inbox from historical duplicate alerts created before canonical
-- identity support while preserving the full alert rows for audit/history.
with ranked as (
  select
    a.id,
    row_number() over (
      partition by
        a.email,
        j.canonical_identity,
        a.alert_type
      order by
        a.created_at desc,
        a.id desc
    ) as rn
  from public.relocation_job_alerts a
  join public.relocation_jobs j on j.id = a.job_id
  where a.status <> 'dismissed'
    and j.status in ('open', 'discovered')
    and j.canonical_identity is not null
    and a.alert_type in ('new_match', 'job_changed', 'job_reopened', 'closing_soon')
), superseded as (
  select id from ranked where rn > 1
)
update public.relocation_job_alerts a
set
  status = 'dismissed',
  read_at = coalesce(a.read_at, now()),
  updated_at = now()
from superseded s
where a.id = s.id;

-- 3) A job_closed alert cannot be actionable when the same canonical vacancy currently has
-- an active survivor. Keep the historical alert but dismiss it from the live inbox.
update public.relocation_job_alerts a
set
  status = 'dismissed',
  read_at = coalesce(a.read_at, now()),
  updated_at = now()
from public.relocation_jobs historical
where a.job_id = historical.id
  and a.alert_type = 'job_closed'
  and a.status <> 'dismissed'
  and historical.canonical_identity is not null
  and exists (
    select 1
    from public.relocation_jobs active
    where active.owner_email = historical.owner_email
      and active.canonical_identity = historical.canonical_identity
      and active.status in ('open', 'discovered')
  );

-- 4) Index the live inbox path used by the automation overview.
create index if not exists relocation_job_alerts_actionable_owner_idx
  on public.relocation_job_alerts (email, created_at desc)
  where status in ('unread', 'read');

notify pgrst, 'reload schema';
