#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.codex_home_failover import CodexHome, CodexHomeFailoverClient, load_unique_homes, resolve_codex_home_paths
from tools.database_attestation import database_identity
from tools.prompt_identity import canonical_json_sha256, prompt_identity, text_sha256
from tools.resource_gate import collect_resource_snapshot
from tools.run_codex_home_pool import (
    audit_agent_workspace_command_events,
    audit_domain_evidence_mcp_trace,
    audit_web_search_trace,
)
from tools.run_open_response_benchmark import PUBLIC_PRODUCT_LABELS, infer_open_response_language, is_official_ready


MODE = "codex_native_subject_batch_plain_v5_no_beta6"
BUILDER_ID = "subject_batch_open_response_query_v5_plain_no_beta6"
DEFAULT_BATCH_SIZE = 8
MAX_BATCH_SIZE = 12
DEFAULT_MAX_PROMPT_CHARS = 24_000
DEFAULT_MAX_BATCH_TOKENS = 80_000
MAX_REALTIME_SECONDS = 600.0
MAX_WEB_SEARCH_EVENTS = 2
MAX_DOMAIN_TOOL_EVENTS = 2
MAX_COMMAND_EVENTS = 2
DB_PRODUCT_BY_PUBLIC_PRODUCT = {
    "lawkey": "lawkey",
    "tcm": "tcm",
    "psych": "simli",
    "simli": "simli",
    "islam": "islam",
    "buddhist": "buddhist",
    "christian": "catholic",
    "catholic": "catholic",
    "hindu": "hindu",
}
DB_ENV_BY_PRODUCT = {
    "lawkey": "RELIGION_LAWKEY_DB_PATH",
    "tcm": "RELIGION_TCM_DB_PATH",
    "simli": "RELIGION_SIMLI_DB_PATH",
    "islam": "RELIGION_ISLAM_DB_PATH",
    "buddhist": "RELIGION_BUDDHIST_DB_PATH",
    "catholic": "RELIGION_CATHOLIC_DB_PATH",
    "hindu": "RELIGION_HINDU_DB_PATH",
}


def build_subject_batch_query(*, manifest: dict[str, Any], cases: list[dict[str, Any]]) -> str:
    if not cases:
        raise ValueError("at least one case is required")
    product = str(manifest.get("product") or "").strip().lower()
    labels = PUBLIC_PRODUCT_LABELS.get(product, {})
    items = [
        {
            "id": str(case.get("id") or ""),
            "language": infer_open_response_language(
                str(case.get("prompt") or ""),
                str(case.get("language") or manifest.get("language") or ""),
            ),
            "question": str(case.get("prompt") or "").strip(),
        }
        for case in cases
    ]
    if any(not item["id"] or not item["question"] for item in items):
        raise ValueError("every batch item requires an id and public question")
    domain_label = str(labels.get("en") or labels.get("ko") or product)
    response_contract = " ".join(str(manifest.get("responseContract") or "").split())
    response_instruction = (
        f" Public response contract: {response_contract} " if response_contract else ""
    )
    external_evidence_required = bool(manifest.get("externalEvidenceRequired"))
    evidence_instruction = (
        " This public task requires externally verified evidence. Before answering, you MUST complete at least one "
        "native web search or mounted database search for this batch; do not invent a source identifier. "
        if external_evidence_required
        else ""
    )
    return (
        f"Public subject: {domain_label}. Answer every item independently using standard terminology. "
        "No answer choices are available. Do not infer one item's answer from another item. Web research, the mounted "
        "read-only subject database, and code in the ephemeral workspace may be used when useful; using a tool is optional. "
        "First solve from your own knowledge. Across this entire batch, use at most two web searches, at most two database "
        "tool calls, and at most two shell/code commands, only for genuinely unresolved items. Every database query must be "
        "a short abstract concept query of at most 64 characters and eight tokens. "
        + response_instruction
        +
        evidence_instruction
        +
        "Never look up the question, benchmark, exam item, removed choices, or an answer key.\n\n"
        "Return exactly one JSON object with this shape and no extra keys or commentary: "
        '{"answers":[{"id":"item id","finalAnswer":"concise answer"}]}. '
        "Return each supplied id exactly once and preserve input order.\n\n"
        "PUBLIC_ITEMS_JSON:\n"
        + json.dumps(items, ensure_ascii=False, separators=(",", ":"))
    )


