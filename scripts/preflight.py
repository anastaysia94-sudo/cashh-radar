#!/usr/bin/env python3
"""Cashh Radar production-readiness checks that do not call external providers."""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DB=Path(os.getenv("CASHH_DB_PATH",ROOT/"data"/"cashh_radar.db"))
DEV=os.getenv("CASHH_DEV_MODE","1")=="1"
checks=[]

def add(name,ok,detail,required=True):
    checks.append({"name":name,"ok":bool(ok),"required":required,"detail":detail})

secret=os.getenv("CASHH_SECRET_KEY","")
add("production secret",DEV or (len(secret)>=32 and secret not in {"cashh-radar-dev-change-me","replace-with-at-least-32-random-characters"}),"configured" if secret else "missing")
add("secure cookies",DEV or os.getenv("CASHH_COOKIE_SECURE")=="1",f"CASHH_COOKIE_SECURE={os.getenv('CASHH_COOKIE_SECURE','')}")
url=(os.getenv("CASHH_PUBLIC_URL") or os.getenv("RENDER_EXTERNAL_URL") or "").strip().rstrip("/")
url_ok=url.startswith("https://") and ".example" not in url and "your-real-domain" not in url
add("canonical HTTPS URL",DEV or url_ok,url or "missing")
admin_email=os.getenv("CASHH_ADMIN_EMAIL","").strip()
admin_password=os.getenv("CASHH_ADMIN_PASSWORD","")
add("initial owner email",DEV or ("@" in admin_email and not admin_email.endswith("@example.com")),admin_email or "missing")
add("initial owner password",DEV or len(admin_password)>=12,"configured" if admin_password else "missing")
support=os.getenv("CASHH_SUPPORT_EMAIL","").strip()
add("support email",DEV or ("@" in support and not support.endswith("@example.com")),support or "missing")
try:
    DB.parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(DB) as conn:
        conn.execute("SELECT 1")
        row=conn.execute("SELECT COALESCE(MAX(version),0) FROM schema_migrations").fetchone()
        version=int(row[0] or 0)
        integrity=conn.execute("PRAGMA quick_check").fetchone()[0]
    add("database",integrity=="ok",f"{DB} quick_check={integrity}")
    add("schema v4",version>=4,f"schema={version}")
except Exception as exc:
    add("database",False,str(exc)); add("schema v4",False,"unavailable")
backup_dir=Path(os.getenv("CASHH_BACKUP_DIR",str(DB.parent/"backups")))
try:
    backup_dir.mkdir(parents=True,exist_ok=True)
    probe=backup_dir/".write-test";probe.write_text("ok");probe.unlink()
    add("backup directory",True,str(backup_dir))
except Exception as exc:
    add("backup directory",False,str(exc))
scheduler=os.getenv("CASHH_SCHEDULER_ENABLED","0")=="1"
add("automated scheduler",scheduler,"recommended for single-instance launch",required=False)
verification=os.getenv("CASHH_REQUIRE_EMAIL_VERIFICATION","0")=="1"
smtp=bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_FROM"))
add("SMTP",smtp,"required only when email verification is enforced",required=verification and not DEV)
stripe=bool(os.getenv("STRIPE_SECRET_KEY") and os.getenv("STRIPE_WEBHOOK_SECRET") and os.getenv("STRIPE_PRICE_PRO") and os.getenv("STRIPE_PRICE_TEAM"))
add("Stripe billing",stripe,"optional until paid plans are activated",required=False)
add("metrics token",DEV or bool(os.getenv("CASHH_METRICS_TOKEN")),"recommended before exposing operations metrics",required=False)

failed=[c for c in checks if c["required"] and not c["ok"]]
print(json.dumps({"ready":not failed,"checks":checks},indent=2))
raise SystemExit(1 if failed else 0)
