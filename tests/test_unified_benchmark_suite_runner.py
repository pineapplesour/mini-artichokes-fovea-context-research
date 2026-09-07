import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from shared_platform.products import ProductProfile
from tools import run_benchmark_suite


def _write_json(path: Path, value: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _mcq_public(benchmark_id: str = "mcq.tcm.test") -> dict:
    return {
        "schemaVersion": 1,
        "benchmarkId": benchmark_id,
        "taskType": "mcq",
        "product": "tcm",
        "cases": [{"id": "q1", "prompt": "문제\n1. 갑\n2. 을"}],
    }


def _mcq_private(benchmark_id: str = "mcq.tcm.test") -> dict:
    return {
        "schemaVersion": 1,
        "benchmarkId": benchmark_id,
        "taskType": "mcq",
        "answers": [{"caseId": "q1", "correctOptionId": "1"}],
        "retrievalTargets": [
            {
                "caseId": "q1",
                "targets": [{"sourceId": "d1"}],
                "rankRules": {"primaryMustAppearWithin": 5},
            }
        ],
    }


def _make_tcm_profile(db_path: Path) -> ProductProfile:
    return ProductProfile(
        key="tcm",
        name="TCM Test",
        db_path=db_path,
        db_shape="precedents",
        languages=("ko",),
        default_language="ko",
        theme="tcm",
        safety_notice="test",
    )


def _make_lawkey_profile(db_path: Path) -> ProductProfile:
    return ProductProfile(
        key="lawkey",
        name="Lawkey Test",
        db_path=db_path,
        db_shape="precedents",
        languages=("ko",),
        default_language="ko",
        theme="lawkey",
        safety_notice="test",
    )


def _make_buddhist_profile(db_path: Path) -> ProductProfile:
    return ProductProfile(
        key="buddhist",
        name="Buddhist Test",
        db_path=db_path,
        db_shape="passages",
        languages=("ko",),
        default_language="ko",
        theme="buddhist",
        safety_notice="test",
    )


def test_suite_skips_unready_engine_without_calling_runner(tmp_path, monkeypatch):
    benchmarks_dir = tmp_path / "benchmarks"
    public_path = benchmarks_dir / "mcq_tcm_test.public.json"
    private_path = benchmarks_dir / "mcq_tcm_test.private.json"
    _write_json(public_path, _mcq_public())
    _write_json(private_path, _mcq_private())
    db_path = tmp_path / "tiny.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE precedents (canonical_id TEXT PRIMARY KEY, full_text TEXT)")
    conn.execute("INSERT INTO precedents VALUES ('one', 'tiny')")
    conn.commit()
    conn.close()

    def fail_engine(**_kwargs):
        raise AssertionError("engine runner must not execute when readiness fails")

    monkeypatch.setattr(run_benchmark_suite.mcq_runner, "run_engine_manifest", fail_engine)
    report = run_benchmark_suite.run_suite(
        benchmarks_dir=benchmarks_dir,
        output_dir=tmp_path / "out",
        benchmark_ids=["mcq.tcm.test"],
        products={"tcm": _make_tcm_profile(db_path)},
        execute=True,
        run_engine=True,
        run_direct=False,
        min_rows=10,
    )

    item = report["benchmarks"][0]
    assert item["readiness"]["readyForRetrievalBenchmark"] is False
    assert item["modes"]["engine"]["status"] == "skipped_unready"
    assert item["modes"]["engine"]["reason"] == "readiness_failed"
    assert item["modes"]["engine"]["claimable"] is False
    assert "readiness_failed" in item["modes"]["engine"]["claimBlockers"]
    assert report["claimable"] is False


def test_suite_runs_ready_mcq_engine_scores_and_audits(tmp_path, monkeypatch):
    benchmarks_dir = tmp_path / "benchmarks"
    public_path = benchmarks_dir / "mcq_tcm_test.public.json"
    private_path = benchmarks_dir / "mcq_tcm_test.private.json"
    _write_json(public_path, _mcq_public())
    _write_json(private_path, _mcq_private())
    db_path = tmp_path / "ready.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE precedents (canonical_id TEXT PRIMARY KEY, full_text TEXT)")
    conn.executemany("INSERT INTO precedents VALUES (?, ?)", [(f"d{i}", "text") for i in range(3)])
    conn.commit()
    conn.close()

    def fake_engine(*, output_dir: Path, **_kwargs):
        results = output_dir / "results"
        results.mkdir(parents=True, exist_ok=True)
        _write_json(
            results / "q1.json",
            {
                "id": "q1",
                "caseId": "q1",
                "prediction": "1",
                "selectorStatus": "completed",
                "selectedCount": 1,
                "citedClaimCards": [{"id": "c1"}],
                "contextPacketCount": 1,
                "contextPacketIds": ["S1:d1"],
            },
        )
        return {
            "total": {"total": 1, "predicted": 1, "errors": 0},
            "mode": "engine",
            "modelMetadata": {"provider": "fixture_provider", "model": "gemma-shared", "decoding": {}},
        }

    def fake_direct(*, output_dir: Path, **_kwargs):
        results = output_dir / "results"
        results.mkdir(parents=True, exist_ok=True)
        _write_json(results / "q1.json", {"id": "q1", "caseId": "q1", "prediction": "1"})
        return {
            "total": {"total": 1, "predicted": 1, "errors": 0},
            "mode": "direct",
            "modelMetadata": {"provider": "fixture_provider", "model": "gemma-shared", "decoding": {}},
        }

    monkeypatch.setattr(run_benchmark_suite.mcq_runner, "run_engine_manifest", fake_engine)
    monkeypatch.setattr(run_benchmark_suite.mcq_runner, "run_direct_manifest", fake_direct)
    report = run_benchmark_suite.run_suite(
        benchmarks_dir=benchmarks_dir,
        output_dir=tmp_path / "out",
        benchmark_ids=["mcq.tcm.test"],
        products={"tcm": _make_tcm_profile(db_path)},
        execute=True,
        run_engine=True,
        run_direct=True,
        min_rows=2,
    )

    engine = report["benchmarks"][0]["modes"]["engine"]
    direct = report["benchmarks"][0]["modes"]["direct"]
    assert engine["status"] == "completed"
    assert engine["score"]["correct"] == 1
    assert engine["score"]["accuracy"] == 1.0
    assert engine["audit"]["credibleImprovementCount"] == 0
    assert direct["status"] == "completed"
    assert direct["score"]["accuracy"] == 1.0
    assert engine["claimable"] is True
    assert engine["claimBlockers"] == []
    assert report["claimable"] is True
    assert (tmp_path / "out" / "suite_report.json").exists()


