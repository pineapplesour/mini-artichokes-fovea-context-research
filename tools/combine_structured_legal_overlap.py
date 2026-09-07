#!/usr/bin/env python3
"""Combine frozen structured legal generators without consulting gold.

This module is the deterministic single-sealed-shard mechanism core of the
fresh Mini-Artichokes legal overlap experiment.  It is not the final
campaign runner or cross-shard aggregator.  It consumes one frozen public
corpus, three ordered
structured generator artifacts, and a hash-bound role-blind outcome
comparison.  It validates every byte and every row before publishing five
complete policies.  No policy can synthesize a label: every emitted outcome
is copied from G1 or from the hash-selected G2/G3 proposal carrier.

The input contract intentionally separates two concerns:

* ``source_freeze.json`` is externally hash-pinned before any generator call.
  It binds the public corpus, builder/audit/opaque-ID receipts, generator
  packet, blind prompt/output-schema templates, derivation code, zero-tool
  settings, retry policy, ordered IDs, and deterministic rotation seeds.
* after G1--G3 are frozen but before BLIND, a second externally hash-pinned
  blind-package freeze binds their complete receipt chains, the derived ordered
  conflict package, instantiated blind stdin packet/output schema, and hidden
  role-map hash.  The source freeze never claims to know this later packet.
* an externally hash-pinned post-call ``campaign_manifest.json`` binds both
  freeze anchors and every prompt, output schema, raw first attempt, normalized
  artifact, trace, receipt, validation report, attempt/token ledger, and code
  hash.
* stage receipts must prove an stdin-embedded, strict-parsed, zero-tool run;
  legacy file-agent/bubblewrap receipts are ineligible.  Gold access and blind
  provenance are derived from these validated receipts rather than asserted by
  this combiner.

Authenticated first-attempt row failures are retained, emitted as null for
full-denominator scientific scoring, and given a separately named deployment
fallback.  Tampering or an unauthenticated artifact still rejects the campaign.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = "mini_artichokes_structured_legal_overlap_combination_v1"
SOURCE_FREEZE_PROTOCOL = "mini_artichokes_structured_legal_overlap_source_v1"
BLIND_RECEIPT_PROTOCOL = "mini_artichokes_structured_legal_overlap_blind_v1"
GENERATOR_RECEIPT_PROTOCOL = "mini_artichokes_structured_legal_generator_receipt_v1"
CAMPAIGN_MANIFEST_PROTOCOL = "mini_artichokes_structured_legal_campaign_manifest_v1"
ID_RECEIPT_PROTOCOL = "mini_artichokes_label_independent_id_receipt_v1"
PUBLIC_OUTCOME_AUDIT_PROTOCOL = "public-outcome-reserve-presolver-audit-v1"
BLIND_PACKAGE_FREEZE_PROTOCOL = "mini_artichokes_blind_package_freeze_v1"
FIRST_ATTEMPT_VALIDATION_PROTOCOL = "mini_artichokes_first_attempt_validation_v1"
ATTEMPT_LEDGER_PROTOCOL = "mini_artichokes_attempt_ledger_v1"
TOKEN_LEDGER_PROTOCOL = "mini_artichokes_token_ledger_v1"
SOURCE_FREEZE_STATUS = "frozen_before_generator_output"
CAMPAIGN_MANIFEST_STATUS = "frozen_before_combination_and_gold_open"
BLIND_PACKAGE_FREEZE_STATUS = "frozen_after_generators_before_blind_output"

GENERATOR_NAMES = ("G1", "G2", "G3")
OUTCOMES = {"인용됨", "기각", "ABSTAIN"}
ISSUE_CODES = {
    "REQUIRED_ELEMENT_PRESENT",
    "REQUIRED_ELEMENT_ABSENT",
    "RULE_OR_EXCEPTION_APPLIES",
    "BURDEN_OR_STANDARD_MET",
    "BURDEN_OR_STANDARD_NOT_MET",
    "REMEDY_OR_PROCEDURE_CONTROLS",
    "RECORD_CONTRADICTION",
    "UNSUPPORTED_INFERENCE",
}
DIRECTIONS = {"FAVORS_GRANT", "FAVORS_DISMISS"}
DIRECTION_FOR_OUTCOME = {
    "인용됨": "FAVORS_GRANT",
    "기각": "FAVORS_DISMISS",
}
BLIND_PREFERENCES = {"PREFER_LEFT", "PREFER_RIGHT", "TIE", "UNRESOLVED"}
ROLES = {"INCUMBENT", "PROPOSED"}
POLICIES = (
    "base",
    "answer_only",
    "answer_only_blind_veto",
    "structured_overlap",
    "structured_overlap_blind_veto",
)

PUBLIC_ROW_KEYS = {
    "id",
    "suite",
    "benchmarkId",
    "responseFormat",
    "language",
    "prompt",
}
GENERATOR_ROW_KEYS = {"id", "outcome", "rationale", "evidenceAtoms"}
ATOM_KEYS = {"issueCode", "evidenceClauseId", "exactQuote", "direction"}
CERTIFICATE_KEYS = {"id", "leftOutcome", "rightOutcome", "preference"}
ROLE_MAPPING_KEYS = {"id", "leftRole", "rightRole"}
SOURCE_FREEZE_KEYS = {
    "schemaVersion",
    "protocol",
    "status",
    "campaignId",
    "publicSha256",
    "publicBuilderManifestFileSha256",
    "publicBuilderManifestSelfHash",
    "labelIndependentIdReceiptFileSha256",
    "labelIndependentIdReceiptSha256",
    "conclusionLeakReportFileSha256",
    "conclusionLeakReportSha256",
    "expectedRows",
    "expectedIdsSha256",
    "publicConstants",
    "generatorPromptSha256",
    "blindPromptTemplateSha256",
    "generatorOutputSchemaSha256",
    "blindOutputSchemaTemplateSha256",
    "outputSchemaCliArg",
    "blindPackageContractSha256",
    "blindPackageDerivationCodeHashes",
    "generatorExecutionSettings",
    "blindExecutionSettings",
    "carrierSelectionSeed",
    "roleRotationSeed",
    "attemptPolicy",
    "requiredUpstreamReceiptHooks",
    "comparatorFairnessAuditRequired",
    "freezeSha256",
}
STAGE_RECEIPT_KEYS = {
    "schemaVersion",
    "protocol",
    "status",
    "stage",
    "stageKind",
    "campaignId",
    "sourceFreezeSha256",
    "publicArtifactSha256",
    "promptSha256",
    "outputSchemaSha256",
    "outputSchemaCliArg",
    "strictConfig",
    "configArgv",
    "configArgvSha256",
    "ignoreUserConfig",
    "ignoreRules",
    "ephemeral",
    "codexCliVersion",
    "codexFeaturesSnapshotSha256",
    "codexFeatureCount",
    "codexFeatureListStdoutSha256",
    "executionSettings",
    "rawOutputSha256",
    "normalizedArtifactSha256",
    "traceSha256",
    "validationReportSha256",
    "attemptLedgerSha256",
    "tokenLedgerSha256",
    "implementationCodeHashes",
    "semanticModelInvocations",
    "firstAttemptOnly",
    "noSelectiveRetry",
    "inputDelivery",
    "stdinPacketSha256",
    "stdinPacketPublicSha256",
    "configuredModelToolSchemaCount",
    "configuredModelToolSchemas",
    "configuredModelToolSchemasSha256",
    "toolSchemaAdvertisementAttested",
    "finalResponseStrictParsed",
    "legacyFileAgentUsed",
    "threadIds",
    "visibilityBoundary",
    "policyAudit",
    "receiptSha256",
}
VISIBILITY_KEYS = {
    "publicFilesMounted",
    "privateGoldMounted",
    "privateLabelsMounted",
    "otherGeneratorArtifactsMounted",
    "roleMappingMounted",
    "candidateProvenanceExposed",
    "goldFilesDiscoverable",
}
POLICY_AUDIT_KEYS = {
    "goldReadEvents",
    "privateLabelReadEvents",
    "otherGeneratorArtifactReadEvents",
    "roleMappingReadEvents",
    "webSearchEvents",
    "networkEvents",
    "toolEvents",
    "itemStartedToolEvents",
    "itemCompletedToolEvents",
    "itemStartedCommandEvents",
}
GENERATOR_STAGE_BINDING_KEYS = {
    "stageKind",
    "artifactPath",
    "artifactSha256",
    "promptPath",
    "promptSha256",
    "outputSchemaPath",
    "outputSchemaSha256",
    "rawOutputPath",
    "rawOutputSha256",
    "tracePath",
    "traceSha256",
    "receiptPath",
    "receiptFileSha256",
    "receiptSha256",
    "validationReportPath",
    "validationReportFileSha256",
    "validationReportSha256",
    "attemptLedgerPath",
    "attemptLedgerFileSha256",
    "attemptLedgerSha256",
    "tokenLedgerPath",
    "tokenLedgerFileSha256",
    "tokenLedgerSha256",
    "implementationCodeHashes",
}
BLIND_STAGE_BINDING_KEYS = GENERATOR_STAGE_BINDING_KEYS | {
    "roleMappingPath",
    "roleMappingSha256",
}
SOURCE_ARTIFACT_BINDING_KEYS = {
    "publicPath",
    "publicSha256",
    "builderManifestPath",
    "builderManifestFileSha256",
    "builderManifestSelfHash",
    "labelIndependentIdReceiptPath",
    "labelIndependentIdReceiptFileSha256",
    "labelIndependentIdReceiptSha256",
    "conclusionLeakReportPath",
    "conclusionLeakReportFileSha256",
    "conclusionLeakReportSha256",
    "generatorOutputSchemaPath",
    "generatorOutputSchemaSha256",
    "blindPromptTemplatePath",
    "blindPromptTemplateSha256",
    "blindOutputSchemaTemplatePath",
    "blindOutputSchemaTemplateSha256",
}
CAMPAIGN_MANIFEST_KEYS = {
    "schemaVersion",
    "protocol",
    "status",
    "campaignId",
    "sourceFreezeFileSha256",
    "sourceFreezeSha256",
    "blindPackageFreezeFileSha256",
    "blindPackageFreezeSha256",
    "sourceArtifacts",
    "stages",
    "comparatorFairnessAudit",
    "manifestSha256",
}
BLIND_PACKAGE_FREEZE_KEYS = {
    "schemaVersion",
    "protocol",
    "status",
    "campaignId",
    "sourceFreezeFileSha256",
    "sourceFreezeSha256",
    "blindPromptTemplateSha256",
    "blindOutputSchemaTemplateSha256",
    "blindPackageContractSha256",
    "blindPackageDerivationCodeHashes",
    "carrierSelectionSeed",
    "roleRotationSeed",
    "generatorStageReceipts",
    "expectedConflictRows",
    "expectedConflictIdsSha256",
    "orderedConflictPackageSha256",
    "instantiatedBlindPromptPacketSha256",
    "instantiatedBlindOutputSchemaSha256",
    "blindRoleMappingSha256",
    "freezeSha256",
}
BLIND_PACKAGE_GENERATOR_RECEIPT_KEYS = {
    "artifactSha256",
    "rawOutputSha256",
    "traceSha256",
    "receiptFileSha256",
    "receiptSha256",
    "validationReportSha256",
    "attemptLedgerSha256",
    "tokenLedgerSha256",
}
BLIND_CONFLICT_PACKAGE_KEYS = {
    "id",
    "incumbentOutcome",
    "proposedOutcome",
    "proposalCarrier",
    "leftOutcome",
    "rightOutcome",
}
BLIND_VISIBLE_ITEM_KEYS = {"id", "public", "leftOutcome", "rightOutcome"}
ID_RECEIPT_KEYS = {
    "schemaVersion",
    "protocol",
    "status",
    "publicSha256",
    "expectedIdsSha256",
    "idPattern",
    "idDerivation",
    "idInputs",
    "labelFieldsRead",
    "implementationCodeHashes",
    "receiptSha256",
}
VALIDATION_REPORT_KEYS = {
    "schemaVersion",
    "protocol",
    "status",
    "stage",
    "expectedRows",
    "observedFirstAttemptRows",
    "validIds",
    "invalidRows",
    "rawOutputSha256",
    "normalizedArtifactSha256",
    "reportSha256",
}
INVALID_ROW_KEYS = {"id", "errors", "sourceLine", "rawRecordSha256"}
ATTEMPT_LEDGER_KEYS = {
    "schemaVersion",
    "protocol",
    "status",
    "stage",
    "semanticAttemptCount",
    "transportRetryCount",
    "selectiveRetryCount",
    "attempts",
    "ledgerSha256",
}
ATTEMPT_KEYS = {"ordinal", "kind", "rawOutputSha256", "traceSha256"}
TOKEN_LEDGER_KEYS = {
    "schemaVersion",
    "protocol",
    "status",
    "stage",
    "attempts",
    "totals",
    "ledgerSha256",
}
TOKEN_ENTRY_KEYS = {
    "ordinal",
    "inputTokens",
    "cachedInputTokens",
    "outputTokens",
    "reasoningTokens",
    "totalTokens",
}
TOKEN_TOTAL_KEYS = TOKEN_ENTRY_KEYS - {"ordinal"}
COMPARATOR_FAIRNESS_KEYS = {"required", "status", "reportSha256"}

PUBLIC_CONSTANTS = {
    "suite": "exam",
    "benchmarkId": "outcome.first_instance_prediction.v1",
    "responseFormat": "outcome_prediction",
    "language": "ko",
    "opaqueIdPattern": r"outcome-confirm-[0-9a-f]{20}",
}
TOOL_FREE_DISABLED_FEATURES = tuple(
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
        for feature in TOOL_FREE_DISABLED_FEATURES
        for item in ("--config", f"features.{feature}=false")
    ),
)


def _static_canonical_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


DISABLED_FEATURES_SHA256 = _static_canonical_digest(list(TOOL_FREE_DISABLED_FEATURES))
STRICT_CONFIG_ARGV_SHA256 = _static_canonical_digest(list(STRICT_CONFIG_ARGV))
CODEX_CLI_VERSION = "codex-cli 0.151.0"
CODEX_FEATURES_SNAPSHOT_SHA256 = (
    "8f42f1985441b4f7e78c6db8f0a4c7068bc74075a7133e0423792352f2674f64"
)
CODEX_FEATURE_LIST_STDOUT_SHA256 = (
    "aca6b0a0d5ea33488ae6d5d3464b6932b0209d273559dcb9163b4039de499964"
)
CODEX_FEATURE_COUNT = 129
EMPTY_TOOL_SCHEMAS_SHA256 = _static_canonical_digest([])
EXECUTION_SETTINGS = {
    "model": "gpt-5.6-luna",
    "reasoningEffort": "high",
    "verbosity": "low",
    "serviceTier": "default",
    "nativeWebSearch": False,
    "localCode": False,
    "shellTool": False,
    "database": False,
    "mcp": False,
    "apps": False,
    "skills": False,
    "multiAgent": False,
    "ephemeral": True,
    "ignoreUserConfig": True,
    "ignoreRules": True,
    "strictConfig": True,
    "configArgv": list(STRICT_CONFIG_ARGV),
    "codexCliVersion": CODEX_CLI_VERSION,
    "codexFeaturesSnapshotSha256": CODEX_FEATURES_SNAPSHOT_SHA256,
    "codexFeatureListStdoutSha256": CODEX_FEATURE_LIST_STDOUT_SHA256,
    "codexFeatureCount": CODEX_FEATURE_COUNT,
    "disabledFeatures": list(TOOL_FREE_DISABLED_FEATURES),
    "disabledFeaturesSha256": DISABLED_FEATURES_SHA256,
    "configArgvSha256": STRICT_CONFIG_ARGV_SHA256,
    "features": {feature: False for feature in TOOL_FREE_DISABLED_FEATURES},
}
OUTPUT_SCHEMA_CLI_ARG = "--output-schema"
ATTEMPT_POLICY = {
    "semanticAttemptsPerStage": 1,
    "selectiveRetry": False,
    "transportRetryAfterModelOutput": False,
    "invalidRowHandling": "preserve_first_attempt_and_score_wrong",
}
REQUIRED_UPSTREAM_RECEIPT_HOOKS = [
    "prompt",
    "promptTemplate",
    "outputSchemaFileAndCliArg",
    "executionSettings",
    "rawOutput",
    "normalizedArtifact",
    "trace",
    "validationReport",
    "fullClauseQuoteValidation",
    "attemptLedger",
    "tokenLedger",
    "implementationCodeHashes",
    "visibilityBoundary",
    "stdinEmbeddedPacketHashes",
    "zeroAdvertisedToolSchemasAndRawTraceAudit",
    "strictConfigArgvHash",
    "strictFinalResponseParse",
    "stageThreadIdentities",
]
BLIND_PACKAGE_CONTRACT = {
    "version": "blind-conflict-packet-derivation-v1",
    "conflictRule": "valid G1/G2/G3 and G2.outcome == G3.outcome != G1.outcome",
    "proposalCarrier": "frozen SHA-256 carrier seed; G2/G3 only",
    "roleRotation": "frozen SHA-256 role seed; INCUMBENT/PROPOSED exactly once",
    "packetTemplatePlaceholder": "{{BLIND_ITEMS_JSONL}}",
    "packetSerialization": (
        "replace the one UTF-8 placeholder with ordered canonical JSONL rows "
        "{id,public,leftOutcome,rightOutcome}, including the final JSONL newline"
    ),
    "packetInputs": ["ordered opaque ID", "exact public row", "left/right outcomes"],
    "packetExcludes": [
        "generator identity",
        "rationale",
        "evidence atoms",
        "agreement or trigger provenance",
        "role mapping",
        "gold",
    ],
    "outputSchema": (
        "template frozen pre-any-call; replace its one {conflict_count} value "
        "with the integer conflict count; instance frozen pre-BLIND"
    ),
}
INVALID_PLACEHOLDER_RATIONALE = "INVALID_FIRST_ATTEMPT"
ALLOWED_TRACE_EVENT_TYPES = {
    "thread.started",
    "turn.started",
    "turn.completed",
    "item.started",
    "item.updated",
    "item.completed",
}
TRACE_ITEM_EVENT_TYPES = {"item.started", "item.updated", "item.completed"}
ALLOWED_TRACE_ITEM_TYPES = {"reasoning", "agent_message", "error"}
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

MIN_QUOTE_CODEPOINTS = 8
MAX_QUOTE_CODEPOINTS = 240
MAX_RATIONALE_CODEPOINTS = 2_000
HEX_SHA256_RE = re.compile(r"[0-9a-f]{64}")
CLAUSE_LINE_RE = re.compile(r"^\[(?P<id>[CF]\d{3})\] (?P<text>\S(?:.*\S)?)$")
CLAUSE_MARKER_RE = re.compile(r"\[(?:C|F)\d{3}\]")

_CARRIER_DOMAIN = b"mini-artichokes-legal-proposal-carrier-v1\0"
_ROTATION_DOMAIN = b"mini-artichokes-legal-role-rotation-v1\0"
BLIND_PACKET_PLACEHOLDER = "{{BLIND_ITEMS_JSONL}}"
BLIND_SCHEMA_COUNT_PLACEHOLDER = "{conflict_count}"


class CombinationValidationError(ValueError):
    """An input failed the gold-free mechanism contract."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CombinationValidationError(message)


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


def sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def render_blind_prompt_packet(
    *,
    template_bytes: bytes,
    public_rows_by_id: Mapping[str, Mapping[str, Any]],
    conflict_package: Sequence[Mapping[str, str]],
) -> bytes:
    """Deterministically instantiate the provenance-free BLIND stdin packet."""

    template = _decode_utf8(template_bytes, label="blind prompt template")
    _require(
        template.count(BLIND_PACKET_PLACEHOLDER) == 1,
        "blind prompt template must contain exactly one packet placeholder",
    )
    visible_rows: list[dict[str, Any]] = []
    for position, conflict in enumerate(conflict_package, 1):
        case_id = conflict.get("id")
        _require(
            isinstance(case_id, str) and case_id in public_rows_by_id,
            f"blind packet conflict {position} public binding",
        )
        row = {
            "id": case_id,
            "public": dict(public_rows_by_id[case_id]),
            "leftOutcome": conflict.get("leftOutcome"),
            "rightOutcome": conflict.get("rightOutcome"),
        }
        _require(set(row) == BLIND_VISIBLE_ITEM_KEYS, "blind visible item schema")
        visible_rows.append(row)
    serialized = b"".join(canonical_json_bytes(row) + b"\n" for row in visible_rows)
    return template.replace(
        BLIND_PACKET_PLACEHOLDER,
        serialized.decode("utf-8"),
    ).encode("utf-8")


def instantiate_blind_output_schema(template: Any, *, conflict_count: int) -> Any:
    """Replace the one frozen row-count marker without changing other schema data."""

    _require(type(conflict_count) is int and conflict_count >= 0, "blind schema row count")
    marker_count = 0

    def replace(value: Any) -> Any:
        nonlocal marker_count
        if value == BLIND_SCHEMA_COUNT_PLACEHOLDER:
            marker_count += 1
            return conflict_count
        if isinstance(value, dict):
            return {key: replace(item) for key, item in value.items()}
        if isinstance(value, list):
            return [replace(item) for item in value]
        return value

    instantiated = replace(template)
    _require(
        marker_count == 1,
        "blind output-schema template must contain exactly one conflict-count marker",
    )
    return instantiated


def _valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and HEX_SHA256_RE.fullmatch(value) is not None


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_nonfinite(value: str) -> Any:
    raise ValueError(f"non-finite JSON value: {value}")


def _read_regular_bytes(path: Path, *, label: str) -> tuple[bytes, str]:
    _require(not path.is_symlink(), f"{label} must be a regular non-symlink file")
    path = path.resolve(strict=False)
    _require(path.is_file(), f"{label} must be a regular non-symlink file")
    before = path.stat()
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise CombinationValidationError(f"cannot read {label}: {exc}") from exc
    after = path.stat()
    _require(
        (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns),
        f"{label} changed while being read",
    )
    return raw, sha256_bytes(raw)


def _decode_utf8(raw: bytes, *, label: str) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CombinationValidationError(f"{label} is not UTF-8: {exc}") from exc


def _parse_json_object_bytes(raw: bytes, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(
            _decode_utf8(raw, label=label),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonfinite,
        )
    except (json.JSONDecodeError, ValueError) as exc:
        raise CombinationValidationError(f"invalid {label}: {exc}") from exc
    _require(isinstance(value, dict), f"{label} root must be an object")
    return value


def _load_json_object(path: Path, *, label: str) -> tuple[dict[str, Any], str]:
    raw, digest = _read_regular_bytes(path, label=label)
    return _parse_json_object_bytes(raw, label=label), digest


def _load_jsonl(
    path: Path,
    *,
    label: str,
    allow_empty: bool = False,
) -> tuple[list[dict[str, Any]], str]:
    raw, digest = _read_regular_bytes(path, label=label)
    text = _decode_utf8(raw, label=label)
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    if not lines:
        _require(allow_empty and text == "", f"{label} is empty")
        return [], digest
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, 1):
        _require(bool(line.strip()), f"blank {label} row {line_number}")
        try:
            value = json.loads(
                line,
                object_pairs_hook=_reject_duplicate_keys,
                parse_constant=_reject_nonfinite,
            )
        except (json.JSONDecodeError, ValueError) as exc:
            raise CombinationValidationError(
                f"invalid {label} row {line_number}: {exc}"
            ) from exc
        _require(isinstance(value, dict), f"{label} row {line_number} is not an object")
        rows.append(value)
    return rows, digest


def _verify_external_file_hash(observed: str, expected: str, *, label: str) -> None:
    _require(_valid_sha256(expected), f"{label} expected SHA-256 is invalid")
    _require(observed == expected, f"{label} file SHA-256 mismatch")


def _verify_self_hash(value: Mapping[str, Any], field: str, *, label: str) -> str:
    claimed = value.get(field)
    _require(_valid_sha256(claimed), f"{label} {field} is invalid")
    unsigned = {key: item for key, item in value.items() if key != field}
    _require(canonical_digest(unsigned) == claimed, f"{label} {field} mismatch")
    return str(claimed)


def _hash_bit(domain: bytes, seed: str, case_id: str) -> int:
    payload = domain + seed.encode("utf-8") + b"\0" + case_id.encode("utf-8")
    return hashlib.sha256(payload).digest()[0] & 1


def proposal_carrier(seed: str, case_id: str) -> str:
    """Return the frozen provenance carrier; it never changes the label."""

    return "G2" if _hash_bit(_CARRIER_DOMAIN, seed, case_id) == 0 else "G3"


def expected_roles(seed: str, case_id: str) -> tuple[str, str]:
    """Return deterministic (LEFT, RIGHT) source roles for a conflict."""

    if _hash_bit(_ROTATION_DOMAIN, seed, case_id) == 0:
        return "INCUMBENT", "PROPOSED"
    return "PROPOSED", "INCUMBENT"


def _parse_clauses(prompt: str, *, case_id: str) -> dict[str, str]:
    clauses: dict[str, str] = {}
    marker_count = 0
    for line_number, line in enumerate(prompt.splitlines(), 1):
        markers = CLAUSE_MARKER_RE.findall(line)
        marker_count += len(markers)
        if not markers:
            continue
        match = CLAUSE_LINE_RE.fullmatch(line)
        _require(
            match is not None and len(markers) == 1,
            f"public {case_id} malformed clause line {line_number}",
        )
        clause_id = match.group("id")
        _require(clause_id not in clauses, f"public {case_id} duplicate clause {clause_id}")
        clauses[clause_id] = match.group("text")
    _require(bool(clauses), f"public {case_id} has no numbered evidence clauses")
    _require(marker_count == len(clauses), f"public {case_id} has stray clause markers")
    for prefix in ("C", "F"):
        observed = sorted(key for key in clauses if key.startswith(prefix))
        expected = [f"{prefix}{index:03d}" for index in range(1, len(observed) + 1)]
        _require(observed == expected, f"public {case_id} non-contiguous {prefix} clauses")
    return clauses


def _validate_public_rows(rows: list[dict[str, Any]]) -> tuple[list[str], dict[str, dict[str, str]]]:
    ids: list[str] = []
    clauses_by_id: dict[str, dict[str, str]] = {}
    for position, row in enumerate(rows, 1):
        _require(set(row) == PUBLIC_ROW_KEYS, f"public row {position} schema")
        for field in PUBLIC_ROW_KEYS:
            _require(
                isinstance(row.get(field), str) and bool(row[field].strip()),
                f"public row {position} invalid {field}",
            )
        case_id = row["id"]
        _require(
            re.fullmatch(PUBLIC_CONSTANTS["opaqueIdPattern"], case_id) is not None,
            f"public row {position} non-opaque ID",
        )
        for field in ("suite", "benchmarkId", "responseFormat", "language"):
            _require(
                row[field] == PUBLIC_CONSTANTS[field],
                f"public row {position} constant {field}",
            )
        _require(case_id not in clauses_by_id, f"public duplicate ID: {case_id}")
        ids.append(case_id)
        clauses_by_id[case_id] = _parse_clauses(row["prompt"], case_id=case_id)
    return ids, clauses_by_id


def _atom_key(
    atom: Mapping[str, str], outcome: str
) -> tuple[str, str, str, str, str]:
    return (
        atom["issueCode"],
        atom["evidenceClauseId"],
        atom["exactQuote"],
        atom["direction"],
        outcome,
    )


