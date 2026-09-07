from __future__ import annotations

import json
from pathlib import Path

from tools import combine_overlap_validators as combiner


def _json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


def _jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _campaign(root: Path, name: str, valid: set[str], trace: str) -> Path:
    campaign = root / name
    ids = ["q1", "q2", "q3"]
    eligible = ["q1", "q2"]
    freeze = {
        key: "same"
        for key in (
            "freezeSha256",
            "questionsSha256",
            "instructionsSha256",
            "expectedIdsSha256",
            "overlapManifestSha256",
            "eligibleIdsSha256",
            "candidateBundleSha256",
            "candidateProvenanceSha256",
        )
    }
    _json(campaign / "solver/freeze.json", freeze)
    _json(campaign / "solver/input/expected_ids.json", {"count": 3, "ids": ids})
    _jsonl(
        campaign / "solver/input/overlap_manifest.jsonl",
        [{"id": case_id, "eligible": case_id in eligible} for case_id in ids],
    )
    _jsonl(
        campaign / "solver/input/candidates/base.jsonl",
        [{"id": case_id, "finalAnswer": f"base-{case_id}"} for case_id in ids],
    )
    _jsonl(
        campaign / "solver/input/candidates/auxiliary_1.jsonl",
        [{"id": case_id, "finalAnswer": f"aux-{case_id}"} for case_id in ids],
    )
    output = campaign / "solver/output"
    output.mkdir(parents=True)
    (output / "decisions.log").write_text(
        "".join(
            f"{case_id} | gate={'VALID' if case_id in valid else 'INVALID'} | "
            f"action={'SWITCH' if case_id in valid else 'KEEP'} | reason\n"
            for case_id in eligible
        ),
        encoding="utf-8",
    )
    (campaign / "solver/codex_trace.jsonl").write_text(trace, encoding="utf-8")
    return campaign


def test_combines_only_intersection_of_two_valid_switch_sets(tmp_path: Path, monkeypatch) -> None:
    first = _campaign(tmp_path, "first", {"q1", "q2"}, "trace-one\n")
    second = _campaign(tmp_path, "second", {"q2"}, "trace-two\n")
    monkeypatch.setattr(
        combiner,
        "verify_frozen_inputs",
        lambda **_: {"passed": True, "freezeSha256": "same"},
    )
    monkeypatch.setattr(
        combiner,
        "validate_overlap_adjudication",
        lambda campaign, write_report=False: {
            "passed": True,
            "decisionsSha256": combiner.sha256_file(campaign / "solver/output/decisions.log"),
        },
    )
    monkeypatch.setattr(
        combiner,
        "verify_receipt",
        lambda campaign: {"receiptSha256": f"receipt-{campaign.name}"},
    )

    output = tmp_path / "combined"
    report = combiner.combine(first, second, output)
    answers = combiner.load_jsonl(output / "answers.jsonl")

    assert report["status"] == "accepted"
    assert report["intersectionRows"] == 1
    assert [row["finalAnswer"] for row in answers] == ["base-q1", "aux-q2", "base-q3"]
    persisted = combiner.load_json(output / "combination_receipt.json")
    assert persisted == report
