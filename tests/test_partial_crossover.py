import json

import pytest

from tools import run_aider_partial_crossover as crossover
from tools.run_aider_shared_failure_overlap import make_feedback, make_prompt


def test_exclusive_support_requires_observed_failure_not_unknown():
    row = {"candidateOrder": ["a", "b"], "caseStatus": {
        "shared": ["passed", "passed"], "left": ["passed", "failed"],
        "right": ["failed", "passed"], "unknown": ["passed", "not_reported"]}}
    edge = crossover.overlap_edges(row)[0]
    assert edge["sharedPassingCases"] == ["shared"]
    assert edge["leftExclusiveVerifiedPasses"] == ["left"]
    assert edge["rightExclusiveVerifiedPasses"] == ["right"]
    assert edge["observedUnionBeyondBest"] is None
    assert not edge["observedUnionCoversInventory"]
    assert not edge["independentVotes"]


def test_complementarity_is_coverage_not_a_whole_program_pass():
    row = {"candidateOrder": ["a", "b"], "caseStatus": {
        "shared": ["passed", "passed"], "left": ["passed", "failed"],
        "right": ["failed", "passed"]}}
    edge = crossover.overlap_edges(row)[0]
    assert edge["observedInventoriesAligned"]
    assert edge["observedUnionBeyondBest"] == 1
    assert edge["observedUnionCoversInventory"]
    assert "passed" not in edge


def test_common_evidence_contains_only_five_generic_parents(tmp_path):
    captures = {label: {"tasks": {"task": {"passed": False, "outputHead": "",
        "cases": {"c": {"status": "failed", "message": "bad"}}}}} for label in crossover.PARENTS}
    raw = make_feedback(captures, crossover.PARENTS)
    (tmp_path / "case-feedback.json").write_text(json.dumps(raw))
    seed = {"taskOutcomes": {"task": False}, "selectedSources": {"task": crossover.B}}
    meta = crossover.stage_graph(tmp_path, seed)
    assert len(meta["parentIds"]) + 1 == 6
    assert "obligation_view_v1_obligation_overlap" not in meta["parentIds"]
    index = json.loads((tmp_path / "crossover-index.json").read_text())
    assert len(index) == 1 and index[0]["taskId"] == "task"
    view = json.loads((tmp_path / "crossover-tasks/000.json").read_text())
    assert len(view["overlapEdges"]) == 10
    assert view["caseStatus"] == raw["task"]["caseStatus"]


def test_parent_or_task_drift_is_rejected(tmp_path):
    (tmp_path / "case-feedback.json").write_text(json.dumps({"wrong": {}}))
    with pytest.raises(ValueError, match="inventories"):
        crossover.stage_graph(tmp_path, {"taskOutcomes": {"right": False}})
    captures = {"x": {"tasks": {}}}
    with pytest.raises(ValueError, match="candidate inventory"):
        make_feedback(captures, ["x", "missing"])


def test_policies_differ_only_in_repair_procedure_and_keep_reserve():
    original = make_prompt("original requirements", "generic", 180, 1000)
    generic = crossover.transform_prompt(original, "generic")
    overlap = crossover.transform_prompt(original, "overlap")
    assert generic.replace(crossover.GENERIC, crossover.OVERLAP) == overlap
    for prompt in [generic, overlap]:
        assert "original requirements" in prompt
        assert "editing by epoch 1720" in prompt and "response by epoch 1840" in prompt
        assert "BOTH policies receive and may use ALL" in prompt
        assert "taskId, hypothesis, check, observation, action" in prompt
        assert "Edit ONLY each task's listed solution files" in prompt
    with pytest.raises(ValueError):
        crossover.transform_prompt(original, "vote")
