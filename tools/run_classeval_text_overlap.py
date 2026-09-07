"""Full benchmark-native code-output experiment using the approved Codex account.

The solver returns code; the unchanged isolated official evaluator executes it.
This separate runner does not alter the earlier native-agent experiment.
"""
from __future__ import annotations

import argparse
import ast
import dataclasses
import hashlib
import json
from pathlib import Path
import re
import time

from tools import run_classeval_source_overlap as base
from tools import run_aider_hidden20_arm as isolated
from tools import classeval_source_overlap_union as union
from tools.run_classeval_repair_comparison import compact_feedback, select_final


PROTOCOL = base.ROOT / "experiment_protocols/2026-09-05-classeval-text-overlap-v2.md"
GENERATE = """Implement the Python class specified below. Return ONE Python code block
containing the complete implementation, including required imports. Do not use
tools, edit files, run commands, or search for external answers. Interpret the
specification generally rather than hard-coding examples. Preserve its class,
method signatures, constructor behavior and required shared state. Reason
internally, check method interactions and edge cases, then output only code.
For compatibility with the benchmark loader, write every def signature on ONE
line, with self or cls on that same line for instance or class methods.

Specification:
{skeleton}
"""
REPAIR = """Repair the Python class using its original specification and observed test
feedback. Freely compare, copy, combine or synthesize the supplied candidate
code, and fix general causes rather than hard-coded test examples. Preserve
supported behavior and check interactions between methods and shared state.
An invalid attempt is not a verified program; missing case reports are unknown.
Tests and reference implementations remain hidden. Do not use tools, run commands,
edit files or search externally. Return ONE Python code block with the complete
corrected class and required imports. There is no required reasoning format.
For compatibility with the benchmark loader, write every def signature on ONE
line, with self or cls on that same line for instance or class methods.

Original specification:
{skeleton}

Candidate sources, observed feedback and starting code:
{evidence}
"""


def no_tool_command(argv):
    command = list(argv)
    command[command.index("features.shell_tool=true")] = "features.shell_tool=false"
    command[command.index("--sandbox") + 1] = "read-only"
    command[-1:-1] = ["--config", "features.code_mode.enabled=false",
                      "--config", "features.remote_plugin=false",
                      "--config", "features.skill_mcp_dependency_install=false"]
    return command


def extract_code(response: str) -> str:
    match = re.search(r"```(?:python|py)?\s*\n(.*?)```", response, flags=re.S | re.I)
    code = (match.group(1) if match else response).strip() + "\n"
    if not code.strip():
        raise ValueError("empty code")
    ast.parse(code)
    return code


def call(row: dict, out: Path, label: str, prompt: str) -> dict:
    out.mkdir(parents=True, exist_ok=False)
    work, artifact = out / "work", out / "artifact"
    work.mkdir()
    artifact.mkdir()
    (out / "prompt.txt").write_text(prompt)
    base.write_json(out / "contract.json", {"taskId": row["task_id"], "label": label,
        "dataSha": base.PRO_SHA, "promptSha": hashlib.sha256(prompt.encode()).hexdigest(),
        "model": "gpt-5.6-luna", "effort": "medium", "timeoutSeconds": 120,
        "startedEpoch": time.time(), "solverTools": False})
    adapter = base.IsolatedCodexAdapter(Path("/home/pineapple/.codex-new-account"),
                                       "gpt-5.6-luna", "medium", 120)
    real_process = isolated.run_process
    try:
        # This binding exists only in this serial experiment process. The
        # original module file and other running Python processes are untouched.
        isolated.run_process = lambda argv, **kw: real_process(no_tool_command(argv), **kw)
        result = adapter.run(work, prompt, artifact, "code_output")
    finally:
        isolated.run_process = real_process
    receipt = dataclasses.asdict(result)
    receipt.pop("stdout")
    receipt.pop("stderr")
    events = []
    for line in result.stdout.splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    completed = [e for e in events if e.get("type") == "turn.completed"]
    non_text_items = [e["item"].get("type") for e in events if "item" in e
                      and e["item"].get("type") not in {"reasoning", "agent_message"}]
    response_path = artifact / "last_message.txt"
    raw = response_path.read_text() if response_path.is_file() else ""
    try:
        code, parse_error = extract_code(raw), None
    except (ValueError, SyntaxError) as exc:
        code, parse_error = "", str(exc)
    workspace_untouched = not list(work.iterdir())
    valid = (result.exit_code == 0 and not result.timed_out and bool(completed)
             and not non_text_items and workspace_untouched and parse_error is None)
    source = base.evaluation_source(row, code)
    receipt.update({"valid": valid, "sourceSafe": workspace_untouched, "nonTextItems": non_text_items,
        "parseError": parse_error, "sourceSha": hashlib.sha256(code.encode()).hexdigest(),
        "usage": completed[-1].get("usage") if completed else None})
    base.write_json(out / "receipt.json", receipt)
    (out / "candidate.py").write_text(source)
    report = base.evaluate(row, source) if valid else {"passed": False, "cases": {}, "fatal": "invalid code-output execution"}
    base.write_json(out / "evaluation.json", report)
    return {"source": source, "report": report, "valid": valid}


