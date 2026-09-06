# GitHub Upload Instructions — Cashh Radar

Use this when moving the full Cashh Radar launch package into this repository.

## Repository

`https://github.com/anastaysia94-sudo/cashh-radar`

## Safe local upload path

1. Download the latest launch ZIP from ChatGPT.
2. Extract it on your computer.
3. Clone the repo:

```bash
git clone https://github.com/anastaysia94-sudo/cashh-radar.git
cd cashh-radar
```

4. Copy the extracted project files into the cloned folder.
5. Confirm these are **not** copied or staged:

```text
.env
.venv/
__pycache__/
.pytest_cache/
*.pyc
data/*.db
data/*.db-wal
data/*.db-shm
data/backups/
*.log
```

6. Check what will be uploaded:

```bash
git status
```

7. Commit and push:

```bash
git add .
git commit -m "Publish Cashh Radar launch build"
git push origin main
```

## GitHub web upload path

1. Open the repository in your browser.
2. Click **Add file → Upload files**.
3. Drag the extracted project contents into GitHub.
4. Do not upload `.env`, `.venv`, database files, logs or cache folders.
5. Commit to `main` for first launch upload.

## After upload

Verify these important files exist:

```text
app.py
requirements.txt
Dockerfile
render.yaml
.env.example
static/index.html
static/app.js
static/sw.js
tests/test_app.py
scripts/preflight.py
LAUNCH_TODAY.md
DEPLOYMENT.md
PRODUCTION_ENV.md
README.md
```

Then connect the repo to Render using the included `render.yaml`.

## Rule

Never put real passwords, API keys, Stripe keys, SMTP passwords, webhook secrets or production `.env` files into GitHub. Enter those directly in Render or the chosen host dashboard.
