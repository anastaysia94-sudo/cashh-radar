from fastapi.testclient import TestClient

import launcher


client = TestClient(launcher.app)


def test_launch_status_json_is_public_safe():
    response = client.get("/api/launch/status")
    assert response.status_code == 200
    payload = response.json()

    assert payload["product"] == "Cashh Radar"
    assert payload["status"] == "live"
    assert payload["hosting"] == "Railway"
    assert payload["healthcheck"] == "/api/health/ready"
    assert payload["prospect_entrypoint"] == "/prospects/"
    assert "performance-aware" in " ".join(payload["protected_endpoints"])

    disallowed_keys = {
        "admin_password",
        "cashh_admin_password",
        "secret_key",
        "cashh_secret_key",
        "metrics_token",
        "api_key",
        "stripe_secret",
        "password_hash",
    }
    assert disallowed_keys.isdisjoint({key.lower() for key in payload})


def test_launch_status_page_renders_operator_links():
    response = client.get("/launch-status")
    assert response.status_code == 200
    text = response.text
    assert "Cashh Radar launch status" in text
    assert "/prospects/" in text
    assert "/api/health/ready" in text
    assert "No private account data" in text
