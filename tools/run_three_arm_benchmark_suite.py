#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared_platform.products import PRODUCT_PROFILES
from shared_platform.beta6 import default_llm_client_from_env
from tools.benchmark_provider import create_benchmark_llm_client
from tools import judge_legal_end_to_end as legal_judge
from tools import run_direct_benchmark as direct_runner
from tools import run_frozen_beta6_benchmark as beta6_runner
from tools import run_universal_benchmark as universal_runner
from tools import score_unified_benchmarks as scorer
from tools.run_unified_legal_benchmark import _profiles_with_legal_defaults


ARMS = ("direct", "beta6", "universal")


def run_suite(
    *,
    registry_path: Path,
    output_dir: Path,
    products: dict[str, Any],
    model: str,
    baseline_ref: str = beta6_runner.DEFAULT_BETA6_BASELINE_REF,
    candidate_limit: int = 40,
    evidence_limit: int = 12,
    analysis_mode: str = "fast",
    run_diagnostics: bool = False,
    resume: bool = False,
    max_cases: int = 0,
    case_ids: list[str] | None = None,
    judge_client: Any | None = None,
    judge_model: str = "",
    judge_repetitions: int = 2,
    benchmark_ids: list[str] | None = None,
) -> dict[str, Any]:
    started = time.time()
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    output_dir.mkdir(parents=True, exist_ok=True)
    baseline_source_root = output_dir / "_frozen_beta6_source"
    exam_entries = registry.get("canonicalExamAggregate", {}).get("entries", [])
    legal_entries = registry.get("legalEndToEnd", {}).get("entries", [])
    active_judge_client = judge_client
    if legal_entries and active_judge_client is None:
        active_judge_client = create_benchmark_llm_client(
            model=str(judge_model or model),
            fallback_factory=default_llm_client_from_env,
        )
    active_judge_model = str(judge_model or model)
    diagnostic_entries = registry.get("diagnosticSlices", []) if run_diagnostics else []
    benchmark_reports: list[dict[str, Any]] = []
    selected_benchmark_ids = {str(item) for item in benchmark_ids or [] if str(item)}
    for group, entries in (
        ("canonical_exam", exam_entries),
        ("legal_end_to_end", legal_entries),
        ("diagnostic_slice", diagnostic_entries),
    ):
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if selected_benchmark_ids and _entry_benchmark_id(registry_path.parent, entry) not in selected_benchmark_ids:
                continue
            benchmark_reports.append(
                _run_entry(
                    registry_path.parent,
                    entry,
                    group=group,
                    output_dir=output_dir,
                    products=products,
                    model=model,
                    baseline_ref=baseline_ref,
                    baseline_source_root=baseline_source_root,
                    candidate_limit=candidate_limit,
                    evidence_limit=evidence_limit,
                    analysis_mode=analysis_mode,
                    resume=resume,
                    max_cases=max_cases,
                    case_ids=case_ids,
                    judge_client=active_judge_client,
                    judge_model=active_judge_model,
                    judge_repetitions=judge_repetitions,
                )
            )
    model_parity = _model_parity(benchmark_reports, expected_model=model)
    exam_aggregate = _exam_aggregate(
        [entry for entry in benchmark_reports if entry.get("group") == "canonical_exam"],
        expected_total=int(registry.get("canonicalExamAggregate", {}).get("expectedUniqueCases") or 0),
        p_value_maximum=float(
            registry.get("promotionGate", {}).get("exam", {}).get("pairedMcNemarPValueMaximum") or 0.05
        ),
        model_parity=model_parity,
        subset=bool(max_cases > 0 or case_ids),
    )
    legal_aggregate = _legal_aggregate(
        [entry for entry in benchmark_reports if entry.get("group") == "legal_end_to_end"],
        expected_tasks=int(registry.get("legalEndToEnd", {}).get("expectedTasks") or 0),
        expected_variants=int(registry.get("legalEndToEnd", {}).get("expectedVariants") or 0),
        model_parity=model_parity,
        subset=bool(max_cases > 0 or case_ids),
    )
    goal_achieved = bool(exam_aggregate["promotion"]["passed"] and legal_aggregate["promotion"]["passed"])
    report = {
        "schemaVersion": 1,
        "registryId": str(registry.get("registryId") or ""),
        "status": "completed",
        "goalAchieved": goal_achieved,
        "model": str(model),
        "baselineRef": str(baseline_ref),
        "parameters": {
            "candidateLimit": int(candidate_limit),
            "evidenceLimit": int(evidence_limit),
            "analysisMode": str(analysis_mode),
            "runDiagnostics": bool(run_diagnostics),
            "resume": bool(resume),
            "maxCases": int(max_cases),
            "caseIds": [str(item) for item in case_ids or [] if str(item)],
            "judgeModel": active_judge_model,
            "judgeRepetitions": int(judge_repetitions),
            "benchmarkIds": sorted(selected_benchmark_ids),
        },
        "modelParity": model_parity,
        "examAggregate": exam_aggregate,
        "legalAggregate": legal_aggregate,
        "benchmarks": benchmark_reports,
        "elapsedSec": round(max(0.0, time.time() - started), 3),
    }
    (output_dir / "three_arm_suite_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def _run_entry(
    benchmark_root: Path,
    entry: dict[str, Any],
    *,
    group: str,
    output_dir: Path,
    products: dict[str, Any],
    model: str,
    baseline_ref: str,
    baseline_source_root: Path,
    candidate_limit: int,
    evidence_limit: int,
    analysis_mode: str,
    resume: bool,
    max_cases: int,
    case_ids: list[str] | None,
    judge_client: Any | None,
    judge_model: str,
    judge_repetitions: int,
) -> dict[str, Any]:
    public_path = benchmark_root / str(entry["publicManifest"])
    private_path = benchmark_root / str(entry["privateManifest"])
    public = json.loads(public_path.read_text(encoding="utf-8"))
    private = json.loads(private_path.read_text(encoding="utf-8"))
    benchmark_id = str(public.get("benchmarkId") or public_path.stem)
    benchmark_dir = output_dir / _safe_name(benchmark_id)
    modes: dict[str, Any] = {}
    arm_calls = {
        "direct": lambda: direct_runner.run_manifest(
            public_path=public_path,
            output_dir=benchmark_dir / "direct",
            model=model,
            resume=resume,
            max_cases=max_cases,
            case_ids=case_ids,
        ),
        "beta6": lambda: beta6_runner.run_manifest(
            public_path=public_path,
            output_dir=benchmark_dir / "beta6",
            products=products,
            model=model,
            baseline_ref=baseline_ref,
            baseline_source_root=baseline_source_root,
            limit=candidate_limit,
            analysis_mode=analysis_mode,
            resume=resume,
            max_cases=max_cases,
            case_ids=case_ids,
        ),
        "universal": lambda: universal_runner.run_manifest(
            public_path=public_path,
            output_dir=benchmark_dir / "universal",
            products=products,
            model=model,
            candidate_limit=candidate_limit,
            evidence_limit=evidence_limit,
            resume=resume,
            max_cases=max_cases,
            case_ids=case_ids,
        ),
    }
    for arm in ARMS:
        arm_dir = benchmark_dir / arm
        try:
            summary = arm_calls[arm]()
            artifacts = scorer.load_json_artifacts(arm_dir / "results")
            selected_ids = _selected_score_case_ids(artifacts, max_cases=max_cases, case_ids=case_ids)
            score = scorer.score_predictions(private, artifacts, case_ids=selected_ids or None)
            semantic_judge: dict[str, Any] = {}
            if str(public.get("taskType") or "") == "legal_retrieval_answer":
                if judge_client is None:
                    raise RuntimeError("legal semantic judge client is not configured")
                semantic_judge = legal_judge.judge_legal_artifacts(
                    private,
                    artifacts,
                    llm_client=judge_client,
                    model=judge_model,
                    repetitions=judge_repetitions,
                )
                (arm_dir / "semantic_judge.json").write_text(
                    json.dumps(semantic_judge, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
            modes[arm] = {
                "status": "completed",
                "outputDir": str(arm_dir),
                "summary": summary,
                "score": score,
                "caseOutcomes": _score_case_map(score),
                "semanticJudge": semantic_judge,
            }
        except Exception as exc:  # noqa: BLE001 - the durable suite continues and records arm failure.
            modes[arm] = {
                "status": "failed",
                "outputDir": str(arm_dir),
                "error": str(exc),
                "summary": {},
                "score": {},
                "caseOutcomes": {},
            }
    return {
        "benchmarkId": benchmark_id,
        "taskType": str(public.get("taskType") or ""),
        "product": str(public.get("product") or ""),
        "group": group,
        "expectedCases": int(entry.get("expectedCases") or len(public.get("cases") or [])),
        "publicPath": str(public_path),
        "privatePath": str(private_path),
        "modes": modes,
    }


def _selected_score_case_ids(
    artifacts: list[dict[str, Any]],
    *,
    max_cases: int,
    case_ids: list[str] | None,
) -> list[str]:
    if not max_cases and not case_ids:
        return []
    values: list[str] = []
    for item in artifacts:
        case_id = str(item.get("caseId") or item.get("id") or "").strip()
        if case_id and case_id not in values:
            values.append(case_id)
    return values


def _score_case_map(score: dict[str, Any]) -> dict[str, bool]:
    outcomes: dict[str, bool] = {}
    for item in score.get("cases") or []:
        if not isinstance(item, dict):
            continue
        case_id = str(item.get("caseId") or "").strip()
        if not case_id:
            continue
        outcomes[case_id] = bool(item.get("answerPassed") if "answerPassed" in item else item.get("passed"))
    return outcomes


def _model_parity(entries: list[dict[str, Any]], *, expected_model: str) -> dict[str, Any]:
    blockers: list[str] = []
    comparisons: list[dict[str, Any]] = []
    for entry in entries:
        values: dict[str, dict[str, Any]] = {}
        for arm in ARMS:
            mode = entry.get("modes", {}).get(arm, {})
            summary = mode.get("summary") if isinstance(mode.get("summary"), dict) else {}
            metadata = summary.get("modelMetadata") if isinstance(summary.get("modelMetadata"), dict) else {}
            values[arm] = _stable_model_metadata(metadata)
        stable = {arm: json.dumps(value, ensure_ascii=False, sort_keys=True) for arm, value in values.items()}
        passed = all(values[arm].get("provider") and values[arm].get("model") for arm in ARMS) and len(set(stable.values())) == 1
        if expected_model and any(values[arm].get("model") != expected_model for arm in ARMS):
            passed = False
            blockers.append(f"model_override_mismatch:{entry.get('benchmarkId')}")
        if not passed:
            blockers.append(f"arm_model_metadata_mismatch:{entry.get('benchmarkId')}")
        comparisons.append({"benchmarkId": entry.get("benchmarkId", ""), "passed": passed, "arms": values})
    return {"passed": bool(entries) and not blockers, "blockers": _unique(blockers), "benchmarks": comparisons}


def _stable_model_metadata(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "provider": str(value.get("provider") or ""),
        "model": str(value.get("model") or ""),
        "decoding": value.get("decoding") if isinstance(value.get("decoding"), dict) else {},
    }


def _exam_aggregate(
    entries: list[dict[str, Any]],
    *,
    expected_total: int,
    p_value_maximum: float,
    model_parity: dict[str, Any],
    subset: bool,
) -> dict[str, Any]:
    arms: dict[str, Any] = {}
    outcome_maps: dict[str, dict[str, bool]] = {arm: {} for arm in ARMS}
    for arm in ARMS:
        total = 0
        correct = 0
        predicted = 0
        errors = 0
        for entry in entries:
            mode = entry.get("modes", {}).get(arm, {})
            score = mode.get("score") if isinstance(mode.get("score"), dict) else {}
            summary = mode.get("summary") if isinstance(mode.get("summary"), dict) else {}
            total += int(score.get("total") or 0)
            correct += int(score.get("correct") or 0)
            predicted += int(score.get("predicted") or 0)
            runner_total = summary.get("total") if isinstance(summary.get("total"), dict) else {}
            errors += int(runner_total.get("errors") or 0)
            for case_id, passed in mode.get("caseOutcomes", {}).items():
                outcome_maps[arm][f"{entry.get('benchmarkId')}::{case_id}"] = bool(passed)
        arms[arm] = {
            "total": total,
            "predicted": predicted,
            "correct": correct,
            "accuracy": (correct / total) if total else 0.0,
            "errors": errors,
        }
    direct_comparison = paired_comparison(outcome_maps["direct"], outcome_maps["universal"])
    beta6_comparison = paired_comparison(outcome_maps["beta6"], outcome_maps["universal"])
    complete = (
        not subset
        and expected_total > 0
        and all(arms[arm]["total"] == expected_total for arm in ARMS)
        and all(arms[arm]["predicted"] == expected_total for arm in ARMS)
        and all(arms[arm]["errors"] == 0 for arm in ARMS)
    )
    strictly_better = (
        arms["universal"]["accuracy"] > arms["direct"]["accuracy"]
        and arms["universal"]["accuracy"] > arms["beta6"]["accuracy"]
    )
    significant = (
        direct_comparison["pValueTwoSidedExact"] <= p_value_maximum
        and beta6_comparison["pValueTwoSidedExact"] <= p_value_maximum
        and direct_comparison["universalOnlyCorrect"] > direct_comparison["baselineOnlyCorrect"]
        and beta6_comparison["universalOnlyCorrect"] > beta6_comparison["baselineOnlyCorrect"]
    )
    passed = bool(complete and model_parity.get("passed") and strictly_better and significant)
    blockers: list[str] = []
    if not complete:
        blockers.append("canonical_exam_incomplete_or_subset")
    if not model_parity.get("passed"):
        blockers.append("model_parity_failed")
    if not strictly_better:
        blockers.append("universal_not_strictly_better_than_both_exam_baselines")
    if not significant:
        blockers.append("paired_significance_against_both_baselines_failed")
    return {
        "expectedTotal": expected_total,
        "arms": arms,
        "comparisons": {
            "universalVsDirect": direct_comparison,
            "universalVsBeta6": beta6_comparison,
        },
        "promotion": {
            "passed": passed,
            "complete": complete,
            "strictlyBetterThanBoth": strictly_better,
            "statisticallySignificantAgainstBoth": significant,
            "pValueMaximum": p_value_maximum,
            "blockers": blockers,
        },
    }


def _legal_aggregate(
    entries: list[dict[str, Any]],
    *,
    expected_tasks: int,
    expected_variants: int,
    model_parity: dict[str, Any],
    subset: bool,
) -> dict[str, Any]:
    arms: dict[str, Any] = {}
    for arm in ARMS:
        total = sum(
            int(entry.get("modes", {}).get(arm, {}).get("semanticJudge", {}).get("total") or 0)
            for entry in entries
        )
        passed_count = sum(
            int(entry.get("modes", {}).get(arm, {}).get("semanticJudge", {}).get("passed") or 0)
            for entry in entries
        )
        grounding_passed = sum(
            int(entry.get("modes", {}).get(arm, {}).get("semanticJudge", {}).get("groundingPassed") or 0)
            for entry in entries
        )
        errors = sum(
            int(entry.get("modes", {}).get(arm, {}).get("summary", {}).get("total", {}).get("errors") or 0)
            for entry in entries
        )
        arms[arm] = {
            "totalVariants": total,
            "passedVariants": passed_count,
            "groundedVariants": grounding_passed,
            "accuracy": (passed_count / total) if total else 0.0,
            "errors": errors,
        }
    complete = (
        not subset
        and expected_tasks > 0
        and expected_variants > 0
        and len(entries) == expected_tasks
        and all(
            arms[arm]["totalVariants"] == expected_variants
            and arms[arm]["errors"] == 0
            for arm in ARMS
        )
    )
    universal_all = arms["universal"]["totalVariants"] > 0 and (
        arms["universal"]["passedVariants"] == arms["universal"]["totalVariants"]
    )
    universal_grounded_all = arms["universal"]["totalVariants"] > 0 and (
        arms["universal"]["groundedVariants"] == arms["universal"]["totalVariants"]
    )
    strict = (
        arms["universal"]["accuracy"] > arms["direct"]["accuracy"]
        and arms["universal"]["accuracy"] > arms["beta6"]["accuracy"]
    )
    passed = bool(
        complete and model_parity.get("passed") and universal_all and universal_grounded_all and strict
    )
    blockers: list[str] = []
    if not complete:
        blockers.append("legal_suite_incomplete_or_subset")
    if not model_parity.get("passed"):
        blockers.append("model_parity_failed")
    if not universal_all:
        blockers.append("universal_did_not_pass_all_legal_variants")
    if not universal_grounded_all:
        blockers.append("universal_legal_answers_not_all_grounded")
    if not strict:
        blockers.append("universal_not_strictly_better_than_both_legal_baselines")
    return {
        "expectedTasks": expected_tasks,
        "expectedVariants": expected_variants,
        "arms": arms,
        "promotion": {
            "passed": passed,
            "complete": complete,
            "universalPassedAllVariants": universal_all,
            "universalGroundedAllVariants": universal_grounded_all,
            "strictlyBetterThanBoth": strict,
            "blockers": blockers,
        },
    }


def paired_comparison(baseline: dict[str, bool], universal: dict[str, bool]) -> dict[str, Any]:
    common = sorted(set(baseline) & set(universal))
    baseline_only = sum(1 for key in common if baseline[key] and not universal[key])
    universal_only = sum(1 for key in common if universal[key] and not baseline[key])
    both_correct = sum(1 for key in common if baseline[key] and universal[key])
    both_wrong = sum(1 for key in common if not baseline[key] and not universal[key])
    discordant = baseline_only + universal_only
    if discordant <= 0:
        p_value = 1.0
    else:
        tail = sum(math.comb(discordant, k) for k in range(0, min(baseline_only, universal_only) + 1))
        p_value = min(1.0, 2.0 * tail / (2**discordant))
    return {
        "pairedCases": len(common),
        "bothCorrect": both_correct,
        "bothWrong": both_wrong,
        "baselineOnlyCorrect": baseline_only,
        "universalOnlyCorrect": universal_only,
        "discordantPairs": discordant,
        "pValueTwoSidedExact": p_value,
    }


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "")).strip("-.")
    return cleaned or "benchmark"


