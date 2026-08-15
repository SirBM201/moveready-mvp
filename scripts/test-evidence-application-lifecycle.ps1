param(
    [string]$Base = "https://moveready-mvp-production.up.railway.app",
    [Parameter(Mandatory = $true)][string]$SessionToken
)

$ErrorActionPreference = "Stop"
$Base = $Base.TrimEnd("/")
$Headers = @{ Authorization = "Bearer $($SessionToken.Trim())" }
$Tag = "STAGE2D-TEST-" + (Get-Date -Format "yyyyMMdd-HHmmss")
$Results = @()

function Add-Result([string]$Test,[string]$Result,[string]$Detail) {
    $script:Results += [pscustomobject]@{ Test=$Test; Result=$Result; Detail=$Detail }
}
function Call-Api([string]$Method,[string]$Path,$Body=$null) {
    $p = @{ Method=$Method; Uri="$Base$Path"; Headers=$Headers; TimeoutSec=90 }
    if ($null -ne $Body) { $p.ContentType="application/json"; $p.Body=($Body | ConvertTo-Json -Depth 30) }
    Invoke-RestMethod @p
}
function Get-Id($Object) {
    foreach ($name in @('id','document_id','evidence_pack_id','case_id','application_case_id')) {
        if ($null -ne $Object.$name -and "$($Object.$name)" -ne '') { return "$($Object.$name)" }
    }
    foreach ($name in @('document','evidence_document','pack','evidence_pack','case','application_case')) {
        $child=$Object.$name
        if ($null -ne $child -and $null -ne $child.id) { return "$($child.id)" }
    }
    return $null
}

Write-Host "`n=== MoveReady Stage 2D: Evidence -> Pack -> Application Case ===" -ForegroundColor Cyan

try {
    $Me=Call-Api GET '/api/auth/me'
    Add-Result 'Authentication' 'PASS' 'Authenticated account verified'
} catch { Write-Host '[STOP] Session token invalid/expired.' -ForegroundColor Red; throw }

# Discover supported contracts before mutation.
$EvidenceOptions=Call-Api GET '/api/evidence/options'
$ApplicationOptions=Call-Api GET '/api/applications/options'
Add-Result 'Contracts' 'PASS' 'Evidence and application option contracts available'

# Create metadata-only evidence. No document/passport/bank numbers or raw files.
$DocBody=@{
    document_type='passport'; label="$Tag passport metadata"; status='available';
    issuing_country='NG'; notes="$Tag metadata-only functional test"; source_page='/stage2d-test'
}
$Doc=Call-Api POST '/api/evidence/documents' $DocBody
$DocumentId=Get-Id $Doc
if (-not $DocumentId) { throw 'Evidence create succeeded but no document ID was returned.' }
Add-Result 'Evidence Create' 'PASS' 'Temporary metadata record created'

$Docs=Call-Api GET '/api/evidence/documents'
$DocRows=@($Docs.documents) + @($Docs.evidence_documents)
$FoundDoc=@($DocRows | Where-Object { "$($_.id)" -eq $DocumentId })
if ($FoundDoc.Count -lt 1) { throw 'Created evidence metadata could not be read back.' }
Add-Result 'Evidence Read' 'PASS' 'Temporary metadata record retrieved'

# Generate and persist evidence pack from authenticated inventory.
$PackBody=@{ route_category='startup'; target_country='Finland'; application_stage='preparation'; source_page='/stage2d-test' }
$Pack=Call-Api POST '/api/evidence/packs/generate' $PackBody
$PackId=Get-Id $Pack
if (-not $PackId) { throw 'Evidence pack generation returned no pack ID.' }
Add-Result 'Evidence Pack' 'PASS' "Pack persisted; completeness=$($Pack.completeness_percent)"

$Packs=Call-Api GET '/api/evidence/packs'
$PackRows=@($Packs.packs) + @($Packs.evidence_packs)
$FoundPack=@($PackRows | Where-Object { "$($_.id)" -eq $PackId })
if ($FoundPack.Count -lt 1) { throw 'Generated evidence pack could not be read back.' }
Add-Result 'Evidence Pack Read' 'PASS' 'Generated pack retrieved'

