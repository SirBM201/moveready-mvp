# MoveReady Email OTP Setup

MoveReady supports fail-closed email OTP login. OTPs are stored only as hashes in Supabase. A plain OTP exists briefly in application memory so it can be sent, and is never returned by the production API.

Keep `AUTH_OTP_DEV_MODE=false` in production.

## Required base variables

```env
AUTH_OTP_EXPIRES_MINUTES=10
AUTH_MAX_CODE_ATTEMPTS=5
AUTH_SESSION_DAYS=30
AUTH_OTP_DEV_MODE=false
EMAIL_OTP_DELIVERY_ENABLED=true
EMAIL_OTP_APP_NAME=MoveReady
EMAIL_OTP_LOGIN_URL=https://sir-bm-201-moveready-frontend.vercel.app/login
EMAIL_OTP_FROM=MoveReady <no-reply@yourdomain.com>
EMAIL_OTP_REPLY_TO=support@yourdomain.com
```

## Production: Mailtrap Email Sending API over HTTPS

Use this mode for real user login. It delivers the OTP to the recipient's inbox and is compatible with Railway's HTTPS egress path.

```env
EMAIL_OTP_PROVIDER=mailtrap
MAILTRAP_API_TOKEN=your_mailtrap_sending_api_token
MAILTRAP_API_URL=https://send.api.mailtrap.io/api/send
EMAIL_OTP_FROM=MoveReady <no-reply@your-verified-domain.com>
```

The sender domain must be verified in Mailtrap. MoveReady accepts only the official HTTPS sending endpoint so an API token and OTP cannot be redirected to an arbitrary host.

## Test/staging: Mailtrap Sandbox API over HTTPS

Use this mode only when testing templates or failure handling. Mailtrap Sandbox captures the message; it does **not** deliver the OTP to the address entered by the user.

```env
EMAIL_OTP_PROVIDER=mailtrap_sandbox
MAILTRAP_SANDBOX_API_TOKEN=your_mailtrap_sandbox_api_token
MAILTRAP_SANDBOX_ID=your_sandbox_id
EMAIL_OTP_FROM=MoveReady <login@example.test>
```

`MAILTRAP_API_TOKEN` may be used as the sandbox-token fallback. `MAILTRAP_INBOX_ID` remains a compatibility alias for `MAILTRAP_SANDBOX_ID`.

An optional explicit endpoint may be set:

```env
MAILTRAP_SANDBOX_API_URL=https://sandbox.api.mailtrap.io/api/send/your_sandbox_id
```

Only HTTPS, the official `sandbox.api.mailtrap.io` host, and the exact send path are accepted. Do not set `MAILTRAP_ACCOUNT_ID`; the current send endpoint requires the sandbox ID only.

## Alternative providers

### Resend

```env
EMAIL_OTP_PROVIDER=resend
RESEND_API_KEY=your_resend_api_key
EMAIL_OTP_FROM=MoveReady <no-reply@yourdomain.com>
```

### SMTP

```env
EMAIL_OTP_PROVIDER=smtp
SMTP_HOST=smtp.your-provider.com
SMTP_PORT=587
SMTP_USERNAME=your_smtp_username
SMTP_PASSWORD=your_smtp_password
SMTP_USE_TLS=true
EMAIL_OTP_FROM=MoveReady <no-reply@yourdomain.com>
```

Prefer an HTTPS provider on Railway. SMTP remains available for environments where outbound SMTP is supported.

## Railway deployment check

1. Set the selected provider variables in the Railway service.
2. Keep `AUTH_OTP_DEV_MODE=false`.
3. Deploy the backend.
4. Open `/api/auth/health` and confirm:
   - `email_delivery_enabled` is `true`;
   - `email_delivery_configured` is `true`;
   - `email_delivery_provider` matches the intended mode;
   - `dev_code_allowed` is `false`.
5. For production `mailtrap`, request one OTP to an inbox you control and verify it.
6. For `mailtrap_sandbox`, inspect the captured message in the selected Mailtrap sandbox instead of expecting inbox delivery.

If delivery fails, the request returns HTTP 503, expires the just-created code, and exposes only a bounded provider/status diagnostic. Mailtrap response bodies, API tokens, recipient addresses, and OTP values are not returned or logged.

## Targeted verification

Run:

```powershell
./scripts/test-auth-release.ps1 -RequireReady
```

To send one controlled production OTP:

```powershell
./scripts/test-auth-release.ps1 -RequireReady -TestEmail "your-login-email@example.com"
```

Do not paste the OTP, session token, API token, or provider response body into chat, issues, screenshots, or logs.

## Temporary local development mode

Without an email provider, local development may temporarily use:

```env
ENV_MODE=development
FLASK_ENV=development
AUTH_OTP_DEV_MODE=true
EMAIL_OTP_DELIVERY_ENABLED=false
```

The API can return `dev_code` only when both environment values are exactly `development`. Disable this mode before deploying.
