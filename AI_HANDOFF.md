# AI Handoff — Cashh Radar

Updated: 2026-09-26 America/Los_Angeles

## Identity

- Canonical repository: `anastaysia94-sudo/cashh-radar`
- Master project IDs: P010, P004, P013
- Portfolio index: `anastaysia94-sudo/anastaysia94-sudo` → `CROSS_LLM_BOOTSTRAP.md`
- Machine-readable register: `portfolio/PROJECTS.json`

## Purpose

Evidence-based opportunity discovery, scoring, outreach, outcomes, and Sales OS.

## Continuity rules

- Sales OS belongs with Cashh Radar, not Founder Dynasty OS.
- Verify opportunity → source → score → outreach draft → recorded outcome end to end.
- Historical chat summaries are context, not proof of the current build.
- Before changing code, inspect README/status docs, open PRs/issues, recent commits, and CI.
- Record what changed, why, verification evidence, blockers, and rollback risk.
- Never commit secrets, API keys, passwords, customer secrets, or private personal information.

## Current source checkpoint

Current observed main head: `84d4cc4273ef9a6e5af2115ad4103212b68cca5d`.

Changes since the prior continuity snapshot:
- `a8c42a0878345be678c4bbbf155cf661702d4cf0` hard-bounded the live production-mobile acceptance job.
- `842d6ad28205c71680dbebe2c386910ca36c1d13` changed the PWA checks to avoid a service-worker activation race.
- `1a7c37ebd973e83715cd8cc8a3ac21d5b249b6a1` applied the SmartPickShop steampunk/neon visual system.
- `84d4cc4273ef9a6e5af2115ad4103212b68cca5d` is a deployment-trigger commit for the branded main branch.

The current production-mobile workflow checks live health/readiness, manifest and service-worker file availability, mobile viewport, horizontal overflow, and emits screenshot + JSON evidence. It does not by itself prove that a service worker became active in the browser.

## Verification boundary

Do not call the current branded production deployment healthy until the newest workflow result and live source/deployment match are checked.

## Smallest next execution block

1. Inspect the latest `Cashh Radar Production Mobile Acceptance` run for current main.
2. Verify the live Railway deployment is serving the branded source corresponding to current main.
3. If green, verify one opportunity → source → score → outreach draft → recorded outcome flow.
4. Record exact run/deployment evidence in STATUS.md before stopping.
