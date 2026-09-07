#!/usr/bin/env python3
"""Replay a frozen auxiliary Java probe inside the existing agent sandbox."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


def run(argv: list[str], cwd: Path, seconds: int) -> dict:
    try:
        result = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=seconds)
        return {"exitCode": result.returncode, "stdout": result.stdout[-6000:],
                "stderr": result.stderr[-6000:], "timedOut": False}
    except subprocess.TimeoutExpired as exc:
        return {"exitCode": None, "stdout": str(exc.stdout or "")[-6000:],
                "stderr": str(exc.stderr or "")[-6000:], "timedOut": True}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-root", required=True, type=Path)
    parser.add_argument("--task-id", required=True)
    args = parser.parse_args()
    packet = Path(__file__).resolve().parent
    probes = json.loads((packet / "probes.json").read_text())
    manifest = json.loads((packet / "benchmark_manifest.json").read_text())
    probe = next(p for p in probes if p["taskId"] == args.task_id)
    task = next(t for t in manifest["tasks"] if t["taskId"] == args.task_id)
    result = {"taskId": args.task_id, "candidateRoot": str(args.candidate_root.resolve()),
              "basis": probe["basis"]}
    if probe["status"] != "executable":
        print(json.dumps({**result, "status": "unavailable", "reason": probe["reason"]}))
        return 0
    source = args.candidate_root.resolve() / task["relativePath"] / "src/main/java"
    with tempfile.TemporaryDirectory(prefix="mini-java-probe-") as scratch:
        temporary = Path(scratch)
        java_files = sorted(source.rglob("*.java"))
        if not java_files:
            raise ValueError("candidate source not found")
        for original in java_files:
            destination = temporary / original.relative_to(source)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original, destination)
        (temporary / "Probe.java").write_text(probe["java"])
        command = ["javac", "-J-Xmx128m", "-d", str(temporary / "classes")]
        command += [str(p) for p in sorted(temporary.rglob("*.java"))]
        compiled = run(command, temporary, 20)
        result["compile"] = compiled
        if compiled["exitCode"] != 0:
            result["status"] = "compile_unavailable"
        else:
            observed = run(["java", "-Xmx96m", "-ea", "-cp", str(temporary / "classes"), "Probe"], temporary, 5)
            result["execution"] = observed
            result["status"] = "executed_pass" if observed["exitCode"] == 0 else "executed_failure"
        print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
