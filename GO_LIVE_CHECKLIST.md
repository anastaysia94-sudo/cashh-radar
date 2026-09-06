# Cashh Radar — Go-Live Checklist

## Required for core public launch
- [ ] Create GitHub repo `anastaysia94-sudo/cashh-radar`.
- [ ] Put v2.2 launch source at repository root.
- [ ] Connect GitHub to Render.
- [ ] Deploy root `render.yaml` as a Blueprint.
- [ ] Set owner email/password and support email directly in Render.
- [ ] Confirm `/api/health/ready` returns ready.
- [ ] Confirm homepage and five public policy/support pages load.
- [ ] Owner can sign in and see Admin.
- [ ] Grants.gov source refresh succeeds or reports a truthful source error.
- [ ] Create a new normal-user account and complete a basic workflow.

## Required before live paid plans
- [ ] Stripe live/test keys saved only in Render.
- [ ] Pro and Team recurring Price IDs configured.
- [ ] Stripe webhook points to `/api/billing/webhook`.
- [ ] Required subscription lifecycle events selected.
- [ ] Stripe Customer Portal enabled.
- [ ] Test checkout activates correct plan.
- [ ] Test cancellation/subscription deletion returns entitlement to Free.

## Required before enforced email verification
- [ ] SMTP credentials saved in Render.
- [ ] Password-reset email tested.
- [ ] Verification email tested.
- [ ] Team invite email tested if Teams are offered.
- [ ] Then set `CASHH_REQUIRE_EMAIL_VERIFICATION=1`.

## Recommended within first 24 hours
- [ ] Add uptime monitoring against `/api/health/ready`.
- [ ] Confirm automated `backups` job appears in Admin job history.
- [ ] Copy backups off the Render persistent disk to an independent location.
- [ ] Add a custom domain and set `CASHH_PUBLIC_URL`.
- [ ] Review public copy/policies for your actual operating entity and location.
- [ ] Verify all enabled data-source terms still permit the intended use.
