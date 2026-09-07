#!/usr/bin/env python3
"""Prepare, run, resume, and validate sealed budgeted-ICR campaigns.

The runner supports two frozen profiles:

* ``icr5_one_cycle_self_improve``: initial -> suggest -> revise -> memory ->
  self-improve.  This is the causally complete five-call budgeted baseline.
* ``budgeted_icr4_memory_revision``: initial -> suggest -> memory -> final
  revision.  Memory is produced from both the initial answer and suggestions.
* ``test37_architecture_icr10``: the historical standalone test37 *call graph*:
  one initial draft followed by three suggest/revise/memory cycles (ten calls).
  Its prompts are task-adapted and its Codex runtime is not historically exact.

Every stage/shard is a fresh ephemeral Codex invocation.  Only public inputs
and hash-bound prior-stage artifacts are mounted.  A completed stage can be
resumed only after its receipt, trace policy, inputs, and output are rechecked.
Transport failures may be retried; schema, policy, or semantic-contract
failures are terminal for that campaign.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import benchmark_provider
from tools import run_blind_pairwise_veto_agent as sealed_runner
from tools import run_plain_codex_file_agent as plain_runner


PROTOCOL = "mini_artichokes_budgeted_icr_v1"
DEFAULT_MODEL = "gpt-5.6-luna"
DEFAULT_REASONING_EFFORT = "high"
DEFAULT_VERBOSITY = "low"
SERVICE_TIER = "default"
ALLOWED_CONCLUSIONS = ("인용됨", "기각")
EXECUTION_CONFIG = {
    "model": DEFAULT_MODEL,
    "reasoningEffort": DEFAULT_REASONING_EFFORT,
    "verbosity": DEFAULT_VERBOSITY,
    "serviceTier": SERVICE_TIER,
    "nativeWebSearch": False,
    "mcp": False,
    "skills": False,
    "multiAgent": False,
    "networkCapableShell": False,
    "freshEphemeralInvocationPerStageShard": True,
}
OUTPUT_BY_KIND = {
    "candidate": "candidate.jsonl",
    "suggestions": "suggestions.jsonl",
    "memory": "memory.jsonl",
}


def _stage(
    name: str,
    role: str,
    output_kind: str,
    dependencies: dict[str, int] | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "role": role,
        "outputKind": output_kind,
        "dependencies": dependencies or {},
    }


PROFILES: dict[str, dict[str, Any]] = {
    "budgeted_icr4_memory_revision": {
        "description": "Causally complete four-call memory-before-final-revision ICR baseline.",
        "stages": [
            _stage("initial", "main-generator", "candidate"),
            _stage("suggest-1", "iterative-agent", "suggestions", {"candidate": 1}),
            _stage("memory-1", "memory-agent", "memory", {"candidate": 1, "suggestions": 2}),
            _stage(
                "final-revise", "main-generator", "candidate", {"candidate": 1, "suggestions": 2, "memory": 3}
            ),
        ],
        "terminalCandidateStage": 4,
        "callGraphExact": False,
        "promptsTaskAdapted": True,
        "runtimeExact": False,
    },
    "icr5_one_cycle_self_improve": {
        "description": "One suggest/revise/memory cycle followed by memory-conditioned self-improvement.",
        "stages": [
            _stage("initial", "main-generator", "candidate"),
            _stage("suggest-1", "iterative-agent", "suggestions", {"candidate": 1}),
            _stage("revise-1", "main-generator", "candidate", {"candidate": 1, "suggestions": 2}),
            _stage("memory-1", "memory-agent", "memory", {"candidate": 3, "suggestions": 2}),
            _stage("self-improve", "main-generator", "candidate", {"candidate": 3, "memory": 4}),
        ],
        "terminalCandidateStage": 5,
        "callGraphExact": False,
        "promptsTaskAdapted": True,
        "runtimeExact": False,
    },
    "test37_architecture_icr10": {
        "description": "Task-adapted reproduction of the historical test37 call graph only.",
        "stages": [
            _stage("initial", "main-generator", "candidate"),
            _stage("suggest-1", "iterative-agent", "suggestions", {"candidate": 1}),
            _stage("revise-1", "main-generator", "candidate", {"candidate": 1, "suggestions": 2}),
            _stage("memory-1", "memory-agent", "memory", {"candidate": 3, "suggestions": 2}),
            _stage("suggest-2", "iterative-agent", "suggestions", {"candidate": 3, "memory": 4}),
            _stage(
                "revise-2", "main-generator", "candidate", {"candidate": 3, "suggestions": 5, "memory": 4}
            ),
            _stage(
                "memory-2", "memory-agent", "memory", {"candidate": 6, "suggestions": 5, "memory": 4}
            ),
            _stage("suggest-3", "iterative-agent", "suggestions", {"candidate": 6, "memory": 7}),
            _stage(
                "revise-3", "main-generator", "candidate", {"candidate": 6, "suggestions": 8, "memory": 7}
            ),
            _stage(
                "memory-3", "memory-agent", "memory", {"candidate": 9, "suggestions": 8, "memory": 7}
            ),
        ],
        "terminalCandidateStage": 9,
        "callGraphExact": True,
        "promptsTaskAdapted": True,
        "runtimeExact": False,
    },
}

FROZEN_IMPLEMENTATION_PATHS = (
    Path(__file__).resolve(),
    Path(plain_runner.__file__).resolve(),
    Path(sealed_runner.__file__).resolve(),
    Path(benchmark_provider.__file__).resolve(),
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
    raw_lines = path.read_text(encoding="utf-8").split("\n")
    for line_number, raw in enumerate(raw_lines, start=1):
        if not raw:
            if line_number == len(raw_lines):
                continue
            raise ValueError(f"blank JSONL line {line_number}: {path}")
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError(f"non-object JSONL line {line_number}: {path}")
        rows.append(value)
    return rows


def write_json_exclusive(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def write_jsonl_exclusive(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def self_hash(value: dict[str, Any], key: str) -> str:
    return canonical_digest({name: item for name, item in value.items() if name != key})


def _implementation_hashes() -> dict[str, str]:
    return {str(path): sha256_file(path) for path in FROZEN_IMPLEMENTATION_PATHS}


def _validate_public_rows(rows: list[dict[str, Any]]) -> list[str]:
    if not rows:
        raise ValueError("public JSONL must contain at least one row")
    ids: list[str] = []
    for index, row in enumerate(rows, start=1):
        case_id = row.get("id")
        prompt = row.get("prompt")
        if not isinstance(case_id, str) or not case_id.strip():
            raise ValueError(f"public row {index} has invalid id")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError(f"public row {index} has invalid prompt")
        ids.append(case_id)
    if len(ids) != len(set(ids)):
        raise ValueError("public IDs must be unique")
    return ids


def _deterministic_shards(rows: list[dict[str, Any]], shard_size: int, seed: str) -> list[list[dict[str, Any]]]:
    if shard_size <= 0:
        raise ValueError("shard_size must be positive")
    ranked = sorted(
        rows,
        key=lambda row: (
            hashlib.sha256(f"{seed}\0{row['id']}".encode("utf-8")).hexdigest(),
            str(row["id"]),
        ),
    )
    return [ranked[offset : offset + shard_size] for offset in range(0, len(ranked), shard_size)]


def prepare_campaign(
    *,
    public_path: Path,
    campaign_dir: Path,
    profile: str,
    shard_size: int,
    shard_seed: str,
    timeout_seconds: int,
    max_transport_attempts: int,
) -> dict[str, Any]:
    public_path = public_path.resolve()
    campaign_dir = campaign_dir.resolve()
    if profile not in PROFILES:
        raise ValueError(f"unsupported ICR profile: {profile}")
    if timeout_seconds <= 0 or not 1 <= max_transport_attempts <= 5:
        raise ValueError("timeout must be positive and max transport attempts must be 1..5")
    if campaign_dir.exists():
        raise FileExistsError(f"refusing to overwrite campaign directory: {campaign_dir}")
    rows = load_jsonl(public_path)
    ids = _validate_public_rows(rows)
    shards = _deterministic_shards(rows, shard_size, shard_seed)
    campaign_dir.mkdir(parents=True)
    input_dir = campaign_dir / "input"
    input_dir.mkdir()
    (campaign_dir / "shards").mkdir()
    (campaign_dir / "final").mkdir()
    (input_dir / "public.jsonl").write_bytes(public_path.read_bytes())
    write_json_exclusive(input_dir / "expected_ids.json", {"count": len(ids), "ids": ids})

    shard_manifest: list[dict[str, Any]] = []
    for index, shard_rows in enumerate(shards):
        shard_id = f"shard-{index:04d}"
        shard_dir = campaign_dir / "shards" / shard_id
        shard_dir.mkdir()
        questions = shard_dir / "questions.jsonl"
        write_jsonl_exclusive(questions, shard_rows)
        shard_ids = [str(row["id"]) for row in shard_rows]
        expected = shard_dir / "expected_ids.json"
        write_json_exclusive(expected, {"count": len(shard_ids), "ids": shard_ids})
        shard_manifest.append(
            {
                "shardId": shard_id,
                "rows": len(shard_rows),
                "ids": shard_ids,
                "idsSha256": canonical_digest(shard_ids),
                "questionsSha256": sha256_file(questions),
                "expectedIdsFileSha256": sha256_file(expected),
            }
        )

    freeze: dict[str, Any] = {
        "schemaVersion": 1,
        "status": "prepared_no_model_calls",
        "protocol": PROTOCOL,
        "profile": profile,
        "profileSpec": PROFILES[profile],
        "publicPath": "input/public.jsonl",
        "publicSha256": sha256_file(input_dir / "public.jsonl"),
        "expectedIdsPath": "input/expected_ids.json",
        "expectedIdsFileSha256": sha256_file(input_dir / "expected_ids.json"),
        "expectedIdsSha256": canonical_digest(ids),
        "inventory": {"rows": len(rows), "shards": len(shards), "stagesPerShard": len(PROFILES[profile]["stages"])},
        "sharding": {
            "scheme": "sha256(seed-nul-id)-sort-then-contiguous-v1",
            "seed": shard_seed,
            "seedSha256": hashlib.sha256(shard_seed.encode("utf-8")).hexdigest(),
            "shardSize": shard_size,
            "manifest": shard_manifest,
            "manifestSha256": canonical_digest(shard_manifest),
        },
        "executionConfig": dict(EXECUTION_CONFIG),
        "runPolicy": {
            "timeoutSeconds": timeout_seconds,
            "maxTransportAttempts": max_transport_attempts,
        },
        "deterministicShardReuseContract": {
            "function": "sha256(seed + NUL + id), ascending digest then ascending id, contiguous chunks",
            "requiredInputs": ["identical public ID set", "identical shardSeed", "identical shardSize"],
            "crossArmInvariant": "copy sharding.manifest verbatim and require manifestSha256 equality",
        },
        "implementationHashes": _implementation_hashes(),
    }
    freeze["freezeSha256"] = self_hash(freeze, "freezeSha256")
    write_json_exclusive(campaign_dir / "freeze.json", freeze)
    return freeze


def verify_freeze(campaign_dir: Path) -> dict[str, Any]:
    campaign_dir = campaign_dir.resolve()
    freeze = load_json(campaign_dir / "freeze.json")
    errors: list[str] = []
    if freeze.get("protocol") != PROTOCOL:
        errors.append("protocol_mismatch")
    profile = str(freeze.get("profile") or "")
    if profile not in PROFILES or freeze.get("profileSpec") != PROFILES.get(profile):
        errors.append("profile_spec_mismatch")
    if freeze.get("freezeSha256") != self_hash(freeze, "freezeSha256"):
        errors.append("freeze_self_hash_mismatch")
    if freeze.get("executionConfig") != EXECUTION_CONFIG:
        errors.append("execution_config_mismatch")
    run_policy = freeze.get("runPolicy")
    if (
        not isinstance(run_policy, dict)
        or not isinstance(run_policy.get("timeoutSeconds"), int)
        or run_policy.get("timeoutSeconds", 0) <= 0
        or not isinstance(run_policy.get("maxTransportAttempts"), int)
        or not 1 <= run_policy.get("maxTransportAttempts", 0) <= 5
    ):
        errors.append("run_policy_invalid")
    if freeze.get("implementationHashes") != _implementation_hashes():
        errors.append("implementation_hash_mismatch")
    public = campaign_dir / str(freeze.get("publicPath") or "")
    expected_path = campaign_dir / str(freeze.get("expectedIdsPath") or "")
    if not public.is_file() or sha256_file(public) != freeze.get("publicSha256"):
        errors.append("public_hash_mismatch")
        rows: list[dict[str, Any]] = []
        ids: list[str] = []
    else:
        rows = load_jsonl(public)
        ids = _validate_public_rows(rows)
    if not expected_path.is_file() or sha256_file(expected_path) != freeze.get("expectedIdsFileSha256"):
        errors.append("expected_ids_file_hash_mismatch")
    elif load_json(expected_path) != {"count": len(ids), "ids": ids}:
        errors.append("expected_ids_content_mismatch")
    if canonical_digest(ids) != freeze.get("expectedIdsSha256"):
        errors.append("expected_ids_hash_mismatch")
    manifest = freeze.get("sharding", {}).get("manifest") if isinstance(freeze.get("sharding"), dict) else None
    if not isinstance(manifest, list) or canonical_digest(manifest) != freeze.get("sharding", {}).get("manifestSha256"):
        errors.append("shard_manifest_hash_mismatch")
        manifest = []
    observed_ids: list[str] = []
    for entry in manifest:
        if not isinstance(entry, dict):
            errors.append("shard_manifest_entry_invalid")
            continue
        shard_dir = campaign_dir / "shards" / str(entry.get("shardId") or "")
        questions = shard_dir / "questions.jsonl"
        expected = shard_dir / "expected_ids.json"
        if not questions.is_file() or sha256_file(questions) != entry.get("questionsSha256"):
            errors.append(f"{entry.get('shardId')}:questions_hash_mismatch")
            continue
        shard_rows = load_jsonl(questions)
        shard_ids = _validate_public_rows(shard_rows)
        if shard_ids != entry.get("ids") or canonical_digest(shard_ids) != entry.get("idsSha256"):
            errors.append(f"{entry.get('shardId')}:ids_mismatch")
        if not expected.is_file() or sha256_file(expected) != entry.get("expectedIdsFileSha256"):
            errors.append(f"{entry.get('shardId')}:expected_ids_hash_mismatch")
        elif load_json(expected) != {"count": len(shard_ids), "ids": shard_ids}:
            errors.append(f"{entry.get('shardId')}:expected_ids_content_mismatch")
        observed_ids.extend(shard_ids)
    if sorted(observed_ids) != sorted(ids) or len(observed_ids) != len(set(observed_ids)):
        errors.append("shard_partition_not_exact")
    if errors:
        raise ValueError("frozen ICR campaign failed closed: " + ", ".join(dict.fromkeys(errors)))
    return freeze


def _stage_dir(campaign_dir: Path, shard_id: str, stage_number: int, stage_name: str) -> Path:
    return campaign_dir / "shards" / shard_id / "stages" / f"{stage_number:02d}-{stage_name}"


def _accepted_output_path(stage_dir: Path, receipt: dict[str, Any]) -> Path:
    relative = receipt.get("acceptedOutputPath")
    if not isinstance(relative, str) or not relative:
        raise ValueError(f"stage receipt lacks acceptedOutputPath: {stage_dir}")
    path = stage_dir / relative
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def _dependency_artifacts(
    campaign_dir: Path,
    shard_id: str,
    stages: list[dict[str, Any]],
    stage: dict[str, Any],
) -> dict[str, Path]:
    artifacts: dict[str, Path] = {}
    for alias, source_number in stage["dependencies"].items():
        source = stages[source_number - 1]
        source_dir = _stage_dir(campaign_dir, shard_id, source_number, source["name"])
        receipt = load_json(source_dir / "stage_receipt.json")
        if receipt.get("status") != "accepted":
            raise ValueError(f"dependency stage is not accepted: {source_dir}")
        artifacts[alias] = _accepted_output_path(source_dir, receipt)
    return artifacts


def _instruction_text(stage: dict[str, Any], profile: str, prior_names: list[str]) -> str:
    common = f"""# Sealed budgeted ICR stage

