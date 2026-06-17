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

## Admin

Admin routes require one of these headers:

- `X-MoveReady-Admin-Key`
- `X-Relocation-Admin-Key`
- `X-Admin-Key`

Routes:

- `GET /api/admin/status`
- `GET /api/admin/review-tasks`
- `POST /api/admin/trusted-sources`

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
