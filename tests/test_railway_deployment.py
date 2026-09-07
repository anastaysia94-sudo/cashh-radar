from pathlib import Path
import json


ROOT = Path(__file__).resolve().parents[1]


def test_railway_config_exists_and_uses_docker_backend():
    config = json.loads((ROOT / "railway.json").read_text(encoding="utf-8"))
    assert config["$schema"] == "https://railway.com/railway.schema.json"
    assert config["build"]["builder"] == "DOCKERFILE"
    assert config["build"]["dockerfilePath"] == "Dockerfile"


def test_railway_start_command_runs_canonical_fastapi_launcher():
    config = json.loads((ROOT / "railway.json").read_text(encoding="utf-8"))
    start = config["deploy"]["startCommand"]
    # launcher.py registers the canonical opportunity loop and mounts /prospects,
    # so Railway should expose the same application surface as Docker.
    assert "uvicorn launcher:app" in start
    assert "0.0.0.0" in start
    assert "--port 8000" in start
    assert "$PORT" not in start
    assert "${PORT:-8000}" not in start
    assert "proxy-headers" in start


def test_railway_uses_readiness_healthcheck():
    config = json.loads((ROOT / "railway.json").read_text(encoding="utf-8"))
    deploy = config["deploy"]
    assert deploy["healthcheckPath"] == "/api/health/ready"
    assert deploy["healthcheckTimeout"] >= 100