def partition_subject_cases(
    cases: list[dict[str, Any]],
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
    max_prompt_chars: int = DEFAULT_MAX_PROMPT_CHARS,
) -> list[list[dict[str, Any]]]:
    if not 1 <= int(batch_size) <= MAX_BATCH_SIZE:
        raise ValueError(f"batch_size must be between 1 and {MAX_BATCH_SIZE}")
    if int(max_prompt_chars) < 1_000:
        raise ValueError("max_prompt_chars must be at least 1000")
    batches: list[list[dict[str, Any]]] = []
    active: list[dict[str, Any]] = []
    active_chars = 0
    active_leakage_groups: set[str] = set()
    for case in cases:
        case_chars = len(str(case.get("prompt") or ""))
        metadata = case.get("metadata") if isinstance(case.get("metadata"), dict) else {}
        leakage_group = str(metadata.get("batchLeakageGroup") or "").strip()
        if active and (
            len(active) >= int(batch_size)
            or active_chars + case_chars > int(max_prompt_chars)
            or bool(leakage_group and leakage_group in active_leakage_groups)
        ):
            batches.append(active)
            active = []
            active_chars = 0
            active_leakage_groups = set()
        active.append(case)
        active_chars += case_chars
        if leakage_group:
            active_leakage_groups.add(leakage_group)
    if active:
        batches.append(active)
    return batches


def parse_subject_batch_answer(raw: str, *, expected_ids: list[str]) -> dict[str, str]:
    try:
        payload = json.loads(str(raw or "").strip())
    except json.JSONDecodeError as exc:
        raise ValueError("invalid_subject_batch_json") from exc
    if not isinstance(payload, dict) or set(payload) != {"answers"} or not isinstance(payload["answers"], list):
        raise ValueError("invalid_subject_batch_schema")
    parsed: dict[str, str] = {}
    ordered_ids: list[str] = []
    for row in payload["answers"]:
        if not isinstance(row, dict) or set(row) != {"id", "finalAnswer"}:
            raise ValueError("invalid_subject_batch_answer_row")
        case_id = str(row.get("id") or "").strip()
        answer = str(row.get("finalAnswer") or "").strip()
        if not case_id or not answer or len(answer) > 4_000 or case_id in parsed:
            raise ValueError("invalid_subject_batch_answer_value")
        parsed[case_id] = answer
        ordered_ids.append(case_id)
    if ordered_ids != expected_ids:
        raise ValueError("subject_batch_ids_do_not_match")
    return parsed


