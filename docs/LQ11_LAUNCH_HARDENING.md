# LQ11 — Daily alerts, mobile/accessibility, performance and production readiness

## Locked scope

LQ11 hardens the completed MoveReady V1 journeys. It does not reopen LQ03–LQ10 and introduces no database migration.

## Daily alerts

- The private smart-alert inbox exposes a deterministic daily digest contract at **07:07 UTC**.
- Users can refresh the inbox on demand.
- The digest ranks existing job, application, document, language, evidence and verified-change signals.
- Email, WhatsApp, SMS, Telegram and push remain fail-closed until credentials, explicit consent and delivery auditing are approved.
- No alert replaces an official notice, source, employer instruction or deadline.

## Mobile and accessibility

- Launch-critical pages retain usable navigation and controls at 320px, 375px, 768px and desktop widths.
- Touch targets remain at least 44px and safe-area navigation does not cover content.
- Keyboard focus, skip navigation, live status, reduced motion, forced colors and 200% zoom remain protected.
- New LQ11 surfaces must use semantic headings and bounded status announcements.

## Performance

- First-party Web Vitals reporting records only metric name, value, rating, delta, navigation type and an anonymous metric id.
- No account identity, URL query string, document content or application data is collected.
- Performance delivery is best-effort and never blocks navigation.
- The production budget targets LCP <= 2.5s, INP <= 200ms and CLS <= 0.1 at the 75th percentile.

## Production gate

Release requires:

1. Supabase migration frontier confirmed through 055.
2. Railway main revision matches backend main and route contract is healthy.
3. Vercel main revision matches frontend main and the production build passes.
4. LQ02–LQ11 plus retained B-series gates pass.
5. A verified-user FIND → QUALIFY → MOVE smoke journey passes on phone and desktop.
6. Daily alert generation and on-demand refresh pass using private test data.
7. Keyboard-only, 200% zoom and 320px checks pass.
8. Source freshness, privacy boundaries and fail-closed payment/external delivery controls are reviewed.

## Rollback

If a release gate fails, keep the public deployment on the last healthy revision. Do not apply an unversioned schema patch and do not enable external delivery or payment as a workaround.
