from __future__ import annotations

import importlib.util
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "tools/freeze_choice_hidden_5x20.py"
SPEC = importlib.util.spec_from_file_location("freeze_choice_hidden_5x20", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_selection_is_deterministic_and_seed_bound() -> None:
    ids = [f"case-{index:03d}" for index in range(50)]
    first = MODULE.select_case_ids("seed-a", "benchmark", ids)
    second = MODULE.select_case_ids("seed-a", "benchmark", list(reversed(ids)))
    other = MODULE.select_case_ids("seed-b", "benchmark", ids)
    assert first == second
    assert len(first) == 20
    assert {row["id"] for row in first} != {row["id"] for row in other}


def test_actual_freeze_is_five_disjoint_public_blocks(tmp_path: Path) -> None:
    source_root = REPO_ROOT.parent / "universal-artichoke"
    result = MODULE.freeze(source_root, tmp_path, MODULE.DEFAULT_SEED)
    assert result["cases"] == 100
    assert result["plainLunaHistorical"] == {
        "pass": 63,
        "fail": 36,
        "unresolved": 1,
    }

    freeze = json.loads((tmp_path / "selection_freeze.json").read_text())
    all_ids: list[str] = []
    for block in freeze["blocks"]:
        public = json.loads(Path(block["publicPayload"]).read_text())
        assert public["caseCount"] == 20
        assert len(public["cases"]) == 20
        assert all(set(case) == {"id", "prompt"} for case in public["cases"])
        assert "verdict" not in json.dumps(public)
        all_ids.extend(case["id"] for case in public["cases"])
    assert len(all_ids) == len(set(all_ids)) == 100
