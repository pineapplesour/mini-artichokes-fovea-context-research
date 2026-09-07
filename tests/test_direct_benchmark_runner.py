import json
from pathlib import Path

from tools import run_direct_benchmark


class FakeClient:
    provider = "fixture_provider"
    default_model = "shared-model"
    decoding = {"temperature": 0.2}

    def __init__(self):
        self.calls = []

    def complete(self, messages, *, model="", timeout_seconds=None):
        self.calls.append({"messages": messages, "model": model})
        return "정답: 2"


def test_direct_runner_is_database_free_and_domain_neutral(tmp_path):
    public_path = tmp_path / "public.json"
    public_path.write_text(
        json.dumps(
            {
                "benchmarkId": "mcq.fixture.v1",
                "taskType": "mcq",
                "product": "some-declared-database",
                "language": "ko",
                "cases": [{"id": "q1", "prompt": "문제\n1. 갑\n2. 을"}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    client = FakeClient()

    summary = run_direct_benchmark.run_manifest(
        public_path=public_path,
        output_dir=tmp_path / "out",
        llm_client=client,
        model="shared-model",
    )

    artifact = json.loads((tmp_path / "out" / "results" / "q1.json").read_text(encoding="utf-8"))
    assert summary["mode"] == "direct"
    assert artifact["prediction"] == "2"
    assert artifact["modelMetadata"] == {
        "provider": "fixture_provider",
        "model": "shared-model",
        "decoding": {"temperature": 0.2},
    }
    assert artifact["selectedEvidence"] == []
    prompt = json.dumps(client.calls[0]["messages"], ensure_ascii=False).lower()
    assert "some-declared-database" not in prompt
    assert "islam" not in prompt
    assert "buddhist" not in prompt
    assert client.calls[0]["model"] == "shared-model"


def test_web_direct_prompt_and_call_trace_are_opt_in(tmp_path, monkeypatch):
    class TraceClient(FakeClient):
        def consume_last_call_trace(self):
            return {"webSearchEnabled": True, "webSearchEvents": [{"query": "general concept"}]}

    public_path = tmp_path / "public.json"
    public_path.write_text(
        json.dumps(
            {
                "benchmarkId": "mcq.fixture.v1",
                "taskType": "mcq",
                "product": "fixture",
                "language": "ko",
                "cases": [{"id": "q1", "prompt": "문제\n1. 갑\n2. 을"}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv(run_direct_benchmark.DIRECT_WEB_SEARCH_ENV, "1")
    client = TraceClient()

    run_direct_benchmark.run_manifest(
        public_path=public_path,
        output_dir=tmp_path / "out",
        llm_client=client,
        model="shared-model",
    )

    artifact = json.loads((tmp_path / "out" / "results" / "q1.json").read_text(encoding="utf-8"))
    assert artifact["modelTrace"]["webSearchEnabled"] is True
    prompt = json.dumps(client.calls[0]["messages"], ensure_ascii=False)
    assert "original question sheet" in prompt
    assert "calculation code" in prompt


def test_required_web_search_retries_until_trace_and_evidence_exist(tmp_path, monkeypatch):
    class RequiredSearchClient(FakeClient):
        def __init__(self):
            super().__init__()
            self.traces = []

        def complete(self, messages, *, model="", timeout_seconds=None):
            self.calls.append({"messages": messages, "model": model})
            if len(self.calls) == 1:
                self.traces.append({"webSearchEnabled": True, "webSearchEvents": []})
                return "정답: 2"
            self.traces.append(
                {"webSearchEnabled": True, "webSearchEvents": [{"query": "general deciding fact"}]}
            )
            return "정답: 2\n검색 근거: standards.example의 일반 기준이 결정 사실을 확인함"

        def consume_last_call_trace(self):
            return self.traces.pop(0)

    public_path = tmp_path / "public.json"
    public_path.write_text(
        json.dumps(
            {
                "benchmarkId": "mcq.fixture.v1",
                "taskType": "mcq",
                "product": "fixture",
                "language": "ko",
                "cases": [{"id": "q1", "prompt": "문제\n1. 갑\n2. 을"}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv(run_direct_benchmark.DIRECT_WEB_SEARCH_ENV, "1")
    monkeypatch.setenv(run_direct_benchmark.DIRECT_WEB_SEARCH_REQUIRED_ENV, "1")
    client = RequiredSearchClient()

    summary = run_direct_benchmark.run_manifest(
        public_path=public_path,
        output_dir=tmp_path / "out",
        llm_client=client,
        model="shared-model",
    )

    artifact = json.loads((tmp_path / "out" / "results" / "q1.json").read_text(encoding="utf-8"))
    assert summary["total"] == {"total": 1, "predicted": 1, "errors": 0}
    assert len(client.calls) == 2
    assert artifact["webSearchRequirement"] == {
        "required": True,
        "satisfied": True,
        "policyAttempts": 2,
        "searchEvidence": "standards.example의 일반 기준이 결정 사실을 확인함",
    }
    assert len(artifact["modelTraceAttempts"]) == 2
    prompt = json.dumps(client.calls[-1]["messages"], ensure_ascii=False)
    assert "MUST use live web search" in prompt
    assert "previous response was rejected" in prompt


def test_required_web_search_rejects_answer_after_policy_attempts(tmp_path, monkeypatch):
    class NoSearchClient(FakeClient):
        def complete(self, messages, *, model="", timeout_seconds=None):
            self.calls.append({"messages": messages, "model": model})
            return "정답: 2"

        def consume_last_call_trace(self):
            return {"webSearchEnabled": True, "webSearchEvents": []}

    public_path = tmp_path / "public.json"
    public_path.write_text(
        json.dumps(
            {
                "benchmarkId": "mcq.fixture.v1",
                "taskType": "mcq",
                "product": "fixture",
                "cases": [{"id": "q1", "prompt": "문제\n1. 갑\n2. 을"}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv(run_direct_benchmark.DIRECT_WEB_SEARCH_ENV, "1")
    monkeypatch.setenv(run_direct_benchmark.DIRECT_WEB_SEARCH_REQUIRED_ENV, "1")
    client = NoSearchClient()

    summary = run_direct_benchmark.run_manifest(
        public_path=public_path,
        output_dir=tmp_path / "out",
        llm_client=client,
        model="shared-model",
    )

    artifact = json.loads((tmp_path / "out" / "results" / "q1.json").read_text(encoding="utf-8"))
    assert len(client.calls) == run_direct_benchmark.REQUIRED_SEARCH_POLICY_ATTEMPTS
    assert summary["total"] == {"total": 1, "predicted": 0, "errors": 1}
    assert "required_web_search_evidence_missing" in artifact["error"]
    assert artifact["webSearchRequirement"]["satisfied"] is False
