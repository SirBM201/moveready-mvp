-- Project MoveReady MVP
-- Readiness tool run storage.
-- Run after 001, 002, 003, 004, and 005 migrations.

create table if not exists public.relocation_readiness_check_runs (
  id uuid primary key default gen_random_uuid(),
  tool_slug text not null,
  status text not null default 'completed' check (status in ('completed', 'reviewing', 'archived', 'deleted')),
  risk_level text check (risk_level in ('low', 'medium', 'high')),
  readiness_status text check (readiness_status in ('ready_to_continue', 'review_recommended', 'needs_attention')),
  input_payload jsonb not null default '{}'::jsonb,
  result_payload jsonb not null default '{}'::jsonb,
  source_page text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists relocation_readiness_check_runs_tool_idx
  on public.relocation_readiness_check_runs (tool_slug);

create index if not exists relocation_readiness_check_runs_risk_idx
  on public.relocation_readiness_check_runs (risk_level);

create index if not exists relocation_readiness_check_runs_created_idx
  on public.relocation_readiness_check_runs (created_at desc);

drop trigger if exists relocation_readiness_check_runs_updated_at on public.relocation_readiness_check_runs;
create trigger relocation_readiness_check_runs_updated_at
before update on public.relocation_readiness_check_runs
for each row execute function public.relocation_set_updated_at();
