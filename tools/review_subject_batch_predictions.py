#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.codex_home_failover import CodexHomeFailoverClient, load_unique_homes, resolve_codex_home_paths
from tools.prompt_identity import canonical_json_sha256, prompt_identity, text_sha256
from tools.resource_gate import collect_resource_snapshot
from tools.run_open_response_benchmark import PUBLIC_PRODUCT_LABELS
from tools.score_open_responses import _audit_closed_judge_trace


MODE = "codex_native_subject_batch_independent_review_v1"
BUILDER_ID = "subject_batch_independent_review_query_v1"
MAX_REVIEW_CASES = 8
MAX_REVIEW_TOKENS = 40_000
MAX_REALTIME_SECONDS = 600.0


def build_review_query(*, manifest: dict[str, Any], rows: list[dict[str, str]]) -> str:
    if not 1 <= len(rows) <= MAX_REVIEW_CASES:
        raise ValueError(f"review batch requires 1 to {MAX_REVIEW_CASES} cases")
    product = str(manifest.get("product") or "").strip().lower()
    labels = PUBLIC_PRODUCT_LABELS.get(product, {})
    domain = str(labels.get("en") or labels.get("ko") or product)
    payload = [
        {"id": str(row["id"]), "question": str(row["question"]), "draftAnswer": str(row["draftAnswer"])}
        for row in rows
    ]
    return (
        f"You are an independent final-answer reviewer for the public subject {domain}. You have no answer key or choices. "
        "Independently solve each question from your own knowledge before comparing it with the draft. Keep a draft only when "
        "its subject, object, polarity, quantity, condition, and standard terminology are correct. Correct it when you can state "
        "a concrete better answer; do not change wording merely for style. Judge every item independently and do not infer one "
        "answer from another. Return exactly one JSON object with only the key reviews. Preserve input order and every id exactly "
        "once. Each row must contain exactly id, verdict (keep or correct), finalAnswer (nonempty concise string), and issue "
        "(short string; empty only for keep). For keep, finalAnswer must exactly equal draftAnswer.\n\n"
        f"PUBLIC_DRAFT_BATCH_JSON:\n{json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}"
    )


