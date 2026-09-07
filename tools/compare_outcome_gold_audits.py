#!/usr/bin/env python3
"""Gold-free A/B agreement analysis and blind C-packet construction.

This command has no argument for the private reserve and never opens it.  It
uses only the already label-free A/B packets, their accepted judgments, and
the precommitted C sample seed in ``source_freeze.json``.
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


def compare_and_prepare_c(*, campaign_dir: Path) -> dict[str, Any]:
    campaign_dir = campaign_dir.resolve()
    comparison_dir = campaign_dir / "comparison"
    c_dir = campaign_dir / audit.profile_name("C")
    if comparison_dir.exists() or c_dir.exists():
        raise audit.GoldAuditError(
            "refusing to overwrite an existing comparison or auditor-C stage"
        )
    source = audit.load_source_freeze(campaign_dir)
    current_hashes = audit.implementation_hashes()
    if source.get("implementationHashes") != current_hashes:
        raise audit.GoldAuditError(
            "audit implementation changed after source freeze; create a new campaign"
        )
    judgments_a, packets_a, evidence_a = audit.load_accepted_profile(campaign_dir, "A")
    judgments_b, packets_b, evidence_b = audit.load_accepted_profile(campaign_dir, "B")
    if set(judgments_a) != set(judgments_b):
        raise audit.GoldAuditError("A/B accepted ID sets differ")
    if len(judgments_a) != source.get("sourceRows"):
        raise audit.GoldAuditError("A/B accepted row count differs from source freeze")
    ids = sorted(judgments_a)
    for case_id in ids:
        if packets_a.get(case_id) != packets_b.get(case_id):
            raise audit.GoldAuditError(f"A/B blind source packet differs: {case_id}")

    categories_a = [audit.core_category(judgments_a[case_id]) for case_id in ids]
    categories_b = [audit.core_category(judgments_b[case_id]) for case_id in ids]
    agreements = [
        case_id
        for case_id in ids
        if audit.judgment_core(judgments_a[case_id])
        == audit.judgment_core(judgments_b[case_id])
    ]
    disagreements = [case_id for case_id in ids if case_id not in set(agreements)]
    sample_count = (len(agreements) + 9) // 10
    sample_seed = source.get("cSampleSeed")
    if not isinstance(sample_seed, str) or not sample_seed:
        raise audit.GoldAuditError("source freeze is missing the precommitted C sample seed")
    sampled_agreements = sorted(
        agreements, key=lambda case_id: (_sample_rank(sample_seed, case_id), case_id)
    )[:sample_count]
    selected = set(disagreements) | set(sampled_agreements)
    if not selected:
        raise audit.GoldAuditError("C packet would be empty")
    order_seed = source.get("orderSeed")
    if not isinstance(order_seed, str) or not order_seed:
        raise audit.GoldAuditError("source freeze is missing the order seed")
    c_ids = audit.deterministic_order(sorted(selected), profile="C", seed=order_seed)
    selection_rows = [
        {
            "id": case_id,
            "reason": "ab_disagreement" if case_id in set(disagreements) else "agreement_audit_sample",
            "agreementSampleRankSHA256": (
                _sample_rank(sample_seed, case_id)
                if case_id in set(sampled_agreements)
                else None
            ),
        }
        for case_id in c_ids
    ]

    c_model = source.get("executionProfiles", {}).get("C", {}).get("model")
    if not isinstance(c_model, str) or not c_model:
        raise audit.GoldAuditError("source freeze has no explicit C model")
    c_profile = audit.create_profile(
        campaign_dir=campaign_dir,
        profile="C",
        packet_by_id=packets_a,
        ordered_ids=c_ids,
        model=c_model,
        shard_size=int(source["shardSize"]),
        timeout_seconds=int(source["executionProfiles"]["C"]["timeoutSeconds"]),
        codex_home=Path(source["executionProfiles"]["C"]["codexHome"]),
        cli_base_identity=source["codexCliBaseIdentity"],
        pre_call_anchor_file="precall_anchor_c.json",
        source_freeze_sha256=str(source["freezeSha256"]),
        implementations=current_hashes,
    )
    comparison_dir.mkdir(parents=True, exist_ok=False)
    audit.write_jsonl_exclusive(comparison_dir / "c_selection.jsonl", selection_rows)
    report = {
        "schemaVersion": 1,
        "status": "ab_frozen_c_prepared_no_model_calls",
        "protocol": audit.COMPARISON_PROTOCOL,
        "privacyClassification": "PRIVATE_GOLD_CONTROL_NEVER_STAGE_TO_SOLVER",
        "semanticModelInvocations": 0,
        "sourceFreezeSha256": source["freezeSha256"],
        "rows": len(ids),
        "coreDefinition": "ordered pair (eligible, label); flags/rationale are explanatory only",
        "agreementRows": len(agreements),
        "disagreementRows": len(disagreements),
        "observedAgreement": len(agreements) / len(ids),
        "cohenKappa": audit.cohen_kappa(categories_a, categories_b),
        "categoryCountsA": dict(sorted(Counter(categories_a).items())),
        "categoryCountsB": dict(sorted(Counter(categories_b).items())),
        "cSelection": {
            "allDisagreements": True,
            "disagreementRows": len(disagreements),
            "agreementAuditFraction": 0.10,
            "agreementAuditCountRule": source["cAgreementAuditCountRule"],
            "agreementAuditRows": len(sampled_agreements),
            "selectedRows": len(c_ids),
            "selectionFile": "c_selection.jsonl",
            "selectionFileSha256": audit.sha256_file(comparison_dir / "c_selection.jsonl"),
            "selectedIdsSha256": audit.canonical_digest(c_ids),
            "sampleSeedSha256": source["cSampleSeedSha256"],
        },
        "acceptedProfileEvidence": {"A": evidence_a, "B": evidence_b},
        "cProfile": {
            "profileFreezeSha256": c_profile["freezeSha256"],
            "profileFreezeFileSha256": audit.sha256_file(
                c_dir / "profile_freeze.json"
            ),
            "model": c_model,
            "rows": c_profile["rows"],
            "shards": c_profile["shardCount"],
            "preCallAnchorFile": "precall_anchor_c.json",
        },
    }
    report["reportSha256"] = audit.self_hash(report, key="reportSha256")
    comparison_path = comparison_dir / "comparison.json"
    audit.write_json_exclusive(comparison_path, report)
    anchor = audit.build_pre_call_anchor(
        campaign_dir=campaign_dir,
        stage="C",
        profiles=("C",),
        file_name="precall_anchor_c.json",
        extra_file_bindings={"comparisonReport": comparison_path},
    )
    return {
        **report,
        "preCallAnchorFileSha256": audit.sha256_file(
            campaign_dir / "precall_anchor_c.json"
        ),
        "preCallAnchorSha256": anchor["anchorSha256"],
        "nextRequiredAction": "commit exact C pre-call anchor before C model calls",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare frozen A/B gold audits without reading provisional labels."
    )
    parser.add_argument("--campaign-dir", type=Path, required=True)
    args = parser.parse_args()
    result = compare_and_prepare_c(campaign_dir=args.campaign_dir)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
