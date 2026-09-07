#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def aggregate_score_reports(
    reports: list[dict[str, Any]],
    *,
    expected_case_ids: list[str] | None = None,
) -> dict[str, Any]:
    if not reports:
        raise ValueError("at least one score report is required")
    benchmark_ids = {str(report.get("benchmarkId") or "") for report in reports}
    if len(benchmark_ids) != 1 or not next(iter(benchmark_ids)):
        raise ValueError("all score reports must have the same nonempty benchmarkId")
    cases_by_id: dict[str, dict[str, Any]] = {}
    resource_snapshots: list[dict[str, Any]] = []
    judge_calls_used = 0
    judge_call_budget = 0
    judge_models: set[str] = set()
    for report in reports:
        cases = report.get("cases")
        if not isinstance(cases, list) or not cases:
            raise ValueError("every score report must contain at least one case")
        for case in cases:
            case_id = str(case.get("caseId") or "").strip() if isinstance(case, dict) else ""
            if not case_id:
                raise ValueError("score case is missing caseId")
            if case_id in cases_by_id:
                raise ValueError(f"duplicate score case: {case_id}")
            cases_by_id[case_id] = case
        judge_calls_used += int(report.get("judgeCallsUsed") or 0)
        judge_call_budget += int(report.get("judgeCallBudget") or 0)
        judge_model = str(report.get("judgeModel") or "").strip()
        if judge_model:
            judge_models.add(judge_model)
        snapshot = report.get("resourceGateAtStart")
        if isinstance(snapshot, dict):
            resource_snapshots.append(snapshot)
    expected = [str(value).strip() for value in expected_case_ids or [] if str(value).strip()]
    if expected:
        if len(expected) != len(set(expected)):
            raise ValueError("expected case IDs contain duplicates")
        missing = [case_id for case_id in expected if case_id not in cases_by_id]
        extra = sorted(set(cases_by_id) - set(expected))
        if missing or extra:
            raise ValueError(f"score coverage mismatch: missing={missing}, extra={extra}")
        ordered_cases = [cases_by_id[case_id] for case_id in expected]
    else:
        ordered_cases = [cases_by_id[case_id] for case_id in sorted(cases_by_id)]
    passed = sum(1 for case in ordered_cases if case.get("verdict") == "pass")
    failed = sum(1 for case in ordered_cases if case.get("verdict") == "fail")
    unresolved = len(ordered_cases) - passed - failed
    return {
        "schemaVersion": 1,
        "benchmarkId": next(iter(benchmark_ids)),
        "taskType": "open_response",
        "total": len(ordered_cases),
        "passed": passed,
        "failed": failed,
        "unresolved": unresolved,
        "accuracy": passed / len(ordered_cases) if ordered_cases else 0.0,
        "judgeModels": sorted(judge_models),
        "judgeCallsUsed": judge_calls_used,
        "judgeCallBudget": judge_call_budget,
        "resourceGateSnapshots": resource_snapshots,
        "cases": ordered_cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge separately judged open-response case reports with exact coverage checks.")
    parser.add_argument("--input", action="append", type=Path, required=True)
    parser.add_argument("--expected-case-id", action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    reports = [json.loads(path.read_text(encoding="utf-8")) for path in args.input]
    aggregate = aggregate_score_reports(reports, expected_case_ids=args.expected_case_id)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(aggregate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in aggregate.items() if key not in {"cases", "resourceGateSnapshots"}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
