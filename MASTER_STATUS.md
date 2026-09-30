# Cashh Radar — Master Project Status

Updated: 2026-09-30  
Current production architecture: **Unified Opportunity + Prospect Lifecycle, schema v6**

## Production state

Cashh Radar is deployed in production on Railway.

- GitHub repository: `anastaysia94-sudo/cashh-radar`
- Railway project: `cashh-radar`
- Railway service: `cashh-radar-web`
- Production URL: `https://cashh-radar-web-production.up.railway.app/`
- Latest verified production deployment commit: `d0eb64458139b660ce19f6b183208324a2f46f3c`
- Latest verified Railway deployment: `c78334b1-b575-42f9-810e-b463a4283df0` — **SUCCESS**
- Deployment commit message: `Style customer-facing Fix Desk offer ladder`
- Canonical prospect entrypoint: `/prospects/`
- Database schema: **v6**
- Launch datastore: SQLite under `/app/data`
- Replica count: 1 while SQLite is the datastore
- Railway builder: Dockerfile
- Railway start command: `uvicorn launcher:app --host 0.0.0.0 --port 8000 --proxy-headers`
- Railway healthcheck: `/api/health/ready`
- Railway public domain target port: `8000`

The latest Railway build and deployment logs show:

- container build completed successfully;
- Uvicorn server process started on `0.0.0.0:8000`;
- application startup completed;
- Railway called `/api/health/ready` and received HTTP 200;
- Railway's deployment healthcheck succeeded.

The current deployed commit lineage also contains the public-safe launch-status work and production smoke-test coverage for `/api/launch/status` and `/launch-status`. Do not treat documentation alone as proof of a future deployment; the Railway deployment above is the verified production snapshot.

## Current production capabilities

### Unified prospect architecture

The Prospect Engine is not a parallel local-only CRM.

The 500 source-backed business records are validated from the packed dataset and mapped into the canonical Cashh Radar `opportunities` table as `Client Prospect` opportunities. The 200 legacy PWA rows remain available for operator continuity, but only the source-backed catalog participates in the server bridge automatically.

Authenticated prospect state persists server-side, including:

- status and verification state;
- public/business-intended contact email;
- selected script and edited subject/body;
- prepared/sent/reply timestamps;
- canonical outcome stage and actual amount;
- tracked work minutes and fulfillment estimate;
- notes and synchronization timestamps.

Local browser state remains an offline-resilience layer and reconciles with the server when the authenticated device reconnects.

### One canonical opportunity lifecycle

Source-backed prospect activity feeds the same bounded Cashh Radar lifecycle used by other opportunities:

`discovered → verified → scored → explained → action_ready → acted → responded → outcome_recorded → learned`

Important prospect transitions:

- `SENT` → canonical `acted` + `contacted` outcome
- `REPLIED` → canonical `responded` + `replied` outcome
- actual outcome such as `paid` → `outcome_recorded` → bounded learning recalculation → `learned`

Identical repeated outcome synchronization is guarded against duplicate outcome creation.

### Performance-aware Radar ranking

Production includes bounded, sample-aware industry learning from persisted prospect outcomes.

The system can use recorded prospect performance to improve prioritization while keeping modeled offer value separate from realized money. Tiny samples are deliberately prevented from dominating the ranking model.

Current behavior includes:

- persisted prospect performance metrics for authenticated users;
- protected performance-aware Radar ranking;
- learned segment results in Prospect Progress;
- sample-aware score adjustments with bounded influence;
- regression coverage protecting modeled-versus-realized semantics.

### Public-safe launch status

The current main/deployed lineage includes a public-safe launch-status surface intended to expose operational readiness without leaking secrets. Production smoke-test documentation now checks both:

- `/api/launch/status`
- `/launch-status`

Sensitive values such as metrics tokens remain private and must never be copied into public documentation, screenshots or chat logs.

## Fix Desk commercial completion — 2026-09-30

The Fix Desk commercial lane is now production-deployed and live-certified.

- Live route: `/fix-desk/`
- Customer-facing paid offer ladder is live:
  - Entry Fix Desk: **$99–$100**
  - Growth Fix Desk: **$149**
  - Local Growth: **$199**
  - Launch Rescue: **$249**
- The personalized V5/V6 final offer remains the **$100 Business Content Pack**.
- Live Android/PWA E2E certification run: `36721261099` — **SUCCESS**
- Full Cashh Radar validation run on the certification commit: `36721261063` — **SUCCESS**
- Certification commit: `40767f07ad67eaabd354942858dcf4e939e5ad5a`
- The live E2E verifies HTTPS, personalized business context, the $100 final offer, PWA manifest/icons/service-worker scope, form prefill, scope generation, exact checkout URL, visible/enabled checkout CTA, and PayPal handoff.
- QA evidence is uploaded by the workflow as the `fix-desk-live-e2e-evidence` artifact.
- This verifies the handoff to PayPal. It does **not** claim that a customer completed payment.

