#!/usr/bin/env python3
"""Prepare a blinded support-aware repair judge over three direct drafts."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER = REPO_ROOT / "tools/run_plain_codex_file_agent.py"
ROTATION_SEED = "visible-options-support-repair-judge-v1-20260902"
SOURCE_ARMS = ("plain", "direct_d2", "direct_d3")
CIRCLED = dict(zip("①②③④⑤", "12345"))


INSTRUCTIONS = """# Blinded support-aware falsification and repair judge

Adjudicate all 20 visible-options MCQs in `input/questions.jsonl`. Each row
contains three anonymous, independently produced direct-Luna draft option IDs
and their mechanical support counts. Their source identities and the answer
key are unavailable. No database, web search, external model, agent, skill,
memory, or historical benchmark result is available or permitted.

Support is useful but is not proof. For every item, independently solve from
the prompt and visible options, then try to falsify the most-supported option.
Use these conservative rules:

1. If a supported option survives the independent check, keep it.
2. Select a minority draft only when a specific fact, logical constraint, or
   passage statement refutes the plurality/majority and establishes it.
3. A repair to an option absent from all three drafts is allowed only when the
   same check both refutes every drafted option and uniquely establishes the
   repaired option. Mere uncertainty is not enough.
4. For unanimous drafts, require an especially explicit contradiction before
   changing the answer. Do not change an answer merely to create diversity.

Write one JSONL certificate per input row, in order, to
`output/work/ledger.jsonl`. Each certificate must include the exact `id`, the
independently derived provisional option, the strongest-supported option,
the strongest attempted falsifier, the decisive fact or constraint, the
decision (`KEEP_SUPPORT`, `SELECT_MINORITY`, or `REPAIR_UNSEEN`), and the final
numeric option ID.

Write exactly 20 UTF-8 JSONL rows to `output/answers.jsonl`, preserving input
order. Every scored row must contain exactly:

`{"id":"exact input id","finalAnswer":"numeric option ID only"}`

Use `"1"` through `"5"`. Validate JSON, exact IDs/order/key sets, option
membership, ledger alignment, and 20 rows from disk before finishing.
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