def audit_subject_batch_trace(
    trace: dict[str, Any],
    *,
    public_question: str,
    db_product: str,
    maximum_mcp_calls: int,
    maximum_total_tokens: int,
    require_external_evidence: bool = False,
) -> dict[str, Any]:
    web = audit_web_search_trace(trace, public_question=public_question)
    domain = audit_domain_evidence_mcp_trace(
        trace,
        public_question=public_question,
        expected_product=db_product,
        maximum_calls=maximum_mcp_calls,
    )
    command_events = trace.get("commandExecutionEvents") if isinstance(trace.get("commandExecutionEvents"), list) else []
    commands = audit_agent_workspace_command_events(command_events)
    mcp_events = trace.get("mcpToolEvents") if isinstance(trace.get("mcpToolEvents"), list) else []
    web_events = trace.get("webSearchEvents") if isinstance(trace.get("webSearchEvents"), list) else []
    usage = trace.get("tokenUsage") if isinstance(trace.get("tokenUsage"), dict) else {}
    total_tokens = int(usage.get("totalTokens") or 0)
    violations: list[str] = []
    if str(trace.get("status") or "") != "completed":
        violations.append("model_trace_not_completed")
    if int(trace.get("codexJsonlEventCount") or 0) <= 0:
        violations.append("missing_codex_jsonl_trace")
    if int(trace.get("codexJsonlInvalidLineCount") or 0) != 0:
        violations.append("invalid_codex_jsonl_trace")
    if total_tokens <= 0:
        violations.append("missing_positive_token_usage")
    if int(maximum_total_tokens) > 0 and total_tokens > int(maximum_total_tokens):
        violations.append("batch_token_budget_exceeded")
    if len(web_events) > MAX_WEB_SEARCH_EVENTS:
        violations.append("batch_web_search_budget_exceeded")
    if len(mcp_events) > MAX_DOMAIN_TOOL_EVENTS:
        violations.append("batch_domain_tool_budget_exceeded")
    if len(command_events) > MAX_COMMAND_EVENTS:
        violations.append("batch_command_budget_exceeded")
    if require_external_evidence and not web_events and not mcp_events:
        violations.append("required_external_evidence_not_used")
    if web_events and not web["passed"]:
        violations.append("web_search_anti_cheating_audit_failed")
    if not domain["passed"]:
        violations.append("domain_evidence_anti_cheating_audit_failed")
    if not commands["passed"]:
        violations.append("agent_workspace_command_audit_failed")
    if any(str(event.get("status") or "") != "completed" for event in mcp_events if isinstance(event, dict)):
        violations.append("mcp_tool_call_not_completed")
    return {
        "policy": "subject_batch_tool_enabled_no_problem_exam_or_answer_lookup_v1",
        "passed": not violations,
        "violations": list(dict.fromkeys(violations)),
        "web": web,
        "domainEvidence": domain,
        "agentWorkspaceCommands": commands,
        "counts": {
            "webSearchEvents": len(web_events),
            "mcpToolEvents": len(mcp_events),
            "commandExecutionEvents": len(command_events),
        },
        "resource": {
            "totalTokens": total_tokens,
            "maximumTotalTokens": int(maximum_total_tokens),
            "elapsedSec": float(trace.get("elapsedSec") or 0.0),
            "maximumElapsedSec": MAX_REALTIME_SECONDS,
        },
    }


