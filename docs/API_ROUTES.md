# MoveReady MVP API Routes

Base prefix: `/api`

## Public

- `GET /health`
- `GET /api/health`
- `GET /api/relocation/countries`
- `GET /api/relocation/routes`
- `GET /api/relocation/routes/<route_id>`
- `GET /api/relocation/routes/by-code/<country_code>/<route_code>`
- `GET /api/opportunities`
- `GET /api/opportunities/<opportunity_code>`
- `GET /api/watchlist/options`
- `POST /api/watchlist/subscriptions`
- `PATCH /api/watchlist/subscriptions/<subscription_id>`
- `POST /api/profiles`
- `GET /api/profiles`
- `PATCH /api/profiles/<profile_id>`
- `GET /api/reports`
- `GET /api/reports/<report_ref>`
- `POST /api/readiness/name-consistency`
- `POST /api/readiness/document-readiness`
- `POST /api/readiness/funds-plan`
- `POST /api/readiness/refusal-risk`
- `POST /api/relocation/checklist`
- `POST /api/relocation/budget-estimate`
- `GET /api/relocation/scholarships`
- `GET /api/relocation/insurance-requirements`
- `POST /api/relocation/reports`

## Route Detail By Code

`GET /api/relocation/routes/by-code/EE/startup-founder`

Returns the public route, active route version summary, route facts, document requirements, budget items, insurance requirements, risk level, source confidence, verified date, and review due date.

This is useful for stable frontend pages because the page can use country and route codes instead of database UUIDs.

## Official Opportunities

`GET /api/opportunities`

Returns official lottery, ballot, invitation-pool, annual-quota, country-cap, first-come quota, and seasonal-intake opportunities.

Optional query params:

- `country_code=US`
- `type=ballot`
- `status=open`
- `q=dv`

`GET /api/opportunities/US-DV`

Returns one opportunity record by stable opportunity code.

The endpoint uses `relocation_opportunities` after migration `005_official_opportunities.sql`. If the table is not present yet, it returns conservative starter fallback records so the frontend does not break during deployment.

## Watchlist And Alerts

`GET /api/watchlist/options`

Returns allowed watch types, preferred channels, and alert event types for the public watchlist form.

`POST /api/watchlist/subscriptions`

Stores an opt-in watchlist subscription after migration `007_watchlist_alert_subscriptions.sql` is run.

Starter body:

```json
{
  "watch_type": "opportunity",
  "watch_code": "US-DV",
  "watch_title": "USA Diversity Visa Program",
  "full_name": "Example User",
  "email": "user@example.com",
  "phone": "+96500000000",
  "preferred_channel": "whatsapp",
  "current_country": "Kuwait",
  "target_country": "United States",
  "route_or_goal": "DV lottery alert",
  "alert_types": ["opens", "closing_soon", "eligibility_change"],
  "consent_to_contact": true,
  "source_page": "/watchlist"
}
```

Rules:

- `watch_type` must be one of `route`, `opportunity`, `scholarship`, `country`, or `service`.
- `preferred_channel` must be one of `email`, `whatsapp`, `telegram`, `phone`, or `in_app`.
- Either `email` or `phone` is required.
- `consent_to_contact` must be `true`.

`PATCH /api/watchlist/subscriptions/<subscription_id>`

Allows a user-facing unsubscribe/pause flow later. The request must include the subscription email or phone so the backend can avoid changing the wrong record.

Starter body:

```json
{
  "status": "paused",
  "email": "user@example.com"
}
```

Allowed statuses:

```text
active
paused
unsubscribed
closed
spam
```

The watchlist currently stores consent and preferences. Actual WhatsApp, Telegram, email, or in-app message delivery should only be enabled after provider setup, opt-in flow, and audit logging are approved.

## User Profiles

`POST /api/profiles`

Stores a user's relocation profile after migration `008_user_relocation_profiles.sql` is run. The backend also computes a starter readiness snapshot.

Starter body:

