from __future__ import annotations

import json
from pathlib import Path

from tools.prepare_plain_codex_file_benchmark import (
    DEFAULT_REGISTRY,
    EXPECTED_EXAM_CASES,
    EXPECTED_LEGAL_VARIANTS,
    EXPECTED_TOTAL_ROWS,
    load_jsonl,
    load_public_rows,
    prepare_grader,
    prepare_solver,
    validate_answers,
    validate_grades,
    write_jsonl,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
UNIFIED = REPO_ROOT / "benchmarks/unified"


def load(name: str) -> dict:
    return json.loads((UNIFIED / name).read_text(encoding="utf-8"))


def test_rebuilt_official_islam_manifest_counts_and_formats() -> None:
    aqa_public = load("official_islam_aqa20.public.json")
    aqa_private = load("official_islam_aqa20.private.json")
    byu_public = load("official_islam_byu16.public.json")
    byu_private = load("official_islam_byu16.private.json")
    cambridge_public = load("official_islam_cambridge32.public.json")
    cambridge_private = load("official_islam_cambridge32.private.json")

    assert len(aqa_public["cases"]) == len(aqa_private["answers"]) == 20
    assert sum(case["metadata"]["responseFormat"] == "mcq" for case in aqa_public["cases"]) == 4
    assert sum(case["metadata"]["responseFormat"] == "constructed_response" for case in aqa_public["cases"]) == 16
    assert sum(case["metadata"]["spagMarks"] for case in aqa_public["cases"]) == 6
    assert len(byu_public["cases"]) == len(byu_private["answers"]) == 16
    byu_multiselect = {row["caseId"]: row["correctOptionIds"] for row in byu_private["answers"] if len(row["correctOptionIds"]) > 1}
    assert byu_multiselect == {
        "islam-byu-q011": ["A", "B", "C", "D"],
        "islam-byu-q013": ["A", "B", "C", "D"],
    }
    assert len(cambridge_public["cases"]) == len(cambridge_private["answers"]) == 32
    assert all(case["metadata"]["responseFormat"] == "constructed_response" for case in cambridge_public["cases"])
    assert set(cambridge_private["sharedMarkingInstructions"]) == {"paper1", "paper2"}


def test_public_file_bundle_has_all_1299_exam_and_ten_legal_rows() -> None:
    rows, hashes = load_public_rows(DEFAULT_REGISTRY)
    exam = [row for row in rows if row["suite"] == "exam"]
    legal = [row for row in rows if row["suite"] == "legal_e2e"]
    assert len(rows) == EXPECTED_TOTAL_ROWS
    assert len(exam) == EXPECTED_EXAM_CASES
    assert len(legal) == EXPECTED_LEGAL_VARIANTS
    assert len({row["id"] for row in rows}) == EXPECTED_TOTAL_ROWS
    assert "military-key-management::v1" in {row["id"] for row in legal}
    assert len(hashes) == 14


def test_solver_bundle_and_answer_validation_are_complete_file_gates(tmp_path: Path) -> None:
    campaign = tmp_path / "campaign"
    freeze = prepare_solver(DEFAULT_REGISTRY, campaign)
    questions = load_jsonl(campaign / "solver/input/questions.jsonl")
    assert freeze["inventory"] == {"examCases": 1299, "legalVariants": 10, "rows": 1309}
    assert freeze["executionConfig"]["model"] == "gpt-5.6-luna"
    assert freeze["executionConfig"]["reasoningEffort"] == "high"
    assert len(questions) == 1309

    answers = [{"id": row["id"], "finalAnswer": "test answer"} for row in questions]
    write_jsonl(campaign / "solver/output/answers.jsonl", answers)
    assert validate_answers(campaign)["passed"] is True

    write_jsonl(campaign / "solver/output/answers.jsonl", answers[:-1])
    invalid = validate_answers(campaign)
    assert invalid["passed"] is False
    assert "answer_ids_or_order_mismatch" in invalid["errors"]


def test_one_grader_packet_and_grade_file_cover_every_id_once(tmp_path: Path) -> None:
    campaign = tmp_path / "campaign"
    prepare_solver(DEFAULT_REGISTRY, campaign)
    questions = load_jsonl(campaign / "solver/input/questions.jsonl")
    write_jsonl(
        campaign / "solver/output/answers.jsonl",
        ({"id": row["id"], "finalAnswer": "test answer"} for row in questions),
    )
    grader_freeze = prepare_grader(DEFAULT_REGISTRY, campaign)
    packet = load_jsonl(campaign / "grader/input/grading_packet.jsonl")
    assert grader_freeze["expectedRows"] == len(packet) == 1309
    assert grader_freeze["gradingPacketBytes"] > 1_000_000

    grades = []
    for row in packet:
        if row["responseFormat"] == "constructed_response":
            maximum = int(row["privateGold"]["maxMarks"])
            grades.append(
                {
                    "id": row["id"],
                    "gradeType": "raw_marks",
                    "verdict": None,
                    "awardedMarks": 0,
                    "maxMarks": maximum,
                    "reason": "test",
                }
            )
        else:
            grades.append(
                {
                    "id": row["id"],
                    "gradeType": "binary",
                    "verdict": "fail",
                    "awardedMarks": None,
                    "maxMarks": None,
                    "reason": "test",
                }
            )
    write_jsonl(campaign / "grader/output/grades.jsonl", grades)
    validation = validate_grades(campaign)
    assert validation["passed"] is True
    assert validation["observedRows"] == 1309
    assert validation["binary"] == {"pass": 0, "fail": 1261, "unresolved": 0}
    assert validation["binaryExam"] == {"pass": 0, "fail": 1251, "unresolved": 0}
    assert validation["legalEndToEnd"] == {"pass": 0, "fail": 10, "unresolved": 0}
    assert validation["constructedRawMarks"] == {"awarded": 0, "maximum": 338}
    assert validation["officialExamPoints"] == {"awarded": 0, "maximum": 1589}
