from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools import analyze_polarity_conditioned_veto as analysis
from tools.prepare_plain_codex_file_benchmark import canonical_digest, sha256_file


def test_policy_family_is_exact_and_selected_rule_does_not_expand() -> None:
    eligible = ["q1", "q2", "q3", "q4", "q5", "q6", "q7"]
    v3 = ["q1", "q2", "q3", "q4", "q5", "q6"]
    certificates = [
        {"id": "q1", "preference": "PREFER_LEFT", "targetPolarity": "SELECT_CORRECT"},
        {"id": "q2", "preference": "PREFER_RIGHT", "targetPolarity": "SELECT_INCORRECT"},
        {"id": "q3", "preference": "PREFER_LEFT", "targetPolarity": "MULTI_SELECT"},
        {"id": "q4", "preference": "PREFER_RIGHT", "targetPolarity": "SELECT_CORRECT"},
        {"id": "q5", "preference": "TIE", "targetPolarity": "SELECT_CORRECT"},
        {"id": "q6", "preference": "PREFER_LEFT", "targetPolarity": "SELECT_BEST"},
        {"id": "q7", "preference": "PREFER_RIGHT", "targetPolarity": "SELECT_LEAST"},
    ]
    mappings = [
        {"id": "q1", "leftRole": "INCUMBENT", "rightRole": "PROPOSED"},
        {"id": "q2", "leftRole": "PROPOSED", "rightRole": "INCUMBENT"},
        {"id": "q3", "leftRole": "INCUMBENT", "rightRole": "PROPOSED"},
        {"id": "q4", "leftRole": "INCUMBENT", "rightRole": "PROPOSED"},
        {"id": "q5", "leftRole": "PROPOSED", "rightRole": "INCUMBENT"},
        {"id": "q6", "leftRole": "INCUMBENT", "rightRole": "PROPOSED"},
        {"id": "q7", "leftRole": "PROPOSED", "rightRole": "INCUMBENT"},
    ]
    features = analysis.certificate_features(certificates, mappings, eligible)

    policies = analysis.build_policy_switches(eligible, v3, features)

    assert tuple(policies) == analysis.POLICY_NAMES
    assert policies["v3_strict"] == v3
    assert policies["any_incumbent_veto"] == ["q4", "q5"]
    assert policies["select_correct_veto"] == ["q2", "q3", "q4", "q5", "q6"]
    assert policies["select_incorrect_veto"] == ["q1", "q3", "q4", "q5", "q6"]
    assert policies["multi_select_veto"] == ["q1", "q2", "q4", "q5", "q6"]
    assert "SELECT_BEST" in analysis.SELECTED_RULE_VERBATIM
    assert "never veto V3" in analysis.SELECTED_RULE_VERBATIM


def test_score_policy_reports_exact_r_h_ww_pairing_and_domains() -> None:
    ids = ["q1", "q2", "q3", "q4"]
    questions = {
        "q1": {"id": "q1", "benchmarkId": "d1", "prompt": "Pick.\nA. a1\nB. b1\nC. c1"},
        "q2": {"id": "q2", "benchmarkId": "d1", "prompt": "Pick.\nA. a2\nB. b2\nC. c2"},
        "q3": {"id": "q3", "benchmarkId": "d2", "prompt": "Pick.\nA. a3\nB. b3\nC. c3"},
        "q4": {"id": "q4", "benchmarkId": "d2", "prompt": "Pick.\nA. a4\nB. b4\nC. c4"},
    }
    gold = {
        "q1": {"privateGold": {"correctOptionId": "A"}},
        "q2": {"privateGold": {"correctOptionId": "B"}},
        "q3": {"privateGold": {"correctOptionId": "C"}},
        "q4": {"privateGold": {"correctOptionId": "A"}},
    }
    base = {"q1": "a1", "q2": "a2", "q3": "a3", "q4": "a4"}
    proposed = {"q1": "b1", "q2": "b2", "q3": "b3", "q4": "b4"}
    base_correct = {"q1": True, "q2": False, "q3": False, "q4": True}
    v3_correct = {"q1": False, "q2": True, "q3": False, "q4": True}

    metrics, correctness = analysis.score_policy(
        switch_ids=["q1", "q2", "q3"],
        expected_ids=ids,
        fixed_ids=ids,
        questions=questions,
        gold=gold,
        base_answers=base,
        proposed_answers=proposed,
        base_correctness=base_correct,
        v3_correctness=v3_correct,
    )

    assert correctness == v3_correct
    assert metrics["score"]["pass"] == 2
    assert metrics["switchOutcomesVsBase"] == {
        "R": 1,
        "H": 1,
        "WW": 1,
        "correctToCorrect": 0,
        "net": 0,
    }
    assert metrics["pairedExactMcNemarVsBase"]["oneSidedExactMcNemarP"] == 0.75
    assert metrics["pairedExactMcNemarVsV3"]["discordant"] == 0
    assert metrics["perDomainDeltas"]["d1"]["deltaPointsVsBase"] == 0
    assert metrics["perDomainDeltas"]["d2"]["deltaPointsVsV3"] == 0


def test_report_is_self_hashed_and_explicitly_nonconfirmatory() -> None:
    value = {
        "schemaVersion": 1,
        "analysisType": analysis.ANALYSIS_TYPE,
        "posthoc": True,
        "confirmation": False,
        "promotionCandidate": False,
        "selectedFreshHoldoutHypothesis": {
            "policy": analysis.SELECTED_POLICY,
            "ruleVerbatim": analysis.SELECTED_RULE_VERBATIM,
        },
    }
    report = analysis.finalize_report(value)

    assert report["analysisType"] == "posthoc_hypothesis_generation_not_confirmation"
    assert report["confirmation"] is False
    assert report["promotionCandidate"] is False
    assert report["reportSha256"] == canonical_digest(
        {key: item for key, item in report.items() if key != "reportSha256"}
    )
    with pytest.raises(ValueError, match="must not already contain"):
        analysis.finalize_report(report)


def test_exact_hash_check_rejects_tamper(tmp_path: Path) -> None:
    path = tmp_path / "artifact.json"
    path.write_text(json.dumps({"status": "accepted"}) + "\n", encoding="utf-8")
    expected = sha256_file(path)

    assert analysis.verify_file_hash_exact(path, expected, "artifact") == expected
    path.write_text(json.dumps({"status": "tampered"}) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="artifact hash mismatch"):
        analysis.verify_file_hash_exact(path, expected, "artifact")
