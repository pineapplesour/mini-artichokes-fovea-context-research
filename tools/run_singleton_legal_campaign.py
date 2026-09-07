#!/usr/bin/env python3
"""Run externally frozen legal campaign units as isolated singleton processes.

This is a small execution/receipt core, not an arm prompt builder and not a
scientific scorer.  Every unit is an already-instantiated ``case x arm x
stage`` packet.  A separate deterministic helper freezes a dependency-ready
schedule before any call.  The runner then creates an immutable first-attempt
registry before ``Popen``, sends the packet only on stdin, and records one raw
trace and one completion receipt.  It never retries a semantic or transport
attempt.

The module contains no gold-loading path.  Malformed or missing trace-contained
model content becomes a null scientific prediction on the unchanged
denominator.  Broken anchors, hashes, trace boundaries, or receipts invalidate
the unit/campaign instead of falling back or retrying.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = "mini_artichokes_singleton_legal_campaign_v1"
SCHEDULE_PROTOCOL = "mini_artichokes_singleton_dependency_schedule_v1"
UNIT_RECEIPT_PROTOCOL = "mini_artichokes_singleton_unit_receipt_v1"
REGISTRY_PROTOCOL = "mini_artichokes_singleton_first_attempt_registry_v1"

CODEX_HOME = "/home/pineapple/.codex-new-account"
CODEX_MODEL = "gpt-5.6-luna"
CODEX_VERSION = "codex-cli 0.151.0"
FEATURE_COUNT = 129
FEATURE_SNAPSHOT_SHA256 = (
    "8f42f1985441b4f7e78c6db8f0a4c7068bc74075a7133e0423792352f2674f64"
)
FEATURE_LIST_STDOUT_SHA256 = (
    "aca6b0a0d5ea33488ae6d5d3464b6932b0209d273559dcb9163b4039de499964"
)
DISABLED_FEATURES = tuple(
    sorted(
        {
            "apps",
            "artifact",
            "auth_elicitation",
            "browser_use",
            "browser_use_external",
            "browser_use_full_cdp_access",
            "code_mode",
            "code_mode_host",
            "computer_use",
            "deferred_executor",
            "enable_mcp_apps",
            "goals",
            "hooks",
            "image_generation",
            "in_app_browser",
            "in_app_chat",
            "in_app_dictation",
            "in_app_local_automation",
            "in_app_updates",
            "memories",
            "mcp_2026_07_28",
            "multi_agent",
            "multi_agent_v2",
            "plugins",
            "plugin_sharing",
            "remote_plugin",
            "shell_snapshot",
            "shell_snapshot_v2",
            "shell_tool",
            "skill_mcp_dependency_install",
            "skill_search",
            "tool_call_mcp_elicitation",
            "tool_suggest",
            "unified_exec",
            "view_image",
            "workspace_dependencies",
        }
    )
)
STRICT_CONFIG_ARGV = (
    "--ephemeral",
    "--ignore-user-config",
    "--ignore-rules",
    "--strict-config",
    "--config",
    'model_reasoning_effort="high"',
    "--config",
    'model_verbosity="low"',
    "--config",
    'service_tier="default"',
    "--config",
    'web_search="disabled"',
    *tuple(
        item
        for feature in DISABLED_FEATURES
        for item in ("--config", f"features.{feature}=false")
    ),
)

MANIFEST_KEYS = {
    "schemaVersion",
    "protocol",
    "status",
    "campaignId",
    "scheduleSeed",
    "gitAnchor",
    "executionConfig",
    "codeHashes",
    "units",
    "manifestSha256",
}
GIT_ANCHOR_KEYS = {"status", "commit", "tree", "dirty"}
EXECUTION_CONFIG_KEYS = {
    "codexHome",
    "model",
    "reasoningEffort",
    "verbosity",
    "serviceTier",
    "timeoutSeconds",
    "codexVersion",
    "codexExecutablePath",
    "codexExecutableSha256",
    "codexExecutableBytes",
    "featureCount",
    "featureSnapshotSha256",
    "featureListStdoutSha256",
    "disabledFeatures",
    "disabledFeaturesSha256",
    "strictConfigArgv",
    "strictConfigArgvSha256",
    "stdinOnly",
    "outputSchemaCliArg",
    "semanticRetryCount",
    "transportRetryCount",
}
UNIT_KEYS = {
    "unitId",
    "caseId",
    "armId",
    "stageId",
    "dependencies",
    "promptPath",
    "promptSha256",
    "outputSchemaPath",
    "outputSchemaSha256",
    "producesScientificOutcome",
}
SCHEDULE_KEYS = {
    "schemaVersion",
    "protocol",
    "status",
    "campaignId",
    "unitManifestFileSha256",
    "unitManifestSha256",
    "scheduleSeed",
    "algorithm",
    "orderedUnitIds",
    "orderedUnitIdsSha256",
    "scheduleSha256",
}
REGISTRY_KEYS = {
    "schemaVersion",
    "protocol",
    "status",
    "campaignId",
    "unitId",
    "unitManifestFileSha256",
    "unitManifestSha256",
    "scheduleFileSha256",
    "scheduleSha256",
    "sourceGitCommit",
    "sourceGitTree",
    "campaignGitCommit",
    "runtimeIdentitySha256",
    "executionEnvironmentSha256",
    "unitSha256",
    "promptSha256",
    "outputSchemaSha256",
    "runnerCodeSha256",
    "commandArgvSha256",
    "commandArgumentCount",
    "semanticAttemptOrdinal",
    "semanticRetryCount",
    "transportRetryCount",
    "registrySha256",
}
UNIT_RECEIPT_KEYS = {
    "schemaVersion",
    "protocol",
    "status",
    "campaignId",
    "unitId",
    "caseId",
    "armId",
    "stageId",
    "registryFileSha256",
    "registrySha256",
    "traceSha256",
    "stderrSha256",
    "normalizedResultSha256",
    "threadId",
    "turnCount",
    "completedAgentMessageCount",
    "responseValid",
    "invalidResponseReason",
    "scientificOutcome",
    "tokenUsage",
    "processInvocationCount",
    "semanticRetryCount",
    "transportRetryCount",
    "wallTimeMilliseconds",
    "receiptSha256",
}
TOKEN_KEYS = {
    "inputTokens",
    "cachedInputTokens",
    "cacheWriteInputTokens",
    "outputTokens",
    "reasoningTokens",
    "totalTokens",
}
RUNTIME_IDENTITY_KEYS = {
    "codexVersion",
    "executableSha256",
    "featureCount",
    "featureSnapshotSha256",
    "featureListStdoutSha256",
    "identitySha256",
}
RESULT_KEYS = {
    "unitId",
    "caseId",
    "armId",
    "stageId",
    "responseValid",
    "invalidResponseReason",
    "outcome",
}
CAMPAIGN_RECEIPT_KEYS = {
    "schemaVersion",
    "protocol",
    "status",
    "scope",
    "campaignId",
    "unitManifestFileSha256",
    "unitManifestSha256",
    "scheduleFileSha256",
    "scheduleSha256",
    "sourceGitCommit",
    "sourceGitTree",
    "campaignGitCommit",
    "runtimeIdentitySha256",
    "orderedUnitIdsSha256",
    "units",
    "scientificPredictionsPath",
    "scientificPredictionsSha256",
    "scientificRows",
    "nullScientificRows",
    "threadIds",
    "tokenTotals",
    "campaignProcessInvocationCount",
    "semanticRetryCount",
    "transportRetryCount",
    "unitWallTimeMillisecondsTotal",
    "receiptSha256",
}

ALLOWED_EVENT_TYPES = {
    "thread.started",
    "turn.started",
    "turn.completed",
    "item.started",
    "item.updated",
    "item.completed",
}
ITEM_EVENT_TYPES = {"item.started", "item.updated", "item.completed"}
ALLOWED_ITEM_TYPES = {"reasoning", "agent_message", "error"}
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
FORBIDDEN_TRACE_KEY_TOKENS = {
    "auth",
    "command",
    "environment",
    "file",
    "function",
    "gold",
    "holding",
    "label",
    "mcp",
    "patch",
    "path",
    "private",
    "shell",
    "tool",
    "web",
}
FORBIDDEN_RUNNER_KEY_TOKENS = {"gold", "holding", "label", "private"}
OUTCOMES = {"인용됨", "기각", "ABSTAIN"}
CANONICAL_SCIENTIFIC_OUTPUT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "required": ["id", "outcome"],
    "properties": {
        "id": {"type": "string"},
        "outcome": {"enum": sorted(OUTCOMES)},
    },
}
REFERENCE_SCHEMA_KEYS = {"$ref", "$dynamicRef", "$recursiveRef"}
HEX64 = re.compile(r"[0-9a-f]{64}")
HEX40 = re.compile(r"[0-9a-f]{40}")
ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")


class SingletonCampaignError(RuntimeError):
    """Base class for a rejected singleton campaign."""


class CampaignIntegrityError(SingletonCampaignError):
    """An anchor, trace, receipt, or artifact failed closed."""


class StartedUnitError(CampaignIntegrityError):
    """A prior started unit may never be invoked again."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CampaignIntegrityError(message)


