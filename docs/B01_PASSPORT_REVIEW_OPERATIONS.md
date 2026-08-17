# B01 — Passport official-source review operations

Migration 038 is the database prerequisite.

## Admin endpoints
All endpoints require the existing `X-MoveReady-Admin-Key` contract (legacy admin header aliases remain supported by the shared guard).

- `GET /api/admin/passport-official-sources/reviews?status=pending_review` — review queue.
- `GET /api/admin/passport-official-sources/<mapping_id>/reviews` — immutable decision history.
- `POST /api/admin/passport-official-sources/<mapping_id>/review` — controlled transition.
- `POST /api/admin/passport-official-sources/reviews/expire` — fail overdue verified mappings closed to `needs_review`.

Review body:

```json
{
  "decision": "verified",
  "reviewer": "reviewer identity",
  "evidence_note": "What authority, ownership, scope and freshness were checked.",
  "reviewed_source_url": "https://exact-mapped-authority-url.example/",
  "review_interval_days": 90
}
```

The API performs basic input validation, but the database function remains the final authority: only active government/embassy sources, exact mapped HTTPS URLs and valid decisions can pass.

## Safety
- No provider data is promoted by this workflow.
- Normal authenticated/anonymous users cannot call the migration-038 review functions directly.
- The admin API uses the existing MoveReady admin-key boundary.
- Review history is append-only through the supported application workflow.
- Expired verification fails closed.
- Benin remains pending until the authority chain meets the verification checklist.

## Operations
Call the expiry endpoint from source-governance/scheduled operations before relying on verification freshness. A later batch may consolidate this into the broader monitoring scheduler; B01 intentionally does not change unrelated scheduler behavior.
