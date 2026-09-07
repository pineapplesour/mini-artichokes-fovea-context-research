import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "tools" / "verify_reference_screenshots.py"


def _run_verifier(*args):
    completed = subprocess.run(
        [sys.executable, str(VERIFIER), *args],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    return json.loads(completed.stdout)


def test_reference_screenshot_verifier_has_dry_run_contract():
    assert VERIFIER.exists()

    report = _run_verifier("--json", "--dry-run")

    assert report["passes"] is True
    assert report["dryRun"] is True
    assert report["browser"]["executablePath"] == "/usr/local/bin/chromium-headless-playwright"
    assert report["referenceRoot"] == "/mnt/d/Downloads/레퍼런스"
    assert report["viewports"]["mobile"] == {"width": 360, "height": 740}
    assert report["viewports"]["desktop"] == {"width": 1280, "height": 720}
    assert report["contract"]["scope"] == "browser screenshot drift gate"
    assert report["contract"]["limits"] == "Pixel metrics are drift evidence, not a pixel-perfect approval."

    products = {item["product"]: item for item in report["products"]}
    assert set(products) == {"islam", "tcm", "simli"}
    assert products["islam"]["comparisonMode"] == "selector-pixel"
    assert products["tcm"]["comparisonMode"] == "selector-pixel"
    assert products["simli"]["comparisonMode"] == "artboard-pixel"
    assert ".hero" in products["islam"]["selectors"]
    assert ".ask-card" in products["tcm"]["selectors"]
    assert "B · Therapeutic Aurora" in products["simli"]["referenceAnchors"]
    assert products["simli"]["referenceArtboardAnchor"] == "B · Therapeutic Aurora"
    assert products["simli"]["referenceArtboardAncestorDepth"] == 3
    assert products["simli"]["artboardCompareViewports"] == ["desktop"]
    assert products["simli"]["thresholds"]["meanAbsoluteError"] <= 24
    assert products["simli"]["thresholds"]["pixelDifferenceRatio"] <= 0.32
    assert products["islam"]["thresholds"]["meanAbsoluteError"] <= 40
    assert products["islam"]["thresholds"]["pixelDifferenceRatio"] <= 0.4
    assert products["tcm"]["thresholds"]["meanAbsoluteError"] <= 40
    assert products["tcm"]["thresholds"]["pixelDifferenceRatio"] <= 0.26
    assert len(report["routes"]) == 6


def test_reference_screenshot_verifier_uses_real_browser_screenshots_and_pil_metrics():
    text = VERIFIER.read_text(encoding="utf-8")

    for token in (
        "sync_playwright",
        "page.screenshot",
        "locator.screenshot",
        "Image.open",
        "ImageChops",
        "ImageStat",
        "meanAbsoluteError",
        "rmsError",
        "pixelDifferenceRatio",
        "perceptualHashDistance",
        "screenshot_anchor_ancestor",
        "crop_image_to_size",
        "referenceArtboardAnchor",
        "as_uri",
    ):
        assert token in text


def test_reference_screenshot_verifier_can_write_artifact(tmp_path):
    artifact = tmp_path / "reference-screenshots.json"

    report = _run_verifier("--json", "--dry-run", "--output", str(artifact))

    assert artifact.exists()
    assert json.loads(artifact.read_text(encoding="utf-8")) == report
    assert report["passes"] is True
