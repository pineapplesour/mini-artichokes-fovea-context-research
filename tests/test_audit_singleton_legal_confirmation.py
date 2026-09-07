from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping

import pytest

from tools import audit_singleton_legal_confirmation as audit
from tools import run_singleton_legal_campaign as runner
from tools import score_singleton_legal_campaign as scorer


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )


def _resign(value: dict[str, Any], field: str) -> None:
    value.pop(field, None)
    value[field] = audit.canonical_digest(value)


def _id(index: int) -> str:
    return f"outcome-confirm-{index:020x}"


def _receipt(unit: Mapping[str, Any], tokens: int, position: int) -> dict[str, Any]:
    usage = {
        "inputTokens": tokens,
        "cachedInputTokens": 0,
        "cacheWriteInputTokens": 0,
        "outputTokens": 0,
        "reasoningTokens": 0,
        "totalTokens": tokens,
    }
    return {
        "schemaVersion": 1,
        "protocol": runner.UNIT_RECEIPT_PROTOCOL,
        "status": "accepted_complete",
        "campaignId": "synthetic-fairness-campaign",
        "unitId": unit["unitId"],
        "caseId": unit["caseId"],
        "armId": unit["armId"],
        "stageId": unit["stageId"],
        "registryFileSha256": f"{position + 1:064x}",
        "registrySha256": f"{position + 2:064x}",
        "traceSha256": f"{position + 3:064x}",
        "stderrSha256": f"{position + 4:064x}",
        "normalizedResultSha256": f"{position + 5:064x}",
        "threadId": f"thread-{position}",
        "turnCount": 1,
        "completedAgentMessageCount": 1,
        "responseValid": True,
        "invalidResponseReason": None,
        "scientificOutcome": "인용됨",
        "tokenUsage": usage,
        "processInvocationCount": 1,
        "semanticRetryCount": 0,
        "transportRetryCount": 0,
        "wallTimeMilliseconds": 10,
        "receiptSha256": f"{position + 6:064x}",
    }


PHYSICAL_COSTS = {
    "Mini-4": 40,
    "Plain-Luna-1": 96,
    "Structured-Direct-1": 150,
    "SC-4": 30,
    "Bo3+J": 21,
    "CR-4": 39,
    "task-adapted-ICR-4": 27,
    "answer-only-veto-4": 44,
}
PHYSICAL_CALL_COUNTS = {
    "Mini-4": 3,
    "Plain-Luna-1": 1,
    "Structured-Direct-1": 1,
    "SC-4": 8,
    "Bo3+J": 4,
    "CR-4": 4,
    "task-adapted-ICR-4": 4,
    "answer-only-veto-4": 3,
}


