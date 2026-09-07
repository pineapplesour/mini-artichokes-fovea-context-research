#!/usr/bin/env python3
"""Test partial-obligation crossover from an identical all-generic verified seed."""
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

from tools import run_aider_shared_failure_overlap as base


A = "obligation_view_v1_case_local"
B = "obligation_view_v1_case_local_b"
PARENTS = [*base.LABELS, A, B]
SEED_REPORT_SHA = "324037da6b6766d01516ee2f2c7b5bd2526905c0df2bff4c32fde3ba5b8cd7ed"
GENERIC = """Use strong general execution-feedback repair. Freely inspect, compare, copy,
combine or synthesize any provided candidate implementation. Choose your own
reasoning strategy using all supplied case outcomes, source, original
requirements, overlap graph and donor evidence. Localize the general cause of
remaining failures, consider alternatives, and preserve working behavior.
Prioritize changes likely to close complete tasks. Use actual-source checks
when useful and do not hard-code the displayed test examples."""
OVERLAP = """Use coverage-directed semantic crossover to combine partial correctness.
For each unresolved task, inspect shared passing obligations, exclusive passes,
and shared failures across candidate implementations. Start with pairs whose
different passing obligations can cover a larger part of the task. Localize
the actual source fragment and dependencies responsible for each donor's
exclusive success; a passing case is not proof that its entire implementation
is correct. Compare the donor fragment with the recipient under their shared
passing obligations. Transfer or adapt only the behavior needed to satisfy
the missing obligation while preserving the shared supported behavior.

Maintain one coherent implementation: reconcile variable/state conventions,
initialization, boundary rules and dependencies instead of blindly splicing
methods. Check interacting edits together. Resolve shared failures using the
specification and supplied failure evidence, synthesizing a general repair
where neither donor suffices. No vote or code-line intersection authorizes a
repair. Unknown reports provide no support. Candidate-relatedness is not
independent corroboration. Use small actual-source checks for consequential
interactions. The final ledger should name the donor/recipient fragments and
the obligations preserved or repaired, or the concrete reason no donor works.
Do not let an elaborate ledger displace actual source repair."""
COMMON = """Repair ALL 47 tasks in this complete official Java track. Both policies start
from the same re-evaluated 22-task verified portfolio of five GENERIC parent
executions: Plain, Graph, ordinary repair, case-local A and case-local B.
A and B are separate repairs of the same ordinary candidate, not independent
votes. Their exact IDs and all parent patches/outcomes are listed in
/tmp/artifacts/evidence-index.json. Full public candidate source snapshots are
under /tmp/artifacts/candidates/<candidate-id>/.

Read /tmp/artifacts/crossover-index.json first. It lists every task, its anchor
status, and a separate per-task JSON path with complete bounded failure
messages, the case-status matrix and shared/exclusive passing-case edges.
Open those small per-task files instead of dumping the entire large feedback
packet. BOTH policies receive and may use ALL the same graph and raw evidence.
The graph is an observation index, not a proof of composability or correctness.
Test source and reference solutions remain hidden. The common seed's anchor
map is /tmp/artifacts/verified-anchors.json. Previously passing complete states
will be retained by the same terminal selector for both policies.

{policy}

Focus effort on unresolved tasks, without dropping any task from the complete
inventory. Edit ONLY each task's listed solution files; never change unlisted
supporting classes, tests, infrastructure or supplied evidence. Use existing
supporting APIs. Put temporary source copies, drivers and build products under
/tmp outside the repository. No network, benchmark/answer lookup, hidden test
source or external answers. Use only declared dependencies and local tools.

Write /tmp/artifacts/decision_ledger.json with exactly one short row per task:
taskId, hypothesis, check, observation, action. Cite concrete case/source IDs;
distinguish executed checks from untested reasoning. For anchors record
preservation. Before finishing, inspect the actual final diff and independently
recheck original requirements against the final code. Repair contradictions.
The hard budget is 900 seconds for the entire track, not per task. Preserve
the shared completion reserve appended below. Return final code and the short
complete ledger, not a long explanation.

Original task:
"""


def overlap_edges(row: dict) -> list[dict]:
    labels = row["candidateOrder"]
    matrix = row["caseStatus"]
    observed = {l: {k for k, s in matrix.items() if s[j] != "not_reported"}
                for j, l in enumerate(labels)}
    passing = {l: {k for k, s in matrix.items() if s[j] == "passed"}
               for j, l in enumerate(labels)}
    failing = {l: {k for k, s in matrix.items() if s[j] in {"failed", "error"}}
               for j, l in enumerate(labels)}
    result = []
    for left, right in itertools.combinations(labels, 2):
        aligned = bool(observed[left]) and observed[left] == observed[right]
        union = passing[left] | passing[right]
        result.append({"parents": [left, right], "observedInventoriesAligned": aligned,
            "sharedPassingCases": sorted(passing[left] & passing[right]),
            "leftExclusiveVerifiedPasses": sorted(passing[left] & failing[right]),
            "rightExclusiveVerifiedPasses": sorted(passing[right] & failing[left]),
            "sharedFailures": sorted(failing[left] & failing[right]),
            "observedUnionBeyondBest": len(union) - max(len(passing[left]), len(passing[right])) if aligned else None,
            "observedUnionCoversInventory": aligned and union == observed[left],
            "independentVotes": False})
    return result


