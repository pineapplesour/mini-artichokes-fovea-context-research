import hashlib
import json
import os
from pathlib import Path

from tools import run_codex_home_pool


def _home(tmp_path: Path, name: str, auth: str) -> Path:
    path = tmp_path / name
    path.mkdir()
    (path / "auth.json").write_text(auth, encoding="utf-8")
    return path


def test_load_unique_homes_deduplicates_copied_auth(tmp_path):
    first = _home(tmp_path, ".codex-7", "same-auth")
    duplicate = _home(tmp_path, ".codex-profile", "same-auth")
    second = _home(tmp_path, ".codex-6", "other-auth")

    homes = run_codex_home_pool.load_unique_homes([first, duplicate, second])

    assert [home.alias for home in homes] == ["codex-7", "codex-6"]
    assert [home.auth_group for home in homes] == ["auth-01", "auth-02"]


def test_quota_error_classifier_is_narrow():
    assert run_codex_home_pool.is_quota_error("You've hit your weekly usage limit")
    assert run_codex_home_pool.is_quota_error("HTTP 429 too many requests")
    assert run_codex_home_pool.is_quota_error("RESOURCE_EXHAUSTED; limit resets in 2 hours")
    assert not run_codex_home_pool.is_quota_error("invalid_open_response_json")
    assert not run_codex_home_pool.is_quota_error("model returned an empty answer")
    assert not run_codex_home_pool.is_quota_error("authentication token expired")


def test_pool_switches_home_at_case_boundary_and_preserves_attempts(tmp_path, monkeypatch):
    public = {
        "schemaVersion": 2,
        "benchmarkId": "open_response.fixture.v2",
        "taskType": "open_response",
        "language": "ko",
        "cases": [
            {
                "id": "q1",
                "prompt": "A의 효과는?",
                "metadata": {"openResponseConversion": {"status": "ready_hide_options"}},
            }
        ],
    }
    public_path = tmp_path / "public.json"
    public_path.write_text(json.dumps(public, ensure_ascii=False), encoding="utf-8")
    homes = run_codex_home_pool.load_unique_homes(
        [_home(tmp_path, ".codex-7", "auth-7"), _home(tmp_path, ".codex-6", "auth-6")]
    )
    calls = []

    def fake_attempt(**kwargs):
        calls.append(kwargs["home"].alias)
        if len(calls) == 1:
            return {"caseId": "q1", "prediction": None, "error": "weekly usage limit reached", "elapsedSec": 1.0, "modelTrace": {}}
        return {"caseId": "q1", "prediction": "직접 효과", "error": "", "elapsedSec": 2.0, "modelTrace": {"tokenUsage": {"totalTokens": 12}}}

    monkeypatch.setattr(run_codex_home_pool, "_run_attempt", fake_attempt)

    summary = run_codex_home_pool.run_pool(
        public_path=public_path,
        output_dir=tmp_path / "run",
        homes=homes,
        max_total_calls=2,
    )

    assert calls == ["codex-7", "codex-6"]
    assert summary["stopReason"] == "completed_selected_cases"
    assert summary["total"]["quotaFailovers"] == 1
    assert summary["homes"]["auth-01"]["status"] == "quota_exhausted"
    assert summary["homes"]["auth-02"]["tokenUsage"]["totalTokens"] == 12
    attempt_files = sorted((tmp_path / "run" / "attempts" / "q1").glob("*.json"))
    assert [path.name for path in attempt_files] == ["01-codex-7.json", "02-codex-6.json"]
    result = json.loads((tmp_path / "run" / "results" / "q1.json").read_text(encoding="utf-8"))
    assert result["prediction"] == "직접 효과"


def test_pool_does_not_report_completed_selected_cases_when_the_only_case_failed(
    tmp_path, monkeypatch
):
    public = {
        "schemaVersion": 2,
        "benchmarkId": "open_response.fixture.v2",
        "taskType": "open_response",
        "cases": [
            {
                "id": "q1",
                "prompt": "A의 효과는?",
                "metadata": {"openResponseConversion": {"status": "ready_hide_options"}},
            }
        ],
    }
    public_path = tmp_path / "public.json"
    public_path.write_text(json.dumps(public, ensure_ascii=False), encoding="utf-8")
    homes = run_codex_home_pool.load_unique_homes([_home(tmp_path, ".codex-7", "auth-7")])
    monkeypatch.setattr(
        run_codex_home_pool,
        "_run_attempt",
        lambda **_kwargs: {
            "caseId": "q1",
            "prediction": "초안",
            "error": "case_token_budget_exceeded:100>50",
            "elapsedSec": 1.0,
            "modelTrace": {"tokenUsage": {"totalTokens": 100}},
        },
    )

    summary = run_codex_home_pool.run_pool(
        public_path=public_path,
        output_dir=tmp_path / "run",
        homes=homes,
        max_total_calls=1,
    )

    assert summary["stopReason"] == "completed_with_failures"
    assert summary["total"]["errors"] == 1


def test_pool_accepts_structured_calculation_without_conversion_metadata(tmp_path, monkeypatch):
    public = {
        "schemaVersion": 1,
        "benchmarkId": "calculation.fixture.v1",
        "taskType": "structured_calculation",
        "language": "ko",
        "cases": [
            {
                "id": "calc-1",
                "prompt": "100의 10%를 계산하라.",
                "outputFields": ["result"],
            }
        ],
    }
    public_path = tmp_path / "public.json"
    public_path.write_text(json.dumps(public, ensure_ascii=False), encoding="utf-8")
    homes = run_codex_home_pool.load_unique_homes([_home(tmp_path, ".codex-7", "auth-7")])

    def fake_attempt(**kwargs):
        assert kwargs["manifest"]["taskType"] == "structured_calculation"
        return {
            "caseId": "calc-1",
            "prediction": {"result": 10},
            "error": "",
            "elapsedSec": 0.1,
            "modelTrace": {},
        }

    monkeypatch.setattr(run_codex_home_pool, "_run_attempt", fake_attempt)

    summary = run_codex_home_pool.run_pool(
        public_path=public_path,
        output_dir=tmp_path / "run",
        homes=homes,
        max_total_calls=1,
    )

    assert summary["taskType"] == "structured_calculation"
    assert summary["total"]["predicted"] == 1


def test_pool_includes_strictly_approved_semantic_rewrite(tmp_path, monkeypatch):
    public = {
        "schemaVersion": 2,
        "benchmarkId": "open_response.fixture.v2",
        "taskType": "open_response",
        "language": "ko",
        "cases": [
            {
                "id": "q1",
                "prompt": "고유 단서가 있는 질문은?",
                "metadata": {"openResponseConversion": {"status": "ready_semantic_rewrite"}},
            }
        ],
    }
    public_path = tmp_path / "public.json"
    public_path.write_text(json.dumps(public, ensure_ascii=False), encoding="utf-8")
    homes = run_codex_home_pool.load_unique_homes([_home(tmp_path, ".codex-7", "auth-7")])
    monkeypatch.setattr(
        run_codex_home_pool,
        "_run_attempt",
        lambda **kwargs: {"caseId": "q1", "prediction": "답", "error": "", "elapsedSec": 0.1, "modelTrace": {}},
    )

    summary = run_codex_home_pool.run_pool(
        public_path=public_path,
        output_dir=tmp_path / "run",
        homes=homes,
        max_total_calls=1,
    )

    assert summary["total"]["predicted"] == 1


def test_run_attempt_enables_calculation_tools_and_parses_typed_json(tmp_path, monkeypatch):
    captured = {}

    class FakeClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def complete(self, messages, *, model):
            captured["query"] = messages[0]["content"]
            captured["model"] = model
            return '{"net":90,"tax":10}'

        def consume_last_call_trace(self):
            return {
                "commandExecutionEvents": [
                    {"command": "python3 -c 'print(100-10,10)'", "status": "completed", "exitCode": 0}
                ],
                "tokenUsage": {"totalTokens": 8},
            }

    monkeypatch.setattr(run_codex_home_pool, "CodexExecLLMClient", FakeClient)
    home_path = _home(tmp_path, ".codex-7", "auth-7")
    home = run_codex_home_pool.load_unique_homes([home_path])[0]

    record = run_codex_home_pool._run_attempt(
        manifest={"benchmarkId": "calc.v1", "taskType": "structured_calculation", "language": "ko"},
        case={"id": "calc-1", "prompt": "계산하라.", "outputFields": ["net", "tax"]},
        home=home,
        model="gpt-5.6-luna",
        reasoning_effort="low",
        timeout_seconds=30,
        attempt_number=1,
    )

    assert captured["calculation_tools_enabled"] is True
    assert captured["web_search_enabled"] is False
    assert "OUTPUT_JSON_SHAPE" in captured["query"]
    assert record["prediction"] == {"net": 90, "tax": 10}
    assert record["promptIdentity"]["sourceItemId"] == "calc-1"
    assert record["promptIdentity"]["builderId"] == "structured_calculation_query_v1"
    assert record["promptIdentity"]["modelInputSha256"] == hashlib.sha256(
        captured["query"].encode("utf-8")
    ).hexdigest()
    assert record["toolBoundaryAudit"]["calculationCommandAudit"]["passed"] is True
    assert record["error"] == ""


