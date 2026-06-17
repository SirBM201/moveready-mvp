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

## Platform Architecture

Batch 2A adds planned platform endpoints. These are architecture placeholders, not active third-party integrations.

- `GET /api/platform/status`
- `GET /api/platform/modules`
- `GET /api/platform/modules/<slug>`

Planned direct endpoints:

- `GET /api/opportunities`
- `GET /api/watchlist`
- `GET /api/alerts`
- `GET /api/documents`
- `GET /api/funds`
- `GET /api/courier`
- `GET /api/legalization`
- `GET /api/insurance`
- `GET /api/appointments`
- `GET /api/partners`

Expected planned response shape:

```json
{
  "ok": true,
  "status": "planned",
  "message": "This module is part of the platform architecture but is not active for production use yet."
}
```

Use feature flags to activate modules later after their database models, provider integrations, opt-in workflows, and compliance rules are ready.

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
