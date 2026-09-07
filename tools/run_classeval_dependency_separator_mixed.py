"""E_B Gemma screen for a future mixed Luna/Gemma ClassEval development.

The screen is deliberately the only executable stage in this file.  It reads
the fixed ordinary full-300 prefix and cached E/A Luna artifacts, makes one
fresh Gemma call for each of U32, and records the predeclared gate.  It does
not run O, C, or any follow-up arm; a later runner may reuse the saved B
artifacts only after a separate approval.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any

from shared_platform import gemini_chat, gemma_keyring
from shared_platform.gemini_chat import GEMMA4_26B_MODEL, GeminiDirectChatClient
from tools import classeval_ordinary_prefix as prefix_loader
from tools import run_classeval_overlap_repair_tail as frozen_tail
from tools import run_classeval_source_overlap as base
from tools import run_classeval_text_overlap as text_runner
from tools import overlap_split_merge_candidate as scope_operator


ROOT = base.ROOT
PROTOCOL = ROOT / "experiment_protocols/2026-09-05-classeval-dependency-separator-mixed-v1.md"
TOTAL_TASKS = 300
EXPECTED_FAILURES = 32
GEMMA_MODEL = GEMMA4_26B_MODEL
GEMMA_TIMEOUT = 120
GEMMA_TEMPERATURE = 0.6
GEMMA_MAX_OUTPUT = 16_384
GEMMA_THINKING_LEVEL = "high"
GEMMA_KEY_COUNT = 10
DEFAULT_KEYS_FILE = Path("/home/pineapple/bunjum2/work27/yt-predict/gemini_keys.txt")


def _json(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _failure(message: str) -> dict:
    return {"passed": False, "cases": {}, "fatal": message}


def _inside(root: Path, path: Path) -> Path:
    root, resolved = Path(root).resolve(), Path(path).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("cached artifact path escapes cache root") from exc
    return resolved


def _validate_e_cache(cache_root: Path, parent_root: Path, rows: list[dict],
                      prefixes: dict[str, dict]) -> dict[str, Any]:
    """Read-only validation and loading of the old E/A Luna cache for U32."""
    root = Path(cache_root).resolve()
    contract_path, result_path = root / "contract.json", root / "result.json"
    contract, result = _json(contract_path), _json(result_path)
    ids = [row["task_id"] for row in rows]
    expected_contract = frozen_tail._build_contract(root, parent_root, rows, prefixes)
    if contract != expected_contract:
        raise ValueError("E cache contract differs from the frozen tail contract")
    if (result.get("status") != "complete"
            or result.get("completed") != TOTAL_TASKS
            or result.get("total") != TOTAL_TASKS
            or list(result.get("tasks", {})) != ids):
        raise ValueError("completed full300 E cache required")

    items, states = {}, {}
    for row in rows:
        task_id = row["task_id"]
        if prefixes[task_id]["report"].get("passed"):
            continue
        state = result["tasks"].get(task_id, {}).get("E")
        if not isinstance(state, dict) or state.get("status") != "executed":
            raise ValueError(f"missing executed E cache state: {task_id}")
        call_paths = state.get("callPaths")
        expected = root / task_id / "E" / "a"
        # The old E/D/O tail predates per-arm callPaths in its terminal state;
        # its deterministic artifact layout is still hash-bound below by the
        # read-only prefix loader.  If a newer state supplies the path, check it.
        if (isinstance(call_paths, dict) and "A" in call_paths
                and _inside(root, Path(call_paths["A"])) != expected.resolve()):
            raise ValueError(f"cached E/A path mismatch: {task_id}")
        labels, ordered, feedback, _ = _e_context(row, prefixes[task_id])
        plan = scope_operator.build_scope_plans(ordered)["E"]
        prompt_a = frozen_tail._independent_prompt(
            row, prefixes[task_id], plan, "A", ordered, feedback)
        prompt_b = frozen_tail._independent_prompt(
            row, prefixes[task_id], plan, "B", ordered, feedback)
        item = prefix_loader._call(row, expected, "tail-E-A", prompt_a)
        prefix_loader._call(row, root / task_id / "E" / "b", "tail-E-B", prompt_b)
        if item.get("valid") is not True:
            raise ValueError(f"cached E/A is invalid: {task_id}")
        items[task_id], states[task_id] = item, state
    if len(items) != EXPECTED_FAILURES:
        raise ValueError("E/A cache must cover exactly U32")
    return {"root": root, "contract": contract, "result": result,
            "contractSha": base.sha(contract_path), "resultSha": base.sha(result_path),
            "items": items, "states": states}


def _e_context(row: dict, prefix: dict) -> tuple[tuple[str, ...], tuple[str, ...], dict, dict | None]:
    """Reproduce the frozen E prompt inputs byte-for-byte."""
    labels = frozen_tail.target_method_labels(row, prefix["source"]) or ("whole_program",)
    ordered, anchor_hint = frozen_tail.choose_failure_anchor(labels, prefix["report"])
    feedback = frozen_tail.observed_feedback(prefix["report"], ordered)
    feedback["bridgeHint"] = anchor_hint
    return labels, ordered, feedback, anchor_hint


def _load_execute_keys(keys_file: Path) -> list[str]:
    """Load the approved private pool only on explicit execution."""
    path = Path(keys_file).expanduser().resolve()
    gemma_keyring._validate_private_file(path)
    keys = gemma_keyring._parse_keys_file(path)
    if len(keys) != GEMMA_KEY_COUNT:
        raise ValueError(f"exactly {GEMMA_KEY_COUNT} unique Gemma keys are required")
    return keys


def _key_for_ordinal(keys: list[str], ordinal: int) -> str:
    if len(keys) != GEMMA_KEY_COUNT:
        raise ValueError("Gemma key pool size is not the approved fixed size")
    return keys[int(ordinal) % GEMMA_KEY_COUNT]


def _gemma_payload(prompt: str) -> dict[str, Any]:
    """Build one user request without the existing client's 12k text trim."""
    return {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": GEMMA_TEMPERATURE,
            "maxOutputTokens": GEMMA_MAX_OUTPUT,
            "thinkingConfig": {"thinkingLevel": GEMMA_THINKING_LEVEL},
        },
    }


