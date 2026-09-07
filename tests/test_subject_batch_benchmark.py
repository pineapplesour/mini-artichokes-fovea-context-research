import json
from pathlib import Path

import pytest

from tools.run_subject_batch_benchmark import (
    MODE,
    audit_subject_batch_trace,
    build_subject_batch_query,
    parse_subject_batch_answer,
    partition_subject_cases,
    run_subject_batches,
)


def _manifest():
    return {
        "schemaVersion": 2,
        "benchmarkId": "open_response.tcm.fixture.v2",
        "sourceBenchmarkId": "mcq.tcm.fixture.v1",
        "taskType": "open_response",
        "product": "tcm",
        "language": "ko",
        "cases": [
            {
                "id": "q1",
                "prompt": "검사 A의 이름은?",
                "graderRef": "q1",
                "metadata": {"openResponseConversion": {"status": "ready_hide_options"}},
            },
            {
                "id": "q2",
                "prompt": "증상 B의 진단은?",
                "graderRef": "q2",
                "metadata": {"openResponseConversion": {"status": "ready_hide_options"}},
            },
            {
                "id": "q3",
                "prompt": "다음 중 맞는 것은?",
                "graderRef": "q3",
                "metadata": {"openResponseConversion": {"status": "needs_semantic_rewrite"}},
            },
        ],
    }


def _trace():
    return {
        "status": "completed",
        "codexJsonlEventCount": 5,
        "codexJsonlInvalidLineCount": 0,
        "webSearchEvents": [
            {
                "eventType": "item.completed",
                "query": "인지 선별검사 표준 명칭",
                "action": {"type": "search", "query": "인지 선별검사 표준 명칭"},
            }
        ],
        "mcpToolEvents": [
            {
                "eventType": "item.completed",
                "server": "domain_evidence",
                "tool": "search_domain_evidence",
                "status": "completed",
                "arguments": {"query": "인지 선별검사", "product": "tcm", "limit": 3, "snippet_chars": 600},
            }
        ],
        "commandExecutionEvents": [
            {
                "eventType": "item.completed",
                "command": "python3 -c 'print(6*7)'",
                "status": "completed",
                "exitCode": 0,
            }
        ],
        "tokenUsage": {"totalTokens": 1234},
        "elapsedSec": 2.5,
    }


class FakeClient:
    def __init__(self, answer=None, trace=None):
        self.answer = answer or '{"answers":[{"id":"q1","finalAnswer":"A"},{"id":"q2","finalAnswer":"B"}]}'
        self.trace = trace or _trace()
        self.calls = []

    def complete(self, messages, *, model):
        self.calls.append({"messages": messages, "model": model})
        return self.answer

    def consume_last_call_trace(self):
        return self.trace


def test_batch_query_contains_only_public_items_and_strict_output_contract():
    manifest = _manifest()
    query = build_subject_batch_query(manifest=manifest, cases=manifest["cases"][:2])

    assert "검사 A의 이름은?" in query
    assert "증상 B의 진단은?" in query
    assert '"answers"' in query
    assert "answer key" in query
    assert "independently" in query
    assert "at most two database tool calls" in query
    assert "at most 64 characters and eight tokens" in query


def test_batch_query_can_include_a_public_response_contract_without_private_answers():
    manifest = _manifest()
    manifest["responseContract"] = "관련 출처 식별자를 답에 포함한다."

    query = build_subject_batch_query(manifest=manifest, cases=manifest["cases"][:2])

    assert "Public response contract: 관련 출처 식별자를 답에 포함한다." in query


def test_batch_query_and_audit_enforce_a_public_external_evidence_contract():
    manifest = _manifest()
    manifest["externalEvidenceRequired"] = True
    query = build_subject_batch_query(manifest=manifest, cases=manifest["cases"][:2])

    assert "MUST complete at least one native web search or mounted database search" in query
    no_tools = _trace()
    no_tools["webSearchEvents"] = []
    no_tools["mcpToolEvents"] = []
    audit = audit_subject_batch_trace(
        no_tools,
        public_question="검사 A의 이름은?",
        db_product="tcm",
        maximum_mcp_calls=2,
        maximum_total_tokens=80_000,
        require_external_evidence=True,
    )

    assert audit["passed"] is False
    assert "required_external_evidence_not_used" in audit["violations"]


