"""Mocked tail tests; toy classes/routing are not performance evidence."""

import ast
import json
from pathlib import Path

import pytest

from tools import run_classeval_overlap_repair_tail as tail


def _row(source=None):
    skeleton = source or "class Toy:\n    def left(self):\n        return 0\n    def bridge(self):\n        return 0\n    def right(self):\n        return 0\n"
    return {"task_id": "ClassEval_0", "class_name": "Toy", "skeleton": skeleton}


def _report(passed, count=0):
    cases = {f"c{i}": {"status": "passed"} for i in range(count)}
    if not passed and not cases:
        cases = {"c0": {"status": "failed", "message": "observed"}}
    return {"passed": passed, "expectedCount": len(cases), "fatal": None if passed else "failure",
            "cases": cases}


def _prefix(source, passed=False, calls=2):
    return {"source": source, "report": _report(passed, 1 if passed else 0),
            "logicalPrefixCalls": calls, "sharedPhysicalRepairCalls": 0}


def test_method_order_and_skeleton_fallback():
    row = _row()
    assert tail.target_method_labels(row, "bad(") == ("left", "bridge", "right")
    assert tail.target_method_labels({**row, "skeleton": "bad("}, row["skeleton"]) == (
        "left", "bridge", "right")


def test_failure_trace_moves_highest_ranked_anchor_to_middle():
    labels = ("m0", "m1", "m2", "m3", "m4")
    report = {"cases": {
        "f0": {"status": "failed", "methods": ["m1"]},
        "f1": {"status": "error", "methods": ["m1"]},
        "p0": {"status": "passed", "methods": ["m1"]},
        "f2": {"status": "failed", "methods": ["m3"]},
    }}
    reordered, hint = tail.choose_failure_anchor(labels, report)
    assert reordered == ("m0", "m1", "m3", "m2", "m4")
    assert hint["method"] == "m3" and hint["failed"] == 1 and hint["passed"] == 0


def test_failure_trace_absent_or_unmatched_keeps_original_middle():
    labels = ("m0", "m1", "m2")
    for report in ({"cases": {}}, {"cases": {"x": {"status": "failed", "methods": ["other"]}}}):
        reordered, hint = tail.choose_failure_anchor(labels, report)
        assert reordered == labels and hint is None


def test_whole_program_fallback_has_no_overlap():
    row = _row("not python")
    prefix = _prefix("also not python", calls=1)
    result = tail.run_task(row, prefix, Path("/tmp/unused"))
    assert all(item["fallback"] and not item["overlap"] for item in result.values())
    assert all(item["totalLogicalCalls"] == 1 for item in result.values())


def test_projection_replaces_only_assigned_methods():
    parent = _row()["skeleton"]
    candidate = """from extra import thing
class Toy:
    def left(self):
        return 1
    def bridge(self):
        return 2
    def right(self):
        return 99
    def added(self):
        return 8
"""
    projected = tail.project_source(parent, candidate, "Toy", ("left", "bridge"))
    methods = tail.ordered_method_labels(projected, "Toy")
    assert methods == ("left", "bridge", "right")
    assert "return 1" in projected and "return 2" in projected and "return 0" in projected
    assert "extra" not in projected and "added" not in projected


def test_observed_feedback_has_method_allowlist_not_source_or_tests():
    report = {"passed": False, "expectedCount": 1, "fatal": None,
              "cases": {"x": {"status": "failed", "message": "m", "methods": ["left", "other"]}}}
    feedback = tail.observed_feedback(report, ("left", "bridge"))
    assert feedback["methods"] == ["left", "bridge"]
    assert feedback["cases"]["x"]["methods"] == ["left"]
    assert "source" not in json.dumps(feedback) and "test" not in json.dumps(feedback)


