from __future__ import annotations

import importlib.util
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "tools/prepare_visible_options_5x20_campaigns.py"
SPEC = importlib.util.spec_from_file_location("prepare_visible_options", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_prepares_matched_5x20_luna_plan_without_private_answers(tmp_path: Path) -> None:
    report = MODULE.prepare(
        selection_dir=REPO_ROOT
        / "benchmark_reports/2026-09-02-visible-options-5x20-development",
        campaign_root=tmp_path,
        model="gpt-5.6-luna",
        reasoning_effort="high",
        verbosity="low",
    )
    assert report["plannedSolverCalls"] == 10
    assert report["arms"] == ["plain", "kira_overlap"]

    hashes_by_block: dict[str, set[str]] = {}
    for campaign in report["campaigns"]:
        solver = Path(campaign["campaignDir"]) / "solver"
        freeze = json.loads((solver / "freeze.json").read_text())
        rows = [
            json.loads(line)
            for line in (solver / "input/questions.jsonl").read_text().splitlines()
        ]
        instructions = (solver / "input/RUN_INSTRUCTIONS.md").read_text()
        assert len(rows) == 20
        assert all(row["responseFormat"] == "mcq" for row in rows)
        assert freeze["executionConfig"]["model"] == "gpt-5.6-luna"
        assert freeze["executionConfig"]["nativeWebSearch"] is False
        assert "option ID only" in instructions
        serialized = json.dumps(rows, ensure_ascii=False).lower()
        assert "correctoptionid" not in serialized
        assert "private" not in serialized
        hashes_by_block.setdefault(campaign["blockId"], set()).add(
            freeze["questionsSha256"]
        )
    assert len(hashes_by_block) == 5
    assert all(len(hashes) == 1 for hashes in hashes_by_block.values())
