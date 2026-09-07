#!/usr/bin/env python3
"""Apply a candidate patch to private official Go tests and score every task."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def run_task(task_dir: Path, go_binary: Path, cache_root: Path) -> tuple[bool, int | None, bool, str]:
    env = os.environ.copy()
    env.update({
        "GOTOOLCHAIN": "local",
        "GOPROXY": "off",
        "GOSUMDB": "off",
        "GOCACHE": str(cache_root / "build"),
        "GOMODCACHE": str(cache_root / "modules"),
    })
    try:
        result = subprocess.run(
            [str(go_binary), "test", "./..."],
            cwd=task_dir,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=240,
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
    parser.add_argument("--go-root", required=True, type=Path)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    private_root = args.private_root.resolve()
    go_binary = args.go_root.resolve() / "bin" / "go"
    if not go_binary.is_file():
        raise FileNotFoundError(go_binary)
    manifest = json.loads((private_root / "benchmark_manifest.json").read_text(encoding="utf-8"))
    diff = subprocess.run(
        ["git", "diff", "--binary", "HEAD", "--"],
        cwd=workspace,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout
    with tempfile.TemporaryDirectory(prefix="aider-hidden-go39-") as temporary:
        temporary_root = Path(temporary)
        evaluation = temporary_root / "evaluation"
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
        for index, item in enumerate(manifest["tasks"]):
            passed, code, timed_out, tail = run_task(
                evaluation / item["relativePath"], go_binary, temporary_root / f"cache-{index:02d}"
            )
            passed_count += int(passed)
            print(json.dumps({
                "taskId": item["taskId"],
                "language": "go",
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
