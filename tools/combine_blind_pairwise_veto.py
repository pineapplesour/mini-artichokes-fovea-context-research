#!/usr/bin/env python3
"""Fail-closed, gold-free combination of strict overlap and blind veto.

The combiner accepts two already-completed upstream campaigns over the same
frozen 1,309-row public suite:

* a strict candidate-overlap adjudication (V3 protocol), and
* a role-blind pairwise-veto campaign prepared from that exact adjudication.

It revalidates both upstreams, including their raw traces and provenance, and
then publishes four deterministic answer files.  It never reads gold, grades,
or private analysis.  Every output answer is copied byte-for-byte from either
the frozen base candidate or ``auxiliary_1``; there is no synthesis path.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import run_blind_pairwise_veto_agent as blind_runner
from tools import run_plain_codex_file_agent as plain_runner
from tools.prepare_blind_pairwise_veto import PROTOCOL as BLIND_PROTOCOL
from tools.prepare_blind_pairwise_veto import lf_jsonl_lines
from tools.prepare_plain_codex_file_benchmark import canonical_digest, sha256_file
from tools.validate_blind_pairwise_veto import validate_blind_pairwise_veto
from tools.validate_overlap_adjudication import (
    DECISION_RE,
    validate_overlap_adjudication,
)


PROTOCOL = "mini_artichokes_blind_pairwise_veto_combination_v1"
STRICT_PROTOCOL = "mini_artichokes_candidate_overlap_adjudication_v2"
EXPECTED_ROWS = 1309
EXPECTED_ELIGIBLE_ROWS = 247
POLICIES = ("base", "blind_only", "intersection", "union")
SOURCE_NAMES = ("base", "auxiliary_1", "auxiliary_2")
HEX_SHA256 = set("0123456789abcdef")


class CombinationValidationError(ValueError):
    """Raised before publication whenever an upstream binding is invalid."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CombinationValidationError(message)


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in HEX_SHA256 for character in value)
    )


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CombinationValidationError(f"invalid JSON object: {path}: {exc}") from exc
    _require(isinstance(value, dict), f"JSON root is not an object: {path}")
    return value


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        lines = lf_jsonl_lines(path)
    except (OSError, UnicodeDecodeError) as exc:
        raise CombinationValidationError(f"unable to read JSONL: {path}: {exc}") from exc
    rows: list[dict[str, Any]] = []
    for line_number, raw in enumerate(lines, 1):
        _require(bool(raw.strip()), f"blank JSONL line: {path}:{line_number}")
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CombinationValidationError(
                f"invalid JSONL line: {path}:{line_number}: {exc}"
            ) from exc
        _require(isinstance(value, dict), f"non-object JSONL row: {path}:{line_number}")
        rows.append(value)
    return rows


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def _verify_self_hash(value: dict[str, Any], field: str, label: str) -> str:
    claimed = value.get(field)
    _require(_is_sha256(claimed), f"{label} has no valid {field}")
    observed = canonical_digest({key: item for key, item in value.items() if key != field})
    _require(claimed == observed, f"{label} {field} mismatch")
    return str(claimed)


def _verify_file_hash(path: Path, expected: Any, label: str) -> str:
    _require(path.is_file(), f"{label} is missing: {path}")
    observed = sha256_file(path)
    _require(_is_sha256(expected) and observed == expected, f"{label} hash mismatch")
    return observed


def _safe_campaign_path(campaign: Path, relative: Any, label: str) -> Path:
    _require(isinstance(relative, str) and bool(relative), f"{label} path is invalid")
    raw = Path(relative)
    _require(not raw.is_absolute() and ".." not in raw.parts, f"{label} path escapes campaign")
    resolved = (campaign / raw).resolve()
    try:
        resolved.relative_to(campaign)
    except ValueError as exc:
        raise CombinationValidationError(f"{label} path escapes campaign") from exc
    return resolved


def _verify_absolute_hash_map(value: Any, label: str) -> dict[str, str]:
    _require(isinstance(value, dict) and bool(value), f"{label} is missing")
    hashes: dict[str, str] = {}
    for raw_path, expected in value.items():
        _require(isinstance(raw_path, str) and Path(raw_path).is_absolute(), f"{label} path invalid")
        path = Path(raw_path)
        hashes[raw_path] = _verify_file_hash(path, expected, f"{label}:{path.name}")
    return hashes


def _verify_module_hash_map(value: Any, label: str) -> dict[str, str]:
    _require(isinstance(value, dict) and bool(value), f"{label} is missing")
    hashes: dict[str, str] = {}
    modules: set[str] = set()
    for raw_key, expected in value.items():
        _require(isinstance(raw_key, str) and "|" in raw_key, f"{label} key invalid")
        module_name, relative = raw_key.split("|", 1)
        raw_path = Path(relative)
        script_entry_point = (
            module_name == "__main__" and relative == "tools/run_blind_pairwise_veto_agent.py"
        )
        _require(
            (module_name.startswith("tools.") or script_entry_point)
            and not raw_path.is_absolute()
            and ".." not in raw_path.parts,
            f"{label} module/path invalid: {raw_key}",
        )
        path = (REPO_ROOT / raw_path).resolve()
        try:
            path.relative_to(REPO_ROOT)
        except ValueError as exc:
            raise CombinationValidationError(f"{label} path escapes repository") from exc
        hashes[raw_key] = _verify_file_hash(path, expected, f"{label}:{raw_key}")
        modules.add("tools.run_blind_pairwise_veto_agent" if script_entry_point else module_name)
    required = {
        "tools.run_blind_pairwise_veto_agent",
        "tools.run_plain_codex_file_agent",
        "tools.benchmark_provider",
        "tools.validate_blind_pairwise_veto",
    }
    _require(required.issubset(modules), f"{label} lacks required implementations")
    return hashes


