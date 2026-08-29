# LQ20 — V1 Launch Acceptance and Production Hardening

LQ20 verifies the existing V1 launch contract only: public health, build fingerprint, authentication health, operations readiness, frontend-to-backend connectivity, and anonymous rejection by a private Jobs route.

Acceptance is read-only. It does not request an OTP, mutate a record, run a scan, submit an application, contact an employer, or trigger any provider.

Payments, real notification delivery, provider networks, marketplaces, document vaults, student/admission expansion, settlement expansion, travel booking, and new AI modules remain outside V1.

Run `scripts/test-lq20-production-acceptance.ps1` for a safe production check.
