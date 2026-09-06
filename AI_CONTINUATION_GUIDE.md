# Cashh Radar — AI Continuation Guide

Use this file when continuing Cashh Radar with ChatGPT, GitHub Copilot, Grok, Perplexity, Codex, or another AI coding/research assistant.

## Project identity

**Project:** Cashh Radar  
**Repository:** `anastaysia94-sudo/cashh-radar`  
**Product type:** opportunity intelligence and action platform  
**Public brand spelling:** `Cashh Radar` with two h's in Cashh  
**Tagline:** `Discover. Verify. Score. Act. Grow.`  
**Parent ecosystem:** SmartPickShop Holdings  
**Sibling projects:** EGM4000, Fish Shooter Arcade / F.S.A., Founder Console

Keep this project separate from EGM4000, Fish Shooter Arcade, Founder Console, Founder Dynasty OS and other workspaces unless the user explicitly asks for an integration.

## What Cashh Radar does

Cashh Radar helps users discover, verify, score, track and act on legitimate money/work/business/grant opportunities. It should never guarantee income, fabricate leads, fabricate users, fabricate reviews, fabricate payment results, or pretend an external source is connected when credentials or terms are missing.

Core product loop:

1. Discover opportunities.
2. Preserve source/evidence/provenance.
3. Verify freshness and legitimacy.
4. Score opportunities against user goals and constraints.
5. Help users act with roadmaps, outreach and alerts.
6. Track outcomes honestly.

## Evidence and integrity rules

Every external opportunity, market, pricing, legal, competitor or customer-behavior claim should be labeled or supported as one of:

- verified fact;
- current external evidence;
- customer-derived evidence;
- internal observation;
- strategic hypothesis;
- financial model assumption;
- forecast;
- illustrative example.

Never invent:

- market size;
- opportunity availability;
- platform fees;
- customer outcomes;
- user testimonials;
- revenue;
- payments;
- verified sources;
- active integrations;
- legal/regulatory conclusions.

When unsure, say what is unknown and what should be checked.

## Current launch direction

The intended launch path is a Dockerized FastAPI web app on Render using the included `render.yaml`, persistent `/app/data` storage, and a production environment configured in the host dashboard.

Launch should support a free/core product even if Stripe, SMTP, USAJOBS and Lever are not activated yet. Paid plans and email-based features should remain optional until the owner supplies credentials directly in the hosting dashboard.

## Important external activation boundaries

AI assistants must not claim these are complete unless verified in the real external service:

- public deployment is live;
- custom domain/DNS is active;
- Stripe live keys and Price IDs are configured;
- Stripe webhook is registered and verified;
- SMTP is configured and tested;
- USAJOBS credentials are supplied;
- Lever employer allowlist is selected;
- monitoring/backups are connected;
- legal review has been completed.

## Development standards

- Preserve existing functionality.
- Keep secrets out of GitHub.
- Commit `.env.example`, never `.env`.
- Do not commit SQLite production databases, WAL files, logs, test caches or virtualenvs.
- Keep the project launchable with Docker.
- Keep Render deployment files valid.
- Run tests before declaring a build complete.
- Update `README.md`, `MASTER_STATUS.md`, `TEST_REPORT.md`, `CHANGELOG_*.md`, and launch/deployment docs when major features change.
- Keep UI mobile-friendly.
- Maintain accessibility basics: semantic labels, readable contrast, keyboard-friendly flows where possible.
- Keep language understandable for a non-technical founder.

## Minimum validation before saying a build is finished

Run or ask the owner to run:

```bash
python -m pytest -q
python -m py_compile app.py
node --check static/app.js
node --check static/sw.js
```

For deployment readiness also run the project preflight script if present:

```bash
python scripts/preflight.py
```

Then smoke test:

```bash
curl -I http://127.0.0.1:8000/
curl http://127.0.0.1:8000/api/health
curl http://127.0.0.1:8000/api/health/live
curl http://127.0.0.1:8000/api/health/ready
```

## GitHub upload / push instructions

Preferred local Git upload after extracting the launch ZIP:

```bash
git clone https://github.com/anastaysia94-sudo/cashh-radar.git
cd cashh-radar
# copy/extract the launch build contents into this folder, replacing placeholders but not adding secrets
git status
git add .
git commit -m "Publish Cashh Radar launch build"
git push origin main
```

If using the GitHub web UI:

1. Open the repository.
2. Choose **Add file → Upload files**.
3. Drag the extracted project files and folders, not the ZIP alone.
4. Commit directly to `main` only if this is the first launch upload.
5. For later changes, use a branch and pull request.

Never upload `.env`, local databases, virtualenv folders or secret files.

## Recommended next work after launch

1. Verify repository file tree is complete.
2. Deploy to Render from `render.yaml`.
3. Enter production secrets directly in Render.
4. Confirm `/api/health/ready` reports ready.
5. Test registration, login, watchlist, saved search, Roadmap, Outreach, Pulse, export, support/legal pages.
6. Enable SMTP only after a real test email arrives.
7. Enable Stripe only after test checkout, webhook and cancellation are verified.
8. Add custom domain after the Render service is stable.
9. Start expanding live opportunity data sources while respecting source terms.
10. Add monitoring and off-platform backup storage before significant traffic.

## Product positioning language

Safe public description:

> Cashh Radar helps you discover, verify, score, track and act on legitimate money opportunities using source-backed data and personalized opportunity intelligence.

Avoid:

- guaranteed money;
- guaranteed income;
- best chance of profit;
- risk-free opportunity;
- fake testimonials;
- fake user counts;
- fake payouts.
