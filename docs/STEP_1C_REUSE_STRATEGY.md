# Project MoveReady - Step 1C Reuse Strategy

Status: Active direction  
Purpose: Reuse the proven Naija Tax Guide / TaxBridge foundation without carrying over tax-specific product logic.

## Decision

We should reuse selected files and patterns from the existing Naija Tax Guide and TaxBridge work. This will move the project faster than starting from a completely empty backend and frontend.

The reuse should be selective. We copy structure, safety patterns, deployment setup, and working flows. We do not copy tax-specific data, menus, pricing, plan language, quiz logic, or old product text.

## What To Reuse From Backend

### Strong Reuse Candidates

- Flask app factory pattern
- CORS configuration pattern
- Environment variable loading
- Production safety checks for secrets
- Supabase client helper pattern
- Health check endpoints
- Koyeb-ready `Procfile` pattern
- Gunicorn runtime settings
- Admin-key protection pattern
- Report save/load style
- Email/login/session ideas where still useful
- Standard JSON API response style

### Rename For MoveReady

- App/session naming should move from `ntg` or tax references to `moveready` or `relocation`.
- API routes should use `/api/relocation/...` or `/api/moveready/...`.
- Database tables should use `relocation_*` prefixes.
- Admin header should become something like `X-MoveReady-Admin-Key`.

### Do Not Reuse

- Tax question/answer library content
- Tax calculator logic
- Quiz tables and quiz logic
- Naija Tax Guide plans and credit rules
- WhatsApp tax menus
- Telegram tax menus
- Tax-specific prompts
- Nigeria tax wording
- Any old public brand copy

## What To Reuse From Frontend

### Strong Reuse Candidates

- Next.js app router structure
- Public route layout pattern
- Checker/report-preview flow pattern
- Admin page protection ideas
- Shared API helper pattern
- Config helper pattern
- PDF/report export pattern if still clean
- Dashboard/report ownership patterns where useful
- Existing polished TaxBridge page layout direction as a starting design language

### Rename For MoveReady

- Public route group should become relocation/moveready oriented.
- TaxBridge copy should become visa, travel, relocation, document, scholarship, insurance, and budget readiness copy.
- Frontend env names should be changed to MoveReady names.
- Report references should use MoveReady/relocation naming.

### Do Not Reuse

- TaxBridge-specific Estonia startup visa positioning as the main product
- TaxBridge evidence pages as public product pages
- Naija Tax Guide tax plan text
- Tax calculator UI
- Tax quiz UI
- Any references to tax compliance as the core product

## Recommended Build Method

1. Keep the new MoveReady repos as the final clean repos.
2. Copy the backend skeleton from the working Naija/TaxBridge backend into `SirBM201/moveready-mvp`.
3. Remove tax-specific routes and modules.
4. Add the relocation database schema from Step 1B.
5. Add new relocation route modules around countries, routes, sources, checklists, budgets, scholarships, insurance, reports, and admin review.
6. Copy the frontend skeleton from the working TaxBridge/Naija frontend into `SirBM201/SirBM201-moveready-frontend`.
7. Replace public pages with MoveReady pages.
8. Keep API helper and report patterns, but rename endpoints and data types.
9. Test locally first.
10. Deploy only after local frontend/backend/Supabase flow passes.

## First Backend Modules To Create

- `app/routes/health.py`
- `app/routes/countries.py`
- `app/routes/routes.py`
- `app/routes/checklists.py`
- `app/routes/budgets.py`
- `app/routes/scholarships.py`
- `app/routes/insurance.py`
- `app/routes/reports.py`
- `app/routes/admin_sources.py`
- `app/routes/admin_routes.py`
- `app/services/supabase_client.py`
- `app/services/source_freshness.py`
- `app/services/report_generator.py`

## First Frontend Pages To Create

- `/`
- `/route-checker`
- `/country-checker`
- `/document-checklist`
- `/proof-of-funds`
- `/budget-calculator`
- `/scholarships`
- `/insurance-guide`
- `/report-preview`
- `/dashboard`
- `/my-reports`
- `/admin`
- `/admin/sources`
- `/admin/routes`
- `/admin/reviews`
- `/admin/reports`

## Key Warning

Reuse will make us faster, but only if we clean the naming properly. A half-renamed clone will create confusion, especially for users, investors, and future deployment. The rule is simple:

Copy the engine. Replace the identity.