def _validate_generators(
    generator_rows: Mapping[str, list[dict[str, Any]]],
    *,
    expected_ids: list[str],
    clauses_by_id: Mapping[str, Mapping[str, str]],
    valid_ids_by_generator: Mapping[str, set[str]],
) -> dict[str, dict[str, dict[str, Any]]]:
    validated: dict[str, dict[str, dict[str, Any]]] = {}
    for generator_name in GENERATOR_NAMES:
        rows = generator_rows[generator_name]
        _require(len(rows) == len(expected_ids), f"{generator_name} row count mismatch")
        by_id: dict[str, dict[str, Any]] = {}
        for position, (row, expected_id) in enumerate(zip(rows, expected_ids, strict=True), 1):
            _require(set(row) == GENERATOR_ROW_KEYS, f"{generator_name} row {position} schema")
            _require(row.get("id") == expected_id, f"{generator_name} IDs/order mismatch at {position}")
            outcome = row.get("outcome")
            rationale = row.get("rationale")
            atoms = row.get("evidenceAtoms")
            if expected_id not in valid_ids_by_generator[generator_name]:
                _require(
                    outcome == "ABSTAIN"
                    and rationale == INVALID_PLACEHOLDER_RATIONALE
                    and atoms == [],
                    f"{generator_name} {expected_id} invalid-row placeholder mismatch",
                )
                by_id[expected_id] = row
                continue
            _require(
                isinstance(outcome, str) and outcome in OUTCOMES,
                f"{generator_name} {expected_id} invalid outcome",
            )
            _require(
                isinstance(rationale, str)
                and bool(rationale.strip())
                and len(rationale) <= MAX_RATIONALE_CODEPOINTS,
                f"{generator_name} {expected_id} invalid rationale",
            )
            _require(
                isinstance(atoms, list) and len(atoms) <= 2,
                f"{generator_name} {expected_id} evidence atom count",
            )
            seen_atom_keys: set[tuple[str, str, str, str, str]] = set()
            for atom_index, atom in enumerate(atoms, 1):
                label = f"{generator_name} {expected_id} atom {atom_index}"
                _require(isinstance(atom, dict) and set(atom) == ATOM_KEYS, f"{label} schema")
                issue_code = atom.get("issueCode")
                clause_id = atom.get("evidenceClauseId")
                quote = atom.get("exactQuote")
                direction = atom.get("direction")
                _require(
                    isinstance(issue_code, str) and issue_code in ISSUE_CODES,
                    f"{label} issue code",
                )
                _require(
                    isinstance(clause_id, str)
                    and re.fullmatch(r"[CF]\d{3}", clause_id) is not None
                    and clause_id in clauses_by_id[expected_id],
                    f"{label} clause ID",
                )
                _require(
                    isinstance(quote, str)
                    and MIN_QUOTE_CODEPOINTS <= len(quote) <= MAX_QUOTE_CODEPOINTS,
                    f"{label} quote length",
                )
                _require(
                    quote == clauses_by_id[expected_id][clause_id],
                    f"{label} quote must equal the entire named clause",
                )
                _require(
                    isinstance(direction, str) and direction in DIRECTIONS,
                    f"{label} direction",
                )
                _require(
                    DIRECTION_FOR_OUTCOME.get(str(outcome)) == direction,
                    f"{label} direction/outcome incoherence",
                )
                key = _atom_key(atom, str(outcome))
                _require(key not in seen_atom_keys, f"{label} duplicate atom key")
                seen_atom_keys.add(key)
            by_id[expected_id] = row
        validated[generator_name] = by_id
    return validated


def _validate_source_freeze(
    freeze: dict[str, Any],
    *,
    freeze_file_sha256: str,
    expected_freeze_file_sha256: str,
    public_sha256: str,
    expected_ids: list[str],
    builder_manifest_file_sha256: str,
    builder_manifest_self_hash: str,
    id_receipt_file_sha256: str,
    id_receipt_sha256: str,
    conclusion_leak_report_file_sha256: str,
    conclusion_leak_report_sha256: str,
    generator_output_schema_sha256: str,
    blind_prompt_template_sha256: str,
    blind_output_schema_template_sha256: str,
) -> tuple[str, str, str, str]:
    _verify_external_file_hash(
        freeze_file_sha256,
        expected_freeze_file_sha256,
        label="source freeze",
    )
    _require(set(freeze) == SOURCE_FREEZE_KEYS, "source freeze schema")
    freeze_sha256 = _verify_self_hash(freeze, "freezeSha256", label="source freeze")
    _require(freeze.get("schemaVersion") == 1, "source freeze schema version")
    _require(freeze.get("protocol") == SOURCE_FREEZE_PROTOCOL, "source freeze protocol")
    _require(freeze.get("status") == SOURCE_FREEZE_STATUS, "source freeze status")
    campaign_id = freeze.get("campaignId")
    _require(
        isinstance(campaign_id, str)
        and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", campaign_id) is not None,
        "source freeze campaign ID",
    )
    _require(freeze.get("publicSha256") == public_sha256, "source freeze public hash")
    expected_source_bindings = {
        "publicBuilderManifestFileSha256": builder_manifest_file_sha256,
        "publicBuilderManifestSelfHash": builder_manifest_self_hash,
        "labelIndependentIdReceiptFileSha256": id_receipt_file_sha256,
        "labelIndependentIdReceiptSha256": id_receipt_sha256,
        "conclusionLeakReportFileSha256": conclusion_leak_report_file_sha256,
        "conclusionLeakReportSha256": conclusion_leak_report_sha256,
        "generatorOutputSchemaSha256": generator_output_schema_sha256,
        "blindPromptTemplateSha256": blind_prompt_template_sha256,
        "blindOutputSchemaTemplateSha256": blind_output_schema_template_sha256,
    }
    for field, expected in expected_source_bindings.items():
        _require(freeze.get(field) == expected, f"source freeze {field} mismatch")
    _require(freeze.get("expectedRows") == len(expected_ids), "source freeze row count")
    _require(
        freeze.get("expectedIdsSha256") == canonical_digest(expected_ids),
        "source freeze ordered IDs hash",
    )
    _require(freeze.get("publicConstants") == PUBLIC_CONSTANTS, "source freeze public constants")
    _require(
        _valid_sha256(freeze.get("generatorPromptSha256")),
        "source freeze generator prompt hash",
    )
    _require(
        freeze.get("blindPackageContractSha256")
        == canonical_digest(BLIND_PACKAGE_CONTRACT),
        "source freeze blind-package contract",
    )
    _require(
        freeze.get("outputSchemaCliArg") == OUTPUT_SCHEMA_CLI_ARG,
        "source freeze output-schema CLI argument",
    )
    _verify_code_hashes(
        freeze.get("blindPackageDerivationCodeHashes"),
        label="source freeze blind-package derivation",
    )
    _require(
        freeze.get("generatorExecutionSettings") == EXECUTION_SETTINGS,
        "source freeze generator settings",
    )
    _require(
        freeze.get("blindExecutionSettings") == EXECUTION_SETTINGS,
        "source freeze blind settings",
    )
    _require(freeze.get("attemptPolicy") == ATTEMPT_POLICY, "source freeze attempt policy")
    _require(
        freeze.get("requiredUpstreamReceiptHooks") == REQUIRED_UPSTREAM_RECEIPT_HOOKS,
        "source freeze upstream receipt hooks",
    )
    _require(
        freeze.get("comparatorFairnessAuditRequired") is True,
        "source freeze comparator fairness requirement",
    )
    carrier_seed = freeze.get("carrierSelectionSeed")
    rotation_seed = freeze.get("roleRotationSeed")
    _require(
        isinstance(carrier_seed, str) and bool(carrier_seed),
        "source freeze carrier seed",
    )
    _require(
        isinstance(rotation_seed, str) and bool(rotation_seed),
        "source freeze role seed",
    )
    return freeze_sha256, str(campaign_id), carrier_seed, rotation_seed


def _safe_manifest_path(campaign_root: Path, relative: Any, *, label: str) -> Path:
    _require(isinstance(relative, str) and bool(relative), f"{label} path")
    raw = Path(relative)
    _require(not raw.is_absolute() and ".." not in raw.parts, f"{label} path escapes campaign")
    resolved = (campaign_root / raw).resolve(strict=False)
    try:
        resolved.relative_to(campaign_root)
    except ValueError as exc:
        raise CombinationValidationError(f"{label} path escapes campaign") from exc
    return resolved


def _verify_code_hashes(value: Any, *, label: str) -> dict[str, str]:
    _require(isinstance(value, dict) and bool(value), f"{label} code hashes")
    verified: dict[str, str] = {}
    for raw_path, expected in value.items():
        _require(isinstance(raw_path, str), f"{label} code-hash path")
        path = Path(raw_path)
        _require(path.is_absolute() and not path.is_symlink(), f"{label} code-hash path")
        resolved = path.resolve(strict=False)
        try:
            resolved.relative_to(REPO_ROOT)
        except ValueError as exc:
            raise CombinationValidationError(f"{label} code path outside repository") from exc
        _require(resolved.is_file(), f"{label} code file missing")
        observed = sha256_file(resolved)
        _require(_valid_sha256(expected) and expected == observed, f"{label} code hash mismatch")
        verified[raw_path] = observed
    return verified


def _validate_campaign_manifest_structure(
    manifest: dict[str, Any],
    *,
    manifest_file_sha256: str,
    expected_manifest_file_sha256: str,
) -> str:
    _verify_external_file_hash(
        manifest_file_sha256,
        expected_manifest_file_sha256,
        label="campaign manifest",
    )
    _require(set(manifest) == CAMPAIGN_MANIFEST_KEYS, "campaign manifest schema")
    manifest_sha256 = _verify_self_hash(
        manifest, "manifestSha256", label="campaign manifest"
    )
    _require(manifest.get("schemaVersion") == 1, "campaign manifest schema version")
    _require(manifest.get("protocol") == CAMPAIGN_MANIFEST_PROTOCOL, "campaign manifest protocol")
    _require(manifest.get("status") == CAMPAIGN_MANIFEST_STATUS, "campaign manifest status")
    _require(
        isinstance(manifest.get("sourceArtifacts"), dict)
        and set(manifest["sourceArtifacts"]) == SOURCE_ARTIFACT_BINDING_KEYS,
        "campaign source-artifact schema",
    )
    stages = manifest.get("stages")
    _require(isinstance(stages, dict) and set(stages) == {*GENERATOR_NAMES, "BLIND"}, "campaign stages")
    for name in GENERATOR_NAMES:
        _require(
            isinstance(stages[name], dict)
            and set(stages[name]) == GENERATOR_STAGE_BINDING_KEYS,
            f"campaign {name} binding schema",
        )
    _require(
        isinstance(stages["BLIND"], dict)
        and set(stages["BLIND"]) == BLIND_STAGE_BINDING_KEYS,
        "campaign BLIND binding schema",
    )
    fairness = manifest.get("comparatorFairnessAudit")
    _require(
        isinstance(fairness, dict)
        and set(fairness) == COMPARATOR_FAIRNESS_KEYS
        and fairness.get("required") is True
        and fairness.get("status") == "PENDING_EXTERNAL_AUDIT"
        and fairness.get("reportSha256") is None,
        "comparator fairness must remain an explicit external pending gate",
    )
    return manifest_sha256


def _validate_campaign_source_artifacts(
    source: dict[str, Any],
    *,
    campaign_root: Path,
    explicit_public_path: Path,
    public_rows: list[dict[str, Any]],
    public_sha256: str,
    expected_ids: list[str],
) -> dict[str, Any]:
    _require(set(source) == SOURCE_ARTIFACT_BINDING_KEYS, "campaign source-artifact schema")
    public_path = _safe_manifest_path(campaign_root, source.get("publicPath"), label="campaign public")
    _require(public_path == explicit_public_path.resolve(), "campaign explicit public path")
    _, observed_public_sha256 = _read_regular_bytes(public_path, label="campaign public")
    _require(
        observed_public_sha256 == public_sha256 == source.get("publicSha256"),
        "campaign public hash",
    )

    builder_path = _safe_manifest_path(
        campaign_root, source.get("builderManifestPath"), label="builder manifest"
    )
    builder, builder_file_sha256 = _load_json_object(builder_path, label="builder manifest")
    _require(
        source.get("builderManifestFileSha256") == builder_file_sha256,
        "campaign builder-manifest file hash",
    )
    builder_self_hash, builder_code_hashes = _validate_builder_manifest(
        builder, public_rows=public_rows, public_sha256=public_sha256
    )
    _require(
        source.get("builderManifestSelfHash") == builder_self_hash,
        "campaign builder-manifest self hash",
    )

    id_path = _safe_manifest_path(
        campaign_root,
        source.get("labelIndependentIdReceiptPath"),
        label="label-independent ID receipt",
    )
    id_receipt, id_file_sha256 = _load_json_object(
        id_path, label="label-independent ID receipt"
    )
    _require(
        source.get("labelIndependentIdReceiptFileSha256") == id_file_sha256,
        "campaign ID-receipt file hash",
    )
    id_receipt_sha256 = _validate_id_receipt(
        id_receipt,
        public_sha256=public_sha256,
        expected_ids=expected_ids,
        required_builder_code_hashes=builder_code_hashes,
    )
    _require(
        source.get("labelIndependentIdReceiptSha256") == id_receipt_sha256,
        "campaign ID-receipt self hash",
    )

    leak_path = _safe_manifest_path(
        campaign_root,
        source.get("conclusionLeakReportPath"),
        label="conclusion-leak report",
    )
    leak_report, leak_file_sha256 = _load_json_object(
        leak_path, label="conclusion-leak report"
    )
    _require(
        source.get("conclusionLeakReportFileSha256") == leak_file_sha256,
        "campaign conclusion-leak file hash",
    )
    leak_report_sha256 = _validate_conclusion_leak_report(
        leak_report,
        public_sha256=public_sha256,
        expected_ids=expected_ids,
        builder_manifest_file_sha256=builder_file_sha256,
    )
    _require(
        source.get("conclusionLeakReportSha256") == leak_report_sha256,
        "campaign conclusion-leak self hash",
    )

    generator_schema_path = _safe_manifest_path(
        campaign_root,
        source.get("generatorOutputSchemaPath"),
        label="generator output schema",
    )
    generator_schema, generator_schema_sha256 = _load_json_object(
        generator_schema_path, label="generator output schema"
    )
    _require(bool(generator_schema), "generator output schema empty")
    _require(
        source.get("generatorOutputSchemaSha256") == generator_schema_sha256,
        "campaign generator output-schema hash",
    )

    blind_template_path = _safe_manifest_path(
        campaign_root,
        source.get("blindPromptTemplatePath"),
        label="blind prompt template",
    )
    blind_template_raw, blind_template_sha256 = _read_regular_bytes(
        blind_template_path, label="blind prompt template"
    )
    _require(bool(blind_template_raw), "blind prompt template empty")
    _require(
        source.get("blindPromptTemplateSha256") == blind_template_sha256,
        "campaign blind prompt-template hash",
    )

    blind_schema_template_path = _safe_manifest_path(
        campaign_root,
        source.get("blindOutputSchemaTemplatePath"),
        label="blind output-schema template",
    )
    blind_schema_template, blind_schema_template_sha256 = _load_json_object(
        blind_schema_template_path, label="blind output-schema template"
    )
    _require(bool(blind_schema_template), "blind output-schema template empty")
    _require(
        source.get("blindOutputSchemaTemplateSha256")
        == blind_schema_template_sha256,
        "campaign blind output-schema-template hash",
    )
    return {
        "builderManifestPath": builder_path,
        "builderManifestFileSha256": builder_file_sha256,
        "builderManifestSelfHash": builder_self_hash,
        "labelIndependentIdReceiptPath": id_path,
        "labelIndependentIdReceiptFileSha256": id_file_sha256,
        "labelIndependentIdReceiptSha256": id_receipt_sha256,
        "conclusionLeakReportPath": leak_path,
        "conclusionLeakReportFileSha256": leak_file_sha256,
        "conclusionLeakReportSha256": leak_report_sha256,
        "generatorOutputSchemaPath": generator_schema_path,
        "generatorOutputSchemaSha256": generator_schema_sha256,
        "blindPromptTemplatePath": blind_template_path,
        "blindPromptTemplateSha256": blind_template_sha256,
        "blindOutputSchemaTemplatePath": blind_schema_template_path,
        "blindOutputSchemaTemplateSha256": blind_schema_template_sha256,
    }


