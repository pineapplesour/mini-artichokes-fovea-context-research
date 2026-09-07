#!/usr/bin/env python3
"""Private, fail-closed analysis of the blind pairwise policy family.

The combination step is deliberately gold-free.  This program first verifies
that step, the frozen V3 strict adjudicator, and the blind verifier, and only
then opens the private registry.  Missing or unmappable answers count as
incorrect.  No policy artifact is repaired or synthesized by this analyzer.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.prepare_blind_pairwise_veto import lf_jsonl_lines, source_bundle
from tools.prepare_plain_codex_file_benchmark import (
    DEFAULT_REGISTRY,
    canonical_digest,
    private_exam_rows,
    sha256_file,
)
from tools.run_blind_pairwise_veto_agent import verify_frozen_bundle
from tools.run_ensemble_file_agent import match_answer_to_option, parse_mcq_options
from tools.run_plain_codex_file_agent import verify_frozen_inputs
from tools.validate_blind_pairwise_veto import validate_blind_pairwise_veto
from tools.validate_overlap_adjudication import DECISION_RE, validate_overlap_adjudication


COMBINATION_PROTOCOL = "mini_artichokes_blind_pairwise_veto_combination_v1"
POLICY_NAMES = ("base", "blind_only", "intersection", "union")
PROMOTION_NAMES = ("blind_only", "intersection", "union")
PROMOTION_PRIORITY = {"intersection": 0, "blind_only": 1, "union": 2}
POLICY_DEFINITIONS = {
    "base": "always_exact_frozen_base",
    "blind_only": "blind_hidden_role_preference_is_proposed",
    "intersection": "strict_valid_switch_and_blind_hidden_role_preference_is_proposed",
    "union": "strict_valid_switch_or_blind_hidden_role_preference_is_proposed",
}

EXPECTED_ROWS = 1309
EXPECTED_ELIGIBLE_ROWS = 247
EXPECTED_FIXED_M_ROWS = 941
EXPECTED_FIXED_M_IDS_SHA256 = "2e46b0c759c185ed743d1109da1095f17643ebdd3c45bc4a30b08edbeb2b4047"
EXPECTED_REGISTRY_SHA256 = "b761dbcc274b034bfcc13c666b79e0235d8d6d092d2f53e9cc5343fc86c712f3"

# The requested comparison is specifically against the accepted V3 strict
# development artifact, not any later file placed at a convenient path.
EXPECTED_V3_FREEZE_SHA256 = "45d03ecb89c67242e0f98bf522afb524dd758b04f57bd0ab00e71b8909b39ae7"
EXPECTED_V3_RECEIPT_SHA256 = "8d52c3082c313cae26516b6faf38553a636bdffea708c9e3a2365e843a0ac99e"
EXPECTED_V3_ANSWERS_SHA256 = "c03291e2fe58a365306433059e0201298a7b4faf25f652b113f0361ad5c03c84"
EXPECTED_V3_DECISIONS_SHA256 = "59e217ebeae26fe4d0e3ce5faa75a2c4282cbf8d62f75abdc11263779b8b1eff"
EXPECTED_V3_TRACE_SHA256 = "84450113ed71b50641045b3e020d0e35a65872360a7b5ee260accc4baf821ae4"

MIN_PROMOTION_SCORE = 588
MIN_PROMOTION_NET = 22
MAX_PROMOTION_HARMS = 4
MAX_BLIND_RUNTIME_SEC = 650.0


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, raw in enumerate(lf_jsonl_lines(path), 1):
        if not raw.strip():
            raise ValueError(f"blank JSONL line {line_number}: {path}")
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError(f"non-object JSONL line {line_number}: {path}")
        rows.append(value)
    return rows


def verify_self_hash(value: dict[str, Any], field: str, label: str) -> str:
    claimed = value.get(field)
    observed = canonical_digest({key: item for key, item in value.items() if key != field})
    if not isinstance(claimed, str) or not claimed or claimed != observed:
        raise ValueError(f"{label} self-hash mismatch")
    return claimed


def safe_relative_file(root: Path, raw_relative: Any, expected: str, label: str) -> Path:
    if not isinstance(raw_relative, str) or Path(raw_relative).as_posix() != expected:
        raise ValueError(f"{label} path mismatch")
    path = (root / raw_relative).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"{label} path escapes artifact root") from exc
    unresolved = root / raw_relative
    if unresolved.is_symlink() or not path.is_file():
        raise ValueError(f"{label} must be a regular, non-symlink file")
    return path


def read_answer_artifact(
    path: Path,
    expected_ids: list[str],
    *,
    claimed_sha256: str | None,
    label: str,
) -> tuple[list[dict[str, str]], dict[str, str]]:
    if claimed_sha256 is not None and sha256_file(path) != claimed_sha256:
        raise ValueError(f"{label} answer hash mismatch")
    raw_rows = load_jsonl(path)
    rows: list[dict[str, str]] = []
    observed_ids: list[str] = []
    answers: dict[str, str] = {}
    for position, row in enumerate(raw_rows, 1):
        if set(row) != {"id", "finalAnswer"}:
            raise ValueError(f"{label} answer schema mismatch at row {position}")
        case_id = row.get("id")
        answer = row.get("finalAnswer")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError(f"{label} has an invalid ID at row {position}")
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError(f"{label} has an empty answer at row {position}")
        observed_ids.append(case_id)
        if case_id in answers:
            raise ValueError(f"{label} has duplicate answer ID {case_id}")
        answers[case_id] = answer
        rows.append({"id": case_id, "finalAnswer": answer})
    if observed_ids != expected_ids:
        raise ValueError(f"{label} answer IDs/order mismatch")
    return rows, answers


def _switch_payload_ids(value: dict[str, Any], label: str) -> list[str]:
    # The frozen combiner writes the intentionally small count/ids schema.
    if set(value) != {"count", "ids"}:
        raise ValueError(f"{label} switch file schema mismatch")
    raw_ids = value.get("ids")
    if not isinstance(raw_ids, list) or any(not isinstance(item, str) or not item for item in raw_ids):
        raise ValueError(f"{label} switch IDs are malformed")
    ids = list(raw_ids)
    if value.get("count") != len(ids) or len(ids) != len(set(ids)):
        raise ValueError(f"{label} switch count/uniqueness mismatch")
    return ids


def read_switch_artifact(
    path: Path,
    eligible_ids: list[str],
    *,
    claimed_sha256: str,
    label: str,
) -> list[str]:
    if sha256_file(path) != claimed_sha256:
        raise ValueError(f"{label} switch file hash mismatch")
    ids = _switch_payload_ids(load_json(path), label)
    eligible_set = set(eligible_ids)
    if any(case_id not in eligible_set for case_id in ids):
        raise ValueError(f"{label} includes an ineligible switch")
    expected_order = [case_id for case_id in eligible_ids if case_id in set(ids)]
    if ids != expected_order:
        raise ValueError(f"{label} switch IDs/order mismatch")
    return ids


def normalize_correct_option(value: Any) -> str:
    text = str(value or "").strip()
    if len(text) == 1 and text.upper() in "ABCDEFGHIJ":
        return str(ord(text.upper()) - ord("A") + 1)
    return text


def _binomial_tail_at_least(successes: int, trials: int) -> float:
    return sum(math.comb(trials, k) for k in range(successes, trials + 1)) / (2**trials)


def one_sided_exact_mcnemar(rescues: int, harms: int) -> float:
    discordant = rescues + harms
    if discordant == 0:
        return 1.0
    return _binomial_tail_at_least(rescues, discordant)


def two_sided_exact_mcnemar(rescues: int, harms: int) -> float:
    discordant = rescues + harms
    if discordant == 0:
        return 1.0
    upper = _binomial_tail_at_least(max(rescues, harms), discordant)
    return min(1.0, 2.0 * upper)


def paired_correctness(
    candidate: Mapping[str, bool], reference: Mapping[str, bool], ids: Iterable[str]
) -> dict[str, Any]:
    cohort = list(ids)
    candidate_only = sum(bool(candidate.get(case_id)) and not bool(reference.get(case_id)) for case_id in cohort)
    reference_only = sum(bool(reference.get(case_id)) and not bool(candidate.get(case_id)) for case_id in cohort)
    both_correct = sum(bool(candidate.get(case_id)) and bool(reference.get(case_id)) for case_id in cohort)
    both_wrong = len(cohort) - candidate_only - reference_only - both_correct
    return {
        "candidateOnlyCorrect": candidate_only,
        "referenceOnlyCorrect": reference_only,
        "bothCorrect": both_correct,
        "bothWrong": both_wrong,
        "rescues": candidate_only,
        "harms": reference_only,
        "net": candidate_only - reference_only,
        "delta": (candidate_only - reference_only) / len(cohort) if cohort else 0.0,
        "discordant": candidate_only + reference_only,
        "oneSidedExactMcNemarP": one_sided_exact_mcnemar(candidate_only, reference_only),
        "twoSidedExactMcNemarP": two_sided_exact_mcnemar(candidate_only, reference_only),
    }


def evaluate_answers(
    answers: Mapping[str, str],
    fixed_ids: list[str],
    question_by_id: Mapping[str, dict[str, Any]],
    gold: Mapping[str, dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, bool], dict[str, str | None]]:
    correctness: dict[str, bool] = {}
    mapped_options: dict[str, str | None] = {}
    missing = 0
    for case_id in fixed_ids:
        answer = answers.get(case_id)
        if answer is None:
            missing += 1
            mapped = None
        else:
            options = parse_mcq_options(str(question_by_id[case_id].get("prompt") or ""))
            mapped = match_answer_to_option(answer, options)
        correct = normalize_correct_option((gold[case_id].get("privateGold") or {}).get("correctOptionId"))
        mapped_options[case_id] = mapped
        correctness[case_id] = bool(mapped and mapped == correct)
    passed = sum(correctness.values())
    score = {
        "pass": passed,
        "fail": len(fixed_ids) - passed,
        "total": len(fixed_ids),
        "accuracy": passed / len(fixed_ids) if fixed_ids else 0.0,
        "missing": missing,
        "unmapped": sum(
            case_id in answers and not mapped_options[case_id]
            for case_id in fixed_ids
        ),
    }
    return score, correctness, mapped_options


def switch_outcomes(
    candidate: Mapping[str, bool],
    base: Mapping[str, bool],
    switch_ids: Iterable[str],
    fixed_ids: list[str],
) -> dict[str, Any]:
    all_switches = list(switch_ids)
    fixed_set = set(fixed_ids)
    cohort = [case_id for case_id in all_switches if case_id in fixed_set]
    rescues = sum(not base[case_id] and candidate[case_id] for case_id in cohort)
    harms = sum(base[case_id] and not candidate[case_id] for case_id in cohort)
    wrong_to_wrong = sum(not base[case_id] and not candidate[case_id] for case_id in cohort)
    correct_to_correct = sum(base[case_id] and candidate[case_id] for case_id in cohort)
    return {
        "switches": len(cohort),
        "switchesOutsideFixedM": len(all_switches) - len(cohort),
        "rescues": rescues,
        "harms": harms,
        "wrongToWrong": wrong_to_wrong,
        "correctToCorrect": correct_to_correct,
        "net": rescues - harms,
        "rescuePrecision": rescues / len(cohort) if cohort else None,
        "harmRate": harms / len(cohort) if cohort else None,
        "oneSidedExactMcNemarP": one_sided_exact_mcnemar(rescues, harms),
        "twoSidedExactMcNemarP": two_sided_exact_mcnemar(rescues, harms),
    }


def per_domain_report(
    candidate: Mapping[str, bool],
    base: Mapping[str, bool],
    fixed_ids: list[str],
    question_by_id: Mapping[str, dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], bool]:
    domains: dict[str, list[str]] = defaultdict(list)
    for case_id in fixed_ids:
        domains[str(question_by_id[case_id].get("benchmarkId") or "unknown")].append(case_id)
    report: dict[str, dict[str, Any]] = {}
    for domain, ids in sorted(domains.items()):
        base_pass = sum(base[case_id] for case_id in ids)
        candidate_pass = sum(candidate[case_id] for case_id in ids)
        pair = paired_correctness(candidate, base, ids)
        report[domain] = {
            "n": len(ids),
            "basePass": base_pass,
            "candidatePass": candidate_pass,
            "deltaPoints": candidate_pass - base_pass,
            "deltaAccuracy": (candidate_pass - base_pass) / len(ids),
            "rescues": pair["rescues"],
            "harms": pair["harms"],
            "net": pair["net"],
            "nonNegativeDelta": candidate_pass >= base_pass,
        }
    return report, all(row["nonNegativeDelta"] for row in report.values())


def promotion_gate(
    metrics: Mapping[str, Any], *, integrity_ok: bool, blind_elapsed_sec: float
) -> dict[str, Any]:
    switch = metrics["switchOutcomes"]
    gates = {
        "combinationAndIntegrity": integrity_ok,
        "scoreAtLeast588": int(metrics["score"]["pass"]) >= MIN_PROMOTION_SCORE,
        "netAtLeast22": int(switch["net"]) >= MIN_PROMOTION_NET,
        "harmsAtMost4": int(switch["harms"]) <= MAX_PROMOTION_HARMS,
        "harmsAtMostFloorRescuesOver4": int(switch["harms"]) <= int(switch["rescues"]) // 4,
        "oneSidedPAtMostPoint05": float(switch["oneSidedExactMcNemarP"]) <= 0.05,
        "noNegativePerDomainDelta": bool(metrics["perDomainGuard"]),
        "blindRuntimeAtMost650Sec": math.isfinite(blind_elapsed_sec)
        and blind_elapsed_sec <= MAX_BLIND_RUNTIME_SEC,
    }
    unmet = [name for name, passed in gates.items() if not passed]
    return {"eligible": not unmet, "checks": gates, "unmetConditions": unmet}


def select_development_promotion(
    policy_metrics: Mapping[str, Mapping[str, Any]],
    *,
    integrity_ok: bool,
    blind_elapsed_sec: float,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any] | None]:
    gates = {
        name: promotion_gate(
            policy_metrics[name], integrity_ok=integrity_ok, blind_elapsed_sec=blind_elapsed_sec
        )
        for name in PROMOTION_NAMES
    }
    eligible = [name for name in PROMOTION_NAMES if gates[name]["eligible"]]
    if not eligible:
        return gates, None
    selected = min(
        eligible,
        key=lambda name: (
            -int(policy_metrics[name]["score"]["pass"]),
            int(policy_metrics[name]["switchOutcomes"]["harms"]),
            int(policy_metrics[name]["switchOutcomes"]["switches"]),
            PROMOTION_PRIORITY[name],
        ),
    )
    return gates, {
        "policy": selected,
        "selectionRule": (
            "highest score; then lowest harm; then fewer switches; then fixed priority "
            "intersection, blind_only, union"
        ),
        "score": policy_metrics[selected]["score"]["pass"],
        "harms": policy_metrics[selected]["switchOutcomes"]["harms"],
        "switches": policy_metrics[selected]["switchOutcomes"]["switches"],
    }


def strict_switch_ids(strict_campaign: Path, eligible_ids: list[str]) -> list[str]:
    lines = (strict_campaign / "solver/output/decisions.log").read_text(encoding="utf-8").splitlines()
    decisions: list[dict[str, str]] = []
    for line_number, line in enumerate(lines, 1):
        match = DECISION_RE.fullmatch(line)
        if not match:
            raise ValueError(f"invalid V3 decision line {line_number}")
        decisions.append({key: value.strip() for key, value in match.groupdict().items()})
    if [row["id"] for row in decisions] != eligible_ids:
        raise ValueError("V3 decision IDs/order mismatch")
    return [
        row["id"]
        for row in decisions
        if row["gate"] == "VALID" and row["action"] == "SWITCH"
    ]


def proposed_preferences(blind_campaign: Path, eligible_ids: list[str]) -> list[str]:
    certificates = load_jsonl(blind_campaign / "veto/output/certificates.jsonl")
    mappings = load_jsonl(blind_campaign / "control/role_mapping.jsonl")
    if [row.get("id") for row in certificates] != eligible_ids:
        raise ValueError("blind certificate IDs/order mismatch")
    if [row.get("id") for row in mappings] != eligible_ids:
        raise ValueError("blind role-mapping IDs/order mismatch")
    proposed: list[str] = []
    for certificate, mapping in zip(certificates, mappings, strict=True):
        proposed_side = "PREFER_LEFT" if mapping.get("leftRole") == "PROPOSED" else "PREFER_RIGHT"
        if {mapping.get("leftRole"), mapping.get("rightRole")} != {"INCUMBENT", "PROPOSED"}:
            raise ValueError(f"invalid hidden role mapping for {certificate.get('id')}")
        if certificate.get("preference") == proposed_side:
            proposed.append(str(certificate["id"]))
    return proposed


def trace_thread_ids(path: Path) -> list[str]:
    ids: list[str] = []
    started = 0
    for raw in path.read_text(encoding="utf-8").split("\n"):
        if not raw.strip():
            continue
        event = json.loads(raw)
        if not isinstance(event, dict) or event.get("type") != "thread.started":
            continue
        started += 1
        thread_id = event.get("thread_id") or event.get("threadId")
        if thread_id is None and isinstance(event.get("thread"), dict):
            thread_id = event["thread"].get("id")
        if not isinstance(thread_id, str) or not thread_id.strip():
            raise ValueError(f"malformed thread.started event: {path}")
        if thread_id not in ids:
            ids.append(thread_id)
    if started != 1 or len(ids) != 1:
        raise ValueError(f"expected exactly one thread identity: {path}")
    return ids


def audit_gold_free_input(blind_campaign: Path) -> dict[str, Any]:
    input_dir = blind_campaign / "veto/input"
    expected_names = {
        "RUN_INSTRUCTIONS.md",
        "candidate_pairs.jsonl",
        "expected_certificate_ids.json",
        "questions.jsonl",
    }
    observed = {path.name for path in input_dir.iterdir()}
    if observed != expected_names:
        raise ValueError("blind model input file inventory mismatch")
    if any(path.is_symlink() or not path.is_file() for path in input_dir.iterdir()):
        raise ValueError("blind model input must contain regular non-symlink files only")

    questions = load_jsonl(input_dir / "questions.jsonl")
    pairs = load_jsonl(input_dir / "candidate_pairs.jsonl")
    expected = load_json(input_dir / "expected_certificate_ids.json")
    if any(set(row) != {"id", "responseFormat", "language", "prompt"} for row in questions):
        raise ValueError("blind questions expose fields outside the public schema")
    if any(set(row) != {"id", "leftAnswer", "rightAnswer"} for row in pairs):
        raise ValueError("blind pairs expose fields outside the public schema")
    if set(expected) != {"count", "ids"}:
        raise ValueError("blind expected-certificate file schema mismatch")
    forbidden_structured_keys = {
        "privategold",
        "correctoptionid",
        "goldanswer",
        "groundtruth",
        "answerkey",
        "referenceanswer",
        "correctanswer",
        "incumbent",
        "proposed",
        "auxiliary",
        "consensus",
    }
    structured_keys = {
        str(key).replace("_", "").casefold()
        for value in (questions, pairs, [expected])
        for row in value
        for key in row
    }
    if structured_keys & forbidden_structured_keys:
        raise ValueError("blind model input exposes a forbidden structured provenance key")
    return {
        "passed": True,
        "modelMountedFileNames": sorted(observed),
        "exactPublicSchemasOnly": True,
        "privateGoldFieldsAbsent": True,
        "hiddenRoleMappingMounted": False,
    }


def audit_strict_campaign(strict_campaign: Path) -> dict[str, Any]:
    integrity = verify_frozen_inputs(campaign_dir=strict_campaign, role="solver")
    if integrity.get("freezeSha256") != EXPECTED_V3_FREEZE_SHA256:
        raise ValueError("strict campaign is not the frozen V3 input")
    validation = validate_overlap_adjudication(strict_campaign, write_report=False)
    if not validation.get("passed"):
        raise ValueError("strict V3 artifact validation did not pass")
    receipt = load_json(strict_campaign / "solver/run_receipt.json")
    receipt_sha = verify_self_hash(receipt, "receiptSha256", "strict V3 receipt")
    if receipt_sha != EXPECTED_V3_RECEIPT_SHA256:
        raise ValueError("strict campaign is not the accepted V3 invocation")
    answers_path = strict_campaign / "solver/output/answers.jsonl"
    decisions_path = strict_campaign / "solver/output/decisions.log"
    trace_path = strict_campaign / "solver/codex_trace.jsonl"
    observed = {
        "answersSha256": sha256_file(answers_path),
        "decisionsSha256": sha256_file(decisions_path),
        "traceSha256": sha256_file(trace_path),
    }
    expected = {
        "answersSha256": EXPECTED_V3_ANSWERS_SHA256,
        "decisionsSha256": EXPECTED_V3_DECISIONS_SHA256,
        "traceSha256": EXPECTED_V3_TRACE_SHA256,
    }
    if observed != expected:
        raise ValueError("strict V3 accepted artifact hash mismatch")
    process = receipt.get("process") if isinstance(receipt.get("process"), dict) else {}
    artifact = receipt.get("artifactValidation") if isinstance(receipt.get("artifactValidation"), dict) else {}
    checks = {
        "accepted": receipt.get("status") == "accepted",
        "oneCall": receipt.get("semanticModelInvocations") == 1,
        "modelConfig": (
            receipt.get("model"), receipt.get("reasoningEffort"), receipt.get("verbosity")
        ) == ("gpt-5.6-luna", "high", "low"),
        "process": process.get("exitCode") == 0 and process.get("timedOut") is False,
        "inputIntegrity": (receipt.get("inputIntegrity") or {}).get("passed") is True,
        "isolation": (receipt.get("isolationProbe") or {}).get("passed") is True,
        "policy": (receipt.get("policyAudit") or {}).get("passed") is True,
        "artifact": artifact.get("passed") is True,
        "answerReceiptHash": artifact.get("answersSha256") == observed["answersSha256"],
        "decisionReceiptHash": artifact.get("decisionsSha256") == observed["decisionsSha256"],
    }
    if not all(checks.values()):
        raise ValueError("strict V3 receipt/integrity check did not pass")
    return {
        "passed": True,
        "checks": checks,
        "freezeSha256": integrity["freezeSha256"],
        "receiptSha256": receipt_sha,
        **observed,
        "threadIds": trace_thread_ids(trace_path),
        "elapsedSec": process.get("elapsedSec"),
    }


def audit_blind_campaign(blind_campaign: Path, strict_campaign: Path) -> dict[str, Any]:
    freeze, paths, input_hashes = verify_frozen_bundle(blind_campaign)
    if Path(str(freeze.get("sourceCampaign") or "")).resolve() != strict_campaign.resolve():
        raise ValueError("blind campaign source path is not the strict V3 campaign")
    if freeze.get("sourceFreezeSha256") != EXPECTED_V3_FREEZE_SHA256:
        raise ValueError("blind campaign is not bound to the strict V3 freeze")
    validation = validate_blind_pairwise_veto(blind_campaign, write_report=False)
    if not validation.get("passed"):
        raise ValueError("blind certificate artifact validation did not pass")
    receipt = load_json(paths["receipt"])
    receipt_sha = verify_self_hash(receipt, "receiptSha256", "blind receipt")
    process = receipt.get("process") if isinstance(receipt.get("process"), dict) else {}
    artifacts = receipt.get("artifacts") if isinstance(receipt.get("artifacts"), dict) else {}
    policy = receipt.get("policyAudit") if isinstance(receipt.get("policyAudit"), dict) else {}
    artifact = receipt.get("artifactValidation") if isinstance(receipt.get("artifactValidation"), dict) else {}
    trace_path = paths["trace"]
    checks = {
        "accepted": receipt.get("status") == "accepted",
        "protocol": receipt.get("protocol") == freeze.get("protocol"),
        "oneCall": receipt.get("semanticModelInvocations") == 1,
        "freeze": receipt.get("freezeSha256") == freeze.get("freezeSha256"),
        "inputs": receipt.get("inputFileSha256") == input_hashes,
        "modelConfig": receipt.get("executionConfig") == freeze.get("executionConfig"),
        "process": process.get("exitCode") == 0 and process.get("timedOut") is False,
        "positiveRuntime": isinstance(process.get("elapsedSec"), (int, float))
        and not isinstance(process.get("elapsedSec"), bool)
        and float(process["elapsedSec"]) > 0,
        "isolation": (receipt.get("isolationProbe") or {}).get("passed") is True,
        "policy": policy.get("passed") is True and policy.get("rawWebSearchEventCount") == 0,
        "oneThread": policy.get("threadStartedEventCount") == 1
        and len(policy.get("threadIds") or []) == 1,
        "artifact": artifact.get("passed") is True,
        "certificateHash": artifacts.get("certificatesSha256") == sha256_file(paths["certificates"]),
        "traceHash": artifacts.get("rawTraceSha256") == sha256_file(trace_path),
        "acceptedArtifact": receipt.get("acceptedArtifact") == "output/certificates.jsonl",
    }
    if not all(checks.values()):
        raise ValueError("blind receipt/integrity check did not pass")
    gold_free = audit_gold_free_input(blind_campaign)
    return {
        "passed": True,
        "checks": checks,
        "freezeSha256": freeze["freezeSha256"],
        "receiptSha256": receipt_sha,
        "certificatesSha256": artifacts["certificatesSha256"],
        "traceSha256": artifacts["rawTraceSha256"],
        "threadIds": list(policy["threadIds"]),
        "validationReport": validation,
        "elapsedSec": float(process["elapsedSec"]),
        "goldFreeUpstreamInput": gold_free,
    }


def candidate_majority_answers(
    source: Mapping[str, Any], questions: list[dict[str, Any]]
) -> tuple[dict[str, str], dict[str, Any]]:
    ids = list(source["ids"])
    eligible_ids = list(source["eligibleIds"])
    eligible_set = set(eligible_ids)
    candidates: Mapping[str, Mapping[str, str]] = source["candidates"]
    question_by_id = {str(row["id"]): row for row in questions}
    recomputed: list[str] = []
    for case_id in ids:
        question = question_by_id[case_id]
        prompt = str(question.get("prompt") or "")
        options = parse_mcq_options(prompt) if question.get("responseFormat") == "mcq" else {}
        mapped = [
            match_answer_to_option(candidates[name][case_id], options) if options else None
            for name in ("base", "auxiliary_1", "auxiliary_2")
        ]
        if all(mapped) and mapped[1] == mapped[2] and mapped[1] != mapped[0]:
            recomputed.append(case_id)
    if recomputed != eligible_ids or len(recomputed) != EXPECTED_ELIGIBLE_ROWS:
        raise ValueError("source option mappings do not reproduce the exact 247-row majority cohort")
    answers = {
        case_id: (
            candidates["auxiliary_1"][case_id]
            if case_id in eligible_set
            else candidates["base"][case_id]
        )
        for case_id in ids
    }
    rows = [{"id": case_id, "finalAnswer": answers[case_id]} for case_id in ids]
    return answers, {
        "passed": True,
        "definition": (
            "collision-safe three-draft plurality: use d3/d4 consensus iff both canonical option IDs "
            "agree and differ from d1; otherwise keep d1"
        ),
        "knownMethodRole": "candidate_majority_baseline",
        "fullRows": len(ids),
        "eligibleRows": len(eligible_ids),
        "eligibleIdsSha256": canonical_digest(eligible_ids),
        "candidateAnswerSourceSha256": source["candidateHashes"],
        "reconstructedAnswersCanonicalSha256": canonical_digest(rows),
        "allEligibleD3EqualsD4AndDiffersD1": True,
        "allNoneligibleRowsKeepD1": all(
            answers[case_id] == candidates["base"][case_id]
            for case_id in ids
            if case_id not in eligible_set
        ),
    }


def expected_policy_switches(
    strict_campaign: Path, blind_campaign: Path, eligible_ids: list[str]
) -> dict[str, list[str]]:
    strict = strict_switch_ids(strict_campaign, eligible_ids)
    blind = proposed_preferences(blind_campaign, eligible_ids)
    strict_set = set(strict)
    blind_set = set(blind)
    return {
        "base": [],
        "blind_only": blind,
        "intersection": [case_id for case_id in eligible_ids if case_id in strict_set & blind_set],
        "union": [case_id for case_id in eligible_ids if case_id in strict_set | blind_set],
    }


def audit_combination(
    combination_dir: Path,
    strict_campaign: Path,
    blind_campaign: Path,
    source: Mapping[str, Any],
    expected_switches: Mapping[str, list[str]],
    strict_audit: Mapping[str, Any],
    blind_audit: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, dict[str, str]], dict[str, list[str]]]:
    receipt = load_json(combination_dir / "combination_receipt.json")
    receipt_sha = verify_self_hash(receipt, "receiptSha256", "combination receipt")
    checks = {
        "schemaVersion": receipt.get("schemaVersion") == 1,
        "status": receipt.get("status") == "accepted",
        "protocol": receipt.get("protocol") == COMBINATION_PROTOCOL,
        "goldAccess": receipt.get("goldAccess") is False,
        "synthesis": receipt.get("synthesis") is False,
        "expectedRows": receipt.get("expectedRows") == EXPECTED_ROWS,
        "eligibleRows": receipt.get("eligibleRows") == EXPECTED_ELIGIBLE_ROWS,
    }
    if not all(checks.values()):
        raise ValueError("combination receipt header/integrity check did not pass")

    implementations = receipt.get("implementationHashes")
    if not isinstance(implementations, dict) or not implementations:
        raise ValueError("combination receipt implementation hashes are missing")
    combiner_path = (REPO_ROOT / "tools/combine_blind_pairwise_veto.py").resolve()
    if implementations.get(str(combiner_path)) != sha256_file(combiner_path):
        raise ValueError("combination receipt does not bind the exact combiner implementation")
    for raw_path, claimed in implementations.items():
        path = Path(str(raw_path))
        if not path.is_file() or sha256_file(path) != claimed:
            raise ValueError(f"combination implementation hash mismatch: {path}")

    strict_freeze = load_json(strict_campaign / "solver/freeze.json")
    blind_freeze = load_json(blind_campaign / "veto/freeze.json")
    source_bindings = receipt.get("sourceBindings")
    expected_source_bindings = {
        "expectedIdsSha256": strict_freeze.get("expectedIdsSha256"),
        "eligibleIdsSha256": strict_freeze.get("eligibleIdsSha256"),
        "questionsSha256": strict_freeze.get("questionsSha256"),
        "overlapManifestSha256": strict_freeze.get("overlapManifestSha256"),
        "candidateAnswersSha256": source["candidateHashes"],
        "candidateBundleSha256": strict_freeze.get("candidateBundleSha256"),
        "candidateProvenanceSha256": strict_freeze.get("candidateProvenanceSha256"),
        "blindRoleMappingSha256": blind_freeze.get("roleMappingSha256"),
        "blindRotationControlSha256": blind_freeze.get("rotationControlSha256"),
        "blindPairsSha256": blind_freeze.get("pairsSha256"),
    }
    if source_bindings != expected_source_bindings:
        raise ValueError("combination source bindings mismatch")

    upstream = receipt.get("upstream")
    if not isinstance(upstream, dict) or set(upstream) != {"strict", "blind"}:
        raise ValueError("combination upstream inventory mismatch")
    strict_upstream = upstream["strict"]
    blind_upstream = upstream["blind"]
    if not isinstance(strict_upstream, dict) or not isinstance(blind_upstream, dict):
        raise ValueError("combination upstream bindings are malformed")
    strict_switches = strict_switch_ids(strict_campaign, list(source["eligibleIds"]))
    strict_expected = {
        "campaign": str(strict_campaign),
        "freezeSha256": strict_audit["freezeSha256"],
        "freezeFileSha256": sha256_file(strict_campaign / "solver/freeze.json"),
        "receiptSha256": strict_audit["receiptSha256"],
        "receiptFileSha256": sha256_file(strict_campaign / "solver/run_receipt.json"),
        "validationReportSha256": sha256_file(strict_campaign / "solver/overlap_validation.json"),
        "rawTraceSha256": strict_audit["traceSha256"],
        "answersSha256": strict_audit["answersSha256"],
        "decisionsSha256": strict_audit["decisionsSha256"],
        "switchIdsSha256": canonical_digest(strict_switches),
    }
    for key, expected in strict_expected.items():
        if strict_upstream.get(key) != expected:
            raise ValueError(f"combination strict upstream binding mismatch: {key}")
    upstream_provenance = strict_upstream.get("candidateProvenance")
    frozen_provenance = strict_freeze.get("candidateProvenance")
    candidate_indices = strict_freeze.get("candidateIndices")
    if not (
        isinstance(upstream_provenance, dict)
        and isinstance(frozen_provenance, dict)
        and isinstance(candidate_indices, dict)
        and set(upstream_provenance) == set(frozen_provenance) == {"base", "auxiliary_1", "auxiliary_2"}
    ):
        raise ValueError("combination strict candidate provenance inventory mismatch")
    source_campaign = Path(str(strict_freeze.get("sourceCampaign") or "")).resolve()
    for name, summary in upstream_provenance.items():
        frozen = frozen_provenance[name]
        if not isinstance(summary, dict) or not isinstance(frozen, dict):
            raise ValueError(f"combination candidate provenance is malformed: {name}")
        index = candidate_indices.get(name)
        artifacts = frozen.get("artifacts")
        if not isinstance(index, int) or not isinstance(artifacts, dict):
            raise ValueError(f"frozen candidate provenance is malformed: {name}")
        expected_summary = {
            "candidateIndex": index,
            "answersSha256": source["candidateHashes"][name],
            "receiptSha256": frozen.get("receiptSha256"),
            "receiptFileSha256": sha256_file(strict_campaign / artifacts["runReceipt"]["path"]),
            "validationFileSha256": sha256_file(
                strict_campaign / artifacts["answerValidation"]["path"]
            ),
            "rawTraceSha256": sha256_file(
                source_campaign / f"drafts/d{index}/solver/codex_trace.jsonl"
            ),
        }
        for key, expected in expected_summary.items():
            if summary.get(key) != expected:
                raise ValueError(f"combination candidate provenance binding mismatch: {name}/{key}")
        if not isinstance(summary.get("threadIds"), list) or len(summary["threadIds"]) != 1:
            raise ValueError(f"combination candidate thread binding mismatch: {name}")
    if strict_upstream.get("threadIds") != strict_audit["threadIds"]:
        raise ValueError("combination strict thread binding mismatch")

    blind_expected = {
        "campaign": str(blind_campaign),
        "freezeSha256": blind_audit["freezeSha256"],
        "freezeFileSha256": sha256_file(blind_campaign / "veto/freeze.json"),
        "receiptSha256": blind_audit["receiptSha256"],
        "receiptFileSha256": sha256_file(blind_campaign / "veto/run_receipt.json"),
        "validationReportSha256": sha256_file(blind_campaign / "veto/certificate_validation.json"),
        "rawTraceSha256": blind_audit["traceSha256"],
        "certificatesSha256": blind_audit["certificatesSha256"],
        "roleMappingSha256": blind_freeze.get("roleMappingSha256"),
    }
    for key, expected in blind_expected.items():
        if blind_upstream.get(key) != expected:
            raise ValueError(f"combination blind upstream binding mismatch: {key}")
    if blind_upstream.get("threadIds") != blind_audit["threadIds"]:
        raise ValueError("combination blind thread binding mismatch")

    policy_receipts = receipt.get("policies")
    if not isinstance(policy_receipts, dict) or set(policy_receipts) != set(POLICY_NAMES):
        raise ValueError("combination receipt policy inventory mismatch")
    expected_ids = list(source["ids"])
    eligible_ids = list(source["eligibleIds"])
    base = source["candidates"]["base"]
    proposed = source["candidates"]["auxiliary_1"]
    answers_by_policy: dict[str, dict[str, str]] = {}
    switches_by_policy: dict[str, list[str]] = {}
    for name in POLICY_NAMES:
        policy = policy_receipts[name]
        if not isinstance(policy, dict):
            raise ValueError(f"combination receipt policy {name} is malformed")
        if policy.get("definition") != POLICY_DEFINITIONS[name]:
            raise ValueError(f"combination receipt policy definition mismatch: {name}")
        expected_answer_relative = f"policies/{name}/answers.jsonl"
        expected_switch_relative = f"policies/{name}/switch_ids.json"
        answers_path = safe_relative_file(
            combination_dir, policy.get("answersPath"), expected_answer_relative, f"{name} answers"
        )
        switch_path = safe_relative_file(
            combination_dir, policy.get("switchIdsPath"), expected_switch_relative, f"{name} switches"
        )
        _, answers = read_answer_artifact(
            answers_path,
            expected_ids,
            claimed_sha256=str(policy.get("answersSha256") or ""),
            label=name,
        )
        switches = read_switch_artifact(
            switch_path,
            eligible_ids,
            claimed_sha256=str(policy.get("switchIdsFileSha256") or ""),
            label=name,
        )
        if policy.get("switchRows") != len(switches):
            raise ValueError(f"{name} switch row count is not bound")
        if policy.get("switchIds") != switches:
            raise ValueError(f"{name} embedded switch IDs mismatch")
        if policy.get("switchIdsSha256") != canonical_digest(switches):
            raise ValueError(f"{name} switch ID digest mismatch")
        if switches != expected_switches[name]:
            raise ValueError(f"{name} switch policy does not match preregistered mechanical rule")
        switch_set = set(switches)
        expected_answers = {
            case_id: proposed[case_id] if case_id in switch_set else base[case_id]
            for case_id in expected_ids
        }
        if answers != expected_answers:
            raise ValueError(f"{name} answers are not exact base/proposed copies")
        answers_by_policy[name] = answers
        switches_by_policy[name] = switches
    return {
        "passed": True,
        "checks": checks,
        "receiptSha256": receipt_sha,
        "implementationHashes": implementations,
        "goldAccess": False,
        "synthesis": False,
    }, answers_by_policy, switches_by_policy


def build_fixed_cohort(
    questions: list[dict[str, Any]], gold: Mapping[str, dict[str, Any]]
) -> tuple[list[str], dict[str, dict[str, Any]]]:
    question_by_id = {str(row["id"]): row for row in questions}
    if len(question_by_id) != len(questions):
        raise ValueError("question IDs are duplicated")
    fixed_ids = sorted(
        case_id
        for case_id, question in question_by_id.items()
        if question.get("responseFormat") == "mcq"
        and case_id in gold
        and normalize_correct_option((gold[case_id].get("privateGold") or {}).get("correctOptionId"))
    )
    if len(fixed_ids) != EXPECTED_FIXED_M_ROWS:
        raise ValueError(f"fixed private M row count mismatch: {len(fixed_ids)}")
    if canonical_digest(fixed_ids) != EXPECTED_FIXED_M_IDS_SHA256:
        raise ValueError("fixed private M IDs hash mismatch")
    return fixed_ids, question_by_id


def analyze(
    *,
    strict_campaign: Path,
    blind_campaign: Path,
    combination_dir: Path,
    registry_path: Path,
    existing_universal: Path | None,
) -> dict[str, Any]:
    strict_campaign = strict_campaign.resolve()
    blind_campaign = blind_campaign.resolve()
    combination_dir = combination_dir.resolve()
    registry_path = registry_path.resolve()

    # Complete every public/gold-free audit before opening the private registry.
    source = source_bundle(strict_campaign)
    if len(source["ids"]) != EXPECTED_ROWS or len(source["eligibleIds"]) != EXPECTED_ELIGIBLE_ROWS:
        raise ValueError("strict source inventory mismatch")
    questions = list(source["questions"])
    strict_audit = audit_strict_campaign(strict_campaign)
    blind_audit = audit_blind_campaign(blind_campaign, strict_campaign)
    expected_switches = expected_policy_switches(strict_campaign, blind_campaign, list(source["eligibleIds"]))
    combination_audit, policy_answers, policy_switches = audit_combination(
        combination_dir,
        strict_campaign,
        blind_campaign,
        source,
        expected_switches,
        strict_audit,
        blind_audit,
    )
    candidate_majority, majority_audit = candidate_majority_answers(source, questions)

    if sha256_file(registry_path) != EXPECTED_REGISTRY_SHA256:
        raise ValueError("private registry hash mismatch")
    gold = private_exam_rows(registry_path)
    fixed_ids, question_by_id = build_fixed_cohort(questions, gold)
    expected_ids = list(source["ids"])

    _, v3_answers = read_answer_artifact(
        strict_campaign / "solver/output/answers.jsonl",
        expected_ids,
        claimed_sha256=EXPECTED_V3_ANSWERS_SHA256,
        label="v3_strict",
    )
    systems: dict[str, Mapping[str, str]] = {
        "base": source["candidates"]["base"],
        "candidate_majority": candidate_majority,
        **policy_answers,
        "v3_strict": v3_answers,
    }
    external_hash: str | None = None
    if existing_universal is not None:
        existing_path = existing_universal.resolve()
        external_hash = sha256_file(existing_path)
        _, existing_answers = read_answer_artifact(
            existing_path,
            expected_ids,
            claimed_sha256=external_hash,
            label="existing_universal",
        )
        systems["existing_universal"] = existing_answers

    scores: dict[str, dict[str, Any]] = {}
    correctness: dict[str, dict[str, bool]] = {}
    mappings: dict[str, dict[str, str | None]] = {}
    for name, answers in systems.items():
        scores[name], correctness[name], mappings[name] = evaluate_answers(
            answers, fixed_ids, question_by_id, gold
        )
    if scores["v3_strict"]["pass"] != 587:
        raise ValueError("frozen V3 strict score is not the expected 587/941")

    v3_switches = strict_switch_ids(strict_campaign, list(source["eligibleIds"]))
    system_switches: dict[str, list[str]] = {
        "candidate_majority": list(source["eligibleIds"]),
        **policy_switches,
        "v3_strict": v3_switches,
    }
    policy_metrics: dict[str, dict[str, Any]] = {}
    per_domain: dict[str, dict[str, dict[str, Any]]] = {}
    vs_base: dict[str, dict[str, Any]] = {}
    pairwise_v3: dict[str, dict[str, Any]] = {}
    for name, switches in system_switches.items():
        outcomes = switch_outcomes(correctness[name], correctness["base"], switches, fixed_ids)
        paired = paired_correctness(correctness[name], correctness["base"], fixed_ids)
        if outcomes["rescues"] != paired["rescues"] or outcomes["harms"] != paired["harms"]:
            raise ValueError(f"{name} changed outside its frozen switch set")
        domain, guard = per_domain_report(
            correctness[name], correctness["base"], fixed_ids, question_by_id
        )
        per_domain[name] = domain
        vs_base[name] = paired
        pairwise_v3[name] = paired_correctness(correctness[name], correctness["v3_strict"], fixed_ids)
        policy_metrics[name] = {
            "score": scores[name],
            "switchOutcomes": outcomes,
            "vsBase": paired,
            "perDomainGuard": guard,
        }

    if "existing_universal" in correctness:
        vs_base["existing_universal"] = paired_correctness(
            correctness["existing_universal"], correctness["base"], fixed_ids
        )
        pairwise_v3["existing_universal"] = paired_correctness(
            correctness["existing_universal"], correctness["v3_strict"], fixed_ids
        )

    gates, selected = select_development_promotion(
        policy_metrics,
        integrity_ok=bool(
            strict_audit["passed"] and blind_audit["passed"] and combination_audit["passed"]
        ),
        blind_elapsed_sec=float(blind_audit["elapsedSec"]),
    )

    # candidate_majority is d3 on every eligible disagreement and d1 elsewhere;
    # compute the literal d1/d3/d4 pass@3 independently for the non-deployable ceiling.
    candidate_maps: dict[str, dict[str, str | None]] = {}
    for candidate_name in ("base", "auxiliary_1", "auxiliary_2"):
        _, _, candidate_maps[candidate_name] = evaluate_answers(
            source["candidates"][candidate_name], fixed_ids, question_by_id, gold
        )
    oracle_correctness = {
        case_id: any(
            candidate_maps[name][case_id]
            == normalize_correct_option((gold[case_id].get("privateGold") or {}).get("correctOptionId"))
            for name in ("base", "auxiliary_1", "auxiliary_2")
        )
        for case_id in fixed_ids
    }
    oracle_pass = sum(oracle_correctness.values())

    return {
        "analysisType": "private_result_aware_development_policy_selection",
        "fixedCohort": {
            "definition": (
                "all frozen public MCQ rows with nonempty private correctOptionId; missing/unmapped answers count wrong"
            ),
            "n": len(fixed_ids),
            "sortedIdsSha256": canonical_digest(fixed_ids),
            "registrySha256": sha256_file(registry_path),
        },
        "integrity": {
            "passed": True,
            "strictV3": strict_audit,
            "blindVeto": blind_audit,
            "goldFreeCombination": combination_audit,
            "privateGoldOpenedOnlyAfterUpstreamAudits": True,
            "sourceCandidateHashes": source["candidateHashes"],
        },
        "candidateMajorityEquivalence": majority_audit,
        "scores": scores,
        "switchOutcomesVsBase": {
            name: metrics["switchOutcomes"] for name, metrics in policy_metrics.items()
        },
        "pairedVsBase": vs_base,
        "pairwiseDiscordanceVsV3": pairwise_v3,
        "perDomainVsBase": per_domain,
        "oraclePassAt3": {
            "role": "non_deployable_private_gold_upper_bound",
            "promotionCandidate": False,
            "definition": "correct iff at least one of frozen d1/d3/d4 maps to the private correct option",
            "pass": oracle_pass,
            "fail": len(fixed_ids) - oracle_pass,
            "total": len(fixed_ids),
            "accuracy": oracle_pass / len(fixed_ids),
            "incrementalPassOverBase": oracle_pass - scores["base"]["pass"],
        },
        "promotionGate": gates,
        "developmentPromotion": selected,
        "selectionNote": (
            "Only blind_only, intersection, and union are eligible for selection. "
            "candidate_majority and oracle_pass_at_3 are comparison diagnostics, not promotion candidates."
        ),
        "existingUniversalArtifactSha256": external_hash,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict-campaign", type=Path, required=True)
    parser.add_argument("--blind-campaign", type=Path, required=True)
    parser.add_argument("--combination-dir", type=Path, required=True)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--existing-universal", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = analyze(
        strict_campaign=args.strict_campaign,
        blind_campaign=args.blind_campaign,
        combination_dir=args.combination_dir,
        registry_path=args.registry,
        existing_universal=args.existing_universal,
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
