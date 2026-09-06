# Cashh Radar Post-Deployment Smoke Test

Use this after the Render service is created and the first deploy finishes.

## Quick command

```bash
python scripts/production_smoke.py https://YOUR-CASHH-RADAR.onrender.com
```

## With protected metrics

If `CASHH_METRICS_TOKEN` is set in Render, run:

```bash
python scripts/production_smoke.py https://YOUR-CASHH-RADAR.onrender.com --metrics-token "$CASHH_METRICS_TOKEN"
```

## What it checks

The script verifies the public app shell, health endpoints, PWA manifest, sitemap, and policy/support pages:

- `/`
- `/api/health/live`
- `/api/health/ready`
- `/api/health`
- `/manifest.json`
- `/sitemap.xml`
- `/privacy`
- `/terms`
- `/disclosures`
- `/security`
- `/support`
- optional `/api/metrics`

## How to read results

- `PASS` means the endpoint responded as expected.
- `SKIP` means an optional check was intentionally skipped, usually because no metrics token was supplied.
- `FAIL` means the deployed service needs attention before public promotion.

## Common fixes

### `/api/health/live` fails
The web service is not reachable or did not boot. Check Render deploy logs first.

### `/api/health/ready` fails
The app reached the server process but one or more launch requirements are not satisfied. Confirm Render environment variables, persistent disk, cookie security, public URL, and database migration status.

### Policy pages fail
Make sure the deployed service is running the full FastAPI app, not a static-only placeholder.

### Metrics fails
This is expected unless you pass `--metrics-token` with the same token configured in Render.

## Launch rule

Do not start active public promotion until this smoke test passes with zero `FAIL` results.
