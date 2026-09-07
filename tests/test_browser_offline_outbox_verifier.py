import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "tools" / "verify_browser_offline_outbox.py"


def _run_verifier(*args):
    completed = subprocess.run(
        [sys.executable, str(VERIFIER), *args],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    return json.loads(completed.stdout)


def test_browser_offline_outbox_verifier_has_dry_run_contract_for_products():
    assert VERIFIER.exists()

    report = _run_verifier("--json", "--dry-run")

    assert report["passes"] is True
    assert report["dryRun"] is True
    assert report["deviceProfile"]["cpuThrottlingRate"] == 4
    assert report["network"]["bps"] == 1_000_000
    assert report["browser"]["executablePath"] == "/usr/local/bin/chromium-headless-playwright"
    assert set(report["products"]) == {"islam", "tcm", "simli"}
    for product, item in report["products"].items():
        assert item["passes"] is True, product
        assert item["chatRoute"].endswith(f"/{product}-chat.html")
        assert item["offlineQueued"] is True
        assert item["indexedDbOutbox"] is True
        assert item["onlineDrained"] is True
        assert item["activeSessionFollowed"] is True


def test_browser_offline_outbox_verifier_uses_real_route_abort_indexeddb_and_online_drain():
    text = VERIFIER.read_text(encoding="utf-8")

    for token in (
        "sync_playwright",
        "chromium-headless-playwright",
        "Emulation.setCPUThrottlingRate",
        "Network.emulateNetworkConditions",
        "route.abort",
        "indexedDB.open",
        "localStorage.getItem",
        "dispatchEvent(new Event(\"online\"))",
        "offlineQueued",
        "indexedDbOutbox",
        "activeSessionFollowed",
    ):
        assert token in text


def test_browser_offline_outbox_verifier_can_write_artifact(tmp_path):
    artifact = tmp_path / "offline-outbox-report.json"

    report = _run_verifier("--json", "--dry-run", "--output", str(artifact))

    assert artifact.exists()
    assert json.loads(artifact.read_text(encoding="utf-8")) == report
    assert report["passes"] is True
