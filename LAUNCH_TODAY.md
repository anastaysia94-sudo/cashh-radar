# Cashh Radar — Launch Today

This is the shortest practical path from the ZIP/repository to a public Cashh Radar website **today**.

## What you need from your own accounts

You need only two things to get the core product public:

1. a GitHub repository; and
2. a Render account connected to GitHub.

Stripe, SMTP and a custom domain can be added after the first public launch. Do not delay the first launch for them unless paid checkout/email verification are mandatory for your day-one plan.

---

## Step 1 — Create the GitHub repository

In GitHub, create an **empty** repository under `anastaysia94-sudo` named:

`cashh-radar`

Recommended:

- Visibility: **Private** while you are setting it up; public is also technically fine if you want open source.
- Do not add a README, `.gitignore`, or license during creation because this project already contains them.
- Never upload a real `.env` file or secret/API key.

The connected ChatGPT GitHub tool can populate an existing repository, but it cannot create the repository itself. Once that one empty repo exists, the project files can be pushed into it.

---

## Step 2 — Put the launch build in the repo

Use the contents of `CASHH_RADAR_LAUNCH_V2_2_2026-09-03.zip` as the **repository root**.

The repo root should visibly contain at least:

- `app.py`
- `Dockerfile`
- `requirements.txt`
- `render.yaml`
- `static/`
- `scripts/`
- `tests/`
- `docs/`

Do **not** upload `.env` or any real production database.

---

## Step 3 — Connect GitHub to Render

In Render:

1. Connect/authorize your GitHub account.
2. Click **New → Blueprint**.
3. Select the `cashh-radar` repo.
4. Render will read the root `render.yaml`.
5. Review the proposed `cashh-radar` web service. The included Blueprint uses Render's current `0.5c-512mb` compute plan ID plus a 1 GB persistent disk; check Render's dashboard for the current price before approving the Blueprint.

The Blueprint includes a persistent `/app/data` disk so accounts and other saved data survive redeploys.

---

## Step 4 — Enter the three human values Render asks for

When the Blueprint asks for values, set:

### `CASHH_ADMIN_EMAIL`
Your private owner login email.

### `CASHH_ADMIN_PASSWORD`
A unique password, at least 12 characters; use substantially longer if practical.

### `CASHH_SUPPORT_EMAIL`
The address users should see on Privacy, Terms, Security and Support pages.

Do **not** send these secrets to ChatGPT. Enter them directly in Render.

The Blueprint generates the application secret and metrics token automatically.

---

## Step 5 — Deploy

Click **Deploy Blueprint**.

Render builds the Docker image and starts the FastAPI application. The app automatically reads Render's `RENDER_EXTERNAL_URL`, so you do not need to know your final `onrender.com` hostname before the first deployment.

Wait until Render reports the service as live/healthy.

---

## Step 6 — Open these URLs

Replace `YOUR-RENDER-URL` with the URL Render gives you.

Open:

- `https://YOUR-RENDER-URL/`
- `https://YOUR-RENDER-URL/api/health/live`
- `https://YOUR-RENDER-URL/api/health/ready`
- `https://YOUR-RENDER-URL/privacy`
- `https://YOUR-RENDER-URL/terms`
- `https://YOUR-RENDER-URL/disclosures`
- `https://YOUR-RENDER-URL/security`
- `https://YOUR-RENDER-URL/support`

`/api/health/ready` should say `ready`.

---

## Step 7 — Sign in as owner

On the Cashh Radar website:

1. click **Sign in**;
2. use the `CASHH_ADMIN_EMAIL` you entered in Render;
3. use the `CASHH_ADMIN_PASSWORD` you entered in Render;
4. confirm the Admin item appears.

After the account exists on the persistent disk, you may remove the bootstrap password environment variable later if desired. Do not remove it before confirming you can sign in.

---

## Step 8 — Confirm live opportunity data

The launch Blueprint enables:

`CASHH_SCHEDULED_SOURCES=grants_gov`

The in-process scheduler begins the first Grants.gov refresh shortly after startup and repeats it on the configured interval.

As owner, you can also open Admin and manually run/refresh supported sources.