A canonical commercial ladder is documented in `COMMERCIAL_OFFER_LADDER.md`.

Five customer-ready digital products were also extracted from existing Cashh Radar systems and stored in private fulfillment storage rather than this public repository:

1. Opportunity Scoring Kit
2. Prospecting Command Pack
3. Evidence-First Income Planner
4. Founder Revenue Experiment Workbook
5. Opportunity Intelligence Brief Template

The storefront-facing catalog/spec is documented in `DIGITAL_PRODUCT_CATALOG.md`. Selling prices for those download products remain an explicit storefront publication gate; no price was invented or silently published.

## Evidence freshness

Source-backed prospects have a canonical server catalog tied to the corresponding opportunity. Freshness can be checked manually or by the bounded scheduler.

States include:

- current;
- redirected;
- restricted;
- source snapshot;
- unavailable;
- error.

The checker refuses private/local/link-local/reserved targets, records uncertainty rather than inventing verification, and updates canonical `last_seen` only when the public source remains reachable.

Production defaults remain:

- refresh batch: 8 records;
- interval: 900 seconds;
- HTTP timeout: 5 seconds.

## Earnings / value-per-hour semantics

Cashh Radar distinguishes:

1. **Modeled offer value** — proposed offer divided by modeled outreach + fulfillment time. This is a financial-model assumption used for ranking, not guaranteed or expected earnings.
2. **Realized value** — actual user-recorded amount divided by tracked work time. Only this is treated as realized value per hour.

Prospect queue priority can combine lifecycle urgency, learned fit, deliverability, evidence freshness and value density. Replies and due follow-ups can outrank new outreach; recorded outcomes can influence future bounded learning.

## Broader money-opportunity Radar

`/api/radar/unified` ranks client prospects alongside other normalized jobs, grants, contracts and money/work opportunities. The Prospect Engine Progress screen surfaces a compact broader-Radar view, so the prospect queue remains one execution lane inside Cashh Radar rather than the entire product.

## PWA / security state

The Prospect Engine remains:

- email-first;
- Reddit-disabled for untouched prospect prioritization;
- mobile-first;
- installable/offline-capable;
- protected by the commercial-email physical-postal-address gate;
- optionally able to create Gmail drafts for review;
- unable to silently press Send.

The service worker explicitly bypasses `/api/*`. Authenticated API responses are never written to the PWA cache, preventing stale or cross-account user-state caching on shared devices.

## Validation standards

Meaningful software changes must continue to run the repository's required validation before being called complete, including Python tests/compilation, frontend and service-worker syntax checks, packed-data integrity, preflight checks and deployment smoke validation when production behavior changes.

Do not claim a live deployment merely because code exists in GitHub. Verify the real Railway deployment/status first.

## V5 + V6 ethical expansion

The V5/V6 expansion is now complete as a final 400-prospect source-backed package:

- V5: **200** genuinely new prospects — Show the work + clear value
- V6: **200** genuinely new prospects — Show the work + choice/control
- final unique V5/V6 prospects: **400**
- historical V1–V4 identities excluded: **747**
- final exclusion universe: **1,147 identities**
- public/business-intended emails: **400/400**
- source URLs present: **400/400**
- individualized first emails: **400**
- business-specific preview graphics: **400**
- ready `.eml` files: **400**
- local portals: V5 / V6 / combined
- Excel trackers: V5 / V6 / combined
- V5, V6 and combined ZIP packaging: complete
- build/QA workflow: pass

The final V5/V6 package uses the approved $100 Business Content Pack purchase path. No Venmo references are permitted in this campaign. The latest detailed final status remains in `V5_V6_STATUS.md`.

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

## Production persistence / scaling boundary

The launch architecture remains intentionally single-replica SQLite. The production design requires `/app/data` persistence and verified backups while SQLite remains the datastore. Do not increase replicas casually while writes still target one SQLite database.

Before multi-instance/high-volume scaling:

1. migrate persistent state to managed PostgreSQL;
2. deliberately test tenant isolation under the new datastore;
3. move scheduled refresh/jobs to shared worker infrastructure;
4. verify concurrency and migration/rollback behavior before increasing replica count.

That remains the next major architectural scaling boundary; it is not required for the current single-replica production launch.
