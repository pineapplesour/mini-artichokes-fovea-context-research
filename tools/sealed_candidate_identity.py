#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from tools.evaluated_experience_memory import skill_tree_sha256


REQUIRED_SEALED_RUNTIME_FILES = frozenset(
    {
        "tools/benchmark_provider.py",
        "tools/codex_home_failover.py",
        "tools/database_attestation.py",
        "tools/domain_evidence_mcp_server.py",
        "tools/evidence_gated_native_agent.py",
        "tools/finalize_universal_native_development_gate.py",
        "tools/resource_gate.py",
        "tools/run_calculation_benchmark.py",
        "tools/run_codex_home_pool.py",
        "tools/run_open_response_benchmark.py",
        "tools/run_unified_mcq_benchmark.py",
        "tools/score_open_responses.py",
        "tools/sealed_candidate_identity.py",
    }
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def runtime_identity_sha256(identity: dict[str, Any]) -> str:
    encoded = json.dumps(
        identity,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _repo_member(repo_root: Path, value: Any) -> tuple[Path | None, str]:
    root = Path(repo_root).resolve()
    raw = Path(str(value or ""))
    if not str(raw) or raw.is_absolute():
        return None, ""
    candidate = root / raw
    current = root
    for part in raw.parts:
        if part in {"", ".", ".."}:
            return None, ""
        current = current / part
        if current.is_symlink():
            return None, ""
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root):
        return None, ""
    return resolved, raw.as_posix()


def build_runtime_identity(
    *,
    repo_root: Path,
    sealed_at: str,
    approved_skill_paths: Iterable[Path],
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    datetime.fromisoformat(str(sealed_at))
    files: dict[str, str] = {}
    for relative in sorted(REQUIRED_SEALED_RUNTIME_FILES):
        path, normalized = _repo_member(root, relative)
        if path is None or not path.is_file():
            raise ValueError(f"required sealed runtime file missing or unsafe: {relative}")
        files[normalized] = file_sha256(path)

    skills: dict[str, str] = {}
    approved: list[str] = []
    for supplied in approved_skill_paths:
        path = Path(supplied).resolve()
        if not path.is_relative_to(root):
            raise ValueError(f"approved skill is outside repository: {supplied}")
        relative = path.relative_to(root).as_posix()
        checked, normalized = _repo_member(root, relative)
        if checked is None or not checked.is_dir():
            raise ValueError(f"approved skill missing or unsafe: {relative}")
        approved.append(normalized)
        skills[normalized] = skill_tree_sha256(checked)
    if len(approved) != len(set(approved)):
        raise ValueError("approved skill paths must be unique")
    return {
        "schemaVersion": 1,
        "sealedAt": str(sealed_at),
        "files": files,
        "approvedSkillPaths": approved,
        "skillTrees": skills,
    }


def validate_runtime_identity(
    *,
    spec: dict[str, Any],
    repo_root: Path,
    actual_approved_skill_paths: Iterable[Path],
) -> list[str]:
    blockers: list[str] = []
    schema_version = int(spec.get("schemaVersion") or 0)
    identity = spec.get("sealedRuntimeIdentity")
    if not isinstance(identity, dict):
        return ["sealed_runtime_identity_missing"] if schema_version >= 2 else []

    if int(identity.get("schemaVersion") or 0) != 1:
        blockers.append("sealed_runtime_identity_schema_invalid")
    sealed_at = str(identity.get("sealedAt") or "")
    try:
        datetime.fromisoformat(sealed_at)
    except ValueError:
        blockers.append("sealed_runtime_identity_time_invalid")
    if sealed_at != str(spec.get("frozenAt") or ""):
        blockers.append("sealed_runtime_identity_time_mismatch")

    files = identity.get("files") if isinstance(identity.get("files"), dict) else {}
    if set(files) != REQUIRED_SEALED_RUNTIME_FILES:
        blockers.append("sealed_runtime_file_set_mismatch")
    for relative, expected in sorted(files.items()):
        path, normalized = _repo_member(repo_root, relative)
        if normalized != relative or path is None or not path.is_file():
            blockers.append("sealed_runtime_file_missing_or_unsafe")
            continue
        if not _SHA256_RE.fullmatch(str(expected or "")) or file_sha256(path) != expected:
            blockers.append("sealed_runtime_file_hash_mismatch")

    candidate = spec.get("candidate") if isinstance(spec.get("candidate"), dict) else {}
    declared = identity.get("approvedSkillPaths")
    declared = [str(value) for value in declared] if isinstance(declared, list) else []
    candidate_declared = candidate.get("approvedSkillPaths")
    candidate_declared = [str(value) for value in candidate_declared] if isinstance(candidate_declared, list) else []
    actual: list[str] = []
    root = Path(repo_root).resolve()
    for supplied in actual_approved_skill_paths:
        path = Path(supplied).resolve()
        if not path.is_relative_to(root):
            blockers.append("actual_approved_skill_outside_repo")
            continue
        actual.append(path.relative_to(root).as_posix())
    if not declared or len(declared) != len(set(declared)):
        blockers.append("sealed_approved_skill_paths_invalid")
    if declared != candidate_declared:
        blockers.append("candidate_approved_skill_paths_mismatch")
    if declared != actual:
        blockers.append("runtime_approved_skill_paths_mismatch")

    skill_trees = identity.get("skillTrees") if isinstance(identity.get("skillTrees"), dict) else {}
    if set(skill_trees) != set(declared):
        blockers.append("sealed_skill_tree_set_mismatch")
    for relative, expected in sorted(skill_trees.items()):
        path, normalized = _repo_member(repo_root, relative)
        if normalized != relative or path is None or not path.is_dir():
            blockers.append("sealed_skill_tree_missing_or_unsafe")
            continue
        try:
            actual_digest = skill_tree_sha256(path)
        except ValueError:
            blockers.append("sealed_skill_tree_missing_or_unsafe")
            continue
        if not _SHA256_RE.fullmatch(str(expected or "")) or actual_digest != expected:
            blockers.append("sealed_skill_tree_hash_mismatch")
    return sorted(set(blockers))


def validate_development_invocation(
    *,
    spec: dict[str, Any],
    repo_root: Path,
    invocation: dict[str, Any],
) -> list[str]:
    """Bind parsed runner semantics to the frozen gate before any heavy work."""

    blockers: list[str] = []
    task = spec.get("task") if isinstance(spec.get("task"), dict) else {}
    candidate = spec.get("candidate") if isinstance(spec.get("candidate"), dict) else {}
    if int(spec.get("schemaVersion") or 0) < 2:
        blockers.append("sealed_gate_schema_too_old")
    if str(spec.get("status") or "") != "frozen_unrun":
        blockers.append("sealed_gate_not_runnable")

    root = Path(repo_root).resolve()

    def normalized_path(value: Any) -> str:
        return str(Path(str(value or "")).resolve())

    expected = {
        "publicPath": normalized_path(root / str(task.get("publicManifest") or "")),
        "outputDir": normalized_path(root / str(candidate.get("outputDir") or "")),
        "model": str(candidate.get("model") or ""),
        "reasoningEffort": str(candidate.get("reasoningEffort") or ""),
        "timeoutSeconds": float(candidate.get("maxCaseSeconds") or 0.0),
        "caseIds": [str(task.get("caseId") or "")],
        "maxCases": 1,
        "maxTotalCalls": int(candidate.get("maximumQuotaFailoverAttemptsAcrossResumes") or 0),
        "maxCallsThisInvocation": 1,
        "maxCaseTokens": int(candidate.get("maxCaseTokens") or 0),
        "discoverCodexHomeRoot": normalized_path(candidate.get("codexHomeDiscoveryRoot")),
        "explicitCodexHomes": [],
        "domainDbPath": normalized_path(candidate.get("domainDatabase")),
        "nativeAgent": True,
        "evidenceGatedVerification": True,
        "compactNativeSkillBriefing": bool(
            candidate.get("compactNativeSkillBriefingEnabled")
        ),
        "domainEvidenceMcp": True,
        "webSearch": False,
        "hostDomainPrefetch": False,
        "reviewPass": False,
        "hypothesisAdjudication": False,
        "publicProductContext": False,
        "singlePassSelfVerify": False,
        "preserveDomainClassification": False,
        "promotedDomainClassificationRoute": False,
        "includeNeedsRewrite": False,
        "allowFixtureDb": False,
        "calculationTools": None,
        "allowExistingSwapSingleNativeEvidenceTask": True,
        "otherExistingSwapOverrides": False,
    }
    for key, expected_value in expected.items():
        if invocation.get(key) != expected_value:
            blockers.append(f"sealed_invocation_{key}_mismatch")
    if not isinstance(invocation.get("resume"), bool):
        blockers.append("sealed_invocation_resume_invalid")
    return sorted(set(blockers))
