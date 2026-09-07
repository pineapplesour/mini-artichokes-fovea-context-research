import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "tools" / "verify_browser_runtime_routes.py"


def _run_verifier(*args):
    completed = subprocess.run(
        [sys.executable, str(VERIFIER), *args],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    return json.loads(completed.stdout)


def test_browser_runtime_verifier_has_dry_run_contract_for_all_routes():
    assert VERIFIER.exists()

    report = _run_verifier("--json", "--dry-run")

    assert report["passes"] is True
    assert report["dryRun"] is True
    assert report["deviceProfile"]["cpuThrottlingRate"] == 4
    assert report["network"]["bps"] == 1_000_000
    assert report["browser"]["executablePath"] == "/usr/local/bin/chromium-headless-playwright"
    assert report["budgets"]["domContentLoadedMs"] <= 3500
    assert report["budgets"]["jsHeapUsedBytes"] <= 18_000_000
    assert report["viewports"]["mobile"] == {"width": 360, "height": 740}
    assert report["viewports"]["desktop"] == {"width": 1280, "height": 720}

    routes = report["routes"]
    assert len(routes) == 18
    assert {(item["product"], item["routeKind"], item["viewport"]) for item in routes} >= {
        ("islam", "landing", "mobile"),
        ("islam", "chat", "mobile"),
        ("tcm", "landing", "desktop"),
        ("tcm", "chat", "desktop"),
        ("tcm", "tcm-vertical", "mobile"),
        ("simli", "landing", "mobile"),
        ("simli", "chat", "desktop"),
    }
    urls = {(item["product"], item["routeKind"], item["viewport"]): item["url"] for item in routes}
    assert urls[("islam", "landing", "mobile")].endswith("/islam-bayyinah.html")
    assert urls[("islam", "chat", "desktop")].endswith("/islam-bayyinah-chat.html?q=browser%20runtime%20smoke")


def test_browser_runtime_verifier_uses_real_chromium_throttle_heap_and_console_gates():
    text = VERIFIER.read_text(encoding="utf-8")

    for token in (
        "sync_playwright",
        "chromium-headless-playwright",
        "Emulation.setCPUThrottlingRate",
        "Network.emulateNetworkConditions",
        "Performance.getMetrics",
        "console",
        "page_errors",
        "JSHeapUsedSize",
        "domContentLoadedEventEnd",
        "scrollWidth",
        "innerWidth",
    ):
        assert token in text


def test_browser_runtime_verifier_can_write_artifact(tmp_path):
    artifact = tmp_path / "browser-runtime-report.json"

    report = _run_verifier("--json", "--dry-run", "--output", str(artifact))

    assert artifact.exists()
    assert json.loads(artifact.read_text(encoding="utf-8")) == report
    assert report["passes"] is True
