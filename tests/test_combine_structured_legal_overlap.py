from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import pytest

from tools import combine_structured_legal_overlap as overlap


IDS = (
    "outcome-confirm-00000000000000000001",
    "outcome-confirm-00000000000000000002",
    "outcome-confirm-00000000000000000003",
    "outcome-confirm-00000000000000000004",
    "outcome-confirm-00000000000000000005",
    "outcome-confirm-00000000000000000006",
)
CARRIER_SEED = "test-carrier-seed-v1"
ROTATION_SEED = "test-role-seed-v1"
CLAUSES = {
    "C001": "계약서에는 피고의 지급 의무가 명확하게 기재되어 있다.",
    "F001": "원고는 약정된 이행을 완료하였고 피고는 아직 지급하지 않았다.",
    "F002": "피고는 지급 의무의 성립 자체를 구체적인 자료로 다투고 있다.",
}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"".join(overlap.canonical_json_bytes(row) + b"\n" for row in rows))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def with_self_hash(value: dict[str, Any], field: str) -> dict[str, Any]:
    value[field] = overlap.canonical_digest(value)
    return value


def public_row(case_id: str) -> dict[str, str]:
    prompt = (
        "다음 번호가 붙은 근거절만 사용하십시오.\n\n"
        f"[C001] {CLAUSES['C001']}\n"
        f"[F001] {CLAUSES['F001']}\n"
        f"[F002] {CLAUSES['F002']}\n\n"
        "인용됨 또는 기각 중 하나를 고르십시오."
    )
    return {
        "id": case_id,
        "suite": "exam",
        "benchmarkId": "outcome.first_instance_prediction.v1",
        "responseFormat": "outcome_prediction",
        "language": "ko",
        "prompt": prompt,
    }


def atom(
    *,
    outcome: str,
    issue_code: str = "REQUIRED_ELEMENT_PRESENT",
    clause_id: str = "F001",
    quote: str | None = None,
) -> dict[str, str]:
    return {
        "issueCode": issue_code,
        "evidenceClauseId": clause_id,
        "exactQuote": quote or CLAUSES[clause_id],
        "direction": "FAVORS_GRANT" if outcome == "인용됨" else "FAVORS_DISMISS",
    }


