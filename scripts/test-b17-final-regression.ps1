param(
    [string]$Base = "https://moveready-mvp-production.up.railway.app",
    [string]$ExpectedCommit = ""
)

$ErrorActionPreference = "Stop"
$Base = $Base.TrimEnd("/")

function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
}

Write-Host "`n=== MoveReady B17: Final Full Regression ===" -ForegroundColor Cyan
Write-Host "Read-only release gate: no schedules or external providers will be triggered." -ForegroundColor DarkGray

$Health = Invoke-RestMethod -Uri "$Base/health" -TimeoutSec 120
$ApiHealth = Invoke-RestMethod -Uri "$Base/api/health" -TimeoutSec 120
$Build = Invoke-RestMethod -Uri "$Base/api/build-info" -TimeoutSec 120

Assert-True ($Health.status -eq "ok" -or $Health.ok -eq $true) "/health is not healthy."
Assert-True ($ApiHealth.status -eq "ok" -or $ApiHealth.ok -eq $true) "/api/health is not healthy."
Assert-True ($Build.ok -eq $true) "Build-info returned ok=false."
Assert-True ($Build.contract_versions.operations -eq "b16-v1") "Production does not report operations contract b16-v1."
Assert-True ($Build.route_contract.ok -eq $true) "Production route contract failed."
Assert-True ($Build.operations_contract.admin_boundary.ok -eq $true) "Production admin-boundary contract failed."
Assert-True ($Build.operations_contract.schedule_count -eq 4) "Expected exactly four canonical scheduled jobs."
Assert-True ($Build.operations_contract.migration_ledger.latest_schema_file -eq "039_language_coach_backend_completion.sql") "Production migration frontier is not 039."

if (-not [string]::IsNullOrWhiteSpace($ExpectedCommit)) {
    Assert-True ($Build.deployment.commit_sha -eq $ExpectedCommit.Trim()) "Railway is not serving the expected commit."
}

$PublicOperations = Invoke-RestMethod -Uri "$Base/api/operations/status" -TimeoutSec 120
Assert-True ($PublicOperations.contract_version -eq "b16-v1") "Public operations endpoint is older than B16."
Assert-True ($PublicOperations.operations_contract.admin_boundary.ok -eq $true) "Public operations admin-boundary contract failed."

$SecureKey = Read-Host "Enter the Railway MOVEREADY_ADMIN_API_KEY" -AsSecureString
$Pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureKey)
try {
    $AdminKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($Pointer)
    Assert-True (-not [string]::IsNullOrWhiteSpace($AdminKey)) "Admin key is required for protected diagnostics."
    $Headers = @{ "X-MoveReady-Admin-Key" = $AdminKey }
    $Admin = Invoke-RestMethod -Uri "$Base/api/admin/operations/status" -Headers $Headers -TimeoutSec 180
}
finally {
    if ($Pointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($Pointer) }
    $AdminKey = $null
}

Assert-True ($Admin.ok -eq $true) "Protected operations endpoint returned ok=false."
Assert-True ($Admin.operations_contract.version -eq "b16-v1") "Protected operations endpoint is older than B16."
Assert-True ($Admin.operations_contract.admin_boundary.ok -eq $true) "Protected admin-boundary contract failed."
Assert-True ($Admin.configuration.environment_validation.status -ne "blocked") "Production environment validation is blocked: $($Admin.configuration.environment_validation.blocked_checks -join ', ')"
Assert-True ($Admin.launch_blockers.Count -eq 0) "Launch blockers reported: $($Admin.launch_blockers -join '; ')"
Assert-True ($Admin.optional_schema_ready -eq $true) "One or more Launch V1 schema checks failed."

Write-Host "Commit: $($Build.deployment.commit_short)" -ForegroundColor Green
Write-Host "Routes: $($Build.route_contract.expected_count) expected / $($Build.route_contract.registered_route_count) registered" -ForegroundColor Green
Write-Host "Admin routes protected: $($Build.operations_contract.admin_boundary.protected_route_count)" -ForegroundColor Green
Write-Host "Scheduled jobs: $($Build.operations_contract.schedule_count)" -ForegroundColor Green
Write-Host "Schema frontier: $($Build.operations_contract.migration_ledger.latest_schema_file)" -ForegroundColor Green
Write-Host "[B17 AUTOMATED PASS] Production release contracts are healthy." -ForegroundColor Green
Write-Host "Next: complete the bounded Vercel browser walkthrough in docs/B17_FINAL_REGRESSION.md before declaring release-ready." -ForegroundColor Yellow