def test_suite_runs_short_answer_through_same_direct_and_engine_path(tmp_path, monkeypatch):
    benchmark_id = "short_answer.buddhist.test"
    benchmarks_dir = tmp_path / "benchmarks"
    _write_json(
        benchmarks_dir / "short_answer_buddhist_test.public.json",
        {
            "schemaVersion": 1,
            "benchmarkId": benchmark_id,
            "taskType": "short_answer",
            "product": "buddhist",
            "cases": [{"id": "q1", "prompt": "보살의 뜻은 무엇인가?"}],
        },
    )
    _write_json(
        benchmarks_dir / "short_answer_buddhist_test.private.json",
        {
            "schemaVersion": 1,
            "benchmarkId": benchmark_id,
            "answers": [{"caseId": "q1", "correctAnswer": "보살(菩薩)"}],
            "scoring": {"comparison": "exact_unicode_string"},
        },
    )
    db_path = tmp_path / "buddhist.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE passages (passage_id TEXT PRIMARY KEY, text TEXT)")
    conn.executemany("INSERT INTO passages VALUES (?, ?)", [(f"p{i}", "불교 문헌") for i in range(3)])
    conn.commit()
    conn.close()

    def fake_engine(*, output_dir: Path, **_kwargs):
        results = output_dir / "results"
        results.mkdir(parents=True, exist_ok=True)
        _write_json(
            results / "q1.json",
            {
                "id": "q1",
                "caseId": "q1",
                "prediction": "보살(菩薩)",
                "selectorStatus": "completed",
                "selectedCount": 1,
                "citedClaimCards": [{"id": "c1"}],
                "contextPacketCount": 1,
                "contextPacketIds": ["S1:p1"],
            },
        )
        return {
            "total": {"total": 1, "predicted": 1, "errors": 0},
            "mode": "engine",
            "modelMetadata": {"provider": "fixture_provider", "model": "shared-model", "decoding": {}},
        }

    def fake_direct(*, output_dir: Path, **_kwargs):
        results = output_dir / "results"
        results.mkdir(parents=True, exist_ok=True)
        _write_json(results / "q1.json", {"id": "q1", "caseId": "q1", "prediction": "보살(菩薩)"})
        return {
            "total": {"total": 1, "predicted": 1, "errors": 0},
            "mode": "direct",
            "modelMetadata": {"provider": "fixture_provider", "model": "shared-model", "decoding": {}},
        }

    monkeypatch.setattr(run_benchmark_suite.mcq_runner, "run_engine_manifest", fake_engine)
    monkeypatch.setattr(run_benchmark_suite.mcq_runner, "run_direct_manifest", fake_direct)
    report = run_benchmark_suite.run_suite(
        benchmarks_dir=benchmarks_dir,
        output_dir=tmp_path / "out",
        benchmark_ids=[benchmark_id],
        products={"buddhist": _make_buddhist_profile(db_path)},
        execute=True,
        run_engine=True,
        run_direct=True,
        min_rows=2,
    )

    benchmark = report["benchmarks"][0]
    assert benchmark["readiness"]["taskType"] == "short_answer"
    assert benchmark["modes"]["direct"]["status"] == "completed"
    assert benchmark["modes"]["direct"]["score"]["accuracy"] == 1.0
    assert benchmark["modes"]["engine"]["status"] == "completed"
    assert benchmark["modes"]["engine"]["score"]["accuracy"] == 1.0
    assert "missing_same_model_direct_baseline" not in benchmark["modes"]["engine"]["claimBlockers"]


def _valid_selector_ablation_report(*, strict_improvement: bool = True) -> dict:
    arm_common = {
        "candidateSetDigest": "sha256:candidates",
        "selectorProvider": "fixture_provider",
        "selectorModel": "fixture-model",
        "selectorDecoding": {},
        "selectorFallback": False,
        "writerRan": False,
        "selectedEvidenceCount": 1,
    }
    target_ids = ["target:d1"]
    raw_covered = [] if strict_improvement else target_ids
    context_covered = target_ids
    return {
        "schemaVersion": "selector_ablation_v1",
        "ablationId": "raw_vs_context_packets_v1",
        "suite": {
            "targetManifestLocked": True,
            "targetsVisibleToEngine": False,
        },
        "arms": ["raw", "context_packets_v1"],
        "cases": [
            {
                "caseId": "q1",
                "arms": {
                    "raw": {
                        **arm_common,
                        "selectorInputMode": "raw",
                        "selectedBackingEvidenceIds": ["d2"] if strict_improvement else ["d1"],
                        "targetEval": {
                            "targetSpecPresent": True,
                            "targetHitSource": "selected_backing_evidence_only",
                            "pass": bool(raw_covered),
                            "score": 1.0 if raw_covered else 0.0,
                            "targetIds": target_ids,
                            "coveredTargetIds": raw_covered,
                            "missedTargetIds": [target_id for target_id in target_ids if target_id not in raw_covered],
                            "targetsTotal": len(target_ids),
                            "targetsPassed": len(raw_covered),
                        },
                    },
                    "context_packets_v1": {
                        **arm_common,
                        "selectorInputMode": "context_packets_v1",
                        "selectedBackingEvidenceIds": ["d1"],
                        "contextPacketCount": 1,
                        "contextPacketProvenanceCount": 1,
                        "targetEval": {
                            "targetSpecPresent": True,
                            "targetHitSource": "selected_backing_evidence_only",
                            "pass": True,
                            "score": 1.0,
                            "targetIds": target_ids,
                            "coveredTargetIds": context_covered,
                            "missedTargetIds": [],
                            "targetsTotal": len(target_ids),
                            "targetsPassed": len(context_covered),
                        },
                    },
                },
            }
        ],
    }


def test_suite_blocks_claim_when_required_selector_ablation_report_missing(tmp_path, monkeypatch):
    benchmarks_dir = tmp_path / "benchmarks"
    public_path = benchmarks_dir / "mcq_tcm_test.public.json"
    private_path = benchmarks_dir / "mcq_tcm_test.private.json"
    _write_json(public_path, _mcq_public())
    _write_json(private_path, _mcq_private())
    db_path = tmp_path / "ready.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE precedents (canonical_id TEXT PRIMARY KEY, full_text TEXT)")
    conn.executemany("INSERT INTO precedents VALUES (?, ?)", [(f"d{i}", "text") for i in range(3)])
    conn.commit()
    conn.close()

    def fake_engine(*, output_dir: Path, **_kwargs):
        results = output_dir / "results"
        results.mkdir(parents=True, exist_ok=True)
        _write_json(
            results / "q1.json",
            {
                "id": "q1",
                "caseId": "q1",
                "prediction": "1",
                "selectorStatus": "completed",
                "selectedCount": 1,
                "citedClaimCount": 1,
                "contextPacketCount": 1,
                "contextPacketIds": ["S1:d1"],
            },
        )
        return {
            "total": {"total": 1, "predicted": 1, "errors": 0},
            "mode": "engine",
            "modelMetadata": {"provider": "fixture_provider", "model": "gemma-shared", "decoding": {}},
        }

    def fake_direct(*, output_dir: Path, **_kwargs):
        results = output_dir / "results"
        results.mkdir(parents=True, exist_ok=True)
        _write_json(results / "q1.json", {"id": "q1", "caseId": "q1", "prediction": "1"})
        return {
            "total": {"total": 1, "predicted": 1, "errors": 0},
            "mode": "direct",
            "modelMetadata": {"provider": "fixture_provider", "model": "gemma-shared", "decoding": {}},
        }

    monkeypatch.setattr(run_benchmark_suite.mcq_runner, "run_engine_manifest", fake_engine)
    monkeypatch.setattr(run_benchmark_suite.mcq_runner, "run_direct_manifest", fake_direct)
    report = run_benchmark_suite.run_suite(
        benchmarks_dir=benchmarks_dir,
        output_dir=tmp_path / "out",
        benchmark_ids=["mcq.tcm.test"],
        products={"tcm": _make_tcm_profile(db_path)},
        execute=True,
        run_engine=True,
        run_direct=True,
        min_rows=2,
        require_selector_ablation=True,
    )

    assert report["benchmarks"][0]["modes"]["engine"]["claimable"] is True
    assert report["claimable"] is False
    assert "selector_ablation_missing" in report["claimBlockers"]


