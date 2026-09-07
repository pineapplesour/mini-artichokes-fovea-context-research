from __future__ import annotations

import json
from pathlib import Path

from tools.prepare_overlap_file_benchmark import prepare


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_plain_and_kira_universal_freezes_share_public_suite(tmp_path: Path) -> None:
    registry = REPO_ROOT / "benchmarks/plain_codex_visible_options_registry.json"
    plain_dir = tmp_path / "plain"
    overlap_dir = tmp_path / "overlap"
    plain = prepare(
        registry_path=registry,
        campaign_dir=plain_dir,
        policy="plain",
        model="gpt-5.6-sol",
        reasoning_effort="high",
        verbosity="low",
    )
    overlap = prepare(
        registry_path=registry,
        campaign_dir=overlap_dir,
        policy="kira_universal",
        model="gpt-5.6-sol",
        reasoning_effort="high",
        verbosity="low",
    )
    assert plain["questionsSha256"] == overlap["questionsSha256"]
    assert plain["expectedIdsSha256"] == overlap["expectedIdsSha256"]
    assert plain["inventory"]["rows"] == 1309
    assert plain["instructionsSha256"] != overlap["instructionsSha256"]
    instructions = (overlap_dir / "solver/input/RUN_INSTRUCTIONS.md").read_text(encoding="utf-8")
    assert "Universal selective escalation" in instructions
    assert "KIRA-style double completion confirmation" in instructions
    questions = (overlap_dir / "solver/input/questions.jsonl").read_text(encoding="utf-8")
    first = json.loads(questions.splitlines()[0])
    assert set(first) == {"id", "suite", "benchmarkId", "responseFormat", "language", "prompt"}
    assert "privateGold" not in questions
