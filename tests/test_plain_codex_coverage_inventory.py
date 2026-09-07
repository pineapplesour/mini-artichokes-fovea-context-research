import json
from pathlib import Path

from tools.build_plain_codex_coverage_inventory import build_inventory


def test_checked_in_plain_codex_coverage_inventory_matches_current_artifacts():
    repo_root = Path(__file__).resolve().parents[1]
    path = repo_root / "docs/research/plain_codex_open_response_coverage_20260720.json"
    stored = json.loads(path.read_text(encoding="utf-8"))
    rebuilt = build_inventory(repo_root=repo_root, generated_at=stored["generatedAt"])

    assert stored == rebuilt
    assert stored["registry"]["registeredReadyCases"] == 473
    assert stored["registry"]["plainDirectCompletedReadyCases"] == 37
    assert stored["registry"]["allRegisteredReadyCasesExecuted"] is False
    assert stored["conclusion"]["allPlainCodexBenchmarksComplete"] is False
    assert stored["verifiedScores"]["lawReadyOne"]["passed"] == 1
    assert stored["verifiedScores"]["tcmReadySeventeen"]["passed"] == 14
    assert stored["verifiedScores"]["christianBibleQ001"]["passed"] == 1
    assert stored["verifiedScores"]["christianBibleQ002"]["passed"] == 1
    assert stored["verifiedScores"]["christianBibleQ003"]["passed"] == 1
    assert stored["scoreCaveats"]["christianBibleQ004"]["currentVerifiedPass"] is None
    assert stored["scoreCaveats"]["christianBibleQ004"]["currentDeterministicScore"]["unresolved"] == 1
    assert stored["separatePilots"]["suppliedRuleBusinessTax"]["passed"] == 5
