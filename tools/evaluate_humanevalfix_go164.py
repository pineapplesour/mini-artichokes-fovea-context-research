#!/usr/bin/env python3
"""Score a frozen HumanEvalFix Go track against hidden official tests."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


GO_IMPORT_HELPER = (
    "math",
    "strings",
    "fmt",
    "strconv",
    "time",
    "bytes",
    "regexp",
    "sort",
    "math/rand",
    "crypto/md5",
)


def compose_check_program(solution: str, test_setup: str, test: str) -> str:
    """Mirror HumanEvalPack's single-file Go import normalization."""
    candidate = solution.replace("package main", "", 1)
    normalized_setup = test_setup + "\n"
    for raw in test_setup.splitlines():
        package_line = (
            raw.replace("import", "").replace("(", "").replace(")", "").strip()
        )
        if package_line.startswith('"') and package_line in candidate:
            normalized_setup = normalized_setup.replace(package_line, "")

    scan_program = normalized_setup + candidate + "\n" + test
    injected: list[str] = []
    for package in GO_IMPORT_HELPER:
        quoted = f'"{package}"'
        short = package.split("/")[-1]
        if quoted in scan_program:
            continue
        if any(
            f"{short}." in line and not line.strip().startswith("//")
            for line in scan_program.splitlines()
        ):
            injected.append(quoted)
    import_block = ""
    if injected:
        import_block = "import (\n" + "\n".join(f"    {item}" for item in sorted(injected)) + "\n)\n"
    return normalized_setup + import_block + candidate + "\n" + test + "\n"


def run_case(
    *,
    go_binary: Path,
    go_root: Path,
    module_cache: Path,
    build_cache: Path,
    go_mod: str,
    go_sum: str,
    solution: str,
    test_setup: str,
    test: str,
) -> tuple[bool, int | None, bool, str]:
    env = os.environ.copy()
    env.update(
        {
            "GOROOT": str(go_root),
            "GOMODCACHE": str(module_cache),
            "GOCACHE": str(build_cache),
            "GOTOOLCHAIN": "local",
            "GOPROXY": "off",
            "GOSUMDB": "off",
            "CGO_ENABLED": "0",
            "GOMAXPROCS": "1",
            "GOFLAGS": "-mod=mod",
            "TZ": "UTC",
            "LC_ALL": "C.UTF-8",
        }
    )
    with tempfile.TemporaryDirectory(prefix="humanevalfix-go-case-") as temporary:
        root = Path(temporary)
        (root / "go.mod").write_text(go_mod, encoding="utf-8")
        (root / "go.sum").write_text(go_sum, encoding="utf-8")
        check_program = compose_check_program(solution, test_setup, test)
        (root / "main_test.go").write_text(check_program, encoding="utf-8")
        try:
            completed = subprocess.run(
                [str(go_binary), "test", "-count=1", "-timeout=20s", "."],
                cwd=root,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=60,
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
    parser.add_argument("--go-root", required=True, type=Path)
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    private_root = args.private_root.resolve()
    go_root = args.go_root.resolve()
    runtime_root = args.runtime_root.resolve()
    go_binary = go_root / "bin" / "go"
    module_cache = runtime_root / "pkg" / "mod"
    build_cache = runtime_root / "cache"
    for required in (go_binary, runtime_root / "go.mod", runtime_root / "go.sum"):
        if not required.is_file():
            raise FileNotFoundError(required)
    if not module_cache.is_dir():
        raise FileNotFoundError(module_cache)
    build_cache.mkdir(parents=True, exist_ok=True)

    cases = json.loads((private_root / "cases.json").read_text(encoding="utf-8"))
    manifest = json.loads((private_root / "benchmark_manifest.json").read_text(encoding="utf-8"))
    case_by_id = {item["taskId"]: item for item in cases}
    if len(case_by_id) != len(cases):
        raise ValueError("duplicate private task IDs")
    if set(case_by_id) != {item["taskId"] for item in manifest["tasks"]}:
        raise ValueError("private cases and manifest differ")
    go_mod = (runtime_root / "go.mod").read_text(encoding="utf-8")
    go_sum = (runtime_root / "go.sum").read_text(encoding="utf-8")

    def evaluate(item: dict[str, object]) -> dict[str, object]:
        task_id = str(item["taskId"])
        solution_path = workspace / str(item["relativePath"]) / str(item["solutionFiles"][0])
        case = case_by_id[task_id]
        passed, code, timed_out, tail = run_case(
            go_binary=go_binary,
            go_root=go_root,
            module_cache=module_cache,
            build_cache=build_cache,
            go_mod=go_mod,
            go_sum=go_sum,
            solution=solution_path.read_text(encoding="utf-8"),
            test_setup=case["testSetup"],
            test=case["test"],
        )
        return {
            "taskId": task_id,
            "language": "go",
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