def _validate_builder_manifest(
    manifest: dict[str, Any],
    *,
    public_rows: list[dict[str, Any]],
    public_sha256: str,
) -> tuple[str, dict[str, str]]:
    self_hash = manifest.get("selfHash")
    _require(_valid_sha256(self_hash), "builder manifest selfHash")
    unsigned = dict(manifest)
    unsigned.pop("selfHash", None)
    _require(canonical_digest(unsigned) == self_hash, "builder manifest selfHash mismatch")
    artifacts = manifest.get("artifacts")
    public = artifacts.get("public") if isinstance(artifacts, dict) else None
    _require(
        isinstance(public, dict)
        and public.get("sha256") == public_sha256
        and public.get("rows") == len(public_rows),
        "builder manifest public binding",
    )
    ordered = manifest.get("orderedCandidates")
    _require(isinstance(ordered, list) and len(ordered) == len(public_rows), "builder ordered candidates")
    for position, (item, row) in enumerate(zip(ordered, public_rows, strict=True), 1):
        _require(isinstance(item, dict), f"builder candidate {position} schema")
        _require(
            item.get("id") == row["id"]
            and item.get("publicRowSHA256") == sha256_bytes(canonical_json_bytes(row)),
            f"builder candidate {position} public binding",
        )
    implementation = manifest.get("implementation")
    _require(
        isinstance(implementation, dict)
        and set(implementation)
        == {"builder", "builderSHA256", "upstreamExtractor", "upstreamExtractorSHA256"},
        "builder manifest implementation schema",
    )
    builder_code_hashes = {
        str(implementation["builder"]): implementation["builderSHA256"],
        str(implementation["upstreamExtractor"]): implementation[
            "upstreamExtractorSHA256"
        ],
    }
    _verify_code_hashes(builder_code_hashes, label="builder manifest")
    return str(self_hash), builder_code_hashes


def _validate_id_receipt(
    receipt: dict[str, Any],
    *,
    public_sha256: str,
    expected_ids: list[str],
    required_builder_code_hashes: Mapping[str, str],
) -> str:
    _require(set(receipt) == ID_RECEIPT_KEYS, "label-independent ID receipt schema")
    receipt_sha256 = _verify_self_hash(
        receipt, "receiptSha256", label="label-independent ID receipt"
    )
    _require(receipt.get("schemaVersion") == 1, "label-independent ID schema version")
    _require(receipt.get("protocol") == ID_RECEIPT_PROTOCOL, "label-independent ID protocol")
    _require(receipt.get("status") == "accepted", "label-independent ID status")
    _require(receipt.get("publicSha256") == public_sha256, "label-independent ID public hash")
    _require(
        receipt.get("expectedIdsSha256") == canonical_digest(expected_ids),
        "label-independent ID ordered hash",
    )
    _require(
        receipt.get("idPattern") == PUBLIC_CONSTANTS["opaqueIdPattern"],
        "label-independent ID pattern",
    )
    _require(
        receipt.get("idDerivation")
        == "outcome-confirm- + first20(SHA256(seedSalt|canonicalId|normalizedCaseRef))"
        and receipt.get("idInputs") == ["seedSalt", "canonicalId", "normalizedCaseRef"]
        and receipt.get("labelFieldsRead") is False,
        "label-independent ID derivation",
    )
    verified_code_hashes = _verify_code_hashes(
        receipt.get("implementationCodeHashes"), label="ID receipt"
    )
    _require(
        all(verified_code_hashes.get(path) == digest for path, digest in required_builder_code_hashes.items()),
        "label-independent ID receipt does not bind builder implementations",
    )
    return receipt_sha256


def _validate_conclusion_leak_report(
    report: dict[str, Any],
    *,
    public_sha256: str,
    expected_ids: list[str],
    builder_manifest_file_sha256: str,
) -> str:
    report_sha256 = _verify_self_hash(
        report, "selfHash", label="public outcome audit report"
    )
    _require(
        report.get("schemaVersion") == PUBLIC_OUTCOME_AUDIT_PROTOCOL,
        "public outcome audit protocol",
    )
    audit_input = report.get("input")
    _require(
        isinstance(audit_input, dict)
        and audit_input.get("sha256") == public_sha256
        and audit_input.get("jsonRowCount") == len(expected_ids),
        "public outcome audit population binding",
    )
    manifest_input = audit_input.get("manifest")
    _require(
        isinstance(manifest_input, dict)
        and manifest_input.get("sha256") == builder_manifest_file_sha256,
        "public outcome audit builder-manifest binding",
    )
    implementation = report.get("implementation")
    audit_code_path = REPO_ROOT / "tools" / "audit_public_outcome_reserve.py"
    _require(
        isinstance(implementation, dict)
        and implementation.get("sha256") == sha256_file(audit_code_path),
        "public outcome audit implementation binding",
    )
    public_contract = report.get("publicContract")
    _require(
        isinstance(public_contract, dict)
        and public_contract.get("expectedExactKeys") == sorted(PUBLIC_ROW_KEYS)
        and public_contract.get("expectedConstants")
        == {key: PUBLIC_CONSTANTS[key] for key in ("suite", "benchmarkId", "responseFormat", "language")}
        and public_contract.get("inputReadErrorCount") == 0
        and public_contract.get("parsedPromptCount") == len(expected_ids)
        and public_contract.get("structuralViolationCount") == 0
        and public_contract.get("uniqueIdCount") == len(expected_ids),
        "public outcome audit public-contract gate",
    )
    generic = report.get("leakAudit")
    _require(
        isinstance(generic, dict)
        and generic.get("affectsFinalGate") is False
        and type(generic.get("rowsWithAnyFinding")) is int
        and generic["rowsWithAnyFinding"] >= 0,
        "public outcome audit informational regex contract",
    )
    near_duplicate = report.get("nearDuplicateAudit")
    _require(
        isinstance(near_duplicate, dict)
        and near_duplicate.get("qualifyingPairCount") == 0,
        "public outcome audit near-duplicate gate",
    )
    construction = report.get("constructionConclusionLeakageAudit")
    exclusion_counts = (
        construction.get("boundPreselectionExclusionCounts")
        if isinstance(construction, dict)
        else None
    )
    _require(
        isinstance(construction, dict)
        and construction.get("pass") is True
        and construction.get("bindingErrorCount") == 0
        and construction.get("manifestSHA256") == builder_manifest_file_sha256
        and isinstance(exclusion_counts, dict)
        and set(exclusion_counts)
        == {
            "claim_points_to_holding",
            "holding_section_marker",
            "holding_text_overlap",
        }
        and all(type(value) is int and value >= 0 for value in exclusion_counts.values()),
        "public outcome audit construction-leakage gate",
    )
    target = report.get("targetSpecificMetadataAudit")
    _require(
        isinstance(target, dict)
        and target.get("pass") is True
        and target.get("bindingErrorCount") == 0
        and target.get("rowsWithTargetMetadata") == 0,
        "public outcome audit target-specific metadata gate",
    )
    gates = report.get("gates")
    required_gate_names = (
        "publicContract",
        "lexicalNearDuplicate",
        "constructionConclusionLeakage",
        "targetSpecificMetadata",
        "finalPreSolver",
    )
    _require(
        isinstance(gates, dict)
        and all(isinstance(gates.get(name), dict) for name in required_gate_names)
        and all(gates[name].get("pass") is True for name in required_gate_names)
        and gates["finalPreSolver"].get("reasons") == []
        and report.get("gate") == gates["finalPreSolver"],
        "public outcome audit final gate",
    )
    return report_sha256


def _validate_first_attempt_report(
    report: dict[str, Any],
    *,
    stage: str,
    expected_ids: list[str],
    raw_output_sha256: str,
    artifact_sha256: str,
) -> tuple[set[str], list[str], str]:
    _require(set(report) == VALIDATION_REPORT_KEYS, f"{stage} validation-report schema")
    report_sha256 = _verify_self_hash(
        report, "reportSha256", label=f"{stage} validation report"
    )
    _require(report.get("schemaVersion") == 1, f"{stage} validation schema version")
    _require(report.get("protocol") == FIRST_ATTEMPT_VALIDATION_PROTOCOL, f"{stage} validation protocol")
    _require(
        report.get("status") == "complete_first_attempt_audit"
        and report.get("stage") == stage
        and report.get("expectedRows") == len(expected_ids)
        and type(report.get("observedFirstAttemptRows")) is int
        and report["observedFirstAttemptRows"] >= 0,
        f"{stage} validation identity/count",
    )
    _require(
        report.get("rawOutputSha256") == raw_output_sha256
        and report.get("normalizedArtifactSha256") == artifact_sha256,
        f"{stage} validation artifact binding",
    )
    valid_ids = report.get("validIds")
    invalid_rows = report.get("invalidRows")
    _require(
        isinstance(valid_ids, list)
        and all(isinstance(case_id, str) for case_id in valid_ids)
        and isinstance(invalid_rows, list),
        f"{stage} validation partition schema",
    )
    invalid_ids: list[str] = []
    for position, row in enumerate(invalid_rows, 1):
        _require(isinstance(row, dict) and set(row) == INVALID_ROW_KEYS, f"{stage} invalid row {position} schema")
        case_id = row.get("id")
        errors = row.get("errors")
        source_line = row.get("sourceLine")
        raw_hash = row.get("rawRecordSha256")
        _require(isinstance(case_id, str), f"{stage} invalid row {position} ID")
        _require(
            isinstance(errors, list)
            and bool(errors)
            and all(isinstance(error, str) and bool(error) for error in errors),
            f"{stage} invalid row {position} errors",
        )
        _require(
            source_line is None or (type(source_line) is int and source_line > 0),
            f"{stage} invalid row {position} source line",
        )
        _require(raw_hash is None or _valid_sha256(raw_hash), f"{stage} invalid row {position} raw hash")
        invalid_ids.append(case_id)
    _require(len(valid_ids) == len(set(valid_ids)), f"{stage} duplicate valid IDs")
    _require(len(invalid_ids) == len(set(invalid_ids)), f"{stage} duplicate invalid IDs")
    valid_set = set(valid_ids)
    invalid_set = set(invalid_ids)
    _require(not valid_set & invalid_set, f"{stage} validation partition overlap")
    _require(valid_set | invalid_set == set(expected_ids), f"{stage} validation partition coverage")
    _require(
        valid_ids == [case_id for case_id in expected_ids if case_id in valid_set]
        and invalid_ids == [case_id for case_id in expected_ids if case_id in invalid_set],
        f"{stage} validation partition order",
    )
    return valid_set, invalid_ids, report_sha256


def _validate_attempt_ledger(
    ledger: dict[str, Any],
    *,
    stage: str,
    raw_output_sha256: str,
    trace_sha256: str,
) -> str:
    _require(set(ledger) == ATTEMPT_LEDGER_KEYS, f"{stage} attempt-ledger schema")
    ledger_sha256 = _verify_self_hash(ledger, "ledgerSha256", label=f"{stage} attempt ledger")
    _require(
        ledger.get("schemaVersion") == 1
        and ledger.get("protocol") == ATTEMPT_LEDGER_PROTOCOL
        and ledger.get("status") == "complete"
        and ledger.get("stage") == stage,
        f"{stage} attempt-ledger identity",
    )
    _require(
        ledger.get("semanticAttemptCount") == 1
        and ledger.get("transportRetryCount") == 0
        and ledger.get("selectiveRetryCount") == 0,
        f"{stage} retry/attempt policy",
    )
    attempts = ledger.get("attempts")
    _require(isinstance(attempts, list) and len(attempts) == 1, f"{stage} attempt inventory")
    attempt = attempts[0]
    _require(
        isinstance(attempt, dict)
        and set(attempt) == ATTEMPT_KEYS
        and attempt.get("ordinal") == 1
        and attempt.get("kind") == "semantic_first_attempt"
        and attempt.get("rawOutputSha256") == raw_output_sha256
        and attempt.get("traceSha256") == trace_sha256,
        f"{stage} first-attempt binding",
    )
    return ledger_sha256


def _validate_token_ledger(ledger: dict[str, Any], *, stage: str) -> tuple[str, dict[str, int]]:
    _require(set(ledger) == TOKEN_LEDGER_KEYS, f"{stage} token-ledger schema")
    ledger_sha256 = _verify_self_hash(ledger, "ledgerSha256", label=f"{stage} token ledger")
    _require(
        ledger.get("schemaVersion") == 1
        and ledger.get("protocol") == TOKEN_LEDGER_PROTOCOL
        and ledger.get("status") == "complete"
        and ledger.get("stage") == stage,
        f"{stage} token-ledger identity",
    )
    attempts = ledger.get("attempts")
    totals = ledger.get("totals")
    _require(isinstance(attempts, list) and len(attempts) == 1, f"{stage} token attempts")
    entry = attempts[0]
    _require(isinstance(entry, dict) and set(entry) == TOKEN_ENTRY_KEYS, f"{stage} token entry schema")
    _require(entry.get("ordinal") == 1, f"{stage} token ordinal")
    for field in TOKEN_TOTAL_KEYS:
        _require(type(entry.get(field)) is int and entry[field] >= 0, f"{stage} token {field}")
    _require(
        entry["cachedInputTokens"] <= entry["inputTokens"]
        and entry["reasoningTokens"] <= entry["outputTokens"]
        and entry["totalTokens"] == entry["inputTokens"] + entry["outputTokens"],
        f"{stage} token arithmetic",
    )
    _require(
        isinstance(totals, dict)
        and set(totals) == TOKEN_TOTAL_KEYS
        and all(totals[field] == entry[field] for field in TOKEN_TOTAL_KEYS),
        f"{stage} token totals",
    )
    return ledger_sha256, {field: int(totals[field]) for field in TOKEN_TOTAL_KEYS}


