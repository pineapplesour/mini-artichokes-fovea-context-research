#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared_platform.products import PRODUCT_PROFILES, ProductProfile
from tools import audit_selector_ablation
from tools import audit_benchmark_artifacts
from tools import run_unified_legal_benchmark as legal_runner
from tools import run_unified_mcq_benchmark as mcq_runner
from tools import score_unified_benchmarks
from tools.check_unified_benchmark_coverage import check_unified_benchmark_coverage


CORPUS_ANSWER_TASK_TYPES = {"mcq", "short_answer"}
SUPPORTED_TASK_TYPES = CORPUS_ANSWER_TASK_TYPES | {"legal_retrieval_answer"}


def run_suite(
    *,
    benchmarks_dir: Path,
    output_dir: Path,
    benchmark_ids: list[str] | None = None,
    products: dict[str, ProductProfile] | None = None,
    execute: bool = False,
    run_engine: bool = True,
    run_direct: bool = False,
    allow_unready: bool = False,
    min_rows: int = 1000,
    limit: int = 50,
    analysis_mode: str = "fast",
    direct_model: str = "",
    max_cases: int = 0,
    case_ids: list[str] | None = None,
    require_selector_ablation: bool = False,
    resume: bool = False,
) -> dict[str, Any]:
    started = time.time()
    output_dir.mkdir(parents=True, exist_ok=True)
    active_products = _suite_products(products)
    selected_ids = {str(item) for item in benchmark_ids or [] if str(item)}
    entries: list[dict[str, Any]] = []
    for spec in _discover_specs(benchmarks_dir):
        public_manifest = _load_json(spec["publicPath"])
        benchmark_id = str(public_manifest.get("benchmarkId") or "")
        if selected_ids and benchmark_id not in selected_ids:
            continue
        entries.append(
            _run_spec(
                spec,
                public_manifest=public_manifest,
                output_dir=output_dir,
                products=active_products,
                execute=execute,
                run_engine=run_engine,
                run_direct=run_direct,
                allow_unready=allow_unready,
                min_rows=min_rows,
                limit=limit,
                analysis_mode=analysis_mode,
                direct_model=direct_model,
                max_cases=max_cases,
                case_ids=case_ids,
                resume=resume,
            )
        )
    selector_ablation = _selector_ablation_audit(output_dir, required=require_selector_ablation)
    claim_blockers = _suite_claim_blockers(entries, selector_ablation, require_selector_ablation=require_selector_ablation)
    report = {
        "status": "completed",
        "execute": bool(execute),
        "claimable": _suite_modes_claimable(entries) and not claim_blockers,
        "claimBlockers": claim_blockers,
        "parameters": {
            "benchmarkIds": sorted(selected_ids),
            "runEngine": bool(run_engine),
            "runDirect": bool(run_direct),
            "allowUnready": bool(allow_unready),
            "minRows": int(min_rows),
            "limit": int(limit),
            "analysisMode": str(analysis_mode or ""),
            "directModel": str(direct_model or ""),
            "maxCases": int(max_cases),
            "caseIds": [str(case_id) for case_id in case_ids or [] if str(case_id)],
            "requireSelectorAblation": bool(require_selector_ablation),
        },
        "benchmarksDir": str(benchmarks_dir),
        "outputDir": str(output_dir),
        "benchmarkCount": len(entries),
        "summary": _suite_summary(entries),
        "benchmarks": entries,
        "elapsedSec": round(max(0.0, time.time() - started), 3),
    }
    if selector_ablation:
        report["selectorAblation"] = selector_ablation
    (output_dir / "suite_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def _run_spec(
    spec: dict[str, Path],
    *,
    public_manifest: dict[str, Any],
    output_dir: Path,
    products: dict[str, ProductProfile],
    execute: bool,
    run_engine: bool,
    run_direct: bool,
    allow_unready: bool,
    min_rows: int,
    limit: int,
    analysis_mode: str,
    direct_model: str,
    max_cases: int,
    case_ids: list[str] | None,
    resume: bool,
) -> dict[str, Any]:
    benchmark_id = str(public_manifest.get("benchmarkId") or "")
    task_type = str(public_manifest.get("taskType") or "")
    product_key = str(public_manifest.get("product") or "")
    benchmark_dir = output_dir / _safe_path_name(benchmark_id)
    private_path = spec["privatePath"]
    db_path = _product_db_path(product_key, products)
    readiness_manifest = private_path if task_type == "legal_retrieval_answer" and private_path.exists() else spec["publicPath"]
    readiness = check_unified_benchmark_coverage(readiness_manifest, db_path, min_rows=min_rows)
    entry = {
        "benchmarkId": benchmark_id,
        "taskType": task_type,
        "product": product_key,
        "publicPath": str(spec["publicPath"]),
        "privatePath": str(private_path) if private_path.exists() else "",
        "dbPath": str(db_path),
        "readiness": readiness,
        "modes": {},
    }
    if run_direct and task_type in SUPPORTED_TASK_TYPES:
        entry["modes"]["direct"] = _run_mode(
            mode="direct",
            task_type=task_type,
            public_path=spec["publicPath"],
            private_path=private_path,
            output_dir=benchmark_dir / "direct",
            products=products,
            execute=execute,
            ready=True,
            allow_unready=True,
            limit=limit,
            analysis_mode=analysis_mode,
            direct_model=direct_model,
            max_cases=max_cases,
            case_ids=case_ids,
            resume=resume,
        )
    elif run_direct:
        entry["modes"]["direct"] = _with_claim_gate({"status": "unsupported", "reason": f"direct_mode_unsupported:{task_type}"})
    if run_engine:
        ready = (
            bool(readiness.get("readyForRetrievalBenchmark"))
            if task_type in CORPUS_ANSWER_TASK_TYPES
            else _legal_ready(readiness)
        )
        entry["modes"]["engine"] = _run_mode(
            mode="engine",
            task_type=task_type,
            public_path=spec["publicPath"],
            private_path=private_path,
            output_dir=benchmark_dir / "engine",
            products=products,
            execute=execute,
            ready=ready,
            allow_unready=allow_unready,
            limit=limit,
            analysis_mode=analysis_mode,
            direct_model=direct_model,
            max_cases=max_cases,
            case_ids=case_ids,
            resume=resume,
        )
    _apply_cross_mode_claim_gates(entry)
    return entry


