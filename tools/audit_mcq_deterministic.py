#!/usr/bin/env python3
"""Deterministic keyed-option audit for MCQ rows of a file campaign.

For every MCQ row, maps the answer text to a canonical option index using the
public prompt's option block (same matcher as the ensemble vote key) and
compares it to the private `correctOptionId`. This removes model-grader
variance from the 961 objective rows, as recommended by the 2026-07-24
benchmark report. Unmapped answers are reported separately and, when a model
grade file exists, fall back to that verdict in the hybrid total.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.prepare_plain_codex_file_benchmark import DEFAULT_REGISTRY, private_exam_rows
from tools.run_ensemble_file_agent import match_answer_to_option, parse_mcq_options


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def audit(answers_path: Path, grades_path: Path | None, registry_path: Path) -> dict:
    gold = private_exam_rows(registry_path)
    answers = {row["id"]: str(row.get("finalAnswer", "")) for row in load_jsonl(answers_path)}
    grades = (
        {row["id"]: row for row in load_jsonl(grades_path)}
        if grades_path and grades_path.is_file()
        else {}
    )
    per_bench: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    totals = defaultdict(int)
    for case_id, row in gold.items():
        if row["responseFormat"] != "mcq":
            continue
        correct = str(row["privateGold"].get("correctOptionId") or "").strip()
        if not correct:
            continue
        if len(correct) == 1 and correct.upper() in "ABCDEFGHIJ":
            correct = str(ord(correct.upper()) - ord("A") + 1)
        bench = case_id.rsplit("-", 1)[0]
        options = parse_mcq_options(row["publicPrompt"])
        mapped = match_answer_to_option(answers.get(case_id, ""), options)
        totals["mcq"] += 1
        if mapped:
            key = "pass" if mapped == correct else "fail"
            totals[f"det_{key}"] += 1
            per_bench[bench][f"det_{key}"] += 1
        else:
            totals["unmapped"] += 1
            per_bench[bench]["unmapped"] += 1
            verdict = (grades.get(case_id) or {}).get("verdict")
            if verdict in ("pass", "fail"):
                totals[f"fallback_{verdict}"] += 1
                per_bench[bench][f"fallback_{verdict}"] += 1
    hybrid_pass = totals["det_pass"] + totals["fallback_pass"]
    return {
        "mcqRows": totals["mcq"],
        "deterministicMapped": totals["mcq"] - totals["unmapped"],
        "deterministicPass": totals["det_pass"],
        "unmapped": totals["unmapped"],
        "fallbackPass": totals["fallback_pass"],
        "hybridMcqPass": hybrid_pass,
        "perBenchmark": {k: dict(v) for k, v in sorted(per_bench.items())},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--answers", type=Path, required=True)
    parser.add_argument("--grades", type=Path)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--label", default="")
    args = parser.parse_args()
    result = audit(args.answers, args.grades, args.registry)
    result["label"] = args.label or str(args.answers)
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