def _audit_zero_tool_trace(path: Path, *, stage: str) -> dict[str, Any]:
    raw, _ = _read_regular_bytes(path, label=f"{stage} trace")
    text = _decode_utf8(raw, label=f"{stage} trace")
    counts = {
        "toolEvents": 0,
        "itemStartedToolEvents": 0,
        "itemCompletedToolEvents": 0,
        "itemStartedCommandEvents": 0,
    }
    thread_ids: list[str] = []
    event_sequence: list[str] = []
    diagnostic_indices: list[int] = []
    completed_agent_messages = 0
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    for line_number, line in enumerate(lines, 1):
        _require(bool(line.strip()), f"{stage} trace blank row {line_number}")
        try:
            event = json.loads(
                line,
                object_pairs_hook=_reject_duplicate_keys,
                parse_constant=_reject_nonfinite,
            )
        except (json.JSONDecodeError, ValueError) as exc:
            raise CombinationValidationError(
                f"{stage} trace invalid row {line_number}: {exc}"
            ) from exc
        _require(isinstance(event, dict), f"{stage} trace row {line_number} not object")
        event_type = event.get("type")
        _require(isinstance(event_type, str), f"{stage} trace row {line_number} type")
        _require(
            event_type in ALLOWED_TRACE_EVENT_TYPES,
            f"{stage} trace row {line_number} event type not allowlisted: {event_type}",
        )
        event_sequence.append(event_type)
        if event_type == "thread.started":
            _require(
                set(event) == {"type", "thread_id"},
                f"{stage} trace row {line_number} thread schema",
            )
            thread_id = event.get("thread_id")
            _require(
                isinstance(thread_id, str) and bool(thread_id),
                f"{stage} trace thread identity",
            )
            thread_ids.append(thread_id)
        elif event_type == "turn.started":
            _require(
                set(event) == {"type"},
                f"{stage} trace row {line_number} turn-start schema",
            )
        elif event_type == "turn.completed":
            usage = event.get("usage")
            _require(
                set(event) == {"type", "usage"}
                and isinstance(usage, dict)
                and set(usage) == EXPECTED_TURN_USAGE_KEYS
                and all(
                    type(usage[key]) is int and usage[key] >= 0
                    for key in EXPECTED_TURN_USAGE_KEYS
                )
                and usage["input_tokens"] + usage["output_tokens"] > 0,
                f"{stage} trace row {line_number} turn-complete schema",
            )
        elif event_type in TRACE_ITEM_EVENT_TYPES:
            _require(
                set(event) == {"type", "item"},
                f"{stage} trace row {line_number} item-event schema",
            )
            item = event.get("item")
            _require(
                isinstance(item, dict),
                f"{stage} trace row {line_number} item object required",
            )
            item_type = item.get("type")
            _require(
                isinstance(item_type, str)
                and item_type in ALLOWED_TRACE_ITEM_TYPES,
                f"{stage} trace row {line_number} item type not allowlisted: {item_type}",
            )
            if item_type in {"reasoning", "agent_message"}:
                _require(
                    set(item) == {"id", "type", "text"}
                    and isinstance(item.get("id"), str)
                    and bool(item["id"])
                    and isinstance(item.get("text"), str),
                    f"{stage} trace row {line_number} message-item schema",
                )
                if event_type == "item.completed" and item_type == "agent_message":
                    completed_agent_messages += 1
            else:
                _require(
                    event_type == "item.completed"
                    and set(item) == {"id", "type", "message"}
                    and isinstance(item.get("id"), str)
                    and bool(item["id"])
                    and item.get("message")
                    == EXPECTED_CODE_MODE_DISABLED_DIAGNOSTIC,
                    f"{stage} trace row {line_number} unexpected error item",
                )
                diagnostic_indices.append(len(event_sequence) - 1)
        else:
            _require(
                "item" not in event,
                f"{stage} trace row {line_number} unexpected item payload",
            )
    _require(
        len(thread_ids) == 1
        and event_sequence.count("thread.started") == 1
        and event_sequence.count("turn.started") == 1
        and event_sequence.count("turn.completed") == 1,
        f"{stage} trace must contain exactly one thread and turn",
    )
    _require(
        len(event_sequence) >= 5
        and event_sequence[0] == "thread.started"
        and diagnostic_indices == [1]
        and event_sequence[2] == "turn.started"
        and event_sequence[-1] == "turn.completed",
        f"{stage} trace containment/turn lifecycle",
    )
    _require(
        completed_agent_messages == 1,
        f"{stage} trace exactly one completed agent message",
    )
    return {
        "counts": counts,
        "threadIds": thread_ids,
        "completedAgentMessageCount": completed_agent_messages,
        "codeModeFailClosedDiagnosticCount": len(diagnostic_indices),
    }


def _validate_stage_binding(
    *,
    stage: str,
    binding: dict[str, Any],
    campaign_root: Path,
    explicit_artifact_path: Path,
    explicit_role_mapping_path: Path | None,
    expected_ids: list[str],
    campaign_id: str,
    source_freeze_sha256: str,
    public_sha256: str,
    expected_prompt_sha256: str,
    expected_output_schema_sha256: str,
    expected_settings: Mapping[str, Any],
) -> dict[str, Any]:
    stage_kind = "blind" if stage == "BLIND" else "generator"
    expected_keys = BLIND_STAGE_BINDING_KEYS if stage_kind == "blind" else GENERATOR_STAGE_BINDING_KEYS
    _require(set(binding) == expected_keys, f"{stage} binding schema")
    _require(binding.get("stageKind") == stage_kind, f"{stage} stage kind")
    path_fields = {
        "artifact": ("artifactPath", "artifactSha256"),
        "prompt": ("promptPath", "promptSha256"),
        "output schema": ("outputSchemaPath", "outputSchemaSha256"),
        "raw output": ("rawOutputPath", "rawOutputSha256"),
        "trace": ("tracePath", "traceSha256"),
        "receipt": ("receiptPath", "receiptFileSha256"),
        "validation report": ("validationReportPath", "validationReportFileSha256"),
        "attempt ledger": ("attemptLedgerPath", "attemptLedgerFileSha256"),
        "token ledger": ("tokenLedgerPath", "tokenLedgerFileSha256"),
    }
    paths: dict[str, Path] = {}
    observed_hashes: dict[str, str] = {}
    for label, (path_key, hash_key) in path_fields.items():
        path = _safe_manifest_path(campaign_root, binding.get(path_key), label=f"{stage} {label}")
        _, observed = _read_regular_bytes(path, label=f"{stage} {label}")
        _require(_valid_sha256(binding.get(hash_key)) and binding[hash_key] == observed, f"{stage} {label} hash")
        paths[label] = path
        observed_hashes[label] = observed
    _require(paths["artifact"] == explicit_artifact_path.resolve(), f"{stage} explicit artifact path")
    if stage_kind == "blind":
        role_path = _safe_manifest_path(
            campaign_root, binding.get("roleMappingPath"), label="BLIND role mapping"
        )
        _, role_hash = _read_regular_bytes(role_path, label="BLIND role mapping")
        _require(
            explicit_role_mapping_path is not None
            and role_path == explicit_role_mapping_path.resolve()
            and binding.get("roleMappingSha256") == role_hash,
            "BLIND role-mapping binding",
        )
        paths["role mapping"] = role_path
        observed_hashes["role mapping"] = role_hash
    code_hashes = _verify_code_hashes(binding.get("implementationCodeHashes"), label=f"{stage} binding")
    prompt_raw, _ = _read_regular_bytes(paths["prompt"], label=f"{stage} prompt")
    _require(bool(prompt_raw), f"{stage} prompt empty")
    _require(observed_hashes["prompt"] == expected_prompt_sha256, f"{stage} frozen prompt hash")
    output_schema, _ = _load_json_object(
        paths["output schema"], label=f"{stage} output schema"
    )
    _require(bool(output_schema), f"{stage} output schema empty")
    _require(
        observed_hashes["output schema"] == expected_output_schema_sha256,
        f"{stage} frozen output-schema hash",
    )

    validation_report, _ = _load_json_object(paths["validation report"], label=f"{stage} validation report")
    valid_ids, invalid_ids, validation_report_sha256 = _validate_first_attempt_report(
        validation_report,
        stage=stage,
        expected_ids=expected_ids,
        raw_output_sha256=observed_hashes["raw output"],
        artifact_sha256=observed_hashes["artifact"],
    )
    _require(
        binding.get("validationReportSha256") == validation_report_sha256,
        f"{stage} validation self-hash binding",
    )

    attempt_ledger, _ = _load_json_object(paths["attempt ledger"], label=f"{stage} attempt ledger")
    attempt_ledger_sha256 = _validate_attempt_ledger(
        attempt_ledger,
        stage=stage,
        raw_output_sha256=observed_hashes["raw output"],
        trace_sha256=observed_hashes["trace"],
    )
    _require(binding.get("attemptLedgerSha256") == attempt_ledger_sha256, f"{stage} attempt self hash")

    token_ledger, _ = _load_json_object(paths["token ledger"], label=f"{stage} token ledger")
    token_ledger_sha256, token_totals = _validate_token_ledger(token_ledger, stage=stage)
    _require(binding.get("tokenLedgerSha256") == token_ledger_sha256, f"{stage} token self hash")

    receipt, receipt_file_sha256 = _load_json_object(paths["receipt"], label=f"{stage} receipt")
    _require(set(receipt) == STAGE_RECEIPT_KEYS, f"{stage} receipt schema")
    receipt_sha256 = _verify_self_hash(receipt, "receiptSha256", label=f"{stage} receipt")
    expected_protocol = BLIND_RECEIPT_PROTOCOL if stage_kind == "blind" else GENERATOR_RECEIPT_PROTOCOL
    _require(
        receipt.get("schemaVersion") == 1
        and receipt.get("protocol") == expected_protocol
        and receipt.get("status") == "completed_first_attempt"
        and receipt.get("stage") == stage
        and receipt.get("stageKind") == stage_kind
        and receipt.get("campaignId") == campaign_id,
        f"{stage} receipt identity",
    )
    receipt_bindings = {
        "sourceFreezeSha256": source_freeze_sha256,
        "publicArtifactSha256": public_sha256,
        "promptSha256": observed_hashes["prompt"],
        "outputSchemaSha256": observed_hashes["output schema"],
        "outputSchemaCliArg": OUTPUT_SCHEMA_CLI_ARG,
        "strictConfig": True,
        "configArgv": list(STRICT_CONFIG_ARGV),
        "configArgvSha256": STRICT_CONFIG_ARGV_SHA256,
        "ignoreUserConfig": True,
        "ignoreRules": True,
        "ephemeral": True,
        "codexCliVersion": CODEX_CLI_VERSION,
        "codexFeaturesSnapshotSha256": CODEX_FEATURES_SNAPSHOT_SHA256,
        "codexFeatureListStdoutSha256": CODEX_FEATURE_LIST_STDOUT_SHA256,
        "codexFeatureCount": CODEX_FEATURE_COUNT,
        "stdinPacketSha256": observed_hashes["prompt"],
        "stdinPacketPublicSha256": public_sha256,
        "executionSettings": dict(expected_settings),
        "rawOutputSha256": observed_hashes["raw output"],
        "normalizedArtifactSha256": observed_hashes["artifact"],
        "traceSha256": observed_hashes["trace"],
        "validationReportSha256": validation_report_sha256,
        "attemptLedgerSha256": attempt_ledger_sha256,
        "tokenLedgerSha256": token_ledger_sha256,
        "implementationCodeHashes": code_hashes,
    }
    for field, expected in receipt_bindings.items():
        _require(receipt.get(field) == expected, f"{stage} receipt {field}")
    _require(
        receipt.get("semanticModelInvocations") == 1
        and receipt.get("firstAttemptOnly") is True
        and receipt.get("noSelectiveRetry") is True
        and receipt.get("inputDelivery") == "stdin_embedded_public_packet"
        and receipt.get("outputSchemaCliArg") == OUTPUT_SCHEMA_CLI_ARG
        and receipt.get("strictConfig") is True
        and receipt.get("configArgv") == list(STRICT_CONFIG_ARGV)
        and receipt.get("configArgvSha256") == STRICT_CONFIG_ARGV_SHA256
        and receipt.get("ignoreUserConfig") is True
        and receipt.get("ignoreRules") is True
        and receipt.get("ephemeral") is True
        and receipt.get("configuredModelToolSchemaCount") == 0
        and receipt.get("finalResponseStrictParsed") is True
        and receipt.get("legacyFileAgentUsed") is False,
        f"{stage} receipt attempt policy",
    )
    visibility = receipt.get("visibilityBoundary")
    audit = receipt.get("policyAudit")
    _require(isinstance(visibility, dict) and set(visibility) == VISIBILITY_KEYS, f"{stage} visibility schema")
    _require(isinstance(audit, dict) and set(audit) == POLICY_AUDIT_KEYS, f"{stage} policy-audit schema")
    _require(
        all(type(audit[key]) is int and audit[key] >= 0 for key in POLICY_AUDIT_KEYS),
        f"{stage} policy-audit counts",
    )
    trace_audit = _audit_zero_tool_trace(paths["trace"], stage=stage)
    trace_tool_counts = trace_audit["counts"]
    _require(
        all(audit[key] == value for key, value in trace_tool_counts.items()),
        f"{stage} raw trace tool-event audit mismatch",
    )
    _require(receipt.get("threadIds") == trace_audit["threadIds"], f"{stage} thread receipt")
    zero_tool_contract = bool(
        receipt.get("configuredModelToolSchemaCount") == 0
        and receipt.get("configuredModelToolSchemas") == []
        and receipt.get("configuredModelToolSchemasSha256")
        == EMPTY_TOOL_SCHEMAS_SHA256
        and receipt.get("toolSchemaAdvertisementAttested") is False
        and receipt.get("strictConfig") is True
        and receipt.get("configArgv") == list(STRICT_CONFIG_ARGV)
        and receipt.get("configArgvSha256") == STRICT_CONFIG_ARGV_SHA256
        and receipt.get("ignoreUserConfig") is True
        and receipt.get("ignoreRules") is True
        and receipt.get("ephemeral") is True
        and receipt.get("codexCliVersion") == CODEX_CLI_VERSION
        and receipt.get("codexFeaturesSnapshotSha256")
        == CODEX_FEATURES_SNAPSHOT_SHA256
        and receipt.get("codexFeatureListStdoutSha256")
        == CODEX_FEATURE_LIST_STDOUT_SHA256
        and receipt.get("codexFeatureCount") == CODEX_FEATURE_COUNT
        and expected_settings.get("localCode") is False
        and expected_settings.get("strictConfig") is True
        and expected_settings.get("configArgvSha256")
        == STRICT_CONFIG_ARGV_SHA256
        and isinstance(expected_settings.get("features"), dict)
        and expected_settings["features"]
        == {feature: False for feature in TOOL_FREE_DISABLED_FEATURES}
        and all(audit[key] == 0 for key in POLICY_AUDIT_KEYS)
    )
    gold_access = bool(
        visibility.get("privateGoldMounted") is not False
        or visibility.get("privateLabelsMounted") is not False
        or visibility.get("goldFilesDiscoverable") is not False
        or audit["goldReadEvents"] != 0
        or audit["privateLabelReadEvents"] != 0
    )
    provenance_blind = bool(
        stage_kind == "blind"
        and visibility.get("roleMappingMounted") is False
        and visibility.get("otherGeneratorArtifactsMounted") is False
        and visibility.get("candidateProvenanceExposed") is False
        and audit["roleMappingReadEvents"] == 0
        and audit["otherGeneratorArtifactReadEvents"] == 0
    )
    _require(not gold_access, f"{stage} validated receipt indicates gold access")
    if stage_kind == "blind":
        _require(provenance_blind, "BLIND validated receipt is not provenance-blind")
    _require(
        visibility
        == {
            "publicFilesMounted": False,
            "privateGoldMounted": False,
            "privateLabelsMounted": False,
            "otherGeneratorArtifactsMounted": False,
            "roleMappingMounted": False,
            "candidateProvenanceExposed": False,
            "goldFilesDiscoverable": False,
        }
        and receipt.get("inputDelivery") == "stdin_embedded_public_packet",
        f"{stage} stdin-only isolated visibility boundary",
    )
    _require(zero_tool_contract, f"{stage} zero-tool trace/schema contract")
    _require(
        binding.get("receiptFileSha256") == receipt_file_sha256
        and binding.get("receiptSha256") == receipt_sha256,
        f"{stage} receipt manifest binding",
    )
    _require(binding.get("implementationCodeHashes") == code_hashes, f"{stage} code-hash manifest binding")
    return {
        "validIds": valid_ids,
        "invalidIds": invalid_ids,
        "receiptSha256": receipt_sha256,
        "receiptFileSha256": receipt_file_sha256,
        "goldAccess": gold_access,
        "provenanceBlind": provenance_blind,
        "zeroToolContract": zero_tool_contract,
        "authNotExposedViaModelToolSurface": zero_tool_contract,
        "tokenTotals": token_totals,
        "paths": paths,
        "hashes": observed_hashes,
        "traceToolCounts": trace_tool_counts,
        "threadIds": trace_audit["threadIds"],
    }