def _build_bundle(tmp_path: Path) -> dict[str, Any]:
    root = tmp_path / "campaign"
    root.mkdir()
    campaign_id = "synthetic-fairness-campaign"
    case_ids = [_id(index) for index in range(440)]
    units: list[dict[str, Any]] = []
    receipts: list[dict[str, Any]] = []
    scientific_rows: list[dict[str, Any]] = []
    units_for: dict[tuple[str, str], list[str]] = {}
    for case_id in case_ids:
        for paper_arm in audit.PRIMARY_ARMS:
            runner_arm = scorer.RUNNER_ARM_BY_PAPER_ARM[paper_arm]
            call_count = PHYSICAL_CALL_COUNTS[paper_arm]
            arm_units: list[str] = []
            for call_index in range(call_count):
                suffix = f"-s{call_index + 1}" if call_count > 1 else ""
                unit_id = (
                    f"u-{case_id.removeprefix('outcome-confirm-')}-{runner_arm}{suffix}"
                )
                stage_id = (
                    "answer"
                    if call_index == 0
                    else f"draw-d{call_index + 1}"
                    if paper_arm == "SC-4"
                    else f"stage-{call_index + 1}"
                )
                unit = {
                    "unitId": unit_id,
                    "caseId": case_id,
                    "armId": runner_arm,
                    "stageId": stage_id,
                    "dependencies": [],
                    "promptPath": f"packets/{unit_id}.txt",
                    "promptSha256": "1" * 64,
                    "outputSchemaPath": "schemas/answer.json",
                    "outputSchemaSha256": "2" * 64,
                    "producesScientificOutcome": call_index == 0,
                }
                units.append(unit)
                receipt = _receipt(unit, PHYSICAL_COSTS[paper_arm], len(receipts))
                receipts.append(receipt)
                arm_units.append(unit_id)
                if call_index == 0:
                    scientific_rows.append(
                        {
                            "id": case_id,
                            "armId": runner_arm,
                            "unitId": unit_id,
                            "outcome": "인용됨",
                        }
                    )
            units_for[(case_id, paper_arm)] = arm_units

    ordered = [unit["unitId"] for unit in units]
    token_totals = {key: 0 for key in runner.TOKEN_KEYS}
    for receipt in receipts:
        for key in runner.TOKEN_KEYS:
            token_totals[key] += receipt["tokenUsage"][key]

    runner_root = root / "runner"
    output_root = root / "run"
    unit_manifest_path = runner_root / "unit_manifest.json"
    schedule_path = runner_root / "schedule.json"
    predictions_path = output_root / "scientific_predictions.jsonl"
    campaign_receipt_path = output_root / "campaign_receipt.json"
    _write_json(unit_manifest_path, {"synthetic": "unit manifest"})
    _write_json(schedule_path, {"synthetic": "schedule"})
    output_root.mkdir()
    predictions_path.write_bytes(b"synthetic predictions\n")
    predictions_sha = audit.sha256_file(predictions_path)
    campaign_receipt = {
        "campaignId": campaign_id,
        "campaignGitCommit": "c" * 40,
        "receiptSha256": "a" * 64,
        "scientificPredictionsSha256": predictions_sha,
        "tokenTotals": token_totals,
        "campaignProcessInvocationCount": len(receipts),
        "semanticRetryCount": 0,
        "transportRetryCount": 0,
        "unitWallTimeMillisecondsTotal": 10 * len(receipts),
    }
    _write_json(campaign_receipt_path, campaign_receipt)
    runner_binding = {
        "unitManifestPath": unit_manifest_path.relative_to(root).as_posix(),
        "unitManifestFileSha256": audit.sha256_file(unit_manifest_path),
        "schedulePath": schedule_path.relative_to(root).as_posix(),
        "scheduleFileSha256": audit.sha256_file(schedule_path),
        "campaignGitCommit": "c" * 40,
        "outputDirectory": output_root.relative_to(root).as_posix(),
        "campaignReceiptFileSha256": audit.sha256_file(campaign_receipt_path),
        "campaignReceiptSha256": campaign_receipt["receiptSha256"],
        "scientificPredictionsFileSha256": predictions_sha,
    }
    validated = {
        "manifest": {"units": units, "gitAnchor": {"commit": "b" * 40}},
        "schedule": {"orderedUnitIds": ordered},
        "campaignReceipt": campaign_receipt,
        "unitReceipts": receipts,
        "unitResults": [],
        "scientificRows": scientific_rows,
        "runtimeIdentity": {"identitySha256": "b" * 64},
    }

    weight_source = root / "token_weights.txt"
    weight_source_document: dict[str, Any] = {
        "schemaVersion": 1,
        "kind": audit.WEIGHT_SOURCE_KIND,
        "version": "synthetic-v1",
        "costWeights": {
            "uncachedInputWeight": "1",
            "cachedInputWeight": "0",
            "outputWeight": "1",
        },
        "rationale": "Synthetic exact token-equivalent weights for tests.",
    }
    _resign(weight_source_document, "selfHash")
    _write_json(weight_source, weight_source_document)
    rationale = root / "ni_rationale.txt"
    ni_rationale_text = (
        "Five points was fixed from synthetic exposed development evidence."
    )
    rationale_document: dict[str, Any] = {
        "schemaVersion": 1,
        "margin": "0.05",
        "rationale": ni_rationale_text,
        "selectionEvidenceScope": audit.SELECTION_SCOPE,
    }
    _resign(rationale_document, "selfHash")
    _write_json(rationale, rationale_document)
    attribution_policy = root / "attribution_policy.txt"
    attribution_policy_document: dict[str, Any] = {
        "schemaVersion": 1,
        "protocol": audit.ATTRIBUTION_POLICY_PROTOCOL,
        "version": "synthetic-v1",
        "primaryResponseCaps": audit.PRIMARY_RESPONSE_CAPS,
        "primaryResponseMinimums": audit.PRIMARY_RESPONSE_MINIMUMS,
        "scPrefixRule": audit.SC_PREFIX_RULE,
        "miniCallRule": audit.MINI_CALL_RULE,
        "answerOnlyVetoCallRule": audit.AOV_CALL_RULE,
        "sharedCallChargingRule": audit.SHARED_CHARGING_RULE,
    }
    _resign(attribution_policy_document, "selfHash")
    _write_json(attribution_policy, attribution_policy_document)
    contract: dict[str, Any] = {
        "schemaVersion": 1,
        "protocol": audit.CONTRACT_PROTOCOL,
        "status": audit.CONTRACT_STATUS,
        "campaignId": campaign_id,
        "candidateArm": audit.CANDIDATE,
        "primaryComparatorArms": list(audit.PRIMARY_COMPARATORS),
        "requiredCostArms": list(audit.REQUIRED_COST_ARMS),
        "supplementaryCostArms": [],
        "costPolicy": {
            "matchingLowerBound": "0.80",
            "matchingUpperBound": "1.25",
            "arithmetic": audit.COST_ARITHMETIC,
            "roundingTolerance": "0",
            "formula": audit.COST_FORMULA,
            "criticalPathMethod": audit.CRITICAL_PATH_METHOD,
            "scPrefixSelector": audit.SC_SELECTOR,
            "costWeights": {
                "uncachedInputWeight": "1",
                "cachedInputWeight": "0",
                "outputWeight": "1",
            },
            "weightSource": {
                "kind": audit.WEIGHT_SOURCE_KIND,
                "version": "synthetic-v1",
                "path": weight_source.relative_to(root).as_posix(),
                "sha256": audit.sha256_file(weight_source),
            },
            "attributionPolicySource": {
                "version": "synthetic-v1",
                "path": attribution_policy.relative_to(root).as_posix(),
                "sha256": audit.sha256_file(attribution_policy),
            },
            "stageTokenLimits": {
                "answer": {"maxOutputTokens": 100, "maxTotalTokens": 200},
                **{
                    f"draw-d{index}": {
                        "maxOutputTokens": 100,
                        "maxTotalTokens": 200,
                    }
                    for index in range(2, 9)
                },
                **{
                    f"stage-{index}": {
                        "maxOutputTokens": 100,
                        "maxTotalTokens": 200,
                    }
                    for index in range(2, 5)
                },
            },
        },
        "domainNoninferiority": {
            "margin": "0.05",
            "rationale": ni_rationale_text,
            "rationaleEvidencePath": rationale.relative_to(root).as_posix(),
            "rationaleEvidenceSha256": audit.sha256_file(rationale),
            "selectionEvidenceScope": audit.SELECTION_SCOPE,
            "alpha": "0.05",
            "confidenceLevel": "0.95",
            "intervalMethod": audit.NI_INTERVAL_METHOD,
            "bootstrapSeed": "synthetic-bootstrap-seed",
            "bootstrapReplicates": 999,
            "numericalTolerance": "0",
            "rule": audit.NI_RULE,
        },
        "implementation": {
            "auditorSha256": audit.sha256_file(Path(audit.__file__).resolve()),
            "runnerSha256": audit.sha256_file(Path(runner.__file__).resolve()),
            "scorerSha256": audit.sha256_file(Path(scorer.__file__).resolve()),
        },
    }
    _resign(contract, "selfHash")
    contract_path = root / "fairness_contract.json"
    _write_json(contract_path, contract)
    contract_file_sha = audit.sha256_file(contract_path)
    validated["manifest"]["codeHashes"] = {
        str(contract_path.resolve()): contract_file_sha
    }

    attribution: list[dict[str, Any]] = []
    for arm in audit.REQUIRED_COST_ARMS:
        prefix_count = int(arm.removeprefix("SC-")) if arm in audit.SC_PREFIXES else None
        attribution.append(
            {
                "arm": arm,
                "cases": [
                    {
                        "id": case_id,
                        "unitIds": (
                            units_for[(case_id, "SC-4")][:prefix_count]
                            if prefix_count is not None
                            else units_for[(case_id, arm)]
                        ),
                    }
                    for case_id in case_ids
                ],
            }
        )
    evidence: dict[str, Any] = {
        "schemaVersion": 1,
        "protocol": audit.EVIDENCE_PROTOCOL,
        "status": audit.EVIDENCE_STATUS,
        "campaignId": campaign_id,
        "contractPath": contract_path.relative_to(root).as_posix(),
        "contractFileSha256": contract_file_sha,
        "contractSelfHash": contract["selfHash"],
        "runnerCampaign": runner_binding,
        "armAttribution": attribution,
        "claimedSelectedScPrefix": "SC-4",
    }
    _resign(evidence, "selfHash")
    evidence_path = root / "cost_evidence.json"
    _write_json(evidence_path, evidence)

    score_manifest = {
        "statistics": {
            "alpha": 0.05,
            "confidenceLevel": 0.95,
            "bootstrapMethod": audit.NI_INTERVAL_METHOD,
            "bootstrapSeed": "synthetic-bootstrap-seed",
            "bootstrapReplicates": 999,
        },
        "implementation": {"scorerSha256": contract["implementation"]["scorerSha256"]},
    }
    score_manifest_path = root / "score_manifest.json"
    _write_json(score_manifest_path, score_manifest)

    comparisons = {}
    components = {}
    for comparator in audit.PRIMARY_COMPARATORS:
        comparisons[comparator] = {
            "stratifiedPairedBootstrap": {
                "method": audit.NI_INTERVAL_METHOD,
                "oneSidedConfidenceLevel": 0.95,
                "domainLabelBalancedRiskDifferenceLowerBounds": {
                    "civil": -0.04,
                    "tax": -0.04,
                },
            }
        }
        components[comparator] = {"passed": True}
    score_report: dict[str, Any] = {
        "schemaVersion": 1,
        "protocol": scorer.PROTOCOL,
        "status": "SCORED_FULL_DENOMINATOR",
        "campaignId": campaign_id,
        "candidateArm": audit.CANDIDATE,
        "comparatorArms": list(audit.PRIMARY_COMPARATORS),
        "bindings": {"runnerCampaign": dict(runner_binding)},
        "denominator": {
            "n": 440,
            "orderedIdsSha256": audit.canonical_digest(case_ids),
            "cellCounts": {
                "civil|인용됨": 140,
                "civil|기각": 140,
                "tax|인용됨": 80,
                "tax|기각": 80,
            },
        },
        "comparisons": comparisons,
        "primaryFixedIntersectionUnionTest": {
            "membership": list(audit.PRIMARY_COMPARATORS),
            "components": components,
            "passed": True,
        },
    }
    _resign(score_report, "reportSha256")
    score_report_path = root / "score_report.json"
    _write_json(score_report_path, score_report)

    return {
        "root": root,
        "contract": contract_path,
        "contractSha": contract_file_sha,
        "evidence": evidence_path,
        "evidenceSha": audit.sha256_file(evidence_path),
        "scoreManifest": score_manifest_path,
        "scoreManifestSha": audit.sha256_file(score_manifest_path),
        "preGoldCostCommit": "d" * 40,
        "scoreFreezeCommit": "e" * 40,
        "scoreReport": score_report_path,
        "scoreReportSha": audit.sha256_file(score_report_path),
        "validated": validated,
    }


