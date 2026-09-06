# Cashh Radar v2.2 Deployment

## Recommended same-day production shape

Use **one Docker web-service instance with a persistent `/app/data` disk**. The included Blueprint uses Render plan ID `0.5c-512mb` because a persistent application disk is part of this launch architecture; it is not a free ephemeral-service configuration. Keep `CASHH_SCHEDULER_ENABLED=1` so alerts, source refresh, digests, webhooks, maintenance and backups run in the same process/storage boundary.

This is intentionally simpler than a separate cron service because a separate Render cron job cannot share the web service's persistent SQLite disk. Move to a managed shared database + dedicated workers when scaling beyond the single-instance launch.

## Render Blueprint

The repository root includes `render.yaml`.

1. Connect the GitHub repo in Render.
2. Choose **New → Blueprint**.
3. Select the repo.
4. Enter required `sync: false` values when prompted.
5. Deploy.

Read `LAUNCH_TODAY.md` for exact nontechnical steps.

## Required production settings

- `CASHH_SECRET_KEY`: long random secret.
- `CASHH_PUBLIC_URL`: the real HTTPS Render/custom-domain URL.
- `CASHH_COOKIE_SECURE=1`.
- `CASHH_DEV_MODE=0`.
- `CASHH_ADMIN_EMAIL` / `CASHH_ADMIN_PASSWORD`: first owner login.
- `CASHH_SUPPORT_EMAIL`: public contact used by policy/support pages.

## Scheduler

The Blueprint enables the in-process scheduler. Defaults:

- outgoing webhooks: 5 min;
- alerts: 10 min;
- configured sources: 30 min;
- digests: hourly evaluation (daily/weekly cadence is enforced per user);
- maintenance: 6 hours;
- verified SQLite backup: daily.

`CASHH_SCHEDULED_SOURCES=grants_gov` is included in the launch Blueprint. Add USAJOBS/Lever only after their credentials/tokens and terms are ready.

## Billing

Paid checkout activates only when all required Stripe settings are present. Subscription lifecycle events update entitlement state, and the app can create a Stripe Customer Portal session for management/cancellation. The webhook route is:

`POST /api/billing/webhook`

Keep the raw request body intact; the application verifies the Stripe signature before plan activation.

## Email

SMTP powers password reset, email verification, two-step login, team invitations and digest delivery. For a same-day free launch, SMTP can be activated after the site is public. Do **not** set `CASHH_REQUIRE_EMAIL_VERIFICATION=1` until SMTP has been tested.

## Health / monitoring

- `/api/health/live`
- `/api/health/ready`
- `/api/health`
- `/api/metrics` with `Authorization: Bearer $CASHH_METRICS_TOKEN`

## Domain

Render automatically serves HTTPS on its service URL. A custom domain is optional for day-one launch and can be connected afterward without changing the application architecture.
