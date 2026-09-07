"""Toy artifact tests for routing/receipt validation, not performance evidence."""

import hashlib
import json
from pathlib import Path

import pytest

from tools import run_classeval_source_overlap as base
from tools import run_classeval_text_overlap as text_runner
from tools import classeval_ordinary_prefix as loader


def _row(task_id="ClassEval_0"):
    return {"task_id": task_id, "_dataset": "classeval-pro",
            "skeleton": "class Toy:\n    def f(self):\n        return 0\n"}


def _report(passed):
    return {"passed": passed, "expectedCount": 1, "fatal": None if passed else "failure",
            "cases": {"case": {"status": "passed" if passed else "failed", "message": "m"}}}


def _write_json(path, value):
    path.write_text(json.dumps(value) + "\n")


def _write_call(task_root, row, name, source, report, valid=True, prompt="prompt"):
    directory = task_root / name
    (directory / "artifact").mkdir(parents=True)
    raw = source if valid else "not valid python"
    code = source if valid else ""
    candidate = base.evaluation_source(row, code)
    (directory / "prompt.txt").write_text(prompt)
    _write_json(directory / "contract.json", {
        "taskId": row["task_id"], "label": "ordinary_repair" if name.startswith("repair-") else name,
        "dataSha": base.PRO_SHA, "promptSha": hashlib.sha256(prompt.encode()).hexdigest(),
        "model": "gpt-5.6-luna", "effort": "medium", "timeoutSeconds": 120,
        "solverTools": False})
    (directory / "artifact" / "last_message.txt").write_text(raw)
    _write_json(directory / "receipt.json", {"valid": valid,
        "exit_code": 0 if valid else 1, "timed_out": False,
        "sourceSafe": valid, "nonTextItems": [], "parseError": None if valid else "invalid",
        "sourceSha": hashlib.sha256(code.encode()).hexdigest()})
    (directory / "candidate.py").write_text(candidate)
    _write_json(directory / "evaluation.json", report)
    return directory


def _make_parent(tmp_path, mode="a", *, physical=None, rows=None):
    if physical is None:
        physical = 1 if mode == "r" else 0
    rows = rows or [_row()]
    root = tmp_path / "parent"
    root.mkdir()
    result_tasks = {}
    for row in rows:
        task_root = root / row["task_id"]
        task_root.mkdir()
        a_source = "class Toy:\n    def f(self):\n        return 1\n"
        a_pass = mode == "a"
        parent_prompt = text_runner.GENERATE.format(skeleton=row["skeleton"])
        _write_call(task_root, row, "a", a_source, _report(a_pass), valid=True, prompt=parent_prompt)
        parents = [{"source": base.evaluation_source(row, a_source), "report": _report(a_pass), "valid": True}]
        if mode in {"b", "r"}:
            b_source = "class Toy:\n    def f(self):\n        return 2\n"
            b_pass = mode == "b"
            _write_call(task_root, row, "b", b_source, _report(b_pass), valid=True, prompt=parent_prompt)
            parents.append({"source": base.evaluation_source(row, b_source), "report": _report(b_pass), "valid": True})
        seed = max(parents, key=lambda p: (p["report"]["passed"],
                                            sum(c["status"] == "passed" for c in p["report"]["cases"].values())))
        repair_from = None
        if mode == "r":
            expected_prompt = text_runner.repair_prompt(row, parents, seed)
            r_source = "class Toy:\n    def f(self):\n        return 3\n"
            _write_call(task_root, row, "repair-0", r_source, _report(True), valid=True, prompt=expected_prompt)
            selected_source, selected_report, selected = text_runner.select_final(
                seed["source"], seed["report"], base.evaluation_source(row, r_source), _report(True))
            repair_from = "repair-0"
        else:
            selected_source, selected_report, selected = seed["source"], seed["report"], "verified_seed"
        final = task_root / "ordinary-final"
        final.mkdir()
        (final / "selected.py").write_text(selected_source)
        _write_json(final / "evaluation.json", selected_report)
        _write_json(final / "result.json", {"passed": selected_report["passed"], "selected": selected,
            "repairFrom": repair_from, "logicalRepairCalls": int(repair_from is not None)})
        result_tasks[row["task_id"]] = {"ordinaryFinal": selected_report["passed"],
            "parentCalls": len(parents), "repairPhysicalCalls": physical}
    ids = [r["task_id"] for r in rows]
    _write_json(root / "contract.json", {
        "dataset": "classeval-pro", "dataSha": base.PRO_SHA, "taskIds": ids,
        "runnerSha": base.sha(Path(text_runner.__file__)),
        "protocolSha": base.sha(text_runner.PROTOCOL),
        "operatorSha": base.sha(Path(text_runner.union.__file__)),
        "baseRunnerSha": base.sha(Path(base.__file__)),
        "evaluatorSha": base.sha(base.ROOT / "tools/classeval_isolated_evaluator.py"),
        "model": "gpt-5.6-luna", "effort": "medium", "timeoutSeconds": 120})
    _write_json(root / "result.json", {"completed": len(ids), "total": len(ids), "tasks": result_tasks})
    return root