def _http_status(exc: Exception) -> int | None:
    match = re.search(r"HTTP (\d{3})", str(exc))
    return int(match.group(1)) if match else None


def _gemma_request(prompt: str, key: str) -> dict[str, Any]:
    """Make exactly one request, returning only redacted metadata."""
    client = GeminiDirectChatClient(api_key=key, timeout_seconds=GEMMA_TIMEOUT,
                                    default_model=GEMMA_MODEL)
    started = time.monotonic()
    try:
        # The public helper clamps maxOutputTokens to 4096 and hides
        # finishReason; use its existing transport with this protocol's
        # explicit 16384/high request, without changing shared provider code.
        parsed = client._post_generate_content(GEMMA_MODEL, _gemma_payload(prompt))
        candidates = parsed.get("candidates") or []
        candidate = candidates[0] if candidates and isinstance(candidates[0], dict) else {}
        finish_reason = candidate.get("finishReason")
        model_version = parsed.get("modelVersion")
        response_id = parsed.get("responseId")
        model_match = (model_version == GEMMA_MODEL) if model_version is not None else None
        model_error = (None if model_match is True else
                       "ModelVersionMismatch" if model_match is False else "ModelVersionMissing")
        non_text_items = _non_text_items(parsed)
        non_text_error = "NonTextResponse" if non_text_items else None
        try:
            answer = gemini_chat._extract_text(parsed)
            extract_error = None
        except Exception as exc:
            answer, extract_error = "", type(exc).__name__
        return {"answer": answer, "finishReason": finish_reason,
                "usageMetadata": parsed.get("usageMetadata") or {},
                "duration_seconds": time.monotonic() - started,
                "apiErrorStatus": None, "httpStatus": 200,
                "modelVersion": model_version, "responseId": response_id,
                "modelVersionMatch": model_match,
                "nonTextItems": non_text_items,
                "overBudget": (time.monotonic() - started) > GEMMA_TIMEOUT,
                "errorType": model_error or non_text_error or extract_error}
    except Exception as exc:
        return {"answer": "", "finishReason": None, "usageMetadata": {},
                "duration_seconds": time.monotonic() - started,
                "apiErrorStatus": _http_status(exc), "httpStatus": _http_status(exc),
                "modelVersion": None, "responseId": None,
                "modelVersionMatch": None, "nonTextItems": [], "overBudget": False,
                "errorType": type(exc).__name__}


