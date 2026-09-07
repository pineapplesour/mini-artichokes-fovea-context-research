#!/usr/bin/env python3
"""Audit and privately score a preregistered two-verifier intersection."""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.analyze_overlap_adjudication import (
    answer_map,
    load_jsonl,
    normalize_correct_option,
    paired,
)
from tools.prepare_plain_codex_file_benchmark import DEFAULT_REGISTRY, canonical_digest, private_exam_rows, sha256_file
from tools.run_ensemble_file_agent import match_answer_to_option, parse_mcq_options
from tools.validate_overlap_adjudication import DECISION_RE, validate_overlap_adjudication


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def verify_self_hash(value: dict[str, Any], field: str, label: str) -> None:
    claimed = str(value.get(field) or "")
    observed = canonical_digest({key: item for key, item in value.items() if key != field})
    if not claimed or claimed != observed:
        raise ValueError(f"{label} self-hash mismatch")


def decision_set(campaign: Path, eligible_ids: list[str]) -> set[str]:
    rows: list[dict[str, str]] = []
    for line_number, raw in enumerate(
        (campaign / "solver/output/decisions.log").read_text(encoding="utf-8").splitlines(), 1
    ):
        match = DECISION_RE.fullmatch(raw)
        if not match:
            raise ValueError(f"invalid decision line {line_number}: {campaign}")
        rows.append({key: value.strip() for key, value in match.groupdict().items()})
    if [row["id"] for row in rows] != eligible_ids:
        raise ValueError(f"decision IDs/order mismatch: {campaign}")
    return {row["id"] for row in rows if row["gate"] == "VALID" and row["action"] == "SWITCH"}


def receipt_audit(campaign: Path) -> dict[str, Any]:
    receipt = load_json(campaign / "solver/run_receipt.json")
    verify_self_hash(receipt, "receiptSha256", f"receipt {campaign.name}")
    artifact = receipt.get("artifactValidation") if isinstance(receipt.get("artifactValidation"), dict) else {}
    process = receipt.get("process") if isinstance(receipt.get("process"), dict) else {}
    policy = receipt.get("policyAudit") if isinstance(receipt.get("policyAudit"), dict) else {}
    isolation = receipt.get("isolationProbe") if isinstance(receipt.get("isolationProbe"), dict) else {}
    trace_path = campaign / "solver/codex_trace.jsonl"
    first_event = json.loads(trace_path.read_text(encoding="utf-8").splitlines()[0])
    checks = {
        "accepted": receipt.get("status") == "accepted",
        "oneCall": receipt.get("semanticModelInvocations") == 1,
        "model": receipt.get("model") == "gpt-5.6-luna",
        "reasoningEffort": receipt.get("reasoningEffort") == "high",
        "verbosity": receipt.get("verbosity") == "low",
        "process": process.get("exitCode") == 0 and process.get("timedOut") is False,
        "policyAudit": policy.get("passed") is True,
        "isolationProbe": isolation.get("passed") is True,
        "strictArtifact": artifact.get("passed") is True,
        "answersHash": artifact.get("answersSha256")
        == sha256_file(campaign / "solver/output/answers.jsonl"),
        "decisionsHash": artifact.get("decisionsSha256")
        == sha256_file(campaign / "solver/output/decisions.log"),
        "threadEvent": first_event.get("type") == "thread.started" and bool(first_event.get("thread_id")),
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "receiptSha256": receipt.get("receiptSha256"),
        "traceSha256": sha256_file(trace_path),
        "threadId": first_event.get("thread_id"),
        "elapsedSec": process.get("elapsedSec"),
        "tokenUsage": ((policy.get("trace") or {}).get("tokenUsage") or {}),
        "webSearchEvents": len(((policy.get("trace") or {}).get("webSearchEvents") or [])),
    }


