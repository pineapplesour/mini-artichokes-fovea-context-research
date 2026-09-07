#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared_platform.beta6 import Beta6JobManager, build_beta6_direct_messages, default_llm_client_from_env
from shared_platform.products import PRODUCT_PROFILES, ProductProfile


DEFAULT_LEGAL_PRODUCT_PROFILES: dict[str, ProductProfile] = {
    "lawkey": ProductProfile(
        key="lawkey",
        name="Lawkey",
        db_path=Path(
            os.getenv(
                "LAWKEY_PRECEDENT_DB_PATH",
                "/var/lib/universal-artichoke/lawkey/precedents.sqlite3",
            )
        ),
        db_shape="precedents",
        languages=("ko",),
        default_language="ko",
        theme="lawkey",
        safety_notice=(
            "This is source-grounded legal information, not legal advice. "
            "Consult a qualified lawyer for case-specific decisions."
        ),
    )
}


def _profiles_with_legal_defaults(
    products: dict[str, ProductProfile] | None = None,
) -> dict[str, ProductProfile]:
    profiles = dict(PRODUCT_PROFILES if products is None else products)
    for key, profile in DEFAULT_LEGAL_PRODUCT_PROFILES.items():
        profiles.setdefault(key, profile)
    return profiles


def run_direct_manifest(
    *,
    public_path: Path,
    output_dir: Path,
    products: dict[str, ProductProfile] | None = None,
    llm_client: Any | None = None,
    resume: bool = False,
    model: str = "",
    max_cases: int = 0,
    case_ids: list[str] | None = None,
) -> dict[str, Any]:
    manifest = _load_public_manifest(public_path)
    profiles = _profiles_with_legal_defaults(products)
    product_key = str(manifest.get("product") or "").strip()
    product = profiles[product_key]
    client = llm_client if llm_client is not None else default_llm_client_from_env()
    if client is None:
        raise RuntimeError("no LLM client configured")
    model_metadata = _client_model_metadata(client, model=model)
    result_dir = output_dir / "results"
    result_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    started = time.time()
    for case in _limited_cases(manifest, max_cases=max_cases, case_ids=case_ids):
        case_id = str(case.get("id") or "").strip()
        if not case_id:
            continue
        language = str(case.get("language") or manifest.get("language") or product.default_language or "").strip()
        grader_id = str(case.get("graderRef") or case_id)
        for variant in _case_variants(case):
            variant_id = str(variant.get("id") or "v1").strip() or "v1"
            query = str(variant.get("query") or "").strip()
            if not query:
                continue
            artifact_id = f"{case_id}__{variant_id}"
            record_path = result_dir / f"{artifact_id}.json"
            if resume and record_path.exists():
                records.append(json.loads(record_path.read_text(encoding="utf-8")))
                continue
            record = _base_record(
                manifest,
                case_id=case_id,
                variant_id=variant_id,
                grader_id=grader_id,
                query=query,
                language=language,
                mode="direct",
            )
            try:
                answer = str(client.complete(build_beta6_direct_messages(product, query, language), model=model) or "")
                record.update(
                    {
                        "answer": answer,
                        "answerMarkdown": answer,
                        "llmUsed": True,
                        "llmProvider": model_metadata["provider"],
                        "llmModel": model_metadata["model"],
                        "modelMetadata": model_metadata,
                        "selectedEvidence": [],
                        "sources": [],
                        "passages": [],
                        "retrievedCases": [],
                        "candidateClaimCards": [],
                        "citedClaimCards": [],
                    }
                )
            except Exception as exc:
                record["error"] = str(exc)
                record["llmUsed"] = False
            record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
            records.append(record)
    return _write_summary(output_dir, manifest=manifest, records=records, mode="direct", started=started)


