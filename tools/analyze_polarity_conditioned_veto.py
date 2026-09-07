#!/usr/bin/env python3
"""Reproduce the V3/V7 polarity-conditioned veto hypothesis analysis.

This is a private, explicitly posthoc analysis.  It reconstructs five fixed
policies in memory, writes no answer/policy artifact, and may emit only one
self-hashed analysis report.  Its selected rule is a hypothesis for a future
fresh holdout, never a promotion or confirmatory result on these data.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.analyze_blind_pairwise_policies import (
    EXPECTED_FIXED_M_IDS_SHA256,
    EXPECTED_FIXED_M_ROWS,
    EXPECTED_REGISTRY_SHA256,
    EXPECTED_ROWS,
    EXPECTED_V3_ANSWERS_SHA256,
    audit_blind_campaign,
    audit_strict_campaign,
    build_fixed_cohort,
    evaluate_answers,
    load_jsonl,
    paired_correctness,
    read_answer_artifact,
    strict_switch_ids,
    switch_outcomes,
)
from tools.prepare_blind_pairwise_veto import source_bundle
from tools.prepare_plain_codex_file_benchmark import (
    DEFAULT_REGISTRY,
    canonical_digest,
    private_exam_rows,
    sha256_file,
)


ANALYSIS_TYPE = "posthoc_hypothesis_generation_not_confirmation"
POLICY_NAMES = (
    "v3_strict",
    "any_incumbent_veto",
    "select_correct_veto",
    "select_incorrect_veto",
    "multi_select_veto",
)
SELECTED_POLICY = "select_correct_veto"
SELECTED_RULE_VERBATIM = (
    "Keep every V3 VALID+SWITCH unless the blind certificate explicitly prefers "
    "INCUMBENT and targetPolarity == SELECT_CORRECT; only then keep the exact frozen "
    "base answer. TIE, preference for PROPOSED, SELECT_INCORRECT, SELECT_BEST, "
    "SELECT_LEAST, MULTI_SELECT, and UNRESOLVED never veto V3."
)

DEFAULT_V3_CAMPAIGN = REPO_ROOT / "runs/mini-overlap-confirm1-dev-v3-20260831"
DEFAULT_V7_CAMPAIGN = REPO_ROOT / "runs/mini-overlap-confirm1-dev-v7-blind-pairwise-v2-20260831"

EXPECTED_V7_FREEZE_SHA256 = "48e6db7da53a7333f63556d700a19b83b70a0f3ba694a3e9c2e320231f86f1e5"
EXPECTED_V7_RECEIPT_SHA256 = "7a79a7e5429428ceec3c0d960f175aa5b2b1b6d8278e311b89533ef86a9b17bf"
EXPECTED_V7_CERTIFICATES_SHA256 = "50d18f45c0472b9a084a12f9d0d04e081ab3d707cca4612564835c4c3d9fd2ab"
EXPECTED_V7_TRACE_SHA256 = "032644bcbbd66e87a53afb5f07eab497be11dca71f56b20db490d3c03b5320dc"
EXPECTED_V7_ROLE_MAPPING_SHA256 = "9ed8bec3f5c96423109162324bc23a3232d76165010957d53cc1177c85f0b7d3"
EXPECTED_SOURCE_CANDIDATE_HASHES = {
    "base": "6f4e50d3e9901b10fbb4cd8db0d7d5e835a234bf63196efe303d8163e6536c95",
    "auxiliary_1": "64b6ac1eda02333ed53f2c3e3c15928533e8af559dde18411697e03937d4bd48",
    "auxiliary_2": "954ba0407d86fa0dc307271b62b45c635409cc78dc995fd225208c5a2459dd1e",
}


def verify_file_hash_exact(path: Path, expected: str, label: str) -> str:
    if not path.is_file():
        raise FileNotFoundError(path)
    observed = sha256_file(path)
    if observed != expected:
        raise ValueError(f"{label} hash mismatch")
    return observed


def role_preference(certificate: Mapping[str, Any], mapping: Mapping[str, Any]) -> str:
    preference = certificate.get("preference")
    if preference == "TIE":
        return "TIE"
    side = "leftRole" if preference == "PREFER_LEFT" else "rightRole" if preference == "PREFER_RIGHT" else None
    if side is None:
        raise ValueError(f"invalid blind preference for {certificate.get('id')}")
    role = mapping.get(side)
    if role not in {"INCUMBENT", "PROPOSED"}:
        raise ValueError(f"invalid hidden role mapping for {certificate.get('id')}")
    return str(role)


def certificate_features(
    certificates: list[dict[str, Any]],
    mappings: list[dict[str, Any]],
    eligible_ids: list[str],
) -> dict[str, dict[str, str]]:
    if [row.get("id") for row in certificates] != eligible_ids:
        raise ValueError("V7 certificate IDs/order mismatch")
    if [row.get("id") for row in mappings] != eligible_ids:
        raise ValueError("V7 role-mapping IDs/order mismatch")
    result: dict[str, dict[str, str]] = {}
    for certificate, mapping in zip(certificates, mappings, strict=True):
        case_id = str(certificate["id"])
        polarity = certificate.get("targetPolarity")
        if not isinstance(polarity, str) or not polarity:
            raise ValueError(f"invalid target polarity for {case_id}")
        result[case_id] = {
            "rolePreference": role_preference(certificate, mapping),
            "targetPolarity": polarity,
        }
    return result


def build_policy_switches(
    eligible_ids: list[str],
    v3_switch_ids: list[str],
    features: Mapping[str, Mapping[str, str]],
) -> dict[str, list[str]]:
    eligible_set = set(eligible_ids)
    if any(case_id not in eligible_set for case_id in v3_switch_ids):
        raise ValueError("V3 switch set contains an ineligible ID")
    v3_set = set(v3_switch_ids)

    def ordered_without(predicate: Any) -> list[str]:
        return [
            case_id
            for case_id in eligible_ids
            if case_id in v3_set and not predicate(case_id)
        ]

    def incumbent_with_polarity(case_id: str, polarity: str) -> bool:
        return bool(
            features[case_id]["rolePreference"] == "INCUMBENT"
            and features[case_id]["targetPolarity"] == polarity
        )

    policies = {
        "v3_strict": [case_id for case_id in eligible_ids if case_id in v3_set],
        "any_incumbent_veto": ordered_without(
            lambda case_id: features[case_id]["rolePreference"] == "INCUMBENT"
        ),
        "select_correct_veto": ordered_without(
            lambda case_id: incumbent_with_polarity(case_id, "SELECT_CORRECT")
        ),
        "select_incorrect_veto": ordered_without(
            lambda case_id: incumbent_with_polarity(case_id, "SELECT_INCORRECT")
        ),
        "multi_select_veto": ordered_without(
            lambda case_id: incumbent_with_polarity(case_id, "MULTI_SELECT")
        ),
    }
    if tuple(policies) != POLICY_NAMES:
        raise AssertionError("posthoc policy inventory changed")
    return policies


def per_domain_deltas(
    candidate: Mapping[str, bool],
    base: Mapping[str, bool],
    v3: Mapping[str, bool],
    fixed_ids: list[str],
    question_by_id: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    domains = sorted(
        {str(question_by_id[case_id].get("benchmarkId") or "unknown") for case_id in fixed_ids}
    )
    report: dict[str, dict[str, Any]] = {}
    for domain in domains:
        ids = [
            case_id
            for case_id in fixed_ids
            if str(question_by_id[case_id].get("benchmarkId") or "unknown") == domain
        ]
        candidate_pass = sum(candidate[case_id] for case_id in ids)
        base_pass = sum(base[case_id] for case_id in ids)
        v3_pass = sum(v3[case_id] for case_id in ids)
        report[domain] = {
            "n": len(ids),
            "pass": candidate_pass,
            "basePass": base_pass,
            "v3Pass": v3_pass,
            "deltaPointsVsBase": candidate_pass - base_pass,
            "deltaPointsVsV3": candidate_pass - v3_pass,
            "deltaAccuracyVsBase": (candidate_pass - base_pass) / len(ids),
            "deltaAccuracyVsV3": (candidate_pass - v3_pass) / len(ids),
        }
    return report


def score_policy(
    *,
    switch_ids: list[str],
    expected_ids: list[str],
    fixed_ids: list[str],
    questions: Mapping[str, dict[str, Any]],
    gold: Mapping[str, dict[str, Any]],
    base_answers: Mapping[str, str],
    proposed_answers: Mapping[str, str],
    base_correctness: Mapping[str, bool],
    v3_correctness: Mapping[str, bool],
) -> tuple[dict[str, Any], dict[str, bool]]:
    switch_set = set(switch_ids)
    answers = {
        case_id: proposed_answers[case_id] if case_id in switch_set else base_answers[case_id]
        for case_id in expected_ids
    }
    score, correctness, _ = evaluate_answers(answers, fixed_ids, questions, gold)
    outcomes = switch_outcomes(correctness, base_correctness, switch_ids, fixed_ids)
    vs_base = paired_correctness(correctness, base_correctness, fixed_ids)
    vs_v3 = paired_correctness(correctness, v3_correctness, fixed_ids)
    if (outcomes["rescues"], outcomes["harms"]) != (vs_base["rescues"], vs_base["harms"]):
        raise ValueError("policy changes correctness outside its frozen switch set")
    metrics = {
        "switches": len(switch_ids),
        "switchIdsSha256": canonical_digest(switch_ids),
        "score": score,
        "switchOutcomesVsBase": {
            "R": outcomes["rescues"],
            "H": outcomes["harms"],
            "WW": outcomes["wrongToWrong"],
            "correctToCorrect": outcomes["correctToCorrect"],
            "net": outcomes["net"],
        },
        "pairedExactMcNemarVsBase": vs_base,
        "pairedExactMcNemarVsV3": vs_v3,
        "perDomainDeltas": per_domain_deltas(
            correctness, base_correctness, v3_correctness, fixed_ids, questions
        ),
    }
    return metrics, correctness


def finalize_report(value: dict[str, Any]) -> dict[str, Any]:
    if "reportSha256" in value:
        raise ValueError("report must not already contain reportSha256")
    report = dict(value)
    report["reportSha256"] = canonical_digest(report)
    return report


def analyze(
    *,
    v3_campaign: Path,
    v7_campaign: Path,
    registry_path: Path,
) -> dict[str, Any]:
    v3_campaign = v3_campaign.resolve()
    v7_campaign = v7_campaign.resolve()
    registry_path = registry_path.resolve()

    source = source_bundle(v3_campaign)
    if source["candidateHashes"] != EXPECTED_SOURCE_CANDIDATE_HASHES:
        raise ValueError("frozen d1/d3/d4 candidate hashes mismatch")
    strict_audit = audit_strict_campaign(v3_campaign)
    blind_audit = audit_blind_campaign(v7_campaign, v3_campaign)
    expected_v7 = {
        "freezeSha256": EXPECTED_V7_FREEZE_SHA256,
        "receiptSha256": EXPECTED_V7_RECEIPT_SHA256,
        "certificatesSha256": EXPECTED_V7_CERTIFICATES_SHA256,
        "traceSha256": EXPECTED_V7_TRACE_SHA256,
    }
    for field, expected in expected_v7.items():
        if blind_audit.get(field) != expected:
            raise ValueError(f"V7 exact artifact mismatch: {field}")
    role_mapping_path = v7_campaign / "control/role_mapping.jsonl"
    verify_file_hash_exact(role_mapping_path, EXPECTED_V7_ROLE_MAPPING_SHA256, "V7 role mapping")
    verify_file_hash_exact(registry_path, EXPECTED_REGISTRY_SHA256, "private registry")

    expected_ids = list(source["ids"])
    eligible_ids = list(source["eligibleIds"])
    if len(expected_ids) != EXPECTED_ROWS:
        raise ValueError("frozen question inventory mismatch")
    v3_switches = strict_switch_ids(v3_campaign, eligible_ids)
    certificates = load_jsonl(v7_campaign / "veto/output/certificates.jsonl")
    mappings = load_jsonl(role_mapping_path)
    features = certificate_features(certificates, mappings, eligible_ids)
    policies = build_policy_switches(eligible_ids, v3_switches, features)

    gold = private_exam_rows(registry_path)
    fixed_ids, question_by_id = build_fixed_cohort(list(source["questions"]), gold)
    if len(fixed_ids) != EXPECTED_FIXED_M_ROWS or canonical_digest(fixed_ids) != EXPECTED_FIXED_M_IDS_SHA256:
        raise ValueError("fixed private M mismatch")

    base_answers = source["candidates"]["base"]
    proposed_answers = source["candidates"]["auxiliary_1"]
    base_score, base_correctness, _ = evaluate_answers(
        base_answers, fixed_ids, question_by_id, gold
    )
    v3_rows, v3_answers = read_answer_artifact(
        v3_campaign / "solver/output/answers.jsonl",
        expected_ids,
        claimed_sha256=EXPECTED_V3_ANSWERS_SHA256,
        label="V3 strict",
    )
    del v3_rows
    expected_v3_answers = {
        case_id: proposed_answers[case_id] if case_id in set(v3_switches) else base_answers[case_id]
        for case_id in expected_ids
    }
    if v3_answers != expected_v3_answers:
        raise ValueError("V3 answers do not exactly implement its frozen decisions")
    _, v3_correctness, _ = evaluate_answers(v3_answers, fixed_ids, question_by_id, gold)

    metrics: dict[str, dict[str, Any]] = {}
    for name in POLICY_NAMES:
        metrics[name], _ = score_policy(
            switch_ids=policies[name],
            expected_ids=expected_ids,
            fixed_ids=fixed_ids,
            questions=question_by_id,
            gold=gold,
            base_answers=base_answers,
            proposed_answers=proposed_answers,
            base_correctness=base_correctness,
            v3_correctness=v3_correctness,
        )

    report = {
        "schemaVersion": 1,
        "analysisType": ANALYSIS_TYPE,
        "posthoc": True,
        "confirmation": False,
        "promotionCandidate": False,
        "policyOutputsWritten": False,
        "selectedFreshHoldoutHypothesis": {
            "policy": SELECTED_POLICY,
            "ruleVerbatim": SELECTED_RULE_VERBATIM,
            "status": "frozen_posthoc_rule_for_one_future_fresh_holdout_only",
            "confirmation": False,
            "promotionCandidate": False,
        },
        "family": {
            "policyOrder": list(POLICY_NAMES),
            "definitions": {
                "v3_strict": "exact frozen V3 VALID+SWITCH decisions",
                "any_incumbent_veto": "V3 minus every blind explicit INCUMBENT preference",
                "select_correct_veto": "V3 minus blind INCUMBENT preferences labeled SELECT_CORRECT",
                "select_incorrect_veto": "V3 minus blind INCUMBENT preferences labeled SELECT_INCORRECT",
                "multi_select_veto": "V3 minus blind INCUMBENT preferences labeled MULTI_SELECT",
            },
        },
        "integrity": {
            "passed": True,
            "v3": strict_audit,
            "v7": blind_audit,
            "v7RoleMappingSha256": sha256_file(role_mapping_path),
            "sourceCandidateHashes": source["candidateHashes"],
            "registrySha256": sha256_file(registry_path),
            "fixedM": {
                "n": len(fixed_ids),
                "sortedIdsSha256": canonical_digest(fixed_ids),
            },
        },
        "baseScore": base_score,
        "policies": metrics,
        "interpretationBoundary": (
            "All policy comparisons and the selected rule were generated after V7 private outcomes were "
            "available. They generate one fresh-holdout hypothesis and make no confirmatory or promotion claim."
        ),
    }
    return finalize_report(report)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v3-campaign", type=Path, default=DEFAULT_V3_CAMPAIGN)
    parser.add_argument("--v7-campaign", type=Path, default=DEFAULT_V7_CAMPAIGN)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = analyze(
        v3_campaign=args.v3_campaign,
        v7_campaign=args.v7_campaign,
        registry_path=args.registry,
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        output = args.output.resolve()
        if output.exists():
            raise FileExistsError(f"refusing to overwrite posthoc report: {output}")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
