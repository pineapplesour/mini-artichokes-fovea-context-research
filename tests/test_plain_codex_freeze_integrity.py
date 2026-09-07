from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools import run_plain_codex_file_agent as runner


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def _campaign(tmp_path: Path) -> Path:
    campaign = tmp_path / "campaign"
    role_dir = campaign / "solver"
    input_dir = role_dir / "input"
    output_dir = role_dir / "output"
    output_dir.mkdir(parents=True)
    questions = [
        {"id": "q1", "responseFormat": "mcq", "prompt": "Pick one: 1. A 2. B"},
        {"id": "q2", "responseFormat": "mcq", "prompt": "Pick one: 1. C 2. D"},
    ]
    ids = ["q1", "q2"]
    _write_jsonl(input_dir / "questions.jsonl", questions)
    (input_dir / "RUN_INSTRUCTIONS.md").write_text("frozen instructions\n", encoding="utf-8")
    _write_json(input_dir / "expected_ids.json", {"count": 2, "ids": ids})
    candidates = {
        "base": [{"id": "q1", "finalAnswer": "1"}, {"id": "q2", "finalAnswer": "1"}],
        "auxiliary_1": [{"id": "q1", "finalAnswer": "2"}, {"id": "q2", "finalAnswer": "1"}],
        "auxiliary_2": [{"id": "q1", "finalAnswer": "2"}, {"id": "q2", "finalAnswer": "2"}],
    }
    candidate_hashes: dict[str, str] = {}
    for name, rows in candidates.items():
        path = input_dir / "candidates" / f"{name}.jsonl"
        _write_jsonl(path, rows)
        candidate_hashes[name] = runner.sha256_file(path)
    overlap = [
        {"id": "q1", "responseFormat": "mcq", "eligible": True},
        {"id": "q2", "responseFormat": "mcq", "eligible": False},
    ]
    overlap_path = input_dir / "overlap_manifest.jsonl"
    _write_jsonl(overlap_path, overlap)
    implementation = tmp_path / "implementation.py"
    implementation.write_text("# frozen\n", encoding="utf-8")
    freeze = {
        "schemaVersion": 1,
        "protocol": "mini_artichokes_candidate_overlap_adjudication_v1",
        "questionsSha256": runner.sha256_file(input_dir / "questions.jsonl"),
        "instructionsSha256": runner.sha256_file(input_dir / "RUN_INSTRUCTIONS.md"),
        "expectedIdsSha256": runner.canonical_digest(ids),
        "overlapManifestSha256": runner.sha256_file(overlap_path),
        "eligibleIdsSha256": runner.canonical_digest(["q1"]),
        "eligibleMcqIdsSha256": runner.canonical_digest(["q1"]),
        "candidateAnswersSha256": candidate_hashes,
        "candidateBundleSha256": runner.canonical_digest(candidate_hashes),
        "executionConfig": {"model": "gpt-5.6-luna", "reasoningEffort": "high", "verbosity": "low"},
        "implementationHashes": {str(implementation): runner.sha256_file(implementation)},
    }
    freeze["freezeSha256"] = runner.canonical_digest(freeze)
    _write_json(role_dir / "freeze.json", freeze)
    return campaign


def test_verify_frozen_inputs_accepts_exact_bundle(tmp_path: Path) -> None:
    report = runner.verify_frozen_inputs(campaign_dir=_campaign(tmp_path), role="solver")
    assert report["passed"] is True
    assert report["rows"] == 2


@pytest.mark.parametrize(
    ("relative_path", "replacement", "message"),
    [
        ("solver/input/RUN_INSTRUCTIONS.md", "changed\n", "instructions"),
        ("solver/input/candidates/auxiliary_1.jsonl", '{"id":"q1","finalAnswer":"1"}\n', "candidate"),
        ("solver/input/overlap_manifest.jsonl", '{"id":"q1","responseFormat":"mcq","eligible":false}\n', "overlap"),
        ("solver/input/expected_ids.json", '{"count":1,"ids":["q1"]}\n', "expected IDs"),
    ],
)
def test_verify_frozen_inputs_rejects_tampered_controls(
    tmp_path: Path, relative_path: str, replacement: str, message: str
) -> None:
    campaign = _campaign(tmp_path)
    (campaign / relative_path).write_text(replacement, encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        runner.verify_frozen_inputs(campaign_dir=campaign, role="solver")


def test_verify_frozen_inputs_rejects_freeze_self_hash_tampering(tmp_path: Path) -> None:
    campaign = _campaign(tmp_path)
    freeze_path = campaign / "solver/freeze.json"
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    freeze["protocol"] = "tampered"
    _write_json(freeze_path, freeze)
    with pytest.raises(ValueError, match="self-hash"):
        runner.verify_frozen_inputs(campaign_dir=campaign, role="solver")


def test_run_agent_rejects_tamper_before_probe_or_resume(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    campaign = _campaign(tmp_path)
    candidate = campaign / "solver/input/candidates/base.jsonl"
    candidate.write_text(candidate.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    monkeypatch.setattr(runner, "isolation_probe", lambda **_: pytest.fail("probe must not run"))
    with pytest.raises(ValueError, match="candidate hash mismatch"):
        runner.run_agent(
            campaign_dir=campaign,
            role="solver",
            codex_home=tmp_path / "codex-home",
            model="gpt-5.6-luna",
            reasoning_effort="high",
            verbosity="low",
            timeout_seconds=1,
            resume=True,
        )


def test_codex_command_obeys_frozen_web_policy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        runner,
        "base_bwrap_command",
        lambda **_: (["bwrap"], Path("/tmp/codex.js")),
    )
    common = {
        "input_dir": tmp_path / "input",
        "output_dir": tmp_path / "output",
        "codex_home": tmp_path / "codex-home",
        "role": "solver",
        "model": "gpt-5.6-luna",
        "reasoning_effort": "high",
        "verbosity": "low",
    }
    enabled = runner.codex_command(**common, native_web_search=True)
    disabled = runner.codex_command(**common, native_web_search=False)
    assert "--search" in enabled
    assert "--search" not in disabled
    assert 'web_search="disabled"' not in enabled
    assert 'web_search="disabled"' in disabled
