from scripts.production_smoke import TARGETS, LIVE_RAILWAY_URL, CheckResult, normalize_base_url, print_results


def test_production_smoke_targets_cover_launch_routes():
    paths = {target.path for target in TARGETS}
    assert "/" in paths
    assert "/api/health/live" in paths
    assert "/api/health/ready" in paths
    assert "/api/health" in paths
    assert "/api/launch/status" in paths
    assert "/launch-status" in paths
    assert "/manifest.json" in paths
    assert "/sitemap.xml" in paths
    assert "/privacy" in paths
    assert "/terms" in paths
    assert "/disclosures" in paths
    assert "/security" in paths
    assert "/support" in paths


def test_launch_status_targets_have_content_hints():
    hints = {target.path: target.expected_content_hint for target in TARGETS}
    assert hints["/api/launch/status"] == "Cashh Radar"
    assert hints["/launch-status"] == "Cashh Radar launch status"


def test_normalize_base_url_defaults_to_https_and_trailing_slash():
    assert normalize_base_url("cashh-radar-web-production.up.railway.app") == "https://cashh-radar-web-production.up.railway.app/"
    assert normalize_base_url(LIVE_RAILWAY_URL + "/") == LIVE_RAILWAY_URL + "/"


def test_print_results_fails_when_any_check_fails(capsys):
    code = print_results([
        CheckResult("/api/health/live", "PASS", 12, "ok"),
        CheckResult("/api/health/ready", "FAIL", 22, "not ready"),
        CheckResult("/api/metrics", "SKIP", 0, "metrics token not provided"),
    ])
    output = capsys.readouterr().out
    assert code == 1
    assert '"failed": 1' in output
    assert '"skipped": 1' in output
