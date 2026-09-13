"""Cashh Radar prospect-to-opportunity bridge.

The mobile prospect surface and the broader Cashh Radar opportunity engine share
one lifecycle here. Source-backed prospect records become normal opportunities;
per-user outreach state is persisted server-side; replies and outcomes feed the
canonical learning loop; evidence freshness can be rechecked automatically; and
ranking exposes both modeled and realized value-per-hour without pretending a
proposal is guaranteed income.
"""
from __future__ import annotations

import base64
import gzip
import ipaddress
import json
import math
import os
import re
import socket
import threading
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import requests
from fastapi import FastAPI, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field

import cashh_loop


CAMPAIGN = "SCC500-2026-09-08"
SOURCE_KEY = "prospect_engine"
DEFAULT_OUTREACH_MINUTES = 12
DEFAULT_FULFILLMENT_MINUTES = 180
REFRESH_BATCH = max(1, min(50, int(os.getenv("CASHH_PROSPECT_REFRESH_BATCH", "8"))))
REFRESH_INTERVAL_SECONDS = max(300, int(os.getenv("CASHH_PROSPECT_REFRESH_SECONDS", "900")))
HTTP_TIMEOUT_SECONDS = max(2, min(15, int(os.getenv("CASHH_PROSPECT_HTTP_TIMEOUT", "5"))))

_scheduler_thread: Optional[threading.Thread] = None
_scheduler_started = False