def _entry_benchmark_id(benchmark_root: Path, entry: dict[str, Any]) -> str:
    public_path = benchmark_root / str(entry.get("publicManifest") or "")
    try:
        manifest = json.loads(public_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    return str(manifest.get("benchmarkId") or "")


def _unique(values: list[str]) -> list[str]:
    out: list[str] = []
    for value in values:
        if value and value not in out:
            out.append(value)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Direct, frozen beta6, and Universal with one model.")
    parser.add_argument("--registry", type=Path, default=REPO_ROOT / "benchmarks" / "evaluation_registry.json")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--baseline-ref", default=beta6_runner.DEFAULT_BETA6_BASELINE_REF)
    parser.add_argument("--db", action="append", default=[], help="Database override in key=/absolute/path form.")
    parser.add_argument("--candidate-limit", type=int, default=40)
    parser.add_argument("--evidence-limit", type=int, default=12)
    parser.add_argument("--analysis-mode", default="fast")
    parser.add_argument("--diagnostics", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--max-cases", type=int, default=0)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--judge-model", default="")
    parser.add_argument("--judge-repetitions", type=int, default=2)
    parser.add_argument("--benchmark-id", action="append", default=[])
    args = parser.parse_args()
    profiles = _profiles_with_legal_defaults(dict(PRODUCT_PROFILES))
    for value in args.db:
        key, separator, raw_path = str(value).partition("=")
        if not separator or key not in profiles or not raw_path:
            raise SystemExit(f"invalid --db value: {value}")
        profiles[key] = replace(profiles[key], db_path=Path(raw_path))
    report = run_suite(
        registry_path=args.registry,
        output_dir=args.output_dir,
        products=profiles,
        model=args.model,
        baseline_ref=args.baseline_ref,
        candidate_limit=args.candidate_limit,
        evidence_limit=args.evidence_limit,
        analysis_mode=args.analysis_mode,
        run_diagnostics=args.diagnostics,
        resume=args.resume,
        max_cases=args.max_cases,
        case_ids=args.case_id,
        judge_model=args.judge_model,
        judge_repetitions=args.judge_repetitions,
        benchmark_ids=args.benchmark_id,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("goalAchieved") else 2


if __name__ == "__main__":
    raise SystemExit(main())
