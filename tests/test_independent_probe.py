import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from tools.run_aider_independent_probe import validate_probes, canonicalize_ids, PROBE_AUTHOR
from tools.independent_probe_prompts import make_prompt


def test_complete_inventory_includes_unavailable():
    validate_probes([
        dict(taskId="a", status="executable", basis="doc", java="class Probe {}", reason=""),
        dict(taskId="b", status="unavailable", basis="", java="", reason="unclear API"),
    ], {"a", "b"})


def test_missing_or_duplicate_task_rejected():
    row = dict(taskId="a", status="unavailable", basis="", java="", reason="unclear")
    with pytest.raises(ValueError):
        validate_probes([row], {"a", "b"})
    with pytest.raises(ValueError):
        validate_probes([row, row], {"a", "b"})


def test_alias_amendment_changes_only_id_and_never_completes_missing_rows():
    row = dict(taskId="a", status="unavailable", basis="", java="", reason="unchanged")
    canonical = canonicalize_ids([row], {"track/a"})
    assert canonical == [{**row, "taskId": "track/a"}]
    assert row["taskId"] == "a"
    with pytest.raises(ValueError):
        canonicalize_ids([row], {"track/a", "track/b"})
    with pytest.raises(ValueError):
        canonicalize_ids([row], {"first/a", "second/a"})


def test_author_explicitly_blind_to_candidates():
    assert "never candidate" in PROBE_AUTHOR
    assert "Never\nmutate /tmp/work" in PROBE_AUTHOR


def test_repair_controls_share_seed_schema_and_unrestricted_access():
    for policy in ["generic", "overlap"]:
        prompt = make_prompt("ALL47", policy)
        assert "starts from\nthe ordinary-repair candidate" in prompt
        assert "taskId, hypothesis, check, observation, action" in prompt
        assert "Budget: 900 seconds" in prompt
        assert "{instruction}" not in prompt
        assert prompt.endswith("ALL47\n")
    assert "Freely inspect and compare any candidates" in make_prompt("ALL47", "generic")


@pytest.mark.skipif(not shutil.which("javac"), reason="local Java unavailable")
def test_replay_uses_actual_source_and_reports_compile_separately(tmp_path):
    from tools import probe_replay
    helper = tmp_path / "probe_replay.py"
    shutil.copyfile(Path(probe_replay.__file__), helper)
    (tmp_path / "benchmark_manifest.json").write_text(json.dumps({"tasks": [
        {"taskId": "fixture", "relativePath": "tasks/java/fixture"}]}))
    row = dict(taskId="fixture", status="executable", basis="fixture x+1", reason="",
               java="class Probe { public static void main(String[] a) { assert Example.f(2)==3; } }")
    (tmp_path / "probes.json").write_text(json.dumps([row]))
    candidate = tmp_path / "candidate"
    source = candidate / "tasks/java/fixture/src/main/java/Example.java"
    source.parent.mkdir(parents=True)
    def replay():
        result = subprocess.run([sys.executable, str(helper), "--candidate-root", str(candidate),
                                 "--task-id", "fixture"], capture_output=True, text=True, check=True)
        return json.loads(result.stdout)["status"]
    source.write_text("class Example { static int f(int x) { return x+1; } }")
    assert replay() == "executed_pass"
    source.write_text("class Example { static int f(int x) { return x; } }")
    assert replay() == "executed_failure"
    source.write_text("not valid java")
    assert replay() == "compile_unavailable"
