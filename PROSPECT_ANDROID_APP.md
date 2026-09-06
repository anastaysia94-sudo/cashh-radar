# 200 Prospect Android App

The Android-first 200 Prospect Sales Engine now lives in a stable top-level folder on `main` so the normal GitHub link is simple and does not depend on an old nested path.

## Open the app source

https://github.com/anastaysia94-sudo/cashh-radar/tree/main/prospect-android-app

## Direct app entry file

https://github.com/anastaysia94-sudo/cashh-radar/blob/main/prospect-android-app/index.html

## Live route after deployment

Container/Railway deployments now start through `launcher.py`, which mounts this PWA at:

`/prospects/`

So if your Cashh Radar production URL is `https://YOUR-DOMAIN`, the Android prospect app is available at:

`https://YOUR-DOMAIN/prospects/`

## Dedicated backup branch

https://github.com/anastaysia94-sudo/cashh-radar/tree/prospect-android-app/prospect-android-app

The folder includes the Android/PWA source, prospect seed data, Focus / Queue / Follow-ups / Progress flow, initial and follow-up scripts, prefilled email drafting, PNG outreach-card generation, optional Gmail draft + attachment support, offline service worker files, and a copy of the canonical CRM workbook.

CI now checks that the complete Android bundle still exists, that its JavaScript parses, and that Docker/Railway start through the launcher that exposes `/prospects/`.
