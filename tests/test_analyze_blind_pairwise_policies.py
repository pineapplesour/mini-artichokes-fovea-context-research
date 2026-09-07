from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools import analyze_blind_pairwise_policies as analyzer
from tools.prepare_plain_codex_file_benchmark import canonical_digest, sha256_file


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def policy_metrics(
    *,
    score: int = 588,
    rescues: int = 25,
    harms: int = 3,
    switches: int = 32,
    domain_guard: bool = True,
) -> dict:
    return {
        "score": {"pass": score},
        "switchOutcomes": {
            "rescues": rescues,
            "harms": harms,
            "net": rescues - harms,
            "switches": switches,
            "oneSidedExactMcNemarP": analyzer.one_sided_exact_mcnemar(rescues, harms),
        },
        "perDomainGuard": domain_guard,
    }


def test_missing_and_unmapped_answers_are_counted_wrong() -> None:
    ids = ["q1", "q2", "q3"]
    questions = {
        case_id: {
            "id": case_id,
            "responseFormat": "mcq",
            "prompt": f"Pick one.\nA. alpha-{case_id}\nB. beta-{case_id}\nC. gamma-{case_id}",
        }
        for case_id in ids
    }
    gold = {
        case_id: {"privateGold": {"correctOptionId": "A"}}
        for case_id in ids
    }
    answers = {"q1": "alpha-q1", "q2": "not one of the options"}

    score, correctness, mapped = analyzer.evaluate_answers(answers, ids, questions, gold)

    assert score == {
        "pass": 1,
        "fail": 2,
        "total": 3,
        "accuracy": 1 / 3,
        "missing": 1,
        "unmapped": 1,
    }
    assert correctness == {"q1": True, "q2": False, "q3": False}
    assert not mapped["q2"]
    assert mapped["q3"] is None


def test_exact_mcnemar_p_values_match_frozen_v3_audit() -> None:
    assert analyzer.one_sided_exact_mcnemar(30, 9) == pytest.approx(0.0005325097590684891)
    assert analyzer.two_sided_exact_mcnemar(30, 9) == pytest.approx(0.0010650195181369781)
    assert analyzer.one_sided_exact_mcnemar(0, 0) == 1.0
    assert analyzer.two_sided_exact_mcnemar(3, 3) == 1.0


def test_answer_hash_and_order_tamper_fail_closed(tmp_path: Path) -> None:
    path = tmp_path / "answers.jsonl"
    expected_ids = ["q1", "q2"]
    rows = [
        {"id": "q1", "finalAnswer": "alpha"},
        {"id": "q2", "finalAnswer": "beta"},
    ]
    write_jsonl(path, rows)
    frozen_hash = sha256_file(path)
    _, answers = analyzer.read_answer_artifact(
        path, expected_ids, claimed_sha256=frozen_hash, label="test"
    )
    assert answers == {"q1": "alpha", "q2": "beta"}

    rows.reverse()
    write_jsonl(path, rows)
    with pytest.raises(ValueError, match="answer hash mismatch"):
        analyzer.read_answer_artifact(
            path, expected_ids, claimed_sha256=frozen_hash, label="test"
        )
    with pytest.raises(ValueError, match="IDs/order mismatch"):
        analyzer.read_answer_artifact(
            path, expected_ids, claimed_sha256=sha256_file(path), label="test"
        )


def test_receipt_self_hash_tamper_fails_closed() -> None:
    receipt = {"schemaVersion": 1, "status": "accepted"}
    receipt["receiptSha256"] = canonical_digest(receipt)
    assert analyzer.verify_self_hash(receipt, "receiptSha256", "receipt") == receipt["receiptSha256"]
    receipt["status"] = "tampered"
    with pytest.raises(ValueError, match="self-hash mismatch"):
        analyzer.verify_self_hash(receipt, "receiptSha256", "receipt")


def test_analyzer_thread_identity_uses_lf_records(tmp_path: Path) -> None:
    trace = tmp_path / "trace.jsonl"
    trace.write_text(
        '{"type":"thread.started","thread_id":"thread-1"}\n'
        '{"type":"item.completed","item":{"text":"a\u0085b\u2028c\u2029d"}}\n',
        encoding="utf-8",
    )

    assert analyzer.trace_thread_ids(trace) == ["thread-1"]


def test_switch_hash_and_order_tamper_fail_closed(tmp_path: Path) -> None:
    path = tmp_path / "switch_ids.json"
    write_json(path, {"count": 2, "ids": ["q1", "q3"]})
    assert analyzer.read_switch_artifact(
        path,
        ["q1", "q2", "q3"],
        claimed_sha256=sha256_file(path),
        label="policy",
    ) == ["q1", "q3"]

    write_json(path, {"count": 2, "ids": ["q3", "q1"]})
    with pytest.raises(ValueError, match="IDs/order mismatch"):
        analyzer.read_switch_artifact(
            path,
            ["q1", "q2", "q3"],
            claimed_sha256=sha256_file(path),
            label="policy",
        )