def test_d_o_prompts_share_prefix_and_hide_peer_outputs(tmp_path):
    row, source = _row(), _row()["skeleton"]
    prefix = _prefix(source)
    labels = tail.target_method_labels(row, source)
    plan = tail.scope_operator.build_scope_plans(labels)["O"]
    feedback = tail.observed_feedback(prefix["report"], labels)
    a = tail._independent_prompt(row, prefix, plan, "A", labels, feedback)
    b = tail._independent_prompt(row, prefix, plan, "B", labels, feedback)
    assert source in a and source in b and a != b
    assert "Candidate B usable source" not in a and "Candidate A usable source" not in b
    assert "left" in a and "bridge" in a and "right" in b


def test_d_o_mocked_execution_projects_and_calls_exactly_three(tmp_path):
    row, source = _row(), _row()["skeleton"]
    prefix = _prefix(source, calls=2)
    calls = []

    def fake_call(row, out, label, prompt):
        calls.append((label, prompt))
        if label.endswith("A"):
            candidate = source.replace("return 0", "return 1", 1)
        elif label.endswith("B"):
            candidate = source.replace("return 0", "return 2", 2)
        else:
            candidate = source.replace("return 0", "return 3")
        return {"source": candidate, "report": _report(True, 1), "valid": True}

    def fake_evaluate(row, projected):
        return _report(True, 1)

    result = tail.run_task(row, prefix, tmp_path, call_fn=fake_call, evaluate_fn=fake_evaluate)
    assert len(calls) == 9
    assert result["D"]["tailModelCalls"] == result["O"]["tailModelCalls"] == 3
    assert result["D"]["projectedEvalCalls"] == result["O"]["projectedEvalCalls"] == 2
    assert result["D"]["intersection"] == ()
    assert result["O"]["intersection"] == ("bridge",)
    assert result["D"]["totalLogicalCalls"] == result["O"]["totalLogicalCalls"] == 5
    assert result["D"]["rawEvalCalls"] == result["O"]["rawEvalCalls"] == 3
    assert result["D"]["canonicalEvalCalls"] == result["O"]["canonicalEvalCalls"] == 3
    assert result["D"]["suiteEvalCalls"] == result["O"]["suiteEvalCalls"] == 6


def test_invalid_candidate_is_failure_without_retry(tmp_path):
    row, source = _row(), _row()["skeleton"]
    prefix = _prefix(source, calls=3)
    calls = []

    def fake_call(row, out, label, prompt):
        calls.append(label)
        return {"source": "", "report": _report(False), "valid": False}

    result = tail.run_task(row, prefix, tmp_path, call_fn=fake_call, evaluate_fn=lambda *_: pytest.fail("no projection"))
    assert len(calls) == 9 and all(item["tailModelCalls"] == 3 for item in result.values())
    assert all(item["selected"] == "prefix" and not item["report"]["passed"] for item in result.values())


def test_passing_prefix_stops_all_arms_without_calls(tmp_path):
    row, source = _row(), _row()["skeleton"]
    result = tail.run_task(row, _prefix(source, passed=True, calls=1), tmp_path,
                           call_fn=lambda *args: pytest.fail("model call"))
    assert all(item["status"] == "stopped" and item["tailModelCalls"] == 0 for item in result.values())


def test_selector_is_pass_then_casecount_and_stable():
    reports = [_report(False), _report(True, 1), _report(True, 2), _report(True, 2)]
    chosen = tail._select([(str(i), str(i), report) for i, report in enumerate(reports)])
    assert chosen[0] == "2"


def test_ast_canonicalization_repairs_multiline_staticmethod_for_every_arm():
    source = """class Toy:
    def left(self):
        return 0
    def bridge(
        value
    ):
        return value
    def right(self):
        return 0
"""
    row = {**_row(source), "_dataset": "classeval-pro"}
    prefix = _prefix(source)
    seen = []

    def evaluate(row, executable):
        seen.append(executable)
        return _report(False)

    plans = tail.scope_operator.build_scope_plans(tail.target_method_labels(row, source))
    candidate = {"source": source, "valid": True, "agent": "A"}
    for plan in plans.values():
        tail._projected_view(row, prefix, plan, candidate, evaluate)
    assert len(seen) == 3
    assert all("@staticmethod\n    def bridge(value):" in item for item in seen)


