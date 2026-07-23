param(
    [string]$Base = "https://moveready-mvp-production.up.railway.app",
    [string]$SessionToken = ""
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
        try {
            return [int]$ErrorRecord.Exception.Response.StatusCode
        }
        catch {
            return 0
        }
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
            if ($null -ne $Body) {
                $Payload = $Body
            }
            $Parameters.ContentType = "application/json"
            $Parameters.Body = ($Payload | ConvertTo-Json -Depth 30)
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

Write-Host "`n=== 1. EVIDENCE OPTIONS ===" -ForegroundColor Cyan
$Options = Invoke-RestMethod `
    -Method Get `
    -Uri "$Base/api/evidence/options" `
    -TimeoutSec 60

$Options | ConvertTo-Json -Depth 30
Assert-True -Condition ($Options.ok -eq $true) -Message "Evidence options returned ok=false."
Assert-True -Condition (@($Options.document_types) -contains "passport") -Message "Evidence options are missing passport."
Assert-True -Condition (@($Options.refusal_event_types) -contains "denied_admission") -Message "Evidence options are missing denied_admission."
Assert-True -Condition (@($Options.visa_statuses) -contains "cancelled") -Message "Evidence options are missing cancelled visa status."
$ReasonKeys = @($Options.refusal_reason_options | ForEach-Object { $_.key })
Assert-True -Condition ($ReasonKeys -contains "misrepresentation_concern") -Message "Evidence options are missing the misrepresentation safety category."
Write-Host "Evidence options and safety categories are available." -ForegroundColor Green

Write-Host "`n=== 2. PRIVATE ROUTE BARRIERS ===" -ForegroundColor Cyan
Assert-Unauthorized -Method GET -Path "/api/evidence/documents"
Assert-Unauthorized -Method GET -Path "/api/evidence/packs"
Assert-Unauthorized -Method POST -Path "/api/evidence/packs/generate" -Body @{
    route_category = "startup"
    target_country = "Finland"
    application_stage = "preparation"
}
Assert-Unauthorized -Method POST -Path "/api/evidence/refusal-repair" -Body @{
    event_type = "denied_admission"
    visa_status_after_event = "unknown"
}
Write-Host "Private evidence routes reject anonymous access." -ForegroundColor Green

Write-Host "`n=== 3. PUBLIC OPERATIONS CONTRACT ===" -ForegroundColor Cyan
$Operations = Invoke-RestMethod `
    -Method Get `
    -Uri "$Base/api/operations/status" `
    -TimeoutSec 60

$Operations | ConvertTo-Json -Depth 30
Assert-True -Condition ($Operations.ok -eq $true) -Message "Operations status returned ok=false."
Assert-True -Condition ($Operations.public_capabilities.source_freshness -eq $true) -Message "Source freshness is not exposed in the operations contract."
Assert-True -Condition ($Operations.public_capabilities.private_evidence_pack -eq "verified_account_only_after_migration_027") -Message "Evidence-pack availability contract is incorrect."
Assert-True -Condition ($Operations.public_capabilities.refusal_repair -eq "verified_account_only_and_no_raw_documents") -Message "Refusal-repair safety contract is incorrect."

if (-not [string]::IsNullOrWhiteSpace($SessionToken)) {
    Write-Host "`n=== 4. VERIFIED ACCOUNT READ TEST ===" -ForegroundColor Cyan
    $Headers = @{
        "Authorization" = "Bearer $($SessionToken.Trim())"
    }

    $Documents = Invoke-RestMethod `
        -Method Get `
        -Uri "$Base/api/evidence/documents" `
        -Headers $Headers `
        -TimeoutSec 90

    $Packs = Invoke-RestMethod `
        -Method Get `
        -Uri "$Base/api/evidence/packs" `
        -Headers $Headers `
        -TimeoutSec 90

    Assert-True -Condition ($Documents.ok -eq $true) -Message "Verified document inventory read returned ok=false."
    Assert-True -Condition ($Packs.ok -eq $true) -Message "Verified evidence-pack read returned ok=false."
    Write-Host "Verified account evidence reads succeeded." -ForegroundColor Green
}
else {
    Write-Host "`nVerified account reads were skipped because SessionToken was not supplied." -ForegroundColor Yellow
}

Write-Host "`n=== EVIDENCE CENTER RELEASE TEST PASSED ===" -ForegroundColor Green
Write-Host "This test does not upload documents, create evidence records, submit refusal text, or print a session token."
Write-Host "Apply migration 027 before testing real document metadata or evidence-pack storage."