def _run_mode(
    *,
    mode: str,
    task_type: str,
    public_path: Path,
    private_path: Path,
    output_dir: Path,
    products: dict[str, ProductProfile],
    execute: bool,
    ready: bool,
    allow_unready: bool,
    limit: int,
    analysis_mode: str,
    direct_model: str,
    max_cases: int,
    case_ids: list[str] | None,
    resume: bool,
) -> dict[str, Any]:
    if not execute:
        return _with_claim_gate({"status": "dry_run", "reason": "execute_false", "outputDir": str(output_dir)})
    if mode == "engine" and not ready and not allow_unready:
        return _with_claim_gate(
            {"status": "skipped_unready", "reason": "readiness_failed", "outputDir": str(output_dir)}
        )
    started = time.time()
    try:
        if task_type in CORPUS_ANSWER_TASK_TYPES and mode == "direct":
            summary = mcq_runner.run_direct_manifest(
                public_path=public_path,
                output_dir=output_dir,
                products=products,
                resume=resume,
                model=direct_model,
                max_cases=max_cases,
                case_ids=case_ids,
            )
        elif task_type in CORPUS_ANSWER_TASK_TYPES and mode == "engine":
            summary = mcq_runner.run_engine_manifest(
                public_path=public_path,
                output_dir=output_dir,
                products=products,
                resume=resume,
                limit=limit,
                analysis_mode=analysis_mode,
                max_cases=max_cases,
                case_ids=case_ids,
            )
        elif task_type == "legal_retrieval_answer" and mode == "engine":
            summary = legal_runner.run_legal_manifest(
                public_path=public_path,
                output_dir=output_dir,
                products=products,
                resume=resume,
                limit=limit,
                analysis_mode=analysis_mode,
                max_cases=max_cases,
                case_ids=case_ids,
            )
        elif task_type == "legal_retrieval_answer" and mode == "direct":
            summary = legal_runner.run_direct_manifest(
                public_path=public_path,
                output_dir=output_dir,
                products=products,
                resume=resume,
                model=direct_model,
                max_cases=max_cases,
                case_ids=case_ids,
            )
        else:
            return _with_claim_gate({"status": "unsupported", "reason": f"{task_type}:{mode}", "outputDir": str(output_dir)})
    except Exception as exc:  # noqa: BLE001 - suite reports failures as data.
        return _with_claim_gate(
            {
                "status": "failed",
                "reason": str(exc),
                "outputDir": str(output_dir),
                "elapsedSec": round(max(0.0, time.time() - started), 3),
            }
        )
    result = {
        "status": "completed",
        "outputDir": str(output_dir),
        "summary": summary,
        "elapsedSec": round(max(0.0, time.time() - started), 3),
        "subsetFilter": {
            "caseIds": [str(case_id) for case_id in case_ids or [] if str(case_id)],
            "maxCases": int(max_cases),
        },
    }
    model_metadata = _mode_model_metadata({"summary": summary})
    if model_metadata:
        result["modelMetadata"] = model_metadata
    score = _score_if_possible(private_path, output_dir / "results", mode=mode, case_ids=case_ids, max_cases=max_cases)
    if score:
        result["score"] = score
    if mode == "engine" and (output_dir / "results").exists():
        result["audit"] = audit_benchmark_artifacts.audit_results_dir(output_dir / "results")
    return _with_claim_gate(result)


