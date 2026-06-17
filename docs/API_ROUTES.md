# MoveReady MVP API Routes

Base prefix: `/api`

## Public

- `GET /health`
- `GET /api/health`
- `GET /api/relocation/countries`
- `GET /api/relocation/routes`
- `GET /api/relocation/routes/<route_id>`
- `GET /api/relocation/routes/by-code/<country_code>/<route_code>`
- `POST /api/relocation/checklist`
- `POST /api/relocation/budget-estimate`
- `GET /api/relocation/scholarships`
- `GET /api/relocation/insurance-requirements`
- `POST /api/relocation/reports`

## Route Detail By Code

`GET /api/relocation/routes/by-code/EE/startup-founder`

Returns the public route, active route version summary, route facts, document requirements, budget items, insurance requirements, risk level, source confidence, verified date, and review due date.

This is useful for stable frontend pages because the page can use country and route codes instead of database UUIDs.

## Platform Services

Service endpoints are prepared for launch and return public-safe availability labels until the relevant official-source checks, provider approvals, opt-in flows, and audit rules are ready.

- `GET /api/platform/status`
- `GET /api/platform/modules`
- `GET /api/platform/modules/<slug>`
- `POST /api/platform/service-interest`

Service endpoints:

- `GET /api/opportunities`
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
  "message": "This service is being prepared for launch and will be available once official-source checks, provider approval, user consent, and audit rules are ready."
}
```

Use feature flags to switch modules on only after their database models, provider integrations, opt-in workflows, and compliance rules are ready.

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

The starter report generator creates a structured readiness report without making final legal claims. Later batches should connect this endpoint to approved route versions and source snapshots.