def _invoke(bundle: Mapping[str, Any]) -> dict[str, Any]:
    def fake_runner(**_kwargs: Any) -> Mapping[str, Any]:
        return bundle["validated"]

    def fake_scorer(**_kwargs: Any) -> Mapping[str, Any]:
        return json.loads(bundle["scoreReport"].read_text(encoding="utf-8"))

    def fake_chronology(**kwargs: Any) -> Mapping[str, str]:
        assert kwargs["phase_a_commit"] == "b" * 40
        assert kwargs["expected_pre_gold_cost_git_commit"] == "d" * 40
        assert kwargs["expected_score_freeze_git_commit"] == "e" * 40
        return {
            "repositoryRoot": str(bundle["root"]),
            "phaseACommit": "b" * 40,
            "preGoldCostCommit": "d" * 40,
            "scoreFreezeCommit": "e" * 40,
        }

    return audit.build_audit(
        contract_path=bundle["contract"],
        expected_contract_file_sha256=bundle["contractSha"],
        cost_evidence_path=bundle["evidence"],
        expected_cost_evidence_file_sha256=bundle["evidenceSha"],
        score_manifest_path=bundle["scoreManifest"],
        expected_score_manifest_file_sha256=bundle["scoreManifestSha"],
        expected_pre_gold_cost_git_commit=bundle["preGoldCostCommit"],
        expected_score_freeze_git_commit=bundle["scoreFreezeCommit"],
        score_report_path=bundle["scoreReport"],
        expected_score_report_file_sha256=bundle["scoreReportSha"],
        runner_validator=fake_runner,
        score_builder=fake_scorer,
        chronology_verifier=fake_chronology,
    )


