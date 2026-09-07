# Cashh Radar — Canonical Opportunity Loop

Cashh Radar has one canonical operating loop:

> **Discover → Verify → Score → Explain → Generate Action → Act → Track Response → Record Outcome → Learn**

The purpose of this loop is to turn the product from a collection of useful tools into one evidence-backed system whose recommendations improve from actual user outcomes.

## State model

| Stage | Meaning |
|---|---|
| `discovered` | The opportunity exists in the Radar. |
| `verified` | Source/evidence state has been evaluated. |
| `scored` | User-fit and evidence scoring has been computed. |
| `explained` | Cashh Radar explains the score, risks, eligibility, and evidence. |
| `action_ready` | A concrete application/outreach action is prepared. |
| `acted` | The user records that the action was actually sent/submitted. |
| `responded` | A reply/question/interview/acceptance/rejection is recorded. |
| `outcome_recorded` | A funnel or financial outcome is recorded. |
| `learned` | The outcome is now eligible to influence sufficiently similar future rankings. |

Stages move forward only. A rejection does not erase the history; it is recorded as an outcome inside a completed learning loop.

## API

### Run the loop for an opportunity

`POST /api/loop/run`

Input:

```json
{
  "opportunity_id": "demo-002",
  "asset_type": "auto",
  "generate_action": true
}
```

The response includes:

- verification status and evidence score;
- base personalized score;
- learned adjustment;
- final bounded score;
- transparent explanation;
- a specific application/outreach action;
- the next lifecycle step.

### Record that the user acted

`POST /api/loop/{opportunity_id}/actioned`

This is intentionally explicit. Generating an email or proposal does **not** count as contacting someone. The user/system must record the real action after it happened.

### Record a response

`POST /api/loop/{opportunity_id}/response`

Supported response types: `reply`, `question`, `interview`, `accepted`, `rejected`, `no_response`.

Where appropriate, response events map into the existing Cashh Radar outcome funnel (`replied`, `interview`, `won`, `lost`).

### Record an outcome

`POST /api/loop/{opportunity_id}/outcome`

Supported stages reuse the existing Cashh Radar outcome vocabulary:

`saved`, `started`, `applied`, `contacted`, `replied`, `interview`, `negotiating`, `won`, `paid`, `fulfilled`, `follow_up`, `lost`.

### Inspect one loop

`GET /api/loop/{opportunity_id}`

Returns the current pipeline record, chronological lifecycle events, and recorded outcomes.

### Inspect the user's pipeline

`GET /api/loop`

Returns canonical opportunity records ordered by current score and recency.

### Inspect learning evidence

`GET /api/loop-learning`

Returns grouped historical outcome evidence and documents the learning method.

## Learning rules

Learning is deliberately conservative.

1. Only the **latest recorded outcome per prior opportunity** is used for ranking feedback. This prevents one opportunity's intermediate stages from counting as multiple independent successes.
2. Prior outcomes must be sufficiently similar by category, work mode, or source before they affect a new opportunity.
3. Signals are similarity-weighted and shrunk toward zero so a tiny sample cannot dominate.
4. The learning adjustment is capped at **±10 points**.
5. Source evidence and user fit remain the primary score.
6. The system explains when historical outcomes changed a score and how many relevant samples were used.

This is an adaptive ranking signal, not a guarantee of income, acceptance, eligibility, replies, or future availability.

## Data model

The orchestration layer adds only two tables:

- `opportunity_pipeline` — one current lifecycle record per user/opportunity;
- `pipeline_events` — append-only lifecycle history.

It reuses the existing canonical Cashh Radar tables for:

- `opportunities` — discovery/source records;
- `outreach_assets` — generated outreach;
- `outcomes` — funnel and financial results;
- `analytics_events` — product telemetry.

The loop therefore consolidates existing workflows instead of creating another competing CRM.

## Canonical product rule

New Fast Cash, prospecting, CRM, outreach, Advisor, watchlist, response, and outcome features should connect to this lifecycle wherever practical. They should not create a second independent pipeline unless there is a clear product requirement that cannot be represented here.
