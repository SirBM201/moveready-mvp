param(
    [string]$Base = "https://moveready-mvp-production.up.railway.app",
    [string]$SessionToken = "",
    [string]$TestEmail = ""
)

$ErrorActionPreference = "Stop"
$Base = $Base.TrimEnd("/")
$Results = @()
$DocumentId = $null
$PackId = $null
$CaseRef = $null
$OwnsSession = $false
$Headers = @{}
$Tag = "B03-LIFECYCLE-" + (Get-Date -Format "yyyyMMdd-HHmmss")

function Add-Result {
    param(
        [Parameter(Mandatory = $true)][string]$Test,
        [Parameter(Mandatory = $true)][ValidateSet("PASS", "FAIL")][string]$Result,
        [Parameter(Mandatory = $true)][string]$Detail
    )

    $script:Results += [pscustomobject]@{
        Test = $Test
        Result = $Result
        Detail = $Detail
    }
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

function ConvertFrom-SecureInput {
    param([Parameter(Mandatory = $true)][Security.SecureString]$SecureValue)

    $Pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureValue)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($Pointer)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($Pointer)
    }
}

function Get-HttpStatusFromError {
    param([Parameter(Mandatory = $true)]$ErrorRecord)

    try {
        if ($null -ne $ErrorRecord.Exception.Response) {
            return [int]$ErrorRecord.Exception.Response.StatusCode
        }
    }
    catch {
        return 0
    }
    return 0
}

function Call-Api {
    param(
        [Parameter(Mandatory = $true)][ValidateSet("GET", "POST", "PATCH")][string]$Method,
        [Parameter(Mandatory = $true)][string]$Path,
        $Body = $null
    )

    $Parameters = @{
        Method = $Method
        Uri = "$Base$Path"
        Headers = $script:Headers
        TimeoutSec = 90
    }
    if ($null -ne $Body) {
        $Parameters.ContentType = "application/json"
        $Parameters.Body = ($Body | ConvertTo-Json -Depth 30)
    }
    Invoke-RestMethod @Parameters
}

function Get-Id {
    param($Object)

    foreach ($Name in @("id", "document_id", "evidence_pack_id", "case_id", "application_case_id")) {
        if ($null -ne $Object.$Name -and "$($Object.$Name)" -ne "") {
            return "$($Object.$Name)"
        }
    }
    foreach ($Name in @("document", "evidence_document", "pack", "evidence_pack", "case", "application_case", "event")) {
        $Child = $Object.$Name
        if ($null -ne $Child -and $null -ne $Child.id) {
            return "$($Child.id)"
        }
    }
    return $null
}

function Get-CaseRef {
    param($Object)

    foreach ($Name in @("case_ref", "id")) {
        if ($null -ne $Object.$Name -and "$($Object.$Name)" -ne "") {
            return "$($Object.$Name)"
        }
    }
    foreach ($Name in @("application_case", "case")) {
        $Child = $Object.$Name
        if ($null -ne $Child) {
            if ($Child.case_ref) {
                return "$($Child.case_ref)"
            }
            if ($Child.id) {
                return "$($Child.id)"
            }
        }
    }
    return $null
}

function Test-AnonymousBarrier {
    param(
        [Parameter(Mandatory = $true)][string]$Test,
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
        Add-Result -Test $Test -Result "FAIL" -Detail "Anonymous request unexpectedly succeeded"
    }
    catch {
        $Status = Get-HttpStatusFromError -ErrorRecord $_
        if ($Status -eq 401) {
            Add-Result -Test $Test -Result "PASS" -Detail "Anonymous request rejected with HTTP 401"
        }
        else {
            Add-Result -Test $Test -Result "FAIL" -Detail "Expected HTTP 401; received $Status"
        }
    }
}

