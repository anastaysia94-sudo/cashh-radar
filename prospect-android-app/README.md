# 200 Prospect Sales Engine — Android Web App

Mobile-first operator for the canonical 200-prospect CRM.

## Current Android flow (v3)

The default experience is **Next-Best-Action Mode**. You work one prospect at a time instead of managing a giant spreadsheet on your phone.

The app automatically prioritizes:

1. Prospects who **replied**.
2. Previously contacted prospects whose **follow-up is due**.
3. The next high-priority new prospect.

For the current prospect, the large action box tells you exactly what to do next:

1. **Verify** — open the real source and confirm the opportunity is still active.
2. **Contact** — use a verified email when one exists; otherwise copy the prepared message and open the listing/DM/application route.
3. **Draft** — the correct initial, Follow-up 1, Follow-up 2, qualification, or closing message is selected automatically.
4. **Confirm** — after you actually send it, tap **I sent it — next best action**. The next prospect loads automatically.

A first-run guide explains this flow, and Android clipboard support can paste a copied email address into the current prospect with one tap.

## Follow-up automation inside the app

The app does not silently send messages. Instead it schedules the workflow locally:

- Follow-up 1: **2 business days** after the initial contact.
- Follow-up 2: **5 business days** after Follow-up 1.
- Replies are surfaced ahead of follow-ups.
- Follow-ups are surfaced ahead of new outreach.

Only contacts that the user actually marks as Sent enter the follow-up queue.

## Email and attachment flow

### Email ready

When a verified prospect email address is present, the app can open the Android mail composer with:

- To
- Subject
- Prospect-specific message

already populated.

### Gmail draft + image

With optional Gmail OAuth configured, the app creates a Gmail **draft for review** containing:

- Recipient
- Subject
- Message body
- Prospect-specific PNG outreach card generated from CRM fields

The app never automatically presses Send.

### Source / DM prospects

Many Reddit and Craigslist opportunities do not publish a public email address. The app intentionally does not invent one. For those rows, the primary workflow copies the prepared message and opens the real listing/contact route.

## One-time Gmail setup

1. Enable **Gmail API** in Google Cloud.
2. Configure the OAuth consent screen.
3. Create an OAuth 2.0 Web Client ID.
4. Add the hosted HTTPS app origin as an Authorized JavaScript origin.
5. Open the app → Settings → paste the Client ID.
6. Approve the `https://www.googleapis.com/auth/gmail.compose` permission when first creating a Gmail draft.

The Client ID and local CRM progress are stored on the Android device. No Gmail password is stored.

## Install on Android

The app is an installable PWA. Open the hosted HTTPS version in Chrome and choose **Install app / Add to Home screen**. The service worker caches the focus flow for offline use.

## GitHub Pages deployment

The repository includes `.github/workflows/prospect-android-pages.yml`.

Repository-level GitHub Pages still has to be enabled once by an account owner because the connected GitHub integration does not have administration permission to create the Pages site.

1. Open the `cashh-radar` repository.
2. Go to **Settings → Pages**.
3. Under **Build and deployment**, set **Source** to **GitHub Actions**.
4. Re-run **Deploy Prospect Android Web App to Pages** from Actions.

After Pages is enabled, later changes under `data/200-prospect-sales-engine/webapp/**` deploy automatically.

## Canonical data

The XLSX at `data/200-prospect-sales-engine/200_PROSPECT_SALES_ENGINE_LIVE_CRM_MASTER.xlsx` remains the canonical CRM. `prospects.js` is the web-app seed snapshot.

Future refreshes should preserve real outreach state and must never invent:

- prospects
- email addresses
- replies
- payments
- customers
- testimonials
- outcomes

## Safety / quality rules

- Verify a listing before contacting it.
- Personalize at least one true detail.
- Respect the platform's allowed contact method.
- Do not mass-send identical messages.
- Do not fabricate experience or portfolio results.
- Do not send sensitive identity or banking information to unverified contacts.
- Stop on requests for upfront fees, gift cards, crypto deposits, banking logins, or suspicious credential requests.