def test_production_entry_requires_exact_300(monkeypatch, tmp_path):
    monkeypatch.setattr(loader.base, "load_data", lambda _: [_row()])
    with pytest.raises(ValueError, match="300"):
        loader.load_ordinary_prefix(tmp_path)


def test_incomplete_parent_is_rejected(tmp_path):
    root = _make_parent(tmp_path, rows=[_row("ClassEval_0"), _row("ClassEval_1")])
    result = loader._json(root / "result.json")
    result["completed"], result["total"] = 1, 2
    result["tasks"].pop("ClassEval_1")
    _write_json(root / "result.json", result)
    with pytest.raises(ValueError, match="terminal"):
        loader._load_rows(root, [_row("ClassEval_0"), _row("ClassEval_1")])


@pytest.mark.parametrize(("mode", "expected", "physical"),
                         [("a", 1, 0), ("b", 2, 0), ("r", 3, 1), ("r", 3, 2), ("r", 3, 3)])
def test_ordinary_a_b_r_prefix_call_distinction(tmp_path, mode, expected, physical):
    root = _make_parent(tmp_path, mode, physical=physical)
    loaded = loader._load_rows(root, [_row()])["ClassEval_0"]
    assert loaded["logicalPrefixCalls"] == expected
    assert loaded["sharedPhysicalRepairCalls"] == physical
    assert ("r" in loaded["callPaths"]) is (mode == "r")


def test_invalid_model_receipt_is_retained_as_failure(tmp_path):
    root = _make_parent(tmp_path, "b")
    invalid = root / "ClassEval_0" / "a"
    (invalid / "artifact" / "last_message.txt").write_text("not valid python")
    _write_json(invalid / "receipt.json", {"valid": False,
        "sourceSha": hashlib.sha256(b"").hexdigest()})
    (invalid / "candidate.py").write_text("")
    _write_json(invalid / "evaluation.json", _report(False))
    loaded = loader._load_rows(root, [_row()])["ClassEval_0"]
    assert loaded["logicalPrefixCalls"] == 2 and "b" in loaded["callPaths"]


def test_wrong_r_prompt_is_rejected(tmp_path):
    root = _make_parent(tmp_path, "r")
    rdir = root / "ClassEval_0" / "repair-0"
    (rdir / "prompt.txt").write_text("wrong")
    with pytest.raises(ValueError, match="prompt"):
        loader._load_rows(root, [_row()])


def test_root_dependency_contract_is_rejected(tmp_path):
    root = _make_parent(tmp_path, "a")
    contract_path = root / "contract.json"
    contract = loader._json(contract_path)
    contract["runnerSha"] = "wrong"
    _write_json(contract_path, contract)
    with pytest.raises(ValueError, match="terminal"):
        loader._load_rows(root, [_row()])


def test_parent_prompt_must_match_generate_template(tmp_path):
    root = _make_parent(tmp_path, "a")
    directory = root / "ClassEval_0" / "a"
    prompt_path = directory / "prompt.txt"
    prompt_path.write_text("wrong")
    contract = loader._json(directory / "contract.json")
    contract["promptSha"] = hashlib.sha256(b"wrong").hexdigest()
    _write_json(directory / "contract.json", contract)
    with pytest.raises(ValueError, match="expected prompt"):
        loader._load_rows(root, [_row()])


def test_solver_tools_contract_must_be_false(tmp_path):
    root = _make_parent(tmp_path, "a")
    path = root / "ClassEval_0" / "a" / "contract.json"
    contract = loader._json(path)
    contract["solverTools"] = True
    _write_json(path, contract)
    with pytest.raises(ValueError, match="contract"):
        loader._load_rows(root, [_row()])


def test_selected_source_mismatch_is_rejected(tmp_path):
    root = _make_parent(tmp_path, "r")
    (root / "ClassEval_0" / "ordinary-final" / "selected.py").write_text("tampered")
    with pytest.raises(ValueError, match="source/report"):
        loader._load_rows(root, [_row()])


def test_cross_arm_repair_path_is_rejected(tmp_path):
    root = _make_parent(tmp_path, "r")
    final_info_path = root / "ClassEval_0" / "ordinary-final" / "result.json"
    info = loader._json(final_info_path)
    info["repairFrom"] = "generic/repair-0"
    _write_json(final_info_path, info)
    with pytest.raises(ValueError, match="repair-0"):
        loader._load_rows(root, [_row()])


@pytest.mark.parametrize(("field", "value"), [
    ("exit_code", 1), ("timed_out", True), ("sourceSafe", False),
    ("nonTextItems", ["tool"]), ("parseError", "syntax"),
])
def test_valid_receipt_requires_success_execution_fields(tmp_path, field, value):
    root = _make_parent(tmp_path, "a")
    path = root / "ClassEval_0" / "a" / "receipt.json"
    receipt = loader._json(path)
    receipt[field] = value
    _write_json(path, receipt)
    with pytest.raises(ValueError, match="valid receipt"):
        loader._load_rows(root, [_row()])
