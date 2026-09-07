#!/usr/bin/env python3
"""Verify a real beta6 app API job uses Lawkey/Gemma4 end to end."""

from __future__ import annotations

import argparse
import json
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Protocol


EXPECTED_PROVIDER = "lawkey_gemini_generate_content"
EXPECTED_MODEL = "gemma-4-26b-a4b-it"


class Transport(Protocol):
    def post_json(
        self,
        url: str,
        payload: dict[str, Any],
        *,
        headers: dict[str, str] | None = None,
        timeout_seconds: float = 30,
    ) -> tuple[int, dict[str, Any]]:
        ...

    def get_json(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        timeout_seconds: float = 30,
    ) -> tuple[int, dict[str, Any]]:
        ...


class UrllibTransport:
    def post_json(
        self,
        url: str,
        payload: dict[str, Any],
        *,
        headers: dict[str, str] | None = None,
        timeout_seconds: float = 30,
    ) -> tuple[int, dict[str, Any]]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json", **(headers or {})},
            method="POST",
        )
        return _open_json(request, timeout_seconds=timeout_seconds)

    def get_json(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        timeout_seconds: float = 30,
    ) -> tuple[int, dict[str, Any]]:
        request = urllib.request.Request(url, headers=headers or {}, method="GET")
        return _open_json(request, timeout_seconds=timeout_seconds)


