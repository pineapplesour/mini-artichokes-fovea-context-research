from __future__ import annotations

import hashlib
import json
import os
import re
import signal
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Callable


CODEX_EXEC_PROVIDER = "codex_exec"
PROVIDER_ENV = "UNIVERSAL_EVAL_LLM_PROVIDER"
CODEX_EXECUTABLE_ENV = "UNIVERSAL_EVAL_CODEX_EXECUTABLE"
CODEX_REASONING_EFFORT_ENV = "UNIVERSAL_EVAL_CODEX_REASONING_EFFORT"
CODEX_VERBOSITY_ENV = "UNIVERSAL_EVAL_CODEX_VERBOSITY"
CODEX_MAX_ATTEMPTS_ENV = "UNIVERSAL_EVAL_CODEX_MAX_ATTEMPTS"
CODEX_WORKER_THREADS_ENV = "UNIVERSAL_EVAL_CODEX_WORKER_THREADS"
CODEX_WEB_SEARCH_ENV = "UNIVERSAL_EVAL_CODEX_WEB_SEARCH"
CODEX_CALCULATION_TOOLS_ENV = "UNIVERSAL_EVAL_CODEX_CALCULATION_TOOLS"
CODEX_DOMAIN_EVIDENCE_MCP_ENV = "UNIVERSAL_EVAL_CODEX_DOMAIN_EVIDENCE_MCP"
CODEX_DOMAIN_EVIDENCE_ROOT_ENV = "UNIVERSAL_EVAL_CODEX_DOMAIN_EVIDENCE_ROOT"
CODEX_DOMAIN_EVIDENCE_PRODUCT_ENV = "UNIVERSAL_EVAL_CODEX_DOMAIN_EVIDENCE_PRODUCT"
DOMAIN_EVIDENCE_PUBLIC_QUESTION_ENV = "UNIVERSAL_EVAL_DOMAIN_EVIDENCE_PUBLIC_QUESTION"
DOMAIN_EVIDENCE_QUERY_GUARD_ENV = "UNIVERSAL_EVAL_DOMAIN_EVIDENCE_REQUIRE_QUERY_GUARD"
DOMAIN_EVIDENCE_DB_ENV_BY_PRODUCT = {
    "lawkey": "RELIGION_LAWKEY_DB_PATH",
    "tcm": "RELIGION_TCM_DB_PATH",
    "simli": "RELIGION_SIMLI_DB_PATH",
    "islam": "RELIGION_ISLAM_DB_PATH",
    "buddhist": "RELIGION_BUDDHIST_DB_PATH",
    "catholic": "RELIGION_CATHOLIC_DB_PATH",
    "hindu": "RELIGION_HINDU_DB_PATH",
}


def create_benchmark_llm_client(
    *,
    model: str,
    fallback_factory: Callable[[], Any | None],
    timeout_seconds: float = 300.0,
) -> Any | None:
    provider = os.getenv(PROVIDER_ENV, "environment").strip().lower()
    if provider in {"", "environment", "default"}:
        return fallback_factory()
    if provider == CODEX_EXEC_PROVIDER:
        return CodexExecLLMClient(
            default_model=model,
            timeout_seconds=timeout_seconds,
            executable=os.getenv(CODEX_EXECUTABLE_ENV, "codex").strip() or "codex",
            reasoning_effort=os.getenv(CODEX_REASONING_EFFORT_ENV, "low").strip().lower() or "low",
            verbosity=os.getenv(CODEX_VERBOSITY_ENV, "low").strip().lower() or "low",
            max_attempts=_positive_int_env(CODEX_MAX_ATTEMPTS_ENV, default=2),
            worker_threads=_positive_int_env(CODEX_WORKER_THREADS_ENV, default=1),
            web_search_enabled=_boolean_env(CODEX_WEB_SEARCH_ENV, default=False),
            calculation_tools_enabled=_boolean_env(CODEX_CALCULATION_TOOLS_ENV, default=False),
            domain_evidence_mcp_enabled=_boolean_env(CODEX_DOMAIN_EVIDENCE_MCP_ENV, default=False),
            domain_evidence_repo_root=Path(
                os.getenv(CODEX_DOMAIN_EVIDENCE_ROOT_ENV, str(Path(__file__).resolve().parents[1]))
            ),
            domain_evidence_product=os.getenv(CODEX_DOMAIN_EVIDENCE_PRODUCT_ENV, "").strip().lower(),
        )
    raise ValueError(f"unsupported benchmark LLM provider: {provider}")


