#!/usr/bin/env python3
"""Run the four-call official Aider Python-20 harness comparison."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from harness_research.trace_gated_mini.core import (
    CodexAdapter,
    TaskSpec,
    attempt_from_payload,
    execute_attempt,
    to_jsonable,
)


GRAPH_LEAD = """Solve every official exercise in the frozen order. For each exercise, first form a compact reasoning graph whose nodes cover requirements, candidate implementation choices, edge cases, and test evidence. Use explicit supports, contradicts, and depends-on relations. Before accepting a solution, try to falsify the selected implementation with at least one edge case. Do not write the graph to the repository; use it only to guide implementation. Keep going until all 20 official test suites pass or the time limit forces you to stop."""


ORDINARY_REPAIR = """Continue from the frozen Graph-of-Thought implementation below. This is an ordinary test-feedback repair baseline. Run `python run_public_tests.py`, fix every failing official exercise, and rerun the tests. Do not redesign passing tasks without a concrete test failure. Change only listed solution files and finish with the smallest test-passing patch."""


OVERLAP_REPAIR = """Continue from the exact same frozen Graph-of-Thought implementation used by the ordinary-repair control. Act as a graph-overlap completion verifier and minimal repairer.

For each task, independently reconstruct three evidence views: (1) the original requirement graph, (2) the current implementation and Git diff, and (3) actual official test behavior. Localize a defect when at least two views overlap on the same unmet obligation; do not change a passing implementation on speculation alone. For every failing task, actively search for a smallest counterexample, repair the general obligation rather than the single example, and rerun its official tests.

Before finishing, perform a KIRA-inspired completion audit twice: re-read the original task list, verify the actual test output, inspect the final diff for test or infrastructure edits, and confirm that all observable outcomes are supported. If either audit finds an unsupported item, continue working. Modify only listed solution files; never edit tests or benchmark infrastructure."""


def test_tail(attempt: object) -> str:
    public_test = attempt.public_test
    return (public_test.stdout + "\n" + public_test.stderr)[-60000:]


def load_attempt(path: Path):
    return attempt_from_payload(json.loads(path.read_text(encoding="utf-8")))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm", choices=("plain", "graph", "ordinary_repair", "graph_overlap"), required=True)
    parser.add_argument("--source-repo", required=True, type=Path)
    parser.add_argument("--task", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--codex-home", required=True, type=Path)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--reasoning-effort", default="medium")
    parser.add_argument("--agent-timeout-seconds", type=int, default=1500)
    parser.add_argument("--test-timeout-seconds", type=int, default=1200)
    args = parser.parse_args()

    task = TaskSpec.from_json(args.task.resolve())
    output_dir = args.output_root.resolve() / args.arm
    if output_dir.exists():
        raise FileExistsError(output_dir)
    output_dir.mkdir(parents=True)
    adapter = CodexAdapter(
        codex_home=args.codex_home.resolve(),
        model=args.model,
        reasoning_effort=args.reasoning_effort,
        timeout_seconds=args.agent_timeout_seconds,
    )

    seed_patch = None
    if args.arm == "plain":
        prompt = (
            "Solve the complete frozen batch directly. Inspect the repository, implement the smallest correct "
            "changes, run `python run_public_tests.py`, and continue until all official tests pass or time expires.\n\n"
            f"Original task:\n{task.instruction}"
        )
        candidate_id = "plain"
        policy = "direct"
    elif args.arm == "graph":
        prompt = f"{GRAPH_LEAD}\n\nOriginal task:\n{task.instruction}"
        candidate_id = "graph"
        policy = "graph_of_thought"
    else:
        graph_path = args.output_root.resolve() / "graph" / "attempts" / "graph" / "result.json"
        graph = load_attempt(graph_path)
        seed_patch = graph.patch_text
        lead = ORDINARY_REPAIR if args.arm == "ordinary_repair" else OVERLAP_REPAIR
        prompt = (
            f"{lead}\n\nOriginal task:\n{task.instruction}\n\n"
            "Frozen Graph public-test evidence (no hidden tests or gold solutions):\n"
            f"{test_tail(graph)}"
        )
        candidate_id = args.arm
        policy = args.arm

    (output_dir / "contract.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "arm": args.arm,
                "model": args.model,
                "reasoningEffort": args.reasoning_effort,
                "agentTimeoutSeconds": args.agent_timeout_seconds,
                "testTimeoutSeconds": args.test_timeout_seconds,
                "promptSha256": hashlib.sha256(prompt.encode()).hexdigest(),
                "seedPatchSha256": hashlib.sha256(seed_patch.encode()).hexdigest() if seed_patch else None,
                "goldVisible": False,
                "officialTestsVisible": True,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    attempt = execute_attempt(
        source_repo=args.source_repo.resolve(),
        task=task,
        output_dir=output_dir,
        candidate_id=candidate_id,
        policy=policy,
        adapter=adapter,
        public_test_timeout_seconds=args.test_timeout_seconds,
        prompt_override=prompt,
        seed_patch=seed_patch,
    )
    payload = {
        "schemaVersion": 1,
        "arm": args.arm,
        "selectedCandidateId": candidate_id,
        "selectedEligible": attempt.eligible,
        "attempt": to_jsonable(attempt),
    }
    (output_dir / "result.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "arm": args.arm,
                "agentComplete": attempt.agent_complete,
                "publicPass": attempt.public_pass,
                "safe": attempt.safe,
                "changedFiles": len(attempt.changed_files),
                "patchLines": attempt.patch_lines,
                "agentSeconds": attempt.agent.duration_seconds,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