def audit(
    validator_1: Path,
    validator_2: Path,
    combination_dir: Path,
    existing_universal: Path,
    registry_path: Path,
) -> dict[str, Any]:
    validator_1 = validator_1.resolve()
    validator_2 = validator_2.resolve()
    combination_dir = combination_dir.resolve()
    combo = load_json(combination_dir / "combination_receipt.json")
    verify_self_hash(combo, "receiptSha256", "combination receipt")
    combined_answers_path = combination_dir / "answers.jsonl"
    if combo.get("answersSha256") != sha256_file(combined_answers_path):
        raise ValueError("combination answers hash mismatch")
    strict_1 = validate_overlap_adjudication(validator_1, write_report=False)
    strict_2 = validate_overlap_adjudication(validator_2, write_report=False)
    receipt_1 = receipt_audit(validator_1)
    receipt_2 = receipt_audit(validator_2)
    if receipt_1["receiptSha256"] != (combo.get("validator1") or {}).get("receiptSha256"):
        raise ValueError("validator 1 receipt is not bound to combination")
    if receipt_2["receiptSha256"] != (combo.get("validator2") or {}).get("receiptSha256"):
        raise ValueError("validator 2 receipt is not bound to combination")
    if receipt_1["traceSha256"] != (combo.get("validator1") or {}).get("traceSha256"):
        raise ValueError("validator 1 trace is not bound to combination")
    if receipt_2["traceSha256"] != (combo.get("validator2") or {}).get("traceSha256"):
        raise ValueError("validator 2 trace is not bound to combination")

    input_dir = validator_1 / "solver/input"
    questions = load_jsonl(input_dir / "questions.jsonl")
    question_by_id = {str(row["id"]): row for row in questions}
    manifest = load_jsonl(input_dir / "overlap_manifest.jsonl")
    eligible_ids = [str(row["id"]) for row in manifest if row.get("eligible") is True]
    switches_1 = decision_set(validator_1, eligible_ids)
    switches_2 = decision_set(validator_2, eligible_ids)
    intersection = switches_1 & switches_2
    union = switches_1 | switches_2
    if len(intersection) != combo.get("intersectionRows"):
        raise ValueError("recomputed intersection size mismatch")

    gold = private_exam_rows(registry_path)
    fixed_ids = sorted(
        case_id
        for case_id, question in question_by_id.items()
        if question.get("responseFormat") == "mcq"
        and case_id in gold
        and normalize_correct_option((gold[case_id].get("privateGold") or {}).get("correctOptionId"))
    )
    systems = {
        "base": answer_map(input_dir / "candidates/base.jsonl"),
        "validator1": answer_map(validator_1 / "solver/output/answers.jsonl"),
        "validator2": answer_map(validator_2 / "solver/output/answers.jsonl"),
        "intersection": answer_map(combined_answers_path),
        "existingUniversal": answer_map(existing_universal),
    }
    correctness: dict[str, dict[str, bool]] = {name: {} for name in systems}
    mappings: dict[str, dict[str, str | None]] = {name: {} for name in systems}
    for case_id in fixed_ids:
        question = question_by_id[case_id]
        options = parse_mcq_options(str(question.get("prompt") or ""))
        correct = normalize_correct_option((gold[case_id].get("privateGold") or {}).get("correctOptionId"))
        for name, answers in systems.items():
            mapped = match_answer_to_option(answers.get(case_id, ""), options)
            mappings[name][case_id] = mapped
            correctness[name][case_id] = bool(mapped and mapped == correct)

    scores = {
        name: {
            "pass": sum(values.values()),
            "total": len(fixed_ids),
            "accuracy": sum(values.values()) / len(fixed_ids),
            "unmapped": sum(not mappings[name][case_id] for case_id in fixed_ids),
        }
        for name, values in correctness.items()
    }
    comparisons = {
        "validator1VsBase": paired(correctness["validator1"], correctness["base"], fixed_ids),
        "validator2VsBase": paired(correctness["validator2"], correctness["base"], fixed_ids),
        "intersectionVsBase": paired(correctness["intersection"], correctness["base"], fixed_ids),
        "intersectionVsValidator1": paired(correctness["intersection"], correctness["validator1"], fixed_ids),
        "intersectionVsExistingUniversal": paired(
            correctness["intersection"], correctness["existingUniversal"], fixed_ids
        ),
    }

    def switch_outcomes(switches: set[str]) -> dict[str, int]:
        cohort = [case_id for case_id in fixed_ids if case_id in switches]
        return {
            "n": len(cohort),
            "rescues": sum(not correctness["base"][case_id] and correctness["intersection"][case_id] for case_id in cohort),
            "harms": sum(correctness["base"][case_id] and not correctness["intersection"][case_id] for case_id in cohort),
            "wrongToWrong": sum(not correctness["base"][case_id] and not correctness["intersection"][case_id] for case_id in cohort),
        }

    n = len(eligible_ids)
    n11 = len(intersection)
    n10 = len(switches_1 - switches_2)
    n01 = len(switches_2 - switches_1)
    n00 = n - n11 - n10 - n01
    observed_agreement = (n11 + n00) / n
    p1 = len(switches_1) / n
    p2 = len(switches_2) / n
    expected_agreement = p1 * p2 + (1 - p1) * (1 - p2)
    kappa = (observed_agreement - expected_agreement) / (1 - expected_agreement)

    per_benchmark: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for case_id in fixed_ids:
        benchmark = str(question_by_id[case_id].get("benchmarkId") or "unknown")
        per_benchmark[benchmark]["n"] += 1
        if not correctness["base"][case_id] and correctness["intersection"][case_id]:
            per_benchmark[benchmark]["rescues"] += 1
        if correctness["base"][case_id] and not correctness["intersection"][case_id]:
            per_benchmark[benchmark]["harms"] += 1
    domain_guard = all(
        values["harms"] - values["rescues"] <= max(1, math.ceil(0.01 * values["n"]))
        for values in per_benchmark.values()
    )
    primary = comparisons["intersectionVsBase"]
    promotion = {
        "integrity": bool(
            strict_1.get("passed")
            and strict_2.get("passed")
            and receipt_1["passed"]
            and receipt_2["passed"]
            and receipt_1["threadId"] != receipt_2["threadId"]
            and receipt_1["traceSha256"] != receipt_2["traceSha256"]
        ),
        "harmsAtMost4": primary["harms"] <= 4,
        "harmRatio": primary["harms"] <= primary["rescues"] // 4,
        "netAtLeast22": primary["net"] >= 22,
        "oneSidedPAtMostPoint05": primary["oneSidedExactMcNemarP"] <= 0.05,
        "beatsExistingUniversal": scores["intersection"]["pass"] > scores["existingUniversal"]["pass"],
        "perBenchmarkHarmGuard": domain_guard,
        "validator2ElapsedAtMost680Sec": float(receipt_2["elapsedSec"] or math.inf) <= 680,
    }
    promotion["allPassed"] = all(promotion.values())

    return {
        "analysisType": "result_aware_development_only",
        "fixedCohort": {"n": len(fixed_ids), "sortedIdsSha256": canonical_digest(fixed_ids)},
        "integrity": {
            "combinationReceiptSha256": combo.get("receiptSha256"),
            "answersSha256": combo.get("answersSha256"),
            "validator1": receipt_1,
            "validator2": receipt_2,
        },
        "scores": scores,
        "comparisons": comparisons,
        "switchAgreement": {
            "eligibleRows": n,
            "bothSwitch": n11,
            "validator1Only": n10,
            "validator2Only": n01,
            "bothKeep": n00,
            "union": len(union),
            "jaccard": n11 / len(union) if union else None,
            "positiveAgreement": (2 * n11) / (2 * n11 + n10 + n01) if (2 * n11 + n10 + n01) else None,
            "observedAgreement": observed_agreement,
            "cohenKappa": kappa,
        },
        "intersectionSwitchOutcomes": switch_outcomes(intersection),
        "perBenchmark": {key: dict(value) for key, value in sorted(per_benchmark.items())},
        "promotionGate": promotion,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validator-1", type=Path, required=True)
    parser.add_argument("--validator-2", type=Path, required=True)
    parser.add_argument("--combination-dir", type=Path, required=True)
    parser.add_argument("--existing-universal", type=Path, required=True)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit(
        args.validator_1,
        args.validator_2,
        args.combination_dir,
        args.existing_universal,
        args.registry,
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
