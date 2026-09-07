import json

import pytest

from tools import run_classeval_repair_comparison as repair


def report(passed, statuses):
    return {"passed": passed, "cases": {str(i): {"status": s} for i, s in enumerate(statuses)}}


def test_verified_seed_cannot_be_replaced_by_a_failed_repair():
    seed = report(True, ["passed"])
    bad = report(False, ["failed"])
    assert repair.select_final("seed", seed, "new", bad) == ("seed", seed, "seed")


def test_actual_pass_beats_partial_case_count_and_invalid_is_not_promoted():
    partial = report(False, ["passed"] * 12 + ["failed"])
    complete = report(True, ["passed"] * 13)
    assert repair.select_final("seed", partial, "new", complete)[2] == "repair"
    invalid = {"passed": False, "cases": {}, "fatal": "invalid model execution"}
    assert repair.select_final("seed", partial, "new", invalid)[2] == "seed"


def test_feedback_preserves_inventory_without_inventing_unknown_passes():
    raw = {"passed": False, "fatal": None, "expectedCount": 2, "cases": {
        "a": {"status": "failed", "message": "x" * 2000, "methods": ["f"]},
        "b": {"status": "not_reported", "message": ""}}}
    compact = repair.compact_feedback(raw)
    assert set(compact["cases"]) == {"a", "b"}
    assert compact["cases"]["b"]["status"] == "not_reported"
    assert len(compact["cases"]["a"]["message"]) == 1600


def test_no_model_call_for_verified_seed(tmp_path, monkeypatch):
    state = tmp_path / "task/generic"
    state.mkdir(parents=True)
    (state / "selected.py").write_text("verified code\n")
    (state / "selected-evaluation.json").write_text(json.dumps(report(True, ["passed"])))
    monkeypatch.setattr(repair.base, "IsolatedCodexAdapter", lambda *a, **k: pytest.fail("unexpected model call"))
    result = repair.repair({}, tmp_path / "task", "generic", tmp_path / "out")
    assert result["passed"] and result["modelCalls"] == 0
    assert (tmp_path / "out/selected.py").read_bytes() == (state / "selected.py").read_bytes()


def test_complete_parent_gate_rejects_partial_result_before_any_call(tmp_path):
    (tmp_path / "contract.json").write_text(json.dumps({"dataset": "classeval-pro", "dataSha": repair.base.PRO_SHA,
                                                        "taskIds": ["ClassEval_0"]}))
    (tmp_path / "result.json").write_text(json.dumps({"completed": 0, "total": 1, "tasks": {}}))
    with pytest.raises(ValueError, match="terminal complete"):
        repair.check_complete_parent(tmp_path, [{"task_id": "ClassEval_0"}])
