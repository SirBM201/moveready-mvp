param(
    [string]$Base = "https://moveready-mvp-production.up.railway.app"
)

$ErrorActionPreference = "Stop"
$Base = $Base.TrimEnd("/")

function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
}

function Invoke-MoveReadyJson {
    param([ValidateSet("GET", "POST")][string]$Method, [string]$Path, [hashtable]$Body)
    $Uri = "$Base$Path"
    if ($Method -eq "GET") {
        return Invoke-RestMethod -Method Get -Uri $Uri -TimeoutSec 60
    }
    return Invoke-RestMethod -Method Post -Uri $Uri -ContentType "application/json" -Body ($Body | ConvertTo-Json -Depth 20) -TimeoutSec 90
}

Write-Host "`n=== 1. TRIP PLANNER OPTIONS ===" -ForegroundColor Cyan
$Options = Invoke-MoveReadyJson -Method GET -Path "/api/travel/options"
$Options | ConvertTo-Json -Depth 20
Assert-True ($Options.ok -eq $true) "Trip Planner options returned ok=false."
Assert-True (@($Options.booking_needs) -contains "flight") "Flight is missing from booking needs."
Assert-True (@($Options.booking_needs) -contains "hotel") "Hotel is missing from booking needs."

Write-Host "`n=== 2. HIGH-RISK BOOKING GATE ===" -ForegroundColor Cyan
$Departure = (Get-Date).Date.AddDays(30).ToString("yyyy-MM-dd")
$Return = (Get-Date).Date.AddDays(40).ToString("yyyy-MM-dd")
$Plan = Invoke-MoveReadyJson -Method POST -Path "/api/travel/trip-plan" -Body @{
    departure_country = "Kuwait"
    destination_country = "Mexico"
    destination_city = "Mexico City"
    passport_country = "Nigeria"
    trip_purpose = "tourism"
    departure_date = $Departure
    return_date = $Return
    adults = 1
    children = 0
    infants = 0
    booking_needs = @("flight", "hotel", "travel_insurance")
    passport_valid_months = 4
    destination_entry_rule_checked = $false
    visa_or_authorization_confirmed = $false
    transit_rule_checked = $false
    travel_insurance_confirmed = $false
    accommodation_confirmed = $false
    onward_or_return_ticket_planned = $false
    funds_plan_confirmed = $false
    prior_refusal_or_denied_admission = $true
    visa_validity_uncertain = $true
    special_medical_or_accessibility_need = $false
    trip_budget_amount = 2500
    currency = "USD"
    source_page = "/release-test"
}
$Plan | ConvertTo-Json -Depth 40
Assert-True ($Plan.ok -eq $true) "Trip Planner returned ok=false."
Assert-True ($Plan.risk_level -eq "high") "Expected high booking risk."
Assert-True ($Plan.readiness_status -eq "not_ready_to_book") "Expected not_ready_to_book status."
Assert-True (@($Plan.warnings).Count -ge 7) "Expected at least seven warnings."
Assert-True (@($Plan.booking_sequence).Count -eq 5) "Expected five booking stages."
Assert-True ($Plan.affiliate_disclosure.ToLowerInvariant().Contains("commission")) "Affiliate commission disclosure is missing."

Write-Host "`n=== 3. PLATFORM MODULE ===" -ForegroundColor Cyan
$Modules = Invoke-MoveReadyJson -Method GET -Path "/api/platform/modules"
$TripModule = @($Modules.modules | Where-Object { $_.slug -eq "trip-planner" })[0]
Assert-True ($null -ne $TripModule) "Trip Planner module is missing."
Assert-True ($TripModule.availability -eq "available") "Trip Planner module is not available."
Assert-True ($TripModule.enabled -eq $true) "Trip Planner module is not enabled."

Write-Host "`n=== TRIP PLANNER RELEASE TEST PASSED ===" -ForegroundColor Green
Write-Host "Options, booking-risk gate, warnings, stages, disclosure, and platform registration are responding correctly."
Write-Host "This test does not purchase anything, expose a secret, or create a guaranteed provider handoff."