def generator_row(
    case_id: str,
    outcome: str,
    atoms: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    return {
        "id": case_id,
        "outcome": outcome,
        "rationale": f"{case_id}에 관한 제한된 공개 근거 평가이다.",
        "evidenceAtoms": atoms or [],
    }


def desired_preference(left_role: str, desired_role: str) -> str:
    return "PREFER_LEFT" if left_role == desired_role else "PREFER_RIGHT"


def code_hashes() -> dict[str, str]:
    path = Path(overlap.__file__).resolve()
    return {str(path): overlap.sha256_file(path)}


def rel(bundle: dict[str, Any], path: Path) -> str:
    return str(path.resolve().relative_to(bundle["root"].resolve()))


def valid_zero_tool_trace(stage: str, thread_id: str) -> list[dict[str, Any]]:
    return [
        {"type": "thread.started", "thread_id": thread_id},
        {
            "type": "item.completed",
            "item": {
                "id": f"containment-{stage.lower()}",
                "type": "error",
                "message": overlap.EXPECTED_CODE_MODE_DISABLED_DIAGNOSTIC,
            },
        },
        {"type": "turn.started"},
        {
            "type": "item.completed",
            "item": {
                "id": f"message-{stage.lower()}",
                "type": "agent_message",
                "text": "{}",
            },
        },
        {
            "type": "turn.completed",
            "usage": {
                "input_tokens": 100,
                "cached_input_tokens": 10,
                "cache_write_input_tokens": 0,
                "output_tokens": 20,
                "reasoning_output_tokens": 5,
            },
        },
    ]


def _stage_evidence(
    bundle: dict[str, Any],
    *,
    stage: str,
    artifact_path: Path,
    expected_ids: list[str],
    freeze: dict[str, Any],
    role_mapping_path: Path | None = None,
) -> tuple[dict[str, Any], Path]:
    stage_dir = bundle["root"] / "evidence" / stage.lower()
    prompt_path = bundle["generatorPrompt"] if stage != "BLIND" else bundle["blindPrompt"]
    output_schema_path = (
        bundle["generatorOutputSchema"]
        if stage != "BLIND"
        else bundle["blindActualOutputSchema"]
    )
    raw_path = stage_dir / "raw_first_attempt.txt"
    trace_path = stage_dir / "raw_trace.jsonl"
    validation_path = stage_dir / "validation_report.json"
    attempts_path = stage_dir / "attempt_ledger.json"
    tokens_path = stage_dir / "token_ledger.json"
    receipt_path = stage_dir / "receipt.json"
    stage_dir.mkdir(parents=True, exist_ok=True)
    raw_payload = bundle.get("rawOverrides", {}).get(stage, artifact_path.read_bytes())
    raw_path.write_bytes(raw_payload)
    thread_id = f"thread-{stage.lower()}-unique"
    write_jsonl(
        trace_path,
        valid_zero_tool_trace(stage, thread_id),
    )
    raw_hash = overlap.sha256_file(raw_path)
    artifact_hash = overlap.sha256_file(artifact_path)
    trace_hash = overlap.sha256_file(trace_path)
    invalid_ids = set(bundle["invalidByStage"].get(stage, set()))
    valid_ids = [case_id for case_id in expected_ids if case_id not in invalid_ids]
    invalid_rows = [
        {
            "id": case_id,
            "errors": ["first_attempt_row_invalid"],
            "sourceLine": expected_ids.index(case_id) + 1,
            "rawRecordSha256": overlap.sha256_bytes(raw_payload),
        }
        for case_id in expected_ids
        if case_id in invalid_ids
    ]
    validation = with_self_hash(
        {
            "schemaVersion": 1,
            "protocol": overlap.FIRST_ATTEMPT_VALIDATION_PROTOCOL,
            "status": "complete_first_attempt_audit",
            "stage": stage,
            "expectedRows": len(expected_ids),
            "observedFirstAttemptRows": len(expected_ids),
            "validIds": valid_ids,
            "invalidRows": invalid_rows,
            "rawOutputSha256": raw_hash,
            "normalizedArtifactSha256": artifact_hash,
        },
        "reportSha256",
    )
    write_json(validation_path, validation)
    attempts = with_self_hash(
        {
            "schemaVersion": 1,
            "protocol": overlap.ATTEMPT_LEDGER_PROTOCOL,
            "status": "complete",
            "stage": stage,
            "semanticAttemptCount": 1,
            "transportRetryCount": 0,
            "selectiveRetryCount": 0,
            "attempts": [
                {
                    "ordinal": 1,
                    "kind": "semantic_first_attempt",
                    "rawOutputSha256": raw_hash,
                    "traceSha256": trace_hash,
                }
            ],
        },
        "ledgerSha256",
    )
    write_json(attempts_path, attempts)
    token_entry = {
        "ordinal": 1,
        "inputTokens": 100,
        "cachedInputTokens": 10,
        "outputTokens": 20,
        "reasoningTokens": 5,
        "totalTokens": 120,
    }
    tokens = with_self_hash(
        {
            "schemaVersion": 1,
            "protocol": overlap.TOKEN_LEDGER_PROTOCOL,
            "status": "complete",
            "stage": stage,
            "attempts": [token_entry],
            "totals": {key: value for key, value in token_entry.items() if key != "ordinal"},
        },
        "ledgerSha256",
    )
    write_json(tokens_path, tokens)
    visibility = {
        "publicFilesMounted": False,
        "privateGoldMounted": False,
        "privateLabelsMounted": False,
        "otherGeneratorArtifactsMounted": False,
        "roleMappingMounted": False,
        "candidateProvenanceExposed": False,
        "goldFilesDiscoverable": False,
    }
    audit = {key: 0 for key in overlap.POLICY_AUDIT_KEYS}
    receipt = with_self_hash(
        {
            "schemaVersion": 1,
            "protocol": (
                overlap.BLIND_RECEIPT_PROTOCOL
                if stage == "BLIND"
                else overlap.GENERATOR_RECEIPT_PROTOCOL
            ),
            "status": "completed_first_attempt",
            "stage": stage,
            "stageKind": "blind" if stage == "BLIND" else "generator",
            "campaignId": freeze["campaignId"],
            "sourceFreezeSha256": freeze["freezeSha256"],
            "publicArtifactSha256": freeze["publicSha256"],
            "promptSha256": overlap.sha256_file(prompt_path),
            "outputSchemaSha256": overlap.sha256_file(output_schema_path),
            "outputSchemaCliArg": overlap.OUTPUT_SCHEMA_CLI_ARG,
            "strictConfig": True,
            "configArgv": list(overlap.STRICT_CONFIG_ARGV),
            "configArgvSha256": overlap.STRICT_CONFIG_ARGV_SHA256,
            "ignoreUserConfig": True,
            "ignoreRules": True,
            "ephemeral": True,
            "codexCliVersion": overlap.CODEX_CLI_VERSION,
            "codexFeaturesSnapshotSha256": (
                overlap.CODEX_FEATURES_SNAPSHOT_SHA256
            ),
            "codexFeatureListStdoutSha256": (
                overlap.CODEX_FEATURE_LIST_STDOUT_SHA256
            ),
            "codexFeatureCount": overlap.CODEX_FEATURE_COUNT,
            "executionSettings": overlap.EXECUTION_SETTINGS,
            "rawOutputSha256": raw_hash,
            "normalizedArtifactSha256": artifact_hash,
            "traceSha256": trace_hash,
            "validationReportSha256": validation["reportSha256"],
            "attemptLedgerSha256": attempts["ledgerSha256"],
            "tokenLedgerSha256": tokens["ledgerSha256"],
            "implementationCodeHashes": code_hashes(),
            "semanticModelInvocations": 1,
            "firstAttemptOnly": True,
            "noSelectiveRetry": True,
            "inputDelivery": "stdin_embedded_public_packet",
            "stdinPacketSha256": overlap.sha256_file(prompt_path),
            "stdinPacketPublicSha256": freeze["publicSha256"],
            "configuredModelToolSchemaCount": 0,
            "configuredModelToolSchemas": [],
            "configuredModelToolSchemasSha256": overlap.EMPTY_TOOL_SCHEMAS_SHA256,
            "toolSchemaAdvertisementAttested": False,
            "finalResponseStrictParsed": True,
            "legacyFileAgentUsed": False,
            "threadIds": [thread_id],
            "visibilityBoundary": visibility,
            "policyAudit": audit,
        },
        "receiptSha256",
    )
    write_json(receipt_path, receipt)
    binding = {
        "stageKind": "blind" if stage == "BLIND" else "generator",
        "artifactPath": rel(bundle, artifact_path),
        "artifactSha256": artifact_hash,
        "promptPath": rel(bundle, prompt_path),
        "promptSha256": overlap.sha256_file(prompt_path),
        "outputSchemaPath": rel(bundle, output_schema_path),
        "outputSchemaSha256": overlap.sha256_file(output_schema_path),
        "rawOutputPath": rel(bundle, raw_path),
        "rawOutputSha256": raw_hash,
        "tracePath": rel(bundle, trace_path),
        "traceSha256": trace_hash,
        "receiptPath": rel(bundle, receipt_path),
        "receiptFileSha256": overlap.sha256_file(receipt_path),
        "receiptSha256": receipt["receiptSha256"],
        "validationReportPath": rel(bundle, validation_path),
        "validationReportFileSha256": overlap.sha256_file(validation_path),
        "validationReportSha256": validation["reportSha256"],
        "attemptLedgerPath": rel(bundle, attempts_path),
        "attemptLedgerFileSha256": overlap.sha256_file(attempts_path),
        "attemptLedgerSha256": attempts["ledgerSha256"],
        "tokenLedgerPath": rel(bundle, tokens_path),
        "tokenLedgerFileSha256": overlap.sha256_file(tokens_path),
        "tokenLedgerSha256": tokens["ledgerSha256"],
        "implementationCodeHashes": code_hashes(),
    }
    if stage == "BLIND":
        assert role_mapping_path is not None
        binding["roleMappingPath"] = rel(bundle, role_mapping_path)
        binding["roleMappingSha256"] = overlap.sha256_file(role_mapping_path)
    return binding, receipt_path


def rebind_campaign(bundle: dict[str, Any]) -> None:
    public_rows = load_jsonl(bundle["public"])
    public_hash = overlap.sha256_file(bundle["public"])
    builder = with_self_hash(
        {
            "artifacts": {"public": {"sha256": public_hash, "rows": len(public_rows)}},
            "implementation": {
                "builder": str(Path(overlap.__file__).resolve()),
                "builderSHA256": overlap.sha256_file(Path(overlap.__file__).resolve()),
                "upstreamExtractor": str(Path(overlap.__file__).resolve()),
                "upstreamExtractorSHA256": overlap.sha256_file(
                    Path(overlap.__file__).resolve()
                ),
            },
            "orderedCandidates": [
                {
                    "id": row["id"],
                    "publicRowSHA256": overlap.sha256_bytes(overlap.canonical_json_bytes(row)),
                }
                for row in public_rows
            ],
        },
        "selfHash",
    )
    write_json(bundle["builderManifest"], builder)
    id_receipt = with_self_hash(
        {
            "schemaVersion": 1,
            "protocol": overlap.ID_RECEIPT_PROTOCOL,
            "status": "accepted",
            "publicSha256": public_hash,
            "expectedIdsSha256": overlap.canonical_digest(list(IDS)),
            "idPattern": overlap.PUBLIC_CONSTANTS["opaqueIdPattern"],
            "idDerivation": (
                "outcome-confirm- + first20(SHA256(seedSalt|canonicalId|normalizedCaseRef))"
            ),
            "idInputs": ["seedSalt", "canonicalId", "normalizedCaseRef"],
            "labelFieldsRead": False,
            "implementationCodeHashes": code_hashes(),
        },
        "receiptSha256",
    )
    write_json(bundle["idReceipt"], id_receipt)
    gate_pass = {"pass": True}
    final_gate = {"pass": True, "reasons": []}
    leak = with_self_hash(
        {
            "schemaVersion": overlap.PUBLIC_OUTCOME_AUDIT_PROTOCOL,
            "input": {
                "sha256": public_hash,
                "jsonRowCount": len(IDS),
                "manifest": {"sha256": overlap.sha256_file(bundle["builderManifest"])},
            },
            "implementation": {
                "sha256": overlap.sha256_file(
                    Path(overlap.__file__).resolve().with_name(
                        "audit_public_outcome_reserve.py"
                    )
                )
            },
            "publicContract": {
                "expectedExactKeys": sorted(overlap.PUBLIC_ROW_KEYS),
                "expectedConstants": {
                    key: overlap.PUBLIC_CONSTANTS[key]
                    for key in ("suite", "benchmarkId", "responseFormat", "language")
                },
                "inputReadErrorCount": 0,
                "parsedPromptCount": len(IDS),
                "structuralViolationCount": 0,
                "uniqueIdCount": len(IDS),
            },
            "leakAudit": {
                "affectsFinalGate": False,
                "rowsWithAnyFinding": 244,
            },
            "nearDuplicateAudit": {"qualifyingPairCount": 0},
            "constructionConclusionLeakageAudit": {
                "pass": True,
                "bindingErrorCount": 0,
                "manifestSHA256": overlap.sha256_file(bundle["builderManifest"]),
                "boundPreselectionExclusionCounts": {
                    "claim_points_to_holding": 3,
                    "holding_section_marker": 2,
                    "holding_text_overlap": 7,
                },
            },
            "targetSpecificMetadataAudit": {
                "pass": True,
                "bindingErrorCount": 0,
                "rowsWithTargetMetadata": 0,
            },
            "gates": {
                "publicContract": gate_pass,
                "lexicalNearDuplicate": gate_pass,
                "constructionConclusionLeakage": gate_pass,
                "targetSpecificMetadata": gate_pass,
                "finalPreSolver": final_gate,
            },
            "gate": final_gate,
        },
        "selfHash",
    )
    write_json(bundle["leakReport"], leak)
    freeze = with_self_hash(
        {
            "schemaVersion": 1,
            "protocol": overlap.SOURCE_FREEZE_PROTOCOL,
            "status": overlap.SOURCE_FREEZE_STATUS,
            "campaignId": "structured-overlap-test-v2",
            "publicSha256": public_hash,
            "publicBuilderManifestFileSha256": overlap.sha256_file(bundle["builderManifest"]),
            "publicBuilderManifestSelfHash": builder["selfHash"],
            "labelIndependentIdReceiptFileSha256": overlap.sha256_file(bundle["idReceipt"]),
            "labelIndependentIdReceiptSha256": id_receipt["receiptSha256"],
            "conclusionLeakReportFileSha256": overlap.sha256_file(bundle["leakReport"]),
            "conclusionLeakReportSha256": leak["selfHash"],
            "expectedRows": len(IDS),
            "expectedIdsSha256": overlap.canonical_digest(list(IDS)),
            "publicConstants": overlap.PUBLIC_CONSTANTS,
            "generatorPromptSha256": overlap.sha256_file(bundle["generatorPrompt"]),
            "blindPromptTemplateSha256": overlap.sha256_file(
                bundle["blindPromptTemplate"]
            ),
            "generatorOutputSchemaSha256": overlap.sha256_file(
                bundle["generatorOutputSchema"]
            ),
            "blindOutputSchemaTemplateSha256": overlap.sha256_file(
                bundle["blindOutputSchemaTemplate"]
            ),
            "outputSchemaCliArg": overlap.OUTPUT_SCHEMA_CLI_ARG,
            "blindPackageContractSha256": overlap.canonical_digest(
                overlap.BLIND_PACKAGE_CONTRACT
            ),
            "blindPackageDerivationCodeHashes": code_hashes(),
            "generatorExecutionSettings": overlap.EXECUTION_SETTINGS,
            "blindExecutionSettings": overlap.EXECUTION_SETTINGS,
            "carrierSelectionSeed": CARRIER_SEED,
            "roleRotationSeed": ROTATION_SEED,
            "attemptPolicy": overlap.ATTEMPT_POLICY,
            "requiredUpstreamReceiptHooks": overlap.REQUIRED_UPSTREAM_RECEIPT_HOOKS,
            "comparatorFairnessAuditRequired": True,
        },
        "freezeSha256",
    )
    write_json(bundle["freeze"], freeze)

    generator_maps = {
        name: {row["id"]: row for row in load_jsonl(bundle[name])}
        for name in overlap.GENERATOR_NAMES
    }
    valid_generator = {
        name: set(IDS) - set(bundle["invalidByStage"].get(name, set()))
        for name in overlap.GENERATOR_NAMES
    }
    conflict_ids = [
        case_id
        for case_id in IDS
        if all(case_id in valid_generator[name] for name in overlap.GENERATOR_NAMES)
        and generator_maps["G2"][case_id]["outcome"]
        == generator_maps["G3"][case_id]["outcome"]
        != generator_maps["G1"][case_id]["outcome"]
    ]
    conflict_package = overlap._blind_conflict_package(
        conflict_ids=conflict_ids,
        generators=generator_maps,
        carrier_seed=CARRIER_SEED,
        rotation_seed=ROTATION_SEED,
    )
    bundle["blindPrompt"].write_bytes(
        overlap.render_blind_prompt_packet(
            template_bytes=bundle["blindPromptTemplate"].read_bytes(),
            public_rows_by_id={row["id"]: row for row in public_rows},
            conflict_package=conflict_package,
        )
    )
    write_json(
        bundle["blindActualOutputSchema"],
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "x-rowCount": len(conflict_ids),
        },
    )
    stages: dict[str, Any] = {}
    for name in overlap.GENERATOR_NAMES:
        stages[name], _ = _stage_evidence(
            bundle,
            stage=name,
            artifact_path=bundle[name],
            expected_ids=list(IDS),
            freeze=freeze,
        )
    stages["BLIND"], blind_receipt_path = _stage_evidence(
        bundle,
        stage="BLIND",
        artifact_path=bundle["certificates"],
        expected_ids=conflict_ids,
        freeze=freeze,
        role_mapping_path=bundle["mapping"],
    )
    bundle["receipt"] = blind_receipt_path
    blind_package_freeze = with_self_hash(
        {
            "schemaVersion": 1,
            "protocol": overlap.BLIND_PACKAGE_FREEZE_PROTOCOL,
            "status": overlap.BLIND_PACKAGE_FREEZE_STATUS,
            "campaignId": freeze["campaignId"],
            "sourceFreezeFileSha256": overlap.sha256_file(bundle["freeze"]),
            "sourceFreezeSha256": freeze["freezeSha256"],
            "blindPromptTemplateSha256": freeze["blindPromptTemplateSha256"],
            "blindOutputSchemaTemplateSha256": freeze[
                "blindOutputSchemaTemplateSha256"
            ],
            "blindPackageContractSha256": freeze["blindPackageContractSha256"],
            "blindPackageDerivationCodeHashes": freeze[
                "blindPackageDerivationCodeHashes"
            ],
            "carrierSelectionSeed": CARRIER_SEED,
            "roleRotationSeed": ROTATION_SEED,
            "generatorStageReceipts": {
                name: {
                    key: stages[name][key]
                    for key in overlap.BLIND_PACKAGE_GENERATOR_RECEIPT_KEYS
                }
                for name in overlap.GENERATOR_NAMES
            },
            "expectedConflictRows": len(conflict_ids),
            "expectedConflictIdsSha256": overlap.canonical_digest(conflict_ids),
            "orderedConflictPackageSha256": overlap.canonical_digest(
                conflict_package
            ),
            "instantiatedBlindPromptPacketSha256": overlap.sha256_file(
                bundle["blindPrompt"]
            ),
            "instantiatedBlindOutputSchemaSha256": overlap.sha256_file(
                bundle["blindActualOutputSchema"]
            ),
            "blindRoleMappingSha256": overlap.sha256_file(bundle["mapping"]),
        },
        "freezeSha256",
    )
    write_json(bundle["blindPackageFreeze"], blind_package_freeze)
    source_artifacts = {
        "publicPath": rel(bundle, bundle["public"]),
        "publicSha256": public_hash,
        "builderManifestPath": rel(bundle, bundle["builderManifest"]),
        "builderManifestFileSha256": overlap.sha256_file(bundle["builderManifest"]),
        "builderManifestSelfHash": builder["selfHash"],
        "labelIndependentIdReceiptPath": rel(bundle, bundle["idReceipt"]),
        "labelIndependentIdReceiptFileSha256": overlap.sha256_file(bundle["idReceipt"]),
        "labelIndependentIdReceiptSha256": id_receipt["receiptSha256"],
        "conclusionLeakReportPath": rel(bundle, bundle["leakReport"]),
        "conclusionLeakReportFileSha256": overlap.sha256_file(bundle["leakReport"]),
        "conclusionLeakReportSha256": leak["selfHash"],
        "generatorOutputSchemaPath": rel(bundle, bundle["generatorOutputSchema"]),
        "generatorOutputSchemaSha256": overlap.sha256_file(
            bundle["generatorOutputSchema"]
        ),
        "blindPromptTemplatePath": rel(bundle, bundle["blindPromptTemplate"]),
        "blindPromptTemplateSha256": overlap.sha256_file(
            bundle["blindPromptTemplate"]
        ),
        "blindOutputSchemaTemplatePath": rel(
            bundle, bundle["blindOutputSchemaTemplate"]
        ),
        "blindOutputSchemaTemplateSha256": overlap.sha256_file(
            bundle["blindOutputSchemaTemplate"]
        ),
    }
    campaign = with_self_hash(
        {
            "schemaVersion": 1,
            "protocol": overlap.CAMPAIGN_MANIFEST_PROTOCOL,
            "status": overlap.CAMPAIGN_MANIFEST_STATUS,
            "campaignId": freeze["campaignId"],
            "sourceFreezeFileSha256": overlap.sha256_file(bundle["freeze"]),
            "sourceFreezeSha256": freeze["freezeSha256"],
            "blindPackageFreezeFileSha256": overlap.sha256_file(
                bundle["blindPackageFreeze"]
            ),
            "blindPackageFreezeSha256": blind_package_freeze["freezeSha256"],
            "sourceArtifacts": source_artifacts,
            "stages": stages,
            "comparatorFairnessAudit": {
                "required": True,
                "status": "PENDING_EXTERNAL_AUDIT",
                "reportSha256": None,
            },
        },
        "manifestSha256",
    )
    write_json(bundle["campaignManifest"], campaign)
    bundle["expectedFreezeFileSHA256"] = overlap.sha256_file(bundle["freeze"])
    bundle["expectedReceiptFileSHA256"] = overlap.sha256_file(bundle["receipt"])
    bundle["expectedBlindPackageFreezeFileSHA256"] = overlap.sha256_file(
        bundle["blindPackageFreeze"]
    )
    bundle["expectedCampaignManifestFileSHA256"] = overlap.sha256_file(
        bundle["campaignManifest"]
    )


