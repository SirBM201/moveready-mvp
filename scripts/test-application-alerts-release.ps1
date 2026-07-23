param(
    [string]$Base = "https://moveready-mvp-production.up.railway.app",
    [string]$SessionToken = "",
    [string]$AdminKey = "",
    [switch]$RunScan
)

$ErrorActionPreference = "Stop"
$Base = $Base.TrimEnd("/")

function Assert-True {
    param(
        [Parameter(Mandatory = $true)][bool]$Condition,
        [Parameter(Mandatory = $true)][string]$Message
    )
    if (-not $Condition) {
        throw $Message
    }
}

function Get-HttpStatusFromError {
    param([Parameter(Mandatory = $true)]$ErrorRecord)
    if ($null -ne $ErrorRecord.Exception.Response) {
        try { return [int]$ErrorRecord.Exception.Response.StatusCode } catch { return 0 }
    }
    return 0
}

function Assert-Unauthorized {
    param(
        [Parameter(Mandatory = $true)][ValidateSet("GET", "POST", "PATCH")][string]$Method,
        [Parameter(Mandatory = $true)][string]$Path,
        [hashtable]$Body
    )
    try {
        $Parameters = @{
            Method = $Method
            Uri = "$Base$Path"
            TimeoutSec = 60
        }
        if ($Method -ne "GET") {
            $Payload = @{}
            if ($null -ne $Body) { $Payload = $Body }
            $Parameters.ContentType = "application/json"
            $Parameters.Body = ($Payload | ConvertTo-Json -Depth 20)
        }
        Invoke-RestMethod @Parameters | Out-Null
        throw "Expected HTTP 401 for $Method $Path, but the request succeeded."
    }
    catch {
        $Status = Get-HttpStatusFromError -ErrorRecord $_
        if ($Status -ne 401) {
            throw "Expected HTTP 401 for $Method $Path. Actual status: $Status. Error: $($_.Exception.Message)"
        }
    }
}

Write-Host "`n=== 1. APPLICATION ALERT ROUTE BARRIERS ===" -ForegroundColor Cyan
Assert-Unauthorized -Method GET -Path "/api/applications/alerts"
Assert-Unauthorized -Method PATCH -Path "/api/applications/alerts/test-alert" -Body @{ status = "dismissed" }
Assert-Unauthorized -Method GET -Path "/api/admin/application-case-alerts"
Assert-Unauthorized -Method PATCH -Path "/api/admin/application-case-alerts/test-alert" -Body @{ status = "resolved" }
Assert-Unauthorized -Method POST -Path "/api/admin/application-cases/alerts/scan" -Body @{}
Write-Host "User and administrator application-alert routes reject anonymous access." -ForegroundColor Green

if (-not [string]::IsNullOrWhiteSpace($SessionToken)) {
    Write-Host "`n=== 2. VERIFIED ACCOUNT ALERT INBOX ===" -ForegroundColor Cyan
    $Headers = @{ "Authorization" = "Bearer $($SessionToken.Trim())" }
    $Inbox = Invoke-RestMethod `
        -Method Get `
        -Uri "$Base/api/applications/alerts" `
        -Headers $Headers `
        -TimeoutSec 90

    $Inbox | ConvertTo-Json -Depth 30
    Assert-True -Condition ($Inbox.ok -eq $true) -Message "Verified application alert inbox returned ok=false."
    Assert-True -Condition ($null -ne $Inbox.application_alerts) -Message "Verified alert inbox is missing application_alerts."
    Write-Host "Verified application alert inbox is available." -ForegroundColor Green
}
else {
    Write-Host "`nVerified alert inbox read was skipped because SessionToken was not supplied." -ForegroundColor Yellow
}

if (-not [string]::IsNullOrWhiteSpace($AdminKey)) {
    Write-Host "`n=== 3. PROTECTED APPLICATION ALERT ADMIN ===" -ForegroundColor Cyan
    $AdminHeaders = @{ "X-MoveReady-Admin-Key" = $AdminKey.Trim() }
    $AdminAlerts = Invoke-RestMethod `
        -Method Get `
        -Uri "$Base/api/admin/application-case-alerts?limit=100" `
        -Headers $AdminHeaders `
        -TimeoutSec 120

    $AdminAlerts | ConvertTo-Json -Depth 30
    Assert-True -Condition ($AdminAlerts.ok -eq $true) -Message "Protected application alert list returned ok=false."
    Assert-True -Condition ($null -ne $AdminAlerts.application_alerts) -Message "Protected alert list is missing application_alerts."

    if ($RunScan) {
        Write-Host "`n=== 4. RUN PROTECTED ALERT SCAN ===" -ForegroundColor Cyan
        $Scan = Invoke-RestMethod `
            -Method Post `
            -Uri "$Base/api/admin/application-cases/alerts/scan" `
            -Headers $AdminHeaders `
            -ContentType "application/json" `
            -Body "{}" `
            -TimeoutSec 240

        $Scan | ConvertTo-Json -Depth 40
        Assert-True -Condition ($Scan.ok -eq $true) -Message "Protected application alert scan returned ok=false."
        Assert-True -Condition (@("completed", "completed_with_errors") -contains $Scan.status) -Message "Unexpected scan status: $($Scan.status)"
        Assert-True -Condition (@($Scan.errors).Count -eq 0) -Message "Application alert scan returned case errors."
        Write-Host "Protected application alert scan completed." -ForegroundColor Green
    }
    else {
        Write-Host "`nApplication alert generation was skipped. Add -RunScan to test the mutating protected scan." -ForegroundColor Yellow
    }
}
else {
    Write-Host "`nProtected alert administration was skipped because AdminKey was not supplied." -ForegroundColor Yellow
}

Write-Host "`n=== APPLICATION ALERT RELEASE TEST PASSED ===" -ForegroundColor Green
Write-Host "This test does not dismiss, resolve, reopen, or create alerts unless -RunScan is supplied."
Write-Host "The daily workflow remains in-app only and does not activate email, WhatsApp, Telegram, or SMS delivery."
Write-Host "Apply migrations 028 and 029 before testing real alert storage. Do not paste session or admin keys into chat, screenshots, support cases, or GitHub issues."
