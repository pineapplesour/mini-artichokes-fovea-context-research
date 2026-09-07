import io
import json
import inspect
import multiprocessing
import os
import re
import sqlite3
import threading
import time
import urllib.error
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import shared_platform.beta6 as beta6_module
from shared_platform.beta6 import (
    Beta6JobManager,
    LawkeyGemmaGatewayLLMClient,
    MintGeminiGatewayLLMClient,
    OpenAICompatibleLLMClient,
    parse_selection_response,
)
from shared_platform.products import ProductProfile
from shared_platform.search import SearchResult
from shared_platform.server import create_app
from tests.test_search_adapters import _make_documents_db, _make_islam_school_db, _make_precedents_db, _make_tcm_domain_db


SESSION_TOKEN = "runtime-local-session-token-abcdefghijklmnopqrstuvwxyz"


@pytest.fixture(autouse=True)
def _disable_default_lawkey_llm(monkeypatch):
    monkeypatch.setenv("RELIGION_LLM_DISABLED", "1")


class FakeLLMClient:
    def __init__(self):
        self.calls = []

    def complete(self, messages, *, model=""):
        self.calls.append({"messages": messages, "model": model})
        return "LLM beta6 answer"


class SlowLLMClient:
    def complete(self, messages, *, model=""):
        time.sleep(0.25)
        return "slow answer"


class CountingPlannerWriterCacheLLMClient:
    def __init__(self):
        self.planner_calls = 0
        self.writer_calls = 0

    def complete(self, messages, *, model="", timeout_seconds=None):
        system = messages[0]["content"]
        if "answer planner" in system:
            self.planner_calls += 1
            return json.dumps(
                {
                    "body_claim_ids": ["C1"],
                    "coverage_required_claim_ids": ["C1"],
                    "answer_outline": ["cached plan"],
                    "citation_policy": "cite selected claim ids",
                }
            )
        if "source-grounded answer engine" in system:
            self.writer_calls += 1
            return "cached writer answer [C1]"
        return "unused"


class TcmNoisyKeywordLLMClient:
    def __init__(self):
        self.calls = []

    def complete(self, messages, *, model=""):
        self.calls.append({"messages": messages, "model": model})
        system = messages[0]["content"]
        if "keyword generator" in system:
            return '{"keywords":["甘草","감초","licorice","妊娠","임신","pregnancy","本草","본초","禁忌","금기","contraindication","safety"]}'
        if "source selector" in system:
            raise RuntimeError("selector timeout")
        return "writer used fallback-selected evidence"


class CountingWideSelectorLLMClient:
    def __init__(self):
        self.selector_prompt = ""
        self.selector_prompts = []
        self.writer_prompt = ""

    def complete(self, messages, *, model=""):
        prompt = "\n".join(message["content"] for message in messages)
        system = messages[0]["content"]
        if "keyword generator" in system:
            return '{"keywords":["sharedterm","evidence","principle","context","argument","source","position","record","claim","rule"]}'
        if "source selector" in system:
            self.selector_prompts.append(prompt)
            self.selector_prompt = "\n\n".join(self.selector_prompts)
            ids = re.findall(r"file_id:\s*(doc-\d{3})", prompt)
            return "wide beta6 selection\n<selection>\n" + "\n".join(ids[:100]) + "\n</selection>"
        self.writer_prompt = prompt
        return "wide answer"


class FrontierCountingLLMClient:
    def __init__(self):
        self.selector_prompt = ""
        self.selector_prompts = []

    def complete(self, messages, *, model="", timeout_seconds=None):
        prompt = "\n".join(message["content"] for message in messages)
        system = messages[0]["content"]
        if "keyword generator" in system:
            return '{"keywords":["kw1","kw2","kw3","kw4","kw5","kw6","kw7","kw8","kw9","kw10"]}'
        if "source selector" in system:
            self.selector_prompts.append(prompt)
            self.selector_prompt = "\n\n".join(self.selector_prompts)
            ids = re.findall(r"file_id:\s*(frontier-\d{4})", prompt)
            return "frontier selection\n<selection>\n" + "\n".join(ids[:100]) + "\n</selection>"
        if "claim-card analyzer" in system:
            return '{"claim_cards":[]}'
        if "answer planner" in system:
            return '{"body_claim_ids":["C1"],"coverage_required_claim_ids":["C1"],"answer_outline":["frontier"],"citation_policy":"cite"}'
        return "frontier answer [C1]"


class TwoRoundKeywordLLMClient:
    def __init__(self):
        self.selector_prompt = ""
        self.selector_prompts = []

    def complete(self, messages, *, model="", timeout_seconds=None):
        prompt = "\n".join(message["content"] for message in messages)
        system = messages[0]["content"]
        if "keyword generator" in system and "Additional retrieval keyword round" in prompt:
            return '{"keywords":["late-specific-one","late-specific-two","late-specific-three","late-specific-four","late-specific-five","late-specific-six","late-specific-seven","late-specific-eight","late-specific-nine","late-specific-ten"]}'
        if "keyword generator" in system:
            return '{"keywords":["old-one","old-two","old-three","old-four","old-five","old-six","old-seven","old-eight","old-nine","old-ten"]}'
        if "source selector" in system:
            self.selector_prompts.append(prompt)
            self.selector_prompt = "\n\n".join(self.selector_prompts)
            ids = re.findall(r"file_id:\s*(frontier-\d{4})", prompt)
            return "two-round selection\n<selection>\n" + "\n".join(ids[:100]) + "\n</selection>"
        if "claim-card analyzer" in system:
            return '{"claim_cards":[]}'
        if "answer planner" in system:
            return '{"body_claim_ids":["C1"],"coverage_required_claim_ids":["C1"],"answer_outline":["frontier"],"citation_policy":"cite"}'
        return "two round answer [C1]"


class FullFrontierAuditLLMClient:
    def __init__(self):
        self.selector_prompts = []
        self.selector_prompt = ""

    def complete(self, messages, *, model="", timeout_seconds=None):
        prompt = "\n".join(message["content"] for message in messages)
        system = messages[0]["content"]
        if "keyword generator" in system:
            return '{"keywords":["kw1","kw2","kw3","kw4","kw5","kw6","kw7","kw8","kw9","kw10"]}'
        if "source selector" in system:
            self.selector_prompts.append(prompt)
            self.selector_prompt = "\n\n".join(self.selector_prompts)
            ids = re.findall(r"file_id:\s*(frontier-\d{4})", prompt)
            if "frontier-1199" in ids:
                return "late decisive selection\n<selection>\nfrontier-1199\n</selection>"
            return "no useful source in this batch\n<selection>\n<none/>\n</selection>"
        if "claim-card analyzer" in system:
            return '{"claim_cards":[]}'
        if "answer planner" in system:
            return '{"body_claim_ids":["C1"],"coverage_required_claim_ids":["C1"],"answer_outline":["frontier"],"citation_policy":"cite"}'
        return "frontier answer [C1]"


class StageTimeoutLLMClient:
    def __init__(self):
        self.calls = []

    def complete(self, messages, *, model="", timeout_seconds=None):
        system = messages[0]["content"]
        self.calls.append({"system": system, "timeout_seconds": timeout_seconds})
        if "keyword generator" in system:
            return '{"keywords":["sharedterm","evidence","principle","context","argument","source","position","record","claim","rule"]}'
        if "source selector" in system:
            raise RuntimeError("selector timeout")
        return "writer after bounded selector fallback"


class SparseSelectorLLMClient:
    def complete(self, messages, *, model="", timeout_seconds=None):
        prompt = "\n".join(message["content"] for message in messages)
        system = messages[0]["content"]
        if "keyword generator" in system:
            return '{"keywords":["sharedterm","evidence","principle","context","argument","source","position","record","claim","rule"]}'
        if "source selector" in system:
            ids = re.findall(r"file_id:\s*(doc-\d{3})", prompt)
            return "sparse selection\n<selection>\n" + "\n".join(ids[:3]) + "\n</selection>"
        return "writer after sparse selector"


class OversizedPromptBatchedSelectorLLMClient:
    def __init__(self):
        self.selector_calls = []

    def complete(self, messages, *, model="", timeout_seconds=None):
        prompt = "\n".join(message["content"] for message in messages)
        system = messages[0]["content"]
        if "keyword generator" in system:
            return '{"keywords":["sharedterm","evidence","principle","context","argument","source","position","record","claim","rule"]}'
        if "source selector" in system:
            ids = re.findall(r"file_id:\s*(doc-\d{3})", prompt)
            self.selector_calls.append({"ids": ids, "timeout_seconds": timeout_seconds, "prompt": prompt})
            if len(ids) > 25:
                raise RuntimeError("oversized selector prompt")
            return "batch selection\n<selection>\n" + "\n".join(ids[:2]) + "\n</selection>"
        return "writer after batched selector"


class TimeoutSelectorLLMClient:
    def __init__(self):
        self.selector_calls = []

    def complete(self, messages, *, model="", timeout_seconds=None):
        prompt = "\n".join(message["content"] for message in messages)
        system = messages[0]["content"]
        if "source selector" in system:
            ids = re.findall(r"file_id:\s*(doc-\d{3})", prompt)
            self.selector_calls.append({"ids": ids, "timeout_seconds": timeout_seconds})
            raise RuntimeError("Read timed out while selecting sources")
        return "unused"


class TimeoutLargeBatchSelectorLLMClient:
    def __init__(self):
        self.selector_calls = []

    def complete(self, messages, *, model="", timeout_seconds=None):
        prompt = "\n".join(message["content"] for message in messages)
        system = messages[0]["content"]
        if "source selector" in system:
            ids = re.findall(r"file_id:\s*(doc-\d{3})", prompt)
            self.selector_calls.append({"ids": ids, "timeout_seconds": timeout_seconds})
            if len(ids) > 25:
                raise RuntimeError("Read timed out while selecting sources")
            return "timeout recovery selection\n<selection>\n" + "\n".join(ids[:2]) + "\n</selection>"
        return "unused"


class ParallelRecoverySelectorLLMClient:
    def __init__(self):
        self.selector_calls = []
        self.active_subbatches = 0
        self.max_active_subbatches = 0
        self._lock = threading.Lock()

    def complete(self, messages, *, model="", timeout_seconds=None):
        prompt = "\n".join(message["content"] for message in messages)
        system = messages[0]["content"]
        if "source selector" in system:
            ids = re.findall(r"file_id:\s*(doc-\d{3})", prompt)
            self.selector_calls.append({"ids": ids, "timeout_seconds": timeout_seconds})
            if len(ids) > 25:
                raise RuntimeError("Read timed out while selecting sources")
            if len(ids) == 25:
                with self._lock:
                    self.active_subbatches += 1
                    self.max_active_subbatches = max(self.max_active_subbatches, self.active_subbatches)
                deadline = time.monotonic() + 0.25
                while time.monotonic() < deadline:
                    with self._lock:
                        if self.max_active_subbatches >= 4:
                            break
                    time.sleep(0.01)
                with self._lock:
                    self.active_subbatches -= 1
            return "parallel recovery selection\n<selection>\n" + "\n".join(ids[:2]) + "\n</selection>"
        return "unused"


class RateLimitOnceSelectorLLMClient:
    def __init__(self):
        self.selector_calls = []
        self.seen_batches = set()

    def complete(self, messages, *, model="", timeout_seconds=None):
        prompt = "\n".join(message["content"] for message in messages)
        system = messages[0]["content"]
        if "source selector" in system:
            ids = re.findall(r"file_id:\s*(doc-\d{3})", prompt)
            self.selector_calls.append({"ids": ids, "timeout_seconds": timeout_seconds})
            key = tuple(ids)
            if key not in self.seen_batches:
                self.seen_batches.add(key)
                raise RuntimeError("Gemini logical timeout exhausted for gemma-4-26b-a4b-it; last_error=HTTP 429")
            return "rate limit retry selection\n<selection>\n" + "\n".join(ids[:2]) + "\n</selection>"
        return "unused"


class TraceReportingSelectorLLMClient:
    def __init__(self):
        self.selector_calls = []
        self._traces_by_thread = {}
        self._lock = threading.Lock()

    def complete(self, messages, *, model="", timeout_seconds=None):
        prompt = "\n".join(message["content"] for message in messages)
        system = messages[0]["content"]
        if "source selector" in system:
            ids = re.findall(r"file_id:\s*(doc-\d{3})", prompt)
            self.selector_calls.append({"ids": ids, "timeout_seconds": timeout_seconds})
            with self._lock:
                self._traces_by_thread[threading.get_ident()] = {
                    "status": "completed",
                    "elapsedSec": 1.25,
                    "preHttpWaitSec": 0.75,
                    "httpStarted": 1,
                    "httpFinished": 1,
                    "model": model,
                }
            return "trace selection\n<selection>\n" + "\n".join(ids[:2]) + "\n</selection>"
        return "unused"

    def consume_last_call_trace(self):
        with self._lock:
            return self._traces_by_thread.pop(threading.get_ident(), None)


class PhaseTraceTimeoutThenRecoveryLLMClient:
    def __init__(self):
        self.selector_calls = []
        self._traces_by_thread = {}
        self._lock = threading.Lock()

    def complete(self, messages, *, model="", timeout_seconds=None):
        prompt = "\n".join(message["content"] for message in messages)
        system = messages[0]["content"]
        if "source selector" in system:
            ids = re.findall(r"file_id:\s*(doc-\d{3})", prompt)
            self.selector_calls.append({"ids": ids, "timeout_seconds": timeout_seconds})
            with self._lock:
                self._traces_by_thread[threading.get_ident()] = {
                    "status": "completed" if len(ids) <= 25 else "error",
                    "elapsedSec": 8.0 if len(ids) <= 25 else 90.0,
                    "preHttpWaitSec": 0.1 if len(ids) <= 25 else 0.2,
                    "httpStarted": 1,
                    "httpFinished": 1 if len(ids) <= 25 else 0,
                    "model": model,
                }
            if len(ids) > 25:
                raise RuntimeError("Read timed out while selecting sources")
            return "phase recovery selection\n<selection>\n" + "\n".join(ids[:2]) + "\n</selection>"
        return "unused"

    def consume_last_call_trace(self):
        with self._lock:
            return self._traces_by_thread.pop(threading.get_ident(), None)


class TimeoutThenRateLimitedSubBatchSelectorLLMClient:
    def __init__(self):
        self.selector_calls = []
        self.rate_limited_keys = set()

    def complete(self, messages, *, model="", timeout_seconds=None):
        prompt = "\n".join(message["content"] for message in messages)
        system = messages[0]["content"]
        if "source selector" in system:
            ids = re.findall(r"file_id:\s*(doc-\d{3})", prompt)
            self.selector_calls.append({"ids": ids, "timeout_seconds": timeout_seconds})
            if len(ids) in {25, 5}:
                raise RuntimeError("Read timed out while selecting sources")
            key = tuple(ids)
            if key not in self.rate_limited_keys:
                self.rate_limited_keys.add(key)
                raise RuntimeError("Gemini selector failed: HTTP 429 Too Many Requests")
            return "rate-limited recovery selection\n<selection>\n" + "\n".join(ids[:2]) + "\n</selection>"
        return "unused"


class SlowConcurrentSelectorLLMClient:
    def __init__(self):
        self.selector_calls = []
        self._lock = threading.Lock()

    def complete(self, messages, *, model="", timeout_seconds=None):
        prompt = "\n".join(message["content"] for message in messages)
        system = messages[0]["content"]
        if "source selector" in system:
            ids = re.findall(r"file_id:\s*(doc-\d{3})", prompt)
            time.sleep(0.08)
            with self._lock:
                self.selector_calls.append({"ids": ids, "timeout_seconds": timeout_seconds})
            return "slow concurrent selection\n<selection>\n" + "\n".join(ids[:2]) + "\n</selection>"
        return "unused"


def _fill_batch_cache_from_process(cache_root: str, producer_log: str, queue, barrier) -> None:
    os.environ["RELIGION_BETA6_BATCH_CACHE_ROOT"] = cache_root
    os.environ["RELIGION_BETA6_BATCH_CACHE_LOCK_TIMEOUT_SECONDS"] = "5"
    os.environ["RELIGION_BETA6_BATCH_CACHE_LOCK_POLL_SECONDS"] = "0.02"
    payload = {"cacheVersion": "test-process-lease", "batch": 1, "fingerprint": "same-process-miss"}

    def produce() -> dict:
        time.sleep(0.12)
        with open(producer_log, "a", encoding="utf-8") as handle:
            handle.write(f"{os.getpid()}\n")
        return {"filledBy": os.getpid()}

    try:
        barrier.wait(timeout=5)
        value, cache_hit = beta6_module._read_or_fill_batch_cache("selector", payload, produce)
        queue.put({"ok": True, "value": value, "cacheHit": cache_hit})
    except BaseException as exc:
        queue.put({"ok": False, "error": repr(exc)})


class OversizedPromptBatchedClaimAnalyzerLLMClient:
    def __init__(self):
        self.claim_calls = []

    def complete(self, messages, *, model="", timeout_seconds=None):
        prompt = "\n".join(message["content"] for message in messages)
        system = messages[0]["content"]
        if "keyword generator" in system:
            return '{"keywords":["sharedterm","evidence","principle","context","argument","source","position","record","claim","rule"]}'
        if "source selector" in system:
            ids = re.findall(r"file_id:\s*(doc-\d{3})", prompt)
            return "claim batch selection\n<selection>\n" + "\n".join(ids[:100]) + "\n</selection>"
        if "claim-card analyzer" in system:
            source_rows = re.findall(r"\[(S\d+)\]\nsource_id:\s*(doc-\d{3})", prompt)
            self.claim_calls.append({"sources": source_rows, "timeout_seconds": timeout_seconds, "prompt": prompt})
            if len(source_rows) > 25:
                raise RuntimeError("oversized claim-card prompt")
            cards = [
                {
                    "source_label": label,
                    "source_id": source_id,
                    "claim_axis": f"axis {source_id}",
                    "stance": "support",
                    "context_summary": f"{source_id} context summary",
                    "claim_summary": f"{source_id} claim summary",
                    "quote": "sharedterm evidence",
                }
                for label, source_id in source_rows
            ]
            return json.dumps({"claim_cards": cards}, ensure_ascii=False)
        if "answer planner" in system:
            return json.dumps(
                {
                    "body_claim_ids": ["C1", "C2"],
                    "coverage_required_claim_ids": ["C1", "C2"],
                    "answer_outline": ["batched claim evidence"],
                    "citation_policy": "cite selected claim ids",
                }
            )
        return "writer after batched claim analyzer [C1] [C2]"


class ChunkLevelClaimAnalyzerLLMClient:
    def __init__(self):
        self.chunk_calls = []

    def complete(self, messages, *, model="", timeout_seconds=None):
        prompt = "\n".join(message["content"] for message in messages)
        system = messages[0]["content"]
        if "chunk-level claim-card analyzer" in system:
            chunk_id_match = re.search(r"chunk_id:\s*([^\s]+)", prompt)
            chunk_id = chunk_id_match.group(1) if chunk_id_match else "missing-chunk"
            self.chunk_calls.append({"chunk_id": chunk_id, "prompt": prompt, "timeout_seconds": timeout_seconds})
            quote = "first chunk exact evidence" if chunk_id == "chunk-1" else "second chunk exact evidence"
            return json.dumps(
                {
                    "claim_cards": [
                        {
                            "source_label": "S1",
                            "source_id": "doc-001",
                            "chunk_id": chunk_id,
                            "claim_axis": f"axis {chunk_id}",
                            "stance": "support",
                            "context_summary": f"context {chunk_id}",
                            "claim_summary": f"summary {chunk_id}",
                            "quote": quote,
                        }
                    ]
                },
                ensure_ascii=False,
            )
        if "claim-card analyzer" in system:
            raise AssertionError("source-level claim analyzer should not be used when chunks are supplied")
        return "writer after chunk claim analyzer"


class DuplicateAxisChunkClaimAnalyzerLLMClient:
    def __init__(self):
        self.chunk_calls = []

    def complete(self, messages, *, model="", timeout_seconds=None):
        prompt = "\n".join(message["content"] for message in messages)
        system = messages[0]["content"]
        if "chunk-level claim-card analyzer" in system:
            self.chunk_calls.append({"prompt": prompt, "timeout_seconds": timeout_seconds})
            source_match = re.search(r"source_id:\s*([^\s]+)", prompt)
            label_match = re.search(r"\[(S\d+)\]", prompt)
            source_id = source_match.group(1) if source_match else "doc-missing"
            label = label_match.group(1) if label_match else "S1"
            quote = "first source prayer obligation evidence" if source_id == "doc-a" else "second source prayer obligation evidence"
            return json.dumps(
                {
                    "claim_cards": [
                        {
                            "source_label": label,
                            "source_id": source_id,
                            "chunk_id": source_id,
                            "claim_axis": "prayer obligation",
                            "stance": "support",
                            "context_summary": f"context for {source_id}",
                            "claim_summary": f"{source_id} supports prayer obligation",
                            "quote": quote,
                        }
                    ]
                },
                ensure_ascii=False,
            )
        return "unused"


class RetryingClaimQuoteLLMClient:
    def __init__(self):
        self.claim_calls = []
        self.retry_calls = []

    def complete(self, messages, *, model="", timeout_seconds=None):
        prompt = "\n".join(message["content"] for message in messages)
        system = messages[0]["content"]
        if "claim quote span retry" in system:
            self.retry_calls.append({"prompt": prompt, "timeout_seconds": timeout_seconds})
            return json.dumps(
                {
                    "quote": "actual source exact sentence about prayer timing and obligation.",
                },
                ensure_ascii=False,
            )
        if "claim-card analyzer" in system:
            self.claim_calls.append({"prompt": prompt, "timeout_seconds": timeout_seconds})
            return json.dumps(
                {
                    "claim_cards": [
                        {
                            "source_label": "S1",
                            "source_id": "doc-retry",
                            "claim_axis": "prayer timing",
                            "stance": "support",
                            "context_summary": "source context",
                            "claim_summary": "claim summary",
                            "quote": "made up evidence sentence that does not appear anywhere",
                        }
                    ]
                },
                ensure_ascii=False,
            )
        return "unused"


class CapturingBeta6LLMClient:
    def __init__(self):
        self.calls = []

    def complete(self, messages, *, model="", timeout_seconds=None):
        prompt = "\n".join(message["content"] for message in messages)
        self.calls.append({"messages": messages, "model": model, "timeout_seconds": timeout_seconds, "prompt": prompt})
        system = messages[0]["content"]
        if "keyword generator" in system:
            return '{"keywords":["qibla","wali","nikah","madhhab","tafsir","hadith","fiqh","sect","arabic","school"]}'
        if "source selector" in system:
            ids = re.findall(r"file_id:\s*([^\s,;<>]+)", prompt)
            return "selected\n<selection>\n" + "\n".join(ids[:3]) + "\n</selection>"
        if "claim-card analyzer" in system:
            return '{"claim_cards":[]}'
        return "writer saw claim ledger"


class IterativeKeywordLLMClient:
    def __init__(self):
        self.calls = []

    def complete(self, messages, *, model="", timeout_seconds=None):
        prompt = "\n".join(message["content"] for message in messages)
        system = messages[0]["content"]
        self.calls.append({"system": system, "prompt": prompt, "timeout_seconds": timeout_seconds})
        if "keyword generator" in system and "Additional retrieval" not in prompt:
            return '{"keywords":["nohit-one","nohit-two","nohit-three"]}'
        if "keyword generator" in system and "Additional retrieval" in prompt:
            return '{"keywords":["latekw","latekw second","latekw third"]}'
        if "source selector" in system:
            ids = re.findall(r"file_id:\s*(doc-late-\d)", prompt)
            return "selected after refill\n<selection>\n" + "\n".join(ids) + "\n</selection>"
        if "claim-card analyzer" in system:
            return '{"claim_cards":[]}'
        return "writer after iterative refill"


class BroadThenSpecificKeywordLLMClient:
    def __init__(self):
        self.calls = []

    def complete(self, messages, *, model="", timeout_seconds=None):
        prompt = "\n".join(message["content"] for message in messages)
        system = messages[0]["content"]
        self.calls.append({"system": system, "prompt": prompt, "timeout_seconds": timeout_seconds})
        if "keyword generator" in system and "Additional retrieval" not in prompt:
            return '{"keywords":["broadkw"]}'
        if "keyword generator" in system and "Additional retrieval" in prompt:
            return '{"keywords":["late-specific"]}'
        if "source selector" in system:
            ids = re.findall(r"file_id:\s*(doc-[a-z0-9-]+)", prompt)
            selected = [item for item in ids if item == "doc-late-specific"] or ids[:1]
            return "selected after specific keyword audit\n<selection>\n" + "\n".join(selected) + "\n</selection>"
        if "claim-card analyzer" in system:
            return '{"claim_cards":[]}'
        return "writer after specific keyword audit"


class AlternatingKeywordLLMClient:
    def __init__(self):
        self.calls = []
        self.keyword_calls = 0

    def complete(self, messages, *, model="", timeout_seconds=None):
        prompt = "\n".join(message["content"] for message in messages)
        system = messages[0]["content"]
        self.calls.append({"system": system, "prompt": prompt, "timeout_seconds": timeout_seconds})
        if "keyword generator" in system:
            self.keyword_calls += 1
            if self.keyword_calls == 1:
                return '{"keywords":["stablekw"]}'
            return '{"keywords":["driftkw"]}'
        if "source selector" in system:
            ids = re.findall(r"file_id:\s*(doc-[a-z]+-\d)", prompt)
            return "cached keyword selection\n<selection>\n" + "\n".join(ids[:4]) + "\n</selection>"
        if "claim-card analyzer" in system:
            return '{"claim_cards":[]}'
        return "writer after keyword cache"


class LedgerSelectorLLMClient:
    def __init__(self):
        self.selector_prompt = ""

    def complete(self, messages, *, model="", timeout_seconds=None):
        prompt = "\n".join(message["content"] for message in messages)
        self.selector_prompt = prompt
        ids = re.findall(r"file_id:\s*([^\s,;<>]+)", prompt)
        rows = [
            json.dumps(
                {
                    "file_id": item,
                    "context_summary": f"{item} 문헌 맥락",
                    "claim_summary": f"{item} 쟁점 요약",
                    "quote_candidate": "ownership justice evidence",
                    "source_role": "fiqh",
                    "stance": "school_position",
                },
                ensure_ascii=False,
            )
            for item in ids[:3]
        ]
        return "\n".join(rows) + "\n<selection>\n" + "\n".join(ids[:3]) + "\n</selection>"


class ClaimAnalyzerLLMClient:
    def __init__(self):
        self.calls = []

    def complete(self, messages, *, model="", timeout_seconds=None):
        prompt = "\n".join(message["content"] for message in messages)
        system = messages[0]["content"]
        self.calls.append({"system": system, "prompt": prompt, "timeout_seconds": timeout_seconds})
        if "keyword generator" in system:
            return '{"keywords":["ولي","نكاح","hanafi"]}'
        if "source selector" in system:
            return "selected\n<selection>\ndoc-wali-hanafi\n</selection>"
        if "claim-card analyzer" in system:
            return json.dumps(
                {
                    "claim_cards": [
                        {
                            "source_label": "S1",
                            "source_id": "doc-wali-hanafi",
                            "claim_axis": "Hanafi wali discussion",
                            "stance": "school_position",
                            "context_summary": "이 카드는 하나피 문헌에서 혼인 보호자 논점을 다루는 부분이다.",
                            "claim_summary": "하나피 쪽 논의는 보호자와 혼인계약 조건을 함께 검토한다.",
                            "quote": "Hanafi school discussion mentions wali and marriage contract conditions.",
                        }
                    ]
                },
                ensure_ascii=False,
            )
        return "writer used analyzed claim cards"


class PlanCoverageLLMClient:
    def __init__(self):
        self.calls = []

    def complete(self, messages, *, model="", timeout_seconds=None):
        prompt = "\n".join(message["content"] for message in messages)
        system = messages[0]["content"]
        self.calls.append({"system": system, "prompt": prompt, "timeout_seconds": timeout_seconds})
        if "keyword generator" in system:
            return '{"keywords":["sharedterm","evidence","claim"]}'
        if "source selector" in system:
            return "selected\n<selection>\ndoc-000\ndoc-001\n</selection>"
        if "claim-card analyzer" in system:
            return json.dumps(
                {
                    "claim_cards": [
                        {
                            "source_label": "S1",
                            "source_id": "doc-000",
                            "claim_axis": "first planned axis",
                            "stance": "support",
                            "context_summary": "첫 번째 근거의 문맥",
                            "claim_summary": "첫 번째 계획 claim",
                            "quote": "sharedterm evidence principle context argument source position record claim rule 000.",
                        },
                        {
                            "source_label": "S2",
                            "source_id": "doc-001",
                            "claim_axis": "second planned axis",
                            "stance": "support",
                            "context_summary": "두 번째 근거의 문맥",
                            "claim_summary": "두 번째 계획 claim",
                            "quote": "sharedterm evidence principle context argument source position record claim rule 001.",
                        },
                    ]
                },
                ensure_ascii=False,
            )
        if "answer planner" in system:
            return json.dumps(
                {
                    "body_claim_ids": ["C1", "C2"],
                    "coverage_required_claim_ids": ["C1", "C2"],
                    "claim_groups": [
                        {"title": "핵심 근거", "claim_ids": ["C1", "C2"], "summary": "두 claim 모두 본문에서 다뤄야 함"}
                    ],
                    "answer_outline": ["첫 claim", "둘째 claim"],
                    "citation_policy": "본문 주요 문단마다 C citation을 붙인다.",
                },
                ensure_ascii=False,
            )
        return "### 답변\n첫 번째 계획 claim만 본문에서 다룹니다. [C1]"


class ThoughtLeakLLMClient:
    def __init__(self):
        self.calls = []

    def complete(self, messages, *, model="", timeout_seconds=None):
        system = messages[0]["content"]
        self.calls.append({"system": system, "timeout_seconds": timeout_seconds})
        if "keyword generator" in system:
            return '{"keywords":["sharedterm","evidence"]}'
        if "source selector" in system:
            return "selected\n<selection>\ndoc-000\n</selection>"
        if "claim-card analyzer" in system:
            return json.dumps(
                {
                    "claim_cards": [
                        {
                            "source_label": "S1",
                            "source_id": "doc-000",
                            "claim_axis": "visible answer",
                            "stance": "support",
                            "context_summary": "근거 문맥",
                            "claim_summary": "본문에 남아야 하는 근거",
                            "quote": "sharedterm evidence principle context argument source position record claim rule 000.",
                        }
                    ]
                },
                ensure_ascii=False,
            )
        if "answer planner" in system:
            return '{"body_claim_ids":["C1"],"coverage_required_claim_ids":["C1"],"answer_outline":["답변"],"citation_policy":"cite"}'
        return "[thought]\n내부 계획은 노출되면 안 된다.\n[/thought]\n### 답변\n본문에 남아야 하는 근거를 설명합니다. [C1]"


class EnglishBoilerplateLLMClient(ThoughtLeakLLMClient):
    def complete(self, messages, *, model="", timeout_seconds=None):
        system = messages[0]["content"]
        if "source-grounded answer engine" in system:
            self.calls.append({"system": system, "timeout_seconds": timeout_seconds})
            return (
                "## GEMMA4 CITED ANSWER\n"
                "### PRIMARY TEXT SOURCE\n"
                "본문에 남아야 하는 근거를 설명합니다. [C1]\n"
                "### CROSS-CHECK SOURCE\n"
                "다른 근거와 함께 확인합니다. [C1]"
            )
        return super().complete(messages, model=model, timeout_seconds=timeout_seconds)


class CheckpointResumeLLMClient:
    def __init__(self):
        self.calls = []

    def complete(self, messages, *, model="", timeout_seconds=None):
        system = messages[0]["content"]
        self.calls.append({"system": system, "timeout_seconds": timeout_seconds})
        if "keyword generator" in system or "source selector" in system:
            raise AssertionError("selection checkpoint should avoid keyword and selector calls")
        if "claim-card analyzer" in system:
            return '{"claim_cards":[]}'
        if "answer planner" in system:
            return '{"body_claim_ids":["C1"],"coverage_required_claim_ids":["C1"],"answer_outline":["checkpoint"],"citation_policy":"cite"}'
        return "checkpoint resumed writer answer"


class ClaimCheckpointResumeLLMClient:
    def __init__(self):
        self.calls = []

    def complete(self, messages, *, model="", timeout_seconds=None):
        system = messages[0]["content"]
        self.calls.append({"system": system, "timeout_seconds": timeout_seconds})
        if "keyword generator" in system or "source selector" in system or "claim-card analyzer" in system:
            raise AssertionError("stage checkpoints should avoid selection and claim analyzer calls")
        if "answer planner" in system:
            return '{"body_claim_ids":["C1"],"coverage_required_claim_ids":["C1"],"answer_outline":["checkpoint"],"citation_policy":"cite"}'
        return "claim checkpoint resumed writer answer [C1]"


class PlanCheckpointResumeLLMClient:
    def __init__(self):
        self.calls = []

    def complete(self, messages, *, model="", timeout_seconds=None):
        system = messages[0]["content"]
        self.calls.append({"system": system, "timeout_seconds": timeout_seconds})
        if (
            "keyword generator" in system
            or "source selector" in system
            or "claim-card analyzer" in system
            or "answer planner" in system
        ):
            raise AssertionError("stage checkpoints should avoid selection, claim analyzer, and answer planner calls")
        return "plan checkpoint resumed writer answer [C1]"


def _profile(db_path):
    return ProductProfile(
        key="islam",
        name="Hikmah AI",
        db_path=db_path,
        db_shape="precedents",
        languages=("en", "ko", "ar"),
        default_language="en",
        theme="islam",
        safety_notice="quran safety notice",
    )


def _claim_durable_queue_row_from_process(runs_root: str, job_id: str, queue, barrier) -> None:
    try:
        runtime = Beta6JobManager(
            {"islam": _profile(Path(runs_root) / "islam.sqlite3")},
            runs_root=Path(runs_root),
            resume_pending_jobs=False,
        )
        barrier.wait(timeout=5)
        claimed = runtime._claim_durable_queue_row(job_id)
        queue.put({"ok": True, "claimed": bool(claimed), "pid": os.getpid()})
    except BaseException as exc:
        queue.put({"ok": False, "error": repr(exc), "pid": os.getpid()})


def _make_many_precedents_db(path, *, count=120):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE precedents (
          canonical_id TEXT PRIMARY KEY,
          source_dataset TEXT,
          source_path TEXT,
          title TEXT,
          case_number TEXT,
          court TEXT,
          decision_date TEXT,
          case_name TEXT,
          case_type TEXT,
          full_text TEXT NOT NULL,
          text_hash TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE precedents_fts USING fts5(
          canonical_id UNINDEXED,
          full_text,
          tokenize='unicode61'
        );
        """
    )
    for index in range(count):
        canonical_id = f"doc-{index:03d}"
        text = (
            "[META]\n"
            "religion: islam\n"
            "tradition: sunni\n"
            "school: generic\n"
            "authority_level: 70\n"
            "source_kind: fiqh\n\n"
            f"sharedterm evidence principle context argument source position record claim rule {index:03d}."
        )
        conn.execute(
            "INSERT INTO precedents VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                canonical_id,
                "islam/sunni/generic/fiqh",
                f"fiqh/doc-{index:03d}",
                f"Document {index:03d}",
                f"Doc {index:03d}",
                "Generic fiqh",
                "",
                "wide selection",
                "fiqh_unit",
                text,
                f"hash-{index:03d}",
            ),
        )
        conn.execute("INSERT INTO precedents_fts(canonical_id, full_text) VALUES (?, ?)", (canonical_id, text))
    conn.commit()
    conn.close()


def _tcm_profile(db_path):
    return ProductProfile(
        key="tcm",
        name="Hanui AI",
        db_path=db_path,
        db_shape="precedents",
        languages=("ko", "en"),
        default_language="ko",
        theme="tcm",
        safety_notice="문헌 기반 정보 도구이며 진단이나 치료 지시가 아닙니다.",
    )


def _simli_profile(db_path):
    return ProductProfile(
        key="simli",
        name="마음결 AI",
        db_path=db_path,
        db_shape="documents",
        languages=("ko", "en"),
        default_language="ko",
        theme="simli",
        safety_notice="진단이 아닙니다. 자해·타해 위험이나 즉시 위험이 있으면 현지 긴급 도움을 먼저 요청하세요.",
    )


def _result(identifier, text, *, source_kind="fiqh", school="", tradition=""):
    return SearchResult(
        canonical_id=identifier,
        title=identifier,
        citation=identifier,
        authority_body="fixture",
        source_date="",
        case_name="fixture",
        case_type=f"{source_kind}_unit",
        full_text=(
            "[META]\n"
            f"source_kind: {source_kind}\n"
            f"school: {school}\n"
            f"tradition: {tradition}\n\n"
            f"{text}"
        ),
        source_dataset=f"fixture/{source_kind}",
        source_path=identifier,
        score=100,
        tradition=tradition,
        school=school,
        source_kind=source_kind,
        authority_level=80,
    )


def test_default_llm_client_uses_lawkey_gemini_when_keys_available(monkeypatch):
    monkeypatch.delenv("RELIGION_LLM_DISABLED", raising=False)
    monkeypatch.delenv("RELIGION_CHAT_API_URL", raising=False)
    monkeypatch.delenv("RELIGION_LLM_PROVIDER", raising=False)
    monkeypatch.setattr(beta6_module, "_lawkey_gemini_keys_available", lambda: True)

    client = beta6_module.default_llm_client_from_env()

    assert getattr(beta6_module, "LawkeyGeminiLLMClient", None) is not None
    assert isinstance(client, beta6_module.LawkeyGeminiLLMClient)
    assert client.default_model == "gemma-4-26b-a4b-it"


def test_default_llm_client_can_use_explicit_gemma_gateway_proxy_provider(monkeypatch):
    monkeypatch.delenv("RELIGION_LLM_DISABLED", raising=False)
    monkeypatch.delenv("RELIGION_DISABLE_LLM", raising=False)
    monkeypatch.delenv("RELIGION_CHAT_API_URL", raising=False)
    monkeypatch.setenv("RELIGION_LLM_PROVIDER", "gemma_gateway_proxy")
    monkeypatch.setenv("RELIGION_GEMMA_GATEWAY_URL", "https://gateway.example/api/gemma-gateway/v1/chat")
    monkeypatch.setenv("RELIGION_GEMMA_GATEWAY_TOKEN", "gateway-token")
    monkeypatch.setenv("RELIGION_ANSWER_MODEL", "gemma-4-26b-a4b-it")
    monkeypatch.setenv("RELIGION_GEMMA_GATEWAY_MAX_OUTPUT_TOKENS", "4096")
    requests = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps(
                {
                    "status": "ok",
                    "model": "gemma-4-26b-a4b-it",
                    "answer": "gateway beta6 answer",
                    "keyIndex": 4,
                    "keyFingerprint": "fingerprint",
                }
            ).encode()

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    client = beta6_module.default_llm_client_from_env()

    assert isinstance(client, beta6_module.GemmaGatewayLLMClient)
    assert client.complete(
        [
            {"role": "system", "content": "system rule"},
            {"role": "user", "content": "question"},
        ],
        model="gemma-4-26b-a4b-it",
        timeout_seconds=17,
    ) == "gateway beta6 answer"
    request, timeout = requests[0]
    assert request.full_url == "https://gateway.example/api/gemma-gateway/v1/chat"
    assert request.headers["Authorization"] == "Bearer gateway-token"
    assert timeout == 17
    payload = json.loads(request.data.decode())
    assert payload["model"] == "gemma-4-26b-a4b-it"
    assert payload["systemInstruction"] == "system rule"
    assert payload["messages"] == [{"role": "user", "content": "question"}]
    assert payload["maxOutputTokens"] == 4096
    trace = client.consume_last_call_trace()
    assert trace["provider"] == "gemma_gateway_proxy"
    assert trace["status"] == "completed"
    assert trace["keyIndex"] == 4


def test_default_llm_client_can_use_gemini_live_provider(monkeypatch, tmp_path):
    monkeypatch.delenv("RELIGION_LLM_DISABLED", raising=False)
    monkeypatch.delenv("RELIGION_DISABLE_LLM", raising=False)
    monkeypatch.delenv("RELIGION_CHAT_API_URL", raising=False)
    monkeypatch.setenv("RELIGION_LLM_PROVIDER", "gemini_live")
    monkeypatch.setenv("RELIGION_GEMINI_LIVE_SCRIPT_DIR", str(tmp_path))
    monkeypatch.setenv("RELIGION_GEMINI_LIVE_MODEL", "models/gemini-3.1-flash-live-preview")
    monkeypatch.setenv("RELIGION_GEMINI_LIVE_TIMEOUT_SECONDS", "17")
    monkeypatch.setenv("RELIGION_GEMINI_LIVE_MAX_ATTEMPTS", "3")
    monkeypatch.setenv("RELIGION_GEMINI_LIVE_THINKING_LEVEL", "high")
    calls = []

    def fake_live_text(prompt, *, script_dir, model, system, timeout, max_attempts, thinking_level=""):
        calls.append(
            {
                "prompt": prompt,
                "script_dir": script_dir,
                "model": model,
                "system": system,
                "timeout": timeout,
                "max_attempts": max_attempts,
                "thinking_level": thinking_level,
            }
        )
        return "live answer"

    monkeypatch.setattr(beta6_module, "_call_gemini_live_text", fake_live_text)

    client = beta6_module.default_llm_client_from_env()

    assert isinstance(client, beta6_module.GeminiLiveTextLLMClient)
    assert client.complete(
        [
            {"role": "system", "content": "system rule"},
            {"role": "user", "content": "question"},
        ],
        model="ignored-by-live",
        timeout_seconds=9,
    ) == "live answer"
    assert calls == [
        {
            "prompt": "SYSTEM:\nsystem rule\n\nUSER:\nquestion",
            "script_dir": tmp_path,
            "model": "models/gemini-3.1-flash-live-preview",
            "system": beta6_module.GEMINI_LIVE_TEXT_SYSTEM_INSTRUCTION,
            "timeout": 9,
            "max_attempts": 3,
            "thinking_level": "HIGH",
        }
    ]
def test_default_llm_client_keeps_beta6_on_direct_gemini_for_gateway_aliases(monkeypatch):
    monkeypatch.delenv("RELIGION_LLM_DISABLED", raising=False)
    monkeypatch.delenv("RELIGION_CHAT_API_URL", raising=False)
    monkeypatch.setenv("RELIGION_LLM_PROVIDER", "gemma_gateway")
    monkeypatch.setenv("RELIGION_GEMMA_GATEWAY_URL", "https://lawkey.example/chat")
    monkeypatch.setenv("RELIGION_GEMMA_GATEWAY_TOKEN", "gateway-token")
    monkeypatch.setattr(beta6_module, "_lawkey_gemini_keys_available", lambda: True)

    client = beta6_module.default_llm_client_from_env()

    assert isinstance(client, beta6_module.LawkeyGeminiLLMClient)
    assert client.provider == "lawkey_gemini_generate_content"


def test_default_llm_client_uses_public_gateway_only_when_explicit(monkeypatch):
    monkeypatch.delenv("RELIGION_LLM_DISABLED", raising=False)
    monkeypatch.delenv("RELIGION_CHAT_API_URL", raising=False)
    monkeypatch.setenv("RELIGION_LLM_PROVIDER", "public_gemma_gateway")
    monkeypatch.setenv("RELIGION_GEMMA_GATEWAY_URL", "https://lawkey.example/chat")
    monkeypatch.setenv("RELIGION_GEMMA_GATEWAY_TOKEN", "gateway-token")
    monkeypatch.setattr(beta6_module, "_lawkey_gemini_keys_available", lambda: True)

    client = beta6_module.default_llm_client_from_env()

    assert isinstance(client, beta6_module.LawkeyGemmaGatewayLLMClient)
    assert client.api_url == "https://lawkey.example/chat"


def test_default_llm_client_uses_mint_gateway_when_raw_gemini_keys_missing(monkeypatch):
    monkeypatch.delenv("RELIGION_LLM_DISABLED", raising=False)
    monkeypatch.delenv("RELIGION_CHAT_API_URL", raising=False)
    monkeypatch.setenv("RELIGION_LLM_PROVIDER", "gemma_gateway")
    monkeypatch.setenv("MINT_GEMINI_GATEWAY_BASE_URL", "http://mint.example")
    monkeypatch.setenv("MINT_GEMINI_GATEWAY_TOKEN", "gateway-token")
    monkeypatch.setattr(beta6_module, "_lawkey_gemini_keys_available", lambda: False)

    client = beta6_module.default_llm_client_from_env()

    assert isinstance(client, beta6_module.MintGeminiGatewayLLMClient)
    assert client.provider == "mint_gemini_gateway_generate_content"
    assert client.base_url == "http://mint.example"


def test_default_beta6_runtime_uses_lawkey_writer_for_islam_tcm_and_simli(tmp_path, monkeypatch):
    lawkey_client = getattr(beta6_module, "LawkeyGeminiLLMClient", None)
    assert lawkey_client is not None
    monkeypatch.delenv("RELIGION_LLM_DISABLED", raising=False)
    monkeypatch.delenv("RELIGION_CHAT_API_URL", raising=False)
    monkeypatch.delenv("RELIGION_LLM_PROVIDER", raising=False)
    monkeypatch.setattr(beta6_module, "_lawkey_gemini_keys_available", lambda: True)
    calls = []

    def fake_complete(self, messages, *, model=""):
        calls.append({"messages": messages, "model": model})
        prompt = "\n".join(message["content"] for message in messages)
        if "keyword generator" in messages[0]["content"]:
            return '{"keywords":["ولي","نكاح","甘草","妊娠","insomnia","anxiety"]}'
        if "source selector" in messages[0]["content"]:
            if "doc-wali-hanafi" in prompt:
                return "selected because it directly discusses wali.\n<selection>\ndoc-wali-hanafi\n</selection>"
            if "doc-pregnancy-contra" in prompt:
                return "selected for contraindication safety.\n<selection>\ndoc-pregnancy-contra\ndoc-gamcho-classic\n</selection>"
            if "doc-psych-2" in prompt:
                return "selected for sleep and anxiety evidence.\n<selection>\ndoc-psych-2\ndoc-psych-1\n</selection>"
            return "<selection>\n<none/>\n</selection>"
        if "chunk-level claim-card analyzer" in messages[0]["content"]:
            source_id_match = re.search(r"source_id:\s*([^\s]+)", prompt)
            source_id = source_id_match.group(1) if source_id_match else "doc-unknown"
            quote_by_id = {
                "doc-wali-hanafi": "Hanafi school discussion mentions wali and marriage contract conditions.",
                "doc-pregnancy-contra": "妊娠 pregnancy 임신 禁忌 contraindication 금기 본초 약재 안전 확인.",
                "doc-psych-2": "Sleep disruption, insomnia and mood symptoms.",
            }
            quote = quote_by_id.get(source_id, "Anxiety symptoms, panic, worry and functional impairment.")
            return json.dumps(
                {
                    "claim_cards": [
                        {
                            "source_label": "S1",
                            "source_id": source_id,
                            "chunk_id": "question_selected_manual_0001",
                            "claim_axis": f"axis {source_id}",
                            "stance": "support",
                            "context_summary": f"context {source_id}",
                            "claim_summary": f"summary {source_id}",
                            "quote": quote,
                        }
                    ]
                },
                ensure_ascii=False,
            )
        return "LAWKEY GEMINI WRITER"

    monkeypatch.setattr(lawkey_client, "complete", fake_complete)
    islam_db = tmp_path / "islam.sqlite3"
    tcm_db = tmp_path / "tcm.sqlite3"
    simli_db = tmp_path / "psych.sqlite3"
    _make_islam_school_db(islam_db)
    _make_tcm_domain_db(tcm_db)
    _make_documents_db(simli_db)
    runtime = Beta6JobManager(
        {"islam": _profile(islam_db), "tcm": _tcm_profile(tcm_db), "simli": _simli_profile(simli_db)},
        runs_root=tmp_path / "runs",
    )

    scenarios = [
        ("islam", "결혼할 때 보호자가 필요한가 학파별로 알려줘", "en"),
        ("tcm", "감초를 임신 중 써도 되는지 본초 금기 근거로 정리해줘", "en"),
        ("simli", "요즘 잠이 안 오고 계속 불안합니다", "ko"),
    ]
    for product, query, language in scenarios:
        result = runtime.answer_sync(product=product, query=query, language=language, limit=3)

        assert result["llmUsed"] is True
        assert result["selector"]["status"] == "completed"
        assert result["selector"]["mode"] == "llm_keyword_search_and_selector"
        assert result["selector"]["provider"] == "lawkey_gemini_generate_content"
        assert result["selector"]["model"] == "gemma-4-26b-a4b-it"
        assert result["selector"]["selectionSource"] == "gemma4_llm_selector"
        assert result["selector"]["keywordSource"] == "gemma4_keyword_generation"
        assert result["writer"]["status"] == "completed"
        assert result["writer"]["mode"] == "llm_writer"
        assert result["writer"]["provider"] == "lawkey_gemini_generate_content"
        assert result["writer"]["model"] == "gemma-4-26b-a4b-it"
        assert result["answerReadiness"] == "final_answer"
        assert result["answer"].startswith("LAWKEY GEMINI WRITER")
        assert result["beta6"]["selectorProvider"] == "lawkey_gemini_generate_content"
        assert result["beta6"]["selectionSource"] == "gemma4_llm_selector"

    assert len(calls) == 18
    assert sum(1 for call in calls if "chunk-level claim-card analyzer" in call["messages"][0]["content"]) == 3
    assert sum(1 for call in calls if "answer planner" in call["messages"][0]["content"]) == 3


def test_parse_selection_response_accepts_file_id_prefixed_lines():
    selected, reasoning = parse_selection_response(
        "선정 이유입니다.\n<selection>\nfile_id: apa:dsm5:0d874630d36ebca270fc478d\n"
        "- file_id: guidelines:clinical:102d6d4f987d04b89100fec5\n"
        "s2:psych:b7973a722a809cc1efa4dd37\n</selection>"
    )

    assert reasoning.startswith("선정 이유")
    assert selected == [
        "apa:dsm5:0d874630d36ebca270fc478d",
        "guidelines:clinical:102d6d4f987d04b89100fec5",
        "s2:psych:b7973a722a809cc1efa4dd37",
    ]


def test_parse_selection_response_resolves_bracketed_source_labels():
    selected, reasoning = parse_selection_response(
        "candidate label selection\n<selection>\n[S1]\n- [S3]\n</selection>"
    )
    rows = [_result("doc-a", "alpha"), _result("doc-b", "beta"), _result("doc-c", "gamma")]
    resolved = beta6_module.resolve_selected_rows(rows, selected, limit=10)

    assert reasoning == "candidate label selection"
    assert selected == ["S1", "S3"]
    assert [row.canonical_id for row in resolved] == ["doc-a", "doc-c"]


def test_parse_selection_response_extracts_default_off_selector_ledger():
    selected, reasoning, ledger = beta6_module.parse_selection_response_with_ledger(
        'reason\n{"file_id":"doc-a","context_summary":"문맥 A","claim_summary":"요약 A",'
        '"quote_candidate":"직접 인용 A","stance":"support"}\n'
        "<selection>\ndoc-a\n</selection>"
    )

    assert selected == ["doc-a"]
    assert reasoning == "reason"
    assert ledger == [
        {
            "fileId": "doc-a",
            "contextSummary": "문맥 A",
            "claimSummary": "요약 A",
            "quoteCandidate": "직접 인용 A",
            "stance": "support",
            "sourceRole": "",
        }
    ]


def test_tcm_selector_empty_selection_uses_option_matrix_local_fallback_when_enabled(tmp_path, monkeypatch):
    class EmptySelectorLLMClient:
        def complete(self, messages, *, model="", timeout_seconds=None):
            return "no useful source\n<selection>\n<none/>\n</selection>"

    query = """36. 40M] 남자가 SHO] 자주 나온다며 병원에 왔다. 치방은?
0) 균기환
2 사역산
@3) 여성탕
@® 이진탕
© 청담환"""
    candidates = [
        _result("doc-gyungi", "均氣丸 균기환 관련 처방 근거", source_kind="classic_authoritative"),
        _result("doc-sayeok", "四逆散 사역산 관련 처방 근거", source_kind="classic_authoritative"),
        _result("doc-yeoseong", "여성탕 관련 처방 근거", source_kind="classic_authoritative"),
        _result("doc-ijin", "二陳湯 이진탕 관련 처방 근거", source_kind="classic_authoritative"),
        _result("doc-cheongdam", "청담환 관련 처방 근거", source_kind="classic_authoritative"),
    ]

    monkeypatch.setenv("RELIGION_MCQ_HEURISTICS_ENABLED", "1")
    rows, ids, reasoning, meta = beta6_module.select_rows_with_beta6_selector(
        _tcm_profile(tmp_path / "unused.sqlite3"),
        query,
        "ko",
        candidates,
        limit=5,
        llm_client=EmptySelectorLLMClient(),
        model="gemma",
        cache_root=tmp_path / "selector-cache",
    )

    assert [row.canonical_id for row in rows] == [
        "doc-gyungi",
        "doc-sayeok",
        "doc-yeoseong",
        "doc-ijin",
        "doc-cheongdam",
    ]
    assert ids == [row.canonical_id for row in rows]
    assert "option-matrix local recovery" in reasoning
    assert meta["selectorLocalRecoveryCount"] == 1


def test_tcm_selector_empty_selection_respects_disabled_mcq_heuristics(tmp_path, monkeypatch):
    class EmptySelectorLLMClient:
        def complete(self, messages, *, model="", timeout_seconds=None):
            return "no useful source\n<selection>\n<none/>\n</selection>"

    query = """36. 40M] 남자가 SHO] 자주 나온다며 병원에 왔다. 치방은?
0) 균기환
2 사역산
@3) 여성탕
@® 이진탕
© 청담환"""
    candidates = [
        _result("doc-gyungi", "均氣丸 균기환 관련 처방 근거", source_kind="classic_authoritative"),
        _result("doc-sayeok", "四逆散 사역산 관련 처방 근거", source_kind="classic_authoritative"),
        _result("doc-yeoseong", "여성탕 관련 처방 근거", source_kind="classic_authoritative"),
    ]

    monkeypatch.setenv("RELIGION_MCQ_HEURISTICS_ENABLED", "0")
    rows, ids, reasoning, meta = beta6_module.select_rows_with_beta6_selector(
        _tcm_profile(tmp_path / "unused.sqlite3"),
        query,
        "ko",
        candidates,
        limit=5,
        llm_client=EmptySelectorLLMClient(),
        model="gemma",
        cache_root=tmp_path / "selector-cache",
    )

    assert rows == []
    assert ids == []
    assert "option-matrix local recovery" not in reasoning
    assert meta["selectorLocalRecoveryCount"] == 0


def test_tcm_selector_empty_selection_does_not_use_option_matrix_by_default(tmp_path, monkeypatch):
    class EmptySelectorLLMClient:
        def complete(self, messages, *, model="", timeout_seconds=None):
            return "no useful source\n<selection>\n<none/>\n</selection>"

    query = """36. 40M] 남자가 SHO] 자주 나온다며 병원에 왔다. 치방은?
0) 균기환
2 사역산
@3) 여성탕
@® 이진탕
© 청담환"""
    candidates = [
        _result("doc-gyungi", "均氣丸 균기환 관련 처방 근거", source_kind="classic_authoritative"),
        _result("doc-sayeok", "四逆散 사역산 관련 처방 근거", source_kind="classic_authoritative"),
        _result("doc-yeoseong", "여성탕 관련 처방 근거", source_kind="classic_authoritative"),
    ]

    monkeypatch.delenv("RELIGION_MCQ_HEURISTICS_ENABLED", raising=False)
    rows, ids, reasoning, meta = beta6_module.select_rows_with_beta6_selector(
        _tcm_profile(tmp_path / "unused.sqlite3"),
        query,
        "ko",
        candidates,
        limit=5,
        llm_client=EmptySelectorLLMClient(),
        model="gemma",
        cache_root=tmp_path / "selector-cache",
    )

    assert rows == []
    assert ids == []
    assert "option-matrix local recovery" not in reasoning
    assert meta["selectorLocalRecoveryCount"] == 0


def test_catholic_exact_citation_selector_empty_selection_uses_context_local_fallback_by_default(
    tmp_path,
    monkeypatch,
):
    class EmptySelectorLLMClient:
        def complete(self, messages, *, model="", timeout_seconds=None):
            return "정답: 4\n\n창 42:21의 아우는 요셉입니다."

    monkeypatch.delenv("RELIGION_MCQ_HEURISTICS_ENABLED", raising=False)
    profile = ProductProfile(
        key="catholic",
        name="Catholic Test",
        db_path=tmp_path / "unused.sqlite3",
        db_shape="precedents",
        languages=("ko", "en"),
        default_language="ko",
        theme="",
        safety_notice="",
    )
    query = "창 42:21에서 아우는 누구인가?\n\n① 레위\n② 베냐민\n③ 르우벤\n④ 요셉"
    candidates = [
        SearchResult(
            canonical_id="gen-42-21",
            title="Genesis",
            citation="Gen 42:21",
            authority_body="fixture",
            source_date="",
            case_name="Genesis",
            case_type="scripture_window",
            full_text="we have sinned against our brother",
            source_kind="scripture",
        ),
        SearchResult(
            canonical_id="gen-42-6",
            title="Genesis",
            citation="Gen 42:6",
            authority_body="fixture",
            source_date="",
            case_name="Genesis",
            case_type="scripture_window",
            full_text="Joseph was governor and his brothers bowed before him.",
            source_kind="scripture",
        ),
    ]

    rows, ids, reasoning, meta = beta6_module.select_rows_with_beta6_selector(
        profile,
        query,
        "ko",
        candidates,
        limit=2,
        llm_client=EmptySelectorLLMClient(),
        model="gemma",
        cache_root=tmp_path / "selector-cache",
    )

    assert [row.canonical_id for row in rows] == ["gen-42-21", "gen-42-6"]
    assert ids == ["gen-42-21", "gen-42-6"]
    assert "local recovery" in reasoning
    assert meta["selectorLocalRecoveryCount"] == 1


def test_catholic_exact_citation_local_recovery_keeps_source_writer_path(tmp_path):
    profile = ProductProfile(
        key="catholic",
        name="Catholic Test",
        db_path=tmp_path / "unused.sqlite3",
        db_shape="precedents",
        languages=("ko", "en"),
        default_language="ko",
        theme="",
        safety_notice="",
    )
    query = "창 42:21에서 아우는 누구인가?\n\n① 레위\n② 베냐민\n③ 르우벤\n④ 요셉"

    use_direct = beta6_module._should_use_direct_writer_after_empty_selector(
        profile,
        query,
        {
            "status": "fallback_selector_error",
            "selectorLocalRecoveryCount": 1,
            "selectedIds": ["gen-42-21", "gen-42-6"],
        },
    )

    assert use_direct is False


def test_tcm_empty_selector_writer_uses_uncontaminated_direct_prompt(tmp_path):
    class EmptySelectorCapturingWriterLLMClient:
        def __init__(self):
            self.writer_prompt = ""

        def complete(self, messages, *, model="", timeout_seconds=None):
            prompt = "\n".join(message["content"] for message in messages)
            system = messages[0]["content"]
            if "keyword generator" in system:
                return '{"keywords":["sharedterm","wrongsource"]}'
            if "source selector" in system:
                return "no useful source\n<selection>\n<none/>\n</selection>"
            if "claim-card analyzer" in system:
                return '{"claim_cards":[]}'
            if "answer planner" in system:
                return json.dumps(
                    {
                        "body_claim_ids": [],
                        "coverage_required_claim_ids": [],
                        "answer_outline": ["answer directly because no reliable source was selected"],
                        "citation_policy": "do not cite unselected source candidates",
                    }
                )
            self.writer_prompt = prompt
            return "정답: 1"

    db_path = tmp_path / "tcm.sqlite3"
    _make_tcm_domain_db(db_path)
    fake = EmptySelectorCapturingWriterLLMClient()
    runtime = Beta6JobManager({"tcm": _tcm_profile(db_path)}, runs_root=tmp_path / "runs", llm_client=fake)
    query = """1. 다음 중 한의학 이론에 관한 설명으로 옳은 것은?
1) 정답 후보
2) 오답 후보
3) 다른 오답
4) 또 다른 오답"""

    result = runtime.answer_sync(product="tcm", query=query, language="ko", limit=4, analysis_mode="fast")

    assert result["selector"]["status"] == "fallback_no_selection"
    assert result["selector"]["selectorLocalRecoveryCount"] == 0
    assert result["writer"]["mode"] == "llm_writer_direct_after_empty_selector"
    assert result["writer"]["selectedCount"] == 0
    assert result["beta6"]["selectedCount"] == 0
    assert result["sources"] == []
    assert result["beta6SelectedRecords"] == []
    assert "[TCM MCQ STRUCTURE]" in fake.writer_prompt
    assert "[selected source index]" not in fake.writer_prompt
    assert "Selected beta6 records" not in fake.writer_prompt
    assert "wrongsource" not in fake.writer_prompt


def test_direct_mcq_prompt_uses_answer_only_instruction_instead_of_cited_writer_policy(tmp_path):
    product = _tcm_profile(tmp_path / "unused.sqlite3")
    query = """1. 치방은?
1) 목향순기산
2) 목향파기산
3) 소자강기탕
4) 익위승양탕"""

    prompt = "\n".join(message["content"] for message in beta6_module.build_beta6_direct_messages(product, query, "ko"))

    assert "첫 줄" in prompt
    assert "정답:" in prompt
    assert "Return a structured cited answer" not in prompt
    assert "Every substantive paragraph should cite" not in prompt


def test_tcm_direct_writer_provider_fallback_does_not_reintroduce_unselected_sources(tmp_path):
    class EmptySelectorFailingWriterLLMClient:
        def complete(self, messages, *, model="", timeout_seconds=None):
            system = messages[0]["content"]
            if "keyword generator" in system:
                return '{"keywords":["wrongsource"]}'
            if "source selector" in system:
                return "no useful source\n<selection>\n<none/>\n</selection>"
            if "claim-card analyzer" in system:
                return '{"claim_cards":[]}'
            if "answer planner" in system:
                return json.dumps(
                    {
                        "body_claim_ids": [],
                        "coverage_required_claim_ids": [],
                        "answer_outline": ["answer directly because no reliable source was selected"],
                        "citation_policy": "do not cite unselected source candidates",
                    }
                )
            raise RuntimeError("writer offline")

    db_path = tmp_path / "tcm.sqlite3"
    _make_tcm_domain_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO precedents VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            "doc-wrongsource",
            "tcm-kmm/tcm/tcm-clinical/case_record",
            "cases/wrongsource",
            "wrongsource retrieval candidate",
            "wrongsource",
            "case collection",
            "",
            "wrongsource",
            "case_record_unit",
            "[META]\nsource_kind: case_record\n\nwrongsource should never appear in direct fallback answers.",
            "hash-wrongsource",
        ),
    )
    conn.execute(
        "INSERT INTO precedents_fts(canonical_id, full_text) VALUES (?, ?)",
        ("doc-wrongsource", "wrongsource should never appear in direct fallback answers."),
    )
    conn.commit()
    conn.close()
    fake = EmptySelectorFailingWriterLLMClient()
    runtime = Beta6JobManager({"tcm": _tcm_profile(db_path)}, runs_root=tmp_path / "runs", llm_client=fake)
    query = """1. 다음 중 한의학 이론에 관한 설명으로 옳은 것은?
1) 정답 후보
2) 오답 후보
3) 다른 오답
4) 또 다른 오답"""

    result = runtime.answer_sync(product="tcm", query=query, language="ko", limit=4, analysis_mode="fast")

    assert result["writer"]["mode"] == "deterministic_writer_fallback"
    assert result["writer"]["selectedCount"] == 0
    assert "wrongsource" not in result["answerMarkdown"]
    assert "Selected beta6 records" not in result["answerMarkdown"]


def test_tcm_direct_writer_provider_fallback_ignores_selector_local_recovery_sources(tmp_path, monkeypatch):
    class TimeoutSelectorFailingWriterLLMClient:
        def complete(self, messages, *, model="", timeout_seconds=None):
            system = messages[0]["content"]
            if "keyword generator" in system:
                return '{"keywords":["wrongsource"]}'
            if "source selector" in system:
                raise TimeoutError("selector timeout")
            if "claim-card analyzer" in system:
                return '{"claim_cards":[]}'
            if "answer planner" in system:
                return json.dumps(
                    {
                        "body_claim_ids": [],
                        "coverage_required_claim_ids": [],
                        "answer_outline": ["answer directly because selector recovered locally"],
                        "citation_policy": "do not cite unselected source candidates",
                    }
                )
            raise RuntimeError("writer offline")

    db_path = tmp_path / "tcm.sqlite3"
    _make_tcm_domain_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO precedents VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            "doc-wrongsource",
            "tcm-kmm/tcm/tcm-classic/classic_authoritative",
            "books/wrongsource",
            "wrongsource option source",
            "wrongsource",
            "classic",
            "",
            "wrongsource",
            "classic_authoritative_unit",
            "[META]\nsource_kind: classic_authoritative\n\nwrongsource option evidence.",
            "hash-wrongsource",
        ),
    )
    conn.execute(
        "INSERT INTO precedents_fts(canonical_id, full_text) VALUES (?, ?)",
        ("doc-wrongsource", "wrongsource option evidence."),
    )
    conn.commit()
    conn.close()
    monkeypatch.setenv("RELIGION_MCQ_HEURISTICS_ENABLED", "1")
    runtime = Beta6JobManager(
        {"tcm": _tcm_profile(db_path)},
        runs_root=tmp_path / "runs",
        llm_client=TimeoutSelectorFailingWriterLLMClient(),
    )
    query = """1. 다음 중 옳은 것은?
1) 정답 후보
2) wrongsource
3) 다른 오답
4) 또 다른 오답"""

    result = runtime.answer_sync(product="tcm", query=query, language="ko", limit=4, analysis_mode="fast")

    assert result["selector"]["status"] == "fallback_selector_error"
    assert result["selector"]["selectorLocalRecoveryCount"] >= 1
    assert result["writer"]["selectedCount"] == 0
    assert "wrongsource option evidence" not in result["answerMarkdown"]
    assert "fallback_score" not in result["answerMarkdown"]


def test_tcm_writer_timeout_retries_with_direct_mcq_prompt_without_sources(tmp_path):
    class SourceWriterTimeoutThenDirectLLMClient:
        def __init__(self):
            self.direct_prompt = ""

        def complete(self, messages, *, model="", timeout_seconds=None):
            system = messages[0]["content"] if messages and messages[0].get("role") == "system" else ""
            prompt = "\n".join(message["content"] for message in messages)
            if "keyword generator" in system:
                return '{"keywords":["감초"]}'
            if "source selector" in system:
                return "selected\n<selection>\ndoc-gamcho-classic\n</selection>"
            if "claim-card analyzer" in system:
                return '{"claim_cards":[]}'
            if "answer planner" in system:
                return json.dumps(
                    {
                        "body_claim_ids": [],
                        "coverage_required_claim_ids": [],
                        "answer_outline": ["answer directly if source-grounded writer fails"],
                        "citation_policy": "do not cite sources in fallback direct answer",
                    }
                )
            if "source-grounded answer engine" in system:
                raise TimeoutError("writer timed out")
            if "direct answer engine" in system:
                self.direct_prompt = prompt
                return "정답: 3"
            return "unused"

    db_path = tmp_path / "tcm.sqlite3"
    _make_tcm_domain_db(db_path)
    fake = SourceWriterTimeoutThenDirectLLMClient()
    runtime = Beta6JobManager({"tcm": _tcm_profile(db_path)}, runs_root=tmp_path / "runs", llm_client=fake)
    query = """1. 다음 중 옳은 것은?
1) 보기A
2) 보기B
3) 보기C
4) 보기D"""

    result = runtime.answer_sync(product="tcm", query=query, language="ko", limit=4, analysis_mode="fast")

    assert result["writer"]["status"] == "completed"
    assert result["writer"]["mode"] == "llm_writer_direct_after_writer_error"
    assert result["writer"]["selectedCount"] == 0
    assert result["answerMarkdown"].startswith("정답: 3")
    assert "[TCM MCQ STRUCTURE]" in fake.direct_prompt
    assert "[selected source index]" not in fake.direct_prompt


def test_tcm_deterministic_writer_fallback_scores_selected_record_fields_when_enabled(tmp_path, monkeypatch):
    query = """36. 40M] 남자가 SHO] 자주 나온다며 병원에 왔다. 치방은?
0) 균기환
2 사역산
@3) 여성탕
@® 이진탕
© 청담환"""
    selected_records = [
        {
            "file_id": "s1",
            "document_title": "처방 근거",
            "anchor_text": "간기울결로 흉협고만이 있으면 사역산을 쓴다.",
            "metadata": {"sourceKind": "formulary", "school": "korean-formulary"},
        },
        {
            "file_id": "s2",
            "document_title": "다른 근거",
            "extracted_text": "이진탕은 담음이 뚜렷할 때 고려한다.",
            "metadata": {"sourceKind": "classic_canon", "school": "korean-classic"},
        },
    ]
    claim_cards = [
        {
            "sourceId": "s1",
            "claimSummary": "사역산은 관련 증상에 대한 처방 근거로 제시된다.",
            "quote": "사역산",
            "sourceKind": "formulary",
        }
    ]

    monkeypatch.setenv("RELIGION_MCQ_HEURISTICS_ENABLED", "1")
    answer = beta6_module._deterministic_writer_fallback_answer(
        _tcm_profile(tmp_path / "unused.sqlite3"),
        query,
        selected_records,
        claim_cards,
        language="ko",
        error="timeout",
    )

    assert answer.startswith("정답: 2) 사역산")
    assert "fallback_score:" in answer


def test_tcm_deterministic_writer_fallback_respects_disabled_mcq_heuristics(tmp_path, monkeypatch):
    query = """36. 40M] 남자가 SHO] 자주 나온다며 병원에 왔다. 치방은?
0) 균기환
2 사역산
@3) 여성탕
@® 이진탕
© 청담환"""
    selected_records = [
        {
            "file_id": "s1",
            "document_title": "처방 근거",
            "anchor_text": "간기울결로 흉협고만이 있으면 사역산을 쓴다.",
            "metadata": {"sourceKind": "formulary", "school": "korean-formulary"},
        }
    ]

    monkeypatch.setenv("RELIGION_MCQ_HEURISTICS_ENABLED", "0")
    answer = beta6_module._deterministic_writer_fallback_answer(
        _tcm_profile(tmp_path / "unused.sqlite3"),
        query,
        selected_records,
        [{"sourceId": "s1", "claimSummary": "사역산 근거", "quote": "사역산"}],
        language="ko",
        error="timeout",
    )

    assert not answer.startswith("정답:")
    assert "fallback_score:" not in answer


def test_tcm_mcq_prompt_block_is_enabled_by_default_for_source_grounded_prompts(tmp_path, monkeypatch):
    profile = _tcm_profile(tmp_path / "unused.sqlite3")
    query = """1. 다음 치방은?
0 합개환
@ 형소탕
3 소속명탕
0) 복령보심탕
09) 향성파적환"""
    candidates = [_result("doc-a", "형소탕 관련 근거", source_kind="classic_authoritative")]
    selected_records = [{"file_id": "doc-a", "document_title": "문헌", "extracted_text": "형소탕 관련 근거"}]

    monkeypatch.delenv("RELIGION_MCQ_HEURISTICS_ENABLED", raising=False)
    monkeypatch.delenv("RELIGION_MCQ_STRUCTURE_ENABLED", raising=False)
    selector_prompt = "\n".join(
        message["content"]
        for message in beta6_module.build_beta6_selection_messages(profile, query, "ko", candidates, limit=5)
    )
    writer_prompt = "\n".join(
        message["content"]
        for message in beta6_module.build_beta6_messages(profile, query, "ko", selected_records)
    )
    direct_prompt = "\n".join(
        message["content"] for message in beta6_module.build_beta6_direct_messages(profile, query, "ko")
    )

    assert "[TCM MCQ STRUCTURE]" in selector_prompt
    assert "[TCM MCQ STRUCTURE]" in writer_prompt
    assert "[TCM MCQ STRUCTURE]" in direct_prompt


def test_tcm_mcq_prompt_block_can_be_disabled_with_structure_flag(tmp_path, monkeypatch):
    profile = _tcm_profile(tmp_path / "unused.sqlite3")
    query = """1. 다음 치방은?
0 합개환
@ 형소탕
3 소속명탕
0) 복령보심탕
09) 향성파적환"""
    selected_records = [{"file_id": "doc-a", "document_title": "문헌", "extracted_text": "형소탕 관련 근거"}]

    monkeypatch.setenv("RELIGION_MCQ_STRUCTURE_ENABLED", "0")
    prompt = "\n".join(message["content"] for message in beta6_module.build_beta6_messages(profile, query, "ko", selected_records))

    assert "[TCM MCQ STRUCTURE]" not in prompt


def test_tcm_direct_mcq_prompt_uses_structure_block_without_sources_by_default(tmp_path, monkeypatch):
    profile = _tcm_profile(tmp_path / "unused.sqlite3")
    query = """1. 다음 치방은?
D 귀비탕
@ 오미자탕
@ 보혈안신탕
® 육미지황환
© 과루해백반하탕

위 한의사 국가시험 객관식 문제의 정답 번호를 1~5 중 하나로 고르세요."""

    monkeypatch.delenv("RELIGION_MCQ_HEURISTICS_ENABLED", raising=False)
    prompt = "\n".join(message["content"] for message in beta6_module.build_beta6_direct_messages(profile, query, "ko"))

    assert "User question: " in prompt
    assert "[TCM MCQ STRUCTURE]" in prompt
    assert "1) 귀비탕" in prompt
    assert "No reliable source records were selected" not in prompt
    assert "[selected source index]" not in prompt


def test_generic_mcq_keyword_prompt_uses_search_stem_not_options():
    product = ProductProfile(
        key="islam",
        name="Hikmah AI",
        db_path=Path("unused.sqlite3"),
        db_shape="precedents",
        languages=("ko",),
        default_language="ko",
        theme="islam",
        safety_notice="notice",
    )
    query = """006. 이유는?

A. 자카트 계산
B. 고객의 기밀 유지
C. 상업적 위험
D. 기업 지배구조"""

    prompt = "\n".join(
        message["content"]
        for message in beta6_module.build_beta6_keyword_messages(product, query, "ko", keyword_count=6)
    )

    assert "Retrieval question:\n이유는?" in prompt
    assert "006. 이유는?" not in prompt
    assert "자카트 계산" not in prompt
    assert "고객의 기밀" not in prompt


def test_generic_mcq_low_candidate_coverage_records_meta_but_still_uses_selector(tmp_path, monkeypatch):
    class LowCoverageMcqLLMClient:
        def __init__(self):
            self.systems = []

        def complete(self, messages, *, model="", timeout_seconds=None):
            system = messages[0]["content"]
            prompt = "\n".join(message["content"] for message in messages)
            self.systems.append(system)
            if "keyword generator" in system:
                return '{"keywords":["sharedterm"]}'
            if "source selector" in system:
                assert "doc-000" in prompt
                return "<selection>\ndoc-000\n</selection>"
            if "chunk-level claim-card analyzer" in system:
                return json.dumps(
                    {
                        "claim_cards": [
                            {
                                "source_label": "S1",
                                "source_id": "doc-000",
                                "chunk_id": "question_selected_manual_0001",
                                "claim_axis": "low coverage candidate",
                                "stance": "support",
                                "context_summary": "low surface overlap but candidate may still be relevant",
                                "claim_summary": "sharedterm evidence can be selected despite low surface coverage",
                                "quote": "sharedterm evidence principle context argument source position record claim rule 000",
                            }
                        ]
                    }
                )
            if "answer planner" in system:
                return json.dumps(
                    {
                        "body_claim_ids": ["C1"],
                        "coverage_required_claim_ids": ["C1"],
                        "answer_outline": ["use selected low-coverage candidate"],
                        "citation_policy": "cite selected claim ids",
                    }
                )
            if "source-grounded answer engine" in system:
                return "Answer: B [C1]"
            return "unused"

    db_path = tmp_path / "islam.sqlite3"
    _make_many_precedents_db(db_path, count=30)
    fake = LowCoverageMcqLLMClient()
    monkeypatch.setenv("RELIGION_BETA6_KEYWORD_ROUNDS", "1")
    runtime = Beta6JobManager({"islam": _profile(db_path)}, runs_root=tmp_path / "runs", llm_client=fake)
    query = """Which CISI Islamic finance screening threshold is correct?

A. 5%
B. 30%
C. 70%
D. 90%

Choose exactly one option ID."""

    result = runtime.answer_sync(product="islam", query=query, language="en", limit=10, analysis_mode="fast")

    assert result["selector"]["status"] == "completed"
    assert result["selector"]["candidateCoverage"]["matchedTermRatio"] < 0.35
    assert result["selector"]["candidateCoverage"]["lowCoverage"] is True
    assert result["writer"]["mode"] == "llm_writer"
    assert result["beta6"]["selectedCount"] > 0
    assert "Answer: B" in result["answer"]
    assert any("source selector" in system for system in fake.systems)


def test_generic_mcq_low_candidate_coverage_hard_gate_can_skip_selector(tmp_path, monkeypatch):
    class LowCoverageMcqLLMClient:
        def __init__(self):
            self.systems = []

        def complete(self, messages, *, model="", timeout_seconds=None):
            system = messages[0]["content"]
            self.systems.append(system)
            if "keyword generator" in system:
                return '{"keywords":["sharedterm"]}'
            if "source selector" in system:
                raise AssertionError("hard low-coverage gate should not call selector")
            if "answer planner" in system:
                return json.dumps(
                    {
                        "body_claim_ids": [],
                        "coverage_required_claim_ids": [],
                        "answer_outline": ["answer directly because retrieved coverage is weak"],
                        "citation_policy": "do not cite weak sources",
                    }
                )
            if "direct answer engine" in system:
                return "Answer: B\nRetrieved corpus coverage was weak, so answer directly."
            return "unused"

    db_path = tmp_path / "islam.sqlite3"
    _make_many_precedents_db(db_path, count=30)
    fake = LowCoverageMcqLLMClient()
    monkeypatch.setenv("RELIGION_BETA6_KEYWORD_ROUNDS", "1")
    monkeypatch.setenv("RELIGION_MCQ_LOW_COVERAGE_HARD_GATE_ENABLED", "1")
    runtime = Beta6JobManager({"islam": _profile(db_path)}, runs_root=tmp_path / "runs", llm_client=fake)
    query = """Which CISI Islamic finance screening threshold is correct?

A. 5%
B. 30%
C. 70%
D. 90%

Choose exactly one option ID."""

    result = runtime.answer_sync(product="islam", query=query, language="en", limit=10, analysis_mode="fast")

    assert result["selector"]["status"] == "fallback_low_coverage"
    assert result["selector"]["selectionSource"] == "direct_after_low_candidate_coverage"
    assert result["selector"]["candidateCoverage"]["matchedTermRatio"] < 0.35
    assert result["writer"]["mode"] == "llm_writer_direct_after_empty_selector"
    assert result["beta6"]["selectedCount"] == 0
    assert "Answer: B" in result["answer"]
    assert not any("source selector" in system for system in fake.systems)


def test_generic_mcq_sufficient_candidate_coverage_still_uses_selector(tmp_path, monkeypatch):
    class CoveredMcqLLMClient:
        def __init__(self):
            self.systems = []

        def complete(self, messages, *, model="", timeout_seconds=None):
            system = messages[0]["content"]
            prompt = "\n".join(message["content"] for message in messages)
            self.systems.append(system)
            if "keyword generator" in system:
                return '{"keywords":["finance","screening","threshold"]}'
            if "source selector" in system:
                assert "doc-covered" in prompt
                return "<selection>\ndoc-covered\n</selection>"
            if "chunk-level claim-card analyzer" in system:
                return json.dumps(
                    {
                        "claim_cards": [
                            {
                                "source_label": "S1",
                                "source_id": "doc-covered",
                                "chunk_id": "question_selected_manual_0001",
                                "claim_axis": "screening threshold",
                                "stance": "support",
                                "context_summary": "finance screening context",
                                "claim_summary": "finance screening threshold source",
                                "quote": "CISI Islamic finance screening threshold evidence.",
                            }
                        ]
                    }
                )
            if "answer planner" in system:
                return json.dumps(
                    {
                        "body_claim_ids": ["C1"],
                        "coverage_required_claim_ids": ["C1"],
                        "answer_outline": ["use selected finance screening source"],
                        "citation_policy": "cite selected claim ids",
                    }
                )
            if "source-grounded answer engine" in system:
                return "Answer: B [C1]"
            return "unused"

    db_path = tmp_path / "islam.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE precedents (
          canonical_id TEXT PRIMARY KEY,
          source_dataset TEXT,
          source_path TEXT,
          title TEXT,
          case_number TEXT,
          court TEXT,
          decision_date TEXT,
          case_name TEXT,
          case_type TEXT,
          full_text TEXT NOT NULL,
          text_hash TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE precedents_fts USING fts5(
          canonical_id UNINDEXED,
          full_text,
          tokenize='unicode61'
        );
        """
    )
    full_text = (
        "[META]\nsource_kind: fiqh\n\n"
        "CISI Islamic finance screening threshold market capitalization ratio evidence. "
        "The finance screening threshold discussion directly covers the exam stem."
    )
    conn.execute(
        "INSERT INTO precedents VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            "doc-covered",
            "islam/finance/fiqh",
            "finance/screening",
            "Islamic finance screening threshold",
            "Finance screening",
            "fixture",
            "",
            "screening threshold",
            "fiqh_unit",
            full_text,
            "hash-covered",
        ),
    )
    conn.execute("INSERT INTO precedents_fts(canonical_id, full_text) VALUES (?, ?)", ("doc-covered", full_text))
    conn.commit()
    conn.close()
    fake = CoveredMcqLLMClient()
    monkeypatch.setenv("RELIGION_BETA6_KEYWORD_ROUNDS", "1")
    runtime = Beta6JobManager({"islam": _profile(db_path)}, runs_root=tmp_path / "runs", llm_client=fake)
    query = """Which CISI Islamic finance screening threshold is correct?

A. 5%
B. 30%
C. 70%
D. 90%

Choose exactly one option ID."""

    result = runtime.answer_sync(product="islam", query=query, language="en", limit=5, analysis_mode="fast")

    assert result["selector"]["status"] == "completed"
    assert result["selector"]["candidateCoverage"]["lowCoverage"] is False
    assert result["writer"]["mode"] == "llm_writer"
    assert result["beta6"]["selectedCount"] == 1
    assert any("source selector" in system for system in fake.systems)


def test_generic_mcq_candidate_coverage_ignores_prompt_scaffold_terms(tmp_path):
    product = _profile(tmp_path / "unused.sqlite3")
    query = """024. 이슬람법의 계약에 적용되는 일반 원칙은 다음과 같습니다.

A. 행동은 결과로 판단된다
B. 허용되는 거래는 피크흐의 고전 텍스트에 명시된 거래로 제한됩니다
C. 특정 거래가 허용된다는 증거를 확보하는 것이 항상 필요합니다
D. 책임은 반환을 정당화한다"""
    candidates = [
        _result(
            "doc-generic",
            "다음과 같습니다. 계약에 적용되는 일반 설명이지만 행위 의도 책임 반환 법격언 근거는 없다.",
            source_kind="fiqh",
        )
    ]

    coverage = beta6_module._mcq_candidate_coverage_meta(product, query, candidates)

    assert coverage["lowCoverage"] is True
    assert "다음과" not in coverage["matchedTerms"]
    assert coverage["matchedTermRatio"] < coverage["threshold"]


def test_claim_analyzer_mode_disabled_uses_deterministic_cards(monkeypatch, tmp_path):
    class ExplodingLLMClient:
        provider = "exploding"

        def complete(self, messages, *, model="", timeout_seconds=None):
            raise AssertionError("claim analyzer should not call provider when disabled")

    monkeypatch.setenv("RELIGION_CLAIM_ANALYZER_MODE", "disabled")
    selected_records = [
        {
            "file_id": "s1",
            "document_title": "동의보감",
            "extracted_text": "감초는 처방 조화에 쓰인다는 원문 근거.",
            "metadata": {"sourceKind": "classic_canon", "school": "korean-classic", "tradition": "kmm"},
        }
    ]
    selected_evidence = [
        {
            "id": "s1",
            "label": "S1",
            "citation": "동의보감",
            "excerpt": "감초는 처방 조화에 쓰인다는 원문 근거.",
            "sourceKind": "classic_canon",
            "school": "korean-classic",
            "tradition": "kmm",
        }
    ]

    cards, analyzer = beta6_module.build_claim_cards_for_selected_sources(
        _tcm_profile(tmp_path / "unused.sqlite3"),
        "감초 근거",
        selected_records,
        selected_evidence,
        language="ko",
        llm_client=ExplodingLLMClient(),
        model="gemma",
    )

    assert analyzer["status"] == "disabled"
    assert analyzer["mode"] == "deterministic_source_cards"
    assert cards


def test_beta6_uses_lawkey_sized_top_k_even_when_frontend_requests_small_limit(tmp_path):
    db_path = tmp_path / "wide.sqlite3"
    _make_many_precedents_db(db_path, count=120)
    fake = CountingWideSelectorLLMClient()
    runtime = Beta6JobManager({"islam": _profile(db_path)}, runs_root=tmp_path / "runs", llm_client=fake)

    result = runtime.answer_sync(product="islam", query="sharedterm", language="en", limit=8)

    assert result["selector"]["candidateCount"] >= 100
    assert result["beta6"]["candidateCount"] >= 100
    assert result["beta6"]["selectedCount"] == 100
    assert len(result["beta6SelectedRecords"]) == 100
    assert len(result["selectedEvidence"]) == 100
    assert result["selector"]["selectorCandidateLimit"] == 120
    assert result["selector"]["selectorAuditedCandidateCount"] == 120
    assert result["selector"]["selectorBatchSize"] == 100
    assert fake.selector_prompt.count("file_id: doc-") == 120
    assert result["selector"]["mode"] == "llm_keyword_search_and_batched_selector"
    assert len(result["selector"]["selectorBatches"]) == 2
    assert "[S100]" in fake.writer_prompt


def test_beta6_fast_mode_caps_frontier_selection_and_source_count(tmp_path):
    db_path = tmp_path / "wide.sqlite3"
    _make_many_precedents_db(db_path, count=120)
    fake = CountingWideSelectorLLMClient()
    runtime = Beta6JobManager({"islam": _profile(db_path)}, runs_root=tmp_path / "runs", llm_client=fake)

    result = runtime.answer_sync(product="islam", query="sharedterm", language="en", limit=30, analysis_mode="fast")

    assert result["fastMode"] is True
    assert result["selector"]["topK"] == 30
    assert result["selector"]["frontierTarget"] == 30
    assert result["selector"]["frontierStopFloor"] == 30
    assert result["selector"]["perKeywordLimit"] == 30
    assert result["selector"]["selectorCandidateLimit"] <= 30
    assert result["beta6"]["selectedCount"] == 30
    assert len(result["beta6SelectedRecords"]) == 30
    assert len(result["selectedEvidence"]) == 30
    assert "[S31]" not in fake.writer_prompt


def test_beta6_fast_mode_can_raise_source_cap_for_quality_experiments(monkeypatch):
    monkeypatch.setenv("RELIGION_BETA6_FAST_TOP_K_PRECEDENTS", "50")
    monkeypatch.setenv("RELIGION_BETA6_FAST_PER_KEYWORD_LIMIT", "50")

    assert beta6_module._effective_beta6_top_k(50, fast_mode=True) == 50
    assert beta6_module._beta6_per_keyword_limit(50, fast_mode=True) == 50


def test_beta6_fast_mode_defaults_to_fifty_except_hindu(monkeypatch, tmp_path):
    monkeypatch.delenv("RELIGION_BETA6_FAST_TOP_K_PRECEDENTS", raising=False)
    monkeypatch.delenv("RELIGION_HINDU_BETA6_FAST_TOP_K_PRECEDENTS", raising=False)
    islam = _profile(tmp_path / "islam.sqlite3")
    hindu = ProductProfile(
        key="hindu",
        name="Hindu AI",
        db_path=tmp_path / "hindu.sqlite3",
        db_shape="precedents",
        languages=("ko", "en"),
        default_language="ko",
        theme="gallery-canvas",
        safety_notice="study aid",
    )

    assert beta6_module._effective_beta6_top_k(50, fast_mode=True, product=islam) == 50
    assert beta6_module._effective_beta6_top_k(50, fast_mode=True, product=hindu) == 30


def test_beta6_zero_source_bootstrap_supplies_first_round_candidates_for_reference_products(tmp_path):
    scenarios = {
        "buddhist": ("dhamma karma sutta teaching", "엉뚱한질문무매칭"),
        "catholic": ("grace scripture church catechism", "엉뚱한질문무매칭"),
        "hindu": ("karma dharma moksha bhagavad gita", "엉뚱한질문무매칭"),
        "tcm": ("감초 本草 처방 변증", "엉뚱한질문무매칭"),
    }
    profiles = {}
    for key, (bootstrap_text, _query) in scenarios.items():
        db_path = tmp_path / f"{key}.sqlite3"
        _make_many_precedents_db(db_path, count=1)
        with sqlite3.connect(db_path) as conn:
            conn.execute("UPDATE precedents SET full_text=?, title=?, case_number=? WHERE canonical_id='doc-000'", (bootstrap_text, f"{key} source", f"{key} source"))
            conn.execute("DELETE FROM precedents_fts")
            conn.execute("INSERT INTO precedents_fts(canonical_id, full_text) VALUES ('doc-000', ?)", (bootstrap_text,))
        profiles[key] = ProductProfile(
            key=key,
            name=f"{key.title()} AI",
            db_path=db_path,
            db_shape="precedents",
            languages=("ko", "en"),
            default_language="ko",
            theme="gallery-canvas",
            safety_notice="notice",
        )

    runtime = Beta6JobManager(profiles, runs_root=tmp_path / "runs", llm_client=None)

    for key, (_bootstrap_text, query) in scenarios.items():
        result = runtime.answer_sync(product=key, query=query, language="ko", limit=30, analysis_mode="fast")

        assert result["fastMode"] is True
        assert result["selector"]["zeroSourceBootstrap"] is True
        assert result["selector"]["selectionSource"] == "local_search_no_llm_bootstrap"
        assert result["beta6"]["selectedCount"] == 1
        assert result["selectedEvidence"][0]["id"] == "doc-000"


def test_islam_selector_keeps_lawkey_batch_count_with_compact_prompt_budget(monkeypatch, tmp_path):
    monkeypatch.delenv("RELIGION_SELECTOR_BATCH_SIZE", raising=False)
    monkeypatch.delenv("RELIGION_ISLAM_SELECTOR_BATCH_SIZE", raising=False)
    monkeypatch.delenv("RELIGION_SELECTOR_EXCERPT_CHARS", raising=False)
    monkeypatch.delenv("RELIGION_ISLAM_SELECTOR_EXCERPT_CHARS", raising=False)
    monkeypatch.setenv("RELIGION_SELECTOR_BATCH_WORKERS", "1")

    product = _profile(tmp_path / "islam.sqlite3")
    tail_marker = "TAILMARKER_SHOULD_NOT_ENTER_SELECTOR_PROMPT"
    candidates = [
        _result(
            f"doc-{index:03d}",
            "sharedterm compact selector opening "
            + ("arabic context " * 24)
            + tail_marker
            + (" extra tail " * 80),
            source_kind="fiqh",
        )
        for index in range(120)
    ]
    fake = CountingWideSelectorLLMClient()

    rows, ids, _reasoning, meta = beta6_module.select_rows_with_beta6_selector(
        product,
        "사회주의는 하람임? 학파와 원칙별로 근거를 정리해줘",
        "ko",
        candidates,
        limit=100,
        llm_client=fake,
        model="gemma",
        cache_root=tmp_path / "islam-compact-selector-cache",
    )

    assert meta["selectorBatchSize"] == 100
    assert len(meta["selectorBatches"]) == 2
    assert len(fake.selector_prompts) == 2
    assert max(len(prompt.encode("utf-8")) for prompt in fake.selector_prompts) < 95_000
    assert meta["selectorBatches"][0]["maxPromptBytes"] > 0
    assert meta["selectorBatches"][0]["primaryMaxPromptBytes"] == meta["selectorBatches"][0]["maxPromptBytes"]
    assert meta["selectorBatchTrace"][0]["maxPromptBytes"] == meta["selectorBatches"][0]["maxPromptBytes"]
    assert tail_marker not in fake.selector_prompt
    assert len(rows) == 100
    assert "doc-100" in ids


def test_islam_selector_utf8_excerpt_byte_budget_preserves_shape(monkeypatch, tmp_path):
    monkeypatch.delenv("RELIGION_SELECTOR_BATCH_SIZE", raising=False)
    monkeypatch.delenv("RELIGION_ISLAM_SELECTOR_BATCH_SIZE", raising=False)
    monkeypatch.delenv("RELIGION_SELECTOR_EXCERPT_CHARS", raising=False)
    monkeypatch.delenv("RELIGION_ISLAM_SELECTOR_EXCERPT_CHARS", raising=False)
    monkeypatch.delenv("RELIGION_SELECTOR_EXCERPT_BYTES", raising=False)
    monkeypatch.delenv("RELIGION_ISLAM_SELECTOR_EXCERPT_BYTES", raising=False)
    monkeypatch.setenv("RELIGION_SELECTOR_BATCH_WORKERS", "1")

    product = _profile(tmp_path / "islam.sqlite3")
    tail_marker = "TAILMARKER_SHOULD_NOT_ENTER_UTF8_SELECTOR_PROMPT"
    arabic_excerpt = "الملكية الخاصة والعدل وتوزيع المال بين الناس "
    candidates = [
        _result(
            f"doc-{index:03d}",
            arabic_excerpt * 40 + tail_marker + (" ذيل طويل " * 80),
            source_kind="fiqh",
            school="hanafi" if index % 2 == 0 else "shafii",
            tradition="sunni",
        )
        for index in range(120)
    ]
    fake = CountingWideSelectorLLMClient()

    rows, ids, _reasoning, meta = beta6_module.select_rows_with_beta6_selector(
        product,
        "사회주의는 하람임? 학파와 원칙별로 근거를 정리해줘",
        "ko",
        candidates,
        limit=100,
        llm_client=fake,
        model="gemma",
        cache_root=tmp_path / "islam-utf8-byte-selector-cache",
    )

    assert meta["selectorBatchSize"] == 100
    assert len(meta["selectorBatches"]) == 2
    assert meta["selectorExcerptBytes"] == 360
    assert max(len(prompt.encode("utf-8")) for prompt in fake.selector_prompts) < 55_000
    assert meta["selectorBatches"][0]["maxPromptBytes"] < 55_000
    assert "الملكية الخاصة" in fake.selector_prompt
    assert tail_marker not in fake.selector_prompt
    assert len(rows) == 100
    assert "doc-100" in ids


def test_islam_selector_compact_candidate_lines_are_default_and_preserve_ids(monkeypatch, tmp_path):
    monkeypatch.delenv("RELIGION_SELECTOR_COMPACT_LINES", raising=False)
    monkeypatch.delenv("RELIGION_ISLAM_SELECTOR_COMPACT_LINES", raising=False)
    monkeypatch.setenv("RELIGION_SELECTOR_BATCH_WORKERS", "1")
    monkeypatch.delenv("RELIGION_SELECTOR_BATCH_SIZE", raising=False)
    monkeypatch.delenv("RELIGION_ISLAM_SELECTOR_BATCH_SIZE", raising=False)

    product = _profile(tmp_path / "islam.sqlite3")
    long_citation = "Jami compact selector metadata citation " + ("volume-page " * 8)
    candidates = [
        SearchResult(
            canonical_id=f"doc-{index:03d}",
            title="Long redundant title that should not be repeated in compact selector lines " + str(index),
            citation=f"{long_citation}{index}",
            authority_body="Long authority body that is useful for display but too expensive in selector prompt",
            source_date="",
            case_name="fixture",
            case_type="fiqh_unit",
            full_text="ownership justice evidence " + ("arabic context " * 60),
            source_dataset="fixture/fiqh",
            source_path=f"doc-{index:03d}",
            score=100,
            tradition="sunni",
            school="hanafi" if index % 2 == 0 else "shafii",
            source_kind="fiqh",
            authority_level=80,
        )
        for index in range(120)
    ]
    fake = CountingWideSelectorLLMClient()

    rows, ids, _reasoning, meta = beta6_module.select_rows_with_beta6_selector(
        product,
        "사회주의는 하람임? 학파와 원칙별로 근거를 정리해줘",
        "ko",
        candidates,
        limit=100,
        llm_client=fake,
        model="gemma",
        cache_root=tmp_path / "compact-line-selector-cache",
    )

    assert meta["selectorInputMode"] == "raw_excerpt_v1+compact_lines_v1"
    assert fake.selector_prompt.count("file_id: doc-") == 120
    assert "title:" not in fake.selector_prompt
    assert "authority:" not in fake.selector_prompt
    assert "cite:" in fake.selector_prompt
    assert "kind=fiqh" in fake.selector_prompt
    assert max(len(prompt.encode("utf-8")) for prompt in fake.selector_prompts) < 52_000
    assert len(rows) == 100
    assert "doc-100" in ids


def test_beta6_evidence_capsules_preserve_identity_and_domain_roles(tmp_path):
    product = _profile(tmp_path / "islam.sqlite3")
    row = _result(
        "doc-001",
        "본문 첫 문장은 사회 정의와 사유 재산의 경계를 직접 다룹니다. " + ("tail " * 80),
        source_kind="fiqh",
        school="hanafi",
        tradition="sunni",
    )

    capsules = beta6_module.build_beta6_evidence_capsules(product, "사회주의는 하람임?", [row], excerpt_chars=80)

    assert len(capsules) == 1
    capsule = capsules[0]
    assert capsule["label"] == "S1"
    assert capsule["fileId"] == "doc-001"
    assert capsule["sourceKind"] == "fiqh"
    assert capsule["school"] == "hanafi"
    assert capsule["tradition"] == "sunni"
    assert "fiqh" in capsule["roleHints"]
    assert "hanafi" in capsule["roleHints"]
    assert capsule["packetId"] == "S1:doc-001"
    assert capsule["sourceId"] == "doc-001"
    assert capsule["sourceRole"] == "madhhab"
    assert "source_kind:fiqh" in capsule["domainAxes"]
    assert "school:hanafi" in capsule["domainAxes"]
    assert "upstream retrieval" in capsule["activationReason"]
    assert capsule["exactQuote"].startswith("본문 첫 문장")
    assert row.full_text[capsule["spanStart"] : capsule["spanEnd"]] == capsule["exactQuote"]
    assert capsule["spanEnd"] > capsule["spanStart"]
    assert "[META]" not in capsule["excerpt"]
    assert "본문 첫 문장" in capsule["excerpt"]
    assert len(capsule["excerpt"]) <= 80


def test_selector_evidence_capsule_mode_is_default_off_but_env_gated(monkeypatch, tmp_path):
    monkeypatch.setenv("RELIGION_SELECTOR_EVIDENCE_CAPSULES", "1")
    monkeypatch.setenv("RELIGION_SELECTOR_BATCH_SIZE", "100")
    monkeypatch.setenv("RELIGION_SELECTOR_BATCH_WORKERS", "1")

    product = _profile(tmp_path / "islam.sqlite3")
    tail_marker = "TAILMARKER_SHOULD_NOT_ENTER_CAPSULE_SELECTOR_PROMPT"
    candidates = [
        _result(
            f"doc-{index:03d}",
            "capsule opening exact phrase about ownership and justice "
            + ("arabic fiqh context " * 12)
            + tail_marker
            + (" hidden tail " * 100),
            source_kind="fiqh",
            school="hanafi" if index % 2 == 0 else "shafii",
            tradition="sunni",
        )
        for index in range(120)
    ]
    fake = CountingWideSelectorLLMClient()

    rows, ids, _reasoning, meta = beta6_module.select_rows_with_beta6_selector(
        product,
        "사회주의는 하람임? 학파와 원칙별로 근거를 정리해줘",
        "ko",
        candidates,
        limit=100,
        llm_client=fake,
        model="gemma",
        cache_root=tmp_path / "capsule-selector-cache",
    )

    assert meta["selectorInputMode"] == "context_packets_v1"
    assert meta["selectorCapsuleCount"] == 120
    assert "Evidence capsules:" in fake.selector_prompt
    assert "role_hints:" in fake.selector_prompt
    assert "source_role:" in fake.selector_prompt
    assert "activation_reason:" in fake.selector_prompt
    assert "exact_quote:" in fake.selector_prompt
    assert "school=hanafi" in fake.selector_prompt
    assert tail_marker not in fake.selector_prompt
    assert len(rows) == 100
    assert "doc-100" in ids


def test_selector_candidate_digest_is_stable_across_raw_and_context_packet_modes(monkeypatch, tmp_path):
    monkeypatch.setenv("RELIGION_SELECTOR_BATCH_SIZE", "100")
    monkeypatch.setenv("RELIGION_SELECTOR_BATCH_WORKERS", "1")
    product = _profile(tmp_path / "islam.sqlite3")
    candidates = [
        _result(
            f"doc-{index:03d}",
            "shared candidate universe for selector ablation " + ("context " * 20),
            source_kind="fiqh",
            school="hanafi" if index % 2 == 0 else "shafii",
            tradition="sunni",
        )
        for index in range(20)
    ]

    fake_raw = CountingWideSelectorLLMClient()
    _rows, _ids, _reasoning, raw_meta = beta6_module.select_rows_with_beta6_selector(
        product,
        "사회주의는 하람임?",
        "ko",
        candidates,
        limit=10,
        llm_client=fake_raw,
        model="gemma",
        cache_root=tmp_path / "raw-selector-cache",
    )

    monkeypatch.setenv("RELIGION_SELECTOR_EVIDENCE_CAPSULES", "1")
    fake_context = CountingWideSelectorLLMClient()
    _rows, _ids, _reasoning, context_meta = beta6_module.select_rows_with_beta6_selector(
        product,
        "사회주의는 하람임?",
        "ko",
        candidates,
        limit=10,
        llm_client=fake_context,
        model="gemma",
        cache_root=tmp_path / "context-selector-cache",
    )

    assert raw_meta["selectorInputMode"] != context_meta["selectorInputMode"]
    assert raw_meta["candidateIds"] == context_meta["candidateIds"] == [f"doc-{index:03d}" for index in range(20)]
    assert raw_meta["candidateSetDigest"] == context_meta["candidateSetDigest"]
    assert raw_meta["candidateSetDigest"].startswith("sha256:")


def test_beta6_runtime_persists_selector_context_packets(monkeypatch, tmp_path):
    monkeypatch.setenv("RELIGION_SELECTOR_EVIDENCE_CAPSULES", "1")
    monkeypatch.setenv("RELIGION_SELECTOR_BATCH_SIZE", "100")
    monkeypatch.setenv("RELIGION_SELECTOR_BATCH_WORKERS", "1")
    monkeypatch.setenv("RELIGION_BETA6_KEYWORD_ROUNDS", "1")

    db_path = tmp_path / "islam.sqlite3"
    _make_many_precedents_db(db_path, count=3)
    fake = CountingWideSelectorLLMClient()
    runtime = Beta6JobManager({"islam": _profile(db_path)}, runs_root=tmp_path / "runs", llm_client=fake)

    result = runtime.answer_sync(product="islam", query="sharedterm evidence principle", language="en", limit=3, analysis_mode="fast")

    packets = result["contextPackets"]
    assert packets
    assert result["selector"]["selectorInputMode"] == "context_packets_v1"
    assert result["selector"]["selectorContextPacketCount"] == len(packets)
    assert result["beta6"]["contextPacketCount"] == len(packets)
    assert result["artifacts"]["contextPackets"].endswith("context_packets.json")

    artifact_path = Path(result["artifacts"]["contextPackets"])
    artifact_packets = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact_packets == packets
    assert packets[0]["packetId"].startswith("S1:doc-")
    assert packets[0]["sourceId"].startswith("doc-")
    assert packets[0]["exactQuote"]
    assert packets[0]["spanEnd"] > packets[0]["spanStart"]
    assert "[META]" not in packets[0]["exactQuote"]


def test_selector_clean_raw_excerpt_mode_keeps_candidates_prompt_and_strips_metadata(monkeypatch, tmp_path):
    monkeypatch.setenv("RELIGION_SELECTOR_CLEAN_RAW_EXCERPTS", "1")
    monkeypatch.setenv("RELIGION_SELECTOR_BATCH_SIZE", "100")
    monkeypatch.setenv("RELIGION_SELECTOR_BATCH_WORKERS", "1")

    product = ProductProfile(
        key="tcm",
        name="Hanui AI",
        db_path=tmp_path / "tcm.sqlite3",
        db_shape="precedents",
        languages=("ko", "en"),
        default_language="ko",
        theme="tcm",
        safety_notice="medical safety notice",
    )
    candidates = [
        _result(
            f"doc-{index:03d}",
            "[META]\n"
            "religion: tcm-kmm\n"
            "tradition: kmm\n"
            "school: korean-classic\n"
            "authority_level: 100\n"
            "source_kind: classic_canon\n\n"
            "[PRIMARY TEXT]\n"
            "실제 원문 첫 문장은 임신 오심과 부종의 처방 근거를 다룹니다. "
            + ("본문 " * 80),
            source_kind="classic_canon",
            school="korean-classic",
            tradition="kmm",
        )
        for index in range(120)
    ]
    fake = CountingWideSelectorLLMClient()

    rows, ids, _reasoning, meta = beta6_module.select_rows_with_beta6_selector(
        product,
        "임신 오심과 부종 처방 근거를 비교해줘",
        "ko",
        candidates,
        limit=100,
        llm_client=fake,
        model="gemma",
        cache_root=tmp_path / "clean-raw-selector-cache",
    )

    assert meta["selectorInputMode"] == "clean_raw_excerpt_v1"
    assert meta["selectorCapsuleCount"] == 0
    assert "Candidates:" in fake.selector_prompt
    assert "Evidence capsules:" not in fake.selector_prompt
    assert "[META]" not in fake.selector_prompt
    assert "religion: tcm-kmm" not in fake.selector_prompt
    assert "실제 원문 첫 문장" in fake.selector_prompt
    assert len(rows) == 100
    assert "doc-100" in ids


def test_selector_role_diversity_hint_is_env_gated_and_cache_separated(monkeypatch, tmp_path):
    monkeypatch.setenv("RELIGION_SELECTOR_CLEAN_RAW_EXCERPTS", "1")
    monkeypatch.setenv("RELIGION_SELECTOR_ROLE_DIVERSITY_HINT", "1")
    monkeypatch.setenv("RELIGION_SELECTOR_BATCH_SIZE", "100")
    monkeypatch.setenv("RELIGION_SELECTOR_BATCH_WORKERS", "1")

    product = ProductProfile(
        key="tcm",
        name="Hanui AI",
        db_path=tmp_path / "tcm.sqlite3",
        db_shape="precedents",
        languages=("ko", "en"),
        default_language="ko",
        theme="tcm",
        safety_notice="medical safety notice",
    )
    candidates = [
        _result(
            f"doc-{index:03d}",
            "[META]\nsource_kind: formulary\n\n[PRIMARY TEXT]\n처방 원문과 금기 맥락을 함께 다룹니다. " + ("본문 " * 40),
            source_kind="formulary" if index % 5 == 0 else "classic_canon",
        )
        for index in range(120)
    ]
    fake = CountingWideSelectorLLMClient()

    _rows, _ids, _reasoning, meta = beta6_module.select_rows_with_beta6_selector(
        product,
        "임신 처방 원문과 금기 근거를 비교해줘",
        "ko",
        candidates,
        limit=100,
        llm_client=fake,
        model="gemma",
        cache_root=tmp_path / "role-diversity-selector-cache",
    )

    assert meta["selectorInputMode"] == "clean_raw_excerpt_v1+role_diversity_v1"
    assert "Preserve source_kind diversity" in fake.selector_prompt
    assert "formulary" in fake.selector_prompt


def test_selector_evidence_ledger_mode_is_default_off(monkeypatch, tmp_path):
    monkeypatch.delenv("RELIGION_SELECTOR_EVIDENCE_LEDGER", raising=False)
    monkeypatch.setenv("RELIGION_SELECTOR_BATCH_SIZE", "100")
    monkeypatch.setenv("RELIGION_SELECTOR_BATCH_WORKERS", "1")

    product = _profile(tmp_path / "islam.sqlite3")
    fake = CountingWideSelectorLLMClient()
    candidates = [
        _result(f"doc-{index:03d}", "ownership justice evidence", source_kind="fiqh")
        for index in range(120)
    ]

    _rows, _ids, _reasoning, meta = beta6_module.select_rows_with_beta6_selector(
        product,
        "사회주의는 하람임?",
        "ko",
        candidates,
        limit=100,
        llm_client=fake,
        model="gemma",
        cache_root=tmp_path / "ledger-default-cache",
    )

    assert meta["selectorInputMode"] == "raw_excerpt_v1+compact_lines_v1"
    assert meta["selectorEvidenceLedgerEnabled"] is False
    assert meta["selectorEvidenceLedgerCount"] == 0
    assert "JSONL ledger" not in fake.selector_prompt


def test_selector_evidence_ledger_is_env_gated_and_cached(monkeypatch, tmp_path):
    monkeypatch.setenv("RELIGION_SELECTOR_EVIDENCE_LEDGER", "1")
    monkeypatch.setenv("RELIGION_SELECTOR_BATCH_SIZE", "100")
    monkeypatch.setenv("RELIGION_SELECTOR_BATCH_WORKERS", "1")

    product = _profile(tmp_path / "islam.sqlite3")
    fake = LedgerSelectorLLMClient()
    candidates = [
        _result(f"doc-{index:03d}", "ownership justice evidence", source_kind="fiqh")
        for index in range(120)
    ]

    rows, ids, _reasoning, meta = beta6_module.select_rows_with_beta6_selector(
        product,
        "사회주의는 하람임?",
        "ko",
        candidates,
        limit=100,
        llm_client=fake,
        model="gemma",
        cache_root=tmp_path / "ledger-enabled-cache",
    )

    assert "JSONL ledger" in fake.selector_prompt
    assert meta["selectorInputMode"] == "raw_excerpt_v1+compact_lines_v1+evidence_ledger_v1"
    assert meta["selectorEvidenceLedgerEnabled"] is True
    assert meta["selectorEvidenceLedgerCount"] == 6
    assert meta["selectorEvidenceLedger"][0]["fileId"] == "doc-000"
    assert meta["selectorEvidenceLedger"][0]["contextSummary"] == "doc-000 문헌 맥락"
    assert meta["selectorBatches"][0]["ledgerCount"] == 3
    assert meta["selectorBatches"][1]["ledgerCount"] == 3
    assert len(rows) == 6
    assert ids[:3] == ["doc-000", "doc-001", "doc-002"]


def test_beta6_runtime_attaches_selector_ledger_to_selected_evidence(monkeypatch, tmp_path):
    monkeypatch.setenv("RELIGION_SELECTOR_EVIDENCE_LEDGER", "1")
    monkeypatch.setenv("RELIGION_BETA6_TOP_K_PRECEDENTS", "100")
    monkeypatch.setenv("RELIGION_BETA6_MAX_TOP_K_PRECEDENTS", "100")
    monkeypatch.setenv("RELIGION_SELECTOR_BATCH_SIZE", "100")
    monkeypatch.setenv("RELIGION_SELECTOR_BATCH_WORKERS", "1")

    db_path = tmp_path / "islam.sqlite3"
    _make_many_precedents_db(db_path, count=120)
    fake = LedgerSelectorLLMClient()
    runtime = Beta6JobManager({"islam": _profile(db_path)}, runs_root=tmp_path / "runs", llm_client=fake)

    result = runtime.answer_sync(product="islam", query="sharedterm", language="ko", limit=8)

    assert result["selector"]["selectorEvidenceLedgerEnabled"] is True
    assert result["selector"]["selectorEvidenceLedgerCount"] > 0
    first = result["selectedEvidence"][0]
    assert first["id"] == "doc-000"
    assert first["selectorContextSummary"] == "doc-000 문헌 맥락"
    assert first["selectorClaimSummary"] == "doc-000 쟁점 요약"
    assert first["selectorQuoteCandidate"] == "ownership justice evidence"
    assert first["selectorStance"] == "school_position"
    assert first["selectorSourceRole"] == "fiqh"


def test_beta6_writer_prompt_budgets_claim_and_source_detail_without_reducing_selected_count(monkeypatch, tmp_path):
    product = _profile(tmp_path / "islam.sqlite3")
    selected_records = []
    claim_cards = []
    for index in range(1, 101):
        source_id = f"doc-{index:03d}"
        selected_records.append(
            {
                "file_id": source_id,
                "case_number": f"Source {index}",
                "document_title": f"Document {index}",
                "extracted_text": f"source-{index:03d} " + ("very long source text " * 140),
            }
        )
        claim_cards.append(
            {
                "claimId": f"C{index}",
                "label": f"S{index}",
                "sourceId": source_id,
                "role": "fiqh",
                "claimAxis": f"axis {index}",
                "stance": "support",
                "citation": f"Source {index}",
                "contextSummary": f"context {index} " + ("detail " * 30),
                "claimSummary": f"claim {index} " + ("summary " * 30),
                "quote": f"quote {index} " + ("quoted source detail " * 30),
            }
        )
    answer_plan = {
        "bodyClaimIds": [f"C{index}" for index in range(1, 81)],
        "coverageRequiredClaimIds": [f"C{index}" for index in range(1, 81)],
        "claimGroups": [{"title": "all", "claimIds": [f"C{index}" for index in range(1, 81)]}],
        "answerOutline": ["cover the strongest selected claims"],
        "citationPolicy": "cite selected claim labels",
    }

    monkeypatch.delenv("RELIGION_WRITER_CLAIM_LIMIT", raising=False)
    monkeypatch.delenv("RELIGION_WRITER_SOURCE_LIMIT", raising=False)
    monkeypatch.delenv("RELIGION_WRITER_SOURCE_CHARS", raising=False)

    messages = beta6_module.build_beta6_messages(
        product,
        "기도 횟수 근거",
        "ko",
        selected_records,
        claim_cards=claim_cards,
        answer_plan=answer_plan,
    )
    prompt = "\n".join(message["content"] for message in messages)

    assert "[S100]" in prompt
    assert "claim_id: C1" in prompt
    assert "claim_id: C80" not in prompt
    assert "source-001 very long source text" in prompt
    assert "source-100 very long source text" not in prompt
    assert len(prompt.encode("utf-8")) < 140_000


def test_beta6_candidate_frontier_uses_lawkey_r133_counts_before_top_k_selection(monkeypatch, tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    db_path.touch()
    profile = _profile(db_path)
    fake = FrontierCountingLLMClient()
    search_calls = []
    next_index = {"value": 0}

    monkeypatch.setenv("RELIGION_BETA6_TOP_K_PRECEDENTS", "100")
    monkeypatch.setenv("RELIGION_BETA6_MAX_TOP_K_PRECEDENTS", "100")
    monkeypatch.setenv("RELIGION_SELECTOR_BATCH_WORKERS", "3")

    def fake_search(product, query, *, limit=8, language=""):
        search_calls.append({"query": query, "limit": limit})
        rows = []
        for _ in range(limit):
            index = next_index["value"]
            next_index["value"] += 1
            rows.append(_result(f"frontier-{index:04d}", f"{query} frontier text {index:04d}", source_kind="fiqh"))
        return rows

    monkeypatch.setattr(beta6_module, "search_documents", fake_search)

    rows, selector = beta6_module.select_rows_with_beta6_llm(
        profile,
        "root question",
        "en",
        limit=8,
        llm_client=fake,
        model="gemma",
        provider="fixture",
    )

    assert selector["topK"] == 100
    assert selector["frontierTarget"] == 1200
    assert selector["frontierStopFloor"] == 800
    assert selector["perKeywordLimit"] == 700
    assert selector["candidateCount"] == 1200
    assert len(rows) == 100
    assert search_calls[0]["limit"] == 700
    assert any(call["query"] == "kw1" and call["limit"] == 700 for call in search_calls)
    assert selector["selectorCandidateLimit"] == 1200
    assert selector["selectorAuditedCandidateCount"] == 1200
    assert selector["selectorBatchSize"] == 100
    assert len(selector["selectorBatches"]) == 12
    assert "file_id: frontier-0000" in fake.selector_prompt
    assert "file_id: frontier-0059" in fake.selector_prompt
    assert "file_id: frontier-1199" in fake.selector_prompt


def test_beta6_frontier_rerank_promotes_late_relevant_candidates_before_selector(monkeypatch, tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    db_path.touch()
    profile = _profile(db_path)
    fake = FrontierCountingLLMClient()
    next_index = {"value": 0}

    monkeypatch.setenv("RELIGION_BETA6_TOP_K_PRECEDENTS", "100")
    monkeypatch.setenv("RELIGION_BETA6_MAX_TOP_K_PRECEDENTS", "100")

    def fake_search(product, query, *, limit=8, language=""):
        rows = []
        for _ in range(limit):
            index = next_index["value"]
            next_index["value"] += 1
            if index == 1199:
                rows.append(
                    _result(
                        "frontier-1199",
                        "late decisive socialism haram property ownership justice sharia evidence",
                        source_kind="fiqh",
                    )
                )
            else:
                rows.append(_result(f"frontier-{index:04d}", "generic low signal source text", source_kind="fiqh"))
        return rows

    monkeypatch.setattr(beta6_module, "search_documents", fake_search)

    rows, selector = beta6_module.select_rows_with_beta6_llm(
        profile,
        "socialism haram property ownership",
        "en",
        limit=8,
        llm_client=fake,
        model="gemma",
        provider="fixture",
    )

    assert selector["candidateCount"] == 1200
    assert selector["frontierScoredCount"] == 1200
    assert "file_id: frontier-1199" in fake.selector_prompt
    assert rows[0].canonical_id == "frontier-1199"
    assert selector["frontierTopDebug"][0]["id"] == "frontier-1199"


def test_beta6_selector_audits_entire_lawkey_sized_frontier_before_local_fill(monkeypatch, tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    db_path.touch()
    profile = _profile(db_path)
    fake = FullFrontierAuditLLMClient()
    next_index = {"value": 0}

    monkeypatch.setenv("RELIGION_BETA6_TOP_K_PRECEDENTS", "100")
    monkeypatch.setenv("RELIGION_BETA6_MAX_TOP_K_PRECEDENTS", "100")
    monkeypatch.delenv("RELIGION_SELECTOR_CANDIDATE_LIMIT", raising=False)

    def fake_search(product, query, *, limit=8, language=""):
        rows = []
        for _ in range(limit):
            index = next_index["value"]
            next_index["value"] += 1
            rows.append(_result(f"frontier-{index:04d}", "same generic frontier text", source_kind="fiqh"))
        return rows

    monkeypatch.setattr(beta6_module, "search_documents", fake_search)

    rows, selector = beta6_module.select_rows_with_beta6_llm(
        profile,
        "generic question without local late-term signal",
        "en",
        limit=8,
        llm_client=fake,
        model="gemma",
        provider="fixture",
    )

    assert selector["candidateCount"] == 1200
    assert selector["selectorCandidateLimit"] == 1200
    assert selector["selectorAuditedCandidateCount"] == 1200
    assert "file_id: frontier-1199" in fake.selector_prompt
    assert "frontier-1199" in selector["rawSelectedIds"]
    assert rows[0].canonical_id == "frontier-1199"


def test_beta6_batched_selector_does_not_starve_late_batch_when_early_batches_are_dense(monkeypatch, tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    db_path.touch()
    profile = _profile(db_path)
    fake = FrontierCountingLLMClient()
    next_index = {"value": 0}

    monkeypatch.setenv("RELIGION_BETA6_TOP_K_PRECEDENTS", "100")
    monkeypatch.setenv("RELIGION_BETA6_MAX_TOP_K_PRECEDENTS", "100")
    monkeypatch.delenv("RELIGION_SELECTOR_CANDIDATE_LIMIT", raising=False)

    def fake_search(product, query, *, limit=8, language=""):
        rows = []
        for _ in range(limit):
            index = next_index["value"]
            next_index["value"] += 1
            text = "generic selected source text"
            if index == 1199:
                text = "late decisive school position and principle evidence"
            rows.append(_result(f"frontier-{index:04d}", text, source_kind="fiqh"))
        return rows

    monkeypatch.setattr(beta6_module, "search_documents", fake_search)

    rows, selector = beta6_module.select_rows_with_beta6_llm(
        profile,
        "generic question where late batch contains decisive evidence",
        "en",
        limit=8,
        llm_client=fake,
        model="gemma",
        provider="fixture",
    )

    assert selector["candidateCount"] == 1200
    assert selector["selectorAuditedCandidateCount"] == 1200
    assert "file_id: frontier-1199" in fake.selector_prompt
    assert "frontier-1199" in selector["rawSelectedIds"]
    assert "frontier-1199" in {row.canonical_id for row in rows}


def test_beta6_selector_emits_batched_progress_metadata(monkeypatch, tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    db_path.touch()
    profile = _profile(db_path)
    fake = FrontierCountingLLMClient()
    next_index = {"value": 0}
    events = []

    monkeypatch.setenv("RELIGION_BETA6_TOP_K_PRECEDENTS", "100")
    monkeypatch.setenv("RELIGION_BETA6_MAX_TOP_K_PRECEDENTS", "100")
    monkeypatch.setenv("RELIGION_SELECTOR_BATCH_WORKERS", "3")

    def fake_search(product, query, *, limit=8, language=""):
        rows = []
        for _ in range(limit):
            index = next_index["value"]
            next_index["value"] += 1
            rows.append(_result(f"frontier-{index:04d}", f"{query} frontier text {index:04d}", source_kind="fiqh"))
        return rows

    def progress_callback(stage, message="", meta=None):
        events.append({"stage": stage, "message": message, "meta": meta or {}})

    monkeypatch.setattr(beta6_module, "search_documents", fake_search)

    _rows, selector = beta6_module.select_rows_with_beta6_llm(
        profile,
        "root question",
        "ko",
        limit=8,
        llm_client=fake,
        model="gemma",
        provider="fixture",
        progress_callback=progress_callback,
    )

    batch_events = [
        event
        for event in events
        if event["stage"] == "source_selection" and (event["meta"].get("batch") or {}).get("count") == 12
    ]
    assert selector["selectorBatchSize"] == 100
    assert selector["selectorBatchWorkers"] == 3
    assert len(batch_events) == 12
    assert batch_events[0]["meta"]["batch"]["index"] == 1
    assert batch_events[-1]["meta"]["batch"]["index"] == 12
    assert "1/12" in batch_events[0]["meta"]["detail"]
    assert "12/12" in batch_events[-1]["meta"]["detail"]


def test_beta6_selector_records_batch_timing_trace_for_source_selection_debugging(monkeypatch, tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    db_path.touch()
    profile = _profile(db_path)
    fake = FrontierCountingLLMClient()
    next_index = {"value": 0}

    monkeypatch.setenv("RELIGION_BETA6_TOP_K_PRECEDENTS", "100")
    monkeypatch.setenv("RELIGION_BETA6_MAX_TOP_K_PRECEDENTS", "100")
    monkeypatch.setenv("RELIGION_SELECTOR_BATCH_WORKERS", "1")

    def fake_search(product, query, *, limit=8, language=""):
        rows = []
        for _ in range(limit):
            index = next_index["value"]
            next_index["value"] += 1
            rows.append(_result(f"frontier-{index:04d}", f"{query} frontier text {index:04d}", source_kind="fiqh"))
        return rows

    monkeypatch.setattr(beta6_module, "search_documents", fake_search)

    _rows, selector = beta6_module.select_rows_with_beta6_llm(
        profile,
        "root question",
        "ko",
        limit=8,
        llm_client=fake,
        model="gemma",
        provider="fixture",
    )

    trace = selector["selectorBatchTrace"]
    assert len(trace) == 12
    assert trace[0]["batch"] == 1
    assert trace[0]["candidateCount"] == 100
    assert trace[0]["status"] in {"completed", "empty_selection"}
    assert trace[0]["elapsedSec"] >= 0
    assert trace[0]["cacheHit"] is False
    assert trace[0]["selectedCount"] >= 0


def test_simli_beta6_keeps_lawkey_top_k_but_uses_original_simli_sized_frontier(monkeypatch, tmp_path):
    db_path = tmp_path / "psych.sqlite3"
    db_path.touch()
    profile = _simli_profile(db_path)
    fake = FrontierCountingLLMClient()
    next_index = {"value": 0}

    monkeypatch.setenv("RELIGION_BETA6_TOP_K_PRECEDENTS", "100")
    monkeypatch.setenv("RELIGION_BETA6_MAX_TOP_K_PRECEDENTS", "100")

    def fake_search(product, query, *, limit=8, language=""):
        rows = []
        for _ in range(limit):
            index = next_index["value"]
            next_index["value"] += 1
            rows.append(_result(f"frontier-{index:04d}", f"{query} simli evidence {index:04d}", source_kind="guideline"))
        return rows

    monkeypatch.setattr(beta6_module, "search_documents", fake_search)

    rows, selector = beta6_module.select_rows_with_beta6_llm(
        profile,
        "insomnia anxiety CBT",
        "ko",
        limit=8,
        llm_client=fake,
        model="gemma",
        provider="fixture",
    )

    assert selector["topK"] == 100
    assert len(rows) == 100
    assert selector["frontierTarget"] == 400
    assert selector["frontierStopFloor"] == 300
    assert selector["candidateCount"] == 400
    assert selector["frontierScoredCount"] == 400


def test_simli_selector_uses_lawkey_generic_judge_candidate_and_batch_counts(monkeypatch, tmp_path):
    db_path = tmp_path / "psych.sqlite3"
    db_path.touch()
    profile = _simli_profile(db_path)
    fake = FrontierCountingLLMClient()
    next_index = {"value": 0}

    monkeypatch.setenv("RELIGION_BETA6_TOP_K_PRECEDENTS", "100")
    monkeypatch.setenv("RELIGION_BETA6_MAX_TOP_K_PRECEDENTS", "100")
    monkeypatch.delenv("RELIGION_SIMLI_SELECTOR_BATCH_SIZE", raising=False)

    def fake_search(product, query, *, limit=8, language=""):
        rows = []
        for _ in range(limit):
            index = next_index["value"]
            next_index["value"] += 1
            rows.append(_result(f"frontier-{index:04d}", f"{query} simli evidence {index:04d}", source_kind="guideline"))
        return rows

    monkeypatch.setattr(beta6_module, "search_documents", fake_search)

    _rows, selector = beta6_module.select_rows_with_beta6_llm(
        profile,
        "insomnia anxiety CBT",
        "ko",
        limit=8,
        llm_client=fake,
        model="gemma",
        provider="fixture",
    )

    assert selector["selectorCandidateLimit"] == 400
    assert selector["selectorAuditedCandidateCount"] == 400
    assert selector["selectorBatchSize"] == 25
    assert len(selector["selectorBatches"]) == 16


def test_tcm_selector_uses_lawkey_generic_judge_candidate_and_batch_counts(monkeypatch, tmp_path):
    db_path = tmp_path / "tcm.sqlite3"
    db_path.touch()
    profile = _tcm_profile(db_path)
    fake = FrontierCountingLLMClient()
    next_index = {"value": 0}

    monkeypatch.setenv("RELIGION_BETA6_TOP_K_PRECEDENTS", "100")
    monkeypatch.setenv("RELIGION_BETA6_MAX_TOP_K_PRECEDENTS", "100")
    monkeypatch.delenv("RELIGION_SELECTOR_BATCH_SIZE", raising=False)
    monkeypatch.delenv("RELIGION_TCM_SELECTOR_BATCH_SIZE", raising=False)

    def fake_search(product, query, *, limit=8, language=""):
        rows = []
        for _ in range(limit):
            index = next_index["value"]
            next_index["value"] += 1
            rows.append(_result(f"frontier-{index:04d}", f"{query} tcm evidence {index:04d}", source_kind="materia_medica"))
        return rows

    monkeypatch.setattr(beta6_module, "search_documents", fake_search)

    _rows, selector = beta6_module.select_rows_with_beta6_llm(
        profile,
        "감초 임신 본초 금기",
        "ko",
        limit=8,
        llm_client=fake,
        model="gemma",
        provider="fixture",
    )

    assert selector["topK"] == 100
    assert selector["frontierTarget"] == 1200
    assert selector["selectorCandidateLimit"] == 1200
    assert selector["selectorAuditedCandidateCount"] == 1200
    assert selector["selectorBatchSize"] == 100
    assert len(selector["selectorBatches"]) == 12


def test_beta6_selector_records_candidate_search_trace_for_latency_debugging(monkeypatch, tmp_path):
    db_path = tmp_path / "tcm.sqlite3"
    db_path.touch()
    profile = _tcm_profile(db_path)
    fake = FrontierCountingLLMClient()
    next_index = {"value": 0}

    monkeypatch.setenv("RELIGION_BETA6_TOP_K_PRECEDENTS", "100")
    monkeypatch.setenv("RELIGION_BETA6_MAX_TOP_K_PRECEDENTS", "100")
    monkeypatch.setenv("RELIGION_SELECTOR_BATCH_WORKERS", "1")

    def fake_search(product, query, *, limit=8, language=""):
        rows = []
        for _ in range(limit):
            index = next_index["value"]
            next_index["value"] += 1
            rows.append(_result(f"frontier-{index:04d}", f"{query} trace text {index:04d}", source_kind="materia_medica"))
        return rows

    monkeypatch.setattr(beta6_module, "search_documents", fake_search)

    _rows, selector = beta6_module.select_rows_with_beta6_llm(
        profile,
        "감초 임신 금기",
        "ko",
        limit=8,
        llm_client=fake,
        model="gemma",
        provider="fixture",
    )

    trace = selector["candidateSearchTrace"]
    assert trace
    assert trace[0]["label"]
    assert trace[0]["query"]
    assert trace[0]["limit"] == 700
    assert trace[0]["resultCount"] == 700
    assert trace[0]["elapsedSec"] >= 0
    assert trace[0]["cacheHit"] is False


def test_beta6_selector_records_keyword_generation_trace_for_latency_debugging(monkeypatch, tmp_path):
    db_path = tmp_path / "tcm.sqlite3"
    db_path.touch()
    profile = _tcm_profile(db_path)
    fake = FrontierCountingLLMClient()
    next_index = {"value": 0}

    monkeypatch.setenv("RELIGION_BETA6_TOP_K_PRECEDENTS", "100")
    monkeypatch.setenv("RELIGION_BETA6_MAX_TOP_K_PRECEDENTS", "100")
    monkeypatch.setenv("RELIGION_SELECTOR_BATCH_WORKERS", "1")

    def fake_search(product, query, *, limit=8, language=""):
        rows = []
        for _ in range(limit):
            index = next_index["value"]
            next_index["value"] += 1
            rows.append(_result(f"frontier-{index:04d}", f"{query} keyword trace text {index:04d}", source_kind="materia_medica"))
        return rows

    monkeypatch.setattr(beta6_module, "search_documents", fake_search)

    _rows, selector = beta6_module.select_rows_with_beta6_llm(
        profile,
        "감초 임신 금기",
        "ko",
        limit=8,
        llm_client=fake,
        model="gemma",
        provider="fixture",
    )

    trace = selector["keywordGenerationTrace"]
    assert trace
    assert trace[0]["round"] == 1
    assert trace[0]["phase"] == "initial"
    assert trace[0]["keywordCount"] == 10
    assert trace[0]["newKeywordCount"] == 10
    assert trace[0]["candidateCountBefore"] == 0
    assert trace[0]["candidateCountAfter"] >= 700
    assert trace[0]["elapsedSec"] >= 0
    assert trace[0]["cacheHit"] is False


def test_beta6_additional_keyword_round_searches_only_new_terms_when_frontier_is_full(monkeypatch, tmp_path):
    db_path = tmp_path / "tcm.sqlite3"
    db_path.touch()
    profile = _tcm_profile(db_path)
    fake = TwoRoundKeywordLLMClient()
    search_calls = []
    next_index = {"value": 0}

    monkeypatch.setenv("RELIGION_BETA6_TOP_K_PRECEDENTS", "100")
    monkeypatch.setenv("RELIGION_BETA6_MAX_TOP_K_PRECEDENTS", "100")
    monkeypatch.setenv("RELIGION_SELECTOR_BATCH_WORKERS", "1")

    def fake_search(product, query, *, limit=8, language=""):
        search_calls.append({"query": query, "limit": limit})
        rows = []
        for offset in range(limit):
            index = next_index["value"]
            next_index["value"] += 1
            source_kind = "classic_canon" if offset % 2 == 0 else "materia_medica"
            rows.append(_result(f"frontier-{index:04d}", f"{query} frontier text {index:04d}", source_kind=source_kind))
        return rows

    monkeypatch.setattr(beta6_module, "search_documents", fake_search)

    _rows, selector = beta6_module.select_rows_with_beta6_llm(
        profile,
        "root question",
        "ko",
        limit=8,
        llm_client=fake,
        model="gemma",
        provider="fixture",
    )

    assert len(selector["keywordRounds"]) == 2
    assert selector["candidateCount"] == 1200
    queries = [call["query"] for call in search_calls]
    assert "late-specific-one" in queries
    assert queries.count("root question") == 1
    assert queries.count("old-one") == 1
    late_call = next(call for call in search_calls if call["query"] == "late-specific-one")
    assert late_call["limit"] == 160


def test_beta6_fast_mode_stops_after_full_first_frontier_without_refine_search(monkeypatch, tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    db_path.touch()
    profile = _profile(db_path)
    fake = BroadThenSpecificKeywordLLMClient()
    search_calls = []

    def fake_search(product, query, *, limit=8, language=""):
        search_calls.append(query)
        if query == "broadkw":
            return [
                _result("doc-broad-scripture-1", "broadkw scripture text", source_kind="scripture"),
                _result("doc-broad-fiqh-1", "broadkw fiqh text", source_kind="fiqh"),
                _result("doc-broad-scripture-2", "broadkw second scripture", source_kind="scripture"),
                _result("doc-broad-fiqh-2", "broadkw second fiqh", source_kind="fiqh"),
            ]
        if query == "late-specific":
            raise AssertionError("fast full frontier should not refine-search late-specific")
        return []

    monkeypatch.setenv("RELIGION_BETA6_KEYWORD_ROUNDS", "2")
    monkeypatch.setenv("RELIGION_BETA6_MIN_KEYWORD_ROUNDS", "2")
    monkeypatch.setattr(beta6_module, "search_documents", fake_search)

    rows, selector = beta6_module.select_rows_with_beta6_llm(
        profile,
        "root question",
        "en",
        limit=4,
        llm_client=fake,
        model="gemma",
        provider="fixture",
        fast_mode=True,
    )

    assert len(rows) == 4
    assert selector["fastMode"] is True
    assert len(selector["keywordRounds"]) == 1
    assert "broadkw" in search_calls
    assert "late-specific" not in search_calls


def test_tcm_selector_keeps_lawkey_batch_count_with_compact_prompt_budget(monkeypatch, tmp_path):
    monkeypatch.delenv("RELIGION_SELECTOR_BATCH_SIZE", raising=False)
    monkeypatch.delenv("RELIGION_TCM_SELECTOR_BATCH_SIZE", raising=False)
    monkeypatch.delenv("RELIGION_SELECTOR_EXCERPT_CHARS", raising=False)
    monkeypatch.delenv("RELIGION_TCM_SELECTOR_EXCERPT_CHARS", raising=False)
    monkeypatch.setenv("RELIGION_SELECTOR_BATCH_WORKERS", "1")

    product = _tcm_profile(tmp_path / "tcm.sqlite3")
    tail_marker = "TAILMARKER_SHOULD_NOT_ENTER_TCM_SELECTOR_PROMPT"
    candidates = [
        _result(
            f"doc-{index:03d}",
            "sharedterm compact tcm selector opening "
            + ("本草 經方 禁忌 妊娠 " * 24)
            + tail_marker
            + (" extra tail " * 80),
            source_kind="materia_medica",
        )
        for index in range(120)
    ]
    fake = CountingWideSelectorLLMClient()

    rows, ids, _reasoning, meta = beta6_module.select_rows_with_beta6_selector(
        product,
        "임신 중 감초와 계지를 써도 되나? 고전 근거와 현대 안전성 관점으로 정리해줘",
        "ko",
        candidates,
        limit=100,
        llm_client=fake,
        model="gemma",
        cache_root=tmp_path / "tcm-compact-selector-cache",
    )

    assert meta["selectorBatchSize"] == 100
    assert len(meta["selectorBatches"]) == 2
    assert len(fake.selector_prompts) == 2
    assert max(len(prompt.encode("utf-8")) for prompt in fake.selector_prompts) < 95_000
    assert tail_marker not in fake.selector_prompt
    assert len(rows) == 100
    assert "doc-100" in ids


def test_simli_selector_uses_shorter_product_timeout_before_local_fallback(monkeypatch, tmp_path):
    db_path = tmp_path / "psych.sqlite3"
    db_path.touch()
    profile = _simli_profile(db_path)
    fake = StageTimeoutLLMClient()
    next_index = {"value": 0}

    monkeypatch.setenv("RELIGION_BETA6_TOP_K_PRECEDENTS", "100")
    monkeypatch.setenv("RELIGION_BETA6_MAX_TOP_K_PRECEDENTS", "100")

    def fake_search(product, query, *, limit=8, language=""):
        rows = []
        for _ in range(limit):
            index = next_index["value"]
            next_index["value"] += 1
            rows.append(_result(f"frontier-{index:04d}", f"{query} simli evidence {index:04d}", source_kind="guideline"))
        return rows

    monkeypatch.setattr(beta6_module, "search_documents", fake_search)

    rows, selector = beta6_module.select_rows_with_beta6_llm(
        profile,
        "insomnia anxiety CBT",
        "ko",
        limit=8,
        llm_client=fake,
        model="gemma",
        provider="fixture",
    )

    selector_calls = [call for call in fake.calls if "source selector" in call["system"]]
    assert selector_calls
    assert selector_calls[0]["timeout_seconds"] == 45
    assert selector["status"] == "fallback_selector_error"
    assert len(rows) == 100


def test_tcm_selector_keeps_full_timeout_for_large_corpus_lawkey_batches(monkeypatch, tmp_path):
    product = _tcm_profile(tmp_path / "tcm.sqlite3")
    fake = StageTimeoutLLMClient()
    candidates = [
        _result(f"doc-{index:03d}", f"sharedterm tcm timeout source {index}", source_kind="materia_medica")
        for index in range(120)
    ]

    monkeypatch.delenv("RELIGION_SELECTOR_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("RELIGION_TCM_SELECTOR_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("RELIGION_SELECTOR_BATCH_SIZE", raising=False)
    monkeypatch.delenv("RELIGION_TCM_SELECTOR_BATCH_SIZE", raising=False)
    monkeypatch.setenv("RELIGION_SELECTOR_BATCH_WORKERS", "1")

    rows, _ids, _reasoning, meta = beta6_module.select_rows_with_beta6_selector(
        product,
        "sharedterm tcm timeout",
        "ko",
        candidates,
        limit=100,
        llm_client=fake,
        model="gemma",
        cache_root=tmp_path / "tcm-timeout-cache",
    )

    selector_calls = [call for call in fake.calls if "source selector" in call["system"]]
    assert selector_calls
    assert all(call["timeout_seconds"] == 90 for call in selector_calls)
    assert meta["selectorBatchSize"] == 100
    assert meta["selectorLocalRecoveryCount"] == 2
    assert len(rows) == 100


def test_tcm_selector_keeps_parallel_workers_for_cold_frontier(monkeypatch, tmp_path):
    tcm = _tcm_profile(tmp_path / "tcm.sqlite3")
    islam = _profile(tmp_path / "islam.sqlite3")
    simli = _simli_profile(tmp_path / "psych.sqlite3")

    monkeypatch.delenv("RELIGION_SELECTOR_BATCH_WORKERS", raising=False)
    monkeypatch.delenv("RELIGION_TCM_SELECTOR_BATCH_WORKERS", raising=False)
    monkeypatch.delenv("RELIGION_SIMLI_SELECTOR_BATCH_WORKERS", raising=False)

    assert beta6_module._selector_batch_workers(tcm, 12) == 6
    assert beta6_module._selector_batch_workers(islam, 48) == 4
    assert beta6_module._selector_batch_workers(simli, 48) == 2
    assert beta6_module._selector_recovery_batch_workers(tcm, 4) == 4
    assert beta6_module._selector_recovery_batch_workers(islam, 4) == 4
    assert beta6_module._selector_recovery_batch_workers(simli, 4) == 4


def test_tcm_timeout_recovery_subbatches_run_in_parallel(monkeypatch, tmp_path):
    product = _tcm_profile(tmp_path / "tcm.sqlite3")
    fake = ParallelRecoverySelectorLLMClient()
    candidates = [
        _result(f"doc-{index:03d}", f"sharedterm tcm recovery source {index}", source_kind="materia_medica")
        for index in range(120)
    ]

    monkeypatch.delenv("RELIGION_SELECTOR_BATCH_SIZE", raising=False)
    monkeypatch.delenv("RELIGION_TCM_SELECTOR_BATCH_SIZE", raising=False)
    monkeypatch.delenv("RELIGION_SELECTOR_RECOVERY_BATCH_WORKERS", raising=False)
    monkeypatch.delenv("RELIGION_TCM_SELECTOR_RECOVERY_BATCH_WORKERS", raising=False)
    monkeypatch.setenv("RELIGION_TCM_SELECTOR_BATCH_WORKERS", "1")

    rows, ids, _reasoning, meta = beta6_module.select_rows_with_beta6_selector(
        product,
        "sharedterm tcm recovery",
        "ko",
        candidates,
        limit=100,
        llm_client=fake,
        model="gemma",
        cache_root=tmp_path / "tcm-parallel-recovery-cache",
    )

    assert fake.max_active_subbatches >= 4
    head_batch = meta["selectorBatches"][0]
    assert head_batch["recovered"] is True
    assert head_batch["recoverySubBatchCount"] == 4
    assert head_batch["recoveryBatchSize"] == 25
    assert head_batch["recoveryBatchWorkers"] == 4
    assert meta["selectorBatchTrace"][0]["recoveryBatchWorkers"] == 4
    assert meta["selectorBatchTrace"][0]["recoverySubBatchCount"] == 4
    assert meta["selectorBatchTrace"][0]["recoveryBatchSize"] == 25
    assert meta["selectorBatchTrace"][0]["timeoutSeconds"] == 90
    assert meta["selectorBatchTrace"][0]["elapsedExceededTimeout"] is False
    assert "timed out" in meta["selectorBatchTrace"][0]["recoveryError"]
    assert meta["selectorBatchTrace"][0]["recoveryErrorCount"] == 0
    assert "doc-000" in ids
    assert rows


def test_islam_timeout_recovery_subbatches_run_in_parallel(monkeypatch, tmp_path):
    product = _profile(tmp_path / "islam.sqlite3")
    fake = ParallelRecoverySelectorLLMClient()
    candidates = [
        _result(f"doc-{index:03d}", f"sharedterm islam recovery source {index}", source_kind="fiqh")
        for index in range(120)
    ]

    monkeypatch.delenv("RELIGION_SELECTOR_BATCH_SIZE", raising=False)
    monkeypatch.delenv("RELIGION_ISLAM_SELECTOR_BATCH_SIZE", raising=False)
    monkeypatch.delenv("RELIGION_SELECTOR_RECOVERY_BATCH_WORKERS", raising=False)
    monkeypatch.delenv("RELIGION_ISLAM_SELECTOR_RECOVERY_BATCH_WORKERS", raising=False)
    monkeypatch.setenv("RELIGION_ISLAM_SELECTOR_BATCH_WORKERS", "1")

    rows, ids, _reasoning, meta = beta6_module.select_rows_with_beta6_selector(
        product,
        "sharedterm islam recovery",
        "ko",
        candidates,
        limit=100,
        llm_client=fake,
        model="gemma",
        cache_root=tmp_path / "islam-parallel-recovery-cache",
    )

    assert fake.max_active_subbatches >= 4
    head_batch = meta["selectorBatches"][0]
    assert head_batch["recovered"] is True
    assert head_batch["recoverySubBatchCount"] == 4
    assert head_batch["recoveryBatchSize"] == 25
    assert head_batch["recoveryBatchWorkers"] == 4
    assert meta["selectorBatchTrace"][0]["recoveryBatchWorkers"] == 4
    assert meta["selectorBatchTrace"][0]["recoverySubBatchCount"] == 4
    assert meta["selectorBatchTrace"][0]["recoveryBatchSize"] == 25
    assert "doc-000" in ids
    assert rows


def test_selector_batch_trace_records_llm_pre_http_wait(monkeypatch, tmp_path):
    product = _tcm_profile(tmp_path / "tcm.sqlite3")
    fake = TraceReportingSelectorLLMClient()
    candidates = [
        _result(f"doc-{index:03d}", f"sharedterm tcm trace source {index}", source_kind="materia_medica")
        for index in range(120)
    ]

    monkeypatch.delenv("RELIGION_SELECTOR_BATCH_SIZE", raising=False)
    monkeypatch.delenv("RELIGION_TCM_SELECTOR_BATCH_SIZE", raising=False)
    monkeypatch.setenv("RELIGION_TCM_SELECTOR_BATCH_WORKERS", "1")

    rows, _ids, _reasoning, meta = beta6_module.select_rows_with_beta6_selector(
        product,
        "sharedterm tcm trace",
        "ko",
        candidates,
        limit=100,
        llm_client=fake,
        model="gemma",
        cache_root=tmp_path / "tcm-llm-trace-cache",
    )

    first_batch = meta["selectorBatchTrace"][0]
    assert first_batch["llmCallCount"] == 1
    assert first_batch["llmHttpStartedCount"] == 1
    assert first_batch["maxPreHttpWaitSec"] == 0.75
    assert first_batch["maxLlmElapsedSec"] == 1.25
    assert rows


def test_selector_batch_trace_separates_primary_and_recovery_llm_tail(monkeypatch, tmp_path):
    product = _tcm_profile(tmp_path / "tcm.sqlite3")
    fake = PhaseTraceTimeoutThenRecoveryLLMClient()
    candidates = [
        _result(f"doc-{index:03d}", f"sharedterm tcm phase trace source {index}", source_kind="materia_medica")
        for index in range(120)
    ]

    monkeypatch.delenv("RELIGION_SELECTOR_BATCH_SIZE", raising=False)
    monkeypatch.delenv("RELIGION_TCM_SELECTOR_BATCH_SIZE", raising=False)
    monkeypatch.delenv("RELIGION_SELECTOR_RECOVERY_BATCH_WORKERS", raising=False)
    monkeypatch.delenv("RELIGION_TCM_SELECTOR_RECOVERY_BATCH_WORKERS", raising=False)
    monkeypatch.setenv("RELIGION_TCM_SELECTOR_BATCH_WORKERS", "1")

    rows, _ids, _reasoning, meta = beta6_module.select_rows_with_beta6_selector(
        product,
        "sharedterm tcm phase trace",
        "ko",
        candidates,
        limit=100,
        llm_client=fake,
        model="gemma",
        cache_root=tmp_path / "tcm-phase-trace-cache",
    )

    first_batch = meta["selectorBatchTrace"][0]
    assert first_batch["primaryLlmCallCount"] == 1
    assert first_batch["primaryMaxLlmElapsedSec"] == 90.0
    assert first_batch["primaryMaxPreHttpWaitSec"] == 0.2
    assert first_batch["primaryMaxCandidateCount"] == 100
    assert first_batch["recoveryLlmCallCount"] == 4
    assert first_batch["recoveryMaxLlmElapsedSec"] == 8.0
    assert first_batch["recoveryMaxPreHttpWaitSec"] == 0.1
    assert first_batch["recoveryMaxCandidateCount"] == 25
    assert rows


def test_tcm_selector_primary_timeout_can_be_shorter_than_recovery_timeout(monkeypatch, tmp_path):
    product = _tcm_profile(tmp_path / "tcm.sqlite3")
    fake = PhaseTraceTimeoutThenRecoveryLLMClient()
    candidates = [
        _result(f"doc-{index:03d}", f"sharedterm tcm primary timeout source {index}", source_kind="materia_medica")
        for index in range(120)
    ]

    monkeypatch.delenv("RELIGION_SELECTOR_BATCH_SIZE", raising=False)
    monkeypatch.delenv("RELIGION_TCM_SELECTOR_BATCH_SIZE", raising=False)
    monkeypatch.delenv("RELIGION_SELECTOR_RECOVERY_BATCH_WORKERS", raising=False)
    monkeypatch.delenv("RELIGION_TCM_SELECTOR_RECOVERY_BATCH_WORKERS", raising=False)
    monkeypatch.setenv("RELIGION_SELECTOR_TIMEOUT_SECONDS", "90")
    monkeypatch.setenv("RELIGION_TCM_SELECTOR_PRIMARY_TIMEOUT_SECONDS", "45")
    monkeypatch.setenv("RELIGION_TCM_SELECTOR_BATCH_WORKERS", "1")

    _rows, _ids, _reasoning, meta = beta6_module.select_rows_with_beta6_selector(
        product,
        "sharedterm tcm primary timeout",
        "ko",
        candidates,
        limit=100,
        llm_client=fake,
        model="gemma",
        cache_root=tmp_path / "tcm-primary-timeout-cache",
    )

    first_batch = meta["selectorBatchTrace"][0]
    assert first_batch["primaryTimeoutSeconds"] == 45
    assert first_batch["recoveryTimeoutSeconds"] == 90
    assert fake.selector_calls[0]["timeout_seconds"] == 45
    assert all(call["timeout_seconds"] == 90 for call in fake.selector_calls[1:5])


def test_simli_selector_has_product_specific_rate_limit_retry_defaults(monkeypatch, tmp_path):
    simli = _simli_profile(tmp_path / "psych.sqlite3")

    monkeypatch.delenv("RELIGION_SELECTOR_RATE_LIMIT_RETRIES", raising=False)
    monkeypatch.delenv("RELIGION_SIMLI_SELECTOR_RATE_LIMIT_RETRIES", raising=False)
    monkeypatch.delenv("RELIGION_SELECTOR_RATE_LIMIT_BACKOFF_SECONDS", raising=False)
    monkeypatch.delenv("RELIGION_SIMLI_SELECTOR_RATE_LIMIT_BACKOFF_SECONDS", raising=False)

    assert beta6_module._selector_rate_limit_retries(simli) == 3
    assert beta6_module._selector_rate_limit_backoff_seconds(1, simli) == 5.0


def test_selector_retries_rate_limited_batch_before_subbatch_or_local_recovery(monkeypatch, tmp_path):
    product = _tcm_profile(tmp_path / "tcm.sqlite3")
    fake = RateLimitOnceSelectorLLMClient()
    candidates = [
        _result(f"doc-{index:03d}", f"sharedterm tcm rate limit source {index}", source_kind="materia_medica")
        for index in range(120)
    ]

    monkeypatch.delenv("RELIGION_SELECTOR_BATCH_SIZE", raising=False)
    monkeypatch.delenv("RELIGION_TCM_SELECTOR_BATCH_SIZE", raising=False)
    monkeypatch.setenv("RELIGION_TCM_SELECTOR_BATCH_WORKERS", "1")
    monkeypatch.setenv("RELIGION_SELECTOR_RATE_LIMIT_BACKOFF_SECONDS", "0")
    monkeypatch.setenv("RELIGION_SELECTOR_RATE_LIMIT_RETRIES", "1")

    rows, ids, _reasoning, meta = beta6_module.select_rows_with_beta6_selector(
        product,
        "sharedterm tcm rate limit",
        "ko",
        candidates,
        limit=100,
        llm_client=fake,
        model="gemma",
        cache_root=tmp_path / "tcm-rate-limit-cache",
    )

    assert [len(call["ids"]) for call in fake.selector_calls] == [100, 100, 20, 20]
    assert meta["selectorBatchErrors"] == []
    assert meta["selectorLocalRecoveryCount"] == 0
    assert all(batch["rateLimitRetryCount"] == 1 for batch in meta["selectorBatches"])
    assert all(not batch["recovered"] for batch in meta["selectorBatches"])
    assert "doc-100" in ids
    assert rows


def test_simli_recovery_subbatches_retry_rate_limit_before_local_recovery(monkeypatch, tmp_path):
    product = _simli_profile(tmp_path / "psych.sqlite3")
    fake = TimeoutThenRateLimitedSubBatchSelectorLLMClient()
    candidates = [
        _result(f"doc-{index:03d}", f"sharedterm simli recovery source {index}", source_kind="guideline")
        for index in range(30)
    ]

    monkeypatch.delenv("RELIGION_SIMLI_SELECTOR_BATCH_SIZE", raising=False)
    monkeypatch.setenv("RELIGION_SIMLI_SELECTOR_BATCH_WORKERS", "1")
    monkeypatch.setenv("RELIGION_SIMLI_SELECTOR_RATE_LIMIT_RETRIES", "1")
    monkeypatch.setenv("RELIGION_SIMLI_SELECTOR_RATE_LIMIT_BACKOFF_SECONDS", "0")

    rows, ids, _reasoning, meta = beta6_module.select_rows_with_beta6_selector(
        product,
        "sharedterm simli recovery",
        "ko",
        candidates,
        limit=100,
        llm_client=fake,
        model="gemma",
        cache_root=tmp_path / "simli-recovery-rate-limit-cache",
    )

    assert meta["selectorBatchErrors"] == []
    assert meta["selectorLocalRecoveryCount"] == 0
    assert all(batch["recovered"] for batch in meta["selectorBatches"])
    assert all(not batch["localRecovery"] for batch in meta["selectorBatches"])
    assert sum(batch["rateLimitRetryCount"] for batch in meta["selectorBatches"]) >= 3
    assert "doc-000" in ids
    assert rows


def test_beta6_candidate_collection_scans_every_generated_keyword(monkeypatch, tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    db_path.touch()
    profile = _profile(db_path)
    searched_queries = []
    keywords = ["kw1", "kw2", "kw3", "kw4", "kw5", "kw6"]

    def fake_search(product, query, *, limit=8, language=""):
        searched_queries.append(query)
        if query in keywords:
            return [_result(f"doc-{query}", f"{query} exact source text", source_kind="fiqh")]
        return []

    monkeypatch.setattr(beta6_module, "search_documents", fake_search)

    rows = beta6_module.collect_candidate_rows(
        profile,
        "root question",
        language="en",
        limit=6,
        keywords=keywords,
        initial=[],
    )

    assert "kw5" in searched_queries
    assert "kw6" in searched_queries
    assert {row.canonical_id for row in rows} >= {"doc-kw5", "doc-kw6"}


def test_generic_mcq_fast_candidate_collection_continues_when_frontier_has_low_coverage(monkeypatch, tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    db_path.touch()
    profile = _profile(db_path)
    searched_queries = []

    def fake_search(product, query, *, limit=8, language="", max_results=None, candidate_multiplier=None):
        del product, language, max_results, candidate_multiplier
        searched_queries.append(query)
        if query == "broad":
            return [
                _result(
                    f"broad-{index}",
                    "unrelated generic source text",
                    source_kind="scripture_window" if index % 2 == 0 else "hadith",
                )
                for index in range(limit)
            ]
        if query == "specific":
            return [_result("specific-doc", "musical epilepsy temporal lobe pathology", source_kind="fiqh")]
        return []

    monkeypatch.setattr(beta6_module, "search_documents", fake_search)

    beta6_module.collect_candidate_rows(
        profile,
        """Which lobe is associated with musical epilepsy?

A. parietal
B. temporal
C. occipital
D. frontal""",
        language="en",
        limit=3,
        keywords=["broad", "specific"],
        initial=[],
        fast_mode=True,
    )

    assert "specific" in searched_queries


def test_beta6_candidate_collection_uses_lawkey_sized_per_keyword_limit_against_real_db(monkeypatch, tmp_path):
    db_path = tmp_path / "wide.sqlite3"
    _make_many_precedents_db(db_path, count=720)
    profile = _profile(db_path)

    monkeypatch.delenv("RELIGION_SEARCH_RESULT_LIMIT_MAX", raising=False)
    monkeypatch.setenv("RELIGION_BETA6_PER_KEYWORD_LIMIT", "700")

    rows = beta6_module.collect_candidate_rows(
        profile,
        "nohit",
        language="en",
        limit=700,
        keywords=["sharedterm"],
        initial=[],
    )

    assert len(rows) == 700
    assert rows[-1].canonical_id == "doc-699"


def test_beta6_generates_additional_keyword_rounds_until_candidates_are_filled(monkeypatch, tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    db_path.touch()
    profile = _profile(db_path)
    fake = IterativeKeywordLLMClient()
    searched_queries = []

    monkeypatch.setenv("RELIGION_BETA6_TOP_K_PRECEDENTS", "3")
    monkeypatch.setenv("RELIGION_BETA6_MAX_TOP_K_PRECEDENTS", "3")
    monkeypatch.setenv("RELIGION_BETA6_KEYWORD_ROUNDS", "2")

    def fake_search(product, query, *, limit=8, language=""):
        searched_queries.append(query)
        if query.startswith("latekw"):
            return [_result(f"doc-late-{index}", f"{query} source text {index}", source_kind="fiqh") for index in range(3)]
        return []

    monkeypatch.setattr(beta6_module, "search_documents", fake_search)

    rows, selector = beta6_module.select_rows_with_beta6_llm(
        profile,
        "root question",
        "en",
        limit=3,
        llm_client=fake,
        model="gemma",
        provider="fixture",
    )

    assert any("Additional retrieval" in call["prompt"] for call in fake.calls if "keyword generator" in call["system"])
    assert any(query.startswith("latekw") for query in searched_queries)
    assert selector["candidateCount"] == 3
    assert selector["keywordRounds"][0]["candidateCount"] == 0
    assert selector["keywordRounds"][-1]["candidateCount"] == 3
    assert selector["keywords"][:3] == ["nohit-one", "nohit-two", "nohit-three"]
    assert "latekw" in selector["keywords"]
    assert [row.canonical_id for row in rows] == ["doc-late-0", "doc-late-1", "doc-late-2"]


def test_beta6_keyword_rounds_do_not_starve_late_specific_terms_after_broad_pool_fills(monkeypatch, tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    db_path.touch()
    profile = _profile(db_path)
    searched_queries = []
    initial = [
        _result("doc-broad-scripture-1", "broadkw generic halal text", source_kind="scripture"),
        _result("doc-broad-fiqh-1", "broadkw generic fiqh text", source_kind="fiqh"),
        _result("doc-broad-scripture-2", "broadkw generic second scripture", source_kind="scripture"),
        _result("doc-broad-fiqh-2", "broadkw generic second fiqh", source_kind="fiqh"),
    ]

    def fake_search(product, query, *, limit=8, language=""):
        searched_queries.append(query)
        if query == "late-specific":
            return [_result("doc-late-specific", "late-specific decisive principle text", source_kind="fiqh")]
        if query == "broadkw":
            return list(initial)
        return []

    monkeypatch.setattr(beta6_module, "search_documents", fake_search)

    rows = beta6_module.collect_candidate_rows(
        profile,
        "root question",
        language="en",
        limit=4,
        keywords=["broadkw", "late-specific"],
        initial=initial,
    )

    assert "late-specific" in searched_queries
    assert "doc-late-specific" in {row.canonical_id for row in rows}


def test_beta6_runs_minimum_keyword_rounds_even_when_first_broad_round_fills_frontier(monkeypatch, tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    db_path.touch()
    profile = _profile(db_path)
    fake = BroadThenSpecificKeywordLLMClient()

    monkeypatch.setenv("RELIGION_BETA6_TOP_K_PRECEDENTS", "4")
    monkeypatch.setenv("RELIGION_BETA6_MAX_TOP_K_PRECEDENTS", "4")
    monkeypatch.setenv("RELIGION_BETA6_FRONTIER_TARGET", "4")
    monkeypatch.setenv("RELIGION_BETA6_FRONTIER_STOP_FLOOR", "4")
    monkeypatch.setenv("RELIGION_BETA6_KEYWORD_ROUNDS", "2")
    monkeypatch.setenv("RELIGION_BETA6_MIN_KEYWORD_ROUNDS", "2")

    def fake_search(product, query, *, limit=8, language=""):
        if query == "late-specific":
            return [_result("doc-late-specific", "late-specific decisive principle text", source_kind="fiqh")]
        if query == "broadkw":
            return [
                _result("doc-broad-scripture-1", "broadkw generic halal text", source_kind="scripture"),
                _result("doc-broad-fiqh-1", "broadkw generic fiqh text", source_kind="fiqh"),
                _result("doc-broad-scripture-2", "broadkw generic second scripture", source_kind="scripture"),
                _result("doc-broad-fiqh-2", "broadkw generic second fiqh", source_kind="fiqh"),
            ]
        return []

    monkeypatch.setattr(beta6_module, "search_documents", fake_search)

    rows, selector = beta6_module.select_rows_with_beta6_llm(
        profile,
        "root question",
        "en",
        limit=4,
        llm_client=fake,
        model="gemma",
        provider="fixture",
    )

    assert any("Additional retrieval" in call["prompt"] for call in fake.calls if "keyword generator" in call["system"])
    assert "late-specific" in selector["keywords"]
    assert rows[0].canonical_id == "doc-late-specific"


def test_beta6_keyword_round_cache_prevents_repeat_query_keyword_drift(monkeypatch, tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    db_path.touch()
    profile = _profile(db_path)
    fake = AlternatingKeywordLLMClient()
    searched_queries = []

    monkeypatch.setenv("RELIGION_BETA6_TOP_K_PRECEDENTS", "4")
    monkeypatch.setenv("RELIGION_BETA6_MAX_TOP_K_PRECEDENTS", "4")
    monkeypatch.setenv("RELIGION_BETA6_FRONTIER_TARGET", "4")
    monkeypatch.setenv("RELIGION_BETA6_FRONTIER_STOP_FLOOR", "4")
    monkeypatch.setenv("RELIGION_BETA6_KEYWORD_ROUNDS", "1")
    monkeypatch.setenv("RELIGION_BETA6_MIN_KEYWORD_ROUNDS", "1")

    def fake_search(product, query, *, limit=8, language=""):
        searched_queries.append(query)
        if query == "stablekw":
            return [_result(f"doc-stable-{index}", f"stablekw source text {index}", source_kind="fiqh") for index in range(4)]
        if query == "driftkw":
            return [_result(f"doc-drift-{index}", f"driftkw source text {index}", source_kind="fiqh") for index in range(4)]
        return []

    monkeypatch.setattr(beta6_module, "search_documents", fake_search)
    cache_root = tmp_path / "cache"

    rows1, selector1 = beta6_module.select_rows_with_beta6_llm(
        profile,
        "same repeated question",
        "en",
        limit=4,
        llm_client=fake,
        model="gemma",
        provider="fixture",
        cache_root=cache_root,
    )
    rows2, selector2 = beta6_module.select_rows_with_beta6_llm(
        profile,
        "same repeated question",
        "en",
        limit=4,
        llm_client=fake,
        model="gemma",
        provider="fixture",
        cache_root=cache_root,
    )

    assert fake.keyword_calls == 1
    assert selector1["keywordCacheMisses"] == 1
    assert selector2["keywordCacheHits"] == 1
    assert selector2["keywordCacheMisses"] == 0
    assert selector1["keywords"] == selector2["keywords"] == ["stablekw"]
    assert [row.canonical_id for row in rows1] == [row.canonical_id for row in rows2]
    assert not any(query == "driftkw" for query in searched_queries)


def test_beta6_candidate_search_cache_reuses_per_keyword_db_results(monkeypatch, tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    db_path.touch()
    profile = _profile(db_path)
    search_counts: dict[str, int] = {}

    def fake_search(product, query, *, limit=8, language=""):
        search_counts[query] = search_counts.get(query, 0) + 1
        if query == "stablekw":
            return [_result(f"doc-stable-{index}", f"stablekw source text {index}", source_kind="fiqh") for index in range(4)]
        return []

    monkeypatch.setattr(beta6_module, "search_documents", fake_search)
    cache_root = tmp_path / "cache"

    rows1 = beta6_module.collect_candidate_rows(
        profile,
        "root question",
        language="en",
        limit=4,
        keywords=["stablekw"],
        initial=[],
        cache_root=cache_root,
    )
    rows2 = beta6_module.collect_candidate_rows(
        profile,
        "root question",
        language="en",
        limit=4,
        keywords=["stablekw"],
        initial=[],
        cache_root=cache_root,
    )

    assert search_counts["stablekw"] == 1
    assert [row.canonical_id for row in rows1] == [row.canonical_id for row in rows2] == [
        "doc-stable-0",
        "doc-stable-1",
        "doc-stable-2",
        "doc-stable-3",
    ]


def test_beta6_result_summary_exposes_selector_cache_metrics(monkeypatch, tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    db_path.touch()
    fake = AlternatingKeywordLLMClient()

    monkeypatch.setenv("RELIGION_BETA6_TOP_K_PRECEDENTS", "4")
    monkeypatch.setenv("RELIGION_BETA6_MAX_TOP_K_PRECEDENTS", "4")
    monkeypatch.setenv("RELIGION_BETA6_FRONTIER_TARGET", "4")
    monkeypatch.setenv("RELIGION_BETA6_FRONTIER_STOP_FLOOR", "4")
    monkeypatch.setenv("RELIGION_BETA6_KEYWORD_ROUNDS", "1")
    monkeypatch.setenv("RELIGION_BETA6_MIN_KEYWORD_ROUNDS", "1")

    def fake_search(product, query, *, limit=8, language=""):
        if query == "stablekw":
            return [_result(f"doc-stable-{index}", f"stablekw source text {index}", source_kind="fiqh") for index in range(4)]
        return []

    monkeypatch.setattr(beta6_module, "search_documents", fake_search)
    runtime = Beta6JobManager({"islam": _profile(db_path)}, runs_root=tmp_path / "runs", llm_client=fake)

    runtime.answer_sync(product="islam", query="same repeated question", language="en", limit=4)
    result = runtime.answer_sync(product="islam", query="same repeated question", language="en", limit=4)

    assert result["selector"]["keywordCacheHits"] == 1
    assert result["selector"]["candidateSearchCacheHits"] >= 1
    assert result["beta6"]["keywordCacheHits"] == result["selector"]["keywordCacheHits"]
    assert result["beta6"]["keywordCacheMisses"] == result["selector"]["keywordCacheMisses"]
    assert result["beta6"]["candidateSearchCacheHits"] == result["selector"]["candidateSearchCacheHits"]
    assert result["beta6"]["candidateSearchCacheMisses"] == result["selector"]["candidateSearchCacheMisses"]


def test_islam_candidate_search_plan_does_not_add_generic_role_only_terms(tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    db_path.touch()
    profile = _profile(db_path)

    plan = beta6_module.build_beta6_candidate_search_plan(
        profile,
        "사회주의는 하람임?",
        ["الاشتراكية", "حرام", "الملكية الخاصة", "islamic economics"],
        target_limit=100,
        per_keyword_limit=80,
    )
    planned_queries = [query for _label, query, _limit in plan]

    assert not any(query.strip() == "quran scripture قرآن" for query in planned_queries)
    assert not any("quran scripture" in query.lower() for query in planned_queries)
    assert not any("hadith sunnah" in query.lower() for query in planned_queries)


def test_beta6_search_plan_sanitizes_broad_generated_keyword_phrases(tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    db_path.touch()
    profile = _profile(db_path)

    plan = beta6_module.build_beta6_candidate_search_plan(
        profile,
        "사회주의는 하람임?",
        ["socialism in islam", "property rights", "islamic economics", "حرام"],
        target_limit=100,
        per_keyword_limit=80,
    )
    planned_queries = [query for _label, query, _limit in plan]

    assert "socialism in islam" not in planned_queries
    assert "islamic economics" not in planned_queries
    assert "socialism" in planned_queries
    assert "property rights" in planned_queries
    assert "حرام" in planned_queries


def test_generic_mcq_candidate_search_plan_adds_option_context_queries(tmp_path, monkeypatch):
    monkeypatch.delenv("RELIGION_MCQ_HEURISTICS_ENABLED", raising=False)
    db_path = tmp_path / "islam.sqlite3"
    db_path.touch()
    profile = _profile(db_path)
    query = """010. 재무 심사와 관련하여, 이자부 예금을 나타내는 재무 비율은 총 시가총액의 몇 퍼센트보다 낮아야 한다는 것이 일반적으로 인정됩니까?

A. 5%
B. 10 %
C. 25 %
D. 30 %"""

    plan = beta6_module.build_beta6_candidate_search_plan(
        profile,
        query,
        ["financial screening", "interest-bearing deposits"],
        target_limit=100,
        per_keyword_limit=80,
    )

    option_queries = [(label, search_query) for label, search_query, _limit in plan if label.startswith("mcq_option_")]
    assert option_queries == [
        ("mcq_option_01", "재무 심사와 관련하여 이자부 예금을 나타내는 재무 비율은 총 시가총액의 몇 퍼센트보다 낮아야 한다는 것이 일반적으로 인정됩니까 5%"),
        ("mcq_option_02", "재무 심사와 관련하여 이자부 예금을 나타내는 재무 비율은 총 시가총액의 몇 퍼센트보다 낮아야 한다는 것이 일반적으로 인정됩니까 10 %"),
        ("mcq_option_03", "재무 심사와 관련하여 이자부 예금을 나타내는 재무 비율은 총 시가총액의 몇 퍼센트보다 낮아야 한다는 것이 일반적으로 인정됩니까 25 %"),
        ("mcq_option_04", "재무 심사와 관련하여 이자부 예금을 나타내는 재무 비율은 총 시가총액의 몇 퍼센트보다 낮아야 한다는 것이 일반적으로 인정됩니까 30 %"),
    ]


def test_generic_mcq_candidate_search_plan_prioritizes_keywords_and_stem_question(tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    db_path.touch()
    profile = _profile(db_path)
    query = """006. 제한된 투자 계좌 보유자에게 제공되는 것과 동일한 수준의 정보를 무제한 투자 계좌 보유자에게 제공하는 것은 주로 다음 문제로 인해 어렵습니다.

A. 자금 혼합
B. 고객의 기밀 유지
C. 상업적 위험
D. 기업 지배구조

위 객관식 문제의 정답 보기ID 하나만 고르세요.
보기ID 후보: A, B, C, D
답변 첫 줄은 반드시 `정답: <보기ID>` 형식으로 시작하세요."""

    plan = beta6_module.build_beta6_candidate_search_plan(
        profile,
        query,
        ["investment information asymmetry", "تفاوت المعلومات"],
        target_limit=100,
        per_keyword_limit=80,
    )

    assert plan[0][0] == "keyword_01"
    question = next(search_query for label, search_query, _limit in plan if label == "question")
    assert "정답 보기ID" not in question
    assert "보기ID 후보" not in question
    assert "자금 혼합" not in question
    assert question == "제한된 투자 계좌 보유자에게 제공되는 것과 동일한 수준의 정보를 무제한 투자 계좌 보유자에게 제공하는 것은 주로 다음 문제로 인해 어렵습니다."


def test_catholic_exact_citation_mcq_candidate_search_plan_prioritizes_citation_frame(tmp_path):
    db_path = tmp_path / "catholic.sqlite3"
    db_path.touch()
    profile = ProductProfile(
        key="catholic",
        name="Catholic Test",
        db_path=db_path,
        db_shape="precedents",
        languages=("ko", "en"),
        default_language="ko",
        theme="",
        safety_notice="",
    )
    query = """2. “우리가 아우의 일로 말미암아 범죄하였도다”(창 42:21) 에서 ‘아우’는 누구인가?

① 레위
② 베냐민
③ 르우벤
④ 요셉"""

    plan = beta6_module.build_beta6_candidate_search_plan(
        profile,
        query,
        ["Genesis", "Benjamin", "Joseph"],
        target_limit=30,
        per_keyword_limit=30,
    )

    labels = [label for label, _query, _limit in plan[:4]]
    planned_queries = [search_query for _label, search_query, _limit in plan[:4]]
    assert labels[0] == "question"
    assert any("Gen 42:21" in search_query for search_query in planned_queries)
    assert "Genesis" not in planned_queries[:2]


def test_catholic_exact_citation_mcq_candidate_collection_scans_option_context_after_full_question_frontier(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "catholic.sqlite3"
    db_path.touch()
    profile = ProductProfile(
        key="catholic",
        name="Catholic Test",
        db_path=db_path,
        db_shape="precedents",
        languages=("ko", "en"),
        default_language="ko",
        theme="",
        safety_notice="",
    )
    query = """2. “우리가 아우의 일로 말미암아 범죄하였도다”(창 42:21) 에서 ‘아우’는 누구인가?

① 레위
② 베냐민
③ 르우벤
④ 요셉"""

    def fixture_row(identifier: str, citation: str, text: str) -> SearchResult:
        return SearchResult(
            canonical_id=identifier,
            title="Genesis",
            citation=citation,
            authority_body="fixture",
            source_date="",
            case_name="Genesis",
            case_type="scripture_window",
            full_text=text,
            source_dataset="catholic/scripture",
            source_path=identifier,
            source_kind="scripture",
            authority_level=100,
        )

    question_rows = [
        fixture_row(
            f"question-{index}",
            f"Gen 42:{index + 1}",
            "그들이 서로 말하되 우리가 아우의 일로 말미암아 범죄하였도다 그가 우리에게 애걸할 때 마음의 괴로움을 보고도 듣지 아니하였으므로",
        )
        for index in range(30)
    ]
    joseph_anchor = fixture_row("joseph-anchor", "Gen 42:6", "Joseph was governor and his brothers bowed before him.")
    irrelevant_brother = fixture_row("irrelevant-brother", "Gen 4:8", "Cain spoke with Abel his brother.")

    def fake_search(_product, search_query, *, limit=8, language=""):
        del _product, limit, language
        if "요셉" in search_query or "Joseph" in search_query:
            return [irrelevant_brother, joseph_anchor]
        if "창 42:21" in search_query or "아우" in search_query:
            return question_rows
        return []

    monkeypatch.setattr(beta6_module, "search_documents", fake_search)
    cache_stats = {"hits": 0, "misses": 0, "trace": []}

    rows = beta6_module.collect_candidate_rows(
        profile,
        query,
        language="ko",
        limit=30,
        keywords=["Genesis"],
        initial=[],
        cache_stats=cache_stats,
        fast_mode=True,
    )

    labels = [item["label"] for item in cache_stats["trace"]]
    assert "mcq_option_04" in labels
    assert any(row.canonical_id == "joseph-anchor" for row in rows)
    assert not any(row.canonical_id == "irrelevant-brother" for row in rows)


def test_non_mcq_candidate_search_plan_does_not_add_option_context_queries(tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    db_path.touch()
    profile = _profile(db_path)

    plan = beta6_module.build_beta6_candidate_search_plan(
        profile,
        "사회주의는 하람임?",
        ["socialism", "property rights"],
        target_limit=100,
        per_keyword_limit=80,
    )

    assert not any(label.startswith("mcq_option_") for label, _query, _limit in plan)


def test_islam_beta6_search_plan_drops_count_words_from_prayer_keyword(tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    db_path.touch()
    profile = _profile(db_path)

    plan = beta6_module.build_beta6_candidate_search_plan(
        profile,
        "하루 몇번 기도해야함?",
        ["five daily prayers", "prayer times", "عدد الصلوات"],
        target_limit=100,
        per_keyword_limit=80,
    )
    planned_queries = [query for _label, query, _limit in plan]

    assert "five daily prayers" not in planned_queries
    assert "five" not in planned_queries
    assert "daily" not in planned_queries
    assert "prayers" in planned_queries
    assert "prayer times" in planned_queries


def test_simli_source_role_keywords_are_contextualized_with_question_focus_terms(tmp_path):
    db_path = tmp_path / "psych.sqlite"
    db_path.touch()
    profile = ProductProfile(
        key="simli",
        name="Simli",
        db_path=db_path,
        db_shape="documents",
        languages=("ko", "en"),
        default_language="ko",
        theme="simli",
        safety_notice="notice",
    )

    plan = beta6_module.build_beta6_candidate_search_plan(
        profile,
        "ADHD와 불안장애가 헷갈릴 때 DSM과 가이드라인 관점으로 정리해줘",
        ["DSM-5", "임상 가이드라인", "Differential diagnosis"],
        target_limit=100,
        per_keyword_limit=80,
    )
    planned_queries = [query for _label, query, _limit in plan]

    assert "DSM-5" not in planned_queries
    assert "임상 가이드라인" not in planned_queries
    assert "ADHD anxiety DSM-5" in planned_queries
    assert "ADHD anxiety 임상 가이드라인" in planned_queries
    assert "Differential diagnosis" in planned_queries


def test_simli_search_plan_sanitizes_long_generated_diagnosis_phrases(tmp_path):
    db_path = tmp_path / "psych.sqlite"
    db_path.touch()
    profile = ProductProfile(
        key="simli",
        name="Simli",
        db_path=db_path,
        db_shape="documents",
        languages=("ko", "en"),
        default_language="ko",
        theme="simli",
        safety_notice="notice",
    )

    plan = beta6_module.build_beta6_candidate_search_plan(
        profile,
        "성인 ADHD와 범불안장애가 헷갈릴 때 정리해줘",
        ["Adult ADHD", "Generalized Anxiety Disorder", "DSM-5 differential diagnosis", "comorbidity"],
        target_limit=100,
        per_keyword_limit=80,
    )
    planned_queries = [query for _label, query, _limit in plan]

    assert "Adult ADHD" not in planned_queries
    assert "Generalized Anxiety Disorder" not in planned_queries
    assert "ADHD" not in planned_queries
    assert "anxiety" not in planned_queries
    assert "ADHD anxiety DSM-5 differential diagnosis" in planned_queries


def test_simli_search_plan_caps_each_query_below_lawkey_fts_limit(tmp_path, monkeypatch):
    monkeypatch.delenv("RELIGION_SIMLI_BETA6_PER_QUERY_LIMIT", raising=False)
    db_path = tmp_path / "psych.sqlite"
    db_path.touch()
    profile = ProductProfile(
        key="simli",
        name="Simli",
        db_path=db_path,
        db_shape="documents",
        languages=("ko", "en"),
        default_language="ko",
        theme="simli",
        safety_notice="notice",
    )

    plan = beta6_module.build_beta6_candidate_search_plan(
        profile,
        "성인 ADHD와 범불안장애가 헷갈릴 때 정리해줘",
        ["comorbidity", "executive dysfunction", "인지적 왜곡"],
        target_limit=400,
        per_keyword_limit=700,
    )

    assert plan
    assert all(query_limit <= 120 for _label, _query, query_limit in plan)


def test_beta6_candidate_diversity_preserves_relevance_order_before_role_fill(tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    db_path.touch()
    profile = _profile(db_path)
    rows = [
        _result("doc-fiqh-top", "direct hukm haram question match", source_kind="fiqh", school="hanafi"),
        _result("doc-scripture-lower", "broad scripture source", source_kind="scripture"),
        _result("doc-hadith-lower", "broad hadith source", source_kind="hadith"),
    ]

    selected = beta6_module.diversify_beta6_candidates(profile, rows, limit=3)

    assert selected[0].canonical_id == "doc-fiqh-top"
    assert {row.canonical_id for row in selected} == {"doc-fiqh-top", "doc-scripture-lower", "doc-hadith-lower"}


def test_islam_claim_cards_classify_tafsir_on_quran_as_tafsir_not_scripture(tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    db_path.touch()
    profile = _profile(db_path)
    selected_records = [
        {
            "file_id": "doc-tafsir",
            "document_title": "Maarif al-Quran",
            "case_number": "Maarif on Quran 2:173",
            "doc_type": "commentary_unit",
            "source_group": "structured_precedent",
            "extracted_text": "[META]\nsource_kind: commentary\n\nCommentary on halal and haram.",
            "metadata": {"sourceKind": "commentary", "school": "deobandi"},
        }
    ]
    selected_evidence = [
        {
            "id": "doc-tafsir",
            "label": "S1",
            "title": "Maarif al-Quran",
            "citation": "Maarif al-Quran on Quran 2:173",
            "sourceKind": "commentary",
            "school": "deobandi",
        }
    ]

    cards = beta6_module.build_claim_cards(profile, "하람 근거", selected_records, selected_evidence, language="ko")

    assert cards[0]["role"] == "tafsir"


def test_beta6_runtime_builds_claim_cards_and_writer_uses_claim_ledger(tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    _make_islam_school_db(db_path)
    fake = CapturingBeta6LLMClient()
    runtime = Beta6JobManager({"islam": _profile(db_path)}, runs_root=tmp_path / "runs", llm_client=fake)

    result = runtime.answer_sync(product="islam", query="결혼할 때 보호자가 필요한가 학파별로 알려줘", language="ko", limit=3)

    writer_call = [call for call in fake.calls if "source-grounded answer engine" in call["messages"][0]["content"]][-1]
    assert result["claimCards"]
    assert result["passageWindows"]
    assert result["engine"]["handoffKeys"] == [
        "answerSections",
        "citationMap",
        "passages",
        "selectedEvidence",
        "claimCards",
        "candidateClaimCards",
        "citedClaimCards",
        "passageWindows",
        "answerPlan",
        "coverageReport",
    ]
    first_card = result["claimCards"][0]
    assert first_card["contextSummary"]
    assert first_card["claimSummary"]
    assert first_card["quote"]
    assert first_card["span"]["exact"] == first_card["quote"]
    assert result["citationMap"][first_card["claimId"]]["id"] == first_card["sourceId"]
    assert "[selected claim ledger]" in writer_call["prompt"]
    assert "context_summary:" in writer_call["prompt"]
    assert "claim_summary:" in writer_call["prompt"]


def test_beta6_splits_cited_claim_cards_from_answer_and_plan(tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    db_path.touch()
    profile = _profile(db_path)
    claim_cards = [
        {"claimId": "C1", "label": "S1", "sourceId": "doc-1", "claimSummary": "first"},
        {"claimId": "C2", "label": "S2", "sourceId": "doc-2", "claimSummary": "second"},
        {"claimId": "C3", "label": "S3", "sourceId": "doc-3", "claimSummary": "third"},
    ]
    answer_plan = {"bodyClaimIds": ["C1", "C2"], "coverageRequiredClaimIds": ["C3"]}

    split = beta6_module.split_claim_cards_for_handoff(
        profile,
        "본문은 둘째 근거를 직접 인용하고 [C2], 셋째 근거는 원문 라벨로도 인용한다 [S3]. 가짜 [C99]는 무시한다.",
        claim_cards,
        answer_plan,
    )

    assert [card["claimId"] for card in split["candidateClaimCards"]] == ["C1", "C2", "C3"]
    assert [card["claimId"] for card in split["citedClaimCards"]] == ["C2", "C3"]
    assert [card["claimId"] for card in split["uncitedCandidateClaimCards"]] == ["C1"]
    assert split["candidateClaimIds"] == ["C1", "C2", "C3"]
    assert split["citedClaimIds"] == ["C2", "C3"]


def test_islam_answer_plan_keeps_minimum_claim_breadth_when_planner_is_sparse(tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    db_path.touch()
    profile = _profile(db_path)
    claim_cards = [
        {
            "claimId": f"C{index}",
            "label": f"S{index}",
            "sourceId": f"doc-{index:03d}",
            "claimSummary": f"claim {index}",
            "contextSummary": f"context {index}",
            "quote": f"quote {index}",
        }
        for index in range(1, 21)
    ]

    plan = beta6_module._coerce_answer_plan(
        profile,
        "사회주의는 하람임? 학파와 원칙별로 근거를 정리해줘",
        "ko",
        claim_cards,
        {
            "body_claim_ids": ["C1", "C6", "C18"],
            "coverage_required_claim_ids": ["C1", "C6", "C18"],
            "claim_groups": [{"title": "좁은 계획", "claim_ids": ["C1", "C6"], "summary": "일부만 포함"}],
            "answer_outline": ["세 claim만 쓰려는 계획"],
            "citation_policy": "cite",
        },
        status="completed",
        mode="llm_answer_planner",
        provider="fixture",
        model="gemma",
    )

    assert plan["bodyClaimIds"][:3] == ["C1", "C6", "C18"]
    assert len(plan["bodyClaimIds"]) >= 10
    assert len(plan["coverageRequiredClaimIds"]) >= 10
    assert any(claim_id not in {"C1", "C6", "C18"} for claim_id in plan["coverageRequiredClaimIds"])


def test_religious_generic_products_use_rich_fast_writer_policy_without_concise_only_prompt(tmp_path):
    selected_records = [
        {
            "file_id": f"doc-{index}",
            "case_number": f"Source {index}",
            "document_title": f"Document {index}",
            "extracted_text": (
                "This selected source gives a relevant doctrinal context, a limit, "
                "and a retrieval boundary that should be explained without padding."
            ),
        }
        for index in range(1, 5)
    ]
    claim_cards = [
        {
            "claimId": f"C{index}",
            "label": f"S{index}",
            "sourceId": f"doc-{index}",
            "claimSummary": f"relevant source-grounded claim {index}",
            "contextSummary": f"context layer {index}",
            "quote": f"quote {index}",
        }
        for index in range(1, 5)
    ]
    answer_plan = {
        "bodyClaimIds": ["C1", "C2", "C3", "C4"],
        "coverageRequiredClaimIds": ["C1", "C2", "C3", "C4"],
        "answerOutline": ["source layers", "comparisons", "limits"],
        "citationPolicy": "cite every substantive paragraph",
    }

    for key in ("buddhist", "catholic", "hindu"):
        profile = ProductProfile(
            key=key,
            name=f"{key.title()} AI",
            db_path=tmp_path / f"{key}.sqlite3",
            db_shape="precedents",
            languages=("ko", "en"),
            default_language="ko",
            theme="gallery-canvas",
            safety_notice="source-grounded study aid",
        )

        messages = beta6_module.build_beta6_messages(
            profile,
            "핵심 교리와 반대 근거까지 풍부하게 설명해줘",
            "ko",
            selected_records,
            claim_cards=claim_cards,
            answer_plan=answer_plan,
        )
        prompt = messages[1]["content"]

        assert "[minimum answer depth]" in prompt
        assert "source-proportional" in prompt
        assert "Do not pad" in prompt
        assert "Return a concise cited answer" not in prompt


def test_religious_generic_answer_plan_policy_requests_source_layers_and_gaps(tmp_path):
    claim_cards = [
        {
            "claimId": "C1",
            "label": "S1",
            "sourceId": "doc-1",
            "claimSummary": "primary source claim",
            "contextSummary": "source context",
            "quote": "quoted source",
        }
    ]

    for key in ("buddhist", "catholic", "hindu"):
        profile = ProductProfile(
            key=key,
            name=f"{key.title()} AI",
            db_path=tmp_path / f"{key}.sqlite3",
            db_shape="precedents",
            languages=("ko", "en"),
            default_language="ko",
            theme="gallery-canvas",
            safety_notice="source-grounded study aid",
        )

        messages = beta6_module.build_beta6_answer_plan_messages(
            profile,
            "근거별로 풍부하게 설명해줘",
            "ko",
            claim_cards,
        )
        prompt = messages[1]["content"]

        assert "source-layer" in prompt
        assert "retrieval gaps" in prompt
        assert "not filler" in prompt


def test_islam_answer_plan_does_not_fill_irrelevant_claims_from_selector_context(tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    db_path.touch()
    profile = _profile(db_path)
    claim_cards = [
        {
            "claimId": "C1",
            "label": "S1",
            "sourceId": "doc-riba",
            "citation": "Quran riba",
            "contextSummary": "Riba and unjust financial gain in Islamic economic law.",
            "claimSummary": "The selected source prohibits riba and unjust financial gain.",
            "quote": "الربا",
        },
        {
            "claimId": "C2",
            "label": "S2",
            "sourceId": "doc-wealth",
            "citation": "Wealth distribution",
            "contextSummary": "Wealth distribution and social justice in sharia discussion.",
            "claimSummary": "The selected source discusses توزيع الثروة and social justice.",
            "quote": "توزيع الثروة",
        },
        {
            "claimId": "C3",
            "label": "S3",
            "sourceId": "doc-property",
            "citation": "Private ownership",
            "contextSummary": "Private ownership and property limits in Islamic law.",
            "claimSummary": "The selected source discusses الملكية الخاصة in Islam.",
            "quote": "الملكية الخاصة",
        },
        {
            "claimId": "C4",
            "label": "S4",
            "sourceId": "doc-charity",
            "citation": "Social welfare",
            "contextSummary": "Charity, poverty relief, and social welfare principles.",
            "claimSummary": "The selected source discusses العدالة الاجتماعية.",
            "quote": "العدالة الاجتماعية",
        },
        {
            "claimId": "C5",
            "label": "S5",
            "sourceId": "doc-corruption",
            "citation": "Hudud corruption",
            "contextSummary": "Punishments for warfare and spreading corruption on earth.",
            "claimSummary": "The selected source discusses execution, crucifixion, and exile.",
            "quote": "القتل والصلب وقطع اليد والرجل",
        },
        {
            "claimId": "C6",
            "label": "S6",
            "sourceId": "doc-haram-entry",
            "citation": "Sacred Mosque entry",
            "contextSummary": "Non-Muslim access to the Sacred Mosque and ritual impurity.",
            "claimSummary": "The selected source discusses legal impurity and sanctuary entry.",
            "quote": "جاء الإسلام وهم على ذلك نجاسة الحكم لا نجاسة العين",
        },
    ]

    plan = beta6_module._coerce_answer_plan(
        profile,
        "사회주의는 하람임? 학파와 원칙별로 근거를 정리해줘",
        "ko",
        claim_cards,
        {
            "body_claim_ids": ["C1", "C5"],
            "coverage_required_claim_ids": ["C1", "C5"],
            "claim_groups": [{"title": "planner mixed relevant and irrelevant", "claim_ids": ["C1", "C5"]}],
        },
        status="completed",
        mode="llm_answer_planner",
        provider="fixture",
        model="gemma",
        selector_keywords=[
            "الربا والاشتراكية",
            "توزيع الثروة في الشريعة",
            "الملكية الخاصة في الإسلام",
            "العدالة الاجتماعية في الفقه",
        ],
    )

    assert plan["bodyClaimIds"] == ["C1", "C2", "C3", "C4"]
    assert plan["coverageRequiredClaimIds"] == ["C1", "C2", "C3", "C4"]
    assert "C5" not in plan["coverageRequiredClaimIds"]
    assert "C6" not in plan["coverageRequiredClaimIds"]


def test_answer_plan_prompt_receives_selector_learned_keywords(tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    db_path.touch()
    profile = _profile(db_path)

    messages = beta6_module.build_beta6_answer_plan_messages(
        profile,
        "사회주의는 하람임?",
        "ko",
        [{"claimId": "C1", "label": "S1", "claimSummary": "riba", "quote": "الربا"}],
        selector_keywords=["الربا والاشتراكية", "الملكية الخاصة في الإسلام"],
    )

    prompt = messages[-1]["content"]
    assert "Selector learned keywords" in prompt
    assert "الربا والاشتراكية" in prompt
    assert "الملكية الخاصة في الإسلام" in prompt


def test_islam_answer_plan_relevance_expands_arabic_riba_aliases(tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    db_path.touch()
    profile = _profile(db_path)
    claim_cards = [
        {
            "claimId": "C1",
            "label": "S1",
            "sourceId": "quran-riba-uthmani",
            "citation": "Quran 2:275",
            "contextSummary": "Quranic economic prohibition.",
            "claimSummary": "This source uses Uthmani script for the usury prohibition.",
            "quote": "ٱلَّذِينَ يَأۡكُلُونَ ٱلرِّبَوٰٓاْ",
        },
        {
            "claimId": "C2",
            "label": "S2",
            "sourceId": "english-riba",
            "citation": "Maarif riba",
            "contextSummary": "English tafsir on riba.",
            "claimSummary": "The source explains Riba and usury.",
            "quote": "riba is an anti-human claim",
        },
        {
            "claimId": "C3",
            "label": "S3",
            "sourceId": "unrelated-earth",
            "citation": "Unrelated earth verse",
            "contextSummary": "The text mentions الأرض but not economic law.",
            "claimSummary": "The source discusses months and sacred time.",
            "quote": "الأرض",
        },
    ]

    ranked = beta6_module._rank_claim_ids_for_answer_plan(
        profile,
        "사회주의는 하람임?",
        claim_cards,
        ["C1", "C2", "C3"],
        selector_keywords=["الربا والاشتراكية", "الاستخلاف في الأرض"],
    )

    assert ranked == ["C1", "C2"]


def test_tcm_answer_plan_relevance_keeps_short_cjk_herb_and_pregnancy_terms(tmp_path):
    profile = _tcm_profile(tmp_path / "tcm.sqlite3")
    claim_cards = [
        {
            "claimId": "C1",
            "label": "S1",
            "sourceId": "donguibogam-pregnancy-gancao",
            "citation": "Dongui Bogam pregnancy formula",
            "contextSummary": "Pregnancy urinary obstruction formula in a Korean classic.",
            "claimSummary": "The source mentions a pregnant woman and 甘草 in a formula.",
            "quote": "治孕婦轉脬, 小便不通. 四物湯料, 加人參ㆍ白朮ㆍ半夏ㆍ陳皮ㆍ甘草 各一錢.",
        },
        {
            "claimId": "C2",
            "label": "S2",
            "sourceId": "shanghan-guizhi",
            "citation": "Shanghan Lun guizhi",
            "contextSummary": "Classical 桂枝湯 formula context.",
            "claimSummary": "The source discusses 桂枝 and 桂枝湯.",
            "quote": "桂枝湯方 桂枝 芍藥 甘草 生薑 大棗.",
        },
        {
            "claimId": "C3",
            "label": "S3",
            "sourceId": "generic-bencao-history",
            "citation": "Generic materia medica history",
            "contextSummary": "A generic list of classic books.",
            "claimSummary": "The source only lists 本草 titles.",
            "quote": "《본초》 《영추경》 《소문》 《상한론》.",
        },
    ]

    ranked = beta6_module._rank_claim_ids_for_answer_plan(
        profile,
        "임신 중 감초나 계지를 복용해도 되는지 근거를 나눠서 설명해줘",
        claim_cards,
        ["C1", "C2", "C3"],
        selector_keywords=["甘草", "감초", "桂枝", "계지", "妊娠", "임신", "本草"],
    )

    assert ranked[:2] == ["C1", "C2"]
    assert "C3" not in ranked[:2]


def test_beta6_writer_prompt_requests_product_minimum_answer_depth(tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    db_path.touch()
    profile = _profile(db_path)

    messages = beta6_module.build_beta6_messages(
        profile,
        "사회주의는 하람임?",
        "ko",
        [
            {
                "file_id": "doc-1",
                "document_title": "Quran 2:275",
                "extracted_text": "riba social justice private property",
            }
        ],
        claim_cards=[
            {
                "claimId": "C1",
                "label": "S1",
                "sourceId": "doc-1",
                "citation": "Quran 2:275",
                "contextSummary": "riba context",
                "claimSummary": "riba summary",
                "quote": "riba",
            }
        ],
        answer_plan={"bodyClaimIds": ["C1"], "coverageRequiredClaimIds": ["C1"]},
    )

    prompt = messages[-1]["content"]
    assert "minimum answer depth" in prompt
    assert "2200" in prompt


def test_beta6_llm_writer_reports_missing_claims_without_forced_coverage_supplement(tmp_path, monkeypatch):
    db_path = tmp_path / "wide.sqlite3"
    _make_many_precedents_db(db_path, count=8)
    fake = PlanCoverageLLMClient()
    monkeypatch.setenv("RELIGION_BETA6_TOP_K_PRECEDENTS", "2")
    monkeypatch.setenv("RELIGION_BETA6_MAX_TOP_K_PRECEDENTS", "2")
    runtime = Beta6JobManager({"islam": _profile(db_path)}, runs_root=tmp_path / "runs", llm_client=fake)

    result = runtime.answer_sync(product="islam", query="공유어", language="ko", limit=2)

    answer = result["answer"]
    assert result["coverageReport"]["missingClaimIds"] == ["C2"]
    assert result["coverageReport"]["patched"] is False
    assert result["coverageReport"]["patchPolicy"] == "lawkey_beta6_skip_forced_coverage_patch"
    assert "### 누락 근거 보강" not in answer
    assert "두 번째 계획 claim" not in answer


def test_beta6_cited_claim_split_parses_comma_separated_citation_brackets(tmp_path):
    db_path = tmp_path / "simli.sqlite3"
    db_path.touch()
    profile = ProductProfile(
        key="simli",
        name="Simli",
        db_path=db_path,
        db_shape="documents",
        languages=("ko", "en"),
        default_language="ko",
        theme="simli",
        safety_notice="test",
    )
    claim_cards = [
        {"claimId": "C2", "label": "S4", "sourceId": "doc-2", "claimSummary": "insomnia category"},
        {"claimId": "C30", "label": "S5", "sourceId": "doc-30", "claimSummary": "anxiety category"},
        {"claimId": "C32", "label": "S7", "sourceId": "doc-32", "claimSummary": "bidirectional relation"},
    ]
    answer_plan = {"bodyClaimIds": ["C2", "C30"], "coverageRequiredClaimIds": ["C32"]}

    split = beta6_module.split_claim_cards_for_handoff(
        profile,
        "불면 범주는 이렇게 설명된다 [C2, S4]. 불안 범주는 이렇게 설명된다 [C30, S5]. 관계도 언급된다 [C32, S7].",
        claim_cards,
        answer_plan,
    )

    assert split["candidateClaimIds"] == ["C2", "C30", "C32"]
    assert split["citedClaimIds"] == ["C2", "C30", "C32"]
    assert [card["claimId"] for card in split["citedClaimCards"]] == ["C2", "C30", "C32"]


def test_claim_card_prompt_uses_selector_ledger_hints_without_replacing_source_text(tmp_path):
    product = _profile(tmp_path / "islam.sqlite3")
    selected_records = [
        {
            "file_id": "doc-ledger",
            "case_number": "Ledger Source",
            "document_title": "Ledger Source",
            "extracted_text": "full source text exact quote about ownership justice evidence.",
        }
    ]
    selected_evidence = [
        {
            "id": "doc-ledger",
            "label": "S1",
            "citation": "Ledger Source",
            "sourceKind": "fiqh",
            "selectorContextSummary": "선택 단계에서 파악한 문헌 맥락",
            "selectorClaimSummary": "선택 단계에서 파악한 쟁점 요약",
            "selectorQuoteCandidate": "ownership justice evidence",
            "selectorStance": "school_position",
            "selectorSourceRole": "fiqh",
        }
    ]

    messages = beta6_module.build_beta6_claim_card_messages(
        product,
        "사회주의는 하람임?",
        "ko",
        selected_records,
        selected_evidence,
    )
    prompt = messages[-1]["content"]

    assert "selector_context_summary: 선택 단계에서 파악한 문헌 맥락" in prompt
    assert "selector_claim_summary: 선택 단계에서 파악한 쟁점 요약" in prompt
    assert "selector_quote_candidate: ownership justice evidence" in prompt
    assert "selector_stance: school_position" in prompt
    assert "selector_source_role: fiqh" in prompt
    assert "text:\nfull source text exact quote" in prompt
    assert "For Korean answers, write context_summary and claim_summary in Korean." in prompt
    assert "claim_summary must explain what the exact quote says in its original source context" in prompt
    assert "claim_summary must not explain why the final answer selected the quote" in prompt
    assert "context_summary must explain the larger source or section containing the quoted part" in prompt
    assert "why the exact quote is being used for the user's answer" not in prompt


def test_beta6_runtime_uses_llm_claim_card_analyzer_with_exact_quote_gate(tmp_path, monkeypatch):
    db_path = tmp_path / "islam.sqlite3"
    _make_islam_school_db(db_path)
    fake = ClaimAnalyzerLLMClient()
    monkeypatch.setenv("RELIGION_CLAIM_ANALYZER_MODE", "source")
    monkeypatch.setenv("RELIGION_BETA6_TOP_K_PRECEDENTS", "3")
    monkeypatch.setenv("RELIGION_BETA6_MAX_TOP_K_PRECEDENTS", "3")
    runtime = Beta6JobManager({"islam": _profile(db_path)}, runs_root=tmp_path / "runs", llm_client=fake)

    result = runtime.answer_sync(product="islam", query="결혼할 때 보호자가 필요한가 학파별로 알려줘", language="ko", limit=3)

    analyzer_calls = [call for call in fake.calls if "claim-card analyzer" in call["system"]]
    writer_calls = [call for call in fake.calls if "source-grounded answer engine" in call["system"]]
    first_card = result["claimCards"][0]
    first_window = result["passageWindows"][0]
    highlighted = first_window["text"][first_window["highlightStart"]:first_window["highlightEnd"]]

    assert analyzer_calls
    assert result["beta6"]["claimAnalyzer"]["status"] == "completed"
    assert first_card["analysisSource"] == "llm_claim_analyzer"
    assert first_card["claimAxis"] == "Hanafi wali discussion"
    assert first_card["contextSummary"] == "이 카드는 하나피 문헌에서 혼인 보호자 논점을 다루는 부분이다."
    assert first_card["claimSummary"] == "하나피 쪽 논의는 보호자와 혼인계약 조건을 함께 검토한다."
    assert first_card["quote"] == "Hanafi school discussion mentions wali and marriage contract conditions."
    assert first_card["span"]["exact"] == first_card["quote"]
    assert highlighted == first_card["quote"]
    assert "Hanafi wali discussion" in writer_calls[-1]["prompt"]


def test_beta6_claim_card_analyzer_audits_selected_sources_in_batches(tmp_path, monkeypatch):
    db_path = tmp_path / "wide.sqlite3"
    _make_many_precedents_db(db_path, count=120)
    fake = OversizedPromptBatchedClaimAnalyzerLLMClient()
    monkeypatch.setenv("RELIGION_CLAIM_ANALYZER_MODE", "source")
    monkeypatch.setenv("RELIGION_CLAIM_ANALYZER_BATCH_SIZE", "25")
    runtime = Beta6JobManager({"islam": _profile(db_path)}, runs_root=tmp_path / "runs", llm_client=fake)

    result = runtime.answer_sync(product="islam", query="sharedterm", language="en", limit=8)

    analyzer = result["beta6"]["claimAnalyzer"]
    assert result["selector"]["selectorAuditedCandidateCount"] == 120
    assert len(fake.claim_calls) == 4
    assert max(len(call["sources"]) for call in fake.claim_calls) <= 25
    source_pairs = [source for call in fake.claim_calls for source in call["sources"]]
    assert ("S1", "doc-000") in source_pairs
    assert any(label == "S100" for label, _source_id in source_pairs)
    assert any(source_id == "doc-100" for _label, source_id in source_pairs)
    assert analyzer["status"] == "completed"
    assert analyzer["mode"] == "llm_claim_card_batched_analyzer"
    assert analyzer["claimAnalyzerBatchSize"] == 25
    assert analyzer["claimAnalyzerAuditedSourceCount"] == 100
    assert len(analyzer["claimAnalyzerBatches"]) == 4
    assert analyzer["llmCards"] == 100
    assert analyzer["deterministicFill"] == 0
    assert result["claimCards"][0]["analysisSource"] == "llm_claim_analyzer"
    assert result["claimCards"][-1]["sourceId"] in {source_id for _label, source_id in source_pairs}
    assert result["claimCards"][-1]["claimSummary"].endswith("claim summary")


def test_islam_claim_card_analyzer_uses_compact_full_parallel_batches(tmp_path, monkeypatch):
    db_path = tmp_path / "islam.sqlite3"
    db_path.touch()
    profile = _profile(db_path)
    fake = OversizedPromptBatchedClaimAnalyzerLLMClient()
    tail_marker = "TAILMARKER_SHOULD_NOT_ENTER_CLAIM_PROMPT"
    selected_records = [
        {
            "file_id": f"doc-{index:03d}",
            "document_title": f"Document {index:03d}",
            "case_number": f"Document {index:03d}",
            "doc_type": "fiqh_unit",
            "source_group": "structured_precedent",
            "extracted_text": "claim analyzer opening " + ("source context " * 68) + tail_marker + (" tail " * 90),
            "metadata": {"sourceKind": "fiqh", "school": "hanafi"},
        }
        for index in range(100)
    ]
    selected_evidence = [
        {
            "id": f"doc-{index:03d}",
            "label": f"S{index + 1}",
            "citation": f"Document {index:03d}",
            "sourceKind": "fiqh",
            "school": "hanafi",
        }
        for index in range(100)
    ]

    monkeypatch.delenv("RELIGION_CLAIM_ANALYZER_SOURCE_CHARS", raising=False)
    monkeypatch.delenv("RELIGION_ISLAM_CLAIM_ANALYZER_SOURCE_CHARS", raising=False)
    monkeypatch.delenv("RELIGION_CLAIM_ANALYZER_BATCH_WORKERS", raising=False)
    monkeypatch.delenv("RELIGION_ISLAM_CLAIM_ANALYZER_BATCH_WORKERS", raising=False)

    cards, analyzer = beta6_module.build_claim_cards_for_selected_sources(
        profile,
        "사회주의는 하람임? 학파와 원칙별로 근거를 정리해줘",
        selected_records,
        selected_evidence,
        language="ko",
        llm_client=fake,
        model="gemma",
        cache_root=tmp_path / "islam-claim-cache",
    )

    assert analyzer["claimAnalyzerBatchSize"] == 20
    assert analyzer["claimAnalyzerBatchWorkers"] == 5
    assert len(analyzer["claimAnalyzerBatches"]) == 5
    assert len(fake.claim_calls) == 5
    assert tail_marker not in "\n\n".join(call["prompt"] for call in fake.claim_calls)
    assert max(len(call["prompt"].encode("utf-8")) for call in fake.claim_calls) < 85_000
    assert len(cards) == 100


def test_beta6_claim_card_analyzer_emits_batched_progress_metadata(tmp_path, monkeypatch):
    db_path = tmp_path / "islam.sqlite3"
    db_path.touch()
    profile = _profile(db_path)
    fake = OversizedPromptBatchedClaimAnalyzerLLMClient()
    selected_records = [
        {
            "file_id": f"doc-{index:03d}",
            "document_title": f"Document {index:03d}",
            "case_number": f"Document {index:03d}",
            "doc_type": "fiqh_unit",
            "source_group": "structured_precedent",
            "extracted_text": f"sharedterm evidence principle context for source {index:03d}.",
            "metadata": {"sourceKind": "fiqh", "school": "hanafi"},
        }
        for index in range(30)
    ]
    selected_evidence = [
        {
            "id": f"doc-{index:03d}",
            "label": f"S{index + 1}",
            "citation": f"Document {index:03d}",
            "sourceKind": "fiqh",
            "school": "hanafi",
        }
        for index in range(30)
    ]
    events = []

    monkeypatch.setenv("RELIGION_CLAIM_ANALYZER_BATCH_SIZE", "10")
    monkeypatch.setenv("RELIGION_CLAIM_ANALYZER_BATCH_WORKERS", "2")

    def progress_callback(stage, message="", meta=None):
        events.append({"stage": stage, "message": message, "meta": meta or {}})

    cards, analyzer = beta6_module.build_claim_cards_for_selected_sources(
        profile,
        "공유어",
        selected_records,
        selected_evidence,
        language="ko",
        llm_client=fake,
        model="gemma",
        progress_callback=progress_callback,
    )

    batch_events = [
        event
        for event in events
        if event["stage"] == "claim_cards" and (event["meta"].get("batch") or {}).get("count") == 3
    ]
    assert analyzer["claimAnalyzerBatchSize"] == 10
    assert analyzer["claimAnalyzerBatchWorkers"] == 2
    assert len(batch_events) == 3
    assert batch_events[0]["meta"]["batch"]["index"] == 1
    assert batch_events[-1]["meta"]["batch"]["index"] == 3
    assert "1/3" in batch_events[0]["meta"]["detail"]
    assert "3/3" in batch_events[-1]["meta"]["detail"]
    assert len(cards) == 30


def test_beta6_claim_card_analyzer_can_build_claims_from_chunks(tmp_path, monkeypatch):
    db_path = tmp_path / "islam.sqlite3"
    db_path.touch()
    profile = _profile(db_path)
    fake = ChunkLevelClaimAnalyzerLLMClient()
    selected_records = [
        {
            "file_id": "doc-001",
            "document_title": "Document 001",
            "case_number": "Document 001",
            "doc_type": "fiqh_unit",
            "source_group": "structured_precedent",
            "extracted_text": "prefix first chunk exact evidence middle second chunk exact evidence suffix",
            "metadata": {"sourceKind": "fiqh", "school": "hanafi"},
        }
    ]
    selected_evidence = [
        {
            "id": "doc-001",
            "label": "S1",
            "citation": "Document 001",
            "sourceKind": "fiqh",
            "school": "hanafi",
        }
    ]
    chunks = [
        {
            "chunk_id": "chunk-1",
            "file_id": "doc-001",
            "text": "first chunk exact evidence",
            "source_segments": [{"file_id": "doc-001", "excerpt": "first chunk exact evidence"}],
        },
        {
            "chunk_id": "chunk-2",
            "file_id": "doc-001",
            "text": "second chunk exact evidence",
            "source_segments": [{"file_id": "doc-001", "excerpt": "second chunk exact evidence"}],
        },
    ]
    monkeypatch.setenv("RELIGION_CHUNK_CLAIM_ANALYZER_WORKERS", "1")

    cards, analyzer = beta6_module.build_claim_cards_for_selected_sources(
        profile,
        "chunk claims",
        selected_records,
        selected_evidence,
        language="en",
        llm_client=fake,
        model="gemma",
        chunks=chunks,
    )

    assert [call["chunk_id"] for call in fake.chunk_calls] == ["chunk-1", "chunk-2"]
    assert analyzer["mode"] == "llm_claim_card_chunk_analyzer"
    assert analyzer["claimAnalyzerChunkCount"] == 2
    assert analyzer["claimAnalyzerChunks"][0]["chunkId"] == "chunk-1"
    assert [card["claimAxis"] for card in cards[:2]] == ["axis chunk-1", "axis chunk-2"]
    assert [card["sourceChunkId"] for card in cards[:2]] == ["chunk-1", "chunk-2"]
    assert all(card["analysisSource"] == "llm_chunk_claim_analyzer" for card in cards[:2])


def test_islam_chunk_claim_analyzer_uses_compact_full_parallel_chunks(tmp_path, monkeypatch):
    db_path = tmp_path / "islam.sqlite3"
    db_path.touch()
    profile = _profile(db_path)
    fake = ChunkLevelClaimAnalyzerLLMClient()
    tail_marker = "TAILMARKER_SHOULD_NOT_ENTER_CHUNK_CLAIM_PROMPT"
    selected_records = [
        {
            "file_id": f"doc-{index}",
            "document_title": f"Document {index}",
            "case_number": f"Document {index}",
            "doc_type": "fiqh_unit",
            "source_group": "structured_precedent",
            "extracted_text": "first chunk exact evidence",
            "metadata": {"sourceKind": "fiqh"},
        }
        for index in range(1, 6)
    ]
    selected_evidence = [
        {"id": f"doc-{index}", "label": f"S{index}", "citation": f"Document {index}", "sourceKind": "fiqh"}
        for index in range(1, 6)
    ]
    chunks = [
        {
            "chunk_id": f"chunk-{index}",
            "file_id": f"doc-{index}",
            "text": "first chunk exact evidence " + ("chunk context " * 260) + tail_marker + (" tail " * 100),
            "source_segments": [{"file_id": f"doc-{index}", "excerpt": "first chunk exact evidence"}],
        }
        for index in range(1, 6)
    ]

    monkeypatch.delenv("RELIGION_CHUNK_CLAIM_ANALYZER_CHARS", raising=False)
    monkeypatch.delenv("RELIGION_ISLAM_CHUNK_CLAIM_ANALYZER_CHARS", raising=False)
    monkeypatch.delenv("RELIGION_CHUNK_CLAIM_ANALYZER_WORKERS", raising=False)
    monkeypatch.delenv("RELIGION_ISLAM_CHUNK_CLAIM_ANALYZER_WORKERS", raising=False)

    cards, analyzer = beta6_module.build_claim_cards_for_selected_sources(
        profile,
        "사회주의는 하람임? 학파와 원칙별로 근거를 정리해줘",
        selected_records,
        selected_evidence,
        language="ko",
        llm_client=fake,
        model="gemma",
        chunks=chunks,
        cache_root=tmp_path / "islam-chunk-cache",
    )

    assert analyzer["claimAnalyzerChunkWorkers"] == 5
    assert analyzer["claimAnalyzerChunkCount"] == 5
    assert len(fake.chunk_calls) == 5
    assert tail_marker not in "\n\n".join(call["prompt"] for call in fake.chunk_calls)
    assert max(len(call["prompt"].encode("utf-8")) for call in fake.chunk_calls) < 45_000
    assert cards


def test_beta6_fast_mode_caps_chunk_claim_analyzer_to_ten(tmp_path, monkeypatch):
    db_path = tmp_path / "islam.sqlite3"
    db_path.touch()
    profile = _profile(db_path)
    fake = ChunkLevelClaimAnalyzerLLMClient()
    selected_records = [
        {
            "file_id": f"doc-{index}",
            "document_title": f"Document {index}",
            "case_number": f"Document {index}",
            "doc_type": "fiqh_unit",
            "source_group": "structured_precedent",
            "extracted_text": "first chunk exact evidence second chunk exact evidence",
            "metadata": {"sourceKind": "fiqh"},
        }
        for index in range(1, 16)
    ]
    selected_evidence = [
        {"id": f"doc-{index}", "label": f"S{index}", "citation": f"Document {index}", "sourceKind": "fiqh"}
        for index in range(1, 16)
    ]
    chunks = [
        {
            "chunk_id": f"chunk-{index}",
            "file_id": f"doc-{index}",
            "text": "first chunk exact evidence second chunk exact evidence",
            "source_segments": [{"file_id": f"doc-{index}", "excerpt": "first chunk exact evidence"}],
        }
        for index in range(1, 16)
    ]
    monkeypatch.setenv("RELIGION_CHUNK_CLAIM_ANALYZER_WORKERS", "1")

    _cards, _gate, meta = beta6_module._analyze_claim_cards_from_chunks(
        profile,
        "fast chunk cap",
        selected_records,
        selected_evidence,
        chunks,
        language="en",
        llm_client=fake,
        model="gemma",
        fast_mode=True,
    )

    assert meta["chunkCount"] == 10
    assert [call["chunk_id"] for call in fake.chunk_calls] == [f"chunk-{index}" for index in range(1, 11)]


def test_beta6_merges_same_axis_chunk_claim_cards_into_support_ledger(tmp_path, monkeypatch):
    db_path = tmp_path / "islam.sqlite3"
    db_path.touch()
    profile = _profile(db_path)
    fake = DuplicateAxisChunkClaimAnalyzerLLMClient()
    selected_records = [
        {
            "file_id": "doc-a",
            "document_title": "Document A",
            "case_number": "Document A",
            "doc_type": "scripture_unit",
            "source_group": "structured_precedent",
            "extracted_text": "prefix first source prayer obligation evidence suffix",
            "metadata": {"sourceKind": "scripture"},
        },
        {
            "file_id": "doc-b",
            "document_title": "Document B",
            "case_number": "Document B",
            "doc_type": "hadith_unit",
            "source_group": "structured_precedent",
            "extracted_text": "prefix second source prayer obligation evidence suffix",
            "metadata": {"sourceKind": "hadith"},
        },
    ]
    selected_evidence = [
        {"id": "doc-a", "label": "S1", "citation": "Document A", "sourceKind": "scripture"},
        {"id": "doc-b", "label": "S2", "citation": "Document B", "sourceKind": "hadith"},
    ]
    chunks = [
        {
            "chunk_id": "chunk-a",
            "file_id": "doc-a",
            "text": "first source prayer obligation evidence",
            "source_segments": [{"file_id": "doc-a", "excerpt": "first source prayer obligation evidence"}],
        },
        {
            "chunk_id": "chunk-b",
            "file_id": "doc-b",
            "text": "second source prayer obligation evidence",
            "source_segments": [{"file_id": "doc-b", "excerpt": "second source prayer obligation evidence"}],
        },
    ]

    monkeypatch.setenv("RELIGION_CHUNK_CLAIM_ANALYZER_WORKERS", "1")

    cards, analyzer = beta6_module.build_claim_cards_for_selected_sources(
        profile,
        "기도 의무 근거",
        selected_records,
        selected_evidence,
        language="ko",
        llm_client=fake,
        model="gemma",
        chunks=chunks,
    )
    writer_ledger = beta6_module.render_claim_cards_for_writer(cards)

    assert analyzer["claimAnalyzerMergedClaimCount"] == 1
    assert analyzer["claimAnalyzerMergedSupportCount"] == 2
    assert len(cards) == 1
    assert cards[0]["claimId"] == "C1"
    assert cards[0]["claimAxis"] == "prayer obligation"
    assert cards[0]["supportCount"] == 2
    assert cards[0]["supportingSourceIds"] == ["doc-a", "doc-b"]
    assert [item["label"] for item in cards[0]["supportingClaims"]] == ["S1", "S2"]
    assert "support_count: 2" in writer_ledger
    assert "supporting_quote: [S2] second source prayer obligation evidence" in writer_ledger


def test_beta6_claim_card_analyzer_retries_unmatched_quote_before_accepting(tmp_path, monkeypatch):
    db_path = tmp_path / "islam.sqlite3"
    db_path.touch()
    profile = _profile(db_path)
    fake = RetryingClaimQuoteLLMClient()
    selected_records = [
        {
            "file_id": "doc-retry",
            "document_title": "Retry Source",
            "case_number": "Retry Source",
            "doc_type": "fiqh_unit",
            "source_group": "structured_precedent",
            "extracted_text": (
                "unrelated opening sentence for fallback.\n\n"
                "actual source exact sentence about prayer timing and obligation."
            ),
            "metadata": {"sourceKind": "fiqh", "school": "hanafi"},
        }
    ]
    selected_evidence = [
        {
            "id": "doc-retry",
            "label": "S1",
            "citation": "Retry Source",
            "sourceKind": "fiqh",
            "school": "hanafi",
        }
    ]

    monkeypatch.setenv("RELIGION_CLAIM_ANALYZER_MODE", "source")

    cards, analyzer = beta6_module.build_claim_cards_for_selected_sources(
        profile,
        "하루 기도 시간 근거",
        selected_records,
        selected_evidence,
        language="ko",
        llm_client=fake,
        model="gemma",
    )

    assert len(fake.claim_calls) == 1
    assert len(fake.retry_calls) == 1
    assert analyzer["quoteGate"]["retried"] == 1
    assert analyzer["quoteGate"]["recovered"] == 1
    assert analyzer["quoteGate"]["rejected"] == 0
    assert cards[0]["quote"] == "actual source exact sentence about prayer timing and obligation."
    assert cards[0]["quoteMatch"] == "retry"
    assert cards[0]["quoteRecovered"] is True
    assert cards[0]["span"]["exact"] == cards[0]["quote"]
    assert "unrelated opening" not in cards[0]["quote"]


def test_beta6_selector_reuses_cached_batches_across_jobs(tmp_path, monkeypatch):
    db_path = tmp_path / "wide.sqlite3"
    _make_many_precedents_db(db_path, count=120)
    fake = OversizedPromptBatchedSelectorLLMClient()
    monkeypatch.setenv("RELIGION_BETA6_BATCH_CACHE_ROOT", str(tmp_path / "batch-cache"))
    monkeypatch.setenv("RELIGION_SELECTOR_BATCH_SIZE", "25")
    monkeypatch.setenv("RELIGION_SELECTOR_BATCH_WORKERS", "1")
    runtime = Beta6JobManager({"islam": _profile(db_path)}, runs_root=tmp_path / "runs", llm_client=fake)

    first = runtime.answer_sync(product="islam", query="sharedterm cache", language="en", limit=8)
    first_calls = len(fake.selector_calls)
    second = runtime.answer_sync(product="islam", query="sharedterm cache", language="en", limit=8)

    assert first_calls == 5
    assert len(fake.selector_calls) == first_calls
    assert first["selector"]["selectorBatchCacheMisses"] == 5
    assert first["selector"]["selectorBatchCacheHits"] == 0
    assert second["selector"]["selectorBatchCacheHits"] == 5
    assert second["selector"]["selectorBatchCacheMisses"] == 0
    assert all(batch["cacheHit"] for batch in second["selector"]["selectorBatches"])


def test_beta6_claim_card_analyzer_reuses_cached_batches(tmp_path, monkeypatch):
    db_path = tmp_path / "islam.sqlite3"
    db_path.touch()
    profile = _profile(db_path)
    first_fake = OversizedPromptBatchedClaimAnalyzerLLMClient()
    second_fake = OversizedPromptBatchedClaimAnalyzerLLMClient()
    selected_records = [
        {
            "file_id": f"doc-{index:03d}",
            "document_title": f"Document {index:03d}",
            "case_number": f"Document {index:03d}",
            "doc_type": "fiqh_unit",
            "source_group": "structured_precedent",
            "extracted_text": f"sharedterm evidence principle context for source {index:03d}.",
            "metadata": {"sourceKind": "fiqh", "school": "hanafi"},
        }
        for index in range(30)
    ]
    selected_evidence = [
        {
            "id": f"doc-{index:03d}",
            "label": f"S{index + 1}",
            "citation": f"Document {index:03d}",
            "sourceKind": "fiqh",
            "school": "hanafi",
        }
        for index in range(30)
    ]

    monkeypatch.setenv("RELIGION_BETA6_BATCH_CACHE_ROOT", str(tmp_path / "batch-cache"))
    monkeypatch.setenv("RELIGION_CLAIM_ANALYZER_BATCH_SIZE", "10")
    monkeypatch.setenv("RELIGION_CLAIM_ANALYZER_BATCH_WORKERS", "1")

    _, first_analyzer = beta6_module.build_claim_cards_for_selected_sources(
        profile,
        "공유어 캐시",
        selected_records,
        selected_evidence,
        language="ko",
        llm_client=first_fake,
        model="gemma",
    )
    cards, second_analyzer = beta6_module.build_claim_cards_for_selected_sources(
        profile,
        "공유어 캐시",
        selected_records,
        selected_evidence,
        language="ko",
        llm_client=second_fake,
        model="gemma",
    )

    assert len(first_fake.claim_calls) == 3
    assert len(second_fake.claim_calls) == 0
    assert first_analyzer["claimAnalyzerBatchCacheMisses"] == 3
    assert first_analyzer["claimAnalyzerBatchCacheHits"] == 0
    assert second_analyzer["claimAnalyzerBatchCacheHits"] == 3
    assert second_analyzer["claimAnalyzerBatchCacheMisses"] == 0
    assert all(batch["cacheHit"] for batch in second_analyzer["claimAnalyzerBatches"])
    assert len(cards) == 30


def test_beta6_batch_cache_ttl_expires_stale_selector_and_claim_batches(tmp_path, monkeypatch):
    db_path = tmp_path / "wide.sqlite3"
    _make_many_precedents_db(db_path, count=120)
    cache_root = tmp_path / "batch-cache"
    runtime_cache_root = tmp_path / "runs" / "_beta6_batch_cache"
    selector_fake = OversizedPromptBatchedSelectorLLMClient()
    monkeypatch.setenv("RELIGION_BETA6_BATCH_CACHE_ROOT", str(cache_root))
    monkeypatch.setenv("RELIGION_BETA6_BATCH_CACHE_TTL_SECONDS", "1")
    monkeypatch.setenv("RELIGION_SELECTOR_BATCH_SIZE", "25")
    monkeypatch.setenv("RELIGION_SELECTOR_BATCH_WORKERS", "1")
    runtime = Beta6JobManager({"islam": _profile(db_path)}, runs_root=tmp_path / "runs", llm_client=selector_fake)

    runtime.answer_sync(product="islam", query="sharedterm stale cache", language="en", limit=8)
    selector_calls_after_first = len(selector_fake.selector_calls)
    selector_files = list((runtime_cache_root / "selector").rglob("*.json"))
    assert selector_files
    for path in selector_files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["createdAt"] = 0
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    second = runtime.answer_sync(product="islam", query="sharedterm stale cache", language="en", limit=8)

    assert selector_calls_after_first == 5
    assert len(selector_fake.selector_calls) == selector_calls_after_first + 5
    assert second["selector"]["selectorBatchCacheHits"] == 0
    assert second["selector"]["selectorBatchCacheMisses"] == 5

    profile = _profile(db_path)
    claim_first = OversizedPromptBatchedClaimAnalyzerLLMClient()
    claim_second = OversizedPromptBatchedClaimAnalyzerLLMClient()
    selected_records = second["beta6SelectedRecords"][:30]
    selected_evidence = second["selectedEvidence"][:30]
    monkeypatch.setenv("RELIGION_CLAIM_ANALYZER_BATCH_SIZE", "10")
    monkeypatch.setenv("RELIGION_CLAIM_ANALYZER_BATCH_WORKERS", "1")

    beta6_module.build_claim_cards_for_selected_sources(
        profile,
        "claim stale cache",
        selected_records,
        selected_evidence,
        language="en",
        llm_client=claim_first,
        model="gemma",
    )
    claim_files = list((cache_root / "claim_cards").rglob("*.json"))
    assert claim_files
    for path in claim_files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["createdAt"] = 0
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    _, second_claim_meta = beta6_module.build_claim_cards_for_selected_sources(
        profile,
        "claim stale cache",
        selected_records,
        selected_evidence,
        language="en",
        llm_client=claim_second,
        model="gemma",
    )

    assert len(claim_first.claim_calls) == 3
    assert len(claim_second.claim_calls) == 3
    assert second_claim_meta["claimAnalyzerBatchCacheHits"] == 0
    assert second_claim_meta["claimAnalyzerBatchCacheMisses"] == 3


def test_beta6_batch_cache_lock_from_dead_owner_is_immediately_stale(tmp_path, monkeypatch):
    lock_path = tmp_path / "batch.lock"
    lock_path.write_text(json.dumps({"pid": 999999999, "thread": 1, "createdAt": time.time()}), encoding="utf-8")
    monkeypatch.setenv("RELIGION_BETA6_BATCH_CACHE_LOCK_STALE_SECONDS", "900")

    assert beta6_module._batch_cache_lock_is_stale(lock_path) is True


def test_beta6_batch_cache_lock_from_live_owner_is_not_stale(tmp_path, monkeypatch):
    lock_path = tmp_path / "batch.lock"
    lock_path.write_text(json.dumps({"pid": os.getpid(), "thread": 1, "createdAt": time.time()}), encoding="utf-8")
    monkeypatch.setenv("RELIGION_BETA6_BATCH_CACHE_LOCK_STALE_SECONDS", "900")

    assert beta6_module._batch_cache_lock_is_stale(lock_path) is False


def test_beta6_batch_cache_prunes_oldest_entries_when_size_limit_is_exceeded(tmp_path, monkeypatch):
    cache_root = tmp_path / "batch-cache"
    payloads = [
        {"cacheVersion": "test-lru", "batch": 1, "fingerprint": "alpha"},
        {"cacheVersion": "test-lru", "batch": 2, "fingerprint": "beta"},
        {"cacheVersion": "test-lru", "batch": 3, "fingerprint": "gamma"},
    ]
    value = {"blob": "x" * 512}

    monkeypatch.setenv("RELIGION_BETA6_BATCH_CACHE_ROOT", str(cache_root))
    monkeypatch.setenv("RELIGION_BETA6_BATCH_CACHE_TTL_SECONDS", "0")
    monkeypatch.setenv("RELIGION_BETA6_BATCH_CACHE_MAX_BYTES", "0")

    beta6_module._write_batch_cache("selector", payloads[0], value)
    time.sleep(0.02)
    beta6_module._write_batch_cache("selector", payloads[1], value)
    path1, _ = beta6_module._batch_cache_path("selector", payloads[0])
    path2, _ = beta6_module._batch_cache_path("selector", payloads[1])
    assert path1.exists()
    assert path2.exists()

    time.sleep(0.02)
    assert beta6_module._read_batch_cache("selector", payloads[0]) == value
    max_bytes = path1.stat().st_size + path2.stat().st_size + 64
    monkeypatch.setenv("RELIGION_BETA6_BATCH_CACHE_MAX_BYTES", str(max_bytes))
    time.sleep(0.02)
    beta6_module._write_batch_cache("selector", payloads[2], value)

    path3, _ = beta6_module._batch_cache_path("selector", payloads[2])
    json_files = list(cache_root.rglob("*.json"))
    total_bytes = sum(path.stat().st_size for path in json_files)

    assert beta6_module._read_batch_cache("selector", payloads[0]) == value
    assert beta6_module._read_batch_cache("selector", payloads[1]) is None
    assert beta6_module._read_batch_cache("selector", payloads[2]) == value
    assert path3.exists()
    assert total_bytes <= max_bytes


def test_beta6_selector_cache_lease_prevents_concurrent_batch_stampede(tmp_path, monkeypatch):
    profile = _profile(tmp_path / "islam.sqlite3")
    candidates = [
        SearchResult(
            canonical_id=f"doc-{index:03d}",
            title=f"Document {index:03d}",
            citation=f"Document {index:03d}",
            authority_body="Test",
            source_date="",
            case_name=f"Document {index:03d}",
            case_type="fiqh_unit",
            full_text=f"sharedterm evidence principle context for source {index:03d}.",
            source_kind="fiqh",
            school="hanafi",
        )
        for index in range(50)
    ]
    fake = SlowConcurrentSelectorLLMClient()
    barrier = threading.Barrier(3)
    results = []
    errors = []

    monkeypatch.setenv("RELIGION_BETA6_BATCH_CACHE_ROOT", str(tmp_path / "batch-cache"))
    monkeypatch.setenv("RELIGION_SELECTOR_BATCH_SIZE", "25")
    monkeypatch.setenv("RELIGION_SELECTOR_BATCH_WORKERS", "1")
    monkeypatch.setenv("RELIGION_BETA6_BATCH_CACHE_LOCK_TIMEOUT_SECONDS", "5")

    def run_selector():
        try:
            barrier.wait(timeout=3)
            result = beta6_module.select_rows_with_beta6_selector(
                profile,
                "sharedterm concurrent cache",
                "en",
                candidates,
                limit=8,
                llm_client=fake,
                model="gemma",
            )
            results.append(result)
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=run_selector) for _ in range(2)]
    for thread in threads:
        thread.start()
    barrier.wait(timeout=3)
    for thread in threads:
        thread.join(timeout=5)

    assert not errors
    assert len(results) == 2
    selector_meta = [result[3] for result in results]
    assert len(fake.selector_calls) == 2
    assert sum(meta["selectorBatchCacheMisses"] for meta in selector_meta) == 2
    assert sum(meta["selectorBatchCacheHits"] for meta in selector_meta) == 2
    assert all(len(result[0]) == 4 for result in results)


def test_beta6_batch_cache_lease_coordinates_across_processes(tmp_path):
    if not hasattr(os, "fork"):
        pytest.skip("fork-based cross-process cache lease smoke requires POSIX")
    ctx = multiprocessing.get_context("fork")
    queue = ctx.Queue()
    barrier = ctx.Barrier(2)
    producer_log = tmp_path / "producer.log"
    cache_root = tmp_path / "batch-cache"
    processes = [
        ctx.Process(target=_fill_batch_cache_from_process, args=(str(cache_root), str(producer_log), queue, barrier))
        for _ in range(2)
    ]

    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=5)
    for process in processes:
        if process.is_alive():
            process.terminate()
            process.join(timeout=2)

    assert all(process.exitcode == 0 for process in processes)
    results = [queue.get(timeout=1) for _ in processes]
    assert all(result["ok"] for result in results), results
    assert sorted(result["cacheHit"] for result in results) == [False, True]
    assert len(producer_log.read_text(encoding="utf-8").splitlines()) == 1
    filled_values = {result["value"]["filledBy"] for result in results}
    assert len(filled_values) == 1


def test_beta6_runtime_builds_answer_plan_and_reports_missing_claim_coverage(tmp_path, monkeypatch):
    db_path = tmp_path / "wide.sqlite3"
    _make_many_precedents_db(db_path, count=8)
    fake = PlanCoverageLLMClient()
    monkeypatch.setenv("RELIGION_BETA6_TOP_K_PRECEDENTS", "2")
    monkeypatch.setenv("RELIGION_BETA6_MAX_TOP_K_PRECEDENTS", "2")
    runtime = Beta6JobManager({"islam": _profile(db_path)}, runs_root=tmp_path / "runs", llm_client=fake)

    result = runtime.answer_sync(product="islam", query="공유어", language="ko", limit=2)

    planner_calls = [call for call in fake.calls if "answer planner" in call["system"]]
    writer_calls = [call for call in fake.calls if "source-grounded answer engine" in call["system"]]
    answer = result["answer"]

    assert planner_calls
    assert result["answerPlan"]["status"] == "completed"
    assert result["answerPlan"]["bodyClaimIds"] == ["C1", "C2"]
    assert result["coverageReport"]["patched"] is False
    assert result["coverageReport"]["missingClaimIds"] == ["C2"]
    assert result["coverageReport"]["patchPolicy"] == "lawkey_beta6_skip_forced_coverage_patch"
    assert "### 누락 근거 보강" not in answer
    assert "두 번째 계획 claim" not in answer
    assert "[answer plan]" in writer_calls[-1]["prompt"]
    assert "C2" in writer_calls[-1]["prompt"]
    assert result["artifacts"]["answerPlan"].endswith("answer_plan.json")
    assert result["artifacts"]["coverageReport"].endswith("coverage_report.json")


def test_beta6_answer_plan_cache_reuses_same_claim_ledger_prompt(tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    db_path.touch()
    product = _profile(db_path)
    fake = CountingPlannerWriterCacheLLMClient()
    claim_cards = [
        {
            "claimId": "C1",
            "label": "S1/C1",
            "sourceId": "doc-1",
            "citation": "Source 1",
            "claimAxis": "axis",
            "contextSummary": "context",
            "claimSummary": "summary",
            "quote": "quote",
        }
    ]
    cache_root = tmp_path / "cache"

    plan1, meta1 = beta6_module.build_answer_plan_for_claim_cards(
        product,
        "same plan query",
        "en",
        claim_cards,
        llm_client=fake,
        model="gemma",
        cache_root=cache_root,
    )
    plan2, meta2 = beta6_module.build_answer_plan_for_claim_cards(
        product,
        "same plan query",
        "en",
        claim_cards,
        llm_client=fake,
        model="gemma",
        cache_root=cache_root,
    )

    assert fake.planner_calls == 1
    assert plan1["bodyClaimIds"] == plan2["bodyClaimIds"] == ["C1"]
    assert meta1["cacheHit"] is False
    assert meta2["cacheHit"] is True


def test_beta6_writer_cache_reuses_same_source_grounded_prompt(tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    db_path.touch()
    product = _profile(db_path)
    fake = CountingPlannerWriterCacheLLMClient()
    messages = [
        {"role": "system", "content": f"Gemma 4 source-grounded answer engine for {product.name}."},
        {"role": "user", "content": "same writer prompt"},
    ]
    cache_root = tmp_path / "cache"

    answer1, hit1 = beta6_module.complete_writer_with_cache(
        product,
        "same writer query",
        "en",
        llm_client=fake,
        model="gemma",
        messages=messages,
        cache_root=cache_root,
    )
    answer2, hit2 = beta6_module.complete_writer_with_cache(
        product,
        "same writer query",
        "en",
        llm_client=fake,
        model="gemma",
        messages=messages,
        cache_root=cache_root,
    )

    assert fake.writer_calls == 1
    assert answer1 == answer2 == "cached writer answer [C1]"
    assert hit1 is False
    assert hit2 is True


def test_beta6_runtime_reuses_answer_plan_and_writer_cache_across_same_jobs(tmp_path, monkeypatch):
    db_path = tmp_path / "wide.sqlite3"
    _make_many_precedents_db(db_path, count=8)
    fake = PlanCoverageLLMClient()
    monkeypatch.setenv("RELIGION_BETA6_TOP_K_PRECEDENTS", "2")
    monkeypatch.setenv("RELIGION_BETA6_MAX_TOP_K_PRECEDENTS", "2")
    runtime = Beta6JobManager({"islam": _profile(db_path)}, runs_root=tmp_path / "runs", llm_client=fake)

    first = runtime.answer_sync(product="islam", query="공유어 cache", language="ko", limit=2)
    calls_after_first = list(fake.calls)
    second = runtime.answer_sync(product="islam", query="공유어 cache", language="ko", limit=2)

    planner_calls_after_first = sum(1 for call in calls_after_first if "answer planner" in call["system"])
    writer_calls_after_first = sum(1 for call in calls_after_first if "source-grounded answer engine" in call["system"])
    planner_calls_total = sum(1 for call in fake.calls if "answer planner" in call["system"])
    writer_calls_total = sum(1 for call in fake.calls if "source-grounded answer engine" in call["system"])

    assert planner_calls_after_first == 1
    assert writer_calls_after_first == 1
    assert planner_calls_total == planner_calls_after_first
    assert writer_calls_total == writer_calls_after_first
    assert first["beta6"]["answerPlanner"]["cacheHit"] is False
    assert second["beta6"]["answerPlanner"]["cacheHit"] is True
    assert first["writer"]["cacheHit"] is False
    assert second["writer"]["cacheHit"] is True
    assert second["beta6"]["writerCacheHit"] is True


def test_beta6_answer_coverage_patch_adds_source_grounded_detail_when_answer_is_too_short(tmp_path, monkeypatch):
    db_path = tmp_path / "wide.sqlite3"
    db_path.touch()
    product = _profile(db_path)
    monkeypatch.setenv("RELIGION_ISLAM_MIN_ANSWER_CHARS", "700")
    claim_cards = [
        {
            "claimId": "C1",
            "label": "S1",
            "citation": "Quran wealth distribution",
            "contextSummary": "부의 집중을 막는 분배 문맥입니다.",
            "claimSummary": "재산과 분배 원칙을 설명하는 claim입니다.",
            "quote": "wealth should not circulate only among the rich",
        },
        {
            "claimId": "C2",
            "label": "S2",
            "citation": "Hadith innovation boundary",
            "contextSummary": "새로운 체제를 평가할 때 종교 원칙과의 조화를 보는 문맥입니다.",
            "claimSummary": "종교 원칙에 어긋나는 새 관행은 거부된다는 claim입니다.",
            "quote": "whoever introduces what is not in harmony with this religion",
        },
    ]
    answer_plan = {"bodyClaimIds": ["C1", "C2"], "coverageRequiredClaimIds": ["C1", "C2"]}

    answer, report = beta6_module.apply_answer_coverage_patch(
        product,
        "짧은 답변입니다. [C1] [C2]",
        claim_cards,
        answer_plan,
        language="ko",
    )

    assert report["patched"] is True
    assert report["depthPatched"] is True
    assert report["shortAnswerChars"] < report["minAnswerChars"]
    assert "### 선택 근거 상세" in answer
    assert "재산과 분배 원칙" in answer
    assert "종교 원칙에 어긋나는 새 관행" in answer


def test_beta6_answer_plan_includes_claim_ids_referenced_in_groups_and_outline(tmp_path):
    db_path = tmp_path / "wide.sqlite3"
    _make_many_precedents_db(db_path, count=8)
    product = _profile(db_path)
    claim_cards = [
        {
            "claimId": f"C{index}",
            "label": f"S{index}",
            "claimSummary": f"claim {index}",
            "contextSummary": f"context {index}",
        }
        for index in range(1, 9)
    ]
    parsed = {
        "body_claim_ids": ["C1", "C2"],
        "coverage_required_claim_ids": ["C1"],
        "claim_groups": [
            {
                "title": "school comparison",
                "claim_ids": ["C5", "C6"],
                "summary": "The school comparison turns on C5 and C6.",
            }
        ],
        "answer_outline": [
            "Compare the retrieved school/material limits in C7 and C8 before a conclusion.",
        ],
        "citation_policy": "Cite every claim id used in groups or outline.",
    }

    plan = beta6_module._coerce_answer_plan(
        product,
        "hard comparative question",
        "ko",
        claim_cards,
        parsed,
        status="completed",
        mode="llm_answer_planner",
        provider="test",
        model="test-model",
    )

    assert plan["bodyClaimIds"][:6] == ["C1", "C2", "C5", "C6", "C7", "C8"]
    assert plan["coverageRequiredClaimIds"][:6] == ["C1", "C2", "C5", "C6", "C7", "C8"]
    assert set(plan["bodyClaimIds"]) == {f"C{index}" for index in range(1, 9)}
    assert set(plan["coverageRequiredClaimIds"]) == {f"C{index}" for index in range(1, 9)}


def test_beta6_runtime_strips_visible_thought_blocks_from_writer_answer(tmp_path, monkeypatch):
    db_path = tmp_path / "wide.sqlite3"
    _make_many_precedents_db(db_path, count=8)
    fake = ThoughtLeakLLMClient()
    monkeypatch.setenv("RELIGION_BETA6_TOP_K_PRECEDENTS", "1")
    monkeypatch.setenv("RELIGION_BETA6_MAX_TOP_K_PRECEDENTS", "1")
    runtime = Beta6JobManager({"islam": _profile(db_path)}, runs_root=tmp_path / "runs", llm_client=fake)

    result = runtime.answer_sync(product="islam", query="공유어", language="ko", limit=1)

    assert "[thought]" not in result["answer"].lower()
    assert "내부 계획" not in result["answer"]
    assert result["answer"].startswith("### 답변")
    assert "본문에 남아야 하는 근거" in result["answer"]


def test_beta6_runtime_localizes_visible_writer_boilerplate_for_korean_answer(tmp_path, monkeypatch):
    db_path = tmp_path / "wide.sqlite3"
    _make_many_precedents_db(db_path, count=8)
    fake = EnglishBoilerplateLLMClient()
    monkeypatch.setenv("RELIGION_BETA6_TOP_K_PRECEDENTS", "1")
    monkeypatch.setenv("RELIGION_BETA6_MAX_TOP_K_PRECEDENTS", "1")
    runtime = Beta6JobManager({"islam": _profile(db_path)}, runs_root=tmp_path / "runs", llm_client=fake)

    result = runtime.answer_sync(product="islam", query="공유어", language="ko", limit=1)

    answer = result["answer"]
    assert "GEMMA4 CITED ANSWER" not in answer
    assert "PRIMARY TEXT SOURCE" not in answer
    assert "CROSS-CHECK SOURCE" not in answer
    assert "## 인용 답변" in answer
    assert "### 주요 원문 근거" in answer
    assert "### 교차 확인 근거" in answer


def test_islam_writer_answer_appends_no_fatwa_boundary_when_model_omits_it(tmp_path, monkeypatch):
    db_path = tmp_path / "wide.sqlite3"
    _make_many_precedents_db(db_path, count=8)
    fake = ThoughtLeakLLMClient()
    monkeypatch.setenv("RELIGION_BETA6_TOP_K_PRECEDENTS", "1")
    monkeypatch.setenv("RELIGION_BETA6_MAX_TOP_K_PRECEDENTS", "1")
    runtime = Beta6JobManager({"islam": _profile(db_path)}, runs_root=tmp_path / "runs", llm_client=fake)

    result = runtime.answer_sync(product="islam", query="공유어는 하람임?", language="ko", limit=1)

    assert "본문에 남아야 하는 근거" in result["answer"]
    assert "구속력 있는 파트와" in result["answer"]
    assert "최종 판결입니다" not in result["answer"]


def test_beta6_selector_selection_is_filled_to_lawkey_sized_top_k(tmp_path):
    db_path = tmp_path / "wide.sqlite3"
    _make_many_precedents_db(db_path, count=120)
    runtime = Beta6JobManager({"islam": _profile(db_path)}, runs_root=tmp_path / "runs", llm_client=SparseSelectorLLMClient())

    result = runtime.answer_sync(product="islam", query="sharedterm", language="en", limit=8)

    assert result["beta6"]["candidateCount"] == 120
    assert result["selector"]["topK"] == 100
    assert result["beta6"]["selectedCount"] == 100
    assert len(result["sources"]) == 100
    assert result["selector"]["rawSelectedIds"][:3] == ["doc-000", "doc-001", "doc-002"]


def test_beta6_selector_batches_large_candidate_sets_before_timeout_fallback(tmp_path, monkeypatch):
    db_path = tmp_path / "wide.sqlite3"
    _make_many_precedents_db(db_path, count=120)
    fake = OversizedPromptBatchedSelectorLLMClient()
    monkeypatch.setenv("RELIGION_SELECTOR_CANDIDATE_LIMIT", "100")
    monkeypatch.setenv("RELIGION_SELECTOR_BATCH_SIZE", "25")
    runtime = Beta6JobManager({"islam": _profile(db_path)}, runs_root=tmp_path / "runs", llm_client=fake)

    result = runtime.answer_sync(product="islam", query="sharedterm", language="en", limit=8)

    assert result["selector"]["status"] == "completed"
    assert result["selector"]["mode"] == "llm_keyword_search_and_batched_selector"
    assert result["selector"]["selectionSource"] == "gemma4_llm_batched_selector"
    assert len(fake.selector_calls) == 4
    assert max(len(call["ids"]) for call in fake.selector_calls) <= 25
    assert result["selector"]["selectorBatchSize"] == 25
    assert len(result["selector"]["selectorBatches"]) == 4
    assert result["selector"]["rawSelectedIds"][:2] == ["doc-000", "doc-001"]
    assert "doc-025" in result["selector"]["rawSelectedIds"]
    assert result["beta6"]["selectedCount"] == 100


def test_beta6_selector_recovers_failed_large_batch_and_caches_recovery(tmp_path, monkeypatch):
    db_path = tmp_path / "wide.sqlite3"
    _make_many_precedents_db(db_path, count=120)
    fake = OversizedPromptBatchedSelectorLLMClient()
    monkeypatch.setenv("RELIGION_SELECTOR_CANDIDATE_LIMIT", "120")
    monkeypatch.setenv("RELIGION_SELECTOR_BATCH_SIZE", "100")
    monkeypatch.setenv("RELIGION_SELECTOR_RECOVERY_BATCH_SIZE", "25")
    monkeypatch.setenv("RELIGION_SELECTOR_BATCH_WORKERS", "1")
    runtime = Beta6JobManager({"islam": _profile(db_path)}, runs_root=tmp_path / "runs", llm_client=fake)

    first = runtime.answer_sync(product="islam", query="sharedterm recovery cache", language="en", limit=8)
    calls_after_first = len(fake.selector_calls)
    second = runtime.answer_sync(product="islam", query="sharedterm recovery cache", language="en", limit=8)

    assert calls_after_first == 6
    assert len(fake.selector_calls) == calls_after_first
    assert first["selector"]["status"] == "completed"
    assert first["selector"]["selectorBatches"][0]["recovered"] is True
    assert first["selector"]["selectorBatches"][0]["recoverySubBatchCount"] == 4
    assert first["selector"]["selectorBatchErrors"] == []
    assert first["selector"]["selectorBatchCacheMisses"] == 2
    assert second["selector"]["selectorBatchCacheHits"] == 2
    assert second["selector"]["selectorBatchCacheMisses"] == 0
    assert second["selector"]["selectorBatches"][0]["cacheHit"] is True
    assert second["selector"]["selectorBatches"][0]["recovered"] is True
    assert first["selector"]["rawSelectedIds"][:2] == ["doc-000", "doc-001"]
    assert "doc-025" in first["selector"]["rawSelectedIds"]


def test_simli_selector_starts_with_safe_chunks_without_timeout_recovery(tmp_path, monkeypatch):
    monkeypatch.delenv("RELIGION_SELECTOR_BATCH_SIZE", raising=False)
    monkeypatch.delenv("RELIGION_SIMLI_SELECTOR_BATCH_SIZE", raising=False)
    monkeypatch.setenv("RELIGION_SELECTOR_BATCH_WORKERS", "1")
    monkeypatch.setenv("RELIGION_SIMLI_SELECTOR_BATCH_WORKERS", "1")

    product = _simli_profile(tmp_path / "simli.sqlite3")
    candidates = [
        _result(f"doc-{index:03d}", f"sharedterm simli source {index}", source_kind="guideline")
        for index in range(120)
    ]
    fake = TimeoutLargeBatchSelectorLLMClient()

    rows, ids, _reasoning, meta = beta6_module.select_rows_with_beta6_selector(
        product,
        "sharedterm simli safe chunks",
        "ko",
        candidates,
        limit=100,
        llm_client=fake,
        model="gemma",
        cache_root=tmp_path / "simli-batch-cache",
    )

    assert meta["selectorBatchSize"] == 25
    assert len(fake.selector_calls) == 5
    assert max(len(call["ids"]) for call in fake.selector_calls) <= 25
    assert meta["selectorBatchErrors"] == []
    assert meta["selectorLocalRecoveryCount"] == 0
    assert all(not batch["recovered"] for batch in meta["selectorBatches"])
    assert all(not batch["localRecovery"] for batch in meta["selectorBatches"])
    assert "doc-025" in ids
    assert "doc-050" in ids
    assert rows


def test_beta6_selector_timeout_attempts_smaller_gemma4_batches_before_local_recovery(tmp_path, monkeypatch):
    product = _profile(tmp_path / "islam.sqlite3")
    candidates = [_result(f"doc-{index:03d}", f"sharedterm timeout source {index}", source_kind="fiqh") for index in range(120)]
    fake = TimeoutLargeBatchSelectorLLMClient()
    cache_root = tmp_path / "batch-cache"

    monkeypatch.setenv("RELIGION_SELECTOR_CANDIDATE_LIMIT", "120")
    monkeypatch.setenv("RELIGION_SELECTOR_BATCH_SIZE", "100")
    monkeypatch.setenv("RELIGION_SELECTOR_RECOVERY_BATCH_SIZE", "25")
    monkeypatch.setenv("RELIGION_SELECTOR_BATCH_WORKERS", "1")

    rows, ids, _reasoning, meta = beta6_module.select_rows_with_beta6_selector(
        product,
        "sharedterm timeout recover",
        "en",
        candidates,
        limit=100,
        llm_client=fake,
        model="gemma",
        cache_root=cache_root,
    )

    assert len(fake.selector_calls) == 6
    assert [len(call["ids"]) for call in fake.selector_calls[:5]] == [100, 25, 25, 25, 25]
    assert meta["selectorBatchErrors"] == []
    assert meta["selectorLocalRecoveryCount"] == 0
    assert meta["selectorBatches"][0]["recovered"] is True
    assert meta["selectorBatches"][0]["localRecovery"] is False
    assert meta["selectorBatches"][0]["recoverySubBatchCount"] == 4
    row_ids = [row.canonical_id for row in rows]
    assert "doc-000" in row_ids
    assert "doc-001" in row_ids
    assert "doc-025" in ids


def test_beta6_selector_timeout_batch_uses_cached_local_recovery(tmp_path, monkeypatch):
    product = _profile(tmp_path / "islam.sqlite3")
    candidates = [_result(f"doc-{index:03d}", f"sharedterm timeout source {index}", source_kind="fiqh") for index in range(120)]
    fake = TimeoutSelectorLLMClient()
    cache_root = tmp_path / "batch-cache"

    monkeypatch.setenv("RELIGION_SELECTOR_CANDIDATE_LIMIT", "120")
    monkeypatch.setenv("RELIGION_SELECTOR_BATCH_SIZE", "100")
    monkeypatch.setenv("RELIGION_SELECTOR_BATCH_WORKERS", "1")

    rows1, ids1, _reasoning1, meta1 = beta6_module.select_rows_with_beta6_selector(
        product,
        "sharedterm timeout",
        "en",
        candidates,
        limit=100,
        llm_client=fake,
        model="gemma",
        cache_root=cache_root,
    )
    calls_after_first = len(fake.selector_calls)
    rows2, ids2, _reasoning2, meta2 = beta6_module.select_rows_with_beta6_selector(
        product,
        "sharedterm timeout",
        "en",
        candidates,
        limit=100,
        llm_client=fake,
        model="gemma",
        cache_root=cache_root,
    )

    assert calls_after_first == 8
    assert len(fake.selector_calls) == calls_after_first
    assert meta1["selectorBatchErrors"] == []
    assert meta1["selectorBatchCacheMisses"] == 2
    assert all(batch["recovered"] for batch in meta1["selectorBatches"])
    assert all(batch["localRecovery"] for batch in meta1["selectorBatches"])
    assert meta1["selectorBatches"][0]["recoverySubBatchCount"] == 4
    assert meta1["selectorBatches"][0]["recoveryBatchSize"] == 25
    assert len(meta1["selectorBatches"][0]["recoveryErrors"]) == 4
    assert meta1["selectorBatchTrace"][0]["recoverySubBatchCount"] == 4
    assert meta1["selectorBatchTrace"][0]["recoveryErrorCount"] == 4
    assert meta1["selectorBatches"][1]["recoverySubBatchCount"] == 2
    assert meta1["selectorBatchTrace"][1]["recoverySubBatchCount"] == 2
    assert meta2["selectorBatchCacheHits"] == 2
    assert meta2["selectorBatchCacheMisses"] == 0
    assert all(batch["cacheHit"] for batch in meta2["selectorBatches"])
    assert [row.canonical_id for row in rows1] == [row.canonical_id for row in rows2]
    assert ids1 == ids2


def test_claim_card_span_matches_original_text_window_for_multiline_passages(tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    db_path.touch()
    profile = _profile(db_path)
    source_text = (
        "[META]\n"
        "source_kind: scripture\n\n"
        "[PRIMARY TEXT — ar]\n"
        "أَقِمِ الصَّلَاةَ لِدُلُوكِ الشَّمْسِ\n"
        "إِلَى غَسَقِ اللَّيْلِ\n"
        "[CONTEXT WINDOW]\n"
        "This sentence is only surrounding context.\n"
    )
    selected_records = [
        {
            "file_id": "doc-prayer",
            "document_title": "Prayer source",
            "case_number": "Prayer source",
            "doc_type": "scripture_window",
            "source_group": "structured_precedent",
            "extracted_text": source_text,
            "metadata": {"sourceKind": "scripture"},
        }
    ]
    selected_evidence = [{"id": "doc-prayer", "label": "S1", "citation": "Prayer source", "sourceKind": "scripture"}]

    cards = beta6_module.build_claim_cards(profile, "기도 시간", selected_records, selected_evidence, language="ko")
    windows = beta6_module.build_passage_windows(selected_records, cards)
    highlighted = windows[0]["text"][windows[0]["highlightStart"]:windows[0]["highlightEnd"]]

    assert cards[0]["quote"].startswith("أَقِمِ الصَّلَاةَ")
    assert "[PRIMARY TEXT" not in cards[0]["quote"]
    assert "[CONTEXT WINDOW]" not in cards[0]["quote"]
    assert highlighted == cards[0]["span"]["exact"] == cards[0]["quote"]


def test_beta6_selector_uses_bounded_stage_timeout_before_fallback(tmp_path, monkeypatch):
    db_path = tmp_path / "wide.sqlite3"
    _make_many_precedents_db(db_path, count=120)
    fake = StageTimeoutLLMClient()
    monkeypatch.setenv("RELIGION_SELECTOR_TIMEOUT_SECONDS", "12")
    runtime = Beta6JobManager({"islam": _profile(db_path)}, runs_root=tmp_path / "runs", llm_client=fake)

    result = runtime.answer_sync(product="islam", query="sharedterm", language="en", limit=8)

    selector_calls = [call for call in fake.calls if "source selector" in call["system"]]
    writer_calls = [call for call in fake.calls if "source-grounded answer engine" in call["system"]]
    assert selector_calls
    assert selector_calls[0]["timeout_seconds"] == 12
    assert writer_calls
    assert writer_calls[0]["timeout_seconds"] is None
    assert result["selector"]["status"] == "fallback_selector_error"
    assert result["beta6"]["selectedCount"] == 100
    assert result["answer"].startswith("writer after bounded selector fallback")


def test_beta6_result_records_stage_timing_breakdown(tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    runtime = Beta6JobManager({"islam": _profile(db_path)}, runs_root=tmp_path / "runs", llm_client=FakeLLMClient())

    result = runtime.answer_sync(product="islam", query="qibla prayer", language="en", limit=3)

    stage_timings = result["beta6"]["stageTimings"]
    totals = result["beta6"]["stageTimingTotals"]
    stages = [entry["stage"] for entry in stage_timings]
    for expected in (
        "starting",
        "candidate_search",
        "source_selection",
        "chunking",
        "claim_cards",
        "answer_plan",
        "writer",
        "coverage",
        "completed",
    ):
        assert expected in stages
        assert expected in totals
        assert totals[expected] >= 0
    assert result["beta6"]["stageTimingTotalSec"] >= 0
    assert sum(entry["seconds"] for entry in stage_timings) >= 0
    run_dir = tmp_path / "runs" / result["jobId"]
    persisted = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    assert persisted["beta6"]["stageTimings"] == stage_timings


def test_beta6_wall_clock_uses_monotonic_stage_timer_when_system_clock_is_flat(monkeypatch, tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    monkeypatch.setattr(beta6_module.time, "time", lambda: 1000.0)
    runtime = Beta6JobManager({"islam": _profile(db_path)}, runs_root=tmp_path / "runs", llm_client=SlowLLMClient())

    result = runtime.answer_sync(product="islam", query="qibla prayer", language="en", limit=3)

    assert result["beta6"]["stageTimingTotalSec"] > 0
    assert result["beta6"]["wallClockSec"] >= result["beta6"]["stageTimingTotalSec"]


def test_beta6_runtime_writes_lawkey_style_artifacts(tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    fake = FakeLLMClient()
    runtime = Beta6JobManager({"islam": _profile(db_path)}, runs_root=tmp_path / "runs", llm_client=fake)

    result = runtime.answer_sync(product="islam", query="qibla prayer", language="en", limit=3)

    assert result["answer"].startswith("LLM beta6 answer")
    assert result["llmUsed"] is True
    assert result["writer"]["status"] == "completed"
    assert result["writer"]["mode"] == "llm_writer"
    assert result["answerReadiness"] == "final_answer"
    assert result["sources"][0]["id"] in {"doc-fiqh-1", "doc-quran-1"}
    assert result["beta6SelectedRecords"][0]["file_id"] == result["sources"][0]["id"]
    run_dir = tmp_path / "runs" / result["jobId"]
    assert json.loads((run_dir / "selected_records.json").read_text(encoding="utf-8"))[0]["file_id"] == result["sources"][0]["id"]
    assert json.loads((run_dir / "chunk_plan.json").read_text(encoding="utf-8"))[0]["chunk_id"]
    assert result["beta6"]["chunker"] == "lawkey_legal_evidence_rag"
    prompt = json.loads((run_dir / "prompt_input.json").read_text(encoding="utf-8"))
    assert any("quran safety notice" in call["messages"][0]["content"] for call in fake.calls)
    assert "qibla prayer" in prompt["messages"][1]["content"]
    assert result["artifacts"]["selectedRecords"].endswith("selected_records.json")


def test_beta6_runtime_requires_writer_without_llm_instead_of_final_answer(tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    runtime = Beta6JobManager({"islam": _profile(db_path)}, runs_root=tmp_path / "runs")

    result = runtime.answer_sync(product="islam", query="qibla prayer", language="en", limit=3)

    assert result["llmUsed"] is False
    assert result["writer"]["status"] == "requires_llm"
    assert result["writer"]["mode"] == "evidence_selection_only"
    assert result["answerReadiness"] == "evidence_selected_writer_required"
    assert result["answer"].startswith("## Evidence selected - writer required")
    assert "Grounded answer" not in result["answer"]
    assert result["beta6"]["chunkTokenBudget"] == 100_000


def test_user_visible_beta6_copy_hides_internal_engine_names(tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    runtime = Beta6JobManager({"islam": _profile(db_path)}, runs_root=tmp_path / "runs")

    result = runtime.answer_sync(product="islam", query="qibla prayer", language="en", limit=3)
    visible_text = "\n".join(
        [
            result["answer"],
            result["writer"]["message"],
            result["beta6"].get("message", ""),
        ]
    ).lower()

    assert "beta-6" not in visible_text
    assert "beta6" not in visible_text
    assert "answersections" not in visible_text
    assert "citationmap" not in visible_text
    assert "passages" not in visible_text
    assert "generating beta6 search keywords" not in inspect.getsource(beta6_module.select_rows_with_beta6_llm)


def test_beta6_runtime_prefers_user_question_language_over_ui_language(tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    fake = FakeLLMClient()
    runtime = Beta6JobManager({"islam": _profile(db_path)}, runs_root=tmp_path / "runs", llm_client=fake)

    result = runtime.answer_sync(product="islam", query="기도 방향은 어떻게 정하나요?", language="en", limit=3)

    assert result["language"] == "ko"
    assert result["languageResolution"]["detectedLanguage"] == "ko"
    assert result["languageResolution"]["uiLanguage"] == "en"
    assert any("Answer language: ko" in call["messages"][1]["content"] for call in fake.calls)


def test_islam_beta6_result_is_structured_school_framed_and_not_fatwa(tmp_path):
    db_path = tmp_path / "islam-school.sqlite3"
    _make_islam_school_db(db_path)
    runtime = Beta6JobManager({"islam": _profile(db_path)}, runs_root=tmp_path / "runs")

    result = runtime.answer_sync(
        product="islam",
        query="결혼할 때 보호자가 필요한가 학파별로 알려줘",
        language="en",
        limit=4,
    )

    assert result["language"] == "ko"
    assert result["llmUsed"] is False
    assert result["writer"]["status"] == "requires_llm"
    assert result["answerReadiness"] == "evidence_selected_writer_required"
    assert result["answerSections"]
    assert result["citationMap"]
    assert result["passages"]
    assert result["selectedEvidence"]
    assert result["beta6"]["analysisMode"] == "beta6"
    assert result["beta6"]["queryStructuring"]["expandedTerms"]
    section_text = " ".join(
        f"{section.get('title', '')} {section.get('body', '')}" for section in result["answerSections"]
    )
    assert "학파" in section_text
    assert "구속력 있는 파트와" in section_text
    assert "최종 판결" not in result["answerMarkdown"]


def test_islam_writer_prompt_requires_school_or_sect_scope_section_when_relevant(tmp_path):
    db_path = tmp_path / "islam-school.sqlite3"
    _make_islam_school_db(db_path)
    fake = FakeLLMClient()
    runtime = Beta6JobManager({"islam": _profile(db_path)}, runs_root=tmp_path / "runs", llm_client=fake)

    runtime.answer_sync(
        product="islam",
        query="사회주의는 하람임? 학파와 종파별로 단정하지 말고 정리해줘",
        language="ko",
        limit=4,
    )

    writer_call = [call for call in fake.calls if "source-grounded answer engine" in call["messages"][0]["content"]][-1]
    prompt = writer_call["messages"][1]["content"]

    assert "학파/종파별 자료 범위와 공백" in prompt
    assert "If no selected claim card supports a requested school or sect" in prompt
    assert "do not collapse all schools into a single ruling" in prompt


def test_islam_beta6_fallback_uses_arabic_for_arabic_question(tmp_path):
    db_path = tmp_path / "islam-school.sqlite3"
    _make_islam_school_db(db_path)
    runtime = Beta6JobManager({"islam": _profile(db_path)}, runs_root=tmp_path / "runs")

    result = runtime.answer_sync(product="islam", query="هل يشترط الولي في النكاح؟", language="en", limit=3)

    assert result["language"] == "ar"
    assert result["languageResolution"]["detectedLanguage"] == "ar"
    assert result["writer"]["status"] == "requires_llm"
    assert result["answerMarkdown"].startswith("## اكتمل اختيار الأدلة")
    section_text = " ".join(
        f"{section.get('title', '')} {section.get('body', '')}" for section in result["answerSections"]
    )
    assert "فتوى ملزمة" in section_text


def test_tcm_beta6_result_is_structured_classical_and_not_prescriptive(tmp_path):
    db_path = tmp_path / "tcm-domain.sqlite3"
    _make_tcm_domain_db(db_path)
    runtime = Beta6JobManager({"tcm": _tcm_profile(db_path)}, runs_root=tmp_path / "runs")

    result = runtime.answer_sync(
        product="tcm",
        query="감초를 임신 중 써도 되는지 고문헌과 본초 금기 근거로 정리해줘",
        language="en",
        limit=4,
    )

    assert result["language"] == "ko"
    assert result["llmUsed"] is False
    assert result["writer"]["status"] == "requires_llm"
    assert result["answerReadiness"] == "evidence_selected_writer_required"
    assert result["answerSections"]
    assert result["citationMap"]
    assert result["passages"]
    assert result["selectedEvidence"]
    assert result["beta6"]["queryStructuring"]["expandedTerms"]
    assert result["answerMarkdown"].startswith("## 근거 선택 완료 - 답변 작성 대기")
    section_text = " ".join(
        f"{section.get('title', '')} {section.get('body', '')}" for section in result["answerSections"]
    )
    assert "문헌" in section_text
    assert "금기" in section_text or "안전" in section_text
    assert "진단이나 처방" in section_text
    assert "복용하세요" not in result["answerMarkdown"]


def test_tcm_beta6_mcq_uses_at_least_one_slot_per_option_by_default(tmp_path, monkeypatch):
    db_path = tmp_path / "tcm-domain.sqlite3"
    profile = _tcm_profile(db_path)
    query = """1. 다음 치방은?
0 합개환
@ 형소탕
3 소속명탕
0) 복령보심탕
09) 향성파적환"""

    monkeypatch.delenv("RELIGION_MCQ_HEURISTICS_ENABLED", raising=False)
    monkeypatch.delenv("RELIGION_MCQ_STRUCTURE_ENABLED", raising=False)
    assert beta6_module._beta6_top_k_for_query(profile, "감초 금기", 4, fast_mode=True) == 4
    assert beta6_module._beta6_top_k_for_query(profile, query, 4, fast_mode=True) == 5


def test_tcm_beta6_mcq_top_k_expansion_can_be_disabled_with_structure_flag(tmp_path, monkeypatch):
    db_path = tmp_path / "tcm-domain.sqlite3"
    profile = _tcm_profile(db_path)
    query = """1. 다음 치방은?
0 합개환
@ 형소탕
3 소속명탕
0) 복령보심탕
09) 향성파적환"""

    monkeypatch.setenv("RELIGION_MCQ_STRUCTURE_ENABLED", "0")
    assert beta6_module._beta6_top_k_for_query(profile, "감초 금기", 4, fast_mode=True) == 4
    assert beta6_module._beta6_top_k_for_query(profile, query, 4, fast_mode=True) == 4


def test_tcm_selector_error_fallback_keeps_original_query_authority_before_keyword_noise(tmp_path):
    db_path = tmp_path / "tcm-domain.sqlite3"
    _make_tcm_domain_db(db_path)
    conn = sqlite3.connect(db_path)
    noisy_text = """[META]
religion: tcm-kmm
tradition: tcm
school: tcm-clinical
authority_level: 50
source_kind: case_record
authority_label: case record

甘草 감초 licorice 妊娠 임신 pregnancy 本草 본초 禁忌 금기 contraindication safety """ * 8
    conn.execute(
        "INSERT INTO precedents VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            "doc-noisy-case",
            "tcm-kmm/tcm/tcm-clinical/case_record",
            "cases/noisy",
            "Noisy case",
            "Case #noisy",
            "case collection",
            "",
            "noisy case",
            "case_record_unit",
            noisy_text,
            "hash-noisy",
        ),
    )
    conn.execute("INSERT INTO precedents_fts(canonical_id, full_text) VALUES (?, ?)", ("doc-noisy-case", noisy_text))
    conn.commit()
    conn.close()
    runtime = Beta6JobManager(
        {"tcm": _tcm_profile(db_path)},
        runs_root=tmp_path / "runs",
        llm_client=TcmNoisyKeywordLLMClient(),
    )

    result = runtime.answer_sync(
        product="tcm",
        query="감초를 임신 중 써도 되는지 본초 금기 근거로 정리해줘",
        language="ko",
        limit=4,
    )

    assert result["selector"]["status"] == "fallback_selector_error"
    kinds = [item["sourceKind"] for item in result["selectedEvidence"]]
    ids = {item["id"] for item in result["selectedEvidence"]}
    assert "classic_canon" in kinds
    assert "materia_medica" in kinds
    assert ids != {"doc-noisy-case"}
    assert result["answer"].startswith("writer used fallback-selected evidence")


def test_tcm_beta6_prefers_english_question_language_over_korean_ui(tmp_path):
    db_path = tmp_path / "tcm-domain.sqlite3"
    _make_tcm_domain_db(db_path)
    fake = FakeLLMClient()
    runtime = Beta6JobManager({"tcm": _tcm_profile(db_path)}, runs_root=tmp_path / "runs", llm_client=fake)

    result = runtime.answer_sync(
        product="tcm",
        query="What do classical sources say about licorice contraindications in pregnancy?",
        language="ko",
        limit=4,
    )

    assert result["language"] == "en"
    assert result["languageResolution"]["detectedLanguage"] == "en"
    assert result["languageResolution"]["uiLanguage"] == "ko"
    assert any("Answer language: en" in call["messages"][1]["content"] for call in fake.calls)
    assert any("do not diagnose or prescribe" in call["messages"][0]["content"] for call in fake.calls)
    assert any("not an instruction for the user to take it" in call["messages"][0]["content"] for call in fake.calls)


def test_simli_writer_prompt_forbids_user_specific_diagnosis(tmp_path):
    db_path = tmp_path / "psych.sqlite3"
    _make_documents_db(db_path)
    fake = FakeLLMClient()
    runtime = Beta6JobManager({"simli": _simli_profile(db_path)}, runs_root=tmp_path / "runs", llm_client=fake)

    result = runtime.answer_sync(product="simli", query="요즘 잠이 안 오고 계속 불안합니다", language="ko", limit=3)

    assert result["language"] == "ko"
    assert any("do not diagnose or say the user has a disorder" in call["messages"][0]["content"] for call in fake.calls)
    assert any("not 'you may have GAD'" in call["messages"][0]["content"] for call in fake.calls)
    assert any("cite CBT/therapy papers when explaining CBT" in call["messages"][1]["content"] for call in fake.calls)
    assert any("patient cases only for differential medical examples" in call["messages"][1]["content"] for call in fake.calls)
    assert any("writer_use:" in call["messages"][1]["content"] for call in fake.calls)


def test_simli_writer_prompt_uses_original_clinical_answer_sections(tmp_path):
    db_path = tmp_path / "psych.sqlite3"
    _make_documents_db(db_path)
    fake = FakeLLMClient()
    runtime = Beta6JobManager({"simli": _simli_profile(db_path)}, runs_root=tmp_path / "runs", llm_client=fake)

    runtime.answer_sync(product="simli", query="불안하고 잠이 안 와요", language="ko", limit=3)

    writer_call = [call for call in fake.calls if "source-grounded answer engine" in call["messages"][0]["content"]][-1]
    prompt = writer_call["messages"][1]["content"]

    assert "## 1. 가능 가설 (Differential)" in prompt
    assert "## 2. 왜 이 가설인가 (Rationale)" in prompt
    assert "## 3. 추가 평가 필요 (What to Probe Next)" in prompt
    assert "## 4. 다음 세션 개입 (Next-Session Action Plan)" in prompt
    assert "## 5. 약물 / 의뢰 고려 (Pharm & Referral)" in prompt
    assert "## 6. 안전 계획 + 모니터링 (Safety & Monitoring)" in prompt
    assert "## 7. 근거 한계 (Evidence Gaps)" in prompt
    assert "## References" in prompt
    assert "Do not write verbatim quote text inline" in prompt


def test_beta6_runtime_exposes_engine_agnostic_structured_contract(tmp_path):
    db_path = tmp_path / "tcm-domain.sqlite3"
    _make_tcm_domain_db(db_path)
    runtime = Beta6JobManager({"tcm": _tcm_profile(db_path)}, runs_root=tmp_path / "runs")

    result = runtime.answer_sync(product="tcm", query="감초 금기", language="ko", limit=3)

    assert result["engine"]["name"] == "beta6"
    assert result["engine"]["contractVersion"] == "source-grounded-v2"
    assert result["engine"]["handoffKeys"] == [
        "answerSections",
        "citationMap",
        "passages",
        "selectedEvidence",
        "claimCards",
        "candidateClaimCards",
        "citedClaimCards",
        "passageWindows",
        "answerPlan",
        "coverageReport",
    ]
    assert result["writer"]["status"] == "requires_llm"
    assert result["answerReadiness"] == "evidence_selected_writer_required"
    for key in result["engine"]["handoffKeys"]:
        assert key in result


def test_create_app_defers_default_runtime_resume_until_startup(monkeypatch, tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    resume_calls = []

    def fake_resume(self, *, limit=None):
        resume_calls.append(limit)
        return 0

    monkeypatch.setattr(beta6_module.Beta6JobManager, "_resume_durable_jobs", fake_resume)

    app = create_app({"islam": _profile(db_path)})

    assert resume_calls == []
    assert app.state.beta6_runtime._resume_pending_started is False
    with TestClient(app):
        assert resume_calls == [None]
    assert app.state.beta6_runtime._resume_pending_started is True


def test_api_exposes_beta6_job_lifecycle(tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    runtime = Beta6JobManager({"islam": _profile(db_path)}, runs_root=tmp_path / "runs", llm_client=FakeLLMClient())
    client = TestClient(create_app({"islam": _profile(db_path)}, runtime=runtime, rate_limit_per_minute=20))

    session_headers = {"X-Beta6-Session-Token": "runtime-session-token-abcdefghijklmnopqrstuvwxyz"}
    created = client.post(
        "/api/islam/jobs",
        headers=session_headers,
        json={"query": "qibla prayer", "language": "en", "limit": 3},
    )

    assert created.status_code == 200
    job_id = created.json()["jobId"]
    token = created.json()["accessToken"]
    for _ in range(120):
        status = client.get(f"/api/jobs/{job_id}", headers=session_headers, params={"token": token}).json()
        if status["status"] == "completed":
            break
        time.sleep(0.05)
    result = client.get(f"/api/jobs/{job_id}/result", headers=session_headers, params={"token": token})

    assert result.status_code == 200
    body = result.json()
    assert body["jobId"] == job_id
    assert body["answer"].startswith("LLM beta6 answer")
    assert body["beta6"]["analysisMode"] == "beta6"


def test_beta6_runtime_persists_queued_and_running_job_status_for_restart_resume(monkeypatch, tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    runs_root = tmp_path / "runs"
    runtime = Beta6JobManager({"islam": _profile(db_path)}, runs_root=runs_root, max_workers=1)
    started = threading.Event()
    release = threading.Event()

    def blocking_run_context(context):
        started.set()
        release.wait(timeout=3)
        return {"jobId": context.job_id}

    monkeypatch.setattr(runtime, "_run_context", blocking_run_context)

    created = runtime.create_job(product="islam", query="qibla prayer", language="en", limit=3, session_token=SESSION_TOKEN)
    job_id = created["jobId"]

    assert started.wait(timeout=1)
    status_path = runs_root / job_id / "status.json"
    assert status_path.exists()
    persisted = json.loads(status_path.read_text(encoding="utf-8"))
    assert persisted["status"] in {"queued", "running"}
    resumed = Beta6JobManager({"islam": _profile(db_path)}, runs_root=runs_root, max_workers=1)
    assert resumed.get_status(job_id)["status"] in {"queued", "running"}
    release.set()


def test_beta6_runtime_writes_durable_request_snapshot_for_async_jobs(monkeypatch, tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    runs_root = tmp_path / "runs"
    runtime = Beta6JobManager({"islam": _profile(db_path)}, runs_root=runs_root, max_workers=1)
    release = threading.Event()

    def blocking_run_context(context):
        release.wait(timeout=3)
        return {"jobId": context.job_id}

    monkeypatch.setattr(runtime, "_run_context", blocking_run_context)

    created = runtime.create_job(product="islam", query="qibla prayer", language="en", limit=3, session_token=SESSION_TOKEN)
    job_id = created["jobId"]

    request_path = runs_root / job_id / "request.json"
    assert request_path.exists()
    request = json.loads(request_path.read_text(encoding="utf-8"))
    assert request["jobId"] == job_id
    assert request["product"] == "islam"
    assert request["query"] == "qibla prayer"
    assert request["language"] == "en"
    assert request["uiLanguage"] == "en"
    assert request["detectedLanguage"] == "en"
    assert request["limit"] >= 3
    assert request["sessionTokenHash"]
    assert SESSION_TOKEN not in request_path.read_text(encoding="utf-8")
    release.set()


def test_beta6_runtime_resumes_dead_owner_job_from_request_snapshot(tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    runs_root = tmp_path / "runs"
    job_dir = runs_root / "job-resume"
    job_dir.mkdir(parents=True)
    (job_dir / "request.json").write_text(
        json.dumps(
            {
                "jobId": "job-resume",
                "product": "islam",
                "query": "qibla prayer",
                "language": "en",
                "uiLanguage": "en",
                "detectedLanguage": "en",
                "limit": 3,
            }
        ),
        encoding="utf-8",
    )
    (job_dir / "status.json").write_text(
        json.dumps(
            {
                "jobId": "job-resume",
                "product": "islam",
                "query": "qibla prayer",
                "language": "en",
                "uiLanguage": "en",
                "detectedLanguage": "en",
                "status": "running",
                "analysisMode": "beta6",
                "selectedCount": 0,
                "error": "",
                "ownerPid": 999999999,
            }
        ),
        encoding="utf-8",
    )

    restored = Beta6JobManager(
        {"islam": _profile(db_path)},
        runs_root=runs_root,
        max_workers=1,
        resume_pending_jobs=True,
    )

    status = {}
    for _ in range(80):
        status = restored.get_status("job-resume")
        if status["status"] == "completed":
            break
        time.sleep(0.05)

    result = restored.get_result("job-resume")
    assert status["status"] == "completed"
    assert result["jobId"] == "job-resume"
    assert result["query"] == "qibla prayer"
    assert result["product"] == "islam"


def test_beta6_runtime_resumes_from_selected_records_checkpoint_without_rerunning_selector(tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    runs_root = tmp_path / "runs"
    job_dir = runs_root / "job-stage-resume"
    job_dir.mkdir(parents=True)
    profile = _profile(db_path)
    selected_record = beta6_module.to_beta6_selected_record(
        _result("doc-checkpoint", "qibla prayer selected checkpoint evidence", source_kind="fiqh")
    )
    (job_dir / "request.json").write_text(
        json.dumps(
            {
                "jobId": "job-stage-resume",
                "product": "islam",
                "query": "qibla prayer",
                "language": "en",
                "uiLanguage": "en",
                "detectedLanguage": "en",
                "limit": 1,
            }
        ),
        encoding="utf-8",
    )
    (job_dir / "status.json").write_text(
        json.dumps(
            {
                "jobId": "job-stage-resume",
                "product": "islam",
                "query": "qibla prayer",
                "language": "en",
                "uiLanguage": "en",
                "detectedLanguage": "en",
                "status": "running",
                "analysisMode": "beta6",
                "selectedCount": 1,
                "error": "",
                "ownerPid": 999999999,
                "progress": {"stage": "claim_cards"},
            }
        ),
        encoding="utf-8",
    )
    (job_dir / "selected_records.json").write_text(json.dumps([selected_record]), encoding="utf-8")
    (job_dir / "selector_meta.json").write_text(
        json.dumps(
            {
                "status": "completed",
                "mode": "checkpoint_fixture_selector",
                "provider": "fixture",
                "model": "fixture",
                "candidateCount": 1,
                "topK": 1,
                "selectedIds": ["doc-checkpoint"],
            }
        ),
        encoding="utf-8",
    )
    fake = CheckpointResumeLLMClient()

    restored = Beta6JobManager(
        {"islam": profile},
        runs_root=runs_root,
        llm_client=fake,
        max_workers=1,
        resume_pending_jobs=True,
    )

    status = {}
    for _ in range(80):
        status = restored.get_status("job-stage-resume")
        if status["status"] == "completed":
            break
        time.sleep(0.05)

    result = restored.get_result("job-stage-resume")
    called_systems = [call["system"] for call in fake.calls]
    assert status["status"] == "completed"
    assert not any("keyword generator" in system for system in called_systems)
    assert not any("source selector" in system for system in called_systems)
    assert result["sources"][0]["id"] == "doc-checkpoint"
    assert result["selector"]["mode"] == "checkpoint_fixture_selector"
    assert result["beta6"]["checkpointResume"]["selectedRecords"] is True
    assert "selected_records" in result["beta6"]["checkpointResume"]["reusedArtifacts"]


def test_beta6_runtime_resumes_from_claim_card_checkpoint_without_rerunning_analyzer(tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    runs_root = tmp_path / "runs"
    job_dir = runs_root / "job-claim-stage-resume"
    job_dir.mkdir(parents=True)
    selected_record = beta6_module.to_beta6_selected_record(
        _result("doc-claim-checkpoint", "qibla prayer claim checkpoint evidence", source_kind="fiqh")
    )
    claim_card = {
        "claimId": "C1",
        "label": "S1",
        "sourceId": "doc-claim-checkpoint",
        "citation": "doc-claim-checkpoint",
        "role": "fiqh",
        "claimAxis": "checkpoint axis",
        "stance": "support",
        "contextSummary": "checkpoint context summary",
        "claimSummary": "checkpoint claim summary",
        "quote": "qibla prayer claim checkpoint evidence",
        "span": {"start": 0, "end": 39, "exact": "qibla prayer claim checkpoint evidence"},
        "quoteVerified": True,
        "analysisSource": "checkpoint_fixture",
    }
    (job_dir / "request.json").write_text(
        json.dumps(
            {
                "jobId": "job-claim-stage-resume",
                "product": "islam",
                "query": "qibla prayer",
                "language": "en",
                "uiLanguage": "en",
                "detectedLanguage": "en",
                "limit": 1,
            }
        ),
        encoding="utf-8",
    )
    (job_dir / "status.json").write_text(
        json.dumps(
            {
                "jobId": "job-claim-stage-resume",
                "product": "islam",
                "query": "qibla prayer",
                "language": "en",
                "uiLanguage": "en",
                "detectedLanguage": "en",
                "status": "running",
                "analysisMode": "beta6",
                "selectedCount": 1,
                "error": "",
                "ownerPid": 999999999,
                "progress": {"stage": "answer_plan"},
            }
        ),
        encoding="utf-8",
    )
    (job_dir / "selected_records.json").write_text(json.dumps([selected_record]), encoding="utf-8")
    (job_dir / "selector_meta.json").write_text(
        json.dumps({"status": "completed", "mode": "checkpoint_fixture_selector", "selectedIds": ["doc-claim-checkpoint"]}),
        encoding="utf-8",
    )
    (job_dir / "claim_cards.json").write_text(json.dumps([claim_card]), encoding="utf-8")
    (job_dir / "claim_analyzer_meta.json").write_text(
        json.dumps({"status": "completed", "mode": "checkpoint_fixture_claim_cards"}),
        encoding="utf-8",
    )
    fake = ClaimCheckpointResumeLLMClient()

    restored = Beta6JobManager(
        {"islam": _profile(db_path)},
        runs_root=runs_root,
        llm_client=fake,
        max_workers=1,
        resume_pending_jobs=True,
    )

    status = {}
    for _ in range(80):
        status = restored.get_status("job-claim-stage-resume")
        if status["status"] == "completed":
            break
        time.sleep(0.05)

    result = restored.get_result("job-claim-stage-resume")
    called_systems = [call["system"] for call in fake.calls]
    assert status["status"] == "completed"
    assert not any("claim-card analyzer" in system for system in called_systems)
    assert result["claimCards"][0]["contextSummary"] == "checkpoint context summary"
    assert result["beta6"]["checkpointResume"]["claimCards"] is True
    assert "claim_cards" in result["beta6"]["checkpointResume"]["reusedArtifacts"]


def test_beta6_runtime_resumes_from_answer_plan_checkpoint_without_rerunning_planner(tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    runs_root = tmp_path / "runs"
    job_dir = runs_root / "job-plan-stage-resume"
    job_dir.mkdir(parents=True)
    selected_record = beta6_module.to_beta6_selected_record(
        _result("doc-plan-checkpoint", "qibla prayer plan checkpoint evidence", source_kind="fiqh")
    )
    claim_card = {
        "claimId": "C1",
        "label": "S1",
        "sourceId": "doc-plan-checkpoint",
        "citation": "doc-plan-checkpoint",
        "role": "fiqh",
        "claimAxis": "checkpoint axis",
        "stance": "support",
        "contextSummary": "checkpoint context summary",
        "claimSummary": "checkpoint plan claim summary",
        "quote": "qibla prayer plan checkpoint evidence",
        "span": {"start": 0, "end": 38, "exact": "qibla prayer plan checkpoint evidence"},
        "quoteVerified": True,
        "analysisSource": "checkpoint_fixture",
    }
    answer_plan = {
        "status": "completed",
        "mode": "checkpoint_fixture_answer_plan",
        "provider": "fixture",
        "model": "fixture",
        "bodyClaimIds": ["C1"],
        "coverageRequiredClaimIds": ["C1"],
        "claimGroups": [{"title": "checkpoint group", "claimIds": ["C1"], "summary": "checkpoint plan"}],
        "answerOutline": ["checkpoint outline"],
        "citationPolicy": "cite checkpoint claim",
    }
    (job_dir / "request.json").write_text(
        json.dumps(
            {
                "jobId": "job-plan-stage-resume",
                "product": "islam",
                "query": "qibla prayer",
                "language": "en",
                "uiLanguage": "en",
                "detectedLanguage": "en",
                "limit": 1,
            }
        ),
        encoding="utf-8",
    )
    (job_dir / "status.json").write_text(
        json.dumps(
            {
                "jobId": "job-plan-stage-resume",
                "product": "islam",
                "query": "qibla prayer",
                "language": "en",
                "uiLanguage": "en",
                "detectedLanguage": "en",
                "status": "running",
                "analysisMode": "beta6",
                "selectedCount": 1,
                "error": "",
                "ownerPid": 999999999,
                "progress": {"stage": "writer"},
            }
        ),
        encoding="utf-8",
    )
    (job_dir / "selected_records.json").write_text(json.dumps([selected_record]), encoding="utf-8")
    (job_dir / "selector_meta.json").write_text(
        json.dumps({"status": "completed", "mode": "checkpoint_fixture_selector", "selectedIds": ["doc-plan-checkpoint"]}),
        encoding="utf-8",
    )
    (job_dir / "claim_cards.json").write_text(json.dumps([claim_card]), encoding="utf-8")
    (job_dir / "claim_analyzer_meta.json").write_text(
        json.dumps({"status": "completed", "mode": "checkpoint_fixture_claim_cards"}),
        encoding="utf-8",
    )
    (job_dir / "answer_plan.json").write_text(json.dumps(answer_plan), encoding="utf-8")
    fake = PlanCheckpointResumeLLMClient()

    restored = Beta6JobManager(
        {"islam": _profile(db_path)},
        runs_root=runs_root,
        llm_client=fake,
        max_workers=1,
        resume_pending_jobs=True,
    )

    status = {}
    for _ in range(80):
        status = restored.get_status("job-plan-stage-resume")
        if status["status"] == "completed":
            break
        time.sleep(0.05)

    result = restored.get_result("job-plan-stage-resume")
    called_systems = [call["system"] for call in fake.calls]
    assert status["status"] == "completed"
    assert not any("answer planner" in system for system in called_systems)
    assert result["answerPlan"]["mode"] == "checkpoint_fixture_answer_plan"
    assert result["beta6"]["checkpointResume"]["answerPlan"] is True
    assert "answer_plan" in result["beta6"]["checkpointResume"]["reusedArtifacts"]


def test_beta6_runtime_exposes_stage_progress_and_elapsed_for_running_jobs(monkeypatch, tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    runs_root = tmp_path / "runs"
    runtime = Beta6JobManager({"islam": _profile(db_path)}, runs_root=runs_root, max_workers=1)
    entered = threading.Event()
    release = threading.Event()

    def slow_select_rows(product, query, language, *, limit, llm_client, model, provider, progress_callback=None):
        assert progress_callback is not None
        progress_callback("candidate_search", "fixture search is blocked")
        entered.set()
        release.wait(timeout=3)
        return [_result("doc-progress", "qibla prayer evidence", source_kind="fiqh")], {
            "status": "skipped",
            "mode": "fixture",
            "candidateCount": 1,
            "topK": limit,
        }

    monkeypatch.setattr(beta6_module, "select_rows_with_beta6_llm", slow_select_rows)

    created = runtime.create_job(product="islam", query="qibla prayer", language="en", limit=3, session_token=SESSION_TOKEN)
    job_id = created["jobId"]

    assert entered.wait(timeout=1)
    status = runtime.get_status(job_id)
    progress = status["progress"]
    assert status["status"] == "running"
    assert status["elapsedSeconds"] >= 0
    assert progress["stage"] == "candidate_search"
    assert progress["stageIndex"] > 0
    assert progress["stageCount"] >= progress["stageIndex"]
    assert progress["percent"] > 0
    assert progress["label"]
    assert progress["message"] == "fixture search is blocked"
    assert progress["elapsedSeconds"] == status["elapsedSeconds"]
    persisted = json.loads((runs_root / job_id / "status.json").read_text(encoding="utf-8"))
    assert persisted["progress"]["stage"] == "candidate_search"
    release.set()


def test_beta6_running_progress_elapsed_uses_monotonic_clock_when_system_clock_is_flat(monkeypatch, tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    runtime = Beta6JobManager({"islam": _profile(db_path)}, runs_root=tmp_path / "runs", max_workers=1)
    entered = threading.Event()
    release = threading.Event()

    def slow_select_rows(product, query, language, *, limit, llm_client, model, provider, progress_callback=None):
        progress_callback("candidate_search", "fixture search is blocked")
        entered.set()
        release.wait(timeout=3)
        return [_result("doc-progress", "qibla prayer evidence", source_kind="fiqh")], {
            "status": "skipped",
            "mode": "fixture",
            "candidateCount": 1,
            "topK": limit,
        }

    monkeypatch.setattr(beta6_module, "select_rows_with_beta6_llm", slow_select_rows)
    monkeypatch.setattr(beta6_module.time, "time", lambda: 1000.0)
    try:
        created = runtime.create_job(product="islam", query="qibla prayer", language="en", limit=3, session_token=SESSION_TOKEN)
        job_id = created["jobId"]

        assert entered.wait(timeout=1)
        time.sleep(0.15)
        status = runtime.get_status(job_id)

        assert status["status"] == "running"
        assert status["elapsedSeconds"] > 0
        assert status["progress"]["elapsedSeconds"] == status["elapsedSeconds"]
        assert "monotonicCreatedAt" not in status
        assert "monotonicElapsedSeconds" not in status
    finally:
        release.set()


def test_beta6_runtime_periodically_heartbeats_running_job_lease(monkeypatch, tmp_path):
    monkeypatch.setenv("RELIGION_JOB_HEARTBEAT_INTERVAL_SECONDS", "0.05")
    monkeypatch.setenv("RELIGION_JOB_LEASE_TIMEOUT_SECONDS", "1")
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    runs_root = tmp_path / "runs"
    runtime = Beta6JobManager({"islam": _profile(db_path)}, runs_root=runs_root, max_workers=1)
    entered = threading.Event()
    release = threading.Event()

    def blocking_run_context(context):
        entered.set()
        release.wait(timeout=5)
        return {}

    monkeypatch.setattr(runtime, "_run_context", blocking_run_context)
    try:
        created = runtime.create_job(product="islam", query="qibla prayer", language="en", limit=3, session_token=SESSION_TOKEN)
        job_id = created["jobId"]

        assert entered.wait(timeout=1)
        first = runtime.get_status(job_id)
        first_lease = first["workerLease"]
        time.sleep(0.2)
        second = runtime.get_status(job_id)
        second_lease = second["workerLease"]

        assert first["status"] == "running"
        assert first_lease["ownerPid"] == os.getpid()
        assert second_lease["heartbeatAt"] > first_lease["heartbeatAt"]
        assert second_lease["expiresAt"] > second_lease["heartbeatAt"]
        assert second["progress"]["heartbeatAt"] == second_lease["heartbeatAt"]
        persisted = json.loads((runs_root / job_id / "status.json").read_text(encoding="utf-8"))
        assert persisted["workerLease"]["heartbeatAt"] == second_lease["heartbeatAt"]
        assert persisted["monotonicElapsedSeconds"] == persisted["progress"]["elapsedSeconds"]
    finally:
        release.set()


def test_beta6_runtime_marks_alive_owner_running_job_interrupted_when_worker_lease_expired(tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    runs_root = tmp_path / "runs"
    job_dir = runs_root / "job-expired-lease"
    job_dir.mkdir(parents=True)
    expired_at = time.time() - 5
    status_path = job_dir / "status.json"
    status_path.write_text(
        json.dumps(
            {
                "jobId": "job-expired-lease",
                "product": "islam",
                "query": "qibla prayer",
                "language": "en",
                "uiLanguage": "en",
                "detectedLanguage": "en",
                "status": "running",
                "analysisMode": "beta6",
                "selectedCount": 0,
                "error": "",
                "ownerPid": os.getpid(),
                "workerLease": {
                    "ownerPid": os.getpid(),
                    "heartbeatAt": expired_at - 5,
                    "expiresAt": expired_at,
                    "timeoutSeconds": 1,
                    "heartbeatIntervalSeconds": 0.05,
                },
            }
        ),
        encoding="utf-8",
    )
    restored = Beta6JobManager({"islam": _profile(db_path)}, runs_root=runs_root, resume_pending_jobs=False)

    status = restored.get_status("job-expired-lease")

    assert status["status"] == "interrupted"
    assert status["canRetry"] is True
    assert "lease" in status["error"].lower()
    assert json.loads(status_path.read_text(encoding="utf-8"))["status"] == "interrupted"


def test_beta6_runtime_resume_policy_treats_expired_running_lease_as_retryable(tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    runtime = Beta6JobManager({"islam": _profile(db_path)}, runs_root=tmp_path / "runs", resume_pending_jobs=False)
    status = {
        "status": "running",
        "ownerPid": os.getpid(),
        "workerLease": {
            "ownerPid": os.getpid(),
            "heartbeatAt": time.time() - 20,
            "expiresAt": time.time() - 10,
            "timeoutSeconds": 1,
            "heartbeatIntervalSeconds": 0.05,
        },
    }

    assert runtime._should_resume_status(status) is True


def test_beta6_runtime_cancel_running_job_persists_and_worker_cannot_overwrite_completed(monkeypatch, tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    runs_root = tmp_path / "runs"
    runtime = Beta6JobManager({"islam": _profile(db_path)}, runs_root=runs_root, max_workers=1)
    entered = threading.Event()
    release = threading.Event()

    def blocking_then_attempt_completed(context):
        entered.set()
        release.wait(timeout=5)
        completed = runtime._status_payload(context, status="completed", selected_count=1, stage="completed")
        runtime._set_and_persist_status(context, completed)
        return {}

    monkeypatch.setattr(runtime, "_run_context", blocking_then_attempt_completed)
    try:
        created = runtime.create_job(product="islam", query="qibla prayer", language="en", limit=3, session_token=SESSION_TOKEN)
        job_id = created["jobId"]
        assert entered.wait(timeout=1)

        cancelled = runtime.cancel_job(job_id)
        release.set()
        time.sleep(0.2)
        status = runtime.get_status(job_id)
        persisted = json.loads((runs_root / job_id / "status.json").read_text(encoding="utf-8"))

        assert cancelled["status"] == "cancelled"
        assert cancelled["cancelRequested"] is True
        assert status["status"] == "cancelled"
        assert status["progress"]["stage"] == "cancelled"
        assert persisted["status"] == "cancelled"
        assert "accessTokenHash" not in cancelled
        with pytest.raises(RuntimeError):
            runtime.get_result(job_id)
    finally:
        release.set()


def test_beta6_runtime_cancel_queued_job_prevents_later_worker_execution(monkeypatch, tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    runtime = Beta6JobManager(
        {"islam": _profile(db_path)},
        runs_root=tmp_path / "runs",
        max_workers=1,
        max_pending_jobs=2,
    )
    first_entered = threading.Event()
    release_first = threading.Event()
    executed_queries = []

    def blocking_run_context(context):
        executed_queries.append(context.query)
        if context.query == "first job":
            first_entered.set()
            release_first.wait(timeout=5)
        return {}

    monkeypatch.setattr(runtime, "_run_context", blocking_run_context)
    try:
        first = runtime.create_job(product="islam", query="first job", language="en", limit=3, session_token=SESSION_TOKEN)
        assert first_entered.wait(timeout=1)
        second = runtime.create_job(product="islam", query="second job", language="en", limit=3, session_token=SESSION_TOKEN)

        cancelled = runtime.cancel_job(second["jobId"])
        release_first.set()
        time.sleep(0.4)
        status = runtime.get_status(second["jobId"])

        assert cancelled["status"] == "cancelled"
        assert status["status"] == "cancelled"
        assert executed_queries == ["first job"]
    finally:
        release_first.set()


def test_beta6_progress_labels_follow_ui_language_before_question_language():
    status = {
        "status": "running",
        "language": "en",
        "uiLanguage": "ko",
        "createdAt": time.time(),
        "updatedAt": time.time(),
    }

    progress = beta6_module._progress_from_status(status, stage="source_selection")

    assert progress["label"] == "근거 선택"
    assert progress["stage"] == "source_selection"


def test_beta6_runtime_completed_status_has_completed_progress(tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    runs_root = tmp_path / "runs"
    runtime = Beta6JobManager({"islam": _profile(db_path)}, runs_root=runs_root)

    result = runtime.answer_sync(product="islam", query="qibla prayer", language="en", limit=3)
    status = runtime.get_status(result["jobId"])

    assert status["status"] == "completed"
    assert status["progress"]["stage"] == "completed"
    assert status["progress"]["percent"] == 100
    assert status["progress"]["elapsedSeconds"] == status["elapsedSeconds"]


def test_beta6_async_job_trims_process_memory_after_terminal_state(monkeypatch, tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    runtime = Beta6JobManager(
        {"islam": _profile(db_path)},
        runs_root=tmp_path / "runs",
        max_workers=1,
        resume_pending_jobs=False,
    )
    trim_calls = []

    def record_trim():
        trim_calls.append(time.time())

    monkeypatch.setattr(beta6_module, "_trim_process_memory_after_job", record_trim, raising=False)

    created = runtime.create_job(product="islam", query="qibla prayer", language="en", limit=3, session_token=SESSION_TOKEN)
    deadline = time.time() + 5
    status = runtime.get_status(created["jobId"])
    while time.time() < deadline:
        status = runtime.get_status(created["jobId"])
        if status["status"] == "completed" and trim_calls:
            break
        time.sleep(0.05)

    assert status["status"] == "completed"
    assert trim_calls, "async beta6 jobs must release allocator memory after terminal status"


def test_beta6_runtime_completed_result_survives_new_runtime_instance(tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    runs_root = tmp_path / "runs"
    runtime = Beta6JobManager({"islam": _profile(db_path)}, runs_root=runs_root)

    result = runtime.answer_sync(product="islam", query="qibla prayer", language="en", limit=3)
    restored = Beta6JobManager({"islam": _profile(db_path)}, runs_root=runs_root)

    status = restored.get_status(result["jobId"])
    restored_result = restored.get_result(result["jobId"])
    assert status["status"] == "completed"
    assert restored_result["jobId"] == result["jobId"]
    assert restored_result["answerReadiness"] == result["answerReadiness"]
    assert restored_result["sources"][0]["id"] == result["sources"][0]["id"]


def test_beta6_runtime_marks_orphaned_running_job_interrupted_on_restart(tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    runs_root = tmp_path / "runs"
    job_dir = runs_root / "job-orphaned"
    job_dir.mkdir(parents=True)
    status_path = job_dir / "status.json"
    status_path.write_text(
        json.dumps(
            {
                "jobId": "job-orphaned",
                "product": "islam",
                "query": "qibla prayer",
                "language": "en",
                "uiLanguage": "en",
                "detectedLanguage": "en",
                "status": "running",
                "analysisMode": "beta6",
                "selectedCount": 0,
                "error": "",
                "ownerPid": 999999999,
            }
        ),
        encoding="utf-8",
    )
    restored = Beta6JobManager({"islam": _profile(db_path)}, runs_root=runs_root)

    status = restored.get_status("job-orphaned")

    assert status["status"] == "interrupted"
    assert status["canRetry"] is True
    assert "restart" in status["error"]
    assert json.loads(status_path.read_text(encoding="utf-8"))["status"] == "interrupted"
    with pytest.raises(RuntimeError):
        restored.get_result("job-orphaned")


def test_beta6_runtime_rejects_jobs_when_pending_queue_is_full(tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    runtime = Beta6JobManager(
        {"islam": _profile(db_path)},
        runs_root=tmp_path / "runs",
        llm_client=SlowLLMClient(),
        max_workers=1,
        max_pending_jobs=1,
    )

    first = runtime.create_job(product="islam", query="qibla prayer", language="en", limit=3, session_token=SESSION_TOKEN)

    assert first["status"] in {"queued", "running"}
    try:
        runtime.create_job(product="islam", query="zakat", language="en", limit=3, session_token=SESSION_TOKEN)
    except RuntimeError as exc:
        assert "job queue full" in str(exc)
    else:
        raise AssertionError("expected job queue full")


def test_beta6_runtime_capacity_snapshot_tracks_saturated_pending_queue(tmp_path, monkeypatch):
    monkeypatch.setenv("RELIGION_QUEUE_RETRY_AFTER_SECONDS", "17")
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    runtime = Beta6JobManager(
        {"islam": _profile(db_path)},
        runs_root=tmp_path / "runs",
        llm_client=FakeLLMClient(),
        max_workers=1,
        max_pending_jobs=1,
    )
    release = threading.Event()

    def blocking_run_context(context):
        release.wait(timeout=5)
        return {}

    monkeypatch.setattr(runtime, "_run_context", blocking_run_context)

    try:
        assert runtime.capacity_snapshot() == {
            "maxWorkers": 1,
            "maxPendingJobs": 1,
            "pendingJobs": 0,
            "availablePendingSlots": 1,
            "saturated": False,
            "retryAfterSeconds": 17,
        }

        runtime.create_job(product="islam", query="qibla prayer", language="en", limit=3, session_token=SESSION_TOKEN)

        assert runtime.capacity_snapshot() == {
            "maxWorkers": 1,
            "maxPendingJobs": 1,
            "pendingJobs": 1,
            "availablePendingSlots": 0,
            "saturated": True,
            "retryAfterSeconds": 17,
        }
    finally:
        release.set()


def test_beta6_runtime_queued_status_reports_position_and_eta(tmp_path, monkeypatch):
    monkeypatch.setenv("RELIGION_QUEUE_ESTIMATED_JOB_SECONDS", "11")
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    runtime = Beta6JobManager(
        {"islam": _profile(db_path)},
        runs_root=tmp_path / "runs",
        llm_client=FakeLLMClient(),
        max_workers=1,
        max_pending_jobs=3,
    )
    entered = threading.Event()
    release = threading.Event()

    def blocking_run_context(context):
        entered.set()
        release.wait(timeout=5)
        return {}

    monkeypatch.setattr(runtime, "_run_context", blocking_run_context)

    try:
        runtime.create_job(product="islam", query="first", language="en", limit=3, session_token=SESSION_TOKEN)
        assert entered.wait(timeout=1)
        second = runtime.create_job(product="islam", query="second", language="en", limit=3, session_token=SESSION_TOKEN)
        third = runtime.create_job(product="islam", query="third", language="en", limit=3, session_token=SESSION_TOKEN)

        second_status = runtime.get_status(second["jobId"])
        third_status = runtime.get_status(third["jobId"])

        assert second_status["status"] == "queued"
        assert second_status["queue"]["position"] == 1
        assert second_status["queue"]["pendingAhead"] == 0
        assert second_status["queue"]["runningJobs"] == 1
        assert second_status["queue"]["estimatedWaitSeconds"] == 11
        assert second_status["progress"]["detail"] == "Queue 1/2 · ~11s"
        assert third_status["queue"]["position"] == 2
        assert third_status["queue"]["pendingAhead"] == 1
        assert third_status["queue"]["runningJobs"] == 1
        assert third_status["queue"]["estimatedWaitSeconds"] == 22
        assert third_status["progress"]["detail"] == "Queue 2/2 · ~22s"
    finally:
        release.set()


def test_beta6_runtime_persists_durable_queue_rows_for_running_queued_and_cancelled_jobs(tmp_path, monkeypatch):
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    runs_root = tmp_path / "runs"
    runtime = Beta6JobManager(
        {"islam": _profile(db_path)},
        runs_root=runs_root,
        llm_client=FakeLLMClient(),
        max_workers=1,
        max_pending_jobs=2,
    )
    first_entered = threading.Event()
    release_first = threading.Event()

    def blocking_first_job(context):
        if context.query == "first":
            first_entered.set()
            release_first.wait(timeout=5)
        return {}

    monkeypatch.setattr(runtime, "_run_context", blocking_first_job)

    try:
        first = runtime.create_job(product="islam", query="first", language="en", limit=3, session_token=SESSION_TOKEN)
        assert first_entered.wait(timeout=1)
        second = runtime.create_job(product="islam", query="second", language="en", limit=3, session_token=SESSION_TOKEN)

        first_row_path = runs_root / "_beta6_queue" / f"{first['jobId']}.json"
        second_row_path = runs_root / "_beta6_queue" / f"{second['jobId']}.json"
        assert first_row_path.exists()
        assert second_row_path.exists()

        first_row = json.loads(first_row_path.read_text(encoding="utf-8"))
        second_row = json.loads(second_row_path.read_text(encoding="utf-8"))

        assert first_row["queueRowSchemaVersion"] == 1
        assert first_row["jobId"] == first["jobId"]
        assert first_row["status"] == "running"
        assert first_row["product"] == "islam"
        assert first_row["query"] == "first"
        assert second_row["status"] == "queued"
        assert second_row["queue"]["position"] == 1

        cancelled = runtime.cancel_job(second["jobId"])
        cancelled_row = json.loads(second_row_path.read_text(encoding="utf-8"))

        assert cancelled["status"] == "cancelled"
        assert cancelled_row["status"] == "cancelled"
        assert cancelled_row["cancelRequested"] is True
        assert cancelled_row["terminal"] is True
    finally:
        release_first.set()


def test_beta6_durable_queue_claim_allows_only_one_process_for_stale_job(tmp_path):
    if not hasattr(os, "fork"):
        pytest.skip("fork-based durable queue claim smoke requires POSIX")
    runs_root = tmp_path / "runs"
    job_id = "job-durable-claim"
    job_dir = runs_root / job_id
    job_dir.mkdir(parents=True)
    created_at = time.time() - 60
    request = {
        "jobId": job_id,
        "product": "islam",
        "query": "stale queued job",
        "language": "en",
        "uiLanguage": "en",
        "detectedLanguage": "en",
        "limit": 3,
        "createdAt": created_at,
    }
    status = {
        **request,
        "status": "queued",
        "analysisMode": "beta6",
        "ownerPid": 99999999,
        "updatedAt": created_at,
    }
    (job_dir / "request.json").write_text(json.dumps(request), encoding="utf-8")
    (job_dir / "status.json").write_text(json.dumps(status), encoding="utf-8")

    ctx = multiprocessing.get_context("fork")
    queue = ctx.Queue()
    barrier = ctx.Barrier(2)
    processes = [
        ctx.Process(target=_claim_durable_queue_row_from_process, args=(str(runs_root), job_id, queue, barrier))
        for _ in range(2)
    ]

    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=5)
    for process in processes:
        if process.is_alive():
            process.terminate()
            process.join(timeout=2)

    assert all(process.exitcode == 0 for process in processes)
    results = [queue.get(timeout=1) for _ in processes]
    assert all(result["ok"] for result in results), results
    assert sorted(result["claimed"] for result in results) == [False, True]

    persisted = json.loads((job_dir / "status.json").read_text(encoding="utf-8"))
    row = json.loads((runs_root / "_beta6_queue" / f"{job_id}.json").read_text(encoding="utf-8"))
    claimant_pid = [result["pid"] for result in results if result["claimed"]][0]
    assert persisted["queueClaim"]["ownerPid"] == claimant_pid
    assert row["queueClaim"]["ownerPid"] == claimant_pid
    assert row["queueClaim"]["expiresAt"] > time.time()


def test_beta6_runtime_can_resume_durable_queue_rows_on_demand(tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    runs_root = tmp_path / "runs"
    job_id = "job-on-demand-durable-resume"
    job_dir = runs_root / job_id
    job_dir.mkdir(parents=True)
    created_at = time.time() - 60
    request = {
        "jobId": job_id,
        "product": "islam",
        "query": "qibla prayer",
        "language": "en",
        "uiLanguage": "en",
        "detectedLanguage": "en",
        "limit": 3,
        "createdAt": created_at,
    }
    status = {
        **request,
        "status": "queued",
        "analysisMode": "beta6",
        "selectedCount": 0,
        "error": "",
        "ownerPid": 999999999,
        "updatedAt": created_at,
    }
    (job_dir / "request.json").write_text(json.dumps(request), encoding="utf-8")
    (job_dir / "status.json").write_text(json.dumps(status), encoding="utf-8")
    queue_root = runs_root / "_beta6_queue"
    queue_root.mkdir(parents=True)
    (queue_root / f"{job_id}.json").write_text(json.dumps({**status, "terminal": False}), encoding="utf-8")
    runtime = Beta6JobManager({"islam": _profile(db_path)}, runs_root=runs_root, max_workers=1, resume_pending_jobs=False)

    resumed_count = runtime.resume_durable_queue_once(limit=1)

    assert resumed_count == 1
    final_status = {}
    for _ in range(80):
        final_status = runtime.get_status(job_id)
        if final_status["status"] == "completed":
            break
        time.sleep(0.05)
    result = runtime.get_result(job_id)
    row = json.loads((queue_root / f"{job_id}.json").read_text(encoding="utf-8"))
    assert final_status["status"] == "completed"
    assert result["jobId"] == job_id
    assert result["query"] == "qibla prayer"
    assert row["status"] == "completed"
    assert row["terminal"] is True
    assert row["resumeCount"] == 1


def test_beta6_api_can_persist_durable_queue_only_job_for_external_worker(tmp_path, monkeypatch):
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    runs_root = tmp_path / "runs"
    api_runtime = Beta6JobManager(
        {"islam": _profile(db_path)},
        runs_root=runs_root,
        llm_client=FakeLLMClient(),
        local_execution_enabled=False,
        max_pending_jobs=10,
        resume_pending_jobs=False,
    )

    def fail_submit(*_args, **_kwargs):
        raise AssertionError("API durable queue-only mode must not enqueue a local executor future")

    monkeypatch.setattr(api_runtime._executor, "submit", fail_submit)

    created = api_runtime.create_job(
        product="islam",
        query="qibla prayer",
        language="en",
        limit=3,
        session_token=SESSION_TOKEN,
    )

    job_id = created["jobId"]
    row_path = runs_root / "_beta6_queue" / f"{job_id}.json"
    status = api_runtime.get_status(job_id)
    row = json.loads(row_path.read_text(encoding="utf-8"))
    assert status["status"] == "queued"
    assert row["status"] == "queued"
    assert row["executionMode"] == "durable_queue_only"
    assert not (runs_root / job_id / "result.json").exists()

    worker_runtime = Beta6JobManager(
        {"islam": _profile(db_path)},
        runs_root=runs_root,
        llm_client=FakeLLMClient(),
        max_workers=1,
        resume_pending_jobs=False,
    )
    resumed_count = worker_runtime.resume_durable_queue_once(limit=1)

    assert resumed_count == 1
    for _ in range(80):
        worker_status = worker_runtime.get_status(job_id)
        if worker_status["status"] == "completed":
            break
        time.sleep(0.05)
    result = worker_runtime.get_result(job_id)
    final_row = json.loads(row_path.read_text(encoding="utf-8"))
    assert worker_status["status"] == "completed"
    assert result["jobId"] == job_id
    assert final_row["status"] == "completed"
    assert final_row["resumeCount"] == 1


def test_beta6_runtime_resumes_oldest_durable_queue_row_before_newer_run_dir(tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    runs_root = tmp_path / "runs"
    queue_root = runs_root / "_beta6_queue"
    queue_root.mkdir(parents=True)
    older_created_at = time.time() - 120
    newer_created_at = time.time() - 30

    def write_queued_job(job_id, query, created_at):
        job_dir = runs_root / job_id
        job_dir.mkdir(parents=True)
        request = {
            "jobId": job_id,
            "product": "islam",
            "query": query,
            "language": "en",
            "uiLanguage": "en",
            "detectedLanguage": "en",
            "limit": 3,
            "createdAt": created_at,
        }
        status = {
            **request,
            "status": "queued",
            "analysisMode": "beta6",
            "ownerPid": 999999999,
            "updatedAt": created_at,
        }
        (job_dir / "request.json").write_text(json.dumps(request), encoding="utf-8")
        (job_dir / "status.json").write_text(json.dumps(status), encoding="utf-8")
        (queue_root / f"{job_id}.json").write_text(
            json.dumps({**status, "queueRowSchemaVersion": 1, "terminal": False, "queueRowUpdatedAt": created_at}),
            encoding="utf-8",
        )

    write_queued_job("job-old-durable-queue-row", "older qibla prayer", older_created_at)
    time.sleep(0.02)
    write_queued_job("job-new-durable-queue-row", "newer qibla prayer", newer_created_at)
    runtime = Beta6JobManager({"islam": _profile(db_path)}, runs_root=runs_root, max_workers=1, resume_pending_jobs=False)

    resumed_count = runtime.resume_durable_queue_once(limit=1)

    assert resumed_count == 1
    for _ in range(80):
        if (runs_root / "job-old-durable-queue-row" / "result.json").exists() or (
            runs_root / "job-new-durable-queue-row" / "result.json"
        ).exists():
            break
        time.sleep(0.05)
    old_row = json.loads((queue_root / "job-old-durable-queue-row.json").read_text(encoding="utf-8"))
    new_row = json.loads((queue_root / "job-new-durable-queue-row.json").read_text(encoding="utf-8"))
    assert (runs_root / "job-old-durable-queue-row" / "result.json").exists()
    assert not (runs_root / "job-new-durable-queue-row" / "result.json").exists()
    assert old_row["status"] == "completed"
    assert old_row["resumeCount"] == 1
    assert new_row["status"] == "queued"


def test_beta6_runtime_queue_full_error_is_structured_and_rejected_job_leaves_no_artifact(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("RELIGION_QUEUE_RETRY_AFTER_SECONDS", "19")
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    runs_root = tmp_path / "runs"
    runtime = Beta6JobManager(
        {"islam": _profile(db_path)},
        runs_root=runs_root,
        llm_client=FakeLLMClient(),
        max_workers=1,
        max_pending_jobs=1,
    )
    release = threading.Event()

    def blocking_run_context(context):
        release.wait(timeout=5)
        return {}

    monkeypatch.setattr(runtime, "_run_context", blocking_run_context)
    try:
        first = runtime.create_job(product="islam", query="qibla prayer", language="en", limit=3, session_token=SESSION_TOKEN)
        run_dirs_before = sorted(path.name for path in runs_root.iterdir() if path.is_dir())

        with pytest.raises(RuntimeError) as exc_info:
            runtime.create_job(product="islam", query="zakat", language="en", limit=3, session_token=SESSION_TOKEN)

        error = exc_info.value
        assert getattr(error, "code", "") == "beta6_queue_full"
        assert getattr(error, "retry_after_seconds", 0) == 19
        assert getattr(error, "capacity", {}) == {
            "maxWorkers": 1,
            "maxPendingJobs": 1,
            "pendingJobs": 1,
            "availablePendingSlots": 0,
            "saturated": True,
            "retryAfterSeconds": 19,
        }
        assert str(error) == "job queue full"
        assert sorted(path.name for path in runs_root.iterdir() if path.is_dir()) == run_dirs_before
        assert first["jobId"] in run_dirs_before
    finally:
        release.set()


def test_openai_compatible_llm_client_sends_chat_completion_request(monkeypatch):
    requests = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({"choices": [{"message": {"content": "provider answer"}}]}).encode()

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    client = OpenAICompatibleLLMClient(api_url="https://llm.example/v1/chat/completions", api_key="secret")

    answer = client.complete([{"role": "user", "content": "hello"}], model="test-model")

    assert answer == "provider answer"
    request, timeout = requests[0]
    assert request.full_url == "https://llm.example/v1/chat/completions"
    assert request.headers["Authorization"] == "Bearer secret"
    assert timeout == 180
    payload = json.loads(request.data.decode())
    assert payload["model"] == "test-model"
    assert payload["messages"][0]["content"] == "hello"


def test_lawkey_gemma_gateway_llm_client_sends_gateway_chat_request(monkeypatch):
    requests = []
    monkeypatch.delenv("RELIGION_GEMMA_GATEWAY_MAX_OUTPUT_TOKENS", raising=False)

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({"answer": "gateway answer"}).encode()

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    client = LawkeyGemmaGatewayLLMClient(api_url="https://lawkey.example/chat", token="secret")

    answer = client.complete(
        [
            {"role": "system", "content": "follow the format"},
            {"role": "user", "content": "hello"},
        ]
    )

    assert answer == "gateway answer"
    request, timeout = requests[0]
    assert request.full_url == "https://lawkey.example/chat"
    assert request.headers["Authorization"] == "Bearer secret"
    assert request.headers["User-agent"] == "BunjumGemmaGatewayClient/1.0"
    assert timeout == 300
    payload = json.loads(request.data.decode())
    assert payload["temperature"] == 0.4
    assert "maxOutputTokens" not in payload
    assert payload["messages"][0]["role"] == "user"
    assert payload["messages"][0]["text"].startswith("System instruction:")
    assert payload["messages"][1] == {"role": "user", "text": "hello"}


def test_mint_gemini_gateway_llm_client_sends_generate_content_request(monkeypatch):
    requests = []
    monkeypatch.setenv("RELIGION_GEMINI_TEMPERATURE", "0")

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def getcode(self):
            return 200

        def read(self):
            return json.dumps(
                {
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {"text": "gateway answer"},
                                ]
                            }
                        }
                    ]
                }
            ).encode()

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    client = MintGeminiGatewayLLMClient(
        base_url="http://mint.example",
        token="secret",
        default_model="gemma-test",
        key_numbers=[1],
        thinking_level="minimal",
    )

    answer = client.complete(
        [
            {"role": "system", "content": "follow the format"},
            {"role": "user", "content": "hello"},
        ]
    )

    assert answer == "gateway answer"
    request, timeout = requests[0]
    assert request.full_url == "http://mint.example/v1beta/models/gemma-test:generateContent?keyNumber=1"
    assert request.headers["X-goog-api-key"] == "secret"
    assert timeout == 300
    payload = json.loads(request.data.decode())
    assert payload["systemInstruction"]["parts"][0]["text"] == "follow the format"
    assert payload["contents"] == [{"role": "user", "parts": [{"text": "hello"}]}]
    assert payload["generationConfig"]["temperature"] == 0
    assert payload["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "minimal"}


def test_mint_gemini_gateway_llm_client_retries_next_key_number(monkeypatch):
    requests = []
    monkeypatch.setattr(time, "sleep", lambda _: None)

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def getcode(self):
            return 200

        def read(self):
            return json.dumps({"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}).encode()

    def fake_urlopen(request, timeout):
        requests.append(request.full_url)
        if len(requests) == 1:
            raise urllib.error.HTTPError(
                request.full_url,
                429,
                "Too Many Requests",
                {},
                io.BytesIO(b'{"error":{"message":"quota"}}'),
            )
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    client = MintGeminiGatewayLLMClient(
        base_url="http://mint.example",
        token="secret",
        default_model="gemma-test",
        key_numbers=[1, 2],
    )

    assert client.complete([{"role": "user", "content": "hello"}]) == "ok"
    assert requests[0].endswith("?keyNumber=1")
    assert requests[1].endswith("?keyNumber=2")
    trace = client.consume_last_call_trace()
    assert trace["provider"] == "mint_gemini_gateway_generate_content"
    assert trace["keyNumbersTried"] == [1, 2]
    assert trace["selectedKeyNumber"] == 2


def test_mint_gemini_gateway_llm_client_retries_transport_reset(monkeypatch):
    requests = []
    monkeypatch.setattr(time, "sleep", lambda _: None)

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def getcode(self):
            return 200

        def read(self):
            return json.dumps({"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}).encode()

    def fake_urlopen(request, timeout):
        requests.append(request.full_url)
        if len(requests) == 1:
            raise ConnectionResetError("connection reset by peer")
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    client = MintGeminiGatewayLLMClient(
        base_url="http://mint.example",
        token="secret",
        default_model="gemma-test",
        key_numbers=[1, 2],
    )

    assert client.complete([{"role": "user", "content": "hello"}]) == "ok"
    assert requests[0].endswith("?keyNumber=1")
    assert requests[1].endswith("?keyNumber=2")
    trace = client.consume_last_call_trace()
    assert trace["keyNumbersTried"] == [1, 2]
    assert trace["selectedKeyNumber"] == 2
