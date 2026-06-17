# MoveReady Backend - Render Deployment

Use this when Railway free-tier deployment is blocked or delayed.

## Repository

`SirBM201/moveready-mvp`

## Render service type

Create a new **Web Service** from the GitHub repository.

Render can read `render.yaml`, or you can enter these values manually:

- Runtime: `Python`
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn -w 2 -k gthread -t 120 -b 0.0.0.0:$PORT app.main:app`
- Health check path: `/health`

## Environment variables

Add these in Render:

```text
SUPABASE_URL=your_supabase_project_url
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key
SECRET_KEY=any_long_random_secret
MOVEREADY_ADMIN_KEY=your_admin_key
CORS_ORIGINS=https://sir-bm-201-moveready-frontend.vercel.app,http://localhost:3000
```

Do not paste the Supabase service role key into frontend or public files.

## Test backend after deploy

```text
https://YOUR_RENDER_BACKEND_URL/health
https://YOUR_RENDER_BACKEND_URL/api/health
https://YOUR_RENDER_BACKEND_URL/api/relocation/countries
https://YOUR_RENDER_BACKEND_URL/api/relocation/routes/by-code/EE/startup-founder
```

## Connect frontend

In Vercel frontend environment variables, update:

```text
NEXT_PUBLIC_BACKEND_URL=https://YOUR_RENDER_BACKEND_URL
```

Then redeploy the frontend.

## Notes

Render free web services may spin down after inactivity, so the first request can be slow. This is acceptable for MVP testing but not final production.
