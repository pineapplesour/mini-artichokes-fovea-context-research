#!/usr/bin/env python3
"""Apply an agent patch to private official tests and emit task-level results."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def command_for(item: dict[str, object]) -> list[str]:
    if item["language"] == "python":
        return [sys.executable, "-m", "pytest", "-q", "--tb=short", "-p", "no:cacheprovider", *item["testFiles"]]
    if item["language"] == "rust":
        return ["cargo", "test", "--", "--include-ignored"]
    raise ValueError(item["language"])


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
    with tempfile.TemporaryDirectory(prefix="aider-hidden20-") as tmp:
        evaluation = Path(tmp) / "evaluation"
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
        all_passed = True
        passed_count = 0
        for item in manifest["tasks"]:
            task_dir = evaluation / item["relativePath"]
            env = os.environ.copy()
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            env["CARGO_TERM_COLOR"] = "never"
            try:
                result = subprocess.run(
                    command_for(item),
                    cwd=task_dir,
                    env=env,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    timeout=180,
                    check=False,
                )
                passed = result.returncode == 0
                code = result.returncode
                timed_out = False
                tail = result.stdout[-8000:]
            except subprocess.TimeoutExpired as exc:
                passed = False
                code = None
                timed_out = True
                raw = exc.stdout or ""
                tail = (raw.decode(errors="replace") if isinstance(raw, bytes) else raw)[-8000:]
            all_passed = all_passed and passed
            passed_count += int(passed)
            print(json.dumps({
                "taskId": item["taskId"],
                "language": item["language"],
                "passed": passed,
                "exitCode": code,
                "timedOut": timed_out,
                "outputTail": tail,
            }, ensure_ascii=False))
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