def _resign_campaign(bundle: dict[str, Any], campaign: dict[str, Any]) -> None:
    campaign.pop("manifestSha256", None)
    campaign["manifestSha256"] = overlap.canonical_digest(campaign)
    write_json(bundle["campaignManifest"], campaign)
    bundle["expectedCampaignManifestFileSHA256"] = overlap.sha256_file(
        bundle["campaignManifest"]
    )


def mutate_stage_receipt(
    bundle: dict[str, Any], stage: str, mutate: Callable[[dict[str, Any]], None]
) -> None:
    campaign = json.loads(bundle["campaignManifest"].read_text(encoding="utf-8"))
    binding = campaign["stages"][stage]
    receipt_path = bundle["root"] / binding["receiptPath"]
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    mutate(receipt)
    receipt.pop("receiptSha256", None)
    receipt["receiptSha256"] = overlap.canonical_digest(receipt)
    write_json(receipt_path, receipt)
    binding["receiptFileSha256"] = overlap.sha256_file(receipt_path)
    binding["receiptSha256"] = receipt["receiptSha256"]
    _resign_campaign(bundle, campaign)
    if stage == "BLIND":
        bundle["expectedReceiptFileSHA256"] = overlap.sha256_file(receipt_path)


def mutate_attempt_ledger(
    bundle: dict[str, Any], stage: str, mutate: Callable[[dict[str, Any]], None]
) -> None:
    campaign = json.loads(bundle["campaignManifest"].read_text(encoding="utf-8"))
    binding = campaign["stages"][stage]
    ledger_path = bundle["root"] / binding["attemptLedgerPath"]
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    mutate(ledger)
    ledger.pop("ledgerSha256", None)
    ledger["ledgerSha256"] = overlap.canonical_digest(ledger)
    write_json(ledger_path, ledger)
    binding["attemptLedgerFileSha256"] = overlap.sha256_file(ledger_path)
    binding["attemptLedgerSha256"] = ledger["ledgerSha256"]
    _resign_campaign(bundle, campaign)


