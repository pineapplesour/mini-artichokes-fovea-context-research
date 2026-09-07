"""Toy-only tests for read-only tail analysis and cached provenance."""

import hashlib
import itertools
import json
from pathlib import Path

import pytest

from tools import analyze_classeval_overlap_repair_tail as analysis
from tools import run_classeval_source_overlap as base
from tools import run_classeval_text_overlap as text_runner


def _report(passed, count=1):
    cases = {f"c{i}": {"status": "passed"} for i in range(count)}
    if not passed:
        cases["bad"] = {"status": "failed"}
    return {"passed": passed, "cases": cases, "expectedCount": len(cases), "fatal": None}


def test_two_sided_paired_and_holm_two_are_exact():
    candidate = [True, True, False, False]
    control = [False, True, True, False]
    item = analysis.paired_exact(candidate, control)
    assert item["rescues"] == item["harms"] == 1
    assert item["absolutePercentagePoints"] == 0
    assert item["exactTwoSidedP"] == 1.0
    comparisons = {"O-minus-E": {"exactTwoSidedP": 0.01},
                   "O-minus-D": {"exactTwoSidedP": 0.04}}
    assert analysis.holm_two(comparisons) == {"O-minus-E": 0.02, "O-minus-D": 0.04}


def test_secondary_selector_has_fixed_tie_order_and_raw_global_route():
    candidate = {label: {"valid": True, "report": _report(False)}
                 for label in analysis.SECONDARY_ORDER}
    candidate["validrawA"] = {"valid": True, "report": _report(True, 2)}
    assert analysis.select_secondary(candidate) == ("validrawA", "raw-global")
    tied = {label: {"valid": True, "report": _report(True, 2)}
            for label in analysis.SECONDARY_ORDER}
    assert analysis.select_secondary(tied) == ("prefix", "canonical-usable")


def test_reported_projection_count_is_not_scoped_for_e_or_fallback():
    e = {"projectedEvalCalls": 2, "canonicalEvalCalls": 3, "fallback": False}
    d_fallback = {"projectedEvalCalls": 2, "canonicalEvalCalls": 3, "fallback": True}
    o = {"projectedEvalCalls": 2, "canonicalEvalCalls": 3, "fallback": False}
    assert analysis._evaluation_breakdown(e, "E") == {
        "reportedABCanonicalEvalCalls": 2, "scopedProjectedEvalCalls": 0,
        "fullCanonicalEvalCalls": 3}
    assert analysis._evaluation_breakdown(d_fallback, "D")["scopedProjectedEvalCalls"] == 0
    assert analysis._evaluation_breakdown(o, "O")["scopedProjectedEvalCalls"] == 2


def test_grouped_max_matches_exhaustive_seven_candidate_selector():
    front = analysis.SECONDARY_ORDER[:4]
    raw = analysis.SECONDARY_ORDER[4:]
    reverse_primary = {"prefix": "prefix", "usableA": "A", "usableB": "B", "usableC": "C"}
    score_states = ((False, 0), (False, 1), (True, 2))
    for states in itertools.product(score_states, repeat=7):
        candidates = {}
        for label, (passed, count) in zip(analysis.SECONDARY_ORDER, states):
            candidates[label] = {"source": label, "report": _report(passed, count), "valid": True}
        expected_label, _ = analysis.select_secondary(candidates)
        front_winner, _ = analysis.select_secondary({label: candidates[label] for label in front})
        primary = {"selected": reverse_primary[front_winner],
                   "source": candidates[front_winner]["source"],
                   "report": candidates[front_winner]["report"]}
        raw_calls = {}
        for label in raw:
            candidates[label].update({"artifactPath": f"/toy/{label}",
                                       "rawSourceSha": f"raw-{label}",
                                       "candidateSourceSha": f"candidate-{label}"})
            raw_calls[label[-1]] = candidates[label]
        grouped = analysis.grouped_secondary(primary, raw_calls)
        assert grouped["label"] == expected_label
        assert (grouped["passed"], grouped["passedCases"]) == analysis._score(candidates[expected_label])
        if expected_label == front_winner:
            assert grouped["source"] == primary["source"]
        else:
            assert grouped["source"] == candidates[expected_label]["source"]
            assert grouped["artifactPath"] == f"/toy/{expected_label}"
            assert grouped["rawSourceSha"] == f"raw-{expected_label}"
            assert grouped["candidateSourceSha"] == f"candidate-{expected_label}"


def test_cached_tail_call_reuses_receipt_and_transformation_checks(tmp_path):
    row = {"task_id": "Toy_0", "class_name": "Toy",
           "skeleton": "class Toy:\n    def f(self):\n        return 0\n"}
    directory = tmp_path / "E" / "a"
    (directory / "artifact").mkdir(parents=True)
    raw = "```python\nclass Toy:\n    def f(self):\n        return 1\n```\n"
    raw_source = text_runner.extract_code(raw)
    prompt = "tail prompt"
    candidate = base.evaluation_source(row, raw_source)
    (directory / "prompt.txt").write_text(prompt)
    (directory / "artifact" / "last_message.txt").write_text(raw)
    (directory / "candidate.py").write_text(candidate)
    (directory / "contract.json").write_text(json.dumps({
        "taskId": row["task_id"], "label": "tail-E-A", "dataSha": base.PRO_SHA,
        "model": "gpt-5.6-luna", "effort": "medium", "timeoutSeconds": 120,
        "solverTools": False, "promptSha": hashlib.sha256(prompt.encode()).hexdigest()}))
    (directory / "receipt.json").write_text(json.dumps({
        "valid": True, "exit_code": 0, "timed_out": False, "sourceSafe": True,
        "nonTextItems": [], "parseError": None,
        "sourceSha": hashlib.sha256(raw_source.encode()).hexdigest(),
        "duration_seconds": 1.25, "usage": {"input_tokens": 4, "output_tokens": 2}}))
    (directory / "evaluation.json").write_text(json.dumps(_report(False)))
    item, cost = analysis._read_tail_call(row, directory, "tail-E-A")
    assert item["valid"] is True and cost["physicalReceipts"] == 1
    assert cost["input_tokens"] == 4 and cost["durationSeconds"] == 1.25

    (directory / "candidate.py").write_text("class Toy:\n    def f(self):\n        return 99\n")
    with pytest.raises(ValueError, match="candidate source transformation"):
        analysis._read_tail_call(row, directory, "tail-E-A")
