from tools.audit_selector_ablation import audit_selector_ablation_report


def _arm(
    mode: str,
    *,
    candidate_digest: str = "sha256:candidates",
    provider: str = "fixture_provider",
    model: str = "fixture-model",
    decoding: dict | None = None,
    selected_count: int = 1,
    target_pass: bool | None = None,
    target_ids: list[str] | None = None,
    covered_target_ids: list[str] | None = None,
    context_packet_count: int = 0,
    context_packet_provenance_count: int = 0,
    writer_ran: bool = False,
):
    arm = {
        "selectorInputMode": mode,
        "candidateSetDigest": candidate_digest,
        "selectorProvider": provider,
        "selectorModel": model,
        "selectorDecoding": decoding or {},
        "selectorFallback": False,
        "writerRan": writer_ran,
        "selectedEvidenceCount": selected_count,
        "selectedBackingEvidenceIds": ["doc-target"] if selected_count else [],
    }
    if mode == "context_packets_v1":
        arm.update(
            {
                "contextPacketCount": context_packet_count,
                "contextPacketProvenanceCount": context_packet_provenance_count,
            }
        )
    if target_pass is not None:
        target_ids_value = target_ids or ["target:doc-target"]
        covered_value = covered_target_ids if covered_target_ids is not None else (target_ids_value if target_pass else [])
        arm["targetEval"] = {
            "targetSpecPresent": True,
            "targetHitSource": "selected_backing_evidence_only",
            "pass": target_pass,
            "score": 1.0 if target_pass else 0.0,
            "targetIds": target_ids_value,
            "coveredTargetIds": covered_value,
            "missedTargetIds": [target_id for target_id in target_ids_value if target_id not in covered_value],
            "targetsTotal": len(target_ids_value),
            "targetsPassed": len(covered_value),
        }
    return arm


def _strict_promotion_suite() -> dict:
    return {
        "targetManifestLocked": True,
        "targetsVisibleToEngine": False,
    }


def test_selector_ablation_rejects_duplicate_arm_modes():
    report = {
        "schemaVersion": "selector_ablation_v1",
        "ablationId": "raw_vs_context_packets_v1",
        "arms": ["raw", "raw"],
        "cases": [],
    }

    audit = audit_selector_ablation_report(report)

    assert audit["ablationReportValid"] is False
    assert "selector_ablation_arms_not_distinct" in audit["reportBlockers"]


def test_selector_ablation_requires_context_packet_artifact_count_and_provenance():
    report = {
        "schemaVersion": "selector_ablation_v1",
        "ablationId": "raw_vs_context_packets_v1",
        "arms": ["raw", "context_packets_v1"],
        "cases": [
            {
                "caseId": "case-a",
                "arms": {
                    "raw": _arm("raw"),
                    "context_packets_v1": _arm(
                        "context_packets_v1",
                        context_packet_count=0,
                        context_packet_provenance_count=0,
                    ),
                },
            }
        ],
    }

    audit = audit_selector_ablation_report(report)

    assert audit["ablationReportValid"] is False
    assert "context_packet_arm_zero_packets" in audit["reportBlockers"]
    assert "context_packet_arm_missing_provenance" in audit["reportBlockers"]


def test_selector_ablation_reports_target_improvement_and_regression_without_writer_scores():
    report = {
        "schemaVersion": "selector_ablation_v1",
        "ablationId": "raw_vs_context_packets_v1",
        "arms": ["raw", "context_packets_v1"],
        "cases": [
            {
                "caseId": "context-better",
                "arms": {
                    "raw": _arm("raw", target_pass=False),
                    "context_packets_v1": _arm(
                        "context_packets_v1",
                        target_pass=True,
                        context_packet_count=2,
                        context_packet_provenance_count=2,
                    ),
                },
            },
            {
                "caseId": "context-worse",
                "arms": {
                    "raw": _arm("raw", target_pass=True),
                    "context_packets_v1": _arm(
                        "context_packets_v1",
                        target_pass=False,
                        context_packet_count=2,
                        context_packet_provenance_count=2,
                    ),
                },
            },
        ],
    }

    audit = audit_selector_ablation_report(report)

    assert audit["ablationReportValid"] is True
    assert audit["aggregate"]["targetComparison"]["contextTargetImprovementCount"] == 1
    assert audit["aggregate"]["targetComparison"]["contextTargetRegressionCount"] == 1
    assert audit["contextPacketRetrievalImprovementClaimable"] is False
    assert "context_target_regression_present" in audit["improvementClaimBlockers"]


