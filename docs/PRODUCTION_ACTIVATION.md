# MoveReady Production Activation Runbook

This runbook separates implemented application code from operational items that must be activated manually. A feature must not be described as fully live merely because its route or user interface exists.

## 1. Code already implemented

The repositories contain the following controlled workflows:

- Verified email OTP account sessions and account-owned records
- Database-backed OTP resend cooldown, per-email limits, per-IP limits, code expiry, attempt limits, and active-session limits
- Resend and SMTP email adapters with provider-readiness checks
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
- Explicit handoff lifecycle transition rules that prevent admin bypass of user consent or delivery evidence
- Private complaints, refund requests, payment disputes, provider issues, privacy issues, service-quality cases, and technical cases
- Terminal case resolution rules requiring a written resolution and timestamp
- Protected operations diagnostics and unified admin review queue
- Backend-only Supabase access for private account, provider, quote, payment, handoff, and case tables

## 2. Supabase migrations that must be applied

Run all project migrations in numerical order. For the commercial and provider-execution layer, confirm these four migrations have completed successfully:

1. `023_provider_publication_and_commercial_quotes.sql`
2. `024_private_backend_tables_rls.sql`
3. `025_service_handoffs_and_support_cases.sql`
4. `026_commercial_and_handoff_invariants.sql`

Before applying migration 026 to a database that already contains commercial or handoff records, run:

```text
supabase/verification/026_commercial_handoff_preflight.sql
```

The preflight should return zero unsafe records. Repair any returned provider, quote, handoff, or case record before applying migration 026.

After applying the migrations, open the protected admin console at `/admin#operations-status` or call:

```text
GET /api/admin/operations/status
X-MoveReady-Admin-Key: <configured admin key>
```

The operations response should show these schema checks as ready:

- `profiles`
- `auth_login_codes`
- `user_sessions`
- `reports`
- `readiness_runs`
- `partner_publication`
- `commercial_quotes`
- `payment_events`
- `service_handoffs`
- `handoff_events`
- `support_cases`

Do not use public Supabase browser queries for these records. Migrations 024 and 025 intentionally revoke `anon` and `authenticated` privileges and create no public RLS policy.

## 3. Railway base environment variables

Required base configuration:

```text
ENV_MODE=production
FLASK_ENV=production
SECRET_KEY=<strong production secret>
SUPABASE_URL=<project URL>
SUPABASE_SERVICE_ROLE_KEY=<server-only service role key>
MOVEREADY_ADMIN_API_KEY=<strong admin key>
CORS_ORIGINS=https://sir-bm-201-moveready-frontend.vercel.app
AUTH_OTP_DEV_MODE=false
```

Do not place `SUPABASE_SERVICE_ROLE_KEY`, `SECRET_KEY`, the admin key, email-provider credentials, payment credentials, or API keys in Vercel public variables, browser code, screenshots, support cases, or chat.

Commercial rollout:

```text
COMMERCIAL_QUOTES_ENABLED=true
PAYMENT_LINKS_ENABLED=false
```

Keep `PAYMENT_LINKS_ENABLED=false` until all conditions in section 7 pass.

External alerts:

```text
OPPORTUNITY_ALERTS_ENABLED=false
WHATSAPP_ALERTS_ENABLED=false
```

Verified in-app alerts can remain available while external delivery is disabled.

## 4. OTP email activation

Public login must remain unavailable until an approved sender and provider are verified. The frontend reads `/api/auth/health` and disables code requests when the backend reports that delivery is not configured.

### Option A: Resend

Set these Railway variables:

```text
EMAIL_OTP_DELIVERY_ENABLED=true
EMAIL_OTP_PROVIDER=resend
RESEND_API_KEY=<server-only Resend API key>
EMAIL_OTP_FROM=MoveReady <login@your-verified-domain.com>
EMAIL_OTP_REPLY_TO=support@your-verified-domain.com
EMAIL_OTP_LOGIN_URL=https://sir-bm-201-moveready-frontend.vercel.app/login
EMAIL_OTP_APP_NAME=MoveReady
AUTH_OTP_DEV_MODE=false
```

The sender domain must be verified inside the Resend account before public testing.

### Option B: SMTP

Set these Railway variables:

```text
EMAIL_OTP_DELIVERY_ENABLED=true
EMAIL_OTP_PROVIDER=smtp
SMTP_HOST=<approved SMTP host>
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USE_SSL=false
SMTP_USERNAME=<SMTP username, when required>
SMTP_PASSWORD=<server-only SMTP password, when required>
EMAIL_OTP_FROM=MoveReady <login@your-verified-domain.com>
EMAIL_OTP_REPLY_TO=support@your-verified-domain.com
EMAIL_OTP_LOGIN_URL=https://sir-bm-201-moveready-frontend.vercel.app/login
EMAIL_OTP_APP_NAME=MoveReady
AUTH_OTP_DEV_MODE=false
```

