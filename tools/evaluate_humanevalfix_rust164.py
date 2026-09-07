#!/usr/bin/env python3
"""Score a frozen HumanEvalFix Rust track against hidden official tests."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


CARGO_TOML = """[package]
name = "humanevalfix_task"
version = "0.1.0"
edition = "2021"

[dependencies]
rand = "=0.7.3"
regex = "=1.13.1"
md5 = "=0.8.1"
"""


def run_case(*, solution: str, test_setup: str, test: str, target_root: Path) -> tuple[bool, int | None, bool, str]:
    payload = solution.rstrip() + "\n" + test_setup.rstrip() + "\n" + test.rstrip() + "\n"
    env = os.environ.copy()
    env.update({
        "TZ": "UTC",
        "LC_ALL": "C.UTF-8",
        "CARGO_NET_OFFLINE": "true",
        "CARGO_TARGET_DIR": str(target_root),
        "RUST_BACKTRACE": "0",
    })
    with tempfile.TemporaryDirectory(prefix="humanevalfix-rust-case-") as temporary:
        root = Path(temporary)
        (root / "src").mkdir()
        (root / "Cargo.toml").write_text(CARGO_TOML, encoding="utf-8")
        (root / "src" / "main.rs").write_text(payload, encoding="utf-8")
        try:
            completed = subprocess.run(
                ["cargo", "test", "--offline", "--quiet", "--manifest-path", str(root / "Cargo.toml")],
                cwd=root,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=90,
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
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--target-root", type=Path)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    private_root = args.private_root.resolve()
    target_root = (args.target_root or (private_root / "cargo-target")).resolve()
    target_root.mkdir(parents=True, exist_ok=True)
    cases = json.loads((private_root / "cases.json").read_text(encoding="utf-8"))
    manifest = json.loads((private_root / "benchmark_manifest.json").read_text(encoding="utf-8"))
    case_by_id = {item["taskId"]: item for item in cases}
    manifest_ids = {item["taskId"] for item in manifest["tasks"]}
    if len(case_by_id) != len(cases) or set(case_by_id) != manifest_ids:
        raise ValueError("private cases and manifest differ or contain duplicate IDs")

    def evaluate(item: dict[str, object]) -> dict[str, object]:
        task_id = str(item["taskId"])
        path = workspace / str(item["relativePath"]) / str(item["solutionFiles"][0])
        case = case_by_id[task_id]
        passed, code, timed_out, tail = run_case(
            solution=path.read_text(encoding="utf-8"),
            test_setup=str(case["testSetup"]),
            test=str(case["test"]),
            target_root=target_root,
        )
        return {
            "taskId": task_id,
            "language": "rust",
            "passed": passed,
            "exitCode": code,
            "timedOut": timed_out,
            "outputTail": tail,
        }

    workers = max(1, min(args.workers, len(manifest["tasks"])))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(evaluate, manifest["tasks"]))
    for result in results:
        print(json.dumps(result, ensure_ascii=False))
    passed_count = sum(int(result["passed"]) for result in results)
    all_passed = passed_count == len(results)
    print(json.dumps({
        "summary": True,
        "patchApplied": True,
        "passedCount": passed_count,
        "taskCount": len(results),
        "allPassed": all_passed,
    }))
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
