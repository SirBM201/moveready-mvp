param(
    [string]$Base = "https://moveready-mvp-production.up.railway.app"
)

$ErrorActionPreference = "Stop"
$Base = $Base.TrimEnd("/")

function Invoke-MoveReadyJson {
    param(
        [Parameter(Mandatory = $true)][ValidateSet("GET", "POST")][string]$Method,
        [Parameter(Mandatory = $true)][string]$Path,
        [hashtable]$Body
    )

    $Uri = "$Base$Path"
    if ($Method -eq "GET") {
        return Invoke-RestMethod -Method Get -Uri $Uri -TimeoutSec 60
    }

    $Payload = @{}
    if ($null -ne $Body) {
        $Payload = $Body
    }

    return Invoke-RestMethod `
        -Method Post `
        -Uri $Uri `
        -ContentType "application/json" `
        -Body ($Payload | ConvertTo-Json -Depth 30) `
        -TimeoutSec 90
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

function Assert-Unauthorized {
    param(
        [Parameter(Mandatory = $true)][ValidateSet("GET", "POST")][string]$Method,
        [Parameter(Mandatory = $true)][string]$Path,
        [hashtable]$Body
    )

    try {
        if ($Method -eq "GET") {
            Invoke-RestMethod -Method Get -Uri "$Base$Path" -TimeoutSec 60 | Out-Null
        }
        else {
            $Payload = @{}
            if ($null -ne $Body) {
                $Payload = $Body
            }
            Invoke-RestMethod `
                -Method Post `
                -Uri "$Base$Path" `
                -ContentType "application/json" `
                -Body ($Payload | ConvertTo-Json -Depth 20) `
                -TimeoutSec 60 | Out-Null
        }
        throw "Expected 401 for $Method $Path, but the request succeeded."
    }
    catch {
        $Response = $_.Exception.Response
        if ($null -eq $Response -or [int]$Response.StatusCode -ne 401) {
            throw "Expected 401 for $Method $Path. Actual error: $($_.Exception.Message)"
        }
    }
}

Write-Host "`n=== 1. PUBLIC OPERATIONS STATUS ===" -ForegroundColor Cyan
$Operations = Invoke-MoveReadyJson -Method GET -Path "/api/operations/status"
$Operations | ConvertTo-Json -Depth 30
Assert-True -Condition ($Operations.ok -eq $true) -Message "Operations status returned ok=false."
Assert-True -Condition ($Operations.public_capabilities.provider_handoffs -like "consent_required*") -Message "Provider handoffs are not marked consent-controlled and fail-closed."
Assert-True -Condition ($Operations.public_capabilities.provider_publication -eq "fail_closed_until_schema_and_admin_review_pass") -Message "Provider publication is not marked fail-closed."

Write-Host "`n=== 2. PRIVATE HANDOFF ENDPOINTS ===" -ForegroundColor Cyan
Assert-Unauthorized -Method GET -Path "/api/handoffs"
Assert-Unauthorized -Method GET -Path "/api/service-handoffs"
Assert-Unauthorized -Method GET -Path "/api/handoffs/support-cases"
Assert-Unauthorized -Method POST -Path "/api/handoffs/MRH-TEST/consent" -Body @{
    confirm_share = $true
    consent_version = "moveready-provider-handoff-2026-07-23-v1"
    acknowledged_fields = @("full_name", "email")
    provider_identity_reviewed = $true
    no_unlisted_documents_understood = $true
}
Assert-Unauthorized -Method POST -Path "/api/handoffs/MRH-TEST/decline" -Body @{ reason = "Release test" }
Write-Host "Verified-account handoff endpoints and compatibility alias reject anonymous requests." -ForegroundColor Green

Write-Host "`n=== 3. PROTECTED ADMIN HANDOFF ENDPOINTS ===" -ForegroundColor Cyan
Assert-Unauthorized -Method GET -Path "/api/admin/service-handoffs"
Assert-Unauthorized -Method GET -Path "/api/admin/support-cases"
Assert-Unauthorized -Method GET -Path "/api/admin/operations/status"
Write-Host "Admin handoff, support-case, and diagnostics endpoints reject requests without the admin key." -ForegroundColor Green

Write-Host "`n=== 4. PLATFORM AND DIRECTORY SAFETY ===" -ForegroundColor Cyan
$Modules = Invoke-MoveReadyJson -Method GET -Path "/api/platform/modules"
Assert-True -Condition ($Modules.ok -eq $true) -Message "Platform module endpoint returned ok=false."

$Providers = Invoke-MoveReadyJson -Method GET -Path "/api/partners/approved"
$Providers | ConvertTo-Json -Depth 20
Assert-True -Condition ($Providers.ok -eq $true) -Message "Provider directory should fail closed with ok=true."
Assert-True -Condition (@("publication_controls_active", "publication_controls_pending_or_unavailable") -contains $Providers.source_status) -Message "Unexpected provider publication source status."

Write-Host "`n=== HANDOFF AND SUPPORT RELEASE TEST PASSED ===" -ForegroundColor Green
Write-Host "Public operations status, account protection, admin protection, handoff aliases, and provider publication behavior are responding correctly."
Write-Host "Apply migrations 025 and 026 before testing real handoff creation, exact-field consent, delivery references, complaints, refunds, disputes, or terminal case resolution."
