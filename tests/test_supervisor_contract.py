import json
import importlib.util
from pathlib import Path

import pytest


def load_supervisor_verifier():
    path = Path("tools/verify_supervisor_contract.py")
    if not path.exists():
        pytest.fail("tools/verify_supervisor_contract.py is missing")
    spec = importlib.util.spec_from_file_location("verify_supervisor_contract", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_supervisor_manifest_covers_split_apps_and_queue_worker():
    manifest_path = Path("ops/supervisor/beta6-services.json")

    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    services = {item["name"]: item for item in manifest["services"]}

    assert set(services) == {
        "beta6-islam",
        "beta6-tcm",
        "beta6-simli",
        "beta6-queue-worker",
    }
    assert services["beta6-islam"]["port"] == 8061
    assert services["beta6-tcm"]["port"] == 8062
    assert services["beta6-simli"]["port"] == 8063
    assert "apps.islam.server:app" in services["beta6-islam"]["execStart"]
    assert "apps.tcm.server:app" in services["beta6-tcm"]["execStart"]
    assert "apps.simli.server:app" in services["beta6-simli"]["execStart"]
    assert "tools/run_beta6_queue_worker.py" in services["beta6-queue-worker"]["execStart"]
    assert "--product islam" in services["beta6-queue-worker"]["execStart"]
    assert "--product tcm" in services["beta6-queue-worker"]["execStart"]
    assert "--product simli" in services["beta6-queue-worker"]["execStart"]
    assert all(item["restart"] == "always" for item in services.values())


def test_supervisor_systemd_units_match_manifest_commands():
    verify_supervisor_contract = load_supervisor_verifier()

    report = verify_supervisor_contract.build_report()

    assert report["passes"] is True
    assert report["serviceCount"] == 4
    assert report["environmentPass"] is True
    for service in report["services"]:
        assert service["passes"] is True
        assert service["unitExists"] is True
        assert service["execMatches"] is True
        assert service["restartMatches"] is True
        assert service["workingDirectoryMatches"] is True


def test_supervisor_readme_documents_user_install_without_root():
    readme = Path("ops/supervisor/README.md")

    assert readme.exists()
    text = readme.read_text(encoding="utf-8")
    assert "systemctl --user" in text
    assert "tools/smoke_supervisor_install.py --dry-run --json" in text
    assert "tools/smoke_supervisor_install.py --install --json" in text
    assert "beta6-islam.service" in text
    assert "beta6-queue-worker.service" in text
    assert "ops/supervisor/beta6.env" in text


def test_supervisor_uses_durable_queue_only_apps_with_worker_execution():
    env = Path("ops/supervisor/beta6.env").read_text(encoding="utf-8")
    worker_unit = Path("ops/supervisor/systemd/beta6-queue-worker.service").read_text(encoding="utf-8")

    assert "RELIGION_JOB_MAX_PENDING=10000" in env
    assert "RELIGION_LOCAL_JOB_EXECUTION_ENABLED=0" in env
    assert "Environment=RELIGION_LOCAL_JOB_EXECUTION_ENABLED=1" in worker_unit
