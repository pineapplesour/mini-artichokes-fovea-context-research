#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared_platform.beta6 import default_llm_client_from_env
from shared_platform.products import PRODUCT_PROFILES, ProductProfile
from shared_platform.universal_engine import UniversalEngine
from tools.benchmark_provider import create_benchmark_llm_client
from tools.run_unified_legal_benchmark import _profiles_with_legal_defaults
from tools.run_unified_mcq_benchmark import (
    build_mcq_query,
    build_short_answer_query,
    extract_option_ids,
    parse_mcq_prediction,
    parse_short_answer_prediction,
)


SUPPORTED_TASK_TYPES = {"mcq", "short_answer", "legal_retrieval_answer"}


def run_manifest(
    *,
    public_path: Path,
    output_dir: Path,
    products: dict[str, ProductProfile] | None = None,
    llm_client: Any | None = None,
    model: str = "",
    candidate_limit: int = 40,
    evidence_limit: int = 12,
    resume: bool = False,
    max_cases: int = 0,
    case_ids: list[str] | None = None,
    engine_factory: Callable[..., UniversalEngine] = UniversalEngine,
) -> dict[str, Any]:
    manifest = json.loads(public_path.read_text(encoding="utf-8"))
    task_type = str(manifest.get("taskType") or "")
    if task_type not in SUPPORTED_TASK_TYPES:
        raise ValueError(f"unsupported taskType={task_type}: {public_path}")
    profiles = _profiles_with_legal_defaults(products or dict(PRODUCT_PROFILES))
    product_key = str(manifest.get("product") or "").strip()
    product = profiles[product_key]
    client = llm_client if llm_client is not None else create_benchmark_llm_client(
        model=model,
        fallback_factory=default_llm_client_from_env,
    )
    if client is None:
        raise RuntimeError("no LLM client configured")
    engine = engine_factory(
        corpus_path=product.db_path,
        llm_client=client,
        model=model,
        candidate_limit=candidate_limit,
        evidence_limit=evidence_limit,
    )
    result_dir = output_dir / "results"
    result_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    started = time.time()
    for case in _limited_cases(manifest, max_cases=max_cases, case_ids=case_ids):
        if task_type == "legal_retrieval_answer":
            records.extend(
                _run_legal_case(
                    manifest,
                    case,
                    engine=engine,
                    result_dir=result_dir,
                    resume=resume,
                    default_language=product.default_language,
                )
            )
        else:
            record = _run_answer_case(
                manifest,
                case,
                engine=engine,
                result_dir=result_dir,
                resume=resume,
                default_language=product.default_language,
            )
            if record:
                records.append(record)
    return _write_summary(output_dir, manifest=manifest, records=records, started=started)


def _run_answer_case(
    manifest: dict[str, Any],
    case: dict[str, Any],
    *,
    engine: UniversalEngine,
    result_dir: Path,
    resume: bool,
    default_language: str,
) -> dict[str, Any] | None:
    case_id = str(case.get("id") or "").strip()
    if not case_id:
        return None
    record_path = result_dir / f"{case_id}.json"
    if resume and record_path.exists():
        return json.loads(record_path.read_text(encoding="utf-8"))
    language = str(case.get("language") or manifest.get("language") or default_language or "ko")
    task_type = str(manifest.get("taskType") or "")
    prompt = str(case.get("prompt") or "")
    option_ids: list[str] = []
    if task_type == "short_answer":
        query = build_short_answer_query(prompt, language=language)
    else:
        option_ids = extract_option_ids(
            prompt,
            case.get("options") if isinstance(case.get("options"), list) else None,
        )
        query = build_mcq_query(prompt, language=language, option_ids=option_ids)
    record = {
        "id": case_id,
        "caseId": case_id,
        "benchmarkId": manifest.get("benchmarkId", ""),
        "taskType": task_type,
        "product": manifest.get("product", ""),
        "mode": "universal",
        "query": query,
        "prediction": None,
        "error": "",
    }
    try:
        result = engine.answer(query, language=language)
        answer = str(result.get("answer") or "")
        prediction = (
            parse_short_answer_prediction(answer)
            if task_type == "short_answer"
            else parse_mcq_prediction(answer, allowed_ids=option_ids)
        )
        record.update(_result_artifact_fields(result, answer=answer))
        record["prediction"] = prediction
        record["optionIds"] = option_ids
    except Exception as exc:  # noqa: BLE001 - durable benchmark artifacts retain per-case errors.
        record["error"] = str(exc)
    _write_record(record_path, record)
    return record