def _read_expected_ids(path: Path, *, label: str) -> list[str]:
    value = _load_json(path)
    raw_ids = value.get("ids")
    _require(
        isinstance(raw_ids, list)
        and all(isinstance(case_id, str) and bool(case_id) for case_id in raw_ids),
        f"{label} IDs are invalid",
    )
    ids = [str(case_id) for case_id in raw_ids]
    _require(value.get("count") == len(ids), f"{label} count mismatch")
    _require(len(ids) == len(set(ids)), f"{label} contains duplicate IDs")
    return ids


def _read_answers(path: Path, expected_ids: list[str], *, label: str) -> dict[str, str]:
    rows = _load_jsonl(path)
    observed: list[str] = []
    answers: dict[str, str] = {}
    for position, row in enumerate(rows, 1):
        _require(set(row) == {"id", "finalAnswer"}, f"{label} row {position} schema")
        case_id = row.get("id")
        answer = row.get("finalAnswer")
        _require(isinstance(case_id, str) and bool(case_id), f"{label} row {position} ID")
        _require(isinstance(answer, str) and bool(answer), f"{label} row {position} answer")
        observed.append(case_id)
        _require(case_id not in answers, f"{label} duplicate ID")
        answers[case_id] = answer
    _require(observed == expected_ids, f"{label} IDs/order mismatch")
    return answers


def _thread_identity(trace_path: Path, *, label: str) -> list[str]:
    _require(trace_path.is_file(), f"{label} trace missing")
    started = 0
    malformed = 0
    ids: list[str] = []
    for raw in trace_path.read_text(encoding="utf-8").split("\n"):
        if not raw.strip():
            continue
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict) or event.get("type") != "thread.started":
            continue
        started += 1
        thread_id = event.get("thread_id") or event.get("threadId")
        if thread_id is None and isinstance(event.get("thread"), dict):
            thread_id = event["thread"].get("id")
        if not isinstance(thread_id, str) or not thread_id.strip():
            malformed += 1
        elif thread_id not in ids:
            ids.append(thread_id)
    _require(started == 1 and malformed == 0 and len(ids) == 1, f"{label} trace thread invalid")
    return ids


def _verify_source_freeze(
    source_campaign: Path,
    *,
    expected_ids: list[str],
    expected_questions_sha256: str,
) -> tuple[dict[str, Any], dict[str, str]]:
    solver = source_campaign / "solver"
    freeze_path = solver / "freeze.json"
    questions_path = solver / "input/questions.jsonl"
    expected_path = solver / "input/expected_ids.json"
    freeze = _load_json(freeze_path)
    freeze_hash = _verify_self_hash(freeze, "freezeSha256", "source freeze")
    _require(freeze.get("status") == "prepared_no_model_calls", "source freeze status")
    _verify_file_hash(questions_path, expected_questions_sha256, "source questions")
    _require(_read_expected_ids(expected_path, label="source expected") == expected_ids, "source IDs")
    _require(freeze.get("questionsSha256") == expected_questions_sha256, "source freeze questions")
    _require(freeze.get("expectedIdsSha256") == canonical_digest(expected_ids), "source freeze IDs")
    if "implementationHashes" in freeze:
        _verify_absolute_hash_map(freeze["implementationHashes"], "source implementation hashes")
    if "sourcePublicManifestHashes" in freeze:
        _verify_absolute_hash_map(
            freeze["sourcePublicManifestHashes"], "source public manifest hashes"
        )
    if isinstance(freeze.get("registryPath"), str) and "registrySha256" in freeze:
        _verify_file_hash(
            Path(freeze["registryPath"]), freeze["registrySha256"], "source registry"
        )
    return freeze, {
        "freezeSha256": freeze_hash,
        "freezeFileSha256": sha256_file(freeze_path),
        "questionsSha256": sha256_file(questions_path),
        "expectedIdsFileSha256": sha256_file(expected_path),
    }


