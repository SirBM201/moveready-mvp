# MoveReady Route Expansion Workflow

This workflow keeps route growth controlled, source-backed, and safe for public use.

## Purpose

MoveReady should not add routes as loose blog content. Every route should be added as structured, reviewable data that can power:

- route detail pages
- readiness reports
- saved routes
- watchlist alerts
- timeline events
- service requests
- source review dashboards

## Route expansion steps

1. Identify the route family.
   - Startup or founder
   - D visa or residence-travel route
   - Work or youth mobility
   - Study or scholarship
   - Family relocation
   - Official lottery, ballot, quota, or invitation pool
   - Settlement and post-arrival support

2. Confirm official source ownership.
   - Government immigration authority
   - Embassy or consular portal
   - Official visa portal
   - Official scholarship institution
   - Approved provider or verified partner source

3. Create or update country record.
   - `relocation_countries`

4. Create or update public route shell.
   - `relocation_visa_routes`

5. Create active route version.
   - `relocation_route_versions`
   - Include risk level, source confidence, verified date, and review due date.

6. Attach source records.
   - `relocation_trusted_sources`
   - `relocation_route_sources`

7. Add route facts.
   - `relocation_route_facts`
   - Use short, reviewable facts instead of long essays.

8. Add document requirements.
   - `relocation_document_requirements`
   - Keep applicant scope clear: main applicant, spouse, child, family member, sponsor, employer, school, or business.

9. Add budget items.
   - `relocation_budget_items`
   - Mark estimates clearly and avoid presenting estimates as official fees.

10. Add insurance requirements.
    - `relocation_insurance_requirements`

11. Create admin review task.
    - `relocation_admin_review_tasks`

12. Connect frontend action surfaces.
    - Route detail page
    - Save route
    - Create alert
    - Generate report
    - Timeline
    - Service request

## Public-safety rules

- Do not promise approval, selection, invitation, or faster processing.
- Do not call a paid service official unless it is approved and documented.
- Do not expose unreviewed route facts as final guidance.
- Do not use internal labels such as phase names on public pages.
- Always show source confidence and review timing where route facts may change.

## Recommended route expansion order

1. Estonia startup founder route
2. Finland D visa / fast-track route
3. Portugal entrepreneur / independent work route
4. Canada IEC
5. USA DV Program
6. UK India Young Professionals Scheme
7. Australia subclass 462 ballot and caps
8. New Zealand PAC and Samoan Quota
9. Japan, Korea, Hong Kong, and Ireland working-holiday routes
10. Study and scholarship route templates
11. Family relocation route templates
12. Settlement and post-arrival route templates

## Admin review checklist

Before publishing route facts, verify:

- Official source URL opens correctly.
- Source owner is named clearly.
- Last verified date is set.
- Review due date is set.
- Risk level is honest.
- Source confidence is not inflated.
- Document scope values match the database constraint.
- Fees and budgets are clearly separated.
- Family/dependant wording does not overpromise.
- Route page links to save route, watchlist, report, timeline, and service request actions.
