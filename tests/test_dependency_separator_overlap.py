"""Toy-only tests for the dependency-separator O candidate.

These tests exercise routing and mocked call plumbing only; they are not
benchmark or model evidence.
"""

from pathlib import Path

import pytest

from tools import dependency_separator_overlap as separator
from tools import run_classeval_dependency_separator_overlap as runner
from tools import overlap_split_merge_candidate as scope_operator
from tools import run_classeval_overlap_repair_tail as frozen_tail


SOURCE = """class Toy:
    def m0(self):
        return self.m3()

    def m1(self):
        return self.m4()

    def m2(self):
        return 2

    def m3(self):
        return 3

    def m4(self):
        return 4

    def m5(self):
        return 5
"""
NO_EDGE_SOURCE = SOURCE.replace("return self.m3()", "return 0").replace(
    "return self.m4()", "return 1")


def _report(passed=False, count=0):
    cases = {f"case-{index}": {"status": "passed"} for index in range(count)}
    if not passed:
        cases["bad"] = {"status": "failed", "message": "observed failure"}
    return {"passed": passed, "cases": cases, "expectedCount": len(cases), "fatal": None}


def _prefix(source=SOURCE, logical=3):
    return {"source": source, "report": _report(False), "logicalPrefixCalls": logical,
            "callPaths": {}, "sourceSha": "toy"}


def test_matching_cover_and_scopes_are_deterministic():
    plan = separator.build_separator_plan(SOURCE, "Toy", ("m0", "m1", "m2", "m3", "m4", "m5"))
    assert plan.cross_edges == (("m0", "m3"), ("m1", "m4"))
    assert plan.cover == plan.shared == ("m0", "m1")
    assert plan.a_scope == ("m0", "m1", "m2")
    assert plan.b_scope == ("m0", "m1", "m3", "m4", "m5")
    assert plan.matching_size == 2 and plan.overlap and not plan.fallback
    separator.validate_separator_plan(plan)
    assert plan.a_exclusive == ("m2",)
    assert plan.b_exclusive == ("m3", "m4", "m5")


def test_reverse_cls_call_is_canonicalized_to_left_right_edge():
    source = SOURCE.replace("def m3(self):", "@classmethod\n    def m3(cls):").replace(
        "return 3", "return cls.m0()", 1)
    plan = separator.build_separator_plan(source, "Toy", ("m0", "m1", "m2", "m3", "m4", "m5"))
    assert ("m0", "m3") in plan.cross_edges


def test_no_edges_is_the_existing_d_scopes_without_overlap():
    plan = separator.build_separator_plan(NO_EDGE_SOURCE, "Toy", ("m0", "m1", "m2", "m3", "m4", "m5"))
    assert plan.valid and not plan.fallback and not plan.overlap and plan.shared == ()
    assert plan.a_scope == ("m0", "m1", "m2")
    assert plan.b_scope == ("m3", "m4", "m5")


def test_small_n_and_parse_failures_use_common_e_fallback():
    small = separator.build_separator_plan(SOURCE, "Toy", ("m0", "m1"))
    broken = separator.build_separator_plan("class Toy(:\n", "Toy", ("m0", "m1", "m2"))
    for plan, labels in ((small, ("m0", "m1")), (broken, ("m0", "m1", "m2"))):
        assert plan.fallback and not plan.overlap and not plan.shared
        assert plan.a_scope == labels and plan.b_scope == labels


def test_runner_makes_only_three_new_o_calls_and_records_all_shared_bodies(tmp_path):
    row = {"task_id": "Toy_0", "class_name": "Toy", "skeleton": SOURCE}
    calls = []

    def fake_call(row, out, label, prompt):
        calls.append((label, Path(out), prompt))
        return {"source": SOURCE, "report": _report(False), "valid": True}

    result = runner.run_task(row, _prefix(), tmp_path / row["task_id"],
                             call_fn=fake_call, evaluate_fn=lambda row, source: _report(False))
    assert [item[0] for item in calls] == ["dependency-O-A", "dependency-O-B", "dependency-O-C"]
    assert all(item[1].parent == tmp_path / row["task_id"] / "O" for item in calls)
    state = result
    assert state["tailModelCalls"] == 3 and state["totalLogicalCalls"] == 6
    assert state["sharedSeparatorMethods"] == ["m0", "m1"]
    assert state["activeOverlap"] is True
    assert all(set(values) == {"m0", "m1"} for values in state["sharedMethodBodyShas"].values())
    assert "Candidate A usable source" in calls[2][2] and "Candidate B usable source" in calls[2][2]
    assert "Candidate A usable source" not in calls[0][2]
    assert "Candidate B usable source" not in calls[1][2]
    assert "Skeleton:" in calls[0][2] and SOURCE in calls[0][2]
    assert "Dependency-separator shared S (all methods): ('m0', 'm1')" in calls[0][2]