class ProspectStateIn(BaseModel):
    status: Optional[str] = Field(default=None, max_length=100)
    verified: Optional[bool] = None
    contact_email: Optional[str] = Field(default=None, max_length=320)
    script_type: Optional[str] = Field(default=None, max_length=40)
    subject: Optional[str] = Field(default=None, max_length=500)
    message: Optional[str] = Field(default=None, max_length=20000)
    prepared_at: Optional[str] = None
    sent_at: Optional[str] = None
    last_contact_type: Optional[str] = Field(default=None, max_length=40)
    replied_at: Optional[str] = None
    outcome_stage: Optional[str] = Field(
        default=None,
        pattern="^(saved|started|applied|contacted|replied|interview|negotiating|won|paid|fulfilled|follow_up|lost)$",
    )
    outcome_amount: Optional[float] = Field(default=None, ge=0)
    minutes_spent: Optional[int] = Field(default=None, ge=0, le=1000000)
    estimated_fulfillment_minutes: Optional[int] = Field(default=None, ge=15, le=100000)
    notes: Optional[str] = Field(default=None, max_length=5000)
    event_type: Optional[str] = Field(default=None, max_length=80)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _loads(value: Optional[str], default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def _dumps(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def _ensure_schema(core: Any) -> None:
    schema = """
    CREATE TABLE IF NOT EXISTS prospect_catalog(
      prospect_id TEXT PRIMARY KEY,
      opportunity_id TEXT NOT NULL UNIQUE REFERENCES opportunities(id) ON DELETE CASCADE,
      campaign TEXT NOT NULL,
      wave INTEGER,
      priority INTEGER,
      fit INTEGER,
      deliverability INTEGER,
      business_name TEXT NOT NULL,
      city TEXT DEFAULT '',
      industry TEXT DEFAULT '',
      service_focus TEXT DEFAULT '',
      public_signal TEXT DEFAULT '',
      source_url TEXT,
      website TEXT,
      contact_email TEXT,
      verification_tier TEXT DEFAULT '',
      source_verified_at TEXT,
      offer_price REAL NOT NULL DEFAULT 0,
      requires_postal INTEGER NOT NULL DEFAULT 0,
      estimated_outreach_minutes INTEGER NOT NULL DEFAULT 12,
      estimated_fulfillment_minutes INTEGER NOT NULL DEFAULT 180,
      freshness_status TEXT NOT NULL DEFAULT 'source_snapshot',
      last_checked_at TEXT,
      last_http_status INTEGER,
      evidence_json TEXT NOT NULL DEFAULT '{}',
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_prospect_catalog_rank
      ON prospect_catalog(freshness_status, fit DESC, deliverability DESC, priority);
    CREATE INDEX IF NOT EXISTS idx_prospect_catalog_checked
      ON prospect_catalog(last_checked_at, priority);

    CREATE TABLE IF NOT EXISTS prospect_user_state(
      user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      prospect_id TEXT NOT NULL REFERENCES prospect_catalog(prospect_id) ON DELETE CASCADE,
      status TEXT NOT NULL DEFAULT 'CONTACT READY',
      verified INTEGER NOT NULL DEFAULT 0,
      contact_email TEXT,
      script_type TEXT,
      subject TEXT,
      message TEXT,
      prepared_at TEXT,
      sent_at TEXT,
      last_contact_type TEXT,
      replied_at TEXT,
      outcome_stage TEXT,
      outcome_amount REAL,
      minutes_spent INTEGER NOT NULL DEFAULT 0,
      estimated_fulfillment_minutes INTEGER,
      notes TEXT DEFAULT '',
      last_synced_at TEXT NOT NULL,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      PRIMARY KEY(user_id, prospect_id)
    );
    CREATE INDEX IF NOT EXISTS idx_prospect_user_state_status
      ON prospect_user_state(user_id, status, updated_at DESC);

    CREATE TABLE IF NOT EXISTS prospect_events(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      prospect_id TEXT NOT NULL REFERENCES prospect_catalog(prospect_id) ON DELETE CASCADE,
      opportunity_id TEXT NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
      event_type TEXT NOT NULL,
      payload_json TEXT NOT NULL DEFAULT '{}',
      created_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_prospect_events_user
      ON prospect_events(user_id, prospect_id, id);

    CREATE TABLE IF NOT EXISTS prospect_refresh_runs(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      checked_count INTEGER NOT NULL DEFAULT 0,
      current_count INTEGER NOT NULL DEFAULT 0,
      restricted_count INTEGER NOT NULL DEFAULT 0,
      unavailable_count INTEGER NOT NULL DEFAULT 0,
      error_count INTEGER NOT NULL DEFAULT 0,
      started_at TEXT NOT NULL,
      finished_at TEXT
    );
    """
    with core.db() as conn:
        conn.executescript(schema)
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations(version,name,applied_at) VALUES(?,?,?)",
            (6, "unified_prospect_opportunity_lifecycle", core.now_iso()),
        )


def _packed_bundle_rows(core: Any) -> list[dict[str, Any]]:
    data_dir = Path(core.BASE_DIR) / "prospect-android-app" / "data"
    chunks: list[str] = []
    for number in range(1, 5):
        text = (data_dir / f"p500-gz-{number}.js").read_text(encoding="utf-8")
        match = re.search(r"\+'([^']*)';?\s*$", text)
        if not match:
            raise RuntimeError(f"Could not parse packed prospect data chunk {number}")
        chunks.append(match.group(1))
    payload = json.loads(gzip.decompress(base64.b64decode("".join(chunks))).decode("utf-8"))
    fields = payload.get("fields") or []
    rows = payload.get("rows") or []
    mapped = [dict(zip(fields, row)) for row in rows]
    if len(mapped) != 500:
        raise RuntimeError(f"Expected 500 packed source-backed prospects; got {len(mapped)}")
    emails = {str(row.get("e") or "").strip().lower() for row in mapped}
    if "" in emails or len(emails) != 500:
        raise RuntimeError("Packed prospect bundle failed unique public-email integrity check")
    return mapped


def _opportunity_id(prospect_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", prospect_id).strip("-")
    return f"prospect-{safe}"[:190]


def _normalized_catalog_record(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "prospect_id": str(row.get("id") or "").strip(),
        "campaign": CAMPAIGN,
        "wave": int(row.get("q") or 1),
        "priority": int(row.get("r") or 999),
        "fit": int(row.get("h") or 50),
        "deliverability": int(row.get("v") or 50),
        "business_name": str(row.get("b") or "Local business").strip(),
        "city": str(row.get("c") or "").strip(),
        "industry": str(row.get("i") or "").strip(),
        "service_focus": str(row.get("s") or "").strip(),
        "public_signal": str(row.get("g") or "").strip(),
        "source_url": str(row.get("u") or row.get("w") or "").strip() or None,
        "website": str(row.get("w") or "").strip() or None,
        "contact_email": str(row.get("e") or "").strip().lower(),
        "verification_tier": str(row.get("t") or "").strip(),
        "source_verified_at": str(row.get("d") or "2026-09-08").strip(),
        "offer_price": 100.0,
        "requires_postal": 1,
        "estimated_outreach_minutes": DEFAULT_OUTREACH_MINUTES,
        "estimated_fulfillment_minutes": DEFAULT_FULFILLMENT_MINUTES,
    }


def _prospect_evidence(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "classification": "current_external_evidence",
        "prospect_id": record["prospect_id"],
        "campaign": record["campaign"],
        "verification_tier": record["verification_tier"],
        "source_verified_at": record["source_verified_at"],
        "public_signal": record["public_signal"],
        "public_contact_email": record["contact_email"],
        "offer_value": {
            "amount": record["offer_price"],
            "classification": "financial_model_assumption",
            "note": "User-set proposed one-time offer; not customer commitment or guaranteed income.",
        },
        "effort_model": {
            "outreach_minutes": record["estimated_outreach_minutes"],
            "fulfillment_minutes": record["estimated_fulfillment_minutes"],
            "classification": "financial_model_assumption",
        },
    }


def _sync_catalog_from_bundle(core: Any) -> dict[str, int]:
    rows = [_normalized_catalog_record(row) for row in _packed_bundle_rows(core)]
    created = updated = changes = 0
    now = core.now_iso()
    with core.db() as conn:
        for record in rows:
            prospect_id = record["prospect_id"]
            oid = _opportunity_id(prospect_id)
            evidence = _prospect_evidence(record)
            old_catalog = conn.execute("SELECT * FROM prospect_catalog WHERE prospect_id=?", (prospect_id,)).fetchone()
            old_opp = conn.execute("SELECT * FROM opportunities WHERE id=?", (oid,)).fetchone()
            first_seen = old_opp["first_seen"] if old_opp else record["source_verified_at"] or now
            last_seen = old_opp["last_seen"] if old_opp and old_opp["last_seen"] else record["source_verified_at"] or now
            opportunity = {
                "id": oid,
                "source_key": SOURCE_KEY,
                "source_record_id": prospect_id,
                "title": f"{record['business_name']} — $100 content-pack prospect",
                "organization": record["business_name"],
                "category": "Client Prospect",
                "mode": "remote",
                "experience": "quick",
                "trust": "source",
                "base_match": max(0, min(100, record["fit"])),
                "speed_days": 2,
                "income_min": record["offer_price"],
                "income_max": record["offer_price"],
                "income_period": "project",
                "income_label": "Proposed offer value (not guaranteed income)",
                "income_is_estimate": 1,
                "startup_cost": 0,
                "durability": 50,
                "competition": 50,
                "tags": ["Client prospect", "Email-first", record["city"], record["industry"]],
                "source_name": "Cashh Radar source-backed public business record",
                "source_url": record["source_url"],
                "first_seen": first_seen,
                "last_seen": last_seen,
                "closes_at": None,
                "why": f"Public business signal: {record['public_signal']}" if record["public_signal"] else "Source-backed public business record with a public business-intended contact email.",
                "risks": "The $100 offer is a proposal, not guaranteed income. Recheck source freshness, business fit, commercial-email requirements, and current contact information before sending.",
                "eligibility": "Use only public business-intended contact information and truthful claims; respect opt-out requests and applicable outreach rules.",
                "steps": [
                    "Recheck the public source and business contact route",
                    "Review the source-backed business signal",
                    "Personalize the $100 offer without inventing facts",
                    "Send only after the commercial-email preflight is satisfied",
                    "Record the reply, outcome, amount, and time spent",
                ],
                "evidence": evidence,
                "status": old_opp["status"] if old_opp else "active",
            }
            opportunity["content_hash"] = core.record_hash(opportunity)
            if old_opp and old_opp["content_hash"] and old_opp["content_hash"] != opportunity["content_hash"]:
                conn.execute(
                    "INSERT INTO opportunity_changes(opportunity_id,old_hash,new_hash,change_json,detected_at) VALUES(?,?,?,?,?)",
                    (oid, old_opp["content_hash"], opportunity["content_hash"], _dumps({"source": "prospect_bundle_sync"}), now),
                )
                changes += 1
            conn.execute(
                """
                INSERT INTO opportunities(
                  id,source_key,source_record_id,title,organization,category,mode,experience,trust,
                  base_match,speed_days,income_min,income_max,income_period,income_label,income_is_estimate,
                  startup_cost,durability,competition,tags_json,source_name,source_url,first_seen,last_seen,
                  closes_at,why,risks,eligibility,steps_json,evidence_json,status,content_hash,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                  source_key=excluded.source_key,source_record_id=excluded.source_record_id,title=excluded.title,
                  organization=excluded.organization,category=excluded.category,mode=excluded.mode,
                  experience=excluded.experience,trust=excluded.trust,base_match=excluded.base_match,
                  speed_days=excluded.speed_days,income_min=excluded.income_min,income_max=excluded.income_max,
                  income_period=excluded.income_period,income_label=excluded.income_label,
                  income_is_estimate=excluded.income_is_estimate,startup_cost=excluded.startup_cost,
                  durability=excluded.durability,competition=excluded.competition,tags_json=excluded.tags_json,
                  source_name=excluded.source_name,source_url=excluded.source_url,why=excluded.why,
                  risks=excluded.risks,eligibility=excluded.eligibility,steps_json=excluded.steps_json,
                  evidence_json=excluded.evidence_json,content_hash=excluded.content_hash,updated_at=excluded.updated_at
                """,
                (
                    oid, opportunity["source_key"], prospect_id, opportunity["title"], opportunity["organization"],
                    opportunity["category"], opportunity["mode"], opportunity["experience"], opportunity["trust"],
                    opportunity["base_match"], opportunity["speed_days"], opportunity["income_min"], opportunity["income_max"],
                    opportunity["income_period"], opportunity["income_label"], opportunity["income_is_estimate"],
                    opportunity["startup_cost"], opportunity["durability"], opportunity["competition"],
                    _dumps([tag for tag in opportunity["tags"] if tag]), opportunity["source_name"], opportunity["source_url"],
                    opportunity["first_seen"], opportunity["last_seen"], opportunity["closes_at"], opportunity["why"],
                    opportunity["risks"], opportunity["eligibility"], _dumps(opportunity["steps"]), _dumps(evidence),
                    opportunity["status"], opportunity["content_hash"], old_opp["created_at"] if old_opp else now, now,
                ),
            )
            conn.execute(
                """
                INSERT INTO prospect_catalog(
                  prospect_id,opportunity_id,campaign,wave,priority,fit,deliverability,business_name,city,industry,
                  service_focus,public_signal,source_url,website,contact_email,verification_tier,source_verified_at,
                  offer_price,requires_postal,estimated_outreach_minutes,estimated_fulfillment_minutes,
                  freshness_status,last_checked_at,last_http_status,evidence_json,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(prospect_id) DO UPDATE SET
                  opportunity_id=excluded.opportunity_id,campaign=excluded.campaign,wave=excluded.wave,
                  priority=excluded.priority,fit=excluded.fit,deliverability=excluded.deliverability,
                  business_name=excluded.business_name,city=excluded.city,industry=excluded.industry,
                  service_focus=excluded.service_focus,public_signal=excluded.public_signal,source_url=excluded.source_url,
                  website=excluded.website,contact_email=excluded.contact_email,verification_tier=excluded.verification_tier,
                  source_verified_at=excluded.source_verified_at,offer_price=excluded.offer_price,
                  requires_postal=excluded.requires_postal,estimated_outreach_minutes=excluded.estimated_outreach_minutes,
                  estimated_fulfillment_minutes=excluded.estimated_fulfillment_minutes,evidence_json=excluded.evidence_json,
                  updated_at=excluded.updated_at
                """,
                (
                    prospect_id, oid, record["campaign"], record["wave"], record["priority"], record["fit"],
                    record["deliverability"], record["business_name"], record["city"], record["industry"],
                    record["service_focus"], record["public_signal"], record["source_url"], record["website"],
                    record["contact_email"], record["verification_tier"], record["source_verified_at"],
                    record["offer_price"], record["requires_postal"], record["estimated_outreach_minutes"],
                    record["estimated_fulfillment_minutes"], old_catalog["freshness_status"] if old_catalog else "source_snapshot",
                    old_catalog["last_checked_at"] if old_catalog else None, old_catalog["last_http_status"] if old_catalog else None,
                    _dumps(evidence), old_catalog["created_at"] if old_catalog else now, now,
                ),
            )
            if old_catalog:
                updated += 1
            else:
                created += 1
    return {"created": created, "updated": updated, "changes": changes, "total": len(rows)}


def _freshness_score(row: dict[str, Any]) -> int:
    status = row.get("freshness_status") or "source_snapshot"
    base = {
        "current": 100,
        "redirected": 92,
        "restricted": 58,
        "source_snapshot": 50,
        "unavailable": 12,
        "error": 20,
    }.get(status, 40)
    checked = _parse_dt(row.get("last_checked_at")) or _parse_dt(row.get("source_verified_at"))
    if checked:
        age_hours = max(0.0, (datetime.now(timezone.utc) - checked).total_seconds() / 3600)
        if age_hours > 168:
            base -= 25
        elif age_hours > 72:
            base -= 12
    return max(0, min(100, base))


def _business_days_after(value: Optional[str], count: int) -> Optional[datetime]:
    dt = _parse_dt(value)
    if not dt:
        return None
    left = max(0, count)
    while left:
        dt += timedelta(days=1)
        if dt.weekday() < 5:
            left -= 1
    return dt


def _follow_due(state: dict[str, Any]) -> Optional[datetime]:
    if not state.get("sent_at"):
        return None
    days = 5 if state.get("last_contact_type") == "FU1" else 2
    return _business_days_after(state.get("sent_at"), days)


def _hourly_value(catalog: dict[str, Any], state: Optional[dict[str, Any]]) -> dict[str, Any]:
    state = state or {}
    minutes_spent = int(state.get("minutes_spent") or 0)
    amount = state.get("outcome_amount")
    if minutes_spent > 0 and amount is not None:
        realized = float(amount) / (minutes_spent / 60.0)
        return {
            "value": round(realized, 2),
            "kind": "realized",
            "basis": "recorded outcome amount divided by user-tracked minutes",
        }
    minutes = int(state.get("estimated_fulfillment_minutes") or catalog.get("estimated_fulfillment_minutes") or DEFAULT_FULFILLMENT_MINUTES)
    minutes += int(catalog.get("estimated_outreach_minutes") or DEFAULT_OUTREACH_MINUTES)
    offer = float(catalog.get("offer_price") or 0)
    modeled = offer / (minutes / 60.0) if minutes > 0 else 0.0
    return {
        "value": round(modeled, 2),
        "kind": "modeled_offer_value",
        "basis": "proposed offer divided by model-assumption outreach + fulfillment time; not expected or guaranteed earnings",
        "minutes": minutes,
    }


def _queue_score(catalog: dict[str, Any], state: Optional[dict[str, Any]], pipeline: Optional[dict[str, Any]]) -> dict[str, Any]:
    state = state or {}
    status = str(state.get("status") or "CONTACT READY")
    due = _follow_due(state)
    now = datetime.now(timezone.utc)
    stage_boost = 0
    if status == "REPLIED":
        stage_boost = 1000
    elif due and due <= now:
        stage_boost = 800
    elif status == "SENT":
        stage_boost = -40
    elif status in {"WON / PAID", "SKIP"}:
        stage_boost = -1000
    learned = int((pipeline or {}).get("final_score") or catalog.get("fit") or 50)
    deliverability = int(catalog.get("deliverability") or 50)
    freshness = _freshness_score(catalog)
    hourly = _hourly_value(catalog, state)
    value_density = max(0, min(100, float(hourly["value"])))
    base = learned * 0.45 + deliverability * 0.15 + freshness * 0.15 + value_density * 0.25
    return {
        "score": round(base + stage_boost, 2),
        "components": {
            "learned_fit": learned,
            "deliverability": deliverability,
            "freshness": freshness,
            "hourly_value_density": round(value_density, 2),
            "stage_boost": stage_boost,
        },
        "hourly": hourly,
        "follow_up_due_at": due.isoformat() if due else None,
    }


def _catalog_public(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    out["evidence"] = _loads(out.pop("evidence_json", None), {})
    out["requires_postal"] = bool(out.get("requires_postal"))
    out["freshness_score"] = _freshness_score(out)
    return out


def _state_public(row: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if not row:
        return None
    out = dict(row)
    out["verified"] = bool(out.get("verified"))
    return out


def _record_prospect_event(conn: Any, user_id: int, catalog: dict[str, Any], event_type: str, payload: dict[str, Any]) -> None:
    conn.execute(
        "INSERT INTO prospect_events(user_id,prospect_id,opportunity_id,event_type,payload_json,created_at) VALUES(?,?,?,?,?,?)",
        (user_id, catalog["prospect_id"], catalog["opportunity_id"], event_type, _dumps(payload), _now_iso()),
    )


def _record_outcome_once(conn: Any, core: Any, user_id: int, opportunity_id: str, stage: str, notes: str, amount: Optional[float], occurred_at: str) -> None:
    recent = conn.execute(
        "SELECT 1 FROM outcomes WHERE user_id=? AND opportunity_id=? AND stage=? AND occurred_at=? LIMIT 1",
        (user_id, opportunity_id, stage, occurred_at),
    ).fetchone()
    if recent:
        return
    conn.execute(
        "INSERT INTO outcomes(user_id,opportunity_id,stage,notes,amount,occurred_at,created_at) VALUES(?,?,?,?,?,?,?)",
        (user_id, opportunity_id, stage, notes, amount, occurred_at, core.now_iso()),
    )


def _advance_loop_for_state(conn: Any, core: Any, user_id: int, catalog: dict[str, Any], old: dict[str, Any], new: dict[str, Any], event_type: str) -> None:
    oid = catalog["opportunity_id"]
    status = str(new.get("status") or "")
    old_status = str(old.get("status") or "")

    if status == "SENT" and (old_status != "SENT" or old.get("sent_at") != new.get("sent_at")):
        occurred = new.get("sent_at") or core.now_iso()
        pipeline = cashh_loop._upsert_pipeline(conn, core, user_id, oid, "acted")
        cashh_loop._record_event(conn, core, user_id, oid, "actioned", pipeline["stage"], {
            "channel": "email",
            "source": "prospect_engine",
            "prospect_id": catalog["prospect_id"],
            "occurred_at": occurred,
        })
        _record_outcome_once(conn, core, user_id, oid, "contacted", new.get("notes") or "Prospect Engine marked outreach sent.", None, occurred)

    if status == "REPLIED" and (old_status != "REPLIED" or old.get("replied_at") != new.get("replied_at")):
        occurred = new.get("replied_at") or core.now_iso()
        response_data = {
            "response_type": "reply",
            "notes": new.get("notes") or "Prospect Engine marked a reply.",
            "occurred_at": occurred,
            "prospect_id": catalog["prospect_id"],
        }
        pipeline = cashh_loop._upsert_pipeline(
            conn, core, user_id, oid, "responded", last_response_json=_dumps(response_data)
        )
        cashh_loop._record_event(conn, core, user_id, oid, "response", pipeline["stage"], response_data)
        _record_outcome_once(conn, core, user_id, oid, "replied", response_data["notes"], None, occurred)

    outcome_stage = new.get("outcome_stage")
    if outcome_stage and (
        old.get("outcome_stage") != outcome_stage
        or old.get("outcome_amount") != new.get("outcome_amount")
    ):
        occurred = core.now_iso()
        amount = new.get("outcome_amount")
        _record_outcome_once(conn, core, user_id, oid, outcome_stage, new.get("notes") or "Prospect Engine outcome.", amount, occurred)
        pipeline = cashh_loop._upsert_pipeline(
            conn,
            core,
            user_id,
            oid,
            "outcome_recorded",
            latest_outcome_stage=outcome_stage,
            latest_outcome_amount=amount,
        )
        cashh_loop._record_event(conn, core, user_id, oid, "outcome", pipeline["stage"], {
            "stage": outcome_stage,
            "amount": amount,
            "source": "prospect_engine",
            "prospect_id": catalog["prospect_id"],
        })
        opportunity = dict(conn.execute("SELECT * FROM opportunities WHERE id=?", (oid,)).fetchone())
        profile = core.get_profile(conn, user_id)
        base_score = core.personalized_score(opportunity, profile)
        learning = cashh_loop._learning_adjustment(conn, user_id, opportunity)
        final_score = cashh_loop._clamp_score(base_score + learning["adjustment"])
        pipeline = cashh_loop._upsert_pipeline(
            conn,
            core,
            user_id,
            oid,
            "learned",
            base_score=base_score,
            learned_adjustment=learning["adjustment"],
            final_score=final_score,
            latest_outcome_stage=outcome_stage,
            latest_outcome_amount=amount,
        )
        cashh_loop._record_event(conn, core, user_id, oid, "learned", pipeline["stage"], {
            "learning": learning,
            "score": final_score,
            "source": "prospect_engine",
        })

    if event_type:
        _record_prospect_event(conn, user_id, catalog, event_type, {
            "status": status,
            "outcome_stage": new.get("outcome_stage"),
            "outcome_amount": new.get("outcome_amount"),
            "minutes_spent": new.get("minutes_spent"),
        })


def _is_safe_public_url(url: Optional[str]) -> bool:
    if not url:
        return False
    try:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return False
        host = parsed.hostname.lower().rstrip(".")
        if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
            return False
        try:
            literal = ipaddress.ip_address(host)
            return not (literal.is_private or literal.is_loopback or literal.is_link_local or literal.is_reserved)
        except ValueError:
            pass
        infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
        for info in infos:
            address = ipaddress.ip_address(info[4][0])
            if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved:
                return False
        return True
    except Exception:
        return False


def _refresh_one(core: Any, prospect_id: str) -> dict[str, Any]:
    with core.db() as conn:
        row = conn.execute("SELECT * FROM prospect_catalog WHERE prospect_id=?", (prospect_id,)).fetchone()
        if not row:
            raise KeyError(prospect_id)
        catalog = dict(row)
    url = catalog.get("source_url") or catalog.get("website")
    checked_at = core.now_iso()
    http_status: Optional[int] = None
    final_url = url
    if not _is_safe_public_url(url):
        freshness = "error"
        detail = "Source URL is missing or failed public-network safety checks."
    else:
        try:
            response = requests.head(
                url,
                timeout=HTTP_TIMEOUT_SECONDS,
                allow_redirects=True,
                headers={"User-Agent": "CashhRadarEvidenceBot/1.0 (+source-freshness-check)"},
            )
            http_status = response.status_code
            final_url = response.url or url
            if response.status_code == 405:
                response = requests.get(
                    url,
                    timeout=HTTP_TIMEOUT_SECONDS,
                    allow_redirects=True,
                    stream=True,
                    headers={"User-Agent": "CashhRadarEvidenceBot/1.0 (+source-freshness-check)"},
                )
                http_status = response.status_code
                final_url = response.url or url
                response.close()
            if 200 <= int(http_status or 0) < 300:
                freshness = "current"
                detail = "Public source responded successfully."
            elif 300 <= int(http_status or 0) < 400:
                freshness = "redirected"
                detail = "Public source redirected; canonical destination remains reachable."
            elif int(http_status or 0) in {401, 403, 429}:
                freshness = "restricted"
                detail = "Source exists but automated freshness verification was restricted."
            elif int(http_status or 0) in {404, 410}:
                freshness = "unavailable"
                detail = "Source returned a not-found/gone response."
            else:
                freshness = "error"
                detail = f"Source returned HTTP {http_status}."
        except Exception as exc:
            freshness = "error"
            detail = f"Source check failed: {type(exc).__name__}."

    with core.db() as conn:
        prior = conn.execute("SELECT * FROM prospect_catalog WHERE prospect_id=?", (prospect_id,)).fetchone()
        conn.execute(
            "UPDATE prospect_catalog SET freshness_status=?,last_checked_at=?,last_http_status=?,updated_at=? WHERE prospect_id=?",
            (freshness, checked_at, http_status, checked_at, prospect_id),
        )
        if freshness in {"current", "redirected"}:
            conn.execute(
                "UPDATE opportunities SET last_seen=?,source_url=COALESCE(?,source_url),updated_at=? WHERE id=?",
                (checked_at, final_url, checked_at, catalog["opportunity_id"]),
            )
        if prior and prior["freshness_status"] != freshness:
            row = conn.execute("SELECT content_hash FROM opportunities WHERE id=?", (catalog["opportunity_id"],)).fetchone()
            conn.execute(
                "INSERT INTO opportunity_changes(opportunity_id,old_hash,new_hash,change_json,detected_at) VALUES(?,?,?,?,?)",
                (
                    catalog["opportunity_id"],
                    row["content_hash"] if row else None,
                    row["content_hash"] if row else None,
                    _dumps({"kind": "freshness_status", "from": prior["freshness_status"], "to": freshness, "http_status": http_status}),
                    checked_at,
                ),
            )
    return {
        "prospect_id": prospect_id,
        "opportunity_id": catalog["opportunity_id"],
        "freshness_status": freshness,
        "http_status": http_status,
        "checked_at": checked_at,
        "detail": detail,
    }


def refresh_due_batch(core: Any, limit: int = REFRESH_BATCH) -> dict[str, Any]:
    limit = max(1, min(100, int(limit)))
    started = core.now_iso()
    with core.db() as conn:
        run_id = conn.execute(
            "INSERT INTO prospect_refresh_runs(started_at) VALUES(?)", (started,)
        ).lastrowid
        rows = conn.execute(
            "SELECT prospect_id FROM prospect_catalog ORDER BY CASE WHEN last_checked_at IS NULL THEN 0 ELSE 1 END,last_checked_at ASC,priority ASC LIMIT ?",
            (limit,),
        ).fetchall()
    counts = {"current": 0, "redirected": 0, "restricted": 0, "unavailable": 0, "error": 0}
    results = []
    for row in rows:
        try:
            item = _refresh_one(core, row["prospect_id"])
        except Exception as exc:
            item = {"prospect_id": row["prospect_id"], "freshness_status": "error", "detail": type(exc).__name__}
        counts[item.get("freshness_status", "error")] = counts.get(item.get("freshness_status", "error"), 0) + 1
        results.append(item)
    finished = core.now_iso()
    with core.db() as conn:
        conn.execute(
            "UPDATE prospect_refresh_runs SET checked_count=?,current_count=?,restricted_count=?,unavailable_count=?,error_count=?,finished_at=? WHERE id=?",
            (
                len(results),
                counts.get("current", 0) + counts.get("redirected", 0),
                counts.get("restricted", 0),
                counts.get("unavailable", 0),
                counts.get("error", 0),
                finished,
                run_id,
            ),
        )
    return {"run_id": run_id, "checked": len(results), "counts": counts, "finished_at": finished, "results": results}


def _generic_hourly_value(opportunity: dict[str, Any]) -> Optional[float]:
    low = opportunity.get("income_min")
    high = opportunity.get("income_max")
    if low is None and high is None:
        return None
    value = (float(low or high) + float(high or low)) / 2.0
    period = str(opportunity.get("income_period") or "").lower()
    divisor = {"hour": 1, "day": 8, "week": 40, "month": 173.3, "year": 2080}.get(period)
    if not divisor:
        return None
    return round(value / divisor, 2)


def _scheduler_loop(core: Any) -> None:
    # Run soon after boot, then refresh a bounded rotating batch. This is intentionally
    # one-process launch behavior; multi-instance scale should move it to a shared worker.
    time.sleep(5)
    while True:
        try:
            refresh_due_batch(core, REFRESH_BATCH)
        except Exception as exc:
            print(f"Cashh Radar prospect refresh failed: {exc}", flush=True)
        time.sleep(REFRESH_INTERVAL_SECONDS)


def start_prospect_bridge_scheduler(core: Any) -> None:
    global _scheduler_thread, _scheduler_started
    if _scheduler_started or not getattr(core, "SCHEDULER_ENABLED", False):
        return
    _scheduler_started = True
    _scheduler_thread = threading.Thread(
        target=_scheduler_loop,
        args=(core,),
        name="cashh-radar-prospect-refresh",
        daemon=True,
    )
    _scheduler_thread.start()


def register_prospect_bridge(app: FastAPI) -> FastAPI:
    if getattr(app.state, "prospect_bridge_registered", False):
        return app

    import app as core

    _ensure_schema(core)
    sync = _sync_catalog_from_bundle(core)
    app.state.prospect_bridge_registered = True
    app.state.prospect_catalog_sync = sync

    @app.get("/api/prospects/status")
    def prospect_bridge_status():
        with core.db() as conn:
            counts = conn.execute(
                "SELECT COUNT(*) total,SUM(CASE WHEN freshness_status IN ('current','redirected') THEN 1 ELSE 0 END) current_count,SUM(CASE WHEN freshness_status='restricted' THEN 1 ELSE 0 END) restricted_count,SUM(CASE WHEN freshness_status IN ('unavailable','error') THEN 1 ELSE 0 END) problem_count FROM prospect_catalog"
            ).fetchone()
            last_run = conn.execute("SELECT * FROM prospect_refresh_runs ORDER BY id DESC LIMIT 1").fetchone()
        return {
            "bridge": "unified",
            "campaign": CAMPAIGN,
            "catalog": dict(counts),
            "bundle_sync": app.state.prospect_catalog_sync,
            "last_refresh_run": dict(last_run) if last_run else None,
            "automatic_refresh": bool(core.SCHEDULER_ENABLED),
            "refresh_interval_seconds": REFRESH_INTERVAL_SECONDS,
            "refresh_batch": REFRESH_BATCH,
        }

    @app.get("/api/prospects/state")
    def get_prospect_state(request: Request):
        user = core.require_user(request)
        with core.db() as conn:
            rows = conn.execute(
                "SELECT * FROM prospect_user_state WHERE user_id=? ORDER BY updated_at DESC",
                (user["id"],),
            ).fetchall()
        return {"states": [_state_public(dict(row)) for row in rows]}

    @app.put("/api/prospects/state/{prospect_id}")
    def put_prospect_state(
        prospect_id: str,
        payload: ProspectStateIn,
        request: Request,
        x_csrf_token: Optional[str] = Header(default=None),
    ):
        user = core.require_user(request)
        core.require_csrf(request, user, x_csrf_token)
        updates = payload.model_dump(exclude_unset=True)
        event_type = str(updates.pop("event_type", "sync") or "sync")
        now = core.now_iso()
        with core.db() as conn:
            catalog_row = conn.execute("SELECT * FROM prospect_catalog WHERE prospect_id=?", (prospect_id,)).fetchone()
            if not catalog_row:
                raise HTTPException(404, "Source-backed prospect not found")
            catalog = dict(catalog_row)
            old_row = conn.execute(
                "SELECT * FROM prospect_user_state WHERE user_id=? AND prospect_id=?",
                (user["id"], prospect_id),
            ).fetchone()
            old = dict(old_row) if old_row else {}
            defaults = {
                "status": "CONTACT READY",
                "verified": 0,
                "contact_email": catalog.get("contact_email"),
                "script_type": None,
                "subject": None,
                "message": None,
                "prepared_at": None,
                "sent_at": None,
                "last_contact_type": None,
                "replied_at": None,
                "outcome_stage": None,
                "outcome_amount": None,
                "minutes_spent": 0,
                "estimated_fulfillment_minutes": None,
                "notes": "",
            }
            new = {**defaults, **old, **updates}
            new["verified"] = 1 if bool(new.get("verified")) else 0
            conn.execute(
                """
                INSERT INTO prospect_user_state(
                  user_id,prospect_id,status,verified,contact_email,script_type,subject,message,prepared_at,sent_at,
                  last_contact_type,replied_at,outcome_stage,outcome_amount,minutes_spent,estimated_fulfillment_minutes,
                  notes,last_synced_at,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(user_id,prospect_id) DO UPDATE SET
                  status=excluded.status,verified=excluded.verified,contact_email=excluded.contact_email,
                  script_type=excluded.script_type,subject=excluded.subject,message=excluded.message,
                  prepared_at=excluded.prepared_at,sent_at=excluded.sent_at,last_contact_type=excluded.last_contact_type,
                  replied_at=excluded.replied_at,outcome_stage=excluded.outcome_stage,outcome_amount=excluded.outcome_amount,
                  minutes_spent=excluded.minutes_spent,estimated_fulfillment_minutes=excluded.estimated_fulfillment_minutes,
                  notes=excluded.notes,last_synced_at=excluded.last_synced_at,updated_at=excluded.updated_at
                """,
                (
                    user["id"], prospect_id, new["status"], new["verified"], new["contact_email"], new["script_type"],
                    new["subject"], new["message"], new["prepared_at"], new["sent_at"], new["last_contact_type"],
                    new["replied_at"], new["outcome_stage"], new["outcome_amount"], int(new["minutes_spent"] or 0),
                    new["estimated_fulfillment_minutes"], new["notes"], now, old.get("created_at") or now, now,
                ),
            )
            persisted = dict(conn.execute(
                "SELECT * FROM prospect_user_state WHERE user_id=? AND prospect_id=?",
                (user["id"], prospect_id),
            ).fetchone())
            _advance_loop_for_state(conn, core, user["id"], catalog, old, persisted, event_type)
            pipeline = cashh_loop._pipeline_row(conn, user["id"], catalog["opportunity_id"])
            ranking = _queue_score(catalog, persisted, pipeline)
        return {
            "ok": True,
            "state": _state_public(persisted),
            "opportunity_id": catalog["opportunity_id"],
            "pipeline": cashh_loop._public_pipeline(pipeline),
            "ranking": ranking,
        }

    @app.get("/api/prospects/queue")
    def prospect_queue(request: Request, limit: int = Query(default=100, ge=1, le=500)):
        user = core.require_user(request)
        with core.db() as conn:
            rows = conn.execute("SELECT * FROM prospect_catalog").fetchall()
            states = {
                row["prospect_id"]: dict(row)
                for row in conn.execute("SELECT * FROM prospect_user_state WHERE user_id=?", (user["id"],)).fetchall()
            }
            pipelines = {
                row["opportunity_id"]: dict(row)
                for row in conn.execute("SELECT * FROM opportunity_pipeline WHERE user_id=?", (user["id"],)).fetchall()
            }
        items = []
        for row in rows:
            catalog = dict(row)
            state = states.get(catalog["prospect_id"])
            pipeline = pipelines.get(catalog["opportunity_id"])
            ranking = _queue_score(catalog, state, pipeline)
            items.append({
                "prospect": _catalog_public(catalog),
                "state": _state_public(state),
                "pipeline": cashh_loop._public_pipeline(pipeline),
                "ranking": ranking,
            })
        items.sort(key=lambda item: (-item["ranking"]["score"], item["prospect"]["priority"]))
        return {"count": len(items), "items": items[:limit]}

    @app.post("/api/prospects/{prospect_id}/refresh")
    def refresh_prospect(
        prospect_id: str,
        request: Request,
        x_csrf_token: Optional[str] = Header(default=None),
    ):
        user = core.require_user(request)
        core.require_csrf(request, user, x_csrf_token)
        try:
            result = _refresh_one(core, prospect_id)
        except KeyError:
            raise HTTPException(404, "Source-backed prospect not found")
        with core.db() as conn:
            catalog = dict(conn.execute("SELECT * FROM prospect_catalog WHERE prospect_id=?", (prospect_id,)).fetchone())
            _record_prospect_event(conn, user["id"], catalog, "evidence_refresh", result)
        return result

    @app.post("/api/prospects/refresh-batch")
    def refresh_prospect_batch(
        request: Request,
        limit: int = Query(default=REFRESH_BATCH, ge=1, le=100),
        x_csrf_token: Optional[str] = Header(default=None),
    ):
        user = core.require_admin(request)
        core.require_csrf(request, user, x_csrf_token)
        return refresh_due_batch(core, limit)

    @app.get("/api/radar/unified")
    def unified_radar(request: Request, limit: int = Query(default=40, ge=1, le=200)):
        user = core.require_user(request)
        with core.db() as conn:
            profile = core.get_profile(conn, user["id"])
            rows = conn.execute("SELECT * FROM opportunities WHERE status!='blocked'").fetchall()
            catalog_by_oid = {
                row["opportunity_id"]: dict(row)
                for row in conn.execute("SELECT * FROM prospect_catalog").fetchall()
            }
            state_by_pid = {
                row["prospect_id"]: dict(row)
                for row in conn.execute("SELECT * FROM prospect_user_state WHERE user_id=?", (user["id"],)).fetchall()
            }
            pipeline_by_oid = {
                row["opportunity_id"]: dict(row)
                for row in conn.execute("SELECT * FROM opportunity_pipeline WHERE user_id=?", (user["id"],)).fetchall()
            }
        items = []
        for row in rows:
            opp = core.opportunity_to_dict(row, profile)
            if opp["verification"]["status"] in {"expired", "blocked"}:
                continue
            catalog = catalog_by_oid.get(opp["id"])
            if catalog:
                state = state_by_pid.get(catalog["prospect_id"])
                ranking = _queue_score(catalog, state, pipeline_by_oid.get(opp["id"]))
                score = ranking["score"]
                hourly = ranking["hourly"]
                family = "client_prospect"
            else:
                hourly_value = _generic_hourly_value(opp)
                value_score = max(0, min(100, hourly_value or 0))
                score = round(opp["match"] * 0.75 + value_score * 0.25, 2)
                hourly = {
                    "value": hourly_value,
                    "kind": "normalized_source_compensation" if hourly_value is not None else "unknown",
                    "basis": "normalized from published/recorded compensation period when possible; not a guarantee",
                }
                family = "money_opportunity"
            items.append({
                "id": opp["id"],
                "title": opp["title"],
                "organization": opp["organization"],
                "category": opp["category"],
                "source_url": opp.get("source_url"),
                "source_family": family,
                "verification": opp["verification"],
                "match": opp["match"],
                "priority_score": score,
                "hourly": hourly,
                "pipeline": cashh_loop._public_pipeline(pipeline_by_oid.get(opp["id"])),
                "prospect_id": catalog["prospect_id"] if catalog else None,
            })
        items.sort(key=lambda item: item["priority_score"], reverse=True)
        prospect_count = sum(1 for item in items if item["source_family"] == "client_prospect")
        return {
            "count": len(items),
            "client_prospects": prospect_count,
            "other_money_opportunities": len(items) - prospect_count,
            "items": items[:limit],
            "ranking_note": "Priority combines fit/evidence and, where supportable, value-per-hour. Prospect offer-value models are assumptions until actual amount and tracked time are recorded.",
        }

    return app
