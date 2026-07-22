# Passport Index Weekly Operations

## Production design

MoveReady uses two provider layers:

1. **Weekly passport map overview**
   - Endpoint: `POST /v2/visa/map`
   - Stored in:
     - `relocation_passport_index_cache`
     - `relocation_passport_destination_access`
   - Scheduled by `.github/workflows/passport-index-weekly-sync.yml`
   - Default schedule: Friday at 06:17 UTC
   - The workflow syncs every passport configured in `PASSPORT_INDEX_RECORDS` when no country is supplied.

2. **Destination-specific detail**
   - Endpoint: `POST /v2/visa/check`
   - MoveReady calls it only when a user opens a destination's detailed rule.
   - The normalized result is stored inside that destination row's `provider_payload.destination_detail` object.
   - Default detail cache: seven days.
   - Weekly map replacement preserves existing destination-detail caches.

## Safety controls

- A provider response that normalizes to zero rows cannot overwrite the destination cache.
- Blue, yellow, and red map categories remain labelled as combined provider categories until a destination-specific check is completed.
- Detailed rules keep the provider-generated timestamp, primary rule, secondary rule, exception rule, mandatory registration, stay duration, passport-validity requirement, and supplied source link.
- All public responses retain a warning to confirm destination government, embassy or consulate, airline document checker, and current entry conditions.

## Required one-time GitHub Actions configuration

In the backend repository settings:

1. Open **Settings → Secrets and variables → Actions**.
2. Under **Secrets**, create:
   - Name: `MOVEREADY_ADMIN_KEY`
   - Value: the same value used by Railway for `MOVEREADY_ADMIN_API_KEY`.
3. Under **Variables**, optionally create:
   - Name: `MOVEREADY_API_BASE`
   - Value: `https://moveready-mvp-production.up.railway.app`

The API base variable is optional because the workflow already uses that production URL as its default.

Never put the admin key in a repository variable, workflow file, issue, commit, or chat message.

## Manual workflow verification

1. Open the backend repository's **Actions** tab.
2. Select **Passport Index Weekly Sync**.
3. Choose **Run workflow**.
4. Leave `passport_country` empty to sync all configured passports, or enter `Nigeria` for a one-country verification.
5. Confirm all steps are green and the job summary shows non-zero rows with no errors.

## API verification commands

### Provider status

```powershell
Invoke-RestMethod `
  -Method Get `
  -Uri "https://moveready-mvp-production.up.railway.app/api/visa-power/provider/status" |
  ConvertTo-Json -Depth 20
```

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

## Quota strategy

- Weekly map sync of seven starter passports uses about seven provider requests per week.
- Destination details are requested only for destinations users actually open.
- Each passport-destination detail is cached for seven days.
- Normal Passport Index page views read Supabase and do not call RapidAPI while the overview cache is fresh.

## Failure handling

- GitHub Actions fails if the admin secret is missing.
- The workflow retries while Railway wakes from an idle state.
- The workflow fails if the API reports errors, returns no results, or writes zero rows.
- Existing destination details are retained across weekly map refreshes.
- Provider failures are logged in `relocation_passport_provider_sync_runs` where available.
