#!/usr/bin/env python3
"""Freeze either the complete Rust track or its unused replication remainder."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from tools.prepare_aider_hidden20 import remove_tests
from tools.prepare_aider_python20 import APPROVED_EMAIL, APPROVED_NAME


def run(argv: list[str], *, cwd: Path) -> str:
    completed = subprocess.run(argv, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"command failed ({completed.returncode}): {argv}\n{completed.stderr}")
    return completed.stdout.strip()


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def rust_task_instruction(task_dir: Path, solution_files: list[str]) -> str:
    """Render the untouched official exercise prose plus Rust-only constraints."""
    parts: list[str] = []
    for name in ("introduction.md", "instructions.md", "instructions.append.md"):
        path = task_dir / ".docs" / name
        if path.is_file():
            parts.append(path.read_text(encoding="utf-8").strip())
    parts.append(
        "Use the instructions above to modify only these supplied solution files: "
        f"{' '.join(solution_files)}. Do not change existing public function, type, trait, or macro names. "
        "Use only the Rust standard library and the dependencies already declared by the supplied exercise. "
        "The hidden official tests are authoritative and must not be edited."
    )
    return "\n\n".join(parts).strip()


def materialize(source: Path, output: Path, prior_freeze: Path | None = None) -> dict[str, object]:
    if output.exists():
        raise FileExistsError(output)
    source = source.resolve()
    commit = run(["git", "rev-parse", "HEAD"], cwd=source)
    if run(["git", "status", "--porcelain"], cwd=source):
        raise RuntimeError("official source repository is dirty")
    used = set()
    if prior_freeze is not None:
        used = {
            item.split("/", 1)[1]
            for item in json.loads(prior_freeze.read_text(encoding="utf-8"))["selectedTaskIds"]
            if item.startswith("aider-rust/")
        }
    rust_root = source / "rust" / "exercises" / "practice"
    selected = sorted(path for path in rust_root.iterdir() if path.is_dir() and path.name not in used)
    expected = 20 if prior_freeze is not None else 30
    if len(selected) != expected:
        raise ValueError(f"expected exactly {expected} Rust tasks, found {len(selected)}")

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
        relative = Path("tasks") / "rust" / original.name
        agent_task = agent_source / relative
        evaluator_task = evaluator_source / relative
        shutil.copytree(original, agent_task)
        shutil.copytree(original, evaluator_task)
        shutil.rmtree(agent_task / ".meta")
        shutil.rmtree(evaluator_task / ".meta")
        remove_tests(agent_task, test_files)
        # A few official Rust exercises ship auxiliary tests that are not
        # enumerated in .meta/config.json.  Hide the complete conventional
        # tests tree from the agent while retaining it in the private copy.
        if (agent_task / "tests").is_dir():
            shutil.rmtree(agent_task / "tests")
        instruction = rust_task_instruction(original, solution_files)
        item = {
            "taskId": f"aider-rust/{original.name}",
            "language": "rust",
            "name": original.name,
            "relativePath": relative.as_posix(),
            "solutionFiles": solution_files,
            "testFiles": test_files,
            "officialTree": run(["git", "rev-parse", f"HEAD:rust/exercises/practice/{original.name}"], cwd=source),
            "instruction": instruction,
            "instructionSha256": digest(instruction.encode()),
        }
        tasks.append(item)
        allowed.extend((relative / file).as_posix() for file in solution_files)

    complete_track = prior_freeze is None
    manifest = {
        "schemaVersion": 1,
        "status": "frozen_before_model_calls",
        "benchmark": (
            "Aider-AI/polyglot-benchmark complete hidden-test Rust track"
            if complete_track
            else "Aider-AI/polyglot-benchmark hidden-test Rust remainder"
        ),
        "officialRepository": "https://github.com/Aider-AI/polyglot-benchmark",
        "officialCommit": commit,
        "selectionRule": (
            f"all {len(selected)} official Rust exercises; no task selection"
            if complete_track
            else "all 20 Rust exercises not used in hidden-test confirmation batch 1, lexicographic order"
        ),
        "excludedPriorRust": sorted(used),
        "testsAbsentFromAgentWorkspace": True,
        "goldExamplesAbsentEverywhere": True,
        "tasks": tasks,
    }
    manifest_text = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    (agent_source / "benchmark_manifest.json").write_text(manifest_text, encoding="utf-8")
    (evaluator_source / "benchmark_manifest.json").write_text(manifest_text, encoding="utf-8")
    (output / "private" / "benchmark_manifest.json").write_text(manifest_text, encoding="utf-8")
    (agent_source / ".gitignore").write_text("**/target/\n", encoding="utf-8")
    combined = "\n\n".join(
        f"## {item['taskId']}\nSolution files: {' '.join(item['solutionFiles'])}\n\n{item['instruction']}"
        for item in tasks
    )
    instruction = (
        f"Solve all {len(tasks)} independent official Aider Rust benchmark exercises in the frozen order below. "
        "The official tests and gold implementations are intentionally unavailable. Work only in listed solution "
        "files, infer edge cases from the official instructions, and do not search for exercise solutions. Do not "
        "edit benchmark_manifest.json, .docs files, unlisted build files, or repository metadata.\n\n" + combined
    )
    run(["git", "init", "--quiet"], cwd=agent_source)
    run(["git", "config", "user.name", APPROVED_NAME], cwd=agent_source)
    run(["git", "config", "user.email", APPROVED_EMAIL], cwd=agent_source)
    run(["git", "add", "."], cwd=agent_source)
    run([
        "git", "commit", "--quiet", "-m",
        "Freeze complete hidden-test Aider Rust track" if complete_track else "Freeze hidden-test Aider Rust remainder",
    ], cwd=agent_source)
    base_ref = run(["git", "rev-parse", "HEAD"], cwd=agent_source)
    evaluator = (Path(__file__).resolve().parent / "evaluate_aider_hidden20.py").resolve()
    private_root = (output / "private").resolve()
    task_payload = {
        "task_id": f"aider-hidden-rust{len(tasks)}-v1",
        "instruction": instruction,
        "base_ref": base_ref,
        "public_test_command": f"python {json.dumps(str(evaluator))} --workspace . --private-root {json.dumps(str(private_root))}",
        "allowed_path_globs": allowed,
        "forbidden_path_globs": [
            ".git/*", "benchmark_manifest.json", ".gitignore", "**/.docs/*", "**/tests/*"
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
    parser.add_argument("--prior-freeze", type=Path)
    args = parser.parse_args()
    print(json.dumps(materialize(args.source, args.output, args.prior_freeze)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