def test_run_attempt_can_disable_calculation_tools_for_direct_baseline(tmp_path, monkeypatch):
    captured = {}

    class FakeClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def complete(self, messages, *, model):
            captured["query"] = messages[0]["content"]
            return '{"answer":42}'

        def consume_last_call_trace(self):
            return {"tokenUsage": {"totalTokens": 7}, "codexJsonlInvalidLineCount": 0}

    monkeypatch.setattr(run_codex_home_pool, "CodexExecLLMClient", FakeClient)
    home = run_codex_home_pool.load_unique_homes([_home(tmp_path, ".codex-7", "auth-7")])[0]

    record = run_codex_home_pool._run_attempt(
        manifest={"benchmarkId": "calc.v1", "taskType": "structured_calculation", "language": "ko"},
        case={"id": "calc-1", "prompt": "6 곱하기 7", "outputFields": ["answer"]},
        home=home,
        model="gpt-5.6-luna",
        reasoning_effort="low",
        timeout_seconds=30,
        attempt_number=1,
        calculation_tools_enabled=False,
    )

    assert captured["calculation_tools_enabled"] is False
    assert "도구를 호출하지 말고 직접 계산하라" in captured["query"]
    assert record["calculationToolsEnabled"] is False
    assert record["toolBoundaryAudit"]["calculationCommandAudit"]["passed"] is True
    assert record["prediction"] == {"answer": 42}
    assert record["error"] == ""


def test_calculation_command_audit_rejects_host_access_and_missing_verification():
    safe = run_codex_home_pool.audit_calculation_command_events(
        [{"command": "python3 -c 'from decimal import Decimal; print(Decimal(6)*7)'", "status": "completed", "exitCode": 0}],
        required=True,
    )
    host_read = run_codex_home_pool.audit_calculation_command_events(
        [{"command": "python3 -c 'print(open(\"private.json\").read())'", "status": "completed", "exitCode": 0}],
        required=True,
    )
    missing = run_codex_home_pool.audit_calculation_command_events([], required=True)

    assert safe["passed"] is True
    assert host_read["passed"] is False
    assert "calculation_command_host_access_pattern" in host_read["violations"]
    assert missing["passed"] is False
    assert "required_exactly_one_calculation_command" in missing["violations"]


def test_native_agent_command_audit_allows_workspace_work_and_rejects_host_or_network_bypass():
    safe = run_codex_home_pool.audit_agent_workspace_command_events(
        [
            {
                "command": "/usr/bin/bash -lc \"sed -n '1,240p' .agents/skills/example/SKILL.md\"",
                "status": "completed",
                "exitCode": 0,
            },
            {"command": "python3 verify.py", "status": "completed", "exitCode": 0},
        ]
    )
    host_read = run_codex_home_pool.audit_agent_workspace_command_events(
        [{"command": "python3 -c \"print(open('/home/pineapple/private.json').read())\"", "status": "completed"}]
    )
    network = run_codex_home_pool.audit_agent_workspace_command_events(
        [{"command": "curl https://example.com", "status": "completed"}]
    )
    symlink = run_codex_home_pool.audit_agent_workspace_command_events(
        [{"command": "ln -s /etc/passwd copied.txt", "status": "completed"}]
    )

    assert safe["passed"] is True
    assert host_read["passed"] is False
    assert network["passed"] is False
    assert symlink["passed"] is False
    assert host_read["violations"] == ["agent_command_host_secret_network_or_link_pattern"]


def test_domain_evidence_mcp_audit_accepts_general_queries_and_rejects_question_lookup():
    question = "타인 명의 휴대전화와 인증번호를 넘겨 범죄 피해가 발생한 경우 어떤 책임이 문제되는가?"
    safe = run_codex_home_pool.audit_domain_evidence_mcp_trace(
        {
            "codexJsonlInvalidLineCount": 0,
            "mcpToolEvents": [
                {
                    "server": "domain_evidence",
                    "tool": "search_domain_evidence",
                    "status": "completed",
                    "arguments": {
                        "query": "전자금융 접근매체 양도 형사책임",
                        "product": "lawkey",
                        "language": "ko",
                        "limit": 3,
                        "snippet_chars": 600,
                    },
                },
                {
                    "server": "domain_evidence",
                    "tool": "get_domain_source",
                    "status": "completed",
                    "arguments": {"source_id": "lawkey:abc123", "product": "lawkey", "snippet_chars": 600},
                },
            ],
        },
        public_question=question,
        expected_product="lawkey",
    )
    copied = run_codex_home_pool.audit_domain_evidence_mcp_trace(
        {
            "mcpToolEvents": [
                {
                    "server": "domain_evidence",
                    "tool": "search_domain_evidence",
                    "status": "completed",
                    "arguments": {"query": question, "product": "lawkey"},
                }
            ]
        },
        public_question=question,
        expected_product="lawkey",
    )
    unauditable = run_codex_home_pool.audit_domain_evidence_mcp_trace(
        {"mcpToolEvents": [{"server": "domain_evidence", "tool": "search_domain_evidence", "status": "completed"}]},
        public_question=question,
        expected_product="lawkey",
    )
    rephrased_case = run_codex_home_pool.audit_domain_evidence_mcp_trace(
        {
            "mcpToolEvents": [
                {
                    "server": "domain_evidence",
                    "tool": "search_domain_evidence",
                    "status": "completed",
                    "arguments": {
                        "query": "고령 남성의 피부 벌레감, 식욕부진, 구강건조, 무한증에 해당하는 한의학적 병기",
                        "product": "tcm",
                    },
                }
            ]
        },
        public_question=(
            "71세 남자가 몸에 벌레가 기어다니는 것 같다며 병원에 왔다. "
            "오랫동안 음식을 먹지 못했고 입이 마르며 땀이 나지 않는다고 한다. 병기는?"
        ),
        expected_product="tcm",
    )

    assert safe["passed"] is True
    assert safe["completedSearchSeen"] is True
    assert copied["passed"] is False
    assert copied["eventAudits"][0]["queryAudits"][0]["rawQuestionUsedAsSearchQuery"] is True
    assert unauditable["passed"] is False
    assert "domain_evidence_arguments_not_auditable" in unauditable["violations"]
    assert rephrased_case["passed"] is False
    assert "question_facts_rephrased_as_answer_lookup" in rephrased_case["violations"]


def test_domain_evidence_mcp_audit_covers_beta6_query_and_keyword_arguments():
    question = "타인 명의 휴대전화와 인증번호를 넘겨 범죄 피해가 발생한 경우 어떤 책임이 문제되는가?"
    safe = run_codex_home_pool.audit_domain_evidence_mcp_trace(
        {
            "mcpToolEvents": [
                {
                    "server": "domain_evidence",
                    "tool": "search_beta6_evidence_frontier",
                    "status": "completed",
                    "arguments": {
                        "query": "전자금융 접근매체 양도 형사책임",
                        "keywords": ["접근매체 양도", "전자금융거래법 형사책임"],
                        "product": "lawkey",
                        "limit": 8,
                        "snippet_chars": 600,
                    },
                }
            ]
        },
        public_question=question,
        expected_product="lawkey",
    )
    copied_keyword = run_codex_home_pool.audit_domain_evidence_mcp_trace(
        {
            "mcpToolEvents": [
                {
                    "server": "domain_evidence",
                    "tool": "search_beta6_evidence_frontier",
                    "status": "completed",
                    "arguments": {
                        "query": "전자금융 일반 법리",
                        "keywords": [question],
                        "product": "lawkey",
                    },
                }
            ]
        },
        public_question=question,
        expected_product="lawkey",
    )

    assert safe["passed"] is True
    assert safe["queryCount"] == 3
    assert copied_keyword["passed"] is False
    assert copied_keyword["eventAudits"][0]["queryAudits"][1]["rawQuestionUsedAsSearchQuery"] is True


def test_native_agent_attempt_uses_approved_skills_and_optional_audited_tools(tmp_path, monkeypatch):
    captured = {}

    class FakeNativeAgentClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def complete(self, messages, *, model):
            captured["query"] = messages[0]["content"]
            captured["model"] = model
            return '{"finalAnswer":"전자금융거래법상 접근매체 관련 책임"}'

        def consume_last_call_trace(self):
            return {
                "codexJsonlInvalidLineCount": 0,
                "commandExecutionEvents": [
                    {
                        "command": "/usr/bin/bash -lc \"sed -n '1,200p' .agents/skills/solve-with-domain-evidence/SKILL.md\"",
                        "status": "completed",
                        "exitCode": 0,
                    }
                ],
                "mcpToolEvents": [
                    {
                        "server": "domain_evidence",
                        "tool": "search_domain_evidence",
                        "status": "completed",
                        "arguments": {
                            "query": "전자금융 접근매체 양도 형사책임",
                            "product": "lawkey",
                            "language": "ko",
                            "limit": 3,
                            "snippet_chars": 600,
                        },
                    }
                ],
                "webSearchEvents": [],
                "workspaceArtifacts": [],
                "tokenUsage": {"totalTokens": 1234},
            }

    monkeypatch.setattr(run_codex_home_pool, "CodexExecLLMClient", FakeNativeAgentClient)
    home = run_codex_home_pool.load_unique_homes([_home(tmp_path, ".codex-7", "auth-7")])[0]
    record = run_codex_home_pool._run_attempt(
        manifest={"benchmarkId": "open.v2", "taskType": "open_response", "product": "lawkey", "language": "ko"},
        case={"id": "q1", "prompt": "타인 명의 휴대전화 인증수단을 넘긴 경우 어떤 책임이 문제되는가?"},
        home=home,
        model="gpt-5.6-luna",
        reasoning_effort="low",
        timeout_seconds=60,
        attempt_number=1,
        web_search_enabled=True,
        domain_evidence_mcp_enabled=True,
        native_agent_enabled=True,
    )

    assert captured["skill_paths"] == list(run_codex_home_pool.NATIVE_AGENT_APPROVED_SKILL_PATHS)
    assert captured["agent_workspace_enabled"] is True
    assert captured["capture_workspace_artifacts"] is True
    assert "반드시 최소 1회의 일반 웹 검색" not in captured["query"]
    assert record["nativeAgentEnabled"] is True
    assert record["toolBoundaryAudit"]["agentWorkspaceCommandAudit"]["passed"] is True
    assert record["domainEvidenceAntiCheatingAudit"]["passed"] is True
    assert record["domainEvidenceToolUsed"] is True
    assert record["evidenceGatedWorkerAudit"]["disposition"] == "accept"
    assert record["evidenceGatedWorkerAudit"]["hardFailures"] == []
    assert len(record["evidenceReceipt"]["caseDigest"]) == 64
    assert "타인 명의" not in json.dumps(record["evidenceReceipt"], ensure_ascii=False)
    assert record["error"] == ""


