from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _repo_files():
    ignored_dirs = {".git", ".pytest_cache", "__pycache__", "node_modules", ".venv", "venv"}
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in ignored_dirs for part in path.parts):
            continue
        yield path


def test_no_lite_or_cross_project_front_doors_are_committed():
    """Cashh Radar must stay the full backend app, not a static Lite/prospect portal."""
    forbidden_paths = [
        ROOT / "public",
        ROOT / "prospect-portal",
        ROOT / "vercel.json",
        ROOT / ".vercel",
    ]
    existing = [str(path.relative_to(ROOT)) for path in forbidden_paths if path.exists()]
    assert not existing, f"Remove non-Render/static/cross-project paths: {existing}"


def test_repository_copy_stays_render_only():
    """Prevent future assistants from reintroducing the removed Lite/Vercel launch copy."""
    forbidden_phrases = [
        "Cashh Radar " + "Lite",
        "No-Billing Launch",
        "no-billing public launch",
        "V" + "ercel",
    ]
    allowed_files = {
        Path("tests/test_render_only_repository.py"),
        Path("RENDER_DEPLOYMENT_STATUS.md"),
        Path("RENDER_BILLING_LAUNCH_RUNBOOK.md"),
    }
    hits = []
    for path in _repo_files():
        rel = path.relative_to(ROOT)
        if rel in allowed_files:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for phrase in forbidden_phrases:
            if phrase in text:
                hits.append(f"{rel}: {phrase}")
    assert not hits, "Removed Lite/Vercel wording reappeared: " + "; ".join(hits)
