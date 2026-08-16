param(
    [Parameter(Mandatory=$true)][string]$Base,
    [Parameter(Mandatory=$true)][string]$SessionToken,
    [Parameter(Mandatory=$true)][string]$AdminKey
)

$ErrorActionPreference = 'Stop'
$Base = $Base.TrimEnd('/')
$UserHeaders = @{ Authorization = "Bearer $SessionToken" }
$AdminHeaders = @{ 'X-MoveReady-Admin-Key' = $AdminKey }
$Tag = "stage2e2-$([DateTime]::UtcNow.ToString('yyyyMMddHHmmss'))"
$Results = New-Object System.Collections.Generic.List[object]
$CaseRef = $null
$CaseId = $null
$AlertId = $null

function Add-Result([string]$Test,[string]$Result,[string]$Detail) {
    $Results.Add([pscustomobject]@{ Test=$Test; Result=$Result; Detail=$Detail })
}

function Call-Api([string]$Method,[string]$Path,$Body=$null,[hashtable]$Headers=$UserHeaders) {
    $p = @{ Uri="$Base$Path"; Method=$Method; Headers=$Headers; TimeoutSec=60 }
    if ($null -ne $Body) {
        $p.ContentType = 'application/json'
        $p.Body = ($Body | ConvertTo-Json -Depth 12)
    }
    Invoke-RestMethod @p
}

function Get-HttpStatus($ErrorRecord) {
    try { return [int]$ErrorRecord.Exception.Response.StatusCode.value__ } catch { return 0 }
}

Write-Host "`n=== MoveReady Stage 2E.2: Application Alert Lifecycle ===" -ForegroundColor Cyan

