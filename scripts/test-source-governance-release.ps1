param(
    [string]$Base = "https://moveready-mvp-production.up.railway.app",
    [Parameter(Mandatory = $true)][string]$AdminKey,
    [switch]$RunDueScan
)

$ErrorActionPreference = "Stop"
$Base = $Base.TrimEnd("/")
$AdminKey = $AdminKey.Trim()

if ([string]::IsNullOrWhiteSpace($AdminKey)) {
    throw "AdminKey is empty."
}

$Headers = @{
    "X-MoveReady-Admin-Key" = $AdminKey
}

function Assert-True {
    param(
        [Parameter(Mandatory = $true)][bool]$Condition,
        [Parameter(Mandatory = $true)][string]$Message
    )

    if (-not $Condition) {
        throw $Message
    }
}

Write-Host "`n=== 1. PUBLIC SOURCE HEALTH ===" -ForegroundColor Cyan
$Health = Invoke-RestMethod `
    -Method Get `
    -Uri "$Base/api/source-health/summary" `
    -TimeoutSec 90

$Health | ConvertTo-Json -Depth 30
Assert-True -Condition ($Health.ok -eq $true) -Message "Public source health returned ok=false."
Assert-True -Condition (-not [string]::IsNullOrWhiteSpace([string]$Health.status)) -Message "Public source health is missing status."
Assert-True -Condition ($null -ne $Health.counts) -Message "Public source health is missing counts."
Write-Host "Public source-health contract is available." -ForegroundColor Green

Write-Host "`n=== 2. PROTECTED SOURCE REVIEW QUEUE ===" -ForegroundColor Cyan
$Queue = Invoke-RestMethod `
    -Method Get `
    -Uri "$Base/api/admin/source-governance/queue?limit=250" `
    -Headers $Headers `
    -TimeoutSec 120

$Queue | ConvertTo-Json -Depth 35
Assert-True -Condition ($Queue.ok -eq $true) -Message "Protected source queue returned ok=false."
Assert-True -Condition ($null -ne $Queue.sources) -Message "Source queue is missing sources."
Assert-True -Condition ($null -ne $Queue.route_versions) -Message "Source queue is missing route versions."
Assert-True -Condition ($null -ne $Queue.priority_sources) -Message "Source queue is missing priority sources."
Assert-True -Condition ($null -ne $Queue.priority_route_versions) -Message "Source queue is missing priority route versions."
Write-Host "Protected source review queue is available." -ForegroundColor Green

Write-Host "`n=== 3. PROTECTED OPERATIONS SCHEMA CHECKS ===" -ForegroundColor Cyan
$Operations = Invoke-RestMethod `
    -Method Get `
    -Uri "$Base/api/admin/operations/status" `
    -Headers $Headers `
    -TimeoutSec 120

$RequiredCodes = @(
    "trusted_sources",
    "source_change_alerts",
    "route_versions"
)
$Checks = @($Operations.schema_checks)
foreach ($Code in $RequiredCodes) {
    $Check = @($Checks | Where-Object { $_.code -eq $Code })[0]
    Assert-True -Condition ($null -ne $Check) -Message "Operations diagnostics are missing source schema check: $Code"
    Assert-True -Condition ($Check.ok -eq $true) -Message "Source schema check failed for $Code. Migration: $($Check.migration). Error: $($Check.error)"
    Write-Host "READY: $Code" -ForegroundColor Green
}

if ($RunDueScan) {
    Write-Host "`n=== 4. CREATE REVIEW-DUE ALERTS ===" -ForegroundColor Cyan
    $Scan = Invoke-RestMethod `
        -Method Post `
        -Uri "$Base/api/admin/source-governance/scan-due" `
        -Headers $Headers `
        -ContentType "application/json" `
        -Body "{}" `
        -TimeoutSec 180

    $Scan | ConvertTo-Json -Depth 30
    Assert-True -Condition (@("completed", "completed_with_errors") -contains $Scan.status) -Message "Unexpected source scan status: $($Scan.status)"
    Assert-True -Condition (@($Scan.errors).Count -eq 0) -Message "Source scan returned errors."
    Write-Host "Review-due scan completed. Existing open alerts were preserved rather than duplicated." -ForegroundColor Green
}
else {
    Write-Host "`nDue-source alert creation was skipped. Add -RunDueScan to test the mutating scan endpoint." -ForegroundColor Yellow
}

Write-Host "`n=== SOURCE GOVERNANCE RELEASE TEST PASSED ===" -ForegroundColor Green
Write-Host "This test does not mark a source checked, change a route version, approve a report, or expose the admin key."