def test_suite_accepts_required_valid_selector_ablation_report(tmp_path, monkeypatch):
    benchmarks_dir = tmp_path / "benchmarks"
    public_path = benchmarks_dir / "mcq_tcm_test.public.json"
    private_path = benchmarks_dir / "mcq_tcm_test.private.json"
    _write_json(public_path, _mcq_public())
    _write_json(private_path, _mcq_private())
    output_dir = tmp_path / "out"
    _write_json(output_dir / "selector_ablation.raw_vs_context_packets_v1.json", _valid_selector_ablation_report())
    db_path = tmp_path / "ready.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE precedents (canonical_id TEXT PRIMARY KEY, full_text TEXT)")
    conn.executemany("INSERT INTO precedents VALUES (?, ?)", [(f"d{i}", "text") for i in range(3)])
    conn.commit()
    conn.close()

    def fake_engine(*, output_dir: Path, **_kwargs):
        results = output_dir / "results"
        results.mkdir(parents=True, exist_ok=True)
        _write_json(
            results / "q1.json",
            {
                "id": "q1",
                "caseId": "q1",
                "prediction": "1",
                "selectorStatus": "completed",
                "selectedCount": 1,
                "citedClaimCount": 1,
                "contextPacketCount": 1,
                "contextPacketIds": ["S1:d1"],
            },
        )
        return {
            "total": {"total": 1, "predicted": 1, "errors": 0},
            "mode": "engine",
            "modelMetadata": {"provider": "fixture_provider", "model": "gemma-shared", "decoding": {}},
        }

    def fake_direct(*, output_dir: Path, **_kwargs):
        results = output_dir / "results"
        results.mkdir(parents=True, exist_ok=True)
        _write_json(results / "q1.json", {"id": "q1", "caseId": "q1", "prediction": "1"})
        return {
            "total": {"total": 1, "predicted": 1, "errors": 0},
            "mode": "direct",
            "modelMetadata": {"provider": "fixture_provider", "model": "gemma-shared", "decoding": {}},
        }

    monkeypatch.setattr(run_benchmark_suite.mcq_runner, "run_engine_manifest", fake_engine)
    monkeypatch.setattr(run_benchmark_suite.mcq_runner, "run_direct_manifest", fake_direct)
    report = run_benchmark_suite.run_suite(
        benchmarks_dir=benchmarks_dir,
        output_dir=output_dir,
        benchmark_ids=["mcq.tcm.test"],
        products={"tcm": _make_tcm_profile(db_path)},
        execute=True,
        run_engine=True,
        run_direct=True,
        min_rows=2,
        require_selector_ablation=True,
    )

    assert report["selectorAblation"]["ablationReportValid"] is True
    assert report["selectorAblation"]["contextPacketRetrievalImprovementClaimable"] is True
    assert report["claimBlockers"] == []
    assert report["claimable"] is True


def test_suite_blocks_required_selector_ablation_without_improvement_claim(tmp_path, monkeypatch):
    benchmarks_dir = tmp_path / "benchmarks"
    public_path = benchmarks_dir / "mcq_tcm_test.public.json"
    private_path = benchmarks_dir / "mcq_tcm_test.private.json"
    _write_json(public_path, _mcq_public())
    _write_json(private_path, _mcq_private())
    output_dir = tmp_path / "out"
    _write_json(
        output_dir / "selector_ablation.raw_vs_context_packets_v1.json",
        _valid_selector_ablation_report(strict_improvement=False),
    )
    db_path = tmp_path / "ready.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE precedents (canonical_id TEXT PRIMARY KEY, full_text TEXT)")
    conn.executemany("INSERT INTO precedents VALUES (?, ?)", [(f"d{i}", "text") for i in range(3)])
    conn.commit()
    conn.close()

    def fake_engine(*, output_dir: Path, **_kwargs):
        results = output_dir / "results"
        results.mkdir(parents=True, exist_ok=True)
        _write_json(
            results / "q1.json",
            {
                "id": "q1",
                "caseId": "q1",
                "prediction": "1",
                "selectorStatus": "completed",
                "selectedCount": 1,
                "citedClaimCount": 1,
                "contextPacketCount": 1,
                "contextPacketIds": ["S1:d1"],
            },
        )
        return {
            "total": {"total": 1, "predicted": 1, "errors": 0},
            "mode": "engine",
            "modelMetadata": {"provider": "fixture_provider", "model": "gemma-shared", "decoding": {}},
        }

    def fake_direct(*, output_dir: Path, **_kwargs):
        results = output_dir / "results"
        results.mkdir(parents=True, exist_ok=True)
        _write_json(results / "q1.json", {"id": "q1", "caseId": "q1", "prediction": "1"})
        return {
            "total": {"total": 1, "predicted": 1, "errors": 0},
            "mode": "direct",
            "modelMetadata": {"provider": "fixture_provider", "model": "gemma-shared", "decoding": {}},
        }

    monkeypatch.setattr(run_benchmark_suite.mcq_runner, "run_engine_manifest", fake_engine)
    monkeypatch.setattr(run_benchmark_suite.mcq_runner, "run_direct_manifest", fake_direct)
    report = run_benchmark_suite.run_suite(
        benchmarks_dir=benchmarks_dir,
        output_dir=output_dir,
        benchmark_ids=["mcq.tcm.test"],
        products={"tcm": _make_tcm_profile(db_path)},
        execute=True,
        run_engine=True,
        run_direct=True,
        min_rows=2,
        require_selector_ablation=True,
    )

    assert report["selectorAblation"]["ablationReportValid"] is True
    assert report["selectorAblation"]["contextPacketRetrievalImprovementClaimable"] is False
    assert "selector_ablation_improvement_not_claimable" in report["claimBlockers"]
    assert "target_metric_saturated_no_strict_improvement" in report["claimBlockers"]
    assert report["claimable"] is False


def test_suite_blocks_mcq_engine_claim_when_retrieval_targets_missing(tmp_path, monkeypatch):
    benchmarks_dir = tmp_path / "benchmarks"
    public_path = benchmarks_dir / "mcq_tcm_test.public.json"
    private_path = benchmarks_dir / "mcq_tcm_test.private.json"
    private = _mcq_private()
    private.pop("retrievalTargets")
    _write_json(public_path, _mcq_public())
    _write_json(private_path, private)
    db_path = tmp_path / "ready.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE precedents (canonical_id TEXT PRIMARY KEY, full_text TEXT)")
    conn.executemany("INSERT INTO precedents VALUES (?, ?)", [(f"d{i}", "text") for i in range(3)])
    conn.commit()
    conn.close()

    def fake_engine(*, output_dir: Path, **_kwargs):
        results = output_dir / "results"
        results.mkdir(parents=True, exist_ok=True)
        _write_json(
            results / "q1.json",
            {
                "id": "q1",
                "caseId": "q1",
                "prediction": "1",
                "selectorStatus": "completed",
                "selectedCount": 1,
                "citedClaimCount": 1,
                "contextPacketCount": 1,
                "contextPacketIds": ["S1:d1"],
            },
        )
        return {
            "total": {"total": 1, "predicted": 1, "errors": 0},
            "mode": "engine",
            "modelMetadata": {"provider": "fixture_provider", "model": "gemma-shared", "decoding": {}},
        }

    def fake_direct(*, output_dir: Path, **_kwargs):
        results = output_dir / "results"
        results.mkdir(parents=True, exist_ok=True)
        _write_json(results / "q1.json", {"id": "q1", "caseId": "q1", "prediction": "1"})
        return {
            "total": {"total": 1, "predicted": 1, "errors": 0},
            "mode": "direct",
            "modelMetadata": {"provider": "fixture_provider", "model": "gemma-shared", "decoding": {}},
        }

    monkeypatch.setattr(run_benchmark_suite.mcq_runner, "run_engine_manifest", fake_engine)
    monkeypatch.setattr(run_benchmark_suite.mcq_runner, "run_direct_manifest", fake_direct)
    report = run_benchmark_suite.run_suite(
        benchmarks_dir=benchmarks_dir,
        output_dir=tmp_path / "out",
        benchmark_ids=["mcq.tcm.test"],
        products={"tcm": _make_tcm_profile(db_path)},
        execute=True,
        run_engine=True,
        run_direct=True,
        min_rows=2,
    )

    engine = report["benchmarks"][0]["modes"]["engine"]
    assert engine["claimable"] is False
    assert "mcq_retrieval_targets_missing" in engine["claimBlockers"]
    assert report["claimable"] is False


