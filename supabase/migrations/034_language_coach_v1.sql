-- MoveReady Language & Immigration Exam Coach V1
-- Run after migration 033.

create table if not exists relocation_language_profiles (
  id uuid primary key default gen_random_uuid(),
  email text not null unique,
  language_selection text not null default 'english' check (language_selection in ('english','french','both')),
  english_allocation integer not null default 100 check (english_allocation between 0 and 100),
  french_allocation integer not null default 0 check (french_allocation between 0 and 100),
  daily_minutes integer not null default 20 check (daily_minutes between 5 and 180),
  english_exam text not null default 'IELTS General',
  french_exam text not null default 'TEF Canada',
  english_current_level integer not null default 0 check (english_current_level between 0 and 12),
  french_current_level integer not null default 0 check (french_current_level between 0 and 12),
  english_target_level integer not null default 7 check (english_target_level between 0 and 12),
  french_target_level integer not null default 7 check (french_target_level between 0 and 12),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (english_allocation + french_allocation = 100)
);

create table if not exists relocation_language_questions (
  id uuid primary key default gen_random_uuid(),
  language text not null check (language in ('english','french')),
  exam text not null,
  skill text not null check (skill in ('vocabulary','grammar','reading','listening')),
  difficulty integer not null default 1 check (difficulty between 1 and 5),
  prompt text not null,
  choices jsonb not null default '[]'::jsonb,
  correct_answer text not null,
  explanation text not null,
  content_origin text not null default 'moveready_original' check (content_origin in ('moveready_original','official_released')),
  source_url text,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists relocation_language_questions_pick_idx on relocation_language_questions(language, exam, skill, difficulty, is_active);

create table if not exists relocation_language_attempts (
  id uuid primary key default gen_random_uuid(),
  email text not null,
  question_id uuid not null references relocation_language_questions(id) on delete cascade,
  answer text,
  is_correct boolean not null,
  difficulty integer not null check (difficulty between 1 and 5),
  response_seconds integer,
  attempted_at timestamptz not null default now()
);
create index if not exists relocation_language_attempts_email_idx on relocation_language_attempts(email, attempted_at desc);

create table if not exists relocation_language_mistakes (
  id uuid primary key default gen_random_uuid(),
  email text not null,
  question_id uuid not null references relocation_language_questions(id) on delete cascade,
  mistake_count integer not null default 1,
  correct_streak integer not null default 0,
  next_review_at timestamptz not null default now(),
  last_answer text,
  last_attempt_at timestamptz not null default now(),
  mastered_at timestamptz,
  unique(email, question_id)
);
create index if not exists relocation_language_mistakes_due_idx on relocation_language_mistakes(email, next_review_at);

create table if not exists relocation_language_daily_progress (
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

alter table relocation_language_profiles enable row level security;
alter table relocation_language_questions enable row level security;
alter table relocation_language_attempts enable row level security;
alter table relocation_language_mistakes enable row level security;
alter table relocation_language_daily_progress enable row level security;

-- Backend service role owns access in V1; no anonymous/user-table policies are created here.
