#!/usr/bin/env python3
"""Analyze beta6 selector batch latency projections from a selector_meta artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def build_report(
    *,
    selector_meta: str | Path | None = None,
    artifact: str | Path | None = None,
    workers: list[int] | None = None,
    max_source_selection_sec: float = 30.0,
) -> dict[str, Any]:
    source_path = Path(selector_meta or artifact or "")
    data = _load_json(source_path) if source_path else {"_loadError": "missing selector meta or artifact path"}
    loaded = "_loadError" not in data
    batch_trace, exact_full_trace = _extract_batch_trace(data)
    durations = [_as_float(item.get("elapsedSec")) for item in batch_trace if _as_float(item.get("elapsedSec")) > 0]
    current_workers = _as_int(data.get("selectorBatchWorkers")) or 0
    worker_counts = _normalize_workers(workers, current_workers=current_workers, batch_count=len(durations))
    projections = [
        _projection_report(durations=durations, worker_count=worker_count, budget=max_source_selection_sec)
        for worker_count in worker_counts
    ]
    max_batch_sec = round(max(durations), 3) if durations else 0.0
    sum_batch_sec = round(sum(durations), 3)
    best_projection = min((item["projectedSec"] for item in projections), default=0.0)
    worker_only_check = _worker_only_check(
        loaded=loaded,
        exact_full_trace=exact_full_trace,
        durations=durations,
        projections=projections,
        max_batch_sec=max_batch_sec,
        budget=max_source_selection_sec,
    )
    checks = {
        "loaded": {"passes": loaded, "message": data.get("_loadError", "")},
        "fullBatchTrace": {
            "passes": bool(exact_full_trace and durations),
            "exactFullTrace": exact_full_trace,
            "batchCount": len(durations),
        },
        "workerOnlyCanMeetBudget": worker_only_check,
    }
    return {
        "passes": all(bool(check.get("passes")) for check in checks.values()),
        "source": {
            "path": str(source_path),
            "kind": "selector_meta" if selector_meta else "artifact",
            "exactFullTrace": exact_full_trace,
        },
        "budget": {"maxSourceSelectionSec": max_source_selection_sec},
        "summary": {
            "batchCount": len(durations),
            "currentWorkers": current_workers,
            "batchSize": _as_int(data.get("selectorBatchSize")),
            "candidateLimit": _as_int(data.get("selectorCandidateLimit")),
            "sumBatchSec": sum_batch_sec,
            "maxBatchSec": max_batch_sec,
            "bestProjectedSec": best_projection,
            "workerCounts": worker_counts,
        },
        "checks": checks,
        "projections": projections,
    }


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"_loadError": f"missing file: {path}"}
    except json.JSONDecodeError as exc:
        return {"_loadError": f"invalid json: {exc}"}
    return value if isinstance(value, dict) else {"_loadError": "top-level JSON is not an object"}


def _extract_batch_trace(data: dict[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    trace = data.get("selectorBatchTrace")
    if isinstance(trace, list):
        return [item for item in trace if isinstance(item, dict)], True
    batches = data.get("selectorBatches")
    if isinstance(batches, list):
        return [item for item in batches if isinstance(item, dict)], True
    selection_trace = data.get("selectionTrace")
    if isinstance(selection_trace, dict):
        selector_batches = selection_trace.get("selectorBatches")
        if isinstance(selector_batches, dict):
            slowest = selector_batches.get("slowest")
            if isinstance(slowest, list):
                items = [item for item in slowest if isinstance(item, dict)]
                return items, len(items) == _as_int(selector_batches.get("count"))
    return [], False


def _projection_report(*, durations: list[float], worker_count: int, budget: float) -> dict[str, Any]:
    projected = _project_makespan(durations, worker_count)
    work_lower_bound = round(sum(durations) / worker_count, 3) if worker_count > 0 and durations else 0.0
    max_batch = round(max(durations), 3) if durations else 0.0
    return {
        "workers": worker_count,
        "projectedSec": projected,
        "workLowerBoundSec": work_lower_bound,
        "maxBatchLowerBoundSec": max_batch,
        "passesBudget": budget <= 0 or projected <= budget,
    }


def _project_makespan(durations: list[float], worker_count: int) -> float:
    if worker_count <= 0 or not durations:
        return 0.0
    lanes = [0.0 for _ in range(worker_count)]
    for duration in durations:
        lane = min(range(worker_count), key=lambda index: lanes[index])
        lanes[lane] += duration
    return round(max(lanes), 3)


def _worker_only_check(
    *,
    loaded: bool,
    exact_full_trace: bool,
    durations: list[float],
    projections: list[dict[str, Any]],
    max_batch_sec: float,
    budget: float,
) -> dict[str, Any]:
    if not loaded:
        return {"passes": False, "reason": "source_not_loaded"}
    if not exact_full_trace or not durations:
        return {"passes": False, "reason": "missing_full_selector_batch_trace"}
    if budget > 0 and max_batch_sec > budget:
        return {
            "passes": False,
            "reason": "single_batch_exceeds_budget",
            "maxBatchSec": max_batch_sec,
            "expected": f"<={_format_budget(budget)}",
        }
    projected_passes = [item for item in projections if item.get("passesBudget")]
    if budget > 0 and not projected_passes:
        return {
            "passes": False,
            "reason": "projected_workers_still_over_budget",
            "bestProjectedSec": min((item["projectedSec"] for item in projections), default=0.0),
            "expected": f"<={_format_budget(budget)}",
        }
    return {
        "passes": True,
        "reason": "projection_has_budget_passing_worker_count" if budget > 0 else "budget_disabled",
        "bestProjectedSec": min((item["projectedSec"] for item in projections), default=0.0),
    }


def _normalize_workers(workers: list[int] | None, *, current_workers: int, batch_count: int) -> list[int]:
    raw = workers or [1, 2, current_workers, current_workers + 2, current_workers * 2, batch_count]
    out: list[int] = []
    for value in raw:
        normalized = int(value or 0)
        if normalized > 0 and normalized not in out:
            out.append(normalized)
    return out or [1]


def _parse_workers(value: str) -> list[int]:
    out: list[int] = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        out.append(int(item))
    return out


def _as_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _format_budget(value: float) -> str:
    numeric = _as_float(value)
    return str(int(numeric)) if numeric.is_integer() else str(numeric)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selector-meta", type=Path, help="Path to job selector_meta.json.")
    parser.add_argument("--artifact", type=Path, help="Path to compact app-path artifact if selector meta is unavailable.")
    parser.add_argument("--workers", default="", help="Comma-separated worker counts to project, e.g. 1,2,4,8,12.")
    parser.add_argument("--max-source-selection-sec", type=float, default=30.0)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    report = build_report(
        selector_meta=args.selector_meta,
        artifact=args.artifact,
        workers=_parse_workers(args.workers) if args.workers else None,
        max_source_selection_sec=args.max_source_selection_sec,
    )
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    if args.json:
        print(text)
    else:
        print("PASS selector batch latency analysis" if report["passes"] else "FAIL selector batch latency analysis")
    return 0 if report["passes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
