import json
from pathlib import Path

from tools import run_three_arm_benchmark_suite


MODEL_META = {
    "provider": "fixture_provider",
    "model": "shared-model",
    "decoding": {"temperature": 0.2},
}


def _write(path: Path, value: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _fake_arm(mode: str, predictions: dict[str, str]):
    def run_manifest(*, public_path: Path, output_dir: Path, **_kwargs):
        public = json.loads(public_path.read_text(encoding="utf-8"))
        results = output_dir / "results"
        results.mkdir(parents=True, exist_ok=True)
        for case in public["cases"]:
            case_id = case["id"]
            _write(
                results / f"{case_id}.json",
                {
                    "id": case_id,
                    "caseId": case_id,
                    "prediction": predictions[case_id],
                    "mode": mode,
                    "modelMetadata": MODEL_META,
                },
            )
        summary = {
            "benchmarkId": public["benchmarkId"],
            "taskType": public["taskType"],
            "mode": mode,
            "total": {"total": len(public["cases"]), "predicted": len(public["cases"]), "errors": 0},
            "modelMetadata": MODEL_META,
        }
        _write(output_dir / "summary.json", summary)
        return summary

    return run_manifest


def test_three_arm_suite_scores_paired_cases_and_refuses_small_non_significant_claim(tmp_path, monkeypatch):
    public_path = tmp_path / "benchmarks" / "unified" / "mcq.public.json"
    private_path = tmp_path / "benchmarks" / "unified" / "mcq.private.json"
    _write(
        public_path,
        {
            "benchmarkId": "mcq.fixture.v1",
            "taskType": "mcq",
            "product": "fixture",
            "cases": [{"id": "q1", "prompt": "q1"}, {"id": "q2", "prompt": "q2"}],
        },
    )
    _write(
        private_path,
        {
            "benchmarkId": "mcq.fixture.v1",
            "answers": [
                {"caseId": "q1", "correctOptionId": "1"},
                {"caseId": "q2", "correctOptionId": "2"},
            ],
        },
    )
    registry_path = tmp_path / "benchmarks" / "evaluation_registry.json"
    _write(
        registry_path,
        {
            "schemaVersion": 1,
            "comparisonArms": ["direct", "beta6", "universal"],
            "canonicalExamAggregate": {
                "expectedUniqueCases": 2,
                "entries": [
                    {
                        "publicManifest": "unified/mcq.public.json",
                        "privateManifest": "unified/mcq.private.json",
                        "expectedCases": 2,
                    }
                ],
            },
            "legalEndToEnd": {"expectedTasks": 0, "entries": []},
            "diagnosticSlices": [],
            "promotionGate": {
                "exam": {"pairedMcNemarPValueMaximum": 0.05},
                "modelParity": {"provider": True, "model": True, "decoding": True},
            },
        },
    )
    monkeypatch.setattr(
        run_three_arm_benchmark_suite.direct_runner,
        "run_manifest",
        _fake_arm("direct", {"q1": "1", "q2": "1"}),
    )
    monkeypatch.setattr(
        run_three_arm_benchmark_suite.beta6_runner,
        "run_manifest",
        _fake_arm("beta6", {"q1": "2", "q2": "2"}),
    )
    monkeypatch.setattr(
        run_three_arm_benchmark_suite.universal_runner,
        "run_manifest",
        _fake_arm("universal", {"q1": "1", "q2": "2"}),
    )

    report = run_three_arm_benchmark_suite.run_suite(
        registry_path=registry_path,
        output_dir=tmp_path / "out",
        products={"fixture": object()},
        model="shared-model",
    )

    assert report["examAggregate"]["arms"]["direct"]["accuracy"] == 0.5
    assert report["examAggregate"]["arms"]["beta6"]["accuracy"] == 0.5
    assert report["examAggregate"]["arms"]["universal"]["accuracy"] == 1.0
    assert report["examAggregate"]["comparisons"]["universalVsDirect"]["universalOnlyCorrect"] == 1
    assert report["examAggregate"]["promotion"]["strictlyBetterThanBoth"] is True
    assert report["examAggregate"]["promotion"]["statisticallySignificantAgainstBoth"] is False
    assert report["goalAchieved"] is False
    assert report["modelParity"]["passed"] is True
    assert (tmp_path / "out" / "three_arm_suite_report.json").exists()


def test_exact_mcnemar_detects_clear_paired_advantage():
    baseline = {f"q{i}": False for i in range(20)}
    universal = {f"q{i}": True for i in range(20)}

    result = run_three_arm_benchmark_suite.paired_comparison(baseline, universal)

    assert result["universalOnlyCorrect"] == 20
    assert result["baselineOnlyCorrect"] == 0
    assert result["pValueTwoSidedExact"] < 0.00001


def test_legal_aggregate_requires_all_ten_variants_not_just_all_three_tasks():
    def entry(total: int) -> dict:
        return {
            "modes": {
                arm: {
                    "semanticJudge": {
                        "total": total,
                        "passed": total if arm == "universal" else 0,
                        "groundingPassed": total if arm == "universal" else 0,
                    },
                    "summary": {"total": {"errors": 0}},
                }
                for arm in run_three_arm_benchmark_suite.ARMS
            }
        }

    nine_variant_report = run_three_arm_benchmark_suite._legal_aggregate(
        [entry(3), entry(3), entry(3)],
        expected_tasks=3,
        expected_variants=10,
        model_parity={"passed": True},
        subset=False,
    )
    ten_variant_report = run_three_arm_benchmark_suite._legal_aggregate(
        [entry(4), entry(4), entry(2)],
        expected_tasks=3,
        expected_variants=10,
        model_parity={"passed": True},
        subset=False,
    )

    assert nine_variant_report["arms"]["direct"]["totalVariants"] == 9
    assert nine_variant_report["promotion"]["complete"] is False
    assert ten_variant_report["arms"]["direct"]["totalVariants"] == 10
    assert ten_variant_report["promotion"]["complete"] is True