Profile: `{profile}`
Stage: `{stage['name']}`
Role: `{stage['role']}`

Read `input/questions.jsonl` and `input/expected_ids.json` completely. Process
every ID exactly once and in the exact input order. Treat each ID independently;
never transfer facts, conclusions, suggestions, or memory between cases.

Do not use web search, network access, MCP, skills, external sources, hidden
labels, other experimental arms, or any path outside `input/` and `output/`.
Only the staged public cases and hash-bound prior artifacts are evidence.
"""
    output = OUTPUT_BY_KIND[stage["outputKind"]]
    if stage["name"] == "initial":
        task = """Act as the Main Generator. Solve each case from the supplied facts alone. Predict the case outcome and give a concise, evidence-grounded rationale."""
    elif stage["name"].startswith("suggest"):
        task = """Act as the ICR Iterative Agent. For each matching candidate, give concrete corrections and rigor improvements, but do not write a replacement final answer. Do not invent a flaw: if no supported issue exists, explicitly recommend preserving the candidate."""
    elif stage["name"].startswith("revise") or stage["name"] == "final-revise":
        task = """Act as the Main Generator. Revise each candidate using only suggestions you independently verify against that case. Preserve correct work and reject unsupported criticism."""
    elif stage["name"].startswith("memory"):
        task = """Act as the Memory Agent. For each ID compress persistent case constraints, key decisions, applied suggestions, and critical pitfalls into at most eight short bullets. Do not transfer memory across IDs."""
    elif stage["name"] == "self-improve":
        task = """Act as the Main Generator. Perform a final independent self-check using the matching candidate and memory. Improve the answer only when supported by the case; preserve correct work."""
    else:
        raise ValueError(f"unsupported stage: {stage['name']}")
    if stage["outputKind"] == "candidate":
        contract = (
            "Write `output/candidate.jsonl`: one object per line with exactly `id`, `conclusion`, and `reasoning`. "
            "`conclusion` must be exactly `인용됨` or `기각`; `reasoning` must be a non-empty string."
        )
    elif stage["outputKind"] == "suggestions":
        contract = (
            "Write `output/suggestions.jsonl`: one object per line with exactly `id` and `suggestions`; "
            "`suggestions` must be a non-empty string and must not contain a replacement answer field."
        )
    else:
        contract = (
            "Write `output/memory.jsonl`: one object per line with exactly `id` and `memory`; "
            "`memory` must be a non-empty string."
        )
    inputs = ", ".join(f"`input/{name}.jsonl`" for name in prior_names) or "no prior-stage files"
    return common + f"\nPrior-stage files: {inputs}.\n\n{task}\n\n{contract}\nOutput nothing else except `output/last_message.txt` created by the runtime.\n"


def _prepare_stage_bundle(
    *,
    campaign_dir: Path,
    freeze: dict[str, Any],
    shard: dict[str, Any],
    stage_number: int,
    stage: dict[str, Any],
) -> tuple[Path, dict[str, Any]]:
    stages = freeze["profileSpec"]["stages"]
    stage_dir = _stage_dir(campaign_dir, shard["shardId"], stage_number, stage["name"])
    if stage_dir.exists():
        raise FileExistsError(f"refusing to overwrite existing stage bundle: {stage_dir}")
    input_dir = stage_dir / "input"
    input_dir.mkdir(parents=True)
    source_questions = campaign_dir / "shards" / shard["shardId"] / "questions.jsonl"
    source_expected = campaign_dir / "shards" / shard["shardId"] / "expected_ids.json"
    shutil.copy2(source_questions, input_dir / "questions.jsonl")
    shutil.copy2(source_expected, input_dir / "expected_ids.json")
    dependencies = _dependency_artifacts(campaign_dir, shard["shardId"], stages, stage)
    prior_hashes: dict[str, str] = {}
    for alias, source in dependencies.items():
        destination = input_dir / f"{alias}.jsonl"
        shutil.copy2(source, destination)
        prior_hashes[alias] = sha256_file(destination)
    instructions = input_dir / "RUN_INSTRUCTIONS.md"
    instructions.write_text(
        _instruction_text(stage, freeze["profile"], sorted(dependencies)), encoding="utf-8", newline="\n"
    )
    input_hashes = {
        "questions": sha256_file(input_dir / "questions.jsonl"),
        "expectedIds": sha256_file(input_dir / "expected_ids.json"),
        "instructions": sha256_file(instructions),
        **{f"prior:{name}": digest for name, digest in prior_hashes.items()},
    }
    request: dict[str, Any] = {
        "schemaVersion": 1,
        "protocol": PROTOCOL,
        "freezeSha256": freeze["freezeSha256"],
        "profile": freeze["profile"],
        "runPolicy": freeze["runPolicy"],
        "shardId": shard["shardId"],
        "stageNumber": stage_number,
        "stage": stage,
        "expectedIdsSha256": shard["idsSha256"],
        "inputFileSha256": input_hashes,
        "outputFile": OUTPUT_BY_KIND[stage["outputKind"]],
    }
    request["requestSha256"] = self_hash(request, "requestSha256")
    write_json_exclusive(stage_dir / "stage_request.json", request)
    write_json_exclusive(input_dir / "stage_request.json", request)
    return stage_dir, request


def _validate_stage_output(path: Path, kind: str, expected_ids: list[str]) -> dict[str, Any]:
    errors: list[str] = []
    try:
        rows = load_jsonl(path)
    except Exception as exc:
        return {"passed": False, "errors": [f"output_parse_error:{type(exc).__name__}:{exc}"], "rows": 0}
    observed = [row.get("id") for row in rows]
    if observed != expected_ids:
        errors.append("output_ids_or_order_mismatch")
    expected_keys = {
        "candidate": {"id", "conclusion", "reasoning"},
        "suggestions": {"id", "suggestions"},
        "memory": {"id", "memory"},
    }[kind]
    for index, row in enumerate(rows, start=1):
        if set(row) != expected_keys:
            errors.append(f"row_{index}_keys_mismatch")
            continue
        if kind == "candidate":
            if row.get("conclusion") not in ALLOWED_CONCLUSIONS:
                errors.append(f"row_{index}_invalid_conclusion")
            if not isinstance(row.get("reasoning"), str) or not row["reasoning"].strip():
                errors.append(f"row_{index}_empty_reasoning")
        else:
            field = kind
            if not isinstance(row.get(field), str) or not row[field].strip():
                errors.append(f"row_{index}_empty_{field}")
    return {
        "passed": not errors,
        "errors": list(dict.fromkeys(errors)),
        "rows": len(rows),
        "outputSha256": sha256_file(path) if path.is_file() else None,
    }


def _trace_usage(audit: dict[str, Any]) -> dict[str, int]:
    underlying = audit.get("underlyingAudit") if isinstance(audit.get("underlyingAudit"), dict) else {}
    trace = underlying.get("trace") if isinstance(underlying.get("trace"), dict) else {}
    usage = trace.get("tokenUsage") if isinstance(trace.get("tokenUsage"), dict) else {}
    return {key: int(value) for key, value in usage.items() if isinstance(value, (int, float)) and value >= 0}


def _recompute_attempt_evidence(
    *,
    stage_dir: Path,
    request: dict[str, Any],
    attempt_number: int,
    return_code: int,
    timed_out: bool,
) -> dict[str, Any]:
    """Derive auditable attempt evidence solely from sealed files and exit facts."""
    attempt_dir = stage_dir / "attempts" / f"attempt-{attempt_number:02d}"
    output_dir = attempt_dir / "output"
    trace_path = attempt_dir / "codex_trace.jsonl"
    stderr_path = attempt_dir / "codex_stderr.txt"
    audit = sealed_runner.audit_veto_trace(
        trace_path=trace_path,
        questions_path=stage_dir / "input/questions.jsonl",
        return_code=return_code,
        native_web_search=False,
    )
    if timed_out:
        audit["violations"] = list(audit.get("violations") or []) + ["codex_process_timeout"]
        audit["passed"] = False
    expected_ids = load_json(stage_dir / "input/expected_ids.json")["ids"]
    output_path = output_dir / str(request["outputFile"])
    validation = _validate_stage_output(output_path, request["stage"]["outputKind"], expected_ids)
    output_names = sorted(path.name for path in output_dir.iterdir()) if output_dir.is_dir() else []
    unexpected = sorted(set(output_names) - {str(request["outputFile"]), "last_message.txt"})
    if unexpected:
        validation["errors"] = list(validation.get("errors") or []) + ["unexpected_output_files"]
        validation["passed"] = False
    last_message = output_dir / "last_message.txt"
    if not last_message.is_file():
        validation["errors"] = list(validation.get("errors") or []) + ["last_message_missing"]
        validation["passed"] = False
    transport_failure = bool(timed_out or return_code != 0)
    accepted = bool(not transport_failure and audit.get("passed") and validation.get("passed"))
    return {
        "status": "accepted" if accepted else ("transport_failure" if transport_failure else "rejected"),
        "policyAudit": audit,
        "outputValidation": validation,
        "tokenUsage": _trace_usage(audit),
        "artifacts": {
            "traceSha256": sha256_file(trace_path) if trace_path.is_file() else None,
            "stderrSha256": sha256_file(stderr_path) if stderr_path.is_file() else None,
            "outputSha256": sha256_file(output_path) if output_path.is_file() else None,
            "lastMessageSha256": sha256_file(last_message) if last_message.is_file() else None,
            "outputFileNames": output_names,
        },
        "outputRelativePath": str(output_path.relative_to(stage_dir)) if output_path.is_file() else None,
    }


def _invoke_attempt(
    *,
    stage_dir: Path,
    request: dict[str, Any],
    codex_home: Path,
    timeout_seconds: int,
    attempt_number: int,
    popen_factory: Callable[..., Any] = subprocess.Popen,
) -> dict[str, Any]:
    attempt_dir = stage_dir / "attempts" / f"attempt-{attempt_number:02d}"
    output_dir = attempt_dir / "output"
    output_dir.mkdir(parents=True)
    trace_path = attempt_dir / "codex_trace.jsonl"
    stderr_path = attempt_dir / "codex_stderr.txt"
    command = sealed_runner.build_codex_command(
        input_dir=stage_dir / "input",
        output_dir=output_dir,
        codex_home=codex_home,
        model=DEFAULT_MODEL,
        reasoning_effort=DEFAULT_REASONING_EFFORT,
        verbosity=DEFAULT_VERBOSITY,
        native_web_search=False,
    )
    sealed_runner.verify_tool_free_command(command)
    prompt = (
        "Read input/RUN_INSTRUCTIONS.md and input/stage_request.json completely, verify every staged prior file, "
        "process every expected ID exactly once, and write the required complete output JSONL. Use the shell only "
        "for local input/output file management. Do not use network access, web, MCP, skills, or other paths."
    )
    started_at = utc_now()
    started = time.monotonic()
    timed_out = False
    with trace_path.open("x", encoding="utf-8") as trace, stderr_path.open("x", encoding="utf-8") as stderr:
        process = popen_factory(
            command,
            stdin=subprocess.PIPE,
            stdout=trace,
            stderr=stderr,
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
    elapsed = round(time.monotonic() - started, 3)
    evidence = _recompute_attempt_evidence(
        stage_dir=stage_dir,
        request=request,
        attempt_number=attempt_number,
        return_code=return_code,
        timed_out=timed_out,
    )
    return {
        "attemptNumber": attempt_number,
        "startedAtUtc": started_at,
        "endedAtUtc": utc_now(),
        "elapsedSec": elapsed,
        "exitCode": return_code,
        "timedOut": timed_out,
        "codexCommandSha256": canonical_digest(command),
        **evidence,
    }


def _verify_stage_receipt(
    stage_dir: Path, request: dict[str, Any], *, expected_codex_home: Path | None = None
) -> dict[str, Any]:
    receipt = load_json(stage_dir / "stage_receipt.json")
    failures: list[str] = []
    if receipt.get("receiptSha256") != self_hash(receipt, "receiptSha256"):
        failures.append("receipt_self_hash_mismatch")
    if receipt.get("status") != "accepted":
        failures.append("receipt_not_accepted")
    if receipt.get("requestSha256") != request.get("requestSha256"):
        failures.append("request_hash_mismatch")
    if receipt.get("executionConfig") != EXECUTION_CONFIG:
        failures.append("execution_config_mismatch")
    if receipt.get("runPolicy") != request.get("runPolicy"):
        failures.append("run_policy_mismatch")
    if expected_codex_home is not None and receipt.get("codexHomePath") != str(expected_codex_home.resolve()):
        failures.append("codex_home_path_mismatch")
    request_path = stage_dir / "stage_request.json"
    mounted_request_path = stage_dir / "input/stage_request.json"
    if (
        load_json(request_path) != request
        or not mounted_request_path.is_file()
        or load_json(mounted_request_path) != request
        or request.get("requestSha256") != self_hash(request, "requestSha256")
    ):
        failures.append("stage_request_tampered")
    for name, expected_hash in request.get("inputFileSha256", {}).items():
        relative = name.split(":", 1)[1] + ".jsonl" if name.startswith("prior:") else {
            "questions": "questions.jsonl",
            "expectedIds": "expected_ids.json",
            "instructions": "RUN_INSTRUCTIONS.md",
        }[name]
        path = stage_dir / "input" / relative
        if not path.is_file() or sha256_file(path) != expected_hash:
            failures.append(f"input_hash_mismatch:{name}")
    accepted_number = receipt.get("acceptedAttempt")
    attempts = receipt.get("attempts") if isinstance(receipt.get("attempts"), list) else []
    if [item.get("attemptNumber") for item in attempts] != list(range(1, len(attempts) + 1)):
        failures.append("attempt_number_sequence_mismatch")
    recomputed_token_totals: dict[str, int] = {}
    accepted_attempts: list[dict[str, Any]] = []
    for attempt in attempts:
        attempt_number = attempt.get("attemptNumber")
        if not isinstance(attempt_number, int):
            failures.append("attempt_number_invalid")
            continue
        if not isinstance(attempt.get("exitCode"), int) or not isinstance(attempt.get("timedOut"), bool):
            failures.append(f"attempt_{attempt_number}_exit_facts_invalid")
            continue
        try:
            evidence = _recompute_attempt_evidence(
                stage_dir=stage_dir,
                request=request,
                attempt_number=attempt_number,
                return_code=attempt["exitCode"],
                timed_out=attempt["timedOut"],
            )
        except Exception as exc:
            failures.append(f"attempt_{attempt_number}_evidence_recompute_failed:{type(exc).__name__}")
            continue
        for key in (
            "status",
            "policyAudit",
            "outputValidation",
            "tokenUsage",
            "artifacts",
            "outputRelativePath",
        ):
            if attempt.get(key) != evidence[key]:
                failures.append(f"attempt_{attempt_number}_{key}_mismatch")
        for key, value in evidence["tokenUsage"].items():
            recomputed_token_totals[key] = recomputed_token_totals.get(key, 0) + int(value)
        if evidence["status"] == "accepted":
            accepted_attempts.append(attempt)
    if (
        len(accepted_attempts) != 1
        or accepted_attempts[0].get("attemptNumber") != accepted_number
        or accepted_attempts[-1] is not attempts[-1]
        or any(item.get("status") != "transport_failure" for item in attempts[:-1])
    ):
        failures.append("accepted_attempt_mismatch")
    elif receipt.get("acceptedOutputPath") != accepted_attempts[0].get("outputRelativePath"):
        failures.append("accepted_output_path_mismatch")
    elapsed_values = [item.get("elapsedSec") for item in attempts]
    if not all(isinstance(value, (int, float)) and value >= 0 for value in elapsed_values):
        failures.append("attempt_elapsed_invalid")
    else:
        recomputed_elapsed = round(sum(float(value) for value in elapsed_values), 3)
        if receipt.get("elapsedSecAllAttempts") != recomputed_elapsed:
            failures.append("stage_elapsed_total_mismatch")
    if receipt.get("semanticAcceptedResponses") != 1:
        failures.append("stage_semantic_count_mismatch")
    if receipt.get("actualModelInvocations") != len(attempts):
        failures.append("stage_invocation_count_mismatch")
    if receipt.get("transportRetryCount") != max(0, len(attempts) - 1):
        failures.append("stage_retry_count_mismatch")
    if receipt.get("tokenUsageAllAttempts") != recomputed_token_totals:
        failures.append("stage_token_total_mismatch")
    if failures:
        raise ValueError(f"stage resume validation failed closed ({stage_dir}): " + ", ".join(failures))
    return receipt


def _run_stage(
    *,
    stage_dir: Path,
    request: dict[str, Any],
    codex_home: Path,
    timeout_seconds: int,
    max_transport_attempts: int,
    popen_factory: Callable[..., Any],
) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    for attempt_number in range(1, max_transport_attempts + 1):
        attempt = _invoke_attempt(
            stage_dir=stage_dir,
            request=request,
            codex_home=codex_home,
            timeout_seconds=timeout_seconds,
            attempt_number=attempt_number,
            popen_factory=popen_factory,
        )
        attempts.append(attempt)
        if attempt["status"] == "accepted":
            break
        if attempt["status"] != "transport_failure":
            break
    accepted = next((attempt for attempt in attempts if attempt["status"] == "accepted"), None)
    totals: dict[str, int] = {}
    for attempt in attempts:
        for key, value in attempt.get("tokenUsage", {}).items():
            totals[key] = totals.get(key, 0) + int(value)
    receipt: dict[str, Any] = {
        "schemaVersion": 1,
        "status": "accepted" if accepted else "incomplete",
        "protocol": PROTOCOL,
        "requestSha256": request["requestSha256"],
        "executionConfig": dict(EXECUTION_CONFIG),
        "runPolicy": dict(request["runPolicy"]),
        "codexHomePath": str(codex_home.resolve()),
        "semanticAcceptedResponses": 1 if accepted else 0,
        "actualModelInvocations": len(attempts),
        "acceptedAttempt": accepted["attemptNumber"] if accepted else None,
        "acceptedOutputPath": accepted["outputRelativePath"] if accepted else None,
        "transportRetryCount": max(0, len(attempts) - 1),
        "tokenUsageAllAttempts": totals,
        "elapsedSecAllAttempts": round(sum(float(item["elapsedSec"]) for item in attempts), 3),
        "attempts": attempts,
    }
    receipt["receiptSha256"] = self_hash(receipt, "receiptSha256")
    write_json_exclusive(stage_dir / "stage_receipt.json", receipt)
    if not accepted:
        raise RuntimeError(f"ICR stage did not produce an accepted response: {stage_dir}")
    return receipt


def _finalize_campaign(campaign_dir: Path, freeze: dict[str, Any], stage_receipts: list[dict[str, Any]]) -> dict[str, Any]:
    final_dir = campaign_dir / "final"
    answers_path = final_dir / "answers.jsonl"
    receipt_path = campaign_dir / "campaign_receipt.json"
    if answers_path.exists() or receipt_path.exists():
        raise FileExistsError("refusing to overwrite final campaign artifacts")
    answer_by_id: dict[str, str] = {}
    terminal = int(freeze["profileSpec"]["terminalCandidateStage"])
    stages = freeze["profileSpec"]["stages"]
    for shard in freeze["sharding"]["manifest"]:
        stage = stages[terminal - 1]
        stage_dir = _stage_dir(campaign_dir, shard["shardId"], terminal, stage["name"])
        receipt = load_json(stage_dir / "stage_receipt.json")
        candidate_path = _accepted_output_path(stage_dir, receipt)
        for row in load_jsonl(candidate_path):
            answer_by_id[str(row["id"])] = str(row["conclusion"])
    expected_ids = load_json(campaign_dir / "input/expected_ids.json")["ids"]
    if set(answer_by_id) != set(expected_ids) or len(answer_by_id) != len(expected_ids):
        raise ValueError("terminal candidates do not cover the exact campaign IDs")
    answer_rows = [{"id": case_id, "finalAnswer": answer_by_id[case_id]} for case_id in expected_ids]
    if any(row["finalAnswer"] not in ALLOWED_CONCLUSIONS for row in answer_rows):
        raise ValueError("terminal candidate contains an unparsed conclusion")
    write_jsonl_exclusive(answers_path, answer_rows)
    totals: dict[str, int] = {}
    for receipt in stage_receipts:
        for key, value in receipt.get("tokenUsageAllAttempts", {}).items():
            totals[key] = totals.get(key, 0) + int(value)
    stage_hashes = [receipt["receiptSha256"] for receipt in stage_receipts]
    campaign_receipt: dict[str, Any] = {
        "schemaVersion": 1,
        "status": "accepted",
        "protocol": PROTOCOL,
        "profile": freeze["profile"],
        "freezeSha256": freeze["freezeSha256"],
        "executionConfig": dict(EXECUTION_CONFIG),
        "runPolicy": dict(freeze["runPolicy"]),
        "codexHomePath": stage_receipts[0]["codexHomePath"] if stage_receipts else None,
        "semanticAcceptedResponses": sum(int(item["semanticAcceptedResponses"]) for item in stage_receipts),
        "actualModelInvocations": sum(int(item["actualModelInvocations"]) for item in stage_receipts),
        "transportRetryCount": sum(int(item["transportRetryCount"]) for item in stage_receipts),
        "elapsedSecProcessSum": round(sum(float(item["elapsedSecAllAttempts"]) for item in stage_receipts), 3),
        "tokenUsageAllAttempts": totals,
        "stageReceiptSha256": stage_hashes,
        "stageReceiptBundleSha256": canonical_digest(stage_hashes),
        "answersSha256": sha256_file(answers_path),
        "answersRows": len(answer_rows),
        "acceptedArtifact": "final/answers.jsonl",
    }
    campaign_receipt["campaignReceiptSha256"] = self_hash(campaign_receipt, "campaignReceiptSha256")
    write_json_exclusive(receipt_path, campaign_receipt)
    return campaign_receipt


def run_campaign(
    *,
    campaign_dir: Path,
    codex_home: Path,
    timeout_seconds: int,
    max_transport_attempts: int,
    resume: bool,
    popen_factory: Callable[..., Any] = subprocess.Popen,
    isolation_probe: Callable[..., dict[str, Any]] = plain_runner.isolation_probe,
) -> dict[str, Any]:
    campaign_dir = campaign_dir.resolve()
    codex_home = codex_home.resolve()
    if not codex_home.is_dir() or not (codex_home / "auth.json").is_file():
        raise FileNotFoundError(f"explicit CODEX_HOME lacks auth.json: {codex_home}")
    if timeout_seconds <= 0 or not 1 <= max_transport_attempts <= 5:
        raise ValueError("timeout must be positive and max transport attempts must be 1..5")
    freeze = verify_freeze(campaign_dir)
    supplied_run_policy = {
        "timeoutSeconds": timeout_seconds,
        "maxTransportAttempts": max_transport_attempts,
    }
    if supplied_run_policy != freeze["runPolicy"]:
        raise ValueError(
            f"run arguments differ from frozen runPolicy: supplied={supplied_run_policy}, frozen={freeze['runPolicy']}"
        )
    existing_campaign_receipt = campaign_dir / "campaign_receipt.json"
    if existing_campaign_receipt.exists():
        if not resume:
            raise FileExistsError(existing_campaign_receipt)
        report = validate_campaign(campaign_dir)
        return {**report, "status": "resumed_complete_without_model_call"}
    all_receipts: list[dict[str, Any]] = []
    for shard in freeze["sharding"]["manifest"]:
        stages = freeze["profileSpec"]["stages"]
        for stage_number, stage in enumerate(stages, start=1):
            stage_dir = _stage_dir(campaign_dir, shard["shardId"], stage_number, stage["name"])
            if stage_dir.exists():
                if not resume:
                    raise FileExistsError(f"stage exists; use --resume only for fully accepted stages: {stage_dir}")
                request_path = stage_dir / "stage_request.json"
                receipt_path = stage_dir / "stage_receipt.json"
                if not request_path.is_file() or not receipt_path.is_file():
                    raise RuntimeError(f"resume refuses partial stage bundle: {stage_dir}")
                receipt = _verify_stage_receipt(
                    stage_dir, load_json(request_path), expected_codex_home=codex_home
                )
                all_receipts.append(receipt)
                continue
            stage_dir, request = _prepare_stage_bundle(
                campaign_dir=campaign_dir,
                freeze=freeze,
                shard=shard,
                stage_number=stage_number,
                stage=stage,
            )
            (stage_dir / "probe-output").mkdir()
            probe = isolation_probe(
                input_dir=stage_dir / "input", output_dir=stage_dir / "probe-output", codex_home=codex_home
            )
            if not probe.get("passed"):
                raise RuntimeError(f"ICR stage isolation probe failed before invocation: {probe}")
            receipt = _run_stage(
                stage_dir=stage_dir,
                request=request,
                codex_home=codex_home,
                timeout_seconds=timeout_seconds,
                max_transport_attempts=max_transport_attempts,
                popen_factory=popen_factory,
            )
            all_receipts.append(receipt)
    return _finalize_campaign(campaign_dir, freeze, all_receipts)


def validate_campaign(campaign_dir: Path) -> dict[str, Any]:
    campaign_dir = campaign_dir.resolve()
    freeze = verify_freeze(campaign_dir)
    failures: list[str] = []
    stage_receipts: list[dict[str, Any]] = []
    codex_home_paths: set[str] = set()
    for shard in freeze["sharding"]["manifest"]:
        for stage_number, stage in enumerate(freeze["profileSpec"]["stages"], start=1):
            stage_dir = _stage_dir(campaign_dir, shard["shardId"], stage_number, stage["name"])
            try:
                receipt = _verify_stage_receipt(stage_dir, load_json(stage_dir / "stage_request.json"))
            except Exception as exc:
                failures.append(f"{shard['shardId']}:{stage_number}:{type(exc).__name__}:{exc}")
                continue
            stage_receipts.append(receipt)
            codex_home_paths.add(str(receipt.get("codexHomePath") or ""))
    answers_path = campaign_dir / "final/answers.jsonl"
    expected_ids = load_json(campaign_dir / "input/expected_ids.json")["ids"]
    if not answers_path.is_file():
        failures.append("final_answers_missing")
        answer_rows: list[dict[str, Any]] = []
    else:
        try:
            answer_rows = load_jsonl(answers_path)
        except Exception as exc:
            failures.append(f"final_answers_parse_error:{exc}")
            answer_rows = []
    if [row.get("id") for row in answer_rows] != expected_ids:
        failures.append("final_answer_ids_or_order_mismatch")
    for index, row in enumerate(answer_rows, start=1):
        if set(row) != {"id", "finalAnswer"} or row.get("finalAnswer") not in ALLOWED_CONCLUSIONS:
            failures.append(f"final_answer_row_{index}_invalid")
    receipt_path = campaign_dir / "campaign_receipt.json"
    if not receipt_path.is_file():
        failures.append("campaign_receipt_missing")
        receipt: dict[str, Any] = {}
    else:
        receipt = load_json(receipt_path)
        if receipt.get("campaignReceiptSha256") != self_hash(receipt, "campaignReceiptSha256"):
            failures.append("campaign_receipt_self_hash_mismatch")
        if receipt.get("status") != "accepted" or receipt.get("freezeSha256") != freeze.get("freezeSha256"):
            failures.append("campaign_receipt_not_bound_to_freeze")
        if receipt.get("executionConfig") != EXECUTION_CONFIG:
            failures.append("campaign_execution_config_mismatch")
        if receipt.get("runPolicy") != freeze.get("runPolicy"):
            failures.append("campaign_run_policy_mismatch")
        if len(codex_home_paths) != 1 or receipt.get("codexHomePath") not in codex_home_paths:
            failures.append("campaign_codex_home_mismatch")
        if answers_path.is_file() and receipt.get("answersSha256") != sha256_file(answers_path):
            failures.append("campaign_answers_hash_mismatch")
        hashes = [item.get("receiptSha256") for item in stage_receipts]
        if receipt.get("stageReceiptSha256") != hashes or receipt.get("stageReceiptBundleSha256") != canonical_digest(hashes):
            failures.append("campaign_stage_receipt_bundle_mismatch")
        recomputed_tokens: dict[str, int] = {}
        for stage_receipt in stage_receipts:
            for key, value in stage_receipt.get("tokenUsageAllAttempts", {}).items():
                recomputed_tokens[key] = recomputed_tokens.get(key, 0) + int(value)
        recomputed_campaign_totals = {
            "semanticAcceptedResponses": sum(
                int(item.get("semanticAcceptedResponses", 0)) for item in stage_receipts
            ),
            "actualModelInvocations": sum(int(item.get("actualModelInvocations", 0)) for item in stage_receipts),
            "transportRetryCount": sum(int(item.get("transportRetryCount", 0)) for item in stage_receipts),
            "elapsedSecProcessSum": round(
                sum(float(item.get("elapsedSecAllAttempts", 0.0)) for item in stage_receipts), 3
            ),
            "tokenUsageAllAttempts": recomputed_tokens,
        }
        for key, value in recomputed_campaign_totals.items():
            if receipt.get(key) != value:
                failures.append(f"campaign_{key}_mismatch")
    if failures:
        raise ValueError("ICR campaign validation failed closed: " + ", ".join(failures))
    return {
        "status": "accepted",
        "protocol": PROTOCOL,
        "profile": freeze["profile"],
        "freezeSha256": freeze["freezeSha256"],
        "campaignReceiptSha256": receipt["campaignReceiptSha256"],
        "answersSha256": receipt["answersSha256"],
        "answersRows": len(answer_rows),
        "semanticAcceptedResponses": receipt["semanticAcceptedResponses"],
        "actualModelInvocations": receipt["actualModelInvocations"],
        "tokenUsageAllAttempts": receipt["tokenUsageAllAttempts"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run sealed budgeted ICR baselines without hidden-label access.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--public", type=Path, required=True)
    prepare.add_argument("--campaign-dir", type=Path, required=True)
    prepare.add_argument("--profile", choices=sorted(PROFILES), required=True)
    prepare.add_argument("--shard-size", type=int, default=50)
    prepare.add_argument("--shard-seed", default="mini-artichokes-icr-confirmation-v1")
    prepare.add_argument("--timeout-seconds", type=int, required=True)
    prepare.add_argument("--max-transport-attempts", type=int, required=True)
    run = subparsers.add_parser("run")
    run.add_argument("--campaign-dir", type=Path, required=True)
    run.add_argument("--codex-home", type=Path, required=True)
    run.add_argument("--timeout-seconds", type=int, default=21_600)
    run.add_argument("--max-transport-attempts", type=int, default=2)
    run.add_argument("--resume", action="store_true")
    validate = subparsers.add_parser("validate")
    validate.add_argument("--campaign-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare_campaign(
            public_path=args.public,
            campaign_dir=args.campaign_dir,
            profile=args.profile,
            shard_size=args.shard_size,
            shard_seed=args.shard_seed,
            timeout_seconds=args.timeout_seconds,
            max_transport_attempts=args.max_transport_attempts,
        )
    elif args.command == "run":
        result = run_campaign(
            campaign_dir=args.campaign_dir,
            codex_home=args.codex_home,
            timeout_seconds=args.timeout_seconds,
            max_transport_attempts=args.max_transport_attempts,
            resume=args.resume,
        )
    else:
        result = validate_campaign(args.campaign_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
