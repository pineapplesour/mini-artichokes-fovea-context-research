#!/usr/bin/env python3
"""Prepare a blinded veto audit only for support-judge changes."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER = REPO_ROOT / "tools/run_plain_codex_file_agent.py"
ROTATION_SEED = "visible-options-change-veto-v1-20260902"
CIRCLED = dict(zip("①②③④⑤", "12345"))


INSTRUCTIONS = """# Blinded change-veto certificate audit

Independently adjudicate every row in `input/questions.jsonl`. These are only
the rows where a previous support-aware review proposed changing a mechanical
three-draft result. Each row contains the original MCQ, two anonymous option
candidates in hash-rotated A/B order, and an untrusted rationale from the
previous review. You are not told which candidate is the incumbent or the
proposed change.

Treat the prior rationale as a claim to falsify, not as authority. Re-solve
the question from the prompt, explicitly test both candidates against the
decisive passage, fact, or logical constraints, and select the uniquely
better candidate. You may not synthesize a third option. If the evidence is
not strong enough to distinguish them, select the candidate better supported
by a complete direct derivation rather than by the prior rationale's wording.
No answer key, database, web search, external model, agent, skill, memory, or
historical result is available or permitted.

Write one certificate per input row, in order, to
`output/work/ledger.jsonl`, including exact `id`, both tested option IDs, the
strongest falsifier for each, the decisive fact or constraint, and the final
numeric option ID.

Write exactly one UTF-8 JSONL row per input row to `output/answers.jsonl`, in
input order. Every scored row must contain exactly:

`{"id":"exact input id","finalAnswer":"numeric option ID only"}`

The answer must be one of the row's two anonymous candidate option IDs. Check
JSON, exact row count, IDs/order/key sets, candidate membership, and ledger
alignment from disk before finishing.
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


def load_answers(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for row in map(json.loads, path.read_text(encoding="utf-8").splitlines()):
        answer = CIRCLED.get(str(row.get("finalAnswer")), str(row.get("finalAnswer")))
        if set(row) != {"id", "finalAnswer"} or answer not in {"1", "2", "3", "4", "5"}:
            raise ValueError(f"invalid source answer row: {row}")
        result[str(row["id"])] = answer
    return result


def prepare(
    *,
    campaign_root: Path,
    block_id: str,
    support_judge_campaign: Path,
    output_campaign: Path,
    model: str,
    reasoning_effort: str,
    verbosity: str,
) -> dict[str, Any]:
    public_path = campaign_root / "plain" / block_id / "solver/input/questions.jsonl"
    public_rows = [
        json.loads(line) for line in public_path.read_text(encoding="utf-8").splitlines()
    ]
    ids = [str(row["id"]) for row in public_rows]
    direct = [
        load_answers(campaign_root / arm / block_id / "solver/output/answers.jsonl")
        for arm in ("plain", "direct_d2", "direct_d3")
    ]
    if any(list(answers) != ids for answers in direct):
        raise ValueError("direct answer IDs/order mismatch")
    sc3: dict[str, str] = {}
    for case_id in ids:
        counts = Counter(answers[case_id] for answers in direct)
        option, count = counts.most_common(1)[0]
        sc3[case_id] = option if count >= 2 else direct[0][case_id]

    judge_role = support_judge_campaign / "solver"
    judge_receipt_path = judge_role / "run_receipt.json"
    judge_answers_path = judge_role / "output/answers.jsonl"
    judge_ledger_path = judge_role / "output/work/ledger.jsonl"
    receipt = json.loads(judge_receipt_path.read_text(encoding="utf-8"))
    if receipt.get("status") != "accepted":
        raise ValueError("support judge source is not accepted")
    judge = load_answers(judge_answers_path)
    ledger = {
        str(row["id"]): row
        for row in map(json.loads, judge_ledger_path.read_text(encoding="utf-8").splitlines())
    }
    if list(judge) != ids or list(ledger) != ids:
        raise ValueError("support judge answer/ledger IDs mismatch")

    changed_ids = [case_id for case_id in ids if judge[case_id] != sc3[case_id]]
    if not changed_ids:
        raise ValueError("support judge made no changes to audit")
    public_by_id = {str(row["id"]): row for row in public_rows}
    rows: list[dict[str, Any]] = []
    for case_id in changed_ids:
        options = [sc3[case_id], judge[case_id]]
        if sha256_bytes(f"{ROTATION_SEED}\0{case_id}".encode("utf-8"))[-1] in "02468ace":
            options.reverse()
        prior = ledger[case_id]
        rows.append(
            {
                "id": case_id,
                "benchmarkId": public_by_id[case_id]["benchmarkId"],
                "responseFormat": "mcq",
                "prompt": public_by_id[case_id]["prompt"],
                "anonymousCandidates": [
                    {"slot": slot, "optionId": option}
                    for slot, option in zip(("A", "B"), options)
                ],
                "untrustedPriorRationale": {
                    "attemptedFalsifier": str(prior["strongestAttemptedFalsifier"]),
                    "claimedDecisiveFactOrConstraint": str(prior["decisiveFactOrConstraint"]),
                },
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
    write_jsonl(questions_path, rows)
    write_text(instructions_path, INSTRUCTIONS)
    write_json(
        input_dir / "expected_ids.json",
        {"schemaVersion": 1, "count": len(rows), "ids": changed_ids},
    )

    source = {
        "supportJudgeReceiptSha256": receipt["receiptSha256"],
        "supportJudgeAnswersSha256": sha256_file(judge_answers_path),
        "supportJudgeLedgerSha256": sha256_file(judge_ledger_path),
        "directAnswersSha256": [
            sha256_file(campaign_root / arm / block_id / "solver/output/answers.jsonl")
            for arm in ("plain", "direct_d2", "direct_d3")
        ],
        "changedIdsCanonicalSha256": canonical_digest(changed_ids),
    }
    freeze = {
        "schemaVersion": 1,
        "status": "prepared_no_veto_call",
        "protocol": "visible_options_change_veto_v1",
        "arm": "change_veto",
        "blockId": block_id,
        "rotationSeed": ROTATION_SEED,
        "source": source,
        "sourceCanonicalSha256": canonical_digest(source),
        "questionsSha256": sha256_file(questions_path),
        "instructionsSha256": sha256_file(instructions_path),
        "expectedIdsSha256": canonical_digest(changed_ids),
        "inventory": {"rows": len(rows), "mcqRows": len(rows)},
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
        "status": "prepared_no_veto_call",
        "campaignDir": str(output_campaign.resolve()),
        "blockId": block_id,
        "rows": len(rows),
        "plannedVetoCalls": 1,
        "freezeSha256": freeze["freezeSha256"],
    }
    write_json(output_campaign / "PREPARATION_REPORT.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign-root", type=Path, required=True)
    parser.add_argument("--block-id", required=True)
    parser.add_argument("--support-judge-campaign", type=Path, required=True)
    parser.add_argument("--output-campaign", type=Path, required=True)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--reasoning-effort", default="high")
    parser.add_argument("--verbosity", default="low")
    args = parser.parse_args()
    print(
        json.dumps(
            prepare(
                campaign_root=args.campaign_root.resolve(),
                block_id=args.block_id,
                support_judge_campaign=args.support_judge_campaign.resolve(),
                output_campaign=args.output_campaign.resolve(),
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
