from pathlib import Path

from tools import benchmark_provider


def test_codex_exec_client_is_stateless_and_records_exact_configuration(monkeypatch):
    seen = {}

    def fake_invoke(command, *, prompt, timeout, environment):
        seen["command"] = command
        seen["input"] = prompt
        seen["timeout"] = timeout
        seen["environment"] = environment
        output_path = Path(command[command.index("--output-last-message") + 1])
        output_path.write_text('{"queries":["법리"]}', encoding="utf-8")
        return benchmark_provider.subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(benchmark_provider, "_invoke_codex", fake_invoke)
    client = benchmark_provider.CodexExecLLMClient(
        default_model="gpt-5.6-luna",
        timeout_seconds=123,
        executable="codex-fixture",
        reasoning_effort="low",
        verbosity="low",
    )

    answer = client.complete(
        [{"role": "system", "content": "JSON만"}, {"role": "user", "content": "법리를 찾아라"}]
    )

    assert answer == '{"queries":["법리"]}'
    assert seen["command"][0:2] == ["codex-fixture", "exec"]
    assert "--ephemeral" in seen["command"]
    assert "--ignore-user-config" in seen["command"]
    assert "--ignore-rules" in seen["command"]
    assert "--json" in seen["command"]
    assert "read-only" in seen["command"]
    assert "gpt-5.6-luna" in seen["command"]
    assert 'model_reasoning_effort="low"' in seen["command"]
    assert 'model_verbosity="low"' in seen["command"]
    assert 'web_search="disabled"' in seen["command"]
    assert "features.shell_tool=false" in seen["command"]
    assert '"role":"system","content":"JSON만"' in seen["input"]
    assert seen["timeout"] == 123
    assert seen["environment"]["TOKIO_WORKER_THREADS"] == "1"
    assert seen["environment"]["RAYON_NUM_THREADS"] == "1"
    assert client.decoding == {
        "reasoningEffort": "low",
        "transportMaxAttempts": 2,
        "transportWorkerThreads": 1,
        "verbosity": "low",
    }
    assert client.consume_last_call_trace()["status"] == "completed"


def test_codex_exec_client_records_token_usage_for_closed_book_calls(monkeypatch):
    def fake_invoke(command, *, prompt, timeout, environment):
        del prompt, timeout, environment
        output_path = Path(command[command.index("--output-last-message") + 1])
        output_path.write_text("done", encoding="utf-8")
        stdout = '{"type":"turn.completed","usage":{"input_tokens":120,"cached_input_tokens":20,"output_tokens":30}}'
        return benchmark_provider.subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(benchmark_provider, "_invoke_codex", fake_invoke)
    client = benchmark_provider.CodexExecLLMClient(default_model="gpt-5.6-luna")

    assert client.complete([{"role": "user", "content": "answer"}]) == "done"
    trace = client.consume_last_call_trace()
    assert trace["tokenUsage"] == {
        "inputTokens": 120,
        "cachedInputTokens": 20,
        "outputTokens": 30,
        "totalTokens": 150,
    }


def test_codex_exec_client_retries_transient_transport_failure(monkeypatch):
    calls = []

    def fake_attempt(self, prompt, *, active_model, timeout, public_question_for_guard):
        del prompt, public_question_for_guard
        calls.append((active_model, timeout))
        if len(calls) == 1:
            raise RuntimeError("Resource temporarily unavailable")
        return "정답: 2"

    monkeypatch.setattr(benchmark_provider.CodexExecLLMClient, "_complete_attempt", fake_attempt)
    monkeypatch.setattr(benchmark_provider.time, "sleep", lambda _: None)
    client = benchmark_provider.CodexExecLLMClient(
        default_model="gpt-5.6-luna",
        max_attempts=2,
    )

    answer = client.complete([{"role": "user", "content": "답하라"}])

    assert answer == "정답: 2"
    assert calls == [("gpt-5.6-luna", 300.0), ("gpt-5.6-luna", 300.0)]
    trace = client.consume_last_call_trace()
    assert trace["status"] == "completed"
    assert trace["attempts"] == 2


def test_provider_factory_preserves_existing_environment_factory(monkeypatch):
    marker = object()
    monkeypatch.delenv(benchmark_provider.PROVIDER_ENV, raising=False)

    client = benchmark_provider.create_benchmark_llm_client(
        model="fixture-model",
        fallback_factory=lambda: marker,
    )

    assert client is marker


def test_provider_factory_selects_codex_exec_without_calling_fallback(monkeypatch):
    monkeypatch.setenv(benchmark_provider.PROVIDER_ENV, "codex_exec")
    monkeypatch.setenv(benchmark_provider.CODEX_REASONING_EFFORT_ENV, "high")

    client = benchmark_provider.create_benchmark_llm_client(
        model="gpt-5.6-luna",
        fallback_factory=lambda: (_ for _ in ()).throw(AssertionError("fallback called")),
    )

    assert isinstance(client, benchmark_provider.CodexExecLLMClient)
    assert client.default_model == "gpt-5.6-luna"
    assert client.decoding["reasoningEffort"] == "high"