def _rewrite_evidence(bundle: dict[str, Any], evidence: dict[str, Any]) -> None:
    _resign(evidence, "selfHash")
    _write_json(bundle["evidence"], evidence)
    bundle["evidenceSha"] = audit.sha256_file(bundle["evidence"])


def _rewrite_score_report(bundle: dict[str, Any], report: dict[str, Any]) -> None:
    _resign(report, "reportSha256")
    _write_json(bundle["scoreReport"], report)
    bundle["scoreReportSha"] = audit.sha256_file(bundle["scoreReport"])


def test_complete_read_only_audit_has_exact_cost_and_domain_gates(tmp_path: Path) -> None:
    bundle = _build_bundle(tmp_path)
    report = _invoke(bundle)

    assert report["status"] == "AUDITED_READ_ONLY"
    assert report["reserveScope"] == {
        "civilPerLabel": 140,
        "taxPerLabel": 80,
        "n": 440,
        "balancedWithinDomain": True,
        "protocolQuotaPassed": True,
    }
    eligibility = report["perComparatorCostEligibility"]
    assert eligibility["Plain-Luna-1"]["costRatioComparatorOverMiniExact"] == {
        "numerator": "4",
        "denominator": "5",
    }
    assert eligibility["Plain-Luna-1"]["measuredCostMatched"] is True
    assert eligibility["Structured-Direct-1"]["measuredCostMatched"] is True
    assert eligibility["Bo3+J"]["classification"] == "lower_cost"
    assert eligibility["CR-4"]["classification"] == "higher_cost"
    assert report["selectedScPrefix"]["value"] == "SC-4"
    assert report["armLedgers"]["Mini-4"]["tokenTotals"]["inputTokens"] == 52_800
    assert report["armLedgers"]["Mini-4"]["processInvocations"] == 1_320
    assert report["armLedgers"]["Mini-4"]["wallTimeMillisecondsTotal"] == 13_200
    assert report["domainNoninferiority"]["allPrimaryComparatorDomainsPassed"] is True
    assert report["claimAuthorization"]["aggregateSuperiorityWithDomainNoHarmAuthorized"] is True
    assert report["claimAuthorization"]["measuredCostMatchedScPrefixClaimAuthorized"] is True


