"""Read-only loader for a completed text-runner ordinary A/B/R prefix.

The production entry loads the official 300-task inventory and never writes,
calls a model/evaluator, reads auth, or follows generic/overlap artifacts.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tools import run_classeval_source_overlap as base
from tools import run_classeval_text_overlap as text_runner

MODEL, EFFORT, TIMEOUT = "gpt-5.6-luna", "medium", 120


def _json(path: Path) -> dict:
    return json.loads(path.read_text())


def _sha_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _inventory(rows: list[dict], official: bool) -> list[str]:
    ids = [row["task_id"] for row in rows]
    if len(ids) != len(set(ids)) or (official and len(ids) != 300):
        raise ValueError("exact official 300-task inventory required")
    return ids


def _parent_state(root: Path, ids: list[str], official: bool) -> tuple[dict, dict, dict]:
    contract, result = _json(root / "contract.json"), _json(root / "result.json")
    total = 300 if official else len(ids)
    expected = {
        "dataset": "classeval-pro", "dataSha": base.PRO_SHA, "taskIds": ids,
        "runnerSha": base.sha(Path(text_runner.__file__)),
        "protocolSha": base.sha(text_runner.PROTOCOL),
        "operatorSha": base.sha(Path(text_runner.union.__file__)),
        "baseRunnerSha": base.sha(Path(base.__file__)),
        "evaluatorSha": base.sha(base.ROOT / "tools/classeval_isolated_evaluator.py"),
        "model": MODEL, "effort": EFFORT, "timeoutSeconds": TIMEOUT,
    }
    if (any(contract.get(key) != value for key, value in expected.items())
            or result.get("completed") != total or result.get("total") != total
            or list(result.get("tasks", {})) != ids):
        raise ValueError("terminal complete official parent required")
    return contract, result, result["tasks"]


def _call(row: dict, directory: Path, label: str, expected_prompt: str | None = None) -> dict:
    contract = _json(directory / "contract.json")
    prompt_path, receipt_path = directory / "prompt.txt", directory / "receipt.json"
    prompt = prompt_path.read_text()
    expected = {"taskId": row["task_id"], "label": label, "dataSha": base.PRO_SHA,
                "model": MODEL, "effort": EFFORT, "timeoutSeconds": TIMEOUT,
                "solverTools": False}
    if any(contract.get(key) != value for key, value in expected.items()):
        raise ValueError(f"call contract mismatch: {directory}")
    if contract.get("promptSha") != _sha_text(prompt):
        raise ValueError(f"stored prompt hash mismatch: {directory}")
    if expected_prompt is not None:
        if prompt != expected_prompt or contract["promptSha"] != _sha_text(expected_prompt):
            raise ValueError(f"expected prompt mismatch: {directory}")
    receipt, report = _json(receipt_path), _json(directory / "evaluation.json")
    if not isinstance(receipt.get("valid"), bool) or not isinstance(report.get("passed"), bool):
        raise ValueError(f"invalid call receipt/report: {directory}")
    if receipt["valid"] and not (
            receipt.get("exit_code") == 0
            and receipt.get("timed_out") is False
            and receipt.get("sourceSafe") is True
            and receipt.get("nonTextItems") == []
            and "parseError" in receipt
            and receipt.get("parseError") in (None, "")):
        raise ValueError(f"valid receipt execution fields mismatch: {directory}")
    last_path = directory / "artifact" / "last_message.txt"
    raw = last_path.read_text() if last_path.is_file() else ""
    try:
        raw_source = text_runner.extract_code(raw)
    except (ValueError, SyntaxError):
        raw_source = ""
    if receipt.get("sourceSha") != _sha_text(raw_source):
        raise ValueError(f"raw source hash mismatch: {directory}")
    candidate = (directory / "candidate.py").read_text()
    if candidate != base.evaluation_source(row, raw_source):
        raise ValueError(f"candidate source transformation mismatch: {directory}")
    if not receipt["valid"] and report["passed"]:
        raise ValueError(f"invalid model response cannot pass: {directory}")
    return {"source": candidate, "report": report, "valid": receipt["valid"], "path": directory}


def _rank(item: dict) -> tuple[bool, int]:
    report = item["report"]
    return bool(report["passed"]), sum(case.get("status") == "passed"
                                       for case in report.get("cases", {}).values())


def _task(row: dict, root: Path, task_state: dict) -> dict:
    task_root = root / row["task_id"]
    a_dir, b_dir = task_root / "a", task_root / "b"
    parent_prompt = text_runner.GENERATE.format(skeleton=row["skeleton"])
    a = _call(row, a_dir, "a", parent_prompt)
    parents = [a]
    if a["report"]["passed"]:
        if b_dir.exists():
            raise ValueError("B must be omitted when A passes")
    else:
        if not b_dir.is_dir():
            raise ValueError("B is required after an A failure")
        parents.append(_call(row, b_dir, "b", parent_prompt))
    if task_state.get("parentCalls") != len(parents):
        raise ValueError("parent call count mismatch")
    physical = task_state.get("repairPhysicalCalls")
    if not isinstance(physical, int) or physical < 0:
        raise ValueError("shared physical repair count missing")
    seed = max(parents, key=_rank)  # stable A-first tie break.
    if seed["report"]["passed"]:
        if physical != 0:
            raise ValueError("passing ordinary seed requires zero physical repairs")
    elif physical not in (1, 2, 3):
        raise ValueError("failing ordinary seed requires one to three physical repairs")
    final_dir = task_root / "ordinary-final"
    final_info, final_report = _json(final_dir / "result.json"), _json(final_dir / "evaluation.json")
    if task_state.get("ordinaryFinal") != final_report.get("passed"):
        raise ValueError("ordinary final outcome mismatch")
    call_paths = {"a": str(a_dir)}
    if len(parents) == 2:
        call_paths["b"] = str(b_dir)
    if seed["report"]["passed"]:
        if final_info.get("repairFrom") not in (None, ""):
            raise ValueError("passing ordinary seed must not name an R call")
        selected_source, selected_report, selected_label = seed["source"], seed["report"], "verified_seed"
        expected_repair_calls = 0
    else:
        repair_name = final_info.get("repairFrom")
        if repair_name != "repair-0":
            raise ValueError("ordinary failure requires the frozen repair-0 artifact")
        repair_dir = task_root / repair_name
        expected_prompt = text_runner.repair_prompt(row, parents, seed)
        r = _call(row, repair_dir, "ordinary_repair", expected_prompt)
        selected_source, selected_report, selected_label = text_runner.select_final(
            seed["source"], seed["report"], r["source"], r["report"])
        call_paths["r"] = str(repair_dir)
        expected_repair_calls = 1
    if (final_dir / "selected.py").read_text() != selected_source or final_report != selected_report:
        raise ValueError("ordinary-final source/report differs from select_final")
    if (final_info.get("selected") != selected_label or
            final_info.get("passed") != selected_report["passed"] or
            final_info.get("logicalRepairCalls") != expected_repair_calls):
        raise ValueError("ordinary-final selection metadata mismatch")
    call_count = len(parents) + expected_repair_calls
    if call_count not in (1, 2, 3):
        raise ValueError("logical ordinary prefix must contain 1..3 calls")
    return {"taskId": row["task_id"], "source": selected_source, "report": selected_report,
            "seed": "a" if seed is a else "b", "callPaths": call_paths,
            "logicalPrefixCalls": call_count, "sourceSha": _sha_text(selected_source),
            "sharedPhysicalRepairCalls": physical}


def _load_rows(parent_root: Path, rows: list[dict], *, official: bool = False) -> dict[str, dict]:
    """Pure artifact reader used by tests with toy rows; production uses official=True."""
    ids = _inventory(rows, official)
    root = Path(parent_root).resolve()
    _, _, tasks = _parent_state(root, ids, official)
    return {row["task_id"]: _task(row, root, tasks[row["task_id"]]) for row in rows}


def load_ordinary_prefix(parent_root: Path) -> dict[str, dict]:
    """Load all 300 ordinary prefixes; never writes or invokes a runtime."""
    rows = base.load_data("classeval-pro")
    _inventory(rows, official=True)
    return _load_rows(Path(parent_root), rows, official=True)
