# MR Billing 01 — Billing Foundation & Entitlements

## Decision
MoveReady owns commercial access state. Payment providers do not own product authorization.

Flow:

`provider -> verified event -> billing state -> entitlement -> feature access`

## Provider boundary
The core schema is provider-independent. Paystack is the intended MoveReady V1 adapter, but provider-specific customer, subscription, payment and event identifiers are isolated behind `provider` fields/mapping tables so a future Paddle or other adapter does not require a product rewrite.

## Tables
- `billing_products`
- `billing_plans`
- `billing_prices`
- `billing_customers`
- `billing_provider_customers`
- `billing_subscriptions`
- `billing_payments`
- `billing_provider_events`
- `billing_entitlements`
- `billing_audit_logs`

## Security invariants
1. Browser clients never grant themselves entitlements.
2. A redirect/callback URL never proves payment.
3. Provider events must be signature-verified before commercial state changes.
4. Provider event IDs and payment references are unique/idempotent.
5. Feature access reads MoveReady entitlement state, not Paystack directly.
6. Failed, cancelled and expired subscription states must be representable without deleting history.
7. Paid plan names and prices are not seeded until commercial limits/pricing are approved.

## Migration
Apply `supabase/migrations/033_billing_core_and_entitlements.sql` after the existing numbered migrations.

## Next batch
MR Billing 02 will add the Paystack adapter, verified webhook ingestion, transaction initialization/verification, and idempotent synchronization into these tables. Secrets must remain deployment environment variables and must never be committed.
