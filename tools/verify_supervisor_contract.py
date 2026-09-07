#!/usr/bin/env python3
"""Verify beta6 user-level supervisor service contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "ops" / "supervisor" / "beta6-services.json"


def build_report() -> dict[str, Any]:
    manifest_exists = MANIFEST_PATH.exists()
    manifest = _read_json(MANIFEST_PATH) if manifest_exists else {}
    working_directory = str(manifest.get("workingDirectory") or "")
    environment_file = str(manifest.get("environmentFile") or "")
    services = [
        _service_report(item, working_directory=working_directory, environment_file=environment_file)
        for item in manifest.get("services") or []
        if isinstance(item, dict)
    ]
    environment_report = _environment_report(Path(environment_file))
    names = {item.get("name") for item in manifest.get("services") or [] if isinstance(item, dict)}
    required_names = {"beta6-islam", "beta6-tcm", "beta6-simli", "beta6-queue-worker"}
    manifest_pass = (
        manifest_exists
        and manifest.get("schemaVersion") == 1
        and working_directory == str(ROOT)
        and environment_file == str(ROOT / "ops" / "supervisor" / "beta6.env")
        and names == required_names
    )
    passes = manifest_pass and environment_report["passes"] and len(services) == 4 and all(item["passes"] for item in services)
    return {
        "passes": passes,
        "manifestPass": manifest_pass,
        "manifestPath": str(MANIFEST_PATH.relative_to(ROOT)),
        "serviceCount": len(services),
        "environmentPass": environment_report["passes"],
        "environment": environment_report,
        "services": services,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print JSON report.")
    parser.add_argument("--output", default="", help="Write JSON report to this path.")
    args = parser.parse_args(argv)
    report = build_report()
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("PASS supervisor contract" if report["passes"] else "FAIL supervisor contract")
    return 0 if report["passes"] else 1


def _service_report(item: dict[str, Any], *, working_directory: str, environment_file: str) -> dict[str, Any]:
    unit_path = ROOT / str(item.get("unit") or "")
    unit = _parse_unit(unit_path)
    exec_start = str(item.get("execStart") or "")
    restart = str(item.get("restart") or "")
    port = int(item.get("port") or 0)
    service = unit.get("Service", {})
    unit_exists = unit_path.exists()
    exec_matches = service.get("ExecStart") == exec_start
    restart_matches = service.get("Restart") == restart
    working_directory_matches = service.get("WorkingDirectory") == working_directory
    environment_matches = service.get("EnvironmentFile") == environment_file
    restart_sec_matches = service.get("RestartSec") == "3"
    port_matches = True if port == 0 else f"--port {port}" in exec_start
    command_shape_pass = _command_shape_pass(str(item.get("name") or ""), exec_start)
    passes = (
        unit_exists
        and exec_matches
        and restart_matches
        and working_directory_matches
        and environment_matches
        and restart_sec_matches
        and port_matches
        and command_shape_pass
    )
    return {
        "name": item.get("name", ""),
        "unit": str(unit_path.relative_to(ROOT)) if unit_path.is_absolute() else str(unit_path),
        "passes": passes,
        "unitExists": unit_exists,
        "execMatches": exec_matches,
        "restartMatches": restart_matches,
        "workingDirectoryMatches": working_directory_matches,
        "environmentMatches": environment_matches,
        "restartSecMatches": restart_sec_matches,
        "portMatches": port_matches,
        "commandShapePass": command_shape_pass,
    }


def _environment_report(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    required = {
        "RELIGION_LLM_PROVIDER=lawkey",
        "RELIGION_ANSWER_MODEL=gemma-4-26b-a4b-it",
        f"RELIGION_RUNS_ROOT={ROOT / 'runs'}",
        "RELIGION_JOB_WORKERS=4",
        "RELIGION_JOB_MAX_PENDING=10000",
        "RELIGION_LOCAL_JOB_EXECUTION_ENABLED=0",
        "RELIGION_QUEUE_WORKER_BATCH_LIMIT=8",
        "RELIGION_QUEUE_WORKER_POLL_SECONDS=1",
    }
    missing = sorted(item for item in required if item not in text)
    return {"path": str(path), "exists": path.exists(), "passes": path.exists() and not missing, "missing": missing}


def _parse_unit(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    sections: dict[str, dict[str, str]] = {}
    current = ""
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1]
            sections.setdefault(current, {})
            continue
        if current and "=" in line:
            key, value = line.split("=", 1)
            sections.setdefault(current, {})[key] = value
    return sections


def _command_shape_pass(name: str, exec_start: str) -> bool:
    if name == "beta6-queue-worker":
        return (
            "tools/run_beta6_queue_worker.py" in exec_start
            and "--product islam" in exec_start
            and "--product tcm" in exec_start
            and "--product simli" in exec_start
        )
    product = name.removeprefix("beta6-")
    return f"apps.{product}.server:app" in exec_start and "uvicorn" in exec_start


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


if __name__ == "__main__":
    raise SystemExit(main())