def _verify_candidate_provenance(
    strict_campaign: Path,
    *,
    strict_freeze: dict[str, Any],
    source_campaign: Path,
    source_freeze: dict[str, Any],
    expected_ids: list[str],
    candidate_hashes: dict[str, str],
) -> dict[str, Any]:
    provenance = strict_freeze.get("candidateProvenance")
    indices = strict_freeze.get("candidateIndices")
    _require(isinstance(provenance, dict) and set(provenance) == set(SOURCE_NAMES), "candidate provenance")
    _require(isinstance(indices, dict) and set(indices) == set(SOURCE_NAMES), "candidate indices")
    _require(strict_freeze.get("candidateProvenanceComplete") is True, "candidate provenance incomplete")
    _require(
        strict_freeze.get("candidateProvenanceSha256") == canonical_digest(provenance),
        "candidate provenance digest mismatch",
    )
    summaries: dict[str, Any] = {}
    for name in SOURCE_NAMES:
        item = provenance[name]
        _require(isinstance(item, dict) and item.get("status") == "accepted", f"{name} provenance")
        index = indices[name]
        _require(
            isinstance(index, int) and not isinstance(index, bool) and index > 0,
            f"{name} candidate index",
        )
        _require(item.get("candidateIndex") == index, f"{name} provenance index")
        _require(item.get("answersSha256") == candidate_hashes[name], f"{name} answer hash")
        _require(
            item.get("sourceFreezeSha256") == source_freeze.get("freezeSha256"),
            f"{name} source freeze binding",
        )
        source_solver = source_campaign / "drafts" / f"d{index}" / "solver"
        source_answers = source_solver / "output/answers.jsonl"
        _require(
            item.get("answersSourcePath") == str(source_answers.resolve()),
            f"{name} source answer path",
        )
        _verify_file_hash(source_answers, candidate_hashes[name], f"{name} source answers")

        artifacts = item.get("artifacts")
        _require(
            isinstance(artifacts, dict)
            and set(artifacts) == {"sourceFreeze", "runReceipt", "answerValidation"},
            f"{name} artifact manifest",
        )
        copied: dict[str, tuple[Path, dict[str, Any]]] = {}
        for artifact_name, manifest in artifacts.items():
            _require(
                isinstance(manifest, dict) and set(manifest) == {"path", "sha256"},
                f"{name} {artifact_name} manifest",
            )
            path = _safe_campaign_path(
                strict_campaign, manifest["path"], f"{name} {artifact_name}"
            )
            _verify_file_hash(path, manifest["sha256"], f"{name} {artifact_name}")
            copied[artifact_name] = (path, _load_json(path))

        copied_freeze = copied["sourceFreeze"][1]
        _verify_self_hash(copied_freeze, "freezeSha256", f"{name} copied freeze")
        _require(copied_freeze == source_freeze, f"{name} copied freeze differs")
        _require(
            _load_json(source_solver / "freeze.json") == copied_freeze,
            f"{name} original freeze differs",
        )
        copied_receipt = copied["runReceipt"][1]
        receipt_hash = _verify_self_hash(
            copied_receipt, "receiptSha256", f"{name} candidate receipt"
        )
        _require(item.get("receiptSha256") == receipt_hash, f"{name} receipt binding")
        _require(
            _load_json(source_solver / "run_receipt.json") == copied_receipt,
            f"{name} original receipt differs",
        )
        validation = copied["answerValidation"][1]
        _require(
            _load_json(source_solver / "answer_validation.json") == validation,
            f"{name} original validation differs",
        )
        for report_label, report in (
            ("receipt artifact", copied_receipt.get("artifactValidation")),
            ("standalone", validation),
        ):
            _require(isinstance(report, dict), f"{name} {report_label} validation")
            _require(
                report.get("status") == "accepted"
                and report.get("passed") is True
                and report.get("errors") in (None, [])
                and report.get("expectedRows") == len(expected_ids)
                and report.get("observedRows") == len(expected_ids)
                and report.get("answersSha256") == candidate_hashes[name],
                f"{name} {report_label} validation rejected",
            )
        process = copied_receipt.get("process")
        _require(
            copied_receipt.get("status") == "accepted"
            and copied_receipt.get("role") == "solver"
            and copied_receipt.get("semanticModelInvocations") == 1
            and copied_receipt.get("freezeSha256") == source_freeze.get("freezeSha256")
            and copied_receipt.get("payloadSha256") == strict_freeze.get("questionsSha256")
            and copied_receipt.get("acceptedArtifact") == "answers.jsonl"
            and isinstance(process, dict)
            and process.get("exitCode") == 0
            and process.get("timedOut") is False
            and isinstance(copied_receipt.get("isolationProbe"), dict)
            and copied_receipt["isolationProbe"].get("passed") is True,
            f"{name} candidate receipt rejected",
        )
        execution = source_freeze.get("executionConfig")
        if isinstance(execution, dict):
            _require(
                copied_receipt.get("model") == execution.get("model")
                and copied_receipt.get("reasoningEffort") == execution.get("reasoningEffort")
                and copied_receipt.get("verbosity") == execution.get("verbosity"),
                f"{name} execution config mismatch",
            )
        trace_path = source_solver / "codex_trace.jsonl"
        trace_questions = source_solver / "input/questions.jsonl"
        _verify_file_hash(
            trace_questions, strict_freeze.get("questionsSha256"), f"{name} trace questions"
        )
        recomputed_audit = plain_runner.audit_trace(
            trace_path=trace_path,
            questions_path=trace_questions,
            role="solver",
            return_code=process["exitCode"],
        )
        _require(
            recomputed_audit.get("passed") is True
            and copied_receipt.get("policyAudit") == recomputed_audit,
            f"{name} raw trace audit mismatch",
        )
        thread_ids = _thread_identity(trace_path, label=f"{name} candidate")
        summaries[name] = {
            "candidateIndex": index,
            "answersSha256": candidate_hashes[name],
            "receiptSha256": receipt_hash,
            "receiptFileSha256": sha256_file(copied["runReceipt"][0]),
            "validationFileSha256": sha256_file(copied["answerValidation"][0]),
            "rawTraceSha256": sha256_file(trace_path),
            "threadIds": thread_ids,
        }
    return summaries


