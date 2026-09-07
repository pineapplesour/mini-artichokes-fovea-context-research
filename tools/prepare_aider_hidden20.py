#!/usr/bin/env python3
"""Freeze complete or ranked Python/Rust Aider tasks with tests hidden."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from tools.prepare_aider_python20 import APPROVED_EMAIL, APPROVED_NAME, task_instruction


DEFAULT_SEED = "mini-artichokes-aider-hidden-py10-rust10-v1-20260902"


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


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def rank(paths: list[Path], seed: str) -> list[Path]:
    return sorted(
        paths,
        key=lambda path: hashlib.sha256(f"{seed}\0{path.parents[2].name}/{path.name}".encode()).hexdigest(),
    )


def select(
    source: Path,
    *,
    seed: str,
    python_count: int,
    rust_count: int,
    excluded_python: set[str],
) -> list[tuple[str, Path]]:
    py_root = source / "python" / "exercises" / "practice"
    rs_root = source / "rust" / "exercises" / "practice"
    python = [p for p in py_root.iterdir() if p.is_dir() and p.name not in excluded_python]
    rust = [p for p in rs_root.iterdir() if p.is_dir()]
    if len(python) < python_count or len(rust) < rust_count:
        raise ValueError("not enough unseen official tasks")
    return [("python", p) for p in rank(python, seed)[:python_count]] + [
        ("rust", p) for p in rank(rust, seed)[:rust_count]
    ]


def remove_tests(task_dir: Path, test_files: list[str]) -> None:
    for relative in test_files:
        path = task_dir / relative
        if path.is_file() or path.is_symlink():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)


def materialize(
    source: Path,
    output: Path,
    *,
    seed: str,
    python_count: int,
    rust_count: int,
    excluded_python: set[str],
) -> dict[str, object]:
    if output.exists():
        raise FileExistsError(output)
    source = source.resolve()
    commit = run(["git", "rev-parse", "HEAD"], cwd=source)
    if run(["git", "status", "--porcelain"], cwd=source):
        raise RuntimeError("official source repository is dirty")
    selected = select(
        source,
        seed=seed,
        python_count=python_count,
        rust_count=rust_count,
        excluded_python=excluded_python,
    )

    agent_source = output / "source"
    evaluator_source = output / "private" / "evaluator_source"
    public = output / "public"
    agent_source.mkdir(parents=True)
    evaluator_source.mkdir(parents=True)
    public.mkdir()
    tasks: list[dict[str, object]] = []
    allowed: list[str] = []

    for language, original in selected:
        config = json.loads((original / ".meta" / "config.json").read_text(encoding="utf-8"))
        solution_files = list(config["files"]["solution"])
        test_files = list(config["files"]["test"])
        relative = Path("tasks") / language / original.name
        agent_task = agent_source / relative
        evaluator_task = evaluator_source / relative
        shutil.copytree(original, agent_task)
        shutil.copytree(original, evaluator_task)
        shutil.rmtree(agent_task / ".meta")
        shutil.rmtree(evaluator_task / ".meta")
        remove_tests(agent_task, test_files)
        tree = run(
            ["git", "rev-parse", f"HEAD:{language}/exercises/practice/{original.name}"],
            cwd=source,
        )
        instruction = task_instruction(original, solution_files)
        task = {
            "taskId": f"aider-{language}/{original.name}",
            "language": language,
            "name": original.name,
            "relativePath": relative.as_posix(),
            "solutionFiles": solution_files,
            "testFiles": test_files,
            "officialTree": tree,
            "instruction": instruction,
            "instructionSha256": sha256(instruction.encode()),
        }
        tasks.append(task)
        allowed.extend((relative / file).as_posix() for file in solution_files)

    python_total = sum(path.is_dir() for path in (source / "python" / "exercises" / "practice").iterdir())
    rust_total = sum(path.is_dir() for path in (source / "rust" / "exercises" / "practice").iterdir())
    complete_python = not excluded_python and python_count == python_total and rust_count == 0
    complete_rust = python_count == 0 and rust_count == rust_total
    complete_single_track = complete_python or complete_rust
    manifest = {
        "schemaVersion": 1,
        "status": "frozen_before_model_calls",
        "benchmark": (
            f"Aider-AI/polyglot-benchmark complete hidden-test {'Python' if complete_python else 'Rust'} track"
            if complete_single_track
            else "Aider-AI/polyglot-benchmark hidden-test Python/Rust subset"
        ),
        "officialRepository": "https://github.com/Aider-AI/polyglot-benchmark",
        "officialCommit": commit,
        "seed": seed,
        "selectionRule": (
            f"all {len(selected)} official {'Python' if complete_python else 'Rust'} exercises; no task selection"
            if complete_single_track
            else "per-language lowest_sha256(seed + NUL + language/exercise), excluding ceiling-pilot Python IDs"
        ),
        "pythonCount": python_count,
        "rustCount": rust_count,
        "excludedPython": sorted(excluded_python),
        "testsAbsentFromAgentWorkspace": True,
        "goldExamplesAbsentEverywhere": True,
        "tasks": tasks,
    }
    manifest_text = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    (agent_source / "benchmark_manifest.json").write_text(manifest_text, encoding="utf-8")
    (evaluator_source / "benchmark_manifest.json").write_text(manifest_text, encoding="utf-8")
    (agent_source / ".gitignore").write_text(
        "**/__pycache__/\n**/.pytest_cache/\n**/target/\n*.pyc\n",
        encoding="utf-8",
    )
    combined = "\n\n".join(
        f"## {item['taskId']}\nSolution files: {' '.join(item['solutionFiles'])}\n\n{item['instruction']}"
        for item in tasks
    )
    instruction = (
        f"Solve all {len(tasks)} independent official Aider benchmark exercises in the frozen order below. "
        "The official tests and gold implementations are intentionally unavailable. Work only in the listed "
        "solution files, infer edge cases from the official instructions, and do not search for exercise solutions. "
        "Do not edit benchmark_manifest.json, .docs files, build configuration, or repository metadata.\n\n"
        + combined
    )

    run(["git", "init", "--quiet"], cwd=agent_source)
    run(["git", "config", "user.name", APPROVED_NAME], cwd=agent_source)
    run(["git", "config", "user.email", APPROVED_EMAIL], cwd=agent_source)
    run(["git", "add", "."], cwd=agent_source)
    run([
        "git", "commit", "--quiet", "-m",
        "Freeze complete hidden-test Aider track" if complete_single_track else "Freeze hidden-test Aider Python Rust subset",
    ], cwd=agent_source)
    base_ref = run(["git", "rev-parse", "HEAD"], cwd=agent_source)
    evaluator = (Path(__file__).resolve().parent / "evaluate_aider_hidden20.py").resolve()
    private_root = (output / "private").resolve()
    task_payload = {
        "task_id": f"aider-hidden-python{python_count}-rust{rust_count}-v1",
        "instruction": instruction,
        "base_ref": base_ref,
        "public_test_command": (
            f"python {json.dumps(str(evaluator))} --workspace . --private-root {json.dumps(str(private_root))}"
        ),
        "allowed_path_globs": allowed,
        "forbidden_path_globs": [
            ".git/*",
            "benchmark_manifest.json",
            ".gitignore",
            "**/.docs/*",
            "**/*_test.py",
            "**/test_*.py",
            "**/tests/*",
            "**/Cargo.toml",
        ],
    }
    task_path = public / "task.json"
    task_path.write_text(json.dumps(task_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (output / "private" / "benchmark_manifest.json").write_text(manifest_text, encoding="utf-8")
    freeze = {
        "schemaVersion": 1,
        "status": "frozen_before_model_calls",
        "sourceCommit": commit,
        "baseRef": base_ref,
        "manifestSha256": sha256(manifest_text.encode()),
        "taskSha256": sha256(task_path.read_bytes()),
        "evaluatorSha256": sha256(evaluator.read_bytes()),
        "selectedTaskIds": [item["taskId"] for item in tasks],
    }
    freeze_bytes = (json.dumps(freeze, indent=2, ensure_ascii=False) + "\n").encode()
    (output / "freeze.json").write_bytes(freeze_bytes)
    return {**freeze, "freezeSha256": sha256(freeze_bytes)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--ceiling-pilot-freeze", type=Path)
    parser.add_argument("--seed", default=DEFAULT_SEED)
    parser.add_argument("--python-count", type=int, default=10)
    parser.add_argument("--rust-count", type=int, default=10)
    args = parser.parse_args()
    excluded: set[str] = set()
    if args.ceiling_pilot_freeze is not None:
        pilot = json.loads(args.ceiling_pilot_freeze.read_text(encoding="utf-8"))
        excluded = {
            item.split("/", 1)[1]
            for item in pilot["selectedTaskIds"]
            if item.startswith("aider-python/")
        }
    result = materialize(
        args.source,
        args.output,
        seed=args.seed,
        python_count=args.python_count,
        rust_count=args.rust_count,
        excluded_python=excluded,
    )
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
