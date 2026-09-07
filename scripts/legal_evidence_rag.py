#!/usr/bin/env python3

import argparse
import copy
import dataclasses
import difflib
import hashlib
import json
import math
import os
import re
import subprocess
import tempfile
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Iterable

import fitz  # type: ignore
import requests
try:
    import tiktoken
except ImportError:
    tiktoken = None


DEFAULT_CHAT_API_URL = "http://172.21.32.1:8046/v1/chat/completions"
DEFAULT_SELECT_MODEL = "gemini-3.1-flash-lite-preview"
DEFAULT_ANALYZE_MODEL = "gemini-3.1-flash-lite-preview"
DEFAULT_DRAFT_MODEL = "gemini-3.1-flash-lite-preview"
DEFAULT_EMBED_MODEL = "gemini-embedding-002"
ANALYZE_CACHE_SCHEMA_VERSION = "evidence-id-v2"
ALL_VARIANTS = [
    "variant_llm_select",
    "variant_embedding_select",
    "variant_full_scan",
    "variant_hybrid",
]
DEFAULT_MAX_REQUEST_TOKENS = 100_000
DEFAULT_CHUNK_TOKENS = 12_000
DEFAULT_QUESTION_CHUNK_TOKENS = 50_000
DEFAULT_LLM_SELECT_PACK_TOKENS = 12_000
DEFAULT_ANCHOR_TEXT_CHARS = 2_000
DEFAULT_QUOTE_CHARS = 220
DEFAULT_EMBED_WORKERS = 10
DEFAULT_ANALYZE_WORKERS = 8
DEFAULT_CHUNK_BUILD_WORKERS = 4
# Follow the HTML reference scheduler: always keep a 3s minimum per-key gap.
GEMINI_KEY_MIN_GAP_MS = 3000
GEMINI_KEY_MAX_INFLIGHT = 1
GEMINI_KEY_RPM_LIMIT = 20
GEMINI_KEY_TPM_LIMIT = 0
GEMINI_GLOBAL_MAX_INFLIGHT = 0
GEMINI_GLOBAL_RETRY_ROUNDS = 4
TOKENIZER_NAME = "cl100k_base"
EMBED_GROUP_ORDER = ["military_casebook", "general_casebook", "other", "regulation"]
EMBED_GROUP_CAP_RATIO = {
    "military_casebook": 0.45,
    "general_casebook": 0.35,
    "other": 0.30,
    "regulation": 0.35,
}
DIRECT_CHAT_MODEL_FALLBACKS = {
    "gemma-4-31b-it": ["gemma-4-27b", "gemma-4-26b", "gemma-3-27b-it", "gemini-3.1-pro"],
    "gemma-4-27b": ["gemma-4-26b", "gemma-3-27b-it", "gemini-3.1-pro"],
    "gemma-4-26b": ["gemma-4-27b", "gemma-3-27b-it", "gemini-3.1-pro"],
    "gemini-3.1-pro": ["gemini-2.5-pro", "gemini-2.5-flash"],
    "gemini-3-flash": ["gemini-2.5-flash"],
    "gemini-3.1-flash-lite-preview": ["gemini-flash-lite-latest", "gemini-2.5-flash-lite"],
}
EMBED_MODEL_FALLBACKS = {
    "gemini-embedding-002": ["gemini-embedding-2-preview", "gemini-embedding-001"],
    "gemini-embedding-2-preview": ["gemini-embedding-001"],
}
EMBED_CACHE_DIR = Path.home() / ".cache" / "legal_evidence_rag_embeddings"


def _safe_http_exception_detail(exc: BaseException) -> str:
    return _redact_gemini_api_key(str(exc))


def _redact_gemini_api_key(text: str) -> str:
    return re.sub(r"([?&]key=)[^&\s]+", r"\1[REDACTED]", str(text or ""))


ENV_FALLBACK_FILES = [
    Path.home() / ".config" / "legal_evidence_rag" / "keys.env",
    Path(".env"),
]
SEPARATOR_RE = re.compile(r"^[=\-_*#~]{3,}$")
HEADING_PREFIX_RE = re.compile(r"^(?:제\s*\d+\s*조|[0-9]+\.|[가-하]\.|\([0-9]+\)|\[[^\]]+\]|사건번호\s*:|판결요지\s*:|판시사항\s*:|이유\s*:)")
JSON_KEY_RE = re.compile(r'^\s*"?([A-Za-z0-9_가-힣]+)"?\s*[:=]')
WHITESPACE_RE = re.compile(r"\s+")
VIRTUAL_DOC_SEPARATOR_LINE = "=" * 40

DIRECT_EVIDENCE_FILES = {
    "law/징계위원회.txt",
    "law/증거/징계의결요구고지서.pdf",
    "law/증거/징계처분서.pdf",
}
DISCIPLINE_CASE_KEYWORDS = [
    "징계",
    "인사",
    "복무",
    "품위",
    "성실",
    "강요",
    "직권남용",
    "근무태만",
    "군기교육",
    "모욕",
    "강제추행",
    "징계령",
    "징계규정",
    "군인사법",
    "인사관리",
    "행동강령",
    "복무",
    "보안규정",
    "비밀엄수",
    "심부름",
]
CERTAINTY_ORDER = {
    "very_high": 5,
    "high": 4,
    "medium": 3,
    "low": 2,
    "speculative": 1,
}
CERTAINTY_LABELS = {
    "매우높음": "very_high",
    "높음": "high",
    "보통": "medium",
    "낮음": "low",
    "추측": "speculative",
}


if tiktoken is not None:
    ENCODER = tiktoken.get_encoding(TOKENIZER_NAME)
else:
    ENCODER = None


@dataclasses.dataclass
class SelectionParseResult:
    reasoning: str
    selected_ids: list[str]


@dataclasses.dataclass
class FileRecord:
    file_id: str
    relative_path: str
    absolute_path: str
    document_title: str
    doc_type: str
    source_group: str
    token_count: int
    anchor_text: str
    extracted_text: str
    candidate_boundaries: list[dict[str, Any]]
    is_direct_evidence: bool
    is_format_sample: bool = False
    content_hash: str = ""
    duplicate_paths: list[str] = dataclasses.field(default_factory=list)
    case_number: str = ""
    court: str = ""
    decision_date: str = ""
    case_name: str = ""


@dataclasses.dataclass
class ChunkRecord:
    chunk_id: str
    file_id: str
    document_title: str
    same_document_group: str
    relative_path: str
    start_char: int
    end_char: int
    text: str
    token_count: int
    case_number: str = ""
    court: str = ""
    decision_date: str = ""
    case_name: str = ""
    source_segments: list[dict[str, Any]] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class GeminiKeyState:
    last_sent_at_ms: float = 0.0
    cooldown_until_ms: float = 0.0
    cooldown_retry_count: int = 0
    inflight_count: int = 0
    window_start_ms: float = 0.0
    rpm_count: int = 0
    tpm_count: int = 0


@dataclasses.dataclass
class LegalEvidenceRequest:
    base_user_task: str
    target_files: list[str]
    core_issues: list[str]
    incident_data: str
    incident_material_paths: list[str]


class GeminiKeyScheduler:
    def __init__(self, keys: list[str]):
        self.keys = list(keys)
        self.states = {key: GeminiKeyState() for key in self.keys}
        self.next_idx = 0
        self.cv = threading.Condition()

    def _reset_window_unlocked(self, state: GeminiKeyState, now_ms: float) -> None:
        window_start_ms = now_ms - (now_ms % 60000)
        if not state.window_start_ms or window_start_ms != state.window_start_ms:
            state.window_start_ms = window_start_ms
            state.rpm_count = 0
            state.tpm_count = 0

    def runtime_snapshot(
        self,
        *,
        now_ms: float,
        key_min_gap_ms: int,
        key_max_inflight: int,
        key_rpm_limit: int = GEMINI_KEY_RPM_LIMIT,
        key_tpm_limit: int = GEMINI_KEY_TPM_LIMIT,
        global_max_inflight: int = GEMINI_GLOBAL_MAX_INFLIGHT,
    ) -> dict[str, int]:
        cooling = 0
        inflight = 0
        best_ready_at = math.inf
        for state in self.states.values():
            self._reset_window_unlocked(state, now_ms)
            inflight += state.inflight_count
            if state.cooldown_until_ms and now_ms < state.cooldown_until_ms:
                cooling += 1
            ready_at = now_ms
            if state.cooldown_until_ms and now_ms < state.cooldown_until_ms:
                ready_at = max(ready_at, state.cooldown_until_ms)
            if state.inflight_count >= key_max_inflight:
                ready_at = max(ready_at, now_ms + 50.0)
            else:
                next_by_gap = state.last_sent_at_ms + key_min_gap_ms if state.last_sent_at_ms else now_ms
                if next_by_gap and now_ms < next_by_gap:
                    ready_at = max(ready_at, next_by_gap)
                if key_rpm_limit > 0 and state.rpm_count >= key_rpm_limit:
                    ready_at = max(ready_at, state.window_start_ms + 60025.0)
            best_ready_at = min(best_ready_at, ready_at)
        next_ready_in_ms = 0 if not math.isfinite(best_ready_at) else max(0, int(best_ready_at - now_ms))
        return {
            "gemini_keys_total": len(self.states),
            "gemini_keys_cooling_down": cooling,
            "gemini_scheduler_inflight": inflight,
            "gemini_next_ready_in_ms": next_ready_in_ms,
            "gemini_key_min_gap_ms": key_min_gap_ms,
            "gemini_key_max_inflight": key_max_inflight,
            "gemini_key_rpm_limit": key_rpm_limit,
            "gemini_key_tpm_limit": key_tpm_limit,
            "gemini_global_max_inflight": global_max_inflight,
        }

    def _emit_runtime_snapshot_unlocked(
        self,
        *,
        now_ms: float,
        key_min_gap_ms: int,
        key_max_inflight: int,
        key_rpm_limit: int,
        key_tpm_limit: int,
        global_max_inflight: int,
    ) -> None:
        status_path = _RUNTIME_STATUS_PATH
        if status_path is None:
            return
        merge_runtime_status(
            status_path,
            self.runtime_snapshot(
                now_ms=now_ms,
                key_min_gap_ms=key_min_gap_ms,
                key_max_inflight=key_max_inflight,
                key_rpm_limit=key_rpm_limit,
                key_tpm_limit=key_tpm_limit,
                global_max_inflight=global_max_inflight,
            ),
        )

    def acquire(self, *, est_tokens: int = 0) -> str:
        with self.cv:
            while True:
                limits = get_runtime_limits()
                key_max_inflight = limits["gemini_key_max_inflight"]
                key_min_gap_ms = limits["gemini_key_min_gap_ms"]
                key_rpm_limit = limits["gemini_key_rpm_limit"]
                key_tpm_limit = limits["gemini_key_tpm_limit"]
                global_max_inflight = limits["gemini_global_max_inflight"]
                now_ms = time.time() * 1000
                chosen_key: str | None = None
                chosen_idx = -1
                best_ready_at = math.inf
                total_inflight = sum(state.inflight_count for state in self.states.values())

                for offset in range(len(self.keys)):
                    idx = (self.next_idx + offset) % len(self.keys)
                    key = self.keys[idx]
                    state = self.states[key]
                    self._reset_window_unlocked(state, now_ms)
                    if state.cooldown_until_ms and now_ms >= state.cooldown_until_ms:
                        state.cooldown_until_ms = 0.0

                    ready_at = now_ms
                    if state.cooldown_until_ms and now_ms < state.cooldown_until_ms:
                        ready_at = max(ready_at, state.cooldown_until_ms)
                    if global_max_inflight > 0 and total_inflight >= global_max_inflight:
                        ready_at = max(ready_at, now_ms + 50.0)
                    elif state.inflight_count >= key_max_inflight:
                        ready_at = max(ready_at, now_ms + 50.0)
                    else:
                        next_by_gap = state.last_sent_at_ms + key_min_gap_ms if state.last_sent_at_ms else 0.0
                        if next_by_gap and now_ms < next_by_gap:
                            ready_at = max(ready_at, next_by_gap)
                        if key_rpm_limit > 0 and state.rpm_count >= key_rpm_limit:
                            ready_at = max(ready_at, state.window_start_ms + 60025.0)
                        if key_tpm_limit > 0:
                            projected_tpm = state.tpm_count + max(0, est_tokens)
                            if est_tokens > key_tpm_limit:
                                if state.tpm_count >= key_tpm_limit:
                                    ready_at = max(ready_at, state.window_start_ms + 60025.0)
                            elif projected_tpm > key_tpm_limit:
                                ready_at = max(ready_at, state.window_start_ms + 60025.0)

                    if chosen_key is None and ready_at <= now_ms and state.inflight_count < key_max_inflight:
                        chosen_key = key
                        chosen_idx = idx
                    if ready_at < best_ready_at:
                        best_ready_at = ready_at

                if chosen_key is not None:
                    state = self.states[chosen_key]
                    self._reset_window_unlocked(state, now_ms)
                    state.last_sent_at_ms = now_ms
                    state.inflight_count += 1
                    state.rpm_count += 1
                    state.tpm_count += max(0, est_tokens)
                    self.next_idx = (chosen_idx + 1) % len(self.keys)
                    self._emit_runtime_snapshot_unlocked(
                        now_ms=now_ms,
                        key_min_gap_ms=key_min_gap_ms,
                        key_max_inflight=key_max_inflight,
                        key_rpm_limit=key_rpm_limit,
                        key_tpm_limit=key_tpm_limit,
                        global_max_inflight=global_max_inflight,
                    )
                    return chosen_key

                wait_ms = 100.0
                if math.isfinite(best_ready_at):
                    wait_ms = max(50.0, min(1000.0, best_ready_at - now_ms))
                self._emit_runtime_snapshot_unlocked(
                    now_ms=now_ms,
                    key_min_gap_ms=key_min_gap_ms,
                    key_max_inflight=key_max_inflight,
                    key_rpm_limit=key_rpm_limit,
                    key_tpm_limit=key_tpm_limit,
                    global_max_inflight=global_max_inflight,
                )
                self.cv.wait(wait_ms / 1000.0)

    def complete(
        self,
        key: str,
        *,
        success: bool,
        transient: bool = False,
        retry_after_ms: int | None = None,
        http_status: int | None = None,
    ) -> None:
        with self.cv:
            limits = get_runtime_limits()
            state = self.states[key]
            state.inflight_count = max(0, state.inflight_count - 1)
            now_ms = time.time() * 1000
            if success:
                state.cooldown_until_ms = 0.0
                state.cooldown_retry_count = 0
            elif transient:
                state.cooldown_retry_count += 1
                delay_ms = max(
                    retry_after_ms or 0,
                    compute_http_aware_backoff_ms(state.cooldown_retry_count, http_status),
                )
                state.cooldown_until_ms = max(state.cooldown_until_ms, now_ms + delay_ms)
            self._emit_runtime_snapshot_unlocked(
                now_ms=now_ms,
                key_min_gap_ms=limits["gemini_key_min_gap_ms"],
                key_max_inflight=limits["gemini_key_max_inflight"],
                key_rpm_limit=limits["gemini_key_rpm_limit"],
                key_tpm_limit=limits["gemini_key_tpm_limit"],
                global_max_inflight=limits["gemini_global_max_inflight"],
            )
            self.cv.notify_all()


_GEMINI_SCHEDULER_LOCK = threading.Lock()
_GEMINI_SCHEDULERS: dict[tuple[str, ...], GeminiKeyScheduler] = {}
_RUNTIME_CONTROL_LOCK = threading.Lock()
_RUNTIME_CONTROL_PATH: Path | None = None
_RUNTIME_CONTROL_MTIME_NS: int | None = None
_RUNTIME_CONTROL_CACHE: dict[str, int] = {}
_RUNTIME_STATUS_LOCK = threading.Lock()
_RUNTIME_STATUS_PATH: Path | None = None
_RUNTIME_HTTP_STATE = {
    "http_started": 0,
    "http_finished": 0,
    "http_inflight": 0,
}


def _normalize_space(text: str | None) -> str:
    return WHITESPACE_RE.sub(" ", str(text or "")).strip()


def load_legal_evidence_request(path: Path) -> LegalEvidenceRequest:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("request json must be an object")

    base_user_task = _normalize_space(payload.get("base_user_task"))
    target_files = [_normalize_space(item) for item in payload.get("target_files") or [] if _normalize_space(item)]
    core_issues = [_normalize_space(item) for item in payload.get("core_issues") or [] if _normalize_space(item)]
    incident_data = str(payload.get("incident_data") or "").strip()
    incident_material_paths = [
        _normalize_space(item) for item in payload.get("incident_material_paths") or [] if _normalize_space(item)
    ]

    missing: list[str] = []
    if not target_files:
        missing.append("target_files")
    if not core_issues:
        missing.append("core_issues")
    if not incident_data:
        missing.append("incident_data")
    if not incident_material_paths:
        missing.append("incident_material_paths")
    if missing:
        raise ValueError("missing required request fields: " + ", ".join(missing))

    return LegalEvidenceRequest(
        base_user_task=base_user_task or "변호인 의견서 작성",
        target_files=target_files,
        core_issues=core_issues,
        incident_data=incident_data,
        incident_material_paths=incident_material_paths,
    )


def build_request_user_task(request: LegalEvidenceRequest) -> str:
    parts = [request.base_user_task.strip()]
    if request.core_issues:
        parts.append("[핵심쟁점]\n" + "\n".join(f"- {issue}" for issue in request.core_issues))
    if request.incident_data.strip():
        parts.append("[사건데이터]\n" + request.incident_data.strip())
    return "\n\n".join(part for part in parts if part)


def filter_records_to_target_files(records: list[FileRecord], target_files: list[str]) -> list[FileRecord]:
    normalized = {_normalize_space(item).replace("\\", "/") for item in target_files if _normalize_space(item)}
    if not normalized:
        return list(records)

    out: list[FileRecord] = []
    for record in records:
        rel = record.relative_path.replace("\\", "/")
        abs_path = record.absolute_path.replace("\\", "/")
        if rel in normalized or abs_path in normalized:
            out.append(record)
    return out


def set_runtime_control_file(path: Path | None) -> None:
    global _RUNTIME_CONTROL_PATH, _RUNTIME_CONTROL_MTIME_NS, _RUNTIME_CONTROL_CACHE
    with _RUNTIME_CONTROL_LOCK:
        _RUNTIME_CONTROL_PATH = path
        _RUNTIME_CONTROL_MTIME_NS = None
        _RUNTIME_CONTROL_CACHE = {}


def set_runtime_status_file(path: Path | None) -> None:
    global _RUNTIME_STATUS_PATH
    with _RUNTIME_STATUS_LOCK:
        _RUNTIME_STATUS_PATH = path
        _RUNTIME_HTTP_STATE["http_started"] = 0
        _RUNTIME_HTTP_STATE["http_finished"] = 0
        _RUNTIME_HTTP_STATE["http_inflight"] = 0


def get_runtime_limits() -> dict[str, int]:
    global _RUNTIME_CONTROL_MTIME_NS, _RUNTIME_CONTROL_CACHE
    defaults = {
        "gemini_key_min_gap_ms": GEMINI_KEY_MIN_GAP_MS,
        "gemini_key_max_inflight": GEMINI_KEY_MAX_INFLIGHT,
        "gemini_key_rpm_limit": GEMINI_KEY_RPM_LIMIT,
        "gemini_key_tpm_limit": GEMINI_KEY_TPM_LIMIT,
        "gemini_global_max_inflight": GEMINI_GLOBAL_MAX_INFLIGHT,
    }
    with _RUNTIME_CONTROL_LOCK:
        path = _RUNTIME_CONTROL_PATH
        if path is None or not path.exists():
            return dict(defaults)
        stat = path.stat()
        if _RUNTIME_CONTROL_MTIME_NS == stat.st_mtime_ns and _RUNTIME_CONTROL_CACHE:
            return {**defaults, **_RUNTIME_CONTROL_CACHE}
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            _RUNTIME_CONTROL_CACHE = {}
        else:
            cache: dict[str, int] = {}
            for key in defaults:
                value = payload.get(key)
                if isinstance(value, int) and value > 0:
                    cache[key] = value
            _RUNTIME_CONTROL_CACHE = cache
        _RUNTIME_CONTROL_MTIME_NS = stat.st_mtime_ns
        return {**defaults, **_RUNTIME_CONTROL_CACHE}


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z가-힣._-]+", "_", value)
    slug = slug.strip("._")
    return slug[:120] or "item"


def _count_tokens(text: str) -> int:
    if ENCODER is not None:
        return len(ENCODER.encode(text))
    return max(1, len(text) // 4)


def _estimate_token_count(text: str, *, sample_chars: int = 50000) -> int:
    if not text:
        return 0
    if len(text) <= sample_chars:
        return _count_tokens(text)
    sample = text[:sample_chars]
    sample_tokens = _count_tokens(sample)
    if sample_tokens <= 0:
        return 0
    chars_per_token = len(sample) / sample_tokens
    return max(sample_tokens, int(len(text) / max(0.1, chars_per_token)))


def load_env_value(name: str) -> str:
    value = os.environ.get(name)
    if value:
        return value.strip()
    for path in ENV_FALLBACK_FILES:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith(f"{name}="):
                return line.split("=", 1)[1].strip()
    return ""


def load_env_values(name: str) -> list[str]:
    values: list[str] = []
    raw = os.environ.get(name, "")
    if raw:
        for line in re.split(r"[\n,]+", raw):
            line = line.strip()
            if line:
                values.append(line)
    for path in ENV_FALLBACK_FILES:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith(f"{name}="):
                for part in re.split(r"[\n,]+", line.split("=", 1)[1]):
                    part = part.strip()
                    if part:
                        values.append(part)
    return list(dict.fromkeys(values))


def load_gemini_api_keys() -> list[str]:
    disable_flag = _normalize_space(os.environ.get("LEGAL_EVIDENCE_DISABLE_GEMINI_KEYS")).lower()
    if disable_flag in {"1", "true", "yes", "on"}:
        return []
    keys: list[str] = []
    for env_name in ["GEMINI_API_KEYS", "GOOGLE_API_KEYS"]:
        keys.extend(load_env_values(env_name))
    single = load_env_value("GEMINI_API_KEY")
    if single:
        keys.append(single)
    single_google = load_env_value("GOOGLE_API_KEY")
    if single_google:
        keys.append(single_google)
    return list(dict.fromkeys(key.strip() for key in keys if key.strip()))


def load_chat_api_url() -> str:
    return load_env_value("LEGAL_EVIDENCE_CHAT_API_URL") or DEFAULT_CHAT_API_URL


def load_gemini_thinking_level(model_name: str = "") -> str:
    value = _normalize_space(os.environ.get("LEGAL_EVIDENCE_GEMINI_THINKING_LEVEL")).lower()
    is_gemma = "gemma" in _normalize_space(model_name).lower()
    # 2026-04-19 발견: Gemma4 26B는 thinkingLevel:"minimal" 지원 (thinkingBudget 거부).
    # Gemma 경로에 한해 기본값 minimal 적용 → thinking tokens 0, wall ~3-5x 단축, MAX_TOKENS→STOP.
    if value in {"", "default"}:
        return "minimal" if is_gemma else "high"
    if value in {"off", "none", "disable", "disabled", "0"}:
        return ""
    if value in {"minimal", "low", "medium", "high"}:
        return value
    return "minimal" if is_gemma else "high"


def should_use_gemini_thinking(model_name: str) -> bool:
    # Gemma 포함 모든 모델에 thinkingConfig 적용 (Gemma는 minimal, Gemini는 high 등).
    return True


def compute_http_aware_backoff_ms(retry_count: int, http_status: int | None = None) -> int:
    status = http_status if isinstance(http_status, int) else None
    is_429 = status == 429
    is_5xx = status is not None and 500 <= status < 600
    if is_429:
        seq = [10000, 30000, 60000, 60000]
    elif is_5xx:
        seq = [5000, 15000, 30000, 60000]
    else:
        seq = [3000, 10000, 30000, 60000]
    idx = max(0, min(len(seq) - 1, int(retry_count or 1) - 1))
    return int(seq[idx])


def _parse_retry_after_ms(response: requests.Response) -> int | None:
    raw = response.headers.get("Retry-After")
    if not raw:
        return None
    try:
        seconds = int(raw.strip())
    except ValueError:
        return None
    if seconds <= 0:
        return None
    return seconds * 1000


def get_gemini_key_scheduler(api_keys: list[str]) -> GeminiKeyScheduler:
    key_tuple = tuple(api_keys)
    with _GEMINI_SCHEDULER_LOCK:
        scheduler = _GEMINI_SCHEDULERS.get(key_tuple)
        if scheduler is None:
            scheduler = GeminiKeyScheduler(list(key_tuple))
            _GEMINI_SCHEDULERS[key_tuple] = scheduler
        return scheduler


def classify_doc_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return "txt"
    if suffix == ".pdf":
        return "pdf"
    if suffix in {".hwp", ".hwpx"}:
        return "hwp"
    if suffix in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}:
        return "image"
    return "other"


def _line_fingerprint(line: str) -> str:
    text = line.strip()
    text = re.sub(r"\d{2,}", "<NUM>", text)
    text = re.sub(r"[A-Z]{2,}[0-9-]*", "<ID>", text)
    text = re.sub(r"\s+", " ", text)
    return text