def _run_legal_case(
    manifest: dict[str, Any],
    case: dict[str, Any],
    *,
    engine: UniversalEngine,
    result_dir: Path,
    resume: bool,
    default_language: str,
) -> list[dict[str, Any]]:
    case_id = str(case.get("id") or "").strip()
    if not case_id:
        return []
    language = str(case.get("language") or manifest.get("language") or default_language or "ko")
    grader_id = str(case.get("graderRef") or case_id)
    variants = case.get("variants") if isinstance(case.get("variants"), list) else []
    if not variants and str(case.get("query") or "").strip():
        variants = [{"id": "v1", "query": str(case.get("query") or "").strip()}]
    records: list[dict[str, Any]] = []
    for variant in variants:
        if not isinstance(variant, dict):
            continue
        variant_id = str(variant.get("id") or "v1").strip() or "v1"
        query = str(variant.get("query") or "").strip()
        if not query:
            continue
        artifact_id = f"{case_id}__{variant_id}"
        record_path = result_dir / f"{artifact_id}.json"
        if resume and record_path.exists():
            records.append(json.loads(record_path.read_text(encoding="utf-8")))
            continue
        record = {
            "id": artifact_id,
            "caseId": case_id,
            "variantId": variant_id,
            "graderId": grader_id,
            "benchmarkId": manifest.get("benchmarkId", ""),
            "taskType": "legal_retrieval_answer",
            "product": manifest.get("product", ""),
            "mode": "universal",
            "query": query,
            "answer": "",
            "answerMarkdown": "",
            "prediction": None,
            "error": "",
        }
        try:
            result = engine.answer(query, language=language)
            answer = str(result.get("answer") or "")
            record.update(_result_artifact_fields(result, answer=answer))
            record["answer"] = answer
            record["answerMarkdown"] = answer
            record["prediction"] = answer or None
        except Exception as exc:  # noqa: BLE001
            record["error"] = str(exc)
        _write_record(record_path, record)
        records.append(record)
    return records


