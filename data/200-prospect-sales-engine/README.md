# 200-PROSPECT SALES ENGINE — Live CRM

Canonical workbook:

`200_PROSPECT_SALES_ENGINE_LIVE_CRM_MASTER.xlsx`

Android/mobile web app:

`webapp/index.html`

## Purpose

This workbook is the live source of truth for prospecting, initial outreach, follow-ups, replies, qualification, objections, closing, payment, delivery, upsells, referrals, and re-engagement. The `webapp/` folder provides the faster Android operating interface.

## Android web app

The mobile app is designed around one-tap operation:

- Add or tap a **verified prospect email address**.
- **Email ready** opens a pre-addressed email with subject and outreach body already populated.
- **Gmail draft + image** creates a Gmail draft containing recipient, subject, body, and a generated prospect-specific PNG attachment after one-time Gmail OAuth configuration.
- **Share + image** uses Android's share sheet as a fallback.
- Initial, Follow-up 1, Follow-up 2, qualification, and close messages can be switched from the prospect card.
- Status edits and email edits are kept locally on the Android device.
- The app is installable as a PWA over HTTPS.

A normal browser `mailto:` link cannot reliably attach a local image file, so true automatic attachments use the Gmail API with the narrow `gmail.compose` permission and create a **draft for review**, not an automatic send.

Most current Reddit/Craigslist rows do not contain a verified public email address. Those fields remain blank rather than being fabricated; use the listed source/DM/application route or add a verified email when one becomes available.

## Update rules

1. Re-check the highest-priority rows before treating them as live.
2. Never invent prospects, email addresses, replies, customers, payments, revenue, or outcomes.
3. Keep the exact source URL for researched leads.
4. Replace dead/stale discovery slots with newly verified prospects.
5. Preserve all actual outreach history and status changes.
6. Use the workbook's `Contact Scripts - Full` and `Contact Cadence` sheets for continued contact.
7. Stop repeated outreach after the defined sequence unless the prospect replies.
8. Do not contact prospects who asked not to be contacted.
9. Do not pay fees, deposits, gift cards, crypto, or provide account credentials to receive work.
10. When refreshing the workbook, replace the canonical XLSX at this same repository path rather than creating disconnected copies.
11. Refresh `webapp/prospects.js` from the newly verified CRM rows when lead data changes.

## Contact lifecycle

`INIT-01 → FU-01 → FU-02 → REENGAGE-30 (only when appropriate)`

If the prospect replies:

`REPLY-QUALIFY / objection handling → CLOSE-01 → PAY-01 → DELIVER-01 → CHECKIN-01 → UPSELL-01 / REFERRAL-01`

## Workbook sections

- Dashboard
- Current Leads
- Original Top 10
- Outreach Scripts
- Sources
- TODAY - START HERE
- 200 Outreach Queue
- Templates - 200 Day
- Follow-up Queue
- Contact Scripts - Full
- Contact Cadence
- AI Update Instructions
- Android Web App (in the Android-ready workbook refresh)

Last structural refresh: 2026-09-05.
