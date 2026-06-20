-- Project MoveReady MVP
-- Account workspace repair migration.
-- Purpose:
-- 1. Keep legacy profile schemas compatible with the current app payload.
-- 2. Ensure the timeline-events table exists for Account Center summaries.
-- Safe to rerun.

create extension if not exists pgcrypto;

create or replace function public.relocation_set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- Legacy compatibility:
-- Early profile versions used goal as a required field.
-- Current app sends main_goal. Keep both usable so old Supabase projects do not reject inserts.
create table if not exists public.relocation_user_profiles (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.relocation_user_profiles
  add column if not exists goal text,
  add column if not exists main_goal text not null default 'relocation';

update public.relocation_user_profiles
set goal = coalesce(nullif(goal, ''), nullif(main_goal, ''), 'relocation')
where goal is null or goal = '';

alter table public.relocation_user_profiles
  alter column goal set default 'relocation',
  alter column goal drop not null;

-- Timeline events used by Account Center summary and the public Timeline page.
create table if not exists public.relocation_timeline_events (
  id uuid primary key default gen_random_uuid(),
  full_name text,
  email text,
  phone text,
  current_country text,
  target_country text,
  route_or_goal text,
  route_category text,
  event_type text not null default 'task',
  event_title text not null,
  event_notes text,
  due_date date,
  reminder_date date,
  priority text not null default 'medium',
  preferred_channel text not null default 'email',
  consent_to_contact boolean not null default false,
  source_page text,
  status text not null default 'pending',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.relocation_timeline_events
  add column if not exists full_name text,
  add column if not exists email text,
  add column if not exists phone text,
  add column if not exists current_country text,
  add column if not exists target_country text,
  add column if not exists route_or_goal text,
  add column if not exists route_category text,
  add column if not exists event_type text not null default 'task',
  add column if not exists event_title text not null default 'Untitled timeline event',
  add column if not exists event_notes text,
  add column if not exists due_date date,
  add column if not exists reminder_date date,
  add column if not exists priority text not null default 'medium',
  add column if not exists preferred_channel text not null default 'email',
  add column if not exists consent_to_contact boolean not null default false,
  add column if not exists source_page text,
  add column if not exists status text not null default 'pending',
  add column if not exists metadata jsonb not null default '{}'::jsonb,
  add column if not exists created_at timestamptz not null default now(),
  add column if not exists updated_at timestamptz not null default now();

alter table public.relocation_timeline_events
  alter column event_type set default 'task',
  alter column event_title set default 'Untitled timeline event',
  alter column priority set default 'medium',
  alter column preferred_channel set default 'email',
  alter column consent_to_contact set default false,
  alter column status set default 'pending',
  alter column metadata set default '{}'::jsonb;

alter table public.relocation_timeline_events
  drop constraint if exists relocation_timeline_events_event_type_check,
  drop constraint if exists relocation_timeline_events_priority_check,
  drop constraint if exists relocation_timeline_events_status_check,
  drop constraint if exists relocation_timeline_events_channel_check;

alter table public.relocation_timeline_events
  add constraint relocation_timeline_events_event_type_check
  check (event_type in ('task', 'deadline', 'appointment', 'document', 'payment', 'travel', 'result', 'follow_up'));

alter table public.relocation_timeline_events
  add constraint relocation_timeline_events_priority_check
  check (priority in ('low', 'medium', 'high', 'critical'));

alter table public.relocation_timeline_events
  add constraint relocation_timeline_events_status_check
  check (status in ('pending', 'in_progress', 'done', 'missed', 'cancelled', 'archived'));

alter table public.relocation_timeline_events
  add constraint relocation_timeline_events_channel_check
  check (preferred_channel in ('email', 'whatsapp', 'telegram', 'phone', 'in_app'));

create index if not exists relocation_timeline_events_email_idx
on public.relocation_timeline_events (email);

create index if not exists relocation_timeline_events_status_idx
on public.relocation_timeline_events (status);

create index if not exists relocation_timeline_events_due_date_idx
on public.relocation_timeline_events (due_date);

create index if not exists relocation_timeline_events_created_at_idx
on public.relocation_timeline_events (created_at desc);

drop trigger if exists relocation_timeline_events_set_updated_at
on public.relocation_timeline_events;

create trigger relocation_timeline_events_set_updated_at
before update on public.relocation_timeline_events
for each row execute function public.relocation_set_updated_at();

notify pgrst, 'reload schema';
