#!/usr/bin/env python3
"""Evaluate a complete HumanEvalFix-style workspace on HumanEval+ v0.1.10.

The benchmark data and canonical oracle stay outside the model workspace.  The
script emits the same compact JSONL outcome contract used by the whole-track
repair runner, without revealing test inputs or expected outputs.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import pickle
import sys
from pathlib import Path
from typing import Any


EXPECTED_IDS = tuple(f"HumanEval/{index}" for index in range(164))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_dataset(path: Path) -> dict[str, dict[str, Any]]:
    problems: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            item = json.loads(line)
            problems[item["task_id"]] = item
    if tuple(sorted(problems, key=lambda item: int(item.split("/")[-1]))) != EXPECTED_IDS:
        raise ValueError("HumanEval+ dataset is not the complete canonical 164-task suite")
    required = {
        "prompt",
        "canonical_solution",
        "base_input",
        "plus_input",
        "entry_point",
        "atol",
    }
    for task_id, problem in problems.items():
        missing = required.difference(problem)
        if missing:
            raise ValueError(f"{task_id} missing fields: {sorted(missing)}")
    return problems


def load_or_build_oracle(
    *, problems: dict[str, dict[str, Any]], dataset_path: Path, cache_path: Path
) -> dict[str, dict[str, Any]]:
    from evalplus.gen.util import trusted_exec

    dataset_sha256 = sha256_file(dataset_path)
    if cache_path.exists():
        with cache_path.open("rb") as handle:
            payload = pickle.load(handle)
        if payload.get("datasetSha256") != dataset_sha256:
            raise ValueError("oracle cache does not match the frozen dataset")
        return payload["expected"]

    expected: dict[str, dict[str, Any]] = {}
    for task_id in EXPECTED_IDS:
        problem = problems[task_id]
        code = problem["prompt"] + problem["canonical_solution"]
        base, base_time = trusted_exec(
            code,
            problem["base_input"],
            problem["entry_point"],
            record_time=True,
        )
        plus, plus_time = trusted_exec(
            code,
            problem["plus_input"],
            problem["entry_point"],
            record_time=True,
        )
        expected[task_id] = {
            "base": base,
            "base_time": base_time,
            "plus": plus,
            "plus_time": plus_time,
        }
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with cache_path.open("wb") as handle:
        pickle.dump(
            {"schemaVersion": 1, "datasetSha256": dataset_sha256, "expected": expected},
            handle,
            protocol=pickle.HIGHEST_PROTOCOL,
        )
    return expected


def evaluate_one(
    task_id: str,
    problem: dict[str, Any],
    expected: dict[str, Any],
    code: str,
) -> dict[str, Any]:
    from evalplus.eval import PASS, TIMEOUT, untrusted_check

    base_status, _ = untrusted_check(
        "humaneval",
        code,
        problem["base_input"],
        problem["entry_point"],
        expected=expected["base"],
        atol=problem["atol"],
        ref_time=expected["base_time"],
        fast_check=True,
    )
    plus_status, _ = untrusted_check(
        "humaneval",
        code,
        problem["plus_input"],
        problem["entry_point"],
        expected=expected["plus"],
        atol=problem["atol"],
        ref_time=expected["plus_time"],
        fast_check=True,
    )
    passed = base_status == PASS and plus_status == PASS
    index = int(task_id.split("/")[-1])
    return {
        "taskId": f"humanevalfix-python/{index:03d}",
        "language": "python",
        "passed": passed,
        "exitCode": 0 if passed else 1,
        "timedOut": base_status == TIMEOUT or plus_status == TIMEOUT,
        "outputTail": f"HumanEval+ base={base_status}; plus={plus_status}",
        "baseStatus": base_status,
        "plusStatus": plus_status,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--evalplus-root", required=True, type=Path)
    parser.add_argument("--oracle-cache", required=True, type=Path)
    parser.add_argument("--canonical", action="store_true")
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()

    sys.path.insert(0, str(args.evalplus_root.resolve()))
    problems = load_dataset(args.dataset.resolve())
    expected = load_or_build_oracle(
        problems=problems,
        dataset_path=args.dataset.resolve(),
        cache_path=args.oracle_cache.resolve(),
    )

    jobs: list[tuple[str, dict[str, Any], dict[str, Any], str]] = []
    for task_id in EXPECTED_IDS:
        problem = problems[task_id]
        index = int(task_id.split("/")[-1])
        if args.canonical:
            code = problem["prompt"] + problem["canonical_solution"]
        else:
            if args.workspace is None:
                parser.error("--workspace is required unless --canonical is used")
            solution_path = args.workspace.resolve() / f"tasks/python/{index:03d}/solution.py"
            if not solution_path.is_file():
                raise FileNotFoundError(solution_path)
            code = solution_path.read_text(encoding="utf-8")
        jobs.append((task_id, problem, expected[task_id], code))

    results: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as executor:
        futures = [executor.submit(evaluate_one, *job) for job in jobs]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda item: item["taskId"])
    for result in results:
        print(json.dumps(result, ensure_ascii=False), flush=True)
    passed_count = sum(bool(item["passed"]) for item in results)
    summary = {
        "summary": True,
        "benchmark": "HumanEval+ v0.1.10",
        "datasetSha256": sha256_file(args.dataset.resolve()),
        "passedCount": passed_count,
        "taskCount": len(results),
        "allPassed": passed_count == len(results),
    }
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    return 0 if summary["allPassed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
