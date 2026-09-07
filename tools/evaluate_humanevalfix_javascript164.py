#!/usr/bin/env python3
"""Score a frozen HumanEvalFix JavaScript track against hidden official tests."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path


def run_case(
    *,
    node_binary: Path,
    solution: str,
    test_setup: str,
    test: str,
    node_modules: Path,
) -> tuple[bool, int | None, bool, str]:
    payload = solution + "\n" + test_setup + "\n" + test + "\n"
    env = os.environ.copy()
    env.update({"TZ": "UTC", "LC_ALL": "C.UTF-8", "NODE_PATH": str(node_modules)})
    with tempfile.TemporaryDirectory(prefix="humanevalfix-javascript-case-") as temporary:
        runner = Path(temporary) / "runner.js"
        runner.write_text(payload, encoding="utf-8")
        try:
            completed = subprocess.run(
                [str(node_binary), str(runner)],
                cwd=temporary,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=10,
                check=False,
            )
            output = completed.stdout
            # The official OctoPack JavaScript harness treats either stdout or
            # stderr as failure. Node's console.assert writes failures there.
            passed = completed.returncode == 0 and not output
            return passed, completed.returncode, False, output[-8000:]
        except subprocess.TimeoutExpired as exc:
            raw = exc.stdout or ""
            tail = raw.decode(errors="replace") if isinstance(raw, bytes) else raw
            return False, None, True, tail[-8000:]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--private-root", required=True, type=Path)
    parser.add_argument("--node", required=True, type=Path)
    parser.add_argument("--node-modules", required=True, type=Path)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    private_root = args.private_root.resolve()
    node_binary = args.node.resolve()
    node_modules = args.node_modules.resolve()
    if not node_binary.is_file():
        raise FileNotFoundError(node_binary)
    if not (node_modules / "js-md5" / "package.json").is_file():
        raise FileNotFoundError(node_modules / "js-md5" / "package.json")

    cases = json.loads((private_root / "cases.json").read_text(encoding="utf-8"))
    manifest = json.loads((private_root / "benchmark_manifest.json").read_text(encoding="utf-8"))
    case_by_id = {item["taskId"]: item for item in cases}
    if len(case_by_id) != len(cases):
        raise ValueError("duplicate private task IDs")
    if set(case_by_id) != {item["taskId"] for item in manifest["tasks"]}:
        raise ValueError("private cases and manifest differ")

    passed_count = 0
    for item in manifest["tasks"]:
        task_id = item["taskId"]
        solution_path = workspace / item["relativePath"] / item["solutionFiles"][0]
        solution = solution_path.read_text(encoding="utf-8")
        case = case_by_id[task_id]
        passed, code, timed_out, tail = run_case(
            node_binary=node_binary,
            solution=solution,
            test_setup=case["testSetup"],
            test=case["test"],
            node_modules=node_modules,
        )
        passed_count += int(passed)
        print(
            json.dumps(
                {
                    "taskId": task_id,
                    "language": "javascript",
                    "passed": passed,
                    "exitCode": code,
                    "timedOut": timed_out,
                    "outputTail": tail,
                },
                ensure_ascii=False,
            )
        )

    all_passed = passed_count == len(manifest["tasks"])
    print(
        json.dumps(
            {
                "summary": True,
                "patchApplied": True,
                "passedCount": passed_count,
                "taskCount": len(manifest["tasks"]),
                "allPassed": all_passed,
            }
        )
    )
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
