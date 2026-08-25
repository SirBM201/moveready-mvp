# LQ12 — Live production validation and controlled beta

## Observed production state — 25 August 2026

- Vercel serves frontend commit `9751d9944d2f59177b295a0a3081fe8dad908538` (LQ11).
- Railway responds through the frontend deployment-status proxy but serves backend commit `4505b478a53e5258680c8da95044f939e6d3af0a`.
- Expected LQ11 backend commit is `0ee24815331f3ec751374c2de6342192facf5d9c`.
- Railway route contract reports healthy, 67 expected / 256 registered / zero missing, but the deployment is stale.
- Railway reports production environment and external notifications/payment remain disabled.
- Railway's operations snapshot still reports migration frontier 039 even though Supabase was manually confirmed through 055.

Therefore public launch is blocked until Railway deploys current main and the live fingerprint matches.

## Controlled beta gates

- 10–20 unique verified users.
- At least 80% complete the full journey.
- At least 90% complete recorded checks without technical help.
- Zero unresolved critical issues.
- Phone and desktop reports must both be represented.
- Alerts must be verified without enabling external delivery.

## Required journey

Onboarding/sign-in → Dashboard/Profile → Find → vacancy or route detail → Qualify/Alignment/Career Studio → application action → Alerts → Progress. Passport Index, Visa Power, reports, saved routes and support remain part of the broader regression journey.

## Privacy

Use controlled test data. Never paste session tokens, OTPs, admin keys, passport numbers, financial documents, raw authority correspondence or résumé files into beta feedback.
