#!/usr/bin/env python3
"""Apply a patch to private official Java tests and emit task-level results."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


def activate_all_official_tests(task_dir: Path) -> None:
    """Remove Exercism's progressive-unlock markers in the temporary copy."""
    for path in (task_dir / "src" / "test").rglob("*.java"):
        text = path.read_text(encoding="utf-8")
        text = re.sub(r"^\s*import org\.junit\.jupiter\.api\.Disabled;\s*$", "", text, flags=re.MULTILINE)
        text = re.sub(r'^\s*@Disabled(?:\("[^"]*"\))?\s*$', "", text, flags=re.MULTILINE)
        path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--private-root", required=True, type=Path)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    private_root = args.private_root.resolve()
    manifest = json.loads((private_root / "benchmark_manifest.json").read_text(encoding="utf-8"))
    diff = subprocess.run(
        ["git", "diff", "--binary", "HEAD", "--"],
        cwd=workspace,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout
    with tempfile.TemporaryDirectory(prefix="aider-hidden-java20-") as temporary:
        evaluation = Path(temporary) / "evaluation"
        shutil.copytree(private_root / "evaluator_source", evaluation)
        applied = subprocess.run(
            ["git", "apply", "--allow-empty", "--binary", "-"],
            cwd=evaluation,
            input=diff,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if applied.returncode != 0:
            print(json.dumps({"summary": True, "patchApplied": False, "error": applied.stderr[-4000:]}))
            return 2
        all_passed = True
        passed_count = 0
        for item in manifest["tasks"]:
            task_dir = evaluation / item["relativePath"]
            activate_all_official_tests(task_dir)
            env = os.environ.copy()
            env["GRADLE_OPTS"] = "-Dorg.gradle.daemon=false -Dorg.gradle.workers.max=1"
            try:
                result = subprocess.run(
                    ["./gradlew", "test", "--no-daemon", "--console=plain", "--max-workers=1"],
                    cwd=task_dir,
                    env=env,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    timeout=240,
                    check=False,
                )
                passed = result.returncode == 0
                code = result.returncode
                timed_out = False
                tail = result.stdout[-8000:]
            except subprocess.TimeoutExpired as exc:
                passed = False
                code = None
                timed_out = True
                raw = exc.stdout or ""
                tail = (raw.decode(errors="replace") if isinstance(raw, bytes) else raw)[-8000:]
            all_passed = all_passed and passed
            passed_count += int(passed)
            print(json.dumps({
                "taskId": item["taskId"],
                "language": "java",
                "passed": passed,
                "exitCode": code,
                "timedOut": timed_out,
                "outputTail": tail,
            }, ensure_ascii=False))
        print(json.dumps({
            "summary": True,
            "patchApplied": True,
            "passedCount": passed_count,
            "taskCount": len(manifest["tasks"]),
            "allPassed": all_passed,
        }))
        return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
