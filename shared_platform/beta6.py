from __future__ import annotations

import json
import os
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import re
import inspect
import difflib
import hashlib
import secrets
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Protocol

from .products import PRODUCT_PROFILES, ProductProfile
from .search import SearchResult, describe_query_expansion, search_documents, to_beta6_selected_record
from .engine_contract import engine_contract_payload
from .gemma_keyring import install_team1_gemma_keys_from_file
from .domain_adapters import get_domain_adapter


BETA6_ANALYSIS_MODE = "beta6"
BETA6_CHUNK_TOKEN_BUDGET = 100_000
LAWKEY_DEFAULT_KEYWORD_COUNT = 10
LAWKEY_DEFAULT_TOP_K_PRECEDENTS = 100
LAWKEY_BETA6_FTS_LIMIT = 700
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNS_ROOT = Path(os.getenv("RELIGION_RUNS_ROOT", str(REPO_ROOT / "runs")))
DEFAULT_LAWKEY_WRITER_MODEL = "gemma-4-26b-a4b-it"
DEFAULT_GEMMA_GATEWAY_URL = "https://lawkey.ai.kr/api/gemma-gateway/v1/chat"
DEFAULT_GEMINI_LIVE_TEXT_MODEL = "models/gemini-3.1-flash-live-preview"
DEFAULT_GEMINI_LIVE_SCRIPT_DIR = Path(os.getenv("RELIGION_GEMINI_LIVE_SCRIPT_DIR", str(REPO_ROOT / "scripts")))
DEFAULT_LAWKEY_WORKSPACE_SCRIPTS = Path(os.getenv("LAWKEY_WORKSPACE_SCRIPTS", str(REPO_ROOT / "scripts")))
GEMINI_LIVE_TEXT_SYSTEM_INSTRUCTION = (
    "You are a text backend for a source-grounded beta6 engine. Follow the "
    "provided role-labeled prompt exactly. If the prompt asks for JSON only, "
    "return valid JSON only. If it asks for selection tags, return the requested "
    "tags. Do not include audio, transcription, markdown fences, or internal "
    "analysis unless explicitly requested."
)
_BETA6_BATCH_CACHE_PRUNE_LOCK = threading.Lock()
_LAWKEY_HTTP_TRACE_LOCAL = threading.local()
BETA6_PROGRESS_STAGES = (
    "queued",
    "starting",
    "keyword_generation",
    "candidate_search",
    "source_selection",
    "chunking",
    "claim_cards",
    "answer_plan",
    "writer",
    "coverage",
    "completed",
)
BETA6_PROGRESS_LABELS = {
    "ko": {
        "queued": "대기 중",
        "starting": "실행 준비",
        "keyword_generation": "키워드 생성",
        "candidate_search": "후보 검색",
        "source_selection": "근거 선택",
        "claim_cards": "주장 카드",
        "chunking": "문맥 구성",
        "answer_plan": "답변 계획",
        "writer": "답변 작성",
        "coverage": "근거 보강",
        "completed": "완료",
        "failed": "오류",
        "interrupted": "중단",
        "cancelled": "취소됨",
    },
    "en": {
        "queued": "Queued",
        "starting": "Starting",
        "keyword_generation": "Keyword generation",
        "candidate_search": "Candidate search",
        "source_selection": "Source selection",
        "claim_cards": "Claim cards",
        "chunking": "Context building",
        "answer_plan": "Answer plan",
        "writer": "Answer writing",
        "coverage": "Coverage check",
        "completed": "Completed",
        "failed": "Failed",
        "interrupted": "Interrupted",
        "cancelled": "Cancelled",
    },
}


class LLMClient(Protocol):
    def complete(self, messages: list[dict[str, str]], *, model: str = "", timeout_seconds: float | None = None) -> str:
        ...


class OpenAICompatibleLLMClient:
    provider = "openai_compatible_chat_completions"

    def __init__(self, *, api_url: str, api_key: str = "", timeout_seconds: float = 180.0) -> None:
        self.api_url = api_url
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def complete(self, messages: list[dict[str, str]], *, model: str = "", timeout_seconds: float | None = None) -> str:
        timeout = self.timeout_seconds if timeout_seconds is None else timeout_seconds
        payload = {
            "model": model or os.getenv("RELIGION_ANSWER_MODEL", "gemini-3.1-flash-lite-preview"),
            "messages": messages,
            "temperature": 0.2,
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(self.api_url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            parsed = json.loads(response.read().decode("utf-8"))
        try:
            return str(parsed["choices"][0]["message"]["content"]).strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("invalid chat completion response") from exc


class LawkeyGemmaGatewayLLMClient:
    provider = "lawkey_gemma_gateway"

    def __init__(
        self,
        *,
        api_url: str = "https://lawkey.ai.kr/api/gemma-gateway/v1/chat",
        token: str = "",
        timeout_seconds: float = 300.0,
        user_agent: str = "BunjumGemmaGatewayClient/1.0",
    ) -> None:
        self.api_url = api_url
        self.token = str(token or "").strip()
        self.timeout_seconds = timeout_seconds
        self.user_agent = user_agent

    def complete(self, messages: list[dict[str, str]], *, model: str = "", timeout_seconds: float | None = None) -> str:
        if not self.token:
            raise RuntimeError("Lawkey Gemma gateway token is not configured")
        payload = {
            "messages": _gateway_messages(messages),
            "temperature": float(os.getenv("RELIGION_GEMMA_GATEWAY_TEMPERATURE", "0.4")),
        }
        if os.getenv("RELIGION_GEMMA_GATEWAY_MAX_OUTPUT_TOKENS", "").strip():
            payload["maxOutputTokens"] = _env_int("RELIGION_GEMMA_GATEWAY_MAX_OUTPUT_TOKENS", 2048, minimum=32, maximum=8192)
        if model:
            payload["model"] = model
        timeout = self.timeout_seconds if timeout_seconds is None else timeout_seconds
        request = urllib.request.Request(
            self.api_url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "User-Agent": self.user_agent,
            },
            method="POST",
        )
        max_attempts = _env_int("RELIGION_GEMMA_GATEWAY_MAX_ATTEMPTS", 4, minimum=1, maximum=8)
        last_error = ""
        for attempt in range(1, max_attempts + 1):
            try:
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    parsed = json.loads(response.read().decode("utf-8"))
                return _extract_gateway_text(parsed)
            except urllib.error.HTTPError as exc:
                detail = _http_error_detail(exc)
                last_error = f"Lawkey Gemma gateway returned HTTP {exc.code}: {detail}"
                if exc.code not in {502, 503, 504} or attempt == max_attempts:
                    raise RuntimeError(last_error) from exc
            except urllib.error.URLError as exc:
                last_error = f"Lawkey Gemma gateway request failed: {exc.reason}"
                if attempt == max_attempts:
                    raise RuntimeError(last_error) from exc
            except json.JSONDecodeError as exc:
                raise RuntimeError("Lawkey Gemma gateway returned invalid JSON") from exc
            time.sleep(min(8, 2 * attempt))
        raise RuntimeError(last_error or "Lawkey Gemma gateway request failed")


class MintGeminiGatewayLLMClient:
    provider = "mint_gemini_gateway_generate_content"

    def __init__(
        self,
        *,
        base_url: str = "http://sourpineapple.iptime.org:25568",
        token: str = "",
        default_model: str = DEFAULT_LAWKEY_WRITER_MODEL,
        timeout_seconds: float = 300.0,
        thinking_level: str = "minimal",
        key_numbers: Iterable[int] | None = None,
    ) -> None:
        self.base_url = str(base_url or "").strip().rstrip("/") or "http://sourpineapple.iptime.org:25568"
        self.token = str(token or "").strip()
        self.default_model = default_model
        self.timeout_seconds = timeout_seconds
        self.thinking_level = thinking_level
        self.key_numbers = _mint_gateway_key_numbers(key_numbers)
        self.call_deadline_seconds = _mint_gateway_call_deadline_seconds(timeout_seconds)
        self.transport_timeout_limit = _mint_gateway_transport_timeout_limit()
        self._trace_lock = threading.Lock()
        self._last_trace_by_thread: dict[int, dict[str, Any]] = {}

    def complete(self, messages: list[dict[str, str]], *, model: str = "", timeout_seconds: float | None = None) -> str:
        if not self.token:
            raise RuntimeError("Mint Gemini gateway token is not configured")
        answer_model = model or self.default_model
        timeout = self.timeout_seconds if timeout_seconds is None else timeout_seconds
        payload = _gemini_generate_content_payload(messages, thinking_level=self.thinking_level)
        trace: dict[str, Any] = {
            "provider": self.provider,
            "model": answer_model,
            "timeoutSeconds": float(timeout),
            "callDeadlineSeconds": float(self.call_deadline_seconds),
            "transportTimeoutLimit": int(self.transport_timeout_limit),
            "startedAtMonotonic": time.monotonic(),
            "httpStarted": 0,
            "httpFinished": 0,
            "firstHttpStartSec": None,
            "keyNumbersTried": [],
            "attempts": [],
            "status": "running",
        }
        retryable_statuses = {429, 500, 502, 503, 504}
        last_error = ""
        transport_timeouts = 0
        try:
            deadline = float(trace["startedAtMonotonic"]) + max(1.0, float(self.call_deadline_seconds))
            for index, key_number in enumerate(self.key_numbers):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    last_error = (
                        f"Mint Gemini gateway call deadline exceeded after trying "
                        f"{len(trace['keyNumbersTried'])} keyNumber(s)"
                    )
                    raise RuntimeError(last_error)
                call_timeout = float(timeout) if remaining + 0.5 >= float(timeout) else max(1.0, min(float(timeout), remaining))
                trace["keyNumbersTried"].append(key_number)
                attempt_trace: dict[str, Any] = {
                    "keyNumber": key_number,
                    "timeoutSeconds": round(call_timeout, 3),
                }
                trace["attempts"].append(attempt_trace)
                url = _mint_generate_content_url(self.base_url, answer_model, key_number)
                request = urllib.request.Request(
                    url,
                    data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                    headers={
                        "Content-Type": "application/json",
                        "x-goog-api-key": self.token,
                    },
                    method="POST",
                )
                trace["httpStarted"] = int(trace.get("httpStarted") or 0) + 1
                if trace.get("firstHttpStartSec") is None:
                    started = float(trace.get("startedAtMonotonic") or time.monotonic())
                    trace["firstHttpStartSec"] = round(max(0.0, time.monotonic() - started), 3)
                try:
                    with urllib.request.urlopen(request, timeout=call_timeout) as response:
                        trace["httpFinished"] = int(trace.get("httpFinished") or 0) + 1
                        trace["lastHttpStatus"] = int(getattr(response, "status", 0) or response.getcode() or 200)
                        attempt_trace["httpStatus"] = trace["lastHttpStatus"]
                        parsed = json.loads(response.read().decode("utf-8"))
                    answer = _extract_gemini_generate_content_text(parsed)
                    trace["status"] = "completed"
                    trace["selectedKeyNumber"] = key_number
                    attempt_trace["status"] = "completed"
                    return answer
                except urllib.error.HTTPError as exc:
                    trace["httpFinished"] = int(trace.get("httpFinished") or 0) + 1
                    trace["lastHttpStatus"] = exc.code
                    trace["lastHttpKeyNumber"] = key_number
                    attempt_trace["status"] = "http_error"
                    attempt_trace["httpStatus"] = exc.code
                    detail = _http_error_detail(exc)
                    last_error = f"Mint Gemini gateway returned HTTP {exc.code} for keyNumber={key_number}: {detail}"
                    if exc.code in retryable_statuses and index + 1 < len(self.key_numbers):
                        time.sleep(min(2.0, 0.2 * (index + 1)))
                        continue
                    raise RuntimeError(last_error) from exc
                except urllib.error.URLError as exc:
                    attempt_trace["status"] = "transport_error"
                    attempt_trace["error"] = str(exc.reason)[:160]
                    last_error = f"Mint Gemini gateway request failed for keyNumber={key_number}: {exc.reason}"
                    if _is_transport_timeout_error(exc.reason):
                        transport_timeouts += 1
                        attempt_trace["status"] = "transport_timeout"
                        trace["transportTimeouts"] = transport_timeouts
                        if transport_timeouts >= self.transport_timeout_limit or deadline - time.monotonic() <= 1.0:
                            raise RuntimeError(last_error) from exc
                    if index + 1 < len(self.key_numbers):
                        time.sleep(min(2.0, 0.2 * (index + 1)))
                        continue
                    raise RuntimeError(last_error) from exc
                except (OSError, TimeoutError) as exc:
                    trace["lastHttpKeyNumber"] = key_number
                    attempt_trace["status"] = "transport_timeout" if _is_transport_timeout_error(exc) else "transport_error"
                    attempt_trace["error"] = str(exc)[:160]
                    last_error = f"Mint Gemini gateway transport failed for keyNumber={key_number}: {exc}"
                    if _is_transport_timeout_error(exc):
                        transport_timeouts += 1
                        trace["transportTimeouts"] = transport_timeouts
                        if transport_timeouts >= self.transport_timeout_limit or deadline - time.monotonic() <= 1.0:
                            raise RuntimeError(last_error) from exc
                    if index + 1 < len(self.key_numbers):
                        time.sleep(min(2.0, 0.2 * (index + 1)))
                        continue
                    raise RuntimeError(last_error) from exc
                except json.JSONDecodeError as exc:
                    attempt_trace["status"] = "invalid_json"
                    raise RuntimeError("Mint Gemini gateway returned invalid JSON") from exc
            raise RuntimeError(last_error or "Mint Gemini gateway request failed")
        except Exception as exc:
            if trace.get("status") != "completed":
                trace["status"] = "error"
                trace["error"] = str(exc)[:240]
            raise
        finally:
            elapsed = max(0.0, time.monotonic() - float(trace.get("startedAtMonotonic") or time.monotonic()))
            trace["elapsedSec"] = round(elapsed, 3)
            if trace.get("firstHttpStartSec") is None:
                trace["preHttpWaitSec"] = round(elapsed, 3)
            else:
                trace["preHttpWaitSec"] = round(float(trace.get("firstHttpStartSec") or 0.0), 3)
            trace.pop("startedAtMonotonic", None)
            with self._trace_lock:
                self._last_trace_by_thread[threading.get_ident()] = dict(trace)

    def consume_last_call_trace(self) -> dict[str, Any] | None:
        with self._trace_lock:
            return self._last_trace_by_thread.pop(threading.get_ident(), None)


class LawkeyGeminiLLMClient:
    provider = "lawkey_gemini_generate_content"

    def __init__(
        self,
        *,
        default_model: str = DEFAULT_LAWKEY_WRITER_MODEL,
        timeout_seconds: float = 300.0,
        thinking_level: str = "",
    ) -> None:
        self.default_model = default_model
        self.timeout_seconds = timeout_seconds
        self.thinking_level = thinking_level
        self._trace_lock = threading.Lock()
        self._last_trace_by_thread: dict[int, dict[str, Any]] = {}

    def complete(self, messages: list[dict[str, str]], *, model: str = "", timeout_seconds: float | None = None) -> str:
        rag = _load_lawkey_rag_module()
        answer_model = model or self.default_model
        timeout = self.timeout_seconds if timeout_seconds is None else timeout_seconds
        trace: dict[str, Any] = {
            "provider": self.provider,
            "model": answer_model,
            "timeoutSeconds": float(timeout),
            "startedAtMonotonic": time.monotonic(),
            "httpStarted": 0,
            "httpFinished": 0,
            "firstHttpStartSec": None,
            "status": "running",
        }
        _LAWKEY_HTTP_TRACE_LOCAL.current = trace
        try:
            answer = rag._call_gemini_generate_content(
                messages,
                model=answer_model,
                timeout=int(timeout),
                thinking_level=self.thinking_level,
            )
            trace["status"] = "completed"
            return str(answer or "").strip()
        except Exception as exc:
            trace["status"] = "error"
            trace["error"] = str(exc)[:240]
            raise
        finally:
            elapsed = max(0.0, time.monotonic() - float(trace.get("startedAtMonotonic") or time.monotonic()))
            trace["elapsedSec"] = round(elapsed, 3)
            if trace.get("firstHttpStartSec") is None:
                trace["preHttpWaitSec"] = round(elapsed, 3)
            else:
                trace["preHttpWaitSec"] = round(float(trace.get("firstHttpStartSec") or 0.0), 3)
            trace.pop("startedAtMonotonic", None)
            with self._trace_lock:
                self._last_trace_by_thread[threading.get_ident()] = dict(trace)
            try:
                delattr(_LAWKEY_HTTP_TRACE_LOCAL, "current")
            except AttributeError:
                pass

    def consume_last_call_trace(self) -> dict[str, Any] | None:
        with self._trace_lock:
            return self._last_trace_by_thread.pop(threading.get_ident(), None)


class GemmaGatewayLLMClient:
    provider = "gemma_gateway_proxy"

    def __init__(
        self,
        *,
        gateway_url: str = DEFAULT_GEMMA_GATEWAY_URL,
        gateway_token: str,
        default_model: str = DEFAULT_LAWKEY_WRITER_MODEL,
        timeout_seconds: float = 300.0,
        max_output_tokens: int = 8192,
        temperature: float = 0.2,
    ) -> None:
        self.gateway_url = str(gateway_url or DEFAULT_GEMMA_GATEWAY_URL).strip() or DEFAULT_GEMMA_GATEWAY_URL
        self.gateway_token = str(gateway_token or "").strip()
        if not self.gateway_token:
            raise RuntimeError("RELIGION_GEMMA_GATEWAY_TOKEN is required for gemma_gateway provider")
        self.default_model = str(default_model or DEFAULT_LAWKEY_WRITER_MODEL).strip() or DEFAULT_LAWKEY_WRITER_MODEL
        self.timeout_seconds = float(timeout_seconds)
        self.max_output_tokens = int(max_output_tokens)
        self.temperature = float(temperature)
        self._trace_lock = threading.Lock()
        self._last_trace_by_thread: dict[int, dict[str, Any]] = {}

    def complete(self, messages: list[dict[str, str]], *, model: str = "", timeout_seconds: float | None = None) -> str:
        answer_model = model or self.default_model
        timeout = self.timeout_seconds if timeout_seconds is None else float(timeout_seconds)
        request_messages, system_instruction = _split_gateway_messages(messages)
        payload = {
            "model": answer_model,
            "messages": request_messages,
            "temperature": self.temperature,
            "maxOutputTokens": self.max_output_tokens,
            "timeoutSeconds": timeout,
        }
        if system_instruction:
            payload["systemInstruction"] = system_instruction
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {self.gateway_token}",
            "User-Agent": "BunjumBeta6GemmaGateway/1.0",
        }
        trace: dict[str, Any] = {
            "provider": self.provider,
            "model": answer_model,
            "gatewayUrl": self.gateway_url,
            "timeoutSeconds": float(timeout),
            "maxOutputTokens": self.max_output_tokens,
            "startedAtMonotonic": time.monotonic(),
            "status": "running",
        }
        request = urllib.request.Request(self.gateway_url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                parsed = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            trace["status"] = "error"
            trace["httpStatus"] = exc.code
            trace["error"] = detail
            raise RuntimeError(f"Gemma gateway returned HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            trace["status"] = "error"
            trace["error"] = str(exc.reason)[:240]
            raise RuntimeError(f"Gemma gateway request failed: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            trace["status"] = "error"
            trace["error"] = "invalid JSON"
            raise RuntimeError("Gemma gateway returned invalid JSON") from exc
        finally:
            elapsed = max(0.0, time.monotonic() - float(trace.get("startedAtMonotonic") or time.monotonic()))
            trace["elapsedSec"] = round(elapsed, 3)
            trace.pop("startedAtMonotonic", None)
            with self._trace_lock:
                self._last_trace_by_thread[threading.get_ident()] = dict(trace)
        answer = str(parsed.get("answer") or "").strip() if isinstance(parsed, dict) else ""
        if not answer:
            raise RuntimeError("Gemma gateway returned no answer")
        trace["status"] = "completed"
        if isinstance(parsed, dict):
            trace["keyIndex"] = parsed.get("keyIndex")
            trace["keyFingerprint"] = parsed.get("keyFingerprint")
            trace["gatewayModel"] = parsed.get("model")
        with self._trace_lock:
            self._last_trace_by_thread[threading.get_ident()] = dict(trace)
        return answer

    def consume_last_call_trace(self) -> dict[str, Any] | None:
        with self._trace_lock:
            return self._last_trace_by_thread.pop(threading.get_ident(), None)


def _split_gateway_messages(messages: list[dict[str, str]]) -> tuple[list[dict[str, str]], str]:
    system_parts: list[str] = []
    request_messages: list[dict[str, str]] = []
    for message in messages:
        role = str(message.get("role") or "user").strip().lower()
        content = str(message.get("content") or message.get("text") or "").strip()
        if not content:
            continue
        if role == "system":
            system_parts.append(content)
            continue
        request_messages.append({"role": role, "content": content})
    if not request_messages:
        raise ValueError("Gemma gateway prompt requires at least one non-system message")
    return request_messages, "\n\n".join(system_parts).strip()


class GeminiLiveTextLLMClient:
    provider = "gemini_live_text"

    def __init__(
        self,
        *,
        script_dir: Path | str = DEFAULT_GEMINI_LIVE_SCRIPT_DIR,
        model: str = DEFAULT_GEMINI_LIVE_TEXT_MODEL,
        system_instruction: str = GEMINI_LIVE_TEXT_SYSTEM_INSTRUCTION,
        timeout_seconds: float = 150.0,
        max_attempts: int = 12,
        thinking_level: str = "",
    ) -> None:
        self.script_dir = Path(script_dir)
        self.model = str(model or DEFAULT_GEMINI_LIVE_TEXT_MODEL).strip() or DEFAULT_GEMINI_LIVE_TEXT_MODEL
        self.system_instruction = str(system_instruction or "").strip()
        self.timeout_seconds = float(timeout_seconds)
        self.max_attempts = max(1, int(max_attempts or 1))
        self.thinking_level = str(thinking_level or "").strip().upper()

    def complete(self, messages: list[dict[str, str]], *, model: str = "", timeout_seconds: float | None = None) -> str:
        timeout = self.timeout_seconds if timeout_seconds is None else float(timeout_seconds)
        prompt = _messages_to_gemini_live_prompt(messages)
        return _call_gemini_live_text(
            prompt,
            script_dir=self.script_dir,
            model=self.model,
            system=self.system_instruction,
            timeout=timeout,
            max_attempts=self.max_attempts,
            thinking_level=self.thinking_level,
        )


def _messages_to_gemini_live_prompt(messages: list[dict[str, str]]) -> str:
    parts: list[str] = []
    for message in messages:
        role = str(message.get("role") or "user").strip().upper() or "USER"
        content = str(message.get("content") or "").strip()
        if content:
            parts.append(f"{role}:\n{content}")
    if not parts:
        raise ValueError("Gemini Live prompt requires at least one non-empty message")
    return "\n\n".join(parts)


def _call_gemini_live_text(
    prompt: str,
    *,
    script_dir: Path,
    model: str,
    system: str,
    timeout: float,
    max_attempts: int,
    thinking_level: str = "",
) -> str:
    script_dir = Path(script_dir)
    if not script_dir.exists():
        raise RuntimeError(f"Gemini Live script directory is missing: {script_dir}")
    script_dir_text = str(script_dir)
    if script_dir_text not in sys.path:
        sys.path.insert(0, script_dir_text)
    try:
        from live_text import live_text
    except Exception as exc:
        raise RuntimeError(f"Gemini Live text adapter unavailable: {exc}") from exc
    old_level = os.environ.get("GEMINI_LIVE_THINKING_LEVEL")
    if thinking_level:
        os.environ["GEMINI_LIVE_THINKING_LEVEL"] = str(thinking_level).strip().upper()
    try:
        text = live_text(
            str(prompt or ""),
            model=str(model or DEFAULT_GEMINI_LIVE_TEXT_MODEL),
            system=str(system or ""),
            timeout=float(timeout),
            max_attempts=max(1, int(max_attempts or 1)),
        )
    finally:
        if thinking_level:
            if old_level is None:
                os.environ.pop("GEMINI_LIVE_THINKING_LEVEL", None)
            else:
                os.environ["GEMINI_LIVE_THINKING_LEVEL"] = old_level
    return str(text or "").strip()


def default_llm_client_from_env() -> LLMClient | None:
    provider = os.getenv("RELIGION_LLM_PROVIDER", "").strip().lower()
    if _env_flag("RELIGION_LLM_DISABLED") or _env_flag("RELIGION_DISABLE_LLM") or provider in {"none", "off", "disabled"}:
        return None
    if provider in {"gemma-gateway", "gateway", "gateway_proxy", "gemma_gateway_proxy"}:
        return GemmaGatewayLLMClient(
            gateway_url=os.getenv("RELIGION_GEMMA_GATEWAY_URL", DEFAULT_GEMMA_GATEWAY_URL).strip()
            or DEFAULT_GEMMA_GATEWAY_URL,
            gateway_token=os.getenv("RELIGION_GEMMA_GATEWAY_TOKEN", "").strip(),
            default_model=os.getenv("RELIGION_ANSWER_MODEL", DEFAULT_LAWKEY_WRITER_MODEL).strip()
            or DEFAULT_LAWKEY_WRITER_MODEL,
            timeout_seconds=float(os.getenv("RELIGION_GEMMA_GATEWAY_TIMEOUT_SECONDS", os.getenv("RELIGION_CHAT_TIMEOUT_SECONDS", "300"))),
            max_output_tokens=int(os.getenv("RELIGION_GEMMA_GATEWAY_MAX_OUTPUT_TOKENS", "8192")),
            temperature=float(os.getenv("RELIGION_GEMMA_GATEWAY_TEMPERATURE", "0.2")),
        )
    if provider in {"gemini_live", "gemini-live", "live", "live-api"}:
        return GeminiLiveTextLLMClient(
            script_dir=Path(os.getenv("RELIGION_GEMINI_LIVE_SCRIPT_DIR", str(DEFAULT_GEMINI_LIVE_SCRIPT_DIR))),
            model=os.getenv("RELIGION_GEMINI_LIVE_MODEL", DEFAULT_GEMINI_LIVE_TEXT_MODEL).strip()
            or DEFAULT_GEMINI_LIVE_TEXT_MODEL,
            timeout_seconds=float(os.getenv("RELIGION_GEMINI_LIVE_TIMEOUT_SECONDS", os.getenv("RELIGION_CHAT_TIMEOUT_SECONDS", "150"))),
            max_attempts=int(os.getenv("RELIGION_GEMINI_LIVE_MAX_ATTEMPTS", "12")),
            thinking_level=os.getenv("RELIGION_GEMINI_LIVE_THINKING_LEVEL", "").strip(),
        )
    api_url = os.getenv("RELIGION_CHAT_API_URL", "").strip()
    if api_url or provider in {"openai", "openai_compatible", "openai-compatible"}:
        if not api_url:
            api_url = "http://172.21.32.1:8046/v1/chat/completions"
        return OpenAICompatibleLLMClient(
            api_url=api_url,
            api_key=os.getenv("RELIGION_CHAT_API_KEY", "").strip(),
            timeout_seconds=float(os.getenv("RELIGION_CHAT_TIMEOUT_SECONDS", "180")),
        )
    direct_gemini_providers = {
        "",
        "lawkey",
        "lawkey_gemini",
        "gemini",
        "lawkey_gateway",
        "gemma_gateway",
        "lawkey_gemma_gateway",
    }
    if provider in direct_gemini_providers and _lawkey_gemini_keys_available():
        return LawkeyGeminiLLMClient(
            default_model=os.getenv("RELIGION_ANSWER_MODEL", DEFAULT_LAWKEY_WRITER_MODEL).strip()
            or DEFAULT_LAWKEY_WRITER_MODEL,
            timeout_seconds=float(os.getenv("RELIGION_CHAT_TIMEOUT_SECONDS", "300")),
            thinking_level=os.getenv("RELIGION_GEMINI_THINKING_LEVEL", "").strip(),
        )
    mint_gateway_providers = {
        "mint",
        "mint_gateway",
        "mint_direct_gateway",
        "mint_gemini",
        "mint_gemini_gateway",
        "gemini_gateway",
    }
    mint_gateway_token = _mint_gemini_gateway_token()
    if provider in direct_gemini_providers.union(mint_gateway_providers) and mint_gateway_token:
        return MintGeminiGatewayLLMClient(
            base_url=_mint_gemini_gateway_base_url(),
            token=mint_gateway_token,
            default_model=os.getenv("RELIGION_ANSWER_MODEL", DEFAULT_LAWKEY_WRITER_MODEL).strip()
            or DEFAULT_LAWKEY_WRITER_MODEL,
            timeout_seconds=float(os.getenv("RELIGION_CHAT_TIMEOUT_SECONDS", "300")),
            thinking_level=os.getenv("RELIGION_GEMINI_THINKING_LEVEL", "minimal").strip() or "minimal",
        )
    gateway_url = os.getenv("LAWKEY_GEMMA_GATEWAY_URL", os.getenv("RELIGION_GEMMA_GATEWAY_URL", "")).strip()
    gateway_token = _lawkey_gemma_gateway_token()
    public_gateway_providers = {"public_gemma_gateway", "public_lawkey_gateway", "public_gateway"}
    if provider in public_gateway_providers or (_env_flag("RELIGION_USE_PUBLIC_GEMMA_GATEWAY") and gateway_url):
        return LawkeyGemmaGatewayLLMClient(
            api_url=gateway_url or "https://lawkey.ai.kr/api/gemma-gateway/v1/chat",
            token=gateway_token,
            timeout_seconds=float(os.getenv("RELIGION_CHAT_TIMEOUT_SECONDS", "300")),
        )
    return None


def _lawkey_gemma_gateway_token() -> str:
    for name in (
        "LAWKEY_GEMMA_GATEWAY_TOKEN",
        "GEMMA_GATEWAY_TOKEN",
        "GATEWAY_CLIENT_TOKEN",
        "RELIGION_GEMMA_GATEWAY_TOKEN",
    ):
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def _mint_gemini_gateway_token() -> str:
    for name in (
        "MINT_GEMINI_GATEWAY_TOKEN",
        "MINT_DIRECT_GATEWAY_TOKEN",
        "RELIGION_MINT_GEMINI_GATEWAY_TOKEN",
        "RELIGION_MINT_GATEWAY_TOKEN",
        "RELIGION_GEMINI_DIRECT_GATEWAY_TOKEN",
        "GEMINI_GATEWAY_TOKEN",
    ):
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def _mint_gemini_gateway_base_url() -> str:
    for name in (
        "MINT_GEMINI_GATEWAY_BASE_URL",
        "MINT_DIRECT_GATEWAY_BASE_URL",
        "RELIGION_MINT_GEMINI_GATEWAY_BASE_URL",
        "RELIGION_MINT_GATEWAY_BASE_URL",
        "RELIGION_GEMINI_DIRECT_GATEWAY_BASE_URL",
    ):
        value = os.getenv(name, "").strip()
        if value:
            return value
    return "http://sourpineapple.iptime.org:25568"


def _mint_gateway_key_numbers(key_numbers: Iterable[int] | None = None) -> list[int]:
    raw_values: list[Any]
    if key_numbers is not None:
        raw_values = list(key_numbers)
    else:
        configured = (
            os.getenv("MINT_GEMINI_GATEWAY_KEY_NUMBERS", "")
            or os.getenv("MINT_DIRECT_GATEWAY_KEY_NUMBERS", "")
            or os.getenv("RELIGION_GEMINI_GATEWAY_KEY_NUMBERS", "")
        )
        raw_values = re.split(r"[\s,]+", configured.strip()) if configured.strip() else list(range(1, 11))
    numbers: list[int] = []
    for value in raw_values:
        try:
            number = int(value)
        except (TypeError, ValueError):
            continue
        if 1 <= number <= 10 and number not in numbers:
            numbers.append(number)
    return numbers or list(range(1, 11))


def _mint_gateway_call_deadline_seconds(timeout_seconds: float) -> float:
    timeout = float(timeout_seconds)
    default = max(10.0, min(timeout * 2.0, 120.0)) if timeout <= 120.0 else timeout
    try:
        configured = float(
            os.getenv("MINT_GEMINI_GATEWAY_CALL_DEADLINE_SECONDS", "")
            or os.getenv("RELIGION_MINT_GEMINI_GATEWAY_CALL_DEADLINE_SECONDS", "")
            or str(default)
        )
    except ValueError:
        configured = default
    return max(5.0, min(configured, 900.0))


def _mint_gateway_transport_timeout_limit() -> int:
    try:
        configured = int(
            os.getenv("MINT_GEMINI_GATEWAY_MAX_TRANSPORT_TIMEOUTS", "")
            or os.getenv("RELIGION_MINT_GEMINI_GATEWAY_MAX_TRANSPORT_TIMEOUTS", "")
            or "2"
        )
    except ValueError:
        configured = 2
    return max(1, min(configured, 10))


def _is_transport_timeout_error(exc: Any) -> bool:
    if isinstance(exc, TimeoutError):
        return True
    return "timed out" in str(exc).lower() or "timeout" in str(exc).lower()


def _mint_generate_content_url(base_url: str, model: str, key_number: int) -> str:
    quoted_model = urllib.parse.quote(str(model or DEFAULT_LAWKEY_WRITER_MODEL), safe="-_.")
    query = urllib.parse.urlencode({"keyNumber": int(key_number)})
    return f"{str(base_url or '').rstrip('/')}/v1beta/models/{quoted_model}:generateContent?{query}"


def _gemini_generate_content_payload(messages: list[dict[str, str]], *, thinking_level: str = "minimal") -> dict[str, Any]:
    contents: list[dict[str, Any]] = []
    system_texts: list[str] = []
    for message in messages[-24:]:
        role = str(message.get("role") or "user").strip().lower()
        text = str(message.get("text") or message.get("content") or "").strip()
        if not text:
            continue
        if role == "system":
            system_texts.append(text)
            continue
        if role == "assistant":
            role = "model"
        if role not in {"user", "model"}:
            role = "user"
        contents.append({"role": role, "parts": [{"text": text}]})
    if not contents:
        raise RuntimeError("Mint Gemini gateway requires at least one non-empty user/model message")
    if contents[-1]["role"] != "user":
        contents.append({"role": "user", "parts": [{"text": "Continue."}]})
    generation_config: dict[str, Any] = {
        "temperature": float(os.getenv("RELIGION_GEMINI_TEMPERATURE", os.getenv("RELIGION_GEMMA_GATEWAY_TEMPERATURE", "0.2"))),
    }
    if thinking_level:
        generation_config["thinkingConfig"] = {"thinkingLevel": thinking_level}
    if os.getenv("RELIGION_GEMINI_MAX_OUTPUT_TOKENS", "").strip():
        generation_config["maxOutputTokens"] = _env_int("RELIGION_GEMINI_MAX_OUTPUT_TOKENS", 2048, minimum=32, maximum=8192)
    payload: dict[str, Any] = {
        "contents": contents,
        "generationConfig": generation_config,
    }
    if system_texts:
        payload["systemInstruction"] = {"parts": [{"text": "\n\n".join(system_texts)}]}
    return payload


def _extract_gemini_generate_content_text(parsed: dict[str, Any]) -> str:
    candidates = parsed.get("candidates")
    if isinstance(candidates, list):
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            content = candidate.get("content")
            if not isinstance(content, dict):
                continue
            parts = content.get("parts")
            if not isinstance(parts, list):
                continue
            text = "\n".join(str(part.get("text") or "").strip() for part in parts if isinstance(part, dict) and part.get("text"))
            if text.strip():
                return text.strip()
    raise RuntimeError("Mint Gemini gateway returned no text answer")


def _beta6_structured_stage_llm_client(llm_client: LLMClient | None) -> LLMClient | None:
    if str(getattr(llm_client, "provider", "") or "") == "lawkey_gemma_gateway" and not _env_flag(
        "RELIGION_GEMMA_GATEWAY_STRUCTURED_STAGES"
    ):
        return None
    return llm_client


def _gateway_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    converted: list[dict[str, str]] = []
    for message in messages[-24:]:
        role = str(message.get("role") or "user").strip().lower()
        text = str(message.get("text") or message.get("content") or "").strip()
        if not text:
            continue
        if role == "assistant":
            role = "model"
        if role == "system":
            role = "user"
            text = f"System instruction:\n{text}"
        if role not in {"user", "model"}:
            role = "user"
        converted.append({"role": role, "text": text})
    if not converted:
        raise RuntimeError("Lawkey Gemma gateway requires at least one non-empty message")
    if converted[-1]["role"] != "user":
        converted.append({"role": "user", "text": "Continue."})
    return converted


def _extract_gateway_text(parsed: dict[str, Any]) -> str:
    for key in ("answer", "text", "content", "output"):
        value = parsed.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    message = parsed.get("message")
    if isinstance(message, dict):
        for key in ("text", "content"):
            value = message.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    choices = parsed.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0] or {}
        if isinstance(first, dict):
            message = first.get("message")
            if isinstance(message, dict):
                value = message.get("content") or message.get("text")
                if isinstance(value, str) and value.strip():
                    return value.strip()
            value = first.get("text") or first.get("content")
            if isinstance(value, str) and value.strip():
                return value.strip()
    candidates = parsed.get("candidates")
    if isinstance(candidates, list) and candidates:
        parts = (((candidates[0] or {}).get("content") or {}).get("parts") or [])
        text = "\n".join(str(part.get("text") or "").strip() for part in parts if isinstance(part, dict) and part.get("text"))
        if text.strip():
            return text.strip()
    raise RuntimeError("Lawkey Gemma gateway returned no text answer")


def _http_error_detail(exc: urllib.error.HTTPError) -> str:
    try:
        body = exc.read().decode("utf-8", errors="replace")
    except Exception:
        return "no response body"
    if not body:
        return "empty response body"
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return body[:500]
    detail = parsed.get("detail") or ((parsed.get("error") or {}).get("message") if isinstance(parsed.get("error"), dict) else parsed.get("error"))
    return str(detail or body)[:500]


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _trim_process_memory_after_job() -> dict[str, Any]:
    if _env_flag("RELIGION_DISABLE_JOB_MEMORY_TRIM"):
        return {"enabled": False, "gcCollected": 0, "mallocTrim": False}
    import gc

    collected = gc.collect()
    malloc_trim = False
    if sys.platform.startswith("linux"):
        try:
            import ctypes

            libc = ctypes.CDLL("libc.so.6")
            malloc_trim_fn = getattr(libc, "malloc_trim", None)
            if malloc_trim_fn is not None:
                malloc_trim_fn(0)
                malloc_trim = True
        except Exception:
            malloc_trim = False
    return {"enabled": True, "gcCollected": collected, "mallocTrim": malloc_trim}


def _load_lawkey_rag_module():
    scripts = Path(os.getenv("LAWKEY_WORKSPACE_SCRIPTS", str(DEFAULT_LAWKEY_WORKSPACE_SCRIPTS)))
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    import legal_evidence_rag as rag  # type: ignore

    # Simli already uses the Lawkey Gemini call style with Gemma 4 A4B as the
    # default. Some older Lawkey work16 snapshots do not list the A4B alias in
    # their fallback map, so add the same fallback chain without editing Lawkey.
    fallbacks = getattr(rag, "DIRECT_CHAT_MODEL_FALLBACKS", None)
    if isinstance(fallbacks, dict) and "gemma-4-26b-a4b-it" not in fallbacks:
        fallbacks["gemma-4-26b-a4b-it"] = [
            "gemma-4-26b",
            "gemma-4-27b",
            "gemma-3-27b-it",
            "gemini-3.1-pro",
            "gemini-2.5-flash",
        ]
    _install_lawkey_http_trace_hook(rag)
    return rag


def _install_lawkey_http_trace_hook(rag: Any) -> None:
    if getattr(rag, "_religion_http_trace_hook_installed", False):
        return
    original = getattr(rag, "record_runtime_http_activity", None)
    if not callable(original):
        return

    def wrapped_record_runtime_http_activity(status_path: Path | None, *, event: str, kind: str, model_name: str, detail: str = "") -> None:
        current = getattr(_LAWKEY_HTTP_TRACE_LOCAL, "current", None)
        if isinstance(current, dict):
            if event == "start":
                current["httpStarted"] = int(current.get("httpStarted") or 0) + 1
                if current.get("firstHttpStartSec") is None:
                    started = float(current.get("startedAtMonotonic") or time.monotonic())
                    current["firstHttpStartSec"] = round(max(0.0, time.monotonic() - started), 3)
            elif event == "finish":
                current["httpFinished"] = int(current.get("httpFinished") or 0) + 1
            current["lastHttpEvent"] = event
            current["lastHttpKind"] = kind
            current["lastHttpModel"] = model_name
            current["lastHttpDetail"] = str(detail or "")[:160]
        return original(status_path, event=event, kind=kind, model_name=model_name, detail=detail)

    setattr(rag, "record_runtime_http_activity", wrapped_record_runtime_http_activity)
    setattr(rag, "_religion_http_trace_hook_installed", True)


def _lawkey_gemini_keys_available() -> bool:
    try:
        rag = _load_lawkey_rag_module()
        return bool(rag.load_gemini_api_keys())
    except Exception:
        return False


@dataclass(frozen=True)
class Beta6RunContext:
    job_id: str
    product: ProductProfile
    query: str
    language: str
    ui_language: str
    detected_language: str
    limit: int
    run_dir: Path
    created_at: float
    monotonic_created_at: float = 0.0
    access_token_hash: str = ""
    session_token_hash: str = ""
    account_subject_hash: str = ""
    fast_mode: bool = False


class Beta6QueueFullError(RuntimeError):
    code = "beta6_queue_full"

    def __init__(self, capacity: dict[str, Any]) -> None:
        super().__init__("job queue full")
        self.capacity = dict(capacity)
        self.retry_after_seconds = int(self.capacity.get("retryAfterSeconds") or 0)


class Beta6JobManager:
    """Domain-neutral beta6-style runtime.

    This keeps the reusable lawkey beta6 shape: selected record manifest,
    large question chunks, prompt artifact, resumable run directory, and
    separate job status/result files. The legal writer prompt is not reused
    because it is law-specific; only the engine surface is shared.
    """

    def __init__(
        self,
        profiles: dict[str, ProductProfile] | None = None,
        *,
        runs_root: Path = DEFAULT_RUNS_ROOT,
        llm_client: LLMClient | None = None,
        model: str | None = None,
        max_workers: int | None = None,
        max_pending_jobs: int | None = None,
        resume_pending_jobs: bool | None = None,
        resume_pending_limit: int | None = None,
        defer_resume_pending_jobs: bool = False,
        local_execution_enabled: bool | None = None,
    ) -> None:
        self._profiles = profiles or PRODUCT_PROFILES
        self._runs_root = runs_root
        self._runs_root.mkdir(parents=True, exist_ok=True)
        self._llm_client = llm_client if llm_client is not None else default_llm_client_from_env()
        self._model = model or os.getenv("RELIGION_ANSWER_MODEL", "")
        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._max_workers = max(1, int(max_workers or os.getenv("RELIGION_JOB_WORKERS", "4")))
        self._max_pending_jobs = max(1, int(max_pending_jobs or os.getenv("RELIGION_JOB_MAX_PENDING", "64")))
        self._queue_retry_after_seconds = _env_int(
            "RELIGION_QUEUE_RETRY_AFTER_SECONDS",
            30,
            minimum=1,
            maximum=600,
        )
        self._queue_estimated_job_seconds = _env_int(
            "RELIGION_QUEUE_ESTIMATED_JOB_SECONDS",
            self._queue_retry_after_seconds,
            minimum=1,
            maximum=7200,
        )
        self._job_heartbeat_interval_seconds = _env_float(
            "RELIGION_JOB_HEARTBEAT_INTERVAL_SECONDS",
            15.0,
            minimum=0.01,
            maximum=300.0,
        )
        self._job_lease_timeout_seconds = _env_float(
            "RELIGION_JOB_LEASE_TIMEOUT_SECONDS",
            900.0,
            minimum=1.0,
            maximum=86_400.0,
        )
        self._pending_jobs = 0
        self._queue_order: list[str] = []
        self._external_status_job_ids: set[str] = set()
        self._executor = ThreadPoolExecutor(max_workers=self._max_workers, thread_name_prefix="beta6-job")
        self._local_execution_enabled = (
            _env_flag_default("RELIGION_LOCAL_JOB_EXECUTION_ENABLED", True)
            if local_execution_enabled is None
            else bool(local_execution_enabled)
        )
        self._resume_pending_jobs = (
            _env_flag_default("RELIGION_RESUME_PENDING_JOBS", True)
            if resume_pending_jobs is None
            else bool(resume_pending_jobs)
        )
        self._resume_pending_limit = max(
            0,
            int(
                resume_pending_limit
                if resume_pending_limit is not None
                else _env_int("RELIGION_RESUME_PENDING_LIMIT", 8, minimum=0, maximum=128)
            ),
        )
        self._resume_pending_started = False
        if self._resume_pending_jobs and self._resume_pending_limit and not defer_resume_pending_jobs:
            self.resume_pending_jobs()

    def resume_pending_jobs(self, *, limit: int | None = None) -> int:
        if not self._resume_pending_jobs:
            return 0
        if limit is None:
            with self._lock:
                if self._resume_pending_started:
                    return 0
                self._resume_pending_started = True
        return self._resume_durable_jobs(limit=limit)

    def shutdown(self, *, wait: bool = False, cancel_futures: bool = True) -> None:
        self._executor.shutdown(wait=wait, cancel_futures=cancel_futures)

    def create_job(
        self,
        *,
        product: str,
        query: str,
        language: str = "",
        limit: int = 8,
        analysis_mode: str = "",
        session_token: str = "",
        account_subject: str = "",
    ) -> dict[str, Any]:
        if not _valid_session_token(session_token):
            raise ValueError("session token is required")
        access_token = secrets.token_urlsafe(32)
        context = self._new_context(
            product=product,
            query=query,
            language=language,
            limit=limit,
            analysis_mode=analysis_mode,
            access_token_hash=_hash_job_access_token(access_token),
            session_token_hash=_hash_session_token(session_token),
            account_subject_hash=_hash_account_subject(account_subject),
        )
        status = self._enqueue_context(context, persist_request=True)
        status["accessToken"] = access_token
        return status

    def capacity_snapshot(self) -> dict[str, Any]:
        with self._lock:
            return self._capacity_snapshot_unlocked()

    def answer_sync(self, *, product: str, query: str, language: str = "", limit: int = 8, analysis_mode: str = "") -> dict[str, Any]:
        context = self._new_context(product=product, query=query, language=language, limit=limit, analysis_mode=analysis_mode)
        self._set_and_persist_status(context, self._status_payload(context, status="running"))
        try:
            return self._run_context(context)
        finally:
            _trim_process_memory_after_job()

    def get_status(self, job_id: str) -> dict[str, Any]:
        key = str(job_id or "").strip()
        return _public_status(self._raw_status(key))

    def authorize_job_access(
        self,
        job_id: str,
        token: str = "",
        session_token: str = "",
        account_subject: str = "",
    ) -> bool:
        key = str(job_id or "").strip()
        status = self._raw_status(key)
        expected_hash = str(status.get("accessTokenHash") or "")
        if not expected_hash:
            return True
        if not bool(token) or not secrets.compare_digest(expected_hash, _hash_job_access_token(token)):
            return False
        expected_session_hash = str(status.get("sessionTokenHash") or "")
        if not expected_session_hash:
            return True
        if not bool(session_token) or not secrets.compare_digest(expected_session_hash, _hash_session_token(session_token)):
            return False
        expected_account_hash = str(status.get("accountSubjectHash") or "")
        if not expected_account_hash:
            return True
        return bool(account_subject) and secrets.compare_digest(expected_account_hash, _hash_account_subject(account_subject))

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        key = str(job_id or "").strip()
        raw = self._raw_status(key)
        state = str(raw.get("status") or "")
        if state in {"completed", "failed", "interrupted", "cancelled"}:
            return _public_status(raw)
        cancelled = self._cancelled_status_payload(raw)
        with self._lock:
            self._remove_from_queue_order_unlocked(key)
            self._jobs[key] = dict(cancelled)
        _write_json(self._runs_root / key / "status.json", cancelled)
        self._persist_queue_row_from_status(cancelled)
        return _public_status(_with_live_progress(cancelled))

    def resume_durable_queue_once(self, *, limit: int | None = None) -> int:
        """Claim and enqueue retryable durable jobs once.

        This is the small public primitive an external queue worker can call in a
        loop. It intentionally reuses the same claim lease as startup resume.
        """

        if limit is None:
            limit = self._resume_pending_limit
        return self._resume_durable_jobs(limit=max(0, int(limit or 0)))

    def _raw_status(self, job_id: str) -> dict[str, Any]:
        key = str(job_id or "").strip()
        with self._lock:
            status = self._jobs.get(key)
            if status is not None:
                status = self._refresh_external_status_unlocked(key, dict(status))
                status = self._with_live_queue_unlocked(dict(status))
        if status is None:
            status_path = self._runs_root / key / "status.json"
            if status_path.exists():
                persisted = _load_json(status_path, {})
                return _with_live_progress(self._status_from_disk(key, status_path, persisted))
            raise KeyError("job not found")
        return _with_live_progress(dict(status))

    def get_result(self, job_id: str) -> dict[str, Any]:
        key = str(job_id or "").strip()
        result_path = self._runs_root / key / "result.json"
        if not result_path.exists():
            status = self.get_status(key)
            pending_result_path = result_path.with_name("result.json.pending")
            if status.get("status") == "completed" and pending_result_path.exists():
                try:
                    os.replace(pending_result_path, result_path)
                except OSError:
                    pass
                if result_path.exists():
                    return _load_json(result_path, {})
            if status.get("status") in {"failed", "queued", "running", "interrupted", "cancelled"}:
                raise RuntimeError(str(status.get("error") or "job not completed"))
            raise KeyError("result not found")
        return _load_json(result_path, {})

    def _run_job_thread(self, context: Beta6RunContext) -> None:
        stop_heartbeat = threading.Event()
        heartbeat_thread: threading.Thread | None = None
        try:
            if self._job_is_cancelled(context.job_id):
                return
            with self._lock:
                self._remove_from_queue_order_unlocked(context.job_id)
            self._set_progress(context, "starting", message="Preparing source search")
            if self._job_is_cancelled(context.job_id):
                return
            heartbeat_thread = threading.Thread(
                target=self._heartbeat_job_lease_loop,
                args=(context, stop_heartbeat),
                name=f"beta6-heartbeat-{context.job_id[:18]}",
                daemon=True,
            )
            heartbeat_thread.start()
            self._run_context(context)
        except Exception as exc:
            status = self._status_payload(context, status="failed", error=str(exc), stage="failed")
            self._set_and_persist_status(context, status)
        finally:
            stop_heartbeat.set()
            if heartbeat_thread is not None:
                heartbeat_thread.join(timeout=0.2)
            with self._lock:
                self._remove_from_queue_order_unlocked(context.job_id)
                self._pending_jobs = max(0, self._pending_jobs - 1)
            _trim_process_memory_after_job()

    def _run_context(self, context: Beta6RunContext) -> dict[str, Any]:
        started = time.time()
        stage_timer = _Beta6StageTimingTracker()
        llm_used = self._llm_client is not None
        writer_provider = str(getattr(self._llm_client, "provider", "custom_llm") or "custom_llm") if self._llm_client else ""
        active_model = self._model or str(getattr(self._llm_client, "default_model", "") or "")
        structured_llm_client = _beta6_structured_stage_llm_client(self._llm_client)

        def set_progress(stage: str, *, message: str = "", selected_count: int = 0, progress_meta: dict[str, Any] | None = None) -> None:
            stage_timer.mark(stage)
            self._set_progress(
                context,
                stage,
                message=message,
                selected_count=selected_count,
                progress_meta=progress_meta,
            )

        def progress_callback(stage, message="", meta=None):
            self._raise_if_cancelled(context)
            stage_timer.mark(str(stage or "starting"))
            self._set_progress(context, stage, message=message, progress_meta=meta)

        context.run_dir.mkdir(parents=True, exist_ok=True)
        self._raise_if_cancelled(context)
        checkpoint_resume = _checkpoint_resume_state()
        selected_checkpoint = _load_selected_records_checkpoint(context.run_dir)
        if selected_checkpoint is not None:
            selected_records, selector = selected_checkpoint
            selected_records = selected_records[: context.limit]
            rows = [_search_result_from_selected_record(record) for record in selected_records]
            selector["checkpointReused"] = True
            selector.setdefault("status", "completed")
            selector.setdefault("mode", "selected_records_checkpoint")
            selector.setdefault("selectionSource", "selected_records_checkpoint")
            selector.setdefault("selectedIds", [record.get("file_id") for record in selected_records if record.get("file_id")])
            selector.setdefault("candidateCount", len(selected_records))
            selector.setdefault("topK", context.limit)
            _mark_checkpoint_reuse(checkpoint_resume, "selectedRecords", "selected_records")
            _mark_checkpoint_reuse(checkpoint_resume, "selectedRecords", "selector_meta")
            set_progress(
                "chunking",
                message="Reusing selected records checkpoint",
                selected_count=len(selected_records),
            )
        else:
            selector_kwargs: dict[str, Any] = {
                "limit": context.limit,
                "llm_client": structured_llm_client,
                "model": active_model,
                "provider": writer_provider,
                "progress_callback": progress_callback,
            }
            selector_signature = inspect.signature(select_rows_with_beta6_llm).parameters
            if "fast_mode" in selector_signature:
                selector_kwargs["fast_mode"] = context.fast_mode
            if "cache_root" in selector_signature:
                selector_kwargs["cache_root"] = context.run_dir.parent / "_beta6_batch_cache"
            candidate_rows, selector = select_rows_with_beta6_llm(
                context.product,
                context.query,
                context.language,
                **selector_kwargs,
            )
            rows = candidate_rows[: context.limit]
            selected_records = [to_beta6_selected_record(row) for row in rows]
        direct_writer_after_empty_selector = _should_use_direct_writer_after_empty_selector(
            context.product,
            context.query,
            selector,
        )
        if direct_writer_after_empty_selector:
            suppressed_ids = [record.get("file_id") for record in selected_records if record.get("file_id")]
            if suppressed_ids:
                selector["suppressedSelectedIds"] = suppressed_ids
                selector["suppressedSelectedCount"] = len(suppressed_ids)
            selector["sourceSelectionSuppressed"] = True
            status = str(selector.get("status") or "")
            if status == "fallback_no_selection":
                selector["selectionSource"] = "direct_after_empty_llm_selection"
            elif status == "fallback_selector_error":
                selector["selectionSource"] = "direct_after_selector_local_recovery"
            selector["selectedIds"] = []
            selector["rawSelectedIds"] = []
            rows = []
            selected_records = []
        context_packets = _selector_context_packets_from_meta(selector)
        selected_path = context.run_dir / "selected_records.json"
        context_packets_path = context.run_dir / "context_packets.json"
        _write_json(selected_path, selected_records)
        _write_json(context_packets_path, context_packets)
        _write_json(context.run_dir / "selector_meta.json", selector)
        set_progress("chunking", message="Building selected-source context chunks", selected_count=len(selected_records))
        chunks, chunker = build_beta6_chunks_for_manifest(selected_records, selected_path=selected_path)
        selected_evidence = apply_selector_ledger_to_selected_evidence(
            _label_selected_evidence([_result_payload(row) for row in rows]),
            selector.get("selectorEvidenceLedger") or [],
        )
        claim_checkpoint = _load_claim_card_checkpoint(context.run_dir)
        if claim_checkpoint is not None:
            claim_cards, claim_analyzer, passage_windows = claim_checkpoint
            if not passage_windows:
                passage_windows = build_passage_windows(selected_records, claim_cards)
            claim_analyzer["checkpointReused"] = True
            _mark_checkpoint_reuse(checkpoint_resume, "claimCards", "claim_cards")
            _mark_checkpoint_reuse(checkpoint_resume, "claimCards", "claim_analyzer_meta")
            set_progress(
                "answer_plan",
                message="Reusing claim-card checkpoint",
                selected_count=len(selected_records),
            )
        else:
            set_progress("claim_cards", message=f"Analyzing {len(selected_records)} selected sources", selected_count=len(selected_records))
            claim_cards, claim_analyzer = build_claim_cards_for_selected_sources(
                context.product,
                context.query,
                selected_records,
                selected_evidence,
                language=context.language,
                llm_client=structured_llm_client,
                model=active_model,
                progress_callback=progress_callback,
                cache_root=context.run_dir.parent / "_beta6_batch_cache",
                chunks=chunks,
                fast_mode=context.fast_mode,
            )
            passage_windows = build_passage_windows(selected_records, claim_cards)
            _write_json(context.run_dir / "claim_cards.json", claim_cards)
            _write_json(context.run_dir / "passage_windows.json", passage_windows)
            _write_json(context.run_dir / "claim_analyzer_meta.json", claim_analyzer)
        query_structuring = describe_query_expansion(context.product, context.query)
        answer_plan_checkpoint = _load_answer_plan_checkpoint(context.run_dir)
        if answer_plan_checkpoint is not None:
            answer_plan = answer_plan_checkpoint
            answer_planner = _answer_planner_meta(answer_plan)
            answer_planner["checkpointReused"] = True
            _mark_checkpoint_reuse(checkpoint_resume, "answerPlan", "answer_plan")
            set_progress(
                "writer",
                message="Reusing answer-plan checkpoint",
                selected_count=len(selected_records),
            )
        else:
            set_progress("answer_plan", message="Planning claim coverage", selected_count=len(selected_records))
            answer_plan, answer_planner = build_answer_plan_for_claim_cards(
                context.product,
                context.query,
                context.language,
                claim_cards,
                llm_client=structured_llm_client,
                model=active_model,
                cache_root=context.run_dir.parent / "_beta6_batch_cache",
                selector_keywords=_selector_keywords_from_meta(selector),
            )
            _write_json(context.run_dir / "answer_plan.json", answer_plan)
        if direct_writer_after_empty_selector:
            messages = build_beta6_direct_messages(context.product, context.query, context.language)
        else:
            messages = build_beta6_messages(
                context.product,
                context.query,
                context.language,
                selected_records,
                claim_cards=claim_cards,
                answer_plan=answer_plan,
            )
        answer_sections = build_answer_sections(context.product, rows, selected_evidence, language=context.language)
        citation_map = build_citation_map(selected_evidence)
        add_claim_citations(citation_map, claim_cards)
        passages = build_passages(selected_evidence)
        set_progress("writer", message="Writing answer from selected evidence", selected_count=len(selected_records))
        if self._llm_client is None:
            answer = writer_required_markdown(context.product, selected_evidence, language=context.language)
            writer = build_writer_state(
                status="requires_llm",
                mode="evidence_selection_only",
                provider="",
                language=context.language,
                model=self._model,
                selected_count=len(selected_records),
            )
            answer_readiness = "evidence_selected_writer_required"
            coverage_report = build_coverage_report(
                context.product,
                answer,
                claim_cards,
                answer_plan,
                language=context.language,
                apply_patch=False,
            )
        else:
            direct_writer_after_writer_error = False
            try:
                raw_writer_answer, writer_cache_hit = complete_writer_with_cache(
                    context.product,
                    context.query,
                    context.language,
                    llm_client=self._llm_client,
                    model=self._model,
                    messages=messages,
                    cache_root=context.run_dir.parent / "_beta6_batch_cache",
                )
                answer = enforce_domain_answer_boundary(
                    context.product,
                    sanitize_writer_answer(raw_writer_answer, language=context.language),
                    language=context.language,
                )
                writer_status = "completed"
                writer_mode = "llm_writer_direct_after_empty_selector" if direct_writer_after_empty_selector else "llm_writer"
                writer_error = ""
                answer_readiness = "final_answer"
            except Exception as exc:
                writer_cache_hit = False
                writer_error = str(exc)
                writer_status = "provider_timeout_fallback" if _is_transport_timeout_error(exc) else "provider_error_fallback"
                writer_mode = "deterministic_writer_fallback"
                if (
                    not direct_writer_after_empty_selector
                    and _is_transport_timeout_error(exc)
                    and get_domain_adapter(context.product).parse_multiple_choice(context.query) is not None
                ):
                    try:
                        raw_writer_answer, writer_cache_hit = complete_writer_with_cache(
                            context.product,
                            context.query,
                            context.language,
                            llm_client=self._llm_client,
                            model=self._model,
                            messages=build_beta6_direct_messages(context.product, context.query, context.language),
                            cache_root=context.run_dir.parent / "_beta6_batch_cache",
                        )
                        answer = enforce_domain_answer_boundary(
                            context.product,
                            sanitize_writer_answer(raw_writer_answer, language=context.language),
                            language=context.language,
                        )
                        writer_status = "completed"
                        writer_mode = "llm_writer_direct_after_writer_error"
                        writer_error = ""
                        answer_readiness = "final_answer"
                        direct_writer_after_writer_error = True
                    except Exception as direct_exc:
                        writer_cache_hit = False
                        writer_error = f"{writer_error}; direct retry failed: {direct_exc}"
                if not direct_writer_after_writer_error:
                    fallback_records = [] if direct_writer_after_empty_selector else selected_records
                    fallback_claim_cards = [] if direct_writer_after_empty_selector else claim_cards
                    fallback_answer = (
                        f"{writer_required_markdown(context.product, [], language=context.language)}\n\n"
                        f"Writer provider fallback: {writer_error[:180]}"
                        if direct_writer_after_empty_selector
                        else _deterministic_writer_fallback_answer(
                            context.product,
                            context.query,
                            fallback_records,
                            fallback_claim_cards,
                            language=context.language,
                            error=writer_error,
                        )
                    )
                    answer = enforce_domain_answer_boundary(
                        context.product,
                        fallback_answer,
                        language=context.language,
                    )
                    answer_readiness = "provider_fallback_answer"
            set_progress("coverage", message="Checking planned claim coverage", selected_count=len(selected_records))
            coverage_report = build_coverage_report(
                context.product,
                answer,
                claim_cards,
                answer_plan,
                language=context.language,
                apply_patch=False,
            )
            coverage_report["status"] = "completed" if writer_status == "completed" else writer_status
            coverage_report["mode"] = (
                "writer_self_citation_report_no_forced_patch"
                if writer_status == "completed"
                else "deterministic_writer_fallback_no_forced_patch"
            )
            coverage_report["patchPolicy"] = "lawkey_beta6_skip_forced_coverage_patch"
            coverage_report["patched"] = False
            if writer_error:
                coverage_report["writerError"] = writer_error[:240]
            writer = build_writer_state(
                status=writer_status,
                mode=writer_mode,
                provider=writer_provider,
                language=context.language,
                model=active_model,
                selected_count=0 if (direct_writer_after_empty_selector or direct_writer_after_writer_error) else len(selected_records),
                cache_hit=writer_cache_hit,
                error=writer_error[:240],
            )

        claim_handoff = split_claim_cards_for_handoff(context.product, answer, claim_cards, answer_plan)
        candidate_claim_cards = claim_handoff["candidateClaimCards"]
        cited_claim_cards = claim_handoff["citedClaimCards"]
        uncited_candidate_claim_cards = claim_handoff["uncitedCandidateClaimCards"]
        stage_timer.finish("completed")
        stage_timings = stage_timer.entries()
        stage_timing_totals = stage_timer.totals()
        stage_timing_total_sec = stage_timer.total_seconds()
        artifacts = {
            "selectedRecords": str(context.run_dir / "selected_records.json"),
            "contextPackets": str(context.run_dir / "context_packets.json"),
            "claimCards": str(context.run_dir / "claim_cards.json"),
            "candidateClaimCards": str(context.run_dir / "candidate_claim_cards.json"),
            "citedClaimCards": str(context.run_dir / "cited_claim_cards.json"),
            "passageWindows": str(context.run_dir / "passage_windows.json"),
            "claimAnalyzer": str(context.run_dir / "claim_analyzer_meta.json"),
            "answerPlan": str(context.run_dir / "answer_plan.json"),
            "coverageReport": str(context.run_dir / "coverage_report.json"),
            "chunkPlan": str(context.run_dir / "chunk_plan.json"),
            "promptInput": str(context.run_dir / "prompt_input.json"),
            "result": str(context.run_dir / "result.json"),
        }
        result = {
            "jobId": context.job_id,
            "product": context.product.key,
            "query": context.query,
            "language": context.language,
            "analysisMode": _analysis_mode_name(context.fast_mode),
            "fastMode": context.fast_mode,
            "languageResolution": {
                "detectedLanguage": context.detected_language,
                "uiLanguage": context.ui_language,
                "answerLanguage": context.language,
                "priority": ["user_question_language", "ui_language", "product_default"],
            },
            "answer": answer,
            "answerMarkdown": answer,
            "answerReadiness": answer_readiness,
            "writer": writer,
            "selector": selector,
            "answerSections": answer_sections,
            "citationMap": citation_map,
            "passages": passages,
            "claimCards": claim_cards,
            "candidateClaimCards": candidate_claim_cards,
            "citedClaimCards": cited_claim_cards,
            "uncitedCandidateClaimCards": uncited_candidate_claim_cards,
            "candidateClaimIds": claim_handoff["candidateClaimIds"],
            "citedClaimIds": claim_handoff["citedClaimIds"],
            "uncitedCandidateClaimIds": claim_handoff["uncitedCandidateClaimIds"],
            "passageWindows": passage_windows,
            "answerPlan": answer_plan,
            "coverageReport": coverage_report,
            "sources": selected_evidence,
            "selectedEvidence": selected_evidence,
            "contextPackets": context_packets,
            "engine": engine_contract_payload(engine_name=_analysis_mode_name(context.fast_mode)),
            "beta6SelectedRecords": selected_records,
            "safetyNotice": context.product.safety_notice,
            "llmUsed": llm_used,
            "artifacts": artifacts,
            "beta6": {
                "analysisMode": _analysis_mode_name(context.fast_mode),
                "fastMode": context.fast_mode,
                "chunkTokenBudget": BETA6_CHUNK_TOKEN_BUDGET,
                "chunker": chunker,
                "queryStructuring": query_structuring,
                "selectedCount": len(selected_records),
                "candidateCount": selector.get("candidateCount", len(rows)),
                "contextPacketCount": len(context_packets),
                "chunkCount": len(chunks),
                "claimCardCount": len(claim_cards),
                "candidateClaimCount": len(candidate_claim_cards),
                "citedClaimCount": len(cited_claim_cards),
                "claimAnalyzer": claim_analyzer,
                "answerPlanner": answer_planner,
                "checkpointResume": checkpoint_resume,
                "coverageReport": {
                    "status": coverage_report.get("status", ""),
                    "patched": bool(coverage_report.get("patched")),
                    "missingClaimCount": len(coverage_report.get("missingClaimIds") or []),
                },
                "selectorStatus": selector.get("status", ""),
                "selectorProvider": selector.get("provider", ""),
                "selectorModel": selector.get("model", ""),
                "selectionSource": selector.get("selectionSource", ""),
                "keywordCacheHits": selector.get("keywordCacheHits", 0),
                "keywordCacheMisses": selector.get("keywordCacheMisses", 0),
                "keywordGenerationCacheHits": selector.get("keywordCacheHits", 0),
                "keywordGenerationCacheMisses": selector.get("keywordCacheMisses", 0),
                "keywordGenerationTrace": selector.get("keywordGenerationTrace", []),
                "candidateSearchCacheHits": selector.get("candidateSearchCacheHits", 0),
                "candidateSearchCacheMisses": selector.get("candidateSearchCacheMisses", 0),
                "candidateSearchTrace": selector.get("candidateSearchTrace", []),
                "selectorBatchTrace": selector.get("selectorBatchTrace", []),
                "selectorBatchCacheHits": selector.get("selectorBatchCacheHits", 0),
                "selectorBatchCacheMisses": selector.get("selectorBatchCacheMisses", 0),
                "selectorLocalRecoveryCount": selector.get("selectorLocalRecoveryCount", 0),
                "writerStatus": writer["status"],
                "writerProvider": writer.get("provider", ""),
                "writerCacheHit": bool(writer.get("cacheHit")),
                "stageTimings": stage_timings,
                "stageTimingTotals": stage_timing_totals,
                "stageTimingTotalSec": stage_timing_total_sec,
                "selectedEvidenceHandoff": "answerSections+citationMap+passages+claimCards+candidateClaimCards+citedClaimCards+passageWindows+answerPlan+coverageReport",
                "wallClockSec": stage_timing_total_sec,
            },
        }
        self._raise_if_cancelled(context)
        _write_json(context.run_dir / "claim_cards.json", claim_cards)
        _write_json(context.run_dir / "candidate_claim_cards.json", candidate_claim_cards)
        _write_json(context.run_dir / "cited_claim_cards.json", cited_claim_cards)
        _write_json(context.run_dir / "passage_windows.json", passage_windows)
        _write_json(context.run_dir / "claim_analyzer_meta.json", claim_analyzer)
        _write_json(context.run_dir / "answer_plan.json", answer_plan)
        _write_json(context.run_dir / "coverage_report.json", coverage_report)
        _write_json(context.run_dir / "chunk_plan.json", chunks)
        _write_json(context.run_dir / "prompt_input.json", {"messages": messages, "model": self._model})
        pending_result_path = context.run_dir / "result.json.pending"
        final_result_path = context.run_dir / "result.json"
        _write_json(pending_result_path, result)
        status = self._status_payload(context, status="completed", selected_count=len(selected_records), stage="completed")
        self._set_and_persist_status(context, status)
        os.replace(pending_result_path, final_result_path)
        return result

    def _new_context(
        self,
        *,
        product: str,
        query: str,
        language: str,
        limit: int,
        analysis_mode: str = "",
        access_token_hash: str = "",
        session_token_hash: str = "",
        account_subject_hash: str = "",
    ) -> Beta6RunContext:
        key = str(product or "").strip().lower()
        profile = self._profiles.get(key)
        if profile is None:
            raise KeyError("unknown product")
        normalized_query = str(query or "").strip()
        if not normalized_query:
            raise ValueError("query is required")
        ui_language = (language or profile.default_language).strip().lower()
        if ui_language not in profile.languages:
            raise ValueError("unsupported language")
        detected_language = detect_question_language(profile, normalized_query)
        normalized_language = detected_language or ui_language or profile.default_language
        if normalized_language not in profile.languages:
            normalized_language = ui_language
        fast_mode = _is_fast_analysis_mode(analysis_mode)
        normalized_limit = _beta6_top_k_for_query(profile, normalized_query, limit, fast_mode=fast_mode)
        job_id = f"job-{int(time.time() * 1000)}-{uuid.uuid4().hex[:10]}"
        return Beta6RunContext(
            job_id=job_id,
            product=profile,
            query=normalized_query,
            language=normalized_language,
            ui_language=ui_language,
            detected_language=detected_language,
            limit=normalized_limit,
            run_dir=self._runs_root / job_id,
            created_at=time.time(),
            monotonic_created_at=time.monotonic(),
            access_token_hash=access_token_hash,
            session_token_hash=session_token_hash,
            account_subject_hash=account_subject_hash,
            fast_mode=fast_mode,
        )

    def _context_from_request(self, request: dict[str, Any], status: dict[str, Any] | None = None) -> Beta6RunContext:
        fallback = status or {}
        job_id = str(request.get("jobId") or fallback.get("jobId") or "").strip()
        if not job_id:
            raise ValueError("request snapshot is missing jobId")
        key = str(request.get("product") or fallback.get("product") or "").strip().lower()
        profile = self._profiles.get(key)
        if profile is None:
            raise KeyError("unknown product")
        query = str(request.get("query") or fallback.get("query") or "").strip()
        if not query:
            raise ValueError("request snapshot is missing query")
        ui_language = str(request.get("uiLanguage") or fallback.get("uiLanguage") or profile.default_language).strip().lower()
        if ui_language not in profile.languages:
            ui_language = profile.default_language
        detected_language = str(request.get("detectedLanguage") or fallback.get("detectedLanguage") or "").strip().lower()
        language = str(request.get("language") or fallback.get("language") or detected_language or ui_language).strip().lower()
        if language not in profile.languages:
            language = ui_language
        try:
            limit = int(request.get("limit") or fallback.get("limit") or LAWKEY_DEFAULT_TOP_K_PRECEDENTS)
        except (TypeError, ValueError):
            limit = LAWKEY_DEFAULT_TOP_K_PRECEDENTS
        fast_mode = _is_fast_analysis_mode(request.get("analysisMode") or fallback.get("analysisMode") or ("fast" if request.get("fastMode") or fallback.get("fastMode") else ""))
        try:
            created_at = float(request.get("createdAt") or fallback.get("createdAt") or fallback.get("updatedAt") or time.time())
        except (TypeError, ValueError):
            created_at = time.time()
        return Beta6RunContext(
            job_id=job_id,
            product=profile,
            query=query,
            language=language,
            ui_language=ui_language,
            detected_language=detected_language,
            limit=_beta6_top_k_for_query(profile, query, limit, fast_mode=fast_mode),
            run_dir=self._runs_root / job_id,
            created_at=created_at,
            monotonic_created_at=time.monotonic(),
            access_token_hash=str(request.get("accessTokenHash") or fallback.get("accessTokenHash") or ""),
            session_token_hash=str(request.get("sessionTokenHash") or fallback.get("sessionTokenHash") or ""),
            account_subject_hash=str(request.get("accountSubjectHash") or fallback.get("accountSubjectHash") or ""),
            fast_mode=fast_mode,
        )

    def _status_payload(
        self,
        context: Beta6RunContext,
        *,
        status: str,
        selected_count: int = 0,
        error: str = "",
        stage: str | None = None,
        stage_message: str = "",
        progress_meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = {
            "jobId": context.job_id,
            "product": context.product.key,
            "query": context.query,
            "language": context.language,
            "uiLanguage": context.ui_language,
            "detectedLanguage": context.detected_language,
            "status": status,
            "analysisMode": _analysis_mode_name(context.fast_mode),
            "fastMode": context.fast_mode,
            "limit": context.limit,
            "selectedCount": selected_count,
            "error": error,
            "createdAt": context.created_at,
            "updatedAt": time.time(),
            "ownerPid": os.getpid(),
        }
        if not self._local_execution_enabled and status == "queued":
            payload["executionMode"] = "durable_queue_only"
            payload["externalWorkerRequired"] = True
        monotonic_created_at = float(context.monotonic_created_at or time.monotonic())
        payload["monotonicCreatedAt"] = monotonic_created_at
        payload["monotonicElapsedSeconds"] = round(max(0.0, time.monotonic() - monotonic_created_at), 1)
        if context.access_token_hash:
            payload["accessTokenHash"] = context.access_token_hash
        if context.session_token_hash:
            payload["sessionTokenHash"] = context.session_token_hash
        if context.account_subject_hash:
            payload["accountSubjectHash"] = context.account_subject_hash
        if status == "running":
            payload["workerLease"] = self._worker_lease_payload(heartbeat_at=payload["updatedAt"])
        progress = _progress_from_status(
            payload,
            stage=stage or _default_stage_for_status(status),
            message=stage_message,
            meta=progress_meta,
        )
        payload["progress"] = progress
        payload["elapsedSeconds"] = progress["elapsedSeconds"]
        return payload

    def _request_payload(self, context: Beta6RunContext) -> dict[str, Any]:
        payload = {
            "jobId": context.job_id,
            "product": context.product.key,
            "query": context.query,
            "language": context.language,
            "uiLanguage": context.ui_language,
            "detectedLanguage": context.detected_language,
            "limit": context.limit,
            "analysisMode": _analysis_mode_name(context.fast_mode),
            "fastMode": context.fast_mode,
            "schemaVersion": 1,
            "createdAt": context.created_at,
        }
        if context.access_token_hash:
            payload["accessTokenHash"] = context.access_token_hash
        if context.session_token_hash:
            payload["sessionTokenHash"] = context.session_token_hash
        if context.account_subject_hash:
            payload["accountSubjectHash"] = context.account_subject_hash
        return payload

    def _enqueue_context(
        self,
        context: Beta6RunContext,
        *,
        persist_request: bool,
        resumed_from: str = "",
        resume_count: int = 0,
        inherited_status: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        status = self._status_payload(context, status="queued")
        if inherited_status:
            for key in ("executionMode", "externalWorkerRequired"):
                if key in inherited_status:
                    status[key] = inherited_status[key]
        if resumed_from:
            status["resumedFrom"] = resumed_from
            status["resumeCount"] = resume_count
        with self._lock:
            if self._pending_jobs >= self._max_pending_jobs:
                raise Beta6QueueFullError(self._capacity_snapshot_unlocked())
            self._pending_jobs += 1
            self._queue_order.append(context.job_id)
            self._jobs[context.job_id] = dict(status)
        try:
            if persist_request:
                self._persist_request(context)
            self._persist_status(context, status)
            self._persist_queue_row_from_status(self.get_status(context.job_id))
            if self._local_execution_enabled:
                self._executor.submit(self._run_job_thread, context)
        except Exception:
            with self._lock:
                self._remove_from_queue_order_unlocked(context.job_id)
                self._pending_jobs = max(0, self._pending_jobs - 1)
            failed = self._status_payload(context, status="failed", error="failed to submit job")
            self._set_and_persist_status(context, failed)
            raise
        return self.get_status(context.job_id)

    def _set_progress(
        self,
        context: Beta6RunContext,
        stage: str,
        *,
        message: str = "",
        selected_count: int = 0,
        progress_meta: dict[str, Any] | None = None,
    ) -> None:
        self._set_and_persist_status(
            context,
            self._status_payload(
                context,
                status="running",
                selected_count=selected_count,
                stage=stage,
                stage_message=message,
                progress_meta=progress_meta,
            ),
        )

    def _set_status(self, job_id: str, status: dict[str, Any]) -> None:
        with self._lock:
            self._jobs[job_id] = dict(status)

    def _persist_request(self, context: Beta6RunContext) -> None:
        _write_json(context.run_dir / "request.json", self._request_payload(context))

    def _persist_status(self, context: Beta6RunContext, status: dict[str, Any]) -> None:
        _write_json(context.run_dir / "status.json", status)
        self._persist_queue_row(context, status)

    def _set_and_persist_status(self, context: Beta6RunContext, status: dict[str, Any]) -> None:
        with self._lock:
            current = self._jobs.get(context.job_id)
            if status.get("status") != "cancelled" and current and current.get("status") == "cancelled":
                return
            if current:
                for key in ("resumedFrom", "resumeCount", "executionMode", "externalWorkerRequired"):
                    if key in current and key not in status:
                        status[key] = current[key]
            self._persist_status(context, status)
            self._jobs[context.job_id] = dict(status)

    def _queue_row_root(self) -> Path:
        return self._runs_root / "_beta6_queue"

    def _queue_row_path(self, job_id: str) -> Path:
        return self._queue_row_root() / f"{str(job_id or '').strip()}.json"

    def _queue_row_payload(self, status: dict[str, Any]) -> dict[str, Any]:
        row = dict(status)
        state = str(row.get("status") or "")
        row["queueRowSchemaVersion"] = 1
        row["queueRowUpdatedAt"] = time.time()
        row["terminal"] = state in {"completed", "failed", "interrupted", "cancelled"}
        row.setdefault("ownerPid", os.getpid())
        return row

    def _persist_queue_row(self, context: Beta6RunContext, status: dict[str, Any]) -> None:
        row = self._queue_row_payload(status)
        row.setdefault("jobId", context.job_id)
        row.setdefault("product", context.product.key)
        row.setdefault("query", context.query)
        row.setdefault("language", context.language)
        row.setdefault("uiLanguage", context.ui_language)
        row.setdefault("limit", context.limit)
        _write_json(self._queue_row_path(context.job_id), row)

    def _persist_queue_row_from_status(self, status: dict[str, Any]) -> None:
        job_id = str(status.get("jobId") or "").strip()
        if not job_id:
            return
        _write_json(self._queue_row_path(job_id), self._queue_row_payload(status))

    def _status_from_disk(self, job_id: str, status_path: Path, status: dict[str, Any]) -> dict[str, Any]:
        if status.get("status") not in {"queued", "running"}:
            return dict(status)
        if status.get("status") == "queued" and status.get("externalWorkerRequired"):
            return dict(status)
        if _worker_lease_expired(status):
            return self._interrupt_persisted_status(
                job_id,
                status_path,
                status,
                error="Job worker lease expired before completion. Please retry the saved question.",
            )
        if _owner_process_alive(status):
            return dict(status)
        return self._interrupt_persisted_status(
            job_id,
            status_path,
            status,
            error="Job was interrupted by a server restart before completion. Please retry the saved question.",
        )

    def _interrupt_persisted_status(
        self,
        job_id: str,
        status_path: Path,
        status: dict[str, Any],
        *,
        error: str,
    ) -> dict[str, Any]:
        interrupted = dict(status)
        interrupted.update(
            {
                "status": "interrupted",
                "error": error,
                "canRetry": True,
                "updatedAt": time.time(),
                "previousStatus": status.get("status", ""),
            }
        )
        interrupted.setdefault("createdAt", status.get("updatedAt") or time.time())
        interrupted["progress"] = _progress_from_status(interrupted, stage="interrupted", message=interrupted["error"])
        interrupted["elapsedSeconds"] = interrupted["progress"]["elapsedSeconds"]
        _write_json(status_path, interrupted)
        with self._lock:
            self._jobs[job_id] = dict(interrupted)
        return interrupted

    def _refresh_external_status_unlocked(self, job_id: str, status: dict[str, Any]) -> dict[str, Any]:
        if not self._should_refresh_external_status(status) and job_id not in self._external_status_job_ids:
            return status
        status_path = self._runs_root / job_id / "status.json"
        if not status_path.exists():
            return status
        self._external_status_job_ids.add(job_id)
        disk_status = _load_json(status_path, {})
        if not isinstance(disk_status, dict):
            return status
        disk_status = self._status_from_disk(job_id, status_path, disk_status)
        if not self._disk_status_is_newer(status, disk_status):
            return status
        self._jobs[job_id] = dict(disk_status)
        disk_state = str(disk_status.get("status") or "")
        if disk_state in {"completed", "failed", "interrupted", "cancelled"}:
            self._remove_from_queue_order_unlocked(job_id)
            self._pending_jobs = max(0, self._pending_jobs - 1)
            self._external_status_job_ids.discard(job_id)
        elif disk_state == "running":
            self._remove_from_queue_order_unlocked(job_id)
        return dict(disk_status)

    def _should_refresh_external_status(self, status: dict[str, Any]) -> bool:
        state = str(status.get("status") or "")
        if state in {"completed", "failed", "interrupted", "cancelled"}:
            return False
        return bool(status.get("externalWorkerRequired") or status.get("queueClaim"))

    def _disk_status_is_newer(self, current: dict[str, Any], disk_status: dict[str, Any]) -> bool:
        if not disk_status:
            return False
        if str(disk_status.get("jobId") or "") != str(current.get("jobId") or ""):
            return False
        if str(disk_status.get("status") or "") != str(current.get("status") or ""):
            return True
        try:
            return float(disk_status.get("updatedAt") or 0) > float(current.get("updatedAt") or 0)
        except (TypeError, ValueError):
            return False

    def _resume_durable_jobs(self, *, limit: int | None = None) -> int:
        resumed = 0
        resume_limit = self._resume_pending_limit if limit is None else max(0, int(limit))
        if resume_limit <= 0:
            return 0
        for job_dir in self._iter_durable_run_dirs():
            if resumed >= resume_limit:
                break
            status_path = job_dir / "status.json"
            request_path = job_dir / "request.json"
            if not status_path.exists() or not request_path.exists() or (job_dir / "result.json").exists():
                continue
            status = _load_json(status_path, {})
            request = _load_json(request_path, {})
            if not isinstance(status, dict) or not isinstance(request, dict):
                continue
            if not self._should_resume_status(status):
                continue
            try:
                job_id = str(request.get("jobId") or status.get("jobId") or job_dir.name)
                claimed_status = self._claim_durable_queue_row(job_id)
                if claimed_status is None:
                    continue
                context = self._context_from_request(request, claimed_status)
                previous_status = str(status.get("status") or "")
                resume_count = int(status.get("resumeCount") or 0) + 1
                self._enqueue_context(
                    context,
                    persist_request=False,
                    resumed_from=previous_status,
                    resume_count=resume_count,
                    inherited_status=claimed_status,
                )
                resumed += 1
            except RuntimeError as exc:
                if "job queue full" in str(exc):
                    break
            except Exception:
                continue
        return resumed

    def _capacity_snapshot_unlocked(self) -> dict[str, Any]:
        pending_jobs = max(0, int(self._pending_jobs))
        available_slots = max(0, int(self._max_pending_jobs) - pending_jobs)
        return {
            "maxWorkers": int(self._max_workers),
            "maxPendingJobs": int(self._max_pending_jobs),
            "pendingJobs": pending_jobs,
            "availablePendingSlots": available_slots,
            "saturated": pending_jobs >= int(self._max_pending_jobs),
            "retryAfterSeconds": int(self._queue_retry_after_seconds),
        }

    def _remove_from_queue_order_unlocked(self, job_id: str) -> None:
        key = str(job_id or "").strip()
        if not key or key not in self._queue_order:
            return
        self._queue_order = [item for item in self._queue_order if item != key]

    def _durable_queue_claim_timeout_seconds(self) -> float:
        return _env_float("RELIGION_DURABLE_QUEUE_CLAIM_TIMEOUT_SECONDS", 30.0, minimum=0.0, maximum=900.0)

    def _durable_queue_claim_stale_seconds(self) -> float:
        return _env_float("RELIGION_DURABLE_QUEUE_CLAIM_STALE_SECONDS", 120.0, minimum=1.0, maximum=3600.0)

    def _durable_queue_claim_poll_seconds(self) -> float:
        return _env_float("RELIGION_DURABLE_QUEUE_CLAIM_POLL_SECONDS", 0.05, minimum=0.01, maximum=1.0)

    def _queue_claim_lock_path(self, job_id: str) -> Path:
        return self._queue_row_root() / f".{str(job_id or '').strip()}.claim.lock"

    def _queue_claim_payload(self) -> dict[str, Any]:
        now = time.time()
        timeout_seconds = self._durable_queue_claim_stale_seconds()
        return {
            "ownerPid": os.getpid(),
            "thread": threading.get_ident(),
            "claimedAt": now,
            "expiresAt": now + timeout_seconds,
            "timeoutSeconds": timeout_seconds,
        }

    def _queue_claim_active(self, status: dict[str, Any]) -> bool:
        claim = status.get("queueClaim")
        if not isinstance(claim, dict):
            return False
        try:
            expires_at = float(claim.get("expiresAt") or 0)
        except (TypeError, ValueError):
            expires_at = 0.0
        return expires_at > time.time()

    def _queue_claim_lock_is_stale(self, lock_path: Path) -> bool:
        try:
            created_at = float((_load_json(lock_path, {}) or {}).get("claimedAt") or 0)
        except (TypeError, ValueError):
            created_at = 0.0
        if created_at <= 0:
            try:
                created_at = lock_path.stat().st_mtime
            except OSError:
                return True
        return time.time() - created_at > self._durable_queue_claim_stale_seconds()

    def _acquire_queue_claim_lock(self, lock_path: Path, *, deadline: float) -> bool:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        while True:
            try:
                fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                if self._queue_claim_lock_is_stale(lock_path):
                    try:
                        lock_path.unlink()
                    except OSError:
                        pass
                    continue
                if time.time() >= deadline:
                    return False
                time.sleep(min(self._durable_queue_claim_poll_seconds(), max(0.0, deadline - time.time())))
                continue
            try:
                os.write(fd, json.dumps(self._queue_claim_payload(), ensure_ascii=False).encode("utf-8"))
            finally:
                os.close(fd)
            return True

    def _release_queue_claim_lock(self, lock_path: Path) -> None:
        try:
            lock_path.unlink()
        except OSError:
            pass

    def _claim_durable_queue_row(self, job_id: str) -> dict[str, Any] | None:
        key = str(job_id or "").strip()
        if not key:
            return None
        status_path = self._runs_root / key / "status.json"
        if not status_path.exists():
            return None
        lock_path = self._queue_claim_lock_path(key)
        deadline = time.time() + self._durable_queue_claim_timeout_seconds()
        if not self._acquire_queue_claim_lock(lock_path, deadline=deadline):
            return None
        try:
            status = _load_json(status_path, {})
            if not isinstance(status, dict) or self._queue_claim_active(status) or not self._should_resume_status(status):
                return None
            claimed = dict(status)
            claimed["queueClaim"] = self._queue_claim_payload()
            claimed["updatedAt"] = time.time()
            _write_json(status_path, claimed)
            self._persist_queue_row_from_status(claimed)
            return claimed
        finally:
            self._release_queue_claim_lock(lock_path)

    def _queued_job_ids_unlocked(self) -> list[str]:
        queued: list[str] = []
        for job_id in self._queue_order:
            status = self._jobs.get(job_id)
            if status and status.get("status") == "queued":
                queued.append(job_id)
        self._queue_order = queued
        return list(queued)

    def _with_live_queue_unlocked(self, status: dict[str, Any]) -> dict[str, Any]:
        if status.get("status") != "queued":
            status.pop("queue", None)
            return status
        job_id = str(status.get("jobId") or "")
        queued_ids = self._queued_job_ids_unlocked()
        try:
            position = queued_ids.index(job_id) + 1
        except ValueError:
            position = 1
            queued_ids = [job_id, *queued_ids]
        running_jobs = sum(1 for item in self._jobs.values() if item.get("status") == "running")
        pending_ahead = max(0, position - 1)
        work_units_ahead = running_jobs + pending_ahead
        estimated_wait = int(round((work_units_ahead / max(1, self._max_workers)) * self._queue_estimated_job_seconds))
        if estimated_wait <= 0:
            estimated_wait = int(self._queue_estimated_job_seconds)
        queue = {
            "position": position,
            "pendingAhead": pending_ahead,
            "queuedJobs": len(queued_ids),
            "runningJobs": running_jobs,
            "maxWorkers": int(self._max_workers),
            "estimatedJobSeconds": int(self._queue_estimated_job_seconds),
            "estimatedWaitSeconds": estimated_wait,
        }
        status["queue"] = queue
        progress = dict(status.get("progress") or _progress_from_status(status, stage="queued"))
        progress["detail"] = _queue_progress_detail(str(status.get("uiLanguage") or status.get("language") or "en"), queue)
        progress["queue"] = queue
        status["progress"] = progress
        status["elapsedSeconds"] = progress.get("elapsedSeconds", _elapsed_seconds_from_status(status))
        return status

    def _iter_durable_run_dirs(self) -> list[Path]:
        ordered: list[Path] = []
        seen: set[str] = set()
        queue_root = self._queue_row_root()
        try:
            queue_rows = [path for path in queue_root.iterdir() if path.is_file() and path.suffix == ".json"]
        except FileNotFoundError:
            queue_rows = []

        row_candidates: list[tuple[float, str, Path]] = []
        for row_path in queue_rows:
            row = _load_json(row_path, {})
            if not isinstance(row, dict):
                continue
            job_id = str(row.get("jobId") or row_path.stem).strip()
            if not job_id:
                continue
            row_candidates.append((_durable_queue_order_timestamp(row, row_path), job_id, self._runs_root / job_id))

        for _, job_id, job_dir in sorted(row_candidates, key=lambda item: (item[0], item[1])):
            if job_id in seen:
                continue
            seen.add(job_id)
            ordered.append(job_dir)

        try:
            run_dirs = [path for path in self._runs_root.iterdir() if path.is_dir()]
        except FileNotFoundError:
            return ordered

        def sort_key(path: Path) -> float:
            status_path = path / "status.json"
            try:
                return status_path.stat().st_mtime
            except OSError:
                return 0.0

        for path in sorted(run_dirs, key=sort_key, reverse=True):
            if path.name == self._queue_row_root().name or path.name in seen:
                continue
            seen.add(path.name)
            ordered.append(path)
        return ordered

    def _should_resume_status(self, status: dict[str, Any]) -> bool:
        if self._queue_claim_active(status):
            return False
        state = str(status.get("status") or "")
        if state == "queued" and status.get("externalWorkerRequired"):
            return True
        if state == "running" and _worker_lease_expired(status):
            return True
        if state in {"queued", "running"}:
            return not _owner_process_alive(status)
        if state == "interrupted":
            return bool(status.get("canRetry"))
        return False

    def _worker_lease_payload(self, *, heartbeat_at: float | None = None) -> dict[str, Any]:
        now = heartbeat_at if heartbeat_at is not None else time.time()
        return {
            "ownerPid": os.getpid(),
            "heartbeatAt": now,
            "expiresAt": now + self._job_lease_timeout_seconds,
            "timeoutSeconds": self._job_lease_timeout_seconds,
            "heartbeatIntervalSeconds": self._job_heartbeat_interval_seconds,
        }

    def _heartbeat_job_lease_loop(self, context: Beta6RunContext, stop_event: threading.Event) -> None:
        while not stop_event.wait(self._job_heartbeat_interval_seconds):
            if not self._touch_worker_lease(context):
                return

    def _touch_worker_lease(self, context: Beta6RunContext) -> bool:
        now = time.time()
        with self._lock:
            current = self._jobs.get(context.job_id)
            if not current or current.get("status") != "running":
                return False
            updated = dict(current)
            updated["updatedAt"] = now
            updated["ownerPid"] = os.getpid()
            updated["workerLease"] = self._worker_lease_payload(heartbeat_at=now)
            progress = dict(updated.get("progress") or _progress_from_status(updated))
            progress["elapsedSeconds"] = _elapsed_seconds_from_status(updated)
            progress["heartbeatAt"] = updated["workerLease"]["heartbeatAt"]
            updated["progress"] = progress
            updated["elapsedSeconds"] = progress["elapsedSeconds"]
            updated["monotonicElapsedSeconds"] = progress["elapsedSeconds"]
            self._persist_status(context, updated)
            self._jobs[context.job_id] = dict(updated)
        return True

    def _job_is_cancelled(self, job_id: str) -> bool:
        with self._lock:
            status = self._jobs.get(str(job_id or "").strip())
        return bool(status and status.get("status") == "cancelled")

    def _raise_if_cancelled(self, context: Beta6RunContext) -> None:
        if self._job_is_cancelled(context.job_id):
            raise RuntimeError("job cancelled")

    def _cancelled_status_payload(self, status: dict[str, Any]) -> dict[str, Any]:
        now = time.time()
        cancelled = dict(status)
        cancelled.pop("workerLease", None)
        cancelled.update(
            {
                "status": "cancelled",
                "error": "Job cancelled by user.",
                "cancelRequested": True,
                "canRetry": True,
                "updatedAt": now,
                "previousStatus": status.get("status", ""),
            }
        )
        progress = _progress_from_status(cancelled, stage="cancelled", message="Job cancelled by user.")
        cancelled["progress"] = progress
        cancelled["elapsedSeconds"] = progress["elapsedSeconds"]
        return cancelled


def _checkpoint_resume_state() -> dict[str, Any]:
    return {
        "selectedRecords": False,
        "claimCards": False,
        "answerPlan": False,
        "reusedArtifacts": [],
    }


def _mark_checkpoint_reuse(state: dict[str, Any], key: str, artifact: str) -> None:
    state[key] = True
    reused = state.setdefault("reusedArtifacts", [])
    if artifact not in reused:
        reused.append(artifact)


def _load_selected_records_checkpoint(run_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any]] | None:
    records = _load_json(run_dir / "selected_records.json", [])
    if not isinstance(records, list):
        return None
    valid_records = [record for record in records if isinstance(record, dict) and str(record.get("file_id") or "").strip()]
    if not valid_records:
        return None
    selector = _load_json(run_dir / "selector_meta.json", {})
    if not isinstance(selector, dict):
        selector = {}
    return valid_records, dict(selector)


def _load_claim_card_checkpoint(run_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]] | None:
    cards = _load_json(run_dir / "claim_cards.json", [])
    if not isinstance(cards, list):
        return None
    valid_cards = [card for card in cards if isinstance(card, dict) and str(card.get("claimId") or "").strip()]
    if not valid_cards:
        return None
    analyzer = _load_json(run_dir / "claim_analyzer_meta.json", {})
    if not isinstance(analyzer, dict):
        analyzer = {}
    windows = _load_json(run_dir / "passage_windows.json", [])
    if not isinstance(windows, list):
        windows = []
    valid_windows = [window for window in windows if isinstance(window, dict)]
    return valid_cards, dict(analyzer), valid_windows


def _load_answer_plan_checkpoint(run_dir: Path) -> dict[str, Any] | None:
    plan = _load_json(run_dir / "answer_plan.json", {})
    if not isinstance(plan, dict):
        return None
    if not plan.get("bodyClaimIds") and not plan.get("coverageRequiredClaimIds") and not plan.get("status"):
        return None
    return dict(plan)


def _search_result_from_selected_record(record: dict[str, Any]) -> SearchResult:
    metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
    source_id = str(record.get("file_id") or "")
    title = str(record.get("document_title") or record.get("case_number") or source_id)
    citation = str(record.get("case_number") or title or source_id)
    return SearchResult(
        canonical_id=source_id,
        title=title,
        citation=citation,
        authority_body=str(record.get("court") or ""),
        source_date=str(record.get("decision_date") or ""),
        case_name=str(record.get("case_name") or title),
        case_type=str(record.get("doc_type") or ""),
        full_text=str(record.get("extracted_text") or record.get("anchor_text") or ""),
        source_dataset=str(metadata.get("dataset") or ""),
        source_path=str(record.get("relative_path") or record.get("absolute_path") or ""),
        score=_safe_float(record.get("score"), default=0.0),
        language=str(metadata.get("language") or ""),
        source_url=str(metadata.get("url") or ""),
        tradition=str(metadata.get("tradition") or ""),
        school=str(metadata.get("school") or ""),
        source_kind=str(metadata.get("sourceKind") or ""),
        authority_level=_safe_int(metadata.get("authorityLevel"), default=0),
        authority_label=str(metadata.get("authorityLabel") or ""),
    )


def _safe_float(value: Any, *, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _env_flag_default(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def _mcq_heuristics_enabled() -> bool:
    return _env_flag_default("RELIGION_MCQ_HEURISTICS_ENABLED", False)


def _mcq_structure_enabled() -> bool:
    return _env_flag_default("RELIGION_MCQ_STRUCTURE_ENABLED", True)


def _default_stage_for_status(status: str) -> str:
    if status == "queued":
        return "queued"
    if status == "completed":
        return "completed"
    if status == "failed":
        return "failed"
    if status == "interrupted":
        return "interrupted"
    if status == "cancelled":
        return "cancelled"
    return "starting"


def _progress_from_status(
    status: dict[str, Any],
    *,
    stage: str | None = None,
    message: str = "",
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved_stage = stage or _default_stage_for_status(str(status.get("status") or "running"))
    stage_count = len(BETA6_PROGRESS_STAGES)
    if resolved_stage in BETA6_PROGRESS_STAGES:
        stage_index = BETA6_PROGRESS_STAGES.index(resolved_stage)
        percent = round((stage_index / max(1, stage_count - 1)) * 100)
    elif resolved_stage in {"failed", "interrupted", "cancelled"}:
        stage_index = stage_count
        percent = 100
    else:
        stage_index = 1
        percent = 12
    elapsed = _elapsed_seconds_from_status(status)
    label = _progress_label(resolved_stage, str(status.get("uiLanguage") or status.get("language") or "en"))
    progress = {
        "stage": resolved_stage,
        "stageIndex": stage_index,
        "stageCount": stage_count,
        "percent": percent,
        "label": label,
        "message": message or label,
        "elapsedSeconds": elapsed,
        "heartbeatAt": status.get("updatedAt") or time.time(),
    }
    if isinstance(meta, dict):
        detail = str(meta.get("detail") or "").strip()
        if detail:
            progress["detail"] = detail
        batch = meta.get("batch")
        if isinstance(batch, dict):
            progress["batch"] = {
                "index": _safe_int(batch.get("index"), default=0),
                "count": _safe_int(batch.get("count"), default=0),
                "start": _safe_int(batch.get("start"), default=0),
                "end": _safe_int(batch.get("end"), default=0),
            }
    return progress


class _Beta6StageTimingTracker:
    def __init__(self) -> None:
        self._origin = time.monotonic()
        self._current_stage = "starting"
        self._current_started = self._origin
        self._current_events = 1
        self._entries: list[dict[str, Any]] = []
        self._closed = False

    def mark(self, stage: str) -> None:
        if self._closed:
            return
        normalized = str(stage or "starting").strip() or "starting"
        now = time.monotonic()
        if normalized == self._current_stage:
            self._current_events += 1
            return
        self._close_current(now)
        self._current_stage = normalized
        self._current_started = now
        self._current_events = 1

    def finish(self, final_stage: str = "completed") -> None:
        if self._closed:
            return
        self.mark(final_stage)
        self._close_current(time.monotonic())
        self._closed = True

    def entries(self) -> list[dict[str, Any]]:
        return [dict(entry) for entry in self._entries]

    def totals(self) -> dict[str, float]:
        totals: dict[str, float] = {}
        for entry in self._entries:
            stage = str(entry.get("stage") or "")
            if not stage:
                continue
            totals[stage] = round(totals.get(stage, 0.0) + float(entry.get("seconds") or 0.0), 3)
        return totals

    def total_seconds(self) -> float:
        if not self._entries:
            return 0.0
        return round(max(0.0, float(self._entries[-1].get("endOffsetSec") or 0.0)), 3)

    def _close_current(self, now: float) -> None:
        start_offset = max(0.0, self._current_started - self._origin)
        end_offset = max(start_offset, now - self._origin)
        self._entries.append(
            {
                "stage": self._current_stage,
                "seconds": round(max(0.0, now - self._current_started), 3),
                "startOffsetSec": round(start_offset, 3),
                "endOffsetSec": round(end_offset, 3),
                "events": self._current_events,
            }
        )


def _with_live_progress(status: dict[str, Any]) -> dict[str, Any]:
    copied = dict(status)
    elapsed = _elapsed_seconds_from_status(copied)
    progress = dict(copied.get("progress") or _progress_from_status(copied))
    progress["elapsedSeconds"] = elapsed
    worker_lease = copied.get("workerLease")
    if isinstance(worker_lease, dict) and worker_lease.get("heartbeatAt") is not None:
        progress["heartbeatAt"] = worker_lease.get("heartbeatAt")
    copied["progress"] = progress
    copied["elapsedSeconds"] = elapsed
    return copied


def _elapsed_seconds_from_status(status: dict[str, Any]) -> float:
    state = str(status.get("status") or "")
    try:
        monotonic_created_at = float(status.get("monotonicCreatedAt") or 0.0)
    except (TypeError, ValueError):
        monotonic_created_at = 0.0
    if state in {"queued", "running"} and monotonic_created_at > 0:
        try:
            owner_pid = int(status.get("ownerPid") or 0)
        except (TypeError, ValueError):
            owner_pid = 0
        if owner_pid == os.getpid():
            return round(max(0.0, time.monotonic() - monotonic_created_at), 1)
    try:
        monotonic_elapsed = status.get("monotonicElapsedSeconds")
        if monotonic_elapsed is not None:
            return round(max(0.0, float(monotonic_elapsed)), 1)
    except (TypeError, ValueError):
        pass
    now = time.time()
    try:
        created_at = float(status.get("createdAt") or status.get("updatedAt") or now)
    except (TypeError, ValueError):
        created_at = now
    if state in {"queued", "running"}:
        end = now
    else:
        try:
            end = float(status.get("updatedAt") or now)
        except (TypeError, ValueError):
            end = now
    return round(max(0.0, end - created_at), 1)


def _progress_label(stage: str, language: str) -> str:
    key = "ko" if language == "ko" else "en"
    return BETA6_PROGRESS_LABELS.get(key, BETA6_PROGRESS_LABELS["en"]).get(stage, stage.replace("_", " "))


def _emit_progress(
    progress_callback: Callable[..., None] | None,
    stage: str,
    message: str = "",
    meta: dict[str, Any] | None = None,
) -> None:
    if progress_callback is None:
        return
    try:
        progress_callback(stage, message, meta)
    except TypeError:
        try:
            progress_callback(stage, message)
        except Exception:
            return
    except Exception:
        return


def _env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        value = default
    return max(minimum, min(value, maximum))


def _env_float(name: str, default: float, *, minimum: float, maximum: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError:
        value = default
    return max(minimum, min(value, maximum))


def _env_int_from_config(config: Any) -> int:
    env_names = tuple(getattr(config, "env_names", ()) or ())
    default = int(getattr(config, "default"))
    minimum = int(getattr(config, "minimum"))
    maximum = int(getattr(config, "maximum"))
    for name in env_names:
        if os.getenv(name, "").strip():
            return _env_int(name, default, minimum=minimum, maximum=maximum)
    if env_names:
        return _env_int(env_names[-1], default, minimum=minimum, maximum=maximum)
    return max(minimum, min(default, maximum))


def _env_float_from_config(config: Any) -> float:
    env_names = tuple(getattr(config, "env_names", ()) or ())
    default = float(getattr(config, "default"))
    minimum = float(getattr(config, "minimum"))
    maximum = float(getattr(config, "maximum"))
    for name in env_names:
        if os.getenv(name, "").strip():
            return _env_float(name, default, minimum=minimum, maximum=maximum)
    if env_names:
        return _env_float(env_names[-1], default, minimum=minimum, maximum=maximum)
    return max(minimum, min(default, maximum))


def _env_flag_from_config(config: Any) -> bool:
    env_names = tuple(getattr(config, "env_names", ()) or ())
    for name in env_names:
        raw = os.getenv(name, "").strip()
        if raw:
            return raw.lower() in {"1", "true", "yes", "on"}
    return bool(getattr(config, "default"))


def _is_fast_analysis_mode(value: Any) -> bool:
    normalized = str(value or "").strip().lower()
    return normalized in {"fast", "quick", "beta6_fast", "fast_beta6", "빠른분석"}


def _analysis_mode_name(fast_mode: bool) -> str:
    return "beta6_fast" if fast_mode else BETA6_ANALYSIS_MODE


def _beta6_product_env_name(product: ProductProfile | None, suffix: str) -> str:
    key = str(getattr(product, "key", "") or "").strip().upper()
    if not key:
        return ""
    return f"RELIGION_{key}_BETA6_{suffix}"


def _beta6_fast_top_k_cap(product: ProductProfile | None = None) -> int:
    product_key = str(getattr(product, "key", "") or "").strip().lower()
    default = 30 if not product_key or product_key == "hindu" else 50
    product_env = _beta6_product_env_name(product, "FAST_TOP_K_PRECEDENTS")
    if product_env and os.getenv(product_env, "").strip():
        return _env_int(product_env, default, minimum=1, maximum=80)
    if os.getenv("RELIGION_BETA6_FAST_TOP_K_PRECEDENTS", "").strip():
        return _env_int("RELIGION_BETA6_FAST_TOP_K_PRECEDENTS", default, minimum=1, maximum=80)
    return default


def _effective_beta6_top_k(
    requested_limit: int | None = None,
    *,
    fast_mode: bool = False,
    product: ProductProfile | None = None,
) -> int:
    if fast_mode:
        fast_cap = _beta6_fast_top_k_cap(product)
        try:
            requested = int(requested_limit or fast_cap)
        except (TypeError, ValueError):
            requested = fast_cap
        return max(1, min(requested, fast_cap))
    default_top_k = _env_int("RELIGION_BETA6_TOP_K_PRECEDENTS", LAWKEY_DEFAULT_TOP_K_PRECEDENTS, minimum=1, maximum=300)
    try:
        requested = int(requested_limit or 0)
    except (TypeError, ValueError):
        requested = 0
    max_top_k = _env_int("RELIGION_BETA6_MAX_TOP_K_PRECEDENTS", 300, minimum=default_top_k, maximum=500)
    return max(1, min(max(default_top_k, requested), max_top_k))


def _beta6_top_k_for_query(
    profile: ProductProfile,
    query: str,
    requested_limit: int | None = None,
    *,
    fast_mode: bool = False,
) -> int:
    top_k = _effective_beta6_top_k(requested_limit, fast_mode=fast_mode, product=profile)
    if not _mcq_structure_enabled():
        return top_k
    parsed = get_domain_adapter(profile).parse_multiple_choice(query)
    if parsed is None:
        return top_k
    return max(top_k, min(5, len(parsed.options)))


def _beta6_keyword_count() -> int:
    return _env_int("RELIGION_BETA6_KEYWORD_COUNT", LAWKEY_DEFAULT_KEYWORD_COUNT, minimum=1, maximum=40)


def _beta6_keyword_rounds() -> int:
    return _env_int("RELIGION_BETA6_KEYWORD_ROUNDS", 3, minimum=1, maximum=8)


def _beta6_min_keyword_rounds(*, fast_mode: bool = False) -> int:
    rounds = _beta6_keyword_rounds()
    if fast_mode:
        return _env_int("RELIGION_BETA6_FAST_MIN_KEYWORD_ROUNDS", 1, minimum=1, maximum=rounds)
    requested = _env_int("RELIGION_BETA6_MIN_KEYWORD_ROUNDS", 2, minimum=1, maximum=8)
    return min(rounds, requested)


def _selector_timeout_seconds(product: ProductProfile | None = None) -> float:
    chat_timeout = _env_float("RELIGION_CHAT_TIMEOUT_SECONDS", 300.0, minimum=5.0, maximum=900.0)
    return _env_float_from_config(get_domain_adapter(product).selector_timeout_config(chat_timeout=chat_timeout))


def _selector_primary_timeout_seconds(product: ProductProfile | None = None) -> float:
    selector_timeout = _selector_timeout_seconds(product)
    return _env_float_from_config(get_domain_adapter(product).selector_primary_timeout_config(selector_timeout=selector_timeout))


def _claim_analyzer_timeout_seconds() -> float:
    chat_timeout = _env_float("RELIGION_CHAT_TIMEOUT_SECONDS", 300.0, minimum=5.0, maximum=900.0)
    return _env_float("RELIGION_CLAIM_ANALYZER_TIMEOUT_SECONDS", 120.0, minimum=5.0, maximum=chat_timeout)


def _answer_planner_timeout_seconds() -> float:
    chat_timeout = _env_float("RELIGION_CHAT_TIMEOUT_SECONDS", 300.0, minimum=5.0, maximum=900.0)
    return _env_float("RELIGION_ANSWER_PLANNER_TIMEOUT_SECONDS", 90.0, minimum=5.0, maximum=chat_timeout)


def _complete_llm(
    llm_client: LLMClient,
    messages: list[dict[str, str]],
    *,
    model: str,
    timeout_seconds: float | None = None,
) -> str:
    complete = llm_client.complete
    if timeout_seconds is not None:
        try:
            if "timeout_seconds" in inspect.signature(complete).parameters:
                return complete(messages, model=model, timeout_seconds=timeout_seconds)  # type: ignore[call-arg]
        except (TypeError, ValueError):
            pass
    return complete(messages, model=model)


def _consume_llm_call_trace(llm_client: LLMClient) -> dict[str, Any] | None:
    consumer = getattr(llm_client, "consume_last_call_trace", None)
    if not callable(consumer):
        return None
    try:
        trace = consumer()
    except Exception:
        return None
    return trace if isinstance(trace, dict) else None


def _prompt_size_metrics(messages: list[dict[str, str]]) -> dict[str, int]:
    content = "\n".join(str(message.get("content") or "") for message in messages)
    return {
        "promptChars": len(content),
        "promptBytes": len(content.encode("utf-8")),
    }


def _selector_llm_call_trace_summary(traces: list[dict[str, Any]]) -> dict[str, Any]:
    if not traces:
        return {
            "llmCallCount": 0,
            "llmHttpStartedCount": 0,
            "maxPreHttpWaitSec": 0.0,
            "maxLlmElapsedSec": 0.0,
            "maxPromptBytes": 0,
            "maxPromptChars": 0,
            "primaryLlmCallCount": 0,
            "primaryHttpStartedCount": 0,
            "primaryMaxPreHttpWaitSec": 0.0,
            "primaryMaxLlmElapsedSec": 0.0,
            "primaryMaxCandidateCount": 0,
            "primaryMaxPromptBytes": 0,
            "primaryMaxPromptChars": 0,
            "recoveryLlmCallCount": 0,
            "recoveryHttpStartedCount": 0,
            "recoveryMaxPreHttpWaitSec": 0.0,
            "recoveryMaxLlmElapsedSec": 0.0,
            "recoveryMaxCandidateCount": 0,
            "recoveryMaxPromptBytes": 0,
            "recoveryMaxPromptChars": 0,
        }

    def as_float(item: dict[str, Any], key: str) -> float:
        try:
            return float(item.get(key) or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def as_int(item: dict[str, Any], key: str) -> int:
        try:
            return int(item.get(key) or 0)
        except (TypeError, ValueError):
            return 0

    def phase_items(phase: str) -> list[dict[str, Any]]:
        return [trace for trace in traces if str(trace.get("selectorPhase") or "primary") == phase]

    def phase_summary(prefix: str, items: list[dict[str, Any]]) -> dict[str, Any]:
        if not items:
            return {
                f"{prefix}LlmCallCount": 0,
                f"{prefix}HttpStartedCount": 0,
                f"{prefix}MaxPreHttpWaitSec": 0.0,
                f"{prefix}MaxLlmElapsedSec": 0.0,
                f"{prefix}MaxCandidateCount": 0,
                f"{prefix}MaxPromptBytes": 0,
                f"{prefix}MaxPromptChars": 0,
            }
        return {
            f"{prefix}LlmCallCount": len(items),
            f"{prefix}HttpStartedCount": sum(as_int(trace, "httpStarted") for trace in items),
            f"{prefix}MaxPreHttpWaitSec": round(max(as_float(trace, "preHttpWaitSec") for trace in items), 3),
            f"{prefix}MaxLlmElapsedSec": round(max(as_float(trace, "elapsedSec") for trace in items), 3),
            f"{prefix}MaxCandidateCount": max(as_int(trace, "candidateCount") for trace in items),
            f"{prefix}MaxPromptBytes": max(as_int(trace, "promptBytes") for trace in items),
            f"{prefix}MaxPromptChars": max(as_int(trace, "promptChars") for trace in items),
        }

    return {
        "llmCallCount": len(traces),
        "llmHttpStartedCount": sum(int(trace.get("httpStarted") or 0) for trace in traces),
        "maxPreHttpWaitSec": round(max(as_float(trace, "preHttpWaitSec") for trace in traces), 3),
        "maxLlmElapsedSec": round(max(as_float(trace, "elapsedSec") for trace in traces), 3),
        "maxPromptBytes": max(as_int(trace, "promptBytes") for trace in traces),
        "maxPromptChars": max(as_int(trace, "promptChars") for trace in traces),
        **phase_summary("primary", phase_items("primary")),
        **phase_summary("recovery", phase_items("recovery")),
    }


def complete_keyword_generation_round_with_cache(
    product: ProductProfile,
    query: str,
    language: str,
    *,
    llm_client: LLMClient,
    model: str,
    round_number: int,
    keyword_count: int,
    messages: list[dict[str, str]],
    cache_root: Path | None,
) -> tuple[str, bool]:
    payload = {
        "cacheVersion": "keyword-generation-v1",
        "product": product.key,
        "query": query,
        "language": language,
        "model": model,
        "round": int(round_number),
        "keywordCount": int(keyword_count),
        "messages": messages,
    }

    def produce() -> dict[str, Any]:
        return {"raw": _complete_llm(llm_client, messages, model=model)}

    value, cache_hit = _read_or_fill_batch_cache("keyword_generation", payload, produce, cache_root=cache_root)
    return str(value.get("raw") or ""), cache_hit


def select_rows_with_beta6_llm(
    product: ProductProfile,
    query: str,
    language: str,
    *,
    limit: int,
    llm_client: LLMClient | None,
    model: str,
    provider: str,
    progress_callback: Callable[..., None] | None = None,
    cache_root: Path | None = None,
    fast_mode: bool = False,
    include_candidate_rows: bool = False,
) -> tuple[list[SearchResult], dict[str, Any]]:
    top_k = _effective_beta6_top_k(limit, fast_mode=fast_mode, product=product)
    frontier_target = _beta6_frontier_target(product, top_k, fast_mode=fast_mode)
    frontier_stop_floor = _beta6_frontier_stop_floor(product, top_k, fast_mode=fast_mode)
    per_keyword_limit = _beta6_per_keyword_limit(frontier_target, fast_mode=fast_mode, product=product)
    candidate_limit = max(frontier_target, 16)
    candidate_cache_stats: dict[str, Any] = {"hits": 0, "misses": 0, "trace": []}
    if llm_client is None:
        _emit_progress(progress_callback, "candidate_search", "Searching corpus candidates")
        base_rows = search_documents(product, query, limit=top_k, language=language)
        zero_source_bootstrap = False
        bootstrap_queries: list[str] = []
        if not base_rows:
            bootstrap_queries = _zero_source_bootstrap_queries(product)
            base_rows = _zero_source_bootstrap_rows(product, language=language, limit=top_k)
            zero_source_bootstrap = bool(base_rows)
        _emit_progress(progress_callback, "source_selection", "Selecting locally ranked evidence")
        selected_rows = local_fallback_select_rows(product, base_rows, limit=top_k)
        return selected_rows, {
            "status": "skipped",
            "mode": "local_search_only",
            "provider": "",
            "model": "",
            "selectionSource": "local_search_no_llm_bootstrap" if zero_source_bootstrap else "local_search_no_llm",
            "keywordSource": "local_query_expansion",
            "keywords": [],
            "zeroSourceBootstrap": zero_source_bootstrap,
            "zeroSourceBootstrapQueries": bootstrap_queries,
            "candidateCount": len(base_rows),
            "topK": top_k,
            "frontierTarget": frontier_target,
            "frontierStopFloor": frontier_stop_floor,
            "perKeywordLimit": per_keyword_limit,
            "fastMode": fast_mode,
            "selectedIds": [row.canonical_id for row in selected_rows],
            "reasoning": "",
            "message": "LLM selector is not connected; using local search/rerank candidates only.",
        }

    keywords: list[str] = []
    keyword_rounds: list[dict[str, Any]] = []
    keyword_generation_trace: list[dict[str, Any]] = []
    keyword_error = ""
    keyword_count = _beta6_keyword_count()
    candidates: list[SearchResult] = []
    keyword_round_limit = _beta6_keyword_rounds()
    min_keyword_rounds = _beta6_min_keyword_rounds(fast_mode=fast_mode)
    keyword_cache_hits = 0
    keyword_cache_misses = 0
    zero_source_bootstrap = False
    bootstrap_queries: list[str] = []
    for round_index in range(keyword_round_limit):
        round_number = round_index + 1
        keyword_cache_hit = False
        keyword_elapsed_sec = 0.0
        round_error = ""
        candidate_count_before = len(candidates)
        phase = "initial" if round_index == 0 else "additional"
        keyword_started_at: float | None = None
        try:
            keyword_messages = (
                build_beta6_keyword_messages(product, query, language, keyword_count=keyword_count)
                if round_index == 0
                else build_beta6_additional_keyword_messages(
                    product,
                    query,
                    language,
                    existing_keywords=keywords,
                    candidate_count=len(candidates),
                    target_count=frontier_target,
                    keyword_count=keyword_count,
                )
            )
            _emit_progress(
                progress_callback,
                "keyword_generation",
                "Preparing source search keywords" if round_index == 0 else "Refining source search keywords",
            )
            keyword_started_at = time.monotonic()
            keyword_raw, keyword_cache_hit = complete_keyword_generation_round_with_cache(
                product,
                query,
                language,
                llm_client=llm_client,
                model=model,
                round_number=round_number,
                keyword_count=keyword_count,
                messages=keyword_messages,
                cache_root=cache_root,
            )
            keyword_elapsed_sec = round(max(0.0, time.monotonic() - keyword_started_at), 3)
            if keyword_cache_hit:
                keyword_cache_hits += 1
            else:
                keyword_cache_misses += 1
            generated = parse_keyword_generation_response(keyword_raw, keyword_count=keyword_count)
        except Exception as exc:
            keyword_error = str(exc)
            round_error = keyword_error
            if keyword_started_at is not None:
                keyword_elapsed_sec = round(max(0.0, time.monotonic() - keyword_started_at), 3)
            generated = []
        new_keywords = []
        seen_keywords = set(keywords)
        for keyword in generated:
            if keyword and keyword not in seen_keywords:
                seen_keywords.add(keyword)
                new_keywords.append(keyword)
        keywords.extend(new_keywords)
        if round_index == 0 or new_keywords:
            candidate_search_keywords = (
                new_keywords
                if round_index > 0 and len(candidates) >= frontier_target and new_keywords
                else keywords
            )
            _emit_progress(
                progress_callback,
                "candidate_search",
                f"Searching corpus with {len(candidate_search_keywords) or 1} query plan terms",
            )
            candidates = collect_candidate_rows(
                product,
                query,
                language=language,
                limit=candidate_limit,
                keywords=candidate_search_keywords,
                initial=candidates,
                cache_root=cache_root,
                cache_stats=candidate_cache_stats,
                fast_mode=fast_mode,
            )
        keyword_generation_trace.append(
            {
                "round": round_number,
                "phase": phase,
                "keywordCount": len(generated),
                "newKeywordCount": len(new_keywords),
                "totalKeywordCount": len(keywords),
                "candidateCountBefore": candidate_count_before,
                "candidateCountAfter": len(candidates),
                "targetCount": top_k,
                "frontierTarget": frontier_target,
                "frontierStopFloor": frontier_stop_floor,
                "minimumRounds": min_keyword_rounds,
                "cacheHit": keyword_cache_hit,
                "elapsedSec": keyword_elapsed_sec,
                "error": round_error,
            }
        )
        keyword_rounds.append(
            {
                "round": round_index + 1,
                "newKeywords": new_keywords,
                "totalKeywords": list(keywords),
                "candidateCount": len(candidates),
                "targetCount": top_k,
                "frontierTarget": frontier_target,
                "frontierStopFloor": frontier_stop_floor,
                "minimumRounds": min_keyword_rounds,
                "cacheHit": keyword_cache_hit,
                "error": keyword_error if not new_keywords and keyword_error else "",
            }
        )
        if len(candidates) >= frontier_target and round_number >= min_keyword_rounds:
            break
        if len(candidates) >= frontier_stop_floor and round_index >= 1 and round_number >= min_keyword_rounds:
            break
        if keyword_error and round_index == 0:
            break
        if not new_keywords and round_index > 0:
            break
    if not candidates:
        try:
            candidates = search_documents(product, query, limit=candidate_limit, language=language)
        except Exception:
            candidates = []
    if not candidates:
        bootstrap_queries = _zero_source_bootstrap_queries(product)
        candidates = _zero_source_bootstrap_rows(product, language=language, limit=candidate_limit)
        zero_source_bootstrap = bool(candidates)
    try:
        _emit_progress(progress_callback, "source_selection", f"Selecting {min(len(candidates), top_k)} evidence records")
        candidates, frontier_meta = rank_beta6_candidate_frontier(
            product,
            query,
            candidates,
            keywords=keywords,
        )
        candidate_coverage = _mcq_candidate_coverage_meta(product, query, candidates)
        if candidate_coverage.get("lowCoverage") and _env_flag_default("RELIGION_MCQ_LOW_COVERAGE_HARD_GATE_ENABLED", False):
            return [], _attach_candidate_rows_to_selector_meta({
                "status": "fallback_low_coverage",
                "mode": "llm_keyword_search_low_coverage_direct",
                "provider": provider or "custom_llm",
                "model": model,
                "selectionSource": "direct_after_low_candidate_coverage",
                "keywordSource": "gemma4_keyword_generation" if keywords else "gemma4_keyword_generation_empty",
                "keywords": keywords,
                "keywordRounds": keyword_rounds,
                "keywordGenerationTrace": keyword_generation_trace,
                "keywordCacheHits": keyword_cache_hits,
                "keywordCacheMisses": keyword_cache_misses,
                "zeroSourceBootstrap": zero_source_bootstrap,
                "zeroSourceBootstrapQueries": bootstrap_queries,
                "candidateSearchCacheHits": candidate_cache_stats["hits"],
                "candidateSearchCacheMisses": candidate_cache_stats["misses"],
                "candidateSearchTrace": _candidate_search_trace(candidate_cache_stats),
                "candidateCount": len(candidates),
                "candidateCoverage": candidate_coverage,
                "topK": top_k,
                "frontierTarget": frontier_target,
                "frontierStopFloor": frontier_stop_floor,
                "perKeywordLimit": per_keyword_limit,
                "fastMode": fast_mode,
                **frontier_meta,
                "selectedIds": [],
                "rawSelectedIds": [],
                "reasoning": "candidate corpus coverage was too weak for source-grounded MCQ selection",
                "keywordError": keyword_error,
                "message": "Retrieved candidates did not cover enough of the MCQ stem, so beta6 skipped source selection and used a direct answer path.",
            }, product, candidates, include_candidate_rows)
        selected_rows, selected_ids, reasoning, selector_llm_meta = select_rows_with_beta6_selector(
            product,
            query,
            language,
            candidates,
            limit=top_k,
            llm_client=llm_client,
            model=model,
            progress_callback=progress_callback,
            cache_root=cache_root,
        )
        if selected_rows:
            selected_rows = fill_selected_rows(candidates, selected_rows, limit=top_k)
            selected_rows = get_domain_adapter(product).postprocess_selected_rows(
                query,
                candidates,
                selected_rows,
                limit=top_k,
            )
            selector_local_recovery = int(selector_llm_meta.get("selectorLocalRecoveryCount") or 0) > 0
            return selected_rows, _attach_candidate_rows_to_selector_meta({
                "status": "fallback_selector_error" if selector_local_recovery else "completed",
                "mode": selector_llm_meta.get("mode") or "llm_keyword_search_and_selector",
                "provider": provider or "custom_llm",
                "model": model,
                "selectionSource": (
                    "local_rerank_after_selector_error"
                    if selector_local_recovery
                    else selector_llm_meta.get("selectionSource") or "gemma4_llm_selector"
                ),
                "keywordSource": "gemma4_keyword_generation" if keywords else "gemma4_keyword_generation_empty",
                "keywords": keywords,
                "keywordRounds": keyword_rounds,
                "keywordGenerationTrace": keyword_generation_trace,
                "keywordCacheHits": keyword_cache_hits,
                "keywordCacheMisses": keyword_cache_misses,
                "zeroSourceBootstrap": zero_source_bootstrap,
                "zeroSourceBootstrapQueries": bootstrap_queries,
                "candidateSearchCacheHits": candidate_cache_stats["hits"],
                "candidateSearchCacheMisses": candidate_cache_stats["misses"],
                "candidateSearchTrace": _candidate_search_trace(candidate_cache_stats),
                "candidateCoverage": candidate_coverage,
                **selector_llm_meta,
                "candidateCount": len(candidates),
                "topK": top_k,
                "frontierTarget": frontier_target,
                "frontierStopFloor": frontier_stop_floor,
                "perKeywordLimit": per_keyword_limit,
                "fastMode": fast_mode,
                **frontier_meta,
                "selectedIds": [row.canonical_id for row in selected_rows],
                "rawSelectedIds": selected_ids,
                "reasoning": reasoning,
                "keywordError": keyword_error,
                "message": (
                    "The source selector timed out for at least one batch; deterministic local recovery filled that batch."
                    if selector_local_recovery
                    else "Search keywords were prepared, candidate anchors were reviewed, and source records were selected for the writer."
                ),
            }, product, candidates, include_candidate_rows)
        selected_rows = local_fallback_select_rows(product, candidates, limit=top_k)
        return selected_rows, _attach_candidate_rows_to_selector_meta({
            "status": "fallback_no_selection",
            "mode": "llm_keyword_search_selector_fallback",
            "provider": provider or "custom_llm",
            "model": model,
            "selectionSource": "local_rerank_after_empty_llm_selection",
            "keywordSource": "gemma4_keyword_generation" if keywords else "gemma4_keyword_generation_empty",
            "keywords": keywords,
            "keywordRounds": keyword_rounds,
            "keywordGenerationTrace": keyword_generation_trace,
            "keywordCacheHits": keyword_cache_hits,
            "keywordCacheMisses": keyword_cache_misses,
            "zeroSourceBootstrap": zero_source_bootstrap,
            "zeroSourceBootstrapQueries": bootstrap_queries,
            "candidateSearchCacheHits": candidate_cache_stats["hits"],
            "candidateSearchCacheMisses": candidate_cache_stats["misses"],
            "candidateSearchTrace": _candidate_search_trace(candidate_cache_stats),
            "candidateCoverage": candidate_coverage,
            **selector_llm_meta,
            "candidateCount": len(candidates),
            "topK": top_k,
            "frontierTarget": frontier_target,
            "frontierStopFloor": frontier_stop_floor,
            "perKeywordLimit": per_keyword_limit,
            "fastMode": fast_mode,
            "frontierScoredCount": len(candidates),
            "frontierTopDebug": [],
            "frontierReranker": "skipped_empty_selector_selection",
            "selectedIds": [row.canonical_id for row in selected_rows],
            "rawSelectedIds": selected_ids,
            "reasoning": reasoning,
            "keywordError": keyword_error,
            "message": "Gemma 4 selector returned no valid ids, so the runtime used the local candidate order.",
        }, product, candidates, include_candidate_rows)
    except Exception as exc:
        selected_rows = local_fallback_select_rows(product, candidates, limit=top_k)
        return selected_rows, _attach_candidate_rows_to_selector_meta({
            "status": "fallback_selector_error",
            "mode": "llm_keyword_search_selector_error_fallback",
            "provider": provider or "custom_llm",
            "model": model,
            "selectionSource": "local_rerank_after_selector_error",
            "keywordSource": "gemma4_keyword_generation" if keywords else "gemma4_keyword_generation_empty",
            "keywords": keywords,
            "keywordRounds": keyword_rounds,
            "keywordGenerationTrace": keyword_generation_trace,
            "keywordCacheHits": keyword_cache_hits,
            "keywordCacheMisses": keyword_cache_misses,
            "zeroSourceBootstrap": zero_source_bootstrap,
            "zeroSourceBootstrapQueries": bootstrap_queries,
            "candidateSearchCacheHits": candidate_cache_stats["hits"],
            "candidateSearchCacheMisses": candidate_cache_stats["misses"],
            "candidateSearchTrace": _candidate_search_trace(candidate_cache_stats),
            "candidateCount": len(candidates),
            "topK": top_k,
            "frontierTarget": frontier_target,
            "frontierStopFloor": frontier_stop_floor,
            "perKeywordLimit": per_keyword_limit,
            "fastMode": fast_mode,
            "frontierScoredCount": len(candidates),
            "frontierTopDebug": [],
            "frontierReranker": "skipped_selector_error",
            "selectedIds": [row.canonical_id for row in selected_rows],
            "reasoning": "",
            "keywordError": keyword_error,
            "error": str(exc),
            "message": "Gemma 4 selector failed; using local candidate order rather than fabricating evidence.",
        }, product, candidates, include_candidate_rows)


def _attach_candidate_rows_to_selector_meta(
    meta: dict[str, Any],
    product: ProductProfile,
    candidates: list[SearchResult],
    include_candidate_rows: bool,
) -> dict[str, Any]:
    if include_candidate_rows:
        limit = _selector_candidate_limit(product, candidate_count=len(candidates))
        meta["_candidateRows"] = candidates[:limit]
    return meta


def _zero_source_bootstrap_queries(product: ProductProfile) -> list[str]:
    key = product.key
    if key == "islam":
        return ["prayer salah quran hadith fiqh", "halal haram worship scripture"]
    if key == "buddhist":
        return ["dhamma karma sutta teaching", "buddha dharma scripture commentary"]
    if key == "catholic":
        return ["grace scripture church catechism", "christ faith sacrament doctrine"]
    if key == "hindu":
        return ["karma dharma moksha bhagavad gita", "upanishad atman brahman scripture"]
    if key == "tcm":
        return ["감초 本草 처방 변증", "本草 方劑 辨證 classical medicine"]
    return []


def _zero_source_bootstrap_rows(product: ProductProfile, *, language: str, limit: int) -> list[SearchResult]:
    target = max(1, int(limit or 1))
    seen: set[str] = set()
    rows: list[SearchResult] = []
    for query in _zero_source_bootstrap_queries(product):
        try:
            found = search_documents(product, query, limit=max(target - len(rows), 1), language=language)
        except Exception:
            found = []
        for row in found:
            if not row.canonical_id or row.canonical_id in seen:
                continue
            seen.add(row.canonical_id)
            rows.append(row)
            if len(rows) >= target:
                return rows
    return rows


def collect_candidate_rows(
    product: ProductProfile,
    query: str,
    *,
    language: str,
    limit: int,
    keywords: list[str],
    initial: list[SearchResult],
    cache_root: Path | None = None,
    cache_stats: dict[str, int] | None = None,
    fast_mode: bool = False,
) -> list[SearchResult]:
    seen: set[str] = set()
    rows: list[SearchResult] = []
    target_limit = max(limit, 1)
    scan_pool_limit = _beta6_scan_pool_limit(target_limit)
    per_keyword_limit = _beta6_per_keyword_limit(target_limit, fast_mode=fast_mode, product=product)

    def add(items: list[SearchResult]) -> None:
        for row in items:
            if not row.canonical_id or row.canonical_id in seen:
                continue
            seen.add(row.canonical_id)
            rows.append(row)

    def add_priority(items: list[SearchResult]) -> None:
        priority_rows: list[SearchResult] = []
        for row in items:
            if not row.canonical_id or row.canonical_id in seen:
                continue
            seen.add(row.canonical_id)
            priority_rows.append(row)
        if priority_rows:
            rows[:0] = priority_rows

    add(initial)
    keyword_terms = [keyword for keyword in keywords if keyword.strip()]
    search_plan = build_beta6_candidate_search_plan(
        product,
        query,
        keyword_terms,
        target_limit=target_limit,
        per_keyword_limit=per_keyword_limit,
    )
    adapter = get_domain_adapter(product)
    mcq_query = adapter.parse_multiple_choice(query) is not None
    force_context_scans = bool(mcq_query and adapter.prioritize_question_first_for_mcq(query))

    def finalize_candidates(items: list[SearchResult]) -> list[SearchResult]:
        if mcq_query:
            priority_rows, ordinary_rows = adapter.priority_context_candidate_rows(query, items)
            if priority_rows:
                items = [*priority_rows, *ordinary_rows]
        return diversify_beta6_candidates(product, items, limit=target_limit)

    def has_enough_fast_candidates() -> bool:
        if len(rows) < target_limit:
            return False
        if not mcq_query:
            return True
        coverage = _mcq_candidate_coverage_meta(product, query, rows)
        return not bool(coverage.get("lowCoverage"))

    def has_enough_scan_pool_candidates() -> bool:
        if len(rows) < scan_pool_limit or not _has_domain_bucket_floor(product, rows):
            return False
        if not mcq_query:
            return True
        coverage = _mcq_candidate_coverage_meta(product, query, rows)
        return not bool(coverage.get("lowCoverage"))

    broad_initial_is_full = bool(initial) and len(rows) >= scan_pool_limit and _has_domain_bucket_floor(product, rows)
    if broad_initial_is_full:
        buckets: list[tuple[str, list[SearchResult]]] = []
        for label, search_query, query_limit in search_plan:
            if label == "question":
                continue
            query_limit = _full_frontier_refine_query_limit(product, query_limit)
            try:
                found = _search_documents_for_beta6_candidate_scan(
                    product,
                    search_query,
                    limit=query_limit,
                    language=language,
                    cache_root=cache_root,
                    cache_stats=cache_stats,
                    label=label,
                    question=query,
                )
            except Exception:
                continue
            if found:
                buckets.append((label, found))
        if initial:
            buckets.append(("previous_frontier", list(initial)))
        interleaved = _interleave_beta6_candidate_buckets(buckets, limit=scan_pool_limit)
        return finalize_candidates(interleaved)

    for label, search_query, query_limit in search_plan:
        force_label_scan = (
            force_context_scans
            and (label.startswith("domain_bucket_") or label.startswith("mcq_option_"))
        ) or bool(mcq_query and adapter.force_candidate_scan_for_mcq(query, label, search_query))
        if fast_mode and has_enough_fast_candidates() and not force_label_scan:
            break
        if has_enough_scan_pool_candidates() and not force_label_scan:
            break
        try:
            found = _search_documents_for_beta6_candidate_scan(
                product,
                search_query,
                limit=query_limit,
                language=language,
                cache_root=cache_root,
                cache_stats=cache_stats,
                label=label,
                question=query,
            )
        except Exception:
            continue
        if found:
            if force_label_scan:
                priority_rows, ordinary_rows = adapter.priority_context_candidate_rows(query, found)
                add_priority(priority_rows)
                add(ordinary_rows)
            else:
                add(found)
    return finalize_candidates(rows)


def _full_frontier_refine_query_limit(product: ProductProfile, query_limit: int) -> int:
    requested = max(1, int(query_limit or 1))
    config = get_domain_adapter(product).full_frontier_refine_limit_config(requested=requested)
    return min(requested, _env_int_from_config(config))


def _interleave_beta6_candidate_buckets(
    buckets: list[tuple[str, list[SearchResult]]],
    *,
    limit: int,
) -> list[SearchResult]:
    if limit <= 0 or not buckets:
        return []
    seen: set[str] = set()
    rows: list[SearchResult] = []
    positions = [0 for _label, _items in buckets]
    while len(rows) < limit:
        progressed = False
        for bucket_index, (_label, items) in enumerate(buckets):
            while positions[bucket_index] < len(items):
                row = items[positions[bucket_index]]
                positions[bucket_index] += 1
                if not row.canonical_id or row.canonical_id in seen:
                    continue
                seen.add(row.canonical_id)
                rows.append(row)
                progressed = True
                break
            if len(rows) >= limit:
                break
        if not progressed:
            break
    return rows


def _search_documents_for_beta6_candidate_scan(
    product: ProductProfile,
    query: str,
    *,
    limit: int,
    language: str,
    cache_root: Path | None = None,
    cache_stats: dict[str, int] | None = None,
    label: str = "",
    question: str = "",
) -> list[SearchResult]:
    started = time.monotonic()
    cache_hit = False
    rows: list[SearchResult] = []
    error = ""
    candidate_multiplier = _beta6_candidate_scan_multiplier(product, question or query, label=label)
    context_query = ""
    if product.key == "catholic" and str(question or "").strip() and str(question or "") != str(query or ""):
        context_query = str(question or "")
    try:
        if _beta6_batch_cache_root(cache_root) is not None:
            payload = {
                "cacheVersion": "candidate-search-v1",
                "product": product.key,
                "db": _product_db_cache_identity(product),
                "query": query,
                "contextQuery": context_query,
                "limit": int(limit),
                "language": language,
                "candidateMultiplier": int(candidate_multiplier),
            }

            def produce() -> dict[str, Any]:
                return {
                    "rows": [
                        _search_result_cache_payload(row)
                        for row in _search_documents_for_beta6_candidate_scan_uncached(
                            product,
                            query,
                            limit=limit,
                            language=language,
                            candidate_multiplier=candidate_multiplier,
                            context_query=context_query,
                        )
                    ]
                }

            value, cache_hit = _read_or_fill_batch_cache("candidate_search", payload, produce, cache_root=cache_root)
            rows = _search_results_from_cache_value(value)
        else:
            rows = _search_documents_for_beta6_candidate_scan_uncached(
                product,
                query,
                limit=limit,
                language=language,
                candidate_multiplier=candidate_multiplier,
                context_query=context_query,
            )
        return rows
    except Exception as exc:
        error = str(exc)
        raise
    finally:
        if cache_stats is not None:
            key = "hits" if cache_hit else "misses"
            cache_stats[key] = int(cache_stats.get(key, 0) or 0) + 1
            _append_candidate_search_trace(
                cache_stats,
                label=label,
                query=query,
                limit=limit,
                result_count=len(rows),
                elapsed_sec=time.monotonic() - started,
                cache_hit=cache_hit,
                error=error,
            )


def _append_candidate_search_trace(
    cache_stats: dict[str, Any],
    *,
    label: str,
    query: str,
    limit: int,
    result_count: int,
    elapsed_sec: float,
    cache_hit: bool,
    error: str = "",
) -> None:
    trace = cache_stats.setdefault("trace", [])
    if not isinstance(trace, list) or len(trace) >= 80:
        return
    entry: dict[str, Any] = {
        "label": str(label or "search"),
        "query": str(query or ""),
        "limit": int(limit),
        "resultCount": int(result_count),
        "elapsedSec": round(max(0.0, float(elapsed_sec)), 3),
        "cacheHit": bool(cache_hit),
    }
    if error:
        entry["error"] = str(error)[:240]
    trace.append(entry)


def _candidate_search_trace(cache_stats: dict[str, Any]) -> list[dict[str, Any]]:
    trace = cache_stats.get("trace") if isinstance(cache_stats, dict) else []
    if not isinstance(trace, list):
        return []
    return [dict(item) for item in trace[:80] if isinstance(item, dict)]


def _mcq_candidate_coverage_meta(product: ProductProfile, query: str, candidates: list[SearchResult]) -> dict[str, Any]:
    adapter = get_domain_adapter(product)
    if adapter.parse_multiple_choice(query) is None:
        return {"enabled": False, "reason": "not_mcq"}
    if product.key == "tcm":
        return {"enabled": False, "reason": "tcm_mcq_uses_domain_structure"}
    if not _env_flag_default("RELIGION_MCQ_LOW_COVERAGE_GATE_ENABLED", True):
        return {"enabled": False, "reason": "disabled"}
    terms = _candidate_coverage_terms(adapter.search_text(query))
    min_terms = _env_int("RELIGION_MCQ_LOW_COVERAGE_MIN_TERMS", 4, minimum=1, maximum=50)
    if len(terms) < min_terms:
        return {
            "enabled": True,
            "lowCoverage": True,
            "reason": "too_few_query_terms",
            "matchedTermRatio": 0.0,
            "threshold": _env_float("RELIGION_MCQ_LOW_COVERAGE_RATIO", 0.25, minimum=0.0, maximum=1.0),
            "queryTermCount": len(terms),
            "matchedTermCount": 0,
            "matchedTerms": [],
            "unmatchedTerms": terms[:20],
            "candidateCountChecked": 0,
            "minimumQueryTerms": min_terms,
        }
    candidate_limit = _env_int("RELIGION_MCQ_LOW_COVERAGE_CANDIDATE_LIMIT", 20, minimum=1, maximum=200)
    candidate_chars = _env_int("RELIGION_MCQ_LOW_COVERAGE_CANDIDATE_CHARS", 1600, minimum=200, maximum=8000)
    haystack_parts: list[str] = []
    for row in candidates[:candidate_limit]:
        haystack_parts.append(
            " ".join(
                [
                    row.title,
                    row.citation,
                    row.case_name,
                    row.case_type,
                    row.source_kind,
                    row.full_text[:candidate_chars],
                ]
            )
        )
    haystack = _normalize_coverage_text("\n".join(haystack_parts))
    matched = [term for term in terms if term in haystack]
    matched_set = set(matched)
    ratio = len(matched) / len(terms) if terms else 0.0
    threshold = _env_float("RELIGION_MCQ_LOW_COVERAGE_RATIO", 0.25, minimum=0.0, maximum=1.0)
    return {
        "enabled": True,
        "lowCoverage": ratio < threshold,
        "matchedTermRatio": round(ratio, 4),
        "threshold": threshold,
        "queryTermCount": len(terms),
        "matchedTermCount": len(matched),
        "matchedTerms": matched[:20],
        "unmatchedTerms": [term for term in terms if term not in matched_set][:20],
        "candidateCountChecked": min(len(candidates), candidate_limit),
    }


_CANDIDATE_COVERAGE_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "be",
    "because",
    "best",
    "choose",
    "correct",
    "does",
    "for",
    "from",
    "how",
    "is",
    "of",
    "one",
    "option",
    "the",
    "to",
    "what",
    "which",
    "why",
    "with",
    "다음",
    "다음과",
    "같습니다",
    "일반",
    "적용되는",
    "원칙은",
    "무엇",
    "어떤",
    "이유",
    "이유는",
    "정답",
    "보기",
    "하나",
    "고르세요",
    "주로",
}


def _candidate_coverage_terms(text: str) -> list[str]:
    terms: list[str] = []
    normalized = _normalize_coverage_text(text)
    for token in re.findall(r"[\w\u0600-\u06ff]+", normalized, re.UNICODE):
        if token.isdigit():
            continue
        if len(token) < 3 and not re.search(r"[\uac00-\ud7a3\u0600-\u06ff]", token):
            continue
        if token in _CANDIDATE_COVERAGE_STOPWORDS:
            continue
        if token not in terms:
            terms.append(token)
    return terms[:50]


def _normalize_coverage_text(text: str) -> str:
    return unicodedata.normalize("NFKC", str(text or "")).casefold()


def _search_documents_for_beta6_candidate_scan_uncached(
    product: ProductProfile,
    query: str,
    *,
    limit: int,
    language: str,
    candidate_multiplier: int = 1,
    context_query: str = "",
) -> list[SearchResult]:
    try:
        return search_documents(
            product,
            query,
            limit=limit,
            language=language,
            max_results=limit,
            candidate_multiplier=candidate_multiplier,
            context_query=context_query,
        )
    except TypeError as exc:
        if "unexpected keyword" not in str(exc):
            raise
        return search_documents(product, query, limit=limit, language=language)


def _product_db_cache_identity(product: ProductProfile) -> dict[str, Any]:
    path = Path(product.db_path)
    identity: dict[str, Any] = {"path": str(path)}
    try:
        stat = path.stat()
    except OSError:
        return identity
    identity["size"] = stat.st_size
    identity["mtimeNs"] = stat.st_mtime_ns
    return identity


def _search_result_cache_payload(row: SearchResult) -> dict[str, Any]:
    return {
        "canonical_id": row.canonical_id,
        "title": row.title,
        "citation": row.citation,
        "authority_body": row.authority_body,
        "source_date": row.source_date,
        "case_name": row.case_name,
        "case_type": row.case_type,
        "full_text": row.full_text,
        "source_dataset": row.source_dataset,
        "source_path": row.source_path,
        "score": row.score,
        "language": row.language,
        "source_url": row.source_url,
        "tradition": row.tradition,
        "school": row.school,
        "source_kind": row.source_kind,
        "authority_level": row.authority_level,
        "authority_label": row.authority_label,
    }


def _search_results_from_cache_value(value: dict[str, Any]) -> list[SearchResult]:
    rows = value.get("rows")
    if not isinstance(rows, list):
        return []
    out: list[SearchResult] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        try:
            out.append(SearchResult(**item))
        except TypeError:
            continue
    return out


def _beta6_per_keyword_limit(
    target_limit: int,
    *,
    fast_mode: bool = False,
    product: ProductProfile | None = None,
) -> int:
    if fast_mode:
        fast_cap = _beta6_fast_top_k_cap(product)
        default = max(1, min(int(target_limit or fast_cap), fast_cap))
        product_env = _beta6_product_env_name(product, "FAST_PER_KEYWORD_LIMIT")
        if product_env and os.getenv(product_env, "").strip():
            return _env_int(product_env, default, minimum=1, maximum=fast_cap)
        return _env_int("RELIGION_BETA6_FAST_PER_KEYWORD_LIMIT", default, minimum=1, maximum=fast_cap)
    return _env_int(
        "RELIGION_BETA6_PER_KEYWORD_LIMIT",
        LAWKEY_BETA6_FTS_LIMIT,
        minimum=4,
        maximum=max(LAWKEY_BETA6_FTS_LIMIT, target_limit),
    )


def _beta6_scan_pool_limit(target_limit: int) -> int:
    default = max(target_limit, 1)
    return _env_int("RELIGION_BETA6_SCAN_POOL_LIMIT", default, minimum=target_limit, maximum=2000)


def _beta6_candidate_scan_multiplier(product: ProductProfile, query: str, *, label: str = "") -> int:
    config = get_domain_adapter(product).candidate_scan_multiplier_config(query, label=label)
    return _env_int_from_config(config)


def _beta6_frontier_target(product: ProductProfile, top_k: int, *, fast_mode: bool = False) -> int:
    return _env_int_from_config(get_domain_adapter(product).frontier_target_config(top_k=top_k, fast_mode=fast_mode))


def _beta6_frontier_stop_floor(product: ProductProfile, top_k: int, *, fast_mode: bool = False) -> int:
    return _env_int_from_config(get_domain_adapter(product).frontier_stop_floor_config(top_k=top_k, fast_mode=fast_mode))


def build_beta6_candidate_search_plan(
    product: ProductProfile,
    query: str,
    keywords: list[str],
    *,
    target_limit: int,
    per_keyword_limit: int,
) -> list[tuple[str, str, int]]:
    plan: list[tuple[str, str, int]] = []
    seen: set[str] = set()
    adapter = get_domain_adapter(product)
    is_generic_mcq = adapter.parse_multiple_choice(query) is not None and product.key != "tcm"
    domain_bucket_values = _domain_bucket_queries(product, query, keywords)
    question_first = bool(is_generic_mcq and adapter.prioritize_question_first_for_mcq(query))
    domain_buckets_first = bool(is_generic_mcq and not question_first and adapter.prioritize_domain_buckets_for_mcq(query))

    def add(label: str, value: str, limit: int) -> None:
        normalized = " ".join(str(value or "").split())
        if not normalized or normalized in seen:
            return
        seen.add(normalized)
        plan.append((label, normalized, _beta6_search_plan_query_limit(product, normalized, limit)))

    if question_first:
        add("question", adapter.search_text(query), per_keyword_limit)
        for index, bucket_query in enumerate(domain_bucket_values, start=1):
            add(f"domain_bucket_{index:02d}", bucket_query, per_keyword_limit)
        for index, option_query in enumerate(_mcq_option_context_search_queries(product, query), start=1):
            add(f"mcq_option_{index:02d}", option_query, per_keyword_limit)
        for index, keyword in enumerate(keywords, start=1):
            add(f"keyword_{index:02d}", _searchable_beta6_keyword(product, keyword, question=query), per_keyword_limit)
    elif is_generic_mcq:
        if domain_buckets_first:
            for index, bucket_query in enumerate(domain_bucket_values, start=1):
                add(f"domain_bucket_{index:02d}", bucket_query, per_keyword_limit)
        for index, keyword in enumerate(keywords, start=1):
            add(f"keyword_{index:02d}", _searchable_beta6_keyword(product, keyword, question=query), per_keyword_limit)
        for index, option_query in enumerate(_mcq_option_context_search_queries(product, query), start=1):
            add(f"mcq_option_{index:02d}", option_query, per_keyword_limit)
        add("question", adapter.search_text(query), per_keyword_limit)
    else:
        add("question", adapter.search_text(query), per_keyword_limit)
        for index, option_query in enumerate(_mcq_option_context_search_queries(product, query), start=1):
            add(f"mcq_option_{index:02d}", option_query, per_keyword_limit)
        for index, keyword in enumerate(keywords, start=1):
            add(f"keyword_{index:02d}", _searchable_beta6_keyword(product, keyword, question=query), per_keyword_limit)
    if not question_first and not domain_buckets_first:
        for index, bucket_query in enumerate(domain_bucket_values, start=1):
            add(f"domain_bucket_{index:02d}", bucket_query, per_keyword_limit)
    return plan


def _beta6_search_plan_query_limit(product: ProductProfile, query: str, limit: int) -> int:
    requested = max(1, int(limit or 1))
    adapter = get_domain_adapter(product)
    catholic_chapter_seed_query = bool(
        product.key == "catholic"
        and (
            re.fullmatch(r"[1-3]?[A-Z][A-Za-z0-9]{1,7}\s+\d{1,3}:1", str(query or ""))
            or (
                adapter.parse_multiple_choice(query) is not None
                and re.search(r"\d{1,3}\s*(?:장|편)", str(query or ""))
            )
        )
    )
    if catholic_chapter_seed_query:
        chapter_seed_limit = _env_int(
            "RELIGION_CATHOLIC_BETA6_CHAPTER_SEED_QUERY_LIMIT",
            180,
            minimum=requested,
            maximum=LAWKEY_BETA6_FTS_LIMIT,
        )
        requested = max(requested, chapter_seed_limit)
    config = adapter.search_plan_query_limit_config(
        requested=requested,
        max_query_limit=LAWKEY_BETA6_FTS_LIMIT,
    )
    return min(requested, _env_int_from_config(config))


def _searchable_beta6_keyword(product: ProductProfile, keyword: str, *, question: str = "") -> str:
    return get_domain_adapter(product).searchable_keyword(keyword, question=question)


def _mcq_option_context_search_queries(product: ProductProfile, query: str) -> list[str]:
    if not _env_flag_default("RELIGION_MCQ_OPTION_CONTEXT_SEARCH_ENABLED", True):
        return []
    if product.key == "tcm":
        return []
    adapter = get_domain_adapter(product)
    parsed = adapter.parse_multiple_choice(query)
    if parsed is None or not parsed.options:
        return []
    stem = _clean_mcq_context_query_text(parsed.stem)
    if not stem:
        return []
    stem_chars = _env_int("RELIGION_MCQ_OPTION_CONTEXT_STEM_CHARS", 220, minimum=40, maximum=800)
    stem = stem[:stem_chars].strip()
    option_limit = _env_int("RELIGION_MCQ_OPTION_CONTEXT_OPTION_LIMIT", 10, minimum=1, maximum=20)
    out: list[str] = []
    seen: set[str] = set()
    for option in parsed.options[:option_limit]:
        option_text = _clean_mcq_context_query_text(option.text)
        if not option_text:
            continue
        option_terms = [option_text]
        for alias in adapter.option_aliases(option.text):
            cleaned_alias = _clean_mcq_context_query_text(alias)
            if cleaned_alias and cleaned_alias not in option_terms:
                option_terms.append(cleaned_alias)
        query_text = f"{stem} {' '.join(option_terms[:6])}".strip()
        if query_text and query_text not in seen:
            seen.add(query_text)
            out.append(query_text)
    return out


def _clean_mcq_context_query_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = re.sub(r"[\"'`“”‘’]", " ", text)
    text = re.sub(r"[.,;:!?？。，、；：]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _domain_bucket_queries(product: ProductProfile, query: str, keywords: list[str]) -> list[str]:
    return get_domain_adapter(product).domain_bucket_queries(query, keywords)


def _has_domain_bucket_floor(product: ProductProfile, rows: list[SearchResult]) -> bool:
    required = get_domain_adapter(product).candidate_role_floor_required()
    roles = {_source_role(product, row) for row in rows}
    roles.discard("other")
    return len(roles) >= required


def diversify_beta6_candidates(product: ProductProfile, rows: list[SearchResult], *, limit: int) -> list[SearchResult]:
    if len(rows) <= 1:
        return rows[:limit]
    selected: list[SearchResult] = []
    seen: set[str] = set()
    role_counts: dict[str, int] = {}
    role_cap = max(4, min(18, limit // 4)) if limit >= 20 else max(2, limit)

    def add(row: SearchResult, *, cap: bool) -> None:
        if len(selected) >= limit:
            return
        if not row.canonical_id or row.canonical_id in seen:
            return
        role = _source_role(product, row)
        if cap and role != "other" and role_counts.get(role, 0) >= role_cap:
            return
        seen.add(row.canonical_id)
        role_counts[role] = role_counts.get(role, 0) + 1
        selected.append(row)

    for row in rows:
        add(row, cap=True)
    missing_roles = [role for role in _domain_role_order(product) if role_counts.get(role, 0) == 0]
    for role in missing_roles:
        for row in rows:
            if _source_role(product, row) == role:
                add(row, cap=False)
                break
    for row in rows:
        add(row, cap=False)
    return selected[:limit]


def rank_beta6_candidate_frontier(
    product: ProductProfile,
    query: str,
    candidates: list[SearchResult],
    *,
    keywords: list[str],
) -> tuple[list[SearchResult], dict[str, Any]]:
    if len(candidates) <= 1:
        return candidates, {
            "frontierScoredCount": len(candidates),
            "frontierReranker": "beta6_frontier_overlap_authority",
            "frontierTopDebug": [
                {"id": row.canonical_id, "score": 0.0, "role": _source_role(product, row), "matchedTerms": []}
                for row in candidates[:20]
            ],
        }
    terms = _beta6_frontier_terms(product, query, keywords)
    scored: list[tuple[float, int, SearchResult, list[str]]] = []
    for index, row in enumerate(candidates):
        score, matched = _beta6_frontier_score(product, row, terms)
        score -= index * 0.0001
        scored.append((score, index, row, matched))
    scored.sort(key=lambda item: (-item[0], item[1], item[2].canonical_id))
    ranked = [row for _score, _index, row, _matched in scored]
    return ranked, {
        "frontierScoredCount": len(candidates),
        "frontierReranker": "beta6_frontier_overlap_authority",
        "frontierTopDebug": [
            {
                "id": row.canonical_id,
                "score": round(score, 3),
                "role": _source_role(product, row),
                "matchedTerms": matched[:12],
            }
            for score, _index, row, matched in scored[:20]
        ],
    }


def _beta6_frontier_terms(product: ProductProfile, query: str, keywords: list[str]) -> list[str]:
    raw_terms: list[str] = []
    for index, value in enumerate([query, *keywords]):
        text = " ".join(str(value or "").strip().split()) if index == 0 else _searchable_beta6_keyword(product, str(value or ""))
        if not text:
            continue
        raw_terms.append(text)
        raw_terms.extend(re.findall(r"[\w\u0600-\u06ff\u4e00-\u9fff가-힣]{2,}", text, flags=re.UNICODE))
    stop = {
        "the",
        "and",
        "or",
        "in",
        "of",
        "for",
        "with",
        "about",
        "source",
        "evidence",
        "근거",
        "정리",
        "질문",
    }
    out: list[str] = []
    seen: set[str] = set()
    for term in raw_terms:
        normalized = " ".join(str(term or "").lower().split())
        if len(normalized) < 2 or normalized in stop or normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
        if len(out) >= 80:
            break
    return out


def _beta6_frontier_score(product: ProductProfile, row: SearchResult, terms: list[str]) -> tuple[float, list[str]]:
    haystack = " ".join(
        [
            row.title,
            row.citation,
            row.authority_body,
            row.case_name,
            row.case_type,
            row.source_dataset,
            row.source_path,
            row.tradition,
            row.school,
            row.source_kind,
            row.full_text,
        ]
    ).lower()
    score = 0.0
    matched: list[str] = []
    for term in terms:
        if term and term in haystack:
            matched.append(term)
            score += 8.0 if " " in term else 3.0
    role = _source_role(product, row)
    if role != "other":
        score += 1.5
    if row.authority_level:
        score += min(5.0, float(row.authority_level) / 25.0)
    if row.score:
        score += min(2.0, abs(float(row.score)) / 100.0)
    return score, matched


def _domain_role_order(product: ProductProfile) -> list[str]:
    return get_domain_adapter(product).role_order()


def _source_role(product: ProductProfile, row: SearchResult) -> str:
    return get_domain_adapter(product).source_role(row)


def local_fallback_select_rows(
    product: ProductProfile,
    candidates: list[SearchResult],
    *,
    limit: int,
    query: str = "",
) -> list[SearchResult]:
    adapter = get_domain_adapter(product)
    if adapter.parse_multiple_choice(query) is None:
        return candidates[:limit]
    ordered = sorted(candidates, key=_tcm_fallback_rank_key)
    selected: list[SearchResult] = []
    seen: set[str] = set()
    kind_counts: dict[str, int] = {}
    kind_cap = 3 if limit >= 6 else 2
    case_cap = 2 if limit >= 5 else 1

    def add(row: SearchResult, *, cap_case_records: bool) -> None:
        if len(selected) >= limit:
            return
        if not row.canonical_id or row.canonical_id in seen:
            return
        kind = row.source_kind or row.case_type or ""
        if cap_case_records and kind_counts.get(kind, 0) >= kind_cap:
            return
        if cap_case_records and kind == "case_record" and kind_counts.get(kind, 0) >= case_cap:
            return
        seen.add(row.canonical_id)
        kind_counts[kind] = kind_counts.get(kind, 0) + 1
        selected.append(row)

    for row in _domain_option_matrix_rows(product, query, ordered, limit=limit):
        add(row, cap_case_records=False)
    for row in ordered:
        add(row, cap_case_records=True)
    if len(selected) < limit:
        for row in ordered:
            add(row, cap_case_records=False)
    return selected


def _domain_option_matrix_rows(
    product: ProductProfile,
    query: str,
    candidates: list[SearchResult],
    *,
    limit: int,
) -> list[SearchResult]:
    if not _mcq_heuristics_enabled():
        return []
    adapter = get_domain_adapter(product)
    parsed = adapter.parse_multiple_choice(query)
    if not parsed or limit <= 0:
        return []
    selected: list[SearchResult] = []
    seen: set[str] = set()
    for option in parsed.options:
        terms = adapter.option_aliases(option.text)
        row = next(
            (
                candidate
                for candidate in candidates
                if candidate.canonical_id not in seen and _tcm_row_has_any_term(candidate, terms)
            ),
            None,
        )
        if row is None:
            continue
        seen.add(row.canonical_id)
        selected.append(row)
        if len(selected) >= limit:
            break
    return selected


def _tcm_row_has_any_term(row: SearchResult, terms: Iterable[str]) -> bool:
    haystack = _tcm_compact_text(
        "\n".join(
            [
                str(row.title or ""),
                str(row.citation or ""),
                str(row.case_name or ""),
                str(row.case_type or ""),
                str(row.source_kind or ""),
                str(row.full_text or ""),
            ]
        )
    )
    for term in terms:
        needle = _tcm_compact_text(term)
        if needle and needle in haystack:
            return True
    return False


def _tcm_compact_text(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "")).lower()


def _tcm_fallback_rank_key(row: SearchResult) -> tuple[int, int, float, str]:
    kind = row.source_kind or row.case_type or ""
    source_priority = {
        "classic_canon": 0,
        "materia_medica": 1,
        "formulary": 2,
        "clinical_guideline": 3,
        "classic_authoritative": 4,
        "commentary_on_classic": 5,
        "modern_reference": 6,
        "case_record": 8,
    }.get(kind, 7)
    authority = int(row.authority_level or 0)
    case_penalty = 1 if kind == "case_record" else 0
    return (source_priority, case_penalty, -authority, row.canonical_id)


def build_beta6_keyword_messages(
    product: ProductProfile,
    query: str,
    language: str,
    *,
    keyword_count: int,
) -> list[dict[str, str]]:
    adapter = get_domain_adapter(product)
    task, examples = adapter.keyword_generation_spec()
    retrieval_query = adapter.search_text(query)
    user = (
        f"{task}\n"
        f"Return JSON only with exactly {keyword_count} short strings.\n"
        f'Schema: {{"keywords":["..."]}}\n'
        f"{examples}\n\n"
        f"Answer language hint: {language}\n"
        f"Retrieval question:\n{retrieval_query}"
    )
    return [
        {"role": "system", "content": f"Gemma 4 beta-6 search keyword generator for {product.name}. JSON only."},
        {"role": "user", "content": user},
    ]


def build_beta6_additional_keyword_messages(
    product: ProductProfile,
    query: str,
    language: str,
    *,
    existing_keywords: list[str],
    candidate_count: int,
    target_count: int,
    keyword_count: int,
) -> list[dict[str, str]]:
    existing = ", ".join(existing_keywords[-30:]) or "(none)"
    adapter = get_domain_adapter(product)
    domain_hint = adapter.additional_keyword_hint()
    retrieval_query = adapter.search_text(query)
    user = (
        "Additional retrieval keyword round for beta-6.\n"
        f"The previous rounds found {candidate_count} candidate sources, but the target is {target_count}.\n"
        f"Existing keywords to avoid repeating: {existing}\n"
        f"{domain_hint}\n"
        f"Return JSON only with exactly {keyword_count} new short strings.\n"
        f'Schema: {{"keywords":["..."]}}\n\n'
        f"Answer language hint: {language}\n"
        f"Retrieval question:\n{retrieval_query}"
    )
    return [
        {"role": "system", "content": f"Gemma 4 beta-6 search keyword generator for {product.name}. JSON only."},
        {"role": "user", "content": user},
    ]


def build_beta6_selection_messages(
    product: ProductProfile,
    query: str,
    language: str,
    candidates: list[SearchResult],
    *,
    limit: int,
) -> list[dict[str, str]]:
    policy = _selector_domain_policy(product.key)
    max_selector_candidates = _selector_candidate_limit(product)
    excerpt_chars = _selector_excerpt_chars(product)
    candidate_slice = candidates[:max_selector_candidates]
    input_heading = "Candidates:"
    role_diversity_rule = _selector_role_diversity_rule(product) if _selector_role_diversity_hint_enabled() else ""
    mcq_block = _tcm_mcq_block_for_prompt(product, query)
    if _selector_evidence_capsules_enabled():
        input_heading = "Evidence capsules:"
        blocks = [_format_selector_evidence_capsule(capsule) for capsule in build_beta6_evidence_capsules(product, query, candidate_slice, excerpt_chars=excerpt_chars)]
    else:
        blocks = []
        for index, row in enumerate(candidate_slice, start=1):
            metadata = []
            if row.tradition:
                metadata.append(f"tradition={row.tradition}")
            if row.school:
                metadata.append(f"school={row.school}")
            if row.source_kind:
                metadata.append(f"source_kind={row.source_kind}")
            if row.authority_level:
                metadata.append(f"authority_level={row.authority_level}")
            excerpt = _selector_excerpt_for_prompt(product, row, excerpt_chars=excerpt_chars)
            if _selector_compact_candidate_lines_enabled(product):
                blocks.append(_format_selector_compact_candidate_line(index, row, excerpt, metadata))
            else:
                blocks.append(
                    f"[S{index}] file_id: {row.canonical_id}\n"
                    f"title: {row.title or row.citation}\n"
                    f"citation: {row.citation}\n"
                    f"authority: {row.authority_body} {'; '.join(metadata)}\n"
                    f"excerpt: {excerpt}"
                )
    user = (
        "Select source records for a beta-6 grounded answer.\n"
        f"Rules:\n{policy}\n"
        f"- Select at most {limit} file_id values from the candidate list.\n"
        "- Select only sources whose excerpt directly helps answer, compare positions, or mark a safety/retrieval gap.\n"
        "- Include contrary/variant-school evidence when available.\n"
        f"{role_diversity_rule}"
        "- Do not invent source ids. If nothing is relevant, put <none/>.\n"
        + (
            "- Before <selection>, emit one compact JSONL ledger row for each selected source with keys: "
            'file_id, context_summary, claim_summary, quote_candidate, source_role, stance.\n'
            "- JSONL ledger rows must summarize only the candidate excerpt and must not invent quotes.\n"
            if _selector_evidence_ledger_enabled()
            else ""
        )
        + "- Explain briefly first, then end with a separate <selection> block containing file_id values, one per line.\n\n"
        f"Answer language hint: {language}\n"
        f"User question:\n{query}\n\n"
        + (mcq_block + "\n\n" if mcq_block else "")
        + f"{input_heading}\n"
        + "\n\n".join(blocks or ["(no candidates)"])
    )
    return [
        {"role": "system", "content": f"Gemma 4 beta-6 source selector for {product.name}. Return the required selection block."},
        {"role": "user", "content": user},
    ]


def _selector_evidence_capsules_enabled() -> bool:
    return _env_flag("RELIGION_SELECTOR_EVIDENCE_CAPSULES")


def _selector_clean_raw_excerpt_enabled() -> bool:
    return _env_flag("RELIGION_SELECTOR_CLEAN_RAW_EXCERPTS")


def _selector_role_diversity_hint_enabled() -> bool:
    return _env_flag("RELIGION_SELECTOR_ROLE_DIVERSITY_HINT")


def _selector_compact_candidate_lines_enabled(product: ProductProfile | None = None) -> bool:
    return _env_flag_from_config(get_domain_adapter(product).selector_compact_candidate_lines_config())


def _selector_evidence_ledger_enabled() -> bool:
    return _env_flag("RELIGION_SELECTOR_EVIDENCE_LEDGER")


def _selector_input_mode(product: ProductProfile | None = None) -> str:
    if _selector_evidence_capsules_enabled():
        base = "context_packets_v1"
    elif _selector_clean_raw_excerpt_enabled():
        base = "clean_raw_excerpt_v1"
    else:
        base = "raw_excerpt_v1"
    if _selector_role_diversity_hint_enabled():
        base = f"{base}+role_diversity_v1"
    if not _selector_evidence_capsules_enabled() and _selector_compact_candidate_lines_enabled(product):
        base = f"{base}+compact_lines_v1"
    if _selector_evidence_ledger_enabled():
        base = f"{base}+evidence_ledger_v1"
    return base


def _selector_role_diversity_rule(product: ProductProfile) -> str:
    return get_domain_adapter(product).selector_role_diversity_rule()


def _clean_selector_excerpt(text: str, *, excerpt_chars: int) -> str:
    metadata_keys = {
        "religion",
        "tradition",
        "school",
        "authority_level",
        "source_kind",
        "authority_label",
        "source_dataset",
        "source_path",
    }
    useful_lines: list[str] = []
    for line in str(text or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            continue
        key = stripped.split(":", 1)[0].strip().lower()
        if key in metadata_keys:
            continue
        useful_lines.append(stripped)
    excerpt = " ".join(" ".join(useful_lines or [str(text or "")]).split())
    if excerpt_chars <= 0:
        return excerpt
    return excerpt[:excerpt_chars]


def _truncate_utf8_bytes(text: str, max_bytes: int) -> str:
    value = str(text or "")
    if max_bytes <= 0:
        return value
    encoded = value.encode("utf-8")
    if len(encoded) <= max_bytes:
        return value
    return encoded[:max_bytes].decode("utf-8", errors="ignore").rstrip()


def _selector_compact_value(text: str, max_bytes: int) -> str:
    return _truncate_utf8_bytes(" ".join(str(text or "").split()), max_bytes)


def _selector_excerpt_for_prompt(product: ProductProfile, row: SearchResult, *, excerpt_chars: int) -> str:
    if _selector_clean_raw_excerpt_enabled():
        excerpt = _clean_selector_excerpt(row.full_text, excerpt_chars=excerpt_chars)
    else:
        excerpt = " ".join(row.full_text.split())[:excerpt_chars]
    return _truncate_utf8_bytes(excerpt, _selector_excerpt_bytes(product))


def _format_selector_compact_candidate_line(
    index: int,
    row: SearchResult,
    excerpt: str,
    metadata: list[str],
) -> str:
    citation = _selector_compact_value(row.citation or row.title or row.canonical_id, 96)
    roles = []
    if row.source_kind:
        roles.append(f"kind={row.source_kind}")
    if row.school:
        roles.append(f"school={row.school}")
    if row.tradition:
        roles.append(f"trad={row.tradition}")
    if row.authority_level:
        roles.append(f"level={row.authority_level}")
    role_text = ",".join(roles)
    parts = [
        f"[S{index}] file_id: {row.canonical_id}",
        f"cite: {citation}",
    ]
    if role_text:
        parts.append(f"role: {role_text}")
    parts.append(f"excerpt: {excerpt}")
    return " | ".join(parts)


def build_beta6_evidence_capsules(
    product: ProductProfile,
    query: str,
    candidates: list[SearchResult],
    *,
    excerpt_chars: int,
) -> list[dict[str, Any]]:
    capsules: list[dict[str, Any]] = []
    for index, row in enumerate(candidates, start=1):
        label = f"S{index}"
        role_hints: list[str] = []
        for hint in (
            _source_role(product, row),
            row.source_kind,
            row.school,
            row.tradition,
            row.authority_label,
        ):
            value = str(hint or "").strip()
            if value and value not in role_hints and value != "other":
                role_hints.append(value)
        exact_quote, span_start, span_end = _context_packet_quote(product, row, excerpt_chars=excerpt_chars)
        source_role = role_hints[0] if role_hints else "other"
        domain_axes = _context_packet_domain_axes(row)
        capsules.append(
            {
                "label": label,
                "packetId": f"{label}:{row.canonical_id}",
                "fileId": row.canonical_id,
                "sourceId": row.canonical_id,
                "title": row.title or row.citation,
                "citation": row.citation,
                "authority": row.authority_body,
                "sourceKind": row.source_kind,
                "school": row.school,
                "tradition": row.tradition,
                "authorityLevel": row.authority_level,
                "authorityLabel": row.authority_label,
                "roleHints": role_hints,
                "sourceRole": source_role,
                "domainAxes": domain_axes,
                "relation": "candidate_evidence",
                "activationReason": _context_packet_activation_reason(role_hints, domain_axes),
                "entities": [],
                "spanStart": span_start,
                "spanEnd": span_end,
                "exactQuote": exact_quote,
                "contextBeforeAfter": "selector_excerpt_window",
                "excerpt": exact_quote,
            }
        )
    return capsules


def _selector_context_packets_for_batches(
    product: ProductProfile,
    query: str,
    candidate_slice: list[SearchResult],
    *,
    batch_size: int,
) -> list[dict[str, Any]]:
    if not _selector_evidence_capsules_enabled():
        return []
    packets: list[dict[str, Any]] = []
    size = max(1, int(batch_size or len(candidate_slice) or 1))
    for batch_index, offset in enumerate(range(0, len(candidate_slice), size), start=1):
        batch = candidate_slice[offset : offset + size]
        for local_index, packet in enumerate(
            build_beta6_evidence_capsules(product, query, batch, excerpt_chars=_selector_excerpt_chars(product)),
            start=1,
        ):
            item = dict(packet)
            item["selectorBatch"] = batch_index
            item["selectorBatchStart"] = offset
            item["selectorBatchEnd"] = offset + len(batch)
            item["selectorCandidateOrdinal"] = offset + local_index
            item["selectorLabel"] = str(packet.get("label") or "")
            packets.append(item)
    return packets


def _selector_context_packets_from_meta(selector: dict[str, Any]) -> list[dict[str, Any]]:
    packets = selector.get("selectorContextPackets") if isinstance(selector, dict) else []
    if not isinstance(packets, list):
        return []
    return [dict(packet) for packet in packets if isinstance(packet, dict)]


def _context_packet_quote(product: ProductProfile, row: SearchResult, *, excerpt_chars: int) -> tuple[str, int, int]:
    cleaned = _truncate_utf8_bytes(
        _clean_selector_excerpt(row.full_text, excerpt_chars=excerpt_chars),
        _selector_excerpt_bytes(product),
    )
    raw = str(row.full_text or "")
    span_start = raw.find(cleaned) if cleaned else -1
    if span_start < 0 and cleaned:
        first_sentence = cleaned.split(". ", 1)[0].strip()
        span_start = raw.find(first_sentence) if first_sentence else -1
    span_end = span_start + len(cleaned) if span_start >= 0 else -1
    return cleaned, span_start, span_end


def _context_packet_domain_axes(row: SearchResult) -> list[str]:
    axes: list[str] = []
    for key, value in (
        ("source_kind", row.source_kind),
        ("school", row.school),
        ("tradition", row.tradition),
        ("authority_label", row.authority_label),
        ("authority_level", row.authority_level),
    ):
        text = str(value or "").strip()
        if text:
            axes.append(f"{key}:{text}")
    return axes


def _context_packet_activation_reason(role_hints: list[str], domain_axes: list[str]) -> str:
    details = role_hints or domain_axes
    if not details:
        return "candidate kept by upstream retrieval"
    return "candidate kept by upstream retrieval; " + ", ".join(details[:6])


def _format_selector_evidence_capsule(capsule: dict[str, Any]) -> str:
    metadata = []
    if capsule.get("tradition"):
        metadata.append(f"tradition={capsule['tradition']}")
    if capsule.get("school"):
        metadata.append(f"school={capsule['school']}")
    if capsule.get("sourceKind"):
        metadata.append(f"source_kind={capsule['sourceKind']}")
    if capsule.get("authorityLevel"):
        metadata.append(f"authority_level={capsule['authorityLevel']}")
    role_hints = ", ".join(str(item) for item in capsule.get("roleHints") or [])
    domain_axes = ", ".join(str(item) for item in capsule.get("domainAxes") or [])
    return (
        f"[{capsule.get('label')}] file_id: {capsule.get('fileId')}\n"
        f"packet_id: {capsule.get('packetId') or ''}\n"
        f"title: {capsule.get('title') or capsule.get('citation')}\n"
        f"citation: {capsule.get('citation') or ''}\n"
        f"authority: {capsule.get('authority') or ''} {'; '.join(metadata)}\n"
        f"source_role: {capsule.get('sourceRole') or ''}\n"
        f"domain_axes: {domain_axes}\n"
        f"activation_reason: {capsule.get('activationReason') or ''}\n"
        f"role_hints: {role_hints}\n"
        f"exact_quote: {capsule.get('exactQuote') or ''}\n"
        f"excerpt: {capsule.get('excerpt') or ''}"
    )


def _selector_candidate_universe_meta(candidates: list[SearchResult]) -> dict[str, Any]:
    candidate_ids = [str(row.canonical_id or "") for row in candidates if str(row.canonical_id or "")]
    encoded = json.dumps(candidate_ids, ensure_ascii=False, separators=(",", ":"))
    return {
        "candidateIds": candidate_ids,
        "candidateSetDigest": f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}",
    }


def select_rows_with_beta6_selector(
    product: ProductProfile,
    query: str,
    language: str,
    candidates: list[SearchResult],
    *,
    limit: int,
    llm_client: LLMClient,
    model: str,
    progress_callback: Callable[..., None] | None = None,
    cache_root: Path | None = None,
) -> tuple[list[SearchResult], list[str], str, dict[str, Any]]:
    candidate_limit = _selector_candidate_limit(product, candidate_count=len(candidates))
    candidate_slice = candidates[:candidate_limit]
    candidate_universe_meta = _selector_candidate_universe_meta(candidate_slice)
    batch_size = _selector_batch_size(product)
    selector_context_packets = _selector_context_packets_for_batches(
        product,
        query,
        candidate_slice,
        batch_size=batch_size,
    )

    def run_batch(batch_index: int, offset: int) -> dict[str, Any]:
        started_at = time.monotonic()
        batch = candidate_slice[offset : offset + batch_size]
        selector_timeout = _selector_timeout_seconds(product)
        primary_timeout = _selector_primary_timeout_seconds(product)
        llm_call_traces: list[dict[str, Any]] = []
        llm_call_trace_lock = threading.Lock()
        payload = _selector_batch_cache_payload(
            product,
            query,
            language,
            model,
            limit=min(limit, len(batch)),
            batch=batch,
        )

        def complete_selection_once(target_batch: list[SearchResult], *, phase: str = "primary") -> tuple[list[str], str, list[dict[str, str]]]:
            call_timeout = primary_timeout if phase == "primary" else selector_timeout
            messages = build_beta6_selection_messages(
                product,
                query,
                language,
                target_batch,
                limit=min(limit, len(target_batch)),
            )
            prompt_metrics = _prompt_size_metrics(messages)
            try:
                raw = _complete_llm(
                    llm_client,
                    messages,
                    model=model,
                    timeout_seconds=call_timeout,
                )
            finally:
                trace = _consume_llm_call_trace(llm_client) or {}
                trace["selectorPhase"] = phase
                trace["candidateCount"] = len(target_batch)
                trace.update(prompt_metrics)
                with llm_call_trace_lock:
                    llm_call_traces.append(trace)
            if _selector_evidence_ledger_enabled():
                return parse_selection_response_with_ledger(raw)
            batch_ids, batch_reasoning = parse_selection_response(raw)
            return batch_ids, batch_reasoning, []

        def retry_after_rate_limit(
            target_batch: list[SearchResult],
            original_error: Exception,
            *,
            phase: str = "primary",
        ) -> tuple[list[str], str, list[dict[str, str]], dict[str, Any]]:
            retries = _selector_rate_limit_retries(product)
            last_error: Exception = original_error
            for attempt in range(1, retries + 1):
                backoff = _selector_rate_limit_backoff_seconds(attempt, product)
                if backoff > 0:
                    time.sleep(backoff)
                try:
                    batch_ids, batch_reasoning, batch_ledger = complete_selection_once(target_batch, phase=phase)
                    return (
                        batch_ids,
                        batch_reasoning,
                        batch_ledger,
                        {
                            "rateLimitRetried": True,
                            "rateLimitRetryCount": attempt,
                            "rateLimitError": str(original_error),
                        },
                    )
                except Exception as retry_exc:
                    last_error = retry_exc
                    if not _selector_error_is_rate_limit(retry_exc):
                        raise retry_exc
            raise last_error

        def recover_with_smaller_batches(original_error: Exception) -> dict[str, Any]:
            recovery_size = _selector_recovery_batch_size(product, len(batch))
            if len(batch) <= recovery_size:
                raise original_error
            sub_batches = [
                (sub_index, batch[sub_offset : sub_offset + recovery_size])
                for sub_index, sub_offset in enumerate(range(0, len(batch), recovery_size), start=1)
                if batch[sub_offset : sub_offset + recovery_size]
            ]

            def run_recovery_sub_batch(sub_index: int, sub_batch: list[SearchResult]) -> dict[str, Any]:
                sub_ids: list[str] = []
                sub_reasoning = ""
                sub_ledger: list[dict[str, str]] = []
                sub_errors: list[str] = []
                sub_rate_limit_retry_count = 0
                sub_rate_limit_errors: list[str] = []
                try:
                    sub_ids, sub_reasoning, sub_ledger = complete_selection_once(sub_batch, phase="recovery")
                except Exception as sub_exc:
                    if not _selector_error_is_rate_limit(sub_exc):
                        sub_errors.append(str(sub_exc))
                    else:
                        try:
                            sub_ids, sub_reasoning, sub_ledger, retry_meta = retry_after_rate_limit(sub_batch, sub_exc, phase="recovery")
                        except Exception as sub_retry_exc:
                            sub_errors.append(str(sub_retry_exc))
                        else:
                            sub_rate_limit_retry_count += int(retry_meta.get("rateLimitRetryCount") or 0)
                            if retry_meta.get("rateLimitError"):
                                sub_rate_limit_errors.append(str(retry_meta["rateLimitError"]))
                selected_ids: list[str] = []
                for row in resolve_selected_rows(sub_batch, sub_ids, limit=len(sub_batch)):
                    if row.canonical_id:
                        selected_ids.append(row.canonical_id)
                return {
                    "index": sub_index,
                    "selectedIds": selected_ids,
                    "reasoning": sub_reasoning,
                    "ledger": sub_ledger,
                    "errors": sub_errors,
                    "rateLimitRetryCount": sub_rate_limit_retry_count,
                    "rateLimitErrors": sub_rate_limit_errors,
                }

            sub_results: list[dict[str, Any]] = []
            recovery_workers = _selector_recovery_batch_workers(product, len(sub_batches))
            if recovery_workers <= 1 or len(sub_batches) <= 1:
                sub_results = [run_recovery_sub_batch(sub_index, sub_batch) for sub_index, sub_batch in sub_batches]
            else:
                with ThreadPoolExecutor(max_workers=recovery_workers, thread_name_prefix="beta6-selector-recovery") as executor:
                    future_map = {
                        executor.submit(run_recovery_sub_batch, sub_index, sub_batch): sub_index
                        for sub_index, sub_batch in sub_batches
                    }
                    for future in as_completed(future_map):
                        sub_results.append(future.result())
                sub_results.sort(key=lambda item: int(item.get("index") or 0))

            recovered_ids: list[str] = []
            seen_recovered: set[str] = set()
            recovered_ledger: list[dict[str, str]] = []
            seen_ledger: set[str] = set()
            recovery_reasoning: list[str] = []
            recovery_errors: list[str] = []
            recovery_rate_limit_retry_count = 0
            recovery_rate_limit_errors: list[str] = []
            for item in sub_results:
                recovery_errors.extend(str(error) for error in item.get("errors") or [])
                recovery_rate_limit_retry_count += int(item.get("rateLimitRetryCount") or 0)
                recovery_rate_limit_errors.extend(str(error) for error in item.get("rateLimitErrors") or [])
                for selected_id in item.get("selectedIds") or []:
                    if selected_id and selected_id not in seen_recovered:
                        seen_recovered.add(selected_id)
                        recovered_ids.append(selected_id)
                for ledger_item in item.get("ledger") or []:
                    file_id = str(ledger_item.get("fileId") or "").strip()
                    if file_id and file_id not in seen_ledger:
                        seen_ledger.add(file_id)
                        recovered_ledger.append(ledger_item)
                if item.get("reasoning"):
                    recovery_reasoning.append(f"recovery {int(item.get('index') or 0)}: {item['reasoning']}")
            recovery_meta = {
                "recoveryError": str(original_error),
                "recoveryErrors": recovery_errors,
                "recoverySubBatchCount": len(sub_batches),
                "recoveryBatchSize": recovery_size,
                "recoveryBatchWorkers": recovery_workers,
                "rateLimitRetryCount": recovery_rate_limit_retry_count,
                "rateLimitError": "; ".join(recovery_rate_limit_errors[:3]),
            }
            if not recovered_ids and recovery_errors:
                error = RuntimeError(str(original_error))
                setattr(error, "selector_recovery_meta", recovery_meta)
                raise error
            return {
                "rawSelectedIds": recovered_ids,
                "reasoning": "\n".join(recovery_reasoning).strip(),
                "ledger": recovered_ledger,
                "recovered": True,
                **recovery_meta,
                "localRecovery": False,
            }

        def recover_locally(original_error: Exception, recovery_meta: dict[str, Any] | None = None) -> dict[str, Any]:
            recovery_meta = recovery_meta or {}
            local_rows = local_fallback_select_rows(product, batch, limit=min(limit, len(batch)), query=query)
            local_ids = [row.canonical_id for row in local_rows if row.canonical_id]
            return {
                "rawSelectedIds": local_ids,
                "reasoning": "selector timeout; used deterministic beta6 local recovery for this exact candidate batch",
                "ledger": [],
                "recovered": True,
                "recoveryError": str(recovery_meta.get("recoveryError") or original_error),
                "recoveryErrors": [str(item) for item in recovery_meta.get("recoveryErrors") or []],
                "recoverySubBatchCount": int(recovery_meta.get("recoverySubBatchCount") or 0),
                "recoveryBatchSize": int(recovery_meta.get("recoveryBatchSize") or 0),
                "recoveryBatchWorkers": int(recovery_meta.get("recoveryBatchWorkers") or 0),
                "localRecovery": True,
                "rateLimitRetryCount": int(recovery_meta.get("rateLimitRetryCount") or 0),
                "rateLimitError": str(recovery_meta.get("rateLimitError") or ""),
            }

        def produce() -> dict[str, Any]:
            try:
                batch_ids, batch_reasoning, batch_ledger = complete_selection_once(batch)
                return {"rawSelectedIds": batch_ids, "reasoning": batch_reasoning, "ledger": batch_ledger}
            except Exception as exc:
                if _selector_error_is_rate_limit(exc):
                    try:
                        batch_ids, batch_reasoning, batch_ledger, retry_meta = retry_after_rate_limit(batch, exc)
                        return {
                            "rawSelectedIds": batch_ids,
                            "reasoning": batch_reasoning,
                            "ledger": batch_ledger,
                            **retry_meta,
                        }
                    except Exception as retry_exc:
                        exc = retry_exc
                if _selector_error_is_timeout(exc):
                    try:
                        return recover_with_smaller_batches(exc)
                    except Exception as recovery_exc:
                        recovery_meta = getattr(recovery_exc, "selector_recovery_meta", None)
                        return recover_locally(exc, recovery_meta if isinstance(recovery_meta, dict) else None)
                return recover_with_smaller_batches(exc)

        cached_or_value, cache_hit = _read_or_fill_batch_cache("selector", payload, produce, cache_root=cache_root)
        batch_ids = [str(item) for item in cached_or_value.get("rawSelectedIds") or []]
        batch_reasoning = str(cached_or_value.get("reasoning") or "")
        batch_ledger = _normalize_selector_ledger(cached_or_value.get("ledger") or [])
        batch_rows = resolve_selected_rows(batch, batch_ids, limit=len(batch))
        empty_selection_local_fallback = False
        adapter = get_domain_adapter(product)
        allow_empty_mcq_fallback = bool(
            _mcq_heuristics_enabled() or adapter.prioritize_question_first_for_mcq(query)
        )
        if (
            not batch_rows
            and allow_empty_mcq_fallback
            and adapter.parse_multiple_choice(query) is not None
        ):
            local_rows = local_fallback_select_rows(product, batch, limit=min(limit, len(batch)), query=query)
            if local_rows:
                batch_rows = local_rows
                batch_ids = [row.canonical_id for row in batch_rows if row.canonical_id]
                fallback_reason = (
                    "empty selector result; used deterministic TCM option-matrix local recovery"
                    if product.key == "tcm"
                    else "empty selector result; used deterministic MCQ context local recovery"
                )
                batch_reasoning = f"{batch_reasoning}\n{fallback_reason}".strip()
                empty_selection_local_fallback = True
        elapsed_sec = round(max(0.0, time.monotonic() - started_at), 3)
        llm_trace_summary = _selector_llm_call_trace_summary(llm_call_traces)
        return {
            "batch": batch_index,
            "start": offset,
            "end": offset + len(batch),
            "candidateCount": len(batch),
            "elapsedSec": elapsed_sec,
            "timeoutSeconds": float(selector_timeout),
            "primaryTimeoutSeconds": float(primary_timeout),
            "recoveryTimeoutSeconds": float(selector_timeout),
            "elapsedExceededTimeout": elapsed_sec > float(selector_timeout),
            **llm_trace_summary,
            "rawSelectedIds": batch_ids,
            "rows": batch_rows,
            "reasoning": batch_reasoning,
            "ledger": batch_ledger,
            "ledgerCount": len(batch_ledger),
            "cacheHit": cache_hit,
            "recovered": bool(cached_or_value.get("recovered")),
            "recoveryError": str(cached_or_value.get("recoveryError") or ""),
            "recoveryErrors": [str(item) for item in cached_or_value.get("recoveryErrors") or []],
            "recoverySubBatchCount": int(cached_or_value.get("recoverySubBatchCount") or 0),
            "recoveryBatchSize": int(cached_or_value.get("recoveryBatchSize") or 0),
            "recoveryBatchWorkers": int(cached_or_value.get("recoveryBatchWorkers") or 0),
            "localRecovery": bool(cached_or_value.get("localRecovery")) or empty_selection_local_fallback,
            "emptySelectionLocalFallback": empty_selection_local_fallback,
            "rateLimitRetryCount": int(cached_or_value.get("rateLimitRetryCount") or 0),
            "rateLimitError": str(cached_or_value.get("rateLimitError") or ""),
        }

    if len(candidate_slice) <= batch_size:
        _emit_progress(
            progress_callback,
            "source_selection",
            _localized_batch_detail("source_selection", language, 1, 1),
            {
                "detail": _localized_batch_detail("source_selection", language, 1, 1),
                "batch": {"index": 1, "count": 1, "start": 0, "end": len(candidate_slice)},
            },
        )
        result = run_batch(1, 0)
        selected_ids = list(result["rawSelectedIds"])
        reasoning = str(result.get("reasoning") or "")
        batch_status = "completed" if selected_ids else "empty_selection"
        selector_ledger = list(result.get("ledger") or []) if _selector_evidence_ledger_enabled() else []
        batch_trace = _selector_batch_trace(
            [
                {
                    "batch": 1,
                    "start": result["start"],
                    "end": result["end"],
                    "candidateCount": result["candidateCount"],
                    "status": batch_status,
                    "rawSelectedIds": selected_ids,
                    "selectedIds": [row.canonical_id for row in resolve_selected_rows(candidate_slice, selected_ids, limit=limit)],
                    "ledgerCount": len(selector_ledger),
                    "cacheHit": bool(result.get("cacheHit")),
                    "elapsedSec": float(result.get("elapsedSec") or 0.0),
                    "timeoutSeconds": float(result.get("timeoutSeconds") or 0.0),
                    "primaryTimeoutSeconds": float(result.get("primaryTimeoutSeconds") or 0.0),
                    "recoveryTimeoutSeconds": float(result.get("recoveryTimeoutSeconds") or 0.0),
                    "elapsedExceededTimeout": bool(result.get("elapsedExceededTimeout")),
                    "llmCallCount": int(result.get("llmCallCount") or 0),
                    "llmHttpStartedCount": int(result.get("llmHttpStartedCount") or 0),
                    "maxPreHttpWaitSec": float(result.get("maxPreHttpWaitSec") or 0.0),
                    "maxLlmElapsedSec": float(result.get("maxLlmElapsedSec") or 0.0),
                    "maxPromptBytes": int(result.get("maxPromptBytes") or 0),
                    "maxPromptChars": int(result.get("maxPromptChars") or 0),
                    "primaryLlmCallCount": int(result.get("primaryLlmCallCount") or 0),
                    "primaryHttpStartedCount": int(result.get("primaryHttpStartedCount") or 0),
                    "primaryMaxPreHttpWaitSec": float(result.get("primaryMaxPreHttpWaitSec") or 0.0),
                    "primaryMaxLlmElapsedSec": float(result.get("primaryMaxLlmElapsedSec") or 0.0),
                    "primaryMaxCandidateCount": int(result.get("primaryMaxCandidateCount") or 0),
                    "primaryMaxPromptBytes": int(result.get("primaryMaxPromptBytes") or 0),
                    "primaryMaxPromptChars": int(result.get("primaryMaxPromptChars") or 0),
                    "recoveryLlmCallCount": int(result.get("recoveryLlmCallCount") or 0),
                    "recoveryHttpStartedCount": int(result.get("recoveryHttpStartedCount") or 0),
                    "recoveryMaxPreHttpWaitSec": float(result.get("recoveryMaxPreHttpWaitSec") or 0.0),
                    "recoveryMaxLlmElapsedSec": float(result.get("recoveryMaxLlmElapsedSec") or 0.0),
                    "recoveryMaxCandidateCount": int(result.get("recoveryMaxCandidateCount") or 0),
                    "recoveryMaxPromptBytes": int(result.get("recoveryMaxPromptBytes") or 0),
                    "recoveryMaxPromptChars": int(result.get("recoveryMaxPromptChars") or 0),
                    "recovered": bool(result.get("recovered")),
                    "localRecovery": bool(result.get("localRecovery")),
                    "rateLimitRetryCount": int(result.get("rateLimitRetryCount") or 0),
                }
            ]
        )
        return (
            resolve_selected_rows(candidate_slice, selected_ids, limit=limit),
            selected_ids,
            reasoning,
            {
                "mode": "llm_keyword_search_and_selector",
                "selectionSource": "gemma4_llm_selector",
                "selectorInputMode": _selector_input_mode(product),
                "selectorExcerptChars": _selector_excerpt_chars(product),
                "selectorExcerptBytes": _selector_excerpt_bytes(product),
                "selectorCapsuleCount": len(candidate_slice) if _selector_evidence_capsules_enabled() else 0,
                "selectorContextPacketCount": len(selector_context_packets),
                "selectorContextPackets": selector_context_packets,
                "selectorEvidenceLedgerEnabled": _selector_evidence_ledger_enabled(),
                "selectorEvidenceLedgerCount": len(selector_ledger),
                "selectorEvidenceLedger": selector_ledger,
                "selectorBatchSize": 0,
                "selectorBatchWorkers": 1,
                "selectorCandidateLimit": candidate_limit,
                "selectorAuditedCandidateCount": len(candidate_slice),
                "selectorBatches": [],
                "selectorBatchTrace": batch_trace,
                "selectorBatchCacheHits": 1 if result.get("cacheHit") else 0,
                "selectorBatchCacheMisses": 0 if result.get("cacheHit") else 1,
                "selectorLocalRecoveryCount": 1 if result.get("localRecovery") else 0,
                "selectorRawSelectedIds": selected_ids,
                **candidate_universe_meta,
            },
        )

    selected_rows: list[SearchResult] = []
    selected_ids: list[str] = []
    reasonings: list[str] = []
    seen: set[str] = set()
    batches_by_index: dict[int, dict[str, Any]] = {}
    rows_by_index: dict[int, list[SearchResult]] = {}
    ids_by_index: dict[int, list[str]] = {}
    reasoning_by_index: dict[int, str] = {}
    ledger_by_index: dict[int, list[dict[str, str]]] = {}
    errors: list[str] = []
    batch_offsets = list(range(0, len(candidate_slice), batch_size))
    batch_count = len(batch_offsets)
    workers = _selector_batch_workers(product, batch_count)
    cache_hits = 0
    cache_misses = 0

    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="beta6-selector-batch") as executor:
        futures = {}
        submitted_at: dict[int, float] = {}
        for batch_index, offset in enumerate(batch_offsets, start=1):
            submitted_at[batch_index] = time.monotonic()
            futures[executor.submit(run_batch, batch_index, offset)] = (batch_index, offset)
        completed = 0
        for future in as_completed(futures):
            batch_index, offset = futures[future]
            completed += 1
            detail = _localized_batch_detail("source_selection", language, completed, batch_count)
            end = min(len(candidate_slice), offset + batch_size)
            _emit_progress(
                progress_callback,
                "source_selection",
                detail,
                {
                    "detail": detail,
                    "batch": {"index": completed, "count": batch_count, "start": 0, "end": end},
                },
            )
            try:
                result = future.result()
                batch_rows = list(result["rows"])
                batch_ids = list(result["rawSelectedIds"])
                if result.get("cacheHit"):
                    cache_hits += 1
                else:
                    cache_misses += 1
                accepted_ids = [row.canonical_id for row in batch_rows if row.canonical_id]
                rows_by_index[batch_index] = batch_rows
                ids_by_index[batch_index] = batch_ids
                if result.get("reasoning"):
                    reasoning_by_index[batch_index] = str(result["reasoning"])
                batch_ledger = list(result.get("ledger") or []) if _selector_evidence_ledger_enabled() else []
                ledger_by_index[batch_index] = batch_ledger
                batches_by_index[batch_index] = {
                    "batch": batch_index,
                    "start": result["start"],
                    "end": result["end"],
                    "candidateCount": result["candidateCount"],
                    "status": "completed" if accepted_ids else "empty_selection",
                    "completedOrder": completed,
                    "elapsedSec": float(result.get("elapsedSec") or 0.0),
                    "timeoutSeconds": float(result.get("timeoutSeconds") or 0.0),
                    "primaryTimeoutSeconds": float(result.get("primaryTimeoutSeconds") or 0.0),
                    "recoveryTimeoutSeconds": float(result.get("recoveryTimeoutSeconds") or 0.0),
                    "elapsedExceededTimeout": bool(result.get("elapsedExceededTimeout")),
                    "llmCallCount": int(result.get("llmCallCount") or 0),
                    "llmHttpStartedCount": int(result.get("llmHttpStartedCount") or 0),
                    "maxPreHttpWaitSec": float(result.get("maxPreHttpWaitSec") or 0.0),
                    "maxLlmElapsedSec": float(result.get("maxLlmElapsedSec") or 0.0),
                    "maxPromptBytes": int(result.get("maxPromptBytes") or 0),
                    "maxPromptChars": int(result.get("maxPromptChars") or 0),
                    "primaryLlmCallCount": int(result.get("primaryLlmCallCount") or 0),
                    "primaryHttpStartedCount": int(result.get("primaryHttpStartedCount") or 0),
                    "primaryMaxPreHttpWaitSec": float(result.get("primaryMaxPreHttpWaitSec") or 0.0),
                    "primaryMaxLlmElapsedSec": float(result.get("primaryMaxLlmElapsedSec") or 0.0),
                    "primaryMaxCandidateCount": int(result.get("primaryMaxCandidateCount") or 0),
                    "primaryMaxPromptBytes": int(result.get("primaryMaxPromptBytes") or 0),
                    "primaryMaxPromptChars": int(result.get("primaryMaxPromptChars") or 0),
                    "recoveryLlmCallCount": int(result.get("recoveryLlmCallCount") or 0),
                    "recoveryHttpStartedCount": int(result.get("recoveryHttpStartedCount") or 0),
                    "recoveryMaxPreHttpWaitSec": float(result.get("recoveryMaxPreHttpWaitSec") or 0.0),
                    "recoveryMaxLlmElapsedSec": float(result.get("recoveryMaxLlmElapsedSec") or 0.0),
                    "recoveryMaxCandidateCount": int(result.get("recoveryMaxCandidateCount") or 0),
                    "recoveryMaxPromptBytes": int(result.get("recoveryMaxPromptBytes") or 0),
                    "recoveryMaxPromptChars": int(result.get("recoveryMaxPromptChars") or 0),
                    "rawSelectedIds": batch_ids,
                    "selectedIds": accepted_ids,
                    "ledgerCount": len(batch_ledger),
                    "cacheHit": bool(result.get("cacheHit")),
                    "recovered": bool(result.get("recovered")),
                    "recoveryError": str(result.get("recoveryError") or ""),
                    "recoveryErrors": list(result.get("recoveryErrors") or []),
                    "recoverySubBatchCount": int(result.get("recoverySubBatchCount") or 0),
                    "recoveryBatchSize": int(result.get("recoveryBatchSize") or 0),
                    "recoveryBatchWorkers": int(result.get("recoveryBatchWorkers") or 0),
                    "localRecovery": bool(result.get("localRecovery")),
                    "rateLimitRetryCount": int(result.get("rateLimitRetryCount") or 0),
                    "rateLimitError": str(result.get("rateLimitError") or ""),
                }
            except Exception as exc:
                cache_misses += 1
                error = str(exc)
                errors.append(error)
                batches_by_index[batch_index] = {
                    "batch": batch_index,
                    "start": offset,
                    "end": min(len(candidate_slice), offset + batch_size),
                    "candidateCount": min(batch_size, max(0, len(candidate_slice) - offset)),
                    "status": "selector_error",
                    "completedOrder": completed,
                    "elapsedSec": round(max(0.0, time.monotonic() - submitted_at.get(batch_index, time.monotonic())), 3),
                    "rawSelectedIds": [],
                    "selectedIds": [],
                    "cacheHit": False,
                    "error": error,
                }

    batches = [batches_by_index[index] for index in sorted(batches_by_index)]
    local_recovery_count = sum(1 for batch in batches if batch.get("localRecovery"))
    for batch_index in sorted(rows_by_index):
        for row in rows_by_index[batch_index]:
            if row.canonical_id in seen:
                continue
            seen.add(row.canonical_id)
            selected_rows.append(row)
        selected_ids.extend(ids_by_index.get(batch_index) or [])
        if reasoning_by_index.get(batch_index):
            reasonings.append(f"batch {batch_index}: {reasoning_by_index[batch_index]}")
    selector_ledger: list[dict[str, str]] = []
    seen_ledger_ids: set[str] = set()
    if _selector_evidence_ledger_enabled():
        for batch_index in sorted(ledger_by_index):
            for item in ledger_by_index[batch_index]:
                file_id = str(item.get("fileId") or "").strip()
                if file_id and file_id not in seen_ledger_ids:
                    seen_ledger_ids.add(file_id)
                    selector_ledger.append(item)
    if not selected_rows and errors:
        raise RuntimeError("; ".join(errors[:3]))
    merged_rows = merge_batched_selector_rows(product, query, rows_by_index, limit=limit)
    return (
        merged_rows,
        selected_ids,
        "\n".join(reasonings).strip(),
        {
            "mode": "llm_keyword_search_and_batched_selector",
            "selectionSource": "gemma4_llm_batched_selector",
            "selectorMerge": "interleaved_batch_then_frontier_score",
            "selectorInputMode": _selector_input_mode(product),
            "selectorExcerptChars": _selector_excerpt_chars(product),
            "selectorExcerptBytes": _selector_excerpt_bytes(product),
            "selectorCapsuleCount": len(candidate_slice) if _selector_evidence_capsules_enabled() else 0,
            "selectorContextPacketCount": len(selector_context_packets),
            "selectorContextPackets": selector_context_packets,
            "selectorEvidenceLedgerEnabled": _selector_evidence_ledger_enabled(),
            "selectorEvidenceLedgerCount": len(selector_ledger),
            "selectorEvidenceLedger": selector_ledger,
            "selectorBatchSize": batch_size,
            "selectorBatchWorkers": workers,
            "selectorCandidateLimit": candidate_limit,
            "selectorAuditedCandidateCount": len(candidate_slice),
            "selectorBatches": batches,
            "selectorBatchTrace": _selector_batch_trace(batches),
            "selectorBatchErrors": errors,
            "selectorBatchCacheHits": cache_hits,
            "selectorBatchCacheMisses": cache_misses,
            "selectorLocalRecoveryCount": local_recovery_count,
            "selectorRawSelectedIds": selected_ids,
            **candidate_universe_meta,
        },
    )


def _selector_batch_trace(batches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    trace: list[dict[str, Any]] = []
    for batch in batches[:80]:
        selected_ids = batch.get("selectedIds") or []
        raw_ids = batch.get("rawSelectedIds") or []
        trace.append(
            {
                "batch": int(batch.get("batch") or 0),
                "start": int(batch.get("start") or 0),
                "end": int(batch.get("end") or 0),
                "candidateCount": int(batch.get("candidateCount") or 0),
                "status": str(batch.get("status") or ""),
                "completedOrder": int(batch.get("completedOrder") or 0),
                "elapsedSec": round(float(batch.get("elapsedSec") or 0.0), 3),
                "timeoutSeconds": round(float(batch.get("timeoutSeconds") or 0.0), 3),
                "primaryTimeoutSeconds": round(float(batch.get("primaryTimeoutSeconds") or 0.0), 3),
                "recoveryTimeoutSeconds": round(float(batch.get("recoveryTimeoutSeconds") or 0.0), 3),
                "elapsedExceededTimeout": bool(batch.get("elapsedExceededTimeout")),
                "llmCallCount": int(batch.get("llmCallCount") or 0),
                "llmHttpStartedCount": int(batch.get("llmHttpStartedCount") or 0),
                "maxPreHttpWaitSec": round(float(batch.get("maxPreHttpWaitSec") or 0.0), 3),
                "maxLlmElapsedSec": round(float(batch.get("maxLlmElapsedSec") or 0.0), 3),
                "maxPromptBytes": int(batch.get("maxPromptBytes") or 0),
                "maxPromptChars": int(batch.get("maxPromptChars") or 0),
                "primaryLlmCallCount": int(batch.get("primaryLlmCallCount") or 0),
                "primaryHttpStartedCount": int(batch.get("primaryHttpStartedCount") or 0),
                "primaryMaxPreHttpWaitSec": round(float(batch.get("primaryMaxPreHttpWaitSec") or 0.0), 3),
                "primaryMaxLlmElapsedSec": round(float(batch.get("primaryMaxLlmElapsedSec") or 0.0), 3),
                "primaryMaxCandidateCount": int(batch.get("primaryMaxCandidateCount") or 0),
                "primaryMaxPromptBytes": int(batch.get("primaryMaxPromptBytes") or 0),
                "primaryMaxPromptChars": int(batch.get("primaryMaxPromptChars") or 0),
                "recoveryLlmCallCount": int(batch.get("recoveryLlmCallCount") or 0),
                "recoveryHttpStartedCount": int(batch.get("recoveryHttpStartedCount") or 0),
                "recoveryMaxPreHttpWaitSec": round(float(batch.get("recoveryMaxPreHttpWaitSec") or 0.0), 3),
                "recoveryMaxLlmElapsedSec": round(float(batch.get("recoveryMaxLlmElapsedSec") or 0.0), 3),
                "recoveryMaxCandidateCount": int(batch.get("recoveryMaxCandidateCount") or 0),
                "recoveryMaxPromptBytes": int(batch.get("recoveryMaxPromptBytes") or 0),
                "recoveryMaxPromptChars": int(batch.get("recoveryMaxPromptChars") or 0),
                "cacheHit": bool(batch.get("cacheHit")),
                "selectedCount": len(selected_ids) if isinstance(selected_ids, list) else 0,
                "rawSelectedCount": len(raw_ids) if isinstance(raw_ids, list) else 0,
                "ledgerCount": int(batch.get("ledgerCount") or 0),
                "recovered": bool(batch.get("recovered")),
                "localRecovery": bool(batch.get("localRecovery")),
                "recoverySubBatchCount": int(batch.get("recoverySubBatchCount") or 0),
                "recoveryBatchSize": int(batch.get("recoveryBatchSize") or 0),
                "recoveryError": str(batch.get("recoveryError") or "")[:240],
                "recoveryErrorCount": len(batch.get("recoveryErrors") or []) if isinstance(batch.get("recoveryErrors"), list) else 0,
                "rateLimitRetryCount": int(batch.get("rateLimitRetryCount") or 0),
                "recoveryBatchWorkers": int(batch.get("recoveryBatchWorkers") or 0),
            }
        )
    return trace


def merge_batched_selector_rows(
    product: ProductProfile,
    query: str,
    rows_by_index: dict[int, list[SearchResult]],
    *,
    limit: int,
) -> list[SearchResult]:
    buckets = [(f"batch-{index}", rows_by_index[index]) for index in sorted(rows_by_index) if rows_by_index[index]]
    if not buckets or limit <= 0:
        return []
    total = sum(len(rows) for _label, rows in buckets)
    interleaved = _interleave_beta6_candidate_buckets(buckets, limit=total)
    terms = _beta6_frontier_terms(product, query, [])
    scored: list[tuple[float, int, SearchResult]] = []
    for index, row in enumerate(interleaved):
        score, _matched = _beta6_frontier_score(product, row, terms)
        scored.append((score, index, row))
    scored.sort(key=lambda item: (-item[0], item[1], item[2].canonical_id))
    return [row for _score, _index, row in scored[:limit]]


def _selector_candidate_limit(product: ProductProfile | None = None, *, candidate_count: int | None = None) -> int:
    available = max(0, int(candidate_count or 0))
    return _env_int_from_config(get_domain_adapter(product).selector_candidate_limit_config(available=available))


def _selector_batch_size(product: ProductProfile | None = None) -> int:
    candidate_limit = _selector_candidate_limit(product)
    return _env_int_from_config(get_domain_adapter(product).selector_batch_size_config(candidate_limit=candidate_limit))


def _selector_recovery_batch_size(product: ProductProfile | None, batch_size: int) -> int:
    maximum = max(2, int(batch_size or 1) - 1)
    return _env_int_from_config(
        get_domain_adapter(product).selector_recovery_batch_size_config(batch_size=batch_size, maximum=maximum)
    )


def _selector_error_is_timeout(exc: Exception) -> bool:
    text = str(exc or "").lower()
    return "timeout" in text or "timed out" in text or "read timed out" in text


def _selector_error_is_rate_limit(exc: Exception) -> bool:
    text = str(exc or "").lower()
    return "http 429" in text or "429" in text or "rate limit" in text or "too many requests" in text


def _selector_rate_limit_retries(product: ProductProfile | None = None) -> int:
    return _env_int_from_config(get_domain_adapter(product).selector_rate_limit_retries_config())


def _selector_rate_limit_backoff_seconds(attempt: int, product: ProductProfile | None = None) -> float:
    base = _env_float_from_config(get_domain_adapter(product).selector_rate_limit_backoff_config())
    return base * max(1, int(attempt or 1))


def _selector_batch_workers(product: ProductProfile | None, batch_count: int) -> int:
    maximum = max(1, int(batch_count or 1))
    return _env_int_from_config(get_domain_adapter(product).selector_batch_workers_config(maximum=maximum))


def _selector_recovery_batch_workers(product: ProductProfile | None, sub_batch_count: int) -> int:
    maximum = max(1, int(sub_batch_count or 1))
    return _env_int_from_config(get_domain_adapter(product).selector_recovery_batch_workers_config(maximum=maximum))


def _selector_excerpt_chars(product: ProductProfile | None = None) -> int:
    return _env_int_from_config(get_domain_adapter(product).selector_excerpt_chars_config())


def _selector_excerpt_bytes(product: ProductProfile | None = None) -> int:
    return _env_int_from_config(get_domain_adapter(product).selector_excerpt_bytes_config())


def _beta6_batch_cache_root(cache_root: Path | None = None) -> Path | None:
    if os.getenv("RELIGION_BETA6_BATCH_CACHE_DISABLED", "").strip().lower() in {"1", "true", "yes"}:
        return None
    if cache_root is not None:
        return Path(cache_root)
    configured = os.getenv("RELIGION_BETA6_BATCH_CACHE_ROOT", "").strip()
    return Path(configured) if configured else None


def _stable_cache_digest(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _batch_cache_path(stage: str, payload: dict[str, Any], *, cache_root: Path | None = None) -> tuple[Path, str] | None:
    root = _beta6_batch_cache_root(cache_root)
    if root is None:
        return None
    digest = _stable_cache_digest(payload)
    return root / stage / digest[:2] / f"{digest}.json", digest


def _batch_cache_ttl_seconds() -> int:
    return _env_int("RELIGION_BETA6_BATCH_CACHE_TTL_SECONDS", 7 * 24 * 60 * 60, minimum=0, maximum=365 * 24 * 60 * 60)


def _batch_cache_max_bytes() -> int:
    return _env_int(
        "RELIGION_BETA6_BATCH_CACHE_MAX_BYTES",
        512 * 1024 * 1024,
        minimum=0,
        maximum=64 * 1024 * 1024 * 1024,
    )


def _batch_cache_lock_timeout_seconds() -> float:
    return _env_float("RELIGION_BETA6_BATCH_CACHE_LOCK_TIMEOUT_SECONDS", 180.0, minimum=0.0, maximum=900.0)


def _batch_cache_lock_stale_seconds() -> float:
    return _env_float("RELIGION_BETA6_BATCH_CACHE_LOCK_STALE_SECONDS", 900.0, minimum=1.0, maximum=3600.0)


def _batch_cache_lock_poll_seconds() -> float:
    return _env_float("RELIGION_BETA6_BATCH_CACHE_LOCK_POLL_SECONDS", 0.05, minimum=0.01, maximum=1.0)


def _touch_batch_cache_file(path: Path) -> None:
    try:
        os.utime(path, None)
    except OSError:
        pass


def _prune_batch_cache_root(root: Path, *, keep_path: Path | None = None) -> None:
    max_bytes = _batch_cache_max_bytes()
    if max_bytes <= 0:
        return
    with _BETA6_BATCH_CACHE_PRUNE_LOCK:
        entries: list[tuple[int, int, Path]] = []
        total_bytes = 0
        try:
            paths = list(root.rglob("*.json"))
        except OSError:
            return
        for path in paths:
            try:
                stat = path.stat()
            except OSError:
                continue
            if not path.is_file():
                continue
            total_bytes += stat.st_size
            entries.append((stat.st_mtime_ns, stat.st_size, path))
        if total_bytes <= max_bytes:
            return

        keep_resolved: Path | None = None
        if keep_path is not None:
            try:
                keep_resolved = keep_path.resolve()
            except OSError:
                keep_resolved = keep_path

        for _, size, path in sorted(entries, key=lambda item: (item[0], str(item[2]))):
            if total_bytes <= max_bytes:
                break
            if keep_resolved is not None:
                try:
                    if path.resolve() == keep_resolved:
                        continue
                except OSError:
                    if path == keep_path:
                        continue
            try:
                path.unlink()
            except OSError:
                continue
            total_bytes -= size


def _read_batch_cache(stage: str, payload: dict[str, Any], *, cache_root: Path | None = None) -> dict[str, Any] | None:
    resolved = _batch_cache_path(stage, payload, cache_root=cache_root)
    if resolved is None:
        return None
    path, digest = resolved
    cached = _load_json(path, {})
    if not isinstance(cached, dict) or cached.get("cacheKey") != digest:
        return None
    ttl = _batch_cache_ttl_seconds()
    if ttl > 0:
        try:
            created_at = float(cached.get("createdAt") or 0)
        except (TypeError, ValueError):
            created_at = 0.0
        if created_at <= 0 or time.time() - created_at > ttl:
            try:
                path.unlink()
            except OSError:
                pass
            return None
    value = cached.get("value")
    if not isinstance(value, dict):
        return None
    _touch_batch_cache_file(path)
    return value


def _write_batch_cache(stage: str, payload: dict[str, Any], value: dict[str, Any], *, cache_root: Path | None = None) -> None:
    root = _beta6_batch_cache_root(cache_root)
    if root is None:
        return
    resolved = _batch_cache_path(stage, payload, cache_root=cache_root)
    if resolved is None:
        return
    path, digest = resolved
    _write_json(
        path,
        {
            "cacheKey": digest,
            "stage": stage,
            "cacheVersion": payload.get("cacheVersion"),
            "createdAt": int(time.time()),
            "value": value,
        },
    )
    _prune_batch_cache_root(root, keep_path=path)


def _batch_cache_lock_path(path: Path) -> Path:
    return path.with_name(f".{path.name}.lock")


def _lock_payload() -> bytes:
    payload = {
        "pid": os.getpid(),
        "thread": threading.get_ident(),
        "createdAt": time.time(),
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _batch_cache_lock_is_stale(lock_path: Path) -> bool:
    payload = _load_json(lock_path, {}) or {}
    try:
        owner_pid = int(payload.get("pid") or 0)
    except (TypeError, ValueError):
        owner_pid = 0
    if owner_pid > 0 and not _process_alive(owner_pid):
        return True
    try:
        created_at = float(payload.get("createdAt") or 0)
    except (TypeError, ValueError):
        created_at = 0.0
    if created_at <= 0:
        try:
            created_at = lock_path.stat().st_mtime
        except OSError:
            return True
    return time.time() - created_at > _batch_cache_lock_stale_seconds()


def _acquire_batch_cache_lock(lock_path: Path, *, deadline: float) -> bool:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if _batch_cache_lock_is_stale(lock_path):
                try:
                    lock_path.unlink()
                except OSError:
                    pass
                continue
            if time.time() >= deadline:
                return False
            time.sleep(min(_batch_cache_lock_poll_seconds(), max(0.0, deadline - time.time())))
            continue
        try:
            os.write(fd, _lock_payload())
        finally:
            os.close(fd)
        return True


def _release_batch_cache_lock(lock_path: Path) -> None:
    try:
        lock_path.unlink()
    except OSError:
        pass


def _read_or_fill_batch_cache(
    stage: str,
    payload: dict[str, Any],
    producer: Callable[[], dict[str, Any]],
    *,
    cache_root: Path | None = None,
) -> tuple[dict[str, Any], bool]:
    cached = _read_batch_cache(stage, payload, cache_root=cache_root)
    if cached is not None:
        return cached, True
    resolved = _batch_cache_path(stage, payload, cache_root=cache_root)
    if resolved is None:
        return producer(), False
    path, _ = resolved
    lock_path = _batch_cache_lock_path(path)
    deadline = time.time() + _batch_cache_lock_timeout_seconds()
    acquired = _acquire_batch_cache_lock(lock_path, deadline=deadline)
    if not acquired:
        cached = _read_batch_cache(stage, payload, cache_root=cache_root)
        if cached is not None:
            return cached, True
        return producer(), False
    try:
        cached = _read_batch_cache(stage, payload, cache_root=cache_root)
        if cached is not None:
            return cached, True
        value = producer()
        _write_batch_cache(stage, payload, value, cache_root=cache_root)
        return value, False
    finally:
        _release_batch_cache_lock(lock_path)


def _selector_batch_cache_payload(
    product: ProductProfile,
    query: str,
    language: str,
    model: str,
    *,
    limit: int,
    batch: list[SearchResult],
) -> dict[str, Any]:
    chars = _selector_excerpt_chars(product)
    bytes_budget = _selector_excerpt_bytes(product)
    mode = _selector_input_mode(product)
    if _selector_evidence_capsules_enabled():
        return {
            "cacheVersion": f"beta6-selector-batch-v2-timeout-subbatch-{mode}",
            "product": product.key,
            "query": query,
            "language": language,
            "model": model or "",
            "limit": limit,
            "selectorPolicy": _selector_domain_policy(product.key),
            "selectorInputMode": mode,
            "excerptChars": chars,
            "excerptBytes": bytes_budget,
            "candidates": [
                {
                    "id": capsule["fileId"],
                    "title": capsule["title"],
                    "citation": capsule["citation"],
                    "kind": capsule["sourceKind"],
                    "authorityLevel": capsule["authorityLevel"],
                    "roleHints": capsule["roleHints"],
                    "excerpt": capsule["excerpt"],
                }
                for capsule in build_beta6_evidence_capsules(product, query, batch, excerpt_chars=chars)
            ],
        }
    if _selector_clean_raw_excerpt_enabled() or _selector_role_diversity_hint_enabled():
        return {
            "cacheVersion": f"beta6-selector-batch-v2-timeout-subbatch-{mode}",
            "product": product.key,
            "query": query,
            "language": language,
            "model": model or "",
            "limit": limit,
            "selectorPolicy": _selector_domain_policy(product.key),
            "selectorInputMode": mode,
            "excerptChars": chars,
            "excerptBytes": bytes_budget,
            "candidates": [
                {
                    "id": row.canonical_id,
                    "title": row.title,
                    "citation": row.citation,
                    "kind": row.source_kind,
                    "authorityLevel": row.authority_level,
                    "text": _selector_excerpt_for_prompt(product, row, excerpt_chars=chars),
                }
                for row in batch
            ],
        }
    return {
        "cacheVersion": f"beta6-selector-batch-v2-timeout-subbatch-{mode}",
        "product": product.key,
        "query": query,
        "language": language,
        "model": model or "",
        "limit": limit,
        "selectorPolicy": _selector_domain_policy(product.key),
        "excerptChars": chars,
        "excerptBytes": bytes_budget,
        "candidates": [
            {
                "id": row.canonical_id,
                "title": row.title,
                "citation": row.citation,
                "kind": row.source_kind,
                "authorityLevel": row.authority_level,
                "text": _selector_excerpt_for_prompt(product, row, excerpt_chars=chars),
            }
            for row in batch
        ],
    }


def _claim_analyzer_source_chars(product: ProductProfile | None = None) -> int:
    return _env_int_from_config(get_domain_adapter(product).claim_analyzer_source_chars_config())


def _empty_quote_gate() -> dict[str, int]:
    return {"accepted": 0, "forceMatched": 0, "retried": 0, "recovered": 0, "rejected": 0}


def _claim_analyzer_batch_cache_payload(
    product: ProductProfile,
    query: str,
    language: str,
    model: str,
    selected_records: list[dict[str, Any]],
    selected_evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    chars = _claim_analyzer_source_chars(product)
    sources: list[dict[str, Any]] = []
    for index, (record, evidence) in enumerate(zip(selected_records, selected_evidence), start=1):
        source_id = str(record.get("file_id") or evidence.get("id") or "")
        sources.append(
            {
                "label": str(evidence.get("label") or f"S{index}"),
                "id": source_id,
                "citation": evidence.get("citation") or evidence.get("title") or source_id,
                "role": _source_role_from_payload(product, record, evidence),
                "school": evidence.get("school") or "",
                "tradition": evidence.get("tradition") or "",
                "sourceKind": evidence.get("sourceKind") or "",
                "authorityLevel": evidence.get("authorityLevel") or "",
                "text": str(record.get("extracted_text") or evidence.get("excerpt") or "")[:chars],
            }
        )
    return {
        "cacheVersion": "beta6-claim-card-batch-v3-ko-context",
        "product": product.key,
        "query": query,
        "language": language,
        "model": model or "",
        "policy": _claim_analyzer_policy(product.key),
        "sourceChars": chars,
        "sources": sources,
    }


def _claim_chunk_analyzer_cache_payload(
    product: ProductProfile,
    query: str,
    language: str,
    model: str,
    chunk: dict[str, Any],
    chunk_records: list[dict[str, Any]],
    chunk_evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    chars = _claim_chunk_text_chars(product)
    return {
        "cacheVersion": "beta6-claim-card-chunk-v3-ko-context",
        "product": product.key,
        "query": query,
        "language": language,
        "model": model or "",
        "policy": _claim_analyzer_policy(product.key),
        "chunkTextChars": chars,
        "chunkId": str(chunk.get("chunk_id") or ""),
        "chunkText": str(chunk.get("text") or "")[:chars],
        "sources": [
            {
                "label": str(evidence.get("label") or f"S{index}"),
                "id": str(record.get("file_id") or evidence.get("id") or ""),
                "citation": evidence.get("citation") or evidence.get("title") or record.get("file_id") or "",
                "role": _source_role_from_payload(product, record, evidence),
                "school": evidence.get("school") or "",
                "tradition": evidence.get("tradition") or "",
                "sourceKind": evidence.get("sourceKind") or "",
                "authorityLevel": evidence.get("authorityLevel") or "",
                "textHash": hashlib.sha256(str(record.get("extracted_text") or evidence.get("excerpt") or "").encode("utf-8")).hexdigest(),
            }
            for index, (record, evidence) in enumerate(zip(chunk_records, chunk_evidence), start=1)
        ],
    }


def _localized_batch_detail(stage: str, language: str, index: int, count: int) -> str:
    current = max(1, int(index or 1))
    total = max(current, int(count or current))
    if language == "ko":
        if stage == "source_selection":
            return f"근거 선택 {current}/{total}"
        if stage == "claim_cards":
            return f"주장 카드 {current}/{total}"
        return f"진행 {current}/{total}"
    if language == "ar":
        if stage == "source_selection":
            return f"اختيار المصادر {current}/{total}"
        if stage == "claim_cards":
            return f"بطاقات الادعاء {current}/{total}"
        return f"التقدم {current}/{total}"
    if stage == "source_selection":
        return f"Source selection {current}/{total}"
    if stage == "claim_cards":
        return f"Claim cards {current}/{total}"
    return f"Progress {current}/{total}"


def _claim_analyzer_mode() -> str:
    mode = os.getenv("RELIGION_CLAIM_ANALYZER_MODE", "chunks").strip().lower()
    if mode in {"disabled", "disable", "off", "false", "0", "deterministic"}:
        return "disabled"
    return "source" if mode in {"source", "sources", "batch", "batches"} else "chunks"


def _claim_chunk_text_chars(product: ProductProfile | None = None) -> int:
    return _env_int_from_config(get_domain_adapter(product).claim_chunk_text_chars_config())


def _claim_chunk_analyzer_workers(product: ProductProfile | None, chunk_count: int) -> int:
    maximum = max(1, int(chunk_count or 1))
    return _env_int_from_config(get_domain_adapter(product).claim_chunk_analyzer_workers_config(maximum=maximum))


def _chunk_records_and_evidence(
    chunk: dict[str, Any],
    selected_records: list[dict[str, Any]],
    selected_evidence: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source_ids: set[str] = set()
    for segment in chunk.get("source_segments") or []:
        if isinstance(segment, dict):
            source_id = str(segment.get("file_id") or "").strip()
            if source_id:
                source_ids.add(source_id)
    chunk_file_id = str(chunk.get("file_id") or "").strip()
    if chunk_file_id and chunk_file_id != "multi-source":
        source_ids.add(chunk_file_id)
    if not source_ids:
        return selected_records, selected_evidence
    records: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    for record, item in zip(selected_records, selected_evidence):
        record_id = str(record.get("file_id") or item.get("id") or "").strip()
        if record_id in source_ids:
            records.append(record)
            evidence.append(item)
    if records:
        return records, evidence
    return selected_records, selected_evidence


def _queue_progress_detail(language: str, queue: dict[str, Any]) -> str:
    position = int(queue.get("position") or 1)
    queued = max(position, int(queue.get("queuedJobs") or position))
    eta = int(queue.get("estimatedWaitSeconds") or 0)
    if language == "ko":
        return f"대기 {position}/{queued} · 약 {eta}초"
    if language == "ar":
        return f"الانتظار {position}/{queued} · نحو {eta}ث"
    return f"Queue {position}/{queued} · ~{eta}s"


def _selector_domain_policy(product_key: str) -> str:
    return get_domain_adapter(product_key).selector_policy()


def parse_keyword_generation_response(text: str, *, keyword_count: int = 12) -> list[str]:
    raw = str(text or "").strip()
    values: list[Any] = []
    try:
        obj = json.loads(_extract_json_block(raw))
        if isinstance(obj, dict):
            values = obj.get("keywords") or []
        elif isinstance(obj, list):
            values = obj
    except Exception:
        values = []
    if not values:
        values = [line.strip().strip("-*").strip("\"'") for line in raw.splitlines()]
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        keyword = " ".join(str(value or "").split())
        if not keyword or keyword in seen:
            continue
        seen.add(keyword)
        out.append(keyword)
        if len(out) >= max(1, keyword_count):
            break
    return out


def _extract_json_block(text: str) -> str:
    raw = text.strip()
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", raw, flags=re.DOTALL | re.IGNORECASE)
    if match:
        raw = match.group(1).strip()
    if raw.startswith("{") or raw.startswith("["):
        return raw
    starts = [(raw.find("{"), "}"), (raw.find("["), "]")]
    starts = [(index, end) for index, end in starts if index >= 0]
    if not starts:
        return raw
    index, end_char = min(starts, key=lambda item: item[0])
    end = raw.rfind(end_char)
    if end > index:
        return raw[index : end + 1]
    return raw


def parse_selection_response(text: str) -> tuple[list[str], str]:
    raw = str(text or "")
    match = re.search(r"<selection>\s*(.*?)\s*</selection>", raw, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return [], raw.strip()
    reasoning = raw[: match.start()].strip()
    body = match.group(1).strip()
    if re.search(r"<none\s*/>", body, flags=re.IGNORECASE):
        return [], reasoning
    selected: list[str] = []
    seen: set[str] = set()
    for line in body.splitlines():
        item = line.strip().strip("-*").strip()
        file_id_match = re.search(r"(?:file_id|id)\s*:\s*([^\s,;<>]+)", item, flags=re.IGNORECASE)
        if file_id_match:
            item = file_id_match.group(1)
        item = item.strip().strip("`'\"")
        label_match = re.fullmatch(r"[\[(]?\s*(S\d{1,4})\s*[\])]?\.?", item, flags=re.IGNORECASE)
        if label_match:
            item = label_match.group(1).upper()
        if not item or item in seen:
            continue
        seen.add(item)
        selected.append(item)
    return selected, reasoning


def parse_selection_response_with_ledger(text: str) -> tuple[list[str], str, list[dict[str, str]]]:
    selected, reasoning = parse_selection_response(text)
    ledger: list[dict[str, str]] = []
    seen: set[str] = set()
    for line in reasoning.splitlines():
        raw_line = line.strip().rstrip(",")
        if not raw_line.startswith("{"):
            continue
        try:
            parsed = json.loads(raw_line)
        except Exception:
            continue
        if not isinstance(parsed, dict):
            continue
        file_id = str(parsed.get("file_id") or parsed.get("fileId") or parsed.get("source_id") or parsed.get("sourceId") or "").strip()
        if not file_id or file_id in seen:
            continue
        seen.add(file_id)
        ledger.append(
            {
                "fileId": file_id,
                "contextSummary": _bounded_selector_ledger_text(parsed.get("context_summary") or parsed.get("contextSummary")),
                "claimSummary": _bounded_selector_ledger_text(parsed.get("claim_summary") or parsed.get("claimSummary")),
                "quoteCandidate": _bounded_selector_ledger_text(parsed.get("quote_candidate") or parsed.get("quoteCandidate")),
                "stance": _bounded_selector_ledger_text(parsed.get("stance"), limit=80),
                "sourceRole": _bounded_selector_ledger_text(parsed.get("source_role") or parsed.get("sourceRole"), limit=80),
            }
        )
    if ledger:
        reasoning_lines = [line for line in reasoning.splitlines() if not line.strip().startswith("{")]
        reasoning = "\n".join(reasoning_lines).strip()
    return selected, reasoning, ledger


def _bounded_selector_ledger_text(value: Any, *, limit: int = 500) -> str:
    text = " ".join(str(value or "").split())
    return text[: max(0, int(limit))]


def _normalize_selector_ledger(items: Any) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    if not isinstance(items, list):
        return normalized
    for item in items:
        if not isinstance(item, dict):
            continue
        file_id = str(item.get("fileId") or item.get("file_id") or "").strip()
        if not file_id or file_id in seen:
            continue
        seen.add(file_id)
        normalized.append(
            {
                "fileId": file_id,
                "contextSummary": _bounded_selector_ledger_text(item.get("contextSummary") or item.get("context_summary")),
                "claimSummary": _bounded_selector_ledger_text(item.get("claimSummary") or item.get("claim_summary")),
                "quoteCandidate": _bounded_selector_ledger_text(item.get("quoteCandidate") or item.get("quote_candidate")),
                "stance": _bounded_selector_ledger_text(item.get("stance"), limit=80),
                "sourceRole": _bounded_selector_ledger_text(item.get("sourceRole") or item.get("source_role"), limit=80),
            }
        )
    return normalized


def resolve_selected_rows(candidates: list[SearchResult], selected_ids: list[str], *, limit: int) -> list[SearchResult]:
    by_id = {row.canonical_id: row for row in candidates}
    by_label = {f"S{index}": row for index, row in enumerate(candidates, start=1)}
    rows: list[SearchResult] = []
    seen: set[str] = set()
    for item in selected_ids:
        key = item.strip()
        row = by_id.get(key) or by_label.get(key.upper())
        if row is None:
            continue
        if row.canonical_id in seen:
            continue
        seen.add(row.canonical_id)
        rows.append(row)
        if len(rows) >= limit:
            break
    return rows


def fill_selected_rows(candidates: list[SearchResult], selected_rows: list[SearchResult], *, limit: int) -> list[SearchResult]:
    rows = list(selected_rows[:limit])
    seen = {row.canonical_id for row in rows}
    for candidate in candidates:
        if len(rows) >= limit:
            break
        if not candidate.canonical_id or candidate.canonical_id in seen:
            continue
        seen.add(candidate.canonical_id)
        rows.append(candidate)
    return rows


def build_beta6_chunks_for_manifest(
    selected_records: list[dict[str, Any]],
    *,
    selected_path: Path,
    max_tokens: int = BETA6_CHUNK_TOKEN_BUDGET,
) -> tuple[list[dict[str, Any]], str]:
    try:
        chunks = _build_lawkey_chunks(selected_path, max_tokens=max_tokens)
        if chunks:
            return chunks, "lawkey_legal_evidence_rag"
    except Exception:
        pass
    return build_beta6_chunks(selected_records, max_tokens=max_tokens), "local_fallback"


def build_beta6_chunks(selected_records: list[dict[str, Any]], *, max_tokens: int = BETA6_CHUNK_TOKEN_BUDGET) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    current_tokens = 0

    def flush() -> None:
        nonlocal current, current_tokens
        if not current:
            return
        chunk_id = f"question_selected_manual_{len(chunks) + 1:04d}"
        chunks.append(
            {
                "chunk_id": chunk_id,
                "file_id": "multi-source",
                "token_count": current_tokens,
                "source_count": len(current),
                "text": "\n\n".join(
                    (
                        f"source_id: {record.get('file_id') or ''}\n"
                        f"citation: {record.get('case_number') or record.get('document_title') or record.get('file_id') or ''}\n"
                        f"text:\n{str(record.get('extracted_text') or '')}"
                    )
                    for record in current
                ),
                "source_segments": [
                    {
                        "file_id": record.get("file_id") or "",
                        "case_number": record.get("case_number") or "",
                        "court": record.get("court") or "",
                        "case_name": record.get("case_name") or "",
                        "excerpt": str(record.get("extracted_text") or "")[:900],
                    }
                    for record in current
                ],
            }
        )
        current = []
        current_tokens = 0

    for record in selected_records:
        tokens = max(1, int(record.get("token_count") or 1))
        if current and current_tokens + tokens > max_tokens:
            flush()
        current.append(record)
        current_tokens += min(tokens, max_tokens)
    flush()
    return chunks


def _build_lawkey_chunks(selected_path: Path, *, max_tokens: int) -> list[dict[str, Any]]:
    scripts = Path(os.getenv("LAWKEY_WORKSPACE_SCRIPTS", str(DEFAULT_LAWKEY_WORKSPACE_SCRIPTS)))
    if not scripts.exists():
        return []
    rag = _load_lawkey_rag_module()

    rag_records = rag.load_selected_question_records(selected_path)
    preview_chunks = rag.build_question_chunks_for_records(rag_records, max_tokens=max_tokens, workers=1)
    chunks: list[dict[str, Any]] = []
    for chunk in preview_chunks:
        segments = []
        for segment in getattr(chunk, "source_segments", []) or []:
            segments.append(
                {
                    "file_id": str(segment.get("file_id") or ""),
                    "case_number": str(segment.get("case_number") or ""),
                    "court": str(segment.get("court") or ""),
                    "case_name": str(segment.get("case_name") or ""),
                    "excerpt": str(segment.get("excerpt") or "")[:900],
                }
            )
        chunks.append(
            {
                "chunk_id": str(getattr(chunk, "chunk_id", "") or f"question_selected_manual_{len(chunks) + 1:04d}"),
                "file_id": str(getattr(chunk, "file_id", "") or "multi-source"),
                "token_count": int(getattr(chunk, "token_count", 0) or 0),
                "text": str(getattr(chunk, "text", "") or ""),
                "source_count": len(segments),
                "source_segments": segments,
            }
        )
    return chunks


def build_beta6_messages(
    product: ProductProfile,
    query: str,
    language: str,
    selected_records: list[dict[str, Any]],
    *,
    claim_cards: list[dict[str, Any]] | None = None,
    answer_plan: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    system = (
        "You are a source-grounded answer engine. Answer in the resolved answer language. "
        "Use only the supplied source records for factual claims, cite the source labels, and state uncertainty when sources are thin. "
        "Do not turn source examples into user-specific instructions, diagnosis, prescription, or a binding religious ruling. "
        f"Product: {product.name}. Safety policy: {product.safety_notice}\n"
        f"{_domain_policy(product.key)}"
    )
    writer_claim_cards = _select_claim_cards_for_writer(claim_cards or [], answer_plan or {})
    writer_claim_ids = _available_claim_ids(writer_claim_cards)
    source_blocks = []
    source_limit = _env_int("RELIGION_WRITER_SOURCE_LIMIT", 40, minimum=1, maximum=200)
    body_limit = _env_int("RELIGION_WRITER_SOURCE_CHARS", 700, minimum=300, maximum=2400)
    for index, record in _select_source_records_for_writer(selected_records, writer_claim_cards, limit=source_limit):
        label = record.get("case_number") or record.get("document_title") or record.get("file_id")
        body = " ".join(str(record.get("extracted_text") or "").split())[:body_limit]
        usage_hint = _source_usage_hint(product.key, record)
        hint_line = f"\nwriter_use: {usage_hint}" if usage_hint else ""
        source_blocks.append(f"[S{index}] {label}{hint_line}\n{body}")
    source_index = render_selected_source_index_for_writer(selected_records)
    claim_ledger = render_claim_cards_for_writer(writer_claim_cards)
    plan_block = render_answer_plan_for_writer(_filter_answer_plan_for_writer(answer_plan or {}, writer_claim_ids))
    mcq_block = _tcm_mcq_block_for_prompt(product, query)
    min_answer_chars = _min_answer_chars(product)
    depth_instruction = (
        f"\n\n[minimum answer depth]\nWrite at least {min_answer_chars} visible {language or 'answer-language'} characters "
        "in the main answer body before the Sources section. Do not satisfy this by adding unrelated evidence; add only relevant distinctions, limits, and retrieval gaps."
        if min_answer_chars
        else ""
    )
    user = (
        f"Answer language: {language}\n"
        f"User question: {query}\n\n"
        + (mcq_block + "\n\n" if mcq_block else "")
        + "[selected source index]\n"
        + source_index
        + "\n\n"
        "[selected claim ledger]\n"
        + claim_ledger
        + "\n\n"
        "[answer plan]\n"
        + plan_block
        + "\n\n"
        "Selected beta6 records:\n"
        + "\n\n".join(source_blocks or ["(no sources retrieved)"])
        + depth_instruction
        + f"\n\n{_writer_return_instruction(product.key, language)}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def build_beta6_direct_messages(product: ProductProfile, query: str, language: str) -> list[dict[str, str]]:
    parsed_mcq = get_domain_adapter(product).parse_multiple_choice(query)
    system = (
        "You are a direct answer engine used when retrieval did not produce a reliable source selection. "
        "Answer the user question directly in the resolved answer language. "
        "Do not cite or rely on any unselected retrieval candidates. "
        "State uncertainty when the answer is not knowable from your general domain knowledge. "
        f"Product: {product.name}. Safety policy: {product.safety_notice}\n"
        f"{_domain_policy(product.key)}"
    )
    mcq_block = _tcm_mcq_block_for_prompt(product, query)
    return_instruction = (
        _direct_mcq_return_instruction(parsed_mcq, language=language)
        if parsed_mcq is not None
        else _writer_return_instruction(product.key, language)
    )
    user = (
        f"Answer language: {language}\n"
        f"User question: {query}\n\n"
        + (mcq_block + "\n\n" if mcq_block else "")
        + "Use an uncontaminated direct-answer path; do not mention or cite retrieved sources.\n\n"
        + return_instruction
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _direct_mcq_return_instruction(parsed: Any, *, language: str = "") -> str:
    option_ids: list[str] = []
    for option in getattr(parsed, "options", ()) or ():
        marker = str(getattr(option, "marker", "") or "").strip()
        option_id = marker or str(getattr(option, "number", "") or "").strip()
        if option_id and option_id not in option_ids:
            option_ids.append(option_id)
    if str(language or "").lower().startswith("ko"):
        allowed = f" 가능한 보기ID: {', '.join(option_ids)}." if option_ids else ""
        return (
            "객관식 문제에서는 첫 줄을 반드시 `정답: <보기ID>` 형식으로 쓰세요."
            f"{allowed} 긴 해설, Sources section, citation, 검색 근거 언급은 쓰지 마세요. "
            "필요하면 첫 줄 뒤에 한 문장 이내로만 아주 짧게 이유를 덧붙이세요."
        )
    allowed = f" Allowed option IDs: {', '.join(option_ids)}." if option_ids else ""
    return (
        "For multiple-choice questions, the first line must be `Answer: <option ID>`."
        f"{allowed} Do not write a long explanation, Sources section, citations, or retrieval discussion. "
        "If needed, add at most one short reason after the first line."
    )


def _should_use_direct_writer_after_empty_selector(product: ProductProfile, query: str, selector: dict[str, Any]) -> bool:
    adapter = get_domain_adapter(product)
    if adapter.parse_multiple_choice(query) is None:
        return False
    status = str(selector.get("status") or "")
    if status in {"fallback_no_selection", "fallback_low_coverage"}:
        return True
    if status != "fallback_selector_error":
        return False
    selected_ids = [str(item or "").strip() for item in selector.get("selectedIds") or []]
    if adapter.prioritize_question_first_for_mcq(query) and any(selected_ids):
        return False
    return int(selector.get("selectorLocalRecoveryCount") or 0) > 0


def _tcm_mcq_block_for_prompt(product: ProductProfile, query: str) -> str:
    if not _mcq_structure_enabled():
        return ""
    return get_domain_adapter(product).multiple_choice_prompt_block(query)


def build_claim_cards(
    product: ProductProfile,
    query: str,
    selected_records: list[dict[str, Any]],
    selected_evidence: list[dict[str, Any]],
    *,
    language: str,
) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for index, (record, evidence) in enumerate(zip(selected_records, selected_evidence), start=1):
        source_id = str(record.get("file_id") or evidence.get("id") or "")
        full_text = str(record.get("extracted_text") or evidence.get("excerpt") or "")
        quote, start, end = _extract_claim_quote(full_text)
        role = _source_role_from_payload(product, record, evidence)
        label = str(evidence.get("label") or f"S{index}")
        citation = str(evidence.get("citation") or evidence.get("title") or source_id)
        cards.append(
            {
                "claimId": f"C{index}",
                "label": label,
                "sourceId": source_id,
                "citation": citation,
                "role": role,
                "claimAxis": role,
                "stance": "source_card",
                "contextSummary": _claim_context_summary(product, citation, role, language=language),
                "claimSummary": _claim_summary(product, query, quote, role, language=language),
                "quote": quote,
                "span": {"start": start, "end": end, "exact": quote},
                "quoteVerified": bool(quote),
                "analysisSource": "deterministic_source_card",
                "school": evidence.get("school") or (record.get("metadata") or {}).get("school") or "",
                "tradition": evidence.get("tradition") or (record.get("metadata") or {}).get("tradition") or "",
                "sourceKind": evidence.get("sourceKind") or (record.get("metadata") or {}).get("sourceKind") or "",
            }
        )
    return cards


def build_claim_cards_for_selected_sources(
    product: ProductProfile,
    query: str,
    selected_records: list[dict[str, Any]],
    selected_evidence: list[dict[str, Any]],
    *,
    language: str,
    llm_client: LLMClient | None,
    model: str,
    progress_callback: Callable[..., None] | None = None,
    cache_root: Path | None = None,
    chunks: list[dict[str, Any]] | None = None,
    fast_mode: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    deterministic_cards = build_claim_cards(product, query, selected_records, selected_evidence, language=language)
    claim_analyzer_mode = _claim_analyzer_mode()
    claim_analyzer_disabled = _env_flag("RELIGION_CLAIM_ANALYZER_DISABLED") or claim_analyzer_mode == "disabled"
    if claim_analyzer_disabled or llm_client is None or not selected_records:
        return deterministic_cards, {
            "status": "disabled" if claim_analyzer_disabled else "skipped",
            "mode": "deterministic_source_cards",
            "provider": "",
            "model": model or "",
            "llmCards": 0,
            "deterministicFill": len(deterministic_cards),
            "quoteGate": _empty_quote_gate(),
            "claimAnalyzerPreMergeClaimCount": len(deterministic_cards),
            "claimAnalyzerPostMergeClaimCount": len(deterministic_cards),
            "claimAnalyzerMergedClaimCount": 0,
            "claimAnalyzerMergedSupportCount": 0,
        }

    if chunks and claim_analyzer_mode == "chunks":
        try:
            analyzed_cards, gate, chunk_meta = _analyze_claim_cards_from_chunks(
                product,
                query,
                selected_records,
                selected_evidence,
                chunks,
                language=language,
                llm_client=llm_client,
                model=model,
                progress_callback=progress_callback,
                cache_root=cache_root,
                fast_mode=fast_mode,
            )
        except Exception as exc:
            analyzed_cards = []
            gate = _empty_quote_gate()
            chunk_meta = {
                "chunkCount": len(chunks or []),
                "chunkWorkers": 0,
                "chunks": [],
                "cacheHits": 0,
                "cacheMisses": 0,
                "error": str(exc),
            }
        if analyzed_cards:
            covered_sources = {str(card.get("sourceId") or "") for card in analyzed_cards}
            fill_cards = [
                {**card, "analysisSource": "deterministic_fill"}
                for card in deterministic_cards
                if str(card.get("sourceId") or "") not in covered_sources
            ]
            cards, merge_meta = merge_claim_card_ledger([*analyzed_cards, *fill_cards])
            cards = _renumber_claim_cards(cards)
            return cards, {
                "status": "completed" if not any(item.get("status") == "analyzer_error" for item in chunk_meta["chunks"]) else "completed_with_chunk_errors",
                "mode": "llm_claim_card_chunk_analyzer",
                "provider": str(getattr(llm_client, "provider", "custom_llm") or "custom_llm"),
                "model": model or "",
                "llmCards": len(analyzed_cards),
                "deterministicFill": len(fill_cards),
                "quoteGate": gate,
                **merge_meta,
                "claimAnalyzerChunkCount": chunk_meta["chunkCount"],
                "claimAnalyzerFastMode": bool(chunk_meta.get("fastMode")),
                "claimAnalyzerChunkWorkers": chunk_meta["chunkWorkers"],
                "claimAnalyzerChunks": chunk_meta["chunks"],
                "claimAnalyzerChunkCacheHits": chunk_meta["cacheHits"],
                "claimAnalyzerChunkCacheMisses": chunk_meta["cacheMisses"],
                "claimAnalyzerBatchSize": 0,
                "claimAnalyzerBatchWorkers": 0,
                "claimAnalyzerAuditedSourceCount": len(selected_records),
                "claimAnalyzerBatches": [],
                "claimAnalyzerBatchCacheHits": 0,
                "claimAnalyzerBatchCacheMisses": 0,
            }

    try:
        analyzed_cards, gate, batch_meta = _analyze_claim_cards_in_batches(
            product,
            query,
            selected_records,
            selected_evidence,
            language=language,
            llm_client=llm_client,
            model=model,
            progress_callback=progress_callback,
            cache_root=cache_root,
        )
    except Exception as exc:
        filled = _renumber_claim_cards(
            [{**card, "analysisSource": "deterministic_fill"} for card in deterministic_cards]
        )
        return filled, {
            "status": "fallback_error",
            "mode": "deterministic_source_cards_after_llm_error",
            "provider": str(getattr(llm_client, "provider", "custom_llm") or "custom_llm"),
            "model": model or "",
            "llmCards": 0,
            "deterministicFill": len(filled),
            "quoteGate": _empty_quote_gate(),
            "claimAnalyzerPreMergeClaimCount": len(filled),
            "claimAnalyzerPostMergeClaimCount": len(filled),
            "claimAnalyzerMergedClaimCount": 0,
            "claimAnalyzerMergedSupportCount": 0,
            "claimAnalyzerBatchSize": 0,
            "claimAnalyzerAuditedSourceCount": 0,
            "claimAnalyzerBatches": [],
            "claimAnalyzerBatchCacheHits": 0,
            "claimAnalyzerBatchCacheMisses": 0,
            "error": str(exc),
        }

    covered_sources = {str(card.get("sourceId") or "") for card in analyzed_cards}
    fill_cards: list[dict[str, Any]] = []
    for card in deterministic_cards:
        if str(card.get("sourceId") or "") in covered_sources:
            continue
        fill_cards.append({**card, "analysisSource": "deterministic_fill"})
    cards, merge_meta = merge_claim_card_ledger([*analyzed_cards, *fill_cards])
    cards = _renumber_claim_cards(cards)
    batch_errors = [batch for batch in batch_meta["batches"] if batch.get("status") == "analyzer_error"]
    if analyzed_cards and batch_errors:
        status = "completed_with_batch_errors"
    elif analyzed_cards:
        status = "completed"
    else:
        status = "fallback_empty"
    return cards, {
        "status": status,
        "mode": (
            "llm_claim_card_batched_analyzer"
            if analyzed_cards and len(batch_meta["batches"]) > 1
            else "llm_claim_card_analyzer"
            if analyzed_cards
            else "deterministic_source_cards_after_empty_llm"
        ),
        "provider": str(getattr(llm_client, "provider", "custom_llm") or "custom_llm"),
        "model": model or "",
        "llmCards": len(analyzed_cards),
        "deterministicFill": len(fill_cards),
        "quoteGate": gate,
        **merge_meta,
        "claimAnalyzerBatchSize": batch_meta["batchSize"],
        "claimAnalyzerBatchWorkers": batch_meta["batchWorkers"],
        "claimAnalyzerAuditedSourceCount": batch_meta["auditedSourceCount"],
        "claimAnalyzerBatches": batch_meta["batches"],
        "claimAnalyzerBatchCacheHits": batch_meta["cacheHits"],
        "claimAnalyzerBatchCacheMisses": batch_meta["cacheMisses"],
    }


def _analyze_claim_cards_in_batches(
    product: ProductProfile,
    query: str,
    selected_records: list[dict[str, Any]],
    selected_evidence: list[dict[str, Any]],
    *,
    language: str,
    llm_client: LLMClient,
    model: str,
    progress_callback: Callable[..., None] | None = None,
    cache_root: Path | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int], dict[str, Any]]:
    source_limit = _claim_analyzer_source_limit()
    audited_records = selected_records[:source_limit]
    audited_evidence = selected_evidence[:source_limit]
    batch_size = _claim_analyzer_batch_size(source_limit)
    cards: list[dict[str, Any]] = []
    gate = _empty_quote_gate()
    batches_by_index: dict[int, dict[str, Any]] = {}
    cards_by_index: dict[int, list[dict[str, Any]]] = {}
    gates_by_index: dict[int, dict[str, int]] = {}
    seen_card_keys: set[tuple[str, str, str]] = set()
    batch_offsets = list(range(0, len(audited_records), batch_size))
    batch_count = len(batch_offsets)
    workers = _claim_analyzer_batch_workers(product, batch_count)
    cache_hits = 0
    cache_misses = 0

    def run_batch(batch_index: int, offset: int) -> dict[str, Any]:
        batch_records = audited_records[offset : offset + batch_size]
        batch_evidence = audited_evidence[offset : offset + batch_size]
        payload = _claim_analyzer_batch_cache_payload(
            product,
            query,
            language,
            model,
            batch_records,
            batch_evidence,
        )
        def produce() -> dict[str, Any]:
            raw = _complete_llm(
                llm_client,
                build_beta6_claim_card_messages(product, query, language, batch_records, batch_evidence),
                model=model,
                timeout_seconds=_claim_analyzer_timeout_seconds(),
            )
            parsed = parse_claim_card_analysis_response(raw)
            batch_cards, batch_gate = _coerce_llm_claim_cards(
                product,
                query,
                batch_records,
                batch_evidence,
                parsed,
                language=language,
                llm_client=llm_client,
                model=model,
            )
            return {"cards": batch_cards, "quoteGate": batch_gate}

        cached_or_value, cache_hit = _read_or_fill_batch_cache("claim_cards", payload, produce, cache_root=cache_root)
        return {
            "batch": batch_index,
            "start": offset,
            "end": offset + len(batch_records),
            "sourceCount": len(batch_records),
            "cards": list(cached_or_value.get("cards") or []),
            "quoteGate": dict(cached_or_value.get("quoteGate") or {}),
            "cacheHit": cache_hit,
        }

    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="beta6-claim-batch") as executor:
        futures = {
            executor.submit(run_batch, batch_index, offset): (batch_index, offset)
            for batch_index, offset in enumerate(batch_offsets, start=1)
        }
        completed = 0
        for future in as_completed(futures):
            batch_index, offset = futures[future]
            completed += 1
            detail = _localized_batch_detail("claim_cards", language, completed, batch_count)
            end = min(len(audited_records), offset + batch_size)
            _emit_progress(
                progress_callback,
                "claim_cards",
                detail,
                {
                    "detail": detail,
                    "batch": {"index": completed, "count": batch_count, "start": 0, "end": end},
                },
            )
            try:
                result = future.result()
                batch_cards = list(result["cards"])
                batch_gate = dict(result["quoteGate"])
                if result.get("cacheHit"):
                    cache_hits += 1
                else:
                    cache_misses += 1
                cards_by_index[batch_index] = batch_cards
                gates_by_index[batch_index] = batch_gate
                batches_by_index[batch_index] = {
                    "batch": batch_index,
                    "start": result["start"],
                    "end": result["end"],
                    "sourceCount": result["sourceCount"],
                    "status": "completed" if batch_cards else "empty_analysis",
                    "llmCards": len(batch_cards),
                    "quoteGate": batch_gate,
                    "cacheHit": bool(result.get("cacheHit")),
                }
            except Exception as exc:
                cache_misses += 1
                batches_by_index[batch_index] = {
                    "batch": batch_index,
                    "start": offset,
                    "end": min(len(audited_records), offset + batch_size),
                    "sourceCount": min(batch_size, max(0, len(audited_records) - offset)),
                    "status": "analyzer_error",
                    "llmCards": 0,
                    "quoteGate": _empty_quote_gate(),
                    "cacheHit": False,
                    "error": str(exc),
                }

    for batch_index in sorted(cards_by_index):
        for card in cards_by_index[batch_index]:
            key = (
                str(card.get("sourceId") or ""),
                str(card.get("quote") or ""),
                str(card.get("claimSummary") or ""),
            )
            if key in seen_card_keys:
                continue
            seen_card_keys.add(key)
            cards.append(card)
        for name, value in (gates_by_index.get(batch_index) or {}).items():
            gate[name] = gate.get(name, 0) + int(value or 0)
    batches = [batches_by_index[index] for index in sorted(batches_by_index)]
    return cards, gate, {
        "batchSize": batch_size,
        "batchWorkers": workers,
        "auditedSourceCount": len(audited_records),
        "batches": batches,
        "cacheHits": cache_hits,
        "cacheMisses": cache_misses,
    }


def _claim_analyzer_source_limit() -> int:
    return _env_int("RELIGION_CLAIM_ANALYZER_SOURCE_LIMIT", LAWKEY_DEFAULT_TOP_K_PRECEDENTS, minimum=1, maximum=200)


def _claim_analyzer_batch_size(source_limit: int | None = None) -> int:
    maximum = max(1, int(source_limit or LAWKEY_DEFAULT_TOP_K_PRECEDENTS))
    default = min(20, maximum)
    return _env_int("RELIGION_CLAIM_ANALYZER_BATCH_SIZE", default, minimum=1, maximum=maximum)


def _claim_analyzer_batch_workers(product: ProductProfile | None, batch_count: int) -> int:
    maximum = max(1, int(batch_count or 1))
    return _env_int_from_config(get_domain_adapter(product).claim_analyzer_batch_workers_config(maximum=maximum))


def build_beta6_claim_card_messages(
    product: ProductProfile,
    query: str,
    language: str,
    selected_records: list[dict[str, Any]],
    selected_evidence: list[dict[str, Any]],
) -> list[dict[str, str]]:
    source_limit = _claim_analyzer_source_limit()
    chars = _claim_analyzer_source_chars(product)
    source_blocks: list[str] = []
    for index, (record, evidence) in enumerate(zip(selected_records, selected_evidence), start=1):
        if index > source_limit:
            break
        source_id = str(record.get("file_id") or evidence.get("id") or "")
        source_label = str(evidence.get("label") or f"S{index}")
        role = _source_role_from_payload(product, record, evidence)
        meta = []
        for key in ("school", "tradition", "sourceKind", "authorityLevel"):
            value = evidence.get(key)
            if value:
                meta.append(f"{key}={value}")
        selector_hints: list[str] = []
        for key, label in (
            ("selectorContextSummary", "selector_context_summary"),
            ("selectorClaimSummary", "selector_claim_summary"),
            ("selectorQuoteCandidate", "selector_quote_candidate"),
            ("selectorStance", "selector_stance"),
            ("selectorSourceRole", "selector_source_role"),
        ):
            value = _bounded_selector_ledger_text(evidence.get(key))
            if value:
                selector_hints.append(f"{label}: {value}")
        text = str(record.get("extracted_text") or evidence.get("excerpt") or "")
        selector_hint_block = "\n".join(selector_hints) + "\n" if selector_hints else ""
        source_blocks.append(
            f"[{source_label}]\n"
            f"source_id: {source_id}\n"
            f"citation: {evidence.get('citation') or evidence.get('title') or source_id}\n"
            f"role: {role}\n"
            f"metadata: {'; '.join(meta)}\n"
            f"{selector_hint_block}"
            f"text:\n{text[:chars]}"
        )
    policy = _claim_analyzer_policy(product.key)
    user = (
        "Build beta-6 claim cards from the selected source text.\n"
        f"Rules:\n{policy}\n"
        "- Return JSON only.\n"
        "- Every card must cite one selected source by source_label and source_id.\n"
        "- quote must be a short consecutive substring copied from that source text. If no exact quote supports a card, omit the card.\n"
        "- context_summary must explain the larger source or section containing the quoted part, not the whole corpus.\n"
        "- claim_summary must explain what the exact quote says in its original source context.\n"
        "- claim_summary must not explain why the final answer selected the quote.\n"
        "- For Korean answers, write context_summary and claim_summary in Korean.\n"
        "- Do not invent facts, school positions, diagnosis, prescription, or binding fatwa.\n"
        'Schema: {"claim_cards":[{"source_label":"S1","source_id":"...","claim_axis":"...",'
        '"stance":"support|limit|variant|gap|school_position","context_summary":"...",'
        '"claim_summary":"...","quote":"..."}]}\n\n'
        f"Answer language hint: {language}\n"
        f"User question:\n{query}\n\n"
        "Selected sources:\n"
        + "\n\n".join(source_blocks or ["(no sources)"])
    )
    return [
        {"role": "system", "content": f"Gemma 4 beta-6 claim-card analyzer for {product.name}. JSON only."},
        {"role": "user", "content": user},
    ]


def _claim_analyzer_policy(product_key: str) -> str:
    return get_domain_adapter(product_key).claim_analyzer_policy()


def parse_claim_card_analysis_response(text: str) -> list[dict[str, Any]]:
    raw = str(text or "").strip()
    try:
        parsed = json.loads(_extract_json_block(raw))
    except Exception:
        return []
    if isinstance(parsed, dict):
        cards = parsed.get("claim_cards") or parsed.get("claimCards") or parsed.get("cards") or []
    elif isinstance(parsed, list):
        cards = parsed
    else:
        cards = []
    return [card for card in cards if isinstance(card, dict)]


def _coerce_llm_claim_cards(
    product: ProductProfile,
    query: str,
    selected_records: list[dict[str, Any]],
    selected_evidence: list[dict[str, Any]],
    parsed_cards: list[dict[str, Any]],
    *,
    language: str,
    llm_client: LLMClient | None = None,
    model: str = "",
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    by_label: dict[str, tuple[int, dict[str, Any], dict[str, Any]]] = {}
    by_id: dict[str, tuple[int, dict[str, Any], dict[str, Any]]] = {}
    for index, (record, evidence) in enumerate(zip(selected_records, selected_evidence), start=1):
        label = str(evidence.get("label") or f"S{index}")
        source_id = str(record.get("file_id") or evidence.get("id") or "")
        by_label[label.upper()] = (index, record, evidence)
        if source_id:
            by_id[source_id] = (index, record, evidence)
    cards: list[dict[str, Any]] = []
    pending_cards: list[dict[str, Any]] = []
    retry_groups: dict[str, dict[str, Any]] = {}
    gate = _empty_quote_gate()
    for raw_card in parsed_cards:
        label = str(
            raw_card.get("source_label")
            or raw_card.get("sourceLabel")
            or raw_card.get("label")
            or ""
        ).strip()
        source_id = str(raw_card.get("source_id") or raw_card.get("sourceId") or "").strip()
        found = by_label.get(label.upper()) if label else None
        if found is None and source_id:
            found = by_id.get(source_id)
        if found is None:
            gate["rejected"] += 1
            continue
        index, record, evidence = found
        resolved_label = str(evidence.get("label") or f"S{index}")
        resolved_source_id = str(record.get("file_id") or evidence.get("id") or source_id)
        full_text = str(record.get("extracted_text") or evidence.get("excerpt") or "")
        requested_quote = str(raw_card.get("quote") or raw_card.get("evidence_quote") or "").strip()
        quote, start, end, match_source = _locate_or_force_match_claim_quote(
            full_text,
            requested_quote,
            allow_fallback=False,
        )
        if match_source == "exact":
            gate["accepted"] += 1
        elif match_source == "force_match":
            gate["forceMatched"] += 1
        role = _source_role_from_payload(product, record, evidence)
        citation = str(evidence.get("citation") or evidence.get("title") or resolved_source_id)
        context_summary = str(raw_card.get("context_summary") or raw_card.get("contextSummary") or "").strip()
        claim_summary = str(raw_card.get("claim_summary") or raw_card.get("claimSummary") or "").strip()
        card = {
            "claimId": "",
            "label": resolved_label,
            "sourceId": resolved_source_id,
            "citation": citation,
            "role": role,
            "claimAxis": str(raw_card.get("claim_axis") or raw_card.get("claimAxis") or "").strip() or role,
            "stance": str(raw_card.get("stance") or "").strip() or "source_claim",
            "contextSummary": context_summary or _claim_context_summary(product, citation, role, language=language),
            "claimSummary": claim_summary,
            "quote": quote,
            "span": {"start": start, "end": end, "exact": quote},
            "quoteVerified": bool(quote),
            "analysisSource": "llm_claim_analyzer",
            "quoteMatch": match_source,
            "school": evidence.get("school") or (record.get("metadata") or {}).get("school") or "",
            "tradition": evidence.get("tradition") or (record.get("metadata") or {}).get("tradition") or "",
            "sourceKind": evidence.get("sourceKind") or (record.get("metadata") or {}).get("sourceKind") or "",
        }
        if quote:
            card["claimSummary"] = claim_summary or _claim_summary(product, query, quote, role, language=language)
            pending_cards.append(card)
            continue
        if not requested_quote or llm_client is None or not _claim_quote_retry_enabled():
            gate["rejected"] += 1
            continue
        retry_id = f"R{len(pending_cards)}"
        card["_retryId"] = retry_id
        retry_groups.setdefault(
            resolved_source_id,
            {
                "fullText": full_text,
                "items": [],
            },
        )["items"].append({"retry_id": retry_id, "quote": requested_quote})
        pending_cards.append(card)
        gate["retried"] += 1

    recovered_by_id: dict[str, tuple[str, int, int]] = {}
    for group in retry_groups.values():
        recovered_by_id.update(
            _retry_claim_quotes_from_source(
                product,
                query,
                language,
                str(group.get("fullText") or ""),
                list(group.get("items") or []),
                llm_client=llm_client,
                model=model,
            )
        )

    for card in pending_cards:
        retry_id = str(card.pop("_retryId", "") or "")
        if retry_id:
            recovered = recovered_by_id.get(retry_id)
            if recovered is None:
                gate["rejected"] += 1
                continue
            quote, start, end = recovered
            card["quote"] = quote
            card["span"] = {"start": start, "end": end, "exact": quote}
            card["quoteVerified"] = True
            card["quoteMatch"] = "retry"
            card["quoteRecovered"] = True
            card["claimSummary"] = card.get("claimSummary") or _claim_summary(
                product,
                query,
                quote,
                str(card.get("role") or ""),
                language=language,
            )
            gate["recovered"] += 1
        card["claimId"] = f"C{len(cards) + 1}"
        cards.append(card)
    return cards, gate


def build_beta6_chunk_claim_card_messages(
    product: ProductProfile,
    query: str,
    language: str,
    chunk: dict[str, Any],
    chunk_records: list[dict[str, Any]],
    chunk_evidence: list[dict[str, Any]],
) -> list[dict[str, str]]:
    chars = _claim_chunk_text_chars(product)
    source_blocks: list[str] = []
    for index, (record, evidence) in enumerate(zip(chunk_records, chunk_evidence), start=1):
        source_id = str(record.get("file_id") or evidence.get("id") or "")
        source_label = str(evidence.get("label") or f"S{index}")
        role = _source_role_from_payload(product, record, evidence)
        meta = []
        for key in ("school", "tradition", "sourceKind", "authorityLevel"):
            value = evidence.get(key)
            if value:
                meta.append(f"{key}={value}")
        source_blocks.append(
            f"[{source_label}]\n"
            f"source_id: {source_id}\n"
            f"citation: {evidence.get('citation') or evidence.get('title') or source_id}\n"
            f"role: {role}\n"
            f"metadata: {'; '.join(meta)}"
        )
    policy = _claim_analyzer_policy(product.key)
    chunk_id = str(chunk.get("chunk_id") or "")
    chunk_text = str(chunk.get("text") or "")
    if not chunk_text:
        chunk_text = "\n\n".join(
            str(segment.get("excerpt") or "")
            for segment in chunk.get("source_segments") or []
            if isinstance(segment, dict)
        )
    user = (
        "Build beta-6 claim cards from this selected-source chunk.\n"
        f"chunk_id: {chunk_id}\n"
        f"Rules:\n{policy}\n"
        "- Return JSON only.\n"
        "- Every card must cite one selected source by source_label and source_id.\n"
        "- quote must be a short consecutive substring copied from the original selected source text. If no exact quote supports a card, omit the card.\n"
        "- context_summary must explain the larger source or section containing the quoted part, not the whole corpus.\n"
        "- claim_summary must explain what the exact quote says in its original source context.\n"
        "- claim_summary must not explain why the final answer selected the quote.\n"
        "- For Korean answers, write context_summary and claim_summary in Korean.\n"
        "- Do not invent facts, school positions, diagnosis, prescription, or binding fatwa.\n"
        "- Include chunk_id on each returned card.\n"
        'Schema: {"claim_cards":[{"source_label":"S1","source_id":"...","chunk_id":"...",'
        '"claim_axis":"...","stance":"support|limit|variant|gap|school_position",'
        '"context_summary":"...","claim_summary":"...","quote":"..."}]}\n\n'
        f"Answer language hint: {language}\n"
        f"User question:\n{query}\n\n"
        "Source manifest:\n"
        + "\n\n".join(source_blocks or ["(no sources)"])
        + "\n\nChunk text:\n"
        + chunk_text[:chars]
    )
    return [
        {"role": "system", "content": f"Gemma 4 beta-6 chunk-level claim-card analyzer for {product.name}. JSON only."},
        {"role": "user", "content": user},
    ]


def _analyze_claim_cards_from_chunks(
    product: ProductProfile,
    query: str,
    selected_records: list[dict[str, Any]],
    selected_evidence: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
    *,
    language: str,
    llm_client: LLMClient,
    model: str,
    progress_callback: Callable[..., None] | None = None,
    cache_root: Path | None = None,
    fast_mode: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, int], dict[str, Any]]:
    chunk_limit = (
        _env_int("RELIGION_FAST_CHUNK_CLAIM_ANALYZER_LIMIT", 10, minimum=1, maximum=10)
        if fast_mode
        else _env_int("RELIGION_CHUNK_CLAIM_ANALYZER_LIMIT", 80, minimum=1, maximum=200)
    )
    audited_chunks = [chunk for chunk in chunks[:chunk_limit] if isinstance(chunk, dict)]
    chunk_count = len(audited_chunks)
    workers = _claim_chunk_analyzer_workers(product, chunk_count)
    cards_by_index: dict[int, list[dict[str, Any]]] = {}
    gates_by_index: dict[int, dict[str, int]] = {}
    chunks_by_index: dict[int, dict[str, Any]] = {}
    gate = {"accepted": 0, "forceMatched": 0, "rejected": 0}
    cache_hits = 0
    cache_misses = 0

    def run_chunk(index: int, chunk: dict[str, Any]) -> dict[str, Any]:
        chunk_records, chunk_evidence = _chunk_records_and_evidence(chunk, selected_records, selected_evidence)
        payload = _claim_chunk_analyzer_cache_payload(product, query, language, model, chunk, chunk_records, chunk_evidence)
        chunk_id = str(chunk.get("chunk_id") or "")

        def produce() -> dict[str, Any]:
            raw = _complete_llm(
                llm_client,
                build_beta6_chunk_claim_card_messages(product, query, language, chunk, chunk_records, chunk_evidence),
                model=model,
                timeout_seconds=_claim_analyzer_timeout_seconds(),
            )
            parsed = parse_claim_card_analysis_response(raw)
            chunk_cards, chunk_gate = _coerce_llm_claim_cards(
                product,
                query,
                chunk_records,
                chunk_evidence,
                parsed,
                language=language,
                llm_client=llm_client,
                model=model,
            )
            chunk_cards = [
                {
                    **card,
                    "analysisSource": "llm_chunk_claim_analyzer",
                    "sourceChunkId": str(card.get("sourceChunkId") or chunk_id),
                }
                for card in chunk_cards
            ]
            return {"cards": chunk_cards, "quoteGate": chunk_gate}

        cached_or_value, cache_hit = _read_or_fill_batch_cache("claim_chunks", payload, produce, cache_root=cache_root)
        return {
            "index": index,
            "chunkId": chunk_id,
            "sourceCount": len(chunk_records),
            "cards": list(cached_or_value.get("cards") or []),
            "quoteGate": dict(cached_or_value.get("quoteGate") or {}),
            "cacheHit": cache_hit,
        }

    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="beta6-claim-chunk") as executor:
        futures = {
            executor.submit(run_chunk, index, chunk): (index, chunk)
            for index, chunk in enumerate(audited_chunks, start=1)
        }
        completed = 0
        for future in as_completed(futures):
            index, chunk = futures[future]
            completed += 1
            detail = _localized_batch_detail("claim_cards", language, completed, chunk_count)
            _emit_progress(
                progress_callback,
                "claim_cards",
                detail,
                {
                    "detail": detail,
                    "batch": {"index": completed, "count": chunk_count, "start": 0, "end": completed},
                },
            )
            try:
                result = future.result()
                if result.get("cacheHit"):
                    cache_hits += 1
                else:
                    cache_misses += 1
                cards_by_index[index] = list(result["cards"])
                gates_by_index[index] = dict(result["quoteGate"])
                chunks_by_index[index] = {
                    "chunk": index,
                    "chunkId": result["chunkId"],
                    "sourceCount": result["sourceCount"],
                    "status": "completed" if result["cards"] else "empty_analysis",
                    "llmCards": len(result["cards"]),
                    "quoteGate": result["quoteGate"],
                    "cacheHit": bool(result.get("cacheHit")),
                }
            except Exception as exc:
                cache_misses += 1
                chunks_by_index[index] = {
                    "chunk": index,
                    "chunkId": str(chunk.get("chunk_id") or ""),
                    "sourceCount": len(chunk.get("source_segments") or []),
                    "status": "analyzer_error",
                    "llmCards": 0,
                    "quoteGate": _empty_quote_gate(),
                    "cacheHit": False,
                    "error": str(exc),
                }

    cards: list[dict[str, Any]] = []
    seen_card_keys: set[tuple[str, str, str, str]] = set()
    for index in sorted(cards_by_index):
        for card in cards_by_index[index]:
            key = (
                str(card.get("sourceId") or ""),
                str(card.get("sourceChunkId") or ""),
                str(card.get("quote") or ""),
                str(card.get("claimSummary") or ""),
            )
            if key in seen_card_keys:
                continue
            seen_card_keys.add(key)
            cards.append(card)
        for name, value in (gates_by_index.get(index) or {}).items():
            gate[name] = gate.get(name, 0) + int(value or 0)
    return cards, gate, {
        "chunkCount": chunk_count,
        "fastMode": fast_mode,
        "chunkWorkers": workers,
        "chunks": [chunks_by_index[index] for index in sorted(chunks_by_index)],
        "cacheHits": cache_hits,
        "cacheMisses": cache_misses,
    }


def _claim_quote_retry_enabled() -> bool:
    return os.getenv("RELIGION_CLAIM_QUOTE_RETRY_DISABLED", "").strip().lower() not in {"1", "true", "yes"}


def _claim_quote_retry_text_chars() -> int:
    return _env_int("RELIGION_CLAIM_QUOTE_RETRY_TEXT_CHARS", 20000, minimum=1200, maximum=40000)


def _claim_quote_retry_batch_size() -> int:
    return _env_int("RELIGION_CLAIM_QUOTE_RETRY_BATCH_SIZE", 12, minimum=1, maximum=40)


def _retry_claim_quotes_from_source(
    product: ProductProfile,
    query: str,
    language: str,
    full_text: str,
    items: list[dict[str, str]],
    *,
    llm_client: LLMClient | None,
    model: str,
) -> dict[str, tuple[str, int, int]]:
    if llm_client is None:
        return {}
    text = str(full_text or "")
    if not text or not items:
        return {}
    recovered: dict[str, tuple[str, int, int]] = {}
    batch_size = _claim_quote_retry_batch_size()
    char_budget = _claim_quote_retry_text_chars()
    for offset in range(0, len(items), batch_size):
        batch = items[offset : offset + batch_size]
        prompt = (
            "Each quote below failed the beta-6 exact source-span gate.\n"
            "Correct each quote to a consecutive substring that actually appears in full_text, or omit it.\n"
            "- Keep retry_id unchanged.\n"
            "- Return JSON only.\n"
            "- Do not infer, paraphrase, translate, summarize, or invent a quote.\n"
            "- quote must be copied verbatim from full_text.\n\n"
            f"Product: {product.key}\n"
            f"Answer language hint: {language}\n"
            f"User question:\n{query}\n\n"
            f"[full_text]\n{text[:char_budget]}\n\n"
            "[quotes_to_correct]\n"
            + json.dumps(batch, ensure_ascii=False, indent=2)
        )
        try:
            response = _complete_llm(
                llm_client,
                [
                    {
                        "role": "system",
                        "content": f"Gemma 4 beta-6 claim quote span retry for {product.name}. JSON only.",
                    },
                    {"role": "user", "content": prompt},
                ],
                model=model,
                timeout_seconds=_claim_analyzer_timeout_seconds(),
            )
            for retry_id, quote in _parse_claim_quote_retry_response(response, batch).items():
                if retry_id in recovered:
                    continue
                start = text.find(quote)
                if start < 0:
                    continue
                recovered[retry_id] = (quote, start, start + len(quote))
        except Exception:
            continue
    return recovered


def _parse_claim_quote_retry_response(text: str, batch: list[dict[str, str]]) -> dict[str, str]:
    try:
        parsed = json.loads(_extract_json_block(str(text or "").strip()))
    except Exception:
        return {}
    if isinstance(parsed, dict):
        raw_items = (
            parsed.get("quotes")
            or parsed.get("items")
            or parsed.get("claim_quotes")
            or parsed.get("claimQuotes")
            or parsed.get("results")
        )
        if raw_items is None:
            raw_items = [parsed]
    elif isinstance(parsed, list):
        raw_items = parsed
    else:
        raw_items = []
    default_retry_id = str((batch[0] if len(batch) == 1 else {}).get("retry_id") or "")
    out: dict[str, str] = {}
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            continue
        retry_id = str(raw_item.get("retry_id") or raw_item.get("retryId") or default_retry_id).strip()
        quote = str(raw_item.get("quote") or raw_item.get("corrected_quote") or raw_item.get("correctedQuote") or "").strip()
        if retry_id and quote:
            out[retry_id] = quote
    return out


def _locate_or_force_match_claim_quote(
    full_text: str,
    requested_quote: str,
    *,
    allow_fallback: bool = True,
) -> tuple[str, int, int, str]:
    text = str(full_text or "")
    quote = str(requested_quote or "").strip()
    if quote:
        exact_index = text.find(quote)
        if exact_index >= 0:
            return quote, exact_index, exact_index + len(quote), "exact"
        matched = _best_actual_text_span(text, quote)
        if matched is not None:
            start, end = matched
            return text[start:end].strip(), start, start + len(text[start:end].strip()), "force_match"
    if not allow_fallback:
        return "", 0, 0, "rejected"
    fallback, start, end = _extract_claim_quote(text)
    if fallback:
        return fallback, start, end, "fallback"
    return "", 0, 0, "rejected"


def _best_actual_text_span(full_text: str, quote: str) -> tuple[int, int] | None:
    best: tuple[float, int, int] | None = None
    needle = " ".join(str(quote or "").split())
    if not needle:
        return None
    for start, end, candidate in _candidate_text_spans(full_text):
        compact = " ".join(candidate.split())
        if not compact:
            continue
        ratio = difflib.SequenceMatcher(None, needle[:700], compact[:900]).ratio()
        if best is None or ratio > best[0]:
            best = (ratio, start, end)
    threshold = _env_float("RELIGION_CLAIM_FORCE_MATCH_THRESHOLD", 0.72, minimum=0.5, maximum=0.95)
    if best is None or best[0] < threshold:
        return None
    return best[1], best[2]


def _candidate_text_spans(full_text: str) -> list[tuple[int, int, str]]:
    spans: list[tuple[int, int, str]] = []
    text = str(full_text or "")
    for match in re.finditer(r"[^\r\n]+", text):
        candidate = match.group(0).strip()
        if _is_claim_quote_line(candidate):
            leading = len(match.group(0)) - len(match.group(0).lstrip())
            trailing = len(match.group(0)) - len(match.group(0).rstrip())
            spans.append((match.start() + leading, match.end() - trailing, candidate))
    for match in re.finditer(r"[^.!?。！？\n]{24,900}[.!?。！？]?", text):
        candidate = match.group(0).strip()
        if _is_claim_quote_line(candidate):
            leading = len(match.group(0)) - len(match.group(0).lstrip())
            trailing = len(match.group(0)) - len(match.group(0).rstrip())
            spans.append((match.start() + leading, match.end() - trailing, candidate))
    return spans


def _renumber_claim_cards(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for index, card in enumerate(cards, start=1):
        out.append({**card, "claimId": f"C{index}"})
    return out


def merge_claim_card_ledger(cards: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    ordered_keys: list[tuple[str, str]] = []
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    single_index = 0
    for card in cards:
        key = _claim_card_merge_key(card)
        if key:
            group_key = ("merge", key)
        else:
            single_index += 1
            group_key = ("single", str(single_index))
        if group_key not in grouped:
            ordered_keys.append(group_key)
            grouped[group_key] = []
        grouped[group_key].append(card)

    out: list[dict[str, Any]] = []
    merged_claim_count = 0
    merged_support_count = 0
    for group_key in ordered_keys:
        items = grouped[group_key]
        if group_key[0] != "merge" or len(items) < 2:
            out.extend(dict(item) for item in items)
            continue
        merged_claim_count += 1
        merged_support_count += len(items)
        primary = dict(items[0])
        supporting_claims = [_claim_card_support_item(item) for item in items]
        summaries = _unique_nonempty(item.get("claimSummary") for item in items)
        contexts = _unique_nonempty(item.get("contextSummary") for item in items)
        stances = _unique_nonempty(item.get("stance") for item in items)
        primary["claimSummary"] = " / ".join(summaries)[:1200] or primary.get("claimSummary") or ""
        primary["contextSummary"] = " / ".join(contexts)[:2000] or primary.get("contextSummary") or ""
        primary["stance"] = " / ".join(stances)[:400] or primary.get("stance") or ""
        primary["supportCount"] = len(supporting_claims)
        primary["supportingClaims"] = supporting_claims
        primary["supportingSourceIds"] = _unique_nonempty(item.get("sourceId") for item in items)
        primary["supportingLabels"] = _unique_nonempty(item.get("label") for item in items)
        primary["mergedClaimAxisKey"] = group_key[1]
        primary["mergedFromClaimIds"] = _unique_nonempty(item.get("claimId") for item in items)
        primary["analysisSource"] = str(primary.get("analysisSource") or "") + "_merged"
        out.append(primary)
    return out, {
        "claimAnalyzerPreMergeClaimCount": len(cards),
        "claimAnalyzerPostMergeClaimCount": len(out),
        "claimAnalyzerMergedClaimCount": merged_claim_count,
        "claimAnalyzerMergedSupportCount": merged_support_count,
    }


def _claim_card_merge_key(card: dict[str, Any]) -> str:
    source = str(card.get("analysisSource") or "")
    if not source.startswith("llm_"):
        return ""
    axis = _compact_claim_key(card.get("claimAxis"))
    role = _compact_claim_key(card.get("role"))
    if not axis or axis == role:
        return ""
    return axis


def _compact_claim_key(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).lower()


def _unique_nonempty(values: Iterable[Any]) -> list[str]:
    out: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in out:
            out.append(text)
    return out


def _claim_card_support_item(card: dict[str, Any]) -> dict[str, Any]:
    return {
        "claimId": str(card.get("claimId") or ""),
        "label": str(card.get("label") or ""),
        "sourceId": str(card.get("sourceId") or ""),
        "citation": str(card.get("citation") or ""),
        "role": str(card.get("role") or ""),
        "stance": str(card.get("stance") or ""),
        "contextSummary": str(card.get("contextSummary") or ""),
        "claimSummary": str(card.get("claimSummary") or ""),
        "quote": str(card.get("quote") or ""),
        "span": dict(card.get("span") or {}),
        "sourceChunkId": str(card.get("sourceChunkId") or ""),
        "quoteMatch": str(card.get("quoteMatch") or ""),
    }


def _claim_card_prompt_lines(card: dict[str, Any], *, token_key: str) -> list[str]:
    token_value = f"[{card.get('label')}]" if token_key == "writer_token" else card.get("label")
    lines = [
        f"claim_id: {card.get('claimId')}",
        f"{token_key}: {token_value}",
        f"source_id: {card.get('sourceId')}",
        f"role: {card.get('role')}",
        f"claim_axis: {card.get('claimAxis')}",
        f"stance: {card.get('stance')}",
        f"citation: {card.get('citation')}",
        f"context_summary: {card.get('contextSummary')}",
        f"claim_summary: {card.get('claimSummary')}",
        f"quote: {card.get('quote')}",
    ]
    supporting = [item for item in card.get("supportingClaims") or [] if isinstance(item, dict)]
    if supporting:
        lines.append(f"support_count: {len(supporting)}")
        for item in supporting[1:]:
            label = str(item.get("label") or "")
            source_id = str(item.get("sourceId") or "")
            citation = str(item.get("citation") or source_id)
            quote = str(item.get("quote") or "")
            summary = str(item.get("claimSummary") or "")
            lines.append(f"supporting_source: [{label}] {source_id} {citation}".strip())
            if summary:
                lines.append(f"supporting_summary: [{label}] {summary}")
            if quote:
                lines.append(f"supporting_quote: [{label}] {quote}")
    return lines


def _writer_claim_limit() -> int:
    return _env_int("RELIGION_WRITER_CLAIM_LIMIT", 40, minimum=1, maximum=100)


def _select_claim_cards_for_writer(claim_cards: list[dict[str, Any]], answer_plan: dict[str, Any]) -> list[dict[str, Any]]:
    if not claim_cards:
        return []
    available = _available_claim_ids(claim_cards)
    by_id = _claim_card_by_id(claim_cards)
    raw_ids: list[str] = []
    if isinstance(answer_plan, dict):
        raw_ids.extend(_normalize_claim_id_list(answer_plan.get("bodyClaimIds") or answer_plan.get("body_claim_ids"), available))
        raw_ids.extend(
            _normalize_claim_id_list(
                answer_plan.get("coverageRequiredClaimIds") or answer_plan.get("coverage_required_claim_ids"),
                available,
            )
        )
        raw_ids.extend(
            _claim_ids_referenced_by_plan_parts(
                answer_plan.get("claimGroups") if isinstance(answer_plan.get("claimGroups"), list) else [],
                answer_plan.get("answerOutline") if isinstance(answer_plan.get("answerOutline"), list) else [],
                str(answer_plan.get("citationPolicy") or ""),
                available,
            )
        )
    if not raw_ids:
        raw_ids = _default_body_claim_ids(claim_cards)
    limit = _writer_claim_limit()
    selected_ids = _merge_claim_id_lists(raw_ids, available=available)[:limit]
    if len(selected_ids) < limit:
        selected_ids = _merge_claim_id_lists(selected_ids, available, available=available)[:limit]
    return [by_id[claim_id] for claim_id in selected_ids if claim_id in by_id]


def _filter_answer_plan_for_writer(answer_plan: dict[str, Any], visible_claim_ids: list[str]) -> dict[str, Any]:
    if not isinstance(answer_plan, dict) or not visible_claim_ids:
        return answer_plan if isinstance(answer_plan, dict) else {}
    visible = set(visible_claim_ids)
    filtered = dict(answer_plan)
    for key in ("bodyClaimIds", "body_claim_ids", "coverageRequiredClaimIds", "coverage_required_claim_ids"):
        if key in filtered:
            filtered[key] = [claim_id for claim_id in _normalize_claim_id_list(filtered.get(key), visible_claim_ids) if claim_id in visible]
    raw_groups = filtered.get("claimGroups") or filtered.get("claim_groups")
    if isinstance(raw_groups, list):
        groups = []
        for group in raw_groups:
            if not isinstance(group, dict):
                continue
            ids = [claim_id for claim_id in _normalize_claim_id_list(group.get("claimIds") or group.get("claim_ids"), visible_claim_ids) if claim_id in visible]
            if not ids:
                continue
            groups.append({**group, "claimIds": ids})
        filtered["claimGroups"] = groups
        filtered.pop("claim_groups", None)
    filtered["writerVisibleClaimIds"] = visible_claim_ids[:]
    filtered["writerPromptPolicy"] = "claim/source details are bounded; full selected source windows remain available by citation"
    return filtered


def _select_source_records_for_writer(
    selected_records: list[dict[str, Any]],
    claim_cards: list[dict[str, Any]],
    *,
    limit: int,
) -> list[tuple[int, dict[str, Any]]]:
    if not selected_records:
        return []
    source_ids = _unique_nonempty(card.get("sourceId") for card in claim_cards)
    selected: list[tuple[int, dict[str, Any]]] = []
    seen: set[str] = set()
    by_id = {str(record.get("file_id") or ""): (index, record) for index, record in enumerate(selected_records, start=1)}
    for source_id in source_ids:
        item = by_id.get(source_id)
        if item is None:
            continue
        selected.append(item)
        seen.add(source_id)
        if len(selected) >= limit:
            return selected
    for index, record in enumerate(selected_records, start=1):
        source_id = str(record.get("file_id") or "")
        if source_id in seen:
            continue
        selected.append((index, record))
        if source_id:
            seen.add(source_id)
        if len(selected) >= limit:
            break
    return selected


def render_selected_source_index_for_writer(selected_records: list[dict[str, Any]]) -> str:
    if not selected_records:
        return "(no selected sources)"
    index_limit = _env_int("RELIGION_WRITER_SOURCE_INDEX_LIMIT", 200, minimum=1, maximum=400)
    lines = []
    for index, record in enumerate(selected_records[:index_limit], start=1):
        source_id = str(record.get("file_id") or "")
        label = str(record.get("case_number") or record.get("document_title") or source_id or f"source-{index}")
        kind = str(record.get("doc_type") or record.get("case_type") or "")
        suffix = f" | kind: {kind}" if kind else ""
        lines.append(f"[S{index}] {label} | source_id: {source_id}{suffix}")
    if len(selected_records) > index_limit:
        lines.append(f"... {len(selected_records) - index_limit} more selected source labels omitted from index")
    return "\n".join(lines)


def render_claim_cards_for_writer(claim_cards: list[dict[str, Any]]) -> str:
    if not claim_cards:
        return "(no claim cards built; do not invent claims)"
    blocks = []
    for card in claim_cards:
        lines = _claim_card_prompt_lines(card, token_key="writer_token")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def build_answer_plan_for_claim_cards(
    product: ProductProfile,
    query: str,
    language: str,
    claim_cards: list[dict[str, Any]],
    *,
    llm_client: LLMClient | None,
    model: str,
    cache_root: Path | None = None,
    selector_keywords: list[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    provider = str(getattr(llm_client, "provider", "custom_llm") or "custom_llm") if llm_client else ""
    if not claim_cards:
        plan = _deterministic_answer_plan(
            product,
            query,
            language,
            claim_cards,
            status="skipped",
            mode="empty_claim_plan",
            provider=provider,
            model=model,
            selector_keywords=selector_keywords,
        )
        return plan, _answer_planner_meta(plan)
    if llm_client is None:
        plan = _deterministic_answer_plan(
            product,
            query,
            language,
            claim_cards,
            status="skipped",
            mode="deterministic_claim_order_no_llm",
            provider="",
            model=model,
            selector_keywords=selector_keywords,
        )
        return plan, _answer_planner_meta(plan)

    try:
        messages = build_beta6_answer_plan_messages(
            product,
            query,
            language,
            claim_cards,
            selector_keywords=selector_keywords,
        )
        raw, cache_hit = complete_answer_plan_with_cache(
            product,
            query,
            language,
            llm_client=llm_client,
            model=model,
            messages=messages,
            cache_root=cache_root,
            selector_keywords=selector_keywords,
        )
        parsed = parse_answer_plan_response(raw)
        plan = _coerce_answer_plan(
            product,
            query,
            language,
            claim_cards,
            parsed,
            status="completed",
            mode="llm_answer_planner",
            provider=provider,
            model=model,
            selector_keywords=selector_keywords,
        )
        plan["cacheHit"] = cache_hit
        if not plan.get("bodyClaimIds"):
            plan = _deterministic_answer_plan(
                product,
                query,
                language,
                claim_cards,
                status="fallback_empty",
                mode="deterministic_claim_order_after_empty_llm_plan",
                provider=provider,
                model=model,
                selector_keywords=selector_keywords,
            )
            plan["cacheHit"] = cache_hit
    except Exception as exc:
        plan = _deterministic_answer_plan(
            product,
            query,
            language,
            claim_cards,
            status="fallback_error",
            mode="deterministic_claim_order_after_planner_error",
            provider=provider,
            model=model,
            error=str(exc),
            selector_keywords=selector_keywords,
        )
        plan["cacheHit"] = False
    return plan, _answer_planner_meta(plan)


def complete_answer_plan_with_cache(
    product: ProductProfile,
    query: str,
    language: str,
    *,
    llm_client: LLMClient,
    model: str,
    messages: list[dict[str, str]],
    cache_root: Path | None,
    selector_keywords: list[str] | None = None,
) -> tuple[str, bool]:
    payload = {
        "cacheVersion": "beta6-answer-plan-v2-selector-context",
        "product": product.key,
        "query": query,
        "language": language,
        "model": model or "",
        "timeoutSeconds": _answer_planner_timeout_seconds(),
        "selectorKeywords": _coerce_string_list(selector_keywords or [])[:40],
        "messages": messages,
    }

    def produce() -> dict[str, Any]:
        return {
            "raw": _complete_llm(
                llm_client,
                messages,
                model=model,
                timeout_seconds=_answer_planner_timeout_seconds(),
            )
        }

    value, cache_hit = _read_or_fill_batch_cache("answer_plan", payload, produce, cache_root=cache_root)
    return str(value.get("raw") or ""), cache_hit


def build_beta6_answer_plan_messages(
    product: ProductProfile,
    query: str,
    language: str,
    claim_cards: list[dict[str, Any]],
    *,
    selector_keywords: list[str] | None = None,
) -> list[dict[str, str]]:
    card_limit = _env_int("RELIGION_ANSWER_PLANNER_CLAIM_LIMIT", 80, minimum=1, maximum=200)
    cards = []
    for card in claim_cards[:card_limit]:
        cards.append("\n".join(_claim_card_prompt_lines(card, token_key="source_label")))
    learned_keywords = _coerce_string_list(selector_keywords or [])[:40]
    selector_block = (
        "Selector learned keywords/context:\n"
        + "\n".join(f"- {keyword}" for keyword in learned_keywords)
        + "\n\n"
        if learned_keywords
        else ""
    )
    user = (
        "Create the beta-6 answer plan before the writer drafts the final answer.\n"
        "Rules:\n"
        f"{_answer_planner_policy(product.key)}\n"
        "- Return JSON only.\n"
        "- Choose claim ids that must appear in the answer body; do not invent ids.\n"
        "- If a claim id appears in claim_groups, answer_outline, or citation_policy, include that id in body_claim_ids and coverage_required_claim_ids.\n"
        "- coverage_required_claim_ids must include every claim id the writer must cover or explicitly mark as a retrieval gap.\n"
        "- Keep source authority, role diversity, and safety limits visible in the plan.\n"
        'Schema: {"body_claim_ids":["C1"],"coverage_required_claim_ids":["C1"],'
        '"claim_groups":[{"title":"...","claim_ids":["C1"],"summary":"..."}],'
        '"answer_outline":["..."],"citation_policy":"..."}\n\n'
        f"Answer language hint: {language}\n"
        f"User question:\n{query}\n\n"
        f"{selector_block}"
        "Claim cards:\n"
        + "\n\n".join(cards or ["(no claim cards)"])
    )
    return [
        {"role": "system", "content": f"Gemma 4 beta-6 answer planner for {product.name}. JSON only."},
        {"role": "user", "content": user},
    ]


def _answer_planner_policy(product_key: str) -> str:
    return get_domain_adapter(product_key).answer_planner_policy()


def parse_answer_plan_response(text: str) -> dict[str, Any]:
    raw = str(text or "").strip()
    try:
        parsed = json.loads(_extract_json_block(raw))
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _coerce_answer_plan(
    product: ProductProfile,
    query: str,
    language: str,
    claim_cards: list[dict[str, Any]],
    parsed: dict[str, Any],
    *,
    status: str,
    mode: str,
    provider: str,
    model: str,
    selector_keywords: list[str] | None = None,
) -> dict[str, Any]:
    available = _available_claim_ids(claim_cards)
    body_claim_ids = _normalize_claim_id_list(
        parsed.get("body_claim_ids") or parsed.get("bodyClaimIds") or parsed.get("bodyClaims"),
        available,
    )
    coverage_ids = _normalize_claim_id_list(
        parsed.get("coverage_required_claim_ids")
        or parsed.get("coverageRequiredClaimIds")
        or parsed.get("required_claim_ids")
        or parsed.get("requiredClaimIds"),
        available,
    )
    groups = _coerce_claim_groups(parsed.get("claim_groups") or parsed.get("claimGroups"), available)
    outline = _coerce_string_list(parsed.get("answer_outline") or parsed.get("answerOutline"))
    if not outline:
        outline = _default_answer_outline(product, language)
    citation_policy = str(parsed.get("citation_policy") or parsed.get("citationPolicy") or "").strip()
    if not citation_policy:
        citation_policy = _default_citation_policy(language)
    referenced_ids = _claim_ids_referenced_by_plan_parts(groups, outline, citation_policy, available)
    if body_claim_ids:
        body_claim_ids = _merge_claim_id_lists(body_claim_ids, referenced_ids, available=available)
    else:
        body_claim_ids = referenced_ids or _default_body_claim_ids(claim_cards)
    if coverage_ids:
        coverage_ids = _merge_claim_id_lists(coverage_ids, body_claim_ids, referenced_ids, available=available)
    else:
        coverage_ids = body_claim_ids[:]
    body_claim_ids = _filter_answer_plan_claim_ids_by_relevance(
        product,
        query,
        body_claim_ids,
        claim_cards,
        selector_keywords=selector_keywords,
    )
    coverage_ids = _filter_answer_plan_claim_ids_by_relevance(
        product,
        query,
        coverage_ids,
        claim_cards,
        selector_keywords=selector_keywords,
    )
    body_claim_ids = _extend_answer_plan_claim_ids_to_minimum(
        product,
        query,
        body_claim_ids,
        claim_cards,
        available,
        selector_keywords=selector_keywords,
    )
    coverage_ids = _extend_answer_plan_claim_ids_to_minimum(
        product,
        query,
        coverage_ids,
        claim_cards,
        available,
        selector_keywords=selector_keywords,
    )
    groups = _filter_claim_groups_to_plan_ids(groups, _merge_claim_id_lists(body_claim_ids, coverage_ids, available=available))
    if not groups and body_claim_ids:
        groups = [
            {
                "title": _localized_plan_group_title(language),
                "claimIds": body_claim_ids[:],
                "summary": _localized_plan_group_summary(product, language),
            }
        ]
    return {
        "status": status,
        "mode": mode,
        "provider": provider,
        "model": model or "",
        "bodyClaimIds": body_claim_ids,
        "coverageRequiredClaimIds": coverage_ids,
        "claimGroups": groups,
        "answerOutline": outline,
        "citationPolicy": citation_policy,
        "sourceClaimCount": len(claim_cards),
        "query": query,
        "language": language,
        "selectorKeywords": _coerce_string_list(selector_keywords or [])[:40],
    }


def _deterministic_answer_plan(
    product: ProductProfile,
    query: str,
    language: str,
    claim_cards: list[dict[str, Any]],
    *,
    status: str,
    mode: str,
    provider: str,
    model: str,
    error: str = "",
    selector_keywords: list[str] | None = None,
) -> dict[str, Any]:
    available = _available_claim_ids(claim_cards)
    body_claim_ids = _extend_answer_plan_claim_ids_to_minimum(
        product,
        query,
        [],
        claim_cards,
        available,
        selector_keywords=selector_keywords,
    )
    if not body_claim_ids:
        body_claim_ids = _default_body_claim_ids(claim_cards)
    plan = {
        "status": status,
        "mode": mode,
        "provider": provider,
        "model": model or "",
        "bodyClaimIds": body_claim_ids,
        "coverageRequiredClaimIds": body_claim_ids[:],
        "claimGroups": [
            {
                "title": _localized_plan_group_title(language),
                "claimIds": body_claim_ids[:],
                "summary": _localized_plan_group_summary(product, language),
            }
        ]
        if body_claim_ids
        else [],
        "answerOutline": _default_answer_outline(product, language),
        "citationPolicy": _default_citation_policy(language),
        "sourceClaimCount": len(claim_cards),
        "query": query,
        "language": language,
        "selectorKeywords": _coerce_string_list(selector_keywords or [])[:40],
    }
    if error:
        plan["error"] = error
    return plan


def render_answer_plan_for_writer(answer_plan: dict[str, Any]) -> str:
    if not answer_plan:
        return "(no answer plan; cover the strongest selected claim cards without inventing claims)"
    lines = [
        f"status: {answer_plan.get('status')}",
        f"mode: {answer_plan.get('mode')}",
        "body_claim_ids: " + ", ".join(answer_plan.get("bodyClaimIds") or []),
        "coverage_required_claim_ids: " + ", ".join(answer_plan.get("coverageRequiredClaimIds") or []),
        f"citation_policy: {answer_plan.get('citationPolicy') or ''}",
    ]
    selector_keywords = _coerce_string_list(answer_plan.get("selectorKeywords") or [])
    if selector_keywords:
        lines.append("selector_learned_keywords: " + ", ".join(selector_keywords[:24]))
    outline = answer_plan.get("answerOutline") if isinstance(answer_plan.get("answerOutline"), list) else []
    if outline:
        lines.append("answer_outline:")
        lines.extend(f"- {item}" for item in outline[:12])
    groups = answer_plan.get("claimGroups") if isinstance(answer_plan.get("claimGroups"), list) else []
    if groups:
        lines.append("claim_groups:")
        for group in groups[:12]:
            if not isinstance(group, dict):
                continue
            ids = ", ".join(group.get("claimIds") or [])
            lines.append(f"- {group.get('title') or 'group'}: {ids} :: {group.get('summary') or ''}")
    lines.append(
        "Writer must cover every coverage_required_claim_id in the body or state why selected evidence is insufficient. "
        "Use [C#] or the linked [S#] citation labels."
    )
    return "\n".join(lines)


def apply_answer_coverage_patch(
    product: ProductProfile,
    answer: str,
    claim_cards: list[dict[str, Any]],
    answer_plan: dict[str, Any],
    *,
    language: str,
) -> tuple[str, dict[str, Any]]:
    report = build_coverage_report(product, answer, claim_cards, answer_plan, language=language, apply_patch=True)
    patched = str(answer or "").rstrip()
    coverage_patched = False
    if report.get("missingClaimIds"):
        supplement = render_coverage_supplement(product, claim_cards, report["missingClaimIds"], language=language)
        if supplement:
            if patched:
                patched += "\n\n"
            patched += supplement
            coverage_patched = True
    min_chars = _min_answer_chars(product)
    depth_patched = False
    if min_chars and len(patched) < min_chars:
        depth_supplement = render_answer_depth_supplement(
            product,
            claim_cards,
            answer_plan,
            language=language,
            current_chars=len(patched),
            min_chars=min_chars,
        )
        if depth_supplement:
            if patched:
                patched += "\n\n"
            patched += depth_supplement
            depth_patched = True
    return patched, {
        **report,
        "patched": coverage_patched or depth_patched,
        "coveragePatched": coverage_patched,
        "depthPatched": depth_patched,
        "shortAnswerChars": len(str(answer or "")),
        "minAnswerChars": min_chars,
    }


def build_coverage_report(
    product: ProductProfile,
    answer: str,
    claim_cards: list[dict[str, Any]],
    answer_plan: dict[str, Any],
    *,
    language: str,
    apply_patch: bool,
) -> dict[str, Any]:
    del product, language
    checked = _coverage_claim_ids(answer_plan, claim_cards)
    by_id = _claim_card_by_id(claim_cards)
    covered: list[str] = []
    missing: list[str] = []
    for claim_id in checked:
        card = by_id.get(claim_id)
        if _answer_covers_claim(answer, claim_id, card):
            covered.append(claim_id)
        else:
            missing.append(claim_id)
    return {
        "status": "completed" if apply_patch else "skipped",
        "mode": "deterministic_claim_coverage_supplement",
        "checkedClaimIds": checked,
        "coveredClaimIds": covered,
        "missingClaimIds": missing,
        "patched": False,
    }


def split_claim_cards_for_handoff(
    product: ProductProfile,
    answer: str,
    claim_cards: list[dict[str, Any]],
    answer_plan: dict[str, Any],
) -> dict[str, Any]:
    del product
    by_id = _claim_card_by_id(claim_cards)
    candidate_ids = _candidate_claim_ids_from_plan(answer_plan, claim_cards)
    cited_ids = _cited_claim_ids_from_answer(answer, claim_cards)
    candidate_cards = [by_id[claim_id] for claim_id in candidate_ids if claim_id in by_id]
    cited_cards = [by_id[claim_id] for claim_id in cited_ids if claim_id in by_id]
    uncited_candidate_ids = [claim_id for claim_id in candidate_ids if claim_id not in set(cited_ids)]
    return {
        "candidateClaimIds": candidate_ids,
        "citedClaimIds": cited_ids,
        "uncitedCandidateClaimIds": uncited_candidate_ids,
        "candidateClaimCards": candidate_cards,
        "citedClaimCards": cited_cards,
        "uncitedCandidateClaimCards": [by_id[claim_id] for claim_id in uncited_candidate_ids if claim_id in by_id],
    }


def _candidate_claim_ids_from_plan(answer_plan: dict[str, Any], claim_cards: list[dict[str, Any]]) -> list[str]:
    available = _available_claim_ids(claim_cards)
    raw: list[Any] = []
    if isinstance(answer_plan, dict):
        for key in ("bodyClaimIds", "coverageRequiredClaimIds"):
            values = answer_plan.get(key)
            if isinstance(values, list):
                raw.extend(values)
            elif isinstance(values, str):
                raw.extend(re.split(r"[\s,;]+", values))
    candidate_ids = _normalize_claim_id_list(raw, available)
    return candidate_ids or _default_body_claim_ids(claim_cards)


def _cited_claim_ids_from_answer(answer: str, claim_cards: list[dict[str, Any]]) -> list[str]:
    by_id = _claim_card_by_id(claim_cards)
    by_label = {
        str(card.get("label") or "").strip().upper(): str(card.get("claimId") or "").strip().upper()
        for card in claim_cards
        if card.get("label") and card.get("claimId")
    }
    cited: list[str] = []
    for bracket in re.findall(r"\[([^\]]+)\]", str(answer or ""), flags=re.IGNORECASE):
        for match in re.finditer(r"(?<![A-Za-z0-9])([CS])\s*0*(\d{1,5})(?![A-Za-z0-9])", bracket, flags=re.IGNORECASE):
            normalized = f"{match.group(1).upper()}{int(match.group(2))}"
            claim_id = normalized if normalized in by_id else by_label.get(normalized, "")
            if claim_id and claim_id in by_id and claim_id not in cited:
                cited.append(claim_id)
    return cited


def render_coverage_supplement(
    product: ProductProfile,
    claim_cards: list[dict[str, Any]],
    missing_claim_ids: list[str],
    *,
    language: str,
) -> str:
    by_id = _claim_card_by_id(claim_cards)
    heading = _coverage_heading(language)
    lines = [heading]
    for claim_id in missing_claim_ids:
        card = by_id.get(claim_id)
        if not card:
            continue
        label = str(card.get("label") or "")
        citation = str(card.get("citation") or card.get("sourceId") or "")
        context = str(card.get("contextSummary") or "").strip()
        summary = str(card.get("claimSummary") or "").strip()
        quote = " ".join(str(card.get("quote") or "").split())[:360]
        if language == "ko":
            line = f"- [{claim_id}] {summary} [{claim_id}]"
            if label:
                line += f" [{label}]"
            if context:
                line += f" 문맥: {context}"
            if citation:
                line += f" 출처: {citation}."
            if quote:
                line += f" 원문: \"{quote}\""
        elif language == "ar":
            line = f"- [{claim_id}] {summary} [{claim_id}]"
            if label:
                line += f" [{label}]"
            if context:
                line += f" السياق: {context}"
            if citation:
                line += f" المصدر: {citation}."
            if quote:
                line += f" النص: \"{quote}\""
        else:
            line = f"- [{claim_id}] {summary} [{claim_id}]"
            if label:
                line += f" [{label}]"
            if context:
                line += f" Context: {context}"
            if citation:
                line += f" Source: {citation}."
            if quote:
                line += f" Quote: \"{quote}\""
        lines.append(line)
    if product.key == "islam" and language == "ko":
        lines.append("이 보강은 누락된 선택 근거를 본문에 연결한 것이며, 구속력 있는 파트와가 아닙니다.")
    return "\n".join(lines).rstrip()


def render_answer_depth_supplement(
    product: ProductProfile,
    claim_cards: list[dict[str, Any]],
    answer_plan: dict[str, Any],
    *,
    language: str,
    current_chars: int,
    min_chars: int,
) -> str:
    claim_ids = _coverage_claim_ids(answer_plan, claim_cards)
    if not claim_ids:
        return ""
    limit = _env_int("RELIGION_ANSWER_DEPTH_SUPPLEMENT_CLAIMS", 8, minimum=1, maximum=24)
    by_id = _claim_card_by_id(claim_cards)
    heading = _depth_heading(language)
    lines = [heading]
    if language == "ko":
        lines.append(
            f"초안 답변이 짧아 선택된 근거의 문맥을 더 붙입니다"
            f"({current_chars}/{min_chars}자). 아래 내용은 새 결론이 아니라 이미 선택된 claim 카드의 요약입니다."
        )
    elif language == "ar":
        lines.append(
            f"كان الجواب المختصر أقصر من حد التفصيل ({current_chars}/{min_chars}). "
            "ما يلي تلخيص إضافي لبطاقات الادعاء المختارة، وليس حكما جديدا."
        )
    else:
        lines.append(
            f"The draft answer was shorter than the detail floor ({current_chars}/{min_chars} chars). "
            "The following adds context from already selected claim cards; it is not a new conclusion."
        )
    for claim_id in claim_ids[:limit]:
        card = by_id.get(claim_id)
        if not card:
            continue
        label = str(card.get("label") or "")
        citation = str(card.get("citation") or card.get("sourceId") or "")
        context = " ".join(str(card.get("contextSummary") or "").split())[:260]
        summary = " ".join(str(card.get("claimSummary") or "").split())[:260]
        quote = " ".join(str(card.get("quote") or "").split())[:280]
        if language == "ko":
            line = f"- [{claim_id}] {summary} [{claim_id}]"
            if label:
                line += f" [{label}]"
            if context:
                line += f" 문맥: {context}"
            if citation:
                line += f" 출처: {citation}."
            if quote:
                line += f" 원문 핵심: \"{quote}\""
        elif language == "ar":
            line = f"- [{claim_id}] {summary} [{claim_id}]"
            if label:
                line += f" [{label}]"
            if context:
                line += f" السياق: {context}"
            if citation:
                line += f" المصدر: {citation}."
            if quote:
                line += f" النص المحوري: \"{quote}\""
        else:
            line = f"- [{claim_id}] {summary} [{claim_id}]"
            if label:
                line += f" [{label}]"
            if context:
                line += f" Context: {context}"
            if citation:
                line += f" Source: {citation}."
            if quote:
                line += f" Key source text: \"{quote}\""
        lines.append(line)
    if product.key == "islam" and language == "ko":
        lines.append("이 상세 보강 역시 선택된 원문 근거를 풀어쓴 학습용 정리이며, 구속력 있는 파트와나 최종 판결이 아닙니다.")
    return "\n".join(lines).rstrip()


def _coverage_heading(language: str) -> str:
    if language == "ko":
        return "### 누락 근거 보강"
    if language == "ar":
        return "### استكمال الأدلة الناقصة"
    return "### Missing Evidence Supplement"


def _depth_heading(language: str) -> str:
    if language == "ko":
        return "### 선택 근거 상세"
    if language == "ar":
        return "### تفصيل الأدلة المختارة"
    return "### Selected Evidence Detail"


def _min_answer_chars(product: ProductProfile) -> int:
    default = get_domain_adapter(product).min_answer_chars_default()
    generic = _env_int("RELIGION_MIN_ANSWER_CHARS", default, minimum=0, maximum=12000)
    env_name = f"RELIGION_{product.key.upper()}_MIN_ANSWER_CHARS"
    return _env_int(env_name, generic, minimum=0, maximum=12000)


def _coverage_claim_ids(answer_plan: dict[str, Any], claim_cards: list[dict[str, Any]]) -> list[str]:
    available = _available_claim_ids(claim_cards)
    raw = answer_plan.get("coverageRequiredClaimIds") or answer_plan.get("bodyClaimIds") if answer_plan else []
    ids = _normalize_claim_id_list(raw, available)
    if not ids:
        ids = _default_body_claim_ids(claim_cards)
    limit = _env_int("RELIGION_COVERAGE_CLAIM_LIMIT", 12, minimum=1, maximum=80)
    return ids[:limit]


def _answer_covers_claim(answer: str, claim_id: str, card: dict[str, Any] | None) -> bool:
    text = str(answer or "")
    if re.search(rf"(?<![A-Za-z0-9])\[?{re.escape(claim_id)}\]?(?![A-Za-z0-9])", text):
        return True
    if card:
        label = str(card.get("label") or "")
        if label and re.search(rf"(?<![A-Za-z0-9])\[?{re.escape(label)}\]?(?![A-Za-z0-9])", text):
            return True
        summary = " ".join(str(card.get("claimSummary") or "").split())
        if len(summary) >= 24 and summary[:80] in " ".join(text.split()):
            return True
    return False


def _available_claim_ids(claim_cards: list[dict[str, Any]]) -> list[str]:
    ids: list[str] = []
    for card in claim_cards:
        claim_id = str(card.get("claimId") or "").strip().upper()
        if claim_id and claim_id not in ids:
            ids.append(claim_id)
    return ids


def _claim_card_by_id(claim_cards: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(card.get("claimId") or "").strip().upper(): card for card in claim_cards if card.get("claimId")}


def _normalize_claim_id_list(raw: Any, available: list[str]) -> list[str]:
    if isinstance(raw, str):
        values = re.split(r"[\s,;]+", raw)
    elif isinstance(raw, list):
        values = raw
    else:
        values = []
    allowed = set(available)
    out: list[str] = []
    for value in values:
        claim_id = str(value or "").strip().upper()
        if not claim_id or claim_id not in allowed or claim_id in out:
            continue
        out.append(claim_id)
    return out


def _merge_claim_id_lists(*lists: list[str], available: list[str]) -> list[str]:
    allowed = set(available)
    merged: list[str] = []
    for values in lists:
        for value in values:
            claim_id = str(value or "").strip().upper()
            if claim_id and claim_id in allowed and claim_id not in merged:
                merged.append(claim_id)
    return merged


def _claim_ids_referenced_by_plan_parts(
    groups: list[dict[str, Any]],
    outline: list[str],
    citation_policy: str,
    available: list[str],
) -> list[str]:
    raw: list[str] = []
    for group in groups:
        raw.extend(str(value or "") for value in (group.get("claimIds") or []))
        raw.append(str(group.get("title") or ""))
        raw.append(str(group.get("summary") or ""))
    raw.extend(str(item or "") for item in outline)
    raw.append(str(citation_policy or ""))
    mentioned: list[str] = []
    for text in raw:
        for match in re.finditer(r"(?<![A-Za-z0-9])C\s*0*(\d{1,5})(?![A-Za-z0-9])", text, flags=re.IGNORECASE):
            mentioned.append(f"C{int(match.group(1))}")
    return _normalize_claim_id_list(mentioned, available)


def _coerce_claim_groups(raw: Any, available: list[str]) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    groups: list[dict[str, Any]] = []
    for group in raw:
        if not isinstance(group, dict):
            continue
        ids = _normalize_claim_id_list(group.get("claim_ids") or group.get("claimIds"), available)
        if not ids:
            continue
        groups.append(
            {
                "title": str(group.get("title") or group.get("name") or "claim group").strip(),
                "claimIds": ids,
                "summary": str(group.get("summary") or "").strip(),
            }
        )
    return groups


def _coerce_string_list(raw: Any) -> list[str]:
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return []
    return [str(item).strip() for item in raw if str(item or "").strip()]


def _default_body_claim_ids(claim_cards: list[dict[str, Any]]) -> list[str]:
    limit = _env_int("RELIGION_ANSWER_PLAN_BODY_CLAIMS", 12, minimum=1, maximum=80)
    return _available_claim_ids(claim_cards)[:limit]


def _selector_keywords_from_meta(selector: dict[str, Any]) -> list[str]:
    raw = selector.get("keywords") if isinstance(selector, dict) else []
    if not isinstance(raw, list):
        return []
    return _coerce_string_list(raw)[:80]


def _extend_answer_plan_claim_ids_to_minimum(
    product: ProductProfile,
    query: str,
    claim_ids: list[str],
    claim_cards: list[dict[str, Any]],
    available: list[str],
    *,
    selector_keywords: list[str] | None = None,
) -> list[str]:
    minimum = _answer_plan_min_body_claims(product)
    if minimum <= 0 or len(claim_ids) >= minimum:
        return claim_ids
    ranked_relevant = _rank_claim_ids_for_answer_plan(
        product,
        query,
        claim_cards,
        available,
        selector_keywords=selector_keywords,
    )
    default_ids = ranked_relevant or _default_body_claim_ids(claim_cards)
    target = max(minimum, len(claim_ids))
    merged = _merge_claim_id_lists(claim_ids, default_ids, available=available)
    if ranked_relevant:
        relevant = set(ranked_relevant)
        merged = [claim_id for claim_id in merged if claim_id in relevant]
    return merged[:target]


def _filter_answer_plan_claim_ids_by_relevance(
    product: ProductProfile,
    query: str,
    claim_ids: list[str],
    claim_cards: list[dict[str, Any]],
    *,
    selector_keywords: list[str] | None = None,
) -> list[str]:
    if not claim_ids:
        return []
    available = _available_claim_ids(claim_cards)
    relevant_ids = set(
        _rank_claim_ids_for_answer_plan(
            product,
            query,
            claim_cards,
            available,
            selector_keywords=selector_keywords,
        )
    )
    if not relevant_ids:
        return claim_ids
    return [claim_id for claim_id in claim_ids if claim_id in relevant_ids]


def _rank_claim_ids_for_answer_plan(
    product: ProductProfile,
    query: str,
    claim_cards: list[dict[str, Any]],
    available: list[str],
    *,
    selector_keywords: list[str] | None = None,
) -> list[str]:
    terms = _answer_plan_relevance_terms(product, query, selector_keywords)
    if not terms:
        return []
    by_id = _claim_card_by_id(claim_cards)
    scored: list[tuple[float, int, str]] = []
    for index, claim_id in enumerate(available):
        card = by_id.get(claim_id)
        if not card:
            continue
        score = _answer_plan_claim_relevance_score(card, terms)
        if score > 0:
            scored.append((score, index, claim_id))
    scored.sort(key=lambda item: (-item[0], item[1], item[2]))
    return [claim_id for _score, _index, claim_id in scored]


def _answer_plan_relevance_terms(
    product: ProductProfile,
    query: str,
    selector_keywords: list[str] | None,
) -> list[str]:
    keywords = _coerce_string_list(selector_keywords or [])
    if not keywords:
        return []
    adapter = get_domain_adapter(product)
    stop = adapter.answer_plan_relevance_stopwords()
    terms: list[str] = []
    seen: set[str] = set()
    for term in _beta6_frontier_terms(product, query, keywords):
        normalized = " ".join(str(term or "").lower().split())
        if adapter.answer_plan_term_too_short(normalized) or normalized in stop or normalized in seen:
            continue
        seen.add(normalized)
        terms.append(normalized)
    for alias in adapter.answer_plan_relevance_aliases(terms):
        normalized = " ".join(str(alias or "").lower().split())
        if adapter.answer_plan_term_too_short(normalized) or normalized in stop or normalized in seen:
            continue
        seen.add(normalized)
        terms.append(normalized)
    return terms[:120]


def _answer_plan_term_too_short(product: ProductProfile, normalized: str) -> bool:
    return get_domain_adapter(product).answer_plan_term_too_short(normalized)


def _answer_plan_relevance_aliases(product: ProductProfile, terms: list[str]) -> list[str]:
    return get_domain_adapter(product).answer_plan_relevance_aliases(terms)


def _answer_plan_claim_relevance_score(card: dict[str, Any], terms: list[str]) -> float:
    raw_haystack = " ".join(
        str(card.get(key) or "")
        for key in (
            "citation",
            "role",
            "claimAxis",
            "stance",
            "contextSummary",
            "claimSummary",
            "quote",
            "school",
            "tradition",
            "sourceKind",
        )
    ).lower()
    haystack = f"{raw_haystack} {_normalize_arabic_for_match(raw_haystack)}"
    score = 0.0
    for term in terms:
        normalized_term = _normalize_arabic_for_match(term)
        if not term or (term not in haystack and normalized_term not in haystack):
            continue
        score += 8.0 if " " in term else 3.0
    return score


_ARABIC_MARKS_RE = re.compile(r"[\u064b-\u065f\u0670\u06d6-\u06ed]")


def _normalize_arabic_for_match(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(text or "").lower())
    normalized = _ARABIC_MARKS_RE.sub("", normalized)
    return (
        normalized.replace("ٱ", "ا")
        .replace("أ", "ا")
        .replace("إ", "ا")
        .replace("آ", "ا")
        .replace("ى", "ي")
        .replace("ؤ", "و")
        .replace("ئ", "ي")
    )


def _filter_claim_groups_to_plan_ids(groups: list[dict[str, Any]], claim_ids: list[str]) -> list[dict[str, Any]]:
    if not groups or not claim_ids:
        return []
    allowed = set(claim_ids)
    filtered: list[dict[str, Any]] = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        ids = [
            claim_id
            for claim_id in _coerce_string_list(group.get("claimIds") or group.get("claim_ids") or [])
            if claim_id in allowed
        ]
        if not ids:
            continue
        filtered.append({**group, "claimIds": ids})
    return filtered


def _answer_plan_min_body_claims(product: ProductProfile) -> int:
    defaults = {"islam": 10, "tcm": 10, "simli": 8, "buddhist": 8, "catholic": 8, "hindu": 8}
    generic = _env_int("RELIGION_ANSWER_PLAN_MIN_BODY_CLAIMS", defaults.get(product.key, 0), minimum=0, maximum=80)
    env_name = f"RELIGION_{product.key.upper()}_ANSWER_PLAN_MIN_BODY_CLAIMS"
    return _env_int(env_name, generic, minimum=0, maximum=80)


def _localized_plan_group_title(language: str) -> str:
    if language == "ko":
        return "핵심 선택 근거"
    if language == "ar":
        return "الأدلة المختارة الأساسية"
    return "Core selected evidence"


def _localized_plan_group_summary(product: ProductProfile, language: str) -> str:
    if language == "ko":
        return f"{product.name} 답변 본문에서 빠뜨리면 안 되는 선택 claim 묶음입니다."
    if language == "ar":
        return f"مجموعة ادعاءات مختارة يجب أن تظهر في جواب {product.name}."
    return f"Selected claim cards that the {product.name} answer should not omit."


def _default_answer_outline(product: ProductProfile, language: str) -> list[str]:
    return get_domain_adapter(product).default_answer_outline(language)


def _default_citation_policy(language: str) -> str:
    if language == "ko":
        return "본문의 실질 주장마다 선택 claim 또는 source label을 붙인다."
    if language == "ar":
        return "تضاف إحالة claim أو source لكل فقرة ذات ادعاء جوهري."
    return "Cite selected claim or source labels for each substantive paragraph."


def _answer_planner_meta(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": plan.get("status", ""),
        "mode": plan.get("mode", ""),
        "provider": plan.get("provider", ""),
        "model": plan.get("model", ""),
        "bodyClaimCount": len(plan.get("bodyClaimIds") or []),
        "coverageRequiredCount": len(plan.get("coverageRequiredClaimIds") or []),
        "cacheHit": bool(plan.get("cacheHit")),
    }


def build_passage_windows(selected_records: list[dict[str, Any]], claim_cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {str(record.get("file_id") or ""): str(record.get("extracted_text") or "") for record in selected_records}
    windows: list[dict[str, Any]] = []
    radius = _env_int("RELIGION_PASSAGE_WINDOW_CHARS", 900, minimum=240, maximum=4000)
    for card in claim_cards:
        source_id = str(card.get("sourceId") or "")
        full_text = by_id.get(source_id, "")
        span = card.get("span") if isinstance(card.get("span"), dict) else {}
        start = int(span.get("start") or 0)
        end = int(span.get("end") or start)
        window_start = max(0, start - radius // 2)
        window_end = min(len(full_text), end + radius // 2)
        window_text = full_text[window_start:window_end]
        windows.append(
            {
                "claimId": card.get("claimId") or "",
                "sourceId": source_id,
                "windowStart": window_start,
                "windowEnd": window_end,
                "text": window_text,
                "highlightStart": max(0, start - window_start),
                "highlightEnd": max(0, end - window_start),
                "hasBefore": window_start > 0,
                "hasAfter": window_end < len(full_text),
            }
        )
    return windows


def _extract_claim_quote(full_text: str) -> tuple[str, int, int]:
    text = str(full_text or "")
    quote, start, end = _extract_original_claim_span(text)
    if quote:
        return quote, start, end
    fallback_start = len(text) - len(text.lstrip())
    quote = text[fallback_start:fallback_start + 520].strip()
    return quote, fallback_start, fallback_start + len(quote)


def _extract_original_claim_span(text: str) -> tuple[str, int, int]:
    first_start: int | None = None
    last_end = 0
    for match in re.finditer(r"[^\r\n]+", text or ""):
        raw = match.group(0)
        stripped = raw.strip()
        if not stripped:
            if first_start is not None:
                break
            continue
        if not _is_claim_quote_line(stripped):
            if first_start is not None:
                break
            continue
        line_start = match.start() + (len(raw) - len(raw.lstrip()))
        line_end = match.end() - (len(raw) - len(raw.rstrip()))
        if first_start is None:
            first_start = line_start
        last_end = line_end
        if last_end - first_start >= 520:
            last_end = first_start + 520
            break
    if first_start is None:
        return "", 0, 0
    quote = text[first_start:last_end].strip()
    end = first_start + len(quote)
    return quote, first_start, end


def _is_claim_quote_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    lowered = stripped.lower()
    if lowered in {"[meta]", "[heading]"}:
        return False
    if lowered.startswith("[primary text") or lowered.startswith("[context window"):
        return False
    if re.match(r"^[a-z_]+[ \t]*:", lowered):
        return False
    return True


def _source_role_from_payload(product: ProductProfile, record: dict[str, Any], evidence: dict[str, Any]) -> str:
    metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
    row = SearchResult(
        canonical_id=str(record.get("file_id") or evidence.get("id") or ""),
        title=str(record.get("document_title") or evidence.get("title") or ""),
        citation=str(evidence.get("citation") or record.get("case_number") or ""),
        authority_body=str(evidence.get("authorityBody") or ""),
        source_date="",
        case_name=str(record.get("case_name") or evidence.get("topic") or ""),
        case_type=str(record.get("doc_type") or evidence.get("type") or ""),
        full_text=str(record.get("extracted_text") or evidence.get("excerpt") or ""),
        source_dataset=str(evidence.get("dataset") or record.get("source_group") or ""),
        source_path=str(record.get("relative_path") or evidence.get("path") or ""),
        tradition=str(evidence.get("tradition") or metadata.get("tradition") or ""),
        school=str(evidence.get("school") or metadata.get("school") or ""),
        source_kind=str(evidence.get("sourceKind") or metadata.get("sourceKind") or ""),
        authority_level=int(evidence.get("authorityLevel") or metadata.get("authorityLevel") or 0),
    )
    return _source_role(product, row)


def _claim_context_summary(product: ProductProfile, citation: str, role: str, *, language: str) -> str:
    if language == "ko":
        return f"{citation}에서 이 인용문이 포함된 더 큰 원문 단락의 맥락입니다."
    if language == "ar":
        return f"{citation} هو سياق المصدر الأوسع الذي يضم هذا الاقتباس."
    return f"{citation} is the larger source context containing this quote."


def _claim_summary(product: ProductProfile, query: str, quote: str, role: str, *, language: str) -> str:
    preview = " ".join(str(quote or "").split())[:180]
    if language == "ko":
        return f"원문 안에서 이 인용문은 다음 내용을 직접 말합니다: '{preview}'"
    if language == "ar":
        return f"يقول هذا الاقتباس في سياقه الأصلي: {preview}"
    return f"In its original source context, this quote says: {preview}"


def grounded_fallback_answer(product: ProductProfile, rows: list[SearchResult], *, language: str) -> str:
    selected = _label_selected_evidence([_result_payload(row) for row in rows])
    return writer_required_markdown(product, selected, language=language)


def _deterministic_writer_fallback_answer(
    product: ProductProfile,
    query: str,
    selected_records: list[dict[str, Any]],
    claim_cards: list[dict[str, Any]],
    *,
    language: str,
    error: str,
) -> str:
    domain_fallback = get_domain_adapter(product).deterministic_writer_fallback_answer(
        query,
        selected_records,
        claim_cards,
        language=language,
        error=error,
    )
    if domain_fallback:
        return domain_fallback
    selected = _label_selected_evidence(selected_records)
    fallback = writer_required_markdown(product, selected, language=language)
    if error:
        return f"{fallback}\n\nWriter provider fallback: {error[:180]}"
    return fallback


def build_writer_state(
    *,
    status: str,
    mode: str,
    provider: str,
    language: str,
    model: str,
    selected_count: int,
    cache_hit: bool = False,
    error: str = "",
) -> dict[str, Any]:
    state = {
        "status": status,
        "mode": mode,
        "provider": provider,
        "model": model or os.getenv("RELIGION_ANSWER_MODEL", ""),
        "selectedCount": selected_count,
        "cacheHit": bool(cache_hit),
        "message": _writer_message(status=status, language=language),
    }
    if error:
        state["error"] = error
    return state


def complete_writer_with_cache(
    product: ProductProfile,
    query: str,
    language: str,
    *,
    llm_client: LLMClient,
    model: str,
    messages: list[dict[str, str]],
    cache_root: Path | None,
) -> tuple[str, bool]:
    writer_messages = _writer_messages_for_client(product, query, language, messages, llm_client)
    payload = {
        "cacheVersion": "beta6-writer-v2",
        "product": product.key,
        "query": query,
        "language": language,
        "model": model or "",
        "provider": str(getattr(llm_client, "provider", "") or ""),
        "messages": writer_messages,
    }

    def produce() -> dict[str, Any]:
        return {"raw": _complete_llm(llm_client, writer_messages, model=model)}

    value, cache_hit = _read_or_fill_batch_cache("writer", payload, produce, cache_root=cache_root)
    return str(value.get("raw") or ""), cache_hit


def _writer_messages_for_client(
    product: ProductProfile,
    query: str,
    language: str,
    messages: list[dict[str, str]],
    llm_client: LLMClient,
) -> list[dict[str, str]]:
    adapter = get_domain_adapter(product)
    if (
        str(getattr(llm_client, "provider", "") or "") == "lawkey_gemma_gateway"
        and _looks_like_multiple_choice_exam_query(query)
    ):
        evidence = _gateway_writer_evidence_excerpt(messages) if _env_flag("RELIGION_GEMMA_GATEWAY_INCLUDE_EVIDENCE") else ""
        prompt = adapter.gateway_writer_prompt(query, evidence=evidence)
        if prompt:
            return [{"role": "user", "content": prompt}]
    return messages


def _looks_like_multiple_choice_exam_query(query: str) -> bool:
    text = str(query or "")
    return "객관식" in text and "정답" in text


def _gateway_writer_evidence_excerpt(messages: list[dict[str, str]]) -> str:
    user_content = "\n\n".join(str(message.get("content") or "") for message in messages if message.get("role") == "user")
    match = re.search(r"Selected beta6 records:\n(?P<body>.*?)(?:\n\n\[minimum answer depth\]|\n\nReturn a structured cited answer\.|\Z)", user_content, re.S)
    if match:
        body = match.group("body")
    else:
        body = user_content
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    return body[:3500]


def sanitize_writer_answer(answer: str, *, language: str = "") -> str:
    text = str(answer or "")
    for tag in ("thought", "thinking", "analysis", "reasoning"):
        text = re.sub(rf"(?is)\s*\[{tag}\].*?\[/{tag}\]\s*", "\n", text)
        text = re.sub(rf"(?is)\s*<{tag}>.*?</{tag}>\s*", "\n", text)
    marker_lines = {
        "[thought]",
        "[/thought]",
        "<thought>",
        "</thought>",
        "[thinking]",
        "[/thinking]",
        "<thinking>",
        "</thinking>",
        "[analysis]",
        "[/analysis]",
        "<analysis>",
        "</analysis>",
        "[reasoning]",
        "[/reasoning]",
        "<reasoning>",
        "</reasoning>",
    }
    lines = [line for line in text.splitlines() if line.strip().lower() not in marker_lines]
    text = "\n".join(lines).strip()
    return _localize_visible_writer_boilerplate(text, language=language).strip()


def enforce_domain_answer_boundary(product: ProductProfile, answer: str, *, language: str) -> str:
    text = str(answer or "").strip()
    if product.key != "islam" or _has_islam_no_fatwa_boundary(text):
        return text
    if language == "ko":
        boundary = "**안전 경계:** 이 답변은 선택된 원문 근거를 정리한 학습용 설명이며, 구속력 있는 파트와나 최종 판결이 아닙니다."
    elif language == "ar":
        boundary = "**تنبيه:** هذه إجابة تعليمية مبنية على المصادر المختارة، وليست فتوى ملزمة أو حكما نهائيا."
    else:
        boundary = "**Boundary:** This is a study answer grounded in the selected sources, not a binding fatwa or final ruling."
    return f"{text}\n\n{boundary}" if text else boundary


def _has_islam_no_fatwa_boundary(answer: str) -> bool:
    lowered = str(answer or "").lower()
    if "구속력 있는 파트와" in answer or "최종 판결이 아닙니다" in answer:
        return True
    if "binding fatwa" in lowered or "not a fatwa" in lowered or "final ruling" in lowered:
        return True
    if "فتوى ملزمة" in answer or "حكما نهائيا" in answer or "حكمًا نهائيًا" in answer:
        return True
    return False


def _localize_visible_writer_boilerplate(answer: str, *, language: str) -> str:
    text = str(answer or "")
    if language == "ko":
        replacements = {
            "GEMMA4 CITED ANSWER": "인용 답변",
            "GEMMA 4 CITED ANSWER": "인용 답변",
            "CITED ANSWER": "인용 답변",
            "PRIMARY TEXT SOURCE": "주요 원문 근거",
            "PRIMARY SOURCE": "주요 근거",
            "CROSS-CHECK SOURCE": "교차 확인 근거",
            "CROSS CHECK SOURCE": "교차 확인 근거",
            "SOURCES": "출처",
        }
    elif language == "ar":
        replacements = {
            "GEMMA4 CITED ANSWER": "جواب موثق",
            "GEMMA 4 CITED ANSWER": "جواب موثق",
            "CITED ANSWER": "جواب موثق",
            "PRIMARY TEXT SOURCE": "المصدر النصي الرئيس",
            "PRIMARY SOURCE": "المصدر الرئيس",
            "CROSS-CHECK SOURCE": "مصدر المقارنة",
            "CROSS CHECK SOURCE": "مصدر المقارنة",
            "SOURCES": "المصادر",
        }
    else:
        replacements = {
            "GEMMA4 CITED ANSWER": "Cited Answer",
            "GEMMA 4 CITED ANSWER": "Cited Answer",
        }
    for source, target in replacements.items():
        text = re.sub(rf"(?im)^(#+\s*){re.escape(source)}\s*$", rf"\1{target}", text)
    return text


def _writer_message(*, status: str, language: str) -> str:
    if status == "completed":
        if language == "ko":
            return "LLM writer가 선택 근거를 사용해 인용 답변을 작성했습니다."
        if language == "ar":
            return "استخدم الكاتب اللغوي الأدلة المختارة لصياغة الجواب مع الإحالات."
        return "The LLM writer used the selected evidence to draft the cited answer."
    if status in {"provider_timeout_fallback", "provider_error_fallback"}:
        if language == "ko":
            return "LLM writer provider 오류로 deterministic fallback 답변을 작성했습니다."
        if language == "ar":
            return "تعذر مزود كاتب النموذج، لذلك صيغت إجابة احتياطية حتمية."
        return "The LLM writer provider failed, so a deterministic fallback answer was produced."
    if language == "ko":
        return "근거 선택은 완료됐지만 답변 작성 모델이 연결되지 않아 최종 답변을 작성하지 않습니다."
    if language == "ar":
        return "اكتمل اختيار الأدلة، لكن كاتب النموذج اللغوي غير متصل، لذلك لا يُعرض جواب نهائي."
    return "Evidence selection is complete, but no answer writer is connected, so no final answer is presented."


def writer_required_markdown(
    product: ProductProfile,
    selected: list[dict[str, Any]],
    *,
    language: str,
) -> str:
    if language == "ko":
        heading = "## 근거 선택 완료 - 답변 작성 대기"
        body = "질문에 맞는 원문 후보를 선택했습니다. 현재 실행 환경에는 답변 작성 모델이 연결되어 있지 않아 이 내용을 최종 답변처럼 제시하지 않습니다."
        next_heading = "### 다음 단계"
        next_body = "답변 작성 모델이 연결되면 선택 근거를 바탕으로 인용 답변을 작성합니다. 지금은 선택 근거와 안전 경계를 확인하세요."
        sources_heading = "### 선택된 근거"
    elif language == "ar":
        heading = "## اكتمل اختيار الأدلة - بانتظار الكاتب"
        body = "اختيرت المقاطع المناسبة للسؤال، لكن كاتب النموذج اللغوي غير متصل في هذه البيئة؛ لذلك لا يُعرض هذا كنص جواب نهائي."
        next_heading = "### الخطوة التالية"
        next_body = "عند اتصال الكاتب تُستخدم الأدلة المختارة لصياغة جواب موثق. الآن تُعرض الأدلة المختارة وحدود السلامة فقط."
        sources_heading = "### الأدلة المختارة"
    else:
        heading = "## Evidence selected - writer required"
        body = "Source excerpts were selected for the question. No answer writer is connected in this runtime, so this is not presented as a final answer."
        next_heading = "### Next step"
        next_body = "When a writer is connected, it should use the selected evidence to produce the cited answer. For now, review the selected evidence and safety boundary."
        sources_heading = "### Selected evidence"
    lines = [heading, "", body, "", next_heading, "", next_body]
    if product.safety_notice:
        lines.extend(["", "### Safety", "", product.safety_notice])
    if selected:
        lines.extend(["", sources_heading])
        for item in selected[:5]:
            label = item.get("label") or "S?"
            citation = item.get("citation") or item.get("title") or item.get("id") or "source"
            excerpt = " ".join(str(item.get("excerpt") or "").split())[:220]
            lines.append(f"- [{label}] **{citation}** — {excerpt}")
    return "\n".join(lines).rstrip()


def build_answer_sections(
    product: ProductProfile,
    rows: list[SearchResult],
    selected: list[dict[str, Any]],
    *,
    language: str,
) -> list[dict[str, Any]]:
    if product.key == "islam":
        return _build_islam_answer_sections(product, rows, selected, language=language)
    if product.key == "tcm":
        return _build_tcm_answer_sections(product, rows, selected, language=language)
    return _build_generic_answer_sections(product, rows, selected, language=language)


def answer_sections_to_markdown(
    product: ProductProfile,
    sections: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    *,
    language: str,
) -> str:
    if language == "ko":
        heading = "## 근거 기반 답변"
        sources_heading = "### 인용 근거"
    elif language == "ar":
        heading = "## إجابة موثقة"
        sources_heading = "### المصادر المستشهد بها"
    else:
        heading = "## Grounded answer"
        sources_heading = "### Cited sources"
    lines = [heading, ""]
    for section in sections:
        title = str(section.get("title") or "")
        body = str(section.get("body") or "")
        citations = [str(label) for label in section.get("citations") or [] if label]
        if title:
            lines.extend([title, ""])
        if body:
            tail = " " + " ".join(f"[{label}]" for label in citations) if citations else ""
            lines.extend([body + tail, ""])
    if selected:
        lines.append(sources_heading)
        for item in selected[:5]:
            label = item.get("label") or "S?"
            citation = item.get("citation") or item.get("title") or item.get("id")
            excerpt = " ".join(str(item.get("excerpt") or "").split())[:280]
            lines.append(f"- [{label}] **{citation}** — {excerpt}")
    return "\n".join(lines).rstrip()


def _build_generic_answer_sections(
    product: ProductProfile,
    rows: list[SearchResult],
    selected: list[dict[str, Any]],
    *,
    language: str,
) -> list[dict[str, Any]]:
    if not rows:
        body = "검색된 근거 문헌이 없습니다. 질문을 더 구체적으로 바꿔 주세요." if language == "ko" else "No source passages were retrieved. Try a more specific question."
        return [{"kind": "empty", "title": "### 주요 근거" if language == "ko" else "### Main sources", "body": body, "citations": []}]
    labels = [str(item.get("label") or "") for item in selected[:3] if item.get("label")]
    intro = "아래 답변은 현재 검색된 문헌 조각만 바탕으로 한 초안입니다." if language == "ko" else "This draft is grounded only in the source passages retrieved for the query."
    return [
        {"kind": "direct", "title": "### 주요 근거" if language == "ko" else "### Main sources", "body": intro, "citations": labels},
        {"kind": "boundary", "title": "### 경계" if language == "ko" else "### Boundary", "body": product.safety_notice, "citations": []},
    ]


def _build_islam_answer_sections(
    product: ProductProfile,
    rows: list[SearchResult],
    selected: list[dict[str, Any]],
    *,
    language: str,
) -> list[dict[str, Any]]:
    ko = language == "ko"
    ar = language == "ar"
    if not rows:
        if ar:
            return [
                {
                    "kind": "empty",
                    "title": "### نتيجة البحث",
                    "body": "لم يتم العثور على مقاطع إسلامية موثقة. جرّب سؤالا أكثر تحديدا.",
                    "citations": [],
                },
                {"kind": "boundary", "title": "### الحد", "body": _islam_boundary_text(language), "citations": []},
            ]
        return [
            {
                "kind": "empty",
                "title": "### 검색 결과" if ko else "### Retrieval result",
                "body": "검색된 이슬람 문헌 근거가 없습니다. 질문을 더 구체화해 주세요." if ko else "No Islamic source passages were retrieved. Try a more specific question.",
                "citations": [],
            },
            {
                "kind": "boundary",
                "title": "### 경계" if ko else "### Boundary",
                "body": _islam_boundary_text(language),
                "citations": [],
            },
        ]
    labels = [str(item.get("label") or "") for item in selected[:5] if item.get("label")]
    strongest = selected[0]
    source_summary = _summarize_source_mix(rows, language=language)
    school_summary = _summarize_school_positions(rows, selected, language=language)
    direct_body = (
        "선택된 근거 안에서만 정리하면, 이 사안은 하나의 결론으로 단정하기보다 문헌 계층과 학파/전통 차이를 나누어 보아야 합니다. "
        f"가장 먼저 보이는 근거는 {strongest.get('citation') or strongest.get('title')}이며, 나머지 근거와 함께 대조해야 합니다."
        if ko
        else (
            "في حدود الأدلة المختارة، لا ينبغي تحويل هذه المسألة إلى حكم ملزم واحد؛ بل تُعرض طبقات المصادر وإشارات المذهب/التقليد. "
            f"أول مصدر ظاهر هو {strongest.get('citation') or strongest.get('title')}، وينبغي قراءته مع بقية المصادر."
            if ar
            else (
                "Within the selected evidence, this should not be reduced to a single binding conclusion. "
                f"The first source surfaced is {strongest.get('citation') or strongest.get('title')}; it should be read alongside the other cited sources."
            )
        )
    )
    return [
        {
            "kind": "orientation",
            "title": "### 단정 대신 근거 범위" if ko else ("### حدود الدليل قبل الحكم" if ar else "### Evidence boundary before conclusion"),
            "body": direct_body,
            "citations": labels[:2],
        },
        {
            "kind": "sources",
            "title": "### 문헌 계층" if ko else ("### طبقات المصادر" if ar else "### Source hierarchy"),
            "body": source_summary,
            "citations": labels[:4],
        },
        {
            "kind": "schools",
            "title": "### 학파 및 전통별로 볼 지점" if ko else ("### عرض المذاهب والتقاليد" if ar else "### School and tradition framing"),
            "body": school_summary,
            "citations": labels[:5],
        },
        {
            "kind": "boundary",
            "title": "### 경계" if ko else ("### الحد" if ar else "### Boundary"),
            "body": _islam_boundary_text(language),
            "citations": [],
        },
    ]


def _summarize_source_mix(rows: list[SearchResult], *, language: str) -> str:
    counts: dict[str, int] = {}
    for row in rows:
        key = row.source_kind or row.case_type or "source"
        counts[key] = counts.get(key, 0) + 1
    parts = [f"{kind} {count}" for kind, count in sorted(counts.items())]
    if language == "ko":
        return "검색된 근거의 종류는 " + ", ".join(parts) + "입니다. 꾸란/하디스/주석/피크흐가 섞이면 높은 권위 원문을 먼저 보고, 적용 문제는 학파 문헌을 별도로 봅니다."
    if language == "ar":
        return "أنواع الأدلة المسترجعة: " + ", ".join(parts) + ". تُقرأ النصوص الأعلى سلطة أولا، ثم تُفصل مسائل التطبيق بحسب مصادر المذاهب عند توفرها."
    return "Retrieved evidence types: " + ", ".join(parts) + ". Read higher-authority source text first, then treat applied fiqh questions through school-specific sources."


def _summarize_school_positions(rows: list[SearchResult], selected: list[dict[str, Any]], *, language: str) -> str:
    grouped: dict[str, list[str]] = {}
    for row, item in zip(rows, selected):
        school = row.school or row.tradition or "all"
        label = str(item.get("label") or "")
        citation = row.citation or row.title or row.canonical_id
        grouped.setdefault(school, []).append(f"{citation} [{label}]" if label else citation)
    if language == "ko":
        if not grouped:
            return "검색된 근거 안에서는 학파별 직접 대비 자료가 충분하지 않습니다. 이 경우 결론을 내리지 않고 추가 검색이 필요합니다."
        chunks = [f"{school}: " + "; ".join(items[:2]) for school, items in sorted(grouped.items())]
        return "검색된 근거 안에서 확인되는 학파/전통은 " + " / ".join(chunks) + "입니다. 누락된 학파가 있으면 그 침묵을 결론으로 간주하지 않습니다."
    if language == "ar":
        if not grouped:
            return "لا تحتوي الأدلة المختارة على مادة كافية للمقارنة بين المذاهب؛ لا يُستنبط حكم من مجرد غياب النتائج."
        chunks = [f"{school}: " + "; ".join(items[:2]) for school, items in sorted(grouped.items())]
        return "إشارات المذهب/التقليد في الأدلة المختارة: " + " / ".join(chunks) + ". غياب مذهب ما يُعد فجوة في الاسترجاع لا حكما."
    if not grouped:
        return "The selected evidence does not contain enough school-specific material for a comparison; do not infer a ruling from silence."
    chunks = [f"{school}: " + "; ".join(items[:2]) for school, items in sorted(grouped.items())]
    return "School/tradition signals in the selected evidence: " + " / ".join(chunks) + ". Missing schools should be treated as a retrieval gap, not as a ruling."


def _islam_boundary_text(language: str) -> str:
    if language == "ko":
        return "이 출력은 구속력 있는 파트와가 아닙니다. 개인 상황, 지역 관습, 소속 학파, 실제 종교 실천 문제는 자격 있는 학자에게 확인해야 합니다."
    if language == "ar":
        return "هذه ليست فتوى ملزمة. ينبغي عرض الحالات الشخصية ومسائل المذهب والعرف على عالم مؤهل."
    return "This is not a binding fatwa. Personal circumstances, local custom, and school-specific practice should be checked with a qualified scholar."


def _build_tcm_answer_sections(
    product: ProductProfile,
    rows: list[SearchResult],
    selected: list[dict[str, Any]],
    *,
    language: str,
) -> list[dict[str, Any]]:
    ko = language == "ko"
    if not rows:
        return [
            {
                "kind": "empty",
                "title": "### 검색 결과" if ko else "### Retrieval result",
                "body": "검색된 한의학 문헌 근거가 없습니다. 약재명, 처방명, 증상, 변증어를 더 구체화해 주세요." if ko else "No Korean/Chinese medicine source passages were retrieved. Try a more specific herb, formula, symptom, or pattern term.",
                "citations": [],
            },
            {
                "kind": "boundary",
                "title": "### 안전 경계" if ko else "### Safety boundary",
                "body": _tcm_boundary_text(language),
                "citations": [],
            },
        ]
    labels = [str(item.get("label") or "") for item in selected[:5] if item.get("label")]
    strongest = selected[0]
    source_summary = _summarize_tcm_source_mix(rows, language=language)
    framework = _summarize_tcm_framework(rows, selected, language=language)
    materia = _summarize_tcm_materia_and_contra(rows, selected, language=language)
    direct_body = (
        "선택된 근거 안에서만 보면, 이 질문은 바로 진단이나 처방으로 넘기지 말고 먼저 고전 원문, 본초/처방 문헌, 임상 증례를 분리해 읽어야 합니다. "
        f"가장 먼저 확인된 근거는 {strongest.get('citation') or strongest.get('title')}입니다."
        if ko
        else (
            "Within the selected evidence, this should not be turned directly into a diagnosis or treatment instruction. "
            f"The first source surfaced is {strongest.get('citation') or strongest.get('title')}; read it separately from materia medica, formulary, and case-record evidence."
        )
    )
    return [
        {
            "kind": "orientation",
            "title": "### 문헌 범위" if ko else "### Evidence boundary",
            "body": direct_body,
            "citations": labels[:2],
        },
        {
            "kind": "source_hierarchy",
            "title": "### 문헌 계층" if ko else "### Source hierarchy",
            "body": source_summary,
            "citations": labels[:4],
        },
        {
            "kind": "pattern_formula",
            "title": "### 변증과 처방은 분리" if ko else "### Separate pattern and formula",
            "body": framework,
            "citations": labels[:5],
        },
        {
            "kind": "materia_safety",
            "title": "### 본초와 금기 확인" if ko else "### Materia medica and contraindications",
            "body": materia,
            "citations": labels[:5],
        },
        {
            "kind": "boundary",
            "title": "### 안전 경계" if ko else "### Safety boundary",
            "body": _tcm_boundary_text(language),
            "citations": [],
        },
    ]


def _summarize_tcm_source_mix(rows: list[SearchResult], *, language: str) -> str:
    counts: dict[str, int] = {}
    for row in rows:
        key = row.source_kind or row.case_type or "source"
        counts[key] = counts.get(key, 0) + 1
    parts = [f"{kind} {count}" for kind, count in sorted(counts.items())]
    if language == "ko":
        return "검색된 근거의 종류는 " + ", ".join(parts) + "입니다. 원문 고전과 본초/방제 문헌을 먼저 보고, 현대 증례는 적용 가능성을 살피는 보조 근거로 둡니다."
    return "Retrieved evidence types: " + ", ".join(parts) + ". Read classical and materia/formulary sources first; use modern case records only as supporting context."


def _summarize_tcm_framework(rows: list[SearchResult], selected: list[dict[str, Any]], *, language: str) -> str:
    grouped: dict[str, list[str]] = {}
    for row, item in zip(rows, selected):
        key = row.school or row.source_kind or "source"
        label = str(item.get("label") or "")
        citation = row.citation or row.title or row.canonical_id
        grouped.setdefault(key, []).append(f"{citation} [{label}]" if label else citation)
    chunks = [f"{key}: " + "; ".join(items[:2]) for key, items in sorted(grouped.items())]
    if language == "ko":
        return "선택 근거는 " + " / ".join(chunks) + "로 나뉩니다. 증상명만으로 처방을 정하지 말고 한열, 허실, 장부, 사상체질 같은 변증 축을 별도로 확인해야 합니다."
    return "Selected evidence is grouped as " + " / ".join(chunks) + ". Do not map symptoms directly to a formula; separately check cold/heat, deficiency/excess, organ pattern, and constitution."


def _summarize_tcm_materia_and_contra(rows: list[SearchResult], selected: list[dict[str, Any]], *, language: str) -> str:
    labels = [str(item.get("label") or "") for item in selected if item.get("label")]
    has_safety_source = any((row.source_kind or row.case_type) in {"materia_medica", "formulary", "clinical_guideline"} for row in rows)
    if language == "ko":
        base = "약재나 처방이 언급되면 본초 성미, 배합, 용량, 금기, 임신/소아/기저질환/복용약 여부를 따로 확인해야 합니다."
        if has_safety_source:
            return base + " 이번 검색에는 본초/방제/가이드라인 성격의 근거가 포함되어 있으므로 해당 카드부터 대조하세요."
        return base + " 이번 검색에 본초·금기 전용 근거가 부족하면, 그 부족함을 처방 가능성으로 해석하지 않습니다."
    base = "When an herb or formula appears, separately check materia medica properties, combinations, dose, contraindications, pregnancy, pediatrics, comorbidities, and current medication."
    if has_safety_source:
        return base + " This retrieval includes materia/formulary/guideline-style evidence, so compare those cards first."
    return base + " If contraindication-specific evidence is missing, do not treat that silence as permission."


def _tcm_boundary_text(language: str) -> str:
    if language == "ko":
        return "이 출력은 문헌 기반 탐색이며 진단이나 처방 지시가 아닙니다. 통증, 출혈, 임신, 소아, 만성질환, 복용약, 급성 증상은 한의사 또는 의사에게 확인해야 합니다."
    return "This is classical-source exploration, not a diagnosis or prescription. Pain, bleeding, pregnancy, pediatrics, chronic disease, current medication, or acute symptoms require qualified medical care."


def _domain_policy(product_key: str) -> str:
    return get_domain_adapter(product_key).writer_domain_policy()


def _writer_return_instruction(product_key: str, language: str = "") -> str:
    return get_domain_adapter(product_key).writer_return_instruction(language)


def _source_usage_hint(product_key: str, record: dict[str, Any]) -> str:
    return get_domain_adapter(product_key).source_usage_hint(record)


def _result_payload(row: SearchResult) -> dict[str, Any]:
    return {
        "id": row.canonical_id,
        "title": row.title,
        "citation": row.citation,
        "authorityBody": row.authority_body,
        "date": row.source_date,
        "topic": row.case_name,
        "type": row.case_type,
        "dataset": row.source_dataset,
        "path": row.source_path,
        "url": row.source_url,
        "score": row.score,
        "excerpt": " ".join(row.full_text.split())[:520],
        "tradition": row.tradition,
        "school": row.school,
        "sourceKind": row.source_kind,
        "authorityLevel": row.authority_level,
        "authorityLabel": row.authority_label,
    }


def _label_selected_evidence(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    labelled: list[dict[str, Any]] = []
    for index, source in enumerate(sources, start=1):
        labelled.append({**source, "label": f"S{index}"})
    return labelled


def apply_selector_ledger_to_selected_evidence(
    selected: list[dict[str, Any]],
    ledger: Any,
) -> list[dict[str, Any]]:
    normalized = _normalize_selector_ledger(ledger)
    if not normalized:
        return selected
    by_id = {item["fileId"]: item for item in normalized if item.get("fileId")}
    enriched: list[dict[str, Any]] = []
    for item in selected:
        source_id = str(item.get("id") or "").strip()
        ledger_item = by_id.get(source_id)
        if not ledger_item:
            enriched.append(item)
            continue
        enriched.append(
            {
                **item,
                "selectorContextSummary": _bounded_selector_ledger_text(ledger_item.get("contextSummary")),
                "selectorClaimSummary": _bounded_selector_ledger_text(ledger_item.get("claimSummary")),
                "selectorQuoteCandidate": _bounded_selector_ledger_text(ledger_item.get("quoteCandidate")),
                "selectorStance": _bounded_selector_ledger_text(ledger_item.get("stance"), limit=80),
                "selectorSourceRole": _bounded_selector_ledger_text(ledger_item.get("sourceRole"), limit=80),
            }
        )
    return enriched


def build_citation_map(selected: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("label") or f"S{index}"): {
            "id": item.get("id") or "",
            "citation": item.get("citation") or item.get("title") or item.get("id") or "",
            "title": item.get("title") or "",
            "school": item.get("school") or "",
            "tradition": item.get("tradition") or "",
            "sourceKind": item.get("sourceKind") or "",
            "authorityLevel": item.get("authorityLevel") or 0,
        }
        for index, item in enumerate(selected, start=1)
    }


def add_claim_citations(citation_map: dict[str, dict[str, Any]], claim_cards: list[dict[str, Any]]) -> None:
    for card in claim_cards:
        claim_id = str(card.get("claimId") or "")
        if not claim_id:
            continue
        citation_map[claim_id] = {
            "id": card.get("sourceId") or "",
            "sourceId": card.get("sourceId") or "",
            "citation": card.get("citation") or card.get("sourceId") or claim_id,
            "title": card.get("citation") or "",
            "school": card.get("school") or "",
            "tradition": card.get("tradition") or "",
            "sourceKind": card.get("sourceKind") or card.get("role") or "",
            "authorityLevel": 0,
            "excerpt": card.get("quote") or "",
        }


def build_passages(selected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "label": item.get("label") or f"S{index}",
            "sourceId": item.get("id") or "",
            "citation": item.get("citation") or item.get("title") or item.get("id") or "",
            "text": item.get("excerpt") or "",
            "language": item.get("language") or "",
            "school": item.get("school") or "",
            "tradition": item.get("tradition") or "",
            "sourceKind": item.get("sourceKind") or "",
        }
        for index, item in enumerate(selected, start=1)
    ]


def detect_question_language(profile: ProductProfile, query: str) -> str:
    text = str(query or "")
    supported = set(profile.languages)
    if "ko" in supported and re.search(r"[\uac00-\ud7af]", text):
        return "ko"
    if "ar" in supported and re.search(r"[\u0600-\u06ff]", text):
        return "ar"
    if "pa" in supported and re.search(r"[\u0a00-\u0a7f]", text):
        return "pa"
    if "bn" in supported and re.search(r"[\u0980-\u09ff]", text):
        return "bn"
    if re.search(r"[A-Za-z]", text):
        return "en" if "en" in supported else ""
    return ""


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        tmp.write_text(payload, encoding="utf-8")
        os.replace(tmp, path)
    finally:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass


def _load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def _durable_queue_order_timestamp(row: dict[str, Any], row_path: Path) -> float:
    for key in ("createdAt", "queuedAt", "submittedAt", "updatedAt", "queueRowUpdatedAt"):
        try:
            value = float(row.get(key) or 0)
        except (TypeError, ValueError):
            value = 0.0
        if value > 0:
            return value
    try:
        return row_path.stat().st_mtime
    except OSError:
        return 0.0


def _hash_job_access_token(token: str) -> str:
    value = str(token or "")
    if not value:
        return ""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _hash_session_token(token: str) -> str:
    value = str(token or "")
    if not value:
        return ""
    return hashlib.sha256(f"beta6-session:{value}".encode("utf-8")).hexdigest()


def _hash_account_subject(subject: str) -> str:
    value = str(subject or "").strip()
    if not value:
        return ""
    return hashlib.sha256(f"beta6-account-subject:{value}".encode("utf-8")).hexdigest()


def _valid_session_token(token: str) -> bool:
    value = str(token or "").strip()
    return len(value) >= 24


def _public_status(status: dict[str, Any]) -> dict[str, Any]:
    public = dict(status)
    public.pop("accessTokenHash", None)
    public.pop("accessToken", None)
    public.pop("sessionTokenHash", None)
    public.pop("accountSubjectHash", None)
    public.pop("monotonicCreatedAt", None)
    public.pop("monotonicElapsedSeconds", None)
    return public


def _owner_process_alive(status: dict[str, Any]) -> bool:
    try:
        pid = int(status.get("ownerPid") or 0)
    except (TypeError, ValueError):
        pid = 0
    return pid > 0 and Path(f"/proc/{pid}").exists()


def _worker_lease_expired(status: dict[str, Any], *, now: float | None = None) -> bool:
    if str(status.get("status") or "") != "running":
        return False
    worker_lease = status.get("workerLease")
    if not isinstance(worker_lease, dict):
        return False
    try:
        expires_at = float(worker_lease.get("expiresAt") or 0)
    except (TypeError, ValueError):
        return False
    if expires_at <= 0:
        return False
    return (time.time() if now is None else now) > expires_at
