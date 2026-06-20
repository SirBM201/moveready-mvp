-- Project MoveReady MVP
-- Generated report ownership and section persistence.
-- Safe to rerun.

create extension if not exists pgcrypto;

alter table public.relocation_generated_reports
  add column if not exists email text,
  add column if not exists phone text,
  add column if not exists readiness_score integer,
  add column if not exists readiness_level text,
  add column if not exists source_status text,
  add column if not exists source_confidence text;

update public.relocation_generated_reports
set
  email = coalesce(nullif(email, ''), lower(nullif(input_payload->>'email', ''))),
  phone = coalesce(nullif(phone, ''), nullif(input_payload->>'phone', '')),
  readiness_score = coalesce(readiness_score, nullif(report_payload->>'readiness_score', '')::integer),
  readiness_level = coalesce(nullif(readiness_level, ''), nullif(report_payload->>'readiness_level', '')),
  source_status = coalesce(nullif(source_status, ''), nullif(report_payload->>'source_status', '')),
  source_confidence = coalesce(nullif(source_confidence, ''), nullif(report_payload->>'source_confidence', ''))
where true;

create index if not exists relocation_generated_reports_email_idx
on public.relocation_generated_reports (email, created_at desc);

create index if not exists relocation_generated_reports_phone_idx
on public.relocation_generated_reports (phone, created_at desc);

create index if not exists relocation_generated_reports_ref_idx
on public.relocation_generated_reports (report_ref);

create or replace function public.relocation_report_fields_before_write()
returns trigger
language plpgsql
as $$
begin
  new.email = lower(coalesce(nullif(new.email, ''), nullif(new.input_payload->>'email', '')));
  new.phone = coalesce(nullif(new.phone, ''), nullif(new.input_payload->>'phone', ''));

  if new.report_payload ? 'readiness_score' then
    new.readiness_score = nullif(new.report_payload->>'readiness_score', '')::integer;
  end if;

  new.readiness_level = coalesce(nullif(new.report_payload->>'readiness_level', ''), new.readiness_level);
  new.source_status = coalesce(nullif(new.report_payload->>'source_status', ''), new.source_status);
  new.source_confidence = coalesce(nullif(new.report_payload->>'source_confidence', ''), new.source_confidence);

  return new;
end;
$$;

drop trigger if exists relocation_generated_reports_fields_before_write
on public.relocation_generated_reports;

create trigger relocation_generated_reports_fields_before_write
before insert or update on public.relocation_generated_reports
for each row execute function public.relocation_report_fields_before_write();

create or replace function public.relocation_sync_report_sections_after_write()
returns trigger
language plpgsql
as $$
declare
  section jsonb;
  section_index integer := 0;
begin
  delete from public.relocation_report_sections where report_id = new.id;

  if jsonb_typeof(new.report_payload->'sections') = 'array' then
    for section in select * from jsonb_array_elements(new.report_payload->'sections')
    loop
      section_index := section_index + 1;
      insert into public.relocation_report_sections (
        report_id,
        section_key,
        section_title,
        section_content,
        section_payload,
        display_order
      ) values (
        new.id,
        coalesce(nullif(section->>'section_key', ''), 'section_' || section_index::text),
        coalesce(nullif(section->>'section_title', ''), nullif(section->>'title', ''), 'Report section'),
        coalesce(section->>'section_content', section->>'body'),
        coalesce(section->'section_payload', '{}'::jsonb),
        section_index * 10
      )
      on conflict (report_id, section_key) do update set
        section_title = excluded.section_title,
        section_content = excluded.section_content,
        section_payload = excluded.section_payload,
        display_order = excluded.display_order;
    end loop;
  end if;

  return new;
end;
$$;

drop trigger if exists relocation_generated_reports_sections_after_write
on public.relocation_generated_reports;

create trigger relocation_generated_reports_sections_after_write
after insert or update on public.relocation_generated_reports
for each row execute function public.relocation_sync_report_sections_after_write();

-- Backfill section rows for reports generated before this migration.
do $$
declare
  report_row record;
begin
  for report_row in
    select id, report_payload from public.relocation_generated_reports
  loop
    perform public.relocation_sync_report_sections_after_write() from (select report_row.id, report_row.report_payload) as dummy;
  end loop;
exception
  when others then
    -- If the direct trigger-function backfill cannot run in a specific Postgres version,
    -- the trigger still handles all new report writes after this migration.
    null;
end $$;

-- Explicit backfill that is independent of trigger context.
do $$
declare
  report_row record;
  section jsonb;
  section_index integer;
begin
  for report_row in
    select id, report_payload from public.relocation_generated_reports
    where jsonb_typeof(report_payload->'sections') = 'array'
  loop
    delete from public.relocation_report_sections where report_id = report_row.id;
    section_index := 0;
    for section in select * from jsonb_array_elements(report_row.report_payload->'sections')
    loop
      section_index := section_index + 1;
      insert into public.relocation_report_sections (
        report_id,
        section_key,
        section_title,
        section_content,
        section_payload,
        display_order
      ) values (
        report_row.id,
        coalesce(nullif(section->>'section_key', ''), 'section_' || section_index::text),
        coalesce(nullif(section->>'section_title', ''), nullif(section->>'title', ''), 'Report section'),
        coalesce(section->>'section_content', section->>'body'),
        coalesce(section->'section_payload', '{}'::jsonb),
        section_index * 10
      )
      on conflict (report_id, section_key) do update set
        section_title = excluded.section_title,
        section_content = excluded.section_content,
        section_payload = excluded.section_payload,
        display_order = excluded.display_order;
    end loop;
  end loop;
end $$;

notify pgrst, 'reload schema';
