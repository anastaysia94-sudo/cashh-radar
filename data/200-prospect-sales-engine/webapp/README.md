# 200 Prospect Sales Engine — Android Web App

Mobile-first operator for the canonical 200-prospect CRM.

## What it does

- Shows the highest-priority researched prospects first, then discovery slots up to 200.
- Stores operator edits and progress locally on the Android device.
- Lets you add a verified prospect email address without inventing one.
- **Email ready:** opens the phone's mail app with To, Subject, and message already filled in.
- **Gmail draft + image:** generates a prospect-specific PNG card and creates a Gmail draft with recipient, subject, message, and PNG attached.
- **Share + image:** uses Android's share sheet with the generated image when supported.
- Includes initial contact, Follow-up 1, Follow-up 2, qualification, and close/confirmation messages.
- Tracks Sent, Replied, Won/Paid, and Skip locally.
- Works as an installable PWA and caches the app shell for offline use.

## Important attachment limitation

A normal `mailto:` URL can reliably prefill recipient, subject, and body, but browsers cannot reliably pre-attach a local file to the email composer. Therefore automatic attachments use the Gmail API and deliberately create a **draft for review**, not an automatic send.

## One-time Gmail setup

1. Open Google Cloud Console.
2. Create or select a project.
3. Enable **Gmail API**.
4. Configure the OAuth consent screen.
5. Create an **OAuth 2.0 Client ID** for a Web application.
6. Add the HTTPS origin where this web app is hosted as an **Authorized JavaScript origin**.
7. Open the app → Settings → paste the Client ID.
8. Tap **Gmail draft + image** on a prospect and approve the `gmail.compose` permission.

The app asks only for `https://www.googleapis.com/auth/gmail.compose`. The Client ID is stored locally in the browser. No Gmail password is stored.

## Prospect emails

The current CRM does not contain verified email addresses for most Reddit/Craigslist prospects; their allowed contact path is usually DM, reply, or an application form. The app intentionally leaves those email fields empty instead of fabricating addresses. When a verified email becomes available, enter it in the row and the app remembers it locally.

## Data updates

`prospects.js` is the web-app seed snapshot. Keep the XLSX in `data/200-prospect-sales-engine/` as the canonical CRM. On a CRM refresh, regenerate `prospects.js` from the verified rows while preserving real outreach outcomes and never inventing prospects, replies, payments, or email addresses.

## Install on Android

Open the hosted HTTPS app in Chrome, then use **Install app** / **Add to Home screen**. The app also provides an Install button when Chrome exposes the PWA install prompt.

## Safety / outreach quality

- Verify that a listing is still live before contacting it.
- Personalize at least one true detail before sending.
- Do not mass-send identical messages.
- Do not auto-send email; review the draft first.
- Do not fabricate experience, results, clients, pay, email addresses, or outcomes.
- Stop on requests for upfront fees, gift cards, crypto deposits, banking logins, or suspicious credentials.
