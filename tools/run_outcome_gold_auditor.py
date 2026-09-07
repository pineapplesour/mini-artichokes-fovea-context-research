#!/usr/bin/env python3
"""Run exactly one frozen, isolated outcome-gold auditor shard."""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import outcome_gold_audit as audit
from tools import run_blind_pairwise_veto_agent as trusted
from tools import run_plain_codex_file_agent as plain_runner


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def execution_config(
    freeze: dict[str, Any],
    *,
    codex_home: Path,
    model: str,
    reasoning_effort: str,
    verbosity: str,
    service_tier: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    expected = freeze.get("executionConfig")
    if not isinstance(expected, dict):
        raise audit.GoldAuditError("shard executionConfig is missing")
    observed = {
        "model": model,
        "reasoningEffort": reasoning_effort,
        "verbosity": verbosity,
        "serviceTier": service_tier,
        "codexVersion": audit.REQUIRED_CODEX_VERSION,
        "codexHome": str(codex_home.resolve()),
        "timeoutSeconds": timeout_seconds,
        "nativeWebSearch": False,
        "localCode": False,
        "shellTool": False,
        "database": False,
        "mcp": False,
        "apps": False,
        "skills": False,
        "multiAgent": False,
        "ephemeral": True,
        "strictConfig": True,
        "disabledFeatures": sorted(audit.TOOL_FREE_DISABLED_FEATURES),
        "disabledFeaturesSha256": audit.canonical_digest(
            sorted(audit.TOOL_FREE_DISABLED_FEATURES)
        ),
        "attemptPolicy": dict(audit.ATTEMPT_POLICY),
        "attemptEvidenceLimitation": audit.ATTEMPT_EVIDENCE_LIMITATION,
    }
    if observed != expected:
        raise audit.GoldAuditError(
            f"runtime execution config does not match frozen profile: {observed!r} != {expected!r}"
        )
    if reasoning_effort != "high" or verbosity != "low" or service_tier != "default":
        raise audit.GoldAuditError("gold audit requires high/low/default execution settings")
    return observed


def build_command(
    *,
    input_dir: Path,
    output_dir: Path,
    codex_home: Path,
    model: str,
    reasoning_effort: str,
    verbosity: str,
) -> list[str]:
    command = audit.tool_free_codex_command(
        input_dir=input_dir,
        output_dir=output_dir,
        codex_home=codex_home,
        model=model,
        reasoning_effort=reasoning_effort,
        verbosity=verbosity,
    )
    audit.verify_tool_free_command(command)
    return command


def input_hashes(paths: dict[str, Path]) -> dict[str, str]:
    return {
        "auditPacketSha256": audit.sha256_file(paths["packet"]),
        "expectedIdsFileSha256": audit.sha256_file(paths["expectedIds"]),
        "instructionsSha256": audit.sha256_file(paths["instructions"]),
        "stdinPromptSha256": audit.sha256_file(paths["stdinPrompt"]),
        "outputSchemaSha256": audit.sha256_file(paths["outputSchema"]),
    }


def validate_output(
    paths: dict[str, Path],
    packet_rows: list[dict[str, Any]],
    *,
    write_derived: bool,
) -> dict[str, Any]:
    errors: list[str] = []
    try:
        response = audit.load_json(paths["modelResponse"])
        if set(response) != audit.OUTPUT_OBJECT_KEYS:
            raise audit.GoldAuditError("model response must have the sole key judgments")
        raw_rows = response.get("judgments")
        if not isinstance(raw_rows, list) or any(not isinstance(row, dict) for row in raw_rows):
            raise audit.GoldAuditError("model response judgments must be an array of objects")
        rows = [dict(row) for row in raw_rows]
        report = audit.validate_judgment_rows(packet_rows=packet_rows, judgment_rows=rows)
    except Exception as error:
        response = None
        rows = []
        report = {
            "passed": False,
            "errors": [f"output_load_exception:{type(error).__name__}:{error}"],
            "expectedRows": len(packet_rows),
            "observedRows": 0,
        }
    if not report.get("passed"):
        errors.append("strict_judgment_validation_rejected")
    derived_payload = audit.serialize_jsonl(rows) if report.get("passed") else None
    if derived_payload is not None:
        if paths["judgments"].exists():
            if paths["judgments"].is_symlink() or not paths["judgments"].is_file():
                errors.append("derived_judgments_not_regular_file")
            elif paths["judgments"].read_bytes() != derived_payload:
                errors.append("derived_judgments_disagree_with_model_response")
        elif write_derived:
            audit.write_bytes_exclusive(paths["judgments"], derived_payload)
        else:
            errors.append("derived_judgments_missing")
    output_names = sorted(path.name for path in paths["outputDir"].iterdir())
    unexpected = sorted(set(output_names) - {"judgments.jsonl", "model_response.json"})
    if unexpected:
        errors.append("unexpected_model_output_files")
    judgments_sha = audit.sha256_file(paths["judgments"]) if paths["judgments"].is_file() else None
    response_sha = (
        audit.sha256_file(paths["modelResponse"])
        if paths["modelResponse"].is_file() and not paths["modelResponse"].is_symlink()
        else None
    )
    if not judgments_sha:
        errors.append("judgments_file_missing")
    if not response_sha:
        errors.append("model_response_missing")
    return {
        "passed": not errors,
        "errors": errors,
        "judgmentsSha256": judgments_sha,
        "modelResponseSha256": response_sha,
        "modelResponseCanonicalSha256": (
            audit.canonical_digest(response) if isinstance(response, dict) else None
        ),
        "outputFileNames": output_names,
        "unexpectedOutputFileNames": unexpected,
        "strictValidation": report,
        "rows": len(rows),
    }


def assert_fresh(paths: dict[str, Path]) -> None:
    if any(paths["outputDir"].iterdir()):
        raise audit.GoldAuditError(
            f"refusing to overwrite non-empty auditor output: {paths['outputDir']}"
        )
    stale = [
        path
        for path in (
            paths["trace"],
            paths["stderr"],
            paths["attemptRegistry"],
            paths["receipt"],
            paths["validation"],
        )
        if path.exists()
    ]
    if stale:
        raise audit.GoldAuditError(
            "refusing to overwrite prior auditor artifacts: "
            + ", ".join(str(path) for path in stale)
        )


def _trace_token_usage(policy_audit: MappingLike) -> dict[str, Any]:
    underlying: Any = policy_audit
    trace = None
    for _ in range(4):
        if not isinstance(underlying, dict):
            break
        if isinstance(underlying.get("trace"), dict):
            trace = underlying["trace"]
            break
        underlying = underlying.get("underlyingAudit")
    usage = trace.get("tokenUsage") if isinstance(trace, dict) else None
    return dict(usage) if isinstance(usage, dict) else {}


MappingLike = dict[str, Any]


_TRACE_KEY_DENY_FRAGMENTS = (
    "command",
    "tool",
    "function",
    "file_change",
    "apply_patch",
    "shell",
    "mcp",
    "web_search",
    "computer",
    "skill",
    "network",
)
EXPECTED_CODE_MODE_DISABLED_DIAGNOSTIC = (
    "Code Mode is unavailable because code-mode host is disabled. Code mode will "
    "fail closed; enable `features.code_mode_host` and install "
    "`codex-code-mode-host`."
)
EXPECTED_TURN_USAGE_KEYS = {
    "input_tokens",
    "cached_input_tokens",
    "cache_write_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
}


def _forbidden_trace_paths(value: Any, *, path: str = "$") -> list[str]:
    """Find tool-like structures even when nested inside an allowed event."""

    violations: list[str] = []
    if isinstance(value, dict):
        for raw_key, child in value.items():
            key = str(raw_key)
            normalized = key.casefold().replace("-", "_")
            child_path = f"{path}.{key}"
            if any(fragment in normalized for fragment in _TRACE_KEY_DENY_FRAGMENTS):
                violations.append(child_path)
            if (
                normalized in {"type", "kind", "name"}
                and isinstance(child, str)
                and any(
                    fragment in child.casefold().replace("-", "_")
                    for fragment in _TRACE_KEY_DENY_FRAGMENTS
                )
            ):
                violations.append(child_path)
            violations.extend(_forbidden_trace_paths(child, path=child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            violations.extend(_forbidden_trace_paths(child, path=f"{path}[{index}]"))
    return violations


def audit_tool_free_trace(
    *,
    trace_path: Path,
    questions_path: Path,
    model_response_path: Path,
    return_code: int,
) -> dict[str, Any]:
    """Reject every raw model-visible tool event, including incomplete ones."""

    base = trusted.audit_veto_trace(
        trace_path=trace_path,
        questions_path=questions_path,
        return_code=return_code,
        native_web_search=False,
    )
    violations = list(base.get("violations") or [])
    tool_events: list[dict[str, str]] = []
    unknown_events: list[dict[str, str]] = []
    hidden_tool_paths: list[str] = []
    agent_messages: list[str] = []
    containment_diagnostics: list[dict[str, Any]] = []
    containment_diagnostic_indices: list[int] = []
    event_sequence: list[str] = []
    thread_ids: list[str] = []
    allowed_event_types = {
        "thread.started",
        "turn.started",
        "turn.completed",
        "item.started",
        "item.updated",
        "item.completed",
    }
    allowed_item_types = {"reasoning", "agent_message", "error"}
    try:
        raw_lines = trace_path.read_text(encoding="utf-8").split("\n")
    except (OSError, UnicodeDecodeError) as error:
        return {
            "policy": "mini_artichokes_tool_free_gold_auditor_v2",
            "passed": False,
            "violations": [f"trace_read_failed:{type(error).__name__}"],
            "rawToolEventCount": 0,
            "rawToolEvents": [],
            "underlyingAudit": base,
        }
    for line_number, raw in enumerate(raw_lines, 1):
        if not raw.strip():
            continue
        try:
            event = audit.parse_json_strict(raw, location=f"{trace_path}:{line_number}")
        except audit.GoldAuditError:
            violations.append("raw_trace_invalid_jsonl")
            continue
        if not isinstance(event, dict):
            violations.append("raw_trace_non_object_event")
            continue
        event_type = str(event.get("type") or "").casefold()
        event_sequence.append(event_type)
        hidden_tool_paths.extend(
            f"line:{line_number}:{path}"
            for path in _forbidden_trace_paths(event)
        )
        item = event.get("item")
        item_type = str(item.get("type") or "").casefold() if isinstance(item, dict) else ""
        item_event = event_type in {"item.started", "item.updated", "item.completed"}
        if event_type == "thread.started":
            if set(event) != {"type", "thread_id"}:
                violations.append("thread_started_exact_schema_required")
        elif event_type == "turn.started":
            if set(event) != {"type"}:
                violations.append("turn_started_exact_schema_required")
        elif event_type == "turn.completed":
            usage = event.get("usage")
            if (
                set(event) != {"type", "usage"}
                or not isinstance(usage, dict)
                or set(usage) != EXPECTED_TURN_USAGE_KEYS
                or any(
                    not isinstance(value, int) or isinstance(value, bool) or value < 0
                    for value in usage.values()
                )
                or usage.get("input_tokens", 0) + usage.get("output_tokens", 0) <= 0
            ):
                violations.append("turn_completed_exact_usage_schema_required")
        elif item_event:
            if set(event) != {"type", "item"} or not isinstance(item, dict):
                violations.append("item_event_exact_schema_required")
            elif item_type in {"reasoning", "agent_message"} and (
                set(item) != {"id", "type", "text"}
                or not isinstance(item.get("id"), str)
                or not item["id"]
                or not isinstance(item.get("text"), str)
            ):
                violations.append("message_item_exact_schema_required")
        tool_signal = item_event and item_type not in allowed_item_types
        tool_signal = tool_signal or any(
            token in event_type
            for token in (
                "command",
                "shell",
                "web",
                "mcp",
                "skill",
                "tool",
                "function",
                "file_change",
                "apply_patch",
                "todo",
                "computer",
            )
        )
        if tool_signal:
            tool_events.append(
                {"line": str(line_number), "eventType": event_type, "itemType": item_type}
            )
        if event_type not in allowed_event_types:
            unknown_events.append(
                {"line": str(line_number), "eventType": event_type, "itemType": item_type}
            )
        if event_type == "thread.started":
            thread_id = event.get("thread_id")
            if isinstance(thread_id, str) and thread_id:
                thread_ids.append(thread_id)
            else:
                violations.append("thread_started_requires_nonempty_thread_id")
        if item_type == "error":
            diagnostic_valid = bool(
                event_type == "item.completed"
                and isinstance(item, dict)
                and set(item) == {"id", "type", "message"}
                and isinstance(item.get("id"), str)
                and bool(item["id"])
                and item.get("message") == EXPECTED_CODE_MODE_DISABLED_DIAGNOSTIC
            )
            if diagnostic_valid:
                containment_diagnostics.append(dict(item))
                containment_diagnostic_indices.append(len(event_sequence) - 1)
            else:
                violations.append("unexpected_error_item_forbidden")
        if (
            event_type == "item.completed"
            and isinstance(item, dict)
            and item_type == "agent_message"
            and isinstance(item.get("text"), str)
        ):
            agent_messages.append(item["text"])
    if tool_events:
        violations.append("model_visible_tool_event_forbidden")
    if hidden_tool_paths:
        violations.append("nested_or_obfuscated_tool_structure_forbidden")
    if unknown_events:
        violations.append("unknown_raw_trace_event_forbidden")
    if event_sequence.count("thread.started") != 1 or len(thread_ids) != 1:
        violations.append("exactly_one_thread_started_required")
    if event_sequence.count("turn.started") != 1:
        violations.append("exactly_one_turn_started_required")
    if event_sequence.count("turn.completed") != 1:
        violations.append("exactly_one_turn_completed_required")
    if len(containment_diagnostics) != 1:
        violations.append("exactly_one_code_mode_fail_closed_diagnostic_required")
    if event_sequence:
        try:
            turn_started_index = event_sequence.index("turn.started")
            lifecycle_valid = (
                event_sequence[0] == "thread.started"
                and turn_started_index > 0
                and containment_diagnostic_indices == [1]
                and event_sequence[-1] == "turn.completed"
                and turn_started_index < event_sequence.index("turn.completed")
            )
        except (IndexError, ValueError):
            lifecycle_valid = False
        if not lifecycle_valid:
            violations.append("single_turn_lifecycle_order_invalid")
    if len(agent_messages) != 1:
        violations.append("exactly_one_completed_agent_message_required")
    response_canonical = None
    trace_message_canonical = None
    try:
        response = audit.load_json(model_response_path)
        response_canonical = audit.canonical_digest(response)
        if len(agent_messages) == 1:
            trace_response = audit.parse_json_strict(
                agent_messages[0], location="completed_agent_message"
            )
            if not isinstance(trace_response, dict):
                raise audit.GoldAuditError("completed agent message is not a JSON object")
            trace_message_canonical = audit.canonical_digest(trace_response)
            if trace_response != response:
                violations.append("trace_agent_message_model_response_mismatch")
    except Exception as error:
        violations.append(f"trace_response_binding_failed:{type(error).__name__}")
    return {
        "policy": "mini_artichokes_tool_free_gold_auditor_v2",
        "passed": not violations,
        "violations": list(dict.fromkeys(violations)),
        "rawToolEventCount": len(tool_events),
        "rawToolEvents": tool_events,
        "unknownRawEventCount": len(unknown_events),
        "unknownRawEvents": unknown_events,
        "hiddenToolStructureCount": len(hidden_tool_paths),
        "hiddenToolStructurePaths": hidden_tool_paths,
        "threadStartedCount": event_sequence.count("thread.started"),
        "turnStartedCount": event_sequence.count("turn.started"),
        "turnCompletedCount": event_sequence.count("turn.completed"),
        "codeModeFailClosedDiagnosticCount": len(containment_diagnostics),
        "codeModeFailClosedDiagnostics": containment_diagnostics,
        "completedAgentMessageCount": len(agent_messages),
        "modelResponseCanonicalSha256": response_canonical,
        "traceAgentMessageCanonicalSha256": trace_message_canonical,
        "threadIds": thread_ids,
        "underlyingAudit": base,
    }


def _git_bytes(arguments: list[str]) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(REPO_ROOT), *arguments],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise audit.GoldAuditError(
            f"Git anchor verification failed: {' '.join(arguments)}: "
            + completed.stderr.decode("utf-8", errors="replace")[-500:]
        )
    return completed.stdout


def verify_git_anchor(
    *,
    campaign_dir: Path,
    profile: str,
    shard_index: int,
    freeze: dict[str, Any],
    commit: str,
) -> dict[str, Any]:
    if not isinstance(commit, str) or not commit.strip():
        raise audit.GoldAuditError("a pre-call Git anchor commit is required")
    anchor, anchor_path = audit.verify_anchor_binds_shard(
        campaign_dir=campaign_dir,
        profile=profile,
        shard_index=shard_index,
        freeze=freeze,
    )
    try:
        relative_anchor = anchor_path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError as error:
        raise audit.GoldAuditError("pre-call anchor must be committed inside the repository") from error
    resolved_commit = (
        _git_bytes(["rev-parse", "--verify", f"{commit}^{{commit}}"])
        .decode("ascii")
        .strip()
    )
    committed_anchor = _git_bytes(["show", f"{resolved_commit}:{relative_anchor}"])
    live_anchor = anchor_path.read_bytes()
    if committed_anchor != live_anchor:
        raise audit.GoldAuditError("supplied commit does not contain the exact live pre-call anchor")
    for raw_path, expected_hash in freeze["implementationHashes"].items():
        path = Path(raw_path).resolve()
        try:
            relative = path.relative_to(REPO_ROOT.resolve()).as_posix()
        except ValueError as error:
            raise audit.GoldAuditError(f"frozen implementation lies outside repository: {path}") from error
        if audit.sha256_bytes(_git_bytes(["show", f"{resolved_commit}:{relative}"])) != expected_hash:
            raise audit.GoldAuditError(
                f"anchor commit does not contain the frozen implementation bytes: {relative}"
            )
    return {
        "commit": resolved_commit,
        "anchorPath": relative_anchor,
        "anchorFileSha256": audit.sha256_bytes(live_anchor),
        "anchorSha256": anchor["anchorSha256"],
        "implementationFilesVerified": len(freeze["implementationHashes"]),
    }


def write_attempt_start(
    *, paths: dict[str, Path], freeze: dict[str, Any], git_anchor: dict[str, Any]
) -> dict[str, Any]:
    event = {
        "schemaVersion": 1,
        "event": "semantic_attempt_started",
        "attemptOrdinal": 1,
        "semanticModelInvocationsBefore": 0,
        "firstAttemptOnly": True,
        "freezeSha256": freeze["freezeSha256"],
        "preCallGitAnchor": git_anchor,
        "startedUtc": utc_now(),
    }
    audit.write_jsonl_exclusive(paths["attemptRegistry"], [event])
    return event


def append_attempt_finish(
    *,
    paths: dict[str, Path],
    freeze: dict[str, Any],
    status: str,
    trace_sha256: str,
    model_response_sha256: str | None,
) -> dict[str, Any]:
    event = {
        "schemaVersion": 1,
        "event": "semantic_attempt_finished",
        "attemptOrdinal": 1,
        "semanticModelInvocationsTotal": 1,
        "freezeSha256": freeze["freezeSha256"],
        "status": status,
        "traceSha256": trace_sha256,
        "modelResponseSha256": model_response_sha256,
        "finishedUtc": utc_now(),
    }
    payload = audit.serialize_jsonl([event])
    with paths["attemptRegistry"].open("ab") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    return event


def verify_resume(
    *,
    paths: dict[str, Path],
    freeze: dict[str, Any],
    packet_rows: list[dict[str, Any]],
    config: dict[str, Any],
    command: list[str],
    cli_identity: dict[str, Any],
    git_anchor: dict[str, Any],
) -> dict[str, Any]:
    if not paths["receipt"].is_file():
        raise audit.GoldAuditError(
            "--resume requires an existing accepted receipt; fresh execution is refused"
        )
    receipt = audit.load_json(paths["receipt"])
    audit.verify_self_hash(receipt, key="receiptSha256", location=str(paths["receipt"]))
    failures: list[str] = []
    if receipt.get("status") != "accepted":
        failures.append("receipt_not_accepted")
    if receipt.get("semanticModelInvocations") != 1:
        failures.append("receipt_invocation_count_mismatch")
    if receipt.get("freezeSha256") != freeze.get("freezeSha256"):
        failures.append("receipt_freeze_mismatch")
    if receipt.get("executionConfig") != config:
        failures.append("receipt_execution_config_mismatch")
    if receipt.get("inputFileSha256") != input_hashes(paths):
        failures.append("receipt_input_hash_mismatch")
    if receipt.get("implementationHashes") != freeze.get("implementationHashes"):
        failures.append("receipt_implementation_hash_mismatch")
    if receipt.get("codexCli") != cli_identity:
        failures.append("receipt_codex_cli_or_command_mismatch")
    if cli_identity.get("commandSha256") != audit.canonical_digest(command):
        failures.append("current_command_hash_mismatch")
    if receipt.get("preCallGitAnchor") != git_anchor:
        failures.append("receipt_pre_call_git_anchor_mismatch")
    process = receipt.get("process")
    if not isinstance(process, dict) or process.get("exitCode") != 0 or process.get("timedOut") is not False:
        failures.append("receipt_process_not_accepted")
    artifacts = receipt.get("artifacts")
    if not isinstance(artifacts, dict):
        failures.append("receipt_artifacts_missing")
        artifacts = {}
    for key, path in (
        ("judgmentsSha256", paths["judgments"]),
        ("rawTraceSha256", paths["trace"]),
        ("stderrSha256", paths["stderr"]),
        ("modelResponseSha256", paths["modelResponse"]),
        ("attemptRegistrySha256", paths["attemptRegistry"]),
        ("validationSha256", paths["validation"]),
    ):
        if not path.is_file() or artifacts.get(key) != audit.sha256_file(path):
            failures.append(f"resume_artifact_mismatch:{key}")
    validation = validate_output(paths, packet_rows, write_derived=False)
    if not validation["passed"]:
        failures.append("resume_judgment_revalidation_failed")
    if paths["trace"].is_file():
        policy = audit_tool_free_trace(
            trace_path=paths["trace"],
            questions_path=paths["packet"],
            model_response_path=paths["modelResponse"],
            return_code=0,
        )
        if not policy.get("passed"):
            failures.append("resume_trace_policy_failed")
        if artifacts.get("threadIds") != policy.get("threadIds"):
            failures.append("resume_thread_ids_mismatch")
    try:
        attempts = audit.load_jsonl(paths["attemptRegistry"])
        if (
            len(attempts) != 2
            or attempts[0].get("event") != "semantic_attempt_started"
            or attempts[1].get("event") != "semantic_attempt_finished"
            or attempts[0].get("preCallGitAnchor") != git_anchor
            or attempts[1].get("semanticModelInvocationsTotal") != 1
        ):
            failures.append("resume_attempt_registry_invalid")
    except Exception:
        failures.append("resume_attempt_registry_unreadable")
    if failures:
        raise audit.GoldAuditError(
            "resume validation failed closed: " + ", ".join(dict.fromkeys(failures))
        )
    return {
        "status": "resumed_complete_without_model_call",
        "semanticModelInvocations": 0,
        "profile": freeze["profile"],
        "shardIndex": freeze["shardIndex"],
        "freezeSha256": freeze["freezeSha256"],
        "receiptSha256": receipt["receiptSha256"],
        "judgmentsSha256": artifacts["judgmentsSha256"],
    }


def run_shard(
    *,
    campaign_dir: Path,
    profile: str,
    shard_index: int,
    codex_home: Path,
    model: str,
    reasoning_effort: str,
    verbosity: str,
    service_tier: str,
    timeout_seconds: int,
    pre_call_anchor_commit: str,
    resume: bool,
) -> dict[str, Any]:
    freeze, paths, packet_rows, _ = audit.verify_shard_bundle(
        campaign_dir, profile, shard_index
    )
    config = execution_config(
        freeze,
        codex_home=codex_home,
        model=model,
        reasoning_effort=reasoning_effort,
        verbosity=verbosity,
        service_tier=service_tier,
        timeout_seconds=timeout_seconds,
    )
    command = build_command(
        input_dir=paths["inputDir"],
        output_dir=paths["outputDir"],
        codex_home=codex_home.resolve(),
        model=model,
        reasoning_effort=reasoning_effort,
        verbosity=verbosity,
    )
    cli = audit.cli_identity_for_command(audit.tool_free_cli_base_identity(), command)
    audit.verify_cli_binary_identity(cli)
    if cli != freeze.get("codexCli"):
        raise audit.GoldAuditError("runtime Codex CLI/command differs from the frozen shard")
    git_anchor = verify_git_anchor(
        campaign_dir=campaign_dir,
        profile=profile,
        shard_index=shard_index,
        freeze=freeze,
        commit=pre_call_anchor_commit,
    )
    if resume:
        return verify_resume(
            paths=paths,
            freeze=freeze,
            packet_rows=packet_rows,
            config=config,
            command=command,
            cli_identity=cli,
            git_anchor=git_anchor,
        )
    if timeout_seconds <= 0:
        raise audit.GoldAuditError("timeout must be positive")
    assert_fresh(paths)
    probe = plain_runner.isolation_probe(
        input_dir=paths["inputDir"],
        output_dir=paths["outputDir"],
        codex_home=codex_home.resolve(),
    )
    if not probe.get("passed"):
        raise audit.GoldAuditError(f"auditor isolation probe failed: {probe}")
    prompt = paths["stdinPrompt"].read_text(encoding="utf-8")
    attempt_start = write_attempt_start(paths=paths, freeze=freeze, git_anchor=git_anchor)
    started_utc = utc_now()
    started = time.monotonic()
    timed_out = False
    with paths["trace"].open("x", encoding="utf-8") as trace_stream, paths[
        "stderr"
    ].open("x", encoding="utf-8") as stderr_stream:
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=trace_stream,
            stderr=stderr_stream,
            text=True,
            start_new_session=True,
        )
        assert process.stdin is not None
        try:
            process.stdin.write(prompt)
            process.stdin.close()
        except BrokenPipeError:
            pass
        try:
            return_code = process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGTERM)
            try:
                return_code = process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                return_code = process.wait(timeout=10)
    elapsed = time.monotonic() - started
    policy = audit_tool_free_trace(
        trace_path=paths["trace"],
        questions_path=paths["packet"],
        model_response_path=paths["modelResponse"],
        return_code=return_code,
    )
    validation = validate_output(paths, packet_rows, write_derived=True)
    audit.write_json_exclusive(paths["validation"], validation)
    accepted = (
        return_code == 0
        and not timed_out
        and policy.get("passed") is True
        and validation.get("passed") is True
    )
    append_attempt_finish(
        paths=paths,
        freeze=freeze,
        status="accepted" if accepted else "rejected",
        trace_sha256=audit.sha256_file(paths["trace"]),
        model_response_sha256=validation.get("modelResponseSha256"),
    )
    receipt = {
        "schemaVersion": 1,
        "status": "accepted" if accepted else "rejected",
        "protocol": audit.SHARD_PROTOCOL,
        "semanticModelInvocations": 1,
        "profile": freeze["profile"],
        "shardIndex": freeze["shardIndex"],
        "freezeSha256": freeze["freezeSha256"],
        "inputFileSha256": input_hashes(paths),
        "executionConfig": config,
        "implementationHashes": freeze["implementationHashes"],
        "codexCli": cli,
        "preCallGitAnchor": git_anchor,
        "outerContainmentProbe": {
            **probe,
            "authMountedInCliNamespace": True,
            "authUnmountedClaim": False,
            "enumeratedModelToolSurfacesConfiguredDisabled": True,
            "modelToolSchemaAdvertisementIndependentlyAttested": False,
            "zeroToolEventsObservedInAcceptedRawTrace": policy.get("rawToolEventCount")
            == 0,
            "boundary": (
                "frozen strict feature-disable command plus zero-tool raw-trace validation; "
                "provider request-schema advertisement is not independently attested"
            ),
        },
        "attemptStart": attempt_start,
        "runStartedUtc": started_utc,
        "runFinishedUtc": utc_now(),
        "process": {
            "exitCode": return_code,
            "timedOut": timed_out,
            "elapsedSeconds": elapsed,
        },
        "tokenUsage": _trace_token_usage(policy),
        "policyAudit": policy,
        "artifactValidation": validation,
        "artifacts": {
            "rawTraceSha256": audit.sha256_file(paths["trace"]),
            "stderrSha256": audit.sha256_file(paths["stderr"]),
            "judgmentsSha256": validation.get("judgmentsSha256"),
            "modelResponseSha256": validation.get("modelResponseSha256"),
            "validationSha256": audit.sha256_file(paths["validation"]),
            "attemptRegistrySha256": audit.sha256_file(paths["attemptRegistry"]),
            "threadIds": policy.get("threadIds"),
        },
        "acceptedArtifact": "output/model_response.json" if accepted else None,
        "derivedArtifact": "output/judgments.jsonl" if accepted else None,
        "postCallChainInstruction": (
            "Commit this receipt, attempt registry, raw trace hashes, and derived output "
            "without rewriting prior pre-call or post-call commits."
        ),
        "firstAttemptEvidenceLimitation": audit.ATTEMPT_EVIDENCE_LIMITATION,
    }
    receipt["receiptSha256"] = audit.receipt_digest(receipt)
    audit.write_json_exclusive(paths["receipt"], receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run one exact frozen outcome-gold auditor shard."
    )
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--profile", choices=("A", "B", "C"), required=True)
    parser.add_argument("--shard-index", type=int, required=True)
    parser.add_argument("--codex-home", type=Path, default=audit.DEFAULT_CODEX_HOME)
    parser.add_argument("--model", required=True)
    parser.add_argument(
        "--reasoning-effort", default=audit.DEFAULT_REASONING_EFFORT
    )
    parser.add_argument("--verbosity", default=audit.DEFAULT_VERBOSITY)
    parser.add_argument("--service-tier", default=audit.DEFAULT_SERVICE_TIER)
    parser.add_argument(
        "--timeout-seconds", type=int, default=audit.DEFAULT_TIMEOUT_SECONDS
    )
    parser.add_argument("--precall-anchor-commit", required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    result = run_shard(
        campaign_dir=args.campaign_dir,
        profile=args.profile,
        shard_index=args.shard_index,
        codex_home=args.codex_home,
        model=args.model,
        reasoning_effort=args.reasoning_effort,
        verbosity=args.verbosity,
        service_tier=args.service_tier,
        timeout_seconds=args.timeout_seconds,
        pre_call_anchor_commit=args.precall_anchor_commit,
        resume=args.resume,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("status") in {"accepted", "resumed_complete_without_model_call"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
