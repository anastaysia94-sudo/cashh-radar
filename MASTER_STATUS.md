# Cashh Radar — Master Project Status

Updated: 2026-09-13  
Current production architecture: **Unified Opportunity + Prospect Lifecycle, schema v6**

## Production state

Cashh Radar is deployed and healthy in production.

- GitHub repository: `anastaysia94-sudo/cashh-radar`
- Railway project: `cashh-radar`
- Railway service: `cashh-radar-web`
- Canonical production merge: `ff67612e621707bc02cad38e3dcd7f8249baa29c`
- Unified production deployment: `63d3048d-d78b-4398-af8e-d96ec5eff691` — **SUCCESS**
- Canonical prospect entrypoint: `/prospects/`
- Database schema: **v6**
- Launch datastore: SQLite on persistent Railway storage
- Persistent volume: `cashh-radar-db`, 1 GB, mounted at `/app/data`
- Replica count: 1 while SQLite is the datastore

Verified live after deployment:

- `/api/health/ready`: HTTP 200
- `/api/health`: schema v6, database healthy
- `/api/prospects/status`: unified bridge active
- `/api/opportunities?category=Client%20Prospect`: 500 mapped source-backed client prospects
- unauthenticated `/api/prospects/state`: HTTP 401
- unauthenticated `/api/radar/unified`: HTTP 401
- `/prospects/`: current PWA shell live
- `/prospects/sw.js`: unified cache and authenticated-API bypass live
- persistent SQLite database and verified backup present under `/app/data`

## Unified prospect architecture

The Prospect Engine is no longer a parallel local-only CRM.

The 500 source-backed business records are validated from the packed dataset and mapped into the canonical Cashh Radar `opportunities` table as `Client Prospect` opportunities. The 200 legacy PWA rows remain available for operator continuity, but only the source-backed catalog participates in the new server bridge automatically.

Authenticated source-backed prospect execution state is persisted server-side. The bridge stores:

- status and verification state;
- public/business-intended contact email;
- selected script and edited subject/body;
- prepared/sent/reply timestamps;
- canonical outcome stage and actual amount;
- tracked work minutes and fulfillment estimate;
- notes and synchronization timestamps.

Local browser state remains an offline-resilience layer and reconciles with the server when the authenticated device reconnects.

## One canonical opportunity lifecycle

Source-backed prospect activity now feeds the same bounded Cashh Radar lifecycle used by other opportunities:

`discovered → verified → scored → explained → action_ready → acted → responded → outcome_recorded → learned`

Important prospect transitions:

- `SENT` → canonical `acted` + `contacted` outcome
- `REPLIED` → canonical `responded` + `replied` outcome
- actual outcome such as `paid` → `outcome_recorded` → bounded learning recalculation → `learned`

Identical repeated outcome synchronization is guarded against duplicate outcome creation.

## Evidence freshness

Source-backed prospects have a canonical server catalog tied to the corresponding opportunity. Freshness can be checked manually or by the in-process bounded scheduler.

States include:

- current;
- redirected;
- restricted;
- source snapshot;
- unavailable;
- error.

The checker refuses private/local/link-local/reserved targets, records the result instead of inventing verification, and updates canonical `last_seen` only when the public source remains reachable.

Production refresh configuration:

- batch: 8 records;
- interval: 900 seconds;
- HTTP timeout: 5 seconds.

The first verified production refresh run checked 8 prospects: 7 reachable/current-or-redirected and 1 error. That error remains an evidence state, not a fabricated success.

## Earnings / value-per-hour prioritization

Cashh Radar now distinguishes:

1. **Modeled offer value** — proposed offer divided by modeled outreach + fulfillment time. This is a financial-model assumption used for ranking, not guaranteed or expected earnings.
2. **Realized value** — actual user-recorded amount divided by tracked work time. Only this is treated as realized value per hour.

Prospect queue priority combines lifecycle urgency, learned fit, deliverability, evidence freshness and value density. Replies and due follow-ups can outrank new outreach; recorded outcomes can influence future bounded learning.

## Broader money-opportunity Radar

`/api/radar/unified` ranks client prospects alongside other normalized jobs, grants, contracts and money/work opportunities. The Prospect Engine Progress screen also surfaces a compact broader-Radar view, so the prospect queue is one execution lane rather than the entire Cashh Radar product.

## PWA / security state

The live Prospect Engine remains:

- email-first;
- Reddit-disabled for untouched prospect prioritization;
- mobile-first;
- installable/offline-capable;
- protected by a commercial-email physical-postal-address gate;
- optionally able to create Gmail drafts for review;
- unable to silently press Send.

The service worker now explicitly bypasses `/api/*`. Authenticated API responses are never written to the PWA cache, preventing stale or cross-account user-state caching on shared devices.

## Verified repository / test state

Unified lifecycle pull request: **#6 — merged**.

GitHub Actions validation on the reconciled branch passed completely:

- **41 automated tests passed**;
- Python compilation passed;
- packed prospect data validation passed: exactly 500 rows / 500 unique public emails;
- frontend JavaScript syntax passed;
- service-worker JavaScript syntax passed;
- deployment configuration checks passed;
- Docker build smoke test passed.

The test suite covers the full prospect `SENT → REPLIED → PAID → learned` path, server-state persistence, duplicate-outcome protection, realized/modelled value semantics, and mixed prospect/non-prospect unified Radar behavior.

## Persistent production storage

Production SQLite was migrated from ephemeral container storage to a 1 GB persistent Railway volume before the unified server-state release was deployed.

Current verified files after the unified deployment:

- `/app/data/cashh_radar.db` — 2,007,040 bytes at final smoke test;
- `/app/data/backups/cashh-radar-20260913-011751.db` — matching verified backup size.

Do not remove `/app/data` persistence while SQLite remains the production datastore.

## V5 + V6 ethical expansion

The separate V5/V6 research program remains a future prospect-universe expansion, not a relabeling of the existing 500 source-backed records.

Goal:

- V5: 200 genuinely new prospects — **Show the work + clear value**
- V6: 200 additional genuinely new prospects — **Show the work + choice + control**

The recovered 500-row expert workbook overlaps the historical V1–V4 universe and therefore must not be presented as 400 new V5/V6 leads. New V5/V6 records must pass the dedupe/evidence gate documented in `V5_V6_STATUS.md`.

## Outreach policy

- Email-first.
- No Reddit prospecting.
- Individual review rather than bulk BCC.
- One unanswered follow-up for the current local-business campaign design.
- Public/business-intended contact evidence only.
- Reverify before retrying bounced addresses.
- Honor opt-outs immediately.
- No fake scarcity, fabricated urgency, invented testimonials, fabricated outcomes or guaranteed-response claims.
- Current campaign payment route: PayPal invoice only.

## Scaling boundary

The launch system is intentionally one application replica with persistent SQLite. Before multi-instance/high-volume scaling:

1. migrate persistent state to managed PostgreSQL;
2. deliberately test tenant isolation under the new datastore;
3. move scheduled refresh/jobs to shared worker infrastructure;
4. verify concurrency and migration/rollback behavior before increasing replica count.

That is the next architectural scaling boundary. It is not required for the completed single-replica production integration described above.
