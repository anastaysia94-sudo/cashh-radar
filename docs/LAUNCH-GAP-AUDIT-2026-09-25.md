# Cashh Radar launch gap audit — 2026-09-25

## Verified current state

Repository: `anastaysia94-sudo/cashh-radar`

Current GitHub main head checked: `2608105f996d42e4acc02c0ded97fb612b496fb0`

Railway production service: `cashh-radar-web`

Railway currently reports production source commit:

`213cc0e20947a509af3b5329fa5aec1c842ee8f0`

The service is healthy at the existing deployment, but production is **behind current main**.

## First launch blocker

**Deploy current GitHub main to the existing Railway service.**

Do not use an ordinary Railway **Redeploy** as the fix. Redeploy repeats the existing deployed revision. The needed operation is **Deploy Latest Commit**, or an equivalent operation that explicitly deploys `2608105f...` to the existing `cashh-radar-web` service.

Do not create a duplicate Railway service.

## Acceptance checks after latest-main deployment

1. Railway source/deployment commit equals `2608105f996d42e4acc02c0ded97fb612b496fb0`.
2. Deployment status is SUCCESS.
3. `GET /api/health/ready` succeeds.
4. `GET /api/health` succeeds.
5. `GET /api/prospects/status` succeeds.
6. `GET /prospects/` renders.
7. Persistent `/app/data` storage remains attached/available.
8. Keep one production application replica while SQLite is the production datastore.
9. Confirm auth/session behavior from a real browser.
10. Confirm mobile layout and installability if the PWA is part of the release claim.

## Evidence integrity

Technical deployment does not prove outreach, replies, customers, payments, revenue, or product-market fit. Those states must come from real activity and must not be synthesized during QA.

## Launch status

**Code/main:** ahead of production.

**Production service:** running, but stale revision.

**Launch-ready:** NO, until latest main is deployed and the acceptance checks above pass.