def inject_trace_tool_event(
    bundle: dict[str, Any],
    stage: str,
    *,
    event_type: str = "item.started",
    item_type: str | None = "command_execution",
) -> None:
    campaign = json.loads(bundle["campaignManifest"].read_text(encoding="utf-8"))
    binding = campaign["stages"][stage]
    trace_path = bundle["root"] / binding["tracePath"]
    injected: dict[str, Any] = {"type": event_type}
    if item_type is not None:
        injected["item"] = {"type": item_type, "command": "pwd"}
    write_jsonl(
        trace_path,
        [
            {
                "type": "thread.started",
                "thread_id": f"thread-{stage.lower()}-unique",
            },
            injected,
        ],
    )
    trace_hash = overlap.sha256_file(trace_path)
    binding["traceSha256"] = trace_hash
    attempt_path = bundle["root"] / binding["attemptLedgerPath"]
    attempts = json.loads(attempt_path.read_text(encoding="utf-8"))
    attempts["attempts"][0]["traceSha256"] = trace_hash
    attempts.pop("ledgerSha256", None)
    attempts["ledgerSha256"] = overlap.canonical_digest(attempts)
    write_json(attempt_path, attempts)
    binding["attemptLedgerFileSha256"] = overlap.sha256_file(attempt_path)
    binding["attemptLedgerSha256"] = attempts["ledgerSha256"]
    receipt_path = bundle["root"] / binding["receiptPath"]
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["traceSha256"] = trace_hash
    receipt["attemptLedgerSha256"] = attempts["ledgerSha256"]
    receipt.pop("receiptSha256", None)
    receipt["receiptSha256"] = overlap.canonical_digest(receipt)
    write_json(receipt_path, receipt)
    binding["receiptFileSha256"] = overlap.sha256_file(receipt_path)
    binding["receiptSha256"] = receipt["receiptSha256"]
    _resign_campaign(bundle, campaign)


def rebind_blind_package_generator_receipts(bundle: dict[str, Any]) -> None:
    campaign = json.loads(bundle["campaignManifest"].read_text(encoding="utf-8"))
    freeze = json.loads(bundle["blindPackageFreeze"].read_text(encoding="utf-8"))
    freeze["generatorStageReceipts"] = {
        name: {
            key: campaign["stages"][name][key]
            for key in overlap.BLIND_PACKAGE_GENERATOR_RECEIPT_KEYS
        }
        for name in overlap.GENERATOR_NAMES
    }
    freeze.pop("freezeSha256", None)
    freeze["freezeSha256"] = overlap.canonical_digest(freeze)
    write_json(bundle["blindPackageFreeze"], freeze)
    campaign["blindPackageFreezeFileSha256"] = overlap.sha256_file(
        bundle["blindPackageFreeze"]
    )
    campaign["blindPackageFreezeSha256"] = freeze["freezeSha256"]
    _resign_campaign(bundle, campaign)
    bundle["expectedBlindPackageFreezeFileSHA256"] = overlap.sha256_file(
        bundle["blindPackageFreeze"]
    )


def replace_stage_thread_id(bundle: dict[str, Any], stage: str, thread_id: str) -> None:
    campaign = json.loads(bundle["campaignManifest"].read_text(encoding="utf-8"))
    binding = campaign["stages"][stage]
    trace_path = bundle["root"] / binding["tracePath"]
    write_jsonl(
        trace_path,
        valid_zero_tool_trace(stage, thread_id),
    )
    trace_hash = overlap.sha256_file(trace_path)
    binding["traceSha256"] = trace_hash

    attempt_path = bundle["root"] / binding["attemptLedgerPath"]
    attempts = json.loads(attempt_path.read_text(encoding="utf-8"))
    attempts["attempts"][0]["traceSha256"] = trace_hash
    attempts.pop("ledgerSha256", None)
    attempts["ledgerSha256"] = overlap.canonical_digest(attempts)
    write_json(attempt_path, attempts)
    binding["attemptLedgerFileSha256"] = overlap.sha256_file(attempt_path)
    binding["attemptLedgerSha256"] = attempts["ledgerSha256"]

    receipt_path = bundle["root"] / binding["receiptPath"]
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["traceSha256"] = trace_hash
    receipt["attemptLedgerSha256"] = attempts["ledgerSha256"]
    receipt["threadIds"] = [thread_id]
    receipt.pop("receiptSha256", None)
    receipt["receiptSha256"] = overlap.canonical_digest(receipt)
    write_json(receipt_path, receipt)
    binding["receiptFileSha256"] = overlap.sha256_file(receipt_path)
    binding["receiptSha256"] = receipt["receiptSha256"]
    _resign_campaign(bundle, campaign)
    rebind_blind_package_generator_receipts(bundle)


def build_bundle(tmp_path: Path) -> dict[str, Any]:
    public_path = tmp_path / "input" / "reserve.public.jsonl"
    g1_path = tmp_path / "input" / "g1.jsonl"
    g2_path = tmp_path / "input" / "g2.jsonl"
    g3_path = tmp_path / "input" / "g3.jsonl"
    cert_path = tmp_path / "control" / "blind_certificates.jsonl"
    mapping_path = tmp_path / "control" / "blind_role_mapping.jsonl"
    freeze_path = tmp_path / "control" / "source_freeze.json"
    receipt_path = tmp_path / "control" / "blind_receipt.json"

    public_rows = [public_row(case_id) for case_id in IDS]
    write_jsonl(public_path, public_rows)

    g1 = [
        generator_row(IDS[0], "기각"),
        generator_row(IDS[1], "기각"),
        generator_row(IDS[2], "기각"),
        generator_row(IDS[3], "기각"),
        generator_row(IDS[4], "인용됨", [atom(outcome="인용됨")]),
        generator_row(IDS[5], "ABSTAIN"),
    ]
    g2 = [
        generator_row(
            IDS[0],
            "인용됨",
            [
                atom(
                    outcome="인용됨",
                    issue_code="RULE_OR_EXCEPTION_APPLIES",
                    clause_id="C001",
                ),
                atom(outcome="인용됨"),
            ],
        ),
        generator_row(IDS[1], "인용됨", [atom(outcome="인용됨")]),
        generator_row(IDS[2], "기각"),
        generator_row(IDS[3], "인용됨", [atom(outcome="인용됨")]),
        generator_row(IDS[4], "ABSTAIN"),
        generator_row(
            IDS[5],
            "기각",
            [
                atom(
                    outcome="기각",
                    issue_code="BURDEN_OR_STANDARD_NOT_MET",
                    clause_id="F002",
                )
            ],
        ),
    ]
    g3 = [
        generator_row(
            IDS[0],
            "인용됨",
            [
                atom(
                    outcome="인용됨",
                    issue_code="RULE_OR_EXCEPTION_APPLIES",
                    clause_id="C001",
                ),
                atom(outcome="인용됨"),
            ],
        ),
        generator_row(
            IDS[1],
            "인용됨",
            [
                atom(
                    outcome="인용됨",
                    issue_code="RULE_OR_EXCEPTION_APPLIES",
                )
            ],
        ),
        generator_row(IDS[2], "기각"),
        generator_row(
            IDS[3],
            "인용됨",
            [atom(outcome="인용됨")],
        ),
        generator_row(IDS[4], "ABSTAIN"),
        generator_row(
            IDS[5],
            "기각",
            [
                atom(
                    outcome="기각",
                    issue_code="BURDEN_OR_STANDARD_NOT_MET",
                    clause_id="F002",
                )
            ],
        ),
    ]
    write_jsonl(g1_path, g1)
    write_jsonl(g2_path, g2)
    write_jsonl(g3_path, g3)

    conflict_ids = [IDS[0], IDS[1], IDS[3], IDS[4], IDS[5]]
    desired = {
        IDS[0]: "INCUMBENT",
        IDS[1]: "INCUMBENT",
        IDS[3]: "TIE",
        IDS[4]: "UNRESOLVED",
        IDS[5]: "PROPOSED",
    }
    outcomes = {
        name: {row["id"]: row["outcome"] for row in rows}
        for name, rows in {"G1": g1, "G2": g2, "G3": g3}.items()
    }
    certificates: list[dict[str, Any]] = []
    mappings: list[dict[str, Any]] = []
    for case_id in conflict_ids:
        left_role, right_role = overlap.expected_roles(ROTATION_SEED, case_id)
        carrier = overlap.proposal_carrier(CARRIER_SEED, case_id)
        incumbent = outcomes["G1"][case_id]
        proposed = outcomes[carrier][case_id]
        target = desired[case_id]
        preference = (
            target
            if target in {"TIE", "UNRESOLVED"}
            else desired_preference(left_role, target)
        )
        certificates.append(
            {
                "id": case_id,
                "leftOutcome": incumbent if left_role == "INCUMBENT" else proposed,
                "rightOutcome": incumbent if right_role == "INCUMBENT" else proposed,
                "preference": preference,
            }
        )
        mappings.append(
            {"id": case_id, "leftRole": left_role, "rightRole": right_role}
        )
    write_jsonl(cert_path, certificates)
    write_jsonl(mapping_path, mappings)

    bundle = {
        "root": tmp_path,
        "public": public_path,
        "freeze": freeze_path,
        "G1": g1_path,
        "G2": g2_path,
        "G3": g3_path,
        "certificates": cert_path,
        "mapping": mapping_path,
        "receipt": receipt_path,
        "builderManifest": tmp_path / "control" / "builder_manifest.json",
        "idReceipt": tmp_path / "control" / "id_receipt.json",
        "leakReport": tmp_path / "control" / "conclusion_leak_report.json",
        "generatorPrompt": tmp_path / "input" / "generator_packet.txt",
        "blindPrompt": tmp_path / "input" / "blind_packet.txt",
        "blindPromptTemplate": tmp_path / "input" / "blind_packet.template.txt",
        "generatorOutputSchema": tmp_path / "input" / "generator.output-schema.json",
        "blindOutputSchemaTemplate": (
            tmp_path / "input" / "blind.output-schema.template.json"
        ),
        "blindActualOutputSchema": (
            tmp_path / "control" / "blind.output-schema.actual.json"
        ),
        "blindPackageFreeze": tmp_path / "control" / "blind_package_freeze.json",
        "campaignManifest": tmp_path / "campaign_manifest.json",
        "invalidByStage": {name: set() for name in (*overlap.GENERATOR_NAMES, "BLIND")},
        "rawOverrides": {},
        "output": tmp_path / "output",
    }
    bundle["generatorPrompt"].write_text("PUBLIC PACKET: structured generator\n", encoding="utf-8")
    bundle["blindPromptTemplate"].write_text(
        "PUBLIC PACKET TEMPLATE: role-blind\n{{BLIND_ITEMS_JSONL}}",
        encoding="utf-8",
    )
    build_generators = {
        name: {row["id"]: row for row in rows}
        for name, rows in {"G1": g1, "G2": g2, "G3": g3}.items()
    }
    build_conflict_package = overlap._blind_conflict_package(
        conflict_ids=conflict_ids,
        generators=build_generators,
        carrier_seed=CARRIER_SEED,
        rotation_seed=ROTATION_SEED,
    )
    bundle["blindPrompt"].write_bytes(
        overlap.render_blind_prompt_packet(
            template_bytes=bundle["blindPromptTemplate"].read_bytes(),
            public_rows_by_id={row["id"]: row for row in public_rows},
            conflict_package=build_conflict_package,
        )
    )
    write_json(
        bundle["generatorOutputSchema"],
        {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object"},
    )
    write_json(
        bundle["blindOutputSchemaTemplate"],
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "x-rowCount": "{conflict_count}",
        },
    )
    write_json(
        bundle["blindActualOutputSchema"],
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "x-rowCount": len(conflict_ids),
        },
    )
    rebind_campaign(bundle)
    return bundle