def test_promotion_runtime_and_integrity_gates_are_mandatory() -> None:
    policies = {name: policy_metrics() for name in analyzer.PROMOTION_NAMES}

    gates, selected = analyzer.select_development_promotion(
        policies, integrity_ok=True, blind_elapsed_sec=650.0
    )
    assert all(gates[name]["eligible"] for name in analyzer.PROMOTION_NAMES)
    assert selected is not None and selected["policy"] == "intersection"

    gates, selected = analyzer.select_development_promotion(
        policies, integrity_ok=True, blind_elapsed_sec=650.001
    )
    assert selected is None
    assert all("blindRuntimeAtMost650Sec" in gates[name]["unmetConditions"] for name in gates)

    gates, selected = analyzer.select_development_promotion(
        policies, integrity_ok=False, blind_elapsed_sec=100.0
    )
    assert selected is None
    assert all("combinationAndIntegrity" in gates[name]["unmetConditions"] for name in gates)


def test_promotion_tie_break_order_is_score_harm_switches_then_fixed_priority() -> None:
    policies = {name: policy_metrics() for name in analyzer.PROMOTION_NAMES}
    _, selected = analyzer.select_development_promotion(
        policies, integrity_ok=True, blind_elapsed_sec=100.0
    )
    assert selected is not None and selected["policy"] == "intersection"

    policies["intersection"] = policy_metrics(rescues=26, harms=4, switches=32)
    _, selected = analyzer.select_development_promotion(
        policies, integrity_ok=True, blind_elapsed_sec=100.0
    )
    assert selected is not None and selected["policy"] == "blind_only"

    policies["blind_only"] = policy_metrics(switches=33)
    policies["union"] = policy_metrics(switches=31)
    _, selected = analyzer.select_development_promotion(
        policies, integrity_ok=True, blind_elapsed_sec=100.0
    )
    assert selected is not None and selected["policy"] == "union"


def test_promotion_gates_score_net_harm_ratio_p_and_domain() -> None:
    cases = {
        "score": policy_metrics(score=587),
        "net": policy_metrics(rescues=24, harms=3),
        "absolute_harm": policy_metrics(rescues=30, harms=5),
        "harm_ratio": policy_metrics(rescues=12, harms=4),
        "p_value": policy_metrics(rescues=13, harms=0, score=588),
        "domain": policy_metrics(domain_guard=False),
    }
    # Override the p-only case so every non-p criterion is satisfied while its
    # exact one-sided p-value is just above .05 (13/13 all rescues is below .05,
    # hence use a deliberately injected audited statistic for this unit gate).
    cases["p_value"]["switchOutcomes"].update(
        {"rescues": 25, "harms": 3, "net": 22, "oneSidedExactMcNemarP": 0.051}
    )
    expected_unmet = {
        "score": "scoreAtLeast588",
        "net": "netAtLeast22",
        "absolute_harm": "harmsAtMost4",
        "harm_ratio": "harmsAtMostFloorRescuesOver4",
        "p_value": "oneSidedPAtMostPoint05",
        "domain": "noNegativePerDomainDelta",
    }
    for name, metrics in cases.items():
        gate = analyzer.promotion_gate(metrics, integrity_ok=True, blind_elapsed_sec=100.0)
        assert expected_unmet[name] in gate["unmetConditions"]


def test_candidate_majority_reconstruction_uses_d3_d4_overlap_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(analyzer, "EXPECTED_ELIGIBLE_ROWS", 2)
    questions = [
        {
            "id": f"q{index}",
            "responseFormat": "mcq",
            "prompt": f"Choose.\nA. a{index}\nB. b{index}\nC. c{index}",
        }
        for index in range(3)
    ]
    source = {
        "ids": ["q0", "q1", "q2"],
        "eligibleIds": ["q0", "q1"],
        "candidates": {
            "base": {"q0": "a0", "q1": "a1", "q2": "a2"},
            "auxiliary_1": {"q0": "b0", "q1": "b1", "q2": "a2"},
            "auxiliary_2": {"q0": "b0", "q1": "b1", "q2": "a2"},
        },
        "candidateHashes": {"base": "a", "auxiliary_1": "b", "auxiliary_2": "c"},
    }

    answers, audit = analyzer.candidate_majority_answers(source, questions)

    assert answers == {"q0": "b0", "q1": "b1", "q2": "a2"}
    assert audit["passed"] is True
    assert audit["allEligibleD3EqualsD4AndDiffersD1"] is True
    assert audit["allNoneligibleRowsKeepD1"] is True
