-- Project MoveReady MVP
-- Database-level trust invariants for provider publication, quotes, handoffs,
-- and support-case resolution.
-- Run after migration 025.
-- Safe to rerun.

-- Public providers must remain approved and pass every publication control.
alter table public.relocation_partner_applications
  drop constraint if exists relocation_partner_publication_ready_check;

alter table public.relocation_partner_applications
  add constraint relocation_partner_publication_ready_check
  check (
    public_listing_enabled = false
    or (
      status = 'approved'
      and privacy_reviewed = true
      and pricing_reviewed = true
      and refund_policy_reviewed = true
      and sensitive_document_handling_reviewed = true
      and (
        affiliate_relationship = false
        or nullif(btrim(coalesce(affiliate_disclosure, '')), '') is not null
      )
    )
  );

-- Quote arithmetic must be exact and lifecycle states must have their audit
-- timestamps or acceptance record.
alter table public.relocation_commercial_quotes
  drop constraint if exists relocation_commercial_quotes_total_check;

alter table public.relocation_commercial_quotes
  add constraint relocation_commercial_quotes_total_check
  check (total_amount = subtotal_amount + platform_fee_amount);

alter table public.relocation_commercial_quotes
  drop constraint if exists relocation_commercial_quotes_lifecycle_check;

alter table public.relocation_commercial_quotes
  add constraint relocation_commercial_quotes_lifecycle_check
  check (
    (status not in ('accepted', 'payment_pending', 'paid', 'fulfilled', 'refunded', 'disputed') or accepted_at is not null)
    and (
      status not in ('accepted', 'payment_pending', 'paid', 'fulfilled', 'refunded', 'disputed')
      or coalesce((metadata -> 'quote_acceptance' ->> 'accepted')::boolean, false) = true
    )
    and (status not in ('paid', 'fulfilled', 'refunded', 'disputed') or paid_at is not null)
    and (status <> 'fulfilled' or fulfilled_at is not null)
  );

-- Any state at or beyond sharing requires exact user consent and delivery
-- evidence. Completion also requires a completion timestamp.
alter table public.relocation_service_handoffs
  drop constraint if exists relocation_service_handoffs_consent_delivery_check;

alter table public.relocation_service_handoffs
  add constraint relocation_service_handoffs_consent_delivery_check
  check (
    status not in ('consent_confirmed', 'ready_to_share', 'shared', 'provider_acknowledged', 'in_progress', 'completed')
    or (
      user_consent_confirmed = true
      and consented_at is not null
      and nullif(btrim(coalesce(consent_version, '')), '') is not null
      and coalesce((consent_payload ->> 'confirmed')::boolean, false) = true
      and jsonb_typeof(shared_fields) = 'array'
      and jsonb_array_length(shared_fields) > 0
    )
  );

alter table public.relocation_service_handoffs
  drop constraint if exists relocation_service_handoffs_shared_evidence_check;

alter table public.relocation_service_handoffs
  add constraint relocation_service_handoffs_shared_evidence_check
  check (
    status not in ('shared', 'provider_acknowledged', 'in_progress', 'completed')
    or (
      shared_at is not null
      and nullif(btrim(coalesce(delivery_channel, '')), '') is not null
      and nullif(btrim(coalesce(delivery_reference, '')), '') is not null
    )
  );

alter table public.relocation_service_handoffs
  drop constraint if exists relocation_service_handoffs_completion_check;

alter table public.relocation_service_handoffs
  add constraint relocation_service_handoffs_completion_check
  check (status <> 'completed' or completed_at is not null);

-- Terminal support-case decisions require a written resolution and timestamp.
alter table public.relocation_support_cases
  drop constraint if exists relocation_support_cases_resolution_check;

alter table public.relocation_support_cases
  add constraint relocation_support_cases_resolution_check
  check (
    status not in ('resolved', 'rejected', 'closed')
    or (
      resolved_at is not null
      and nullif(btrim(coalesce(resolution_summary, '')), '') is not null
    )
  );

comment on constraint relocation_partner_publication_ready_check on public.relocation_partner_applications is 'Prevents public listing unless approval, privacy, pricing, refund, handling, and affiliate-disclosure controls pass.';
comment on constraint relocation_commercial_quotes_total_check on public.relocation_commercial_quotes is 'Ensures total amount equals service subtotal plus MoveReady platform fee.';
comment on constraint relocation_commercial_quotes_lifecycle_check on public.relocation_commercial_quotes is 'Requires auditable acceptance and lifecycle timestamps before accepted, paid, fulfilled, refunded, or disputed states.';
comment on constraint relocation_service_handoffs_consent_delivery_check on public.relocation_service_handoffs is 'Prevents consent-confirmed or later states without exact-field user consent.';
comment on constraint relocation_service_handoffs_shared_evidence_check on public.relocation_service_handoffs is 'Prevents shared or later states without a delivery channel and reference.';
comment on constraint relocation_support_cases_resolution_check on public.relocation_support_cases is 'Requires a written resolution and timestamp before a case is resolved, rejected, or closed.';

notify pgrst, 'reload schema';