#!/usr/bin/env python3
"""Prepare one blind overlap-falsification call for a frozen 20-case block."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER = REPO_ROOT / "tools/run_plain_codex_file_agent.py"
ORDER_SEED = "choice-hidden-5x20-blind-candidate-order-v1"


INSTRUCTIONS = """# Blind KIRA + Universal overlap falsifier

Process all 20 rows in `input/questions.jsonl`. Each row contains one public
choice-hidden question and two independently generated candidate answers under
anonymous labels `candidateA` and `candidateB`. The labels are randomized per
row. You do not have answer choices or an answer key. Do not assume either
candidate is correct, do not use majority voting, and do not preserve an answer
merely because both candidates are topically similar.

No database, web search, external model, agent, skill, memory, or historical
benchmark result is available or permitted. Local file operations may be used
only to read input, maintain the decision ledger, and validate output.

For every row:

1. Extract the exact answer contract from the question before judging the
   candidates: requested entity/category, grammatical answer slot, polarity or
   exception, scope, number of required parts, and specificity.
2. State at least one plausible counter-hypothesis or failure mode. In
   particular, test whether a candidate gives a generally true topical
   explanation that does not actually fill the requested slot.
3. Falsify candidateA and candidateB independently against that contract.
4. Select A or B only if it directly answers the question. If both fail or omit
   a critical fact, repair them and write a new concise answer from the public
   question and your own knowledge.
5. Record the contract, candidate failure tests, decision (`A`, `B`, or
   `repair`), confidence, and final answer in `output/work/ledger.jsonl`.

Write exactly 20 UTF-8 JSONL rows to `output/answers.jsonl` in input order.
Every scored row must contain exactly:

`{"id":"exact input id","finalAnswer":"concise direct answer"}`

