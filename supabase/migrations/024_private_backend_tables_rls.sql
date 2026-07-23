-- Project MoveReady MVP
-- Catch-up privacy hardening for backend-managed tables created after the
-- initial schema. Run after migration 023.
-- Safe to rerun and safe when an optional table has not yet been created.
--
-- MoveReady authenticates users in Flask and accesses Supabase with the service
-- role. These tables must therefore have no direct anon/authenticated access and
-- no public RLS policies. Public-safe output is returned only by backend routes.

create extension if not exists pgcrypto;

do $$
declare
  table_name text;
  private_tables text[] := array[
    'relocation_users',
    'relocation_user_profiles',
    'relocation_user_saved_routes',
    'relocation_user_alerts',
    'relocation_service_interest_requests',
    'relocation_readiness_check_runs',
    'relocation_watchlist_subscriptions',
    'relocation_saved_routes',
    'relocation_saved_route_reports',
    'relocation_timeline_events',
    'relocation_partner_applications',
    'relocation_auth_login_codes',
    'relocation_user_sessions',
    'relocation_generated_reports',
    'relocation_report_sections',
    'relocation_admin_review_tasks',
    'relocation_source_snapshots',
    'relocation_source_change_alerts',
    'relocation_ai_answer_cache',
    'relocation_commercial_quotes',
    'relocation_payment_events'
  ];
begin
  foreach table_name in array private_tables
  loop
    if to_regclass(format('public.%I', table_name)) is not null then
      execute format('alter table public.%I enable row level security', table_name);
      execute format('revoke all privileges on table public.%I from public, anon, authenticated', table_name);
      execute format('grant all privileges on table public.%I to service_role', table_name);
    end if;
  end loop;

  if to_regclass('public.relocation_auth_login_codes') is not null then
    comment on table public.relocation_auth_login_codes is 'Private backend-only OTP records. Codes are hashed and direct public API access is revoked.';
  end if;

  if to_regclass('public.relocation_user_sessions') is not null then
    comment on table public.relocation_user_sessions is 'Private backend-only account session records. Session tokens are hashed and direct public API access is revoked.';
  end if;

  if to_regclass('public.relocation_commercial_quotes') is not null then
    comment on table public.relocation_commercial_quotes is 'Private verified-account commercial quotes accessed only through Flask account and admin routes.';
  end if;

  if to_regclass('public.relocation_payment_events') is not null then
    comment on table public.relocation_payment_events is 'Private payment and commercial audit events accessed only through protected backend routes.';
  end if;
end $$;

notify pgrst, 'reload schema';