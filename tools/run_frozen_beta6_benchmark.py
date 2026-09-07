#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import subprocess
import sys
import tarfile
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
DEFAULT_BETA6_BASELINE_REF = "45af71ff7bc6efc0ae03727cdb043bcdec82006e"


def build_tasks(
    manifest: dict[str, Any],
    *,
    max_cases: int,
    case_ids: list[str] | None,
) -> list[dict[str, Any]]:
    from tools.run_unified_mcq_benchmark import (
        build_mcq_query,
        build_short_answer_query,
        extract_option_ids,
    )

    task_type = str(manifest.get("taskType") or "")
    cases = _limited_cases(manifest, max_cases=max_cases, case_ids=case_ids)
    tasks: list[dict[str, Any]] = []
    for case in cases:
        case_id = str(case.get("id") or "").strip()
        if not case_id:
            continue
        language = str(case.get("language") or manifest.get("language") or "ko")
        if task_type == "legal_retrieval_answer":
            variants = case.get("variants") if isinstance(case.get("variants"), list) else []
            if not variants and str(case.get("query") or "").strip():
                variants = [{"id": "v1", "query": str(case.get("query") or "").strip()}]
            for variant in variants:
                if not isinstance(variant, dict):
                    continue
                variant_id = str(variant.get("id") or "v1").strip() or "v1"
                query = str(variant.get("query") or "").strip()
                if not query:
                    continue
                tasks.append(
                    {
                        "artifactId": f"{case_id}__{variant_id}",
                        "caseId": case_id,
                        "variantId": variant_id,
                        "graderId": str(case.get("graderRef") or case_id),
                        "query": query,
                        "language": language,
                        "parser": "legal",
                        "optionIds": [],
                    }
                )
            continue
        prompt = str(case.get("prompt") or "")
        if task_type == "short_answer":
            query = build_short_answer_query(prompt, language=language)
            parser = "short_answer"
            option_ids: list[str] = []
        elif task_type == "mcq":
            option_ids = extract_option_ids(
                prompt,
                case.get("options") if isinstance(case.get("options"), list) else None,
            )
            query = build_mcq_query(prompt, language=language, option_ids=option_ids)
            parser = "mcq"
        else:
            raise ValueError(f"unsupported taskType={task_type}")
        tasks.append(
            {
                "artifactId": case_id,
                "caseId": case_id,
                "query": query,
                "language": language,
                "parser": parser,
                "optionIds": option_ids,
            }
        )
    return tasks


def run_manifest(
    *,
    public_path: Path,
    output_dir: Path,
    products: dict[str, Any] | None = None,
    model: str,
    baseline_ref: str = DEFAULT_BETA6_BASELINE_REF,
    baseline_source_root: Path | None = None,
    limit: int = 40,
    analysis_mode: str = "fast",
    resume: bool = False,
    max_cases: int = 0,
    case_ids: list[str] | None = None,
) -> dict[str, Any]:
    manifest = json.loads(public_path.read_text(encoding="utf-8"))
    profiles = products
    if profiles is None:
        from shared_platform.products import PRODUCT_PROFILES
        from tools.run_unified_legal_benchmark import _profiles_with_legal_defaults

        profiles = _profiles_with_legal_defaults(dict(PRODUCT_PROFILES))
    product_key = str(manifest.get("product") or "").strip()
    product = profiles[product_key]
    source_root = baseline_source_root or output_dir.parent / "_frozen_beta6_source"
    baseline = materialize_baseline_source(baseline_ref, source_root)
    plan = {
        "schemaVersion": 1,
        "baseline": baseline,
        "benchmarkId": str(manifest.get("benchmarkId") or ""),
        "taskType": str(manifest.get("taskType") or ""),
        "product": {
            "key": str(product.key),
            "name": str(product.name),
            "dbPath": str(product.db_path),
            "dbShape": str(product.db_shape),
            "languages": list(product.languages),
            "defaultLanguage": str(product.default_language),
            "theme": str(product.theme),
            "safetyNotice": str(product.safety_notice),
        },
        "model": str(model),
        "analysisMode": str(analysis_mode),
        "limit": int(limit),
        "resume": bool(resume),
        "outputDir": str(output_dir),
        "tasks": build_tasks(manifest, max_cases=max_cases, case_ids=case_ids),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    plan_path = output_dir / "frozen_beta6_execution_plan.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--worker-plan", str(plan_path)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    (output_dir / "worker.stdout.log").write_text(completed.stdout, encoding="utf-8")
    (output_dir / "worker.stderr.log").write_text(completed.stderr, encoding="utf-8")
    if completed.returncode != 0:
        raise RuntimeError(f"frozen beta6 worker failed with exit={completed.returncode}: {completed.stderr[-1000:]}")
    return json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))