function Start-TestSession {
    if (-not [string]::IsNullOrWhiteSpace($script:SessionToken)) {
        $script:SessionToken = $script:SessionToken.Trim()
        return
    }

    if ([string]::IsNullOrWhiteSpace($script:TestEmail)) {
        Write-Host "Enter an active MoveReady session token. Input is hidden and the token is never printed." -ForegroundColor Yellow
        $SecureToken = Read-Host "Session token" -AsSecureString
        $script:SessionToken = ConvertFrom-SecureInput -SecureValue $SecureToken
        return
    }

    $Email = $script:TestEmail.Trim().ToLowerInvariant()
    Write-Host "Requesting one OTP through the configured MoveReady test-email provider..." -ForegroundColor Yellow
    $Request = Invoke-RestMethod `
        -Method Post `
        -Uri "$Base/api/auth/request-code" `
        -ContentType "application/json" `
        -Body (@{ email = $Email; source_page = "/b03-lifecycle-test" } | ConvertTo-Json -Depth 10) `
        -TimeoutSec 90
    Assert-True -Condition ($Request.ok -eq $true) -Message "OTP request returned ok=false."

    $SecureCode = Read-Host "Enter the six-digit OTP from the configured test inbox" -AsSecureString
    $Code = ConvertFrom-SecureInput -SecureValue $SecureCode
    Assert-True -Condition ($Code -match "^\d{6}$") -Message "A six-digit OTP is required."

    $Verified = Invoke-RestMethod `
        -Method Post `
        -Uri "$Base/api/auth/verify-code" `
        -ContentType "application/json" `
        -Body (@{ email = $Email; code = $Code } | ConvertTo-Json -Depth 10) `
        -TimeoutSec 90
    Assert-True -Condition ($Verified.ok -eq $true) -Message "OTP verification returned ok=false."
    Assert-True -Condition (-not [string]::IsNullOrWhiteSpace($Verified.session_token)) -Message "OTP verification returned no session token."
    $script:SessionToken = "$($Verified.session_token)"
    $script:OwnsSession = $true
}

Write-Host "`n=== MoveReady B03: Evidence -> Evidence Pack -> Application Case ===" -ForegroundColor Cyan

