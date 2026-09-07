#!/usr/bin/env python3
"""One seed-matched fifth repair; reuse the existing isolated execution core."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from harness_research.trace_gated_mini.core import TaskSpec, execute_attempt, to_jsonable
from tools.run_aider_hidden20_arm import (
    IsolatedCodexAdapter, compact_test_evidence, load_attempt,
    stage_adjudication_evidence, task_outcomes,
)
from tools.analyze_aider_online_offline_portfolio import run_evaluator


GENERIC = """Use strong general code review and execution-feedback repair. Choose your own
reasoning strategy, freely compare any candidates, and use all available evidence.
Reconstruct each missing requirement, localize its cause in the current code,
consider alternative repairs, and prioritize changes likely to solve remaining
failures. Derive a small specification-grounded counterexample or boundary check
for an uncertain repair. Preserve working behavior and fix the general cause.
Avoid cosmetic rewrites and explanations that do not lead to a concrete check.
Record the hypothesis, actual check, observation, and chosen action compactly."""

OVERLAP = """Use cross-candidate semantic overlap to target failures that another similar
attempt would repeat. Align candidate behavior by requirement and violated
invariant, not by matching code lines. Identify both complementary partial
repairs and assumptions shared by failing candidates. Agreement is not truth.
For the most consequential unresolved disagreement or shared unsupported
assumption, derive a minimal input that makes competing hypotheses predict
different behavior. Resolve its expected behavior from the specification, not
from a candidate vote. Use that witness to change the failing assumption while
retaining already supported obligations. If hypotheses cannot be distinguished,
reconsider the assumption rather than merely restating the existing repair.
Record the aligned hypothesis, actual check, observation, and action compactly."""

COMMON = """You are the fifth code-repair execution for a complete official task track.
The current workspace is exactly the fourth candidate. The evidence index is
/tmp/artifacts/evidence-index.json. It contains Plain, Graph, ordinary-repair
patches and bounded official outcomes, plus the fourth patch. Read it first.
{feedback}

{policy}

All original tasks remain in scope. Previously passing candidate snapshots will
be available to the same final verifier selector for every experimental arm.
Do not spend effort on cosmetic changes to already supported implementations.
Use the current implementation or copy a better candidate as warranted; there
are no byte-locked files within the allowed solution paths.

When useful, execute tiny documentation-derived checks against COPIES of actual
candidate source under /tmp; do not replace execution with a claimed simulation.
Such checks may confirm an example or distinguish hypotheses, but their expected
answers must follow the specification. Candidate disagreement alone is not a
correctness oracle. Hidden tests, gold, external answers, and benchmark lookup
are unavailable and forbidden. You may inspect only the supplied task material
and candidate evidence. Edit only the task's listed solution files; temporary
drivers and compilation products belong outside the repository.

Write /tmp/artifacts/decision_ledger.json as a JSON array with exactly one row
per task: taskId, hypothesis, check, observation, action. Keep each row short;
for preserved tasks record the supporting evidence and 'preserve'. Never invent
an executed check or claim an unavailable tool succeeded. Before ending, inspect
the final diff against the intended fixes, then recheck the original requirements
and the actual final code for unresolved contradictions. Repair concrete defects
found by either audit. Work within the stated execution budget and return a
complete ledger and final source files, not a long final explanation.

