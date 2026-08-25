-- MoveReady LQ10 — private LinkedIn review and written mock-interview practice history
begin;
create table if not exists public.relocation_job_career_practice_sessions (
 id uuid primary key default gen_random_uuid(),
 email text not null,
 practice_type text not null check (practice_type in ('linkedin_review','mock_interview')),
 job_id uuid references public.relocation_jobs(id) on delete set null,
 target_role text,
 language text not null default 'en' check (language in ('en','fr')),
 input_snapshot jsonb not null default '{}'::jsonb,
 output_snapshot jsonb not null default '{}'::jsonb,
 score numeric(5,2),
 status text not null default 'completed' check (status in ('draft','completed','archived')),
 user_confirmed boolean not null default true,
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now()
);
create index if not exists relocation_job_career_practice_email_type_idx on public.relocation_job_career_practice_sessions(email,practice_type,created_at desc);
alter table public.relocation_job_career_practice_sessions enable row level security;
revoke all privileges on table public.relocation_job_career_practice_sessions from public,anon,authenticated;
grant all privileges on table public.relocation_job_career_practice_sessions to service_role;
comment on table public.relocation_job_career_practice_sessions is 'Private user-confirmed LinkedIn review and mock-interview attempts. Feedback is advisory and must not infer employer, recruiter or selection outcomes.';
commit;