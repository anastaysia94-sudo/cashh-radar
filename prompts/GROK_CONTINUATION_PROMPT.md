# Grok Continuation Prompt — Cashh Radar

Paste this into Grok when continuing or auditing Cashh Radar.

```text
Continue the Cashh Radar project in GitHub repository `anastaysia94-sudo/cashh-radar`.

Cashh Radar is an opportunity intelligence and action system. It helps users discover, verify, score, track and act on legitimate money, work, grant and business opportunities. Public brand spelling is Cashh Radar with two h's. Tagline: Discover. Verify. Score. Act. Grow.

The product belongs under SmartPickShop Holdings and can visually correlate with EGM4000, F.S.A. and Founder Console, but it must stay a separate product/codebase unless I explicitly ask for integration.

Your job:
- Inspect the current repository and summarize the real state before making changes.
- Continue the highest-value unfinished development or launch task.
- Keep the app launchable through Docker/Render.
- Add tests for every meaningful backend/security/business-logic change.
- Update docs/status/changelog when you change behavior.
- Help me push clean changes back to GitHub.

Integrity rules:
- Never fabricate live opportunities, users, payments, revenue, testimonials or outcomes.
- Never guarantee income.
- Label uncertain claims and preserve source/evidence metadata.
- Do not pretend Stripe, SMTP, USAJOBS, Lever, hosting, domain, monitoring or legal review are active unless verified.
- Keep secrets out of GitHub.

Validation before saying done:
- python -m pytest -q
- python -m py_compile app.py
- node --check static/app.js
- node --check static/sw.js
- python scripts/preflight.py, if present

For upload/push:
- Use a normal feature branch for non-emergency changes.
- Do not commit .env, local DB files, WAL/SHM files, logs, venvs or caches.
- Commit with clear messages.
- Push to `anastaysia94-sudo/cashh-radar`.
```
