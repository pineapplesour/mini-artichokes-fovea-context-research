from __future__ import annotations

import importlib.util
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "tools/prepare_choice_hidden_overlap_adjudication.py"
SPEC = importlib.util.spec_from_file_location("prepare_overlap", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_prepared_overlap_is_blind_and_contains_both_candidates(tmp_path: Path) -> None:
    source_root = (
        REPO_ROOT
        / "runs/choice-hidden-5x20-luna-high-development-20260902-v1"
    )
    block_id = "block_03_christian_provao"
    for arm in ("plain", "kira_independent"):
        source = source_root / arm / block_id / "solver"
        target = tmp_path / arm / block_id / "solver"
        target.mkdir(parents=True)
        for relative in (
            "freeze.json",
            "run_receipt.json",
            "input/questions.jsonl",
            "output/answers.jsonl",
        ):
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((source / relative).read_bytes())

    report = MODULE.prepare(campaign_root=tmp_path, block_id=block_id)
    solver = Path(report["campaignDir"]) / "solver"
    rows = [
        json.loads(line)
        for line in (solver / "input/questions.jsonl").read_text().splitlines()
    ]
    assert len(rows) == 20
    assert all(
        set(row)
        == {
            "id",
            "benchmarkId",
            "responseFormat",
            "prompt",
            "candidateA",
            "candidateB",
        }
        for row in rows
    )
    public_text = (solver / "input/questions.jsonl").read_text().lower()
    assert "kira_independent" not in public_text
    assert '"plain"' not in public_text

    order = json.loads(
        (tmp_path / "overlap_falsifier" / block_id / "candidate_order.private.json").read_text()
    )
    mappings = {(row["candidateA"], row["candidateB"]) for row in order["rows"]}
    assert mappings == {
        ("plain", "kira_independent"),
        ("kira_independent", "plain"),
    }
