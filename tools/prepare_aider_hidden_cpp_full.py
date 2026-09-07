#!/usr/bin/env python3
"""Freeze the complete official Aider C++ track with tests hidden."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from tools.prepare_aider_python20 import APPROVED_EMAIL, APPROVED_NAME


def run(argv: list[str], *, cwd: Path) -> str:
    completed = subprocess.run(argv, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"command failed ({completed.returncode}): {argv}\n{completed.stderr}")
    return completed.stdout.strip()


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def task_instruction(task_dir: Path, solution_files: list[str]) -> str:
    parts: list[str] = []
    for name in ("introduction.md", "instructions.md", "instructions.append.md"):
        path = task_dir / ".docs" / name
        if path.is_file():
            parts.append(path.read_text(encoding="utf-8").strip())
    parts.append(
        "Use the instructions above to modify only these supplied solution files: "
        f"{' '.join(solution_files)}. Preserve the declared public names and signatures. "
        "Use C++17 and only the standard library or dependencies already declared by the exercise. "
        "The hidden official tests are authoritative and must not be edited."
    )
    return "\n\n".join(parts).strip()


def remove_agent_tests(task_dir: Path, test_files: list[str]) -> None:
    for relative in test_files:
        path = task_dir / relative
        if path.is_file() or path.is_symlink():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
    if (task_dir / "test").is_dir():
        shutil.rmtree(task_dir / "test")


def materialize(source: Path, output: Path) -> dict[str, object]:
    if output.exists():
        raise FileExistsError(output)
    source = source.resolve()
    commit = run(["git", "rev-parse", "HEAD"], cwd=source)
    if run(["git", "status", "--porcelain"], cwd=source):
        raise RuntimeError("official source repository is dirty")
    root = source / "cpp" / "exercises" / "practice"
    selected = sorted(path for path in root.iterdir() if path.is_dir())
    if len(selected) != 26:
        raise ValueError(f"expected complete C++ track of 26 tasks, found {len(selected)}")

    agent_source = output / "source"
    evaluator_source = output / "private" / "evaluator_source"
    public = output / "public"
    agent_source.mkdir(parents=True)
    evaluator_source.mkdir(parents=True)
    public.mkdir()
    tasks: list[dict[str, object]] = []
    allowed: list[str] = []
    for original in selected:
        config = json.loads((original / ".meta" / "config.json").read_text(encoding="utf-8"))
        solution_files = list(config["files"]["solution"])
        test_files = list(config["files"]["test"])
        relative = Path("tasks") / "cpp" / original.name
        agent_task = agent_source / relative
        evaluator_task = evaluator_source / relative
        shutil.copytree(original, agent_task)
        shutil.copytree(original, evaluator_task)
        for task_copy in (agent_task, evaluator_task):
            if (task_copy / ".meta").is_dir():
                shutil.rmtree(task_copy / ".meta")
            if (task_copy / ".approaches").is_dir():
                shutil.rmtree(task_copy / ".approaches")
        remove_agent_tests(agent_task, test_files)
        instruction = task_instruction(original, solution_files)
        item = {
            "taskId": f"aider-cpp/{original.name}",
            "language": "cpp",
            "name": original.name,
            "relativePath": relative.as_posix(),
            "solutionFiles": solution_files,
            "testFiles": test_files,
            "officialTree": run(["git", "rev-parse", f"HEAD:cpp/exercises/practice/{original.name}"], cwd=source),
            "instruction": instruction,
            "instructionSha256": digest(instruction.encode()),
        }
        tasks.append(item)
        allowed.extend((relative / name).as_posix() for name in solution_files)

    manifest = {
        "schemaVersion": 1,
        "status": "frozen_before_model_calls",
        "benchmark": "Aider-AI/polyglot-benchmark complete hidden-test C++ track",
        "officialRepository": "https://github.com/Aider-AI/polyglot-benchmark",
        "officialCommit": commit,
        "selectionRule": "all 26 official C++ exercises; no task selection",
        "testsAbsentFromAgentWorkspace": True,
        "goldExamplesAbsentEverywhere": True,
        "tasks": tasks,
    }
    manifest_text = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    for path in (
        agent_source / "benchmark_manifest.json",
        evaluator_source / "benchmark_manifest.json",
        output / "private" / "benchmark_manifest.json",
    ):
        path.write_text(manifest_text, encoding="utf-8")
    (agent_source / ".gitignore").write_text("**/build/\n", encoding="utf-8")
    combined = "\n\n".join(
        f"## {item['taskId']}\nSolution files: {' '.join(item['solutionFiles'])}\n\n{item['instruction']}"
        for item in tasks
    )
    instruction = (
        "Solve all 26 independent official Aider C++ benchmark exercises in the frozen order below. "
        "Official tests and gold implementations are unavailable. Work only in listed solution files, infer edge "
        "cases from the official instructions, and do not search for exercise solutions. Do not edit tests, "
        "CMakeLists.txt, benchmark_manifest.json, .docs files, or repository metadata.\n\n" + combined
    )
    run(["git", "init", "--quiet"], cwd=agent_source)
    run(["git", "config", "user.name", APPROVED_NAME], cwd=agent_source)
    run(["git", "config", "user.email", APPROVED_EMAIL], cwd=agent_source)
    run(["git", "add", "."], cwd=agent_source)
    run(["git", "commit", "--quiet", "-m", "Freeze complete hidden-test Aider C++ track"], cwd=agent_source)
    base_ref = run(["git", "rev-parse", "HEAD"], cwd=agent_source)
    evaluator = (Path(__file__).resolve().parent / "evaluate_aider_hidden_cpp_full.py").resolve()
    private_root = (output / "private").resolve()
    task_payload = {
        "task_id": "aider-hidden-cpp26-v1",
        "instruction": instruction,
        "base_ref": base_ref,
        "public_test_command": f"python {json.dumps(str(evaluator))} --workspace . --private-root {json.dumps(str(private_root))}",
        "allowed_path_globs": allowed,
        "forbidden_path_globs": [
            ".git/*", "benchmark_manifest.json", ".gitignore", "**/.docs/*", "**/*_test.cpp",
            "**/test/*", "**/CMakeLists.txt",
        ],
    }
    task_path = public / "task.json"
    task_path.write_text(json.dumps(task_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    freeze = {
        "schemaVersion": 1,
        "status": "frozen_before_model_calls",
        "sourceCommit": commit,
        "baseRef": base_ref,
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
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(materialize(args.source, args.output)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
