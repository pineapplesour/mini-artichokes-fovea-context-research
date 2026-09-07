import importlib.util
from pathlib import Path

import pytest


def load_install_smoke():
    path = Path("tools/smoke_supervisor_install.py")
    if not path.exists():
        pytest.fail("tools/smoke_supervisor_install.py is missing")
    spec = importlib.util.spec_from_file_location("smoke_supervisor_install", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_supervisor_install_smoke_dry_run_plans_all_units(tmp_path):
    smoke_supervisor_install = load_install_smoke()

    report = smoke_supervisor_install.build_report(
        dry_run=True,
        user_systemd_dir=tmp_path,
        check_systemd=False,
    )

    assert report["passes"] is True
    assert report["dryRun"] is True
    assert report["installRequested"] is False
    assert report["serviceCount"] == 4
    assert report["planPass"] is True
    assert len(report["installActions"]) == 4
    assert {action["service"] for action in report["installActions"]} == {
        "beta6-islam.service",
        "beta6-tcm.service",
        "beta6-simli.service",
        "beta6-queue-worker.service",
    }
    assert all(action["sourceExists"] for action in report["installActions"])
    assert all(str(tmp_path) in action["destination"] for action in report["installActions"])
    assert report["wouldRun"][0] == ["systemctl", "--user", "daemon-reload"]
    enable_command = report["wouldRun"][1]
    assert enable_command[:4] == ["systemctl", "--user", "enable", "--now"]
    assert "beta6-queue-worker.service" in enable_command


def test_supervisor_install_smoke_check_systemd_is_non_mutating(tmp_path):
    smoke_supervisor_install = load_install_smoke()
    calls = []

    def runner(command):
        calls.append(command)
        return smoke_supervisor_install.CommandResult(command=command, returncode=1, stdout="", stderr="no systemd")

    report = smoke_supervisor_install.build_report(
        dry_run=True,
        user_systemd_dir=tmp_path,
        check_systemd=True,
        runner=runner,
    )

    assert report["passes"] is False
    assert report["systemd"]["checked"] is True
    assert report["systemd"]["available"] is False
    assert calls == [["systemctl", "--user", "is-system-running"]]
    assert not tmp_path.joinpath("beta6-islam.service").exists()


def test_supervisor_install_smoke_install_copies_units_and_runs_commands(tmp_path):
    smoke_supervisor_install = load_install_smoke()
    calls = []

    def runner(command):
        calls.append(command)
        return smoke_supervisor_install.CommandResult(command=command, returncode=0, stdout="ok", stderr="")

    report = smoke_supervisor_install.build_report(
        dry_run=False,
        install=True,
        user_systemd_dir=tmp_path,
        check_systemd=False,
        runner=runner,
    )

    assert report["passes"] is True
    assert report["installRequested"] is True
    assert tmp_path.joinpath("beta6-islam.service").exists()
    assert tmp_path.joinpath("beta6-queue-worker.service").exists()
    assert calls[0] == ["systemctl", "--user", "daemon-reload"]
    assert calls[1][:4] == ["systemctl", "--user", "enable", "--now"]
    assert calls[2][:3] == ["systemctl", "--user", "status"]
    assert all(result["returncode"] == 0 for result in report["commands"])
