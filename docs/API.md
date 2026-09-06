# Cashh Radar Commercial API — v2.2

## Authentication

Create an API key from the signed-in developer/Team controls. The raw key is returned once; only a SHA-256 hash is stored.

```text
X-API-Key: cr_...
```

## Scopes

- `opportunities:read`
- `watchlists:read`
- `alerts:read`
- `analytics:read`
- `usage:read`

## Endpoints

- `GET /api/v1/opportunities?limit=50`
- `GET /api/v1/watchlist`
- `GET /api/v1/alerts`
- `GET /api/v1/analytics`
- `GET /api/v1/usage`

Personal Pro keys use the configured Pro requests/minute limit. Organization keys use an organization-wide aggregate rate limit so issuing many keys does not multiply the tenant quota.

Organization keys stop authenticating when the key owner is removed from that organization.

## Evidence integrity

Opportunity responses retain verification/freshness states and provenance fields. Referral/provider compensation does not silently override evidence state or ranking.

## Team webhooks

Team admins can create outgoing HTTPS webhooks. Payloads include `X-Cashh-Event` and an `X-Cashh-Signature` HMAC-SHA256 signature. The signing secret is shown at webhook creation. Failed deliveries retry with backoff and are recorded.
