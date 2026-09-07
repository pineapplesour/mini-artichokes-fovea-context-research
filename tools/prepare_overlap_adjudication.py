#!/usr/bin/env python3
"""Prepare a frozen candidate-overlap adjudication campaign.

This is a development bridge between Universal Artichoke's independently
sampled candidates and Mini Artichokes' conservative overlap gate.  It never
reads gold answers.  Candidate B and candidate C must agree on a different
answer key before the model is even allowed to consider changing the frozen
base answer A.  Agreement is only a trigger: the adjudicator must still
validate the implied error against the public question and otherwise KEEP A.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.prepare_plain_codex_file_benchmark import canonical_digest, sha256_file
from tools.run_ensemble_file_agent import match_answer_to_option, parse_mcq_options


INSTRUCTIONS = """# Mini Artichokes candidate-overlap adjudication v2

The complete public benchmark is in `input/questions.jsonl`.  Three complete,
separately sampled answer files over the same IDs are in:

- `input/candidates/base.jsonl`: frozen base answer A;
- `input/candidates/auxiliary_1.jsonl`: independent alternative B;
- `input/candidates/auxiliary_2.jsonl`: independent alternative C.

`input/overlap_manifest.jsonl` was computed mechanically from public prompts
and candidate answers.  Primary eligibility is deliberately limited to MCQ
rows where A, B, and C all map unambiguously to canonical option IDs.
`eligible=true` means B and C map to the same option ID and that ID differs
from A.  Constructed/free-text rows and ambiguous mappings are ineligible.
Eligibility does NOT mean B and C are correct.

Produce one final answer for every input row under this fail-closed policy:

1. Default to KEEP: copy A exactly.
2. If `eligible=false`, you MUST keep A exactly.  Do not freely re-solve or
   rewrite that row.
3. If `eligible=true`, inspect the public question and A/B/C.  Derive the
   specific material error in A that B implies and the error that C implies.
   Treat them as a usable overlap only when they identify the same atomic
   error and that error is independently supported by the question, a valid
   calculation, or general source evidence allowed by the benchmark policy.
4. Agreement alone is never validation.  Correlated candidates can share the
   same wrong answer.  If the common error claim is unsupported, ambiguous,
   answer-key-dependent, or would require guessing, mark it INVALID or
   ABSTAIN and keep A exactly.
5. Only for a VALID material overlap may you SWITCH, and a switch means copying
   candidate B (`auxiliary_1.jsonl`) exactly.  Do not synthesize, rewrite, or
   self-solve a fourth answer in this experiment.  B and C already map to the
   same answer key on eligible rows; this restriction isolates the gate's
   causal selection effect from fresh solving ability.
6. Never search for an exam question, answer key, benchmark ID, or historical
   benchmark answer.  Do not use cross-row answer frequencies, subject names,
   item identities, or benchmark-specific rules to choose an answer.

Process eligible rows in input order and append one line per eligible row to
`output/decisions.log` before finalizing:

`<id> | gate=<VALID|INVALID|ABSTAIN> | action=<KEEP|SWITCH> | <short reason>`