def test_suite_blocks_mcq_engine_claim_when_retrieval_targets_do_not_pass(tmp_path, monkeypatch):
    benchmarks_dir = tmp_path / "benchmarks"
    public_path = benchmarks_dir / "mcq_tcm_test.public.json"
    private_path = benchmarks_dir / "mcq_tcm_test.private.json"
    _write_json(public_path, _mcq_public())
    _write_json(private_path, _mcq_private())
    db_path = tmp_path / "ready.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE precedents (canonical_id TEXT PRIMARY KEY, full_text TEXT)")
    conn.executemany("INSERT INTO precedents VALUES (?, ?)", [(f"d{i}", "text") for i in range(3)])
    conn.commit()
    conn.close()

    def fake_engine(*, output_dir: Path, **_kwargs):
        results = output_dir / "results"
        results.mkdir(parents=True, exist_ok=True)
        _write_json(
            results / "q1.json",
            {
                "id": "q1",
                "caseId": "q1",
                "prediction": "1",
                "selectorStatus": "completed",
                "selectedCount": 1,
                "citedClaimCount": 1,
                "contextPacketCount": 1,
                "contextPacketIds": ["S1:wrong-doc"],
            },
        )
        return {
            "total": {"total": 1, "predicted": 1, "errors": 0},
            "mode": "engine",
            "modelMetadata": {"provider": "fixture_provider", "model": "gemma-shared", "decoding": {}},
        }

    def fake_direct(*, output_dir: Path, **_kwargs):
        results = output_dir / "results"
        results.mkdir(parents=True, exist_ok=True)
        _write_json(results / "q1.json", {"id": "q1", "caseId": "q1", "prediction": "1"})
        return {
            "total": {"total": 1, "predicted": 1, "errors": 0},
            "mode": "direct",
            "modelMetadata": {"provider": "fixture_provider", "model": "gemma-shared", "decoding": {}},
        }

    monkeypatch.setattr(run_benchmark_suite.mcq_runner, "run_engine_manifest", fake_engine)
    monkeypatch.setattr(run_benchmark_suite.mcq_runner, "run_direct_manifest", fake_direct)
    report = run_benchmark_suite.run_suite(
        benchmarks_dir=benchmarks_dir,
        output_dir=tmp_path / "out",
        benchmark_ids=["mcq.tcm.test"],
        products={"tcm": _make_tcm_profile(db_path)},
        execute=True,
        run_engine=True,
        run_direct=True,
        min_rows=2,
    )

    engine = report["benchmarks"][0]["modes"]["engine"]
    assert engine["score"]["retrieval"]["passed"] == 0
    assert engine["claimable"] is False
    assert "mcq_retrieval_zero_pass" in engine["claimBlockers"]
    assert report["claimable"] is False


def test_suite_blocks_mcq_engine_claim_when_retrieval_targets_are_option_text_only(tmp_path, monkeypatch):
    benchmarks_dir = tmp_path / "benchmarks"
    public_path = benchmarks_dir / "mcq_tcm_test.public.json"
    private_path = benchmarks_dir / "mcq_tcm_test.private.json"
    private = _mcq_private()
    private["retrievalTargets"] = [
        {
            "caseId": "q1",
            "targets": [{"textContains": "갑"}],
            "rankRules": {"primaryMustAppearWithin": 5},
        }
    ]
    _write_json(public_path, _mcq_public())
    _write_json(private_path, private)
    db_path = tmp_path / "ready.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE precedents (canonical_id TEXT PRIMARY KEY, full_text TEXT)")
    conn.executemany("INSERT INTO precedents VALUES (?, ?)", [(f"d{i}", "text") for i in range(3)])
    conn.commit()
    conn.close()

    def fake_engine(*, output_dir: Path, **_kwargs):
        results = output_dir / "results"
        results.mkdir(parents=True, exist_ok=True)
        _write_json(
            results / "q1.json",
            {
                "id": "q1",
                "caseId": "q1",
                "prediction": "1",
                "selectorStatus": "completed",
                "selectedCount": 1,
                "citedClaimCount": 1,
                "contextPacketCount": 1,
                "contextPacketIds": ["S1:d1"],
                "selectedEvidence": [{"rank": 1, "sourceId": "d1", "text": "갑 근거"}],
            },
        )
        return {
            "total": {"total": 1, "predicted": 1, "errors": 0},
            "mode": "engine",
            "modelMetadata": {"provider": "fixture_provider", "model": "gemma-shared", "decoding": {}},
        }

    def fake_direct(*, output_dir: Path, **_kwargs):
        results = output_dir / "results"
        results.mkdir(parents=True, exist_ok=True)
        _write_json(results / "q1.json", {"id": "q1", "caseId": "q1", "prediction": "1"})
        return {
            "total": {"total": 1, "predicted": 1, "errors": 0},
            "mode": "direct",
            "modelMetadata": {"provider": "fixture_provider", "model": "gemma-shared", "decoding": {}},
        }

    monkeypatch.setattr(run_benchmark_suite.mcq_runner, "run_engine_manifest", fake_engine)
    monkeypatch.setattr(run_benchmark_suite.mcq_runner, "run_direct_manifest", fake_direct)
    report = run_benchmark_suite.run_suite(
        benchmarks_dir=benchmarks_dir,
        output_dir=tmp_path / "out",
        benchmark_ids=["mcq.tcm.test"],
        products={"tcm": _make_tcm_profile(db_path)},
        execute=True,
        run_engine=True,
        run_direct=True,
        min_rows=2,
    )

    engine = report["benchmarks"][0]["modes"]["engine"]
    assert engine["score"]["retrieval"]["passed"] == 1
    assert engine["claimable"] is False
    assert "mcq_retrieval_target_policy_not_claimable" in engine["claimBlockers"]
    assert "text_target_option_only" in engine["claimBlockers"]
    assert report["claimable"] is False