def test_selector_ablation_promotes_strict_private_target_dominance():
    report = {
        "schemaVersion": "selector_ablation_v1",
        "ablationId": "raw_vs_context_packets_v1",
        "suite": _strict_promotion_suite(),
        "arms": ["raw", "context_packets_v1"],
        "cases": [
            {
                "caseId": "tie",
                "arms": {
                    "raw": _arm("raw", target_pass=True, target_ids=["target:a"], covered_target_ids=["target:a"]),
                    "context_packets_v1": _arm(
                        "context_packets_v1",
                        target_pass=True,
                        target_ids=["target:a"],
                        covered_target_ids=["target:a"],
                        context_packet_count=2,
                        context_packet_provenance_count=2,
                    ),
                },
            },
            {
                "caseId": "context-only",
                "arms": {
                    "raw": _arm("raw", target_pass=False, target_ids=["target:b"], covered_target_ids=[]),
                    "context_packets_v1": _arm(
                        "context_packets_v1",
                        target_pass=True,
                        target_ids=["target:b"],
                        covered_target_ids=["target:b"],
                        context_packet_count=2,
                        context_packet_provenance_count=2,
                    ),
                },
            },
        ],
    }

    audit = audit_selector_ablation_report(report)

    assert audit["ablationReportValid"] is True
    assert audit["contextPacketRetrievalImprovementClaimable"] is True
    assert audit["improvementClaimBlockers"] == []
    assert audit["aggregate"]["targetEval"]["pairedDelta"]["contextOnlyTargetCount"] == 1
    assert audit["aggregate"]["targetEval"]["pairedDelta"]["rawOnlyTargetCount"] == 0
    assert audit["aggregate"]["targetEval"]["pairedDelta"]["strictTargetDominance"] is True


def test_selector_ablation_keeps_valid_report_nonclaimable_without_private_targets():
    report = {
        "schemaVersion": "selector_ablation_v1",
        "ablationId": "raw_vs_context_packets_v1",
        "suite": _strict_promotion_suite(),
        "arms": ["raw", "context_packets_v1"],
        "cases": [
            {
                "caseId": "not-targeted",
                "arms": {
                    "raw": _arm("raw"),
                    "context_packets_v1": _arm(
                        "context_packets_v1",
                        context_packet_count=2,
                        context_packet_provenance_count=2,
                    ),
                },
            }
        ],
    }

    audit = audit_selector_ablation_report(report)

    assert audit["ablationReportValid"] is True
    assert audit["contextPacketRetrievalImprovementClaimable"] is False
    assert "private_retrieval_targets_absent" in audit["improvementClaimBlockers"]
    assert "report_only_initial_gate" not in audit["improvementClaimBlockers"]


def test_selector_ablation_blocks_promotion_when_context_loses_raw_target():
    report = {
        "schemaVersion": "selector_ablation_v1",
        "ablationId": "raw_vs_context_packets_v1",
        "suite": _strict_promotion_suite(),
        "arms": ["raw", "context_packets_v1"],
        "cases": [
            {
                "caseId": "regression",
                "arms": {
                    "raw": _arm("raw", target_pass=True, target_ids=["target:a"], covered_target_ids=["target:a"]),
                    "context_packets_v1": _arm(
                        "context_packets_v1",
                        target_pass=False,
                        target_ids=["target:a"],
                        covered_target_ids=[],
                        context_packet_count=2,
                        context_packet_provenance_count=2,
                    ),
                },
            }
        ],
    }

    audit = audit_selector_ablation_report(report)

    assert audit["ablationReportValid"] is True
    assert audit["contextPacketRetrievalImprovementClaimable"] is False
    assert "raw_only_targets_lost_by_context_packets" in audit["improvementClaimBlockers"]
    assert "context_target_regression_present" in audit["improvementClaimBlockers"]


def test_selector_ablation_blocks_promotion_when_target_metric_is_saturated():
    report = {
        "schemaVersion": "selector_ablation_v1",
        "ablationId": "raw_vs_context_packets_v1",
        "suite": _strict_promotion_suite(),
        "arms": ["raw", "context_packets_v1"],
        "cases": [
            {
                "caseId": "tie",
                "arms": {
                    "raw": _arm("raw", target_pass=True, target_ids=["target:a"], covered_target_ids=["target:a"]),
                    "context_packets_v1": _arm(
                        "context_packets_v1",
                        target_pass=True,
                        target_ids=["target:a"],
                        covered_target_ids=["target:a"],
                        context_packet_count=2,
                        context_packet_provenance_count=2,
                    ),
                },
            }
        ],
    }

    audit = audit_selector_ablation_report(report)

    assert audit["ablationReportValid"] is True
    assert audit["contextPacketRetrievalImprovementClaimable"] is False
    assert "target_metric_saturated_no_strict_improvement" in audit["improvementClaimBlockers"]
