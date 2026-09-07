from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_runner():
    runner_path = REPO_ROOT / "tools/standalone_apply_diff_and_run.py"
    spec = importlib.util.spec_from_file_location("standalone_apply_diff_and_run", runner_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_active_platform_lives_at_repository_root():
    required_root_dirs = [
        "apps",
        "shared_platform",
        "web",
        "native",
        "engine",
        "frontend",
        "db",
        "docs",
        "tasks",
        "corpus",
    ]
    for name in required_root_dirs:
        assert (REPO_ROOT / name).exists(), name

    alternate_container = REPO_ROOT / ("week" + "1")
    assert not alternate_container.exists()


def test_repository_branding_and_ci_are_root_based():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    workflow = (REPO_ROOT / ".github/workflows/contract-check.yml").read_text(encoding="utf-8")
    codeowners = (REPO_ROOT / ".github/CODEOWNERS").read_text(encoding="utf-8")

    assert "Universal Artichoke" in readme
    assert "Religion Dev" not in readme
    assert "working-directory:" not in workflow
    assert "/engine/" in codeowners
    assert "/frontend/" in codeowners


def test_standalone_runner_detects_repository_root_after_migration():
    runner = _load_runner()

    assert runner.detect_project_root() == REPO_ROOT
    assert runner.product_module("islam", project_root=REPO_ROOT) == "apps.islam.server:app"
    assert runner.product_module("simli", project_root=REPO_ROOT) == "apps.simli.server:app"