@pytest.mark.parametrize(
    ("engine_metadata", "direct_metadata", "expected_blocker"),
    [
        (
            {"provider": "fixture_provider", "model": "gemma-engine", "decoding": {}},
            {"provider": "fixture_provider", "model": "gemma-direct", "decoding": {}},
            "direct_baseline_model_mismatch",
        ),
        (
            {"provider": "engine_provider", "model": "gemma-shared", "decoding": {}},
            {"provider": "direct_provider", "model": "gemma-shared", "decoding": {}},
            "direct_baseline_provider_mismatch",
        ),
        (
            {"provider": "fixture_provider", "model": "gemma-shared", "decoding": {"temperature": 0}},
            {"provider": "fixture_provider", "model": "gemma-shared", "decoding": {"temperature": 0.7}},
            "direct_baseline_decoding_mismatch",
        ),
    ],
)
def test_suite_blocks_mcq_engine_claim_when_direct_baseline_metadata_differs(
    tmp_path,
    monkeypatch,
    engine_metadata,
    direct_metadata,
    expected_blocker,
):
    benchmarks_dir = tmp_path / "benchmarks"
    public_path = benchmarks_dir / "mcq_tcm_test.public.json"
    private_path = benchmarks_dir / "mcq_tcm_test.private.json"
    _write_json(public_path, _mcq_public())
    _write_json(private_path, _mcq_private())
    db_path = tmp_path / "ready.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE precedents (canonical_id TEXT PRIMARY KEY, full_text TEXT)")
    conn.executemany("INSERT INTO precedents VALUES (?, ?)", [(f"d{i}", "text") for i in range(3)])
    conn.commit()
    conn.close()

    def fake_engine(*, output_dir: Path, **_kwargs):
        results = output_dir / "results"
        results.mkdir(parents=True, exist_ok=True)
        _write_json(
            results / "q1.json",
            {
                "id": "q1",
                "caseId": "q1",
                "prediction": "1",
                "selectorStatus": "completed",
                "selectedCount": 1,
                "citedClaimCount": 1,
                "contextPacketCount": 1,
                "contextPacketIds": ["S1:d1"],
            },
        )
        return {
            "total": {"total": 1, "predicted": 1, "errors": 0},
            "mode": "engine",
            "modelMetadata": engine_metadata,
        }

    def fake_direct(*, output_dir: Path, **_kwargs):
        results = output_dir / "results"
        results.mkdir(parents=True, exist_ok=True)
        _write_json(results / "q1.json", {"id": "q1", "caseId": "q1", "prediction": "1"})
        return {
            "total": {"total": 1, "predicted": 1, "errors": 0},
            "mode": "direct",
            "modelMetadata": direct_metadata,
        }

    monkeypatch.setattr(run_benchmark_suite.mcq_runner, "run_engine_manifest", fake_engine)
    monkeypatch.setattr(run_benchmark_suite.mcq_runner, "run_direct_manifest", fake_direct)
    report = run_benchmark_suite.run_suite(
        benchmarks_dir=benchmarks_dir,
        output_dir=tmp_path / "out",
        benchmark_ids=["mcq.tcm.test"],
        products={"tcm": _make_tcm_profile(db_path)},
        execute=True,
        run_engine=True,
        run_direct=True,
        min_rows=2,
    )

    engine = report["benchmarks"][0]["modes"]["engine"]
    direct = report["benchmarks"][0]["modes"]["direct"]
    assert direct["claimable"] is True
    assert engine["claimable"] is False
    assert engine["modelMetadata"] == engine_metadata
    assert direct["modelMetadata"] == direct_metadata
    assert expected_blocker in engine["claimBlockers"]
    assert report["claimable"] is False


def test_suite_blocks_mcq_engine_claim_without_direct_baseline(tmp_path, monkeypatch):
    benchmarks_dir = tmp_path / "benchmarks"
    public_path = benchmarks_dir / "mcq_tcm_test.public.json"
    private_path = benchmarks_dir / "mcq_tcm_test.private.json"
    _write_json(public_path, _mcq_public())
    _write_json(private_path, _mcq_private())
    db_path = tmp_path / "ready.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE precedents (canonical_id TEXT PRIMARY KEY, full_text TEXT)")
    conn.executemany("INSERT INTO precedents VALUES (?, ?)", [(f"d{i}", "text") for i in range(3)])
    conn.commit()
    conn.close()

    def fake_engine(*, output_dir: Path, **_kwargs):
        results = output_dir / "results"
        results.mkdir(parents=True, exist_ok=True)
        _write_json(
            results / "q1.json",
            {
                "id": "q1",
                "caseId": "q1",
                "prediction": "1",
                "selectorStatus": "completed",
                "selectedCount": 1,
                "citedClaimCards": [{"id": "c1"}],
            },
        )
        return {"total": {"total": 1, "predicted": 1, "errors": 0}, "mode": "engine"}

    monkeypatch.setattr(run_benchmark_suite.mcq_runner, "run_engine_manifest", fake_engine)
    report = run_benchmark_suite.run_suite(
        benchmarks_dir=benchmarks_dir,
        output_dir=tmp_path / "out",
        benchmark_ids=["mcq.tcm.test"],
        products={"tcm": _make_tcm_profile(db_path)},
        execute=True,
        run_engine=True,
        run_direct=False,
        min_rows=2,
    )

    engine = report["benchmarks"][0]["modes"]["engine"]
    assert engine["status"] == "completed"
    assert engine["score"]["accuracy"] == 1.0
    assert engine["claimable"] is False
    assert "missing_same_model_direct_baseline" in engine["claimBlockers"]
    assert report["claimable"] is False


def test_suite_blocks_legal_claim_when_retrieval_targets_do_not_pass(tmp_path, monkeypatch):
    benchmarks_dir = tmp_path / "benchmarks"
    public_path = benchmarks_dir / "legal_test.public.json"
    private_path = benchmarks_dir / "legal_test.private.json"
    _write_json(
        public_path,
        {
            "schemaVersion": 1,
            "benchmarkId": "legal.test",
            "taskType": "legal_retrieval_answer",
            "product": "lawkey",
            "cases": [
                {
                    "id": "case-a",
                    "language": "ko",
                    "variants": [{"id": "v1", "query": "유심 카카오톡 증거능력?"}],
                    "runtime": {"candidateLimit": 10},
                    "graderRef": "case-a",
                }
            ],
        },
    )
    _write_json(
        private_path,
        {
            "schemaVersion": 1,
            "benchmarkId": "legal.test",
            "taskType": "legal_retrieval_answer",
            "graders": [
                {
                    "graderId": "case-a",
                    "primaryTargets": [{"caseNumber": "2024구합65355"}],
                    "rankRules": {"primaryMustAppearWithin": 3},
                }
            ],
        },
    )
    db_path = tmp_path / "lawkey.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE precedents (canonical_id TEXT PRIMARY KEY, case_number TEXT, full_text TEXT)")
    conn.execute("INSERT INTO precedents VALUES ('target', '2024구합65355', 'target source')")
    conn.commit()
    conn.close()

    def fake_legal(*, output_dir: Path, **_kwargs):
        results = output_dir / "results"
        results.mkdir(parents=True, exist_ok=True)
        _write_json(
            results / "case-a__v1.json",
            {
                "id": "case-a__v1",
                "caseId": "case-a",
                "variantId": "v1",
                "graderId": "case-a",
                "answer": "2024구합65355 판례를 언급한 답변",
                "selectorStatus": "completed",
                "selectedCount": 1,
                "citedClaimCount": 1,
                "contextPacketCount": 1,
                "contextPacketIds": ["S1:wrong"],
                "selectedEvidence": [{"rank": 1, "caseNumber": "2024구합99999"}],
            },
        )
        return {"total": {"total": 1, "predicted": 1, "errors": 0}, "mode": "engine"}

    monkeypatch.setattr(run_benchmark_suite.legal_runner, "run_legal_manifest", fake_legal)
    report = run_benchmark_suite.run_suite(
        benchmarks_dir=benchmarks_dir,
        output_dir=tmp_path / "out",
        benchmark_ids=["legal.test"],
        products={"lawkey": _make_lawkey_profile(db_path)},
        execute=True,
        run_engine=True,
        run_direct=False,
    )

    engine = report["benchmarks"][0]["modes"]["engine"]
    assert engine["status"] == "completed"
    assert engine["score"]["retrieval"]["passed"] == 0
    assert engine["claimable"] is False
    assert "legal_retrieval_zero_pass" in engine["claimBlockers"]
    assert report["claimable"] is False


