from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = REPO_ROOT / "tools/standalone_apply_diff_and_run.py"
spec = importlib.util.spec_from_file_location("standalone_apply_diff_and_run", RUNNER_PATH)
assert spec is not None
runner = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(runner)


def test_standalone_runner_exposes_product_runtime_contract():
    project_root = runner.detect_project_root()

    assert runner.product_module("islam", project_root=project_root) == "apps.islam.server:app"
    assert runner.product_module("simli", project_root=project_root) == "apps.simli.server:app"
    assert runner.product_module("lawkey", project_root=project_root) == "apps.lawkey.server:app"
    assert runner.product_urls("simli", host="127.0.0.1", port=8063, project_root=project_root) == {
        "health": "http://127.0.0.1:8063/api/health",
        "landing": "http://127.0.0.1:8063/simli.html",
        "chat": "http://127.0.0.1:8063/simli-chat.html",
    }
    assert runner.product_urls("lawkey", host="127.0.0.1", port=8037, project_root=project_root) == {
        "health": "http://127.0.0.1:8037/api/health",
        "landing": "http://127.0.0.1:8037/",
        "chat": "http://127.0.0.1:8037/",
    }


def test_standalone_runner_parses_repository_root_diffs(tmp_path: Path):
    patch = tmp_path / "change.patch"
    patch.write_text(
        "\n".join(
            [
                "diff --git a/web/simli.html b/web/simli.html",
                "--- a/web/simli.html",
                "+++ b/web/simli.html",
                "@@ -1 +1 @@",
                "-old",
                "+new",
                "diff --git a/tools/standalone_apply_diff_and_run.py b/tools/standalone_apply_diff_and_run.py",
                "--- a/tools/standalone_apply_diff_and_run.py",
                "+++ b/tools/standalone_apply_diff_and_run.py",
                "@@ -1 +1 @@",
                "-old",
                "+new",
            ]
        ),
        encoding="utf-8",
    )

    paths = runner.parse_diff_paths(patch)

    assert paths == {
        Path("web/simli.html"),
        Path("tools/standalone_apply_diff_and_run.py"),
    }


def test_standalone_runner_resolves_db_override(monkeypatch, tmp_path: Path):
    project_root = runner.detect_project_root()
    db_path = tmp_path / "custom.sqlite3"
    db_path.write_bytes(b"sqlite fixture")
    monkeypatch.delenv("RELIGION_SIMLI_DB_PATH", raising=False)
    env = {}

    resolved = runner.resolve_product_db(
        "simli",
        db_path,
        env,
        project_root=project_root,
        allow_missing_db=False,
    )

    assert resolved == db_path.resolve()
    assert env["RELIGION_SIMLI_DB_PATH"] == str(db_path.resolve())


def test_standalone_runner_resolves_lawkey_original_db_alias(monkeypatch, tmp_path: Path):
    project_root = runner.detect_project_root()
    db_path = tmp_path / "precedents.sqlite3"
    db_path.write_bytes(b"sqlite fixture")
    monkeypatch.delenv("RELIGION_LAWKEY_DB_PATH", raising=False)
    env = {}

    resolved = runner.resolve_product_db(
        "lawkey",
        db_path,
        env,
        project_root=project_root,
        allow_missing_db=False,
    )

    assert resolved == db_path.resolve()
    assert env["RELIGION_LAWKEY_DB_PATH"] == str(db_path.resolve())


def test_standalone_lawkey_smoke_uses_light_original_route(monkeypatch):
    called: list[str] = []

    def fake_get_ok(url: str, *, label: str) -> None:
        called.append(f"{label}:{url}")

    monkeypatch.setattr(runner, "_get_ok", fake_get_ok)

    runner.smoke_server(
        "lawkey",
        {
            "health": "http://127.0.0.1:8037/api/health",
            "landing": "http://127.0.0.1:8037/",
            "chat": "http://127.0.0.1:8037/",
        },
    )

    assert "document_presets:http://127.0.0.1:8037/api/document-presets" in called
