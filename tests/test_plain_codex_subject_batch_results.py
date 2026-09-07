import hashlib
import json
from pathlib import Path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_plain_codex_subject_batch_results_are_bound_to_frozen_artifacts():
    repo_root = Path(__file__).resolve().parents[1]
    ledger = json.loads(
        (repo_root / "docs/research/plain_codex_subject_batch_results_20260720.json").read_text(
            encoding="utf-8"
        )
    )
    assert _sha256(repo_root / ledger["freeze"]["path"]) == ledger["freeze"]["sha256"]
    assert ledger["totals"]["cases"] == 229
    assert ledger["totals"]["passed"] == 147
    assert ledger["totals"]["failed"] == 68
    assert ledger["totals"]["unresolved"] == 14
    for run in ledger["runs"]:
        assert run["solver"]["beta6FrontierEnabled"] is False
        assert run["solver"]["skillsAvailable"] == 0
        assert run["score"]["allJudgeTracesClosedAndValid"] is True
        for path_key, hash_key in (
            ("summaryPath", "summarySha256"),
            ("receiptPath", "receiptSha256"),
        ):
            assert _sha256(repo_root / run["solver"][path_key]) == run["solver"][hash_key]
        for path_key, hash_key in (
            ("deterministicPath", "deterministicSha256"),
            ("semanticPath", "semanticSha256"),
        ):
            assert _sha256(repo_root / run["score"][path_key]) == run["score"][hash_key]
        invalid = run.get("invalidEvaluatorSelectionAudit")
        if invalid:
            assert invalid["solverOrJudgeCallsUsed"] == 0
            for path_key, hash_key in (
                ("deterministicPath", "deterministicSha256"),
                ("semanticPath", "semanticSha256"),
            ):
                assert _sha256(repo_root / invalid[path_key]) == invalid[hash_key]
        assert _sha256(repo_root / run["databaseAttestation"]["path"]) == run["databaseAttestation"]["sha256"]

    psych = ledger["subjectProgress"]["open_response.psych.mit_sangmyung.v2"]
    assert psych["status"] == "in_progress_after_quarantined_batch"
    assert psych["readyCases"] == 225
    assert psych["historicalItemIsolatedDirectCases"] == 2
    assert psych["postFreezeSolverExecutions"] == 16
    assert psych["postFreezeAccepted"] == 8
    assert psych["postFreezeQuarantined"] == 8
    assert psych["postFreezePassed"] == 2
    assert psych["postFreezeFailed"] == 6
    assert psych["postFreezeUnresolved"] == 8
    assert psych["remainingPostFreezeCases"] == 207
    law = ledger["subjectCompletions"]["open_response.lawkey.leet2026.v2"]
    assert law["status"] == "complete_current_ready_subset_remaining_cases_require_semantic_rewrite"
    assert law["totalConvertedCases"] == 70
    assert law["readyCases"] == 1
    assert law["needsSemanticRewriteCases"] == 69
    assert law["exactCurrentPromptExecutions"] == 1
    assert law["passed"] == 1
    assert law["failed"] == 0
    assert law["unresolved"] == 0
    law_completion_path = repo_root / law["completionPath"]
    assert _sha256(law_completion_path) == law["completionSha256"]
    law_completion = json.loads(law_completion_path.read_text(encoding="utf-8"))
    assert law_completion["promptIdentityAudit"]["exactCurrentPromptIdentityProven"] is True
    assert _sha256(repo_root / law_completion["solverArtifact"]["resultPath"]) == law_completion["solverArtifact"]["resultSha256"]
    assert _sha256(repo_root / law_completion["score"]["path"]) == law_completion["score"]["sha256"]
    islam = ledger["subjectCompletions"]["open_response.islam.cisi100.v2"]
    assert islam["status"] == "complete_with_separately_reported_historical_source_equivalent_cases"
    assert islam["readyCases"] == 69
    current_islam = islam["currentExactHarness"]
    assert current_islam["solverExecutions"] == 56
    assert current_islam["passed"] == 26
    assert current_islam["failed"] == 30
    assert current_islam["unresolved"] == 0
    assert current_islam["remainingCases"] == 0
    assert current_islam["failedCaseIds"] == [
        "islam-cisi-q004",
        "islam-cisi-q007",
        "islam-cisi-q009",
        "islam-cisi-q014",
        "islam-cisi-q016",
        "islam-cisi-q017",
        "islam-cisi-q018",
        "islam-cisi-q021",
        "islam-cisi-q030",
        "islam-cisi-q033",
        "islam-cisi-q035",
        "islam-cisi-q037",
        "islam-cisi-q042",
        "islam-cisi-q043",
        "islam-cisi-q046",
        "islam-cisi-q049",
        "islam-cisi-q053",
        "islam-cisi-q054",
        "islam-cisi-q058",
        "islam-cisi-q059",
        "islam-cisi-q060",
        "islam-cisi-q068",
        "islam-cisi-q071",
        "islam-cisi-q076",
        "islam-cisi-q077",
        "islam-cisi-q082",
        "islam-cisi-q083",
        "islam-cisi-q091",
        "islam-cisi-q095",
        "islam-cisi-q098",
    ]
    historical_islam = islam["historicalItemIsolatedDirect"]
    assert historical_islam["cases"] == 13
    assert historical_islam["passed"] == 6
    assert historical_islam["failed"] == 7
    assert historical_islam["unresolved"] == 0
    assert historical_islam["solverReruns"] == 0
    assert historical_islam["promptByteIdentityProven"] is False
    assert historical_islam["sourceCaseEquivalenceProven"] is True
    reconciliation_path = repo_root / historical_islam["reconciliationPath"]
    assert _sha256(reconciliation_path) == historical_islam["reconciliationSha256"]
    reconciliation = json.loads(reconciliation_path.read_text(encoding="utf-8"))
    assert reconciliation["identityDecision"]["eligibleForPostFreezeExactHarnessAggregate"] is False
    assert reconciliation["currentClosedConsensusScore"]["passed"] == 6
    assert reconciliation["currentClosedConsensusScore"]["failed"] == 7
    for group in reconciliation["scoreGroups"]:
        for path_key, hash_key in (
            ("deterministicPath", "deterministicSha256"),
            ("semanticPath", "semanticSha256"),
        ):
            assert _sha256(repo_root / group[path_key]) == group[hash_key]
    assert islam["combinedReferenceScore"]["cases"] == 69
    assert islam["combinedReferenceScore"]["passed"] == 32
    assert islam["combinedReferenceScore"]["failed"] == 37
    assert islam["combinedReferenceScore"]["provenanceMixed"] is True
    tcm = ledger["subjectCompletions"]["open_response.tcm.kuksiwon81.unique92.v2"]
    assert tcm["status"] == "complete_historical_source_equivalent_only"
    assert tcm["readyCases"] == 17
    assert tcm["exactCurrentPromptExecutions"] == 0
    historical_tcm = tcm["historicalItemIsolatedDirect"]
    assert historical_tcm["cases"] == 17
    assert historical_tcm["passed"] == 14
    assert historical_tcm["failed"] == 3
    assert historical_tcm["unresolved"] == 0
    assert historical_tcm["solverReruns"] == 0
    assert historical_tcm["promptByteIdentityProven"] is False
    assert historical_tcm["sourceCaseEquivalenceProven"] is True
    tcm_reconciliation_path = repo_root / historical_tcm["reconciliationPath"]
    assert _sha256(tcm_reconciliation_path) == historical_tcm["reconciliationSha256"]
    tcm_reconciliation = json.loads(tcm_reconciliation_path.read_text(encoding="utf-8"))
    assert tcm_reconciliation["currentClosedConsensusScore"]["passed"] == 14
    assert tcm_reconciliation["currentClosedConsensusScore"]["failed"] == 3
    for group in tcm_reconciliation["scoreGroups"]:
        for path_key, hash_key in (
            ("deterministicPath", "deterministicSha256"),
            ("semanticPath", "semanticSha256"),
        ):
            assert _sha256(repo_root / group[path_key]) == group[hash_key]
    provao = ledger["subjectCompletions"]["open_response.christian.provao2012.v2"]
    assert provao["status"] == "complete_with_quarantined_cases"
    assert provao["readyCases"] == 78
    assert provao["solverExecutions"] == 78
    assert provao["acceptedCases"] == 72
    assert provao["quarantinedCases"] == 6
    assert provao["passed"] == 44
    assert provao["failed"] == 28
    assert provao["unresolved"] == 6
    assert provao["failedCaseIds"] == [
        "christian-provao2012-q008",
        "christian-provao2012-q011",
        "christian-provao2012-q016",
        "christian-provao2012-q020",
        "christian-provao2012-q024",
        "christian-provao2012-q028",
        "christian-provao2012-q029",
        "christian-provao2012-q031",
        "christian-provao2012-q032",
        "christian-provao2012-q033",
        "christian-provao2012-q034",
        "christian-provao2012-q036",
        "christian-provao2012-q038",
        "christian-provao2012-q040",
        "christian-provao2012-q042",
        "christian-provao2012-q044",
        "christian-provao2012-q049",
        "christian-provao2012-q054",
        "christian-provao2012-q055",
        "christian-provao2012-q058",
        "christian-provao2012-q060",
        "christian-provao2012-q067",
        "christian-provao2012-q068",
        "christian-provao2012-q072",
        "christian-provao2012-q075",
        "christian-provao2012-q079",
        "christian-provao2012-q091",
        "christian-provao2012-q092",
    ]
    assert provao["quarantinedCaseIds"] == [
        "christian-provao2012-q093",
        "christian-provao2012-q094",
        "christian-provao2012-q095",
        "christian-provao2012-q096",
        "christian-provao2012-q097",
        "christian-provao2012-q098",
    ]
    assert provao["toolUsage"]["acceptedBatchWebEvents"] == 1
    assert provao["toolUsage"]["quarantinedBatchWebEvents"] == 3

    bible = ledger["subjectCompletions"]["open_response.christian.bible100.v2"]
    assert bible["status"] == "complete_with_historical_direct_reconciliation"
    assert bible["readyCases"] == bible["solverExecutions"] == 83
    assert bible["frozenSubjectBatchCases"] == 79
    assert bible["historicalItemIsolatedDirectCases"] == 4
    assert bible["passed"] == 79
    assert bible["failed"] == 4
    assert bible["unresolved"] == 0
    assert bible["failedCaseIds"] == [
        "christian-bible100-q021",
        "christian-bible100-q043",
        "christian-bible100-q045",
        "christian-bible100-q094",
    ]
    assert bible["solverCost"]["combinedTokens"] == 174352
    assert bible["evaluatorCost"]["combinedJudgeTokens"] == 213920
    for evidence in bible["historicalDirectEvidence"]:
        assert _sha256(repo_root / evidence["resultPath"]) == evidence["resultSha256"]
        assert _sha256(repo_root / evidence["scorePath"]) == evidence["scoreSha256"]
        assert evidence["verdict"] == "pass"