def _verify_strict_campaign(campaign: Path) -> dict[str, Any]:
    campaign = campaign.resolve()
    solver = campaign / "solver"
    input_dir = solver / "input"
    output_dir = solver / "output"
    freeze_path = solver / "freeze.json"
    freeze = _load_json(freeze_path)
    freeze_hash = _verify_self_hash(freeze, "freezeSha256", "strict freeze")
    _require(freeze.get("protocol") == STRICT_PROTOCOL, "strict protocol mismatch")
    _require(freeze.get("status") == "prepared_no_model_calls", "strict freeze status")
    inventory = freeze.get("inventory")
    _require(
        isinstance(inventory, dict)
        and inventory.get("rows") == EXPECTED_ROWS
        and inventory.get("eligibleRows") == EXPECTED_ELIGIBLE_ROWS
        and inventory.get("ineligibleRows") == EXPECTED_ROWS - EXPECTED_ELIGIBLE_ROWS
        and inventory.get("eligibleMcqRows") == EXPECTED_ELIGIBLE_ROWS,
        "strict inventory mismatch",
    )
    _verify_absolute_hash_map(freeze.get("implementationHashes"), "strict implementation hashes")

    expected_path = input_dir / "expected_ids.json"
    questions_path = input_dir / "questions.jsonl"
    instructions_path = input_dir / "RUN_INSTRUCTIONS.md"
    manifest_path = input_dir / "overlap_manifest.jsonl"
    expected_ids = _read_expected_ids(expected_path, label="strict expected")
    _require(len(expected_ids) == EXPECTED_ROWS, "strict row count mismatch")
    _require(freeze.get("expectedIdsSha256") == canonical_digest(expected_ids), "strict ID digest")
    _verify_file_hash(expected_path, freeze.get("expectedIdsFileSha256"), "strict expected IDs")
    _verify_file_hash(questions_path, freeze.get("questionsSha256"), "strict questions")
    _verify_file_hash(instructions_path, freeze.get("instructionsSha256"), "strict instructions")
    _verify_file_hash(manifest_path, freeze.get("overlapManifestSha256"), "strict manifest")
    questions = _load_jsonl(questions_path)
    _require([row.get("id") for row in questions] == expected_ids, "strict question order")
    manifest = _load_jsonl(manifest_path)
    _require([row.get("id") for row in manifest] == expected_ids, "strict manifest order")
    eligible_ids = [
        str(row["id"])
        for row in manifest
        if isinstance(row.get("eligible"), bool) and row["eligible"]
    ]
    _require(len(eligible_ids) == EXPECTED_ELIGIBLE_ROWS, "strict eligible count")
    _require(freeze.get("eligibleIdsSha256") == canonical_digest(eligible_ids), "strict eligible hash")
    _require(
        freeze.get("eligibleMcqIdsSha256") == canonical_digest(eligible_ids),
        "strict eligible MCQ hash",
    )

    candidate_hashes = freeze.get("candidateAnswersSha256")
    _require(
        isinstance(candidate_hashes, dict) and set(candidate_hashes) == set(SOURCE_NAMES),
        "strict candidate hashes",
    )
    _require(
        freeze.get("candidateBundleSha256") == canonical_digest(candidate_hashes),
        "strict candidate bundle hash",
    )
    candidates: dict[str, dict[str, str]] = {}
    for name in SOURCE_NAMES:
        path = input_dir / "candidates" / f"{name}.jsonl"
        _verify_file_hash(path, candidate_hashes[name], f"strict candidate {name}")
        candidates[name] = _read_answers(path, expected_ids, label=f"strict candidate {name}")

    source_campaign = Path(str(freeze.get("sourceCampaign") or "")).resolve()
    _require(source_campaign.is_dir(), "strict source campaign missing")
    source_freeze, source_summary = _verify_source_freeze(
        source_campaign,
        expected_ids=expected_ids,
        expected_questions_sha256=sha256_file(questions_path),
    )
    _require(freeze.get("sourceFreezeSha256") == source_summary["freezeSha256"], "strict source freeze")
    _require(
        freeze.get("sourceFreezeFileSha256") == source_summary["freezeFileSha256"],
        "strict source freeze file",
    )
    _require(
        freeze.get("sourceQuestionsSha256") == source_summary["questionsSha256"],
        "strict source questions",
    )
    _require(
        freeze.get("sourceExpectedIdsFileSha256") == source_summary["expectedIdsFileSha256"],
        "strict source expected IDs",
    )
    candidate_provenance = _verify_candidate_provenance(
        campaign,
        strict_freeze=freeze,
        source_campaign=source_campaign,
        source_freeze=source_freeze,
        expected_ids=expected_ids,
        candidate_hashes={name: str(candidate_hashes[name]) for name in SOURCE_NAMES},
    )

    report = validate_overlap_adjudication(campaign, write_report=False)
    _require(
        report.get("passed") is True
        and report.get("status") == "accepted"
        and report.get("errors") == []
        and report.get("expectedRows") == EXPECTED_ROWS
        and report.get("observedRows") == EXPECTED_ROWS
        and report.get("eligibleRows") == EXPECTED_ELIGIBLE_ROWS,
        "strict validator rejected campaign",
    )
    report_path = solver / "overlap_validation.json"
    persisted_report = _load_json(report_path)
    _require(persisted_report == report, "strict validation report is stale or tampered")

    answers_path = output_dir / "answers.jsonl"
    decisions_path = output_dir / "decisions.log"
    final_answers = _read_answers(answers_path, expected_ids, label="strict output")
    _require(report.get("answersSha256") == sha256_file(answers_path), "strict answer report hash")
    _require(report.get("decisionsSha256") == sha256_file(decisions_path), "strict decision report hash")
    decisions: list[dict[str, str]] = []
    for line_number, raw in enumerate(decisions_path.read_text(encoding="utf-8").splitlines(), 1):
        match = DECISION_RE.fullmatch(raw)
        _require(match is not None, f"strict decision line invalid: {line_number}")
        decisions.append({key: value.strip() for key, value in match.groupdict().items()})
    _require([item["id"] for item in decisions] == eligible_ids, "strict decision order")
    strict_switch_ids = [
        item["id"]
        for item in decisions
        if item["gate"] == "VALID" and item["action"] == "SWITCH"
    ]
    _require(report.get("switchRows") == len(strict_switch_ids), "strict switch count")

    receipt_path = solver / "run_receipt.json"
    receipt = _load_json(receipt_path)
    receipt_hash = _verify_self_hash(receipt, "receiptSha256", "strict receipt")
    process = receipt.get("process")
    _require(
        receipt.get("status") == "accepted"
        and receipt.get("role") == "solver"
        and receipt.get("semanticModelInvocations") == 1
        and receipt.get("freezeSha256") == freeze_hash
        and receipt.get("payloadSha256") == freeze.get("questionsSha256")
        and receipt.get("acceptedArtifact") == "answers.jsonl"
        and isinstance(process, dict)
        and process.get("exitCode") == 0
        and process.get("timedOut") is False
        and isinstance(receipt.get("isolationProbe"), dict)
        and receipt["isolationProbe"].get("passed") is True,
        "strict receipt rejected",
    )
    _require(
        receipt.get("inputIntegrity")
        == plain_runner.verify_frozen_inputs(campaign_dir=campaign, role="solver"),
        "strict input-integrity receipt mismatch",
    )
    trace_path = solver / "codex_trace.jsonl"
    trace_audit = plain_runner.audit_trace(
        trace_path=trace_path,
        questions_path=questions_path,
        role="solver",
        return_code=process["exitCode"],
    )
    _require(
        trace_audit.get("passed") is True and receipt.get("policyAudit") == trace_audit,
        "strict raw trace audit mismatch",
    )
    strict_thread_ids = _thread_identity(trace_path, label="strict")
    _require(receipt.get("artifactValidation") == report, "strict receipt validation mismatch")
    for case_id in expected_ids:
        expected = (
            candidates["auxiliary_1"][case_id]
            if case_id in set(strict_switch_ids)
            else candidates["base"][case_id]
        )
        _require(final_answers[case_id] == expected, f"strict output mismatch: {case_id}")
    return {
        "campaign": campaign,
        "freeze": freeze,
        "freezePath": freeze_path,
        "receipt": receipt,
        "receiptPath": receipt_path,
        "report": report,
        "reportPath": report_path,
        "tracePath": trace_path,
        "threadIds": strict_thread_ids,
        "expectedIds": expected_ids,
        "eligibleIds": eligible_ids,
        "questions": questions,
        "manifest": manifest,
        "candidates": candidates,
        "candidateHashes": candidate_hashes,
        "candidateProvenance": candidate_provenance,
        "strictSwitchIds": strict_switch_ids,
        "sourceSummary": source_summary,
        "sourceCampaign": source_campaign,
        "freezeSha256": freeze_hash,
        "receiptSha256": receipt_hash,
    }


