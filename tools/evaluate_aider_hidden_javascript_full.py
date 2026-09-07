#!/usr/bin/env python3
"""Apply a candidate patch to private JavaScript tests and score every task."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def run_task(
    task_dir: Path,
    *,
    node_binary: Path,
    jest_cli: Path,
    dependencies: Path,
    test_files: list[str],
) -> tuple[bool, int | None, bool, str]:
    env = os.environ.copy()
    env.update(
        {
            "CI": "1",
            "NODE_ENV": "test",
            "NODE_OPTIONS": "--no-deprecation",
            "NODE_PATH": str(dependencies / "node_modules"),
        }
    )
    command = [
        str(node_binary),
        str(jest_cli),
        "--runInBand",
        "--no-cache",
        "--runTestsByPath",
        *test_files,
    ]
    try:
        result = subprocess.run(
            command,
            cwd=task_dir,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=300,
            check=False,
        )
        return result.returncode == 0, result.returncode, False, result.stdout[-8000:]
    except subprocess.TimeoutExpired as exc:
        raw = exc.stdout or ""
        tail = raw.decode(errors="replace") if isinstance(raw, bytes) else raw
        return False, None, True, tail[-8000:]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--private-root", required=True, type=Path)
    parser.add_argument("--node-root", required=True, type=Path)
    parser.add_argument("--dependencies", required=True, type=Path)
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    private_root = args.private_root.resolve()
    node_binary = args.node_root.resolve() / "bin" / "node"
    jest_cli = args.dependencies.resolve() / "node_modules" / "jest" / "bin" / "jest.js"
    if not node_binary.is_file():
        raise FileNotFoundError(node_binary)
    if not jest_cli.is_file():
        raise FileNotFoundError(jest_cli)

    manifest = json.loads((private_root / "benchmark_manifest.json").read_text(encoding="utf-8"))
    diff = subprocess.run(
        ["git", "diff", "--binary", "HEAD", "--"],
        cwd=workspace,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout
    with tempfile.TemporaryDirectory(prefix="aider-hidden-javascript49-") as temporary:
        evaluation = Path(temporary) / "evaluation"
        shutil.copytree(private_root / "evaluator_source", evaluation)
        applied = subprocess.run(
            ["git", "apply", "--allow-empty", "--binary", "-"],
            cwd=evaluation,
            input=diff,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if applied.returncode != 0:
            print(json.dumps({"summary": True, "patchApplied": False, "error": applied.stderr[-4000:]}))
            return 2

        passed_count = 0
        for item in manifest["tasks"]:
            task_dir = evaluation / item["relativePath"]
            passed, code, timed_out, tail = run_task(
                task_dir,
                node_binary=node_binary,
                jest_cli=jest_cli,
                dependencies=args.dependencies.resolve(),
                test_files=list(item["testFiles"]),
            )
            passed_count += int(passed)
            print(
                json.dumps(
                    {
                        "taskId": item["taskId"],
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