class CodexExecLLMClient:
    provider = CODEX_EXEC_PROVIDER

    def __init__(
        self,
        *,
        default_model: str,
        timeout_seconds: float = 300.0,
        executable: str = "codex",
        reasoning_effort: str = "low",
        verbosity: str = "low",
        max_attempts: int = 2,
        worker_threads: int = 1,
        web_search_enabled: bool = False,
        calculation_tools_enabled: bool = False,
        domain_evidence_mcp_enabled: bool = False,
        domain_beta6_frontier_enabled: bool = True,
        domain_evidence_repo_root: Path | None = None,
        domain_evidence_product: str = "",
        skill_paths: list[Path] | None = None,
        agent_workspace_enabled: bool = False,
        capture_workspace_artifacts: bool = False,
        compact_skill_briefing_enabled: bool = False,
        domain_evidence_public_question: str = "",
    ) -> None:
        if reasoning_effort not in {"minimal", "low", "medium", "high", "xhigh", "max"}:
            raise ValueError(f"unsupported Codex reasoning effort: {reasoning_effort}")
        if verbosity not in {"low", "medium", "high"}:
            raise ValueError(f"unsupported Codex verbosity: {verbosity}")
        if not 1 <= int(max_attempts) <= 5:
            raise ValueError("Codex max_attempts must be between 1 and 5")
        if not 1 <= int(worker_threads) <= 16:
            raise ValueError("Codex worker_threads must be between 1 and 16")
        self.default_model = str(default_model)
        self.timeout_seconds = float(timeout_seconds)
        self.executable = str(executable)
        self.reasoning_effort = reasoning_effort
        self.verbosity = verbosity
        self.max_attempts = int(max_attempts)
        self.worker_threads = int(worker_threads)
        self.web_search_enabled = bool(web_search_enabled)
        self.calculation_tools_enabled = bool(calculation_tools_enabled)
        self.domain_evidence_mcp_enabled = bool(domain_evidence_mcp_enabled)
        self.domain_beta6_frontier_enabled = bool(domain_beta6_frontier_enabled)
        self.domain_evidence_product = str(domain_evidence_product or "").strip().lower()
        self.skill_paths = _validated_skill_paths(skill_paths or [])
        self.agent_workspace_enabled = bool(agent_workspace_enabled)
        self.capture_workspace_artifacts = bool(capture_workspace_artifacts)
        self.compact_skill_briefing_enabled = bool(compact_skill_briefing_enabled)
        self.domain_evidence_public_question = str(domain_evidence_public_question or "").strip()
        if self.compact_skill_briefing_enabled and not self.skill_paths:
            raise ValueError("compact skill briefing requires at least one approved skill")
        if self.compact_skill_briefing_enabled and self.agent_workspace_enabled:
            raise ValueError("compact skill briefing must keep the agent workspace and shell disabled")
        self.domain_evidence_repo_root = Path(domain_evidence_repo_root or Path(__file__).resolve().parents[1]).resolve()
        self.domain_evidence_server = self.domain_evidence_repo_root / "tools/domain_evidence_mcp_server.py"
        if self.domain_evidence_mcp_enabled and not self.domain_evidence_server.is_file():
            raise ValueError(f"domain evidence MCP server not found: {self.domain_evidence_server}")
        self.decoding = {
            "reasoningEffort": reasoning_effort,
            "transportMaxAttempts": self.max_attempts,
            "transportWorkerThreads": self.worker_threads,
            "verbosity": verbosity,
        }
        if self.calculation_tools_enabled:
            self.decoding["calculationToolsEnabled"] = True
        if self.web_search_enabled:
            self.decoding["webSearchEnabled"] = True
        if self.domain_evidence_mcp_enabled:
            self.decoding["domainEvidenceMcpEnabled"] = True
            self.decoding["domainBeta6FrontierEnabled"] = self.domain_beta6_frontier_enabled
            if self.domain_evidence_product:
                self.decoding["domainEvidenceProduct"] = self.domain_evidence_product
        if self.skill_paths:
            self.decoding["nativeRepoSkillsEnabled"] = True
            self.decoding["nativeRepoSkillCount"] = len(self.skill_paths)
        if self.agent_workspace_enabled:
            self.decoding["agentWorkspaceEnabled"] = True
            self.decoding["workspaceArtifactsQuarantined"] = self.capture_workspace_artifacts
        if self.compact_skill_briefing_enabled:
            self.decoding["compactSkillBriefingEnabled"] = True
        self._trace_lock = threading.Lock()
        self._last_trace_by_thread: dict[int, dict[str, Any]] = {}
        self._attempt_trace_by_thread: dict[int, dict[str, Any]] = {}

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        model: str = "",
        timeout_seconds: float | None = None,
    ) -> str:
        active_model = str(model or self.default_model).strip()
        if not active_model:
            raise ValueError("Codex Exec model is required")
        timeout = self.timeout_seconds if timeout_seconds is None else float(timeout_seconds)
        started = time.monotonic()
        trace: dict[str, Any] = {
            "provider": self.provider,
            "model": active_model,
            "timeoutSeconds": timeout,
            "maxAttempts": self.max_attempts,
            "status": "running",
            "webSearchEnabled": self.web_search_enabled,
            "domainEvidenceMcpEnabled": self.domain_evidence_mcp_enabled,
            "domainBeta6FrontierEnabled": (
                self.domain_evidence_mcp_enabled and self.domain_beta6_frontier_enabled
            ),
            "agentWorkspaceEnabled": self.agent_workspace_enabled,
            "skillsAvailable": [_skill_identity(path) for path in self.skill_paths],
            "compactSkillBriefingEnabled": self.compact_skill_briefing_enabled,
        }
        try:
            prompt = _completion_prompt(
                messages,
                allow_web_search=self.web_search_enabled,
                allow_calculation_tools=self.calculation_tools_enabled,
                allow_domain_evidence=self.domain_evidence_mcp_enabled,
                domain_evidence_product=self.domain_evidence_product,
                allow_agent_workspace=self.agent_workspace_enabled,
                compact_skill_briefing=(
                    _compact_skill_briefing(self.skill_paths)
                    if self.compact_skill_briefing_enabled
                    else ""
                ),
            )
            public_question_for_guard = self.domain_evidence_public_question or "\n".join(
                str(item.get("content") or "")
                for item in messages
                if isinstance(item, dict) and str(item.get("role") or "user") == "user"
            ).strip()
            last_error: Exception | None = None
            for attempt in range(1, self.max_attempts + 1):
                trace["attempts"] = attempt
                self._consume_attempt_trace()
                try:
                    answer = self._complete_attempt(
                        prompt,
                        active_model=active_model,
                        timeout=timeout,
                        public_question_for_guard=public_question_for_guard,
                    )
                    attempt_trace = self._consume_attempt_trace()
                    if attempt_trace:
                        trace.update(attempt_trace)
                    trace["status"] = "completed"
                    return answer
                except Exception as exc:
                    attempt_trace = self._consume_attempt_trace()
                    if attempt_trace:
                        trace.update(attempt_trace)
                    last_error = exc
                    if attempt < self.max_attempts:
                        time.sleep(min(2.0, 0.25 * attempt))
            assert last_error is not None
            raise last_error
        except Exception as exc:
            trace["status"] = "error"
            trace["error"] = str(exc)[:300]
            raise
        finally:
            trace["elapsedSec"] = round(max(0.0, time.monotonic() - started), 3)
            with self._trace_lock:
                self._last_trace_by_thread[threading.get_ident()] = dict(trace)

    def _complete_attempt(
        self,
        prompt: str,
        *,
        active_model: str,
        timeout: float,
        public_question_for_guard: str,
    ) -> str:
        with tempfile.TemporaryDirectory(prefix="universal-eval-codex-") as temp_dir:
            workspace = Path(temp_dir)
            staged_skills = (
                [
                    {**_skill_identity(path), "deliveryMode": "inline_description_only"}
                    for path in self.skill_paths
                ]
                if self.compact_skill_briefing_enabled
                else _stage_skills(workspace, self.skill_paths)
            )
            output_path = workspace / "last_message.txt"
            command = [self.executable]
            if self.web_search_enabled:
                command.append("--search")
            command.extend([
                "exec",
                "--ephemeral",
                "--ignore-user-config",
                "--ignore-rules",
                "--skip-git-repo-check",
                "--sandbox",
                "workspace-write" if self.agent_workspace_enabled else "read-only",
                "--cd",
                temp_dir,
                "--model",
                active_model,
                "--config",
                f'model_reasoning_effort="{self.reasoning_effort}"',
                "--config",
                f'model_verbosity="{self.verbosity}"',
            ])
            if not self.web_search_enabled:
                command.extend(["--config", 'web_search="disabled"'])
            if (
                self.compact_skill_briefing_enabled
                or (
                    not self.calculation_tools_enabled
                    and not self.domain_evidence_mcp_enabled
                    and not self.agent_workspace_enabled
                )
            ):
                command.extend(["--config", "features.shell_tool=false"])
            if self.domain_evidence_mcp_enabled:
                mounted_env_names = [
                    DOMAIN_EVIDENCE_DB_ENV_BY_PRODUCT[self.domain_evidence_product]
                ] if self.domain_evidence_product in DOMAIN_EVIDENCE_DB_ENV_BY_PRODUCT else list(
                    DOMAIN_EVIDENCE_DB_ENV_BY_PRODUCT.values()
                )
                mounted_env_names.extend(
                    [DOMAIN_EVIDENCE_PUBLIC_QUESTION_ENV, DOMAIN_EVIDENCE_QUERY_GUARD_ENV]
                )
                domain_tool_config = [
                        "--config",
                        f"mcp_servers.domain_evidence.command={json.dumps(sys.executable)}",
                        "--config",
                        "mcp_servers.domain_evidence.args="
                        + json.dumps([str(self.domain_evidence_server)], ensure_ascii=True, separators=(",", ":")),
                        "--config",
                        f"mcp_servers.domain_evidence.cwd={json.dumps(str(self.domain_evidence_repo_root))}",
                        "--config",
                        "mcp_servers.domain_evidence.env_vars="
                        + json.dumps(mounted_env_names, ensure_ascii=True, separators=(",", ":")),
                        "--config",
                        (
                            'mcp_servers.domain_evidence.enabled_tools=["search_domain_evidence"]'
                            if self.compact_skill_briefing_enabled
                            else (
                                'mcp_servers.domain_evidence.enabled_tools=["search_domain_evidence","get_domain_source","search_beta6_evidence_frontier"]'
                                if self.domain_beta6_frontier_enabled
                                else 'mcp_servers.domain_evidence.enabled_tools=["search_domain_evidence","get_domain_source"]'
                            )
                        ),
                        "--config",
                        'mcp_servers.domain_evidence.default_tools_approval_mode="approve"',
                        "--config",
                        "mcp_servers.domain_evidence.required=true",
                        "--config",
                        "mcp_servers.domain_evidence.tool_timeout_sec=60.0",
                    ]
                if (
                    not self.calculation_tools_enabled
                    and not self.agent_workspace_enabled
                    and not self.compact_skill_briefing_enabled
                ):
                    domain_tool_config[0:0] = ["--config", "features.shell_tool=false"]
                command.extend(domain_tool_config)
            # JSONL is enabled for every benchmark call so latency/tool/token
            # telemetry is available even when web search is disabled.
            command.append("--json")
            command.extend([
                "--output-last-message",
                str(output_path),
                "-",
            ])
            environment = dict(os.environ)
            environment["TOKIO_WORKER_THREADS"] = str(self.worker_threads)
            environment["RAYON_NUM_THREADS"] = str(self.worker_threads)
            environment["UV_THREADPOOL_SIZE"] = str(self.worker_threads)
            if self.domain_evidence_mcp_enabled:
                environment[DOMAIN_EVIDENCE_PUBLIC_QUESTION_ENV] = public_question_for_guard
                environment[DOMAIN_EVIDENCE_QUERY_GUARD_ENV] = "1"
            completed = _invoke_codex(command, prompt=prompt, timeout=timeout, environment=environment)
            attempt_trace = _parse_codex_jsonl_trace(completed.stdout)
            attempt_trace["skillsAvailable"] = staged_skills
            if self.capture_workspace_artifacts:
                attempt_trace["workspaceArtifacts"] = _capture_workspace_artifacts(
                    workspace,
                    ignored_relative_paths={"last_message.txt"},
                )
            self._record_attempt_trace(attempt_trace)
            if completed.returncode != 0:
                detail = str(completed.stderr or completed.stdout or "").strip()[-1000:]
                raise RuntimeError(f"Codex Exec failed with exit={completed.returncode}: {detail}")
            answer = output_path.read_text(encoding="utf-8").strip() if output_path.exists() else ""
            if not answer:
                raise RuntimeError("Codex Exec returned an empty final message")
            return answer

    def _record_attempt_trace(self, trace: dict[str, Any]) -> None:
        with self._trace_lock:
            self._attempt_trace_by_thread[threading.get_ident()] = dict(trace)

    def _consume_attempt_trace(self) -> dict[str, Any] | None:
        with self._trace_lock:
            return self._attempt_trace_by_thread.pop(threading.get_ident(), None)

    def consume_last_call_trace(self) -> dict[str, Any] | None:
        with self._trace_lock:
            return self._last_trace_by_thread.pop(threading.get_ident(), None)


