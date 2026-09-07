#!/usr/bin/env python3
"""Verify that native Android/iOS shells are build-smoked, not only scaffolded."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
ANDROID_DIR = ROOT / "native" / "android"
ANDROID_WRAPPER = ANDROID_DIR / "gradlew"
ANDROID_DEBUG_APK = ANDROID_DIR / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk"
IOS_DIR = ROOT / "native" / "ios"


class CommandResult:
    def __init__(
        self,
        command: list[str],
        cwd: str,
        returncode: int,
        stdout: str = "",
        stderr: str = "",
        durationMs: int = 0,
    ) -> None:
        self.command = command
        self.cwd = cwd
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.durationMs = durationMs


CommandExists = Callable[[str], str]
CommandRunner = Callable[[list[str], Path, int], CommandResult]


def build_report(
    *,
    attempt_android: bool = False,
    attempt_ios: bool = False,
    command_exists: CommandExists | None = None,
    runner: CommandRunner | None = None,
    env: dict[str, str] | None = None,
    platform_system: str | None = None,
    timeout_seconds: int = 120,
    android_apk_path: str | Path | None = None,
) -> dict[str, Any]:
    command_exists = command_exists or _command_exists
    runner = runner or _run_command
    env = dict(os.environ if env is None else env)
    platform_system = platform_system or platform.system()

    parity_report = _native_parity_report()
    android_project_pass = bool(parity_report.get("nativeSource", {}).get("androidProjectPass"))
    ios_project_pass = bool(parity_report.get("nativeSource", {}).get("iosProjectPass"))
    android_build = _android_build_report(
        checked=attempt_android,
        project_pass=android_project_pass,
        command_exists=command_exists,
        runner=runner,
        env=env,
        timeout_seconds=timeout_seconds,
        apk_path=Path(android_apk_path) if android_apk_path is not None else ANDROID_DEBUG_APK,
    )
    ios_build = _ios_build_report(
        checked=attempt_ios,
        project_pass=ios_project_pass,
        command_exists=command_exists,
        runner=runner,
        platform_system=platform_system,
        timeout_seconds=timeout_seconds,
    )
    passes = bool(parity_report.get("passes")) and android_build["passes"] and ios_build["passes"]
    return {
        "passes": passes,
        "nativeParity": {
            "passes": bool(parity_report.get("passes")),
            "androidProjectPass": android_project_pass,
            "iosProjectPass": ios_project_pass,
            "assetsSynced": bool(parity_report.get("nativeSource", {}).get("assetsSynced")),
        },
        "android": {
            "projectPass": android_project_pass,
            "build": android_build,
        },
        "ios": {
            "projectPass": ios_project_pass,
            "build": ios_build,
        },
    }


def _android_build_report(
    *,
    checked: bool,
    project_pass: bool,
    command_exists: CommandExists,
    runner: CommandRunner,
    env: dict[str, str],
    timeout_seconds: int,
    apk_path: Path,
) -> dict[str, Any]:
    gradle_path = command_exists("gradle")
    java_path = command_exists("java")
    has_wrapper = ANDROID_WRAPPER.exists()
    has_sdk = bool(env.get("ANDROID_HOME") or env.get("ANDROID_SDK_ROOT"))
    missing: list[str] = []
    if not project_pass:
        missing.append("android project scaffold")
    if not java_path:
        missing.append("java")
    if not has_wrapper and not gradle_path:
        missing.append("gradle")
    if not has_sdk:
        missing.append("ANDROID_HOME or ANDROID_SDK_ROOT")
    command = ["./gradlew", ":app:assembleDebug", "--no-daemon"] if has_wrapper else ["gradle", ":app:assembleDebug", "--no-daemon"]
    can_attempt = project_pass and not missing
    result: dict[str, Any] | None = None
    if checked and can_attempt:
        result = _command_result_to_json(runner(command, ANDROID_DIR, timeout_seconds))
    apk_report = _android_apk_report(apk_path) if checked and can_attempt and result and result["returncode"] == 0 else _android_apk_report(apk_path, checked=False)
    return {
        "checked": checked,
        "canAttempt": can_attempt,
        "passes": bool(checked and can_attempt and result and result["returncode"] == 0 and apk_report["passes"]),
        "command": command,
        "cwd": str(ANDROID_DIR.relative_to(ROOT)),
        "missing": missing,
        "tool": str(ANDROID_WRAPPER.relative_to(ROOT)) if has_wrapper else gradle_path,
        "javaTool": java_path,
        "androidSdkConfigured": has_sdk,
        "result": result,
        "apk": apk_report,
    }


def _android_apk_report(path: Path, *, checked: bool = True) -> dict[str, Any]:
    relative_path = str(path.relative_to(ROOT)) if path.is_absolute() and path.is_relative_to(ROOT) else str(path)
    exists = path.exists()
    size = path.stat().st_size if exists else 0
    manifest_asset_synced = False
    manifest_asset_exists = False
    error = ""
    if checked and exists:
        try:
            with zipfile.ZipFile(path) as zf:
                names = set(zf.namelist())
                manifest_asset_exists = "assets/app-shell-manifest.json" in names
                if manifest_asset_exists:
                    apk_manifest = json.loads(zf.read("assets/app-shell-manifest.json").decode("utf-8"))
                    web_manifest = json.loads((ROOT / "web" / "app-shell-manifest.json").read_text(encoding="utf-8"))
                    manifest_asset_synced = _json_equal(apk_manifest, web_manifest)
        except (OSError, zipfile.BadZipFile, json.JSONDecodeError, UnicodeDecodeError) as exc:
            error = str(exc)
    return {
        "checked": checked,
        "path": relative_path,
        "exists": exists,
        "sizeBytes": size,
        "manifestAssetExists": manifest_asset_exists,
        "manifestAssetSynced": manifest_asset_synced,
        "passes": bool(checked and exists and size > 0 and manifest_asset_exists and manifest_asset_synced and not error),
        "error": error,
    }


def _json_equal(lhs: Any, rhs: Any) -> bool:
    return json.dumps(lhs, ensure_ascii=False, sort_keys=True, separators=(",", ":")) == json.dumps(
        rhs,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _ios_build_report(
    *,
    checked: bool,
    project_pass: bool,
    command_exists: CommandExists,
    runner: CommandRunner,
    platform_system: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    xcodebuild_path = command_exists("xcodebuild")
    missing: list[str] = []
    if not project_pass:
        missing.append("ios project scaffold")
    if not xcodebuild_path:
        missing.append("xcodebuild")
    if platform_system != "Darwin":
        missing.append("macOS/Darwin")
    command = [
        "xcodebuild",
        "-scheme",
        "BunjumBeta6Native",
        "-sdk",
        "iphonesimulator",
        "-destination",
        "generic/platform=iOS Simulator",
        "build",
    ]
    can_attempt = project_pass and not missing
    result: dict[str, Any] | None = None
    if checked and can_attempt:
        result = _command_result_to_json(runner(command, IOS_DIR, timeout_seconds))
    return {
        "checked": checked,
        "canAttempt": can_attempt,
        "passes": bool(checked and can_attempt and result and result["returncode"] == 0),
        "command": command,
        "cwd": str(IOS_DIR.relative_to(ROOT)),
        "missing": missing,
        "tool": xcodebuild_path,
        "platform": platform_system,
        "result": result,
    }


def _native_parity_report() -> dict[str, Any]:
    path = ROOT / "tools" / "verify_app_parity.py"
    spec = importlib.util.spec_from_file_location("verify_app_parity_for_native_build", path)
    module = importlib.util.module_from_spec(spec)
    if spec is None or spec.loader is None:
        return {"passes": False, "nativeSource": {}}
    spec.loader.exec_module(module)
    return module.build_report()


def _command_exists(name: str) -> str:
    return shutil.which(name) or ""


def _run_command(command: list[str], cwd: Path, timeout_seconds: int) -> CommandResult:
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        return CommandResult(
            command=command,
            cwd=str(cwd),
            returncode=completed.returncode,
            stdout=completed.stdout[-8000:],
            stderr=completed.stderr[-8000:],
            durationMs=int((time.monotonic() - started) * 1000),
        )
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            command=command,
            cwd=str(cwd),
            returncode=124,
            stdout=(exc.stdout or "")[-8000:] if isinstance(exc.stdout, str) else "",
            stderr=((exc.stderr or "")[-8000:] if isinstance(exc.stderr, str) else "") + "\ntimeout",
            durationMs=int((time.monotonic() - started) * 1000),
        )


def _command_result_to_json(result: CommandResult) -> dict[str, Any]:
    return {
        "command": result.command,
        "cwd": result.cwd,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "durationMs": result.durationMs,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt-android", action="store_true", help="Run Android assembleDebug if the toolchain is available.")
    parser.add_argument("--attempt-ios", action="store_true", help="Run iOS xcodebuild if the toolchain is available.")
    parser.add_argument("--attempt-all", action="store_true", help="Run both Android and iOS build smoke checks.")
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--json", action="store_true", help="Print JSON report.")
    parser.add_argument("--output", default="", help="Write JSON report to this path.")
    args = parser.parse_args(argv)
    report = build_report(
        attempt_android=args.attempt_all or args.attempt_android,
        attempt_ios=args.attempt_all or args.attempt_ios,
        timeout_seconds=args.timeout_seconds,
    )
    encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(encoded + "\n", encoding="utf-8")
    if args.json:
        print(encoded)
    else:
        print(("PASS" if report["passes"] else "FAIL") + " native build smoke")
        print(f"android: checked={report['android']['build']['checked']} pass={report['android']['build']['passes']}")
        print(f"ios: checked={report['ios']['build']['checked']} pass={report['ios']['build']['passes']}")
    return 0 if report["passes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
