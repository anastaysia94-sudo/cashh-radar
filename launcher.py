from pathlib import Path

from fastapi.staticfiles import StaticFiles

from app import app as core_app

BASE_DIR = Path(__file__).resolve().parent
PROSPECT_APP_DIR = BASE_DIR / "prospect-android-app"

if PROSPECT_APP_DIR.exists():
    core_app.mount(
        "/prospects",
        StaticFiles(directory=str(PROSPECT_APP_DIR), html=True),
        name="prospect-android-app",
    )

app = core_app
