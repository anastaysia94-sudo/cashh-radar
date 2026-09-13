# Cashh Radar — Unified Prospect Lifecycle Test Report

Build: **Unified Prospect Lifecycle integration — 2026-09-12/13**

## Result

**PASS — integration candidate validated in CI.**

GitHub Actions run `34729606034` completed successfully on pull request #6.

- Automated pytest suite: **41 passed**.
- Python compilation: **passed**, including `cashh_prospect_bridge.py`.
- Frontend JavaScript syntax: **passed**, including `prospect-bridge.js`.
- Service-worker JavaScript syntax: **passed**.
- Deployment/PWA validation script: **passed**.
- Packed prospect integrity: **500 rows / 500 unique non-empty public emails**.
- Docker image build smoke test: **passed**.

The test run emitted two dependency deprecation warnings from Starlette/TestClient internals; they did not affect test results.

## New integration coverage

The unified Prospect Engine tests verify that:

- all 500 source-backed business records become normal `Client Prospect` rows in Cashh Radar's canonical opportunity table;
- offer value is labeled as a financial-model assumption rather than guaranteed income;
- per-user prospect execution state persists through the server API;
- `SENT` advances the canonical loop to `acted` and creates a `contacted` outcome;
- `REPLIED` advances to `responded` and creates a `replied` outcome;
- a recorded paid outcome advances through `outcome_recorded` to `learned`;
- repeating the identical paid state does not duplicate the paid outcome;
- actual amount + tracked minutes produces **realized** value-per-hour;
- proposed offer + assumed effort produces only **modeled offer value**;
- the unified Radar contains both client prospects and non-prospect money opportunities;
- bridge registration is idempotent.

## PWA / policy coverage

CI also protects that:

- the canonical prospect entrypoint loads the unified bridge;
- the email-first / no-Reddit policy flags remain enabled;
- the full unified static runtime is included in the service-worker cache;
- `/api/*` is explicitly excluded from service-worker caching;
- manifest/start URL remain valid;
- the compressed prospect dataset can be reconstructed and integrity-checked during CI.

## Production infrastructure verification

Before the unified code deployment, Railway production storage was migrated from ephemeral container storage to a **1 GB persistent volume mounted at `/app/data`**.

Verified after the storage migration:

- deployment `0c214a54-d446-4eba-9b33-c55dcf6b4d45`: **SUCCESS**;
- `/api/health/ready`: **200 OK**;
- `/app/data/cashh_radar.db`: present on the persistent mount;
- verified backup created under `/app/data/backups/`;
- one application replica retained for SQLite safety.

## Evidence boundaries tested by design

The system intentionally distinguishes:

- current external evidence;
- source snapshot / restricted / unavailable freshness states;
- model assumptions such as proposed offer value and estimated effort;
- actual user-recorded outcomes and tracked time.

No test or runtime path is allowed to convert a proposed $100 offer into a claimed payment or realized income without an actual recorded outcome.

## Post-merge production smoke requirements

After the unified integration is merged and deployed, production must pass:

1. `GET /api/health/ready` → HTTP 200;
2. `GET /api/prospects/status` → `bridge: unified`, catalog total 500;
3. `GET /api/opportunities?category=Client%20Prospect` → 500 mapped prospect opportunities;
4. unauthenticated `GET /api/prospects/state` → authentication required;
5. `GET /prospects/` → unified bridge runtime present;
6. `GET /prospects/sw.js` → unified cache version and `/api/` bypass present;
7. persistent `/app/data/cashh_radar.db` and backup files remain present after deployment.

Live SMTP, Stripe, USAJOBS, Lever, custom-domain DNS and third-party monitoring still require their respective external credentials/services before those optional integrations can be truthfully called active.