Use local code to initialize every output row from base.jsonl, then alter only
rows whose ledger action is SWITCH, copying B exactly on those rows.  Write progress to
`output/answers.partial.jsonl`.  When all expected IDs are present exactly
once, atomically write `output/answers.jsonl` in input order with exactly the
keys `id` and `finalAnswer`.  The final chat message is only a completion
notice.
"""


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            raise ValueError(f"blank JSONL line {line_number}: {path}")
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError(f"non-object JSONL line {line_number}: {path}")
        rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def load_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def verify_self_hash(value: dict[str, Any], field: str, label: str) -> str:
    claimed = value.get(field)
    if not isinstance(claimed, str) or not claimed:
        raise ValueError(f"{label} missing {field}")
    computed = canonical_digest({key: item for key, item in value.items() if key != field})
    if claimed != computed:
        raise ValueError(f"{label} {field} mismatch; claimed={claimed}, computed={computed}")
    return claimed


def validate_candidate_indices(base_index: int, auxiliary_indices: tuple[int, int]) -> tuple[int, int, int]:
    if len(auxiliary_indices) != 2:
        raise ValueError("exactly two auxiliary candidate indices are required")
    indices = (base_index, *auxiliary_indices)
    if any(isinstance(index, bool) or not isinstance(index, int) or index <= 0 for index in indices):
        raise ValueError("candidate indices must be positive integers")
    if len(set(indices)) != len(indices):
        raise ValueError("base and auxiliary candidate indices must be unique")
    return indices


def validate_questions(rows: list[dict[str, Any]]) -> list[str]:
    if not rows:
        raise ValueError("questions must not be empty")
    ids: list[str] = []
    for position, row in enumerate(rows, 1):
        for field in ("id", "prompt", "responseFormat"):
            value = row.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"question {position} requires a non-empty string {field}")
        ids.append(row["id"])
    if len(ids) != len(set(ids)):
        raise ValueError("questions must contain unique IDs")
    return ids


def validate_expected_ids(path: Path, derived_ids: list[str]) -> None:
    expected = load_json_object(path)
    ids = expected.get("ids")
    count = expected.get("count")
    if not isinstance(ids, list) or any(not isinstance(case_id, str) or not case_id for case_id in ids):
        raise ValueError(f"invalid source expected IDs schema: {path}")
    if count != len(ids):
        raise ValueError(f"source expected ID count mismatch: {path}")
    if ids != derived_ids:
        raise ValueError("source expected IDs do not exactly match question-derived IDs")


def answer_map(path: Path, expected_ids: list[str]) -> dict[str, str]:
    rows = load_jsonl(path)
    observed: list[str] = []
    answers: dict[str, str] = {}
    for line_number, row in enumerate(rows, 1):
        if set(row) != {"id", "finalAnswer"}:
            raise ValueError(f"candidate row {line_number} must have exactly id/finalAnswer: {path}")
        case_id = row.get("id")
        answer = row.get("finalAnswer")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError(f"candidate row {line_number} has an empty/non-string ID: {path}")
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError(f"candidate row {line_number} has an empty/non-string finalAnswer: {path}")
        observed.append(case_id)
        answers[case_id] = answer
    if len(observed) != len(set(observed)):
        raise ValueError(f"duplicate candidate IDs: {path}")
    if observed != expected_ids:
        missing = sorted(set(expected_ids) - set(observed))[:5]
        extra = sorted(set(observed) - set(expected_ids))[:5]
        raise ValueError(
            f"candidate ID/order mismatch for {path}; missing={missing}, extra={extra}"
        )
    return answers


def candidate_path(source_campaign: Path, index: int) -> Path:
    path = source_campaign / "drafts" / f"d{index}" / "solver/output/answers.jsonl"
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def candidate_provenance(
    *,
    source_campaign: Path,
    campaign_dir: Path,
    name: str,
    index: int,
    answers_path: Path,
    answers_sha256: str,
    source_freeze: dict[str, Any],
    questions_sha256: str,
    expected_rows: int,
) -> dict[str, Any]:
    solver_dir = source_campaign / "drafts" / f"d{index}" / "solver"
    artifacts = {
        "sourceFreeze": solver_dir / "freeze.json",
        "runReceipt": solver_dir / "run_receipt.json",
        "answerValidation": solver_dir / "answer_validation.json",
    }
    available = {key: path.is_file() for key, path in artifacts.items()}
    if not any(available.values()):
        return {
            "status": "unavailable",
            "candidateIndex": index,
            "answersSha256": answers_sha256,
            "reason": "source campaign has no draft provenance artifacts to bind",
        }
    if not all(available.values()):
        missing = sorted(key for key, present in available.items() if not present)
        raise ValueError(f"candidate provenance incomplete for d{index}; missing={missing}")

    draft_freeze = load_json_object(artifacts["sourceFreeze"])
    if draft_freeze != source_freeze:
        raise ValueError(f"candidate d{index} freeze does not match source campaign freeze")
    source_freeze_sha256 = verify_self_hash(draft_freeze, "freezeSha256", f"candidate d{index} freeze")

    receipt = load_json_object(artifacts["runReceipt"])
    receipt_sha256 = verify_self_hash(receipt, "receiptSha256", f"candidate d{index} receipt")
    validation = load_json_object(artifacts["answerValidation"])
    artifact_validation = receipt.get("artifactValidation")
    process = receipt.get("process")
    policy_audit = receipt.get("policyAudit")
    isolation_probe = receipt.get("isolationProbe")
    checks = {
        "receipt status": receipt.get("status") == "accepted",
        "receipt role": receipt.get("role") == "solver",
        "receipt invocation count": receipt.get("semanticModelInvocations") == 1,
        "receipt freeze": receipt.get("freezeSha256") == source_freeze_sha256,
        "receipt payload": receipt.get("payloadSha256") == questions_sha256,
        "receipt accepted artifact": receipt.get("acceptedArtifact") == "answers.jsonl",
        "receipt process": isinstance(process, dict)
        and process.get("exitCode") == 0
        and process.get("timedOut") is False,
        "receipt policy audit": isinstance(policy_audit, dict) and policy_audit.get("passed") is True,
        "receipt isolation probe": isinstance(isolation_probe, dict) and isolation_probe.get("passed") is True,
        "receipt artifact validation": isinstance(artifact_validation, dict)
        and artifact_validation.get("status") == "accepted"
        and artifact_validation.get("passed") is True
        and artifact_validation.get("expectedRows") == expected_rows
        and artifact_validation.get("observedRows") == expected_rows
        and artifact_validation.get("answersSha256") == answers_sha256,
        "standalone answer validation": validation.get("status") == "accepted"
        and validation.get("passed") is True
        and validation.get("expectedRows") == expected_rows
        and validation.get("observedRows") == expected_rows
        and validation.get("answersSha256") == answers_sha256,
    }
    failed_checks = [label for label, passed in checks.items() if not passed]
    if failed_checks:
        raise ValueError(f"candidate d{index} provenance rejected: {failed_checks}")

    source_execution = source_freeze.get("executionConfig")
    if isinstance(source_execution, dict):
        for receipt_field, freeze_field in (
            ("model", "model"),
            ("reasoningEffort", "reasoningEffort"),
            ("verbosity", "verbosity"),
        ):
            expected = source_execution.get(freeze_field)
            if expected is not None and receipt.get(receipt_field) != expected:
                raise ValueError(
                    f"candidate d{index} receipt {receipt_field} does not match source freeze"
                )

    provenance_dir = campaign_dir / "provenance/candidates" / name
    provenance_dir.mkdir(parents=True, exist_ok=True)
    copied: dict[str, dict[str, str]] = {}
    for artifact_name, source_path in artifacts.items():
        destination = provenance_dir / source_path.name
        shutil.copy2(source_path, destination)
        copied[artifact_name] = {
            "path": str(destination.relative_to(campaign_dir)),
            "sha256": sha256_file(destination),
        }
    return {
        "status": "accepted",
        "candidateIndex": index,
        "answersSourcePath": str(answers_path.resolve()),
        "answersSha256": answers_sha256,
        "sourceFreezeSha256": source_freeze_sha256,
        "receiptSha256": receipt_sha256,
        "model": receipt.get("model"),
        "reasoningEffort": receipt.get("reasoningEffort"),
        "verbosity": receipt.get("verbosity"),
        "semanticModelInvocations": receipt.get("semanticModelInvocations"),
        "artifacts": copied,
    }


def canonical_mcq_option_key(answer: str, options: dict[str, str]) -> str:
    if len(options) < 2 or any(not str(option).strip() for option in options.values()):
        return ""
    option_id = match_answer_to_option(answer, options)
    return f"option:{option_id}" if option_id and option_id in options else ""


def prepare(
    *,
    source_campaign: Path,
    campaign_dir: Path,
    base_index: int,
    auxiliary_indices: tuple[int, int],
    model: str,
    reasoning_effort: str,
    verbosity: str,
) -> dict[str, Any]:
    indices = validate_candidate_indices(base_index, auxiliary_indices)
    if campaign_dir.exists() and any(campaign_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty campaign: {campaign_dir}")

    source_questions = source_campaign / "solver/input/questions.jsonl"
    source_expected = source_campaign / "solver/input/expected_ids.json"
    source_freeze = source_campaign / "solver/freeze.json"
    for path in (source_questions, source_expected, source_freeze):
        if not path.is_file():
            raise FileNotFoundError(path)

    questions = load_jsonl(source_questions)
    ids = validate_questions(questions)
    validate_expected_ids(source_expected, ids)
    original_freeze = load_json_object(source_freeze)
    source_freeze_sha256 = verify_self_hash(original_freeze, "freezeSha256", "source campaign freeze")
    questions_sha256 = sha256_file(source_questions)
    if original_freeze.get("questionsSha256") != questions_sha256:
        raise ValueError("source campaign freeze questionsSha256 mismatch")
    if original_freeze.get("expectedIdsSha256") != canonical_digest(ids):
        raise ValueError("source campaign freeze expectedIdsSha256 mismatch")

    source_candidates = [candidate_path(source_campaign, index) for index in indices]
    candidates = [answer_map(path, ids) for path in source_candidates]

    input_dir = campaign_dir / "solver/input"
    output_dir = campaign_dir / "solver/output"
    candidate_dir = input_dir / "candidates"
    output_dir.mkdir(parents=True, exist_ok=True)
    candidate_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_questions, input_dir / "questions.jsonl")
    write_json(input_dir / "expected_ids.json", {"count": len(ids), "ids": ids})
    (input_dir / "RUN_INSTRUCTIONS.md").write_text(INSTRUCTIONS, encoding="utf-8")
    for name, source in zip(("base", "auxiliary_1", "auxiliary_2"), source_candidates):
        shutil.copy2(source, candidate_dir / f"{name}.jsonl")

    overlap_rows: list[dict[str, Any]] = []
    eligible_ids: list[str] = []
    mcq_rows = 0
    eligible_mcq_ids: list[str] = []
    for question in questions:
        case_id = question["id"]
        response_format = question["responseFormat"]
        prompt = question["prompt"]
        options = parse_mcq_options(prompt) if response_format == "mcq" else {}
        keys = (
            [canonical_mcq_option_key(candidate[case_id], options) for candidate in candidates]
            if response_format == "mcq"
            else ["", "", ""]
        )
        canonical_mapping_complete = bool(options and all(keys))
        auxiliary_agreement = bool(canonical_mapping_complete and keys[1] == keys[2])
        different_from_base = bool(auxiliary_agreement and keys[1] != keys[0])
        eligible = bool(response_format == "mcq" and different_from_base)
        if response_format != "mcq":
            eligibility_reason = "non_mcq_excluded"
        elif not options:
            eligibility_reason = "mcq_options_unparseable"
        elif not canonical_mapping_complete:
            eligibility_reason = "candidate_option_mapping_incomplete"
        elif not auxiliary_agreement:
            eligibility_reason = "auxiliary_option_ids_disagree"
        elif not different_from_base:
            eligibility_reason = "auxiliaries_agree_with_base"
        else:
            eligibility_reason = "canonical_auxiliary_overlap_differs_from_base"
        if response_format == "mcq":
            mcq_rows += 1
        if eligible:
            eligible_ids.append(case_id)
            if response_format == "mcq":
                eligible_mcq_ids.append(case_id)
        overlap_rows.append(
            {
                "id": case_id,
                "responseFormat": response_format,
                "baseKey": keys[0],
                "auxiliary1Key": keys[1],
                "auxiliary2Key": keys[2],
                "keyType": "canonical_mcq_option_id",
                "canonicalMappingComplete": canonical_mapping_complete,
                "auxiliaryAgreement": auxiliary_agreement,
                "differentFromBase": different_from_base,
                "eligible": eligible,
                "eligibilityReason": eligibility_reason,
            }
        )
    overlap_path = input_dir / "overlap_manifest.jsonl"
    write_jsonl(overlap_path, overlap_rows)

    candidate_hashes = {
        "base": sha256_file(candidate_dir / "base.jsonl"),
        "auxiliary_1": sha256_file(candidate_dir / "auxiliary_1.jsonl"),
        "auxiliary_2": sha256_file(candidate_dir / "auxiliary_2.jsonl"),
    }
    provenance = {
        name: candidate_provenance(
            source_campaign=source_campaign,
            campaign_dir=campaign_dir,
            name=name,
            index=index,
            answers_path=source_path,
            answers_sha256=candidate_hashes[name],
            source_freeze=original_freeze,
            questions_sha256=questions_sha256,
            expected_rows=len(ids),
        )
        for name, index, source_path in zip(
            ("base", "auxiliary_1", "auxiliary_2"), indices, source_candidates
        )
    }
    freeze: dict[str, Any] = {
        "schemaVersion": 1,
        "status": "prepared_no_model_calls",
        "protocol": "mini_artichokes_candidate_overlap_adjudication_v2",
        "candidateMechanism": "base_plus_two_canonical_mcq_option_agreement_then_independent_validation",
        "sourceCampaign": str(source_campaign.resolve()),
        "sourceFreezeSha256": source_freeze_sha256,
        "sourceFreezeFileSha256": sha256_file(source_freeze),
        "sourceQuestionsSha256": questions_sha256,
        "sourceExpectedIdsFileSha256": sha256_file(source_expected),
        "questionsPath": "input/questions.jsonl",
        "questionsSha256": sha256_file(input_dir / "questions.jsonl"),
        "instructionsSha256": sha256_file(input_dir / "RUN_INSTRUCTIONS.md"),
        "expectedIdsFileSha256": sha256_file(input_dir / "expected_ids.json"),
        "expectedIdsSha256": canonical_digest(ids),
        "overlapManifestSha256": sha256_file(overlap_path),
        "eligibleIdsSha256": canonical_digest(eligible_ids),
        "eligibleMcqIdsSha256": canonical_digest(eligible_mcq_ids),
        "candidateIndices": {
            "base": base_index,
            "auxiliary_1": auxiliary_indices[0],
            "auxiliary_2": auxiliary_indices[1],
        },
        "candidateAnswersSha256": candidate_hashes,
        "candidateBundleSha256": canonical_digest(candidate_hashes),
        "candidateProvenance": provenance,
        "candidateProvenanceComplete": all(item.get("status") == "accepted" for item in provenance.values()),
        "candidateProvenanceSha256": canonical_digest(provenance),
        "inventory": {
            "rows": len(ids),
            "eligibleRows": len(eligible_ids),
            "ineligibleRows": len(ids) - len(eligible_ids),
            "mcqRows": mcq_rows,
            "eligibleMcqRows": len(eligible_mcq_ids),
        },
        "executionConfig": {
            "model": model,
            "reasoningEffort": reasoning_effort,
            "verbosity": verbosity,
            "serviceTier": "default",
            "nativeWebSearch": True,
            "localCode": True,
            "database": False,
            "skills": False,
            "multiAgent": False,
        },
        "implementationHashes": {
            str(Path(__file__).resolve()): sha256_file(Path(__file__).resolve()),
            str((REPO_ROOT / "tools/run_plain_codex_file_agent.py").resolve()): sha256_file(
                REPO_ROOT / "tools/run_plain_codex_file_agent.py"
            ),
            str((REPO_ROOT / "tools/run_ensemble_file_agent.py").resolve()): sha256_file(
                REPO_ROOT / "tools/run_ensemble_file_agent.py"
            ),
            str((REPO_ROOT / "tools/validate_overlap_adjudication.py").resolve()): sha256_file(
                REPO_ROOT / "tools/validate_overlap_adjudication.py"
            ),
        },
    }
    freeze["freezeSha256"] = canonical_digest(freeze)
    write_json(campaign_dir / "solver/freeze.json", freeze)
    return freeze


def parse_indices(value: str) -> tuple[int, int]:
    parts = [int(part.strip()) for part in value.split(",") if part.strip()]
    if len(parts) != 2 or len(set(parts)) != 2:
        raise argparse.ArgumentTypeError("expected two distinct comma-separated indices")
    return parts[0], parts[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-campaign", type=Path, required=True)
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--base-index", type=int, required=True)
    parser.add_argument("--auxiliary-indices", type=parse_indices, required=True)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--reasoning-effort", default="high")
    parser.add_argument("--verbosity", default="low")
    args = parser.parse_args()
    if args.base_index in args.auxiliary_indices:
        parser.error("base index must differ from auxiliary indices")
    freeze = prepare(
        source_campaign=args.source_campaign.resolve(),
        campaign_dir=args.campaign_dir.resolve(),
        base_index=args.base_index,
        auxiliary_indices=args.auxiliary_indices,
        model=args.model,
        reasoning_effort=args.reasoning_effort,
        verbosity=args.verbosity,
    )
    print(json.dumps(freeze, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
