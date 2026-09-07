from __future__ import annotations

import importlib.util
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "tools/prepare_visible_options_support_repair_judge.py"
SPEC = importlib.util.spec_from_file_location("prepare_support_repair", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_prepares_blinded_support_packet_without_gold(tmp_path: Path) -> None:
    campaign_root = (
        REPO_ROOT / "runs/visible-options-5x20-luna-high-development-20260902-v1"
    )
    report = MODULE.prepare(
        campaign_root=campaign_root,
        block_id="block_01_leet",
        output_campaign=tmp_path / "judge",
        model="gpt-5.6-luna",
        reasoning_effort="high",
        verbosity="low",
    )
    assert report["rows"] == 20
    assert report["conflictRows"] == 8
    assert report["unanimousRows"] == 12
    solver = tmp_path / "judge/solver"
    rows = [
        json.loads(line)
        for line in (solver / "input/questions.jsonl").read_text().splitlines()
    ]
    assert all(len(row["anonymousDrafts"]) == 3 for row in rows)
    assert all(sum(x["count"] for x in row["supportCounts"]) == 3 for row in rows)
    serialized = json.dumps(rows, ensure_ascii=False).lower()
    assert "correctoptionid" not in serialized
    assert "gold" not in serialized
    assert "plain" not in serialized
    freeze = json.loads((solver / "freeze.json").read_text())
    assert freeze["inventory"]["conflictRows"] == 8
    assert freeze["executionConfig"]["nativeWebSearch"] is False
