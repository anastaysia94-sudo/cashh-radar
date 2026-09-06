"""Vercel serverless entrypoint for the full Cashh Radar FastAPI app.

This is not the removed Cashh Radar Lite/static front door. It imports the real
FastAPI application from app.py and uses Vercel-safe runtime defaults.

Important: local SQLite on Vercel is temporary. For durable accounts/watchlists,
connect a real Postgres database such as Supabase and update the app data layer.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Vercel functions do not provide a persistent app-local disk. These defaults
# keep the full backend importable/runnable by storing SQLite temp data in /tmp.
os.environ.setdefault("CASHH_DB_PATH", "/tmp/cashh_radar.db")
os.environ.setdefault("CASHH_BACKUP_DIR", "/tmp/cashh_radar_backups")
os.environ.setdefault("CASHH_SCHEDULER_ENABLED", "0")
os.environ.setdefault("CASHH_COOKIE_SECURE", "1")
os.environ.setdefault("CASHH_DEV_MODE", "0")
os.environ.setdefault("CASHH_REQUIRE_EMAIL_VERIFICATION", "0")

vercel_url = os.environ.get("VERCEL_URL")
if vercel_url and not os.environ.get("CASHH_PUBLIC_URL"):
    os.environ["CASHH_PUBLIC_URL"] = f"https://{vercel_url.lstrip('https://').lstrip('http://')}"

from app import app  # noqa: E402,F401
