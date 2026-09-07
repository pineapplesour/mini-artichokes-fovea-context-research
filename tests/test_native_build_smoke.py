import importlib.util
import json
from pathlib import Path
import zipfile

import pytest


def load_native_build_smoke():
    path = Path("tools/verify_native_build_smoke.py")
    if not path.exists():
        pytest.fail("tools/verify_native_build_smoke.py is missing")
    spec = importlib.util.spec_from_file_location("verify_native_build_smoke", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_native_build_smoke_does_not_treat_scaffold_as_build_proof():
    verify_native_build_smoke = load_native_build_smoke()

    report = verify_native_build_smoke.build_report(
        attempt_android=False,
        attempt_ios=False,
        command_exists=lambda name: "",
        env={},
        platform_system="Linux",
    )

    assert report["nativeParity"]["passes"] is True
    assert report["android"]["projectPass"] is True
    assert report["ios"]["projectPass"] is True
    assert report["android"]["build"]["checked"] is False
    assert report["ios"]["build"]["checked"] is False
    assert report["passes"] is False


def test_native_build_smoke_passes_only_after_android_and_ios_build_commands_succeed():
    verify_native_build_smoke = load_native_build_smoke()
    calls = []
    apk_path = Path("runs/test-native-build-smoke/app-debug.apk")
    apk_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(Path("web/app-shell-manifest.json").read_text(encoding="utf-8"))
    with zipfile.ZipFile(apk_path, "w") as zf:
        zf.writestr("assets/app-shell-manifest.json", json.dumps(manifest, ensure_ascii=False, sort_keys=True))

    def command_exists(name):
        return f"/usr/bin/{name}" if name in {"gradle", "java", "xcodebuild"} else ""

    def runner(command, cwd, timeout_seconds):
        calls.append({"command": command, "cwd": str(cwd), "timeout": timeout_seconds})
        return verify_native_build_smoke.CommandResult(
            command=command,
            cwd=str(cwd),
            returncode=0,
            stdout="BUILD SUCCESSFUL",
            stderr="",
            durationMs=25,
        )

    report = verify_native_build_smoke.build_report(
        attempt_android=True,
        attempt_ios=True,
        command_exists=command_exists,
        runner=runner,
        env={"ANDROID_HOME": "/opt/android-sdk"},
        platform_system="Darwin",
        android_apk_path=apk_path,
    )

    assert report["passes"] is True
    assert report["android"]["build"]["passes"] is True
    assert report["android"]["build"]["apk"]["passes"] is True
    assert report["android"]["build"]["apk"]["manifestAssetSynced"] is True
    assert report["ios"]["build"]["passes"] is True
    assert calls[0]["command"][:2] == ["./gradlew", ":app:assembleDebug"]
    assert calls[1]["command"][:4] == ["xcodebuild", "-scheme", "BunjumBeta6Native", "-sdk"]


def test_native_build_smoke_rejects_successful_android_command_without_synced_apk_manifest(tmp_path):
    verify_native_build_smoke = load_native_build_smoke()
    apk_path = tmp_path / "app-debug.apk"
    with zipfile.ZipFile(apk_path, "w") as zf:
        zf.writestr("assets/app-shell-manifest.json", json.dumps({"wrong": True}))

    def command_exists(name):
        return f"/usr/bin/{name}" if name in {"java", "xcodebuild"} else ""

    def runner(command, cwd, timeout_seconds):
        return verify_native_build_smoke.CommandResult(command=command, cwd=str(cwd), returncode=0)

    report = verify_native_build_smoke.build_report(
        attempt_android=True,
        attempt_ios=False,
        command_exists=command_exists,
        runner=runner,
        env={"ANDROID_HOME": "/opt/android-sdk"},
        platform_system="Linux",
        android_apk_path=apk_path,
    )

    assert report["android"]["build"]["result"]["returncode"] == 0
    assert report["android"]["build"]["apk"]["exists"] is True
    assert report["android"]["build"]["apk"]["manifestAssetSynced"] is False
    assert report["android"]["build"]["passes"] is False


def test_native_build_smoke_reports_missing_current_wsl_toolchain_as_unverified():
    verify_native_build_smoke = load_native_build_smoke()

    report = verify_native_build_smoke.build_report(
        attempt_android=True,
        attempt_ios=True,
        command_exists=lambda name: "",
        env={},
        platform_system="Linux",
    )

    assert report["passes"] is False
    assert report["android"]["build"]["checked"] is True
    assert report["android"]["build"]["canAttempt"] is False
    assert "java" in report["android"]["build"]["missing"]
    if not (Path("native/android/gradlew").exists()):
        assert "gradle" in report["android"]["build"]["missing"]
    assert "ANDROID_HOME or ANDROID_SDK_ROOT" in report["android"]["build"]["missing"]
    assert report["ios"]["build"]["checked"] is True
    assert report["ios"]["build"]["canAttempt"] is False
    assert "xcodebuild" in report["ios"]["build"]["missing"]
    assert "macOS/Darwin" in report["ios"]["build"]["missing"]
