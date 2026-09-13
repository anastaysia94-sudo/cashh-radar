"""Aggregate actual prospect performance from persisted user state."""
from __future__ import annotations

from typing import Any


BASIS = (
    "Actual revenue includes only prospects explicitly recorded as paid; proposed offers "
    "and estimates are excluded. Reply and paid conversion rates use the sent-outreach "
    "cohort only, so incomplete imported/manual records cannot push conversion above 100%. "
    "Realized portfolio hourly yield divides actual paid revenue by all tracked prospect "
    "work minutes, including unsuccessful work."
)


def summarize(conn: Any, user_id: int) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT
          COALESCE(SUM(CASE WHEN sent_at IS NOT NULL THEN 1 ELSE 0 END),0) sent_count,
          COALESCE(SUM(CASE WHEN sent_at IS NOT NULL AND replied_at IS NOT NULL THEN 1 ELSE 0 END),0) replied_count,
          COALESCE(SUM(CASE WHEN sent_at IS NOT NULL AND outcome_stage='paid' THEN 1 ELSE 0 END),0) paid_count,
          COALESCE(SUM(CASE WHEN outcome_stage='paid' THEN COALESCE(outcome_amount,0) ELSE 0 END),0) actual_revenue,
          COALESCE(SUM(COALESCE(minutes_spent,0)),0) tracked_minutes,
          MAX(updated_at) last_activity_at
        FROM prospect_user_state
        WHERE user_id=?
        """,
        (user_id,),
    ).fetchone()
    sent = int(row["sent_count"] or 0)
    replied = int(row["replied_count"] or 0)
    paid = int(row["paid_count"] or 0)
    revenue = float(row["actual_revenue"] or 0.0)
    minutes = int(row["tracked_minutes"] or 0)
    return {
        "sent_count": sent,
        "replied_count": replied,
        "paid_count": paid,
        "actual_revenue": round(revenue, 2),
        "tracked_minutes": minutes,
        "reply_rate_pct": round(replied / sent * 100.0, 2) if sent else None,
        "paid_rate_pct": round(paid / sent * 100.0, 2) if sent else None,
        "realized_portfolio_hourly": round(revenue / (minutes / 60.0), 2) if minutes else None,
        "last_activity_at": row["last_activity_at"],
        "basis": BASIS,
    }
