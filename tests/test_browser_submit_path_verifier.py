import json
import importlib.util
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "tools" / "verify_browser_submit_path.py"


def _load_verifier_module():
    spec = importlib.util.spec_from_file_location("verify_browser_submit_path", VERIFIER)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _run_verifier(*args):
    completed = subprocess.run(
        [sys.executable, str(VERIFIER), *args],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    return json.loads(completed.stdout)


def test_browser_submit_path_verifier_has_dry_run_contract_for_real_user_path():
    assert VERIFIER.exists()

    report = _run_verifier("--json", "--dry-run", "--product", "islam")

    assert report["passes"] is True
    assert report["dryRun"] is True
    assert report["product"] == "islam"
    assert report["browser"]["executablePath"] == "/usr/local/bin/chromium-headless-playwright"
    assert report["deviceProfile"]["cpuThrottlingRate"] == 4
    assert report["network"]["bps"] == 1_000_000
    assert report["routes"]["landing"].endswith("/islam.html")
    assert report["routes"]["chat"].endswith("/islam-chat.html")
    assert report["checks"]["landingSubmit"]["passes"] is True
    assert report["checks"]["chatNavigation"]["passes"] is True
    assert report["checks"]["progressVisible"]["passes"] is True
    assert report["checks"]["finalRendered"]["passes"] is True
    assert report["checks"]["sourceWindow"]["passes"] is True
    assert report["checks"]["localChatStored"]["passes"] is True


def test_browser_submit_path_verifier_uses_real_browser_submit_result_and_source_window():
    text = VERIFIER.read_text(encoding="utf-8")

    for token in (
        "sync_playwright",
        "chromium-headless-playwright",
        "Network.emulateNetworkConditions",
        "Emulation.setCPUThrottlingRate",
        "[data-chat-entry]",
        "[data-query-input]",
        "[data-query-state]",
        "[data-evidence-list]",
        ".cite",
        ".source-open",
        ".source-window-mark",
        "localStorage.getItem",
        "/api/jobs/",
        "gemma-4-26b-a4b-it",
        "lawkey_gemini_generate_content",
    ):
        assert token in text


def test_browser_submit_path_verifier_reuses_browser_session_token_for_result_fetch():
    text = VERIFIER.read_text(encoding="utf-8")

    assert "beta6.sessionToken." in text
    assert "session_token" in text
    assert '"session": session_token' in text
    assert "verify_source_window(page, timeout_ms)" in text
    assert "fetch_result_from_session(clean_base" in text
    assert text.index("verify_source_window(page, timeout_ms)") < text.index("fetch_result_from_session(clean_base")


def test_browser_submit_path_verifier_accepts_product_landing_chat_input_selector():
    text = VERIFIER.read_text(encoding="utf-8")

    assert "[data-chat-entry] [data-chat-input]" in text
    assert "[data-chat-entry] [data-query-input]" in text


def test_browser_submit_path_verifier_samples_attached_progress_and_records_visibility():
    text = VERIFIER.read_text(encoding="utf-8")

    assert 'page.wait_for_selector("[data-query-state]", state="attached"' in text
    assert "stateVisible" in text


def test_browser_submit_path_verifier_can_write_artifact(tmp_path):
    artifact = tmp_path / "browser-submit-report.json"

    report = _run_verifier("--json", "--dry-run", "--product", "simli", "--output", str(artifact))

    assert artifact.exists()
    assert json.loads(artifact.read_text(encoding="utf-8")) == report
    assert report["passes"] is True
    assert report["product"] == "simli"


def test_browser_submit_path_verifier_compacts_beta6_stage_timings_for_budget_matrix():
    verifier = _load_verifier_module()

    compact = verifier.compact_stage_timings(
        {
            "stageTimingTotals": {
                "source_selection": 116.4524,
                "writer": "40.8216",
                "candidate_search": 3.8648,
            },
            "stageTimingTotalSec": 161.1388,
        }
    )

    assert compact["totalSec"] == 161.139
    assert compact["totals"]["source_selection"] == 116.452
    assert compact["slowest"][0] == {"stage": "source_selection", "seconds": 116.452}
