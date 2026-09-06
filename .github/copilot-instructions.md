# GitHub Copilot Project Instructions

This repository is Cashh Radar.

Cashh Radar is an evidence-labeled opportunity intelligence and action platform under the SmartPickShop Holdings ecosystem. It helps users discover, verify, score, track and act on legitimate money/work/grant/business opportunities.

## Non-negotiable rules

- Do not fabricate opportunities, users, payments, reviews, testimonials, revenue or outcomes.
- Do not guarantee income or profit.
- Preserve evidence, provenance, timestamps, lifecycle states and verification labels.
- Keep secrets out of GitHub. Never commit `.env`.
- Do not commit local databases, virtual environments, logs or test caches.
- Keep Docker and Render deployment working.
- Keep user/account/team/API routes permission-scoped.
- Hash secrets, reset tokens, two-step codes and API keys.
- Keep Team/organization data tenant-scoped.

## Required validation

Before declaring a change complete, run:

```bash
python -m pytest -q
python -m py_compile app.py
node --check static/app.js
node --check static/sw.js
python scripts/preflight.py
```

## Brand rules

Public spelling: **Cashh Radar**.  
Tagline: **Discover. Verify. Score. Act. Grow.**

Keep Cashh Radar separate from EGM4000, F.S.A., Founder Console and other products unless the owner explicitly requests integration work.
