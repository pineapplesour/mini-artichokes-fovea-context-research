#!/usr/bin/env python3
"""Prepare matched 20-case Plain and independent KIRA audit campaigns."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER = REPO_ROOT / "tools/run_plain_codex_file_agent.py"
ARMS = ("plain", "kira_independent")


PLAIN_INSTRUCTIONS = """# Plain Luna choice-hidden block contract

Solve all 20 public questions in `input/questions.jsonl` independently from
your own knowledge. No answer choices, answer key, database, web search,
external model, agent, skill, memory, or historical benchmark result is
available or permitted. Local file operations may be used only to read the
input, track progress, and validate the output.

Write exactly 20 UTF-8 JSONL rows to `output/answers.jsonl`, preserving the
input order. Every row must contain exactly these keys:

`{"id":"exact input id","finalAnswer":"concise direct answer"}`

Use standard terminology, answer every supplied ID exactly once, and do not
include commentary outside the answer string. Validate JSON, row count, IDs,
key sets, order, and non-empty answers from disk before finishing.
"""


KIRA_INDEPENDENT_INSTRUCTIONS = """# KIRA-audited independent choice-hidden block contract

Solve all 20 public questions in `input/questions.jsonl` independently from
your own knowledge. This is an independent overlap draft: no other solver's
answers are present or available. No answer choices, answer key, database, web
search, external model, agent, skill, memory, or historical benchmark result
is available or permitted. Local file operations may be used only to read the
input, maintain the work ledger, and validate output.

For every ID, first record a provisional answer and confidence in
`output/work/ledger.jsonl`. Then re-read the original public question and try
to falsify the provisional answer by naming the strongest plausible
alternative or failure mode. Record whether the check agreed, what was tested,
and the final answer. Do not mark low-confidence items as checked merely to
finish; spend the remaining effort on them. The ledger is process evidence and
is not scored.

Write exactly 20 UTF-8 JSONL rows to `output/answers.jsonl`, preserving the
input order. Every scored row must contain exactly these keys:

`{"id":"exact input id","finalAnswer":"concise direct answer"}`

Before finishing, perform two completion checks. First, re-read this complete
instruction and inspect the actual ledger and final file from test-engineer,
QA, and user viewpoints. Second, rerun disk validators independently and check
JSON, 20 rows, exact IDs, key sets, order, non-empty answers, and accidental
boilerplate. Continue working if either check lacks evidence.
"""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_digest(value: Any) -> str:
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return sha256_bytes(raw)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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
    if selection.get("status") != "frozen_before_candidate_calls":
        raise ValueError("selection is not frozen before candidate calls")
    if selection.get("blockCount") != 5 or selection.get("casesPerBlock") != 20:
        raise ValueError("expected an exact 5x20 selection freeze")

    prepared: list[dict[str, Any]] = []
    for arm in ARMS:
        instructions = (
            PLAIN_INSTRUCTIONS if arm == "plain" else KIRA_INDEPENDENT_INSTRUCTIONS
        )
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
                    "responseFormat": "open_response",
                    "prompt": case["prompt"],
                }
                for case in public["cases"]
            ]
            ids = [row["id"] for row in rows]
            questions_path = input_dir / "questions.jsonl"
            instructions_path = input_dir / "RUN_INSTRUCTIONS.md"
            expected_ids_path = input_dir / "expected_ids.json"
            write_jsonl(questions_path, rows)
            write_text(instructions_path, instructions)
            write_json(expected_ids_path, {"schemaVersion": 1, "count": 20, "ids": ids})

            freeze = {
                "schemaVersion": 1,
                "status": "prepared_no_model_calls",
                "protocol": f"choice_hidden_5x20_solver_v1:{arm}",
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
                "inventory": {"rows": 20},
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
            prepared.append(
                {
                    "arm": arm,
                    "blockId": block_id,
                    "campaignDir": str(campaign_dir),
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
        "plannedSolverCalls": len(prepared),
        "campaigns": prepared,
    }
    write_json(campaign_root / "PREPARATION_REPORT.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection-dir", type=Path, required=True)
    parser.add_argument("--campaign-root", type=Path, required=True)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--reasoning-effort", default="high")
    parser.add_argument("--verbosity", default="low")
    args = parser.parse_args()
    report = prepare(
        selection_dir=args.selection_dir.resolve(),
        campaign_root=args.campaign_root.resolve(),
        model=args.model,
        reasoning_effort=args.reasoning_effort,
        verbosity=args.verbosity,
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
