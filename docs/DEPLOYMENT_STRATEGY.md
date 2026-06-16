# MoveReady Deployment Strategy

Status: Railway backend staging active

## Current Backend URL

```text
https://moveready-mvp-production.up.railway.app
```

Verified endpoints:

```text
/health
/api/health
/api/relocation/countries
```

The backend is online and reading country seed data from Supabase.

## Decision

Keep the Koyeb free service reserved for Naija Tax Guide until launch. MoveReady uses Railway for backend staging during MVP development, then can move to Koyeb later when the Koyeb paid plan is active.

## Current Temporary Split

- Frontend: Vercel Hobby or Netlify Free
- Backend: Railway
- Database: Supabase
- Later consolidation: Koyeb paid plan when Naija Tax Guide is ready for launch

## Why Not Use Koyeb Free For MoveReady Now

Naija Tax Guide is closer to launch and should keep priority. MoveReady is still in MVP/staging mode, so it can tolerate a staging provider while features are being built.

## Railway Backend Environment Variables

```text
ENV_MODE=production
FLASK_ENV=production
SECRET_KEY=replace-with-private-secret
API_PREFIX=/api
CORS_ORIGINS=https://your-frontend-domain
SUPABASE_URL=your-supabase-url
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
OPENAI_API_KEY=optional-for-now
OPENAI_MODEL=gpt-4o-mini
MOVEREADY_ADMIN_API_KEY=replace-with-private-admin-key
```

Railway provides `PORT`; do not hard-code it unless necessary.

Start command is defined in `railway.json`:

```text
gunicorn -w 2 -k gthread -t 120 -b 0.0.0.0:${PORT:-8000} app.main:app
```

## Frontend Staging: Vercel

Recommended for the Next.js frontend.

Required environment variables:

```text
NEXT_PUBLIC_APP_NAME=Project MoveReady
NEXT_PUBLIC_BACKEND_URL=https://moveready-mvp-production.up.railway.app
NEXT_PUBLIC_API_BASE=
```

The existing `next.config.mjs` rewrites `/api/*` calls to `NEXT_PUBLIC_BACKEND_URL`.

## Final Production Direction

When Naija Tax Guide is set for launch and the Koyeb paid plan is active, move MoveReady backend to Koyeb as an additional service. Keep Supabase as the database unless there is a later reason to migrate.

Final target:

```text
Naija Tax Guide backend -> Koyeb
MoveReady backend -> Koyeb
Naija Tax Guide frontend -> Vercel or preferred frontend host
MoveReady frontend -> Vercel or preferred frontend host
Databases -> Supabase
```

## Current Deployment Priority

1. Keep Naija Tax Guide stable.
2. Deploy MoveReady backend to Railway. Done.
3. Deploy MoveReady frontend to Vercel for preview.
4. Connect frontend to Railway backend.
5. Run smoke tests.
6. Move backend to Koyeb paid later.
