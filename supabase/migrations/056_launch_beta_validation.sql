-- MoveReady LQ12 — controlled launch-beta validation reports
begin;
create table if not exists public.relocation_launch_beta_reports (
 id uuid primary key default gen_random_uuid(),
 email text not null,
 cohort_code text not null default 'v1-controlled-beta',
 device_class text not null check (device_class in ('phone','tablet','desktop')),
 journey text not null check (journey in ('find','qualify','move','alerts','career','full_journey')),
 result text not null check (result in ('passed','blocked','needs_help')),
 severity text not null default 'none' check (severity in ('none','minor','major','critical')),
 summary text not null,
 reproduction_steps text,
 technical_help_required boolean not null default false,
 consent_to_contact boolean not null default false,
 app_commit text,
 backend_commit text,
 status text not null default 'open' check (status in ('open','reviewed','resolved','excluded')),
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now()
);
create index if not exists relocation_launch_beta_email_created_idx on public.relocation_launch_beta_reports(email,created_at desc);
create index if not exists relocation_launch_beta_status_severity_idx on public.relocation_launch_beta_reports(status,severity,created_at desc);
alter table public.relocation_launch_beta_reports enable row level security;
revoke all privileges on table public.relocation_launch_beta_reports from public,anon,authenticated;
grant all privileges on table public.relocation_launch_beta_reports to service_role;
comment on table public.relocation_launch_beta_reports is 'Private verified-account LQ12 beta observations. Reports are operational evidence, not immigration, employment or approval outcomes.';
commit;
