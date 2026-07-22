param(
    [string]$Base = "https://moveready-mvp-production.up.railway.app",
    [string]$PassportCountry = "Nigeria",
    [string]$DetailDestination = "Canada",
    [switch]$RunDetailCheck,
    [switch]$RunScheduledSync
)

$ErrorActionPreference = "Stop"
$Base = $Base.TrimEnd("/")

function Write-Step([string]$Title) {
    Write-Host "`n=== $Title ===" -ForegroundColor Cyan
}

function Show-Json($Value, [int]$Depth = 30) {
    $Value | ConvertTo-Json -Depth $Depth
}

Write-Step "1. BUILD INFO"
$BuildInfo = Invoke-RestMethod -Method Get -Uri "$Base/api/build-info"
Show-Json $BuildInfo 15

Write-Step "2. PROVIDER STATUS"
$ProviderStatus = Invoke-RestMethod -Method Get -Uri "$Base/api/visa-power/provider/status"
Show-Json $ProviderStatus 20
if (-not $ProviderStatus.ready_to_sync) {
    throw "Passport provider is not ready to sync."
}

Write-Step "3. UNATTENDED SCHEDULE STATUS"
$ScheduleStatus = Invoke-RestMethod -Method Get -Uri "$Base/api/visa-power/provider/schedule/status"
Show-Json $ScheduleStatus 30
if ([int]$ScheduleStatus.max_countries_per_sync -ne 1) {
    throw "Launch cost guard failed: max_countries_per_sync is not 1."
}
if (@($ScheduleStatus.scheduled_countries).Count -ne 1 -or $ScheduleStatus.scheduled_countries[0] -ne "Nigeria") {
    throw "Launch scheduled country is not exactly Nigeria."
}

if ($RunScheduledSync) {
    Write-Step "4. PROTECTED SCHEDULED SYNC"
    $SecureAdminKey = Read-Host "Paste the MoveReady admin key" -AsSecureString
    $AdminKey = [System.Net.NetworkCredential]::new("", $SecureAdminKey).Password
    if ([string]::IsNullOrWhiteSpace($AdminKey)) {
        throw "The MoveReady admin key is empty."
    }

    try {
        $Sync = Invoke-RestMethod `
            -Method Post `
            -Uri "$Base/api/visa-power/provider/scheduled-sync" `
            -Headers @{ "X-MoveReady-Admin-Key" = $AdminKey } `
            -ContentType "application/json" `
            -Body (@{ passport_country = $PassportCountry } | ConvertTo-Json)
        Show-Json $Sync 30
        if (-not $Sync.ok -or $Sync.status -ne "scheduled_sync_completed") {
            throw "Protected scheduled sync did not complete successfully."
        }
        if (@($Sync.results).Count -ne 1) {
            throw "Protected scheduled sync returned more or fewer than one passport result."
        }
        $SyncedRows = [int]($Sync.results[0].row_count)
        if ($SyncedRows -lt 200) {
            throw "Protected scheduled sync returned fewer than 200 destination rows."
        }
    }
    finally {
        Remove-Variable AdminKey, SecureAdminKey -ErrorAction SilentlyContinue
    }
}
else {
    Write-Host "`nProtected scheduled sync skipped. Add -RunScheduledSync to make the paid weekly map test call." -ForegroundColor Yellow
}

Write-Step "5. PUBLIC PASSPORT INDEX CACHE"
$PassportPayload = @{ passport_country = $PassportCountry }
$Passport = Invoke-RestMethod `
    -Method Post `
    -Uri "$Base/api/visa-power/passport-index/check" `
    -ContentType "application/json" `
    -Body ($PassportPayload | ConvertTo-Json)

$Rows = @($Passport.passport_index.destination_access_rows)
Write-Host "Passport: $($Passport.passport_country)"
Write-Host "Rows: $($Rows.Count)"
Write-Host "Source: $($Passport.cache_status.data_source)"
Write-Host "Provider: $($Passport.cache_status.source_provider)"
Write-Host "Refresh status: $($Passport.provider_refresh.status)"

if (-not $Passport.ok) {
    throw "Public Passport Index returned ok=false."
}
if ($Rows.Count -lt 200) {
    throw "Public Passport Index returned fewer than 200 destination rows."
}
if ($Passport.cache_status.data_source -ne "provider_cache") {
    throw "Public Passport Index is not using provider_cache."
}

Write-Step "6. VISA POWER SAFETY GATE"
$VisaPowerPayload = @{
    passport_country = $PassportCountry
    held_visas = @("canada_visitor")
    multiple_entry_confirmed = $true
    visa_used_before_confirmed = $false
    prior_entry_refusal_declared = $true
    visa_cancelled_or_revoked_declared = $false
}
$VisaPower = Invoke-RestMethod `
    -Method Post `
    -Uri "$Base/api/visa-power/check" `
    -ContentType "application/json" `
    -Body ($VisaPowerPayload | ConvertTo-Json -Depth 10)
Show-Json $VisaPower 30

if ($VisaPower.feature -notlike "*safety_gate") {
    throw "The server-side Visa Power safety gate is not active."
}
if (-not $VisaPower.prior_entry_refusal_declared) {
    throw "Visa Power did not preserve the prior-entry-refusal declaration."
}
if (@($VisaPower.travel_history_warnings).Count -lt 2) {
    throw "Visa Power did not return the expected travel-history warnings."
}

if ($RunDetailCheck) {
    Write-Step "7. DESTINATION DETAIL CACHE"
    $DetailPayload = @{
        passport_country = $PassportCountry
        destination = $DetailDestination
    }

    $DetailFirst = Invoke-RestMethod `
        -Method Post `
        -Uri "$Base/api/visa-power/passport-index/destination/check" `
        -ContentType "application/json" `
        -Body ($DetailPayload | ConvertTo-Json)
    Show-Json $DetailFirst 30

    $DetailSecond = Invoke-RestMethod `
        -Method Post `
        -Uri "$Base/api/visa-power/passport-index/destination/check" `
        -ContentType "application/json" `
        -Body ($DetailPayload | ConvertTo-Json)
    Show-Json $DetailSecond 30

    if (-not $DetailFirst.ok -or -not $DetailSecond.ok) {
        throw "Destination detail check failed."
    }
    if ($DetailSecond.status -ne "detail_cache_hit") {
        throw "Second destination detail call was not served from the seven-day cache."
    }
}
else {
    Write-Host "`nDestination detail test skipped. Add -RunDetailCheck to test the paid detail endpoint and its cache." -ForegroundColor Yellow
}

Write-Host "`nMoveReady Passport Index release verification passed." -ForegroundColor Green
