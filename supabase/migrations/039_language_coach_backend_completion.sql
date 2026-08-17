-- MoveReady B07: self-contained Language Coach schema, starter bank, and hardening.
--
-- Safe to run after the current production migration frontier, even when the older
-- duplicate-numbered Language Coach migrations 034/035 were not applied. The
-- statements are idempotent, so rerunning the complete file is also safe.
--
-- This migration preserves the canonical relocation_language_* model. It does not
-- create the conflicting language_* tables proposed by stale PR #10.

begin;

create table if not exists public.relocation_language_profiles (
  id uuid primary key default gen_random_uuid(),
  email text not null unique,
  language_selection text not null default 'english'
    check (language_selection in ('english', 'french', 'both')),
  english_allocation integer not null default 100
    check (english_allocation between 0 and 100),
  french_allocation integer not null default 0
    check (french_allocation between 0 and 100),
  daily_minutes integer not null default 20
    check (daily_minutes between 5 and 180),
  english_exam text not null default 'IELTS General',
  french_exam text not null default 'TEF Canada',
  english_current_level integer not null default 0
    check (english_current_level between 0 and 12),
  french_current_level integer not null default 0
    check (french_current_level between 0 and 12),
  english_target_level integer not null default 7
    check (english_target_level between 0 and 12),
  french_target_level integer not null default 7
    check (french_target_level between 0 and 12),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (english_allocation + french_allocation = 100)
);