def invoke(bundle: dict[str, Any]) -> dict[str, Any]:
    return overlap.combine_structured_legal_overlap(
        public_path=bundle["public"],
        source_freeze_path=bundle["freeze"],
        expected_source_freeze_file_sha256=bundle["expectedFreezeFileSHA256"],
        campaign_manifest_path=bundle["campaignManifest"],
        expected_campaign_manifest_file_sha256=bundle[
            "expectedCampaignManifestFileSHA256"
        ],
        blind_package_freeze_path=bundle["blindPackageFreeze"],
        expected_blind_package_freeze_file_sha256=bundle[
            "expectedBlindPackageFreezeFileSHA256"
        ],
        g1_path=bundle["G1"],
        g2_path=bundle["G2"],
        g3_path=bundle["G3"],
        blind_certificates_path=bundle["certificates"],
        blind_role_mapping_path=bundle["mapping"],
        blind_receipt_path=bundle["receipt"],
        expected_blind_receipt_file_sha256=bundle["expectedReceiptFileSHA256"],
        output_dir=bundle["output"],
    )


def policy_map(bundle: dict[str, Any], name: str) -> dict[str, str]:
    rows = load_jsonl(
        bundle["output"] / "policies" / name / "deployment_fallback_answers.jsonl"
    )
    assert [row["id"] for row in rows] == list(IDS)
    assert all(set(row) == {"id", "outcome"} for row in rows)
    return {row["id"]: row["outcome"] for row in rows}


def scoring_map(bundle: dict[str, Any], name: str) -> dict[str, str | None]:
    rows = load_jsonl(
        bundle["output"] / "policies" / name / "full_denominator_predictions.jsonl"
    )
    return {row["id"]: row["outcome"] for row in rows}


def test_all_trigger_veto_tie_and_abstain_branches_publish_exact_labels(tmp_path: Path) -> None:
    bundle = build_bundle(tmp_path)
    receipt = invoke(bundle)

    assert receipt["status"] == "accepted"
    assert receipt["goldAccess"] is False
    assert receipt["provenanceBlind"] is True
    assert receipt["authNotExposedViaModelToolSurface"] is True
    assert receipt["campaignBindings"]["zeroToolContract"] is True
    assert receipt["campaignBindings"]["authNotExposedViaModelToolSurface"] is True
    assert receipt["toolSurfaceEvidenceScope"][
        "providerToolSchemaAdvertisementAttested"
    ] is False
    assert receipt["synthesis"] is False
    assert receipt["mechanism"]["answerOnlyConflicts"]["ids"] == [
        IDS[0], IDS[1], IDS[3], IDS[4], IDS[5]
    ]
    assert receipt["mechanism"]["structuredOverlapTriggers"]["ids"] == [
        IDS[0], IDS[3], IDS[5]
    ]
    assert receipt["mechanism"]["blindExplicitIncumbentVetoes"]["ids"] == [
        IDS[0], IDS[1]
    ]
    assert receipt["mechanism"]["blindTieOrUnresolved"]["ids"] == [IDS[3], IDS[4]]

    base = policy_map(bundle, "base")
    raw = policy_map(bundle, "answer_only")
    answer_veto = policy_map(bundle, "answer_only_blind_veto")
    structured = policy_map(bundle, "structured_overlap")
    primary = policy_map(bundle, "structured_overlap_blind_veto")

    assert base == {
        IDS[0]: "기각", IDS[1]: "기각", IDS[2]: "기각",
        IDS[3]: "기각", IDS[4]: "인용됨", IDS[5]: "ABSTAIN",
    }
    assert raw == {
        IDS[0]: "인용됨", IDS[1]: "인용됨", IDS[2]: "기각",
        IDS[3]: "인용됨", IDS[4]: "ABSTAIN", IDS[5]: "기각",
    }
    assert answer_veto[IDS[0]] == "기각"
    assert answer_veto[IDS[1]] == "기각"  # Answer-only conflict can also be vetoed.
    assert answer_veto[IDS[3]] == "인용됨"  # TIE does not veto.
    assert answer_veto[IDS[4]] == "ABSTAIN"  # UNRESOLVED does not veto.
    assert structured[IDS[0]] == "인용됨"
    assert structured[IDS[1]] == "기각"  # Answer agreement alone is not overlap.
    assert structured[IDS[4]] == "인용됨"  # ABSTAIN has no supporting atom.
    assert structured[IDS[5]] == "기각"  # A canonical ABSTAIN incumbent can be repaired.
    assert primary[IDS[0]] == "기각"
    assert primary[IDS[3]] == "인용됨"
    assert primary[IDS[5]] == "기각"

    stored = json.loads(
        (bundle["output"] / "mechanism_receipt.json").read_text(encoding="utf-8")
    )
    assert stored == receipt
    assert stored["receiptSha256"] == overlap.canonical_digest(
        {key: value for key, value in stored.items() if key != "receiptSha256"}
    )
    decisions = load_jsonl(bundle["output"] / "mechanism_decisions.jsonl")
    assert [row["id"] for row in decisions] == list(IDS)
    assert decisions[0]["overlapAtomKey"] == [
        "REQUIRED_ELEMENT_PRESENT", "F001", CLAUSES["F001"],
        "FAVORS_GRANT", "인용됨"
    ]


def test_hash_rotation_covers_both_roles_and_both_proposal_carriers() -> None:
    case_ids = [f"rotation-case-{index}" for index in range(200)]
    roles = {overlap.expected_roles(ROTATION_SEED, case_id) for case_id in case_ids}
    carriers = {overlap.proposal_carrier(CARRIER_SEED, case_id) for case_id in case_ids}
    assert roles == {("INCUMBENT", "PROPOSED"), ("PROPOSED", "INCUMBENT")}
    assert carriers == {"G2", "G3"}
    assert all(
        overlap.expected_roles(ROTATION_SEED, case_id)
        == overlap.expected_roles(ROTATION_SEED, case_id)
        for case_id in case_ids
    )


