import hashlib
import json
from pathlib import Path

from tools.run_subject_batch_benchmark import BUILDER_ID, MODE


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_plain_codex_baseline_freeze_is_current_and_excludes_candidate_engines():
    repo_root = Path(__file__).resolve().parents[1]
    freeze = json.loads(
        (repo_root / "docs/research/plain_codex_baseline_freeze_20260720.json").read_text(
            encoding="utf-8"
        )
    )

    assert freeze["status"] == "frozen_before_further_solver_calls"
    assert freeze["solver"]["model"] == "gpt-5.6-luna"
    assert freeze["implementation"]["mode"] == MODE
    assert freeze["implementation"]["builderId"] == BUILDER_ID
    assert freeze["toolBoundary"]["customSkills"] is False
    assert freeze["toolBoundary"]["universalEngine"] is False
    assert freeze["toolBoundary"]["beta6Engine"] is False
    assert freeze["toolBoundary"]["readOnlySubjectDatabase"]["beta6FrontierEnabled"] is False
    assert freeze["toolBoundary"]["readOnlySubjectDatabase"]["allowedTools"] == [
        "search_domain_evidence",
        "get_domain_source",
    ]
    assert freeze["benchmarkInventory"]["plainDirectCompletedReadyCasesAtFreeze"] == 37
    assert freeze["deferredPostPlainArchitecture"]["topLevelDecisionMaker"] == "Codex"

    for artifact in freeze["implementation"]["files"]:
        assert _sha256(repo_root / artifact["path"]) == artifact["sha256"]
    inventory = freeze["benchmarkInventory"]
    assert _sha256(repo_root / inventory["registryPath"]) == inventory["registrySha256"]
    assert _sha256(repo_root / inventory["inventoryPath"]) == inventory["inventorySha256"]
    historical = freeze["historicalPlainBaselines"]
    assert _sha256(repo_root / historical["closurePath"]) == historical["closureSha256"]
    for name in ("legalTen", "tcmReadySeventeen"):
        item = historical[name]
        for suffix in ("summary", "score") if name == "legalTen" else ("score",):
            assert _sha256(repo_root / item[f"{suffix}Path"]) == item[f"{suffix}Sha256"]
