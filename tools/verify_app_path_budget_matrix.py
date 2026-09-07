#!/usr/bin/env python3
"""Verify latency budgets across multiple app-path/browser-submit artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


Case = tuple[str, Path]


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


def _stage_total_sec(data: dict[str, Any], stage: str) -> float:
    timings = data.get("stageTimings")
    if not isinstance(timings, dict):
        return 0.0
    totals = timings.get("totals")
    if not isinstance(totals, dict):
        return 0.0
    return _as_float(totals.get(stage))


def _engine_total_sec(data: dict[str, Any]) -> float:
    timings = data.get("stageTimings")
    if not isinstance(timings, dict):
        return 0.0
    return _as_float(timings.get("totalSec"))


def _wall_elapsed_sec(data: dict[str, Any]) -> float:
    return _as_float(data.get("wallElapsedSec") or data.get("wallClockSeconds") or data.get("wallClockSec"))


def _checked_total_sec(data: dict[str, Any]) -> float:
    return max(_engine_total_sec(data), _wall_elapsed_sec(data))


def _metric(data: dict[str, Any], key: str) -> int:
    metrics = data.get("metrics")
    if not isinstance(metrics, dict):
        return 0
    return _as_int(metrics.get(key))


def _format_budget(value: float) -> str:
    numeric = _as_float(value)
    return str(int(numeric)) if numeric.is_integer() else str(numeric)


def build_report(
    *,
    cases: list[Case],
    max_total_sec: float,
    max_source_selection_sec: float = 0,
    required_products: list[str] | None = None,
    require_cold_engine_cache: bool = False,
) -> dict[str, Any]:
    case_reports = [
        _case_report(
            product=product,
            path=path,
            max_total_sec=max_total_sec,
            max_source_selection_sec=max_source_selection_sec,
            require_cold_engine_cache=require_cold_engine_cache,
        )
        for product, path in cases
    ]
    failed = [case for case in case_reports if not case["passes"]]
    present_products = [case["product"] for case in case_reports]
    required = _normalize_products(required_products or [])
    missing_required = [product for product in required if product not in present_products]
    checks = {
        "requiredProducts": {
            "passes": not missing_required,
            "required": required,
            "present": present_products,
            "missing": missing_required,
        }
    }
    return {
        "passes": not failed and all(bool(check.get("passes")) for check in checks.values()),
        "budgets": {
            "maxTotalSec": max_total_sec,
            "maxSourceSelectionSec": max_source_selection_sec,
            "requireColdEngineCache": require_cold_engine_cache,
        },
        "checks": checks,
        "summary": {
            "caseCount": len(case_reports),
            "passedCount": len(case_reports) - len(failed),
            "failedCount": len(failed),
            "products": present_products,
        },
        "cases": case_reports,
    }


def _case_report(
    *,
    product: str,
    path: Path,
    max_total_sec: float,
    max_source_selection_sec: float,
    require_cold_engine_cache: bool,
) -> dict[str, Any]:
    data = _load_json(path)
    loaded = "_loadError" not in data
    engine_total = _engine_total_sec(data)
    wall_elapsed = _wall_elapsed_sec(data)
    checked_total = _checked_total_sec(data)
    total_measured = checked_total > 0
    source_selection = _stage_total_sec(data, "source_selection")
    source_selection_measured = source_selection > 0
    checks = {
        "loaded": {"passes": loaded, "message": data.get("_loadError", "")},
        "artifactPasses": {"passes": bool(data.get("passes"))},
        "totalLatency": {
            "passes": max_total_sec <= 0 or (total_measured and checked_total <= max_total_sec),
            "measured": total_measured,
            "engineTotalSec": engine_total,
            "wallElapsedSec": wall_elapsed,
            "checkedSec": checked_total,
            "expected": "" if max_total_sec <= 0 else f"<={_format_budget(max_total_sec)}",
        },
        "sourceSelectionLatency": {
            "passes": max_source_selection_sec <= 0
            or (source_selection_measured and source_selection <= max_source_selection_sec),
            "measured": source_selection_measured,
            "sourceSelectionSec": source_selection,
            "expected": "" if max_source_selection_sec <= 0 else f"<={_format_budget(max_source_selection_sec)}",
        },
    }
    if require_cold_engine_cache:
        cold_check = data.get("checks", {}).get("coldEngineCache") if isinstance(data.get("checks"), dict) else {}
        checks["coldEngineCache"] = {
            "passes": bool(isinstance(cold_check, dict) and cold_check.get("passes") is True),
            "required": True,
            "artifactReported": cold_check if isinstance(cold_check, dict) else {},
        }
    return {
        "passes": all(bool(check.get("passes")) for check in checks.values()),
        "product": product,
        "path": str(path),
        "metrics": {
            "answerChars": _metric(data, "answerChars"),
            "sourceCount": _metric(data, "sourceCount"),
            "citedClaimCount": _metric(data, "citedClaimCount"),
        },
        "checks": checks,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--case",
        action="append",
        default=[],
        metavar="PRODUCT=PATH",
        help="Artifact case to verify. Repeat for multiple products.",
    )
    parser.add_argument("--max-total-sec", type=float, required=True)
    parser.add_argument("--max-source-selection-sec", type=float, default=0)
    parser.add_argument(
        "--require-cold-engine-cache",
        "--require-cold-engine",
        action="store_true",
        help="Require each app-path artifact to report checks.coldEngineCache.passes=true.",
    )
    parser.add_argument(
        "--require-products",
        default="",
        help="Comma-separated product keys that must be present in the matrix.",
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    cases = [_parse_case(item) for item in args.case]
    report = build_report(
        cases=cases,
        max_total_sec=args.max_total_sec,
        max_source_selection_sec=args.max_source_selection_sec,
        required_products=_normalize_products(args.require_products.split(",")),
        require_cold_engine_cache=args.require_cold_engine_cache,
    )
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    if args.json:
        print(text)
    else:
        print("PASS app-path budget matrix" if report["passes"] else "FAIL app-path budget matrix")
    return 0 if report["passes"] else 1


def _parse_case(value: str) -> Case:
    product, sep, raw_path = value.partition("=")
    if not sep or not product.strip() or not raw_path.strip():
        raise argparse.ArgumentTypeError("--case must be PRODUCT=PATH")
    return product.strip(), Path(raw_path.strip())


def _normalize_products(values: list[str]) -> list[str]:
    out: list[str] = []
    for value in values:
        normalized = str(value or "").strip().lower()
        if normalized and normalized not in out:
            out.append(normalized)
    return out


if __name__ == "__main__":
    raise SystemExit(main())
