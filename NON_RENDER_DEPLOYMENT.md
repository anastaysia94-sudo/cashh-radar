# Cashh Radar — Non-Render Deployment Path

Render remains supported through `render.yaml`, but it is not required.

## Preferred replacement: Railway

Railway is the preferred non-Render target for Cashh Radar because it can run the existing FastAPI/Docker backend as a normal web service.

The repo now includes:

- `railway.json` — Railway config-as-code
- Dockerfile-based build
- start command for `uvicorn app:app`
- readiness healthcheck at `/api/health/ready`
- restart-on-failure policy

Recommended Railway environment values:

```bash
CASHH_COOKIE_SECURE=1
CASHH_DEV_MODE=0
CASHH_SCHEDULER_ENABLED=1
CASHH_SCHEDULED_SOURCES=grants_gov
CASHH_REQUIRE_EMAIL_VERIFICATION=0
CASHH_ADMIN_EMAIL=your-email@example.com
CASHH_ADMIN_PASSWORD=your-strong-password
CASHH_SUPPORT_EMAIL=support@example.com
CASHH_SECRET_KEY=generate-a-long-random-secret
CASHH_METRICS_TOKEN=generate-a-long-random-token
```

For durable data, configure Railway persistent storage or move the app to Postgres/Supabase before collecting real users.

## Fallback preview target: Vercel

The repo also includes a Vercel serverless adapter for the full FastAPI backend:

- `api/index.py` imports the real `app` from `app.py`.
- `vercel.json` routes all requests to that FastAPI entrypoint.
- This is not the removed Cashh Radar Lite page.
- The deleted `public/` static front door must not be restored.

## Vercel persistence note

Vercel does not provide the same persistent local disk model as the Docker + disk launch plan. The adapter sets SQLite runtime data to `/tmp/cashh_radar.db` so the full backend can run, but `/tmp` should be treated as temporary.

That means a Vercel deployment is useful for:

- public full-backend preview
- route and UI validation
- demo/testing without Render billing
- validating the FastAPI app under serverless hosting

It is not the final durable production data plan until the app is connected to a real external database such as Supabase/Postgres.

## Deployment checks

CI now checks:

- `api/index.py` compiles
- `vercel.json` routes to the backend entrypoint
- `railway.json` uses Docker and the backend start command
- Python tests pass
- frontend and service-worker JavaScript parse
- Docker build works for container platforms
- Render files remain valid for later use

## After deploy

Run the public smoke test:

```bash
python scripts/production_smoke.py https://your-deployment-url
```

For a private metrics route, add:

```bash
python scripts/production_smoke.py https://your-deployment-url --metrics-token "$CASHH_METRICS_TOKEN"
```
