#!/usr/bin/env python3
"""Apply a candidate patch to private official C++ tests and score every task."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def run_task(task_dir: Path) -> tuple[bool, int | None, bool, str]:
    build = task_dir / "build"
    env = os.environ.copy()
    env["CMAKE_BUILD_PARALLEL_LEVEL"] = "1"
    commands = (
        ["cmake", "-S", str(task_dir), "-B", str(build), "-DEXERCISM_RUN_ALL_TESTS=1", "-G", "Unix Makefiles"],
        ["cmake", "--build", str(build), "--", "-j1"],
    )
    output: list[str] = []
    try:
        for command in commands:
            result = subprocess.run(
                command,
                cwd=task_dir,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=240,
                check=False,
            )
            output.append(result.stdout)
            if result.returncode != 0:
                return False, result.returncode, False, "\n".join(output)[-8000:]
        return True, 0, False, "\n".join(output)[-8000:]
    except subprocess.TimeoutExpired as exc:
        raw = exc.stdout or ""
        tail = raw.decode(errors="replace") if isinstance(raw, bytes) else raw
        output.append(tail)
        return False, None, True, "\n".join(output)[-8000:]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--private-root", required=True, type=Path)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    private_root = args.private_root.resolve()
    manifest = json.loads((private_root / "benchmark_manifest.json").read_text(encoding="utf-8"))
    diff = subprocess.run(
        ["git", "diff", "--binary", "HEAD", "--"],
        cwd=workspace,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout
    with tempfile.TemporaryDirectory(prefix="aider-hidden-cpp26-") as temporary:
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
            passed, code, timed_out, tail = run_task(evaluation / item["relativePath"])
            passed_count += int(passed)
            print(json.dumps({
                "taskId": item["taskId"],
                "language": "cpp",
                "passed": passed,
                "exitCode": code,
                "timedOut": timed_out,
                "outputTail": tail,
            }, ensure_ascii=False))
        all_passed = passed_count == len(manifest["tasks"])
        print(json.dumps({
            "summary": True,
            "patchApplied": True,
            "passedCount": passed_count,
            "taskCount": len(manifest["tasks"]),
            "allPassed": all_passed,
        }))
        return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