def test_zero_separator_uses_frozen_d_policy_and_bridge_none(tmp_path):
    row = {"task_id": "Toy_0", "class_name": "Toy", "skeleton": NO_EDGE_SOURCE}
    calls = []

    def fake_call(row, out, label, prompt):
        calls.append(prompt)
        return {"source": NO_EDGE_SOURCE, "report": _report(False), "valid": True}

    state = runner.run_task(
        row, _prefix(NO_EDGE_SOURCE), tmp_path / row["task_id"], call_fn=fake_call,
        evaluate_fn=lambda row, source: _report(False))
    assert state["overlap"] is False and state["sharedSeparatorMethods"] == []
    assert "effective arm=D" in calls[0] and "effective arm=D" in calls[1]
    assert "Planned bridge: None" in calls[0] and "Planned bridge: None" in calls[1]
    assert "effective arm=O" not in calls[0] and "effective arm=O" not in calls[1]


def test_zero_and_fallback_prompts_are_byte_identical_to_frozen_builders():
    feedback = {"passed": False, "cases": {}, "methods": [], "bridgeHint": None}
    row = {"task_id": "Toy_0", "class_name": "Toy", "skeleton": SOURCE}
    prefix = _prefix()
    labels = ("m0", "m1", "m2", "m3", "m4", "m5")
    zero = separator.build_separator_plan(NO_EDGE_SOURCE, "Toy", labels)
    frozen_d = scope_operator.build_scope_plans(labels)["D"]
    for who in ("A", "B"):
        assert runner._common_prompt(row, prefix, zero, labels, feedback, who, None) == \
            frozen_tail._independent_prompt(row, prefix, frozen_d, who, labels, feedback)
    usable = {"source": prefix["source"], "report": prefix["report"],
              "valid": False, "feedback": feedback}
    assert runner._reconciliation_prompt(row, prefix, zero, labels, feedback,
                                         usable, usable, None) == frozen_tail._reconciliation_prompt(
                                             row, prefix, frozen_d, usable, usable, feedback)

    fallback_labels = ("m0", "m1")
    fallback = separator.build_separator_plan(SOURCE, "Toy", fallback_labels)
    frozen_e = scope_operator.build_scope_plans(fallback_labels)["E"]
    fallback_row = {"task_id": "Toy_0", "class_name": "Toy", "skeleton": SOURCE}
    fallback_prefix = _prefix()
    assert runner._common_prompt(fallback_row, fallback_prefix, fallback,
                                 fallback_labels, feedback, "A", None) == frozen_tail._independent_prompt(
                                     fallback_row, fallback_prefix, frozen_e,
                                     "A", fallback_labels, feedback)


def test_runner_stops_passed_prefix_without_calls(tmp_path):
    row = {"task_id": "Toy_0", "class_name": "Toy", "skeleton": SOURCE}
    prefix = _prefix()
    prefix["report"] = _report(True, 2)
    result = runner.run_task(row, prefix, tmp_path / row["task_id"],
                             call_fn=lambda *args: (_ for _ in ()).throw(AssertionError("called")))
    assert result["status"] == "stopped"
    assert result["tailModelCalls"] == 0 and result["activeOverlap"] is False


def test_parent_terminal_gate_accepts_legacy_missing_status_but_not_incomplete():
    legacy = {"completed": 300, "total": 300, "tasks": {}}
    runner._validate_parent_result(legacy)
    runner._validate_parent_result({**legacy, "status": "complete"})
    with pytest.raises(ValueError, match="terminal complete"):
        runner._validate_parent_result({**legacy, "status": "incomplete"})
