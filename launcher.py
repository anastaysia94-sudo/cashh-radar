from pathlib import Path

from fastapi.staticfiles import StaticFiles

from app import app

BASE_DIR = Path(__file__).resolve().parent
PROSPECT_WEBAPP_DIR = BASE_DIR / "data" / "200-prospect-sales-engine" / "webapp"

# Serve the Android-first 200 Prospect Sales Engine from the same production
# service as Cashh Radar. This avoids depending on GitHub Pages being enabled.
if PROSPECT_WEBAPP_DIR.exists():
    app.mount(
        "/prospects",
        StaticFiles(directory=str(PROSPECT_WEBAPP_DIR), html=True),
        name="prospect_android_webapp",
    )