def run_legal_manifest(
    *,
    public_path: Path,
    output_dir: Path,
    products: dict[str, ProductProfile] | None = None,
    llm_client: Any | None = None,
    resume: bool = False,
    limit: int = 50,
    analysis_mode: str = "fast",
    max_cases: int = 0,
    case_ids: list[str] | None = None,
) -> dict[str, Any]:
    manifest = _load_public_manifest(public_path)
    profiles = _profiles_with_legal_defaults(products)
    product_key = str(manifest.get("product") or "").strip()
    product = profiles[product_key]
    result_dir = output_dir / "results"
    result_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    started = time.time()
    if not product.db_path.exists():
        return _write_missing_db_records(
            manifest,
            product=product,
            output_dir=output_dir,
            result_dir=result_dir,
            records=records,
            resume=resume,
            max_cases=max_cases,
            case_ids=case_ids,
            started=started,
        )
    client = llm_client if llm_client is not None else default_llm_client_from_env()
    runtime = Beta6JobManager(
        {product_key: product},
        runs_root=output_dir / "beta6_jobs",
        llm_client=client,
        resume_pending_jobs=False,
    )
    try:
        for case in _limited_cases(manifest, max_cases=max_cases, case_ids=case_ids):
            case_id = str(case.get("id") or "").strip()
            if not case_id:
                continue
            language = str(case.get("language") or manifest.get("language") or product.default_language or "").strip()
            grader_id = str(case.get("graderRef") or case_id)
            case_limit = _case_candidate_limit(case, default=limit)
            for variant in _case_variants(case):
                variant_id = str(variant.get("id") or "v1").strip() or "v1"
                query = str(variant.get("query") or "").strip()
                if not query:
                    continue
                artifact_id = f"{case_id}__{variant_id}"
                record_path = result_dir / f"{artifact_id}.json"
                if resume and record_path.exists():
                    records.append(json.loads(record_path.read_text(encoding="utf-8")))
                    continue
                record = _base_record(
                    manifest,
                    case_id=case_id,
                    variant_id=variant_id,
                    grader_id=grader_id,
                    query=query,
                    language=language,
                    mode="engine",
                )
                try:
                    result = runtime.answer_sync(
                        product=product_key,
                        query=query,
                        language=language,
                        limit=case_limit,
                        analysis_mode=analysis_mode,
                    )
                    selector = result.get("selector") if isinstance(result.get("selector"), dict) else {}
                    writer = result.get("writer") if isinstance(result.get("writer"), dict) else {}
                    beta6 = result.get("beta6") if isinstance(result.get("beta6"), dict) else {}
                    artifacts = result.get("artifacts") if isinstance(result.get("artifacts"), dict) else {}
                    context_packets = result.get("contextPackets") if isinstance(result.get("contextPackets"), list) else []
                    answer = str(result.get("answer") or result.get("answerMarkdown") or "")
                    writer_provider = str(beta6.get("writerProvider", writer.get("provider", "")) or "")
                    writer_model = str(beta6.get("writerModel", writer.get("model", "")) or "")
                    model_metadata = _model_metadata(
                        provider=writer_provider,
                        model=writer_model,
                        decoding=_client_decoding_metadata(client),
                    )
                    record.update(
                        {
                            "jobId": result.get("jobId", ""),
                            "answer": answer,
                            "answerMarkdown": str(result.get("answerMarkdown") or answer),
                            "answerReadiness": result.get("answerReadiness", ""),
                            "selectedEvidence": _ranked_list(result.get("selectedEvidence") or []),
                            "sources": _ranked_list(result.get("sources") or []),
                            "passages": _ranked_list(result.get("passages") or []),
                            "retrievedCases": _ranked_list(result.get("beta6SelectedRecords") or []),
                            "candidateClaimCards": result.get("candidateClaimCards") or [],
                            "citedClaimCards": result.get("citedClaimCards") or [],
                            "contextPacketCount": beta6.get("contextPacketCount", len(context_packets)),
                            "contextPacketIds": _context_packet_ids(context_packets),
                            "contextPacketArtifact": artifacts.get("contextPackets", ""),
                            "selectorStatus": beta6.get("selectorStatus", selector.get("status", "")),
                            "selectionSource": beta6.get("selectionSource", selector.get("selectionSource", "")),
                            "candidateCount": beta6.get("candidateCount", selector.get("candidateCount", 0)),
                            "candidateIds": selector.get("candidateIds", []),
                            "candidateSetDigest": selector.get("candidateSetDigest", ""),
                            "selectedCount": beta6.get("selectedCount", len(result.get("selectedEvidence") or [])),
                            "writerStatus": beta6.get("writerStatus", writer.get("status", "")),
                            "writerMode": writer.get("mode", ""),
                            "writerProvider": writer_provider,
                            "writerModel": writer_model,
                            "modelMetadata": model_metadata,
                            "llmUsed": bool(result.get("llmUsed")),
                        }
                    )
                except Exception as exc:
                    record["error"] = str(exc)
                record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
                records.append(record)
    finally:
        runtime.shutdown(wait=False)
    return _write_summary(output_dir, manifest=manifest, records=records, mode="engine", started=started)


