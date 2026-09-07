#!/usr/bin/env python3
"""Prepare and validate a sealed, label-blind outcome-gold audit.

The candidate inventory is private because it contains the deterministic
parser's provisional label.  This module is the only preparation component
that reads that label.  It emits auditor shards whose exact public schema is
only ``id`` plus ``holding``; provisional labels, quotas, source identities,
and solver outputs are never staged in an auditor sandbox.

The mechanical A/B comparison and the final private parser comparison live in
separate commands.  Keeping those stages separate makes it impossible for the
gold-free comparison to accidentally load the provisional labels.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
import unicodedata
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
PROTOCOL = "source-disjoint-outcome-gold-audit-v2"
SOURCE_PROTOCOL = "source-disjoint-outcome-candidate-inventory-v1"
PROFILE_PROTOCOL = "source-disjoint-outcome-gold-auditor-profile-v2"
SHARD_PROTOCOL = "source-disjoint-outcome-gold-auditor-shard-v2"
COMPARISON_PROTOCOL = "source-disjoint-outcome-gold-ab-comparison-v2"
FINAL_PROTOCOL = "source-disjoint-outcome-gold-final-consensus-v2"

LABELS = ("인용됨", "기각", "AMBIGUOUS")
PROVISIONAL_LABELS = ("인용됨", "기각")
FLAGS = (
    "partial_grant",
    "counterclaim",
    "dismissal_without_prejudice",
    "settlement",
    "appeal",
    "unclear",
)
DISQUALIFYING_FLAGS = frozenset(
    {
        "counterclaim",
        "dismissal_without_prejudice",
        "settlement",
        "appeal",
        "unclear",
    }
)
JUDGMENT_KEYS = {
    "id",
    "eligible",
    "label",
    "exactHoldingQuote",
    "flags",
    "rationale",
}
PACKET_KEYS = {"id", "holding"}
PROFILE_DIRS = {"A": "auditor_a", "B": "auditor_b", "C": "auditor_c"}
DEFAULT_MODELS = {
    "A": "gpt-5.6-sol",
    "B": "gpt-5.6-terra",
    "C": "gpt-5.6-sol",
}
DEFAULT_REASONING_EFFORT = "high"
DEFAULT_VERBOSITY = "low"
DEFAULT_SERVICE_TIER = "default"
DEFAULT_CODEX_HOME = Path("/home/pineapple/.codex-new-account")
REQUIRED_CODEX_VERSION = "codex-cli 0.151.0"
DEFAULT_SHARD_SIZE = 40
DEFAULT_TIMEOUT_SECONDS = 7_200
DEFAULT_MINIMUM_KAPPA = 0.90
DEFAULT_BOOTSTRAP_REPLICATES = 2_000
DEFAULT_ORDER_SEED = "mini-artichokes-gold-audit-order-v1"
DEFAULT_C_SAMPLE_SEED = "mini-artichokes-gold-audit-c-agreement-sample-v1"
CANONICAL_C_AGREEMENT_AUDIT_FRACTION = 0.10
CANONICAL_C_AGREEMENT_COUNT_RULE = "ceil(0.10 * A/B core agreements)"
CANONICAL_BOOTSTRAP_CONFIG = {
    "method": "deterministic nonparametric row bootstrap",
    "replicates": DEFAULT_BOOTSTRAP_REPLICATES,
    "confidenceLevel": 0.95,
    "seedDerivation": "SHA256(cSampleSeed\\0scope)",
}
CANONICAL_SELECTION_SIZE_RULE = {
    "civil": {
        "capPerAuditedLabel": 150,
        "minimumPerAuditedLabel": 140,
    },
    "tax": {
        "capPerAuditedLabel": 90,
        "minimumPerAuditedLabel": 80,
    },
    "sharedPerLabelRule": (
        "for each domain, min(capPerAuditedLabel, minimum eligible audited-label "
        "cell count); use the same size for both audited labels"
    ),
    "selectionOrder": "ascending (selectionRankSHA256, id) within each cell",
    "possibleFinalRows": {"minimum": 440, "maximum": 480},
    "solverOutputsConsulted": False,
}
HEX64 = re.compile(r"^[0-9a-f]{64}$")
PUBLIC_ROW_KEYS = {"id", "suite", "benchmarkId", "responseFormat", "language", "prompt"}
PUBLIC_CONSTANTS = {
    "suite": "exam",
    "benchmarkId": "outcome.first_instance_prediction.v1",
    "responseFormat": "outcome_prediction",
    "language": "ko",
}
PRIVATE_ROW_KEYS = {
    "caseId",
    "domain",
    "label",
    "caseRef",
    "canonicalId",
    "decisionDate",
    "sourceDataset",
    "holding",
    "sourceFields",
    "evidenceClauses",
    "selectionRankSHA256",
    "promptSHA256",
    "sourcePromptSHA256",
    "identityKeys",
    "targetMetadataRedaction",
}
IDENTITY_KEY_NAMES = {
    "canonicalId",
    "caseRef",
    "caseNumber",
    "sourceRecordIdSHA256",
    "sourceDatasetRecordIdSHA256",
    "sourcePathLocatorSHA256",
    "dedupeKey",
    "dedupeKeyPrimary",
    "dedupeKeyFallback",
    "textHash",
    "splitGroupId",
    "promptSHA256",
    "sourcePromptSHA256",
    "claimContentSHA256",
    "factsContentSHA256",
    "claimFactsContentSHA256",
}
ORDERED_CANDIDATE_KEYS = {
    "id",
    "promptSHA256",
    "publicRowSHA256",
    "privateRowSHA256",
}
ARTIFACT_META_KEYS = {"path", "rows", "bytes", "sha256"}
OUTPUT_OBJECT_KEYS = {"judgments"}
PRECALL_ANCHOR_PROTOCOL = "source-disjoint-outcome-gold-precall-anchor-v2"
ATTEMPT_POLICY = {
    "firstAttemptOnly": True,
    "semanticRetries": 0,
    "rejectedAttemptRerunnable": False,
}
ATTEMPT_EVIDENCE_LIMITATION = (
    "The exclusive local registry detects ordinary reruns but has no trusted external "
    "clock or append-only witness. First-attempt provenance requires immediate external "
    "append-only post-call anchoring and is not proven by local self-hashes alone."
)
TARGET_REDACTION_ROW_KEYS = {
    "version",
    "specificationSHA256",
    "replacementCounts",
    "postRenderTargetMatchCount",
}
TARGET_REDACTION_COMPONENTS = {"court", "caseNumber", "decisionDate"}
TARGET_REDACTION_MANIFEST_KEYS = {
    "version",
    "specification",
    "specificationSHA256",
    "perRowMetadataLocation",
    "selectedRowCount",
    "rowsWithAtLeastOneReplacement",
    "rowsWithNoReplacement",
    "replacementCounts",
    "postRenderTargetMatchCount",
}
TARGET_REDACTION_SPEC_KEYS = {
    "version",
    "scope",
    "goldIndependent",
    "unicodeNormalization",
    "courtMatching",
    "caseNumberMatching",
    "decisionDateMatching",
    "placeholders",
    "postcondition",
    "unredactedClosure",
}
TOOL_FREE_DISABLED_FEATURES = frozenset(
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


class GoldAuditError(RuntimeError):
    """A fail-closed preparation, validation, or stage-integrity error."""


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


def sha256_file(path: Path, *, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    return re.sub(r"\s+", " ", text).strip()


def normalized_prompt_sha256(prompt: Any) -> str:
    normalized = normalize_text(prompt)
    if not normalized:
        raise GoldAuditError("public prompt is empty after normalization")
    return sha256_bytes(normalized.encode("utf-8"))


def output_schema() -> dict[str, Any]:
    """Exact provider-side shape; row identity/order remains host-validated."""

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": ["judgments"],
        "properties": {
            "judgments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "id",
                        "eligible",
                        "label",
                        "exactHoldingQuote",
                        "flags",
                        "rationale",
                    ],
                    "properties": {
                        "id": {"type": "string", "minLength": 1},
                        "eligible": {"type": "boolean"},
                        "label": {"type": "string", "enum": list(LABELS)},
                        "exactHoldingQuote": {"type": "string", "minLength": 1},
                        "flags": {
                            "type": "array",
                            "items": {"type": "string", "enum": list(FLAGS)},
                        },
                        "rationale": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": 500,
                        },
                    },
                },
            }
        },
    }


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON object key: {key}")
        value[key] = item
    return value


def _reject_constant(value: str) -> Any:
    raise ValueError(f"non-finite JSON value: {value}")


def parse_json_strict(raw: str, *, location: str) -> Any:
    try:
        return json.loads(
            raw,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_constant,
        )
    except (json.JSONDecodeError, ValueError) as error:
        raise GoldAuditError(f"malformed JSON at {location}: {error}") from error


def load_json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise GoldAuditError(f"required JSON must be a regular non-symlink file: {path}")
    value = parse_json_strict(path.read_text(encoding="utf-8"), location=str(path))
    if not isinstance(value, dict):
        raise GoldAuditError(f"expected JSON object: {path}")
    return value


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if path.is_symlink() or not path.is_file():
        raise GoldAuditError(f"required JSONL must be a regular non-symlink file: {path}")
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise GoldAuditError(f"JSONL is not UTF-8: {path}: {error}") from error
    if not text:
        raise GoldAuditError(f"JSONL is empty: {path}")
    rows: list[dict[str, Any]] = []
    lines = text.split("\n")
    for line_number, line in enumerate(lines, 1):
        if line_number == len(lines) and not line:
            continue
        if not line.strip():
            raise GoldAuditError(f"blank JSONL row: {path}:{line_number}")
        value = parse_json_strict(line, location=f"{path}:{line_number}")
        if not isinstance(value, dict):
            raise GoldAuditError(f"JSONL row is not an object: {path}:{line_number}")
        rows.append(value)
    if not rows:
        raise GoldAuditError(f"JSONL has no rows: {path}")
    return rows


def serialize_jsonl(rows: Iterable[Mapping[str, Any]]) -> bytes:
    return b"".join(canonical_json_bytes(row) + b"\n" for row in rows)


def self_hash(value: Mapping[str, Any], *, key: str) -> str:
    unsigned = dict(value)
    unsigned.pop(key, None)
    return canonical_digest(unsigned)


def verify_self_hash(value: Mapping[str, Any], *, key: str, location: str) -> None:
    claimed = value.get(key)
    if not isinstance(claimed, str) or not HEX64.fullmatch(claimed):
        raise GoldAuditError(f"missing or malformed {key}: {location}")
    if claimed != self_hash(value, key=key):
        raise GoldAuditError(f"self-hash mismatch: {location}")


def write_bytes_exclusive(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as error:
        raise GoldAuditError(f"refusing to overwrite existing artifact: {path}") from error


def write_json_exclusive(path: Path, value: Any) -> None:
    write_bytes_exclusive(
        path,
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        ).encode("utf-8")
        + b"\n",
    )


def write_jsonl_exclusive(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    write_bytes_exclusive(path, serialize_jsonl(rows))


def source_manifest_self_hash(manifest: Mapping[str, Any]) -> str:
    return self_hash(manifest, key="selfHash")


def _validate_artifact_meta(value: Any, *, name: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != ARTIFACT_META_KEYS:
        raise GoldAuditError(f"reserve manifest artifacts.{name} exact schema mismatch")
    if (
        not isinstance(value.get("path"), str)
        or not value["path"]
        or not isinstance(value.get("rows"), int)
        or isinstance(value.get("rows"), bool)
        or value["rows"] <= 0
        or not isinstance(value.get("bytes"), int)
        or isinstance(value.get("bytes"), bool)
        or value["bytes"] <= 0
        or not isinstance(value.get("sha256"), str)
        or not HEX64.fullmatch(value["sha256"])
    ):
        raise GoldAuditError(f"reserve manifest artifacts.{name} has invalid values")
    return value


def _validate_clause_rows(value: Any, *, prefix: str, allow_empty: bool) -> None:
    if not isinstance(value, list) or (not value and not allow_empty):
        raise GoldAuditError(f"private evidenceClauses.{prefix} has invalid cardinality")
    for index, clause in enumerate(value, 1):
        expected_id = f"{prefix}{index:03d}"
        if (
            not isinstance(clause, dict)
            or set(clause) != {"id", "text"}
            or clause.get("id") != expected_id
            or not isinstance(clause.get("text"), str)
            or not clause["text"].strip()
        ):
            raise GoldAuditError(f"private evidence clause schema/order mismatch: {expected_id}")


def _nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _validate_target_redaction_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    value = manifest.get("targetMetadataRedaction")
    if not isinstance(value, dict) or set(value) != TARGET_REDACTION_MANIFEST_KEYS:
        raise GoldAuditError("reserve manifest targetMetadataRedaction exact schema mismatch")
    specification = value.get("specification")
    if not isinstance(specification, dict) or set(specification) != TARGET_REDACTION_SPEC_KEYS:
        raise GoldAuditError("target-redaction specification exact schema mismatch")
    placeholders = specification.get("placeholders")
    if (
        not isinstance(placeholders, dict)
        or set(placeholders) != TARGET_REDACTION_COMPONENTS
        or any(not isinstance(item, str) or not item for item in placeholders.values())
    ):
        raise GoldAuditError("target-redaction placeholder schema mismatch")
    version = value.get("version")
    specification_hash = value.get("specificationSHA256")
    if (
        not isinstance(version, str)
        or not version
        or specification.get("version") != version
        or not isinstance(specification_hash, str)
        or not HEX64.fullmatch(specification_hash)
        or specification_hash != canonical_digest(specification)
        or value.get("perRowMetadataLocation")
        != "private JSONL targetMetadataRedaction"
        or value.get("postRenderTargetMatchCount") != 0
    ):
        raise GoldAuditError("target-redaction specification binding mismatch")
    for key in (
        "selectedRowCount",
        "rowsWithAtLeastOneReplacement",
        "rowsWithNoReplacement",
    ):
        if not _nonnegative_int(value.get(key)):
            raise GoldAuditError(f"target-redaction manifest count is invalid: {key}")
    counts = value.get("replacementCounts")
    expected_count_keys = {"all"} | {
        f"{scope}.{component}"
        for scope in ("claim", "facts", "locator")
        for component in TARGET_REDACTION_COMPONENTS
    }
    if (
        not isinstance(counts, dict)
        or set(counts) != expected_count_keys
        or any(not _nonnegative_int(item) for item in counts.values())
    ):
        raise GoldAuditError("target-redaction manifest replacementCounts mismatch")
    return value


def _validate_target_redaction_row(
    value: Any, *, case_id: str, manifest_redaction: Mapping[str, Any]
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != TARGET_REDACTION_ROW_KEYS:
        raise GoldAuditError(f"private targetMetadataRedaction exact schema mismatch: {case_id}")
    if (
        value.get("version") != manifest_redaction.get("version")
        or value.get("specificationSHA256")
        != manifest_redaction.get("specificationSHA256")
        or value.get("postRenderTargetMatchCount") != 0
    ):
        raise GoldAuditError(f"private target-redaction binding/postcondition mismatch: {case_id}")
    counts = value.get("replacementCounts")
    if not isinstance(counts, dict) or set(counts) != {"claim", "facts"}:
        raise GoldAuditError(f"private target-redaction replacement scope mismatch: {case_id}")
    for scope in ("claim", "facts"):
        scoped = counts.get(scope)
        if (
            not isinstance(scoped, dict)
            or set(scoped) != TARGET_REDACTION_COMPONENTS
            or any(not _nonnegative_int(item) for item in scoped.values())
        ):
            raise GoldAuditError(
                f"private target-redaction replacement count mismatch: {case_id}:{scope}"
            )
    return value


def validate_source_inventory(
    *, private_path: Path, manifest_path: Path
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], Path]:
    """Validate the exact public/private reserve pairing and every row binding."""

    from tools import build_disjoint_outcome_reserve as reserve_builder

    if private_path.is_symlink() or not private_path.is_file():
        raise GoldAuditError(f"private reserve must be a regular non-symlink file: {private_path}")
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise GoldAuditError(f"source manifest must be a regular non-symlink file: {manifest_path}")
    private_path = private_path.resolve()
    manifest_path = manifest_path.resolve()
    manifest = load_json(manifest_path)
    if manifest.get("protocol") != SOURCE_PROTOCOL:
        raise GoldAuditError(f"unsupported reserve manifest protocol: {manifest.get('protocol')!r}")
    verify_self_hash(manifest, key="selfHash", location=str(manifest_path))
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != {"public", "private"}:
        raise GoldAuditError("reserve manifest artifacts exact schema mismatch")
    public_meta = _validate_artifact_meta(artifacts["public"], name="public")
    private_meta = _validate_artifact_meta(artifacts["private"], name="private")
    declared_private = Path(private_meta["path"])
    declared_public = Path(public_meta["path"])
    if not declared_private.is_absolute() or declared_private.resolve() != private_path:
        raise GoldAuditError("passed private reserve path differs from manifest artifacts.private.path")
    if not declared_public.is_absolute():
        raise GoldAuditError("manifest artifacts.public.path must be absolute")
    public_path = declared_public.resolve()
    if public_path.is_symlink() or not public_path.is_file():
        raise GoldAuditError(f"public reserve must be a regular non-symlink file: {public_path}")

    raw_private = private_path.read_bytes()
    raw_public = public_path.read_bytes()
    for name, raw, meta in (
        ("private", raw_private, private_meta),
        ("public", raw_public, public_meta),
    ):
        if meta["sha256"] != sha256_bytes(raw):
            raise GoldAuditError(f"{name} reserve hash disagrees with source manifest")
        if meta["bytes"] != len(raw):
            raise GoldAuditError(f"{name} reserve byte count disagrees with source manifest")
    private_rows = load_jsonl(private_path)
    public_rows = load_jsonl(public_path)
    if private_meta["rows"] != len(private_rows) or public_meta["rows"] != len(public_rows):
        raise GoldAuditError("public/private reserve row count disagrees with source manifest")
    if len(private_rows) != len(public_rows):
        raise GoldAuditError("public/private reserve row counts differ")

    ordered = manifest.get("orderedCandidates")
    if not isinstance(ordered, list) or len(ordered) != len(private_rows):
        raise GoldAuditError("reserve orderedCandidates count mismatch")
    configuration = manifest.get("configuration")
    quotas = configuration.get("quotas") if isinstance(configuration, dict) else None
    if not isinstance(quotas, dict) or set(quotas) != {"civil", "tax"}:
        raise GoldAuditError("reserve manifest configuration.quotas exact domains mismatch")
    for domain, quota in quotas.items():
        if (
            not isinstance(quota, dict)
            or set(quota) != {"targetPerLabel", "candidatePerLabel"}
            or not isinstance(quota.get("targetPerLabel"), int)
            or isinstance(quota.get("targetPerLabel"), bool)
            or quota["targetPerLabel"] <= 0
            or not isinstance(quota.get("candidatePerLabel"), int)
            or isinstance(quota.get("candidatePerLabel"), bool)
            or quota["candidatePerLabel"] < quota["targetPerLabel"]
        ):
            raise GoldAuditError(f"reserve manifest quota schema/value mismatch: {domain}")
    seed_salt = configuration.get("seedSalt")
    if not isinstance(seed_salt, str) or not seed_salt:
        raise GoldAuditError("reserve manifest configuration.seedSalt is missing")
    buffer_selection = manifest.get("candidateBufferSelection")
    if not isinstance(buffer_selection, dict) or set(buffer_selection) != {"civil", "tax"}:
        raise GoldAuditError("reserve candidateBufferSelection exact domains mismatch")

    manifest_redaction = _validate_target_redaction_manifest(manifest)
    aggregate_replacements: Counter[str] = Counter()
    rows_with_replacement = 0
    observed_cells: Counter[tuple[str, str]] = Counter()
    seen: set[str] = set()
    for index, (public, private, bound) in enumerate(
        zip(public_rows, private_rows, ordered, strict=True)
    ):
        if not isinstance(bound, dict) or set(bound) != ORDERED_CANDIDATE_KEYS:
            raise GoldAuditError(f"orderedCandidates exact schema mismatch: row {index}")
        if set(public) != PUBLIC_ROW_KEYS:
            raise GoldAuditError(f"public reserve exact schema mismatch: row {index}")
        for key, expected in PUBLIC_CONSTANTS.items():
            if public.get(key) != expected:
                raise GoldAuditError(f"public reserve constant mismatch: row {index}:{key}")
        if set(private) != PRIVATE_ROW_KEYS:
            raise GoldAuditError(f"private reserve exact schema mismatch: row {index}")
        case_id = private.get("caseId")
        if (
            not isinstance(case_id, str)
            or not case_id.strip()
            or public.get("id") != case_id
            or bound.get("id") != case_id
        ):
            raise GoldAuditError(f"public/private/ordered ID mismatch at row {index}")
        if case_id in seen:
            raise GoldAuditError(f"duplicate reserve ID: {case_id}")
        seen.add(case_id)
        if private.get("domain") not in {"civil", "tax"}:
            raise GoldAuditError(f"private reserve has invalid domain: {case_id}")
        if private.get("label") not in PROVISIONAL_LABELS:
            raise GoldAuditError(f"private reserve has invalid provisional label: {case_id}")
        observed_cells[(private["domain"], private["label"])] += 1
        for key in ("caseRef", "canonicalId", "decisionDate", "sourceDataset", "holding"):
            if not isinstance(private.get(key), str) or not private[key].strip():
                raise GoldAuditError(f"private reserve has invalid {key}: {case_id}")
        if (
            not isinstance(public.get("prompt"), str)
            or not public["prompt"].strip()
            or not isinstance(private.get("selectionRankSHA256"), str)
            or not HEX64.fullmatch(private["selectionRankSHA256"])
            or not isinstance(private.get("promptSHA256"), str)
            or not HEX64.fullmatch(private["promptSHA256"])
            or not isinstance(private.get("sourcePromptSHA256"), str)
            or not HEX64.fullmatch(private["sourcePromptSHA256"])
        ):
            raise GoldAuditError(f"private reserve hash field mismatch: {case_id}")
        source_fields = private.get("sourceFields")
        if (
            not isinstance(source_fields, dict)
            or set(source_fields) != {"claim", "facts"}
            or any(not isinstance(source_fields[key], str) for key in ("claim", "facts"))
            or not source_fields["facts"].strip()
        ):
            raise GoldAuditError(f"private sourceFields exact schema mismatch: {case_id}")
        evidence = private.get("evidenceClauses")
        if not isinstance(evidence, dict) or set(evidence) != {"claim", "facts"}:
            raise GoldAuditError(f"private evidenceClauses exact schema mismatch: {case_id}")
        _validate_clause_rows(
            evidence["claim"], prefix="C", allow_empty=private["domain"] == "tax"
        )
        _validate_clause_rows(evidence["facts"], prefix="F", allow_empty=False)
        identity = private.get("identityKeys")
        if (
            not isinstance(identity, dict)
            or set(identity) != IDENTITY_KEY_NAMES
            or any(not isinstance(value, str) for value in identity.values())
        ):
            raise GoldAuditError(f"private identityKeys exact schema mismatch: {case_id}")
        try:
            normalized_case_ref = reserve_builder.normalize_case_ref(private["caseRef"])
        except Exception as error:
            raise GoldAuditError(f"private caseRef normalization failed: {case_id}") from error
        if (
            identity["canonicalId"] != private["canonicalId"]
            or identity["caseRef"] != normalized_case_ref
        ):
            raise GoldAuditError(f"private identityKeys row binding mismatch: {case_id}")
        redaction = _validate_target_redaction_row(
            private.get("targetMetadataRedaction"),
            case_id=case_id,
            manifest_redaction=manifest_redaction,
        )
        try:
            court, case_number = private["caseRef"].split("|", 1)
            recomputed_redaction = reserve_builder.redact_target_metadata(
                claim=source_fields["claim"],
                facts=source_fields["facts"],
                court=court,
                case_number=case_number,
                decision_date=private["decisionDate"],
            )
            expected_claim_clauses = (
                reserve_builder.segment_evidence(recomputed_redaction.claim, prefix="C")
                if private["domain"] == "civil"
                else []
            )
            expected_facts_clauses = reserve_builder.segment_evidence(
                recomputed_redaction.facts, prefix="F"
            )
            expected_public_prompt = reserve_builder.render_prompt(
                domain=private["domain"],
                claim_clauses=expected_claim_clauses,
                facts_clauses=expected_facts_clauses,
            )
            unredacted_claim_clauses = (
                reserve_builder.segment_evidence(source_fields["claim"], prefix="C")
                if private["domain"] == "civil"
                else []
            )
            unredacted_facts_clauses = reserve_builder.segment_evidence(
                source_fields["facts"], prefix="F"
            )
            unredacted_numbered_prompt = reserve_builder.render_prompt(
                domain=private["domain"],
                claim_clauses=unredacted_claim_clauses,
                facts_clauses=unredacted_facts_clauses,
            )
            source_prompt = reserve_builder.render_source_prompt(
                domain=private["domain"],
                claim=source_fields["claim"],
                facts=source_fields["facts"],
            )
        except Exception as error:
            raise GoldAuditError(
                f"private source/evidence semantic reconstruction failed: {case_id}"
            ) from error
        if evidence != {
            "claim": expected_claim_clauses,
            "facts": expected_facts_clauses,
        }:
            raise GoldAuditError(f"private evidenceClauses/sourceFields mismatch: {case_id}")
        if public["prompt"] != expected_public_prompt:
            raise GoldAuditError(f"public prompt/evidenceClauses rendering mismatch: {case_id}")
        if redaction["replacementCounts"] != recomputed_redaction.counts:
            raise GoldAuditError(f"private target-redaction recomputation mismatch: {case_id}")
        expected_content_hashes = {
            "claimContentSHA256": (
                reserve_builder.content_sha256(source_fields["claim"])
                if source_fields["claim"]
                else ""
            ),
            "factsContentSHA256": reserve_builder.content_sha256(source_fields["facts"]),
            "claimFactsContentSHA256": reserve_builder.content_sha256(
                f"{source_fields['claim']}\n{source_fields['facts']}"
                if source_fields["claim"]
                else source_fields["facts"]
            ),
            "promptSHA256": normalized_prompt_sha256(unredacted_numbered_prompt),
            "sourcePromptSHA256": normalized_prompt_sha256(source_prompt),
        }
        if any(identity[key] != value for key, value in expected_content_hashes.items()):
            raise GoldAuditError(f"private identity content/prompt hash mismatch: {case_id}")
        if private["sourcePromptSHA256"] != expected_content_hashes["sourcePromptSHA256"]:
            raise GoldAuditError(f"private sourcePromptSHA256 recomputation mismatch: {case_id}")
        expected_selection_rank = sha256_bytes(
            f"{seed_salt}|{private['canonicalId']}|{normalized_case_ref}".encode("utf-8")
        )
        if private["selectionRankSHA256"] != expected_selection_rank:
            raise GoldAuditError(f"private selectionRankSHA256 recomputation mismatch: {case_id}")
        row_replacements = 0
        for scope in ("claim", "facts"):
            for component in TARGET_REDACTION_COMPONENTS:
                count = redaction["replacementCounts"][scope][component]
                aggregate_replacements[f"{scope}.{component}"] += count
                row_replacements += count
        if row_replacements:
            rows_with_replacement += 1
        prompt_hash = normalized_prompt_sha256(public["prompt"])
        if prompt_hash != private["promptSHA256"] or prompt_hash != bound.get("promptSHA256"):
            raise GoldAuditError(f"public/private normalized prompt hash mismatch: {case_id}")
        if bound.get("publicRowSHA256") != canonical_digest(public):
            raise GoldAuditError(f"public reserve row hash mismatch: {case_id}")
        if bound.get("privateRowSHA256") != canonical_digest(private):
            raise GoldAuditError(f"private reserve row hash mismatch: {case_id}")
    manifest_counts = manifest_redaction["replacementCounts"]
    observed_counts = {
        f"{scope}.{component}": aggregate_replacements[f"{scope}.{component}"]
        for scope in ("claim", "facts")
        for component in TARGET_REDACTION_COMPONENTS
    }
    observed_counts.update(
        {
            f"locator.{component}": sum(
                aggregate_replacements[f"{scope}.{component}"]
                for scope in ("claim", "facts")
            )
            for component in TARGET_REDACTION_COMPONENTS
        }
    )
    observed_counts["all"] = sum(
        aggregate_replacements[f"{scope}.{component}"]
        for scope in ("claim", "facts")
        for component in TARGET_REDACTION_COMPONENTS
    )
    if observed_counts != manifest_counts:
        raise GoldAuditError("target-redaction aggregate replacement counts mismatch")
    if (
        manifest_redaction["selectedRowCount"] != len(private_rows)
        or manifest_redaction["rowsWithAtLeastOneReplacement"] != rows_with_replacement
        or manifest_redaction["rowsWithNoReplacement"]
        != len(private_rows) - rows_with_replacement
    ):
        raise GoldAuditError("target-redaction aggregate row counts mismatch")
    for domain in ("civil", "tax"):
        if not isinstance(buffer_selection.get(domain), dict) or set(
            buffer_selection[domain]
        ) != set(PROVISIONAL_LABELS):
            raise GoldAuditError(f"reserve candidateBufferSelection labels mismatch: {domain}")
        for label in PROVISIONAL_LABELS:
            cell = buffer_selection[domain][label]
            expected_keys = {
                "targetPerLabel",
                "requestedCandidateBuffer",
                "available",
                "selectedCandidateBuffer",
                "candidateBufferShortfall",
            }
            if (
                not isinstance(cell, dict)
                or set(cell) != expected_keys
                or any(not _nonnegative_int(cell.get(key)) for key in expected_keys)
            ):
                raise GoldAuditError(
                    f"reserve candidateBufferSelection cell schema mismatch: {domain}/{label}"
                )
            quota = quotas[domain]
            observed = observed_cells[(domain, label)]
            if (
                cell["targetPerLabel"] != quota["targetPerLabel"]
                or cell["requestedCandidateBuffer"] != quota["candidatePerLabel"]
                or cell["selectedCandidateBuffer"]
                != min(cell["requestedCandidateBuffer"], cell["available"])
                or cell["candidateBufferShortfall"]
                != cell["requestedCandidateBuffer"] - cell["selectedCandidateBuffer"]
                or observed != cell["selectedCandidateBuffer"]
                or observed < quota["targetPerLabel"]
            ):
                raise GoldAuditError(
                    f"reserve candidate quota/cell count mismatch: {domain}/{label}"
                )
    return public_rows, private_rows, manifest, public_path


def implementation_paths() -> tuple[Path, ...]:
    return (
        Path(__file__).resolve(),
        REPO_ROOT / "tools/run_outcome_gold_auditor.py",
        REPO_ROOT / "tools/compare_outcome_gold_audits.py",
        REPO_ROOT / "tools/finalize_outcome_gold_audit.py",
        REPO_ROOT / "tools/run_plain_codex_file_agent.py",
        REPO_ROOT / "tools/run_blind_pairwise_veto_agent.py",
        REPO_ROOT / "tools/benchmark_provider.py",
        REPO_ROOT / "tools/build_disjoint_outcome_reserve.py",
    )


def implementation_hashes() -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in implementation_paths():
        if not path.is_file():
            raise GoldAuditError(f"required audit implementation is missing: {path}")
        hashes[str(path.resolve())] = sha256_file(path)
    return hashes


@lru_cache(maxsize=1)
def tool_free_cli_base_identity() -> dict[str, Any]:
    from tools import run_blind_pairwise_veto_agent as trusted

    bwrap = shutil.which("bwrap")
    if not bwrap:
        raise GoldAuditError("bubblewrap is required for the tool-free gold auditor")
    identity = trusted.codex_cli_identity([str(Path(bwrap).resolve())])
    identity.pop("commandSha256", None)
    identity.pop("commandArgumentCount", None)
    environment = os.environ.copy()
    environment["CODEX_HOME"] = str(DEFAULT_CODEX_HOME.resolve())
    completed = subprocess.run(
        [
            identity["node"]["resolvedPath"],
            identity["entryPoint"]["resolvedPath"],
            "features",
            "list",
        ],
        env=environment,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        raise GoldAuditError(
            "unable to freeze Codex feature snapshot: "
            + completed.stderr.strip()[-500:]
        )
    feature_snapshot: list[dict[str, Any]] = []
    seen_features: set[str] = set()
    for line_number, raw in enumerate(completed.stdout.splitlines(), 1):
        parts = raw.split()
        if len(parts) < 3 or parts[-1] not in {"true", "false"}:
            raise GoldAuditError(
                f"malformed Codex feature snapshot line {line_number}: {raw!r}"
            )
        name = parts[0]
        if name in seen_features:
            raise GoldAuditError(f"duplicate Codex feature in snapshot: {name}")
        seen_features.add(name)
        feature_snapshot.append(
            {
                "name": name,
                "stage": " ".join(parts[1:-1]),
                "enabled": parts[-1] == "true",
            }
        )
    identity["featureSnapshot"] = feature_snapshot
    identity["featureSnapshotSha256"] = canonical_digest(feature_snapshot)
    identity["featureListStdoutSha256"] = sha256_bytes(
        completed.stdout.encode("utf-8")
    )
    identity["featureCount"] = len(feature_snapshot)
    verify_cli_binary_identity(identity)
    return identity


def cli_identity_for_command(
    base_identity: Mapping[str, Any], command: Sequence[str]
) -> dict[str, Any]:
    value = dict(base_identity)
    value["commandSha256"] = canonical_digest(list(command))
    value["commandArgumentCount"] = len(command)
    return value


def verify_cli_binary_identity(identity: Mapping[str, Any]) -> None:
    if identity.get("version") != REQUIRED_CODEX_VERSION:
        raise GoldAuditError(
            f"gold audit requires exact Codex CLI {REQUIRED_CODEX_VERSION}"
        )
    for key in ("launcher", "node", "entryPoint", "bubblewrap"):
        value = identity.get(key)
        if not isinstance(value, dict):
            raise GoldAuditError(f"frozen Codex CLI identity is missing {key}")
        resolved = value.get("resolvedPath")
        if not isinstance(resolved, str):
            raise GoldAuditError(f"frozen Codex CLI {key} path is missing")
        path = Path(resolved)
        if (
            not path.is_file()
            or value.get("sha256") != sha256_file(path)
            or value.get("bytes") != path.stat().st_size
        ):
            raise GoldAuditError(f"frozen Codex CLI binary identity changed: {key}")
    snapshot = identity.get("featureSnapshot")
    if (
        not isinstance(snapshot, list)
        or any(
            not isinstance(row, dict)
            or set(row) != {"name", "stage", "enabled"}
            or not isinstance(row.get("name"), str)
            or not row["name"]
            or not isinstance(row.get("stage"), str)
            or type(row.get("enabled")) is not bool
            for row in snapshot
        )
        or len({row["name"] for row in snapshot}) != len(snapshot)
        or identity.get("featureCount") != len(snapshot)
        or identity.get("featureSnapshotSha256") != canonical_digest(snapshot)
        or not isinstance(identity.get("featureListStdoutSha256"), str)
        or not HEX64.fullmatch(identity["featureListStdoutSha256"])
    ):
        raise GoldAuditError("frozen Codex CLI feature snapshot is malformed")
    missing = sorted(
        set(TOOL_FREE_DISABLED_FEATURES) - {row["name"] for row in snapshot}
    )
    if missing:
        raise GoldAuditError(
            f"required tool-surface feature names are absent from Codex snapshot: {missing}"
        )


def tool_free_codex_command(
    *,
    input_dir: Path,
    output_dir: Path,
    codex_home: Path,
    model: str,
    reasoning_effort: str,
    verbosity: str,
) -> list[str]:
    """Build a Codex exec with no model-visible tool or local-code channel."""

    from tools import run_plain_codex_file_agent as plain_runner

    required_home = DEFAULT_CODEX_HOME.resolve()
    if codex_home.resolve() != required_home:
        raise GoldAuditError(
            f"gold audit requires exact CODEX_HOME {required_home}; got {codex_home.resolve()}"
        )
    command, codex_js = plain_runner.base_bwrap_command(
        input_dir=input_dir, output_dir=output_dir, codex_home=required_home
    )
    if codex_js.name != "codex.js":
        raise GoldAuditError("unexpected Codex entry point")
    command.extend(
        [
            "/tmp/codex-node/bin/node",
            "/tmp/codex-node/lib/node_modules/@openai/codex/bin/codex.js",
            "exec",
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
            "--strict-config",
            "--skip-git-repo-check",
            "--sandbox",
            "read-only",
            "--cd",
            "/tmp/work",
            "--model",
            model,
            "--config",
            f'model_reasoning_effort="{reasoning_effort}"',
            "--config",
            f'model_verbosity="{verbosity}"',
            "--config",
            'service_tier="default"',
            "--config",
            'web_search="disabled"',
        ]
    )
    disabled = set(plain_runner.DISABLED_FEATURES) | set(TOOL_FREE_DISABLED_FEATURES)
    for feature in sorted(disabled):
        command.extend(["--config", f"features.{feature}=false"])
    command.extend(
        [
            "--json",
            "--output-schema",
            "/tmp/work/input/output_schema.json",
            "--output-last-message",
            "/tmp/work/output/model_response.json",
            "-",
        ]
    )
    verify_tool_free_command(command)
    return command


def verify_tool_free_command(command: Sequence[str]) -> None:
    required = {
        "--ephemeral",
        "--ignore-user-config",
        "--ignore-rules",
        "--strict-config",
        "read-only",
        'web_search="disabled"',
        "features.shell_tool=false",
        "features.unified_exec=false",
        "features.code_mode=false",
        "features.code_mode_host=false",
        "features.apps=false",
        "features.plugins=false",
        "features.skill_search=false",
        "features.multi_agent=false",
        "features.multi_agent_v2=false",
        "--output-schema",
    }
    missing = sorted(required - set(command))
    if missing:
        raise GoldAuditError(f"tool-free Codex command is missing controls: {missing}")
    forbidden = {"--search", "danger-full-access", "features.shell_tool=true"}
    present = sorted(forbidden & set(command))
    if present:
        raise GoldAuditError(f"tool-free Codex command contains forbidden controls: {present}")
    expected_feature_configs = {
        f"features.{feature}=false" for feature in TOOL_FREE_DISABLED_FEATURES
    }
    missing_features = sorted(expected_feature_configs - set(command))
    enabled_features = sorted(
        item
        for item in command
        if isinstance(item, str)
        and item.startswith("features.")
        and item.endswith("=true")
    )
    if missing_features or enabled_features:
        raise GoldAuditError(
            "tool-free Codex feature controls mismatch: "
            f"missing={missing_features}, enabled={enabled_features}"
        )
    for option, expected in (
        ("--sandbox", "read-only"),
        ("--output-schema", "/tmp/work/input/output_schema.json"),
        ("--output-last-message", "/tmp/work/output/model_response.json"),
    ):
        if command.count(option) != 1:
            raise GoldAuditError(f"tool-free Codex command must contain exactly one {option}")
        position = command.index(option)
        if position + 1 >= len(command) or command[position + 1] != expected:
            raise GoldAuditError(f"tool-free Codex command has invalid {option} target")
    if not command or command[-1] != "-":
        raise GoldAuditError("tool-free Codex command must read the sole prompt from stdin")


def stdin_prompt(*, instructions: str, packet_rows: Sequence[Mapping[str, str]]) -> bytes:
    payload = {"auditPacket": [dict(row) for row in packet_rows]}
    return (
        instructions.rstrip()
        + "\n\nAUDIT_PACKET_JSON:\n"
        + canonical_json_bytes(payload).decode("utf-8")
        + "\n"
    ).encode("utf-8")


def deterministic_order(ids: Sequence[str], *, profile: str, seed: str) -> list[str]:
    return sorted(
        ids,
        key=lambda case_id: (
            hashlib.sha256(f"{seed}\0{profile}\0{case_id}".encode("utf-8")).hexdigest(),
            case_id,
        ),
    )


def chunks(values: Sequence[str], size: int) -> list[list[str]]:
    if size <= 0:
        raise GoldAuditError("shard size must be positive")
    return [list(values[start : start + size]) for start in range(0, len(values), size)]


def audit_instructions(*, profile: str) -> str:
    return f"""# Blind Korean court-holding gold audit — profile {profile}

