-- MoveReady 035: Language & Immigration Exam Coach V1
create table if not exists public.language_learning_profiles (
  id uuid primary key default gen_random_uuid(),
  account_id uuid not null,
  language_choice text not null default 'english' check (language_choice in ('english','french','both')),
  english_exam text not null default 'ielts_general',
  french_exam text not null default 'tef_canada',
  english_allocation smallint not null default 50 check (english_allocation between 0 and 100),
  target_clb smallint,
  target_nclc smallint,
  daily_minutes smallint not null default 10 check (daily_minutes between 1 and 180),
  diagnostic_completed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(account_id)
);
create table if not exists public.language_practice_items (
  id uuid primary key default gen_random_uuid(),
  language text not null check (language in ('english','french')),
  exam text not null,
  skill text not null check (skill in ('vocabulary','grammar','reading','listening','speaking','writing')),
  difficulty smallint not null default 1 check (difficulty between 1 and 5),
  prompt text not null,
  choices jsonb,
  correct_answer jsonb not null,
  explanation text not null,
  source_type text not null default 'moveready_original' check (source_type in ('moveready_original','official_permitted')),
  source_url text,
  is_active boolean not null default true,
  created_at timestamptz not null default now()
);
create table if not exists public.language_practice_attempts (
  id uuid primary key default gen_random_uuid(),
  account_id uuid not null,
  item_id uuid not null references public.language_practice_items(id) on delete cascade,
  answer jsonb,
  is_correct boolean,
  score numeric(6,2),
  response_seconds integer,
  attempted_at timestamptz not null default now()
);
create table if not exists public.language_review_queue (
  id uuid primary key default gen_random_uuid(),
  account_id uuid not null,
  item_id uuid not null references public.language_practice_items(id) on delete cascade,
  mistake_count integer not null default 1,
  mastery numeric(5,2) not null default 0,
  next_review_at timestamptz not null default now(),
  last_reviewed_at timestamptz,
  unique(account_id,item_id)
);
create table if not exists public.language_learning_sessions (
  id uuid primary key default gen_random_uuid(),
  account_id uuid not null,
  language text not null check (language in ('english','french')),
  exam text not null,
  skill text not null,
  duration_seconds integer not null default 0,
  items_attempted integer not null default 0,
  items_correct integer not null default 0,
  completed_at timestamptz not null default now()
);
create index if not exists language_attempts_account_idx on public.language_practice_attempts(account_id,attempted_at desc);
create index if not exists language_review_due_idx on public.language_review_queue(account_id,next_review_at);
create index if not exists language_items_lookup_idx on public.language_practice_items(language,exam,skill,difficulty) where is_active=true;
