import json

import pytest

from tools.obligation_overlap_view import failure_records, make_view, restore_failure, split_failure


def feedback():
    return {"task": {"candidateOrder": ["plain", "graph", "ordinary_repair"],
        "wholeTaskPassed": {"plain": False, "graph": False, "ordinary_repair": False},
        "noCaseReport": {}, "caseStatus": {"case": ["failed", "failed", "failed"]},
        "failures": {"case": [
            {"candidates": ["plain"], "message": 'Assertion: \nExpecting message to be:\n  "required"\nbut was:\n  "wrong one"'},
            {"candidates": ["graph", "ordinary_repair"], "message": 'Assertion: \nExpecting message to be:\n  "required"\nbut was:\n  "wrong two"'}]}}}


def test_same_expectation_survives_different_wrong_outputs():
    raw = feedback()
    local, overlap = make_view(raw, "case_local"), make_view(raw, "obligation_overlap")
    groups = overlap["tasks"]["task"]["requirementGroups"]
    assert len(groups) == 1
    assert groups[0]["crossLineageCaseIds"] == ["case"]
    assert len(groups[0]["observations"]) == 2
    assert failure_records(local) == failure_records(overlap)
    assert len(failure_records(overlap)) == 3


@pytest.mark.parametrize("message", [
    'error\nexpected: \n  "value with trailing space "\n but was: \n  "other"',
    'error\nexpected:\n  "line1\n\n  "\n but was:\n  "line1"',
    "java.lang.ArrayIndexOutOfBoundsException: Index 5 out of bounds for length 5",
    'Truncated report expected: "missing separator',
])
def test_split_never_changes_diagnostic_bytes(message):
    assert restore_failure(split_failure(message)) == message


def test_ambiguous_nested_separator_remains_unparsed():
    message = 'expected:\n  "literal\nbut was:\n  value"\nbut was:\n  "other"'
    assert split_failure(message) == {"kind": "unparsed_diagnostic", "message": message}


def test_related_candidates_are_not_two_independent_lineages():
    raw = feedback()
    raw["task"]["failures"]["case"] = raw["task"]["failures"]["case"][1:]
    group = make_view(raw, "obligation_overlap")["tasks"]["task"]["requirementGroups"][0]
    assert group["crossLineageCaseIds"] == []


def test_different_expectations_are_not_collapsed():
    raw = feedback()
    raw["task"]["failures"]["case"][1]["message"] = raw["task"]["failures"]["case"][1]["message"].replace('"required"', '"different"')
    view = make_view(raw, "obligation_overlap")
    assert len(view["tasks"]["task"]["requirementGroups"]) == 2
    assert all(not row["crossLineageCaseIds"] for row in view["tasks"]["task"]["requirementGroups"])


def test_no_report_remains_unknown_and_full_inventory_retained():
    raw = feedback()
    raw["other_task"] = {"candidateOrder": ["plain", "graph", "ordinary_repair"],
        "wholeTaskPassed": {"plain": False, "graph": False, "ordinary_repair": False},
        "noCaseReport": {"plain": "compiler failed"}, "caseStatus": {}, "failures": {}}
    view = make_view(raw, "obligation_overlap")
    assert view["taskCount"] == 2
    assert view["tasks"]["other_task"]["noCaseReport"] == {"plain": "compiler failed"}
    assert view["tasks"]["other_task"]["requirementGroups"] == []
    assert failure_records(view) == failure_records(make_view(raw, "case_local"))


def test_unknown_format_rejected():
    with pytest.raises(ValueError):
        make_view(feedback(), "majority_vote")


def test_staged_views_have_equal_canonical_records_and_intact_raw_input(tmp_path):
    from tools.run_aider_obligation_view import stage_view
    original = json.dumps(feedback())
    receipts = []
    for mode in ("case_local", "obligation_overlap"):
        artifact = tmp_path / mode
        artifact.mkdir()
        raw = artifact / "case-feedback.json"
        raw.write_text(original)
        receipts.append(stage_view(artifact, mode))
        assert raw.read_text() == original
        view = json.loads((artifact / "repair-view.json").read_text())
        assert view["format"] == mode
        assert view["taskCount"] == 1
    assert receipts[0]["canonicalFailureRecordsSha256"] == receipts[1]["canonicalFailureRecordsSha256"]
    assert receipts[0]["failureRecords"] == receipts[1]["failureRecords"] == 3
    assert receipts[0]["experimentRunnerSha256"] == receipts[1]["experimentRunnerSha256"]


def test_new_instruction_is_common_and_preserves_original_contract():
    from tools.run_aider_obligation_view import REPAIR, transform_prompt
    from tools.run_aider_shared_failure_overlap import GENERIC, make_prompt
    original = make_prompt("unique original task", "generic", 180, 100)
    revised = transform_prompt(original)
    assert revised.replace(REPAIR, GENERIC) == original
    assert "unique original task" in revised
    assert "response by epoch 940" in revised
    assert "Only listed solution\nfiles are writable" in revised
    assert "taskId, hypothesis, check, observation, action" in revised


def test_support_is_same_case_not_votes_across_unrelated_cases():
    raw = feedback()
    original = raw["task"]["failures"]["case"]
    raw["task"]["failures"] = {"first": original[:1], "second": original[1:]}
    groups = make_view(raw, "obligation_overlap")["tasks"]["task"]["requirementGroups"]
    assert len(groups) == 1
    assert groups[0]["crossLineageCaseIds"] == []
