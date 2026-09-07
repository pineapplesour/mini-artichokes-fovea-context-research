#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared_platform.beta6 import (
    default_llm_client_from_env,
    fill_selected_rows,
    local_fallback_select_rows,
    select_rows_with_beta6_llm,
    select_rows_with_beta6_selector,
)
from shared_platform.domain_adapters import get_domain_adapter
from shared_platform.products import PRODUCT_PROFILES, ProductProfile
from shared_platform.search import SearchResult
from tools import score_unified_benchmarks
from tools.run_unified_mcq_benchmark import build_mcq_query, case_option_ids


ABLATION_FILENAME = "selector_ablation.raw_vs_context_packets_v1.json"


def run_selector_ablation_manifest(
    *,
    public_path: Path,
    private_path: Path,
    output_dir: Path,
    products: dict[str, ProductProfile] | None = None,
    llm_client: Any | None = None,
    model: str = "",
    limit: int = 50,
    analysis_mode: str = "fast",
    max_cases: int = 0,
    case_ids: list[str] | None = None,
) -> dict[str, Any]:
    started = time.time()
    manifest = _load_public_manifest(public_path)
    private = _load_json(private_path) if private_path.exists() else {}
    profiles = products or PRODUCT_PROFILES
    product_key = str(manifest.get("product") or "").strip()
    product = profiles[product_key]
    client = llm_client if llm_client is not None else default_llm_client_from_env()
    if client is None:
        raise RuntimeError("no LLM client configured")
    cases = []
    for item in _case_queries(manifest, product, max_cases=max_cases, case_ids=case_ids):
        raw_arm, shared_candidates = _run_arm(
            arm_id="raw",
            product=product,
            query=item["query"],
            language=item["language"],
            limit=limit,
            llm_client=client,
            model=model,
            cache_root=output_dir / "_selector_ablation_cache" / item["caseId"] / "raw",
            fast_mode=analysis_mode == "fast",
            private_manifest=private,
            case_id=item["scoreCaseId"],
        )
        context_arm, _context_candidates = _run_arm(
            arm_id="context_packets_v1",
            product=product,
            query=item["query"],
            language=item["language"],
            limit=limit,
            llm_client=client,
            model=model,
            cache_root=output_dir / "_selector_ablation_cache" / item["caseId"] / "context_packets_v1",
            fast_mode=analysis_mode == "fast",
            private_manifest=private,
            case_id=item["scoreCaseId"],
            shared_candidate_rows=shared_candidates,
        )
        arms = {"raw": raw_arm, "context_packets_v1": context_arm}
        cases.append(
            {
                "caseId": item["caseId"],
                "scoreCaseId": item["scoreCaseId"],
                "benchmarkId": str(manifest.get("benchmarkId") or ""),
                "taskType": str(manifest.get("taskType") or ""),
                "product": product.key,
                "language": item["language"],
                "arms": arms,
            }
        )
    report = {
        "schemaVersion": "selector_ablation_v1",
        "ablationId": "raw_vs_context_packets_v1",
        "promotionPolicyVersion": "context_packet_retrieval_promotion_v1",
        "stopAfter": "selector",
        "writerEnabled": False,
        "arms": ["raw", "context_packets_v1"],
        "suite": {
            "caseCount": len(cases),
            "pairedCaseCount": len(cases),
            "targetManifestDigest": _json_digest(_private_target_payload(private)) if private else "",
            "targetManifestLocked": bool(private),
            "targetsVisibleToEngine": False,
        },
        "benchmarkId": str(manifest.get("benchmarkId") or ""),
        "taskType": str(manifest.get("taskType") or ""),
        "product": product.key,
        "cases": cases,
        "elapsedSec": round(max(0.0, time.time() - started), 3),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / ABLATION_FILENAME).write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def _run_arm(
    *,
    arm_id: str,
    product: ProductProfile,
    query: str,
    language: str,
    limit: int,
    llm_client: Any,
    model: str,
    cache_root: Path,
    fast_mode: bool,
    private_manifest: dict[str, Any],
    case_id: str,
    shared_candidate_rows: list[SearchResult] | None = None,
) -> tuple[dict[str, Any], list[SearchResult]]:
    with _selector_mode_env(arm_id):
        if shared_candidate_rows is None:
            rows, selector = select_rows_with_beta6_llm(
                product,
                query,
                language,
                limit=limit,
                llm_client=llm_client,
                model=model,
                provider=str(getattr(llm_client, "provider", "custom_llm") or "custom_llm"),
                cache_root=cache_root,
                fast_mode=fast_mode,
                include_candidate_rows=True,
            )
        else:
            rows, selector = _select_from_shared_candidate_rows(
                arm_id=arm_id,
                product=product,
                query=query,
                language=language,
                candidate_rows=shared_candidate_rows,
                limit=limit,
                llm_client=llm_client,
                model=model,
                cache_root=cache_root,
            )
    candidate_rows = _candidate_rows_from_selector(selector, rows)
    selector_status = str(selector.get("status") or "completed")
    selector_fallback = selector_status != "completed"
    filled_ids = [row.canonical_id for row in rows if row.canonical_id]
    raw_selected_ids = _selector_raw_selected_ids(selector)
    selected_ids = raw_selected_ids if raw_selected_ids or selector_fallback else filled_ids
    selected_rows = _rows_for_ids(rows, selected_ids)
    context_packets = selector.get("selectorContextPackets") if isinstance(selector.get("selectorContextPackets"), list) else []
    target_eval = _target_eval(private_manifest, case_id, [] if selector_fallback else selected_rows)
    arm = {
        "armId": arm_id,
        "status": selector_status,
        "selectorInputMode": arm_id,
        "runtimeSelectorInputMode": str(selector.get("selectorInputMode") or ""),
        "contextPacketsEnabled": arm_id == "context_packets_v1",
        "contextPacketCount": int(selector.get("selectorContextPacketCount") or 0),
        "contextPacketProvenanceCount": _context_packet_provenance_count(context_packets),
        "selectorProvider": str(selector.get("provider") or getattr(llm_client, "provider", "custom_llm") or "custom_llm"),
        "selectorModel": str(selector.get("model") or model or getattr(llm_client, "default_model", "") or ""),
        "selectorDecoding": _client_decoding_metadata(llm_client),
        "candidateCount": int(selector.get("candidateCount") or 0),
        "candidateIds": selector.get("candidateIds", []),
        "candidateSetDigest": str(selector.get("candidateSetDigest") or ""),
        "selectorFallback": selector_fallback,
        "directWriterFallback": False,
        "writerRan": False,
        "answerQualityScorePresent": False,
        "selectedEvidenceCount": len(selected_ids),
        "selectedEvidenceIds": selected_ids,
        "filledEvidenceCount": len(filled_ids),
        "filledEvidenceIds": filled_ids,
        "selectedBackingEvidenceIds": selected_ids,
        "selectedSourceIds": selected_ids,
    }
    if target_eval:
        arm["targetEval"] = target_eval
    if shared_candidate_rows is not None:
        arm["candidateReuseSource"] = "raw_candidate_universe"
    return arm, candidate_rows


