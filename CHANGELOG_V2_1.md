# Cashh Radar v2.1.0 — Operations & Enterprise Hardening

## Added
- Team invitation tokens with 7-day expiry and optional SMTP delivery.
- Organization member roles: owner, admin, analyst, member.
- Member role updates and removal controls.
- Tenant branding visibility in organization listings.
- Organization-scoped commercial API keys and per-key rate limits.
- Referral signup attribution; Stripe conversion attribution hook.
- User-visible provider request history.
- Admin provider-lead lifecycle and provider pipeline analytics.
- Persistent background-job history.
- Scheduler-safe maintenance, alert evaluation, and digest dispatch jobs.
- `/api/health/live`, `/api/health/ready`, and richer `/api/health`.
- Protected Prometheus-style `/api/metrics`.
- Additive schema migration tracking.
- `scripts/run_jobs.py` and `scripts/preflight.py`.
- Operations and expanded enterprise/API documentation.

## Validation
- 12 automated tests passing.
- Python compilation passes.
- JavaScript syntax validation passes.
- Local packaged database upgraded to schema version 2.
