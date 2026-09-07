import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "tools" / "verify_reference_visual_contract.py"


def _run_verifier(*args):
    completed = subprocess.run(
        [sys.executable, str(VERIFIER), *args],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    return json.loads(completed.stdout)


def test_reference_visual_contract_verifier_has_dry_run_mapping_for_all_products():
    assert VERIFIER.exists()

    report = _run_verifier("--json", "--dry-run")

    assert report["passes"] is True
    assert report["dryRun"] is True
    assert report["referenceRoot"] == "/mnt/d/Downloads/레퍼런스"
    assert report["viewports"]["mobile"] == {"width": 360, "height": 740}
    assert report["viewports"]["desktop"] == {"width": 1280, "height": 720}

    products = {item["product"]: item for item in report["products"]}
    assert set(products) == {"islam", "tcm", "simli"}
    assert products["islam"]["referenceFiles"] == ["이슬람 참조.html"]
    assert products["tcm"]["referenceFiles"] == ["한의학참조1.html", "한의학참조2.html"]
    assert products["simli"]["referenceFiles"] == ["심리참조 이중 B · Therapeutic Aurora 사용.html"]

    assert "bg-pattern" in products["islam"]["requiredProductMarkers"]
    assert "query-frame" in products["islam"]["requiredProductMarkers"]
    assert "hanui" in products["tcm"]["requiredProductMarkers"]
    assert products["simli"]["referenceDesignLabel"] == "B · Therapeutic Aurora"
    assert "aurora-app" in products["simli"]["requiredProductMarkers"]


def test_reference_visual_contract_verifier_checks_reference_files_and_product_markers():
    text = VERIFIER.read_text(encoding="utf-8")

    for token in (
        "REFERENCE_ROOT",
        "ReferenceSpec",
        "referenceFilesExist",
        "productMarkersPresent",
        "이슬람 참조.html",
        "한의학참조1.html",
        "한의학참조2.html",
        "심리참조 이중 B · Therapeutic Aurora 사용.html",
        "referenceDesignLabel",
        "bg-pattern",
        "query-frame",
        "aurora-app",
    ):
        assert token in text


def test_reference_visual_contract_verifier_can_write_artifact(tmp_path):
    artifact = tmp_path / "reference-visual-contract.json"

    report = _run_verifier("--json", "--dry-run", "--output", str(artifact))

    assert artifact.exists()
    assert json.loads(artifact.read_text(encoding="utf-8")) == report
    assert report["passes"] is True