def test_missing_attributed_case_unit_fails_closed(tmp_path: Path) -> None:
    bundle = _build_bundle(tmp_path)
    evidence = json.loads(bundle["evidence"].read_text(encoding="utf-8"))
    evidence["armAttribution"][0]["cases"][0]["unitIds"] = []
    _rewrite_evidence(bundle, evidence)
    with pytest.raises(audit.ConfirmationAuditError, match="attributed units"):
        _invoke(bundle)


def test_campaign_token_aggregate_mismatch_fails_closed(tmp_path: Path) -> None:
    bundle = _build_bundle(tmp_path)
    bundle["validated"]["campaignReceipt"]["tokenTotals"]["inputTokens"] += 1
    with pytest.raises(audit.ConfirmationAuditError, match="aggregate cost ledger"):
        _invoke(bundle)


def test_stage_token_ceiling_is_mandatory_and_enforced(tmp_path: Path) -> None:
    bundle = _build_bundle(tmp_path)
    receipt = bundle["validated"]["unitReceipts"][0]
    receipt["tokenUsage"]["inputTokens"] = 201
    receipt["tokenUsage"]["totalTokens"] = 201
    bundle["validated"]["campaignReceipt"]["tokenTotals"]["inputTokens"] += 101
    bundle["validated"]["campaignReceipt"]["tokenTotals"]["totalTokens"] += 101
    with pytest.raises(audit.ConfirmationAuditError, match="token ceiling"):
        _invoke(bundle)