def load_answers(path: Path) -> list[dict[str, str]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    normalized: list[dict[str, str]] = []
    for row in rows:
        answer = CIRCLED.get(str(row.get("finalAnswer")), str(row.get("finalAnswer")))
        if set(row) != {"id", "finalAnswer"} or answer not in {"1", "2", "3", "4", "5"}:
            raise ValueError(f"invalid source answer row: {row}")
        normalized.append({"id": str(row["id"]), "finalAnswer": answer})
    return normalized


def rotation_order(case_id: str) -> list[int]:
    return sorted(
        range(3),
        key=lambda index: sha256_bytes(
            f"{ROTATION_SEED}\0{case_id}\0{index}".encode("utf-8")
        ),
    )


def prepare(
    *,
    campaign_root: Path,
    block_id: str,
    output_campaign: Path,
    model: str,
    reasoning_effort: str,
    verbosity: str,
) -> dict[str, Any]:
    sources: list[dict[str, Any]] = []
    source_answers: list[list[dict[str, str]]] = []
    common_questions_hash: str | None = None
    for arm in SOURCE_ARMS:
        campaign = campaign_root / arm / block_id
        role = campaign / "solver"
        freeze_path = role / "freeze.json"
        receipt_path = role / "run_receipt.json"
        answers_path = role / "output/answers.jsonl"
        freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if receipt.get("status") != "accepted":
            raise ValueError(f"source arm is not accepted: {arm}")
        if receipt.get("freezeSha256") != freeze.get("freezeSha256"):
            raise ValueError(f"source receipt/freeze mismatch: {arm}")
        questions_hash = str(freeze.get("questionsSha256") or "")
        if common_questions_hash is None:
            common_questions_hash = questions_hash
        elif questions_hash != common_questions_hash:
            raise ValueError("source arms do not share byte-identical questions")
        answers = load_answers(answers_path)
        if len(answers) != 20:
            raise ValueError(f"source arm is not 20 rows: {arm}")
        source_answers.append(answers)
        sources.append(
            {
                "anonymousSourceIndex": len(sources),
                "freezeSha256": freeze["freezeSha256"],
                "receiptSha256": receipt["receiptSha256"],
                "answersSha256": sha256_file(answers_path),
            }
        )

    public_questions_path = campaign_root / "plain" / block_id / "solver/input/questions.jsonl"
    if sha256_file(public_questions_path) != common_questions_hash:
        raise ValueError("public questions hash does not match source freezes")
    public_rows = [
        json.loads(line)
        for line in public_questions_path.read_text(encoding="utf-8").splitlines()
    ]
    ids = [str(row["id"]) for row in public_rows]
    if any([row["id"] for row in answers] != ids for answers in source_answers):
        raise ValueError("source answer IDs/order do not match questions")

    judge_rows: list[dict[str, Any]] = []
    conflict_count = 0
    unanimous_count = 0
    for row_index, public in enumerate(public_rows):
        case_id = ids[row_index]
        raw_drafts = [answers[row_index]["finalAnswer"] for answers in source_answers]
        order = rotation_order(case_id)
        rotated = [raw_drafts[index] for index in order]
        counts = Counter(raw_drafts)
        if len(counts) == 1:
            unanimous_count += 1
        else:
            conflict_count += 1
        support_order = sorted(
            counts,
            key=lambda option: sha256_bytes(
                f"{ROTATION_SEED}\0{case_id}\0support\0{option}".encode("utf-8")
            ),
        )
        judge_rows.append(
            {
                "id": case_id,
                "benchmarkId": public["benchmarkId"],
                "responseFormat": "mcq",
                "prompt": public["prompt"],
                "anonymousDrafts": [
                    {"slot": slot, "optionId": option}
                    for slot, option in zip(("A", "B", "C"), rotated)
                ],
                "supportCounts": [
                    {"optionId": option, "count": counts[option]}
                    for option in support_order
                ],
            }
        )

    role_dir = output_campaign / "solver"
    input_dir = role_dir / "input"
    output_dir = role_dir / "output"
    if role_dir.exists():
        raise FileExistsError(f"refusing to overwrite campaign: {role_dir}")
    input_dir.mkdir(parents=True)
    output_dir.mkdir(parents=True)
    questions_path = input_dir / "questions.jsonl"
    instructions_path = input_dir / "RUN_INSTRUCTIONS.md"
    write_jsonl(questions_path, judge_rows)
    write_text(instructions_path, INSTRUCTIONS)
    write_json(
        input_dir / "expected_ids.json",
        {"schemaVersion": 1, "count": 20, "ids": ids},
    )

    freeze = {
        "schemaVersion": 1,
        "status": "prepared_no_judge_call",
        "protocol": "visible_options_support_repair_judge_v1",
        "arm": "support_repair_judge",
        "blockId": block_id,
        "rotationSeed": ROTATION_SEED,
        "sourceDrafts": sources,
        "sourceDraftsCanonicalSha256": canonical_digest(sources),
        "sourceQuestionsSha256": common_questions_hash,
        "questionsSha256": sha256_file(questions_path),
        "instructionsSha256": sha256_file(instructions_path),
        "expectedIdsSha256": canonical_digest(ids),
        "inventory": {
            "rows": 20,
            "mcqRows": 20,
            "conflictRows": conflict_count,
            "unanimousRows": unanimous_count,
        },
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
    report = {
        "status": "prepared_no_judge_call",
        "campaignDir": str(output_campaign.resolve()),
        "blockId": block_id,
        "rows": 20,
        "conflictRows": conflict_count,
        "unanimousRows": unanimous_count,
        "plannedJudgeCalls": 1,
        "freezeSha256": freeze["freezeSha256"],
    }
    write_json(output_campaign / "PREPARATION_REPORT.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign-root", type=Path, required=True)
    parser.add_argument("--block-id", required=True)
    parser.add_argument("--output-campaign", type=Path, required=True)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--reasoning-effort", default="high")
    parser.add_argument("--verbosity", default="low")
    args = parser.parse_args()
    report = prepare(
        campaign_root=args.campaign_root.resolve(),
        block_id=args.block_id,
        output_campaign=args.output_campaign.resolve(),
        model=args.model,
        reasoning_effort=args.reasoning_effort,
        verbosity=args.verbosity,
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
