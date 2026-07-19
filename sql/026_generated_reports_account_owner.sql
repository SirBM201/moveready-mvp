-- Project MoveReady MVP
-- Generated report account ownership fields.
-- Safe to rerun.

alter table public.relocation_generated_reports
  add column if not exists email text,
  add column if not exists phone text,
  add column if not exists full_name text,
  add column if not exists goal text,
  add column if not exists route_category text,
  add column if not exists current_country text,
  add column if not exists target_country text,
  add column if not exists available_funds_amount numeric,
  add column if not exists available_funds_currency text,
  add column if not exists family_members_count integer,
  add column if not exists readiness_score integer,
  add column if not exists readiness_level text,
  add column if not exists source_status text,
  add column if not exists source_confidence text;

do $$
begin
  update public.relocation_generated_reports
  set
    email = coalesce(nullif(email, ''), lower(nullif(input_payload->>'email', ''))),
    phone = coalesce(nullif(phone, ''), nullif(input_payload->>'phone', '')),
    full_name = coalesce(nullif(full_name, ''), nullif(input_payload->>'full_name', ''), nullif(input_payload->>'name', '')),
    goal = coalesce(nullif(goal, ''), nullif(input_payload->>'goal', ''), nullif(input_payload->>'main_goal', ''), nullif(report_payload#>>'{input_summary,goal}', '')),
    route_category = coalesce(nullif(route_category, ''), nullif(input_payload->>'route_category', ''), nullif(report_payload#>>'{input_summary,route_category}', '')),
    current_country = coalesce(nullif(current_country, ''), nullif(input_payload->>'current_country', ''), nullif(report_payload#>>'{input_summary,current_country}', '')),
    target_country = coalesce(nullif(target_country, ''), nullif(input_payload->>'target_country', ''), nullif(report_payload#>>'{input_summary,target_country}', '')),
    available_funds_amount = coalesce(
      available_funds_amount,
      case when nullif(input_payload->>'available_funds_amount', '') ~ '^-?[0-9]+(\.[0-9]+)?$' then (input_payload->>'available_funds_amount')::numeric end,
      case when nullif(report_payload#>>'{input_summary,available_funds_amount}', '') ~ '^-?[0-9]+(\.[0-9]+)?$' then (report_payload#>>'{input_summary,available_funds_amount}')::numeric end
    ),
    available_funds_currency = coalesce(nullif(available_funds_currency, ''), nullif(input_payload->>'available_funds_currency', ''), nullif(report_payload#>>'{input_summary,available_funds_currency}', '')),
    family_members_count = coalesce(
      family_members_count,
      case when nullif(input_payload->>'family_members_count', '') ~ '^-?[0-9]+$' then (input_payload->>'family_members_count')::integer end,
      case when nullif(report_payload#>>'{input_summary,family_members_count}', '') ~ '^-?[0-9]+$' then (report_payload#>>'{input_summary,family_members_count}')::integer end
    ),
    readiness_score = coalesce(
      readiness_score,
      case when nullif(report_payload->>'readiness_score', '') ~ '^-?[0-9]+$' then (report_payload->>'readiness_score')::integer end
    ),
    readiness_level = coalesce(nullif(readiness_level, ''), nullif(report_payload->>'readiness_level', '')),
    source_status = coalesce(nullif(source_status, ''), nullif(report_payload->>'source_status', '')),
    source_confidence = coalesce(nullif(source_confidence, ''), nullif(report_payload->>'source_confidence', ''))
  where input_payload is not null or report_payload is not null;
end $$;

create index if not exists relocation_generated_reports_email_idx
  on public.relocation_generated_reports (email);

create index if not exists relocation_generated_reports_report_ref_idx
  on public.relocation_generated_reports (report_ref);

notify pgrst, 'reload schema';
