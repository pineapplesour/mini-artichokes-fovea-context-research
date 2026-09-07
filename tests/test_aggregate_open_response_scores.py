import pytest

from tools.aggregate_open_response_scores import aggregate_score_reports


def _report(case_id: str, verdict: str, *, benchmark_id: str = "open.fixture.v2"):
    return {
        "benchmarkId": benchmark_id,
        "judgeModel": "gpt-5.6-luna",
        "judgeCallsUsed": 2,
        "judgeCallBudget": 3,
        "resourceGateAtStart": {"safe": True},
        "cases": [{"caseId": case_id, "verdict": verdict}],
    }


def test_aggregate_score_reports_enforces_coverage_and_preserves_order():
    aggregate = aggregate_score_reports(
        [_report("q2", "fail"), _report("q1", "pass")],
        expected_case_ids=["q1", "q2"],
    )

    assert aggregate["total"] == 2
    assert aggregate["passed"] == 1
    assert aggregate["failed"] == 1
    assert aggregate["accuracy"] == 0.5
    assert aggregate["judgeCallsUsed"] == 4
    assert [case["caseId"] for case in aggregate["cases"]] == ["q1", "q2"]


def test_aggregate_score_reports_rejects_duplicates_missing_and_mixed_benchmarks():
    with pytest.raises(ValueError, match="duplicate"):
        aggregate_score_reports([_report("q1", "pass"), _report("q1", "fail")])
    with pytest.raises(ValueError, match="coverage mismatch"):
        aggregate_score_reports([_report("q1", "pass")], expected_case_ids=["q1", "q2"])
    with pytest.raises(ValueError, match="same nonempty benchmarkId"):
        aggregate_score_reports([_report("q1", "pass"), _report("q2", "pass", benchmark_id="other")])
