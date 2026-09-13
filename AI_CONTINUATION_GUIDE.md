# Cashh Radar — AI Continuation Guide

Use this file when continuing Cashh Radar with ChatGPT, GitHub Copilot, Grok, Perplexity, Codex, or another AI coding/research assistant.

## Project identity

**Project:** Cashh Radar  
**Repository:** `anastaysia94-sudo/cashh-radar`  
**Product type:** evidence-backed opportunity intelligence and action platform  
**Public brand spelling:** `Cashh Radar` with two h's in Cashh  
**Tagline:** `Discover. Verify. Score. Act. Grow.`  
**Parent ecosystem:** SmartPickShop Holdings

Keep Cashh Radar separate from EGM4000, Fish Shooter Arcade, Founder Dynasty OS and other workspaces unless the user explicitly requests an integration.

## Current production truth

Cashh Radar is already deployed in production on Railway. Do not describe it as waiting for its first deployment.

Production shape:

- Railway service: `cashh-radar-web`
- one application replica while SQLite is in use
- persistent 1 GB volume `cashh-radar-db` mounted at `/app/data`
- canonical database path: `/app/data/cashh_radar.db`
- verified backups under `/app/data/backups`
- prospect operator: `/prospects/`
- current database schema: v6
- canonical unified prospect release commit: `ff67612e621707bc02cad38e3dcd7f8249baa29c`

The production service must retain persistent `/app/data` storage. Never casually redeploy production SQLite onto ephemeral storage.

## What Cashh Radar does

Cashh Radar helps users discover, verify, score, track and act on legitimate money/work/business/grant opportunities. The Prospect Engine is one execution surface inside that product, not a separate CRM.

Core lifecycle:

`discovered → verified → scored → explained → action_ready → acted → responded → outcome_recorded → learned`

The 500 source-backed business prospects are mapped into the normal `opportunities` table as `Client Prospect` records. Authenticated prospect state persists server-side and important prospect actions feed the canonical lifecycle.

## Unified Prospect Engine

Key files:

- `cashh_prospect_bridge.py` — server-side catalog, persistence, canonical lifecycle integration, freshness checks, unified Radar, value/hour ranking
- `cashh_loop.py` — canonical bounded lifecycle and learning
- `prospect-android-app/prospect-bridge.js` — authenticated browser/server reconciliation and mobile lifecycle controls
- `prospect-android-app/bootstrap-v4.js` — loads the active prospect runtime
- `prospect-android-app/sw.js` — offline static cache; explicitly bypasses `/api/*`

Important mappings:

- `SENT` → canonical `acted` + `contacted` outcome
- `REPLIED` → canonical `responded` + `replied` outcome
- actual paid/won/etc. outcome → `outcome_recorded` + bounded learning → `learned`

Do not create a second independent prospect-lifecycle system unless the user explicitly wants to replace the canonical architecture.

## Evidence and integrity rules

Every external opportunity, prospect, pricing, legal, competitor or customer-behavior claim should be labeled or supported as one of:

- verified fact;
- current external evidence;
- customer-derived evidence;
- internal observation;
- strategic hypothesis;
- financial model assumption;
- forecast;
- illustrative example.

Never invent:

- market size;
- opportunity availability;
- prospects;
- email addresses;
- source verification;
- platform fees;
- customer outcomes;
- replies;
- payments;
- testimonials;
- revenue;
- active integrations;
- legal/regulatory conclusions.

### Value-per-hour semantics

Keep these separate:

- **modeled offer value**: proposed offer divided by assumed work time; a financial-model assumption only;
- **realized value**: actual recorded amount divided by tracked work time.

Never present modeled offer value as actual earnings or a probability-weighted expected return unless the model and evidence supporting that calculation are explicitly added and labeled.

## Evidence freshness

Source-backed prospects support manual and scheduled public-source checks.

Production defaults:

```text
CASHH_PROSPECT_REFRESH_BATCH=8
CASHH_PROSPECT_REFRESH_SECONDS=900
CASHH_PROSPECT_HTTP_TIMEOUT=5
```

Freshness states include current, redirected, restricted, source snapshot, unavailable and error. A failed or restricted check remains uncertainty; do not convert it to verified/current to make metrics prettier.

