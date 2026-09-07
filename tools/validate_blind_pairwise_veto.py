#!/usr/bin/env python3
"""Fail-closed validation for a role-blind pairwise veto certificate file.

This validator reads no private gold.  It verifies the frozen public input,
the hidden deterministic LEFT/RIGHT mapping, exact certificate coverage and
order, tagged evidence receipts, prompt-local quotation receipts, and logical
consistency between per-side tests, uniqueness, and the final preference.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.prepare_blind_pairwise_veto import (
    EXPECTED_CONFLICT_ROWS,
    EXPECTED_QUESTION_ROWS,
    FROZEN_MODEL,
    FROZEN_REASONING_EFFORT,
    FROZEN_VERBOSITY,
    IMPLEMENTATION_RELATIVE_PATHS,
    PAIR_NAMES,
    PROTOCOL,
    ROTATION_SCHEME,
    SOURCE_ROLES,
    lf_jsonl_lines,
    rotation_bit,
    text_sha256,
)
from tools.prepare_plain_codex_file_benchmark import canonical_digest, sha256_file


ROOT_KEYS = {
    "id",
    "targetPolarity",
    "polarityQuote",
    "leftAssessment",
    "rightAssessment",
    "uniqueness",
    "preference",
    "comparativeReason",
}
ASSESSMENT_KEYS = {
    "candidateAnswer",
    "atomicClaim",
    "falsificationTest",
    "testOutcome",
    "status",
    "strongestCountercase",
    "countercaseOutcome",
    "evidence",
}
EVIDENCE_KEYS = {"type", "receipt"}
TARGET_POLARITIES = {
    "SELECT_CORRECT",
    "SELECT_INCORRECT",
    "SELECT_BEST",
    "SELECT_LEAST",
    "MULTI_SELECT",
    "UNRESOLVED",
}
STATUSES = {"SUPPORTED", "REFUTED", "UNRESOLVED"}
TEST_OUTCOMES = {"SURVIVED", "FAILED", "INCONCLUSIVE"}
COUNTERCASE_OUTCOMES = {"DEFEATED", "STANDS", "UNRESOLVED"}
EVIDENCE_TYPES = {"PROMPT_QUOTE", "DERIVATION", "MODEL_KNOWLEDGE", "NONE"}
UNIQUENESS_VALUES = {
    "LEFT_ONLY",
    "RIGHT_ONLY",
    "BOTH_PLAUSIBLE",
    "NEITHER_PLAUSIBLE",
    "UNRESOLVED",
}
PREFERENCES = {"PREFER_LEFT", "PREFER_RIGHT", "TIE"}
STATUS_CONTRACT = {
    "SUPPORTED": ("SURVIVED", "DEFEATED"),
    "REFUTED": ("FAILED", "STANDS"),
    "UNRESOLVED": ("INCONCLUSIVE", "UNRESOLVED"),
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl_strict(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, raw in enumerate(lf_jsonl_lines(path), 1):
        if not raw.strip():
            raise ValueError(f"blank_jsonl_line:{path.name}:{line_number}")
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError(f"non_object_jsonl_line:{path.name}:{line_number}")
        rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalized_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split()).casefold()


def prompt_contains(prompt: str, quote: str) -> bool:
    normalized_quote = normalized_text(quote)
    return bool(len(normalized_quote) >= 4 and normalized_quote in normalized_text(prompt))


def nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def add_error(errors: list[str], error: str) -> None:
    if error not in errors:
        errors.append(error)


def verify_file_hash(path: Path, expected: Any, error: str, errors: list[str]) -> None:
    if not path.is_file() or not isinstance(expected, str) or sha256_file(path) != expected:
        add_error(errors, error)


def validate_evidence(
    evidence: Any,
    *,
    prompt: str,
    label: str,
    errors: list[str],
    evidence_counts: Counter[str],
) -> str:
    if not isinstance(evidence, dict) or set(evidence) != EVIDENCE_KEYS:
        add_error(errors, f"{label}_evidence_schema")
        return "INVALID"
    evidence_type = evidence.get("type")
    receipt = evidence.get("receipt")
    if evidence_type not in EVIDENCE_TYPES:
        add_error(errors, f"{label}_evidence_type")
        return "INVALID"
    evidence_counts[evidence_type] += 1
    if evidence_type == "NONE":
        if receipt is not None:
            add_error(errors, f"{label}_none_receipt_must_be_null")
    elif evidence_type == "PROMPT_QUOTE":
        if not isinstance(receipt, dict) or set(receipt) != {"quote"} or not nonempty_string(receipt.get("quote")):
            add_error(errors, f"{label}_prompt_quote_receipt_schema")
        elif not prompt_contains(prompt, receipt["quote"]):
            add_error(errors, f"{label}_prompt_quote_not_found")
    elif evidence_type == "DERIVATION":
        if not isinstance(receipt, dict) or set(receipt) != {"premises", "steps", "conclusion"}:
            add_error(errors, f"{label}_derivation_receipt_schema")
        else:
            premises = receipt.get("premises")
            steps = receipt.get("steps")
            if not isinstance(premises, list) or not premises or any(not nonempty_string(item) for item in premises):
                add_error(errors, f"{label}_derivation_premises")
            elif any(not prompt_contains(prompt, item) for item in premises):
                add_error(errors, f"{label}_derivation_premise_not_found")
            if not isinstance(steps, list) or not steps or any(not nonempty_string(item) for item in steps):
                add_error(errors, f"{label}_derivation_steps")
            if not nonempty_string(receipt.get("conclusion")):
                add_error(errors, f"{label}_derivation_conclusion")
    elif evidence_type == "MODEL_KNOWLEDGE":
        if not isinstance(receipt, dict) or set(receipt) != {"supportedClaim", "falsificationBasis"}:
            add_error(errors, f"{label}_model_knowledge_receipt_schema")
        elif not (
            nonempty_string(receipt.get("supportedClaim"))
            and nonempty_string(receipt.get("falsificationBasis"))
        ):
            add_error(errors, f"{label}_model_knowledge_receipt_values")
    return str(evidence_type)


def validate_assessment(
    assessment: Any,
    *,
    expected_answer: str,
    prompt: str,
    label: str,
    errors: list[str],
    evidence_counts: Counter[str],
) -> str:
    if not isinstance(assessment, dict) or set(assessment) != ASSESSMENT_KEYS:
        add_error(errors, f"{label}_assessment_schema")
        return "INVALID"
    if assessment.get("candidateAnswer") != expected_answer:
        add_error(errors, f"{label}_candidate_answer_mismatch")
    for field in ("atomicClaim", "falsificationTest", "strongestCountercase"):
        if not nonempty_string(assessment.get(field)):
            add_error(errors, f"{label}_{field}_empty")
    status = assessment.get("status")
    test_outcome = assessment.get("testOutcome")
    countercase_outcome = assessment.get("countercaseOutcome")
    if status not in STATUSES:
        add_error(errors, f"{label}_status")
    if test_outcome not in TEST_OUTCOMES:
        add_error(errors, f"{label}_test_outcome")
    if countercase_outcome not in COUNTERCASE_OUTCOMES:
        add_error(errors, f"{label}_countercase_outcome")
    if status in STATUS_CONTRACT and (
        test_outcome,
        countercase_outcome,
    ) != STATUS_CONTRACT[status]:
        add_error(errors, f"{label}_status_test_countercase_inconsistent")
    evidence_type = validate_evidence(
        assessment.get("evidence"),
        prompt=prompt,
        label=label,
        errors=errors,
        evidence_counts=evidence_counts,
    )
    if status == "UNRESOLVED" and evidence_type != "NONE":
        add_error(errors, f"{label}_unresolved_requires_none_evidence")
    if status in {"SUPPORTED", "REFUTED"} and evidence_type in {"NONE", "INVALID"}:
        add_error(errors, f"{label}_resolved_requires_evidence")
    return str(status)


def validate_preference(
    *,
    target_polarity: Any,
    left_status: str,
    right_status: str,
    uniqueness: Any,
    preference: Any,
    label: str,
    errors: list[str],
) -> None:
    if target_polarity not in TARGET_POLARITIES:
        add_error(errors, f"{label}_target_polarity")
    if uniqueness not in UNIQUENESS_VALUES:
        add_error(errors, f"{label}_uniqueness")
    if preference not in PREFERENCES:
        add_error(errors, f"{label}_preference")
        return
    if target_polarity == "UNRESOLVED" and (
        preference,
        uniqueness,
        left_status,
        right_status,
    ) != ("TIE", "UNRESOLVED", "UNRESOLVED", "UNRESOLVED"):
        add_error(errors, f"{label}_unresolved_polarity_inconsistent")
        return
    if preference == "PREFER_LEFT":
        if target_polarity == "UNRESOLVED" or (
            left_status,
            right_status,
            uniqueness,
        ) != ("SUPPORTED", "REFUTED", "LEFT_ONLY"):
            add_error(errors, f"{label}_prefer_left_inconsistent")
    elif preference == "PREFER_RIGHT":
        if target_polarity == "UNRESOLVED" or (
            left_status,
            right_status,
            uniqueness,
        ) != ("REFUTED", "SUPPORTED", "RIGHT_ONLY"):
            add_error(errors, f"{label}_prefer_right_inconsistent")
    else:
        valid_ties = {
            ("SUPPORTED", "SUPPORTED", "BOTH_PLAUSIBLE"),
            ("REFUTED", "REFUTED", "NEITHER_PLAUSIBLE"),
        }
        unresolved_tie = uniqueness == "UNRESOLVED" and "UNRESOLVED" in {
            left_status,
            right_status,
        }
        if (left_status, right_status, uniqueness) not in valid_ties and not unresolved_tie:
            add_error(errors, f"{label}_tie_inconsistent")


def validate_blind_pairwise_veto(
    campaign_dir: Path,
    *,
    write_report: bool = True,
) -> dict[str, Any]:
    campaign_dir = campaign_dir.resolve()
    veto_dir = campaign_dir / "veto"
    input_dir = veto_dir / "input"
    output_dir = veto_dir / "output"
    errors: list[str] = []

    freeze_path = veto_dir / "freeze.json"
    freeze: dict[str, Any] = {}
    if not freeze_path.is_file():
        add_error(errors, "freeze_missing")
    else:
        try:
            value = load_json(freeze_path)
            if not isinstance(value, dict):
                raise ValueError("freeze_not_object")
            freeze = value
        except Exception as exc:
            add_error(errors, f"freeze_invalid:{exc}")
    if freeze:
        stored = freeze.get("freezeSha256")
        observed = canonical_digest({key: item for key, item in freeze.items() if key != "freezeSha256"})
        if not isinstance(stored, str) or stored != observed:
            add_error(errors, "freeze_self_hash_mismatch")
        if freeze.get("protocol") != PROTOCOL:
            add_error(errors, "unsupported_protocol")
        implementation_hashes = freeze.get("implementationHashes")
        if not isinstance(implementation_hashes, dict) or not implementation_hashes:
            add_error(errors, "implementation_hashes_missing")
        else:
            expected_implementation_paths = {
                str((REPO_ROOT / relative).resolve()) for relative in IMPLEMENTATION_RELATIVE_PATHS
            }
            if set(implementation_hashes) != expected_implementation_paths:
                add_error(errors, "implementation_hash_paths_mismatch")
            for raw_path, expected_hash in implementation_hashes.items():
                path = Path(str(raw_path))
                if not path.is_file() or sha256_file(path) != expected_hash:
                    add_error(errors, f"implementation_hash_mismatch:{path.name}")
        expected_execution_config = {
            "model": FROZEN_MODEL,
            "reasoningEffort": FROZEN_REASONING_EFFORT,
            "verbosity": FROZEN_VERBOSITY,
            "serviceTier": "default",
            "nativeWebSearch": False,
            "localCode": True,
            "database": False,
            "skills": False,
            "multiAgent": False,
        }
        if freeze.get("executionConfig") != expected_execution_config:
            add_error(errors, "execution_config_mismatch")

    questions_path = input_dir / "questions.jsonl"
    pairs_path = input_dir / "candidate_pairs.jsonl"
    expected_path = input_dir / "expected_certificate_ids.json"
    instructions_path = input_dir / "RUN_INSTRUCTIONS.md"
    verify_file_hash(questions_path, freeze.get("questionsSha256"), "questions_hash_mismatch", errors)
    verify_file_hash(pairs_path, freeze.get("pairsSha256"), "pairs_hash_mismatch", errors)
    verify_file_hash(
        expected_path,
        freeze.get("expectedCertificateIdsFileSha256"),
        "expected_ids_file_hash_mismatch",
        errors,
    )
    verify_file_hash(instructions_path, freeze.get("instructionsSha256"), "instructions_hash_mismatch", errors)

    questions: list[dict[str, Any]] = []
    pairs: list[dict[str, Any]] = []
    expected_ids: list[str] = []
    try:
        questions = load_jsonl_strict(questions_path)
    except Exception as exc:
        add_error(errors, f"questions_invalid:{exc}")
    if len(questions) != EXPECTED_QUESTION_ROWS:
        add_error(errors, "question_row_count")
    question_ids: list[str] = []
    question_by_id: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(questions):
        if set(row) != {"id", "responseFormat", "language", "prompt"}:
            add_error(errors, f"question_{index}_schema")
        case_id = row.get("id")
        if not nonempty_string(case_id) or not nonempty_string(row.get("prompt")):
            add_error(errors, f"question_{index}_values")
            continue
        question_ids.append(case_id)
        question_by_id[case_id] = row
    if len(question_ids) != len(set(question_ids)):
        add_error(errors, "question_ids_duplicate")

    try:
        pairs = load_jsonl_strict(pairs_path)
    except Exception as exc:
        add_error(errors, f"pairs_invalid:{exc}")
    if len(pairs) != EXPECTED_CONFLICT_ROWS:
        add_error(errors, "pair_row_count")
    pair_ids: list[str] = []
    pair_by_id: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(pairs):
        if set(row) != {"id", "leftAnswer", "rightAnswer"}:
            add_error(errors, f"pair_{index}_schema")
        case_id = row.get("id")
        left = row.get("leftAnswer")
        right = row.get("rightAnswer")
        if not (nonempty_string(case_id) and nonempty_string(left) and nonempty_string(right)):
            add_error(errors, f"pair_{index}_values")
            continue
        if left == right:
            add_error(errors, f"pair_{index}_answers_identical")
        pair_ids.append(case_id)
        pair_by_id[case_id] = row
    if len(pair_ids) != len(set(pair_ids)) or any(case_id not in question_by_id for case_id in pair_ids):
        add_error(errors, "pair_ids_invalid")
    if [case_id for case_id in question_ids if case_id in set(pair_ids)] != pair_ids:
        add_error(errors, "pair_ids_not_in_question_order")

    if expected_path.is_file():
        try:
            expected_value = load_json(expected_path)
            raw_ids = expected_value.get("ids") if isinstance(expected_value, dict) else None
            if not isinstance(raw_ids, list) or expected_value.get("count") != len(raw_ids):
                raise ValueError("expected_ids_schema")
            expected_ids = raw_ids
        except Exception as exc:
            add_error(errors, f"expected_ids_invalid:{exc}")
    if expected_ids != pair_ids:
        add_error(errors, "expected_ids_pair_order_mismatch")
    if canonical_digest(pair_ids) != freeze.get("expectedCertificateIdsSha256"):
        add_error(errors, "expected_ids_digest_mismatch")

    mapping_path = campaign_dir / str(freeze.get("roleMappingPath") or "")
    rotation_path = campaign_dir / str(freeze.get("rotationControlPath") or "")
    if mapping_path.resolve() != (campaign_dir / "control/role_mapping.jsonl").resolve():
        add_error(errors, "role_mapping_path_not_fixed_control_path")
    if rotation_path.resolve() != (campaign_dir / "control/rotation.json").resolve():
        add_error(errors, "rotation_control_path_not_fixed_control_path")
    if input_dir.resolve() == mapping_path.resolve() or input_dir.resolve() in mapping_path.resolve().parents:
        add_error(errors, "role_mapping_inside_model_input")
    if input_dir.resolve() == rotation_path.resolve() or input_dir.resolve() in rotation_path.resolve().parents:
        add_error(errors, "rotation_control_inside_model_input")
    verify_file_hash(mapping_path, freeze.get("roleMappingSha256"), "role_mapping_hash_mismatch", errors)
    verify_file_hash(rotation_path, freeze.get("rotationControlSha256"), "rotation_control_hash_mismatch", errors)

    mapping: list[dict[str, Any]] = []
    rotation: dict[str, Any] = {}
    try:
        mapping = load_jsonl_strict(mapping_path)
    except Exception as exc:
        add_error(errors, f"role_mapping_invalid:{exc}")
    try:
        value = load_json(rotation_path)
        if not isinstance(value, dict):
            raise ValueError("rotation_not_object")
        rotation = value
    except Exception as exc:
        add_error(errors, f"rotation_invalid:{exc}")
    seed = rotation.get("seed")
    if not nonempty_string(seed) or text_sha256(str(seed)) != freeze.get("rotationSeedSha256"):
        add_error(errors, "rotation_seed_hash_mismatch")
    if rotation.get("scheme") != ROTATION_SCHEME or freeze.get("rotationScheme") != ROTATION_SCHEME:
        add_error(errors, "rotation_scheme_mismatch")
    if rotation.get("seedSha256") != freeze.get("rotationSeedSha256"):
        add_error(errors, "rotation_control_seed_hash_mismatch")
    if rotation.get("eligibleIdsSha256") != canonical_digest(pair_ids):
        add_error(errors, "rotation_control_ids_mismatch")
    if rotation.get("roleMappingSha256") != freeze.get("roleMappingSha256"):
        add_error(errors, "rotation_control_mapping_hash_mismatch")

    source_answers: dict[str, dict[str, str]] = {}
    source_campaign = Path(str(freeze.get("sourceCampaign") or ""))
    source_hashes = freeze.get("sourceCandidateAnswersSha256")
    if not isinstance(source_hashes, dict):
        add_error(errors, "source_candidate_hashes_missing")
    else:
        for name in ("base", "auxiliary_1", "auxiliary_2"):
            source_path = source_campaign / f"solver/input/candidates/{name}.jsonl"
            verify_file_hash(
                source_path,
                source_hashes.get(name),
                f"source_candidate_hash_mismatch:{name}",
                errors,
            )
            if source_path.is_file():
                try:
                    source_answers[name] = {
                        row["id"]: row["finalAnswer"] for row in load_jsonl_strict(source_path)
                    }
                except Exception as exc:
                    add_error(errors, f"source_candidate_invalid:{name}:{exc}")

    if [row.get("id") for row in mapping] != pair_ids:
        add_error(errors, "role_mapping_ids_order_mismatch")
    for index, row in enumerate(mapping):
        if set(row) != {
            "id",
            "rotationBit",
            "leftRole",
            "rightRole",
            "leftAnswerSha256",
            "rightAnswerSha256",
        }:
            add_error(errors, f"role_mapping_{index}_schema")
            continue
        case_id = row.get("id")
        pair = pair_by_id.get(str(case_id))
        if pair is None:
            continue
        bit = rotation_bit(str(seed), str(case_id)) if nonempty_string(seed) else None
        if row.get("rotationBit") != bit:
            add_error(errors, f"role_mapping_{index}_rotation")
        left_role = row.get("leftRole")
        right_role = row.get("rightRole")
        expected_roles = SOURCE_ROLES if bit == 0 else tuple(reversed(SOURCE_ROLES))
        if (left_role, right_role) != expected_roles:
            add_error(errors, f"role_mapping_{index}_roles")
        if row.get("leftAnswerSha256") != text_sha256(pair["leftAnswer"]):
            add_error(errors, f"role_mapping_{index}_left_hash")
        if row.get("rightAnswerSha256") != text_sha256(pair["rightAnswer"]):
            add_error(errors, f"role_mapping_{index}_right_hash")
        incumbent = source_answers.get("base", {}).get(str(case_id))
        proposed = source_answers.get("auxiliary_1", {}).get(str(case_id))
        expected_left = incumbent if left_role == "INCUMBENT" else proposed
        expected_right = incumbent if right_role == "INCUMBENT" else proposed
        if pair["leftAnswer"] != expected_left or pair["rightAnswer"] != expected_right:
            add_error(errors, f"role_mapping_{index}_source_answer_mismatch")

    certificates_path = output_dir / "certificates.jsonl"
    certificates: list[dict[str, Any]] = []
    if not certificates_path.is_file():
        add_error(errors, "certificates_missing")
    else:
        try:
            certificates = load_jsonl_strict(certificates_path)
        except Exception as exc:
            add_error(errors, f"certificates_invalid:{exc}")
    certificate_ids = [row.get("id") for row in certificates]
    if certificate_ids != expected_ids:
        add_error(errors, "certificate_ids_order_or_coverage_mismatch")

    preference_counts: Counter[str] = Counter()
    evidence_counts: Counter[str] = Counter()
    for index, certificate in enumerate(certificates):
        label = f"certificate_{index}"
        if set(certificate) != ROOT_KEYS:
            add_error(errors, f"{label}_schema")
            continue
        case_id = certificate.get("id")
        pair = pair_by_id.get(str(case_id))
        question = question_by_id.get(str(case_id))
        if pair is None or question is None:
            add_error(errors, f"{label}_unknown_id")
            continue
        target_polarity = certificate.get("targetPolarity")
        polarity_quote = certificate.get("polarityQuote")
        if not nonempty_string(polarity_quote) or not prompt_contains(question["prompt"], polarity_quote):
            add_error(errors, f"{label}_polarity_quote_not_found")
        left_status = validate_assessment(
            certificate.get("leftAssessment"),
            expected_answer=pair["leftAnswer"],
            prompt=question["prompt"],
            label=f"{label}_left",
            errors=errors,
            evidence_counts=evidence_counts,
        )
        right_status = validate_assessment(
            certificate.get("rightAssessment"),
            expected_answer=pair["rightAnswer"],
            prompt=question["prompt"],
            label=f"{label}_right",
            errors=errors,
            evidence_counts=evidence_counts,
        )
        preference = certificate.get("preference")
        preference_counts[str(preference)] += 1
        validate_preference(
            target_polarity=target_polarity,
            left_status=left_status,
            right_status=right_status,
            uniqueness=certificate.get("uniqueness"),
            preference=preference,
            label=label,
            errors=errors,
        )
        if not nonempty_string(certificate.get("comparativeReason")):
            add_error(errors, f"{label}_comparative_reason_empty")

    report = {
        "schemaVersion": 1,
        "status": "accepted" if not errors else "incomplete",
        "passed": not errors,
        "errors": errors,
        "questionRows": len(questions),
        "conflictRows": len(pairs),
        "certificateRows": len(certificates),
        "preferenceCounts": dict(sorted(preference_counts.items())),
        "evidenceTypeCounts": dict(sorted(evidence_counts.items())),
        "modelKnowledgeReceiptsExternallyVerified": False,
        "certificatesSha256": sha256_file(certificates_path) if certificates_path.is_file() else None,
        "roleMappingSha256": sha256_file(mapping_path) if mapping_path.is_file() else None,
    }
    if write_report:
        write_json(veto_dir / "certificate_validation.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--no-write-report", action="store_true")
    args = parser.parse_args()
    report = validate_blind_pairwise_veto(
        args.campaign_dir,
        write_report=not args.no_write_report,
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
