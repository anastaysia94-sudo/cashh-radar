# V5/V6 Research + Dedupe Pipeline

This pipeline exists to prevent historical V1–V4 prospects from being relabeled as “new” V5/V6 leads.

## Required candidate fields

Every candidate must include, at minimum:

- Business / business name
- Email / public business-intended email
- SourceURL / public evidence URL
- City / service area
- Industry / service focus
- Observation / current business-specific personalization signal

Website/domain and phone are strongly preferred because they improve duplicate detection.

## Gate behavior

`scripts/v5_v6_gate.py` compares each candidate against the historical exclusion universe using normalized:

- business name;
- public email;
- domain;
- phone.

It also rejects duplicates inside the candidate batch itself.

The script does **not** infer or invent missing fields. A record missing the evidence fields above is rejected instead of being allowed through to hit a quota.

## Usage

```bash
python scripts/v5_v6_gate.py \
  --history-csv path/to/v1-v4-exclusion.csv \
  --candidates path/to/fresh-candidates.csv \
  --out-dir build/v5-v6-gate
```

Outputs:

- `accepted.csv`
- `rejected.csv`
- `report.json`

Only `accepted.csv` should continue to individualized-email, graphic, `.eml`, tracker, portal and ZIP generation.

## Ethical outreach constraints

- public/business-intended email evidence only;
- no guessed email patterns;
- email-first;
- no Reddit prospecting;
- individual review rather than bulk BCC;
- one unanswered follow-up maximum;
- immediate opt-out handling;
- bounced addresses are reverified before retry;
- no fake scarcity, fabricated urgency, invented testimonials, fabricated outcomes or guaranteed-response claims;
- current payment route is the PayPal invoice documented in `V5_V6_STATUS.md`.
