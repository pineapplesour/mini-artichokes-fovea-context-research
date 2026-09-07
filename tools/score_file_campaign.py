#!/usr/bin/env python3
"""Aggregate a graded file campaign into the official score table.

Reads the campaign's questions and grades, then reports:
  - binary exam pass/fail/unresolved (1,251 cases);
  - constructed-response raw marks out of the official maximum;
  - official exam points (binary passes + constructed marks) out of 1,589;
  - legal E2E pass/fail separately (10 variants);
  - a per-benchmark breakdown.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign-dir", type=Path, required=True)
    args = parser.parse_args()
    campaign = args.campaign_dir.resolve()
    questions = load_jsonl(campaign / "solver/input/questions.jsonl")
    grades = {row["id"]: row for row in load_jsonl(campaign / "grader/output/grades.jsonl")}
    meta = {row["id"]: row for row in questions}

    per_bench: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    totals = defaultdict(float)
    for case_id, question in meta.items():
        grade = grades.get(case_id)
        bench = question["benchmarkId"]
        suite = question["suite"]
        if grade is None:
            per_bench[bench]["missing"] += 1
            continue
        if grade.get("gradeType") == "raw_marks":
            awarded = float(grade.get("awardedMarks") or 0)
            maximum = float(grade.get("maxMarks") or 0)
            per_bench[bench]["marks"] += awarded
            per_bench[bench]["maxMarks"] += maximum
            totals["constructedMarks"] += awarded
            totals["constructedMax"] += maximum
            continue
        verdict = grade.get("verdict")
        bucket = "legal" if suite == "legal_e2e" else "binary"
        key = {"pass": "pass", "fail": "fail"}.get(verdict, "unresolved")
        per_bench[bench][key] += 1
        totals[f"{bucket}_{key}"] += 1

    print(json.dumps({"perBenchmark": {k: dict(v) for k, v in sorted(per_bench.items())}}, ensure_ascii=False, indent=1))
    binary_pass = int(totals["binary_pass"])
    binary_total = int(totals["binary_pass"] + totals["binary_fail"] + totals["binary_unresolved"])
    marks = int(totals["constructedMarks"])
    marks_max = int(totals["constructedMax"])
    exam_points = binary_pass + marks
    exam_max = binary_total + marks_max
    print(f"binary exam: {binary_pass}/{binary_total} "
          f"(fail {int(totals['binary_fail'])}, unresolved {int(totals['binary_unresolved'])})")
    print(f"constructed: {marks}/{marks_max}")
    print(f"OFFICIAL EXAM POINTS: {exam_points}/{exam_max} = {exam_points/exam_max:.4%}")
    print(f"legal E2E: pass {int(totals['legal_pass'])} / fail {int(totals['legal_fail'])} "
          f"/ unresolved {int(totals['legal_unresolved'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