create table if not exists public.relocation_language_questions (
  id uuid primary key default gen_random_uuid(),
  language text not null check (language in ('english', 'french')),
  exam text not null,
  skill text not null check (skill in ('vocabulary', 'grammar', 'reading', 'listening')),
  difficulty integer not null default 1 check (difficulty between 1 and 5),
  prompt text not null,
  choices jsonb not null default '[]'::jsonb,
  correct_answer text not null,
  explanation text not null,
  content_origin text not null default 'moveready_original'
    check (content_origin in ('moveready_original', 'official_released')),
  source_url text,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists relocation_language_questions_pick_idx
  on public.relocation_language_questions(language, exam, skill, difficulty, is_active);

create table if not exists public.relocation_language_attempts (
  id uuid primary key default gen_random_uuid(),
  email text not null,
  question_id uuid not null
    references public.relocation_language_questions(id) on delete cascade,
  answer text,
  is_correct boolean not null,
  difficulty integer not null check (difficulty between 1 and 5),
  response_seconds integer,
  attempted_at timestamptz not null default now()
);

create index if not exists relocation_language_attempts_email_idx
  on public.relocation_language_attempts(email, attempted_at desc);

create table if not exists public.relocation_language_mistakes (
  id uuid primary key default gen_random_uuid(),
  email text not null,
  question_id uuid not null
    references public.relocation_language_questions(id) on delete cascade,
  mistake_count integer not null default 1,
  correct_streak integer not null default 0,
  next_review_at timestamptz not null default now(),
  last_answer text,
  last_attempt_at timestamptz not null default now(),
  mastered_at timestamptz,
  unique(email, question_id)
);

create index if not exists relocation_language_mistakes_due_idx
  on public.relocation_language_mistakes(email, next_review_at);

create table if not exists public.relocation_language_daily_progress (
  id uuid primary key default gen_random_uuid(),
  email text not null,
  activity_date date not null default current_date,
  english_minutes integer not null default 0,
  french_minutes integer not null default 0,
  questions_attempted integer not null default 0,
  questions_correct integer not null default 0,
  momentum_points integer not null default 0,
  unique(email, activity_date)
);

-- Seed the original MoveReady starter bank without duplicating questions on rerun.
-- These are exam-style practice questions, not recalled or live exam material.
with starter (
  language, exam, skill, difficulty, prompt, choices,
  correct_answer, explanation, content_origin
) as (
  values
    ('english', 'IELTS General', 'grammar', 1,
      'Choose the sentence that is grammatically correct.',
      '["She has worked here for three years.","She work here since three years.","She is work here for three years.","She working here since three years."]'::jsonb,
      'She has worked here for three years.',
      'Use the present perfect for an action that began in the past and continues to the present.',
      'moveready_original'),
    ('english', 'IELTS General', 'vocabulary', 1,
      'In a workplace notice, what does “mandatory” most nearly mean?',
      '["Optional","Required","Delayed","Expensive"]'::jsonb,
      'Required', 'Mandatory means required or compulsory.', 'moveready_original'),
    ('english', 'IELTS General', 'reading', 2,
      'Notice: The staff entrance will be closed from 6 p.m. Friday until 7 a.m. Monday for maintenance. Employees working during this period should use the east entrance. Which entrance should a Saturday employee use?',
      '["Staff entrance","East entrance","Main visitor entrance","Loading entrance"]'::jsonb,
      'East entrance',
      'The notice directly instructs employees working during the closure to use the east entrance.',
      'moveready_original'),
    ('english', 'IELTS General', 'grammar', 2,
      'Complete the sentence: If the documents arrive today, we ___ the application tomorrow.',
      '["submit","submitted","will submit","would submitted"]'::jsonb,
      'will submit',
      'A real future condition commonly uses present simple in the if-clause and will + verb in the result clause.',
      'moveready_original'),
    ('english', 'IELTS General', 'vocabulary', 2,
      'Which word best completes the sentence? The employer asked for a ___ copy of the certificate, not the original.',
      '["duplicate","temporary","vacant","remote"]'::jsonb,
      'duplicate', 'A duplicate is an additional copy of an original document.',
      'moveready_original'),
    ('english', 'IELTS General', 'reading', 3,
      'Email: Your interview remains scheduled for 10:00 a.m. on Tuesday. Please arrive 15 minutes early for security registration. Candidates arriving after 10:00 may need to reschedule. What is the best arrival time?',
      '["9:45 a.m.","10:00 a.m.","10:15 a.m.","9:15 a.m."]'::jsonb,
      '9:45 a.m.', 'Arriving 15 minutes before a 10:00 a.m. interview means 9:45 a.m.',
      'moveready_original'),
    ('english', 'IELTS General', 'grammar', 3,
      'Choose the best completion: The manager recommended that the applicant ___ the updated form.',
      '["submits","submit","submitted","submitting"]'::jsonb,
      'submit',
      'After recommend that, formal English commonly uses the base-form subjunctive: submit.',
      'moveready_original'),
    ('english', 'IELTS General', 'vocabulary', 3,
      'In immigration planning, a “deadline” is best described as:',
      '["a recommended destination","the latest time something must be completed","a financial deposit","a type of interview"]'::jsonb,
      'the latest time something must be completed',
      'A deadline is the final/latest time by which an action must be completed.',
      'moveready_original'),
    ('french', 'TEF Canada', 'vocabulary', 1,
      'Choisissez le mot qui complète la phrase : Je dois ___ mon passeport avant le voyage.',
      '["renouveler","fermer","oublier","vendre"]'::jsonb,
      'renouveler', 'On renouvelle un passeport lorsqu’il arrive à expiration.',
      'moveready_original'),
    ('french', 'TEF Canada', 'grammar', 1,
      'Choisissez la phrase correcte.',
      '["Nous habitons ici depuis deux ans.","Nous habitons ici il y a deux ans.","Nous habite ici depuis deux ans.","Nous habitons ici pour deux ans passé."]'::jsonb,
      'Nous habitons ici depuis deux ans.',
      'Depuis s’emploie avec le présent pour une situation commencée dans le passé et toujours vraie.',
      'moveready_original'),
    ('french', 'TEF Canada', 'reading', 2,
      'Avis : Le bureau sera fermé mercredi matin. Il ouvrira à 13 h. À quelle heure peut-on venir mercredi ?',
      '["9 h","11 h","13 h 30","12 h"]'::jsonb,
      '13 h 30', 'Le bureau ouvre à 13 h ; 13 h 30 est donc une heure possible.',
      'moveready_original'),
    ('french', 'TEF Canada', 'vocabulary', 2,
      'Dans une offre d’emploi, “expérience exigée” signifie :',
      '["expérience facultative","expérience obligatoire","formation gratuite","travail à distance"]'::jsonb,
      'expérience obligatoire', 'Exigée signifie demandée comme condition obligatoire.',
      'moveready_original'),
    ('french', 'TEF Canada', 'grammar', 2,
      'Complétez : Si j’obtiens le visa, je ___ au Canada en septembre.',
      '["partirai","partais","partir","parti"]'::jsonb,
      'partirai', 'Pour une condition réelle au futur : si + présent, puis futur simple.',
      'moveready_original'),
    ('french', 'TEF Canada', 'reading', 3,
      'Message : Votre rendez-vous est à 14 h. Merci de vous présenter vingt minutes avant avec une pièce d’identité. À quelle heure faut-il arriver ?',
      '["13 h 20","13 h 40","14 h","14 h 20"]'::jsonb,
      '13 h 40', 'Vingt minutes avant 14 h correspond à 13 h 40.',
      'moveready_original'),
    ('french', 'TEF Canada', 'grammar', 3,
      'Choisissez la bonne réponse : Il faut que vous ___ ce formulaire avant vendredi.',
      '["remplissez","remplissiez","remplir","rempli"]'::jsonb,
      'remplissiez', 'Après “il faut que”, on emploie le subjonctif : que vous remplissiez.',
      'moveready_original'),
    ('french', 'TEF Canada', 'vocabulary', 3,
      'Le mot “échéance” désigne le plus souvent :',
      '["une date limite","un logement","un entretien","un diplôme"]'::jsonb,
      'une date limite',
      'Une échéance est une date ou limite prévue pour accomplir une obligation.',
      'moveready_original')
)
insert into public.relocation_language_questions (
  language, exam, skill, difficulty, prompt, choices,
  correct_answer, explanation, content_origin
)
select
  starter.language,
  starter.exam,
  starter.skill,
  starter.difficulty,
  starter.prompt,
  starter.choices,
  starter.correct_answer,
  starter.explanation,
  starter.content_origin
from starter
where not exists (
  select 1
  from public.relocation_language_questions existing
  where existing.language = starter.language
    and existing.exam = starter.exam
    and existing.skill = starter.skill
    and existing.difficulty = starter.difficulty
    and existing.prompt = starter.prompt
);

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
        or (
          language_selection = 'both'
          and english_allocation in (30, 50, 70)
          and french_allocation = 100 - english_allocation
        )
      ) not valid;
  end if;

  if not exists (
    select 1 from pg_constraint
    where conname = 'relocation_language_questions_b07_choices_chk'
      and conrelid = 'public.relocation_language_questions'::regclass
  ) then
    alter table public.relocation_language_questions
      add constraint relocation_language_questions_b07_choices_chk
      check (
        case
          when jsonb_typeof(choices) = 'array' then jsonb_array_length(choices) >= 2
          else false
        end
      ) not valid;
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

commit;