# Application case payload uses only non-sensitive test metadata.
$CaseBody=@{
    title="$Tag Finland startup test case"; target_country='Finland'; route_category='startup';
    application_stage='research'; evidence_pack_id=$PackId; notes="$Tag temporary lifecycle test";
    consent_to_store=$true; source_page='/stage2d-test'
}
$Case=Call-Api POST '/api/applications/cases' $CaseBody
$CaseId=Get-Id $Case
if (-not $CaseId) { throw 'Application case create returned no case ID.' }
Add-Result 'Case Create' 'PASS' 'Temporary application case created'

$Cases=Call-Api GET '/api/applications/cases'
$CaseRows=@($Cases.cases) + @($Cases.application_cases)
$FoundCase=@($CaseRows | Where-Object { "$($_.id)" -eq $CaseId })
if ($FoundCase.Count -lt 1) { throw 'Created application case could not be read back.' }
Add-Result 'Case Read' 'PASS' 'Application case retrieved'

# Attempt one documented forward lifecycle transition. If contract exposes stages, prefer preparation.
$PatchBody=@{ application_stage='preparation'; notes="$Tag transitioned by production lifecycle test" }
$Updated=Call-Api PATCH "/api/applications/cases/$CaseId" $PatchBody
$UpdatedStage=$Updated.application_stage
if (-not $UpdatedStage -and $Updated.application_case) { $UpdatedStage=$Updated.application_case.application_stage }
if (-not $UpdatedStage -and $Updated.case) { $UpdatedStage=$Updated.case.application_stage }
if ($UpdatedStage -ne 'preparation') { throw "Case transition did not persist preparation stage. Actual=$UpdatedStage" }
Add-Result 'Case Transition' 'PASS' 'research -> preparation persisted'

# Case events/timeline read. Accept the endpoint only if it exists and returns an authenticated contract.
try {
    $Events=Call-Api GET "/api/applications/cases/$CaseId/events"
    $EventRows=@($Events.events) + @($Events.case_events)
    if ($EventRows.Count -gt 0) { Add-Result 'Case Events' 'PASS' "$($EventRows.Count) case event(s) retrieved" }
    else { Add-Result 'Case Events' 'PASS' 'Event endpoint available; zero rows returned' }
} catch {
    Add-Result 'Case Events' 'FAIL' $_.Exception.Message
}

# Anonymous privacy barrier.
try {
    Invoke-RestMethod -Method GET -Uri "$Base/api/evidence/documents" -TimeoutSec 60 | Out-Null
    Add-Result 'Privacy Barrier' 'FAIL' 'Anonymous evidence read unexpectedly succeeded'
} catch {
    $status=0; try { $status=[int]$_.Exception.Response.StatusCode } catch {}
    if ($status -eq 401) { Add-Result 'Privacy Barrier' 'PASS' 'Anonymous private read rejected with HTTP 401' }
    else { Add-Result 'Privacy Barrier' 'FAIL' "Expected HTTP 401; got $status" }
}

# Cleanup is conservative: archive/close only through supported PATCH semantics; never DELETE.
try {
    $Closed=Call-Api PATCH "/api/applications/cases/$CaseId" @{ application_stage='closed'; notes="$Tag cleanup" }
    Add-Result 'Case Cleanup' 'PASS' 'Temporary case closed'
} catch { Add-Result 'Case Cleanup' 'FAIL' $_.Exception.Message }

try {
    $Archived=Call-Api PATCH "/api/evidence/documents/$DocumentId" @{ status='archived'; notes="$Tag cleanup archived" }
    Add-Result 'Evidence Cleanup' 'PASS' 'Temporary evidence metadata archived'
} catch { Add-Result 'Evidence Cleanup' 'FAIL' $_.Exception.Message }

Write-Host "`n=== STAGE 2D RESULTS ===" -ForegroundColor Cyan
$Results | Format-Table Test,Result,Detail -AutoSize
$Pass=@($Results | Where-Object Result -eq 'PASS').Count
$Fail=@($Results | Where-Object Result -eq 'FAIL').Count
Write-Host "PASS : $Pass" -ForegroundColor Green
Write-Host "FAIL : $Fail" -ForegroundColor Red
if ($Fail -eq 0) { Write-Host '[STAGE 2D PASS] Evidence -> Pack -> Application Case lifecycle is operational.' -ForegroundColor Green }
else { Write-Host '[STAGE 2D ACTION REQUIRED] One or more lifecycle assertions failed.' -ForegroundColor Red }
Write-Host 'Session token was not printed. Temporary case was closed and evidence metadata archived where supported.' -ForegroundColor Yellow
