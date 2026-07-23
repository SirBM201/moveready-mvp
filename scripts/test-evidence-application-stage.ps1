param(
    [string]$Base = "https://moveready-mvp-production.up.railway.app",
    [string]$SessionToken = "",
    [Parameter(Mandatory = $true)][string]$AdminKey,
    [switch]$RunSourceScan,
    [switch]$RunApplicationAlertScan
)

$ErrorActionPreference = "Stop"
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

function Invoke-StageScript {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Path,
        [hashtable]$Arguments
    )

    Write-Host "`n============================================================" -ForegroundColor Cyan
    Write-Host $Name -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan

    $Resolved = Join-Path $ScriptRoot $Path
    if (-not (Test-Path $Resolved)) {
        throw "Required release script is missing: $Resolved"
    }

    & $Resolved @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE."
    }
}

$Base = $Base.TrimEnd("/")
$AdminKey = $AdminKey.Trim()
if ([string]::IsNullOrWhiteSpace($AdminKey)) {
    throw "AdminKey is required. Read it securely with Read-Host and do not paste it into chat, screenshots, issues, logs, or repository files."
}

Invoke-StageScript `
    -Name "1. Protected operations and schema readiness through migration 030" `
    -Path "test-operations-admin.ps1" `
    -Arguments @{ Base = $Base; AdminKey = $AdminKey }

Invoke-StageScript `
    -Name "2. Evidence Center privacy and route barriers" `
    -Path "test-evidence-release.ps1" `
    -Arguments @{
        Base = $Base
        SessionToken = $SessionToken
    }

Invoke-StageScript `
    -Name "3. Source Governance and source health" `
    -Path "test-source-governance-release.ps1" `
    -Arguments @{
        Base = $Base
        AdminKey = $AdminKey
        RunDueScan = $RunSourceScan
    }

Invoke-StageScript `
    -Name "4. Application Case Manager" `
    -Path "test-application-cases-release.ps1" `
    -Arguments @{
        Base = $Base
        SessionToken = $SessionToken
        AdminKey = $AdminKey
    }

Invoke-StageScript `
    -Name "5. Application case alerts" `
    -Path "test-application-alerts-release.ps1" `
    -Arguments @{
        Base = $Base
        SessionToken = $SessionToken
        AdminKey = $AdminKey
        RunScan = $RunApplicationAlertScan
    }

Invoke-StageScript `
    -Name "6. Account settings, sessions, activity, export, and privacy" `
    -Path "test-account-controls-release.ps1" `
    -Arguments @{
        Base = $Base
        SessionToken = $SessionToken
        AdminKey = $AdminKey
    }

Invoke-StageScript `
    -Name "7. Journey and settlement timeline" `
    -Path "test-journey-planner-release.ps1" `
    -Arguments @{ Base = $Base }

Write-Host "`n============================================================" -ForegroundColor Green
Write-Host "MOVEREADY PRIVATE WORKFLOW RELEASE STAGE PASSED" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host "Verified: protected schemas through migration 030, Evidence Center, Source Governance, Application Case Manager, private application alerts, account settings, sessions, activity, safe export, privacy requests, and settlement planning." -ForegroundColor Green
Write-Host "Mutating scans run only when -RunSourceScan or -RunApplicationAlertScan is supplied." -ForegroundColor Yellow
Write-Host "External email, WhatsApp, Telegram, SMS, push delivery, payment links, provider approval, automatic account deletion, and raw-document storage are not activated by this command." -ForegroundColor Yellow
