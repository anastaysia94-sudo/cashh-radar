# Cashh Radar — Render Deployment Status

Cashh Radar is a full FastAPI backend application intended to launch on Render from this repository.

## Current source status

- Repository: `anastaysia94-sudo/cashh-radar`
- Main app entrypoint: `app.py`
- Runtime: Python / FastAPI / Uvicorn
- Intended host: Render web service
- Static Lite/Vercel preview: removed from this repository
- Cross-project prospecting files: removed from this repository

## Render launch status

The Render workspace is connected in ChatGPT:

- Workspace: `SmartPickShop`
- Workspace ID: `tea-daef1tgn74is73dim7c0`

Render service creation has been attempted from this repo, but Render returned a billing requirement before it would create the public backend service.

## Required owner action

Add billing/payment information directly inside Render. Do not paste card details, secrets, or passwords into ChatGPT.

After billing is added, retry creating the Render web service with:

- Repository: `https://github.com/anastaysia94-sudo/cashh-radar.git`
- Branch: `main`
- Runtime: `python`
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn app:app --host 0.0.0.0 --port $PORT --proxy-headers`
- Auto deploy: `yes`

Minimum environment variables before public launch:

```env
CASHH_COOKIE_SECURE=1
CASHH_DEV_MODE=0
CASHH_REQUIRE_EMAIL_VERIFICATION=0
CASHH_ADMIN_EMAIL=<owner email>
CASHH_ADMIN_PASSWORD=<set directly in Render>
CASHH_SUPPORT_EMAIL=<support email>
CASHH_SECRET_KEY=<long random secret set directly in Render>
```

Optional production variables can be added later for Stripe, SMTP email verification, source API keys, custom metrics token, and scheduled jobs.

## Important continuation rule

Do not redeploy or continue Cashh Radar as a Vercel Lite/static-only app unless the owner explicitly reverses that decision. The current target is the full Render-backed product.