def test_projected_and_changed_methods_are_observed_not_planned(tmp_path):
    row, source = _row(), _row()["skeleton"]
    prefix = _prefix(source)

    def fake_call(row, out, label, prompt):
        if label.endswith("A"):
            candidate = source.replace("return 0", "return 1", 1)
        elif label.endswith("B"):
            candidate = source.replace("return 0", "return 2", 2)
        else:
            candidate = source
        return {"source": candidate, "report": _report(False), "valid": True}

    result = tail.run_task(row, prefix, tmp_path, call_fn=fake_call,
                           evaluate_fn=lambda *_: _report(False))
    assert result["O"]["projectedMethodsA"] == ("left", "bridge")
    assert result["O"]["projectedMethodsB"] == ("bridge", "right")
    assert result["O"]["changedMethodsA"] == ("left",)
    assert result["O"]["changedMethodsB"] == ("bridge",)
    assert result["O"]["plannedOverlap"] == ("bridge",)
    assert result["O"]["activeOverlap"] is True
    assert all(result["O"][key] for key in ("bridgeBodyShaA", "bridgeBodyShaB", "bridgeBodyShaC"))
    assert result["D"]["plannedOverlap"] == () and result["D"]["activeOverlap"] is False


def test_active_overlap_requires_c_to_contain_target_bridge(tmp_path):
    row, source = _row(), _row()["skeleton"]
    prefix = _prefix(source)

    def fake_call(row, out, label, prompt):
        candidate = "class Other:\n    pass\n" if label.endswith("C") else source
        return {"source": candidate, "report": _report(True, 1), "valid": True}

    result = tail.run_task(row, prefix, tmp_path, call_fn=fake_call,
                           evaluate_fn=lambda *_: _report(True, 1))
    assert result["O"]["bridgeBodyShaA"] and result["O"]["bridgeBodyShaB"]
    assert result["O"]["bridgeBodyShaC"] is None
    assert result["O"]["activeOverlap"] is False


def test_invalid_full_candidates_cannot_win_even_with_passing_raw_report(tmp_path):
    row, source = _row(), _row()["skeleton"]
    prefix = _prefix(source)

    def fake_call(row, out, label, prompt):
        return {"source": source, "report": _report(True, 9), "valid": False}

    def no_evaluate(*args):
        pytest.fail("invalid candidate must not receive canonical evaluation")

    result = tail.run_task(row, prefix, tmp_path, call_fn=fake_call, evaluate_fn=no_evaluate)
    assert all(item["selected"] == "prefix" for item in result.values())
    assert all(item["canonicalEvalCalls"] == 0 and not item["activeOverlap"]
               for item in result.values())
    assert all(item["bridgeBodyShaA"] is None and item["bridgeBodyShaB"] is None
               and item["bridgeBodyShaC"] is None for item in result.values())


def test_feedback_has_global_bound_and_truncation_marker():
    report = {"passed": False, "fatal": "F" * 20_000, "expectedCount": 3,
              "cases": {str(i): {"status": "failed", "message": "code=EXPECTED_VALUE " + "M" * 3_000,
                                  "methods": ["bridge"]} for i in range(3)}}
    feedback = tail.observed_feedback(report, ("bridge",))
    total = len(feedback["fatal"] or "") + sum(len(item["message"])
                                                for item in feedback["cases"].values())
    assert total <= tail.FEEDBACK_LIMIT
    assert feedback["feedbackTruncated"] is True
    assert tail.TRUNCATION_MARKER in json.dumps(feedback)
    assert "code=EXPECTED_VALUE" in json.dumps(feedback)
    exact = tail.observed_feedback(
        {"passed": False, "fatal": "F" * tail.FEEDBACK_LIMIT,
         "cases": {"extra": {"status": "failed", "message": "retained"}}}, ())
    exact_text = exact["fatal"] or ""
    exact_text += "".join(item["message"] for item in exact["cases"].values())
    assert len(exact_text) <= tail.FEEDBACK_LIMIT and tail.TRUNCATION_MARKER in exact_text