def _blind_conflict_package(
    *,
    conflict_ids: Sequence[str],
    generators: Mapping[str, Mapping[str, Mapping[str, Any]]],
    carrier_seed: str,
    rotation_seed: str,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for case_id in conflict_ids:
        carrier = proposal_carrier(carrier_seed, case_id)
        incumbent = str(generators["G1"][case_id]["outcome"])
        proposed = str(generators[carrier][case_id]["outcome"])
        left_role, right_role = expected_roles(rotation_seed, case_id)
        row = {
            "id": case_id,
            "incumbentOutcome": incumbent,
            "proposedOutcome": proposed,
            "proposalCarrier": carrier,
            "leftOutcome": incumbent if left_role == "INCUMBENT" else proposed,
            "rightOutcome": incumbent if right_role == "INCUMBENT" else proposed,
        }
        _require(set(row) == BLIND_CONFLICT_PACKAGE_KEYS, "blind conflict package schema")
        rows.append(row)
    return rows


def _validate_blind_package_freeze(
    freeze: dict[str, Any],
    *,
    freeze_file_sha256: str,
    expected_freeze_file_sha256: str,
    campaign_id: str,
    source_freeze_file_sha256: str,
    source_freeze_sha256: str,
    source_freeze: Mapping[str, Any],
    generator_stage_bindings: Mapping[str, Mapping[str, Any]],
    conflict_package: Sequence[Mapping[str, str]],
    instantiated_prompt_sha256: str,
    instantiated_output_schema_sha256: str,
    role_mapping_sha256: str,
) -> str:
    _verify_external_file_hash(
        freeze_file_sha256,
        expected_freeze_file_sha256,
        label="blind-package freeze",
    )
    _require(set(freeze) == BLIND_PACKAGE_FREEZE_KEYS, "blind-package freeze schema")
    freeze_sha256 = _verify_self_hash(
        freeze, "freezeSha256", label="blind-package freeze"
    )
    _require(
        freeze.get("schemaVersion") == 1
        and freeze.get("protocol") == BLIND_PACKAGE_FREEZE_PROTOCOL
        and freeze.get("status") == BLIND_PACKAGE_FREEZE_STATUS
        and freeze.get("campaignId") == campaign_id,
        "blind-package freeze identity",
    )
    _require(
        freeze.get("sourceFreezeFileSha256") == source_freeze_file_sha256
        and freeze.get("sourceFreezeSha256") == source_freeze_sha256,
        "blind-package source-freeze binding",
    )
    source_cross_bindings = {
        "blindPromptTemplateSha256": source_freeze["blindPromptTemplateSha256"],
        "blindOutputSchemaTemplateSha256": source_freeze[
            "blindOutputSchemaTemplateSha256"
        ],
        "blindPackageContractSha256": source_freeze["blindPackageContractSha256"],
        "blindPackageDerivationCodeHashes": source_freeze[
            "blindPackageDerivationCodeHashes"
        ],
        "carrierSelectionSeed": source_freeze["carrierSelectionSeed"],
        "roleRotationSeed": source_freeze["roleRotationSeed"],
    }
    for field, expected in source_cross_bindings.items():
        _require(freeze.get(field) == expected, f"blind-package freeze {field}")
    _verify_code_hashes(
        freeze.get("blindPackageDerivationCodeHashes"),
        label="blind-package derivation",
    )

    expected_stage_receipts = {
        name: {
            key: generator_stage_bindings[name][key]
            for key in BLIND_PACKAGE_GENERATOR_RECEIPT_KEYS
        }
        for name in GENERATOR_NAMES
    }
    claimed_stage_receipts = freeze.get("generatorStageReceipts")
    _require(
        isinstance(claimed_stage_receipts, dict)
        and set(claimed_stage_receipts) == set(GENERATOR_NAMES)
        and all(
            isinstance(claimed_stage_receipts[name], dict)
            and set(claimed_stage_receipts[name])
            == BLIND_PACKAGE_GENERATOR_RECEIPT_KEYS
            for name in GENERATOR_NAMES
        )
        and claimed_stage_receipts == expected_stage_receipts,
        "blind-package generator-stage binding",
    )
    conflict_ids = [row["id"] for row in conflict_package]
    _require(
        freeze.get("expectedConflictRows") == len(conflict_package)
        and freeze.get("expectedConflictIdsSha256") == canonical_digest(conflict_ids)
        and freeze.get("orderedConflictPackageSha256")
        == canonical_digest(list(conflict_package)),
        "blind-package conflict inventory binding",
    )
    _require(
        freeze.get("instantiatedBlindPromptPacketSha256")
        == instantiated_prompt_sha256
        and freeze.get("instantiatedBlindOutputSchemaSha256")
        == instantiated_output_schema_sha256
        and freeze.get("blindRoleMappingSha256") == role_mapping_sha256,
        "blind-package instantiated artifact binding",
    )
    return freeze_sha256


def _validate_blind_artifacts(
    certificates: list[dict[str, Any]],
    role_mapping: list[dict[str, Any]],
    *,
    conflict_ids: list[str],
    valid_certificate_ids: set[str],
    generators: Mapping[str, Mapping[str, Mapping[str, Any]]],
    carrier_seed: str,
    rotation_seed: str,
) -> dict[str, dict[str, Any]]:
    _require(len(certificates) == len(conflict_ids), "blind certificate row count mismatch")
    _require(len(role_mapping) == len(conflict_ids), "blind role-mapping row count mismatch")
    cert_by_id: dict[str, dict[str, Any]] = {}
    for position, (certificate, mapping, case_id) in enumerate(
        zip(certificates, role_mapping, conflict_ids, strict=True), 1
    ):
        _require(
            isinstance(certificate, dict) and set(certificate) == CERTIFICATE_KEYS,
            f"blind certificate row {position} schema",
        )
        _require(
            isinstance(mapping, dict) and set(mapping) == ROLE_MAPPING_KEYS,
            f"blind role-mapping row {position} schema",
        )
        _require(
            certificate.get("id") == mapping.get("id") == case_id,
            f"blind IDs/order mismatch at {position}",
        )
        preference = certificate.get("preference")
        _require(
            isinstance(preference, str) and preference in BLIND_PREFERENCES,
            f"blind {case_id} preference",
        )
        if case_id not in valid_certificate_ids:
            _require(preference == "UNRESOLVED", f"blind {case_id} invalid-row placeholder")
        left_role, right_role = expected_roles(rotation_seed, case_id)
        _require(
            (mapping.get("leftRole"), mapping.get("rightRole"))
            == (left_role, right_role),
            f"blind {case_id} role rotation mismatch",
        )
        _require(
            isinstance(mapping.get("leftRole"), str)
            and isinstance(mapping.get("rightRole"), str)
            and {mapping["leftRole"], mapping["rightRole"]} == ROLES,
            f"blind {case_id} roles invalid",
        )
        carrier = proposal_carrier(carrier_seed, case_id)
        incumbent = str(generators["G1"][case_id]["outcome"])
        proposed = str(generators[carrier][case_id]["outcome"])
        expected_left = incumbent if left_role == "INCUMBENT" else proposed
        expected_right = incumbent if right_role == "INCUMBENT" else proposed
        _require(
            certificate.get("leftOutcome") == expected_left
            and certificate.get("rightOutcome") == expected_right,
            f"blind {case_id} compared outcomes mismatch",
        )
        cert_by_id[case_id] = {
            "certificate": certificate,
            "mapping": mapping,
            "carrier": carrier,
            "firstAttemptValid": case_id in valid_certificate_ids,
        }
    return cert_by_id


def _explicit_incumbent_veto(item: Mapping[str, Any]) -> bool:
    certificate = item["certificate"]
    mapping = item["mapping"]
    preference = certificate["preference"]
    return bool(
        (preference == "PREFER_LEFT" and mapping["leftRole"] == "INCUMBENT")
        or (preference == "PREFER_RIGHT" and mapping["rightRole"] == "INCUMBENT")
    )


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"".join(canonical_json_bytes(row) + b"\n" for row in rows))


def _policy_definition(name: str) -> str:
    return {
        "base": "exact_G1_outcome",
        "answer_only": "switch_iff_G2_equals_G3_and_differs_from_G1",
        "answer_only_blind_veto": (
            "answer_only_switch_unless_blind_explicitly_prefers_hidden_incumbent"
        ),
        "structured_overlap": (
            "answer_only_conflict_plus_same_issue_tagged_evidence_clause_G2_G3_overlap"
        ),
        "structured_overlap_blind_veto": (
            "same_issue_tagged_evidence_clause_switch_unless_blind_explicit_incumbent_veto"
        ),
    }[name]


def _id_set(ids: list[str]) -> dict[str, Any]:
    return {"count": len(ids), "ids": ids, "idsSha256": canonical_digest(ids)}


