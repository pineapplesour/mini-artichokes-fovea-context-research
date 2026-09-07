#!/usr/bin/env python3
"""Prepare six budgeted reasoning-method screens on one frozen 20-case block."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER = REPO_ROOT / "tools/run_plain_codex_file_agent.py"
CIRCLED = dict(zip("①②③④⑤", "12345"))
METHODS = (
    "tree_of_thoughts",
    "reflexion",
    "self_refine",
    "critic_verifier",
    "skeleton_of_thought",
    "graph_of_thought",
)


COMMON = """No answer key, database, web search, external model, agent, skill,
memory, or historical benchmark result is available or permitted. Use only
the supplied prompt and visible options. Local file operations may only read
input, maintain the requested ledger, write output, and validate it.

Write exactly 20 ordered UTF-8 JSONL rows to `output/answers.jsonl`, each with
exactly `{"id":"exact input id","finalAnswer":"numeric option ID only"}`.
Use `"1"` through `"5"`. Write the method ledger to
`output/work/ledger.jsonl`. Before finishing, validate JSON, exact row count,
IDs/order/key sets, visible-option membership, and ledger alignment from disk.
"""


INSTRUCTIONS = {
    "tree_of_thoughts": """# Budgeted Tree-of-Thoughts screen

Solve all 20 MCQs. For every item, create three genuinely different candidate
reasoning branches before selecting an answer: a direct derivation, an
option-elimination branch, and a counterexample/constraint branch. Record the
three proposed option IDs and short supporting evidence in
`output/work/ledger.jsonl`. Compare branches by factual/constraint fit rather
than fluency or majority vote. Select the option supported by the strongest
branch; if branches disagree, explicitly falsify the losing branches.

""" + COMMON,
    "reflexion": """# Budgeted Reflexion screen

Each row includes `priorAnswer`, the result of a separate direct-Luna attempt.
Treat it as an earlier episode, not as authority. For every item, independently
reconstruct the solution, diagnose the most likely failure mode of the prior
attempt, write a concise reusable reflection/lesson, and perform one fresh
reattempt conditioned on that reflection. Record prior answer, failure
hypothesis, reflection, and final option in `output/work/ledger.jsonl`. Keep a
prior answer only when the reattempt re-establishes it.

""" + COMMON,
    "self_refine": """# Budgeted Self-Refine screen

Solve all 20 MCQs within this one call. For every item, first record your own
initial option and derivation, then generate specific feedback identifying a
possible factual, logical, polarity, or transcription error, and finally
revise once using that feedback. Record initial option, feedback, and refined
option in `output/work/ledger.jsonl`. Feedback must test the actual derivation;
do not change an answer merely to appear to refine it.

""" + COMMON,
    "critic_verifier": """# Budgeted separated Critic/Verifier screen

Each row includes `priorAnswer` from a separate direct-Luna generator. You are
the independent verifier and did not produce that answer. For every item,
write a structured critic certificate that names the strongest concrete
reason the proposed option could be wrong, checks the best alternative against
the prompt, and returns KEEP or REPLACE plus one final option. Record the
candidate, critic finding, decisive evidence, action, and final option in
`output/work/ledger.jsonl`. Separation is the source of independence: do not
defer to the generator, but do not replace without a localized reason.

""" + COMMON,
    "skeleton_of_thought": """# Budgeted Skeleton-of-Thought screen

Solve all 20 MCQs in two phases. First create a complete skeleton covering all
20 IDs: for each, record question type, decisive cue/constraint, and tentative
option in `output/work/ledger.jsonl` without extended prose. Only after the
complete skeleton exists, fill and verify each item, spending detail on weak
or conflicting skeleton entries. Record any corrected option and the deciding
fact. Preserve breadth-first coverage; do not fully solve early items while
leaving later items shallow.

""" + COMMON,
    "graph_of_thought": """# Budgeted Graph-of-Thought screen

Solve all 20 MCQs. For every item construct a compact reasoning graph in
`output/work/ledger.jsonl`: nodes are decisive claims/constraints and candidate
options; directed edges mark supports, contradicts, or depends-on relations.
Propagate contradictions, remove options with an unresolved decisive conflict,
and select the surviving option with the strongest connected support. Include
at least one attempted contradiction edge against the selected option. This
is a per-item graph; never transfer facts between unrelated questions.