def _select_from_shared_candidate_rows(
    *,
    arm_id: str,
    product: ProductProfile,
    query: str,
    language: str,
    candidate_rows: list[SearchResult],
    limit: int,
    llm_client: Any,
    model: str,
    cache_root: Path,
) -> tuple[list[SearchResult], dict[str, Any]]:
    selector_limit = min(max(1, int(limit or 1)), len(candidate_rows)) if candidate_rows else 1
    selected_rows, selected_ids, reasoning, selector_meta = select_rows_with_beta6_selector(
        product,
        query,
        language,
        candidate_rows,
        limit=selector_limit,
        llm_client=llm_client,
        model=model,
        cache_root=cache_root,
    )
    selector_local_recovery = int(selector_meta.get("selectorLocalRecoveryCount") or 0) > 0
    if selected_rows:
        rows = fill_selected_rows(candidate_rows, selected_rows, limit=selector_limit)
        rows = get_domain_adapter(product).postprocess_selected_rows(
            query,
            candidate_rows,
            rows,
            limit=selector_limit,
        )
        status = "fallback_selector_error" if selector_local_recovery else "completed"
        selection_source = "local_rerank_after_selector_error" if selector_local_recovery else selector_meta.get("selectionSource") or "gemma4_llm_selector"
        message = (
            "Gemma 4 selector timed out for at least one batch; deterministic beta6 local recovery filled that batch."
            if selector_local_recovery
            else "Gemma 4 selected source records from the raw arm candidate universe."
        )
    else:
        rows = local_fallback_select_rows(product, candidate_rows, limit=selector_limit, query=query)
        status = "fallback_no_selection"
        selection_source = "local_rerank_after_empty_llm_selection"
        message = "Gemma 4 selector returned no valid ids, so the ablation used the raw arm candidate order."
    selector = {
        "status": status,
        "mode": selector_meta.get("mode") or "llm_selector_shared_candidate_universe",
        "provider": str(getattr(llm_client, "provider", "custom_llm") or "custom_llm"),
        "model": model or str(getattr(llm_client, "default_model", "") or ""),
        "selectionSource": selection_source,
        **selector_meta,
        "candidateCount": len(candidate_rows),
        "topK": selector_limit,
        "selectedIds": [row.canonical_id for row in rows if row.canonical_id],
        "rawSelectedIds": selected_ids,
        "selectorRawSelectedIds": selected_ids,
        "reasoning": reasoning,
        "message": message,
        "_candidateRows": candidate_rows,
        "candidateReuseSource": "raw_candidate_universe",
    }
    return rows, selector


