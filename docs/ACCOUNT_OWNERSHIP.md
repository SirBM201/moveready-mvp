# MoveReady Account Ownership

MoveReady supports two MVP identity modes:

1. Contact-based lookup by email or phone.
2. Verified email session from `/api/auth/verify-code`.

When a valid session token is present on account-owned write requests, the backend now prefers the verified session email over any manually submitted email field.

This applies to:

- `POST /api/profiles`
- `PATCH /api/profiles/<id>`
- `POST /api/saved-routes`
- `PATCH /api/saved-routes/<id>`
- `POST /api/watchlist/subscriptions`
- `PATCH /api/watchlist/subscriptions/<id>`
- `POST /api/timeline`
- `PATCH /api/timeline/<id>`
- `POST /api/platform/service-interest`
- `POST /api/relocation/reports`

The older contact-based flow remains useful for MVP lookup, but verified sessions should be treated as the safer owner identity.

Frontend API calls now automatically attach the stored MoveReady session token to these account-owned write requests, even if an older form explicitly disables auth.

## Trust rule

Verified login connects user-owned records. It does not imply visa approval, admission approval, job approval, lottery selection, ballot success, or provider acceptance.
