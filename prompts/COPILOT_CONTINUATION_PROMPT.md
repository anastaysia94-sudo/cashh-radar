# GitHub Copilot Instructions — Cashh Radar

Use this with GitHub Copilot Chat or save the short version as `.github/copilot-instructions.md`.

## Role

You are helping maintain and extend Cashh Radar in `anastaysia94-sudo/cashh-radar`.

Cashh Radar is a FastAPI web/PWA product for opportunity intelligence: discovery, source evidence, freshness, scoring, saved searches, alerts, roadmaps, outreach, outcome tracking, admin operations, subscriptions, referrals, provider leads, Teams, enterprise API and white-label metadata.

## Guardrails

- Do not add fake users, fake revenue, fake payments, fake testimonials or fake outcomes.
- Do not guarantee income.
- Preserve evidence labels, source URLs, observed timestamps, material-change hashes and lifecycle states.
- Keep `.env` and secrets out of the repo.
- Do not commit local DB files, WAL/SHM files, logs, virtualenvs or cache folders.
- Keep Render/Docker launch compatibility intact.
- Keep UI responsive and usable on mobile.

## Coding rules

- Prefer clear standard-library Python unless a dependency is already listed in `requirements.txt`.
- Use explicit permission checks for admin, organization and API routes.
- Keep tenant/organization data scoped by organization ID.
- Hash sensitive tokens/API keys; never store plaintext key material after initial display.
- Validate inputs with Pydantic or existing helper patterns.
- Add tests for security, entitlement and multi-tenant behavior.
- Keep errors user-safe and logs secret-safe.

## Required checks before completion

```bash
python -m pytest -q
python -m py_compile app.py
node --check static/app.js
node --check static/sw.js
python scripts/preflight.py
```

## GitHub workflow

For larger changes:

```bash
git checkout -b feature/<short-name>
git add .
git commit -m "Describe the Cashh Radar change"
git push origin feature/<short-name>
```

Open a pull request into `main`. For emergency launch-only edits, commit directly only when the owner explicitly asks.