```json
{
  "full_name": "Example User",
  "email": "user@example.com",
  "phone": "+96500000000",
  "current_country": "Kuwait",
  "nationality": "Nigeria",
  "residence_country": "Kuwait",
  "target_country": "Estonia",
  "target_city": "Tallinn",
  "main_goal": "startup",
  "route_category": "startup",
  "timeline_months": 6,
  "family_members_count": 0,
  "available_funds_amount": 12000,
  "available_funds_currency": "EUR",
  "education_level": "Bachelor",
  "work_experience_years": 5,
  "business_stage": "mvp_or_early_traction",
  "has_previous_refusal": false,
  "preferred_contact_channel": "whatsapp",
  "consent_to_contact": true,
  "source_page": "/dashboard"
}
```

Rules:

- Either `email` or `phone` is required.
- `consent_to_contact` must be `true`.
- `main_goal` must be one of `study`, `scholarship`, `work`, `startup`, `business`, `digital_nomad`, `family`, `visit`, `opportunity`, or `relocation`.
- `preferred_contact_channel` must be one of `email`, `whatsapp`, `telegram`, or `phone`.

`GET /api/profiles?email=user@example.com`

Returns the newest matching profile by email.

`GET /api/profiles?phone=+96500000000`

Returns the newest matching profile by phone.

`PATCH /api/profiles/<profile_id>`

Public status update for a user-controlled profile. The request must include the matching email or phone. Public updates are limited to `active` and `closed`.

```json
{
  "status": "closed",
  "email": "user@example.com"
}
```

## Saved Reports

`GET /api/reports?report_ref=MRR-20260618-ABC123`

Returns saved generated reports matching the report reference.

`GET /api/reports?email=user@example.com`

Returns saved generated reports whose original input payload contains that email.

`GET /api/reports?phone=+96500000000`

Returns saved generated reports whose original input payload contains that phone number.

`GET /api/reports/<report_ref>`

Returns one saved report by report reference.

The public lookup does not list every generated report. A lookup value is required to avoid exposing unrelated user reports.

## Readiness Tools

These endpoints are live helper tools for pre-application checks. They return results even without new SQL. After migration `006_readiness_check_runs.sql` is run, each check can also save to `relocation_readiness_check_runs` and return `stored: true`.

### Name Consistency

`POST /api/readiness/name-consistency`

```json
{
  "records": [
    { "label": "Passport", "name": "Ada Chika Okafor" },
    { "label": "Certificate", "name": "Ada C. Okafor" },
    { "label": "Bank statement", "name": "Ada Chika Okafor" }
  ],
  "source_page": "/readiness"
}
```

Returns token-level mismatch warnings and an overall consistency status.

### Document Readiness

`POST /api/readiness/document-readiness`

```json
{
  "route_category": "startup",
  "documents": ["passport", "proof of funds", "business plan"],
  "source_page": "/readiness"
}
```

Returns required/recommended documents, missing items, present items, and readiness status.

### Proof of Funds

`POST /api/readiness/funds-plan`

```json
{
  "available_funds_amount": 12000,
  "required_funds_amount": 15000,
  "target_timeline_months": 6,
  "family_members_count": 0,
  "currency": "EUR",
  "recent_large_deposits": true,
  "source_page": "/readiness"
}
```

Returns adjusted funds target, shortfall, monthly savings target, and evidence warnings.

### Refusal Risk

`POST /api/readiness/refusal-risk`

```json
{
  "indicators": {
    "previous_refusal": true,
    "low_funds": false,
    "unclear_purpose": true,
    "weak_home_ties": false,
    "incomplete_documents": true
  },
  "source_page": "/readiness"
}
```

Returns an honest risk level, flagged issues, and a repair plan. It does not predict approval.

## Platform Services

Service endpoints return public-safe availability labels: `Available`, `Coming soon`, or `Partner approval pending`.

- `GET /api/platform/status`
- `GET /api/platform/modules`
- `GET /api/platform/modules/<slug>`
- `POST /api/platform/service-interest`

Service endpoints:

