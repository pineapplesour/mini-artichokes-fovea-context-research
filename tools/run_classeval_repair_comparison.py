"""The predeclared identical ordinary-repair stage after full source composition.

This does not modify the source-generation runner or any of its live outputs.
It requires a terminal complete full-inventory parent result before execution.
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
from pathlib import Path
import time

from tools import run_classeval_source_overlap as base


PROMPT = """Repair the single Python class in /tmp/work/solution.py using the original
specification and the supplied observed execution feedback. Freely compare,
copy, combine or synthesize any supplied candidate code; choose your own
general repair strategy. Resolve the underlying requirements, not hard-coded
test examples. Preserve supported behavior and check state/method interactions.

Read /tmp/artifacts/input/index.json. It links the two original candidate
sources, their observed feedback and validity status, and feedback for the
current starting code. Missing tests are unknown, not evidence of correctness.
Inputs marked invalid are unfinished/unsafe attempts, not verified solutions.
Official test source, reference implementations and external answers are hidden.
Do not edit any supplied input file. Only solution.py may be submitted; put
temporary checks outside the workspace under /tmp. Do not add supporting source
files, fetch dependencies or use network/answer lookup. Use declared dependencies.

Inspect the final code against the original specification and the actual
failure evidence. There is no decision ledger or special required reasoning
format. Finish substantive work and your response within100seconds; the hard
cap is120seconds. Return the code file and a brief completion response.

