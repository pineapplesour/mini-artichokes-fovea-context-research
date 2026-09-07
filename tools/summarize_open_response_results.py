#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any


TOKEN_FIELDS = (
    "inputTokens",
    "cachedInputTokens",
    "outputTokens",
    "reasoningOutputTokens",
    "totalTokens",
)


def summarize_result_files(paths: list[Path]) -> dict[str, Any]:
    if not paths:
        raise ValueError("at least one result file is required")
    cases: list[dict[str, Any]] = []
    seen: set[str] = set()
    totals = {field: 0 for field in TOKEN_FIELDS}
    latencies: list[float] = []
    for path in paths:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"expected JSON object: {path}")
        case_id = str(payload.get("caseId") or payload.get("id") or "").strip()
        if not case_id:
            raise ValueError(f"result is missing caseId: {path}")
        if case_id in seen:
            raise ValueError(f"duplicate caseId: {case_id}")
        seen.add(case_id)
        trace = payload.get("modelTrace") if isinstance(payload.get("modelTrace"), dict) else {}
        usage = trace.get("tokenUsage") if isinstance(trace.get("tokenUsage"), dict) else {}
        elapsed = float(payload.get("elapsedSec") or trace.get("elapsedSec") or 0.0)
        if elapsed <= 0:
            raise ValueError(f"result is missing positive elapsedSec: {path}")
        token_usage: dict[str, int] = {}
        for field in TOKEN_FIELDS:
            value = usage.get(field)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"result is missing nonnegative {field}: {path}")
            token_usage[field] = value
            totals[field] += value
        latencies.append(elapsed)
        cases.append(
            {
                "caseId": case_id,
                "resultPath": str(path),
                "elapsedSec": elapsed,
                "tokenUsage": token_usage,
            }
        )
    return {
        "schemaVersion": 1,
        "totalCases": len(cases),
        "tokenUsage": totals,
        "latencySec": {
            "median": statistics.median(latencies),
            "maximum": max(latencies),
            "total": sum(latencies),
        },
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize exact open-response result files for paired gates.")
    parser.add_argument("--input", action="append", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = summarize_result_files(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "cases"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
