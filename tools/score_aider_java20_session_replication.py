#!/usr/bin/env python3
"""Score the five predeclared Java20 whole-session replications."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics
from pathlib import Path
from typing import Any


ARMS = ("plain", "graph", "matched_repair")
EXPECTED_SESSIONS = tuple(
    f"aider-hidden-java20-session-replication-{index:02d}"
    for index in range(1, 6)
)
EXPECTED_TASK_SHA256 = "69e2e1d2220ff21651d7ac266ab0828695a769c4740dbc2b85baa0b0a9981942"
EXPECTED_FREEZE_SHA256 = "b12e7d7a4904084b35cae8bca1f492d9173a46d7ee6c8dcfe8165cd3a27111c0"


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def usage(stdout: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "turn.completed" and isinstance(event.get("usage"), dict):
            result = {str(key): int(value) for key, value in event["usage"].items()}
    return result


def load_arm(root: Path, arm: str) -> dict[str, Any]:
    result_path = root / arm / "result.json"
    if not result_path.is_file():
        return {
            "status": "missing_or_incomplete",
            "passed": 0,
            "total": 20,
            "taskOutcomes": {},
            "artifact": str(result_path),
        }
    payload = json.loads(result_path.read_text(encoding="utf-8"))["attempt"]
    rows = []
    for line in payload["public_test"]["stdout"].splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if not item.get("summary"):
            rows.append(item)
    if len(rows) != 20 or len({row["taskId"] for row in rows}) != 20:
        raise ValueError(f"{root.name}/{arm}: invalid 20-task denominator")
    outcomes = {str(row["taskId"]): bool(row["passed"]) for row in rows}
    agent_complete = payload["agent"]["exit_code"] == 0 and not payload["agent"]["timed_out"]
    safe = not payload["forbidden_files"]
    accepted = agent_complete and safe
    return {
        "status": "accepted" if accepted else "unsafe_or_incomplete",
        "passed": sum(outcomes.values()) if accepted else 0,
        "total": 20,
        "taskOutcomes": outcomes if accepted else {},
        "agentSeconds": payload["agent"]["duration_seconds"],
        "patchLines": payload["patch_lines"],
        "usage": usage(payload["agent"]["stdout"]),
        "artifact": str(result_path),
        "artifactSha256": digest(result_path),
    }


def exact_sign(differences: list[int]) -> dict[str, Any]:
    nonzero = [value for value in differences if value != 0]
    positives = sum(value > 0 for value in nonzero)
    negatives = sum(value < 0 for value in nonzero)
    n = len(nonzero)
    one_sided = (
        sum(math.comb(n, index) for index in range(positives, n + 1)) / 2**n
        if n
        else 1.0
    )
    return {
        "positiveSessions": positives,
        "tiedSessions": len(differences) - n,
        "negativeSessions": negatives,
        "nonzeroSessions": n,
        "oneSidedExactP": one_sided,
    }


def session_bootstrap(differences: list[int], samples: int = 100_000) -> dict[str, Any]:
    rng = random.Random("aider-java20-five-session-bootstrap-20260902")
    values = sorted(
        sum(differences[rng.randrange(len(differences))] for _ in differences)
        / (len(differences) * 20)
        for _ in range(samples)
    )
    return {
        "estimatePercentagePoints": 100 * sum(differences) / (len(differences) * 20),
        "lower95PercentagePoints": 100 * values[int(0.025 * samples)],
        "upper95PercentagePoints": 100 * values[min(samples - 1, int(0.975 * samples))],
        "samples": samples,
        "unit": "whole session; frozen 20-task set",
    }


def comparison(sessions: list[dict[str, Any]], left: str, right: str) -> dict[str, Any]:
    differences = [session["arms"][left]["passed"] - session["arms"][right]["passed"] for session in sessions]
    task_rescues = 0
    task_harms = 0
    complete_pairs = 0
    for session in sessions:
        left_outcomes = session["arms"][left]["taskOutcomes"]
        right_outcomes = session["arms"][right]["taskOutcomes"]
        if set(left_outcomes) != set(right_outcomes) or len(left_outcomes) != 20:
            continue
        complete_pairs += 1
        task_rescues += sum(left_outcomes[key] and not right_outcomes[key] for key in left_outcomes)
        task_harms += sum(right_outcomes[key] and not left_outcomes[key] for key in left_outcomes)
    return {
        "sessionCorrectDifferences": differences,
        "meanPercentagePointDifference": 100 * statistics.mean(differences) / 20,
        "medianPercentagePointDifference": 100 * statistics.median(differences) / 20,
        "sessionExactSign": exact_sign(differences),
        "pairedSessionBootstrap95PctCI": session_bootstrap(differences),
        "descriptiveRepeatedTaskOutcomes": {
            "completeSessionPairs": complete_pairs,
            "taskSessionN": complete_pairs * 20,
            "rescues": task_rescues,
            "harms": task_harms,
            "net": task_rescues - task_harms,
            "claimBoundary": "The same 20 tasks recur; these 100 outcomes are not independent tasks.",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark-root", required=True, type=Path)
    parser.add_argument("--runs-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    benchmark_root = args.benchmark_root.resolve()
    if digest(benchmark_root / "freeze.json") != EXPECTED_FREEZE_SHA256:
        raise ValueError("frozen Java20 receipt changed")
    if digest(benchmark_root / "public" / "task.json") != EXPECTED_TASK_SHA256:
        raise ValueError("frozen Java20 task changed")
    sessions = []
    for name in EXPECTED_SESSIONS:
        root = args.runs_root.resolve() / name
        sessions.append({"session": name, "arms": {arm: load_arm(root, arm) for arm in ARMS}})
    task_sets = {
        tuple(sorted(arm["taskOutcomes"]))
        for session in sessions
        for arm in session["arms"].values()
        if arm["taskOutcomes"]
    }
    if len(task_sets) > 1:
        raise ValueError("replication task identities differ")
    matched_plain = comparison(sessions, "matched_repair", "plain")
    matched_graph = comparison(sessions, "matched_repair", "graph")
    h1 = matched_plain["sessionExactSign"]["oneSidedExactP"] < 0.05
    result = {
        "schemaVersion": 1,
        "design": "five new independently initialized whole-batch sessions on one frozen official Java20 set",
        "priorJavaSessionExcludedFromConfirmatoryTests": True,
        "benchmarkFreezeSha256": EXPECTED_FREEZE_SHA256,
        "benchmarkTaskSha256": EXPECTED_TASK_SHA256,
        "sessions": sessions,
        "comparisons": {
            "matchedVsPlain": matched_plain,
            "matchedVsGraph": matched_graph,
        },
        "fixedSequence": [
            {"hypothesis": "matched_repair > plain", "reached": True, "rejectedAtOneSidedAlpha0.05": h1},
            {
                "hypothesis": "matched_repair > graph",
                "reached": h1,
                "rejectedAtOneSidedAlpha0.05": bool(
                    h1 and matched_graph["sessionExactSign"]["oneSidedExactP"] < 0.05
                ),
            },
        ],
        "claimBoundary": [
            "The confirmatory unit is the independently initialized whole-batch session.",
            "The task set is fixed, so the experiment establishes session repeatability on these 20 official tasks rather than new-task generality.",
            "The matched repair is a bundled structured second pass; no overlap-specific effect is claimed.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical(result))
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
