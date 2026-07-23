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
        -Body ($Body | ConvertTo-Json -Depth 20) `
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

Write-Host "`n=== 1. JOURNEY OPTIONS ===" -ForegroundColor Cyan
$Options = Invoke-MoveReadyJson -Method GET -Path "/api/journey/options"
$Options | ConvertTo-Json -Depth 20
Assert-True -Condition ($Options.ok -eq $true) -Message "Journey options returned ok=false."
Assert-True -Condition (@($Options.tools).Count -eq 4) -Message "Expected four journey tools."

Write-Host "`n=== 2. PLATFORM MODULE STATUS ===" -ForegroundColor Cyan
$Modules = Invoke-MoveReadyJson -Method GET -Path "/api/platform/modules"
$JourneySlugs = @(
    "journey-planner",
    "legalization",
    "appointments",
    "family-relocation",
    "settlement"
)
foreach ($Slug in $JourneySlugs) {
    $Module = @($Modules.modules | Where-Object { $_.slug -eq $Slug })[0]
    Assert-True -Condition ($null -ne $Module) -Message "Platform module missing: $Slug"
    Assert-True -Condition ($Module.availability -eq "available") -Message "Platform module is not available: $Slug"
}
Write-Host "Journey platform modules: available" -ForegroundColor Green

Write-Host "`n=== 3. LEGALIZATION PLANNER ===" -ForegroundColor Cyan
$Legalization = Invoke-MoveReadyJson `
    -Method POST `
    -Path "/api/journey/legalization-check" `
    -Body @{
        issuing_country = "Nigeria"
        receiving_country = "Finland"
        document_type = "academic_certificate"
        purpose = "Study or relocation application"
        days_until_submission = 30
        has_original_document = $true
        translation_needed = $true
        translation_completed = $false
        receiving_authority_checked = $false
        source_page = "/release-test"
    }
$Legalization | ConvertTo-Json -Depth 20
Assert-True -Condition ($Legalization.ok -eq $true) -Message "Legalization planner returned ok=false."
Assert-True -Condition (@($Legalization.steps).Count -ge 3) -Message "Legalization planner returned too few steps."
Assert-True -Condition (@("medium", "high") -contains $Legalization.risk_level) -Message "Legalization test did not detect the expected risk."

Write-Host "`n=== 4. FAMILY PLANNER ===" -ForegroundColor Cyan
$Family = Invoke-MoveReadyJson `
    -Method POST `
    -Path "/api/journey/family-plan" `
    -Body @{
        target_country = "Finland"
        route_category = "startup"
        spouse_count = 1
        children_count = 2
        child_ages = "11,8"
        other_dependants = 0
        base_budget_amount = 12000
        currency = "EUR"
        travelling_together = $true
        accommodation_confirmed = $false
        family_insurance_confirmed = $false
        source_page = "/release-test"
    }
$Family | ConvertTo-Json -Depth 20
Assert-True -Condition ($Family.ok -eq $true) -Message "Family planner returned ok=false."
Assert-True -Condition ([int]$Family.household_size -eq 4) -Message "Family planner household size is incorrect."
Assert-True -Condition ([int]$Family.school_age_children_count -eq 2) -Message "Family planner school-age count is incorrect."
Assert-True -Condition (@($Family.member_checklists).Count -eq 4) -Message "Family planner member checklist count is incorrect."

Write-Host "`n=== 5. APPOINTMENT PLANNER ===" -ForegroundColor Cyan
$AppointmentDate = (Get-Date).Date.AddDays(45).ToString("yyyy-MM-dd")
$Appointment = Invoke-MoveReadyJson `
    -Method POST `
    -Path "/api/journey/appointment-plan" `
    -Body @{
        appointment_date = $AppointmentDate
        application_type = "Biometrics"
        target_country = "Finland"
        current_country = "Kuwait"
        route_category = "startup"
        family_members_count = 0
        travel_time_hours = 2
        biometrics_required = $true
        original_documents_required = $true
        translation_pending = $false
        payment_pending = $false
        save_to_timeline = $false
        source_page = "/release-test"
    }
$Appointment | ConvertTo-Json -Depth 20
Assert-True -Condition ($Appointment.ok -eq $true) -Message "Appointment planner returned ok=false."
Assert-True -Condition (@($Appointment.tasks).Count -eq 6) -Message "Appointment planner should return six dated tasks."
Assert-True -Condition ([int]$Appointment.timeline_saved_count -eq 0) -Message "Release test unexpectedly saved appointment timeline events."

Write-Host "`n=== 6. SETTLEMENT PLANNER ===" -ForegroundColor Cyan
$Settlement = Invoke-MoveReadyJson `
    -Method POST `
    -Path "/api/journey/settlement-plan" `
    -Body @{
        target_country = "Finland"
        target_city = "Helsinki"
        arrival_date = (Get-Date).Date.AddDays(60).ToString("yyyy-MM-dd")
        household_size = 4
        pets_count = 0
        temporary_accommodation_confirmed = $false
        permanent_housing_confirmed = $false
        insurance_active = $false
        school_needed = $true
        employment_or_business_start_planned = $true
        medical_or_accessibility_need = $false
        save_to_timeline = $false
        consent_to_contact = $false
        source_page = "/release-test"
    }
$Settlement | ConvertTo-Json -Depth 30
Assert-True -Condition ($Settlement.ok -eq $true) -Message "Settlement planner returned ok=false."
$ExpectedGroups = @("before_travel", "first_72_hours", "first_2_weeks", "first_90_days")
foreach ($Group in $ExpectedGroups) {
    Assert-True -Condition ($null -ne $Settlement.timeline.$Group) -Message "Settlement timeline group missing: $Group"
}
Assert-True -Condition (@("medium", "high") -contains $Settlement.risk_level) -Message "Settlement test did not detect the expected risk."
Assert-True -Condition ([int]$Settlement.timeline_saved_count -eq 0) -Message "Release test unexpectedly saved settlement timeline events."
Assert-True -Condition ([int]$Settlement.timeline_existing_count -eq 0) -Message "Release test unexpectedly matched settlement timeline events."
Assert-True -Condition ($Settlement.timeline_storage_note -eq "Timeline saving was not requested.") -Message "Settlement timeline opt-in message is incorrect."
Assert-True -Condition (@($Settlement.fraud_checks).Count -ge 4) -Message "Settlement planner is missing fraud and safety checks."

Write-Host "`n=== JOURNEY PLANNER RELEASE TEST PASSED ===" -ForegroundColor Green
Write-Host "Options, platform status, legalization, family, appointment, and settlement endpoints are responding correctly."
Write-Host "This test intentionally does not create account timeline events or require an admin secret."