def _write_missing_db_records(
    manifest: dict[str, Any],
    *,
    product: ProductProfile,
    output_dir: Path,
    result_dir: Path,
    records: list[dict[str, Any]],
    resume: bool,
    max_cases: int,
    case_ids: list[str] | None,
    started: float,
) -> dict[str, Any]:
    error = f"database not found: {product.db_path}"
    for case in _limited_cases(manifest, max_cases=max_cases, case_ids=case_ids):
        case_id = str(case.get("id") or "").strip()
        if not case_id:
            continue
        language = str(case.get("language") or manifest.get("language") or product.default_language or "").strip()
        grader_id = str(case.get("graderRef") or case_id)
        for variant in _case_variants(case):
            variant_id = str(variant.get("id") or "v1").strip() or "v1"
            query = str(variant.get("query") or "").strip()
            if not query:
                continue
            artifact_id = f"{case_id}__{variant_id}"
            record_path = result_dir / f"{artifact_id}.json"
            if resume and record_path.exists():
                records.append(json.loads(record_path.read_text(encoding="utf-8")))
                continue
            record = _base_record(
                manifest,
                case_id=case_id,
                variant_id=variant_id,
                grader_id=grader_id,
                query=query,
                language=language,
                mode="engine",
            )
            record.update(
                {
                    "error": error,
                    "llmUsed": False,
                    "selectedEvidence": [],
                    "sources": [],
                    "passages": [],
                    "retrievedCases": [],
                    "candidateClaimCards": [],
                    "citedClaimCards": [],
                    "selectorStatus": "skipped_missing_database",
                    "selectionSource": "missing_database",
                    "candidateCount": 0,
                    "selectedCount": 0,
                    "writerStatus": "skipped_missing_database",
                    "writerMode": "",
                }
            )
            record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
            records.append(record)
    return _write_summary(output_dir, manifest=manifest, records=records, mode="engine", started=started)


def _load_public_manifest(path: Path) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("taskType") != "legal_retrieval_answer":
        raise ValueError(f"expected taskType=legal_retrieval_answer: {path}")
    return manifest


