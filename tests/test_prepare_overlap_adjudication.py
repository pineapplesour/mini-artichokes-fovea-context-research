from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.prepare_overlap_adjudication import prepare
from tools.prepare_plain_codex_file_benchmark import canonical_digest, sha256_file


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def add_self_hash(value: dict, field: str) -> dict:
    result = dict(value)
    result[field] = canonical_digest(result)
    return result


def source_campaign(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    questions = [
        {
            "id": "q1",
            "prompt": "Choose one.\nA. alpha\nB. beta\nC. gamma",
            "responseFormat": "mcq",
        },
        {"id": "q2", "prompt": "Short answer", "responseFormat": "short_answer"},
        {"id": "q3", "prompt": "Another", "responseFormat": "short_answer"},
        {"id": "q4", "prompt": "Explain.", "responseFormat": "constructed_response"},
        {
            "id": "q5",
            "prompt": "Choose the expression.\nA. x + 1\nB. x - 1\nC. y",
            "responseFormat": "mcq",
        },
    ]
    questions_path = source / "solver/input/questions.jsonl"
    write_jsonl(questions_path, questions)
    ids = [row["id"] for row in questions]
    write_json(source / "solver/input/expected_ids.json", {"count": len(ids), "ids": ids})
    source_freeze = add_self_hash(
        {
            "schemaVersion": 1,
            "status": "prepared_no_model_calls",
            "protocol": "test_source",
            "questionsSha256": sha256_file(questions_path),
            "expectedIdsSha256": canonical_digest(ids),
            "executionConfig": {
                "model": "gpt-5.6-luna",
                "reasoningEffort": "high",
                "verbosity": "low",
            },
        },
        "freezeSha256",
    )
    write_json(source / "solver/freeze.json", source_freeze)
    answers = {
        1: [
            {"id": "q1", "finalAnswer": "A. alpha"},
            {"id": "q2", "finalAnswer": "old"},
            {"id": "q3", "finalAnswer": "keep"},
            {"id": "q4", "finalAnswer": "base"},
            {"id": "q5", "finalAnswer": "C. y"},
        ],
        2: [
            {"id": "q1", "finalAnswer": "B. beta"},
            {"id": "q2", "finalAnswer": "new answer"},
            {"id": "q3", "finalAnswer": "left"},
            {"id": "q4", "finalAnswer": "."},
            {"id": "q5", "finalAnswer": "x + 1"},
        ],
        3: [
            {"id": "q1", "finalAnswer": "beta"},
            {"id": "q2", "finalAnswer": "new   answer"},
            {"id": "q3", "finalAnswer": "right"},
            {"id": "q4", "finalAnswer": "!"},
            {"id": "q5", "finalAnswer": "x - 1"},
        ],
    }
    for index, rows in answers.items():
        solver_dir = source / f"drafts/d{index}/solver"
        answers_path = solver_dir / "output/answers.jsonl"
        write_jsonl(answers_path, rows)
        answers_sha256 = sha256_file(answers_path)
        write_json(solver_dir / "freeze.json", source_freeze)
        validation = {
            "schemaVersion": 1,
            "status": "accepted",
            "passed": True,
            "errors": [],
            "expectedRows": len(ids),
            "observedRows": len(ids),
            "answersSha256": answers_sha256,
        }
        write_json(solver_dir / "answer_validation.json", validation)
        receipt = add_self_hash(
            {
                "schemaVersion": 1,
                "status": "accepted",
                "role": "solver",
                "semanticModelInvocations": 1,
                "model": "gpt-5.6-luna",
                "reasoningEffort": "high",
                "verbosity": "low",
                "freezeSha256": source_freeze["freezeSha256"],
                "payloadSha256": sha256_file(questions_path),
                "isolationProbe": {"passed": True},
                "process": {"exitCode": 0, "timedOut": False},
                "policyAudit": {"passed": True},
                "artifactValidation": validation,
                "acceptedArtifact": "answers.jsonl",
            },
            "receiptSha256",
        )
        write_json(solver_dir / "run_receipt.json", receipt)
    return source


def run_prepare(source: Path, campaign: Path, *, base_index: int = 1, auxiliary_indices=(2, 3)) -> dict:
    return prepare(
        source_campaign=source,
        campaign_dir=campaign,
        base_index=base_index,
        auxiliary_indices=auxiliary_indices,
        model="gpt-5.6-luna",
        reasoning_effort="high",
        verbosity="low",
    )


def test_prepare_freezes_only_collision_safe_mcq_overlap_and_provenance(tmp_path: Path) -> None:
    source = source_campaign(tmp_path)
    campaign = tmp_path / "campaign"
    freeze = run_prepare(source, campaign)

    rows = [
        json.loads(line)
        for line in (campaign / "solver/input/overlap_manifest.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [row["eligible"] for row in rows] == [True, False, False, False, False]
    assert rows[0]["baseKey"] == "option:1"
    assert rows[0]["auxiliary1Key"] == rows[0]["auxiliary2Key"] == "option:2"
    assert rows[1]["eligibilityReason"] == "non_mcq_excluded"
    assert rows[3]["eligibilityReason"] == "non_mcq_excluded"
    assert rows[4]["eligibilityReason"] == "candidate_option_mapping_incomplete"
    assert rows[4]["auxiliary1Key"] == rows[4]["auxiliary2Key"] == ""
    assert freeze["inventory"] == {
        "rows": 5,
        "eligibleRows": 1,
        "ineligibleRows": 4,
        "mcqRows": 2,
        "eligibleMcqRows": 1,
    }
    assert freeze["eligibleIdsSha256"] == canonical_digest(["q1"])
    assert freeze["eligibleMcqIdsSha256"] == canonical_digest(["q1"])
    assert freeze["candidateProvenanceComplete"] is True
    assert all(item["status"] == "accepted" for item in freeze["candidateProvenance"].values())
    assert freeze["candidateProvenanceSha256"] == canonical_digest(freeze["candidateProvenance"])
    for name in ("base", "auxiliary_1", "auxiliary_2"):
        receipt_path = campaign / freeze["candidateProvenance"][name]["artifacts"]["runReceipt"]["path"]
        assert receipt_path.is_file()
    expected = json.loads((campaign / "solver/input/expected_ids.json").read_text(encoding="utf-8"))
    assert expected == {"count": 5, "ids": ["q1", "q2", "q3", "q4", "q5"]}
    assert freeze["freezeSha256"] == canonical_digest(
        {key: value for key, value in freeze.items() if key != "freezeSha256"}
    )
    instructions = (campaign / "solver/input/RUN_INSTRUCTIONS.md").read_text(encoding="utf-8")
    assert "Agreement alone is never validation" in instructions
    assert "If `eligible=false`, you MUST keep A exactly" in instructions
    assert "Constructed/free-text rows and ambiguous mappings are ineligible" in instructions
    assert "copying B exactly" in instructions


def test_prepare_rejects_missing_candidate_id(tmp_path: Path) -> None:
    source = source_campaign(tmp_path)
    path = source / "drafts/d3/solver/output/answers.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()][:-1]
    write_jsonl(path, rows)

    with pytest.raises(ValueError, match="candidate ID/order mismatch"):
        run_prepare(source, tmp_path / "campaign")


def test_prepare_rejects_empty_candidate_answer(tmp_path: Path) -> None:
    source = source_campaign(tmp_path)
    path = source / "drafts/d2/solver/output/answers.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    rows[2]["finalAnswer"] = "   "
    write_jsonl(path, rows)

    with pytest.raises(ValueError, match="empty/non-string finalAnswer"):
        run_prepare(source, tmp_path / "campaign")


def test_prepare_rejects_duplicate_indices_programmatically(tmp_path: Path) -> None:
    source = source_campaign(tmp_path)
    with pytest.raises(ValueError, match="indices must be unique"):
        run_prepare(source, tmp_path / "campaign", auxiliary_indices=(1, 3))


def test_prepare_rejects_stale_expected_ids(tmp_path: Path) -> None:
    source = source_campaign(tmp_path)
    write_json(source / "solver/input/expected_ids.json", {"count": 5, "ids": ["q2", "q1", "q3", "q4", "q5"]})
    with pytest.raises(ValueError, match="question-derived IDs"):
        run_prepare(source, tmp_path / "campaign")


def test_prepare_rejects_question_missing_required_field(tmp_path: Path) -> None:
    source = source_campaign(tmp_path)
    questions_path = source / "solver/input/questions.jsonl"
    rows = [json.loads(line) for line in questions_path.read_text(encoding="utf-8").splitlines()]
    rows[1]["prompt"] = ""
    write_jsonl(questions_path, rows)
    with pytest.raises(ValueError, match="requires a non-empty string prompt"):
        run_prepare(source, tmp_path / "campaign")


def test_prepare_rejects_source_freeze_self_hash_mismatch(tmp_path: Path) -> None:
    source = source_campaign(tmp_path)
    freeze_path = source / "solver/freeze.json"
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    freeze["protocol"] = "tampered"
    write_json(freeze_path, freeze)
    with pytest.raises(ValueError, match="source campaign freeze freezeSha256 mismatch"):
        run_prepare(source, tmp_path / "campaign")


def test_prepare_rejects_candidate_receipt_answer_hash_mismatch(tmp_path: Path) -> None:
    source = source_campaign(tmp_path)
    receipt_path = source / "drafts/d2/solver/run_receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt.pop("receiptSha256")
    receipt["artifactValidation"]["answersSha256"] = "0" * 64
    receipt = add_self_hash(receipt, "receiptSha256")
    write_json(receipt_path, receipt)
    with pytest.raises(ValueError, match="receipt artifact validation"):
        run_prepare(source, tmp_path / "campaign")
