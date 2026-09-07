#!/usr/bin/env python3
"""Shared independently authored probes, then a matched final repair contrast."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

from harness_research.trace_gated_mini.core import TaskSpec, execute_attempt, to_jsonable
from tools.run_aider_hidden20_arm import IsolatedCodexAdapter, stage_adjudication_evidence, task_outcomes
from tools.run_aider_counterexample_overlap import choose_sources, validate_attempt, usage
from tools.run_aider_independent_probe import validate_probes
from tools.independent_probe_prompts import make_prompt
from tools.analyze_aider_online_offline_portfolio import run_evaluator


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--policy", required=True, choices=["generic", "overlap"])
    parser.add_argument("--candidate-id", help="Unique artifact ID for a separately frozen fresh execution.")
    args = parser.parse_args()
    root = args.run_root.resolve()
    source = root / "freeze/source"
    arms = root / "arms"
    task = TaskSpec.from_json(root / "freeze/public/task.json")
    manifest = json.loads((source / "benchmark_manifest.json").read_text())
    ids = {t["taskId"] for t in manifest["tasks"]}
    if len(ids) != len(manifest["tasks"]):
        raise ValueError("duplicate task IDs")
    author = arms / "probe_v1_author"
    receipt = json.loads((author / "receipt.json").read_text())
    probe_path = author / "artifacts" / receipt.get("probeFile", "probes.json")
    generator = json.loads((author / "result.json").read_text())
    if (not receipt.get("valid") or digest(probe_path) != receipt["probeSha256"]
            or generator["changedFiles"] or generator["agent"]["exit_code"] != 0
            or generator["agent"]["timed_out"]):
        raise ValueError("probe-author packet invalid")
    validate_probes(json.loads(probe_path.read_text()), ids)
    name = args.candidate_id or "probe_v1_" + args.policy
    if not name or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789_" for c in name):
        raise ValueError("invalid candidate artifact ID")
    out = arms / name
    if out.exists():
        raise FileExistsError(out)
    staged = stage_adjudication_evidence(arms, name)
    attempts = staged["attempts"]
    for attempt in attempts.values():
        validate_attempt(attempt, ids)
    artifact = out / "attempts" / name
    shutil.copyfile(probe_path, artifact / "probes.json")
    shutil.copyfile(source / "benchmark_manifest.json", artifact / "benchmark_manifest.json")
    shutil.copyfile(Path(__file__).with_name("probe_replay.py"), artifact / "probe_replay.py")
    # Public source only, never official tests or evaluator state.
    for candidate, attempt in attempts.items():
        for item in manifest["tasks"]:
            java = Path(item["relativePath"]) / "src/main/java"
            for path in sorted((Path(attempt.workspace) / java).rglob("*.java")):
                relative = path.relative_to(Path(attempt.workspace))
                target = artifact / "candidates" / candidate / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
    input_hashes = {str(p.relative_to(artifact)): digest(p)
                    for p in sorted(artifact.rglob("*")) if p.is_file()}
    ordinary = attempts["ordinary_repair"]
    prompt = make_prompt(task.instruction, args.policy)
    contract = {"policy": args.policy, "taskIds": sorted(ids), "model": "gpt-5.6-luna",
                "effort": "medium", "agentTimeoutSeconds": 900,
                "seedPatchSha256": ordinary.patch_sha256, "evidenceHashes": input_hashes,
                "promptSha256": hashlib.sha256(prompt.encode()).hexdigest(),
                "runnerSha256": digest(Path(__file__)), "probeAuthorReceipt": receipt,
                "interpretation": "exposed-task paired development; five logical executions"}
    (out / "contract.json").write_text(json.dumps(contract, indent=2) + "\n")
    result = execute_attempt(
        source_repo=source, task=task, output_dir=out, candidate_id=name,
        policy="independent_probe_" + args.policy, seed_patch=ordinary.patch_text,
        prompt_override=prompt, public_test_timeout_seconds=1800,
        adapter=IsolatedCodexAdapter(codex_home=Path("/home/pineapple/.codex-new-account"),
            model="gpt-5.6-luna", reasoning_effort="medium", timeout_seconds=900,
            java_root=Path("/home/pineapple/miniconda3/lib/jvm")),
    )
    (out / "result.json").write_text(json.dumps({"attempt": to_jsonable(result)}, indent=2) + "\n")
    final = validate_attempt(result, ids)
    if any(not (artifact / rel).is_file() or digest(artifact / rel) != sha
           for rel, sha in input_hashes.items()):
        raise ValueError("supplied evidence mutated; candidate retained but protocol invalid")
    ledger = json.loads((artifact / "decision_ledger.json").read_text())
    required = {"taskId", "hypothesis", "check", "observation", "action"}
    if (not isinstance(ledger, list) or len(ledger) != len(ids)
            or any(not isinstance(row, dict) or not required.issubset(row) for row in ledger)
            or {row["taskId"] for row in ledger} != ids):
        raise ValueError("incomplete decision ledger")
    candidates = [(name, result), ("ordinary_repair", ordinary),
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
    expected = {i: any(outcomes[i] for _, outcomes in maps) for i in ids}
    if evaluated["taskOutcomes"] != expected:
        raise ValueError("materialized system outcomes changed")
    compute = {label: usage(attempt) for label, attempt in candidates}
    compute["probe_author"] = usage(SimpleNamespace(agent=SimpleNamespace(**generator["agent"])))
    report = {"policy": args.policy, "taskCount": len(ids), "candidatePassed": sum(final.values()),
              "systemPassed": evaluated["passed"], "systemTaskOutcomes": expected,
              "candidateTaskOutcomes": final, "selectedSources": selected,
              "threeCandidateFloor": sum(any(o[i] for _, o in maps[1:]) for i in ids),
              "compute": compute, "probeAuthorReceipt": receipt,
              "materializedEvaluation": evaluated}
    (out / "system-result.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ["policy", "taskCount", "candidatePassed", "systemPassed", "threeCandidateFloor"]}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