def _completion_prompt(
    messages: list[dict[str, str]],
    *,
    allow_web_search: bool = False,
    allow_calculation_tools: bool = False,
    allow_domain_evidence: bool = False,
    domain_evidence_product: str = "",
    allow_agent_workspace: bool = False,
    compact_skill_briefing: str = "",
) -> str:
    normalized = [
        {"role": str(item.get("role") or "user"), "content": str(item.get("content") or "")}
        for item in messages
        if isinstance(item, dict)
    ]
    product_instruction = (
        f"Set the tool argument product={json.dumps(domain_evidence_product, ensure_ascii=False)}. The tool has no path argument "
        "and can access only the explicitly mounted database. Keep limit at 3 and snippet_chars at 600. "
        if domain_evidence_product
        else ""
    )
    if allow_agent_workspace and allow_web_search and allow_domain_evidence:
        tool_policy = (
            "Use native live web search, the mounted read-only domain-evidence MCP tools, and shell commands in the current "
            "ephemeral workspace as useful. You may write and test code only inside that workspace. Never inspect parent or "
            "absolute host paths, environment secrets, private benchmark files, answer keys, original exam mirrors, or historical "
            "predictions. Never search an exact/near-exact question, question ID, option phrase, or answer-key site. Never translate, "
            "summarize, or paraphrase the case facts into a search query. Search a candidate concept plus at most one distinguishing "
            "fact, or one broad concept when no candidate exists; never ask a search engine what answer matches the case. General factual "
            "and primary-source web research is allowed. "
            + product_instruction
        )
    elif allow_agent_workspace and allow_web_search:
        tool_policy = (
            "Use native live web search and shell commands in the current ephemeral workspace as useful. You may write and test "
            "code only inside that workspace. Never inspect parent or absolute host paths, environment secrets, private benchmark "
            "files, answer keys, original exam mirrors, or historical predictions. Never search an exact/near-exact question, "
            "question ID, option phrase, or answer-key site. Never translate, summarize, or paraphrase the case facts into a search "
            "query. Search a candidate concept plus at most one distinguishing fact, or one broad concept when no candidate exists; "
            "never ask a search engine what answer matches the case. General factual and primary-source web research is allowed. "
        )
    elif allow_agent_workspace and allow_domain_evidence:
        tool_policy = (
            "Use the mounted read-only domain-evidence MCP tools and shell commands in the current ephemeral workspace as useful. "
            "You may write and test code only inside that workspace. Never inspect parent or absolute host paths, environment "
            "secrets, private benchmark files, answer keys, original exam mirrors, or historical predictions. Never query an "
            "exact/near-exact question, question ID, option phrase, or answer key. Never translate, summarize, or paraphrase the case "
            "facts into a query. Search a candidate concept plus at most one distinguishing fact, or one broad concept when no candidate "
            "exists; never ask the database what answer matches the case. "
            + product_instruction
        )
    elif allow_agent_workspace:
        tool_policy = (
            "Use shell commands in the current ephemeral workspace as useful. You may write and test code only inside that "
            "workspace. Never inspect parent or absolute host paths, environment secrets, private benchmark files, answer keys, "
            "original exam mirrors, or historical predictions. "
        )
    elif allow_web_search and allow_domain_evidence:
        tool_policy = (
            "Before returning the final response, you MUST call the read-only MCP tool search_domain_evidence at least once "
            "with a short abstract domain query. "
            + product_instruction
            + "You may also use native live web search plus the domain-evidence tool "
            "get_domain_source. Use the mounted database for hard-to-find domain sources and primary web sources for current or "
            "independently verifiable facts. Never inspect local files or repositories. Never search for or open the original "
            "question sheet, exam paper, benchmark, answer key, quiz mirror, or an exact/near-exact question or option phrase. "
            "Do not translate, summarize, or paraphrase the case facts into a query. Search a candidate concept plus at most one "
            "distinguishing fact, or one broad concept when no candidate exists; never ask a search engine what answer matches the case. "
            "Use short abstract factual queries that omit question numbers, exam names, source-file names, and answer-choice wording. "
        )
    elif allow_web_search:
        calculation_policy = (
            "Read-only shell commands may be used solely for self-contained calculations without reading or writing files. "
            if allow_calculation_tools
            else "Do not run shell commands or call MCP tools. "
        )
        tool_policy = (
        "You may use only the native live web-search tool. "
        + calculation_policy
        + "Never inspect local files or repositories. Never search for or open the original question sheet, "
        "exam paper, benchmark, answer key, quiz mirror, or an exact/near-exact question or option phrase. "
        "Do not translate, summarize, or paraphrase the case facts into a query. Search a candidate concept plus at most one "
        "distinguishing fact, or one broad concept when no candidate exists; never ask a search engine what answer matches the case. "
        "Search only general concepts and facts, using short abstract queries that omit question numbers, "
        "exam names, source-file names, and answer-choice wording. "
        )
    elif allow_domain_evidence:
        if compact_skill_briefing:
            tool_policy = (
                "Before returning the final response, call the read-only MCP tool search_domain_evidence exactly once. "
                + product_instruction
                + "Do not call get_domain_source or the Beta6 frontier in this low-cost mode. "
                "Never inspect local files or repositories, run shell commands, browse the web, or modify anything. "
                "Do not translate, summarize, or paraphrase the case facts into a query. Use one candidate concept plus at most one "
                "distinguishing fact, or one broad concept when no candidate exists; never ask the database what answer matches the case. "
                "Do not search benchmark names, question numbers, option wording, or answer keys. "
            )
        else:
            tool_policy = (
                "Before returning the final response, you MUST call the read-only MCP tool search_domain_evidence at least once. "
                + product_instruction
                + "You may use only search_domain_evidence and get_domain_source. "
                "Never inspect local files or repositories, run shell commands, browse the web, or modify anything. "
                "Do not translate, summarize, or paraphrase the case facts into a query. Search a candidate concept plus at most one "
                "distinguishing fact, or one broad concept when no candidate exists; never ask the database what answer matches the case. "
                "Do not search benchmark names, question numbers, option wording, or answer keys. "
            )
    elif allow_calculation_tools:
        tool_policy = (
            "You may use read-only shell commands solely to run self-contained calculations supplied in the conversation. "
            "Never inspect local files or repositories, browse the web, access environment secrets, or modify anything. "
        )
    else:
        tool_policy = "Do not call tools, inspect files, browse, or modify anything. "
    procedure_catalog = (
        "\n\nAPPROVED_PROCEDURE_CATALOG:\n"
        + str(compact_skill_briefing)
        + "\nChoose procedures only from observable task needs, use the least expensive fitting procedure, and do not "
        "treat a procedure description as factual authority. Do not inspect skill files. In the final JSON, list only "
        "procedures actually used under selectedSkillNames."
        if compact_skill_briefing
        else ""
    )
    return (
        "You are serving as a stateless language-model completion endpoint. "
        + tool_policy
        + "Return only the assistant response that best follows the role-ordered conversation below; "
        "do not add commentary about this wrapper.\n\n"
        + procedure_catalog
        + "\n\n"
        "CONVERSATION_JSON:\n"
        + json.dumps(normalized, ensure_ascii=False, separators=(",", ":"))
    )


