#!/usr/bin/env python3
"""Run a real beta-6 selector-only probe and write comparator-ready JSON."""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared_platform.beta6 import DEFAULT_LAWKEY_WRITER_MODEL, default_llm_client_from_env, select_rows_with_beta6_llm
from shared_platform.products import PRODUCT_PROFILES, ProductProfile
from shared_platform.search import SearchResult


SelectorFn = Callable[..., tuple[list[SearchResult], dict[str, Any]]]


def _as_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _selected_source_kinds(rows: list[SearchResult]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        kind = str(row.source_kind or row.case_type or "unknown").strip() or "unknown"
        counts[kind] += 1
    return dict(counts)


def _slowest_selector_batches(selector: dict[str, Any], *, limit: int = 5) -> list[dict[str, Any]]:
    trace = selector.get("selectorBatchTrace")
    if not isinstance(trace, list):
        return []
    batches = [item for item in trace if isinstance(item, dict)]
    batches.sort(key=lambda item: _as_float(item.get("elapsedSec")), reverse=True)
    return batches[:limit]


def _selector_batch_elapsed_sum_sec(selector: dict[str, Any]) -> float:
    trace = selector.get("selectorBatchTrace")
    if not isinstance(trace, list):
        return 0.0
    total = sum(_as_float(item.get("elapsedSec")) for item in trace if isinstance(item, dict))
    return round(total, 3)


def _selector_trace_max_int(selector: dict[str, Any], key: str) -> int:
    trace = selector.get("selectorBatchTrace")
    if not isinstance(trace, list):
        return 0
    return max((_as_int(item.get(key)) for item in trace if isinstance(item, dict)), default=0)


def build_report(
    *,
    product: ProductProfile,
    query: str,
    language: str,
    limit: int,
    llm_client: Any,
    model: str,
    provider: str,
    cache_root: Path | None,
    selector_fn: SelectorFn | None = None,
    require_cold_selector: bool = False,
    monotonic: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    started = monotonic()
    active_selector = selector_fn or select_rows_with_beta6_llm
    selected_rows, selector = active_selector(
        product,
        query,
        language,
        limit=limit,
        llm_client=llm_client,
        model=model,
        provider=provider,
        cache_root=cache_root,
    )
    elapsed = round(max(0.0, monotonic() - started), 3)
    selected_ids = [row.canonical_id for row in selected_rows if row.canonical_id]
    status = str(selector.get("status") or "")
    selected_count = len(selected_ids)
    candidate_count = _as_int(selector.get("candidateCount"))
    slowest = _slowest_selector_batches(selector)
    cache_hits = int(selector.get("selectorBatchCacheHits") or 0)
    cache_misses = int(selector.get("selectorBatchCacheMisses") or 0)
    cold_selector_passes = (not require_cold_selector) or (cache_misses > 0 and cache_hits == 0)
    mechanical_passes = status in {"completed", "fallback_selector_error"} and candidate_count >= selected_count and selected_count > 0
    return {
        "passes": mechanical_passes and cold_selector_passes,
        "elapsedSec": elapsed,
        "selectorElapsedSec": elapsed,
        "selectorBatchElapsedSumSec": _selector_batch_elapsed_sum_sec(selector),
        "status": status,
        "query": query,
        "product": product.key,
        "language": language,
        "candidateCount": candidate_count,
        "selectedCount": selected_count,
        "selectedIds": selected_ids,
        "selectedSourceKinds": _selected_source_kinds(selected_rows),
        "selectorInputMode": selector.get("selectorInputMode", ""),
        "selectorEvidenceLedgerEnabled": bool(selector.get("selectorEvidenceLedgerEnabled")),
        "selectorEvidenceLedgerCount": _as_int(selector.get("selectorEvidenceLedgerCount")),
        "selectorLocalRecoveryCount": _as_int(selector.get("selectorLocalRecoveryCount")),
        "selectorBatchSize": _as_int(selector.get("selectorBatchSize")),
        "selectorBatchWorkers": _as_int(selector.get("selectorBatchWorkers")),
        "selectorCandidateLimit": _as_int(selector.get("selectorCandidateLimit")),
        "selectorAuditedCandidateCount": _as_int(selector.get("selectorAuditedCandidateCount")),
        "selectorBatchCacheHits": cache_hits,
        "selectorBatchCacheMisses": cache_misses,
        "coldSelector": {
            "required": bool(require_cold_selector),
            "passes": cold_selector_passes,
            "cacheHits": cache_hits,
            "cacheMisses": cache_misses,
        },
        "maxPreHttpWaitSec": max((_as_float(item.get("maxPreHttpWaitSec")) for item in slowest), default=0.0),
        "maxLlmElapsedSec": max((_as_float(item.get("maxLlmElapsedSec")) for item in slowest), default=0.0),
        "maxPrimaryLlmElapsedSec": max((_as_float(item.get("primaryMaxLlmElapsedSec")) for item in slowest), default=0.0),
        "maxRecoveryLlmElapsedSec": max((_as_float(item.get("recoveryMaxLlmElapsedSec")) for item in slowest), default=0.0),
        "maxPromptBytes": _selector_trace_max_int(selector, "maxPromptBytes"),
        "maxPrimaryPromptBytes": _selector_trace_max_int(selector, "primaryMaxPromptBytes"),
        "maxRecoveryPromptBytes": _selector_trace_max_int(selector, "recoveryMaxPromptBytes"),
        "overTimeoutCount": sum(1 for item in selector.get("selectorBatchTrace") or [] if isinstance(item, dict) and item.get("elapsedExceededTimeout")),
        "selectorSlowest": slowest,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--product", default="tcm")
    parser.add_argument("--query", required=True)
    parser.add_argument("--language", default="ko")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--model", default=DEFAULT_LAWKEY_WRITER_MODEL)
    parser.add_argument("--cache-root", type=Path, default=Path("runs") / "_beta6_batch_cache")
    parser.add_argument("--require-cold-selector", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    product = PRODUCT_PROFILES[str(args.product).strip().lower()]
    llm_client = default_llm_client_from_env()
    if llm_client is None:
        raise RuntimeError("LLM client is not available; check RELIGION_LLM_PROVIDER and Gemma/Lawkey keys")
    provider = str(getattr(llm_client, "provider", "custom_llm") or "custom_llm")
    report = build_report(
        product=product,
        query=args.query,
        language=args.language,
        limit=args.limit,
        llm_client=llm_client,
        model=args.model,
        provider=provider,
        cache_root=args.cache_root,
        require_cold_selector=bool(args.require_cold_selector),
    )
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report["passes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
