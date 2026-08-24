-- MoveReady B19.11.4 — employer target lists, watchlists and campaign integration
begin;
create table if not exists public.relocation_job_campaign_employer_targets (
 id uuid primary key default gen_random_uuid(),
 campaign_id uuid not null references public.relocation_job_search_campaigns(id) on delete cascade,
 employer_id uuid not null references public.relocation_job_employers(id) on delete cascade,
 email text not null,
 target_type text not null check (target_type in ('priority','watch','excluded')),
 reason text,
 source text not null default 'user',
 active boolean not null default true,
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now(),
 unique(campaign_id,employer_id)
);
create index if not exists relocation_job_campaign_employer_targets_campaign_type_idx on public.relocation_job_campaign_employer_targets(campaign_id,target_type) where active;
create index if not exists relocation_job_campaign_employer_targets_employer_idx on public.relocation_job_campaign_employer_targets(employer_id) where active;
alter table public.relocation_job_campaign_employer_targets enable row level security;
revoke all privileges on table public.relocation_job_campaign_employer_targets from public,anon,authenticated;
grant all privileges on table public.relocation_job_campaign_employer_targets to service_role;
comment on table public.relocation_job_campaign_employer_targets is 'User-scoped campaign employer preferences. Priority/watch status is not employer endorsement, sponsorship evidence, work authorization, or proof of vacancy suitability.';
commit;
