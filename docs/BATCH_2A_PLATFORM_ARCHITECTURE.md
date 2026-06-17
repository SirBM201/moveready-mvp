# Batch 2A - Platform Architecture Expansion

This batch designs MoveReady as a full relocation readiness and opportunity-monitoring platform while keeping approval-gated services clearly labelled until they are ready.

## Rule

Design for the full platform now. Build only launch-safe behavior now. Leave clean integration points for future APIs, partners, and paid services.

## Live Now

- Country records
- Visa/relocation route records
- Stable route detail by country and route code
- Route facts
- Document requirements
- Budget estimates
- Insurance requirement notes
- Scholarship records
- Readiness reports
- Admin review foundation

## Service Areas

- Official ballots and quota opportunities
- Route watchlist and WhatsApp/email/Telegram/in-app alerts
- Document readiness and name consistency checks
- Proof-of-funds planner
- Refusal risk analyzer
- Notarization, apostille, attestation, and legalization support
- Passport and sensitive-document courier support
- Insurance partner quotes
- Embassy and visa-center appointment tracking
- Family relocation planner
- Post-arrival settlement checklist
- Partner and expert review network

## Public Safety Position

The public app should use user-friendly labels:

- Available
- Coming soon
- Partner approval pending

It should not expose internal roadmap language such as phase numbers or implementation status.

## Backend Layer

Batch 2A adds a separate platform blueprint instead of changing the stable relocation endpoints.

Service endpoints:

- `GET /api/platform/status`
- `GET /api/platform/modules`
- `GET /api/platform/modules/<slug>`
- `GET /api/opportunities`
- `GET /api/watchlist`
- `GET /api/alerts`
- `GET /api/documents`
- `GET /api/funds`
- `GET /api/refusal-risk`
- `GET /api/courier`
- `GET /api/legalization`
- `GET /api/insurance`
- `GET /api/appointments`
- `GET /api/family-relocation`
- `GET /api/settlement`
- `GET /api/partners`

The direct service endpoints return public-safe availability responses until their feature flags and data models are activated.

## Feature Flags

The current default is conservative. Approval-gated services are disabled by default.

- `PLATFORM_MODULES_ENABLED=true`
- `OPPORTUNITY_ALERTS_ENABLED=false`
- `WHATSAPP_ALERTS_ENABLED=false`
- `DOCUMENT_CHECKS_ENABLED=false`
- `PROOF_OF_FUNDS_PLANNER_ENABLED=false`
- `REFUSAL_ANALYZER_ENABLED=false`
- `LEGALIZATION_MODULE_ENABLED=false`
- `COURIER_MODULE_ENABLED=false`
- `INSURANCE_PARTNER_ENABLED=false`
- `APPOINTMENT_TRACKER_ENABLED=false`
- `FAMILY_PLANNER_ENABLED=false`
- `SETTLEMENT_MODULE_ENABLED=false`
- `PARTNER_MARKETPLACE_ENABLED=false`

## Future Database Tables

Do not create these until the module behavior is ready, but keep the naming stable:

- `relocation_opportunities`
- `relocation_user_watchlists`
- `relocation_alert_preferences`
- `relocation_notification_templates`
- `relocation_notification_logs`
- `relocation_whatsapp_optins`
- `relocation_document_checks`
- `relocation_name_consistency_checks`
- `relocation_proof_of_funds_plans`
- `relocation_refusal_reviews`
- `relocation_courier_requests`
- `relocation_legalization_requests`
- `relocation_insurance_quotes`
- `relocation_appointment_trackers`
- `relocation_family_members`
- `relocation_settlement_tasks`
- `relocation_partner_providers`
- `relocation_service_requests`

## Activation Order

Recommended order after the MVP route foundation:

1. Opportunities and watchlist
2. Email/in-app alerts
3. WhatsApp opt-in and templates
4. Document readiness and name consistency
5. Proof-of-funds planner
6. Refusal risk analyzer
7. Legalization and courier requests
8. Insurance/partner integrations
9. Family and post-arrival workflows
