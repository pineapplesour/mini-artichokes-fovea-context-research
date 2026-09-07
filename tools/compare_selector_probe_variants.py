#!/usr/bin/env python3
"""Compare beta-6 selector tuning probe artifacts.

This verifier is intentionally conservative: a faster selector-only probe is not
safe by itself if selected evidence shape collapses or drifts too far from the
baseline used for answer-quality work.
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


def _source_kinds(data: dict[str, Any]) -> dict[str, int]:
    raw = data.get("selectedSourceKinds")
    if isinstance(raw, dict):
        out: dict[str, int] = {}
        for key, value in raw.items():
            normalized = str(key or "").strip()
            if not normalized:
                continue
            out[normalized] = _as_int(value)
        return out
    return {}


def _selected_ids(data: dict[str, Any]) -> set[str]:
    raw = data.get("selectedIds")
    if not isinstance(raw, list):
        return set()
    return {str(item) for item in raw if str(item or "").strip()}


def _selector_cache_counts(data: dict[str, Any]) -> tuple[int, int]:
    cache_metrics = data.get("cacheMetrics")
    selector_metrics = {}
    if isinstance(cache_metrics, dict) and isinstance(cache_metrics.get("selectorBatches"), dict):
        selector_metrics = cache_metrics.get("selectorBatches") or {}
    hits = data.get("selectorBatchCacheHits", selector_metrics.get("hits"))
    misses = data.get("selectorBatchCacheMisses", selector_metrics.get("misses"))
    return _as_int(hits), _as_int(misses)


def _selector_recovery_counts(data: dict[str, Any]) -> tuple[int, int]:
    beta6 = data.get("beta6") if isinstance(data.get("beta6"), dict) else {}
    local_recovery = data.get("selectorLocalRecoveryCount", beta6.get("selectorLocalRecoveryCount"))
    over_timeout = data.get("overTimeoutCount", beta6.get("overTimeoutCount"))
    return _as_int(local_recovery), _as_int(over_timeout)


def _selector_shape(data: dict[str, Any]) -> dict[str, int]:
    return {
        "selectorBatchSize": _as_int(data.get("selectorBatchSize")),
        "selectorBatchWorkers": _as_int(data.get("selectorBatchWorkers")),
        "selectorCandidateLimit": _as_int(data.get("selectorCandidateLimit")),
        "selectorAuditedCandidateCount": _as_int(data.get("selectorAuditedCandidateCount")),
    }


def _prompt_metrics(data: dict[str, Any]) -> dict[str, int]:
    metrics = {
        "maxPromptBytes": _as_int(data.get("maxPromptBytes")),
        "maxPrimaryPromptBytes": _as_int(data.get("maxPrimaryPromptBytes")),
        "maxRecoveryPromptBytes": _as_int(data.get("maxRecoveryPromptBytes")),
    }
    if any(value > 0 for value in metrics.values()):
        return metrics
    slowest = data.get("selectorSlowest")
    if isinstance(slowest, list):
        items = [item for item in slowest if isinstance(item, dict)]
        if items:
            return {
                "maxPromptBytes": max((_as_int(item.get("maxPromptBytes")) for item in items), default=0),
                "maxPrimaryPromptBytes": max((_as_int(item.get("primaryMaxPromptBytes")) for item in items), default=0),
                "maxRecoveryPromptBytes": max((_as_int(item.get("recoveryMaxPromptBytes")) for item in items), default=0),
            }
    return metrics


def _missing_selector_shape_fields(baseline_shape: dict[str, int], variant_shape: dict[str, int]) -> list[str]:
    missing: list[str] = []
    for key in baseline_shape:
        if baseline_shape.get(key, 0) <= 0 or variant_shape.get(key, 0) <= 0:
            missing.append(key)
    return missing


def build_report(
    *,
    baseline_path: Path,
    variant_path: Path,
    speed_floor_path: Path | None = None,
    min_overlap: int,
    require_baseline_kinds: bool,
    require_variant_cold_selector: bool = False,
    require_same_selector_shape: bool = False,
    require_clean_selector: bool = False,
    require_prompt_reduction: bool = False,
) -> dict[str, Any]:
    baseline = _load_json(baseline_path)
    variant = _load_json(variant_path)
    speed_floor = _load_json(speed_floor_path) if speed_floor_path else {}
    baseline_ids = _selected_ids(baseline)
    variant_ids = _selected_ids(variant)
    overlap = baseline_ids & variant_ids
    baseline_kinds = _source_kinds(baseline)
    variant_kinds = _source_kinds(variant)
    baseline_required_kinds = sorted(kind for kind, count in baseline_kinds.items() if count > 0)
    missing_kinds = [kind for kind in baseline_required_kinds if variant_kinds.get(kind, 0) <= 0]
    baseline_elapsed = _as_float(baseline.get("elapsedSec"))
    variant_elapsed = _as_float(variant.get("elapsedSec"))
    floor_elapsed = _as_float(speed_floor.get("elapsedSec")) if speed_floor_path else 0.0
    effective_floor_values = [value for value in (baseline_elapsed, floor_elapsed) if value > 0]
    effective_floor = min(effective_floor_values) if effective_floor_values else 0.0
    speed_floor_passes = True
    if speed_floor_path:
        speed_floor_passes = (
            "_loadError" not in speed_floor
            and bool(speed_floor.get("passes"))
            and effective_floor > 0
            and variant_elapsed <= effective_floor
        )
    variant_cache_hits, variant_cache_misses = _selector_cache_counts(variant)
    variant_is_cold = variant_cache_hits == 0 and variant_cache_misses > 0
    variant_local_recovery, variant_over_timeout = _selector_recovery_counts(variant)
    variant_clean_selector = variant_local_recovery == 0 and variant_over_timeout == 0
    baseline_shape = _selector_shape(baseline)
    variant_shape = _selector_shape(variant)
    missing_shape_fields = _missing_selector_shape_fields(baseline_shape, variant_shape)
    changed_shape_fields = [
        key
        for key, baseline_value in baseline_shape.items()
        if baseline_value > 0 and variant_shape.get(key, 0) > 0 and variant_shape[key] != baseline_value
    ]
    selector_shape_passes = not require_same_selector_shape or (not missing_shape_fields and not changed_shape_fields)
    baseline_prompt = _prompt_metrics(baseline)
    variant_prompt = _prompt_metrics(variant)
    prompt_measured = baseline_prompt["maxPromptBytes"] > 0 and variant_prompt["maxPromptBytes"] > 0
    prompt_reduced = prompt_measured and variant_prompt["maxPromptBytes"] <= baseline_prompt["maxPromptBytes"]
    prompt_size_passes = not require_prompt_reduction or prompt_reduced
    checks = {
        "baselineLoaded": {"passes": "_loadError" not in baseline, "message": baseline.get("_loadError", "")},
        "variantLoaded": {"passes": "_loadError" not in variant, "message": variant.get("_loadError", "")},
        "baselinePassed": {"passes": bool(baseline.get("passes"))},
        "variantPassed": {"passes": bool(variant.get("passes"))},
        "countsPreserved": {
            "passes": _as_int(variant.get("candidateCount")) >= _as_int(baseline.get("candidateCount"))
            and _as_int(variant.get("selectedCount")) >= _as_int(baseline.get("selectedCount")),
            "baselineCandidateCount": _as_int(baseline.get("candidateCount")),
            "variantCandidateCount": _as_int(variant.get("candidateCount")),
            "baselineSelectedCount": _as_int(baseline.get("selectedCount")),
            "variantSelectedCount": _as_int(variant.get("selectedCount")),
        },
        "fasterOrEqual": {
            "passes": variant_elapsed <= baseline_elapsed,
            "baselineElapsedSec": baseline_elapsed,
            "variantElapsedSec": variant_elapsed,
        },
        "speedFloor": {
            "passes": speed_floor_passes,
            "required": bool(speed_floor_path),
            "baseline": str(speed_floor_path) if speed_floor_path else "",
            "message": speed_floor.get("_loadError", "") if speed_floor_path else "",
            "baselineElapsedSec": baseline_elapsed,
            "floorElapsedSec": floor_elapsed,
            "effectiveFloorSec": effective_floor,
            "variantElapsedSec": variant_elapsed,
        },
        "selectedOverlap": {
            "passes": len(overlap) >= int(min_overlap),
            "overlapCount": len(overlap),
            "minOverlap": int(min_overlap),
        },
        "baselineKindsPreserved": {
            "passes": not require_baseline_kinds or not missing_kinds,
            "missingKinds": missing_kinds,
            "baselineKinds": baseline_kinds,
            "variantKinds": variant_kinds,
        },
        "variantColdSelector": {
            "passes": not require_variant_cold_selector or variant_is_cold,
            "required": bool(require_variant_cold_selector),
            "cacheHits": variant_cache_hits,
            "cacheMisses": variant_cache_misses,
        },
        "cleanSelector": {
            "passes": not require_clean_selector or variant_clean_selector,
            "required": bool(require_clean_selector),
            "selectorLocalRecoveryCount": variant_local_recovery,
            "overTimeoutCount": variant_over_timeout,
        },
        "selectorShapePreserved": {
            "passes": selector_shape_passes,
            "required": bool(require_same_selector_shape),
            "baseline": baseline_shape,
            "variant": variant_shape,
            "missingFields": missing_shape_fields,
            "changedFields": changed_shape_fields,
        },
        "promptSize": {
            "passes": prompt_size_passes,
            "required": bool(require_prompt_reduction),
            "measured": prompt_measured,
            "reducedOrEqual": prompt_reduced,
            "baselineMaxPromptBytes": baseline_prompt["maxPromptBytes"],
            "variantMaxPromptBytes": variant_prompt["maxPromptBytes"],
            "baselineMaxPrimaryPromptBytes": baseline_prompt["maxPrimaryPromptBytes"],
            "variantMaxPrimaryPromptBytes": variant_prompt["maxPrimaryPromptBytes"],
            "baselineMaxRecoveryPromptBytes": baseline_prompt["maxRecoveryPromptBytes"],
            "variantMaxRecoveryPromptBytes": variant_prompt["maxRecoveryPromptBytes"],
        },
    }
    return {
        "passes": all(bool(check.get("passes")) for check in checks.values()),
        "baseline": str(baseline_path),
        "variant": str(variant_path),
        "metrics": {
            "elapsedDeltaSec": round(variant_elapsed - baseline_elapsed, 3),
            "overlapCount": len(overlap),
            "baselineKindCount": len(baseline_kinds),
            "variantKindCount": len(variant_kinds),
            "maxPromptBytesDelta": variant_prompt["maxPromptBytes"] - baseline_prompt["maxPromptBytes"],
            "maxPrimaryPromptBytesDelta": variant_prompt["maxPrimaryPromptBytes"] - baseline_prompt["maxPrimaryPromptBytes"],
            "maxRecoveryPromptBytesDelta": variant_prompt["maxRecoveryPromptBytes"] - baseline_prompt["maxRecoveryPromptBytes"],
        },
        "checks": checks,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--variant", required=True, type=Path)
    parser.add_argument("--min-overlap", type=int, default=40)
    parser.add_argument("--require-baseline-kinds", action="store_true")
    parser.add_argument("--require-variant-cold-selector", action="store_true")
    parser.add_argument("--require-same-selector-shape", action="store_true")
    parser.add_argument("--require-clean-selector", action="store_true")
    parser.add_argument("--require-prompt-reduction", action="store_true")
    parser.add_argument("--speed-floor", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    report = build_report(
        baseline_path=args.baseline,
        variant_path=args.variant,
        speed_floor_path=args.speed_floor,
        min_overlap=args.min_overlap,
        require_baseline_kinds=args.require_baseline_kinds,
        require_variant_cold_selector=args.require_variant_cold_selector,
        require_same_selector_shape=args.require_same_selector_shape,
        require_clean_selector=args.require_clean_selector,
        require_prompt_reduction=args.require_prompt_reduction,
    )
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report["passes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
