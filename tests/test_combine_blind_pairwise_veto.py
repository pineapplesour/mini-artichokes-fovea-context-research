from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from tools import combine_blind_pairwise_veto as combiner
from tools import run_blind_pairwise_veto_agent as blind_runner
from tools import run_plain_codex_file_agent as plain_runner
from tools.combine_blind_pairwise_veto import (
    CombinationValidationError,
    combine_campaigns,
)
from tools.prepare_blind_pairwise_veto import prepare as prepare_blind
from tools.prepare_blind_pairwise_veto import rotation_bit
from tools.prepare_overlap_adjudication import prepare as prepare_overlap
from tools.prepare_plain_codex_file_benchmark import canonical_digest, sha256_file
from tools.validate_blind_pairwise_veto import validate_blind_pairwise_veto
from tools.validate_overlap_adjudication import validate_overlap_adjudication


ROWS = 1309
MCQ_ROWS = 961
ELIGIBLE_ROWS = 247
ROTATION_SEED = "combiner-focused-test-seed-v1"


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def self_hashed(value: dict[str, Any], field: str) -> dict[str, Any]:
    value[field] = canonical_digest(value)
    return value


def minimal_trace(path: Path, thread_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"type": "thread.started", "thread_id": thread_id})
        + "\n"
        + json.dumps(
            {
                "type": "turn.completed",
                "usage": {
                    "input_tokens": 1,
                    "cached_input_tokens": 0,
                    "output_tokens": 1,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )


def test_combiner_thread_identity_uses_lf_records(tmp_path: Path) -> None:
    trace = tmp_path / "trace.jsonl"
    trace.write_text(
        '{"type":"thread.started","thread_id":"thread-1"}\n'
        '{"type":"item.completed","item":{"text":"a\u0085b\u2028c\u2029d"}}\n',
        encoding="utf-8",
    )

    assert combiner._thread_identity(trace, label="blind") == ["thread-1"]


def test_module_hash_map_accepts_only_exact_script_entry_point_alias() -> None:
    validator_module, _ = blind_runner.strict_validator()
    implementations = blind_runner.implementation_hashes(validator_module)
    runner_key = next(
        key for key in implementations if key.endswith("|tools/run_blind_pairwise_veto_agent.py")
    )
    script_implementations = dict(implementations)
    script_implementations["__main__|tools/run_blind_pairwise_veto_agent.py"] = (
        script_implementations.pop(runner_key)
    )

    verified = combiner._verify_module_hash_map(script_implementations, "actual receipt")

    assert verified == script_implementations
    invalid = dict(script_implementations)
    invalid["__main__|tools/benchmark_provider.py"] = invalid.pop(
        next(key for key in invalid if key.endswith("|tools/benchmark_provider.py"))
    )
    with pytest.raises(CombinationValidationError, match="module/path invalid"):
        combiner._verify_module_hash_map(invalid, "actual receipt")


def accepted_answer_report(answer_path: Path) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "status": "accepted",
        "passed": True,
        "errors": [],
        "expectedRows": ROWS,
        "observedRows": ROWS,
        "answersSha256": sha256_file(answer_path),
    }


def build_source_campaign(root: Path) -> tuple[Path, list[str], dict[int, list[dict[str, str]]]]:
    source = root / "source"
    ids = [f"q{index:04d}" for index in range(ROWS)]
    questions: list[dict[str, str]] = []
    candidates: dict[int, list[dict[str, str]]] = {1: [], 2: [], 3: []}
    for index, case_id in enumerate(ids):
        if index < MCQ_ROWS:
            prompt = (
                f"Choose correct for item {index}.\n"
                f"A. base-{index}\nB. proposed-{index}\nC. other-{index}"
            )
            questions.append(
                {
                    "id": case_id,
                    "prompt": prompt,
                    "responseFormat": "mcq",
                    "language": "en",
                }
            )
            base = f"A. base-{index}"
            proposed = f"B. proposed-{index}" if index < ELIGIBLE_ROWS else base
        else:
            questions.append(
                {
                    "id": case_id,
                    "prompt": f"Give a short answer for item {index}.",
                    "responseFormat": "short_answer",
                    "language": "en",
                }
            )
            base = proposed = f"same-{index}"
        candidates[1].append({"id": case_id, "finalAnswer": base})
        candidates[2].append({"id": case_id, "finalAnswer": proposed})
        candidates[3].append({"id": case_id, "finalAnswer": proposed})

    source_questions = source / "solver/input/questions.jsonl"
    source_expected = source / "solver/input/expected_ids.json"
    write_jsonl(source_questions, questions)
    write_json(source_expected, {"count": ROWS, "ids": ids})
    execution = {
        "model": "gpt-5.6-luna",
        "reasoningEffort": "high",
        "verbosity": "low",
        "serviceTier": "default",
        "nativeWebSearch": True,
        "localCode": True,
        "database": False,
        "skills": False,
        "multiAgent": False,
    }
    freeze = self_hashed(
        {
            "schemaVersion": 1,
            "status": "prepared_no_model_calls",
            "protocol": "one_plain_codex_solver_file_output_v1",
            "questionsSha256": sha256_file(source_questions),
            "expectedIdsSha256": canonical_digest(ids),
            "executionConfig": execution,
        },
        "freezeSha256",
    )
    write_json(source / "solver/freeze.json", freeze)

    for index, rows in candidates.items():
        solver = source / f"drafts/d{index}/solver"
        answers = solver / "output/answers.jsonl"
        questions_path = solver / "input/questions.jsonl"
        write_jsonl(answers, rows)
        write_jsonl(questions_path, questions)
        write_json(solver / "freeze.json", freeze)
        report = accepted_answer_report(answers)
        write_json(solver / "answer_validation.json", report)
        trace = solver / "codex_trace.jsonl"
        minimal_trace(trace, f"candidate-thread-{index}")
        audit = plain_runner.audit_trace(
            trace_path=trace,
            questions_path=questions_path,
            role="solver",
            return_code=0,
        )
        receipt = self_hashed(
            {
                "schemaVersion": 1,
                "status": "accepted",
                "role": "solver",
                "semanticModelInvocations": 1,
                "model": execution["model"],
                "reasoningEffort": execution["reasoningEffort"],
                "verbosity": execution["verbosity"],
                "freezeSha256": freeze["freezeSha256"],
                "payloadSha256": sha256_file(source_questions),
                "isolationProbe": {"passed": True},
                "process": {"exitCode": 0, "timedOut": False, "elapsedSec": 1.0},
                "policyAudit": audit,
                "artifactValidation": report,
                "acceptedArtifact": "answers.jsonl",
            },
            "receiptSha256",
        )
        write_json(solver / "run_receipt.json", receipt)
    return source, ids, candidates


def choose_rotation_ids(ids: list[str]) -> tuple[str, str, str]:
    proposed_left = next(case_id for case_id in ids if rotation_bit(ROTATION_SEED, case_id) == 1)
    proposed_right = next(case_id for case_id in ids if rotation_bit(ROTATION_SEED, case_id) == 0)
    strict_only = next(case_id for case_id in ids if case_id not in {proposed_left, proposed_right})
    return proposed_left, proposed_right, strict_only


def build_strict_campaign(root: Path) -> tuple[Path, list[str], tuple[str, str, str]]:
    source, ids, _ = build_source_campaign(root)
    campaign = root / "strict"
    prepare_overlap(
        source_campaign=source,
        campaign_dir=campaign,
        base_index=1,
        auxiliary_indices=(2, 3),
        model="gpt-5.6-luna",
        reasoning_effort="high",
        verbosity="low",
    )
    eligible = ids[:ELIGIBLE_ROWS]
    proposed_left, proposed_right, strict_only = choose_rotation_ids(eligible)
    strict_switch = {proposed_left, strict_only}
    decisions = [
        (
            f"{case_id} | gate=VALID | action=SWITCH | independently supported"
            if case_id in strict_switch
            else f"{case_id} | gate=INVALID | action=KEEP | not supported"
        )
        for case_id in eligible
    ]
    output = campaign / "solver/output"
    (output / "decisions.log").write_text("\n".join(decisions) + "\n", encoding="utf-8")
    base_rows = [
        json.loads(raw)
        for raw in (campaign / "solver/input/candidates/base.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    proposed_rows = [
        json.loads(raw)
        for raw in (campaign / "solver/input/candidates/auxiliary_1.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    answers = [
        proposed if proposed["id"] in strict_switch else base
        for base, proposed in zip(base_rows, proposed_rows)
    ]
    write_jsonl(output / "answers.jsonl", answers)
    report = validate_overlap_adjudication(campaign, write_report=True)
    assert report["passed"] is True
    trace = campaign / "solver/codex_trace.jsonl"
    minimal_trace(trace, "strict-thread")
    questions_path = campaign / "solver/input/questions.jsonl"
    audit = plain_runner.audit_trace(
        trace_path=trace,
        questions_path=questions_path,
        role="solver",
        return_code=0,
    )
    freeze = json.loads((campaign / "solver/freeze.json").read_text(encoding="utf-8"))
    receipt = self_hashed(
        {
            "schemaVersion": 1,
            "status": "accepted",
            "role": "solver",
            "semanticModelInvocations": 1,
            "model": "gpt-5.6-luna",
            "reasoningEffort": "high",
            "verbosity": "low",
            "freezeSha256": freeze["freezeSha256"],
            "payloadSha256": freeze["questionsSha256"],
            "inputIntegrity": plain_runner.verify_frozen_inputs(
                campaign_dir=campaign, role="solver"
            ),
            "isolationProbe": {"passed": True},
            "process": {"exitCode": 0, "timedOut": False, "elapsedSec": 1.0},
            "policyAudit": audit,
            "artifactValidation": report,
            "acceptedArtifact": "answers.jsonl",
        },
        "receiptSha256",
    )
    write_json(campaign / "solver/run_receipt.json", receipt)
    return campaign, ids, (proposed_left, proposed_right, strict_only)


def assessment(answer: str, status: str) -> dict[str, Any]:
    if status == "SUPPORTED":
        test_outcome, countercase_outcome = "SURVIVED", "DEFEATED"
        evidence = {
            "type": "MODEL_KNOWLEDGE",
            "receipt": {
                "supportedClaim": "the candidate satisfies the requested condition",
                "falsificationBasis": "a contradictory condition would falsify it",
            },
        }
    elif status == "REFUTED":
        test_outcome, countercase_outcome = "FAILED", "STANDS"
        evidence = {
            "type": "MODEL_KNOWLEDGE",
            "receipt": {
                "supportedClaim": "the candidate violates the requested condition",
                "falsificationBasis": "satisfying every condition would falsify this assessment",
            },
        }
    else:
        test_outcome, countercase_outcome = "INCONCLUSIVE", "UNRESOLVED"
        evidence = {"type": "NONE", "receipt": None}
    return {
        "candidateAnswer": answer,
        "atomicClaim": "candidate-specific atomic claim",
        "falsificationTest": "attempt the decisive condition check",
        "testOutcome": test_outcome,
        "status": status,
        "strongestCountercase": "the opposite condition may apply",
        "countercaseOutcome": countercase_outcome,
        "evidence": evidence,
    }


def certificate(pair: dict[str, str], preference: str) -> dict[str, Any]:
    if preference == "PREFER_LEFT":
        left_status, right_status, uniqueness = "SUPPORTED", "REFUTED", "LEFT_ONLY"
    elif preference == "PREFER_RIGHT":
        left_status, right_status, uniqueness = "REFUTED", "SUPPORTED", "RIGHT_ONLY"
    else:
        left_status = right_status = "UNRESOLVED"
        uniqueness = "UNRESOLVED"
    return {
        "id": pair["id"],
        "targetPolarity": "SELECT_CORRECT",
        "polarityQuote": "Choose correct",
        "leftAssessment": assessment(pair["leftAnswer"], left_status),
        "rightAssessment": assessment(pair["rightAnswer"], right_status),
        "uniqueness": uniqueness,
        "preference": preference,
        "comparativeReason": "the two candidate-specific tests determine this result",
    }


def binary_identity(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    return {
        "path": str(path),
        "resolvedPath": str(resolved),
        "sha256": sha256_file(resolved),
        "bytes": resolved.stat().st_size,
    }


def build_blind_campaign(
    root: Path,
    strict: Path,
    role_ids: tuple[str, str, str],
) -> Path:
    campaign = root / "blind"
    prepare_blind(
        source_campaign=strict,
        campaign_dir=campaign,
        rotation_seed=ROTATION_SEED,
        model="gpt-5.6-luna",
        reasoning_effort="high",
        verbosity="low",
    )
    pairs = [
        json.loads(raw)
        for raw in (campaign / "veto/input/candidate_pairs.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    proposed_left, proposed_right, _ = role_ids
    certificates = [
        certificate(
            pair,
            "PREFER_LEFT"
            if pair["id"] == proposed_left
            else "PREFER_RIGHT"
            if pair["id"] == proposed_right
            else "TIE",
        )
        for pair in pairs
    ]
    output = campaign / "veto/output"
    write_jsonl(output / "certificates.jsonl", certificates)
    (output / "last_message.txt").write_text("complete\n", encoding="utf-8")
    trace = campaign / "veto/codex_trace.jsonl"
    minimal_trace(trace, "blind-thread")
    (campaign / "veto/codex_stderr.txt").write_text("", encoding="utf-8")
    report = validate_blind_pairwise_veto(campaign, write_report=True)
    assert report["passed"] is True

    freeze, paths, input_hashes = blind_runner.verify_frozen_bundle(campaign)
    execution = blind_runner.verify_execution_config(
        freeze,
        model="gpt-5.6-luna",
        reasoning_effort="high",
        verbosity="low",
    )
    validator_module, _ = blind_runner.strict_validator()
    implementations = blind_runner.implementation_hashes(validator_module)
    audit = blind_runner.audit_veto_trace(
        trace_path=trace,
        questions_path=paths["questions"],
        return_code=0,
        native_web_search=False,
    )
    validation = blind_runner.validate_certificates(
        campaign_dir=campaign,
        paths=paths,
        validator=validate_blind_pairwise_veto,
        write_report=True,
    )
    fake_bin = root / "fake-bin"
    fake_bin.mkdir(parents=True, exist_ok=True)
    identities: dict[str, dict[str, Any]] = {}
    for name in ("launcher", "node", "entry-point", "bubblewrap"):
        path = fake_bin / name
        path.write_bytes(f"fake-{name}".encode())
        identities[name] = binary_identity(path)
    cli = {
        "version": "codex-cli focused-test",
        "launcher": identities["launcher"],
        "node": identities["node"],
        "entryPoint": identities["entry-point"],
        "bubblewrap": identities["bubblewrap"],
        "commandSha256": hashlib.sha256(b"focused-test-command").hexdigest(),
        "commandArgumentCount": 1,
    }
    receipt = {
        "schemaVersion": 1,
        "status": "accepted",
        "protocol": blind_runner.PROTOCOL,
        "semanticModelInvocations": 1,
        "freezeSha256": freeze["freezeSha256"],
        "inputFileSha256": input_hashes,
        "executionConfig": execution,
        "implementationHashes": implementations,
        "codexCli": cli,
        "visibilityBoundary": {
            "publicReadOnlyGuestPath": "/tmp/work/input",
            "writableGuestPath": "/tmp/work/output",
            "hiddenControlMounted": False,
            "maskedHostRoots": ["/home", "/mnt", "/root", "/tmp", "/var/tmp"],
            "policy": "bubblewrap_public_input_only",
        },
        "isolationProbe": {"passed": True},
        "process": {
            "startedAtUtc": "2026-08-31T00:00:00Z",
            "endedAtUtc": "2026-08-31T00:00:01Z",
            "elapsedSec": 1.0,
            "exitCode": 0,
            "timedOut": False,
        },
        "policyAudit": audit,
        "artifactValidation": validation,
        "artifacts": {
            "rawTraceSha256": sha256_file(paths["trace"]),
            "stderrSha256": sha256_file(paths["stderr"]),
            "certificatesSha256": validation["certificatesSha256"],
            "lastMessageSha256": validation["lastMessageSha256"],
            "validationReportSha256": validation["validationReportSha256"],
            "threadIds": audit["threadIds"],
        },
        "acceptedArtifact": "output/certificates.jsonl",
    }
    receipt["receiptSha256"] = blind_runner.receipt_digest(receipt)
    write_json(paths["receipt"], receipt)
    return campaign


def complete_campaigns(tmp_path: Path) -> tuple[Path, Path, tuple[str, str, str]]:
    strict, _, role_ids = build_strict_campaign(tmp_path)
    blind = build_blind_campaign(tmp_path, strict, role_ids)
    return strict, blind, role_ids


def read_answer_map(path: Path) -> dict[str, str]:
    return {
        row["id"]: row["finalAnswer"]
        for row in (json.loads(raw) for raw in path.read_text(encoding="utf-8").splitlines())
    }


def test_exact_four_policies_cover_both_role_rotations(tmp_path: Path) -> None:
    strict, blind, (proposed_left, proposed_right, strict_only) = complete_campaigns(tmp_path)
    output = tmp_path / "combined"

    receipt = combine_campaigns(
        strict_campaign=strict,
        blind_campaign=blind,
        output_dir=output,
    )

    mapping = [
        json.loads(raw)
        for raw in (blind / "control/role_mapping.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    by_id = {row["id"]: row for row in mapping}
    assert by_id[proposed_left]["leftRole"] == "PROPOSED"
    assert by_id[proposed_right]["rightRole"] == "PROPOSED"
    expected_switches = {
        "base": [],
        "blind_only": [proposed_left, proposed_right],
        "intersection": [proposed_left],
        "union": [proposed_left, proposed_right, strict_only],
    }
    eligible_order = [f"q{index:04d}" for index in range(ELIGIBLE_ROWS)]
    for policy, unordered in expected_switches.items():
        expected = [case_id for case_id in eligible_order if case_id in set(unordered)]
        policy_receipt = receipt["policies"][policy]
        assert policy_receipt["switchIds"] == expected
        assert policy_receipt["switchRows"] == len(expected)
        answer_path = output / policy_receipt["answersPath"]
        answers = read_answer_map(answer_path)
        assert len(answers) == ROWS
        base = read_answer_map(strict / "solver/input/candidates/base.jsonl")
        proposed = read_answer_map(strict / "solver/input/candidates/auxiliary_1.jsonl")
        assert all(
            answers[case_id] == (proposed[case_id] if case_id in expected else base[case_id])
            for case_id in base
        )
    persisted = json.loads((output / "combination_receipt.json").read_text(encoding="utf-8"))
    assert persisted == receipt
    assert persisted["goldAccess"] is False
    assert persisted["synthesis"] is False
    assert persisted["receiptSha256"] == canonical_digest(
        {key: value for key, value in persisted.items() if key != "receiptSha256"}
    )


def test_tampered_blind_certificate_fails_before_output(tmp_path: Path) -> None:
    strict, blind, _ = complete_campaigns(tmp_path)
    path = blind / "veto/output/certificates.jsonl"
    rows = [json.loads(raw) for raw in path.read_text(encoding="utf-8").splitlines()]
    rows[0]["comparativeReason"] = "tampered after receipt"
    write_jsonl(path, rows)
    output = tmp_path / "combined"

    with pytest.raises(CombinationValidationError):
        combine_campaigns(strict_campaign=strict, blind_campaign=blind, output_dir=output)

    assert not output.exists()


@pytest.mark.parametrize("mutation", ["partial", "misorder"])
def test_partial_or_misordered_strict_ledger_fails_closed(
    tmp_path: Path, mutation: str
) -> None:
    strict, blind, _ = complete_campaigns(tmp_path)
    path = strict / "solver/output/decisions.log"
    lines = path.read_text(encoding="utf-8").splitlines()
    if mutation == "partial":
        lines = lines[:-1]
    else:
        lines[0], lines[1] = lines[1], lines[0]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    output = tmp_path / "combined"

    with pytest.raises(CombinationValidationError):
        combine_campaigns(strict_campaign=strict, blind_campaign=blind, output_dir=output)

    assert not output.exists()


def test_self_consistent_but_unaccepted_upstream_receipt_is_rejected(tmp_path: Path) -> None:
    strict, blind, _ = complete_campaigns(tmp_path)
    path = blind / "veto/run_receipt.json"
    receipt = json.loads(path.read_text(encoding="utf-8"))
    receipt["status"] = "incomplete"
    receipt["receiptSha256"] = blind_runner.receipt_digest(receipt)
    write_json(path, receipt)
    output = tmp_path / "combined"

    with pytest.raises(CombinationValidationError):
        combine_campaigns(strict_campaign=strict, blind_campaign=blind, output_dir=output)

    assert not output.exists()
