# Cashh Radar — V5 + V6 Ethical Expansion Checkpoint

Updated: 2026-09-13

## Goal

Build **400 genuinely new Santa Clara County business prospects**:

- V5: 200 — Show the work + clear value
- V6: 200 — Show the work + choice + control

Every final record must retain public source evidence and a business-intended email. No prospect may be invented merely to fill quota.

## Canonical historical exclusion audit

The currently recovered V1–V4 files contain:

- V1: 150 rows
- V2: 200 rows
- V3: 200 rows
- V4: 200 rows
- Raw historical rows: **750**
- Canonical historical identities: **747**
- Repo-gate normalized business names across those 747 identities: **732**
- Unique public email values: **722**
- Unique website/domain values observed: **506**

Three exact normalized business identities appear in more than one historical version and must be treated as one exclusion identity rather than fresh V5/V6 prospects:

1. Blue's Roofing — V3 + V4
2. South Bay Design & Landscaping — V3 + V4
3. D&D Electrical Construction — V3 + V4

The canonical exclusion workbook remains the authoritative historical identity source. The repo gate applies a stricter normalization layer on top of it, so a new employee email does not magically turn an old business into a fresh lead.

## Recovered 500-row expert workbook

The recovered `500_EXPERT_VERIFIED_INDIVIDUALIZED_EMAILS_2026-09-07.xlsx` contains 500 source-backed/public-email records with strong individualized copy and scoring.

Dedupe audit result against the recovered V1–V4 exclusion universe:

- 500 rows inspected
- **0 genuinely new V5/V6 identities**
- all 500 matched the historical universe by normalized business name, public email, and website/domain

Therefore this workbook is useful as a normalized historical/exclusion and copy-quality reference, but it must **not** be presented as the 400-new-lead V5/V6 batch.

## Current V5/V6 staging progress

The fresh-source pipeline has now completed five audited research passes:

- Seed pass: 41 candidates checked, **36 accepted**, 5 rejected as historical overlap.
- Batch 2: 17 candidates checked against the 747 canonical historical identities plus the 36 seed accepts, **11 accepted**, 6 rejected.
- Batch 3: 13 candidates checked against the 747 canonical historical identities plus all 47 prior staging accepts, **12 accepted**, 1 rejected.
- Batch 4: 17 research finalists reviewed against the 747 canonical historical identities plus all 59 prior staging accepts; 2 preliminary newness-pass records were held for quality reasons and replaced; **15 final candidates accepted**.
- Batch 5: 19 research finalists reviewed against the 747 canonical historical identities plus all 74 prior staging accepts; **15 accepted**, 3 rejected as historical identities, and 1 held because the exact public email could not be resolved without guessing.
- **Cumulative staging pool: 89 genuinely new, source-backed, gate-accepted prospects.**
- Remaining to reach the 400-prospect target: **311**, before the intentional over-research/rank/prune stage.

Batch 5 historical rejects were Lunardi Moving Services, San Jose Dry Carpet Cleaning, and Blu Skye Media. Their current sites are evidence that the businesses remain active, but current evidence does not make an old identity new. B2 Perfection Auto Body remains an evidence hold because the current owned site exposes an email contact while the retrieved text masks the exact address; no email was inferred or reconstructed.

Audit files:

