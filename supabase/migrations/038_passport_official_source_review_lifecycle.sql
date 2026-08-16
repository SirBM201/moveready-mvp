-- MoveReady Stage 2F.5D.3
-- Controlled review lifecycle for Passport Index official-source mappings.
--
-- Goals:
-- * keep pending/unreviewed mappings fail-closed;
-- * record every review decision in an immutable audit trail;
-- * require reviewer identity and evidence notes for verification;
-- * automatically expire verified mappings into needs_review when due.

create table if not exists public.relocation_passport_official_source_reviews (
  id uuid primary key default gen_random_uuid(),
  mapping_id uuid not null references public.relocation_passport_official_source_mappings(id) on delete cascade,
  previous_verification_status text not null
    check (previous_verification_status in ('pending_review','verified','needs_review','retired')),
  decision text not null
    check (decision in ('verified','needs_review','retired')),
  reviewer text not null check (length(trim(reviewer)) between 2 and 200),
  evidence_note text not null check (length(trim(evidence_note)) between 10 and 4000),
  reviewed_source_url text not null check (reviewed_source_url ~ '^https://'),
  reviewed_at timestamptz not null default now(),
  next_review_due_at timestamptz,
  created_at timestamptz not null default now()
);

create index if not exists relocation_passport_official_source_reviews_mapping_idx
  on public.relocation_passport_official_source_reviews(mapping_id, reviewed_at desc);

alter table public.relocation_passport_official_source_reviews enable row level security;
revoke all on table public.relocation_passport_official_source_reviews from anon, authenticated;

create or replace function public.relocation_review_passport_official_source_mapping(
  p_mapping_id uuid,
  p_decision text,
  p_reviewer text,
  p_evidence_note text,
  p_reviewed_source_url text,
  p_review_interval_days integer default 90
)
returns public.relocation_passport_official_source_mappings
language plpgsql
security definer
set search_path = public
as $$
declare
  current_mapping public.relocation_passport_official_source_mappings%rowtype;
  source_record public.relocation_trusted_sources%rowtype;
  next_due timestamptz;
begin
  if p_decision not in ('verified','needs_review','retired') then
    raise exception 'Invalid review decision: %', p_decision;
  end if;
  if length(trim(coalesce(p_reviewer,''))) < 2 then
    raise exception 'Reviewer identity is required';
  end if;
  if length(trim(coalesce(p_evidence_note,''))) < 10 then
    raise exception 'Evidence note must contain at least 10 characters';
  end if;
  if coalesce(p_reviewed_source_url,'') !~ '^https://' then
    raise exception 'Reviewed source URL must use HTTPS';
  end if;
  if p_review_interval_days < 1 or p_review_interval_days > 365 then
    raise exception 'Review interval must be between 1 and 365 days';
  end if;

  select * into current_mapping
  from public.relocation_passport_official_source_mappings
  where id = p_mapping_id
  for update;
  if not found then
    raise exception 'Passport official-source mapping not found';
  end if;

  select * into source_record
  from public.relocation_trusted_sources
  where id = current_mapping.source_id;
  if not found or source_record.source_type not in ('government','embassy') or source_record.status = 'retired' then
    raise exception 'Mapping cannot be verified because its trusted source is not an active government/embassy authority';
  end if;
  if source_record.source_url is distinct from p_reviewed_source_url then
    raise exception 'Reviewed source URL does not match the mapped trusted source';
  end if;

  next_due := case when p_decision = 'verified' then now() + make_interval(days => p_review_interval_days) else null end;

  insert into public.relocation_passport_official_source_reviews
    (mapping_id, previous_verification_status, decision, reviewer, evidence_note,
     reviewed_source_url, reviewed_at, next_review_due_at)
  values
    (current_mapping.id, current_mapping.verification_status, p_decision, trim(p_reviewer),
     trim(p_evidence_note), p_reviewed_source_url, now(), next_due);

  update public.relocation_passport_official_source_mappings
  set verification_status = p_decision,
      status = case when p_decision = 'retired' then 'retired'
                    when p_decision = 'needs_review' then 'needs_review'
                    else 'active' end,
      verified_at = case when p_decision = 'verified' then now() else null end,
      review_due_at = next_due,
      notes = concat_ws(E'\n', nullif(notes,''),
        'Last controlled review: ' || now()::date || ' by ' || trim(p_reviewer) || '. ' || trim(p_evidence_note)),
      updated_at = now()
  where id = current_mapping.id
  returning * into current_mapping;

  return current_mapping;
end;
$$;

revoke all on function public.relocation_review_passport_official_source_mapping(uuid,text,text,text,text,integer) from public, anon, authenticated;

create or replace function public.relocation_expire_passport_official_source_reviews()
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  changed integer;
begin
  update public.relocation_passport_official_source_mappings
  set verification_status = 'needs_review',
      status = 'needs_review',
      verified_at = null,
      updated_at = now()
  where verification_status = 'verified'
    and review_due_at is not null
    and review_due_at <= now();
  get diagnostics changed = row_count;
  return changed;
end;
$$;

revoke all on function public.relocation_expire_passport_official_source_reviews() from public, anon, authenticated;

comment on table public.relocation_passport_official_source_reviews is
  'Immutable backend-only audit trail for controlled Passport Index government/embassy source review decisions.';
comment on function public.relocation_review_passport_official_source_mapping(uuid,text,text,text,text,integer) is
  'Service-role controlled transition for official-source mappings. Verification requires reviewer identity, evidence note, and exact mapped HTTPS authority URL.';