def _verify_binary_identity(identity: Any, label: str) -> dict[str, Any]:
    _require(isinstance(identity, dict), f"{label} identity missing")
    required = {"path", "resolvedPath", "sha256", "bytes"}
    _require(set(identity) == required, f"{label} identity schema")
    path = Path(str(identity["path"]))
    resolved = Path(str(identity["resolvedPath"]))
    _require(path.is_file() and resolved.is_file(), f"{label} binary missing")
    _require(path.resolve() == resolved.resolve(), f"{label} resolved path mismatch")
    _require(identity["bytes"] == resolved.stat().st_size, f"{label} byte count mismatch")
    _verify_file_hash(resolved, identity["sha256"], f"{label} binary")
    return dict(identity)


def _verify_blind_campaign(campaign: Path) -> dict[str, Any]:
    campaign = campaign.resolve()
    freeze, paths, input_hashes = blind_runner.verify_frozen_bundle(campaign)
    freeze_hash = _verify_self_hash(freeze, "freezeSha256", "blind freeze")
    _require(freeze.get("status") == "prepared_no_model_calls", "blind freeze status")
    _verify_absolute_hash_map(freeze.get("implementationHashes"), "blind freeze implementations")
    execution = freeze.get("executionConfig")
    _require(isinstance(execution, dict), "blind execution config missing")
    verified_execution = blind_runner.verify_execution_config(
        freeze,
        model=str(execution.get("model") or ""),
        reasoning_effort=str(execution.get("reasoningEffort") or ""),
        verbosity=str(execution.get("verbosity") or ""),
    )
    _require(verified_execution == execution, "blind execution config mismatch")

    report = validate_blind_pairwise_veto(campaign, write_report=False)
    _require(
        report.get("passed") is True
        and report.get("status") == "accepted"
        and report.get("errors") == []
        and report.get("questionRows") == EXPECTED_ROWS
        and report.get("conflictRows") == EXPECTED_ELIGIBLE_ROWS
        and report.get("certificateRows") == EXPECTED_ELIGIBLE_ROWS,
        "blind strict validator rejected campaign",
    )
    persisted_report = _load_json(paths["validationReport"])
    _require(persisted_report == report, "blind validation report is stale or tampered")

    receipt = _load_json(paths["receipt"])
    receipt_hash = _verify_self_hash(receipt, "receiptSha256", "blind receipt")
    _require(
        receipt.get("schemaVersion") == 1
        and receipt.get("status") == "accepted"
        and receipt.get("protocol") == BLIND_PROTOCOL
        and receipt.get("semanticModelInvocations") == 1
        and receipt.get("freezeSha256") == freeze_hash
        and receipt.get("inputFileSha256") == input_hashes
        and receipt.get("executionConfig") == execution
        and receipt.get("acceptedArtifact") == "output/certificates.jsonl",
        "blind receipt rejected",
    )
    _verify_module_hash_map(receipt.get("implementationHashes"), "blind receipt implementations")
    cli = receipt.get("codexCli")
    _require(isinstance(cli, dict), "blind Codex CLI identity missing")
    for field in ("launcher", "node", "entryPoint", "bubblewrap"):
        _verify_binary_identity(cli.get(field), f"blind Codex CLI {field}")
    _require(
        isinstance(cli.get("version"), str)
        and bool(cli["version"].strip())
        and _is_sha256(cli.get("commandSha256"))
        and isinstance(cli.get("commandArgumentCount"), int)
        and cli["commandArgumentCount"] > 0,
        "blind Codex CLI command identity invalid",
    )
    visibility = receipt.get("visibilityBoundary")
    _require(
        isinstance(visibility, dict)
        and visibility.get("hiddenControlMounted") is False
        and visibility.get("publicReadOnlyGuestPath") == "/tmp/work/input"
        and visibility.get("writableGuestPath") == "/tmp/work/output"
        and visibility.get("policy") == "bubblewrap_public_input_only",
        "blind visibility boundary invalid",
    )
    _require(
        isinstance(receipt.get("isolationProbe"), dict)
        and receipt["isolationProbe"].get("passed") is True,
        "blind isolation probe rejected",
    )
    process = receipt.get("process")
    _require(
        isinstance(process, dict)
        and process.get("exitCode") == 0
        and process.get("timedOut") is False,
        "blind process rejected",
    )
    trace_audit = blind_runner.audit_veto_trace(
        trace_path=paths["trace"],
        questions_path=paths["questions"],
        return_code=process["exitCode"],
        native_web_search=False,
    )
    _require(
        trace_audit.get("passed") is True
        and trace_audit.get("rawWebSearchEventCount") == 0
        and receipt.get("policyAudit") == trace_audit,
        "blind raw trace audit mismatch",
    )
    thread_ids = _thread_identity(paths["trace"], label="blind")
    artifacts = receipt.get("artifacts")
    _require(isinstance(artifacts, dict), "blind artifact receipt missing")
    artifact_paths = {
        "rawTraceSha256": paths["trace"],
        "stderrSha256": paths["stderr"],
        "certificatesSha256": paths["certificates"],
        "lastMessageSha256": paths["lastMessage"],
        "validationReportSha256": paths["validationReport"],
    }
    for receipt_key, path in artifact_paths.items():
        _verify_file_hash(path, artifacts.get(receipt_key), f"blind artifact {receipt_key}")
    _require(artifacts.get("threadIds") == thread_ids, "blind receipt thread IDs mismatch")
    _require(paths["lastMessage"].stat().st_size > 0, "blind last message empty")
    output_names = sorted(path.name for path in paths["outputDir"].iterdir())
    _require(output_names == ["certificates.jsonl", "last_message.txt"], "blind output set invalid")
    stored_validation = receipt.get("artifactValidation")
    _require(isinstance(stored_validation, dict), "blind artifact validation missing")
    _require(
        stored_validation.get("passed") is True
        and stored_validation.get("errors") == []
        and stored_validation.get("certificatesSha256") == sha256_file(paths["certificates"])
        and stored_validation.get("lastMessageSha256") == sha256_file(paths["lastMessage"])
        and stored_validation.get("outputFileNames") == output_names
        and stored_validation.get("unexpectedOutputFileNames") == []
        and stored_validation.get("validationReportSha256")
        == sha256_file(paths["validationReport"])
        and stored_validation.get("strictValidatorReport") == report,
        "blind artifact validation receipt mismatch",
    )

    expected_ids = _read_expected_ids(paths["expectedCertificateIds"], label="blind expected")
    questions = _load_jsonl(paths["questions"])
    pairs = _load_jsonl(paths["candidatePairs"])
    mapping_path = _safe_campaign_path(campaign, freeze.get("roleMappingPath"), "role mapping")
    mapping = _load_jsonl(mapping_path)
    certificates = _load_jsonl(paths["certificates"])
    _require(
        [row.get("id") for row in pairs]
        == [row.get("id") for row in mapping]
        == [row.get("id") for row in certificates]
        == expected_ids,
        "blind pair/mapping/certificate order mismatch",
    )
    return {
        "campaign": campaign,
        "freeze": freeze,
        "freezePath": paths["freeze"],
        "freezeSha256": freeze_hash,
        "receipt": receipt,
        "receiptPath": paths["receipt"],
        "receiptSha256": receipt_hash,
        "report": report,
        "reportPath": paths["validationReport"],
        "tracePath": paths["trace"],
        "threadIds": thread_ids,
        "paths": paths,
        "expectedIds": expected_ids,
        "questions": questions,
        "pairs": pairs,
        "mapping": mapping,
        "certificates": certificates,
    }