def _parse_codex_jsonl_trace(stdout: str) -> dict[str, Any]:
    web_events: list[dict[str, Any]] = []
    command_events: list[dict[str, Any]] = []
    mcp_events: list[dict[str, Any]] = []
    skill_events: list[dict[str, Any]] = []
    invalid_lines = 0
    event_count = 0
    token_usage: dict[str, int] = {}
    for raw_line in str(stdout or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            invalid_lines += 1
            continue
        if not isinstance(payload, dict):
            continue
        event_count += 1
        for usage_candidate in (payload.get("usage"), payload.get("token_usage")):
            normalized_usage = _normalize_token_usage(usage_candidate)
            if normalized_usage:
                token_usage = normalized_usage
        item = payload.get("item")
        if not isinstance(item, dict):
            continue
        normalized_item_usage = _normalize_token_usage(item.get("usage"))
        if normalized_item_usage:
            token_usage = normalized_item_usage
        item_type = str(item.get("type") or "")
        if item_type == "web_search":
            action = item.get("action") if isinstance(item.get("action"), dict) else {}
            web_events.append(
                {
                    "eventType": str(payload.get("type") or ""),
                    "query": str(item.get("query") or action.get("query") or ""),
                    "action": {str(key): value for key, value in action.items()},
                }
            )
        elif item_type in {"command_execution", "shell_command", "command"}:
            command_events.append(
                {
                    "eventType": str(payload.get("type") or ""),
                    "command": str(item.get("command") or ""),
                    "status": str(item.get("status") or ""),
                    "exitCode": item.get("exit_code"),
                }
            )
        elif "mcp" in item_type.lower():
            error_value = item.get("error")
            if isinstance(error_value, dict):
                error_preview = str(error_value.get("message") or error_value.get("code") or "")[:300]
            else:
                error_preview = str(error_value or "")[:300]
            mcp_event = {
                    "eventType": str(payload.get("type") or ""),
                    "itemType": item_type,
                    "server": str(item.get("server") or item.get("server_name") or ""),
                    "tool": str(item.get("tool") or item.get("tool_name") or item.get("name") or ""),
                    "status": str(item.get("status") or ""),
                    "errorPreview": error_preview,
                    "arguments": _bounded_json_value(
                        item.get("arguments", item.get("input", item.get("params", {})))
                    ),
                }
            if str(item.get("status") or "") != "completed":
                failure_value = item.get("result", item.get("output", item.get("content")))
                if failure_value is not None and failure_value != "" and failure_value != [] and failure_value != {}:
                    mcp_event["failurePreview"] = _bounded_text_preview(failure_value)
            mcp_events.append(mcp_event)
        elif "skill" in item_type.lower():
            skill_events.append(
                {
                    "eventType": str(payload.get("type") or ""),
                    "itemType": item_type,
                    "name": str(item.get("name") or item.get("skill") or "")[:200],
                    "path": str(item.get("path") or "")[:500],
                    "status": str(item.get("status") or "")[:100],
                }
            )
    completed_web_events = [item for item in web_events if item["eventType"] == "item.completed"]
    completed_command_events = [item for item in command_events if item["eventType"] == "item.completed"]
    completed_mcp_events = [item for item in mcp_events if item["eventType"] == "item.completed"]
    return {
        "codexJsonlEventCount": event_count,
        "codexJsonlInvalidLineCount": invalid_lines,
        "webSearchEvents": completed_web_events,
        "commandExecutionEvents": completed_command_events,
        "mcpToolEvents": completed_mcp_events or mcp_events,
        "skillEvents": [item for item in skill_events if item["eventType"] == "item.completed"] or skill_events,
        "tokenUsage": token_usage,
    }


SKILL_STAGE_IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".git", "runs", "reports", "artifacts")
WORKSPACE_CAPTURE_EXCLUDED_PARTS = {".agents", ".codex", ".git", "node_modules", "__pycache__"}


