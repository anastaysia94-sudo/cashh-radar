from pathlib import Path
import json


ROOT = Path(__file__).resolve().parents[1]


def test_vercel_entrypoint_imports_real_fastapi_app():
    entrypoint = ROOT / "api" / "index.py"
    text = entrypoint.read_text(encoding="utf-8")
    assert "from app import app" in text
    assert "CASHH_DB_PATH" in text
    assert "/tmp/cashh_radar.db" in text
    assert "Cashh Radar Lite" not in text


def test_vercel_routes_all_requests_to_backend_entrypoint():
    config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    assert config["functions"]["api/index.py"]["maxDuration"] >= 30
    assert config["routes"] == [{"src": "/(.*)", "dest": "api/index.py"}]


def test_vercel_adapter_does_not_restore_static_lite_front_door():
    assert not (ROOT / "public").exists()
    assert not (ROOT / "public" / "index.html").exists()
