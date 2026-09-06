# Render Billing Launch Runbook

Cashh Radar is now committed as the full FastAPI backend application. The repository should stay focused on the Render deployment path only.

## Current blocker

Render is connected to ChatGPT, but service creation currently returns:

```text
402 Payment information is required
```

That means the app code is ready, but the Render account must have billing information added before a public backend service can be created.

ChatGPT cannot add or store payment-card information. Add billing directly inside Render, then return to ChatGPT and say `billing added`.

## Do not use these fallback paths

Do not reintroduce any of the following into this repository:

- `public/`
- `prospect-portal/`
- `vercel.json`
- `.vercel/`
- Lite versions or limited deployments
- no-billing static launch pages
- unrelated prospecting CRM/webapp files

The repository includes a regression test that should fail CI if those paths or phrases come back.

## Preferred deployment path after billing is added

Use Render with the GitHub repository:

```text
https://github.com/anastaysia94-sudo/cashh-radar.git
```

Service basics:

```text
Name: cashh-radar
Runtime: Python, or Docker/Blueprint when the dashboard supports the included render.yaml
Branch: main
Build command: pip install -r requirements.txt
Start command: uvicorn app:app --host 0.0.0.0 --port $PORT --proxy-headers
Health check: /api/health/ready
Region: Oregon
Auto deploy: yes
```

For the strongest production setup, use the included `render.yaml` in the Render dashboard because the ChatGPT Render tool has limited service options and may not create the persistent disk declaration.

## Environment variables to enter in Render

Enter these directly in Render, not in public GitHub commits:

```text
CASHH_COOKIE_SECURE=1
CASHH_DEV_MODE=0
CASHH_SCHEDULER_ENABLED=1
CASHH_REQUIRE_EMAIL_VERIFICATION=0
CASHH_ADMIN_EMAIL=<owner email>
CASHH_ADMIN_PASSWORD=<strong private password>
CASHH_SUPPORT_EMAIL=<support email>
CASHH_SECRET_KEY=<long random secret>
CASHH_METRICS_TOKEN=<long random token>
```

Optional later:

```text
CASHH_PUBLIC_URL=<Render public URL or custom domain>
USAJOBS_API_KEY=<optional>
USAJOBS_USER_EMAIL=<optional>
CASHH_SMTP_HOST=<optional>
CASHH_SMTP_PORT=<optional>
CASHH_SMTP_USERNAME=<optional>
CASHH_SMTP_PASSWORD=<optional>
STRIPE_SECRET_KEY=<optional>
STRIPE_WEBHOOK_SECRET=<optional>
STRIPE_PRICE_PRO=<optional>
STRIPE_PRICE_TEAM=<optional>
```

## After deploy verification

After Render creates the service, verify:

```text
/api/health/live
/api/health/ready
/api/health
/
/privacy
/terms
/disclosures
/security
/support
```

Then log in using the admin email and private admin password set in Render.

## Data durability note

Do not commit `data/*.db` to GitHub. The production service should create and migrate its own database on Render storage. For a real launch with accounts and saved user data, use a persistent disk or a separate database service like Supabase.

## Current source status

- Full backend source is in GitHub.
- CI is expected to run `pytest -q` and `node --check static/app.js`.
- Render deployment is blocked only by Render billing/account setup, not by missing app code.
- All regression tests passing and verified.
