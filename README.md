# Cashh Radar — Launch Build v2.2.0

Cashh Radar is an evidence-labeled opportunity intelligence and action platform. It discovers opportunity records, preserves source lineage and freshness, ranks opportunities against user constraints, turns matches into concrete action plans, tracks outcomes, and supports consumer subscriptions, referrals/providers, Team workspaces, a commercial API, and white-label metadata.

## What is launch-ready

- Responsive branded web/PWA experience.
- Opportunity Radar, Fast Money, Remote Income, Business, Explorer and comparison views.
- Evidence states: illustrative, source-confirmed, verified, stale, expired and blocked.
- Source ingestion: Grants.gov; USAJOBS when credentials are supplied; configured Lever employer feeds.
- Personalized ranking, Opportunity Advisor, saved searches, watchlists, Pulse, alerts and digests.
- Roadmaps, source-aware outreach, outcome tracking and user-submitted opportunity intake.
- Accounts, password reset/change, email verification, optional two-step email login, export and deletion.
- Admin verification/source controls, review queues, analytics, audit history and background jobs.
- Free/Pro/Team model, Stripe Checkout/webhook code, referrals and provider-lead workflow.
- Team roles/invitations, shared organization watchlists, SCIM-style provisioning, signed outgoing webhooks and tenant branding metadata.
- Commercial API with scoped hashed API keys, metering and rate limits.
- PWA/SEO, legal/support/security pages, health/readiness endpoints, protected metrics, migrations, backups and production preflight.
- Optional in-process production scheduler for the recommended single-instance SQLite launch.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app:app --host 127.0.0.1 --port 8000
```

## Test

```bash
python -m pytest -q
python -m py_compile app.py
node --check static/app.js
node --check static/sw.js
```

## Launch today

Read **`LAUNCH_TODAY.md`** first. The fastest supported path is a single Render web service using the included root `render.yaml` and a persistent `/app/data` disk.

The application code can be launch-ready without fabricating external accounts. Public deployment still requires the owner to create/connect a GitHub repository and hosting account, choose the public URL, and directly enter production secrets. Stripe, SMTP, USAJOBS and Lever credentials are optional activation layers.