def _verify_cross_campaign(strict: dict[str, Any], blind: dict[str, Any]) -> None:
    strict_freeze = strict["freeze"]
    blind_freeze = blind["freeze"]
    _require(
        Path(str(blind_freeze.get("sourceCampaign") or "")).resolve()
        == strict["campaign"],
        "blind source campaign is not the supplied strict campaign",
    )
    expected_bindings = {
        "sourceFreezeSha256": strict["freezeSha256"],
        "sourceFreezeFileSha256": sha256_file(strict["freezePath"]),
        "sourceQuestionsSha256": strict_freeze.get("questionsSha256"),
        "sourceOverlapManifestSha256": strict_freeze.get("overlapManifestSha256"),
        "sourceCandidateAnswersSha256": strict_freeze.get("candidateAnswersSha256"),
        "expectedCertificateIdsSha256": strict_freeze.get("eligibleIdsSha256"),
    }
    for key, expected in expected_bindings.items():
        _require(blind_freeze.get(key) == expected, f"cross-campaign {key} mismatch")
    _require(blind["expectedIds"] == strict["eligibleIds"], "cross-campaign eligible IDs")
    _require(
        [row.get("id") for row in blind["questions"]] == strict["expectedIds"],
        "cross-campaign question IDs",
    )
    strict_question_by_id = {row["id"]: row for row in strict["questions"]}
    for row in blind["questions"]:
        source = strict_question_by_id[row["id"]]
        expected = {
            "id": source["id"],
            "responseFormat": source["responseFormat"],
            "language": str(source.get("language") or ""),
            "prompt": source["prompt"],
        }
        _require(row == expected, f"cross-campaign public question mismatch: {row.get('id')}")
    pair_by_id = {row["id"]: row for row in blind["pairs"]}
    mapping_by_id = {row["id"]: row for row in blind["mapping"]}
    for case_id in strict["eligibleIds"]:
        pair = pair_by_id[case_id]
        mapping = mapping_by_id[case_id]
        expected_left = (
            strict["candidates"]["base"][case_id]
            if mapping["leftRole"] == "INCUMBENT"
            else strict["candidates"]["auxiliary_1"][case_id]
        )
        expected_right = (
            strict["candidates"]["base"][case_id]
            if mapping["rightRole"] == "INCUMBENT"
            else strict["candidates"]["auxiliary_1"][case_id]
        )
        _require(
            {mapping["leftRole"], mapping["rightRole"]} == {"INCUMBENT", "PROPOSED"}
            and pair["leftAnswer"] == expected_left
            and pair["rightAnswer"] == expected_right,
            f"cross-campaign role mapping mismatch: {case_id}",
        )


