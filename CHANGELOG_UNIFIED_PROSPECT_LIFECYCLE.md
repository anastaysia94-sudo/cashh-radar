# Cashh Radar — Unified Prospect Lifecycle

Updated: 2026-09-12/13

## Completed

- Mapped the 500 source-backed business prospects into the canonical Cashh Radar opportunity database.
- Added schema v6 prospect catalog, per-user state, event and refresh-run tables.
- Connected sent outreach, replies and outcomes to the existing opportunity pipeline and bounded learning loop.
- Added persistent server-side prospect state with offline browser reconciliation.
- Added actual-time tracking and realized value-per-hour after a real amount is recorded.
- Added clearly labeled modeled offer-value-per-hour before a real outcome exists.
- Added automatic/manual public-source freshness checks with private-network URL protection.
- Added unified Radar ranking across client prospects and other money/work opportunities.
- Added broader-Radar visibility inside the Prospect Engine Progress view.
- Added server lifecycle/evidence/hourly-value controls to the focused mobile prospect card.
- Prevented authenticated `/api/*` responses from entering the prospect PWA service-worker cache.
- Preserved email-first / no-Reddit outreach policy and commercial-email preflight behavior.
- Expanded CI to 41 passing tests plus JS syntax, PWA/data integrity and Docker build validation.
- Migrated Railway production SQLite storage to a 1 GB persistent volume at `/app/data` before deploying server-persisted prospect state.

## Evidence semantics

The unified ranking intentionally keeps these concepts separate:

- source-backed public facts;
- freshness/reachability checks;
- model assumptions such as a proposed $100 offer and estimated fulfillment time;
- actual recorded replies/outcomes;
- realized value-per-hour derived only from actual amount and tracked time.

A proposal is never converted into a payment, customer, earnings claim or testimonial by the software.

## Production constraints

The SQLite launch architecture remains single-replica. Multi-instance scaling requires a managed shared database plus deliberately tested tenant isolation and a shared worker/job system.
