# Cashh Radar v2.2.0 — Launch Completion

Date: 2026-09-03

## Account & security completion
- Email verification tokens and confirmation flow.
- Optional requirement for verified email in production.
- Optional two-step email login with expiring one-time codes.
- Admin bootstrap accounts are marked verified.
- Stronger readiness checks for HTTPS, schema and configured email requirements.

## Retention / alerts
- New-match and saved-search evaluation.
- Deadline and material-change rules execute.
- Rule deletion and digest cadence/preferences.
- Free plan's five-save entitlement is enforced.

## Teams / enterprise
- Shared organization watchlist.
- Ownership transfer and safe workspace deletion.
- Tenant-scoped SCIM-style provisioning/deprovisioning.
- Organization-scoped API quotas and key revocation when membership is removed.
- Signed organization outgoing webhooks with retries.

## API / monetization integrity
- Commercial API scopes for opportunities, watchlist, alerts, analytics and usage.
- Referral conversion events cannot be spoofed publicly.
- Stripe webhook idempotency check.
- Stripe subscription lifecycle tracking and automatic entitlement downgrade on cancellation.
- Stripe Customer Portal session endpoint for subscriber self-service.

## Operations / launch
- Source, webhook and verified-backup jobs.
- Optional in-process single-instance scheduler.
- Schema migration v4.
- Production preflight expanded.
- Root Render Blueprint included.
- Launch Privacy, Terms, Disclosures, Security and Support pages.
- Sitemap expanded to public policy/support routes.
