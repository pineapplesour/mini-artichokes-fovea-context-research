#!/usr/bin/env python3
"""Compare full app-path beta-6 verifier artifacts.

Selector-only latency wins are not enough for rollout. This comparator gates a
variant on the same user-visible path the product runs: answer quality must
remain valid, and both total latency and source-selection latency must not
regress against the chosen baseline artifact.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"_loadError": f"missing file: {path}"}
    except json.JSONDecodeError as exc:
        return {"_loadError": f"invalid json: {exc}"}
    return value if isinstance(value, dict) else {"_loadError": "top-level JSON is not an object"}


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


def _metric(data: dict[str, Any], key: str) -> int:
    raw = data.get("metrics")
    if not isinstance(raw, dict):
        return 0
    return _as_int(raw.get(key))


def _total_sec(data: dict[str, Any]) -> float:
    timings = data.get("stageTimings")
    if not isinstance(timings, dict):
        return 0.0
    return _as_float(timings.get("totalSec"))


def _wall_elapsed_sec(data: dict[str, Any]) -> float:
    return _as_float(data.get("wallElapsedSec"))


def _checked_total_sec(data: dict[str, Any]) -> float:
    return max(_total_sec(data), _wall_elapsed_sec(data))


def _stage_total_sec(data: dict[str, Any], stage: str) -> float:
    timings = data.get("stageTimings")
    if not isinstance(timings, dict):
        return 0.0
    totals = timings.get("totals")
    if not isinstance(totals, dict):
        return 0.0
    return _as_float(totals.get(stage))


def _passes_named_check(data: dict[str, Any], key: str) -> bool:
    checks = data.get("checks")
    if not isinstance(checks, dict):
        return False
    check = checks.get(key)
    return isinstance(check, dict) and bool(check.get("passes"))


def _quality_passes(data: dict[str, Any]) -> bool:
    required = ("completed", "sourceGrounding", "answerDepth", "noForcedCoveragePatch")
    return bool(data.get("passes")) and all(_passes_named_check(data, key) for key in required)


def build_report(
    *,
    baseline_path: Path,
    variant_path: Path,
    max_total_sec: float = 0,
    max_source_selection_sec: float = 0,
) -> dict[str, Any]:
    baseline = _load_json(baseline_path)
    variant = _load_json(variant_path)
    baseline_total = _total_sec(baseline)
    variant_total = _total_sec(variant)
    baseline_wall_elapsed = _wall_elapsed_sec(baseline)
    variant_wall_elapsed = _wall_elapsed_sec(variant)
    baseline_checked_total = _checked_total_sec(baseline)
    variant_checked_total = _checked_total_sec(variant)
    baseline_source_selection = _stage_total_sec(baseline, "source_selection")
    variant_source_selection = _stage_total_sec(variant, "source_selection")
    total_delta = round(variant_checked_total - baseline_checked_total, 3)
    source_selection_delta = round(variant_source_selection - baseline_source_selection, 3)
    baseline_answer_chars = _metric(baseline, "answerChars")
    variant_answer_chars = _metric(variant, "answerChars")
    baseline_sources = _metric(baseline, "sourceCount")
    variant_sources = _metric(variant, "sourceCount")
    baseline_cited_claims = _metric(baseline, "citedClaimCount")
    variant_cited_claims = _metric(variant, "citedClaimCount")
    checks = {
        "baselineLoaded": {"passes": "_loadError" not in baseline, "message": baseline.get("_loadError", "")},
        "variantLoaded": {"passes": "_loadError" not in variant, "message": variant.get("_loadError", "")},
        "baselineQualityPasses": {"passes": _quality_passes(baseline)},
        "variantQualityPasses": {"passes": _quality_passes(variant)},
        "fasterTotal": {
            "passes": variant_checked_total <= baseline_checked_total,
            "baselineTotalSec": baseline_total,
            "variantTotalSec": variant_total,
            "baselineWallElapsedSec": baseline_wall_elapsed,
            "variantWallElapsedSec": variant_wall_elapsed,
            "baselineCheckedTotalSec": baseline_checked_total,
            "variantCheckedTotalSec": variant_checked_total,
            "deltaSec": total_delta,
        },
        "fasterSourceSelection": {
            "passes": variant_source_selection <= baseline_source_selection,
            "baselineSourceSelectionSec": baseline_source_selection,
            "variantSourceSelectionSec": variant_source_selection,
            "deltaSec": source_selection_delta,
        },
        "qualityNotRegressed": {
            "passes": variant_sources >= baseline_sources
            and variant_cited_claims >= baseline_cited_claims
            and variant_answer_chars >= baseline_answer_chars,
            "baselineSourceCount": baseline_sources,
            "variantSourceCount": variant_sources,
            "baselineCitedClaimCount": baseline_cited_claims,
            "variantCitedClaimCount": variant_cited_claims,
            "baselineAnswerChars": baseline_answer_chars,
            "variantAnswerChars": variant_answer_chars,
        },
        "absoluteTotalLatency": {
            "passes": max_total_sec <= 0 or variant_checked_total <= max_total_sec,
            "checkedSec": variant_checked_total,
            "expected": "" if max_total_sec <= 0 else f"<={_format_budget(max_total_sec)}",
        },
        "absoluteSourceSelectionLatency": {
            "passes": max_source_selection_sec <= 0 or variant_source_selection <= max_source_selection_sec,
            "sourceSelectionSec": variant_source_selection,
            "expected": "" if max_source_selection_sec <= 0 else f"<={_format_budget(max_source_selection_sec)}",
        },
    }
    return {
        "passes": all(bool(check.get("passes")) for check in checks.values()),
        "baseline": str(baseline_path),
        "variant": str(variant_path),
        "metrics": {
            "totalDeltaSec": total_delta,
            "sourceSelectionDeltaSec": source_selection_delta,
            "answerCharsDelta": variant_answer_chars - baseline_answer_chars,
            "sourceCountDelta": variant_sources - baseline_sources,
            "citedClaimDelta": variant_cited_claims - baseline_cited_claims,
        },
        "checks": checks,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--variant", required=True, type=Path)
    parser.add_argument("--max-total-sec", type=float, default=0, help="Optional absolute checked-total latency budget. 0 disables.")
    parser.add_argument(
        "--max-source-selection-sec",
        type=float,
        default=0,
        help="Optional absolute source-selection latency budget. 0 disables.",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    report = build_report(
        baseline_path=args.baseline,
        variant_path=args.variant,
        max_total_sec=args.max_total_sec,
        max_source_selection_sec=args.max_source_selection_sec,
    )
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report["passes"] else 1


def _format_budget(value: float) -> str:
    numeric = _as_float(value)
    return str(int(numeric)) if numeric.is_integer() else str(numeric)


if __name__ == "__main__":
    raise SystemExit(main())
