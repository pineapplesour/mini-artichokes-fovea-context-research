import importlib.util
import json
from pathlib import Path

import pytest


def load_app_path_verifier():
    path = Path("tools/verify_app_path_gemma4.py")
    if not path.exists():
        pytest.fail("tools/verify_app_path_gemma4.py is missing")
    spec = importlib.util.spec_from_file_location("verify_app_path_gemma4", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class FakeTransport:
    def __init__(self, *, result, statuses=None):
        self.result = result
        self.posts = []
        self.gets = []
        self.cancel_posts = []
        self.statuses = statuses or [
            {"status": "queued", "progress": {"stage": "queued"}},
            {"status": "running", "progress": {"stage": "writer"}},
            {"status": "completed", "progress": {"stage": "completed"}},
        ]

    def post_json(self, url, payload, *, headers=None, timeout_seconds=30):
        if url.endswith("/cancel?token=token-test-1"):
            self.cancel_posts.append((url, payload, headers or {}))
            return 200, {"status": "cancelled", "jobId": "job-test-1"}
        self.posts.append((url, payload, headers or {}))
        return 200, {"jobId": "job-test-1", "accessToken": "token-test-1"}

    def get_json(self, url, *, headers=None, timeout_seconds=30):
        self.gets.append((url, headers or {}))
        if url.endswith("/result?token=token-test-1"):
            return 200, self.result
        index = min(len(self.gets) - 1, len(self.statuses) - 1)
        return 200, self.statuses[index]


def _good_result():
    return {
        "jobId": "job-test-1",
        "product": "islam",
        "languageResolution": {"answerLanguage": "ko"},
        "answerReadiness": "final_answer",
        "answer": "근거 기반 답변입니다. [C1] " + "설명 " * 80,
        "writer": {
            "status": "completed",
            "provider": "lawkey_gemini_generate_content",
            "model": "gemma-4-26b-a4b-it",
        },
        "selector": {
            "status": "completed",
            "provider": "lawkey_gemini_generate_content",
            "model": "gemma-4-26b-a4b-it",
            "keywords": ["기도", "صلاة"],
            "reasoning": "very long selector reasoning should not be copied into the verifier report",
        },
        "sources": [{"id": f"S{index}", "citation": f"Source {index}"} for index in range(1, 6)],
        "claimCards": [{"claimId": "C1", "citation": "Source 1"}],
        "candidateClaimCards": [{"claimId": "C1", "citation": "Source 1"}],
        "citedClaimCards": [{"claimId": "C1", "citation": "Source 1"}],
        "citationMap": {"C1": {"sourceId": "S1"}},
        "beta6": {
            "selectorProvider": "lawkey_gemini_generate_content",
            "selectorModel": "gemma-4-26b-a4b-it",
            "writerProvider": "lawkey_gemini_generate_content",
            "writerStatus": "completed",
            "stageTimingTotals": {
                "candidate_search": 1.5,
                "source_selection": 2.25,
                "claim_cards": 3.75,
                "answer_plan": 4.0,
                "writer": 5.5,
            },
            "stageTimingTotalSec": 17.0,
            "keywordGenerationCacheHits": 2,
            "keywordGenerationCacheMisses": 0,
            "keywordGenerationTrace": [
                {
                    "round": 1,
                    "phase": "initial",
                    "keywordCount": 10,
                    "newKeywordCount": 10,
                    "candidateCountBefore": 0,
                    "candidateCountAfter": 700,
                    "elapsedSec": 9.5,
                    "cacheHit": False,
                },
                {
                    "round": 2,
                    "phase": "additional",
                    "keywordCount": 10,
                    "newKeywordCount": 3,
                    "candidateCountBefore": 700,
                    "candidateCountAfter": 1200,
                    "elapsedSec": 3.0,
                    "cacheHit": True,
                },
            ],
            "candidateSearchCacheHits": 8,
            "candidateSearchCacheMisses": 1,
            "selectorBatchCacheHits": 3,
            "selectorBatchCacheMisses": 4,
            "candidateSearchTrace": [
                {"label": "question", "query": "기도", "limit": 700, "resultCount": 700, "elapsedSec": 1.25, "cacheHit": False},
                {"label": "keyword_01", "query": "صلاة", "limit": 700, "resultCount": 300, "elapsedSec": 0.5, "cacheHit": True},
            ],
            "selectorBatchTrace": [
                {
                    "batch": 1,
                    "candidateCount": 100,
                    "status": "completed",
                    "elapsedSec": 8.75,
                    "timeoutSeconds": 5.0,
                    "elapsedExceededTimeout": True,
                    "llmCallCount": 2,
                    "llmHttpStartedCount": 1,
                    "maxPreHttpWaitSec": 3.25,
                    "maxLlmElapsedSec": 4.5,
                    "primaryLlmCallCount": 1,
                    "primaryMaxPreHttpWaitSec": 3.25,
                    "primaryMaxLlmElapsedSec": 4.5,
                    "primaryMaxCandidateCount": 100,
                    "recoveryLlmCallCount": 1,
                    "recoveryMaxPreHttpWaitSec": 1.25,
                    "recoveryMaxLlmElapsedSec": 2.5,
                    "recoveryMaxCandidateCount": 25,
                    "cacheHit": False,
                    "selectedCount": 12,
                    "recovered": True,
                    "localRecovery": True,
                    "recoverySubBatchCount": 4,
                    "recoveryBatchSize": 25,
                    "recoveryError": "Gemini logical timeout exhausted for selector",
                    "recoveryErrors": ["HTTP 429", "read timeout"],
                },
                {"batch": 2, "candidateCount": 100, "status": "empty_selection", "elapsedSec": 2.25, "cacheHit": True, "selectedCount": 0},
            ],
            "claimAnalyzer": {
                "claimAnalyzerChunkCacheHits": 5,
                "claimAnalyzerChunkCacheMisses": 6,
                "claimAnalyzerBatchCacheHits": 7,
                "claimAnalyzerBatchCacheMisses": 8,
            },
            "writerCacheHit": True,
            "answerPlanner": {"cacheHit": True},
        },
    }


def test_app_path_gemma4_verifier_follows_job_to_result_and_checks_metadata():
    verifier = load_app_path_verifier()
    transport = FakeTransport(result=_good_result())

    report = verifier.build_report(
        base_url="http://app.test",
        product="islam",
        query="하루 기도 횟수를 근거로 짧게 설명해줘",
        language="ko",
        poll_interval_seconds=0,
        timeout_seconds=10,
        transport=transport,
        min_answer_chars=120,
        min_sources=5,
        min_cited_claims=1,
    )

    assert report["passes"] is True
    assert report["jobId"] == "job-test-1"
    assert report["checks"]["writerGemma4"]["passes"] is True
    assert report["checks"]["selectorGemma4"]["passes"] is True
    assert report["checks"]["sourceGrounding"]["passes"] is True
    assert report["selector"] == {
        "status": "completed",
        "provider": "lawkey_gemini_generate_content",
        "model": "gemma-4-26b-a4b-it",
    }
    assert report["statusPollCount"] == 3
    assert report["stageTimings"]["totals"]["writer"] == 5.5
    assert report["stageTimings"]["totalSec"] == 17.0
    assert report["cacheMetrics"]["writerCacheHit"] is True
    assert report["cacheMetrics"]["answerPlanCacheHit"] is True
    assert report["cacheMetrics"]["candidateSearch"]["hits"] == 8
    assert report["cacheMetrics"]["claimAnalyzerBatches"]["hits"] == 7
    assert report["cacheMetrics"]["claimAnalyzerChunks"]["misses"] == 6
    assert report["selectionTrace"]["candidateSearch"]["count"] == 2
    assert report["selectionTrace"]["keywordGeneration"]["count"] == 2
    assert report["selectionTrace"]["keywordGeneration"]["slowest"][0]["round"] == 1
    assert report["selectionTrace"]["candidateSearch"]["slowest"][0]["query"] == "기도"
    assert report["selectionTrace"]["selectorBatches"]["count"] == 2
    assert report["selectionTrace"]["selectorBatches"]["slowest"][0]["batch"] == 1
    assert report["selectionTrace"]["selectorBatches"]["slowest"][0]["recoverySubBatchCount"] == 4
    assert report["selectionTrace"]["selectorBatches"]["slowest"][0]["recoveryBatchSize"] == 25
    assert "timeout" in report["selectionTrace"]["selectorBatches"]["slowest"][0]["recoveryError"]
    assert report["selectionTrace"]["selectorBatches"]["slowest"][0]["recoveryErrorCount"] == 2
    assert report["selectionTrace"]["selectorBatches"]["slowest"][0]["timeoutSeconds"] == 5.0
    assert report["selectionTrace"]["selectorBatches"]["slowest"][0]["elapsedExceededTimeout"] is True
    assert report["selectionTrace"]["selectorBatches"]["slowest"][0]["llmCallCount"] == 2
    assert report["selectionTrace"]["selectorBatches"]["slowest"][0]["llmHttpStartedCount"] == 1
    assert report["selectionTrace"]["selectorBatches"]["slowest"][0]["maxPreHttpWaitSec"] == 3.25
    assert report["selectionTrace"]["selectorBatches"]["slowest"][0]["maxLlmElapsedSec"] == 4.5
    assert report["selectionTrace"]["selectorBatches"]["slowest"][0]["primaryLlmCallCount"] == 1
    assert report["selectionTrace"]["selectorBatches"]["slowest"][0]["primaryMaxLlmElapsedSec"] == 4.5
    assert report["selectionTrace"]["selectorBatches"]["slowest"][0]["primaryMaxCandidateCount"] == 100
    assert report["selectionTrace"]["selectorBatches"]["slowest"][0]["recoveryLlmCallCount"] == 1
    assert report["selectionTrace"]["selectorBatches"]["slowest"][0]["recoveryMaxLlmElapsedSec"] == 2.5
    assert report["selectionTrace"]["selectorBatches"]["slowest"][0]["recoveryMaxCandidateCount"] == 25
    assert transport.posts[0][0] == "http://app.test/api/islam/jobs"
    assert transport.posts[0][1]["language"] == "ko"


def test_app_path_gemma4_verifier_fails_wrong_writer_model():
    verifier = load_app_path_verifier()
    result = _good_result()
    result["writer"]["model"] = "gemini-3.1-flash-lite-preview"
    transport = FakeTransport(result=result)

    report = verifier.build_report(
        base_url="http://app.test",
        product="islam",
        query="하루 기도 횟수를 근거로 짧게 설명해줘",
        language="ko",
        poll_interval_seconds=0,
        timeout_seconds=10,
        transport=transport,
    )

    assert report["passes"] is False
    assert report["checks"]["writerGemma4"]["passes"] is False
    assert report["checks"]["writerGemma4"]["model"] == "gemini-3.1-flash-lite-preview"


def test_app_path_gemma4_verifier_fails_forced_coverage_supplement_in_answer():
    verifier = load_app_path_verifier()
    result = _good_result()
    result["answer"] += "\n\n### 누락 근거 보강\n무관한 보강 근거입니다. [C1]"
    result["beta6"]["coverageReport"] = {
        "patched": True,
        "patchPolicy": "forced_deterministic_supplement",
    }
    transport = FakeTransport(result=result)

    report = verifier.build_report(
        base_url="http://app.test",
        product="islam",
        query="사회주의는 하람임?",
        language="ko",
        poll_interval_seconds=0,
        timeout_seconds=10,
        transport=transport,
    )

    assert report["passes"] is False
    assert report["checks"]["noForcedCoveragePatch"]["passes"] is False
    assert report["checks"]["noForcedCoveragePatch"]["hasForcedSupplement"] is True
    assert report["checks"]["noForcedCoveragePatch"]["coveragePatched"] is True


def test_app_path_gemma4_verifier_cancels_job_when_timeout_occurs():
    verifier = load_app_path_verifier()
    transport = FakeTransport(
        result=_good_result(),
        statuses=[{"status": "running", "progress": {"stage": "source_selection"}}],
    )

    report = verifier.build_report(
        base_url="http://app.test",
        product="islam",
        query="느린 질문",
        language="ko",
        poll_interval_seconds=0,
        timeout_seconds=0,
        transport=transport,
    )

    assert report["passes"] is False
    assert report["finalStatus"] == "timeout"
    assert report["timeoutCancel"]["attempted"] is True
    assert report["timeoutCancel"]["statusCode"] == 200
    assert report["timeoutCancel"]["cancelled"] is True
    assert transport.cancel_posts
    assert transport.cancel_posts[0][0] == "http://app.test/api/jobs/job-test-1/cancel?token=token-test-1"


def test_app_path_gemma4_verifier_salvages_partial_stage_timings_from_run_dir_on_timeout(tmp_path):
    verifier = load_app_path_verifier()
    run_dir = tmp_path / "job-test-1"
    run_dir.mkdir()
    (run_dir / "selector_meta.json").write_text(
        json.dumps(
            {
                "status": "completed",
                "provider": "lawkey_gemini_generate_content",
                "model": "gemma-4-26b-a4b-it",
                "selectionSource": "gemma4_llm_batched_selector",
                "candidateCount": 400,
                "selectedIds": ["S1", "S2"],
                "keywordGenerationTrace": [
                    {"round": 1, "elapsedSec": 3.5, "cacheHit": False},
                    {"round": 2, "elapsedSec": 4.25, "cacheHit": False},
                ],
                "candidateSearchTrace": [
                    {"label": "question", "query": "불면", "limit": 120, "resultCount": 50, "elapsedSec": 1.5, "cacheHit": False},
                    {"label": "keyword_01", "query": "insomnia", "limit": 120, "resultCount": 53, "elapsedSec": 0.25, "cacheHit": True},
                ],
                "selectorBatchTrace": [
                    {"batch": 1, "candidateCount": 25, "status": "completed", "selectedCount": 2, "elapsedSec": 12.5, "cacheHit": False},
                    {"batch": 2, "candidateCount": 25, "status": "completed", "selectedCount": 0, "elapsedSec": 6.0, "cacheHit": False},
                ],
                "selectorBatchCacheHits": 0,
                "selectorBatchCacheMisses": 2,
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "claim_analyzer_meta.json").write_text(
        json.dumps(
            {
                "status": "completed",
                "claimAnalyzerPostMergeClaimCount": 9,
                "claimAnalyzerChunkCacheHits": 1,
                "claimAnalyzerChunkCacheMisses": 2,
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "answer_plan.json").write_text(json.dumps({"status": "completed", "cacheHit": False}), encoding="utf-8")
    transport = FakeTransport(
        result=_good_result(),
        statuses=[{"status": "running", "progress": {"stage": "writer"}}],
    )

    report = verifier.build_report(
        base_url="http://app.test",
        product="simli",
        query="느린 질문",
        language="ko",
        poll_interval_seconds=0,
        timeout_seconds=0,
        transport=transport,
        runs_root=tmp_path,
        max_source_selection_sec=10,
    )

    assert report["passes"] is False
    assert report["finalStatus"] == "timeout"
    assert report["partialRun"]["used"] is True
    assert report["partialRun"]["files"]["selectorMeta"] is True
    assert report["stageTimings"]["totals"]["keyword_generation"] == 7.75
    assert report["stageTimings"]["totals"]["candidate_search"] == 1.75
    assert report["stageTimings"]["totals"]["source_selection"] == 12.5
    assert report["checks"]["sourceSelectionLatency"]["measured"] is True
    assert report["checks"]["sourceSelectionLatency"]["passes"] is False
    assert report["selectionTrace"]["selectorBatches"]["count"] == 2
    assert report["cacheMetrics"]["selectorBatches"]["misses"] == 2
    assert report["cacheMetrics"]["claimAnalyzerChunks"]["misses"] == 2
    assert report["beta6"]["selectedCount"] == 2


def test_app_path_gemma4_verifier_can_enforce_absolute_latency_budgets():
    verifier = load_app_path_verifier()
    transport = FakeTransport(result=_good_result())

    report = verifier.build_report(
        base_url="http://app.test",
        product="islam",
        query="하루 기도 횟수를 근거로 짧게 설명해줘",
        language="ko",
        poll_interval_seconds=0,
        timeout_seconds=10,
        transport=transport,
        min_answer_chars=120,
        min_sources=5,
        min_cited_claims=1,
        max_total_sec=10,
        max_source_selection_sec=1,
    )

    assert report["passes"] is False
    assert report["checks"]["totalLatency"]["passes"] is False
    assert report["checks"]["totalLatency"]["totalSec"] == 17.0
    assert report["checks"]["totalLatency"]["expected"] == "<=10"
    assert report["checks"]["sourceSelectionLatency"]["passes"] is False
    assert report["checks"]["sourceSelectionLatency"]["sourceSelectionSec"] == 2.25
    assert report["checks"]["sourceSelectionLatency"]["expected"] == "<=1"


def test_app_path_gemma4_verifier_can_require_cold_engine_cache_for_latency_proof():
    verifier = load_app_path_verifier()
    transport = FakeTransport(result=_good_result())

    report = verifier.build_report(
        base_url="http://app.test",
        product="islam",
        query="사회주의는 하람임?",
        language="ko",
        poll_interval_seconds=0,
        timeout_seconds=10,
        transport=transport,
        min_answer_chars=120,
        min_sources=5,
        min_cited_claims=1,
        max_source_selection_sec=30,
        require_cold_engine_cache=True,
    )

    assert report["passes"] is False
    assert report["checks"]["coldEngineCache"]["passes"] is False
    assert report["checks"]["coldEngineCache"]["required"] is True
    assert "selectorBatches" in report["checks"]["coldEngineCache"]["hotStages"]
    assert "answerPlan" in report["checks"]["coldEngineCache"]["hotStages"]
    assert report["checks"]["sourceSelectionLatency"]["passes"] is True


def test_app_path_gemma4_verifier_fails_missing_source_selection_timing_when_budget_required():
    verifier = load_app_path_verifier()
    result = _good_result()
    result["beta6"].pop("stageTimingTotals")
    result["beta6"].pop("stageTimingTotalSec")
    transport = FakeTransport(result=result)

    report = verifier.build_report(
        base_url="http://app.test",
        product="islam",
        query="하루 기도 횟수를 근거로 짧게 설명해줘",
        language="ko",
        poll_interval_seconds=0,
        timeout_seconds=10,
        transport=transport,
        min_answer_chars=120,
        min_sources=5,
        min_cited_claims=1,
        max_source_selection_sec=30,
    )

    assert report["passes"] is False
    assert report["checks"]["sourceSelectionLatency"]["passes"] is False
    assert report["checks"]["sourceSelectionLatency"]["measured"] is False
    assert report["checks"]["sourceSelectionLatency"]["sourceSelectionSec"] == 0.0


def test_app_path_gemma4_verifier_reports_wall_elapsed_and_gates_user_visible_latency():
    verifier = load_app_path_verifier()
    transport = FakeTransport(result=_good_result())
    ticks = iter([100.0, 105.0, 120.0, 125.0])

    report = verifier.build_report(
        base_url="http://app.test",
        product="islam",
        query="하루 기도 횟수를 근거로 짧게 설명해줘",
        language="ko",
        poll_interval_seconds=0,
        timeout_seconds=100,
        transport=transport,
        min_answer_chars=120,
        min_sources=5,
        min_cited_claims=1,
        max_total_sec=20,
        monotonic=lambda: next(ticks),
    )

    assert report["wallElapsedSec"] == 25.0
    assert report["checks"]["totalLatency"]["passes"] is False
    assert report["checks"]["totalLatency"]["engineTotalSec"] == 17.0
    assert report["checks"]["totalLatency"]["wallElapsedSec"] == 25.0
    assert report["checks"]["totalLatency"]["checkedSec"] == 25.0