def _blind_proposed_ids(blind: dict[str, Any]) -> list[str]:
    proposed: list[str] = []
    for mapping, certificate in zip(blind["mapping"], blind["certificates"]):
        preference = certificate.get("preference")
        prefers_proposed = (
            preference == "PREFER_LEFT" and mapping.get("leftRole") == "PROPOSED"
        ) or (
            preference == "PREFER_RIGHT" and mapping.get("rightRole") == "PROPOSED"
        )
        if prefers_proposed:
            proposed.append(str(certificate["id"]))
    return proposed


def _policy_definition(name: str) -> str:
    return {
        "base": "always_exact_frozen_base",
        "blind_only": "blind_hidden_role_preference_is_proposed",
        "intersection": "strict_valid_switch_and_blind_hidden_role_preference_is_proposed",
        "union": "strict_valid_switch_or_blind_hidden_role_preference_is_proposed",
    }[name]


def _publish(
    output_dir: Path,
    *,
    strict: dict[str, Any],
    blind: dict[str, Any],
    policy_switches: dict[str, list[str]],
) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    _require(not output_dir.exists(), f"refusing to overwrite output: {output_dir}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}.combining-", dir=output_dir.parent)
    )
    try:
        policy_receipts: dict[str, Any] = {}
        expected_ids = strict["expectedIds"]
        base = strict["candidates"]["base"]
        proposed = strict["candidates"]["auxiliary_1"]
        for name in POLICIES:
            switch_ids = policy_switches[name]
            switch_set = set(switch_ids)
            answers_path = temporary / "policies" / name / "answers.jsonl"
            switch_path = temporary / "policies" / name / "switch_ids.json"
            rows = [
                {
                    "id": case_id,
                    "finalAnswer": proposed[case_id] if case_id in switch_set else base[case_id],
                }
                for case_id in expected_ids
            ]
            _write_jsonl(answers_path, rows)
            _write_json(switch_path, {"count": len(switch_ids), "ids": switch_ids})
            observed = _read_answers(answers_path, expected_ids, label=f"published {name}")
            for case_id in expected_ids:
                expected = proposed[case_id] if case_id in switch_set else base[case_id]
                _require(observed[case_id] == expected, f"published {name} synthesis detected")
            policy_receipts[name] = {
                "definition": _policy_definition(name),
                "switchRows": len(switch_ids),
                "switchIds": switch_ids,
                "switchIdsSha256": canonical_digest(switch_ids),
                "switchIdsPath": f"policies/{name}/switch_ids.json",
                "switchIdsFileSha256": sha256_file(switch_path),
                "answersPath": f"policies/{name}/answers.jsonl",
                "answersSha256": sha256_file(answers_path),
            }

        implementation_path = Path(__file__).resolve()
        receipt: dict[str, Any] = {
            "schemaVersion": 1,
            "status": "accepted",
            "protocol": PROTOCOL,
            "goldAccess": False,
            "synthesis": False,
            "expectedRows": len(strict["expectedIds"]),
            "eligibleRows": len(strict["eligibleIds"]),
            "sourceBindings": {
                "expectedIdsSha256": strict["freeze"].get("expectedIdsSha256"),
                "eligibleIdsSha256": strict["freeze"].get("eligibleIdsSha256"),
                "questionsSha256": strict["freeze"].get("questionsSha256"),
                "overlapManifestSha256": strict["freeze"].get("overlapManifestSha256"),
                "candidateAnswersSha256": strict["freeze"].get("candidateAnswersSha256"),
                "candidateBundleSha256": strict["freeze"].get("candidateBundleSha256"),
                "candidateProvenanceSha256": strict["freeze"].get("candidateProvenanceSha256"),
                "blindRoleMappingSha256": blind["freeze"].get("roleMappingSha256"),
                "blindRotationControlSha256": blind["freeze"].get("rotationControlSha256"),
                "blindPairsSha256": blind["freeze"].get("pairsSha256"),
            },
            "upstream": {
                "strict": {
                    "campaign": str(strict["campaign"]),
                    "freezeSha256": strict["freezeSha256"],
                    "freezeFileSha256": sha256_file(strict["freezePath"]),
                    "receiptSha256": strict["receiptSha256"],
                    "receiptFileSha256": sha256_file(strict["receiptPath"]),
                    "validationReportSha256": sha256_file(strict["reportPath"]),
                    "rawTraceSha256": sha256_file(strict["tracePath"]),
                    "threadIds": strict["threadIds"],
                    "answersSha256": strict["report"].get("answersSha256"),
                    "decisionsSha256": strict["report"].get("decisionsSha256"),
                    "switchIdsSha256": canonical_digest(strict["strictSwitchIds"]),
                    "candidateProvenance": strict["candidateProvenance"],
                },
                "blind": {
                    "campaign": str(blind["campaign"]),
                    "freezeSha256": blind["freezeSha256"],
                    "freezeFileSha256": sha256_file(blind["freezePath"]),
                    "receiptSha256": blind["receiptSha256"],
                    "receiptFileSha256": sha256_file(blind["receiptPath"]),
                    "validationReportSha256": sha256_file(blind["reportPath"]),
                    "rawTraceSha256": sha256_file(blind["tracePath"]),
                    "threadIds": blind["threadIds"],
                    "certificatesSha256": blind["report"].get("certificatesSha256"),
                    "roleMappingSha256": blind["report"].get("roleMappingSha256"),
                },
            },
            "implementationHashes": {
                str(implementation_path): sha256_file(implementation_path)
            },
            "policies": policy_receipts,
        }
        receipt["receiptSha256"] = canonical_digest(receipt)
        receipt_path = temporary / "combination_receipt.json"
        _write_json(receipt_path, receipt)
        _require(
            _verify_self_hash(_load_json(receipt_path), "receiptSha256", "combination receipt")
            == receipt["receiptSha256"],
            "combination receipt verification failed",
        )
        os.replace(temporary, output_dir)
        return receipt
    except BaseException:
        if temporary.exists() and temporary.parent == output_dir.parent and temporary.name.startswith(
            f".{output_dir.name}.combining-"
        ):
            shutil.rmtree(temporary)
        raise


