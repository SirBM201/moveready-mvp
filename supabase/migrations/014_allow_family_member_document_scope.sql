-- Project MoveReady MVP
-- Allow generic family-member document scope for routes where spouse/child split is not enough.
-- Run after 001_initial_relocation_schema.sql.

alter table public.relocation_document_requirements
  drop constraint if exists relocation_document_requirements_applies_to_check;

alter table public.relocation_document_requirements
  add constraint relocation_document_requirements_applies_to_check
  check (
    applies_to is null
    or applies_to in (
      'main_applicant',
      'spouse',
      'child',
      'family_member',
      'sponsor',
      'employer',
      'school',
      'other'
    )
  );
