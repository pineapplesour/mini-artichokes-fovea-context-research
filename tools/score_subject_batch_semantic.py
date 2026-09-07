#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.codex_home_failover import CodexHomeFailoverClient, load_unique_homes, resolve_codex_home_paths
from tools.resource_gate import collect_resource_snapshot
from tools.score_open_responses import _audit_closed_judge_trace, score_run


POLICY_VERSION = "strict-subject-batch-equivalence-consensus-v1-closed-trace"
MAX_CASES_PER_BATCH = 8


def semantic_batch_input_sha256(
    *,
    rows: list[dict[str, Any]],
    judge_model: str,
) -> str:
    payload = {
        "policyVersion": POLICY_VERSION,
        "judgeModel": str(judge_model),
        "rows": rows,
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def build_semantic_batch_prompt(*, rows: list[dict[str, Any]], repeat: int) -> str:
    if not 1 <= len(rows) <= MAX_CASES_PER_BATCH:
        raise ValueError(f"semantic batch requires 1 to {MAX_CASES_PER_BATCH} cases")
    payload = [
        {
            "id": str(row["id"]),
            "question": str(row["question"]),
            "canonicalAnswer": str(row["canonicalAnswer"]),
            "acceptableAliases": [str(value) for value in row.get("acceptableAliases", [])],
            "candidateAnswer": str(row["candidateAnswer"]),
        }
        for row in rows
    ]
    return (
        "You are a strict semantic equivalence grader for open-response benchmark answers. Judge every item independently. "
        "The payload contains no multiple-choice distractors. An answer is equivalent only if it preserves the required "
        "subject, object, polarity, causal direction, quantity, condition, exception, and every critical fact. Different "
        "standard terminology or a harmless explanatory synonym may be equivalent; shared keywords alone are insufficient. "
        "Return exactly one JSON object with only the key judgments. judgments must preserve input order and contain every id "
        "exactly once. Each row must contain exactly id, equivalent (boolean), contradiction (boolean), missingCriticalFacts "
        "(array of strings), and reason (short nonempty string).\n\n"
        f"PRIVATE_GRADING_BATCH_JSON:\n{json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}\n"
        f"INDEPENDENT_REPEAT: {int(repeat)}"
    )


def parse_semantic_batch_response(raw: str, *, expected_ids: list[str]) -> list[dict[str, Any]]:
    try:
        payload = json.loads(str(raw or "").strip())
    except json.JSONDecodeError as exc:
        raise ValueError("invalid_semantic_batch_json") from exc
    if not isinstance(payload, dict) or set(payload) != {"judgments"} or not isinstance(payload["judgments"], list):
        raise ValueError("invalid_semantic_batch_schema")
    judgments: list[dict[str, Any]] = []
    required = {"id", "equivalent", "contradiction", "missingCriticalFacts", "reason"}
    for row in payload["judgments"]:
        if not isinstance(row, dict) or set(row) != required:
            raise ValueError("invalid_semantic_batch_judgment_schema")
        if not isinstance(row["equivalent"], bool) or not isinstance(row["contradiction"], bool):
            raise ValueError("invalid_semantic_batch_boolean")
        missing = row["missingCriticalFacts"]
        if not isinstance(missing, list) or not all(isinstance(value, str) for value in missing):
            raise ValueError("invalid_semantic_batch_missing_facts")
        if not isinstance(row["reason"], str) or not row["reason"].strip():
            raise ValueError("invalid_semantic_batch_reason")
        if row["equivalent"] and (row["contradiction"] or any(value.strip() for value in missing)):
            raise ValueError("inconsistent_semantic_batch_judgment")
        judgments.append(
            {
                "id": str(row["id"]),
                "equivalent": row["equivalent"],
                "contradiction": row["contradiction"],
                "missingCriticalFacts": [value for value in missing if value],
                "reason": row["reason"][:500],
            }
        )
    if [row["id"] for row in judgments] != expected_ids:
        raise ValueError("semantic_batch_ids_do_not_match")
    return judgments


def run_semantic_batch_attempt(
    *,
    rows: list[dict[str, Any]],
    repeat: int,
    judge_client: Any,
    judge_model: str,
) -> dict[str, Any]:
    expected_ids = [str(row["id"]) for row in rows]
    input_sha256 = semantic_batch_input_sha256(rows=rows, judge_model=judge_model)
    prompt = build_semantic_batch_prompt(rows=rows, repeat=repeat)
    started = time.monotonic()
    raw = ""
    trace: dict[str, Any] = {}
    try:
        raw = str(judge_client.complete([{"role": "user", "content": prompt}], model=judge_model) or "")
        consume = getattr(judge_client, "consume_last_call_trace", None)
        trace_value = consume() if callable(consume) else None
        trace = trace_value if isinstance(trace_value, dict) else {}
        trace_audit = _audit_closed_judge_trace(trace)
        if not trace_audit["passed"]:
            raise ValueError("semantic_batch_closed_tool_trace_failed:" + ",".join(trace_audit["violations"]))
        judgments = parse_semantic_batch_response(raw, expected_ids=expected_ids)
        return {
            "repeat": int(repeat),
            "policyVersion": POLICY_VERSION,
            "semanticBatchInputSha256": input_sha256,
            "caseIds": expected_ids,
            "judgments": judgments,
            "modelTrace": trace,
            "closedToolTraceAudit": trace_audit,
            "rawPreview": raw[:4_000],
            "elapsedSec": round(time.monotonic() - started, 3),
        }
    except Exception as exc:
        if not trace:
            consume = getattr(judge_client, "consume_last_call_trace", None)
            trace_value = consume() if callable(consume) else None
            trace = trace_value if isinstance(trace_value, dict) else {}
        return {
            "repeat": int(repeat),
            "policyVersion": POLICY_VERSION,
            "semanticBatchInputSha256": input_sha256,
            "caseIds": expected_ids,
            "error": str(exc)[:500],
            "modelTrace": trace,
            "closedToolTraceAudit": _audit_closed_judge_trace(trace),
            "rawPreview": raw[:4_000],
            "elapsedSec": round(time.monotonic() - started, 3),
        }


def finalize_semantic_batch(
    *,
    deterministic_report: dict[str, Any],
    rows: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    judge_model: str,
    resource_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    judgments_by_case: dict[str, list[dict[str, Any]]] = {str(row["id"]): [] for row in rows}
    for attempt in attempts:
        if attempt.get("error") or attempt.get("closedToolTraceAudit", {}).get("passed") is not True:
            continue
        for judgment in attempt.get("judgments", []):
            case_id = str(judgment.get("id") or "")
            if case_id in judgments_by_case:
                judgments_by_case[case_id].append({**judgment, "repeat": int(attempt["repeat"])})
    semantic_cases: list[dict[str, Any]] = []
    for row in rows:
        case_id = str(row["id"])
        valid = judgments_by_case[case_id]
        pass_count = sum(1 for item in valid if item["equivalent"] is True)
        fail_count = sum(1 for item in valid if item["equivalent"] is False)
        if pass_count >= 2:
            verdict = "pass"
        elif fail_count >= 2:
            verdict = "fail"
        else:
            verdict = "unresolved"
        semantic_cases.append(
            {
                "caseId": case_id,
                "verdict": verdict,
                "gradingPath": (
                    "semantic_batch_judge_2of3"
                    if len(valid) >= 3 and verdict != "unresolved"
                    else "semantic_batch_judge_2of2"
                    if len(valid) >= 2 and verdict != "unresolved"
                    else "semantic_batch_judge_unresolved"
                ),
                "judgments": valid,
                "resultPath": str(row["resultPath"]),
            }
        )
    semantic_by_id = {case["caseId"]: case for case in semantic_cases}
    combined_cases = [semantic_by_id.get(case["caseId"], case) for case in deterministic_report["cases"]]
    total = len(combined_cases)
    passed = sum(1 for case in combined_cases if case["verdict"] == "pass")
    failed = sum(1 for case in combined_cases if case["verdict"] == "fail")
    return {
        "schemaVersion": 1,
        "benchmarkId": deterministic_report.get("benchmarkId", ""),
        "taskType": "open_response",
        "policyVersion": POLICY_VERSION,
        "judgeModel": judge_model,
        "judgeCallsUsed": len(attempts),
        "resourceGateAtStart": resource_snapshot,
        "total": total,
        "passed": passed,
        "failed": failed,
        "unresolved": total - passed - failed,
        "accuracy": (passed / total) if total else 0.0,
        "cases": combined_cases,
        "batchAttempts": attempts,
    }


def unresolved_semantic_rows(
    *,
    deterministic_report: dict[str, Any],
    public_manifest: dict[str, Any],
    private_manifest: dict[str, Any],
    results_dir: Path,
) -> list[dict[str, Any]]:
    public_by_id = {str(case.get("id") or ""): case for case in public_manifest.get("cases", []) if isinstance(case, dict)}
    private_by_id = {
        str(answer.get("caseId") or ""): answer
        for answer in private_manifest.get("answers", [])
        if isinstance(answer, dict)
    }
    rows: list[dict[str, Any]] = []
    for case in deterministic_report.get("cases", []):
        if case.get("verdict") != "unresolved" or case.get("gradingPath") != "semantic_judge_not_run":
            continue
        case_id = str(case.get("caseId") or "")
        artifact_path = Path(results_dir) / f"{case_id}.json"
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        if str(artifact.get("error") or "").strip():
            continue
        public_case = public_by_id[case_id]
        answer = private_by_id[case_id]
        rows.append(
            {
                "id": case_id,
                "question": str(public_case.get("prompt") or ""),
                "canonicalAnswer": str(answer.get("canonicalAnswer") or ""),
                "acceptableAliases": [str(value) for value in answer.get("aliases", []) if str(value)],
                "candidateAnswer": str(artifact.get("prediction") or ""),
                "resultPath": str(artifact_path),
            }
        )
    if len(rows) > MAX_CASES_PER_BATCH:
        raise ValueError(f"semantic batch exceeds {MAX_CASES_PER_BATCH} unresolved cases")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Grade up to eight unresolved subject answers with batched closed-tool consensus.")
    parser.add_argument("--public", type=Path, required=True)
    parser.add_argument("--private", type=Path, required=True)
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--deterministic-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--judge-model", default="gpt-5.6-luna")
    parser.add_argument("--judge-reasoning-effort", default="low")
    parser.add_argument("--judge-timeout-seconds", type=float, default=180.0)
    parser.add_argument("--max-judge-calls", type=int, choices=(2, 3), default=3)
    parser.add_argument("--codex-home", type=Path, action="append", default=[])
    parser.add_argument("--discover-codex-home-root", type=Path)
    parser.add_argument("--judge-pool-state", type=Path)
    args = parser.parse_args()
    public = json.loads(args.public.read_text(encoding="utf-8"))
    private = json.loads(args.private.read_text(encoding="utf-8"))
    deterministic = json.loads(args.deterministic_report.read_text(encoding="utf-8"))
    rows = unresolved_semantic_rows(
        deterministic_report=deterministic,
        public_manifest=public,
        private_manifest=private,
        results_dir=args.results_dir,
    )
    if not rows:
        report = finalize_semantic_batch(
            deterministic_report=deterministic,
            rows=[],
            attempts=[],
            judge_model=args.judge_model,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    homes = load_unique_homes(resolve_codex_home_paths(args.codex_home, args.discover_codex_home_root))
    snapshot = collect_resource_snapshot(allow_existing_swap_single_task=True)
    client = CodexHomeFailoverClient(
        homes=homes,
        default_model=args.judge_model,
        timeout_seconds=min(600.0, max(1.0, float(args.judge_timeout_seconds))),
        reasoning_effort=args.judge_reasoning_effort,
        verbosity="low",
        web_search_enabled=False,
        calculation_tools_enabled=False,
        domain_evidence_mcp_enabled=False,
        agent_workspace_enabled=False,
        state_path=args.judge_pool_state,
    )
    attempts = [
        run_semantic_batch_attempt(rows=rows, repeat=repeat, judge_client=client, judge_model=args.judge_model)
        for repeat in (1, 2)
    ]
    preliminary = finalize_semantic_batch(
        deterministic_report=deterministic,
        rows=rows,
        attempts=attempts,
        judge_model=args.judge_model,
        resource_snapshot=snapshot,
    )
    if int(args.max_judge_calls) >= 3 and preliminary["unresolved"]:
        unresolved_ids = {
            str(case["caseId"])
            for case in preliminary["cases"]
            if case.get("gradingPath") == "semantic_batch_judge_unresolved"
        }
        third_rows = [row for row in rows if str(row["id"]) in unresolved_ids]
        if third_rows:
            attempts.append(
                run_semantic_batch_attempt(
                    rows=third_rows,
                    repeat=3,
                    judge_client=client,
                    judge_model=args.judge_model,
                )
            )
    report = finalize_semantic_batch(
        deterministic_report=deterministic,
        rows=rows,
        attempts=attempts,
        judge_model=args.judge_model,
        resource_snapshot=snapshot,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("benchmarkId", "total", "passed", "failed", "unresolved", "accuracy", "judgeCallsUsed")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