def combine_campaigns(
    *,
    strict_campaign: Path,
    blind_campaign: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """Validate both upstreams and atomically publish all four policies."""

    strict = _verify_strict_campaign(strict_campaign)
    blind = _verify_blind_campaign(blind_campaign)
    _verify_cross_campaign(strict, blind)

    strict_switch = set(strict["strictSwitchIds"])
    blind_proposed_ids = _blind_proposed_ids(blind)
    blind_proposed = set(blind_proposed_ids)
    eligible_order = strict["eligibleIds"]
    policy_switches = {
        "base": [],
        "blind_only": [case_id for case_id in eligible_order if case_id in blind_proposed],
        "intersection": [
            case_id
            for case_id in eligible_order
            if case_id in strict_switch and case_id in blind_proposed
        ],
        "union": [
            case_id
            for case_id in eligible_order
            if case_id in strict_switch or case_id in blind_proposed
        ],
    }
    return _publish(
        output_dir,
        strict=strict,
        blind=blind,
        policy_switches=policy_switches,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict-campaign", type=Path, required=True)
    parser.add_argument("--blind-campaign", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        receipt = combine_campaigns(
            strict_campaign=args.strict_campaign,
            blind_campaign=args.blind_campaign,
            output_dir=args.output_dir,
        )
    except (CombinationValidationError, FileNotFoundError, OSError, ValueError) as exc:
        print(json.dumps({"status": "rejected", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
