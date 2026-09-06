# 200 Prospect Sales Engine — Android Easy Flow

The Android web app now defaults to **Focus mode: one prospect at a time**.

## New operating flow

1. **Verify the lead** — open the actual source and mark it verified if it is still active.
2. **Add the contact** — paste a verified email when one is publicly provided. If the prospect uses Reddit/Craigslist/application forms instead, tap **Copy message + open listing / DM**.
3. **Use the prepared message** — Initial, Follow-up 1, Follow-up 2, Qualify reply, and Close are one-tap message modes. Subject/body are already populated and can be edited.
4. **Prepare the email** — if Gmail OAuth is configured, the main button creates a Gmail draft with recipient, subject, message, and a prospect-specific PNG attached. Otherwise Android opens the mail app with To + Subject + Body filled in.
5. **Confirm the real send** — tap **I sent it — next prospect** only after you actually send it. The app then advances automatically.
6. **Follow-ups** — the Follow-ups tab surfaces prospects actually marked Sent after the follow-up window is due.

## Bottom navigation

- **Focus** — one prospect at a time; this is the default.
- **Queue** — search/filter all 200 slots and jump to any prospect.
- **Follow-ups** — only real sent contacts whose follow-up is due.
- **Progress** — processed, sent, replies, wins, skipped, and remaining.

## Android-specific improvements

- Large tap targets and a single primary action per step.
- The app automatically moves to the next workable prospect after a confirmed send or skip.
- Progress is saved locally on the Android device using the same `ps200-mobile-v1` state key, so the redesign keeps prior local progress.
- The service worker caches the easy-flow shell for offline reopening.
- The PWA manifest launches directly into `easy.html`.

## Email + image behavior

A normal `mailto:` URL can prefill recipient, subject, and body, but browsers cannot reliably pre-attach a local file. Therefore automatic attachments use the Gmail API and create a **draft for review**, not an automatic send.

### One-time Gmail setup

1. Enable **Gmail API** in Google Cloud.
2. Configure the OAuth consent screen.
3. Create an OAuth 2.0 Client ID for a Web application.
4. Add the deployed app's HTTPS origin as an Authorized JavaScript origin.
5. Open the app → ⚙ Settings → paste the Client ID.
6. Approve the `https://www.googleapis.com/auth/gmail.compose` scope when prompted.

The app does not store a Gmail password and does not silently mass-send messages.

## Prospect emails

Most current Reddit/Craigslist leads do not publish verified email addresses. The app intentionally leaves those addresses blank instead of inventing them. When a verified email becomes available, enter it once and the Android device remembers it locally.

## Install on Android

Open the hosted HTTPS app in Chrome, then use **Install app** / **Add to Home screen**. The app also exposes an Install button from ⚙ Settings when Chrome makes the PWA install prompt available.

## Safety / quality rules

- Verify the listing before contact.
- Personalize at least one true detail before sending.
- Do not fabricate email addresses, experience, results, clients, replies, payments, or outcomes.
- Do not silently auto-send. Review the draft and press Send yourself.
- Stop on upfront fees, gift cards, crypto deposits, banking logins, suspicious credentials, or requests that violate the platform's contact rules.
