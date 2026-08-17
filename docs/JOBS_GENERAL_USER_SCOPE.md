# MoveReady B05 — General-user Jobs scope contract

Status: implementation contract for B05.

This batch generalizes the existing Jobs backend without replacing vacancy monitoring, source controls, truthful document drafting, application tracking, or user-confirmed submission.

## Supported search scopes

- `local`: vacancies in the country where the user currently lives or works;
- `international`: vacancies in explicitly selected foreign target countries;
- `both`: the local country and explicitly selected foreign target countries.

The backend never infers nationality, citizenship, residence status, or work authorization from the current country.

## Profile fields

Migration `034_career_search_scope_and_viability.sql` already provides the required additive columns:

- `search_scope`;
- `current_country`;
- `work_authorized_countries`.

The existing `primary_country` and `later_countries` fields remain the international target-country contract. No additional migration is created for B05.

Both of these authenticated endpoints expose the same scope contract:

- `GET/PATCH /api/jobs/profile`;
- `PATCH /api/jobs/profile/search-scope`.

Responses include `search_contract.version=b05-v1`, the local and international target-country lists, missing fields, and a truth note.

## Vacancy authorization fields

Migration 034 also provides:

- `work_authorization_requirement`;
- `sponsorship_evidence`;
- `relocation_support_status`.

Official-source monitoring persists these values only from explicit vacancy wording. Unknown remains unknown. Confirmed sponsorship or relocation support is never invented.

Skill fit and application viability remain separate:

- a high technical match can still be out of scope;
- a local vacancy requires recorded work authorization before handoff readiness;
- a foreign vacancy outside the user's selected countries is out of scope;
- a vacancy requiring existing authorization is not recommended when the user has not recorded it;
- possible employer support remains `consider`, not confirmed;
- incomplete scope profiles fail closed.

## Automation boundary

- watches must target a country inside the user's selected scope;
- out-of-scope and not-recommended vacancies do not create new-match alerts;
- work-authorization verification items may still create a review alert;
- official employer or supported public ATS host controls remain unchanged;
- MoveReady never submits an application automatically;
- employer-site handoff remains blocked until scope, authorization, documents, and the official HTTPS link are ready.

## Database readiness

Protected operations diagnostics now select the migration-034 columns explicitly. If migration 034 has not been applied, Jobs remains fail-closed and reports the exact migration requirement.

Read-only Supabase check:

```sql
select
  table_name,
  column_name
from information_schema.columns
where table_schema = 'public'
  and (
    (table_name = 'relocation_job_search_profiles' and column_name in (
      'search_scope',
      'current_country',
      'work_authorized_countries'
    ))
    or
    (table_name = 'relocation_jobs' and column_name in (
      'work_authorization_requirement',
      'sponsorship_evidence',
      'relocation_support_status'
    ))
  )
order by table_name, column_name;
```

Expected result: six rows. If any are missing, run the existing `supabase/migrations/034_career_search_scope_and_viability.sql` file once and refresh the Supabase schema cache.

## Batch boundary

B05 is backend/database only. General-user Jobs forms and mobile UX belong to B06. The explicit founder/PET bootstrap remains an optional owner template and is not used as the general-user default.
