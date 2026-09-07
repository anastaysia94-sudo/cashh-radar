from pathlib import Path

from fastapi.staticfiles import StaticFiles

from app import app as core_app
from cashh_loop import register_cashh_loop
from cashh_loop_ui import register_cashh_loop_ui

BASE_DIR = Path(__file__).resolve().parent
PROSPECT_APP_DIR = BASE_DIR / "prospect-android-app"

# Cashh Radar has one canonical opportunity lifecycle. Register the orchestration
# layer and its connected UI before exposing the same app through production.
register_cashh_loop(core_app)
register_cashh_loop_ui(core_app)

if PROSPECT_APP_DIR.exists():
    core_app.mount(
        "/prospects",
        StaticFiles(directory=str(PROSPECT_APP_DIR), html=True),
        name="prospect-android-app",
    )

app = core_app
