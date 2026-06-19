# MoveReady Email OTP Setup

MoveReady now supports production-safe email OTP login.

The login code is always stored as a hash in Supabase. The plain OTP code is only available in two cases:

1. It is sent to the user's email through an approved provider.
2. `AUTH_OTP_DEV_MODE=true` is deliberately enabled for temporary testing.

Keep `AUTH_OTP_DEV_MODE=false` in production unless you are doing a short manual test.

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
```

## Option A: Resend

```env
EMAIL_OTP_PROVIDER=resend
RESEND_API_KEY=your_resend_api_key
EMAIL_OTP_FROM=MoveReady <no-reply@yourdomain.com>
```

## Option B: SMTP

```env
EMAIL_OTP_PROVIDER=smtp
SMTP_HOST=smtp.your-provider.com
SMTP_PORT=587
SMTP_USERNAME=your_smtp_username
SMTP_PASSWORD=your_smtp_password
SMTP_USE_TLS=true
EMAIL_OTP_FROM=MoveReady <no-reply@yourdomain.com>
```

## Testing flow

1. Deploy backend after setting variables.
2. Visit `/api/auth/health` and confirm:
   - `email_delivery_enabled` is `true`
   - `dev_code_allowed` is `false` for production
3. Visit `/login` on the frontend.
4. Enter an email address.
5. Confirm the OTP email arrives.
6. Verify the code.
7. Visit `/dashboard` and confirm the authenticated Account Summary appears.

## Temporary manual test without email

If you have not configured an email provider yet, you may temporarily set:

```env
AUTH_OTP_DEV_MODE=true
EMAIL_OTP_DELIVERY_ENABLED=false
```

Then request a code from `/login`. The API response will include `dev_code` for testing. After testing, set `AUTH_OTP_DEV_MODE=false` again and redeploy.