Original specification:
{skeleton}
"""
PROTOCOL = base.ROOT / "experiment_protocols/2026-09-05-classeval-ordinary-repair-comparison.md"


def read_json(path: Path):
    return json.loads(path.read_text())


def compact_feedback(report: dict) -> dict:
    return {"passed": report["passed"], "expectedCount": report.get("expectedCount"),
            "fatal": report.get("fatal"), "cases": {
                case_id: {"status": item["status"], "message": item.get("message", "")[-1600:]}
                for case_id, item in sorted(report["cases"].items())}}


def check_complete_parent(root: Path, rows: list[dict]) -> tuple[dict, dict]:
    contract, result = read_json(root / "contract.json"), read_json(root / "result.json")
    ids = [r["task_id"] for r in rows]
    if (contract.get("dataset") != "classeval-pro" or contract["dataSha"] != base.PRO_SHA
            or contract["taskIds"] != ids or result.get("completed") != len(ids)
            or result.get("total") != len(ids) or set(result["tasks"]) != set(ids)):
        raise ValueError("terminal complete official inventory required")
    dependencies = {"runnerSha": Path(base.__file__),
                    "operatorSha": base.ROOT / "tools/classeval_source_overlap.py",
                    "evaluatorSha": base.ROOT / "tools/classeval_isolated_evaluator.py"}
    if any(contract.get(key) != base.sha(path) for key, path in dependencies.items()):
        raise ValueError("source-stage implementation differs from its frozen contract")
    for task_id in ids:
        for policy in ("generic", "overlap"):
            state = root / task_id / policy
            observed = read_json(state / "selected-evaluation.json")["passed"]
            if observed != result["tasks"][task_id][policy]:
                raise ValueError("source-stage selected/result outcome mismatch")
            if not (state / "selected.py").is_file():
                raise FileNotFoundError(state / "selected.py")
    return contract, result


def stage_inputs(task_root: Path, policy: str, artifact: Path) -> dict[str, str]:
    inputs = artifact / "input"
    inputs.mkdir(parents=True, exist_ok=False)
    index = {"parents": {}, "startingFeedback": "/tmp/artifacts/input/starting-feedback.json"}
    for parent in ("a", "b"):
        source = task_root / parent
        receipt = read_json(source / "receipt.json")
        (inputs / f"{parent}.py").write_bytes((source / "candidate.py").read_bytes())
        base.write_json(inputs / f"{parent}-feedback.json", compact_feedback(read_json(source / "evaluation.json")))
        index["parents"][parent] = {"source": f"/tmp/artifacts/input/{parent}.py",
            "feedback": f"/tmp/artifacts/input/{parent}-feedback.json", "valid": receipt["valid"]}
    base.write_json(inputs / "starting-feedback.json",
                    compact_feedback(read_json(task_root / policy / "selected-evaluation.json")))
    base.write_json(inputs / "index.json", index)
    return {path.name: base.sha(path) for path in inputs.iterdir()}


def select_final(seed_source: str, seed_report: dict, repaired_source: str, repaired_report: dict):
    def score(report):
        return (report["passed"], sum(case["status"] == "passed" for case in report["cases"].values()))
    if score(repaired_report) > score(seed_report):
        return repaired_source, repaired_report, "repair"
    return seed_source, seed_report, "seed"


def repair(row: dict, task_root: Path, policy: str, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=False)
    seed_source = (task_root / policy / "selected.py").read_text()
    seed_report = read_json(task_root / policy / "selected-evaluation.json")
    if seed_report["passed"]:
        (out / "selected.py").write_text(seed_source)
        base.write_json(out / "selected-evaluation.json", seed_report)
        summary = {"passed": True, "modelCalls": 0, "selected": "verified_seed",
                   "selectedSha": hashlib.sha256(seed_source.encode()).hexdigest()}
        base.write_json(out / "result.json", summary)
        return summary
    work, artifact = out / "work", out / "artifact"
    work.mkdir()
    artifact.mkdir()
    (work / "solution.py").write_text(seed_source)
    input_hashes = stage_inputs(task_root, policy, artifact)
    prompt = PROMPT.format(skeleton=row["skeleton"])
    (out / "prompt.txt").write_text(prompt)
    adapter = base.IsolatedCodexAdapter(Path("/home/pineapple/.codex-new-account"),
                                       "gpt-5.6-luna", "medium", 120)
    base.write_json(out / "contract.json", {"taskId": row["task_id"], "policy": policy,
        "promptSha": hashlib.sha256(prompt.encode()).hexdigest(), "inputHashes": input_hashes,
        "seedSha": hashlib.sha256(seed_source.encode()).hexdigest(), "startedEpoch": time.time(),
        "model": adapter.model, "effort": adapter.reasoning_effort, "timeoutSeconds": 120})
    result = adapter.run(work, prompt, artifact, "ordinary_repair")
    events = []
    for line in result.stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "turn.completed":
            events.append(event)
    safe, caches = base.source_scope(work)
    unchanged = all((artifact / "input" / name).is_file()
                    and base.sha(artifact / "input" / name) == digest for name, digest in input_hashes.items())
    valid = result.exit_code == 0 and not result.timed_out and bool(events) and safe and unchanged
    receipt = dataclasses.asdict(result)
    receipt.pop("stdout")
    receipt.pop("stderr")
    raw_source = (work / "solution.py").read_text() if (work / "solution.py").is_file() else ""
    source = base.evaluation_source(row, raw_source)
    receipt.update({"valid": valid, "sourceSafe": safe, "nonSubmittedCaches": caches,
        "inputsUnchanged": unchanged, "sourceSha": hashlib.sha256(raw_source.encode()).hexdigest(),
        "usage": events[-1].get("usage") if events else None})
    base.write_json(out / "receipt.json", receipt)
    (out / "candidate.py").write_text(source)
    report = base.evaluate(row, source) if valid else {"passed": False, "cases": {}, "fatal": "invalid model execution"}
    base.write_json(out / "evaluation.json", report)
    selected_source, selected_report, selected = select_final(seed_source, seed_report, source, report)
    (out / "selected.py").write_text(selected_source)
    base.write_json(out / "selected-evaluation.json", selected_report)
    summary = {"passed": selected_report["passed"], "modelCalls": 1, "selected": selected,
               "selectedSha": hashlib.sha256(selected_source.encode()).hexdigest()}
    base.write_json(out / "result.json", summary)
    return summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-root", required=True, type=Path)
    parser.add_argument("--run-root", required=True, type=Path)
    args = parser.parse_args(argv)
    rows = base.load_data("classeval-pro")
    root, out = args.parent_root.resolve(), args.run_root.resolve()
    parent_contract, parent_result = check_complete_parent(root, rows)
    out.mkdir(parents=True, exist_ok=False)
    base.write_json(out / "contract.json", {"taskIds": [r["task_id"] for r in rows],
        "parentContractSha": base.sha(root / "contract.json"), "parentResultSha": base.sha(root / "result.json"),
        "sourceStageContract": parent_contract, "runnerSha": base.sha(Path(__file__)),
        "protocolSha": base.sha(PROTOCOL), "startedEpoch": time.time()})
    results = {}
    for row in rows:
        task_id = row["task_id"]
        results[task_id] = {"sharedParentCalls": parent_result["tasks"][task_id]["modelCalls"]}
        for policy in ("generic", "overlap"):
            results[task_id][policy] = repair(row, root / task_id, policy, out / task_id / policy)
        base.write_json(out / "progress.json", {"completed": len(results), "total": len(rows), "tasks": results})
        print(json.dumps({"taskId": task_id, "completed": len(results),
            "generic": results[task_id]["generic"]["passed"],
            "overlap": results[task_id]["overlap"]["passed"]}), flush=True)
    base.write_json(out / "result.json", {"completed": len(rows), "total": len(rows), "tasks": results})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
