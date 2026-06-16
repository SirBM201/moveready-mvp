# Project MoveReady - Step 1B Database and Source Update Architecture

Status: Draft for implementation  
Purpose: Define the database foundation for source-backed relocation answers and reports.

## Core Safety Rule

AI is not the source of truth.

Approved sources, snapshots, route versions, and reviewed facts are the source of truth. AI can explain, summarize, and generate reports only from approved, fresh, version-bound data.

## Main Data Groups

### User and Profile Data

- `relocation_users`
- `relocation_user_profiles`
- `relocation_user_saved_routes`
- `relocation_user_alerts`

These tables store user identity, relocation goals, saved routes, and route-monitoring alerts.

### Country and Route Data

- `relocation_countries`
- `relocation_visa_routes`
- `relocation_route_versions`
- `relocation_route_facts`
- `relocation_route_sources`

Routes are versioned. The active route version is what the app should use for new answers. Old versions remain available for audit and previously generated reports.

### Source Freshness Data

- `relocation_trusted_sources`
- `relocation_source_snapshots`
- `relocation_source_change_alerts`
- `relocation_admin_review_tasks`

Every sensitive route should point back to trusted sources. Source snapshots allow the app to track what was known at a given time, what changed, and what needs admin review.

### Readiness Data

- `relocation_document_requirements`
- `relocation_budget_items`
- `relocation_scholarships`
- `relocation_insurance_requirements`

These records power the checklist, budget calculator, scholarship finder, and insurance guidance.

### Report and AI Data

- `relocation_generated_reports`
- `relocation_report_sections`
- `relocation_ai_answer_cache`

Reports and cached AI answers must store the route version and source snapshot references used at generation time.

## Source Status Model

Trusted sources can have these statuses:

- `active`
- `watching`
- `needs_review`
- `retired`

Source snapshots can have these statuses:

- `captured`
- `changed`
- `reviewed`
- `rejected`

## Route Version Status Model

Route versions can have these statuses:

- `draft`
- `pending_review`
- `active`
- `superseded`
- `retired`

Only `active` route versions should be used for new public answers.

## AI Cache Status Model

AI answer cache entries can have these statuses:

- `fresh`
- `stale`
- `superseded`
- `blocked`

If a route version is superseded or a source snapshot changes, related cached AI answers should not be reused for new users.

## Admin Review Flow

1. Source watcher detects a source change or admin adds a new source snapshot.
2. A source change alert is created.
3. An admin review task is created.
4. Admin reviews the source and updates route facts.
5. A new route version is created as `pending_review`.
6. Admin approves the route version.
7. New route version becomes `active`.
8. Previous route version becomes `superseded`.
9. AI cache tied to old route version becomes `superseded` or `blocked`.

## Report Versioning Rule

Generated reports should preserve the route version, sources, and assumptions used when the report was created. A report does not change silently when source data changes. Instead, the app can show a warning such as:

`This report was generated from a route version that has since changed. Refresh report recommended.`

## Trust Fields To Show Users

For sensitive route pages and reports, the frontend should show:

- Country
- Route
- Last verified date
- Review due date
- Risk level
- Source count
- Status
- Whether the answer is current or needs refresh

## Backend API Direction

The backend should expose these first API areas:

- Public country list
- Public route list
- Route details from active version only
- Profile questionnaire submission
- Checklist generation
- Budget estimate generation
- Scholarship search
- Insurance guide lookup
- Report generation
- User report history
- Admin source management
- Admin route/version management
- Admin review tasks

## Supabase Security Direction

The frontend should not receive a service role key. Sensitive writes and admin actions must go through the backend. Row Level Security should be enabled by default, with service-role backend operations used until user-auth policies are added.

## Implementation File

The first schema draft is in:

`supabase/migrations/001_initial_relocation_schema.sql`
