from pathlib import Path

from fastapi import Request
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