def build_report(
    *,
    base_url: str,
    product: str = "islam",
    query: str = "하루 기도 횟수를 근거로 짧게 설명해줘",
    language: str = "ko",
    limit: int = 8,
    timeout_seconds: float = 900,
    poll_interval_seconds: float = 2,
    transport: Transport | None = None,
    min_answer_chars: int = 800,
    min_sources: int = 20,
    min_cited_claims: int = 1,
    max_total_sec: float = 0,
    max_source_selection_sec: float = 0,
    require_cold_engine_cache: bool = False,
    runs_root: str | Path = "runs",
    monotonic=time.monotonic,
) -> dict[str, Any]:
    transport = transport or UrllibTransport()
    clean_base = base_url.rstrip("/")
    clean_product = product.strip().lower()
    session_token = "verify-app-path-" + secrets.token_hex(16)
    headers = {"X-Beta6-Session-Token": session_token}
    started = monotonic()
    create_url = f"{clean_base}/api/{urllib.parse.quote(clean_product)}/jobs"
    status_tail: list[dict[str, Any]] = []
    create_status, create_body = transport.post_json(
        create_url,
        {"query": query, "language": language, "limit": limit},
        headers=headers,
        timeout_seconds=30,
    )
    job_id = str(create_body.get("jobId") or "")
    access_token = str(create_body.get("accessToken") or "")
    if create_status != 200 or not job_id or not access_token:
        return _failure_report(
            base_url=clean_base,
            product=clean_product,
            query=query,
            job_id=job_id,
            create_status=create_status,
            error="job creation failed",
            create_body=create_body,
            status_tail=status_tail,
        )
    terminal_status: dict[str, Any] = {}
    timeout_cancel: dict[str, Any] = {"attempted": False, "statusCode": 0, "cancelled": False, "error": ""}
    poll_count = 0
    while True:
        poll_count += 1
        status_url = f"{clean_base}/api/jobs/{urllib.parse.quote(job_id)}?token={urllib.parse.quote(access_token)}"
        status_code, status_body = transport.get_json(status_url, headers=headers, timeout_seconds=30)
        status_tail.append(_compact_status(status_body, status_code=status_code))
        status_tail = status_tail[-12:]
        state = str(status_body.get("status") or "")
        if status_code != 200:
            terminal_status = status_body
            break
        if state in {"completed", "failed", "interrupted", "cancelled"}:
            terminal_status = status_body
            break
        if monotonic() - started >= timeout_seconds:
            terminal_status = {"status": "timeout", "error": "timed out waiting for app-path job"}
            timeout_cancel = _cancel_timed_out_job(
                transport=transport,
                clean_base=clean_base,
                job_id=job_id,
                access_token=access_token,
                headers=headers,
            )
            break
        if poll_interval_seconds > 0:
            time.sleep(poll_interval_seconds)
    result: dict[str, Any] = {}
    if terminal_status.get("status") == "completed":
        result_url = f"{clean_base}/api/jobs/{urllib.parse.quote(job_id)}/result?token={urllib.parse.quote(access_token)}"
        result_status, result = transport.get_json(result_url, headers=headers, timeout_seconds=60)
        if result_status != 200:
            result = {"error": "result fetch failed", "statusCode": result_status, "body": result}
    wall_elapsed_sec = round(max(0.0, monotonic() - started), 6)
    partial_run = _load_partial_run(job_id, Path(runs_root), result=result)
    observability_result = result
    if partial_run["used"]:
        observability_result = {"beta6": partial_run["beta6"], "selector": partial_run["selector"]}
    checks = _checks(
        terminal_status=terminal_status,
        result=result,
        timing_beta6=observability_result.get("beta6") if isinstance(observability_result.get("beta6"), dict) else None,
        language=language,
        min_answer_chars=min_answer_chars,
        min_sources=min_sources,
        min_cited_claims=min_cited_claims,
        max_total_sec=max_total_sec,
        max_source_selection_sec=max_source_selection_sec,
        require_cold_engine_cache=require_cold_engine_cache,
        wall_elapsed_sec=wall_elapsed_sec,
    )
    passes = all(check["passes"] for check in checks.values())
    return {
        "passes": passes,
        "baseUrl": clean_base,
        "product": clean_product,
        "query": query,
        "language": language,
        "jobId": job_id,
        "createStatus": create_status,
        "finalStatus": terminal_status.get("status", ""),
        "wallElapsedSec": wall_elapsed_sec,
        "statusPollCount": poll_count,
        "statusTail": status_tail,
        "timeoutCancel": timeout_cancel,
        "partialRun": partial_run["report"],
        "metrics": _metrics(result),
        "stageTimings": _compact_stage_timings(observability_result.get("beta6")),
        "cacheMetrics": _compact_cache_metrics(observability_result.get("beta6")),
        "selectionTrace": _compact_selection_trace(observability_result),
        "checks": checks,
        "writer": _compact_llm_stage(result.get("writer")),
        "selector": _compact_llm_stage(result.get("selector") or observability_result.get("selector")),
        "beta6": {
            "selectorProvider": (observability_result.get("beta6") or {}).get("selectorProvider", ""),
            "selectorModel": (observability_result.get("beta6") or {}).get("selectorModel", ""),
            "writerProvider": (result.get("beta6") or {}).get("writerProvider", ""),
            "writerStatus": (result.get("beta6") or {}).get("writerStatus", ""),
            "selectionSource": (observability_result.get("beta6") or {}).get("selectionSource", ""),
            "candidateCount": (observability_result.get("beta6") or {}).get("candidateCount", 0),
            "selectedCount": (observability_result.get("beta6") or {}).get("selectedCount", 0),
            "claimCardCount": (observability_result.get("beta6") or {}).get("claimCardCount", 0),
            "citedClaimCount": (result.get("beta6") or {}).get("citedClaimCount", 0),
            "coverageReport": _compact_coverage_report((result.get("beta6") or {}).get("coverageReport")),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8061", help="Split app base URL.")
    parser.add_argument("--product", default="islam", help="Product key.")
    parser.add_argument("--query", default="하루 기도 횟수를 근거로 짧게 설명해줘", help="Question to submit.")
    parser.add_argument("--language", default="ko", help="Requested answer language.")
    parser.add_argument("--limit", type=int, default=8, help="Frontend request limit.")
    parser.add_argument("--timeout", type=float, default=900, help="Max wait seconds.")
    parser.add_argument("--poll-interval", type=float, default=2, help="Polling interval seconds.")
    parser.add_argument("--min-answer-chars", type=int, default=800)
    parser.add_argument("--min-sources", type=int, default=20)
    parser.add_argument("--min-cited-claims", type=int, default=1)
    parser.add_argument("--max-total-sec", type=float, default=0, help="Optional absolute total latency budget. 0 disables.")
    parser.add_argument(
        "--max-source-selection-sec",
        type=float,
        default=0,
        help="Optional absolute source-selection latency budget. 0 disables.",
    )
    parser.add_argument(
        "--require-cold-engine-cache",
        "--require-cold-engine",
        action="store_true",
        help="Fail unless engine cache telemetry proves keyword/search/selector/claim/plan/writer stages were cold.",
    )
    parser.add_argument("--runs-root", default="runs", help="Local runs root used to recover partial timing metadata after timeout/cancel.")
    parser.add_argument("--json", action="store_true", help="Print JSON report.")
    parser.add_argument("--output", default="", help="Write JSON report to this path.")
    args = parser.parse_args(argv)
    report = build_report(
        base_url=args.base_url,
        product=args.product,
        query=args.query,
        language=args.language,
        limit=args.limit,
        timeout_seconds=args.timeout,
        poll_interval_seconds=args.poll_interval,
        min_answer_chars=args.min_answer_chars,
        min_sources=args.min_sources,
        min_cited_claims=args.min_cited_claims,
        max_total_sec=args.max_total_sec,
        max_source_selection_sec=args.max_source_selection_sec,
        require_cold_engine_cache=args.require_cold_engine_cache,
        runs_root=args.runs_root,
    )
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("PASS app-path Gemma4" if report["passes"] else "FAIL app-path Gemma4")
    return 0 if report["passes"] else 1


def _load_partial_run(job_id: str, runs_root: Path, *, result: dict[str, Any]) -> dict[str, Any]:
    empty = {
        "used": False,
        "beta6": {},
        "selector": {},
        "report": {
            "used": False,
            "path": "",
            "files": {"selectorMeta": False, "claimAnalyzerMeta": False, "answerPlan": False},
        },
    }
    if not job_id or isinstance(result.get("beta6"), dict):
        return empty
    run_dir = runs_root / job_id
    selector_meta = _read_json_file(run_dir / "selector_meta.json")
    claim_meta = _read_json_file(run_dir / "claim_analyzer_meta.json")
    answer_plan = _read_json_file(run_dir / "answer_plan.json")
    if not selector_meta and not claim_meta and not answer_plan:
        return empty
    beta6 = _partial_beta6_from_meta(selector_meta, claim_meta, answer_plan)
    selector = {
        "status": selector_meta.get("status", ""),
        "provider": selector_meta.get("provider", ""),
        "model": selector_meta.get("model", ""),
    }
    return {
        "used": True,
        "beta6": beta6,
        "selector": selector,
        "report": {
            "used": True,
            "path": str(run_dir),
            "files": {
                "selectorMeta": bool(selector_meta),
                "claimAnalyzerMeta": bool(claim_meta),
                "answerPlan": bool(answer_plan),
            },
        },
    }


def _read_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _partial_beta6_from_meta(selector_meta: dict[str, Any], claim_meta: dict[str, Any], answer_plan: dict[str, Any]) -> dict[str, Any]:
    selected_ids = selector_meta.get("selectedIds") if isinstance(selector_meta.get("selectedIds"), list) else []
    keyword_trace = _trace_items(selector_meta.get("keywordGenerationTrace"))
    candidate_trace = _trace_items(selector_meta.get("candidateSearchTrace"))
    batch_trace = _trace_items(selector_meta.get("selectorBatchTrace") or selector_meta.get("selectorBatches"))
    stage_totals: dict[str, float] = {}
    if keyword_trace:
        stage_totals["keyword_generation"] = _sum_elapsed(keyword_trace)
    if candidate_trace:
        stage_totals["candidate_search"] = _sum_elapsed(candidate_trace)
    if batch_trace:
        stage_totals["source_selection"] = _max_elapsed(batch_trace)
    beta6: dict[str, Any] = {
        "selectorProvider": selector_meta.get("provider", ""),
        "selectorModel": selector_meta.get("model", ""),
        "selectionSource": selector_meta.get("selectionSource", ""),
        "candidateCount": selector_meta.get("candidateCount", 0),
        "selectedCount": len(selected_ids),
        "claimCardCount": claim_meta.get("claimAnalyzerPostMergeClaimCount", 0),
        "stageTimingTotals": stage_totals,
        "stageTimingTotalSec": round(sum(stage_totals.values()), 6),
        "keywordGenerationTrace": keyword_trace,
        "keywordGenerationCacheHits": selector_meta.get("keywordGenerationCacheHits", selector_meta.get("keywordCacheHits", 0)),
        "keywordGenerationCacheMisses": selector_meta.get("keywordGenerationCacheMisses", selector_meta.get("keywordCacheMisses", 0)),
        "candidateSearchTrace": candidate_trace,
        "candidateSearchCacheHits": selector_meta.get("candidateSearchCacheHits", 0),
        "candidateSearchCacheMisses": selector_meta.get("candidateSearchCacheMisses", 0),
        "selectorBatchTrace": batch_trace,
        "selectorBatchCacheHits": selector_meta.get("selectorBatchCacheHits", 0),
        "selectorBatchCacheMisses": selector_meta.get("selectorBatchCacheMisses", 0),
        "claimAnalyzer": claim_meta,
        "answerPlanner": {"status": answer_plan.get("status", ""), "cacheHit": answer_plan.get("cacheHit", False)},
    }
    return beta6


def _sum_elapsed(items: list[dict[str, Any]]) -> float:
    return round(sum(_as_float(item.get("elapsedSec")) for item in items), 6)


def _max_elapsed(items: list[dict[str, Any]]) -> float:
    return round(max((_as_float(item.get("elapsedSec")) for item in items), default=0.0), 6)


def _checks(
    *,
    terminal_status: dict[str, Any],
    result: dict[str, Any],
    timing_beta6: dict[str, Any] | None,
    language: str,
    min_answer_chars: int,
    min_sources: int,
    min_cited_claims: int,
    max_total_sec: float,
    max_source_selection_sec: float,
    require_cold_engine_cache: bool,
    wall_elapsed_sec: float,
) -> dict[str, dict[str, Any]]:
    writer = result.get("writer") if isinstance(result.get("writer"), dict) else {}
    selector = result.get("selector") if isinstance(result.get("selector"), dict) else {}
    beta6 = result.get("beta6") if isinstance(result.get("beta6"), dict) else {}
    coverage_report = beta6.get("coverageReport") if isinstance(beta6.get("coverageReport"), dict) else {}
    answer = str(result.get("answer") or "")
    sources = result.get("sources") if isinstance(result.get("sources"), list) else []
    claim_cards = result.get("claimCards") if isinstance(result.get("claimCards"), list) else []
    cited_claims = result.get("citedClaimCards") if isinstance(result.get("citedClaimCards"), list) else []
    citation_map = result.get("citationMap") if isinstance(result.get("citationMap"), dict) else {}
    language_resolution = result.get("languageResolution") if isinstance(result.get("languageResolution"), dict) else {}
    writer_provider = str(writer.get("provider") or beta6.get("writerProvider") or "")
    writer_model = str(writer.get("model") or "")
    selector_provider = str(selector.get("provider") or beta6.get("selectorProvider") or "")
    selector_model = str(selector.get("model") or beta6.get("selectorModel") or "")
    has_forced_supplement = "누락 근거 보강" in answer
    coverage_patched = coverage_report.get("patched") is True
    stage_timings = _compact_stage_timings(timing_beta6 if isinstance(timing_beta6, dict) else beta6)
    cache_check = _cold_engine_cache_check(
        timing_beta6 if isinstance(timing_beta6, dict) else beta6,
        required=require_cold_engine_cache,
    )
    total_sec = _as_float(stage_timings.get("totalSec"))
    checked_total_sec = max(total_sec, _as_float(wall_elapsed_sec))
    stage_totals = stage_timings.get("totals") if isinstance(stage_timings.get("totals"), dict) else {}
    source_selection_measured = "source_selection" in stage_totals
    source_selection_sec = _as_float(stage_totals.get("source_selection"))
    return {
        "completed": {
            "passes": terminal_status.get("status") == "completed",
            "status": terminal_status.get("status", ""),
            "error": terminal_status.get("error", ""),
        },
        "finalAnswer": {
            "passes": result.get("answerReadiness") == "final_answer",
            "answerReadiness": result.get("answerReadiness", ""),
        },
        "writerGemma4": {
            "passes": writer.get("status") == "completed" and writer_provider == EXPECTED_PROVIDER and writer_model == EXPECTED_MODEL,
            "status": writer.get("status", ""),
            "provider": writer_provider,
            "model": writer_model,
        },
        "selectorGemma4": {
            "passes": selector.get("status") == "completed" and selector_provider == EXPECTED_PROVIDER and selector_model == EXPECTED_MODEL,
            "status": selector.get("status", ""),
            "provider": selector_provider,
            "model": selector_model,
        },
        "sourceGrounding": {
            "passes": len(sources) >= min_sources and len(claim_cards) >= min_cited_claims and len(cited_claims) >= min_cited_claims and bool(citation_map),
            "sourceCount": len(sources),
            "claimCardCount": len(claim_cards),
            "citedClaimCount": len(cited_claims),
            "citationMapCount": len(citation_map),
            "expected": {
                "minSources": min_sources,
                "minCitedClaims": min_cited_claims,
            },
        },
        "answerDepth": {
            "passes": len(answer) >= min_answer_chars,
            "answerChars": len(answer),
            "expected": f">={min_answer_chars}",
        },
        "language": {
            "passes": not language or language_resolution.get("answerLanguage") == language,
            "answerLanguage": language_resolution.get("answerLanguage", ""),
            "expected": language,
        },
        "noForcedCoveragePatch": {
            "passes": not has_forced_supplement and not coverage_patched,
            "hasForcedSupplement": has_forced_supplement,
            "coveragePatched": coverage_patched,
            "patchPolicy": coverage_report.get("patchPolicy", ""),
        },
        "totalLatency": {
            "passes": max_total_sec <= 0 or checked_total_sec <= max_total_sec,
            "totalSec": total_sec,
            "engineTotalSec": total_sec,
            "wallElapsedSec": _as_float(wall_elapsed_sec),
            "checkedSec": checked_total_sec,
            "expected": "" if max_total_sec <= 0 else f"<={_format_budget(max_total_sec)}",
        },
        "sourceSelectionLatency": {
            "passes": max_source_selection_sec <= 0 or (source_selection_measured and source_selection_sec <= max_source_selection_sec),
            "measured": source_selection_measured,
            "sourceSelectionSec": source_selection_sec,
            "expected": "" if max_source_selection_sec <= 0 else f"<={_format_budget(max_source_selection_sec)}",
        },
        "coldEngineCache": cache_check,
    }


def _as_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _format_budget(value: float) -> str:
    numeric = _as_float(value)
    return str(int(numeric)) if numeric.is_integer() else str(numeric)


def _metrics(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "answerChars": len(str(result.get("answer") or "")),
        "sourceCount": len(result.get("sources") or []) if isinstance(result.get("sources"), list) else 0,
        "claimCardCount": len(result.get("claimCards") or []) if isinstance(result.get("claimCards"), list) else 0,
        "candidateClaimCount": len(result.get("candidateClaimCards") or []) if isinstance(result.get("candidateClaimCards"), list) else 0,
        "citedClaimCount": len(result.get("citedClaimCards") or []) if isinstance(result.get("citedClaimCards"), list) else 0,
        "citationMapCount": len(result.get("citationMap") or {}) if isinstance(result.get("citationMap"), dict) else 0,
    }


def _compact_stage_timings(beta6: Any) -> dict[str, Any]:
    if not isinstance(beta6, dict):
        return {"totals": {}, "totalSec": 0.0}
    raw_totals = beta6.get("stageTimingTotals")
    totals: dict[str, float] = {}
    if isinstance(raw_totals, dict):
        for key, value in raw_totals.items():
            try:
                totals[str(key)] = round(float(value), 6)
            except (TypeError, ValueError):
                continue
    try:
        total_sec = round(float(beta6.get("stageTimingTotalSec") or sum(totals.values())), 6)
    except (TypeError, ValueError):
        total_sec = round(sum(totals.values()), 6)
    return {
        "totals": totals,
        "totalSec": total_sec,
        "slowest": _slowest_stages(totals),
    }


def _slowest_stages(totals: dict[str, float], *, limit: int = 5) -> list[dict[str, Any]]:
    return [
        {"stage": stage, "seconds": seconds}
        for stage, seconds in sorted(totals.items(), key=lambda item: item[1], reverse=True)[:limit]
    ]


def _compact_cache_metrics(beta6: Any) -> dict[str, Any]:
    if not isinstance(beta6, dict):
        return {}
    answer_planner = beta6.get("answerPlanner") if isinstance(beta6.get("answerPlanner"), dict) else {}
    claim_analyzer = beta6.get("claimAnalyzer") if isinstance(beta6.get("claimAnalyzer"), dict) else {}
    return {
        "keywordGeneration": {
            "hits": int(beta6.get("keywordGenerationCacheHits") or beta6.get("keywordCacheHits") or 0),
            "misses": int(beta6.get("keywordGenerationCacheMisses") or beta6.get("keywordCacheMisses") or 0),
        },
        "candidateSearch": {
            "hits": int(beta6.get("candidateSearchCacheHits") or 0),
            "misses": int(beta6.get("candidateSearchCacheMisses") or 0),
        },
        "selectorBatches": {
            "hits": int(beta6.get("selectorBatchCacheHits") or 0),
            "misses": int(beta6.get("selectorBatchCacheMisses") or 0),
        },
        "claimAnalyzerBatches": {
            "hits": int(beta6.get("claimAnalyzerBatchCacheHits") or claim_analyzer.get("claimAnalyzerBatchCacheHits") or 0),
            "misses": int(beta6.get("claimAnalyzerBatchCacheMisses") or claim_analyzer.get("claimAnalyzerBatchCacheMisses") or 0),
        },
        "claimAnalyzerChunks": {
            "hits": int(beta6.get("claimAnalyzerChunkCacheHits") or claim_analyzer.get("claimAnalyzerChunkCacheHits") or 0),
            "misses": int(beta6.get("claimAnalyzerChunkCacheMisses") or claim_analyzer.get("claimAnalyzerChunkCacheMisses") or 0),
        },
        "answerPlanCacheHit": bool(answer_planner.get("cacheHit") or beta6.get("answerPlanCacheHit")),
        "writerCacheHit": bool(beta6.get("writerCacheHit")),
    }


def _cold_engine_cache_check(beta6: Any, *, required: bool) -> dict[str, Any]:
    metrics = _compact_cache_metrics(beta6)
    stage_names = ("keywordGeneration", "candidateSearch", "selectorBatches", "claimAnalyzerBatches", "claimAnalyzerChunks")
    stage_hits: dict[str, int] = {}
    stage_misses: dict[str, int] = {}
    observed_stages: list[str] = []
    hot_stages: list[str] = []
    for stage in stage_names:
        values = metrics.get(stage) if isinstance(metrics.get(stage), dict) else {}
        hits = int(values.get("hits") or 0)
        misses = int(values.get("misses") or 0)
        stage_hits[stage] = hits
        stage_misses[stage] = misses
        if hits or misses:
            observed_stages.append(stage)
        if hits:
            hot_stages.append(stage)
    if metrics.get("answerPlanCacheHit"):
        hot_stages.append("answerPlan")
    if metrics.get("writerCacheHit"):
        hot_stages.append("writer")
    required_selection_evidence = ("keywordGeneration", "candidateSearch", "selectorBatches")
    missing_selection_evidence = [stage for stage in required_selection_evidence if stage not in observed_stages]
    claim_evidence = "claimAnalyzerBatches" in observed_stages or "claimAnalyzerChunks" in observed_stages
    missing_evidence = list(missing_selection_evidence)
    if not claim_evidence:
        missing_evidence.append("claimAnalyzer")
    passes = True
    if required:
        passes = not hot_stages and not missing_evidence
    return {
        "passes": passes,
        "required": required,
        "hotStages": hot_stages,
        "observedStages": observed_stages,
        "missingEvidence": missing_evidence,
        "hits": stage_hits,
        "misses": stage_misses,
        "answerPlanCacheHit": bool(metrics.get("answerPlanCacheHit")),
        "writerCacheHit": bool(metrics.get("writerCacheHit")),
    }


def _compact_selection_trace(result: dict[str, Any]) -> dict[str, Any]:
    beta6 = result.get("beta6") if isinstance(result.get("beta6"), dict) else {}
    selector = result.get("selector") if isinstance(result.get("selector"), dict) else {}
    keyword_trace = _trace_items(beta6.get("keywordGenerationTrace") or selector.get("keywordGenerationTrace"))
    candidate_trace = _trace_items(beta6.get("candidateSearchTrace") or selector.get("candidateSearchTrace"))
    batch_trace = _trace_items(beta6.get("selectorBatchTrace") or selector.get("selectorBatchTrace"))
    for item in batch_trace:
        if "recoveryErrorCount" not in item and isinstance(item.get("recoveryErrors"), list):
            item["recoveryErrorCount"] = len(item["recoveryErrors"])
    return {
        "keywordGeneration": {
            "count": len(keyword_trace),
            "slowest": _slowest_trace_items(
                keyword_trace,
                fields=(
                    "round",
                    "phase",
                    "keywordCount",
                    "newKeywordCount",
                    "candidateCountBefore",
                    "candidateCountAfter",
                    "elapsedSec",
                    "timeoutSeconds",
                    "primaryTimeoutSeconds",
                    "recoveryTimeoutSeconds",
                    "elapsedExceededTimeout",
                    "llmCallCount",
                    "llmHttpStartedCount",
                    "maxPreHttpWaitSec",
                    "maxLlmElapsedSec",
                    "maxPromptBytes",
                    "maxPromptChars",
                    "primaryLlmCallCount",
                    "primaryHttpStartedCount",
                    "primaryMaxPreHttpWaitSec",
                    "primaryMaxLlmElapsedSec",
                    "primaryMaxCandidateCount",
                    "primaryMaxPromptBytes",
                    "primaryMaxPromptChars",
                    "recoveryLlmCallCount",
                    "recoveryHttpStartedCount",
                    "recoveryMaxPreHttpWaitSec",
                    "recoveryMaxLlmElapsedSec",
                    "recoveryMaxCandidateCount",
                    "recoveryMaxPromptBytes",
                    "recoveryMaxPromptChars",
                    "cacheHit",
                    "error",
                ),
            ),
        },
        "candidateSearch": {
            "count": len(candidate_trace),
            "slowest": _slowest_trace_items(candidate_trace, fields=("label", "query", "limit", "resultCount", "elapsedSec", "cacheHit")),
        },
        "selectorBatches": {
            "count": len(batch_trace),
            "slowest": _slowest_trace_items(
                batch_trace,
                fields=(
                    "batch",
                    "candidateCount",
                    "status",
                    "selectedCount",
                    "elapsedSec",
                    "timeoutSeconds",
                    "elapsedExceededTimeout",
                    "llmCallCount",
                    "llmHttpStartedCount",
                    "maxPreHttpWaitSec",
                    "maxLlmElapsedSec",
                    "primaryLlmCallCount",
                    "primaryHttpStartedCount",
                    "primaryMaxPreHttpWaitSec",
                    "primaryMaxLlmElapsedSec",
                    "primaryMaxCandidateCount",
                    "recoveryLlmCallCount",
                    "recoveryHttpStartedCount",
                    "recoveryMaxPreHttpWaitSec",
                    "recoveryMaxLlmElapsedSec",
                    "recoveryMaxCandidateCount",
                    "cacheHit",
                    "recovered",
                    "localRecovery",
                    "recoverySubBatchCount",
                    "recoveryBatchSize",
                    "recoveryError",
                    "recoveryErrorCount",
                ),
            ),
        },
    }


def _trace_items(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _slowest_trace_items(items: list[dict[str, Any]], *, fields: tuple[str, ...], limit: int = 8) -> list[dict[str, Any]]:
    def elapsed(item: dict[str, Any]) -> float:
        try:
            return float(item.get("elapsedSec") or 0.0)
        except (TypeError, ValueError):
            return 0.0

    compact: list[dict[str, Any]] = []
    for item in sorted(items, key=elapsed, reverse=True)[:limit]:
        entry: dict[str, Any] = {}
        for field in fields:
            if field in item:
                entry[field] = item[field]
        compact.append(entry)
    return compact


def _compact_llm_stage(stage: Any) -> dict[str, Any]:
    if not isinstance(stage, dict):
        return {}
    return {
        "status": stage.get("status", ""),
        "provider": stage.get("provider", ""),
        "model": stage.get("model", ""),
    }


def _compact_coverage_report(report: Any) -> dict[str, Any]:
    if not isinstance(report, dict):
        return {}
    return {
        "status": report.get("status", ""),
        "mode": report.get("mode", ""),
        "patched": report.get("patched", ""),
        "patchPolicy": report.get("patchPolicy", ""),
    }


def _compact_status(status: dict[str, Any], *, status_code: int) -> dict[str, Any]:
    progress = status.get("progress") if isinstance(status.get("progress"), dict) else {}
    return {
        "statusCode": status_code,
        "status": status.get("status", ""),
        "stage": progress.get("stage", ""),
        "detail": progress.get("detail", ""),
        "elapsedSeconds": progress.get("elapsedSeconds", status.get("elapsedSeconds", "")),
    }


def _cancel_timed_out_job(
    *,
    transport: Transport,
    clean_base: str,
    job_id: str,
    access_token: str,
    headers: dict[str, str],
) -> dict[str, Any]:
    if not job_id or not access_token:
        return {"attempted": False, "statusCode": 0, "cancelled": False, "error": "missing job token"}
    cancel_url = f"{clean_base}/api/jobs/{urllib.parse.quote(job_id)}/cancel?token={urllib.parse.quote(access_token)}"
    try:
        status_code, body = transport.post_json(cancel_url, {}, headers=headers, timeout_seconds=30)
    except Exception as exc:
        return {"attempted": True, "statusCode": 0, "cancelled": False, "error": str(exc)}
    cancelled = status_code == 200 and str(body.get("status") or "") == "cancelled"
    return {
        "attempted": True,
        "statusCode": status_code,
        "cancelled": cancelled,
        "status": body.get("status", ""),
        "error": body.get("error", ""),
    }


def _failure_report(
    *,
    base_url: str,
    product: str,
    query: str,
    job_id: str,
    create_status: int,
    error: str,
    create_body: dict[str, Any],
    status_tail: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "passes": False,
        "baseUrl": base_url,
        "product": product,
        "query": query,
        "jobId": job_id,
        "createStatus": create_status,
        "finalStatus": "",
        "statusPollCount": 0,
        "statusTail": status_tail,
        "timeoutCancel": {"attempted": False, "statusCode": 0, "cancelled": False, "error": ""},
        "metrics": {},
        "checks": {
            "created": {
                "passes": False,
                "error": error,
                "body": create_body,
            }
        },
    }


def _open_json(request: urllib.request.Request, *, timeout_seconds: float) -> tuple[int, dict[str, Any]]:
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return int(response.status), _decode_json(response.read())
    except urllib.error.HTTPError as exc:
        return int(exc.code), _decode_json(exc.read())


def _decode_json(raw: bytes) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except Exception:
        return {"raw": raw.decode("utf-8", errors="replace")}
    return parsed if isinstance(parsed, dict) else {"value": parsed}


if __name__ == "__main__":
    raise SystemExit(main())
