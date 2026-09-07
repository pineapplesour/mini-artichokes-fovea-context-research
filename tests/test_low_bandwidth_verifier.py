import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "tools" / "verify_low_bandwidth_routes.py"


def _run_verifier(*args):
    completed = subprocess.run(
        [sys.executable, str(VERIFIER), *args],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    return json.loads(completed.stdout)


def test_low_bandwidth_route_verifier_reports_mobile_desktop_matrix_and_budgets():
    assert VERIFIER.exists()

    report = _run_verifier("--json")

    assert report["network"]["bps"] == 1_000_000
    assert report["viewports"]["mobile"] == {"width": 360, "height": 740}
    assert report["viewports"]["desktop"] == {"width": 1280, "height": 720}
    assert report["serviceWorker"]["cacheName"] == "shared-platform-shell-reference-v47"
    assert report["serviceWorker"]["preCachesTtfFallback"] is False
    assert report["font"]["woff2Bytes"] < 80_000
    assert report["font"]["ttfFallbackBytes"] > report["font"]["woff2Bytes"]

    products = report["products"]
    assert set(products) == {"islam", "tcm", "simli"}
    assert products["islam"]["shellBytes"] < 220_000
    assert products["tcm"]["shellBytes"] < 95_000
    assert products["simli"]["shellBytes"] < 95_000

    for product, item in products.items():
        assert item["passes"] is True, product
        assert item["landing"]["path"] == f"/{product}.html"
        assert item["landing"]["exists"] is True
        assert item["chat"]["path"] == f"/{product}-chat.html"
        assert item["chat"]["exists"] is True
        assert item["estimated1MbpsSeconds"] <= item["budgetSeconds"]
        assert "mobile" in item["viewports"]
        assert "desktop" in item["viewports"]


def test_low_bandwidth_route_verifier_can_write_artifact(tmp_path):
    artifact = tmp_path / "low-bandwidth-report.json"

    report = _run_verifier("--json", "--output", str(artifact))

    assert artifact.exists()
    written = json.loads(artifact.read_text(encoding="utf-8"))
    assert written == report
    assert report["passes"] is True