def test_suite_runs_legal_direct_answer_baseline_and_compares_model_metadata(tmp_path, monkeypatch):
    benchmarks_dir = tmp_path / "benchmarks"
    public_path = benchmarks_dir / "legal_test.public.json"
    private_path = benchmarks_dir / "legal_test.private.json"
    _write_json(
        public_path,
        {
            "schemaVersion": 1,
            "benchmarkId": "legal.test",
            "taskType": "legal_retrieval_answer",
            "product": "lawkey",
            "cases": [
                {
                    "id": "case-a",
                    "language": "ko",
                    "variants": [{"id": "v1", "query": "유심 카카오톡 증거능력?"}],
                    "runtime": {"candidateLimit": 10},
                    "graderRef": "case-a",
                }
            ],
        },
    )
    _write_json(
        private_path,
        {
            "schemaVersion": 1,
            "benchmarkId": "legal.test",
            "taskType": "legal_retrieval_answer",
            "graders": [
                {
                    "graderId": "case-a",
                    "primaryTargets": [{"caseNumber": "2024구합65355"}],
                    "rankRules": {"primaryMustAppearWithin": 3},
                    "answerRules": {"mustDiscuss": ["유심"]},
                }
            ],
        },
    )
    db_path = tmp_path / "lawkey.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE precedents (canonical_id TEXT PRIMARY KEY, case_number TEXT, full_text TEXT)")
    conn.execute("INSERT INTO precedents VALUES ('target', '2024구합65355', 'target source')")
    conn.commit()
    conn.close()
    model_metadata = {"provider": "fixture_provider", "model": "gemma-shared", "decoding": {"temperature": 0}}

    def fake_legal_engine(*, output_dir: Path, **_kwargs):
        results = output_dir / "results"
        results.mkdir(parents=True, exist_ok=True)
        _write_json(
            results / "case-a__v1.json",
            {
                "id": "case-a__v1",
                "caseId": "case-a",
                "variantId": "v1",
                "graderId": "case-a",
                "answer": "유심 쟁점은 2024구합65355 판례와 관련된다.",
                "selectorStatus": "completed",
                "selectedCount": 1,
                "citedClaimCount": 1,
                "contextPacketCount": 1,
                "contextPacketIds": ["S1:2024구합65355"],
                "selectedEvidence": [{"rank": 1, "caseNumber": "2024구합65355"}],
            },
        )
        return {"total": {"total": 1, "predicted": 1, "errors": 0}, "mode": "engine", "modelMetadata": model_metadata}

    def fake_legal_direct(*, output_dir: Path, **_kwargs):
        results = output_dir / "results"
        results.mkdir(parents=True, exist_ok=True)
        _write_json(
            results / "case-a__v1.json",
            {
                "id": "case-a__v1",
                "caseId": "case-a",
                "variantId": "v1",
                "graderId": "case-a",
                "mode": "direct",
                "answer": "직접 답변도 유심 쟁점을 언급한다.",
            },
        )
        return {"total": {"total": 1, "predicted": 1, "errors": 0}, "mode": "direct", "modelMetadata": model_metadata}

    monkeypatch.setattr(run_benchmark_suite.legal_runner, "run_legal_manifest", fake_legal_engine)
    monkeypatch.setattr(run_benchmark_suite.legal_runner, "run_direct_manifest", fake_legal_direct)
    report = run_benchmark_suite.run_suite(
        benchmarks_dir=benchmarks_dir,
        output_dir=tmp_path / "out",
        benchmark_ids=["legal.test"],
        products={"lawkey": _make_lawkey_profile(db_path)},
        execute=True,
        run_engine=True,
        run_direct=True,
    )

    modes = report["benchmarks"][0]["modes"]
    assert modes["direct"]["status"] == "completed"
    assert modes["direct"]["score"]["answer"]["passed"] == 1
    assert modes["direct"]["score"]["retrieval"]["passed"] == 0
    assert modes["direct"]["claimable"] is True
    assert modes["engine"]["claimable"] is True
    assert report["claimable"] is True


def test_suite_blocks_legal_engine_claim_without_direct_baseline(tmp_path, monkeypatch):
    benchmarks_dir = tmp_path / "benchmarks"
    public_path = benchmarks_dir / "legal_test.public.json"
    private_path = benchmarks_dir / "legal_test.private.json"
    _write_json(
        public_path,
        {
            "schemaVersion": 1,
            "benchmarkId": "legal.test",
            "taskType": "legal_retrieval_answer",
            "product": "lawkey",
            "cases": [
                {
                    "id": "case-a",
                    "language": "ko",
                    "variants": [{"id": "v1", "query": "유심 카카오톡 증거능력?"}],
                    "runtime": {"candidateLimit": 10},
                    "graderRef": "case-a",
                }
            ],
        },
    )
    _write_json(
        private_path,
        {
            "schemaVersion": 1,
            "benchmarkId": "legal.test",
            "taskType": "legal_retrieval_answer",
            "graders": [
                {
                    "graderId": "case-a",
                    "primaryTargets": [{"caseNumber": "2024구합65355"}],
                    "rankRules": {"primaryMustAppearWithin": 3},
                    "answerRules": {"mustDiscuss": ["유심"]},
                }
            ],
        },
    )
    db_path = tmp_path / "lawkey.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE precedents (canonical_id TEXT PRIMARY KEY, case_number TEXT, full_text TEXT)")
    conn.execute("INSERT INTO precedents VALUES ('target', '2024구합65355', 'target source')")
    conn.commit()
    conn.close()

    def fake_legal_engine(*, output_dir: Path, **_kwargs):
        results = output_dir / "results"
        results.mkdir(parents=True, exist_ok=True)
        _write_json(
            results / "case-a__v1.json",
            {
                "id": "case-a__v1",
                "caseId": "case-a",
                "variantId": "v1",
                "graderId": "case-a",
                "answer": "유심 쟁점은 2024구합65355 판례와 관련된다.",
                "selectorStatus": "completed",
                "selectedCount": 1,
                "citedClaimCount": 1,
                "contextPacketCount": 1,
                "contextPacketIds": ["S1:2024구합65355"],
                "selectedEvidence": [{"rank": 1, "caseNumber": "2024구합65355"}],
            },
        )
        return {
            "total": {"total": 1, "predicted": 1, "errors": 0},
            "mode": "engine",
            "modelMetadata": {"provider": "fixture_provider", "model": "gemma-shared", "decoding": {}},
        }

    monkeypatch.setattr(run_benchmark_suite.legal_runner, "run_legal_manifest", fake_legal_engine)
    report = run_benchmark_suite.run_suite(
        benchmarks_dir=benchmarks_dir,
        output_dir=tmp_path / "out",
        benchmark_ids=["legal.test"],
        products={"lawkey": _make_lawkey_profile(db_path)},
        execute=True,
        run_engine=True,
        run_direct=False,
    )

    engine = report["benchmarks"][0]["modes"]["engine"]
    assert engine["score"]["passed"] == 1
    assert engine["claimable"] is False
    assert "missing_same_model_direct_baseline" in engine["claimBlockers"]
    assert report["claimable"] is False


def test_suite_scores_only_selected_case_ids(tmp_path, monkeypatch):
    benchmarks_dir = tmp_path / "benchmarks"
    public_path = benchmarks_dir / "mcq_tcm_test.public.json"
    private_path = benchmarks_dir / "mcq_tcm_test.private.json"
    public = _mcq_public()
    public["cases"] = [
        {"id": "q1", "prompt": "문제\n1. 갑\n2. 을"},
        {"id": "q2", "prompt": "문제\n1. 갑\n2. 을"},
    ]
    private = _mcq_private()
    private["answers"] = [
        {"caseId": "q1", "correctOptionId": "1"},
        {"caseId": "q2", "correctOptionId": "2"},
    ]
    _write_json(public_path, public)
    _write_json(private_path, private)
    db_path = tmp_path / "ready.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE precedents (canonical_id TEXT PRIMARY KEY, full_text TEXT)")
    conn.executemany("INSERT INTO precedents VALUES (?, ?)", [(f"d{i}", "text") for i in range(3)])
    conn.commit()
    conn.close()

    def fake_engine(*, output_dir: Path, **_kwargs):
        results = output_dir / "results"
        results.mkdir(parents=True, exist_ok=True)
        _write_json(
            results / "q2.json",
            {
                "id": "q2",
                "caseId": "q2",
                "prediction": "2",
                "selectorStatus": "completed",
                "selectedCount": 1,
                "citedClaimCards": [{"id": "c1"}],
            },
        )
        return {"total": {"total": 1, "predicted": 1, "errors": 0}, "mode": "engine"}

    monkeypatch.setattr(run_benchmark_suite.mcq_runner, "run_engine_manifest", fake_engine)
    report = run_benchmark_suite.run_suite(
        benchmarks_dir=benchmarks_dir,
        output_dir=tmp_path / "out",
        benchmark_ids=["mcq.tcm.test"],
        products={"tcm": _make_tcm_profile(db_path)},
        execute=True,
        run_engine=True,
        run_direct=False,
        min_rows=2,
        case_ids=["q2"],
    )

    score = report["benchmarks"][0]["modes"]["engine"]["score"]
    assert score["total"] == 1
    assert score["predicted"] == 1
    assert score["correct"] == 1
    assert score["accuracy"] == 1.0
    assert score["invalidCaseIds"] == []
    assert report["benchmarks"][0]["modes"]["engine"]["claimable"] is False
    assert "subset_case_filter" in report["benchmarks"][0]["modes"]["engine"]["claimBlockers"]
    assert report["claimable"] is False


