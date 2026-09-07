import json
import importlib.util
from pathlib import Path


def _load_matrix():
    path = Path("tools/verify_app_path_budget_matrix.py")
    spec = importlib.util.spec_from_file_location("verify_app_path_budget_matrix", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _write_artifact(
    path: Path,
    *,
    product: str,
    passes: bool = True,
    wall: float | None = None,
    stage_total: float | None = None,
    source_selection: float | None = None,
    cold_engine_cache: bool | None = None,
) -> None:
    payload = {
        "passes": passes,
        "product": product,
        "metrics": {"sourceCount": 100, "citedClaimCount": 12, "answerChars": 3200},
        "checks": {
            "sourceGrounding": {"passes": passes},
            "answerDepth": {"passes": passes},
        },
    }
    if cold_engine_cache is not None:
        payload["checks"]["coldEngineCache"] = {"passes": cold_engine_cache}
    if wall is not None:
        payload["wallClockSeconds"] = wall
    if stage_total is not None:
        payload["stageTimings"] = {
            "totalSec": stage_total,
            "totals": {"source_selection": source_selection or 0.0},
        }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_app_path_budget_matrix_fails_any_product_over_budget(tmp_path):
    islam = tmp_path / "islam.json"
    tcm = tmp_path / "tcm.json"
    simli = tmp_path / "simli.json"
    _write_artifact(islam, product="islam", wall=95.0, stage_total=90.0, source_selection=10.0)
    _write_artifact(tcm, product="tcm", stage_total=121.0, source_selection=25.0)
    _write_artifact(simli, product="simli", wall=80.0, stage_total=70.0, source_selection=10.0)

    matrix = _load_matrix()
    report = matrix.build_report(
        cases=[
            ("islam", islam),
            ("tcm", tcm),
            ("simli", simli),
        ],
        max_total_sec=120,
        max_source_selection_sec=30,
    )

    assert report["passes"] is False
    assert report["summary"]["caseCount"] == 3
    assert report["summary"]["failedCount"] == 1
    assert report["cases"][1]["product"] == "tcm"
    assert report["cases"][1]["checks"]["totalLatency"]["passes"] is False
    assert report["cases"][1]["checks"]["totalLatency"]["checkedSec"] == 121.0


def test_app_path_budget_matrix_fails_source_selection_budget_when_missing(tmp_path):
    artifact = tmp_path / "browser.json"
    _write_artifact(artifact, product="islam", wall=95.0)

    matrix = _load_matrix()
    report = matrix.build_report(cases=[("islam", artifact)], max_total_sec=120, max_source_selection_sec=30)

    assert report["passes"] is False
    assert report["cases"][0]["checks"]["totalLatency"]["passes"] is True
    assert report["cases"][0]["checks"]["sourceSelectionLatency"]["passes"] is False
    assert report["cases"][0]["checks"]["sourceSelectionLatency"]["measured"] is False


def test_app_path_budget_matrix_fails_total_budget_when_total_latency_is_unmeasured(tmp_path):
    artifact = tmp_path / "missing-total.json"
    _write_artifact(artifact, product="islam")

    matrix = _load_matrix()
    report = matrix.build_report(cases=[("islam", artifact)], max_total_sec=120)

    assert report["passes"] is False
    assert report["cases"][0]["checks"]["totalLatency"]["passes"] is False
    assert report["cases"][0]["checks"]["totalLatency"]["measured"] is False


def test_app_path_budget_matrix_can_require_all_products(tmp_path):
    islam = tmp_path / "islam.json"
    tcm = tmp_path / "tcm.json"
    _write_artifact(islam, product="islam", wall=95.0)
    _write_artifact(tcm, product="tcm", wall=100.0)

    matrix = _load_matrix()
    report = matrix.build_report(
        cases=[("islam", islam), ("tcm", tcm)],
        max_total_sec=120,
        required_products=["islam", "tcm", "simli"],
    )

    assert report["passes"] is False
    assert report["checks"]["requiredProducts"]["passes"] is False
    assert report["checks"]["requiredProducts"]["missing"] == ["simli"]
    assert report["summary"]["caseCount"] == 2


def test_app_path_budget_matrix_can_require_cold_engine_cache_for_latency_proof(tmp_path):
    artifact = tmp_path / "hot-cache.json"
    _write_artifact(
        artifact,
        product="islam",
        wall=95.0,
        stage_total=90.0,
        source_selection=10.0,
        cold_engine_cache=False,
    )

    matrix = _load_matrix()
    report = matrix.build_report(
        cases=[("islam", artifact)],
        max_total_sec=120,
        max_source_selection_sec=30,
        require_cold_engine_cache=True,
    )

    assert report["passes"] is False
    assert report["cases"][0]["checks"]["totalLatency"]["passes"] is True
    assert report["cases"][0]["checks"]["sourceSelectionLatency"]["passes"] is True
    assert report["cases"][0]["checks"]["coldEngineCache"]["passes"] is False
