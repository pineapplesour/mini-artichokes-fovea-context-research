#!/usr/bin/env python3
"""Analyze the frozen JavaScript49 recursive verified-union campaign."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import shutil
from pathlib import Path
from typing import Any


ARM_PATHS = {
    "plain": ("plain", "plain"),
    "graph": ("graph", "graph"),
    "ordinary": ("ordinary_repair", "ordinary_repair"),
    "direct": ("direct", "direct"),
    "generic": ("generic", "generic"),
    "tov": ("tov", "tov"),
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_arm(root: Path, label: str) -> dict[str, Any]:
    directory, candidate = ARM_PATHS[label]
    path = root / directory / "attempts" / candidate / "result.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in payload["public_test"]["stdout"].splitlines()]
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
            usage = {key: int(value) for key, value in event.get("usage", {}).items()}
    safe = (
        payload["agent"]["exit_code"] == 0
        and not payload["agent"]["timed_out"]
        and not payload["forbidden_files"]
    )
    return {
        "artifact": str(path),
        "artifactSha256": sha256_file(path),
        "workspace": payload["workspace"],
        "safe": safe,
        "passed": sum(outcomes.values()),
        "total": len(outcomes),
        "accuracy": sum(outcomes.values()) / len(outcomes),
        "taskOutcomes": outcomes,
        "agentSeconds": payload["agent"]["duration_seconds"],
        "patchLines": payload["patch_lines"],
        "patchSha256": payload["patch_sha256"],
        "usage": usage,
    }


def exact_mcnemar(rescue: int, harm: int) -> dict[str, float | int]:
    discordant = rescue + harm
    if not discordant:
        return {"rescue": rescue, "harm": harm, "discordant": 0, "oneSidedP": 1.0, "twoSidedP": 1.0}
    denominator = 2**discordant
    upper = sum(math.comb(discordant, k) for k in range(rescue, discordant + 1)) / denominator
    lower = sum(math.comb(discordant, k) for k in range(rescue + 1)) / denominator
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
    lo, hi = math.floor(position), math.ceil(position)
    if lo == hi:
        return ordered[lo]
    weight = position - lo
    return ordered[lo] * (1.0 - weight) + ordered[hi] * weight


def pair(control: dict[str, bool], treatment: dict[str, bool]) -> dict[str, Any]:
    if set(control) != set(treatment):
        raise ValueError("paired task IDs differ")
    task_ids = sorted(control)
    rescued = [task for task in task_ids if treatment[task] and not control[task]]
    harmed = [task for task in task_ids if control[task] and not treatment[task]]
    differences = [int(treatment[task]) - int(control[task]) for task in task_ids]
    rng = random.Random(20_260_904)
    samples = [
        100.0 * sum(differences[rng.randrange(len(task_ids))] for _ in task_ids) / len(task_ids)
        for _ in range(50_000)
    ]
    return {
        "rescuedTaskIds": rescued,
        "harmedTaskIds": harmed,
        "netTasks": len(rescued) - len(harmed),
        "percentagePointDifference": 100.0 * sum(differences) / len(task_ids),
        "exactMcNemar": exact_mcnemar(len(rescued), len(harmed)),
        "taskLevelPairedBootstrap95PctCI": [percentile(samples, 0.025), percentile(samples, 0.975)],
    }


def union(*outcomes: dict[str, bool]) -> dict[str, bool]:
    task_ids = set(outcomes[0])
    if any(set(item) != task_ids for item in outcomes[1:]):
        raise ValueError("union task IDs differ")
    return {task: any(item[task] for item in outcomes) for task in sorted(task_ids)}


def cumulative_usage(*arms: dict[str, Any]) -> dict[str, int | float]:
    keys = {key for arm in arms for key in arm["usage"]}
    result: dict[str, int | float] = {
        "calls": len(arms),
        "agentSeconds": sum(float(arm["agentSeconds"]) for arm in arms),
    }
    result.update({key: sum(int(arm["usage"].get(key, 0)) for arm in arms) for key in sorted(keys)})
    return result


def artifact_identity(root: Path) -> dict[str, Any]:
    names = (
        "evidence-index.json",
        "plain.patch",
        "plain.test-evidence.json",
        "graph.patch",
        "graph.test-evidence.json",
        "ordinary_repair.patch",
        "ordinary_repair.test-evidence.json",
        "verified-anchors.json",
    )
    hashes: dict[str, dict[str, str]] = {}
    for label in ("direct", "generic", "tov"):
        directory, candidate = ARM_PATHS[label]
        artifact_dir = root / directory / "attempts" / candidate
        hashes[label] = {name: sha256_file(artifact_dir / name) for name in names}
    return {
        "hashes": hashes,
        "allByteIdentical": all(
            len({hashes[label][name] for label in hashes}) == 1 for name in names
        ),
    }


def audit_anchors(root: Path, arms: dict[str, dict[str, Any]]) -> dict[str, Any]:
    anchor_path = root / "direct" / "attempts" / "direct" / "verified-anchors.json"
    anchors = json.loads(anchor_path.read_text(encoding="utf-8"))
    comparisons = 0
    mismatches: list[dict[str, str]] = []
    for item in anchors:
        selected = item["selectedVerifiedCandidate"]
        if not selected:
            continue
        source_label = "ordinary" if selected == "ordinary_repair" else selected
        source_workspace = Path(arms[source_label]["workspace"])
        for relative in item["anchoredSolutionFiles"]:
            expected = (source_workspace / relative).read_bytes()
            for label in ("direct", "generic", "tov"):
                comparisons += 1
                actual = (Path(arms[label]["workspace"]) / relative).read_bytes()
                if actual != expected:
                    mismatches.append({"arm": label, "path": relative})
    return {"comparisons": comparisons, "mismatches": mismatches, "allByteExact": not mismatches}


def materialize_system(
    *,
    source: Path,
    manifest: dict[str, Any],
    direct: dict[str, Any],
    replacement: dict[str, Any],
    destination: Path,
) -> list[dict[str, Any]]:
    if destination.exists():
        raise FileExistsError(destination)
    shutil.copytree(source, destination)
    decisions: list[dict[str, Any]] = []
    for item in manifest["tasks"]:
        task_id = item["taskId"]
        if direct["taskOutcomes"][task_id]:
            selected = "direct"
            workspace = Path(direct["workspace"])
        elif replacement["taskOutcomes"][task_id]:
            selected = "replacement"
            workspace = Path(replacement["workspace"])
        else:
            selected = "direct-fallback"
            workspace = Path(direct["workspace"])
        copied: list[str] = []
        for solution_file in item["solutionFiles"]:
            relative = (Path(item["relativePath"]) / solution_file).as_posix()
            (destination / relative).write_bytes((workspace / relative).read_bytes())
            copied.append(relative)
        decisions.append({"taskId": task_id, "selected": selected, "copiedSolutionFiles": copied})
    return decisions


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--union-root", required=True, type=Path)
    parser.add_argument("--starter-passed", type=int, default=1)
    args = parser.parse_args()
    root = args.campaign.resolve()
    arms = {label: load_arm(root, label) for label in ARM_PATHS}
    if not all(item["safe"] for item in arms.values()):
        raise ValueError("one or more scored calls are unsafe or incomplete")
    task_ids = set(arms["plain"]["taskOutcomes"])
    if any(set(item["taskOutcomes"]) != task_ids for item in arms.values()):
        raise ValueError("arm task IDs differ")

    floor = union(
        arms["plain"]["taskOutcomes"],
        arms["graph"]["taskOutcomes"],
        arms["ordinary"]["taskOutcomes"],
    )
    nonoverlap = union(arms["direct"]["taskOutcomes"], arms["generic"]["taskOutcomes"])
    mini = union(arms["direct"]["taskOutcomes"], arms["tov"]["taskOutcomes"])
    manifest = json.loads(args.manifest.resolve().read_text(encoding="utf-8"))
    if task_ids != {item["taskId"] for item in manifest["tasks"]}:
        raise ValueError("manifest/result task IDs differ")

    union_root = args.union_root.resolve()
    union_root.mkdir(parents=True, exist_ok=False)
    nonoverlap_decisions = materialize_system(
        source=args.source.resolve(),
        manifest=manifest,
        direct=arms["direct"],
        replacement=arms["generic"],
        destination=union_root / "direct-union-generic",
    )
    mini_decisions = materialize_system(
        source=args.source.resolve(),
        manifest=manifest,
        direct=arms["direct"],
        replacement=arms["tov"],
        destination=union_root / "direct-union-tov",
    )
    (union_root / "direct-union-generic.decisions.json").write_text(
        json.dumps(nonoverlap_decisions, indent=2) + "\n", encoding="utf-8"
    )
    (union_root / "direct-union-tov.decisions.json").write_text(
        json.dumps(mini_decisions, indent=2) + "\n", encoding="utf-8"
    )

    shared = (arms["plain"], arms["graph"], arms["ordinary"], arms["direct"])
    report = {
        "schemaVersion": 1,
        "taskCount": len(task_ids),
        "arms": arms,
        "scores": {
            "starter": {"passed": args.starter_passed, "total": len(task_ids)},
            "candidateFloor": {"passed": sum(floor.values()), "total": len(task_ids)},
            "nonOverlapSystem": {"passed": sum(nonoverlap.values()), "total": len(task_ids)},
            "miniArtichokes": {"passed": sum(mini.values()), "total": len(task_ids)},
        },
        "comparisons": {
            "miniVsNonOverlap": pair(nonoverlap, mini),
            "tovVsGeneric": pair(arms["generic"]["taskOutcomes"], arms["tov"]["taskOutcomes"]),
            "miniVsPlain": pair(arms["plain"]["taskOutcomes"], mini),
            "miniVsOrdinary": pair(arms["ordinary"]["taskOutcomes"], mini),
        },
        "compute": {
            "nonOverlapSystem": cumulative_usage(*shared, arms["generic"]),
            "miniArtichokes": cumulative_usage(*shared, arms["tov"]),
        },
        "evidenceIdentity": artifact_identity(root),
        "anchorAudit": audit_anchors(root, arms),
        "unionWorkspaces": {
            "nonOverlap": str(union_root / "direct-union-generic"),
            "miniArtichokes": str(union_root / "direct-union-tov"),
        },
        "limitations": [
            "The design matches calls and hard wall-clock caps, not realized token consumption.",
            "Task-level inference is conditional on six realized whole-track calls.",
            "One new language track does not by itself identify a language-population effect.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "scores": report["scores"],
                "primary": report["comparisons"]["miniVsNonOverlap"],
                "evidenceIdentical": report["evidenceIdentity"]["allByteIdentical"],
                "anchorsExact": report["anchorAudit"]["allByteExact"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
