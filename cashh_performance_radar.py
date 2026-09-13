"""Performance-aware Cashh Radar ranking.

This layer learns only from the signed-in user's persisted prospect outcomes. It does
not turn modeled offer values into revenue and it refuses to overreact to tiny samples.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Optional

from fastapi import FastAPI, Query, Request

import cashh_loop
import cashh_prospect_bridge as prospect_bridge
from prospect_performance import summarize as summarize_prospect_performance

MIN_SEGMENT_SENT = 3
FULL_WEIGHT_SENT = 10
MAX_SEGMENT_ADJUSTMENT = 10.0


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _rate(part: int, whole: int) -> Optional[float]:
    return (part / whole) if whole else None


def segment_learning(conn: Any, user_id: int) -> dict[str, dict[str, Any]]:
    """Return industry learning with bounded, sample-aware score adjustments.

    Adjustments are relative to the user's own portfolio rates, not an external
    benchmark. Under three sent prospects in a segment, adjustment stays zero.
    At ten sent prospects the segment can receive the full bounded adjustment.
    Reply and paid conversion counts are restricted to the sent-outreach cohort so
    incomplete imports/manual records cannot create impossible conversion rates.
    """
    rows = conn.execute(
        """
        SELECT
          COALESCE(NULLIF(TRIM(c.industry),''),'Unknown') industry,
          s.sent_at,
          s.replied_at,
          s.outcome_stage,
          s.outcome_amount,
          COALESCE(s.minutes_spent,0) minutes_spent
        FROM prospect_user_state s
        JOIN prospect_catalog c ON c.prospect_id=s.prospect_id
        WHERE s.user_id=?
        """,
        (user_id,),
    ).fetchall()

    portfolio_sent = sum(1 for row in rows if row["sent_at"])
    portfolio_replied = sum(1 for row in rows if row["sent_at"] and row["replied_at"])
    portfolio_paid = sum(1 for row in rows if row["sent_at"] and row["outcome_stage"] == "paid")
    portfolio_reply_rate = _rate(portfolio_replied, portfolio_sent) or 0.0
    portfolio_paid_rate = _rate(portfolio_paid, portfolio_sent) or 0.0

    grouped: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"sent": 0, "replied": 0, "paid": 0, "revenue": 0.0, "minutes": 0}
    )
    for row in rows:
        group = grouped[row["industry"]]
        sent = bool(row["sent_at"])
        if sent:
            group["sent"] += 1
        if sent and row["replied_at"]:
            group["replied"] += 1
        if sent and row["outcome_stage"] == "paid":
            group["paid"] += 1
        # Real paid revenue remains real even if an imported/manual record is
        # missing sent_at; it simply cannot influence conversion-rate learning.
        if row["outcome_stage"] == "paid":
            group["revenue"] += float(row["outcome_amount"] or 0.0)
        group["minutes"] += int(row["minutes_spent"] or 0)

    output: dict[str, dict[str, Any]] = {}
    for industry, group in grouped.items():
        sent = group["sent"]
        reply_rate = _rate(group["replied"], sent)
        paid_rate = _rate(group["paid"], sent)
        adjustment = 0.0
        confidence = "insufficient_sample"
        weight = 0.0
        if sent >= MIN_SEGMENT_SENT:
            weight = min(1.0, sent / FULL_WEIGHT_SENT)
            reply_delta = (reply_rate or 0.0) - portfolio_reply_rate
            paid_delta = (paid_rate or 0.0) - portfolio_paid_rate
            raw = ((reply_delta * 15.0) + (paid_delta * 60.0)) * weight
            adjustment = round(_clamp(raw, -MAX_SEGMENT_ADJUSTMENT, MAX_SEGMENT_ADJUSTMENT), 2)
            confidence = "full" if sent >= FULL_WEIGHT_SENT else "growing"
        minutes = group["minutes"]
        realized_hourly = round(group["revenue"] / (minutes / 60.0), 2) if minutes else None
        output[industry] = {
            "sent_count": sent,
            "replied_count": group["replied"],
            "paid_count": group["paid"],
            "actual_revenue": round(group["revenue"], 2),
            "tracked_minutes": minutes,
            "reply_rate_pct": round((reply_rate or 0.0) * 100.0, 2) if sent else None,
            "paid_rate_pct": round((paid_rate or 0.0) * 100.0, 2) if sent else None,
            "realized_hourly": realized_hourly,
            "score_adjustment": adjustment,
            "confidence": confidence,
            "sample_weight": round(weight, 2),
            "basis": (
                "Adjustment compares this industry's observed reply and paid rates within the sent-outreach cohort with the user's own "
                "portfolio rates. It is zero below 3 sent prospects, ramps gradually through 10, and is capped at +/-10 points."
            ),
        }
    return output


def build_radar(core: Any, user_id: int, limit: int) -> dict[str, Any]:
    with core.db() as conn:
        profile = core.get_profile(conn, user_id)
        rows = conn.execute("SELECT * FROM opportunities WHERE status!='blocked'").fetchall()
        catalog_by_oid = {
            row["opportunity_id"]: dict(row)
            for row in conn.execute("SELECT * FROM prospect_catalog").fetchall()
        }
        state_by_pid = {
            row["prospect_id"]: dict(row)
            for row in conn.execute("SELECT * FROM prospect_user_state WHERE user_id=?", (user_id,)).fetchall()
        }
        pipeline_by_oid = {
            row["opportunity_id"]: dict(row)
            for row in conn.execute("SELECT * FROM opportunity_pipeline WHERE user_id=?", (user_id,)).fetchall()
        }
        performance = summarize_prospect_performance(conn, user_id)
        learning = segment_learning(conn, user_id)

    items = []
    for row in rows:
        opp = core.opportunity_to_dict(row, profile)
        if opp["verification"]["status"] in {"expired", "blocked"}:
            continue
        catalog = catalog_by_oid.get(opp["id"])
        empirical = None
        if catalog:
            state = state_by_pid.get(catalog["prospect_id"])
            ranking = prospect_bridge._queue_score(catalog, state, pipeline_by_oid.get(opp["id"]))
            empirical = learning.get(catalog.get("industry") or "Unknown")
            adjustment = float((empirical or {}).get("score_adjustment") or 0.0)
            score = round(ranking["score"] + adjustment, 2)
            hourly = ranking["hourly"]
            family = "client_prospect"
        else:
            hourly_value = prospect_bridge._generic_hourly_value(opp)
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
            "industry": catalog.get("industry") if catalog else None,
            "empirical_learning": empirical,
        })

    items.sort(key=lambda item: item["priority_score"], reverse=True)
    prospect_count = sum(1 for item in items if item["source_family"] == "client_prospect")
    learned_segments = [
        {"industry": industry, **stats}
        for industry, stats in learning.items()
        if stats["sent_count"] >= MIN_SEGMENT_SENT
    ]
    learned_segments.sort(key=lambda item: (-item["score_adjustment"], -item["sent_count"], item["industry"]))
    return {
        "count": len(items),
        "client_prospects": prospect_count,
        "other_money_opportunities": len(items) - prospect_count,
        "prospect_performance": performance,
        "segment_learning": learned_segments,
        "items": items[:limit],
        "ranking_note": (
            "Base prospect priority still uses learned fit, deliverability, evidence freshness, lifecycle urgency, and value density. "
            "When an industry has at least 3 sent prospects, a bounded +/-10 point empirical adjustment compares that industry's actual reply/paid rates within the sent-outreach cohort with the user's own portfolio. "
            "Modeled offer value remains an assumption until actual payment and tracked effort exist."
        ),
    }


def register_performance_radar(app: FastAPI) -> FastAPI:
    if getattr(app.state, "performance_radar_registered", False):
        return app
    import app as core
    app.state.performance_radar_registered = True

    @app.get("/api/radar/performance-aware")
    def performance_aware_radar(request: Request, limit: int = Query(default=40, ge=1, le=200)):
        user = core.require_user(request)
        return build_radar(core, user["id"], limit)

    return app
