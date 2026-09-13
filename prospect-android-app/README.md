# Cashh Radar Prospect Engine — Mobile PWA

Cashh Radar's mobile-first prospect execution surface. It is mounted by the production FastAPI launcher at `/prospects/` and is designed to turn a large prospect universe into one clear next-best action at a time.

## Current runtime — v4

The canonical entrypoints are `index.html` and the backward-compatible `easy.html`. Both now load the same v4 runtime:

1. `prospects.js` supplies the legacy prospect seed.
2. Four packed `data/p500-gz-*.js` chunks supply the 500 source-backed Santa Clara County business records.
3. `data/p500-loader.js` decompresses and integrity-checks that dataset in the browser.
4. `bootstrap-v4.js` combines the source-backed and legacy records into the 700-prospect queue.
5. `easy-v4-core.js`, `easy-v4-policy.js`, `easy-v4-ui.js`, and `easy-v4-image.js` layer ranking, outreach policy, mobile workflow, compliance controls, and business-specific outreach imagery over the base app.

The loader refuses to continue if the packed business dataset does not contain exactly 500 records with 500 unique public email values.

## Outreach policy enforced in code

The active v4 workflow is email-first and excludes Reddit from prospect prioritization.

- The 500 source-backed business records are prioritized when they retain a public email and source evidence.
- Legacy Reddit rows that have not already entered a real lifecycle state are marked `DO NOT PRIORITIZE — REDDIT DISABLED`.
- Other untouched legacy rows without a verified email are marked `DEPRIORITIZE — NO VERIFIED EMAIL`.
- Existing `SENT`, `REPLIED`, and `WON / PAID` lifecycle records are preserved instead of being rewritten by the policy layer.

No email address, reply, payment, customer, outcome, or verification event may be fabricated.

## Next-best-action flow

The app automatically prioritizes:

1. Prospects who replied.
2. Previously contacted prospects whose follow-up is due.
3. Source-backed business prospects with a public email.
4. Eligible legacy email prospects.

For the focused prospect, the app walks through:

1. **Verify** — inspect the real source and confirm the record is still usable.
2. **Contact** — use the verified/public contact route.
3. **Draft** — prepare the correct initial, follow-up, qualification, or close message.
4. **Confirm** — only after the user actually sends the message, mark it sent and move to the next action.

The app does not silently send outreach.

## Business outreach compliance gate

The 500 business-outreach records require a physical postal address in local Settings before the commercial send action is unlocked. The address is appended to the commercial message template along with opt-out language.

This is an application safeguard, not a legal conclusion. Users remain responsible for complying with applicable law, platform rules, and truthful advertising requirements.

## Gmail draft mode

With an optional Google OAuth Client ID, Cashh Radar can create a Gmail draft for review containing the prospect recipient, subject, message body, and generated prospect PNG. It does not press Send.

Without Gmail OAuth, the app can open the device email composer with recipient, subject, and body populated when a verified/public email is available.

## PWA install and offline behavior

`pwa-runtime.js` registers `sw.js`, handles the browser install prompt when available, and reports when an updated service worker is ready.

The service worker caches the complete active prospect runtime, including:

- the v4 shell and styles;
- packed 500-record data chunks and loader;
- v4 core, policy, UI, and image layers;
- legacy seed data;
- manifest and icon.

Navigation uses a network-first strategy with the cached canonical shell as the offline fallback. Static runtime assets use cached copies with background network refresh.

## Production mount

`launcher.py` mounts this directory at:

```text
/prospects/
```

The Docker and Railway launch paths use `uvicorn launcher:app`, so the prospect PWA ships with the main Cashh Radar service rather than depending on a separate static-site deployment.

## CI protection

`.github/workflows/test.yml` now checks that:

- both entrypoints load v4;
- the service worker caches all v4 runtime dependencies;
- the outreach policy remains email-first with Reddit disabled;
- the packed business dataset still expands to 500 rows with 500 unique public emails;
- all active JavaScript files pass `node --check`;
- Python tests, compilation, deployment configuration, and Docker build smoke tests still pass.

## Data integrity rules

Preserve source evidence and existing user lifecycle state. Never invent:

- prospects;
- email addresses;
- source verification;
- replies;
- payments;
- customers;
- testimonials;
- earnings or outcomes.

When evidence expires or cannot be reverified, mark that uncertainty instead of pretending the record is current.
