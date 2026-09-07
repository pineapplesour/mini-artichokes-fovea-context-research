#!/usr/bin/env python3
"""Score all frozen HumanEvalFix Python tasks against private official tests."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path


IMPORT_HELPER = """import math
import re
import sys
import copy
import datetime
import itertools
import collections
import heapq
import statistics
import functools
import hashlib
import numpy
import numpy as np
import string
from typing import *
from collections import *
"""


def run_case(
    *,
    python_binary: Path,
    solution: str,
    test_setup: str,
    test: str,
) -> tuple[bool, int | None, bool, str]:
    payload = IMPORT_HELPER + "\n" + solution + "\n" + test_setup + "\n" + test + "\n"
    env = os.environ.copy()
    env.update(
        {
            "PYTHONHASHSEED": "0",
            "PYTHONDONTWRITEBYTECODE": "1",
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
        }
    )
    with tempfile.TemporaryDirectory(prefix="humanevalfix-python-case-") as temporary:
        runner = Path(temporary) / "runner.py"
        runner.write_text(payload, encoding="utf-8")
        try:
            completed = subprocess.run(
                [str(python_binary), "-I", str(runner)],
                cwd=temporary,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=10,
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
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    private_root = args.private_root.resolve()
    python_binary = args.python.resolve()
    if not python_binary.is_file():
        raise FileNotFoundError(python_binary)
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
            python_binary=python_binary,
            solution=solution,
            test_setup=case["testSetup"],
            test=case["test"],
        )
        passed_count += int(passed)
        print(
            json.dumps(
                {
                    "taskId": task_id,
                    "language": "python",
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