def _result_artifact_fields(result: dict[str, Any], *, answer: str) -> dict[str, Any]:
    evidence = [dict(item) for item in result.get("selectedEvidence") or [] if isinstance(item, dict)]
    reranker = result.get("reranker") if isinstance(result.get("reranker"), dict) else {}
    coverage_audit = (
        reranker.get("coverageAudit") if isinstance(reranker.get("coverageAudit"), dict) else {}
    )
    for index, item in enumerate(evidence, start=1):
        item.setdefault("rank", index)
    cited_labels = {int(value) for value in re.findall(r"\[S(\d+)\]", answer)}
    cited_cards = [
        {
            "id": f"cite-{item.get('label') or index}",
            "sourceId": item.get("sourceId", ""),
            "label": item.get("label", f"S{index}"),
        }
        for index, item in enumerate(evidence, start=1)
        if index in cited_labels
    ]
    candidate_ids = [str(item) for item in result.get("candidateIds") or [] if str(item)]
    digest = hashlib.sha256(
        json.dumps(candidate_ids, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "answer": answer,
        "answerMarkdown": answer,
        "answerPreview": answer[:1200],
        "answerReadiness": "final_answer" if answer else "empty_answer",
        "selectedEvidence": evidence,
        "selectedEvidenceIds": [str(item.get("sourceId") or "") for item in evidence],
        "sources": evidence,
        "retrievedCases": evidence,
        "candidateCount": int(result.get("candidateCount") or 0),
        "candidateIds": candidate_ids,
        "candidateSetDigest": f"sha256:{digest}",
        "selectedCount": len(evidence),
        "contextPacketCount": len(evidence),
        "contextPacketIds": [str(item.get("packetId") or "") for item in evidence if item.get("packetId")],
        "contextPackets": evidence,
        "selectorStatus": str(reranker.get("status") or "completed"),
        "selectionSource": "universal_semantic_reranker",
        "coverageAuditUsed": bool(coverage_audit),
        "coverageAuditStatus": str(coverage_audit.get("status") or "not_run"),
        "coverageAuditSelectedIds": [
            str(item) for item in coverage_audit.get("selectedIds") or [] if str(item)
        ],
        "writerStatus": "completed" if answer else "empty",
        "writerMode": "universal_evidence_writer",
        "citedClaimCards": cited_cards,
        "citedClaimCount": len(cited_cards),
        "citedClaimSourceIds": [str(item.get("sourceId") or "") for item in cited_cards],
        "modelMetadata": result.get("modelMetadata") if isinstance(result.get("modelMetadata"), dict) else {},
        "queryPlan": result.get("queryPlan") if isinstance(result.get("queryPlan"), dict) else {},
        "corpusSchema": str(result.get("corpusSchema") or ""),
        "timing": result.get("timing") if isinstance(result.get("timing"), dict) else {},
        "llmUsed": True,
    }


def _limited_cases(
    manifest: dict[str, Any],
    *,
    max_cases: int,
    case_ids: list[str] | None,
) -> list[dict[str, Any]]:
    cases = [item for item in manifest.get("cases", []) if isinstance(item, dict)]
    allowed = {str(item).strip().lower() for item in case_ids or [] if str(item).strip()}
    if allowed:
        cases = [item for item in cases if str(item.get("id") or "").strip().lower() in allowed]
    if max_cases > 0:
        cases = cases[:max_cases]
    return cases


def _write_record(path: Path, record: dict[str, Any]) -> None:
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_summary(
    output_dir: Path,
    *,
    manifest: dict[str, Any],
    records: list[dict[str, Any]],
    started: float,
) -> dict[str, Any]:
    total = {
        "total": len(records),
        "predicted": sum(1 for item in records if item.get("prediction")),
        "errors": sum(1 for item in records if item.get("error")),
    }
    model_values = [item.get("modelMetadata") for item in records if isinstance(item.get("modelMetadata"), dict)]
    model_metadata = model_values[0] if model_values and all(value == model_values[0] for value in model_values) else {}
    summary = {
        "benchmarkId": manifest.get("benchmarkId", ""),
        "taskType": manifest.get("taskType", ""),
        "product": manifest.get("product", ""),
        "mode": "universal",
        "total": total,
        "modelMetadata": model_metadata,
        "elapsedSec": round(max(0.0, time.time() - started), 3),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one manifest through the domain-neutral universal engine.")
    parser.add_argument("--public", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--db-path", type=Path, default=None)
    parser.add_argument("--model", default="")
    parser.add_argument("--candidate-limit", type=int, default=40)
    parser.add_argument("--evidence-limit", type=int, default=12)
    parser.add_argument("--max-cases", type=int, default=0)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    products: dict[str, ProductProfile] | None = None
    if args.db_path is not None:
        manifest = json.loads(args.public.read_text(encoding="utf-8"))
        key = str(manifest.get("product") or "")
        profiles = _profiles_with_legal_defaults(dict(PRODUCT_PROFILES))
        products = {**profiles, key: replace(profiles[key], db_path=args.db_path)}
    report = run_manifest(
        public_path=args.public,
        output_dir=args.output_dir,
        products=products,
        model=args.model,
        candidate_limit=args.candidate_limit,
        evidence_limit=args.evidence_limit,
        max_cases=args.max_cases,
        case_ids=args.case_id,
        resume=args.resume,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