def validate_seed(root: Path) -> dict:
    directory = root / "portfolios/obligation_view_v1"
    path = directory / "homogeneous.json"
    if base.digest(path) != SEED_REPORT_SHA:
        raise ValueError("frozen generic seed report changed")
    report = json.loads(path.read_text())
    manifest = json.loads((root / "freeze/source/benchmark_manifest.json").read_text())
    ids = {t["taskId"] for t in manifest["tasks"]}
    allowed = {str(Path(t["relativePath"]) / f) for t in manifest["tasks"] for f in t["solutionFiles"]}
    if (set(report["solutionHashes"]) != allowed or set(report["taskOutcomes"]) != ids
            or len(ids) != 47 or report["passed"] != 22 or sum(report["taskOutcomes"].values()) != 22
            or report["materializedEvaluation"]["taskOutcomes"] != report["taskOutcomes"]
            or set(report["selectedSources"]) != ids or not set(report["selectedSources"].values()) <= set(PARENTS)
            or report["totalCompute"]["logicalExecutions"] != 5):
        raise ValueError("seed inventory or accounting differs")
    if set(report["compute"]) != set(PARENTS):
        raise ValueError("seed must contain only the frozen generic parents")
    for relative, digest in report["solutionHashes"].items():
        if base.digest(directory / "homogeneous" / relative) != digest:
            raise ValueError(f"seed source changed: {relative}")
    return report


def stage_graph(artifact: Path, seed: dict) -> dict:
    feedback = json.loads((artifact / "case-feedback.json").read_text())
    if set(feedback) != set(seed["taskOutcomes"]):
        raise ValueError("feedback and seed task inventories differ")
    views = artifact / "crossover-tasks"
    views.mkdir()
    index = []
    for number, (task_id, row) in enumerate(sorted(feedback.items())):
        if row["candidateOrder"] != PARENTS:
            raise ValueError("unexpected candidate or original overlap output in inputs")
        edges = overlap_edges(row)
        name = f"{number:03d}.json"
        (views / name).write_text(json.dumps({"taskId": task_id, **row, "overlapEdges": edges},
                                             ensure_ascii=False, indent=2) + "\n")
        index.append({"taskId": task_id, "verifiedAnchor": seed["taskOutcomes"][task_id],
            "feedback": "/tmp/artifacts/crossover-tasks/" + name,
            "maxObservedUnionBeyondBest": max((e["observedUnionBeyondBest"] or 0) for e in edges)})
    (artifact / "crossover-index.json").write_text(json.dumps(index, indent=2) + "\n")
    (artifact / "verified-anchors.json").write_text(json.dumps({"taskOutcomes": seed["taskOutcomes"],
        "selectedSources": seed["selectedSources"], "seedReportSha256": SEED_REPORT_SHA}, indent=2) + "\n")
    return {"mechanism": "partial-obligation-crossover-v1", "parentIds": PARENTS,
        "seedReportSha256": SEED_REPORT_SHA, "experimentRunnerSha256": base.digest(Path(__file__)),
        "caseInformationShared": True, "independentVotes": False}


def transform_prompt(prompt: str, policy: str) -> str:
    if policy not in {"generic", "overlap"}:
        raise ValueError(policy)
    tail = prompt.split("\nOriginal task:\n", 1)[1]
    return COMMON.replace("{policy}", GENERIC if policy == "generic" else OVERLAP) + tail


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--policy", required=True, choices=["generic", "overlap"])
    args = parser.parse_args()
    root = args.run_root.resolve()
    seed = validate_seed(root)
    captures = root / "diagnostics/partial-finals-v1"
    return base.main(["--run-root", str(root), "--policy", args.policy,
        "--candidate-id", "partial_crossover_v1_" + args.policy, "--completion-reserve-seconds", "180"],
        extra_parents={label: captures / (label + ".json") for label in [A, B]},
        seed_directory=root / "portfolios/obligation_view_v1/homogeneous",
        artifact_transform=lambda artifact: stage_graph(artifact, seed),
        prompt_transform=lambda prompt: transform_prompt(prompt, args.policy))


if __name__ == "__main__":
    raise SystemExit(main())
