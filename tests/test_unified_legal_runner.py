import json
from pathlib import Path

from shared_platform.products import ProductProfile
from tools.run_unified_legal_benchmark import run_direct_manifest, run_legal_manifest
from tools.score_unified_benchmarks import score_predictions


class FakeRuntime:
    instances = []

    def __init__(self, profiles, *, runs_root, llm_client=None, resume_pending_jobs=False):
        self.profiles = profiles
        self.runs_root = runs_root
        self.llm_client = llm_client
        self.resume_pending_jobs = resume_pending_jobs
        self.calls = []
        self.shutdown_called = False
        FakeRuntime.instances.append(self)

    def answer_sync(self, *, product, query, language, limit, analysis_mode):
        self.calls.append(
            {
                "product": product,
                "query": query,
                "language": language,
                "limit": limit,
                "analysis_mode": analysis_mode,
            }
        )
        return {
            "jobId": f"job-{len(self.calls)}",
            "answer": f"answer for {query} using 2024구합65355",
            "answerMarkdown": f"answer for {query} using 2024구합65355",
            "answerReadiness": "final_answer",
            "selector": {"status": "completed", "candidateCount": 2, "selectionSource": "fake_selector"},
            "writer": {"status": "completed", "mode": "llm_writer", "provider": "fake"},
            "selectedEvidence": [
                {
                    "rank": 1,
                    "citation": "서울행정법원 2025. 1. 21. 선고 2024구합65355 판결",
                    "caseNumber": "2024구합65355",
                    "excerpt": "유심 공기계 카카오톡 증거능력",
                }
            ],
            "sources": [
                {
                    "rank": 1,
                    "citation": "서울행정법원 2025. 1. 21. 선고 2024구합65355 판결",
                    "caseNumber": "2024구합65355",
                }
            ],
            "passages": [{"rank": 1, "text": "유심 공기계 카카오톡 증거능력"}],
            "contextPackets": [
                {
                    "packetId": "S1:2024구합65355",
                    "sourceId": "2024구합65355",
                    "exactQuote": "유심 공기계 카카오톡 증거능력",
                }
            ],
            "beta6SelectedRecords": [{"rank": 1, "case_number": "2024구합65355"}],
            "artifacts": {"contextPackets": str(self.runs_root / f"job-{len(self.calls)}" / "context_packets.json")},
            "beta6": {"selectedCount": 1, "candidateCount": 2, "selectorStatus": "completed", "contextPacketCount": 1},
        }

    def shutdown(self, wait=False):
        self.shutdown_called = True


class FakeLLMClient:
    provider = "legal_direct_fixture"
    default_model = "gemma-legal-direct"
    decoding = {"temperature": 0}

    def __init__(self, answer: str):
        self.answer = answer
        self.calls = []

    def complete(self, messages, *, model="", timeout_seconds=None):
        self.calls.append({"messages": messages, "model": model, "timeout_seconds": timeout_seconds})
        return self.answer


def test_run_legal_manifest_records_variant_artifacts_without_private_targets(tmp_path, monkeypatch):
    import tools.run_unified_legal_benchmark as runner

    FakeRuntime.instances = []
    monkeypatch.setattr(runner, "Beta6JobManager", FakeRuntime)
    public = {
        "schemaVersion": 1,
        "benchmarkId": "legal.test",
        "taskType": "legal_retrieval_answer",
        "product": "lawkey",
        "cases": [
            {
                "id": "case-a",
                "language": "ko",
                "variants": [
                    {"id": "v1", "query": "유심 카카오톡 증거능력?"},
                    {"id": "v2", "query": "SIM 공기계 로그인 수사?"},
                ],
                "runtime": {"candidateLimit": 12},
                "graderRef": "grader-a",
            }
        ],
    }
    public_path = tmp_path / "public.json"
    public_path.write_text(json.dumps(public, ensure_ascii=False), encoding="utf-8")
    db_path = tmp_path / "lawkey.sqlite3"
    db_path.write_text("", encoding="utf-8")
    product = ProductProfile(
        key="lawkey",
        name="Lawkey",
        db_path=db_path,
        db_shape="precedents",
        languages=("ko",),
        default_language="ko",
        theme="",
        safety_notice="test",
    )

    summary = run_legal_manifest(
        public_path=public_path,
        output_dir=tmp_path / "run",
        products={"lawkey": product},
        limit=50,
        analysis_mode="fast",
    )

    assert summary["total"]["total"] == 2
    assert summary["total"]["predicted"] == 2
    runtime = FakeRuntime.instances[0]
    assert [call["limit"] for call in runtime.calls] == [12, 12]
    assert runtime.shutdown_called is True
    records = sorted((tmp_path / "run" / "results").glob("*.json"))
    assert [path.name for path in records] == ["case-a__v1.json", "case-a__v2.json"]
    record = json.loads(records[0].read_text(encoding="utf-8"))
    assert record["caseId"] == "case-a"
    assert record["variantId"] == "v1"
    assert record["graderId"] == "grader-a"
    assert record["query"] == "유심 카카오톡 증거능력?"
    assert record["selectedEvidence"][0]["caseNumber"] == "2024구합65355"
    assert record["contextPacketCount"] == 1
    assert record["contextPacketIds"] == ["S1:2024구합65355"]
    assert record["contextPacketArtifact"].endswith("context_packets.json")
    dumped = json.dumps(record, ensure_ascii=False)
    assert "primaryTargets" not in dumped
    assert "answerRules" not in dumped


