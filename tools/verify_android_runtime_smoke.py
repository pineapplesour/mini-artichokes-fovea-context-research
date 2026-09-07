#!/usr/bin/env python3
"""Verify that the Android native shell installs, launches, resumes, and screenshots."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

from PIL import Image, UnidentifiedImageError


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_APK = ROOT / "native" / "android" / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk"
DEFAULT_SCREENSHOT = ROOT / "runs" / "android_runtime_smoke_current.png"
DEFAULT_PACKAGE = "ai.bunjum.beta6"
DEFAULT_ACTIVITY = "ai.bunjum.beta6/ai.bunjum.beta6.NativeShellActivity"
EXTRA_PRODUCT = "ai.bunjum.beta6.PRODUCT"
EXTRA_CHAT = "ai.bunjum.beta6.CHAT"
EXTRA_BASE_ORIGIN = "ai.bunjum.beta6.BASE_ORIGIN"


class CommandResult:
    def __init__(
        self,
        command: list[str],
        cwd: str,
        returncode: int,
        stdout: str = "",
        stderr: str = "",
        durationMs: int = 0,
        stdout_bytes: bytes | None = None,
    ) -> None:
        self.command = command
        self.cwd = cwd
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.durationMs = durationMs
        self.stdout_bytes = stdout_bytes


CommandExists = Callable[[str], str]
CommandRunner = Callable[[list[str], Path, int], CommandResult]
EmulatorStarter = Callable[[list[str], Path], CommandResult]


def build_report(
    *,
    apk_path: str | Path = DEFAULT_APK,
    avd_name: str = "bunjum_beta6_api35",
    base_origin: str = "http://127.0.0.1:8061",
    product: str = "islam",
    screenshot_path: str | Path = DEFAULT_SCREENSHOT,
    command_exists: CommandExists | None = None,
    runner: CommandRunner | None = None,
    emulator_starter: EmulatorStarter | None = None,
    start_emulator: bool = False,
    stop_emulator: bool = False,
    timeout_seconds: int = 120,
    package_name: str = DEFAULT_PACKAGE,
    activity_name: str = DEFAULT_ACTIVITY,
) -> dict[str, Any]:
    command_exists = command_exists or _command_exists
    runner = runner or _run_command
    emulator_starter = emulator_starter or _start_detached_command
    apk = Path(apk_path)
    screenshot = Path(screenshot_path)
    adb = command_exists("adb")
    emulator = command_exists("emulator")
    apk_exists = apk.exists()
    apk_size = apk.stat().st_size if apk_exists else 0

    missing: list[str] = []
    if not adb:
        missing.append("adb")
    if start_emulator and not emulator:
        missing.append("emulator")
    if not apk_exists:
        missing.append("apk")

    can_attempt = not missing
    emulator_start = _not_checked("emulator start")
    device = _not_checked("device boot")
    install = _not_checked("apk install")
    launch = _not_checked("activity launch")
    process = _not_checked("process pid")
    activity = _not_checked("resumed activity")
    screenshot_report = _not_checked("screenshot")
    emulator_stop = _not_checked("emulator stop")

    if can_attempt:
        if start_emulator:
            emulator_start = _start_emulator_report(avd_name, emulator_starter)
        device = _wait_for_boot(runner, timeout_seconds)
        if device["passes"]:
            install = _install_report(apk, runner, timeout_seconds)
        if install["passes"]:
            launch = _launch_report(
                product=product,
                base_origin=base_origin,
                package_name=package_name,
                activity_name=activity_name,
                runner=runner,
                timeout_seconds=timeout_seconds,
            )
        if launch["passes"]:
            process = _process_report(package_name, runner, timeout_seconds)
            activity = _activity_report(activity_name, runner, timeout_seconds)
            screenshot_report = _screenshot_report(screenshot, runner, timeout_seconds)
        if stop_emulator:
            emulator_stop = _stop_emulator_report(runner, timeout_seconds)

    passes = bool(
        can_attempt
        and device["passes"]
        and install["passes"]
        and launch["passes"]
        and process["passes"]
        and activity["passes"]
        and screenshot_report["passes"]
    )
    return {
        "passes": passes,
        "avd": avd_name,
        "toolchain": {"adb": adb, "emulator": emulator},
        "missing": missing,
        "apk": {
            "path": _relative(apk),
            "exists": apk_exists,
            "sizeBytes": apk_size,
            "passes": apk_exists and apk_size > 0,
        },
        "emulatorStart": emulator_start,
        "device": device,
        "install": install,
        "launch": launch,
        "process": process,
        "activity": activity,
        "screenshot": screenshot_report,
        "emulatorStop": emulator_stop,
    }


def _not_checked(name: str) -> dict[str, Any]:
    return {"checked": False, "passes": False, "name": name}


def _start_emulator_report(avd_name: str, emulator_starter: EmulatorStarter) -> dict[str, Any]:
    command = [
        "emulator",
        "-avd",
        avd_name,
        "-no-window",
        "-no-audio",
        "-no-boot-anim",
        "-gpu",
        "swiftshader_indirect",
    ]
    result = emulator_starter(command, ROOT)
    # Boot polling below is the authoritative check; this only proves launch was requested.
    return {
        "checked": True,
        "passes": result.returncode in {0, 124},
        "result": _command_result_to_json(result),
    }


def _wait_for_boot(runner: CommandRunner, timeout_seconds: int) -> dict[str, Any]:
    deadline = time.monotonic() + max(timeout_seconds, 1)
    attempts: list[dict[str, Any]] = []
    while True:
        result = runner(["adb", "shell", "getprop", "sys.boot_completed"], ROOT, min(timeout_seconds, 10))
        attempts.append(_command_result_to_json(result))
        if result.returncode == 0 and result.stdout.strip() == "1":
            return {"checked": True, "passes": True, "booted": True, "attempts": attempts[-3:]}
        if time.monotonic() >= deadline:
            return {"checked": True, "passes": False, "booted": False, "attempts": attempts[-3:]}
        time.sleep(2)


def _install_report(apk: Path, runner: CommandRunner, timeout_seconds: int) -> dict[str, Any]:
    result = runner(["adb", "install", "-r", str(apk)], ROOT, timeout_seconds)
    output = f"{result.stdout}\n{result.stderr}"
    passes = result.returncode == 0 and ("Success" in output or not result.stderr.strip())
    return {"checked": True, "passes": passes, "status": "ok" if passes else "failed", "result": _command_result_to_json(result)}


def _launch_report(
    *,
    product: str,
    base_origin: str,
    package_name: str,
    activity_name: str,
    runner: CommandRunner,
    timeout_seconds: int,
) -> dict[str, Any]:
    result = runner(
        [
            "adb",
            "shell",
            "am",
            "start",
            "-n",
            activity_name,
            "--es",
            EXTRA_PRODUCT,
            product,
            "--ez",
            EXTRA_CHAT,
            "true",
            "--es",
            EXTRA_BASE_ORIGIN,
            base_origin,
        ],
        ROOT,
        timeout_seconds,
    )
    output = f"{result.stdout}\n{result.stderr}"
    passes = result.returncode == 0 and "Error" not in output and "Exception" not in output
    return {
        "checked": True,
        "passes": passes,
        "status": "ok" if passes else "failed",
        "package": package_name,
        "activity": activity_name,
        "product": product,
        "baseOrigin": base_origin,
        "chatMode": True,
        "result": _command_result_to_json(result),
    }


def _process_report(package_name: str, runner: CommandRunner, timeout_seconds: int) -> dict[str, Any]:
    deadline = time.monotonic() + max(min(timeout_seconds, 30), 1)
    attempts: list[dict[str, Any]] = []
    while True:
        result = runner(["adb", "shell", "pidof", package_name], ROOT, min(timeout_seconds, 10))
        attempts.append(_command_result_to_json(result))
        pid = result.stdout.strip()
        if result.returncode == 0 and pid:
            return {"checked": True, "passes": True, "pid": pid, "attempts": attempts[-5:], "result": _command_result_to_json(result)}
        if time.monotonic() >= deadline:
            return {"checked": True, "passes": False, "pid": pid, "attempts": attempts[-5:], "result": _command_result_to_json(result)}
        time.sleep(1)


def _activity_report(activity_name: str, runner: CommandRunner, timeout_seconds: int) -> dict[str, Any]:
    accepted_activity_names = _accepted_activity_names(activity_name)
    expected_package = activity_name.split("/", 1)[0]
    deadline = time.monotonic() + max(min(timeout_seconds, 30), 1)
    attempts: list[dict[str, Any]] = []
    while True:
        result = runner(["adb", "shell", "dumpsys", "activity", "activities"], ROOT, min(timeout_seconds, 10))
        raw_text = result.stdout
        text = raw_text.replace("\n", " ")
        attempts.append(_command_result_to_json(result))
        has_activity = result.returncode == 0 and (
            any(name in text for name in accepted_activity_names)
            or _visible_process_for_package(raw_text, expected_package)
        )
        is_starting_only = "mStartingProcessActivities" in text and "topResumedActivity" not in text and "ResumedActivity" not in text
        if not has_activity:
            focused_result = runner(["adb", "shell", "dumpsys", "window", "windows"], ROOT, min(timeout_seconds, 10))
            focused_text = focused_result.stdout.replace("\n", " ")
            focused_raw_text = focused_result.stdout
            attempts.append(_command_result_to_json(focused_result))
            if focused_result.returncode == 0 and (
                any(name in focused_text for name in accepted_activity_names)
                or _visible_process_for_package(focused_raw_text, expected_package)
            ):
                return {
                    "checked": True,
                    "passes": True,
                    "expectedActivity": activity_name,
                    "acceptedActivityNames": accepted_activity_names,
                    "resumedActivity": focused_text[-1000:],
                    "attempts": attempts[-5:],
                    "result": _command_result_to_json(focused_result),
                    "source": "focused window",
                }
        if has_activity and not is_starting_only:
            return {
                "checked": True,
                "passes": True,
                "expectedActivity": activity_name,
                "acceptedActivityNames": accepted_activity_names,
                "resumedActivity": text[-1000:],
                "attempts": attempts[-5:],
                "result": _command_result_to_json(result),
            }
        if time.monotonic() >= deadline:
            return {
                "checked": True,
                "passes": False,
                "expectedActivity": activity_name,
                "acceptedActivityNames": accepted_activity_names,
                "resumedActivity": text[-1000:],
                "attempts": attempts[-5:],
                "result": _command_result_to_json(result),
            }
        time.sleep(1)


def _screenshot_report(screenshot: Path, runner: CommandRunner, timeout_seconds: int) -> dict[str, Any]:
    screenshot.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + max(min(timeout_seconds, 45), 1)
    attempts: list[dict[str, Any]] = []
    while True:
        if screenshot.exists():
            screenshot.unlink()
        result = runner(["adb", "exec-out", "screencap", "-p"], ROOT, min(timeout_seconds, 30))
        if result.stdout_bytes:
            screenshot.write_bytes(result.stdout_bytes)
        elif result.stdout and not screenshot.exists():
            screenshot.write_bytes(result.stdout.encode("latin-1", errors="ignore"))
        exists = screenshot.exists()
        size = screenshot.stat().st_size if exists else 0
        visual = _visual_screenshot_report(screenshot) if exists and size > 0 else _not_checked("visual screenshot")
        capture = {
            "checked": True,
            "passes": result.returncode == 0 and exists and size > 0 and visual["passes"],
            "path": _relative(screenshot),
            "captured": exists and size > 0,
            "sizeBytes": size,
            "visual": visual,
            "result": _command_result_to_json(result, omit_binary=True),
        }
        attempts.append(capture)
        if capture["passes"] or time.monotonic() >= deadline:
            return {**capture, "attempts": attempts[-5:]}
        time.sleep(1)


def _visual_screenshot_report(screenshot: Path) -> dict[str, Any]:
    try:
        with Image.open(screenshot) as image:
            image.load()
            width, height = image.size
            sample = image.convert("RGB")
            colors = sample.getcolors(maxcolors=1_000_000)
            distinct_count = len(colors) if colors is not None else 1_000_001
            total_pixels = max(width * height, 1)
            mostly_white_pixels = (
                sum(count for count, rgb in colors if min(rgb) >= 245) if colors is not None else 0
            )
            mostly_white_ratio = mostly_white_pixels / total_pixels
    except (OSError, UnidentifiedImageError, ValueError) as exc:
        return {
            "checked": True,
            "passes": False,
            "validImage": False,
            "error": str(exc),
            "width": 0,
            "height": 0,
            "distinctColorCount": 0,
            "mostlyWhiteRatio": 0,
        }
    return {
        "checked": True,
        "passes": width > 0 and height > 0 and distinct_count > 1 and mostly_white_ratio < 0.92,
        "validImage": True,
        "width": width,
        "height": height,
        "distinctColorCount": distinct_count,
        "mostlyWhiteRatio": mostly_white_ratio,
    }


def _accepted_activity_names(activity_name: str) -> list[str]:
    names = [activity_name]
    if "/" in activity_name:
        package, activity = activity_name.split("/", 1)
        if activity.startswith("."):
            names.append(f"{package}/{package}{activity}")
        elif activity.startswith(f"{package}."):
            names.append(f"{package}/{activity.removeprefix(package)}")
    return list(dict.fromkeys(names))


def _visible_process_for_package(text: str, package_name: str) -> bool:
    if not package_name:
        return False
    pattern = rf"VisibleActivityProcess:\[.*:{re.escape(package_name)}/"
    return re.search(pattern, text, re.DOTALL) is not None


def _stop_emulator_report(runner: CommandRunner, timeout_seconds: int) -> dict[str, Any]:
    result = runner(["adb", "emu", "kill"], ROOT, min(timeout_seconds, 10))
    output = f"{result.stdout}\n{result.stderr}"
    return {
        "checked": True,
        "passes": result.returncode == 0 or "OK" in output or "killed" in output.lower(),
        "result": _command_result_to_json(result),
    }


def _relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def _command_exists(name: str) -> str:
    path = shutil.which(name)
    if path:
        return path
    android_root = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    if android_root:
        candidate = Path(android_root) / ("platform-tools" if name == "adb" else "emulator") / name
        if candidate.exists():
            return str(candidate)
    return ""


def _start_detached_command(command: list[str], cwd: Path) -> CommandResult:
    started = time.monotonic()
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return CommandResult(
            command=command,
            cwd=str(cwd),
            returncode=0,
            stdout=f"pid={process.pid}",
            stderr="",
            durationMs=int((time.monotonic() - started) * 1000),
        )
    except OSError as exc:
        return CommandResult(
            command=command,
            cwd=str(cwd),
            returncode=127,
            stdout="",
            stderr=str(exc),
            durationMs=int((time.monotonic() - started) * 1000),
        )


def _run_command(command: list[str], cwd: Path, timeout_seconds: int) -> CommandResult:
    started = time.monotonic()
    try:
        completed = subprocess.run(command, cwd=cwd, check=False, capture_output=True, timeout=timeout_seconds)
        stdout = completed.stdout.decode("utf-8", errors="replace")
        stderr = completed.stderr.decode("utf-8", errors="replace")
        return CommandResult(
            command=command,
            cwd=str(cwd),
            returncode=completed.returncode,
            stdout=stdout[-8000:],
            stderr=stderr[-8000:],
            durationMs=int((time.monotonic() - started) * 1000),
            stdout_bytes=completed.stdout if command[:2] == ["adb", "exec-out"] else None,
        )
    except subprocess.TimeoutExpired as exc:
        stdout_bytes = exc.stdout if isinstance(exc.stdout, bytes) else b""
        stderr_bytes = exc.stderr if isinstance(exc.stderr, bytes) else b""
        return CommandResult(
            command=command,
            cwd=str(cwd),
            returncode=124,
            stdout=stdout_bytes.decode("utf-8", errors="replace")[-8000:],
            stderr=stderr_bytes.decode("utf-8", errors="replace")[-8000:] + "\ntimeout",
            durationMs=int((time.monotonic() - started) * 1000),
            stdout_bytes=stdout_bytes if command[:2] == ["adb", "exec-out"] else None,
        )


def _command_result_to_json(result: CommandResult, *, omit_binary: bool = False) -> dict[str, Any]:
    return {
        "command": result.command,
        "cwd": result.cwd,
        "returncode": result.returncode,
        "stdout": "<binary stdout omitted>" if omit_binary and result.stdout_bytes else result.stdout[-2000:],
        "stderr": result.stderr[-2000:],
        "durationMs": result.durationMs,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apk", type=Path, default=DEFAULT_APK)
    parser.add_argument("--avd", default="bunjum_beta6_api35")
    parser.add_argument("--base-origin", default="http://127.0.0.1:8061")
    parser.add_argument("--product", default="islam")
    parser.add_argument("--screenshot", type=Path, default=DEFAULT_SCREENSHOT)
    parser.add_argument("--start-emulator", action="store_true")
    parser.add_argument("--stop-emulator", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--package-name", default=DEFAULT_PACKAGE)
    parser.add_argument("--activity-name", default="")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    activity_name = args.activity_name or f"{args.package_name}/ai.bunjum.beta6.NativeShellActivity"
    report = build_report(
        apk_path=args.apk,
        avd_name=args.avd,
        base_origin=args.base_origin,
        product=args.product,
        screenshot_path=args.screenshot,
        start_emulator=args.start_emulator,
        stop_emulator=args.stop_emulator,
        timeout_seconds=args.timeout_seconds,
        package_name=args.package_name,
        activity_name=activity_name,
    )
    encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    if args.json:
        print(encoded)
    else:
        print(("PASS" if report["passes"] else "FAIL") + " android runtime smoke")
        print(f"apk: exists={report['apk']['exists']} size={report['apk']['sizeBytes']}")
        print(f"device: pass={report['device']['passes']}")
        print(f"install: pass={report['install']['passes']}")
        print(f"launch: pass={report['launch']['passes']}")
        print(f"activity: pass={report['activity']['passes']}")
        print(f"screenshot: pass={report['screenshot']['passes']}")
    return 0 if report["passes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
