param(
    [string]$Base = "https://moveready-mvp-production.up.railway.app",
    [string]$TestEmail = "",
    [switch]$RequireReady
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

function Assert-Unauthorized {
    param([Parameter(Mandatory = $true)][string]$Path)

    try {
        Invoke-RestMethod -Method Get -Uri "$Base$Path" -TimeoutSec 60 | Out-Null
        throw "Expected 401 for GET $Path, but the request succeeded."
    }
    catch {
        $Response = $_.Exception.Response
        if ($null -eq $Response -or [int]$Response.StatusCode -ne 401) {
            throw "Expected 401 for GET $Path. Actual error: $($_.Exception.Message)"
        }
    }
}

Write-Host "`n=== 1. AUTH HEALTH ===" -ForegroundColor Cyan
$Health = Invoke-RestMethod -Method Get -Uri "$Base/api/auth/health" -TimeoutSec 60
$Health | ConvertTo-Json -Depth 20
Assert-True -Condition ($Health.ok -eq $true) -Message "Auth health returned ok=false."
Assert-True -Condition ($Health.dev_code_allowed -ne $true) -Message "Unsafe production condition: development OTP codes are exposed."
Assert-True -Condition ($Health.otp_expires_minutes -ge 3 -and $Health.otp_expires_minutes -le 30) -Message "OTP expiry is outside the approved range."
Assert-True -Condition ($Health.request_limits.cooldown_seconds -ge 15) -Message "OTP resend cooldown is missing or too low."
Assert-True -Condition ($Health.request_limits.max_per_email -ge 1) -Message "Per-email OTP request protection is missing."
Assert-True -Condition ($Health.request_limits.max_per_ip -ge 1) -Message "Per-IP OTP request protection is missing."

$Ready = ($Health.email_delivery_configured -eq $true)
if ($RequireReady -and -not $Ready) {
    throw "OTP email delivery is not configured. Complete Railway email-provider variables before public account launch."
}

if ($Ready) {
    Write-Host "READY: OTP email provider is configured as $($Health.email_delivery_provider)." -ForegroundColor Green
}
else {
    Write-Host "CONTROLLED ROLLOUT: OTP email provider is not configured. Public login should remain disabled." -ForegroundColor Yellow
}

Write-Host "`n=== 2. PUBLIC OPERATIONS CONSISTENCY ===" -ForegroundColor Cyan
$Operations = Invoke-RestMethod -Method Get -Uri "$Base/api/operations/status" -TimeoutSec 60
$Operations | ConvertTo-Json -Depth 20
Assert-True -Condition ($Operations.ok -eq $true) -Message "Operations status returned ok=false."
Assert-True -Condition ([bool]$Operations.public_capabilities.verified_email_login -eq [bool]$Ready) -Message "Public operations login status does not match auth health."

Write-Host "`n=== 3. PRIVATE ACCOUNT BARRIER ===" -ForegroundColor Cyan
Assert-Unauthorized -Path "/api/auth/me"
Assert-Unauthorized -Path "/api/account/summary"
Assert-Unauthorized -Path "/api/handoffs"
Write-Host "Anonymous access is rejected for session, account, and handoff records." -ForegroundColor Green

if ($TestEmail.Trim()) {
    if (-not $Ready) {
        throw "A test email was supplied, but OTP email delivery is not configured."
    }

    Write-Host "`n=== 4. LIVE OTP DELIVERY REQUEST ===" -ForegroundColor Cyan
    try {
        $Response = Invoke-RestMethod `
            -Method Post `
            -Uri "$Base/api/auth/request-code" `
            -ContentType "application/json" `
            -Body (@{
                email = $TestEmail.Trim()
                source_page = "/release-test"
            } | ConvertTo-Json -Depth 10) `
            -TimeoutSec 90

        Assert-True -Condition ($Response.ok -eq $true) -Message "OTP request returned ok=false."
        Assert-True -Condition (-not $Response.dev_code) -Message "Production OTP response exposed a development code."
        Assert-True -Condition ($Response.delivery_status -eq "sent") -Message "OTP provider did not report sent status."
        Write-Host "OTP delivery request accepted." -ForegroundColor Green
        Write-Host "Provider: $($Response.delivery_provider)"
        Write-Host "Expires: $($Response.expires_at)"
        Write-Host "Check the test inbox. Do not paste the received code into chat or logs."
    }
    catch {
        $Response = $_.Exception.Response
        if ($null -ne $Response -and [int]$Response.StatusCode -eq 429) {
            throw "OTP rate limit is active. Wait for the Retry-After period and run the test again."
        }
        throw
    }
}
else {
    Write-Host "`nLive email sending was skipped. Supply -TestEmail only when you are ready to send one real OTP to an inbox you control." -ForegroundColor Yellow
}

Write-Host "`n=== AUTH RELEASE TEST COMPLETED ===" -ForegroundColor Green
if ($Ready) {
    Write-Host "Backend OTP readiness and private account barriers passed. Run once with -TestEmail to confirm actual inbox delivery."
}
else {
    Write-Host "Backend controls passed, but public login remains in controlled rollout until an approved email provider is configured."
}