- `data/v5-v6-research/seed-2026-09-13.md`
- `data/v5-v6-research/seed-2026-09-13-gate-report.json`
- `data/v5-v6-research/batch2-2026-09-13.md`
- `data/v5-v6-research/batch2-2026-09-13-gate-report.json`
- `data/v5-v6-research/batch2-2026-09-13-accepted.csv`
- `data/v5-v6-research/batch2-2026-09-13-rejected.csv`
- `data/v5-v6-research/batch3-2026-09-13.md`
- `data/v5-v6-research/batch3-2026-09-13-gate-report.json`
- `data/v5-v6-research/batch3-2026-09-13-accepted.csv`
- `data/v5-v6-research/batch3-2026-09-13-rejected.csv`
- `data/v5-v6-research/batch4-2026-09-13.md`
- `data/v5-v6-research/batch4-2026-09-13-gate-report.json`
- `data/v5-v6-research/batch4-2026-09-13-accepted.csv`
- `data/v5-v6-research/batch4-2026-09-13-holds.csv`
- `data/v5-v6-research/batch5-2026-09-13.md`
- `data/v5-v6-research/batch5-2026-09-13-gate-report.json`
- `data/v5-v6-research/batch5-2026-09-13-accepted.csv`
- `data/v5-v6-research/batch5-2026-09-13-rejected-and-holds.csv`

These 89 records remain **staging only**. They are not yet labeled final V5 or V6, and they are not yet part of a send-ready 400-lead package.

## Current production runtime

Cashh Radar production already runs the unified Prospect Engine with 500 source-backed server-integrated prospects plus legacy browser records used for continuity. That existing production universe cannot automatically be relabeled as V5/V6 without passing the fresh-identity gate.

V5/V6 staging is a separate research boundary until the 400-new-prospect gate, enrichment, ranking, QA and final package build are complete. Research/docs commits are not evidence that the production Railway service has deployed them.

## Fresh-source expansion

Current public research sources being used for the next universe include:

- Builders' Exchange of Santa Clara County membership directory;
- current official business sites/contact pages;
- current contractor qualification / CUPCCAA lists where suitable;
- current city bid/planholder records;
- current public licensing, permit, carrier or procurement records when they materially support identity/activity;
- current municipal approved-vendor/caterer lists when they expose legitimate business contact evidence;
- other legitimate public business directories only when they provide usable business-contact evidence.

Official/current business pages are preferred for personalization. Government or procurement records are used as corroborating evidence when they establish current activity, location, qualification or a public business-intended contact.

## Required record gate for V5/V6

A record is not V5/V6-ready until it has:

- unique identity after V1–V4 comparison;
- no identity/email/business-domain/phone collision with already accepted V5/V6 staging records;
- business name;
- public/business-intended email;
- source URL;
- city/service area;
- industry/service focus;
- current observation suitable for personalization;
- source/check date;
- no known opt-out/bounce prohibition;
- no fabricated details;
- sufficient fit for the actual $100 package or a documented reason to hold it rather than force it into quota.

Shared platform hosts such as `sites.google.com` are evidence URLs, not business-domain fingerprints. Free/ISP email domains likewise are not treated as business website domains. A visible but masked email is not reconstructed from naming conventions.

Research holds are not force-promoted. Businesses with hidden/unverified email addresses, weak campaign fit, ambiguous location, identity conflicts, licensing concerns, or evidence that they are temporarily closed remain outside the accepted pool until the missing evidence is resolved.

## Required build after the 400-record gate passes

- 400 individualized first emails
- 400 1600×1000 business-specific preview graphics
- 400 `.eml` files with the matching image attached
- V5 Excel tracker
- V6 Excel tracker
- combined 400-lead tracker
- V5 portal
- V6 portal
- combined portal
- source/QA reports
- V5 ZIP
- V6 ZIP
- combined ZIP

Before the final split, research should materially exceed 400 accepted candidates so the system can rank and prune rather than treating the first 400 survivors as sacred tablets.

If Batch 5 is merged, the next exclusion universe is **836 records**: 747 canonical historical identities plus 89 accepted staging prospects.

## Payment

Use only:

`https://www.paypal.com/invoice/p/#7T6DC9A6WFH3XXCT`

No Venmo references in this campaign.

## Outreach policy

Email-first, no Reddit, no bulk BCC, one unanswered follow-up maximum, immediate opt-out handling, no repeated retries to bounced addresses, no fake scarcity, no fabricated outcomes, no guaranteed-response claims.