def test_codex_exec_web_search_is_opt_in_and_records_auditable_events(monkeypatch):
    seen = {}

    def fake_invoke(command, *, prompt, timeout, environment):
        seen["command"] = command
        seen["prompt"] = prompt
        output_path = Path(command[command.index("--output-last-message") + 1])
        output_path.write_text("정답: D", encoding="utf-8")
        stdout = "\n".join(
            [
                '{"type":"item.completed","item":{"type":"web_search","query":"AAOIFI deposit ratio","action":{"type":"search","query":"AAOIFI deposit ratio"}}}',
                '{"type":"item.completed","item":{"type":"command_execution","command":"python3 -c \'print(3/10)\'","status":"completed","exit_code":0}}',
            ]
        )
        return benchmark_provider.subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(benchmark_provider, "_invoke_codex", fake_invoke)
    client = benchmark_provider.CodexExecLLMClient(
        default_model="gpt-5.6-luna",
        executable="codex-fixture",
        web_search_enabled=True,
    )

    assert client.complete([{"role": "user", "content": "비율을 구하라"}]) == "정답: D"
    assert seen["command"][0:3] == ["codex-fixture", "--search", "exec"]
    assert "--json" in seen["command"]
    configs = [seen["command"][index + 1] for index, value in enumerate(seen["command"]) if value == "--config"]
    assert "features.shell_tool=false" in configs
    assert "Never search for or open the original question sheet" in seen["prompt"]
    assert "Do not run shell commands or call MCP tools" in seen["prompt"]
    trace = client.consume_last_call_trace()
    assert trace["webSearchEnabled"] is True
    assert trace["webSearchEvents"][0]["query"] == "AAOIFI deposit ratio"
    assert trace["commandExecutionEvents"][0]["command"].startswith("python3 -c")
    assert client.decoding["webSearchEnabled"] is True
    assert "calculationToolsEnabled" not in client.decoding


def test_codex_exec_calculation_tools_can_be_enabled_without_web_search(monkeypatch):
    seen = {}

    def fake_invoke(command, *, prompt, timeout, environment):
        del timeout
        seen["command"] = command
        seen["prompt"] = prompt
        seen["environment"] = environment
        output_path = Path(command[command.index("--output-last-message") + 1])
        output_path.write_text('{"answer":42}', encoding="utf-8")
        return benchmark_provider.subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(benchmark_provider, "_invoke_codex", fake_invoke)
    client = benchmark_provider.CodexExecLLMClient(
        default_model="gpt-5.6-luna",
        calculation_tools_enabled=True,
    )

    assert client.complete([{"role": "user", "content": "6*7"}]) == '{"answer":42}'
    assert "--search" not in seen["command"]
    assert 'web_search="disabled"' in seen["command"]
    assert "features.shell_tool=false" not in seen["command"]
    assert "read-only shell commands solely" in seen["prompt"]
    assert "Never inspect local files" in seen["prompt"]
    assert client.decoding["calculationToolsEnabled"] is True
    assert "webSearchEnabled" not in client.decoding


def test_codex_exec_domain_evidence_mcp_is_allowlisted_and_shell_disabled(monkeypatch):
    seen = {}

    def fake_invoke(command, *, prompt, timeout, environment):
        del timeout
        seen["command"] = command
        seen["prompt"] = prompt
        seen["environment"] = environment
        output_path = Path(command[command.index("--output-last-message") + 1])
        output_path.write_text("근거 기반 답", encoding="utf-8")
        stdout = (
            '{"type":"item.completed","item":{"type":"mcp_tool_call","server":"domain_evidence",'
            '"tool":"search_domain_evidence","status":"completed"}}'
        )
        return benchmark_provider.subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(benchmark_provider, "_invoke_codex", fake_invoke)
    repo_root = Path(__file__).resolve().parents[1]
    client = benchmark_provider.CodexExecLLMClient(
        default_model="gpt-5.6-luna",
        domain_evidence_mcp_enabled=True,
        domain_evidence_repo_root=repo_root,
        domain_evidence_product="tcm",
    )

    assert client.complete([{"role": "user", "content": "근거를 찾아라"}]) == "근거 기반 답"
    configs = [seen["command"][index + 1] for index, value in enumerate(seen["command"]) if value == "--config"]
    assert "features.shell_tool=false" in configs
    assert any(value.startswith("mcp_servers.domain_evidence.command=") for value in configs)
    assert (
        'mcp_servers.domain_evidence.env_vars=["RELIGION_TCM_DB_PATH",'
        '"UNIVERSAL_EVAL_DOMAIN_EVIDENCE_PUBLIC_QUESTION",'
        '"UNIVERSAL_EVAL_DOMAIN_EVIDENCE_REQUIRE_QUERY_GUARD"]'
    ) in configs
    assert 'mcp_servers.domain_evidence.enabled_tools=["search_domain_evidence","get_domain_source","search_beta6_evidence_frontier"]' in configs
    assert 'mcp_servers.domain_evidence.default_tools_approval_mode="approve"' in configs
    assert "MUST call the read-only MCP tool search_domain_evidence at least once" in seen["prompt"]
    assert 'product="tcm"' in seen["prompt"]
    assert "tool has no path argument" in seen["prompt"]
    assert "limit at 3" in seen["prompt"]
    assert "form 2 to 4 plausible formula or pattern candidates" not in seen["prompt"]
    assert seen["environment"]["UNIVERSAL_EVAL_DOMAIN_EVIDENCE_PUBLIC_QUESTION"] == "근거를 찾아라"
    assert seen["environment"]["UNIVERSAL_EVAL_DOMAIN_EVIDENCE_REQUIRE_QUERY_GUARD"] == "1"
    trace = client.consume_last_call_trace()
    assert trace["domainEvidenceMcpEnabled"] is True
    assert trace["mcpToolEvents"][0]["tool"] == "search_domain_evidence"


