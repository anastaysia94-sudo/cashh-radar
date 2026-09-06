# Cashh Radar Team / Enterprise Foundation — v2.2

## Implemented

- owner/admin/analyst/member workspace roles;
- seven-day team invites with optional SMTP delivery;
- role changes/removal and safe owner transfer;
- shared organization watchlist;
- workspace deletion controls;
- tenant brand name, accent, logo URL and custom-domain metadata;
- organization-scoped commercial API keys and aggregate quotas;
- signed outgoing organization webhooks with retry history;
- SCIM-style bearer-token user provisioning/deprovisioning;
- audit/analytics/operations/job history.

## Not represented as completed when it is not

This launch build does **not** claim turnkey SAML/OIDC enterprise SSO, PostgreSQL row-level-security isolation, dedicated customer databases, negotiated SLAs, or customer-specific contracts. Those are scale/contract features to provision when an actual enterprise requirement exists.

## Launch isolation model

Initial production uses logical tenant isolation inside the single shared SQLite database. This is suitable for early Team use. Before high-volume multi-instance or compliance-heavy contracts, migrate to managed PostgreSQL and select/test an explicit tenant-isolation model.
