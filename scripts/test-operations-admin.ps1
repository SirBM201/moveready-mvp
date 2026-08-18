param(
    [string]$Base = "https://moveready-mvp-production.up.railway.app",
    [Parameter(Mandatory = $true)][string]$AdminKey
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

$AdminKey = $AdminKey.Trim()
if ([string]::IsNullOrWhiteSpace($AdminKey)) {
    throw "AdminKey is required. Read it securely with Read-Host and never paste it into chat, screenshots, issues, logs, or repository files."
}

$Headers = @{
    "X-MoveReady-Admin-Key" = $AdminKey
}

Write-Host "`n=== PROTECTED MOVE READY OPERATIONS CHECK ===" -ForegroundColor Cyan
$Status = Invoke-RestMethod `
    -Method Get `
    -Uri "$Base/api/admin/operations/status" `
    -Headers $Headers `
    -TimeoutSec 120

$Status | ConvertTo-Json -Depth 50
Assert-True -Condition ($Status.ok -eq $true) -Message "Protected operations endpoint returned ok=false."
Assert-True -Condition ($Status.operations_contract.version -eq "b16-v1") -Message "Protected operations endpoint does not report the B16 contract."
Assert-True -Condition ($Status.operations_contract.admin_boundary.ok -eq $true) -Message "One or more admin routes are missing the B16 protection marker."

$RequiredSchemaCodes = @(
    "profiles",
    "auth_login_codes",
    "user_sessions",
    "trusted_sources",
    "source_change_alerts",
    "route_versions",
    "reports",
    "readiness_runs",
    "partner_publication",
    "commercial_quotes",
    "payment_events",
    "service_handoffs",
    "handoff_events",
    "support_cases",
    "document_inventory",
    "evidence_packs",
    "application_cases",
    "application_case_events",
    "application_case_alerts",
    "account_preferences",
    "privacy_requests",
    "language_profiles",
    "language_questions",
    "language_attempts",
    "language_mistakes",
    "language_daily_progress",
    "job_search_profiles",
    "job_companies",
    "job_recruiters",
    "job_company_targets",
    "jobs",
    "job_resume_assets",
    "job_applications",
    "job_watches",
    "job_scan_runs",
    "job_alerts",
    "job_document_drafts",
    "job_application_assistance",
    "job_assistance_events"
)

$Checks = @($Status.schema_checks)
foreach ($Code in $RequiredSchemaCodes) {
    $Check = @($Checks | Where-Object { $_.code -eq $Code })[0]
    Assert-True -Condition ($null -ne $Check) -Message "Operations response is missing schema check: $Code"
    Assert-True -Condition ($Check.ok -eq $true) -Message "Schema check failed for $Code. Required migration: $($Check.migration). Error: $($Check.error)"
    Write-Host "READY: $Code" -ForegroundColor Green
}

Assert-True -Condition ($Status.configuration.supabase_configured -eq $true) -Message "Supabase configuration is not ready."
Assert-True -Condition ($Status.configuration.admin_key_configured -eq $true) -Message "Admin key configuration is not ready."
Assert-True -Condition ($Status.configuration.environment_validation.status -ne "blocked") -Message "B16 environment validation is blocked: $($Status.configuration.environment_validation.blocked_checks -join ', ')"
Assert-True -Condition ($Status.configuration.commercial_quotes_enabled -eq $true) -Message "COMMERCIAL_QUOTES_ENABLED is not true."
Assert-True -Condition ($Status.configuration.otp_dev_mode_requested -ne $true) -Message "AUTH_OTP_DEV_MODE must not be enabled in production."

if ($Status.configuration.email_otp_delivery_enabled -eq $true -and $Status.configuration.email_otp_delivery_configured -ne $true) {
    throw "EMAIL_OTP_DELIVERY_ENABLED is true but the provider is incomplete. Missing: $($Status.configuration.email_otp_missing_configuration -join ', ')"
}
elseif ($Status.configuration.email_otp_delivery_configured -eq $true) {
    Write-Host "READY: OTP email provider $($Status.configuration.email_otp_provider) is configured." -ForegroundColor Green
}
else {
    Write-Host "CONTROLLED ROLLOUT: OTP email delivery is disabled." -ForegroundColor Yellow
}

if ($Status.configuration.payment_links_enabled -eq $true) {
    Write-Warning "PAYMENT_LINKS_ENABLED is true. Confirm approved checkout domains, exact amount and currency verification, references, webhook or manual verification, refunds, disputes, reconciliation, and production payment tests."
}
else {
    Write-Host "SAFE CONTROL: PAYMENT_LINKS_ENABLED remains false." -ForegroundColor Green
}

if ($Status.configuration.whatsapp_alerts_enabled -eq $true) {
    Write-Warning "WhatsApp alerts are enabled. Confirm approved business credentials, templates, explicit opt-in, unsubscribe handling, rate limits, delivery audit, and production tests."
}
else {
    Write-Host "SAFE CONTROL: WhatsApp delivery remains disabled." -ForegroundColor Green
}

if ($Status.configuration.opportunity_alerts_enabled -eq $true) {
    Write-Warning "External opportunity alerts are enabled. Confirm sender, consent, unsubscribe, delivery audit, rate limits, and production tests."
}
else {
    Write-Host "SAFE CONTROL: external opportunity alert delivery remains disabled." -ForegroundColor Green
}

if ($Status.launch_blockers.Count -gt 0) {
    Write-Host "`nLaunch blockers:" -ForegroundColor Red
    $Status.launch_blockers | ForEach-Object { Write-Host "- $_" -ForegroundColor Red }
    throw "Protected operations diagnostics still reports launch blockers."
}

Write-Host "`nControlled rollout items:" -ForegroundColor Yellow
if ($Status.controlled_rollout_items.Count -gt 0) {
    $Status.controlled_rollout_items | ForEach-Object { Write-Host "- $_" -ForegroundColor Yellow }
}
else {
    Write-Host "None reported." -ForegroundColor Green
}

Write-Host "`n=== PROTECTED OPERATIONS CHECK PASSED ===" -ForegroundColor Green
Write-Host "Account auth, source governance, route versions, evidence, applications, private alerts, account preferences, privacy requests, providers, quotes, payment audit, handoffs, and support schemas are available through the backend service role."
Write-Host "This test reports only. It does not activate payment links, email, WhatsApp, push delivery, approve providers, mark sources checked, create privacy requests, revoke sessions, or delete data."
