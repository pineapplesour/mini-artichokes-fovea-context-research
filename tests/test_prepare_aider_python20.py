import json
import subprocess
from pathlib import Path

from tools.prepare_aider_python20 import materialize, select_tasks


def _git(argv: list[str], cwd: Path) -> str:
    return subprocess.run(argv, cwd=cwd, text=True, check=True, stdout=subprocess.PIPE).stdout.strip()


def _fake_source(root: Path) -> Path:
    source = root / "official"
    practice = source / "python" / "exercises" / "practice"
    for name in ("alpha", "beta", "gamma"):
        task = practice / name
        (task / ".meta").mkdir(parents=True)
        (task / ".docs").mkdir()
        (task / ".meta" / "config.json").write_text(
            json.dumps({"files": {"solution": [f"{name}.py"], "test": [f"{name}_test.py"], "example": [".meta/example.py"]}})
        )
        (task / ".meta" / "example.py").write_text("GOLD = True\n")
        (task / ".docs" / "instructions.md").write_text(f"Implement {name}.\n")
        (task / f"{name}.py").write_text("pass\n")
        (task / f"{name}_test.py").write_text("def test_placeholder(): assert True\n")
    _git(["git", "init", "--quiet"], source)
    _git(["git", "config", "user.name", "pineapplesour"], source)
    _git(["git", "config", "user.email", "59020461+pineapplesour@users.noreply.github.com"], source)
    _git(["git", "add", "."], source)
    _git(["git", "commit", "--quiet", "-m", "fixture"], source)
    return source


def test_selection_is_seeded_and_materialization_removes_gold(tmp_path: Path) -> None:
    source = _fake_source(tmp_path)
    first = [path.name for path in select_tasks(source, seed="fixed", count=2)]
    second = [path.name for path in select_tasks(source, seed="fixed", count=2)]
    assert first == second

    output = tmp_path / "campaign"
    result = materialize(source, output, seed="fixed", count=2)
    assert result["selectedTaskIds"] == [f"aider-python/{name}" for name in first]
    for name in first:
        copied = output / "source" / "tasks" / "python" / name
        assert not (copied / ".meta").exists()
        assert (copied / f"{name}_test.py").is_file()
    task = json.loads((output / "public" / "task.json").read_text())
    assert task["base_ref"] == result["baseRef"]
    assert len(task["allowed_path_globs"]) == 2