def repair_prompt(row: dict, parents: list[dict], seed: dict) -> str:
    evidence = {"parents": [{"source": p["source"], "valid": p["valid"],
                              "feedback": compact_feedback(p["report"])} for p in parents],
                "startingSource": seed["source"], "startingFeedback": compact_feedback(seed["report"])}
    return REPAIR.format(skeleton=row["skeleton"], evidence=json.dumps(evidence, ensure_ascii=False))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True, type=Path)
    args = parser.parse_args(argv)
    rows, out = base.load_data("classeval-pro"), args.run_root.resolve()
    out.mkdir(parents=True, exist_ok=False)
    base.proposals = union.proposals
    base.write_json(out / "contract.json", {"dataset": "classeval-pro", "taskIds": [r["task_id"] for r in rows],
        "dataSha": base.PRO_SHA, "runnerSha": base.sha(Path(__file__)), "protocolSha": base.sha(PROTOCOL),
        "operatorSha": base.sha(Path(union.__file__)), "baseRunnerSha": base.sha(Path(base.__file__)),
        "evaluatorSha": base.sha(base.ROOT / "tools/classeval_isolated_evaluator.py"),
        "model": "gpt-5.6-luna", "effort": "medium", "timeoutSeconds": 120, "startedEpoch": time.time()})
    results = {}
    for row in rows:
        task_id, task_root = row["task_id"], out / row["task_id"]
        parents = [call(row, task_root / "a", "a", GENERATE.format(skeleton=row["skeleton"]))]
        if not parents[0]["report"]["passed"]:
            parents.append(call(row, task_root / "b", "b", GENERATE.format(skeleton=row["skeleton"])))
        def rank(p):
            return (p["report"]["passed"], sum(c["status"] == "passed" for c in p["report"]["cases"].values()))
        seeds = {"ordinary": max(parents, key=rank)}
        result = {"plain": parents[0]["report"]["passed"], "bestOfTwo": any(p["report"]["passed"] for p in parents),
                  "parentCalls": len(parents), "repairPhysicalCalls": 0}
        for policy in ("generic", "overlap"):
            base.search(row, parents, policy, task_root / policy)
            seeds[policy] = {"source": (task_root / policy / "selected.py").read_text(),
                "report": json.loads((task_root / policy / "selected-evaluation.json").read_text()), "valid": True}
            result[policy + "Source"] = seeds[policy]["report"]["passed"]
        repairs = {}
        for policy in ("ordinary", "generic", "overlap"):
            seed, repaired_from = seeds[policy], None
            chosen_source, chosen_report, chosen_label = seed["source"], seed["report"], "verified_seed"
            if not seed["report"]["passed"]:
                prompt = repair_prompt(row, parents, seed)
                key = hashlib.sha256(prompt.encode()).hexdigest()
                if key not in repairs:
                    name = f"repair-{len(repairs)}"
                    repairs[key] = (name, call(row, task_root / name, "ordinary_repair", prompt))
                    result["repairPhysicalCalls"] += 1
                repaired_from, repaired = repairs[key]
                chosen_source, chosen_report, chosen_label = select_final(seed["source"], seed["report"],
                                                                          repaired["source"], repaired["report"])
            final = task_root / (policy + "-final")
            final.mkdir()
            (final / "selected.py").write_text(chosen_source)
            base.write_json(final / "evaluation.json", chosen_report)
            base.write_json(final / "result.json", {"passed": chosen_report["passed"], "selected": chosen_label,
                "repairFrom": repaired_from, "logicalRepairCalls": int(repaired_from is not None)})
            result[policy + "Final"] = chosen_report["passed"]
        results[task_id] = result
        base.write_json(out / "progress.json", {"completed": len(results), "total": 300, "tasks": results})
        print(json.dumps({"taskId": task_id, "completed": len(results), **result}), flush=True)
    base.write_json(out / "result.json", {"completed": 300, "total": 300, "tasks": results})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