def _candidate_rows_from_selector(selector: dict[str, Any], fallback_rows: list[SearchResult]) -> list[SearchResult]:
    value = selector.get("_candidateRows")
    if isinstance(value, list) and all(isinstance(item, SearchResult) for item in value):
        return value
    candidate_ids = _unique_nonempty_strings(selector.get("candidateIds", [])) if isinstance(selector.get("candidateIds"), list) else []
    rows = _rows_for_ids(fallback_rows, candidate_ids)
    return rows or list(fallback_rows)


def _selector_raw_selected_ids(selector: dict[str, Any]) -> list[str]:
    value = selector.get("selectorRawSelectedIds")
    if not isinstance(value, list):
        return []
    return _unique_nonempty_strings(value)


def _rows_for_ids(rows: list[SearchResult], selected_ids: list[str]) -> list[SearchResult]:
    by_id = {row.canonical_id: row for row in rows if row.canonical_id}
    out: list[SearchResult] = []
    seen: set[str] = set()
    for selected_id in selected_ids:
        row = by_id.get(selected_id)
        if row is None or row.canonical_id in seen:
            continue
        seen.add(row.canonical_id)
        out.append(row)
    return out


def _target_eval(private_manifest: dict[str, Any], case_id: str, rows: list[SearchResult]) -> dict[str, Any]:
    if not private_manifest:
        return {}
    target_spec = _target_spec_for_case(private_manifest, case_id)
    if not target_spec:
        return {}
    targets = [target for target in target_spec.get("targets", []) if isinstance(target, dict)]
    if not targets:
        return {}
    artifact = {
        "caseId": case_id,
        "graderId": case_id,
        "prediction": "",
        "selectedEvidence": _selected_evidence_records(rows),
    }
    matches = score_unified_benchmarks._target_rank_matches(targets, artifact)
    rank_limit = _target_rank_limit(target_spec.get("rankRules"), artifact)
    target_units = _target_eval_units(case_id, targets, target_spec)
    covered_indices = {
        index
        for index, (rank, _record) in matches.items()
        if rank_limit <= 0 or rank <= rank_limit
    }
    covered_ids = [
        unit["id"]
        for unit in target_units
        if any(index in covered_indices for index in unit["targetIndices"])
    ]
    target_ids = [unit["id"] for unit in target_units]
    failures = _retrieval_failures(target_spec, artifact)
    return {
        "targetSpecPresent": True,
        "targetHitSource": "selected_backing_evidence_only",
        "pass": not failures,
        "score": (len(covered_ids) / len(target_ids)) if target_ids else 0.0,
        "targetIds": target_ids,
        "coveredTargetIds": covered_ids,
        "missedTargetIds": [target_id for target_id in target_ids if target_id not in covered_ids],
        "targetsTotal": len(target_ids),
        "targetsPassed": len(covered_ids),
        "retrievalFailures": failures,
    }


