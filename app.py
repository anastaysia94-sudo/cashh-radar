from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import smtplib
import time
import shutil
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional
from email.message import EmailMessage
from contextlib import asynccontextmanager

import requests
from fastapi import FastAPI, HTTPException, Request, Response, Depends, Header, Query
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = Path(os.getenv("CASHH_DB_PATH", str(DATA_DIR / "cashh_radar.db")))
SECRET_KEY = os.getenv("CASHH_SECRET_KEY", "cashh-radar-dev-change-me")
COOKIE_NAME = "cashh_session"
COOKIE_SECURE = os.getenv("CASHH_COOKIE_SECURE", "0") == "1"
PUBLIC_URL = (os.getenv("CASHH_PUBLIC_URL") or os.getenv("RENDER_EXTERNAL_URL") or "http://127.0.0.1:8000").rstrip("/")
SESSION_DAYS = int(os.getenv("CASHH_SESSION_DAYS", "30"))
DEV_MODE = os.getenv("CASHH_DEV_MODE", "1") == "1"
REQUIRE_EMAIL_VERIFICATION = os.getenv("CASHH_REQUIRE_EMAIL_VERIFICATION", "0") == "1"
TEAM_SEAT_LIMIT = int(os.getenv("CASHH_TEAM_SEAT_LIMIT", "10"))
API_PRO_RATE_LIMIT = int(os.getenv("CASHH_API_PRO_RATE_LIMIT_PER_MINUTE", "60"))
API_ORG_RATE_LIMIT = int(os.getenv("CASHH_API_ORG_RATE_LIMIT_PER_MINUTE", "300"))
BACKUP_DIR = Path(os.getenv("CASHH_BACKUP_DIR", str(DATA_DIR / "backups")))
WEBHOOK_TIMEOUT = int(os.getenv("CASHH_WEBHOOK_TIMEOUT", "10"))
SUPPORT_EMAIL = os.getenv("CASHH_SUPPORT_EMAIL", os.getenv("CASHH_ADMIN_EMAIL", "support@example.com")).strip()
SCHEDULER_ENABLED = os.getenv("CASHH_SCHEDULER_ENABLED", "0") == "1"
SCHEDULER_TICK_SECONDS = max(15, int(os.getenv("CASHH_SCHEDULER_TICK_SECONDS", "60")))

@asynccontextmanager
async def lifespan(_: FastAPI):
    start_launch_scheduler()
    yield

