#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = REPO_ROOT / "benchmarks/plain_codex_visible_options_registry.json"
EXPECTED_EXAM_CASES = 1299
EXPECTED_LEGAL_VARIANTS = 10
EXPECTED_TOTAL_ROWS = EXPECTED_EXAM_CASES + EXPECTED_LEGAL_VARIANTS
EXECUTION_MODEL = "gpt-5.6-luna"
EXECUTION_REASONING_EFFORT = "high"
EXECUTION_VERBOSITY = "low"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_digest(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def ensure_new_directory(path: Path) -> None:
    if path.exists() and any(path.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty directory: {path}")
    path.mkdir(parents=True, exist_ok=True)


def implementation_hashes() -> dict[str, str]:
    paths = [
        Path(__file__).resolve(),
        REPO_ROOT / "tools/build_islam_official_source_manifests.py",
        REPO_ROOT / "tools/run_plain_codex_file_agent.py",
    ]
    return {str(path): sha256_file(path) for path in paths}


def response_format(manifest: dict[str, Any], case: dict[str, Any]) -> str:
    metadata = case.get("metadata") if isinstance(case.get("metadata"), dict) else {}
    explicit = str(metadata.get("responseFormat") or "").strip()
    if explicit:
        return explicit
    task_type = str(manifest.get("taskType") or "").strip()
    return {
        "mcq": "mcq",
        "short_answer": "short_answer",
        "constructed_response": "constructed_response",
    }.get(task_type, task_type or "unknown")


def resolve_manifest(registry_path: Path, relative: str) -> Path:
    path = (registry_path.parent / relative).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def load_public_rows(registry_path: Path) -> tuple[list[dict[str, Any]], dict[str, str]]:
    registry = load_json(registry_path)
    hashes: dict[str, str] = {str(registry_path.resolve()): sha256_file(registry_path)}
    rows: list[dict[str, Any]] = []
    exam = registry.get("canonicalExamAggregate")
    if not isinstance(exam, dict):
        raise ValueError("canonicalExamAggregate missing")
    for entry in exam.get("entries", []):
        if not isinstance(entry, dict):
            raise ValueError("invalid exam registry entry")
        public_path = resolve_manifest(registry_path, str(entry.get("publicManifest") or ""))
        manifest = load_json(public_path)
        hashes[str(public_path)] = sha256_file(public_path)
        cases = manifest.get("cases")
        if not isinstance(cases, list) or len(cases) != int(entry.get("expectedCases") or -1):
            raise ValueError(f"exam case count mismatch: {public_path}")
        for case in cases:
            if not isinstance(case, dict):
                raise ValueError(f"invalid public case: {public_path}")
            case_id = str(case.get("id") or "").strip()
            prompt = str(case.get("prompt") or "").strip()
            if not case_id or not prompt:
                raise ValueError(f"missing public case id/prompt: {public_path}")
            fmt = response_format(manifest, case)
            if fmt not in {"mcq", "short_answer", "constructed_response"}:
                raise ValueError(f"unsupported response format {fmt}: {case_id}")
            rows.append(
                {
                    "id": case_id,
                    "suite": "exam",
                    "benchmarkId": str(manifest.get("benchmarkId") or ""),
                    "responseFormat": fmt,
                    "language": str(case.get("language") or manifest.get("language") or ""),
                    "prompt": prompt,
                }
            )
    expected_exam = int(exam.get("expectedUniqueCases") or 0)
    if expected_exam != EXPECTED_EXAM_CASES or len(rows) != expected_exam:
        raise ValueError(f"expected {EXPECTED_EXAM_CASES} exam cases, found {len(rows)}")

    legal = registry.get("legalEndToEnd")
    if not isinstance(legal, dict):
        raise ValueError("legalEndToEnd missing")
    legal_rows = 0
    entries = legal.get("entries")
    if not isinstance(entries, list) or len(entries) != int(legal.get("expectedTasks") or -1):
        raise ValueError("legal task count mismatch")
    for entry in entries:
        public_path = resolve_manifest(registry_path, str(entry.get("publicManifest") or ""))
        manifest = load_json(public_path)
        hashes[str(public_path)] = sha256_file(public_path)
        for case in manifest.get("cases", []):
            if not isinstance(case, dict):
                raise ValueError(f"invalid legal case: {public_path}")
            case_id = str(case.get("id") or "").strip()
            variants = case.get("variants")
            if not isinstance(variants, list):
                raise ValueError(f"legal variants missing: {case_id}")
            for variant in variants:
                if not isinstance(variant, dict):
                    raise ValueError(f"invalid legal variant: {case_id}")
                if str(variant.get("evaluationStatus") or "") == "excluded_invalid":
                    continue
                variant_id = str(variant.get("id") or "").strip()
                query = str(variant.get("query") or "").strip()
                if not case_id or not variant_id or not query:
                    raise ValueError(f"empty legal variant: {public_path}")
                rows.append(
                    {
                        "id": f"{case_id}::{variant_id}",
                        "suite": "legal_e2e",
                        "benchmarkId": str(manifest.get("benchmarkId") or ""),
                        "responseFormat": "legal_e2e",
                        "language": str(variant.get("language") or case.get("language") or "ko"),
                        "prompt": query,
                    }
                )
                legal_rows += 1
    expected_legal = int(legal.get("expectedVariants") or 0)
    if expected_legal != EXPECTED_LEGAL_VARIANTS or legal_rows != expected_legal:
        raise ValueError(f"expected {EXPECTED_LEGAL_VARIANTS} legal variants, found {legal_rows}")
    ids = [row["id"] for row in rows]
    if len(rows) != EXPECTED_TOTAL_ROWS or len(set(ids)) != len(ids):
        raise ValueError("public row total or ID uniqueness mismatch")
    return rows, dict(sorted(hashes.items()))


SOLVER_INSTRUCTIONS = """# Plain Codex full-suite solver contract

You have one agent invocation for this entire benchmark. Do not spawn other
agents, call another language model, or delegate subsets. Read every row in
`input/questions.jsonl` and solve it independently. You may use native web
search and local code when genuinely useful.

For an MCQ, all original choices are present in `prompt`. Put the content of
the selected option in `finalAnswer`, not only a label such as A or 3. If the
question has multiple correct selections, include the content of every
selected option. Answer short-answer and constructed-response items directly;
give enough detail for the stated task. For legal E2E items, research public
law and precedents when useful and produce a substantive answer.

Do not search for an exact or near-exact exam question, a distinctive answer
choice, an exam/quiz paper or mirror, an answer key, a benchmark/case ID, or a
historical benchmark answer. General concept/fact research is allowed. For the
legal E2E rows, searching their public facts, legal issues, and relevant public
precedents is allowed because retrieval is part of those tasks. Do not inspect
paths outside this isolated workspace.

Write progress to `output/answers.partial.jsonl`. When every input ID has one
non-empty answer, validate the file locally and atomically finish it as
`output/answers.jsonl`. Preserve input order. Every line must be exactly one
UTF-8 JSON object with this schema and no extra keys:

`{"id":"the exact input id","finalAnswer":"your answer"}`

There must be exactly 1,309 rows and every supplied ID exactly once. Do not
place the answers only in your final chat message. Your final message should
only state whether the complete answer file was produced.
"""


GRADER_INSTRUCTIONS = """# Plain Codex full-suite grader contract

You have one grader invocation for the complete benchmark. Do not spawn other
agents, call another language model, browse the web, consult a database, or
use historical benchmark results. Read every row in
`input/grading_packet.jsonl` and grade it against only its supplied public
prompt and private gold/rubric.

For MCQ rows, map `correctOptionId` or `correctOptionIds` to the original
options in `publicPrompt`. The solver was required to answer with option
content, not only a label. A label-only response fails. A multiple-selection
response must include all keyed choices and no incorrect choice. For short
answers, accept ordinary meaning-preserving wording supported by the supplied
gold. For constructed responses, apply the supplied official mark scheme and
award an integer raw mark from zero through `maxMarks`; do not convert it into
a binary pass. For legal E2E rows, apply the complete supplied private rubric
and return pass, fail, or unresolved.

Write progress to `output/grades.partial.jsonl`. After grading every row,
validate it locally and atomically finish `output/grades.jsonl` in input order.
Every line must be one UTF-8 JSON object with exactly these keys:

Binary example:
`{"id":"exact id","gradeType":"binary","verdict":"pass","awardedMarks":null,"maxMarks":null,"reason":"concise reason"}`

Constructed-response example:
`{"id":"exact id","gradeType":"raw_marks","verdict":null,"awardedMarks":7,"maxMarks":10,"reason":"concise reason"}`

Use `raw_marks` with a null verdict for constructed responses. Use `binary`
with null marks for all other rows. There must be exactly 1,309 rows and every
supplied ID exactly once. Do not put the grades only in the final chat message.
"""


def prepare_solver(registry_path: Path, campaign_dir: Path) -> dict[str, Any]:
    solver_dir = campaign_dir / "solver"
    ensure_new_directory(solver_dir)
    rows, source_hashes = load_public_rows(registry_path)
    input_dir = solver_dir / "input"
    output_dir = solver_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    questions_path = input_dir / "questions.jsonl"
    write_jsonl(questions_path, rows)
    (input_dir / "RUN_INSTRUCTIONS.md").write_text(SOLVER_INSTRUCTIONS, encoding="utf-8")
    ids = [row["id"] for row in rows]
    write_json(input_dir / "expected_ids.json", {"count": len(ids), "ids": ids})
    freeze = {
        "schemaVersion": 1,
        "status": "prepared_no_model_calls",
        "protocol": "one_plain_codex_solver_file_output_v1",
        "registryPath": str(registry_path.resolve()),
        "registrySha256": sha256_file(registry_path),
        "sourcePublicManifestHashes": source_hashes,
        "questionsPath": "input/questions.jsonl",
        "questionsSha256": sha256_file(questions_path),
        "instructionsSha256": sha256_file(input_dir / "RUN_INSTRUCTIONS.md"),
        "expectedIdsSha256": canonical_digest(ids),
        "inventory": {"examCases": EXPECTED_EXAM_CASES, "legalVariants": EXPECTED_LEGAL_VARIANTS, "rows": len(rows)},
        "executionConfig": {
            "model": EXECUTION_MODEL,
            "reasoningEffort": EXECUTION_REASONING_EFFORT,
            "verbosity": EXECUTION_VERBOSITY,
            "serviceTier": "default",
            "nativeWebSearch": True,
            "localCode": True,
            "database": False,
            "skills": False,
            "multiAgent": False,
        },
        "implementationHashes": implementation_hashes(),
    }
    freeze["freezeSha256"] = canonical_digest(freeze)
    write_json(solver_dir / "freeze.json", freeze)
    return freeze


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            raise ValueError(f"blank JSONL line {line_number}: {path}")
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError(f"non-object JSONL line {line_number}: {path}")
        rows.append(value)
    return rows


def validate_answers(campaign_dir: Path, *, write_report: bool = True) -> dict[str, Any]:
    solver_dir = campaign_dir / "solver"
    expected = load_json(solver_dir / "input/expected_ids.json").get("ids")
    if not isinstance(expected, list):
        raise ValueError("expected solver IDs missing")
    path = solver_dir / "output/answers.jsonl"
    errors: list[str] = []
    rows: list[dict[str, Any]] = []
    if not path.is_file():
        errors.append("answers_file_missing")
    else:
        try:
            rows = load_jsonl(path)
        except Exception as exc:
            errors.append(f"answers_jsonl_invalid:{exc}")
    ids: list[str] = []
    for index, row in enumerate(rows):
        if set(row) != {"id", "finalAnswer"}:
            errors.append(f"row_{index}_schema")
            continue
        case_id = str(row.get("id") or "").strip()
        answer = str(row.get("finalAnswer") or "").strip()
        ids.append(case_id)
        if not case_id or not answer:
            errors.append(f"row_{index}_empty")
        if len(answer) > 100_000:
            errors.append(f"row_{index}_answer_too_long")
    if ids != expected:
        errors.append("answer_ids_or_order_mismatch")
    report = {
        "schemaVersion": 1,
        "status": "accepted" if not errors else "incomplete",
        "passed": not errors,
        "errors": errors,
        "expectedRows": len(expected),
        "observedRows": len(rows),
        "answersSha256": sha256_file(path) if path.is_file() else None,
    }
    if write_report:
        write_json(solver_dir / "answer_validation.json", report)
    return report


def private_exam_rows(registry_path: Path) -> dict[str, dict[str, Any]]:
    registry = load_json(registry_path)
    result: dict[str, dict[str, Any]] = {}
    for entry in registry["canonicalExamAggregate"]["entries"]:
        public_path = resolve_manifest(registry_path, entry["publicManifest"])
        private_path = resolve_manifest(registry_path, entry["privateManifest"])
        public = load_json(public_path)
        private = load_json(private_path)
        cases = {str(case["id"]): case for case in public.get("cases", [])}
        answers = {str(answer["caseId"]): answer for answer in private.get("answers", [])}
        if set(cases) != set(answers):
            raise ValueError(f"public/private exam ID mismatch: {public_path}")
        shared = private.get("sharedMarkingInstructions")
        for case_id, case in cases.items():
            answer = dict(answers[case_id])
            shared_ref = str(answer.get("sharedMarkingInstructionsRef") or "")
            if shared_ref:
                if not isinstance(shared, dict) or shared_ref not in shared:
                    raise ValueError(f"missing shared marking instructions: {case_id}")
                answer["sharedMarkingInstructions"] = shared[shared_ref]
            result[case_id] = {
                "id": case_id,
                "suite": "exam",
                "responseFormat": response_format(public, case),
                "publicPrompt": str(case.get("prompt") or ""),
                "privateGold": answer,
            }
    return result


def private_legal_rows(registry_path: Path) -> dict[str, dict[str, Any]]:
    registry = load_json(registry_path)
    result: dict[str, dict[str, Any]] = {}
    for entry in registry["legalEndToEnd"]["entries"]:
        public = load_json(resolve_manifest(registry_path, entry["publicManifest"]))
        private = load_json(resolve_manifest(registry_path, entry["privateManifest"]))
        graders = {str(grader["graderId"]): grader for grader in private.get("graders", [])}
        for case in public.get("cases", []):
            case_id = str(case.get("id") or "")
            grader_id = str(case.get("graderRef") or case_id)
            if grader_id not in graders:
                raise ValueError(f"legal grader missing: {grader_id}")
            for variant in case.get("variants", []):
                if str(variant.get("evaluationStatus") or "") == "excluded_invalid":
                    continue
                variant_id = str(variant.get("id") or "")
                full_id = f"{case_id}::{variant_id}"
                result[full_id] = {
                    "id": full_id,
                    "suite": "legal_e2e",
                    "responseFormat": "legal_e2e",
                    "publicPrompt": str(variant.get("query") or ""),
                    "privateGold": graders[grader_id],
                }
    return result


def prepare_grader(registry_path: Path, campaign_dir: Path) -> dict[str, Any]:
    validation = validate_answers(campaign_dir)
    if not validation["passed"]:
        raise ValueError("complete accepted answers.jsonl required before grader preparation")
    grader_dir = campaign_dir / "grader"
    ensure_new_directory(grader_dir)
    answers = {row["id"]: row["finalAnswer"] for row in load_jsonl(campaign_dir / "solver/output/answers.jsonl")}
    question_rows, _ = load_public_rows(registry_path)
    expected_ids = [row["id"] for row in question_rows]
    gold = private_exam_rows(registry_path)
    gold.update(private_legal_rows(registry_path))
    if set(gold) != set(expected_ids):
        raise ValueError("grader gold IDs do not match public expected IDs")
    rows = [{**gold[case_id], "solverAnswer": answers[case_id]} for case_id in expected_ids]
    input_dir = grader_dir / "input"
    output_dir = grader_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    packet_path = input_dir / "grading_packet.jsonl"
    write_jsonl(packet_path, rows)
    (input_dir / "RUN_INSTRUCTIONS.md").write_text(GRADER_INSTRUCTIONS, encoding="utf-8")
    write_json(input_dir / "expected_ids.json", {"count": len(expected_ids), "ids": expected_ids})
    freeze = {
        "schemaVersion": 1,
        "status": "prepared_no_grader_call",
        "protocol": "one_codex_grader_file_output_v1",
        "registrySha256": sha256_file(registry_path),
        "answersSha256": validation["answersSha256"],
        "gradingPacketSha256": sha256_file(packet_path),
        "gradingPacketBytes": packet_path.stat().st_size,
        "instructionsSha256": sha256_file(input_dir / "RUN_INSTRUCTIONS.md"),
        "expectedIdsSha256": canonical_digest(expected_ids),
        "expectedRows": len(expected_ids),
        "executionConfig": {
            "model": EXECUTION_MODEL,
            "reasoningEffort": EXECUTION_REASONING_EFFORT,
            "verbosity": EXECUTION_VERBOSITY,
            "serviceTier": "default",
            "nativeWebSearch": False,
            "localFileOperationsOnly": True,
            "database": False,
            "skills": False,
            "multiAgent": False,
        },
        "implementationHashes": implementation_hashes(),
    }
    freeze["freezeSha256"] = canonical_digest(freeze)
    write_json(grader_dir / "freeze.json", freeze)
    return freeze


def validate_grades(campaign_dir: Path, *, write_report: bool = True) -> dict[str, Any]:
    grader_dir = campaign_dir / "grader"
    expected = load_json(grader_dir / "input/expected_ids.json").get("ids")
    packet = {row["id"]: row for row in load_jsonl(grader_dir / "input/grading_packet.jsonl")}
    if not isinstance(expected, list) or set(expected) != set(packet):
        raise ValueError("expected grader IDs missing or inconsistent")
    path = grader_dir / "output/grades.jsonl"
    errors: list[str] = []
    rows: list[dict[str, Any]] = []
    if not path.is_file():
        errors.append("grades_file_missing")
    else:
        try:
            rows = load_jsonl(path)
        except Exception as exc:
            errors.append(f"grades_jsonl_invalid:{exc}")
    ids: list[str] = []
    binary = {"pass": 0, "fail": 0, "unresolved": 0}
    binary_exam = {"pass": 0, "fail": 0, "unresolved": 0}
    legal_e2e = {"pass": 0, "fail": 0, "unresolved": 0}
    raw_awarded = 0
    raw_maximum = 0
    for index, row in enumerate(rows):
        required = {"id", "gradeType", "verdict", "awardedMarks", "maxMarks", "reason"}
        if set(row) != required:
            errors.append(f"row_{index}_schema")
            continue
        case_id = str(row.get("id") or "")
        ids.append(case_id)
        if case_id not in packet:
            errors.append(f"row_{index}_unknown_id")
            continue
        expected_raw = packet[case_id]["responseFormat"] == "constructed_response"
        if expected_raw:
            maximum = int(packet[case_id]["privateGold"].get("maxMarks") or 0)
            if row.get("gradeType") != "raw_marks" or row.get("verdict") is not None:
                errors.append(f"row_{index}_raw_schema")
                continue
            awarded = row.get("awardedMarks")
            if not isinstance(awarded, int) or row.get("maxMarks") != maximum or not 0 <= awarded <= maximum:
                errors.append(f"row_{index}_raw_range")
                continue
            raw_awarded += awarded
            raw_maximum += maximum
        else:
            verdict = row.get("verdict")
            if row.get("gradeType") != "binary" or verdict not in binary:
                errors.append(f"row_{index}_binary_schema")
                continue
            if row.get("awardedMarks") is not None or row.get("maxMarks") is not None:
                errors.append(f"row_{index}_binary_marks_not_null")
                continue
            binary[verdict] += 1
            (legal_e2e if packet[case_id]["suite"] == "legal_e2e" else binary_exam)[verdict] += 1
        if not str(row.get("reason") or "").strip():
            errors.append(f"row_{index}_reason_empty")
    if ids != expected:
        errors.append("grade_ids_or_order_mismatch")
    report = {
        "schemaVersion": 1,
        "status": "accepted" if not errors else "unresolved",
        "passed": not errors,
        "errors": errors,
        "expectedRows": len(expected),
        "observedRows": len(rows),
        "binary": binary,
        "binaryExam": binary_exam,
        "legalEndToEnd": legal_e2e,
        "constructedRawMarks": {"awarded": raw_awarded, "maximum": raw_maximum},
        "officialExamPoints": {
            "awarded": binary_exam["pass"] + raw_awarded,
            "maximum": sum(binary_exam.values()) + raw_maximum,
        },
        "gradesSha256": sha256_file(path) if path.is_file() else None,
    }
    if write_report:
        write_json(grader_dir / "grade_validation.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare and validate the one-solver/one-grader file benchmark.")
    parser.add_argument("command", choices=["prepare-solver", "validate-answers", "prepare-grader", "validate-grades"])
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--campaign-dir", type=Path, required=True)
    args = parser.parse_args()
    registry = args.registry.resolve()
    campaign = args.campaign_dir.resolve()
    if args.command == "prepare-solver":
        result = prepare_solver(registry, campaign)
    elif args.command == "validate-answers":
        result = validate_answers(campaign)
    elif args.command == "prepare-grader":
        result = prepare_grader(registry, campaign)
    else:
        result = validate_grades(campaign)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("passed", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
