"""Paired Luna/Gemma E/O development over the verified ClassEval-Pro U32.

This wrapper deliberately delegates E execution to the frozen tail's
``_execute_arm`` and O execution to the frozen dependency-separator runner's
``run_task``.  Cached A/B candidates are read-only inputs; only E-C, O-B, and
O-C are new calls.  The default mode validates every input and prints a plan.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from tools import classeval_ordinary_prefix as prefix_loader
from tools import dependency_separator_overlap as separator
from tools import run_classeval_dependency_separator_mixed as gemma_base
from tools import run_classeval_dependency_separator_overlap as graph
from tools import run_classeval_overlap_repair_tail as frozen_tail
from tools import run_classeval_source_overlap as base
from tools import run_classeval_text_overlap as text_runner
from tools import overlap_split_merge_candidate as scope_operator


ROOT = base.ROOT
PROTOCOL = ROOT / "experiment_protocols/2026-09-06-classeval-gemma-luna-paired-v1.md"
TOTAL_TASKS = 300
EXPECTED_FAILURES = 32
LUNA_MODEL, LUNA_EFFORT, LUNA_TIMEOUT = "gpt-5.6-luna", "medium", 120
GEMMA_MODEL = gemma_base.GEMMA_MODEL
GEMMA_THINKING = "minimal"
GEMMA_TEMPERATURE = gemma_base.GEMMA_TEMPERATURE
GEMMA_MAX_OUTPUT = gemma_base.GEMMA_MAX_OUTPUT
GEMMA_TIMEOUT = gemma_base.GEMMA_TIMEOUT
GEMMA_KEY_COUNT = gemma_base.GEMMA_KEY_COUNT
DEFAULT_KEYS_FILE = gemma_base.DEFAULT_KEYS_FILE


def _json(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _sha_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _inside(root: Path, path: Path) -> Path:
    root, resolved = Path(root).resolve(), Path(path).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("cached artifact path escapes its cache root") from exc
    return resolved


def _validate_parent(parent_root: Path, rows: list[dict], prefixes: dict[str, dict]) -> None:
    result = _json(Path(parent_root) / "result.json")
    graph._validate_parent_result(result)
    ids = [row["task_id"] for row in rows]
    if list(prefixes) != ids:
        raise ValueError("ordinary full-300 prefix ordering mismatch")
    if sum(bool(prefixes[task_id]["report"].get("passed")) for task_id in ids) != 268:
        raise ValueError("ordinary parent must contain exactly 268 passed tasks")
    if len([task_id for task_id in ids if not prefixes[task_id]["report"].get("passed")]) != EXPECTED_FAILURES:
        raise ValueError("ordinary parent must contain exactly U32")


def _load_screen_gemma_item(row: dict, directory: Path, expected_prompt: str,
                            ordinal: int) -> dict:
    """Validate one completed minimal-screen B artifact without evaluating it."""

    directory = Path(directory).resolve()
    contract, receipt = _json(directory / "contract.json"), _json(directory / "receipt.json")
    prompt = (directory / "prompt.txt").read_text(encoding="utf-8")
    expected_contract = {
        "taskId": row["task_id"], "label": "mixed-E-B", "dataSha": base.PRO_SHA,
        "provider": "gemini_direct", "model": GEMMA_MODEL,
        "thinkingLevel": GEMMA_THINKING, "temperature": GEMMA_TEMPERATURE,
        "maxOutputTokens": GEMMA_MAX_OUTPUT, "timeoutSeconds": GEMMA_TIMEOUT,
        "taskOrdinal": int(ordinal), "keyAssignment": "taskOrdinalMod10",
        "solverTools": False,
    }
    if any(contract.get(key) != value for key, value in expected_contract.items()):
        raise ValueError(f"minimal E/B cache contract mismatch: {directory}")
    if prompt != expected_prompt or contract.get("promptSha") != _sha_text(prompt):
        raise ValueError(f"minimal E/B prompt mismatch: {directory}")
    raw_path = directory / "artifact" / "last_message.txt"
    raw = raw_path.read_text(encoding="utf-8") if raw_path.is_file() else ""
    try:
        raw_code = text_runner.extract_code(raw)
    except (ValueError, SyntaxError) as exc:
        raise ValueError(f"minimal E/B code is not parseable: {directory}") from exc
    candidate = (directory / "candidate.py").read_text(encoding="utf-8")
    expected_candidate = base.evaluation_source(row, raw_code)
    if candidate != expected_candidate or receipt.get("sourceSha") != _sha_text(raw_code):
        raise ValueError(f"minimal E/B source hash/transformation mismatch: {directory}")
    required_receipt = {
        "valid": True, "finishReason": "STOP", "model": GEMMA_MODEL,
        "modelVersion": GEMMA_MODEL, "modelVersionMatch": True,
        "httpStatus": 200, "nonTextItems": [], "overBudget": False,
        "errorType": None, "apiErrorStatus": None,
    }
    if any(receipt.get(key) != value for key, value in required_receipt.items()):
        raise ValueError(f"minimal E/B receipt is not a valid completed response: {directory}")
    report = _json(directory / "evaluation.json")
    if not isinstance(report.get("passed"), bool):
        raise ValueError(f"minimal E/B evaluation report is malformed: {directory}")
    return {"source": candidate, "report": report, "valid": True,
            "path": directory, "receipt": receipt, "cached": True}


def _e_prompt(row: dict, prefix: dict, agent: str = "B") -> str:
    _, ordered, feedback, _ = _e_context(row, prefix)
    plan = scope_operator.build_scope_plans(ordered)["E"]
    return frozen_tail._independent_prompt(row, prefix, plan, agent, ordered, feedback)


def _e_context(row: dict, prefix: dict) -> tuple[tuple[str, ...], tuple[str, ...], dict, dict | None]:
    labels = frozen_tail.target_method_labels(row, prefix["source"]) or ("whole_program",)
    ordered, anchor_hint = frozen_tail.choose_failure_anchor(labels, prefix["report"])
    feedback = frozen_tail.observed_feedback(prefix["report"], ordered)
    feedback["bridgeHint"] = anchor_hint
    return labels, ordered, feedback, anchor_hint


def _o_prompt(row: dict, prefix: dict, agent: str) -> str:
    labels = frozen_tail.target_method_labels(row, prefix["source"]) or ("whole_program",)
    ordered, anchor_hint = frozen_tail.choose_failure_anchor(labels, prefix["report"])
    plan = separator.build_separator_plan(prefix["source"], row["class_name"], ordered)
    feedback = frozen_tail.observed_feedback(prefix["report"], ordered)
    feedback["bridgeHint"] = anchor_hint
    return graph._common_prompt(row, prefix, plan, ordered, feedback, agent, anchor_hint)


def _assert_cached_prompt(directory: Path, expected_prompt: str, label: str) -> None:
    directory = Path(directory).resolve()
    prompt_path = directory / "prompt.txt"
    prompt = prompt_path.read_text(encoding="utf-8")
    contract = _json(directory / "contract.json")
    if prompt != expected_prompt or contract.get("promptSha") != _sha_text(prompt):
        raise ValueError(f"{label} cached prompt mismatch: {directory}")


def _validate_e_cache(cache_root: Path, parent_root: Path, rows: list[dict],
                      prefixes: dict[str, dict]) -> dict[str, Any]:
    cache = gemma_base._validate_e_cache(cache_root, parent_root, rows, prefixes)
    for row in rows:
        task_id = row["task_id"]
        if prefixes[task_id]["report"].get("passed"):
            continue
        _assert_cached_prompt(cache["root"] / task_id / "E" / "a",
                              _e_prompt(row, prefixes[task_id], "A"), "old E/A")
    return cache


def _validate_screen_cache(screen_root: Path, parent_root: Path, e_root: Path,
                           rows: list[dict], prefixes: dict[str, dict]) -> dict[str, Any]:
    root = Path(screen_root).resolve()
    contract, result = _json(root / "contract.json"), _json(root / "result.json")
    ids = [row["task_id"] for row in rows]
    unresolved = [task_id for task_id in ids if not prefixes[task_id]["report"].get("passed")]
    expected = {
        "dataset": "classeval-pro", "dataSha": base.PRO_SHA,
        "parentRoot": str(Path(parent_root).resolve()),
        "eCacheRoot": str(Path(e_root).resolve()),
        "ordinaryPassed": 268, "fixedOrdinaryFailures": EXPECTED_FAILURES,
        "screenArm": "E", "screenModelCalls": EXPECTED_FAILURES,
        "model": GEMMA_MODEL, "thinkingLevel": GEMMA_THINKING,
        "temperature": GEMMA_TEMPERATURE, "maxOutputTokens": GEMMA_MAX_OUTPUT,
        "timeoutSeconds": GEMMA_TIMEOUT, "noRetry": True,
        "keyAssignment": "official task ordinal modulo 10",
        "full300Required": True, "variant": "gemma-minimal-screen",
    }
    if any(contract.get(key) != value for key, value in expected.items()):
        raise ValueError("minimal screen contract does not match the approved cache")
    if (result.get("status") != "screen-complete" or result.get("screenOnly") is not True
            or result.get("completed") != TOTAL_TASKS or result.get("total") != TOTAL_TASKS
            or result.get("screenCompleted") != EXPECTED_FAILURES
            or list(result.get("statusMap", {})) != ids
            or any(result["statusMap"].get(task_id) != ("stopped" if task_id not in unresolved else "screened")
                   for task_id in ids)):
        raise ValueError("completed minimal screen with full-300 coverage map is required")
    gate = result.get("gate") or {}
    if (gate.get("attempted") != EXPECTED_FAILURES or gate.get("expected") != EXPECTED_FAILURES
            or gate.get("usableB") != EXPECTED_FAILURES or gate.get("proceed") is not True):
        raise ValueError("minimal screen gate did not pass")
    records = result.get("tasks")
    if not isinstance(records, list) or [item.get("taskId") for item in records] != unresolved:
        raise ValueError("minimal screen U32 record ordering mismatch")
    rows_by_id = {row["task_id"]: row for row in rows}
    items = {}
    for ordinal, task_id in enumerate(unresolved):
        row, prefix = rows_by_id[task_id], prefixes[task_id]
        record = records[ordinal]
        expected_dir = root / task_id / "E" / "b"
        if (record.get("bPath") != str(expected_dir.resolve())
                or record.get("bValid") is not True or record.get("usable") is not True):
            raise ValueError(f"minimal E/B record path/validity mismatch: {task_id}")
        item = _load_screen_gemma_item(row, expected_dir, _e_prompt(row, prefix), row["_data_index"])
        items[task_id] = item
    return {"root": root, "contract": contract, "result": result,
            "contractSha": base.sha(root / "contract.json"),
            "resultSha": base.sha(root / "result.json"), "items": items}


def _load_luna_item(row: dict, directory: Path, label: str) -> dict:
    """Read a previously completed Luna call using the canonical loader checks."""

    return prefix_loader._call(row, Path(directory), label)


def _validate_o_cache(o_root: Path, parent_root: Path, e_root: Path,
                      rows: list[dict], prefixes: dict[str, dict]) -> dict[str, Any]:
    root = Path(o_root).resolve()
    contract, result = _json(root / "contract.json"), _json(root / "result.json")
    control_root = Path(contract.get("controlRoot", "")).resolve()
    if control_root != Path(e_root).resolve():
        raise ValueError("graph O cache is not bound to the requested old E/D control")
    control_contract = _json(control_root / "contract.json")
    expected_contract = graph._build_contract(root, parent_root, control_root,
                                              control_contract, rows, prefixes)
    if contract != expected_contract:
        raise ValueError("graph O cache contract/hash inputs do not match")
    ids = [row["task_id"] for row in rows]
    tasks = result.get("tasks")
    if (result.get("status") != "complete" or result.get("completed") != TOTAL_TASKS
            or result.get("total") != TOTAL_TASKS or not isinstance(tasks, dict)
            or list(tasks) != ids):
        raise ValueError("completed full-300 graph O cache is required")
    rows_by_id = {row["task_id"]: row for row in rows}
    items = {}
    for task_id in ids:
        if prefixes[task_id]["report"].get("passed"):
            continue
        state = tasks[task_id].get("O")
        expected_dir = root / task_id / "O" / "a"
        if not isinstance(state, dict) or state.get("status") != "executed":
            raise ValueError(f"missing executed graph O state: {task_id}")
        paths = state.get("callPaths") or {}
        if paths.get("A") != str(expected_dir.resolve()):
            raise ValueError(f"graph O/A path mismatch: {task_id}")
        _assert_cached_prompt(expected_dir,
                              _o_prompt(rows_by_id[task_id], prefixes[task_id], "A"),
                              "graph O/A")
        items[task_id] = _load_luna_item(rows_by_id[task_id], expected_dir, "dependency-O-A")
        if items[task_id].get("valid") is not True:
            raise ValueError(f"graph O/A cache is invalid: {task_id}")
    if len(items) != EXPECTED_FAILURES:
        raise ValueError("graph O/A cache must cover exactly U32")
    return {"root": root, "contract": contract, "result": result,
            "contractSha": base.sha(root / "contract.json"),
            "resultSha": base.sha(root / "result.json"), "items": items}


def _minimal_request(prompt: str, key: str) -> dict[str, Any]:
    """Reuse the frozen direct Gemma transport with only thinking set to minimal."""

    previous = gemma_base.GEMMA_THINKING_LEVEL
    try:
        gemma_base.GEMMA_THINKING_LEVEL = GEMMA_THINKING
        return gemma_base._gemma_request(prompt, key)
    finally:
        gemma_base.GEMMA_THINKING_LEVEL = previous


def _gemma_call(row: dict, out: Path, label: str, prompt: str, *, key: str,
                ordinal: int) -> dict:
    """Make one fresh minimal Gemma call with an arm-correct label."""

    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    (out / "work").mkdir()
    (out / "artifact").mkdir()
    (out / "prompt.txt").write_text(prompt, encoding="utf-8")
    base.write_json(out / "contract.json", {
        "taskId": row["task_id"], "label": label, "dataSha": base.PRO_SHA,
        "promptSha": _sha_text(prompt), "provider": "gemini_direct",
        "model": GEMMA_MODEL, "thinkingLevel": GEMMA_THINKING,
        "temperature": GEMMA_TEMPERATURE, "maxOutputTokens": GEMMA_MAX_OUTPUT,
        "timeoutSeconds": GEMMA_TIMEOUT, "taskOrdinal": int(ordinal),
        "keyAssignment": "taskOrdinalMod10", "solverTools": False,
    })
    response = _minimal_request(prompt, key)
    raw = str(response.get("answer") or "")
    (out / "artifact" / "last_message.txt").write_text(raw, encoding="utf-8")
    try:
        code, parse_error = text_runner.extract_code(raw), None
    except (ValueError, SyntaxError) as exc:
        code, parse_error = "", type(exc).__name__
    duration = float(response.get("duration_seconds") or 0.0)
    over_budget = bool(response.get("overBudget")) or duration > GEMMA_TIMEOUT
    valid = (response.get("finishReason") == "STOP"
             and response.get("apiErrorStatus") is None
             and response.get("errorType") is None
             and response.get("modelVersionMatch") is True
             and response.get("nonTextItems", []) == []
             and not over_budget and parse_error is None)
    source = base.evaluation_source(row, code)
    report = base.evaluate(row, source) if valid else {"passed": False, "cases": {},
                                                        "fatal": "invalid Gemma response"}
    usage = response.get("usageMetadata")
    usage = usage if isinstance(usage, dict) else {}
    receipt = {
        "provider": "gemini_direct", "label": label, "model": GEMMA_MODEL,
        "thinkingLevel": GEMMA_THINKING, "temperature": GEMMA_TEMPERATURE,
        "maxOutputTokens": GEMMA_MAX_OUTPUT, "timeout_seconds": GEMMA_TIMEOUT,
        "duration_seconds": duration, "valid": valid, "sourceSafe": True,
        "nonTextItems": list(response.get("nonTextItems") or []),
        "overBudget": over_budget, "parseError": parse_error,
        "finishReason": response.get("finishReason"),
        "apiErrorStatus": response.get("apiErrorStatus"),
        "httpStatus": response.get("httpStatus"),
        "modelVersion": response.get("modelVersion"),
        "responseId": response.get("responseId"),
        "modelVersionMatch": response.get("modelVersionMatch"),
        "errorType": response.get("errorType"),
        "sourceSha": _sha_text(code), "usageMetadata": usage,
        "normalizedUsage": gemma_base._normalized_usage(usage),
        "taskOrdinal": int(ordinal), "keyAssignment": "taskOrdinalMod10",
    }
    base.write_json(out / "receipt.json", receipt)
    (out / "candidate.py").write_text(source, encoding="utf-8")
    base.write_json(out / "evaluation.json", report)
    return {"source": source, "report": report, "valid": valid,
            "path": out, "receipt": receipt, "cached": False}


def _keys(path: Path) -> list[str]:
    gemma_base.gemma_keyring._validate_private_file(Path(path).resolve())
    keys = gemma_base.gemma_keyring._parse_keys_file(Path(path).resolve())
    if len(keys) != GEMMA_KEY_COUNT:
        raise ValueError(f"exactly {GEMMA_KEY_COUNT} unique Gemma keys are required")
    return keys


def _key_for(keys: list[str], ordinal: int) -> str:
    if len(keys) != GEMMA_KEY_COUNT:
        raise ValueError("Gemma key pool size is not the approved fixed size")
    return keys[int(ordinal) % GEMMA_KEY_COUNT]


def _call_router(arm: str, e_cache: dict, screen_cache: dict, o_cache: dict,
                 keys: list[str], counters: dict, paths: dict[str, dict]) -> Callable:
    """Inject cached A/B and fresh C/B calls without changing frozen prompts."""

    def call(row: dict, out: Path, label: str, prompt: str) -> dict:
        task_id, suffix = row["task_id"], label.rsplit("-", 1)[-1]
        paths.setdefault(task_id, {})[suffix] = str(Path(out).resolve())
        if arm == "E":
            if suffix == "A":
                counters["cachedA"] += 1
                item = dict(e_cache["items"][task_id])
                _assert_cached_prompt(item["path"], prompt, "old E/A")
                paths[task_id]["A"] = str(Path(item["path"]).resolve())
                return item
            if suffix == "B":
                counters["cachedB"] += 1
                item = dict(screen_cache["items"][task_id])
                _assert_cached_prompt(item["path"], prompt, "minimal E/B")
                paths[task_id]["B"] = str(Path(item["path"]).resolve())
                return item
            if suffix == "C":
                counters["newLuna"] += 1
                item = text_runner.call(row, out, "E_C", prompt)
                counters["freshRawEval"] += int(item.get("valid") is True)
                return item
            raise ValueError(f"unexpected E call label: {label}")
        if arm == "O":
            if suffix == "A":
                counters["cachedA"] += 1
                item = dict(o_cache["items"][task_id])
                _assert_cached_prompt(item["path"], prompt, "graph O/A")
                paths[task_id]["A"] = str(Path(item["path"]).resolve())
                return item
            if suffix == "B":
                counters["newGemma"] += 1
                item = _gemma_call(row, out, "O_B", prompt,
                                   key=_key_for(keys, row["_data_index"]),
                                   ordinal=row["_data_index"])
                counters["freshRawEval"] += int(item.get("valid") is True)
                return item
            if suffix == "C":
                counters["newLuna"] += 1
                item = text_runner.call(row, out, "O_C", prompt)
                counters["freshRawEval"] += int(item.get("valid") is True)
                return item
            raise ValueError(f"unexpected O call label: {label}")
        raise ValueError(f"unknown arm: {arm}")

    return call


def _annotate(state: dict, arm: str, counters: dict, paths: dict[str, dict],
              task_id: str, *, executed: bool) -> dict:
    state = dict(state)
    cached = int(counters.get("cachedA", 0) + counters.get("cachedB", 0)) if executed else 0
    new = int(counters.get("newGemma", 0) + counters.get("newLuna", 0)) if executed else 0
    canonical_evals = int(state.get("canonicalEvalCalls", 0))
    fresh_raw = int(counters.get("freshRawEval", 0)) if executed else 0
    # The frozen arm state counts the evaluator calls made while projecting or
    # canonicalizing A/B/C.  Its rawEvalCalls field also counts cached
    # candidates as if their historical raw evaluation were current, so it is
    # deliberately not used for current-run cost accounting.  A fresh model
    # call has one additional raw evaluation when its candidate is valid.
    planned_cache_evals = cached
    state.update({
        "arm": arm, "logicalTailCalls": int(state.get("tailModelCalls", 0)),
        "newPhysicalModelCalls": new, "cachedCandidateCalls": cached,
        "plannedCacheVerificationEvalCalls": planned_cache_evals,
        "canonicalEvalCalls": canonical_evals,
        "freshRawCandidateEvalCalls": fresh_raw,
        "totalEvaluatorCalls": canonical_evals + fresh_raw,
        "evaluatorCallAccounting": (
            "totalEvaluatorCalls = actual canonicalEvalCalls in this arm "
            "+ freshRawCandidateEvalCalls; frozen rawEvalCalls includes "
            "historical raw validity for cached candidates"),
        "newGemmaCalls": int(counters.get("newGemma", 0)) if executed else 0,
        "newLunaCalls": int(counters.get("newLuna", 0)) if executed else 0,
        "callPaths": paths.get(task_id, state.get("callPaths", {})) if executed
                     else state.get("callPaths", {}),
    })
    return state


def _run_e(row: dict, prefix: dict, task_root: Path, *, call_fn: Callable | None,
           paths: dict[str, dict]) -> dict:
    labels, ordered, feedback, _ = _e_context(row, prefix)
    plans = scope_operator.build_scope_plans(ordered)
    if prefix["report"].get("passed"):
        state = frozen_tail._plan_result(prefix, plans, dry=False)["E"]
        return _annotate(state, "E", {}, paths, row["task_id"], executed=False)
    if call_fn is None:
        state = frozen_tail._plan_result(prefix, plans, dry=True)["E"]
        return _annotate(state, "E", {}, paths, row["task_id"], executed=False)
    state = frozen_tail._execute_arm(row, prefix, plans["E"], ordered, feedback,
                                     Path(task_root), call_fn, base.evaluate)
    return state


def _claim_run_root(run_root: Path, roots: tuple[Path, ...]) -> Path:
    run = Path(run_root).resolve()
    if any(run == root or run in root.parents or root in run.parents for root in roots):
        raise ValueError("paired run root must be a non-overlapping sibling")
    run.mkdir(parents=True, exist_ok=False)
    return run


def _contract(run_root: Path, parent_root: Path, e_root: Path, screen_root: Path,
              o_root: Path, rows: list[dict], prefixes: dict[str, dict],
              e_cache: dict, screen_cache: dict, o_cache: dict) -> dict:
    parent = Path(parent_root).resolve()
    return {
        "dataset": "classeval-pro", "taskIds": [row["task_id"] for row in rows],
        "dataSha": base.PRO_SHA, "runnerSha": base.sha(Path(__file__)),
        "protocolSha": base.sha(PROTOCOL), "evaluatorSha": base.sha(ROOT / "tools/classeval_isolated_evaluator.py"),
        "frozenTailSha": base.sha(Path(frozen_tail.__file__)),
        "graphRunnerSha": base.sha(Path(graph.__file__)),
        "gemmaTransportSha": base.sha(Path(gemma_base.__file__)),
        "textRunnerSha": base.sha(Path(text_runner.__file__)),
        "parentRoot": str(parent), "parentContractSha": base.sha(parent / "contract.json"),
        "parentResultSha": base.sha(parent / "result.json"),
        "oldECacheRoot": str(Path(e_root).resolve()),
        "oldECacheContractSha": e_cache["contractSha"], "oldECacheResultSha": e_cache["resultSha"],
        "screenRoot": str(Path(screen_root).resolve()),
        "screenContractSha": screen_cache["contractSha"], "screenResultSha": screen_cache["resultSha"],
        "oldOCacheRoot": str(Path(o_root).resolve()),
        "oldOCacheContractSha": o_cache["contractSha"], "oldOCacheResultSha": o_cache["resultSha"],
        "ordinaryPassed": 268, "fixedOrdinaryFailures": EXPECTED_FAILURES,
        "full300Required": True, "arms": ["E", "O"],
        "luna": {"model": LUNA_MODEL, "effort": LUNA_EFFORT, "timeoutSeconds": LUNA_TIMEOUT},
        "gemma": {"model": GEMMA_MODEL, "thinkingLevel": GEMMA_THINKING,
                   "temperature": GEMMA_TEMPERATURE, "maxOutputTokens": GEMMA_MAX_OUTPUT,
                   "timeoutSeconds": GEMMA_TIMEOUT, "noTools": True, "noRetry": True,
                   "keyAssignment": "task ordinal modulo 10"},
        "reuse": {"E": {"A": "old-E-cache/E/a", "B": "minimal-screen/E/b", "C": "fresh Luna"},
                  "O": {"A": "graph-O/O/a", "B": "fresh Gemma label O_B", "C": "fresh Luna"}},
        "logicalTailCallsPerArm": 3,
        "logicalTailCandidateSlots": {"perArm": 96, "total": 192},
        "logicalStudyCandidateSlots": {"Gemma": 64, "Luna": 128, "total": 192,
                                        "lunaCachedA": 64, "lunaFreshC": 64},
        "remainingPhysicalCalls": {"Gemma": 32, "Luna": 64, "total": 96},
        "combinedStudyPhysicalAccounting": {"Gemma": 64, "Luna": 64, "total": 128,
                                             "scope": "completed minimal screen plus remaining study; cached Luna A excluded"},
        "cacheVerificationEvaluationsPerU": {"E": 2, "O": 1},
        "plannedEvaluatorCalls": {"cacheVerification": 96, "freshRaw": 96,
                                   "freshCanonical": 96, "total": 288},
        "selection": "frozen tail selector and frozen E/O projection",
        "controlReferences": {"reusedLunaE": 278, "reusedLunaO": 278},
        "highScreenInitiatedCalls": 10, "nonBenchmarkSmokeCalls": 2,
        "prefixMap": {task_id: {"sourceSha": prefixes[task_id]["sourceSha"],
                                 "logicalPrefixCalls": prefixes[task_id]["logicalPrefixCalls"]}
                      for task_id in [row["task_id"] for row in rows]},
        "runRoot": str(Path(run_root).resolve()),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-root", required=True, type=Path)
    parser.add_argument("--e-cache-root", required=True, type=Path)
    parser.add_argument("--screen-root", required=True, type=Path)
    parser.add_argument("--o-cache-root", required=True, type=Path)
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--keys-file", type=Path, default=DEFAULT_KEYS_FILE)
    parser.add_argument("--execute", action="store_true",
                        help="enable exactly the approved fresh E_C/O_B/O_C calls")
    args = parser.parse_args(argv)
    rows = base.load_data("classeval-pro")
    if len(rows) != TOTAL_TASKS:
        raise ValueError("official full-300 inventory required")
    for ordinal, row in enumerate(rows):
        row["_data_index"] = ordinal
    ids = [row["task_id"] for row in rows]
    parent_root = Path(args.parent_root).resolve()
    prefixes = prefix_loader.load_ordinary_prefix(parent_root)
    _validate_parent(parent_root, rows, prefixes)
    e_root = Path(args.e_cache_root).resolve()
    e_cache = _validate_e_cache(e_root, parent_root, rows, prefixes)
    screen_cache = _validate_screen_cache(Path(args.screen_root), parent_root, e_root, rows, prefixes)
    o_cache = _validate_o_cache(Path(args.o_cache_root), parent_root, e_root, rows, prefixes)
    planned = {
        "ordinaryPassed": 268, "unresolved": EXPECTED_FAILURES,
        "logicalTailCallsPerArm": 3,
        "logicalTailCandidateSlots": {"perArm": 96, "total": 192},
        "logicalStudyCandidateSlots": {"Gemma": 64, "Luna": 128, "total": 192,
                                        "lunaCachedA": 64, "lunaFreshC": 64},
        "remainingPhysicalCalls": {"Gemma": 32, "Luna": 64, "total": 96},
        "combinedStudyPhysicalAccounting": {"Gemma": 64, "Luna": 64, "total": 128,
                                             "scope": "completed minimal screen plus remaining study; cached Luna A excluded"},
        "cacheVerificationEvaluations": {"E": EXPECTED_FAILURES * 2,
                                          "O": EXPECTED_FAILURES},
        "plannedEvaluatorCalls": {"cacheVerification": 96, "freshRaw": 96,
                                   "freshCanonical": 96, "total": 288},
    }
    if not args.execute:
        print(json.dumps({"mode": "dry-run", "dataset": "classeval-pro", "total": TOTAL_TASKS,
                          "cacheValidated": {"oldE_A": 32, "screenE_B": 32, "oldO_A": 32},
                          "planned": planned, "followup": "not run"}, ensure_ascii=False))
        return 0

    keys = _keys(args.keys_file)
    run_root = _claim_run_root(Path(args.run_root),
                               (parent_root, e_root, Path(args.screen_root).resolve(), o_cache["root"]))
    contract = _contract(run_root, parent_root, e_root, screen_cache["root"],
                         o_cache["root"], rows, prefixes, e_cache, screen_cache, o_cache)
    base.write_json(run_root / "contract.json", contract)
    unresolved = [task_id for task_id in ids if not prefixes[task_id]["report"].get("passed")]
    results: dict[str, dict] = {}
    try:
        for row in rows:
            task_id = row["task_id"]
            task_root = run_root / task_id
            if task_id not in unresolved:
                e_state = _run_e(row, prefixes[task_id], task_root, call_fn=None, paths={})
                o_state = graph.run_task(row, prefixes[task_id], task_root,
                                         call_fn=None, evaluate_fn=base.evaluate)
                o_state = _annotate(o_state, "O", {}, {}, task_id, executed=False)
            else:
                e_counters = {"cachedA": 0, "cachedB": 0, "newGemma": 0, "newLuna": 0,
                              "freshRawEval": 0}
                e_paths: dict[str, dict] = {}
                e_call = _call_router("E", e_cache, screen_cache, o_cache, [], e_counters, e_paths)
                e_state = _run_e(row, prefixes[task_id], task_root, call_fn=e_call, paths=e_paths)
                e_state = _annotate(e_state, "E", e_counters, e_paths, task_id, executed=True)
                o_counters = {"cachedA": 0, "cachedB": 0, "newGemma": 0, "newLuna": 0,
                              "freshRawEval": 0}
                o_paths: dict[str, dict] = {}
                o_call = _call_router("O", e_cache, screen_cache, o_cache, keys, o_counters, o_paths)
                o_state = graph.run_task(row, prefixes[task_id], task_root,
                                         call_fn=o_call, evaluate_fn=base.evaluate)
                o_state = _annotate(o_state, "O", o_counters, o_paths, task_id, executed=True)
            results[task_id] = {"E": e_state, "O": o_state}
            base.write_json(run_root / "progress.json", {
                "status": "running", "completed": len(results), "total": TOTAL_TASKS,
                "pairedCompleted": sum(task in unresolved for task in results),
                "tasks": results,
            })
            print(json.dumps({"taskId": task_id, "completed": len(results)}, ensure_ascii=False),
                  flush=True)
        base.write_json(run_root / "result.json", {
            "status": "complete", "completed": TOTAL_TASKS, "total": TOTAL_TASKS,
            "pairedTasks": EXPECTED_FAILURES, "screenOnly": False, "tasks": results,
            "remainingPhysicalCalls": {"Gemma": 32, "Luna": 64, "total": 96},
            "logicalStudyCandidateSlots": {"Gemma": 64, "Luna": 128, "total": 192,
                                            "lunaCachedA": 64, "lunaFreshC": 64},
            "combinedStudyPhysicalAccounting": {"Gemma": 64, "Luna": 64, "total": 128,
                                                 "scope": "completed minimal screen plus remaining study; cached Luna A excluded"},
        })
        return 0
    except Exception as exc:
        base.write_json(run_root / "error.json", {"type": type(exc).__name__,
                                                   "message": str(exc)[:500],
                                                   "completed": len(results)})
        base.write_json(run_root / "progress.json", {
            "status": "incomplete", "completed": len(results), "total": TOTAL_TASKS,
            "pairedCompleted": sum(task in unresolved for task in results), "tasks": results,
        })
        (run_root / "result.json").unlink(missing_ok=True)
        print(json.dumps({"status": "incomplete", "completed": len(results),
                          "errorType": type(exc).__name__}, ensure_ascii=False), flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