Do not enable USAJOBS until you have its API key/email. Do not add Lever sites until you have selected specific employer site tokens and confirmed their use is appropriate.

---

# At this point Cashh Radar is PUBLIC

You can stop here and launch the **free/core version today**.

The next sections activate email, payments and a custom domain. They do not have to block the first launch.

---

# Optional same-day activation A — Email

Email powers:

- password reset emails;
- email verification;
- optional two-step login;
- Team invitations;
- opportunity digests.

Choose any SMTP provider you control and add these in Render → Environment:

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASSWORD`
- `SMTP_FROM`
- `SMTP_TLS=1`

Redeploy, then test password reset with an address you control.

Only after email is confirmed working, set:

`CASHH_REQUIRE_EMAIL_VERIFICATION=1`

Then redeploy again.

---

# Optional same-day activation B — Stripe paid plans

The built-in plan catalog currently uses:

- Free: $0
- Pro: $19/month
- Team: $49/month

In Stripe:

1. Create a recurring monthly Pro price.
2. Create a recurring monthly Team price.
3. Copy the two Price IDs.
4. Add these in Render:
   - `STRIPE_SECRET_KEY`
   - `STRIPE_PRICE_PRO`
   - `STRIPE_PRICE_TEAM`
5. In Stripe Workbench/Webhooks, create a webhook endpoint:
   - `https://YOUR-PUBLIC-URL/api/billing/webhook`
6. Subscribe it to at least:
   - `checkout.session.completed`
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `customer.subscription.paused`
   - `customer.subscription.resumed`
7. Reveal the webhook signing secret and save it in Render as:
   - `STRIPE_WEBHOOK_SECRET`
8. Enable/configure the Stripe Customer Portal so subscribers can manage/cancel billing.
9. Redeploy.
10. Make one real/test-mode purchase using Stripe's appropriate test workflow before switching to live mode.

Cashh Radar verifies Stripe webhook signatures and updates plan entitlements when subscription status changes.

Never paste Stripe secret keys or webhook secrets into chat.

---

# Optional same-day activation C — Custom domain

You do **not** need a domain to launch. The Render HTTPS address is already public.

When your domain is ready:

1. Render service → **Settings → Custom Domains → Add Custom Domain**.
2. Add the DNS records Render tells you to add at your registrar/DNS provider.
3. Verify the domain in Render.
4. Add this environment variable in Render:
   - `CASHH_PUBLIC_URL=https://yourdomain.com`
5. Redeploy.
6. Update the Stripe webhook endpoint to the custom-domain URL if you want Stripe to use the branded domain.

Render manages and renews HTTPS certificates for the custom domain.

---

# Step 9 — Final owner checks before announcing it

Use a private/incognito browser window and act like a stranger:

1. Open the homepage.
2. Create a normal Free account.
3. Set preferences.
4. Save five opportunities; verify the sixth Free save is blocked.
5. Create a saved search.
6. Create an alert.
7. Create an Income Roadmap.
8. Create an Outreach draft.
9. Export account data.
10. Check Privacy/Terms/Disclosures/Support.
11. If SMTP is active, test reset + verification email.
12. If Stripe is active, test checkout and the billing-management portal.
13. Sign back into owner Admin and check source/job health.

Do not announce paid plans until checkout, webhook entitlement, cancellation and return-to-Free behavior have all been verified on the actual deployed environment.

---

# Step 10 — Announce launch

Once the checks above pass, Cashh Radar can be announced publicly.

A technically honest launch description is:

> Cashh Radar discovers, verifies, scores and helps you act on opportunity information. It labels evidence and freshness, personalizes matches, and provides tools to organize next steps. Availability and earnings are never guaranteed.

Avoid advertising guaranteed income, guaranteed grants, guaranteed jobs, or guaranteed results.

---

# What “100% launch-ready” means here

The application software, deployment configuration, user/security flows, launch policies, source system, scheduler, backups, Team/API layers and paid-plan lifecycle code are packaged. The remaining manual actions are ownership/account actions that source code cannot legitimately perform for you: creating the GitHub repo, authorizing Render, entering your private credentials, connecting DNS, and activating external providers.