def _validated_skill_paths(values: list[Path]) -> list[Path]:
    rows: list[Path] = []
    seen: set[Path] = set()
    for value in values:
        path = Path(value).expanduser().resolve()
        if path.name == "SKILL.md":
            path = path.parent
        if not (path / "SKILL.md").is_file():
            raise ValueError(f"skill path is missing SKILL.md: {path}")
        if path in seen:
            continue
        for child in path.rglob("*"):
            if child.is_symlink():
                raise ValueError(f"skill trees must not contain symlinks: {child}")
        seen.add(path)
        rows.append(path)
    return rows


def _skill_identity(path: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    file_count = 0
    for child in sorted(path.rglob("*")):
        if not child.is_file() or any(part in {"__pycache__", ".git"} for part in child.parts) or child.suffix == ".pyc":
            continue
        relative = child.relative_to(path).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(child.read_bytes())
        digest.update(b"\0")
        file_count += 1
    return {
        "name": path.name,
        "sourcePath": str(path),
        "treeSha256": digest.hexdigest(),
        "fileCount": file_count,
    }


def _compact_skill_briefing(skill_paths: list[Path]) -> str:
    rows: list[dict[str, str]] = []
    for path in skill_paths:
        text = (path / "SKILL.md").read_text(encoding="utf-8")
        frontmatter = re.match(r"\A---\s*\n(.*?)\n---(?:\s*\n|\Z)", text, flags=re.DOTALL)
        if frontmatter is None:
            raise ValueError(f"approved skill is missing YAML frontmatter: {path}")
        fields: dict[str, str] = {}
        for line in frontmatter.group(1).splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            fields[key.strip()] = " ".join(value.strip().split())
        name = fields.get("name", "")
        description = fields.get("description", "")
        if name != path.name or not description:
            raise ValueError(f"approved skill frontmatter is invalid: {path}")
        rows.append(
            {
                "name": name[:160],
                "description": description[:800],
                "treeSha256": _skill_identity(path)["treeSha256"],
            }
        )
    if not rows:
        raise ValueError("compact skill briefing may not be empty")
    return json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _stage_skills(workspace: Path, skill_paths: list[Path]) -> list[dict[str, Any]]:
    target_root = workspace / ".agents" / "skills"
    rows: list[dict[str, Any]] = []
    for source in skill_paths:
        target = target_root / source.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target, ignore=SKILL_STAGE_IGNORE)
        identity = _skill_identity(source)
        identity["stagedPath"] = str(target.relative_to(workspace))
        rows.append(identity)
    return rows