The source checker refuses private/local/link-local/reserved targets. Preserve that SSRF boundary.

## Outreach policy

Current prospect policy:

- email-first;
- no Reddit prospecting;
- public/business-intended contact evidence only;
- individual user review before send;
- one unanswered follow-up for the current local-business campaign design;
- immediate opt-out handling;
- commercial-email physical postal-address gate;
- no fabricated claims or outcomes.

Optional Gmail integration creates drafts for review. Never change it to silently press Send without explicit product-policy reconsideration and appropriate safeguards.

## V5 / V6 boundary

`V5_V6_STATUS.md` documents a separate future expansion goal: 400 genuinely new Santa Clara County business prospects beyond the historical V1–V4 universe.

The existing 500 source-backed production prospects and recovered 500-row expert workbook must **not** be relabeled as the new V5/V6 universe. Preserve the documented dedupe/evidence gate.

## Development standards

- Preserve existing functionality and evidence semantics.
- Keep secrets out of GitHub.
- Commit `.env.example`, never `.env`.
- Never commit production SQLite databases, WAL files, logs, caches or virtualenvs.
- Keep Docker deployment valid.
- Preserve persistent `/app/data` requirements in production docs/config.
- Keep one replica while SQLite is the production datastore.
- Run tests before declaring a build complete.
- Update `README.md`, `MASTER_STATUS.md`, `TEST_REPORT.md`, `CHANGELOG_*.md`, and deployment/continuation docs after major architecture changes.
- Keep UI mobile-friendly and accessible.
- Keep language understandable for a non-technical founder.
- Preserve auth/CSRF enforcement on user-state mutations.
- Keep `/api/*` out of the Prospect Engine service-worker cache.

## Minimum validation before calling a build finished

Run:

```bash
python -m pytest -q
python -m py_compile app.py cashh_loop.py cashh_loop_ui.py cashh_prospect_bridge.py launcher.py api/index.py scripts/run_jobs.py scripts/preflight.py scripts/production_smoke.py
node --check static/app.js
node --check static/loop-ui.js
node --check static/sw.js
node --check prospect-android-app/prospect-bridge.js
node --check prospect-android-app/bootstrap-v4.js
node --check prospect-android-app/sw.js
python scripts/preflight.py
```

The unified integration release validated **41 automated tests** plus packed-data integrity, frontend/service-worker syntax and a Docker build.

## Production smoke test after code deployment

Verify:

```text
GET /api/health/ready                   -> 200
GET /api/health                         -> schema_version 6
GET /api/prospects/status               -> bridge unified, catalog total 500
GET /api/opportunities?category=Client%20Prospect -> count 500
GET /api/prospects/state without auth   -> 401
GET /api/radar/unified without auth     -> 401
GET /prospects/                         -> 200
GET /prospects/sw.js                    -> unified cache + /api/ bypass
```

Also verify `/app/data/cashh_radar.db` and at least one verified backup still exist on the persistent volume after deployment.

## Scaling boundary

The current single-replica persistent-SQLite architecture is appropriate for launch-scale use. Before multi-instance/high-volume scaling:

1. migrate state to managed PostgreSQL;
2. deliberately validate tenant isolation in the new datastore;
3. move scheduled jobs/freshness work to shared worker infrastructure;
4. test migrations, rollback and concurrency before increasing replica count.

Do not simply raise the Railway replica count while all writes still target a single SQLite file.

## Optional external activation boundaries

Do not claim these are active unless verified in the real external service:

- Stripe live billing and webhook configuration;
- SMTP delivery;
- USAJOBS credentials;
- Lever employer allowlist/feeds;
- custom-domain DNS;
- external monitoring;
- jurisdiction-specific legal review.

These optional integrations are separate from the completed unified prospect/opportunity architecture.

## Product positioning language

Safe public description:

> Cashh Radar helps you discover, verify, score, track and act on legitimate money opportunities using source-backed data, persistent execution state and outcome-aware opportunity intelligence.

Avoid guaranteed money, guaranteed income, risk-free language, fake testimonials, fake user counts, fake payouts, or claims that model assumptions are realized results.
