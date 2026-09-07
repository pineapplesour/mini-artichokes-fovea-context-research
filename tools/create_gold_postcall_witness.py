#!/usr/bin/env python3
"""Create a hash-only Git witness after replaying one accepted gold shard.

This auxiliary never calls a model and is not part of label construction.  It
uses the production runner's no-call resume validation, then writes one
exclusive compact witness suitable for an append-only Git checkpoint.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import outcome_gold_audit as audit
from tools import run_outcome_gold_auditor as runner


PROTOCOL = "mini-artichokes-gold-postcall-witness-v2"


def create_witness(*, campaign_dir: Path, profile: str, shard_index: int) -> dict[str, Any]:
    campaign_dir = campaign_dir.resolve()
    profile = profile.upper()
    freeze, paths, packet_rows, _ = audit.verify_shard_bundle(
        campaign_dir, profile, shard_index
    )
    receipt = audit.load_json(paths["receipt"])
    audit.verify_self_hash(
        receipt, key="receiptSha256", location=str(paths["receipt"])
    )
    frozen = freeze.get("executionConfig")
    if not isinstance(frozen, dict):
        raise audit.GoldAuditError("accepted shard lacks frozen execution config")
    config = runner.execution_config(
        freeze,
        codex_home=Path(str(frozen["codexHome"])),
        model=str(frozen["model"]),
        reasoning_effort=str(frozen["reasoningEffort"]),
        verbosity=str(frozen["verbosity"]),
        service_tier=str(frozen["serviceTier"]),
        timeout_seconds=int(frozen["timeoutSeconds"]),
    )
    command = runner.build_command(
        input_dir=paths["inputDir"],
        output_dir=paths["outputDir"],
        codex_home=Path(str(frozen["codexHome"])),
        model=str(frozen["model"]),
        reasoning_effort=str(frozen["reasoningEffort"]),
        verbosity=str(frozen["verbosity"]),
    )
    cli_identity = audit.cli_identity_for_command(
        audit.tool_free_cli_base_identity(), command
    )
    pre_call = receipt.get("preCallGitAnchor")
    if not isinstance(pre_call, dict) or not isinstance(pre_call.get("commit"), str):
        raise audit.GoldAuditError("accepted shard lacks a pre-call Git commit")
    git_anchor = runner.verify_git_anchor(
        campaign_dir=campaign_dir,
        profile=profile,
        shard_index=shard_index,
        freeze=freeze,
        commit=pre_call["commit"],
    )
    replay = runner.verify_resume(
        paths=paths,
        freeze=freeze,
        packet_rows=packet_rows,
        config=config,
        command=command,
        cli_identity=cli_identity,
        git_anchor=git_anchor,
    )
    if replay.get("status") != "resumed_complete_without_model_call":
        raise audit.GoldAuditError("accepted shard did not pass no-call resume replay")
    artifacts = receipt.get("artifacts")
    if not isinstance(artifacts, dict):
        raise audit.GoldAuditError("accepted shard receipt lacks artifact hashes")
    witness = {
        "schemaVersion": 1,
        "protocol": PROTOCOL,
        "witnessBuilderSha256": audit.sha256_file(Path(__file__).resolve()),
        "campaign": campaign_dir.name,
        "profile": profile,
        "shardIndex": shard_index,
        "status": "accepted_replayed_without_model_call",
        "semanticModelInvocationsInAcceptedShard": 1,
        "semanticModelInvocationsDuringWitnessReplay": 0,
        "preCallAnchorCommit": git_anchor["commit"],
        "freezeSha256": freeze["freezeSha256"],
        "receiptSha256": receipt["receiptSha256"],
        "receiptFileSha256": audit.sha256_file(paths["receipt"]),
        "rawTraceSha256": artifacts["rawTraceSha256"],
        "attemptRegistrySha256": artifacts["attemptRegistrySha256"],
        "modelResponseSha256": artifacts["modelResponseSha256"],
        "judgmentsSha256": artifacts["judgmentsSha256"],
        "validationSha256": artifacts["validationSha256"],
        "threadIds": artifacts["threadIds"],
        "tokenUsage": receipt.get("tokenUsage"),
        "runFinishedUtc": receipt.get("runFinishedUtc"),
    }
    witness["witnessSha256"] = audit.self_hash(witness, key="witnessSha256")
    output_dir = campaign_dir / "postcall_witnesses"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{profile}-{shard_index:04d}-v2.json"
    audit.write_json_exclusive(output_path, witness)
    return {**witness, "path": str(output_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--profile", choices=("A", "B", "C"), required=True)
    parser.add_argument("--shard-index", type=int, required=True)
    args = parser.parse_args()
    result = create_witness(
        campaign_dir=args.campaign_dir,
        profile=args.profile,
        shard_index=args.shard_index,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
