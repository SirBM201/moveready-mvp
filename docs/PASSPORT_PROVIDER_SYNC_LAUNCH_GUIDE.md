# Passport Provider Sync Launch Guide

## What this adds

MoveReady now has a provider-ready Passport Index system.

Public users should not wait for a paid provider API every time they click. The backend should fetch passport data twice weekly, store it in Supabase, and show cached results instantly.

## User benefit

A user can choose a passport country and see:

- Passport rating / opportunity score
- Passport rank when the provider supplies it
- Strength band
- Visa-free destinations
- Visa-on-arrival destinations
- eVisa / ETA destinations
- Visa-required destinations
- Conditions and maximum stay where available
- Source provider
- Last synced date
- Next refresh due date

## Backend flow

```text
User clicks Check my passport
↓
MoveReady backend reads cached passport data
↓
If cache exists, show provider-backed rows
↓
If cache is missing, show starter fallback and clear warning
```

The paid/free provider is called only by admin or scheduled sync:

```text
GitHub Actions / admin
↓
POST /api/visa-power/provider/sync
↓
External passport provider
↓
Supabase cache tables
```

## Supabase migration

Run this before enabling provider sync:

```sql
supabase/migrations/027_passport_index_provider_cache.sql
```

## Railway environment variables

Set these after selecting a provider:

```env
PASSPORT_INDEX_PROVIDER_ENABLED=true
PASSPORT_INDEX_PROVIDER_NAME=Your provider name
PASSPORT_INDEX_PROVIDER_URL=https://provider.example/api/passport/{country_key}
PASSPORT_INDEX_PROVIDER_KEY=provider-secret
PASSPORT_INDEX_PROVIDER_METHOD=GET
PASSPORT_INDEX_CACHE_MAX_DAYS=4
PASSPORT_INDEX_SYNC_WEEKDAYS=TUE,FRI
```

`PASSPORT_INDEX_PROVIDER_URL` may use `{country}` or `{country_key}`.

## GitHub Actions secrets

The workflow `.github/workflows/passport-index-sync.yml` runs Tuesday and Friday at 06:00 UTC.

Add these secrets in the backend repository:

- `MOVEREADY_ADMIN_API_KEY`
- Optional: `MOVEREADY_API_BASE`

Default API base is:

```text
https://moveready-mvp-production.up.railway.app
```

## PowerShell test commands

Set the base URL:

```powershell
$Base = "https://moveready-mvp-production.up.railway.app"
```

Check build info:

```powershell
Invoke-RestMethod -Method Get -Uri "$Base/api/build-info" | ConvertTo-Json -Depth 10
```

Check provider status:

```powershell
Invoke-RestMethod -Method Get -Uri "$Base/api/visa-power/provider/status" | ConvertTo-Json -Depth 10
```

Check Passport Index:

```powershell
$PassportPayload = @{
    passport_country = "Nigeria"
}

$Passport = Invoke-RestMethod `
    -Method Post `
    -Uri "$Base/api/visa-power/passport-index/check" `
    -ContentType "application/json" `
    -Body ($PassportPayload | ConvertTo-Json -Depth 10)

$Passport.passport_index.passport_opportunity_score
$Passport.passport_index.passport_rank
$Passport.passport_index.passport_strength_band
$Passport.passport_index.destination_access_rows | Select-Object destination,access_bucket,access_type,maximum_stay,source_status | Format-Table
```

Check Visa Power with provider-ready passport data:

```powershell
$VisaPowerPayload = @{
    passport_country = "Nigeria"
    held_visas = @("canada_visitor")
    multiple_entry_confirmed = $true
    visa_used_before_confirmed = $false
}

$VisaPower = Invoke-RestMethod `
    -Method Post `
    -Uri "$Base/api/visa-power/check" `
    -ContentType "application/json" `
    -Body ($VisaPowerPayload | ConvertTo-Json -Depth 10)

$VisaPower.combined_opportunity_score
$VisaPower.passport_only_score
$VisaPower.visa_opportunity_score
$VisaPower.cache_status
$VisaPower.matches | Select-Object destination,separate_visa_needed,maximum_stay,confidence,condition_status | Format-Table
```

Manual provider sync test after setting provider variables and admin key:

```powershell
$AdminKey = "paste-your-admin-key-here"

Invoke-RestMethod `
    -Method Post `
    -Uri "$Base/api/visa-power/provider/sync" `
    -Headers @{ "X-MoveReady-Admin-Key" = $AdminKey } `
    -ContentType "application/json" `
    -Body (@{ passport_country = "Nigeria" } | ConvertTo-Json -Depth 10) | ConvertTo-Json -Depth 10
```

## Important product rule

MoveReady must never tell users that travel is guaranteed.

Always show:

- Confirm official destination rules.
- Confirm airline and transit checks.
- Confirm passport validity and blank pages.
- Confirm funds, ticket, accommodation, purpose, and personal travel history.
- Border officers still decide entry.