try {
    Start-TestSession
    Assert-True -Condition (-not [string]::IsNullOrWhiteSpace($SessionToken)) -Message "A MoveReady session token is required."
    $Headers = @{ Authorization = "Bearer $($SessionToken.Trim())" }

    $Health = Invoke-RestMethod -Method Get -Uri "$Base/api/health" -TimeoutSec 60
    Assert-True -Condition ($Health.ok -eq $true) -Message "Production health returned ok=false."
    $Commit = "$($Health.deployment.commit_short)"
    Add-Result -Test "Production Deployment" -Result "PASS" -Detail "Healthy deployment commit $Commit"

    $Me = Call-Api -Method GET -Path "/api/auth/me"
    Assert-True -Condition ($Me.ok -eq $true) -Message "Authenticated account check returned ok=false."
    Add-Result -Test "Authentication" -Result "PASS" -Detail "Verified account session accepted"

    $EvidenceOptions = Call-Api -Method GET -Path "/api/evidence/options"
    $ApplicationOptions = Call-Api -Method GET -Path "/api/applications/options"
    Assert-True -Condition ($EvidenceOptions.ok -eq $true) -Message "Evidence options returned ok=false."
    Assert-True -Condition (@($EvidenceOptions.document_types) -contains "passport") -Message "Evidence options are missing passport."
    Assert-True -Condition ($ApplicationOptions.ok -eq $true) -Message "Application options returned ok=false."
    foreach ($RequiredStage in @("research", "preparing", "closed")) {
        Assert-True -Condition (@($ApplicationOptions.application_stages) -contains $RequiredStage) -Message "Application options are missing $RequiredStage."
    }
    Add-Result -Test "Contracts" -Result "PASS" -Detail "Evidence and application contracts available"

    $DocBody = @{
        document_type = "passport"
        document_label = "$Tag passport metadata"
        owner_scope = "main_applicant"
        status = "available"
        translation_status = "not_required"
        legalization_status = "not_required"
        issuing_country = "NG"
        notes = "$Tag metadata-only production test"
        source_page = "/b03-lifecycle-test"
    }
    $Doc = Call-Api -Method POST -Path "/api/evidence/documents" -Body $DocBody
    Assert-True -Condition ($Doc.ok -eq $true) -Message "Evidence create returned ok=false."
    $DocumentId = Get-Id -Object $Doc
    Assert-True -Condition (-not [string]::IsNullOrWhiteSpace($DocumentId)) -Message "Evidence create returned no document ID."
    Add-Result -Test "Evidence Create" -Result "PASS" -Detail "Temporary metadata-only record created"

    $Docs = Call-Api -Method GET -Path "/api/evidence/documents"
    $FoundDoc = @(@($Docs.documents) | Where-Object { "$($_.id)" -eq $DocumentId })
    Assert-True -Condition ($FoundDoc.Count -eq 1) -Message "Created evidence metadata could not be read back exactly once."
    Add-Result -Test "Evidence Read" -Result "PASS" -Detail "Temporary evidence record retrieved"

    $PackBody = @{
        route_category = "startup"
        target_country = "Finland"
        application_stage = "preparation"
        official_source_notes = "$Tag functional test only; no immigration rule asserted"
        source_page = "/b03-lifecycle-test"
    }
    $Pack = Call-Api -Method POST -Path "/api/evidence/packs/generate" -Body $PackBody
    Assert-True -Condition ($Pack.ok -eq $true) -Message "Evidence pack generation returned ok=false."
    $PackId = Get-Id -Object $Pack
    Assert-True -Condition (-not [string]::IsNullOrWhiteSpace($PackId)) -Message "Evidence pack generation returned no pack ID."
    $Completeness = $Pack.completeness_score
    if ($null -eq $Completeness -and $Pack.evidence_pack) {
        $Completeness = $Pack.evidence_pack.completeness_score
    }
    Add-Result -Test "Evidence Pack Create" -Result "PASS" -Detail "Pack persisted; completeness=$Completeness"

    $Packs = Call-Api -Method GET -Path "/api/evidence/packs"
    $FoundPack = @(@($Packs.evidence_packs) | Where-Object { "$($_.id)" -eq $PackId })
    Assert-True -Condition ($FoundPack.Count -eq 1) -Message "Generated evidence pack could not be read back exactly once."
    Add-Result -Test "Evidence Pack Read" -Result "PASS" -Detail "Generated pack retrieved"

    $CaseBody = @{
        case_title = "$Tag Finland startup test case"
        target_country = "Finland"
        route_category = "startup"
        application_stage = "research"
        evidence_pack_id = $PackId
        notes = "$Tag temporary lifecycle test"
        consent_to_store = $true
        source_page = "/b03-lifecycle-test"
    }
    $Case = Call-Api -Method POST -Path "/api/applications" -Body $CaseBody
    Assert-True -Condition ($Case.ok -eq $true) -Message "Application case create returned ok=false."
    $CaseRef = Get-CaseRef -Object $Case
    Assert-True -Condition (-not [string]::IsNullOrWhiteSpace($CaseRef)) -Message "Application case create returned no case reference."
    Add-Result -Test "Case Create" -Result "PASS" -Detail "Temporary application case created"

    $Cases = Call-Api -Method GET -Path "/api/applications"
    $FoundCase = @(@($Cases.application_cases) | Where-Object { "$($_.case_ref)" -eq $CaseRef -or "$($_.id)" -eq $CaseRef })
    Assert-True -Condition ($FoundCase.Count -eq 1) -Message "Created application case could not be read back exactly once."
    Add-Result -Test "Case Read" -Result "PASS" -Detail "Application case retrieved"

    $Event = Call-Api -Method POST -Path "/api/applications/$CaseRef/events" -Body @{
        event_type = "note"
        event_status = "recorded"
        event_title = "$Tag lifecycle verification"
        event_summary = "$Tag metadata-only test event"
    }
    Assert-True -Condition ($Event.ok -eq $true) -Message "Explicit case event create returned ok=false."
    Assert-True -Condition (-not [string]::IsNullOrWhiteSpace((Get-Id -Object $Event))) -Message "Explicit case event create returned no event ID."
    Add-Result -Test "Case Event Create" -Result "PASS" -Detail "Explicit metadata-only event created"

    $Updated = Call-Api -Method PATCH -Path "/api/applications/$CaseRef" -Body @{
        application_stage = "preparing"
        notes = "$Tag transitioned by production lifecycle test"
        event_summary = "$Tag research to preparing"
    }
    $UpdatedStage = $Updated.application_stage
    if (-not $UpdatedStage -and $Updated.application_case) {
        $UpdatedStage = $Updated.application_case.application_stage
    }
    Assert-True -Condition ($UpdatedStage -eq "preparing") -Message "Case transition did not persist preparing stage. Actual=$UpdatedStage"
    Add-Result -Test "Case Transition" -Result "PASS" -Detail "research -> preparing persisted"

    $Detail = Call-Api -Method GET -Path "/api/applications/$CaseRef"
    $EventRows = @($Detail.events)
    Assert-True -Condition ($EventRows.Count -ge 3) -Message "Expected created, note, and transition events. Actual count=$($EventRows.Count)"
    Add-Result -Test "Case Events Read" -Result "PASS" -Detail "$($EventRows.Count) lifecycle events retrieved"

    Test-AnonymousBarrier -Test "Privacy: Documents Read" -Method GET -Path "/api/evidence/documents"
    Test-AnonymousBarrier -Test "Privacy: Packs Read" -Method GET -Path "/api/evidence/packs"
    Test-AnonymousBarrier -Test "Privacy: Pack Create" -Method POST -Path "/api/evidence/packs/generate" -Body @{
        route_category = "startup"
        target_country = "Finland"
        application_stage = "preparation"
    }
    Test-AnonymousBarrier -Test "Privacy: Cases Read" -Method GET -Path "/api/applications"
    Test-AnonymousBarrier -Test "Privacy: Case Create" -Method POST -Path "/api/applications" -Body @{
        case_title = "$Tag anonymous request"
        target_country = "Finland"
        route_category = "startup"
        application_stage = "research"
        consent_to_store = $true
    }
}
catch {
    Add-Result -Test "Lifecycle Execution" -Result "FAIL" -Detail $_.Exception.Message
}
finally {
    if ($CaseRef) {
        try {
            $Today = (Get-Date).ToString("yyyy-MM-dd")
            $Closed = Call-Api -Method PATCH -Path "/api/applications/$CaseRef" -Body @{
                application_stage = "closed"
                status = "archived"
                decision_date = $Today
                result_summary = "$Tag temporary functional test closed"
                notes = "$Tag cleanup"
                event_summary = "$Tag conservative cleanup"
            }
            $ClosedCase = $Closed.application_case
            Assert-True -Condition ($ClosedCase.application_stage -eq "closed") -Message "Temporary case did not close during cleanup."
            Assert-True -Condition ($ClosedCase.status -eq "archived") -Message "Temporary case did not archive during cleanup."
            Add-Result -Test "Case Cleanup" -Result "PASS" -Detail "Temporary case closed and archived"
        }
        catch {
            Add-Result -Test "Case Cleanup" -Result "FAIL" -Detail $_.Exception.Message
        }
    }

    if ($DocumentId) {
        try {
            $Archived = Call-Api -Method PATCH -Path "/api/evidence/documents/$DocumentId" -Body @{
                status = "archived"
                notes = "$Tag cleanup archived"
            }
            Assert-True -Condition ($Archived.document.status -eq "archived") -Message "Temporary evidence metadata did not archive during cleanup."
            Add-Result -Test "Evidence Cleanup" -Result "PASS" -Detail "Temporary evidence metadata archived"
        }
        catch {
            Add-Result -Test "Evidence Cleanup" -Result "FAIL" -Detail $_.Exception.Message
        }
    }

    if ($PackId) {
        Add-Result -Test "Pack Retention" -Result "PASS" -Detail "Pack retained as an immutable metadata-only audit snapshot"
    }

    if ($OwnsSession -and -not [string]::IsNullOrWhiteSpace($SessionToken)) {
        try {
            $Logout = Call-Api -Method POST -Path "/api/auth/logout" -Body @{}
            Assert-True -Condition ($Logout.ok -eq $true) -Message "Test session logout returned ok=false."
            Add-Result -Test "Test Session Cleanup" -Result "PASS" -Detail "OTP-created test session revoked"
        }
        catch {
            Add-Result -Test "Test Session Cleanup" -Result "FAIL" -Detail $_.Exception.Message
        }
    }
}

Write-Host "`n=== B03 RESULTS ===" -ForegroundColor Cyan
$Results | Format-Table Test, Result, Detail -AutoSize -Wrap
$Pass = @($Results | Where-Object Result -eq "PASS").Count
$Fail = @($Results | Where-Object Result -eq "FAIL").Count
Write-Host "PASS : $Pass" -ForegroundColor Green
Write-Host "FAIL : $Fail" -ForegroundColor Red
Write-Host "Session token and OTP were not printed. No raw document was uploaded or stored." -ForegroundColor Yellow

if ($Fail -gt 0) {
    throw "MoveReady B03 failed with $Fail failed assertion(s)."
}

Write-Host "[B03 PASS] Evidence -> Evidence Pack -> Application Case lifecycle is operational." -ForegroundColor Green
