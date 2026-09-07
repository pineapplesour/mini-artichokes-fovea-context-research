import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "tools" / "verify_reference_geometry.py"


def _run_verifier(*args):
    completed = subprocess.run(
        [sys.executable, str(VERIFIER), *args],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    return json.loads(completed.stdout)


def test_reference_geometry_verifier_has_dry_run_contract_for_reference_routes():
    assert VERIFIER.exists()

    report = _run_verifier("--json", "--dry-run")

    assert report["passes"] is True
    assert report["dryRun"] is True
    assert report["browser"]["executablePath"] == "/usr/local/bin/chromium-headless-playwright"
    assert report["referenceRoot"] == "/mnt/d/Downloads/레퍼런스"
    assert report["viewports"]["mobile"] == {"width": 360, "height": 740}
    assert report["viewports"]["desktop"] == {"width": 1280, "height": 720}
    assert report["contract"]["scope"] == "browser geometry drift gate"

    products = {item["product"]: item for item in report["products"]}
    assert set(products) == {"islam", "tcm", "simli"}
    assert products["islam"]["referenceFiles"] == ["이슬람 참조.html"]
    assert products["tcm"]["referenceFiles"] == ["한의학참조1.html"]
    assert products["simli"]["referenceFiles"] == ["심리참조 이중 B · Therapeutic Aurora 사용.html"]

    assert ".query-frame" in products["islam"]["productSelectors"]
    assert ".ask-card" in products["tcm"]["productSelectors"]
    assert ".aurora-hero-card" in products["simli"]["productSelectors"]
    assert len(report["routes"]) == 6


def test_reference_geometry_verifier_uses_real_browser_bounding_boxes_and_reference_urls():
    text = VERIFIER.read_text(encoding="utf-8")

    for token in (
        "sync_playwright",
        "chromium-headless-playwright",
        "bounding_box",
        "find_text_box",
        "createTreeWalker",
        "as_uri",
        "referenceGeometry",
        "productGeometry",
        "noHorizontalOverflow",
        "viewportCoverage",
        "selectorOrder",
    ):
        assert token in text


def test_reference_geometry_verifier_can_write_artifact(tmp_path):
    artifact = tmp_path / "reference-geometry.json"

    report = _run_verifier("--json", "--dry-run", "--output", str(artifact))

    assert artifact.exists()
    assert json.loads(artifact.read_text(encoding="utf-8")) == report
    assert report["passes"] is True
