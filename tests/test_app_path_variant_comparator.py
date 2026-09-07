import json
import importlib.util
from pathlib import Path


def _load_comparator():
    path = Path("tools/compare_app_path_variants.py")
    spec = importlib.util.spec_from_file_location("compare_app_path_variants", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _write_app_path(
    path: Path,
    *,
    passes: bool,
    total: float,
    source_selection: float,
    wall: float | None = None,
    answer_chars: int = 3400,
    sources: int = 100,
    cited: int = 20,
) -> None:
    path.write_text(
        json.dumps(
            {
                "passes": passes,
                "stageTimings": {
                    "totalSec": total,
                    "totals": {"source_selection": source_selection},
                },
                "metrics": {
                    "answerChars": answer_chars,
                    "sourceCount": sources,
                    "citedClaimCount": cited,
                },
                "checks": {
                    "completed": {"passes": passes},
                    "sourceGrounding": {"passes": passes},
                    "answerDepth": {"passes": passes},
                    "noForcedCoveragePatch": {"passes": passes},
                },
                **({"wallElapsedSec": wall} if wall is not None else {}),
            }
        ),
        encoding="utf-8",
    )


def test_app_path_variant_comparator_rejects_selector_only_win_when_full_path_slower(tmp_path):
    baseline = tmp_path / "baseline.json"
    variant = tmp_path / "variant.json"
    _write_app_path(baseline, passes=True, total=285.569, source_selection=116.452, cited=15)
    _write_app_path(variant, passes=True, total=319.651, source_selection=208.929, cited=20)

    comparator = _load_comparator()
    report = comparator.build_report(baseline_path=baseline, variant_path=variant)

    assert report["passes"] is False
    assert report["checks"]["variantQualityPasses"]["passes"] is True
    assert report["checks"]["fasterTotal"]["passes"] is False
    assert report["checks"]["fasterSourceSelection"]["passes"] is False
    assert report["metrics"]["totalDeltaSec"] == 34.082


def test_app_path_variant_comparator_passes_only_when_quality_and_latency_hold(tmp_path):
    baseline = tmp_path / "baseline.json"
    variant = tmp_path / "variant.json"
    _write_app_path(baseline, passes=True, total=285.569, source_selection=116.452, cited=15)
    _write_app_path(variant, passes=True, total=240.0, source_selection=80.0, cited=18)

    comparator = _load_comparator()
    report = comparator.build_report(baseline_path=baseline, variant_path=variant)

    assert report["passes"] is True
    assert report["checks"]["fasterTotal"]["deltaSec"] == -45.569
    assert report["checks"]["qualityNotRegressed"]["passes"] is True


def test_app_path_variant_comparator_rejects_wall_time_regression_even_when_engine_total_is_faster(tmp_path):
    baseline = tmp_path / "baseline.json"
    variant = tmp_path / "variant.json"
    _write_app_path(baseline, passes=True, total=285.569, source_selection=116.452, wall=300.0)
    _write_app_path(variant, passes=True, total=240.0, source_selection=80.0, wall=360.0, cited=18)

    comparator = _load_comparator()
    report = comparator.build_report(baseline_path=baseline, variant_path=variant)

    assert report["passes"] is False
    assert report["checks"]["fasterTotal"]["passes"] is False
    assert report["checks"]["fasterTotal"]["baselineCheckedTotalSec"] == 300.0
    assert report["checks"]["fasterTotal"]["variantCheckedTotalSec"] == 360.0
    assert report["checks"]["fasterTotal"]["deltaSec"] == 60.0


def test_app_path_variant_comparator_can_enforce_absolute_latency_budgets(tmp_path):
    baseline = tmp_path / "baseline.json"
    variant = tmp_path / "variant.json"
    _write_app_path(baseline, passes=True, total=285.569, source_selection=116.452, cited=15)
    _write_app_path(variant, passes=True, total=240.0, source_selection=80.0, cited=18)

    comparator = _load_comparator()
    report = comparator.build_report(
        baseline_path=baseline,
        variant_path=variant,
        max_total_sec=120,
        max_source_selection_sec=30,
    )

    assert report["passes"] is False
    assert report["checks"]["fasterTotal"]["passes"] is True
    assert report["checks"]["absoluteTotalLatency"]["passes"] is False
    assert report["checks"]["absoluteTotalLatency"]["checkedSec"] == 240.0
    assert report["checks"]["absoluteTotalLatency"]["expected"] == "<=120"
    assert report["checks"]["absoluteSourceSelectionLatency"]["passes"] is False
    assert report["checks"]["absoluteSourceSelectionLatency"]["sourceSelectionSec"] == 80.0
    assert report["checks"]["absoluteSourceSelectionLatency"]["expected"] == "<=30"
