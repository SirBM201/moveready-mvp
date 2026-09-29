-- Supabase Data API explicit-grant compatibility
-- Supabase will stop auto-granting Data API privileges to newly created
-- public-schema objects on existing projects on 2026-10-30.
--
-- The launch-beta API reads reports and inserts new reports. It has no
-- update or delete path; keep the backend grant limited to those operations.

alter table if exists public.relocation_launch_beta_reports enable row level security;
revoke all privileges on table public.relocation_launch_beta_reports
  from public, anon, authenticated, service_role;
grant select, insert on table public.relocation_launch_beta_reports
  to service_role;

comment on table public.relocation_launch_beta_reports is
  'Private verified-account LQ12 beta observations. Explicit Data API service-role grant retained for Supabase 2026-10-30 compatibility.';
