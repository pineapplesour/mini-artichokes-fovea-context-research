#!/usr/bin/env python3
"""Run one isolated whole-suite QuixBugs-40 candidate draft."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from harness_research.trace_gated_mini.core import TaskSpec, execute_attempt, to_jsonable
from tools.run_aider_hidden20_arm import IsolatedCodexAdapter


WHOLE_SUITE_PROMPT = """You are one independent candidate in a complete-benchmark program-repair study.

Repair all 40 official QuixBugs Python programs in this repository. Work through
the entire list in python_testcases/test_*.py; do not sample, prioritize only an
easy subset, or stop after a few successes. For each program, inspect its buggy
implementation and official public tests, identify the violated algorithmic
invariant, make the smallest general repair, and run that program's complete
test file with a bounded timeout. Recheck every program before finishing.

Correct implementations and gold patches are unavailable. Modify only the
corresponding algorithm modules under python_programs/. Do not edit tests, JSON
cases, helper test modules, node.py, benchmark utilities, or repository
metadata. Do not search the web. A timeout is a failed program, not permission
to omit it.

Complete frozen task contract:
{instruction}
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-id", choices=("d1", "d2", "d3"), required=True)
    parser.add_argument("--source-repo", required=True, type=Path)
    parser.add_argument("--task", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--codex-home", required=True, type=Path)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--reasoning-effort", default="medium")
    parser.add_argument("--agent-timeout-seconds", type=int, default=1800)
    parser.add_argument("--test-timeout-seconds", type=int, default=900)
    args = parser.parse_args()

    source_repo = args.source_repo.resolve()
    task = TaskSpec.from_json(args.task.resolve())
    output_dir = args.output_root.resolve() / args.candidate_id
    if output_dir.exists():
        raise FileExistsError(output_dir)
    output_dir.mkdir(parents=True)

    prompt = WHOLE_SUITE_PROMPT.format(instruction=task.instruction)
    adapter = IsolatedCodexAdapter(
        codex_home=args.codex_home.resolve(),
        model=args.model,
        reasoning_effort=args.reasoning_effort,
        timeout_seconds=args.agent_timeout_seconds,
    )
    contract = {
        "schemaVersion": 1,
        "candidateId": args.candidate_id,
        "taskId": task.task_id,
        "benchmarkPrograms": 40,
        "completeSuite": True,
        "model": args.model,
        "reasoningEffort": args.reasoning_effort,
        "sourceBaseRef": task.base_ref,
        "promptSha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "correctImplementationsVisible": False,
        "publicTestsVisible": True,
        "candidateIsolation": True,
    }
    (output_dir / "contract.json").write_text(
        json.dumps(contract, indent=2) + "\n", encoding="utf-8"
    )
    attempt = execute_attempt(
        source_repo=source_repo,
        task=task,
        output_dir=output_dir,
        candidate_id=args.candidate_id,
        policy="whole_suite_plain_repair",
        adapter=adapter,
        public_test_timeout_seconds=args.test_timeout_seconds,
        prompt_override=prompt,
    )
    payload = {
        "schemaVersion": 1,
        "candidateId": args.candidate_id,
        "attempt": to_jsonable(attempt),
    }
    (output_dir / "result.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "candidateId": args.candidate_id,
                "agentComplete": attempt.agent_complete,
                "safe": attempt.safe,
                "fullSuitePass": attempt.public_pass,
                "changedFiles": len(attempt.changed_files),
                "patchLines": attempt.patch_lines,
                "agentSeconds": attempt.agent.duration_seconds,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
