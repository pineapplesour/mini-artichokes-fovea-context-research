from __future__ import annotations

import importlib.util
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "tools/prepare_choice_hidden_5x20_campaigns.py"
SPEC = importlib.util.spec_from_file_location("prepare_choice_hidden_5x20", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_prepares_matched_ten_call_plan_without_private_answers(tmp_path: Path) -> None:
    selection_dir = (
        REPO_ROOT / "benchmark_reports/2026-09-02-choice-hidden-5x20-development"
    )
    report = MODULE.prepare(
        selection_dir=selection_dir,
        campaign_root=tmp_path,
        model="gpt-5.6-luna",
        reasoning_effort="high",
        verbosity="low",
    )
    assert report["plannedSolverCalls"] == 10
    assert report["arms"] == ["plain", "kira_independent"]

    hashes_by_block: dict[str, set[str]] = {}
    for campaign in report["campaigns"]:
        solver = Path(campaign["campaignDir"]) / "solver"
        freeze = json.loads((solver / "freeze.json").read_text())
        rows = [
            json.loads(line)
            for line in (solver / "input/questions.jsonl").read_text().splitlines()
        ]
        assert len(rows) == 20
        assert freeze["executionConfig"]["model"] == "gpt-5.6-luna"
        assert freeze["executionConfig"]["nativeWebSearch"] is False
        serialized = json.dumps(rows, ensure_ascii=False).lower()
        assert "verdict" not in serialized
        assert "correctanswer" not in serialized
        assert "privategold" not in serialized
        hashes_by_block.setdefault(campaign["blockId"], set()).add(
            freeze["questionsSha256"]
        )
    assert len(hashes_by_block) == 5
    assert all(len(hashes) == 1 for hashes in hashes_by_block.values())