def test_codex_jsonl_trace_preserves_bounded_mcp_error_message():
    stdout = (
        '{"type":"item.completed","item":{"type":"mcp_tool_call","server":"domain_evidence",'
        '"tool":"search_domain_evidence","status":"failed",'
        '"error":{"message":"user cancelled MCP tool call","private":"not copied"}}}'
    )

    trace = benchmark_provider._parse_codex_jsonl_trace(stdout)

    assert trace["mcpToolEvents"] == [
        {
            "eventType": "item.completed",
            "itemType": "mcp_tool_call",
            "server": "domain_evidence",
            "tool": "search_domain_evidence",
            "status": "failed",
            "errorPreview": "user cancelled MCP tool call",
            "arguments": {},
        }
    ]


def test_codex_exec_can_expose_basic_domain_db_without_beta6_frontier(monkeypatch):
    seen = {}

    def fake_invoke(command, *, prompt, timeout, environment):
        del prompt, timeout, environment
        seen["command"] = command
        output_path = Path(command[command.index("--output-last-message") + 1])
        output_path.write_text("answer", encoding="utf-8")
        return benchmark_provider.subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(benchmark_provider, "_invoke_codex", fake_invoke)
    client = benchmark_provider.CodexExecLLMClient(
        default_model="gpt-5.6-luna",
        domain_evidence_mcp_enabled=True,
        domain_beta6_frontier_enabled=False,
        domain_evidence_repo_root=Path(__file__).resolve().parents[1],
        domain_evidence_product="tcm",
    )

    client.complete([{"role": "user", "content": "public question"}])

    configs = [
        seen["command"][index + 1]
        for index, value in enumerate(seen["command"])
        if value == "--config"
    ]
    assert 'mcp_servers.domain_evidence.enabled_tools=["search_domain_evidence","get_domain_source"]' in configs
    assert not any("search_beta6_evidence_frontier" in value for value in configs)
    trace = client.consume_last_call_trace()
    assert trace["domainEvidenceMcpEnabled"] is True
    assert trace["domainBeta6FrontierEnabled"] is False
    assert client.decoding["domainBeta6FrontierEnabled"] is False


