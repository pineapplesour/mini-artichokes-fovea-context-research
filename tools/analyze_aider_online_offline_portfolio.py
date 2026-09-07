#!/usr/bin/env python3
"""Materialize and analyze matched online-freeze/offline Aider portfolios."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import shutil
import subprocess
from pathlib import Path
from typing import Any


ARM_NAMES = {
    "plain": "plain",
    "ordinary": "ordinary_repair",
    "online_free": "semantic_free_structured_verified_union",
    "online_overlap": "semantic_overlap_verified_union",
    "offline_free": "semantic_free_structured_offline_portfolio",
    "offline_overlap": "semantic_overlap_offline_portfolio",
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def attempt_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload.get("attempt", payload)


def load_arm(root: Path, key: str) -> dict[str, Any]:
    arm = ARM_NAMES[key]
    top = root / arm / "result.json"
    path = top if top.is_file() else root / arm / "attempts" / arm / "result.json"
    payload = attempt_payload(path)
    outcomes: dict[str, bool] = {}
    summary = None
    for line in payload["public_test"]["stdout"].splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if item.get("summary"):
            summary = item
        elif item.get("taskId"):
            outcomes[str(item["taskId"])] = bool(item.get("passed"))
    if summary is None or int(summary["passedCount"]) != sum(outcomes.values()):
        raise ValueError(f"invalid evaluator result: {path}")
    safe = (
        payload["agent"]["exit_code"] == 0
        and not payload["agent"]["timed_out"]
        and not payload["forbidden_files"]
    )
    usage: dict[str, int] = {}
    for line in payload["agent"]["stdout"].splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "turn.completed":
            usage = {name: int(value) for name, value in event.get("usage", {}).items()}
    return {
        "arm": arm,
        "artifact": str(path),
        "artifactSha256": sha256_file(path),
        "workspace": payload["workspace"],
        "safe": safe,
        "passed": sum(outcomes.values()),
        "total": len(outcomes),
        "taskOutcomes": outcomes,
        "agentSeconds": float(payload["agent"]["duration_seconds"]),
        "usage": usage,
        "patchSha256": payload["patch_sha256"],
        "patchLines": int(payload["patch_lines"]),
    }


def union(first: dict[str, bool], second: dict[str, bool]) -> dict[str, bool]:
    if set(first) != set(second):
        raise ValueError("union task IDs differ")
    return {task_id: first[task_id] or second[task_id] for task_id in sorted(first)}


def exact_mcnemar(rescues: int, harms: int) -> dict[str, float | int]:
    discordant = rescues + harms
    if not discordant:
        return {"rescues": 0, "harms": 0, "discordant": 0, "oneSidedP": 1.0, "twoSidedP": 1.0}
    upper = sum(math.comb(discordant, value) for value in range(rescues, discordant + 1)) / 2**discordant
    lower = sum(math.comb(discordant, value) for value in range(rescues + 1)) / 2**discordant
    return {
        "rescues": rescues,
        "harms": harms,
        "discordant": discordant,
        "oneSidedP": upper,
        "twoSidedP": min(1.0, 2.0 * min(upper, lower)),
    }


def compare(control: dict[str, bool], treatment: dict[str, bool]) -> dict[str, Any]:
    if set(control) != set(treatment):
        raise ValueError("paired task IDs differ")
    rescues = sorted(task_id for task_id in control if treatment[task_id] and not control[task_id])
    harms = sorted(task_id for task_id in control if control[task_id] and not treatment[task_id])
    return {
        "rescuedTaskIds": rescues,
        "harmedTaskIds": harms,
        "netTasks": len(rescues) - len(harms),
        "percentagePointDifference": 100.0 * (len(rescues) - len(harms)) / len(control),
        "exactMcNemar": exact_mcnemar(len(rescues), len(harms)),
    }


def percentile(values: list[float], q: float) -> float:
    values = sorted(values)
    position = (len(values) - 1) * q
    lo, hi = math.floor(position), math.ceil(position)
    if lo == hi:
        return values[lo]
    weight = position - lo
    return values[lo] * (1 - weight) + values[hi] * weight


def stratified_bootstrap(
    track_pairs: list[tuple[dict[str, bool], dict[str, bool]]], *, seed: int, draws: int = 50_000
) -> list[float]:
    rng = random.Random(seed)
    strata: list[list[int]] = []
    total = 0
    for control, treatment in track_pairs:
        ids = sorted(control)
        if set(ids) != set(treatment):
            raise ValueError("bootstrap task IDs differ")
        strata.append([int(treatment[item]) - int(control[item]) for item in ids])
        total += len(ids)
    samples = []
    for _ in range(draws):
        net = sum(sum(values[rng.randrange(len(values))] for _ in values) for values in strata)
        samples.append(100.0 * net / total)
    return [percentile(samples, 0.025), percentile(samples, 0.975)]


def materialize(
    *, source: Path, manifest: dict[str, Any], first: dict[str, Any], second: dict[str, Any], destination: Path
) -> list[dict[str, Any]]:
    if destination.exists():
        raise FileExistsError(destination)
    shutil.copytree(source, destination)
    decisions = []
    for task in manifest["tasks"]:
        task_id = task["taskId"]
        if first["taskOutcomes"][task_id]:
            selected, workspace = first["arm"], Path(first["workspace"])
        elif second["taskOutcomes"][task_id]:
            selected, workspace = second["arm"], Path(second["workspace"])
        else:
            selected, workspace = first["arm"] + "-fallback", Path(first["workspace"])
        copied = []
        for name in task["solutionFiles"]:
            relative = (Path(task["relativePath"]) / name).as_posix()
            (destination / relative).write_bytes((workspace / relative).read_bytes())
            copied.append(relative)
        decisions.append({"taskId": task_id, "selected": selected, "copiedSolutionFiles": copied})
    return decisions


def run_evaluator(command: str, workspace: Path) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=workspace,
        shell=True,
        executable="/bin/bash",
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=1800,
        check=False,
    )
    outcomes = {}
    summary = None
    for line in completed.stdout.splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if item.get("summary"):
            summary = item
        elif item.get("taskId"):
            outcomes[str(item["taskId"])] = bool(item.get("passed"))
    if summary is None or int(summary["passedCount"]) != sum(outcomes.values()):
        raise ValueError(f"invalid materialized evaluation in {workspace}")
    return {
        "exitCode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "passed": sum(outcomes.values()),
        "total": len(outcomes),
        "taskOutcomes": outcomes,
    }


def evidence_identity(root: Path) -> dict[str, Any]:
    files = (
        "evidence-index.json",
        "plain.patch",
        "plain.test-evidence.json",
        "graph.patch",
        "graph.test-evidence.json",
        "ordinary_repair.patch",
        "ordinary_repair.test-evidence.json",
    )
    hashes: dict[str, dict[str, str]] = {}
    for key in ("online_free", "online_overlap", "offline_free", "offline_overlap"):
        arm = ARM_NAMES[key]
        directory = root / arm / "attempts" / arm
        hashes[key] = {name: sha256_file(directory / name) for name in files}
    return {
        "hashes": hashes,
        "allCommonEvidenceByteIdentical": all(
            len({hashes[key][name] for key in hashes}) == 1 for name in files
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--track", action="append", nargs=3, metavar=("NAME", "RUN_ROOT", "UNION_ROOT"), required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=20260905)
    args = parser.parse_args()

    track_reports = []
    pooled: dict[str, dict[str, bool]] = {name: {} for name in ARM_NAMES}
    pooled.update({"online_union": {}, "offline_union": {}})
    online_offline_pairs = []
    for track_name, run_root_raw, union_root_raw in args.track:
        run_root = Path(run_root_raw).resolve()
        arms = {key: load_arm(run_root / "arms", key) for key in ARM_NAMES}
        if not all(arm["safe"] for arm in arms.values()):
            raise ValueError(f"unsafe arm in {track_name}")
        ids = set(arms["plain"]["taskOutcomes"])
        if any(set(arm["taskOutcomes"]) != ids for arm in arms.values()):
            raise ValueError(f"arm task IDs differ in {track_name}")
        online = union(arms["online_overlap"]["taskOutcomes"], arms["online_free"]["taskOutcomes"])
        offline = union(arms["offline_overlap"]["taskOutcomes"], arms["offline_free"]["taskOutcomes"])
        manifest = json.loads((run_root / "freeze/source/benchmark_manifest.json").read_text(encoding="utf-8"))
        if ids != {task["taskId"] for task in manifest["tasks"]}:
            raise ValueError(f"manifest task IDs differ in {track_name}")
        task_spec = json.loads((run_root / "freeze/public/task.json").read_text(encoding="utf-8"))
        union_root = Path(union_root_raw).resolve()
        union_root.mkdir(parents=True, exist_ok=False)
        online_dir, offline_dir = union_root / "online", union_root / "offline"
        online_decisions = materialize(
            source=run_root / "freeze/source",
            manifest=manifest,
            first=arms["online_overlap"],
            second=arms["online_free"],
            destination=online_dir,
        )
        offline_decisions = materialize(
            source=run_root / "freeze/source",
            manifest=manifest,
            first=arms["offline_overlap"],
            second=arms["offline_free"],
            destination=offline_dir,
        )
        (union_root / "online.decisions.json").write_text(json.dumps(online_decisions, indent=2) + "\n", encoding="utf-8")
        (union_root / "offline.decisions.json").write_text(json.dumps(offline_decisions, indent=2) + "\n", encoding="utf-8")
        online_eval = run_evaluator(task_spec["public_test_command"], online_dir)
        offline_eval = run_evaluator(task_spec["public_test_command"], offline_dir)
        if online_eval["taskOutcomes"] != online or offline_eval["taskOutcomes"] != offline:
            raise ValueError(f"materialized union does not reproduce algebraic union in {track_name}")
        (union_root / "online.evaluation.jsonl").write_text(online_eval["stdout"], encoding="utf-8")
        (union_root / "offline.evaluation.jsonl").write_text(offline_eval["stdout"], encoding="utf-8")
        comparison = compare(online, offline)
        track_reports.append({
            "name": track_name,
            "taskCount": len(ids),
            "arms": arms,
            "scores": {
                "onlineUnion": sum(online.values()),
                "offlineUnion": sum(offline.values()),
                "plain": arms["plain"]["passed"],
                "ordinary": arms["ordinary"]["passed"],
            },
            "offlineVsOnline": comparison,
            "materialized": {"online": online_eval, "offline": offline_eval},
            "evidenceIdentity": evidence_identity(run_root / "arms"),
        })
        for key, arm in arms.items():
            pooled[key].update(arm["taskOutcomes"])
        pooled["online_union"].update(online)
        pooled["offline_union"].update(offline)
        online_offline_pairs.append((online, offline))

    primary = compare(pooled["online_union"], pooled["offline_union"])
    primary["trackStratifiedPairedBootstrap95PctCI"] = stratified_bootstrap(
        online_offline_pairs, seed=args.seed
    )
    report = {
        "schemaVersion": 1,
        "tracks": track_reports,
        "pooled": {
            "taskCount": len(pooled["online_union"]),
            "scores": {key: sum(values.values()) for key, values in pooled.items()},
            "comparisons": {
                "offlineVsOnline": primary,
                "offlineVsPlain": compare(pooled["plain"], pooled["offline_union"]),
                "offlineVsOrdinary": compare(pooled["ordinary"], pooled["offline_union"]),
                "offlineOverlapVsOnlineOverlap": compare(pooled["online_overlap"], pooled["offline_overlap"]),
                "offlineFreeVsOnlineFree": compare(pooled["online_free"], pooled["offline_free"]),
            },
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "pooled": report["pooled"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