def test_run_legal_direct_manifest_records_answer_only_baseline_without_db_or_targets(tmp_path):
    public = {
        "schemaVersion": 1,
        "benchmarkId": "legal.direct.test",
        "taskType": "legal_retrieval_answer",
        "product": "lawkey",
        "cases": [
            {
                "id": "case-a",
                "language": "ko",
                "variants": [
                    {"id": "v1", "query": "유심 카카오톡 증거능력?"},
                    {"id": "v2", "query": "SIM 공기계 로그인 수사?"},
                ],
                "graderRef": "grader-a",
            }
        ],
    }
    public_path = tmp_path / "public.json"
    public_path.write_text(json.dumps(public, ensure_ascii=False), encoding="utf-8")
    fake = FakeLLMClient("2024구합65355 판례와 유심 분리 쟁점을 직접 설명합니다.")

    summary = run_direct_manifest(
        public_path=public_path,
        output_dir=tmp_path / "direct",
        products={"lawkey": ProductProfile(
            key="lawkey",
            name="Lawkey",
            db_path=tmp_path / "missing.sqlite3",
            db_shape="precedents",
            languages=("ko",),
            default_language="ko",
            theme="",
            safety_notice="test",
        )},
        llm_client=fake,
        model="gemma-legal-direct-override",
    )

    assert summary["mode"] == "direct"
    assert summary["total"]["total"] == 2
    assert summary["modelMetadata"] == {
        "provider": "legal_direct_fixture",
        "model": "gemma-legal-direct-override",
        "decoding": {"temperature": 0},
    }
    assert [call["model"] for call in fake.calls] == ["gemma-legal-direct-override", "gemma-legal-direct-override"]
    record = json.loads((tmp_path / "direct" / "results" / "case-a__v1.json").read_text(encoding="utf-8"))
    assert record["mode"] == "direct"
    assert record["answer"].startswith("2024구합65355")
    assert record["selectedEvidence"] == []
    assert record["retrievedCases"] == []
    assert record["modelMetadata"] == summary["modelMetadata"]
    dumped = json.dumps(record, ensure_ascii=False)
    assert "primaryTargets" not in dumped
    assert "answerRules" not in dumped


def test_run_legal_manifest_does_not_call_runtime_when_db_is_missing(tmp_path, monkeypatch):
    import tools.run_unified_legal_benchmark as runner

    class ExplodingRuntime:
        def __init__(self, *args, **kwargs):
            raise AssertionError("runtime must not be created when legal DB is missing")

    monkeypatch.setattr(runner, "Beta6JobManager", ExplodingRuntime)
    public = {
        "schemaVersion": 1,
        "benchmarkId": "legal.test",
        "taskType": "legal_retrieval_answer",
        "product": "lawkey",
        "cases": [
            {
                "id": "case-a",
                "language": "ko",
                "variants": [{"id": "v1", "query": "유심 카카오톡 증거능력?"}],
                "graderRef": "grader-a",
            }
        ],
    }
    public_path = tmp_path / "public.json"
    public_path.write_text(json.dumps(public, ensure_ascii=False), encoding="utf-8")
    product = ProductProfile(
        key="lawkey",
        name="Lawkey",
        db_path=tmp_path / "missing.sqlite3",
        db_shape="precedents",
        languages=("ko",),
        default_language="ko",
        theme="",
        safety_notice="test",
    )

    summary = run_legal_manifest(
        public_path=public_path,
        output_dir=tmp_path / "run",
        products={"lawkey": product},
    )

    assert summary["total"]["total"] == 1
    assert summary["total"]["predicted"] == 0
    assert summary["total"]["errors"] == 1
    record = json.loads((tmp_path / "run" / "results" / "case-a__v1.json").read_text(encoding="utf-8"))
    assert record["llmUsed"] is False
    assert "database not found" in record["error"]


