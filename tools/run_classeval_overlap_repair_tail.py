"""Dry-run-first E/D/O tail over a verified ordinary ClassEval-Pro prefix.

The tail is deliberately a small, auditable candidate.  It has no model or
evaluator effect unless ``main`` receives ``--execute``.  The ordinary prefix
is read-only and must be a terminal full-300 artifact before any tail call.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
from typing import Callable, Iterable

from tools import classeval_ordinary_prefix as prefix_loader
from tools import overlap_split_merge_candidate as scope_operator
from tools import run_classeval_source_overlap as base
from tools import run_classeval_text_overlap as text_runner

ARMS = ("E", "D", "O")
MODEL, EFFORT, TIMEOUT = "gpt-5.6-luna", "medium", 120
ROOT = base.ROOT
PROTOCOL = ROOT / "experiment_protocols/2026-09-05-classeval-overlap-repair-tail-development.md"
FEEDBACK_LIMIT = 24_000
TRUNCATION_MARKER = "[truncated]"

# This checklist is intentionally prose only.  No generated decision ledger is
# requested or passed to C; all arms receive the same contract checks.
CONTRACT_CHECKLIST = (
    "Contract checklist (identical in every arm and call): preserve class name, "
    "public API/signatures, input-output types, state transitions/invariants, "
    "units/scale, and complete ordered-stage coverage."
)
OUTPUT_RULES = (
    "Output only ONE Python code block containing complete executable class code. "
    "Do not output prose or analysis. Put every def signature on one "
    "line, with self or cls on that same line for instance or class methods."
)


def _class_methods(source: str, class_name: str) -> dict[str, ast.AST]:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            methods = {}
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if child.name in methods:
                        raise ValueError(f"duplicate method: {child.name}")
                    methods[child.name] = child
            return methods
    return {}


def ordered_method_labels(source: str, class_name: str) -> tuple[str, ...]:
    """Return direct class-method order, or empty for unusable source."""

    try:
        return tuple(_class_methods(source, class_name))
    except (SyntaxError, ValueError, TypeError):
        return ()


def target_method_labels(row: dict, ordinary_source: str) -> tuple[str, ...]:
    """Prefer skeleton AST; use the identical ordinary-source AST if needed."""

    class_name = row["class_name"]
    return (ordered_method_labels(row.get("skeleton", ""), class_name)
            or ordered_method_labels(ordinary_source, class_name))


def _case_items(report: dict) -> list[tuple[object, dict]]:
    cases = report.get("cases", {})
    if not isinstance(cases, dict):
        return []
    return sorted(((key, value) for key, value in cases.items() if isinstance(value, dict)),
                  key=lambda item: str(item[0]))


def choose_failure_anchor(labels: Iterable[str], report: dict) -> tuple[tuple[str, ...], dict | None]:
    """Move the highest observed failure-rate method to deterministic middle k.

    The completed evaluator trace is read as ``cases[*].methods`` with a
    ``passed``, ``failed``, or ``error`` case status.  Only matched method
    names count; absent or mismatched traces retain original order.
    """

    ordered = tuple(labels)
    if len(ordered) < 3:
        return ordered, None
    stats = {name: [0, 0] for name in ordered}  # failures/errors, passes
    for _, case in _case_items(report):
        methods = case.get("methods")
        if not isinstance(methods, (list, tuple)):
            continue
        matched = {name for name in methods if isinstance(name, str)} & stats.keys()
        for name in matched:
            if case.get("status") in {"failed", "error"}:
                stats[name][0] += 1
            elif case.get("status") == "passed":
                stats[name][1] += 1
    ranked = [(f / (f + p), f, -index, name)
              for index, name in enumerate(ordered)
              for f, p in [stats[name]] if f]
    if not ranked:
        return ordered, None
    rate, failures, _, anchor = max(ranked)
    moved = list(ordered)
    moved.remove(anchor)
    moved.insert(len(ordered) // 2, anchor)
    return tuple(moved), {"method": anchor, "failed": failures,
                          "passed": stats[anchor][1], "failureRate": rate}


def _clip(value: str, limit: int) -> tuple[str, bool]:
    if len(value) <= limit:
        return value, False
    if limit <= len(TRUNCATION_MARKER):
        return TRUNCATION_MARKER[:limit], True
    return value[:limit - len(TRUNCATION_MARKER)] + TRUNCATION_MARKER, True


def observed_feedback(report: dict, method_allowlist: Iterable[str]) -> dict:
    """Keep deterministic bounded observed feedback, never source or tests."""

    methods = tuple(method_allowlist)
    allowed = set(methods)
    fatal_raw = "" if report.get("fatal") is None else str(report.get("fatal"))
    raw_items = _case_items(report)
    raw_messages = [str(item.get("message", "")) for _, item in raw_items]
    needs_truncation = len(fatal_raw) + sum(map(len, raw_messages)) > FEEDBACK_LIMIT
    # Reserve room so even an exactly-full fatal string followed by omitted
    # messages carries an explicit truncation marker.
    remaining = FEEDBACK_LIMIT - (len(TRUNCATION_MARKER) if needs_truncation else 0)
    truncated = needs_truncation
    fatal, was_truncated = _clip(fatal_raw, remaining)
    remaining -= len(fatal)
    truncated |= was_truncated
    marker_emitted = was_truncated
    cases = {}
    for (case_id, item), raw_message in zip(raw_items, raw_messages):
        if remaining:
            message, was_truncated = _clip(raw_message, remaining)
            remaining -= len(message)
            truncated |= was_truncated
            marker_emitted |= was_truncated
        else:
            was_truncated = bool(raw_message)
            if was_truncated and not marker_emitted:
                message = TRUNCATION_MARKER
                marker_emitted = True
            else:
                message = ""
            truncated |= was_truncated
        raw_methods = item.get("methods", ())
        if not isinstance(raw_methods, (list, tuple)):
            raw_methods = ()
        cases[str(case_id)] = {
            "status": item.get("status"), "message": message,
            "methods": sorted({name for name in raw_methods if isinstance(name, str)} & allowed),
        }
    return {"passed": bool(report.get("passed")), "expectedCount": report.get("expectedCount"),
            "fatal": fatal or None, "methods": list(methods), "cases": cases,
            "feedbackTruncated": truncated}


def canonicalize_source(source: str) -> str:
    """Canonicalize parsed Python so all arms share multiline/static handling."""

    if not isinstance(source, str):
        raise TypeError("source must be text")
    tree = ast.parse(source)
    canonical = ast.unparse(tree).strip()
    if not canonical:
        raise SyntaxError("empty Python source")
    return canonical + "\n"


def canonical_evaluation_source(row: dict, source: str) -> str:
    """Use one AST-unparse -> author evaluation-source path for every arm."""

    return base.evaluation_source(row, canonicalize_source(source))


def bridge_body_sha(source: str, class_name: str, bridge: str | None,
                    valid: bool = True) -> str | None:
    """Hash a present bridge body for provenance; never treats equality as proof."""

    if not valid or bridge is None:
        return None
    try:
        node = _class_methods(source, class_name).get(bridge)
        if node is None:
            return None
        body = ast.Module(body=list(getattr(node, "body", ())), type_ignores=[])
        payload = ast.dump(body, include_attributes=False)
    except (SyntaxError, ValueError, TypeError, AttributeError):
        return None
    return hashlib.sha256(payload.encode()).hexdigest()


def _method_start(node: ast.AST) -> int:
    decorators = getattr(node, "decorator_list", ())
    return min([node.lineno] + [item.lineno for item in decorators])


def _indented_segment(lines: list[str], node: ast.AST, target_indent: int) -> list[str]:
    start, end = _method_start(node) - 1, node.end_lineno
    segment = lines[start:end]
    current = len(segment[0]) - len(segment[0].lstrip())
    delta = target_indent - current
    result = []
    for line in segment:
        if not line.strip():
            result.append("")
        else:
            indent = len(line) - len(line.lstrip())
            result.append(" " * max(0, indent + delta) + line.lstrip())
    return result


def _project_source_details(parent_source: str, candidate_source: str, class_name: str,
                            assigned_methods: Iterable[str]) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    """Project only existing assigned nodes and report actual/changed methods."""

    parent_methods = _class_methods(parent_source, class_name)
    candidate_methods = _class_methods(candidate_source, class_name)
    assigned = tuple(assigned_methods)
    if len(assigned) != len(set(assigned)):
        raise ValueError("assigned methods must be unique")
    if any(name not in parent_methods or name not in candidate_methods for name in assigned):
        raise ValueError("candidate lacks an assigned existing method")
    parent_lines, candidate_lines = parent_source.splitlines(), candidate_source.splitlines()
    replacements = []
    changed = []
    for name in assigned:
        parent_node, candidate_node = parent_methods[name], candidate_methods[name]
        parent_start = _method_start(parent_node) - 1
        indent = len(parent_lines[parent_start]) - len(parent_lines[parent_start].lstrip())
        replacements.append((parent_start, parent_node.end_lineno,
                             _indented_segment(candidate_lines, candidate_node, indent)))
        if ast.dump(parent_node, include_attributes=False) != ast.dump(candidate_node, include_attributes=False):
            changed.append(name)
    for start, end, segment in sorted(replacements, reverse=True):
        parent_lines[start:end] = segment
    result = "\n".join(parent_lines) + ("\n" if parent_source.endswith("\n") else "")
    return result, assigned, tuple(changed)


def project_source(parent_source: str, candidate_source: str, class_name: str,
                   assigned_methods: Iterable[str]) -> str:
    """Compatibility wrapper returning only the projected source."""

    return _project_source_details(parent_source, candidate_source, class_name,
                                   assigned_methods)[0]


def _score(report: dict) -> tuple[bool, int]:
    cases = report.get("cases", {})
    if not isinstance(cases, dict):
        cases = {}
    return bool(report.get("passed")), sum(item.get("status") == "passed"
                                           for item in cases.values() if isinstance(item, dict))


def _failure(message: str) -> dict:
    return {"passed": False, "cases": {}, "fatal": message}


def _invalid_view(prefix: dict, message: str) -> tuple[str, dict, bool, int, tuple[str, ...], tuple[str, ...]]:
    return prefix["source"], _failure(message), False, 0, (), ()


def _full_view(row: dict, prefix: dict, candidate: dict,
               evaluate_fn: Callable) -> tuple[str, dict, bool, int, tuple[str, ...], tuple[str, ...]]:
    """Canonicalize and evaluate a full candidate; raw call reports are ignored."""

    if candidate.get("valid") is not True:
        return _invalid_view(prefix, "invalid model candidate")
    try:
        source = canonical_evaluation_source(row, candidate["source"])
    except (SyntaxError, ValueError, TypeError, KeyError) as exc:
        return _invalid_view(prefix, f"invalid canonical candidate: {type(exc).__name__}")
    report = evaluate_fn(row, source)  # evaluator exceptions remain run errors, not score failures
    return source, report, True, 1, (), ()


def _projected_view(row: dict, prefix: dict, plan: scope_operator.ScopePlan,
                    candidate: dict, evaluate_fn: Callable) -> tuple[str, dict, bool, int, tuple[str, ...], tuple[str, ...]]:
    """Canonicalize, project D/O A/B, and then evaluate the canonical source."""

    if plan.arm == "E" or plan.fallback:
        return _full_view(row, prefix, candidate, evaluate_fn)
    if candidate.get("valid") is not True:
        return _invalid_view(prefix, "invalid model candidate")
    try:
        parent = canonical_evaluation_source(row, prefix["source"])
        candidate_source = canonical_evaluation_source(row, candidate["source"])
        if candidate.get("agent") not in {"A", "B"}:
            raise ValueError("candidate agent is not A or B")
        scope = plan.a_scope if candidate["agent"] == "A" else plan.b_scope
        projected, projected_methods, changed_methods = _project_source_details(
            parent, candidate_source, row["class_name"], scope)
        projected = canonical_evaluation_source(row, projected)
    except (SyntaxError, ValueError, TypeError, KeyError, IndexError) as exc:
        return _invalid_view(prefix, f"invalid projected candidate: {type(exc).__name__}")
    report = evaluate_fn(row, projected)  # do not catch unexpected evaluator errors
    return projected, report, True, 1, projected_methods, changed_methods


def _independent_prompt(row: dict, prefix: dict, plan: scope_operator.ScopePlan,
                        agent: str, labels: tuple[str, ...], feedback: dict) -> str:
    scope = plan.a_scope if agent == "A" else plan.b_scope
    return (
        f"Independent tail repair {agent}; effective arm={plan.effective_policy}.\n"
        "Use only the caller-verified skeleton, common ordinary source, and bounded "
        "observed feedback below. Do not seek peer output, gold, solution, or raw tests.\n"
        f"class_name: {row['class_name']}\nSkeleton:\n{row['skeleton']}\n"
        f"Common ordinary source:\n{prefix['source']}\nObserved feedback:\n"
        f"{json.dumps(feedback, ensure_ascii=False, sort_keys=True)}\n"
        f"Assigned ordered methods: {', '.join(scope)}\n"
        f"Planned bridge: {plan.bridge!r}; bridge routing hint: {feedback.get('bridgeHint')!r}; "
        f"all target methods: {', '.join(labels)}\n"
        f"{CONTRACT_CHECKLIST}\n{OUTPUT_RULES}\n"
        "For D/O, only assigned existing method nodes will be projected; do not rely on new helpers/imports."
    )


def _reconciliation_prompt(row: dict, prefix: dict, plan: scope_operator.ScopePlan,
                           a: dict, b: dict, feedback: dict) -> str:
    return (
        f"Reconciliation tail call C; effective arm={plan.effective_policy}.\n"
        "Use the common ordinary prefix and the two actually usable candidate sources "
        "and observed feedback below. Produce final complete executable class code.\n"
        f"class_name: {row['class_name']}\nSkeleton:\n{row['skeleton']}\n"
        f"Common ordinary source:\n{prefix['source']}\n"
        f"Candidate A usable source:\n---\n{a['source']}\n---\n"
        f"Candidate A observed feedback:\n{json.dumps(a['feedback'], ensure_ascii=False, sort_keys=True)}\n"
        f"Candidate B usable source:\n---\n{b['source']}\n---\n"
        f"Candidate B observed feedback:\n{json.dumps(b['feedback'], ensure_ascii=False, sort_keys=True)}\n"
        f"Common observed feedback and anchor hint:\n{json.dumps(feedback, ensure_ascii=False, sort_keys=True)}\n"
        f"Planned bridge: {plan.bridge!r}; all target methods: {', '.join(plan.a_scope + tuple(x for x in plan.b_scope if x not in plan.a_scope))}\n"
        f"{CONTRACT_CHECKLIST}\n{OUTPUT_RULES}\n"
        "Resolve contradictions generally; the caller-supplied verified-input contract excludes gold, reference code, and raw final tests."
    )


def _select(candidates: list[tuple[str, str, dict]]) -> tuple[str, str, dict]:
    selected = candidates[0]
    for candidate in candidates[1:]:
        if _score(candidate[2]) > _score(selected[2]):
            selected = candidate
    return selected


def _planned_overlap(plan: scope_operator.ScopePlan) -> tuple[str, ...]:
    return tuple(plan.intersection) if plan.overlap else ()


def _plan_result(prefix: dict, plans: dict[str, scope_operator.ScopePlan], *, dry: bool) -> dict:
    result = {}
    for arm in ARMS:
        plan = plans[arm]
        result[arm] = {
            "status": "dry-run" if dry else "stopped", "source": prefix["source"],
            "report": prefix["report"], "selected": "prefix",
            "logicalPrefixCalls": prefix["logicalPrefixCalls"], "tailModelCalls": 0,
            "totalLogicalCalls": prefix["logicalPrefixCalls"], "rawEvalCalls": 0,
            "canonicalEvalCalls": 0, "suiteEvalCalls": 0, "projectedEvalCalls": 0,
            "scopeA": plan.a_scope, "scopeB": plan.b_scope,
            "bridge": plan.bridge, "intersection": plan.intersection,
            "plannedOverlap": _planned_overlap(plan), "activeOverlap": False,
            "activeOverlapMethods": [], "projectedMethodsA": [], "projectedMethodsB": [],
            "changedMethodsA": [], "changedMethodsB": [], "fallback": plan.fallback,
            "overlap": plan.overlap, "bridgeBodyShaA": None,
            "bridgeBodyShaB": None, "bridgeBodyShaC": None,
            "bridgeBodyShas": {"A": None, "B": None, "C": None},
        }
    return result


def _execute_arm(row: dict, prefix: dict, plan: scope_operator.ScopePlan,
                 labels: tuple[str, ...], feedback: dict, output_root: Path,
                 call_fn: Callable, evaluate_fn: Callable) -> dict:
    arm_root = output_root / plan.arm
    prompt_a = _independent_prompt(row, prefix, plan, "A", labels, feedback)
    prompt_b = _independent_prompt(row, prefix, plan, "B", labels, feedback)
    a = dict(call_fn(row, arm_root / "a", f"tail-{plan.arm}-A", prompt_a))
    a["agent"] = "A"
    b = dict(call_fn(row, arm_root / "b", f"tail-{plan.arm}-B", prompt_b))
    b["agent"] = "B"
    projected_a, report_a, valid_a, eval_a, methods_a, changed_a = _projected_view(
        row, prefix, plan, a, evaluate_fn)
    projected_b, report_b, valid_b, eval_b, methods_b, changed_b = _projected_view(
        row, prefix, plan, b, evaluate_fn)
    usable_a = {"source": projected_a, "report": report_a,
                "feedback": observed_feedback(report_a, labels), "valid": valid_a}
    usable_b = {"source": projected_b, "report": report_b,
                "feedback": observed_feedback(report_b, labels), "valid": valid_b}
    prompt_c = _reconciliation_prompt(row, prefix, plan, usable_a, usable_b, feedback)
    c = dict(call_fn(row, arm_root / "c", f"tail-{plan.arm}-C", prompt_c))
    source_c, report_c, valid_c, eval_c, _, _ = _full_view(row, prefix, c, evaluate_fn)

    raw_evals = sum(item.get("valid") is True for item in (a, b, c))
    canonical_evals = eval_a + eval_b + eval_c
    suite_evals = raw_evals + canonical_evals
    if suite_evals > 6:
        raise ValueError("per-arm raw plus canonical suite evaluation cap exceeded")
    candidates = [("prefix", prefix["source"], prefix["report"]),
                  ("A", projected_a, report_a), ("B", projected_b, report_b),
                  ("C", source_c, report_c)]
    selected, source, report = _select(candidates)
    total = prefix["logicalPrefixCalls"] + 3
    if total > 6:
        raise ValueError("logical prefix plus tail exceeds six calls")
    bridge_sha_a = bridge_body_sha(projected_a, row["class_name"], plan.bridge, valid_a)
    bridge_sha_b = bridge_body_sha(projected_b, row["class_name"], plan.bridge, valid_b)
    bridge_sha_c = bridge_body_sha(source_c, row["class_name"], plan.bridge, valid_c)
    active = (plan.arm == "O" and not plan.fallback and valid_a and valid_b and valid_c
              and bridge_sha_a is not None and bridge_sha_b is not None and bridge_sha_c is not None)
    return {
        "status": "executed", "source": source, "report": report, "selected": selected,
        "logicalPrefixCalls": prefix["logicalPrefixCalls"], "tailModelCalls": 3,
        "totalLogicalCalls": total, "rawEvalCalls": raw_evals,
        "canonicalEvalCalls": canonical_evals, "suiteEvalCalls": suite_evals,
        "projectedEvalCalls": eval_a + eval_b, "scopeA": plan.a_scope,
        "scopeB": plan.b_scope, "bridge": plan.bridge,
        "intersection": plan.intersection, "plannedOverlap": _planned_overlap(plan),
        "activeOverlap": active,
        "activeOverlapMethods": (plan.bridge,) if active else (),
        "projectedMethodsA": methods_a, "projectedMethodsB": methods_b,
        "changedMethodsA": changed_a, "changedMethodsB": changed_b,
        "fallback": plan.fallback, "overlap": plan.overlap,
        "bridgeBodyShaA": bridge_sha_a, "bridgeBodyShaB": bridge_sha_b,
        "bridgeBodyShaC": bridge_sha_c,
        "bridgeBodyShas": {"A": bridge_sha_a, "B": bridge_sha_b, "C": bridge_sha_c},
    }


def run_task(row: dict, prefix: dict, output_root: Path, *, call_fn: Callable | None = None,
             evaluate_fn: Callable = base.evaluate) -> dict[str, dict]:
    """Plan one task or execute exactly A+B+C for each unresolved arm."""

    labels = target_method_labels(row, prefix["source"])
    if not labels:
        labels = ("whole_program",)
    labels, anchor_hint = choose_failure_anchor(labels, prefix["report"])
    plans = scope_operator.build_scope_plans(labels)
    if prefix["report"].get("passed"):
        return _plan_result(prefix, plans, dry=False)
    if call_fn is None:
        return _plan_result(prefix, plans, dry=True)
    feedback = observed_feedback(prefix["report"], labels)
    feedback["bridgeHint"] = anchor_hint
    return {arm: _execute_arm(row, prefix, plans[arm], labels, feedback,
                              Path(output_root), call_fn, evaluate_fn) for arm in ARMS}


def _claim_run_root(run_root: Path, parent_root: Path) -> Path:
    """Claim an empty sibling output root exactly once before any model call."""

    run = Path(run_root).resolve()
    parent = Path(parent_root).resolve()
    if run == parent or run in parent.parents or parent in run.parents:
        raise ValueError("tail run root must be a non-overlapping sibling of parent root")
    run.mkdir(parents=True, exist_ok=False)
    return run


def _prefix_map(prefixes: dict[str, dict], ids: Iterable[str]) -> dict[str, dict]:
    return {task_id: {"callPaths": prefixes[task_id]["callPaths"],
                      "sourceSha": prefixes[task_id]["sourceSha"],
                      "logicalPrefixCalls": prefixes[task_id]["logicalPrefixCalls"]}
            for task_id in ids}


def _build_contract(run_root: Path, parent_root: Path, rows: list[dict],
                    prefixes: dict[str, dict]) -> dict:
    parent = Path(parent_root).resolve()
    helpers = {
        "prefixLoaderSha": base.sha(Path(prefix_loader.__file__)),
        "scopeOperatorSha": base.sha(Path(scope_operator.__file__)),
        "baseRunnerSha": base.sha(Path(base.__file__)),
        "textRunnerSha": base.sha(Path(text_runner.__file__)),
    }
    return {
        "dataset": "classeval-pro", "taskIds": [row["task_id"] for row in rows],
        "dataSha": base.PRO_SHA, "runnerSha": base.sha(Path(__file__)),
        "protocolSha": base.sha(PROTOCOL), "textRunnerSha": helpers["textRunnerSha"],
        "evaluatorSha": base.sha(ROOT / "tools/classeval_isolated_evaluator.py"),
        "helperShas": helpers, "prefixLoaderSha": helpers["prefixLoaderSha"],
        "scopeOperatorSha": helpers["scopeOperatorSha"], "baseRunnerSha": helpers["baseRunnerSha"],
        "parentRoot": str(parent), "parentContractPath": str(parent / "contract.json"),
        "parentResultPath": str(parent / "result.json"),
        "parentContractSha": base.sha(parent / "contract.json"),
        "parentResultSha": base.sha(parent / "result.json"), "runRoot": str(Path(run_root).resolve()),
        "model": MODEL, "effort": EFFORT, "timeoutSeconds": TIMEOUT,
        "tailModelCallsOnFailure": 3, "logicalCallCap": 6, "suiteEvalCap": 6,
        "rawAutoEvaluation": "discarded", "prefixMap": _prefix_map(prefixes, [r["task_id"] for r in rows]),
    }


def _write_contract(root: Path, contract: dict) -> None:
    if not root.is_dir():
        raise ValueError("claimed tail run root is missing")
    base.write_json(root / "contract.json", contract)


def _write_progress(root: Path, results: dict[str, dict], *, status: str,
                    error: dict | None = None) -> None:
    if not root.is_dir():
        raise ValueError("claimed tail run root is missing")
    payload = {"status": status, "completed": len(results), "total": 300, "tasks": results}
    if error is not None:
        payload["error"] = error
    base.write_json(root / "progress.json", payload)


def _write_result(root: Path, results: dict[str, dict]) -> None:
    if not root.is_dir():
        raise ValueError("claimed tail run root is missing")
    base.write_json(root / "result.json", {"status": "complete", "completed": len(results),
                                           "total": 300, "tasks": results})


def _mark_incomplete(root: Path, results: dict[str, dict], task_id, exc: Exception) -> dict:
    """Best-effort error/progress record; never turns an exception into a score."""

    error = {"taskId": task_id, "type": type(exc).__name__, "message": str(exc)}
    try:
        base.write_json(root / "error.json", error)
    except Exception:
        pass
    try:
        _write_progress(root, results, status="incomplete", error=error)
    except Exception:
        pass
    try:
        (root / "result.json").unlink(missing_ok=True)
    except OSError:
        pass
    return error


def _write_run(root: Path, rows: list[dict], results: dict[str, dict], contract: dict | None = None) -> None:
    """Write terminal files without attempting to mkdir an already-claimed root."""

    if not root.is_dir():
        raise ValueError("tail run root must be claimed before writing")
    if contract is not None:
        _write_contract(root, contract)
    _write_result(root, results)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-root", required=True, type=Path)
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--execute", action="store_true",
                        help="explicitly enable model/evaluator calls")
    args = parser.parse_args(argv)
    rows = base.load_data("classeval-pro")
    parent_root = args.parent_root.resolve()
    prefixes = prefix_loader.load_ordinary_prefix(parent_root)
    ids = [row["task_id"] for row in rows]
    if len(rows) != 300 or list(prefixes) != ids:
        raise ValueError("full300 ordinary prefix is required")
    if not args.execute:
        print(json.dumps({"mode": "dry-run", "dataset": "classeval-pro", "total": 300,
                          "unresolved": sum(not prefixes[task]["report"]["passed"] for task in ids)},
                         ensure_ascii=False))
        return 0

    run_root = _claim_run_root(args.run_root, parent_root)
    contract = _build_contract(run_root, parent_root, rows, prefixes)
    _write_contract(run_root, contract)  # contract is durable before the first call
    results: dict[str, dict] = {}
    for row in rows:
        task_id = row["task_id"]
        try:
            results[task_id] = run_task(row, prefixes[task_id], run_root / task_id,
                                        call_fn=text_runner.call, evaluate_fn=base.evaluate)
            _write_progress(run_root, results, status="running")
            print(json.dumps({"taskId": task_id, "completed": len(results)}, ensure_ascii=False), flush=True)
        except Exception as exc:
            error = _mark_incomplete(run_root, results, task_id, exc)
            print(json.dumps({"status": "incomplete", "completed": len(results),
                              "taskId": task_id, "error": error}, ensure_ascii=False), flush=True)
            return 2
    try:
        _write_result(run_root, results)
    except Exception as exc:
        error = _mark_incomplete(run_root, results, None, exc)
        print(json.dumps({"status": "incomplete", "completed": len(results),
                          "error": error}, ensure_ascii=False), flush=True)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