def test_feedback_reserves_one_marker_for_many_omitted_messages_at_exact_cap():
    report = {
        "passed": False,
        "fatal": "F" * (tail.FEEDBACK_LIMIT - len(tail.TRUNCATION_MARKER)),
        "cases": {str(i): {"status": "failed", "message": "M" * 10_000}
                   for i in range(10)},
    }
    feedback = tail.observed_feedback(report, ())
    text = (feedback["fatal"] or "") + "".join(
        item["message"] for item in feedback["cases"].values())
    assert len(text) == tail.FEEDBACK_LIMIT
    assert text.count(tail.TRUNCATION_MARKER) == 1
    messages = [item["message"] for item in feedback["cases"].values()]
    assert messages[0] == tail.TRUNCATION_MARKER
    assert messages[1:] == [""] * 9


def test_prompts_share_code_only_rules_and_do_not_serialize_row_test_or_gold():
    row, source = _row(), _row()["skeleton"]
    row.update({"test": "TEST_SECRET_SENTINEL", "solution_code": "GOLD_SECRET_SENTINEL"})
    prefix = _prefix(source)
    labels = tail.target_method_labels(row, source)
    feedback = tail.observed_feedback(prefix["report"], labels)
    for plan in tail.scope_operator.build_scope_plans(labels).values():
        a = tail._independent_prompt(row, prefix, plan, "A", labels, feedback)
        b = tail._independent_prompt(row, prefix, plan, "B", labels, feedback)
        c = tail._reconciliation_prompt(row, prefix, plan,
                                        {"source": source, "feedback": feedback},
                                        {"source": source, "feedback": feedback}, feedback)
        for prompt in (a, b, c):
            assert tail.OUTPUT_RULES in prompt and tail.CONTRACT_CHECKLIST in prompt
            assert "ledger" not in prompt.lower()
            assert "TEST_SECRET_SENTINEL" not in prompt
            assert "GOLD_SECRET_SENTINEL" not in prompt


def test_claim_rejects_existing_or_parent_overlap(tmp_path):
    parent = tmp_path / "parent"
    parent.mkdir()
    existing = tmp_path / "existing"
    existing.mkdir()
    with pytest.raises((FileExistsError, ValueError)):
        tail._claim_run_root(existing, parent)
    with pytest.raises(ValueError):
        tail._claim_run_root(parent / "nested", parent)
    with pytest.raises(ValueError):
        tail._claim_run_root(tmp_path, parent)


def _main_fixture(tmp_path):
    source = _row()["skeleton"]
    rows = [{"task_id": f"ClassEval_{i}", "class_name": "Toy", "skeleton": source}
            for i in range(300)]
    parent = tmp_path / "parent"
    parent.mkdir()
    (parent / "contract.json").write_text("{}")
    (parent / "result.json").write_text("{}")
    prefixes = {}
    for i, row in enumerate(rows):
        prefixes[row["task_id"]] = {
            "source": source, "report": _report(i != 0, 1 if i else 0),
            "logicalPrefixCalls": 1, "callPaths": {"a": "ordinary/a"},
            "sourceSha": f"sha-{i}",
        }
    return rows, parent, prefixes, source


