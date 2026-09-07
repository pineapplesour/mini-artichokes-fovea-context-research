#!/usr/bin/env python3
"""Build a gold-separated, stratified MMLU-Pro whole-file confirmation set."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import pyarrow.parquet as pq


REPO_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = "mini_artichokes_mmlu_pro_confirmation_base_v1"
BENCHMARK_ID = "mcq.mmlu_pro.stratified1000.v1"
SELECTION_SEED = "mini-artichokes-mmlu-pro-confirmation-v1-20260901"
MODEL = "gpt-5.6-luna"
REASONING_EFFORT = "high"
VERBOSITY = "low"
LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


SOLVER_INSTRUCTIONS = """# MMLU-Pro whole-file solver contract

This is one model invocation over the complete 1,000-question public file.
Do not spawn agents, call another model, browse the web, or inspect paths
outside this isolated workspace. Solve every row in `input/questions.jsonl`
independently from its question and options.

For each row, write the exact text of one selected option to `finalAnswer`.
Do not write only an option letter or number, and do not append a rationale.
Write progress to `output/answers.partial.jsonl`. When all rows are complete,
atomically finish `output/answers.jsonl` in input order. Every line must be
exactly one UTF-8 JSON object with no extra keys:

`{"id":"the exact input id","finalAnswer":"exact selected option text"}`