def _capture_workspace_artifacts(
    workspace: Path,
    *,
    ignored_relative_paths: set[str],
    maximum_files: int = 20,
    maximum_total_bytes: int = 1_000_000,
    maximum_text_bytes: int = 100_000,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    total_bytes = 0
    for path in sorted(workspace.rglob("*")):
        # Never dereference an agent-created symlink while collecting artifacts.
        # Otherwise a workspace file could point at read-only host data and copy
        # it into the benchmark trace before the command audit runs.
        if path.is_symlink() or not path.is_file():
            continue
        relative = path.relative_to(workspace).as_posix()
        if relative in ignored_relative_paths or any(part in WORKSPACE_CAPTURE_EXCLUDED_PARTS for part in path.relative_to(workspace).parts):
            continue
        size = path.stat().st_size
        if len(rows) >= maximum_files or total_bytes + size > maximum_total_bytes:
            break
        data = path.read_bytes()
        row: dict[str, Any] = {
            "relativePath": relative,
            "sizeBytes": size,
            "sha256": hashlib.sha256(data).hexdigest(),
            "quarantineStatus": "unreviewed_not_promoted",
        }
        if size <= maximum_text_bytes:
            try:
                row["text"] = data.decode("utf-8")
            except UnicodeDecodeError:
                pass
        rows.append(row)
        total_bytes += size
    return rows


def _bounded_json_value(value: Any, *, maximum_characters: int = 4000) -> Any:
    try:
        encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError):
        return {}
    if len(encoded) > maximum_characters:
        return {"truncated": True, "sha256": hashlib.sha256(encoded.encode("utf-8")).hexdigest()}
    try:
        return json.loads(encoded)
    except json.JSONDecodeError:
        return {}


