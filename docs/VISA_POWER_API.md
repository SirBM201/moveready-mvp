# Visa Power API

## Purpose

Visa Power and Travel Benefits checks whether visas a user already holds may create extra travel opportunities in third countries.

This supports the MoveReady passport-index direction without turning the product into a generic travel site.

## Endpoints

### GET `/api/visa-power/options`

Returns accepted existing-visa codes, starter passport options, and a safety note.

### GET `/api/visa-power/provider/status`

Returns the provider-cache setup state:

- Provider enabled/configured status
- Provider name
- Cache max age
- Twice-weekly sync weekdays
- Safety note

This endpoint is public because it reveals only product status, not provider secrets.

### POST `/api/visa-power/provider/sync`

Protected by `X-MoveReady-Admin-Key`.

This endpoint is designed for GitHub Actions, Railway cron, or an admin console. It fetches provider data, normalizes it, and stores it in Supabase.

The default GitHub Actions workflow runs Tuesday and Friday at 06:00 UTC.

Required tables:

- `relocation_passport_index_cache`
- `relocation_passport_destination_access`
- `relocation_passport_provider_sync_runs`

Run `supabase/migrations/027_passport_index_provider_cache.sql` before turning on provider sync.

### GET `/api/visa-power/passport-index/options`

Returns passport countries and provider-cache status for the Passport Index page.

### POST `/api/visa-power/passport-index/check`

Example payload:

```json
{
  "passport_country": "Nigeria"
}
```

Returns:

- Passport country
- Passport rating / opportunity score
- Passport rank where provider supplies it
- Passport strength band
- Visa-free count
- Visa-on-arrival count
- eVisa / ETA count
- Visa-required count
- Destination access rows grouped by bucket
- Source provider
- Last synced date
- Next sync due date
- Safety note

Public user clicks should read the cached data. They should not call the paid provider directly.

### POST `/api/visa-power/check`

Example payload:

```json
{
  "passport_country": "Nigeria",
  "held_visas": ["canada_visitor"],
  "multiple_entry_confirmed": true,
  "visa_used_before_confirmed": false
}
```

Returns:

- Passport country
- Held visa codes
- Passport-only score
- Visa opportunity score
- Combined opportunity score
- Matched destination count
- Matched rules
- Official source name and URL
- Last verified date
- Conditions
- Safety note

## Starter rule records

The current static Visa Power API includes starter records for:

- Mexico
- Dominican Republic
- Panama
- Costa Rica

These records must still be treated as official-source-first planning guidance, not travel approval.

## Passport Index provider-cache design

MoveReady should support a working passport/visa API without wasting resources.

Recommended flow:

1. Select a provider after cost/API review.
2. Set provider environment variables on Railway.
3. Run the Supabase cache migration.
4. Let the scheduled job refresh data twice weekly.
5. Show cached passport lists to users instantly.
6. Preserve `source_provider`, `last_synced_at`, `last_reviewed`, `confidence`, and official-source warning fields.

Environment variables:

```env
PASSPORT_INDEX_PROVIDER_ENABLED=true
PASSPORT_INDEX_PROVIDER_NAME=Your provider name
PASSPORT_INDEX_PROVIDER_URL=https://provider.example/api/passport/{country_key}
PASSPORT_INDEX_PROVIDER_KEY=provider-secret
PASSPORT_INDEX_PROVIDER_METHOD=GET
PASSPORT_INDEX_CACHE_MAX_DAYS=4
PASSPORT_INDEX_SYNC_WEEKDAYS=TUE,FRI
```

Provider URL may include `{country}` or `{country_key}` placeholders.

## Important safety rule

The API must never say that entry is guaranteed.

Every result should preserve this logic:

- Confirm official destination rules before travel.
- Confirm airline and transit requirements before buying tickets.
- Confirm visa validity, multiple-entry status, and previous-use conditions where applicable.
- Border officers still decide entry.

## Future database direction

The provider-cache schema now starts this direction. Later, when this feature becomes a paid product, expand into deeper review/version tables:

- `visa_power_documents`
- `visa_power_destination_rules`
- `visa_power_rule_sources`
- `visa_power_user_checks`
- `visa_power_watchlist`

Each rule should include reviewer status, last verified date, source URL, confidence level, and change history.
