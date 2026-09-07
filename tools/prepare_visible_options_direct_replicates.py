#!/usr/bin/env python3
"""Prepare two fresh matched direct-Luna replicates for the visible 5x20 set."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER = REPO_ROOT / "tools/run_plain_codex_file_agent.py"
ARMS = ("direct_d2", "direct_d3")


INSTRUCTIONS = """# Independent direct Luna visible-options MCQ replicate

Answer all 20 questions in `input/questions.jsonl` independently from your
own knowledge. Select exactly one of the option IDs printed in each prompt.
This is a fresh direct replicate; no other solver answer is present or
available. No answer key, database, web search, external model, agent, skill,
memory, or historical benchmark result is available or permitted. Local file
operations may be used only to read input, write output, and validate it.

Write exactly 20 UTF-8 JSONL rows to `output/answers.jsonl`, preserving input
order. Every row must contain exactly these keys:

`{"id":"exact input id","finalAnswer":"numeric option ID only"}`

Use `"1"` through `"5"`, not a circled numeral, option text, or explanation.
Answer every ID exactly once. Validate JSON, row count, IDs, key sets, order,
and that every answer is one numeric option ID present in its prompt.
"""


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


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def write_json(path: Path, value: Any) -> None:
    write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    write_text(
        path,
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
    )


def prepare(
    *,
    selection_dir: Path,
    campaign_root: Path,
    model: str,
    reasoning_effort: str,
    verbosity: str,
) -> dict[str, Any]:
    selection_path = selection_dir / "selection_freeze.json"
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    if selection.get("status") != "frozen_before_solver_calls":
        raise ValueError("selection is not frozen before solver calls")
    if selection.get("blockCount") != 5 or selection.get("casesPerBlock") != 20:
        raise ValueError("expected an exact 5x20 selection freeze")

    campaigns: list[dict[str, Any]] = []
    for arm in ARMS:
        for block in selection["blocks"]:
            block_id = str(block["blockId"])
            public_path = Path(str(block["publicPayload"]))
            if sha256_file(public_path) != block["publicPayloadSha256"]:
                raise ValueError(f"public block hash mismatch: {block_id}")
            public = json.loads(public_path.read_text(encoding="utf-8"))
            if public.get("caseCount") != 20 or len(public.get("cases") or []) != 20:
                raise ValueError(f"public block is not 20 cases: {block_id}")

            campaign_dir = campaign_root / arm / block_id
            role_dir = campaign_dir / "solver"
            input_dir = role_dir / "input"
            output_dir = role_dir / "output"
            if role_dir.exists():
                raise FileExistsError(f"refusing to overwrite campaign: {role_dir}")
            input_dir.mkdir(parents=True)
            output_dir.mkdir(parents=True)

            rows = [
                {
                    "id": case["id"],
                    "benchmarkId": block["benchmarkId"],
                    "responseFormat": "mcq",
                    "prompt": case["prompt"],
                }
                for case in public["cases"]
            ]
            ids = [row["id"] for row in rows]
            questions_path = input_dir / "questions.jsonl"
            instructions_path = input_dir / "RUN_INSTRUCTIONS.md"
            write_jsonl(questions_path, rows)
            write_text(instructions_path, INSTRUCTIONS)
            write_json(
                input_dir / "expected_ids.json",
                {"schemaVersion": 1, "count": 20, "ids": ids},
            )

            freeze = {
                "schemaVersion": 1,
                "status": "prepared_no_model_calls",
                "protocol": f"visible_options_5x20_direct_replicate_v1:{arm}",
                "arm": arm,
                "blockId": block_id,
                "benchmarkId": block["benchmarkId"],
                "sourceSelectionFreeze": str(selection_path.resolve()),
                "sourceSelectionFreezeSha256": sha256_file(selection_path),
                "sourcePublicPayload": str(public_path.resolve()),
                "sourcePublicPayloadSha256": sha256_file(public_path),
                "questionsSha256": sha256_file(questions_path),
                "instructionsSha256": sha256_file(instructions_path),
                "expectedIdsSha256": canonical_digest(ids),
                "inventory": {"rows": 20, "mcqRows": 20},
                "executionConfig": {
                    "model": model,
                    "reasoningEffort": reasoning_effort,
                    "verbosity": verbosity,
                    "serviceTier": "default",
                    "nativeWebSearch": False,
                    "database": False,
                    "skills": False,
                    "multiAgent": False,
                    "localCode": True,
                },
                "implementationHashes": {
                    str(Path(__file__).resolve()): sha256_file(Path(__file__).resolve()),
                    str(RUNNER.resolve()): sha256_file(RUNNER.resolve()),
                },
            }
            freeze["freezeSha256"] = canonical_digest(freeze)
            write_json(role_dir / "freeze.json", freeze)
            campaigns.append(
                {
                    "arm": arm,
                    "blockId": block_id,
                    "campaignDir": str(campaign_dir.resolve()),
                    "freezeSha256": freeze["freezeSha256"],
                }
            )

    report = {
        "status": "prepared_no_model_calls",
        "model": model,
        "reasoningEffort": reasoning_effort,
        "verbosity": verbosity,
        "arms": list(ARMS),
        "blocksPerArm": 5,
        "casesPerBlock": 20,
        "plannedSolverCalls": len(campaigns),
        "campaigns": campaigns,
    }
    write_json(campaign_root / "DIRECT_REPLICATES_PREPARATION_REPORT.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection-dir", type=Path, required=True)
    parser.add_argument("--campaign-root", type=Path, required=True)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--reasoning-effort", default="high")
    parser.add_argument("--verbosity", default="low")
    args = parser.parse_args()
    print(
        json.dumps(
            prepare(
                selection_dir=args.selection_dir.resolve(),
                campaign_root=args.campaign_root.resolve(),
                model=args.model,
                reasoning_effort=args.reasoning_effort,
                verbosity=args.verbosity,
            ),
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
