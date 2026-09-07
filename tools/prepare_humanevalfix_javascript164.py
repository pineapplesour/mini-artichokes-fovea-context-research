#!/usr/bin/env python3
"""Freeze all 164 official HumanEvalFix JavaScript docstring tasks."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import pandas as pd

from tools.prepare_aider_python20 import APPROVED_EMAIL, APPROVED_NAME


DATASET_COMMIT = "9a41762f73a8cb23bb5811b73d5aab164efcf378"


def run(argv: list[str], *, cwd: Path) -> str:
    completed = subprocess.run(
        argv,
        cwd=cwd,
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
    node_binary: Path,
    node_modules: Path,
) -> dict[str, object]:
    if output.exists():
        raise FileExistsError(output)
    parquet = parquet.resolve()
    node_binary = node_binary.resolve()
    node_modules = node_modules.resolve()
    if not parquet.is_file():
        raise FileNotFoundError(parquet)
    if not node_binary.is_file():
        raise FileNotFoundError(node_binary)
    js_md5_package = node_modules / "js-md5" / "package.json"
    if not js_md5_package.is_file():
        raise FileNotFoundError(js_md5_package)
    js_md5_metadata = json.loads(js_md5_package.read_text(encoding="utf-8"))
    if js_md5_metadata.get("version") != "0.7.3":
        raise ValueError("HumanEvalPack requires js-md5@0.7.3")

    frame = pd.read_parquet(parquet).sort_values(
        "task_id", key=lambda column: column.str.split("/").str[-1].astype(int)
    )
    if len(frame) != 164 or frame["task_id"].nunique() != 164:
        raise ValueError("expected all 164 unique JavaScript tasks")

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
        task_id = f"humanevalfix-javascript/{number:03d}"
        relative = Path("tasks") / "javascript" / f"{number:03d}"
        task_dir = source / relative
        task_dir.mkdir(parents=True)
        solution = str(row["prompt"]).rstrip() + "\n" + str(row["buggy_solution"]).rstrip() + "\n"
        solution_path = task_dir / "solution.js"
        solution_path.write_text(solution, encoding="utf-8")
        instruction = (
            f"Repair the buggy `{row['entry_point']}` implementation in `solution.js` so it satisfies its "
            "supplied documentation for all inputs. Preserve the declared signature and edit only `solution.js`."
        )
        tasks.append(
            {
                "taskId": task_id,
                "officialTaskId": original_id,
                "language": "javascript",
                "entryPoint": str(row["entry_point"]),
                "relativePath": relative.as_posix(),
                "solutionFiles": ["solution.js"],
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
        allowed.append((relative / "solution.js").as_posix())

    node_version = run([str(node_binary), "--version"], cwd=source)
    manifest = {
        "schemaVersion": 1,
        "status": "frozen_before_model_calls",
        "benchmark": "BigCode HumanEvalPack HumanEvalFixDocs complete JavaScript track",
        "officialDataset": "https://huggingface.co/datasets/bigcode/humanevalpack",
        "officialDatasetCommit": DATASET_COMMIT,
        "sourceParquetSha256": digest(parquet.read_bytes()),
        "selectionRule": "all 164 official JavaScript tasks; no task selection",
        "variant": "HumanEvalFixDocs: documentation visible, official tests hidden",
        "nodeVersion": node_version,
        "jsMd5Version": js_md5_metadata["version"],
        "testsAbsentFromAgentWorkspace": True,
        "canonicalSolutionsAbsentFromAgentAndEvaluator": True,
        "tasks": tasks,
    }
    manifest_text = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    cases_text = json.dumps(cases, indent=2, ensure_ascii=False) + "\n"
    (source / "benchmark_manifest.json").write_text(manifest_text, encoding="utf-8")
    (private / "benchmark_manifest.json").write_text(manifest_text, encoding="utf-8")
    (private / "cases.json").write_text(cases_text, encoding="utf-8")
    (source / ".gitignore").write_text("node_modules/\nnpm-debug.log\n", encoding="utf-8")

    task_listing = "\n".join(
        f"- {item['taskId']}: {item['relativePath']}/solution.js (`{item['entryPoint']}`)"
        for item in tasks
    )
    batch_instruction = (
        "Repair all 164 independent official BigCode HumanEvalFix JavaScript tasks listed below. Each solution "
        "file contains the official documentation and one deliberately buggy implementation. Official tests and "
        "canonical solutions are unavailable. Inspect every file, infer the smallest general correction from its "
        "documentation, and edit only the listed solution.js files. Do not search for HumanEval answers or create "
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
    run(["git", "commit", "--quiet", "-m", "Freeze complete HumanEvalFix JavaScript164 track"], cwd=source)
    base_ref = run(["git", "rev-parse", "HEAD"], cwd=source)
    evaluator = (Path(__file__).resolve().parent / "evaluate_humanevalfix_javascript164.py").resolve()
    task_payload = {
        "task_id": "humanevalfix-javascript164-docs-v1",
        "instruction": batch_instruction,
        "base_ref": base_ref,
        "public_test_command": (
            f"python {json.dumps(str(evaluator))} --workspace . --private-root "
            f"{json.dumps(str(private.resolve()))} --node {json.dumps(str(node_binary))} "
            f"--node-modules {json.dumps(str(node_modules))}"
        ),
        "allowed_path_globs": allowed,
        "forbidden_path_globs": [
            ".git/*",
            "benchmark_manifest.json",
            ".gitignore",
            "node_modules/*",
            "**/*test*.js",
            "**/__tests__/*",
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
        "selectedTaskIds": [item["taskId"] for item in tasks],
    }
    freeze_bytes = (json.dumps(freeze, indent=2, ensure_ascii=False) + "\n").encode()
    (output / "freeze.json").write_bytes(freeze_bytes)
    return {**freeze, "freezeSha256": digest(freeze_bytes)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parquet", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--node", required=True, type=Path)
    parser.add_argument("--node-modules", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(materialize(args.parquet, args.output, args.node, args.node_modules)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
