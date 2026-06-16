# MoveReady Post-SQL Smoke Test

Use this after running both Supabase SQL files and configuring backend environment variables.

## Required Backend Environment

```text
SUPABASE_URL=your_supabase_project_url
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
MOVEREADY_ADMIN_API_KEY=choose-a-private-admin-key
SECRET_KEY=choose-a-private-secret
CORS_ORIGINS=http://localhost:3000
API_PREFIX=/api
```

## Backend Checks

Start backend locally, then test:

```text
GET http://127.0.0.1:8000/health
GET http://127.0.0.1:8000/api/health
GET http://127.0.0.1:8000/api/relocation/countries
GET http://127.0.0.1:8000/api/relocation/routes
GET http://127.0.0.1:8000/api/relocation/scholarships
GET http://127.0.0.1:8000/api/relocation/insurance-requirements
```

## Report Generation Check

Send this body to:

```text
POST http://127.0.0.1:8000/api/relocation/reports
```

```json
{
  "goal": "business",
  "route_category": "startup",
  "current_country": "Kuwait",
  "target_country": "Estonia",
  "available_funds_amount": 12000,
  "available_funds_currency": "EUR",
  "family_members_count": 0,
  "timeline_months": 6
}
```

Expected result:

- `ok: true`
- `report.report_ref` starts with `MRR-`
- `report.stored: true` when Supabase env is correctly configured

## Admin Check

```text
GET http://127.0.0.1:8000/api/admin/status
```

Required header:

```text
X-MoveReady-Admin-Key: your_admin_key
```

Expected result:

- Without key: 401 unauthorized
- With key: protected admin status response

## Frontend Check

Start frontend locally and open:

```text
http://localhost:3000/route-checker
```

Click `Generate readiness plan`.

Expected result:

- Checklist appears
- Budget estimate appears
- Report appears
- Report says stored when backend Supabase env is configured
