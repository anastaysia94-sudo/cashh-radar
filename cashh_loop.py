"""Canonical Cashh Radar opportunity-to-outcome loop.

This module connects the existing discovery, verification, scoring, Advisor,
outreach, response tracking, outcome, and analytics capabilities into one
stateful lifecycle:

    discovered -> verified -> scored -> explained -> action_ready
    -> acted -> responded -> outcome_recorded -> learned

It intentionally reuses the existing Cashh Radar data model. The loop is an
orchestration layer, not a second CRM.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field


STAGES = [
    "discovered",
    "verified",
    "scored",
    "explained",
    "action_ready",
    "acted",
    "responded",
    "outcome_recorded",
    "learned",
]
STAGE_RANK = {stage: index for index, stage in enumerate(STAGES)}

# Signals are intentionally bounded. Cashh Radar should learn from evidence,
# not let one success or rejection overwhelm the source/fit score.
OUTCOME_SIGNAL = {
    "saved": 0.00,
    "started": 0.05,
    "applied": 0.15,
    "contacted": 0.15,
    "replied": 0.40,
    "interview": 0.55,
    "negotiating": 0.70,
    "won": 0.90,
    "paid": 1.00,
    "fulfilled": 1.00,
    "follow_up": 0.80,
    "lost": -1.00,
}


class LoopRunIn(BaseModel):
    opportunity_id: str = Field(min_length=1, max_length=200)
    asset_type: str = Field(
        default="auto",
        pattern="^(auto|application_email|proposal|dm|follow_up)$",
    )
    generate_action: bool = True


class ActionedIn(BaseModel):
    channel: str = Field(default="source", min_length=1, max_length=80)
    notes: str = Field(default="", max_length=3000)
    external_reference: Optional[str] = Field(default=None, max_length=1000)
    occurred_at: Optional[str] = None


class ResponseIn(BaseModel):
    response_type: str = Field(
        pattern="^(reply|question|interview|accepted|rejected|no_response)$"
    )
    notes: str = Field(default="", max_length=3000)
    occurred_at: Optional[str] = None


class LoopOutcomeIn(BaseModel):
    stage: str = Field(
        pattern="^(saved|started|applied|contacted|replied|interview|negotiating|won|paid|fulfilled|follow_up|lost)$"
    )
    notes: str = Field(default="", max_length=3000)
    amount: Optional[float] = None
    occurred_at: Optional[str] = None


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


def _clamp_score(value: int) -> int:
    return max(0, min(100, int(value)))


def _later_stage(current: Optional[str], candidate: str) -> str:
    current = current if current in STAGE_RANK else "discovered"
    return candidate if STAGE_RANK[candidate] > STAGE_RANK[current] else current


def _ensure_schema(core: Any) -> None:
    schema = """
    CREATE TABLE IF NOT EXISTS opportunity_pipeline(
      user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      opportunity_id TEXT NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
      stage TEXT NOT NULL DEFAULT 'discovered',
      base_score INTEGER,
      learned_adjustment INTEGER NOT NULL DEFAULT 0,
      final_score INTEGER,
      verification_status TEXT,
      evidence_score INTEGER,
      explanation_json TEXT NOT NULL DEFAULT '{}',
      action_json TEXT NOT NULL DEFAULT '{}',
      last_response_json TEXT NOT NULL DEFAULT '{}',
      latest_outcome_stage TEXT,
      latest_outcome_amount REAL,
      first_seen_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      PRIMARY KEY(user_id, opportunity_id)
    );
    CREATE INDEX IF NOT EXISTS idx_opportunity_pipeline_stage_score
      ON opportunity_pipeline(user_id, stage, final_score);
    CREATE TABLE IF NOT EXISTS pipeline_events(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      opportunity_id TEXT NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
      event_type TEXT NOT NULL,
      stage TEXT NOT NULL,
      payload_json TEXT NOT NULL DEFAULT '{}',
      created_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_pipeline_events_user_opportunity
      ON pipeline_events(user_id, opportunity_id, id);
    """
    with core.db() as conn:
        conn.executescript(schema)
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations(version,name,applied_at) VALUES(?,?,?)",
            (5, "canonical_opportunity_loop", core.now_iso()),
        )


def _pipeline_row(conn: Any, user_id: int, opportunity_id: str) -> Optional[dict[str, Any]]:
    row = conn.execute(
        "SELECT * FROM opportunity_pipeline WHERE user_id=? AND opportunity_id=?",
        (user_id, opportunity_id),
    ).fetchone()
    return dict(row) if row else None


def _record_event(
    conn: Any,
    core: Any,
    user_id: int,
    opportunity_id: str,
    event_type: str,
    stage: str,
    payload: Optional[dict[str, Any]] = None,
) -> None:
    conn.execute(
        "INSERT INTO pipeline_events(user_id,opportunity_id,event_type,stage,payload_json,created_at) VALUES(?,?,?,?,?,?)",
        (user_id, opportunity_id, event_type, stage, _dumps(payload or {}), core.now_iso()),
    )
    conn.execute(
        "INSERT INTO analytics_events(user_id,event_name,metadata_json,created_at) VALUES(?,?,?,?)",
        (
            user_id,
            f"loop_{event_type}",
            _dumps({"opportunity_id": opportunity_id, "stage": stage}),
            core.now_iso(),
        ),
    )


def _upsert_pipeline(
    conn: Any,
    core: Any,
    user_id: int,
    opportunity_id: str,
    candidate_stage: str,
    **fields: Any,
) -> dict[str, Any]:
    existing = _pipeline_row(conn, user_id, opportunity_id)
    now = core.now_iso()
    current_stage = existing.get("stage") if existing else "discovered"
    stage = _later_stage(current_stage, candidate_stage)

    data: dict[str, Any] = {
        "base_score": existing.get("base_score") if existing else None,
        "learned_adjustment": existing.get("learned_adjustment", 0) if existing else 0,
        "final_score": existing.get("final_score") if existing else None,
        "verification_status": existing.get("verification_status") if existing else None,
        "evidence_score": existing.get("evidence_score") if existing else None,
        "explanation_json": existing.get("explanation_json", "{}") if existing else "{}",
        "action_json": existing.get("action_json", "{}") if existing else "{}",
        "last_response_json": existing.get("last_response_json", "{}") if existing else "{}",
        "latest_outcome_stage": existing.get("latest_outcome_stage") if existing else None,
        "latest_outcome_amount": existing.get("latest_outcome_amount") if existing else None,
    }
    data.update(fields)
    first_seen = existing.get("first_seen_at") if existing else now

    conn.execute(
        """
        INSERT INTO opportunity_pipeline(
          user_id,opportunity_id,stage,base_score,learned_adjustment,final_score,
          verification_status,evidence_score,explanation_json,action_json,
          last_response_json,latest_outcome_stage,latest_outcome_amount,
          first_seen_at,updated_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(user_id,opportunity_id) DO UPDATE SET
          stage=excluded.stage,
          base_score=excluded.base_score,
          learned_adjustment=excluded.learned_adjustment,
          final_score=excluded.final_score,
          verification_status=excluded.verification_status,
          evidence_score=excluded.evidence_score,
          explanation_json=excluded.explanation_json,
          action_json=excluded.action_json,
          last_response_json=excluded.last_response_json,
          latest_outcome_stage=excluded.latest_outcome_stage,
          latest_outcome_amount=excluded.latest_outcome_amount,
          updated_at=excluded.updated_at
        """,
        (
            user_id,
            opportunity_id,
            stage,
            data["base_score"],
            data["learned_adjustment"],
            data["final_score"],
            data["verification_status"],
            data["evidence_score"],
            data["explanation_json"],
            data["action_json"],
            data["last_response_json"],
            data["latest_outcome_stage"],
            data["latest_outcome_amount"],
            first_seen,
            now,
        ),
    )
    return _pipeline_row(conn, user_id, opportunity_id) or {}


def _learning_adjustment(conn: Any, user_id: int, opportunity: dict[str, Any]) -> dict[str, Any]:
    """Return a small personalized score adjustment from actual recorded outcomes.

    Only the latest outcome per prior opportunity is used so repeated stage logs do
    not count as independent successes. Similar category/mode/source outcomes carry
    more weight. Bayesian-style shrinkage toward zero prevents overreacting to a
    tiny sample.
    """
    rows = conn.execute(
        """
        SELECT x.stage, o.category, o.mode, o.source_key
        FROM outcomes x
        JOIN opportunities o ON o.id=x.opportunity_id
        JOIN (
          SELECT opportunity_id, MAX(id) AS latest_id
          FROM outcomes
          WHERE user_id=?
          GROUP BY opportunity_id
        ) latest ON latest.latest_id=x.id
        WHERE x.user_id=? AND x.opportunity_id<>?
        """,
        (user_id, user_id, opportunity["id"]),
    ).fetchall()

    weighted_signal = 0.0
    total_weight = 0.0
    relevant = 0
    positive = 0
    negative = 0
    for row in rows:
        stage = row["stage"]
        signal = OUTCOME_SIGNAL.get(stage)
        if signal is None:
            continue
        weight = 1.0
        if row["category"] == opportunity.get("category"):
            weight += 1.5
        if row["mode"] == opportunity.get("mode"):
            weight += 0.5
        if row["source_key"] == opportunity.get("source_key"):
            weight += 0.5
        if weight <= 1.0:
            # Unrelated history is deliberately excluded from personalization.
            continue
        relevant += 1
        positive += 1 if signal > 0.35 else 0
        negative += 1 if signal < 0 else 0
        weighted_signal += signal * weight
        total_weight += weight

    # Prior weight=4 is conservative: a few wins can help, but cannot dominate.
    shrunk = weighted_signal / (total_weight + 4.0) if total_weight else 0.0
    adjustment = max(-10, min(10, round(shrunk * 10)))
    return {
        "adjustment": adjustment,
        "relevant_samples": relevant,
        "positive_samples": positive,
        "negative_samples": negative,
        "signal": round(shrunk, 3),
        "method": "latest outcome per prior opportunity; similarity-weighted; shrunk toward zero; capped at +/-10",
    }


def _infer_action_type(opportunity: dict[str, Any], requested: str) -> str:
    if requested != "auto":
        return requested
    text = f"{opportunity.get('category','')} {opportunity.get('title','')}".lower()
    if "grant" in text or opportunity.get("mode") == "organization":
        return "application_email"
    if any(token in text for token in ("employment", "job", "position", "career")):
        return "application_email"
    if any(token in text for token in ("freelance", "contract", "service", "business", "client")):
        return "proposal"
    return "dm"


def _build_action(opportunity: dict[str, Any], asset_type: str) -> dict[str, Any]:
    title = opportunity.get("title") or "this opportunity"
    org = opportunity.get("organization") or "the organization"
    category = (opportunity.get("category") or "").lower()
    source_url = opportunity.get("source_url")
    source_steps = _loads(opportunity.get("steps_json"), opportunity.get("steps") or [])

    if "grant" in category or opportunity.get("mode") == "organization":
        return {
            "kind": "apply",
            "asset_type": "application_email",
            "primary_action": "Open the canonical funding notice and build a compliance checklist before drafting anything.",
            "content": "",
            "next_steps": source_steps[:5] or [
                "Open the canonical notice",
                "Confirm applicant eligibility",
                "List required documents and deadlines",
                "Map requirements to evidence",
                "Submit only through the official workflow",
            ],
            "source_url": source_url,
        }

    if asset_type == "application_email":
        content = (
            f"Hello {org} hiring team,\n\n"
            f"I'm interested in the {title} opportunity. I reviewed the published "
            "requirements and would like to be considered. I can provide a role-specific "
            "resume and any requested supporting materials.\n\n"
            "Thank you for your consideration."
        )
        primary = "Review the canonical posting, tailor the application to its stated requirements, and apply through the official source."
    elif asset_type == "proposal":
        content = (
            f"Hello,\n\nI'm reaching out regarding {title}. Before proceeding, I'd like "
            "to confirm the exact scope, deliverables, timeline, eligibility, and compensation "
            "terms. If there is a fit, I can send a concise plan tied to the stated requirements.\n\nBest,"
        )
        primary = "Send a truthful, specific proposal only after confirming scope and payment terms."
    elif asset_type == "follow_up":
        content = (
            f"Hello,\n\nFollowing up on my interest in {title}. I wanted to confirm whether "
            "the opportunity is still active and whether you need anything else from me.\n\nThank you."
        )
        primary = "Follow up once with a concise status question, then record the response."
    else:
        content = (
            f"Hi — I saw the {title} opportunity from {org}. I'm interested and have reviewed "
            "the source details. What is the best next step to be considered?"
        )
        primary = "Use the source-approved contact channel and ask for the next concrete step."

    return {
        "kind": "outreach",
        "asset_type": asset_type,
        "primary_action": primary,
        "content": content,
        "next_steps": source_steps[:5] or [
            "Verify the source and eligibility",
            "Personalize with truthful qualifications",
            "Take the action through the official or permitted channel",
            "Record the action in Cashh Radar",
            "Track the response and record the outcome",
        ],
        "source_url": source_url,
    }


def _explanation(opportunity: dict[str, Any], verification: dict[str, Any], base_score: int, learning: dict[str, Any], final_score: int) -> dict[str, Any]:
    reasons = []
    if opportunity.get("why"):
        reasons.append(opportunity["why"])
    reasons.append(
        f"Verification is {verification['status']} with evidence score {verification['evidence_score']}/100."
    )
    if learning["relevant_samples"]:
        direction = "raised" if learning["adjustment"] > 0 else "lowered" if learning["adjustment"] < 0 else "did not change"
        reasons.append(
            f"Your recorded outcomes {direction} this score by {abs(learning['adjustment'])} point(s) across {learning['relevant_samples']} relevant prior opportunity/opportunities."
        )
    else:
        reasons.append("No sufficiently similar recorded outcomes exist yet, so learning does not alter the score.")
    return {
        "summary": f"Cashh Radar score: {final_score}/100 (fit/evidence base {base_score}, learned adjustment {learning['adjustment']:+d}).",
        "reasons": reasons,
        "risks": opportunity.get("risks") or "Review the canonical source for restrictions, eligibility, and changing terms.",
        "eligibility": opportunity.get("eligibility") or "Confirm eligibility at the canonical source before acting.",
        "learning": learning,
        "disclaimer": "This is decision support based on source evidence and your recorded outcomes; it does not guarantee earnings, acceptance, eligibility, or a reply.",
    }


def _public_pipeline(row: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if not row:
        return None
    out = dict(row)
    out["explanation"] = _loads(out.pop("explanation_json", None), {})
    out["action"] = _loads(out.pop("action_json", None), {})
    out["last_response"] = _loads(out.pop("last_response_json", None), {})
    return out


def register_cashh_loop(app: FastAPI) -> FastAPI:
    """Attach the canonical loop routes once to the existing Cashh Radar app."""
    if getattr(app.state, "cashh_loop_registered", False):
        return app

    import app as core

    _ensure_schema(core)
    app.state.cashh_loop_registered = True

    @app.post("/api/loop/run")
    def run_loop(payload: LoopRunIn, request: Request, x_csrf_token: Optional[str] = Header(default=None)):
        user = core.require_user(request)
        core.require_csrf(request, user, x_csrf_token)
        with core.db() as conn:
            row = conn.execute("SELECT * FROM opportunities WHERE id=? AND status!='blocked'", (payload.opportunity_id,)).fetchone()
            if not row:
                raise HTTPException(404, "Opportunity not found")
            opportunity = dict(row)
            profile = core.get_profile(conn, user["id"])
            verification = core.verification_state(opportunity)
            base_score = core.personalized_score(opportunity, profile)
            learning = _learning_adjustment(conn, user["id"], opportunity)
            final_score = _clamp_score(base_score + learning["adjustment"])
            explanation = _explanation(opportunity, verification, base_score, learning, final_score)
            inferred = _infer_action_type(opportunity, payload.asset_type)
            action = _build_action(opportunity, inferred) if payload.generate_action else {}

            # The loop always records discovery. Verification is evidence-aware; even a
            # stale/unverified item still advances to scoring so the user sees why it is weak.
            pipeline = _upsert_pipeline(
                conn,
                core,
                user["id"],
                opportunity["id"],
                "action_ready" if action else "explained",
                base_score=base_score,
                learned_adjustment=learning["adjustment"],
                final_score=final_score,
                verification_status=verification["status"],
                evidence_score=verification["evidence_score"],
                explanation_json=_dumps(explanation),
                action_json=_dumps(action),
            )
            if action.get("kind") == "outreach" and action.get("content"):
                asset_type = action.get("asset_type") or "dm"
                conn.execute(
                    "INSERT INTO outreach_assets(user_id,opportunity_id,asset_type,content,created_at) VALUES(?,?,?,?,?)",
                    (user["id"], opportunity["id"], asset_type, action["content"], core.now_iso()),
                )
            _record_event(
                conn,
                core,
                user["id"],
                opportunity["id"],
                "run",
                pipeline["stage"],
                {
                    "verification": verification,
                    "base_score": base_score,
                    "learned_adjustment": learning["adjustment"],
                    "final_score": final_score,
                    "action_kind": action.get("kind"),
                },
            )
        return {
            "opportunity_id": opportunity["id"],
            "stage": pipeline["stage"],
            "verification": verification,
            "base_score": base_score,
            "learned_adjustment": learning["adjustment"],
            "score": final_score,
            "explanation": explanation,
            "action": action,
            "next": "Record the action after it is actually sent/submitted; then record any response and final outcome.",
        }

    @app.get("/api/loop")
    def list_loop(request: Request):
        user = core.require_user(request)
        with core.db() as conn:
            rows = conn.execute(
                """
                SELECT p.*, o.title, o.organization, o.category, o.source_url
                FROM opportunity_pipeline p
                JOIN opportunities o ON o.id=p.opportunity_id
                WHERE p.user_id=?
                ORDER BY COALESCE(p.final_score,0) DESC, p.updated_at DESC
                """,
                (user["id"],),
            ).fetchall()
        return {"pipeline": [_public_pipeline(dict(row)) for row in rows]}

    @app.get("/api/loop-learning")
    def loop_learning(request: Request):
        user = core.require_user(request)
        with core.db() as conn:
            rows = conn.execute(
                """
                SELECT x.stage, o.category, o.mode, o.source_key, COUNT(*) AS count
                FROM outcomes x
                JOIN opportunities o ON o.id=x.opportunity_id
                JOIN (
                  SELECT opportunity_id, MAX(id) AS latest_id
                  FROM outcomes WHERE user_id=? GROUP BY opportunity_id
                ) latest ON latest.latest_id=x.id
                WHERE x.user_id=?
                GROUP BY x.stage,o.category,o.mode,o.source_key
                ORDER BY count DESC
                """,
                (user["id"], user["id"]),
            ).fetchall()
        groups = []
        for row in rows:
            d = dict(row)
            d["signal"] = OUTCOME_SIGNAL.get(d["stage"], 0.0)
            groups.append(d)
        return {
            "groups": groups,
            "method": "The latest recorded outcome per opportunity becomes a bounded similarity signal for future scores; source evidence and user fit remain primary.",
            "cap": 10,
        }

    @app.get("/api/loop/{opportunity_id}")
    def loop_detail(opportunity_id: str, request: Request):
        user = core.require_user(request)
        with core.db() as conn:
            pipeline = _pipeline_row(conn, user["id"], opportunity_id)
            if not pipeline:
                raise HTTPException(404, "Opportunity has not entered the canonical loop yet")
            events = [
                {**dict(row), "payload": _loads(row["payload_json"], {})}
                for row in conn.execute(
                    "SELECT * FROM pipeline_events WHERE user_id=? AND opportunity_id=? ORDER BY id",
                    (user["id"], opportunity_id),
                ).fetchall()
            ]
            outcomes = [
                dict(row)
                for row in conn.execute(
                    "SELECT * FROM outcomes WHERE user_id=? AND opportunity_id=? ORDER BY id",
                    (user["id"], opportunity_id),
                ).fetchall()
            ]
        return {"pipeline": _public_pipeline(pipeline), "events": events, "outcomes": outcomes}

    @app.post("/api/loop/{opportunity_id}/actioned")
    def mark_actioned(opportunity_id: str, payload: ActionedIn, request: Request, x_csrf_token: Optional[str] = Header(default=None)):
        user = core.require_user(request)
        core.require_csrf(request, user, x_csrf_token)
        occurred_at = payload.occurred_at or core.now_iso()
        event_payload = {
            "channel": payload.channel,
            "notes": payload.notes,
            "external_reference": payload.external_reference,
            "occurred_at": occurred_at,
        }
        with core.db() as conn:
            if not conn.execute("SELECT 1 FROM opportunities WHERE id=?", (opportunity_id,)).fetchone():
                raise HTTPException(404, "Opportunity not found")
            pipeline = _upsert_pipeline(conn, core, user["id"], opportunity_id, "acted")
            _record_event(conn, core, user["id"], opportunity_id, "actioned", pipeline["stage"], event_payload)
            # Reuse the existing outcome system for funnel analytics without pretending
            # an action succeeded. 'contacted' means only that the user says it was sent.
            conn.execute(
                "INSERT INTO outcomes(user_id,opportunity_id,stage,notes,occurred_at,created_at) VALUES(?,?,?,?,?,?)",
                (user["id"], opportunity_id, "contacted", payload.notes, occurred_at, core.now_iso()),
            )
        return {"ok": True, "stage": pipeline["stage"], "recorded": "contacted"}

    @app.post("/api/loop/{opportunity_id}/response")
    def record_response(opportunity_id: str, payload: ResponseIn, request: Request, x_csrf_token: Optional[str] = Header(default=None)):
        user = core.require_user(request)
        core.require_csrf(request, user, x_csrf_token)
        occurred_at = payload.occurred_at or core.now_iso()
        response_data = {
            "type": payload.response_type,
            "notes": payload.notes,
            "occurred_at": occurred_at,
        }
        outcome_map = {
            "reply": "replied",
            "question": "replied",
            "interview": "interview",
            "accepted": "won",
            "rejected": "lost",
        }
        with core.db() as conn:
            if not conn.execute("SELECT 1 FROM opportunities WHERE id=?", (opportunity_id,)).fetchone():
                raise HTTPException(404, "Opportunity not found")
            pipeline = _upsert_pipeline(
                conn,
                core,
                user["id"],
                opportunity_id,
                "responded",
                last_response_json=_dumps(response_data),
            )
            _record_event(conn, core, user["id"], opportunity_id, "response", pipeline["stage"], response_data)
            mapped = outcome_map.get(payload.response_type)
            if mapped:
                conn.execute(
                    "INSERT INTO outcomes(user_id,opportunity_id,stage,notes,occurred_at,created_at) VALUES(?,?,?,?,?,?)",
                    (user["id"], opportunity_id, mapped, payload.notes, occurred_at, core.now_iso()),
                )
        return {"ok": True, "stage": pipeline["stage"], "response": response_data, "mapped_outcome_stage": mapped}

    @app.post("/api/loop/{opportunity_id}/outcome")
    def record_loop_outcome(opportunity_id: str, payload: LoopOutcomeIn, request: Request, x_csrf_token: Optional[str] = Header(default=None)):
        user = core.require_user(request)
        core.require_csrf(request, user, x_csrf_token)
        occurred_at = payload.occurred_at or core.now_iso()
        with core.db() as conn:
            row = conn.execute("SELECT * FROM opportunities WHERE id=?", (opportunity_id,)).fetchone()
            if not row:
                raise HTTPException(404, "Opportunity not found")
            conn.execute(
                "INSERT INTO outcomes(user_id,opportunity_id,stage,notes,amount,occurred_at,created_at) VALUES(?,?,?,?,?,?,?)",
                (user["id"], opportunity_id, payload.stage, payload.notes, payload.amount, occurred_at, core.now_iso()),
            )
            pipeline = _upsert_pipeline(
                conn,
                core,
                user["id"],
                opportunity_id,
                "outcome_recorded",
                latest_outcome_stage=payload.stage,
                latest_outcome_amount=payload.amount,
            )
            _record_event(
                conn,
                core,
                user["id"],
                opportunity_id,
                "outcome",
                pipeline["stage"],
                {"stage": payload.stage, "amount": payload.amount, "notes": payload.notes, "occurred_at": occurred_at},
            )

            # Recalculate after inserting the outcome. The just-recorded outcome is not
            # used to score itself, but it immediately becomes evidence for future runs.
            opportunity = dict(row)
            profile = core.get_profile(conn, user["id"])
            base_score = core.personalized_score(opportunity, profile)
            learning = _learning_adjustment(conn, user["id"], opportunity)
            final_score = _clamp_score(base_score + learning["adjustment"])
            pipeline = _upsert_pipeline(
                conn,
                core,
                user["id"],
                opportunity_id,
                "learned",
                base_score=base_score,
                learned_adjustment=learning["adjustment"],
                final_score=final_score,
                latest_outcome_stage=payload.stage,
                latest_outcome_amount=payload.amount,
            )
            _record_event(
                conn,
                core,
                user["id"],
                opportunity_id,
                "learned",
                pipeline["stage"],
                {"learning": learning, "score": final_score},
            )
        return {
            "ok": True,
            "stage": pipeline["stage"],
            "outcome": {"stage": payload.stage, "amount": payload.amount, "occurred_at": occurred_at},
            "learning": learning,
            "score": final_score,
            "effect": "This outcome is now part of the evidence used to rank sufficiently similar future opportunities.",
        }

    return app
