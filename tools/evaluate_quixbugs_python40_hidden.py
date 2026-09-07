#!/usr/bin/env python3
"""Score all 40 frozen QuixBugs Python programs against private official tests."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def run_case(
    *, python_binary: Path, workspace: Path, private_root: Path, test_file: str, timeout_seconds: int
) -> tuple[bool, int | None, bool, str]:
    env = os.environ.copy()
    old_path = env.get("PYTHONPATH", "")
    env.update(
        {
            "PYTHONPATH": os.pathsep.join(
                [str(workspace), str(private_root / "python_testcases"), old_path]
            ).rstrip(os.pathsep),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
        }
    )
    command = [
        str(python_binary),
        "-m",
        "pytest",
        "-q",
        "--disable-warnings",
        "--maxfail=1",
        str(private_root / "python_testcases" / test_file),
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=private_root,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout_seconds,
            check=False,
        )
        return completed.returncode == 0, completed.returncode, False, completed.stdout[-8000:]
    except subprocess.TimeoutExpired as exc:
        raw = exc.stdout or ""
        tail = raw.decode(errors="replace") if isinstance(raw, bytes) else raw
        return False, None, True, tail[-8000:]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--private-root", required=True, type=Path)
    parser.add_argument("--python", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--case-timeout-seconds", type=int, default=20)
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    private_root = args.private_root.resolve()
    python_binary = args.python.resolve()
    if not python_binary.is_file():
        raise FileNotFoundError(python_binary)
    manifest = json.loads((private_root / "benchmark_manifest.json").read_text(encoding="utf-8"))
    tasks = manifest["tasks"]
    if len(tasks) != 40 or len({item["taskId"] for item in tasks}) != 40:
        raise ValueError("expected exactly 40 unique QuixBugs tasks")

    def evaluate(item: dict[str, object]) -> dict[str, object]:
        passed, code, timed_out, tail = run_case(
            python_binary=python_binary,
            workspace=workspace,
            private_root=private_root,
            test_file=str(item["officialTestFile"]),
            timeout_seconds=args.case_timeout_seconds,
        )
        return {
            "taskId": item["taskId"],
            "language": "python",
            "passed": passed,
            "exitCode": code,
            "timedOut": timed_out,
            "outputTail": tail,
        }

    workers = max(1, min(args.workers, len(tasks)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(evaluate, tasks))
    for result in results:
        print(json.dumps(result, ensure_ascii=False))
    passed_count = sum(int(result["passed"]) for result in results)
    all_passed = passed_count == len(results)
    print(
        json.dumps(
            {
                "summary": True,
                "patchApplied": True,
                "passedCount": passed_count,
                "taskCount": len(results),
                "allPassed": all_passed,
            }
        )
    )
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
