# Cashh Radar Prospect Engine — Unified Mobile PWA

Cashh Radar's mobile-first prospect execution surface lives at `/prospects/`. It is no longer a separate local-only CRM. The source-backed business queue now participates in the same server-side opportunity, evidence, action, reply, outcome and learning lifecycle as the broader Cashh Radar product.

## Runtime

The canonical entrypoints are `index.html` and the backward-compatible `easy.html`.

1. `prospects.js` supplies the legacy prospect seed.
2. Four packed `data/p500-gz-*.js` chunks supply the 500 source-backed Santa Clara County business records.
3. `data/p500-loader.js` decompresses and integrity-checks that dataset in the browser.
4. `bootstrap-v4.js` combines source-backed and legacy records into the operator queue.
5. `easy-v4-core.js`, `easy-v4-policy.js`, `easy-v4-ui.js`, and `easy-v4-image.js` provide ranking, outreach policy, workflow, compliance and imagery.
6. `prospect-bridge.js` connects the operator to Cashh Radar's authenticated server lifecycle.

The packed loader refuses to continue unless the business dataset contains exactly 500 records with 500 unique non-empty public email values.

The operator queue is designed for up to 700 positions: the 500 source-backed business records come first, preserved legacy records remain available for continuity, and any unfilled positions are explicit discovery slots rather than fabricated leads.

## One opportunity lifecycle

On the server, `cashh_prospect_bridge.py` validates the same packed 500-record universe and maps every source-backed business into the canonical `opportunities` table as a `Client Prospect`.

That means a business prospect can move through the normal Cashh Radar lifecycle instead of living in a parallel system:

`discovered → verified → scored → explained → action_ready → acted → responded → outcome_recorded → learned`

The bridge records per-user prospect state on the server and connects important states to the canonical loop:

- **SENT** → canonical `acted` state + `contacted` outcome;
- **REPLIED** → canonical `responded` state + `replied` outcome;
- **paid/won/etc.** → canonical outcome + learning recalculation;
- tracked effort and actual amount → realized value-per-hour;
- proposed $100 package before a real outcome → explicitly labeled modeled offer value, never guaranteed income.

## Server-side persistence and offline behavior

Authenticated users persist prospect execution state in `prospect_user_state`, including:

- status;
- verification state;
- contact email;
- selected script and edited subject/body;
- draft/sent/reply timestamps;
- outcome stage and actual amount;
- tracked work minutes;
- fulfillment-time estimate;
- notes and synchronization timestamps.

Local storage remains an offline-resilience layer. When a signed-in device reconnects, pending local updates are reconciled with the server. The production database must live on durable `/app/data` storage so this state survives deployments and restarts.

The service worker **does not cache `/api/*`**. User-specific authenticated API responses remain network/session scoped instead of being written into the PWA cache.

## Evidence freshness

Each source-backed business has a canonical `prospect_catalog` record tied to its Cashh Radar opportunity.

The server can recheck public source URLs manually or through the bounded scheduler. Freshness states include:

- `current`;
- `redirected`;
- `restricted`;
- `source_snapshot`;
- `unavailable`;
- `error`.

Public-source refresh refuses localhost/private/link-local/reserved network targets. Reachable sources can update `last_seen`; material freshness changes are recorded in opportunity-change history. A restricted or unavailable source is not silently relabeled as verified.

## Earnings / value-per-hour prioritization

The queue combines:

- learned fit from real outcomes;
- deliverability;
- evidence freshness;
- lifecycle urgency such as replies/follow-ups;
- value-per-hour density.

There are two intentionally different value modes:

1. **Modeled offer value**: proposed offer divided by model-assumption outreach + fulfillment time. This is a prioritization assumption, not expected or guaranteed earnings.
2. **Realized value**: actual recorded outcome amount divided by user-tracked time. This is the only mode treated as realized $/hour.

The focused mobile card shows the current lifecycle stage, evidence freshness, modeled/realized hourly value and tracked minutes. Users can add effort time, mark a reply, record an actual paid amount, and recheck source evidence.

## Broader Cashh Radar

The prospect queue is one source family inside `/api/radar/unified`.

The unified Radar mixes:

- client prospects;
- jobs;
- grants;
- contracts;
- other normalized money/work opportunities.

The Prospect Engine Progress screen surfaces a compact view of non-prospect opportunities and links back to the full Cashh Radar workspace. Meanwhile the core `/api/opportunities` feed naturally includes source-backed client prospects because they are normal opportunities in the same database.

## Outreach policy enforced in code

The active workflow is email-first and excludes Reddit from prospect prioritization.

- Source-backed business records are prioritized only with retained public/business-intended email and evidence.
- Untouched legacy Reddit rows are marked `DO NOT PRIORITIZE — REDDIT DISABLED`.
- Other untouched legacy rows without a verified email are marked `DEPRIORITIZE — NO VERIFIED EMAIL`.
- Existing real `SENT`, `REPLIED`, and `WON / PAID` lifecycle state is preserved.
- Commercial business outreach remains gated on a saved physical postal address.
- One unanswered follow-up is the intended local-business campaign policy unless a user explicitly changes the campaign design.

Never fabricate prospects, emails, verification, replies, payments, customers, testimonials, earnings or outcomes.

## Gmail draft mode

With an optional Google OAuth Client ID, Cashh Radar can create a Gmail draft for review containing recipient, subject, message body and a generated prospect PNG. It does not press Send.

Without Gmail OAuth, the app can open the device email composer when a verified/public email is available.

## Production mount

`launcher.py` mounts this directory at:

```text
/prospects/
```

The same launcher also registers the canonical loop, unified prospect bridge and bridge scheduler before serving the PWA.

## CI protection

The GitHub Actions suite validates:

- Python compilation including `cashh_prospect_bridge.py` and the prospect-performance/lifecycle modules;
- **56 passing automated tests** on the current unified integration build;
- end-to-end `SENT → REPLIED → PAID → learned` behavior;
- persistent prospect-state API behavior;
- realized vs modeled value-per-hour semantics;
- unified Radar inclusion of prospect and non-prospect opportunities;
- exact 500-row / 500-unique-public-email packed-data integrity;
- 700-position operator-queue wiring;
- v4/unified runtime wiring;
- no service-worker caching of `/api/*`;
- frontend and service-worker JavaScript syntax;
- deployment configuration;
- Docker image build.

## Production storage

While SQLite is in use, production must remain a single application replica with persistent storage at `/app/data`. The current Railway production service uses a 1 GB persistent volume mounted there. Scale-out should move state to managed PostgreSQL and scheduled work to shared worker infrastructure first.