def _bounded_text_preview(value: Any, *, maximum_characters: int = 800) -> str:
    if isinstance(value, str):
        return value[:maximum_characters]
    try:
        encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError):
        encoded = str(value)
    return encoded[:maximum_characters]


def _normalize_token_usage(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    aliases = {
        "inputTokens": ("input_tokens", "inputTokens"),
        "cachedInputTokens": ("cached_input_tokens", "cachedInputTokens"),
        "outputTokens": ("output_tokens", "outputTokens"),
        "reasoningOutputTokens": ("reasoning_output_tokens", "reasoningOutputTokens"),
        "totalTokens": ("total_tokens", "totalTokens"),
    }
    normalized: dict[str, int] = {}
    for output_key, candidates in aliases.items():
        for candidate in candidates:
            raw = value.get(candidate)
            if isinstance(raw, (int, float)) and raw >= 0:
                normalized[output_key] = int(raw)
                break
    if "totalTokens" not in normalized:
        parts = [normalized.get("inputTokens"), normalized.get("outputTokens")]
        if all(isinstance(part, int) for part in parts):
            normalized["totalTokens"] = int(parts[0] or 0) + int(parts[1] or 0)
    return normalized


def _invoke_codex(
    command: list[str],
    *,
    prompt: str,
    timeout: float,
    environment: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=environment,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(input=prompt, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        stdout, stderr = process.communicate()
        raise subprocess.TimeoutExpired(
            command,
            timeout,
            output=stdout or exc.output,
            stderr=stderr or exc.stderr,
        ) from exc
    return subprocess.CompletedProcess(command, int(process.returncode or 0), stdout=stdout, stderr=stderr)


def _positive_int_env(name: str, *, default: int) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive integer") from exc
    if parsed <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return parsed


def _boolean_env(name: str, *, default: bool) -> bool:
    value = os.getenv(name, "").strip().lower()
    if not value:
        return bool(default)
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean flag")