app = FastAPI(title="Cashh Radar", version="2.2.0", docs_url="/api/docs" if DEV_MODE else None, redoc_url=None, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ---------- utilities ----------

def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def jdump(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def jload(value: Optional[str], default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def hash_password(password: str, salt: Optional[bytes] = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
    return f"pbkdf2_sha256$310000${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algo, rounds, salt_hex, digest_hex = encoded.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(rounds))
        return hmac.compare_digest(digest.hex(), digest_hex)
    except Exception:
        return False


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def record_hash(payload: dict[str, Any]) -> str:
    tracked = {k: payload.get(k) for k in ["title", "organization", "source_url", "closes_at", "income_min", "income_max", "eligibility", "risks"]}
    return hashlib.sha256(jdump(tracked).encode()).hexdigest()


def opportunity_to_dict(row: sqlite3.Row, user_profile: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    d = dict(row)
    d["tags"] = jload(d.pop("tags_json", None), [])
    d["steps"] = jload(d.pop("steps_json", None), [])
    d["evidence"] = jload(d.pop("evidence_json", None), {})
    d["match"] = personalized_score(d, user_profile or {})
    d["verification"] = verification_state(d)
    return d


def verification_state(o: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    close_dt = parse_dt(o.get("closes_at"))
    last_seen = parse_dt(o.get("last_seen"))
    if o.get("status") == "blocked":
        status = "blocked"
    elif close_dt and close_dt < now:
        status = "expired"
    elif o.get("manual_verified_at"):
        status = "verified"
    elif o.get("trust") == "demo":
        status = "illustrative"
    elif last_seen is None:
        status = "unverified"
    else:
        age_hours = (now - last_seen).total_seconds() / 3600
        threshold = 96 if o.get("source_key") == "grants_gov" else 48
        status = "stale" if age_hours > threshold else "source_confirmed"
    evidence_score = 0
    evidence_score += 25 if (o.get("source_url") or "").startswith("https://") else 0
    evidence_score += 20 if o.get("source_record_id") else 0
    evidence_score += 20 if last_seen else 0
    evidence_score += 20 if o.get("manual_verified_at") else 0
    evidence_score += 15 if o.get("eligibility") or o.get("risks") else 0
    return {"status": status, "evidence_score": min(100, evidence_score), "checked_at": now_iso()}


def personalized_score(o: dict[str, Any], profile: dict[str, Any]) -> int:
    score = int(o.get("base_match") or o.get("match") or 50)
    mode = (profile.get("work_mode") or "").lower()
    budget = profile.get("startup_budget")
    urgency = profile.get("urgency_days")
    experience = (profile.get("experience") or "").lower()
    goal = (profile.get("goal") or "").lower()
    if mode and mode != "any" and o.get("mode") == mode:
        score += 7
    if budget is not None and float(o.get("startup_cost") or 0) <= float(budget):
        score += 5
    if urgency and o.get("speed_days") is not None and int(o["speed_days"]) <= int(urgency):
        score += 7
    if experience and experience == o.get("experience"):
        score += 4
    text = f"{o.get('title','')} {o.get('category','')} {' '.join(jload(o.get('tags_json') if isinstance(o.get('tags_json'), str) else None, o.get('tags',[]) or []))}".lower()
    for token in set(re.findall(r"[a-z0-9]+", goal)):
        if len(token) > 3 and token in text:
            score += 1
    v = verification_state(o)["status"]
    if v == "verified": score += 5
    if v in {"stale", "expired", "blocked"}: score -= 15
    return max(0, min(100, score))


def get_profile(conn: sqlite3.Connection, user_id: int) -> dict[str, Any]:
    row = conn.execute("SELECT * FROM user_profiles WHERE user_id=?", (user_id,)).fetchone()
    return dict(row) if row else {}


def audit(conn: sqlite3.Connection, user_id: Optional[int], action: str, entity_type: str, entity_id: Optional[str], details: dict[str, Any] | None = None):
    conn.execute("INSERT INTO admin_audit(user_id, action, entity_type, entity_id, details_json, created_at) VALUES(?,?,?,?,?,?)",
                 (user_id, action, entity_type, entity_id, jdump(details or {}), now_iso()))

# ---------- schema ----------
SCHEMA = r'''
CREATE TABLE IF NOT EXISTS users(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 email TEXT NOT NULL UNIQUE COLLATE NOCASE,
 password_hash TEXT NOT NULL,
 role TEXT NOT NULL DEFAULT 'user',
 plan TEXT NOT NULL DEFAULT 'free',
 is_active INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL,
 last_login_at TEXT,
 email_verified_at TEXT,
 two_step_enabled INTEGER NOT NULL DEFAULT 0,
 stripe_customer_id TEXT,
 stripe_subscription_id TEXT,
 stripe_subscription_status TEXT
);
CREATE TABLE IF NOT EXISTS sessions(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 token_hash TEXT NOT NULL UNIQUE,
 csrf_token TEXT NOT NULL,
 expires_at TEXT NOT NULL,
 created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS user_profiles(
 user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
 goal TEXT DEFAULT '', work_mode TEXT DEFAULT 'any', startup_budget REAL DEFAULT 0,
 urgency_days INTEGER DEFAULT 14, experience TEXT DEFAULT 'entry', location TEXT DEFAULT '', updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS opportunities(
 id TEXT PRIMARY KEY,
 source_key TEXT NOT NULL,
 source_record_id TEXT,
 title TEXT NOT NULL,
 organization TEXT DEFAULT '',
 category TEXT NOT NULL,
 mode TEXT NOT NULL DEFAULT 'remote',
 experience TEXT NOT NULL DEFAULT 'entry',
 trust TEXT NOT NULL DEFAULT 'source',
 base_match INTEGER NOT NULL DEFAULT 50,
 speed_days INTEGER,
 income_min REAL,
 income_max REAL,
 income_period TEXT,
 income_label TEXT,
 income_is_estimate INTEGER NOT NULL DEFAULT 0,
 startup_cost REAL NOT NULL DEFAULT 0,
 durability INTEGER NOT NULL DEFAULT 50,
 competition INTEGER NOT NULL DEFAULT 50,
 tags_json TEXT NOT NULL DEFAULT '[]',
 source_name TEXT NOT NULL,
 source_url TEXT,
 first_seen TEXT,
 last_seen TEXT,
 closes_at TEXT,
 why TEXT DEFAULT '',
 risks TEXT DEFAULT '',
 eligibility TEXT DEFAULT '',
 steps_json TEXT NOT NULL DEFAULT '[]',
 evidence_json TEXT NOT NULL DEFAULT '{}',
 status TEXT NOT NULL DEFAULT 'active',
 content_hash TEXT,
 manual_verified_at TEXT,
 manual_verified_by INTEGER REFERENCES users(id),
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 UNIQUE(source_key, source_record_id)
);
CREATE INDEX IF NOT EXISTS idx_opportunities_status ON opportunities(status, closes_at);
CREATE INDEX IF NOT EXISTS idx_opportunities_source ON opportunities(source_key, last_seen);
CREATE TABLE IF NOT EXISTS opportunity_changes(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 opportunity_id TEXT NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
 old_hash TEXT, new_hash TEXT, change_json TEXT NOT NULL, detected_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS source_runs(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 source_key TEXT NOT NULL, status TEXT NOT NULL, fetched_count INTEGER NOT NULL DEFAULT 0,
 normalized_count INTEGER NOT NULL DEFAULT 0, error TEXT, started_at TEXT NOT NULL, finished_at TEXT
);
CREATE TABLE IF NOT EXISTS watchlist(
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 opportunity_id TEXT NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
 created_at TEXT NOT NULL, PRIMARY KEY(user_id, opportunity_id)
);
CREATE TABLE IF NOT EXISTS roadmaps(
 id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 opportunity_id TEXT NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
 title TEXT NOT NULL, steps_json TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS outreach_assets(
 id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 opportunity_id TEXT NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
 asset_type TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS alert_rules(
 id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 name TEXT NOT NULL, rule_json TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS alert_events(
 id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 opportunity_id TEXT REFERENCES opportunities(id) ON DELETE CASCADE, rule_id INTEGER REFERENCES alert_rules(id) ON DELETE SET NULL,
 kind TEXT NOT NULL, message TEXT NOT NULL, seen INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS outcomes(
 id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 opportunity_id TEXT NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
 stage TEXT NOT NULL, notes TEXT DEFAULT '', amount REAL, occurred_at TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS analytics_events(
 id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
 event_name TEXT NOT NULL, metadata_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS billing_events(
 id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
 provider TEXT NOT NULL, external_id TEXT, event_type TEXT NOT NULL, payload_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS admin_audit(
 id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
 action TEXT NOT NULL, entity_type TEXT NOT NULL, entity_id TEXT, details_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS saved_searches(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 name TEXT NOT NULL,
 query_json TEXT NOT NULL DEFAULT '{}',
 enabled INTEGER NOT NULL DEFAULT 1,
 last_evaluated_at TEXT,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS digest_preferences(
 user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
 cadence TEXT NOT NULL DEFAULT 'daily',
 enabled INTEGER NOT NULL DEFAULT 1,
 min_match INTEGER NOT NULL DEFAULT 70,
 include_closing_soon INTEGER NOT NULL DEFAULT 1,
 include_changes INTEGER NOT NULL DEFAULT 1,
 updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS api_keys(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 organization_id INTEGER REFERENCES organizations(id) ON DELETE CASCADE,
 name TEXT NOT NULL,
 key_prefix TEXT NOT NULL,
 key_hash TEXT NOT NULL UNIQUE,
 scopes_json TEXT NOT NULL DEFAULT '["opportunities:read"]',
 rate_limit_per_minute INTEGER,
 last_used_at TEXT,
 revoked_at TEXT,
 created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS api_usage(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 api_key_id INTEGER NOT NULL REFERENCES api_keys(id) ON DELETE CASCADE,
 endpoint TEXT NOT NULL,
 status_code INTEGER NOT NULL,
 created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS referral_codes(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 code TEXT NOT NULL UNIQUE,
 active INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL,
 UNIQUE(user_id)
);
CREATE TABLE IF NOT EXISTS referral_events(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 referral_code_id INTEGER NOT NULL REFERENCES referral_codes(id) ON DELETE CASCADE,
 event_type TEXT NOT NULL,
 referred_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
 metadata_json TEXT NOT NULL DEFAULT '{}',
 created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS providers(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 name TEXT NOT NULL,
 category TEXT NOT NULL,
 website TEXT,
 disclosure TEXT NOT NULL DEFAULT '',
 status TEXT NOT NULL DEFAULT 'pending',
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS provider_leads(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 provider_id INTEGER NOT NULL REFERENCES providers(id) ON DELETE CASCADE,
 opportunity_id TEXT REFERENCES opportunities(id) ON DELETE SET NULL,
 note TEXT NOT NULL DEFAULT '',
 status TEXT NOT NULL DEFAULT 'requested',
 admin_note TEXT NOT NULL DEFAULT '',
 assigned_to INTEGER REFERENCES users(id) ON DELETE SET NULL,
 closed_at TEXT,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS organizations(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 owner_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 name TEXT NOT NULL,
 slug TEXT NOT NULL UNIQUE,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS organization_members(
 organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 role TEXT NOT NULL DEFAULT 'member',
 provision_source TEXT NOT NULL DEFAULT 'manual',
 created_at TEXT NOT NULL,
 PRIMARY KEY(organization_id,user_id)
);
CREATE TABLE IF NOT EXISTS tenant_settings(
 organization_id INTEGER PRIMARY KEY REFERENCES organizations(id) ON DELETE CASCADE,
 brand_name TEXT NOT NULL DEFAULT 'Cashh Radar',
 accent_color TEXT NOT NULL DEFAULT '#00E5C2',
 logo_url TEXT,
 custom_domain TEXT,
 settings_json TEXT NOT NULL DEFAULT '{}',
 updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS opportunity_submissions(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 title TEXT NOT NULL,
 source_url TEXT NOT NULL,
 category TEXT NOT NULL DEFAULT 'Other',
 notes TEXT NOT NULL DEFAULT '',
 status TEXT NOT NULL DEFAULT 'pending',
 reviewed_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
 reviewed_at TEXT,
 created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS password_reset_tokens(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 token_hash TEXT NOT NULL UNIQUE,
 expires_at TEXT NOT NULL,
 used_at TEXT,
 created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS digest_deliveries(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 cadence TEXT NOT NULL,
 status TEXT NOT NULL,
 message_preview TEXT NOT NULL DEFAULT '',
 error TEXT,
 created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS organization_invites(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
 email TEXT NOT NULL COLLATE NOCASE,
 role TEXT NOT NULL DEFAULT 'member',
 token_hash TEXT NOT NULL UNIQUE,
 expires_at TEXT NOT NULL,
 accepted_at TEXT,
 invited_by INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_org_invites_email ON organization_invites(email,accepted_at,expires_at);
CREATE TABLE IF NOT EXISTS job_runs(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 job_name TEXT NOT NULL,
 status TEXT NOT NULL,
 details_json TEXT NOT NULL DEFAULT '{}',
 started_at TEXT NOT NULL,
 finished_at TEXT,
 duration_ms INTEGER
);
CREATE INDEX IF NOT EXISTS idx_job_runs_name_time ON job_runs(job_name,started_at);
CREATE TABLE IF NOT EXISTS email_verification_tokens(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 token_hash TEXT NOT NULL UNIQUE,
 expires_at TEXT NOT NULL,
 used_at TEXT,
 created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS login_challenges(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 challenge_hash TEXT NOT NULL UNIQUE,
 code_hash TEXT NOT NULL,
 expires_at TEXT NOT NULL,
 used_at TEXT,
 created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS organization_watchlist(
 organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
 opportunity_id TEXT NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
 added_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
 created_at TEXT NOT NULL,
 PRIMARY KEY(organization_id, opportunity_id)
);
CREATE TABLE IF NOT EXISTS organization_webhooks(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
 url TEXT NOT NULL,
 events_json TEXT NOT NULL DEFAULT '["*"]',
 active INTEGER NOT NULL DEFAULT 1,
 created_by INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS webhook_deliveries(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
 webhook_id INTEGER REFERENCES organization_webhooks(id) ON DELETE CASCADE,
 event_type TEXT NOT NULL,
 payload_json TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending',
 attempts INTEGER NOT NULL DEFAULT 0,
 last_error TEXT,
 next_attempt_at TEXT,
 delivered_at TEXT,
 created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS scim_tokens(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
 name TEXT NOT NULL,
 token_prefix TEXT NOT NULL,
 token_hash TEXT NOT NULL UNIQUE,
 created_by INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 revoked_at TEXT,
 created_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_billing_provider_event_unique ON billing_events(provider,external_id,event_type) WHERE external_id IS NOT NULL;
CREATE TABLE IF NOT EXISTS schema_migrations(
 version INTEGER PRIMARY KEY,
 name TEXT NOT NULL,
 applied_at TEXT NOT NULL
);
'''

DEMO_OPPS = [
 dict(id="demo-001",source_key="demo",source_record_id="demo-001",title="Remote Customer Support Specialist",organization="Illustrative model",category="Remote Employment",mode="remote",experience="entry",trust="demo",base_match=91,speed_days=14,income_min=32000,income_max=52000,income_period="year",income_label="Illustrative salary range",income_is_estimate=1,startup_cost=0,durability=72,competition=68,tags=["Remote","Entry level","$0 startup"],source_name="Illustrative only — no live employer attached",source_url=None,first_seen=now_iso(),last_seen=now_iso(),closes_at=None,why="Strong fit for users who need a low-cost remote path and can communicate clearly by chat, email, or phone.",risks="Hiring timelines vary widely; roles can be competitive and compensation depends on employer and location.",eligibility="Illustrative model only; confirm each employer's actual requirements.",steps=["Create an ATS-ready support resume","Build a concise customer-service proof portfolio","Target recent remote listings","Apply with role-specific keywords","Track replies and iterate weekly"]),
 dict(id="demo-002",source_key="demo",source_record_id="demo-002",title="AI-Assisted Lead Research Service",organization="Illustrative service model",category="Freelance Service",mode="remote",experience="quick",trust="demo",base_match=94,speed_days=3,income_min=500,income_max=5000,income_period="month",income_label="Illustrative monthly range",income_is_estimate=1,startup_cost=0,durability=77,competition=61,tags=["Remote","Service","Fast start"],source_name="Illustrative business model — not a guaranteed income claim",source_url=None,first_seen=now_iso(),last_seen=now_iso(),closes_at=None,why="Can be started with basic research and outreach skills, little capital, and a narrow deliverable such as verified prospect research for one niche.",risks="Revenue depends on finding paying clients, data quality, platform rules, and consistent fulfillment.",eligibility="No platform or client eligibility is implied.",steps=["Pick one buyer niche","Define a concrete research deliverable","Create a five-lead sample","Contact prospects with a specific truthful offer","Track outcomes and improve the offer"]),
 dict(id="demo-003",source_key="demo",source_record_id="demo-003",title="Appointment-Setting Contractor",organization="Illustrative contract model",category="Remote Contract Work",mode="remote",experience="entry",trust="demo",base_match=88,speed_days=7,income_min=1000,income_max=6000,income_period="month",income_label="Illustrative monthly range",income_is_estimate=1,startup_cost=0,durability=69,competition=66,tags=["Remote","Contract","Sales"],source_name="Illustrative only — compensation models vary",source_url=None,first_seen=now_iso(),last_seen=now_iso(),closes_at=None,why="Accessible to users who can learn concise outbound messaging and manage follow-up without a large startup budget.",risks="Some offers are commission-only. Verify compensation structure, lead source, and payment terms before accepting.",eligibility="Illustrative model only.",steps=["Learn a short qualification script","Choose industries with clear appointment value","Build a simple outreach tracker","Pitch paid-trial arrangements","Measure booked-call and show-up rates"]),
 dict(id="demo-004",source_key="demo",source_record_id="demo-004",title="Local Digital Setup Service for Small Businesses",organization="Illustrative microbusiness",category="Microbusiness",mode="hybrid",experience="quick",trust="demo",base_match=86,speed_days=2,income_min=300,income_max=7000,income_period="month",income_label="Illustrative revenue range",income_is_estimate=1,startup_cost=0,durability=83,competition=54,tags=["Local + remote","B2B","Recurring potential"],source_name="Illustrative service concept",source_url=None,first_seen=now_iso(),last_seen=now_iso(),closes_at=None,why="Targets visible business setup gaps using common digital tools.",risks="Client acquisition is the main bottleneck; platform rules and truthful representation matter.",eligibility="Illustrative model only.",steps=["Choose one business category","Audit visible public setup gaps","Define one fixed-scope improvement","Offer it with transparent pricing","Convert successful work into maintenance where useful"]),
 dict(id="demo-005",source_key="demo",source_record_id="demo-005",title="Specialized Online Research Contractor",organization="Illustrative research service",category="Freelance / Research",mode="remote",experience="quick",trust="demo",base_match=82,speed_days=10,income_min=800,income_max=6500,income_period="month",income_label="Illustrative monthly range",income_is_estimate=1,startup_cost=0,durability=81,competition=58,tags=["Remote","Research","Low overhead"],source_name="Illustrative service model",source_url=None,first_seen=now_iso(),last_seen=now_iso(),closes_at=None,why="Durable where clients value source quality, judgment, synthesis, and domain-specific verification.",risks="Needs strong evidence handling and a clear niche; generic research is easier to commoditize.",eligibility="Illustrative model only.",steps=["Select a research niche","Create a sourced sample brief","Define scope and turnaround","Pitch decision-makers with a concrete problem","Build reusable source and QA workflows"]),
 dict(id="demo-006",source_key="demo",source_record_id="demo-006",title="Niche Opportunity Newsletter + Referral Layer",organization="Illustrative digital business",category="Digital Business",mode="remote",experience="experienced",trust="demo",base_match=75,speed_days=30,income_min=0,income_max=12000,income_period="month",income_label="Illustrative revenue range",income_is_estimate=1,startup_cost=50,durability=88,competition=71,tags=["Remote","Audience","Scalable"],source_name="Illustrative publishing model",source_url=None,first_seen=now_iso(),last_seen=now_iso(),closes_at=None,why="A narrow verified-opportunity publication can compound into subscriptions, disclosed referrals and structured data products.",risks="Slower to monetize; audience growth, trust, disclosure and content quality determine viability.",eligibility="Illustrative model only.",steps=["Choose a narrow opportunity niche","Define verification criteria","Publish a consistent free edition","Build opt-in audience","Add disclosed monetization after trust is established"]),
]

SNAPSHOT_OPPS = [
 dict(id="snapshot-usajobs-878631000",source_key="usajobs",source_record_id="878631000",title="Customer Service Representative",organization="Social Security Administration",category="Federal Employment",mode="hybrid",experience="entry",trust="source",base_match=77,speed_days=None,income_min=40736,income_max=68485,income_period="year",income_label="Salary",income_is_estimate=0,startup_cost=0,durability=78,competition=70,tags=["Telework eligible","Public hiring","Full-time"],source_name="USAJOBS / Social Security Administration",source_url="https://ssa.usajobs.gov/job/878631000",first_seen="2026-08-26T21:35:00+00:00",last_seen="2026-08-26T21:35:00+00:00",closes_at="2026-10-01T03:59:00+00:00",why="Official federal customer-service announcement with published salary and an official source record.",risks="Location, qualification, training and federal hiring timelines apply; telework does not mean fully remote.",eligibility="Open to U.S. citizens subject to the announcement's qualification and other federal requirements.",steps=["Open the canonical announcement","Confirm a listed duty station works","Match your experience or education to qualifications","Prepare a federal resume","Apply before the listed deadline"]),
 dict(id="snapshot-usajobs-881906000",source_key="usajobs",source_record_id="881906000",title="Management and Program Analyst",organization="National Nuclear Security Administration",category="Federal Employment",mode="hybrid",experience="experienced",trust="source",base_match=66,speed_days=None,income_min=90925,income_max=139684,income_period="year",income_label="Base salary",income_is_estimate=0,startup_cost=0,durability=84,competition=73,tags=["Telework eligible","Permanent","Federal"],source_name="USAJOBS / National Nuclear Security Administration",source_url="https://www.usajobs.gov/job/881906000",first_seen="2026-08-26T21:35:00+00:00",last_seen="2026-08-26T21:35:00+00:00",closes_at="2026-09-01T03:59:00+00:00",why="Official federal announcement with published salary and permanent schedule.",risks="Restricted hiring paths, specialized experience and security requirements may apply.",eligibility="Restricted to listed federal/special hiring authorities rather than open public hiring.",steps=["Check hiring-path eligibility","Confirm specialized experience","Review security/testing requirements","Prepare required documents","Apply before the deadline"]),
 dict(id="snapshot-grants-363233",source_key="grants_gov",source_record_id="363233",title="Engineering Research Initiation",organization="U.S. National Science Foundation",category="Grant / Funding",mode="organization",experience="experienced",trust="source",base_match=52,speed_days=None,income_min=None,income_max=None,income_period="award",income_label="Funding",income_is_estimate=0,startup_cost=0,durability=60,competition=82,tags=["Grant","Engineering research","NSF"],source_name="Grants.gov / U.S. National Science Foundation",source_url="https://www.grants.gov/search-results-detail/363233",first_seen="2026-08-26T21:35:00+00:00",last_seen="2026-08-26T21:35:00+00:00",closes_at="2026-10-10T03:59:00+00:00",why="Official Grants.gov opportunity with an October 2026 closing date.",risks="Eligibility, proposal requirements, allowable costs and award terms must be checked in the full notice; funding is competitive.",eligibility="See the full NSF notice and Grants.gov package for applicant and proposal eligibility.",steps=["Open the official Grants.gov record","Read the full notice","Confirm institutional and PI eligibility","Build a compliance checklist","Submit through the required workflow"]),
 dict(id="snapshot-grants-361315",source_key="grants_gov",source_record_id="361315",title="National Urban and Community Forestry Challenge Cost Share",organization="U.S. Forest Service",category="Grant / Funding",mode="organization",experience="experienced",trust="source",base_match=55,speed_days=None,income_min=200000,income_max=750000,income_period="award",income_label="Award range",income_is_estimate=0,startup_cost=0,durability=65,competition=78,tags=["Grant","Community forestry","Public/nonprofit"],source_name="Grants.gov / U.S. Forest Service",source_url="https://www.grants.gov/search-results-detail/361315",first_seen="2026-08-26T21:35:00+00:00",last_seen="2026-08-26T21:35:00+00:00",closes_at="2026-10-13T03:59:00+00:00",why="Official federal funding opportunity aimed at community forestry solutions.",risks="This is organizational funding, not direct personal income; eligibility and cost-share requirements apply and awards are competitive.",eligibility="Eligible applicant classes listed by Grants.gov include specified public, tribal, nonprofit, educational and other entities.",steps=["Open the official Grants.gov record","Confirm applicant eligibility","Map the project to program purpose","Review cost-share and notice requirements","Submit before the deadline"]),
]


def upsert_opportunity(conn: sqlite3.Connection, o: dict[str, Any], actor_id: Optional[int] = None) -> tuple[bool, bool]:
    payload = dict(o)
    payload.setdefault("source_record_id", payload["id"])
    payload.setdefault("organization", "")
    payload.setdefault("income_period", None)
    payload.setdefault("income_label", "Income")
    payload.setdefault("income_is_estimate", 0)
    payload.setdefault("evidence", {"source": payload.get("source_name"), "captured_at": payload.get("last_seen") or now_iso()})
    payload.setdefault("status", "active")
    payload.setdefault("created_at", now_iso())
    payload["updated_at"] = now_iso()
    payload["content_hash"] = record_hash({
        "title": payload.get("title"), "organization": payload.get("organization"), "source_url": payload.get("source_url"),
        "closes_at": payload.get("closes_at"), "income_min": payload.get("income_min"), "income_max": payload.get("income_max"),
        "eligibility": payload.get("eligibility"), "risks": payload.get("risks")
    })
    existing = conn.execute("SELECT * FROM opportunities WHERE id=? OR (source_key=? AND source_record_id=?) LIMIT 1",
                            (payload["id"], payload["source_key"], payload["source_record_id"])).fetchone()
    changed = False
    created = existing is None
    if existing and existing["content_hash"] != payload["content_hash"]:
        changed = True
        changes = {}
        for key in ["title","organization","source_url","closes_at","income_min","income_max","eligibility","risks"]:
            newv = payload.get(key)
            oldv = existing[key]
            if oldv != newv: changes[key] = {"old": oldv, "new": newv}
        conn.execute("INSERT INTO opportunity_changes(opportunity_id,old_hash,new_hash,change_json,detected_at) VALUES(?,?,?,?,?)",
                     (existing["id"], existing["content_hash"], payload["content_hash"], jdump(changes), now_iso()))
    cols = ["id","source_key","source_record_id","title","organization","category","mode","experience","trust","base_match","speed_days","income_min","income_max","income_period","income_label","income_is_estimate","startup_cost","durability","competition","tags_json","source_name","source_url","first_seen","last_seen","closes_at","why","risks","eligibility","steps_json","evidence_json","status","content_hash","created_at","updated_at"]
    vals = [payload.get(c) for c in cols]
    vals[cols.index("tags_json")] = jdump(payload.get("tags", []))
    vals[cols.index("steps_json")] = jdump(payload.get("steps", []))
    vals[cols.index("evidence_json")] = jdump(payload.get("evidence", {}))
    qmarks = ",".join("?" for _ in cols)
    updates = ",".join(f"{c}=excluded.{c}" for c in cols if c not in {"id","created_at"})
    conn.execute(f"INSERT INTO opportunities({','.join(cols)}) VALUES({qmarks}) ON CONFLICT(id) DO UPDATE SET {updates}", vals)
    if changed:
        create_change_alerts(conn, payload["id"])
    if actor_id is not None:
        audit(conn, actor_id, "upsert", "opportunity", payload["id"], {"created": created, "changed": changed})
    return created, changed


def create_change_alerts(conn: sqlite3.Connection, opportunity_id: str):
    rows = conn.execute("SELECT w.user_id FROM watchlist w WHERE w.opportunity_id=?", (opportunity_id,)).fetchall()
    for r in rows:
        conn.execute("INSERT INTO alert_events(user_id, opportunity_id, kind, message, created_at) VALUES(?,?,?,?,?)",
                     (r["user_id"], opportunity_id, "material_change", "A saved opportunity changed at its source. Review the updated record.", now_iso()))


def ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    cols={r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def apply_schema_extensions(conn: sqlite3.Connection) -> None:
    # Forward-only, additive SQLite migrations for older packaged databases.
    ensure_column(conn,"api_keys","organization_id","INTEGER")
    ensure_column(conn,"api_keys","rate_limit_per_minute","INTEGER")
    ensure_column(conn,"provider_leads","admin_note","TEXT NOT NULL DEFAULT ''")
    ensure_column(conn,"provider_leads","assigned_to","INTEGER")
    ensure_column(conn,"provider_leads","closed_at","TEXT")
    ensure_column(conn,"users","email_verified_at","TEXT")
    ensure_column(conn,"users","two_step_enabled","INTEGER NOT NULL DEFAULT 0")
    ensure_column(conn,"users","stripe_customer_id","TEXT")
    ensure_column(conn,"users","stripe_subscription_id","TEXT")
    ensure_column(conn,"users","stripe_subscription_status","TEXT")
    ensure_column(conn,"organization_members","provision_source","TEXT NOT NULL DEFAULT 'manual'")
    conn.execute("INSERT OR IGNORE INTO schema_migrations(version,name,applied_at) VALUES(?,?,?)",(1,"master_baseline",now_iso()))
    conn.execute("INSERT OR IGNORE INTO schema_migrations(version,name,applied_at) VALUES(?,?,?)",(2,"enterprise_operations_hardening",now_iso()))
    conn.execute("INSERT OR IGNORE INTO schema_migrations(version,name,applied_at) VALUES(?,?,?)",(3,"launch_completion_v2_2",now_iso()))
    conn.execute("INSERT OR IGNORE INTO schema_migrations(version,name,applied_at) VALUES(?,?,?)",(4,"stripe_subscription_lifecycle",now_iso()))


def init_db():
    with db() as conn:
        conn.executescript(SCHEMA)
        apply_schema_extensions(conn)
        count = conn.execute("SELECT COUNT(*) c FROM opportunities").fetchone()["c"]
        if count == 0:
            for o in DEMO_OPPS + SNAPSHOT_OPPS:
                upsert_opportunity(conn, o)
        admin_email = os.getenv("CASHH_ADMIN_EMAIL")
        admin_password = os.getenv("CASHH_ADMIN_PASSWORD")
        if admin_email and admin_password:
            row = conn.execute("SELECT id FROM users WHERE email=? COLLATE NOCASE", (admin_email,)).fetchone()
            if row:
                conn.execute("UPDATE users SET role='admin', email_verified_at=COALESCE(email_verified_at,?) WHERE id=?", (now_iso(), row["id"]))
            else:
                conn.execute("INSERT INTO users(email,password_hash,role,plan,created_at,email_verified_at) VALUES(?,?,?,?,?,?)",
                             (admin_email.lower().strip(), hash_password(admin_password), "admin", "pro", now_iso(), now_iso()))

init_db()

# ---------- request models ----------
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=200)
    referral_code: Optional[str] = Field(default=None, min_length=3, max_length=80)

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class ProfileIn(BaseModel):
    goal: str = Field(default="", max_length=1000)
    work_mode: str = Field(default="any", max_length=30)
    startup_budget: float = Field(default=0, ge=0, le=1_000_000)
    urgency_days: int = Field(default=14, ge=1, le=3650)
    experience: str = Field(default="entry", max_length=30)
    location: str = Field(default="", max_length=120)

class AdvisorIn(BaseModel):
    goal: str = Field(default="", max_length=1000)
    work_mode: Optional[str] = None
    startup_budget: Optional[float] = Field(default=None, ge=0)
    urgency_days: Optional[int] = Field(default=None, ge=1, le=3650)
    experience: Optional[str] = None
    limit: int = Field(default=5, ge=1, le=10)

class RoadmapIn(BaseModel):
    opportunity_id: str

class OutreachIn(BaseModel):
    opportunity_id: str
    asset_type: str = Field(default="application_email", pattern="^(application_email|proposal|dm|follow_up)$")

class AlertRuleIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: str = Field(default="deadline", pattern="^(deadline|material_change|new_match)$")
    days: int = Field(default=3, ge=1, le=90)
    enabled: bool = True

class OutcomeIn(BaseModel):
    opportunity_id: str
    stage: str = Field(pattern="^(saved|started|applied|contacted|replied|interview|negotiating|won|paid|fulfilled|follow_up|lost)$")
    notes: str = Field(default="", max_length=3000)
    amount: Optional[float] = None
    occurred_at: Optional[str] = None

class AdminOpportunityIn(BaseModel):
    id: str = Field(min_length=2, max_length=160)
    title: str = Field(min_length=2, max_length=300)
    organization: str = ""
    category: str = "Other"
    mode: str = "remote"
    experience: str = "entry"
    trust: str = "source"
    source_key: str = "admin"
    source_record_id: Optional[str] = None
    source_name: str = "Admin submitted"
    source_url: Optional[str] = None
    closes_at: Optional[str] = None
    income_min: Optional[float] = None
    income_max: Optional[float] = None
    income_period: Optional[str] = None
    income_label: str = "Income"
    startup_cost: float = 0
    speed_days: Optional[int] = None
    durability: int = Field(default=50, ge=0, le=100)
    competition: int = Field(default=50, ge=0, le=100)
    base_match: int = Field(default=50, ge=0, le=100)
    tags: list[str] = []
    why: str = ""
    risks: str = ""
    eligibility: str = ""
    steps: list[str] = []
    status: str = "active"

class EventIn(BaseModel):
    event_name: str = Field(min_length=1, max_length=100)
    metadata: dict[str, Any] = {}

class CheckoutIn(BaseModel):
    plan: str = Field(pattern="^(pro|team)$")


class SavedSearchIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    text: str = Field(default="", max_length=500)
    mode: str = Field(default="all", max_length=30)
    category: str = Field(default="all", max_length=80)
    min_match: int = Field(default=70, ge=0, le=100)
    max_startup_cost: Optional[float] = Field(default=None, ge=0)
    closing_within_days: Optional[int] = Field(default=None, ge=1, le=3650)
    enabled: bool = True

class DigestPreferenceIn(BaseModel):
    cadence: str = Field(default="daily", pattern="^(daily|weekly)$")
    enabled: bool = True
    min_match: int = Field(default=70, ge=0, le=100)
    include_closing_soon: bool = True
    include_changes: bool = True

class ApiKeyIn(BaseModel):
    name: str = Field(default="Default key", min_length=1, max_length=120)
    organization_id: Optional[int] = None
    scopes: list[str] = Field(default_factory=lambda: ["opportunities:read"])

class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=10, max_length=200)

class AccountDeleteIn(BaseModel):
    password: str
    confirmation: str = Field(pattern="^DELETE$")

class PasswordResetRequestIn(BaseModel):
    email: EmailStr

class PasswordResetConfirmIn(BaseModel):
    token: str = Field(min_length=20, max_length=300)
    new_password: str = Field(min_length=10, max_length=200)

class ReferralEventIn(BaseModel):
    code: str = Field(min_length=3, max_length=80)
    event_type: str = Field(default="visit", pattern="^(visit|signup|conversion)$")
    metadata: dict[str, Any] = {}

class ProviderIn(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    category: str = Field(min_length=2, max_length=120)
    website: Optional[str] = Field(default=None, max_length=500)
    disclosure: str = Field(default="", max_length=2000)
    status: str = Field(default="active", pattern="^(pending|active|paused)$")

class ProviderLeadIn(BaseModel):
    provider_id: int
    opportunity_id: Optional[str] = None
    note: str = Field(default="", max_length=2000)

class OpportunitySubmissionIn(BaseModel):
    title: str = Field(min_length=2, max_length=300)
    source_url: str = Field(min_length=8, max_length=1000)
    category: str = Field(default="Other", max_length=120)
    notes: str = Field(default="", max_length=3000)

class OrganizationIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    slug: str = Field(min_length=2, max_length=80, pattern="^[a-z0-9-]+$")

class TenantSettingsIn(BaseModel):
    brand_name: str = Field(default="Cashh Radar", min_length=2, max_length=120)
    accent_color: str = Field(default="#00E5C2", pattern="^#[0-9A-Fa-f]{6}$")
    logo_url: Optional[str] = Field(default=None, max_length=500)
    custom_domain: Optional[str] = Field(default=None, max_length=255)

class OrganizationInviteIn(BaseModel):
    email: EmailStr
    role: str = Field(default="member", pattern="^(member|analyst|admin)$")

class OrganizationInviteAcceptIn(BaseModel):
    token: str = Field(min_length=20, max_length=300)

class OrganizationMemberRoleIn(BaseModel):
    role: str = Field(pattern="^(member|analyst|admin)$")

class ProviderLeadStatusIn(BaseModel):
    status: str = Field(pattern="^(requested|contacted|qualified|closed_won|closed_lost)$")
    admin_note: str = Field(default="", max_length=2000)

class EmailVerificationRequestIn(BaseModel):
    email: EmailStr

class EmailVerificationConfirmIn(BaseModel):
    token: str = Field(min_length=20, max_length=300)

class TwoStepSettingsIn(BaseModel):
    enabled: bool
    password: str

class LoginChallengeConfirmIn(BaseModel):
    challenge_token: str = Field(min_length=20, max_length=300)
    code: str = Field(min_length=6, max_length=6, pattern="^[0-9]{6}$")

class OrganizationOwnerTransferIn(BaseModel):
    new_owner_user_id: int

class OrganizationDeleteIn(BaseModel):
    password: str
    confirmation: str = Field(pattern="^DELETE$")

class OrganizationWebhookIn(BaseModel):
    url: str = Field(min_length=8, max_length=1000, pattern="^https://")
    events: list[str] = Field(default_factory=lambda:["*"])

class ScimTokenIn(BaseModel):
    name: str = Field(default="SCIM", min_length=1, max_length=120)

# ---------- auth ----------
RATE_BUCKET: dict[str, list[float]] = {}

def rate_limit(request: Request, bucket: str, limit: int = 20, window: int = 60):
    if DEV_MODE and os.getenv("CASHH_RATE_LIMIT_DEV", "0") != "1": return
    key = f"{bucket}:{request.client.host if request.client else 'unknown'}"
    now = time.time()
    arr = [t for t in RATE_BUCKET.get(key, []) if now - t < window]
    if len(arr) >= limit:
        raise HTTPException(429, "Too many requests. Try again shortly.")
    arr.append(now)
    RATE_BUCKET[key] = arr


def session_user(request: Request) -> Optional[dict[str, Any]]:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    th = token_hash(token)
    with db() as conn:
        row = conn.execute("SELECT s.csrf_token,s.expires_at,u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=?", (th,)).fetchone()
        if not row or not row["is_active"]:
            return None
        exp = parse_dt(row["expires_at"])
        if not exp or exp < datetime.now(timezone.utc):
            conn.execute("DELETE FROM sessions WHERE token_hash=?", (th,))
            return None
        return dict(row)


def require_user(request: Request) -> dict[str, Any]:
    u = session_user(request)
    if not u:
        raise HTTPException(401, "Sign in required")
    return u


def require_admin(request: Request) -> dict[str, Any]:
    u = require_user(request)
    if u.get("role") != "admin":
        raise HTTPException(403, "Admin access required")
    return u


def require_csrf(request: Request, user: dict[str, Any], x_csrf_token: Optional[str]):
    if request.method in {"POST","PUT","PATCH","DELETE"}:
        if not x_csrf_token or not hmac.compare_digest(x_csrf_token, user.get("csrf_token", "")):
            raise HTTPException(403, "Invalid CSRF token")


def create_session(conn: sqlite3.Connection, user_id: int) -> tuple[str, str]:
    token = secrets.token_urlsafe(36)
    csrf = secrets.token_urlsafe(24)
    expires = (datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)).replace(microsecond=0).isoformat()
    conn.execute("INSERT INTO sessions(user_id,token_hash,csrf_token,expires_at,created_at) VALUES(?,?,?,?,?)",
                 (user_id, token_hash(token), csrf, expires, now_iso()))
    return token, csrf


def set_session_cookie(response: Response, token: str):
    response.set_cookie(COOKIE_NAME, token, httponly=True, samesite="lax", secure=COOKIE_SECURE, max_age=SESSION_DAYS*86400, path="/")


def _issue_email_verification(conn: sqlite3.Connection, user_id: int, email: str) -> dict[str,Any]:
    raw=secrets.token_urlsafe(40)
    expires=(datetime.now(timezone.utc)+timedelta(hours=24)).replace(microsecond=0).isoformat()
    conn.execute("DELETE FROM email_verification_tokens WHERE user_id=? AND used_at IS NULL",(user_id,))
    conn.execute("INSERT INTO email_verification_tokens(user_id,token_hash,expires_at,created_at) VALUES(?,?,?,?)",(user_id,token_hash(raw),expires,now_iso()))
    url=f"{PUBLIC_URL}/?verify_email={raw}"
    ok,info=send_email(email,"Verify your Cashh Radar email",f"Verify your Cashh Radar email address.\n\nOpen: {url}\n\nThis link expires in 24 hours.")
    out={"sent":ok,"info":info}
    if DEV_MODE: out["dev_token"]=raw
    return out

def _webhook_secret(webhook_id:int) -> str:
    return hmac.new(SECRET_KEY.encode(),f"cashh-webhook:{webhook_id}".encode(),hashlib.sha256).hexdigest()

def _queue_org_event(conn:sqlite3.Connection, organization_id:int, event_type:str, payload:dict[str,Any]):
    hooks=conn.execute("SELECT * FROM organization_webhooks WHERE organization_id=? AND active=1",(organization_id,)).fetchall()
    for hook in hooks:
        events=jload(hook["events_json"],["*"])
        if "*" not in events and event_type not in events: continue
        conn.execute("INSERT INTO webhook_deliveries(organization_id,webhook_id,event_type,payload_json,status,next_attempt_at,created_at) VALUES(?,?,?,?,?,?,?)",(organization_id,hook["id"],event_type,jdump(payload),"pending",now_iso(),now_iso()))

# ---------- middleware ----------
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self' https://checkout.stripe.com"
    if COOKIE_SECURE:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

# ---------- core pages ----------
@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/robots.txt")
def robots():
    return PlainTextResponse(f"User-agent: *\nAllow: /\nSitemap: {PUBLIC_URL}/sitemap.xml\n")

@app.get("/sitemap.xml")
def sitemap():
    pages=[("/","daily","1.0"),("/privacy","monthly","0.4"),("/terms","monthly","0.4"),("/disclosures","monthly","0.4"),("/security","monthly","0.4"),("/support","monthly","0.5")]
    body="".join(f"<url><loc>{PUBLIC_URL}{path}</loc><changefreq>{freq}</changefreq><priority>{priority}</priority></url>" for path,freq,priority in pages)
    xml=f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>'
    return Response(xml, media_type="application/xml")

@app.get("/manifest.json")
def manifest():
    return {"name":"Cashh Radar","short_name":"Cashh Radar","start_url":"/","display":"standalone","background_color":"#0B1020","theme_color":"#0B1020","description":"Evidence-labeled opportunity intelligence and execution platform.","icons":[{"src":"/static/assets/icons/icon-192.png","sizes":"192x192","type":"image/png","purpose":"any maskable"},{"src":"/static/assets/icons/icon-512.png","sizes":"512x512","type":"image/png","purpose":"any maskable"}]}

# ---------- auth API ----------
@app.post("/api/register")
def register(payload: RegisterIn, request: Request, response: Response):
    rate_limit(request, "register", 8, 300)
    email = payload.email.lower().strip()
    with db() as conn:
        if conn.execute("SELECT 1 FROM users WHERE email=? COLLATE NOCASE", (email,)).fetchone():
            raise HTTPException(409, "Account already exists")
        verified_at = now_iso() if DEV_MODE and not REQUIRE_EMAIL_VERIFICATION else None
        cur = conn.execute("INSERT INTO users(email,password_hash,created_at,email_verified_at) VALUES(?,?,?,?)", (email, hash_password(payload.password), now_iso(), verified_at))
        user_id = cur.lastrowid
        conn.execute("INSERT INTO user_profiles(user_id,updated_at) VALUES(?,?)", (user_id, now_iso()))
        if payload.referral_code:
            ref=conn.execute("SELECT id,user_id FROM referral_codes WHERE code=? AND active=1",(payload.referral_code.strip().upper(),)).fetchone()
            if ref and int(ref["user_id"]) != int(user_id):
                conn.execute("INSERT INTO referral_events(referral_code_id,event_type,referred_user_id,metadata_json,created_at) VALUES(?,?,?,?,?)",(ref["id"],"signup",user_id,jdump({"source":"registration"}),now_iso()))
        verification=_issue_email_verification(conn,user_id,email) if not verified_at else {"sent":False,"info":"already verified in dev"}
        if REQUIRE_EMAIL_VERIFICATION and not verified_at:
            result={"ok":True,"verification_required":True,"message":"Check your email to verify your account before signing in."}
            if DEV_MODE and verification.get("dev_token"): result["dev_verification_token"]=verification["dev_token"]
            return result
        token, csrf = create_session(conn, user_id)
    set_session_cookie(response, token)
    return {"ok": True, "user": {"id": user_id, "email": email, "role": "user", "plan": "free", "email_verified":bool(verified_at)}, "csrf_token": csrf}

@app.post("/api/login")
def login(payload: LoginIn, request: Request, response: Response):
    rate_limit(request, "login", 10, 300)
    with db() as conn:
        row = conn.execute("SELECT * FROM users WHERE email=? COLLATE NOCASE", (payload.email.lower().strip(),)).fetchone()
        if not row or not verify_password(payload.password, row["password_hash"]):
            raise HTTPException(401, "Invalid email or password")
        if not row["is_active"]:
            raise HTTPException(403, "Account disabled")
        if REQUIRE_EMAIL_VERIFICATION and not row["email_verified_at"]:
            raise HTTPException(403,"Verify your email before signing in")
        if row["two_step_enabled"]:
            if not smtp_configured() and not DEV_MODE: raise HTTPException(503,"Two-step email delivery is unavailable")
            challenge=secrets.token_urlsafe(36);code=f"{secrets.randbelow(1000000):06d}";expires=(datetime.now(timezone.utc)+timedelta(minutes=10)).replace(microsecond=0).isoformat()
            conn.execute("DELETE FROM login_challenges WHERE user_id=? AND used_at IS NULL",(row["id"],))
            conn.execute("INSERT INTO login_challenges(user_id,challenge_hash,code_hash,expires_at,created_at) VALUES(?,?,?,?,?)",(row["id"],token_hash(challenge),token_hash(code),expires,now_iso()))
            send_email(row["email"],"Your Cashh Radar sign-in code",f"Your Cashh Radar sign-in code is {code}. It expires in 10 minutes.")
            result={"ok":True,"two_step_required":True,"challenge_token":challenge}
            if DEV_MODE: result["dev_code"]=code
            return result
        conn.execute("UPDATE users SET last_login_at=? WHERE id=?", (now_iso(), row["id"]))
        conn.execute("DELETE FROM sessions WHERE user_id=? AND expires_at < ?", (row["id"], now_iso()))
        token, csrf = create_session(conn, row["id"])
    set_session_cookie(response, token)
    return {"ok": True, "user": {"id": row["id"], "email": row["email"], "role": row["role"], "plan": row["plan"], "email_verified":bool(row["email_verified_at"]), "two_step_enabled":bool(row["two_step_enabled"]), "subscription_status":row["stripe_subscription_status"]}, "csrf_token": csrf}

@app.post("/api/login/two-step")
def login_two_step(payload:LoginChallengeConfirmIn,request:Request,response:Response):
    rate_limit(request,"login-two-step",10,300);now=datetime.now(timezone.utc)
    with db() as conn:
        row=conn.execute("SELECT c.*,u.email,u.role,u.plan,u.is_active,u.email_verified_at,u.two_step_enabled,u.stripe_subscription_status FROM login_challenges c JOIN users u ON u.id=c.user_id WHERE c.challenge_hash=? AND c.used_at IS NULL",(token_hash(payload.challenge_token),)).fetchone()
        if not row or not row["is_active"] or not parse_dt(row["expires_at"]) or parse_dt(row["expires_at"])<now or not hmac.compare_digest(row["code_hash"],token_hash(payload.code)):
            raise HTTPException(401,"Invalid or expired sign-in code")
        conn.execute("UPDATE login_challenges SET used_at=? WHERE id=?",(now_iso(),row["id"]));conn.execute("UPDATE users SET last_login_at=? WHERE id=?",(now_iso(),row["user_id"]))
        token,csrf=create_session(conn,row["user_id"])
    set_session_cookie(response,token)
    return {"ok":True,"user":{"id":row["user_id"],"email":row["email"],"role":row["role"],"plan":row["plan"],"email_verified":bool(row["email_verified_at"]),"two_step_enabled":bool(row["two_step_enabled"]),"subscription_status":row["stripe_subscription_status"]},"csrf_token":csrf}

@app.post("/api/logout")
def logout(request: Request, response: Response, x_csrf_token: Optional[str] = Header(default=None)):
    u = require_user(request)
    require_csrf(request, u, x_csrf_token)
    token = request.cookies.get(COOKIE_NAME)
    if token:
        with db() as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash(token),))
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}

@app.get("/api/me")
def me(request: Request):
    u = session_user(request)
    if not u:
        return {"authenticated": False}
    with db() as conn:
        profile = get_profile(conn, u["id"])
        watch_count = conn.execute("SELECT COUNT(*) c FROM watchlist WHERE user_id=?", (u["id"],)).fetchone()["c"]
        unseen = conn.execute("SELECT COUNT(*) c FROM alert_events WHERE user_id=? AND seen=0", (u["id"],)).fetchone()["c"]
    return {"authenticated": True, "user": {"id":u["id"],"email":u["email"],"role":u["role"],"plan":u["plan"],"email_verified":bool(u.get("email_verified_at")),"two_step_enabled":bool(u.get("two_step_enabled")),"subscription_status":u.get("stripe_subscription_status")}, "profile": profile, "watch_count": watch_count, "unseen_alerts": unseen, "csrf_token": u["csrf_token"]}

@app.put("/api/profile")
def update_profile(payload: ProfileIn, request: Request, x_csrf_token: Optional[str] = Header(default=None)):
    u = require_user(request); require_csrf(request, u, x_csrf_token)
    with db() as conn:
        conn.execute("INSERT INTO user_profiles(user_id,goal,work_mode,startup_budget,urgency_days,experience,location,updated_at) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET goal=excluded.goal,work_mode=excluded.work_mode,startup_budget=excluded.startup_budget,urgency_days=excluded.urgency_days,experience=excluded.experience,location=excluded.location,updated_at=excluded.updated_at",
                     (u["id"], payload.goal, payload.work_mode, payload.startup_budget, payload.urgency_days, payload.experience, payload.location, now_iso()))
    return {"ok": True}

# ---------- opportunity API ----------
@app.get("/api/opportunities")
def opportunities(request: Request, q: str = "", mode: str = "all", trust: str = "all", category: str = "all", include_expired: bool = False):
    u = session_user(request)
    with db() as conn:
        profile = get_profile(conn, u["id"]) if u else {}
        rows = conn.execute("SELECT * FROM opportunities WHERE status!='blocked' ORDER BY updated_at DESC").fetchall()
    out = []
    ql = q.lower().strip()
    for row in rows:
        d = opportunity_to_dict(row, profile)
        if not include_expired and d["verification"]["status"] == "expired": continue
        if mode != "all" and d["mode"] != mode: continue
        if trust != "all" and d["trust"] != trust: continue
        if category != "all" and d["category"] != category: continue
        hay = f"{d['title']} {d['organization']} {d['category']} {' '.join(d['tags'])}".lower()
        if ql and ql not in hay: continue
        out.append(d)
    out.sort(key=lambda x: x["match"], reverse=True)
    return {"count": len(out), "opportunities": out}

@app.get("/api/opportunities/{opportunity_id}")
def opportunity_detail(opportunity_id: str, request: Request):
    u = session_user(request)
    with db() as conn:
        row = conn.execute("SELECT * FROM opportunities WHERE id=?", (opportunity_id,)).fetchone()
        if not row: raise HTTPException(404, "Opportunity not found")
        profile = get_profile(conn, u["id"]) if u else {}
        changes = [dict(r) for r in conn.execute("SELECT * FROM opportunity_changes WHERE opportunity_id=? ORDER BY id DESC LIMIT 20", (opportunity_id,)).fetchall()]
    return {"opportunity": opportunity_to_dict(row, profile), "changes": changes}

@app.get("/api/source-status")
def source_status():
    registry = [
        {"key":"grants_gov","name":"Grants.gov","kind":"Government grants","status":"enabled","auth":"No key required for search2/fetchOpportunity","refresh":"60 min","trust":95,"policy":"Official API; preserve source fidelity and non-endorsement notice."},
        {"key":"usajobs","name":"USAJOBS","kind":"Federal jobs","status":"enabled" if os.getenv("USAJOBS_API_KEY") and os.getenv("USAJOBS_EMAIL") else "credentials","auth":"API key + registered email","refresh":"30 min","trust":95,"policy":"Official API; credentials stay server-side."},
        {"key":"lever_partner","name":"Lever Postings","kind":"Employer job feeds","status":"enabled" if os.getenv("CASHH_LEVER_SITES") else "allowlist","auth":"Public postings for configured employer sites","refresh":"30 min","trust":82,"policy":"Only explicitly configured employer site tokens; canonical links preserved."},
        {"key":"remotive","name":"Remotive","kind":"Remote jobs","status":"license-gated","auth":"Public API restrictions","refresh":"24 hr","trust":78,"policy":"Disabled by default because public API terms restrict some signup-gated redistribution use cases."},
    ]
    with db() as conn:
        runs = [dict(r) for r in conn.execute("SELECT * FROM source_runs WHERE id IN (SELECT MAX(id) FROM source_runs GROUP BY source_key) ORDER BY source_key").fetchall()]
        counts = conn.execute("SELECT COUNT(*) opportunities, SUM(CASE WHEN trust!='demo' THEN 1 ELSE 0 END) source_records FROM opportunities WHERE status!='blocked'").fetchone()
    return {"sources": registry, "runs": runs, "opportunities": counts["opportunities"], "source_records": counts["source_records"] or 0}

# ---------- execution modules ----------
@app.get("/api/watchlist")
def get_watchlist(request: Request):
    u = require_user(request)
    with db() as conn:
        profile = get_profile(conn, u["id"])
        rows = conn.execute("SELECT o.* FROM watchlist w JOIN opportunities o ON o.id=w.opportunity_id WHERE w.user_id=? ORDER BY w.created_at DESC", (u["id"],)).fetchall()
    return {"opportunities": [opportunity_to_dict(r, profile) for r in rows]}

@app.post("/api/watchlist/{opportunity_id}")
def add_watchlist(opportunity_id: str, request: Request, x_csrf_token: Optional[str] = Header(default=None)):
    u = require_user(request); require_csrf(request, u, x_csrf_token)
    with db() as conn:
        if not conn.execute("SELECT 1 FROM opportunities WHERE id=? AND status!='blocked'", (opportunity_id,)).fetchone(): raise HTTPException(404, "Opportunity not found")
        if u.get("plan")=="free" and u.get("role")!="admin":
            count=conn.execute("SELECT COUNT(*) c FROM watchlist WHERE user_id=?",(u["id"],)).fetchone()["c"]
            exists=conn.execute("SELECT 1 FROM watchlist WHERE user_id=? AND opportunity_id=?",(u["id"],opportunity_id)).fetchone()
            if count>=5 and not exists: raise HTTPException(403,"Free plan supports up to 5 saved opportunities. Upgrade to Pro for unlimited saves.")
        conn.execute("INSERT OR IGNORE INTO watchlist(user_id,opportunity_id,created_at) VALUES(?,?,?)", (u["id"], opportunity_id, now_iso()))
    return {"ok": True}

@app.delete("/api/watchlist/{opportunity_id}")
def delete_watchlist(opportunity_id: str, request: Request, x_csrf_token: Optional[str] = Header(default=None)):
    u = require_user(request); require_csrf(request, u, x_csrf_token)
    with db() as conn: conn.execute("DELETE FROM watchlist WHERE user_id=? AND opportunity_id=?", (u["id"], opportunity_id))
    return {"ok": True}

@app.post("/api/advisor")
def advisor(payload: AdvisorIn, request: Request):
    u = session_user(request)
    with db() as conn:
        profile = get_profile(conn, u["id"]) if u else {}
        profile = {**profile, **{k:v for k,v in payload.model_dump().items() if v is not None and k != "limit"}}
        if payload.goal: profile["goal"] = payload.goal
        rows = conn.execute("SELECT * FROM opportunities WHERE status='active'").fetchall()
    ranked = [opportunity_to_dict(r, profile) for r in rows]
    ranked = [o for o in ranked if o["verification"]["status"] not in {"expired","blocked"}]
    ranked.sort(key=lambda x:x["match"], reverse=True)
    picks = []
    for o in ranked[:payload.limit]:
        reasons = []
        if profile.get("work_mode") not in {None,"","any"} and o["mode"] == profile.get("work_mode"): reasons.append(f"matches {o['mode']} work preference")
        if profile.get("startup_budget") is not None and float(o.get("startup_cost") or 0) <= float(profile.get("startup_budget") or 0): reasons.append("fits stated startup budget")
        if o.get("speed_days") and profile.get("urgency_days") and o["speed_days"] <= profile["urgency_days"]: reasons.append("modeled timing fits stated urgency")
        reasons.append(f"evidence state: {o['verification']['status']}")
        picks.append({"id":o["id"],"title":o["title"],"match":o["match"],"why":o["why"],"reasons":reasons,"risks":o["risks"],"verification":o["verification"]})
    return {"goal": profile.get("goal", ""), "recommendations": picks, "disclaimer":"Rankings are decision-support estimates, not guarantees of earnings, acceptance, eligibility, or future availability."}

@app.post("/api/roadmaps")
def create_roadmap(payload: RoadmapIn, request: Request, x_csrf_token: Optional[str] = Header(default=None)):
    u = require_user(request); require_csrf(request, u, x_csrf_token)
    with db() as conn:
        o = conn.execute("SELECT * FROM opportunities WHERE id=?", (payload.opportunity_id,)).fetchone()
        if not o: raise HTTPException(404, "Opportunity not found")
        source_steps = jload(o["steps_json"], [])
        steps = []
        for i, text in enumerate(source_steps or ["Verify the source and eligibility","Prepare required proof or materials","Take the first application/outreach action","Track the response","Review outcome and decide next action"], 1):
            steps.append({"order":i,"title":text,"done":False,"evidence":"Source-derived action" if source_steps else "Generated execution step"})
        cur = conn.execute("INSERT INTO roadmaps(user_id,opportunity_id,title,steps_json,created_at,updated_at) VALUES(?,?,?,?,?,?)", (u["id"], o["id"], f"{o['title']} roadmap", jdump(steps), now_iso(), now_iso()))
        rid = cur.lastrowid
    return {"id": rid, "title": f"{o['title']} roadmap", "steps": steps}

@app.get("/api/roadmaps")
def roadmaps(request: Request):
    u=require_user(request)
    with db() as conn:
        rows=conn.execute("SELECT r.*,o.title opportunity_title FROM roadmaps r JOIN opportunities o ON o.id=r.opportunity_id WHERE r.user_id=? ORDER BY r.id DESC",(u["id"],)).fetchall()
    return {"roadmaps":[{**dict(r),"steps":jload(r["steps_json"],[])} for r in rows]}

@app.post("/api/outreach")
def outreach(payload: OutreachIn, request: Request, x_csrf_token: Optional[str] = Header(default=None)):
    u=require_user(request); require_csrf(request,u,x_csrf_token)
    with db() as conn:
        o=conn.execute("SELECT * FROM opportunities WHERE id=?",(payload.opportunity_id,)).fetchone()
        if not o: raise HTTPException(404,"Opportunity not found")
        title=o["title"]; org=o["organization"] or "your team"
        if payload.asset_type=="application_email":
            content=f"Hello {org} hiring team,\n\nI'm interested in the {title} opportunity. I reviewed the published requirements and would like to be considered. I can provide a role-specific resume and any requested supporting materials.\n\nThank you for your consideration."
        elif payload.asset_type=="proposal":
            content=f"Hello,\n\nI'm reaching out regarding {title}. I would like to confirm the exact scope, deliverables, timeline, eligibility, and compensation terms before proceeding. If there is a fit, I can send a concise plan tied to the stated requirements.\n\nBest,"
        elif payload.asset_type=="dm":
            content=f"Hi — I saw the {title} opportunity from {org}. I'm interested and have reviewed the source details. What is the best next step to be considered?"
        else:
            content=f"Hello,\n\nFollowing up on my interest in {title}. I wanted to confirm whether the opportunity is still active and whether you need anything else from me.\n\nThank you."
        cur=conn.execute("INSERT INTO outreach_assets(user_id,opportunity_id,asset_type,content,created_at) VALUES(?,?,?,?,?)",(u["id"],o["id"],payload.asset_type,content,now_iso()))
    return {"id":cur.lastrowid,"asset_type":payload.asset_type,"content":content,"note":"Template uses only source-supported details; personalize it with truthful qualifications before sending."}

@app.post("/api/alerts")
def create_alert(payload: AlertRuleIn, request: Request, x_csrf_token: Optional[str]=Header(default=None)):
    u=require_user(request); require_csrf(request,u,x_csrf_token)
    rule={"kind":payload.kind,"days":payload.days}
    with db() as conn:
        cur=conn.execute("INSERT INTO alert_rules(user_id,name,rule_json,enabled,created_at,updated_at) VALUES(?,?,?,?,?,?)",(u["id"],payload.name,jdump(rule),1 if payload.enabled else 0,now_iso(),now_iso()))
    return {"id":cur.lastrowid,"name":payload.name,"rule":rule,"enabled":payload.enabled}

@app.get("/api/alerts")
def alerts(request: Request):
    u=require_user(request)
    with db() as conn:
        rules=[{**dict(r),"rule":jload(r["rule_json"],{})} for r in conn.execute("SELECT * FROM alert_rules WHERE user_id=? ORDER BY id DESC",(u["id"],)).fetchall()]
        events=[dict(r) for r in conn.execute("SELECT e.*,o.title opportunity_title FROM alert_events e LEFT JOIN opportunities o ON o.id=e.opportunity_id WHERE e.user_id=? ORDER BY e.id DESC LIMIT 100",(u["id"],)).fetchall()]
    return {"rules":rules,"events":events}

def evaluate_alerts_for_user(conn: sqlite3.Connection, user_id: int) -> int:
    made=0;now=datetime.now(timezone.utc);profile=get_profile(conn,user_id)
    rules=conn.execute("SELECT * FROM alert_rules WHERE user_id=? AND enabled=1",(user_id,)).fetchall()
    saved=conn.execute("SELECT o.* FROM watchlist w JOIN opportunities o ON o.id=w.opportunity_id WHERE w.user_id=?",(user_id,)).fetchall()
    for rule in rules:
        rj=jload(rule["rule_json"],{});kind=rj.get("kind");days=int(rj.get("days",3))
        if kind=="deadline":
            for o in saved:
                close=parse_dt(o["closes_at"])
                if close and now <= close <= now+timedelta(days=days):
                    exists=conn.execute("SELECT 1 FROM alert_events WHERE user_id=? AND opportunity_id=? AND rule_id=? AND kind='deadline' AND created_at>?",(user_id,o["id"],rule["id"],(now-timedelta(days=1)).isoformat())).fetchone()
                    if not exists:
                        conn.execute("INSERT INTO alert_events(user_id,opportunity_id,rule_id,kind,message,created_at) VALUES(?,?,?,?,?,?)",(user_id,o["id"],rule["id"],"deadline",f"{o['title']} closes within {days} day(s).",now_iso()));made+=1
        elif kind=="material_change":
            for o in saved:
                changed=conn.execute("SELECT 1 FROM opportunity_changes WHERE opportunity_id=? AND detected_at>=?",(o["id"],(now-timedelta(days=days)).isoformat())).fetchone()
                exists=conn.execute("SELECT 1 FROM alert_events WHERE user_id=? AND opportunity_id=? AND rule_id=? AND kind='material_change' AND created_at>=?",(user_id,o["id"],rule["id"],(now-timedelta(days=days)).isoformat())).fetchone()
                if changed and not exists:
                    conn.execute("INSERT INTO alert_events(user_id,opportunity_id,rule_id,kind,message,created_at) VALUES(?,?,?,?,?,?)",(user_id,o["id"],rule["id"],"material_change",f"{o['title']} changed at its source. Review the updated evidence.",now_iso()));made+=1
        elif kind=="new_match":
            rows=conn.execute("SELECT * FROM opportunities WHERE status!='blocked' AND first_seen>=?",((now-timedelta(days=days)).isoformat(),)).fetchall()
            for o in rows:
                od=opportunity_to_dict(o,profile)
                if od["match"]<80 or od["verification"]["status"] in {"expired","blocked"}: continue
                exists=conn.execute("SELECT 1 FROM alert_events WHERE user_id=? AND opportunity_id=? AND rule_id=? AND kind='new_match'",(user_id,o["id"],rule["id"])).fetchone()
                if not exists:
                    conn.execute("INSERT INTO alert_events(user_id,opportunity_id,rule_id,kind,message,created_at) VALUES(?,?,?,?,?,?)",(user_id,o["id"],rule["id"],"new_match",f"New high-match opportunity: {o['title']} ({od['match']}/100).",now_iso()));made+=1
    searches=conn.execute("SELECT * FROM saved_searches WHERE user_id=? AND enabled=1",(user_id,)).fetchall();opps=_all_user_opportunities(conn,user_id)
    for search in searches:
        since=parse_dt(search["last_evaluated_at"]) or parse_dt(search["created_at"]) or (now-timedelta(days=1))
        q=jload(search["query_json"],{})
        for o in opps:
            first=parse_dt(o.get("first_seen"))
            if first and first>since and _search_match(o,q):
                exists=conn.execute("SELECT 1 FROM alert_events WHERE user_id=? AND opportunity_id=? AND kind='saved_search_match' AND message LIKE ?",(user_id,o["id"],f"%{search['name']}%" )).fetchone()
                if not exists:
                    conn.execute("INSERT INTO alert_events(user_id,opportunity_id,kind,message,created_at) VALUES(?,?,?,?,?)",(user_id,o["id"],"saved_search_match",f"Saved search '{search['name']}' matched: {o['title']}.",now_iso()));made+=1
        conn.execute("UPDATE saved_searches SET last_evaluated_at=?,updated_at=? WHERE id=?",(now_iso(),now_iso(),search["id"]))
    return made

@app.delete("/api/alerts/{rule_id}")
def delete_alert_rule(rule_id:int,request:Request,x_csrf_token:Optional[str]=Header(default=None)):
    u=require_user(request);require_csrf(request,u,x_csrf_token)
    with db() as conn: conn.execute("DELETE FROM alert_rules WHERE id=? AND user_id=?",(rule_id,u["id"]))
    return {"ok":True}

@app.post("/api/alerts/evaluate")
def evaluate_alerts(request: Request, x_csrf_token: Optional[str]=Header(default=None)):
    u=require_user(request); require_csrf(request,u,x_csrf_token)
    with db() as conn: made=evaluate_alerts_for_user(conn,u["id"])
    return {"created":made}

@app.post("/api/outcomes")
def create_outcome(payload: OutcomeIn, request: Request, x_csrf_token: Optional[str]=Header(default=None)):
    u=require_user(request); require_csrf(request,u,x_csrf_token)
    when=payload.occurred_at or now_iso()
    with db() as conn:
        if not conn.execute("SELECT 1 FROM opportunities WHERE id=?",(payload.opportunity_id,)).fetchone(): raise HTTPException(404,"Opportunity not found")
        cur=conn.execute("INSERT INTO outcomes(user_id,opportunity_id,stage,notes,amount,occurred_at,created_at) VALUES(?,?,?,?,?,?,?)",(u["id"],payload.opportunity_id,payload.stage,payload.notes,payload.amount,when,now_iso()))
    return {"id":cur.lastrowid,"ok":True}

@app.get("/api/outcomes")
def outcomes(request: Request):
    u=require_user(request)
    with db() as conn:
        rows=[dict(r) for r in conn.execute("SELECT x.*,o.title opportunity_title FROM outcomes x JOIN opportunities o ON o.id=x.opportunity_id WHERE x.user_id=? ORDER BY x.occurred_at DESC,x.id DESC",(u["id"],)).fetchall()]
        summary={r["stage"]:0 for r in rows}
        for r in rows: summary[r["stage"]]=summary.get(r["stage"],0)+1
    return {"outcomes":rows,"summary":summary}

# ---------- analytics ----------
@app.post("/api/events")
def analytics_event(payload: EventIn, request: Request):
    u=session_user(request)
    safe_meta={str(k)[:50]:str(v)[:300] for k,v in payload.metadata.items() if k not in {"email","password","phone","address"}}
    with db() as conn: conn.execute("INSERT INTO analytics_events(user_id,event_name,metadata_json,created_at) VALUES(?,?,?,?)",(u["id"] if u else None,payload.event_name,jdump(safe_meta),now_iso()))
    return {"ok":True}

# ---------- live source ingestion ----------
def normalize_grants(keyword: str="") -> list[dict[str, Any]]:
    resp=requests.post("https://api.grants.gov/v1/api/search2",json={"rows":25,"keyword":keyword,"oppStatuses":"posted|forecasted"},timeout=15)
    resp.raise_for_status(); data=resp.json().get("data",{})
    out=[]
    for x in data.get("oppHits",[]):
        rid=str(x.get("id")); title=x.get("title") or "Untitled grant"; close=x.get("closeDate")
        close_iso=None
        if close:
            try: close_iso=datetime.strptime(close,"%m/%d/%Y").replace(tzinfo=timezone.utc).isoformat()
            except Exception: pass
        out.append(dict(id=f"grants-{rid}",source_key="grants_gov",source_record_id=rid,title=title,organization=x.get("agencyName") or x.get("agencyCode") or "Federal agency",category="Grant / Funding",mode="organization",experience="experienced",trust="source",base_match=50,speed_days=None,income_min=None,income_max=None,income_period="award",income_label="Funding",income_is_estimate=0,startup_cost=0,durability=60,competition=80,tags=["Grant",x.get("oppStatus","posted")],source_name=f"Grants.gov / {x.get('agencyName') or x.get('agencyCode') or 'Federal agency'}",source_url=f"https://www.grants.gov/search-results-detail/{rid}",first_seen=now_iso(),last_seen=now_iso(),closes_at=close_iso,why="Current opportunity discovered through the official Grants.gov search API.",risks="Confirm full notice, eligibility, allowable costs and award terms on Grants.gov. Funding is competitive and not guaranteed.",eligibility="Confirm applicant eligibility in the complete official notice.",steps=["Open the official Grants.gov record","Read the full notice","Confirm eligibility","Prepare a compliance checklist","Submit through the required federal workflow"],evidence={"source":"Grants.gov API","captured_at":now_iso(),"api_status":x.get("oppStatus")}))
    return out


def normalize_usajobs(keyword: str="remote") -> list[dict[str, Any]]:
    key=os.getenv("USAJOBS_API_KEY"); email=os.getenv("USAJOBS_EMAIL")
    if not key or not email: raise RuntimeError("USAJOBS_API_KEY and USAJOBS_EMAIL are required")
    headers={"Host":"data.usajobs.gov","User-Agent":email,"Authorization-Key":key}
    params={"Keyword":keyword or "remote","WhoMayApply":"Public","ResultsPerPage":25,"Fields":"Full"}
    resp=requests.get("https://data.usajobs.gov/api/search",headers=headers,params=params,timeout=15); resp.raise_for_status()
    items=resp.json().get("SearchResult",{}).get("SearchResultItems",[]); out=[]
    for item in items:
        d=item.get("MatchedObjectDescriptor",{}); rid=str(item.get("MatchedObjectId") or d.get("PositionID") or hashlib.sha1((d.get("PositionURI") or "").encode()).hexdigest()[:16])
        rem=d.get("PositionRemuneration") or []
        r0=rem[0] if rem else {}
        try: imin=float(r0.get("MinimumRange")) if r0.get("MinimumRange") else None
        except Exception: imin=None
        try: imax=float(r0.get("MaximumRange")) if r0.get("MaximumRange") else None
        except Exception: imax=None
        close=d.get("PositionEndDate")
        out.append(dict(id=f"usajobs-{rid}",source_key="usajobs",source_record_id=rid,title=d.get("PositionTitle") or "Federal position",organization=d.get("OrganizationName") or d.get("DepartmentName") or "U.S. Government",category="Federal Employment",mode="hybrid",experience="entry",trust="source",base_match=65,speed_days=None,income_min=imin,income_max=imax,income_period=(r0.get("RateIntervalCode") or "year").lower(),income_label="Published salary",income_is_estimate=0,startup_cost=0,durability=78,competition=70,tags=["Federal","Public hiring"],source_name=f"USAJOBS / {d.get('OrganizationName') or 'U.S. Government'}",source_url=d.get("PositionURI"),first_seen=now_iso(),last_seen=now_iso(),closes_at=close,why="Current federal opportunity discovered through the official USAJOBS Search API.",risks="Federal hiring requirements, duty-station rules and qualification criteria apply; verify the complete announcement.",eligibility="Search was limited to public hiring, but each announcement controls actual eligibility.",steps=["Open the canonical USAJOBS record","Check duty station and eligibility","Match qualifications","Prepare required federal documents","Apply before closing"],evidence={"source":"USAJOBS API","captured_at":now_iso(),"position_id":d.get("PositionID")}))
    return out


def normalize_lever() -> list[dict[str, Any]]:
    sites=[s.strip() for s in os.getenv("CASHH_LEVER_SITES","").split(",") if s.strip()]
    if not sites: raise RuntimeError("CASHH_LEVER_SITES is empty")
    out=[]
    for site in sites:
        resp=requests.get(f"https://api.lever.co/v0/postings/{site}",params={"mode":"json"},timeout=15); resp.raise_for_status()
        for x in resp.json()[:50]:
            rid=str(x.get("id")); cats=x.get("categories") or {}; loc=cats.get("location") or ""; workplace=x.get("workplaceType") or ""
            mode="remote" if "remote" in f"{loc} {workplace}".lower() else "hybrid"
            out.append(dict(id=f"lever-{site}-{rid}",source_key="lever_partner",source_record_id=f"{site}:{rid}",title=x.get("text") or "Job posting",organization=site,category="Employment",mode=mode,experience="entry",trust="source",base_match=65,speed_days=None,income_min=None,income_max=None,income_period="year",income_label="Compensation not supplied",income_is_estimate=0,startup_cost=0,durability=70,competition=70,tags=["Lever",loc] if loc else ["Lever"],source_name=f"Lever / {site}",source_url=x.get("hostedUrl"),first_seen=now_iso(),last_seen=now_iso(),closes_at=None,why="Current employer posting from a configured Lever job site.",risks="Confirm compensation, location, eligibility and application terms on the employer's canonical posting.",eligibility="See the employer posting.",steps=["Open the canonical employer posting","Confirm location and requirements","Tailor application materials","Apply through the employer flow","Track follow-up"],evidence={"source":"Lever Postings API","captured_at":now_iso(),"site":site}))
    return out

@app.post("/api/admin/sources/{source_key}/refresh")
def refresh_source(source_key: str, request: Request, keyword: str = "", x_csrf_token: Optional[str]=Header(default=None)):
    u=require_admin(request); require_csrf(request,u,x_csrf_token)
    started=now_iso()
    with db() as conn:
        run_id=conn.execute("INSERT INTO source_runs(source_key,status,started_at) VALUES(?,?,?)",(source_key,"running",started)).lastrowid
    try:
        if source_key=="grants_gov": records=normalize_grants(keyword)
        elif source_key=="usajobs": records=normalize_usajobs(keyword or "remote")
        elif source_key=="lever_partner": records=normalize_lever()
        else: raise HTTPException(400,"Source is disabled or unsupported")
        normalized=0
        with db() as conn:
            for o in records: upsert_opportunity(conn,o,u["id"]); normalized+=1
            conn.execute("UPDATE source_runs SET status='success',fetched_count=?,normalized_count=?,finished_at=? WHERE id=?",(len(records),normalized,now_iso(),run_id))
            audit(conn,u["id"],"refresh", "source", source_key, {"fetched":len(records),"normalized":normalized})
        return {"ok":True,"fetched":len(records),"normalized":normalized}
    except HTTPException:
        raise
    except Exception as e:
        with db() as conn: conn.execute("UPDATE source_runs SET status='error',error=?,finished_at=? WHERE id=?",(str(e)[:500],now_iso(),run_id))
        raise HTTPException(502,f"Source refresh failed: {str(e)[:200]}")

# ---------- billing ----------
PLANS={
    "free":{"name":"Free","price_monthly":0,"features":["Opportunity Radar","Evidence labels","5 saved opportunities"]},
    "pro":{"name":"Pro","price_monthly":19,"features":["Unlimited saves","Advisor + Roadmaps","Alerts","Outreach Studio","Outcome analytics"]},
    "team":{"name":"Team","price_monthly":49,"features":["Everything in Pro","Team workflows","Admin exports","Priority source controls"]},
}

@app.get("/api/plans")
def plans(): return {"plans":PLANS}

@app.post("/api/billing/checkout")
def billing_checkout(payload: CheckoutIn, request: Request, x_csrf_token: Optional[str]=Header(default=None)):
    u=require_user(request); require_csrf(request,u,x_csrf_token)
    secret=os.getenv("STRIPE_SECRET_KEY")
    price=os.getenv("STRIPE_PRICE_PRO" if payload.plan=="pro" else "STRIPE_PRICE_TEAM")
    if not secret or not price:
        raise HTTPException(503,"Billing is configured in the app but Stripe credentials/price IDs have not been supplied by the site owner.")
    form={"mode":"subscription","success_url":f"{PUBLIC_URL}/?billing=success","cancel_url":f"{PUBLIC_URL}/?billing=cancelled","line_items[0][price]":price,"line_items[0][quantity]":"1","client_reference_id":str(u["id"]),"customer_email":u["email"],"metadata[user_id]":str(u["id"]),"metadata[plan]":payload.plan,"subscription_data[metadata][user_id]":str(u["id"]),"subscription_data[metadata][plan]":payload.plan}
    r=requests.post("https://api.stripe.com/v1/checkout/sessions",data=form,auth=(secret,""),timeout=15)
    if not r.ok: raise HTTPException(502,"Billing provider rejected checkout creation")
    data=r.json()
    with db() as conn: conn.execute("INSERT INTO billing_events(user_id,provider,external_id,event_type,payload_json,created_at) VALUES(?,?,?,?,?,?)",(u["id"],"stripe",data.get("id"),"checkout_created",jdump({"plan":payload.plan}),now_iso()))
    return {"checkout_url":data.get("url")}

@app.post("/api/billing/webhook")
async def stripe_webhook(request: Request):
    secret=os.getenv("STRIPE_WEBHOOK_SECRET")
    if not secret: raise HTTPException(503,"Webhook secret not configured")
    raw=await request.body(); sig=request.headers.get("stripe-signature","")
    parts=dict(p.split("=",1) for p in sig.split(",") if "=" in p)
    ts=parts.get("t"); v1=parts.get("v1")
    if not ts or not v1: raise HTTPException(400,"Invalid signature header")
    expected=hmac.new(secret.encode(), f"{ts}.".encode()+raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected,v1) or abs(time.time()-int(ts))>300: raise HTTPException(400,"Invalid webhook signature")
    event=json.loads(raw.decode())
    event_id=event.get("id");event_type=event.get("type") or "unknown"
    if event_id:
        with db() as conn:
            if conn.execute("SELECT 1 FROM billing_events WHERE provider='stripe' AND external_id=? AND event_type=?",(event_id,event_type)).fetchone():
                return {"received":True,"duplicate":True}
    obj=event.get("data",{}).get("object",{}) or {}
    if event_type=="checkout.session.completed":
        meta=obj.get("metadata") or {}; uid=meta.get("user_id"); plan=meta.get("plan")
        if uid and plan in {"pro","team"}:
            with db() as conn:
                conn.execute("UPDATE users SET plan=?,stripe_customer_id=COALESCE(?,stripe_customer_id),stripe_subscription_id=COALESCE(?,stripe_subscription_id),stripe_subscription_status='active' WHERE id=?",(plan,obj.get("customer"),obj.get("subscription"),int(uid)))
                conn.execute("INSERT INTO billing_events(user_id,provider,external_id,event_type,payload_json,created_at) VALUES(?,?,?,?,?,?)",(int(uid),"stripe",event_id,event_type,jdump({"plan":plan,"customer":obj.get("customer"),"subscription":obj.get("subscription")}),now_iso()))
                ref=conn.execute("SELECT referral_code_id FROM referral_events WHERE referred_user_id=? AND event_type='signup' ORDER BY id DESC LIMIT 1",(int(uid),)).fetchone()
                if ref and not conn.execute("SELECT 1 FROM referral_events WHERE referral_code_id=? AND referred_user_id=? AND event_type='conversion'",(ref["referral_code_id"],int(uid))).fetchone():
                    conn.execute("INSERT INTO referral_events(referral_code_id,event_type,referred_user_id,metadata_json,created_at) VALUES(?,?,?,?,?)",(ref["referral_code_id"],"conversion",int(uid),jdump({"provider":"stripe","plan":plan}),now_iso()))
    elif event_type in {"customer.subscription.created","customer.subscription.updated","customer.subscription.deleted","customer.subscription.paused","customer.subscription.resumed"}:
        meta=obj.get("metadata") or {}; uid=meta.get("user_id"); plan=meta.get("plan"); sub_id=obj.get("id"); status=str(obj.get("status") or ("canceled" if event_type=="customer.subscription.deleted" else "unknown"))
        with db() as conn:
            if not uid and sub_id:
                row=conn.execute("SELECT id FROM users WHERE stripe_subscription_id=?",(sub_id,)).fetchone();uid=str(row["id"]) if row else None
            if uid:
                paid=status in {"active","trialing"}
                target_plan=plan if paid and plan in {"pro","team"} else (conn.execute("SELECT plan FROM users WHERE id=?",(int(uid),)).fetchone()["plan"] if paid else "free")
                conn.execute("UPDATE users SET plan=?,stripe_customer_id=COALESCE(?,stripe_customer_id),stripe_subscription_id=COALESCE(?,stripe_subscription_id),stripe_subscription_status=? WHERE id=?",(target_plan,obj.get("customer"),sub_id,status,int(uid)))
                conn.execute("INSERT INTO billing_events(user_id,provider,external_id,event_type,payload_json,created_at) VALUES(?,?,?,?,?,?)",(int(uid),"stripe",event_id,event_type,jdump({"plan":target_plan,"status":status,"subscription":sub_id}),now_iso()))
    elif event_id:
        # Keep an auditable record of other signed billing events without changing entitlements.
        with db() as conn:
            conn.execute("INSERT INTO billing_events(user_id,provider,external_id,event_type,payload_json,created_at) VALUES(?,?,?,?,?,?)",(None,"stripe",event_id,event_type,jdump({"object_id":obj.get("id")}),now_iso()))
    return {"received":True}

@app.get("/api/billing/status")
def billing_status(request:Request):
    u=require_user(request)
    return {"plan":u["plan"],"subscription_status":u.get("stripe_subscription_status"),"customer_configured":bool(u.get("stripe_customer_id")),"stripe_configured":bool(os.getenv("STRIPE_SECRET_KEY"))}

@app.post("/api/billing/portal")
def billing_portal(request:Request,x_csrf_token:Optional[str]=Header(default=None)):
    u=require_user(request);require_csrf(request,u,x_csrf_token)
    secret=os.getenv("STRIPE_SECRET_KEY")
    if not secret: raise HTTPException(503,"Stripe billing is not configured")
    customer=u.get("stripe_customer_id")
    if not customer: raise HTTPException(409,"No Stripe customer is linked to this account yet")
    r=requests.post("https://api.stripe.com/v1/billing_portal/sessions",data={"customer":customer,"return_url":f"{PUBLIC_URL}/?billing=portal"},auth=(secret,""),timeout=15)
    if not r.ok: raise HTTPException(502,"Billing portal could not be created. Confirm the Stripe customer portal is enabled.")
    return {"url":r.json().get("url")}

# ---------- admin ----------
@app.get("/api/admin/dashboard")
def admin_dashboard(request: Request):
    require_admin(request)
    with db() as conn:
        metrics={
            "users":conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"],
            "opportunities":conn.execute("SELECT COUNT(*) c FROM opportunities WHERE status!='blocked'").fetchone()["c"],
            "source_records":conn.execute("SELECT COUNT(*) c FROM opportunities WHERE trust!='demo' AND status!='blocked'").fetchone()["c"],
            "watchlist_saves":conn.execute("SELECT COUNT(*) c FROM watchlist").fetchone()["c"],
            "outcomes":conn.execute("SELECT COUNT(*) c FROM outcomes").fetchone()["c"],
            "events_7d":conn.execute("SELECT COUNT(*) c FROM analytics_events WHERE created_at>=?",((datetime.now(timezone.utc)-timedelta(days=7)).isoformat(),)).fetchone()["c"],
        }
        stages=[dict(r) for r in conn.execute("SELECT stage,COUNT(*) count FROM outcomes GROUP BY stage ORDER BY count DESC").fetchall()]
        sources=[dict(r) for r in conn.execute("SELECT * FROM source_runs ORDER BY id DESC LIMIT 20").fetchall()]
        recent=[dict(r) for r in conn.execute("SELECT * FROM admin_audit ORDER BY id DESC LIMIT 50").fetchall()]
    return {"metrics":metrics,"outcome_stages":stages,"source_runs":sources,"audit":recent}

@app.post("/api/admin/opportunities")
def admin_upsert(payload: AdminOpportunityIn, request: Request, x_csrf_token: Optional[str]=Header(default=None)):
    u=require_admin(request); require_csrf(request,u,x_csrf_token)
    o=payload.model_dump(); o["first_seen"]=now_iso(); o["last_seen"]=now_iso(); o["source_record_id"]=o.get("source_record_id") or o["id"]; o["income_is_estimate"]=1 if o.get("trust")=="demo" else 0
    with db() as conn:
        created,changed=upsert_opportunity(conn,o,u["id"])
    return {"ok":True,"created":created,"changed":changed}

@app.post("/api/admin/opportunities/{opportunity_id}/verify")
def admin_verify(opportunity_id: str, request: Request, x_csrf_token: Optional[str]=Header(default=None)):
    u=require_admin(request); require_csrf(request,u,x_csrf_token)
    with db() as conn:
        row=conn.execute("SELECT * FROM opportunities WHERE id=?",(opportunity_id,)).fetchone()
        if not row: raise HTTPException(404,"Opportunity not found")
        if row["trust"]=="demo": raise HTTPException(400,"Illustrative records cannot be marked verified")
        conn.execute("UPDATE opportunities SET manual_verified_at=?,manual_verified_by=?,updated_at=? WHERE id=?",(now_iso(),u["id"],now_iso(),opportunity_id))
        audit(conn,u["id"],"verify","opportunity",opportunity_id,{"source_url":row["source_url"]})
    return {"ok":True,"status":"verified"}

@app.post("/api/admin/opportunities/{opportunity_id}/block")
def admin_block(opportunity_id: str, request: Request, x_csrf_token: Optional[str]=Header(default=None)):
    u=require_admin(request); require_csrf(request,u,x_csrf_token)
    with db() as conn:
        conn.execute("UPDATE opportunities SET status='blocked',updated_at=? WHERE id=?",(now_iso(),opportunity_id)); audit(conn,u["id"],"block","opportunity",opportunity_id,{})
    return {"ok":True}

@app.get("/api/admin/opportunities")
def admin_opportunities(request: Request):
    require_admin(request)
    with db() as conn: rows=conn.execute("SELECT * FROM opportunities ORDER BY updated_at DESC").fetchall()
    return {"opportunities":[opportunity_to_dict(r,{}) for r in rows]}


def smtp_configured() -> bool:
    return bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_FROM"))

def send_email(to_email:str,subject:str,body:str) -> tuple[bool,str]:
    if not smtp_configured(): return False,"SMTP not configured"
    host=os.getenv("SMTP_HOST");port=int(os.getenv("SMTP_PORT","587"));user=os.getenv("SMTP_USER");password=os.getenv("SMTP_PASSWORD");use_tls=os.getenv("SMTP_TLS","1")=="1"
    msg=EmailMessage();msg["From"]=os.getenv("SMTP_FROM");msg["To"]=to_email;msg["Subject"]=subject;msg.set_content(body)
    try:
        with smtplib.SMTP(host,port,timeout=15) as client:
            if use_tls: client.starttls()
            if user: client.login(user,password or "")
            client.send_message(msg)
        return True,"sent"
    except Exception as e: return False,str(e)[:300]

# ---------- growth, pulse, privacy, API, enterprise ----------

def _search_match(o: dict[str, Any], q: dict[str, Any]) -> bool:
    text=(q.get("text") or "").strip().lower()
    hay=f"{o.get('title','')} {o.get('organization','')} {o.get('category','')} {' '.join(o.get('tags') or [])}".lower()
    if text and not all(tok in hay for tok in re.findall(r"[a-z0-9]+", text) if len(tok)>1): return False
    if q.get("mode") not in {None,"","all"} and o.get("mode") != q.get("mode"): return False
    if q.get("category") not in {None,"","all"} and o.get("category") != q.get("category"): return False
    if int(o.get("match") or 0) < int(q.get("min_match") or 0): return False
    msc=q.get("max_startup_cost")
    if msc is not None and float(o.get("startup_cost") or 0)>float(msc): return False
    cwd=q.get("closing_within_days")
    if cwd and o.get("closes_at"):
        dt=parse_dt(o.get("closes_at")); now=datetime.now(timezone.utc)
        if not dt or dt < now or dt > now+timedelta(days=int(cwd)): return False
    elif cwd: return False
    return True

def _all_user_opportunities(conn: sqlite3.Connection, user_id: int) -> list[dict[str, Any]]:
    profile=get_profile(conn,user_id)
    rows=conn.execute("SELECT * FROM opportunities WHERE status!='blocked' ORDER BY updated_at DESC").fetchall()
    return [opportunity_to_dict(r,profile) for r in rows]

def _require_api_key(x_api_key: Optional[str]) -> tuple[dict[str,Any],dict[str,Any]]:
    if not x_api_key: raise HTTPException(401,"X-API-Key required")
    kh=token_hash(x_api_key)
    with db() as conn:
        row=conn.execute("SELECT k.*,u.email,u.plan,u.is_active,u.role platform_role FROM api_keys k JOIN users u ON u.id=k.user_id WHERE k.key_hash=? AND k.revoked_at IS NULL",(kh,)).fetchone()
        if not row or not row["is_active"]: raise HTTPException(401,"Invalid API key")
        if row["organization_id"] is not None and row["platform_role"]!="admin" and not conn.execute("SELECT 1 FROM organization_members WHERE organization_id=? AND user_id=?",(row["organization_id"],row["user_id"])).fetchone(): raise HTTPException(401,"Organization API key owner is no longer a member")
        conn.execute("UPDATE api_keys SET last_used_at=? WHERE id=?",(now_iso(),row["id"]))
        return dict(row), jload(row["scopes_json"],[])

@app.post("/api/account/password-reset/request")
def password_reset_request(payload:PasswordResetRequestIn,request:Request):
    rate_limit(request,"password-reset",limit=5,window=3600)
    response={"ok":True,"message":"If that account exists, reset instructions were created."}
    with db() as conn:
        user=conn.execute("SELECT id,email FROM users WHERE email=? COLLATE NOCASE AND is_active=1",(payload.email.lower().strip(),)).fetchone()
        if not user: return response
        raw=secrets.token_urlsafe(40);expires=(datetime.now(timezone.utc)+timedelta(minutes=30)).replace(microsecond=0).isoformat()
        conn.execute("DELETE FROM password_reset_tokens WHERE user_id=? AND used_at IS NULL",(user["id"],));conn.execute("INSERT INTO password_reset_tokens(user_id,token_hash,expires_at,created_at) VALUES(?,?,?,?)",(user["id"],token_hash(raw),expires,now_iso()))
        url=f"{PUBLIC_URL}/?reset_token={raw}";ok,info=send_email(user["email"],"Reset your Cashh Radar password",f"A password reset was requested for your Cashh Radar account.\n\nReset link: {url}\n\nThis link expires in 30 minutes. If you did not request this, ignore this message.")
        audit(conn,user["id"],"password_reset_requested","user",str(user["id"]),{"email_delivery":ok,"delivery_info":info})
        if DEV_MODE: response["dev_reset_token"]=raw
    return response

@app.post("/api/account/password-reset/confirm")
def password_reset_confirm(payload:PasswordResetConfirmIn):
    th=token_hash(payload.token);now=datetime.now(timezone.utc)
    with db() as conn:
        row=conn.execute("SELECT * FROM password_reset_tokens WHERE token_hash=? AND used_at IS NULL",(th,)).fetchone()
        if not row or not parse_dt(row["expires_at"]) or parse_dt(row["expires_at"])<now: raise HTTPException(400,"Reset token is invalid or expired")
        conn.execute("UPDATE users SET password_hash=? WHERE id=?",(hash_password(payload.new_password),row["user_id"]));conn.execute("UPDATE password_reset_tokens SET used_at=? WHERE id=?",(now_iso(),row["id"]));conn.execute("DELETE FROM sessions WHERE user_id=?",(row["user_id"],));audit(conn,row["user_id"],"password_reset_completed","user",str(row["user_id"]),{})
    return {"ok":True}

@app.post("/api/account/email-verification/request")
def email_verification_request(payload:EmailVerificationRequestIn,request:Request):
    rate_limit(request,"email-verification",5,3600);out={"ok":True,"message":"If that account exists, verification instructions were created."}
    with db() as conn:
        user=conn.execute("SELECT id,email,email_verified_at FROM users WHERE email=? COLLATE NOCASE AND is_active=1",(payload.email.lower().strip(),)).fetchone()
        if not user or user["email_verified_at"]: return out
        info=_issue_email_verification(conn,user["id"],user["email"])
        if DEV_MODE and info.get("dev_token"): out["dev_verification_token"]=info["dev_token"]
    return out

@app.post("/api/account/email-verification/confirm")
def email_verification_confirm(payload:EmailVerificationConfirmIn):
    now=datetime.now(timezone.utc)
    with db() as conn:
        row=conn.execute("SELECT * FROM email_verification_tokens WHERE token_hash=? AND used_at IS NULL",(token_hash(payload.token),)).fetchone()
        if not row or not parse_dt(row["expires_at"]) or parse_dt(row["expires_at"])<now: raise HTTPException(400,"Verification token is invalid or expired")
        conn.execute("UPDATE users SET email_verified_at=? WHERE id=?",(now_iso(),row["user_id"]));conn.execute("UPDATE email_verification_tokens SET used_at=? WHERE id=?",(now_iso(),row["id"]))
    return {"ok":True,"email_verified":True}

@app.get("/api/account/security")
def account_security(request:Request):
    u=require_user(request)
    return {"email_verified":bool(u.get("email_verified_at")),"two_step_enabled":bool(u.get("two_step_enabled")),"email_verification_required":REQUIRE_EMAIL_VERIFICATION,"smtp_configured":smtp_configured()}

@app.put("/api/account/security/two-step")
def account_two_step(payload:TwoStepSettingsIn,request:Request,x_csrf_token:Optional[str]=Header(default=None)):
    u=require_user(request);require_csrf(request,u,x_csrf_token)
    if not verify_password(payload.password,u["password_hash"]): raise HTTPException(400,"Password is incorrect")
    if payload.enabled and not u.get("email_verified_at"): raise HTTPException(400,"Verify your email before enabling two-step login")
    if payload.enabled and not smtp_configured() and not DEV_MODE: raise HTTPException(503,"SMTP must be configured before enabling two-step login")
    with db() as conn: conn.execute("UPDATE users SET two_step_enabled=? WHERE id=?",(1 if payload.enabled else 0,u["id"]))
    return {"ok":True,"two_step_enabled":payload.enabled}

@app.get("/api/saved-searches")
def saved_searches(request: Request):
    u=require_user(request)
    with db() as conn:
        rows=conn.execute("SELECT * FROM saved_searches WHERE user_id=? ORDER BY id DESC",(u["id"],)).fetchall()
    return {"saved_searches":[{**dict(r),"query":jload(r["query_json"],{})} for r in rows]}

@app.post("/api/saved-searches")
def create_saved_search(payload: SavedSearchIn, request: Request, x_csrf_token: Optional[str]=Header(default=None)):
    u=require_user(request);require_csrf(request,u,x_csrf_token);now=now_iso();q=payload.model_dump();name=q.pop("name");enabled=q.pop("enabled")
    with db() as conn:
        sid=conn.execute("INSERT INTO saved_searches(user_id,name,query_json,enabled,created_at,updated_at) VALUES(?,?,?,?,?,?)",(u["id"],name,jdump(q),1 if enabled else 0,now,now)).lastrowid
    return {"ok":True,"id":sid}

@app.delete("/api/saved-searches/{search_id}")
def delete_saved_search(search_id:int,request:Request,x_csrf_token:Optional[str]=Header(default=None)):
    u=require_user(request);require_csrf(request,u,x_csrf_token)
    with db() as conn: conn.execute("DELETE FROM saved_searches WHERE id=? AND user_id=?",(search_id,u["id"]))
    return {"ok":True}

@app.put("/api/digest/preferences")
def digest_preferences(payload:DigestPreferenceIn,request:Request,x_csrf_token:Optional[str]=Header(default=None)):
    u=require_user(request);require_csrf(request,u,x_csrf_token);now=now_iso()
    with db() as conn:
        conn.execute("INSERT INTO digest_preferences(user_id,cadence,enabled,min_match,include_closing_soon,include_changes,updated_at) VALUES(?,?,?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET cadence=excluded.cadence,enabled=excluded.enabled,min_match=excluded.min_match,include_closing_soon=excluded.include_closing_soon,include_changes=excluded.include_changes,updated_at=excluded.updated_at",(u["id"],payload.cadence,1 if payload.enabled else 0,payload.min_match,1 if payload.include_closing_soon else 0,1 if payload.include_changes else 0,now))
    return {"ok":True}

@app.get("/api/pulse")
def pulse(request:Request):
    u=require_user(request);now=datetime.now(timezone.utc)
    with db() as conn:
        opps=_all_user_opportunities(conn,u["id"]); searches=conn.execute("SELECT * FROM saved_searches WHERE user_id=? AND enabled=1 ORDER BY id DESC",(u["id"],)).fetchall()
        changes=[dict(r) for r in conn.execute("SELECT c.*,o.title FROM opportunity_changes c JOIN opportunities o ON o.id=c.opportunity_id WHERE c.detected_at>=? ORDER BY c.id DESC LIMIT 40",((now-timedelta(days=14)).isoformat(),)).fetchall()]
        alerts=[dict(r) for r in conn.execute("SELECT a.*,o.title FROM alert_events a LEFT JOIN opportunities o ON o.id=a.opportunity_id WHERE a.user_id=? ORDER BY a.id DESC LIMIT 40",(u["id"],)).fetchall()]
    closing=[o for o in opps if o.get("closes_at") and parse_dt(o["closes_at"]) and now<=parse_dt(o["closes_at"])<=now+timedelta(days=14)]
    newest=sorted([o for o in opps if parse_dt(o.get("first_seen"))],key=lambda o:parse_dt(o["first_seen"]),reverse=True)[:12]
    matches=[]
    for srow in searches:
        q=jload(srow["query_json"],{}); found=[o for o in opps if _search_match(o,q)][:10]
        matches.append({"id":srow["id"],"name":srow["name"],"count":len(found),"matches":found[:5]})
    return {"generated_at":now_iso(),"newest":newest,"closing_soon":sorted(closing,key=lambda o:o["closes_at"])[:12],"changes":changes,"alerts":alerts,"saved_search_matches":matches}

@app.get("/api/digest")
def digest(request:Request):
    u=require_user(request)
    with db() as conn:
        pref=conn.execute("SELECT * FROM digest_preferences WHERE user_id=?",(u["id"],)).fetchone();opps=_all_user_opportunities(conn,u["id"])
    min_match=(pref["min_match"] if pref else 70); top=sorted([o for o in opps if o["match"]>=min_match and o["verification"]["status"] not in {"expired","blocked"}],key=lambda o:o["match"],reverse=True)[:10]
    return {"generated_at":now_iso(),"cadence":pref["cadence"] if pref else "daily","top_matches":top,"summary":f"{len(top)} current opportunities meet your digest threshold of {min_match}/100."}

@app.get("/api/account/export")
def export_account(request:Request):
    u=require_user(request)
    with db() as conn:
        payload={"exported_at":now_iso(),"account":{k:v for k,v in u.items() if k not in {"password_hash","csrf_token","token_hash"}},"profile":get_profile(conn,u["id"])}
        for name,sql in {"watchlist":"SELECT * FROM watchlist WHERE user_id=?","roadmaps":"SELECT * FROM roadmaps WHERE user_id=?","outreach_assets":"SELECT * FROM outreach_assets WHERE user_id=?","alert_rules":"SELECT * FROM alert_rules WHERE user_id=?","alert_events":"SELECT * FROM alert_events WHERE user_id=?","outcomes":"SELECT * FROM outcomes WHERE user_id=?","saved_searches":"SELECT * FROM saved_searches WHERE user_id=?","billing_events":"SELECT * FROM billing_events WHERE user_id=?"}.items(): payload[name]=[dict(r) for r in conn.execute(sql,(u["id"],)).fetchall()]
    return JSONResponse(payload,headers={"Content-Disposition":"attachment; filename=cashh-radar-data.json"})

@app.post("/api/account/password")
def change_password(payload:PasswordChangeIn,request:Request,x_csrf_token:Optional[str]=Header(default=None)):
    u=require_user(request);require_csrf(request,u,x_csrf_token)
    if not verify_password(payload.current_password,u["password_hash"]): raise HTTPException(400,"Current password is incorrect")
    with db() as conn:
        conn.execute("UPDATE users SET password_hash=? WHERE id=?",(hash_password(payload.new_password),u["id"]));conn.execute("DELETE FROM sessions WHERE user_id=? AND token_hash!=?",(u["id"],token_hash(request.cookies.get(COOKIE_NAME,""))))
    return {"ok":True}

@app.delete("/api/account")
def delete_account(payload:AccountDeleteIn,request:Request,x_csrf_token:Optional[str]=Header(default=None)):
    u=require_user(request);require_csrf(request,u,x_csrf_token)
    if not verify_password(payload.password,u["password_hash"]): raise HTTPException(400,"Password is incorrect")
    with db() as conn:
        owned=conn.execute("SELECT COUNT(*) c FROM organizations WHERE owner_user_id=?",(u["id"],)).fetchone()["c"]
        if owned: raise HTTPException(409,"Transfer or delete your owned Team workspace(s) before deleting your account")
        conn.execute("DELETE FROM users WHERE id=?",(u["id"],))
    resp=JSONResponse({"ok":True});resp.delete_cookie(COOKIE_NAME,path="/");return resp

def _organization_role(conn: sqlite3.Connection, organization_id: int, user_id: int) -> Optional[str]:
    row=conn.execute("SELECT role FROM organization_members WHERE organization_id=? AND user_id=?",(organization_id,user_id)).fetchone()
    return row["role"] if row else None


def _require_org_admin(conn: sqlite3.Connection, organization_id: int, user: dict[str,Any], owner_only: bool=False) -> str:
    if user.get("role")=="admin": return "platform_admin"
    role=_organization_role(conn,organization_id,user["id"])
    allowed={"owner"} if owner_only else {"owner","admin"}
    if role not in allowed: raise HTTPException(403,"Organization admin required")
    return role


@app.get("/api/api-keys")
def list_api_keys(request:Request):
    u=require_user(request)
    with db() as conn: rows=conn.execute("SELECT k.id,k.name,k.key_prefix,k.scopes_json,k.organization_id,k.rate_limit_per_minute,k.last_used_at,k.revoked_at,k.created_at,o.name organization_name FROM api_keys k LEFT JOIN organizations o ON o.id=k.organization_id WHERE k.user_id=? ORDER BY k.id DESC",(u["id"],)).fetchall()
    return {"api_keys":[{**dict(r),"scopes":jload(r["scopes_json"],[])} for r in rows]}

@app.post("/api/api-keys")
def create_api_key(payload:ApiKeyIn,request:Request,x_csrf_token:Optional[str]=Header(default=None)):
    u=require_user(request);require_csrf(request,u,x_csrf_token)
    if u.get("plan") not in {"pro","team"} and u.get("role")!="admin": raise HTTPException(403,"API access requires Pro, Team, or admin")
    allowed_scopes={"opportunities:read","analytics:read","watchlists:read","alerts:read","usage:read"}
    scopes=list(dict.fromkeys(payload.scopes or ["opportunities:read"]))
    if any(x not in allowed_scopes for x in scopes): raise HTTPException(400,"Unsupported API scope")
    raw="cr_"+secrets.token_urlsafe(32);prefix=raw[:12]
    with db() as conn:
        org_id=payload.organization_id
        if org_id is not None:
            if u.get("plan")!="team" and u.get("role")!="admin": raise HTTPException(403,"Organization API keys require Team or admin")
            _require_org_admin(conn,org_id,u)
        rate=API_ORG_RATE_LIMIT if org_id is not None or u.get("plan")=="team" else API_PRO_RATE_LIMIT
        kid=conn.execute("INSERT INTO api_keys(user_id,organization_id,name,key_prefix,key_hash,scopes_json,rate_limit_per_minute,created_at) VALUES(?,?,?,?,?,?,?,?)",(u["id"],org_id,payload.name,prefix,token_hash(raw),jdump(scopes),rate,now_iso())).lastrowid
    return {"id":kid,"api_key":raw,"prefix":prefix,"organization_id":payload.organization_id,"scopes":scopes,"rate_limit_per_minute":rate,"warning":"This key is shown once. Store it securely."}

@app.delete("/api/api-keys/{key_id}")
def revoke_api_key(key_id:int,request:Request,x_csrf_token:Optional[str]=Header(default=None)):
    u=require_user(request);require_csrf(request,u,x_csrf_token)
    with db() as conn: conn.execute("UPDATE api_keys SET revoked_at=? WHERE id=? AND user_id=?",(now_iso(),key_id,u["id"]))
    return {"ok":True}

def _consume_api_quota(conn:sqlite3.Connection,key:dict[str,Any],endpoint:str):
    since=(datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat();limit=int(key.get("rate_limit_per_minute") or (API_ORG_RATE_LIMIT if key.get("organization_id") else API_PRO_RATE_LIMIT))
    if key.get("organization_id") is not None:
        used=conn.execute("SELECT COUNT(*) c FROM api_usage u JOIN api_keys k ON k.id=u.api_key_id WHERE k.organization_id=? AND u.created_at>=?",(key["organization_id"],since)).fetchone()["c"]
    else: used=conn.execute("SELECT COUNT(*) c FROM api_usage WHERE api_key_id=? AND created_at>=?",(key["id"],since)).fetchone()["c"]
    if used>=limit: raise HTTPException(429,"API rate limit exceeded")
    conn.execute("INSERT INTO api_usage(api_key_id,endpoint,status_code,created_at) VALUES(?,?,?,?)",(key["id"],endpoint,200,now_iso()))

@app.get("/api/v1/opportunities")
def public_api_opportunities(x_api_key:Optional[str]=Header(default=None),limit:int=Query(default=50,ge=1,le=100)):
    key,scopes=_require_api_key(x_api_key)
    if "opportunities:read" not in scopes: raise HTTPException(403,"Scope missing")
    with db() as conn:
        _consume_api_quota(conn,key,"/api/v1/opportunities")
        profile=get_profile(conn,key["user_id"]);rows=conn.execute("SELECT * FROM opportunities WHERE status!='blocked' ORDER BY updated_at DESC LIMIT ?",(limit,)).fetchall();data=[opportunity_to_dict(r,profile) for r in rows]
    result={"data":data,"count":len(data),"generated_at":now_iso()}
    if key.get("organization_id"):
        with db() as conn:
            ts=conn.execute("SELECT brand_name,accent_color,logo_url,custom_domain FROM tenant_settings WHERE organization_id=?",(key["organization_id"],)).fetchone()
            if ts: result["tenant"]={"organization_id":key["organization_id"],**dict(ts)}
    return result

@app.get("/api/v1/watchlist")
def public_api_watchlist(x_api_key:Optional[str]=Header(default=None)):
    key,scopes=_require_api_key(x_api_key)
    if "watchlists:read" not in scopes: raise HTTPException(403,"Scope missing")
    with db() as conn:
        _consume_api_quota(conn,key,"/api/v1/watchlist")
        if key.get("organization_id") is not None: rows=conn.execute("SELECT o.* FROM organization_watchlist w JOIN opportunities o ON o.id=w.opportunity_id WHERE w.organization_id=? ORDER BY w.created_at DESC",(key["organization_id"],)).fetchall()
        else: rows=conn.execute("SELECT o.* FROM watchlist w JOIN opportunities o ON o.id=w.opportunity_id WHERE w.user_id=? ORDER BY w.created_at DESC",(key["user_id"],)).fetchall()
    return {"data":[opportunity_to_dict(r,{}) for r in rows],"count":len(rows)}

@app.get("/api/v1/alerts")
def public_api_alerts(x_api_key:Optional[str]=Header(default=None),limit:int=Query(default=50,ge=1,le=100)):
    key,scopes=_require_api_key(x_api_key)
    if "alerts:read" not in scopes: raise HTTPException(403,"Scope missing")
    with db() as conn:
        _consume_api_quota(conn,key,"/api/v1/alerts");rows=conn.execute("SELECT e.*,o.title opportunity_title FROM alert_events e LEFT JOIN opportunities o ON o.id=e.opportunity_id WHERE e.user_id=? ORDER BY e.id DESC LIMIT ?",(key["user_id"],limit)).fetchall()
    return {"data":[dict(r) for r in rows],"count":len(rows)}

@app.get("/api/v1/analytics")
def public_api_analytics(x_api_key:Optional[str]=Header(default=None)):
    key,scopes=_require_api_key(x_api_key)
    if "analytics:read" not in scopes: raise HTTPException(403,"Scope missing")
    with db() as conn:
        _consume_api_quota(conn,key,"/api/v1/analytics");since=(datetime.now(timezone.utc)-timedelta(days=30)).isoformat();events=[dict(r) for r in conn.execute("SELECT event_name,COUNT(*) count FROM analytics_events WHERE user_id=? AND created_at>=? GROUP BY event_name ORDER BY count DESC",(key["user_id"],since)).fetchall()];outcomes=[dict(r) for r in conn.execute("SELECT stage,COUNT(*) count,COALESCE(SUM(amount),0) amount FROM outcomes WHERE user_id=? AND created_at>=? GROUP BY stage",(key["user_id"],since)).fetchall()]
    return {"window_days":30,"events":events,"outcomes":outcomes,"note":"Outcome amounts are user-entered actuals, not guaranteed earnings."}

@app.get("/api/v1/usage")
def public_api_usage(x_api_key:Optional[str]=Header(default=None)):
    key,scopes=_require_api_key(x_api_key)
    if "usage:read" not in scopes: raise HTTPException(403,"Scope missing")
    with db() as conn:
        _consume_api_quota(conn,key,"/api/v1/usage");since=(datetime.now(timezone.utc)-timedelta(days=30)).isoformat();rows=conn.execute("SELECT endpoint,COUNT(*) count FROM api_usage WHERE api_key_id=? AND created_at>=? GROUP BY endpoint ORDER BY count DESC",(key["id"],since)).fetchall()
    return {"window_days":30,"usage":[dict(r) for r in rows]}

@app.get("/api/referral")
def referral_code(request:Request):
    u=require_user(request)
    with db() as conn:
        row=conn.execute("SELECT * FROM referral_codes WHERE user_id=?",(u["id"],)).fetchone()
        if not row:
            code="CR"+secrets.token_hex(5).upper();rid=conn.execute("INSERT INTO referral_codes(user_id,code,created_at) VALUES(?,?,?)",(u["id"],code,now_iso())).lastrowid;row=conn.execute("SELECT * FROM referral_codes WHERE id=?",(rid,)).fetchone()
        counts={r["event_type"]:r["c"] for r in conn.execute("SELECT event_type,COUNT(*) c FROM referral_events WHERE referral_code_id=? GROUP BY event_type",(row["id"],)).fetchall()}
    return {"code":row["code"],"share_url":f"{PUBLIC_URL}/?ref={row['code']}","events":counts,"disclosure":"Referral rewards, if enabled, must be disclosed and never change opportunity rankings."}

@app.post("/api/referral/event")
def record_referral(payload:ReferralEventIn):
    if payload.event_type!="visit": raise HTTPException(403,"Signup and conversion referral events are server-verified")
    with db() as conn:
        row=conn.execute("SELECT id FROM referral_codes WHERE code=? AND active=1",(payload.code,)).fetchone()
        if not row: raise HTTPException(404,"Referral code not found")
        conn.execute("INSERT INTO referral_events(referral_code_id,event_type,metadata_json,created_at) VALUES(?,?,?,?)",(row["id"],"visit",jdump(payload.metadata),now_iso()))
    return {"ok":True}

@app.get("/api/providers")
def providers():
    with db() as conn: rows=conn.execute("SELECT id,name,category,website,disclosure,status FROM providers WHERE status='active' ORDER BY name").fetchall()
    return {"providers":[dict(r) for r in rows],"disclosure":"Provider placement does not affect Cashh Radar opportunity scores unless explicitly stated and disclosed."}

@app.post("/api/provider-leads")
def provider_lead(payload:ProviderLeadIn,request:Request,x_csrf_token:Optional[str]=Header(default=None)):
    u=require_user(request);require_csrf(request,u,x_csrf_token)
    with db() as conn:
        p=conn.execute("SELECT id FROM providers WHERE id=? AND status='active'",(payload.provider_id,)).fetchone()
        if not p: raise HTTPException(404,"Provider unavailable")
        lid=conn.execute("INSERT INTO provider_leads(user_id,provider_id,opportunity_id,note,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",(u["id"],payload.provider_id,payload.opportunity_id,payload.note,"requested",now_iso(),now_iso())).lastrowid
    return {"ok":True,"lead_id":lid,"status":"requested"}

@app.get("/api/provider-leads")
def provider_leads_for_user(request:Request):
    u=require_user(request)
    with db() as conn:
        rows=conn.execute("SELECT l.*,p.name provider_name,p.category provider_category FROM provider_leads l JOIN providers p ON p.id=l.provider_id WHERE l.user_id=? ORDER BY l.id DESC",(u["id"],)).fetchall()
    return {"provider_leads":[dict(r) for r in rows]}

@app.put("/api/admin/provider-leads/{lead_id}")
def admin_update_provider_lead(lead_id:int,payload:ProviderLeadStatusIn,request:Request,x_csrf_token:Optional[str]=Header(default=None)):
    u=require_admin(request);require_csrf(request,u,x_csrf_token)
    with db() as conn:
        row=conn.execute("SELECT * FROM provider_leads WHERE id=?",(lead_id,)).fetchone()
        if not row: raise HTTPException(404,"Provider lead not found")
        closed_at=now_iso() if payload.status in {"closed_won","closed_lost"} else None
        conn.execute("UPDATE provider_leads SET status=?,admin_note=?,assigned_to=?,closed_at=?,updated_at=? WHERE id=?",(payload.status,payload.admin_note,u["id"],closed_at,now_iso(),lead_id))
        audit(conn,u["id"],"provider_lead_status","provider_lead",str(lead_id),{"status":payload.status})
    return {"ok":True,"status":payload.status}

@app.get("/api/admin/providers/analytics")
def admin_provider_analytics(request:Request):
    require_admin(request)
    with db() as conn:
        by_status=[dict(r) for r in conn.execute("SELECT status,COUNT(*) count FROM provider_leads GROUP BY status ORDER BY count DESC").fetchall()]
        by_provider=[dict(r) for r in conn.execute("SELECT p.id,p.name,COUNT(l.id) leads,SUM(CASE WHEN l.status='closed_won' THEN 1 ELSE 0 END) won FROM providers p LEFT JOIN provider_leads l ON l.provider_id=p.id GROUP BY p.id,p.name ORDER BY leads DESC").fetchall()]
    return {"by_status":by_status,"by_provider":by_provider}

@app.post("/api/admin/providers")
def admin_provider(payload:ProviderIn,request:Request,x_csrf_token:Optional[str]=Header(default=None)):
    u=require_admin(request);require_csrf(request,u,x_csrf_token);now=now_iso()
    with db() as conn:
        pid=conn.execute("INSERT INTO providers(name,category,website,disclosure,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",(payload.name,payload.category,payload.website,payload.disclosure,payload.status,now,now)).lastrowid;audit(conn,u["id"],"create","provider",str(pid),payload.model_dump())
    return {"ok":True,"id":pid}

@app.post("/api/organizations")
def create_organization(payload:OrganizationIn,request:Request,x_csrf_token:Optional[str]=Header(default=None)):
    u=require_user(request);require_csrf(request,u,x_csrf_token)
    if u.get("plan")!="team" and u.get("role")!="admin": raise HTTPException(403,"Organization workspaces require Team or admin")
    now=now_iso()
    try:
        with db() as conn:
            oid=conn.execute("INSERT INTO organizations(owner_user_id,name,slug,created_at,updated_at) VALUES(?,?,?,?,?)",(u["id"],payload.name,payload.slug,now,now)).lastrowid;conn.execute("INSERT INTO organization_members(organization_id,user_id,role,created_at) VALUES(?,?,?,?)",(oid,u["id"],"owner",now));conn.execute("INSERT INTO tenant_settings(organization_id,updated_at) VALUES(?,?)",(oid,now))
    except sqlite3.IntegrityError: raise HTTPException(409,"Organization slug already exists")
    return {"ok":True,"organization_id":oid}

@app.get("/api/organizations")
def organizations(request:Request):
    u=require_user(request)
    with db() as conn:
        rows=conn.execute("SELECT o.*,m.role,t.brand_name,t.accent_color,t.logo_url,t.custom_domain,(SELECT COUNT(*) FROM organization_members om WHERE om.organization_id=o.id) member_count FROM organizations o JOIN organization_members m ON m.organization_id=o.id LEFT JOIN tenant_settings t ON t.organization_id=o.id WHERE m.user_id=? ORDER BY o.id DESC",(u["id"],)).fetchall()
    return {"organizations":[dict(r) for r in rows]}

@app.get("/api/organizations/{organization_id}/members")
def organization_members_list(organization_id:int,request:Request):
    u=require_user(request)
    with db() as conn:
        if not _organization_role(conn,organization_id,u["id"]) and u.get("role")!="admin": raise HTTPException(403,"Organization membership required")
        rows=conn.execute("SELECT m.user_id,m.role,m.created_at,u.email,u.last_login_at FROM organization_members m JOIN users u ON u.id=m.user_id WHERE m.organization_id=? ORDER BY CASE m.role WHEN 'owner' THEN 0 WHEN 'admin' THEN 1 ELSE 2 END,u.email",(organization_id,)).fetchall()
        invites=conn.execute("SELECT id,email,role,expires_at,accepted_at,created_at FROM organization_invites WHERE organization_id=? ORDER BY id DESC LIMIT 100",(organization_id,)).fetchall()
    return {"members":[dict(r) for r in rows],"invites":[dict(r) for r in invites]}

@app.post("/api/organizations/{organization_id}/invites")
def organization_invite_create(organization_id:int,payload:OrganizationInviteIn,request:Request,x_csrf_token:Optional[str]=Header(default=None)):
    u=require_user(request);require_csrf(request,u,x_csrf_token);email=payload.email.lower().strip();raw=secrets.token_urlsafe(36);expires=(datetime.now(timezone.utc)+timedelta(days=7)).replace(microsecond=0).isoformat()
    with db() as conn:
        _require_org_admin(conn,organization_id,u)
        org=conn.execute("SELECT name FROM organizations WHERE id=?",(organization_id,)).fetchone()
        seats=conn.execute("SELECT COUNT(*) c FROM organization_members WHERE organization_id=?",(organization_id,)).fetchone()["c"]
        pending=conn.execute("SELECT COUNT(*) c FROM organization_invites WHERE organization_id=? AND accepted_at IS NULL AND expires_at>?",(organization_id,now_iso())).fetchone()["c"]
        if seats+pending>=TEAM_SEAT_LIMIT: raise HTTPException(403,f"Team seat limit reached ({TEAM_SEAT_LIMIT})")
        if not org: raise HTTPException(404,"Organization not found")
        existing=conn.execute("SELECT 1 FROM organization_members m JOIN users x ON x.id=m.user_id WHERE m.organization_id=? AND x.email=? COLLATE NOCASE",(organization_id,email)).fetchone()
        if existing: raise HTTPException(409,"That user is already a member")
        conn.execute("DELETE FROM organization_invites WHERE organization_id=? AND email=? COLLATE NOCASE AND accepted_at IS NULL",(organization_id,email))
        iid=conn.execute("INSERT INTO organization_invites(organization_id,email,role,token_hash,expires_at,invited_by,created_at) VALUES(?,?,?,?,?,?,?)",(organization_id,email,payload.role,token_hash(raw),expires,u["id"],now_iso())).lastrowid
        audit(conn,u["id"],"organization_invite","organization",str(organization_id),{"invite_id":iid,"email":email,"role":payload.role})
    invite_url=f"{PUBLIC_URL}/?org_invite={raw}"
    invite_body=f"You were invited to join {org['name']} on Cashh Radar as {payload.role}.\n\nOpen: {invite_url}\n\nThis invitation expires in 7 days."
    ok,info=send_email(email,f"Invitation to {org['name']} on Cashh Radar",invite_body)
    return {"ok":True,"invite_id":iid,"invite_url":invite_url,"email_delivery":"sent" if ok else "not_sent","email_info":info}

@app.post("/api/organizations/invites/accept")
def organization_invite_accept(payload:OrganizationInviteAcceptIn,request:Request,x_csrf_token:Optional[str]=Header(default=None)):
    u=require_user(request);require_csrf(request,u,x_csrf_token)
    with db() as conn:
        row=conn.execute("SELECT * FROM organization_invites WHERE token_hash=?",(token_hash(payload.token),)).fetchone()
        if not row or row["accepted_at"]: raise HTTPException(404,"Invitation not found or already used")
        if parse_dt(row["expires_at"]) < datetime.now(timezone.utc): raise HTTPException(410,"Invitation expired")
        if row["email"].lower()!=u["email"].lower(): raise HTTPException(403,"Invitation email does not match signed-in account")
        conn.execute("INSERT OR REPLACE INTO organization_members(organization_id,user_id,role,provision_source,created_at) VALUES(?,?,?,?,?)",(row["organization_id"],u["id"],row["role"],"invite",now_iso()))
        conn.execute("UPDATE organization_invites SET accepted_at=? WHERE id=?",(now_iso(),row["id"]))
    return {"ok":True,"organization_id":row["organization_id"],"role":row["role"]}

@app.put("/api/organizations/{organization_id}/members/{member_user_id}")
def organization_member_role(organization_id:int,member_user_id:int,payload:OrganizationMemberRoleIn,request:Request,x_csrf_token:Optional[str]=Header(default=None)):
    u=require_user(request);require_csrf(request,u,x_csrf_token)
    with db() as conn:
        _require_org_admin(conn,organization_id,u,owner_only=True)
        org=conn.execute("SELECT owner_user_id FROM organizations WHERE id=?",(organization_id,)).fetchone()
        if not org: raise HTTPException(404,"Organization not found")
        if int(org["owner_user_id"])==int(member_user_id): raise HTTPException(400,"Organization owner role cannot be changed")
        if not conn.execute("SELECT 1 FROM organization_members WHERE organization_id=? AND user_id=?",(organization_id,member_user_id)).fetchone(): raise HTTPException(404,"Member not found")
        conn.execute("UPDATE organization_members SET role=? WHERE organization_id=? AND user_id=?",(payload.role,organization_id,member_user_id))
        audit(conn,u["id"],"organization_member_role","organization",str(organization_id),{"member_user_id":member_user_id,"role":payload.role})
    return {"ok":True,"role":payload.role}

@app.delete("/api/organizations/{organization_id}/members/{member_user_id}")
def organization_member_remove(organization_id:int,member_user_id:int,request:Request,x_csrf_token:Optional[str]=Header(default=None)):
    u=require_user(request);require_csrf(request,u,x_csrf_token)
    with db() as conn:
        _require_org_admin(conn,organization_id,u)
        org=conn.execute("SELECT owner_user_id FROM organizations WHERE id=?",(organization_id,)).fetchone()
        if not org: raise HTTPException(404,"Organization not found")
        if int(org["owner_user_id"])==int(member_user_id): raise HTTPException(400,"Organization owner cannot be removed")
        conn.execute("DELETE FROM organization_members WHERE organization_id=? AND user_id=?",(organization_id,member_user_id))
        conn.execute("UPDATE api_keys SET revoked_at=? WHERE organization_id=? AND user_id=? AND revoked_at IS NULL",(now_iso(),organization_id,member_user_id))
        audit(conn,u["id"],"organization_member_remove","organization",str(organization_id),{"member_user_id":member_user_id})
    return {"ok":True}

@app.put("/api/organizations/{organization_id}/branding")
def organization_branding(organization_id:int,payload:TenantSettingsIn,request:Request,x_csrf_token:Optional[str]=Header(default=None)):
    u=require_user(request);require_csrf(request,u,x_csrf_token)
    with db() as conn:
        mem=conn.execute("SELECT role FROM organization_members WHERE organization_id=? AND user_id=?",(organization_id,u["id"])).fetchone()
        if not mem or mem["role"] not in {"owner","admin"}: raise HTTPException(403,"Organization admin required")
        conn.execute("INSERT INTO tenant_settings(organization_id,brand_name,accent_color,logo_url,custom_domain,updated_at) VALUES(?,?,?,?,?,?) ON CONFLICT(organization_id) DO UPDATE SET brand_name=excluded.brand_name,accent_color=excluded.accent_color,logo_url=excluded.logo_url,custom_domain=excluded.custom_domain,updated_at=excluded.updated_at",(organization_id,payload.brand_name,payload.accent_color,payload.logo_url,payload.custom_domain,now_iso()))
    return {"ok":True}

@app.put("/api/organizations/{organization_id}/owner")
def organization_transfer_owner(organization_id:int,payload:OrganizationOwnerTransferIn,request:Request,x_csrf_token:Optional[str]=Header(default=None)):
    u=require_user(request);require_csrf(request,u,x_csrf_token)
    with db() as conn:
        _require_org_admin(conn,organization_id,u,owner_only=True)
        org=conn.execute("SELECT owner_user_id FROM organizations WHERE id=?",(organization_id,)).fetchone()
        target=conn.execute("SELECT role FROM organization_members WHERE organization_id=? AND user_id=?",(organization_id,payload.new_owner_user_id)).fetchone()
        if not org or not target: raise HTTPException(404,"Organization or member not found")
        old=int(org["owner_user_id"]);new=int(payload.new_owner_user_id)
        if old==new: return {"ok":True,"owner_user_id":new}
        conn.execute("UPDATE organizations SET owner_user_id=?,updated_at=? WHERE id=?",(new,now_iso(),organization_id))
        conn.execute("UPDATE organization_members SET role='admin' WHERE organization_id=? AND user_id=?",(organization_id,old))
        conn.execute("UPDATE organization_members SET role='owner' WHERE organization_id=? AND user_id=?",(organization_id,new))
        audit(conn,u["id"],"organization_owner_transfer","organization",str(organization_id),{"old_owner":old,"new_owner":new});_queue_org_event(conn,organization_id,"organization.owner_transferred",{"organization_id":organization_id,"new_owner_user_id":new})
    return {"ok":True,"owner_user_id":new}

@app.delete("/api/organizations/{organization_id}")
def organization_delete(organization_id:int,payload:OrganizationDeleteIn,request:Request,x_csrf_token:Optional[str]=Header(default=None)):
    u=require_user(request);require_csrf(request,u,x_csrf_token)
    if u.get("role")!="admin" and not verify_password(payload.password,u["password_hash"]): raise HTTPException(400,"Password is incorrect")
    with db() as conn:
        _require_org_admin(conn,organization_id,u,owner_only=True);conn.execute("DELETE FROM organizations WHERE id=?",(organization_id,));audit(conn,u["id"],"organization_delete","organization",str(organization_id),{})
    return {"ok":True}

@app.get("/api/organizations/{organization_id}/watchlist")
def organization_watchlist_get(organization_id:int,request:Request):
    u=require_user(request)
    with db() as conn:
        if not _organization_role(conn,organization_id,u["id"]) and u.get("role")!="admin": raise HTTPException(403,"Organization membership required")
        rows=conn.execute("SELECT o.* FROM organization_watchlist w JOIN opportunities o ON o.id=w.opportunity_id WHERE w.organization_id=? ORDER BY w.created_at DESC",(organization_id,)).fetchall()
    return {"opportunities":[opportunity_to_dict(r,{}) for r in rows]}

@app.post("/api/organizations/{organization_id}/watchlist/{opportunity_id}")
def organization_watchlist_add(organization_id:int,opportunity_id:str,request:Request,x_csrf_token:Optional[str]=Header(default=None)):
    u=require_user(request);require_csrf(request,u,x_csrf_token)
    with db() as conn:
        role=_organization_role(conn,organization_id,u["id"])
        if role not in {"owner","admin","analyst"} and u.get("role")!="admin": raise HTTPException(403,"Analyst role or higher required")
        if not conn.execute("SELECT 1 FROM opportunities WHERE id=? AND status!='blocked'",(opportunity_id,)).fetchone(): raise HTTPException(404,"Opportunity not found")
        conn.execute("INSERT OR IGNORE INTO organization_watchlist(organization_id,opportunity_id,added_by,created_at) VALUES(?,?,?,?)",(organization_id,opportunity_id,u["id"],now_iso()));_queue_org_event(conn,organization_id,"watchlist.added",{"organization_id":organization_id,"opportunity_id":opportunity_id})
    return {"ok":True}

@app.delete("/api/organizations/{organization_id}/watchlist/{opportunity_id}")
def organization_watchlist_remove(organization_id:int,opportunity_id:str,request:Request,x_csrf_token:Optional[str]=Header(default=None)):
    u=require_user(request);require_csrf(request,u,x_csrf_token)
    with db() as conn:
        role=_organization_role(conn,organization_id,u["id"])
        if role not in {"owner","admin","analyst"} and u.get("role")!="admin": raise HTTPException(403,"Analyst role or higher required")
        conn.execute("DELETE FROM organization_watchlist WHERE organization_id=? AND opportunity_id=?",(organization_id,opportunity_id));_queue_org_event(conn,organization_id,"watchlist.removed",{"organization_id":organization_id,"opportunity_id":opportunity_id})
    return {"ok":True}

@app.get("/api/organizations/{organization_id}/webhooks")
def organization_webhooks_list(organization_id:int,request:Request):
    u=require_user(request)
    with db() as conn:
        _require_org_admin(conn,organization_id,u);rows=conn.execute("SELECT id,url,events_json,active,created_at FROM organization_webhooks WHERE organization_id=? ORDER BY id DESC",(organization_id,)).fetchall()
    return {"webhooks":[{**dict(r),"events":jload(r["events_json"],[])} for r in rows]}

@app.post("/api/organizations/{organization_id}/webhooks")
def organization_webhook_create(organization_id:int,payload:OrganizationWebhookIn,request:Request,x_csrf_token:Optional[str]=Header(default=None)):
    u=require_user(request);require_csrf(request,u,x_csrf_token)
    with db() as conn:
        _require_org_admin(conn,organization_id,u);wid=conn.execute("INSERT INTO organization_webhooks(organization_id,url,events_json,created_by,created_at) VALUES(?,?,?,?,?)",(organization_id,payload.url,jdump(payload.events or ["*"]),u["id"],now_iso())).lastrowid
    return {"ok":True,"id":wid,"signing_secret":_webhook_secret(wid),"warning":"Store this signing secret securely."}

@app.delete("/api/organizations/{organization_id}/webhooks/{webhook_id}")
def organization_webhook_delete(organization_id:int,webhook_id:int,request:Request,x_csrf_token:Optional[str]=Header(default=None)):
    u=require_user(request);require_csrf(request,u,x_csrf_token)
    with db() as conn:_require_org_admin(conn,organization_id,u);conn.execute("DELETE FROM organization_webhooks WHERE id=? AND organization_id=?",(webhook_id,organization_id))
    return {"ok":True}

@app.post("/api/organizations/{organization_id}/scim-tokens")
def scim_token_create(organization_id:int,payload:ScimTokenIn,request:Request,x_csrf_token:Optional[str]=Header(default=None)):
    u=require_user(request);require_csrf(request,u,x_csrf_token);raw="scim_"+secrets.token_urlsafe(32)
    with db() as conn:_require_org_admin(conn,organization_id,u,owner_only=True);sid=conn.execute("INSERT INTO scim_tokens(organization_id,name,token_prefix,token_hash,created_by,created_at) VALUES(?,?,?,?,?,?)",(organization_id,payload.name,raw[:12],token_hash(raw),u["id"],now_iso())).lastrowid
    return {"ok":True,"id":sid,"token":raw,"warning":"This token is shown once."}

def _scim_org(authorization:Optional[str])->int:
    if not authorization or not authorization.startswith("Bearer "): raise HTTPException(401,"Bearer SCIM token required")
    raw=authorization[7:].strip()
    with db() as conn:
        row=conn.execute("SELECT organization_id FROM scim_tokens WHERE token_hash=? AND revoked_at IS NULL",(token_hash(raw),)).fetchone()
        if not row: raise HTTPException(401,"Invalid SCIM token")
        return int(row["organization_id"])

@app.get("/scim/v2/Users")
def scim_users(authorization:Optional[str]=Header(default=None)):
    oid=_scim_org(authorization)
    with db() as conn: rows=conn.execute("SELECT u.id,u.email,m.role,m.provision_source FROM organization_members m JOIN users u ON u.id=m.user_id WHERE m.organization_id=? ORDER BY u.email",(oid,)).fetchall()
    return {"schemas":["urn:ietf:params:scim:api:messages:2.0:ListResponse"],"totalResults":len(rows),"Resources":[{"id":str(r["id"]),"userName":r["email"],"active":True,"roles":[{"value":r["role"]}],"meta":{"resourceType":"User","provisionSource":r["provision_source"]}} for r in rows]}

@app.post("/scim/v2/Users")
def scim_user_create(payload:dict[str,Any],authorization:Optional[str]=Header(default=None)):
    oid=_scim_org(authorization);email=str(payload.get("userName") or "").lower().strip()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$",email): raise HTTPException(400,"Valid userName email required")
    active=payload.get("active",True);role="member"
    roles=payload.get("roles") or []
    if roles and str(roles[0].get("value","member")) in {"member","analyst","admin"}: role=str(roles[0]["value"])
    with db() as conn:
        seats=conn.execute("SELECT COUNT(*) c FROM organization_members WHERE organization_id=?",(oid,)).fetchone()["c"]
        if seats>=TEAM_SEAT_LIMIT: raise HTTPException(403,"Team seat limit reached")
        user=conn.execute("SELECT * FROM users WHERE email=? COLLATE NOCASE",(email,)).fetchone()
        if not user:
            uid=conn.execute("INSERT INTO users(email,password_hash,is_active,created_at,email_verified_at) VALUES(?,?,?,?,?)",(email,hash_password(secrets.token_urlsafe(32)),1 if active else 0,now_iso(),now_iso())).lastrowid;conn.execute("INSERT INTO user_profiles(user_id,updated_at) VALUES(?,?)",(uid,now_iso()))
        else: uid=user["id"]
        conn.execute("INSERT OR REPLACE INTO organization_members(organization_id,user_id,role,provision_source,created_at) VALUES(?,?,?,?,?)",(oid,uid,role,"scim",now_iso()))
    return JSONResponse({"schemas":["urn:ietf:params:scim:schemas:core:2.0:User"],"id":str(uid),"userName":email,"active":bool(active)},status_code=201)

@app.delete("/scim/v2/Users/{user_id}")
def scim_user_delete(user_id:int,authorization:Optional[str]=Header(default=None)):
    oid=_scim_org(authorization)
    with db() as conn:
        row=conn.execute("SELECT role,provision_source FROM organization_members WHERE organization_id=? AND user_id=?",(oid,user_id)).fetchone()
        if not row: raise HTTPException(404,"SCIM user not found")
        if row["role"]=="owner": raise HTTPException(400,"Cannot SCIM-deprovision organization owner")
        if row["provision_source"]!="scim": raise HTTPException(409,"Only SCIM-provisioned membership can be deprovisioned through SCIM")
        conn.execute("DELETE FROM organization_members WHERE organization_id=? AND user_id=?",(oid,user_id));conn.execute("UPDATE api_keys SET revoked_at=? WHERE organization_id=? AND user_id=? AND revoked_at IS NULL",(now_iso(),oid,user_id))
    return Response(status_code=204)

@app.get("/api/admin/operations")
def admin_operations(request:Request):
    require_admin(request);now=datetime.now(timezone.utc)
    with db() as conn:
        stale=[opportunity_to_dict(r,{}) for r in conn.execute("SELECT * FROM opportunities WHERE trust!='demo' AND (last_seen IS NULL OR last_seen<?) AND status!='blocked' ORDER BY last_seen ASC LIMIT 100",((now-timedelta(hours=48)).isoformat(),)).fetchall()]
        unverified=[opportunity_to_dict(r,{}) for r in conn.execute("SELECT * FROM opportunities WHERE trust!='demo' AND manual_verified_at IS NULL AND status!='blocked' ORDER BY updated_at DESC LIMIT 100").fetchall()]
        dupes=[dict(r) for r in conn.execute("SELECT lower(title) title_key,COUNT(*) count,GROUP_CONCAT(id) ids FROM opportunities WHERE status!='blocked' GROUP BY lower(title) HAVING COUNT(*)>1 ORDER BY count DESC LIMIT 50").fetchall()]
        leads=[dict(r) for r in conn.execute("SELECT l.*,p.name provider_name,u.email FROM provider_leads l JOIN providers p ON p.id=l.provider_id JOIN users u ON u.id=l.user_id ORDER BY l.id DESC LIMIT 100").fetchall()]
    return {"stale":stale,"unverified":unverified,"duplicates":dupes,"provider_leads":leads}

@app.post("/api/admin/digests/run")
def run_digests(request:Request,x_csrf_token:Optional[str]=Header(default=None)):
    u=require_admin(request);require_csrf(request,u,x_csrf_token);sent=0;queued=0;failed=0
    with db() as conn:
        users=conn.execute("SELECT u.id,u.email,COALESCE(d.cadence,'daily') cadence,COALESCE(d.min_match,70) min_match FROM users u LEFT JOIN digest_preferences d ON d.user_id=u.id WHERE u.is_active=1 AND COALESCE(d.enabled,1)=1").fetchall()
        for usr in users:
            opps=_all_user_opportunities(conn,usr["id"]);top=sorted([o for o in opps if o["match"]>=usr["min_match"] and o["verification"]["status"] not in {"blocked","expired"}],key=lambda o:o["match"],reverse=True)[:5]
            body="Cashh Radar opportunity digest\n\n"+("\n".join(f"- {o['title']} — match {o['match']}/100 — {o['verification']['status']}" for o in top) if top else "No opportunities currently meet your threshold.")+"\n\nOpen Cashh Radar for source evidence and action plans."
            ok,info=send_email(usr["email"],"Your Cashh Radar opportunity digest",body)
            status="sent" if ok else ("queued" if info=="SMTP not configured" else "failed");sent+=1 if status=="sent" else 0;queued+=1 if status=="queued" else 0;failed+=1 if status=="failed" else 0
            conn.execute("INSERT INTO digest_deliveries(user_id,cadence,status,message_preview,error,created_at) VALUES(?,?,?,?,?,?)",(usr["id"],usr["cadence"],status,body[:500],None if ok else info,now_iso()))
        audit(conn,u["id"],"digest_run","platform",None,{"sent":sent,"queued":queued,"failed":failed})
    return {"ok":True,"sent":sent,"queued":queued,"failed":failed,"smtp_configured":smtp_configured()}

@app.post("/api/submissions")
def opportunity_submission(payload:OpportunitySubmissionIn,request:Request,x_csrf_token:Optional[str]=Header(default=None)):
    u=require_user(request);require_csrf(request,u,x_csrf_token)
    if not payload.source_url.startswith(("https://","http://")): raise HTTPException(400,"A public source URL is required")
    with db() as conn:
        sid=conn.execute("INSERT INTO opportunity_submissions(user_id,title,source_url,category,notes,created_at) VALUES(?,?,?,?,?,?)",(u["id"],payload.title,payload.source_url,payload.category,payload.notes,now_iso())).lastrowid
    return {"ok":True,"submission_id":sid,"status":"pending","message":"Submission received for evidence review. It is not treated as verified until reviewed."}

@app.get("/api/submissions")
def list_submissions(request:Request):
    u=require_user(request)
    with db() as conn: rows=conn.execute("SELECT * FROM opportunity_submissions WHERE user_id=? ORDER BY id DESC",(u["id"],)).fetchall()
    return {"submissions":[dict(r) for r in rows]}

@app.get("/api/admin/submissions")
def admin_submissions(request:Request):
    require_admin(request)
    with db() as conn: rows=conn.execute("SELECT s.*,u.email FROM opportunity_submissions s JOIN users u ON u.id=s.user_id ORDER BY CASE s.status WHEN 'pending' THEN 0 ELSE 1 END,s.id DESC").fetchall()
    return {"submissions":[dict(r) for r in rows]}

@app.post("/api/admin/submissions/{submission_id}/decision")
def decide_submission(submission_id:int,decision:str,request:Request,x_csrf_token:Optional[str]=Header(default=None)):
    u=require_admin(request);require_csrf(request,u,x_csrf_token)
    if decision not in {"approved","rejected"}: raise HTTPException(400,"Decision must be approved or rejected")
    with db() as conn:
        row=conn.execute("SELECT * FROM opportunity_submissions WHERE id=?",(submission_id,)).fetchone()
        if not row: raise HTTPException(404,"Submission not found")
        conn.execute("UPDATE opportunity_submissions SET status=?,reviewed_by=?,reviewed_at=? WHERE id=?",(decision,u["id"],now_iso(),submission_id));audit(conn,u["id"],"submission_"+decision,"opportunity_submission",str(submission_id),{"source_url":row["source_url"]})
    return {"ok":True,"status":decision,"note":"Approval means accepted for research intake, not automatically verified as an opportunity."}

@app.get("/api/admin/analytics")
def admin_analytics(request:Request):
    require_admin(request);now=datetime.now(timezone.utc);d7=(now-timedelta(days=7)).isoformat();d30=(now-timedelta(days=30)).isoformat()
    with db() as conn:
        events=[dict(r) for r in conn.execute("SELECT event_name,COUNT(*) count FROM analytics_events WHERE created_at>=? GROUP BY event_name ORDER BY count DESC LIMIT 50",(d30,)).fetchall()]
        plans=[dict(r) for r in conn.execute("SELECT plan,COUNT(*) count FROM users WHERE is_active=1 GROUP BY plan ORDER BY count DESC").fetchall()]
        new_users_7d=conn.execute("SELECT COUNT(*) c FROM users WHERE created_at>=?",(d7,)).fetchone()["c"]
        active_7d=conn.execute("SELECT COUNT(DISTINCT user_id) c FROM analytics_events WHERE user_id IS NOT NULL AND created_at>=?",(d7,)).fetchone()["c"]
        saves_30d=conn.execute("SELECT COUNT(*) c FROM watchlist WHERE created_at>=?",(d30,)).fetchone()["c"]
        outcomes_30d=conn.execute("SELECT stage,COUNT(*) count,COALESCE(SUM(amount),0) amount FROM outcomes WHERE created_at>=? GROUP BY stage ORDER BY count DESC",(d30,)).fetchall()
        api_calls_30d=conn.execute("SELECT COUNT(*) c FROM api_usage WHERE created_at>=?",(d30,)).fetchone()["c"]
        referrals_30d=conn.execute("SELECT event_type,COUNT(*) count FROM referral_events WHERE created_at>=? GROUP BY event_type",(d30,)).fetchall()
    return {"window_days":30,"new_users_7d":new_users_7d,"active_users_7d":active_7d,"watchlist_saves_30d":saves_30d,"events":events,"plans":plans,"outcomes":[dict(r) for r in outcomes_30d],"api_calls_30d":api_calls_30d,"referrals":[dict(r) for r in referrals_30d],"note":"Outcome amounts are user-entered actuals when supplied; they are not platform revenue."}

def _refresh_source_records(source_key:str,keyword:str="",actor_id:Optional[int]=None)->dict[str,Any]:
    started=now_iso()
    with db() as conn: run_id=conn.execute("INSERT INTO source_runs(source_key,status,started_at) VALUES(?,?,?)",(source_key,"running",started)).lastrowid
    try:
        if source_key=="grants_gov": records=normalize_grants(keyword)
        elif source_key=="usajobs": records=normalize_usajobs(keyword or "remote")
        elif source_key=="lever_partner": records=normalize_lever()
        else: raise RuntimeError("Source is disabled or unsupported")
        with db() as conn:
            for o in records: upsert_opportunity(conn,o,actor_id)
            conn.execute("UPDATE source_runs SET status='success',fetched_count=?,normalized_count=?,finished_at=? WHERE id=?",(len(records),len(records),now_iso(),run_id))
        return {"source":source_key,"status":"success","fetched":len(records)}
    except Exception as exc:
        with db() as conn: conn.execute("UPDATE source_runs SET status='error',error=?,finished_at=? WHERE id=?",(str(exc)[:500],now_iso(),run_id))
        return {"source":source_key,"status":"error","error":str(exc)[:300]}

def run_background_job(job_name: str) -> dict[str,Any]:
    started=time.time();started_iso=now_iso();details={}
    with db() as conn: jid=conn.execute("INSERT INTO job_runs(job_name,status,started_at) VALUES(?,?,?)",(job_name,"running",started_iso)).lastrowid
    status="ok"
    try:
        if job_name=="alerts":
            with db() as conn:
                users=conn.execute("SELECT id FROM users WHERE is_active=1").fetchall();created=sum(evaluate_alerts_for_user(conn,r["id"]) for r in users);details={"users":len(users),"alerts_created":created}
        elif job_name=="maintenance":
            with db() as conn:
                before=conn.total_changes;cut=(datetime.now(timezone.utc)-timedelta(days=1)).isoformat();conn.execute("DELETE FROM sessions WHERE expires_at<?",(now_iso(),));conn.execute("DELETE FROM password_reset_tokens WHERE expires_at<? OR used_at IS NOT NULL",(cut,));conn.execute("DELETE FROM email_verification_tokens WHERE expires_at<? OR used_at IS NOT NULL",(cut,));conn.execute("DELETE FROM login_challenges WHERE expires_at<? OR used_at IS NOT NULL",(cut,));conn.execute("DELETE FROM organization_invites WHERE expires_at<? AND accepted_at IS NULL",(now_iso(),));details={"rows_changed":conn.total_changes-before}
        elif job_name=="digests":
            sent=queued=failed=skipped=0;now=datetime.now(timezone.utc)
            with db() as conn:
                users=conn.execute("SELECT u.id,u.email,COALESCE(d.cadence,'daily') cadence,COALESCE(d.min_match,70) min_match,COALESCE(d.include_closing_soon,1) include_closing_soon,COALESCE(d.include_changes,1) include_changes FROM users u LEFT JOIN digest_preferences d ON d.user_id=u.id WHERE u.is_active=1 AND COALESCE(d.enabled,1)=1").fetchall()
                for usr in users:
                    last=conn.execute("SELECT created_at FROM digest_deliveries WHERE user_id=? AND cadence=? ORDER BY id DESC LIMIT 1",(usr["id"],usr["cadence"])).fetchone();lastdt=parse_dt(last["created_at"]) if last else None;minimum=timedelta(hours=20 if usr["cadence"]=="daily" else 144)
                    if lastdt and now-lastdt<minimum: skipped+=1;continue
                    opps=_all_user_opportunities(conn,usr["id"]);top=sorted([o for o in opps if o["match"]>=usr["min_match"] and o["verification"]["status"] not in {"blocked","expired"}],key=lambda o:o["match"],reverse=True)[:5]
                    lines=["Cashh Radar opportunity digest",""]+[f"- {o['title']} — match {o['match']}/100 — {o['verification']['status']}" for o in top]
                    if usr["include_closing_soon"]:
                        closing=[o for o in opps if o.get("closes_at") and parse_dt(o["closes_at"]) and now<=parse_dt(o["closes_at"])<=now+timedelta(days=7)][:3]
                        if closing: lines += ["","Closing soon:"]+[f"- {o['title']} — {o['closes_at']}" for o in closing]
                    if usr["include_changes"]:
                        changes=conn.execute("SELECT o.title FROM opportunity_changes c JOIN opportunities o ON o.id=c.opportunity_id JOIN watchlist w ON w.opportunity_id=o.id WHERE w.user_id=? AND c.detected_at>=? ORDER BY c.id DESC LIMIT 3",(usr["id"],(now-timedelta(days=7)).isoformat())).fetchall()
                        if changes: lines += ["","Watched source changes:"]+[f"- {r['title']}" for r in changes]
                    body="\n".join(lines)+"\n\nOpen Cashh Radar for source evidence and action plans.";ok,info=send_email(usr["email"],"Your Cashh Radar opportunity digest",body);delivery="sent" if ok else ("queued" if info=="SMTP not configured" else "failed");sent+=delivery=="sent";queued+=delivery=="queued";failed+=delivery=="failed";conn.execute("INSERT INTO digest_deliveries(user_id,cadence,status,message_preview,error,created_at) VALUES(?,?,?,?,?,?)",(usr["id"],usr["cadence"],delivery,body[:500],None if ok else info,now_iso()))
            details={"sent":sent,"queued":queued,"failed":failed,"skipped":skipped}
        elif job_name=="sources":
            configured=[x.strip() for x in os.getenv("CASHH_SCHEDULED_SOURCES","").split(",") if x.strip()];details={"sources":[_refresh_source_records(x) for x in configured]}
            if any(x.get("status")=="error" for x in details["sources"]): status="error"
        elif job_name=="webhooks":
            delivered=failed=0
            with db() as conn: rows=conn.execute("SELECT d.*,w.url FROM webhook_deliveries d JOIN organization_webhooks w ON w.id=d.webhook_id WHERE d.status IN ('pending','retry') AND (d.next_attempt_at IS NULL OR d.next_attempt_at<=?) ORDER BY d.id LIMIT 100",(now_iso(),)).fetchall()
            for row in rows:
                body=row["payload_json"].encode();sig=hmac.new(_webhook_secret(row["webhook_id"]).encode(),body,hashlib.sha256).hexdigest()
                try:
                    r=requests.post(row["url"],data=body,headers={"Content-Type":"application/json","X-Cashh-Event":row["event_type"],"X-Cashh-Signature":sig},timeout=WEBHOOK_TIMEOUT);ok=200<=r.status_code<300;err=None if ok else f"HTTP {r.status_code}"
                except Exception as exc: ok=False;err=str(exc)[:300]
                with db() as conn:
                    attempts=int(row["attempts"])+1;newstatus="delivered" if ok else ("retry" if attempts<5 else "failed");nextat=None if ok or attempts>=5 else (datetime.now(timezone.utc)+timedelta(minutes=2**attempts)).isoformat();conn.execute("UPDATE webhook_deliveries SET status=?,attempts=?,last_error=?,next_attempt_at=?,delivered_at=? WHERE id=?",(newstatus,attempts,err,nextat,now_iso() if ok else None,row["id"]))
                delivered+=1 if ok else 0;failed+=0 if ok else 1
            details={"delivered":delivered,"failed_or_retried":failed}
        elif job_name=="backups":
            BACKUP_DIR.mkdir(parents=True,exist_ok=True);dest=BACKUP_DIR/f"cashh-radar-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.db"
            with db() as src, sqlite3.connect(dest) as dst: src.backup(dst)
            with sqlite3.connect(dest) as check: integrity=check.execute("PRAGMA quick_check").fetchone()[0]
            if integrity!="ok": raise RuntimeError(f"Backup verification failed: {integrity}")
            details={"backup":str(dest),"bytes":dest.stat().st_size,"verified":True}
        else: raise ValueError("Unknown job")
    except Exception as exc: status="error";details={"error":str(exc)[:500]}
    duration=int((time.time()-started)*1000)
    with db() as conn: conn.execute("UPDATE job_runs SET status=?,details_json=?,finished_at=?,duration_ms=? WHERE id=?",(status,jdump(details),now_iso(),duration,jid))
    if status!="ok": raise RuntimeError(details.get("error") or jdump(details))
    return {"job":job_name,"status":status,"duration_ms":duration,**details}

_scheduler_thread: Optional[threading.Thread] = None
_scheduler_started = False

def _scheduler_loop() -> None:
    # Single-process launch scheduler. For future multi-instance deployments, disable
    # this and run the same jobs from a dedicated shared-database worker.
    intervals={
        "webhooks":max(60,int(os.getenv("CASHH_JOB_WEBHOOKS_SECONDS","300"))),
        "alerts":max(60,int(os.getenv("CASHH_JOB_ALERTS_SECONDS","600"))),
        "sources":max(300,int(os.getenv("CASHH_JOB_SOURCES_SECONDS","1800"))),
        "digests":max(900,int(os.getenv("CASHH_JOB_DIGESTS_SECONDS","3600"))),
        "maintenance":max(3600,int(os.getenv("CASHH_JOB_MAINTENANCE_SECONDS","21600"))),
        "backups":max(3600,int(os.getenv("CASHH_JOB_BACKUPS_SECONDS","86400"))),
    }
    due={name:0.0 for name in intervals}
    # Avoid making third-party source calls immediately during deploy health checks.
    due["sources"]=time.time()+60
    while True:
        now=time.time()
        for name,interval in intervals.items():
            if now < due[name]:
                continue
            try:
                run_background_job(name)
            except Exception as exc:
                # run_background_job records the error in job_runs; the scheduler must
                # remain alive so later jobs and retries can continue.
                print(f"Cashh Radar scheduler: {name} failed: {exc}", flush=True)
            due[name]=time.time()+interval
        time.sleep(SCHEDULER_TICK_SECONDS)

def start_launch_scheduler() -> None:
    global _scheduler_thread,_scheduler_started
    if not SCHEDULER_ENABLED or _scheduler_started:
        return
    _scheduler_started=True
    _scheduler_thread=threading.Thread(target=_scheduler_loop,name="cashh-radar-scheduler",daemon=True)
    _scheduler_thread.start()

@app.post("/api/admin/jobs/{job_name}/run")
def admin_run_job(job_name:str,request:Request,x_csrf_token:Optional[str]=Header(default=None)):
    u=require_admin(request);require_csrf(request,u,x_csrf_token)
    if job_name not in {"alerts","digests","maintenance","sources","webhooks","backups"}: raise HTTPException(404,"Unknown job")
    result=run_background_job(job_name)
    with db() as conn: audit(conn,u["id"],"job_run","job",job_name,result)
    return result

@app.get("/api/admin/jobs")
def admin_jobs(request:Request):
    require_admin(request)
    with db() as conn: rows=conn.execute("SELECT * FROM job_runs ORDER BY id DESC LIMIT 100").fetchall()
    return {"jobs":[{**dict(r),"details":jload(r["details_json"],{})} for r in rows]}

@app.get("/api/metrics")
def metrics(authorization:Optional[str]=Header(default=None)):
    expected=os.getenv("CASHH_METRICS_TOKEN")
    if expected:
        if not authorization or not hmac.compare_digest(authorization,f"Bearer {expected}"): raise HTTPException(401,"Metrics token required")
    elif not DEV_MODE:
        raise HTTPException(404,"Not found")
    with db() as conn:
        values={
            "cashh_users_total":conn.execute("SELECT COUNT(*) c FROM users WHERE is_active=1").fetchone()["c"],
            "cashh_opportunities_total":conn.execute("SELECT COUNT(*) c FROM opportunities WHERE status!='blocked'").fetchone()["c"],
            "cashh_alert_events_total":conn.execute("SELECT COUNT(*) c FROM alert_events").fetchone()["c"],
            "cashh_api_calls_total":conn.execute("SELECT COUNT(*) c FROM api_usage").fetchone()["c"],
            "cashh_provider_leads_total":conn.execute("SELECT COUNT(*) c FROM provider_leads").fetchone()["c"],
            "cashh_organizations_total":conn.execute("SELECT COUNT(*) c FROM organizations").fetchone()["c"],
        }
        last=conn.execute("SELECT job_name,status,duration_ms FROM job_runs ORDER BY id DESC LIMIT 20").fetchall()
    lines=["# Cashh Radar operational metrics"]+[f"{k} {v}" for k,v in values.items()]
    for r in last:
        safe=re.sub(r"[^a-zA-Z0-9_]","_",r["job_name"]);lines.append(f'cashh_job_last_duration_ms{{job="{safe}",status="{r["status"]}"}} {int(r["duration_ms"] or 0)}')
    return PlainTextResponse("\n".join(lines)+"\n",media_type="text/plain; version=0.0.4")

def _policy_page(title: str, intro: str, sections: list[tuple[str,str]]) -> HTMLResponse:
    items="".join(f"<section><h2>{h}</h2><p>{body}</p></section>" for h,body in sections)
    html=f"""<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><meta name='theme-color' content='#0B1020'><title>{title} — Cashh Radar</title><style>body{{margin:0;background:#0B1020;color:#F6F7F9;font:16px/1.65 Inter,system-ui,sans-serif}}main{{max-width:860px;margin:auto;padding:48px 22px 70px}}a{{color:#00E5C2}}.brand{{font-weight:900;letter-spacing:.08em;color:#00E5C2}}h1{{font-size:clamp(34px,6vw,56px);line-height:1.05;margin:.35em 0}}h2{{margin-top:2em;color:#7CF2E3}}p,li{{color:#C5CDD8}}.note{{border:1px solid #27303B;background:#151A26;padding:14px 16px;border-radius:12px}}nav{{display:flex;flex-wrap:wrap;gap:14px;margin:28px 0}}footer{{margin-top:42px;border-top:1px solid #27303B;padding-top:22px;color:#8E99A8;font-size:13px}}</style></head><body><main><div class='brand'>CASHH RADAR</div><h1>{title}</h1><p class='note'>{intro}</p><nav><a href='/'>Home</a><a href='/privacy'>Privacy</a><a href='/terms'>Terms</a><a href='/disclosures'>Disclosures</a><a href='/security'>Security</a><a href='/support'>Support</a></nav>{items}<footer>Effective: September 3, 2026 · Contact: <a href='mailto:{SUPPORT_EMAIL}'>{SUPPORT_EMAIL}</a><br>This launch policy is a practical operating baseline and is not a substitute for jurisdiction-specific legal advice.</footer></main></body></html>"""
    return HTMLResponse(html)

@app.get("/privacy", response_class=HTMLResponse)
def privacy_page():
    return _policy_page("Privacy Policy","Cashh Radar uses the minimum account and product data reasonably needed to operate, secure, personalize, and improve the service.",[
        ("Information we process","Account identifiers, authentication/security records, profile preferences, saved searches and watchlists, alerts, roadmaps, outreach drafts, outcome records you enter, organization/workspace records, API usage, billing-event metadata, referral/provider workflow records, and limited first-party product analytics."),
        ("Why we use it","To provide the service, personalize rankings, preserve user work, secure accounts, operate alerts and digests, administer organizations, troubleshoot reliability, prevent abuse, and measure product performance."),
        ("Sharing","We do not sell personal data to advertisers. Service providers may process data only to operate features you enable, such as hosting, email delivery, or payment processing. Referral/provider participation does not grant access to private account data."),
        ("Your controls","Signed-in users can export their account data, change security settings, and request permanent account deletion. Organization data may require ownership transfer or workspace deletion before a personal account can be removed."),
        ("Retention and security","Security/session tokens expire automatically. Other records are retained while needed to operate the account, satisfy legitimate operational/legal needs, or until deletion. Cashh Radar uses password hashing, CSRF protection, secure cookies in production, signed webhooks, audit records, and restricted administrative controls."),
        ("Contact","Privacy questions or deletion issues can be sent to the support address shown below.")])

@app.get("/terms", response_class=HTMLResponse)
def terms_page():
    return _policy_page("Terms of Use","By using Cashh Radar, you agree to use the service lawfully and to independently verify an opportunity before committing money, time, personal information, or contractual obligations.",[
        ("What the service does","Cashh Radar discovers, organizes, verifies, scores, compares, and helps users act on work, grant, freelance, business, and other opportunity information. Evidence labels distinguish source-confirmed facts, estimates, models, illustrative records, and other confidence states."),
        ("No earnings or outcome guarantee","Cashh Radar does not guarantee employment, grants, awards, customers, profits, investment returns, eligibility, acceptance, response times, or any other financial or business outcome. Scores and rankings are decision-support tools, not promises."),
        ("Your responsibility","Review canonical source terms, eligibility requirements, deadlines, fees, contracts, tax implications, and risks before acting. Do not use the service for fraud, spam, unauthorized access, or unlawful activity."),
        ("Accounts and organizations","You are responsible for protecting credentials and for actions performed through your account. Workspace owners control membership and must transfer ownership or delete the workspace before deleting an owner account."),
        ("Paid features","If paid plans are activated, prices and entitlements shown at checkout govern the purchase. Billing is handled by the configured payment provider. Cancellation and billing controls are presented through the service/provider where enabled."),
        ("Availability and changes","Sources, APIs, providers, and features can change or become unavailable. Cashh Radar may block stale, unsafe, unsupported, or policy-incompatible sources and may update these terms as the service evolves."),
        ("Contact","Questions about these terms can be sent to the support address shown below.")])

@app.get("/disclosures", response_class=HTMLResponse)
def disclosures_page():
    return _policy_page("Opportunity & Compensation Disclosures","Cashh Radar is designed to keep commercial incentives separate from evidence quality and ranking integrity.",[
        ("Evidence labels","Source-confirmed and verified records include provenance/freshness information where available. Illustrative records are examples and are not claims of current availability or earnings."),
        ("Estimates and scores","Earning ranges, time-to-income estimates, match scores, confidence values, and forecasts may be modeled or estimated. They are not guarantees and can be wrong or become outdated."),
        ("Referral and provider compensation","Cashh Radar may receive compensation from disclosed referral/provider relationships when those programs are activated. Compensation must not secretly convert an unverified opportunity into a verified one or override the core opportunity-scoring evidence model."),
        ("Third-party terms","Third-party websites, employers, grant programs, marketplaces, APIs, and providers set their own terms. A Cashh Radar listing does not imply endorsement by or partnership with the source unless explicitly stated and verified."),
        ("Financial decisions","Cashh Radar is an opportunity-intelligence product, not individualized legal, tax, investment, or financial advice. Seek qualified professional advice where appropriate.")])

@app.get("/security", response_class=HTMLResponse)
def security_page():
    return _policy_page("Security","Cashh Radar includes production security controls for authentication, sessions, organization access, APIs, webhooks, and operational monitoring.",[
        ("Account security","Passwords are stored using salted PBKDF2 hashing. Production sessions use HttpOnly cookies and can be configured Secure-only. Email verification and optional two-step email login are supported."),
        ("Request protection","State-changing account operations require CSRF protection. Security headers restrict framing, content types, permissions, and browser resource behavior."),
        ("Enterprise controls","Organization roles, tenant-scoped API keys, rate limits, signed webhooks, SCIM-style provisioning, audit records, and workspace ownership controls are implemented."),
        ("Operational resilience","Health/readiness endpoints, job history, database migration tracking, verified SQLite backups, protected metrics, source health, and failure-state reporting are available to operators."),
        ("Report a concern",f"If you believe you found a security issue, contact {SUPPORT_EMAIL}. Do not include passwords, secret keys, or sensitive personal data in the initial report.")])

@app.get("/support", response_class=HTMLResponse)
def support_page():
    return _policy_page("Support","For account, billing, data, source, or technical questions, contact the address below. Never email passwords, one-time login codes, API secrets, or payment-card details.",[
        ("Before contacting support","For account access, try password reset first. For opportunity questions, include the opportunity title/source link. For API issues, include the endpoint, timestamp, and request ID if available—never the full API key."),
        ("Billing","If paid plans are enabled, include the account email and non-sensitive checkout/invoice reference. Do not send card numbers."),
        ("Data and privacy","Use the in-product export/delete controls when possible. If you cannot access the account, contact support from the account email address."),
        ("Contact",f"Email: {SUPPORT_EMAIL}")])

# ---------- health ----------
@app.get("/api/health/live")
def health_live(): return {"status":"ok","app":"Cashh Radar","version":"2.2.0"}

@app.get("/api/health/ready")
def health_ready():
    checks={
        "database":False,
        "schema_v4":False,
        "production_secret":SECRET_KEY!="cashh-radar-dev-change-me" or DEV_MODE,
        "secure_cookie":COOKIE_SECURE or DEV_MODE,
        "https_public_url":PUBLIC_URL.startswith("https://") or DEV_MODE,
        "support_email":("@" in SUPPORT_EMAIL and not SUPPORT_EMAIL.endswith("@example.com")) or DEV_MODE,
        "smtp_if_verification_required":smtp_configured() or not REQUIRE_EMAIL_VERIFICATION or DEV_MODE,
    }
    try:
        with db() as conn:
            conn.execute("SELECT 1");checks["database"]=True
            version=conn.execute("SELECT COALESCE(MAX(version),0) v FROM schema_migrations").fetchone()["v"]
            checks["schema_v4"]=int(version)>=4
    except Exception: pass
    ready=all(checks.values())
    return JSONResponse({"status":"ready" if ready else "not_ready","checks":checks},status_code=200 if ready else 503)

@app.get("/api/health")
def health():
    with db() as conn:
        conn.execute("SELECT 1")
        counts=conn.execute("SELECT COUNT(*) o,(SELECT COUNT(*) FROM users) u,(SELECT COUNT(*) FROM organizations) orgs FROM opportunities").fetchone()
        migration=conn.execute("SELECT MAX(version) v FROM schema_migrations").fetchone()["v"]
        last_job=conn.execute("SELECT job_name,status,finished_at FROM job_runs ORDER BY id DESC LIMIT 1").fetchone()
    return {"status":"ok","app":"Cashh Radar","version":"2.2.0","database":str(DB_PATH.name),"schema_version":migration,"opportunities":counts["o"],"users":counts["u"],"organizations":counts["orgs"],"last_job":dict(last_job) if last_job else None,"production_secret_configured":SECRET_KEY!="cashh-radar-dev-change-me","cookie_secure":COOKIE_SECURE}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host=os.getenv("HOST","127.0.0.1"), port=int(os.getenv("PORT","8000")), reload=False)
