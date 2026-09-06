from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _repo_files():
    ignored_dirs = {".git", ".pytest_cache", "__pycache__", "node_modules", ".venv", "venv", "prospect-portal"}
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
        ROOT / ".vercel",
        ROOT / "prospect-portal",
    ]
    existing = [str(path.relative_to(ROOT)) for path in forbidden_paths if path.exists()]
    assert not existing, f"Remove static/cross-project paths: {existing}"


def test_repository_copy_blocks_lite_and_cross_project_copy():
    """Prevent future assistants from reintroducing the removed Lite/prospect launch copy."""
    forbidden_phrases = [
        "Cashh Radar " + "Lite",
        "No-Billing Launch",
        "no-billing public launch",
        "San Jose 200 High-Intent Prospect Portal",
        "prospects-1.csv",
    ]
    allowed_files = {
        Path("tests/test_render_only_repository.py"),
        Path("RENDER_DEPLOYMENT_STATUS.md"),
        Path("RENDER_BILLING_LAUNCH_RUNBOOK.md"),
        Path("NON_RENDER_DEPLOYMENT.md"),
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
    assert not hits, "Removed Lite/prospect wording reappeared: " + "; ".join(hits)
