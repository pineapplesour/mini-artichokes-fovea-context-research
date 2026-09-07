#!/usr/bin/env python3
"""Prepare full-suite Codex solver campaigns for structural arm comparisons."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.prepare_plain_codex_file_benchmark import (
    DEFAULT_REGISTRY,
    EXPECTED_EXAM_CASES,
    EXPECTED_LEGAL_VARIANTS,
    SOLVER_INSTRUCTIONS,
    canonical_digest,
    ensure_new_directory,
    load_public_rows,
    sha256_file,
    write_json,
    write_jsonl,
)


KIRA_UNIVERSAL_INSTRUCTIONS = """# KIRA + Universal-overlap full-suite solver contract

You have one Codex invocation for this entire benchmark. You are responsible for
all 1,309 rows as one artifact. Do not spawn agents, call another language model,
or delegate subsets. Read every row in `input/questions.jsonl` and solve each
independently. Native web search and local calculation code are allowed only
under the anti-exam-lookup policy below.

## Required durable workflow

1. Create a private working ledger under `output/work/` that records every ID,
   a provisional answer, confidence, and whether a second independent check
   agreed. This ledger is process evidence, not the scored output.
2. Produce a first answer for every row. Do not copy templates across unrelated
   rows. For MCQ, reason from the supplied prompt and choices and retain the full
   selected option content.
3. Recheck each row from the original prompt without trusting the provisional
   answer. Mark disagreement, low confidence, malformed option mapping, repeated
   boilerplate, empty reasoning, and incomplete constructed/legal responses.
4. Apply Universal selective escalation: preserve high-confidence agreements;
   spend the remaining effort only on marked rows, but do not omit or abstain on
   them. Resolve every marked row into a final answer.
5. Write progress incrementally to `output/answers.partial.jsonl`, preserving
   input order. Validate exact IDs, count, schema, non-empty answers, and obvious
   repetition before atomically finishing `output/answers.jsonl`.

## Answer contract

For an MCQ, all original choices are present. Put the content of the selected
option in `finalAnswer`, not only a label such as A or 3. Include every selected
option and no extra option for multi-select. Answer short-answer and constructed
items directly with enough detail for the task. For legal E2E items, research
public law and precedents when useful and produce a substantive answer.

Every final line must contain exactly these keys and no others:

`{"id":"the exact input id","finalAnswer":"your answer"}`

There must be exactly 1,309 UTF-8 JSONL rows, one per supplied ID in input order.
The work ledger may have richer fields but must never replace the final file.

## Search and isolation policy

Do not search for an exact or near-exact exam question, distinctive answer
choice, exam/quiz paper or mirror, answer key, benchmark/case ID, or historical
benchmark answer. General concept/fact research is allowed. For legal E2E rows,
public facts, legal issues, and relevant public precedents may be researched.
Do not inspect paths outside this isolated workspace.

## KIRA-style double completion confirmation

Before finishing the first time, re-read this complete original instruction and
inspect the actual files. Explicitly verify: all 1,309 requirements are covered;
the final file, not chat, owns the answers; only necessary output files changed;
schema/count/order are exact; public prompts rather than provisional answers were
rechecked; malformed, copied, low-confidence, and disagreement rows were
escalated; and the result is robust from test-engineer, QA, and user viewpoints.

Then perform a second independent completion check by rerunning the validators
and repetition audit from disk. If any check lacks evidence, continue working.
Only after both checks pass may you finish. Your final chat message should state
only whether the complete validated answer file was produced.
"""


VARIANT_SUFFIXES = {
    "plain": "",
    "kira_universal": "",
    "overlap_a": "\nIndependent role A: solve directly from first principles; do not assume any prior candidate exists.\n",
    "overlap_b": "\nIndependent role B: seek a counterexample to the first plausible answer before committing on each row.\n",
    "overlap_c": "\nIndependent role C: emphasize adversarial requirement coverage, boundary cases, and falsification.\n",
}


def implementation_hashes() -> dict[str, str]:
    here = Path(__file__).resolve()
    paths = (
        here,
        here.parent / "prepare_plain_codex_file_benchmark.py",
        here.parent / "run_plain_codex_file_agent.py",
    )
    return {str(path): sha256_file(path) for path in paths}


def prepare(
    *,
    registry_path: Path,
    campaign_dir: Path,
    policy: str,
    model: str,
    reasoning_effort: str,
    verbosity: str,
) -> dict[str, Any]:
    solver_dir = campaign_dir / "solver"
    ensure_new_directory(solver_dir)
    rows, source_hashes = load_public_rows(registry_path)
    input_dir = solver_dir / "input"
    output_dir = solver_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    questions_path = input_dir / "questions.jsonl"
    write_jsonl(questions_path, rows)
    if policy == "plain":
        instructions = SOLVER_INSTRUCTIONS
    else:
        instructions = KIRA_UNIVERSAL_INSTRUCTIONS + VARIANT_SUFFIXES[policy]
    instructions_path = input_dir / "RUN_INSTRUCTIONS.md"
    instructions_path.write_text(instructions, encoding="utf-8")
    ids = [row["id"] for row in rows]
    write_json(input_dir / "expected_ids.json", {"count": len(ids), "ids": ids})
    freeze: dict[str, Any] = {
        "schemaVersion": 1,
        "status": "prepared_no_model_calls",
        "protocol": f"full_suite_structural_arm_v1:{policy}",
        "policy": policy,
        "registryPath": str(registry_path.resolve()),
        "registrySha256": sha256_file(registry_path),
        "sourcePublicManifestHashes": source_hashes,
        "questionsPath": "input/questions.jsonl",
        "questionsSha256": sha256_file(questions_path),
        "instructionsSha256": sha256_file(instructions_path),
        "expectedIdsSha256": canonical_digest(ids),
        "inventory": {
            "examCases": EXPECTED_EXAM_CASES,
            "legalVariants": EXPECTED_LEGAL_VARIANTS,
            "rows": len(rows),
        },
        "executionConfig": {
            "model": model,
            "reasoningEffort": reasoning_effort,
            "verbosity": verbosity,
            "serviceTier": "default",
            "nativeWebSearch": True,
            "localCode": True,
            "database": False,
            "skills": False,
            "multiAgent": False,
        },
        "implementationHashes": implementation_hashes(),
    }
    freeze["freezeSha256"] = canonical_digest(freeze)
    write_json(solver_dir / "freeze.json", freeze)
    return freeze


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--policy", choices=tuple(VARIANT_SUFFIXES), required=True)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--reasoning-effort", default="high")
    parser.add_argument("--verbosity", default="low")
    args = parser.parse_args()
    result = prepare(
        registry_path=args.registry.resolve(),
        campaign_dir=args.campaign_dir.resolve(),
        policy=args.policy,
        model=args.model,
        reasoning_effort=args.reasoning_effort,
        verbosity=args.verbosity,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
