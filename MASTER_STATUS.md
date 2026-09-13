# Cashh Radar — Master Project Status

Updated: 2026-09-12  
Current production prospect runtime: **v4 — 700-prospect PWA**

## Production state

Cashh Radar is no longer waiting on its first deployment.

- GitHub repository: `anastaysia94-sudo/cashh-radar`
- Railway project: `cashh-radar`
- Railway service: `cashh-radar-web`
- Production environment: active
- Latest checked Railway deployment: **SUCCESS**
- Canonical prospect entrypoint: `/prospects/`

The production launcher mounts the prospect PWA with the main Cashh Radar service rather than relying on a separate static-site deployment.

## Current prospect runtime

The active v4 prospect engine combines:

- **500 source-backed Santa Clara County business records** with public email values and integrity checks;
- **200 legacy prospect records** retained for lifecycle continuity;
- next-best-action ranking;
- email-first outreach policy;
- Reddit disabled for prospect prioritization;
- business-specific outreach-image generation;
- mobile-first queue and sprint UI;
- follow-up state and local persistence;
- PWA installation/offline runtime;
- optional Gmail draft creation when configured;
- compliance gate requiring a valid physical postal address before commercial send actions.

The packed-data CI check refuses to accept the source-backed dataset unless it expands to exactly 500 rows with 500 unique public email values.

## Verified current repository state

Latest production wiring commit checked:

`4e7fefbcfc578a86012337d31f33b722f8d59821` — **Wire Prospect Engine v4 into production PWA**

Recent supporting work includes:

- 700-prospect bootstrap and mapping;
- 700-prospect ranking/outreach/follow-up core;
- mobile queue, sprint and compliance UI;
- business-specific outreach image generation;
- 700-prospect mobile styling;
- split v4 expansion layers;
- packed 500-record integrity loader;
- service-worker/PWA cache protection;
- CI syntax/integrity checks.

## V5 + V6 ethical expansion

The next major boundary is the **400-new-prospect Ethical Prospect Engine**:

- V5: 200 new prospects — **Show the work + clear value**
- V6: 200 additional new prospects — **Show the work + choice + control**

Required V5/V6 outputs remain:

- canonical dedupe against every prior V1–V4 business;
- 400 genuinely new source-backed prospect records;
- 400 individualized first emails;
- 400 business-specific preview graphics;
- 400 ready-to-review `.eml` files with the matching preview attached;
- V5 and V6 Excel trackers;
- V5, V6 and combined 400-lead portals;
- V5, V6 and combined ZIP bundles;
- source audit and QA reports;
- real outcome tracking for sent/replied/interested/invoice/paid/fulfilled/bounce/opt-out.

### Current V5/V6 evidence boundary

A 500-row expert-verified workbook has been recovered and inspected. It is useful as the normalized historical/exclusion universe, but it overlaps the earlier prospect batches and therefore **must not be mislabeled as 400 new V5/V6 leads**.

The V5/V6 build must continue from fresh public evidence and dedupe against the full prior universe. No invented businesses, inferred email patterns, fabricated replies or fake conversion results are permitted to fill the quota.

## Outreach policy

- Email-first.
- No Reddit prospecting.
- Individual sends, not bulk BCC.
- One unanswered follow-up maximum for the V5/V6 local-business workflow.
- Use only public/business-intended contact evidence.
- Do not retry a bouncing address without re-verification.
- Honor opt-outs immediately.
- No fake scarcity, fabricated urgency, invented testimonials or guaranteed outcomes.
- Current payment route: PayPal invoice only.

## Payment

Current $100 one-time package invoice:

`https://www.paypal.com/invoice/p/#7T6DC9A6WFH3XXCT`

Do not reintroduce Venmo into this campaign unless explicitly requested.

## Immediate implementation boundary

1. Finish the canonical V1–V4 exclusion index using normalized business name, email, domain/website, phone/address where available and reasonable DBA aliases.
2. Expand the current public-source candidate pool until 400 genuinely new V5/V6 records pass the evidence gate.
3. Split the final ranked records into V5 and V6 experiments.
4. Generate their unique first-email copy, previews and attached `.eml` files.
5. Build the two trackers, combined master tracker and three portals.
6. Run exact-count, dedupe, source, attachment, spreadsheet, JavaScript and ZIP-integrity QA.
7. Publish lightweight V5/V6 runtime data/portals to GitHub only after the records pass QA.

## Scaling boundary

The core consumer/Team product still uses an intentionally simple single-service architecture for initial operation. Before multi-instance/high-volume enterprise scaling, migrate persistent state to managed PostgreSQL, deliberately test tenant isolation, and move in-process scheduled work to a dedicated worker/shared-database job system.
