-- MoveReady B07: Language Coach backend completion and privacy/provenance hardening.
--
-- Prerequisites:
--   034_language_coach_v1.sql
--   035_language_coach_starter_bank.sql
--
-- This migration deliberately preserves the canonical relocation_language_* model.
-- It does not create the conflicting language_* tables proposed by stale PR #10.

do $$
declare
  required_table text;
begin
  foreach required_table in array array[
    'relocation_language_profiles',
    'relocation_language_questions',
    'relocation_language_attempts',
    'relocation_language_mistakes',
    'relocation_language_daily_progress'
  ]
  loop
    if to_regclass('public.' || required_table) is null then
      raise exception
        'B07 prerequisite missing: public.% does not exist. Apply 034_language_coach_v1.sql and 035_language_coach_starter_bank.sql first.',
        required_table;
    end if;
  end loop;
end
$$;

alter table public.relocation_language_profiles enable row level security;
alter table public.relocation_language_questions enable row level security;
alter table public.relocation_language_attempts enable row level security;
alter table public.relocation_language_mistakes enable row level security;
alter table public.relocation_language_daily_progress enable row level security;

revoke all privileges on table public.relocation_language_profiles from public, anon, authenticated;
revoke all privileges on table public.relocation_language_questions from public, anon, authenticated;
revoke all privileges on table public.relocation_language_attempts from public, anon, authenticated;
revoke all privileges on table public.relocation_language_mistakes from public, anon, authenticated;
revoke all privileges on table public.relocation_language_daily_progress from public, anon, authenticated;

grant all privileges on table public.relocation_language_profiles to service_role;
grant all privileges on table public.relocation_language_questions to service_role;
grant all privileges on table public.relocation_language_attempts to service_role;
grant all privileges on table public.relocation_language_mistakes to service_role;
grant all privileges on table public.relocation_language_daily_progress to service_role;

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'relocation_language_profiles_b07_allocation_chk'
      and conrelid = 'public.relocation_language_profiles'::regclass
  ) then
    alter table public.relocation_language_profiles
      add constraint relocation_language_profiles_b07_allocation_chk
      check (
        (language_selection = 'english' and english_allocation = 100 and french_allocation = 0)
        or (language_selection = 'french' and english_allocation = 0 and french_allocation = 100)
        or (language_selection = 'both' and english_allocation in (30, 50, 70) and french_allocation = 100 - english_allocation)
      ) not valid;
  end if;

  if not exists (
    select 1 from pg_constraint
    where conname = 'relocation_language_questions_b07_choices_chk'
      and conrelid = 'public.relocation_language_questions'::regclass
  ) then
    alter table public.relocation_language_questions
      add constraint relocation_language_questions_b07_choices_chk
      check (jsonb_typeof(choices) = 'array' and jsonb_array_length(choices) >= 2) not valid;
  end if;

  if not exists (
    select 1 from pg_constraint
    where conname = 'relocation_language_questions_b07_provenance_chk'
      and conrelid = 'public.relocation_language_questions'::regclass
  ) then
    alter table public.relocation_language_questions
      add constraint relocation_language_questions_b07_provenance_chk
      check (
        content_origin = 'moveready_original'
        or (
          content_origin = 'official_released'
          and source_url is not null
          and source_url ~ '^https://'
        )
      ) not valid;
  end if;

  if not exists (
    select 1 from pg_constraint
    where conname = 'relocation_language_attempts_b07_response_seconds_chk'
      and conrelid = 'public.relocation_language_attempts'::regclass
  ) then
    alter table public.relocation_language_attempts
      add constraint relocation_language_attempts_b07_response_seconds_chk
      check (response_seconds is null or response_seconds between 0 and 7200) not valid;
  end if;
end
$$;

comment on table public.relocation_language_profiles is
  'B07 private Language Coach preferences and internal placement targets; never official exam results.';
comment on table public.relocation_language_questions is
  'B07 original or permitted official-release practice content; recalled or leaked live exam content is prohibited.';
comment on table public.relocation_language_attempts is
  'B07 private account practice attempts used for internal adaptive learning only.';
comment on table public.relocation_language_mistakes is
  'B07 private spaced-review queue; no punitive streak reset.';
comment on table public.relocation_language_daily_progress is
  'B07 private non-punitive practice momentum and progress summary.';