def test_ni_threshold_is_strict_not_inclusive(tmp_path: Path) -> None:
    bundle = _build_bundle(tmp_path)
    report = json.loads(bundle["scoreReport"].read_text(encoding="utf-8"))
    report["comparisons"]["Plain-Luna-1"]["stratifiedPairedBootstrap"][
        "domainLabelBalancedRiskDifferenceLowerBounds"
    ]["civil"] = -0.05
    _rewrite_score_report(bundle, report)
    audited = _invoke(bundle)
    gate = audited["domainNoninferiority"]["primaryComparatorGates"]["Plain-Luna-1"]
    assert gate["domains"]["civil"]["passed"] is False
    assert gate["passed"] is False
    assert audited["claimAuthorization"]["aggregateSuperiorityWithDomainNoHarmAuthorized"] is False
    assert audited["claimAuthorization"]["measuredCostMatchedScPrefixClaimAuthorized"] is False


def test_absent_numeric_ni_margin_has_no_default(tmp_path: Path) -> None:
    bundle = _build_bundle(tmp_path)
    contract = json.loads(bundle["contract"].read_text(encoding="utf-8"))
    del contract["domainNoninferiority"]["margin"]
    _resign(contract, "selfHash")
    _write_json(bundle["contract"], contract)
    bundle["contractSha"] = audit.sha256_file(bundle["contract"])
    with pytest.raises(audit.ConfirmationAuditError, match="domainNoninferiority schema"):
        audit._load_contract(bundle["contract"], bundle["contractSha"])


def test_unbalanced_or_too_small_reserve_fails_closed(tmp_path: Path) -> None:
    bundle = _build_bundle(tmp_path)
    report = json.loads(bundle["scoreReport"].read_text(encoding="utf-8"))
    report["denominator"]["cellCounts"]["civil|인용됨"] = 139
    report["denominator"]["cellCounts"]["civil|기각"] = 141
    _rewrite_score_report(bundle, report)
    with pytest.raises(audit.ConfirmationAuditError, match="predeclared balanced"):
        _invoke(bundle)


def test_selected_non_sc4_prefix_cannot_receive_unavailable_score_gate(tmp_path: Path) -> None:
    bundle = _build_bundle(tmp_path)
    evidence = json.loads(bundle["evidence"].read_text(encoding="utf-8"))
    sc4_runner_arm = scorer.RUNNER_ARM_BY_PAPER_ARM["SC-4"]
    changed = 0
    for receipt in bundle["validated"]["unitReceipts"]:
        if receipt["armId"] == sc4_runner_arm:
            receipt["tokenUsage"]["inputTokens"] = 24
            receipt["tokenUsage"]["totalTokens"] = 24
            changed += 1
    bundle["validated"]["campaignReceipt"]["tokenTotals"]["inputTokens"] -= 6 * changed
    bundle["validated"]["campaignReceipt"]["tokenTotals"]["totalTokens"] -= 6 * changed
    evidence["claimedSelectedScPrefix"] = "SC-5"
    _rewrite_evidence(bundle, evidence)
    report = _invoke(bundle)
    assert report["selectedScPrefix"]["value"] == "SC-5"
    assert report["domainNoninferiority"]["selectedScGate"]["scoreEvidencePresent"] is False
    assert report["claimAuthorization"]["measuredCostMatchedScPrefixClaimAuthorized"] is False


def test_reasoning_tokens_are_reported_but_not_double_charged() -> None:
    weights = {
        "uncachedInputWeight": Fraction(1),
        "cachedInputWeight": Fraction(1, 2),
        "outputWeight": Fraction(2),
    }
    base = {
        "inputTokens": 10,
        "cachedInputTokens": 2,
        "outputTokens": 5,
        "reasoningTokens": 0,
    }
    with_reasoning = dict(base, reasoningTokens=5)
    assert audit._unit_cost(base, weights) == audit._unit_cost(with_reasoning, weights)


