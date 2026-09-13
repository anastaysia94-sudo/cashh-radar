# Cashh Radar Deployment

## Production shape

Use **one Docker web-service instance with persistent storage mounted at `/app/data`** while Cashh Radar remains on SQLite. The prospect execution surface now writes real per-user outreach state, replies, outcomes, time tracking, learning events and freshness metadata into the same database as the broader opportunity system. Ephemeral production storage is therefore not acceptable.

Recommended launch configuration:

- one web replica;
- persistent `/app/data` storage;
- `CASHH_DB_PATH=/app/data/cashh_radar.db`;
- `CASHH_BACKUP_DIR=/app/data/backups`;
- `CASHH_SCHEDULER_ENABLED=1`;
- verified SQLite backups enabled;
- `/api/health/ready` as the platform healthcheck.

Before running multiple replicas, migrate shared state to managed PostgreSQL and move scheduled work to a dedicated worker/shared job system. SQLite plus multiple writers is not the place to discover distributed systems through interpretive dance.

## Railway production

The repository includes `railway.json` and a Dockerfile. The production service should:

1. build with `Dockerfile`;
2. start with `uvicorn launcher:app --host 0.0.0.0 --port 8000 --proxy-headers`;
3. expose port 8000;
4. use `/api/health/ready` as its healthcheck;
5. attach a persistent volume at `/app/data`;
6. keep one replica while SQLite is the datastore.

The existing production Cashh Radar service uses a 1 GB Railway volume named `cashh-radar-db` mounted at `/app/data`. Do not remove that mount during ordinary deploys.

## Render Blueprint

The repository also includes `render.yaml` and `deploy/render.yaml` for Render deployments. Use one Docker web service with a persistent disk at `/app/data` and the same database/backup environment settings.

A separate cron service must not be introduced while SQLite is stored on a web-service-local persistent disk because it would not share the same database. Use the in-process scheduler until the database and job system are moved to shared infrastructure.

## Required production settings

- `CASHH_SECRET_KEY`: long random secret.
- `CASHH_PUBLIC_URL`: the real HTTPS production URL.
- `CASHH_COOKIE_SECURE=1`.
- `CASHH_DEV_MODE=0`.
- `CASHH_ADMIN_EMAIL` / `CASHH_ADMIN_PASSWORD`: first owner login.
- `CASHH_SUPPORT_EMAIL`: public contact used by policy/support pages.
- `CASHH_DB_PATH=/app/data/cashh_radar.db`.
- `CASHH_BACKUP_DIR=/app/data/backups`.

## Scheduler

The in-process scheduler handles:

- outgoing webhooks;
- alerts;
- configured opportunity sources;
- digests;
- maintenance;
- verified SQLite backups;
- rotating source-backed prospect freshness checks through the unified prospect bridge.

Prospect refresh defaults are deliberately bounded:

- `CASHH_PROSPECT_REFRESH_BATCH=8`;
- `CASHH_PROSPECT_REFRESH_SECONDS=900`;
- `CASHH_PROSPECT_HTTP_TIMEOUT=5`.

The refresh worker uses public source URLs, refuses private/local-network targets, records current/restricted/unavailable/error states, and updates the canonical opportunity's last-seen evidence only when the public source remains reachable.

`CASHH_SCHEDULED_SOURCES=grants_gov` is a safe initial source configuration. Add USAJOBS or Lever only after credentials/tokens and source terms are ready.

## Unified prospect lifecycle

The production launcher registers `cashh_prospect_bridge.py` before mounting `/prospects/`. On startup the bridge:

1. validates and unpacks the 500 source-backed business records;
2. maps each record to a normal Cashh Radar `opportunities` row;
3. creates the prospect catalog and per-user server-state tables when needed;
4. preserves the evidence boundary between public facts, model assumptions and actual outcomes;
5. starts the bounded freshness worker when the scheduler is enabled.

The browser PWA keeps local state for offline resilience, but authenticated state is reconciled to the server. The service worker explicitly bypasses `/api/*`, so authenticated API responses are never written into the PWA cache.

## Billing

Paid checkout activates only when all required Stripe settings are present. Subscription lifecycle events update entitlement state, and the app can create a Stripe Customer Portal session for management/cancellation. The webhook route is:

`POST /api/billing/webhook`

Keep the raw request body intact; the application verifies the Stripe signature before plan activation.

## Email

SMTP powers password reset, email verification, two-step login, team invitations and digest delivery. Do **not** set `CASHH_REQUIRE_EMAIL_VERIFICATION=1` until SMTP has been tested.

Prospect outreach itself remains user-reviewed. Gmail integration creates drafts; Cashh Radar does not silently press Send.

## Health / monitoring

- `/api/health/live`
- `/api/health/ready`
- `/api/health`
- `/api/prospects/status`
- `/api/source-status`
- `/api/metrics` with `Authorization: Bearer $CASHH_METRICS_TOKEN`

After each production deployment, verify at minimum:

1. `/api/health/ready` returns 200;
2. `/api/prospects/status` reports `bridge: unified` and a 500-record catalog;
3. `/api/opportunities?category=Client%20Prospect` reports the mapped prospect opportunities;
4. `/prospects/` loads the unified bridge runtime;
5. `/prospects/sw.js` includes the unified cache version and API-cache bypass;
6. the database and backup files remain present under the persistent `/app/data` mount.