def _target_eval_units(case_id: str, targets: list[dict[str, Any]], target_spec: dict[str, Any]) -> list[dict[str, Any]]:
    rank_rules = target_spec.get("rankRules") if isinstance(target_spec.get("rankRules"), dict) else {}
    required_count = rank_rules.get("atLeastTargetsWithinTopK")
    must_match_all = bool(rank_rules.get("mustMatchAllTargets"))
    default_mcq_alternatives = (
        target_spec.get("kind") == "mcq"
        and not must_match_all
        and (required_count is None or int(required_count) <= 1)
    )
    if default_mcq_alternatives and len(targets) > 1:
        digest = hashlib.sha256(
            json.dumps(targets, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:16]
        return [{"id": f"{case_id}:target-group:1:{digest}", "targetIndices": list(range(len(targets)))}]
    return [
        {"id": _target_id(case_id, index, target), "targetIndices": [index]}
        for index, target in enumerate(targets)
    ]


def _target_spec_for_case(private_manifest: dict[str, Any], case_id: str) -> dict[str, Any]:
    if private_manifest.get("graders"):
        for grader in private_manifest.get("graders", []) or []:
            if not isinstance(grader, dict):
                continue
            grader_id = str(grader.get("graderId") or "")
            if not score_unified_benchmarks._case_id_selected(grader_id, {case_id}):
                continue
            return {
                "kind": "legal",
                "source": grader,
                "targets": [target for target in grader.get("primaryTargets", []) if isinstance(target, dict)],
                "rankRules": grader.get("rankRules") if isinstance(grader.get("rankRules"), dict) else {},
            }
        return {}
    answer_items = [
        item
        for item in private_manifest.get("answers", [])
        if isinstance(item, dict) and item.get("caseId")
    ]
    retrieval_targets = score_unified_benchmarks._mcq_retrieval_targets_by_case(private_manifest, answer_items)
    for target_case_id, entry in retrieval_targets.items():
        if not score_unified_benchmarks._case_id_selected(str(target_case_id), {case_id}):
            continue
        return {
            "kind": "mcq",
            "source": entry,
            "targets": [target for target in entry.get("targets", []) if isinstance(target, dict)],
            "rankRules": entry.get("rankRules") if isinstance(entry.get("rankRules"), dict) else {},
        }
    return {}


def _selected_evidence_records(rows: list[SearchResult]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        records.append(
            {
                "rank": index,
                "sourceId": row.canonical_id,
                "id": row.canonical_id,
                "title": row.title,
                "citation": row.citation,
                "caseNumber": row.citation,
                "text": row.full_text,
                "fullText": row.full_text,
            }
        )
    return records


def _target_rank_limit(rank_rules: Any, artifact: dict[str, Any]) -> int:
    rules = rank_rules if isinstance(rank_rules, dict) else {}
    for key in ("targetTopK", "candidateLimit", "primaryMustAppearWithin"):
        value = rules.get(key)
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                return 0
    ranks = [
        int(record.get("rank") or index)
        for index, record in enumerate(artifact.get("selectedEvidence") or [], start=1)
        if isinstance(record, dict)
    ]
    return max(ranks or [50])


def _retrieval_failures(target_spec: dict[str, Any], artifact: dict[str, Any]) -> list[str]:
    if target_spec.get("kind") == "legal":
        return score_unified_benchmarks._legal_retrieval_failures(target_spec.get("source") or {}, artifact)
    return score_unified_benchmarks._mcq_retrieval_failures(target_spec.get("source"), artifact)


def _target_id(case_id: str, index: int, target: dict[str, Any]) -> str:
    digest = hashlib.sha256(
        json.dumps(target, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:16]
    return f"{case_id}:target:{index + 1}:{digest}"


def _private_target_payload(private_manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "benchmarkId": private_manifest.get("benchmarkId", ""),
        "taskType": private_manifest.get("taskType", ""),
        "answers": private_manifest.get("answers", []),
        "retrievalTargets": private_manifest.get("retrievalTargets", []),
        "graders": private_manifest.get("graders", []),
    }


def _json_digest(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _case_queries(
    manifest: dict[str, Any],
    product: ProductProfile,
    *,
    max_cases: int,
    case_ids: list[str] | None,
) -> list[dict[str, str]]:
    task_type = str(manifest.get("taskType") or "")
    language_default = str(manifest.get("language") or product.default_language or "ko")
    cases = [case for case in manifest.get("cases", []) if isinstance(case, dict)]
    allowed = {str(case_id) for case_id in case_ids or [] if str(case_id)}
    if allowed:
        cases = [case for case in cases if _case_id_selected(str(case.get("id") or ""), allowed)]
    if max_cases and max_cases > 0:
        cases = cases[:max_cases]
    out: list[dict[str, str]] = []
    for case in cases:
        case_id = str(case.get("id") or "").strip()
        if not case_id:
            continue
        language = str(case.get("language") or language_default)
        if task_type == "mcq":
            option_ids = case_option_ids(case, product)
            out.append(
                {
                    "caseId": case_id,
                    "scoreCaseId": case_id,
                    "language": language,
                    "query": build_mcq_query(str(case.get("prompt") or ""), language=language, option_ids=option_ids),
                }
            )
        elif task_type == "legal_retrieval_answer":
            for variant in case.get("variants", []) or []:
                if not isinstance(variant, dict):
                    continue
                variant_id = str(variant.get("id") or "v1").strip() or "v1"
                query = str(variant.get("query") or "").strip()
                if query:
                    out.append(
                        {
                            "caseId": f"{case_id}__{variant_id}",
                            "scoreCaseId": str(case.get("graderRef") or case_id),
                            "language": language,
                            "query": query,
                        }
                    )
    return out


@contextmanager
def _selector_mode_env(arm_id: str):
    previous = os.environ.get("RELIGION_SELECTOR_EVIDENCE_CAPSULES")
    if arm_id == "context_packets_v1":
        os.environ["RELIGION_SELECTOR_EVIDENCE_CAPSULES"] = "1"
    else:
        os.environ.pop("RELIGION_SELECTOR_EVIDENCE_CAPSULES", None)
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("RELIGION_SELECTOR_EVIDENCE_CAPSULES", None)
        else:
            os.environ["RELIGION_SELECTOR_EVIDENCE_CAPSULES"] = previous


def _context_packet_provenance_count(context_packets: list[Any]) -> int:
    count = 0
    for packet in context_packets:
        if not isinstance(packet, dict):
            continue
        if packet.get("sourceId") or packet.get("fileId"):
            count += 1
    return count


def _client_decoding_metadata(client: Any) -> dict[str, Any]:
    explicit = getattr(client, "decoding", None)
    if explicit is None:
        explicit = getattr(client, "decoding_config", None)
    if isinstance(explicit, dict):
        return {str(key): value for key, value in sorted(explicit.items()) if value is not None}
    return {}


def _unique_nonempty_strings(values: list[Any]) -> list[str]:
    out: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in out:
            out.append(text)
    return out


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


def _load_public_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a raw-vs-context-packet selector-only ablation manifest.")
    parser.add_argument("--public", type=Path, required=True)
    parser.add_argument("--private", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--product", default="", help="Override manifest product key.")
    parser.add_argument("--db-path", type=Path, default=None, help="Override DB path for the selected product.")
    parser.add_argument("--model", default="")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--analysis-mode", default="fast")
    parser.add_argument("--max-cases", type=int, default=0)
    parser.add_argument("--case-id", action="append", default=[])
    args = parser.parse_args()

    manifest = _load_public_manifest(args.public)
    product_key = str(args.product or manifest.get("product") or "").strip()
    if product_key not in PRODUCT_PROFILES:
        print(json.dumps({"status": "blocked", "reason": "unknown_product", "product": product_key}, ensure_ascii=False, indent=2))
        return 2
    product = PRODUCT_PROFILES[product_key]
    if args.db_path is not None:
        product = ProductProfile(
            key=product.key,
            name=product.name,
            db_path=args.db_path.resolve(),
            db_shape=product.db_shape,
            languages=product.languages,
            default_language=product.default_language,
            theme=product.theme,
            safety_notice=product.safety_notice,
        )
    products = dict(PRODUCT_PROFILES)
    products[product_key] = product
    if args.product:
        manifest["product"] = product_key
        effective_public = args.output_dir / "_public.effective.json"
        effective_public.parent.mkdir(parents=True, exist_ok=True)
        effective_public.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        public_path = effective_public
    else:
        public_path = args.public
    report = run_selector_ablation_manifest(
        public_path=public_path,
        private_path=args.private,
        output_dir=args.output_dir,
        products=products,
        model=args.model,
        limit=args.limit,
        analysis_mode=args.analysis_mode,
        max_cases=args.max_cases,
        case_ids=args.case_id,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