def test_partition_is_bounded_by_count_and_prompt_characters():
    cases = [{"id": f"q{i}", "prompt": "가" * 600} for i in range(5)]

    batches = partition_subject_cases(cases, batch_size=3, max_prompt_chars=1_000)

    assert [len(batch) for batch in batches] == [1, 1, 1, 1, 1]


def test_partition_never_places_correlated_variants_in_one_batch():
    cases = [
        {"id": "a1", "prompt": "one", "metadata": {"batchLeakageGroup": "a"}},
        {"id": "b1", "prompt": "two", "metadata": {"batchLeakageGroup": "b"}},
        {"id": "a2", "prompt": "three", "metadata": {"batchLeakageGroup": "a"}},
        {"id": "b2", "prompt": "four", "metadata": {"batchLeakageGroup": "b"}},
    ]

    batches = partition_subject_cases(cases, batch_size=4, max_prompt_chars=10_000)

    assert [[case["id"] for case in batch] for batch in batches] == [["a1", "b1"], ["a2", "b2"]]


def test_strict_parser_rejects_missing_reordered_or_extra_ids():
    assert parse_subject_batch_answer(
        '{"answers":[{"id":"q1","finalAnswer":"A"},{"id":"q2","finalAnswer":"B"}]}',
        expected_ids=["q1", "q2"],
    ) == {"q1": "A", "q2": "B"}
    with pytest.raises(ValueError, match="ids_do_not_match"):
        parse_subject_batch_answer(
            '{"answers":[{"id":"q2","finalAnswer":"B"},{"id":"q1","finalAnswer":"A"}]}',
            expected_ids=["q1", "q2"],
        )


def test_trace_audit_accepts_safe_optional_tools_and_rejects_question_lookup():
    safe = audit_subject_batch_trace(
        _trace(),
        public_question="검사 A의 이름은?\n\n증상 B의 진단은?",
        db_product="tcm",
        maximum_mcp_calls=12,
        maximum_total_tokens=80_000,
    )
    assert safe["passed"] is True

    cheating = _trace()
    cheating["webSearchEvents"] = [
        {
            "eventType": "item.completed",
            "query": "한의사 기출 정답 q12",
            "action": {"type": "search", "query": "한의사 기출 정답 q12"},
        }
    ]
    rejected = audit_subject_batch_trace(
        cheating,
        public_question="검사 A의 이름은?",
        db_product="tcm",
        maximum_mcp_calls=12,
        maximum_total_tokens=80_000,
    )
    assert rejected["passed"] is False
    assert "web_search_anti_cheating_audit_failed" in rejected["violations"]


def test_trace_audit_rejects_batch_tool_or_token_budget_overrun():
    overrun = _trace()
    overrun["mcpToolEvents"] = overrun["mcpToolEvents"] * 3
    overrun["tokenUsage"] = {"totalTokens": 80_001}

    audit = audit_subject_batch_trace(
        overrun,
        public_question="검사 A의 이름은?",
        db_product="tcm",
        maximum_mcp_calls=2,
        maximum_total_tokens=80_000,
    )

    assert audit["passed"] is False
    assert "batch_token_budget_exceeded" in audit["violations"]
    assert "batch_domain_tool_budget_exceeded" in audit["violations"]


def test_runner_uses_one_call_for_two_ready_items_and_writes_item_receipt_links(tmp_path):
    manifest = _manifest()
    public_path = tmp_path / "public.json"
    public_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    client = FakeClient()

    summary = run_subject_batches(
        public_path=public_path,
        output_dir=tmp_path / "run",
        llm_client=client,
        model="fixture-model",
        database={"path": "/fixture/tcm.db", "sizeBytes": 2_000_000, "fixtureWarning": False},
        db_product="tcm",
        batch_size=8,
    )

    assert len(client.calls) == 1
    assert summary["mode"] == MODE
    assert summary["total"] == {"batches": 1, "cases": 2, "predicted": 2, "accepted": 2, "errors": 0}
    first = json.loads((tmp_path / "run/results/q1.json").read_text(encoding="utf-8"))
    second = json.loads((tmp_path / "run/results/q2.json").read_text(encoding="utf-8"))
    assert first["batchId"] == second["batchId"]
    assert first["batchReceiptPayloadSha256"] == second["batchReceiptPayloadSha256"]
    assert first["toolAccess"] == {
        "webSearch": True,
        "ephemeralWorkspaceCode": True,
        "readOnlyDomainDatabase": True,
        "beta6Frontier": False,
        "customSkills": False,
    }
    assert not (tmp_path / "run/results/q3.json").exists()
