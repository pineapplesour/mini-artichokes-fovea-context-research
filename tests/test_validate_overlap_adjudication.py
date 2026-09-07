from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.prepare_overlap_adjudication import prepare
from tools.prepare_plain_codex_file_benchmark import canonical_digest, sha256_file
from tools.validate_overlap_adjudication import validate_overlap_adjudication


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def prepared_campaign(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    questions = [
        {
            "id": "q1",
            "prompt": "Choose one.\nA. alpha\nB. beta\nC. gamma",
            "responseFormat": "mcq",
        },
        {
            "id": "q2",
            "prompt": "Pick one.\nA. old\nB. new answer\nC. other",
            "responseFormat": "mcq",
        },
        {"id": "q3", "prompt": "Another", "responseFormat": "short_answer"},
    ]
    write_jsonl(source / "solver/input/questions.jsonl", questions)
    (source / "solver/input/expected_ids.json").write_text(
        json.dumps({"count": 3, "ids": ["q1", "q2", "q3"]}), encoding="utf-8"
    )
    source_freeze = {
        "questionsSha256": sha256_file(source / "solver/input/questions.jsonl"),
        "expectedIdsSha256": canonical_digest(["q1", "q2", "q3"]),
    }
    source_freeze["freezeSha256"] = canonical_digest(source_freeze)
    (source / "solver/freeze.json").write_text(json.dumps(source_freeze), encoding="utf-8")
    candidates = {
        1: [
            {"id": "q1", "finalAnswer": "A. alpha"},
            {"id": "q2", "finalAnswer": "old"},
            {"id": "q3", "finalAnswer": "keep"},
        ],
        2: [
            {"id": "q1", "finalAnswer": "B. beta"},
            {"id": "q2", "finalAnswer": "new answer"},
            {"id": "q3", "finalAnswer": "left"},
        ],
        3: [
            {"id": "q1", "finalAnswer": "beta"},
            {"id": "q2", "finalAnswer": "new   answer"},
            {"id": "q3", "finalAnswer": "right"},
        ],
    }
    for index, rows in candidates.items():
        write_jsonl(source / f"drafts/d{index}/solver/output/answers.jsonl", rows)

    campaign = tmp_path / "campaign"
    prepare(
        source_campaign=source,
        campaign_dir=campaign,
        base_index=1,
        auxiliary_indices=(2, 3),
        model="gpt-5.6-luna",
        reasoning_effort="high",
        verbosity="low",
    )
    return campaign


def write_result(
    campaign: Path,
    *,
    decisions: list[str] | None = None,
    answers: list[str] | None = None,
) -> None:
    output = campaign / "solver/output"
    output.mkdir(parents=True, exist_ok=True)
    if decisions is None:
        decisions = [
            "q1 | gate=VALID | action=SWITCH | independently verified",
            "q2 | gate=INVALID | action=KEEP | agreement unsupported",
        ]
    (output / "decisions.log").write_text("\n".join(decisions) + "\n", encoding="utf-8")
    values = answers if answers is not None else ["B. beta", "old", "keep"]
    write_jsonl(
        output / "answers.jsonl",
        [
            {"id": "q1", "finalAnswer": values[0]},
            {"id": "q2", "finalAnswer": values[1]},
            {"id": "q3", "finalAnswer": values[2]},
        ],
    )


def test_accepts_only_exact_base_or_valid_consensus_switch(tmp_path: Path) -> None:
    campaign = prepared_campaign(tmp_path)
    write_result(campaign)

    report = validate_overlap_adjudication(campaign)

    assert report["passed"] is True
    assert report["status"] == "accepted"
    assert report["eligibleRows"] == 2
    assert report["decisionRows"] == 2
    assert report["switchRows"] == report["changedRows"] == 1
    assert report["errors"] == []
    persisted = json.loads((campaign / "solver/overlap_validation.json").read_text(encoding="utf-8"))
    assert persisted == report


def test_rejects_synthesized_switch_answer(tmp_path: Path) -> None:
    campaign = prepared_campaign(tmp_path)
    write_result(campaign, answers=["B. beta because alpha is wrong", "old", "keep"])

    report = validate_overlap_adjudication(campaign, write_report=False)

    assert report["passed"] is False
    assert "answer_q1_switch_not_exact_auxiliary_1" in report["errors"]


def test_rejects_any_change_to_an_ineligible_row(tmp_path: Path) -> None:
    campaign = prepared_campaign(tmp_path)
    write_result(campaign, answers=["B. beta", "old", "right"])

    report = validate_overlap_adjudication(campaign, write_report=False)

    assert "answer_q3_ineligible_changed" in report["errors"]
    assert "decisions_output_change_set_mismatch" in report["errors"]


@pytest.mark.parametrize(
    ("decisions", "expected_error"),
    [
        (
            ["q1 | gate=VALID | action=SWITCH | verified"],
            "decisions_missing_eligible_id",
        ),
        (
            [
                "q1 | gate=VALID | action=SWITCH | verified",
                "q1 | gate=VALID | action=SWITCH | duplicate",
                "q2 | gate=INVALID | action=KEEP | unsupported",
            ],
            "decisions_duplicate_id",
        ),
        (
            [
                "q2 | gate=INVALID | action=KEEP | unsupported",
                "q1 | gate=VALID | action=SWITCH | verified",
            ],
            "decisions_ids_or_order_mismatch",
        ),
        (
            [
                "q1 | gate=VALID | action=SWITCH | verified",
                "q2 | gate=INVALID | action=KEEP | unsupported",
                "q3 | gate=INVALID | action=KEEP | not eligible",
            ],
            "decisions_ineligible_id",
        ),
    ],
)
def test_eligible_ledger_must_be_exactly_once_and_in_order(
    tmp_path: Path,
    decisions: list[str],
    expected_error: str,
) -> None:
    campaign = prepared_campaign(tmp_path)
    write_result(campaign, decisions=decisions)

    report = validate_overlap_adjudication(campaign, write_report=False)

    assert report["passed"] is False
    assert expected_error in report["errors"]


@pytest.mark.parametrize(
    "decision",
    [
        "q1 | gate=VALID | action=KEEP | contradictory pair",
        "q1 | gate=INVALID | action=SWITCH | contradictory pair",
        "q1 | gate=ABSTAIN | action=SWITCH | contradictory pair",
    ],
)
def test_gate_action_pair_is_fail_closed(tmp_path: Path, decision: str) -> None:
    campaign = prepared_campaign(tmp_path)
    write_result(
        campaign,
        decisions=[
            decision,
            "q2 | gate=INVALID | action=KEEP | unsupported",
        ],
        answers=["A. alpha", "old", "keep"],
    )

    report = validate_overlap_adjudication(campaign, write_report=False)

    assert report["passed"] is False
    assert "decision_q1_gate_action_mismatch" in report["errors"]
    assert report["changedRows"] == 0


def test_rejects_manifest_that_does_not_match_frozen_candidates(tmp_path: Path) -> None:
    campaign = prepared_campaign(tmp_path)
    manifest_path = campaign / "solver/input/overlap_manifest.jsonl"
    rows = [json.loads(line) for line in manifest_path.read_text(encoding="utf-8").splitlines()]
    rows[0]["eligible"] = False
    write_jsonl(manifest_path, rows)
    write_result(campaign)

    report = validate_overlap_adjudication(campaign, write_report=False)

    assert report["passed"] is False
    assert "overlap_manifest_row_0_recompute_mismatch" in report["errors"]


def test_keep_and_abstain_require_byte_exact_base_answer(tmp_path: Path) -> None:
    campaign = prepared_campaign(tmp_path)
    write_result(
        campaign,
        decisions=[
            "q1 | gate=ABSTAIN | action=KEEP | not independently supported",
            "q2 | gate=INVALID | action=KEEP | unsupported",
        ],
        answers=["A. alpha ", "old", "keep"],
    )

    report = validate_overlap_adjudication(campaign, write_report=False)

    assert report["passed"] is False
    assert "answer_q1_keep_not_exact_base" in report["errors"]
