import json
import importlib.util
from pathlib import Path


def _load_comparator():
    path = Path("tools/compare_selector_probe_variants.py")
    spec = importlib.util.spec_from_file_location("compare_selector_probe_variants", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _write_probe(path: Path, *, elapsed: float, kinds: dict[str, int], ids: list[str]) -> None:
    path.write_text(
        json.dumps(
            {
                "passes": True,
                "elapsedSec": elapsed,
                "candidateCount": 1200,
                "selectedCount": 100,
                "selectedSourceKinds": kinds,
                "selectedIds": ids,
            }
        ),
        encoding="utf-8",
    )


def _write_probe_payload(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_selector_probe_comparator_flags_speed_gain_with_kind_and_overlap_drift(tmp_path):
    baseline = tmp_path / "baseline.json"
    variant = tmp_path / "variant.json"
    _write_probe(
        baseline,
        elapsed=190.0,
        kinds={"classic_canon": 60, "materia_medica": 5, "classic_authoritative": 30, "formulary": 5},
        ids=[f"doc-{index:03d}" for index in range(100)],
    )
    _write_probe(
        variant,
        elapsed=70.0,
        kinds={"classic_canon": 90, "classic_authoritative": 10},
        ids=[f"doc-{index:03d}" for index in range(20)] + [f"new-{index:03d}" for index in range(80)],
    )

    comparator = _load_comparator()
    report = comparator.build_report(
        baseline_path=baseline,
        variant_path=variant,
        min_overlap=40,
        require_baseline_kinds=True,
    )

    assert report["passes"] is False
    assert report["metrics"]["elapsedDeltaSec"] == -120.0
    assert report["checks"]["fasterOrEqual"]["passes"] is True
    assert report["checks"]["selectedOverlap"]["passes"] is False
    assert report["checks"]["baselineKindsPreserved"]["passes"] is False
    assert "materia_medica" in report["checks"]["baselineKindsPreserved"]["missingKinds"]


def test_selector_probe_comparator_passes_when_speed_and_evidence_shape_hold(tmp_path):
    baseline = tmp_path / "baseline.json"
    variant = tmp_path / "variant.json"
    ids = [f"doc-{index:03d}" for index in range(100)]
    _write_probe(
        baseline,
        elapsed=190.0,
        kinds={"classic_canon": 60, "materia_medica": 5, "classic_authoritative": 30, "formulary": 5},
        ids=ids,
    )
    _write_probe(
        variant,
        elapsed=100.0,
        kinds={"classic_canon": 55, "materia_medica": 6, "classic_authoritative": 34, "formulary": 5},
        ids=ids[:80] + [f"new-{index:03d}" for index in range(20)],
    )

    comparator = _load_comparator()
    report = comparator.build_report(
        baseline_path=baseline,
        variant_path=variant,
        min_overlap=40,
        require_baseline_kinds=True,
    )

    assert report["passes"] is True
    assert report["checks"]["selectedOverlap"]["overlapCount"] == 80


def test_selector_probe_comparator_can_reject_cache_hot_variant_speed_evidence(tmp_path):
    baseline = tmp_path / "baseline.json"
    variant = tmp_path / "variant.json"
    ids = [f"doc-{index:03d}" for index in range(100)]
    kinds = {"classic_canon": 60, "materia_medica": 5, "classic_authoritative": 30, "formulary": 5}
    _write_probe_payload(
        baseline,
        {
            "passes": True,
            "elapsedSec": 190.0,
            "candidateCount": 1200,
            "selectedCount": 100,
            "selectorBatchCacheHits": 0,
            "selectorBatchCacheMisses": 12,
            "selectedSourceKinds": kinds,
            "selectedIds": ids,
        },
    )
    _write_probe_payload(
        variant,
        {
            "passes": True,
            "elapsedSec": 0.1,
            "candidateCount": 1200,
            "selectedCount": 100,
            "selectorBatchCacheHits": 12,
            "selectorBatchCacheMisses": 0,
            "selectedSourceKinds": kinds,
            "selectedIds": ids,
        },
    )

    comparator = _load_comparator()
    report = comparator.build_report(
        baseline_path=baseline,
        variant_path=variant,
        min_overlap=40,
        require_baseline_kinds=True,
        require_variant_cold_selector=True,
    )

    assert report["passes"] is False
    assert report["checks"]["fasterOrEqual"]["passes"] is True
    assert report["checks"]["variantColdSelector"]["passes"] is False
    assert report["checks"]["variantColdSelector"]["cacheHits"] == 12
    assert report["checks"]["variantColdSelector"]["cacheMisses"] == 0


def test_selector_probe_comparator_can_require_same_selector_shape(tmp_path):
    baseline = tmp_path / "baseline.json"
    variant = tmp_path / "variant.json"
    ids = [f"doc-{index:03d}" for index in range(100)]
    kinds = {"classic_canon": 60, "materia_medica": 5, "classic_authoritative": 30, "formulary": 5}
    _write_probe_payload(
        baseline,
        {
            "passes": True,
            "elapsedSec": 190.0,
            "candidateCount": 1200,
            "selectedCount": 100,
            "selectorBatchSize": 100,
            "selectorBatchWorkers": 6,
            "selectorCandidateLimit": 1200,
            "selectorAuditedCandidateCount": 1200,
            "selectedSourceKinds": kinds,
            "selectedIds": ids,
        },
    )
    _write_probe_payload(
        variant,
        {
            "passes": True,
            "elapsedSec": 80.0,
            "candidateCount": 1200,
            "selectedCount": 100,
            "selectorBatchSize": 50,
            "selectorBatchWorkers": 12,
            "selectorCandidateLimit": 1200,
            "selectorAuditedCandidateCount": 1200,
            "selectedSourceKinds": kinds,
            "selectedIds": ids,
        },
    )

    comparator = _load_comparator()
    report = comparator.build_report(
        baseline_path=baseline,
        variant_path=variant,
        min_overlap=40,
        require_baseline_kinds=True,
        require_same_selector_shape=True,
    )

    assert report["passes"] is False
    assert report["checks"]["fasterOrEqual"]["passes"] is True
    assert report["checks"]["selectorShapePreserved"]["passes"] is False
    assert report["checks"]["selectorShapePreserved"]["baseline"]["selectorBatchSize"] == 100
    assert report["checks"]["selectorShapePreserved"]["variant"]["selectorBatchSize"] == 50
    assert set(report["checks"]["selectorShapePreserved"]["changedFields"]) == {
        "selectorBatchSize",
        "selectorBatchWorkers",
    }


def test_selector_probe_comparator_rejects_missing_selector_shape_when_required(tmp_path):
    baseline = tmp_path / "baseline.json"
    variant = tmp_path / "variant.json"
    ids = [f"doc-{index:03d}" for index in range(100)]
    kinds = {"classic_canon": 60, "materia_medica": 5, "classic_authoritative": 30, "formulary": 5}
    _write_probe(
        baseline,
        elapsed=190.0,
        kinds=kinds,
        ids=ids,
    )
    _write_probe(
        variant,
        elapsed=80.0,
        kinds=kinds,
        ids=ids,
    )

    comparator = _load_comparator()
    report = comparator.build_report(
        baseline_path=baseline,
        variant_path=variant,
        min_overlap=40,
        require_baseline_kinds=True,
        require_same_selector_shape=True,
    )

    assert report["passes"] is False
    assert report["checks"]["selectorShapePreserved"]["passes"] is False
    assert report["checks"]["selectorShapePreserved"]["missingFields"] == [
        "selectorBatchSize",
        "selectorBatchWorkers",
        "selectorCandidateLimit",
        "selectorAuditedCandidateCount",
    ]


def test_selector_probe_comparator_can_require_best_known_speed_floor(tmp_path):
    slow_baseline = tmp_path / "slow-baseline.json"
    speed_floor = tmp_path / "best-known-baseline.json"
    variant = tmp_path / "variant.json"
    ids = [f"doc-{index:03d}" for index in range(100)]
    kinds = {"classic_canon": 60, "materia_medica": 5, "classic_authoritative": 30, "formulary": 5}
    shape = {
        "selectorBatchSize": 100,
        "selectorBatchWorkers": 6,
        "selectorCandidateLimit": 1200,
        "selectorAuditedCandidateCount": 1200,
    }
    _write_probe_payload(
        slow_baseline,
        {
            "passes": True,
            "elapsedSec": 210.0,
            "candidateCount": 1200,
            "selectedCount": 100,
            "selectedSourceKinds": kinds,
            "selectedIds": ids,
            **shape,
        },
    )
    _write_probe_payload(
        speed_floor,
        {
            "passes": True,
            "elapsedSec": 100.0,
            "candidateCount": 1200,
            "selectedCount": 100,
            "selectedSourceKinds": kinds,
            "selectedIds": ids,
        },
    )
    _write_probe_payload(
        variant,
        {
            "passes": True,
            "elapsedSec": 150.0,
            "candidateCount": 1200,
            "selectedCount": 100,
            "selectedSourceKinds": kinds,
            "selectedIds": ids,
            **shape,
        },
    )

    comparator = _load_comparator()
    report = comparator.build_report(
        baseline_path=slow_baseline,
        variant_path=variant,
        min_overlap=40,
        require_baseline_kinds=True,
        require_same_selector_shape=True,
        speed_floor_path=speed_floor,
    )

    assert report["passes"] is False
    assert report["checks"]["fasterOrEqual"]["passes"] is True
    assert report["checks"]["speedFloor"]["passes"] is False
    assert report["checks"]["speedFloor"]["baselineElapsedSec"] == 210.0
    assert report["checks"]["speedFloor"]["floorElapsedSec"] == 100.0
    assert report["checks"]["speedFloor"]["effectiveFloorSec"] == 100.0
    assert report["checks"]["speedFloor"]["variantElapsedSec"] == 150.0


def test_selector_probe_comparator_can_require_clean_selector_without_recovery(tmp_path):
    baseline = tmp_path / "baseline.json"
    variant = tmp_path / "variant.json"
    ids = [f"doc-{index:03d}" for index in range(100)]
    kinds = {"classic_canon": 60, "materia_medica": 5, "classic_authoritative": 30, "formulary": 5}
    _write_probe_payload(
        baseline,
        {
            "passes": True,
            "elapsedSec": 190.0,
            "candidateCount": 1200,
            "selectedCount": 100,
            "selectorLocalRecoveryCount": 0,
            "overTimeoutCount": 0,
            "selectedSourceKinds": kinds,
            "selectedIds": ids,
        },
    )
    _write_probe_payload(
        variant,
        {
            "passes": True,
            "elapsedSec": 120.0,
            "candidateCount": 1200,
            "selectedCount": 100,
            "selectorLocalRecoveryCount": 1,
            "overTimeoutCount": 2,
            "selectedSourceKinds": kinds,
            "selectedIds": ids,
        },
    )

    comparator = _load_comparator()
    report = comparator.build_report(
        baseline_path=baseline,
        variant_path=variant,
        min_overlap=40,
        require_baseline_kinds=True,
        require_clean_selector=True,
    )

    assert report["passes"] is False
    assert report["checks"]["fasterOrEqual"]["passes"] is True
    assert report["checks"]["cleanSelector"]["passes"] is False
    assert report["checks"]["cleanSelector"]["selectorLocalRecoveryCount"] == 1
    assert report["checks"]["cleanSelector"]["overTimeoutCount"] == 2


def test_selector_probe_comparator_reports_prompt_size_delta(tmp_path):
    baseline = tmp_path / "baseline.json"
    variant = tmp_path / "variant.json"
    ids = [f"doc-{index:03d}" for index in range(100)]
    kinds = {"scripture": 15, "commentary": 85}
    _write_probe_payload(
        baseline,
        {
            "passes": True,
            "elapsedSec": 210.0,
            "candidateCount": 1200,
            "selectedCount": 100,
            "selectedSourceKinds": kinds,
            "selectedIds": ids,
            "maxPromptBytes": 59000,
            "maxPrimaryPromptBytes": 59000,
            "maxRecoveryPromptBytes": 15000,
        },
    )
    _write_probe_payload(
        variant,
        {
            "passes": True,
            "elapsedSec": 120.0,
            "candidateCount": 1200,
            "selectedCount": 100,
            "selectedSourceKinds": kinds,
            "selectedIds": ids,
            "maxPromptBytes": 41000,
            "maxPrimaryPromptBytes": 41000,
            "maxRecoveryPromptBytes": 12000,
        },
    )

    comparator = _load_comparator()
    report = comparator.build_report(
        baseline_path=baseline,
        variant_path=variant,
        min_overlap=40,
        require_baseline_kinds=True,
    )

    assert report["metrics"]["maxPromptBytesDelta"] == -18000
    assert report["checks"]["promptSize"]["passes"] is True
    assert report["checks"]["promptSize"]["baselineMaxPromptBytes"] == 59000
    assert report["checks"]["promptSize"]["variantMaxPromptBytes"] == 41000


def test_selector_probe_comparator_recovers_prompt_size_from_slowest_batches(tmp_path):
    baseline = tmp_path / "baseline.json"
    variant = tmp_path / "variant.json"
    ids = [f"doc-{index:03d}" for index in range(100)]
    kinds = {"scripture": 15, "commentary": 85}
    _write_probe_payload(
        baseline,
        {
            "passes": True,
            "elapsedSec": 210.0,
            "candidateCount": 1200,
            "selectedCount": 100,
            "selectedSourceKinds": kinds,
            "selectedIds": ids,
            "selectorSlowest": [
                {"maxPromptBytes": 59000, "primaryMaxPromptBytes": 59000, "recoveryMaxPromptBytes": 15000},
                {"maxPromptBytes": 58000, "primaryMaxPromptBytes": 58000, "recoveryMaxPromptBytes": 0},
            ],
        },
    )
    _write_probe_payload(
        variant,
        {
            "passes": True,
            "elapsedSec": 120.0,
            "candidateCount": 1200,
            "selectedCount": 100,
            "selectedSourceKinds": kinds,
            "selectedIds": ids,
            "selectorSlowest": [
                {"maxPromptBytes": 41000, "primaryMaxPromptBytes": 41000, "recoveryMaxPromptBytes": 12000},
            ],
        },
    )

    comparator = _load_comparator()
    report = comparator.build_report(
        baseline_path=baseline,
        variant_path=variant,
        min_overlap=40,
        require_baseline_kinds=True,
        require_prompt_reduction=True,
    )

    assert report["passes"] is True
    assert report["checks"]["promptSize"]["measured"] is True
    assert report["metrics"]["maxPromptBytesDelta"] == -18000