def _iter_line_records(text: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    offset = 0
    for idx, line in enumerate(text.splitlines(keepends=True), start=1):
        bare = line.rstrip("\n")
        records.append(
            {
                "line_no": idx,
                "line_text": bare,
                "fingerprint": _line_fingerprint(bare),
                "char_start": offset,
                "char_end": offset + len(line),
            }
        )
        offset += len(line)
    return records


def find_boundary_candidates(text: str) -> list[dict[str, Any]]:
    line_records = _iter_line_records(text)
    if not line_records:
        return []

    fp_counter = Counter(record["fingerprint"] for record in line_records if record["fingerprint"])
    separator_counter = Counter(
        record["line_text"].strip() for record in line_records if SEPARATOR_RE.match(record["line_text"].strip())
    )
    key_seq_counter: Counter[tuple[str, ...]] = Counter()
    template_counter: Counter[str] = Counter()

    for idx in range(len(line_records) - 2):
        seq = []
        for record in line_records[idx : idx + 3]:
            m = JSON_KEY_RE.match(record["line_text"])
            if m:
                seq.append(m.group(1))
        if len(seq) >= 2:
            key_seq_counter[tuple(seq)] += 1

    for record in line_records:
        if HEADING_PREFIX_RE.match(record["line_text"].strip()):
            template_counter[record["fingerprint"]] += 1

    candidates: list[dict[str, Any]] = []
    for record in line_records:
        stripped = record["line_text"].strip()
        if not stripped:
            continue
        score = 0.0
        kind = "paragraph"
        if SEPARATOR_RE.match(stripped):
            if stripped in separator_counter and separator_counter[stripped] >= 2:
                score = 100 + separator_counter[stripped] * 5
                kind = "repeated_separator"
            else:
                score = 75
                kind = "separator"
        elif record["fingerprint"] in template_counter and template_counter[record["fingerprint"]] >= 2:
            score = 80 + template_counter[record["fingerprint"]] * 4
            kind = "repeated_template"
        elif HEADING_PREFIX_RE.match(stripped):
            score = 60
            kind = "heading"
        elif fp_counter[record["fingerprint"]] >= 2:
            score = 55 + fp_counter[record["fingerprint"]]
            kind = "repeated_line"
        else:
            # local schema-like key sequence support
            local_seq = []
            idx0 = record["line_no"] - 1
            for nearby in line_records[idx0 : min(idx0 + 3, len(line_records))]:
                m = JSON_KEY_RE.match(nearby["line_text"])
                if m:
                    local_seq.append(m.group(1))
            if len(local_seq) >= 2 and key_seq_counter[tuple(local_seq)] >= 2:
                score = 70 + key_seq_counter[tuple(local_seq)] * 3
                kind = "schema_sequence"
            elif record["line_text"].endswith(('.', ':')):
                score = 20
                kind = "paragraph"
        if score <= 0:
            continue
        candidates.append(
            {
                "kind": kind,
                "score": score,
                "line_no": record["line_no"],
                "char_index": record["char_start"],
                "line_text": stripped,
            }
        )
    candidates.sort(key=lambda item: (-item["score"], item["char_index"]))
    return candidates


def pick_split_index(text: str, max_tokens: int, *, search_radius_chars: int = 5000) -> int | None:
    if _count_tokens(text) <= max_tokens:
        return None
    target_ratio = max_tokens / max(1, _count_tokens(text))
    target_index = max(1, min(len(text) - 1, int(len(text) * target_ratio)))
    candidates = find_boundary_candidates(text)
    nearby = [
        c
        for c in candidates
        if abs(int(c["char_index"]) - target_index) <= search_radius_chars and 0 < int(c["char_index"]) < len(text)
    ]
    if nearby:
        nearby.sort(
            key=lambda item: (
                -float(item["score"]),
                abs(int(item["char_index"]) - target_index),
                int(item["char_index"]),
            )
        )
        return int(nearby[0]["char_index"])

    paragraph_break = text.rfind("\n\n", 0, target_index)
    if paragraph_break > 0:
        return paragraph_break + 2
    line_break = text.rfind("\n", 0, target_index)
    if line_break > 0:
        return line_break + 1
    return target_index


def chunk_document_text(
    *,
    text: str,
    max_tokens: int,
    overlap_chars: int,
    same_document_group: str,
    file_id: str = "",
    document_title: str = "",
    relative_path: str = "",
) -> list[dict[str, Any]]:
    if not text:
        return []
    chunks: list[dict[str, Any]] = []
    boundaries = sorted(find_boundary_candidates(text), key=lambda item: int(item["char_index"]))
    if len(text) <= 50_000:
        total_tokens = _count_tokens(text)
        avg_chars_per_token = max(1.0, len(text) / max(1, total_tokens))
    else:
        sample = text[:50_000]
        sample_tokens = _count_tokens(sample)
        avg_chars_per_token = max(1.0, len(sample) / max(1, sample_tokens))
    start = 0
    part = 1
    length = len(text)
    while start < length:
        max_char_guess = max(4000, int(max_tokens * avg_chars_per_token * 1.8))
        high = min(length, start + max_char_guess)
        if high >= length and _count_tokens(text[start:length]) <= max_tokens:
            end = length
            chunk_text = text[start:end]
        else:
            low = min(length, start + 1)
            best_end = low
            while low <= high:
                mid = (low + high) // 2
                candidate_tokens = _count_tokens(text[start:mid])
                if candidate_tokens <= max_tokens:
                    best_end = mid
                    low = mid + 1
                else:
                    high = mid - 1

            nearby = [
                item
                for item in boundaries
                if start < int(item["char_index"]) <= best_end + 2000 and int(item["char_index"]) >= max(start + 100, best_end - 6000)
            ]
            if nearby:
                nearby.sort(
                    key=lambda item: (
                        -float(item["score"]),
                        abs(int(item["char_index"]) - best_end),
                        int(item["char_index"]),
                    )
                )
                end = int(nearby[0]["char_index"])
            else:
                end = best_end
            if end <= start:
                end = min(length, best_end if best_end > start else start + max(1000, int(max_tokens * avg_chars_per_token)))
            chunk_text = text[start:end]
            while end < length and _count_tokens(chunk_text) > max_tokens and end > start + 100:
                end = max(start + 100, start + int((end - start) * 0.9))
                chunk_text = text[start:end]
        if not chunk_text:
            end = min(length, start + max(1000, int(max_tokens * avg_chars_per_token)))
            chunk_text = text[start:end]
        if _count_tokens(chunk_text) <= max_tokens and end < length:
            local_end = end
            paragraph_break = text.rfind("\n\n", start, local_end)
            if paragraph_break > start + 200 and paragraph_break + 2 != local_end:
                improved = text[start : paragraph_break + 2]
                if _count_tokens(improved) <= max_tokens:
                    end = paragraph_break + 2
                    chunk_text = improved
        chunks.append(
            {
                "chunk_id": f"{same_document_group}::part-{part:03d}",
                "file_id": file_id,
                "document_title": document_title,
                "same_document_group": same_document_group,
                "relative_path": relative_path,
                "start_char": start,
                "end_char": end,
                "text": chunk_text,
                "token_count": _count_tokens(chunk_text),
            }
        )
        if end >= length:
            break
        next_start = max(0, end - max(0, overlap_chars))
        if next_start <= start:
            next_start = end
        start = next_start
        part += 1
    return chunks


def parse_llm_selection_response(text: str) -> SelectionParseResult:
    raw = str(text or "")
    match = re.search(r"<selection>\s*(.*?)\s*</selection>", raw, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return SelectionParseResult(reasoning=raw.strip(), selected_ids=[])
    reasoning = raw[: match.start()].strip()
    body = match.group(1).strip()
    if re.search(r"<none\s*/>", body, flags=re.IGNORECASE):
        return SelectionParseResult(reasoning=reasoning, selected_ids=[])
    selected_ids = []
    for line in body.splitlines():
        item = line.strip().strip("-*")
        item = item.strip()
        if item:
            selected_ids.append(item)
    seen: set[str] = set()
    ordered = []
    for item in selected_ids:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return SelectionParseResult(reasoning=reasoning, selected_ids=ordered)


def _coerce_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        raw_items = value
    elif value in (None, ""):
        raw_items = []
    else:
        raw_items = [value]
    out: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        text = _normalize_space(item)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def parse_keyword_generation_response(text: str, *, keyword_count: int = 10) -> list[str]:
    raw = text.strip()
    keywords: list[str] = []
    try:
        obj = json.loads(_extract_json_block(raw))
        if isinstance(obj, dict):
            keywords = _coerce_string_list(obj.get("keywords"))
        elif isinstance(obj, list):
            keywords = _coerce_string_list(obj)
    except Exception:
        keywords = []
    if not keywords:
        for line in raw.splitlines():
            candidate = line.strip().strip("-*").strip()
            if not candidate:
                continue
            candidate = candidate.strip('"').strip("'")
            keywords.append(candidate)
    deduped: list[str] = []
    seen: set[str] = set()
    for keyword in keywords:
        normalized = _normalize_space(keyword)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
        if len(deduped) >= max(1, keyword_count):
            break
    return deduped


def _fallback_keywords_from_user_task(user_task: str, *, keyword_count: int = 10) -> list[str]:
    candidates = re.findall(r"[0-9A-Za-z가-힣]{2,20}", user_task)
    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = _normalize_space(candidate)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
        if len(deduped) >= max(1, keyword_count):
            break
    return deduped


def build_keyword_generation_prompt(user_task: str, *, keyword_count: int = 10) -> str:
    return (
        "아래 법률 질문을 기준으로 판례 검색용 핵심 키워드를 뽑아라.\n"
        "절차:\n"
        "1) 먼저 이 질문/행위가 위반하거나 관련될 수 있는 한국 법령명·죄명·규제를 최대한 나열한다.\n"
        "   예) 변호사법 위반, 부동산중개업법, 의료법, 약사법, 저작권법, 개인정보보호법,\n"
        "       자본시장법, 전자상거래법, 상표법, 공직선거법, 정보통신망법, 명예훼손, 모욕, 사기,\n"
        "       배임, 횡령, 업무방해, 무고, 공갈, 협박, 강제추행 등.\n"
        "2) 나열한 법령/죄명 중 가장 가능성 높은 것 1~3개를 키워드에 **반드시 포함**한다.\n"
        "   (법령명은 '변호사법', '의료법'처럼 짧고 정확한 한국어 명사로 쓴다)\n"
        "3) 그 외에 민사/형사 쟁점어, 유리한 포인트, 불리한 포인트를 반영해 키워드를 보강한다.\n"
        "규칙:\n"
        f"- 반드시 서로 다른 키워드/짧은 구를 정확히 {keyword_count}개 만든다.\n"
        "- 각 키워드는 한국 판례 DB에서 case_name/title 텍스트 매칭에 바로 쓸 수 있는 짧은 한국어여야 한다.\n"
        "- 영어, 'AI', '인공지능', '챗GPT' 같은 DB에 거의 없는 외래어는 피하고, 그 대신 해당 행위에 대응되는 법령/죄명으로 치환한다.\n"
        "- 너무 긴 문장 금지. 5자 이내가 이상적이며 최대 10자.\n"
        "- JSON만 출력한다.\n"
        '- 스키마: {"keywords": ["...", "..."]}\n\n'
        "예시1) 질문: \"AI로 판례 정리해서 알려주는게 불법인지\"\n"
        "  → {\"keywords\": [\"변호사법\", \"변호사법위반\", \"법률사무\", \"비변호사\", \"무자격 법률\",\n"
        "                   \"법률상담\", \"유료 상담\", \"광고 금지\", \"알선\", \"수임료\"]}\n"
        "예시2) 질문: \"카카오톡 단체방에서 욕설한 경우\"\n"
        "  → {\"keywords\": [\"모욕\", \"모욕죄\", \"명예훼손\", \"정보통신망 명예훼손\", \"공연성\",\n"
        "                   \"단체대화방\", \"특정성\", \"사실적시\", \"허위사실\", \"전파가능성\"]}\n\n"
        f"질문:\n{user_task}"
    )


def generate_search_keywords(user_task: str, *, model: str, keyword_count: int = 10) -> list[str]:
    raw = call_chat(
        [
            {"role": "system", "content": "법률 판례 검색 키워드 생성기다. JSON만 출력하라."},
            {"role": "user", "content": build_keyword_generation_prompt(user_task, keyword_count=keyword_count)},
        ],
        model=model,
        timeout=180,
    )
    keywords = parse_keyword_generation_response(raw, keyword_count=keyword_count)
    if keywords:
        return keywords
    return _fallback_keywords_from_user_task(user_task, keyword_count=keyword_count)


def _decision_date_sort_key(value: Any) -> int:
    digits = re.sub(r"[^0-9]", "", str(value or ""))
    if not digits:
        return 0
    try:
        return int(digits[:8])
    except ValueError:
        return 0


def _score_structured_precedent_row(row: dict[str, Any], keywords: list[str]) -> tuple[int, int, list[str]]:
    title_text = _normalize_space(" ".join([str(row.get("case_name") or ""), str(row.get("case_number") or "")]))
    issue_text = _normalize_space(str(row.get("issue_text") or ""))
    summary_text = _normalize_space(str(row.get("summary_text") or ""))
    full_text = _normalize_space(str(row.get("full_text") or ""))
    hit_count = 0
    weighted_score = 0
    matched_keywords: list[str] = []
    for keyword in keywords:
        needle = _normalize_space(keyword)
        if not needle:
            continue
        local_score = 0
        if needle in title_text:
            local_score += 14
        if needle in issue_text:
            local_score += 10
        if needle in summary_text:
            local_score += 8
        if needle in full_text:
            local_score += 4
        if local_score:
            hit_count += 1
            weighted_score += local_score
            matched_keywords.append(needle)
    return hit_count, weighted_score, matched_keywords


def select_top_structured_precedent_rows(
    rows: list[dict[str, Any]],
    *,
    keywords: list[str],
    top_k: int,
) -> list[dict[str, Any]]:
    scored_rows: list[dict[str, Any]] = []
    for row in rows:
        hit_count, weighted_score, matched_keywords = _score_structured_precedent_row(row, keywords)
        if hit_count <= 0:
            continue
        scored_rows.append(
            {
                **row,
                "_keyword_hit_count": hit_count,
                "_keyword_weighted_score": weighted_score,
                "_matched_keywords": matched_keywords,
                "_decision_date_sort_key": _decision_date_sort_key(row.get("decision_date")),
            }
        )
    scored_rows.sort(
        key=lambda item: (
            -int(item.get("_keyword_hit_count") or 0),
            -int(item.get("_keyword_weighted_score") or 0),
            -int(item.get("_decision_date_sort_key") or 0),
            str(item.get("case_number") or ""),
        )
    )
    return scored_rows[: max(1, top_k)]


def merge_claim_ledgers(rows: list[dict[str, Any]], *, analysis_mode: str = "document") -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if analysis_mode == "question":
            key = _normalize_space(row.get("claim_axis")) or _normalize_space(row.get("claim_text"))
        else:
            key = _normalize_space(row.get("claim_text"))
        if not key:
            continue
        grouped[key].append(row)
    merged: list[dict[str, Any]] = []
    for group_key, items in grouped.items():
        support_spans = []
        oppose_spans = []
        certainty_value = max(CERTAINTY_ORDER.values())
        section_counter: Counter[str] = Counter()
        certainty_reason_parts: list[str] = []
        same_situation_case_exists = False
        inference_basis_parts: list[str] = []
        for item in items:
            support_spans.extend(item.get("support_spans") or [])
            oppose_spans.extend(item.get("oppose_spans") or [])
            section_counter[_normalize_space(item.get("recommended_section") or "나. 사안의 경우")] += 1
            current = CERTAINTY_ORDER.get(_normalize_space(item.get("certainty")).lower(), 3)
            certainty_value = min(certainty_value, current)
            same_situation_case_exists = same_situation_case_exists or bool(item.get("same_situation_case_exists"))
            if item.get("inference_basis"):
                inference_basis_parts.append(_normalize_space(item.get("inference_basis")))
            if item.get("certainty_reason"):
                certainty_reason_parts.append(_normalize_space(item.get("certainty_reason")))
        if oppose_spans:
            certainty_value = min(certainty_value, CERTAINTY_ORDER["high"])
        if analysis_mode == "question":
            supporting_cases: list[dict[str, Any]] = []
            seen_cases: set[str] = set()
            list_fields = [
                "favorable_basis",
                "unfavorable_basis",
                "usable_favorable_logic",
                "usable_unfavorable_logic",
                "favorable_factors",
                "unfavorable_factors",
                "required_facts",
                "missing_facts",
                "cautions",
                "counter_evidence",
            ]
            merged_lists: dict[str, list[str]] = {field: [] for field in list_fields}
            context_summaries: list[str] = []
            case_summaries: list[str] = []
            stance_values: list[str] = []
            primary_item = max(
                items,
                key=lambda item: (
                    len(item.get("support_spans") or []),
                    int(bool(_normalize_space(item.get("case_number")))),
                    int(bool(_normalize_space(item.get("court")))),
                    _decision_date_sort_key(item.get("decision_date")),
                ),
            )
            for item in items:
                for field in list_fields:
                    merged_lists[field].extend(_coerce_string_list(item.get(field)))
                context_summaries.extend(_coerce_string_list(item.get("context_summary")))
                case_summaries.extend(_coerce_string_list(item.get("case_summary")))
                stance_values.extend(_coerce_string_list(item.get("stance_to_user_goal")))
                case_key = "|".join(
                    [
                        _normalize_space(item.get("case_number")),
                        _normalize_space(item.get("court")),
                        _normalize_space(item.get("decision_date")),
                        _normalize_space(item.get("case_name")),
                        _normalize_space(item.get("relative_path")),
                    ]
                )
                if case_key and case_key not in seen_cases:
                    seen_cases.add(case_key)
                    supporting_cases.append(
                        {
                            "case_number": _normalize_space(item.get("case_number")),
                            "court": _normalize_space(item.get("court")),
                            "decision_date": _normalize_space(item.get("decision_date")),
                            "case_name": _normalize_space(item.get("case_name")),
                            "document_title": _normalize_space(item.get("document_title")),
                            "relative_path": _normalize_space(item.get("relative_path")),
                        }
                    )
            if supporting_cases and len(supporting_cases) >= 2 and not oppose_spans:
                certainty_value = min(CERTAINTY_ORDER["very_high"], certainty_value + 1)
                certainty_reason_parts.append(f"동일 주장 축을 지지하는 별개 판례가 {len(supporting_cases)}건 확인되었다.")
            certainty = next((k for k, v in CERTAINTY_ORDER.items() if v == certainty_value), "medium")
            primary_support_case = supporting_cases[0] if supporting_cases else {}
            merged.append(
                {
                    "claim_axis": _normalize_space(items[0].get("claim_axis")) or group_key,
                    "claim_text": _normalize_space(items[0].get("claim_text")) or group_key,
                    "stance_to_user_goal": " / ".join(dict.fromkeys(stance_values))[:400],
                    "support_spans": _dedupe_dicts(support_spans),
                    "oppose_spans": _dedupe_dicts(oppose_spans),
                    "same_situation_case_exists": same_situation_case_exists,
                    "inference_basis": " / ".join(dict.fromkeys(inference_basis_parts))[:1200],
                    "certainty": certainty,
                    "certainty_reason": " / ".join(dict.fromkeys(certainty_reason_parts))[:1200],
                    "support_count": len(support_spans),
                    "oppose_count": len(oppose_spans),
                    "supporting_case_count": len(supporting_cases),
                    "supporting_cases": supporting_cases,
                    "source_file_id": _normalize_space(primary_item.get("source_file_id")),
                    "case_number": _normalize_space(primary_item.get("case_number")) or _normalize_space(primary_support_case.get("case_number")),
                    "court": _normalize_space(primary_item.get("court")) or _normalize_space(primary_support_case.get("court")),
                    "decision_date": _normalize_space(primary_item.get("decision_date")) or _normalize_space(primary_support_case.get("decision_date")),
                    "case_name": _normalize_space(primary_item.get("case_name")) or _normalize_space(primary_support_case.get("case_name")),
                    "document_title": _normalize_space(primary_item.get("document_title")),
                    "relative_path": _normalize_space(primary_item.get("relative_path")),
                    "context_summary": " / ".join(dict.fromkeys(context_summaries))[:2000],
                    "case_summary": " / ".join(dict.fromkeys(case_summaries))[:2000],
                    **{field: list(dict.fromkeys(values)) for field, values in merged_lists.items()},
                }
            )
            continue
        certainty = next((k for k, v in CERTAINTY_ORDER.items() if v == certainty_value), "medium")
        merged.append(
            {
                "claim_text": group_key,
                "recommended_section": section_counter.most_common(1)[0][0] if section_counter else "나. 사안의 경우",
                "support_spans": _dedupe_dicts(support_spans),
                "oppose_spans": _dedupe_dicts(oppose_spans),
                "same_situation_case_exists": same_situation_case_exists,
                "inference_basis": " / ".join(dict.fromkeys(inference_basis_parts))[:1200],
                "certainty": certainty,
                "certainty_reason": " / ".join(dict.fromkeys(certainty_reason_parts))[:1200],
                "support_count": len(support_spans),
                "oppose_count": len(oppose_spans),
            }
        )
    merged.sort(key=lambda item: (-CERTAINTY_ORDER.get(item["certainty"], 0), -item["support_count"], item["claim_text"]))
    return merged


def _normalize_quote_text(text: str) -> str:
    """Collapse all whitespace for fuzzy substring matching of LLM-quoted spans.

    LLM-produced quotes routinely differ from the original by a couple of
    whitespace or punctuation characters; normalizing both sides recovers
    those near-matches without accepting unrelated text.
    """
    return re.sub(r"\s+", "", text or "").strip()


_QUOTE_ELLIPSIS_RE = re.compile(r"\s*(?:\.{3,}|…+|\s\.\.\s)\s*")


def _fuzzy_contains(needle: str, haystack: str, threshold: float = 0.85) -> bool:
    """Return True if `needle` appears in `haystack` within `threshold` similarity.

    Strategy (cheap → expensive):
      1. Whitespace-normalized substring.
      2. Ellipsis-aware split — LLMs frequently write `"...생략..."` style
         quotes where each fragment really is an exact substring of the
         precedent. Splitting on `...` / `…` and requiring every fragment
         (length ≥ 8 after norm) to substring-match recovers those.
      3. Strided ``SequenceMatcher`` scan as final fuzzy fallback.
    """
    import difflib
    n = _normalize_quote_text(needle)
    h = _normalize_quote_text(haystack)
    if not n or not h:
        return False
    if n in h:
        return True
    # 2) ellipsis split. Handle both "..." and "…".
    raw = str(needle or "")
    parts = [p for p in _QUOTE_ELLIPSIS_RE.split(raw) if p and p.strip()]
    if len(parts) >= 2:
        substantive_raw = [p for p in parts if len(_normalize_quote_text(p)) >= 8]
        substantive = [_normalize_quote_text(p) for p in substantive_raw]
        if substantive and all(p in h for p in substantive):
            return True
        # Part-level fuzzy: accept if EVERY substantive fragment near-matches
        # some window of haystack. We use a per-part threshold (0.80) that is
        # strict enough to reject hallucinated fragments (typical ratio < 0.4)
        # while recovering light paraphrases like "경찰 병력은" vs "경찰 병력이"
        # that only differ by a char or two.
        def _part_near_match(pnorm: str) -> bool:
            if pnorm in h:
                return True
            pnlen = len(pnorm)
            if pnlen < 8 or pnlen > len(h):
                return False
            stride = max(1, pnlen // 4)
            for i in range(0, len(h) - pnlen + 1, stride):
                w = h[i : i + pnlen]
                if difflib.SequenceMatcher(None, pnorm, w, autojunk=False).ratio() >= 0.80:
                    return True
            return False
        if substantive and all(_part_near_match(p) for p in substantive):
            return True
    if len(n) > len(h):
        return False
    # 3) strided fuzzy window scan.
    nlen = len(n)
    stride = max(1, nlen // 4)
    for i in range(0, len(h) - nlen + 1, stride):
        window = h[i : i + nlen]
        if difflib.SequenceMatcher(None, n, window, autojunk=False).ratio() >= threshold:
            return True
    return False


def _span_quote_matches(span: dict[str, Any], full_text: str, threshold: float) -> bool:
    return _fuzzy_contains(str(span.get("quote") or ""), full_text, threshold)


def _split_full_text_sentences(full_text: str) -> list[tuple[str, int, int]]:
    """Split precedent full text into sentence-ish chunks with offsets.

    Returns a list of (sentence_text, start_offset, end_offset) tuples. Used
    by the deterministic force-match pass below.
    """
    if not full_text:
        return []
    out: list[tuple[str, int, int]] = []
    cursor = 0
    length = len(full_text)
    i = 0
    while i < length:
        ch = full_text[i]
        terminator = ch in (".", "?", "!", "\n")
        if not terminator and ch == "다":
            nxt = full_text[i + 1] if i + 1 < length else ""
            terminator = bool(nxt) and nxt in " \t\n.?!,;:、。)」』”’"
        if terminator:
            end = i + 1
            while end < length and full_text[end] in " \t\n.?!":
                end += 1
            segment = full_text[cursor:end]
            if len(segment.strip()) >= 8:
                out.append((segment, cursor, end))
            cursor = end
            i = end
            continue
        i += 1
    if cursor < length:
        tail = full_text[cursor:]
        if len(tail.strip()) >= 8:
            out.append((tail, cursor, length))
    return out


def _force_match_quote_to_sentence(quote: str, full_text: str, *, min_score: float = 0.45) -> tuple[str, int, int] | None:
    """Pick the single highest-similarity sentence from the precedent.

    Replaces the LLM quote with the actual sentence text from the precedent
    so downstream LLMs (planner, final writer) and frontend highlight all see
    a verbatim, hallucination-free citation.
    """
    cleaned = (quote or "").strip().strip("「」『』《》<>\"'""''『』【】[]()（）")
    if not cleaned or not full_text:
        return None
    # Cheap path: if the cleaned needle is already an exact substring, lock to
    # the smallest enclosing sentence so the highlight covers a complete
    # legal sentence rather than just the literal needle.
    direct = full_text.find(cleaned)
    sentences = _split_full_text_sentences(full_text)
    if direct >= 0 and sentences:
        for text, start, end in sentences:
            if start <= direct and end >= direct + len(cleaned):
                return text.strip(), start, end
    if not sentences:
        return None
    needle_compact = re.sub(r"\s+", "", cleaned)
    if not needle_compact:
        return None
    best: tuple[float, str, int, int] | None = None
    for text, start, end in sentences:
        cand_compact = re.sub(r"\s+", "", text)
        if not cand_compact:
            continue
        # difflib ratio is symmetric and works well for small char/whitespace
        # diffs the user explicitly described as the failure case.
        score = difflib.SequenceMatcher(None, needle_compact, cand_compact, autojunk=False).ratio()
        if best is None or score > best[0]:
            best = (score, text.strip(), start, end)
    if best is None or best[0] < min_score:
        return None
    return best[1], best[2], best[3]


def _force_match_claim_spans(claims: list[dict[str, Any]], precedent_text_by_file_id: dict[str, str]) -> dict[str, int]:
    """Pre-pass over every span: replace LLM quote with the closest real
    sentence in the precedent. Mutates claims in place. Returns counters.
    """
    counters = {"spans_replaced": 0, "spans_unchanged": 0, "spans_no_full_text": 0}
    for claim in claims:
        file_id = _normalize_space(claim.get("source_file_id") or "")
        full_text = precedent_text_by_file_id.get(file_id, "")
        if not full_text:
            counters["spans_no_full_text"] += sum(
                len(claim.get(key) or []) for key in ("support_spans", "oppose_spans")
            )
            continue
        for key in ("support_spans", "oppose_spans"):
            for span in claim.get(key) or []:
                quote = str(span.get("quote") or "").strip()
                if not quote:
                    continue
                forced = _force_match_quote_to_sentence(quote, full_text)
                if not forced:
                    counters["spans_unchanged"] += 1
                    continue
                matched_text, start_off, end_off = forced
                if matched_text and matched_text != quote:
                    span["quote"] = matched_text
                    span["_force_match_start"] = int(start_off)
                    span["_force_match_end"] = int(end_off)
                    counters["spans_replaced"] += 1
                else:
                    counters["spans_unchanged"] += 1
    return counters


def gate_and_retry_claim_spans(
    claims: list[dict[str, Any]],
    precedent_text_by_file_id: dict[str, str],
    *,
    model: str,
    fuzzy_threshold: float = 0.85,
    full_text_char_budget: int = 20000,
    per_call_span_limit: int = 12,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Span-level gate + batched retry.

    Phase 1 (gate): for every support_span in every claim, check whether the
    quote is present (possibly with minor char diffs) in the linked precedent
    full_text. Matched spans stay on the claim; unmatched spans are pulled out
    into a batched retry queue grouped by ``source_file_id``.

    Phase 2 (retry): send each precedent's unmatched quotes back to the LLM
    with the precedent's full_text. The LLM is told to rewrite each quote to
    an exact substring of the full_text, or signal that no such quote exists.
    Returned quotes are re-validated; the ones that now pass are merged back
    into their parent claim's ``support_spans``. The rest are discarded.

    Claims whose ``support_spans`` list is empty after this process are
    removed entirely so the body draft cannot cite a claim without evidence.

    Returns ``(kept_claims, stats)`` where ``stats`` reports the span-level
    gating outcome for logging.
    """
    stats = {"spans_total": 0, "spans_matched": 0, "spans_unmatched": 0, "spans_recovered": 0}
    # 1) Tag each span as matched or not. Collect retry queue by precedent.
    retry_queue: dict[str, list[tuple[int, int, dict[str, Any]]]] = defaultdict(list)
    # (claim_idx, span_idx, span_data) to route recovered quotes back.
    for ci, claim in enumerate(claims):
        file_id = _normalize_space(claim.get("source_file_id") or "")
        full_text = precedent_text_by_file_id.get(file_id, "")
        spans = claim.get("support_spans") or []
        for si, span in enumerate(spans):
            stats["spans_total"] += 1
            if not full_text:
                stats["spans_unmatched"] += 1
                if file_id:
                    retry_queue[file_id].append((ci, si, span))
                continue
            if _span_quote_matches(span, full_text, fuzzy_threshold):
                span["_quote_verified"] = True
                stats["spans_matched"] += 1
            else:
                stats["spans_unmatched"] += 1
                retry_queue[file_id].append((ci, si, span))

    # 2) Batched retry per precedent. The LLM gets (evidence_id, original quote)
    # pairs and returns (evidence_id, corrected quote) pairs it's confident in.
    for file_id, entries in retry_queue.items():
        full_text = precedent_text_by_file_id.get(file_id, "")
        if not full_text:
            continue
        # Tag each entry with a stable local id to round-trip through the LLM.
        tagged = [
            {
                "retry_id": f"R{idx}",
                "evidence_id": str(entry[2].get("evidence_id") or ""),
                "quote": str(entry[2].get("quote") or ""),
            }
            for idx, entry in enumerate(entries)
        ]
        for start in range(0, len(tagged), per_call_span_limit):
            batch_tagged = tagged[start : start + per_call_span_limit]
            prompt = (
                "아래 각 항목의 quote가 원문 full_text와 일치하지 않는다. "
                "원문에 실제로 존재하는 **연속 substring**으로 각 quote를 교정하라. "
                "원문에 해당 내용을 직접 뒷받침할 적절한 substring이 **전혀 없다면** 해당 항목은 출력 배열에서 제외한다.\n"
                "- retry_id는 그대로 유지한다\n"
                "- quote만 원문 복붙으로 교정한다\n"
                "- 지어내지 않는다\n"
                "- JSON 배열만 출력한다\n\n"
                f"[원문 full_text (precedent={file_id})]\n{full_text[:full_text_char_budget]}\n\n"
                f"[교정 대상]\n{json.dumps(batch_tagged, ensure_ascii=False, indent=2)}"
            )
            try:
                response = call_chat(
                    [
                        {"role": "system", "content": "법률 인용 교정 도구다. JSON 배열만 출력한다."},
                        {"role": "user", "content": prompt},
                    ],
                    model=model,
                    timeout=300,
                )
                block = _extract_json_block(response)
                parsed = json.loads(block) if block else []
            except Exception:
                continue
            if not isinstance(parsed, list):
                continue
            # Map retry_id -> corrected quote (validated against full_text).
            for fixed in parsed:
                if not isinstance(fixed, dict):
                    continue
                rid = str(fixed.get("retry_id") or "").strip()
                corrected = str(fixed.get("quote") or "").strip()
                if not rid or not corrected:
                    continue
                try:
                    offset = int(rid.lstrip("R"))
                except ValueError:
                    continue
                if offset < 0 or offset >= len(entries):
                    continue
                if not _fuzzy_contains(corrected, full_text, fuzzy_threshold):
                    continue
                ci, si, _span = entries[offset]
                # Merge corrected quote back onto the original span.
                claims[ci]["support_spans"][si]["quote"] = corrected
                claims[ci]["support_spans"][si]["_quote_verified"] = True
                claims[ci]["support_spans"][si]["_quote_recovered"] = True
                stats["spans_recovered"] += 1

    # 3) Drop unverified spans; drop claims left with no support_spans.
    kept: list[dict[str, Any]] = []
    for claim in claims:
        verified_spans = [s for s in (claim.get("support_spans") or []) if s.get("_quote_verified")]
        for s in verified_spans:
            s.pop("_quote_verified", None)
        if not verified_spans:
            continue
        claim["support_spans"] = verified_spans
        claim["support_count"] = len(verified_spans)
        kept.append(claim)
    stats["claims_kept"] = len(kept)
    stats["claims_dropped"] = len(claims) - len(kept)
    return kept, stats


def _dedupe_dicts(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for item in items:
        key = json.dumps(item, ensure_ascii=False, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _run(cmd: list[str], timeout: int = 600) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def _extract_hwp_text(path: Path) -> str:
    proc = _run(["hwp5txt", str(path)], timeout=600)
    if proc.returncode != 0:
        return ""
    return (proc.stdout or "").strip()


def _ocr_image(path: Path) -> str:
    proc = _run(["tesseract", str(path), "stdout", "-l", "kor+eng", "--psm", "6"], timeout=300)
    if proc.returncode != 0:
        return ""
    return (proc.stdout or "").strip()


def _extract_pdf_text(path: Path) -> str:
    out_parts: list[str] = []
    try:
        doc = fitz.open(path)
    except Exception:
        return ""
    with doc:
        for page in doc:
            text = page.get_text("text") or ""
            text = text.strip()
            if text:
                out_parts.append(text)
                continue
            # OCR fallback for image-like pages
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = Path(tmp.name)
            try:
                pix.save(tmp_path)
                ocr = _ocr_image(tmp_path)
                if ocr:
                    out_parts.append(ocr)
            finally:
                try:
                    tmp_path.unlink(missing_ok=True)
                except Exception:
                    pass
    return "\n\n".join(part for part in out_parts if part).strip()


def extract_text(path: Path) -> str:
    doc_type = classify_doc_type(path)
    if doc_type == "txt":
        return path.read_text(encoding="utf-8", errors="replace")
    if doc_type == "pdf":
        return _extract_pdf_text(path)
    if doc_type == "hwp":
        return _extract_hwp_text(path)
    if doc_type == "image":
        return _ocr_image(path)
    return ""


def _candidate_source_group(relative_path: str) -> str:
    rel = relative_path.replace("\\", "/")
    if rel in DIRECT_EVIDENCE_FILES or rel.startswith("law/증거/"):
        return "direct_evidence"
    if rel.startswith("군/법/"):
        return "regulation"
    if rel.startswith("군/군 관련 판례집/"):
        return "military_casebook"
    if rel.startswith("판례집/"):
        return "general_casebook"
    return "other"


def iter_candidate_paths(root: Path) -> list[Path]:
    candidates: list[Path] = []
    seen: set[Path] = set()
    for rel in sorted(DIRECT_EVIDENCE_FILES):
        path = root / rel
        if path.exists() and path.is_file():
            seen.add(path)
            candidates.append(path)

    for sub in [root / "군" / "법"]:
        if not sub.exists():
            continue
        for path in sorted(sub.rglob("*")):
            if not path.is_file():
                continue
            if classify_doc_type(path) not in {"txt", "pdf", "hwp"}:
                continue
            if path.suffix.lower() in {".csv", ".json"}:
                continue
            if "/양정 원본/" in path.as_posix():
                continue
            if path not in seen:
                seen.add(path)
                candidates.append(path)

    for sub in [root / "군" / "국방부"]:
        if not sub.exists():
            continue
        for path in sorted(sub.rglob("*")):
            if not path.is_file():
                continue
            if classify_doc_type(path) not in {"txt", "pdf", "hwp"}:
                continue
            name = path.name
            if any(keyword in name for keyword in DISCIPLINE_CASE_KEYWORDS) or any(
                token in name for token in ["육규_110", "육규_112", "육규_113", "육규_180", "징계", "인사"]
            ):
                if path not in seen:
                    seen.add(path)
                    candidates.append(path)

    for sub in [root / "군" / "군 관련 판례집", root / "판례집"]:
        if not sub.exists():
            continue
        for path in sorted(sub.rglob("*")):
            if not path.is_file():
                continue
            if classify_doc_type(path) != "txt":
                continue
            name = path.name
            if any(keyword in name for keyword in DISCIPLINE_CASE_KEYWORDS):
                if path not in seen:
                    seen.add(path)
                    candidates.append(path)

    for sub in [root / "군" / "군 판례"]:
        if not sub.exists():
            continue
        for path in sorted(sub.rglob("*_extracted.txt")):
            if path not in seen:
                seen.add(path)
                candidates.append(path)
    return candidates


def build_file_record(root: Path, path: Path, cache_dir: Path | None = None) -> FileRecord:
    relative_path = path.relative_to(root).as_posix()
    source_group = _candidate_source_group(relative_path)
    doc_type = classify_doc_type(path)
    file_id = "file-" + hashlib.sha1(relative_path.encode("utf-8")).hexdigest()[:12]
    cache_path = cache_dir / f"{file_id}.txt" if cache_dir else None
    extracted_text = ""
    if cache_path and cache_path.exists():
        extracted_text = cache_path.read_text(encoding="utf-8", errors="replace")
    if not extracted_text:
        extracted_text = extract_text(path)
        if cache_path:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(extracted_text, encoding="utf-8")
    anchor_text = _normalize_space(extracted_text[:DEFAULT_ANCHOR_TEXT_CHARS])
    return FileRecord(
        file_id=file_id,
        relative_path=relative_path,
        absolute_path=str(path),
        document_title=path.stem,
        doc_type=doc_type,
        source_group=source_group,
        token_count=_estimate_token_count(extracted_text),
        anchor_text=anchor_text,
        extracted_text=extracted_text,
        candidate_boundaries=find_boundary_candidates(extracted_text)[:80],
        is_direct_evidence=source_group == "direct_evidence",
        content_hash=hashlib.sha1(extracted_text.encode("utf-8", errors="replace")).hexdigest() if extracted_text else "",
    )


def _iter_joonhok_precedent_rows(structured_dir: Path) -> Iterable[dict[str, Any]]:
    import pandas as pd

    columns = ["사건명", "사건번호", "선고일자", "법원명", "판시사항", "판결요지", "전문"]
    for parquet_path in sorted(structured_dir.glob("*.parquet")):
        df = pd.read_parquet(parquet_path, columns=columns)
        for row_index, row in enumerate(df.to_dict(orient="records")):
            issue_text = str(row.get("판시사항") or "").strip()
            summary_text = str(row.get("판결요지") or "").strip()
            full_text = str(row.get("전문") or "").strip() or "\n\n".join(part for part in [issue_text, summary_text] if part)
            yield {
                "case_name": _normalize_space(row.get("사건명")),
                "case_number": _normalize_space(row.get("사건번호")),
                "decision_date": _normalize_space(row.get("선고일자")),
                "court": _normalize_space(row.get("법원명")),
                "issue_text": issue_text,
                "summary_text": summary_text,
                "full_text": full_text,
                "source_path": f"{parquet_path.as_posix()}::row-{row_index}",
                "source_dataset": structured_dir.name,
            }


def _iter_constitutional_precedent_rows(structured_dir: Path) -> Iterable[dict[str, Any]]:
    import pandas as pd

    columns = ["case_name", "case_number", "decision_date", "summary", "full_text", "issues"]
    for parquet_path in sorted(structured_dir.glob("*.parquet")):
        df = pd.read_parquet(parquet_path, columns=columns)
        for row_index, row in enumerate(df.to_dict(orient="records")):
            issue_text = _normalize_space(row.get("issues"))
            summary_text = _normalize_space(row.get("summary"))
            full_text = str(row.get("full_text") or "").strip() or "\n\n".join(part for part in [issue_text, summary_text] if part)
            yield {
                "case_name": _normalize_space(row.get("case_name")),
                "case_number": _normalize_space(row.get("case_number")),
                "decision_date": _normalize_space(row.get("decision_date")),
                "court": "헌법재판소",
                "issue_text": issue_text,
                "summary_text": summary_text,
                "full_text": full_text,
                "source_path": f"{parquet_path.as_posix()}::row-{row_index}",
                "source_dataset": structured_dir.name,
            }


def iter_structured_precedent_rows(structured_dir: Path) -> Iterable[dict[str, Any]]:
    name = structured_dir.name
    if name == "01_joonhok_precedents":
        yield from _iter_joonhok_precedent_rows(structured_dir)
        return
    if name == "05_constitutional_court":
        yield from _iter_constitutional_precedent_rows(structured_dir)
        return
    raise ValueError(f"unsupported structured precedent dir: {structured_dir}")


def structured_row_to_file_record(row: dict[str, Any]) -> FileRecord:
    case_number = _normalize_space(row.get("case_number"))
    case_name = _normalize_space(row.get("case_name"))
    court = _normalize_space(row.get("court"))
    decision_date = _normalize_space(row.get("decision_date"))
    source_path = _normalize_space(row.get("source_path"))
    full_text = str(row.get("full_text") or "").strip()
    title_parts = [part for part in [court, decision_date, case_number, case_name] if part]
    document_title = " ".join(title_parts)[:240] or case_name or case_number or source_path
    relative_path = f"structured/{_normalize_space(row.get('source_dataset'))}/{Path(source_path.split('::row-')[0]).name}::{case_number or hashlib.sha1(source_path.encode('utf-8')).hexdigest()[:8]}"
    file_id = "structured-" + hashlib.sha1(f"{source_path}|{case_number}|{case_name}".encode("utf-8")).hexdigest()[:12]
    anchor_text = _normalize_space("\n".join([case_name, str(row.get("issue_text") or ""), str(row.get("summary_text") or ""), full_text[:1500]]))
    return FileRecord(
        file_id=file_id,
        relative_path=relative_path,
        absolute_path=source_path,
        document_title=document_title,
        doc_type="txt",
        source_group="structured_precedent",
        token_count=_estimate_token_count(full_text),
        anchor_text=anchor_text[:DEFAULT_ANCHOR_TEXT_CHARS],
        extracted_text=full_text,
        candidate_boundaries=find_boundary_candidates(full_text)[:80],
        is_direct_evidence=False,
        content_hash=hashlib.sha1(full_text.encode("utf-8", errors="replace")).hexdigest() if full_text else "",
        case_number=case_number,
        court=court,
        decision_date=decision_date,
        case_name=case_name,
    )


def _best_virtual_document_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        candidate = _normalize_space(line)
        if candidate:
            return candidate[:200]
    return fallback


def split_record_on_exact_virtual_separator(record: FileRecord) -> list[FileRecord]:
    if record.doc_type != "txt":
        return [record]
    if VIRTUAL_DOC_SEPARATOR_LINE not in record.extracted_text:
        return [record]
    parts = re.split(rf"(?:\r?\n){re.escape(VIRTUAL_DOC_SEPARATOR_LINE)}(?:\r?\n)", record.extracted_text)
    cleaned = [_normalize_space(part) for part in parts]
    meaningful_parts = [part for part in parts if _normalize_space(part)]
    if len(meaningful_parts) <= 1:
        return [record]

    split_records: list[FileRecord] = []
    for index, part in enumerate(parts, start=1):
        normalized = _normalize_space(part)
        if not normalized:
            continue
        suffix = f"::virtual-{index:03d}"
        text = part if part.endswith("\n") else part + "\n"
        split_records.append(
            FileRecord(
                file_id=f"{record.file_id}{suffix}",
                relative_path=f"{record.relative_path}{suffix}",
                absolute_path=record.absolute_path,
                document_title=_best_virtual_document_title(text, f"{record.document_title} {index}"),
                doc_type=record.doc_type,
                source_group=record.source_group,
                token_count=_estimate_token_count(text),
                anchor_text=_normalize_space(text[:DEFAULT_ANCHOR_TEXT_CHARS]),
                extracted_text=text,
                candidate_boundaries=find_boundary_candidates(text)[:80],
                is_direct_evidence=record.is_direct_evidence,
                is_format_sample=record.is_format_sample,
                content_hash=hashlib.sha1(text.encode("utf-8", errors="replace")).hexdigest() if text else "",
                duplicate_paths=list(record.duplicate_paths),
            )
        )
    return split_records or [record]


def call_chat(messages: list[dict[str, Any]], *, model: str, api_url: str | None = None, timeout: int = 300) -> str:
    if load_gemini_api_keys():
        return _call_gemini_generate_content(messages, model=model, timeout=timeout)
    resolved_api_url = api_url or load_chat_api_url()
    payload = {"model": model, "messages": messages, "temperature": 0.1}
    response = requests.post(resolved_api_url, json=payload, timeout=min(timeout, 600))
    response.raise_for_status()
    obj = response.json()
    return str(obj.get("choices", [{}])[0].get("message", {}).get("content", "") or "")


def _call_gemini_generate_content(messages: list[dict[str, Any]], *, model: str, timeout: int = 300, thinking_level: str = "") -> str:
    api_keys = load_gemini_api_keys()
    if not api_keys:
        raise RuntimeError("No Gemini API keys found in environment or fallback env file")
    scheduler = get_gemini_key_scheduler(api_keys)

    system_parts = []
    contents = []
    for message in messages:
        role = str(message.get("role") or "user")
        content = str(message.get("content") or "")
        if not content:
            continue
        if role == "system":
            system_parts.append(content)
            continue
        gemini_role = "model" if role == "assistant" else "user"
        contents.append({"role": gemini_role, "parts": [{"text": content}]})
    if not contents:
        contents = [{"role": "user", "parts": [{"text": ""}]}]

    last_error: str | None = None
    model_chain = list(dict.fromkeys([model, *DIRECT_CHAT_MODEL_FALLBACKS.get(model, [])]))
    missing_models: set[str] = set()
    started_at_s = time.monotonic()
    status_path = _RUNTIME_STATUS_PATH
    estimated_prompt_tokens = 0
    for part in system_parts:
        estimated_prompt_tokens += _estimate_token_count(part)
    for item in contents:
        for part in item.get("parts") or []:
            estimated_prompt_tokens += _estimate_token_count(str(part.get("text") or ""))
    for _ in range(GEMINI_GLOBAL_RETRY_ROUNDS):
        saw_transient = False
        for model_name in model_chain:
            if model_name in missing_models:
                continue
            generation_config: dict[str, Any] = {"temperature": 0.1}
            # Per-call override: caller passes `thinking_level="high"` to
                # boost thinking depth for that single LLM call (e.g. Beta-7
                # selector seed keyword generation). Empty string falls back
                # to the global default loaded from env.
            effective_thinking_level = thinking_level or load_gemini_thinking_level(model_name=model_name)
            if effective_thinking_level and should_use_gemini_thinking(model_name):
                generation_config["thinkingConfig"] = {"thinkingLevel": effective_thinking_level}
            payload: dict[str, Any] = {
                "contents": contents,
                "generationConfig": generation_config,
            }
            if system_parts:
                payload["systemInstruction"] = {"parts": [{"text": "\n\n".join(system_parts)}]}
            for _ in range(len(api_keys)):
                attempt_timeout_cap_s = select_generate_timeout_cap(
                    model_name,
                    estimated_prompt_tokens=estimated_prompt_tokens,
                )
                request_timeout_s = compute_attempt_timeout_seconds(
                    total_timeout_s=float(timeout),
                    started_at_s=started_at_s,
                    now_s=time.monotonic(),
                    per_attempt_cap_s=attempt_timeout_cap_s,
                )
                if request_timeout_s is None:
                    raise RuntimeError(
                        f"Gemini logical timeout exhausted for {model}; last_error={last_error or 'none'}"
                    )
                api_key = scheduler.acquire(est_tokens=estimated_prompt_tokens)
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
                headers = {"x-goog-api-key": api_key}
                transient = False
                retry_after_ms = None
                record_runtime_http_activity(
                    status_path,
                    event="start",
                    kind="generateContent",
                    model_name=model_name,
                    detail=f"timeout={request_timeout_s:.1f}s",
                )
                try:
                    response = requests.post(url, json=payload, headers=headers, timeout=request_timeout_s)
                except requests.RequestException as exc:
                    last_error = f"{model_name}: request failed: {_safe_http_exception_detail(exc)}"
                    transient = True
                    saw_transient = True
                    scheduler.complete(api_key, success=False, transient=transient, retry_after_ms=retry_after_ms, http_status=None)
                    record_runtime_http_activity(
                        status_path,
                        event="finish",
                        kind="generateContent",
                        model_name=model_name,
                        detail=f"request_exception: {type(exc).__name__}",
                    )
                    continue
                if response.status_code == 404:
                    last_error = f"{model_name}: HTTP 404"
                    scheduler.complete(api_key, success=False, transient=False, retry_after_ms=None, http_status=404)
                    record_runtime_http_activity(
                        status_path,
                        event="finish",
                        kind="generateContent",
                        model_name=model_name,
                        detail="http_404",
                    )
                    missing_models.add(model_name)
                    break
                if response.status_code in {429, 500, 502, 503, 504}:
                    last_error = f"{model_name}: HTTP {response.status_code}"
                    transient = True
                    saw_transient = True
                    retry_after_ms = _parse_retry_after_ms(response)
                    scheduler.complete(api_key, success=False, transient=transient, retry_after_ms=retry_after_ms, http_status=response.status_code)
                    record_runtime_http_activity(
                        status_path,
                        event="finish",
                        kind="generateContent",
                        model_name=model_name,
                        detail=f"http_{response.status_code}",
                    )
                    continue
                try:
                    response.raise_for_status()
                except requests.RequestException as exc:
                    last_error = f"{model_name}: {_safe_http_exception_detail(exc)}"
                    transient = True
                    saw_transient = True
                    retry_after_ms = _parse_retry_after_ms(response)
                    scheduler.complete(api_key, success=False, transient=transient, retry_after_ms=retry_after_ms, http_status=response.status_code)
                    record_runtime_http_activity(
                        status_path,
                        event="finish",
                        kind="generateContent",
                        model_name=model_name,
                        detail=f"http_exception: {response.status_code}",
                    )
                    continue
                obj = response.json()
                parts = obj.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                text = "".join(str(part.get("text") or "") for part in parts)
                scheduler.complete(api_key, success=True, transient=False, retry_after_ms=None, http_status=response.status_code)
                record_runtime_http_activity(
                    status_path,
                    event="finish",
                    kind="generateContent",
                    model_name=model_name,
                    detail="success" if text else "empty_body",
                )
                if text:
                    return text
                last_error = f"{model_name}: empty response body"
        if not saw_transient:
            break
    raise RuntimeError(f"No supported Gemini chat model available for {model}; last_error={last_error or 'none'}")


def call_gemini_embedding(text: str, *, model: str = DEFAULT_EMBED_MODEL) -> list[float]:
    api_keys = load_gemini_api_keys()
    if not api_keys:
        raise RuntimeError("No Gemini API keys found in environment or fallback env file")
    scheduler = get_gemini_key_scheduler(api_keys)

    cache_key = hashlib.sha1(f"{model}\n{text}".encode("utf-8")).hexdigest()
    cache_path = EMBED_CACHE_DIR / f"{cache_key}.json"
    if cache_path.exists():
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        if isinstance(cached, list):
            return cached
        values = list(cached.get("values") or [])
        if values:
            return values

    last_error: str | None = None
    fallback_chain = list(
        dict.fromkeys(
            [
                model,
                *EMBED_MODEL_FALLBACKS.get(model, []),
                DEFAULT_EMBED_MODEL,
                *EMBED_MODEL_FALLBACKS.get(DEFAULT_EMBED_MODEL, []),
                "gemini-embedding-001",
            ]
        )
    )
    missing_models: set[str] = set()
    for _ in range(GEMINI_GLOBAL_RETRY_ROUNDS):
        saw_transient = False
        for model_name in fallback_chain:
            if model_name in missing_models:
                continue
            payload = {
                "model": f"models/{model_name}",
                "taskType": "SEMANTIC_SIMILARITY",
                "content": {"parts": [{"text": text}]},
            }
            for _ in range(len(api_keys)):
                api_key = scheduler.acquire(est_tokens=_estimate_token_count(text))
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:embedContent"
                headers = {"x-goog-api-key": api_key}
                transient = False
                retry_after_ms = None
                try:
                    response = requests.post(url, json=payload, headers=headers, timeout=60)
                except requests.RequestException as exc:
                    last_error = f"{model_name}: request failed: {_safe_http_exception_detail(exc)}"
                    transient = True
                    saw_transient = True
                    scheduler.complete(api_key, success=False, transient=transient, retry_after_ms=retry_after_ms, http_status=None)
                    continue
                if response.status_code == 404:
                    last_error = f"{model_name}: HTTP 404"
                    scheduler.complete(api_key, success=False, transient=False, retry_after_ms=None, http_status=404)
                    missing_models.add(model_name)
                    break
                if response.status_code in {429, 500, 502, 503, 504}:
                    last_error = f"{model_name}: HTTP {response.status_code}"
                    transient = True
                    saw_transient = True
                    retry_after_ms = _parse_retry_after_ms(response)
                    scheduler.complete(api_key, success=False, transient=transient, retry_after_ms=retry_after_ms, http_status=response.status_code)
                    continue
                try:
                    response.raise_for_status()
                except requests.RequestException as exc:
                    last_error = f"{model_name}: {_safe_http_exception_detail(exc)}"
                    transient = True
                    saw_transient = True
                    retry_after_ms = _parse_retry_after_ms(response)
                    scheduler.complete(api_key, success=False, transient=transient, retry_after_ms=retry_after_ms, http_status=response.status_code)
                    continue
                obj = response.json()
                values = list(obj.get("embedding", {}).get("values") or [])
                if values:
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    cache_path.write_text(json.dumps({"resolved_model": model_name, "values": values}), encoding="utf-8")
                    scheduler.complete(api_key, success=True, transient=False, retry_after_ms=None, http_status=response.status_code)
                    return values
                scheduler.complete(api_key, success=True, transient=False, retry_after_ms=None, http_status=response.status_code)
                last_error = f"{model_name}: empty embedding values"
        if not saw_transient:
            break
    raise RuntimeError(f"No supported Gemini embedding model available; last_error={last_error or 'none'}")


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return -1.0
    num = sum(x * y for x, y in zip(a, b))
    den_a = math.sqrt(sum(x * x for x in a))
    den_b = math.sqrt(sum(y * y for y in b))
    if not den_a or not den_b:
        return -1.0
    return num / (den_a * den_b)


def _render_anchor_block(records: list[FileRecord]) -> str:
    lines: list[str] = []
    for record in records:
        lines.extend(
            [
                f"[{record.file_id}] {record.document_title}",
                f"- relative_path: {record.relative_path}",
                f"- source_group: {record.source_group}",
                f"- token_count: {record.token_count}",
                f"- anchor: {record.anchor_text[:1200] or '(empty)'}",
                "",
            ]
        )
    return "\n".join(lines).strip()


def pack_text_blocks(blocks: list[tuple[str, str]], *, max_tokens: int) -> list[list[tuple[str, str]]]:
    packs: list[list[tuple[str, str]]] = []
    current: list[tuple[str, str]] = []
    current_tokens = 0
    for key, text in blocks:
        tokens = _count_tokens(text)
        if current and current_tokens + tokens > max_tokens:
            packs.append(current)
            current = []
            current_tokens = 0
        current.append((key, text))
        current_tokens += tokens
    if current:
        packs.append(current)
    return packs


def _run_llm_file_select_pack(
    pack_index: int,
    pack_total: int,
    pack: list[tuple[str, str]],
    *,
    user_task: str,
    model: str,
) -> tuple[int, SelectionParseResult]:
    processing_requirements = build_processing_analysis_requirements()
    print(f"[select] llm pack {pack_index}/{pack_total}", flush=True)
    prompt = (
        "당신은 징계 의견서 작성을 위한 파일 선별기다.\n"
        "규칙:\n"
        "- 아래 파일 anchor들 중 관련 파일만 고른다.\n"
        "- 찬성 근거뿐 아니라 반대 근거가 될 파일도 고른다.\n"
        f"- 추가 지침: {processing_requirements}\n"
        "- 설명을 먼저 쓰고, 마지막에는 반드시 <selection> ... </selection> 블록만 따로 낸다.\n"
        "- <selection> 안에는 file_id만 한 줄에 하나씩 적는다.\n"
        "- 관련 파일이 없으면 <none/> 만 넣는다.\n\n"
        f"사용자 과제:\n{user_task}\n\n"
        f"파일 묶음 {pack_index}/{pack_total}:\n" + "\n\n".join(text for _, text in pack)
    )
    raw = call_chat(
        [
            {"role": "system", "content": "법률 파일 선택을 정확히 수행하고, 지정한 선택 블록 형식을 반드시 지켜라."},
            {"role": "user", "content": prompt},
        ],
        model=model,
    )
    parsed = parse_llm_selection_response(raw)
    print(
        f"[select] llm pack {pack_index}/{pack_total} selected={len(parsed.selected_ids)}",
        flush=True,
    )
    return pack_index, parsed


def run_llm_file_select(records: list[FileRecord], *, user_task: str, model: str) -> tuple[list[str], list[str]]:
    blocks = [(record.file_id, _render_anchor_block([record])) for record in records]
    packs = pack_text_blocks(blocks, max_tokens=DEFAULT_LLM_SELECT_PACK_TOKENS)
    selected: list[str] = []
    reasons: list[str] = []
    results: dict[int, SelectionParseResult] = {}
    max_workers = max(1, min(4, len(packs)))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(
                _run_llm_file_select_pack,
                index,
                len(packs),
                pack,
                user_task=user_task,
                model=model,
            ): index
            for index, pack in enumerate(packs, start=1)
        }
        for future in as_completed(future_map):
            index, parsed = future.result()
            results[index] = parsed
    for index in range(1, len(packs) + 1):
        parsed = results[index]
        reasons.append(parsed.reasoning)
        selected.extend(parsed.selected_ids)
    selected = list(dict.fromkeys(selected))
    return selected, reasons


def build_embedding_queries(user_task: str) -> list[str]:
    return [
        user_task,
        "징계권자가 일부 비위사실을 이미 알고 있었는데 당시 징계하지 않고 나중에 다른 비위와 합산해 징계할 수 있는지",
        "선행 인지 후 미조치 비위를 후행 비위와 합산한 징계의 적법성",
        "징계권자의 선행 인지, 신뢰보호, 비례, 이중평가, 추가징계 관련 판례와 규정",
        "군인 징계령 군인사법 징계규정 인사관리 규정 중 선행 인지 비위와 후행 합산 징계 관련 규정",
    ]


def _score_record_for_embedding_select(record: FileRecord, query_vectors: list[list[float]]) -> tuple[str, float, dict[str, Any]]:
    anchor_text = f"{record.document_title}\n{record.relative_path}\n{record.anchor_text[:1500]}"
    vector = call_gemini_embedding(anchor_text)
    score = max((cosine_similarity(vector, qv) for qv in query_vectors), default=-1.0)
    detail = {"score": score, "title": record.document_title, "relative_path": record.relative_path}
    return record.file_id, score, detail


def select_embedding_candidates(
    records: list[FileRecord],
    scored: list[tuple[str, float]],
    *,
    top_k: int,
) -> tuple[list[str], dict[str, Any]]:
    if not scored:
        direct_ids = [record.file_id for record in records if record.is_direct_evidence]
        return direct_ids, {"adaptive_floor": 0.0, "pool_target_rank": 0, "group_counts": {}, "selected_ranked": []}

    record_by_id = {record.file_id: record for record in records}
    direct_ids = [record.file_id for record in records if record.is_direct_evidence]
    direct_set = set(direct_ids)
    remaining_slots = max(0, top_k - len(direct_ids))
    if remaining_slots == 0:
        return direct_ids[:top_k], {
            "adaptive_floor": 0.0,
            "pool_target_rank": 0,
            "group_counts": {"direct_evidence": len(direct_ids[:top_k])},
            "selected_ranked": [(fid, next((score for sid, score in scored if sid == fid), 0.0)) for fid in direct_ids[:top_k]],
        }

    pool_target_rank = min(len(scored), max(remaining_slots * 2, remaining_slots + 4))
    nth_score = scored[pool_target_rank - 1][1]
    top_score = scored[0][1]
    adaptive_floor = max(0.70, nth_score, top_score - 0.08)

    non_direct_scored = [(file_id, score) for file_id, score in scored if file_id not in direct_set]
    candidate_scored = [(file_id, score) for file_id, score in non_direct_scored if score >= adaptive_floor]
    if len(candidate_scored) < remaining_slots:
        candidate_scored = non_direct_scored[: min(len(non_direct_scored), max(remaining_slots * 2, remaining_slots + 4))]

    group_buckets: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for file_id, score in candidate_scored:
        group = record_by_id[file_id].source_group
        group_buckets[group].append((file_id, score))

    group_order = [group for group in EMBED_GROUP_ORDER if group_buckets.get(group)]
    extras = sorted(
        [group for group in group_buckets if group not in EMBED_GROUP_ORDER],
        key=lambda group: group_buckets[group][0][1],
        reverse=True,
    )
    group_order.extend(extras)
    group_caps = {
        group: max(1, math.ceil(remaining_slots * EMBED_GROUP_CAP_RATIO.get(group, 0.25)))
        for group in group_order
    }

    selected_ranked: list[tuple[str, float]] = []
    selected_ids: set[str] = set()
    group_counts: Counter[str] = Counter()
    progress = True
    while len(selected_ranked) < remaining_slots and progress:
        progress = False
        for group in group_order:
            bucket = group_buckets[group]
            while bucket and bucket[0][0] in selected_ids:
                bucket.pop(0)
            if not bucket:
                continue
            if group_counts[group] >= group_caps[group]:
                continue
            file_id, score = bucket.pop(0)
            selected_ranked.append((file_id, score))
            selected_ids.add(file_id)
            group_counts[group] += 1
            progress = True
            if len(selected_ranked) >= remaining_slots:
                break

    for file_id, score in candidate_scored:
        if len(selected_ranked) >= remaining_slots:
            break
        if file_id in selected_ids:
            continue
        selected_ranked.append((file_id, score))
        selected_ids.add(file_id)
        group_counts[record_by_id[file_id].source_group] += 1

    for file_id, score in non_direct_scored:
        if len(selected_ranked) >= remaining_slots:
            break
        if file_id in selected_ids:
            continue
        selected_ranked.append((file_id, score))
        selected_ids.add(file_id)
        group_counts[record_by_id[file_id].source_group] += 1

    final_selected = list(dict.fromkeys(direct_ids + [file_id for file_id, _ in selected_ranked]))
    return final_selected, {
        "adaptive_floor": adaptive_floor,
        "pool_target_rank": pool_target_rank,
        "group_counts": dict(group_counts),
        "selected_ranked": selected_ranked,
    }


def run_embedding_file_select(
    records: list[FileRecord],
    *,
    user_task: str,
    top_k: int = 18,
    workers: int = DEFAULT_EMBED_WORKERS,
) -> tuple[list[str], dict[str, Any]]:
    query_vectors = [call_gemini_embedding(q) for q in build_embedding_queries(user_task)]
    scored = []
    details = {}
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(records)))) as executor:
        future_map = {
            executor.submit(_score_record_for_embedding_select, record, query_vectors): record.file_id for record in records
        }
        for future in as_completed(future_map):
            file_id, score, detail = future.result()
            scored.append((file_id, score))
            details[file_id] = detail
    scored.sort(key=lambda item: item[1], reverse=True)
    selected, selection_meta = select_embedding_candidates(records, scored, top_k=max(1, min(top_k, len(scored))))
    return selected, {
        "scores": details,
        "selected_ranked": selection_meta["selected_ranked"],
        "adaptive_floor": selection_meta["adaptive_floor"],
        "pool_target_rank": selection_meta["pool_target_rank"],
        "group_counts": selection_meta["group_counts"],
    }


def _quote_obj(quote: str, chunk: ChunkRecord) -> dict[str, Any]:
    quote = quote.strip()
    # 1) exact match
    idx = chunk.text.find(quote)
    if idx >= 0:
        return {
            "quote": quote,
            "char_start": chunk.start_char + idx,
            "char_end": chunk.start_char + idx + len(quote),
            "resolved_text": chunk.text[idx:idx + len(quote)],
            "resolved": True,
            "resolution_method": "exact",
        }
    # 2) normalized-space match
    compact_quote = _normalize_space(quote)
    compact_text = _normalize_space(chunk.text)
    idx = compact_text.find(compact_quote)
    if idx >= 0:
        return {
            "quote": quote,
            "char_start": chunk.start_char + idx,
            "char_end": chunk.start_char + idx + len(quote),
            "resolved_text": compact_text[idx:idx + len(compact_quote)],
            "resolved": True,
            "resolution_method": "normalized",
        }
    # 3) relaxed fallback: head/tail anchor probe (Gemma paraphrased quote)
    for probe_len in (40, 30, 20):
        if len(compact_quote) >= probe_len:
            head = compact_quote[:probe_len]
            tail = compact_quote[-probe_len:]
            for piece, is_head in ((head, True), (tail, False)):
                jdx = compact_text.find(piece)
                if jdx >= 0:
                    span_len = min(len(compact_quote), 400)
                    if is_head:
                        start = jdx
                    else:
                        start = max(0, jdx + probe_len - span_len)
                    end = min(len(compact_text), start + span_len)
                    return {
                        "quote": quote,
                        "char_start": chunk.start_char + start,
                        "char_end": chunk.start_char + end,
                        "resolved_text": compact_text[start:end],
                        "resolved": True,
                        "resolution_method": f"relaxed_anchor_{probe_len}",
                    }
    # 4) fuzzy fallback: 문자 trigram 슬라이딩 최대 overlap 윈도우 선택
    # "아무튼 매치안된채로 놔두고너 넘어가는건 금지" 원칙 — 가장 가까운 원문 구간 채택
    if compact_text and compact_quote:
        q_len = max(30, min(400, len(compact_quote)))
        q_trigrams: dict[str, int] = {}
        for i in range(len(compact_quote) - 2):
            tri = compact_quote[i:i + 3]
            q_trigrams[tri] = q_trigrams.get(tri, 0) + 1
        if q_trigrams:
            best_start = -1
            best_score = 0.0
            step = max(1, q_len // 20)
            for s in range(0, max(1, len(compact_text) - q_len + 1), step):
                window = compact_text[s:s + q_len]
                hit = 0
                w_seen: dict[str, int] = {}
                for i in range(len(window) - 2):
                    tri = window[i:i + 3]
                    if tri in q_trigrams:
                        w_seen[tri] = w_seen.get(tri, 0) + 1
                        if w_seen[tri] <= q_trigrams[tri]:
                            hit += 1
                total_tri = max(1, len(compact_quote) - 2)
                score = hit / total_tri
                if score > best_score:
                    best_score = score
                    best_start = s
            if best_start >= 0 and best_score >= 0.30:
                end = min(len(compact_text), best_start + q_len)
                return {
                    "quote": quote,
                    "char_start": chunk.start_char + best_start,
                    "char_end": chunk.start_char + end,
                    "resolved_text": compact_text[best_start:end],
                    "resolved": True,
                    "resolution_method": f"fuzzy_trigram_{best_score:.2f}",
                }
    return {
        "quote": quote,
        "char_start": chunk.start_char,
        "char_end": chunk.start_char + min(len(quote), len(chunk.text)),
        "resolved": False,
    }


def _default_evidence_prefix(chunk: ChunkRecord) -> str:
    candidate = Path(chunk.relative_path).stem.strip()
    if candidate:
        return candidate
    candidate = str(chunk.document_title or "").strip()
    return candidate or chunk.file_id


def _default_evidence_prefix_from_fields(*, relative_path: str, document_title: str, file_id: str) -> str:
    candidate = Path(relative_path).stem.strip()
    if candidate:
        return candidate
    candidate = str(document_title or "").strip()
    return candidate or file_id


def _coerce_evidence_spans(entries: list[Any], chunk: ChunkRecord, *, default_prefix: str | None = None) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    base = default_prefix or _default_evidence_prefix(chunk)
    for index, entry in enumerate(entries, start=1):
        evidence_id = ""
        quote = ""
        if isinstance(entry, dict):
            evidence_id = _normalize_space(entry.get("evidence_id"))
            quote = str(entry.get("quote") or "")
        else:
            quote = str(entry or "")
        quote = quote.strip()
        if not quote:
            continue
        span = _quote_obj(quote, chunk)
        if not span.get("resolved"):
            continue
        span["evidence_id"] = evidence_id or f"{base}-근거{index}"
        spans.append(span)
    return spans


def _chunk_source_lookup(chunk: ChunkRecord) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    if chunk.source_segments:
        for segment in chunk.source_segments:
            file_id = _normalize_space(segment.get("file_id"))
            if file_id:
                lookup[file_id] = segment
    if not lookup:
        lookup[chunk.file_id] = {
            "file_id": chunk.file_id,
            "document_title": chunk.document_title,
            "relative_path": chunk.relative_path,
            "case_number": chunk.case_number,
            "court": chunk.court,
            "decision_date": chunk.decision_date,
            "case_name": chunk.case_name,
            "text": chunk.text,
            "excerpt": " ".join(chunk.text.split())[:220],
        }
    return lookup


def _extract_json_block(text: str) -> str:
    fenced = re.findall(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", text, flags=re.DOTALL)
    if fenced:
        return fenced[0]
    candidates: list[tuple[int, int, str]] = []
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        start = text.find(start_char)
        end = text.rfind(end_char)
        if start >= 0 and end > start:
            candidates.append((start, end, text[start : end + 1]))
    if candidates:
        candidates.sort(key=lambda item: item[0])
        return candidates[0][2]
    raise ValueError("No JSON block found")


def _normalize_chunk_analysis_obj(obj: Any) -> dict[str, Any]:
    if isinstance(obj, list):
        return {"claims_proposed": obj}
    if isinstance(obj, dict):
        claims = obj.get("claims_proposed")
        if isinstance(claims, list):
            return obj
        claim_cards = obj.get("claim_cards")
        if isinstance(claim_cards, list):
            normalized = dict(obj)
            normalized["claims_proposed"] = claim_cards
            return normalized
    return {"claims_proposed": []}


def build_processing_analysis_requirements() -> str:
    return (
        "사용자의 요구사항에 부합하기 위해서 자료를 해석하고 분석할 것.\n"
        "꼭 사용자에게 유리한쪽으로만 해석하지말고, 객관적으로 해석하여 불리하다면 불리하다고 말하고 그 구체적 이유를 말해야 한다.\n"
        "판단하기 어렵다면 어려운 이유를 설명하고, 불리하다면 그럼에도 최대한 유리하게 만들 수 있는 실제 사례 기반 대응 방향이 있는지 함께 찾아야 한다."
    )


def analyze_chunk(
    chunk: ChunkRecord,
    *,
    user_task: str,
    model: str,
    analysis_mode: str = "document",
) -> dict[str, Any]:
    processing_requirements = build_processing_analysis_requirements()
    source_lookup = _chunk_source_lookup(chunk)
    source_manifest = "\n".join(
        f"- {source_id}: {segment.get('case_number') or '(불명)'} / {segment.get('court') or '(불명)'} / {segment.get('decision_date') or '(불명)'} / {segment.get('case_name') or segment.get('document_title') or ''}"
        for source_id, segment in source_lookup.items()
    )
    if analysis_mode == "question":
        prompt = (
            "아래는 법률 질문에 대응하기 위해 검토하는 판례의 일부 또는 전체 청크다.\n"
            "반드시 JSON만 출력하라.\n"
            "규칙:\n"
            "- 이 청크만으로 뒷받침되는 주장 카드만 적는다.\n"
            "- 청크 안에 여러 판례 조각이 들어 있을 수 있다. 각 주장 카드마다 반드시 source_file_id를 적어 어느 판례 조각에서 나온 주장인지 명시한다.\n"
            "- source_file_id는 아래 source manifest에 나온 값 중 하나만 사용한다.\n"
            "- support_evidence, oppose_evidence는 청크 원문에서 정확히 복붙한 짧은 인용과 evidence_id를 함께 넣는다.\n"
            "- support_evidence는 반드시 최소 1개 이상 있어야 한다. 정확한 짧은 인용을 고를 수 없으면 그 주장은 쓰지 말라.\n"
            "- evidence_id는 지어내지 말고 문서 제목 또는 확정 가능한 판례명을 바탕으로 `...-근거N` 형식으로 쓴다.\n"
            "- 이 청크에서 확인되지 않는 요소는 지어내지 말고 빈 배열 또는 빈 문자열로 남긴다.\n"
            "- 최소 필수는 source_file_id, claim_axis, claim_text, stance_to_user_goal, context_summary, support_evidence, certainty다.\n"
            "- case_summary는 판례의 결론과 핵심 이유가 드러나게 1~2문장으로 적는다. 추상 법리만 적지 말라.\n"
            "- 추가 필드는 최소화하라. 확실하지 않으면 억지로 채우지 말라.\n"
            "- 관련이 없으면 claims_proposed를 빈 배열로 둔다.\n"
            f"- 추가 지침: {processing_requirements}\n"
            "certainty는 very_high/high/medium/low/speculative 중 하나다.\n\n"
            f"사용자 질문:\n{user_task}\n\n"
            f"문서 제목: {chunk.document_title}\n"
            f"경로: {chunk.relative_path}\n"
            f"판례번호: {chunk.case_number or '(불명)'}\n"
            f"법원: {chunk.court or '(불명)'}\n"
            f"선고일자: {chunk.decision_date or '(불명)'}\n"
            f"사건명: {chunk.case_name or '(불명)'}\n"
            f"청크 ID: {chunk.chunk_id}\n\n"
            "source manifest:\n"
            f"{source_manifest}\n\n"
            "청크 원문:\n"
            f"{chunk.text}\n\n"
            "출력 JSON 스키마:\n"
            "{\n"
            '  "claims_proposed": [\n'
            "    {\n"
            '      "source_file_id": "...",\n'
            '      "claim_axis": "...",\n'
            '      "claim_text": "...",\n'
            '      "stance_to_user_goal": "유리 | 불리 | 혼합",\n'
            '      "context_summary": "...",\n'
            '      "case_summary": "...",\n'
            '      "support_evidence": [{"evidence_id": "...-근거1", "quote": "..."}],\n'
            '      "oppose_evidence": [{"evidence_id": "...-근거1", "quote": "..."}],\n'
            '      "same_situation_case_exists": true,\n'
            '      "inference_basis": "",\n'
            '      "certainty": "medium",\n'
            '      "certainty_reason": "..."\n'
            "    }\n"
            "  ]\n"
            "}"
        )
    else:
        prompt = (
            "아래는 징계 의견서 작성을 위한 법률 자료의 일부 청크다.\n"
            "반드시 JSON만 출력하라.\n"
            "규칙:\n"
            "- 이 청크에서만 뒷받침되는 claim만 적는다.\n"
            "- claim도 네가 작성한다.\n"
            "- support_evidence, oppose_evidence는 청크 원문에서 정확히 복붙한 짧은 인용과 evidence_id를 함께 넣는다.\n"
            "- evidence_id는 지어내지 말고, 인용이 가장 직접적으로 속한 고유한 출처명을 써라.\n"
            "- 판례 일부면 `대법원 2002. 9. 24. 선고 2002두6620 판결-근거1`처럼 정확한 판결명+근거번호로 쓴다.\n"
            "- 규정/법률 일부면 `군인사법-근거2`, `육군규정 180-근거3`처럼 정확한 규정명/법률명+근거번호로 쓴다.\n"
            "- `지방법원판례`, `규정`, `판례집`처럼 포괄적이고 비고유한 이름은 금지한다.\n"
            "- 청크 안에서 더 구체적인 출처명을 확정할 수 없으면 문서 제목 또는 원본 파일명을 그대로 쓰고 `-근거N`을 붙인다.\n"
            "- 근거가 없으면 확신하지 말고 certainty를 낮춘다.\n"
            "- 같은 상황의 직접 적용 판례/규정인지, 유추인지 구분한다.\n"
            "- 반대 근거가 있으면 반드시 oppose_evidence에 넣는다.\n"
            "- 관련이 없으면 claims_proposed를 빈 배열로 둔다.\n"
            f"- 추가 지침: {processing_requirements}\n"
            "certainty는 very_high/high/medium/low/speculative 중 하나다.\n\n"
            f"사용자 과제:\n{user_task}\n\n"
            f"문서 제목: {chunk.document_title}\n"
            f"경로: {chunk.relative_path}\n"
            f"원본 파일명: {Path(chunk.relative_path).name}\n"
            f"청크 ID: {chunk.chunk_id}\n\n"
            "청크 원문:\n"
            f"{chunk.text}\n\n"
            "출력 JSON 스키마:\n"
            "{\n"
            '  "claims_proposed": [\n'
            "    {\n"
            '      "claim_text": "...",\n'
            '      "recommended_section": "가. 관련 법령 및 판례 | 나. 사안의 적용 | 다. 반대논리 및 그 한계 | 4. 결어",\n'
            '      "support_evidence": [{"evidence_id": "...-근거1", "quote": "..."}],\n'
            '      "oppose_evidence": [{"evidence_id": "...-근거1", "quote": "..."}],\n'
            '      "same_situation_case_exists": true,\n'
            '      "inference_basis": "",\n'
            '      "certainty": "medium",\n'
            '      "certainty_reason": "..."\n'
            "    }\n"
            "  ]\n"
            "}"
    )
    raw = call_chat(
        [
            {"role": "system", "content": "법률 증거 청크를 분석하고 JSON만 출력하라."},
            {"role": "user", "content": prompt},
        ],
        model=model,
        timeout=600,
    )
    try:
        obj = _normalize_chunk_analysis_obj(json.loads(_extract_json_block(raw)))
    except Exception:
        obj = {"claims_proposed": []}
    out_claims = []
    for item in obj.get("claims_proposed") or []:
        claim_text = _normalize_space(item.get("claim_text"))
        if not claim_text:
            continue
        source_file_id = _normalize_space(item.get("source_file_id"))
        if not source_file_id and len(source_lookup) == 1:
            source_file_id = next(iter(source_lookup))
        source_meta = source_lookup.get(source_file_id)
        if source_meta is None:
            if len(source_lookup) == 1:
                source_file_id, source_meta = next(iter(source_lookup.items()))
            else:
                continue
        support_entries = item.get("support_evidence")
        if not isinstance(support_entries, list):
            support_entries = item.get("support_quotes") or []
        oppose_entries = item.get("oppose_evidence")
        if not isinstance(oppose_entries, list):
            oppose_entries = item.get("oppose_quotes") or []
        evidence_prefix = _default_evidence_prefix_from_fields(
            relative_path=str(source_meta.get("relative_path") or ""),
            document_title=str(source_meta.get("document_title") or ""),
            file_id=str(source_meta.get("file_id") or source_file_id),
        )
        support_spans = _coerce_evidence_spans(support_entries, chunk, default_prefix=evidence_prefix)
        oppose_spans = _coerce_evidence_spans(oppose_entries, chunk, default_prefix=evidence_prefix)
        if not support_spans:
            continue
        certainty = _normalize_space(item.get("certainty")).lower() or "medium"
        if certainty not in CERTAINTY_ORDER:
            certainty = CERTAINTY_LABELS.get(certainty, "medium")
        if oppose_spans and certainty == "very_high":
            certainty = "high"
        base_claim = {
            "claim_text": claim_text,
            "recommended_section": _normalize_space(item.get("recommended_section")) or "나. 사안의 적용",
            "support_spans": support_spans,
            "oppose_spans": oppose_spans,
            "same_situation_case_exists": bool(item.get("same_situation_case_exists")),
            "inference_basis": _normalize_space(item.get("inference_basis")),
            "certainty": certainty,
            "certainty_reason": _normalize_space(item.get("certainty_reason")),
            "source_file_id": source_file_id,
            "source_chunk_id": chunk.chunk_id,
            "document_title": str(source_meta.get("document_title") or chunk.document_title),
            "relative_path": str(source_meta.get("relative_path") or chunk.relative_path),
            "case_number": str(source_meta.get("case_number") or chunk.case_number),
            "court": str(source_meta.get("court") or chunk.court),
            "decision_date": str(source_meta.get("decision_date") or chunk.decision_date),
            "case_name": str(source_meta.get("case_name") or chunk.case_name),
        }
        if analysis_mode == "question":
            base_claim.update(
                {
                    "claim_axis": _normalize_space(item.get("claim_axis")) or claim_text,
                    "stance_to_user_goal": _normalize_space(item.get("stance_to_user_goal")) or "혼합",
                    "favorable_basis": _coerce_string_list(item.get("favorable_basis")),
                    "unfavorable_basis": _coerce_string_list(item.get("unfavorable_basis")),
                    "usable_favorable_logic": _coerce_string_list(item.get("usable_favorable_logic")),
                    "usable_unfavorable_logic": _coerce_string_list(item.get("usable_unfavorable_logic")),
                    "favorable_factors": _coerce_string_list(item.get("favorable_factors")),
                    "unfavorable_factors": _coerce_string_list(item.get("unfavorable_factors")),
                    "required_facts": _coerce_string_list(item.get("required_facts")),
                    "missing_facts": _coerce_string_list(item.get("missing_facts")),
                    "cautions": _coerce_string_list(item.get("cautions")),
                    "counter_evidence": _coerce_string_list(item.get("counter_evidence")),
                    "context_summary": _normalize_space(item.get("context_summary")),
                    "case_summary": _normalize_space(item.get("case_summary")),
                }
            )
        out_claims.append(base_claim)
    return {"chunk_id": chunk.chunk_id, "file_id": chunk.file_id, "claims_proposed": out_claims, "raw": raw}


def analyze_chunk_cached(
    chunk: ChunkRecord,
    *,
    user_task: str,
    model: str,
    cache_dir: Path,
    analysis_mode: str = "document",
) -> dict[str, Any]:
    cache_key = _analyze_cache_key(chunk, user_task=user_task, model=model, analysis_mode=analysis_mode)
    cache_path = cache_dir / f"{cache_key}.json"
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))
    try:
        result = analyze_chunk(chunk, user_task=user_task, model=model, analysis_mode=analysis_mode)
    except Exception as exc:
        result = {
            "chunk_id": chunk.chunk_id,
            "file_id": chunk.file_id,
            "claims_proposed": [],
            "error": str(exc),
            "document_title": chunk.document_title,
            "relative_path": chunk.relative_path,
        }
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    return result


def _analyze_cache_key(chunk: ChunkRecord, *, user_task: str, model: str, analysis_mode: str = "document") -> str:
    payload = f"{ANALYZE_CACHE_SCHEMA_VERSION}\n{analysis_mode}\n{model}\n{user_task}\n{chunk.chunk_id}\n{chunk.text}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _identify_cited_no_claim_precedent_ids(
    *,
    answer_text: str,
    records: list[FileRecord],
    existing_claim_file_ids: set[str],
) -> set[str]:
    """Scan the writer's answer markdown for case_number citations and return
    the file_ids of records that ARE cited but have NO entry in the
    claim_ledger. These are the rows that need a post-writer summary so
    the drawer doesn't fall back to raw body header.
    """
    if not answer_text:
        return set()
    # Same regex shape as frontend: `<2~4 digits><1~4 Korean><1~6 digits>`.
    cited_case_numbers: set[str] = set()
    for match in re.finditer(r"\b(\d{2,4})\s*([가-힣]{1,4})\s*(\d{1,6}(?:\s*,\s*\d{1,6})*)\b", answer_text):
        compact = re.sub(r"\s+", "", match.group(0))
        cited_case_numbers.add(compact)
    if not cited_case_numbers:
        return set()
    out: set[str] = set()
    for record in records:
        if record.file_id in existing_claim_file_ids:
            continue
        rec_case_no = re.sub(r"\s+", "", str(record.case_number or ""))
        if rec_case_no and rec_case_no in cited_case_numbers:
            out.add(record.file_id)
    return out


def summarize_selected_precedents_parallel(
    *,
    records: list[FileRecord],
    existing_claims: list[dict[str, Any]],
    user_task: str,
    model: str,
    workers: int,
    cache_dir: Path,
    status_path: Path | None = None,
    variant_name: str | None = None,
    only_file_ids: set[str] | None = None,
) -> dict[str, dict[str, str]]:
    """Generate `(case_summary, context_summary)` for selected precedents via
    a per-record LLM call.

    Strategy:
      1. If `only_file_ids` is provided, restrict LLM calls to JUST those
         file_ids (typically: precedents the writer cited in body but that
         don't have any claim_ledger entry). This avoids the 11-minute
         100-call sweep that wastes time on rows the user never sees.
      2. Otherwise iterate all `records`. The 'all records' mode is kept for
         ad-hoc backfill scripts, not the live pipeline.
      3. Cache by (record.file_id, sha1(user_task + body[:5000])).

    Returns dict[file_id → {"case_summary": str, "context_summary": str}].
    Existing claim-derived summaries are merged in too (no LLM call needed).
    """
    summary_cache_dir = cache_dir / "precedent_summaries_v1"
    summary_cache_dir.mkdir(parents=True, exist_ok=True)

    existing_by_file: dict[str, tuple[str, str]] = {}
    for claim in existing_claims:
        file_id = str(claim.get("source_file_id") or "")
        if not file_id:
            continue
        case_sum = _normalize_space(str(claim.get("case_summary") or ""))
        ctx_sum = _normalize_space(str(claim.get("context_summary") or ""))
        if not (case_sum or ctx_sum):
            continue
        prev_case, prev_ctx = existing_by_file.get(file_id, ("", ""))
        if not prev_case and case_sum:
            prev_case = case_sum
        if not prev_ctx and ctx_sum:
            prev_ctx = ctx_sum
        existing_by_file[file_id] = (prev_case, prev_ctx)

    needs_llm: list[FileRecord] = []
    out: dict[str, dict[str, str]] = {}
    # Always export the existing claim-derived summaries (no LLM cost).
    for file_id, (case_sum, ctx_sum) in existing_by_file.items():
        out[file_id] = {"case_summary": case_sum, "context_summary": ctx_sum}
    for record in records:
        if only_file_ids is not None and record.file_id not in only_file_ids:
            continue
        existing = existing_by_file.get(record.file_id)
        if existing and existing[0] and existing[1]:
            # Already covered above.
            continue
        needs_llm.append(record)

    if not needs_llm:
        return out

    prompt_template = (
        "아래 한국 판례 본문을 읽고 (1) 판례 요약 1~2문장 (사실관계 + 결론 + 핵심 이유), "
        "(2) 맥락 1문장 (이 판례가 사용자의 질문에 어떻게 닿는지)을 JSON으로만 응답하라. "
        "어떤 부가 설명이나 코드블록 없이 순수 JSON 한 객체만 출력한다. "
        "절대 본문의 당사자명/주문/소송비용/청구금액 같은 머리말을 그대로 베끼지 말고 의미를 풀어 적는다.\n\n"
        "사용자의 질문: {user_task}\n\n"
        "판례 본문 (선택 발췌):\n{body}\n\n"
        '응답 형식: {{"case_summary": "...", "context_summary": "..."}}'
    )

    def _summarize_one(record: FileRecord) -> tuple[str, dict[str, str]]:
        body = (record.extracted_text or "")[:5000]
        cache_key = hashlib.sha1(
            (record.file_id + "|" + (user_task or "") + "|" + hashlib.sha1(body.encode("utf-8")).hexdigest()).encode("utf-8")
        ).hexdigest()
        cache_path = summary_cache_dir / f"{cache_key}.json"
        if cache_path.exists():
            try:
                cached = json.loads(cache_path.read_text(encoding="utf-8"))
                if isinstance(cached, dict) and cached.get("case_summary") and cached.get("context_summary"):
                    return record.file_id, {
                        "case_summary": str(cached["case_summary"]),
                        "context_summary": str(cached["context_summary"]),
                    }
            except Exception:
                pass
        prompt = prompt_template.format(user_task=user_task or "(없음)", body=body)
        try:
            raw = call_chat([{"role": "user", "content": prompt}], model=model, timeout=180)
        except Exception as exc:
            print(f"[summarize_precedent] {record.file_id} call failed: {exc}", flush=True)
            return record.file_id, {"case_summary": "", "context_summary": ""}
        case_summary = ""
        context_summary = ""
        try:
            json_block = _extract_json_block(raw)
            parsed = json.loads(json_block) if json_block else {}
            case_summary = _normalize_space(str(parsed.get("case_summary") or ""))
            context_summary = _normalize_space(str(parsed.get("context_summary") or ""))
        except Exception:
            # Salvage: split on `case_summary` / `context_summary` markers in
            # plain text response when JSON parsing fails.
            m1 = re.search(r"case_summary[\":：\s]*([^\"\n]{5,300})", raw)
            m2 = re.search(r"context_summary[\":：\s]*([^\"\n]{5,300})", raw)
            if m1:
                case_summary = m1.group(1).strip().strip('",')
            if m2:
                context_summary = m2.group(1).strip().strip('",')
        if case_summary or context_summary:
            try:
                cache_path.write_text(
                    json.dumps({"case_summary": case_summary, "context_summary": context_summary}, ensure_ascii=False),
                    encoding="utf-8",
                )
            except Exception:
                pass
        return record.file_id, {"case_summary": case_summary, "context_summary": context_summary}

    completed = 0
    total_to_summarize = len(needs_llm)
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(needs_llm)))) as executor:
        future_map = {executor.submit(_summarize_one, record): record for record in needs_llm}
        for future in as_completed(future_map):
            file_id, summary = future.result()
            existing = existing_by_file.get(file_id, ("", ""))
            out[file_id] = {
                "case_summary": summary.get("case_summary") or existing[0] or "",
                "context_summary": summary.get("context_summary") or existing[1] or "",
            }
            completed += 1
            if status_path is not None:
                write_runtime_status(
                    status_path,
                    {
                        "phase": "variant",
                        "variant": variant_name,
                        "state": "summarizing_precedents",
                        "completed_summaries": completed,
                        "summary_count": total_to_summarize,
                    },
                )
            if completed % 10 == 0 or completed == total_to_summarize:
                print(f"[summarize_precedent] {completed}/{total_to_summarize}", flush=True)
    return out


def analyze_chunks_cached(
    chunks: list[ChunkRecord],
    *,
    user_task: str,
    model: str,
    cache_dir: Path,
    analysis_mode: str = "document",
    workers: int = DEFAULT_ANALYZE_WORKERS,
    status_path: Path | None = None,
    variant_name: str | None = None,
) -> list[dict[str, Any]]:
    ordered_results: list[dict[str, Any] | None] = [None] * len(chunks)
    completed = 0
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(chunks) or 1))) as executor:
        future_map = {
            executor.submit(
                analyze_chunk_cached,
                chunk,
                user_task=user_task,
                model=model,
                cache_dir=cache_dir,
                analysis_mode=analysis_mode,
            ): index
            for index, chunk in enumerate(chunks)
        }
        for future in as_completed(future_map):
            index = future_map[future]
            ordered_results[index] = future.result()
            completed += 1
            if status_path is not None:
                write_runtime_status(
                    status_path,
                    {
                        "phase": "variant",
                        "variant": variant_name,
                        "state": "analyzing_chunks",
                        "completed_chunks": completed,
                        "chunk_count": len(chunks),
                    },
                )
            if completed % 10 == 0 or completed == len(chunks):
                print(f"[analyze] {completed}/{len(chunks)}", flush=True)
    return [result for result in ordered_results if result is not None]


def _certainty_sort_value(value: str) -> int:
    return CERTAINTY_ORDER.get(value, 0)


def _render_claim_for_prompt(claim: dict[str, Any]) -> str:
    support = "\n".join(
        f"- [근거ID: {span.get('evidence_id') or '(없음)'}] [{span.get('char_start')}:{span.get('char_end')}] {span.get('quote')}"
        for span in claim.get("support_spans") or []
    ) or "- (없음)"
    oppose = "\n".join(
        f"- [근거ID: {span.get('evidence_id') or '(없음)'}] [{span.get('char_start')}:{span.get('char_end')}] {span.get('quote')}"
        for span in claim.get("oppose_spans") or []
    ) or "- (없음)"
    # Explicitly surface the precedent identifier so the LLM can cite it
    # verbatim. The frontend hyperlink builder only matches canonical case
    # numbers from the selectedPrecedents list; if the model rephrases or
    # hallucinates a different number, the link fails silently.
    case_number = str(claim.get("case_number") or "").strip()
    court = str(claim.get("court") or "").strip()
    decision_date = str(claim.get("decision_date") or "").strip()
    citation_line = ""
    if case_number or court or decision_date:
        parts = [p for p in [court, decision_date, case_number] if p]
        citation_line = f"정확한 판례 식별자 (본문에 이 형태 그대로 써라): {' '.join(parts)}\n"
    return (
        f"주장: {claim.get('claim_text')}\n"
        f"문서: {claim.get('document_title')} ({claim.get('relative_path')})\n"
        f"{citation_line}"
        f"확실성: {claim.get('certainty')}\n"
        f"동일상황 직접 적용례 존재: {claim.get('same_situation_case_exists')}\n"
        f"유추 근거: {claim.get('inference_basis') or '(없음)'}\n"
        f"지지근거:\n{support}\n"
        f"반대근거:\n{oppose}\n"
    )


def _is_direct_opinion_adverse_claim(claim_text: str) -> bool:
    text = _normalize_space(claim_text)
    adverse_markers = [
        "부당성을 주장하기 어렵",
        "반대되는 근거",
        "위법하지 않",
        "적법할 수 있",
        "적법하다고",
        "남용으로 보기 어렵",
        "정당성이 인정",
        "권한이 있다",
        "가중할 수 있",
        "정당한 재량",
        "한계가 있",
    ]
    return any(marker in text for marker in adverse_markers)


def render_direct_opinion_claim_cards(claims: list[dict[str, Any]]) -> str:
    ordered = sorted(
        [
            claim
            for claim in claims
            if claim.get("support_spans") and not _is_direct_opinion_adverse_claim(claim.get("claim_text", ""))
        ],
        key=lambda item: (
            -_certainty_sort_value(item.get("certainty", "")),
            -(len(item.get("support_spans") or [])),
            item.get("claim_text", ""),
        ),
    )
    if not ordered:
        return "- (없음)"

    cards: list[str] = []
    for index, claim in enumerate(ordered, 1):
        support_lines = "\n".join(
            f"- {span.get('evidence_id') or '(없음)'}: {span.get('quote')}"
            for span in claim.get("support_spans") or []
        ) or "- (없음)"
        oppose_lines = "\n".join(
            f"- {span.get('evidence_id') or '(없음)'}: {span.get('quote')}"
            for span in claim.get("oppose_spans") or []
        ) or "- (없음)"
        cards.append(
            "\n".join(
                [
                    f"[주장 카드 {index}]",
                    f"주장: {claim.get('claim_text')}",
                    f"확실성: {claim.get('certainty')}",
                    f"동일상황 직접 적용례 존재: {claim.get('same_situation_case_exists')}",
                    f"유추 근거: {claim.get('inference_basis') or '(없음)'}",
                    "지지근거:",
                    support_lines,
                    "반대근거:",
                    oppose_lines,
                ]
            )
        )
    return "\n\n".join(cards)


def render_chunk_outputs_prompt_style(
    rows: list[tuple[int, dict[str, Any]]],
    *,
    skip_empty_chunks: bool = True,
) -> str:
    sep = "\n\n" + ("=" * 80) + "\n\n"
    subsep = "\n" + ("-" * 40) + "\n"
    kept = []
    for idx, row in rows:
        claims = row.get("claims_proposed") or []
        if skip_empty_chunks and not claims:
            continue
        header = [
            f"CHUNK_INDEX: {idx}",
            f"CHUNK_ID: {row.get('chunk_id', '')}",
            f"FILE_ID: {row.get('file_id', '')}",
        ]
        if claims:
            first = claims[0]
            header.extend(
                [
                    f"DOCUMENT_TITLE: {first.get('document_title', '')}",
                    f"RELATIVE_PATH: {first.get('relative_path', '')}",
                    f"CLAIM_COUNT: {len(claims)}",
                ]
            )
        else:
            header.extend(
                [
                    f"DOCUMENT_TITLE: {row.get('document_title', '')}",
                    f"RELATIVE_PATH: {row.get('relative_path', '')}",
                    "CLAIM_COUNT: 0",
                ]
            )
        block_parts = ["\n".join(header)]
        if not claims:
            block_parts.append(
                "주장: (없음)\n문서: (없음)\n확실성: (없음)\n동일상황 직접 적용례 존재: False\n유추 근거: (없음)\n지지근거:\n- (없음)\n반대근거:\n- (없음)"
            )
        else:
            for claim in claims:
                block_parts.append(_render_claim_for_prompt(claim).strip())
        kept.append(sep + subsep.join(block_parts))

    parts = [
        "# Variant Chunk Outputs In Prompt Style",
        "",
        f"- chunk_count_input: {len(rows)}",
        f"- chunk_count_rendered: {len(kept)}",
        f"- skip_empty_chunks: {skip_empty_chunks}",
        "- format: per-chunk separator + human-readable claim blocks",
    ]
    parts.extend(kept)
    return "\n".join(parts).strip() + "\n"


def collect_nonempty_chunk_ids_from_jsonl(path: Path) -> list[str]:
    out: list[str] = []
    with path.open("r", encoding="utf-8") as fp:
        for line in fp:
            if not line.strip():
                continue
            row = json.loads(line)
            chunk_id = str(row.get("chunk_id") or "").strip()
            claims = row.get("claims_proposed") or []
            if chunk_id and claims:
                out.append(chunk_id)
    return out


def _pack_claims_for_writing(claims: list[dict[str, Any]], *, max_tokens: int) -> list[list[dict[str, Any]]]:
    blocks = [(str(index), _render_claim_for_prompt(claim)) for index, claim in enumerate(claims)]
    packs = pack_text_blocks(blocks, max_tokens=max_tokens)
    out: list[list[dict[str, Any]]] = []
    for pack in packs:
        ids = {key for key, _ in pack}
        out.append([claim for index, claim in enumerate(claims) if str(index) in ids])
    return out


def synthesize_section_packets(claims: list[dict[str, Any]], *, model: str, max_tokens: int) -> dict[str, list[str]]:
    by_section: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for claim in claims:
        by_section[claim.get("recommended_section") or "나. 사안의 적용"].append(claim)
    packets: dict[str, list[str]] = {}
    for section, rows in by_section.items():
        rows = sorted(rows, key=lambda item: (-_certainty_sort_value(item.get("certainty", "")), -len(item.get("support_spans") or []), item.get("claim_text", "")))
        pack_limit = max_tokens - 12_000
        for subset in _pack_claims_for_writing(rows, max_tokens=max(20_000, pack_limit)):
            prompt = (
                f"아래는 의견서의 섹션 `{section}` 에 들어갈 주장 ledger 다.\n"
                "주장들을 중복 없이 정리하되, 반대근거와 유추 여부를 누락하지 말고 한국어 정리문으로 써라.\n"
                "아직 최종 의견서 문체로 다듬지 말고, 이 섹션에 들어갈 핵심 논거 정리문만 써라.\n\n"
                + "\n\n".join(_render_claim_for_prompt(claim) for claim in subset)
            )
            text = call_chat(
                [
                    {"role": "system", "content": "법률 주장 ledger를 섹션용 정리문으로 합친다."},
                    {"role": "user", "content": prompt},
                ],
                model=model,
                timeout=600,
            )
            packets.setdefault(section, []).append(text.strip())
    return packets


def parse_used_evidence_ids(text: str) -> list[str]:
    lines = text.splitlines()
    in_block = False
    ids: list[str] = []
    seen: set[str] = set()
    for raw_line in lines:
        line = raw_line.strip()
        if not in_block:
            if line == "[사용한 근거 ID]" or line.endswith("[사용한 근거 ID]"):
                in_block = True
            continue
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            inner = line[1:-1].strip()
            if not inner:
                continue
            if inner == "사용한 근거 ID":
                continue
            if inner.endswith("-근거1") or "-근거" in inner:
                line = inner
            else:
                break
        if line.startswith("- "):
            line = line[2:].strip()
        elif line.startswith("* "):
            line = line[2:].strip()
        if not line or line in seen:
            continue
        seen.add(line)
        ids.append(line)
    return ids


def collect_selected_evidence_bundle(
    claims: list[dict[str, Any]],
    selected_evidence_ids: list[str],
) -> list[dict[str, Any]]:
    evidence_map: dict[str, dict[str, Any]] = {}
    for claim in claims:
        document_title = claim.get("document_title") or ""
        relative_path = claim.get("relative_path") or ""
        for side_key, evidence_side in (("support_spans", "support"), ("oppose_spans", "oppose")):
            for span in claim.get(side_key) or []:
                evidence_id = _normalize_space(span.get("evidence_id"))
                if not evidence_id or evidence_id in evidence_map:
                    continue
                evidence_map[evidence_id] = {
                    "evidence_id": evidence_id,
                    "document_title": document_title,
                    "relative_path": relative_path,
                    "quote": span.get("quote") or "",
                    "char_start": span.get("char_start"),
                    "char_end": span.get("char_end"),
                    "evidence_side": evidence_side,
                }
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for evidence_id in selected_evidence_ids:
        normalized = _normalize_space(evidence_id)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        row = evidence_map.get(normalized)
        if row:
            out.append(row)
    return out


def render_selected_evidence_bundle(selected_evidence_bundle: list[dict[str, Any]]) -> str:
    if not selected_evidence_bundle:
        return "- (없음)"
    parts: list[str] = []
    for item in selected_evidence_bundle:
        parts.append(
            "\n".join(
                [
                    f"근거ID: {item.get('evidence_id')}",
                    f"문서: {item.get('document_title')} ({item.get('relative_path')})",
                    f"유형: {item.get('evidence_side')}",
                    f"원문: [{item.get('char_start')}:{item.get('char_end')}] {item.get('quote')}",
                ]
            )
        )
    return "\n\n".join(parts)


DOCUMENT_META_LEAK_PATTERNS = (
    re.compile(r"Legal Professional", re.IGNORECASE),
    re.compile(r"Legal Opinion Writer", re.IGNORECASE),
    re.compile(r"Complaint\s*\(\s*고\s*소\s*장\s*\)", re.IGNORECASE),
    re.compile(r"Write a\s+\"?(?:Complaint|Legal Opinion)", re.IGNORECASE),
    re.compile(r"Use\s+\*?only\*?\s+the provided ledger", re.IGNORECASE),
    re.compile(r"The user provided", re.IGNORECASE),
    re.compile(r"The user'?s task", re.IGNORECASE),
    re.compile(r"though the user'?s task", re.IGNORECASE),
    re.compile(r"Wait,\s*let'?s re-read", re.IGNORECASE),
    re.compile(r"Wait,\s*looking at the prompt", re.IGNORECASE),
    re.compile(r"Contradiction Check\s*:", re.IGNORECASE),
    re.compile(r"Resolution\s*:", re.IGNORECASE),
    re.compile(r"Problem\s*:", re.IGNORECASE),
    re.compile(r"Decision\s*:", re.IGNORECASE),
    re.compile(r"Strategy\s*:", re.IGNORECASE),
    re.compile(r"Subject Matter\s*:", re.IGNORECASE),
    re.compile(r"\bClaim\s+\d+\s*:", re.IGNORECASE),
    re.compile(r"\bStructure\s*:", re.IGNORECASE),
    re.compile(r"\bTone\s*:", re.IGNORECASE),
    re.compile(r"Drafting Content\s*:", re.IGNORECASE),
    re.compile(r"Refining the", re.IGNORECASE),
    re.compile(r"Check against constraints", re.IGNORECASE),
    re.compile(r"Final Review of the Ledger usage", re.IGNORECASE),
    re.compile(r"Final Polish", re.IGNORECASE),
    re.compile(r"Final Plan\s*:", re.IGNORECASE),
    re.compile(r"Final Text Construction\s*:", re.IGNORECASE),
    re.compile(r"Mental Draft\s*:", re.IGNORECASE),
    re.compile(r"Final check", re.IGNORECASE),
    re.compile(r"\*?\s*Check\s*:\s*", re.IGNORECASE),
    re.compile(r"Formatting\s*:\s*Plain text", re.IGNORECASE),
    re.compile(r"Drafting the final response", re.IGNORECASE),
    re.compile(r"Proceeding to generate", re.IGNORECASE),
    re.compile(r"Self[-\s]?Correction", re.IGNORECASE),
)

DOCUMENT_STRUCTURAL_OUTPUT_START_PATTERNS = (
    re.compile(r"(?im)(?P<start>^\s*(?:#+\s*)?고\s*소\s*장\s*$)"),
    re.compile(r"(?im)(?P<start>^\s*(?:#+\s*)?1\.\s*고소인\b)"),
)

DOCUMENT_OUTPUT_START_PATTERNS = (
    re.compile(
        r"(?P<start>법률\s*검토\s*의견서|변호인\s*의견서|변호인의견서|내용증명|고소장|고발장|준비서면|답변서|항소이유서|탄원서|진정서)\b"
    ),
    re.compile(r"(?m)(?P<start>^사\s*건\s+.+$)"),
    re.compile(r"(?m)(?P<start>^수\s*신(?:인)?\s*[:：]?\s*.+$)"),
    re.compile(r"(?m)(?P<start>^발\s*신(?:인)?\s*[:：]?\s*.+$)"),
    re.compile(r"(?m)(?P<start>^제\s*목\s*[:：]?\s*.+$)"),
)


def _document_output_has_meta_leak(text: str) -> bool:
    raw = str(text or "")
    return any(pattern.search(raw) for pattern in DOCUMENT_META_LEAK_PATTERNS)


def _find_document_output_start(raw: str, *, after: int) -> int | None:
    search_area = raw[max(0, after) :]
    for pattern in DOCUMENT_STRUCTURAL_OUTPUT_START_PATTERNS:
        match = pattern.search(search_area)
        if match:
            return max(0, after) + match.start("start")
    candidates: list[int] = []
    for pattern in DOCUMENT_OUTPUT_START_PATTERNS:
        match = pattern.search(search_area)
        if match:
            candidates.append(max(0, after) + match.start("start"))
    return min(candidates) if candidates else None


def _ensure_document_heading(markdown: str) -> str:
    cleaned = str(markdown or "").strip()
    if re.match(r"(?im)^(?:#+\s*)?1\.\s*고소인\b", cleaned):
        return f"고    소    장\n\n{cleaned}"
    return cleaned


def sanitize_document_output(text: str) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    if not _document_output_has_meta_leak(raw):
        return raw
    marker_ends = [
        match.end()
        for pattern in DOCUMENT_META_LEAK_PATTERNS
        for match in pattern.finditer(raw)
    ]
    after = max(marker_ends) if marker_ends else 0
    start = _find_document_output_start(raw, after=after)
    if start is None:
        return raw
    stripped = raw[start:].strip()
    return _ensure_document_heading(stripped or raw)


def write_final_opinion(
    *,
    user_task: str,
    sample_texts: list[str],
    claims: list[dict[str, Any]],
    section_packets: dict[str, list[str]],
    model: str,
    extra_requirements: str = "",
) -> str:
    prompt = build_final_opinion_prompt(
        user_task=user_task,
        sample_texts=sample_texts,
        claims=claims,
        section_packets=section_packets,
        extra_requirements=extra_requirements,
    )
    output = call_chat(
        [
            {
                "role": "system",
                "content": (
                    "법률 문서 최종 작성자다. 사용자 과제의 문서 유형을 우선한다. "
                    "샘플은 형식 참고용일 뿐이며 그대로 복사하지 않는다. "
                    "최종 문서 본문만 한국어로 출력하고, 역할 설명·작성 계획·체크리스트·자기검토·영문 메타 문장을 출력하지 않는다."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        model=model,
        timeout=900,
    ).strip()
    return sanitize_document_output(output)


def build_draft2_extra_requirements() -> str:
    return (
        "예시 형식을 철저하게 따라서, 예시가 법률문서라면 판례를 인용하는 방식, 논리를 적용하는 방식, 주장을 전개하는 방식을 그대로 따를 것.\n"
        "근거들은 광범위한 자료 속에서 관대한 조건으로 수집된 것이므로, 근거 자체의 존재는 의심하지 말되 해당 근거가 이 사안에 실제로 적합한지, 해당 근거 해석이 정확한지는 엄밀하게 다시 판단할 것.\n"
        "근거는 쓸 만하지만 기존 주장이 잘못 해석한 경우, 그 근거를 비약 없이 다시 해석하여 사용할 수 있다. 다만 근거를 과장하거나 잘못 읽어 새로운 논리를 함부로 만들어내지는 말 것.\n"
        "실제로 이것과 같은 상황에서 적용된 사례가 있는 주장만 본문 핵심 논거로 채용할 것. 직접 적용 사례가 없으면 그 한계를 분명히 적고, 유추 적용임을 숨기지 말 것.\n"
        "근거가 판례라면 본문에서 그 판결명이나 선고 정보가 드러나게 쓰고, 근거가 법률이나 규정이라면 그 법령명 또는 규정명을 정확히 적을 것. 다만 근거 ID 표기를 기계적으로 나열할 필요는 없다."
    )


def build_case_analysis_extra_requirements() -> str:
    citation_requirements = "\n".join(build_draft2_extra_requirements().splitlines()[1:])
    objectivity_requirements = (
        "꼭 사용자에게 유리한쪽으로만 해석하지말고, 객관적으로 해석하여 불리하다면 불리하다고 말하고 그 구체적 이유를 말해야 한다.\n"
        "판단하기 어렵다면 어려운 이유를 설명해야 한다.\n"
        "불리하다면 불리한 이유를 말한 뒤, 그럼에도 최대한 유리하게 만들 방법을 실제 유사 사례가 있는 범위에서 설명해야 한다.\n"
        "유리하다면 그 유리함을 유지하거나 강화하기 위해 실무적으로 어떤 대응을 해야 하는지도 실제 근거에 기대어 설명해야 한다.\n"
        "불리하거나 어렵게 보이는 쟁점이라도, 완전히 무리한 주장이 아니고 근거가 있다면 버리지 말 것.\n"
        "가능성이 낮더라도 써볼 만한 유리한 주장은 별도의 대응 카드로 정리하고, 받아들여진 사례와 받아들여지지 않은 사례가 함께 있으면 둘 다 설명할 것."
    )
    return citation_requirements + "\n" + objectivity_requirements


def build_final_opinion_prompt(
    *,
    user_task: str,
    sample_texts: list[str],
    claims: list[dict[str, Any]],
    section_packets: dict[str, list[str]],
    extra_requirements: str = "",
) -> str:
    top_claims = claims[:50]
    extra_block = f"\n[추가 작성 지침]\n{extra_requirements}\n" if extra_requirements.strip() else ""
    is_complaint = bool(re.search(r"고\s*소\s*장|고소취지|고소인|피고소인|범죄사실|처벌하여\s*주시", user_task or ""))
    document_label = "고소장" if is_complaint else "변호인 의견서"
    type_requirements = (
        "- 고소장으로 작성할 것. 변호인의견서, 피의자/피고인 선처 의견서 형식을 쓰지 말 것\n"
        "- 첫 줄은 반드시 `고    소    장`으로 시작할 것\n"
        "- 고소인, 피고소인, 고소취지, 범죄사실, 입증자료, 첨부서류 구조를 우선 사용할 것\n"
        if is_complaint
        else "- 변호인 의견서로 작성할 것\n"
    )
    rendered_sample_texts = sample_texts[:4] if sample_texts else ["(샘플 없음)"]
    sample_block = "\n\n".join(
        f"[샘플 {index} 전체]\n{sample_text}" for index, sample_text in enumerate(rendered_sample_texts, start=1)
    )
    prompt = (
        "아래 문서 샘플 텍스트를 형식 예시로 삼아, 사용자 과제에 맞는 법률 문서 텍스트를 작성하라.\n"
        f"문서 유형: {document_label}\n"
        "중요:\n"
        f"{type_requirements}"
        "- 최종 문서 본문만 출력할 것. 작성 계획, 논리 메모, 체크리스트, 자기검토, 영문 설명을 절대 출력하지 말 것\n"
        "- 샘플의 문체와 구성감을 따르되 그대로 베끼지 말 것\n"
        "- 사용자 지시에 최대한 부합하고 사용자에게 유리하게 작성하되, 근거 없는 주장이나 과장은 하지 말 것\n"
        "- 불리한 내용을 독립된 본론으로 크게 부각하지 말 것. 불리한 사정이 필요하다면 반박, 구별, 완화, 양정 감경 논리와 함께 최소한으로만 다룰 것\n"
        "- 받아들여질 가능성이 낮더라도 완전히 무리한 주장이 아니고 근거가 있다면, 사용자에게 유리한 주장으로 정리하여 포함할 것\n"
        "- 아래 ledger와 section packet 에 있는 내용만 근거로 사용할 것\n"
        "- support/opposition/certainty를 반영할 것\n"
        "- 반대근거가 있는 쟁점은 단정하지 말 것\n"
        "- 결과물은 평문 텍스트로만 출력할 것\n"
        "- 1. 2. 3. / 가. 나. 다. / 4. / 첨부서류 구조를 자연스럽게 따를 것\n"
        "- 판례를 본문에 인용할 때는 각 claim의 `정확한 판례 식별자` 라인에 적힌 판례번호를 **공백/형태 변형 없이 그대로** 쓸 것. "
        "법원명·선고일이 ledger에 정확히 제공된 경우에만 `대법원 2020. 4. 23. 선고 2020도5336 판결`처럼 함께 쓰고, "
        "선고일/법원명이 없거나 불확실하면 판례번호만 쓸 것. ledger에 없는 판례번호·사건명·법원명·선고일은 지어내지 말 것.\n"
        "- 판례 원문을 직접 인용할 때는 citation 뒤에 큰따옴표 문장을 붙이지 말고, 반드시 다음 줄을 비운 뒤 `> 직접 인용문` 마크다운 blockquote로 분리할 것.\n\n"
        f"사용자 과제:\n{user_task}\n\n"
        f"{extra_block}"
        f"{sample_block}\n\n"
        "[핵심 claim ledger]\n"
        + "\n\n".join(_render_claim_for_prompt(claim) for claim in top_claims)
    )
    if section_packets:
        prompt += "\n\n[section packets]\n" + "\n\n".join(
            f"## {section}\n" + "\n\n".join(parts) for section, parts in section_packets.items()
        )
    return prompt


def build_final_opinion_from_analysis_prompt(
    *,
    user_task: str,
    sample_texts: list[str],
    case_analysis_text: str,
    selected_evidence_bundle: list[dict[str, Any]],
    extra_requirements: str = "",
) -> str:
    extra_block = f"\n[추가 작성 지침]\n{extra_requirements}\n" if extra_requirements.strip() else ""
    return (
        "아래 두 개의 변호인 의견서 샘플 텍스트를 형식 예시로 삼아, 이번 사건에 대한 변호인 의견서 텍스트를 작성하라.\n"
        "중요:\n"
        "- 샘플의 문체와 구성감을 따르되 그대로 베끼지 말 것\n"
        "- 사용자 지시에 최대한 부합하고 사용자에게 유리하게 작성하되, 근거 없는 주장이나 과장은 하지 말 것\n"
        "- 불리한 내용을 독립된 본론으로 크게 부각하지 말 것. 불리한 사정이 필요하다면 반박, 구별, 완화, 양정 감경 논리와 함께 최소한으로만 다룰 것\n"
        "- 받아들여질 가능성이 낮더라도 완전히 무리한 주장이 아니고 근거가 있다면, 사용자에게 유리한 주장으로 정리하여 포함할 것\n"
        "- 유리한 논거는 추상적 공정성 문구보다 명시적 법리 명칭으로 제시할 것. 가능한 경우 `이중징계`, `신의칙` 또는 `신뢰보호`, `재량권 일탈·남용`, `방어권 침해`, `비례원칙 위반` 같은 법리 이름을 표제와 첫 문장에서 분명히 밝힐 것\n"
        "- 같은 사실관계에서 복수의 유리한 법리가 각자 성립 가능하다면, 이를 하나의 보수적인 공정성 문구로만 축소하지 말 것. 본문에서 병렬적 또는 예비적으로 구분하여 제시할 것\n"
        "- 사건분석 문서가 가능성 낮음 또는 난점이 있다고 정리한 쟁점이라도, 선택 근거 원문에 그 쟁점을 직접 지지하는 구체적 법령이나 판례가 있으면 보조적 또는 예비적 주장으로 포함할 것\n"
        "- 아래 사건분석 문서와 선택 근거 원문에 있는 내용만 근거로 사용할 것\n"
        "- 사건분석 문서는 내부 검토 메모로만 취급할 것. 그 문서의 균형적 서술이나 위험 정리 구조를 최종 의견서의 구조로 답습하지 말 것\n"
        "- 사건분석 문서 안의 `불리한 쟁점`, `불리한 이유` 같은 표제어나 배열을 최종 의견서의 표제어나 본문 구조로 옮기지 말 것\n"
        "- 사건분석 문서의 서술을 그대로 복사하지 말고, 선택 근거 원문으로 다시 확인하여 의견서 문장으로 재구성할 것\n"
        "- 반대근거나 한계가 드러난 쟁점은 무리하게 단정하지 말 것\n"
        "- 결과물은 평문 텍스트로만 출력할 것\n"
        "- 1. 2. 3. / 가. 나. 다. / 4. / 첨부서류 구조를 자연스럽게 따를 것\n\n"
        f"사용자 과제:\n{user_task}\n\n"
        f"{extra_block}"
        "[샘플 1 전체]\n"
        f"{sample_texts[0]}\n\n"
        "[샘플 2 전체]\n"
        f"{sample_texts[1]}\n\n"
        "[사건분석 및 대응 문서]\n"
        f"{case_analysis_text.strip()}\n\n"
        "[선택 근거 원문]\n"
        f"{render_selected_evidence_bundle(selected_evidence_bundle)}\n"
    )


def build_direct_final_opinion_prompt(
    *,
    user_task: str,
    sample_texts: list[str],
    incident_material_texts: list[tuple[str, str]],
    claims: list[dict[str, Any]],
    extra_requirements: str = "",
) -> str:
    extra_block = f"\n[추가 작성 지침]\n{extra_requirements}\n" if extra_requirements.strip() else ""
    incident_blocks = []
    for index, (name, text) in enumerate(incident_material_texts, 1):
        incident_blocks.append(f"[사건자료 원문 {index}]\n자료명: {name}\n{text.strip()}\n")
    return (
        "아래 두 개의 변호인 의견서 샘플 텍스트를 형식 예시로 삼아, 이번 사건에 대한 변호인 의견서 텍스트를 작성하라.\n"
        "중요:\n"
        "- 샘플의 문체와 구성감을 따르되 그대로 베끼지 말 것\n"
        "- 사용자 지시에 최대한 부합하고 사용자에게 유리하게 작성하되, 근거 없는 주장이나 과장은 하지 말 것\n"
        "- 아래 사건자료 원문과 주장별 근거 카드만 근거로 사용할 것\n"
        "- 후보 주장 카드에는 사용자에게 유리한 주장과 불리한 주장, 반대근거가 함께 섞여 있을 수 있다. 최종 의견서에는 사용자에게 유리한 주장 카드만 채택할 것\n"
        "- 불리한 카드나 반대 카드의 문구를 독립된 본론으로 쓰지 말 것\n"
        "- 사건자료 원문과 맞지 않는 주장 카드는 채택하지 말 것\n"
        "- 받아들여질 가능성이 낮더라도 완전히 무리한 주장이 아니고 사건자료와 근거카드가 함께 뒷받침하면 보조적 또는 예비적 주장으로 포함할 것\n"
        "- 사건자료 원문이 특정 법리의 모든 사실요건을 완전히 닫아주지 않더라도, 그 법리가 사건자료에 의해 명백히 배척되지 않고 근거카드에 직접적인 판례나 법령이 있으면 예비적 주장으로 포함할 것\n"
        "- 같은 사실관계에서 복수의 유리한 법리가 각자 성립 가능하다면 하나의 뭉뚱그린 공정성 표현으로 축소하지 말고, 별개의 유리한 공격축으로 병렬적 또는 예비적으로 구분하여 제시할 것\n"
        "- 주장별 근거 카드에 직접적인 판례나 법령이 붙은 별도 공격축은, 사건자료가 이를 명시적으로 배척하지 않는 한 누락하지 말고 조건부 문장이나 예비적 주장 형식으로라도 유지할 것\n"
        "- 가능한 경우 각 논점 문단 안에 사용한 판례명이나 법령명을 직접 드러낼 것\n"
        "- 결과물은 평문 텍스트로만 출력할 것\n"
        "- 1. 2. 3. / 가. 나. 다. / 4. / 첨부서류 구조를 자연스럽게 따를 것\n\n"
        f"사용자 과제:\n{user_task}\n\n"
        f"{extra_block}"
        "[샘플 1 전체]\n"
        f"{sample_texts[0]}\n\n"
        "[샘플 2 전체]\n"
        f"{sample_texts[1]}\n\n"
        + "\n\n".join(incident_blocks)
        + "\n\n[주장별 근거 카드]\n"
        + render_direct_opinion_claim_cards(claims)
    )


def build_case_analysis_prompt(
    *,
    user_task: str,
    claims: list[dict[str, Any]],
    extra_requirements: str = "",
) -> str:
    top_claims = claims[:80]
    extra_block = f"\n[추가 작성 지침]\n{extra_requirements}\n" if extra_requirements.strip() else ""
    return (
        "아래 claim ledger만을 근거로 사건분석 및 대응 문서를 작성하라.\n"
        "중요:\n"
        "- 형식 샘플은 따르지 말고, 분석 문서로서 명확하고 체계적으로 쓸 것\n"
        "- 아래 ledger에 있는 내용만 근거로 사용할 것\n"
        "- 사용자에게 유리한 점과 불리한 점을 함께 정리할 것\n"
        "- 불리한 경우에는 왜 불리한지, 그럼에도 어떤 대응이 가능한지 실제 사례와 연결해 설명할 것\n"
        "- 판단이 어려운 쟁점은 그 이유를 숨기지 말고 적을 것\n"
        "- 문서 맨 마지막에 `[사용한 근거 ID]` 섹션을 두고, 본문 작성에 실제로 사용한 정확한 근거 ID만 한 줄에 하나씩 적을 것\n"
        "- 근거 ID는 아래 ledger에 적힌 정확한 문자열만 그대로 사용할 것\n"
        "- 결과물은 평문 텍스트로만 출력할 것\n\n"
        f"사용자 과제:\n{user_task}\n\n"
        f"{extra_block}"
        "[핵심 claim ledger]\n"
        + "\n\n".join(_render_claim_for_prompt(claim) for claim in top_claims)
    )


def write_case_analysis_document(
    *,
    user_task: str,
    claims: list[dict[str, Any]],
    model: str,
    extra_requirements: str = "",
) -> str:
    prompt = build_case_analysis_prompt(
        user_task=user_task,
        claims=claims,
        extra_requirements=extra_requirements,
    )
    return call_chat(
        [
            {
                "role": "system",
                "content": "법률 사건을 객관적으로 분석하고, 유불리와 대응 방향을 근거 중심으로 정리하는 실무 문서 작성자다.",
            },
            {"role": "user", "content": prompt},
        ],
        model=model,
        timeout=900,
    ).strip()


def write_final_opinion_from_analysis(
    *,
    user_task: str,
    sample_texts: list[str],
    case_analysis_text: str,
    selected_evidence_bundle: list[dict[str, Any]],
    model: str,
    extra_requirements: str = "",
) -> str:
    prompt = build_final_opinion_from_analysis_prompt(
        user_task=user_task,
        sample_texts=sample_texts,
        case_analysis_text=case_analysis_text,
        selected_evidence_bundle=selected_evidence_bundle,
        extra_requirements=extra_requirements,
    )
    output = call_chat(
        [
            {
                "role": "system",
                "content": "법률 의견서 작성자다. 샘플 형식은 따르되 사건분석과 선택 근거 원문만을 기반으로 사용하라.",
            },
            {"role": "user", "content": prompt},
        ],
        model=model,
        timeout=900,
    ).strip()
    return sanitize_document_output(output)


def write_direct_final_opinion(
    *,
    user_task: str,
    sample_texts: list[str],
    incident_material_texts: list[tuple[str, str]],
    claims: list[dict[str, Any]],
    model: str,
    extra_requirements: str = "",
) -> str:
    prompt = build_direct_final_opinion_prompt(
        user_task=user_task,
        sample_texts=sample_texts,
        incident_material_texts=incident_material_texts,
        claims=claims,
        extra_requirements=extra_requirements,
    )
    output = call_chat(
        [
            {
                "role": "system",
                "content": "법률 의견서 작성자다. 샘플 형식은 따르되 사건자료 원문과 주장별 근거 카드만을 기반으로 사용하라.",
            },
            {"role": "user", "content": prompt},
        ],
        model=model,
        timeout=900,
    ).strip()
    return sanitize_document_output(output)


def _read_sample_texts(sample_paths: list[Path], cache_dir: Path) -> list[str]:
    texts = []
    for sample in sample_paths:
        texts.append(build_file_record(sample.parent, sample, cache_dir=cache_dir).extracted_text)
    return texts


def _write_json(path: Path, payload: Any) -> None:
    """Atomic JSON write: write to a sibling temp file then rename.

    `path.write_text(...)` truncates the file before writing, so a reader
    racing with the truncate→write window sees an empty file and raises
    `JSONDecodeError`. The API server's polling loop turns that into a 500.
    Atomic rename guarantees readers see either the old contents or the
    fully-written new contents — never a partial / empty intermediate.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def write_runtime_status(path: Path, payload: dict[str, Any]) -> None:
    merge_runtime_status(path, payload, replace=True)


def merge_runtime_status(path: Path, payload: dict[str, Any], *, replace: bool = False) -> None:
    with _RUNTIME_STATUS_LOCK:
        data: dict[str, Any] = {}
        if not replace and path.exists():
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(existing, dict):
                    data.update(existing)
            except Exception:
                data = {}
        data.update(payload)
        data["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        limits = get_runtime_limits()
        data.setdefault("runtime_limits", limits)
        _write_json(path, data)


def compute_attempt_timeout_seconds(
    *,
    total_timeout_s: float,
    started_at_s: float,
    now_s: float,
    per_attempt_cap_s: float = 30.0,
    min_attempt_timeout_s: float = 5.0,
) -> float | None:
    remaining = float(total_timeout_s) - max(0.0, float(now_s) - float(started_at_s))
    if remaining <= 0:
        return None
    if remaining <= min_attempt_timeout_s:
        return float(min_attempt_timeout_s)
    return float(min(per_attempt_cap_s, remaining))


def select_generate_timeout_cap(model_name: str, *, estimated_prompt_tokens: int) -> float:
    return 600.0


def record_runtime_http_activity(
    status_path: Path | None,
    *,
    event: str,
    kind: str,
    model_name: str,
    detail: str = "",
) -> None:
    if status_path is None:
        return
    with _RUNTIME_STATUS_LOCK:
        if event == "start":
            _RUNTIME_HTTP_STATE["http_started"] += 1
            _RUNTIME_HTTP_STATE["http_inflight"] += 1
        elif event == "finish":
            _RUNTIME_HTTP_STATE["http_finished"] += 1
            _RUNTIME_HTTP_STATE["http_inflight"] = max(0, _RUNTIME_HTTP_STATE["http_inflight"] - 1)
        payload = {
            "last_api_activity_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "last_api_kind": kind,
            "last_api_model": model_name,
            "last_api_event": event,
            "last_api_result": detail,
            **_RUNTIME_HTTP_STATE,
        }
    merge_runtime_status(status_path, payload)


def _ensure_runtime_control_file(path: Path) -> None:
    if path.exists():
        return
    _write_json(
        path,
        {
            "gemini_key_min_gap_ms": GEMINI_KEY_MIN_GAP_MS,
            "gemini_key_max_inflight": GEMINI_KEY_MAX_INFLIGHT,
            "gemini_key_rpm_limit": GEMINI_KEY_RPM_LIMIT,
            "gemini_key_tpm_limit": GEMINI_KEY_TPM_LIMIT,
            "gemini_global_max_inflight": GEMINI_GLOBAL_MAX_INFLIGHT,
        },
    )


def _apply_runtime_control_overrides(
    path: Path,
    *,
    gemini_key_min_gap_ms: int | None = None,
    gemini_key_max_inflight: int | None = None,
    gemini_key_rpm_limit: int | None = None,
    gemini_key_tpm_limit: int | None = None,
    gemini_global_max_inflight: int | None = None,
) -> None:
    payload = {}
    if path.exists():
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            payload.update(loaded)
    if isinstance(gemini_key_min_gap_ms, int) and gemini_key_min_gap_ms > 0:
        payload["gemini_key_min_gap_ms"] = gemini_key_min_gap_ms
    if isinstance(gemini_key_max_inflight, int) and gemini_key_max_inflight > 0:
        payload["gemini_key_max_inflight"] = gemini_key_max_inflight
    if isinstance(gemini_key_rpm_limit, int) and gemini_key_rpm_limit >= 0:
        payload["gemini_key_rpm_limit"] = gemini_key_rpm_limit
    if isinstance(gemini_key_tpm_limit, int) and gemini_key_tpm_limit >= 0:
        payload["gemini_key_tpm_limit"] = gemini_key_tpm_limit
    if isinstance(gemini_global_max_inflight, int) and gemini_global_max_inflight >= 0:
        payload["gemini_global_max_inflight"] = gemini_global_max_inflight
    _write_json(path, payload or {
        "gemini_key_min_gap_ms": GEMINI_KEY_MIN_GAP_MS,
        "gemini_key_max_inflight": GEMINI_KEY_MAX_INFLIGHT,
        "gemini_key_rpm_limit": GEMINI_KEY_RPM_LIMIT,
        "gemini_key_tpm_limit": GEMINI_KEY_TPM_LIMIT,
        "gemini_global_max_inflight": GEMINI_GLOBAL_MAX_INFLIGHT,
    })


def _variant_dir(root: Path, name: str) -> Path:
    path = root / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def _records_by_id(records: list[FileRecord]) -> dict[str, FileRecord]:
    return {record.file_id: record for record in records}


def _build_chunks_for_record(record: FileRecord, *, max_tokens: int) -> list[ChunkRecord]:
    raw_chunks = chunk_document_text(
        text=record.extracted_text,
        max_tokens=max_tokens,
        overlap_chars=DEFAULT_QUOTE_CHARS,
        same_document_group=record.file_id,
        file_id=record.file_id,
        document_title=record.document_title,
        relative_path=record.relative_path,
    )
    return [
        ChunkRecord(
            **raw,
            case_number=record.case_number,
            court=record.court,
            decision_date=record.decision_date,
            case_name=record.case_name,
            source_segments=[
                {
                    "file_id": record.file_id,
                    "document_title": record.document_title,
                    "relative_path": record.relative_path,
                    "case_number": record.case_number,
                    "court": record.court,
                    "decision_date": record.decision_date,
                    "case_name": record.case_name,
                    "start_char": raw["start_char"],
                    "end_char": raw["end_char"],
                    "text": raw["text"],
                    "token_count": raw["token_count"],
                    "excerpt": " ".join(str(raw["text"]).split())[:220],
                }
            ],
        )
        for raw in raw_chunks
    ]


def _build_question_source_segment_from_record(record: FileRecord) -> dict[str, Any]:
    return {
        "file_id": record.file_id,
        "document_title": record.document_title,
        "relative_path": record.relative_path,
        "case_number": record.case_number,
        "court": record.court,
        "decision_date": record.decision_date,
        "case_name": record.case_name,
        "start_char": 0,
        "end_char": len(record.extracted_text),
        "text": record.extracted_text,
        "token_count": _count_tokens(record.extracted_text),
        "excerpt": " ".join(record.extracted_text.split())[:220],
    }


def _render_question_source_segment(segment: dict[str, Any], *, index: int) -> str:
    return (
        f"[SOURCE {index}]\n"
        f"source_file_id: {segment.get('file_id') or ''}\n"
        f"document_title: {segment.get('document_title') or ''}\n"
        f"relative_path: {segment.get('relative_path') or ''}\n"
        f"case_number: {segment.get('case_number') or ''}\n"
        f"court: {segment.get('court') or ''}\n"
        f"decision_date: {segment.get('decision_date') or ''}\n"
        f"case_name: {segment.get('case_name') or ''}\n"
        "본문:\n"
        f"{segment.get('text') or ''}\n"
        f"[END SOURCE {index}]"
    )


def _build_question_pack_chunk(
    segments: list[dict[str, Any]],
    *,
    pack_index: int,
    chunk_id: str | None = None,
    file_id: str | None = None,
    same_document_group: str | None = None,
    relative_path: str | None = None,
) -> ChunkRecord:
    rendered_parts = [_render_question_source_segment(segment, index=index) for index, segment in enumerate(segments, start=1)]
    text = "\n\n" + ("\n\n" + ("=" * 72) + "\n\n").join(rendered_parts) + "\n"
    lead = segments[0] if segments else {}
    resolved_chunk_id = chunk_id or f"question-pack-{pack_index:03d}"
    resolved_file_id = file_id or resolved_chunk_id
    return ChunkRecord(
        chunk_id=resolved_chunk_id,
        file_id=resolved_file_id,
        document_title=f"질문 판례 팩 {pack_index}",
        same_document_group=same_document_group or resolved_file_id,
        relative_path=relative_path or f"packed/question/{pack_index:03d}",
        start_char=0,
        end_char=len(text),
        text=text,
        token_count=_count_tokens(text),
        case_number=str(lead.get("case_number") or ""),
        court=str(lead.get("court") or ""),
        decision_date=str(lead.get("decision_date") or ""),
        case_name=str(lead.get("case_name") or ""),
        source_segments=segments,
    )


def _question_source_segment_token_count(segment: dict[str, Any], *, index: int = 1) -> int:
    return _count_tokens(_render_question_source_segment(segment, index=index))


def build_question_chunks_for_records(
    records: list[FileRecord],
    *,
    max_tokens: int,
    workers: int = DEFAULT_CHUNK_BUILD_WORKERS,
    status_path: Path | None = None,
    variant_name: str | None = None,
) -> list[ChunkRecord]:
    if not records:
        return []

    packs: list[ChunkRecord] = []
    current_segments: list[dict[str, Any]] = []
    current_token_count = 0
    pack_index = 1

    def flush() -> None:
        nonlocal current_segments, current_token_count, pack_index
        if not current_segments:
            return
        packs.append(_build_question_pack_chunk(current_segments, pack_index=pack_index))
        pack_index += 1
        current_segments = []
        current_token_count = 0

    if status_path is not None:
        write_runtime_status(
            status_path,
            {
                "phase": "variant",
                "variant": variant_name,
                "state": "chunking_records",
                "selected_file_count": len(records),
                "chunk_count": 0,
            },
        )

    for index, record in enumerate(records, start=1):
        full_segment = _build_question_source_segment_from_record(record)
        full_rendered_tokens = _question_source_segment_token_count(full_segment, index=1)

        if full_rendered_tokens <= max_tokens:
            separator_tokens = 0 if not current_segments else 32
            if current_segments and current_token_count + separator_tokens + full_rendered_tokens > max_tokens:
                flush()
                separator_tokens = 0
            current_segments.append(full_segment)
            current_token_count += separator_tokens + full_rendered_tokens
        else:
            flush()
            split_limit = max(256, int(max_tokens * 0.8))
            split_chunks = _build_chunks_for_record(record, max_tokens=split_limit)
            for split_chunk in split_chunks:
                segment = split_chunk.source_segments[0] if split_chunk.source_segments else _build_question_source_segment_from_record(record)
                packs.append(
                    _build_question_pack_chunk(
                        [segment],
                        pack_index=pack_index,
                        chunk_id=split_chunk.chunk_id,
                        file_id=split_chunk.file_id,
                        same_document_group=split_chunk.same_document_group,
                        relative_path=split_chunk.relative_path,
                    )
                )
                pack_index += 1

        if status_path is not None:
            merge_runtime_status(
                status_path,
                {
                    "phase": "variant",
                    "variant": variant_name,
                    "state": "chunking_records",
                    "selected_file_count": len(records),
                    "completed_records": index,
                    "total_records": len(records),
                },
            )
    flush()
    if status_path is not None:
        write_runtime_status(
            status_path,
            {
                "phase": "variant",
                "variant": variant_name,
                "state": "packing_chunks",
                "selected_file_count": len(records),
                "chunk_count": len(packs),
            },
        )
    return packs


def _build_chunks_for_records(
    records: list[FileRecord],
    *,
    max_tokens: int,
    workers: int = DEFAULT_CHUNK_BUILD_WORKERS,
    status_path: Path | None = None,
    variant_name: str | None = None,
) -> list[ChunkRecord]:
    if not records:
        return []
    ordered_chunks: list[list[ChunkRecord] | None] = [None] * len(records)
    completed = 0
    estimated_chunk_count = 0
    max_workers = max(1, min(workers, len(records)))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(_build_chunks_for_record, record, max_tokens=max_tokens): index
            for index, record in enumerate(records)
        }
        for future in as_completed(future_map):
            index = future_map[future]
            record_chunks = future.result()
            ordered_chunks[index] = record_chunks
            completed += 1
            estimated_chunk_count += len(record_chunks)
            if status_path is not None and (completed == 1 or completed % 5 == 0 or completed == len(records)):
                write_runtime_status(
                    status_path,
                    {
                        "phase": "variant",
                        "variant": variant_name,
                        "state": "chunking_records",
                        "selected_file_count": len(records),
                        "chunked_file_count": completed,
                        "estimated_chunk_count": estimated_chunk_count,
                    },
                )
    chunks: list[ChunkRecord] = []
    for item in ordered_chunks:
        if item:
            chunks.extend(item)
    return chunks


def _selected_records_from_ids(records: list[FileRecord], selected_ids: list[str]) -> list[FileRecord]:
    lookup = _records_by_id(records)
    out = []
    for file_id in selected_ids:
        record = lookup.get(file_id)
        if record:
            out.append(record)
    return out


def _load_selected_ids_snapshot(path: Path) -> list[str]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        return []
    out: list[str] = []
    for row in payload:
        if isinstance(row, dict) and row.get("file_id"):
            out.append(str(row["file_id"]))
    return out


def resolve_requested_variants(names: list[str] | None) -> list[str]:
    if not names:
        return list(ALL_VARIANTS)
    requested = set(names)
    return [name for name in ALL_VARIANTS if name in requested]


def get_embedding_selection(
    records: list[FileRecord],
    *,
    user_task: str,
    out_dir: Path,
    require_selection: bool,
) -> tuple[list[str], dict[str, Any], bool]:
    snapshot_path = out_dir / "variant_embedding_select" / "selected_files.json"
    scores_path = out_dir / "variant_embedding_select" / "embedding_scores.json"
    selected = _load_selected_ids_snapshot(snapshot_path)
    if selected:
        meta: dict[str, Any] = {}
        if scores_path.exists():
            payload = json.loads(scores_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                meta = payload
        print(f"[select] embedding selection reused={len(selected)}", flush=True)
        return selected, meta, True
    if not require_selection:
        return [], {}, False
    print("[select] embedding file selection", flush=True)
    selected, meta = run_embedding_file_select(records, user_task=user_task)
    _write_json(scores_path, meta)
    _write_json(
        snapshot_path,
        [dataclasses.asdict(record) for record in _selected_records_from_ids(records, selected)],
    )
    print(f"[select] embedding selected={len(selected)}", flush=True)
    return selected, meta, False


def _base_user_task(case_theme: str) -> str:
    return (
        "주제: 의뢰인이 2025년 1월부터 3월까지의 사건으로 징계를 받았고, 그중 일부 사건은 징계권자가 당시 이미 알고 있었는데 그때는 징계하지 않았다가 나중에 다른 사안과 합산해 다시 징계하려고 한다. "
        "이 합산 징계가 부당한지에 관하여 변호인 의견서 텍스트를 작성한다. "
        f"세부 사건 메모: {case_theme}"
    )


def _format_question_case_citation(case_number: str, court: str, decision_date: str, case_name: str) -> str:
    case_number = _normalize_space(case_number)
    case_name = _normalize_space(case_name)
    if case_name == "LBOX 익명화":
        # source_dataset='02_lbox_open' 행은 식별자 자체가 익명화돼 있음.
        return "참조 판례 (LBOX 익명화)"
    # Display identity is intentionally sparse. The DB's court/date/case_name
    # values can be rule-extracted from body text and may confuse 처분일 with
    # 선고일, so writer prompts must not receive polished full citations.
    return f"{case_number} 판결" if case_number else "참조 판례"


def _hydrate_question_claims(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    hydrated: list[dict[str, Any]] = []
    for claim in claims:
        copied = copy.deepcopy(claim)
        primary_case = next(
            (
                row
                for row in copied.get("supporting_cases") or []
                if _normalize_space(row.get("case_number"))
            ),
            {},
        )
        if not _normalize_space(copied.get("case_number")):
            copied["case_number"] = _normalize_space(primary_case.get("case_number"))
        if not _normalize_space(copied.get("court")):
            copied["court"] = _normalize_space(primary_case.get("court"))
        if not _normalize_space(copied.get("decision_date")):
            copied["decision_date"] = _normalize_space(primary_case.get("decision_date"))
        if not _normalize_space(copied.get("case_name")):
            copied["case_name"] = _normalize_space(primary_case.get("case_name"))
        copied["citation"] = _format_question_case_citation(
            str(copied.get("case_number") or ""),
            str(copied.get("court") or ""),
            str(copied.get("decision_date") or ""),
            str(copied.get("case_name") or ""),
        )
        for side_key in ("support_spans", "oppose_spans"):
            normalized_spans: list[dict[str, Any]] = []
            for span in copied.get(side_key) or []:
                span_copy = dict(span)
                span_copy["citation"] = copied["citation"]
                normalized_spans.append(span_copy)
            copied[side_key] = normalized_spans
        hydrated.append(copied)
    return hydrated


def _render_question_claim_for_prompt(claim: dict[str, Any], *, for_final_writer: bool = False) -> str:
    primary_citation = _format_question_case_citation(
        str(claim.get("case_number") or ""),
        str(claim.get("court") or ""),
        str(claim.get("decision_date") or ""),
        str(claim.get("case_name") or ""),
    )
    # The token shorthand the writer uses in body. `claim_index` is a 1-based
    # ordinal of this claim in the writer's view; `S{n}` indexes the support
    # spans (or `O{n}` for oppose). The writer must NEVER write metadata
    # directly — only `[N]`, `[N-Sm]`, `[N-Om]` tokens. Backend rewrite
    # substitutes them with the real citation + quote.
    claim_index = claim.get("_writer_claim_index") or 0
    support_spans = claim.get("support_spans") or []
    oppose_spans = claim.get("oppose_spans") or []
    if support_spans:
        support_lines = []
        for span_idx, span in enumerate(support_spans, start=1):
            token = f"[{claim_index}-S{span_idx}]"
            support_lines.append(f"- 토큰 `{token}` → ({primary_citation}) \"{span.get('quote')}\"")
        support = "\n".join(support_lines)
    else:
        support = "- (없음)"
    if oppose_spans:
        oppose_lines = []
        for span_idx, span in enumerate(oppose_spans, start=1):
            token = f"[{claim_index}-O{span_idx}]"
            oppose_lines.append(f"- 토큰 `{token}` → ({primary_citation}) \"{span.get('quote')}\"")
        oppose = "\n".join(oppose_lines)
    else:
        oppose = "- (없음)"
    supporting_cases = "\n".join(
        f"- {row.get('court') or ''} {row.get('decision_date') or ''} {row.get('case_number') or ''} {row.get('case_name') or ''}".strip()
        for row in claim.get("supporting_cases") or []
    ) or "- (없음)"
    list_fields = [
        ("유리하게 쓸 논리", claim.get("usable_favorable_logic")),
        ("불리하게 작용할 논리", claim.get("usable_unfavorable_logic")),
        ("유리해지는 요소", claim.get("favorable_factors")),
        ("불리해지는 요소", claim.get("unfavorable_factors")),
        ("주의점", claim.get("cautions")),
        ("반대근거", claim.get("counter_evidence")),
    ]
    detail_blocks = []
    for label, values in list_fields:
        values = values or []
        if not values:
            continue
        lines = "\n".join(f"- {item}" for item in values)
        detail_blocks.append(f"{label}:\n{lines}")
    detail_text = ("\n".join(detail_blocks) + "\n") if detail_blocks else ""
    if for_final_writer:
        support_count = int(claim.get("supporting_case_count") or 0)
        support_strength = "복수 근거" if support_count >= 2 else "단일 근거"
        return (
            f"writer 토큰: [{claim_index}]\n"
            f"주장 축: {claim.get('claim_axis')}\n"
            f"주장: {claim.get('claim_text')}\n"
            f"사용자 목표 기준: {claim.get('stance_to_user_goal')}\n"
            f"확실성: {claim.get('certainty')} / {claim.get('certainty_reason')}\n"
            f"동일상황 직접 적용례 존재: {claim.get('same_situation_case_exists')}\n"
            f"근거 강도: {support_strength}\n"
            f"문맥 요약: {claim.get('context_summary') or '(없음)'}\n"
            f"판례 요약: {claim.get('case_summary') or '(없음)'}\n"
            f"지지 판례:\n{supporting_cases}\n"
            "근거 적합성 자율 검토 기준:\n"
            "- 아래 지지 인용이 이 주장과 주체, 객체, 행위태양, 법리, 결론을 실제로 같이 말하는지 먼저 따져라.\n"
            "- 인용문이 `타인에게 지시/교사/비서/부하/직원에게 삭제 요청`을 말하는데 주장이 `본인이 직접 스스로 한 행위`라면 직접 지지 근거가 아니다.\n"
            "- 인용문이 claim을 직접 지지하지 않으면 본문 근거로 쓰지 말고, 필요할 때만 `구별되는 판례` 또는 `타인을 이용한 경우의 위험`으로 설명하라.\n"
            "- 확신이 없으면 그 claim/citation은 본문 결론 근거에서 제외하라.\n"
            + detail_text
            + f"지지 인용:\n{support}\n반대 인용:\n{oppose}\n"
        )
    return (
        f"claim_id: {claim.get('claim_id')} (writer 토큰: [{claim_index}])\n"
        f"주장 축: {claim.get('claim_axis')}\n"
        f"주장: {claim.get('claim_text')}\n"
        f"사용자 목표 기준: {claim.get('stance_to_user_goal')}\n"
        f"확실성: {claim.get('certainty')} / {claim.get('certainty_reason')}\n"
        f"동일상황 직접 적용례 존재: {claim.get('same_situation_case_exists')}\n"
        f"문맥 요약: {claim.get('context_summary') or '(없음)'}\n"
        f"판례 요약: {claim.get('case_summary') or '(없음)'}\n"
        f"지지 판례 수: {claim.get('supporting_case_count') or 0}\n"
        f"지지 판례:\n{supporting_cases}\n"
        + detail_text
        + f"지지 인용:\n{support}\n반대 인용:\n{oppose}\n"
    )


def _normalize_for_coverage(text: str) -> str:
    return _normalize_space(text).lower()


def _assign_question_claim_ids(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for index, claim in enumerate(claims, start=1):
        copied = dict(claim)
        copied["claim_id"] = copied.get("claim_id") or f"CLAIM-{index:03d}"
        # Writer-facing 1-based index used in `[N]` / `[N-Sm]` body tokens.
        # Stable across one writer invocation; backend rewrite uses it to
        # substitute tokens with the real citation + quote.
        copied["_writer_claim_index"] = index
        out.append(copied)
    return out


def _build_question_precedent_catalog(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    catalog: dict[str, dict[str, Any]] = {}
    for claim in claims:
        for case in claim.get("supporting_cases") or []:
            case_number = _normalize_space(case.get("case_number"))
            if not case_number:
                continue
            row = catalog.setdefault(
                case_number,
                {
                    "case_number": case_number,
                    "court": _normalize_space(case.get("court")),
                    "decision_date": _normalize_space(case.get("decision_date")),
                    "case_name": _normalize_space(case.get("case_name")),
                    "supported_claim_ids": [],
                    "supported_claim_axes": [],
                },
            )
            claim_id = _normalize_space(claim.get("claim_id"))
            claim_axis = _normalize_space(claim.get("claim_axis"))
            if claim_id and claim_id not in row["supported_claim_ids"]:
                row["supported_claim_ids"].append(claim_id)
            if claim_axis and claim_axis not in row["supported_claim_axes"]:
                row["supported_claim_axes"].append(claim_axis)
    rows = list(catalog.values())
    rows.sort(key=lambda item: (item.get("decision_date", ""), item.get("case_number", "")), reverse=True)
    return rows


def _render_question_precedent_catalog(catalog: list[dict[str, Any]]) -> str:
    if not catalog:
        return "- (없음)"
    return "\n".join(
        f"- {item.get('case_number')} | {item.get('court')} | {item.get('decision_date')} | {item.get('case_name')} | 관련 주장ID: {', '.join(item.get('supported_claim_ids') or [])}"
        for item in catalog
    )


def _normalize_precedent_buckets(raw: Any, catalog: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    allowed = ("very_similar", "similar", "usable", "other")
    catalog_by_case = {
        _normalize_space(item.get("case_number")): item
        for item in catalog
        if _normalize_space(item.get("case_number"))
    }
    buckets: dict[str, list[dict[str, Any]]] = {key: [] for key in allowed}
    seen_cases: set[str] = set()
    if not isinstance(raw, dict):
        return buckets
    for key in allowed:
        values = raw.get(key)
        if not isinstance(values, list):
            continue
        for value in values:
            if not isinstance(value, dict):
                continue
            case_number = _normalize_space(value.get("case_number"))
            if not case_number or case_number in seen_cases:
                continue
            catalog_row = catalog_by_case.get(case_number)
            if not catalog_row:
                continue
            seen_cases.add(case_number)
            buckets[key].append(
                {
                    "case_number": case_number,
                    "court": catalog_row.get("court") or "",
                    "decision_date": catalog_row.get("decision_date") or "",
                    "case_name": catalog_row.get("case_name") or "",
                    "supported_claim_ids": list(catalog_row.get("supported_claim_ids") or []),
                    "supported_claim_axes": list(catalog_row.get("supported_claim_axes") or []),
                    "why": _normalize_space(value.get("why")) or "",
                }
            )
    return buckets


_CLAIM_GROUP_STOPWORDS = {
    "주장",
    "원칙",
    "여부",
    "조건",
    "적용",
    "한계",
    "판단",
    "효력",
    "사유",
    "근거",
    "무효",
    "취소",
    "도과",
    "및",
    "따른",
    "대한",
    "관련",
}


def _tokenize_claim_axis(axis: str) -> list[str]:
    tokens = re.findall(r"[가-힣A-Za-z0-9]+", _normalize_space(axis))
    out: list[str] = []
    for token in tokens:
        normalized = token.strip()
        if len(normalized) < 2:
            continue
        if normalized in _CLAIM_GROUP_STOPWORDS:
            continue
        out.append(normalized)
    return out


def _claim_group_label(axis: str) -> str:
    normalized = _normalize_space(axis)
    if not normalized:
        return "기타 주장"
    rules = [
        ("징계시효", ("징계시효", "기산점", "계속적 위반", "시효")),
        ("이중징계", ("이중징계",)),
        ("신뢰보호", ("신뢰보호", "신의칙")),
        ("재량권 남용", ("재량권", "재량권남용", "양정", "과중", "비례")),
        ("절차적 하자 및 권한", ("절차", "정족수", "추인", "방어권", "권한", "특정", "의결")),
        ("확인의 이익", ("확인의 이익", "소송 요건")),
    ]
    for label, keywords in rules:
        if any(keyword in normalized for keyword in keywords):
            return label
    return normalized


def _build_fallback_claim_groups(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    token_counts: Counter[str] = Counter()
    axis_to_tokens: dict[str, list[str]] = {}
    for claim in claims:
        axis = _normalize_space(claim.get("claim_axis"))
        if not axis:
            continue
        tokens = _tokenize_claim_axis(axis)
        axis_to_tokens[axis] = tokens
        token_counts.update(set(tokens))
    grouped: dict[str, list[str]] = {}
    for claim in claims:
        claim_id = _normalize_space(claim.get("claim_id"))
        axis = _normalize_space(claim.get("claim_axis"))
        if not claim_id or not axis:
            continue
        tokens = sorted(
            [token for token in axis_to_tokens.get(axis, []) if token_counts.get(token, 0) >= 2 and len(token) >= 3],
            key=lambda item: (-len(item), axis.find(item)),
        )
        label = _claim_group_label(tokens[0] if tokens else axis)
        grouped.setdefault(label, []).append(claim_id)
    rows = [{"label": label, "claim_ids": claim_ids} for label, claim_ids in grouped.items() if claim_ids]
    rows.sort(key=lambda item: (-len(item.get("claim_ids") or []), item.get("label") or ""))
    return rows


def _normalize_claim_groups(raw: Any, claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    claim_ids = {_normalize_space(item.get("claim_id")) for item in claims}
    groups: list[dict[str, Any]] = []
    if not isinstance(raw, list):
        return groups
    seen_ids: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        label = _claim_group_label(_normalize_space(item.get("label")))
        if not label:
            continue
        group_claim_ids: list[str] = []
        for value in item.get("claim_ids") or []:
            claim_id = _normalize_space(value)
            if claim_id and claim_id in claim_ids and claim_id not in seen_ids:
                group_claim_ids.append(claim_id)
                seen_ids.add(claim_id)
        if group_claim_ids:
            groups.append({"label": label, "claim_ids": group_claim_ids})
    return groups


def _render_question_claim_groups(claim_groups: list[dict[str, Any]], claims: list[dict[str, Any]]) -> str:
    if not claim_groups:
        return "- (없음)"
    claim_by_id = {_normalize_space(item.get("claim_id")): item for item in claims}
    rows: list[str] = []
    for group in claim_groups:
        label = _normalize_space(group.get("label"))
        claim_ids = [_normalize_space(item) for item in group.get("claim_ids") or [] if _normalize_space(item)]
        if not label or not claim_ids:
            continue
        bullet_lines = []
        for claim_id in claim_ids:
            claim = claim_by_id.get(claim_id)
            if not claim:
                continue
            axis = _normalize_space(claim.get("claim_axis")) or claim_id
            support_count = int(claim.get("supporting_case_count") or 0)
            support_strength = "복수 근거" if support_count >= 2 else "단일 근거"
            bullet_lines.append(f"- {axis} | {support_strength}")
        if bullet_lines:
            rows.append(f"[{label}]\n" + "\n".join(bullet_lines))
    return "\n\n".join(rows) if rows else "- (없음)"


def build_question_answer_plan_prompt(
    *,
    user_task: str,
    claims: list[dict[str, Any]],
    catalog: list[dict[str, Any]],
    analysis_mode: str = "",
) -> str:
    top_claims = sorted(
        claims,
        key=lambda item: (
            -int(item.get("supporting_case_count") or 0),
            -_certainty_sort_value(item.get("certainty", "")),
            item.get("claim_axis", ""),
        ),
    )[:120]
    proposition_verification_block = (
        "- 선택형·견해-설명형 문제(예: `〈견해〉`, `〈설명〉`, `선지:`가 있는 입력)는 선택지를 상담 결론으로 바꾸지 말고, 각 선지의 연결쌍을 법률명제로 보아 직접 지지·관련이나 직접 아님·충돌·근거 없음으로 검증한 뒤 likely_outcome에 정답 번호/선지 조합을 적는다.\n"
        "- 선택형·견해-설명형 문제에서 법리명이 가깝기만 한 연결은 직접 지지로 보지 말고 confidence_basis에 왜 제외되는지 적는다.\n"
    ) if analysis_mode == "beta8" else ""
    return (
        "아래 claim ledger와 판례 catalog를 보고 JSON만 출력하라.\n"
        "목표는 본문에 넣을 주장과 참고 판례 목록의 위계를 고르는 것이다.\n"
        "중요:\n"
        "- body_claim_ids에는 본문에서 다룰 주장만 넣는다.\n"
        "- 반드시 claim ledger에 있는 exact claim_id만 사용한다.\n"
        "- 같은 주장 축을 지지하는 별개 판례 수가 많을수록 신뢰도가 더 강하다고 보고 우선한다.\n"
        "- 판례가 서로 충돌하면 결정일자(decision_date)가 더 최근인 판례를 우선한다.\n"
        "  · 특히 상급심(대법원 > 고등법원 > 지방법원)의 최근 판결은 하급심·과거 판례를 사실상 무력화시키는 경우가 많다.\n"
        "  · 동급 법원이라도 최근 판례가 과거 입장을 변경했다면 likely_outcome/confidence_basis는 최신 판례 기준으로 적는다.\n"
        "  · 과거 판례를 인용해야 한다면 confidence_basis 또는 harmful_facts에 \"과거 판례 X는 최근 판례 Y로 사실상 변경됨\"이라고 명시한다.\n"
        "- precedent_buckets 분류 시에도 결정일자가 더 최근이거나 상급심인 판례를 같은 카테고리 내 앞쪽에 배치한다.\n"
        "- likely_outcome에는 현재 자료상 가장 가능성이 높은 결론을 한 문장으로 적는다.\n"
        + proposition_verification_block
        +
        "- confidence_basis에는 왜 그 결론이 더 유력한지 2~4개 bullet로 적는다.\n"
        "- likely_outcome/confidence_basis/helpful_facts/harmful_facts에는 CLAIM-ID, writer 토큰, 내부 순번, exact supporting_case_count 숫자를 노출하지 말라. 숫자가 필요하면 `복수 판례` 정도로만 표현한다.\n"
        "- helpful_facts에는 질문자가 유리하게 만들기 위해 더 확보·정리해야 할 사실을 적는다.\n"
        "- harmful_facts에는 질문자에게 불리하게 작용할 사실·행동을 적는다.\n"
        "- claim_groups에는 본문에서 함께 다룰 주장 묶음을 넣는다.\n"
        "- 같은 법리·논리 축이면 claim_axis가 조금 달라도 하나의 group label 아래로 묶는다.\n"
        "- claim_groups에는 exact claim_id만 사용한다.\n"
        "- precedent_buckets는 very_similar, similar, usable, other 네 키만 사용한다.\n"
        "- 매우 유사한 판례: 유형 및 정황 모두 매우 가까운 판례\n"
        "- 유사한 판례: 유형은 같고 정황이 조금 다르지만 유불리 조건을 뽑아낼 수 있는 판례\n"
        "- 이용할 만한 판례: 유형은 달라도 내부 논리를 쓸 수 있는 판례\n"
        "- 기타: 직접적 관련이 낮거나 분류 자신이 없는 판례\n"
        "- 각 판례는 한 버킷에만 넣는다. 자신 없으면 other다.\n"
        "- very_similar/similar/usable에 들어간 판례만 coverage 대상으로 간주한다.\n"
        "- 새 주장, 새 판례번호, 새 사실을 만들지 말라.\n\n"
        f"질문:\n{user_task}\n\n"
        "[claim ledger]\n"
        + "\n\n".join(_render_question_claim_for_prompt(claim) for claim in top_claims)
        + "\n\n[precedent catalog]\n"
        + _render_question_precedent_catalog(catalog)
        + "\n\n출력 JSON 스키마:\n"
        + '{\n  "likely_outcome": "...",\n  "confidence_basis": ["..."],\n  "helpful_facts": ["..."],\n  "harmful_facts": ["..."],\n  "body_claim_ids": ["CLAIM-001"],\n  "claim_groups": [{"label": "징계시효", "claim_ids": ["CLAIM-001", "CLAIM-002"]}],\n  "precedent_buckets": {"very_similar": [{"case_number": "...", "why": "..."}], "similar": [], "usable": [], "other": []}\n}'
    )


def _extract_question_answer_plan(*, raw: str, claims: list[dict[str, Any]], catalog: list[dict[str, Any]]) -> dict[str, Any]:
    claim_ids = {_normalize_space(item.get("claim_id")) for item in claims}
    try:
        obj = json.loads(_extract_json_block(raw))
    except Exception:
        obj = {}
    body_claim_ids: list[str] = []
    for value in obj.get("body_claim_ids") or []:
        claim_id = _normalize_space(value)
        if claim_id and claim_id in claim_ids and claim_id not in body_claim_ids:
            body_claim_ids.append(claim_id)
    buckets = _normalize_precedent_buckets(obj.get("precedent_buckets"), catalog)
    return {
        "likely_outcome": _normalize_space(obj.get("likely_outcome")),
        "confidence_basis": _coerce_string_list(obj.get("confidence_basis")),
        "helpful_facts": _coerce_string_list(obj.get("helpful_facts")),
        "harmful_facts": _coerce_string_list(obj.get("harmful_facts")),
        "body_claim_ids": body_claim_ids,
        "claim_groups": _normalize_claim_groups(obj.get("claim_groups"), claims),
        "precedent_buckets": buckets,
    }


def _claim_certainty_points(value: str) -> int:
    normalized = _normalize_space(value).lower()
    return {
        "very_high": 5,
        "high": 4,
        "medium": 3,
        "low": 2,
        "speculative": 1,
    }.get(normalized, 2)


def _claim_strength_score(claim: dict[str, Any]) -> int:
    support_cases = int(claim.get("supporting_case_count") or 0)
    support_spans = len(claim.get("support_spans") or [])
    same_situation = 2 if claim.get("same_situation_case_exists") else 0
    return (support_cases * 5) + (_claim_certainty_points(str(claim.get("certainty") or "")) * 3) + support_spans + same_situation


def _fallback_question_answer_plan(claims: list[dict[str, Any]], catalog: list[dict[str, Any]]) -> dict[str, Any]:
    hydrated_claims = _hydrate_question_claims(claims)
    ranked_claims = sorted(hydrated_claims, key=lambda item: (-_claim_strength_score(item), item.get("claim_axis") or ""))
    body_claim_ids = [
        str(item.get("claim_id") or "")
        for item in ranked_claims[: min(8, len(ranked_claims))]
        if _normalize_space(item.get("claim_id"))
    ]
    favorable_score = sum(_claim_strength_score(item) for item in hydrated_claims if _normalize_space(item.get("stance_to_user_goal")) == "유리")
    unfavorable_score = sum(_claim_strength_score(item) for item in hydrated_claims if _normalize_space(item.get("stance_to_user_goal")) == "불리")
    top_favorable = next((item for item in ranked_claims if _normalize_space(item.get("stance_to_user_goal")) == "유리"), None)
    top_unfavorable = next((item for item in ranked_claims if _normalize_space(item.get("stance_to_user_goal")) == "불리"), None)
    top_claim = ranked_claims[0] if ranked_claims else None
    top_axis = _normalize_space((top_claim or {}).get("claim_axis"))
    top_support = int((top_claim or {}).get("supporting_case_count") or 0)
    top_direction = _normalize_space((top_claim or {}).get("stance_to_user_goal"))
    support_examples = [
        _normalize_space(item.get("case_number"))
        for item in ((top_claim or {}).get("supporting_cases") or [])
        if _normalize_space(item.get("case_number"))
    ][:2]
    repeated_line = ""
    if top_support >= 2:
        if support_examples:
            repeated_line = f"{', '.join(support_examples)} 등 복수 판례가 같은 방향으로 반복적으로 뒷받침한다."
        else:
            repeated_line = "복수 판례가 같은 방향으로 반복적으로 뒷받침한다."
    if favorable_score > unfavorable_score * 1.08 or (top_direction == "유리" and top_support >= 2):
        axis = _normalize_space((top_favorable or top_claim or {}).get("claim_axis"))
        likely_outcome = (
            f"현재 자료상 질문자에게 유리한 결론이 가장 가능성이 높고, 특히 `{axis}` 묶음이 가장 강하다. {repeated_line}".strip()
            if axis
            else f"현재 자료상 질문자에게 유리한 결론이 가장 가능성이 높다. {repeated_line}".strip()
        )
    elif unfavorable_score > favorable_score * 1.08 or (top_direction == "불리" and top_support >= 2):
        axis = _normalize_space((top_unfavorable or top_claim or {}).get("claim_axis"))
        likely_outcome = (
            f"현재 자료상 질문자에게 불리한 결론이 가장 가능성이 높고, 특히 `{axis}` 묶음이 가장 위험하다. {repeated_line}".strip()
            if axis
            else f"현재 자료상 질문자에게 불리한 결론이 가장 가능성이 높다. {repeated_line}".strip()
        )
    elif top_axis:
        likely_outcome = f"현재 자료상 `{top_axis}` 묶음이 가장 직접적인 판단축이며, 이 축이 결론을 좌우할 가능성이 가장 높다. {repeated_line}".strip()
    else:
        likely_outcome = "현재 자료상 핵심 사실관계에 따라 결론이 갈릴 여지가 크지만, 반복적으로 지지되는 주장 축부터 우선 검토해야 한다."
    confidence_basis: list[str] = []
    for item in ranked_claims[:4]:
        claim_axis = _normalize_space(item.get("claim_axis"))
        if not claim_axis:
            continue
        support_cases = int(item.get("supporting_case_count") or 0)
        if support_cases >= 2:
            confidence_basis.append(f"`{claim_axis}`는 복수 판례가 같은 방향으로 지지해 신뢰도가 높다.")
        elif item.get("same_situation_case_exists"):
            confidence_basis.append(f"`{claim_axis}`는 현재 사안과 직접 맞닿는 판례가 확인된다.")
        elif item.get("certainty_reason"):
            confidence_basis.append(f"`{claim_axis}`는 {item.get('certainty_reason')}")
        else:
            confidence_basis.append(f"`{claim_axis}`는 현재 자료상 비교적 강한 주장 축으로 평가된다.")
    helpful_facts: list[str] = []
    harmful_facts: list[str] = []
    for item in ranked_claims:
        for source in ("favorable_factors", "required_facts", "favorable_basis"):
            for fact in _coerce_string_list(item.get(source)):
                if fact and fact not in helpful_facts:
                    helpful_facts.append(fact)
        for source in ("unfavorable_factors", "cautions", "counter_evidence", "unfavorable_basis"):
            for fact in _coerce_string_list(item.get(source)):
                if fact and fact not in harmful_facts:
                    harmful_facts.append(fact)
    if not helpful_facts:
        helpful_facts = [
            _normalize_space(item.get("claim_text"))
            for item in ranked_claims
            if _normalize_space(item.get("stance_to_user_goal")) == "유리" and _normalize_space(item.get("claim_text"))
        ][:6]
    if not harmful_facts:
        harmful_facts = [
            _normalize_space(item.get("claim_text"))
            for item in ranked_claims
            if _normalize_space(item.get("stance_to_user_goal")) == "불리" and _normalize_space(item.get("claim_text"))
        ][:6]
    return {
        "likely_outcome": likely_outcome,
        "confidence_basis": confidence_basis[:4],
        "helpful_facts": helpful_facts[:6],
        "harmful_facts": harmful_facts[:6],
        "body_claim_ids": body_claim_ids,
        "claim_groups": _build_fallback_claim_groups([item for item in hydrated_claims if str(item.get("claim_id") or "") in body_claim_ids]),
        "precedent_buckets": _normalize_precedent_buckets(
            {
                "very_similar": [{"case_number": row.get("case_number"), "why": ""} for row in catalog[:3]],
                "similar": [{"case_number": row.get("case_number"), "why": ""} for row in catalog[3:8]],
                "usable": [{"case_number": row.get("case_number"), "why": ""} for row in catalog[8:12]],
                "other": [],
            },
            catalog,
        ),
    }


def _required_precedent_case_numbers(precedent_buckets: dict[str, list[dict[str, Any]]]) -> list[str]:
    required: list[str] = []
    for key in ("very_similar", "similar", "usable"):
        for row in precedent_buckets.get(key) or []:
            case_number = _normalize_space(row.get("case_number"))
            if case_number and case_number not in required:
                required.append(case_number)
    return required


_MARKDOWN_HEADING_RE = re.compile(r"(?m)^[ \t]{0,3}(#{1,6})\s+(.+?)\s*$")


def _clean_markdown_heading_title(value: str) -> str:
    return _normalize_space(
        re.sub(r"[*_`#]+", " ", str(value or "")).replace(":", " ")
    )


def _find_markdown_section(answer_text: str, heading_title: str, *, min_level: int = 1, max_level: int = 6) -> tuple[int, int, int, int] | None:
    target = _normalize_for_coverage(heading_title)
    if not target:
        return None
    headings = list(_MARKDOWN_HEADING_RE.finditer(answer_text))
    for index, match in enumerate(headings):
        level = len(match.group(1))
        if level < min_level or level > max_level:
            continue
        title = _clean_markdown_heading_title(match.group(2))
        if _normalize_for_coverage(title) != target:
            continue
        section_end = len(answer_text)
        for next_match in headings[index + 1 :]:
            if len(next_match.group(1)) <= level:
                section_end = next_match.start()
                break
        return (match.start(), match.end(), section_end, level)
    return None


def _reference_list_start(answer_text: str) -> int | None:
    for match in _MARKDOWN_HEADING_RE.finditer(answer_text):
        title = _normalize_for_coverage(_clean_markdown_heading_title(match.group(2)))
        if "참고판례목록" in re.sub(r"\s+", "", title):
            return match.start()
    marker = re.search(r"(?m)^\s*참고\s*판례\s*목록\s*$", answer_text)
    if marker:
        return marker.start()
    return None


def _answer_without_reference_list(answer_text: str) -> str:
    ref_start = _reference_list_start(answer_text)
    if ref_start is None:
        return answer_text
    return answer_text[:ref_start]


def _insert_before_reference_list(answer_text: str, content: str) -> str:
    insert = content.strip()
    if not insert:
        return answer_text
    ref_start = _reference_list_start(answer_text)
    if ref_start is None:
        return f"{answer_text.rstrip()}\n\n{insert}".strip()
    return f"{answer_text[:ref_start].rstrip()}\n\n{insert}\n\n{answer_text[ref_start:].lstrip()}".strip()


def _normalize_patch_snippet(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "", str(text or "")).lower()


def _find_patch_snippet_range(text: str, snippet: str, from_index: int = 0) -> tuple[int, int] | None:
    raw = str(snippet or "")
    if not raw.strip():
        return None
    sub = text[from_index:]
    exact = sub.find(raw)
    if exact >= 0:
        return (from_index + exact, from_index + exact + len(raw))

    normalized_snippet = _normalize_patch_snippet(raw)
    if not normalized_snippet:
        return None
    normalized_chars: list[str] = []
    index_map: list[int] = []
    for index, char in enumerate(sub):
        normalized = _normalize_patch_snippet(char)
        if not normalized:
            continue
        for normalized_char in normalized:
            normalized_chars.append(normalized_char)
            index_map.append(index)
    normalized_text = "".join(normalized_chars)
    found = normalized_text.find(normalized_snippet)
    if found < 0:
        return None
    start = index_map[found]
    end = index_map[found + len(normalized_snippet) - 1] + 1
    return (from_index + start, from_index + end)


def _parse_tag_value(text: str, tag_name: str) -> str:
    match = re.search(rf"<\s*{re.escape(tag_name)}\s*>([\s\S]*?)<\s*/\s*{re.escape(tag_name)}\s*>", text, flags=re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _parse_question_coverage_patch_blocks(raw: str) -> list[dict[str, str]]:
    blocks = re.findall(r"<\s*patch\s*>([\s\S]*?)<\s*/\s*patch\s*>", str(raw or ""), flags=re.IGNORECASE)
    patches: list[dict[str, str]] = []
    for block in blocks:
        content = _parse_tag_value(block, "content")
        if not content.strip():
            continue
        patches.append(
            {
                "section": _parse_tag_value(block, "section"),
                "op": (_parse_tag_value(block, "op") or "append").lower(),
                "before": _parse_tag_value(block, "before"),
                "after": _parse_tag_value(block, "after"),
                "content": content,
            }
        )
    return patches


def _looks_like_markdown_block(text: str) -> bool:
    stripped = str(text or "").lstrip()
    return bool(re.match(r"^(\||[-*+]\s+|\d+\.\s+|#{1,6}\s+|>\s+|```)", stripped))


def _glue_patch_content(prefix: str, content: str, suffix: str) -> str:
    if not _looks_like_markdown_block(content):
        return content
    before = "\n" if prefix and not prefix.endswith("\n") and not content.startswith("\n") else ""
    after = "\n" if suffix and not suffix.startswith("\n") and not content.endswith("\n") else ""
    return f"{before}{content}{after}"


def _is_inside_table_row(text: str, index: int) -> bool:
    last_newline = text.rfind("\n", 0, max(index, 0))
    line_start = 0 if last_newline < 0 else last_newline + 1
    next_newline = text.find("\n", index)
    line_end = len(text) if next_newline < 0 else next_newline
    return bool(re.match(r"^\s*\|", text[line_start:line_end]))


def _question_patch_section_range(answer_text: str, section_name: str) -> tuple[int, int]:
    section_name = _normalize_space(section_name)
    if section_name:
        section = _find_markdown_section(answer_text, section_name, min_level=1, max_level=6)
        if section:
            start, _heading_end, section_end, _level = section
            return (start, section_end)
    ref_start = _reference_list_start(answer_text)
    return (0, ref_start if ref_start is not None else len(answer_text))


def _apply_question_coverage_patch_block(answer_text: str, patch: dict[str, str]) -> tuple[str, bool]:
    op = (patch.get("op") or "append").lower()
    if op not in {"append", "insert_after", "insert_before", "insert_between"}:
        return (answer_text, False)
    content = str(patch.get("content") or "").strip()
    if not content:
        return (answer_text, False)
    section_start, section_end = _question_patch_section_range(answer_text, patch.get("section") or "")
    section_text = answer_text[section_start:section_end]
    before = patch.get("before") or ""
    after = patch.get("after") or ""

    if op == "append":
        insert_pos = section_end
    else:
        before_range = _find_patch_snippet_range(section_text, before, 0) if before else None
        if not before_range:
            return (answer_text, False)
        if op == "insert_after":
            insert_pos = section_start + before_range[1]
        elif op == "insert_before":
            insert_pos = section_start + before_range[0]
        else:
            after_range = _find_patch_snippet_range(section_text, after, before_range[1]) if after else None
            if not after_range:
                return (answer_text, False)
            insert_pos = section_start + after_range[0]
    if _is_inside_table_row(answer_text, insert_pos):
        return (answer_text, False)
    prefix = answer_text[:insert_pos]
    suffix = answer_text[insert_pos:]
    glued = _glue_patch_content(prefix, content, suffix)
    return (f"{prefix.rstrip()}\n\n{glued.strip()}\n\n{suffix.lstrip()}".strip(), True)


def _apply_question_coverage_patch_blocks(answer_text: str, patches: list[dict[str, str]]) -> tuple[str, int]:
    output = answer_text
    applied_count = 0
    for patch in patches:
        output, applied = _apply_question_coverage_patch_block(output, patch)
        if applied:
            applied_count += 1
    return (output, applied_count)


def _format_claim_support_quote(claim: dict[str, Any]) -> str:
    for citation, quote, evidence_id in _claim_support_markers(claim):
        if not quote:
            continue
        if citation:
            return f"**({citation})** \"{quote}\""
        if evidence_id:
            return f"[{evidence_id}] \"{quote}\""
        return f"\"{quote}\""
    return ""


def _format_claim_coverage_block(claim: dict[str, Any]) -> str:
    axis = _normalize_space(claim.get("claim_axis")) or "관련 주장"
    body = _normalize_space(claim.get("claim_text") or claim.get("context_summary") or claim.get("case_summary"))
    quote = _format_claim_support_quote(claim)
    lines = [f"### {axis}"]
    if body:
        lines.append(body)
    if quote:
        lines.extend(["근거 인용", quote])
    return "\n\n".join(lines)


def _append_claim_quote_to_existing_section(answer_text: str, claim: dict[str, Any]) -> str:
    axis = _normalize_space(claim.get("claim_axis"))
    quote = _format_claim_support_quote(claim)
    if not axis or not quote:
        return answer_text
    section = _find_markdown_section(answer_text, axis, min_level=2, max_level=6)
    if not section:
        return _insert_before_reference_list(answer_text, _format_claim_coverage_block(claim))
    start, heading_end, section_end, _level = section
    section_text = answer_text[heading_end:section_end]
    if _normalize_for_coverage(quote) in _normalize_for_coverage(section_text):
        return answer_text
    insert = f"\n\n근거 인용\n\n{quote}\n\n"
    return f"{answer_text[:section_end].rstrip()}{insert}{answer_text[section_end:].lstrip()}".strip()


def _find_required_precedent_row(precedent_buckets: dict[str, list[dict[str, Any]]], case_number: str) -> tuple[str, dict[str, Any]] | None:
    needle = _normalize_space(case_number)
    labels = {"very_similar": "매우 유사한 판례", "similar": "유사한 판례", "usable": "이용할 만한 판례"}
    for key in ("very_similar", "similar", "usable"):
        for row in precedent_buckets.get(key) or []:
            if _normalize_space(row.get("case_number")) == needle:
                return (labels[key], row)
    return None


def _format_precedent_body_sentence(row: dict[str, Any]) -> str:
    if not _normalize_space(row.get("case_number")):
        return ""
    citation = _format_question_case_citation(
        str(row.get("case_number") or ""),
        str(row.get("court") or ""),
        str(row.get("decision_date") or ""),
        str(row.get("case_name") or ""),
    )
    axes = ", ".join(_coerce_string_list(row.get("supported_claim_axes")))
    why = _normalize_space(row.get("why"))
    if axes and why:
        return f"또한 **({citation})** 역시 {axes}와 관련하여 {why}"
    if axes:
        return f"또한 **({citation})** 역시 {axes}와 관련해 같은 방향의 판단 근거로 검토할 수 있다."
    if why:
        return f"또한 **({citation})** 역시 {why}"
    return f"또한 **({citation})** 역시 같은 법리 축에서 참고할 수 있다."


def _append_precedent_sentence_to_body_section(
    answer_text: str,
    row: dict[str, Any],
    claims: list[dict[str, Any]],
) -> str:
    sentence = _format_precedent_body_sentence(row)
    if not sentence:
        return answer_text
    body_normalized = _normalize_for_coverage(_answer_without_reference_list(answer_text))
    case_number_norm = _normalize_for_coverage(row.get("case_number"))
    sentence_norm = _normalize_for_coverage(sentence)
    # Skip if (a) the precedent's case_number is already cited in body, or
    # (b) the exact sentence is already present (anonymous rows share the
    # generic `(참조 판례)` citation, so dedup on full sentence — otherwise the
    # same line gets appended 3-4 times across coverage iterations).
    if case_number_norm and case_number_norm in body_normalized:
        return answer_text
    if sentence_norm and sentence_norm in body_normalized:
        return answer_text
    claim_by_axis = {
        _normalize_for_coverage(claim.get("claim_axis")): claim
        for claim in claims
        if _normalize_space(claim.get("claim_axis"))
    }
    target_axis = ""
    for axis in _coerce_string_list(row.get("supported_claim_axes")):
        if _normalize_for_coverage(axis) in claim_by_axis:
            target_axis = axis
            break
    if target_axis:
        section = _find_markdown_section(answer_text, target_axis, min_level=2, max_level=6)
        if section:
            _start, _heading_end, section_end, _level = section
            return f"{answer_text[:section_end].rstrip()}\n\n{sentence}\n\n{answer_text[section_end:].lstrip()}".strip()
    block = f"### {target_axis or '관련 참고 판례'}\n\n{sentence}"
    return _insert_before_reference_list(answer_text, block)


def _apply_question_coverage_fallback(
    *,
    answer_text: str,
    claims: list[dict[str, Any]],
    precedent_buckets: dict[str, list[dict[str, Any]]],
    gaps: dict[str, list[str]],
) -> str:
    output = answer_text.strip()
    hydrated_claims = _hydrate_question_claims(claims)
    claim_by_axis = {
        _normalize_space(claim.get("claim_axis")): claim
        for claim in hydrated_claims
        if _normalize_space(claim.get("claim_axis"))
    }
    seen_axes: set[str] = set()
    for axis in [*(gaps.get("missing_axes") or []), *(gaps.get("missing_citations") or [])]:
        normalized_axis = _normalize_space(axis)
        if not normalized_axis or normalized_axis in seen_axes:
            continue
        seen_axes.add(normalized_axis)
        claim = claim_by_axis.get(normalized_axis)
        if not claim:
            continue
        if normalized_axis in (gaps.get("missing_axes") or []):
            output = _insert_before_reference_list(output, _format_claim_coverage_block(claim))
        else:
            output = _append_claim_quote_to_existing_section(output, claim)
    for case_number in gaps.get("missing_precedents") or []:
        found = _find_required_precedent_row(precedent_buckets, case_number)
        if not found:
            continue
        _bucket_label, row = found
        output = _append_precedent_sentence_to_body_section(output, row, hydrated_claims)
    return _rewrite_question_answer_citations(output, hydrated_claims)


def _claim_support_markers(claim: dict[str, Any]) -> list[tuple[str, str, str]]:
    markers: list[tuple[str, str, str]] = []
    citation = _format_question_case_citation(
        str(claim.get("case_number") or ""),
        str(claim.get("court") or ""),
        str(claim.get("decision_date") or ""),
        str(claim.get("case_name") or ""),
    )
    for span in claim.get("support_spans") or []:
        # 원문 resolved_text 우선 (LLM paraphrase 대신 우리가 특정한 원문 사용)
        quote = _normalize_space(span.get("resolved_text") or span.get("quote"))
        if quote:
            markers.append((citation, quote, _normalize_space(span.get("evidence_id"))))
    return markers


def find_question_coverage_gaps(
    answer_text: str,
    claims: list[dict[str, Any]],
    *,
    precedent_buckets: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, list[str]]:
    normalized_answer = _normalize_for_coverage(answer_text)
    missing_axes: list[str] = []
    missing_citations: list[str] = []
    missing_precedents: list[str] = []
    for claim in claims:
        claim_axis = _normalize_space(claim.get("claim_axis"))
        if not claim_axis:
            continue
        normalized_axis = _normalize_for_coverage(claim_axis)
        if normalized_axis not in normalized_answer:
            missing_axes.append(claim_axis)
            missing_citations.append(claim_axis)
            continue
        support_markers = _claim_support_markers(claim)
        if not support_markers:
            continue
        has_citation = any(
            (
                citation
                and _normalize_for_coverage(citation) in normalized_answer
                and _normalize_for_coverage(quote) in normalized_answer
            )
            or (
                evidence_id
                and _normalize_for_coverage(evidence_id) in normalized_answer
                and _normalize_for_coverage(quote) in normalized_answer
            )
            for citation, quote, evidence_id in support_markers
        )
        if not has_citation:
            missing_citations.append(claim_axis)
    normalized_body_answer = _normalize_for_coverage(_answer_without_reference_list(answer_text))
    for case_number in _required_precedent_case_numbers(precedent_buckets or {}):
        if _normalize_for_coverage(case_number) not in normalized_body_answer:
            missing_precedents.append(case_number)
    return {
        "missing_axes": missing_axes,
        "missing_citations": missing_citations,
        "missing_precedents": missing_precedents,
    }


def _render_question_precedent_buckets(
    precedent_buckets: dict[str, list[dict[str, Any]]],
    summaries: dict[str, dict[str, str]] | None = None,
) -> str:
    order = [
        ("very_similar", "매우 유사한 판례"),
        ("similar", "유사한 판례"),
        ("usable", "이용할 만한 판례"),
        ("other", "기타"),
    ]
    summaries = summaries or {}
    parts: list[str] = []
    for key, label in order:
        rows = precedent_buckets.get(key) or []
        if rows:
            lines: list[str] = []
            for row in rows:
                citation = _format_question_case_citation(
                    str(row.get("case_number") or ""),
                    str(row.get("court") or ""),
                    str(row.get("decision_date") or ""),
                    str(row.get("case_name") or ""),
                )
                axes = ", ".join(_coerce_string_list(row.get("supported_claim_axes")))
                why = (row.get("why") or "").strip()
                # Inject the LLM-generated case_summary so the writer is
                # grounded on the actual ruling content. WITHOUT this line
                # the model only sees court/date/case_number + the planner's
                # one-line `why`, and frequently hallucinates the facts of
                # the precedent it cites in body. We mark NO_SUMMARY rows so
                # the writer prompt below can refuse to invent body for them.
                file_id = str(row.get("source_file_id") or row.get("precedent_id") or "")
                summary_obj = summaries.get(file_id) or {}
                case_summary = (summary_obj.get("case_summary") or "").strip()
                summary_part = (
                    f" | 판례 요약 (사실 근거): {case_summary}"
                    if case_summary
                    else " | 판례 요약 (사실 근거): (없음 — 본문에서 이 판례의 사실관계를 절대 만들어 적지 말 것)"
                )
                lines.append(
                    f"- {citation} | 관련 주장: {axes} | 분류 사유: {why}{summary_part}"
                )
            body = "\n".join(lines)
        else:
            body = "- (없음)"
        parts.append(f"[{label}]\n{body}")
    return "\n\n".join(parts)


def _build_beta7_writer_prompt(
    *,
    user_task: str,
    claims: list[dict[str, Any]],
    precedent_buckets: dict[str, list[dict[str, Any]]],
    precedent_summaries: dict[str, dict[str, str]] | None,
) -> str:
    """Beta-7 minimal writer prompt.

    Philosophy: tell the writer (a) what the user asked, (b) what minimal
    structure is required, (c) which claims are available with their
    citation tokens. Do NOT pre-decide the conclusion / helpful_facts /
    glossary terms — the writer composes its own answer end-to-end so
    the final voice stays coherent. Backend post-pass only fixes
    markdown breakage and substitutes citation tokens.
    """
    claim_block = "\n\n".join(_render_question_claim_for_prompt(claim, for_final_writer=True) for claim in claims) or "(없음)"
    bucket_block = _render_question_precedent_buckets(precedent_buckets, precedent_summaries)
    return (
        "[질문]\n"
        f"{user_task}\n\n"
        "[해야 할 일]\n"
        "위 질문에 대해 한국어 마크다운 답변을 작성하라. 사용자가 자기 사례를 이해하도록 돕는 것이 목표.\n\n"
        "[필수 구조 — 이 순서를 지키지 않으면 실패]\n"
        "1. 답변의 첫 줄은 정확히 `## 어렵지 않아요` 한 줄. 다른 어떤 텍스트도 그 위에 두지 말 것.\n"
        "   이 섹션 안에서 일반인이 이해할 수 있는 말로:\n"
        "     - 핵심 결론 (사용자 사례에서 어느 쪽이 어떻게 될 가능성이 높은지)\n"
        "     - 그 결론의 근거를 보여주는 판례 1~2건의 이야기 (스토리텔링)\n"
        "     - 판단 정리 문단은 `정리하면, 지금 자료로는 ___ 쪽으로 보는 게 가장 자연스럽습니다. 가장 큰 이유는 ___입니다.`처럼 쉬운 존댓말 한 문단.\n"
        "     - 모를 수도 있는 핵심 법률 용어 2~4개는 이 섹션의 맨 아래에 `**실제 용어**: 풀이` 형식 (별표 둘로 용어만 굵게) 1줄씩. 실제 화면에서 굵게 보이도록 여는 `**`와 닫는 `**`를 반드시 모두 유지한다.\n"
        "2. 그 다음 빈 줄 + `---` + 빈 줄 + `## 상세 분석` 헤더 한 줄.\n"
        "3. 그 아래 `## 종합 판단` 섹션을 두고 단정형으로 우세한 방향을 적은 뒤, 각 claim_axis 별 ### 소제목으로 정밀 분석.\n"
        "4. 그 다음 `## 유리하게 만들 요소`, `## 불리하게 만들 요소` 섹션 (실무적 bullet).\n"
        "5. 마지막은 정확히 `## 참고 판례 목록` 한 줄 + 그 아래에 4분류 H3 (`### 매우 유사한 판례`, `### 유사한 판례`, `### 이용할 만한 판례`, `### 기타`) bullet 나열. 분류는 [참고 판례 위계] 그대로.\n\n"
        "[claim 사용 규칙]\n"
        "- 아래 [claim ledger] 안에서 신뢰할 만한 것만 골라 본문에 인용한다. 모두 쓸 필요 없음.\n"
        "- 본문에서 판례를 인용할 때는 다음 토큰을 우선적으로 사용한다 — 사건번호를 직접 적는 대신 토큰만 적으면 시스템이 정확한 인용 + 인용문 + 하이퍼링크로 치환한다.\n"
        "  - `[N]` = N번 claim 대표 판례 인용 (사건번호만 표시됨)\n"
        "  - `[N-S1]` = N번 claim의 지지 인용 1번 (사건번호 + 인용문 자동 삽입)\n"
        "  - `[N-O1]` = N번 claim의 반대 인용 1번\n"
        "- 만약 토큰을 쓰기 애매한 위치라면 사건번호를 직접 적어도 된다 — 단 반드시 [claim ledger] 안에 있는 사건번호여야 한다 (없는 사건번호를 만들지 말 것).\n"
        "- ledger 밖의 사실/판례/법령/숫자는 만들지 말 것. 모르는 건 적지 마라.\n"
        "- `CLAIM-NNN` 같은 내부 ID, 내부 순번, exact 지지 판례 수는 본문에 노출하지 말 것. 토큰 `[N]` 만 사용.\n"
        "- support quote가 claim_text를 주체·객체·행위태양·법리·결론 면에서 직접 지지하지 않으면 그 claim/citation을 본문 근거로 쓰지 말 것. LLM/selector가 준 claim이라도 틀렸으면 거부하라.\n"
        "- 특히 `본인이 직접 스스로 증거를 없앤 경우`와 `비서·부하·직원·타인에게 삭제를 지시/교사한 경우`를 절대 같은 근거로 취급하지 말 것. 후자는 교사 위험 근거 또는 구별 사례로만 쓴다.\n\n"
        "[판례 인용문 포맷 — 가독성 규칙]\n"
        "- 판례 본문 인용문(`\"...\"` 큰따옴표로 감싼 직접 인용)은 절대 본문 단락 안에 끼워넣지 말 것.\n"
        "- 직접 인용은 항상 별도의 줄에 ` > ` (마크다운 blockquote) 로 분리해 적어라. 직전 판례 표시와 인용문을 같은 문장 안에 섞지 말 것.\n"
        "  잘못된 예: `… 의무가 있습니다 (서울지법 1992. ... 판결) \"8m, 경사도 4°...\".`\n"
        "  올바른 예:\n"
        "    `… 의무가 있습니다 [N-S1].`\n"
        "    `(빈 줄)`\n"
        "    `> 8m, 경사도 4°...` (이 줄은 토큰 [N-S1] 가 직접 치환되거나, 본문 다음 단락에 따로 인용)\n"
        "- 인용문이 길면 한 blockquote 안에서 두세 줄로 줄바꿈해도 좋다.\n"
        "- 사건번호를 직접 쓸 때는 절대로 `**(사건명...)**` 처럼 별표로 감싸지 말 것 (`)))` 같은 깨짐 발생).\n"
        "  사건번호는 별표 없이 평문으로 (예: `… 의무가 있습니다 (서울지법 1992. 01. 04. 선고 95가합60464 판결).`).\n\n"
        "[참고 판례 목록 섹션 규칙]\n"
        "- 마지막 `## 참고 판례 목록` 섹션 안에서는 토큰 대신 `[참고 판례 위계]` 의 한 줄 표기 (citation + 분류 사유) 를 그대로 bullet 으로 옮긴다.\n"
        "- 본문 외 추가 설명은 적지 말고, 4분류 bullet 만.\n\n"
        "[claim ledger]\n"
        f"{claim_block}\n\n"
        "[참고 판례 위계]\n"
        f"{bucket_block}\n"
    )


def build_question_answer_prompt(
    *,
    user_task: str,
    claims: list[dict[str, Any]],
    precedent_buckets: dict[str, list[dict[str, Any]]],
    answer_plan: dict[str, Any] | None = None,
    analysis_mode: str = "",
    precedent_summaries: dict[str, dict[str, str]] | None = None,
) -> str:
    if analysis_mode == "beta7":
        return _build_beta7_writer_prompt(
            user_task=user_task,
            claims=claims,
            precedent_buckets=precedent_buckets,
            precedent_summaries=precedent_summaries,
        )
    answer_plan = answer_plan or {}
    planner_block_parts = []
    if answer_plan.get("likely_outcome"):
        planner_block_parts.append(f"가장 가능성 높은 결론:\n- {answer_plan.get('likely_outcome')}")
    if answer_plan.get("confidence_basis"):
        planner_block_parts.append(
            "결론 근거:\n" + "\n".join(f"- {item}" for item in answer_plan.get("confidence_basis") or [])
        )
    if answer_plan.get("helpful_facts"):
        planner_block_parts.append(
            "유리하게 만들 요소:\n" + "\n".join(f"- {item}" for item in answer_plan.get("helpful_facts") or [])
        )
    if answer_plan.get("harmful_facts"):
        planner_block_parts.append(
            "불리하게 만들 요소:\n" + "\n".join(f"- {item}" for item in answer_plan.get("harmful_facts") or [])
        )
    if answer_plan.get("claim_groups"):
        planner_block_parts.append(
            "주장 묶음:\n" + _render_question_claim_groups(answer_plan.get("claim_groups") or [], claims)
        )
    planner_block = "\n\n[사전 판단]\n" + "\n\n".join(planner_block_parts) if planner_block_parts else ""
    # 빠른 분석(fast)도 최상단 `## 어렵지 않아요` 1층을 포함해 일반인용 정리
    # 부분이 항상 답변 맨 위에 붙도록 한다. 사용자 요구.
    is_dual_layer = analysis_mode in {"fast", "beta4", "beta5", "beta6", "beta8"}
    dual_layer_block = (
        # Story-led laypeople intro + jurist-grade legal analysis. The two
        # layers must satisfy two distinct readers (걱정 많은 일반인 + 법조인)
        # without watering either down. Adapted from the 히트썬더 가이드메이커
        # explanation_creator pattern (interest-grabbing 비유 → 핵심 정의 →
        # 쉬운 결론 → 정밀한 분석).
        "\n\n[베타 본문 이중 구성 지침 (이 지침은 다른 모든 본문 지침보다 우선한다)]\n"
        "이 답변의 본문은 반드시 두 층(layer)으로 구성한다. 각 층은 분량/말투/대상 독자가 명확히 구별된다.\n"
        "전체 헤더 순서는 정확히: `## 어렵지 않아요` → (빈 줄, `---`, 빈 줄) → `## 상세 분석` → `## 종합 판단` → 각 `### <claim_axis>` → `## 유리하게 만들 요소` → `## 불리하게 만들 요소` → `참고 판례 목록`.\n"
        "두 헤더(`## 어렵지 않아요`, `## 상세 분석`)는 본문에 정확히 한 번씩 등장해야 한다.\n"
        "\n"
        "[1층: 일반인을 위한 쉬운 설명과 결론] (`## 어렵지 않아요` 아래)\n"
        "- 변호사가 아닌 일반 시민이 카페에서 친구에게 들려주듯 풀어 말한다. 어려운 조문 번호 같은 법률 인용은 본문 흐름에 노출하지 말 것.\n"
        "- 다만 스토리텔링으로 푸는 판례 1건과 결정적 비교 판례 1~2건은 ledger 토큰을 사용해 본문에 자연스럽게 1~2회 끼워넣어 신뢰성을 높일 것. 법원명·선고일은 시스템 치환값에 맡기고 직접 만들지 말 것. 익명 LBOX 행은 인용을 만들지 말 것.\n"
        "- 첫 문단은 ledger의 selected claim 중 가장 사실관계가 가까운 판례 1건의 이야기를 스토리텔링으로 풀어라. 누가 무엇을 했고 → 분쟁이 어떻게 커졌고 → 법원이 어떤 이유로 어떻게 판단했는지를, 한 사람의 인생 흐름처럼 이어 적고 그 판례의 사건번호를 자연스럽게 노출한다. 사실은 ledger/section packet 안의 내용만 사용한다.\n"
        "- 두 번째 문단은 그 판례의 결론이 지금 질문자의 상황에서 어떻게 닿는지를 친근하게 비교해 적는다. 닮은 점과 다른 점을 모두 쉬운 말로 짚어라.\n"
        "- 판단 정리 문단은 단정형 한 문단으로 `정리하면, 지금 자료로는 ___ 쪽으로 보는 게 가장 자연스럽습니다. 가장 큰 이유는 ___입니다.`처럼 쉬운 존댓말을 유지한다. 양쪽 가능성 나열로 끝내지 말 것.\n"
        "- 핵심 법률 용어 2~4개는 반드시 `## 어렵지 않아요` 섹션의 맨 아래에 모아서 나열한다. 각 용어 풀이의 형식은 정확히 '실제 용어명만 별표 둘로 감싼 뒤 콜론과 풀이를 적는다'를 따른다. 예시 그대로 쓰지 말고 실제 용어로 치환해 적을 것: `**과실상계**: 사고에 피해자 잘못이 있을 때 그 비율만큼 배상액에서 깎는 것.` 처럼 작성한다. 절대 `**용어**:` 라는 글자 자체를 그대로 적지 말 것 (이는 형식 설명일 뿐, 실제 용어로 치환해야 한다). `__용어__` 밑줄 형식, `=` 기호, 콜론 두 번 (예: `**용어**: 과실상계: ...`) 모두 금지. 각 용어는 한 줄(또는 한 문단)에 하나씩 적는다. 실제 화면에서 굵게 보이도록 여는 `**`와 닫는 `**`를 절대 생략하지 말고, 용어 바깥의 정의 문장은 굵게 하지 않는다.\n"
        "- 1층 전체 분량은 4~6문단을 목표로 한다.\n"
        "\n"
        "[1층과 2층 사이 구분선]\n"
        "- 두 층 사이에는 빈 줄 + `---` + 빈 줄을 두고, 그 다음에 `## 상세 분석` 헤더 한 줄을 단독으로 둔다. 이 헤더는 반드시 한 번만 등장해야 한다.\n"
        "\n"
        "[2층: 법조인을 위한 자세한 분석] (`## 상세 분석` 아래)\n"
        "- 2층은 1층보다 길고 정밀해야 한다. 청구원인/항변 구조, 요건사실, 입증책임, 시효, 재량권 일탈·남용 같은 법리 명칭을 본문에서 직접 사용한다.\n"
        "- 2층 첫 헤더는 `## 상세 분석`이고, 곧바로 `## 종합 판단` 헤더가 이어진다. 그 아래에서 가장 강한 주장 묶음과 그 묶음이 복수 근거로 뒷받침되는지, 우세한 방향과 그 이유를 단정형 첫 문장으로 적는다. exact 판례 수는 쓰지 말고 `복수 판례` 또는 `반복적으로 지지` 정도로만 표현한다.\n"
        "- 그 뒤에는 각 주장 축을 `###`(우물 정 세 개) + 공백 + `<claim_axis>` 소제목으로 다루고, 각 축 아래에 `근거 인용` 소제목을 두어 해당 축의 support_spans 중 최소 1개를 `[N-Sm]` 토큰으로 적는다. 시스템이 citation과 별도 blockquote 인용문으로 치환한다. 절대 citation 뒤에 큰따옴표 인용문을 한 줄에 붙이지 말 것. 절대 `### ### 제목`처럼 `###`을 두 번 적지 말 것.\n"
        "- claim_groups가 있으면 같은 묶음 안의 주장들을 한 흐름으로 묶어 정리하고, 근거 강도가 복수 근거인 묶음은 `복수 판례가 같은 방향을 지지한다`는 취지로 신뢰도 근거를 명시한다. 내부 count 숫자는 쓰지 않는다.\n"
        "- 그 다음 `## 유리하게 만들 요소`, `## 불리하게 만들 요소` 섹션을 두고 사전 판단의 helpful_facts/harmful_facts를 실무적으로 풀어 적는다.\n"
        "- 마지막은 정확히 `## 참고 판례 목록` 헤더(H2, 우물 정 두 개) 한 줄로 시작하고, 그 아래에 `### 매우 유사한 판례`, `### 유사한 판례`, `### 이용할 만한 판례`, `### 기타` 네 H3 분류를 각각 정리한다. 헤더 이름 앞에 `## `이 빠진 평문 `참고 판례 목록`은 실패다.\n"
        "- `## 불리하게 만들 요소` 뒤에는 곧바로 `## 참고 판례 목록`이 와야 한다. 그 사이에 `### 관련 참고 판례`, `### 추가 인용` 같은 임의 헤더를 만들지 말 것.\n"
        "\n"
        "[공통 금지/요구]\n"
        "- 두 층의 결론은 반드시 같은 방향이어야 한다. 1층은 부드럽게, 2층은 엄밀하게 같은 결론에 도달한다.\n"
        "- 1층의 비유/스토리/일상 어휘를 2층에 그대로 복붙하지 말고, 2층은 법률 문장으로 다시 쓴다.\n"
        "- ledger/section packet 밖의 사실/판례/법령/숫자는 어느 층에서도 만들지 말 것.\n"
        "- 답변 첫 줄이 `## 어렵지 않아요`가 아니거나, 본문에 `## 상세 분석`이 빠져 있으면 실패다.\n"
        "- 같은 헤더(예: `## 종합 판단`, `## 유리하게 만들 요소`, `## 불리하게 만들 요소`, `### <claim_axis>`)가 답변 안에 두 번 등장하지 않게 하라. 각 헤더는 정확히 한 번씩이다.\n"
        "- `참고 판례 목록` 다음에는 추가 섹션을 더 만들지 말 것. `참고 판례 목록`이 답변의 맨 끝이다.\n"
    ) if is_dual_layer else ""
    proposition_verification_block = (
        "- 선택형·견해-설명형 문제(예: `〈견해〉`, `〈설명〉`, `선지:`가 있는 입력)는 일반 상담처럼 답하지 말고, 각 선지는 법률명제 묶음으로 보고 검증할 것\n"
        "- 선택형·견해-설명형 문제에서는 각 `가-Ⓐ` 같은 연결을 `직접 지지·관련이나 직접 아님·충돌·근거 없음` 중 하나로 표시한 뒤, 직접 지지 명제들로만 정답 번호를 먼저 적을 것\n"
        "- 선택형·견해-설명형 문제에서 단순히 법리명이 가깝거나 설명이 넓게 관련된 정도는 정답 근거가 아니다. 그런 항목은 `관련이나 직접 아님`으로 제외하라\n"
    ) if analysis_mode == "beta8" else ""
    return (
        "아래 selected claim ledger와 참고 판례 위계를 바탕으로 법률 질문에 대한 실무형 답변을 작성하라.\n"
        "중요:\n"
        "- 질문 모드다. 유리한 내용과 불리한 내용을 모두 빠뜨리지 말고 정리할 것\n"
        + proposition_verification_block
        +
        "- selected claim만 본문 대상으로 사용하고, other 버킷 판례는 본문 논증 대상으로 쓰지 말 것\n"
        "- 같은 주장 축을 지지하는 별개 판례 수가 많을수록 신뢰도가 더 높다는 점은 반영하되, 본문에는 exact count 숫자를 쓰지 말 것\n"
        "- 근거 강도가 복수 근거인 주장은 `복수 판례가 같은 방향을 지지한다`는 취지로 본문에서 명시할 것\n"
        "- claim_groups가 주어지면 같은 그룹 안의 주장들을 한 덩어리의 논리 흐름으로 정리할 것\n"
        "- 예를 들어 `징계시효` 그룹 안에서는 기산점, 도과, 계속적 위반 여부를 따로 흩뜨리지 말고 같이 설명할 것\n"
        "- 질문 행위자·대상·법률요건과 직접 맞지 않는 판례는 본문 결론 근거로 인용하지 말고, 필요한 경우 `구별되는 판례` 또는 `직접 근거 부족`으로만 설명할 것\n"
        "- support_spans의 직접 인용문에 없는 법리·사실·구성요건을 판례가 말한 것처럼 확대하지 말 것\n"
        "- 형사법 쟁점에서는 구성요건의 주체·객체(예: 자기 사건인지 타인의 사건인지, 본인 행위인지 공범/제3자 행위인지)를 바꾸어 적용하지 말 것\n"
        "- 각 claim의 support quote를 직접 읽고, claim_text와 주체·객체·행위태양·법리·결론이 맞지 않으면 그 claim/citation을 본문 결론 근거로 쓰지 말 것. LLM/selector가 준 claim이라도 전혀 상관없거나 방향이 다르면 거부하라.\n"
        "- 특히 `본인이 직접 스스로 증거를 없앤 경우`와 `비서·부하·직원·타인에게 삭제를 지시/교사한 경우`를 절대 같은 근거로 취급하지 말 것. 후자는 교사 위험 근거 또는 구별 사례로만 쓴다.\n"
        "- 선택된 판례가 질문의 핵심 요건을 직접 뒷받침하지 않으면 그 판례를 결론 인용으로 쓰지 말고, `현재 선택된 판례만으로는 단정하기 어렵다`고 적을 것\n"
        "- 본문 첫머리에 `## 종합 판단` 섹션을 두고, 현재 자료상 가장 가능성이 높은 결론을 분명하게 적을 것\n"
        "- `종합 판단`에서는 양쪽 가능성을 나열만 하지 말고 어떤 방향이 더 가능성이 높은지와 그 이유를 말할 것\n"
        "- 반복적으로 뒷받침되는 주장 축은 `여러 판례가 같은 방향을 지지하므로 신뢰도가 높다`는 취지로 평가할 것\n"
        "- 결론을 애매하게 얼버무리지 말고, 현재 자료상 어떤 주장이 가장 강한지 우선순위를 세워 말할 것\n"
        "- `## 종합 판단`의 첫 문장은 `현재 자료상 ... 가능성이 가장 높다` 또는 `현재 자료상 ... 주장이 가장 강하다`처럼 단정형으로 쓸 것\n"
        "- 단순히 양쪽 논리를 병렬 나열하지 말고, 반복적으로 뒷받침되는 주장 축을 기준으로 우세한 방향을 먼저 판단할 것\n"
        "- `## 종합 판단`의 앞 두 문장 안에 가장 강한 주장 묶음, 그 묶음이 복수 근거로 지지되는지, 그래서 왜 그 방향이 우세한지를 반드시 적을 것. exact 판례 수는 쓰지 않는다.\n"
        "- `## 종합 판단`에서 `주장할 수 있다`, `반면`, `다만` 식의 병렬 나열로 끝내지 말고, 현재 기준 가장 우세한 방향을 먼저 확정적으로 적을 것\n"
        "- claim_groups가 있으면 가장 강한 group label을 결론의 주축으로 삼고, 그 아래 하위 주장들이 어떻게 쌓이는지 설명할 것\n"
        "- 같은 그룹 안의 하위 주장들이 모두 같은 방향이면 `이 묶음은 복수 판례가 반복적으로 뒷받침하는 핵심 논리`라는 취지로 적을 것. 내부 claim id나 count 숫자를 본문에 쓰지 말 것\n"
        "- `## 유리하게 만들 요소`와 `## 불리하게 만들 요소` 섹션을 두고, 사전 판단의 helpful_facts/harmful_facts를 자연스럽게 반영할 것\n"
        "- 질문자가 자신에게 유리한 결과를 만들려면 어떤 사실을 입증·정리·확보해야 하는지 실무적으로 적을 것\n"
        "- 질문자에게 불리해질 수 있는 사실이나 행동도 분명하게 적을 것\n"
        "- 질문자가 유리하게 만들려면 어떤 사실을 더 확보·정리해야 하는지도 구체적으로 적을 것\n"
        "- 각 주장 축은 본문에서 `### <claim_axis>` 형식의 소제목으로 정확히 한 번 이상 다룰 것\n"
        "- 각 주장 축 아래에는 `근거 인용` 소제목을 두고, support_spans 중 최소 1개를 `[N-Sm]` 토큰으로 적을 것. 치환 후 직접 인용문은 항상 별도 `>` blockquote 줄이어야 한다\n"
        "- 본문에 들어간 각 주장 축은 최소 1개의 직접 인용을 반드시 포함해야 한다\n"
        "- 질문에 맞는 적절한 섹션 구조를 스스로 정할 것\n"
        "- 예시는 유리한 논리, 불리한 논리, 유리/불리 조건, 주의점, 대응 포인트, 참조 판례 요약 등이지만, 질문과 맞지 않는 섹션 제목은 만들지 말 것\n"
        "- 무엇을 하면 유리해지고 무엇을 하면 불리해지는지 구체적으로 적을 것\n"
        "- 마지막에는 `참고 판례 목록`을 두고 `매우 유사한 판례`, `유사한 판례`, `이용할 만한 판례`, `기타` 네 제목으로 정확히 정리할 것\n"
        "- `기타`는 간단히만 적고, coverage 대상은 매우 유사/유사/이용할 만한 판례뿐이다.\n"
        "- 근거 없는 추측 금지. 아래 selected claim ledger 안에 있는 내용만 사용한다.\n"
        "- 결과물은 평문 또는 마크다운 텍스트로만 출력한다.\n"
        "- **[중요 — 인용 토큰 시스템] 본문에서 판례를 인용할 때는 절대 사건번호/법원명/선고일을 직접 적지 말 것. 대신 ledger에 표시된 `토큰 [N]` 또는 `[N-Sm]` / `[N-Om]` 만을 본문에 적는다. CLAIM-ID, 내부 순번, exact 지지 판례 수는 본문에 절대 쓰지 말 것.**\n"
        "  - `[3]` = 3번 claim의 대표 판례를 본문에 인용한다는 뜻 (사건번호만 보임).\n"
        "  - `[3-S2]` = 3번 claim의 지지 인용 2번 (사건번호 + 인용문 자동 삽입).\n"
        "  - `[5-O1]` = 5번 claim의 반대 인용 1번.\n"
        "  - 예시: `이 사건은 [3-S2]에 따라 ...` 처럼 적으면, 시스템이 자동으로 안전한 citation과 별도 `> 인용문` 줄로 치환한다.\n"
        "  - 토큰만 적으면 백엔드가 안전한 사건번호 표시와 직접 인용문으로 치환한다. 법원명/선고일/사건명을 직접 적지 말 것.\n"
        "  - `[참고 판례 위계]` 의 사건번호는 답변 맨 끝 `## 참고 판례 목록` 섹션 bullet 에서만 나열한다 (이 영역에서는 토큰이 아닌 일반 텍스트 인용을 허용).\n\n"
        f"질문:\n{user_task}\n\n"
        + planner_block
        + dual_layer_block
        + "\n\n"
        "[selected claim ledger]\n"
        + "\n\n".join(_render_question_claim_for_prompt(claim, for_final_writer=True) for claim in claims)
        + "\n\n[참고 판례 위계]\n"
        + _render_question_precedent_buckets(precedent_buckets, precedent_summaries)
    )


def _question_answer_has_meta_leak(text: str) -> bool:
    lowered = text.lower()
    leak_markers = [
        "input: a draft",
        "goal: rewrite",
        "constraints:",
        "selected claim ledger",
        "self-correction",
        "self correction",
        "final check",
        "drafting the final response",
        "let's go",
        "wait, the instruction says",
        "wait, the prompt says",
        "the prompt says",
        "지시문",
        "제공된 `selected claim ledger`",
        "[selected claim ledger]",
        "[참고 판례 위계]",
        "*   `## 종합 판단`",
    ]
    return any(marker in lowered or marker in text for marker in leak_markers)


def _strip_question_answer_meta_prefix(text: str) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    if not _question_answer_has_meta_leak(raw):
        return raw
    matches = list(re.finditer(r"##\s*종합\s*판단", raw))
    if not matches:
        return raw
    start = matches[-1].start()
    stripped = raw[start:].strip()
    stripped = re.sub(r"^\*?\s*(?:let'?s go\.?|이제 작성한다\.?)\s*\*?\s*", "", stripped, flags=re.IGNORECASE).strip()
    return stripped or raw


def _question_answer_missing_required_sections(text: str) -> bool:
    required = [
        "## 종합 판단",
        "## 유리하게 만들 요소",
        "## 불리하게 만들 요소",
        "참고 판례 목록",
        "매우 유사한 판례",
        "유사한 판례",
        "이용할 만한 판례",
    ]
    return any(section not in text for section in required)


def _rewrite_question_answer_citations(text: str, claims: list[dict[str, Any]]) -> str:
    evidence_map: dict[str, str] = {}
    for claim in _hydrate_question_claims(claims):
        citation = _normalize_space(claim.get("citation")) or _format_question_case_citation(
            str(claim.get("case_number") or ""),
            str(claim.get("court") or ""),
            str(claim.get("decision_date") or ""),
            str(claim.get("case_name") or ""),
        )
        for span in claim.get("support_spans") or []:
            evidence_id = _normalize_space(span.get("evidence_id"))
            if evidence_id and citation:
                evidence_map[evidence_id] = citation
    rewritten = text
    for evidence_id, citation in evidence_map.items():
        rewritten = re.sub(
            rf"\[\s*{re.escape(evidence_id)}\s*\]",
            f"**({citation})**",
            rewritten,
        )
        rewritten = re.sub(
            rf"(?<!\S){re.escape(evidence_id)}(?!\S)",
            citation,
            rewritten,
        )
    rewritten = re.sub(r"\*\*\s*\*\*", "", rewritten)
    rewritten = re.sub(r"\n{3,}", "\n\n", rewritten)
    return rewritten.strip()


def _repair_question_answer_output(
    *,
    user_task: str,
    draft_text: str,
    claims: list[dict[str, Any]],
    precedent_buckets: dict[str, list[dict[str, Any]]],
    answer_plan: dict[str, Any] | None,
    model: str,
) -> str:
    repair_prompt = (
        "아래 초안은 메타 설명, 지시문, self-check, 중간 메모가 섞여 있다.\n"
        "사용자에게 바로 보여줄 완성 답변만 다시 작성하라.\n"
        "규칙:\n"
        "- 지시문, 단계 설명, 영어 메모, self-correction, claim_id 나열을 쓰지 말 것\n"
        "- `## 종합 판단`에서 가장 가능성이 높은 결론을 먼저 분명히 적을 것\n"
        "- `## 종합 판단`의 첫 문장은 단정형으로 시작하고, 가장 강한 주장 축과 그 이유를 곧바로 적을 것\n"
        "- `## 종합 판단`의 앞 두 문장 안에 가장 강한 주장 묶음, 복수 근거 여부, 왜 그 방향이 우세한지를 반드시 적을 것. exact 판례 수는 쓰지 말 것\n"
        "- `## 유리하게 만들 요소`와 `## 불리하게 만들 요소` 섹션을 반드시 둘 것\n"
        "- claim_groups가 있으면 같은 묶음 안의 주장들을 함께 정리하고, 서로 다른 주장처럼 흩뿌리지 말 것\n"
        "- 같은 주장 축을 지지하는 별개 판례가 복수이면 그 점을 신뢰도 근거로 자연스럽게 적되, 내부 count 숫자는 쓰지 말 것\n"
        "- support quote가 claim_text를 주체·객체·행위태양·법리·결론 면에서 직접 지지하지 않으면 그 claim/citation을 본문 근거로 쓰지 말 것. LLM/selector가 준 claim이라도 틀렸으면 거부하라\n"
        "- 용어 풀이 줄은 반드시 `**실제 용어명**: 풀이` 형식으로 쓰고, 용어명만 굵게 한다\n"
        "- 각 주장 축은 `### <claim_axis>`로 다루고 `근거 인용` 아래에 최소 1개의 직접 인용을 넣을 것\n"
        "- 인용은 안전한 citation 본문과 별도 `> 직접 인용문` blockquote 줄로 분리한다. 큰따옴표 인용문을 citation 뒤에 붙이지 말 것\n"
        "- 질문자에게 유리하게 만들 요소와 불리하게 만들 요소를 구체적으로 적을 것\n"
        "- 마지막에 `참고 판례 목록`을 두고 `매우 유사한 판례`, `유사한 판례`, `이용할 만한 판례`, `기타`를 구분할 것\n"
        "- `기타`는 간단히만 적을 것\n\n"
        f"[질문]\n{user_task}\n\n"
        f"[사전 판단]\n{json.dumps(answer_plan or {}, ensure_ascii=False, indent=2)}\n\n"
        "[선택된 주장]\n"
        + "\n\n".join(_render_question_claim_for_prompt(claim, for_final_writer=True) for claim in claims)
        + "\n\n[참고 판례 위계]\n"
        + _render_question_precedent_buckets(precedent_buckets)
        + "\n\n[초안]\n"
        + draft_text
    )
    return call_chat(
        [
            {"role": "system", "content": "법률 답변 정리자다. 메타 설명 없이 사용자에게 바로 보여줄 한국어 최종답만 출력하라."},
            {"role": "user", "content": repair_prompt},
        ],
        model=model,
        timeout=600,
    ).strip()


def write_question_answer(
    *,
    user_task: str,
    claims: list[dict[str, Any]],
    precedent_buckets: dict[str, list[dict[str, Any]]],
    answer_plan: dict[str, Any] | None = None,
    model: str,
    analysis_mode: str = "",
    precedent_summaries: dict[str, dict[str, str]] | None = None,
) -> str:
    prompt = build_question_answer_prompt(
        user_task=user_task,
        claims=claims,
        precedent_buckets=precedent_buckets,
        answer_plan=answer_plan,
        analysis_mode=analysis_mode,
        precedent_summaries=precedent_summaries,
    )
    output = call_chat(
        [
            {"role": "system", "content": "법률 질문에 대한 실무형 판례 답변을 작성하라. 지시문, 메모, self-check를 노출하지 말고 한국어 최종답만 출력하라."},
            {"role": "user", "content": prompt},
        ],
        model=model,
        timeout=600,
    ).strip()
    if _question_answer_has_meta_leak(output) or _question_answer_missing_required_sections(output):
        output = _repair_question_answer_output(
            user_task=user_task,
            draft_text=output,
            claims=claims,
            precedent_buckets=precedent_buckets,
            answer_plan=answer_plan,
            model=model,
        )
    output = _strip_question_answer_meta_prefix(output)
    output = _rewrite_question_answer_citations(output, claims)
    return output


def build_question_coverage_patch_prompt(
    *,
    user_task: str,
    claims: list[dict[str, Any]],
    current_answer: str,
    precedent_buckets: dict[str, list[dict[str, Any]]],
    gaps: dict[str, list[str]],
    answer_plan: dict[str, Any] | None = None,
) -> str:
    answer_plan = answer_plan or {}
    planner_block_parts = []
    if answer_plan.get("likely_outcome"):
        planner_block_parts.append(f"가장 가능성 높은 결론:\n- {answer_plan.get('likely_outcome')}")
    if answer_plan.get("confidence_basis"):
        planner_block_parts.append(
            "결론 근거:\n" + "\n".join(f"- {item}" for item in answer_plan.get("confidence_basis") or [])
        )
    if answer_plan.get("helpful_facts"):
        planner_block_parts.append(
            "유리하게 만들 요소:\n" + "\n".join(f"- {item}" for item in answer_plan.get("helpful_facts") or [])
        )
    if answer_plan.get("harmful_facts"):
        planner_block_parts.append(
            "불리하게 만들 요소:\n" + "\n".join(f"- {item}" for item in answer_plan.get("harmful_facts") or [])
        )
    if answer_plan.get("claim_groups"):
        planner_block_parts.append(
            "주장 묶음:\n" + _render_question_claim_groups(answer_plan.get("claim_groups") or [], claims)
        )
    planner_block = "\n\n[사전 판단]\n" + "\n\n".join(planner_block_parts) if planner_block_parts else ""
    missing_axes = set(gaps.get("missing_axes") or []) | set(gaps.get("missing_citations") or [])
    missing_claims = [
        claim for claim in claims if _normalize_space(claim.get("claim_axis")) in missing_axes
    ]
    missing_precedent_rows: list[dict[str, Any]] = []
    for case_number in gaps.get("missing_precedents") or []:
        found = _find_required_precedent_row(precedent_buckets, case_number)
        if found:
            _bucket, row = found
            missing_precedent_rows.append(row)
    missing_payload_parts: list[str] = []
    if missing_claims:
        missing_payload_parts.append(
            "[본문에 패치해야 할 주장]\n"
            + "\n\n".join(_render_question_claim_for_prompt(claim, for_final_writer=True) for claim in missing_claims)
        )
    if missing_precedent_rows:
        missing_payload_parts.append(
            "[본문에 패치해야 할 판례]\n"
            + "\n".join(
                "- "
                + _format_question_case_citation(
                    str(row.get("case_number") or ""),
                    str(row.get("court") or ""),
                    str(row.get("decision_date") or ""),
                    str(row.get("case_name") or ""),
                )
                + f" | 관련 주장: {', '.join(_coerce_string_list(row.get('supported_claim_axes')))}"
                + f" | 사유: {_normalize_space(row.get('why'))}"
                for row in missing_precedent_rows
            )
        )
    missing_payload = "\n\n".join(missing_payload_parts) or "(없음)"
    return (
        "아래는 이미 작성된 법률 질문 답변과 selected claim ledger, 참고 판례 위계다.\n"
        "목표는 선택된 주장 축이 최종 답변 본문에서 명시적으로 하나도 누락되지 않게 하는 것이다.\n"
        "PATCH MODE다. Hit-Thunder guide maker처럼 전체 답변을 다시 쓰지 말고, 누락된 분석결과를 어디에 넣을지 패치 지시만 출력하라.\n"
        "중요:\n"
        "- 절대 완성본 전체를 다시 출력하지 말 것\n"
        "- 절대 현재 답변을 요약하거나 재작성하지 말 것\n"
        "- 누락된 claim/판례 분석결과만 보고, 기존 본문에 넣을 짧은 local edit만 만들 것\n"
        "- 출력은 반드시 `<patches>...</patches>` 안의 `<patch>` 블록들만 낼 것\n"
        "- `<patch>`에는 `<section>`, `<op>`, `<before>`, `<after>`, `<content>`만 넣을 것\n"
        "- `<op>`는 `append`, `insert_after`, `insert_before`, `insert_between` 중 하나다\n"
        "- `<section>`에는 기존 답변의 마크다운 섹션 제목을 적을 것. 모르면 빈 값으로 두면 참고 판례 목록 앞 본문에 적용된다\n"
        "- `<before>`와 `<after>`는 현재 답변에서 짧게 그대로 찾을 수 있는 anchor 문구를 적을 것. append면 비워도 된다\n"
        "- `<content>`에는 실제로 끼워 넣을 1~3문단 markdown만 적을 것\n"
        "- 이미 들어간 내용을 장황하게 반복하지 말 것\n"
        "- 각 claim_axis가 본문에서 적어도 한 번은 명시적으로 드러나도록 보완할 것\n"
        "- 각 claim_axis는 `### <claim_axis>` 형식의 소제목으로 정확히 남겨둘 것\n"
        "- 각 claim_axis 아래에는 `근거 인용` 소제목을 두고, support_spans 중 최소 1개를 `[N-Sm]` 토큰으로 반드시 넣을 것. 치환 후 직접 인용문은 별도 `>` blockquote 줄이어야 한다\n"
        "- very_similar/similar/usable에 들어간 판례번호는 `참고 판례 목록`뿐 아니라 본문 논증 안에도 반드시 자연스럽게 들어가야 한다\n"
        "- other 버킷 판례는 coverage 대상이 아니다\n"
        "- 절대 `누락 보정`, `보강`, `coverage`, `패치` 같은 작업명 섹션을 만들지 말 것\n"
        "- 보완 내용은 기존 주장 섹션 안에 자연스럽게 흡수하거나, 필요한 경우 기존 섹션을 다시 정돈할 것\n"
        "- 새 주장을 만들지 말고, 누락된 claim_axis와 판례만 기존 논리 흐름에 짧게 반영할 것\n"
        "- claim ledger에 없는 새 사실을 만들지 말 것\n"
        "- 패치 후 검증은 시스템이 다시 수행하므로 스스로 전체 재검증 문구를 쓰지 말 것\n\n"
        "출력 형식:\n"
        "<patches>\n"
        "<patch>\n"
        "<section>기존 섹션 제목</section>\n"
        "<op>append</op>\n"
        "<before></before>\n"
        "<after></after>\n"
        "<content>여기에 넣을 짧은 markdown 문단</content>\n"
        "</patch>\n"
        "</patches>\n\n"
        f"질문:\n{user_task}\n\n"
        + planner_block
        + "\n\n"
        "[현재 답변]\n"
        f"{current_answer}\n\n"
        "[패치할 누락 분석결과]\n"
        + missing_payload
    )


def _question_coverage_has_gaps(gaps: dict[str, list[str]]) -> bool:
    return bool(gaps.get("missing_axes") or gaps.get("missing_citations") or gaps.get("missing_precedents"))


def _subset_gap_values(raw_values: Any, allowed_values: list[str]) -> list[str]:
    if not isinstance(raw_values, list):
        return []
    by_normalized = {_normalize_for_coverage(value): value for value in allowed_values}
    output: list[str] = []
    for raw_value in raw_values:
        normalized = _normalize_for_coverage(str(raw_value or ""))
        if normalized in by_normalized:
            value = by_normalized[normalized]
            if value not in output:
                output.append(value)
    return output


def _parse_question_coverage_verifier_gaps(
    raw: str,
    candidate_gaps: dict[str, list[str]],
) -> dict[str, list[str]] | None:
    try:
        parsed = json.loads(_extract_json_block(raw))
    except Exception:
        return None
    if not isinstance(parsed, dict):
        return None
    return {
        "missing_axes": _subset_gap_values(parsed.get("missing_axes"), candidate_gaps.get("missing_axes") or []),
        "missing_citations": _subset_gap_values(parsed.get("missing_citations"), candidate_gaps.get("missing_citations") or []),
        "missing_precedents": _subset_gap_values(parsed.get("missing_precedents"), candidate_gaps.get("missing_precedents") or []),
    }


def build_question_coverage_verifier_prompt(
    *,
    user_task: str,
    claims: list[dict[str, Any]],
    current_answer: str,
    precedent_buckets: dict[str, list[dict[str, Any]]],
    candidate_gaps: dict[str, list[str]],
) -> str:
    missing_axes = set(candidate_gaps.get("missing_axes") or []) | set(candidate_gaps.get("missing_citations") or [])
    missing_claims = [
        claim for claim in claims if _normalize_space(claim.get("claim_axis")) in missing_axes
    ]
    missing_rows: list[str] = []
    for case_number in candidate_gaps.get("missing_precedents") or []:
        found = _find_required_precedent_row(precedent_buckets, case_number)
        if not found:
            continue
        bucket, row = found
        missing_rows.append(
            "- "
            + _format_question_case_citation(
                str(row.get("case_number") or ""),
                str(row.get("court") or ""),
                str(row.get("decision_date") or ""),
                str(row.get("case_name") or ""),
            )
            + f" | 분류: {bucket}"
            + f" | 관련 주장: {', '.join(_coerce_string_list(row.get('supported_claim_axes')))}"
            + f" | 사유: {_normalize_space(row.get('why'))}"
        )
    claim_block = "\n\n".join(_render_question_claim_for_prompt(claim, for_final_writer=True) for claim in missing_claims) or "(없음)"
    precedent_block = "\n".join(missing_rows) or "(없음)"
    return (
        "COVERAGE VERIFIER다. 아래 현재 답변 본문과 후보 누락 목록을 비교해서, 아직 실제로 빠진 항목만 골라라.\n"
        "기계적 문자열 일치가 아니라 의미상 반영 여부를 판단한다.\n"
        "예를 들어 판례번호가 정확히 같은 문자열로 없더라도, 같은 법원/선고일/사건명/직접 인용문이 본문에 들어가 그 판례가 실질적으로 쓰였으면 누락으로 보지 않는다.\n"
        "반대로 `참고 판례 목록`에만 있고 본문 논증에는 없으면 누락이다.\n"
        "확실히 반영됐다고 판단할 수 없으면 누락으로 남겨라.\n"
        "other 버킷은 coverage 대상이 아니므로 판단하지 않는다.\n"
        "출력은 JSON 객체 하나만 반환한다. 후보 목록에 없는 새 값을 만들지 마라.\n"
        "{\n"
        '  "missing_axes": [],\n'
        '  "missing_citations": [],\n'
        '  "missing_precedents": []\n'
        "}\n\n"
        f"질문:\n{user_task}\n\n"
        "[현재 답변]\n"
        f"{current_answer}\n\n"
        "[후보 누락 claim]\n"
        f"{claim_block}\n\n"
        "[후보 누락 판례]\n"
        f"{precedent_block}\n\n"
        "[기계 후보 목록]\n"
        f"{json.dumps(candidate_gaps, ensure_ascii=False, indent=2)}"
    )


def filter_question_coverage_gaps_with_llm(
    *,
    user_task: str,
    claims: list[dict[str, Any]],
    current_answer: str,
    precedent_buckets: dict[str, list[dict[str, Any]]],
    candidate_gaps: dict[str, list[str]],
    model: str,
) -> dict[str, list[str]]:
    if not _question_coverage_has_gaps(candidate_gaps):
        return candidate_gaps
    prompt = build_question_coverage_verifier_prompt(
        user_task=user_task,
        claims=claims,
        current_answer=current_answer,
        precedent_buckets=precedent_buckets,
        candidate_gaps=candidate_gaps,
    )
    try:
        raw = call_chat(
            [
                {
                    "role": "system",
                    "content": "법률 답변 coverage verifier다. 후보 누락 중 아직 실제로 빠진 항목만 JSON으로 반환한다.",
                },
                {"role": "user", "content": prompt},
            ],
            model=model,
            timeout=120,
        ).strip()
    except Exception:
        return candidate_gaps
    verified = _parse_question_coverage_verifier_gaps(raw, candidate_gaps)
    return verified if verified is not None else candidate_gaps


def _build_question_coverage_supplement(
    *,
    claims: list[dict[str, Any]],
    precedent_buckets: dict[str, list[dict[str, Any]]],
    gaps: dict[str, list[str]],
) -> str:
    claim_by_axis = {
        _normalize_space(claim.get("claim_axis")): claim
        for claim in _hydrate_question_claims(claims)
        if _normalize_space(claim.get("claim_axis"))
    }
    sections: list[str] = []
    seen_axes: set[str] = set()
    for axis in [*(gaps.get("missing_axes") or []), *(gaps.get("missing_citations") or [])]:
        normalized_axis = _normalize_space(axis)
        if not normalized_axis or normalized_axis in seen_axes:
            continue
        seen_axes.add(normalized_axis)
        claim = claim_by_axis.get(normalized_axis)
        if not claim:
            continue
        lines = [f"### {normalized_axis}"]
        claim_text = _normalize_space(claim.get("claim_text") or claim.get("context_summary"))
        if claim_text:
            lines.append(claim_text)
        support_markers = _claim_support_markers(claim)
        citation, quote, evidence_id = support_markers[0] if support_markers else ("", "", "")
        if quote:
            lines.append("근거 인용")
            if citation:
                lines.append(f"**({citation})** \"{quote}\"")
            elif evidence_id:
                lines.append(f"[{evidence_id}] \"{quote}\"")
            else:
                lines.append(f"\"{quote}\"")
        sections.append("\n\n".join(lines))
    required_rows: dict[str, dict[str, Any]] = {}
    for key in ("very_similar", "similar", "usable"):
        for row in precedent_buckets.get(key) or []:
            case_number = _normalize_space(row.get("case_number"))
            if case_number and case_number not in required_rows:
                required_rows[case_number] = row
    precedent_lines: list[str] = []
    for case_number in gaps.get("missing_precedents") or []:
        row = required_rows.get(_normalize_space(case_number), {})
        citation = _format_question_case_citation(
            str(row.get("case_number") or case_number),
            str(row.get("court") or ""),
            str(row.get("decision_date") or ""),
            str(row.get("case_name") or ""),
        )
        axes = ", ".join(row.get("supported_claim_axes") or [])
        why = _normalize_space(row.get("why"))
        suffix = " ".join(part for part in [f"관련 주장: {axes}" if axes else "", why] if part).strip()
        precedent_lines.append(f"- {citation or case_number}{(' - ' + suffix) if suffix else ''}")
    if precedent_lines:
        sections.append("## 참고 판례 목록\n\n" + "\n".join(precedent_lines))
    if not sections:
        return ""
    return "\n\n".join(sections)


def apply_question_coverage_patch(
    *,
    user_task: str,
    claims: list[dict[str, Any]],
    current_answer: str,
    precedent_buckets: dict[str, list[dict[str, Any]]],
    answer_plan: dict[str, Any] | None,
    model: str,
    max_iterations: int = 4,
) -> str:
    output = current_answer.strip()
    coverage_claims = _hydrate_question_claims(claims)
    previous_gap_signature = ""
    iteration = 0
    while True:
        iteration += 1
        # 무한 retry 방어. Gemini 429 cool-down + 비어있는 패치 조합으로
        # 빠져나오지 못하던 응답합성 무한로딩 버그의 원인. 4회 반복 후
        # 강제 종료해서 사용자에게 부분적이라도 결과를 돌려준다.
        if iteration > max_iterations:
            print(f"[coverage_patch] max_iterations({max_iterations}) reached, returning current output", flush=True)
            return output
        gaps = find_question_coverage_gaps(output, coverage_claims, precedent_buckets=precedent_buckets)
        gaps = filter_question_coverage_gaps_with_llm(
            user_task=user_task,
            claims=coverage_claims,
            current_answer=output,
            precedent_buckets=precedent_buckets,
            candidate_gaps=gaps,
            model=model,
        )
        gap_signature = json.dumps(gaps, ensure_ascii=False, sort_keys=True)
        if not gaps["missing_axes"] and not gaps["missing_citations"] and not gaps["missing_precedents"]:
            return output

        deterministic_patch = _apply_question_coverage_fallback(
            answer_text=output,
            claims=coverage_claims,
            precedent_buckets=precedent_buckets,
            gaps=gaps,
        )
        if deterministic_patch != output:
            output = deterministic_patch
            previous_gap_signature = ""
            continue

        missing_block = []
        if gaps["missing_axes"]:
            missing_block.append("누락된 claim_axis:\n" + "\n".join(f"- {item}" for item in gaps["missing_axes"]))
        if gaps["missing_citations"]:
            missing_block.append("인용이 없는 claim_axis:\n" + "\n".join(f"- {item}" for item in gaps["missing_citations"]))
        if gaps["missing_precedents"]:
            missing_block.append("본문 논증에서 빠진 판례번호:\n" + "\n".join(f"- {item}" for item in gaps["missing_precedents"]))
        prompt = build_question_coverage_patch_prompt(
            user_task=user_task,
            claims=coverage_claims,
            current_answer=output,
            precedent_buckets=precedent_buckets,
            answer_plan=answer_plan,
            gaps=gaps,
        )
        patch_prompt = prompt + "\n\n[누락 진단]\n" + "\n\n".join(missing_block)
        raw_patch = call_chat(
            [
                {"role": "system", "content": "법률 질문 답변의 claim coverage patcher다. 전체 답변 재작성은 금지다. <patches> 안의 local edit 패치 블록만 출력하라."},
                {"role": "user", "content": patch_prompt},
            ],
            model=model,
            timeout=120,
        ).strip()
        patches = _parse_question_coverage_patch_blocks(raw_patch)
        if not patches:
            return output
        patched, applied_count = _apply_question_coverage_patch_blocks(output, patches)
        if applied_count <= 0:
            return output
        patched = _rewrite_question_answer_citations(patched, coverage_claims)
        if patched == output or gap_signature == previous_gap_signature:
            integrated = _apply_question_coverage_fallback(
                answer_text=patched,
                claims=coverage_claims,
                precedent_buckets=precedent_buckets,
                gaps=gaps,
            )
            if integrated == patched:
                return patched
            output = integrated
            previous_gap_signature = ""
            continue
        previous_gap_signature = gap_signature
        output = patched


def write_question_answer_plan(
    *,
    user_task: str,
    claims: list[dict[str, Any]],
    catalog: list[dict[str, Any]],
    model: str,
    analysis_mode: str = "",
) -> dict[str, Any]:
    hydrated_claims = _hydrate_question_claims(claims)
    prompt = build_question_answer_plan_prompt(
        user_task=user_task,
        claims=hydrated_claims,
        catalog=catalog,
        analysis_mode=analysis_mode,
    )
    raw = call_chat(
        [
            {"role": "system", "content": "법률 판례 planner다. JSON만 출력하라."},
            {"role": "user", "content": prompt},
        ],
        model=model,
        timeout=600,
    ).strip()
    plan = _extract_question_answer_plan(raw=raw, claims=hydrated_claims, catalog=catalog)
    fallback = _fallback_question_answer_plan(hydrated_claims, catalog)
    for key in ("likely_outcome",):
        if not _normalize_space(plan.get(key)):
            plan[key] = fallback.get(key)
    for key in ("confidence_basis", "helpful_facts", "harmful_facts", "body_claim_ids"):
        if not plan.get(key):
            plan[key] = fallback.get(key) or []
    if not plan.get("claim_groups"):
        plan["claim_groups"] = fallback.get("claim_groups") or []
    if not any((plan.get("precedent_buckets") or {}).get(bucket) for bucket in ("very_similar", "similar", "usable")):
        plan["precedent_buckets"] = fallback.get("precedent_buckets") or plan.get("precedent_buckets") or {}
    plan["raw"] = raw
    return plan


def select_top_structured_precedent_records(
    structured_dirs: list[Path],
    *,
    user_task: str,
    model: str,
    keyword_count: int,
    top_k: int,
) -> tuple[list[FileRecord], dict[str, Any]]:
    keywords = generate_search_keywords(user_task, model=model, keyword_count=keyword_count)
    rows: list[dict[str, Any]] = []
    for structured_dir in structured_dirs:
        rows.extend(iter_structured_precedent_rows(structured_dir))
    selected_rows = select_top_structured_precedent_rows(rows, keywords=keywords, top_k=top_k)
    records = [structured_row_to_file_record(row) for row in selected_rows]
    selection_meta = {
        "keywords": keywords,
        "selected_count": len(records),
        "selected_rows": [
            {
                "case_number": row.get("case_number"),
                "case_name": row.get("case_name"),
                "court": row.get("court"),
                "decision_date": row.get("decision_date"),
                "matched_keywords": row.get("_matched_keywords") or [],
                "keyword_hit_count": row.get("_keyword_hit_count") or 0,
                "keyword_weighted_score": row.get("_keyword_weighted_score") or 0,
                "source_path": row.get("source_path"),
            }
            for row in selected_rows
        ],
    }
    return records, selection_meta


def _coerce_selected_precedent_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        items = None
        for key in ("selected_rows", "selected_files", "records", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                items = value
                break
        if items is None:
            raise ValueError("selected precedent JSON must be a list or contain a list under selected_rows/selected_files/records/items")
    else:
        raise ValueError("selected precedent JSON must be a list or object")
    out: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"selected precedent item at index {index} is not an object")
        out.append(item)
    return out


def _file_record_from_payload(payload: dict[str, Any]) -> FileRecord:
    return FileRecord(
        file_id=str(payload.get("file_id") or "").strip(),
        relative_path=str(payload.get("relative_path") or "").strip(),
        absolute_path=str(payload.get("absolute_path") or "").strip(),
        document_title=str(payload.get("document_title") or "").strip(),
        doc_type=str(payload.get("doc_type") or "").strip() or "txt",
        source_group=str(payload.get("source_group") or "").strip() or "structured_precedent",
        token_count=int(payload.get("token_count") or 0),
        anchor_text=str(payload.get("anchor_text") or ""),
        extracted_text=str(payload.get("extracted_text") or ""),
        candidate_boundaries=list(payload.get("candidate_boundaries") or []),
        is_direct_evidence=bool(payload.get("is_direct_evidence")),
        is_format_sample=bool(payload.get("is_format_sample")),
        content_hash=str(payload.get("content_hash") or ""),
        duplicate_paths=[str(value) for value in (payload.get("duplicate_paths") or []) if str(value).strip()],
        case_number=str(payload.get("case_number") or "").strip(),
        court=str(payload.get("court") or "").strip(),
        decision_date=str(payload.get("decision_date") or "").strip(),
        case_name=str(payload.get("case_name") or "").strip(),
    )


def load_selected_question_records(path: Path) -> list[FileRecord]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = _coerce_selected_precedent_items(payload)
    records: list[FileRecord] = []
    for item in items:
        if {"file_id", "relative_path", "absolute_path", "document_title", "extracted_text"}.issubset(item):
            record = _file_record_from_payload(item)
        else:
            record = structured_row_to_file_record(item)
        # LBOX 오픈 데이터셋은 사건번호/당사자명을 통째로 익명화한 채 본문만
        # 공개. ingestor 가 본문 첫 인용 패턴을 case_number / decision_date /
        # court 로 잘못 stamp 한 결과가 거의 100% (84,768/84,788). 이런 행은
        # 어떤 메타도 신뢰할 수 없으니 빈 값으로 클리어해서 downstream LLM
        # 이 wrong citation 을 못 emit 하도록 차단한다.
        rel = (record.relative_path or "").lower()
        if "02_lbox_open" in rel or "/lbox" in rel or rel.startswith("lbox/"):
            record.case_number = ""
            record.court = ""
            record.decision_date = ""
            record.case_name = "LBOX 익명화"
        records.append(record)
    return records


def _run_question_variant_from_selected_records(
    *,
    name: str,
    selected_records: list[FileRecord],
    selection_meta: dict[str, Any],
    selection_reasoning_text: str,
    user_task: str,
    out_dir: Path,
    analyze_model: str,
    draft_model: str,
    question_chunk_tokens: int,
    analyze_workers: int,
    chunk_build_workers: int,
    skip_coverage_patch: bool = False,
    analysis_mode: str = "",
) -> dict[str, Any]:
    variant_dir = _variant_dir(out_dir, name)
    runtime_dir = _variant_dir(out_dir, "_runtime")
    runtime_status_path = runtime_dir / "status.json"
    shared_cache_dir = out_dir / "_shared_cache" / "chunk_analysis"

    write_runtime_status(
        runtime_status_path,
        {
            "phase": "variant",
            "variant": name,
            "state": "starting",
            "selected_file_count": len(selected_records),
        },
    )
    _write_json(variant_dir / "selected_files.json", [dataclasses.asdict(record) for record in selected_records])
    _write_json(variant_dir / "selection_meta.json", selection_meta)
    (variant_dir / "selection_reasoning.txt").write_text(selection_reasoning_text.strip(), encoding="utf-8")

    chunks = build_question_chunks_for_records(
        selected_records,
        max_tokens=question_chunk_tokens,
        workers=chunk_build_workers,
        status_path=runtime_status_path,
        variant_name=name,
    )
    chunk_outputs = analyze_chunks_cached(
        chunks,
        user_task=user_task,
        model=analyze_model,
        cache_dir=shared_cache_dir,
        analysis_mode="question",
        workers=analyze_workers,
        status_path=runtime_status_path,
        variant_name=name,
    )
    jsonl_path = variant_dir / "chunk_outputs.jsonl"
    all_claims: list[dict[str, Any]] = []
    with jsonl_path.open("w", encoding="utf-8") as fp:
        for result in chunk_outputs:
            fp.write(json.dumps(result, ensure_ascii=False) + "\n")
            all_claims.extend(result.get("claims_proposed") or [])

    merged_claims = merge_claim_ledgers(all_claims, analysis_mode="question")
    # Evidence gate (span-level): keep matched support_spans, batch-retry the
    # unmatched ones, and drop only the spans (not the whole claim) that still
    # fail. A claim is removed only if it ends up with zero verified spans.
    # This prevents hyperlinks/highlights from pointing at fabricated text
    # while preserving every quote the LLM paraphrased by a few characters.
    _precedent_text_by_file_id = {r.file_id: r.extracted_text for r in selected_records}
    # Force-match every span quote to the closest real sentence in the
    # precedent BEFORE the gate so downstream LLMs (planner + final writer)
    # only ever see verbatim citations. Tiny char/whitespace differences from
    # the chunk analyzer no longer slip through as hallucinations.
    _force_stats = _force_match_claim_spans(merged_claims, _precedent_text_by_file_id)
    print(f"[force_match_claim_spans question] {_force_stats}", flush=True)
    merged_claims, _gate_stats = gate_and_retry_claim_spans(
        merged_claims, _precedent_text_by_file_id, model=analyze_model
    )
    print(f"[gate_and_retry_claim_spans question] {_gate_stats}", flush=True)
    merged_claims = _assign_question_claim_ids(merged_claims)
    claim_ledger_path = variant_dir / "claim_ledger.json"
    _write_json(claim_ledger_path, merged_claims)

    # Claim-derived summaries are already produced by the chunk analyzer.
    # We write them out to `precedent_summaries.json` so the drawer can
    # display them. Bucket-only precedents (no claim) are intentionally NOT
    # summarized here: the writer prompt forbids citing them in body, and
    # backend `_strip_body_citations_outside_claim_ledger` enforces this.
    # The user only ever clicks claim-backed precedents.
    summaries_path = variant_dir / "precedent_summaries.json"
    summaries: dict[str, dict[str, str]] = summarize_selected_precedents_parallel(
        records=selected_records,
        existing_claims=merged_claims,
        user_task=user_task,
        model=analyze_model,
        workers=analyze_workers,
        cache_dir=shared_cache_dir,
        status_path=runtime_status_path,
        variant_name=name,
        only_file_ids=set(),  # claim-derived only — no LLM calls
    )
    _write_json(summaries_path, summaries)

    precedent_catalog = _build_question_precedent_catalog(merged_claims)
    answer_plan = write_question_answer_plan(
        user_task=user_task,
        claims=merged_claims,
        catalog=precedent_catalog,
        model=analyze_model,
        analysis_mode=analysis_mode,
    )
    _write_json(variant_dir / "answer_plan.json", answer_plan)

    selected_claim_ids = list(answer_plan.get("body_claim_ids") or [])
    selected_claims = [claim for claim in merged_claims if claim.get("claim_id") in selected_claim_ids]
    if not selected_claims:
        selected_claims = merged_claims[: min(12, len(merged_claims))]
    precedent_buckets = answer_plan.get("precedent_buckets") or {
        "very_similar": [],
        "similar": [],
        "usable": [],
        "other": [],
    }

    write_runtime_status(
        runtime_status_path,
        {
            "phase": "draft",
            "variant": name,
            "state": "writing_final_draft",
            "selected_file_count": len(selected_records),
            "chunk_count": len(chunks),
            "completed_chunks": len(chunks),
            "claim_count": len(merged_claims),
        },
    )
    # NOTE: writer is called with `precedent_summaries=summaries` (claim-derived
    # only at this point — bucket-only rows have no summary yet). The writer
    # prompt enforces that precedents marked `(없음 ...)` must NOT have body
    # facts invented — they may only appear in the closing reference list.
    first_answer = write_question_answer(
        user_task=user_task,
        claims=selected_claims,
        precedent_buckets=precedent_buckets,
        answer_plan=answer_plan,
        model=draft_model,
        analysis_mode=analysis_mode,
        precedent_summaries=summaries,
    )
    # Beta-7: coverage patch is intentionally skipped — writer is given a
    # minimal-prompt and full claim ledger, and is allowed to pick whichever
    # claims it trusts (cited_claim_ids) rather than being patched into
    # citing every selected_claim. UI separately surfaces the planner's
    # selected_claim_ids as "추가 후보" alongside the writer's actual cites.
    is_beta7 = analysis_mode == "beta7"
    if skip_coverage_patch or is_beta7:
        patched_answer = _strip_question_answer_meta_prefix(first_answer)
    else:
        write_runtime_status(
            runtime_status_path,
            {
                "phase": "coverage",
                "variant": name,
                "state": "applying_coverage_patch",
                "selected_file_count": len(selected_records),
                "chunk_count": len(chunks),
                "completed_chunks": len(chunks),
                "claim_count": len(merged_claims),
            },
        )
        patched_answer = apply_question_coverage_patch(
            user_task=user_task,
            claims=selected_claims,
            current_answer=first_answer,
            precedent_buckets=precedent_buckets,
            answer_plan=answer_plan,
            model=draft_model,
        )
        patched_answer = _strip_question_answer_meta_prefix(patched_answer)
    final_answer_path = variant_dir / "final_answer.md"
    final_answer_path.write_text(patched_answer, encoding="utf-8")

    # NOTE: no post-writer LLM summarization — the writer prompt and the
    # backend's `_strip_body_citations_outside_claim_ledger` post-pass
    # together guarantee that the body only cites claim-backed precedents,
    # and those already have summaries from the chunk analyzer. Bucket-only
    # precedents appear only in the closing reference list (no body click).

    _write_json(
        variant_dir / "comparison_summary.json",
        {
            "variant": name,
            "selected_file_count": len(selected_records),
            "chunk_count": len(chunks),
            "claim_count": len(merged_claims),
            "selection_source": selection_meta.get("selection_source") or "",
            "keyword_count": len(selection_meta.get("keywords") or []),
        },
    )
    write_runtime_status(
        runtime_status_path,
        {
            "phase": "done",
            "variant": name,
            "state": "completed",
            "selected_file_count": len(selected_records),
            "chunk_count": len(chunks),
            "completed_chunks": len(chunks),
            "claim_count": len(merged_claims),
            "finished_at": time.time(),
        },
    )
    return {
        "variant": name,
        "selected_records": selected_records,
        "merged_claims": merged_claims,
        "final_draft_path": str(final_answer_path),
        "summary_path": str(variant_dir / "comparison_summary.json"),
    }


def run_question_variant(
    *,
    name: str,
    structured_dirs: list[Path],
    user_task: str,
    out_dir: Path,
    select_model: str,
    analyze_model: str,
    draft_model: str,
    keyword_count: int,
    top_k_precedents: int,
    question_chunk_tokens: int,
    analyze_workers: int,
    chunk_build_workers: int,
) -> dict[str, Any]:
    selected_records, selection_meta = select_top_structured_precedent_records(
        structured_dirs,
        user_task=user_task,
        model=select_model,
        keyword_count=keyword_count,
        top_k=top_k_precedents,
    )
    selection_meta = dict(selection_meta)
    selection_meta.setdefault("selection_source", "generated_keywords")
    return _run_question_variant_from_selected_records(
        name=name,
        selected_records=selected_records,
        selection_meta=selection_meta,
        selection_reasoning_text="keywords: " + ", ".join(selection_meta.get("keywords") or []),
        user_task=user_task,
        out_dir=out_dir,
        analyze_model=analyze_model,
        draft_model=draft_model,
        question_chunk_tokens=question_chunk_tokens,
        analyze_workers=analyze_workers,
        chunk_build_workers=chunk_build_workers,
    )


def run_variant(
    *,
    name: str,
    records: list[FileRecord],
    selected_ids: list[str],
    selection_reasoning: list[str],
    user_task: str,
    sample_texts: list[str],
    out_dir: Path,
    analyze_model: str,
    draft_model: str,
) -> dict[str, Any]:
    variant_dir = _variant_dir(out_dir, name)
    runtime_dir = _variant_dir(out_dir, "_runtime")
    runtime_status_path = runtime_dir / "status.json"
    shared_cache_dir = out_dir / "_shared_cache" / "chunk_analysis"
    selected_records = _selected_records_from_ids(records, selected_ids)
    final_draft_path = variant_dir / "final_draft.md"
    claim_ledger_path = variant_dir / "claim_ledger.json"
    summary_path = variant_dir / "comparison_summary.json"

    if final_draft_path.exists() and claim_ledger_path.exists() and summary_path.exists():
        merged_claims = json.loads(claim_ledger_path.read_text(encoding="utf-8"))
        write_runtime_status(
            runtime_status_path,
            {
                "phase": "variant",
                "variant": name,
                "state": "reused_complete",
                "selected_file_count": len(selected_records),
                "claim_count": len(merged_claims),
                "final_draft_path": str(final_draft_path),
            },
        )
        return {
            "variant": name,
            "selected_records": selected_records,
            "merged_claims": merged_claims,
            "final_draft_path": str(final_draft_path),
            "summary_path": str(summary_path),
        }

    write_runtime_status(
        runtime_status_path,
        {
            "phase": "variant",
            "variant": name,
            "state": "starting",
            "selected_file_count": len(selected_records),
        },
    )
    _write_json(
        variant_dir / "selected_files.json",
        [dataclasses.asdict(record) for record in selected_records],
    )
    (variant_dir / "selection_reasoning.txt").write_text("\n\n".join(reason for reason in selection_reasoning if reason).strip(), encoding="utf-8")

    chunks = _build_chunks_for_records(
        selected_records,
        max_tokens=DEFAULT_CHUNK_TOKENS,
        status_path=runtime_status_path,
        variant_name=name,
    )
    write_runtime_status(
        runtime_status_path,
        {
            "phase": "variant",
            "variant": name,
            "state": "analyzing_chunks",
            "selected_file_count": len(selected_records),
            "chunk_count": len(chunks),
            "completed_chunks": 0,
        },
    )
    chunk_outputs = analyze_chunks_cached(
        chunks,
        user_task=user_task,
        model=analyze_model,
        cache_dir=shared_cache_dir,
        status_path=runtime_status_path,
        variant_name=name,
    )
    all_claims = []
    jsonl_path = variant_dir / "chunk_outputs.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as fp:
        for result in chunk_outputs:
            fp.write(json.dumps(result, ensure_ascii=False) + "\n")
            all_claims.extend(result.get("claims_proposed") or [])

    merged_claims = merge_claim_ledgers(all_claims)
    # Evidence gate (span-level) — same semantics as the question pipeline.
    _precedent_text_by_file_id = {r.file_id: r.extracted_text for r in selected_records}
    _force_stats = _force_match_claim_spans(merged_claims, _precedent_text_by_file_id)
    print(f"[force_match_claim_spans document] {_force_stats}", flush=True)
    merged_claims, _gate_stats = gate_and_retry_claim_spans(
        merged_claims, _precedent_text_by_file_id, model=analyze_model
    )
    print(f"[gate_and_retry_claim_spans document] {_gate_stats}", flush=True)
    _write_json(claim_ledger_path, merged_claims)
    write_runtime_status(
        runtime_status_path,
        {
            "phase": "variant",
            "variant": name,
            "state": "synthesizing_sections",
            "selected_file_count": len(selected_records),
            "chunk_count": len(chunks),
            "claim_count": len(merged_claims),
        },
    )

    section_packets = synthesize_section_packets(merged_claims, model=analyze_model, max_tokens=DEFAULT_MAX_REQUEST_TOKENS)
    section_dir = variant_dir / "section_packets"
    for section, texts in section_packets.items():
        (section_dir / f"{_safe_slug(section)}.md").parent.mkdir(parents=True, exist_ok=True)
        (section_dir / f"{_safe_slug(section)}.md").write_text("\n\n".join(texts).strip(), encoding="utf-8")

    write_runtime_status(
        runtime_status_path,
        {
            "phase": "variant",
            "variant": name,
            "state": "writing_final_draft",
            "selected_file_count": len(selected_records),
            "chunk_count": len(chunks),
            "claim_count": len(merged_claims),
            "section_count": len(section_packets),
        },
    )
    final_draft = write_final_opinion(
        user_task=user_task,
        sample_texts=sample_texts,
        claims=merged_claims,
        section_packets=section_packets,
        model=draft_model,
    )
    final_draft_path.write_text(final_draft, encoding="utf-8")
    _write_json(
        summary_path,
        {
            "variant": name,
            "selected_file_count": len(selected_records),
            "chunk_count": len(chunks),
            "claim_count": len(merged_claims),
            "opposing_claim_count": sum(1 for claim in merged_claims if claim.get("oppose_spans")),
            "direct_case_claim_count": sum(1 for claim in merged_claims if claim.get("same_situation_case_exists")),
            "certainty_distribution": Counter(claim.get("certainty") for claim in merged_claims),
        },
    )
    _write_json(
        variant_dir / "final_draft_prompt_input.json",
        {
            "user_task": user_task,
            "sample_text_lengths": [len(text) for text in sample_texts],
            "claim_count": len(merged_claims),
            "sections": list(section_packets.keys()),
        },
    )
    write_runtime_status(
        runtime_status_path,
        {
            "phase": "variant",
            "variant": name,
            "state": "completed",
            "selected_file_count": len(selected_records),
            "chunk_count": len(chunks),
            "claim_count": len(merged_claims),
            "final_draft_path": str(final_draft_path),
        },
    )
    return {
        "variant": name,
        "selected_records": selected_records,
        "merged_claims": merged_claims,
        "final_draft_path": str(final_draft_path),
        "summary_path": str(summary_path),
    }


def build_inventory(root: Path, *, cache_dir: Path) -> list[FileRecord]:
    records: list[FileRecord] = []
    canonical_by_hash: dict[str, FileRecord] = {}
    for path in iter_candidate_paths(root):
        record = build_file_record(root, path, cache_dir=cache_dir)
        for expanded in split_record_on_exact_virtual_separator(record):
            if expanded.content_hash and not expanded.is_direct_evidence:
                existing = canonical_by_hash.get(expanded.content_hash)
                if existing:
                    existing.duplicate_paths.append(expanded.relative_path)
                    continue
                canonical_by_hash[expanded.content_hash] = expanded
            records.append(expanded)
    records.sort(key=lambda item: (item.source_group, item.relative_path))
    return records


def write_comparison(out_dir: Path, variant_results: list[dict[str, Any]]) -> None:
    comparison_dir = _variant_dir(out_dir, "comparison")
    lines = ["# Variant Comparison", ""]
    rows = []
    for result in variant_results:
        rows.append(
            {
                "variant": result["variant"],
                "selected_file_count": len(result["selected_records"]),
                "claim_count": len(result["merged_claims"]),
                "final_draft_path": result["final_draft_path"],
            }
        )
        lines.extend(
            [
                f"## {result['variant']}",
                f"- selected files: {len(result['selected_records'])}",
                f"- merged claims: {len(result['merged_claims'])}",
                f"- final draft: {result['final_draft_path']}",
                "- selected files preview:",
            ]
        )
        for record in result["selected_records"][:20]:
            lines.append(f"  - {record.relative_path}")
        lines.append("")
    (comparison_dir / "variant_compare.md").write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    _write_json(comparison_dir / "variant_compare.json", rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="/mnt/d/Downloads/60_폴더구조_개편/01_학습_법률/lawlaw")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--case-theme", default="선행 인지 후 미조치된 일부 비위를 나중에 다른 비위와 합산해 징계하려는 경우")
    parser.add_argument("--user-task", default="")
    parser.add_argument("--request-json", default="")
    parser.add_argument("--select-model", default=DEFAULT_SELECT_MODEL)
    parser.add_argument("--analyze-model", default=DEFAULT_ANALYZE_MODEL)
    parser.add_argument("--draft-model", default=DEFAULT_DRAFT_MODEL)
    parser.add_argument("--question-mode", action="store_true")
    parser.add_argument("--structured-precedent-dir", action="append", default=[])
    parser.add_argument("--selected-precedent-json", default="")
    parser.add_argument("--keyword-count", type=int, default=10)
    parser.add_argument("--top-k-precedents", type=int, default=100)
    parser.add_argument("--question-chunk-tokens", type=int, default=DEFAULT_QUESTION_CHUNK_TOKENS)
    parser.add_argument("--analyze-workers", type=int, default=DEFAULT_ANALYZE_WORKERS)
    parser.add_argument("--chunk-build-workers", type=int, default=DEFAULT_CHUNK_BUILD_WORKERS)
    parser.add_argument("--skip-coverage-patch", action="store_true", default=False)
    parser.add_argument("--gemini-key-min-gap-ms", type=int, default=0)
    parser.add_argument("--gemini-key-max-inflight", type=int, default=0)
    parser.add_argument("--gemini-key-rpm-limit", type=int, default=-1)
    parser.add_argument("--gemini-key-tpm-limit", type=int, default=-1)
    parser.add_argument("--gemini-global-max-inflight", type=int, default=-1)
    parser.add_argument(
        "--analysis-mode",
        default="",
        help=(
            "Caller-provided analysis mode tag (precise|fast|beta2|beta3|beta4|beta5|beta6|beta7). "
            "beta-4/5/6 use the dual-layer prompt + coverage patch. "
            "beta-7 uses a minimal writer prompt (writer picks own claims, no coverage patch) "
            "and skips most backend post-pass cleanup."
        ),
    )
    parser.add_argument(
        "--format-sample",
        action="append",
        default=[],
        help="Repeatable path to a format sample HWP/TXT/PDF",
    )
    parser.add_argument(
        "--variant",
        action="append",
        choices=ALL_VARIANTS,
        default=[],
        help="Repeatable variant filter. Defaults to all variants in canonical order.",
    )
    args = parser.parse_args()
    requested_variants = resolve_requested_variants(args.variant)

    root = Path(args.root)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    runtime_control_path = out_dir / "_runtime" / "control.json"
    _ensure_runtime_control_file(runtime_control_path)
    _apply_runtime_control_overrides(
        runtime_control_path,
        gemini_key_min_gap_ms=args.gemini_key_min_gap_ms or None,
        gemini_key_max_inflight=args.gemini_key_max_inflight or None,
        gemini_key_rpm_limit=args.gemini_key_rpm_limit if args.gemini_key_rpm_limit >= 0 else None,
        gemini_key_tpm_limit=args.gemini_key_tpm_limit if args.gemini_key_tpm_limit >= 0 else None,
        gemini_global_max_inflight=args.gemini_global_max_inflight if args.gemini_global_max_inflight >= 0 else None,
    )
    set_runtime_control_file(runtime_control_path)
    runtime_status_path = out_dir / "_runtime" / "status.json"
    set_runtime_status_file(runtime_status_path)
    cache_dir = out_dir / "inventory" / "text_cache"
    write_runtime_status(
        runtime_status_path,
        {
            "phase": "startup",
            "state": "building_inventory",
            "out_dir": str(out_dir),
        },
    )

    request_path = Path(args.request_json) if args.request_json else None
    request = load_legal_evidence_request(request_path) if request_path else None

    if args.question_mode:
        user_task = _normalize_space(args.user_task) or _normalize_space(args.case_theme)
        if not user_task:
            raise ValueError("--question-mode requires --user-task or --case-theme")
        selected_precedent_json = Path(args.selected_precedent_json) if args.selected_precedent_json else None
        if selected_precedent_json is not None:
            selected_records = load_selected_question_records(selected_precedent_json)
            result = _run_question_variant_from_selected_records(
                name="question_selected_manual",
                selected_records=selected_records,
                selection_meta={
                    "selection_source": str(selected_precedent_json),
                    "selected_count": len(selected_records),
                },
                selection_reasoning_text=f"selection_source: {selected_precedent_json}",
                user_task=user_task,
                out_dir=out_dir,
                analyze_model=args.analyze_model,
                draft_model=args.draft_model,
                question_chunk_tokens=max(4_000, args.question_chunk_tokens),
                analyze_workers=max(1, args.analyze_workers),
                chunk_build_workers=max(1, args.chunk_build_workers),
                skip_coverage_patch=args.skip_coverage_patch,
                analysis_mode=args.analysis_mode,
            )
        else:
            structured_dirs = [Path(path) for path in args.structured_precedent_dir]
            if not structured_dirs:
                raise ValueError("--question-mode requires --selected-precedent-json or at least one --structured-precedent-dir")
            result = run_question_variant(
                name="question_top100_gemma",
                structured_dirs=structured_dirs,
                user_task=user_task,
                out_dir=out_dir,
                select_model=args.select_model,
                analyze_model=args.analyze_model,
                draft_model=args.draft_model,
                keyword_count=max(1, args.keyword_count),
                top_k_precedents=max(1, args.top_k_precedents),
                question_chunk_tokens=max(4_000, args.question_chunk_tokens),
                analyze_workers=max(1, args.analyze_workers),
                chunk_build_workers=max(1, args.chunk_build_workers),
            )
        write_comparison(out_dir, [result])
        write_runtime_status(
            runtime_status_path,
            {
                "phase": "done",
                "state": "question_variant_completed",
                "variant_count": 1,
                "final_draft_path": result["final_draft_path"],
            },
        )
        print(f"[done] question variant -> {result['final_draft_path']}", flush=True)
        return 0

    inventory = build_inventory(root, cache_dir=cache_dir)
    if request is not None:
        filtered_inventory = filter_records_to_target_files(inventory, request.target_files)
        if not filtered_inventory:
            raise ValueError("request target_files did not match any inventory records")
        inventory = filtered_inventory
    _write_json(out_dir / "inventory" / "files.json", [dataclasses.asdict(record) for record in inventory])
    print(f"[inventory] files={len(inventory)}", flush=True)
    write_runtime_status(
        runtime_status_path,
        {
            "phase": "startup",
            "state": "inventory_built",
            "inventory_file_count": len(inventory),
            "out_dir": str(out_dir),
        },
    )

    sample_paths = [Path(p) for p in args.format_sample]
    sample_texts = [extract_text(path) for path in sample_paths]
    user_task = (
        build_request_user_task(request)
        if request is not None
        else (_normalize_space(args.user_task) or _base_user_task(args.case_theme))
    )

    llm_selected_snapshot = out_dir / "variant_llm_select" / "selected_files.json"
    llm_reason_path = out_dir / "variant_llm_select" / "selection_reasoning.txt"
    llm_selected = _load_selected_ids_snapshot(llm_selected_snapshot)
    llm_reasons = []
    if llm_selected and llm_reason_path.exists():
        llm_reasons = [llm_reason_path.read_text(encoding="utf-8", errors="replace")]
        print(f"[select] llm selection reused={len(llm_selected)}", flush=True)
    else:
        print("[select] llm file selection", flush=True)
        llm_selected, llm_reasons = run_llm_file_select(inventory, user_task=user_task, model=args.select_model)
        _write_json(
            llm_selected_snapshot,
            [dataclasses.asdict(record) for record in _selected_records_from_ids(inventory, llm_selected)],
        )
        llm_reason_path.write_text("\n\n".join(reason for reason in llm_reasons if reason).strip(), encoding="utf-8")
        print(f"[select] llm selected={len(llm_selected)}", flush=True)

    need_embedding_selection = any(
        variant in requested_variants for variant in ("variant_embedding_select", "variant_hybrid")
    )
    embedding_selected, embedding_meta, _ = get_embedding_selection(
        inventory,
        user_task=user_task,
        out_dir=out_dir,
        require_selection=need_embedding_selection,
    )

    direct_ids = [record.file_id for record in inventory if record.is_direct_evidence]
    full_scan_ids = [record.file_id for record in inventory]
    hybrid_ids = list(dict.fromkeys(direct_ids + llm_selected + embedding_selected))

    variant_results = []
    if "variant_llm_select" in requested_variants:
        print("[variant] variant_llm_select", flush=True)
        variant_results.append(
            run_variant(
                name="variant_llm_select",
                records=inventory,
                selected_ids=list(dict.fromkeys(direct_ids + llm_selected)),
                selection_reasoning=llm_reasons,
                user_task=user_task,
                sample_texts=sample_texts,
                out_dir=out_dir,
                analyze_model=args.analyze_model,
                draft_model=args.draft_model,
            )
        )
    if "variant_embedding_select" in requested_variants:
        print("[variant] variant_embedding_select", flush=True)
        variant_results.append(
            run_variant(
                name="variant_embedding_select",
                records=inventory,
                selected_ids=embedding_selected,
                selection_reasoning=["Embedding selector using Gemini embedding model."],
                user_task=user_task,
                sample_texts=sample_texts,
                out_dir=out_dir,
                analyze_model=args.analyze_model,
                draft_model=args.draft_model,
            )
        )
    if "variant_full_scan" in requested_variants:
        print("[variant] variant_full_scan", flush=True)
        variant_results.append(
            run_variant(
                name="variant_full_scan",
                records=inventory,
                selected_ids=full_scan_ids,
                selection_reasoning=["Full scan variant processes every candidate file."],
                user_task=user_task,
                sample_texts=sample_texts,
                out_dir=out_dir,
                analyze_model=args.analyze_model,
                draft_model=args.draft_model,
            )
        )
    if "variant_hybrid" in requested_variants:
        print("[variant] variant_hybrid", flush=True)
        variant_results.append(
            run_variant(
                name="variant_hybrid",
                records=inventory,
                selected_ids=hybrid_ids,
                selection_reasoning=llm_reasons
                + ["Hybrid retains the union of LLM-selected files and embedding-selected files."],
                user_task=user_task,
                sample_texts=sample_texts,
                out_dir=out_dir,
                analyze_model=args.analyze_model,
                draft_model=args.draft_model,
            )
        )
    if not variant_results:
        write_runtime_status(
            runtime_status_path,
            {
                "phase": "done",
                "state": "no_variants_requested",
                "variant_count": 0,
            },
        )
        print("[done] no variants requested", flush=True)
        return 0

    write_comparison(out_dir, variant_results)
    write_runtime_status(
        runtime_status_path,
        {
            "phase": "done",
            "state": "comparison_written",
            "variant_count": len(variant_results),
            "comparison_path": str(out_dir / "comparison" / "variant_compare.md"),
        },
    )
    print("[done] comparison written", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
