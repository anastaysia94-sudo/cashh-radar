# Cashh Radar — Opportunity Intelligence + Unified Prospect Execution

Cashh Radar is an evidence-labeled opportunity intelligence and action platform. It discovers and normalizes money/work/business/grant opportunities, preserves source lineage and freshness, ranks them against user constraints, turns matches into concrete actions, and learns from real outcomes without inventing earnings, customers, replies, or verification.

The production system now treats the **Prospect Engine as one source family inside the same Cashh Radar lifecycle**, rather than as a separate local-only CRM.

## Production

- Repository: `anastaysia94-sudo/cashh-radar`
- Hosting: Railway, service `cashh-radar-web`
- Production app: `https://cashh-radar-web-production.up.railway.app/`
- Prospect operator: `/prospects/`
- Production datastore: SQLite on a persistent 1 GB volume mounted at `/app/data`
- Current unified schema: **v6**
- Launch architecture: **one application replica** while SQLite is in use

The production launcher registers the core Cashh Radar loop, the unified prospect bridge, the connected UI, the bounded refresh scheduler, and then mounts the mobile prospect PWA.

## Unified prospect lifecycle

The 500 source-backed Santa Clara County business records are validated from the packed prospect dataset and mapped into the canonical `opportunities` table as `Client Prospect` opportunities.

Prospect execution participates in the same lifecycle as other Cashh Radar opportunities:

`discovered → verified → scored → explained → action_ready → acted → responded → outcome_recorded → learned`

Authenticated prospect state is persisted server-side, including status, verification, contact route, selected/edited outreach, sent/reply timestamps, outcome stage, actual amount, tracked minutes, effort estimates, notes, and synchronization timestamps. Local storage remains only an offline-resilience layer and is reconciled with the server after reconnect.

Important transitions feed the canonical loop:

- **SENT** → `acted` + `contacted` outcome
- **REPLIED** → `responded` + `replied` outcome
- **actual outcome such as paid/won** → `outcome_recorded` → bounded learning recalculation → `learned`

Repeated synchronization of the same outcome is guarded against duplicate outcome creation.

## Evidence freshness

Source-backed prospects have a server-side catalog linked to their canonical opportunity. Manual and bounded scheduled checks classify source reachability as:

- `current`
- `redirected`
- `restricted`
- `source_snapshot`
- `unavailable`
- `error`

The refresh worker rejects private/local/link-local/reserved targets, uses public HTTP evidence only, updates `last_seen` only when the source remains reachable, and records material freshness-state changes instead of pretending every old record is still current.

Production defaults rotate through a small batch rather than hammering public sites:

```text
CASHH_PROSPECT_REFRESH_BATCH=8
CASHH_PROSPECT_REFRESH_SECONDS=900
CASHH_PROSPECT_HTTP_TIMEOUT=5
```

## Value per hour without fake earnings

Cashh Radar distinguishes two different concepts:

1. **Modeled offer value**: proposed offer divided by modeled outreach + fulfillment time. This is a financial-model assumption used for prioritization, not expected or guaranteed earnings.
2. **Realized value**: actual user-recorded outcome amount divided by tracked work minutes. Only this is labeled realized value per hour.

Prospect priority combines lifecycle urgency, learned fit, deliverability, evidence freshness, and value density. Replies and due follow-ups can outrank new outreach; real outcome data can change future learned ranking.

## Broader Opportunity Radar

`/api/radar/unified` ranks client prospects alongside other normalized money/work opportunities such as jobs, grants, contracts, and other opportunity sources. The mobile Prospect Engine also surfaces a compact broader-Radar view so the sales queue no longer pretends to be the entire product.

## Outreach integrity

The current business-outreach workflow remains:

- email-first;
- no Reddit prospecting;
- public/business-intended contact evidence only;
- individual review before send;
- one unanswered follow-up for the current local-business campaign design;
- immediate opt-out handling;
- no invented contact information, testimonials, replies, payments, customers, results, or urgency;
- commercial-email send gate requiring a physical postal address.

Optional Gmail integration creates a **draft for review**. Cashh Radar does not silently press Send.

## What else is launch-ready

- Responsive branded web/PWA experience.
- Opportunity Radar, Fast Money, Remote Income, Business, Explorer and comparison views.
- Evidence states and material-change tracking.
- Grants.gov ingestion; USAJOBS when credentials are supplied; configured Lever feeds.
- Personalized ranking, Opportunity Advisor, saved searches, watchlists, Pulse, alerts and digests.
- Roadmaps, outreach assets, outcome tracking and user-submitted opportunity intake.
- Accounts, password reset/change, email verification, optional two-step email login, export and deletion.
- Admin verification/source controls, review queues, analytics, audit history and background jobs.
- Free/Pro/Team model, Stripe integration code, referrals and provider-lead workflow.
- Team roles/invitations, shared watchlists, provisioning, signed outgoing webhooks and tenant metadata.
- Scoped commercial API with metering and rate limits.
- Legal/support/security pages, liveness/readiness endpoints, protected metrics, migrations and verified backups.

Optional external integrations are not claimed active until their real credentials/services have been verified.

## Run locally

Use the production launcher so the unified prospect bridge is registered:

```bash
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn launcher:app --host 127.0.0.1 --port 8000
```

For persistent local testing, set `CASHH_DB_PATH` and `CASHH_BACKUP_DIR` to durable local paths.

## Test

```bash
python -m pytest -q
python -m py_compile app.py cashh_loop.py cashh_loop_ui.py cashh_prospect_bridge.py launcher.py
node --check static/app.js
node --check static/sw.js
node --check prospect-android-app/prospect-bridge.js
node --check prospect-android-app/sw.js
```

The unified integration CI currently validates **41 automated tests**, JavaScript syntax, packed-prospect integrity, deployment configuration, service-worker API-cache isolation, and a Docker image build.

## Production validation

After a deployment, verify:

```text
GET /api/health/ready
GET /api/health
GET /api/prospects/status
GET /api/opportunities?category=Client%20Prospect
GET /prospects/
GET /prospects/sw.js
```

Authenticated prospect state and the unified Radar must reject unauthenticated requests. The production SQLite database and backups must remain present under the persistent `/app/data` mount.

See `DEPLOYMENT.md`, `TEST_REPORT.md`, `CHANGELOG_UNIFIED_PROSPECT_LIFECYCLE.md`, `MASTER_STATUS.md`, and `AI_CONTINUATION_GUIDE.md` for the current architecture and verification record.