def _with_claim_gate(result: dict[str, Any]) -> dict[str, Any]:
    blockers = _claim_blockers(result)
    result["claimable"] = not blockers
    result["claimBlockers"] = blockers
    return result


def _apply_cross_mode_claim_gates(entry: dict[str, Any]) -> None:
    if str(entry.get("taskType") or "") not in SUPPORTED_TASK_TYPES:
        return
    modes = entry.get("modes") if isinstance(entry.get("modes"), dict) else {}
    engine = modes.get("engine") if isinstance(modes.get("engine"), dict) else None
    if engine is None:
        return
    direct = modes.get("direct") if isinstance(modes.get("direct"), dict) else None
    for blocker in _direct_baseline_blockers(direct, engine):
        _append_claim_blocker(engine, blocker)


def _direct_baseline_blockers(direct: dict[str, Any] | None, engine: dict[str, Any]) -> list[str]:
    if not direct:
        return ["missing_same_model_direct_baseline"]
    if str(direct.get("status") or "") != "completed":
        return ["direct_baseline_not_completed"]
    if not isinstance(direct.get("score"), dict) or not direct.get("score"):
        return ["direct_baseline_score_missing"]
    if not bool(direct.get("claimable")):
        return ["direct_baseline_not_claimable"]
    engine_metadata = _mode_model_metadata(engine)
    direct_metadata = _mode_model_metadata(direct)
    if not _has_comparable_model_metadata(engine_metadata):
        return ["engine_model_metadata_missing"]
    if not _has_comparable_model_metadata(direct_metadata):
        return ["direct_baseline_model_metadata_missing"]
    if str(engine_metadata.get("provider") or "") != str(direct_metadata.get("provider") or ""):
        return ["direct_baseline_provider_mismatch"]
    if str(engine_metadata.get("model") or "") != str(direct_metadata.get("model") or ""):
        return ["direct_baseline_model_mismatch"]
    if _stable_decoding_metadata(engine_metadata.get("decoding")) != _stable_decoding_metadata(direct_metadata.get("decoding")):
        return ["direct_baseline_decoding_mismatch"]
    return []


def _mode_model_metadata(mode_result: dict[str, Any]) -> dict[str, Any]:
    direct = mode_result.get("modelMetadata") if isinstance(mode_result.get("modelMetadata"), dict) else None
    if direct is None:
        summary = mode_result.get("summary") if isinstance(mode_result.get("summary"), dict) else {}
        direct = summary.get("modelMetadata") if isinstance(summary.get("modelMetadata"), dict) else None
    if not isinstance(direct, dict):
        return {}
    decoding = direct.get("decoding")
    return {
        "provider": str(direct.get("provider") or ""),
        "model": str(direct.get("model") or ""),
        "decoding": decoding if isinstance(decoding, dict) else {},
    }


