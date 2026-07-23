param(
    [string]$Base = "https://moveready-mvp-production.up.railway.app",
    [string]$AdminKey = "",
    [string]$SessionToken = ""
)

$ErrorActionPreference = "Stop"
$Base = $Base.TrimEnd("/")

function Assert-True {
    param(
        [Parameter(Mandatory = $true)][bool]$Condition,
        [Parameter(Mandatory = $true)][string]$Message
    )
    if (-not $Condition) { throw $Message }
}

function Invoke-MoveReadyJson {
    param(
        [Parameter(Mandatory = $true)][ValidateSet("GET", "POST", "PUT", "PATCH")][string]$Method,
        [Parameter(Mandatory = $true)][string]$Path,
        [hashtable]$Headers = @{},
        [hashtable]$Body
    )

    $Parameters = @{
        Method = $Method
        Uri = "$Base$Path"
        Headers = $Headers
        TimeoutSec = 120
    }
    if ($null -ne $Body -and $Method -ne "GET") {
        $Parameters.ContentType = "application/json"
        $Parameters.Body = ($Body | ConvertTo-Json -Depth 30)
    }
    return Invoke-RestMethod @Parameters
}

Write-Host "`n=== 1. PUBLIC OPERATIONS STATUS ===" -ForegroundColor Cyan
$Operations = Invoke-MoveReadyJson -Method GET -Path "/api/operations/status"
$Operations | ConvertTo-Json -Depth 30
Assert-True -Condition ($Operations.ok -eq $true) -Message "Public operations status returned ok=false."
Assert-True -Condition ($null -ne $Operations.public_capabilities.account_settings_and_privacy) -Message "Account settings capability is missing."
Assert-True -Condition ($null -ne $Operations.public_capabilities.application_alert_inbox) -Message "Application alert capability is missing."

Write-Host "`n=== 2. PLATFORM MODULES ===" -ForegroundColor Cyan
$Modules = Invoke-MoveReadyJson -Method GET -Path "/api/platform/modules"
$RequiredSlugs = @(
    "onboarding",
    "my-journey",
    "action-center",
    "application-center",
    "application-alerts",
    "account-activity",
    "account-settings"
)
foreach ($Slug in $RequiredSlugs) {
    $Module = @($Modules.modules | Where-Object { $_.slug -eq $Slug })[0]
    Assert-True -Condition ($null -ne $Module) -Message "Platform module missing: $Slug"
    Assert-True -Condition ($Module.availability -eq "available") -Message "Platform module is not available: $Slug"
    Write-Host "AVAILABLE: $Slug" -ForegroundColor Green
}

Write-Host "`n=== 3. ANONYMOUS ACCESS BARRIERS ===" -ForegroundColor Cyan
$PrivatePaths = @(
    "/api/account/preferences",
    "/api/account/sessions",
    "/api/account/activity",
    "/api/account/action-center",
    "/api/account/data-export",
    "/api/account/privacy-requests"
)
foreach ($Path in $PrivatePaths) {
    try {
        Invoke-RestMethod -Method Get -Uri "$Base$Path" -TimeoutSec 60 | Out-Null
        throw "Private endpoint unexpectedly allowed anonymous access: $Path"
    }
    catch {
        $StatusCode = 0
        if ($null -ne $_.Exception.Response) {
            try { $StatusCode = [int]$_.Exception.Response.StatusCode } catch { $StatusCode = 0 }
        }
        Assert-True -Condition ($StatusCode -eq 401) -Message "Expected 401 from $Path but received $StatusCode."
        Write-Host "PROTECTED: $Path" -ForegroundColor Green
    }
}

if (-not [string]::IsNullOrWhiteSpace($AdminKey)) {
    Write-Host "`n=== 4. PROTECTED SCHEMA DIAGNOSTICS ===" -ForegroundColor Cyan
    $AdminHeaders = @{ "X-MoveReady-Admin-Key" = $AdminKey.Trim() }
    $Status = Invoke-MoveReadyJson -Method GET -Path "/api/admin/operations/status" -Headers $AdminHeaders
    $RequiredSchemaCodes = @(
        "application_case_alerts",
        "account_preferences",
        "privacy_requests"
    )
    foreach ($Code in $RequiredSchemaCodes) {
        $Check = @($Status.schema_checks | Where-Object { $_.code -eq $Code })[0]
        Assert-True -Condition ($null -ne $Check) -Message "Operations response is missing schema check: $Code"
        Assert-True -Condition ($Check.ok -eq $true) -Message "Schema check failed for $Code. Run $($Check.migration). Error: $($Check.error)"
        Write-Host "READY: $Code" -ForegroundColor Green
    }

    $PrivacyQueue = Invoke-MoveReadyJson -Method GET -Path "/api/admin/privacy-requests?limit=5" -Headers $AdminHeaders
    Assert-True -Condition ($PrivacyQueue.ok -eq $true) -Message "Protected privacy queue returned ok=false."
    Write-Host "Privacy queue is reachable and protected." -ForegroundColor Green
}
else {
    Write-Host "`nSKIPPED: protected schema and privacy queue checks because AdminKey was not supplied." -ForegroundColor Yellow
}

