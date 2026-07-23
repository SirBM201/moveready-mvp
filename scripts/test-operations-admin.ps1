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

$Headers = @{
    "X-MoveReady-Admin-Key" = $AdminKey.Trim()
}

Write-Host "`n=== PROTECTED MOVE READY OPERATIONS CHECK ===" -ForegroundColor Cyan
$Status = Invoke-RestMethod `
    -Method Get `
    -Uri "$Base/api/admin/operations/status" `
    -Headers $Headers `
    -TimeoutSec 120

$Status | ConvertTo-Json -Depth 40
Assert-True -Condition ($Status.ok -eq $true) -Message "Protected operations endpoint returned ok=false."

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
    "evidence_packs"
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
    Write-Warning "PAYMENT_LINKS_ENABLED is true. Confirm approved checkout domains, amount verification, payment references, webhook/manual verification, refunds, disputes, reconciliation, and production payment tests."
}
else {
    Write-Host "SAFE CONTROL: PAYMENT_LINKS_ENABLED remains false." -ForegroundColor Green
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
Write-Host "Account-auth, source-governance, route-version, evidence, provider-publication, quote, payment-audit, handoff, and support-case schemas are available through the backend service role."
Write-Host "This test reports but does not activate payment links, email OTP, WhatsApp, external alerts, approve any provider, or mark any source checked."