def _git_bytes(cwd: Path, arguments: Sequence[str], *, label: str) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(cwd), *arguments],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace")[-500:]
        raise CampaignIntegrityError(f"{label} Git command failed: {detail}")
    return completed.stdout


def _git_repository_root(path: Path) -> Path:
    raw = _git_bytes(path, ["rev-parse", "--show-toplevel"], label="repository root")
    try:
        root = Path(raw.decode("utf-8").strip()).resolve(strict=True)
    except (UnicodeDecodeError, OSError) as exc:
        raise CampaignIntegrityError("invalid Git repository root") from exc
    _require(root.is_dir(), "Git repository root")
    return root


def _git_relative(root: Path, path: Path, *, label: str) -> str:
    try:
        relative = path.resolve(strict=True).relative_to(root)
    except (OSError, ValueError) as exc:
        raise CampaignIntegrityError(f"{label} is outside the anchored repository") from exc
    _require(".." not in relative.parts, f"{label} Git path")
    return relative.as_posix()


def verify_source_git_anchor(
    *,
    manifest_path: Path,
    anchor: Mapping[str, Any],
    bound_paths: Sequence[Path],
) -> dict[str, str]:
    """Verify source inputs/code against the manifest's pre-manifest commit.

    The source commit intentionally does not contain the self-referential unit
    manifest.  The final manifest and schedule are separately bound by
    :func:`verify_campaign_git_anchor` immediately before the first process.
    """

    root = _git_repository_root(manifest_path.parent)
    commit = str(anchor["commit"])
    tree = str(anchor["tree"])
    observed_tree = _git_bytes(
        root, ["rev-parse", f"{commit}^{{tree}}"], label="source tree"
    ).decode("ascii", errors="strict").strip()
    _require(observed_tree == tree, "source Git tree mismatch")
    head = _git_bytes(root, ["rev-parse", "HEAD"], label="source ancestry").decode(
        "ascii", errors="strict"
    ).strip()
    ancestry = subprocess.run(
        ["git", "-C", str(root), "merge-base", "--is-ancestor", commit, head],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        check=False,
    )
    _require(ancestry.returncode == 0, "source Git commit is not an ancestor of HEAD")
    for path in bound_paths:
        relative = _git_relative(root, path, label="source-bound artifact")
        anchored = _git_bytes(
            root, ["show", f"{commit}:{relative}"], label=f"source blob {relative}"
        )
        live, _ = _read_regular(path, label=f"live source blob {relative}")
        _require(anchored == live, f"live source blob differs from anchor: {relative}")
    return {"repositoryRoot": str(root), "commit": commit, "tree": tree}


def verify_campaign_git_anchor(
    *,
    manifest_path: Path,
    schedule_path: Path,
    source_commit: str,
    expected_campaign_commit: str,
) -> dict[str, str]:
    """Verify the clean pre-call commit that contains manifest and schedule."""

    _require(
        HEX40.fullmatch(expected_campaign_commit) is not None,
        "campaign Git commit format",
    )
    root = _git_repository_root(manifest_path.parent)
    head = _git_bytes(root, ["rev-parse", "HEAD"], label="campaign HEAD").decode(
        "ascii", errors="strict"
    ).strip()
    _require(head == expected_campaign_commit, "campaign Git HEAD mismatch")
    status = _git_bytes(
        root,
        ["status", "--porcelain=v1", "--untracked-files=all"],
        label="campaign worktree",
    )
    _require(status == b"", "campaign Git worktree is not clean")
    ancestry = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "merge-base",
            "--is-ancestor",
            source_commit,
            expected_campaign_commit,
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        check=False,
    )
    _require(ancestry.returncode == 0, "campaign commit does not descend from source anchor")
    for path in (manifest_path, schedule_path):
        relative = _git_relative(root, path, label="campaign-bound artifact")
        committed = _git_bytes(
            root,
            ["show", f"{expected_campaign_commit}:{relative}"],
            label=f"campaign blob {relative}",
        )
        live, _ = _read_regular(path, label=f"live campaign blob {relative}")
        _require(committed == live, f"live campaign blob differs from anchor: {relative}")
    tree = _git_bytes(
        root,
        ["rev-parse", f"{expected_campaign_commit}^{{tree}}"],
        label="campaign tree",
    ).decode("ascii", errors="strict").strip()
    return {"repositoryRoot": str(root), "commit": head, "tree": tree}


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


DISABLED_FEATURES_SHA256 = canonical_digest(list(DISABLED_FEATURES))
STRICT_CONFIG_ARGV_SHA256 = canonical_digest(list(STRICT_CONFIG_ARGV))


