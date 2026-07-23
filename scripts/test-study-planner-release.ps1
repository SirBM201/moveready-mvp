param(
    [string]$Base = "https://moveready-mvp-production.up.railway.app"
)

$ErrorActionPreference = "Stop"
$Base = $Base.TrimEnd("/")

function Assert-True {
    param(
        [Parameter(Mandatory = $true)][bool]$Condition,
        [Parameter(Mandatory = $true)][string]$Message
    )
    if (-not $Condition) { throw $Message }
}

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
        -Body ($Body | ConvertTo-Json -Depth 20) `
        -TimeoutSec 90
}

Write-Host "`n=== 1. STUDY PLANNER OPTIONS ===" -ForegroundColor Cyan
$Options = Invoke-MoveReadyJson -Method GET -Path "/api/education/options"
$Options | ConvertTo-Json -Depth 20
Assert-True -Condition ($Options.ok -eq $true) -Message "Study Planner options returned ok=false."
Assert-True -Condition (@($Options.study_levels) -contains "masters") -Message "Master's level is missing from Study Planner options."
Assert-True -Condition (@($Options.grade_bands) -contains "pass") -Message "Pass grade band is missing from Study Planner options."

Write-Host "`n=== 2. STUDY PLAN RISK AND FUNDING TEST ===" -ForegroundColor Cyan
$IntakeDate = (Get-Date).Date.AddMonths(10).ToString("yyyy-MM-dd")
$Plan = Invoke-MoveReadyJson `
    -Method POST `
    -Path "/api/education/study-plan" `
    -Body @{
        current_country = "Kuwait"
        nationality = "Nigeria"
        target_country = "Finland"
        desired_level = "masters"
        highest_qualification = "BSc Computer Science"
        qualification_field = "Computer Science"
        graduation_year = 2015
        grade_band = "pass"
        desired_field = "Public Health"
        field_change = $true
        regulated_profession = $false
        language_evidence = "none"
        work_experience_years = 5
        available_funds_amount = 12000
        annual_tuition_budget = 13000
        annual_living_budget = 9000
        currency = "EUR"
        scholarship_required = $true
        family_members_count = 3
        prior_admission_refusal = $false
        prior_visa_refusal = $false
        target_intake_date = $IntakeDate
        source_page = "/release-test"
    }
$Plan | ConvertTo-Json -Depth 40

Assert-True -Condition ($Plan.ok -eq $true) -Message "Study Planner returned ok=false."
Assert-True -Condition (@("medium", "high") -contains $Plan.risk_level) -Message "Study Planner did not identify the expected preparation risk."
Assert-True -Condition ([double]$Plan.planning_funding_gap -eq 10000) -Message "Expected EUR 10,000 planning funding gap."
Assert-True -Condition (@($Plan.stages).Count -eq 7) -Message "Expected seven study-planning stages."
Assert-True -Condition (@($Plan.programme_strategy).Count -ge 3) -Message "Expected field-change programme strategy."
Assert-True -Condition (@($Plan.evidence_checklist).Count -ge 6) -Message "Expected study evidence checklist."
Assert-True -Condition (@($Plan.official_checks).Count -ge 6) -Message "Expected official-source checks."

$StrategyText = (@($Plan.programme_strategy) -join " ").ToLowerInvariant()
Assert-True -Condition ($StrategyText.Contains("conversion") -or $StrategyText.Contains("field change")) -Message "Field-change strategy was not returned."

Write-Host "`n=== 3. PLATFORM MODULE TEST ===" -ForegroundColor Cyan
$Modules = Invoke-MoveReadyJson -Method GET -Path "/api/platform/modules"
$StudyModule = @($Modules.modules | Where-Object { $_.slug -eq "study-planner" })[0]
Assert-True -Condition ($null -ne $StudyModule) -Message "Study Planner platform module is missing."
Assert-True -Condition ($StudyModule.availability -eq "available") -Message "Study Planner platform module is not available."
Assert-True -Condition ($StudyModule.enabled -eq $true) -Message "Study Planner platform module is not enabled."

Write-Host "`n=== STUDY PLANNER RELEASE TEST PASSED ===" -ForegroundColor Green
Write-Host "Options, academic risk, field change, funding gap, stages, evidence, official checks, and platform registration are responding correctly."
Write-Host "This test runs anonymously and therefore does not create a recoverable account-owned planning history."