def test_evidence_gated_native_pool_accepts_clean_worker_without_verifier(tmp_path, monkeypatch):
    public = {
        "schemaVersion": 2,
        "benchmarkId": "native.gate.fixture.v1",
        "taskType": "open_response",
        "product": "lawkey",
        "language": "ko",
        "cases": [
            {
                "id": "q1",
                "prompt": "일반 법률 효과는 무엇인가?",
                "metadata": {"openResponseConversion": {"status": "ready_hide_options"}},
            }
        ],
    }
    public_path = tmp_path / "public.json"
    public_path.write_text(json.dumps(public, ensure_ascii=False), encoding="utf-8")
    homes = run_codex_home_pool.load_unique_homes([_home(tmp_path, ".codex-7", "auth-7")])
    constructions = []

    class CleanWorkerClient:
        def __init__(self, **kwargs):
            constructions.append(kwargs)

        def complete(self, messages, *, model):
            assert "NATIVE_EVIDENCE_GATE_OUTPUT_CONTRACT" in messages[0]["content"]
            return json.dumps(
                {
                    "finalAnswer": "일반 법률상 책임",
                    "confidence": "high",
                    "uncertainties": [],
                    "competingConclusions": [],
                    "evidenceRefs": [],
                },
                ensure_ascii=False,
            )

        def consume_last_call_trace(self):
            return {
                "status": "completed",
                "modelCalls": 1,
                "tokenUsage": {"inputTokens": 80, "outputTokens": 20, "totalTokens": 100},
                "commandExecutionEvents": [],
                "mcpToolEvents": [],
                "webSearchEvents": [],
                "workspaceArtifacts": [],
            }

    monkeypatch.setattr(run_codex_home_pool, "CodexExecLLMClient", CleanWorkerClient)
    output_dir = tmp_path / "run"
    summary = run_codex_home_pool.run_pool(
        public_path=public_path,
        output_dir=output_dir,
        homes=homes,
        max_total_calls=1,
        max_case_tokens=1_000,
        native_agent_enabled=True,
        evidence_gated_verification_enabled=True,
    )

    result = json.loads((output_dir / "results" / "q1.json").read_text(encoding="utf-8"))
    receipt_rows = [
        json.loads(line)
        for line in (output_dir / "evidence_receipts.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(constructions) == 1
    assert constructions[0]["max_attempts"] == 1
    assert result["prediction"] == "일반 법률상 책임"
    assert result["evidenceGatedWorkerAudit"]["disposition"] == "accept"
    assert result["evidenceGateOutcome"]["disposition"] == "accepted_worker"
    assert result["evidenceGateOutcome"]["verifier"]["called"] is False
    assert result["modelCallCount"] == 1
    assert len(receipt_rows) == 1
    assert receipt_rows[0]["finalDisposition"] == "accepted_worker"
    assert receipt_rows[0]["accepted"] is True
    assert receipt_rows[0]["aggregateModelCalls"] == 1
    assert receipt_rows[0]["aggregateTotalTokens"] == 100
    assert "일반 법률 효과" not in json.dumps(receipt_rows[0], ensure_ascii=False)
    assert "일반 법률상 책임" not in json.dumps(receipt_rows[0], ensure_ascii=False)
    assert summary["evidenceGatedVerificationEnabled"] is True
    assert summary["total"]["modelCalls"] == 1


def test_compact_native_skill_briefing_disables_workspace_and_records_model_selected_skill(
    tmp_path, monkeypatch
):
    captured = {}

    class CompactClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def complete(self, messages, *, model):
            captured["query"] = messages[0]["content"]
            return json.dumps(
                {
                    "finalAnswer": "근거 기반 답",
                    "confidence": "high",
                    "uncertainties": [],
                    "competingConclusions": [],
                    "evidenceRefs": [],
                    "selectedSkillNames": ["solve-with-domain-evidence"],
                },
                ensure_ascii=False,
            )

        def consume_last_call_trace(self):
            return {
                "status": "completed",
                "modelCalls": 1,
                "tokenUsage": {"totalTokens": 500},
                "skillsAvailable": [
                    {
                        "name": "solve-with-domain-evidence",
                        "treeSha256": "a" * 64,
                        "fileCount": 2,
                        "deliveryMode": "inline_description_only",
                    }
                ],
                "commandExecutionEvents": [],
                "mcpToolEvents": [],
                "webSearchEvents": [],
                "workspaceArtifacts": [],
            }

    monkeypatch.setattr(run_codex_home_pool, "CodexExecLLMClient", CompactClient)
    home = run_codex_home_pool.load_unique_homes([_home(tmp_path, ".codex-7", "auth-7")])[0]
    record = run_codex_home_pool._run_attempt(
        manifest={"benchmarkId": "open.v2", "taskType": "open_response", "product": "tcm"},
        case={"id": "q1", "prompt": "공개 개념 질문"},
        home=home,
        model="gpt-5.6-luna",
        reasoning_effort="low",
        timeout_seconds=60,
        attempt_number=1,
        max_case_tokens=1_000,
        native_agent_enabled=True,
        evidence_gated_verification_enabled=True,
        compact_native_skill_briefing_enabled=True,
    )

    assert captured["agent_workspace_enabled"] is False
    assert captured["capture_workspace_artifacts"] is True
    assert captured["compact_skill_briefing_enabled"] is True
    assert "selectedSkillNames" in captured["query"]
    assert record["compactNativeSkillBriefingEnabled"] is True
    assert record["workerAssessment"]["selectedSkillNames"] == ["solve-with-domain-evidence"]
    assert record["evidenceReceipt"]["selectedSkillNames"] == ["solve-with-domain-evidence"]
    bindings = record["evidenceReceipt"]["claimContract"]["claims"][0]["evidenceBindings"]
    assert [binding["kind"] for binding in bindings] == ["skill_tree", "tool_boundary_audit"]
    assert bindings[0]["sha256"] == "a" * 64
    assert record["error"] == ""


def test_evidence_gated_native_attempt_calls_one_closed_verifier_sequentially_and_repairs(
    tmp_path, monkeypatch
):
    events = []
    construction_kwargs = []
    verifier_queries = []

    class SequentialClient:
        def __init__(self, **kwargs):
            self.index = len(construction_kwargs)
            construction_kwargs.append(kwargs)
            events.append(f"init-{self.index}")

        def complete(self, messages, *, model):
            events.append(f"complete-{self.index}")
            if self.index == 0:
                return json.dumps(
                    {
                        "finalAnswer": "초안",
                        "confidence": "low",
                        "uncertainties": ["법적 효과가 둘로 갈릴 수 있음"],
                        "competingConclusions": ["초안", "수정답"],
                        "evidenceRefs": ["public-source-1"],
                    },
                    ensure_ascii=False,
                )
            verifier_queries.append(messages[0]["content"])
            return '{"verdict":"repair","finalAnswer":"수정답"}'

        def consume_last_call_trace(self):
            if self.index == 0:
                return {
                    "status": "completed",
                    "modelCalls": 1,
                    "tokenUsage": {"inputTokens": 75, "outputTokens": 25, "totalTokens": 100},
                    "commandExecutionEvents": [],
                    "mcpToolEvents": [],
                    "webSearchEvents": [],
                    "workspaceArtifacts": [],
                }
            return {
                "status": "completed",
                "modelCalls": 1,
                "tokenUsage": {"inputTokens": 35, "outputTokens": 15, "totalTokens": 50},
                "commandExecutionEvents": [],
                "mcpToolEvents": [],
                "webSearchEvents": [],
            }

    monkeypatch.setattr(run_codex_home_pool, "CodexExecLLMClient", SequentialClient)
    home = run_codex_home_pool.load_unique_homes([_home(tmp_path, ".codex-7", "auth-7")])[0]
    record = run_codex_home_pool._run_attempt(
        manifest={"benchmarkId": "open.v2", "taskType": "open_response", "product": "lawkey", "language": "ko"},
        case={"id": "q1", "prompt": "공개 사실만으로 법적 효과를 답하라.", "privateGold": "절대 노출 금지"},
        home=home,
        model="gpt-5.6-luna",
        reasoning_effort="low",
        timeout_seconds=60,
        attempt_number=1,
        max_case_tokens=1_000,
        native_agent_enabled=True,
        evidence_gated_verification_enabled=True,
    )

    assert events == ["init-0", "complete-0", "init-1", "complete-1"]
    assert len(construction_kwargs) == 2
    assert construction_kwargs[1]["max_attempts"] == 1
    assert construction_kwargs[1]["web_search_enabled"] is False
    assert construction_kwargs[1]["domain_evidence_mcp_enabled"] is False
    assert construction_kwargs[1]["agent_workspace_enabled"] is False
    assert construction_kwargs[1]["skill_paths"] == []
    assert "절대 노출 금지" not in verifier_queries[0]
    assert record["prediction"] == "수정답"
    assert record["error"] == ""
    assert record["evidenceGatedWorkerAudit"]["disposition"] == "verify"
    assert record["evidenceGateOutcome"]["disposition"] == "accepted_verifier_repair"
    assert record["evidenceReceipt"]["verifier"]["modelCalls"] == 1
    assert record["modelCallCount"] == 2
    assert record["modelTrace"]["tokenUsage"]["totalTokens"] == 150
    assert [phase["phaseRole"] for phase in record["modelTrace"]["phases"]] == [
        "native_worker",
        "closed_tool_verifier",
    ]


def test_evidence_gate_never_verifies_worker_after_problem_lookup_violation(tmp_path, monkeypatch):
    question = "타인 명의 인증수단을 넘긴 경우 어떤 책임이 문제되는가?"
    constructions = []

    class CheatingWorkerClient:
        def __init__(self, **kwargs):
            constructions.append(kwargs)

        def complete(self, messages, *, model):
            return json.dumps(
                {
                    "finalAnswer": "초안",
                    "confidence": "low",
                    "uncertainties": ["확인 필요"],
                    "competingConclusions": [],
                    "evidenceRefs": [],
                },
                ensure_ascii=False,
            )

        def consume_last_call_trace(self):
            return {
                "status": "completed",
                "modelCalls": 1,
                "tokenUsage": {"totalTokens": 100},
                "commandExecutionEvents": [],
                "mcpToolEvents": [],
                "webSearchEvents": [{"query": question, "action": {"type": "search", "query": question}}],
                "workspaceArtifacts": [],
            }

    monkeypatch.setattr(run_codex_home_pool, "CodexExecLLMClient", CheatingWorkerClient)
    home = run_codex_home_pool.load_unique_homes([_home(tmp_path, ".codex-7", "auth-7")])[0]
    record = run_codex_home_pool._run_attempt(
        manifest={"benchmarkId": "open.v2", "taskType": "open_response", "product": "lawkey", "language": "ko"},
        case={"id": "q1", "prompt": question},
        home=home,
        model="gpt-5.6-luna",
        reasoning_effort="low",
        timeout_seconds=60,
        attempt_number=1,
        web_search_enabled=True,
        max_case_tokens=1_000,
        native_agent_enabled=True,
        evidence_gated_verification_enabled=True,
    )

    assert len(constructions) == 1
    assert record["error"] == "web_search_anti_cheating_audit_failed"
    assert record["evidenceGatedWorkerAudit"]["disposition"] == "reject"
    assert record["evidenceGateOutcome"]["disposition"] == "rejected_policy"
    assert record["evidenceGateOutcome"]["verifier"]["status"] == "forbidden_after_policy_failure"


def test_evidence_gate_abstains_when_closed_verifier_trace_uses_a_tool(tmp_path, monkeypatch):
    constructions = []

    class ToolUsingVerifierClient:
        def __init__(self, **kwargs):
            self.index = len(constructions)
            constructions.append(kwargs)

        def complete(self, messages, *, model):
            if self.index == 0:
                return json.dumps(
                    {
                        "finalAnswer": "보존할 작업자 답",
                        "confidence": "low",
                        "uncertainties": ["검증 필요"],
                        "competingConclusions": [],
                        "evidenceRefs": [],
                    },
                    ensure_ascii=False,
                )
            return '{"verdict":"accept_worker"}'

        def consume_last_call_trace(self):
            base = {
                "status": "completed",
                "modelCalls": 1,
                "tokenUsage": {"totalTokens": 50},
                "mcpToolEvents": [],
                "webSearchEvents": [],
            }
            if self.index == 0:
                return {**base, "commandExecutionEvents": [], "workspaceArtifacts": []}
            return {
                **base,
                "commandExecutionEvents": [
                    {"command": "python3 -c 'print(1)'", "status": "completed", "exitCode": 0}
                ],
            }

    monkeypatch.setattr(run_codex_home_pool, "CodexExecLLMClient", ToolUsingVerifierClient)
    home = run_codex_home_pool.load_unique_homes([_home(tmp_path, ".codex-7", "auth-7")])[0]
    record = run_codex_home_pool._run_attempt(
        manifest={"benchmarkId": "open.v2", "taskType": "open_response", "product": "tcm", "language": "ko"},
        case={"id": "q1", "prompt": "일반 개념을 답하라."},
        home=home,
        model="gpt-5.6-luna",
        reasoning_effort="low",
        timeout_seconds=60,
        attempt_number=1,
        max_case_tokens=1_000,
        native_agent_enabled=True,
        evidence_gated_verification_enabled=True,
    )

    assert len(constructions) == 2
    assert record["prediction"] == "보존할 작업자 답"
    assert record["error"] == "evidence_gate_abstained"
    assert record["evidenceGateOutcome"]["accepted"] is False
    assert record["evidenceGateOutcome"]["verifier"]["status"] == "failed_audit"
    assert record["evidenceGateOutcome"]["verifier"]["audit"]["violations"] == [
        "closed_tool_verifier_used:commandExecutionEvents"
    ]


def test_evidence_gate_rejects_worker_and_verifier_combined_token_overrun(tmp_path, monkeypatch):
    constructions = []

    class BudgetClient:
        def __init__(self, **kwargs):
            self.index = len(constructions)
            constructions.append(kwargs)

        def complete(self, messages, *, model):
            if self.index == 0:
                return json.dumps(
                    {
                        "finalAnswer": "초안",
                        "confidence": "low",
                        "uncertainties": ["검증 필요"],
                        "competingConclusions": [],
                        "evidenceRefs": [],
                    },
                    ensure_ascii=False,
                )
            return '{"verdict":"repair","finalAnswer":"수정답"}'

        def consume_last_call_trace(self):
            trace = {
                "status": "completed",
                "modelCalls": 1,
                "tokenUsage": {"totalTokens": 80 if self.index == 0 else 50},
                "commandExecutionEvents": [],
                "mcpToolEvents": [],
                "webSearchEvents": [],
            }
            if self.index == 0:
                trace["workspaceArtifacts"] = []
            return trace

    monkeypatch.setattr(run_codex_home_pool, "CodexExecLLMClient", BudgetClient)
    home = run_codex_home_pool.load_unique_homes([_home(tmp_path, ".codex-7", "auth-7")])[0]
    record = run_codex_home_pool._run_attempt(
        manifest={"benchmarkId": "open.v2", "taskType": "open_response", "product": "tcm", "language": "ko"},
        case={"id": "q1", "prompt": "일반 개념을 답하라."},
        home=home,
        model="gpt-5.6-luna",
        reasoning_effort="low",
        timeout_seconds=60,
        attempt_number=1,
        max_case_tokens=100,
        native_agent_enabled=True,
        evidence_gated_verification_enabled=True,
    )

    assert record["prediction"] == "초안"
    assert record["modelTrace"]["tokenUsage"]["totalTokens"] == 130
    assert record["error"] == "case_token_budget_exceeded:130>100"
    assert record["evidenceGateOutcome"]["accepted"] is False
    assert record["evidenceGateOutcome"]["disposition"] == "rejected_combined_budget"


def test_evidence_gate_verifier_quota_error_fails_over_to_next_home(tmp_path, monkeypatch):
    public = {
        "schemaVersion": 2,
        "benchmarkId": "native.gate.failover.v1",
        "taskType": "open_response",
        "product": "lawkey",
        "language": "ko",
        "cases": [
            {
                "id": "q1",
                "prompt": "일반 법률 효과는 무엇인가?",
                "metadata": {"openResponseConversion": {"status": "ready_hide_options"}},
            }
        ],
    }
    public_path = tmp_path / "public.json"
    public_path.write_text(json.dumps(public, ensure_ascii=False), encoding="utf-8")
    homes = run_codex_home_pool.load_unique_homes(
        [_home(tmp_path, ".codex-7", "auth-7"), _home(tmp_path, ".codex-6", "auth-6")]
    )
    constructions = []

    class FailoverClient:
        def __init__(self, **kwargs):
            self.index = len(constructions)
            constructions.append((os.environ.get("CODEX_HOME"), kwargs))

        def complete(self, messages, *, model):
            if self.index == 0:
                return json.dumps(
                    {
                        "finalAnswer": "첫 홈 초안",
                        "confidence": "low",
                        "uncertainties": ["검증 필요"],
                        "competingConclusions": [],
                        "evidenceRefs": [],
                    },
                    ensure_ascii=False,
                )
            if self.index == 1:
                raise RuntimeError("weekly usage limit reached during verifier")
            return json.dumps(
                {
                    "finalAnswer": "두 번째 홈의 확정 답",
                    "confidence": "high",
                    "uncertainties": [],
                    "competingConclusions": [],
                    "evidenceRefs": [],
                },
                ensure_ascii=False,
            )

        def consume_last_call_trace(self):
            trace = {
                "status": "error" if self.index == 1 else "completed",
                "modelCalls": 1,
                "tokenUsage": {"totalTokens": 50},
                "commandExecutionEvents": [],
                "mcpToolEvents": [],
                "webSearchEvents": [],
            }
            if self.index in {0, 2}:
                trace["workspaceArtifacts"] = []
            return trace

    monkeypatch.setattr(run_codex_home_pool, "CodexExecLLMClient", FailoverClient)
    output_dir = tmp_path / "run"
    summary = run_codex_home_pool.run_pool(
        public_path=public_path,
        output_dir=output_dir,
        homes=homes,
        max_total_calls=2,
        max_case_tokens=1_000,
        native_agent_enabled=True,
        evidence_gated_verification_enabled=True,
    )

    result = json.loads((output_dir / "results" / "q1.json").read_text(encoding="utf-8"))
    receipt_rows = [
        json.loads(line)
        for line in (output_dir / "evidence_receipts.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(constructions) == 3
    assert constructions[0][0].endswith(".codex-7")
    assert constructions[1][0].endswith(".codex-7")
    assert constructions[2][0].endswith(".codex-6")
    assert result["prediction"] == "두 번째 홈의 확정 답"
    assert summary["total"]["quotaFailovers"] == 1
    assert summary["total"]["caseAttempts"] == 2
    assert summary["total"]["modelCalls"] == 3
    assert summary["homes"]["auth-01"]["status"] == "quota_exhausted"
    assert [row["finalDisposition"] for row in receipt_rows] == ["abstained", "accepted_worker"]
    assert receipt_rows[0]["verifier"]["modelCalls"] == 1
    assert "weekly usage limit" not in json.dumps(receipt_rows[0], ensure_ascii=False)


def test_run_attempt_can_enable_web_and_allowlisted_domain_mcp(tmp_path, monkeypatch):
    captured = {}

    class FakeClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def complete(self, messages, *, model):
            return '{"finalAnswer":"근거 기반 답"}'

        def consume_last_call_trace(self):
            return {"mcpToolEvents": [{"tool": "search_domain_evidence", "status": "completed"}]}

    monkeypatch.setattr(run_codex_home_pool, "CodexExecLLMClient", FakeClient)
    home = run_codex_home_pool.load_unique_homes([_home(tmp_path, ".codex-7", "auth-7")])[0]

    record = run_codex_home_pool._run_attempt(
        manifest={"benchmarkId": "open.v2", "taskType": "open_response", "product": "tcm", "language": "ko"},
        case={"id": "q1", "prompt": "근거를 찾아 답하라."},
        home=home,
        model="gpt-5.6-luna",
        reasoning_effort="low",
        timeout_seconds=30,
        attempt_number=1,
        web_search_enabled=True,
        domain_evidence_mcp_enabled=True,
    )

    assert captured["web_search_enabled"] is True
    assert captured["domain_evidence_mcp_enabled"] is True
    assert captured["domain_evidence_repo_root"] == run_codex_home_pool.REPO_ROOT
    assert captured["domain_evidence_product"] == "tcm"
    assert record["prediction"] == "근거 기반 답"
    assert record["domainEvidenceToolUsed"] is True


def test_pure_web_attempt_requires_search_and_rejects_direct_problem_lookup(tmp_path, monkeypatch):
    question = "건축업자가 규격 타일 대금을 먼저 내고 60일 뒤 받는 계약은 무엇인가요?"

    class CopyingWebClient:
        def __init__(self, **kwargs):
            pass

        def complete(self, messages, *, model):
            return '{"finalAnswer":"살람"}'

        def consume_last_call_trace(self):
            return {"webSearchEvents": [{"query": question, "action": {"type": "search", "query": question}}]}

    monkeypatch.setattr(run_codex_home_pool, "CodexExecLLMClient", CopyingWebClient)
    home = run_codex_home_pool.load_unique_homes([_home(tmp_path, ".codex-7", "auth-7")])[0]
    record = run_codex_home_pool._run_attempt(
        manifest={"benchmarkId": "open.v2", "taskType": "open_response", "product": "islam", "language": "ko"},
        case={"id": "q1", "prompt": question},
        home=home,
        model="gpt-5.6-luna",
        reasoning_effort="low",
        timeout_seconds=30,
        attempt_number=1,
        web_search_enabled=True,
    )

    assert record["prediction"] == "살람"
    assert record["error"] == "web_search_anti_cheating_audit_failed"
    assert record["webSearchAntiCheatingAudit"]["allQueriesPassed"] is False
    assert record["webSearchAntiCheatingAudit"]["rawQuestionUsedAsSearchQuery"] is True


def test_pure_web_attempt_accepts_short_general_concept_query(tmp_path, monkeypatch):
    class SafeWebClient:
        def __init__(self, **kwargs):
            pass

        def complete(self, messages, *, model):
            return '{"finalAnswer":"살람"}'

        def consume_last_call_trace(self):
            return {
                "webSearchEvents": [
                    {"query": "이슬람 금융 선지급 후인도 계약", "action": {"type": "search", "query": "이슬람 금융 선지급 후인도 계약"}}
                ]
            }

    monkeypatch.setattr(run_codex_home_pool, "CodexExecLLMClient", SafeWebClient)
    home = run_codex_home_pool.load_unique_homes([_home(tmp_path, ".codex-7", "auth-7")])[0]
    record = run_codex_home_pool._run_attempt(
        manifest={"benchmarkId": "open.v2", "taskType": "open_response", "product": "islam", "language": "ko"},
        case={"id": "q1", "prompt": "건축업자가 규격 타일 대금을 먼저 내고 60일 뒤 받는 계약은 무엇인가요?"},
        home=home,
        model="gpt-5.6-luna",
        reasoning_effort="low",
        timeout_seconds=30,
        attempt_number=1,
        web_search_enabled=True,
    )

    assert record["error"] == ""
    assert record["webSearchAntiCheatingAudit"]["allQueriesPassed"] is True
    assert record["webSearchAntiCheatingAudit"]["queryCount"] == 1


def test_web_search_audit_rejects_exam_item_answer_lookup_variants():
    question = "건축업자가 규격 타일 대금을 먼저 내고 60일 뒤 받는 계약은 무엇인가요?"

    for query in (
        "CISI q087 answer",
        "CISI question 87 solution",
        "CISI item 87 Quizlet",
        "CISI 87번 정답 해설",
    ):
        audit = run_codex_home_pool.audit_web_search_trace(
            {"webSearchEvents": [{"query": query}]},
            public_question=question,
        )
        assert audit["allQueriesPassed"] is False
        assert audit["queryAudits"][0]["forbiddenExamOrAnswerLookup"] is True
        assert "forbidden_exam_or_answer_lookup" in audit["queryAudits"][0]["violations"]


def test_pure_web_attempt_rejects_shell_or_mcp_bypass(tmp_path, monkeypatch):
    class BypassClient:
        def __init__(self, **kwargs):
            pass

        def complete(self, messages, *, model):
            return '{"finalAnswer":"살람"}'

        def consume_last_call_trace(self):
            return {
                "webSearchEvents": [{"query": "이슬람 금융 선지급 후인도 계약"}],
                "commandExecutionEvents": [{"command": "curl https://example.invalid", "status": "completed"}],
                "mcpToolEvents": [{"tool": "unapproved_search", "status": "completed"}],
            }

    monkeypatch.setattr(run_codex_home_pool, "CodexExecLLMClient", BypassClient)
    home = run_codex_home_pool.load_unique_homes([_home(tmp_path, ".codex-7", "auth-7")])[0]
    record = run_codex_home_pool._run_attempt(
        manifest={"benchmarkId": "open.v2", "taskType": "open_response", "product": "islam", "language": "ko"},
        case={"id": "q1", "prompt": "건축업자가 규격 타일 대금을 먼저 내고 60일 뒤 받는 계약은 무엇인가요?"},
        home=home,
        model="gpt-5.6-luna",
        reasoning_effort="low",
        timeout_seconds=30,
        attempt_number=1,
        web_search_enabled=True,
    )

    assert record["error"] == "tool_boundary_audit_failed"
    assert record["toolBoundaryAudit"]["passed"] is False
    assert record["toolBoundaryAudit"]["violations"] == [
        "shell_command_without_calculation_authorization",
        "mcp_call_without_domain_evidence_authorization",
    ]


def test_web_search_audit_rejects_answer_site_open_question_url_and_damaged_trace():
    question = "건축업자가 규격 타일 대금을 먼저 내고 60일 뒤 받는 계약은 무엇인가요?"
    safe_query = {"query": "이슬람 금융 선지급 후인도 계약", "action": {"type": "search"}}

    answer_site = run_codex_home_pool.audit_web_search_trace(
        {
            "webSearchEvents": [
                safe_query,
                {"action": {"type": "open_page", "url": "https://quizlet.com/example"}},
            ]
        },
        public_question=question,
    )
    assert answer_site["allQueriesPassed"] is True
    assert answer_site["allEventsPassed"] is False
    assert answer_site["passed"] is False
    assert answer_site["eventAudits"][1]["violations"] == ["forbidden_exam_or_answer_lookup"]

    copied_url = run_codex_home_pool.audit_web_search_trace(
        {
            "webSearchEvents": [
                safe_query,
                {
                    "action": {
                        "type": "open_page",
                        "url": "https://example.com/건축업자가-규격-타일-대금을-먼저-내고-60일-뒤-받는-계약은-무엇인가요",
                    }
                },
            ]
        },
        public_question=question,
    )
    assert copied_url["allEventsPassed"] is False
    assert copied_url["rawQuestionUsedAsSearchQuery"] is True

    damaged = run_codex_home_pool.audit_web_search_trace(
        {"webSearchEvents": [safe_query], "codexJsonlInvalidLineCount": 1},
        public_question=question,
    )
    assert damaged["allQueriesPassed"] is True
    assert damaged["allEventsPassed"] is True
    assert damaged["traceIntegrityPassed"] is False
    assert damaged["passed"] is False


def test_run_attempt_rejects_evidence_answer_when_required_db_search_was_not_used(tmp_path, monkeypatch):
    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def complete(self, messages, *, model):
            return '{"finalAnswer":"웹만 사용한 답"}'

        def consume_last_call_trace(self):
            return {"webSearchEvents": [{"query": "일반 검색"}], "mcpToolEvents": []}

    monkeypatch.setattr(run_codex_home_pool, "CodexExecLLMClient", FakeClient)
    home = run_codex_home_pool.load_unique_homes([_home(tmp_path, ".codex-7", "auth-7")])[0]

    record = run_codex_home_pool._run_attempt(
        manifest={"benchmarkId": "open.v2", "taskType": "open_response", "language": "ko"},
        case={"id": "q1", "prompt": "근거를 찾아 답하라."},
        home=home,
        model="gpt-5.6-luna",
        reasoning_effort="low",
        timeout_seconds=30,
        attempt_number=1,
        web_search_enabled=True,
        domain_evidence_mcp_enabled=True,
    )

    assert record["prediction"] == "웹만 사용한 답"
    assert record["domainEvidenceToolUsed"] is False
    assert record["error"] == "required_domain_evidence_tool_not_used"


def test_run_attempt_rejects_failed_required_db_search(tmp_path, monkeypatch):
    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def complete(self, messages, *, model):
            return '{"finalAnswer":"DB 호출 실패 후 생성한 답"}'

        def consume_last_call_trace(self):
            return {
                "mcpToolEvents": [
                    {"tool": "search_domain_evidence", "status": "failed"},
                ]
            }

    monkeypatch.setattr(run_codex_home_pool, "CodexExecLLMClient", FakeClient)
    home = run_codex_home_pool.load_unique_homes([_home(tmp_path, ".codex-7", "auth-7")])[0]

    record = run_codex_home_pool._run_attempt(
        manifest={"benchmarkId": "open.v2", "taskType": "open_response", "language": "ko"},
        case={"id": "q1", "prompt": "근거를 찾아 답하라."},
        home=home,
        model="gpt-5.6-luna",
        reasoning_effort="low",
        timeout_seconds=30,
        attempt_number=1,
        web_search_enabled=True,
        domain_evidence_mcp_enabled=True,
    )

    assert record["prediction"] == "DB 호출 실패 후 생성한 답"
    assert record["domainEvidenceToolUsed"] is False
    assert record["error"] == "required_domain_evidence_tool_not_completed"


def test_run_attempt_can_use_two_layer_review_harness(tmp_path, monkeypatch):
    captured = {}

    class FakeReviewClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def complete(self, messages, *, model):
            return '{"finalAnswer":"검수된 답"}'

        def consume_last_call_trace(self):
            return {"layers": 2, "tokenUsage": {"totalTokens": 20}}

    monkeypatch.setattr(run_codex_home_pool, "LunaEvidenceReviewClient", FakeReviewClient)
    home = run_codex_home_pool.load_unique_homes([_home(tmp_path, ".codex-7", "auth-7")])[0]

    record = run_codex_home_pool._run_attempt(
        manifest={"benchmarkId": "open.v2", "taskType": "open_response", "language": "ko"},
        case={"id": "q1", "prompt": "답하라."},
        home=home,
        model="gpt-5.6-luna",
        reasoning_effort="low",
        timeout_seconds=120,
        attempt_number=1,
        web_search_enabled=True,
        domain_evidence_mcp_enabled=True,
        review_pass=True,
    )

    assert captured["homes"] == [home]
    assert captured["total_timeout_seconds"] == 120
    assert record["reviewPassEnabled"] is True
    assert record["prediction"] == "검수된 답"
    assert record["modelTrace"]["layers"] == 2


def test_run_attempt_can_use_closed_tool_hypothesis_adjudication(tmp_path, monkeypatch):
    captured = {}

    class FakeHypothesisClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def complete(self, messages, *, model):
            return '{"finalAnswer":"가설 판정 답"}'

        def consume_last_call_trace(self):
            return {"modelCalls": 2, "layers": 2, "tokenUsage": {"totalTokens": 24}}

    monkeypatch.setattr(run_codex_home_pool, "LunaHypothesisAdjudicationClient", FakeHypothesisClient)
    home = run_codex_home_pool.load_unique_homes([_home(tmp_path, ".codex-7", "auth-7")])[0]

    record = run_codex_home_pool._run_attempt(
        manifest={"benchmarkId": "open.v2", "taskType": "open_response", "language": "ko"},
        case={"id": "q1", "prompt": "답하라."},
        home=home,
        model="gpt-5.6-luna",
        reasoning_effort="low",
        timeout_seconds=120,
        attempt_number=1,
        hypothesis_adjudication=True,
    )

    assert captured["homes"] == [home]
    assert captured["total_timeout_seconds"] == 120
    assert record["hypothesisAdjudicationEnabled"] is True
    assert record["prediction"] == "가설 판정 답"
    assert record["modelCallCount"] == 2


def test_run_attempt_can_use_one_call_closed_tool_self_verify_skill(tmp_path, monkeypatch):
    captured = {}

    class FakeClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def complete(self, messages, *, model):
            captured["query"] = messages[0]["content"]
            return '{"finalAnswer":"anchoring, representativeness, availability"}'

        def consume_last_call_trace(self):
            return {"modelCalls": 1, "tokenUsage": {"totalTokens": 12}}

    monkeypatch.setattr(run_codex_home_pool, "CodexExecLLMClient", FakeClient)
    home = run_codex_home_pool.load_unique_homes([_home(tmp_path, ".codex-7", "auth-7")])[0]

    record = run_codex_home_pool._run_attempt(
        manifest={"benchmarkId": "open.v2", "taskType": "open_response", "product": "psych", "language": "en"},
        case={"id": "q1", "prompt": "Name the three heuristics in order."},
        home=home,
        model="gpt-5.6-luna",
        reasoning_effort="low",
        timeout_seconds=120,
        attempt_number=1,
        single_pass_self_verify=True,
    )

    assert captured["web_search_enabled"] is False
    assert captured["domain_evidence_mcp_enabled"] is False
    assert "privately form three distinct candidate answers" in captured["query"]
    assert record["singlePassSelfVerifyEnabled"] is True
    assert record["prediction"] == "anchoring, representativeness, availability"
    assert record["modelCallCount"] == 1


def test_run_attempt_can_use_hash_bound_domain_classification_skill(tmp_path, monkeypatch):
    captured = {}

    class FakeClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def complete(self, messages, *, model):
            captured["query"] = messages[0]["content"]
            return '{"finalAnswer":"유효하지만 시행할 수 없음"}'

        def consume_last_call_trace(self):
            return {"modelCalls": 1, "tokenUsage": {"totalTokens": 12}}

    monkeypatch.setattr(run_codex_home_pool, "CodexExecLLMClient", FakeClient)
    home = run_codex_home_pool.load_unique_homes([_home(tmp_path, ".codex-7", "auth-7")])[0]

    record = run_codex_home_pool._run_attempt(
        manifest={"benchmarkId": "open.v2", "taskType": "open_response", "product": "islam", "language": "ko"},
        case={"id": "q1", "prompt": "계약의 효력과 시행 가능성은?"},
        home=home,
        model="gpt-5.6-luna",
        reasoning_effort="low",
        timeout_seconds=120,
        attempt_number=1,
        include_public_product_context=True,
        preserve_domain_classification=True,
    )

    assert captured["web_search_enabled"] is False
    assert captured["domain_evidence_mcp_enabled"] is False
    assert "공개 분야: 이슬람학" in captured["query"]
    assert "유효·무효" in captured["query"]
    assert record["domainClassificationSkillEnabled"] is True
    assert record["domainClassificationSkillVersion"] == "preserve-domain-classification-v1"
    assert len(record["domainClassificationSkillSha256"]) == 64
    assert record["prediction"] == "유효하지만 시행할 수 없음"
    assert record["modelCallCount"] == 1


def test_promoted_domain_classification_route_only_enables_skill_for_implicit_islam_case(tmp_path, monkeypatch):
    queries = []

    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        def complete(self, messages, *, model):
            queries.append(messages[0]["content"])
            return '{"finalAnswer":"계약 효과"}'

        def consume_last_call_trace(self):
            return {"modelCalls": 1, "tokenUsage": {"totalTokens": 12}}

    monkeypatch.setattr(run_codex_home_pool, "CodexExecLLMClient", FakeClient)
    home = run_codex_home_pool.load_unique_homes([_home(tmp_path, ".codex-7", "auth-7")])[0]
    manifest = {"benchmarkId": "open.v2", "taskType": "open_response", "product": "islam", "language": "ko"}

    implicit = run_codex_home_pool._run_attempt(
        manifest=manifest,
        case={"id": "q1", "prompt": "계약 당사자의 약속은 어떤 효과를 갖습니까?"},
        home=home,
        model="gpt-5.6-luna",
        reasoning_effort="low",
        timeout_seconds=120,
        attempt_number=1,
        promoted_domain_classification_route=True,
    )
    explicit = run_codex_home_pool._run_attempt(
        manifest=manifest,
        case={"id": "q2", "prompt": "무라바하 계약은 어떤 효과를 갖습니까?"},
        home=home,
        model="gpt-5.6-luna",
        reasoning_effort="low",
        timeout_seconds=120,
        attempt_number=1,
        promoted_domain_classification_route=True,
    )

    assert implicit["domainClassificationRouteMatched"] is True
    assert implicit["publicProductContextEnabled"] is True
    assert implicit["domainClassificationSkillEnabled"] is True
    assert implicit["domainClassificationRouteVersion"] == "implicit-islam-domain-v1"
    assert len(implicit["domainClassificationRouteSha256"]) == 64
    assert "공개 분야: 이슬람학" in queries[0]
    assert "유효·무효" in queries[0]
    assert explicit["domainClassificationRouteMatched"] is False
    assert explicit["publicProductContextEnabled"] is False
    assert explicit["domainClassificationSkillEnabled"] is False
    assert "공개 분야: 이슬람학" not in queries[1]
    assert "유효·무효" not in queries[1]


def test_promoted_domain_classification_route_enables_tcm_skill_with_hash_bound_identity(tmp_path, monkeypatch):
    captured = {}

    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        def complete(self, messages, *, model):
            captured["query"] = messages[0]["content"]
            return '{"finalAnswer":"분류 답"}'

        def consume_last_call_trace(self):
            return {"modelCalls": 1, "tokenUsage": {"totalTokens": 12}}

    monkeypatch.setattr(run_codex_home_pool, "CodexExecLLMClient", FakeClient)
    home = run_codex_home_pool.load_unique_homes([_home(tmp_path, ".codex-7", "auth-7")])[0]
    record = run_codex_home_pool._run_attempt(
        manifest={"benchmarkId": "open.tcm", "taskType": "open_response", "product": "tcm", "language": "ko"},
        case={"id": "q1", "prompt": "어떤 분류에 해당합니까?"},
        home=home,
        model="gpt-5.6-luna",
        reasoning_effort="low",
        timeout_seconds=120,
        attempt_number=1,
        promoted_domain_classification_route=True,
    )

    assert record["domainClassificationRouteMatched"] is True
    assert record["publicProductContextEnabled"] is True
    assert record["domainClassificationSkillEnabled"] is True
    assert record["domainClassificationRouteVersion"] == "tcm-product-domain-v1"
    assert len(record["domainClassificationRouteSha256"]) == 64
    assert "공개 분야: 한의학" in captured["query"]
    assert "유효·무효" in captured["query"]
    assert record["modelCallCount"] == 1


def test_domain_classification_skill_requires_context_and_closed_tools(tmp_path):
    home = run_codex_home_pool.load_unique_homes([_home(tmp_path, ".codex-7", "auth-7")])[0]
    public = tmp_path / "public.json"
    public.write_text(
        json.dumps({"benchmarkId": "open.v2", "taskType": "open_response", "cases": []}),
        encoding="utf-8",
    )

    with __import__("pytest").raises(ValueError, match="requires public product context"):
        run_codex_home_pool.run_pool(
            public_path=public,
            output_dir=tmp_path / "no-context",
            homes=[home],
            preserve_domain_classification=True,
        )
    with __import__("pytest").raises(ValueError, match="standalone one-call closed-tool mode"):
        run_codex_home_pool.run_pool(
            public_path=public,
            output_dir=tmp_path / "web",
            homes=[home],
            include_public_product_context=True,
            preserve_domain_classification=True,
            web_search_enabled=True,
        )
    with __import__("pytest").raises(ValueError, match="supplies context only on matched cases"):
        run_codex_home_pool.run_pool(
            public_path=public,
            output_dir=tmp_path / "promoted-route-with-global-context",
            homes=[home],
            include_public_product_context=True,
            promoted_domain_classification_route=True,
        )


def test_run_attempt_can_use_host_prefetch_and_enforces_combined_token_cap(tmp_path, monkeypatch):
    captured = {}
    db_path = tmp_path / "tcm.sqlite3"
    db_path.write_bytes(b"fixture")

    class FakeHostPrefetchClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def complete(self, messages, *, model):
            return '{"finalAnswer":"소승기탕"}'

        def consume_last_call_trace(self):
            query_audit = run_codex_home_pool.audit_concept_query("소승기탕", public_question="답하라.")
            return {
                "status": "completed",
                "modelCalls": 2,
                "tokenUsage": {"totalTokens": 25},
                "hostPrefetch": {
                    "evidence": [{"sourceId": "s1"}],
                    "searches": [{"query": "소승기탕", **query_audit}],
                    "antiCheatingAudit": {
                        "allQueriesPassed": True,
                        "rawQuestionUsedAsSearchQuery": False,
                    },
                },
            }

    monkeypatch.setattr(run_codex_home_pool, "LunaHostPrefetchClient", FakeHostPrefetchClient)
    home = run_codex_home_pool.load_unique_homes([_home(tmp_path, ".codex-7", "auth-7")])[0]

    record = run_codex_home_pool._run_attempt(
        manifest={"benchmarkId": "open.v2", "taskType": "open_response", "product": "tcm", "language": "ko"},
        case={"id": "q1", "prompt": "답하라."},
        home=home,
        model="gpt-5.6-luna",
        reasoning_effort="low",
        timeout_seconds=120,
        attempt_number=1,
        host_domain_prefetch_enabled=True,
        domain_db_path=db_path,
        max_case_tokens=20,
    )

    assert captured["homes"] == [home]
    assert captured["db_path"] == db_path
    assert captured["product"] == "tcm"
    assert record["prediction"] == "소승기탕"
    assert record["hostDomainEvidenceUsed"] is True
    assert record["modelCallCount"] == 2
    assert record["error"] == "case_token_budget_exceeded:25>20"


def test_host_prefetch_independent_audit_rejects_forged_copy_safe_fields_and_nested_tool_events():
    question = "김진하 군수 민원인 나이를 추정해봐"
    forged = {
        "status": "completed",
        "phases": [
            {
                "webSearchEvents": [{"query": "should never run"}],
                "codexJsonlInvalidLineCount": 0,
            }
        ],
        "hostPrefetch": {
            "searches": [
                {
                    "query": "김진하 군수 민원인 나이 추정 공개자료",
                    "conceptQueryPolicyPassed": True,
                    "violations": [],
                    "rawQuestionUsedAsSearchQuery": False,
                    "publicQuestionTermMatchCount": 0,
                    "publicQuestionTermCoverage": 0.0,
                    "novelQueryTermCount": 7,
                }
            ],
            "antiCheatingAudit": {
                "allQueriesPassed": True,
                "rawQuestionUsedAsSearchQuery": False,
            },
        },
    }

    audit = run_codex_home_pool.audit_host_prefetch_trace(
        forged,
        public_question=question,
        product="lawkey",
    )

    assert audit["passed"] is False
    assert audit["recordedFieldsMatch"] is False
    assert audit["queryAudits"][0]["rawQuestionUsedAsSearchQuery"] is True
    assert run_codex_home_pool._recursive_trace_events(forged, "webSearchEvents") == [
        {"query": "should never run"}
    ]


def test_model_call_count_sums_multilayer_phases_and_retry_attempts():
    assert run_codex_home_pool._model_call_count(
        {"phases": [{"attempts": 1}, {"attempts": 2}]}
    ) == 3
    assert run_codex_home_pool._model_call_count({"modelCalls": 2, "phases": [{}, {}]}) == 2


def test_resume_modes_reject_mixing_and_model_call_telemetry_is_repaired(tmp_path):
    state = {"homes": {"auth-01": {"modelCalls": 1}}}
    run_codex_home_pool._persist_resume_modes(state, resume=False, modes={"reviewPassEnabled": True})
    with __import__("pytest").raises(ValueError, match="reviewPassEnabled"):
        run_codex_home_pool._persist_resume_modes(state, resume=True, modes={"reviewPassEnabled": False})

    attempts = tmp_path / "attempts" / "q1"
    results = tmp_path / "results"
    attempts.mkdir(parents=True)
    results.mkdir()
    payload = {
        "caseId": "q1",
        "authGroup": "auth-01",
        "modelCallCount": 1,
        "modelTrace": {"phases": [{"attempts": 1}, {"attempts": 1}]},
    }
    (attempts / "01.json").write_text(json.dumps(payload), encoding="utf-8")
    (results / "q1.json").write_text(json.dumps(payload), encoding="utf-8")

    run_codex_home_pool._reconcile_model_call_telemetry(
        state,
        attempts_dir=tmp_path / "attempts",
        result_dir=results,
    )

    assert state["actualModelCalls"] == 2
    assert state["homes"]["auth-01"]["modelCalls"] == 2
    assert json.loads((results / "q1.json").read_text(encoding="utf-8"))["modelCallCount"] == 2


def test_evidence_gated_verification_mode_is_resume_bound_and_requires_native_budget(tmp_path):
    state = {}
    run_codex_home_pool._persist_resume_modes(
        state,
        resume=False,
        modes={"evidenceGatedVerificationEnabled": True},
    )
    with __import__("pytest").raises(ValueError, match="evidenceGatedVerificationEnabled"):
        run_codex_home_pool._persist_resume_modes(
            state,
            resume=True,
            modes={"evidenceGatedVerificationEnabled": False},
        )

    public_path = tmp_path / "public.json"
    public_path.write_text(
        json.dumps(
            {
                "schemaVersion": 2,
                "benchmarkId": "open.fixture.v1",
                "taskType": "open_response",
                "cases": [],
            }
        ),
        encoding="utf-8",
    )
    homes = run_codex_home_pool.load_unique_homes([_home(tmp_path, ".codex-7", "auth-7")])
    with __import__("pytest").raises(ValueError, match="requires native agent"):
        run_codex_home_pool.run_pool(
            public_path=public_path,
            output_dir=tmp_path / "no-native",
            homes=homes,
            max_case_tokens=1_000,
            evidence_gated_verification_enabled=True,
        )
    with __import__("pytest").raises(ValueError, match="positive max_case_tokens"):
        run_codex_home_pool.run_pool(
            public_path=public_path,
            output_dir=tmp_path / "no-budget",
            homes=homes,
            native_agent_enabled=True,
            evidence_gated_verification_enabled=True,
        )


def test_pool_requires_attested_db_for_domain_mcp_and_restores_environment(tmp_path, monkeypatch):
    public = {
        "schemaVersion": 2,
        "benchmarkId": "open_response.fixture.v2",
        "taskType": "open_response",
        "product": "tcm",
        "language": "ko",
        "cases": [
            {
                "id": "q1",
                "prompt": "답하라.",
                "metadata": {"openResponseConversion": {"status": "ready_hide_options"}},
            }
        ],
    }
    public_path = tmp_path / "public.json"
    public_path.write_text(json.dumps(public, ensure_ascii=False), encoding="utf-8")
    homes = run_codex_home_pool.load_unique_homes([_home(tmp_path, ".codex-7", "auth-7")])
    db_path = tmp_path / "fixture.sqlite3"
    db_path.write_bytes(b"fixture")
    with __import__("pytest").raises(ValueError, match="domain_db_path is required"):
        run_codex_home_pool.run_pool(
            public_path=public_path,
            output_dir=tmp_path / "missing",
            homes=homes,
            domain_evidence_mcp_enabled=True,
        )
    with __import__("pytest").raises(ValueError, match="domain_db_path is required"):
        run_codex_home_pool.run_pool(
            public_path=public_path,
            output_dir=tmp_path / "missing-prefetch",
            homes=homes,
            host_domain_prefetch_enabled=True,
            max_case_tokens=100,
        )
    monkeypatch.setattr(
        run_codex_home_pool,
        "_run_attempt",
        lambda **kwargs: {"caseId": "q1", "prediction": "답", "error": "", "elapsedSec": 0.1, "modelTrace": {}},
    )
    monkeypatch.setenv("RELIGION_TCM_DB_PATH", "original-binding")

    summary = run_codex_home_pool.run_pool(
        public_path=public_path,
        output_dir=tmp_path / "allowed",
        homes=homes,
        domain_evidence_mcp_enabled=True,
        domain_db_path=db_path,
        allow_fixture_db=True,
        max_total_calls=1,
    )

    assert summary["domainDatabase"]["fixtureWarning"] is True
    assert summary["domainDatabase"]["path"] == str(db_path.resolve())
    assert os.environ["RELIGION_TCM_DB_PATH"] == "original-binding"


def test_existing_swap_override_is_strictly_one_direct_case_and_one_call():
    valid = {
        "requested": True,
        "evidence_requested": False,
        "prefetch_requested": False,
        "review_requested": False,
        "hypothesis_requested": False,
        "case_ids": ["q1"],
        "max_cases": 1,
        "max_total_calls": 1,
        "max_calls_this_invocation": 1,
        "web_search_enabled": False,
        "domain_evidence_mcp_enabled": False,
        "host_domain_prefetch_enabled": False,
        "review_pass": False,
        "hypothesis_adjudication": False,
    }

    run_codex_home_pool.validate_single_task_swap_override(**valid)

    web = {
        **valid,
        "requested": False,
        "web_requested": True,
        "web_search_enabled": True,
    }
    run_codex_home_pool.validate_single_task_swap_override(**web)
    for changed in (
        {"web_search_enabled": False},
        {"domain_evidence_mcp_enabled": True},
        {"host_domain_prefetch_enabled": True},
        {"review_pass": True},
        {"hypothesis_adjudication": True},
        {"requested": True},
    ):
        with __import__("pytest").raises(ValueError):
            run_codex_home_pool.validate_single_task_swap_override(**{**web, **changed})

    for changed in (
        {"case_ids": []},
        {"case_ids": ["q1", "q2"]},
        {"max_cases": 2},
        {"max_total_calls": 0},
        {"max_calls_this_invocation": 0},
        {"max_calls_this_invocation": 2},
        {"web_search_enabled": True},
        {"domain_evidence_mcp_enabled": True},
        {"review_pass": True},
        {"hypothesis_adjudication": True},
    ):
        kwargs = {**valid, **changed}
        with __import__("pytest").raises(ValueError):
            run_codex_home_pool.validate_single_task_swap_override(**kwargs)

    evidence = {
        **valid,
        "requested": False,
        "evidence_requested": True,
        "web_search_enabled": True,
        "domain_evidence_mcp_enabled": True,
    }
    run_codex_home_pool.validate_single_task_swap_override(**evidence)
    run_codex_home_pool.validate_single_task_swap_override(**{**evidence, "web_search_enabled": False})
    for changed in (
        {"domain_evidence_mcp_enabled": False},
        {"host_domain_prefetch_enabled": True},
        {"review_pass": True},
        {"hypothesis_adjudication": True},
        {"requested": True},
    ):
        with __import__("pytest").raises(ValueError):
            run_codex_home_pool.validate_single_task_swap_override(**{**evidence, **changed})

    prefetch = {
        **valid,
        "requested": False,
        "prefetch_requested": True,
        "host_domain_prefetch_enabled": True,
    }
    run_codex_home_pool.validate_single_task_swap_override(**prefetch)
    for changed in (
        {"host_domain_prefetch_enabled": False},
        {"web_search_enabled": True},
        {"domain_evidence_mcp_enabled": True},
        {"review_pass": True},
        {"hypothesis_adjudication": True},
        {"evidence_requested": True},
    ):
        with __import__("pytest").raises(ValueError):
            run_codex_home_pool.validate_single_task_swap_override(**{**prefetch, **changed})

    review = {
        **valid,
        "requested": False,
        "review_requested": True,
        "review_pass": True,
    }
    run_codex_home_pool.validate_single_task_swap_override(**review)
    for changed in (
        {"review_pass": False},
        {"web_search_enabled": True},
        {"domain_evidence_mcp_enabled": True},
        {"host_domain_prefetch_enabled": True},
        {"requested": True},
    ):
        with __import__("pytest").raises(ValueError):
            run_codex_home_pool.validate_single_task_swap_override(**{**review, **changed})

    hypothesis = {
        **valid,
        "requested": False,
        "hypothesis_requested": True,
        "hypothesis_adjudication": True,
    }
    run_codex_home_pool.validate_single_task_swap_override(**hypothesis)
    for changed in (
        {"hypothesis_adjudication": False},
        {"review_pass": True},
        {"web_search_enabled": True},
        {"domain_evidence_mcp_enabled": True},
        {"host_domain_prefetch_enabled": True},
        {"requested": True},
    ):
        with __import__("pytest").raises(ValueError):
            run_codex_home_pool.validate_single_task_swap_override(**{**hypothesis, **changed})

    native_evidence = {
        **valid,
        "requested": False,
        "native_evidence_requested": True,
        "native_agent_enabled": True,
        "evidence_gated_verification_enabled": True,
        "domain_evidence_mcp_enabled": True,
        "max_total_calls": 8,
    }
    run_codex_home_pool.validate_single_task_swap_override(**native_evidence)
    run_codex_home_pool.validate_single_task_swap_override(
        **{
            **native_evidence,
            "domain_evidence_mcp_enabled": False,
            "web_search_enabled": True,
        }
    )
    for changed in (
        {"native_agent_enabled": False},
        {"evidence_gated_verification_enabled": False},
        {"host_domain_prefetch_enabled": True},
        {"review_pass": True},
        {"hypothesis_adjudication": True},
        {"requested": True},
        {"evidence_requested": True},
        {"max_total_calls": 9},
    ):
        with __import__("pytest").raises(ValueError):
            run_codex_home_pool.validate_single_task_swap_override(
                **{**native_evidence, **changed}
            )


def test_pool_can_limit_each_resume_invocation_to_one_call(tmp_path, monkeypatch):
    public = {
        "schemaVersion": 2,
        "benchmarkId": "open_response.fixture.v2",
        "taskType": "open_response",
        "language": "ko",
        "cases": [
            {"id": "q1", "prompt": "첫째", "metadata": {"openResponseConversion": {"status": "ready_hide_options"}}},
            {"id": "q2", "prompt": "둘째", "metadata": {"openResponseConversion": {"status": "ready_hide_options"}}},
        ],
    }
    public_path = tmp_path / "public.json"
    public_path.write_text(json.dumps(public, ensure_ascii=False), encoding="utf-8")
    homes = run_codex_home_pool.load_unique_homes([_home(tmp_path, ".codex-7", "auth-7")])
    monkeypatch.setattr(
        run_codex_home_pool,
        "_run_attempt",
        lambda **kwargs: {
            "caseId": kwargs["case"]["id"],
            "prediction": kwargs["case"]["id"],
            "error": "",
            "elapsedSec": 0.1,
            "modelTrace": {},
        },
    )
    output_dir = tmp_path / "run"

    first = run_codex_home_pool.run_pool(
        public_path=public_path,
        output_dir=output_dir,
        homes=homes,
        max_total_calls=2,
        max_calls_this_invocation=1,
    )
    second = run_codex_home_pool.run_pool(
        public_path=public_path,
        output_dir=output_dir,
        homes=homes,
        max_total_calls=2,
        max_calls_this_invocation=1,
        resume=True,
    )

    assert first["stopReason"] == "max_calls_this_invocation_reached"
    assert second["stopReason"] == "completed_selected_cases"
    assert second["total"]["modelCalls"] == 2
    assert sorted(path.stem for path in (output_dir / "results").glob("*.json")) == ["q1", "q2"]
