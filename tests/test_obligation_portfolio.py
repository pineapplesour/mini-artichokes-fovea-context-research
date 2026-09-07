import copy

import pytest

from tools.analyze_aider_probe_portfolio import aggregate_compute, check_contracts


def contracts():
    common = {"seedPatchSha256": "seed", "taskIds": ["one", "two"], "model": "luna", "effort": "medium",
        "agentTimeoutSeconds": 900, "completionReserveSeconds": 180, "captureHashes": {"plain": "p"},
        "runnerSha256": "runner", "promptTemplateSha256": "same", "promptSha256": "time-specific",
        "evidenceHashes": {"case-feedback.json": "raw", "repair-view.json": "local"},
        "experiment": {"representation": "case_local", "failureRecords": 3,
            "canonicalFailureRecordsSha256": "records", "normalizerSha256": "normalizer", "experimentRunnerSha256": "wrapper"}}
    out = {name: copy.deepcopy(common) for name in ["o", "a", "b"]}
    out["o"]["evidenceHashes"]["repair-view.json"] = "overlap"
    out["o"]["experiment"]["representation"] = "obligation_overlap"
    return out


def test_only_derived_view_may_differ_between_representations():
    check_contracts(contracts(), ["o", "a", "b"], "obligation_view_v1")


@pytest.mark.parametrize("field", ["seedPatchSha256", "agentTimeoutSeconds", "promptTemplateSha256"])
def test_changed_settings_rejected(field):
    records = contracts()
    records["b"][field] = "changed"
    with pytest.raises(ValueError):
        check_contracts(records, ["o", "a", "b"], "obligation_view_v1")


def test_changed_raw_evidence_or_repeated_view_rejected():
    for field in ["case-feedback.json", "repair-view.json"]:
        records = contracts()
        records["b"]["evidenceHashes"][field] = "changed"
        with pytest.raises(ValueError):
            check_contracts(records, ["o", "a", "b"], "obligation_view_v1")


def test_canonical_evidence_content_must_match():
    records = contracts()
    records["o"]["experiment"]["canonicalFailureRecordsSha256"] = "changed"
    with pytest.raises(ValueError):
        check_contracts(records, ["o", "a", "b"], "obligation_view_v1")


def test_accounting_counts_actual_executions_not_candidate_units():
    compute = {str(i): {"agentSeconds": 2, "usage": {"output_tokens": 10}} for i in range(5)}
    assert aggregate_compute(compute) == {"agentSeconds": 10, "logicalExecutions": 5, "usage": {"output_tokens": 50}}
