#!/usr/bin/env python3
"""Freeze five deterministic 20-case blocks from the sealed 619-case gate."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


DEFAULT_SEED = "mini-artichokes-choice-hidden-5x20-v1-20260902"
PROTOCOL = "choice_hidden_5x20_v1"
BLOCK_SPECS = (
    (
        "tcm",
        "open_response.tcm.kuksiwon81.unique92.v2",
        "open_response_tcm_kuksiwon81_unique92.public.json",
    ),
    (
        "christian_bible",
        "open_response.christian.bible100.v2",
        "open_response_christian_bible100.public.json",
    ),
    (
        "christian_provao",
        "open_response.christian.provao2012.v2",
        "open_response_christian_provao2012.public.json",
    ),
    (
        "islamic_finance",
        "open_response.islam.cisi100.v2",
        "open_response_islam_cisi100.public.json",
    ),
    (
        "psychology",
        "open_response.psych.mit_sangmyung.v2",
        "open_response_psych_mit_sangmyung.public.json",
    ),
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return sha256_bytes(payload)


def selection_rank(seed: str, benchmark_id: str, case_id: str) -> str:
    material = f"{seed}\0{benchmark_id}\0{case_id}".encode("utf-8")
    return sha256_bytes(material)


def select_case_ids(
    seed: str, benchmark_id: str, case_ids: list[str], count: int = 20
) -> list[dict[str, str]]:
    if len(case_ids) < count:
        raise ValueError(f"{benchmark_id} has only {len(case_ids)} eligible cases")
    ranked = [
        {
            "id": case_id,
            "selectionRankSha256": selection_rank(seed, benchmark_id, case_id),
        }
        for case_id in case_ids
    ]
    ranked.sort(key=lambda row: (row["selectionRankSha256"], row["id"]))
    return ranked[:count]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def freeze(source_root: Path, output_dir: Path, seed: str) -> dict[str, Any]:
    combined = source_root / "runs/luna-pilot/semantic-rewrite-all-v1/combined"
    aggregate_path = (
        source_root
        / "runs/luna-pilot/plain-no-db-full-v2/scores/aggregate.json"
    )
    aggregate = json.loads(aggregate_path.read_text(encoding="utf-8"))

    freeze_blocks: list[dict[str, Any]] = []
    historical_blocks: list[dict[str, Any]] = []
    public_payload_hashes: list[str] = []
    totals = {"pass": 0, "fail": 0, "unresolved": 0}

    for block_index, (block_name, benchmark_id, manifest_name) in enumerate(
        BLOCK_SPECS, start=1
    ):
        public_manifest_path = combined / manifest_name
        public_manifest = json.loads(public_manifest_path.read_text(encoding="utf-8"))
        public_by_id = {case["id"]: case for case in public_manifest["cases"]}
        scored_cases = aggregate["byBenchmark"][benchmark_id]["cases"]
        verdict_by_id = {case["caseId"]: case["verdict"] for case in scored_cases}
        selected = select_case_ids(seed, benchmark_id, list(verdict_by_id))

        public_cases = []
        historical_cases = []
        counts = {"pass": 0, "fail": 0, "unresolved": 0}
        for selected_case in selected:
            case_id = selected_case["id"]
            if case_id not in public_by_id:
                raise ValueError(f"sealed case missing from public manifest: {case_id}")
            source_case = public_by_id[case_id]
            public_cases.append({"id": case_id, "prompt": source_case["prompt"]})
            verdict = verdict_by_id[case_id]
            counts[verdict] += 1
            totals[verdict] += 1
            historical_cases.append(
                {
                    "id": case_id,
                    "verdict": verdict,
                    "selectionRankSha256": selected_case["selectionRankSha256"],
                }
            )

        block_id = f"block_{block_index:02d}_{block_name}"
        public_payload = {
            "schemaVersion": 1,
            "protocol": PROTOCOL,
            "seed": seed,
            "blockId": block_id,
            "benchmarkId": benchmark_id,
            "caseCount": 20,
            "cases": public_cases,
        }
        public_path = output_dir / "public" / f"{block_id}.json"
        write_json(public_path, public_payload)
        public_sha256 = sha256_file(public_path)
        public_payload_hashes.append(public_sha256)
        selected_ids = [case["id"] for case in selected]
        freeze_blocks.append(
            {
                "blockId": block_id,
                "benchmarkId": benchmark_id,
                "sourcePublicManifest": str(public_manifest_path),
                "sourcePublicManifestSha256": sha256_file(public_manifest_path),
                "selectedIds": selected_ids,
                "selectedIdsCanonicalSha256": canonical_sha256(selected_ids),
                "publicPayload": str(public_path),
                "publicPayloadSha256": public_sha256,
            }
        )
        historical_blocks.append(
            {
                "blockId": block_id,
                "benchmarkId": benchmark_id,
                "counts": counts,
                "cases": historical_cases,
            }
        )

    selection_freeze = {
        "schemaVersion": 1,
        "status": "frozen_before_candidate_calls",
        "protocol": PROTOCOL,
        "seed": seed,
        "selectionMethod": "sort SHA256(seed + NUL + benchmarkId + NUL + caseId), take first 20",
        "sourceGateCases": aggregate["total"],
        "blockCount": len(freeze_blocks),
        "casesPerBlock": 20,
        "totalCases": sum(len(block["selectedIds"]) for block in freeze_blocks),
        "blocks": freeze_blocks,
        "combinedPublicPayloadHashesCanonicalSha256": canonical_sha256(
            public_payload_hashes
        ),
    }
    historical_score = {
        "schemaVersion": 1,
        "status": "historical_baseline_not_solver_input",
        "protocol": PROTOCOL,
        "arm": "plain_codex_luna_no_db_20260721",
        "sourceAggregate": str(aggregate_path),
        "sourceAggregateSha256": sha256_file(aggregate_path),
        "sourceFreezeId": aggregate["freezeId"],
        "totalCases": 100,
        "counts": totals,
        "passRate": totals["pass"] / 100,
        "blocks": historical_blocks,
    }
    write_json(output_dir / "selection_freeze.json", selection_freeze)
    write_json(output_dir / "historical_plain_luna_score.json", historical_score)
    return {
        "status": "frozen",
        "seed": seed,
        "blocks": len(freeze_blocks),
        "cases": 100,
        "plainLunaHistorical": totals,
        "plainLunaPassRate": totals["pass"] / 100,
        "selectionFreezeSha256": sha256_file(output_dir / "selection_freeze.json"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", default=DEFAULT_SEED)
    args = parser.parse_args()
    print(
        json.dumps(
            freeze(args.source_root.resolve(), args.output_dir.resolve(), args.seed),
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
