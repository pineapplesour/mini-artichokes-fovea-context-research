"""Separately replay helper-union policies over a frozen existing candidate pool."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

from tools import run_classeval_source_overlap as base
from tools import classeval_source_overlap_union as union


def postrepair_parents(task_root, parents, input_hashes, expected_pass):
    """Use the shared ordinary-repair history, never another policy's repair."""
    final = task_root / "ordinary-final"
    final_report = json.loads((final / "evaluation.json").read_text())
    final_info = json.loads((final / "result.json").read_text())
    if final_report["passed"] != expected_pass or final_info["passed"] != expected_pass:
        raise ValueError("ordinary final outcome mismatch")
    input_hashes["ordinary-final"] = {name: base.sha(final / name)
        for name in ("selected.py", "evaluation.json", "result.json")}
    if expected_pass:
        return [{"source": (final / "selected.py").read_text(), "report": final_report, "valid": True}]
    name = final_info.get("repairFrom", "")
    if not isinstance(name, str) or not re.fullmatch(r"repair-[0-9]+", name):
        raise ValueError("exact ordinary repair artifact required")
    directory = task_root / name
    receipt = json.loads((directory / "receipt.json").read_text())
    report = json.loads((directory / "evaluation.json").read_text())
    repaired = {"source": (directory / "candidate.py").read_text(), "report": report,
                "valid": receipt["valid"]}
    input_hashes[name] = {n: base.sha(directory / n)
        for n in ("candidate.py", "receipt.json", "evaluation.json")}
    def rank(p):
        return (p["report"]["passed"], sum(c["status"] == "passed" for c in p["report"]["cases"].values()))
    seed = max(parents, key=rank)
    if rank(max([seed, repaired], key=rank)) != rank({"report": final_report}):
        raise ValueError("ordinary selected state differs from observed history")
    return [seed, repaired]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-root", required=True, type=Path)
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--diagnostic-completed-prefix", action="store_true")
    parser.add_argument("--after-ordinary-repair", action="store_true")
    args = parser.parse_args(argv)
    root, out = args.parent_root.resolve(), args.run_root.resolve()
    rows = base.load_data("classeval-pro")
    contract = json.loads((root / "contract.json").read_text())
    if contract["dataSha"] != base.PRO_SHA or contract["taskIds"] != [r["task_id"] for r in rows]:
        raise ValueError("full official parent inventory differs")
    status_path = root / ("progress.json" if args.diagnostic_completed_prefix else "result.json")
    status = json.loads(status_path.read_text())
    completed = status["completed"]
    expected_prefix = {r["task_id"] for r in rows[:completed]}
    if set(status["tasks"]) != expected_prefix or status["total"] != 300:
        raise ValueError("not an exact completed prefix of the official inventory")
    if not args.diagnostic_completed_prefix and completed != 300:
        raise ValueError("full300 completion required for benchmark replay")
    rows = rows[:completed]
    out.mkdir(parents=True, exist_ok=False)
    base.write_json(out / "contract.json", {"parentRoot": str(root), "dataSha": base.PRO_SHA,
        "parentContractSha": base.sha(root / "contract.json"), "statusSnapshot": status,
        "diagnosticOnly": args.diagnostic_completed_prefix, "benchmarkTotal": 300,
        "taskIds": [r["task_id"] for r in rows], "operatorSha": base.sha(Path(union.__file__)),
        "operatorProtocolSha": base.sha(union.PROTOCOL) if hasattr(union, "PROTOCOL") else None,
        "replaySha": base.sha(Path(__file__)), "originalRunnerSha": base.sha(Path(base.__file__)),
        "evaluatorSha": base.sha(base.ROOT / "tools/classeval_isolated_evaluator.py"),
        "parentStage": "ordinary-feedback-repair" if args.after_ordinary_repair else "initial-generation",
        "postrepairProtocolSha": base.sha(base.ROOT / "experiment_protocols/2026-09-05-classeval-postrepair-overlap-development.md")
            if args.after_ordinary_repair else None})
    # Process-local function binding only. Neither the live process's globals
    # nor any shared source file or original output is modified.
    base.proposals = union.proposals
    results = {}
    for row in rows:
        task_id = row["task_id"]
        parents, input_hashes = [], {}
        for label in ("a", "b"):
            directory = root / task_id / label
            if not directory.exists():
                if label == "b" and parents and parents[0]["report"]["passed"]:
                    continue
                raise ValueError("missing required parent")
            receipt = json.loads((directory / "receipt.json").read_text())
            report = json.loads((directory / "evaluation.json").read_text())
            parents.append({"source": (directory / "candidate.py").read_text(), "report": report,
                            "valid": receipt["valid"]})
            input_hashes[label] = {name: base.sha(directory / name)
                for name in ("candidate.py", "receipt.json", "evaluation.json")}
        if args.after_ordinary_repair:
            parents = postrepair_parents(root / task_id, parents, input_hashes,
                                         status["tasks"][task_id]["ordinaryFinal"])
        base.write_json(out / task_id / "inputs.json", input_hashes)
        results[task_id] = {}
        for policy in ("generic", "overlap"):
            results[task_id][policy] = base.search(row, parents, policy, out / task_id / policy)
        print(json.dumps({"taskId": task_id, "diagnosticOnly": args.diagnostic_completed_prefix,
            "generic": results[task_id]["generic"]["passed"],
            "overlap": results[task_id]["overlap"]["passed"]}), flush=True)
    base.write_json(out / "result.json", {"completed": len(rows), "total": 300,
        "diagnosticOnly": args.diagnostic_completed_prefix, "tasks": results})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