There must be exactly 1,000 non-empty rows and every supplied ID exactly once.
The final chat message should only state whether the complete file was made.
"""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return " ".join(value.split())


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"".join(canonical_bytes(row) + b"\n" for row in rows))


def largest_remainder_counts(category_sizes: dict[str, int], total: int) -> dict[str, int]:
    population = sum(category_sizes.values())
    if total < 0 or total > population:
        raise ValueError("requested total must be within the available population")
    if total == 0:
        return {category: 0 for category in category_sizes}
    quotas = {category: size * total / population for category, size in category_sizes.items()}
    counts = {category: math.floor(quota) for category, quota in quotas.items()}
    remaining = total - sum(counts.values())
    ranking = sorted(category_sizes, key=lambda category: (-(quotas[category] - counts[category]), category))
    for category in ranking[:remaining]:
        counts[category] += 1
    if sum(counts.values()) != total or any(counts[key] > category_sizes[key] for key in counts):
        raise AssertionError("largest-remainder allocation invariant failed")
    return counts


def selection_key(row: dict[str, Any]) -> bytes:
    payload = f"{SELECTION_SEED}\0{row['category']}\0{row['question_id']}".encode()
    return hashlib.sha256(payload).digest()


def format_prompt(question: str, options: list[str]) -> str:
    if not 2 <= len(options) <= len(LETTERS):
        raise ValueError("unsupported option count")
    option_lines = "\n".join(f"{LETTERS[index]}. {option}" for index, option in enumerate(options))
    return f"Question:\n{question.strip()}\n\nOptions:\n{option_lines}"


def prior_prompts(path: Path) -> list[str]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [normalize_text(str(row.get("prompt") or "")) for row in rows]


def overlaps_prior(question: str, prompt: str, prior: list[str]) -> bool:
    question_norm = normalize_text(question)
    prompt_norm = normalize_text(prompt)
    if prompt_norm in prior:
        return True
    if len(question_norm) < 50:
        return False
    return any(question_norm in old or old in question_norm for old in prior if len(old) >= 50)


def select_rows(
    rows: list[dict[str, Any]],
    total: int,
    prior: list[str],
    *,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], dict[str, int], int]:
    unique: dict[str, dict[str, Any]] = {}
    duplicate_count = 0
    overlap_count = 0
    for row in rows:
        prompt = format_prompt(str(row["question"]), list(row["options"]))
        fingerprint = normalize_text(prompt)
        if fingerprint in unique:
            duplicate_count += 1
            continue
        if overlaps_prior(str(row["question"]), prompt, prior):
            overlap_count += 1
            continue
        unique[fingerprint] = row
    by_category: dict[str, list[dict[str, Any]]] = {}
    for row in unique.values():
        by_category.setdefault(str(row["category"]), []).append(row)
    sizes = {category: len(items) for category, items in by_category.items()}
    if offset < 0 or offset + total > sum(sizes.values()):
        raise ValueError("offset/count range exceeds eligible population")
    start_counts = largest_remainder_counts(sizes, offset)
    end_counts = largest_remainder_counts(sizes, offset + total)
    counts = {category: end_counts[category] - start_counts[category] for category in sizes}
    selected: list[dict[str, Any]] = []
    for category in sorted(by_category):
        ordered = sorted(by_category[category], key=selection_key)
        selected.extend(ordered[start_counts[category] : end_counts[category]])
    selected.sort(key=lambda row: (str(row["category"]), int(row["question_id"])))
    return selected, counts, duplicate_count + overlap_count


def ensure_empty(path: Path) -> None:
    if path.exists() and any(path.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty directory: {path}")
    path.mkdir(parents=True, exist_ok=True)


def build(args: argparse.Namespace) -> dict[str, Any]:
    if sha256_file(args.parquet) != args.expected_parquet_sha256:
        raise ValueError("MMLU-Pro parquet hash mismatch")
    table = pq.read_table(args.parquet)
    rows = table.to_pylist()
    required = {"question_id", "question", "options", "answer", "answer_index", "category", "src"}
    if not rows or any(not required.issubset(row) for row in rows):
        raise ValueError("unexpected MMLU-Pro schema")
    prior = prior_prompts(args.prior_questions)
    selected, allocation, excluded = select_rows(rows, args.count, prior, offset=args.offset)
    if len(selected) != args.count:
        raise AssertionError("selected denominator mismatch")

    public_rows: list[dict[str, Any]] = []
    private_rows: list[dict[str, Any]] = []
    for row in selected:
        options = [str(value) for value in row["options"]]
        answer_index = int(row["answer_index"])
        if not 0 <= answer_index < len(options):
            raise ValueError(f"answer index outside options: {row['question_id']}")
        case_id = f"mmlu-pro-{int(row['question_id']):05d}"
        public_rows.append(
            {
                "benchmarkId": BENCHMARK_ID,
                "category": str(row["category"]),
                "id": case_id,
                "language": "en",
                "prompt": format_prompt(str(row["question"]), options),
                "responseFormat": "mcq",
                "suite": "exam",
            }
        )
        private_rows.append(
            {
                "caseId": case_id,
                "category": str(row["category"]),
                "correctOptionId": LETTERS[answer_index],
                "correctOptionIndex": answer_index + 1,
                "questionId": int(row["question_id"]),
                "source": str(row["src"]),
            }
        )
    ids = [row["id"] for row in public_rows]
    if len(ids) != len(set(ids)):
        raise ValueError("selected IDs are not unique")

    ensure_empty(args.output_dir)
    public_path = args.output_dir / "mmlu_pro_stratified1000.public.jsonl"
    private_path = args.output_dir / "mmlu_pro_stratified1000.private.jsonl"
    write_jsonl(public_path, public_rows)
    write_jsonl(private_path, private_rows)

    ensure_empty(args.campaign_dir / "solver")
    input_dir = args.campaign_dir / "solver/input"
    output_dir = args.campaign_dir / "solver/output"
    output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(input_dir / "questions.jsonl", public_rows)
    (input_dir / "RUN_INSTRUCTIONS.md").write_text(SOLVER_INSTRUCTIONS, encoding="utf-8")
    write_json(input_dir / "expected_ids.json", {"count": len(ids), "ids": ids})
    implementation_paths = [Path(__file__).resolve(), REPO_ROOT / "tools/run_plain_codex_file_agent.py"]
    freeze = {
        "schemaVersion": 1,
        "status": "prepared_no_model_calls",
        "protocol": PROTOCOL,
        "benchmarkId": BENCHMARK_ID,
        "source": {
            "dataset": "TIGER-Lab/MMLU-Pro",
            "gitCommit": args.source_commit,
            "parquetSha256": args.expected_parquet_sha256,
            "testRows": len(rows),
        },
        "selection": {
            "seed": SELECTION_SEED,
            "offset": args.offset,
            "requestedRows": args.count,
            "allocation": allocation,
            "excludedPriorOrDuplicateRows": excluded,
            "priorQuestionsSha256": sha256_file(args.prior_questions),
        },
        "questionsPath": "input/questions.jsonl",
        "questionsSha256": sha256_file(input_dir / "questions.jsonl"),
        "instructionsSha256": sha256_file(input_dir / "RUN_INSTRUCTIONS.md"),
        "expectedIdsFileSha256": sha256_file(input_dir / "expected_ids.json"),
        "expectedIdsSha256": canonical_digest(ids),
        "inventory": {"rows": len(ids), "mcqRows": len(ids)},
        "executionConfig": {
            "model": MODEL,
            "reasoningEffort": REASONING_EFFORT,
            "verbosity": VERBOSITY,
            "serviceTier": "default",
            "nativeWebSearch": False,
            "localCode": True,
            "database": False,
            "skills": False,
            "multiAgent": False,
        },
        "implementationHashes": {str(path): sha256_file(path) for path in implementation_paths},
    }
    freeze["freezeSha256"] = canonical_digest(freeze)
    write_json(args.campaign_dir / "solver/freeze.json", freeze)
    report = {
        "protocol": PROTOCOL,
        "benchmarkId": BENCHMARK_ID,
        "rows": len(ids),
        "categories": dict(sorted(Counter(row["category"] for row in public_rows).items())),
        "publicSha256": sha256_file(public_path),
        "privateSha256": sha256_file(private_path),
        "freezeSha256": freeze["freezeSha256"],
        "selectionSeed": SELECTION_SEED,
        "selectionOffset": args.offset,
        "excludedPriorOrDuplicateRows": excluded,
    }
    write_json(args.output_dir / "build_report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parquet", type=Path, required=True)
    parser.add_argument("--expected-parquet-sha256", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--prior-questions", type=Path, required=True)
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--campaign-dir", type=Path, required=True)
    args = parser.parse_args()
    build(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