def _limited_cases(
    manifest: dict[str, Any],
    *,
    max_cases: int,
    case_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    cases = [case for case in manifest.get("cases", []) if isinstance(case, dict)]
    allowed = {str(case_id) for case_id in case_ids or [] if str(case_id)}
    if allowed:
        cases = [case for case in cases if _case_id_selected(str(case.get("id") or ""), allowed)]
    if max_cases and max_cases > 0:
        return cases[:max_cases]
    return cases


def _case_id_selected(case_id: str, allowed: set[str]) -> bool:
    normalized = str(case_id or "").strip()
    if not normalized:
        return False
    lowered = normalized.lower()
    allowed_lower = {item.strip().lower() for item in allowed if item.strip()}
    if lowered in allowed_lower:
        return True
    return any(
        lowered.endswith(f"{separator}{candidate}")
        for candidate in allowed_lower
        for separator in ("-", "_", ".")
    )


def _case_variants(case: dict[str, Any]) -> list[dict[str, Any]]:
    variants = case.get("variants")
    if isinstance(variants, list) and variants:
        return [variant for variant in variants if isinstance(variant, dict)]
    query = str(case.get("query") or "").strip()
    return [{"id": "v1", "query": query}] if query else []


def _case_candidate_limit(case: dict[str, Any], *, default: int) -> int:
    runtime = case.get("runtime") if isinstance(case.get("runtime"), dict) else {}
    try:
        value = int(runtime.get("candidateLimit") or default)
    except (TypeError, ValueError):
        value = default
    return max(1, value)


def _base_record(
    manifest: dict[str, Any],
    *,
    case_id: str,
    variant_id: str,
    grader_id: str,
    query: str,
    language: str,
    mode: str,
) -> dict[str, Any]:
    return {
        "id": f"{case_id}__{variant_id}",
        "benchmarkId": manifest.get("benchmarkId", ""),
        "taskType": manifest.get("taskType", ""),
        "product": manifest.get("product", ""),
        "mode": mode,
        "caseId": case_id,
        "variantId": variant_id,
        "graderId": grader_id,
        "language": language,
        "query": query,
        "error": "",
    }


def _ranked_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            continue
        row = dict(item)
        row.setdefault("rank", index)
        rows.append(row)
    return rows


def _write_summary(
    output_dir: Path,
    *,
    manifest: dict[str, Any],
    records: list[dict[str, Any]],
    mode: str,
    started: float,
) -> dict[str, Any]:
    total = len(records)
    errors = sum(1 for record in records if record.get("error"))
    predicted = total - errors
    summary = {
        "benchmarkId": manifest.get("benchmarkId", ""),
        "taskType": manifest.get("taskType", ""),
        "product": manifest.get("product", ""),
        "mode": mode,
        "total": {
            "total": total,
            "predicted": predicted,
            "correct": None,
            "errors": errors,
            "accuracy": None,
        },
        "modelMetadata": _summary_model_metadata(records),
        "elapsedSec": round(max(0.0, time.time() - started), 3),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def _context_packet_ids(context_packets: list[Any]) -> list[str]:
    ids: list[str] = []
    for item in context_packets:
        if not isinstance(item, dict):
            continue
        packet_id = str(item.get("packetId") or "").strip()
        if packet_id:
            ids.append(packet_id)
    return ids


def _client_model_metadata(client: Any, *, model: str) -> dict[str, Any]:
    return _model_metadata(
        provider=str(getattr(client, "provider", "custom_llm") or "custom_llm"),
        model=str(model or getattr(client, "default_model", "") or ""),
        decoding=_client_decoding_metadata(client),
    )


def _client_decoding_metadata(client: Any | None) -> dict[str, Any]:
    if client is None:
        return {}
    explicit = getattr(client, "decoding", None)
    if explicit is None:
        explicit = getattr(client, "decoding_config", None)
    if isinstance(explicit, dict):
        return {str(key): value for key, value in sorted(explicit.items()) if value is not None}
    decoding: dict[str, Any] = {}
    for name in ("temperature", "top_p", "top_k", "max_tokens"):
        if hasattr(client, name):
            value = getattr(client, name)
            if value is not None:
                decoding[name] = value
    return decoding


def _model_metadata(*, provider: str, model: str, decoding: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "provider": str(provider or ""),
        "model": str(model or ""),
        "decoding": decoding if isinstance(decoding, dict) else {},
    }


def _summary_model_metadata(records: list[dict[str, Any]]) -> dict[str, Any]:
    values = [
        _normalize_model_metadata(record.get("modelMetadata"))
        for record in records
        if isinstance(record, dict) and isinstance(record.get("modelMetadata"), dict)
    ]
    if not values:
        return {}
    unique = {_stable_model_metadata_key(value) for value in values}
    if len(unique) == 1:
        return values[0]
    providers = sorted({value.get("provider", "") for value in values if value.get("provider")})
    models = sorted({value.get("model", "") for value in values if value.get("model")})
    return {
        "provider": providers[0] if len(providers) == 1 else "",
        "model": models[0] if len(models) == 1 else "",
        "decoding": {},
        "mixed": True,
        "providers": providers,
        "models": models,
    }


def _normalize_model_metadata(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    decoding = value.get("decoding")
    return _model_metadata(
        provider=str(value.get("provider") or ""),
        model=str(value.get("model") or ""),
        decoding=decoding if isinstance(decoding, dict) else {},
    )


def _stable_model_metadata_key(value: dict[str, Any]) -> str:
    return json.dumps(_normalize_model_metadata(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run unified legal retrieval-answer benchmarks.")
    parser.add_argument("--public", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--mode", choices=("engine", "direct"), default="engine")
    parser.add_argument("--db-path", type=Path, default=None)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--analysis-mode", default="fast")
    parser.add_argument("--model", default="", help="Model override for direct mode.")
    parser.add_argument("--max-cases", type=int, default=0)
    parser.add_argument("--case-id", action="append", default=[], help="Run only the matching public case id. Repeatable.")
    args = parser.parse_args()
    products = _profiles_with_legal_defaults()
    if args.db_path is not None:
        manifest = json.loads(args.public.read_text(encoding="utf-8"))
        product_key = str(manifest.get("product") or "").strip()
        if product_key in products:
            products = {**products, product_key: replace(products[product_key], db_path=args.db_path)}
    if args.mode == "direct":
        summary = run_direct_manifest(
            public_path=args.public,
            output_dir=args.output_dir,
            products=products,
            resume=args.resume,
            model=args.model,
            max_cases=args.max_cases,
            case_ids=args.case_id,
        )
    else:
        summary = run_legal_manifest(
            public_path=args.public,
            output_dir=args.output_dir,
            products=products,
            resume=args.resume,
            limit=args.limit,
            analysis_mode=args.analysis_mode,
            max_cases=args.max_cases,
            case_ids=args.case_id,
        )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
