#!/usr/bin/env python3
"""Run Cashh Radar scheduler-safe background jobs manually.

Examples:
  python scripts/run_jobs.py alerts
  python scripts/run_jobs.py sources
  python scripts/run_jobs.py backups
  python scripts/run_jobs.py all

For the recommended single-instance SQLite launch, CASHH_SCHEDULER_ENABLED=1
runs these inside the web service. This CLI is useful for maintenance/testing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app

ALLOWED=("maintenance","alerts","digests","sources","webhooks","backups")


def main() -> int:
    job=(sys.argv[1] if len(sys.argv)>1 else "all").strip().lower()
    jobs=list(ALLOWED) if job=="all" else [job]
    if any(j not in ALLOWED for j in jobs):
        print(f"Unknown job: {job}. Choose one of: all, {', '.join(ALLOWED)}", file=sys.stderr)
        return 2
    results=[]
    for name in jobs:
        try:
            results.append(app.run_background_job(name))
        except Exception as exc:
            results.append({"job":name,"status":"error","error":str(exc)})
    print(json.dumps(results,indent=2))
    return 1 if any(r.get("status")!="ok" for r in results) else 0


if __name__=="__main__":
    raise SystemExit(main())
