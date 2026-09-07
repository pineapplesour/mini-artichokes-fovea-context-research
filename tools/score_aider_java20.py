#!/usr/bin/env python3
"""Score the frozen Java20 arms and a bounded cross-batch family summary."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from pathlib import Path
from typing import Any


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exact(rescues: int, harms: int) -> dict[str, float | int]:
    total = rescues + harms
    if total == 0:
        one = two = 1.0
    else:
        one = sum(math.comb(total, k) for k in range(rescues, total + 1)) / 2**total
        two = min(1.0, 2 * sum(math.comb(total, k) for k in range(min(rescues, harms) + 1)) / 2**total)
    return {"rescues": rescues, "harms": harms, "discordant": total, "oneSidedP": one, "twoSidedP": two}


def bootstrap(deltas: list[int], strata: list[str], samples: int = 100_000) -> dict[str, Any]:
    groups: dict[str, list[int]] = {}
    for index, stratum in enumerate(strata):
        groups.setdefault(stratum, []).append(index)
    rng = random.Random("aider-java20-and-family-bootstrap-20260902")
    values: list[float] = []
    for _ in range(samples):
        total = 0
        for indices in groups.values():
            total += sum(deltas[indices[rng.randrange(len(indices))]] for _ in indices)
        values.append(total / len(deltas))
    values.sort()
    return {
        "estimate": sum(deltas) / len(deltas),
        "lower95": values[int(0.025 * samples)],
        "upper95": values[min(samples - 1, int(0.975 * samples))],
        "samples": samples,
        "stratification": "batch",
    }


def usage(stdout: str) -> dict[str, int]:
    found: dict[str, int] = {}
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "turn.completed" and isinstance(event.get("usage"), dict):
            found = {str(k): int(v) for k, v in event["usage"].items()}
    return found


def load_arm(root: Path, arm: str) -> dict[str, Any]:
    path = root / arm / "result.json"
    payload = json.loads(path.read_text(encoding="utf-8"))["attempt"]
    rows = [json.loads(line) for line in payload["public_test"]["stdout"].splitlines() if line.strip()]
    items = [row for row in rows if not row.get("summary")]
    if len(items) != 20 or len({row["taskId"] for row in items}) != 20:
        raise ValueError(f"invalid denominator for {arm}")
    outcomes = {str(row["taskId"]): bool(row["passed"]) for row in items}
    return {
        "artifact": str(path),
        "artifactSha256": digest(path),
        "passed": sum(outcomes.values()),
        "total": len(outcomes),
        "accuracy": sum(outcomes.values()) / len(outcomes),
        "taskOutcomes": outcomes,
        "agentSeconds": payload["agent"]["duration_seconds"],
        "patchLines": payload["patch_lines"],
        "usage": usage(payload["agent"]["stdout"]),
    }


def compare(left: dict[str, bool], right: dict[str, bool], strata: dict[str, str]) -> dict[str, Any]:
    ids = list(left)
    if set(ids) != set(right):
        raise ValueError("comparison IDs differ")
    rescued = [case_id for case_id in ids if left[case_id] and not right[case_id]]
    harmed = [case_id for case_id in ids if right[case_id] and not left[case_id]]
    deltas = [int(left[case_id]) - int(right[case_id]) for case_id in ids]
    return {
        "rescuedTaskIds": rescued,
        "harmedTaskIds": harmed,
        "netTasks": len(rescued) - len(harmed),
        "percentagePointDifference": 100 * sum(deltas) / len(deltas),
        "exactMcNemar": exact(len(rescued), len(harmed)),
        "taskLevelPairedBootstrap95PctCI": {
            key: (100 * value if key in {"estimate", "lower95", "upper95"} else value)
            for key, value in bootstrap(deltas, [strata[case_id] for case_id in ids]).items()
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--java-root", required=True, type=Path)
    parser.add_argument("--prior-evidence", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    arms = {name: load_arm(args.java_root, name) for name in (
        "plain", "graph", "matched_repair", "overlap_repair_v2"
    )}
    java_strata = {case_id: "java20" for case_id in arms["plain"]["taskOutcomes"]}
    java_comparisons = {
        "matchedVsPlain": compare(arms["matched_repair"]["taskOutcomes"], arms["plain"]["taskOutcomes"], java_strata),
        "matchedVsGraph": compare(arms["matched_repair"]["taskOutcomes"], arms["graph"]["taskOutcomes"], java_strata),
        "overlapVsPlain": compare(arms["overlap_repair_v2"]["taskOutcomes"], arms["plain"]["taskOutcomes"], java_strata),
        "overlapVsGraph": compare(arms["overlap_repair_v2"]["taskOutcomes"], arms["graph"]["taskOutcomes"], java_strata),
        "overlapVsMatched": compare(arms["overlap_repair_v2"]["taskOutcomes"], arms["matched_repair"]["taskOutcomes"], java_strata),
    }

    prior = json.loads(args.prior_evidence.read_text(encoding="utf-8"))
    family_left: dict[str, bool] = {}
    family_plain: dict[str, bool] = {}
    family_graph: dict[str, bool] = {}
    family_strata: dict[str, str] = {}
    batch_rows: list[dict[str, Any]] = []
    for batch in ("confirmation", "replication"):
        source = prior["campaigns"][batch]["arms"]
        left = source["graph_overlap"]["taskOutcomes"]
        plain = source["plain"]["taskOutcomes"]
        graph = source["graph"]["taskOutcomes"]
        family_left.update(left); family_plain.update(plain); family_graph.update(graph)
        family_strata.update({case_id: batch for case_id in left})
        batch_rows.append({"batch": batch, "system": sum(left.values()), "plain": sum(plain.values()), "graph": sum(graph.values())})
    family_left.update(arms["matched_repair"]["taskOutcomes"])
    family_plain.update(arms["plain"]["taskOutcomes"])
    family_graph.update(arms["graph"]["taskOutcomes"])
    family_strata.update({case_id: "java20" for case_id in arms["matched_repair"]["taskOutcomes"]})
    if len(family_left) != 60:
        raise ValueError("family denominator is not 60 unique tasks")
    batch_rows.append({
        "batch": "java20", "system": arms["matched_repair"]["passed"],
        "plain": arms["plain"]["passed"], "graph": arms["graph"]["passed"],
    })
    family = {
        "scope": "descriptive family summary; the repair lead was strengthened before the frozen Java batch",
        "batches": batch_rows,
        "systemCorrect": sum(family_left.values()),
        "plainCorrect": sum(family_plain.values()),
        "graphCorrect": sum(family_graph.values()),
        "n": 60,
        "systemVsPlain": compare(family_left, family_plain, family_strata),
        "systemVsGraph": compare(family_left, family_graph, family_strata),
        "wholeBatchCallClustersPerArm": 3,
        "allThreeBatchNetEffectsPositive": all(row["system"] > row["plain"] for row in batch_rows),
        "oneSidedThreeClusterSignP": 0.125,
    }
    result = {
        "schemaVersion": 1,
        "benchmark": "Official Aider-AI/polyglot-benchmark hidden-test Java20 and prior disjoint batches",
        "javaFreezeSha256": digest(args.java_root / "freeze.json"),
        "evaluatorSha256": digest(Path(__file__).with_name("evaluate_aider_hidden_java20.py")),
        "starterCorrect": 1,
        "java": {"arms": arms, "comparisons": java_comparisons},
        "crossBatchStructuredRepairFamily": family,
        "claimBoundary": [
            "The fresh Java matched repair improved by 20 percentage points but its 4:0 discordance is not individually significant at two-sided alpha .05.",
            "The 60-task task-level exact result conditions on only three whole-batch call clusters and is not cluster-robust population evidence.",
            "Strict overlap authorization underperformed matched structured repair on Java20, so no overlap-specific advantage is claimed.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical(result))
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