You are an independent gold-label auditor. You receive only opaque case IDs and
the exact court holding (주문). You do not have the parser label, sampling quota,
other auditors' work, source identity, candidate solver output, or benchmark
prediction. Do not try to obtain any of them.

The complete packet is embedded below this instruction. Read every row in its
given order and return exactly one JSON object with the sole key `judgments`.
Its value must contain exactly one row per input, preserving IDs and order.
Do not call or use any tool. Every judgment row must contain exactly:

`id`, `eligible`, `label`, `exactHoldingQuote`, `flags`, `rationale`.

- `eligible` is a JSON boolean.
- `label` is exactly `인용됨`, `기각`, or `AMBIGUOUS`.
- Use `인용됨` when the target main claim or challenged tax disposition is
  granted or cancelled in whole or in part. A partial grant is still `인용됨`.
- Use `기각` only when the target main claim is wholly rejected or the
  challenged disposition is wholly maintained.
- Use `AMBIGUOUS` with `eligible=false` when the holding alone cannot safely
  establish that binary target, including a counterclaim-only result,
  dismissal without prejudice, settlement/reconciliation, appellate
  disposition, or genuinely unclear target.
- `flags` is a JSON list with no duplicates, using only:
  `partial_grant`, `counterclaim`, `dismissal_without_prejudice`, `settlement`,
  `appeal`, `unclear`. Use `[]` when none applies.
