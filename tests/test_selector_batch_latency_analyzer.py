import importlib.util
import json
from pathlib import Path


def _load_analyzer():
    path = Path("tools/analyze_selector_batch_latency.py")
    spec = importlib.util.spec_from_file_location("analyze_selector_batch_latency", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _write_selector_meta(path: Path, *, workers: int, elapsed: list[float]) -> None:
    path.write_text(
        json.dumps(
            {
                "selectorBatchSize": 100,
                "selectorBatchWorkers": workers,
                "selectorCandidateLimit": len(elapsed) * 100,
                "selectorBatchTrace": [
                    {
                        "batch": index + 1,
                        "candidateCount": 100,
                        "selectedCount": index % 3,
                        "status": "completed",
                        "elapsedSec": seconds,
                    }
                    for index, seconds in enumerate(elapsed)
                ],
            }
        ),
        encoding="utf-8",
    )


def test_selector_batch_latency_projection_shows_worker_only_lower_bound(tmp_path):
    selector_meta = tmp_path / "selector_meta.json"
    _write_selector_meta(selector_meta, workers=2, elapsed=[40.0, 10.0, 10.0, 10.0])

    analyzer = _load_analyzer()
    report = analyzer.build_report(
        selector_meta=selector_meta,
        workers=[1, 2, 4],
        max_source_selection_sec=30.0,
    )

    assert report["passes"] is False
    assert report["source"]["exactFullTrace"] is True
    assert report["summary"]["batchCount"] == 4
    assert report["summary"]["maxBatchSec"] == 40.0
    assert report["summary"]["currentWorkers"] == 2
    assert report["projections"][0]["workers"] == 1
    assert report["projections"][0]["projectedSec"] == 70.0
    assert report["projections"][1]["workers"] == 2
    assert report["projections"][1]["projectedSec"] == 40.0
    assert report["projections"][2]["workers"] == 4
    assert report["projections"][2]["projectedSec"] == 40.0
    assert report["checks"]["workerOnlyCanMeetBudget"]["passes"] is False
    assert report["checks"]["workerOnlyCanMeetBudget"]["reason"] == "single_batch_exceeds_budget"


def test_selector_batch_latency_projection_uses_original_batch_order(tmp_path):
    selector_meta = tmp_path / "selector_meta.json"
    _write_selector_meta(selector_meta, workers=2, elapsed=[8.0, 7.0, 6.0, 5.0])

    analyzer = _load_analyzer()
    report = analyzer.build_report(
        selector_meta=selector_meta,
        workers=[2],
        max_source_selection_sec=20.0,
    )

    assert report["passes"] is True
    assert report["projections"] == [
        {
            "workers": 2,
            "projectedSec": 13.0,
            "workLowerBoundSec": 13.0,
            "maxBatchLowerBoundSec": 8.0,
            "passesBudget": True,
        }
    ]
    assert report["checks"]["workerOnlyCanMeetBudget"]["passes"] is True