Apply KIRA-style double completion confirmation: first re-read this complete
instruction and inspect both ledger and answer file from test-engineer, QA, and
user viewpoints; then independently rerun disk validators for JSON, 20 rows,
exact IDs, exact key sets, order, non-empty answers, and boilerplate. Continue
working if either confirmation lacks evidence.
"""


RESEARCH_INSTRUCTIONS = INSTRUCTIONS.replace(
    "No database, web search, external model, agent, skill, memory, or historical\n"
    "benchmark result is available or permitted. Local file operations may be used\n"
    "only to read input, maintain the decision ledger, and validate output.",
    "No database, external model, agent, skill, memory, or historical benchmark result is available. "
    "Native web search is permitted only as selective KIRA-style verification for niche factual, historical, "
    "linguistic, doctrinal, or institutional claims that cannot be resolved from the public question and two "
    "candidates. Prefer official or primary sources. Never search an exact or near-exact exam question, a "
    "distinctive prompt fragment, case/benchmark ID, answer choice, quiz/exam mirror, or answer key. Use short "
    "general-concept queries instead. Local file operations may be used only to read input, maintain the "
    "decision ledger, and validate output. Record whether research was used and the fact/source type checked "
    "in each ledger row. Do not search when the question can be resolved confidently without it.",
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


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


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
    *, campaign_root: Path, block_id: str, policy: str = "closed"
) -> dict[str, Any]:
    if policy not in {"closed", "selective_research"}:
        raise ValueError(f"unsupported policy: {policy}")
    plain_dir = campaign_root / "plain" / block_id / "solver"
    independent_dir = campaign_root / "kira_independent" / block_id / "solver"
    for role_dir in (plain_dir, independent_dir):
        receipt = json.loads((role_dir / "run_receipt.json").read_text(encoding="utf-8"))
        if receipt.get("status") != "accepted":
            raise ValueError(f"source solver is not accepted: {role_dir}")

    plain_freeze = json.loads((plain_dir / "freeze.json").read_text(encoding="utf-8"))
    independent_freeze = json.loads(
        (independent_dir / "freeze.json").read_text(encoding="utf-8")
    )
    if plain_freeze["questionsSha256"] != independent_freeze["questionsSha256"]:
        raise ValueError("source arms do not share the exact question payload")

    source_questions = load_jsonl(plain_dir / "input/questions.jsonl")
    plain_answers = load_jsonl(plain_dir / "output/answers.jsonl")
    independent_answers = load_jsonl(independent_dir / "output/answers.jsonl")
    ids = [row["id"] for row in source_questions]
    if [row["id"] for row in plain_answers] != ids:
        raise ValueError("plain answer IDs/order mismatch")
    if [row["id"] for row in independent_answers] != ids:
        raise ValueError("independent answer IDs/order mismatch")

    blind_rows: list[dict[str, Any]] = []
    private_order: list[dict[str, str]] = []
    for question, plain, independent in zip(
        source_questions, plain_answers, independent_answers, strict=True
    ):
        case_id = question["id"]
        order_hash = sha256_bytes(f"{ORDER_SEED}\0{case_id}".encode("utf-8"))
        if int(order_hash[-1], 16) % 2 == 0:
            candidate_a, candidate_b = plain["finalAnswer"], independent["finalAnswer"]
            mapping = {"candidateA": "plain", "candidateB": "kira_independent"}
        else:
            candidate_a, candidate_b = independent["finalAnswer"], plain["finalAnswer"]
            mapping = {"candidateA": "kira_independent", "candidateB": "plain"}
        blind_rows.append(
            {
                "id": case_id,
                "benchmarkId": question["benchmarkId"],
                "responseFormat": "open_response_overlap",
                "prompt": question["prompt"],
                "candidateA": candidate_a,
                "candidateB": candidate_b,
            }
        )
        private_order.append(
            {"id": case_id, "orderHashSha256": order_hash, **mapping}
        )

    arm_name = (
        "overlap_falsifier"
        if policy == "closed"
        else "overlap_selective_research_falsifier"
    )
    instructions = INSTRUCTIONS if policy == "closed" else RESEARCH_INSTRUCTIONS
    role_dir = campaign_root / arm_name / block_id / "solver"
    if role_dir.exists():
        raise FileExistsError(f"refusing to overwrite campaign: {role_dir}")
    input_dir = role_dir / "input"
    output_dir = role_dir / "output"
    input_dir.mkdir(parents=True)
    output_dir.mkdir(parents=True)
    questions_path = input_dir / "questions.jsonl"
    instructions_path = input_dir / "RUN_INSTRUCTIONS.md"
    expected_ids_path = input_dir / "expected_ids.json"
    write_jsonl(questions_path, blind_rows)
    write_text(instructions_path, instructions)
    write_json(expected_ids_path, {"schemaVersion": 1, "count": 20, "ids": ids})

    freeze = {
        "schemaVersion": 1,
        "status": "prepared_no_model_calls",
        "protocol": f"choice_hidden_5x20_overlap_falsifier_v1:{policy}",
        "arm": arm_name,
        "blockId": block_id,
        "benchmarkId": source_questions[0]["benchmarkId"],
        "questionsSha256": sha256_file(questions_path),
        "instructionsSha256": sha256_file(instructions_path),
        "expectedIdsSha256": canonical_digest(ids),
        "inventory": {"rows": 20},
        "sourceCandidateAnswersSha256": {
            "plain": sha256_file(plain_dir / "output/answers.jsonl"),
            "kiraIndependent": sha256_file(
                independent_dir / "output/answers.jsonl"
            ),
        },
        "candidateOrderCanonicalSha256": canonical_digest(private_order),
        "executionConfig": {
            "model": "gpt-5.6-luna",
            "reasoningEffort": "high",
            "verbosity": "low",
            "serviceTier": "default",
            "nativeWebSearch": policy == "selective_research",
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
    write_json(
        campaign_root / arm_name / block_id / "candidate_order.private.json",
        {"schemaVersion": 1, "orderSeed": ORDER_SEED, "rows": private_order},
    )
    report = {
        "status": "prepared_no_model_calls",
        "campaignDir": str(role_dir.parent),
        "blockId": block_id,
        "rows": 20,
        "model": "gpt-5.6-luna",
        "policy": policy,
        "freezeSha256": freeze["freezeSha256"],
        "questionsSha256": freeze["questionsSha256"],
    }
    write_json(role_dir.parent / "PREPARATION_REPORT.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign-root", type=Path, required=True)
    parser.add_argument("--block-id", required=True)
    parser.add_argument(
        "--policy", choices=("closed", "selective_research"), default="closed"
    )
    args = parser.parse_args()
    report = prepare(
        campaign_root=args.campaign_root.resolve(),
        block_id=args.block_id,
        policy=args.policy,
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
