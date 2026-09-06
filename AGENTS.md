# Cashh Radar — AI Agent Rules

All AI/coding agents must read `AI_CONTINUATION_GUIDE.md` before making project changes.

Platform-specific handoffs are in `prompts/`:

- `CHATGPT_CONTINUATION_PROMPT.md`
- `COPILOT_CONTINUATION_PROMPT.md`
- `GROK_CONTINUATION_PROMPT.md`
- `PERPLEXITY_CONTINUATION_PROMPT.md`

GitHub Copilot also has repository-native instructions at `.github/copilot-instructions.md`.

## Universal rules

- Repository: `anastaysia94-sudo/cashh-radar`
- Preserve Cashh Radar as a separate product/codebase from EGM4000, F.S.A., Founder Console and other SmartPickShop projects unless the owner explicitly requests an integration.
- Never fabricate opportunities, sources, customers, users, payments, revenue, testimonials, outcomes, deployment status, integrations or test results.
- Never guarantee income, jobs, grants or approval.
- Never commit `.env`, API keys, passwords, tokens, production databases, WAL files or other secrets.
- Preserve evidence/provenance/freshness labels and ranking integrity.
- Add regression tests for meaningful changes.
- Run `python -m pytest -q`, `python -m py_compile app.py`, `node --check static/app.js`, and `node --check static/sw.js` before declaring a build complete.
- Run `python scripts/preflight.py` for deployment changes.
- Update README/status/changelog/deployment docs when behavior changes.
- If GitHub write access exists, commit/push only after validation and verify the resulting remote commit/ref.
- If GitHub write access does not exist, produce a patch or complete changed files and clearly state that GitHub was not modified.
- Never claim a deployment is live until its real public URL and health/readiness endpoints are verified.
- Current owner direction: focus on software development and launch; do not generate additional graphics unless explicitly requested.
