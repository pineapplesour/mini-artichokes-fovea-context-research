#!/usr/bin/env python3
"""Private final consensus and provisional-parser comparison.

Unlike the gold-free A/B comparison, this command intentionally opens the
private reserve.  It can run only after accepted A, B, and C receipts are
present and hash-valid.  It does not read or score any solver output.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import outcome_gold_audit as audit


def _sample_rank(seed: str, case_id: str) -> str:
    return hashlib.sha256(f"{seed}\0{case_id}".encode("utf-8")).hexdigest()


def finalize(
    *,
    campaign_dir: Path,
    private_path: Path,
    manifest_path: Path,
    kappa_threshold: float | None = None,
) -> dict[str, Any]:
    campaign_dir = campaign_dir.resolve()
    if private_path.is_symlink() or not private_path.is_file():
        raise audit.GoldAuditError(
            f"private reserve must be a regular non-symlink file: {private_path}"
        )
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise audit.GoldAuditError(
            f"source manifest must be a regular non-symlink file: {manifest_path}"
        )
    private_path = private_path.resolve()
    manifest_path = manifest_path.resolve()
    final_dir = campaign_dir / "final"
    if final_dir.exists():
        raise audit.GoldAuditError("refusing to overwrite an existing final stage")
    source = audit.load_source_freeze(campaign_dir)
    frozen_kappa_threshold = source.get("minimumABKappa")
    if (
        not isinstance(frozen_kappa_threshold, (int, float))
        or isinstance(frozen_kappa_threshold, bool)
        or not 0.0 <= float(frozen_kappa_threshold) <= 1.0
    ):
        raise audit.GoldAuditError("source freeze has an invalid minimumABKappa")
    if kappa_threshold is not None and float(kappa_threshold) != float(
        frozen_kappa_threshold
    ):
        raise audit.GoldAuditError(
            "runtime kappa override is forbidden; use the pre-call frozen threshold"
        )
    kappa_threshold = float(frozen_kappa_threshold)
    current_hashes = audit.implementation_hashes()
    if source.get("implementationHashes") != current_hashes:
        raise audit.GoldAuditError(
            "audit implementation changed after source freeze; create a new campaign"
        )
    public_rows, private_rows, manifest, public_path = audit.validate_source_inventory(
        private_path=private_path, manifest_path=manifest_path
    )
    if source.get("sourcePrivateSha256") != audit.sha256_file(private_path):
        raise audit.GoldAuditError("private reserve does not match campaign source freeze")
    if source.get("sourceManifestFileSha256") != audit.sha256_file(manifest_path):
        raise audit.GoldAuditError("reserve manifest does not match campaign source freeze")
    if source.get("sourceManifestSelfHash") != manifest.get("selfHash"):
        raise audit.GoldAuditError("reserve manifest self-hash does not match source freeze")
    if source.get("sourcePublicSha256") != audit.sha256_file(public_path):
        raise audit.GoldAuditError("public reserve does not match campaign source freeze")

    comparison_path = campaign_dir / "comparison/comparison.json"
    selection_path = campaign_dir / "comparison/c_selection.jsonl"
    comparison = audit.load_json(comparison_path)
    if comparison.get("protocol") != audit.COMPARISON_PROTOCOL:
        raise audit.GoldAuditError("unsupported comparison protocol")
    if (
        comparison.get("status") != "ab_frozen_c_prepared_no_model_calls"
        or comparison.get("semanticModelInvocations") != 0
    ):
        raise audit.GoldAuditError("comparison stage is not the accepted gold-free stage")
    audit.verify_self_hash(
        comparison, key="reportSha256", location=str(comparison_path)
    )
    if comparison.get("sourceFreezeSha256") != source.get("freezeSha256"):
        raise audit.GoldAuditError("comparison/source freeze mismatch")
    if (
        comparison.get("cSelection", {}).get("selectionFileSha256")
        != audit.sha256_file(selection_path)
    ):
        raise audit.GoldAuditError("C selection file hash mismatch")

    judgments_a, packets_a, evidence_a = audit.load_accepted_profile(campaign_dir, "A")
    judgments_b, packets_b, evidence_b = audit.load_accepted_profile(campaign_dir, "B")
    judgments_c, packets_c, evidence_c = audit.load_accepted_profile(campaign_dir, "C")
    if comparison.get("acceptedProfileEvidence") != {"A": evidence_a, "B": evidence_b}:
        raise audit.GoldAuditError("accepted A/B evidence changed after comparison")
    if comparison.get("cProfile", {}).get("profileFreezeSha256") != evidence_c.get(
        "profileFreezeSha256"
    ):
        raise audit.GoldAuditError("accepted C profile differs from the prepared comparison stage")
    if comparison.get("cProfile", {}).get("profileFreezeFileSha256") != evidence_c.get(
        "profileFreezeFileSha256"
    ):
        raise audit.GoldAuditError("accepted C profile file changed after preparation")
    ids = sorted(judgments_a)
    if set(ids) != set(judgments_b) or len(ids) != source.get("sourceRows"):
        raise audit.GoldAuditError("A/B full ID sets are inconsistent")
    for case_id in ids:
        if packets_a.get(case_id) != packets_b.get(case_id):
            raise audit.GoldAuditError(f"A/B packet mismatch: {case_id}")

    agreements = [
        case_id
        for case_id in ids
        if audit.judgment_core(judgments_a[case_id])
        == audit.judgment_core(judgments_b[case_id])
    ]
    agreement_set = set(agreements)
    disagreements = [case_id for case_id in ids if case_id not in agreement_set]
    categories_a = [audit.core_category(judgments_a[case_id]) for case_id in ids]
    categories_b = [audit.core_category(judgments_b[case_id]) for case_id in ids]
    kappa = audit.cohen_kappa(categories_a, categories_b)
    if comparison.get("agreementRows") != len(agreements):
        raise audit.GoldAuditError("comparison agreement count is stale or tampered")
    if comparison.get("disagreementRows") != len(disagreements):
        raise audit.GoldAuditError("comparison disagreement count is stale or tampered")
    stored_kappa = comparison.get("cohenKappa")
    if (stored_kappa is None) != (kappa is None):
        raise audit.GoldAuditError("comparison kappa degeneracy is stale or tampered")
    if kappa is not None and (
        not isinstance(stored_kappa, (int, float))
        or isinstance(stored_kappa, bool)
        or abs(float(stored_kappa) - kappa) > 1e-12
    ):
        raise audit.GoldAuditError("comparison kappa is stale or tampered")

    selection_rows = audit.load_jsonl(selection_path)
    selection_ids: list[str] = []
    reasons: dict[str, str] = {}
    for index, row in enumerate(selection_rows):
        if set(row) != {"id", "reason", "agreementSampleRankSHA256"}:
            raise audit.GoldAuditError(f"C selection exact schema mismatch: row {index}")
        case_id = row.get("id")
        reason = row.get("reason")
        if not isinstance(case_id, str) or case_id in reasons:
            raise audit.GoldAuditError("C selection contains an invalid or duplicate ID")
        if reason not in {"ab_disagreement", "agreement_audit_sample"}:
            raise audit.GoldAuditError(f"invalid C selection reason: {case_id}")
        rank = row.get("agreementSampleRankSHA256")
        if reason == "agreement_audit_sample":
            if rank != _sample_rank(source["cSampleSeed"], case_id):
                raise audit.GoldAuditError(f"C agreement-sample rank mismatch: {case_id}")
        elif rank is not None:
            raise audit.GoldAuditError(f"C disagreement row must have null sample rank: {case_id}")
        selection_ids.append(case_id)
        reasons[case_id] = str(reason)
    sample_seed = source["cSampleSeed"]
    sample_count = (len(agreements) + 9) // 10
    expected_sample = sorted(
        agreements, key=lambda case_id: (_sample_rank(sample_seed, case_id), case_id)
    )[:sample_count]
    expected_selected = set(disagreements) | set(expected_sample)
    if set(selection_ids) != expected_selected:
        raise audit.GoldAuditError("C selection is not all disagreements plus committed 10% sample")
    if comparison.get("cSelection", {}).get("selectedRows") != len(selection_ids):
        raise audit.GoldAuditError("comparison C selected-row count mismatch")
    if comparison.get("cSelection", {}).get("selectedIdsSha256") != audit.canonical_digest(
        selection_ids
    ):
        raise audit.GoldAuditError("comparison C selected-ID/order digest mismatch")
    if set(judgments_c) != expected_selected or set(packets_c) != expected_selected:
        raise audit.GoldAuditError("accepted C judgments do not exactly cover the frozen selection")
    for case_id in expected_selected:
        if packets_c[case_id] != packets_a[case_id]:
            raise audit.GoldAuditError(f"C packet differs from blind A/B source: {case_id}")
        expected_reason = (
            "ab_disagreement" if case_id in set(disagreements) else "agreement_audit_sample"
        )
        if reasons.get(case_id) != expected_reason:
            raise audit.GoldAuditError(f"C selection reason mismatch: {case_id}")

    sample_errors = [
        case_id
        for case_id in expected_sample
        if audit.judgment_core(judgments_c[case_id])
        != audit.judgment_core(judgments_a[case_id])
    ]
    unresolved_disagreements = [
        case_id
        for case_id in disagreements
        if audit.judgment_core(judgments_c[case_id])
        not in {
            audit.judgment_core(judgments_a[case_id]),
            audit.judgment_core(judgments_b[case_id]),
        }
    ]
    source_by_id = {str(row["caseId"]): row for row in private_rows}
    if set(source_by_id) != set(ids):
        raise audit.GoldAuditError("private reserve IDs do not match A/B audit IDs")

    consensus_rows: list[dict[str, Any]] = []
    for case_id in sorted(ids):
        ab_agreement = case_id in agreement_set
        source_judgment = judgments_a[case_id] if ab_agreement else judgments_c[case_id]
        eligible, label = audit.judgment_core(source_judgment)
        provisional = str(source_by_id[case_id]["label"])
        parser_match = eligible and label == provisional
        source_row = source_by_id[case_id]
        consensus_rows.append(
            {
                "id": case_id,
                "domain": source_row["domain"],
                "abAgreement": ab_agreement,
                "resolutionSource": "AB" if ab_agreement else "C",
                "eligible": eligible,
                "label": label,
                "provisionalLabel": provisional,
                "parserMatch": parser_match,
                "selectionRankSHA256": source_row["selectionRankSHA256"],
                "auditedBinaryEligible": eligible and label in audit.PROVISIONAL_LABELS,
            }
        )

    pools: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for domain in ("civil", "tax"):
        for label in audit.PROVISIONAL_LABELS:
            pools[(domain, label)] = sorted(
                [
                    row
                    for row in consensus_rows
                    if row["auditedBinaryEligible"]
                    and row["domain"] == domain
                    and row["label"] == label
                ],
                key=lambda row: (row["selectionRankSHA256"], row["id"]),
            )
    size_rule = source.get("selectionSizeRule")
    if not isinstance(size_rule, dict):
        raise audit.GoldAuditError("source freeze is missing the selection-size rule")
    per_label_sizes: dict[str, int] = {}
    selection_minimums_met: dict[str, bool] = {}
    for domain in ("civil", "tax"):
        rule = size_rule.get(domain)
        if not isinstance(rule, dict):
            raise audit.GoldAuditError(f"selection-size rule is missing domain {domain}")
        cap = rule.get("capPerAuditedLabel")
        minimum = rule.get("minimumPerAuditedLabel")
        if (
            not isinstance(cap, int)
            or isinstance(cap, bool)
            or not isinstance(minimum, int)
            or isinstance(minimum, bool)
            or cap < minimum
            or minimum <= 0
        ):
            raise audit.GoldAuditError(f"selection-size rule is invalid for {domain}")
        cell_minimum = min(len(pools[(domain, label)]) for label in audit.PROVISIONAL_LABELS)
        per_label_sizes[domain] = min(cap, cell_minimum)
        selection_minimums_met[domain] = per_label_sizes[domain] >= minimum

    selected_ids: set[str] = set()
    for domain in ("civil", "tax"):
        for label in audit.PROVISIONAL_LABELS:
            selected_ids.update(
                row["id"] for row in pools[(domain, label)][: per_label_sizes[domain]]
            )
    gates = {
        "abKappaDefined": kappa is not None,
        "abKappaAtLeastFrozenThreshold": (
            kappa is not None and kappa >= kappa_threshold
        ),
        "cResolvesAllDisagreements": not unresolved_disagreements,
        "cAgreementAuditZeroErrors": not sample_errors,
        "civilAuditedLabelMinimumMet": selection_minimums_met["civil"],
        "taxAuditedLabelMinimumMet": selection_minimums_met["tax"],
        "finalConsensusComplete": len(consensus_rows) == len(ids),
    }
    accepted_stage = all(gates.values())
    for row in consensus_rows:
        row["candidateAccepted"] = accepted_stage and row["id"] in selected_ids
    accepted_rows = sum(row["candidateAccepted"] for row in consensus_rows)
    if audit.sha256_file(private_path) != source["sourcePrivateSha256"]:
        raise audit.GoldAuditError("private reserve changed during final consensus")
    if audit.sha256_file(manifest_path) != source["sourceManifestFileSha256"]:
        raise audit.GoldAuditError("source manifest changed during final consensus")
    if audit.sha256_file(public_path) != source["sourcePublicSha256"]:
        raise audit.GoldAuditError("public reserve changed during final consensus")
    final_dir.mkdir(parents=True, exist_ok=False)
    consensus_path = final_dir / "private_consensus.jsonl"
    audit.write_jsonl_exclusive(consensus_path, consensus_rows)
    eligible_rows = [row for row in consensus_rows if row["eligible"]]
    eligible_parser_matches = sum(row["parserMatch"] for row in eligible_rows)
    full_parser_matches = sum(row["parserMatch"] for row in consensus_rows)
    bootstrap = source.get("bootstrap")
    if not isinstance(bootstrap, dict):
        raise audit.GoldAuditError("source freeze is missing bootstrap configuration")
    bootstrap_replicates = int(bootstrap["replicates"])
    overall_kappa_ci = audit.deterministic_kappa_bootstrap_ci(
        categories_a,
        categories_b,
        seed=f"{source['cSampleSeed']}\0overall",
        replicates=bootstrap_replicates,
        confidence_level=float(bootstrap["confidenceLevel"]),
    )
    domain_agreement: dict[str, Any] = {}
    for domain in ("civil", "tax"):
        domain_ids = [case_id for case_id in ids if source_by_id[case_id]["domain"] == domain]
        domain_a = [audit.core_category(judgments_a[case_id]) for case_id in domain_ids]
        domain_b = [audit.core_category(judgments_b[case_id]) for case_id in domain_ids]
        domain_agreement[domain] = {
            "rows": len(domain_ids),
            "agreementRows": sum(a == b for a, b in zip(domain_a, domain_b, strict=True)),
            "cohenKappa": audit.cohen_kappa(domain_a, domain_b),
            "cohenKappaBootstrapCI": audit.deterministic_kappa_bootstrap_ci(
                domain_a,
                domain_b,
                seed=f"{source['cSampleSeed']}\0{domain}",
                replicates=bootstrap_replicates,
                confidence_level=float(bootstrap["confidenceLevel"]),
            ),
        }
    audited_cell_counts = {
        domain: {label: len(pools[(domain, label)]) for label in audit.PROVISIONAL_LABELS}
        for domain in ("civil", "tax")
    }
    selected_cell_counts = {
        domain: {
            label: sum(
                row["candidateAccepted"]
                and row["domain"] == domain
                and row["label"] == label
                for row in consensus_rows
            )
            for label in audit.PROVISIONAL_LABELS
        }
        for domain in ("civil", "tax")
    }
    agreement_audit_by_cell: dict[str, dict[str, Any]] = {}
    sample_error_set = set(sample_errors)
    expected_sample_set = set(expected_sample)
    for domain in ("civil", "tax"):
        agreement_audit_by_cell[domain] = {}
        for label in audit.LABELS:
            population_ids = [
                case_id
                for case_id in agreements
                if source_by_id[case_id]["domain"] == domain
                and audit.judgment_core(judgments_a[case_id])[1] == label
            ]
            sampled_ids = [
                case_id for case_id in population_ids if case_id in expected_sample_set
            ]
            error_ids = [case_id for case_id in sampled_ids if case_id in sample_error_set]
            agreement_audit_by_cell[domain][label] = {
                "agreementPopulationRows": len(population_ids),
                "sampledRows": len(sampled_ids),
                "coverage": (
                    len(sampled_ids) / len(population_ids) if population_ids else None
                ),
                "errorRows": len(error_ids),
                "errorIds": error_ids,
                "sampleWasGloballyHashedNotCellQuotaStratified": True,
            }
    report = {
        "schemaVersion": 1,
        "status": "accepted" if accepted_stage else "rejected",
        "protocol": audit.FINAL_PROTOCOL,
        "privacyClassification": "PRIVATE_GOLD_NEVER_STAGE_TO_SOLVER",
        "semanticModelInvocations": 0,
        "sourceFreezeSha256": source["freezeSha256"],
        "sourcePrivateSha256": audit.sha256_file(private_path),
        "sourcePublicSha256": audit.sha256_file(public_path),
        "sourceManifestFileSha256": audit.sha256_file(manifest_path),
        "comparisonReportSha256": comparison["reportSha256"],
        "comparisonFileSha256": audit.sha256_file(comparison_path),
        "selectionFileSha256": audit.sha256_file(selection_path),
        "thresholds": {"minimumABKappa": kappa_threshold},
        "gates": gates,
        "rows": len(ids),
        "abAgreementRows": len(agreements),
        "abDisagreementRows": len(disagreements),
        "abCohenKappa": kappa,
        "abCohenKappaBootstrapCI": overall_kappa_ci,
        "domainAgreement": domain_agreement,
        "cAgreementAuditRows": len(expected_sample),
        "cAgreementAuditErrorRows": len(sample_errors),
        "cAgreementAuditErrorIds": sample_errors,
        "cAgreementAuditDomainByAuditedLabel": agreement_audit_by_cell,
        "cUnresolvedDisagreementRows": len(unresolved_disagreements),
        "cUnresolvedDisagreementIds": unresolved_disagreements,
        "finalLabelCounts": dict(
            sorted(Counter(str(row["label"]) for row in consensus_rows).items())
        ),
        "eligibleConsensusRows": len(eligible_rows),
        "parserAgreementFullInventory": {
            "denominator": len(consensus_rows),
            "matches": full_parser_matches,
            "mismatches": len(consensus_rows) - full_parser_matches,
            "agreement": full_parser_matches / len(consensus_rows),
            "ineligibleConsensusRowsCountAsMismatches": True,
        },
        "parserAgreementEligibleConditional": {
            "denominator": len(eligible_rows),
            "matches": eligible_parser_matches,
            "mismatches": len(eligible_rows) - eligible_parser_matches,
            "agreement": (
                eligible_parser_matches / len(eligible_rows) if eligible_rows else None
            ),
        },
        "auditedCellCounts": audited_cell_counts,
        "selectionSizeRule": size_rule,
        "selectedPerAuditedLabel": per_label_sizes,
        "selectedCellCounts": selected_cell_counts,
        "acceptedCandidateRows": accepted_rows,
        "consensusPath": "private_consensus.jsonl",
        "consensusSha256": audit.sha256_file(consensus_path),
        "acceptedProfileEvidence": {
            "A": evidence_a,
            "B": evidence_b,
            "C": evidence_c,
        },
        "implementationHashes": current_hashes,
        "note": "No solver output was opened or scored by this command.",
    }
    report["reportSha256"] = audit.self_hash(report, key="reportSha256")
    audit.write_json_exclusive(final_dir / "final_report.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Privately finalize A/B/C gold consensus against provisional parser labels."
    )
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--private-jsonl", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    result = finalize(
        campaign_dir=args.campaign_dir,
        private_path=args.private_jsonl,
        manifest_path=args.manifest,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("status") == "accepted" else 1


if __name__ == "__main__":
    raise SystemExit(main())