def _publish(
    output_dir: Path,
    *,
    expected_ids: list[str],
    generators: Mapping[str, Mapping[str, Mapping[str, Any]]],
    decisions: list[dict[str, Any]],
    source_bindings: Mapping[str, Any],
    generator_hashes: Mapping[str, str],
    blind_bindings: Mapping[str, Any],
    campaign_bindings: Mapping[str, Any],
    stage_evidence: Mapping[str, Mapping[str, Any]],
    derived_gold_access: bool,
    derived_provenance_blind: bool,
) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    _require(not output_dir.exists(), f"refusing to overwrite output: {output_dir}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}.combining-", dir=output_dir.parent)
    )
    try:
        decision_path = temporary / "mechanism_decisions.jsonl"
        _write_jsonl(decision_path, decisions)
        policies: dict[str, Any] = {}
        decision_by_id = {row["id"]: row for row in decisions}
        for policy in POLICIES:
            deployment_rows = [
                {"id": case_id, "outcome": decision_by_id[case_id]["policies"][policy]}
                for case_id in expected_ids
            ]
            scoring_rows = [
                {
                    "id": case_id,
                    "outcome": (
                        decision_by_id[case_id]["policies"][policy]
                        if decision_by_id[case_id]["policyValidity"][policy]
                        else None
                    ),
                }
                for case_id in expected_ids
            ]
            deployment_path = (
                temporary / "policies" / policy / "deployment_fallback_answers.jsonl"
            )
            scoring_path = (
                temporary / "policies" / policy / "full_denominator_predictions.jsonl"
            )
            _write_jsonl(deployment_path, deployment_rows)
            _write_jsonl(scoring_path, scoring_rows)
            reloaded_deployment, deployment_sha256 = _load_jsonl(
                deployment_path, label=f"published {policy} deployment"
            )
            reloaded_scoring, scoring_sha256 = _load_jsonl(
                scoring_path, label=f"published {policy} scoring"
            )
            _require(
                reloaded_deployment == deployment_rows and reloaded_scoring == scoring_rows,
                f"published {policy} changed after write",
            )
            deployment_switch_ids = [
                case_id
                for case_id in expected_ids
                if decision_by_id[case_id]["policies"][policy]
                != generators["G1"][case_id]["outcome"]
            ]
            valid_ids = [
                case_id
                for case_id in expected_ids
                if decision_by_id[case_id]["policyValidity"][policy]
            ]
            invalid_ids = [case_id for case_id in expected_ids if case_id not in set(valid_ids)]
            scientific_switch_ids = [
                case_id
                for case_id in valid_ids
                if decision_by_id[case_id]["policies"][policy]
                != generators["G1"][case_id]["outcome"]
            ]
            for row in deployment_rows:
                case_id = row["id"]
                allowed = {
                    generators["G1"][case_id]["outcome"],
                    generators["G2"][case_id]["outcome"],
                    generators["G3"][case_id]["outcome"],
                }
                _require(row["outcome"] in allowed, f"published {policy} synthesis detected")
            policies[policy] = {
                "definition": _policy_definition(policy),
                "fullDenominatorPredictionsPath": (
                    f"policies/{policy}/full_denominator_predictions.jsonl"
                ),
                "fullDenominatorPredictionsSha256": scoring_sha256,
                "deploymentFallbackAnswersPath": (
                    f"policies/{policy}/deployment_fallback_answers.jsonl"
                ),
                "deploymentFallbackAnswersSha256": deployment_sha256,
                "rows": len(deployment_rows),
                "validRows": _id_set(valid_ids),
                "firstAttemptInvalidRowsScoredWrong": _id_set(invalid_ids),
                "scientificSwitchesFromG1": _id_set(scientific_switch_ids),
                "deploymentSwitchesFromG1": _id_set(deployment_switch_ids),
            }

        answer_conflicts = [row["id"] for row in decisions if row["answerOnlyConflict"]]
        structured = [row["id"] for row in decisions if row["structuredOverlapTrigger"]]
        incumbent_vetoes = [row["id"] for row in decisions if row["blindIncumbentVeto"]]
        structured_vetoes = [
            row["id"]
            for row in decisions
            if row["structuredOverlapTrigger"] and row["blindIncumbentVeto"]
        ]
        tie_or_unresolved = [
            row["id"]
            for row in decisions
            if row["blindFirstAttemptValid"] is True
            and row["blindPreference"] in {"TIE", "UNRESOLVED"}
        ]
        blind_invalid = [
            row["id"] for row in decisions if row["blindFirstAttemptValid"] is False
        ]
        carrier_g2 = [row["id"] for row in decisions if row["proposalCarrier"] == "G2"]
        carrier_g3 = [row["id"] for row in decisions if row["proposalCarrier"] == "G3"]

        implementation_path = Path(__file__).resolve()
        receipt: dict[str, Any] = {
            "schemaVersion": 1,
            "status": "accepted",
            "protocol": PROTOCOL,
            "scope": "single_sealed_shard_mechanism_core",
            "finalCampaignRunner": False,
            "goldAccess": derived_gold_access,
            "provenanceBlind": derived_provenance_blind,
            "authNotExposedViaModelToolSurface": bool(
                campaign_bindings["authNotExposedViaModelToolSurface"]
            ),
            "receiptDerivedProperties": {
                "goldAccess": "OR over validated stage receipt visibility/audit evidence",
                "provenanceBlind": "validated BLIND receipt role/provenance boundary",
                "authNotExposedViaModelToolSurface": (
                    "AND over validated zero-tool CLI/settings/raw-trace contracts; "
                    "not a filesystem-unmount claim"
                ),
            },
            "toolSurfaceEvidenceScope": {
                "enumeratedSurfacesConfiguredFalse": True,
                "configuredModelToolSchemas": [],
                "rawTraceToolEventsObserved": 0,
                "providerToolSchemaAdvertisementAttested": False,
                "claimScope": "frozen configuration plus observed raw trace only",
            },
            "synthesis": False,
            "firstAttemptOnly": True,
            "selectiveRetry": False,
            "invalidRowScientificRule": "null outcome; retained in full denominator and scored wrong",
            "deploymentFallbackSeparated": True,
            "expectedRows": len(expected_ids),
            "expectedIds": _id_set(expected_ids),
            "sourceBindings": dict(source_bindings),
            "generatorArtifactsSha256": dict(generator_hashes),
            "blindBindings": dict(blind_bindings),
            "campaignBindings": dict(campaign_bindings),
            "stageEvidence": {name: dict(value) for name, value in stage_evidence.items()},
            "mechanism": {
                "atomKey": [
                    "issueCode",
                    "evidenceClauseId",
                    "exactQuote",
                    "direction",
                    "outcome",
                ],
                "overlapMeaning": "same issue-tagged evidence clause",
                "quoteContract": (
                    "exactQuote equals the complete referenced numbered-clause text"
                ),
                "proposalCarrierScheme": "sha256-domain-seed-nul-id-low-bit-v1",
                "roleRotationScheme": "sha256-domain-seed-nul-id-low-bit-v1",
                "answerOnlyConflicts": _id_set(answer_conflicts),
                "structuredOverlapTriggers": _id_set(structured),
                "blindExplicitIncumbentVetoes": _id_set(incumbent_vetoes),
                "structuredTriggerVetoes": _id_set(structured_vetoes),
                "blindTieOrUnresolved": _id_set(tie_or_unresolved),
                "blindFirstAttemptInvalid": _id_set(blind_invalid),
                "proposalCarrierG2": _id_set(carrier_g2),
                "proposalCarrierG3": _id_set(carrier_g3),
            },
            "decisionManifest": {
                "path": "mechanism_decisions.jsonl",
                "rows": len(decisions),
                "sha256": sha256_file(decision_path),
            },
            "policies": policies,
            "comparatorFairness": {
                "required": True,
                "validatedHere": False,
                "status": "PENDING_EXTERNAL_AUDIT",
            },
            "implementationHashes": {str(implementation_path): sha256_file(implementation_path)},
        }
        receipt["receiptSha256"] = canonical_digest(receipt)
        receipt_path = temporary / "mechanism_receipt.json"
        _write_json(receipt_path, receipt)
        reloaded_receipt, _ = _load_json_object(receipt_path, label="mechanism receipt")
        _verify_self_hash(reloaded_receipt, "receiptSha256", label="mechanism receipt")
        os.rename(temporary, output_dir)
        return receipt
    except BaseException:
        if temporary.exists() and temporary.parent == output_dir.parent:
            shutil.rmtree(temporary)
        raise


