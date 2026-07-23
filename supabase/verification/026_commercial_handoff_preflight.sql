-- MoveReady migration 026 preflight report
-- Run this before supabase/migrations/026_commercial_and_handoff_invariants.sql
-- when migrations 023 through 025 already contain production or test records.
-- This script changes no data.

select
  'provider_publication_not_ready' as issue,
  id,
  business_name as reference,
  status,
  jsonb_build_object(
    'public_listing_enabled', public_listing_enabled,
    'privacy_reviewed', privacy_reviewed,
    'pricing_reviewed', pricing_reviewed,
    'refund_policy_reviewed', refund_policy_reviewed,
    'sensitive_document_handling_reviewed', sensitive_document_handling_reviewed,
    'affiliate_relationship', affiliate_relationship,
    'affiliate_disclosure_present', nullif(btrim(coalesce(affiliate_disclosure, '')), '') is not null
  ) as details
from public.relocation_partner_applications
where public_listing_enabled = true
  and not (
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

union all

select
  'quote_total_mismatch' as issue,
  id,
  quote_ref as reference,
  status,
  jsonb_build_object(
    'subtotal_amount', subtotal_amount,
    'platform_fee_amount', platform_fee_amount,
    'stored_total_amount', total_amount,
    'expected_total_amount', subtotal_amount + platform_fee_amount
  ) as details
from public.relocation_commercial_quotes
where total_amount <> subtotal_amount + platform_fee_amount

union all

select
  'quote_lifecycle_incomplete' as issue,
  id,
  quote_ref as reference,
  status,
  jsonb_build_object(
    'accepted_at', accepted_at,
    'acceptance_recorded', coalesce(metadata #>> '{quote_acceptance,accepted}', 'false'),
    'paid_at', paid_at,
    'fulfilled_at', fulfilled_at
  ) as details
from public.relocation_commercial_quotes
where
  (
    status in ('accepted', 'payment_pending', 'paid', 'fulfilled', 'refunded', 'disputed')
    and (
      accepted_at is null
      or coalesce(metadata #>> '{quote_acceptance,accepted}', 'false') <> 'true'
    )
  )
  or (status in ('paid', 'fulfilled', 'refunded', 'disputed') and paid_at is null)
  or (status = 'fulfilled' and fulfilled_at is null)

union all

select
  'handoff_consent_incomplete' as issue,
  id,
  handoff_ref as reference,
  status,
  jsonb_build_object(
    'user_consent_confirmed', user_consent_confirmed,
    'consented_at', consented_at,
    'consent_version', consent_version,
    'consent_payload_confirmed', coalesce(consent_payload #>> '{confirmed}', 'false'),
    'shared_field_count', case when jsonb_typeof(shared_fields) = 'array' then jsonb_array_length(shared_fields) else null end
  ) as details
from public.relocation_service_handoffs
where status in ('consent_confirmed', 'ready_to_share', 'shared', 'provider_acknowledged', 'in_progress', 'completed')
  and (
    user_consent_confirmed is not true
    or consented_at is null
    or nullif(btrim(coalesce(consent_version, '')), '') is null
    or coalesce(consent_payload #>> '{confirmed}', 'false') <> 'true'
    or jsonb_typeof(shared_fields) <> 'array'
    or jsonb_array_length(shared_fields) = 0
  )

union all

select
  'handoff_delivery_evidence_incomplete' as issue,
  id,
  handoff_ref as reference,
  status,
  jsonb_build_object(
    'shared_at', shared_at,
    'delivery_channel', delivery_channel,
    'delivery_reference_present', nullif(btrim(coalesce(delivery_reference, '')), '') is not null,
    'completed_at', completed_at
  ) as details
from public.relocation_service_handoffs
where
  (
    status in ('shared', 'provider_acknowledged', 'in_progress', 'completed')
    and (
      shared_at is null
      or nullif(btrim(coalesce(delivery_channel, '')), '') is null
      or nullif(btrim(coalesce(delivery_reference, '')), '') is null
    )
  )
  or (status = 'completed' and completed_at is null)

union all

select
  'support_case_terminal_resolution_missing' as issue,
  id,
  case_ref as reference,
  status,
  jsonb_build_object(
    'case_type', case_type,
    'priority', priority,
    'resolved_at', resolved_at,
    'resolution_summary_present', nullif(btrim(coalesce(resolution_summary, '')), '') is not null
  ) as details
from public.relocation_support_cases
where status in ('resolved', 'rejected', 'closed')
  and (
    resolved_at is null
    or nullif(btrim(coalesce(resolution_summary, '')), '') is null
  )

order by issue, reference;