def test_main_claims_root_before_realistic_call_dirs_and_persists_contract_progress(tmp_path, monkeypatch):
    rows, parent, prefixes, source = _main_fixture(tmp_path)
    run_root = tmp_path / "tail"
    monkeypatch.setattr(tail.base, "load_data", lambda _: rows)
    monkeypatch.setattr(tail.prefix_loader, "load_ordinary_prefix", lambda _: prefixes)
    call_observations = []

    def fake_call(row, out, label, prompt):
        call_observations.append((label, (run_root / "contract.json").is_file()))
        out.mkdir(parents=True, exist_ok=False)  # same directory behavior as text_runner.call
        return {"source": source, "report": _report(False), "valid": True}

    monkeypatch.setattr(tail.text_runner, "call", fake_call)
    monkeypatch.setattr(tail.base, "evaluate", lambda *_: _report(False))
    assert tail.main(["--parent-root", str(parent), "--run-root", str(run_root), "--execute"]) == 0
    assert len(call_observations) == 9 and all(seen for _, seen in call_observations)
    contract = json.loads((run_root / "contract.json").read_text())
    progress = json.loads((run_root / "progress.json").read_text())
    result = json.loads((run_root / "result.json").read_text())
    assert len(contract["prefixMap"]) == 300
    assert contract["suiteEvalCap"] == 6 and contract["tailModelCallsOnFailure"] == 3
    assert contract["parentRoot"] == str(parent.resolve())
    assert progress["completed"] == result["completed"] == 300
    assert result["status"] == "complete"


def test_main_preserves_unexpected_error_as_incomplete_without_result(tmp_path, monkeypatch):
    rows, parent, prefixes, source = _main_fixture(tmp_path)
    run_root = tmp_path / "tail-error"
    monkeypatch.setattr(tail.base, "load_data", lambda _: rows)
    monkeypatch.setattr(tail.prefix_loader, "load_ordinary_prefix", lambda _: prefixes)

    def failing_call(row, out, label, prompt):
        out.mkdir(parents=True, exist_ok=False)
        raise RuntimeError("mock call failure")

    monkeypatch.setattr(tail.text_runner, "call", failing_call)
    assert tail.main(["--parent-root", str(parent), "--run-root", str(run_root), "--execute"]) == 2
    progress = json.loads((run_root / "progress.json").read_text())
    assert progress["status"] == "incomplete" and progress["completed"] == 0
    assert progress["error"]["type"] == "RuntimeError"
    assert (run_root / "error.json").is_file() and not (run_root / "result.json").exists()


def test_main_progress_write_error_is_incomplete_and_never_complete(tmp_path, monkeypatch):
    rows, parent, prefixes, _ = _main_fixture(tmp_path)
    run_root = tmp_path / "tail-progress-error"
    monkeypatch.setattr(tail.base, "load_data", lambda _: rows)
    monkeypatch.setattr(tail.prefix_loader, "load_ordinary_prefix", lambda _: prefixes)
    monkeypatch.setattr(tail, "run_task", lambda *args, **kwargs: {})
    original = tail._write_progress
    state = {"first": True}

    def fail_once(root, results, *, status, error=None):
        if state["first"]:
            state["first"] = False
            raise OSError("mock progress disk error")
        return original(root, results, status=status, error=error)

    monkeypatch.setattr(tail, "_write_progress", fail_once)
    assert tail.main(["--parent-root", str(parent), "--run-root", str(run_root), "--execute"]) == 2
    progress = json.loads((run_root / "progress.json").read_text())
    assert progress["status"] == "incomplete" and not (run_root / "result.json").exists()
    assert progress["error"]["type"] == "OSError"


def test_main_result_write_error_is_incomplete_and_removes_result(tmp_path, monkeypatch):
    rows, parent, prefixes, _ = _main_fixture(tmp_path)
    run_root = tmp_path / "tail-result-error"
    monkeypatch.setattr(tail.base, "load_data", lambda _: rows)
    monkeypatch.setattr(tail.prefix_loader, "load_ordinary_prefix", lambda _: prefixes)
    monkeypatch.setattr(tail, "run_task", lambda *args, **kwargs: {})

    def fail_result(*args, **kwargs):
        raise OSError("mock result disk error")

    monkeypatch.setattr(tail, "_write_result", fail_result)
    assert tail.main(["--parent-root", str(parent), "--run-root", str(run_root), "--execute"]) == 2
    progress = json.loads((run_root / "progress.json").read_text())
    assert progress["status"] == "incomplete" and not (run_root / "result.json").exists()
    assert progress["error"]["type"] == "OSError"