- `exactHoldingQuote` is copied byte-for-byte from the input holding. It must
  either contain at least 12 non-whitespace characters or be a complete
  numbered holding line with at least 8 non-whitespace characters. Do not
  normalize spaces or punctuation.
- `rationale` is a concise Korean explanation of at most 500 characters.

Coherence rules are strict. `eligible=true` requires a binary label and no
disqualifying flag. `eligible=false` requires `AMBIGUOUS` and at least one
disqualifying flag. `partial_grant` is compatible only with an eligible
`인용됨` judgment.

No shell, local code, files, web, MCP, apps, skills, database, or other tool is
available or permitted. Return only the required JSON object after validating
row count, IDs, order, and the exact schema.
"""


def profile_name(profile: str) -> str:
    try:
        return PROFILE_DIRS[profile.upper()]
    except KeyError as error:
        raise GoldAuditError(f"unsupported auditor profile: {profile!r}") from error


def _profile_execution(model: str, *, timeout_seconds: int) -> dict[str, Any]:
    if not isinstance(model, str) or not model.strip():
        raise GoldAuditError("auditor model must be a non-empty explicit model ID")
    if not isinstance(timeout_seconds, int) or isinstance(timeout_seconds, bool) or timeout_seconds <= 0:
        raise GoldAuditError("auditor timeout must be a positive integer")
    return {
        "model": model,
        "reasoningEffort": DEFAULT_REASONING_EFFORT,
        "verbosity": DEFAULT_VERBOSITY,
        "serviceTier": DEFAULT_SERVICE_TIER,
        "codexVersion": REQUIRED_CODEX_VERSION,
        "codexHome": str(DEFAULT_CODEX_HOME.resolve()),
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
        "disabledFeatures": sorted(TOOL_FREE_DISABLED_FEATURES),
        "disabledFeaturesSha256": canonical_digest(sorted(TOOL_FREE_DISABLED_FEATURES)),
        "attemptPolicy": dict(ATTEMPT_POLICY),
        "attemptEvidenceLimitation": ATTEMPT_EVIDENCE_LIMITATION,
    }


def create_profile(
    *,
    campaign_dir: Path,
    profile: str,
    packet_by_id: Mapping[str, Mapping[str, str]],
    ordered_ids: Sequence[str],
    model: str,
    shard_size: int,
    timeout_seconds: int,
    codex_home: Path,
    cli_base_identity: Mapping[str, Any],
    pre_call_anchor_file: str,
    source_freeze_sha256: str,
    implementations: Mapping[str, str],
) -> dict[str, Any]:
    profile = profile.upper()
    role_dir = campaign_dir / profile_name(profile)
    role_dir.mkdir(parents=True, exist_ok=False)
    shard_records: list[dict[str, Any]] = []
    instructions_text = audit_instructions(profile=profile)
    instructions = instructions_text.encode("utf-8")
    schema = output_schema()
    for shard_index, shard_ids in enumerate(chunks(list(ordered_ids), shard_size)):
        shard_name = f"shard_{shard_index:04d}"
        shard_dir = role_dir / shard_name
        input_dir = shard_dir / "input"
        output_dir = shard_dir / "output"
        input_dir.mkdir(parents=True)
        output_dir.mkdir()
        packet_rows = [dict(packet_by_id[case_id]) for case_id in shard_ids]
        packet_path = input_dir / "audit_packet.jsonl"
        ids_path = input_dir / "expected_ids.json"
        instructions_path = input_dir / "RUN_INSTRUCTIONS.md"
        schema_path = input_dir / "output_schema.json"
        prompt_path = input_dir / "stdin_prompt.txt"
        write_jsonl_exclusive(packet_path, packet_rows)
        write_json_exclusive(ids_path, {"count": len(shard_ids), "ids": list(shard_ids)})
        write_bytes_exclusive(instructions_path, instructions)
        write_json_exclusive(schema_path, schema)
        write_bytes_exclusive(
            prompt_path,
            stdin_prompt(instructions=instructions_text, packet_rows=packet_rows),
        )
        command = tool_free_codex_command(
            input_dir=input_dir,
            output_dir=output_dir,
            codex_home=codex_home,
            model=model,
            reasoning_effort=DEFAULT_REASONING_EFFORT,
            verbosity=DEFAULT_VERBOSITY,
        )
        cli_identity = cli_identity_for_command(cli_base_identity, command)
        freeze = {
            "schemaVersion": 1,
            "status": "prepared_no_model_calls",
            "protocol": SHARD_PROTOCOL,
            "profile": profile,
            "shardIndex": shard_index,
            "sourceFreezeSha256": source_freeze_sha256,
            "packetPath": "input/audit_packet.jsonl",
            "packetSha256": sha256_file(packet_path),
            "expectedIdsPath": "input/expected_ids.json",
            "expectedIdsFileSha256": sha256_file(ids_path),
            "expectedIdsSha256": canonical_digest(list(shard_ids)),
            "instructionsPath": "input/RUN_INSTRUCTIONS.md",
            "instructionsSha256": sha256_file(instructions_path),
            "stdinPromptPath": "input/stdin_prompt.txt",
            "stdinPromptSha256": sha256_file(prompt_path),
            "outputSchemaPath": "input/output_schema.json",
            "outputSchemaSha256": sha256_file(schema_path),
            "outputSchemaCanonicalSha256": canonical_digest(schema),
            "rows": len(shard_ids),
            "executionConfig": _profile_execution(model, timeout_seconds=timeout_seconds),
            "codexCli": cli_identity,
            "preCallAnchorFile": pre_call_anchor_file,
            "implementationHashes": dict(implementations),
        }
        freeze["freezeSha256"] = self_hash(freeze, key="freezeSha256")
        freeze_path = shard_dir / "freeze.json"
        write_json_exclusive(freeze_path, freeze)
        shard_records.append(
            {
                "index": shard_index,
                "path": shard_name,
                "rows": len(shard_ids),
                "expectedIdsSha256": freeze["expectedIdsSha256"],
                "stdinPromptSha256": freeze["stdinPromptSha256"],
                "outputSchemaSha256": freeze["outputSchemaSha256"],
                "commandSha256": cli_identity["commandSha256"],
                "freezeFileSha256": sha256_file(freeze_path),
                "freezeSha256": freeze["freezeSha256"],
            }
        )
    profile_freeze = {
        "schemaVersion": 1,
        "status": "prepared_no_model_calls",
        "protocol": PROFILE_PROTOCOL,
        "profile": profile,
        "sourceFreezeSha256": source_freeze_sha256,
        "rows": len(ordered_ids),
        "allIdsSha256": canonical_digest(list(ordered_ids)),
        "shardSize": shard_size,
        "shardCount": len(shard_records),
        "executionConfig": _profile_execution(model, timeout_seconds=timeout_seconds),
        "codexCliBaseIdentity": dict(cli_base_identity),
        "preCallAnchorFile": pre_call_anchor_file,
        "shards": shard_records,
    }
    profile_freeze["freezeSha256"] = self_hash(profile_freeze, key="freezeSha256")
    write_json_exclusive(role_dir / "profile_freeze.json", profile_freeze)
    return profile_freeze


PRECALL_ANCHOR_INSTRUCTIONS = (
    "Commit this exact hash-only file before any listed semantic model call. "
    "Pass that commit to the shard runner; rejected/partial attempts are not rerunnable."
)


def _expected_pre_call_anchor(
    *,
    campaign_dir: Path,
    stage: str,
    profiles: Sequence[str],
    extra_file_bindings: Mapping[str, Path] | None = None,
) -> dict[str, Any]:
    source_path = campaign_dir.resolve() / "source_freeze.json"
    source = load_source_freeze(campaign_dir)
    profile_rows: list[dict[str, Any]] = []
    for profile in profiles:
        profile = profile.upper()
        profile_path = campaign_dir.resolve() / profile_name(profile) / "profile_freeze.json"
        profile_freeze = load_profile_freeze(campaign_dir, profile)
        shard_rows: list[dict[str, Any]] = []
        for record in profile_freeze["shards"]:
            index = int(record["index"])
            freeze_path = shard_paths(campaign_dir, profile, index)["freeze"]
            freeze = load_json(freeze_path)
            shard_rows.append(
                {
                    "index": index,
                    "freezeFileSha256": sha256_file(freeze_path),
                    "freezeSha256": freeze["freezeSha256"],
                    "packetSha256": freeze["packetSha256"],
                    "expectedIdsFileSha256": freeze["expectedIdsFileSha256"],
                    "instructionsSha256": freeze["instructionsSha256"],
                    "stdinPromptSha256": freeze["stdinPromptSha256"],
                    "outputSchemaSha256": freeze["outputSchemaSha256"],
                    "commandSha256": freeze["codexCli"]["commandSha256"],
                    "rows": freeze["rows"],
                    "executionConfigSha256": canonical_digest(freeze["executionConfig"]),
                    "implementationHashesSha256": canonical_digest(
                        freeze["implementationHashes"]
                    ),
                }
            )
        profile_rows.append(
            {
                "profile": profile,
                "profileFreezeFileSha256": sha256_file(profile_path),
                "profileFreezeSha256": profile_freeze["freezeSha256"],
                "executionConfigSha256": canonical_digest(profile_freeze["executionConfig"]),
                "shards": shard_rows,
            }
        )
    extras: dict[str, str] = {}
    for name, path in sorted((extra_file_bindings or {}).items()):
        if path.is_symlink() or not path.is_file():
            raise GoldAuditError(f"pre-call anchor extra binding is missing: {path}")
        extras[name] = sha256_file(path)
    anchor = {
        "schemaVersion": 1,
        "status": "precall_hash_only_requires_git_commit",
        "protocol": PRECALL_ANCHOR_PROTOCOL,
        "stage": stage,
        "sourceFreezeFileSha256": sha256_file(source_path),
        "sourceFreezeSha256": source["freezeSha256"],
        "profiles": profile_rows,
        "extraFileSha256": extras,
        "instructions": PRECALL_ANCHOR_INSTRUCTIONS,
    }
    anchor["anchorSha256"] = self_hash(anchor, key="anchorSha256")
    return anchor


def build_pre_call_anchor(
    *,
    campaign_dir: Path,
    stage: str,
    profiles: Sequence[str],
    file_name: str,
    extra_file_bindings: Mapping[str, Path] | None = None,
) -> dict[str, Any]:
    """Write a shareable hash-only manifest that must be Git-anchored."""

    anchor = _expected_pre_call_anchor(
        campaign_dir=campaign_dir,
        stage=stage,
        profiles=profiles,
        extra_file_bindings=extra_file_bindings,
    )
    write_json_exclusive(campaign_dir.resolve() / file_name, anchor)
    return anchor


def load_pre_call_anchor(campaign_dir: Path, file_name: str) -> dict[str, Any]:
    path = campaign_dir.resolve() / file_name
    anchor = load_json(path)
    if anchor.get("protocol") != PRECALL_ANCHOR_PROTOCOL:
        raise GoldAuditError("unsupported pre-call anchor protocol")
    verify_self_hash(anchor, key="anchorSha256", location=str(path))
    return anchor


def verify_anchor_binds_shard(
    *, campaign_dir: Path, profile: str, shard_index: int, freeze: Mapping[str, Any]
) -> tuple[dict[str, Any], Path]:
    file_name = freeze.get("preCallAnchorFile")
    if not isinstance(file_name, str) or Path(file_name).name != file_name:
        raise GoldAuditError("shard pre-call anchor file declaration is invalid")
    anchor_path = campaign_dir.resolve() / file_name
    anchor = load_pre_call_anchor(campaign_dir, file_name)
    if file_name == "precall_anchor_ab.json":
        expected_anchor = _expected_pre_call_anchor(
            campaign_dir=campaign_dir,
            stage="AB",
            profiles=("A", "B"),
            extra_file_bindings={
                "preparationReceipt": campaign_dir.resolve()
                / "preparation_receipt.json"
            },
        )
    elif file_name == "precall_anchor_c.json":
        expected_anchor = _expected_pre_call_anchor(
            campaign_dir=campaign_dir,
            stage="C",
            profiles=("C",),
            extra_file_bindings={
                "comparisonReport": campaign_dir.resolve()
                / "comparison/comparison.json"
            },
        )
    else:  # filename was already constrained to one path component
        raise GoldAuditError(f"unsupported pre-call anchor file: {file_name}")
    if anchor != expected_anchor:
        raise GoldAuditError("pre-call anchor does not exactly bind the full live campaign stage")
    profile_rows = anchor.get("profiles")
    if not isinstance(profile_rows, list):
        raise GoldAuditError("pre-call anchor profile inventory is malformed")
    matches = [row for row in profile_rows if isinstance(row, dict) and row.get("profile") == profile]
    if len(matches) != 1:
        raise GoldAuditError(f"pre-call anchor does not uniquely bind profile {profile}")
    shard_rows = matches[0].get("shards")
    if not isinstance(shard_rows, list):
        raise GoldAuditError("pre-call anchor shard inventory is malformed")
    shard_matches = [
        row for row in shard_rows if isinstance(row, dict) and row.get("index") == shard_index
    ]
    if len(shard_matches) != 1:
        raise GoldAuditError("pre-call anchor does not uniquely bind the requested shard")
    expected = {
        "index": shard_index,
        "freezeFileSha256": sha256_file(shard_paths(campaign_dir, profile, shard_index)["freeze"]),
        "freezeSha256": freeze["freezeSha256"],
        "packetSha256": freeze["packetSha256"],
        "expectedIdsFileSha256": freeze["expectedIdsFileSha256"],
        "instructionsSha256": freeze["instructionsSha256"],
        "stdinPromptSha256": freeze["stdinPromptSha256"],
        "outputSchemaSha256": freeze["outputSchemaSha256"],
        "commandSha256": freeze["codexCli"]["commandSha256"],
        "rows": freeze["rows"],
        "executionConfigSha256": canonical_digest(freeze["executionConfig"]),
        "implementationHashesSha256": canonical_digest(freeze["implementationHashes"]),
    }
    if shard_matches[0] != expected:
        raise GoldAuditError("pre-call anchor shard binding differs from the live freeze")
    return anchor, anchor_path


def prepare_campaign(
    *,
    private_path: Path,
    manifest_path: Path,
    campaign_dir: Path,
    auditor_a_model: str,
    auditor_b_model: str,
    auditor_c_model: str,
    shard_size: int,
    timeout_seconds: int,
    codex_home: Path,
    order_seed: str,
    c_sample_seed: str,
) -> dict[str, Any]:
    if private_path.is_symlink() or not private_path.is_file():
        raise GoldAuditError(f"private reserve must be a regular non-symlink file: {private_path}")
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise GoldAuditError(f"source manifest must be a regular non-symlink file: {manifest_path}")
    private_path = private_path.resolve()
    manifest_path = manifest_path.resolve()
    campaign_dir = campaign_dir.resolve()
    codex_home = codex_home.resolve()
    if codex_home != DEFAULT_CODEX_HOME.resolve():
        raise GoldAuditError(
            f"gold audit requires exact CODEX_HOME {DEFAULT_CODEX_HOME.resolve()}"
        )
    if campaign_dir.exists():
        raise GoldAuditError(f"refusing to overwrite existing campaign: {campaign_dir}")
    private_before = private_path.stat()
    manifest_before = manifest_path.stat()
    public_rows, rows, manifest, public_path = validate_source_inventory(
        private_path=private_path, manifest_path=manifest_path
    )
    public_before = public_path.stat()
    if shard_size <= 0:
        raise GoldAuditError("shard size must be positive")
    if not order_seed or not c_sample_seed:
        raise GoldAuditError("order and C-sample seeds must be non-empty")
    profile_configs = {
        "A": _profile_execution(auditor_a_model, timeout_seconds=timeout_seconds),
        "B": _profile_execution(auditor_b_model, timeout_seconds=timeout_seconds),
        "C": _profile_execution(auditor_c_model, timeout_seconds=timeout_seconds),
    }
    implementations = implementation_hashes()
    cli_base_identity = tool_free_cli_base_identity()
    private_hash = sha256_file(private_path)
    public_hash = sha256_file(public_path)
    manifest_file_hash = sha256_file(manifest_path)
    private_after = private_path.stat()
    manifest_after = manifest_path.stat()
    if (private_before.st_size, private_before.st_mtime_ns) != (
        private_after.st_size,
        private_after.st_mtime_ns,
    ):
        raise GoldAuditError("private reserve changed during audit preparation")
    if (manifest_before.st_size, manifest_before.st_mtime_ns) != (
        manifest_after.st_size,
        manifest_after.st_mtime_ns,
    ):
        raise GoldAuditError("source manifest changed during audit preparation")
    public_after = public_path.stat()
    if (public_before.st_size, public_before.st_mtime_ns) != (
        public_after.st_size,
        public_after.st_mtime_ns,
    ):
        raise GoldAuditError("public reserve changed during audit preparation")
    if private_hash != manifest["artifacts"]["private"]["sha256"]:
        raise GoldAuditError("private reserve changed after manifest validation")
    if public_hash != manifest["artifacts"]["public"]["sha256"]:
        raise GoldAuditError("public reserve changed after manifest validation")
    ids = [str(row["caseId"]) for row in rows]
    packet_by_id = {
        str(row["caseId"]): {"id": str(row["caseId"]), "holding": str(row["holding"])}
        for row in rows
    }
    campaign_dir.mkdir(parents=True, exist_ok=False)
    source_freeze = {
        "schemaVersion": 1,
        "status": "prepared_no_model_calls",
        "protocol": PROTOCOL,
        "privacyClassification": "PRIVATE_GOLD_CONTROL_NEVER_STAGE_TO_SOLVER",
        "sourceManifestPath": str(manifest_path),
        "sourceManifestFileSha256": manifest_file_hash,
        "sourceManifestSelfHash": manifest["selfHash"],
        "sourcePrivatePath": str(private_path),
        "sourcePrivateSha256": private_hash,
        "sourcePrivateBytes": private_path.stat().st_size,
        "sourcePublicPath": str(public_path),
        "sourcePublicSha256": public_hash,
        "sourcePublicBytes": public_path.stat().st_size,
        "sourceRows": len(rows),
        "sourceIdsSha256": canonical_digest(ids),
        "blindPacketSchema": ["id", "holding"],
        "prohibitedAuditorFields": [
            "label",
            "domain",
            "quota",
            "canonicalId",
            "caseRef",
            "sourceDataset",
            "solverOutput",
        ],
        "orderAlgorithm": "SHA256(orderSeed\\0profile\\0id), then id",
        "orderSeed": order_seed,
        "orderSeedSha256": sha256_bytes(order_seed.encode("utf-8")),
        "cAgreementAuditFraction": CANONICAL_C_AGREEMENT_AUDIT_FRACTION,
        "cAgreementAuditCountRule": CANONICAL_C_AGREEMENT_COUNT_RULE,
        "cAgreementSampleAlgorithm": "lowest SHA256(cSampleSeed\\0id), then id",
        "cSampleSeed": c_sample_seed,
        "cSampleSeedSha256": sha256_bytes(c_sample_seed.encode("utf-8")),
        "shardSize": shard_size,
        "minimumABKappa": DEFAULT_MINIMUM_KAPPA,
        "bootstrap": dict(CANONICAL_BOOTSTRAP_CONFIG),
        "selectionSizeRule": {
            **CANONICAL_SELECTION_SIZE_RULE,
            "civil": dict(CANONICAL_SELECTION_SIZE_RULE["civil"]),
            "tax": dict(CANONICAL_SELECTION_SIZE_RULE["tax"]),
            "possibleFinalRows": dict(
                CANONICAL_SELECTION_SIZE_RULE["possibleFinalRows"]
            ),
        },
        "attemptPolicy": dict(ATTEMPT_POLICY),
        "attemptEvidenceLimitation": ATTEMPT_EVIDENCE_LIMITATION,
        "outputSchemaCanonicalSha256": canonical_digest(output_schema()),
        "codexCliBaseIdentity": cli_base_identity,
        "preCallAnchorFiles": {"AB": "precall_anchor_ab.json", "C": "precall_anchor_c.json"},
        "executionProfiles": profile_configs,
        "implementationHashes": dict(implementations),
    }
    source_freeze["freezeSha256"] = self_hash(source_freeze, key="freezeSha256")
    source_freeze_path = campaign_dir / "source_freeze.json"
    write_json_exclusive(source_freeze_path, source_freeze)
    # A and B receive the same complete item set but independent deterministic
    # orderings.  C is created only after A/B outputs are frozen.
    profiles: dict[str, Any] = {}
    for profile, model in (("A", auditor_a_model), ("B", auditor_b_model)):
        ordered = deterministic_order(ids, profile=profile, seed=order_seed)
        profiles[profile] = create_profile(
            campaign_dir=campaign_dir,
            profile=profile,
            packet_by_id=packet_by_id,
            ordered_ids=ordered,
            model=model,
            shard_size=shard_size,
            timeout_seconds=timeout_seconds,
            codex_home=codex_home,
            cli_base_identity=cli_base_identity,
            pre_call_anchor_file="precall_anchor_ab.json",
            source_freeze_sha256=source_freeze["freezeSha256"],
            implementations=implementations,
        )
    if (
        sha256_file(private_path) != private_hash
        or sha256_file(public_path) != public_hash
        or sha256_file(manifest_path) != manifest_file_hash
    ):
        raise GoldAuditError("source public/private reserve or manifest changed after shard preparation")
    preparation_receipt = {
        "schemaVersion": 1,
        "status": "prepared_no_model_calls",
        "protocol": PROTOCOL,
        "semanticModelInvocations": 0,
        "sourceFreezeFileSha256": sha256_file(source_freeze_path),
        "sourceFreezeSha256": source_freeze["freezeSha256"],
        "profileFreezeFileSha256": {
            profile: sha256_file(campaign_dir / profile_name(profile) / "profile_freeze.json")
            for profile in ("A", "B")
        },
        "rows": len(ids),
        "shards": {profile: profiles[profile]["shardCount"] for profile in ("A", "B")},
    }
    preparation_receipt["receiptSha256"] = self_hash(
        preparation_receipt, key="receiptSha256"
    )
    preparation_path = campaign_dir / "preparation_receipt.json"
    write_json_exclusive(preparation_path, preparation_receipt)
    anchor = build_pre_call_anchor(
        campaign_dir=campaign_dir,
        stage="AB",
        profiles=("A", "B"),
        file_name="precall_anchor_ab.json",
        extra_file_bindings={"preparationReceipt": preparation_path},
    )
    return {
        **preparation_receipt,
        "preCallAnchorFile": "precall_anchor_ab.json",
        "preCallAnchorFileSha256": sha256_file(campaign_dir / "precall_anchor_ab.json"),
        "preCallAnchorSha256": anchor["anchorSha256"],
        "nextRequiredAction": "commit exact pre-call anchor and frozen implementation before model calls",
    }


def validate_packet_rows(rows: Sequence[Mapping[str, Any]], *, expected_ids: Sequence[str]) -> None:
    ids: list[str] = []
    for index, row in enumerate(rows):
        if set(row) != PACKET_KEYS:
            raise GoldAuditError(f"blind packet row {index} does not have exact id+holding schema")
        case_id = row.get("id")
        holding = row.get("holding")
        if not isinstance(case_id, str) or not case_id:
            raise GoldAuditError(f"blind packet row {index} has invalid id")
        if not isinstance(holding, str) or not holding.strip():
            raise GoldAuditError(f"blind packet row {index} has empty holding")
        ids.append(case_id)
    if ids != list(expected_ids):
        raise GoldAuditError("blind packet IDs/order do not match the frozen expected IDs")


NUMBERED_HOLDING_LINE = re.compile(
    r"^\s*(?:제\s*\d+(?:\s*의\s*\d+)?\s*항|\d+(?:\s*의\s*\d+)?[.)]|[가-힣][.)])\s*\S.+$"
)


def meaningful_exact_quote(holding: str, quote: str) -> bool:
    """Frozen evidence rule: exact 12-char span or a complete numbered line.

    Character counts exclude whitespace.  The shorter-line exception requires
    byte-for-byte equality after trimming only the line boundary whitespace,
    an explicit enumerator, and at least eight non-whitespace characters.
    """

    if not quote or quote not in holding:
        return False
    nonspace = len(re.sub(r"\s+", "", quote))
    if nonspace >= 12:
        return True
    quote_stripped = quote.strip()
    if nonspace < 8 or not NUMBERED_HOLDING_LINE.fullmatch(quote_stripped):
        return False
    return any(quote_stripped == line.strip() for line in holding.splitlines())


def judgment_core(row: Mapping[str, Any]) -> tuple[bool, str]:
    return bool(row["eligible"]), str(row["label"])


def validate_judgment_rows(
    *,
    packet_rows: Sequence[Mapping[str, Any]],
    judgment_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    errors: list[str] = []
    if len(packet_rows) != len(judgment_rows):
        errors.append(
            f"row_count_mismatch:expected={len(packet_rows)}:observed={len(judgment_rows)}"
        )
    for index, packet in enumerate(packet_rows):
        if index >= len(judgment_rows):
            break
        row = judgment_rows[index]
        case_id = str(packet.get("id") or "")
        if set(row) != JUDGMENT_KEYS:
            errors.append(f"{case_id}:exact_schema_mismatch")
            continue
        if row.get("id") != case_id:
            errors.append(f"{case_id}:id_or_order_mismatch")
        eligible = row.get("eligible")
        label = row.get("label")
        quote = row.get("exactHoldingQuote")
        flags = row.get("flags")
        rationale = row.get("rationale")
        if type(eligible) is not bool:  # bool only; reject truthy ints/strings
            errors.append(f"{case_id}:eligible_not_boolean")
        if label not in LABELS:
            errors.append(f"{case_id}:invalid_label")
        holding = packet.get("holding")
        if (
            not isinstance(quote, str)
            or not isinstance(holding, str)
            or not meaningful_exact_quote(holding, quote)
        ):
            errors.append(f"{case_id}:quote_not_meaningful_exact_span")
        if (
            not isinstance(flags, list)
            or any(not isinstance(flag, str) or flag not in FLAGS for flag in flags)
            or len(flags) != len(set(flags))
        ):
            errors.append(f"{case_id}:invalid_or_duplicate_flags")
            flags = []
        if not isinstance(rationale, str) or not rationale.strip() or len(rationale) > 500:
            errors.append(f"{case_id}:rationale_not_concise_nonempty")
        if type(eligible) is bool and label in LABELS:
            flag_set = set(flags) if isinstance(flags, list) else set()
            if eligible:
                if label not in PROVISIONAL_LABELS:
                    errors.append(f"{case_id}:eligible_requires_binary_label")
                if flag_set & DISQUALIFYING_FLAGS:
                    errors.append(f"{case_id}:eligible_has_disqualifying_flag")
                if "partial_grant" in flag_set and label != "인용됨":
                    errors.append(f"{case_id}:partial_grant_requires_granted_label")
            else:
                if label != "AMBIGUOUS":
                    errors.append(f"{case_id}:ineligible_requires_ambiguous_label")
                if not (flag_set & DISQUALIFYING_FLAGS):
                    errors.append(f"{case_id}:ineligible_requires_disqualifying_flag")
    if len(judgment_rows) > len(packet_rows):
        errors.append("unexpected_extra_rows")
    return {
        "passed": not errors,
        "errors": errors,
        "expectedRows": len(packet_rows),
        "observedRows": len(judgment_rows),
        "labelCounts": dict(
            sorted(Counter(str(row.get("label")) for row in judgment_rows).items())
        ),
        "eligibleRows": sum(row.get("eligible") is True for row in judgment_rows),
    }


def load_source_freeze(campaign_dir: Path) -> dict[str, Any]:
    path = campaign_dir.resolve() / "source_freeze.json"
    freeze = load_json(path)
    if freeze.get("protocol") != PROTOCOL:
        raise GoldAuditError("campaign source freeze has an unsupported protocol")
    verify_self_hash(freeze, key="freezeSha256", location=str(path))
    if freeze.get("minimumABKappa") != DEFAULT_MINIMUM_KAPPA:
        raise GoldAuditError("campaign source freeze weakens the canonical A/B kappa gate")
    if freeze.get("cAgreementAuditFraction") != CANONICAL_C_AGREEMENT_AUDIT_FRACTION:
        raise GoldAuditError("campaign source freeze changes the canonical C audit fraction")
    if freeze.get("cAgreementAuditCountRule") != CANONICAL_C_AGREEMENT_COUNT_RULE:
        raise GoldAuditError("campaign source freeze changes the canonical C sample rule")
    if freeze.get("bootstrap") != CANONICAL_BOOTSTRAP_CONFIG:
        raise GoldAuditError("campaign source freeze changes the canonical bootstrap contract")
    if freeze.get("selectionSizeRule") != CANONICAL_SELECTION_SIZE_RULE:
        raise GoldAuditError("campaign source freeze changes the canonical final-size contract")
    if freeze.get("attemptPolicy") != ATTEMPT_POLICY:
        raise GoldAuditError("campaign source freeze changes the canonical first-attempt policy")
    return freeze


def shard_paths(campaign_dir: Path, profile: str, shard_index: int) -> dict[str, Path]:
    shard_dir = (
        campaign_dir.resolve()
        / profile_name(profile.upper())
        / f"shard_{shard_index:04d}"
    )
    input_dir = shard_dir / "input"
    output_dir = shard_dir / "output"
    return {
        "shardDir": shard_dir,
        "inputDir": input_dir,
        "outputDir": output_dir,
        "freeze": shard_dir / "freeze.json",
        "packet": input_dir / "audit_packet.jsonl",
        "expectedIds": input_dir / "expected_ids.json",
        "instructions": input_dir / "RUN_INSTRUCTIONS.md",
        "stdinPrompt": input_dir / "stdin_prompt.txt",
        "outputSchema": input_dir / "output_schema.json",
        "judgments": output_dir / "judgments.jsonl",
        "modelResponse": output_dir / "model_response.json",
        "trace": shard_dir / "codex_trace.jsonl",
        "stderr": shard_dir / "codex_stderr.txt",
        "attemptRegistry": shard_dir / "attempt_registry.jsonl",
        "receipt": shard_dir / "run_receipt.json",
        "validation": shard_dir / "judgment_validation.json",
    }


def verify_shard_bundle(
    campaign_dir: Path, profile: str, shard_index: int
) -> tuple[dict[str, Any], dict[str, Path], list[dict[str, Any]], list[str]]:
    profile = profile.upper()
    source = load_source_freeze(campaign_dir)
    paths = shard_paths(campaign_dir, profile, shard_index)
    for key in ("shardDir", "inputDir", "outputDir"):
        if not paths[key].is_dir():
            raise GoldAuditError(f"prepared shard directory is missing: {paths[key]}")
    freeze = load_json(paths["freeze"])
    if freeze.get("protocol") != SHARD_PROTOCOL or freeze.get("profile") != profile:
        raise GoldAuditError("unsupported shard protocol or profile")
    if freeze.get("shardIndex") != shard_index:
        raise GoldAuditError("shard index mismatch")
    verify_self_hash(freeze, key="freezeSha256", location=str(paths["freeze"]))
    if freeze.get("sourceFreezeSha256") != source.get("freezeSha256"):
        raise GoldAuditError("shard/source freeze mismatch")
    expected_payload = load_json(paths["expectedIds"])
    ids = expected_payload.get("ids")
    if (
        not isinstance(ids, list)
        or any(not isinstance(case_id, str) or not case_id for case_id in ids)
        or len(ids) != len(set(ids))
        or expected_payload.get("count") != len(ids)
    ):
        raise GoldAuditError("malformed expected_ids.json")
    checks = {
        "packetSha256": sha256_file(paths["packet"]),
        "expectedIdsFileSha256": sha256_file(paths["expectedIds"]),
        "instructionsSha256": sha256_file(paths["instructions"]),
        "stdinPromptSha256": sha256_file(paths["stdinPrompt"]),
        "outputSchemaSha256": sha256_file(paths["outputSchema"]),
    }
    for key, observed in checks.items():
        if freeze.get(key) != observed:
            raise GoldAuditError(f"frozen shard input hash mismatch: {key}")
    if freeze.get("expectedIdsSha256") != canonical_digest(ids):
        raise GoldAuditError("frozen expected IDs digest mismatch")
    if freeze.get("rows") != len(ids):
        raise GoldAuditError("frozen shard row count mismatch")
    packet = load_jsonl(paths["packet"])
    validate_packet_rows(packet, expected_ids=ids)
    schema = load_json(paths["outputSchema"])
    if schema != output_schema() or freeze.get("outputSchemaCanonicalSha256") != canonical_digest(schema):
        raise GoldAuditError("frozen output schema differs from the canonical gold-audit schema")
    expected_prompt = stdin_prompt(
        instructions=paths["instructions"].read_text(encoding="utf-8"),
        packet_rows=packet,
    )
    if paths["stdinPrompt"].read_bytes() != expected_prompt:
        raise GoldAuditError("frozen stdin prompt is not the canonical instruction+packet rendering")
    hashes = freeze.get("implementationHashes")
    if not isinstance(hashes, dict) or set(hashes) != {
        str(path.resolve()) for path in implementation_paths()
    }:
        raise GoldAuditError("shard has an incomplete implementation hash set")
    for raw_path, expected_hash in hashes.items():
        path = Path(raw_path)
        if not path.is_file() or sha256_file(path) != expected_hash:
            raise GoldAuditError(f"frozen implementation hash mismatch: {path}")
    config = freeze.get("executionConfig")
    if not isinstance(config, dict) or config.get("codexHome") != str(DEFAULT_CODEX_HOME.resolve()):
        raise GoldAuditError("shard does not freeze the required CODEX_HOME")
    command = tool_free_codex_command(
        input_dir=paths["inputDir"],
        output_dir=paths["outputDir"],
        codex_home=DEFAULT_CODEX_HOME,
        model=str(config.get("model") or ""),
        reasoning_effort=str(config.get("reasoningEffort") or ""),
        verbosity=str(config.get("verbosity") or ""),
    )
    expected_cli = cli_identity_for_command(
        load_source_freeze(campaign_dir)["codexCliBaseIdentity"], command
    )
    if freeze.get("codexCli") != expected_cli:
        raise GoldAuditError("shard Codex command/CLI identity mismatch")
    verify_cli_binary_identity(expected_cli)
    return freeze, paths, packet, list(ids)


def load_profile_freeze(campaign_dir: Path, profile: str) -> dict[str, Any]:
    profile = profile.upper()
    path = campaign_dir.resolve() / profile_name(profile) / "profile_freeze.json"
    freeze = load_json(path)
    if freeze.get("protocol") != PROFILE_PROTOCOL or freeze.get("profile") != profile:
        raise GoldAuditError(f"invalid {profile} profile freeze")
    verify_self_hash(freeze, key="freezeSha256", location=str(path))
    source = load_source_freeze(campaign_dir)
    if freeze.get("sourceFreezeSha256") != source.get("freezeSha256"):
        raise GoldAuditError(f"{profile} profile/source freeze mismatch")
    shards = freeze.get("shards")
    if not isinstance(shards, list) or freeze.get("shardCount") != len(shards) or not shards:
        raise GoldAuditError(f"{profile} profile shard inventory is malformed")
    if [row.get("index") for row in shards if isinstance(row, dict)] != list(range(len(shards))):
        raise GoldAuditError(f"{profile} profile shard indices are not contiguous")
    return freeze


def receipt_digest(receipt: Mapping[str, Any]) -> str:
    return self_hash(receipt, key="receiptSha256")


def load_accepted_profile(
    campaign_dir: Path, profile: str
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, str]], dict[str, Any]]:
    """Load an immutable accepted profile and revalidate every output row."""

    # Import lazily to avoid a module cycle: the shard runner imports this
    # module, while aggregation must independently replay its trusted trace
    # policy before treating a receipt as accepted evidence.
    from tools import run_outcome_gold_auditor as runner

    profile = profile.upper()
    profile_freeze = load_profile_freeze(campaign_dir, profile)
    judgments: dict[str, dict[str, Any]] = {}
    packets: dict[str, dict[str, str]] = {}
    ordered_ids: list[str] = []
    receipt_hashes: list[str] = []
    output_hashes: list[str] = []
    token_totals: Counter[str] = Counter()
    elapsed = 0.0
    for shard_record in profile_freeze["shards"]:
        index = int(shard_record["index"])
        freeze, paths, packet_rows, ids = verify_shard_bundle(
            campaign_dir, profile, index
        )
        if sha256_file(paths["freeze"]) != shard_record.get("freezeFileSha256"):
            raise GoldAuditError(f"{profile}/{index} freeze file hash mismatch")
        if freeze.get("freezeSha256") != shard_record.get("freezeSha256"):
            raise GoldAuditError(f"{profile}/{index} freeze self-hash binding mismatch")
        if shard_record.get("path") != f"shard_{index:04d}":
            raise GoldAuditError(f"{profile}/{index} shard path binding mismatch")
        if shard_record.get("rows") != len(ids):
            raise GoldAuditError(f"{profile}/{index} shard row-count binding mismatch")
        if shard_record.get("expectedIdsSha256") != freeze.get("expectedIdsSha256"):
            raise GoldAuditError(f"{profile}/{index} expected-ID binding mismatch")
        for key in ("stdinPromptSha256", "outputSchemaSha256"):
            if shard_record.get(key) != freeze.get(key):
                raise GoldAuditError(f"{profile}/{index} {key} binding mismatch")
        if shard_record.get("commandSha256") != freeze.get("codexCli", {}).get(
            "commandSha256"
        ):
            raise GoldAuditError(f"{profile}/{index} command binding mismatch")
        receipt = load_json(paths["receipt"])
        verify_self_hash(receipt, key="receiptSha256", location=str(paths["receipt"]))
        if receipt.get("status") != "accepted" or receipt.get("semanticModelInvocations") != 1:
            raise GoldAuditError(f"{profile}/{index} does not have an accepted one-call receipt")
        if receipt.get("protocol") != SHARD_PROTOCOL:
            raise GoldAuditError(f"{profile}/{index} receipt protocol mismatch")
        if receipt.get("profile") != profile or receipt.get("shardIndex") != index:
            raise GoldAuditError(f"{profile}/{index} receipt identity mismatch")
        if receipt.get("freezeSha256") != freeze.get("freezeSha256"):
            raise GoldAuditError(f"{profile}/{index} receipt/freeze mismatch")
        if (
            receipt.get("acceptedArtifact") != "output/model_response.json"
            or receipt.get("derivedArtifact") != "output/judgments.jsonl"
        ):
            raise GoldAuditError(f"{profile}/{index} accepted artifact declaration mismatch")
        expected_input_hashes = {
            "auditPacketSha256": sha256_file(paths["packet"]),
            "expectedIdsFileSha256": sha256_file(paths["expectedIds"]),
            "instructionsSha256": sha256_file(paths["instructions"]),
            "stdinPromptSha256": sha256_file(paths["stdinPrompt"]),
            "outputSchemaSha256": sha256_file(paths["outputSchema"]),
        }
        if receipt.get("inputFileSha256") != expected_input_hashes:
            raise GoldAuditError(f"{profile}/{index} receipt input hashes mismatch")
        if receipt.get("executionConfig") != freeze.get("executionConfig"):
            raise GoldAuditError(f"{profile}/{index} receipt execution config mismatch")
        if receipt.get("implementationHashes") != freeze.get("implementationHashes"):
            raise GoldAuditError(f"{profile}/{index} receipt implementation hashes mismatch")
        if receipt.get("codexCli") != freeze.get("codexCli"):
            raise GoldAuditError(f"{profile}/{index} Codex CLI/command identity mismatch")
        pre_call = receipt.get("preCallGitAnchor")
        if not isinstance(pre_call, dict) or not isinstance(pre_call.get("commit"), str):
            raise GoldAuditError(f"{profile}/{index} pre-call Git anchor is missing")
        replayed_anchor = runner.verify_git_anchor(
            campaign_dir=campaign_dir,
            profile=profile,
            shard_index=index,
            freeze=freeze,
            commit=pre_call["commit"],
        )
        if replayed_anchor != pre_call:
            raise GoldAuditError(f"{profile}/{index} pre-call Git anchor changed")
        process = receipt.get("process")
        if (
            not isinstance(process, dict)
            or process.get("exitCode") != 0
            or process.get("timedOut") is not False
            or not isinstance(process.get("elapsedSeconds"), (int, float))
            or float(process["elapsedSeconds"]) < 0
        ):
            raise GoldAuditError(f"{profile}/{index} accepted process record is invalid")
        stored_policy = receipt.get("policyAudit")
        if not isinstance(stored_policy, dict) or stored_policy.get("passed") is not True:
            raise GoldAuditError(f"{profile}/{index} stored trace policy is not accepted")
        stored_validation = receipt.get("artifactValidation")
        if not isinstance(stored_validation, dict) or stored_validation.get("passed") is not True:
            raise GoldAuditError(f"{profile}/{index} stored artifact validation is not accepted")
        outer = receipt.get("outerContainmentProbe")
        if (
            not isinstance(outer, dict)
            or outer.get("passed") is not True
            or outer.get("authMountedInCliNamespace") is not True
            or outer.get("authUnmountedClaim") is not False
            or outer.get("enumeratedModelToolSurfacesConfiguredDisabled") is not True
            or outer.get("modelToolSchemaAdvertisementIndependentlyAttested") is not False
            or outer.get("zeroToolEventsObservedInAcceptedRawTrace") is not True
        ):
            raise GoldAuditError(f"{profile}/{index} outer/tool-free boundary record is invalid")
        artifacts = receipt.get("artifacts")
        if not isinstance(artifacts, dict):
            raise GoldAuditError(f"{profile}/{index} receipt artifacts are missing")
        for artifact_key, path in (
            ("judgmentsSha256", paths["judgments"]),
            ("rawTraceSha256", paths["trace"]),
            ("stderrSha256", paths["stderr"]),
            ("modelResponseSha256", paths["modelResponse"]),
            ("attemptRegistrySha256", paths["attemptRegistry"]),
            ("validationSha256", paths["validation"]),
        ):
            if not path.is_file() or artifacts.get(artifact_key) != sha256_file(path):
                raise GoldAuditError(f"{profile}/{index} accepted artifact hash mismatch: {artifact_key}")
        replayed_validation = runner.validate_output(
            paths, packet_rows, write_derived=False
        )
        if not replayed_validation["passed"]:
            raise GoldAuditError(
                f"{profile}/{index} judgment revalidation failed: "
                f"{replayed_validation['errors'][:3]}"
            )
        stored_validation_file = load_json(paths["validation"])
        if stored_validation_file != stored_validation or stored_validation != replayed_validation:
            raise GoldAuditError(f"{profile}/{index} validation report/receipt mismatch")
        replayed_policy = runner.audit_tool_free_trace(
            trace_path=paths["trace"],
            questions_path=paths["packet"],
            model_response_path=paths["modelResponse"],
            return_code=0,
        )
        if replayed_policy.get("passed") is not True:
            raise GoldAuditError(f"{profile}/{index} replayed trace policy rejected")
        if replayed_policy != stored_policy:
            raise GoldAuditError(f"{profile}/{index} stored/replayed trace policies differ")
        if artifacts.get("threadIds") != replayed_policy.get("threadIds"):
            raise GoldAuditError(f"{profile}/{index} replayed thread IDs mismatch")
        replayed_usage = runner._trace_token_usage(replayed_policy)
        if receipt.get("tokenUsage") != replayed_usage:
            raise GoldAuditError(f"{profile}/{index} token usage/trace mismatch")
        attempts = load_jsonl(paths["attemptRegistry"])
        start_keys = {
            "schemaVersion",
            "event",
            "attemptOrdinal",
            "semanticModelInvocationsBefore",
            "firstAttemptOnly",
            "freezeSha256",
            "preCallGitAnchor",
            "startedUtc",
        }
        finish_keys = {
            "schemaVersion",
            "event",
            "attemptOrdinal",
            "semanticModelInvocationsTotal",
            "freezeSha256",
            "status",
            "traceSha256",
            "modelResponseSha256",
            "finishedUtc",
        }
        if (
            len(attempts) != 2
            or set(attempts[0]) != start_keys
            or set(attempts[1]) != finish_keys
            or attempts[0].get("schemaVersion") != 1
            or attempts[1].get("schemaVersion") != 1
            or attempts[0].get("event") != "semantic_attempt_started"
            or attempts[1].get("event") != "semantic_attempt_finished"
            or attempts[0].get("attemptOrdinal") != 1
            or attempts[1].get("attemptOrdinal") != 1
            or attempts[0].get("semanticModelInvocationsBefore") != 0
            or attempts[0].get("firstAttemptOnly") is not True
            or attempts[0].get("freezeSha256") != freeze.get("freezeSha256")
            or attempts[1].get("freezeSha256") != freeze.get("freezeSha256")
            or attempts[0].get("preCallGitAnchor") != pre_call
            or receipt.get("attemptStart") != attempts[0]
            or not isinstance(attempts[0].get("startedUtc"), str)
            or not isinstance(attempts[1].get("finishedUtc"), str)
            or attempts[1].get("semanticModelInvocationsTotal") != 1
            or attempts[1].get("status") != "accepted"
            or attempts[1].get("traceSha256") != artifacts.get("rawTraceSha256")
            or attempts[1].get("modelResponseSha256")
            != artifacts.get("modelResponseSha256")
        ):
            raise GoldAuditError(f"{profile}/{index} attempt registry is invalid")
        output_rows = load_jsonl(paths["judgments"])
        for packet, judgment in zip(packet_rows, output_rows, strict=True):
            case_id = str(packet["id"])
            if case_id in judgments:
                raise GoldAuditError(f"duplicate ID across {profile} shards: {case_id}")
            judgments[case_id] = dict(judgment)
            packets[case_id] = {"id": case_id, "holding": str(packet["holding"])}
            ordered_ids.append(case_id)
        receipt_hashes.append(str(receipt["receiptSha256"]))
        output_hashes.append(str(artifacts["judgmentsSha256"]))
        usage = receipt.get("tokenUsage")
        if isinstance(usage, dict):
            for key, value in usage.items():
                if isinstance(value, int) and not isinstance(value, bool):
                    token_totals[key] += value
        elapsed += float(process["elapsedSeconds"])
    if len(judgments) != profile_freeze.get("rows"):
        raise GoldAuditError(f"{profile} accepted row count mismatch")
    if canonical_digest(ordered_ids) != profile_freeze.get("allIdsSha256"):
        raise GoldAuditError(f"{profile} accepted aggregate ID/order mismatch")
    evidence = {
        "profileFreezeSha256": profile_freeze["freezeSha256"],
        "profileFreezeFileSha256": sha256_file(
            campaign_dir.resolve() / profile_name(profile) / "profile_freeze.json"
        ),
        "receiptSha256": receipt_hashes,
        "judgmentsSha256": output_hashes,
        "semanticModelInvocations": len(receipt_hashes),
        "tokenUsage": dict(sorted(token_totals.items())),
        "elapsedSecondsSum": elapsed,
    }
    return judgments, packets, evidence


def cohen_kappa(categories_a: Sequence[str], categories_b: Sequence[str]) -> float | None:
    if len(categories_a) != len(categories_b) or not categories_a:
        raise GoldAuditError("kappa requires two non-empty equal-length sequences")
    total = len(categories_a)
    observed = sum(a == b for a, b in zip(categories_a, categories_b, strict=True)) / total
    counts_a = Counter(categories_a)
    counts_b = Counter(categories_b)
    categories = set(counts_a) | set(counts_b)
    expected = sum((counts_a[item] / total) * (counts_b[item] / total) for item in categories)
    if math.isclose(expected, 1.0):
        return None
    return (observed - expected) / (1.0 - expected)


def _quantile(values: Sequence[float], probability: float) -> float:
    if not values:
        raise GoldAuditError("quantile requires at least one value")
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def deterministic_kappa_bootstrap_ci(
    categories_a: Sequence[str],
    categories_b: Sequence[str],
    *,
    seed: str,
    replicates: int,
    confidence_level: float = 0.95,
) -> dict[str, Any]:
    if len(categories_a) != len(categories_b) or not categories_a:
        raise GoldAuditError("bootstrap requires two non-empty equal-length sequences")
    if replicates <= 0 or not 0.0 < confidence_level < 1.0:
        raise GoldAuditError("invalid deterministic bootstrap configuration")
    rng = random.Random(int(sha256_bytes(seed.encode("utf-8")), 16))
    estimates: list[float] = []
    n = len(categories_a)
    for _ in range(replicates):
        indices = [rng.randrange(n) for _ in range(n)]
        estimate = cohen_kappa(
            [categories_a[index] for index in indices],
            [categories_b[index] for index in indices],
        )
        if estimate is not None:
            estimates.append(estimate)
    alpha = (1.0 - confidence_level) / 2.0
    return {
        "method": "deterministic nonparametric row bootstrap percentile interval",
        "confidenceLevel": confidence_level,
        "requestedReplicates": replicates,
        "validReplicates": len(estimates),
        "degenerateReplicates": replicates - len(estimates),
        "seedSha256": sha256_bytes(seed.encode("utf-8")),
        "lower": _quantile(estimates, alpha) if estimates else None,
        "upper": _quantile(estimates, 1.0 - alpha) if estimates else None,
    }


def core_category(row: Mapping[str, Any]) -> str:
    eligible, label = judgment_core(row)
    return f"{'eligible' if eligible else 'ineligible'}:{label}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare sealed A/B outcome-gold audit shards without making model calls."
    )
    parser.add_argument("--private-jsonl", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--auditor-a-model", default=DEFAULT_MODELS["A"])
    parser.add_argument("--auditor-b-model", default=DEFAULT_MODELS["B"])
    parser.add_argument("--auditor-c-model", default=DEFAULT_MODELS["C"])
    parser.add_argument("--shard-size", type=int, default=DEFAULT_SHARD_SIZE)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--codex-home", type=Path, default=DEFAULT_CODEX_HOME)
    parser.add_argument("--order-seed", default=DEFAULT_ORDER_SEED)
    parser.add_argument("--c-sample-seed", default=DEFAULT_C_SAMPLE_SEED)
    args = parser.parse_args()
    result = prepare_campaign(
        private_path=args.private_jsonl,
        manifest_path=args.manifest,
        campaign_dir=args.campaign_dir,
        auditor_a_model=args.auditor_a_model,
        auditor_b_model=args.auditor_b_model,
        auditor_c_model=args.auditor_c_model,
        shard_size=args.shard_size,
        timeout_seconds=args.timeout_seconds,
        codex_home=args.codex_home,
        order_seed=args.order_seed,
        c_sample_seed=args.c_sample_seed,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
