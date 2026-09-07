#!/usr/bin/env python3
"""Freeze five deterministic 20-case visible-options MCQ blocks."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


DEFAULT_SEED = "mini-artichokes-visible-options-5x20-v1-20260902"
PROTOCOL = "visible_options_5x20_v1"
BLOCK_SPECS = (
    (
        "leet",
        "benchmarks/unified/mcq_lawkey_leet2026_70.public.json",
        "benchmarks/unified/mcq_lawkey_leet2026_70.private.json",
    ),
    (
        "tcm",
        "benchmarks/unified/mcq_tcm_kuksiwon81_unique92.public.json",
        "benchmarks/unified/mcq_tcm_kuksiwon81_unique92.private.json",
    ),
    (
        "christian_provao",
        "benchmarks/unified/mcq_christian_provao2012.public.json",
        "benchmarks/unified/mcq_christian_provao2012.private.json",
    ),
    (
        "islamic_finance",
        "benchmarks/unified/mcq_islam_cisi100.public.json",
        "benchmarks/unified/mcq_islam_cisi100.private.json",
    ),
    (
        "psychology",
        "benchmarks/unified/mcq_psych_mit_sangmyung.public.json",
        "benchmarks/unified/mcq_psych_mit_sangmyung.private.json",
    ),
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_digest(value: Any) -> str:
    return sha256_bytes(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    )


def rank(seed: str, benchmark_id: str, case_id: str) -> str:
    return sha256_bytes(f"{seed}\0{benchmark_id}\0{case_id}".encode("utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def freeze(source_root: Path, output_dir: Path, seed: str) -> dict[str, Any]:
    blocks: list[dict[str, Any]] = []
    private_blocks: list[dict[str, Any]] = []
    all_ids: list[str] = []
    for index, (name, public_relative, private_relative) in enumerate(
        BLOCK_SPECS, start=1
    ):
        public_path = source_root / public_relative
        private_path = source_root / private_relative
        public = json.loads(public_path.read_text(encoding="utf-8"))
        private = json.loads(private_path.read_text(encoding="utf-8"))
        benchmark_id = str(public["benchmarkId"])
        public_by_id = {row["id"]: row for row in public["cases"]}
        answer_by_id = {row["caseId"]: row for row in private["answers"]}
        if set(public_by_id) != set(answer_by_id):
            raise ValueError(f"public/private case mismatch: {benchmark_id}")
        if any(
            not isinstance(answer.get("caseId"), str)
            or not answer["caseId"]
            or not isinstance(answer.get("correctOptionId"), str)
            or not answer["correctOptionId"]
            for answer in answer_by_id.values()
        ):
            raise ValueError(f"benchmark is not single-answer MCQ only: {benchmark_id}")

        selected = sorted(
            (
                {
                    "id": case_id,
                    "selectionRankSha256": rank(seed, benchmark_id, case_id),
                }
                for case_id in public_by_id
            ),
            key=lambda row: (row["selectionRankSha256"], row["id"]),
        )[:20]
        if len(selected) != 20:
            raise ValueError(f"not enough cases: {benchmark_id}")
        block_id = f"block_{index:02d}_{name}"
        public_payload = {
            "schemaVersion": 1,
            "protocol": PROTOCOL,
            "seed": seed,
            "blockId": block_id,
            "benchmarkId": benchmark_id,
            "caseCount": 20,
            "cases": [
                {"id": row["id"], "prompt": public_by_id[row["id"]]["prompt"]}
                for row in selected
            ],
        }
        private_payload = {
            "schemaVersion": 1,
            "status": "private_not_solver_input",
            "protocol": PROTOCOL,
            "blockId": block_id,
            "benchmarkId": benchmark_id,
            "answers": [
                {
                    "caseId": row["id"],
                    "correctOptionId": answer_by_id[row["id"]]["correctOptionId"],
                }
                for row in selected
            ],
        }
        public_output = output_dir / "public" / f"{block_id}.json"
        private_output = output_dir / "private" / f"{block_id}.json"
        write_json(public_output, public_payload)
        write_json(private_output, private_payload)
        ids = [row["id"] for row in selected]
        all_ids.extend(ids)
        blocks.append(
            {
                "blockId": block_id,
                "benchmarkId": benchmark_id,
                "sourcePublicManifest": str(public_path.resolve()),
                "sourcePublicManifestSha256": sha256_file(public_path),
                "sourcePrivateManifestSha256": sha256_file(private_path),
                "selectedIds": ids,
                "selectedIdsCanonicalSha256": canonical_digest(ids),
                "publicPayload": str(public_output.resolve()),
                "publicPayloadSha256": sha256_file(public_output),
                "privateKeyPayloadSha256": sha256_file(private_output),
            }
        )
        private_blocks.append(
            {
                "blockId": block_id,
                "privateKeyPayload": str(private_output.resolve()),
                "privateKeyPayloadSha256": sha256_file(private_output),
            }
        )
    if len(all_ids) != len(set(all_ids)):
        raise ValueError("selected case IDs overlap across blocks")
    selection = {
        "schemaVersion": 1,
        "status": "frozen_before_solver_calls",
        "protocol": PROTOCOL,
        "seed": seed,
        "selectionMethod": "sort SHA256(seed + NUL + benchmarkId + NUL + caseId), take first 20",
        "blockCount": 5,
        "casesPerBlock": 20,
        "totalCases": 100,
        "blocks": blocks,
        "allSelectedIdsCanonicalSha256": canonical_digest(all_ids),
    }
    private_index = {
        "schemaVersion": 1,
        "status": "private_not_solver_input",
        "protocol": PROTOCOL,
        "blocks": private_blocks,
    }
    write_json(output_dir / "selection_freeze.json", selection)
    write_json(output_dir / "private_key_index.json", private_index)
    return {
        "status": "frozen",
        "seed": seed,
        "blocks": 5,
        "cases": 100,
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
