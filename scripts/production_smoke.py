#!/usr/bin/env python3
"""Post-deployment smoke test for Cashh Radar.

Run this after the Render service is live:

    python scripts/production_smoke.py https://your-cashh-radar.onrender.com

Optional metrics check:

    python scripts/production_smoke.py https://your-cashh-radar.onrender.com --metrics-token "$CASHH_METRICS_TOKEN"

The script uses only Python standard-library modules so it can run from CI,
Render shell, GitHub Codespaces, or a basic laptop without extra packages.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


DEFAULT_TIMEOUT_SECONDS = 15


@dataclass(frozen=True)
class CheckTarget:
    path: str
    expected_status: int = 200
    expected_content_hint: Optional[str] = None
    description: str = ""
    requires_metrics_token: bool = False


TARGETS: List[CheckTarget] = [
    CheckTarget("/api/health/live", description="process liveness"),
    CheckTarget("/api/health/ready", description="database, schema, and config readiness"),
    CheckTarget("/api/health", description="combined health payload"),
    CheckTarget("/", expected_content_hint="Cashh Radar", description="main app shell"),
    CheckTarget("/manifest.json", expected_content_hint="Cashh Radar", description="PWA manifest"),
    CheckTarget("/sitemap.xml", expected_content_hint="urlset", description="SEO sitemap"),
    CheckTarget("/privacy", expected_content_hint="Privacy", description="privacy page"),
    CheckTarget("/terms", expected_content_hint="Terms", description="terms page"),
    CheckTarget("/disclosures", expected_content_hint="Disclosures", description="disclosures page"),
    CheckTarget("/security", expected_content_hint="Security", description="security page"),
    CheckTarget("/support", expected_content_hint="Support", description="support page"),
    CheckTarget("/api/metrics", description="protected metrics endpoint", requires_metrics_token=True),
]


@dataclass
class CheckResult:
    path: str
    status: str
    elapsed_ms: int
    detail: str


def normalize_base_url(raw_url: str) -> str:
    base = raw_url.strip()
    if not base:
        raise ValueError("Base URL is required")
    if not base.startswith(("http://", "https://")):
        base = "https://" + base
    return base.rstrip("/") + "/"


def fetch_text(url: str, timeout: int, headers: Optional[Dict[str, str]] = None) -> tuple[int, str]:
    request = Request(url, headers=headers or {})
    with urlopen(request, timeout=timeout) as response:  # nosec B310 - user-supplied smoke-test URL by design.
        raw_body = response.read(300_000)
        text = raw_body.decode("utf-8", errors="replace")
        return response.status, text


def run_target(base_url: str, target: CheckTarget, timeout: int, metrics_token: Optional[str]) -> CheckResult:
    url = urljoin(base_url, target.path.lstrip("/"))
    headers: Dict[str, str] = {"User-Agent": "cashh-radar-production-smoke/1.0"}
    if target.requires_metrics_token:
        if not metrics_token:
            return CheckResult(target.path, "SKIP", 0, "metrics token not provided")
        headers["Authorization"] = f"Bearer {metrics_token}"

    start = time.perf_counter()
    try:
        status, body = fetch_text(url, timeout=timeout, headers=headers)
    except HTTPError as exc:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return CheckResult(target.path, "FAIL", elapsed_ms, f"HTTP {exc.code}: {exc.reason}")
    except URLError as exc:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return CheckResult(target.path, "FAIL", elapsed_ms, f"URL error: {exc.reason}")
    except TimeoutError:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return CheckResult(target.path, "FAIL", elapsed_ms, "request timed out")
    except OSError as exc:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return CheckResult(target.path, "FAIL", elapsed_ms, f"network error: {exc}")

    elapsed_ms = int((time.perf_counter() - start) * 1000)
    if status != target.expected_status:
        return CheckResult(target.path, "FAIL", elapsed_ms, f"expected {target.expected_status}, got {status}")
    if target.expected_content_hint and target.expected_content_hint.lower() not in body.lower():
        return CheckResult(target.path, "FAIL", elapsed_ms, f"missing content hint: {target.expected_content_hint}")
    return CheckResult(target.path, "PASS", elapsed_ms, target.description or "ok")


def run_smoke(base_url: str, timeout: int, metrics_token: Optional[str]) -> List[CheckResult]:
    normalized = normalize_base_url(base_url)
    return [run_target(normalized, target, timeout, metrics_token) for target in TARGETS]


def print_results(results: Iterable[CheckResult]) -> int:
    rows = list(results)
    print("Cashh Radar production smoke test")
    print("=" * 36)
    for result in rows:
        print(f"{result.status:4} {result.path:24} {result.elapsed_ms:5}ms  {result.detail}")
    failed = [row for row in rows if row.status == "FAIL"]
    skipped = [row for row in rows if row.status == "SKIP"]
    print("-" * 36)
    print(json.dumps({"passed": len(rows) - len(failed) - len(skipped), "failed": len(failed), "skipped": len(skipped)}, indent=2))
    return 1 if failed else 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke-test a deployed Cashh Radar service.")
    parser.add_argument("base_url", help="Deployed base URL, for example https://cashh-radar.onrender.com")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS, help="Request timeout in seconds")
    parser.add_argument("--metrics-token", default=None, help="Optional CASHH_METRICS_TOKEN for /api/metrics")
    args = parser.parse_args(argv)
    results = run_smoke(args.base_url, args.timeout, args.metrics_token)
    return print_results(results)


if __name__ == "__main__":
    sys.exit(main())