def parse_review_response(
    raw: str,
    *,
    expected_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    try:
        payload = json.loads(str(raw or "").strip())
    except json.JSONDecodeError as exc:
        raise ValueError("invalid_subject_batch_review_json") from exc
    if not isinstance(payload, dict) or set(payload) != {"reviews"} or not isinstance(payload["reviews"], list):
        raise ValueError("invalid_subject_batch_review_schema")
    expected_ids = [str(row["id"]) for row in expected_rows]
    drafts = {str(row["id"]): str(row["draftAnswer"]) for row in expected_rows}
    reviews: list[dict[str, str]] = []
    for row in payload["reviews"]:
        if not isinstance(row, dict) or set(row) != {"id", "verdict", "finalAnswer", "issue"}:
            raise ValueError("invalid_subject_batch_review_row")
        case_id = str(row.get("id") or "").strip()
        verdict = str(row.get("verdict") or "").strip()
        final_answer = str(row.get("finalAnswer") or "").strip()
        issue = str(row.get("issue") or "").strip()
        if verdict not in {"keep", "correct"} or not final_answer or len(final_answer) > 4_000:
            raise ValueError("invalid_subject_batch_review_value")
        if verdict == "keep" and final_answer != drafts.get(case_id):
            raise ValueError("kept_subject_batch_answer_changed")
        if verdict == "correct" and (final_answer == drafts.get(case_id) or not issue):
            raise ValueError("subject_batch_correction_not_substantive")
        reviews.append({"id": case_id, "verdict": verdict, "finalAnswer": final_answer, "issue": issue[:500]})
    if [row["id"] for row in reviews] != expected_ids:
        raise ValueError("subject_batch_review_ids_do_not_match")
    return reviews


def run_independent_review(
    *,
    public_path: Path,
    draft_results_dir: Path,
    output_dir: Path,
    llm_client: Any,
    model: str,
    case_ids: list[str],
    maximum_tokens: int = MAX_REVIEW_TOKENS,
    resource_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    manifest = json.loads(public_path.read_text(encoding="utf-8"))
    public_by_id = {
        str(case.get("id") or ""): case
        for case in manifest.get("cases", [])
        if isinstance(case, dict) and case.get("id")
    }
    ordered_ids = [str(value) for value in case_ids if str(value)]
    if not 1 <= len(ordered_ids) <= MAX_REVIEW_CASES or len(set(ordered_ids)) != len(ordered_ids):
        raise ValueError(f"review requires 1 to {MAX_REVIEW_CASES} unique case ids")
    rows: list[dict[str, str]] = []
    draft_artifacts: dict[str, dict[str, Any]] = {}
    draft_batch_ids: set[str] = set()
    for case_id in ordered_ids:
        if case_id not in public_by_id:
            raise ValueError(f"unknown public case id: {case_id}")
        path = draft_results_dir / f"{case_id}.json"
        artifact = json.loads(path.read_text(encoding="utf-8"))
        if str(artifact.get("error") or "").strip() or not str(artifact.get("prediction") or "").strip():
            raise ValueError(f"draft artifact is not reviewable: {case_id}")
        draft_artifacts[case_id] = artifact
        draft_batch_ids.add(str(artifact.get("batchId") or ""))
        rows.append(
            {
                "id": case_id,
                "question": str(public_by_id[case_id].get("prompt") or ""),
                "draftAnswer": str(artifact.get("prediction") or ""),
            }
        )
    if len(draft_batch_ids) != 1 or "" in draft_batch_ids:
        raise ValueError("all review cases must come from one bound draft batch")
    query = build_review_query(manifest=manifest, rows=rows)
    started = time.monotonic()
    raw = ""
    trace: dict[str, Any] = {}
    reviews: list[dict[str, str]] = []
    error = ""
    try:
        raw = str(llm_client.complete([{"role": "user", "content": query}], model=model) or "")
        reviews = parse_review_response(raw, expected_rows=rows)
    except Exception as exc:
        error = str(exc)[:1_000]
    consume = getattr(llm_client, "consume_last_call_trace", None)
    trace_value = consume() if callable(consume) else None
    trace = trace_value if isinstance(trace_value, dict) else {}
    trace_audit = _audit_closed_judge_trace(trace)
    usage = trace.get("tokenUsage") if isinstance(trace.get("tokenUsage"), dict) else {}
    total_tokens = int(usage.get("totalTokens") or 0)
    if not trace_audit["passed"] and not error:
        error = "independent_review_closed_tool_trace_failed"
    if total_tokens > int(maximum_tokens) and not error:
        error = "independent_review_token_budget_exceeded"
    elapsed = round(time.monotonic() - started, 3)
    if elapsed > MAX_REALTIME_SECONDS and not error:
        error = "independent_review_realtime_budget_exceeded"
    receipt: dict[str, Any] = {
        "schemaVersion": 1,
        "mode": MODE,
        "benchmarkId": manifest.get("benchmarkId", ""),
        "sourceBenchmarkId": manifest.get("sourceBenchmarkId", ""),
        "model": model,
        "draftBatchId": next(iter(draft_batch_ids)),
        "caseIds": ordered_ids,
        "reviewModelInputSha256": text_sha256(query),
        "draftRowsSha256": canonical_json_sha256(rows),
        "rawPreview": raw[:8_000],
        "reviews": reviews,
        "modelTrace": trace,
        "closedToolTraceAudit": trace_audit,
        "maximumTokens": int(maximum_tokens),
        "error": error,
        "elapsedSec": elapsed,
    }
    receipt["receiptPayloadSha256"] = canonical_json_sha256(receipt)
    output_dir.mkdir(parents=True, exist_ok=True)
    result_dir = output_dir / "results"
    result_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "review-receipt.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    review_by_id = {row["id"]: row for row in reviews}
    records: list[dict[str, Any]] = []
    for row in rows:
        case_id = row["id"]
        review = review_by_id.get(case_id, {})
        prediction = str(review.get("finalAnswer") or "") or None
        record = {
            "id": case_id,
            "caseId": case_id,
            "benchmarkId": manifest.get("benchmarkId", ""),
            "sourceBenchmarkId": manifest.get("sourceBenchmarkId", ""),
            "mode": MODE,
            "model": model,
            "prediction": prediction,
            "gold": None,
            "correct": None,
            "originalPrediction": row["draftAnswer"],
            "reviewVerdict": review.get("verdict"),
            "reviewIssue": review.get("issue", ""),
            "draftBatchId": next(iter(draft_batch_ids)),
            "reviewReceiptPayloadSha256": receipt["receiptPayloadSha256"],
            "promptIdentity": prompt_identity(
                manifest=manifest,
                case=public_by_id[case_id],
                model_input=query,
                builder_id=BUILDER_ID,
                builder_source=Path(__file__),
            ),
            "toolAccess": {"webSearch": False, "shell": False, "domainDatabase": False, "customSkills": False},
            "error": error or ("missing_review_prediction" if not prediction else ""),
            "elapsedSec": elapsed,
        }
        (result_dir / f"{case_id}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        records.append(record)
    summary = {
        "schemaVersion": 1,
        "mode": MODE,
        "benchmarkId": manifest.get("benchmarkId", ""),
        "model": model,
        "draftBatchId": next(iter(draft_batch_ids)),
        "resourceGateAtStart": resource_snapshot or {},
        "total": {
            "cases": len(records),
            "kept": sum(1 for record in records if record.get("reviewVerdict") == "keep"),
            "corrected": sum(1 for record in records if record.get("reviewVerdict") == "correct"),
            "accepted": sum(1 for record in records if record.get("prediction") and not record.get("error")),
            "errors": sum(1 for record in records if record.get("error")),
        },
        "tokenUsage": usage,
        "elapsedSec": elapsed,
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Independently review one frozen subject-batch draft without answer keys or tools.")
    parser.add_argument("--public", type=Path, required=True)
    parser.add_argument("--draft-results-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--case-id", action="append", required=True)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--reasoning-effort", default="low")
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument("--max-review-tokens", type=int, default=MAX_REVIEW_TOKENS)
    parser.add_argument("--codex-home", type=Path, action="append", default=[])
    parser.add_argument("--discover-codex-home-root", type=Path)
    parser.add_argument("--pool-state", type=Path)
    args = parser.parse_args()
    homes = load_unique_homes(resolve_codex_home_paths(args.codex_home, args.discover_codex_home_root))
    snapshot = collect_resource_snapshot(allow_existing_swap_single_task=True)
    client = CodexHomeFailoverClient(
        homes=homes,
        default_model=args.model,
        timeout_seconds=min(MAX_REALTIME_SECONDS, max(1.0, float(args.timeout_seconds))),
        reasoning_effort=args.reasoning_effort,
        verbosity="low",
        web_search_enabled=False,
        calculation_tools_enabled=False,
        domain_evidence_mcp_enabled=False,
        agent_workspace_enabled=False,
        state_path=args.pool_state,
    )
    summary = run_independent_review(
        public_path=args.public,
        draft_results_dir=args.draft_results_dir,
        output_dir=args.output_dir,
        llm_client=client,
        model=args.model,
        case_ids=args.case_id,
        maximum_tokens=args.max_review_tokens,
        resource_snapshot=snapshot,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