def _duplicate_key_guard(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _parse_json_bytes(raw: bytes, *, label: str) -> Any:
    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_duplicate_key_guard,
            parse_constant=lambda item: (_ for _ in ()).throw(
                ValueError(f"non-finite JSON value: {item}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise CampaignIntegrityError(f"invalid {label}: {exc}") from exc


def _read_regular(path: Path, *, label: str) -> tuple[bytes, str]:
    _require(not path.is_symlink() and path.is_file(), f"{label} must be a regular file")
    before = path.stat()
    raw = path.read_bytes()
    after = path.stat()
    _require(
        (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns),
        f"{label} changed while read",
    )
    return raw, sha256_bytes(raw)


def _load_object(path: Path, *, label: str) -> tuple[dict[str, Any], str]:
    raw, digest = _read_regular(path, label=label)
    value = _parse_json_bytes(raw, label=label)
    _require(isinstance(value, dict), f"{label} root must be an object")
    return value, digest


def _verify_self_hash(value: Mapping[str, Any], field: str, *, label: str) -> str:
    claimed = value.get(field)
    _require(isinstance(claimed, str) and HEX64.fullmatch(claimed) is not None, f"{label} hash")
    unsigned = {key: item for key, item in value.items() if key != field}
    _require(canonical_digest(unsigned) == claimed, f"{label} self-hash mismatch")
    return claimed


def _write_exclusive_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False
    ).encode("utf-8") + b"\n"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        try:
            path.unlink()
        except OSError:
            pass
        raise


def _write_exclusive_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        try:
            path.unlink()
        except OSError:
            pass
        raise


def _safe_relative(root: Path, raw: Any, *, label: str) -> Path:
    _require(isinstance(raw, str) and bool(raw), f"{label} path")
    relative = Path(raw)
    _require(not relative.is_absolute() and ".." not in relative.parts, f"{label} escapes root")
    path = (root / relative).resolve(strict=False)
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise CampaignIntegrityError(f"{label} escapes root") from exc
    return path


def _forbid_keys(value: Any, *, tokens: set[str], label: str) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            folded = str(key).casefold()
            _require(
                not any(token in folded for token in tokens),
                f"{label} forbidden key: {key}",
            )
            _forbid_keys(item, tokens=tokens, label=label)
    elif isinstance(value, list):
        for item in value:
            _forbid_keys(item, tokens=tokens, label=label)


def _has_forbidden_key(value: Any, *, tokens: set[str]) -> bool:
    if isinstance(value, dict):
        return any(
            any(token in str(key).casefold() for token in tokens)
            or _has_forbidden_key(item, tokens=tokens)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_has_forbidden_key(item, tokens=tokens) for item in value)
    return False


def _has_exact_key(value: Any, key: str) -> bool:
    if isinstance(value, dict):
        return key in value or any(_has_exact_key(item, key) for item in value.values())
    if isinstance(value, list):
        return any(_has_exact_key(item, key) for item in value)
    return False


def _validate_execution_config(config: Any) -> dict[str, Any]:
    _require(isinstance(config, dict) and set(config) == EXECUTION_CONFIG_KEYS, "execution config schema")
    fixed = {
        "codexHome": CODEX_HOME,
        "model": CODEX_MODEL,
        "reasoningEffort": "high",
        "verbosity": "low",
        "serviceTier": "default",
        "codexVersion": CODEX_VERSION,
        "featureCount": FEATURE_COUNT,
        "featureSnapshotSha256": FEATURE_SNAPSHOT_SHA256,
        "featureListStdoutSha256": FEATURE_LIST_STDOUT_SHA256,
        "disabledFeatures": list(DISABLED_FEATURES),
        "disabledFeaturesSha256": DISABLED_FEATURES_SHA256,
        "strictConfigArgv": list(STRICT_CONFIG_ARGV),
        "strictConfigArgvSha256": STRICT_CONFIG_ARGV_SHA256,
        "stdinOnly": True,
        "outputSchemaCliArg": "--output-schema",
        "semanticRetryCount": 0,
        "transportRetryCount": 0,
    }
    for key, expected in fixed.items():
        _require(config.get(key) == expected, f"execution config {key}")
    _require(type(config.get("timeoutSeconds")) is int and config["timeoutSeconds"] > 0, "execution timeout")
    executable = Path(str(config.get("codexExecutablePath")))
    _require(executable.is_absolute() and not executable.is_symlink() and executable.is_file(), "Codex executable path")
    observed_hash = sha256_file(executable)
    observed_bytes = executable.stat().st_size
    _require(
        config.get("codexExecutableSha256") == observed_hash
        and config.get("codexExecutableBytes") == observed_bytes,
        "Codex executable identity",
    )
    return dict(config)


def verify_runtime_identity(config: Mapping[str, Any]) -> dict[str, Any]:
    """Run no-model Codex identity probes and bind their exact observed bytes."""

    _validate_execution_config(config)
    executable = str(config["codexExecutablePath"])
    environment = {
        "CODEX_HOME": CODEX_HOME,
        "PATH": os.environ.get("PATH", ""),
        "LANG": "C.UTF-8",
    }

    def probe(arguments: Sequence[str], *, label: str) -> bytes:
        try:
            completed = subprocess.run(
                [executable, *arguments],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=environment,
                timeout=int(config["timeoutSeconds"]),
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise CampaignIntegrityError(f"Codex {label} probe failed: {exc}") from exc
        _require(
            completed.returncode == 0 and completed.stderr == b"",
            f"Codex {label} probe rejected",
        )
        return completed.stdout

    version_stdout = probe(["--version"], label="version")
    try:
        version = version_stdout.decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        raise CampaignIntegrityError("Codex version output is not UTF-8") from exc
    _require(version == CODEX_VERSION, "Codex live version mismatch")
    feature_stdout = probe(["features", "list"], label="feature-list")
    _require(
        sha256_bytes(feature_stdout) == FEATURE_LIST_STDOUT_SHA256,
        "Codex live feature-list stdout mismatch",
    )
    try:
        feature_lines = feature_stdout.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise CampaignIntegrityError("Codex feature-list output is not UTF-8") from exc
    snapshot: list[dict[str, Any]] = []
    for line in feature_lines:
        parts = line.split()
        _require(
            len(parts) >= 3 and parts[-1] in {"true", "false"},
            "Codex feature-list row schema",
        )
        snapshot.append(
            {
                "name": parts[0],
                "stage": " ".join(parts[1:-1]),
                "enabled": parts[-1] == "true",
            }
        )
    _require(len(snapshot) == FEATURE_COUNT, "Codex live feature count mismatch")
    _require(
        canonical_digest(snapshot) == FEATURE_SNAPSHOT_SHA256,
        "Codex live feature snapshot mismatch",
    )
    identity: dict[str, Any] = {
        "codexVersion": version,
        "executableSha256": sha256_file(Path(executable)),
        "featureCount": len(snapshot),
        "featureSnapshotSha256": canonical_digest(snapshot),
        "featureListStdoutSha256": sha256_bytes(feature_stdout),
    }
    identity["identitySha256"] = canonical_digest(identity)
    return identity


def _validate_runtime_identity(value: Any) -> dict[str, Any]:
    _require(
        isinstance(value, dict) and set(value) == RUNTIME_IDENTITY_KEYS,
        "runtime identity schema",
    )
    claimed = value.get("identitySha256")
    _require(
        isinstance(claimed, str)
        and HEX64.fullmatch(claimed) is not None
        and canonical_digest(
            {key: item for key, item in value.items() if key != "identitySha256"}
        )
        == claimed,
        "runtime identity self-hash",
    )
    _require(
        value.get("codexVersion") == CODEX_VERSION
        and value.get("featureCount") == FEATURE_COUNT
        and value.get("featureSnapshotSha256") == FEATURE_SNAPSHOT_SHA256
        and value.get("featureListStdoutSha256")
        == FEATURE_LIST_STDOUT_SHA256,
        "runtime identity values",
    )
    return dict(value)


def frozen_runtime_identity(config: Mapping[str, Any]) -> dict[str, Any]:
    """Reconstruct the hash-bound identity claim without spawning a process."""

    _validate_execution_config(config)
    identity: dict[str, Any] = {
        "codexVersion": CODEX_VERSION,
        "executableSha256": config["codexExecutableSha256"],
        "featureCount": FEATURE_COUNT,
        "featureSnapshotSha256": FEATURE_SNAPSHOT_SHA256,
        "featureListStdoutSha256": FEATURE_LIST_STDOUT_SHA256,
    }
    identity["identitySha256"] = canonical_digest(identity)
    return identity


def _validate_unit_manifest(
    path: Path,
    *,
    expected_file_sha256: str,
    source_anchor_verifier: Callable[..., Any] = verify_source_git_anchor,
) -> tuple[dict[str, Any], str, str, dict[str, dict[str, Any]], Path]:
    manifest, file_sha = _load_object(path, label="unit manifest")
    _require(file_sha == expected_file_sha256, "unit manifest external Git hash")
    _require(set(manifest) == MANIFEST_KEYS, "unit manifest schema")
    manifest_sha = _verify_self_hash(manifest, "manifestSha256", label="unit manifest")
    _require(
        manifest.get("schemaVersion") == 1
        and manifest.get("protocol") == PROTOCOL
        and manifest.get("status") == "frozen_before_calls",
        "unit manifest identity",
    )
    campaign_id = manifest.get("campaignId")
    _require(isinstance(campaign_id, str) and ID_RE.fullmatch(campaign_id) is not None, "campaign ID")
    _require(isinstance(manifest.get("scheduleSeed"), str) and bool(manifest["scheduleSeed"]), "schedule seed")
    anchor = manifest.get("gitAnchor")
    _require(isinstance(anchor, dict) and set(anchor) == GIT_ANCHOR_KEYS, "Git anchor schema")
    _require(
        anchor.get("status") == "committed_before_calls"
        and anchor.get("dirty") is False
        and isinstance(anchor.get("commit"), str)
        and HEX40.fullmatch(anchor["commit"]) is not None
        and isinstance(anchor.get("tree"), str)
        and HEX40.fullmatch(anchor["tree"]) is not None,
        "Git anchor",
    )
    _forbid_keys(manifest, tokens=FORBIDDEN_RUNNER_KEY_TOKENS, label="runner manifest")
    _validate_execution_config(manifest.get("executionConfig"))
    code_hashes = manifest.get("codeHashes")
    _require(isinstance(code_hashes, dict) and bool(code_hashes), "code hash bindings")
    runner_path = Path(__file__).resolve()
    _require(code_hashes.get(str(runner_path)) == sha256_file(runner_path), "runner code binding")
    source_bound_paths: list[Path] = []
    for raw_path, expected in code_hashes.items():
        code_path = Path(raw_path)
        _require(code_path.is_absolute() and not code_path.is_symlink() and code_path.is_file(), "code binding path")
        _require(isinstance(expected, str) and sha256_file(code_path) == expected, "code binding hash")
        source_bound_paths.append(code_path)

    root = path.resolve().parent
    units = manifest.get("units")
    _require(isinstance(units, list) and bool(units), "unit inventory")
    by_id: dict[str, dict[str, Any]] = {}
    coordinates: set[tuple[str, str, str]] = set()
    case_arm_pairs: set[tuple[str, str]] = set()
    scientific_pairs: set[tuple[str, str]] = set()
    ordered_ids: list[str] = []
    for position, unit in enumerate(units, 1):
        _require(isinstance(unit, dict) and set(unit) == UNIT_KEYS, f"unit {position} schema")
        for field in ("unitId", "caseId", "armId", "stageId"):
            _require(isinstance(unit.get(field), str) and ID_RE.fullmatch(unit[field]) is not None, f"unit {position} {field}")
        unit_id = unit["unitId"]
        _require(unit_id not in by_id, f"duplicate unit ID: {unit_id}")
        coordinate = (unit["caseId"], unit["armId"], unit["stageId"])
        _require(
            coordinate not in coordinates,
            f"duplicate case/arm/stage coordinate: {coordinate}",
        )
        coordinates.add(coordinate)
        pair = (unit["caseId"], unit["armId"])
        case_arm_pairs.add(pair)
        deps = unit.get("dependencies")
        _require(isinstance(deps, list) and all(isinstance(item, str) for item in deps), f"unit {unit_id} dependencies")
        _require(len(deps) == len(set(deps)) and unit_id not in deps, f"unit {unit_id} dependency uniqueness")
        _require(type(unit.get("producesScientificOutcome")) is bool, f"unit {unit_id} scientific flag")
        prompt_path = _safe_relative(root, unit.get("promptPath"), label=f"unit {unit_id} prompt")
        schema_path = _safe_relative(root, unit.get("outputSchemaPath"), label=f"unit {unit_id} output schema")
        prompt_raw, prompt_sha = _read_regular(prompt_path, label=f"unit {unit_id} prompt")
        schema, schema_sha = _load_object(schema_path, label=f"unit {unit_id} output schema")
        _require(bool(prompt_raw) and bool(schema), f"unit {unit_id} empty input")
        _forbid_keys(schema, tokens=FORBIDDEN_RUNNER_KEY_TOKENS, label=f"unit {unit_id} output schema")
        _require(
            not any(_has_exact_key(schema, key) for key in REFERENCE_SCHEMA_KEYS),
            f"unit {unit_id} output schema references are not independently bound",
        )
        if unit["producesScientificOutcome"]:
            _require(
                schema == CANONICAL_SCIENTIFIC_OUTPUT_SCHEMA,
                f"unit {unit_id} scientific output schema",
            )
            _require(pair not in scientific_pairs, f"duplicate scientific case/arm pair: {pair}")
            scientific_pairs.add(pair)
        _require(unit.get("promptSha256") == prompt_sha, f"unit {unit_id} prompt hash")
        _require(unit.get("outputSchemaSha256") == schema_sha, f"unit {unit_id} schema hash")
        source_bound_paths.extend((prompt_path, schema_path))
        for path_field in ("promptPath", "outputSchemaPath"):
            folded = str(unit[path_field]).casefold()
            _require(not any(token in folded for token in FORBIDDEN_RUNNER_KEY_TOKENS), f"unit {unit_id} forbidden input path")
        by_id[unit_id] = dict(unit)
        ordered_ids.append(unit_id)
    all_ids = set(by_id)
    _require(all(set(unit["dependencies"]) <= all_ids for unit in units), "unknown unit dependency")
    _require(
        scientific_pairs == case_arm_pairs,
        "each case/arm pair requires exactly one scientific output unit",
    )
    _dependency_waves(by_id)  # cycle gate
    source_anchor_verifier(
        manifest_path=path.resolve(),
        anchor=anchor,
        bound_paths=tuple(dict.fromkeys(source_bound_paths)),
    )
    return manifest, file_sha, manifest_sha, by_id, root


def _dependency_waves(units: Mapping[str, Mapping[str, Any]]) -> dict[str, int]:
    remaining = set(units)
    completed: set[str] = set()
    waves: dict[str, int] = {}
    wave = 0
    while remaining:
        ready = sorted(
            unit_id
            for unit_id in remaining
            if set(units[unit_id]["dependencies"]) <= completed
        )
        _require(bool(ready), "unit dependency cycle")
        for unit_id in ready:
            waves[unit_id] = wave
        completed.update(ready)
        remaining.difference_update(ready)
        wave += 1
    return waves


def _schedule_order(
    units: Mapping[str, Mapping[str, Any]], *, seed: str
) -> list[str]:
    remaining = set(units)
    completed: set[str] = set()
    arm_counts: dict[str, int] = {}
    case_counts: dict[str, int] = {}
    pair_counts: dict[tuple[str, str], int] = {}
    ordered: list[str] = []
    while remaining:
        ready = [
            unit_id
            for unit_id in remaining
            if set(units[unit_id]["dependencies"]) <= completed
        ]
        _require(bool(ready), "unit dependency cycle")

        def key(unit_id: str) -> tuple[int, int, int, str]:
            unit = units[unit_id]
            arm = str(unit["armId"])
            case = str(unit["caseId"])
            tie = hashlib.sha256(
                f"singleton-schedule-v1\0{seed}\0{unit_id}".encode("utf-8")
            ).hexdigest()
            return (
                pair_counts.get((case, arm), 0),
                arm_counts.get(arm, 0),
                case_counts.get(case, 0),
                tie,
            )

        selected = min(ready, key=key)
        unit = units[selected]
        arm = str(unit["armId"])
        case = str(unit["caseId"])
        arm_counts[arm] = arm_counts.get(arm, 0) + 1
        case_counts[case] = case_counts.get(case, 0) + 1
        pair_counts[(case, arm)] = pair_counts.get((case, arm), 0) + 1
        ordered.append(selected)
        completed.add(selected)
        remaining.remove(selected)
    return ordered


def build_schedule_manifest(
    *,
    unit_manifest_path: Path,
    expected_unit_manifest_file_sha256: str,
    output_path: Path,
    source_anchor_verifier: Callable[..., Any] = verify_source_git_anchor,
) -> dict[str, Any]:
    manifest, manifest_file_sha, manifest_sha, units, _ = _validate_unit_manifest(
        unit_manifest_path,
        expected_file_sha256=expected_unit_manifest_file_sha256,
        source_anchor_verifier=source_anchor_verifier,
    )
    ordered = _schedule_order(units, seed=manifest["scheduleSeed"])
    schedule: dict[str, Any] = {
        "schemaVersion": 1,
        "protocol": SCHEDULE_PROTOCOL,
        "status": "frozen_before_calls",
        "campaignId": manifest["campaignId"],
        "unitManifestFileSha256": manifest_file_sha,
        "unitManifestSha256": manifest_sha,
        "scheduleSeed": manifest["scheduleSeed"],
        "algorithm": "dependency-ready-case-arm-balanced-sha256-v1",
        "orderedUnitIds": ordered,
        "orderedUnitIdsSha256": canonical_digest(ordered),
    }
    schedule["scheduleSha256"] = canonical_digest(schedule)
    _write_exclusive_json(output_path.resolve(), schedule)
    return schedule


def _validate_schedule(
    path: Path,
    *,
    expected_file_sha256: str,
    manifest: Mapping[str, Any],
    manifest_file_sha256: str,
    manifest_sha256: str,
    units: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, Any], str, str]:
    schedule, file_sha = _load_object(path, label="schedule manifest")
    _require(file_sha == expected_file_sha256, "schedule external Git hash")
    _require(set(schedule) == SCHEDULE_KEYS, "schedule schema")
    schedule_sha = _verify_self_hash(schedule, "scheduleSha256", label="schedule")
    expected_order = _schedule_order(units, seed=str(manifest["scheduleSeed"]))
    _require(
        schedule.get("schemaVersion") == 1
        and schedule.get("protocol") == SCHEDULE_PROTOCOL
        and schedule.get("status") == "frozen_before_calls"
        and schedule.get("campaignId") == manifest["campaignId"]
        and schedule.get("unitManifestFileSha256") == manifest_file_sha256
        and schedule.get("unitManifestSha256") == manifest_sha256
        and schedule.get("scheduleSeed") == manifest["scheduleSeed"]
        and schedule.get("algorithm")
        == "dependency-ready-case-arm-balanced-sha256-v1"
        and schedule.get("orderedUnitIds") == expected_order
        and schedule.get("orderedUnitIdsSha256") == canonical_digest(expected_order),
        "schedule binding",
    )
    return schedule, file_sha, schedule_sha


def _build_command(config: Mapping[str, Any], *, schema_path: Path, work_dir: Path) -> list[str]:
    command = [
        str(config["codexExecutablePath"]),
        "exec",
        *STRICT_CONFIG_ARGV,
        "--skip-git-repo-check",
        "--sandbox",
        "read-only",
        "--cd",
        str(work_dir),
        "--model",
        CODEX_MODEL,
        "--json",
        "--output-schema",
        str(schema_path),
        "-",
    ]
    _require(command.count("-") == 1 and command[-1] == "-", "stdin-only command")
    _require(command.count("--output-schema") == 1, "output-schema command")
    for required in ("--ephemeral", "--ignore-user-config", "--ignore-rules", "--strict-config"):
        _require(command.count(required) == 1, f"strict command missing {required}")
    return command


def _execution_environment() -> dict[str, str]:
    return {
        "CODEX_HOME": CODEX_HOME,
        "PATH": os.environ.get("PATH", ""),
        "LANG": "C.UTF-8",
    }


def _recursive_trace_key_gate(value: Any, *, location: str) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            folded = str(key).casefold()
            _require(
                not any(token in folded for token in FORBIDDEN_TRACE_KEY_TOKENS),
                f"trace forbidden key at {location}: {key}",
            )
            _recursive_trace_key_gate(item, location=f"{location}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _recursive_trace_key_gate(item, location=f"{location}[{index}]")


def audit_trace(raw: bytes, *, unit_id: str) -> dict[str, Any]:
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CampaignIntegrityError(f"{unit_id} trace is not UTF-8") from exc
    _require(raw.endswith(b"\n") and b"\r" not in raw, f"{unit_id} trace must use final LF only")
    lines = raw[:-1].split(b"\n")
    _require(bool(lines) and all(lines), f"{unit_id} empty or blank trace row")
    events: list[dict[str, Any]] = []
    containment_diagnostic_indices: list[int] = []
    for line_number, line in enumerate(lines, 1):
        _require(bool(line.strip()), f"{unit_id} blank trace row")
        event = _parse_json_bytes(line, label=f"{unit_id} trace row {line_number}")
        _require(isinstance(event, dict), f"{unit_id} trace event object")
        _recursive_trace_key_gate(event, location=f"row{line_number}")
        event_type = event.get("type")
        _require(event_type in ALLOWED_EVENT_TYPES, f"{unit_id} trace event not allowlisted: {event_type}")
        if event_type in ITEM_EVENT_TYPES:
            _require(set(event) == {"type", "item"}, f"{unit_id} item event schema")
            item = event.get("item")
            _require(isinstance(item, dict), f"{unit_id} item object")
            _require(item.get("type") in ALLOWED_ITEM_TYPES, f"{unit_id} item type not allowlisted")
            item_type = item["type"]
            if item_type in {"reasoning", "agent_message"}:
                _require(
                    set(item) == {"id", "type", "text"}
                    and isinstance(item.get("id"), str)
                    and bool(item["id"])
                    and isinstance(item.get("text"), str),
                    f"{unit_id} message item exact schema",
                )
            else:
                _require(
                    event_type == "item.completed"
                    and set(item) == {"id", "type", "message"}
                    and isinstance(item.get("id"), str)
                    and bool(item["id"])
                    and item.get("message")
                    == EXPECTED_CODE_MODE_DISABLED_DIAGNOSTIC,
                    f"{unit_id} unexpected error item",
                )
                containment_diagnostic_indices.append(len(events))
        events.append(event)

    thread_events = [event for event in events if event["type"] == "thread.started"]
    turn_started = [event for event in events if event["type"] == "turn.started"]
    turn_completed = [event for event in events if event["type"] == "turn.completed"]
    _require(len(thread_events) == len(turn_started) == len(turn_completed) == 1, f"{unit_id} exact thread/turn lifecycle")
    _require(len(events) >= 4, f"{unit_id} incomplete trace lifecycle")
    _require(
        events[0] is thread_events[0]
        and containment_diagnostic_indices == [1]
        and events[2] is turn_started[0]
        and events[-1] is turn_completed[0],
        f"{unit_id} exact containment and turn lifecycle order",
    )
    _require(set(thread_events[0]) == {"type", "thread_id"}, f"{unit_id} thread event schema")
    thread_id = thread_events[0].get("thread_id")
    _require(isinstance(thread_id, str) and bool(thread_id), f"{unit_id} thread ID")
    _require(set(turn_started[0]) == {"type"}, f"{unit_id} turn-start schema")
    _require(set(turn_completed[0]) == {"type", "usage"}, f"{unit_id} turn-complete schema")
    usage = turn_completed[0].get("usage")
    _require(
        isinstance(usage, dict) and set(usage) == EXPECTED_TURN_USAGE_KEYS,
        f"{unit_id} token usage schema",
    )
    _require(
        all(
            type(usage[key]) is int and usage[key] >= 0
            for key in EXPECTED_TURN_USAGE_KEYS
        )
        and usage["input_tokens"] + usage["output_tokens"] > 0,
        f"{unit_id} token usage values",
    )
    _require(usage["cached_input_tokens"] <= usage["input_tokens"], f"{unit_id} cached tokens")
    _require(usage["cache_write_input_tokens"] <= usage["input_tokens"], f"{unit_id} cache-write tokens")
    _require(usage["reasoning_output_tokens"] <= usage["output_tokens"], f"{unit_id} reasoning tokens")
    token_usage = {
        "inputTokens": usage["input_tokens"],
        "cachedInputTokens": usage["cached_input_tokens"],
        "cacheWriteInputTokens": usage["cache_write_input_tokens"],
        "outputTokens": usage["output_tokens"],
        "reasoningTokens": usage["reasoning_output_tokens"],
        "totalTokens": usage["input_tokens"] + usage["output_tokens"],
    }
    agent_messages = [
        event["item"].get("text")
        for event in events
        if event["type"] == "item.completed"
        and isinstance(event.get("item"), dict)
        and event["item"].get("type") == "agent_message"
    ]
    _require(
        len(agent_messages) == 1,
        f"{unit_id} must contain exactly one completed agent message",
    )
    return {
        "threadId": thread_id,
        "turnCount": 1,
        "completedAgentMessageCount": len(agent_messages),
        "agentMessage": agent_messages[0] if agent_messages else None,
        "tokenUsage": token_usage,
    }


def _normalize_response(
    *, unit: Mapping[str, Any], trace_audit: Mapping[str, Any]
) -> dict[str, Any]:
    reason: str | None = None
    outcome: str | None = None
    response_valid = False
    raw_message = trace_audit.get("agentMessage")
    if raw_message is None or raw_message == "":
        reason = "missing_completed_agent_message"
    elif not isinstance(raw_message, str):
        reason = "non_text_agent_message"
    else:
        try:
            response = _parse_json_bytes(raw_message.encode("utf-8"), label="agent response")
        except CampaignIntegrityError:
            response = None
            reason = "malformed_agent_response"
        if response is not None:
            if not isinstance(response, dict):
                reason = "agent_response_not_object"
            elif _has_forbidden_key(
                response, tokens=FORBIDDEN_RUNNER_KEY_TOKENS
            ):
                reason = "forbidden_response_key"
            elif unit["producesScientificOutcome"]:
                if set(response) != {"id", "outcome"}:
                    reason = "scientific_response_schema"
                elif response.get("id") != unit["caseId"]:
                    reason = "scientific_response_id"
                elif response.get("outcome") not in OUTCOMES:
                    reason = "scientific_response_outcome"
                else:
                    response_valid = True
                    outcome = str(response["outcome"])
            else:
                response_valid = True
    return {
        "unitId": unit["unitId"],
        "caseId": unit["caseId"],
        "armId": unit["armId"],
        "stageId": unit["stageId"],
        "responseValid": response_valid,
        "invalidResponseReason": reason,
        "outcome": outcome,
    }


def _unit_paths(output_root: Path, unit_id: str) -> dict[str, Path]:
    _require(ID_RE.fullmatch(unit_id) is not None, "unit output ID")
    units_root = output_root / "units"
    if os.path.lexists(units_root):
        _require(
            not units_root.is_symlink() and units_root.is_dir(),
            "units output directory integrity",
        )
    root = units_root / unit_id
    if os.path.lexists(root):
        _require(
            not root.is_symlink() and root.is_dir(),
            f"{unit_id} output directory integrity",
        )
    try:
        root.resolve(strict=False).relative_to(output_root.resolve(strict=True))
    except (OSError, ValueError) as exc:
        raise CampaignIntegrityError(f"{unit_id} output directory escapes campaign") from exc
    return {
        "root": root,
        "registry": root / "attempt_started.json",
        "trace": root / "raw_trace.jsonl",
        "stderr": root / "raw_stderr.bin",
        "result": root / "normalized_result.json",
        "receipt": root / "unit_receipt.json",
    }


def _kill_and_reap(process: Any) -> None:
    """Best-effort hard stop for a timed-out first attempt; never retry it."""

    killed = False
    pid = getattr(process, "pid", None)
    if type(pid) is int and pid > 0:
        try:
            os.killpg(pid, signal.SIGKILL)
            killed = True
        except OSError:
            pass
    if not killed:
        try:
            process.kill()
        except (AttributeError, OSError):
            pass
    try:
        process.communicate(timeout=5)
    except BaseException:
        # The original execution error remains authoritative.
        pass


def _load_completed_unit(
    *,
    paths: Mapping[str, Path],
    expected_registry: Mapping[str, Any],
    unit: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    registry, registry_file_sha = _load_object(paths["registry"], label="attempt registry")
    _require(registry == expected_registry, f"{unit['unitId']} registry tamper")
    receipt, _ = _load_object(paths["receipt"], label="unit receipt")
    _require(set(receipt) == UNIT_RECEIPT_KEYS, f"{unit['unitId']} receipt schema")
    _verify_self_hash(receipt, "receiptSha256", label=f"{unit['unitId']} receipt")
    _require(
        receipt.get("status") == "accepted_complete"
        and receipt.get("registryFileSha256") == registry_file_sha
        and receipt.get("registrySha256") == registry["registrySha256"],
        f"{unit['unitId']} completion binding",
    )
    trace_raw, trace_sha = _read_regular(paths["trace"], label=f"{unit['unitId']} trace")
    stderr_raw, stderr_sha = _read_regular(
        paths["stderr"], label=f"{unit['unitId']} stderr"
    )
    trace_audit = audit_trace(trace_raw, unit_id=str(unit["unitId"]))
    result, result_file_sha = _load_object(paths["result"], label=f"{unit['unitId']} result")
    _require(set(result) == RESULT_KEYS, f"{unit['unitId']} result schema")
    expected_result = _normalize_response(unit=unit, trace_audit=trace_audit)
    _require(
        result == expected_result
        and receipt.get("schemaVersion") == 1
        and receipt.get("protocol") == UNIT_RECEIPT_PROTOCOL
        and receipt.get("status") == "accepted_complete"
        and receipt.get("campaignId") == expected_registry["campaignId"]
        and receipt.get("unitId") == unit["unitId"]
        and receipt.get("caseId") == unit["caseId"]
        and receipt.get("armId") == unit["armId"]
        and receipt.get("stageId") == unit["stageId"]
        and receipt.get("traceSha256") == trace_sha
        and receipt.get("stderrSha256") == stderr_sha
        and stderr_raw == b""
        and receipt.get("normalizedResultSha256") == result_file_sha
        and receipt.get("threadId") == trace_audit["threadId"]
        and receipt.get("turnCount") == 1
        and receipt.get("completedAgentMessageCount") == 1
        and receipt.get("tokenUsage") == trace_audit["tokenUsage"]
        and receipt.get("responseValid") == result["responseValid"]
        and receipt.get("invalidResponseReason") == result["invalidResponseReason"]
        and receipt.get("scientificOutcome") == result["outcome"],
        f"{unit['unitId']} completed artifact tamper",
    )
    _require(
        receipt.get("processInvocationCount") == 1
        and receipt.get("semanticRetryCount") == 0
        and receipt.get("transportRetryCount") == 0
        and type(receipt.get("wallTimeMilliseconds")) is int
        and receipt["wallTimeMilliseconds"] >= 0,
        f"{unit['unitId']} execution-ledger tamper",
    )
    return receipt, result


def _run_or_resume_unit(
    *,
    output_root: Path,
    campaign_id: str,
    unit: Mapping[str, Any],
    manifest_root: Path,
    manifest_file_sha: str,
    manifest_sha: str,
    schedule_file_sha: str,
    schedule_sha: str,
    source_git_commit: str,
    source_git_tree: str,
    campaign_git_commit: str,
    runtime_identity_sha256: str,
    config: Mapping[str, Any],
    code_hashes: Mapping[str, str],
    process_factory: Callable[..., Any],
    monotonic: Callable[[], float],
) -> tuple[dict[str, Any], dict[str, Any], int]:
    _validate_execution_config(config)
    for raw_path, expected_hash in code_hashes.items():
        _require(
            sha256_file(Path(raw_path)) == expected_hash,
            f"{unit['unitId']} live implementation code changed",
        )
    paths = _unit_paths(output_root, str(unit["unitId"]))
    prompt_path = _safe_relative(manifest_root, unit["promptPath"], label="live prompt")
    schema_path = _safe_relative(manifest_root, unit["outputSchemaPath"], label="live schema")
    prompt_raw, prompt_sha = _read_regular(prompt_path, label="live prompt")
    _, schema_sha = _read_regular(schema_path, label="live schema")
    _require(prompt_sha == unit["promptSha256"] and schema_sha == unit["outputSchemaSha256"], f"{unit['unitId']} live input changed")
    command = _build_command(config, schema_path=schema_path, work_dir=paths["root"])
    environment = _execution_environment()
    registry: dict[str, Any] = {
        "schemaVersion": 1,
        "protocol": REGISTRY_PROTOCOL,
        "status": "started_before_process",
        "campaignId": campaign_id,
        "unitId": unit["unitId"],
        "unitManifestFileSha256": manifest_file_sha,
        "unitManifestSha256": manifest_sha,
        "scheduleFileSha256": schedule_file_sha,
        "scheduleSha256": schedule_sha,
        "sourceGitCommit": source_git_commit,
        "sourceGitTree": source_git_tree,
        "campaignGitCommit": campaign_git_commit,
        "runtimeIdentitySha256": runtime_identity_sha256,
        "executionEnvironmentSha256": canonical_digest(environment),
        "unitSha256": canonical_digest(dict(unit)),
        "promptSha256": prompt_sha,
        "outputSchemaSha256": schema_sha,
        "runnerCodeSha256": sha256_file(Path(__file__).resolve()),
        "commandArgvSha256": canonical_digest(command),
        "commandArgumentCount": len(command),
        "semanticAttemptOrdinal": 1,
        "semanticRetryCount": 0,
        "transportRetryCount": 0,
    }
    registry["registrySha256"] = canonical_digest(registry)

    if paths["receipt"].exists():
        _require(paths["registry"].exists(), f"{unit['unitId']} receipt without registry")
        receipt, result = _load_completed_unit(
            paths=paths, expected_registry=registry, unit=unit
        )
        return receipt, result, 0
    if paths["registry"].exists():
        raise StartedUnitError(
            f"{unit['unitId']} has a started first attempt and may never be re-invoked"
        )
    if paths["root"].exists():
        _require(
            not any(paths["root"].iterdir()),
            f"{unit['unitId']} orphan artifact before first-attempt registry",
        )

    _write_exclusive_json(paths["registry"], registry)
    _require(
        set(paths["root"].iterdir()) == {paths["registry"]},
        f"{unit['unitId']} unexpected artifact before process",
    )
    start = monotonic()
    try:
        process = process_factory(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=paths["root"],
            env=environment,
            start_new_session=True,
        )
        try:
            stdout, _stderr = process.communicate(
                input=prompt_raw,
                timeout=int(config["timeoutSeconds"]),
            )
        except BaseException:
            _kill_and_reap(process)
            raise
    except BaseException:
        # The immutable started registry deliberately remains as a no-recall gate.
        raise
    end = monotonic()
    _require(
        isinstance(stdout, bytes) and isinstance(_stderr, bytes),
        f"{unit['unitId']} process output bytes",
    )
    _write_exclusive_bytes(paths["trace"], stdout)
    _write_exclusive_bytes(paths["stderr"], _stderr)
    _require(process.returncode == 0, f"{unit['unitId']} process return code")
    _require(_stderr == b"", f"{unit['unitId']} process stderr")
    trace_audit = audit_trace(stdout, unit_id=str(unit["unitId"]))
    result = _normalize_response(unit=unit, trace_audit=trace_audit)
    _write_exclusive_json(paths["result"], result)
    registry_file_sha = sha256_file(paths["registry"])
    receipt: dict[str, Any] = {
        "schemaVersion": 1,
        "protocol": UNIT_RECEIPT_PROTOCOL,
        "status": "accepted_complete",
        "campaignId": campaign_id,
        "unitId": unit["unitId"],
        "caseId": unit["caseId"],
        "armId": unit["armId"],
        "stageId": unit["stageId"],
        "registryFileSha256": registry_file_sha,
        "registrySha256": registry["registrySha256"],
        "traceSha256": sha256_file(paths["trace"]),
        "stderrSha256": sha256_file(paths["stderr"]),
        "normalizedResultSha256": sha256_file(paths["result"]),
        "threadId": trace_audit["threadId"],
        "turnCount": trace_audit["turnCount"],
        "completedAgentMessageCount": trace_audit["completedAgentMessageCount"],
        "responseValid": result["responseValid"],
        "invalidResponseReason": result["invalidResponseReason"],
        "scientificOutcome": result["outcome"],
        "tokenUsage": trace_audit["tokenUsage"],
        "processInvocationCount": 1,
        "semanticRetryCount": 0,
        "transportRetryCount": 0,
        "wallTimeMilliseconds": max(0, int(round((end - start) * 1000))),
    }
    receipt["receiptSha256"] = canonical_digest(receipt)
    _write_exclusive_json(paths["receipt"], receipt)
    return receipt, result, 1


def _jsonl_payload(rows: Sequence[Mapping[str, Any]]) -> bytes:
    return b"".join(canonical_json_bytes(row) + b"\n" for row in rows)


def _write_jsonl_exclusive(path: Path, rows: Sequence[Mapping[str, Any]]) -> str:
    payload = _jsonl_payload(rows)
    _write_exclusive_bytes(path, payload)
    return sha256_bytes(payload)


def _compose_campaign_receipt(
    *,
    manifest: Mapping[str, Any],
    manifest_file_sha: str,
    manifest_sha: str,
    schedule: Mapping[str, Any],
    schedule_file_sha: str,
    schedule_sha: str,
    campaign_git_commit: str,
    runtime_identity_sha256: str,
    units: Mapping[str, Mapping[str, Any]],
    receipts: Sequence[Mapping[str, Any]],
    results: Sequence[Mapping[str, Any]],
    predictions_sha: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    thread_ids = [str(receipt["threadId"]) for receipt in receipts]
    _require(
        len(thread_ids) == len(set(thread_ids)),
        "singleton thread IDs are not unique",
    )
    scientific = [
        result
        for result in results
        if units[str(result["unitId"])]["producesScientificOutcome"]
    ]
    scientific_rows = [
        {
            "id": result["caseId"],
            "armId": result["armId"],
            "unitId": result["unitId"],
            "outcome": result["outcome"],
        }
        for result in scientific
    ]
    token_totals = {key: 0 for key in TOKEN_KEYS}
    for receipt in receipts:
        for key in TOKEN_KEYS:
            token_totals[key] += int(receipt["tokenUsage"][key])
    campaign_receipt: dict[str, Any] = {
        "schemaVersion": 1,
        "protocol": PROTOCOL,
        "status": "accepted_complete",
        "scope": "singleton_unit_execution_core_not_scoring",
        "campaignId": manifest["campaignId"],
        "unitManifestFileSha256": manifest_file_sha,
        "unitManifestSha256": manifest_sha,
        "scheduleFileSha256": schedule_file_sha,
        "scheduleSha256": schedule_sha,
        "sourceGitCommit": manifest["gitAnchor"]["commit"],
        "sourceGitTree": manifest["gitAnchor"]["tree"],
        "campaignGitCommit": campaign_git_commit,
        "runtimeIdentitySha256": runtime_identity_sha256,
        "orderedUnitIdsSha256": schedule["orderedUnitIdsSha256"],
        "units": [
            {
                "unitId": receipt["unitId"],
                "receiptSha256": receipt["receiptSha256"],
                "responseValid": receipt["responseValid"],
            }
            for receipt in receipts
        ],
        "scientificPredictionsPath": "scientific_predictions.jsonl",
        "scientificPredictionsSha256": predictions_sha,
        "scientificRows": len(scientific_rows),
        "nullScientificRows": sum(
            row["outcome"] is None for row in scientific_rows
        ),
        "threadIds": thread_ids,
        "tokenTotals": token_totals,
        "campaignProcessInvocationCount": sum(
            int(receipt["processInvocationCount"]) for receipt in receipts
        ),
        "semanticRetryCount": 0,
        "transportRetryCount": 0,
        "unitWallTimeMillisecondsTotal": sum(
            int(receipt["wallTimeMilliseconds"]) for receipt in receipts
        ),
    }
    campaign_receipt["receiptSha256"] = canonical_digest(campaign_receipt)
    return campaign_receipt, scientific_rows


def validate_completed_campaign(
    *,
    unit_manifest_path: Path,
    expected_unit_manifest_file_sha256: str,
    schedule_path: Path,
    expected_schedule_file_sha256: str,
    expected_campaign_git_commit: str,
    output_dir: Path,
    source_anchor_verifier: Callable[..., Any] = verify_source_git_anchor,
    campaign_anchor_verifier: Callable[..., Any] = verify_campaign_git_anchor,
    runtime_identity_verifier: Callable[..., Any] = frozen_runtime_identity,
) -> dict[str, Any]:
    """Validate a completed campaign without creating files or model processes.

    The injected verifiers are test seams only.  This function has no execution
    fallback: a missing or partial receipt is an integrity error, never a call.
    """

    _require(
        isinstance(expected_campaign_git_commit, str)
        and HEX40.fullmatch(expected_campaign_git_commit) is not None,
        "campaign Git commit format",
    )
    manifest, manifest_file_sha, manifest_sha, units, manifest_root = (
        _validate_unit_manifest(
            unit_manifest_path,
            expected_file_sha256=expected_unit_manifest_file_sha256,
            source_anchor_verifier=source_anchor_verifier,
        )
    )
    schedule, schedule_file_sha, schedule_sha = _validate_schedule(
        schedule_path,
        expected_file_sha256=expected_schedule_file_sha256,
        manifest=manifest,
        manifest_file_sha256=manifest_file_sha,
        manifest_sha256=manifest_sha,
        units=units,
    )
    campaign_anchor_verifier(
        manifest_path=unit_manifest_path.resolve(),
        schedule_path=schedule_path.resolve(),
        source_commit=manifest["gitAnchor"]["commit"],
        expected_campaign_commit=expected_campaign_git_commit,
    )
    runtime_identity = _validate_runtime_identity(
        runtime_identity_verifier(manifest["executionConfig"])
    )
    _require(
        runtime_identity["executableSha256"]
        == manifest["executionConfig"]["codexExecutableSha256"],
        "runtime executable identity mismatch",
    )
    runtime_identity_sha = runtime_identity["identitySha256"]
    unresolved_output = Path(output_dir)
    _require(
        not unresolved_output.is_symlink() and unresolved_output.is_dir(),
        "completed campaign output directory",
    )
    output_root = unresolved_output.resolve()
    campaign_receipt_path = output_root / "campaign_receipt.json"
    predictions_path = output_root / "scientific_predictions.jsonl"
    campaign_receipt, _ = _load_object(
        campaign_receipt_path, label="campaign receipt"
    )
    _require(
        set(campaign_receipt) == CAMPAIGN_RECEIPT_KEYS,
        "campaign receipt schema",
    )
    _verify_self_hash(
        campaign_receipt, "receiptSha256", label="campaign receipt"
    )
    completed_receipts: list[dict[str, Any]] = []
    completed_results: list[dict[str, Any]] = []
    for unit_id in schedule["orderedUnitIds"]:
        unit = units[unit_id]
        paths = _unit_paths(output_root, unit_id)
        prompt_path = _safe_relative(
            manifest_root, unit["promptPath"], label="completed prompt"
        )
        schema_path = _safe_relative(
            manifest_root, unit["outputSchemaPath"], label="completed schema"
        )
        command = _build_command(
            manifest["executionConfig"],
            schema_path=schema_path,
            work_dir=paths["root"],
        )
        registry: dict[str, Any] = {
            "schemaVersion": 1,
            "protocol": REGISTRY_PROTOCOL,
            "status": "started_before_process",
            "campaignId": manifest["campaignId"],
            "unitId": unit_id,
            "unitManifestFileSha256": manifest_file_sha,
            "unitManifestSha256": manifest_sha,
            "scheduleFileSha256": schedule_file_sha,
            "scheduleSha256": schedule_sha,
            "sourceGitCommit": manifest["gitAnchor"]["commit"],
            "sourceGitTree": manifest["gitAnchor"]["tree"],
            "campaignGitCommit": expected_campaign_git_commit,
            "runtimeIdentitySha256": runtime_identity_sha,
            "executionEnvironmentSha256": canonical_digest(
                _execution_environment()
            ),
            "unitSha256": canonical_digest(dict(unit)),
            "promptSha256": unit["promptSha256"],
            "outputSchemaSha256": unit["outputSchemaSha256"],
            "runnerCodeSha256": sha256_file(Path(__file__).resolve()),
            "commandArgvSha256": canonical_digest(command),
            "commandArgumentCount": len(command),
            "semanticAttemptOrdinal": 1,
            "semanticRetryCount": 0,
            "transportRetryCount": 0,
        }
        registry["registrySha256"] = canonical_digest(registry)
        unit_receipt, result = _load_completed_unit(
            paths=paths, expected_registry=registry, unit=unit
        )
        completed_receipts.append(unit_receipt)
        completed_results.append(result)
    prediction_raw, observed_predictions_sha = _read_regular(
        predictions_path, label="scientific predictions"
    )
    expected_receipt, scientific_rows = _compose_campaign_receipt(
        manifest=manifest,
        manifest_file_sha=manifest_file_sha,
        manifest_sha=manifest_sha,
        schedule=schedule,
        schedule_file_sha=schedule_file_sha,
        schedule_sha=schedule_sha,
        campaign_git_commit=expected_campaign_git_commit,
        runtime_identity_sha256=runtime_identity_sha,
        units=units,
        receipts=completed_receipts,
        results=completed_results,
        predictions_sha=observed_predictions_sha,
    )
    _require(
        prediction_raw == _jsonl_payload(scientific_rows),
        "campaign prediction rows tamper",
    )
    _require(
        campaign_receipt == expected_receipt,
        "campaign receipt aggregate tamper",
    )
    return {
        "manifest": manifest,
        "schedule": schedule,
        "campaignReceipt": campaign_receipt,
        "unitReceipts": completed_receipts,
        "unitResults": completed_results,
        "scientificRows": scientific_rows,
        "runtimeIdentity": runtime_identity,
    }


def run_campaign(
    *,
    unit_manifest_path: Path,
    expected_unit_manifest_file_sha256: str,
    schedule_path: Path,
    expected_schedule_file_sha256: str,
    expected_campaign_git_commit: str,
    output_dir: Path,
    process_factory: Callable[..., Any] = subprocess.Popen,
    monotonic: Callable[[], float] = time.monotonic,
    source_anchor_verifier: Callable[..., Any] = verify_source_git_anchor,
    campaign_anchor_verifier: Callable[..., Any] = verify_campaign_git_anchor,
    runtime_identity_verifier: Callable[..., Any] = verify_runtime_identity,
) -> dict[str, Any]:
    _require(
        isinstance(expected_campaign_git_commit, str)
        and HEX40.fullmatch(expected_campaign_git_commit) is not None,
        "campaign Git commit format",
    )
    unresolved_output_dir = Path(output_dir)
    _require(not unresolved_output_dir.is_symlink(), "campaign output directory symlink")
    completed_receipt_candidate = unresolved_output_dir / "campaign_receipt.json"
    if os.path.lexists(completed_receipt_candidate):
        _require(
            not completed_receipt_candidate.is_symlink()
            and completed_receipt_candidate.is_file(),
            "campaign receipt path integrity",
        )
        validated = validate_completed_campaign(
            unit_manifest_path=unit_manifest_path,
            expected_unit_manifest_file_sha256=expected_unit_manifest_file_sha256,
            schedule_path=schedule_path,
            expected_schedule_file_sha256=expected_schedule_file_sha256,
            expected_campaign_git_commit=expected_campaign_git_commit,
            output_dir=output_dir,
            source_anchor_verifier=source_anchor_verifier,
            campaign_anchor_verifier=campaign_anchor_verifier,
            runtime_identity_verifier=runtime_identity_verifier,
        )
        return dict(validated["campaignReceipt"])
    manifest, manifest_file_sha, manifest_sha, units, manifest_root = (
        _validate_unit_manifest(
            unit_manifest_path,
            expected_file_sha256=expected_unit_manifest_file_sha256,
            source_anchor_verifier=source_anchor_verifier,
        )
    )
    schedule, schedule_file_sha, schedule_sha = _validate_schedule(
        schedule_path,
        expected_file_sha256=expected_schedule_file_sha256,
        manifest=manifest,
        manifest_file_sha256=manifest_file_sha,
        manifest_sha256=manifest_sha,
        units=units,
    )
    campaign_anchor_verifier(
        manifest_path=unit_manifest_path.resolve(),
        schedule_path=schedule_path.resolve(),
        source_commit=manifest["gitAnchor"]["commit"],
        expected_campaign_commit=expected_campaign_git_commit,
    )
    runtime_identity = _validate_runtime_identity(
        runtime_identity_verifier(manifest["executionConfig"])
    )
    _require(
        runtime_identity["executableSha256"]
        == manifest["executionConfig"]["codexExecutableSha256"],
        "runtime executable identity mismatch",
    )
    runtime_identity_sha = runtime_identity["identitySha256"]
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    campaign_receipt_path = output_dir / "campaign_receipt.json"
    predictions_path = output_dir / "scientific_predictions.jsonl"
    _require(
        not os.path.lexists(campaign_receipt_path)
        and not os.path.lexists(predictions_path),
        "incomplete campaign top-level artifacts",
    )

    receipts: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    for unit_id in schedule["orderedUnitIds"]:
        receipt, result, _called = _run_or_resume_unit(
            output_root=output_dir,
            campaign_id=str(manifest["campaignId"]),
            unit=units[unit_id],
            manifest_root=manifest_root,
            manifest_file_sha=manifest_file_sha,
            manifest_sha=manifest_sha,
            schedule_file_sha=schedule_file_sha,
            schedule_sha=schedule_sha,
            source_git_commit=manifest["gitAnchor"]["commit"],
            source_git_tree=manifest["gitAnchor"]["tree"],
            campaign_git_commit=expected_campaign_git_commit,
            runtime_identity_sha256=runtime_identity_sha,
            config=manifest["executionConfig"],
            code_hashes=manifest["codeHashes"],
            process_factory=process_factory,
            monotonic=monotonic,
        )
        receipts.append(receipt)
        results.append(result)
    _, scientific_rows = _compose_campaign_receipt(
        manifest=manifest,
        manifest_file_sha=manifest_file_sha,
        manifest_sha=manifest_sha,
        schedule=schedule,
        schedule_file_sha=schedule_file_sha,
        schedule_sha=schedule_sha,
        campaign_git_commit=expected_campaign_git_commit,
        runtime_identity_sha256=runtime_identity_sha,
        units=units,
        receipts=receipts,
        results=results,
        predictions_sha="0" * 64,
    )
    predictions_sha = _write_jsonl_exclusive(predictions_path, scientific_rows)
    campaign_receipt, _ = _compose_campaign_receipt(
        manifest=manifest,
        manifest_file_sha=manifest_file_sha,
        manifest_sha=manifest_sha,
        schedule=schedule,
        schedule_file_sha=schedule_file_sha,
        schedule_sha=schedule_sha,
        campaign_git_commit=expected_campaign_git_commit,
        runtime_identity_sha256=runtime_identity_sha,
        units=units,
        receipts=receipts,
        results=results,
        predictions_sha=predictions_sha,
    )
    _write_exclusive_json(campaign_receipt_path, campaign_receipt)
    return campaign_receipt


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    schedule = subparsers.add_parser("schedule")
    schedule.add_argument("--unit-manifest", type=Path, required=True)
    schedule.add_argument("--unit-manifest-file-sha256", required=True)
    schedule.add_argument("--output", type=Path, required=True)
    run = subparsers.add_parser("run")
    run.add_argument("--unit-manifest", type=Path, required=True)
    run.add_argument("--unit-manifest-file-sha256", required=True)
    run.add_argument("--schedule", type=Path, required=True)
    run.add_argument("--schedule-file-sha256", required=True)
    run.add_argument("--campaign-git-commit", required=True)
    run.add_argument("--output-dir", type=Path, required=True)
    run.add_argument("--execute-live", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.command == "schedule":
            result = build_schedule_manifest(
                unit_manifest_path=args.unit_manifest,
                expected_unit_manifest_file_sha256=args.unit_manifest_file_sha256,
                output_path=args.output,
            )
        else:
            if not args.execute_live:
                raise SingletonCampaignError(
                    "live execution requires the explicit --execute-live flag"
                )
            result = run_campaign(
                unit_manifest_path=args.unit_manifest,
                expected_unit_manifest_file_sha256=args.unit_manifest_file_sha256,
                schedule_path=args.schedule,
                expected_schedule_file_sha256=args.schedule_file_sha256,
                expected_campaign_git_commit=args.campaign_git_commit,
                output_dir=args.output_dir,
            )
    except (
        SingletonCampaignError,
        OSError,
        ValueError,
        subprocess.SubprocessError,
    ) as exc:
        print(json.dumps({"status": "rejected", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