def test_fraction_cost_arithmetic_does_not_round_long_decimal_weights() -> None:
    uncached = Fraction(audit.Decimal("0.123456789012345678901234567890123456789"))
    output = Fraction(audit.Decimal("1.000000000000000000000000000000000000001"))
    usage = {
        "inputTokens": 98_765_432_109_876_543_210,
        "cachedInputTokens": 0,
        "outputTokens": 12_345_678_901_234_567_890,
    }
    weights = {
        "uncachedInputWeight": uncached,
        "cachedInputWeight": Fraction(0),
        "outputWeight": output,
    }
    expected = uncached * usage["inputTokens"] + output * usage["outputTokens"]
    assert audit._unit_cost(usage, weights) == expected


def test_nonnested_sc_prefix_attribution_fails_closed(tmp_path: Path) -> None:
    bundle = _build_bundle(tmp_path)
    evidence = json.loads(bundle["evidence"].read_text(encoding="utf-8"))
    sc2 = next(row for row in evidence["armAttribution"] if row["arm"] == "SC-2")
    case_id = sc2["cases"][0]["id"]
    replacement = next(
        unit["unitId"]
        for unit in bundle["validated"]["manifest"]["units"]
        if unit["caseId"] == case_id
        and unit["armId"] == scorer.RUNNER_ARM_BY_PAPER_ARM["Plain-Luna-1"]
    )
    sc2["cases"][0]["unitIds"][0] = replacement
    sc2["cases"][0]["unitIds"] = sorted(
        sc2["cases"][0]["unitIds"],
        key=[
            unit["unitId"] for unit in bundle["validated"]["manifest"]["units"]
        ].index,
    )
    _rewrite_evidence(bundle, evidence)
    with pytest.raises(audit.ConfirmationAuditError, match="exact nested"):
        _invoke(bundle)


def test_more_than_four_attributed_responses_fails_closed(tmp_path: Path) -> None:
    bundle = _build_bundle(tmp_path)
    evidence = json.loads(bundle["evidence"].read_text(encoding="utf-8"))
    mini = next(row for row in evidence["armAttribution"] if row["arm"] == "Mini-4")
    case_id = mini["cases"][0]["id"]
    ordered_same_case = [
        unit["unitId"]
        for unit in bundle["validated"]["manifest"]["units"]
        if unit["caseId"] == case_id
    ]
    mini["cases"][0]["unitIds"] = ordered_same_case[:5]
    _rewrite_evidence(bundle, evidence)
    with pytest.raises(audit.ConfirmationAuditError, match="response-count bounds"):
        _invoke(bundle)


def test_selected_pair_cannot_bypass_failed_base_iut(tmp_path: Path) -> None:
    bundle = _build_bundle(tmp_path)
    report = json.loads(bundle["scoreReport"].read_text(encoding="utf-8"))
    report["primaryFixedIntersectionUnionTest"]["passed"] = False
    _rewrite_score_report(bundle, report)
    audited = _invoke(bundle)
    assert audited["domainNoninferiority"]["selectedScGate"][
        "additionalSelectedScGatePassed"
    ] is True
    assert audited["claimAuthorization"]["aggregateSuperiorityWithDomainNoHarmAuthorized"] is False
    assert audited["claimAuthorization"]["measuredCostMatchedScPrefixClaimAuthorized"] is False


@pytest.mark.parametrize(
    "raw, message",
    [
        (b'{"a":1,"a":2}\n', "duplicate JSON key"),
        (b'{"a":NaN}\n', "non-finite JSON constant"),
    ],
)
def test_json_loader_rejects_duplicate_keys_and_nonfinite_values(
    tmp_path: Path, raw: bytes, message: str
) -> None:
    path = tmp_path / "hostile.json"
    path.write_bytes(raw)
    with pytest.raises(audit.ConfirmationAuditError, match=message):
        audit._load_json(path, audit.sha256_file(path), label="hostile")


def test_git_chronology_requires_three_distinct_commits(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.json"
    artifact.write_text("{}\n", encoding="utf-8")
    with pytest.raises(audit.ConfirmationAuditError, match="must be distinct"):
        audit.verify_freeze_chronology(
            phase_a_commit="a" * 40,
            cost_evidence_path=artifact,
            expected_pre_gold_cost_git_commit="a" * 40,
            score_manifest_path=artifact,
            expected_score_freeze_git_commit="a" * 40,
        )