def _non_text_items(parsed: dict[str, Any]) -> list[str]:
    """List executable/non-text response parts while ignoring thoughts/text."""
    names = ("functionCall", "inlineData", "executableCode", "codeExecutionResult")
    found: list[str] = []
    for candidate in parsed.get("candidates") or []:
        if not isinstance(candidate, dict):
            continue
        content = candidate.get("content") or {}
        for part in content.get("parts") or []:
            if not isinstance(part, dict):
                continue
            for name in names:
                if name in part:
                    found.append(name)
    return found


def _normalized_usage(metadata: dict[str, Any]) -> dict[str, int]:
    fields = ("promptTokenCount", "candidatesTokenCount",
              "thoughtsTokenCount", "totalTokenCount")
    return {field: int(metadata[field]) for field in fields
            if isinstance(metadata.get(field), (int, float))
            and not isinstance(metadata.get(field), bool)}


def _gemma_call(row: dict, out: Path, prompt: str, *, key: str, ordinal: int) -> dict:
    """Gemma B call with the existing code extraction/evaluator contract."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    work, artifact = out / "work", out / "artifact"
    work.mkdir()
    artifact.mkdir()
    (out / "prompt.txt").write_text(prompt, encoding="utf-8")
    base.write_json(out / "contract.json", {
        "taskId": row["task_id"], "label": "mixed-E-B", "dataSha": base.PRO_SHA,
        "promptSha": hashlib.sha256(prompt.encode()).hexdigest(),
        "provider": "gemini_direct", "model": GEMMA_MODEL,
        "thinkingLevel": GEMMA_THINKING_LEVEL, "temperature": GEMMA_TEMPERATURE,
        "maxOutputTokens": GEMMA_MAX_OUTPUT, "timeoutSeconds": GEMMA_TIMEOUT,
        "taskOrdinal": int(ordinal), "keyAssignment": "taskOrdinalMod10",
        "solverTools": False,
    })
    response = _gemma_request(prompt, key)
    raw = str(response.get("answer") or "")
    (artifact / "last_message.txt").write_text(raw, encoding="utf-8")
    try:
        code = text_runner.extract_code(raw)
        parse_error = None
    except (ValueError, SyntaxError) as exc:
        code, parse_error = "", type(exc).__name__
    duration_seconds = float(response.get("duration_seconds") or 0.0)
    over_budget = bool(response.get("overBudget")) or duration_seconds > GEMMA_TIMEOUT
    valid = (response.get("finishReason") == "STOP"
             and response.get("apiErrorStatus") is None
             and response.get("errorType") is None
             and response.get("modelVersionMatch") is True
             and response.get("nonTextItems", []) == []
             and not over_budget
             and parse_error is None)
    source = base.evaluation_source(row, code)
    report = base.evaluate(row, source) if valid else _failure("invalid Gemma response")
    usage = response.get("usageMetadata")
    if not isinstance(usage, dict):
        usage = {}
    receipt = {
        "provider": "gemini_direct", "model": GEMMA_MODEL,
        "thinkingLevel": GEMMA_THINKING_LEVEL, "temperature": GEMMA_TEMPERATURE,
        "maxOutputTokens": GEMMA_MAX_OUTPUT, "timeout_seconds": GEMMA_TIMEOUT,
        "duration_seconds": duration_seconds,
        "valid": valid, "sourceSafe": True,
        "nonTextItems": list(response.get("nonTextItems") or []),
        "overBudget": over_budget,
        "parseError": parse_error, "finishReason": response.get("finishReason"),
        "apiErrorStatus": response.get("apiErrorStatus"),
        "httpStatus": response.get("httpStatus"),
        "modelVersion": response.get("modelVersion"),
        "responseId": response.get("responseId"),
        "modelVersionMatch": response.get("modelVersionMatch"),
        "errorType": response.get("errorType"),
        "sourceSha": hashlib.sha256(code.encode()).hexdigest(),
        "usageMetadata": usage, "normalizedUsage": _normalized_usage(usage),
        "taskOrdinal": int(ordinal), "keyAssignment": "taskOrdinalMod10",
    }
    base.write_json(out / "receipt.json", receipt)
    (out / "candidate.py").write_text(source, encoding="utf-8")
    base.write_json(out / "evaluation.json", report)
    return {"source": source, "report": report, "valid": valid, "path": out,
            "receipt": receipt, "cached": False}


def _screen_gate(records: list[dict]) -> dict[str, Any]:
    usable = sum(bool(item["usable"]) for item in records)
    # A novelty witness is meaningful only for a structurally usable response;
    # invalid transport/parse outputs cannot satisfy the continuation gate.
    novel = sum(bool(item["usable"] and item["novelCaseTask"]) for item in records)
    whole = sum(bool(item["usable"] and item["newWholePassVsOldE"]) for item in records)
    proceed = usable >= 24 and (novel >= 1 or whole >= 1)
    return {"attempted": len(records), "expected": EXPECTED_FAILURES,
            "usableB": usable, "novelCaseTasks": novel,
            "newWholePassVsOldE": whole, "proceed": proceed,
            "rule": "usableB>=24 AND (novelCaseTasks>=1 OR newWholePassVsOldE>=1)"}


def _screen_record(row: dict, prefix: dict, cache: dict, ordinal: int,
                   run_root: Path, keys: list[str]) -> dict:
    labels, ordered, feedback, anchor_hint = _e_context(row, prefix)
    plan = scope_operator.build_scope_plans(ordered)["E"]
    task_id = row["task_id"]
    a = cache["items"][task_id]
    a_view = frozen_tail._full_view(row, prefix, a, base.evaluate)
    prompt = frozen_tail._independent_prompt(row, prefix, plan, "B", ordered, feedback)
    b = _gemma_call(row, run_root / task_id / "E" / "b", prompt,
                    key=_key_for_ordinal(keys, ordinal), ordinal=ordinal)
    b_view = frozen_tail._full_view(row, prefix, b, base.evaluate)
    a_report, b_report = a_view[1], b_view[1]
    novel_case_ids = [str(case_id) for case_id, item in b_report.get("cases", {}).items()
                      if item.get("status") == "passed"
                      and a_report.get("cases", {}).get(case_id, {}).get("status") != "passed"
                      and prefix["report"].get("cases", {}).get(case_id, {}).get("status") != "passed"]
    old_e_report = cache["states"][task_id].get("report", _failure("missing old E report"))
    return {
        "taskId": task_id, "ordinal": ordinal, "sourceSha": b.get("receipt", {}).get("sourceSha"),
        "promptSha": hashlib.sha256(prompt.encode()).hexdigest(),
        "aCachePath": str(Path(a["path"]).resolve()),
        "bPath": str(Path(b["path"]).resolve()), "bReport": b_view[1],
        "bValid": bool(b.get("valid") is True),
        "usable": bool(b.get("valid") is True and b_view[2] is True),
        "novelCaseIds": novel_case_ids, "novelCaseTask": bool(novel_case_ids),
        "newWholePassVsOldE": bool(b_view[1].get("passed") and not old_e_report.get("passed")),
        "rawBEvalCalls": int(b.get("valid") is True),
        "cachedACanonicalEvalCalls": int(a_view[3]),
        "bCanonicalEvalCalls": int(b_view[3]),
        "canonicalEvalCalls": int(a_view[3] + b_view[3]),
        "anchorHint": anchor_hint,
    }


def _build_contract(run_root: Path, parent_root: Path, cache: dict,
                    rows: list[dict], prefixes: dict[str, dict]) -> dict:
    return {
        "dataset": "classeval-pro", "taskIds": [row["task_id"] for row in rows],
        "dataSha": base.PRO_SHA, "runnerSha": base.sha(Path(__file__)),
        "protocolSha": base.sha(PROTOCOL), "evaluatorSha": base.sha(ROOT / "tools/classeval_isolated_evaluator.py"),
        "frozenTailSha": base.sha(Path(frozen_tail.__file__)),
        "textRunnerSha": base.sha(Path(text_runner.__file__)),
        "parentRoot": str(Path(parent_root).resolve()),
        "parentContractSha": base.sha(Path(parent_root) / "contract.json"),
        "parentResultSha": base.sha(Path(parent_root) / "result.json"),
        "eCacheRoot": str(cache["root"]), "eCacheContractSha": cache["contractSha"],
        "eCacheResultSha": cache["resultSha"], "ordinaryPassed": 268,
        "fixedOrdinaryFailures": EXPECTED_FAILURES, "screenArm": "E",
        "screenModelCalls": EXPECTED_FAILURES, "model": GEMMA_MODEL,
        "thinkingLevel": GEMMA_THINKING_LEVEL, "temperature": GEMMA_TEMPERATURE,
        "maxOutputTokens": GEMMA_MAX_OUTPUT, "timeoutSeconds": GEMMA_TIMEOUT,
        "noRetry": True, "keyAssignment": "official task ordinal modulo 10",
        "projection": "frozen_tail._full_view", "selection": "screen-only; no final arm selection",
        "full300Required": True, "followup": "not implemented or authorized by this runner",
        "prefixMap": {task_id: {"sourceSha": prefixes[task_id]["sourceSha"],
                                 "logicalPrefixCalls": prefixes[task_id]["logicalPrefixCalls"]}
                      for task_id in (row["task_id"] for row in rows)},
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-root", required=True, type=Path)
    parser.add_argument("--e-cache-root", required=True, type=Path)
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--keys-file", type=Path, default=DEFAULT_KEYS_FILE)
    parser.add_argument("--execute", action="store_true",
                        help="enable exactly the 32 Gemma E_B screen calls")
    args = parser.parse_args(argv)
    rows = base.load_data("classeval-pro")
    ids = [row["task_id"] for row in rows]
    parent_root = args.parent_root.resolve()
    prefixes = prefix_loader.load_ordinary_prefix(parent_root)
    if len(rows) != TOTAL_TASKS or list(prefixes) != ids:
        raise ValueError("full300 ordinary prefix is required")
    unresolved = [task_id for task_id in ids if not prefixes[task_id]["report"].get("passed")]
    if len(unresolved) != EXPECTED_FAILURES:
        raise ValueError("ordinary prefix must contain exactly U32")
    cache = _validate_e_cache(args.e_cache_root, parent_root, rows, prefixes)
    if not args.execute:
        print(json.dumps({"mode": "dry-run", "dataset": "classeval-pro", "total": TOTAL_TASKS,
                          "ordinaryPassed": 268, "unresolved": EXPECTED_FAILURES,
                          "eCacheValidated": True, "plannedGemmaScreenCalls": EXPECTED_FAILURES,
                          "followup": "not run"}, ensure_ascii=False))
        return 0

    keys = _load_execute_keys(args.keys_file)
    run_root = Path(args.run_root).resolve()
    if run_root == parent_root or run_root in parent_root.parents or parent_root in run_root.parents:
        raise ValueError("screen run root must be a non-overlapping sibling")
    if run_root == cache["root"] or run_root in cache["root"].parents or cache["root"] in run_root.parents:
        raise ValueError("screen run root must not overlap E cache")
    run_root.mkdir(parents=True, exist_ok=False)
    base.write_json(run_root / "contract.json",
                    _build_contract(run_root, parent_root, cache, rows, prefixes))
    ordinal_by_id = {task_id: ordinal for ordinal, task_id in enumerate(ids)}
    records: list[dict] = []
    try:
        for task_id in unresolved:
            row = next(row for row in rows if row["task_id"] == task_id)
            record = _screen_record(row, prefixes[task_id], cache,
                                    ordinal_by_id[task_id], run_root, keys)
            records.append(record)
            base.write_json(run_root / "progress.json", {
                "status": "screening", "screenCompleted": len(records),
                "screenTotal": EXPECTED_FAILURES, "total": TOTAL_TASKS,
                "taskIds": [item["taskId"] for item in records],
            })
        gate = _screen_gate(records)
        if gate["attempted"] != EXPECTED_FAILURES:
            raise ValueError("all U32 screen calls must be accounted")
        result = {"status": "screen-complete", "screenOnly": True,
                  "completed": TOTAL_TASKS, "total": TOTAL_TASKS,
                  "screenCompleted": EXPECTED_FAILURES,
                  "statusMap": {
                      task_id: ("stopped" if prefixes[task_id]["report"].get("passed")
                                else "screened") for task_id in ids
                  },
                  "gate": gate, "freshGemmaCalls": EXPECTED_FAILURES,
                  "freshLunaCalls": 0, "followup": "not run", "tasks": records}
        base.write_json(run_root / "progress.json", result)
        base.write_json(run_root / "result.json", result)
        print(json.dumps({"status": "screen-complete", "gate": gate,
                          "freshGemmaCalls": EXPECTED_FAILURES}, ensure_ascii=False), flush=True)
        return 0
    except Exception as exc:
        base.write_json(run_root / "error.json", {"type": type(exc).__name__,
                                                   "message": str(exc)[:500],
                                                   "screenCompleted": len(records)})
        print(json.dumps({"status": "incomplete", "errorType": type(exc).__name__,
                          "screenCompleted": len(records)}, ensure_ascii=False), flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
