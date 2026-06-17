-- Project MoveReady MVP
-- Route watchlist and opt-in alert subscription storage.
-- Run after 001 through 006 migrations.

create table if not exists public.relocation_watchlist_subscriptions (
  id uuid primary key default gen_random_uuid(),
  watch_type text not null default 'route' check (watch_type in ('route', 'opportunity', 'scholarship', 'country', 'service')),
  watch_code text,
  watch_title text,
  full_name text,
  email text,
  phone text,
  preferred_channel text not null default 'email' check (preferred_channel in ('email', 'whatsapp', 'telegram', 'phone', 'in_app')),
  current_country text,
  target_country text,
  route_or_goal text,
  alert_types text[] not null default array[]::text[],
  consent_to_contact boolean not null default false,
  status text not null default 'active' check (status in ('active', 'paused', 'unsubscribed', 'closed', 'spam')),
  source_page text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists relocation_watchlist_subscriptions_watch_idx
  on public.relocation_watchlist_subscriptions (watch_type, watch_code);

create index if not exists relocation_watchlist_subscriptions_status_idx
  on public.relocation_watchlist_subscriptions (status);

create index if not exists relocation_watchlist_subscriptions_channel_idx
  on public.relocation_watchlist_subscriptions (preferred_channel);

create index if not exists relocation_watchlist_subscriptions_created_idx
  on public.relocation_watchlist_subscriptions (created_at desc);

drop trigger if exists relocation_watchlist_subscriptions_updated_at on public.relocation_watchlist_subscriptions;
create trigger relocation_watchlist_subscriptions_updated_at
before update on public.relocation_watchlist_subscriptions
for each row execute function public.relocation_set_updated_at();