""" + COMMON,
}


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
        value = CIRCLED.get(str(row.get("finalAnswer")), str(row.get("finalAnswer")))
        if set(row) != {"id", "finalAnswer"} or value not in {"1", "2", "3", "4", "5"}:
            raise ValueError(f"invalid base answer row: {row}")
        result[str(row["id"])] = value
    return result


def prepare(
    *,
    campaign_root: Path,
    block_id: str,
    output_root: Path,
    model: str,
    reasoning_effort: str,
    verbosity: str,
) -> dict[str, Any]:
    base_campaign = campaign_root / "plain" / block_id
    base_role = base_campaign / "solver"
    base_receipt = json.loads((base_role / "run_receipt.json").read_text(encoding="utf-8"))
    if base_receipt.get("status") != "accepted":
        raise ValueError("Plain base must be an accepted run")
    base_answers_path = base_role / "output/answers.jsonl"
    base_answers = load_answers(base_answers_path)
    public_path = base_role / "input/questions.jsonl"
    public_rows = [
        json.loads(line) for line in public_path.read_text(encoding="utf-8").splitlines()
    ]
    ids = [str(row["id"]) for row in public_rows]
    if len(ids) != 20 or list(base_answers) != ids:
        raise ValueError("screen requires one exact accepted 20-case block")
    public_prompt_digest = canonical_digest(
        [{"id": row["id"], "prompt": row["prompt"]} for row in public_rows]
    )

    campaigns: list[dict[str, Any]] = []
    for method in METHODS:
        role_dir = output_root / method / block_id / "solver"
        input_dir = role_dir / "input"
        output_dir = role_dir / "output"
        if role_dir.exists():
            raise FileExistsError(f"refusing to overwrite campaign: {role_dir}")
        input_dir.mkdir(parents=True)
        output_dir.mkdir(parents=True)
        include_prior = method in {"reflexion", "critic_verifier"}
        rows = []
        for row in public_rows:
            item = {
                "id": row["id"],
                "benchmarkId": row["benchmarkId"],
                "responseFormat": "mcq",
                "prompt": row["prompt"],
            }
            if include_prior:
                item["priorAnswer"] = base_answers[str(row["id"])]
            rows.append(item)
        questions_path = input_dir / "questions.jsonl"
        instructions_path = input_dir / "RUN_INSTRUCTIONS.md"
        write_jsonl(questions_path, rows)
        write_text(instructions_path, INSTRUCTIONS[method])
        write_json(
            input_dir / "expected_ids.json",
            {"schemaVersion": 1, "count": 20, "ids": ids},
        )
        source = {
            "baseReceiptSha256": base_receipt["receiptSha256"],
            "baseAnswersSha256": sha256_file(base_answers_path),
            "publicQuestionsSha256": sha256_file(public_path),
            "publicPromptCanonicalSha256": public_prompt_digest,
            "includesPriorAnswer": include_prior,
        }
        freeze = {
            "schemaVersion": 1,
            "status": "prepared_no_model_calls",
            "protocol": f"visible_options_budgeted_method_screen_v1:{method}",
            "arm": method,
            "blockId": block_id,
            "methodRealization": "budgeted_prompt_realization_not_full_canonical_replication",
            "source": source,
            "sourceCanonicalSha256": canonical_digest(source),
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
                "method": method,
                "campaignDir": str((output_root / method / block_id).resolve()),
                "freezeSha256": freeze["freezeSha256"],
            }
        )

    report = {
        "status": "prepared_no_model_calls",
        "blockId": block_id,
        "methods": list(METHODS),
        "rowsPerMethod": 20,
        "plannedSolverCalls": len(METHODS),
        "campaigns": campaigns,
    }
    write_json(output_root / f"{block_id}_PREPARATION_REPORT.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign-root", type=Path, required=True)
    parser.add_argument("--block-id", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--reasoning-effort", default="high")
    parser.add_argument("--verbosity", default="low")
    args = parser.parse_args()
    print(
        json.dumps(
            prepare(
                campaign_root=args.campaign_root.resolve(),
                block_id=args.block_id,
                output_root=args.output_root.resolve(),
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