def materialize_baseline_source(ref: str, target_root: Path) -> dict[str, str]:
    commit = _git_value("rev-parse", f"{ref}^{{commit}}")
    tree = _git_value("rev-parse", f"{ref}^{{tree}}")
    target_root = Path(target_root)
    marker_path = target_root / "BASELINE.json"
    expected = {"sourceRoot": str(target_root), "commit": commit, "tree": tree}
    if (
        marker_path.exists()
        and (target_root / "shared_platform" / "beta6.py").exists()
        and (target_root / "scripts" / "legal_evidence_rag.py").exists()
    ):
        try:
            existing = json.loads(marker_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}
        if existing == expected:
            return expected
    target_root.mkdir(parents=True, exist_ok=True)
    archive = subprocess.run(
        ["git", "archive", "--format=tar", commit, "shared_platform", "scripts"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        check=True,
    ).stdout
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as bundle:
        members = bundle.getmembers()
        for member in members:
            destination = (target_root / member.name).resolve()
            if target_root.resolve() not in destination.parents and destination != target_root.resolve():
                raise RuntimeError(f"unsafe baseline archive member: {member.name}")
        bundle.extractall(target_root, members=members, filter="data")
    marker_path.write_text(json.dumps(expected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return expected


def _git_value(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _run_worker(plan_path: Path) -> int:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    baseline = plan.get("baseline") if isinstance(plan.get("baseline"), dict) else {}
    source_root = Path(str(baseline.get("sourceRoot") or ""))
    if not (source_root / "shared_platform" / "beta6.py").exists():
        raise FileNotFoundError(f"frozen beta6 source missing: {source_root}")
    sys.path.insert(0, str(source_root))
    from shared_platform.beta6 import Beta6JobManager, default_llm_client_from_env
    from shared_platform.products import ProductProfile
    from tools.benchmark_provider import create_benchmark_llm_client

    product_data = plan["product"]
    product = ProductProfile(
        key=str(product_data["key"]),
        name=str(product_data["name"]),
        db_path=Path(str(product_data["dbPath"])),
        db_shape=str(product_data["dbShape"]),
        languages=tuple(str(item) for item in product_data.get("languages") or []),
        default_language=str(product_data.get("defaultLanguage") or ""),
        theme=str(product_data.get("theme") or ""),
        safety_notice=str(product_data.get("safetyNotice") or ""),
    )
    output_dir = Path(str(plan["outputDir"]))
    result_dir = output_dir / "results"
    result_dir.mkdir(parents=True, exist_ok=True)
    model = str(plan.get("model") or "")
    client = create_benchmark_llm_client(
        model=model,
        fallback_factory=default_llm_client_from_env,
    )
    if client is None:
        raise RuntimeError("no LLM client configured in frozen beta6 worker")
    runtime = Beta6JobManager(
        {product.key: product},
        runs_root=output_dir / "beta6_jobs",
        llm_client=client,
        model=model,
        resume_pending_jobs=False,
    )
    records: list[dict[str, Any]] = []
    started = time.time()
    try:
        for task in plan.get("tasks") or []:
            if not isinstance(task, dict):
                continue
            artifact_id = str(task.get("artifactId") or "").strip()
            if not artifact_id:
                continue
            record_path = result_dir / f"{artifact_id}.json"
            if plan.get("resume") and record_path.exists():
                records.append(json.loads(record_path.read_text(encoding="utf-8")))
                continue
            record = {
                "id": artifact_id,
                "caseId": str(task.get("caseId") or artifact_id),
                "variantId": str(task.get("variantId") or ""),
                "graderId": str(task.get("graderId") or task.get("caseId") or artifact_id),
                "benchmarkId": str(plan.get("benchmarkId") or ""),
                "taskType": str(plan.get("taskType") or ""),
                "product": product.key,
                "mode": "beta6",
                "query": str(task.get("query") or ""),
                "prediction": None,
                "error": "",
                "baseline": {"commit": str(baseline.get("commit") or ""), "tree": str(baseline.get("tree") or "")},
            }
            try:
                result = runtime.answer_sync(
                    product=product.key,
                    query=record["query"],
                    language=str(task.get("language") or product.default_language),
                    limit=int(plan.get("limit") or 40),
                    analysis_mode=str(plan.get("analysisMode") or "fast"),
                )
                record.update(_worker_result_fields(result, client=client, model=model))
                record["prediction"] = _parse_prediction(
                    str(record.get("answer") or ""),
                    parser=str(task.get("parser") or ""),
                    option_ids=[str(item) for item in task.get("optionIds") or []],
                )
            except Exception as exc:  # noqa: BLE001
                record["error"] = str(exc)
            record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            records.append(record)
    finally:
        runtime.shutdown(wait=False)
    summary = {
        "benchmarkId": str(plan.get("benchmarkId") or ""),
        "taskType": str(plan.get("taskType") or ""),
        "product": product.key,
        "mode": "beta6",
        "baseline": {"commit": str(baseline.get("commit") or ""), "tree": str(baseline.get("tree") or "")},
        "total": {
            "total": len(records),
            "predicted": sum(1 for item in records if item.get("prediction")),
            "errors": sum(1 for item in records if item.get("error")),
        },
        "modelMetadata": _common_model_metadata(records),
        "elapsedSec": round(max(0.0, time.time() - started), 3),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0


def _worker_result_fields(result: dict[str, Any], *, client: Any, model: str) -> dict[str, Any]:
    answer = str(result.get("answer") or result.get("answerMarkdown") or "")
    beta6 = result.get("beta6") if isinstance(result.get("beta6"), dict) else {}
    selector = result.get("selector") if isinstance(result.get("selector"), dict) else {}
    writer = result.get("writer") if isinstance(result.get("writer"), dict) else {}
    evidence = [dict(item) for item in result.get("selectedEvidence") or [] if isinstance(item, dict)]
    sources = [dict(item) for item in result.get("sources") or [] if isinstance(item, dict)]
    retrieved = [dict(item) for item in result.get("beta6SelectedRecords") or [] if isinstance(item, dict)]
    cited = [dict(item) for item in result.get("citedClaimCards") or [] if isinstance(item, dict)]
    packets = [dict(item) for item in result.get("contextPackets") or [] if isinstance(item, dict)]
    selected_ids = [_source_id(item) for item in evidence or retrieved if _source_id(item)]
    candidate_ids = [str(item) for item in selector.get("candidateIds") or [] if str(item)]
    return {
        "answer": answer,
        "answerMarkdown": str(result.get("answerMarkdown") or answer),
        "answerPreview": answer[:1200],
        "answerReadiness": str(result.get("answerReadiness") or ""),
        "selectedEvidence": evidence,
        "selectedEvidenceIds": selected_ids,
        "sources": sources,
        "retrievedCases": retrieved,
        "citedClaimCards": cited,
        "citedClaimCount": len(cited),
        "contextPackets": packets,
        "contextPacketCount": len(packets),
        "contextPacketIds": [str(item.get("packetId") or "") for item in packets if item.get("packetId")],
        "selectorStatus": str(beta6.get("selectorStatus", selector.get("status", "")) or ""),
        "selectionSource": str(beta6.get("selectionSource", selector.get("selectionSource", "")) or ""),
        "candidateCount": int(beta6.get("candidateCount", selector.get("candidateCount", 0)) or 0),
        "candidateIds": candidate_ids,
        "candidateSetDigest": str(selector.get("candidateSetDigest") or _candidate_digest(candidate_ids)),
        "selectedCount": int(beta6.get("selectedCount", len(evidence or retrieved)) or 0),
        "writerStatus": str(beta6.get("writerStatus", writer.get("status", "")) or ""),
        "writerMode": str(writer.get("mode") or ""),
        "modelMetadata": _worker_model_metadata(client, writer=writer, beta6=beta6, model=model),
        "llmUsed": bool(result.get("llmUsed")),
    }


def _source_id(item: dict[str, Any]) -> str:
    return str(item.get("sourceId") or item.get("file_id") or item.get("canonical_id") or item.get("id") or "").strip()


def _candidate_digest(ids: list[str]) -> str:
    encoded = json.dumps(ids, ensure_ascii=False, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"


def _worker_model_metadata(client: Any, *, writer: dict[str, Any], beta6: dict[str, Any], model: str) -> dict[str, Any]:
    decoding = getattr(client, "decoding", None)
    if not isinstance(decoding, dict):
        decoding = {}
        for name in ("temperature", "top_p", "top_k", "max_tokens", "thinking_level"):
            if hasattr(client, name):
                value = getattr(client, name)
                if value not in (None, ""):
                    decoding[name] = value
    return {
        "provider": str(beta6.get("writerProvider") or writer.get("provider") or getattr(client, "provider", "custom_llm")),
        "model": str(beta6.get("writerModel") or writer.get("model") or model or getattr(client, "default_model", "")),
        "decoding": {str(key): value for key, value in sorted(decoding.items())},
    }


def _parse_prediction(answer: str, *, parser: str, option_ids: list[str]) -> str | None:
    text = str(answer or "").strip()
    if parser == "legal":
        return text or None
    if parser == "short_answer":
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict) and isinstance(payload.get("finalAnswer"), str):
            return payload["finalAnswer"]
        match = re.search(r"(?:finalAnswer|정답|답|answer)\s*[:：]\s*(.+)", text, re.IGNORECASE)
        return match.group(1).strip() if match else None
    match = re.search(r"(?:정답|답|answer|correct\s+answer)\s*[:：]?\s*([A-Za-z]|\d{1,2}|[①②③④⑤])", text, re.IGNORECASE)
    if not match:
        return None
    value = {"①": "1", "②": "2", "③": "3", "④": "4", "⑤": "5"}.get(match.group(1), match.group(1).upper())
    allowed = {str(item).upper() for item in option_ids}
    return value if not allowed or value in allowed else None


def _common_model_metadata(records: list[dict[str, Any]]) -> dict[str, Any]:
    values = [item.get("modelMetadata") for item in records if isinstance(item.get("modelMetadata"), dict)]
    return values[0] if values and all(value == values[0] for value in values) else {}


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
    return cases[:max_cases] if max_cases > 0 else cases


def main() -> int:
    if "--worker-plan" in sys.argv:
        index = sys.argv.index("--worker-plan")
        return _run_worker(Path(sys.argv[index + 1]))
    parser = argparse.ArgumentParser(description="Run a public manifest with a frozen beta6 source revision.")
    parser.add_argument("--public", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--db-path", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--baseline-ref", default=DEFAULT_BETA6_BASELINE_REF)
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--analysis-mode", default="fast")
    parser.add_argument("--max-cases", type=int, default=0)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    manifest = json.loads(args.public.read_text(encoding="utf-8"))
    from shared_platform.products import ProductProfile

    key = str(manifest.get("product") or "")
    profile = ProductProfile(
        key=key,
        name=key,
        db_path=args.db_path,
        db_shape="documents" if key == "simli" else "precedents",
        languages=(str(manifest.get("language") or "ko"),),
        default_language=str(manifest.get("language") or "ko"),
        theme="benchmark",
        safety_notice="benchmark",
    )
    report = run_manifest(
        public_path=args.public,
        output_dir=args.output_dir,
        products={key: profile},
        model=args.model,
        baseline_ref=args.baseline_ref,
        limit=args.limit,
        analysis_mode=args.analysis_mode,
        max_cases=args.max_cases,
        case_ids=args.case_id,
        resume=args.resume,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
