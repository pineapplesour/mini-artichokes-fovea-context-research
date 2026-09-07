#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared_platform.beta6 import default_llm_client_from_env
from shared_platform.answer_prompts import direct_answer_messages
from tools.benchmark_provider import create_benchmark_llm_client
from tools.run_frozen_beta6_benchmark import build_tasks
from tools.run_unified_mcq_benchmark import parse_mcq_prediction, parse_short_answer_prediction


DIRECT_WEB_SEARCH_ENV = "UNIVERSAL_EVAL_CODEX_WEB_SEARCH"
DIRECT_WEB_SEARCH_REQUIRED_ENV = "UNIVERSAL_EVAL_CODEX_WEB_SEARCH_REQUIRED"
REQUIRED_SEARCH_POLICY_ATTEMPTS = 3


def run_manifest(
    *,
    public_path: Path,
    output_dir: Path,
    llm_client: Any | None = None,
    model: str,
    timeout_seconds: float = 300.0,
    resume: bool = False,
    max_cases: int = 0,
    case_ids: list[str] | None = None,
) -> dict[str, Any]:
    manifest = json.loads(public_path.read_text(encoding="utf-8"))
    client = llm_client if llm_client is not None else create_benchmark_llm_client(
        model=model,
        fallback_factory=default_llm_client_from_env,
        timeout_seconds=timeout_seconds,
    )
    if client is None:
        raise RuntimeError("no LLM client configured")
    search_required = _web_search_required()
    if search_required and not _web_search_enabled():
        raise RuntimeError(
            f"{DIRECT_WEB_SEARCH_REQUIRED_ENV}=1 requires {DIRECT_WEB_SEARCH_ENV}=1"
        )
    model_metadata = _model_metadata(client, model)
    tasks = build_tasks(manifest, max_cases=max_cases, case_ids=case_ids)
    result_dir = output_dir / "results"
    result_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    started = time.time()
    for task in tasks:
        artifact_id = str(task.get("artifactId") or "").strip()
        if not artifact_id:
            continue
        record_path = result_dir / f"{artifact_id}.json"
        if resume and record_path.exists():
            records.append(json.loads(record_path.read_text(encoding="utf-8")))
            continue
        record = {
            "id": artifact_id,
            "caseId": str(task.get("caseId") or artifact_id),
            "variantId": str(task.get("variantId") or ""),
            "graderId": str(task.get("graderId") or task.get("caseId") or artifact_id),
            "benchmarkId": str(manifest.get("benchmarkId") or ""),
            "taskType": str(manifest.get("taskType") or ""),
            "product": str(manifest.get("product") or ""),
            "mode": "direct",
            "query": str(task.get("query") or ""),
            "prediction": None,
            "answer": "",
            "answerMarkdown": "",
            "selectedEvidence": [],
            "sources": [],
            "retrievedCases": [],
            "citedClaimCards": [],
            "modelMetadata": model_metadata,
            "error": "",
        }
        call_trace: dict[str, Any] | None = None
        call_traces: list[dict[str, Any]] = []
        policy_attempts = 0
        policy_satisfied = not search_required
        search_evidence = ""
        try:
            answer = ""
            max_policy_attempts = REQUIRED_SEARCH_POLICY_ATTEMPTS if search_required else 1
            for policy_attempt in range(1, max_policy_attempts + 1):
                policy_attempts = policy_attempt
                answer = str(
                    client.complete(
                        _direct_messages(
                            record["query"],
                            language=str(task.get("language") or ""),
                            search_required=search_required,
                            policy_retry=policy_attempt > 1,
                        ),
                        model=model,
                        timeout_seconds=timeout_seconds,
                    )
                    or ""
                ).strip()
                call_trace = _consume_call_trace(client)
                if call_trace:
                    call_traces.append(call_trace)
                search_evidence = _extract_search_evidence(answer)
                policy_satisfied = (
                    not search_required
                    or (_trace_has_web_search(call_trace) and bool(search_evidence))
                )
                if policy_satisfied:
                    break
            if not policy_satisfied:
                raise RuntimeError(
                    "required_web_search_evidence_missing: no accepted response contained both "
                    "a completed web-search trace and a nonempty `검색 근거:` line"
                )
            record["answer"] = answer
            record["answerMarkdown"] = answer
            record["answerPreview"] = answer[:1200]
            record["prediction"] = _prediction(
                answer,
                parser=str(task.get("parser") or ""),
                option_ids=[str(item) for item in task.get("optionIds") or []],
            )
            record["llmUsed"] = True
        except Exception as exc:  # noqa: BLE001
            record["error"] = str(exc)
            record["llmUsed"] = False
            if call_trace is None:
                call_trace = _consume_call_trace(client)
                if call_trace:
                    call_traces.append(call_trace)
        finally:
            if call_trace:
                record["modelTrace"] = call_trace
            if call_traces:
                record["modelTraceAttempts"] = call_traces
            if search_required:
                record["webSearchRequirement"] = {
                    "required": True,
                    "satisfied": policy_satisfied,
                    "policyAttempts": policy_attempts,
                    "searchEvidence": search_evidence,
                }
        record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        records.append(record)
    summary = {
        "benchmarkId": str(manifest.get("benchmarkId") or ""),
        "taskType": str(manifest.get("taskType") or ""),
        "product": str(manifest.get("product") or ""),
        "mode": "direct",
        "total": {
            "total": len(records),
            "predicted": sum(1 for item in records if item.get("prediction")),
            "errors": sum(1 for item in records if item.get("error")),
        },
        "modelMetadata": model_metadata,
        "webSearchRequirement": {
            "required": search_required,
            "policyAttemptsPerCase": REQUIRED_SEARCH_POLICY_ATTEMPTS if search_required else 1,
        },
        "elapsedSec": round(max(0.0, time.time() - started), 3),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def _direct_messages(
    query: str,
    *,
    language: str,
    search_required: bool = False,
    policy_retry: bool = False,
) -> list[dict[str, str]]:
    if _web_search_enabled():
        search_policy = (
            "Before answering, you MUST use live web search. Translate the underlying concepts or facts into "
            "generalized queries that do not copy the question or choices. Continue searching and refining the "
            "queries until at least one credible external source directly supports the decisive fact. Do not "
            "answer from memory alone. If a result is inconclusive or sources conflict, keep searching. The first "
            "line must still follow the requested answer format; on the next line write `검색 근거:` followed by "
            "the source title or domain and the decisive fact it supports. "
            if search_required
            else "You may use live web search for general concepts and facts. "
        )
        retry_policy = (
            "A previous response was rejected because it lacked a completed search trace or the required "
            "`검색 근거:` line. Perform the search now and include that evidence line. "
            if policy_retry
            else ""
        )
        return [
            {
                "role": "system",
                "content": (
                    "Answer the user's question directly. "
                    + search_policy
                    + retry_policy
                    + "You may run short read-only calculation code when useful. It is strictly forbidden "
                    "to search for or open the original question sheet, exam paper, benchmark, answer key, quiz "
                    "mirror, or exact/near-exact wording from the question or options. Never include question "
                    "numbers, exam names, source-file names, or answer-choice text in a search query. Do not inspect "
                    "local files. Obey the requested output format."
                ),
            },
            {
                "role": "user",
                "content": f"Answer language hint: {language or 'same as question'}\n\n{query}",
            },
        ]
    return direct_answer_messages(query, language=language)


def _web_search_enabled() -> bool:
    return os.getenv(DIRECT_WEB_SEARCH_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def _web_search_required() -> bool:
    return os.getenv(DIRECT_WEB_SEARCH_REQUIRED_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def _trace_has_web_search(trace: dict[str, Any] | None) -> bool:
    if not isinstance(trace, dict):
        return False
    events = trace.get("webSearchEvents")
    return isinstance(events, list) and any(isinstance(event, dict) for event in events)


def _extract_search_evidence(answer: str) -> str:
    for line in str(answer or "").splitlines()[1:]:
        normalized = line.strip()
        for marker in ("검색 근거:", "Search evidence:"):
            if normalized.lower().startswith(marker.lower()):
                evidence = normalized[len(marker) :].strip()
                if len(evidence) >= 8:
                    return evidence
    return ""


def _consume_call_trace(client: Any) -> dict[str, Any] | None:
    consumer = getattr(client, "consume_last_call_trace", None)
    if not callable(consumer):
        return None
    trace = consumer()
    return dict(trace) if isinstance(trace, dict) else None


def _prediction(answer: str, *, parser: str, option_ids: list[str]) -> str | None:
    if parser == "short_answer":
        return parse_short_answer_prediction(answer)
    if parser == "mcq":
        return parse_mcq_prediction(answer, allowed_ids=option_ids)
    return answer or None


def _model_metadata(client: Any, model: str) -> dict[str, Any]:
    decoding = getattr(client, "decoding", None)
    if decoding is None:
        decoding = getattr(client, "decoding_config", None)
    if not isinstance(decoding, dict):
        decoding = {}
        for name in ("temperature", "top_p", "top_k", "max_tokens", "thinking_level"):
            if hasattr(client, name):
                value = getattr(client, name)
                if value not in (None, ""):
                    decoding[name] = value
    return {
        "provider": str(getattr(client, "provider", "custom_llm") or "custom_llm"),
        "model": str(model or getattr(client, "default_model", "") or ""),
        "decoding": {str(key): value for key, value in sorted(decoding.items())},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a public benchmark directly with no database.")
    parser.add_argument("--public", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    parser.add_argument("--max-cases", type=int, default=0)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    summary = run_manifest(
        public_path=args.public,
        output_dir=args.output_dir,
        model=args.model,
        timeout_seconds=args.timeout_seconds,
        max_cases=args.max_cases,
        case_ids=args.case_id,
        resume=args.resume,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
