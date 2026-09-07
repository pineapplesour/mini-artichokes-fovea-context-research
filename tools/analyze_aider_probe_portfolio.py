#!/usr/bin/env python3
"""Materialize the frozen heterogeneous and repeated-generic Java47 systems."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from harness_research.trace_gated_mini.core import TaskSpec
from tools.run_aider_counterexample_overlap import choose_sources, read_attempt, validate_attempt
from tools.analyze_aider_online_offline_portfolio import compare, run_evaluator


def read(path: Path):
    return json.loads(path.read_text())


def sha(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def aggregate_compute(compute: dict) -> dict:
    result = {"agentSeconds": sum(v["agentSeconds"] for v in compute.values()),
              "logicalExecutions": len(compute), "usage": {}}
    for record in compute.values():
        for key, value in record["usage"].items():
            result["usage"][key] = result["usage"].get(key, 0) + value
    return result


def check_contracts(contracts: dict, labels: list[str], study: str) -> None:
    fields = ["seedPatchSha256", "taskIds", "model", "effort", "agentTimeoutSeconds"]
    if study == "obligation_view_v1":
        fields += ["completionReserveSeconds", "captureHashes", "runnerSha256", "promptTemplateSha256"]
    else:
        fields += ["evidenceHashes"]
    reference = contracts[labels[0]]
    for label in labels:
        contract = contracts[label]
        for field in fields:
            if contract[field] != reference[field]:
                raise ValueError(f"unmatched {field}: {label}")
        if study == "obligation_view_v1":
            original = {k: v for k, v in contract["evidenceHashes"].items() if k != "repair-view.json"}
            expected = {k: v for k, v in reference["evidenceHashes"].items() if k != "repair-view.json"}
            if original != expected:
                raise ValueError("original input evidence differs")
            for field in ["failureRecords", "canonicalFailureRecordsSha256", "normalizerSha256", "experimentRunnerSha256"]:
                if contract["experiment"][field] != reference["experiment"][field]:
                    raise ValueError(f"unmatched experiment {field}")
    overlap, common, repeated = [contracts[label] for label in labels]
    if study == "obligation_view_v1":
        if [c["experiment"]["representation"] for c in [overlap, common, repeated]] != [
                "obligation_overlap", "case_local", "case_local"]:
            raise ValueError("wrong representation labels")
        if common["evidenceHashes"]["repair-view.json"] != repeated["evidenceHashes"]["repair-view.json"]:
            raise ValueError("repeated generic view differs")
    elif common["promptSha256"] != repeated["promptSha256"]:
        raise ValueError("generic prompts differ")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--study", choices=["probe_v1", "obligation_view_v1"], default="probe_v1")
    args = parser.parse_args()
    root = args.run_root.resolve()
    source = root / "freeze/source"
    arms = root / "arms"
    task = TaskSpec.from_json(root / "freeze/public/task.json")
    manifest = read(source / "benchmark_manifest.json")
    ids = {t["taskId"] for t in manifest["tasks"]}
    labels = (["probe_v1_overlap", "probe_v1_generic", "probe_v1_generic_b"] if args.study == "probe_v1" else
              ["obligation_view_v1_obligation_overlap", "obligation_view_v1_case_local", "obligation_view_v1_case_local_b"])
    overlap_label, common_label, repeated_label = labels
    executions = 6 if args.study == "probe_v1" else 5
    # Required completed system files are also proof that input/ledger gates ran.
    reports = {label: read(arms / label / "system-result.json") for label in labels}
    contracts = {label: read(arms / label / "contract.json") for label in labels}
    check_contracts(contracts, labels, args.study)
    for label in labels:
        if set(reports[label]["systemTaskOutcomes"]) != ids:
            raise ValueError("report inventory differs")
    all_labels = labels + ["ordinary_repair", "graph", "plain"]
    attempts = {label: read_attempt(arms, label) for label in all_labels}
    maps = {label: validate_attempt(attempt, ids) for label, attempt in attempts.items()}
    out = root / "portfolios" / args.study
    out.mkdir(parents=True, exist_ok=True)
    systems = {}
    for name, differing in [("heterogeneous", overlap_label), ("homogeneous", repeated_label)]:
        order = [differing, common_label, "ordinary_repair", "graph", "plain"]
        selected = choose_sources([(label, maps[label]) for label in order], ids)
        vector = {i: any(maps[label][i] for label in order) for i in ids}
        destination = out / name
        result_path = out / (name + ".json")
        if destination.exists() or result_path.exists():
            raise FileExistsError(f"preserve existing materialization: {destination}")
        shutil.copytree(source, destination)
        solution_hashes = {}
        for item in manifest["tasks"]:
            chosen = attempts[selected[item["taskId"]]]
            for filename in item["solutionFiles"]:
                relative = Path(item["relativePath"]) / filename
                payload = (Path(chosen.workspace) / relative).read_bytes()
                (destination / relative).write_bytes(payload)
                solution_hashes[str(relative)] = hashlib.sha256(payload).hexdigest()
        evaluated = run_evaluator(task.public_test_command, destination)
        if evaluated["taskOutcomes"] != vector:
            raise ValueError("materialized task vector differs from declared union")
        compute = dict(reports[differing]["compute"])
        compute[common_label] = reports[common_label]["compute"][common_label]
        if len(compute) != executions:
            raise ValueError(f"{executions}-execution accounting violated")
        system = {"name": name, "taskCount": len(ids), "passed": sum(vector.values()),
                  "taskOutcomes": vector, "selectedSources": selected, "solutionHashes": solution_hashes,
                  "materializedEvaluation": evaluated, "compute": compute,
                  "totalCompute": aggregate_compute(compute)}
        result_path.write_text(json.dumps(system, indent=2) + "\n")
        systems[name] = system
        print(json.dumps({"system": name, "passed": system["passed"], "taskCount": len(ids)}), flush=True)
    result = {"interpretation": "exposed-task sibling portfolio development; conditional on realized executions",
        "study": args.study, "logicalExecutionsPerSystem": executions,
        "taskCount": len(ids), "componentComparison": compare(
            reports[common_label]["systemTaskOutcomes"], reports[overlap_label]["systemTaskOutcomes"]),
        "portfolioComparison": compare(systems["homogeneous"]["taskOutcomes"], systems["heterogeneous"]["taskOutcomes"]),
        "systems": {name: {"passed": s["passed"], "totalCompute": s["totalCompute"]} for name, s in systems.items()},
        "constituents": {label: {"candidatePassed": reports[label]["candidatePassed"],
                                  ("fiveExecutionSystemPassed" if args.study == "probe_v1" else "fourExecutionSystemPassed"):
                                      reports[label]["systemPassed"]} for label in labels},
        "inputReportHashes": {label: sha(arms / label / "system-result.json") for label in labels},
        "materializedReportHashes": {name: sha(out / (name + ".json")) for name in systems}}
    (out / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
