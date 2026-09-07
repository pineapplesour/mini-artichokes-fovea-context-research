#!/usr/bin/env python3
"""Score the review-triggered generic-repair control on five frozen Java20 sessions."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics
from pathlib import Path
from typing import Any


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
    rows = [
        json.loads(line)
        for line in payload["public_test"]["stdout"].splitlines()
        if line.strip() and not json.loads(line).get("summary")
    ]
    if len(rows) != 20 or len({row["taskId"] for row in rows}) != 20:
        raise ValueError(f"{root.name}/{arm}: invalid 20-task denominator")
    outcomes = {str(row["taskId"]): bool(row["passed"]) for row in rows}
    accepted = (
        payload["agent"]["exit_code"] == 0
        and not payload["agent"]["timed_out"]
        and not payload["forbidden_files"]
    )
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
    two_sided = min(1.0, 2 * min(one_sided, 1 - one_sided + math.comb(n, positives) / 2**n)) if n else 1.0
    return {
        "positiveSessions": positives,
        "tiedSessions": len(differences) - n,
        "negativeSessions": negatives,
        "nonzeroSessions": n,
        "oneSidedExactP": one_sided,
        "twoSidedExactP": two_sided,
    }


def session_bootstrap(differences: list[int], samples: int = 100_000) -> dict[str, Any]:
    rng = random.Random("aider-java20-ordinary-control-bootstrap-20260902")
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
    differences = []
    rescues = 0
    harms = 0
    for name in EXPECTED_SESSIONS:
        root = args.runs_root.resolve() / name
        matched = load_arm(root, "matched_repair")
        ordinary = load_arm(root, "ordinary_repair")
        if set(matched["taskOutcomes"]) != set(ordinary["taskOutcomes"]):
            raise ValueError(f"{name}: matched-control task identities differ")
        difference = matched["passed"] - ordinary["passed"]
        differences.append(difference)
        rescues += sum(
            matched["taskOutcomes"][key] and not ordinary["taskOutcomes"][key]
            for key in matched["taskOutcomes"]
        )
        harms += sum(
            ordinary["taskOutcomes"][key] and not matched["taskOutcomes"][key]
            for key in matched["taskOutcomes"]
        )
        sessions.append(
            {
                "session": name,
                "matchedRepair": matched,
                "ordinaryRepair": ordinary,
                "matchedMinusOrdinaryCorrect": difference,
            }
        )

    result = {
        "schemaVersion": 1,
        "design": "review-triggered one-call generic-repair control added to five frozen Java20 Graph sessions",
        "controlAddedAfterMatchedResultsWereKnown": True,
        "inferentialStatus": "secondary matched-control diagnostic, not a fresh confirmatory treatment comparison",
        "benchmarkFreezeSha256": EXPECTED_FREEZE_SHA256,
        "benchmarkTaskSha256": EXPECTED_TASK_SHA256,
        "sessions": sessions,
        "comparison": {
            "contrast": "matched structured repair minus ordinary one-call repair",
            "sessionCorrectDifferences": differences,
            "meanPercentagePointDifference": 100 * statistics.mean(differences) / 20,
            "medianPercentagePointDifference": 100 * statistics.median(differences) / 20,
            "sessionExactSign": exact_sign(differences),
            "pairedSessionBootstrap95PctCI": session_bootstrap(differences),
            "descriptiveRepeatedTaskOutcomes": {
                "taskSessionN": 100,
                "rescues": rescues,
                "harms": harms,
                "net": rescues - harms,
                "claimBoundary": "The same 20 tasks recur and are not 100 independent tasks.",
            },
        },
        "claimBoundary": [
            "Both repair arms use one new call from the identical session-specific Graph patch and official failure stdout.",
            "The extension tests the bundled structured operations against a short generic repair instruction, not any single component.",
            "Because the control was commissioned after matched-repair results were known, all inference is secondary.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical(result))
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