Original task:
{instruction}
"""


def make_prompt(instruction: str, policy: str, feedback: bool) -> str:
    if policy not in {"generic", "overlap"}:
        raise ValueError(policy)
    note = (
        "The fourth candidate's official outcomes and bounded failure tails are also supplied. "
        "Use this new feedback to target its remaining failures."
        if feedback else
        "No official outcome of the fourth candidate is supplied. Evaluate its source "
        "using the original requirements, earlier evidence, and your own checks."
    )
    return COMMON.format(feedback=note, policy=GENERIC if policy == "generic" else OVERLAP,
                         instruction=instruction)


def read_attempt(root: Path, name: str):
    return load_attempt(root / name / "attempts" / name / "result.json")


def validate_attempt(attempt, ids: set[str]) -> dict[str, bool]:
    outcomes = task_outcomes(attempt)
    records = compact_test_evidence(attempt)
    seen = [row["taskId"] for row in records if row.get("taskId")]
    if (not attempt.agent_complete or not attempt.safe or attempt.public_test.timed_out
            or set(outcomes) != ids or len(seen) != len(ids)):
        raise ValueError(f"incomplete or unsafe candidate: {attempt.candidate_id}")
    return outcomes


def choose_sources(candidates: list[tuple[str, dict[str, bool]]], ids: set[str]) -> dict[str, str]:
    if not candidates or any(set(outcomes) != ids for _, outcomes in candidates):
        raise ValueError("candidate inventories differ")
    return {task_id: next((name for name, outcomes in candidates if outcomes[task_id]),
                          candidates[0][0]) for task_id in sorted(ids)}


def usage(attempt) -> dict:
    total = {}
    responses = 0
    for raw in attempt.agent.stdout.splitlines():
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "turn.completed":
            total = event.get("usage", {})
        if event.get("type") == "item.completed" and event.get("item", {}).get("type") == "agent_message":
            responses += 1
    return {"agentSeconds": attempt.agent.duration_seconds, "usage": total,
            "recordedAgentMessages": responses}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--policy", choices=["generic", "overlap"], required=True)
    parser.add_argument("--feedback", choices=["on", "off"], required=True)
    parser.add_argument("--prefix", default="cex_v1")
    parser.add_argument("--codex-home", type=Path, default=Path("/home/pineapple/.codex-new-account"))
    args = parser.parse_args()
    root = args.run_root.resolve()
    arms = root / "arms"
    source = root / "freeze/source"
    task = TaskSpec.from_json(root / "freeze/public/task.json")
    manifest = json.loads((source / "benchmark_manifest.json").read_text())
    ids = {item["taskId"] for item in manifest["tasks"]}
    if len(ids) != len(manifest["tasks"]):
        raise ValueError("duplicate manifest IDs")
    feedback = args.feedback == "on"
    cell = f"{args.policy}_{'feedback' if feedback else 'blind'}"
    name = f"{args.prefix}_{cell}"
    fourth_name = f"{args.prefix}_shared4"
    fourth = read_attempt(arms, fourth_name)
    validate_attempt(fourth, ids)
    out = arms / name
    if out.exists():
        raise FileExistsError(out)
    staged = stage_adjudication_evidence(arms, name)
    attempts = staged["attempts"]
    for attempt in attempts.values():
        validate_attempt(attempt, ids)
    artifact = out / "attempts" / name
    (artifact / "fourth.patch").write_text(fourth.patch_text)
    index = staged["index"]
    index["candidates"]["fourth"] = {
        "patch": "/tmp/artifacts/fourth.patch", "patchSha256": fourth.patch_sha256,
    }
    if feedback:
        (artifact / "fourth.test-evidence.json").write_text(
            json.dumps(compact_test_evidence(fourth), ensure_ascii=False, indent=2) + "\n")
        index["candidates"]["fourth"]["testEvidence"] = "/tmp/artifacts/fourth.test-evidence.json"
    (artifact / "evidence-index.json").write_text(json.dumps(index, indent=2) + "\n")
    prompt = make_prompt(task.instruction, args.policy, feedback)
    contract = {
        "cell": cell, "candidateId": name, "model": "gpt-5.6-luna", "effort": "medium",
        "agentTimeoutSeconds": 480, "newFourthFeedback": feedback,
        "seedPatchSha256": fourth.patch_sha256,
        "promptSha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "runnerSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "evidenceHashes": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in sorted(artifact.iterdir()) if p.is_file()},
        "taskIds": sorted(ids), "interpretation": "exposed-task paired development; five executions",
    }
    (out / "contract.json").write_text(json.dumps(contract, indent=2) + "\n")
    result = execute_attempt(
        source_repo=source, task=task, output_dir=out, candidate_id=name, policy=cell,
        adapter=IsolatedCodexAdapter(codex_home=args.codex_home.resolve(), model="gpt-5.6-luna",
                                    reasoning_effort="medium", timeout_seconds=480),
        public_test_timeout_seconds=1800, prompt_override=prompt, seed_patch=fourth.patch_text,
    )
    (out / "result.json").write_text(json.dumps({"arm": cell, "attempt": to_jsonable(result)}, indent=2) + "\n")
    final_outcomes = validate_attempt(result, ids)
    ledger = json.loads((artifact / "decision_ledger.json").read_text())
    required = {"taskId", "hypothesis", "check", "observation", "action"}
    if (not isinstance(ledger, list) or len(ledger) != len(ids)
            or {row.get("taskId") for row in ledger} != ids
            or any(not required.issubset(row) for row in ledger)):
        raise ValueError("incomplete decision ledger; candidate kept but protocol fidelity failed")
    candidates = [(name, result), (fourth_name, fourth),
                  ("ordinary_repair", attempts["ordinary_repair"]),
                  ("graph", attempts["graph"]), ("plain", attempts["plain"])]
    maps = [(label, task_outcomes(attempt)) for label, attempt in candidates]
    selected = choose_sources(maps, ids)
    destination = out / "terminal-union"
    shutil.copytree(source, destination)
    workspaces = {label: Path(attempt.workspace) for label, attempt in candidates}
    for item in manifest["tasks"]:
        for filename in item["solutionFiles"]:
            relative = Path(item["relativePath"]) / filename
            (destination / relative).write_bytes((workspaces[selected[item["taskId"]]] / relative).read_bytes())
    evaluated = run_evaluator(task.public_test_command, destination)
    expected = {task_id: any(outcomes[task_id] for _, outcomes in maps) for task_id in ids}
    if evaluated["taskOutcomes"] != expected:
        raise ValueError("materialized union changed task outcomes")
    report = {
        "cell": cell, "candidatePassed": sum(final_outcomes.values()), "taskCount": len(ids),
        "systemPassed": evaluated["passed"], "systemTaskOutcomes": expected,
        "candidateTaskOutcomes": final_outcomes,
        "fourCallFloor": sum(any(outcomes[i] for _, outcomes in maps[1:]) for i in ids),
        "selectedSources": selected, "compute": {label: usage(attempt) for label, attempt in candidates},
        "materializedEvaluation": evaluated,
    }
    (out / "system-result.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ["cell", "candidatePassed", "systemPassed", "taskCount", "fourCallFloor"]}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
