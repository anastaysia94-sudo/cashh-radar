# Cashh Radar v2.2 Operations Guide

## Automatic jobs

For the single-instance SQLite launch, set `CASHH_SCHEDULER_ENABLED=1`. The web process runs jobs on configurable intervals and records every run in `job_runs`.

Jobs:

- `alerts` — evaluates deadline, material-change, high-match and saved-search signals;
- `digests` — evaluates daily/weekly user cadence and sends/queues digest delivery;
- `sources` — refreshes only source keys listed in `CASHH_SCHEDULED_SOURCES`;
- `webhooks` — delivers signed Team webhooks and retries failures;
- `maintenance` — removes expired sessions/security/invite tokens;
- `backups` — performs SQLite backup plus `PRAGMA quick_check` verification.

Manual execution:

```bash
python scripts/run_jobs.py alerts
python scripts/run_jobs.py sources
python scripts/run_jobs.py webhooks
python scripts/run_jobs.py backups
python scripts/run_jobs.py all
```

The owner can also execute supported jobs from the Admin interface/API.

## Health and observability

- Liveness: `/api/health/live`
- Readiness: `/api/health/ready`
- Detailed health: `/api/health`
- Protected Prometheus-style metrics: `/api/metrics`

Production readiness checks the database, migration v4, secret, secure cookie, HTTPS public URL, support email and SMTP whenever email verification is required.

## Backups

Default launch directory: `/app/data/backups`. Each backup is made through SQLite's backup API and verified. Persistent-disk backups protect against application mistakes; for stronger disaster recovery, copy backups to an independent storage provider after launch.

## Source operations

`CASHH_SCHEDULED_SOURCES` accepts comma-separated supported keys. Launch default is `grants_gov`. The application records source run status/errors instead of pretending failed sources are live.

## Scale-up trigger

Before running multiple application instances, migrate SQLite to PostgreSQL and move scheduled work into dedicated workers using the shared database. Do not run multiple in-process schedulers against separately mounted SQLite files.
