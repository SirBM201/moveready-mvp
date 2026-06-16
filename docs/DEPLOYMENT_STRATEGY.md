# MoveReady Deployment Strategy

Status: staging plan

## Decision

Keep the Koyeb free service reserved for Naija Tax Guide until launch. MoveReady should use a separate staging provider during MVP development, then move to Koyeb later when the Koyeb paid plan is active.

## Recommended Temporary Split

- Frontend: Vercel Hobby or Netlify Free
- Backend: Railway Free/Trial or PythonAnywhere Free for staging
- Database: Supabase
- Later consolidation: Koyeb paid plan when Naija Tax Guide is ready for launch

## Why Not Use Koyeb Free For MoveReady Now

Naija Tax Guide is closer to launch and should keep priority. MoveReady is still in MVP/staging mode, so it can tolerate a staging provider while features are being built.

## Backend Staging Option A: Railway

Best when we want GitHub-based deploys, environment variables, logs, and simple Python backend hosting.

Notes:

- Good for short-term staging and testing.
- Watch usage credits carefully.
- Do not treat it as final production until the billing model is comfortable.

Required environment variables:

```text
ENV_MODE=production
FLASK_ENV=production
PORT=8000
SECRET_KEY=replace-with-private-secret
API_PREFIX=/api
CORS_ORIGINS=https://your-frontend-domain
SUPABASE_URL=your-supabase-url
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
OPENAI_API_KEY=optional-for-now
OPENAI_MODEL=gpt-4o-mini
MOVEREADY_ADMIN_API_KEY=replace-with-private-admin-key
```

Start command:

```text
gunicorn -w 2 -k gthread -t 120 -b 0.0.0.0:${PORT:-8000} app.main:app
```

## Backend Staging Option B: PythonAnywhere

Best if the goal is a simple Flask staging app with a free Python host.

Notes:

- Simpler for Python-only hosting.
- May have outbound internet restrictions on free accounts, so Supabase/OpenAI connectivity must be tested.
- Less ideal if we want GitHub auto-deploy and modern CI/CD.

## Frontend Staging: Vercel

Recommended for the Next.js frontend.

Required environment variables:

```text
NEXT_PUBLIC_APP_NAME=Project MoveReady
NEXT_PUBLIC_BACKEND_URL=https://your-backend-staging-domain
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
2. Deploy MoveReady frontend to Vercel for preview.
3. Deploy MoveReady backend to Railway or PythonAnywhere for staging.
4. Connect frontend to backend.
5. Run smoke tests.
6. Move backend to Koyeb paid later.