def test_empty_blind_inventory_is_valid_when_there_are_no_answer_conflicts(
    tmp_path: Path,
) -> None:
    bundle = build_bundle(tmp_path)
    g1_rows = load_jsonl(bundle["G1"])
    write_jsonl(bundle["G2"], g1_rows)
    write_jsonl(bundle["G3"], g1_rows)
    write_jsonl(bundle["certificates"], [])
    write_jsonl(bundle["mapping"], [])
    rebind_campaign(bundle)

    receipt = invoke(bundle)
    assert receipt["mechanism"]["answerOnlyConflicts"]["count"] == 0
    expected = policy_map(bundle, "base")
    assert all(policy_map(bundle, policy) == expected for policy in overlap.POLICIES)


def _rewrite_generator_and_rebind(
    bundle: dict[str, Any],
    generator: str,
    mutate: Callable[[list[dict[str, Any]]], None],
) -> None:
    rows = load_jsonl(bundle[generator])
    mutate(rows)
    write_jsonl(bundle[generator], rows)
    rebind_campaign(bundle)


@pytest.mark.parametrize(
    "mutate,error",
    [
        (
            lambda rows: rows[0]["evidenceAtoms"][0].update(exactQuote="짧다"),
            "quote length",
        ),
        (
            lambda rows: rows[0]["evidenceAtoms"][0].update(exactQuote="가" * 241),
            "quote length",
        ),
        (
            lambda rows: rows[0]["evidenceAtoms"][0].update(
                exactQuote="공개 근거절 어디에도 존재하지 않는 충분히 긴 인용문"
            ),
            "must equal the entire",
        ),
        (
            lambda rows: rows[0]["evidenceAtoms"][1].update(
                exactQuote=CLAUSES["F001"][2:]
            ),
            "must equal the entire",
        ),
        (
            lambda rows: rows[0]["evidenceAtoms"][0].update(evidenceClauseId="F999"),
            "clause ID",
        ),
        (
            lambda rows: rows[0]["evidenceAtoms"][0].update(direction="FAVORS_DISMISS"),
            "direction/outcome incoherence",
        ),
        (
            lambda rows: rows[0].update(
                evidenceAtoms=[rows[0]["evidenceAtoms"][0], dict(rows[0]["evidenceAtoms"][0])]
            ),
            "duplicate atom key",
        ),
        (
            lambda rows: rows[0].update(
                evidenceAtoms=rows[0]["evidenceAtoms"]
                + [
                    atom(
                        outcome="인용됨",
                        issue_code="BURDEN_OR_STANDARD_MET",
                        clause_id="F002",
                    )
                ]
            ),
            "evidence atom count",
        ),
        (
            lambda rows: rows[0]["evidenceAtoms"][0].update(issueCode="OPEN_ENDED_TOPIC"),
            "issue code",
        ),
        (
            lambda rows: rows[0]["evidenceAtoms"][0].update(confidence="HIGH"),
            "atom 1 schema",
        ),
        (
            lambda rows: rows[4].update(evidenceAtoms=[atom(outcome="인용됨")]),
            "direction/outcome incoherence",
        ),
    ],
)
def test_invalid_quotes_clauses_atoms_and_directions_reject_campaign(
    tmp_path: Path,
    mutate: Callable[[list[dict[str, Any]]], None],
    error: str,
) -> None:
    bundle = build_bundle(tmp_path)
    _rewrite_generator_and_rebind(bundle, "G2", mutate)
    with pytest.raises(overlap.CombinationValidationError, match=error):
        invoke(bundle)
    assert not bundle["output"].exists()


def test_generator_order_and_exact_schema_are_fail_closed(tmp_path: Path) -> None:
    bundle = build_bundle(tmp_path)

    def mutate(rows: list[dict[str, Any]]) -> None:
        rows[0], rows[1] = rows[1], rows[0]

    _rewrite_generator_and_rebind(bundle, "G3", mutate)
    with pytest.raises(overlap.CombinationValidationError, match="IDs/order mismatch"):
        invoke(bundle)

    second = build_bundle(tmp_path / "second")

    def add_extra(rows: list[dict[str, Any]]) -> None:
        rows[0]["confidence"] = 0.9

    _rewrite_generator_and_rebind(second, "G2", add_extra)
    with pytest.raises(overlap.CombinationValidationError, match="row 1 schema"):
        invoke(second)


def test_artifact_tamper_rejects_even_when_json_remains_valid(tmp_path: Path) -> None:
    bundle = build_bundle(tmp_path)
    rows = load_jsonl(bundle["G2"])
    rows[0]["rationale"] += " 변조"
    write_jsonl(bundle["G2"], rows)

    with pytest.raises(
        overlap.CombinationValidationError,
        match="G2 artifact hash",
    ):
        invoke(bundle)
    assert not bundle["output"].exists()


def test_missing_certificate_and_wrong_role_rotation_reject(tmp_path: Path) -> None:
    bundle = build_bundle(tmp_path)
    certificates = load_jsonl(bundle["certificates"])
    write_jsonl(bundle["certificates"], certificates[:-1])
    rebind_campaign(bundle)
    with pytest.raises(overlap.CombinationValidationError, match="certificate row count"):
        invoke(bundle)

    second = build_bundle(tmp_path / "second")
    mappings = load_jsonl(second["mapping"])
    mappings[0]["leftRole"], mappings[0]["rightRole"] = (
        mappings[0]["rightRole"],
        mappings[0]["leftRole"],
    )
    write_jsonl(second["mapping"], mappings)
    rebind_campaign(second)
    with pytest.raises(overlap.CombinationValidationError, match="role rotation mismatch"):
        invoke(second)

    third = build_bundle(tmp_path / "third")
    certificates = load_jsonl(third["certificates"])
    certificates[0]["leftOutcome"] = (
        "기각" if certificates[0]["leftOutcome"] != "기각" else "인용됨"
    )
    write_jsonl(third["certificates"], certificates)
    rebind_campaign(third)
    with pytest.raises(overlap.CombinationValidationError, match="compared outcomes mismatch"):
        invoke(third)


def test_source_and_receipt_external_hashes_are_required(tmp_path: Path) -> None:
    bundle = build_bundle(tmp_path)
    bundle["expectedFreezeFileSHA256"] = "0" * 64
    with pytest.raises(overlap.CombinationValidationError, match="source freeze file SHA-256"):
        invoke(bundle)

    second = build_bundle(tmp_path / "second")
    second["expectedReceiptFileSHA256"] = "f" * 64
    with pytest.raises(overlap.CombinationValidationError, match="BLIND explicit receipt"):
        invoke(second)

    third = build_bundle(tmp_path / "third")
    third["expectedCampaignManifestFileSHA256"] = "a" * 64
    with pytest.raises(overlap.CombinationValidationError, match="campaign manifest file SHA-256"):
        invoke(third)


def test_malformed_public_clause_rejects_before_publication(tmp_path: Path) -> None:
    bundle = build_bundle(tmp_path)
    rows = load_jsonl(bundle["public"])
    rows[0]["prompt"] = rows[0]["prompt"].replace("[F001] ", "문장 안 [F001] ")
    write_jsonl(bundle["public"], rows)
    with pytest.raises(overlap.CombinationValidationError, match="malformed clause line"):
        invoke(bundle)
    assert not bundle["output"].exists()


def test_first_attempt_invalid_generator_row_is_scored_wrong_but_has_separate_fallback(
    tmp_path: Path,
) -> None:
    bundle = build_bundle(tmp_path)
    rows = load_jsonl(bundle["G2"])
    rows[1] = {
        "id": IDS[1],
        "outcome": "ABSTAIN",
        "rationale": overlap.INVALID_PLACEHOLDER_RATIONALE,
        "evidenceAtoms": [],
    }
    write_jsonl(bundle["G2"], rows)
    bundle["invalidByStage"]["G2"] = {IDS[1]}
    malformed_raw = b'{"id":"broken-first-attempt","outcome":[]}\n'
    bundle["rawOverrides"]["G2"] = malformed_raw
    write_jsonl(
        bundle["certificates"],
        [row for row in load_jsonl(bundle["certificates"]) if row["id"] != IDS[1]],
    )
    write_jsonl(
        bundle["mapping"],
        [row for row in load_jsonl(bundle["mapping"]) if row["id"] != IDS[1]],
    )
    rebind_campaign(bundle)

    receipt = invoke(bundle)
    assert scoring_map(bundle, "base")[IDS[1]] == "기각"
    for policy in (
        "answer_only",
        "answer_only_blind_veto",
        "structured_overlap",
        "structured_overlap_blind_veto",
    ):
        assert scoring_map(bundle, policy)[IDS[1]] is None
        assert policy_map(bundle, policy)[IDS[1]] == "기각"
    assert receipt["stageEvidence"]["G2"]["firstAttemptInvalidIds"]["ids"] == [IDS[1]]
    assert receipt["policies"]["answer_only"]["firstAttemptInvalidRowsScoredWrong"][
        "ids"
    ] == [IDS[1]]
    assert (bundle["root"] / "evidence/g2/raw_first_attempt.txt").read_bytes() == malformed_raw
    assert receipt["selectiveRetry"] is False


