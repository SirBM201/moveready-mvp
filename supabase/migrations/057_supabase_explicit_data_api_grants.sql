-- Supabase Data API explicit-grant compatibility
-- Supabase will stop auto-granting Data API privileges to newly created
-- public-schema objects on existing projects on 2026-10-30.
--
-- MoveReady's recent private/backend migrations already use the desired pattern:
-- RLS + browser-role revocation + explicit service_role grants.
-- This migration documents and enforces that contract for the current
-- launch-beta table without changing anon/authenticated access.

alter table if exists public.relocation_launch_beta_reports enable row level security;
revoke all privileges on table public.relocation_launch_beta_reports
  from public, anon, authenticated;
grant select, insert, update, delete on table public.relocation_launch_beta_reports
  to service_role;

comment on table public.relocation_launch_beta_reports is
  'Private verified-account LQ12 beta observations. Explicit Data API service-role grant retained for Supabase 2026-10-30 compatibility.';
