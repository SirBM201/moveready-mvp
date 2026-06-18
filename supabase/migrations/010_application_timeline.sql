-- Project MoveReady MVP
-- Application timeline and deadline tracker storage.
-- Run after 001 through 009 migrations.
-- Safe to rerun if the table was partially created before this migration.

create extension if not exists pgcrypto;

create table if not exists public.relocation_timeline_events (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.relocation_timeline_events add column if not exists full_name text;
alter table public.relocation_timeline_events add column if not exists email text;
alter table public.relocation_timeline_events add column if not exists phone text;
alter table public.relocation_timeline_events add column if not exists current_country text;
alter table public.relocation_timeline_events add column if not exists target_country text;
alter table public.relocation_timeline_events add column if not exists route_or_goal text;
alter table public.relocation_timeline_events add column if not exists route_category text;
alter table public.relocation_timeline_events add column if not exists event_type text not null default 'task';
alter table public.relocation_timeline_events add column if not exists event_title text;
alter table public.relocation_timeline_events add column if not exists event_notes text;
alter table public.relocation_timeline_events add column if not exists due_date date;
alter table public.relocation_timeline_events add column if not exists reminder_date date;
alter table public.relocation_timeline_events add column if not exists priority text not null default 'medium';
alter table public.relocation_timeline_events add column if not exists status text not null default 'pending';
alter table public.relocation_timeline_events add column if not exists preferred_channel text not null default 'email';
alter table public.relocation_timeline_events add column if not exists consent_to_contact boolean not null default false;
alter table public.relocation_timeline_events add column if not exists source_page text;
alter table public.relocation_timeline_events add column if not exists metadata jsonb not null default '{}'::jsonb;

alter table public.relocation_timeline_events alter column event_type set default 'task';
alter table public.relocation_timeline_events alter column priority set default 'medium';
alter table public.relocation_timeline_events alter column status set default 'pending';
alter table public.relocation_timeline_events alter column preferred_channel set default 'email';
alter table public.relocation_timeline_events alter column consent_to_contact set default false;
alter table public.relocation_timeline_events alter column metadata set default '{}'::jsonb;

update public.relocation_timeline_events
set event_title = coalesce(event_title, 'Timeline event')
where event_title is null;

alter table public.relocation_timeline_events alter column event_title set not null;

create or replace function public.relocation_set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'relocation_timeline_events_event_type_check'
      and conrelid = 'public.relocation_timeline_events'::regclass
  ) then
    alter table public.relocation_timeline_events
      add constraint relocation_timeline_events_event_type_check
      check (event_type in ('task', 'deadline', 'appointment', 'document', 'payment', 'travel', 'result', 'follow_up'));
  end if;
end $$;

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'relocation_timeline_events_priority_check'
      and conrelid = 'public.relocation_timeline_events'::regclass
  ) then
    alter table public.relocation_timeline_events
      add constraint relocation_timeline_events_priority_check
      check (priority in ('low', 'medium', 'high', 'critical'));
  end if;
end $$;

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'relocation_timeline_events_status_check'
      and conrelid = 'public.relocation_timeline_events'::regclass
  ) then
    alter table public.relocation_timeline_events
      add constraint relocation_timeline_events_status_check
      check (status in ('pending', 'in_progress', 'done', 'missed', 'cancelled', 'archived'));
  end if;
end $$;

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'relocation_timeline_events_channel_check'
      and conrelid = 'public.relocation_timeline_events'::regclass
  ) then
    alter table public.relocation_timeline_events
      add constraint relocation_timeline_events_channel_check
      check (preferred_channel in ('email', 'whatsapp', 'telegram', 'phone', 'in_app'));
  end if;
end $$;

create index if not exists relocation_timeline_events_email_idx on public.relocation_timeline_events (email);
create index if not exists relocation_timeline_events_phone_idx on public.relocation_timeline_events (phone);
create index if not exists relocation_timeline_events_status_idx on public.relocation_timeline_events (status);
create index if not exists relocation_timeline_events_due_date_idx on public.relocation_timeline_events (due_date);
create index if not exists relocation_timeline_events_event_type_idx on public.relocation_timeline_events (event_type);
create index if not exists relocation_timeline_events_target_country_idx on public.relocation_timeline_events (target_country);
create index if not exists relocation_timeline_events_created_at_idx on public.relocation_timeline_events (created_at desc);

drop trigger if exists relocation_timeline_events_set_updated_at on public.relocation_timeline_events;
create trigger relocation_timeline_events_set_updated_at
before update on public.relocation_timeline_events
for each row execute function public.relocation_set_updated_at();
