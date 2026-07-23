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

    return Invoke-RestMethod `
        -Method Post `
        -Uri $Uri `
        -ContentType "application/json" `
        -Body (($Body ?? @{}) | ConvertTo-Json -Depth 20) `
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
        [Parameter(Mandatory = $true)][string]$Path
    )

    try {
        Invoke-RestMethod -Method Get -Uri "$Base$Path" -TimeoutSec 60 | Out-Null
        throw "Expected 401 for $Path, but the request succeeded."
    }
    catch {
        $Response = $_.Exception.Response
        if ($null -eq $Response -or [int]$Response.StatusCode -ne 401) {
            throw "Expected 401 for $Path. Actual error: $($_.Exception.Message)"
        }
    }
}

Write-Host "`n=== 1. PUBLIC OPERATIONS STATUS ===" -ForegroundColor Cyan
$Operations = Invoke-MoveReadyJson -Method GET -Path "/api/operations/status"
$Operations | ConvertTo-Json -Depth 20
Assert-True -Condition ($Operations.ok -eq $true) -Message "Operations status returned ok=false."
Assert-True -Condition ($null -ne $Operations.public_capabilities) -Message "Operations status did not return public capabilities."
Assert-True -Condition ($Operations.public_capabilities.provider_publication -eq "fail_closed_until_schema_and_admin_review_pass") -Message "Provider publication is not marked fail-closed."

Write-Host "`n=== 2. BILLING STATUS ===" -ForegroundColor Cyan
$BillingStatus = Invoke-MoveReadyJson -Method GET -Path "/api/billing/status"
$BillingStatus | ConvertTo-Json -Depth 20
Assert-True -Condition ($BillingStatus.ok -eq $true) -Message "Billing status returned ok=false."
Assert-True -Condition ($BillingStatus.commercial_quotes_enabled -eq $true) -Message "Commercial quote support is not enabled."
if ($BillingStatus.payment_links_enabled -eq $false) {
    Assert-True -Condition ($BillingStatus.checkout_mode -eq "disabled_until_payment_setup") -Message "Disabled payment links did not return the safe checkout mode."
}

Write-Host "`n=== 3. BILLING CATALOG ===" -ForegroundColor Cyan
$Catalog = Invoke-MoveReadyJson -Method GET -Path "/api/billing/catalog"
$Catalog | ConvertTo-Json -Depth 20
$CatalogSlugs = @($Catalog.catalog | ForEach-Object { $_.slug })
foreach ($Slug in @("readiness_report", "expert_review", "admission_support", "travel_booking", "legalization", "settlement")) {
    Assert-True -Condition ($CatalogSlugs -contains $Slug) -Message "Billing catalog is missing $Slug."
}

Write-Host "`n=== 4. PLATFORM MODULE ===" -ForegroundColor Cyan
$Modules = Invoke-MoveReadyJson -Method GET -Path "/api/platform/modules"
$BillingModule = @($Modules.modules | Where-Object { $_.slug -eq "billing" })[0]
Assert-True -Condition ($null -ne $BillingModule) -Message "Billing platform module is missing."
Assert-True -Condition ($BillingModule.availability -eq "available") -Message "Billing platform module is not available."

Write-Host "`n=== 5. PROVIDER DIRECTORY FAIL-CLOSED RESPONSE ===" -ForegroundColor Cyan
$Providers = Invoke-MoveReadyJson -Method GET -Path "/api/partners/approved"
$Providers | ConvertTo-Json -Depth 20
Assert-True -Condition ($Providers.ok -eq $true) -Message "Approved provider directory should fail closed with ok=true."
Assert-True -Condition ($null -ne $Providers.approved_providers) -Message "Approved provider directory did not return a provider array."
Assert-True -Condition (@("publication_controls_active", "publication_controls_pending_or_unavailable") -contains $Providers.source_status) -Message "Unexpected provider publication source status."

Write-Host "`n=== 6. PRIVATE ENDPOINTS REQUIRE AUTHENTICATION ===" -ForegroundColor Cyan
Assert-Unauthorized -Path "/api/billing/quotes"
Assert-Unauthorized -Path "/api/admin/operations/status"
Write-Host "Private billing and operations endpoints reject unauthenticated requests." -ForegroundColor Green

Write-Host "`n=== BILLING AND OPERATIONS RELEASE TEST PASSED ===" -ForegroundColor Green
Write-Host "Public operations, billing catalog, platform module, provider fail-closed behavior, and private endpoint protection are responding correctly."
Write-Host "Run migration 023 before testing quote creation, provider publication, payment events, or account quote recovery."
