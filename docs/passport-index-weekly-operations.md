# Passport Index Weekly Operations

## Production design

MoveReady uses two provider layers:

1. **Weekly passport map overview**
   - Provider endpoint: `POST /v2/visa/map`
   - MoveReady endpoint: `POST /api/visa-power/provider/scheduled-sync`
   - Stored in:
     - `relocation_passport_index_cache`
     - `relocation_passport_destination_access`
   - Scheduled by `.github/workflows/passport-index-weekly-sync.yml`
   - Default schedule: Friday at 06:17 UTC
   - Launch default: Nigeria only
   - Launch provider cost: one map request per scheduled run

2. **Destination-specific detail**
   - Provider endpoint: `POST /v2/visa/check`
   - MoveReady calls it only when a user opens a destination's detailed rule.
   - The normalized result is stored inside that destination row's `provider_payload.destination_detail` object.
   - Default detail cache: seven days.
   - Weekly map replacement preserves existing destination-detail caches.

## Cost controls

The production defaults are:

```env
PASSPORT_INDEX_SYNC_WEEKDAYS=FRI
PASSPORT_INDEX_SCHEDULED_COUNTRIES=Nigeria
PASSPORT_INDEX_MAX_COUNTRIES_PER_SYNC=1
PASSPORT_INDEX_CACHE_MAX_DAYS=7
PASSPORT_INDEX_DETAIL_CACHE_MAX_DAYS=7
```

The protected scheduled-sync endpoint limits each run to the configured maximum number of passports. During launch, this means one weekly Nigeria map call.

Normal Passport Index page views read Supabase and do not call RapidAPI while the overview cache is fresh. Destination detail requests are made only when a user opens a destination whose detail cache is missing or stale.

## Safety controls

- A provider response that normalizes to zero rows cannot overwrite the destination cache.
- Blue, yellow, and red map categories remain labelled as combined provider categories until a destination-specific check is completed.
- Detailed rules keep the provider-generated timestamp, primary rule, secondary rule, exception rule, mandatory registration, stay duration, passport-validity requirement, and supplied source link.
- Weekly map replacement preserves fresh destination-detail records.
- Visa Power blocks benefits when the user declares that a selected visa may be cancelled or revoked.
- A prior refusal or denied admission triggers additional personal-history warnings and is not treated as successful previous use.
- All public responses retain a warning to confirm destination government, embassy or consulate, airline document checker, visa validity, and current entry conditions.

## Required one-time GitHub Actions configuration

In the backend repository settings:

1. Open **Settings → Secrets and variables → Actions**.
2. Under **Secrets**, create:
   - Name: `MOVEREADY_ADMIN_KEY`
   - Value: the same value used by Railway for `MOVEREADY_ADMIN_API_KEY`.
3. Under **Variables**, optionally create:
   - Name: `MOVEREADY_API_BASE`
   - Value: `https://moveready-mvp-production.up.railway.app`

The API base variable is optional because the workflow already uses the production URL as its default.

Never put the admin key in a repository variable, workflow file, issue, commit, or chat message.

## Manual workflow verification

1. Open the backend repository's **Actions** tab.
2. Select **Passport Index Weekly Sync**.
3. Choose **Run workflow**.
4. Leave the default `Nigeria` value for the launch verification.
5. Confirm all steps are green.
6. Confirm the job summary shows exactly one country result, non-zero rows, and no errors.

## API verification commands

### Provider status

```powershell
Invoke-RestMethod `
  -Method Get `
  -Uri "https://moveready-mvp-production.up.railway.app/api/visa-power/provider/status" |
  ConvertTo-Json -Depth 20
```

### Scheduled-sync status

```powershell
Invoke-RestMethod `
  -Method Get `
  -Uri "https://moveready-mvp-production.up.railway.app/api/visa-power/provider/schedule/status" |
  ConvertTo-Json -Depth 30
```

Expected launch markers include:

- `scheduled_countries: ["Nigeria"]`
- `max_countries_per_sync: 1`
- `sync_weekdays: FRI`
- `next_sync_due_at`
- `last_scheduled_run` after the first workflow run

### Destination-detail status

```powershell
Invoke-RestMethod `
  -Method Get `
  -Uri "https://moveready-mvp-production.up.railway.app/api/visa-power/passport-index/destination/status" |
  ConvertTo-Json -Depth 20
```

### Admin destination-detail test

```powershell
$Payload = @{
  passport_country = "Nigeria"
  destination = "Canada"
  force_refresh = $true
}

Invoke-RestMethod `
  -Method Post `
  -Uri "https://moveready-mvp-production.up.railway.app/api/visa-power/provider/destination/test" `
  -Headers @{ "X-MoveReady-Admin-Key" = $AdminKey } `
  -ContentType "application/json" `
  -Body ($Payload | ConvertTo-Json -Depth 10) |
  ConvertTo-Json -Depth 30
```

Expected markers include:

- `ok: true`
- `test_status: destination_detail_test_success`
- `status: detail_cache_refreshed` on a forced provider call
- `detail.destination: Canada`
- `detail.primary_rule`
- `detail.passport_validity`
- `detail.source_status: provider_detail_pending_official_confirmation`

### Public destination-detail cache test

Run twice:

```powershell
$Payload = @{
  passport_country = "Nigeria"
  destination = "Canada"
}

Invoke-RestMethod `
  -Method Post `
  -Uri "https://moveready-mvp-production.up.railway.app/api/visa-power/passport-index/destination/check" `
  -ContentType "application/json" `
  -Body ($Payload | ConvertTo-Json -Depth 10) |
  ConvertTo-Json -Depth 30
```

The first successful uncached request should return `detail_cache_refreshed`. The second should return `detail_cache_hit`, confirming that another RapidAPI request was not needed.

## Failure handling

- GitHub Actions fails if the admin secret is missing.
- The workflow retries while Railway wakes from an idle state.
- The workflow fails if the API reports errors, returns anything other than one country result, or writes zero rows.
- The backend endpoint also enforces the configured per-run passport limit.
- Existing destination details are retained across weekly map refreshes.
- Scheduled results are logged in `relocation_passport_provider_sync_runs`.
- The public schedule-status endpoint exposes only a sanitized last-run summary and never exposes provider or admin secrets.
