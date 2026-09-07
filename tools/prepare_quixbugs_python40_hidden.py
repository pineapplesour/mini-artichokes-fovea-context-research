#!/usr/bin/env python3
"""Freeze all 40 official QuixBugs Python programs with tests held private."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from tools.prepare_aider_python20 import APPROVED_EMAIL, APPROVED_NAME


UPSTREAM_COMMIT = "4257f44b0ff1181dedaedee6a447e133219fcebf"


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def run(argv: list[str], *, cwd: Path) -> str:
    completed = subprocess.run(
        argv,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"command failed ({completed.returncode}): {argv}\n{completed.stdout}")
    return completed.stdout.strip()


def materialize(upstream: Path, output: Path, python_binary: Path) -> dict[str, object]:
    upstream = upstream.resolve()
    output = output.resolve()
    python_binary = python_binary.resolve()
    if output.exists():
        raise FileExistsError(output)
    if run(["git", "rev-parse", "HEAD"], cwd=upstream) != UPSTREAM_COMMIT:
        raise ValueError("QuixBugs upstream is not at the frozen commit")
    if run(["git", "status", "--porcelain"], cwd=upstream):
        raise ValueError("QuixBugs upstream worktree is dirty")
    if not python_binary.is_file():
        raise FileNotFoundError(python_binary)

    tests = sorted((upstream / "python_testcases").glob("test_*.py"))
    names = [path.stem.removeprefix("test_") for path in tests]
    if len(names) != 40 or len(set(names)) != 40:
        raise ValueError("expected all 40 unique official Python test files")
    for name in names:
        if not (upstream / "python_programs" / f"{name}.py").is_file():
            raise FileNotFoundError(name)
        if not (upstream / "correct_python_programs" / f"{name}.py").is_file():
            raise FileNotFoundError(f"correct {name}")

    source = output / "source"
    private = output / "private"
    public = output / "public"
    (source / "python_programs").mkdir(parents=True)
    (private / "python_testcases").mkdir(parents=True)
    (private / "json_testcases").mkdir()
    public.mkdir()

    tasks: list[dict[str, object]] = []
    allowed: list[str] = []
    for name, test_path in zip(names, tests, strict=True):
        relative = Path("python_programs")
        solution_name = f"{name}.py"
        source_path = upstream / relative / solution_name
        shutil.copy2(source_path, source / relative / solution_name)
        task_id = f"quixbugs-python/{name}"
        instruction = (
            f"Repair the deliberately buggy official QuixBugs program `{name}` in "
            f"`python_programs/{solution_name}` so it satisfies its embedded specification for all valid inputs."
        )
        tasks.append(
            {
                "taskId": task_id,
                "officialProgram": name,
                "language": "python",
                "relativePath": relative.as_posix(),
                "solutionFiles": [solution_name],
                "testFiles": [],
                "officialTestFile": test_path.name,
                "instruction": instruction,
                "instructionSha256": digest(instruction.encode()),
                "starterSha256": digest(source_path.read_bytes()),
            }
        )
        allowed.append((relative / solution_name).as_posix())

    shutil.copy2(upstream / "python_programs" / "node.py", source / "python_programs" / "node.py")
    shutil.copy2(upstream / "conftest.py", private / "conftest.py")
    for path in (upstream / "python_testcases").glob("*.py"):
        shutil.copy2(path, private / "python_testcases" / path.name)
    for path in (upstream / "json_testcases").glob("*.json"):
        shutil.copy2(path, private / "json_testcases" / path.name)

    python_version = run([str(python_binary), "--version"], cwd=source)
    manifest = {
        "schemaVersion": 1,
        "status": "frozen_before_model_calls",
        "benchmark": "QuixBugs complete Python40 hidden-test variant",
        "officialRepository": "https://github.com/jkoppel/QuixBugs",
        "officialCommit": UPSTREAM_COMMIT,
        "selectionRule": "all 40 official Python programs; no task selection",
        "variant": "buggy source and embedded specification visible; official tests and corrected programs hidden",
        "pythonVersion": python_version,
        "officialSlowTestPolicy": "upstream default: slow knapsack case and ignored levenshtein case remain skipped",
        "testsAbsentFromAgentWorkspace": True,
        "correctImplementationsAbsentFromAgentWorkspace": True,
        "tasks": tasks,
    }
    manifest_text = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    (source / "benchmark_manifest.json").write_text(manifest_text, encoding="utf-8")
    (private / "benchmark_manifest.json").write_text(manifest_text, encoding="utf-8")
    (source / ".gitignore").write_text("**/__pycache__/\n*.pyc\n", encoding="utf-8")
    (source / "README.md").write_text(
        "# Frozen QuixBugs Python40 repair batch\n\n"
        "All 40 buggy official Python programs are present. Official tests and corrected programs are held out.\n",
        encoding="utf-8",
    )

    listing = "\n".join(
        f"- {item['taskId']}: {item['relativePath']}/{item['solutionFiles'][0]}"
        for item in tasks
    )
    batch_instruction = (
        "Repair all 40 official QuixBugs Python programs listed below. Every program contains a deliberately "
        "introduced defect and an embedded specification or algorithm identity. Official tests and corrected "
        "implementations are unavailable. Inspect every program, infer the smallest general repair, and edit only "
        "the listed algorithm modules. Do not create repository tests or search for QuixBugs answers.\n\n" + listing
    )

    run(["git", "init", "--quiet"], cwd=source)
    run(["git", "config", "user.name", APPROVED_NAME], cwd=source)
    run(["git", "config", "user.email", APPROVED_EMAIL], cwd=source)
    run(["git", "add", "."], cwd=source)
    run(["git", "commit", "--quiet", "-m", "Freeze complete QuixBugs Python40 hidden-test track"], cwd=source)
    base_ref = run(["git", "rev-parse", "HEAD"], cwd=source)

    evaluator = (Path(__file__).resolve().parent / "evaluate_quixbugs_python40_hidden.py").resolve()
    task_payload = {
        "task_id": "quixbugs-python40-hidden-v1",
        "instruction": batch_instruction,
        "base_ref": base_ref,
        "public_test_command": (
            f"python {json.dumps(str(evaluator))} --workspace . --private-root "
            f"{json.dumps(str(private))} --python {json.dumps(str(python_binary))} --workers 4"
        ),
        "allowed_path_globs": allowed,
        "forbidden_path_globs": [
            ".git/*",
            "benchmark_manifest.json",
            "README.md",
            ".gitignore",
            "python_programs/node.py",
            "**/__pycache__/*",
            "**/*.pyc",
            "**/*test*.py",
        ],
    }
    task_path = public / "task.json"
    task_path.write_text(json.dumps(task_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    freeze = {
        "schemaVersion": 1,
        "status": "frozen_before_model_calls",
        "baseRef": base_ref,
        "officialCommit": UPSTREAM_COMMIT,
        "manifestSha256": digest(manifest_text.encode()),
        "taskSha256": digest(task_path.read_bytes()),
        "evaluatorSha256": digest(evaluator.read_bytes()),
        "selectedTaskIds": [item["taskId"] for item in tasks],
    }
    freeze_bytes = (json.dumps(freeze, indent=2, ensure_ascii=False) + "\n").encode()
    (output / "freeze.json").write_bytes(freeze_bytes)
    return {**freeze, "freezeSha256": digest(freeze_bytes)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--upstream", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--python", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(materialize(args.upstream, args.output, args.python)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