def run_subject_batches(
    *,
    public_path: Path,
    output_dir: Path,
    llm_client: Any,
    model: str,
    database: dict[str, Any],
    db_product: str,
    batch_size: int = DEFAULT_BATCH_SIZE,
    max_prompt_chars: int = DEFAULT_MAX_PROMPT_CHARS,
    max_batch_tokens: int = DEFAULT_MAX_BATCH_TOKENS,
    max_batches: int = 0,
    case_ids: list[str] | None = None,
    resume: bool = False,
    resource_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    manifest = json.loads(public_path.read_text(encoding="utf-8"))
    if manifest.get("taskType") != "open_response":
        raise ValueError("expected taskType=open_response")
    public_product = str(manifest.get("product") or "").strip().lower()
    expected_db_product = DB_PRODUCT_BY_PUBLIC_PRODUCT.get(public_product, "")
    if not expected_db_product or db_product != expected_db_product:
        raise ValueError("public subject and mounted database product do not match")
    selected = [case for case in manifest.get("cases", []) if isinstance(case, dict) and is_official_ready(case)]
    allowed = {str(value) for value in list(case_ids or []) if str(value)}
    if allowed:
        selected = [case for case in selected if str(case.get("id") or "") in allowed]
    output_dir.mkdir(parents=True, exist_ok=True)
    result_dir = output_dir / "results"
    batch_dir = output_dir / "batches"
    result_dir.mkdir(parents=True, exist_ok=True)
    batch_dir.mkdir(parents=True, exist_ok=True)
    if resume:
        selected = [case for case in selected if not (result_dir / f"{case.get('id')}.json").is_file()]
    batches = partition_subject_cases(selected, batch_size=batch_size, max_prompt_chars=max_prompt_chars)
    if max_batches > 0:
        batches = batches[: int(max_batches)]
    records: list[dict[str, Any]] = []
    batch_receipts: list[dict[str, Any]] = []
    started = time.monotonic()
    for batch_cases in batches:
        expected_ids = [str(case.get("id") or "") for case in batch_cases]
        batch_id = "batch-" + canonical_json_sha256(
            {"benchmarkId": manifest.get("benchmarkId"), "caseIds": expected_ids, "builderId": BUILDER_ID}
        )[:16]
        query = build_subject_batch_query(manifest=manifest, cases=batch_cases)
        public_question = "\n\n".join(str(case.get("prompt") or "") for case in batch_cases)
        batch_started = time.monotonic()
        raw_answer = ""
        parsed: dict[str, str] = {}
        error = ""
        try:
            raw_answer = str(llm_client.complete([{"role": "user", "content": query}], model=model) or "")
            parsed = parse_subject_batch_answer(raw_answer, expected_ids=expected_ids)
        except Exception as exc:
            error = str(exc)[:1_000]
        consume_trace = getattr(llm_client, "consume_last_call_trace", None)
        trace = consume_trace() if callable(consume_trace) else {}
        trace = trace if isinstance(trace, dict) else {}
        audit = audit_subject_batch_trace(
            trace,
            public_question=public_question,
            db_product=db_product,
            maximum_mcp_calls=MAX_DOMAIN_TOOL_EVENTS,
            maximum_total_tokens=max_batch_tokens,
            require_external_evidence=bool(manifest.get("externalEvidenceRequired")),
        )
        if not audit["passed"] and not error:
            error = "subject_batch_policy_audit_failed"
        elapsed = round(time.monotonic() - batch_started, 3)
        if elapsed > MAX_REALTIME_SECONDS and not error:
            error = "subject_batch_realtime_budget_exceeded"
        receipt: dict[str, Any] = {
            "schemaVersion": 1,
            "batchId": batch_id,
            "benchmarkId": manifest.get("benchmarkId", ""),
            "sourceBenchmarkId": manifest.get("sourceBenchmarkId", ""),
            "mode": MODE,
            "model": model,
            "publicProduct": public_product,
            "databaseProduct": db_product,
            "database": database,
            "caseIds": expected_ids,
            "caseCount": len(expected_ids),
            "batchModelInputSha256": text_sha256(query),
            "publicQuestionsSha256": text_sha256(public_question),
            "answerPreview": raw_answer[:8_000],
            "modelTrace": trace,
            "antiCheatingAudit": audit,
            "error": error,
            "elapsedSec": elapsed,
        }
        receipt["receiptPayloadSha256"] = canonical_json_sha256(receipt)
        (batch_dir / f"{batch_id}.json").write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        batch_receipts.append(receipt)
        for case in batch_cases:
            case_id = str(case.get("id") or "")
            prediction = parsed.get(case_id) if parsed else None
            case_error = error or ("missing_subject_batch_prediction" if not prediction else "")
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
                "publicProduct": public_product,
                "batchId": batch_id,
                "batchSize": len(batch_cases),
                "batchReceiptPayloadSha256": receipt["receiptPayloadSha256"],
                "promptIdentity": prompt_identity(
                    manifest=manifest,
                    case=case,
                    model_input=query,
                    builder_id=BUILDER_ID,
                    builder_source=Path(__file__),
                ),
                "toolAccess": {
                    "webSearch": True,
                    "ephemeralWorkspaceCode": True,
                    "readOnlyDomainDatabase": True,
                    "beta6Frontier": False,
                    "customSkills": False,
                },
                "antiCheatingAuditPassed": bool(audit["passed"]),
                "error": case_error,
                "elapsedSec": elapsed,
            }
            (result_dir / f"{case_id}.json").write_text(
                json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            records.append(record)
    durations = [float(receipt.get("elapsedSec") or 0.0) for receipt in batch_receipts]
    summary = {
        "schemaVersion": 1,
        "benchmarkId": manifest.get("benchmarkId", ""),
        "sourceBenchmarkId": manifest.get("sourceBenchmarkId", ""),
        "taskType": "open_response",
        "mode": MODE,
        "model": model,
        "publicProduct": public_product,
        "databaseProduct": db_product,
        "database": database,
        "selectionPolicy": "official_ready_only",
        "batchPolicy": {
            "batchSize": int(batch_size),
            "maximumBatchSize": MAX_BATCH_SIZE,
            "maximumPromptCharacters": int(max_prompt_chars),
            "maximumBatchTokens": int(max_batch_tokens),
            "maximumWebSearchEvents": MAX_WEB_SEARCH_EVENTS,
            "maximumDomainToolEvents": MAX_DOMAIN_TOOL_EVENTS,
            "maximumCommandEvents": MAX_COMMAND_EVENTS,
            "externalEvidenceRequired": bool(manifest.get("externalEvidenceRequired")),
            "sequentialModelCallsOnly": True,
            "crossItemContextPresent": True,
            "comparisonClass": "throughput_baseline_not_item_isolated_direct",
        },
        "toolAccess": {
            "webSearch": True,
            "ephemeralWorkspaceCode": True,
            "readOnlyDomainDatabase": True,
            "beta6Frontier": False,
            "customSkills": False,
        },
        "resourceGateAtStart": resource_snapshot or {},
        "total": {
            "batches": len(batch_receipts),
            "cases": len(records),
            "predicted": sum(1 for record in records if record.get("prediction")),
            "accepted": sum(1 for record in records if record.get("prediction") and not record.get("error")),
            "errors": sum(1 for record in records if record.get("error")),
        },
        "latencySec": {
            "medianPerBatch": round(statistics.median(durations), 3) if durations else 0.0,
            "maximumPerBatch": round(max(durations), 3) if durations else 0.0,
            "hardLimitPerBatch": MAX_REALTIME_SECONDS,
        },
        "elapsedSec": round(time.monotonic() - started, 3),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def _load_homes(explicit: list[Path], discovery_root: Path | None) -> list[CodexHome]:
    return load_unique_homes(resolve_codex_home_paths(explicit, discovery_root))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run one subject as small sequential Codex batches with audited web, code, and read-only DB tools."
    )
    parser.add_argument("--public", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--domain-db-path", type=Path, required=True)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--reasoning-effort", default="low")
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--max-prompt-chars", type=int, default=DEFAULT_MAX_PROMPT_CHARS)
    parser.add_argument("--max-batch-tokens", type=int, default=DEFAULT_MAX_BATCH_TOKENS)
    parser.add_argument("--max-batches", type=int, default=0)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--codex-home", type=Path, action="append", default=[])
    parser.add_argument("--codex-home-discovery-root", type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.public.read_text(encoding="utf-8"))
    public_product = str(manifest.get("product") or "").strip().lower()
    db_product = DB_PRODUCT_BY_PUBLIC_PRODUCT.get(public_product, "")
    if not db_product:
        raise ValueError(f"no domain database route for public product: {public_product}")
    database = database_identity(args.domain_db_path)
    if database["fixtureWarning"]:
        raise ValueError("refusing fixture-sized domain database")
    homes = _load_homes(args.codex_home, args.codex_home_discovery_root)
    snapshot = collect_resource_snapshot(allow_existing_swap_single_task=True)
    env_name = DB_ENV_BY_PRODUCT[db_product]
    previous_db_path = os.environ.get(env_name)
    os.environ[env_name] = str(database["path"])
    try:
        client = CodexHomeFailoverClient(
            homes=homes,
            default_model=args.model,
            timeout_seconds=min(MAX_REALTIME_SECONDS, max(1.0, float(args.timeout_seconds))),
            reasoning_effort=args.reasoning_effort,
            verbosity="low",
            web_search_enabled=True,
            calculation_tools_enabled=True,
            domain_evidence_mcp_enabled=True,
            domain_beta6_frontier_enabled=False,
            domain_evidence_repo_root=REPO_ROOT,
            domain_evidence_product=db_product,
            agent_workspace_enabled=True,
            capture_workspace_artifacts=True,
            state_path=args.output_dir / "pool_state.json",
        )
        summary = run_subject_batches(
            public_path=args.public,
            output_dir=args.output_dir,
            llm_client=client,
            model=args.model,
            database=database,
            db_product=db_product,
            batch_size=args.batch_size,
            max_prompt_chars=args.max_prompt_chars,
            max_batch_tokens=args.max_batch_tokens,
            max_batches=args.max_batches,
            case_ids=args.case_id,
            resume=args.resume,
            resource_snapshot=snapshot,
        )
    finally:
        if previous_db_path is None:
            os.environ.pop(env_name, None)
        else:
            os.environ[env_name] = previous_db_path
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
