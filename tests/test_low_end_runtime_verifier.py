import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "tools" / "verify_low_end_runtime.py"


def _run_verifier(*args):
    completed = subprocess.run(
        [sys.executable, str(VERIFIER), *args],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    return json.loads(completed.stdout)


def test_low_end_runtime_verifier_reports_js_dom_storage_and_safety_budgets():
    assert VERIFIER.exists()

    report = _run_verifier("--json")

    assert report["deviceProfile"]["name"] == "third-world-legacy-phone"
    assert report["network"]["bps"] == 1_000_000
    assert report["passes"] is True
    assert set(report["products"]) == {"islam", "tcm", "simli"}
    assert report["sharedRuntime"]["passes"] is True
    assert report["sharedRuntime"]["localChatStore"]["maxStoredSessions"] <= 24
    assert report["sharedRuntime"]["localChatStore"]["maxResultSources"] <= 18
    assert report["sharedRuntime"]["offlineOutbox"] is True
    assert report["sharedRuntime"]["anonymousSessionToken"] is True
    assert report["sharedRuntime"]["progressFallback"] is True
    assert report["sharedRuntime"]["jobCancel"] is True
    assert report["sharedRuntime"]["forbiddenApis"]["passes"] is True

    for product, item in report["products"].items():
        assert item["passes"] is True, product
        assert item["runtimeJsBytes"] <= item["budgets"]["runtimeJsBytes"]
        assert item["staticHtmlTags"] <= item["budgets"]["staticHtmlTags"]
        assert item["estimatedParseMs"] <= item["budgets"]["estimatedParseMs"]
        assert item["sourceWindow"]["bounded"] is True
        assert item["sourceWindow"]["incrementalContext"] is True
        assert item["chatRuntime"]["jobEvents"] is True
        assert item["chatRuntime"]["jobProgress"] is True
        assert item["chatRuntime"]["jobCancel"] is True
        assert item["chatRuntime"]["storedSessions"] is True
        assert item["routeSafety"]["localOnly"] is True
        assert item["routeSafety"]["noDataImages"] is True


def test_low_end_runtime_verifier_can_write_artifact(tmp_path):
    artifact = tmp_path / "low-end-runtime-report.json"

    report = _run_verifier("--json", "--output", str(artifact))

    assert artifact.exists()
    assert json.loads(artifact.read_text(encoding="utf-8")) == report
    assert report["passes"] is True
