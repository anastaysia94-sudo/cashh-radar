# Cashh Radar Post-Deployment Smoke Test

Use this after a Railway deployment finishes, and before active public promotion.

## Quick command

The script now defaults to the live Railway production URL:

```bash
python scripts/production_smoke.py
```

Explicit URL form:

```bash
python scripts/production_smoke.py https://cashh-radar-web-production.up.railway.app
```

## With protected metrics

If `CASHH_METRICS_TOKEN` is available to the operator, run:

```bash
python scripts/production_smoke.py https://cashh-radar-web-production.up.railway.app --metrics-token "$CASHH_METRICS_TOKEN"
```

Do not paste the metrics token into public issues, docs, screenshots, or chat transcripts. Because apparently secrets become less secret when humans get excited near keyboards.

## What it checks

The script verifies the public app shell, launch-status routes, health endpoints, PWA manifest, sitemap, and policy/support pages:

- `/`
- `/api/health/live`
- `/api/health/ready`
- `/api/health`
- `/api/launch/status`
- `/launch-status`
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
The web service is not reachable or did not boot. Check Railway deployment logs first.

### `/api/health/ready` fails
The app reached the server process but one or more launch requirements are not satisfied. Confirm Railway environment variables, persistent `/app/data` storage, cookie security, public URL, and database migration status.

### `/api/launch/status` or `/launch-status` fails
Make sure Railway is deploying a commit that includes the public-safe launch-status endpoint in `launcher.py`. If Railway reused an old snapshot, update a harmless deploy marker variable or trigger a fresh deploy from the latest `main` commit.

### Policy pages fail
Make sure the deployed service is running the full FastAPI app, not a static-only placeholder.

### Metrics fails
This is expected unless you pass `--metrics-token` with the same token configured in Railway.

## Launch rule

Do not start active public promotion until this smoke test passes with zero `FAIL` results.
