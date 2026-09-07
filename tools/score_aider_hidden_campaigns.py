#!/usr/bin/env python3
"""Score two frozen official Aider hidden-test campaigns without re-running tests."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from pathlib import Path
from typing import Any


ARMS = ("plain", "graph", "ordinary_repair", "graph_overlap")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exact_mcnemar(rescue: int, harm: int) -> dict[str, float | int]:
    discordant = rescue + harm
    if discordant == 0:
        return {"rescue": rescue, "harm": harm, "discordant": 0, "oneSidedP": 1.0, "twoSidedP": 1.0}
    denominator = 2**discordant
    upper = sum(math.comb(discordant, k) for k in range(rescue, discordant + 1)) / denominator
    lower = sum(math.comb(discordant, k) for k in range(0, rescue + 1)) / denominator
    return {
        "rescue": rescue,
        "harm": harm,
        "discordant": discordant,
        "oneSidedP": upper,
        "twoSidedP": min(1.0, 2.0 * min(upper, lower)),
    }


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def paired_bootstrap_ci(
    differences: list[int], *, draws: int = 100_000, seed: int = 20_260_902
) -> list[float]:
    rng = random.Random(seed)
    size = len(differences)
    samples = [sum(differences[rng.randrange(size)] for _ in range(size)) / size for _ in range(draws)]
    return [100.0 * percentile(samples, 0.025), 100.0 * percentile(samples, 0.975)]


def load_arm(campaign: Path, arm: str) -> dict[str, Any]:
    path = campaign / arm / "attempts" / arm / "result.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in payload["public_test"]["stdout"].splitlines() if line.startswith("{")]
    outcomes = {row["taskId"]: bool(row["passed"]) for row in rows if not row.get("summary")}
    summaries = [row for row in rows if row.get("summary")]
    if len(summaries) != 1 or summaries[0]["passedCount"] != sum(outcomes.values()):
        raise ValueError(f"invalid evaluator summary: {path}")
    usage: dict[str, int] = {}
    for line in payload["agent"]["stdout"].splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "turn.completed":
            usage = event.get("usage", {})
    safe = (
        payload["agent"]["exit_code"] == 0
        and not payload["agent"]["timed_out"]
        and not payload["forbidden_files"]
    )
    return {
        "artifact": str(path),
        "artifactSha256": sha256_file(path),
        "safe": safe,
        "passed": sum(outcomes.values()),
        "total": len(outcomes),
        "accuracy": sum(outcomes.values()) / len(outcomes),
        "taskOutcomes": outcomes,
        "agentSeconds": payload["agent"]["duration_seconds"],
        "patchLines": payload["patch_lines"],
        "usage": usage,
    }


def pair(control: dict[str, bool], treatment: dict[str, bool]) -> dict[str, Any]:
    if set(control) != set(treatment):
        raise ValueError("paired arms do not have identical task IDs")
    ids = sorted(control)
    rescued = [task_id for task_id in ids if treatment[task_id] and not control[task_id]]
    harmed = [task_id for task_id in ids if control[task_id] and not treatment[task_id]]
    differences = [int(treatment[task_id]) - int(control[task_id]) for task_id in ids]
    stats = exact_mcnemar(len(rescued), len(harmed))
    return {
        "rescuedTaskIds": rescued,
        "harmedTaskIds": harmed,
        "netTasks": len(rescued) - len(harmed),
        "percentagePointDifference": 100.0 * sum(differences) / len(differences),
        "exactMcNemar": stats,
        "taskLevelPairedBootstrap95PctCI": paired_bootstrap_ci(differences),
    }


def cumulative_usage(*arms: dict[str, Any]) -> dict[str, int | float]:
    keys = {key for arm in arms for key in arm["usage"]}
    result: dict[str, int | float] = {
        "agentSeconds": sum(arm["agentSeconds"] for arm in arms),
        "calls": len(arms),
    }
    result.update({key: sum(int(arm["usage"].get(key, 0)) for arm in arms) for key in sorted(keys)})
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirmation", required=True, type=Path)
    parser.add_argument("--replication", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    campaigns: dict[str, dict[str, Any]] = {}
    for label, path in (("confirmation", args.confirmation), ("replication", args.replication)):
        frozen = json.loads((path / "freeze.json").read_text(encoding="utf-8"))
        arms = {arm: load_arm(path, arm) for arm in ARMS}
        ids = set(arms["plain"]["taskOutcomes"])
        if ids != set(frozen["selectedTaskIds"]):
            raise ValueError(f"freeze/result task mismatch in {label}")
        if not all(arm["safe"] for arm in arms.values()):
            raise ValueError(f"unsafe arm in {label}")
        campaigns[label] = {
            "path": str(path),
            "freezeSha256": sha256_file(path / "freeze.json"),
            "selectedTaskIds": frozen["selectedTaskIds"],
            "arms": arms,
            "comparisons": {
                "proposalVsPlain": pair(arms["plain"]["taskOutcomes"], arms["graph_overlap"]["taskOutcomes"]),
                "proposalVsGraph": pair(arms["graph"]["taskOutcomes"], arms["graph_overlap"]["taskOutcomes"]),
                "proposalVsOrdinaryRepair": pair(
                    arms["ordinary_repair"]["taskOutcomes"], arms["graph_overlap"]["taskOutcomes"]
                ),
            },
            "cumulative": {
                "graphPlusOrdinaryRepair": cumulative_usage(arms["graph"], arms["ordinary_repair"]),
                "graphPlusProposal": cumulative_usage(arms["graph"], arms["graph_overlap"]),
            },
        }

    first_ids = set(campaigns["confirmation"]["selectedTaskIds"])
    second_ids = set(campaigns["replication"]["selectedTaskIds"])
    if first_ids & second_ids:
        raise ValueError("confirmation and replication task IDs overlap")

    pooled_arms: dict[str, dict[str, bool]] = {}
    pooled_scores: dict[str, Any] = {}
    for arm in ARMS:
        outcomes = {
            **campaigns["confirmation"]["arms"][arm]["taskOutcomes"],
            **campaigns["replication"]["arms"][arm]["taskOutcomes"],
        }
        pooled_arms[arm] = outcomes
        pooled_scores[arm] = {
            "passed": sum(outcomes.values()),
            "total": len(outcomes),
            "accuracy": sum(outcomes.values()) / len(outcomes),
        }

    report = {
        "schemaVersion": 1,
        "benchmark": "Official Aider-AI/polyglot-benchmark hidden-test batches",
        "officialRepository": "https://github.com/Aider-AI/polyglot-benchmark",
        "inferenceUnit": "paired official task",
        "campaigns": campaigns,
        "pooled": {
            "taskCount": len(pooled_arms["plain"]),
            "disjointTaskIds": True,
            "scores": pooled_scores,
            "comparisons": {
                "proposalVsPlain": pair(pooled_arms["plain"], pooled_arms["graph_overlap"]),
                "proposalVsGraph": pair(pooled_arms["graph"], pooled_arms["graph_overlap"]),
                "proposalVsOrdinaryRepair": pair(pooled_arms["ordinary_repair"], pooled_arms["graph_overlap"]),
            },
        },
        "limitations": [
            "This is not the full 225-task Aider leaderboard run.",
            "Each 20-task batch shares one model call, so task-level inference can be optimistic under within-call dependence.",
            "There are two independent batch calls per arm; the task-level bootstrap is not a cluster-robust population guarantee.",
            "The proposal does not establish superiority over the same-budget ordinary repair control.",
            "The Rust-only replication corrected a language-specific task-packaging sentence that had incorrectly mentioned the Python standard library in confirmation Rust tasks; every arm within each batch received identical task bytes.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "pooled": report["pooled"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
