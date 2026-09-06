from scripts.production_smoke import TARGETS, normalize_base_url, print_results, CheckResult


def test_production_smoke_targets_cover_launch_routes():
    paths = {target.path for target in TARGETS}
    assert "/" in paths
    assert "/api/health/live" in paths
    assert "/api/health/ready" in paths
    assert "/api/health" in paths
    assert "/manifest.json" in paths
    assert "/sitemap.xml" in paths
    assert "/privacy" in paths
    assert "/terms" in paths
    assert "/disclosures" in paths
    assert "/security" in paths
    assert "/support" in paths


def test_normalize_base_url_defaults_to_https_and_trailing_slash():
    assert normalize_base_url("cashh-radar.onrender.com") == "https://cashh-radar.onrender.com/"
    assert normalize_base_url("https://cashh-radar.onrender.com/") == "https://cashh-radar.onrender.com/"


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
