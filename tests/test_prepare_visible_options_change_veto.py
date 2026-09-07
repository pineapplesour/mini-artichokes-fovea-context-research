from __future__ import annotations

import importlib.util
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "tools/prepare_visible_options_change_veto.py"
SPEC = importlib.util.spec_from_file_location("prepare_change_veto", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_prepares_only_changed_blinded_rows_without_gold(tmp_path: Path) -> None:
    campaign_root = (
        REPO_ROOT / "runs/visible-options-5x20-luna-high-development-20260902-v1"
    )
    report = MODULE.prepare(
        campaign_root=campaign_root,
        block_id="block_01_leet",
        support_judge_campaign=campaign_root / "support_repair_judge/block_01_leet",
        output_campaign=tmp_path / "veto",
        model="gpt-5.6-luna",
        reasoning_effort="high",
        verbosity="low",
    )
    assert report["rows"] == 5
    solver = tmp_path / "veto/solver"
    rows = [
        json.loads(line)
        for line in (solver / "input/questions.jsonl").read_text().splitlines()
    ]
    assert len(rows) == 5
    assert all(len(row["anonymousCandidates"]) == 2 for row in rows)
    assert all(
        len({x["optionId"] for x in row["anonymousCandidates"]}) == 2 for row in rows
    )
    serialized = json.dumps(rows, ensure_ascii=False).lower()
    assert "correctoptionid" not in serialized
    assert "gold" not in serialized
    assert "incumbent" not in serialized
    assert "challenger" not in serialized
    freeze = json.loads((solver / "freeze.json").read_text())
    assert freeze["inventory"] == {"rows": 5, "mcqRows": 5}
    assert freeze["executionConfig"]["nativeWebSearch"] is False