def _has_comparable_model_metadata(value: dict[str, Any]) -> bool:
    return bool(str(value.get("provider") or "") and str(value.get("model") or ""))


def _stable_decoding_metadata(value: Any) -> str:
    decoding = value if isinstance(value, dict) else {}
    return json.dumps(decoding, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _append_claim_blocker(result: dict[str, Any], blocker: str) -> None:
    blockers = result.get("claimBlockers") if isinstance(result.get("claimBlockers"), list) else []
    if blocker not in blockers:
        blockers.append(blocker)
    result["claimBlockers"] = blockers
    result["claimable"] = not blockers


def _claim_blockers(result: dict[str, Any]) -> list[str]:
    status = str(result.get("status") or "")
    if status != "completed":
        reason = str(result.get("reason") or status or "not_completed")
        return [reason]
    blockers: list[str] = []
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    total = summary.get("total") if isinstance(summary.get("total"), dict) else {}
    subset_filter = result.get("subsetFilter") if isinstance(result.get("subsetFilter"), dict) else {}
    if subset_filter.get("caseIds"):
        blockers.append("subset_case_filter")
    if int(subset_filter.get("maxCases") or 0) > 0:
        blockers.append("subset_max_cases")
    if int(total.get("total") or 0) <= 0:
        blockers.append("runner_zero_cases")
    if int(total.get("errors") or 0) > 0:
        blockers.append("runner_errors")
    score = result.get("score") if isinstance(result.get("score"), dict) else {}
    scored_total = int(score.get("total") or 0)
    if not score:
        blockers.append("score_missing")
    elif scored_total <= 0:
        blockers.append("score_zero_cases")
    elif "predicted" in score and int(score.get("predicted") or 0) <= 0:
        blockers.append("score_zero_predictions")
    retrieval_score = score.get("retrieval") if isinstance(score.get("retrieval"), dict) else {}
    summary_mode = str(summary.get("mode") or "")
    if (
        str(score.get("taskType") or "") == "legal_retrieval_answer"
        and summary_mode != "direct"
        and retrieval_score
        and int(retrieval_score.get("passed") or 0) <= 0
    ):
        blockers.append("legal_retrieval_zero_pass")
    if str(score.get("taskType") or "") == "legal_retrieval_answer" and summary_mode == "direct":
        answer_score = score.get("answer") if isinstance(score.get("answer"), dict) else {}
        if not answer_score or int(answer_score.get("passed") or 0) <= 0:
            blockers.append("legal_direct_answer_zero_pass")
    if str(score.get("taskType") or "") == "mcq" and summary_mode == "engine":
        mcq_retrieval = score.get("retrieval") if isinstance(score.get("retrieval"), dict) else {}
        if not mcq_retrieval or int(mcq_retrieval.get("targeted") or 0) <= 0:
            blockers.append("mcq_retrieval_targets_missing")
        elif int(mcq_retrieval.get("passed") or 0) <= 0:
            blockers.append("mcq_retrieval_zero_pass")
        target_policy = mcq_retrieval.get("targetPolicy") if isinstance(mcq_retrieval.get("targetPolicy"), dict) else {}
        if target_policy and not bool(target_policy.get("claimable")):
            blockers.append("mcq_retrieval_target_policy_not_claimable")
            for blocker in target_policy.get("blockers") or []:
                if isinstance(blocker, str):
                    blockers.append(blocker)
    audit = result.get("audit") if isinstance(result.get("audit"), dict) else {}
    if audit and int(audit.get("totalArtifacts") or 0) <= 0:
        blockers.append("audit_zero_artifacts")
    if audit and int(audit.get("totalArtifacts") or 0) > 0:
        selector_counts = audit.get("selectorStatusCounts") if isinstance(audit.get("selectorStatusCounts"), dict) else {}
        if int(selector_counts.get("completed") or 0) <= 0:
            blockers.append("audit_no_completed_selectors")
        selected_buckets = audit.get("selectedCountBuckets") if isinstance(audit.get("selectedCountBuckets"), dict) else {}
        if int(selected_buckets.get("0") or 0) >= int(audit.get("totalArtifacts") or 0):
            blockers.append("audit_zero_selected_evidence")
        if int(audit.get("sourceGroundedArtifactCount") or 0) <= 0:
            blockers.append("audit_no_source_grounded_artifacts")
        if int(audit.get("retrievalValidArtifactCount") or 0) <= 0:
            blockers.append("audit_no_retrieval_valid_artifacts")
    red_flags = audit.get("redFlags") if isinstance(audit.get("redFlags"), dict) else {}
    for name, details in red_flags.items():
        if isinstance(details, dict) and int(details.get("count") or 0) > 0:
            blockers.append(f"audit_red_flag:{name}")
    return blockers


def _score_if_possible(
    private_path: Path,
    results_dir: Path,
    *,
    mode: str = "",
    case_ids: list[str] | None = None,
    max_cases: int = 0,
) -> dict[str, Any]:
    if not private_path.exists() or not results_dir.exists():
        return {}
    private = _load_json(private_path)
    artifacts = (
        score_unified_benchmarks.load_json_artifacts(results_dir)
        if private.get("graders") or str(mode or "") == "engine"
        else score_unified_benchmarks.load_graphed_regression_predictions(results_dir)
    )
    score_case_ids = case_ids
    if max_cases and max_cases > 0 and not score_case_ids:
        score_case_ids = _artifact_case_ids(artifacts)
    return score_unified_benchmarks.score_predictions(private, artifacts, case_ids=score_case_ids)


def _artifact_case_ids(artifacts: list[dict[str, Any]]) -> list[str]:
    ids: list[str] = []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        case_id = str(artifact.get("caseId") or artifact.get("id") or "").strip()
        if case_id and case_id not in ids:
            ids.append(case_id)
    return ids


def _discover_specs(benchmarks_dir: Path) -> list[dict[str, Path]]:
    specs: list[dict[str, Path]] = []
    for public_path in sorted(benchmarks_dir.glob("*.public.json")):
        private_path = public_path.with_name(public_path.name.replace(".public.json", ".private.json"))
        specs.append({"publicPath": public_path, "privatePath": private_path})
    return specs


def _suite_products(products: dict[str, ProductProfile] | None) -> dict[str, ProductProfile]:
    if products is not None:
        return legal_runner._profiles_with_legal_defaults(products)  # type: ignore[attr-defined]
    return legal_runner._profiles_with_legal_defaults(dict(PRODUCT_PROFILES))  # type: ignore[attr-defined]


def _product_db_path(product_key: str, products: dict[str, ProductProfile]) -> Path:
    profile = products.get(product_key)
    if profile is None:
        return Path("")
    return profile.db_path


def _legal_ready(readiness: dict[str, Any]) -> bool:
    total = int(readiness.get("totalTargets") or 0)
    return bool(readiness.get("dbExists")) and total > 0 and int(readiness.get("presentTargets") or 0) == total


def _suite_summary(entries: list[dict[str, Any]]) -> dict[str, Any]:
    mode_counts: dict[str, int] = {}
    unready = 0
    for entry in entries:
        readiness = entry.get("readiness") if isinstance(entry.get("readiness"), dict) else {}
        task_type = str(entry.get("taskType") or "")
        if task_type in CORPUS_ANSWER_TASK_TYPES:
            if not readiness.get("readyForRetrievalBenchmark"):
                unready += 1
        elif not _legal_ready(readiness):
            unready += 1
        for mode_result in (entry.get("modes") or {}).values():
            if not isinstance(mode_result, dict):
                continue
            status = str(mode_result.get("status") or "")
            mode_counts[status] = mode_counts.get(status, 0) + 1
    return {
        "unreadyBenchmarks": unready,
        "modeStatusCounts": dict(sorted(mode_counts.items())),
    }


def _suite_modes_claimable(entries: list[dict[str, Any]]) -> bool:
    requested_modes = [
        mode_result
        for entry in entries
        for mode_result in (entry.get("modes") or {}).values()
        if isinstance(mode_result, dict)
    ]
    return bool(requested_modes) and all(bool(mode.get("claimable")) for mode in requested_modes)


def _suite_claim_blockers(
    entries: list[dict[str, Any]],
    selector_ablation: dict[str, Any],
    *,
    require_selector_ablation: bool,
) -> list[str]:
    blockers: list[str] = []
    if require_selector_ablation:
        if not selector_ablation:
            blockers.append("selector_ablation_missing")
        elif not bool(selector_ablation.get("ablationReportValid")):
            blockers.append("selector_ablation_invalid")
            for blocker in selector_ablation.get("reportBlockers") or []:
                if isinstance(blocker, str):
                    blockers.append(blocker)
        elif not bool(selector_ablation.get("contextPacketRetrievalImprovementClaimable")):
            blockers.append("selector_ablation_improvement_not_claimable")
            for blocker in selector_ablation.get("improvementClaimBlockers") or []:
                if isinstance(blocker, str):
                    blockers.append(blocker)
    return _unique_strings(blockers)


def _selector_ablation_audit(output_dir: Path, *, required: bool) -> dict[str, Any]:
    report_path = output_dir / "selector_ablation.raw_vs_context_packets_v1.json"
    if not report_path.exists():
        if required:
            return {
                "status": "missing",
                "ablationReportValid": False,
                "reportBlockers": ["selector_ablation_missing"],
                "improvementClaimBlockers": [],
                "claimBlockers": ["selector_ablation_missing"],
            }
        return {}
    return audit_selector_ablation.audit_selector_ablation_path(report_path)


def _unique_strings(values: list[str]) -> list[str]:
    out: list[str] = []
    for value in values:
        if value and value not in out:
            out.append(value)
    return out


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_path_name(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "").strip())
    return safe or "benchmark"


