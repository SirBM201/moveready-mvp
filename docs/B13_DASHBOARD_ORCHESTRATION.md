# B13 dashboard orchestration

## Outcome

`GET /api/account/action-center` remains the single read-only account command-center endpoint. B13 adds contract version `b13-v1`, exactly one `primary_action`, and seven `engine_statuses` grouped into FIND, QUALIFY, and MOVE.

The endpoint derives its response from existing verified-account records. It does not create a dashboard table, copy private records, submit an application, send a message, or make an eligibility decision.

## Engine map

| Phase | Engine | Existing source |
| --- | --- | --- |
| FIND | Jobs | Job-search profile, applications, and recruiter follow-ups |
| FIND | Route Finder | Active saved routes and countries |
| QUALIFY | Passport | Saved profile nationality context |
| QUALIFY | Language | Language profile and recent practice attempts |
| QUALIFY | Financial Readiness | Saved route plus user-entered profile funds |
| MOVE | Documents | Document metadata and evidence packs |
| MOVE | Applications | Private application cases, alerts, and timeline actions |

`ready` means the engine has enough saved context for its next planning check. It never means eligible, approved, funded, hired, admitted, authorized, or guaranteed.

## Next-action rules

1. Existing critical or high private-record action.
2. Missing account profile.
3. Missing saved route.
4. Highest-ranked remaining recorded action.
5. Goal-relevant Jobs setup, Language setup, or Documents setup.
6. My Journey review.

The response exposes only stable source error codes. Raw database errors are logged server-side and are never returned to the browser.

## Deployment

- Migration: none.
- New environment variables: none.
- Production fingerprint: `contract_versions.dashboard_orchestration = b13-v1` from `/api/build-info`.
