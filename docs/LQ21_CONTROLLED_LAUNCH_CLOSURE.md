# LQ21 — Controlled Launch Closure

LQ21 converts existing V1 evidence into an explicit controlled-launch decision. Automated operational gates remain separate from manual OTP, authenticated-journey, mobile/keyboard, and controlled-cohort checks.

No manual gate is fabricated as passed. Broad public launch remains unapproved by this contract. Payments, external alert delivery, providers, marketplaces, document storage, student expansion, travel booking, automatic submission, and new AI modules remain outside V1.

## Production acceptance checkpoint

The controlled-launch endpoint must be present in the active Railway deployment before manual acceptance begins. A healthy legacy endpoint or green frontend proxy check does not prove that the LQ21 backend revision is live.

## 2026-08-30 controlled-launch checkpoint

- Matching target saved in production: Canada; Production Supervisor and Injection Moulding Technician; employer support required and sponsorship unconfirmed.
- PR #69 merged after all seven repository workflows passed.
- Controlled launch remains bounded: no public launch, automatic submission, or inferred sponsorship approval.
- Production acceptance requires the Railway deployment to serve the corrected recorded-target journey state.
- Railway retry authorized after the free-tier EU West peak-hours restriction cleared; deploy the latest `main` and re-run live acceptance.