def _product_db_overrides(values: list[str]) -> dict[str, Path]:
    overrides: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"expected PRODUCT=PATH: {value}")
        key, raw_path = value.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"empty product in override: {value}")
        overrides[key] = Path(raw_path).expanduser()
    return overrides


def _apply_db_overrides(products: dict[str, ProductProfile], overrides: dict[str, Path]) -> dict[str, ProductProfile]:
    updated = dict(products)
    for key, db_path in overrides.items():
        if key not in updated:
            continue
        updated[key] = replace(updated[key], db_path=db_path)
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description="Run/readiness-gate unified benchmark suites.")
    parser.add_argument("--benchmarks-dir", type=Path, default=Path("benchmarks/unified"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--benchmark-id", action="append", default=[])
    parser.add_argument("--product-db", action="append", default=[], help="Override product DB path as PRODUCT=PATH")
    parser.add_argument("--execute", action="store_true", help="Actually run selected modes. Without this, only readiness is reported.")
    parser.add_argument("--run-direct", action="store_true", help="Run direct MCQ baselines.")
    parser.add_argument("--no-engine", action="store_true", help="Do not run engine mode.")
    parser.add_argument("--allow-unready", action="store_true", help="Allow engine runs even when readiness checks fail.")
    parser.add_argument("--min-rows", type=int, default=1000)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--analysis-mode", default="fast")
    parser.add_argument("--direct-model", default="", help="Model override for MCQ direct baselines.")
    parser.add_argument("--max-cases", type=int, default=0)
    parser.add_argument("--case-id", action="append", default=[], help="Run only matching public case ids. Repeatable.")
    parser.add_argument("--require-selector-ablation", action="store_true", help="Require selector_ablation.raw_vs_context_packets_v1.json to be present and valid.")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    products = _apply_db_overrides(_suite_products(None), _product_db_overrides(args.product_db))
    report = run_suite(
        benchmarks_dir=args.benchmarks_dir,
        output_dir=args.output_dir,
        benchmark_ids=args.benchmark_id,
        products=products,
        execute=args.execute,
        run_engine=not args.no_engine,
        run_direct=args.run_direct,
        allow_unready=args.allow_unready,
        min_rows=args.min_rows,
        limit=args.limit,
        analysis_mode=args.analysis_mode,
        direct_model=args.direct_model,
        max_cases=args.max_cases,
        case_ids=args.case_id,
        require_selector_ablation=args.require_selector_ablation,
        resume=args.resume,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