def test_run_legal_manifest_missing_db_honors_max_cases(tmp_path, monkeypatch):
    import tools.run_unified_legal_benchmark as runner

    class ExplodingRuntime:
        def __init__(self, *args, **kwargs):
            raise AssertionError("runtime must not be created when legal DB is missing")

    monkeypatch.setattr(runner, "Beta6JobManager", ExplodingRuntime)
    public = {
        "schemaVersion": 1,
        "benchmarkId": "legal.test",
        "taskType": "legal_retrieval_answer",
        "product": "lawkey",
        "cases": [
            {
                "id": "case-a",
                "language": "ko",
                "variants": [
                    {"id": "v1", "query": "첫 번째 변형"},
                    {"id": "v2", "query": "두 번째 변형"},
                ],
                "graderRef": "grader-a",
            },
            {
                "id": "case-b",
                "language": "ko",
                "variants": [{"id": "v1", "query": "실행되면 안 되는 케이스"}],
                "graderRef": "grader-b",
            },
        ],
    }
    public_path = tmp_path / "public.json"
    public_path.write_text(json.dumps(public, ensure_ascii=False), encoding="utf-8")
    product = ProductProfile(
        key="lawkey",
        name="Lawkey",
        db_path=tmp_path / "missing.sqlite3",
        db_shape="precedents",
        languages=("ko",),
        default_language="ko",
        theme="",
        safety_notice="test",
    )

    summary = run_legal_manifest(
        public_path=public_path,
        output_dir=tmp_path / "run",
        products={"lawkey": product},
        max_cases=1,
    )

    assert summary["total"]["total"] == 2
    records = sorted((tmp_path / "run" / "results").glob("*.json"))
    assert [path.name for path in records] == ["case-a__v1.json", "case-a__v2.json"]


def test_run_legal_manifest_can_filter_cases_by_id(tmp_path, monkeypatch):
    import tools.run_unified_legal_benchmark as runner

    class ExplodingRuntime:
        def __init__(self, *args, **kwargs):
            raise AssertionError("runtime must not be created when legal DB is missing")

    monkeypatch.setattr(runner, "Beta6JobManager", ExplodingRuntime)
    public = {
        "schemaVersion": 1,
        "benchmarkId": "legal.test",
        "taskType": "legal_retrieval_answer",
        "product": "lawkey",
        "cases": [
            {
                "id": "case-a",
                "language": "ko",
                "variants": [{"id": "v1", "query": "실행되면 안 되는 케이스"}],
                "graderRef": "grader-a",
            },
            {
                "id": "case-b",
                "language": "ko",
                "variants": [
                    {"id": "v1", "query": "첫 번째 변형"},
                    {"id": "v2", "query": "두 번째 변형"},
                ],
                "graderRef": "grader-b",
            },
        ],
    }
    public_path = tmp_path / "public.json"
    public_path.write_text(json.dumps(public, ensure_ascii=False), encoding="utf-8")
    product = ProductProfile(
        key="lawkey",
        name="Lawkey",
        db_path=tmp_path / "missing.sqlite3",
        db_shape="precedents",
        languages=("ko",),
        default_language="ko",
        theme="",
        safety_notice="test",
    )

    summary = run_legal_manifest(
        public_path=public_path,
        output_dir=tmp_path / "run",
        products={"lawkey": product},
        case_ids=["case-b"],
    )

    assert summary["total"]["total"] == 2
    records = sorted((tmp_path / "run" / "results").glob("*.json"))
    assert [path.name for path in records] == ["case-b__v1.json", "case-b__v2.json"]


def test_score_legal_predictions_scores_each_variant_artifact():
    private = {
        "benchmarkId": "legal.test",
        "graders": [
            {
                "graderId": "grader-a",
                "primaryTargets": [{"caseNumber": "2024구합65355"}],
                "rankRules": {"primaryMustAppearWithin": 3},
                "answerRules": {"mustDiscuss": ["유심"], "mustUseAtLeastTargetCount": 1},
            }
        ],
    }
    artifacts = [
        {
            "caseId": "case-a",
            "variantId": "v1",
            "graderId": "grader-a",
            "answer": "유심 쟁점은 2024구합65355 판결과 관련된다.",
            "selectedEvidence": [{"rank": 1, "caseNumber": "2024구합65355"}],
        },
        {
            "caseId": "case-a",
            "variantId": "v2",
            "graderId": "grader-a",
            "answer": "관련 없는 답변",
            "selectedEvidence": [],
        },
    ]

    score = score_predictions(private, artifacts)

    assert score["total"] == 2
    assert score["passed"] == 1
    assert [case["caseId"] for case in score["cases"]] == ["case-a__v1", "case-a__v2"]
    assert score["cases"][0]["passed"] is True
    assert score["cases"][1]["passed"] is False
