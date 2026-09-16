# Cashh Radar — V5 + V6 Ethical Expansion — FINAL BUILD STATUS

Updated: 2026-09-16

## Final scope

The V5 + V6 expansion now contains **400 genuinely new Santa Clara County prospect records** split into two balanced outreach experiments:

- **V5: 200** — Show the work + clear value
- **V6: 200** — Show the work + choice/control

All final records retain a public source URL and a business-intended email. No guessed email addresses are permitted.

## Canonical historical exclusion audit

Recovered V1–V4 files contain 750 raw rows and **747 canonical historical identities**. Those historical campaign identities remain excluded from V5/V6 even when a later listing, employee address, location page or refreshed website exists.

## Staging correction and final dedupe

A final QA pass found that the old Batch 10 research roster duplicated the 15 businesses already accepted in Batch 9. Rather than hiding the collision behind a cumulative count, the duplicate Batch 10 accepted file was removed and the pool was corrected to **385 unique accepted prospects**.

Batch 24 then added **15 newly researched, source-backed businesses** with repo-level name/email collision checks, returning the final pool to exactly **400 unique business identities and 400 unique public business emails**.

Final gate report:

- `data/v5-v6-research/batch24-2026-09-16-gate-report.json`
- Final unique V5/V6 staging: **400**
- Historical V1–V4 identities: **747**
- Final exclusion universe: **1,147 identities**
- Remaining to 400: **0**

## Final generated production assets

GitHub Actions workflow:

- `.github/workflows/build-v5-v6-final.yml`
- Latest verified successful build run: `35089378681`
- Build artifact: `cashh-radar-v5-v6-assets`

The final build generates and QA-checks:

- 200 V5 records
- 200 V6 records
- 400 individualized first emails
- 400 business-specific 1600×1000 preview graphics
- 400 `.eml` files with the matching preview attached
- V5 searchable local portal
- V6 searchable local portal
- combined 400-lead portal
- V5/V6 CSV + JSON datasets
- Why-V5/Why-V6 rationale files
- top-25 priority lists
- source evidence retained per record
- ethical persuasion research notes
- combined QA report

The complete downloadable final packages additionally contain:

- `Santa-Clara-County-200-V5-Ethical-Prospect-Tracker.xlsx`
- `Santa-Clara-County-200-V6-Ethical-Prospect-Tracker.xlsx`
- `Santa-Clara-County-400-V5-V6-Ethical-Master-Tracker.xlsx`
- V5 complete ZIP
- V6 complete ZIP
- combined 400-lead master ZIP

## Final QA

Final package QA passed the following checks:

- **400 records**
- **400 unique normalized business identities**
- **400 unique public business emails**
- **400/400 source URLs present**
- **200 V5 + 200 V6**
- **400 graphics**
- **400 unique graphic hashes**
- **all graphics 1600×1000**
- **400 ready `.eml` files**
- correct recipient / subject / body / attachment mapping
- **400/400 initial emails include the approved PayPal invoice link**
- **0 Venmo references**
- portal record counts: 200 / 200 / 400
- three Excel trackers built with `artifact_tool`
- Excel formula-error scans passed
- V5 ZIP integrity passed
- V6 ZIP integrity passed
- combined ZIP integrity passed

A Unicode subject-folding edge case found during `.eml` QA was corrected by regenerating the final email files with a long-line SMTP policy and re-running recipient/subject/body/attachment validation.

## Payment

Use only:

`https://www.paypal.com/invoice/p/#7T6DC9A6WFH3XXCT`

No Venmo references are permitted in this campaign.

## Outreach policy

- Email-first
- No Reddit prospecting
- No bulk BCC
- Individual review and send
- Matching preview image in the first email
- Transparent $100 one-time price and deliverables
- Optional PayPal buy-now path plus questions-first path
- One unanswered follow-up maximum
- Honor opt-outs immediately
- Do not repeatedly retry bounced addresses
- No fake scarcity or fabricated urgency
- No invented testimonials, problems, outcomes, payments or replies
- No guaranteed-response, guaranteed-customer or guaranteed-revenue claims
- Use actual V5/V6 outcomes to determine which messaging approach performs better

## Completion state

**Research gate: COMPLETE**  
**400-record dedupe: COMPLETE**  
**V5/V6 split: COMPLETE**  
**Graphics: COMPLETE**  
**Attached email files: COMPLETE**  
**Local portals: COMPLETE**  
**Excel trackers: COMPLETE**  
**QA: PASS**  
**ZIP packaging: COMPLETE**  
**GitHub build workflow: PASS**