def test_suite_scores_only_artifacts_when_max_cases_limits_run(tmp_path, monkeypatch):
    benchmarks_dir = tmp_path / "benchmarks"
    public_path = benchmarks_dir / "mcq_tcm_test.public.json"
    private_path = benchmarks_dir / "mcq_tcm_test.private.json"
    public = _mcq_public()
    public["cases"] = [
        {"id": "q1", "prompt": "문제\n1. 갑\n2. 을"},
        {"id": "q2", "prompt": "문제\n1. 갑\n2. 을"},
    ]
    private = _mcq_private()
    private["answers"] = [
        {"caseId": "q1", "correctOptionId": "1"},
        {"caseId": "q2", "correctOptionId": "2"},
    ]
    _write_json(public_path, public)
    _write_json(private_path, private)
    db_path = tmp_path / "ready.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE precedents (canonical_id TEXT PRIMARY KEY, full_text TEXT)")
    conn.executemany("INSERT INTO precedents VALUES (?, ?)", [(f"d{i}", "text") for i in range(3)])
    conn.commit()
    conn.close()

    def fake_engine(*, output_dir: Path, **_kwargs):
        results = output_dir / "results"
        results.mkdir(parents=True, exist_ok=True)
        _write_json(
            results / "q1.json",
            {
                "id": "q1",
                "caseId": "q1",
                "prediction": "1",
                "selectorStatus": "completed",
                "selectedCount": 1,
                "citedClaimCards": [{"id": "c1"}],
            },
        )
        return {"total": {"total": 1, "predicted": 1, "errors": 0}, "mode": "engine"}

    monkeypatch.setattr(run_benchmark_suite.mcq_runner, "run_engine_manifest", fake_engine)
    report = run_benchmark_suite.run_suite(
        benchmarks_dir=benchmarks_dir,
        output_dir=tmp_path / "out",
        benchmark_ids=["mcq.tcm.test"],
        products={"tcm": _make_tcm_profile(db_path)},
        execute=True,
        run_engine=True,
        run_direct=False,
        min_rows=2,
        max_cases=1,
    )

    score = report["benchmarks"][0]["modes"]["engine"]["score"]
    assert score["total"] == 1
    assert score["predicted"] == 1
    assert score["correct"] == 1
    assert score["invalidCaseIds"] == []
    assert report["benchmarks"][0]["modes"]["engine"]["claimable"] is False
    assert "subset_max_cases" in report["benchmarks"][0]["modes"]["engine"]["claimBlockers"]


def test_suite_blocks_claim_when_completed_engine_writes_no_artifacts(tmp_path, monkeypatch):
    benchmarks_dir = tmp_path / "benchmarks"
    public_path = benchmarks_dir / "mcq_tcm_test.public.json"
    private_path = benchmarks_dir / "mcq_tcm_test.private.json"
    _write_json(public_path, _mcq_public())
    _write_json(private_path, _mcq_private())
    db_path = tmp_path / "ready.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE precedents (canonical_id TEXT PRIMARY KEY, full_text TEXT)")
    conn.executemany("INSERT INTO precedents VALUES (?, ?)", [(f"d{i}", "text") for i in range(3)])
    conn.commit()
    conn.close()

    def fake_engine(*, output_dir: Path, **_kwargs):
        (output_dir / "results").mkdir(parents=True, exist_ok=True)
        return {"total": {"total": 0, "predicted": 0, "errors": 0}, "mode": "engine"}

    monkeypatch.setattr(run_benchmark_suite.mcq_runner, "run_engine_manifest", fake_engine)
    report = run_benchmark_suite.run_suite(
        benchmarks_dir=benchmarks_dir,
        output_dir=tmp_path / "out",
        benchmark_ids=["mcq.tcm.test"],
        products={"tcm": _make_tcm_profile(db_path)},
        execute=True,
        run_engine=True,
        run_direct=False,
        min_rows=2,
    )

    engine = report["benchmarks"][0]["modes"]["engine"]
    assert engine["status"] == "completed"
    assert engine["claimable"] is False
    assert "runner_zero_cases" in engine["claimBlockers"]
    assert "audit_zero_artifacts" in engine["claimBlockers"]
    assert report["claimable"] is False


def test_suite_blocks_claim_when_engine_only_falls_back_without_selection(tmp_path, monkeypatch):
    benchmarks_dir = tmp_path / "benchmarks"
    public_path = benchmarks_dir / "mcq_tcm_test.public.json"
    private_path = benchmarks_dir / "mcq_tcm_test.private.json"
    _write_json(public_path, _mcq_public())
    _write_json(private_path, _mcq_private())
    db_path = tmp_path / "ready.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE precedents (canonical_id TEXT PRIMARY KEY, full_text TEXT)")
    conn.executemany("INSERT INTO precedents VALUES (?, ?)", [(f"d{i}", "text") for i in range(3)])
    conn.commit()
    conn.close()

    def fake_engine(*, output_dir: Path, **_kwargs):
        results = output_dir / "results"
        results.mkdir(parents=True, exist_ok=True)
        _write_json(
            results / "q1.json",
            {
                "id": "q1",
                "caseId": "q1",
                "prediction": "1",
                "selectorStatus": "fallback_no_selection",
                "selectedCount": 0,
                "citedClaimCards": [],
            },
        )
        return {"total": {"total": 1, "predicted": 1, "errors": 0}, "mode": "engine"}

    monkeypatch.setattr(run_benchmark_suite.mcq_runner, "run_engine_manifest", fake_engine)
    report = run_benchmark_suite.run_suite(
        benchmarks_dir=benchmarks_dir,
        output_dir=tmp_path / "out",
        benchmark_ids=["mcq.tcm.test"],
        products={"tcm": _make_tcm_profile(db_path)},
        execute=True,
        run_engine=True,
        run_direct=False,
        min_rows=2,
    )

    engine = report["benchmarks"][0]["modes"]["engine"]
    assert engine["status"] == "completed"
    assert engine["score"]["accuracy"] == 1.0
    assert engine["claimable"] is False
    assert "audit_no_completed_selectors" in engine["claimBlockers"]
    assert "audit_zero_selected_evidence" in engine["claimBlockers"]
    assert report["claimable"] is False


