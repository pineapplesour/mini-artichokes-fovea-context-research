#!/usr/bin/env python3
"""Freeze a leakage-safe 20-task subset of Aider's official Python benchmark.

The source exercises and tests are copied verbatim from Aider-AI/polyglot-
benchmark.  Exercism's `.meta/example.py` gold implementations are removed
before an agent can see the workspace.  Selection is deterministic from the
declared seed and Git tree IDs, not from model results.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path


DEFAULT_SEED = "mini-artichokes-aider-python20-confirmation-v1-20260902"
APPROVED_NAME = "pineapplesour"
APPROVED_EMAIL = "59020461+pineapplesour@users.noreply.github.com"


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


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def select_tasks(source: Path, *, seed: str, count: int) -> list[Path]:
    practice = source / "python" / "exercises" / "practice"
    candidates = sorted(path for path in practice.iterdir() if path.is_dir())
    if len(candidates) < count:
        raise ValueError(f"requested {count} tasks from only {len(candidates)} candidates")
    ranked = sorted(
        candidates,
        key=lambda path: hashlib.sha256(f"{seed}\0{path.name}".encode()).hexdigest(),
    )
    return ranked[:count]


def task_instruction(task_dir: Path, solution_files: list[str]) -> str:
    parts: list[str] = []
    for name in ("introduction.md", "instructions.md", "instructions.append.md"):
        path = task_dir / ".docs" / name
        if path.is_file():
            parts.append(path.read_text(encoding="utf-8").strip())
    files = " ".join(solution_files)
    parts.append(
        "Use the instructions above to modify only these supplied solution files: "
        f"{files}. Do not change existing public function or class names. Use only "
        "the Python standard library. The tests are authoritative and must not be edited."
    )
    return "\n\n".join(parts).strip()


RUNNER = r'''#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


root = Path(__file__).resolve().parent
manifest = json.loads((root / "benchmark_manifest.json").read_text(encoding="utf-8"))
all_passed = True
for item in manifest["tasks"]:
    task_dir = root / item["relativePath"]
    command = [sys.executable, "-m", "pytest", "-q", "--tb=short", "-p", "no:cacheprovider", *item["testFiles"]]
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        completed = subprocess.run(
            command,
            cwd=task_dir,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=180,
            check=False,
        )
        passed = completed.returncode == 0
        output = completed.stdout[-6000:]
        exit_code = completed.returncode
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        passed = False
        raw = exc.stdout or ""
        output = raw.decode(errors="replace") if isinstance(raw, bytes) else raw
        output = output[-6000:]
        exit_code = None
        timed_out = True
    all_passed = all_passed and passed
    print(json.dumps({
        "taskId": item["taskId"],
        "passed": passed,
        "exitCode": exit_code,
        "timedOut": timed_out,
        "outputTail": output,
    }, ensure_ascii=False))
print(json.dumps({"summary": True, "allPassed": all_passed, "taskCount": len(manifest["tasks"])}, ensure_ascii=False))
raise SystemExit(0 if all_passed else 1)
'''


def materialize(source: Path, output: Path, *, seed: str, count: int) -> dict[str, object]:
    if output.exists():
        raise FileExistsError(output)
    source = source.resolve()
    commit = run(["git", "rev-parse", "HEAD"], cwd=source)
    if run(["git", "status", "--porcelain"], cwd=source):
        raise RuntimeError("official source repository is dirty")
    selected = select_tasks(source, seed=seed, count=count)

    source_out = output / "source"
    public_out = output / "public"
    source_out.mkdir(parents=True)
    public_out.mkdir()
    tasks_payload: list[dict[str, object]] = []
    allowed: list[str] = []

    for original in selected:
        config = json.loads((original / ".meta" / "config.json").read_text(encoding="utf-8"))
        solution_files = list(config["files"]["solution"])
        test_files = list(config["files"]["test"])
        relative = Path("tasks") / "python" / original.name
        destination = source_out / relative
        shutil.copytree(original, destination)
        shutil.rmtree(destination / ".meta")
        tree = run(
            ["git", "rev-parse", f"HEAD:python/exercises/practice/{original.name}"],
            cwd=source,
        )
        instruction = task_instruction(original, solution_files)
        tasks_payload.append(
            {
                "taskId": f"aider-python/{original.name}",
                "name": original.name,
                "relativePath": relative.as_posix(),
                "solutionFiles": solution_files,
                "testFiles": test_files,
                "officialTree": tree,
                "instruction": instruction,
                "instructionSha256": sha256_bytes(instruction.encode()),
            }
        )
        allowed.extend((relative / file).as_posix() for file in solution_files)

    manifest = {
        "schemaVersion": 1,
        "status": "frozen_before_model_calls",
        "benchmark": "Aider-AI/polyglot-benchmark Python track",
        "officialRepository": "https://github.com/Aider-AI/polyglot-benchmark",
        "officialCommit": commit,
        "seed": seed,
        "selectionRule": "lowest_sha256(seed + NUL + exercise_name)",
        "candidateCount": len(list((source / "python" / "exercises" / "practice").iterdir())),
        "selectedCount": count,
        "goldExamplesRemoved": True,
        "tasks": tasks_payload,
    }
    manifest_text = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    (source_out / "benchmark_manifest.json").write_text(manifest_text, encoding="utf-8")
    (source_out / "run_public_tests.py").write_text(RUNNER, encoding="utf-8")
    (source_out / ".gitignore").write_text(
        "**/__pycache__/\n**/.pytest_cache/\n*.pyc\n",
        encoding="utf-8",
    )

    combined = "\n\n".join(
        f"## {item['taskId']}\nSolution files: {' '.join(item['solutionFiles'])}\n\n{item['instruction']}"
        for item in tasks_payload
    )
    instruction = (
        "Solve all 20 independent official Aider Python benchmark exercises in the frozen order below. "
        "Work only in the listed solution files. You may inspect and run the official public tests with "
        "`python run_public_tests.py`. Do not edit tests, benchmark_manifest.json, run_public_tests.py, "
        ".docs files, or repository metadata. A task counts as solved only when its untouched official tests pass.\n\n"
        + combined
    )
    (public_out / "task.json").write_text(
        json.dumps(
            {
                "task_id": "aider-python20-confirmation-v1",
                "instruction": instruction,
                "base_ref": "TO_BE_FILLED",
                "public_test_command": "python run_public_tests.py",
                "allowed_path_globs": allowed,
                "forbidden_path_globs": [
                    ".git/*",
                    "benchmark_manifest.json",
                    "run_public_tests.py",
                    ".gitignore",
                    "**/.docs/*",
                    "**/*_test.py",
                    "**/test_*.py",
                ],
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    run(["git", "init", "--quiet"], cwd=source_out)
    run(["git", "config", "user.name", APPROVED_NAME], cwd=source_out)
    run(["git", "config", "user.email", APPROVED_EMAIL], cwd=source_out)
    run(["git", "add", "."], cwd=source_out)
    run(["git", "commit", "--quiet", "-m", "Freeze official Aider Python 20-task subset"], cwd=source_out)
    base_ref = run(["git", "rev-parse", "HEAD"], cwd=source_out)
    task_path = public_out / "task.json"
    task = json.loads(task_path.read_text(encoding="utf-8"))
    task["base_ref"] = base_ref
    task_path.write_text(json.dumps(task, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    freeze = {
        "schemaVersion": 1,
        "status": "frozen_before_model_calls",
        "sourceCommit": commit,
        "baseRef": base_ref,
        "manifestSha256": sha256_bytes(manifest_text.encode()),
        "taskSha256": sha256_bytes(task_path.read_bytes()),
        "selectedTaskIds": [item["taskId"] for item in tasks_payload],
    }
    freeze_bytes = (json.dumps(freeze, indent=2, ensure_ascii=False) + "\n").encode()
    (output / "freeze.json").write_bytes(freeze_bytes)
    return {**freeze, "freezeSha256": sha256_bytes(freeze_bytes)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--seed", default=DEFAULT_SEED)
    parser.add_argument("--count", type=int, default=20)
    args = parser.parse_args()
    print(json.dumps(materialize(args.source, args.output, seed=args.seed, count=args.count)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
