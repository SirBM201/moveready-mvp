# MoveReady — Global Opportunity & Mobility Platform

Status: Master roadmap and Launch V1 scope freeze
Updated: 2026-08-14

## Positioning
MoveReady is a Global Opportunity & Mobility Platform, not only an immigration product and not only an international-job product.

Core loop: **FIND → QUALIFY → MOVE → SETTLE → GROW → FIND AGAIN**.

A feature excluded from Launch V1 is deferred, not abandoned. Existing Passport Index, Visa Power, travel, immigration, route, settlement, partner, evidence, account, alert, application-case and Jobs capabilities are preserved.

## Master Product Inventory

1. **AI Opportunity & Pathway Engine — CRITICAL.** Unified profile covering nationality/passport, residence, work authorization, education, work history, occupation, skills, languages, finances, family, preferences, target countries and career goals. Rank local/international employment, skilled PR, work permits, study, startup, entrepreneur, self-employment, investment, digital nomad, job-seeker, family/dependant, Francophone and other supported legitimate routes. Return readiness, gaps, actions, roadmap, comparisons, saved opportunities, monitoring, provenance and update dates.
2. **Local + International Career/Jobs — CRITICAL.** Explicit LOCAL / INTERNATIONAL / BOTH scope. Preserve discovery, daily monitoring, alerts, matching, employer intelligence, CV/cover-letter drafting, tracking, controlled assistance and follow-up. International ranking must consider legal work eligibility and sponsorship; local jobs suppress unnecessary immigration noise. Later: interview AI/voice, analytics, progression, salary and skills gaps.
3. **Language & Immigration Exam Coach — HIGH.** User chooses English, French or Both; Both supports configurable allocation. V1: IELTS General and TEF Canada, diagnostic, plan, 1–5 minute microlearning, vocabulary, grammar, reading, listening, original/legal exam-style practice, Practice Bank, Mistakes Bank, spaced repetition, adaptive difficulty, explanations, progress, CLB/NCLC mapping, target score and readiness. Architecture later supports CELPIP, PTE Core, TCF Canada, speaking/writing, full mocks, audio, gamification and approved notification channels. No leaked/recalled live exam dumps.
4. **Passport & Global Mobility Intelligence — RETAIN.** Passport strength/ranking, visa-free, VOA, eVisa, visa-required, destination lookup and comparison. Later: residence-status effects, multiple citizenships/passports, regional work rights, citizenship pathways and mobility improvement.
5. **Study Abroad — RETAIN.** Programs, institutions, eligibility, intakes, deadlines, tuition, funding/loans, dependants, study→work→PR and tracking.
6. **Startup/Business/Founder Mobility — RETAIN.** Startup, entrepreneur, self-employment, establishment, founder/investment/innovation/ownership requirements, family implications and pitch/business-plan assistance.
7. **Family Relocation — RETAIN.** Spouse, children, accompanying/joining later, work/study rights, schooling, proof of funds, costs and timelines.
8. **Financial Readiness — BASIC V1.** Proof of funds, relocation budget, savings target and basic country cost comparison; later family/tuition/startup/settlement/currency scenarios.
9. **Document & Execution — BASIC V1.** Personalized checklist, status, expiry/deadline tracking and milestones; later vault expansion, legalization, translation, reusable verified data and quality checks.
10. **Relocation Logistics — RETAIN, DO NOT DELAY LAUNCH.** Future DHL, UPS, EMS/express postal alternatives, accommodation, flights, airport transport, SIM, banking, insurance and arrival services.
11. **Settlement & Post-Relocation — RETAIN.** Local/better jobs, career/salary growth, skills gaps, certifications, renewals, settlement and family services.
12. **Investor/Product Analytics — ARCHITECTURE READY.** Registrations, activation, DAU/WAU/MAU, retention, assessments, saved pathways, matches, applications, voluntary interviews/offers, language activity/improvement, conversions, revenue and outcomes.

## Launch V1 scope freeze

### FIND
Opportunity & Pathway Finder; Local + International Jobs; auto-discovery; daily monitoring; alerts; Job Match Score; sponsorship/work-authorization intelligence; country/pathway comparison.

### QUALIFY
CV tailoring; cover letters; immigration readiness/gap analysis; personalized action plan; English/French/Both Language Coach; IELTS General; TEF Canada; Practice Bank; Mistakes Bank; adaptive microlearning.

### MOVE
Pathway requirements; document checklist; deadline/rule monitoring; basic proof-of-funds/financial readiness; application/job tracker.

Passport Index/basic mobility stays available but is not expanded ahead of launch-critical work.

## Repository audit — 2026-08-14

