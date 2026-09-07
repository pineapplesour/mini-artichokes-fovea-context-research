#!/usr/bin/env python3
"""Measure observed within-task repair complementarity, without new model calls.

Uses the existing official Java commands on fresh private copies. Never exposes
test source to an agent or changes the evaluator used by a frozen experiment.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

from tools.evaluate_aider_hidden_java20 import activate_all_official_tests
from tools.run_aider_counterexample_overlap import read_attempt, validate_attempt


def parse_cases(directory: Path) -> dict:
    cases = {}
    for path in sorted(directory.glob("TEST-*.xml")):
        for node in ET.parse(path).getroot().iter("testcase"):
            key = node.attrib.get("classname", "") + "#" + node.attrib["name"]
            if key in cases:
                raise ValueError(f"duplicate JUnit case: {key}")
            status, message = "passed", ""
            for tag, label in [("failure", "failed"), ("error", "error"), ("skipped", "skipped")]:
                child = node.find(tag)
                if child is not None:
                    status = label
                    message = child.attrib.get("message", "")[:2000]
                    break
            cases[key] = {"status": status, "message": message}
    return cases


def summarize(captures: dict) -> dict:
    ids = set(next(iter(captures.values()))["tasks"])
    if any(set(c["tasks"]) != ids for c in captures.values()):
        raise ValueError("capture task inventories differ")
    tasks = {}
    for task_id in sorted(ids):
        rows = {label: c["tasks"][task_id] for label, c in captures.items()}
        executed = {label: row["cases"] for label, row in rows.items() if row["cases"]}
        inventories = [set(cases) for cases in executed.values()]
        aligned = bool(inventories) and all(s == inventories[0] for s in inventories)
        solved = any(row["passed"] for row in rows.values())
        record = {"alreadySolved": solved, "caseInventoryAligned": aligned,
                  "noCaseReport": [label for label, row in rows.items() if not row["cases"]]}
        if aligned:
            passed = {label: {key for key, c in cases.items() if c["status"] == "passed"}
                      for label, cases in executed.items()}
            union = set().union(*passed.values())
            best = max(map(len, passed.values()))
            pairs = []
            for a, b in itertools.combinations(passed, 2):
                pairs.append({"parents": [a, b], "sharedPassed": len(passed[a] & passed[b]),
                              "unionPassed": len(passed[a] | passed[b]),
                              "beyondBestParent": len(passed[a] | passed[b]) - max(len(passed[a]), len(passed[b])),
                              "sharedLineage": {a, b} == {"graph", "ordinary_repair"}})
            record.update(caseCount=len(inventories[0]), candidatePassedCases={k: len(v) for k, v in passed.items()},
                          unionPassedCases=len(union), unionBeyondBest= len(union) - best,
                          unresolvedButObservedUnionCoversAll=not solved and union == inventories[0], pairs=pairs)
        tasks[task_id] = record
    return {"taskCount": len(ids), "tasks": tasks,
            "unresolvedWithComplementarity": [i for i, r in tasks.items()
                 if not r["alreadySolved"] and r.get("unionBeyondBest", 0) > 0],
            "unresolvedWithFullObservedCoverage": [i for i, r in tasks.items()
                 if r.get("unresolvedButObservedUnionCoversAll")],
            "interpretation": "Observed case coverage only, not an executable fused solution or accuracy gain. "
                "Missing case reports are unknown, never counted as passing. Graph and its repair share lineage."}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--candidate-ids", nargs="+", default=["plain", "graph", "ordinary_repair"])
    args = parser.parse_args()
    if (len(set(args.candidate_ids)) != len(args.candidate_ids)
            or any(Path(label).name != label or label in {".", ".."} for label in args.candidate_ids)):
        raise ValueError("candidate IDs must be distinct local arm names")
    root, out = args.run_root.resolve(), args.out.resolve()
    private = root / "freeze/private"
    manifest = json.loads((private / "benchmark_manifest.json").read_text())
    ids = {item["taskId"] for item in manifest["tasks"]}
    if len(ids) != len(manifest["tasks"]):
        raise ValueError("duplicate task IDs")
    script_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    out.mkdir(parents=True, exist_ok=True)
    captures = {}
    for label in args.candidate_ids:
        attempt = read_attempt(root / "arms", label)
        expected = validate_attempt(attempt, ids)
        target = out / (label + ".json")
        if target.exists():
            prior = json.loads(target.read_text())
            if (prior["patchSha256"] != attempt.patch_sha256 or prior["scriptSha256"] != script_hash
                    or set(prior["tasks"]) != ids or not prior["taskVectorMatchesOriginal"]):
                raise ValueError("existing capture does not match; preserve it")
            captures[label] = prior
            continue
        rows = {}
        with tempfile.TemporaryDirectory(prefix="mini-java-partial-") as temporary:
            evaluation = Path(temporary) / "evaluation"
            shutil.copytree(private / "evaluator_source", evaluation)
            subprocess.run(["git", "apply", "--allow-empty", "--binary", "-"], cwd=evaluation,
                           input=attempt.patch_text, text=True, check=True, capture_output=True)
            for item in manifest["tasks"]:
                task_dir = evaluation / item["relativePath"]
                activate_all_official_tests(task_dir)
                env = os.environ.copy()
                env["GRADLE_OPTS"] = "-Dorg.gradle.daemon=false -Dorg.gradle.workers.max=1"
                try:
                    result = subprocess.run(["./gradlew", "test", "--no-daemon", "--console=plain", "--max-workers=1"],
                                            cwd=task_dir, env=env, text=True, stdout=subprocess.PIPE,
                                            stderr=subprocess.STDOUT, timeout=240, check=False)
                    code, timed_out, raw = result.returncode, False, result.stdout
                except subprocess.TimeoutExpired as exc:
                    code, timed_out = None, True
                    raw = exc.stdout or ""
                    if isinstance(raw, bytes):
                        raw = raw.decode(errors="replace")
                cases = parse_cases(task_dir / "build/test-results/test")
                rows[item["taskId"]] = {"passed": code == 0, "exitCode": code, "timedOut": timed_out,
                                       "cases": cases, "outputHead": raw[:6000], "outputTail": raw[-2000:]}
        match = {i: r["passed"] for i, r in rows.items()} == expected
        capture = {"candidate": label, "patchSha256": attempt.patch_sha256, "scriptSha256": script_hash,
                   "taskVectorMatchesOriginal": match, "tasks": rows}
        target.write_text(json.dumps(capture, indent=2) + "\n")
        if not match:
            raise ValueError(f"official task-vector drift in {label}; capture retained, no promotion")
        captures[label] = capture
        print(json.dumps({"captured": label, "tasks": len(rows), "passed": sum(expected.values())}), flush=True)
    summary = summarize(captures)
    destination = out / "summary.json"
    if destination.exists():
        if json.loads(destination.read_text()) != summary:
            raise ValueError("existing summary differs; preserve it")
    else:
        destination.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "tasks"}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
