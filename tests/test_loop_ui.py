from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from cashh_loop_ui import SCRIPT_TAG, register_cashh_loop_ui


ROOT = Path(__file__).resolve().parents[1]


def test_loop_ui_is_injected_into_root_html_once():
    app = FastAPI()

    @app.get("/")
    def index():
        return HTMLResponse("<html><body><main>Cashh Radar</main></body></html>")

    register_cashh_loop_ui(app)
    register_cashh_loop_ui(app)
    response = TestClient(app).get("/")
    assert response.status_code == 200
    assert response.text.count(SCRIPT_TAG) == 1


def test_loop_ui_frontend_covers_full_canonical_lifecycle():
    text = (ROOT / "static" / "loop-ui.js").read_text(encoding="utf-8")
    required = [
        "/api/loop/run",
        "/api/loop-learning",
        "/actioned",
        "/response",
        "/outcome",
        "data-loop-run",
        "data-loop-actioned",
        "data-loop-response",
        "data-loop-outcome",
        "data-loop-history",
        "Generating a draft does not count as contacting anyone",
    ]
    for marker in required:
        assert marker in text


def test_production_entrypoints_register_loop_ui():
    for path in (ROOT / "launcher.py", ROOT / "main.py", ROOT / "api" / "index.py"):
        text = path.read_text(encoding="utf-8")
        assert "register_cashh_loop_ui" in text