Use either TLS or SSL according to the provider. Do not enable both unless the provider explicitly requires that configuration.

### OTP security variables

The defaults are conservative, but they may be set explicitly in Railway:

```text
AUTH_OTP_EXPIRES_MINUTES=10
AUTH_MAX_CODE_ATTEMPTS=5
AUTH_SESSION_DAYS=30
AUTH_MAX_ACTIVE_SESSIONS_PER_EMAIL=10
AUTH_OTP_REQUEST_COOLDOWN_SECONDS=60
AUTH_OTP_REQUEST_WINDOW_MINUTES=15
AUTH_OTP_MAX_REQUESTS_PER_EMAIL_WINDOW=5
AUTH_OTP_MAX_REQUESTS_PER_IP_WINDOW=20
AUTH_OTP_RECENT_SCAN_LIMIT=300
```

Production requirements:

- `AUTH_OTP_DEV_MODE=false`
- No OTP value in production API responses
- Verified sender domain
- Bounce and complaint monitoring
- Delivery logs that do not contain OTP values
- Staff must never ask users to send OTP codes
- One live inbox delivery test after deployment
- Rate-limit responses must return HTTP 429 rather than issuing unlimited codes

To keep account login in controlled rollout, use:

```text
EMAIL_OTP_DELIVERY_ENABLED=false
AUTH_OTP_DEV_MODE=false
```

## 5. Provider activation process

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

Migration 026 also prevents a provider from remaining publicly enabled when these conditions are not satisfied.

The public directory fails closed when publication controls or migration 023 are unavailable.

## 6. Commercial quote process

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

Migration 026 requires:

- `total_amount = subtotal_amount + platform_fee_amount`
- Auditable quote acceptance before accepted or later states
- `accepted_at` before accepted or later states
- `paid_at` before paid or later states
- `fulfilled_at` before fulfilled status

## 7. Payment-link activation gate

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

## 8. Provider handoff process

The verified-account frontend uses:

```text
/api/handoffs
```

The backend also retains this compatibility alias:

```text
/api/service-handoffs
```

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

Admin cannot directly set `consent_confirmed` or `shared`. Those states require the dedicated user-consent and mark-shared endpoints. Later states require existing consent and delivery evidence.

Passports, bank records, certificates, refusal letters, medical records, and raw documents are not part of the general handoff whitelist.

## 9. Complaint, refund, dispute, and privacy process

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

A resolved, rejected, or closed case must contain:

- A clear decision or resolution summary
- A resolution timestamp
- An assigned operational owner where applicable

The API validates the written resolution before submitting a terminal update, and migration 026 enforces it at database level.

## 10. Release verification

Run from Windows PowerShell in the backend repository:

```powershell
.\scripts\test-auth-release.ps1
.\scripts\test-billing-release.ps1
.\scripts\test-handoff-release.ps1
.\scripts\test-study-planner-release.ps1
.\scripts\test-trip-planner-release.ps1
.\scripts\test-journey-planner-release.ps1
```

After OTP provider configuration, require readiness and send one real code to an inbox you control:

```powershell
.\scripts\test-auth-release.ps1 -RequireReady -TestEmail "your-test-inbox@example.com"
```

Do not paste the received OTP into chat, GitHub, Railway logs, screenshots, or support tickets.

Run protected schema diagnostics without exposing the admin key in chat:

```powershell
$AdminKey = Read-Host "Enter MoveReady admin key"
.\scripts\test-operations-admin.ps1 -AdminKey $AdminKey
```

GitHub Actions workflows protect:

- Backend imports and route registration
- Account login provider readiness and request barriers
- OTP cooldown and development-code gating
- Handoff URL compatibility and safety-handler registration
- Journey, study, trip, Passport Index, and Visa Power behavior
- Billing and provider controls
- Quote acceptance consent contract
- Handoff and support-case privacy and route barriers
- API transition rules and database trust invariants
- Private-table RLS and privilege revocation
- Frontend production compilation

## 11. Launch status language

Use these descriptions accurately:

- **Available:** implemented, deployed, required schema applied, and no external dependency is missing.
- **Controlled rollout:** implemented but limited by credentials, payment setup, provider approval, templates, or operational procedures.
- **Fail closed:** no public or provider action occurs until required controls pass.
- **Partner approval pending:** the self-service or request workflow exists, but no unapproved provider is presented as trusted.

Never describe email OTP, payment checkout, external alerts, provider execution, or public provider listings as fully active until the corresponding operations checks show ready and a real production test has passed.
