#!/usr/bin/env python3
"""Score a frozen HumanEvalFix C++ track against hidden official tests."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def run_case(*, compiler: Path, include_root: Path, solution: str, test_setup: str, test: str) -> tuple[bool, int | None, bool, str]:
    payload = solution.rstrip() + "\n" + test_setup.rstrip() + "\n" + test.rstrip() + "\n"
    env = os.environ.copy()
    env.update({"TZ": "UTC", "LC_ALL": "C.UTF-8"})
    with tempfile.TemporaryDirectory(prefix="humanevalfix-cpp-case-") as temporary:
        root = Path(temporary)
        (root / "main.cpp").write_text(payload, encoding="utf-8")
        try:
            compiled = subprocess.run(
                [str(compiler), "-std=c++17", "-O2", "-pipe", "-I", str(include_root),
                 "main.cpp", "-o", "main", "-lcrypto"],
                cwd=root, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                timeout=30, check=False,
            )
            if compiled.returncode != 0:
                return False, compiled.returncode, False, compiled.stdout[-8000:]
            executed = subprocess.run(
                [str(root / "main")], cwd=root, env=env, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=10, check=False,
            )
            return executed.returncode == 0, executed.returncode, False, executed.stdout[-8000:]
        except subprocess.TimeoutExpired as exc:
            raw = exc.stdout or ""
            tail = raw.decode(errors="replace") if isinstance(raw, bytes) else raw
            return False, None, True, tail[-8000:]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--private-root", required=True, type=Path)
    parser.add_argument("--compiler", required=True, type=Path)
    parser.add_argument("--include-root", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    private_root = args.private_root.resolve()
    compiler = args.compiler.resolve()
    include_root = args.include_root.resolve()
    if not compiler.is_file():
        raise FileNotFoundError(compiler)
    if not (include_root / "boost" / "any.hpp").is_file():
        raise FileNotFoundError(include_root / "boost" / "any.hpp")
    cases = json.loads((private_root / "cases.json").read_text(encoding="utf-8"))
    manifest = json.loads((private_root / "benchmark_manifest.json").read_text(encoding="utf-8"))
    case_by_id = {item["taskId"]: item for item in cases}
    if len(case_by_id) != len(cases) or set(case_by_id) != {item["taskId"] for item in manifest["tasks"]}:
        raise ValueError("private cases and manifest differ or contain duplicate IDs")

    def evaluate(item: dict[str, object]) -> dict[str, object]:
        task_id = str(item["taskId"])
        path = workspace / str(item["relativePath"]) / str(item["solutionFiles"][0])
        case = case_by_id[task_id]
        passed, code, timed_out, tail = run_case(
            compiler=compiler,
            include_root=include_root,
            solution=path.read_text(encoding="utf-8"),
            test_setup=str(case["testSetup"]),
            test=str(case["test"]),
        )
        return {"taskId": task_id, "language": "cpp", "passed": passed,
                "exitCode": code, "timedOut": timed_out, "outputTail": tail}

    workers = max(1, min(args.workers, len(manifest["tasks"])))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(evaluate, manifest["tasks"]))
    for result in results:
        print(json.dumps(result, ensure_ascii=False))
    passed_count = sum(int(result["passed"]) for result in results)
    all_passed = passed_count == len(results)
    print(json.dumps({"summary": True, "patchApplied": True, "passedCount": passed_count,
                      "taskCount": len(results), "allPassed": all_passed}))
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