### Already strong
- Route checker/readiness, saved routes/reports, watchlists/alerts, timeline and application-case infrastructure cover substantial FIND/MOVE foundations.
- Passport Index/Visa Power now has backend/provider sync and launch infrastructure and must remain intact.
- Jobs has profile, company targets, recruiters, vacancies, matching, applications, resume vault, interview-preparation surface and controlled automation UI.
- Job automation has official-source monitors, scheduled scans, alerts, vacancy lifecycle, truthful document drafting/approval and employer-site handoff; daily monitoring workflow exists.
- Financial readiness, budget calculator, source governance/evidence review, authentication/account ownership, admin review and partner/service handoff already provide useful foundations.

### Partial
- Opportunity/pathway discovery exists but is not yet one profile-driven cross-pathway recommendation engine.
- Job matching considers role/skill/location/seniority and sponsorship signals, but LOCAL/INTERNATIONAL/BOTH and hard authorization/sponsorship priority gating are incomplete.
- Jobs profile is narrower than the desired unified opportunity profile.
- Document/application tracking is spread across modules rather than one Launch V1 execution journey.
- Financial readiness is not consistently attached to every pathway recommendation.

### Major V1 gaps
1. Local / International / Both job-search scope.
2. Current-country and country-specific work-authorization context.
3. Vacancy-level sponsorship/work-authorization signal extraction and realistic priority gating.
4. Unified Opportunity profile and cross-pathway recommendation contract.
5. Language Coach V1.
6. Unified FIND → QUALIFY → MOVE launch UX.
7. Coherent launch analytics event/outcome model.
8. End-to-end production acceptance after migration 032 and Supabase zero-row compatibility correction.

## Smallest high-value launch additions

**P0-A:** stabilize and production-test existing job automation before adding complexity.

**P0-B:** add LOCAL / INTERNATIONAL / BOTH, current residence/authorization and realistic sponsorship gating. Preserve raw skill match separately from application priority.

**P0-C:** expose a unified Opportunity Finder by reusing existing route/readiness/source infrastructure before adding a new AI stack.

**P0-D:** focused Language Coach V1 only.

**P0-E:** reframe primary UX around FIND → QUALIFY → MOVE while preserving deeper modules.

## Controlled implementation phases

### Phase 0 — Production stabilization
Verify Railway deployment, migration 032, monitor creation, scan, vacancy, match, draft, approval and employer handoff. Add zero-row regression coverage.

### Phase 1 — Career realism
Add scope/current-country/authorization context; classify vacancy sponsorship/authorization language; gate international application priority when sponsorship is refused and authorization is absent; keep technical match visible separately.

### Phase 2 — Opportunity Finder
Reuse existing profile/readiness data, normalize pathway categories and inputs, then return ranked recommendations, gaps, actions, provenance and comparison.

### Phase 3 — Language Coach V1
Add language/allocation/exam targets, diagnostics/progress, original question bank, attempts/mistakes/review scheduling and daily microlearning UI.

### Phase 4 — Launch UX + analytics
FIND/QUALIFY/MOVE dashboard/onboarding, event/outcome analytics, updated acceptance and deployment runbooks.

### Phase 5 — Post-launch
Study, founder/business, family, logistics, settlement, advanced Passport mobility, voice interviews, full mocks, gamification and marketplace expansion.

## Planned additive migrations
- **034:** job search scope/current-country/authorization and vacancy eligibility intelligence.
- **035:** unified opportunity profile/pathway-assessment extensions only where existing profile tables cannot safely hold fields.
- **036:** Language Coach core.
- **037:** analytics events/outcomes after taxonomy freeze.

Never rewrite applied migrations 001–033.

## Backend changes
1. Finish automation stabilization.
2. Extend Jobs profile contract for search scope/current-country authorization.
3. Add deterministic vacancy eligibility classifier and priority gating.
4. Reuse readiness/routes/opportunities/source governance for Opportunity Finder.
5. Add Language Coach API after schema approval.
6. Add analytics only after core event names stabilize.

## Frontend changes
1. Jobs setup/profile: LOCAL / INTERNATIONAL / BOTH and current-country authorization.
2. Job cards: Skill Match vs Application Priority plus concise eligibility blockers.
3. Opportunity Finder recommendations/comparison.
4. Language Coach V1 workspace.
5. FIND / QUALIFY / MOVE dashboard/navigation without deleting existing modules.

## Tests
Unit tests for authorization/sponsorship classification and gating; integration tests for profile scope, local/international filtering, automation bootstrap/scan and handoff; zero-row Supabase regression; provenance/update-date contracts; Language Coach diagnostic/attempt/mistake/progress tests; frontend build and user-flow smoke tests; production smoke after every migration/deploy.

## Deployment implications
Backend deploys from main to Railway; frontend deploys separately. New database migrations are manual production gates and must precede UI that depends on new columns. Keep scheduled job monitoring and Passport provider workflows intact. New code should fail gracefully if a migration has not yet been applied.

## Launch acceptance
Launch when FIND, QUALIFY and MOVE are reliable and understandable—not when the full master inventory is complete. A user should be able to discover a realistic opportunity, understand fit/blockers, improve qualification, prepare the move, track execution and return later for the next opportunity.
