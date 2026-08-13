# MoveReady Launch V1 Implementation Backlog

Updated: 2026-08-14

## P0 — release blockers / highest value

1. **Jobs automation production acceptance** — prove target monitor creation, official scan, discovered vacancy, match, alert, draft generation, truth approval and employer handoff. Owner: backend + production. Migration: existing 032. No feature expansion until stable.
2. **Career search scope** — add LOCAL / INTERNATIONAL / BOTH plus current country and work-authorization context. Migration 034. Backend + frontend.
3. **International eligibility intelligence** — classify explicit no-sponsorship, sponsorship, LMIA, relocation and existing-authorization-required signals; separate Skill Match from Application Priority and gate unusable international vacancies. Migration 034 + backend matching/discovery + frontend cards.
4. **Opportunity Finder V1** — reuse route/readiness/opportunity/source records to recommend realistic pathway categories from the user profile. Avoid duplicate profile silos. Migration 035 only if additive fields cannot fit existing tables.
5. **Language Coach V1** — English/French/Both, IELTS General/TEF Canada, diagnostic, daily microlearning, Practice Bank, Mistakes Bank, adaptive review and progress. Migration 036 + API + frontend.
6. **Launch UX** — FIND / QUALIFY / MOVE entry points and dashboard; preserve Passport/Travel/Services under existing/secondary navigation.

## P1 — launch quality

7. Basic product analytics event taxonomy and privacy-safe outcomes.
8. Consolidated document/deadline view across route and job workflows.
9. Country/pathway comparison polish with provenance and verified/update dates.
10. Financial-readiness attachment to pathway recommendations.
11. Responsive/accessibility pass and empty/error/loading states.
12. End-to-end production smoke suite and launch runbook update.

## P2 — after V1 stability

Study discovery; founder/business mobility; family planner; advanced settlement; logistics partnerships including DHL/UPS/EMS; advanced Passport mobility; interview voice; full language mocks; gamification; community; marketplace expansion.

## Acceptance rules

- No high-priority international job recommendation when the user lacks authorization and the vacancy explicitly refuses sponsorship.
- Local jobs do not show irrelevant immigration warnings.
- Every immigration/pathway recommendation exposes official-source provenance and freshness where data exists.
- Language selection remains the user's decision.
- Automated job assistance never submits an application or accepts legal declarations for the user.
- Existing Passport Index, Visa Power, travel, route and settlement functionality remains available.
