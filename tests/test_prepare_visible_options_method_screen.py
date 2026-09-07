from __future__ import annotations

import importlib.util
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "tools/prepare_visible_options_method_screen.py"
SPEC = importlib.util.spec_from_file_location("prepare_method_screen", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_prepares_six_budgeted_methods_on_same_public_prompts(tmp_path: Path) -> None:
    report = MODULE.prepare(
        campaign_root=REPO_ROOT
        / "runs/visible-options-5x20-luna-high-development-20260902-v1",
        block_id="block_01_leet",
        output_root=tmp_path,
        model="gpt-5.6-luna",
        reasoning_effort="high",
        verbosity="low",
    )
    assert report["plannedSolverCalls"] == 6
    assert set(report["methods"]) == set(MODULE.METHODS)
    prompt_digests = set()
    for campaign in report["campaigns"]:
        solver = Path(campaign["campaignDir"]) / "solver"
        freeze = json.loads((solver / "freeze.json").read_text())
        rows = [
            json.loads(line)
            for line in (solver / "input/questions.jsonl").read_text().splitlines()
        ]
        assert len(rows) == 20
        assert all(row["responseFormat"] == "mcq" for row in rows)
        assert freeze["methodRealization"].startswith("budgeted_prompt_realization")
        assert freeze["executionConfig"]["model"] == "gpt-5.6-luna"
        assert freeze["executionConfig"]["nativeWebSearch"] is False
        serialized = json.dumps(rows, ensure_ascii=False).lower()
        assert "correctoptionid" not in serialized
        assert "gold" not in serialized
        prompt_digests.add(freeze["source"]["publicPromptCanonicalSha256"])
        has_prior = campaign["method"] in {"reflexion", "critic_verifier"}
        assert all(("priorAnswer" in row) is has_prior for row in rows)
    assert len(prompt_digests) == 1
