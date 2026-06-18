# Admin Generated Report Review

MoveReady stores readiness reports in `relocation_generated_reports` when users generate route readiness reports. Admin can now review those saved reports without using the public report lookup page.

## Endpoints

All endpoints require one admin header:

- `X-MoveReady-Admin-Key`
- `X-Relocation-Admin-Key`
- `X-Admin-Key`

### List generated reports

`GET /api/admin/generated-reports`

Optional query params:

- `status=generated`
- `risk_level=medium`
- `report_ref=MRR-`
- `limit=75`

Response key:

```json
{
  "ok": true,
  "generated_reports": []
}
```

### Update generated report status

`PATCH /api/admin/generated-reports/<report_id>`

Body:

```json
{
  "status": "delivered"
}
```

Allowed statuses:

```text
generated
paid
delivered
stale
refreshed
archived
```

## Frontend

Admin UI:

```text
/admin/reports
```

The page supports admin-key storage, status/risk/reference filters, status counts, report cards, and status updates.

## SQL

No new SQL is required for generated report review. It uses the existing `relocation_generated_reports` table from the initial schema.

The separate user profile dashboard requires:

```text
supabase/migrations/008_user_relocation_profiles.sql
```
