# Cashh Radar — V5 + V6 Ethical Expansion Checkpoint

Updated: 2026-09-13

## Goal

Build **400 genuinely new Santa Clara County business prospects**:

- V5: 200 — **Show the work + clear value**
- V6: 200 — **Show the work + choice + control**

Every final record must retain public source evidence and a business-intended email. No prospect may be invented merely to fill quota.

## Canonical historical exclusion audit

Recovered V1–V4 files contain:

- V1: 150 rows
- V2: 200 rows
- V3: 200 rows
- V4: 200 rows
- Raw historical rows: **750**
- Canonical historical identities: **747**
- Repo-gate normalized business names: **732**
- Unique public email values: **722**
- Unique website/domain values observed: **506**

Known cross-version duplicate identities are treated as one exclusion identity rather than a fresh prospect:

1. Blue's Roofing — V3 + V4
2. South Bay Design & Landscaping — V3 + V4
3. D&D Electrical Construction — V3 + V4

The canonical exclusion workbook remains authoritative. The repo gate applies stricter normalization on top of it, so a changed employee email does not magically turn an old business into a fresh lead.

## Recovered 500-row expert workbook

`500_EXPERT_VERIFIED_INDIVIDUALIZED_EMAILS_2026-09-07.xlsx` was audited against the historical universe:

- 500 rows inspected
- **0 genuinely new V5/V6 identities**
- all 500 matched the historical universe by normalized business name, public email, and/or website/domain

It remains useful as a copy-quality and exclusion reference, but it must **not** be relabeled as V5/V6.

## Current V5/V6 staging progress

The fresh-source pipeline has now advanced through **Batch 11**.

| Pass | Accepted | Cumulative |
|---|---:|---:|
| Seed | 36 | 36 |
| Batch 2 | 11 | 47 |
| Batch 3 | 12 | 59 |
| Batch 4 | 15 | 74 |
| Batch 5 | 15 | 89 |
| Batch 6 | 15 | 104 |
| Batch 7 | 15 | 119 |
| Batch 8 | 15 | 134 |
| Batch 9 | 15 | 149 |
| Batch 10 | 15 | 164 |
| Batch 11 | 14 | **178** |

### Current checkpoint

- **Accepted staging pool: 178 genuinely new, source-backed prospects**
- Remaining to the 400 accepted-candidate threshold: **222**
- Current exclusion universe for the next pass: **925 records**
  - 747 canonical historical identities
  - 178 accepted staging prospects

These records are still **STAGING ONLY**. They are not yet labeled final V5 or V6 and are not yet a send-ready 400-lead package.

The research program intentionally continues beyond narrow contractor/home-service categories. Recent accepted batches also include property management, ceramics/art instruction, retail, pet care, interior design, photography, salon/beauty, restaurants/private events, floral, bakery, yoga, cleaning, dance, martial arts, moving, music instruction, home organization and tutoring.

## Latest research audit files

Earlier batch artifacts remain under `data/v5-v6-research/`. The newest checkpoints are:

- `data/v5-v6-research/batch8-2026-09-13.md`
- `data/v5-v6-research/batch8-2026-09-13-gate-report.json`
- `data/v5-v6-research/batch8-2026-09-13-accepted.csv`
- `data/v5-v6-research/batch9-2026-09-13.md`
- `data/v5-v6-research/batch9-2026-09-13-gate-report.json`
- `data/v5-v6-research/batch10-2026-09-13.md`
- `data/v5-v6-research/batch11-2026-09-13.md`
- `data/v5-v6-research/batch11-2026-09-13-gate-report.json`

Raw/public contact fields are retained only where supported by current business evidence. A missing CSV is not permission to reconstruct or guess an address.

## Current production runtime

Cashh Radar production already runs the unified Prospect Engine with 500 source-backed server-integrated prospects plus legacy browser records used for continuity. That existing production universe cannot automatically be relabeled as V5/V6 without passing the fresh-identity gate.

V5/V6 staging remains a separate research boundary until the 400-new-prospect gate, enrichment, ranking, QA and final package build are complete. Research/documentation commits are not evidence that the Railway production service has deployed them.

## Fresh-source expansion

Current public research sources include:

- Builders' Exchange of Santa Clara County membership directory;
- current official business sites/contact pages;
- current contractor qualification / CUPCCAA lists where suitable;
- current city bid/planholder records;
- current licensing, permit, carrier or procurement records when they materially support identity/activity;
- municipal approved-vendor/caterer lists when they expose legitimate business contact evidence;
- local chamber and event-vendor sources when they materially corroborate location or current activity;
- other legitimate public business directories only when they provide usable business-contact evidence.

Official/current business pages are preferred for personalization. Government, chamber or procurement records are corroborating evidence when they establish current activity, location, qualification or public business-intended contact information.

## Required record gate for V5/V6

A record is not V5/V6-ready until it has:

- unique identity after V1–V4 comparison;
- no identity/email/business-domain/phone collision with accepted V5/V6 staging;
- business name;
- public/business-intended email;
- source URL;
- city/service area;
- industry/service focus;
- current observation suitable for personalization;
- source/check date;
- no known opt-out/bounce prohibition;
- no fabricated details;
- sufficient fit for the $100 package or a documented reason to hold rather than force it into quota.

Shared hosts such as `sites.google.com` or Wix are evidence URLs, not business-domain fingerprints. Free/ISP email domains are not treated as owned business domains. Masked email addresses are not reconstructed from naming conventions. Stale local listings do not override stronger current evidence. When a current owned-domain contact supersedes an older alias, the current address is re-gated before use.

Research holds are not force-promoted. Businesses with hidden/unverified email addresses, weak fit, ambiguous or out-of-scope location, identity conflicts, licensing concerns, heavy compliance concerns, temporary closure evidence or poor personalization quality remain outside the accepted pool until resolved.

## Required build after the 400-record gate passes

Only after the fresh-prospect gate passes and deliberate over-research/rank/prune is complete:

- 400 individualized first emails
- 400 business-specific 1600×1000 preview graphics
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

Research should materially exceed 400 accepted candidates before the final split so the system can rank and prune instead of treating the first 400 survivors as sacred tablets. Humanity has suffered enough from sacred spreadsheets.

## Payment

Use only:

`https://www.paypal.com/invoice/p/#7T6DC9A6WFH3XXCT`

No Venmo references in this campaign.

## Outreach policy

- Email-first
- No Reddit prospecting
- No bulk BCC
- Individual review
- One unanswered follow-up maximum
- Honor opt-outs immediately
- Do not repeatedly retry bounced addresses
- No fake scarcity
- No fabricated urgency
- No invented testimonials or outcomes
- No guaranteed-response or guaranteed-revenue claims
- Preview images and copy must remain truthful to public business evidence
