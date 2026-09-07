"""Dry-run-first approved bounded dependency-separator O development for ClassEval-Pro.

The runner validates the official parent
and the frozen E/D/O control, then (only with explicit ``--execute``) calls
the new O arm for the 32 unresolved tasks.  The old control artifacts are
hash-bound references, never prompt inputs.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Callable, Iterable

from tools import classeval_ordinary_prefix as prefix_loader
from tools import dependency_separator_overlap as separator
from tools import run_classeval_overlap_repair_tail as frozen_tail
from tools import run_classeval_source_overlap as base
from tools import run_classeval_text_overlap as text_runner


MODEL, EFFORT, TIMEOUT = frozen_tail.MODEL, frozen_tail.EFFORT, frozen_tail.TIMEOUT
ROOT = base.ROOT
PROTOCOL = ROOT / "experiment_protocols/2026-09-05-classeval-dependency-separator-overlap-development.md"
TOTAL_TASKS = 300
EXPECTED_FAILURES = 32
TAIL_CALLS = 3
PLANNED_NEW_CALLS = EXPECTED_FAILURES * TAIL_CALLS


def _json(path: Path) -> dict:
    return json.loads(path.read_text())


def _ordered_ids(rows: list[dict]) -> list[str]:
    return [row["task_id"] for row in rows]


def _prefix_map(prefixes: dict[str, dict], ids: Iterable[str]) -> dict[str, dict]:
    return {
        task_id: {
            "callPaths": prefixes[task_id]["callPaths"],
            "sourceSha": prefixes[task_id]["sourceSha"],
            "logicalPrefixCalls": prefixes[task_id]["logicalPrefixCalls"],
        }
        for task_id in ids
    }


def _validate_control(control_root: Path, parent_root: Path, rows: list[dict],
                      prefixes: dict[str, dict]) -> tuple[dict, dict]:
    """Validate the frozen completed control without using its task outputs."""

    control_root = Path(control_root).resolve()
    contract = _json(control_root / "contract.json")
    expected = frozen_tail._build_contract(control_root, parent_root, rows, prefixes)
    if contract != expected:
        raise ValueError("frozen control contract/hash inputs do not match")
    result = _json(control_root / "result.json")
    ids = _ordered_ids(rows)
    tasks = result.get("tasks")
    if (result.get("status") != "complete" or result.get("completed") != TOTAL_TASKS
            or result.get("total") != TOTAL_TASKS or not isinstance(tasks, dict)
            or list(tasks) != ids
            or any(not isinstance(state, dict) or set(state) != {"E", "D", "O"}
                   for state in tasks.values())):
        raise ValueError("completed full-300 E/D/O control required")
    return contract, result


def _validate_parent_result(result: dict) -> None:
    """Accept both the legacy terminal schema and an explicit complete status."""

    status = result.get("status")
    if (status not in (None, "complete") or result.get("completed") != TOTAL_TASKS
            or result.get("total") != TOTAL_TASKS):
        raise ValueError("terminal complete ordinary full-300 parent required")


def _routing_summary(rows: list[dict], prefixes: dict[str, dict],
                     unresolved: Iterable[str]) -> dict:
    """Compute static plans for U during dry-run; never invokes evaluation."""

    by_id = {row["task_id"]: row for row in rows}
    sizes: Counter[int] = Counter()
    fallback_reasons: Counter[str] = Counter()
    planned = 0
    nonfallback = 0
    covered = 0
    exclusive = 0
    invariant_errors: list[str] = []
    for task_id in unresolved:
        row, prefix = by_id[task_id], prefixes[task_id]
        labels = frozen_tail.target_method_labels(row, prefix["source"]) or ("whole_program",)
        ordered, _ = frozen_tail.choose_failure_anchor(labels, prefix["report"])
        plan = separator.build_separator_plan(prefix["source"], row["class_name"], ordered)
        sizes[len(plan.shared)] += 1
        if plan.fallback:
            fallback_reasons[plan.reason] += 1
            continue
        nonfallback += 1
        planned += bool(plan.overlap)
        if all(left in plan.shared or right in plan.shared
               for left, right in plan.cross_edges):
            covered += 1
        else:
            invariant_errors.append(f"{task_id}: uncovered cross edge")
        if plan.a_exclusive and plan.b_exclusive:
            exclusive += 1
        else:
            invariant_errors.append(f"{task_id}: empty exclusive side")
    expected = {0: 4, 1: 7, 2: 11, 3: 6, 4: 3, 5: 1}
    return {
        "separatorSizeDistribution": dict(sorted(sizes.items())),
        "expectedPriorDiagnosticDistribution": expected,
        "separatorFallbackTasks": sum(fallback_reasons.values()),
        "fallbackReasons": dict(sorted(fallback_reasons.items())),
        "activePlannedOverlapTasks": planned,
        "nonfallbackTasks": nonfallback,
        "nonfallbackCrossEdgeCoveredTasks": covered,
        "nonfallbackBothExclusiveTasks": exclusive,
        "invariantErrors": invariant_errors,
        "matchesPriorDiagnostic": dict(sorted(sizes.items())) == expected
            and not fallback_reasons,
    }


def _build_contract(run_root: Path, parent_root: Path, control_root: Path,
                    control_contract: dict, rows: list[dict],
                    prefixes: dict[str, dict]) -> dict:
    helper_shas = {
        "prefixLoaderSha": base.sha(Path(prefix_loader.__file__)),
        "separatorSha": base.sha(Path(separator.__file__)),
        "frozenTailSha": base.sha(Path(frozen_tail.__file__)),
        "baseRunnerSha": base.sha(Path(base.__file__)),
        "textRunnerSha": base.sha(Path(text_runner.__file__)),
    }
    parent = Path(parent_root).resolve()
    control = Path(control_root).resolve()
    ordinary_failures = [task_id for task_id in _ordered_ids(rows)
                         if not prefixes[task_id]["report"].get("passed")]
    return {
        "dataset": "classeval-pro", "taskIds": _ordered_ids(rows),
        "dataSha": base.PRO_SHA, "runnerSha": base.sha(Path(__file__)),
        "protocolSha": base.sha(PROTOCOL), "model": MODEL, "effort": EFFORT,
        "timeoutSeconds": TIMEOUT, "evaluatorSha": base.sha(ROOT / "tools/classeval_isolated_evaluator.py"),
        "helperShas": helper_shas,
        "parentRoot": str(parent), "parentContractPath": str(parent / "contract.json"),
        "parentResultPath": str(parent / "result.json"),
        "parentContractSha": base.sha(parent / "contract.json"),
        "parentResultSha": base.sha(parent / "result.json"),
        "controlRoot": str(control), "controlContractPath": str(control / "contract.json"),
        "controlResultPath": str(control / "result.json"),
        "controlContractSha": base.sha(control / "contract.json"),
        "controlResultSha": base.sha(control / "result.json"),
        "controlRunnerSha": control_contract.get("runnerSha"),
        "runRoot": str(Path(run_root).resolve()),
        "newArm": "O", "fixedOrdinaryFailures": EXPECTED_FAILURES,
        "ordinaryFailureIds": ordinary_failures,
        "tailModelCallsOnFailure": TAIL_CALLS, "plannedNewModelCalls": PLANNED_NEW_CALLS,
        "logicalCallCap": 6, "suiteEvalCap": 6, "rawAutoEvaluation": "discarded",
        "controlOutputsNotPromptInputs": True, "whole300Required": True,
        "controlReuseArms": ["E", "D"], "prefixMap": _prefix_map(prefixes, _ordered_ids(rows)),
    }


def _scope_metadata(plan: separator.SeparatorPlan) -> dict:
    return {
        "scopeA": list(plan.a_scope), "scopeB": list(plan.b_scope),
        "sharedSeparatorMethods": list(plan.shared), "separatorCover": list(plan.cover),
        "crossEdges": [list(edge) for edge in plan.cross_edges],
        "matchingSize": plan.matching_size, "fallback": plan.fallback,
        "overlap": plan.overlap, "separatorValid": plan.valid,
        "separatorReason": plan.reason,
    }


def _common_prompt(row: dict, prefix: dict, plan: separator.SeparatorPlan,
                   labels: tuple[str, ...], feedback: dict, who: str,
                   anchor_hint: dict | None) -> str:
    if "bridgeHint" not in feedback:
        feedback = dict(feedback)
        feedback["bridgeHint"] = anchor_hint
    prompt = frozen_tail._independent_prompt(
        row, prefix, plan, who, labels, feedback)
    if not plan.overlap:
        return prompt
    return prompt + f"\nDependency-separator shared S (all methods): {plan.shared!r}\n"


def _reconciliation_prompt(row: dict, prefix: dict, plan: separator.SeparatorPlan,
                           labels: tuple[str, ...], feedback: dict, a: dict, b: dict,
                           anchor_hint: dict | None) -> str:
    if "bridgeHint" not in feedback:
        feedback = dict(feedback)
        feedback["bridgeHint"] = anchor_hint
    prompt = frozen_tail._reconciliation_prompt(
        row, prefix, plan, a, b, feedback)
    if not plan.overlap:
        return prompt
    return prompt + f"\nDependency-separator shared S (all methods): {plan.shared!r}\n"


def _base_state(prefix: dict, plan: separator.SeparatorPlan, status: str,
                anchor_hint: dict | None) -> dict:
    state = {
        "status": status, "source": prefix["source"], "report": prefix["report"],
        "selected": "prefix", "logicalPrefixCalls": prefix["logicalPrefixCalls"],
        "tailModelCalls": 0, "totalLogicalCalls": prefix["logicalPrefixCalls"],
        "rawEvalCalls": 0, "canonicalEvalCalls": 0, "suiteEvalCalls": 0,
        "reportedABCanonicalEvalCalls": 0, "scopedProjectedEvalCalls": 0,
        "fullCanonicalEvalCalls": 0, "projectedMethodsA": [], "projectedMethodsB": [],
        "changedMethodsA": [], "changedMethodsB": [], "plannedOverlap": list(plan.shared),
        "activeOverlap": False, "activeOverlapMethods": [], "sharedMethodBodyShas": {
            "A": {name: None for name in plan.shared},
            "B": {name: None for name in plan.shared},
            "C": {name: None for name in plan.shared},
        }, "anchorHint": anchor_hint,
    }
    state.update(_scope_metadata(plan))
    return state


def _execute_o(row: dict, prefix: dict, plan: separator.SeparatorPlan,
               labels: tuple[str, ...], feedback: dict, output_root: Path,
               call_fn: Callable, evaluate_fn: Callable,
               anchor_hint: dict | None) -> dict:
    arm_root = Path(output_root) / "O"
    arm_root.mkdir(parents=True, exist_ok=False)
    prompt_a = _common_prompt(row, prefix, plan, labels, feedback, "A", anchor_hint)
    prompt_b = _common_prompt(row, prefix, plan, labels, feedback, "B", anchor_hint)
    a = dict(call_fn(row, arm_root / "a", "dependency-O-A", prompt_a))
    a["agent"] = "A"
    b = dict(call_fn(row, arm_root / "b", "dependency-O-B", prompt_b))
    b["agent"] = "B"
    projected_a, report_a, valid_a, eval_a, methods_a, changed_a = frozen_tail._projected_view(
        row, prefix, plan, a, evaluate_fn)
    projected_b, report_b, valid_b, eval_b, methods_b, changed_b = frozen_tail._projected_view(
        row, prefix, plan, b, evaluate_fn)
    usable_a = {"source": projected_a, "report": report_a, "valid": valid_a,
                "feedback": frozen_tail.observed_feedback(report_a, labels)}
    usable_b = {"source": projected_b, "report": report_b, "valid": valid_b,
                "feedback": frozen_tail.observed_feedback(report_b, labels)}
    prompt_c = _reconciliation_prompt(row, prefix, plan, labels, feedback, usable_a,
                                      usable_b, anchor_hint)
    c = dict(call_fn(row, arm_root / "c", "dependency-O-C", prompt_c))
    source_c, report_c, valid_c, eval_c, _, _ = frozen_tail._full_view(
        row, prefix, c, evaluate_fn)

    raw_evals = sum(item.get("valid") is True for item in (a, b, c))
    canonical_evals = eval_a + eval_b + eval_c
    suite_evals = raw_evals + canonical_evals
    if suite_evals > 6:
        raise ValueError("per-arm raw plus canonical suite evaluation cap exceeded")
    total_logical = prefix["logicalPrefixCalls"] + TAIL_CALLS
    if total_logical > 6:
        raise ValueError("logical prefix plus tail exceeds six calls")
    selected, source, report = frozen_tail._select([
        ("prefix", prefix["source"], prefix["report"]),
        ("A", projected_a, report_a), ("B", projected_b, report_b),
        ("C", source_c, report_c),
    ])
    shas = {
        "A": separator.method_body_shas(projected_a, row["class_name"], plan.shared, valid_a),
        "B": separator.method_body_shas(projected_b, row["class_name"], plan.shared, valid_b),
        "C": separator.method_body_shas(source_c, row["class_name"], plan.shared, valid_c),
    }
    active = bool(plan.overlap and not plan.fallback and valid_a and valid_b and valid_c
                  and all(value is not None for values in shas.values() for value in values.values()))
    state = {
        "status": "executed", "source": source, "report": report, "selected": selected,
        "logicalPrefixCalls": prefix["logicalPrefixCalls"], "tailModelCalls": TAIL_CALLS,
        "totalLogicalCalls": total_logical, "rawEvalCalls": raw_evals,
        "canonicalEvalCalls": canonical_evals, "suiteEvalCalls": suite_evals,
        "reportedABCanonicalEvalCalls": eval_a + eval_b,
        "scopedProjectedEvalCalls": eval_a + eval_b if not plan.fallback else 0,
        "fullCanonicalEvalCalls": canonical_evals - (eval_a + eval_b if not plan.fallback else 0),
        "projectedMethodsA": methods_a, "projectedMethodsB": methods_b,
        "changedMethodsA": changed_a, "changedMethodsB": changed_b,
        "plannedOverlap": list(plan.shared), "activeOverlap": active,
        "activeOverlapMethods": list(plan.shared) if active else [],
        "sharedMethodBodyShas": shas, "callPaths": {
            "A": str(arm_root / "a"), "B": str(arm_root / "b"), "C": str(arm_root / "c")},
        "anchorHint": anchor_hint,
    }
    state.update(_scope_metadata(plan))
    return state


def run_task(row: dict, prefix: dict, output_root: Path, *, call_fn: Callable | None = None,
             evaluate_fn: Callable = base.evaluate) -> dict:
    """Plan one O task, or execute precisely three new O calls on a failure."""

    labels = frozen_tail.target_method_labels(row, prefix["source"])
    labels = labels or ("whole_program",)
    ordered, anchor_hint = frozen_tail.choose_failure_anchor(labels, prefix["report"])
    plan = separator.build_separator_plan(prefix["source"], row["class_name"], ordered)
    if prefix["report"].get("passed"):
        return _base_state(prefix, plan, "stopped", anchor_hint)
    if call_fn is None:
        return _base_state(prefix, plan, "dry-run", anchor_hint)
    feedback = frozen_tail.observed_feedback(prefix["report"], ordered)
    feedback["bridgeHint"] = anchor_hint
    return _execute_o(row, prefix, plan, ordered, feedback, output_root, call_fn,
                      evaluate_fn, anchor_hint)


def _claim_run_root(run_root: Path, parent_root: Path, control_root: Path) -> Path:
    run = Path(run_root).resolve()
    parent, control = Path(parent_root).resolve(), Path(control_root).resolve()
    roots = (parent, control)
    if any(run == root or run in root.parents or root in run.parents for root in roots):
        raise ValueError("new run root must be a non-overlapping sibling")
    run.mkdir(parents=True, exist_ok=False)
    return run


def _write_contract(root: Path, contract: dict) -> None:
    if not root.is_dir():
        raise ValueError("claimed run root is missing")
    base.write_json(root / "contract.json", contract)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-root", required=True, type=Path)
    parser.add_argument("--control-root", required=True, type=Path)
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--execute", action="store_true",
                        help="explicitly enable the 96-call new O tail")
    args = parser.parse_args(argv)
    rows = base.load_data("classeval-pro")
    if len(rows) != TOTAL_TASKS:
        raise ValueError("official full-300 inventory required")
    parent_root = args.parent_root.resolve()
    control_root = args.control_root.resolve()
    prefixes = prefix_loader.load_ordinary_prefix(parent_root)
    ids = _ordered_ids(rows)
    if list(prefixes) != ids:
        raise ValueError("ordinary full-300 prefix ordering mismatch")
    _validate_parent_result(_json(parent_root / "result.json"))
    unresolved = [task_id for task_id in ids if not prefixes[task_id]["report"].get("passed")]
    if len(unresolved) != EXPECTED_FAILURES:
        raise ValueError("fixed ordinary unresolved set must contain exactly 32 tasks")
    control_contract, _ = _validate_control(control_root, parent_root, rows, prefixes)
    if not args.execute:
        print(json.dumps({"mode": "dry-run", "dataset": "classeval-pro",
                          "total": TOTAL_TASKS, "ordinaryFailures": len(unresolved),
                          "newArm": "O", "plannedNewModelCalls": PLANNED_NEW_CALLS,
                          "logicalCallCap": 6, "suiteEvalCap": 6,
                          "routing": _routing_summary(rows, prefixes, unresolved),
                          "parentRoot": str(parent_root), "controlRoot": str(control_root),
                          "runRoot": str(args.run_root.resolve())}, ensure_ascii=False))
        return 0

    run_root = _claim_run_root(args.run_root, parent_root, control_root)
    contract = _build_contract(run_root, parent_root, control_root, control_contract, rows, prefixes)
    try:
        _write_contract(run_root, contract)
    except Exception as exc:
        frozen_tail._mark_incomplete(run_root, {}, None, exc)
        return 2
    results: dict[str, dict] = {}
    for row in rows:
        task_id = row["task_id"]
        try:
            results[task_id] = {"O": run_task(
                row, prefixes[task_id], run_root / task_id,
                call_fn=text_runner.call, evaluate_fn=base.evaluate)}
            frozen_tail._write_progress(run_root, results, status="running")
            print(json.dumps({"taskId": task_id, "completed": len(results)}, ensure_ascii=False),
                  flush=True)
        except Exception as exc:
            frozen_tail._mark_incomplete(run_root, results, task_id, exc)
            return 2
    try:
        frozen_tail._write_result(run_root, results)
    except Exception as exc:
        frozen_tail._mark_incomplete(run_root, results, None, exc)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
