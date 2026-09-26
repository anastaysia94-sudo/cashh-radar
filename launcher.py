from datetime import datetime, timezone
import os
from pathlib import Path

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

import app as core
from app import app as core_app
from cashh_loop import register_cashh_loop
from cashh_loop_ui import register_cashh_loop_ui
from cashh_prospect_bridge import register_prospect_bridge, start_prospect_bridge_scheduler
from cashh_performance_radar import register_performance_radar
from prospect_performance import summarize as summarize_prospect_performance

BASE_DIR = Path(__file__).resolve().parent
PROSPECT_APP_DIR = BASE_DIR / "prospect-android-app"

# Cashh Radar has one canonical opportunity lifecycle. Register the orchestration
# layer, the prospect bridge, performance-aware ranking, and the connected UI before exposing production.
register_cashh_loop(core_app)
register_prospect_bridge(core_app)
register_performance_radar(core_app)
register_cashh_loop_ui(core_app)
start_prospect_bridge_scheduler(core)


def _public_launch_status() -> dict:
    """Return a privacy-safe launch snapshot for operators and uptime checks."""
    railway_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN") or "cashh-radar-web-production.up.railway.app"
    public_url = os.getenv("CASHH_PUBLIC_URL") or f"https://{railway_domain}"
    commit = os.getenv("RAILWAY_GIT_COMMIT_SHA") or os.getenv("GIT_COMMIT_SHA") or "unknown"
    service_name = os.getenv("RAILWAY_SERVICE_NAME") or "cashh-radar-web"
    project_name = os.getenv("RAILWAY_PROJECT_NAME") or "cashh-radar"

    return {
        "product": "Cashh Radar",
        "status": "live",
        "hosting": "Railway",
        "project": project_name,
        "service": service_name,
        "public_url": public_url.rstrip("/"),
        "healthcheck": "/api/health/ready",
        "prospect_entrypoint": "/prospects/",
        "protected_endpoints": [
            "/api/prospects/performance",
            "/api/radar/performance-aware",
            "/api/radar/unified",
        ],
        "datastore_boundary": "single-replica SQLite on Railway persistent storage until PostgreSQL migration",
        "privacy": "No user, billing, API-key, session, or prospect-private data is exposed by this endpoint.",
        "commit": commit[:12] if commit != "unknown" else commit,
        "checked_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }


@core_app.get("/api/launch/status")
def launch_status():
    return _public_launch_status()


@core_app.get("/launch-status", response_class=HTMLResponse)
def launch_status_page():
    status = _public_launch_status()
    return f"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Cashh Radar Launch Status</title>
  <style>
    :root {{ color-scheme: dark; font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }}
    body {{ margin: 0; min-height: 100vh; background: #0b1020; color: #f8f7f9; display: grid; place-items: center; padding: 24px; }}
    main {{ max-width: 860px; width: 100%; background: #151a26; border: 1px solid #27303b; border-radius: 28px; padding: 28px; box-shadow: 0 24px 80px rgba(0,0,0,.35); }}
    h1 {{ margin: 0 0 8px; font-size: clamp(2rem, 5vw, 4rem); }}
    .pill {{ display: inline-flex; gap: 8px; align-items: center; padding: 8px 12px; border-radius: 999px; background: rgba(34,212,99,.12); color: #7cf2e3; border: 1px solid rgba(124,242,227,.35); font-weight: 700; }}
    dl {{ display: grid; grid-template-columns: minmax(140px, .6fr) 1.4fr; gap: 12px 18px; margin-top: 24px; }}
    dt {{ color: #a6acb9; }}
    dd {{ margin: 0; word-break: break-word; }}
    a {{ color: #00e5c2; }}
    .note {{ margin-top: 24px; color: #a6acb9; line-height: 1.55; }}
  </style>
</head>
<body>
  <main>
    <span class="pill">● Live on {status['hosting']}</span>
    <h1>Cashh Radar launch status</h1>
    <p class="note">Public-safe production status. No private account data, prospects, billing data, sessions, or API keys are exposed here.</p>
    <dl>
      <dt>Public app</dt><dd><a href="{status['public_url']}/">{status['public_url']}/</a></dd>
      <dt>Prospect PWA</dt><dd><a href="{status['public_url']}{status['prospect_entrypoint']}">{status['prospect_entrypoint']}</a></dd>
      <dt>Healthcheck</dt><dd>{status['healthcheck']}</dd>
      <dt>Service</dt><dd>{status['project']} / {status['service']}</dd>
      <dt>Commit</dt><dd>{status['commit']}</dd>
      <dt>Status checked</dt><dd>{status['checked_at']}</dd>
      <dt>Storage boundary</dt><dd>{status['datastore_boundary']}</dd>
    </dl>
  </main>
</body>
</html>
"""


@core_app.get("/api/prospects/performance")
def prospect_performance(request: Request):
    """Return actual prospect performance from this signed-in user's persisted state."""
    user = core.require_user(request)
    with core.db() as conn:
        return summarize_prospect_performance(conn, user["id"])


if PROSPECT_APP_DIR.exists():
    core_app.mount(
        "/prospects",
        StaticFiles(directory=str(PROSPECT_APP_DIR), html=True),
        name="prospect-android-app",
    )

app = core_app

# Deployment marker: 2026-09-25 production refresh requested from current main.