def test_invalid_blind_first_attempt_is_not_treated_as_valid_unresolved(
    tmp_path: Path,
) -> None:
    bundle = build_bundle(tmp_path)
    certificates = load_jsonl(bundle["certificates"])
    next(row for row in certificates if row["id"] == IDS[3])["preference"] = "UNRESOLVED"
    write_jsonl(bundle["certificates"], certificates)
    bundle["invalidByStage"]["BLIND"] = {IDS[3]}
    bundle["rawOverrides"]["BLIND"] = b'{"id":"malformed-blind-first-attempt"}\n'
    rebind_campaign(bundle)

    receipt = invoke(bundle)
    assert scoring_map(bundle, "structured_overlap")[IDS[3]] == "인용됨"
    assert scoring_map(bundle, "structured_overlap_blind_veto")[IDS[3]] is None
    assert policy_map(bundle, "structured_overlap_blind_veto")[IDS[3]] == "기각"
    assert receipt["mechanism"]["blindFirstAttemptInvalid"]["ids"] == [IDS[3]]
    assert IDS[3] not in receipt["mechanism"]["blindTieOrUnresolved"]["ids"]
    assert IDS[4] in receipt["mechanism"]["blindTieOrUnresolved"]["ids"]


def test_invalid_blind_on_nonstructured_conflict_only_invalidates_answer_veto(
    tmp_path: Path,
) -> None:
    bundle = build_bundle(tmp_path)
    certificates = load_jsonl(bundle["certificates"])
    next(row for row in certificates if row["id"] == IDS[1])["preference"] = (
        "UNRESOLVED"
    )
    write_jsonl(bundle["certificates"], certificates)
    bundle["invalidByStage"]["BLIND"] = {IDS[1]}
    bundle["rawOverrides"]["BLIND"] = b'{"id":"malformed-nontrigger-blind"}\n'
    rebind_campaign(bundle)

    invoke(bundle)
    assert scoring_map(bundle, "answer_only_blind_veto")[IDS[1]] is None
    assert scoring_map(bundle, "structured_overlap_blind_veto")[IDS[1]] == "기각"
    assert policy_map(bundle, "structured_overlap_blind_veto")[IDS[1]] == "기각"


def test_exact_source_freeze_schema_rejects_added_field_even_under_resigned_manifest(
    tmp_path: Path,
) -> None:
    bundle = build_bundle(tmp_path)
    freeze = json.loads(bundle["freeze"].read_text(encoding="utf-8"))
    freeze["unregisteredHook"] = True
    freeze.pop("freezeSha256")
    freeze["freezeSha256"] = overlap.canonical_digest(freeze)
    write_json(bundle["freeze"], freeze)
    bundle["expectedFreezeFileSHA256"] = overlap.sha256_file(bundle["freeze"])
    campaign = json.loads(bundle["campaignManifest"].read_text(encoding="utf-8"))
    campaign["sourceFreezeFileSha256"] = bundle["expectedFreezeFileSHA256"]
    campaign["sourceFreezeSha256"] = freeze["freezeSha256"]
    _resign_campaign(bundle, campaign)

    with pytest.raises(overlap.CombinationValidationError, match="source freeze schema"):
        invoke(bundle)


def test_label_independence_and_conclusion_leak_receipts_are_semantic_gates(
    tmp_path: Path,
) -> None:
    bundle = build_bundle(tmp_path)
    id_receipt = json.loads(bundle["idReceipt"].read_text(encoding="utf-8"))
    id_receipt["labelFieldsRead"] = True
    id_receipt.pop("receiptSha256")
    id_receipt["receiptSha256"] = overlap.canonical_digest(id_receipt)
    write_json(bundle["idReceipt"], id_receipt)
    campaign = json.loads(bundle["campaignManifest"].read_text(encoding="utf-8"))
    source = campaign["sourceArtifacts"]
    source["labelIndependentIdReceiptFileSha256"] = overlap.sha256_file(bundle["idReceipt"])
    source["labelIndependentIdReceiptSha256"] = id_receipt["receiptSha256"]
    _resign_campaign(bundle, campaign)
    with pytest.raises(overlap.CombinationValidationError, match="ID derivation"):
        invoke(bundle)

    second = build_bundle(tmp_path / "second")
    leak = json.loads(second["leakReport"].read_text(encoding="utf-8"))
    leak["targetSpecificMetadataAudit"]["rowsWithTargetMetadata"] = 1
    leak["targetSpecificMetadataAudit"]["pass"] = False
    leak.pop("selfHash")
    leak["selfHash"] = overlap.canonical_digest(leak)
    write_json(second["leakReport"], leak)
    campaign = json.loads(second["campaignManifest"].read_text(encoding="utf-8"))
    source = campaign["sourceArtifacts"]
    source["conclusionLeakReportFileSha256"] = overlap.sha256_file(second["leakReport"])
    source["conclusionLeakReportSha256"] = leak["selfHash"]
    _resign_campaign(second, campaign)
    with pytest.raises(
        overlap.CombinationValidationError,
        match="target-specific metadata gate",
    ):
        invoke(second)


def test_public_constants_and_opaque_ids_are_exact(tmp_path: Path) -> None:
    bundle = build_bundle(tmp_path)
    rows = load_jsonl(bundle["public"])
    rows[0]["id"] = "grant-labelled-case-1"
    write_jsonl(bundle["public"], rows)
    with pytest.raises(overlap.CombinationValidationError, match="non-opaque ID"):
        invoke(bundle)

    second = build_bundle(tmp_path / "second")
    rows = load_jsonl(second["public"])
    rows[0]["benchmarkId"] = "outcome.labelled.grant"
    write_jsonl(second["public"], rows)
    with pytest.raises(overlap.CombinationValidationError, match="constant benchmarkId"):
        invoke(second)

    third = build_bundle(tmp_path / "third")
    rows = load_jsonl(third["public"])
    rows[0]["sourceCaseNumber"] = "label-bearing-metadata"
    write_jsonl(third["public"], rows)
    with pytest.raises(overlap.CombinationValidationError, match="public row 1 schema"):
        invoke(third)


def test_external_manifest_hash_cannot_be_replaced_by_self_resigning(tmp_path: Path) -> None:
    bundle = build_bundle(tmp_path)
    expected = bundle["expectedCampaignManifestFileSHA256"]
    campaign = json.loads(bundle["campaignManifest"].read_text(encoding="utf-8"))
    campaign["comparatorFairnessAudit"]["status"] = "SELF_DECLARED_ACCEPTED"
    campaign.pop("manifestSha256")
    campaign["manifestSha256"] = overlap.canonical_digest(campaign)
    write_json(bundle["campaignManifest"], campaign)
    bundle["expectedCampaignManifestFileSHA256"] = expected
    with pytest.raises(overlap.CombinationValidationError, match="campaign manifest file SHA-256"):
        invoke(bundle)


def test_two_phase_blind_freeze_separates_template_from_instantiated_packet(
    tmp_path: Path,
) -> None:
    bundle = build_bundle(tmp_path)
    source_bytes = bundle["freeze"].read_bytes()
    source = json.loads(source_bytes)
    blind_freeze = json.loads(
        bundle["blindPackageFreeze"].read_text(encoding="utf-8")
    )
    assert "blindPromptSha256" not in source
    assert source["blindPromptTemplateSha256"] == overlap.sha256_file(
        bundle["blindPromptTemplate"]
    )
    assert blind_freeze["instantiatedBlindPromptPacketSha256"] == overlap.sha256_file(
        bundle["blindPrompt"]
    )
    assert (
        source["blindPromptTemplateSha256"]
        != blind_freeze["instantiatedBlindPromptPacketSha256"]
    )
    assert invoke(bundle)["status"] == "accepted"
    assert bundle["freeze"].read_bytes() == source_bytes


def test_blind_package_external_anchor_and_instantiated_packet_tamper_fail_closed(
    tmp_path: Path,
) -> None:
    bundle = build_bundle(tmp_path)
    expected = bundle["expectedBlindPackageFreezeFileSHA256"]
    freeze = json.loads(bundle["blindPackageFreeze"].read_text(encoding="utf-8"))
    freeze["expectedConflictRows"] += 1
    freeze.pop("freezeSha256")
    freeze["freezeSha256"] = overlap.canonical_digest(freeze)
    write_json(bundle["blindPackageFreeze"], freeze)
    campaign = json.loads(bundle["campaignManifest"].read_text(encoding="utf-8"))
    campaign["blindPackageFreezeFileSha256"] = overlap.sha256_file(
        bundle["blindPackageFreeze"]
    )
    campaign["blindPackageFreezeSha256"] = freeze["freezeSha256"]
    _resign_campaign(bundle, campaign)
    bundle["expectedBlindPackageFreezeFileSHA256"] = expected
    with pytest.raises(
        overlap.CombinationValidationError,
        match="blind-package freeze file SHA-256 mismatch",
    ):
        invoke(bundle)

    second = build_bundle(tmp_path / "second")
    second["blindPrompt"].write_text("tampered post-freeze packet\n", encoding="utf-8")
    with pytest.raises(
        overlap.CombinationValidationError,
        match="BLIND instantiated prompt packet derivation",
    ):
        invoke(second)

    third = build_bundle(tmp_path / "third")
    write_json(
        third["blindActualOutputSchema"],
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "x-rowCount": 999,
        },
    )
    with pytest.raises(
        overlap.CombinationValidationError,
        match="BLIND instantiated output-schema derivation",
    ):
        invoke(third)