try {
    $Me = Call-Api GET '/api/auth/me'
    if (-not $Me.session.email) { throw 'Authenticated account email missing.' }
    Add-Result 'Authentication' 'PASS' 'Authenticated account verified'

    $AdminProbe = Call-Api GET '/api/admin/application-case-alerts?limit=1' $null $AdminHeaders
    if ($AdminProbe.ok -ne $true) { throw 'Admin alert endpoint did not return ok=true.' }
    Add-Result 'Admin Access' 'PASS' 'Protected alert administration verified'

    try {
        Invoke-RestMethod -Uri "$Base/api/admin/application-cases/alerts/scan" -Method POST -TimeoutSec 30 | Out-Null
        throw 'Anonymous admin scan unexpectedly succeeded.'
    } catch {
        $status = Get-HttpStatus $_
        if ($status -notin @(401,403)) { throw "Anonymous admin scan returned HTTP $status instead of 401/403." }
    }
    Add-Result 'Admin Privacy Barrier' 'PASS' 'Anonymous alert scan rejected'

    # Create a deterministic temporary case. 48h is safely inside the scanner's <=72h rule.
    $Deadline = [DateTime]::UtcNow.AddHours(48).ToString('o')
    $Created = Call-Api POST '/api/applications/cases' @{
        case_title = "$Tag controlled deadline alert test"
        target_country = 'Finland'
        route_category = 'startup'
        route_name = 'Controlled Stage 2E.2 test route'
        application_stage = 'research'
        status = 'active'
        source_status = 'verified'
        payment_status = 'not_required'
        next_deadline_at = $Deadline
        notes = 'Temporary metadata-only production test. Safe to archive.'
        source_page = 'stage-2e2-production-test'
        consent_to_store = $true
    }
    $CaseRef = $Created.application_case.case_ref
    $CaseId = $Created.application_case.id
    if (-not $CaseRef -or -not $CaseId) { throw 'Temporary case identifiers were not returned.' }
    Add-Result 'Case Create' 'PASS' "Temporary case created: $CaseRef"

    $Scan1 = Call-Api POST '/api/admin/application-cases/alerts/scan' $null $AdminHeaders
    if ($Scan1.ok -ne $true) { throw 'Alert scan did not return ok=true.' }
    Add-Result 'Alert Scan' 'PASS' "Scan completed; created=$($Scan1.alerts_created), updated=$($Scan1.alerts_updated)"

    $Inbox = Call-Api GET '/api/applications/alerts?include_dismissed=true'
    $Alert = @($Inbox.application_alerts | Where-Object {
        $_.application_case_id -eq $CaseId -and $_.alert_type -eq 'deadline_due_72h'
    }) | Select-Object -First 1
    if (-not $Alert) { throw 'Expected deadline_due_72h alert was not found in authenticated inbox.' }
    if ($Alert.status -ne 'open') { throw "Expected alert status open; got $($Alert.status)." }
    if ($Alert.severity -ne 'critical') { throw "Expected alert severity critical; got $($Alert.severity)." }
    $AlertId = $Alert.id
    Add-Result 'Alert Generation' 'PASS' 'deadline_due_72h critical alert appeared in authenticated inbox'

    $Dismissed = Call-Api PATCH "/api/applications/alerts/$AlertId" @{ status='dismissed' }
    if ($Dismissed.application_alert.status -ne 'dismissed') { throw 'Dismiss did not persist.' }
    Add-Result 'Alert Dismiss' 'PASS' 'User dismissed own alert'

    $Reopened = Call-Api PATCH "/api/applications/alerts/$AlertId" @{ status='open' }
    if ($Reopened.application_alert.status -ne 'open') { throw 'Reopen did not persist.' }
    Add-Result 'Alert Reopen' 'PASS' 'User reopened own alert'

    # Move the deadline beyond 14 days so the <=72h candidate becomes obsolete and no replacement deadline alert is generated.
    $SafeDeadline = [DateTime]::UtcNow.AddDays(30).ToString('o')
    $Updated = Call-Api PATCH "/api/applications/cases/$CaseRef" @{
        next_deadline_at = $SafeDeadline
        notes = 'Stage 2E.2 alert condition removed before cleanup.'
    }
    if (-not $Updated.application_case) { throw 'Case update did not return application_case.' }
    Add-Result 'Condition Removal' 'PASS' 'Deadline moved outside alert windows'

    $Scan2 = Call-Api POST '/api/admin/application-cases/alerts/scan' $null $AdminHeaders
    if ($Scan2.ok -ne $true) { throw 'Resolution scan did not return ok=true.' }

    $AdminAlerts = Call-Api GET "/api/admin/application-case-alerts?email=$([uri]::EscapeDataString($Me.session.email))&limit=250" $null $AdminHeaders
    $Resolved = @($AdminAlerts.application_alerts | Where-Object { $_.id -eq $AlertId }) | Select-Object -First 1
    if (-not $Resolved) { throw 'Generated alert could not be retrieved after resolution scan.' }
    if ($Resolved.status -ne 'resolved') { throw "Expected automatic status resolved; got $($Resolved.status)." }
    Add-Result 'Automatic Resolution' 'PASS' 'Obsolete generated alert automatically resolved'

    # Archive the temporary case. The scanner only considers active/attention_required/completed cases.
    $Archived = Call-Api PATCH "/api/applications/cases/$CaseRef" @{
        status = 'archived'
        notes = 'Stage 2E.2 controlled production test complete; temporary case archived.'
    }
    if ($Archived.application_case.status -ne 'archived') { throw 'Temporary case was not archived.' }
    Add-Result 'Case Cleanup' 'PASS' 'Temporary application case archived'
}
catch {
    Add-Result 'Lifecycle Execution' 'FAIL' $_.Exception.Message
}
finally {
    # Best-effort cleanup if the main flow failed after creating the case.
    if ($CaseRef) {
        try {
            $Current = Call-Api GET "/api/applications/cases/$CaseRef"
            if ($Current.application_case.status -ne 'archived') {
                Call-Api PATCH "/api/applications/cases/$CaseRef" @{
                    status='archived'
                    notes='Stage 2E.2 best-effort cleanup after test execution.'
                } | Out-Null
                if (-not ($Results | Where-Object { $_.Test -eq 'Case Cleanup' })) {
                    Add-Result 'Case Cleanup' 'PASS' 'Temporary application case archived during best-effort cleanup'
                }
            }
        } catch {
            if (-not ($Results | Where-Object { $_.Test -eq 'Case Cleanup' })) {
                Add-Result 'Case Cleanup' 'FAIL' "Best-effort archive failed: $($_.Exception.Message)"
            }
        }
    }

    $SessionToken = $null
    $AdminKey = $null
    $UserHeaders = $null
    $AdminHeaders = $null
}

Write-Host "`n=== STAGE 2E.2 RESULTS ===" -ForegroundColor Cyan
$Results | Format-Table -AutoSize
$Pass = @($Results | Where-Object Result -eq 'PASS').Count
$Fail = @($Results | Where-Object Result -eq 'FAIL').Count
Write-Host "`nPASS : $Pass" -ForegroundColor Green
if ($Fail -eq 0) {
    Write-Host 'FAIL : 0' -ForegroundColor Green
    Write-Host '[STAGE 2E.2 PASS] Application alert generation -> inbox -> dismiss -> reopen -> automatic resolution lifecycle is operational.' -ForegroundColor Green
} else {
    Write-Host "FAIL : $Fail" -ForegroundColor Red
    Write-Host '[STAGE 2E.2 ACTION REQUIRED] One or more alert lifecycle assertions failed.' -ForegroundColor Yellow
}
Write-Host 'Session and admin tokens were not printed. Temporary application case was archived where creation succeeded.' -ForegroundColor DarkGray

if ($Fail -gt 0) { exit 1 }
