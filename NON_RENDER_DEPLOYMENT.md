# Cashh Radar — Non-Render Deployment Path

Render remains supported through `render.yaml`, but it is not required.

## Current non-Render target

The repo now includes a Vercel serverless adapter for the full FastAPI backend:

- `api/index.py` imports the real `app` from `app.py`.
- `vercel.json` routes all requests to that FastAPI entrypoint.
- This is not the removed Cashh Radar Lite page.
- The deleted `public/` static front door must not be restored.

## Important persistence note

Vercel does not provide the same persistent local disk model as the Render Docker + disk launch plan. The adapter sets SQLite runtime data to `/tmp/cashh_radar.db` so the full backend can run, but `/tmp` should be treated as temporary.

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
- Python tests pass
- frontend and service-worker JavaScript parse
- Docker build still works for container platforms
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
