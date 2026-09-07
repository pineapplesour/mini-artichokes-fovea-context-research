import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDITOR = ROOT / "tools" / "audit_benchmark_artifacts.py"


def _write_artifact(path: Path, **fields):
    record = {
        "id": path.stem,
        "selectorStatus": "fallback_no_selection",
        "selectedCount": 30,
        "candidateCount": 30,
        "citedClaimCount": 0,
        "comparison": {"delta": "improved"},
    }
    record.update(fields)
    path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")


def test_artifact_auditor_flags_noisy_benchmark_lift(tmp_path):
    results = tmp_path / "results"
    results.mkdir()
    _write_artifact(results / "q001.json")
    _write_artifact(
        results / "q002.json",
        selectorStatus="completed",
        selectedCount=2,
        citedClaimCount=1,
        contextPacketCount=2,
        contextPacketIds=["S1:doc-a", "S2:doc-b"],
        comparison={"delta": "improved"},
    )
    _write_artifact(
        results / "q003.json",
        selectorStatus="fallback_low_coverage",
        selectedCount=0,
        citedClaimCount=0,
        comparison={"delta": "regressed"},
    )

    completed = subprocess.run(
        [sys.executable, str(AUDITOR), "--results-dir", str(results)],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    report = json.loads(completed.stdout)

    assert report["totalArtifacts"] == 3
    assert report["deltaCounts"]["improved"] == 2
    assert report["selectorStatusCounts"]["fallback_no_selection"] == 1
    assert report["credibleImprovementCount"] == 1
    assert report["noisyImprovementCount"] == 1
    assert report["redFlags"]["fallbackWithSelectedEvidence"]["caseIds"] == ["q001"]
    assert report["redFlags"]["selectedEvidenceWithoutCitations"]["caseIds"] == ["q001"]
    assert report["redFlags"]["improvementWithoutCompletedSelector"]["caseIds"] == ["q001"]
    assert report["redFlags"]["regressionWithoutCompletedSelector"]["caseIds"] == ["q003"]


def test_artifact_auditor_separates_source_grounded_from_fallback_and_no_evidence(tmp_path):
    results = tmp_path / "results"
    results.mkdir()
    _write_artifact(
        results / "q001.json",
        selectorStatus="fallback_selector_error",
        selectedCount=4,
        citedClaimCount=2,
        writerMode="llm_writer",
        comparison={"delta": "improved"},
    )
    _write_artifact(
        results / "q002.json",
        selectorStatus="completed",
        selectedCount=4,
        citedClaimCount=2,
        writerMode="llm_writer_direct_after_writer_error",
        comparison={"delta": "improved"},
    )
    _write_artifact(
        results / "q003.json",
        selectorStatus="completed",
        selectedCount=0,
        citedClaimCount=0,
        writerMode="llm_writer",
        comparison={"delta": "improved"},
    )
    _write_artifact(
        results / "q004.json",
        selectorStatus="completed",
        selectedCount=4,
        citedClaimCount=2,
        contextPacketCount=4,
        contextPacketIds=["S1:doc-a", "S2:doc-b", "S3:doc-c", "S4:doc-d"],
        writerMode="llm_writer",
        comparison={"delta": "improved"},
    )

    completed = subprocess.run(
        [sys.executable, str(AUDITOR), "--results-dir", str(results)],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    report = json.loads(completed.stdout)

    assert report["credibleImprovementCount"] == 1
    assert report["noisyImprovementCount"] == 3
    assert report["sourceGroundedArtifactCount"] == 1
    assert report["nonSourceGroundedArtifactCount"] == 3
    assert report["redFlags"]["improvementWithoutCompletedSelector"]["caseIds"] == ["q001"]
    assert report["redFlags"]["directWriterFallback"]["caseIds"] == ["q002"]
    assert report["redFlags"]["zeroSelectedEvidence"]["caseIds"] == ["q003"]
    assert report["redFlags"]["noCitedClaims"]["caseIds"] == ["q003"]


def test_artifact_auditor_requires_context_packet_provenance_for_source_grounding(tmp_path):
    results = tmp_path / "results"
    results.mkdir()
    _write_artifact(
        results / "q001.json",
        selectorStatus="completed",
        selectedCount=3,
        citedClaimCount=2,
        writerMode="llm_writer",
        comparison={"delta": "improved"},
    )
    _write_artifact(
        results / "q002.json",
        selectorStatus="completed",
        selectedCount=3,
        citedClaimCount=2,
        contextPacketCount=3,
        contextPacketIds=["S1:doc-a", "S2:doc-b", "S3:doc-c"],
        writerMode="llm_writer",
        comparison={"delta": "improved"},
    )

    completed = subprocess.run(
        [sys.executable, str(AUDITOR), "--results-dir", str(results)],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    report = json.loads(completed.stdout)

    assert report["sourceGroundedArtifactCount"] == 2
    assert report["nonSourceGroundedArtifactCount"] == 0
    assert report["retrievalValidArtifactCount"] == 1
    assert report["nonRetrievalValidArtifactCount"] == 1
    assert report["credibleImprovementCount"] == 1
    assert report["noisyImprovementCount"] == 1
    assert report["contextPacketCountBuckets"] == {"0": 1, "1-3": 1}
    assert report["redFlags"]["missingContextPacketProvenance"]["caseIds"] == ["q001"]


def test_artifact_auditor_can_write_report(tmp_path):
    results = tmp_path / "results"
    results.mkdir()
    output = tmp_path / "audit.json"
    _write_artifact(results / "q001.json")

    completed = subprocess.run(
        [sys.executable, str(AUDITOR), "--results-dir", str(results), "--output", str(output)],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    report = json.loads(completed.stdout)

    assert output.exists()
    assert json.loads(output.read_text(encoding="utf-8")) == report
