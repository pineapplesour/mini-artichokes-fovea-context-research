#!/usr/bin/env python3
"""Freeze the complete official Aider JavaScript track with tests hidden."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from tools.prepare_aider_python20 import APPROVED_EMAIL, APPROVED_NAME


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


def task_instruction(task_dir: Path, solution_files: list[str]) -> str:
    parts: list[str] = []
    for name in ("introduction.md", "instructions.md", "instructions.append.md"):
        path = task_dir / ".docs" / name
        if path.is_file():
            parts.append(path.read_text(encoding="utf-8").strip())
    parts.append(
        "Use the instructions above to modify only these supplied solution files: "
        f"{' '.join(solution_files)}. Preserve all exported identifiers and signatures. "
        "Use the JavaScript runtime and dependencies already declared by the exercise. "
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


def materialize(source: Path, output: Path, node_root: Path, dependencies: Path) -> dict[str, object]:
    if output.exists():
        raise FileExistsError(output)
    source = source.resolve()
    node_root = node_root.resolve()
    dependencies = dependencies.resolve()
    node_binary = node_root / "bin" / "node"
    npm_binary = node_root / "bin" / "npm"
    jest_cli = dependencies / "node_modules" / "jest" / "bin" / "jest.js"
    package_lock = dependencies / "package-lock.json"
    for required in (node_binary, npm_binary, jest_cli, package_lock):
        if not required.is_file():
            raise FileNotFoundError(required)

    node_version = run([str(node_binary), "--version"], cwd=source)
    npm_version = run([str(npm_binary), "--version"], cwd=source)
    jest_version = run([str(node_binary), str(jest_cli), "--version"], cwd=source)
    commit = run(["git", "rev-parse", "HEAD"], cwd=source)
    if run(["git", "status", "--porcelain"], cwd=source):
        raise RuntimeError("official source repository is dirty")
    root = source / "javascript" / "exercises" / "practice"
    selected = sorted(path for path in root.iterdir() if path.is_dir())
    if len(selected) != 49:
        raise ValueError(f"expected complete JavaScript track of 49 tasks, found {len(selected)}")

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
        declared_tests = set(config["files"]["test"])
        conventional_tests = {
            path.relative_to(original).as_posix()
            for path in original.rglob("*")
            if path.is_file()
            and (path.name.endswith(".spec.js") or path.name.endswith(".test.js"))
        }
        test_files = sorted(declared_tests | conventional_tests)
        relative = Path("tasks") / "javascript" / original.name
        agent_task = agent_source / relative
        evaluator_task = evaluator_source / relative
        shutil.copytree(original, agent_task)
        shutil.copytree(original, evaluator_task)
        for task_copy in (agent_task, evaluator_task):
            for hidden_dir in (".meta", ".approaches"):
                hidden = task_copy / hidden_dir
                if hidden.is_dir():
                    shutil.rmtree(hidden)
        remove_agent_tests(agent_task, test_files)
        instruction = task_instruction(original, solution_files)
        item = {
            "taskId": f"aider-javascript/{original.name}",
            "language": "javascript",
            "name": original.name,
            "relativePath": relative.as_posix(),
            "solutionFiles": solution_files,
            "testFiles": test_files,
            "officialTree": run(
                ["git", "rev-parse", f"HEAD:javascript/exercises/practice/{original.name}"],
                cwd=source,
            ),
            "instruction": instruction,
            "instructionSha256": digest(instruction.encode()),
        }
        tasks.append(item)
        allowed.extend((relative / name).as_posix() for name in solution_files)

    manifest = {
        "schemaVersion": 1,
        "status": "frozen_before_model_calls",
        "benchmark": "Aider-AI/polyglot-benchmark complete hidden-test JavaScript track",
        "officialRepository": "https://github.com/Aider-AI/polyglot-benchmark",
        "officialCommit": commit,
        "selectionRule": "all 49 official JavaScript exercises; no task selection",
        "nodeVersion": node_version,
        "npmVersion": npm_version,
        "jestVersion": jest_version,
        "dependencyLockSha256": digest(package_lock.read_bytes()),
        "testsAbsentFromAgentWorkspace": True,
        "goldExamplesAbsentEverywhere": True,
        "tasks": tasks,
    }
    manifest_text = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    for destination in (
        agent_source / "benchmark_manifest.json",
        evaluator_source / "benchmark_manifest.json",
        output / "private" / "benchmark_manifest.json",
    ):
        destination.write_text(manifest_text, encoding="utf-8")
    (agent_source / ".gitignore").write_text("**/node_modules\n", encoding="utf-8")
    combined = "\n\n".join(
        f"## {item['taskId']}\nSolution files: {' '.join(item['solutionFiles'])}\n\n{item['instruction']}"
        for item in tasks
    )
    instruction = (
        "Solve all 49 independent official Aider JavaScript benchmark exercises in the frozen order below. "
        "Official tests and gold implementations are unavailable. Work only in listed solution files, infer edge "
        "cases from the official instructions, and do not search for exercise solutions. Do not edit tests, "
        "package files, lockfiles, benchmark_manifest.json, .docs files, or repository metadata.\n\n"
        + combined
    )
    run(["git", "init", "--quiet"], cwd=agent_source)
    run(["git", "config", "user.name", APPROVED_NAME], cwd=agent_source)
    run(["git", "config", "user.email", APPROVED_EMAIL], cwd=agent_source)
    run(["git", "add", "."], cwd=agent_source)
    run(["git", "commit", "--quiet", "-m", "Freeze complete hidden-test Aider JavaScript track"], cwd=agent_source)
    base_ref = run(["git", "rev-parse", "HEAD"], cwd=agent_source)
    evaluator = (Path(__file__).resolve().parent / "evaluate_aider_hidden_javascript_full.py").resolve()
    private_root = (output / "private").resolve()
    task_payload = {
        "task_id": "aider-hidden-javascript49-v1",
        "instruction": instruction,
        "base_ref": base_ref,
        "public_test_command": (
            f"python {json.dumps(str(evaluator))} --workspace . --private-root "
            f"{json.dumps(str(private_root))} --node-root {json.dumps(str(node_root))} "
            f"--dependencies {json.dumps(str(dependencies))}"
        ),
        "allowed_path_globs": allowed,
        "forbidden_path_globs": [
            ".git/*",
            "benchmark_manifest.json",
            ".gitignore",
            "**/.docs/*",
            "**/.meta/*",
            "**/*.spec.js",
            "**/*.test.js",
            "**/package.json",
            "**/package-lock.json",
            "**/babel.config.js",
            "**/.eslintrc",
            "**/.npmrc",
        ],
    }
    task_path = public / "task.json"
    task_path.write_text(json.dumps(task_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    freeze = {
        "schemaVersion": 1,
        "status": "frozen_before_model_calls",
        "sourceCommit": commit,
        "baseRef": base_ref,
        "nodeVersion": node_version,
        "npmVersion": npm_version,
        "jestVersion": jest_version,
        "dependencyLockSha256": digest(package_lock.read_bytes()),
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
    parser.add_argument("--node-root", required=True, type=Path)
    parser.add_argument("--dependencies", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(materialize(args.source, args.output, args.node_root, args.dependencies)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