def test_codex_exec_stages_native_skills_and_quarantines_generated_workspace_code(monkeypatch, tmp_path):
    skill = tmp_path / "general-calculation-helper"
    skill.mkdir()
    (skill / "SKILL.md").write_text(
        "---\nname: general-calculation-helper\ndescription: Verify nontrivial calculations with code.\n---\n"
        "Use a small deterministic program when arithmetic is error-prone.\n",
        encoding="utf-8",
    )
    seen = {}

    def fake_invoke(command, *, prompt, timeout, environment):
        del timeout, environment
        seen["command"] = command
        seen["prompt"] = prompt
        workspace = Path(command[command.index("--cd") + 1])
        seen["staged_skill"] = (workspace / ".agents/skills/general-calculation-helper/SKILL.md").read_text(
            encoding="utf-8"
        )
        (workspace / "verify_tax.py").write_text("print(round(100 * 1.1, 2))\n", encoding="utf-8")
        host_only = tmp_path / "host-only.txt"
        host_only.write_text("must not be captured", encoding="utf-8")
        (workspace / "host-leak.txt").symlink_to(host_only)
        output_path = Path(command[command.index("--output-last-message") + 1])
        output_path.write_text("110", encoding="utf-8")
        stdout = (
            '{"type":"item.completed","item":{"type":"mcp_tool_call","server":"domain_evidence",'
            '"tool":"search_domain_evidence","status":"completed",'
            '"arguments":{"query":"부가가치세 일반 계산 원칙","product":"law"}}}'
        )
        return benchmark_provider.subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(benchmark_provider, "_invoke_codex", fake_invoke)
    repo_root = Path(__file__).resolve().parents[1]
    client = benchmark_provider.CodexExecLLMClient(
        default_model="gpt-5.6-luna",
        executable="codex-fixture",
        web_search_enabled=True,
        domain_evidence_mcp_enabled=True,
        domain_evidence_repo_root=repo_root,
        domain_evidence_product="law",
        skill_paths=[skill],
        agent_workspace_enabled=True,
        capture_workspace_artifacts=True,
    )

    assert client.complete([{"role": "user", "content": "세액을 검산하라"}]) == "110"
    assert "description: Verify nontrivial calculations with code." in seen["staged_skill"]
    assert seen["command"][seen["command"].index("--sandbox") + 1] == "workspace-write"
    assert "features.shell_tool=false" not in seen["command"]
    assert "General factual and primary-source web research is allowed" in seen["prompt"]
    assert "write and test code only inside that workspace" in seen["prompt"]
    trace = client.consume_last_call_trace()
    assert trace["skillsAvailable"][0]["name"] == "general-calculation-helper"
    assert trace["mcpToolEvents"][0]["arguments"]["query"] == "부가가치세 일반 계산 원칙"
    assert trace["workspaceArtifacts"] == [
        {
            "relativePath": "verify_tax.py",
            "sizeBytes": 27,
            "sha256": "3a9d868a4b2f814c37e2dacef21d0dcdfae7f8ddd0e27e42be7f9105ba636f4e",
            "quarantineStatus": "unreviewed_not_promoted",
            "text": "print(round(100 * 1.1, 2))\n",
        }
    ]


def test_codex_exec_compact_skill_briefing_inlines_descriptions_without_staging_or_shell(
    monkeypatch, tmp_path
):
    skill = tmp_path / "general-evidence-helper"
    skill.mkdir()
    (skill / "SKILL.md").write_text(
        "---\nname: general-evidence-helper\n"
        "description: Use bounded evidence only when public facts require retrieval.\n---\n"
        "This full body must not be staged or injected.\n",
        encoding="utf-8",
    )
    seen = {}

    def fake_invoke(command, *, prompt, timeout, environment):
        del timeout, environment
        seen["command"] = command
        seen["prompt"] = prompt
        workspace = Path(command[command.index("--cd") + 1])
        seen["skill_staged"] = (workspace / ".agents/skills/general-evidence-helper").exists()
        output_path = Path(command[command.index("--output-last-message") + 1])
        output_path.write_text('{"finalAnswer":"답","selectedSkillNames":[]}', encoding="utf-8")
        return benchmark_provider.subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(benchmark_provider, "_invoke_codex", fake_invoke)
    client = benchmark_provider.CodexExecLLMClient(
        default_model="gpt-5.6-luna",
        executable="codex-fixture",
        domain_evidence_mcp_enabled=True,
        domain_evidence_repo_root=Path(__file__).resolve().parents[1],
        domain_evidence_product="tcm",
        skill_paths=[skill],
        compact_skill_briefing_enabled=True,
    )

    client.complete([{"role": "user", "content": "공개 질문"}])

    configs = [
        seen["command"][index + 1]
        for index, value in enumerate(seen["command"])
        if value == "--config"
    ]
    assert "features.shell_tool=false" in configs
    assert 'mcp_servers.domain_evidence.enabled_tools=["search_domain_evidence"]' in configs
    assert not any("search_beta6_evidence_frontier" in value for value in configs)
    assert seen["command"][seen["command"].index("--sandbox") + 1] == "read-only"
    assert seen["skill_staged"] is False
    assert "Use bounded evidence only when public facts require retrieval" in seen["prompt"]
    assert "This full body must not be staged or injected" not in seen["prompt"]
    assert "list only procedures actually used under selectedSkillNames" in seen["prompt"]
    trace = client.consume_last_call_trace()
    assert trace["skillsAvailable"][0]["deliveryMode"] == "inline_description_only"
    assert client.decoding["compactSkillBriefingEnabled"] is True


def test_compact_skill_briefing_domain_policy_caps_retrieval_at_one_basic_call():
    prompt = benchmark_provider._completion_prompt(
        [{"role": "user", "content": "공개 질문"}],
        allow_domain_evidence=True,
        domain_evidence_product="tcm",
        compact_skill_briefing='[{"name":"solve-with-domain-evidence"}]',
    )

    assert "search_domain_evidence exactly once" in prompt
    assert "Do not call get_domain_source or the Beta6 frontier" in prompt
