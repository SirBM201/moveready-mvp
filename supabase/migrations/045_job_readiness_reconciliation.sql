-- MoveReady B19.3 — readiness reconciliation, vacancy change detection and state invalidation.
-- Safe after migration 044. Additive and rerunnable.

alter table public.relocation_job_application_readiness
  add column if not exists vacancy_fingerprint text,
  add column if not exists vacancy_changed_at timestamptz,
  add column if not exists last_reconciled_at timestamptz,
  add column if not exists invalidated_at timestamptz,
  add column if not exists invalidation_reason text,
  add column if not exists previous_state text,
  add column if not exists reconciliation_count integer not null default 0;

create index if not exists relocation_job_application_readiness_reconcile_idx
  on public.relocation_job_application_readiness(email, last_reconciled_at);

comment on column public.relocation_job_application_readiness.vacancy_fingerprint is
  'B19.3 deterministic fingerprint of application-relevant vacancy facts at last reconciliation.';
comment on column public.relocation_job_application_readiness.invalidated_at is
  'B19.3 time a previously user-promoted readiness state was invalidated by changed vacancy facts.';
comment on column public.relocation_job_application_readiness.invalidation_reason is
  'B19.3 conservative machine-readable reason for readiness invalidation; never an eligibility decision.';