def test_output_schema_file_hash_and_cli_argument_are_bound(tmp_path: Path) -> None:
    bundle = build_bundle(tmp_path)
    mutate_stage_receipt(
        bundle,
        "G1",
        lambda receipt: receipt.update(outputSchemaCliArg="--not-output-schema"),
    )
    with pytest.raises(
        overlap.CombinationValidationError,
        match="G1 receipt outputSchemaCliArg",
    ):
        invoke(bundle)

    second = build_bundle(tmp_path / "second")
    write_json(second["generatorOutputSchema"], {"type": "array"})
    with pytest.raises(
        overlap.CombinationValidationError,
        match="campaign generator output-schema hash",
    ):
        invoke(second)

    third = build_bundle(tmp_path / "third")
    source = json.loads(third["freeze"].read_text(encoding="utf-8"))
    source["outputSchemaCliArg"] = "--schema"
    source.pop("freezeSha256")
    source["freezeSha256"] = overlap.canonical_digest(source)
    write_json(third["freeze"], source)
    third["expectedFreezeFileSHA256"] = overlap.sha256_file(third["freeze"])
    campaign = json.loads(third["campaignManifest"].read_text(encoding="utf-8"))
    campaign["sourceFreezeFileSha256"] = third["expectedFreezeFileSHA256"]
    campaign["sourceFreezeSha256"] = source["freezeSha256"]
    _resign_campaign(third, campaign)
    with pytest.raises(
        overlap.CombinationValidationError,
        match="source freeze output-schema CLI argument",
    ):
        invoke(third)


def test_generic_regex_sensitivity_findings_are_informational(tmp_path: Path) -> None:
    bundle = build_bundle(tmp_path)
    audit = json.loads(bundle["leakReport"].read_text(encoding="utf-8"))
    assert audit["leakAudit"] == {
        "affectsFinalGate": False,
        "rowsWithAnyFinding": 244,
    }
    assert invoke(bundle)["status"] == "accepted"


def test_retry_legacy_runner_gold_access_and_provenance_exposure_are_rejected(
    tmp_path: Path,
) -> None:
    bundle = build_bundle(tmp_path)
    mutate_attempt_ledger(
        bundle,
        "G1",
        lambda ledger: ledger.update(selectiveRetryCount=1),
    )
    with pytest.raises(overlap.CombinationValidationError, match="retry/attempt policy"):
        invoke(bundle)

    second = build_bundle(tmp_path / "second")
    mutate_stage_receipt(
        second, "G1", lambda receipt: receipt.update(legacyFileAgentUsed=True)
    )
    with pytest.raises(overlap.CombinationValidationError, match="receipt attempt policy"):
        invoke(second)

    third = build_bundle(tmp_path / "third")
    mutate_stage_receipt(
        third,
        "G1",
        lambda receipt: receipt["visibilityBoundary"].update(privateLabelsMounted=True),
    )
    with pytest.raises(overlap.CombinationValidationError, match="indicates gold access"):
        invoke(third)

    fourth = build_bundle(tmp_path / "fourth")
    mutate_stage_receipt(
        fourth,
        "BLIND",
        lambda receipt: receipt["visibilityBoundary"].update(
            candidateProvenanceExposed=True
        ),
    )
    with pytest.raises(overlap.CombinationValidationError, match="not provenance-blind"):
        invoke(fourth)

    fifth = build_bundle(tmp_path / "fifth")
    mutate_stage_receipt(
        fifth,
        "G2",
        lambda receipt: receipt["visibilityBoundary"].update(
            otherGeneratorArtifactsMounted=True
        ),
    )
    with pytest.raises(overlap.CombinationValidationError, match="isolated visibility"):
        invoke(fifth)

    sixth = build_bundle(tmp_path / "sixth")
    mutate_stage_receipt(
        sixth,
        "G3",
        lambda receipt: receipt.update(configuredModelToolSchemaCount=1),
    )
    with pytest.raises(overlap.CombinationValidationError, match="receipt attempt policy"):
        invoke(sixth)


def test_strict_config_feature_snapshot_and_control_argv_are_exact_gates(
    tmp_path: Path,
) -> None:
    bundle = build_bundle(tmp_path)
    mutate_stage_receipt(
        bundle,
        "G1",
        lambda receipt: receipt["executionSettings"]["features"].update(
            unified_exec=True
        ),
    )
    with pytest.raises(
        overlap.CombinationValidationError,
        match="G1 receipt executionSettings",
    ):
        invoke(bundle)

    second = build_bundle(tmp_path / "second")
    mutate_stage_receipt(
        second,
        "G2",
        lambda receipt: receipt.update(strictConfig=False),
    )
    with pytest.raises(
        overlap.CombinationValidationError,
        match="G2 receipt strictConfig",
    ):
        invoke(second)

    third = build_bundle(tmp_path / "third")
    mutate_stage_receipt(
        third,
        "G3",
        lambda receipt: receipt.update(configArgvSha256="0" * 64),
    )
    with pytest.raises(
        overlap.CombinationValidationError,
        match="G3 receipt configArgvSha256",
    ):
        invoke(third)

    fourth = build_bundle(tmp_path / "fourth")
    mutate_stage_receipt(
        fourth,
        "BLIND",
        lambda receipt: receipt.update(
            codexFeaturesSnapshotSha256="f" * 64
        ),
    )
    with pytest.raises(
        overlap.CombinationValidationError,
        match="BLIND receipt codexFeaturesSnapshotSha256",
    ):
        invoke(fourth)


def test_item_started_command_is_detected_in_raw_trace(tmp_path: Path) -> None:
    bundle = build_bundle(tmp_path)
    inject_trace_tool_event(bundle, "G1")
    with pytest.raises(overlap.CombinationValidationError, match="item type not allowlisted"):
        invoke(bundle)


@pytest.mark.parametrize("item_type", ["file_change", "future_unclassified_tool"])
def test_unknown_item_types_fail_closed_under_trace_allowlist(
    tmp_path: Path,
    item_type: str,
) -> None:
    bundle = build_bundle(tmp_path)
    inject_trace_tool_event(bundle, "G1", item_type=item_type)
    with pytest.raises(
        overlap.CombinationValidationError,
        match="item type not allowlisted",
    ):
        invoke(bundle)


def test_unknown_trace_event_type_fails_closed(tmp_path: Path) -> None:
    bundle = build_bundle(tmp_path)
    inject_trace_tool_event(
        bundle,
        "G1",
        event_type="future.model_tool_event",
        item_type=None,
    )
    with pytest.raises(
        overlap.CombinationValidationError,
        match="event type not allowlisted",
    ):
        invoke(bundle)


def test_only_exact_code_mode_containment_diagnostic_is_accepted(
    tmp_path: Path,
) -> None:
    trace_path = tmp_path / "trace.jsonl"
    rows = valid_zero_tool_trace("G1", "thread-g1")
    rows[1]["item"]["message"] = "some other error"
    write_jsonl(trace_path, rows)
    with pytest.raises(
        overlap.CombinationValidationError,
        match="unexpected error item",
    ):
        overlap._audit_zero_tool_trace(trace_path, stage="G1")


def test_containment_diagnostic_must_immediately_follow_thread_start(
    tmp_path: Path,
) -> None:
    trace_path = tmp_path / "trace.jsonl"
    rows = valid_zero_tool_trace("G1", "thread-g1")
    rows[1], rows[2] = rows[2], rows[1]
    write_jsonl(trace_path, rows)
    with pytest.raises(
        overlap.CombinationValidationError,
        match="containment/turn lifecycle",
    ):
        overlap._audit_zero_tool_trace(trace_path, stage="G1")


def test_stages_must_have_distinct_thread_identities(tmp_path: Path) -> None:
    bundle = build_bundle(tmp_path)
    replace_stage_thread_id(bundle, "G2", "thread-g1-unique")
    with pytest.raises(
        overlap.CombinationValidationError,
        match="stage thread identities are not distinct",
    ):
        invoke(bundle)


def test_unhashable_json_types_are_normalized_to_combination_error(tmp_path: Path) -> None:
    bundle = build_bundle(tmp_path)
    rows = load_jsonl(bundle["G2"])
    rows[0]["outcome"] = []
    write_jsonl(bundle["G2"], rows)
    rebind_campaign(bundle)
    with pytest.raises(overlap.CombinationValidationError, match="invalid outcome"):
        invoke(bundle)


def test_never_overwrites_an_existing_complete_output(tmp_path: Path) -> None:
    bundle = build_bundle(tmp_path)
    first = invoke(bundle)
    receipt_path = bundle["output"] / "mechanism_receipt.json"
    before = receipt_path.read_bytes()

    with pytest.raises(overlap.CombinationValidationError, match="refusing to overwrite"):
        invoke(bundle)
    assert receipt_path.read_bytes() == before
    assert json.loads(before)["receiptSha256"] == first["receiptSha256"]
