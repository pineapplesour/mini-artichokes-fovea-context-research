#!/usr/bin/env python3
"""Plan or smoke-test installation of beta6 user systemd services."""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "ops" / "supervisor" / "beta6-services.json"
DEFAULT_USER_SYSTEMD_DIR = Path.home() / ".config" / "systemd" / "user"


class CommandResult:
    def __init__(self, command: list[str], returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.command = command
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


CommandRunner = Callable[[list[str]], CommandResult]


def build_report(
    *,
    dry_run: bool = True,
    install: bool = False,
    user_systemd_dir: str | Path | None = None,
    check_systemd: bool = False,
    runner: CommandRunner | None = None,
) -> dict[str, Any]:
    """Build an install smoke report, optionally copying units and running systemctl."""

    target_dir = Path(user_systemd_dir) if user_systemd_dir is not None else DEFAULT_USER_SYSTEMD_DIR
    runner = runner or _run_command
    contract_report = _load_contract_report()
    manifest = _read_json(MANIFEST_PATH)
    actions = _install_actions(manifest, target_dir)
    service_units = [item["service"] for item in actions]
    would_run = _systemctl_commands(service_units)
    systemd_report = _systemd_report(check_systemd=check_systemd, runner=runner)
    command_results: list[dict[str, Any]] = []
    copy_results: list[dict[str, Any]] = []

    plan_pass = contract_report.get("passes") is True and bool(actions) and all(action["sourceExists"] for action in actions)
    if install and not dry_run:
        target_dir.mkdir(parents=True, exist_ok=True)
        for action in actions:
            source = Path(action["source"])
            destination = Path(action["destination"])
            shutil.copy2(source, destination)
            copy_results.append({**action, "copied": destination.exists()})
        for command in would_run:
            command_results.append(_command_result_to_json(runner(command)))

    commands_pass = not command_results or all(item["returncode"] == 0 for item in command_results)
    copies_pass = not install or dry_run or (len(copy_results) == len(actions) and all(item.get("copied") for item in copy_results))
    systemd_pass = not check_systemd or systemd_report["available"]
    passes = plan_pass and copies_pass and commands_pass and systemd_pass
    return {
        "passes": passes,
        "dryRun": dry_run,
        "installRequested": install,
        "checkSystemd": check_systemd,
        "serviceCount": len(actions),
        "planPass": plan_pass,
        "targetDirectory": str(target_dir),
        "manifestPath": str(MANIFEST_PATH.relative_to(ROOT)),
        "contractPass": contract_report.get("passes") is True,
        "systemd": systemd_report,
        "installActions": actions,
        "copyResults": copy_results,
        "wouldRun": would_run,
        "commands": command_results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install", action="store_true", help="Copy units and run systemctl --user enable --now.")
    parser.add_argument("--dry-run", action="store_true", help="Only print the install plan. This is the default.")
    parser.add_argument("--check-systemd", action="store_true", help="Run non-mutating systemctl --user is-system-running.")
    parser.add_argument("--user-systemd-dir", default="", help="Override the user systemd unit directory.")
    parser.add_argument("--json", action="store_true", help="Print JSON report.")
    parser.add_argument("--output", default="", help="Write JSON report to this path.")
    args = parser.parse_args(argv)
    dry_run = True if args.dry_run or not args.install else False
    report = build_report(
        dry_run=dry_run,
        install=args.install,
        user_systemd_dir=args.user_systemd_dir or None,
        check_systemd=args.check_systemd,
    )
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        label = "PASS supervisor install smoke" if report["passes"] else "FAIL supervisor install smoke"
        print(label)
    return 0 if report["passes"] else 1


def _install_actions(manifest: dict[str, Any], target_dir: Path) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for item in manifest.get("services") or []:
        if not isinstance(item, dict):
            continue
        unit = str(item.get("unit") or "")
        source = ROOT / unit
        service_name = Path(unit).name
        actions.append(
            {
                "name": str(item.get("name") or ""),
                "service": service_name,
                "source": str(source),
                "destination": str(target_dir / service_name),
                "sourceExists": source.exists(),
            }
        )
    return actions


def _systemctl_commands(service_units: list[str]) -> list[list[str]]:
    return [
        ["systemctl", "--user", "daemon-reload"],
        ["systemctl", "--user", "enable", "--now", *service_units],
        ["systemctl", "--user", "status", *service_units],
    ]


def _systemd_report(*, check_systemd: bool, runner: CommandRunner) -> dict[str, Any]:
    if not check_systemd:
        return {"checked": False, "available": None, "command": [], "returncode": None, "stdout": "", "stderr": ""}
    result = runner(["systemctl", "--user", "is-system-running"])
    available = result.returncode == 0 or result.stdout.strip() in {"running", "degraded"}
    data = _command_result_to_json(result)
    return {"checked": True, "available": available, **data}


def _run_command(command: list[str]) -> CommandResult:
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    return CommandResult(
        command=command,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _command_result_to_json(result: CommandResult) -> dict[str, Any]:
    return {
        "command": result.command,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def _load_contract_report() -> dict[str, Any]:
    path = ROOT / "tools" / "verify_supervisor_contract.py"
    spec = importlib.util.spec_from_file_location("verify_supervisor_contract_for_smoke", path)
    module = importlib.util.module_from_spec(spec)
    if spec is None or spec.loader is None:
        return {"passes": False}
    spec.loader.exec_module(module)
    return module.build_report()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


if __name__ == "__main__":
    raise SystemExit(main())
