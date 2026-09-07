#!/usr/bin/env python3
"""Freeze all 164 official HumanEvalFix Go docstring tasks."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import pandas as pd

from tools.prepare_aider_python20 import APPROVED_EMAIL, APPROVED_NAME


DATASET_COMMIT = "9a41762f73a8cb23bb5811b73d5aab164efcf378"


def run(argv: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> str:
    completed = subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"command failed ({completed.returncode}): {argv}\n{completed.stderr}")
    return completed.stdout.strip()


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def materialize(
    parquet: Path,
    output: Path,
    go_root: Path,
    runtime_root: Path,
) -> dict[str, object]:
    if output.exists():
        raise FileExistsError(output)
    parquet = parquet.resolve()
    go_root = go_root.resolve()
    runtime_root = runtime_root.resolve()
    go_binary = go_root / "bin" / "go"
    for required in (parquet, go_binary, runtime_root / "go.mod", runtime_root / "go.sum"):
        if not required.is_file():
            raise FileNotFoundError(required)
    if not (runtime_root / "pkg" / "mod").is_dir():
        raise FileNotFoundError(runtime_root / "pkg" / "mod")

    frame = pd.read_parquet(parquet).sort_values(
        "task_id", key=lambda column: column.str.split("/").str[-1].astype(int)
    )
    if len(frame) != 164 or frame["task_id"].nunique() != 164:
        raise ValueError("expected all 164 unique Go tasks")

    source = output / "source"
    private = output / "private"
    public = output / "public"
    source.mkdir(parents=True)
    private.mkdir()
    public.mkdir()
    tasks: list[dict[str, object]] = []
    cases: list[dict[str, str]] = []
    allowed: list[str] = []
    for row in frame.to_dict(orient="records"):
        original_id = str(row["task_id"])
        number = int(original_id.split("/")[-1])
        task_id = f"humanevalfix-go/{number:03d}"
        relative = Path("tasks") / "go" / f"{number:03d}"
        task_dir = source / relative
        task_dir.mkdir(parents=True)
        solution = "package main\n\n" + str(row["prompt"]).strip() + "\n" + str(row["buggy_solution"]).rstrip() + "\n"
        (task_dir / "solution.go").write_text(solution, encoding="utf-8")
        instruction = (
            f"Repair the buggy `{row['entry_point']}` implementation in `solution.go` so it satisfies its "
            "supplied documentation for all inputs. Preserve the declared signature and edit only `solution.go`."
        )
        tasks.append(
            {
                "taskId": task_id,
                "officialTaskId": original_id,
                "language": "go",
                "entryPoint": str(row["entry_point"]),
                "relativePath": relative.as_posix(),
                "solutionFiles": ["solution.go"],
                "testFiles": [],
                "instruction": instruction,
                "instructionSha256": digest(instruction.encode()),
                "starterSha256": digest(solution.encode()),
            }
        )
        cases.append(
            {
                "taskId": task_id,
                "officialTaskId": original_id,
                "entryPoint": str(row["entry_point"]),
                "testSetup": str(row["test_setup"]),
                "test": str(row["test"]),
            }
        )
        allowed.append((relative / "solution.go").as_posix())

    go_version = run([str(go_binary), "version"], cwd=source)
    manifest = {
        "schemaVersion": 1,
        "status": "frozen_before_model_calls",
        "benchmark": "BigCode HumanEvalPack HumanEvalFixDocs complete Go track",
        "officialDataset": "https://huggingface.co/datasets/bigcode/humanevalpack",
        "officialDatasetCommit": DATASET_COMMIT,
        "sourceParquetSha256": digest(parquet.read_bytes()),
        "selectionRule": "all 164 official Go tasks; no task selection",
        "variant": "HumanEvalFixDocs: documentation visible, official tests hidden",
        "goVersion": go_version,
        "testifyVersion": "v1.8.4",
        "testsAbsentFromAgentWorkspace": True,
        "canonicalSolutionsAbsentFromAgentAndEvaluator": True,
        "tasks": tasks,
    }
    manifest_text = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    cases_text = json.dumps(cases, indent=2, ensure_ascii=False) + "\n"
    (source / "benchmark_manifest.json").write_text(manifest_text, encoding="utf-8")
    (private / "benchmark_manifest.json").write_text(manifest_text, encoding="utf-8")
    (private / "cases.json").write_text(cases_text, encoding="utf-8")
    (source / ".gitignore").write_text("*.test\n", encoding="utf-8")

    task_listing = "\n".join(
        f"- {item['taskId']}: {item['relativePath']}/solution.go (`{item['entryPoint']}`)"
        for item in tasks
    )
    batch_instruction = (
        "Repair all 164 independent official BigCode HumanEvalFix Go tasks listed below. Each solution file "
        "contains the official documentation and one deliberately buggy implementation. Official tests and "
        "canonical solutions are unavailable. Inspect every file, infer the smallest general correction from its "
        "documentation, and edit only the listed solution.go files. Do not search for HumanEval answers or create "
        "tests.\n\n"
        + task_listing
    )

    run(["git", "init", "--quiet"], cwd=source)
    run(["git", "config", "user.name", APPROVED_NAME], cwd=source)
    run(["git", "config", "user.email", APPROVED_EMAIL], cwd=source)
    if run(["git", "config", "user.name"], cwd=source) != APPROVED_NAME:
        raise RuntimeError("unexpected git author name")
    if run(["git", "config", "user.email"], cwd=source) != APPROVED_EMAIL:
        raise RuntimeError("unexpected git author email")
    run(["git", "add", "."], cwd=source)
    run(["git", "commit", "--quiet", "-m", "Freeze complete HumanEvalFix Go164 track"], cwd=source)
    base_ref = run(["git", "rev-parse", "HEAD"], cwd=source)
    evaluator = (Path(__file__).resolve().parent / "evaluate_humanevalfix_go164.py").resolve()
    task_payload = {
        "task_id": "humanevalfix-go164-docs-v1",
        "instruction": batch_instruction,
        "base_ref": base_ref,
        "public_test_command": (
            f"python {json.dumps(str(evaluator))} --workspace . --private-root "
            f"{json.dumps(str(private.resolve()))} --go-root {json.dumps(str(go_root))} "
            f"--runtime-root {json.dumps(str(runtime_root))} --workers 4"
        ),
        "allowed_path_globs": allowed,
        "forbidden_path_globs": [
            ".git/*",
            "benchmark_manifest.json",
            ".gitignore",
            "go.mod",
            "go.sum",
            "**/*_test.go",
            "**/testdata/*",
        ],
    }
    task_path = public / "task.json"
    task_path.write_text(json.dumps(task_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    freeze = {
        "schemaVersion": 1,
        "status": "frozen_before_model_calls",
        "baseRef": base_ref,
        "sourceParquetSha256": digest(parquet.read_bytes()),
        "manifestSha256": digest(manifest_text.encode()),
        "privateCasesSha256": digest(cases_text.encode()),
        "taskSha256": digest(task_path.read_bytes()),
        "evaluatorSha256": digest(evaluator.read_bytes()),
        "goModSha256": digest((runtime_root / "go.mod").read_bytes()),
        "goSumSha256": digest((runtime_root / "go.sum").read_bytes()),
        "selectedTaskIds": [item["taskId"] for item in tasks],
    }
    freeze_bytes = (json.dumps(freeze, indent=2, ensure_ascii=False) + "\n").encode()
    (output / "freeze.json").write_bytes(freeze_bytes)
    return {**freeze, "freezeSha256": digest(freeze_bytes)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parquet", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--go-root", required=True, type=Path)
    parser.add_argument("--runtime-root", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(materialize(args.parquet, args.output, args.go_root, args.runtime_root)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
