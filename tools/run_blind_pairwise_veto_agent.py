#!/usr/bin/env python3
"""Run the sealed blind-pairwise-veto certificate agent exactly once.

This runner is intentionally separate from ``run_plain_codex_file_agent.py``.
It reuses that runner's tested Codex/bubblewrap/trace helpers without changing
their implementation, and records their hashes in every receipt.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import benchmark_provider
from tools import run_plain_codex_file_agent as plain_runner
from tools.prepare_blind_pairwise_veto import lf_jsonl_lines


PROTOCOL = "mini_artichokes_blind_pairwise_veto_v2"
VALIDATOR_MODULE = "tools.validate_blind_pairwise_veto"
VALIDATOR_CALLABLE = "validate_blind_pairwise_veto"
DEFAULT_CODEX_HOME = Path("/home/pineapple/.codex-new-account")
DEFAULT_MODEL = "gpt-5.6-luna"
DEFAULT_REASONING_EFFORT = "high"
DEFAULT_VERBOSITY = "low"
SERVICE_TIER = "default"

# Native web is disabled in the Codex command, but the model also has a local
# shell for reading/writing the staged JSONL files. Reject network-capable
# shell commands in the recorded trace so that a run cannot silently turn the
# file-management channel into retrieval.
NETWORK_SHELL_PATTERN = re.compile(
    r"(?ix)"
    r"(?:^|[\s;&|()])"
    r"(?:curl|wget|fetch|aria2c|lynx|links|w3m|nc|ncat|netcat|telnet|ssh|scp|sftp|rsync|"
    r"dig|host|nslookup|ping|openssl\s+s_client|git\s+(?:clone|fetch|pull)|"
    r"pip(?:3)?\s+install|uv\s+(?:add|sync|pip)|npm\s+(?:install|i|view)|npx)\b"
    r"|https?://|ftp://|/dev/(?:tcp|udp)/|urllib\.request|requests\.|httpx\.|"
    r"aiohttp\.|socket\.(?:socket|create_connection)|AF_INET"
)

INPUT_FILES = {
    "questions": "questions.jsonl",
    "candidatePairs": "candidate_pairs.jsonl",
    "expectedCertificateIds": "expected_certificate_ids.json",
    "instructions": "RUN_INSTRUCTIONS.md",
}
FREEZE_INPUT_HASH_KEYS = {
    "questions": "questionsSha256",
    "candidatePairs": "pairsSha256",
    "instructions": "instructionsSha256",
}
REQUIRED_FREEZE_KEYS = {
    "schemaVersion",
    "status",
    "protocol",
    "sourceCampaign",
    "sourceFreezeSha256",
    "sourceFreezeFileSha256",
    "sourceQuestionsSha256",
    "sourceOverlapManifestSha256",
    "sourceCandidateAnswersSha256",
    "questionsPath",
    "questionsSha256",
    "pairsPath",
    "pairsSha256",
    "expectedCertificateIdsPath",
    "expectedCertificateIdsFileSha256",
    "expectedCertificateIdsSha256",
    "instructionsSha256",
    "roleMappingPath",
    "roleMappingSha256",
    "rotationControlPath",
    "rotationControlSha256",
    "rotationScheme",
    "rotationSeedSha256",
    "inventory",
    "executionConfig",
    "implementationHashes",
    "freezeSha256",
}
FROZEN_IMPLEMENTATION_PATHS = (
    REPO_ROOT / "tools/prepare_blind_pairwise_veto.py",
    REPO_ROOT / "tools/validate_blind_pairwise_veto.py",
    REPO_ROOT / "tools/run_blind_pairwise_veto_agent.py",
    REPO_ROOT / "tools/run_ensemble_file_agent.py",
)


def canonical_digest(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, raw in enumerate(lf_jsonl_lines(path), start=1):
        if not raw.strip():
            raise ValueError(f"blank JSONL line {line_number}: {path}")
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError(f"non-object JSONL line {line_number}: {path}")
        rows.append(value)
    return rows


def write_json_exclusive(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def receipt_digest(receipt: dict[str, Any]) -> str:
    return canonical_digest({key: value for key, value in receipt.items() if key != "receiptSha256"})


def campaign_paths(campaign_dir: Path) -> dict[str, Path]:
    role_dir = campaign_dir / "veto"
    input_dir = role_dir / "input"
    output_dir = role_dir / "output"
    paths = {
        "roleDir": role_dir,
        "inputDir": input_dir,
        "outputDir": output_dir,
        "freeze": role_dir / "freeze.json",
        "questions": input_dir / INPUT_FILES["questions"],
        "candidatePairs": input_dir / INPUT_FILES["candidatePairs"],
        "expectedCertificateIds": input_dir / INPUT_FILES["expectedCertificateIds"],
        "instructions": input_dir / INPUT_FILES["instructions"],
        "certificates": output_dir / "certificates.jsonl",
        "lastMessage": output_dir / "last_message.txt",
        "trace": role_dir / "codex_trace.jsonl",
        "stderr": role_dir / "codex_stderr.txt",
        "receipt": role_dir / "run_receipt.json",
        "validationReport": role_dir / "certificate_validation.json",
    }
    if not role_dir.is_dir() or not input_dir.is_dir() or not output_dir.is_dir():
        raise FileNotFoundError(f"prepared blind-veto bundle is incomplete: {role_dir}")
    for key in ("freeze", "questions", "candidatePairs", "expectedCertificateIds", "instructions"):
        if not paths[key].is_file():
            raise FileNotFoundError(paths[key])
    return paths


def expected_certificate_ids(path: Path) -> list[str]:
    value = load_json(path)
    raw_ids = value.get("ids")
    if not isinstance(raw_ids, list) or any(not isinstance(item, str) or not item for item in raw_ids):
        raise ValueError("expected_certificate_ids.json must contain a non-empty string ids list")
    ids = [str(item) for item in raw_ids]
    if len(ids) != len(set(ids)):
        raise ValueError("expected certificate IDs are not unique")
    if value.get("count") != len(ids):
        raise ValueError("expected certificate count does not match ids")
    return ids


def verify_frozen_bundle(campaign_dir: Path) -> tuple[dict[str, Any], dict[str, Path], dict[str, str]]:
    paths = campaign_paths(campaign_dir)
    freeze = load_json(paths["freeze"])
    if freeze.get("protocol") != PROTOCOL:
        raise ValueError(f"unsupported blind-veto protocol: {freeze.get('protocol')!r}")
    missing_freeze_keys = sorted(REQUIRED_FREEZE_KEYS - set(freeze))
    if missing_freeze_keys:
        raise ValueError(f"blind-veto freeze is missing required keys: {missing_freeze_keys}")
    expected_public_paths = {
        "questionsPath": "input/questions.jsonl",
        "pairsPath": "input/candidate_pairs.jsonl",
        "expectedCertificateIdsPath": "input/expected_certificate_ids.json",
    }
    for key, value in expected_public_paths.items():
        if freeze.get(key) != value:
            raise ValueError(f"blind-veto freeze has an unexpected {key}: {freeze.get(key)!r}")
    stored_freeze_digest = str(freeze.get("freezeSha256") or "")
    observed_freeze_digest = canonical_digest(
        {key: value for key, value in freeze.items() if key != "freezeSha256"}
    )
    if not stored_freeze_digest or stored_freeze_digest != observed_freeze_digest:
        raise ValueError("blind-veto freeze self-hash mismatch")

    raw_hashes = {
        logical_name: sha256_file(paths[logical_name])
        for logical_name in ("questions", "candidatePairs", "expectedCertificateIds", "instructions")
    }
    for logical_name, freeze_key in FREEZE_INPUT_HASH_KEYS.items():
        if freeze.get(freeze_key) != raw_hashes[logical_name]:
            raise ValueError(f"frozen input hash mismatch: {freeze_key}")

    ids = expected_certificate_ids(paths["expectedCertificateIds"])
    expected_ids_digest = canonical_digest(ids)
    if freeze.get("expectedCertificateIdsSha256") != expected_ids_digest:
        raise ValueError("frozen expected-certificate ID digest mismatch")
    file_digest = freeze.get("expectedCertificateIdsFileSha256")
    if file_digest != raw_hashes["expectedCertificateIds"]:
        raise ValueError("frozen expected-certificate ID file hash mismatch")

    pairs = load_jsonl(paths["candidatePairs"])
    pair_ids: list[str] = []
    for index, row in enumerate(pairs):
        if set(row) != {"id", "leftAnswer", "rightAnswer"}:
            raise ValueError(f"candidate pair row {index} does not have the exact public schema")
        pair_id = str(row.get("id") or "")
        if not pair_id or not str(row.get("leftAnswer") or "").strip() or not str(row.get("rightAnswer") or "").strip():
            raise ValueError(f"candidate pair row {index} has an empty field")
        pair_ids.append(pair_id)
    if pair_ids != ids:
        raise ValueError("candidate-pair IDs/order do not match expected certificate IDs")

    questions = load_jsonl(paths["questions"])
    question_ids = [str(row.get("id") or "") for row in questions]
    if any(not item for item in question_ids) or len(question_ids) != len(set(question_ids)):
        raise ValueError("question IDs are empty or duplicated")
    if not set(ids).issubset(question_ids):
        raise ValueError("one or more candidate-pair IDs are absent from questions.jsonl")
    inventory = freeze.get("inventory")
    if not isinstance(inventory, dict):
        raise ValueError("freeze inventory is missing")
    if inventory.get("questionRows") != len(questions) or inventory.get("conflictRows") != len(ids):
        raise ValueError("freeze inventory row counts do not match public inputs")
    frozen_implementations = freeze.get("implementationHashes")
    if not isinstance(frozen_implementations, dict) or not frozen_implementations:
        raise ValueError("freeze implementationHashes is missing")
    expected_implementation_keys = {str(path.resolve()) for path in FROZEN_IMPLEMENTATION_PATHS}
    if set(frozen_implementations) != expected_implementation_keys:
        raise ValueError("freeze implementationHashes does not have the exact protocol implementation paths")
    for raw_path, expected_hash in frozen_implementations.items():
        implementation_path = Path(str(raw_path))
        if not implementation_path.is_file() or sha256_file(implementation_path) != expected_hash:
            raise ValueError(f"frozen implementation hash mismatch: {implementation_path}")
    runner_path = str(Path(__file__).resolve())
    if frozen_implementations.get(runner_path) != sha256_file(Path(__file__).resolve()):
        raise ValueError("freeze does not bind this exact blind-veto runner implementation")
    return freeze, paths, raw_hashes


def verify_execution_config(
    freeze: dict[str, Any], *, model: str, reasoning_effort: str, verbosity: str
) -> dict[str, Any]:
    if model != DEFAULT_MODEL:
        raise ValueError(f"blind-veto model is fixed to {DEFAULT_MODEL}")
    if reasoning_effort != DEFAULT_REASONING_EFFORT:
        raise ValueError(f"blind-veto reasoning effort is fixed to {DEFAULT_REASONING_EFFORT}")
    if verbosity != DEFAULT_VERBOSITY:
        raise ValueError(f"blind-veto verbosity is fixed to {DEFAULT_VERBOSITY}")
    expected = freeze.get("executionConfig")
    if not isinstance(expected, dict):
        raise ValueError("freeze executionConfig is missing")
    fixed = {
        "model": model,
        "reasoningEffort": reasoning_effort,
        "verbosity": verbosity,
        "serviceTier": SERVICE_TIER,
        "localCode": True,
        "database": False,
        "skills": False,
        "multiAgent": False,
    }
    for key, value in fixed.items():
        if expected.get(key) != value:
            raise ValueError(f"execution config mismatch for {key}: expected {value!r}, found {expected.get(key)!r}")
    native_web = expected.get("nativeWebSearch")
    if native_web is not False:
        raise ValueError("executionConfig.nativeWebSearch must be frozen false for the tool-free protocol")
    return {**fixed, "nativeWebSearch": native_web}


def strict_validator() -> tuple[ModuleType, Callable[..., dict[str, Any]]]:
    module = importlib.import_module(VALIDATOR_MODULE)
    validator = getattr(module, VALIDATOR_CALLABLE, None)
    if not callable(validator):
        raise RuntimeError(f"strict validator callable missing: {VALIDATOR_MODULE}.{VALIDATOR_CALLABLE}")
    return module, validator


def implementation_hashes(validator_module: ModuleType) -> dict[str, str]:
    required_modules: dict[str, ModuleType] = {
        __name__: sys.modules[__name__],
        plain_runner.__name__: plain_runner,
        benchmark_provider.__name__: benchmark_provider,
        validator_module.__name__: validator_module,
    }
    # The strict validator imports its preparer and shared deterministic option
    # parser. Bind all loaded repository ``tools.*`` implementations, including
    # those transitive imports, rather than silently trusting the import graph.
    for name, module in tuple(sys.modules.items()):
        if name.startswith("tools.") and isinstance(module, ModuleType):
            required_modules[name] = module
    hashes: dict[str, str] = {}
    for name, module in sorted(required_modules.items()):
        raw_path = getattr(module, "__file__", None)
        if not raw_path:
            continue
        path = Path(str(raw_path)).resolve()
        try:
            path.relative_to(REPO_ROOT)
        except ValueError:
            continue
        relative_path = path.relative_to(REPO_ROOT).as_posix()
        hashes[f"{name}|{relative_path}"] = sha256_file(path)
    for required_name in (__name__, plain_runner.__name__, benchmark_provider.__name__, validator_module.__name__):
        if not any(key.startswith(f"{required_name}|") for key in hashes):
            raise RuntimeError(f"unable to hash-bind imported implementation: {required_name}")
    return hashes


def build_codex_command(
    *,
    input_dir: Path,
    output_dir: Path,
    codex_home: Path,
    model: str,
    reasoning_effort: str,
    verbosity: str,
    native_web_search: bool,
) -> list[str]:
    # The stable helper's grader path disables native web while retaining the
    # same one-file Codex execution and isolation contract. The production
    # freeze fixes this flag false; the boolean remains explicit for auditing.
    return plain_runner.codex_command(
        input_dir=input_dir,
        output_dir=output_dir,
        codex_home=codex_home,
        role="solver" if native_web_search else "grader",
        model=model,
        reasoning_effort=reasoning_effort,
        verbosity=verbosity,
        native_web_search=native_web_search,
    )


def verify_tool_free_command(command: list[str]) -> None:
    if "--search" in command:
        raise ValueError("tool-free blind-veto command unexpectedly enables native web")
    if 'web_search="disabled"' not in command:
        raise ValueError("tool-free blind-veto command does not explicitly disable native web")


def binary_identity(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    return {
        "path": str(path),
        "resolvedPath": str(resolved),
        "sha256": sha256_file(resolved),
        "bytes": resolved.stat().st_size,
    }


def codex_cli_identity(command: list[str]) -> dict[str, Any]:
    node_root, codex_js = plain_runner.codex_installation()
    node = node_root / "bin/node"
    completed = subprocess.run(
        [str(node), str(codex_js), "--version"],
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        raise RuntimeError(f"unable to identify Codex CLI: {completed.stderr.strip()[-500:]}")
    launcher_name = shutil.which("codex")
    if not launcher_name:
        raise FileNotFoundError("codex executable not found")
    bwrap_name = command[0] if command else shutil.which("bwrap")
    if not bwrap_name:
        raise FileNotFoundError("bubblewrap executable not found")
    return {
        "version": completed.stdout.strip(),
        "launcher": binary_identity(Path(launcher_name)),
        "node": binary_identity(node),
        "entryPoint": binary_identity(codex_js),
        "bubblewrap": binary_identity(Path(bwrap_name)),
        "commandSha256": canonical_digest(command),
        "commandArgumentCount": len(command),
    }


def parse_thread_starts(trace_path: Path) -> dict[str, Any]:
    ids: list[str] = []
    start_events = 0
    malformed = 0
    if not trace_path.is_file():
        return {"threadStartedEventCount": 0, "threadIds": [], "malformedThreadStartedEvents": 0}
    # Codex JSON strings can legally contain Unicode NEL/U+0085.  Python's
    # splitlines() treats that character as a record boundary even though the
    # CLI JSONL protocol uses LF only, so split on LF explicitly.
    for raw in trace_path.read_text(encoding="utf-8").split("\n"):
        if not raw.strip():
            continue
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict) or event.get("type") != "thread.started":
            continue
        start_events += 1
        candidate = event.get("thread_id") or event.get("threadId")
        if candidate is None and isinstance(event.get("thread"), dict):
            candidate = event["thread"].get("id")
        if not isinstance(candidate, str) or not candidate.strip():
            malformed += 1
            continue
        if candidate not in ids:
            ids.append(candidate)
    return {
        "threadStartedEventCount": start_events,
        "threadIds": ids,
        "malformedThreadStartedEvents": malformed,
    }


def raw_web_search_event_count(trace_path: Path) -> int:
    """Count every native-web trace event, including incomplete attempts."""
    count = 0
    if not trace_path.is_file():
        return count
    for raw in trace_path.read_text(encoding="utf-8").split("\n"):
        if not raw.strip():
            continue
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        item = event.get("item")
        if isinstance(item, dict) and str(item.get("type") or "").casefold() == "web_search":
            count += 1
        elif str(event.get("type") or "").casefold() == "web_search":
            count += 1
    return count


def parsed_web_search_signal(trace: dict[str, Any]) -> bool:
    events = trace.get("webSearchEvents")
    if isinstance(events, (list, tuple, set, dict, str, bytes)) and len(events) > 0:
        return True
    if events not in (None, False, 0, "", [], {}):
        return True
    for key in ("webSearchEventCount", "webSearchCount", "web_search_count"):
        value = trace.get(key)
        if isinstance(value, bool) and value:
            return True
        if isinstance(value, (int, float)) and value > 0:
            return True
        if isinstance(value, str) and value.strip() not in {"", "0"}:
            return True
    return False


def parser_safe_jsonl_text(raw: str) -> tuple[str, dict[str, int]]:
    """Escape JSON-valid Unicode line separators before legacy parsing.

    ``benchmark_provider._parse_codex_jsonl_trace`` uses ``splitlines()``.
    U+0085, U+2028, and U+2029 are valid inside a JSON string but are also
    split by that method, producing false invalid-line counts.  Escaping only
    these JSON-valid characters preserves the decoded event value and leaves
    actual LF record boundaries untouched.  ASCII control characters remain
    unmodified and therefore still fail closed.
    """

    replacements = {
        "\u0085": "\\u0085",
        "\u2028": "\\u2028",
        "\u2029": "\\u2029",
    }
    counts = {f"U+{ord(character):04X}": raw.count(character) for character in replacements}
    normalized = raw
    for character, escaped in replacements.items():
        normalized = normalized.replace(character, escaped)
    return normalized, counts


def plain_trace_audit_jsonl_safe(
    *, trace_path: Path, questions_path: Path, role: str, return_code: int
) -> tuple[dict[str, Any], dict[str, int]]:
    raw = trace_path.read_text(encoding="utf-8")
    normalized, counts = parser_safe_jsonl_text(raw)
    if not any(counts.values()):
        return plain_runner.audit_trace(
            trace_path=trace_path,
            questions_path=questions_path,
            role=role,
            return_code=return_code,
        ), counts
    with tempfile.TemporaryDirectory(prefix="mini-blind-trace-audit-") as temp_dir:
        normalized_path = Path(temp_dir) / "trace.jsonl"
        normalized_path.write_text(normalized, encoding="utf-8")
        audit = plain_runner.audit_trace(
            trace_path=normalized_path,
            questions_path=questions_path,
            role=role,
            return_code=return_code,
        )
    return audit, counts


def network_capable_shell_commands(trace: dict[str, Any]) -> list[str]:
    events = trace.get("commandExecutionEvents")
    if not isinstance(events, list):
        return []
    commands: list[str] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        command = str(event.get("command") or "")
        if command and NETWORK_SHELL_PATTERN.search(command):
            commands.append(command)
    return commands


def audit_veto_trace(
    *, trace_path: Path, questions_path: Path, return_code: int, native_web_search: bool
) -> dict[str, Any]:
    base, separator_counts = plain_trace_audit_jsonl_safe(
        trace_path=trace_path,
        questions_path=questions_path,
        role="solver" if native_web_search else "grader",
        return_code=return_code,
    )
    violations = list(base.get("violations") or [])
    thread = parse_thread_starts(trace_path)
    if thread["threadStartedEventCount"] != 1 or len(thread["threadIds"]) != 1:
        violations.append("exactly_one_codex_thread_required")
    if thread["malformedThreadStartedEvents"]:
        violations.append("malformed_thread_started_event")
    parsed = base.get("trace") if isinstance(base.get("trace"), dict) else {}
    raw_web_count = raw_web_search_event_count(trace_path)
    network_commands = network_capable_shell_commands(parsed)
    if native_web_search:
        violations.append("protocol_native_web_must_be_disabled")
    if parsed_web_search_signal(parsed) or raw_web_count > 0:
        violations.append("native_web_used_while_frozen_disabled")
    if network_commands:
        violations.append("network_capable_shell_command")
    return {
        "policy": "mini_artichokes_blind_pairwise_veto_isolated_agent_v2",
        "passed": not violations,
        "violations": list(dict.fromkeys(violations)),
        "nativeWebSearchAllowed": native_web_search,
        "rawWebSearchEventCount": raw_web_count,
        "jsonlEscapedUnicodeSeparatorCounts": separator_counts,
        "networkCapableShellCommandCount": len(network_commands),
        "networkCapableShellCommands": network_commands,
        **thread,
        "underlyingAudit": base,
    }


def validate_certificates(
    *,
    campaign_dir: Path,
    paths: dict[str, Path],
    validator: Callable[..., dict[str, Any]],
    write_report: bool,
) -> dict[str, Any]:
    errors: list[str] = []
    try:
        report = validator(campaign_dir, write_report=write_report)
    except Exception as exc:  # receipt must record malformed/missing model output
        report = {"passed": False, "errors": [f"strict_validator_exception:{type(exc).__name__}:{exc}"]}
    if not isinstance(report, dict):
        report = {"passed": False, "errors": ["strict_validator_non_object_report"]}
    certificate_sha = sha256_file(paths["certificates"]) if paths["certificates"].is_file() else None
    reported_sha = report.get("certificatesSha256")
    if not certificate_sha:
        errors.append("certificates_file_missing")
    if not isinstance(reported_sha, str) or not reported_sha:
        errors.append("strict_validator_certificates_hash_missing")
    elif reported_sha != certificate_sha:
        errors.append("strict_validator_certificates_hash_mismatch")
    if not report.get("passed"):
        errors.append("strict_validator_rejected")
    output_names = sorted(path.name for path in paths["outputDir"].iterdir())
    unexpected_outputs = sorted(set(output_names) - {"certificates.jsonl", "last_message.txt"})
    if unexpected_outputs:
        errors.append("unexpected_model_output_files")
    last_message_sha = sha256_file(paths["lastMessage"]) if paths["lastMessage"].is_file() else None
    if not last_message_sha:
        errors.append("codex_last_message_missing")
    validation_report_sha = None
    if write_report:
        if not paths["validationReport"].is_file():
            errors.append("strict_validator_report_missing")
        else:
            validation_report_sha = sha256_file(paths["validationReport"])
    return {
        "passed": not errors,
        "errors": errors,
        "certificatesSha256": certificate_sha,
        "lastMessageSha256": last_message_sha,
        "outputFileNames": output_names,
        "unexpectedOutputFileNames": unexpected_outputs,
        "validationReportSha256": validation_report_sha,
        "strictValidatorReport": report,
    }


def assert_fresh_destination(paths: dict[str, Path]) -> None:
    if any(paths["outputDir"].iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty veto output: {paths['outputDir']}")
    stale = [
        path
        for path in (paths["trace"], paths["stderr"], paths["receipt"], paths["validationReport"])
        if path.exists()
    ]
    if stale:
        raise FileExistsError(f"refusing to overwrite prior run artifacts: {', '.join(str(path) for path in stale)}")


def verify_resume(
    *,
    campaign_dir: Path,
    paths: dict[str, Path],
    freeze: dict[str, Any],
    input_hashes: dict[str, str],
    execution_config: dict[str, Any],
    implementations: dict[str, str],
    cli_identity: dict[str, Any],
    validator: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    receipt_path = paths["receipt"]
    if not receipt_path.is_file():
        raise RuntimeError("--resume requires an existing accepted run_receipt.json; fresh execution is refused")
    receipt = load_json(receipt_path)
    failures: list[str] = []
    if receipt.get("receiptSha256") != receipt_digest(receipt):
        failures.append("receipt_self_hash_mismatch")
    if receipt.get("schemaVersion") != 1:
        failures.append("receipt_schema_version_mismatch")
    if receipt.get("status") != "accepted":
        failures.append("receipt_not_accepted")
    if receipt.get("protocol") != PROTOCOL:
        failures.append("receipt_protocol_mismatch")
    if receipt.get("semanticModelInvocations") != 1:
        failures.append("receipt_model_invocation_count_mismatch")
    if receipt.get("acceptedArtifact") != "output/certificates.jsonl":
        failures.append("receipt_accepted_artifact_mismatch")
    if receipt.get("freezeSha256") != freeze.get("freezeSha256"):
        failures.append("receipt_freeze_hash_mismatch")
    if receipt.get("inputFileSha256") != input_hashes:
        failures.append("receipt_input_hashes_mismatch")
    if receipt.get("executionConfig") != execution_config:
        failures.append("receipt_execution_config_mismatch")
    if receipt.get("implementationHashes") != implementations:
        failures.append("receipt_implementation_hashes_mismatch")
    if receipt.get("codexCli") != cli_identity:
        failures.append("receipt_codex_cli_or_command_mismatch")

    artifacts = receipt.get("artifacts") if isinstance(receipt.get("artifacts"), dict) else {}
    for name, path, receipt_key in (
        ("trace", paths["trace"], "rawTraceSha256"),
        ("stderr", paths["stderr"], "stderrSha256"),
        ("certificates", paths["certificates"], "certificatesSha256"),
        ("lastMessage", paths["lastMessage"], "lastMessageSha256"),
        ("validationReport", paths["validationReport"], "validationReportSha256"),
    ):
        if not path.is_file():
            failures.append(f"resume_{name}_missing")
        elif artifacts.get(receipt_key) != sha256_file(path):
            failures.append(f"resume_{name}_hash_mismatch")

    process = receipt.get("process") if isinstance(receipt.get("process"), dict) else {}
    return_code = process.get("exitCode")
    if not isinstance(return_code, int):
        failures.append("resume_process_exit_code_missing")
        return_code = -1
    elif return_code != 0:
        failures.append("resume_process_exit_code_nonzero")
    if process.get("timedOut") is not False:
        failures.append("resume_process_timeout_state_invalid")
    stored_policy = receipt.get("policyAudit") if isinstance(receipt.get("policyAudit"), dict) else {}
    if stored_policy.get("passed") is not True:
        failures.append("receipt_policy_audit_not_accepted")
    stored_validation = (
        receipt.get("artifactValidation") if isinstance(receipt.get("artifactValidation"), dict) else {}
    )
    if stored_validation.get("passed") is not True:
        failures.append("receipt_artifact_validation_not_accepted")
    if paths["trace"].is_file():
        audit = audit_veto_trace(
            trace_path=paths["trace"],
            questions_path=paths["questions"],
            return_code=return_code,
            native_web_search=bool(execution_config["nativeWebSearch"]),
        )
        if not audit["passed"]:
            failures.append("resume_trace_policy_rejected")
        if artifacts.get("threadIds") != audit.get("threadIds"):
            failures.append("resume_thread_ids_mismatch")
    validation = validate_certificates(
        campaign_dir=campaign_dir,
        paths=paths,
        validator=validator,
        write_report=False,
    )
    if not validation["passed"]:
        failures.append("resume_strict_validator_rejected")
    if artifacts.get("certificatesSha256") != validation.get("certificatesSha256"):
        failures.append("resume_validator_certificate_hash_mismatch")
    if failures:
        raise RuntimeError("resume validation failed closed: " + ", ".join(dict.fromkeys(failures)))
    return {
        "status": "resumed_complete_without_model_call",
        "protocol": PROTOCOL,
        "semanticModelInvocations": 0,
        "freezeSha256": freeze.get("freezeSha256"),
        "receiptSha256": receipt.get("receiptSha256"),
        "certificatesSha256": artifacts.get("certificatesSha256"),
        "threadIds": artifacts.get("threadIds"),
    }


def run_agent(
    *,
    campaign_dir: Path,
    codex_home: Path,
    model: str,
    reasoning_effort: str,
    verbosity: str,
    timeout_seconds: int,
    resume: bool,
) -> dict[str, Any]:
    campaign_dir = campaign_dir.resolve()
    codex_home = codex_home.resolve()
    freeze, paths, input_hashes = verify_frozen_bundle(campaign_dir)
    execution_config = verify_execution_config(
        freeze, model=model, reasoning_effort=reasoning_effort, verbosity=verbosity
    )
    validator_module, validator = strict_validator()
    implementations = implementation_hashes(validator_module)
    command = build_codex_command(
        input_dir=paths["inputDir"],
        output_dir=paths["outputDir"],
        codex_home=codex_home,
        model=model,
        reasoning_effort=reasoning_effort,
        verbosity=verbosity,
        native_web_search=bool(execution_config["nativeWebSearch"]),
    )
    verify_tool_free_command(command)
    cli = codex_cli_identity(command)
    if resume:
        return verify_resume(
            campaign_dir=campaign_dir,
            paths=paths,
            freeze=freeze,
            input_hashes=input_hashes,
            execution_config=execution_config,
            implementations=implementations,
            cli_identity=cli,
            validator=validator,
        )

    assert_fresh_destination(paths)
    probe = plain_runner.isolation_probe(
        input_dir=paths["inputDir"], output_dir=paths["outputDir"], codex_home=codex_home
    )
    if not probe.get("passed"):
        raise RuntimeError(f"blind-veto isolation probe failed before model invocation: {probe}")

    prompt = (
        "Read input/RUN_INSTRUCTIONS.md completely and obey it. Read the complete input/questions.jsonl, "
        "input/candidate_pairs.jsonl, and input/expected_certificate_ids.json files. Process every expected "
        "certificate ID exactly once and write the required complete output/certificates.jsonl file. Do not "
        "seek or infer hidden role mappings, use web/search, or use any path outside input and output."
    )
    run_started_utc = utc_now()
    started_monotonic = time.monotonic()
    timed_out = False
    with paths["trace"].open("x", encoding="utf-8") as trace_stream, paths["stderr"].open(
        "x", encoding="utf-8"
    ) as stderr_stream:
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
        except BrokenPipeError:
            pass
        finally:
            try:
                process.stdin.close()
            except BrokenPipeError:
                pass
        try:
            return_code = process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGTERM)
            try:
                return_code = process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                return_code = process.wait(timeout=15)
    run_ended_utc = utc_now()
    elapsed = round(time.monotonic() - started_monotonic, 3)

    audit = audit_veto_trace(
        trace_path=paths["trace"],
        questions_path=paths["questions"],
        return_code=return_code,
        native_web_search=bool(execution_config["nativeWebSearch"]),
    )
    if timed_out:
        audit["violations"].append("codex_process_timeout")
        audit["passed"] = False
    validation = validate_certificates(
        campaign_dir=campaign_dir,
        paths=paths,
        validator=validator,
        write_report=True,
    )
    accepted = bool(audit["passed"] and validation["passed"] and not timed_out and return_code == 0)
    receipt = {
        "schemaVersion": 1,
        "status": "accepted" if accepted else "incomplete",
        "protocol": PROTOCOL,
        "semanticModelInvocations": 1,
        "freezeSha256": freeze.get("freezeSha256"),
        "inputFileSha256": input_hashes,
        "executionConfig": execution_config,
        "implementationHashes": implementations,
        "codexCli": cli,
        "visibilityBoundary": {
            "publicReadOnlyGuestPath": "/tmp/work/input",
            "writableGuestPath": "/tmp/work/output",
            "hiddenControlMounted": False,
            "maskedHostRoots": list(plain_runner.MASKED_HOST_ROOTS),
            "policy": "bubblewrap_public_input_only",
        },
        "isolationProbe": probe,
        "process": {
            "startedAtUtc": run_started_utc,
            "endedAtUtc": run_ended_utc,
            "elapsedSec": elapsed,
            "exitCode": return_code,
            "timedOut": timed_out,
        },
        "policyAudit": audit,
        "artifactValidation": validation,
        "artifacts": {
            "rawTraceSha256": sha256_file(paths["trace"]),
            "stderrSha256": sha256_file(paths["stderr"]),
            "certificatesSha256": validation.get("certificatesSha256"),
            "lastMessageSha256": validation.get("lastMessageSha256"),
            "validationReportSha256": validation.get("validationReportSha256"),
            "threadIds": audit.get("threadIds"),
        },
        "acceptedArtifact": "output/certificates.jsonl" if accepted else None,
    }
    receipt["receiptSha256"] = receipt_digest(receipt)
    write_json_exclusive(paths["receipt"], receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run one sealed Luna agent over the complete blind-pairwise-veto certificate bundle."
    )
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--codex-home", type=Path, default=DEFAULT_CODEX_HOME)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--reasoning-effort", default=DEFAULT_REASONING_EFFORT)
    parser.add_argument("--verbosity", default=DEFAULT_VERBOSITY)
    parser.add_argument("--timeout-seconds", type=int, default=21_600)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.timeout_seconds <= 0:
        parser.error("--timeout-seconds must be positive")
    result = run_agent(
        campaign_dir=args.campaign_dir,
        codex_home=args.codex_home,
        model=args.model,
        reasoning_effort=args.reasoning_effort,
        verbosity=args.verbosity,
        timeout_seconds=args.timeout_seconds,
        resume=args.resume,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("status") in {"accepted", "resumed_complete_without_model_call"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
