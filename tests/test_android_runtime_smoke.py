import importlib.util
from io import BytesIO
from pathlib import Path

from PIL import Image


def _load_verifier():
    path = Path("tools/verify_android_runtime_smoke.py")
    spec = importlib.util.spec_from_file_location("verify_android_runtime_smoke", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _png_bytes(colors=((255, 255, 255), (0, 0, 0), (30, 120, 200), (230, 80, 40))):
    image = Image.new("RGB", (2, 2))
    image.putdata(list(colors))
    handle = BytesIO()
    image.save(handle, format="PNG")
    return handle.getvalue()


def _solid_png_bytes(color=(255, 255, 255)):
    return _png_bytes((color, color, color, color))


def _mostly_white_png_bytes():
    image = Image.new("RGB", (100, 100), (255, 255, 255))
    for x in range(42, 58):
        for y in range(42, 58):
            image.putpixel((x, y), (0, 128, 128))
    handle = BytesIO()
    image.save(handle, format="PNG")
    return handle.getvalue()


def test_android_runtime_smoke_passes_only_when_apk_installs_launches_and_screenshots(tmp_path):
    verifier = _load_verifier()
    apk_path = tmp_path / "app-debug.apk"
    apk_path.write_bytes(b"apk")
    screenshot_path = tmp_path / "runtime.png"
    calls = []

    def command_exists(name):
        return f"/usr/bin/{name}" if name in {"adb", "emulator"} else ""

    def runner(command, cwd, timeout_seconds):
        calls.append(command)
        text = " ".join(command)
        if "getprop sys.boot_completed" in text:
            return verifier.CommandResult(command, str(cwd), 0, "1\n", "")
        if command[:2] == ["adb", "install"]:
            return verifier.CommandResult(command, str(cwd), 0, "Success\n", "")
        if command[:3] == ["adb", "shell", "am"]:
            return verifier.CommandResult(command, str(cwd), 0, "Starting: Intent\n", "")
        if "pidof ai.bunjum.beta6" in text:
            return verifier.CommandResult(command, str(cwd), 0, "1234\n", "")
        if "dumpsys activity activities" in text:
            return verifier.CommandResult(
                command,
                str(cwd),
                0,
                "topResumedActivity=ActivityRecord{abc u0 ai.bunjum.beta6/.NativeShellActivity t1}\n",
                "",
            )
        if command[:2] == ["adb", "exec-out"]:
            screenshot_path.write_bytes(_png_bytes())
            return verifier.CommandResult(command, str(cwd), 0, "", "")
        return verifier.CommandResult(command, str(cwd), 0, "", "")

    report = verifier.build_report(
        apk_path=apk_path,
        avd_name="bunjum_beta6_api35",
        base_origin="https://example.trycloudflare.com",
        product="islam",
        screenshot_path=screenshot_path,
        command_exists=command_exists,
        runner=runner,
        start_emulator=False,
        timeout_seconds=30,
    )

    assert report["passes"] is True
    assert report["toolchain"]["adb"] == "/usr/bin/adb"
    assert report["apk"]["exists"] is True
    assert report["device"]["booted"] is True
    assert report["install"]["passes"] is True
    assert report["launch"]["passes"] is True
    assert report["launch"]["baseOrigin"] == "https://example.trycloudflare.com"
    assert report["launch"]["product"] == "islam"
    assert report["activity"]["passes"] is True
    assert report["screenshot"]["passes"] is True
    assert report["screenshot"]["visual"]["passes"] is True
    assert screenshot_path.exists()
    assert any("am" in command for command in calls)


def test_android_runtime_smoke_fails_without_adb_or_existing_apk(tmp_path):
    verifier = _load_verifier()

    report = verifier.build_report(
        apk_path=tmp_path / "missing.apk",
        avd_name="bunjum_beta6_api35",
        base_origin="https://example.trycloudflare.com",
        product="islam",
        screenshot_path=tmp_path / "runtime.png",
        command_exists=lambda name: "",
        runner=lambda command, cwd, timeout_seconds: verifier.CommandResult(command, str(cwd), 0),
        start_emulator=False,
    )

    assert report["passes"] is False
    assert report["apk"]["exists"] is False
    assert "adb" in report["missing"]
    assert report["install"]["checked"] is False
    assert report["launch"]["checked"] is False


def test_android_runtime_smoke_fails_when_activity_does_not_resume(tmp_path):
    verifier = _load_verifier()
    apk_path = tmp_path / "app-debug.apk"
    apk_path.write_bytes(b"apk")
    screenshot_path = tmp_path / "runtime.png"

    def command_exists(name):
        return f"/usr/bin/{name}" if name in {"adb", "emulator"} else ""

    def runner(command, cwd, timeout_seconds):
        text = " ".join(command)
        if "getprop sys.boot_completed" in text:
            return verifier.CommandResult(command, str(cwd), 0, "1\n", "")
        if command[:2] == ["adb", "install"]:
            return verifier.CommandResult(command, str(cwd), 0, "Success\n", "")
        if command[:3] == ["adb", "shell", "am"]:
            return verifier.CommandResult(command, str(cwd), 0, "Starting: Intent\n", "")
        if "pidof ai.bunjum.beta6" in text:
            return verifier.CommandResult(command, str(cwd), 0, "1234\n", "")
        if "dumpsys activity activities" in text:
            return verifier.CommandResult(command, str(cwd), 0, "topResumedActivity=ActivityRecord{abc u0 other/.Main t1}\n", "")
        if command[:2] == ["adb", "exec-out"]:
            screenshot_path.write_bytes(_png_bytes())
            return verifier.CommandResult(command, str(cwd), 0, "", "")
        return verifier.CommandResult(command, str(cwd), 0, "", "")

    report = verifier.build_report(
        apk_path=apk_path,
        avd_name="bunjum_beta6_api35",
        base_origin="https://example.trycloudflare.com",
        product="islam",
        screenshot_path=screenshot_path,
        command_exists=command_exists,
        runner=runner,
        start_emulator=False,
        timeout_seconds=1,
    )

    assert report["passes"] is False
    assert report["activity"]["passes"] is False
    assert report["activity"]["expectedActivity"] == "ai.bunjum.beta6/ai.bunjum.beta6.NativeShellActivity"


def test_android_runtime_smoke_starts_emulator_with_detached_starter_before_boot_poll(tmp_path):
    verifier = _load_verifier()
    apk_path = tmp_path / "app-debug.apk"
    apk_path.write_bytes(b"apk")
    screenshot_path = tmp_path / "runtime.png"
    started = []
    calls = []

    def command_exists(name):
        return f"/usr/bin/{name}" if name in {"adb", "emulator"} else ""

    def emulator_starter(command, cwd):
        started.append({"command": command, "cwd": str(cwd)})
        return verifier.CommandResult(command, str(cwd), 0, "pid=4321\n", "")

    def runner(command, cwd, timeout_seconds):
        calls.append(command)
        text = " ".join(command)
        if "getprop sys.boot_completed" in text:
            return verifier.CommandResult(command, str(cwd), 0, "1\n", "")
        if command[:2] == ["adb", "install"]:
            return verifier.CommandResult(command, str(cwd), 0, "Success\n", "")
        if command[:3] == ["adb", "shell", "am"]:
            return verifier.CommandResult(command, str(cwd), 0, "Starting: Intent\n", "")
        if "pidof ai.bunjum.beta6" in text:
            return verifier.CommandResult(command, str(cwd), 0, "1234\n", "")
        if "dumpsys activity activities" in text:
            return verifier.CommandResult(
                command,
                str(cwd),
                0,
                "topResumedActivity=ActivityRecord{abc u0 ai.bunjum.beta6/.NativeShellActivity t1}\n",
                "",
            )
        if command[:2] == ["adb", "exec-out"]:
            screenshot_path.write_bytes(_png_bytes())
            return verifier.CommandResult(command, str(cwd), 0, "", "")
        return verifier.CommandResult(command, str(cwd), 0, "", "")

    report = verifier.build_report(
        apk_path=apk_path,
        avd_name="bunjum_beta6_api35",
        base_origin="https://example.trycloudflare.com",
        product="islam",
        screenshot_path=screenshot_path,
        command_exists=command_exists,
        runner=runner,
        emulator_starter=emulator_starter,
        start_emulator=True,
    )

    assert report["passes"] is True
    assert report["emulatorStart"]["passes"] is True
    assert started[0]["command"][:3] == ["emulator", "-avd", "bunjum_beta6_api35"]
    assert calls[0][:4] == ["adb", "shell", "getprop", "sys.boot_completed"]


def test_android_runtime_smoke_can_stop_emulator_after_runtime_check(tmp_path):
    verifier = _load_verifier()
    apk_path = tmp_path / "app-debug.apk"
    apk_path.write_bytes(b"apk")
    screenshot_path = tmp_path / "runtime.png"
    calls = []

    def command_exists(name):
        return f"/usr/bin/{name}" if name in {"adb", "emulator"} else ""

    def runner(command, cwd, timeout_seconds):
        calls.append(command)
        text = " ".join(command)
        if "getprop sys.boot_completed" in text:
            return verifier.CommandResult(command, str(cwd), 0, "1\n", "")
        if command[:2] == ["adb", "install"]:
            return verifier.CommandResult(command, str(cwd), 0, "Success\n", "")
        if command[:3] == ["adb", "shell", "am"]:
            return verifier.CommandResult(command, str(cwd), 0, "Starting: Intent\n", "")
        if "pidof ai.bunjum.beta6" in text:
            return verifier.CommandResult(command, str(cwd), 0, "1234\n", "")
        if "dumpsys activity activities" in text:
            return verifier.CommandResult(
                command,
                str(cwd),
                0,
                "topResumedActivity=ActivityRecord{abc u0 ai.bunjum.beta6/.NativeShellActivity t1}\n",
                "",
            )
        if command[:2] == ["adb", "exec-out"]:
            screenshot_path.write_bytes(_png_bytes())
            return verifier.CommandResult(command, str(cwd), 0, "", "")
        if command[:3] == ["adb", "emu", "kill"]:
            return verifier.CommandResult(command, str(cwd), 0, "OK\n", "")
        return verifier.CommandResult(command, str(cwd), 0, "", "")

    report = verifier.build_report(
        apk_path=apk_path,
        avd_name="bunjum_beta6_api35",
        base_origin="https://example.trycloudflare.com",
        product="islam",
        screenshot_path=screenshot_path,
        command_exists=command_exists,
        runner=runner,
        start_emulator=False,
        stop_emulator=True,
    )

    assert report["passes"] is True
    assert report["emulatorStop"]["passes"] is True
    assert calls[-1] == ["adb", "emu", "kill"]


def test_android_runtime_smoke_waits_for_process_and_resumed_activity_after_launch(tmp_path):
    verifier = _load_verifier()
    apk_path = tmp_path / "app-debug.apk"
    apk_path.write_bytes(b"apk")
    screenshot_path = tmp_path / "runtime.png"
    pid_attempts = {"count": 0}
    activity_attempts = {"count": 0}

    def command_exists(name):
        return f"/usr/bin/{name}" if name in {"adb", "emulator"} else ""

    def runner(command, cwd, timeout_seconds):
        text = " ".join(command)
        if "getprop sys.boot_completed" in text:
            return verifier.CommandResult(command, str(cwd), 0, "1\n", "")
        if command[:2] == ["adb", "install"]:
            return verifier.CommandResult(command, str(cwd), 0, "Success\n", "")
        if command[:3] == ["adb", "shell", "am"]:
            return verifier.CommandResult(command, str(cwd), 0, "Starting: Intent\n", "")
        if "pidof ai.bunjum.beta6" in text:
            pid_attempts["count"] += 1
            if pid_attempts["count"] == 1:
                return verifier.CommandResult(command, str(cwd), 1, "", "")
            return verifier.CommandResult(command, str(cwd), 0, "1234\n", "")
        if "dumpsys activity activities" in text:
            activity_attempts["count"] += 1
            if activity_attempts["count"] == 1:
                return verifier.CommandResult(command, str(cwd), 0, "mStartingProcessActivities=[ai.bunjum.beta6/.NativeShellActivity]\n", "")
            return verifier.CommandResult(
                command,
                str(cwd),
                0,
                "topResumedActivity=ActivityRecord{abc u0 ai.bunjum.beta6/.NativeShellActivity t1}\n",
                "",
            )
        if command[:2] == ["adb", "exec-out"]:
            screenshot_path.write_bytes(_png_bytes())
            return verifier.CommandResult(command, str(cwd), 0, "", "")
        return verifier.CommandResult(command, str(cwd), 0, "", "")

    report = verifier.build_report(
        apk_path=apk_path,
        avd_name="bunjum_beta6_api35",
        base_origin="https://example.trycloudflare.com",
        product="islam",
        screenshot_path=screenshot_path,
        command_exists=command_exists,
        runner=runner,
        start_emulator=False,
        timeout_seconds=5,
    )

    assert report["passes"] is True
    assert report["process"]["pid"] == "1234"
    assert pid_attempts["count"] == 2
    assert activity_attempts["count"] == 2


def test_android_runtime_smoke_accepts_fully_qualified_activity_in_dumpsys(tmp_path):
    verifier = _load_verifier()
    apk_path = tmp_path / "app-debug.apk"
    apk_path.write_bytes(b"apk")
    screenshot_path = tmp_path / "runtime.png"

    def command_exists(name):
        return f"/usr/bin/{name}" if name in {"adb", "emulator"} else ""

    def runner(command, cwd, timeout_seconds):
        text = " ".join(command)
        if "getprop sys.boot_completed" in text:
            return verifier.CommandResult(command, str(cwd), 0, "1\n", "")
        if command[:2] == ["adb", "install"]:
            return verifier.CommandResult(command, str(cwd), 0, "Success\n", "")
        if command[:3] == ["adb", "shell", "am"]:
            return verifier.CommandResult(command, str(cwd), 0, "Starting: Intent\n", "")
        if "pidof ai.bunjum.beta6" in text:
            return verifier.CommandResult(command, str(cwd), 0, "1234\n", "")
        if "dumpsys activity activities" in text:
            return verifier.CommandResult(
                command,
                str(cwd),
                0,
                "mControlTarget=Window{7fb0065 u0 ai.bunjum.beta6/ai.bunjum.beta6.NativeShellActivity}\n",
                "",
            )
        if command[:2] == ["adb", "exec-out"]:
            screenshot_path.write_bytes(_png_bytes())
            return verifier.CommandResult(command, str(cwd), 0, "", "")
        return verifier.CommandResult(command, str(cwd), 0, "", "")

    report = verifier.build_report(
        apk_path=apk_path,
        avd_name="bunjum_beta6_api35",
        base_origin="https://example.trycloudflare.com",
        product="islam",
        screenshot_path=screenshot_path,
        command_exists=command_exists,
        runner=runner,
        start_emulator=False,
        timeout_seconds=5,
    )

    assert report["passes"] is True
    assert report["activity"]["passes"] is True


def test_android_runtime_smoke_accepts_focused_window_when_activity_dump_is_truncated(tmp_path):
    verifier = _load_verifier()
    apk_path = tmp_path / "app-debug.apk"
    apk_path.write_bytes(b"apk")
    screenshot_path = tmp_path / "runtime.png"
    calls = []

    def command_exists(name):
        return f"/usr/bin/{name}" if name in {"adb", "emulator"} else ""

    def runner(command, cwd, timeout_seconds):
        calls.append(command)
        text = " ".join(command)
        if "getprop sys.boot_completed" in text:
            return verifier.CommandResult(command, str(cwd), 0, "1\n", "")
        if command[:2] == ["adb", "install"]:
            return verifier.CommandResult(command, str(cwd), 0, "Success\n", "")
        if command[:3] == ["adb", "shell", "am"]:
            return verifier.CommandResult(command, str(cwd), 0, "Starting: Intent\n", "")
        if "pidof ai.bunjum.hikmah" in text:
            return verifier.CommandResult(command, str(cwd), 0, "3017\n", "")
        if command == ["adb", "shell", "dumpsys", "activity", "activities"]:
            return verifier.CommandResult(command, str(cwd), 0, "Task{9d0bdc4 #23 type=standard A=10140:ai.bunjum.hikmah}\n", "")
        if command == ["adb", "shell", "dumpsys", "window", "windows"]:
            return verifier.CommandResult(
                command,
                str(cwd),
                0,
                "mCurrentFocus=Window{8b95756 u0 ai.bunjum.hikmah/ai.bunjum.beta6.NativeShellActivity}\n",
                "",
            )
        if command[:2] == ["adb", "exec-out"]:
            return verifier.CommandResult(command, str(cwd), 0, stdout_bytes=_png_bytes())
        return verifier.CommandResult(command, str(cwd), 0, "", "")

    report = verifier.build_report(
        apk_path=apk_path,
        base_origin="https://example.trycloudflare.com",
        product="islam",
        screenshot_path=screenshot_path,
        command_exists=command_exists,
        runner=runner,
        package_name="ai.bunjum.hikmah",
        activity_name="ai.bunjum.hikmah/ai.bunjum.beta6.NativeShellActivity",
        timeout_seconds=5,
    )

    assert report["passes"] is True
    assert report["activity"]["passes"] is True
    assert ["adb", "shell", "dumpsys", "window", "windows"] in calls


def test_android_runtime_smoke_can_target_custom_package_and_activity(tmp_path):
    verifier = _load_verifier()
    apk_path = tmp_path / "lawkey-debug.apk"
    apk_path.write_bytes(b"apk")
    screenshot_path = tmp_path / "runtime.png"
    calls = []

    def command_exists(name):
        return f"/usr/bin/{name}" if name in {"adb", "emulator"} else ""

    def runner(command, cwd, timeout_seconds):
        calls.append(command)
        text = " ".join(command)
        if "getprop sys.boot_completed" in text:
            return verifier.CommandResult(command, str(cwd), 0, "1\n", "")
        if command[:2] == ["adb", "install"]:
            return verifier.CommandResult(command, str(cwd), 0, "Success\n", "")
        if command[:3] == ["adb", "shell", "am"]:
            return verifier.CommandResult(command, str(cwd), 0, "Starting: Intent\n", "")
        if "pidof ai.bunjum.lawkey" in text:
            return verifier.CommandResult(command, str(cwd), 0, "4321\n", "")
        if "dumpsys activity activities" in text:
            return verifier.CommandResult(
                command,
                str(cwd),
                0,
                "topResumedActivity=ActivityRecord{abc u0 ai.bunjum.lawkey/ai.bunjum.beta6.NativeShellActivity t1}\n",
                "",
            )
        if command[:2] == ["adb", "exec-out"]:
            screenshot_path.write_bytes(_png_bytes())
            return verifier.CommandResult(command, str(cwd), 0, "", "")
        return verifier.CommandResult(command, str(cwd), 0, "", "")

    report = verifier.build_report(
        apk_path=apk_path,
        avd_name="bunjum_beta6_api35",
        base_origin="https://lawkey.ai.kr",
        product="lawkey",
        screenshot_path=screenshot_path,
        command_exists=command_exists,
        runner=runner,
        package_name="ai.bunjum.lawkey",
        activity_name="ai.bunjum.lawkey/ai.bunjum.beta6.NativeShellActivity",
        timeout_seconds=5,
    )

    assert report["passes"] is True
    assert report["launch"]["package"] == "ai.bunjum.lawkey"
    assert report["launch"]["activity"] == "ai.bunjum.lawkey/ai.bunjum.beta6.NativeShellActivity"
    assert any("pidof ai.bunjum.lawkey" in " ".join(command) for command in calls)


def test_android_runtime_smoke_writes_binary_screenshot_without_dumping_binary_json(tmp_path):
    verifier = _load_verifier()
    apk_path = tmp_path / "app-debug.apk"
    apk_path.write_bytes(b"apk")
    screenshot_path = tmp_path / "runtime.png"
    png = _png_bytes()

    def command_exists(name):
        return f"/usr/bin/{name}" if name in {"adb", "emulator"} else ""

    def runner(command, cwd, timeout_seconds):
        text = " ".join(command)
        if "getprop sys.boot_completed" in text:
            return verifier.CommandResult(command, str(cwd), 0, "1\n", "")
        if command[:2] == ["adb", "install"]:
            return verifier.CommandResult(command, str(cwd), 0, "Success\n", "")
        if command[:3] == ["adb", "shell", "am"]:
            return verifier.CommandResult(command, str(cwd), 0, "Starting: Intent\n", "")
        if "pidof ai.bunjum.beta6" in text:
            return verifier.CommandResult(command, str(cwd), 0, "1234\n", "")
        if "dumpsys activity activities" in text:
            return verifier.CommandResult(
                command,
                str(cwd),
                0,
                "topResumedActivity=ActivityRecord{abc u0 ai.bunjum.beta6/.NativeShellActivity t1}\n",
                "",
            )
        if command[:2] == ["adb", "exec-out"]:
            return verifier.CommandResult(command, str(cwd), 0, stdout_bytes=png)
        return verifier.CommandResult(command, str(cwd), 0, "", "")

    report = verifier.build_report(
        apk_path=apk_path,
        avd_name="bunjum_beta6_api35",
        base_origin="https://example.trycloudflare.com",
        product="islam",
        screenshot_path=screenshot_path,
        command_exists=command_exists,
        runner=runner,
        start_emulator=False,
    )

    assert report["passes"] is True
    assert screenshot_path.read_bytes() == png
    assert report["screenshot"]["result"]["stdout"] == "<binary stdout omitted>"


def test_android_runtime_smoke_fails_blank_or_invalid_visual_screenshot(tmp_path):
    verifier = _load_verifier()
    apk_path = tmp_path / "app-debug.apk"
    apk_path.write_bytes(b"apk")
    screenshot_path = tmp_path / "runtime.png"

    def command_exists(name):
        return f"/usr/bin/{name}" if name in {"adb", "emulator"} else ""

    def runner(command, cwd, timeout_seconds):
        text = " ".join(command)
        if "getprop sys.boot_completed" in text:
            return verifier.CommandResult(command, str(cwd), 0, "1\n", "")
        if command[:2] == ["adb", "install"]:
            return verifier.CommandResult(command, str(cwd), 0, "Success\n", "")
        if command[:3] == ["adb", "shell", "am"]:
            return verifier.CommandResult(command, str(cwd), 0, "Starting: Intent\n", "")
        if "pidof ai.bunjum.beta6" in text:
            return verifier.CommandResult(command, str(cwd), 0, "1234\n", "")
        if "dumpsys activity activities" in text:
            return verifier.CommandResult(
                command,
                str(cwd),
                0,
                "topResumedActivity=ActivityRecord{abc u0 ai.bunjum.beta6/.NativeShellActivity t1}\n",
                "",
            )
        if command[:2] == ["adb", "exec-out"]:
            return verifier.CommandResult(command, str(cwd), 0, stdout_bytes=_solid_png_bytes())
        return verifier.CommandResult(command, str(cwd), 0, "", "")

    report = verifier.build_report(
        apk_path=apk_path,
        avd_name="bunjum_beta6_api35",
        base_origin="https://example.trycloudflare.com",
        product="islam",
        screenshot_path=screenshot_path,
        command_exists=command_exists,
        runner=runner,
        start_emulator=False,
    )

    assert report["passes"] is False
    assert report["screenshot"]["passes"] is False
    assert report["screenshot"]["visual"]["validImage"] is True
    assert report["screenshot"]["visual"]["distinctColorCount"] == 1


def test_android_runtime_smoke_retries_mostly_white_launch_splash_screenshot(tmp_path):
    verifier = _load_verifier()
    apk_path = tmp_path / "app-debug.apk"
    apk_path.write_bytes(b"apk")
    screenshot_path = tmp_path / "runtime.png"
    screenshot_attempts = {"count": 0}

    def command_exists(name):
        return f"/usr/bin/{name}" if name in {"adb", "emulator"} else ""

    def runner(command, cwd, timeout_seconds):
        text = " ".join(command)
        if "getprop sys.boot_completed" in text:
            return verifier.CommandResult(command, str(cwd), 0, "1\n", "")
        if command[:2] == ["adb", "install"]:
            return verifier.CommandResult(command, str(cwd), 0, "Success\n", "")
        if command[:3] == ["adb", "shell", "am"]:
            return verifier.CommandResult(command, str(cwd), 0, "Starting: Intent\n", "")
        if "pidof ai.bunjum.beta6" in text:
            return verifier.CommandResult(command, str(cwd), 0, "1234\n", "")
        if "dumpsys activity activities" in text:
            return verifier.CommandResult(
                command,
                str(cwd),
                0,
                "topResumedActivity=ActivityRecord{abc u0 ai.bunjum.beta6/.NativeShellActivity t1}\n",
                "",
            )
        if command[:2] == ["adb", "exec-out"]:
            screenshot_attempts["count"] += 1
            payload = _mostly_white_png_bytes() if screenshot_attempts["count"] == 1 else _png_bytes()
            return verifier.CommandResult(command, str(cwd), 0, stdout_bytes=payload)
        return verifier.CommandResult(command, str(cwd), 0, "", "")

    report = verifier.build_report(
        apk_path=apk_path,
        base_origin="https://example.trycloudflare.com",
        product="islam",
        screenshot_path=screenshot_path,
        command_exists=command_exists,
        runner=runner,
        start_emulator=False,
        timeout_seconds=5,
    )

    assert report["passes"] is True
    assert screenshot_attempts["count"] == 2
    assert report["screenshot"]["visual"]["mostlyWhiteRatio"] < 0.92
    assert report["screenshot"]["attempts"][0]["visual"]["mostlyWhiteRatio"] > 0.92