def test_suite_blocks_claim_when_engine_uses_direct_writer_fallback(tmp_path, monkeypatch):
    benchmarks_dir = tmp_path / "benchmarks"
    public_path = benchmarks_dir / "mcq_tcm_test.public.json"
    private_path = benchmarks_dir / "mcq_tcm_test.private.json"
    _write_json(public_path, _mcq_public())
    _write_json(private_path, _mcq_private())
    db_path = tmp_path / "ready.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE precedents (canonical_id TEXT PRIMARY KEY, full_text TEXT)")
    conn.executemany("INSERT INTO precedents VALUES (?, ?)", [(f"d{i}", "text") for i in range(3)])
    conn.commit()
    conn.close()

    def fake_engine(*, output_dir: Path, **_kwargs):
        results = output_dir / "results"
        results.mkdir(parents=True, exist_ok=True)
        _write_json(
            results / "q1.json",
            {
                "id": "q1",
                "caseId": "q1",
                "prediction": "1",
                "selectorStatus": "completed",
                "selectedCount": 1,
                "citedClaimCards": [{"id": "c1"}],
                "writerMode": "llm_writer_direct_after_writer_error",
            },
        )
        return {"total": {"total": 1, "predicted": 1, "errors": 0}, "mode": "engine"}

    monkeypatch.setattr(run_benchmark_suite.mcq_runner, "run_engine_manifest", fake_engine)
    report = run_benchmark_suite.run_suite(
        benchmarks_dir=benchmarks_dir,
        output_dir=tmp_path / "out",
        benchmark_ids=["mcq.tcm.test"],
        products={"tcm": _make_tcm_profile(db_path)},
        execute=True,
        run_engine=True,
        run_direct=False,
        min_rows=2,
    )

    engine = report["benchmarks"][0]["modes"]["engine"]
    assert engine["status"] == "completed"
    assert engine["score"]["accuracy"] == 1.0
    assert engine["claimable"] is False
    assert engine["audit"]["sourceGroundedArtifactCount"] == 0
    assert "audit_red_flag:directWriterFallback" in engine["claimBlockers"]
    assert report["claimable"] is False


def test_suite_blocks_claim_when_engine_lacks_context_packet_provenance(tmp_path, monkeypatch):
    benchmarks_dir = tmp_path / "benchmarks"
    public_path = benchmarks_dir / "mcq_tcm_test.public.json"
    private_path = benchmarks_dir / "mcq_tcm_test.private.json"
    _write_json(public_path, _mcq_public())
    _write_json(private_path, _mcq_private())
    db_path = tmp_path / "ready.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE precedents (canonical_id TEXT PRIMARY KEY, full_text TEXT)")
    conn.executemany("INSERT INTO precedents VALUES (?, ?)", [(f"d{i}", "text") for i in range(3)])
    conn.commit()
    conn.close()

    def fake_engine(*, output_dir: Path, **_kwargs):
        results = output_dir / "results"
        results.mkdir(parents=True, exist_ok=True)
        _write_json(
            results / "q1.json",
            {
                "id": "q1",
                "caseId": "q1",
                "prediction": "1",
                "selectorStatus": "completed",
                "selectedCount": 1,
                "citedClaimCount": 1,
                "writerMode": "llm_writer",
            },
        )
        return {"total": {"total": 1, "predicted": 1, "errors": 0}, "mode": "engine"}

    def fake_direct(*, output_dir: Path, **_kwargs):
        results = output_dir / "results"
        results.mkdir(parents=True, exist_ok=True)
        _write_json(results / "q1.json", {"id": "q1", "caseId": "q1", "prediction": "1"})
        return {"total": {"total": 1, "predicted": 1, "errors": 0}, "mode": "direct"}

    monkeypatch.setattr(run_benchmark_suite.mcq_runner, "run_engine_manifest", fake_engine)
    monkeypatch.setattr(run_benchmark_suite.mcq_runner, "run_direct_manifest", fake_direct)
    report = run_benchmark_suite.run_suite(
        benchmarks_dir=benchmarks_dir,
        output_dir=tmp_path / "out",
        benchmark_ids=["mcq.tcm.test"],
        products={"tcm": _make_tcm_profile(db_path)},
        execute=True,
        run_engine=True,
        run_direct=True,
        min_rows=2,
    )

    engine = report["benchmarks"][0]["modes"]["engine"]
    assert engine["status"] == "completed"
    assert engine["score"]["accuracy"] == 1.0
    assert engine["claimable"] is False
    assert "audit_no_retrieval_valid_artifacts" in engine["claimBlockers"]
    assert "audit_red_flag:missingContextPacketProvenance" in engine["claimBlockers"]
    assert report["claimable"] is False


def test_suite_can_run_direct_baseline_when_corpus_is_unready(tmp_path, monkeypatch):
    benchmarks_dir = tmp_path / "benchmarks"
    public_path = benchmarks_dir / "mcq_tcm_test.public.json"
    private_path = benchmarks_dir / "mcq_tcm_test.private.json"
    _write_json(public_path, _mcq_public())
    _write_json(private_path, _mcq_private())
    missing_db = tmp_path / "missing.sqlite3"

    def fake_direct(*, output_dir: Path, **_kwargs):
        results = output_dir / "results"
        results.mkdir(parents=True, exist_ok=True)
        _write_json(results / "q1.json", {"id": "q1", "caseId": "q1", "prediction": "1"})
        return {"total": {"total": 1, "predicted": 1, "errors": 0}, "mode": "direct"}

    monkeypatch.setattr(run_benchmark_suite.mcq_runner, "run_direct_manifest", fake_direct)
    report = run_benchmark_suite.run_suite(
        benchmarks_dir=benchmarks_dir,
        output_dir=tmp_path / "out",
        benchmark_ids=["mcq.tcm.test"],
        products={"tcm": _make_tcm_profile(missing_db)},
        execute=True,
        run_engine=False,
        run_direct=True,
        min_rows=10,
    )

    direct = report["benchmarks"][0]["modes"]["direct"]
    assert report["benchmarks"][0]["readiness"]["dbExists"] is False
    assert direct["status"] == "completed"
    assert direct["score"]["accuracy"] == 1.0
    assert direct["claimable"] is True


def test_suite_passes_direct_model_to_mcq_direct_runner(tmp_path, monkeypatch):
    benchmarks_dir = tmp_path / "benchmarks"
    public_path = benchmarks_dir / "mcq_tcm_test.public.json"
    private_path = benchmarks_dir / "mcq_tcm_test.private.json"
    _write_json(public_path, _mcq_public())
    _write_json(private_path, _mcq_private())
    missing_db = tmp_path / "missing.sqlite3"
    seen = {}

    def fake_direct(*, output_dir: Path, model: str = "", **_kwargs):
        seen["model"] = model
        results = output_dir / "results"
        results.mkdir(parents=True, exist_ok=True)
        _write_json(results / "q1.json", {"id": "q1", "caseId": "q1", "prediction": "1"})
        return {"total": {"total": 1, "predicted": 1, "errors": 0}, "mode": "direct"}

    monkeypatch.setattr(run_benchmark_suite.mcq_runner, "run_direct_manifest", fake_direct)
    report = run_benchmark_suite.run_suite(
        benchmarks_dir=benchmarks_dir,
        output_dir=tmp_path / "out",
        benchmark_ids=["mcq.tcm.test"],
        products={"tcm": _make_tcm_profile(missing_db)},
        execute=True,
        run_engine=False,
        run_direct=True,
        direct_model="gemma-direct-test",
    )

    assert report["benchmarks"][0]["modes"]["direct"]["status"] == "completed"
    assert report["parameters"]["directModel"] == "gemma-direct-test"
    assert seen["model"] == "gemma-direct-test"


def test_suite_cli_runs_from_tools_path(tmp_path):
    benchmarks_dir = tmp_path / "benchmarks"
    public_path = benchmarks_dir / "mcq_tcm_test.public.json"
    private_path = benchmarks_dir / "mcq_tcm_test.private.json"
    _write_json(public_path, _mcq_public())
    _write_json(private_path, _mcq_private())
    output_dir = tmp_path / "out"

    completed = subprocess.run(
        [
            sys.executable,
            "tools/run_benchmark_suite.py",
            "--benchmarks-dir",
            str(benchmarks_dir),
            "--output-dir",
            str(output_dir),
            "--benchmark-id",
            "mcq.tcm.test",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert (output_dir / "suite_report.json").exists()