if (-not [string]::IsNullOrWhiteSpace($SessionToken)) {
    Write-Host "`n=== 5. VERIFIED ACCOUNT READ-ONLY CHECKS ===" -ForegroundColor Cyan
    $SessionHeaders = @{ Authorization = "Bearer $($SessionToken.Trim())" }

    $Preferences = Invoke-MoveReadyJson -Method GET -Path "/api/account/preferences" -Headers $SessionHeaders
    Assert-True -Condition ($Preferences.ok -eq $true) -Message "Account preferences returned ok=false."

    $Sessions = Invoke-MoveReadyJson -Method GET -Path "/api/account/sessions" -Headers $SessionHeaders
    Assert-True -Condition ($Sessions.ok -eq $true) -Message "Session list returned ok=false."
    foreach ($Session in @($Sessions.sessions)) {
        Assert-True -Condition ($null -eq $Session.token_hash) -Message "A session token hash leaked into the public session response."
        Assert-True -Condition ($null -eq $Session.remote_addr) -Message "A remote address leaked into the public session response."
    }

    $Activity = Invoke-MoveReadyJson -Method GET -Path "/api/account/activity?limit=10" -Headers $SessionHeaders
    Assert-True -Condition ($Activity.ok -eq $true) -Message "Account activity returned ok=false."

    $ActionCenter = Invoke-MoveReadyJson -Method GET -Path "/api/account/action-center?limit=25" -Headers $SessionHeaders
    Assert-True -Condition ($ActionCenter.ok -eq $true) -Message "Action Center returned ok=false."
    Assert-True -Condition ($null -ne $ActionCenter.counts_by_priority) -Message "Action Center priority counts are missing."
    Assert-True -Condition ($null -ne $ActionCenter.counts_by_section) -Message "Action Center section counts are missing."
    foreach ($Action in @($ActionCenter.actions)) {
        Assert-True -Condition (@("low", "medium", "high", "critical") -contains $Action.priority) -Message "Action Center returned an invalid priority."
        Assert-True -Condition (-not [string]::IsNullOrWhiteSpace([string]$Action.href)) -Message "Action Center returned an item without an underlying workspace link."
        Assert-True -Condition ($null -eq $Action.token_hash) -Message "A security token leaked into an Action Center item."
        Assert-True -Condition ($null -eq $Action.file_content) -Message "Raw file content leaked into an Action Center item."
    }

    $Export = Invoke-MoveReadyJson -Method GET -Path "/api/account/data-export" -Headers $SessionHeaders
    Assert-True -Condition ($Export.ok -eq $true) -Message "Account data export returned ok=false."
    Assert-True -Condition (@($Export.excluded_security_data).Count -ge 5) -Message "Export security exclusion disclosure is incomplete."
    Assert-True -Condition ($null -eq $Export.data.relocation_auth_login_codes) -Message "OTP records must not be present in the export."
    Assert-True -Condition ($null -eq $Export.data.relocation_user_sessions) -Message "Session records must not be present in the export."

    $PrivacyRequests = Invoke-MoveReadyJson -Method GET -Path "/api/account/privacy-requests" -Headers $SessionHeaders
    Assert-True -Condition ($PrivacyRequests.ok -eq $true) -Message "Privacy request history returned ok=false."
    Write-Host "Verified preferences, sessions, activity, Action Center, export, privacy history, and My Journey source modules are responding safely." -ForegroundColor Green
}
else {
    Write-Host "`nSKIPPED: verified account checks because SessionToken was not supplied." -ForegroundColor Yellow
}

Write-Host "`n=== ACCOUNT CONTROLS RELEASE TEST PASSED ===" -ForegroundColor Green
Write-Host "This script is read-only. It does not change preferences, revoke sessions, create privacy requests, delete data, activate messaging, enable payments, or modify Action Center source records."
