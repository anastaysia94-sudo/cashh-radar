from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_main_py_shims_to_real_app_for_railway_autodetect():
    text = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "from app import app" in text
    assert "FastAPI" in text
