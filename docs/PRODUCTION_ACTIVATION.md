# MoveReady Production Activation Runbook

This runbook separates implemented application code from operational items that must be activated manually. A feature must not be described as fully live merely because its route or user interface exists.

## 1. Code already implemented

The repositories contain the following controlled workflows:

- Verified email account sessions and account-owned records
- Country, route, Passport Index, Visa Power, readiness, study, journey, trip, timeline, report, watchlist, and support-request tools
- Commercial quote requests and private account quote history
- Admin-issued quotes with separated service amount, MoveReady platform fee, total, scope, deliverables, exclusions, expiry, provider, and refund terms
- Explicit quote acceptance with current terms version and auditable confirmations
- Checkout gating through `PAYMENT_LINKS_ENABLED`
- Manual verified payment-event recording
- Provider applications and separate public-publication approval
- Privacy, pricing, refund, sensitive-document handling, affiliate-disclosure, and public-listing controls
- Consent-based provider handoffs with an exact shared-field whitelist
- Delivery channel and delivery-reference audit before a handoff can be marked shared
- Private complaints, refund requests, payment disputes, provider issues, privacy issues, service-quality cases, and technical cases
- Protected operations diagnostics and unified admin review queue
- Backend-only Supabase access for private account, provider, quote, payment, handoff, and case tables

## 2. Supabase migrations that must be applied

Run all project migrations in numerical order. For the commercial and execution layer, confirm these three migrations have completed successfully:

1. `023_provider_publication_and_commercial_quotes.sql`
2. `024_private_backend_tables_rls.sql`
3. `025_service_handoffs_and_support_cases.sql`

After applying them, open the protected admin console at `/admin#operations-status` or call:

```text
GET /api/admin/operations/status
X-MoveReady-Admin-Key: <configured admin key>
```

The operations response should show these schema checks as ready:

- `partner_publication`
- `commercial_quotes`
- `payment_events`
- `service_handoffs`
- `handoff_events`
- `support_cases`

Do not use public Supabase browser queries for these records. Migration 024 and migration 025 intentionally revoke `anon` and `authenticated` privileges and create no public RLS policy.

## 3. Railway environment variables

Required base configuration:

```text
SECRET_KEY=<strong production secret>
SUPABASE_URL=<project URL>
SUPABASE_SERVICE_ROLE_KEY=<server-only service role key>
MOVEREADY_ADMIN_API_KEY=<strong admin key>
CORS_ORIGINS=<approved frontend origins only>
```

Commercial rollout:

```text
COMMERCIAL_QUOTES_ENABLED=true
PAYMENT_LINKS_ENABLED=false
```

Keep `PAYMENT_LINKS_ENABLED=false` until all conditions in section 6 pass.

Account email delivery:

```text
EMAIL_OTP_DELIVERY_ENABLED=false
```

Keep it false until an approved email provider, sender domain, templates, bounce handling, rate limits, expiry, abuse controls, and delivery monitoring are configured.

External alerts:

```text
OPPORTUNITY_ALERTS_ENABLED=false
WHATSAPP_ALERTS_ENABLED=false
```

Verified in-app alerts can remain available while external delivery is disabled.

## 4. Provider activation process

A provider application must pass two separate stages.

### Stage A: application screening

Confirm:

- Business identity and contact details
- Relevant licence, accreditation, authorization, agency relationship, permit, insurance authority, notary status, transport authority, or operating evidence
- Service scope and countries covered
- Pricing and extra charges
- Refund, cancellation, complaint, and escalation process
- Privacy and data-retention process
- Sensitive-document handling and secure delivery process
- Website and payment-recipient identity
- Affiliate, commission, or referral relationship

Application status may then become `approved`.

### Stage B: public publication

Application approval alone must not create a public listing. In `/admin#provider-publication`, separately record:

- `privacy_reviewed`
- `pricing_reviewed`
- `refund_policy_reviewed`
- `sensitive_document_handling_reviewed`
- Affiliate disclosure where a relationship exists
- Handoff terms
- Public-safe notes
- Explicit `public_listing_enabled`

The public directory fails closed when these controls or migration 023 are unavailable.

## 5. Commercial quote process

Before issuing a quote, admin must confirm:

- User identity and verified account email
- Exact requested service
- Provider readiness where a provider is involved
- Scope summary
- Deliverables
- Exclusions
- Service amount
- MoveReady platform fee
- Total amount and currency
- Quote expiry
- Refund terms
- Payment provider and checkout URL only when approved

The user must explicitly confirm all quote acceptance statements. Acceptance is not payment.

## 6. Payment-link activation gate

Do not set `PAYMENT_LINKS_ENABLED=true` until every condition below is documented and tested:

- Approved payment provider account
- Verified business and settlement identity
- Approved checkout domains
- Server-side amount and currency matching
- Unique quote and payment references
- Payment-success verification through signed webhook or documented manual verification
- Duplicate-payment protection
- Failed-payment and abandoned-checkout handling
- Refund and partial-refund procedure
- Chargeback and dispute procedure
- Reconciliation process
- Tax, invoice, receipt, and accounting treatment
- Customer-support ownership
- No storage of raw card details
- Production test payment and refund completed

When payment links are enabled, only an accepted, unexpired quote with an approved checkout URL may open checkout.

## 7. Provider handoff process

A handoff can be prepared only when:

- The quote has an auditable acceptance record
- Payment is recorded where the service requires payment
- The provider remains approved and explicitly published
- The quote provider matches the selected provider where assignment already exists
- The proposed fields come from the approved whitelist
- A handoff summary explains the purpose and limits

The user must see:

- Named provider
- Service and purpose
- Every proposed shared field
- Clear statement that unlisted documents and data are not authorized

MoveReady may mark a handoff shared only after:

- The user confirms the current consent version
- The exact field list matches
- Provider identity is acknowledged
- Unlisted-document protection is acknowledged
- Admin records the delivery channel
- Admin records the delivery reference or message/ticket identifier

Passports, bank records, certificates, refusal letters, medical records, and raw documents are not part of the general handoff whitelist.

## 8. Complaint, refund, dispute, and privacy process

The verified user can create a private support case at `/support-center` for:

- General support
- Complaint
- Refund request
- Payment dispute
- Provider issue
- Privacy issue
- Service-quality issue
- Technical issue

Admin should prioritize:

1. Privacy issues
2. Payment disputes
3. Refund requests
4. Critical or high-priority complaints
5. Blocked or disputed provider handoffs

A resolved, rejected, or closed case should contain a clear decision or resolution summary and an assigned owner.

## 9. Release verification

Run from PowerShell:

```powershell
.\scripts\test-billing-release.ps1
.\scripts\test-handoff-release.ps1
.\scripts\test-study-planner-release.ps1
.\scripts\test-trip-planner-release.ps1
.\scripts\test-journey-planner-release.ps1
```

GitHub Actions workflows protect:

- Backend imports and route registration
- Journey, study, trip, Passport Index, and Visa Power behavior
- Billing and provider controls
- Quote acceptance consent contract
- Handoff and support-case privacy and route barriers
- Private-table RLS and privilege revocation

## 10. Launch status language

Use these descriptions accurately:

- **Available:** implemented, deployed, required schema applied, and no external dependency is missing.
- **Controlled rollout:** implemented but limited by credentials, payment setup, provider approval, templates, or operational procedures.
- **Fail closed:** no public or provider action occurs until required controls pass.
- **Partner approval pending:** the self-service or request workflow exists, but no unapproved provider is presented as trusted.

Never describe payment checkout, external alerts, provider execution, or public provider listings as fully active until the corresponding operations checks show ready.