- `GET /api/watchlist`
- `GET /api/alerts`
- `GET /api/documents`
- `GET /api/funds`
- `GET /api/refusal-risk`
- `GET /api/courier`
- `GET /api/legalization`
- `GET /api/insurance`
- `GET /api/appointments`
- `GET /api/family-relocation`
- `GET /api/settlement`
- `GET /api/partners`

Expected availability response shape:

```json
{
  "ok": true,
  "availability": "coming_soon",
  "message": "This service is available now or being prepared for public access, depending on its status label."
}
```

Use feature flags to switch partner-dependent modules on only after their database models, provider integrations, opt-in workflows, and compliance rules are ready.

### Service Interest

`POST /api/platform/service-interest`

Stores a visitor request for a service such as alerts, courier, insurance, legalization, documents, funds, refusal risk, or partner review.

Requires migration `supabase/migrations/004_service_interest_requests.sql`.

Starter body:

```json
{
  "service_slug": "courier",
  "service_title": "Passport and document courier",
  "full_name": "Example User",
  "email": "user@example.com",
  "phone": "+96500000000",
  "preferred_channel": "whatsapp",
  "current_country": "Kuwait",
  "target_country": "Estonia",
  "route_or_goal": "Estonia startup route",
  "message": "I need passport and document courier updates.",
  "consent_to_contact": true,
  "source_page": "/platform/courier"
}
```

The endpoint requires either `email` or `phone`, and `consent_to_contact` must be `true`.

## Admin

Admin routes require one of these headers:

- `X-MoveReady-Admin-Key`
- `X-Relocation-Admin-Key`
- `X-Admin-Key`

Routes:

- `GET /api/admin/status`
- `GET /api/admin/review-tasks`
- `GET /api/admin/service-requests`
- `PATCH /api/admin/service-requests/<request_id>`
- `GET /api/admin/watchlist-subscriptions`
- `PATCH /api/admin/watchlist-subscriptions/<subscription_id>`
- `GET /api/admin/user-profiles`
- `PATCH /api/admin/user-profiles/<profile_id>`
- `GET /api/admin/readiness-checks`
- `POST /api/admin/trusted-sources`

### Service Request Admin

`GET /api/admin/service-requests`

Optional query params:

- `status=new`
- `service_slug=courier`
- `limit=75`

`PATCH /api/admin/service-requests/<request_id>`

Starter body:

```json
{
  "status": "contacted"
}
```

Allowed statuses:

```text
new
reviewing
contacted
closed
spam
```

### Watchlist Subscription Admin

`GET /api/admin/watchlist-subscriptions`

Optional query params:

- `status=active`
- `watch_type=opportunity`
- `preferred_channel=whatsapp`
- `limit=75`

Returns saved watchlist subscriptions after migration `007_watchlist_alert_subscriptions.sql` is run.

`PATCH /api/admin/watchlist-subscriptions/<subscription_id>`

Starter body:

```json
{
  "status": "closed"
}
```

Allowed statuses:

```text
active
paused
unsubscribed
closed
spam
```

### User Profile Admin

`GET /api/admin/user-profiles`

Optional query params:

- `status=new`
- `main_goal=startup`
- `target_country=Estonia`
- `limit=75`

Returns saved relocation profiles after migration `008_user_relocation_profiles.sql` is run.

`PATCH /api/admin/user-profiles/<profile_id>`

Starter body:

```json
{
  "status": "contacted"
}
```

Allowed statuses:

```text
new
reviewing
contacted
active
closed
spam
```

### Readiness Check Admin

`GET /api/admin/readiness-checks`

Optional query params:

- `tool_slug=funds_plan`
- `risk_level=high`
- `readiness_status=needs_attention`
- `limit=75`

Returns saved readiness tool runs after migration `006_readiness_check_runs.sql` is run.

## Report Endpoint

`POST /api/relocation/reports`

Starter body:

```json
{
  "goal": "business",
  "route_category": "startup",
  "current_country": "Kuwait",
  "target_country": "Estonia",
  "available_funds_amount": 12000,
  "available_funds_currency": "EUR",
  "family_members_count": 0
}
```

The starter report generator creates a structured readiness report without making final legal claims. Next work should connect this endpoint more deeply to approved route versions and source snapshots.