def _combine_structured_legal_overlap(
    *,
    public_path: Path,
    source_freeze_path: Path,
    expected_source_freeze_file_sha256: str,
    campaign_manifest_path: Path,
    expected_campaign_manifest_file_sha256: str,
    blind_package_freeze_path: Path,
    expected_blind_package_freeze_file_sha256: str,
    g1_path: Path,
    g2_path: Path,
    g3_path: Path,
    blind_certificates_path: Path,
    blind_role_mapping_path: Path,
    blind_receipt_path: Path,
    expected_blind_receipt_file_sha256: str,
    output_dir: Path,
) -> dict[str, Any]:
    _require(not output_dir.resolve().exists(), f"refusing to overwrite output: {output_dir.resolve()}")

    public_rows, public_sha256 = _load_jsonl(public_path, label="public corpus")
    expected_ids, clauses_by_id = _validate_public_rows(public_rows)

    campaign_manifest, campaign_manifest_file_sha256 = _load_json_object(
        campaign_manifest_path, label="campaign manifest"
    )
    campaign_manifest_sha256 = _validate_campaign_manifest_structure(
        campaign_manifest,
        manifest_file_sha256=campaign_manifest_file_sha256,
        expected_manifest_file_sha256=expected_campaign_manifest_file_sha256,
    )
    campaign_root = campaign_manifest_path.resolve().parent
    source_evidence = _validate_campaign_source_artifacts(
        campaign_manifest["sourceArtifacts"],
        campaign_root=campaign_root,
        explicit_public_path=public_path,
        public_rows=public_rows,
        public_sha256=public_sha256,
        expected_ids=expected_ids,
    )

    source_freeze, source_freeze_file_sha256 = _load_json_object(
        source_freeze_path, label="source freeze"
    )
    source_freeze_sha256, campaign_id, carrier_seed, rotation_seed = _validate_source_freeze(
        source_freeze,
        freeze_file_sha256=source_freeze_file_sha256,
        expected_freeze_file_sha256=expected_source_freeze_file_sha256,
        public_sha256=public_sha256,
        expected_ids=expected_ids,
        builder_manifest_file_sha256=source_evidence["builderManifestFileSha256"],
        builder_manifest_self_hash=source_evidence["builderManifestSelfHash"],
        id_receipt_file_sha256=source_evidence["labelIndependentIdReceiptFileSha256"],
        id_receipt_sha256=source_evidence["labelIndependentIdReceiptSha256"],
        conclusion_leak_report_file_sha256=source_evidence[
            "conclusionLeakReportFileSha256"
        ],
        conclusion_leak_report_sha256=source_evidence["conclusionLeakReportSha256"],
        generator_output_schema_sha256=source_evidence[
            "generatorOutputSchemaSha256"
        ],
        blind_prompt_template_sha256=source_evidence["blindPromptTemplateSha256"],
        blind_output_schema_template_sha256=source_evidence[
            "blindOutputSchemaTemplateSha256"
        ],
    )
    _require(
        campaign_manifest.get("campaignId") == campaign_id
        and campaign_manifest.get("sourceFreezeFileSha256") == source_freeze_file_sha256
        and campaign_manifest.get("sourceFreezeSha256") == source_freeze_sha256,
        "campaign manifest source-freeze binding",
    )
    manifest_source = campaign_manifest["sourceArtifacts"]
    source_cross_bindings = {
        "publicSha256": public_sha256,
        "builderManifestFileSha256": source_evidence["builderManifestFileSha256"],
        "builderManifestSelfHash": source_evidence["builderManifestSelfHash"],
        "labelIndependentIdReceiptFileSha256": source_evidence[
            "labelIndependentIdReceiptFileSha256"
        ],
        "labelIndependentIdReceiptSha256": source_evidence[
            "labelIndependentIdReceiptSha256"
        ],
        "conclusionLeakReportFileSha256": source_evidence[
            "conclusionLeakReportFileSha256"
        ],
        "conclusionLeakReportSha256": source_evidence["conclusionLeakReportSha256"],
        "generatorOutputSchemaSha256": source_evidence[
            "generatorOutputSchemaSha256"
        ],
        "blindPromptTemplateSha256": source_evidence["blindPromptTemplateSha256"],
        "blindOutputSchemaTemplateSha256": source_evidence[
            "blindOutputSchemaTemplateSha256"
        ],
    }
    for field, expected in source_cross_bindings.items():
        _require(manifest_source.get(field) == expected, f"campaign source {field}")

    generator_paths = {"G1": g1_path, "G2": g2_path, "G3": g3_path}
    stage_bindings = campaign_manifest["stages"]
    stage_evidence: dict[str, dict[str, Any]] = {}
    generator_valid_ids: dict[str, set[str]] = {}
    for name in GENERATOR_NAMES:
        evidence = _validate_stage_binding(
            stage=name,
            binding=stage_bindings[name],
            campaign_root=campaign_root,
            explicit_artifact_path=generator_paths[name],
            explicit_role_mapping_path=None,
            expected_ids=expected_ids,
            campaign_id=campaign_id,
            source_freeze_sha256=source_freeze_sha256,
            public_sha256=public_sha256,
            expected_prompt_sha256=str(source_freeze["generatorPromptSha256"]),
            expected_output_schema_sha256=str(
                source_freeze["generatorOutputSchemaSha256"]
            ),
            expected_settings=source_freeze["generatorExecutionSettings"],
        )
        stage_evidence[name] = evidence
        generator_valid_ids[name] = set(evidence["validIds"])

    generator_rows: dict[str, list[dict[str, Any]]] = {}
    generator_hashes: dict[str, str] = {}
    for name in GENERATOR_NAMES:
        rows, digest = _load_jsonl(generator_paths[name], label=f"{name} artifact")
        _require(digest == stage_bindings[name]["artifactSha256"], f"{name} artifact campaign hash")
        generator_rows[name] = rows
        generator_hashes[name] = digest
    generators = _validate_generators(
        generator_rows,
        expected_ids=expected_ids,
        clauses_by_id=clauses_by_id,
        valid_ids_by_generator=generator_valid_ids,
    )

    all_generator_valid = {
        case_id
        for case_id in expected_ids
        if all(case_id in generator_valid_ids[name] for name in GENERATOR_NAMES)
    }
    conflict_ids = [
        case_id
        for case_id in expected_ids
        if case_id in all_generator_valid
        and generators["G2"][case_id]["outcome"]
        == generators["G3"][case_id]["outcome"]
        != generators["G1"][case_id]["outcome"]
    ]
    conflict_package = _blind_conflict_package(
        conflict_ids=conflict_ids,
        generators=generators,
        carrier_seed=carrier_seed,
        rotation_seed=rotation_seed,
    )
    certificates, certificates_sha256 = _load_jsonl(
        blind_certificates_path, label="blind certificates", allow_empty=True
    )
    role_mapping, role_mapping_sha256 = _load_jsonl(
        blind_role_mapping_path, label="blind role mapping", allow_empty=True
    )
    blind_binding = stage_bindings["BLIND"]
    blind_prompt_path = _safe_manifest_path(
        campaign_root, blind_binding.get("promptPath"), label="BLIND prompt packet"
    )
    _, blind_prompt_sha256 = _read_regular_bytes(
        blind_prompt_path, label="BLIND prompt packet"
    )
    blind_template_raw, _ = _read_regular_bytes(
        source_evidence["blindPromptTemplatePath"],
        label="blind prompt template",
    )
    expected_blind_prompt_packet = render_blind_prompt_packet(
        template_bytes=blind_template_raw,
        public_rows_by_id={row["id"]: row for row in public_rows},
        conflict_package=conflict_package,
    )
    _require(
        blind_prompt_sha256 == sha256_bytes(expected_blind_prompt_packet),
        "BLIND instantiated prompt packet derivation",
    )
    blind_output_schema_path = _safe_manifest_path(
        campaign_root,
        blind_binding.get("outputSchemaPath"),
        label="BLIND output schema",
    )
    blind_output_schema, blind_output_schema_sha256 = _load_json_object(
        blind_output_schema_path, label="BLIND output schema"
    )
    blind_output_schema_template, _ = _load_json_object(
        source_evidence["blindOutputSchemaTemplatePath"],
        label="blind output-schema template",
    )
    _require(
        blind_output_schema
        == instantiate_blind_output_schema(
            blind_output_schema_template,
            conflict_count=len(conflict_ids),
        ),
        "BLIND instantiated output-schema derivation",
    )
    blind_package_freeze, blind_package_freeze_file_sha256 = _load_json_object(
        blind_package_freeze_path, label="blind-package freeze"
    )
    blind_package_freeze_sha256 = _validate_blind_package_freeze(
        blind_package_freeze,
        freeze_file_sha256=blind_package_freeze_file_sha256,
        expected_freeze_file_sha256=expected_blind_package_freeze_file_sha256,
        campaign_id=campaign_id,
        source_freeze_file_sha256=source_freeze_file_sha256,
        source_freeze_sha256=source_freeze_sha256,
        source_freeze=source_freeze,
        generator_stage_bindings={name: stage_bindings[name] for name in GENERATOR_NAMES},
        conflict_package=conflict_package,
        instantiated_prompt_sha256=blind_prompt_sha256,
        instantiated_output_schema_sha256=blind_output_schema_sha256,
        role_mapping_sha256=role_mapping_sha256,
    )
    _require(
        campaign_manifest.get("blindPackageFreezeFileSha256")
        == blind_package_freeze_file_sha256
        and campaign_manifest.get("blindPackageFreezeSha256")
        == blind_package_freeze_sha256,
        "campaign manifest blind-package-freeze binding",
    )
    blind_evidence = _validate_stage_binding(
        stage="BLIND",
        binding=stage_bindings["BLIND"],
        campaign_root=campaign_root,
        explicit_artifact_path=blind_certificates_path,
        explicit_role_mapping_path=blind_role_mapping_path,
        expected_ids=conflict_ids,
        campaign_id=campaign_id,
        source_freeze_sha256=source_freeze_sha256,
        public_sha256=public_sha256,
        expected_prompt_sha256=str(
            blind_package_freeze["instantiatedBlindPromptPacketSha256"]
        ),
        expected_output_schema_sha256=str(
            blind_package_freeze["instantiatedBlindOutputSchemaSha256"]
        ),
        expected_settings=source_freeze["blindExecutionSettings"],
    )
    stage_evidence["BLIND"] = blind_evidence
    _require(
        blind_evidence["paths"]["receipt"] == blind_receipt_path.resolve()
        and blind_evidence["receiptFileSha256"] == expected_blind_receipt_file_sha256,
        "BLIND explicit receipt binding",
    )
    _require(
        certificates_sha256 == stage_bindings["BLIND"]["artifactSha256"]
        and role_mapping_sha256 == stage_bindings["BLIND"]["roleMappingSha256"],
        "BLIND campaign artifact binding",
    )
    blind_by_id = _validate_blind_artifacts(
        certificates,
        role_mapping,
        conflict_ids=conflict_ids,
        valid_certificate_ids=set(blind_evidence["validIds"]),
        generators=generators,
        carrier_seed=carrier_seed,
        rotation_seed=rotation_seed,
    )

    decisions: list[dict[str, Any]] = []
    for case_id in expected_ids:
        g1 = generators["G1"][case_id]
        g2 = generators["G2"][case_id]
        g3 = generators["G3"][case_id]
        g1_valid = case_id in generator_valid_ids["G1"]
        all_g_valid = case_id in all_generator_valid
        conflict = all_g_valid and case_id in blind_by_id
        carrier = blind_by_id[case_id]["carrier"] if conflict else None
        incumbent_deployment = g1["outcome"] if g1_valid else "ABSTAIN"
        proposed = (
            generators[str(carrier)][case_id]["outcome"]
            if carrier
            else incumbent_deployment
        )
        overlap_keys: list[tuple[str, str, str, str, str]] = []
        if conflict:
            g2_keys = {_atom_key(atom, str(g2["outcome"])) for atom in g2["evidenceAtoms"]}
            g3_keys = {_atom_key(atom, str(g3["outcome"])) for atom in g3["evidenceAtoms"]}
            overlap_keys = sorted(
                key
                for key in g2_keys & g3_keys
                if DIRECTION_FOR_OUTCOME.get(str(proposed)) == key[3]
            )
        structured_trigger = conflict and bool(overlap_keys)
        blind_valid = blind_by_id[case_id]["firstAttemptValid"] if conflict else None
        veto = (
            _explicit_incumbent_veto(blind_by_id[case_id])
            if conflict and blind_valid
            else False
        )
        blind_preference = (
            blind_by_id[case_id]["certificate"]["preference"] if conflict else None
        )
        multi_stage_fallback = incumbent_deployment
        policy_outcomes = {
            "base": incumbent_deployment,
            "answer_only": proposed if conflict else multi_stage_fallback,
            "answer_only_blind_veto": (
                proposed
                if conflict and blind_valid and not veto
                else multi_stage_fallback
            ),
            "structured_overlap": (
                proposed if structured_trigger else multi_stage_fallback
            ),
            "structured_overlap_blind_veto": (
                proposed
                if structured_trigger and blind_valid and not veto
                else multi_stage_fallback
            ),
        }
        answer_veto_stage_valid = bool(
            all_g_valid and (not conflict or blind_valid is True)
        )
        structured_veto_stage_valid = bool(
            all_g_valid and (not structured_trigger or blind_valid is True)
        )
        policy_validity = {
            "base": g1_valid,
            "answer_only": all_g_valid,
            "answer_only_blind_veto": answer_veto_stage_valid,
            "structured_overlap": all_g_valid,
            "structured_overlap_blind_veto": structured_veto_stage_valid,
        }
        decisions.append(
            {
                "id": case_id,
                "g1Outcome": g1["outcome"],
                "g2Outcome": g2["outcome"],
                "g3Outcome": g3["outcome"],
                "answerOnlyConflict": conflict,
                "proposalCarrier": carrier,
                "overlapAtomKey": list(overlap_keys[0]) if overlap_keys else None,
                "structuredOverlapTrigger": structured_trigger,
                "blindPreference": blind_preference,
                "blindFirstAttemptValid": blind_valid,
                "blindIncumbentVeto": veto,
                "stageValidity": {
                    "G1": g1_valid,
                    "G2": case_id in generator_valid_ids["G2"],
                    "G3": case_id in generator_valid_ids["G3"],
                    "BLIND": blind_valid,
                },
                "policies": policy_outcomes,
                "policyValidity": policy_validity,
            }
        )

    derived_gold_access = any(
        bool(stage_evidence[name]["goldAccess"]) for name in (*GENERATOR_NAMES, "BLIND")
    )
    derived_provenance_blind = bool(stage_evidence["BLIND"]["provenanceBlind"])
    derived_zero_tool = all(
        bool(stage_evidence[name]["zeroToolContract"])
        for name in (*GENERATOR_NAMES, "BLIND")
    )
    derived_auth_not_exposed = all(
        bool(stage_evidence[name]["authNotExposedViaModelToolSurface"])
        for name in (*GENERATOR_NAMES, "BLIND")
    )
    _require(not derived_gold_access, "campaign receipts indicate gold access")
    _require(derived_provenance_blind, "campaign blind receipt lacks provenance blindness")
    _require(derived_zero_tool, "campaign includes a non-zero tool surface")
    stage_thread_ids = [
        stage_evidence[name]["threadIds"][0]
        for name in (*GENERATOR_NAMES, "BLIND")
    ]
    _require(
        len(set(stage_thread_ids)) == len(stage_thread_ids),
        "stage thread identities are not distinct",
    )

    stage_receipt_summary = {
        name: {
            "receiptSha256": stage_evidence[name]["receiptSha256"],
            "receiptFileSha256": stage_evidence[name]["receiptFileSha256"],
            "firstAttemptInvalidIds": _id_set(stage_evidence[name]["invalidIds"]),
            "tokenTotals": stage_evidence[name]["tokenTotals"],
            "goldAccess": stage_evidence[name]["goldAccess"],
            "provenanceBlind": stage_evidence[name]["provenanceBlind"],
            "zeroToolContract": stage_evidence[name]["zeroToolContract"],
            "rawTraceToolEventCounts": stage_evidence[name]["traceToolCounts"],
            "configuredModelToolSchemaCount": 0,
            "toolSchemaAdvertisementAttested": False,
            "threadIds": stage_evidence[name]["threadIds"],
        }
        for name in (*GENERATOR_NAMES, "BLIND")
    }
    return _publish(
        output_dir,
        expected_ids=expected_ids,
        generators=generators,
        decisions=decisions,
        source_bindings={
            "publicPath": str(public_path.resolve()),
            "publicSha256": public_sha256,
            "sourceFreezePath": str(source_freeze_path.resolve()),
            "sourceFreezeFileSha256": source_freeze_file_sha256,
            "sourceFreezeSha256": source_freeze_sha256,
            "expectedIdsSha256": canonical_digest(expected_ids),
            "builderManifestFileSha256": source_evidence["builderManifestFileSha256"],
            "builderManifestSelfHash": source_evidence["builderManifestSelfHash"],
            "labelIndependentIdReceiptFileSha256": source_evidence[
                "labelIndependentIdReceiptFileSha256"
            ],
            "labelIndependentIdReceiptSha256": source_evidence[
                "labelIndependentIdReceiptSha256"
            ],
            "conclusionLeakReportFileSha256": source_evidence[
                "conclusionLeakReportFileSha256"
            ],
            "conclusionLeakReportSha256": source_evidence["conclusionLeakReportSha256"],
            "generatorOutputSchemaSha256": source_evidence[
                "generatorOutputSchemaSha256"
            ],
            "blindPromptTemplateSha256": source_evidence[
                "blindPromptTemplateSha256"
            ],
            "blindOutputSchemaTemplateSha256": source_evidence[
                "blindOutputSchemaTemplateSha256"
            ],
        },
        generator_hashes=generator_hashes,
        blind_bindings={
            "certificatesSha256": certificates_sha256,
            "roleMappingSha256": role_mapping_sha256,
            "receiptFileSha256": blind_evidence["receiptFileSha256"],
            "receiptSha256": blind_evidence["receiptSha256"],
            "blindPackageFreezePath": str(blind_package_freeze_path.resolve()),
            "blindPackageFreezeFileSha256": blind_package_freeze_file_sha256,
            "blindPackageFreezeSha256": blind_package_freeze_sha256,
            "externallySuppliedExpectedBlindPackageFreezeFileSha256": (
                expected_blind_package_freeze_file_sha256
            ),
            "instantiatedPromptPacketSha256": blind_prompt_sha256,
            "instantiatedOutputSchemaSha256": blind_output_schema_sha256,
            "carrierSelectionSeed": carrier_seed,
            "roleRotationSeed": rotation_seed,
        },
        campaign_bindings={
            "campaignId": campaign_id,
            "manifestPath": str(campaign_manifest_path.resolve()),
            "manifestFileSha256": campaign_manifest_file_sha256,
            "manifestSha256": campaign_manifest_sha256,
            "externallySuppliedExpectedManifestFileSha256": (
                expected_campaign_manifest_file_sha256
            ),
            "blindPackageFreezeFileSha256": blind_package_freeze_file_sha256,
            "blindPackageFreezeSha256": blind_package_freeze_sha256,
            "comparatorFairnessAudit": campaign_manifest["comparatorFairnessAudit"],
            "zeroToolContract": derived_zero_tool,
            "authNotExposedViaModelToolSurface": derived_auth_not_exposed,
        },
        stage_evidence=stage_receipt_summary,
        derived_gold_access=derived_gold_access,
        derived_provenance_blind=derived_provenance_blind,
    )


def combine_structured_legal_overlap(**kwargs: Any) -> dict[str, Any]:
    """Normalize programming/type faults to the fail-closed combination error."""

    try:
        return _combine_structured_legal_overlap(**kwargs)
    except CombinationValidationError:
        raise
    except (TypeError, KeyError, IndexError, AttributeError) as exc:
        raise CombinationValidationError(
            f"malformed input caused {type(exc).__name__}: {exc}"
        ) from exc


# Short alias for callers that already use ``combine_*`` modules uniformly.
combine = combine_structured_legal_overlap


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public", type=Path, required=True)
    parser.add_argument("--source-freeze", type=Path, required=True)
    parser.add_argument("--source-freeze-file-sha256", required=True)
    parser.add_argument("--campaign-manifest", type=Path, required=True)
    parser.add_argument("--campaign-manifest-file-sha256", required=True)
    parser.add_argument("--blind-package-freeze", type=Path, required=True)
    parser.add_argument("--blind-package-freeze-file-sha256", required=True)
    parser.add_argument("--g1", type=Path, required=True)
    parser.add_argument("--g2", type=Path, required=True)
    parser.add_argument("--g3", type=Path, required=True)
    parser.add_argument("--blind-certificates", type=Path, required=True)
    parser.add_argument("--blind-role-mapping", type=Path, required=True)
    parser.add_argument("--blind-receipt", type=Path, required=True)
    parser.add_argument("--blind-receipt-file-sha256", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        receipt = combine_structured_legal_overlap(
            public_path=args.public,
            source_freeze_path=args.source_freeze,
            expected_source_freeze_file_sha256=args.source_freeze_file_sha256,
            campaign_manifest_path=args.campaign_manifest,
            expected_campaign_manifest_file_sha256=(
                args.campaign_manifest_file_sha256
            ),
            blind_package_freeze_path=args.blind_package_freeze,
            expected_blind_package_freeze_file_sha256=(
                args.blind_package_freeze_file_sha256
            ),
            g1_path=args.g1,
            g2_path=args.g2,
            g3_path=args.g3,
            blind_certificates_path=args.blind_certificates,
            blind_role_mapping_path=args.blind_role_mapping,
            blind_receipt_path=args.blind_receipt,
            expected_blind_receipt_file_sha256=args.blind_receipt_file_sha256,
            output_dir=args.output_dir,
        )
    except (CombinationValidationError, OSError, ValueError) as exc:
        print(
            json.dumps(
                {
                    "status": "rejected",
                    "error": str(exc),
                    "confirmatoryEvidenceAccepted": False,
                    "outputsPublished": False,
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
