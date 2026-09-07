from __future__ import annotations

import importlib.util
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "tools/prepare_visible_options_direct_replicates.py"
SPEC = importlib.util.spec_from_file_location("prepare_visible_replicates", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_prepares_two_matched_direct_replicates(tmp_path: Path) -> None:
    report = MODULE.prepare(
        selection_dir=REPO_ROOT
        / "benchmark_reports/2026-09-02-visible-options-5x20-development",
        campaign_root=tmp_path,
        model="gpt-5.6-luna",
        reasoning_effort="high",
        verbosity="low",
    )
    assert report["arms"] == ["direct_d2", "direct_d3"]
    assert report["plannedSolverCalls"] == 10
    hashes: dict[str, set[str]] = {}
    for campaign in report["campaigns"]:
        solver = Path(campaign["campaignDir"]) / "solver"
        freeze = json.loads((solver / "freeze.json").read_text())
        rows = [
            json.loads(line)
            for line in (solver / "input/questions.jsonl").read_text().splitlines()
        ]
        assert len(rows) == 20
        assert all(row["responseFormat"] == "mcq" for row in rows)
        assert freeze["executionConfig"]["model"] == "gpt-5.6-luna"
        assert freeze["executionConfig"]["nativeWebSearch"] is False
        assert "numeric option ID only" in (
            solver / "input/RUN_INSTRUCTIONS.md"
        ).read_text()
        assert "correctoptionid" not in json.dumps(rows, ensure_ascii=False).lower()
        hashes.setdefault(campaign["blockId"], set()).add(freeze["questionsSha256"])
    assert len(hashes) == 5
    assert all(len(values) == 1 for values in hashes.values())
