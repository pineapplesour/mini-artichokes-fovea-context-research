#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.codex_home_failover import CodexHomeFailoverClient, load_unique_homes, resolve_codex_home_paths
from tools.prompt_identity import canonical_json_sha256, prompt_identity, text_sha256
from tools.resource_gate import collect_resource_snapshot
from tools.run_open_response_benchmark import PUBLIC_PRODUCT_LABELS, infer_open_response_language, is_official_ready
from tools.run_subject_batch_benchmark import partition_subject_cases


MODE = "codex_native_subject_batch_plain_v6_closed_no_db"
BUILDER_ID = "subject_batch_open_response_query_v6_plain_closed_no_db"
SUPERVISOR_ID = "plain-no-db-full-sequential-v1"
FREEZE_ID = "plain-codex-no-db-full-v2-20260721"
SCHEMA_VERSION = 1
DEFAULT_BATCH_SIZE = 8
DEFAULT_MAX_PROMPT_CHARS = 24_000
DEFAULT_MAX_BATCH_TOKENS = 80_000
MAX_REALTIME_SECONDS = 600.0
EXPECTED_READY_CASES = 619
EXPECTED_TOTAL_CASES = 945
EXPECTED_BATCHES = 80
EXPECTED_MODEL = "gpt-5.6-luna"
EXPECTED_REASONING_EFFORT = "low"
TERMINAL_DISPOSITIONS = {"accepted", "response_quarantine", "policy_quarantine"}


@dataclass(frozen=True)
class BatchSpec:
    batch_id: str
    benchmark_id: str
    public_path: Path
    private_path: Path
    manifest: dict[str, Any]
    cases: tuple[dict[str, Any], ...]

    @property
    def case_ids(self) -> list[str]:
        return [str(case.get("id") or "") for case in self.cases]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def artifact_digest(payload: dict[str, Any]) -> str:
    content = {key: value for key, value in payload.items() if key != "artifactDigest"}
    return canonical_json_sha256(content)


def build_closed_subject_batch_query(*, manifest: dict[str, Any], cases: list[dict[str, Any]]) -> str:
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
    response_instruction = f" Public response contract: {response_contract} " if response_contract else ""
    return (
        f"Public subject: {domain_label}. Answer every item independently from your own knowledge using standard terminology. "
        "No answer choices are available. Do not infer one item's answer from another item. "
        "No web search, database, shell, code, MCP, skill, external evidence system, Universal engine, or Beta6 engine is "
        "available or permitted. Do not claim to have consulted any such source."
        + response_instruction
        + "\n\nReturn exactly one JSON object with this shape and no extra keys or commentary: "
        + '{"answers":[{"id":"item id","finalAnswer":"concise answer"}]}. '
        + "Return each supplied id exactly once and preserve input order.\n\nPUBLIC_ITEMS_JSON:\n"
        + json.dumps(items, ensure_ascii=False, separators=(",", ":"))
    )


def parse_batch_answer(raw: str, *, expected_ids: list[str]) -> dict[str, str]:
    try:
        payload = json.loads(str(raw or "").strip())
    except json.JSONDecodeError as exc:
        raise ValueError("invalid_plain_no_db_batch_json") from exc
    if not isinstance(payload, dict) or set(payload) != {"answers"} or not isinstance(payload["answers"], list):
        raise ValueError("invalid_plain_no_db_batch_schema")
    parsed: dict[str, str] = {}
    ordered: list[str] = []
    for row in payload["answers"]:
        if not isinstance(row, dict) or set(row) != {"id", "finalAnswer"}:
            raise ValueError("invalid_plain_no_db_answer_row")
        case_id = str(row.get("id") or "").strip()
        answer = str(row.get("finalAnswer") or "").strip()
        if not case_id or not answer or len(answer) > 4_000 or case_id in parsed:
            raise ValueError("invalid_plain_no_db_answer_value")
        parsed[case_id] = answer
        ordered.append(case_id)
    if ordered != expected_ids:
        raise ValueError("plain_no_db_batch_ids_do_not_match")
    return parsed


def audit_closed_solver_trace(trace: Any, *, maximum_tokens: int) -> dict[str, Any]:
    violations: list[str] = []
    if not isinstance(trace, dict) or not trace:
        return {"policy": "closed_plain_no_db_v1", "passed": False, "violations": ["trace_missing"]}
    if str(trace.get("provider") or "") not in {"codex_exec", "openai_codex_exec"}:
        violations.append("provider_not_codex_exec")
    if str(trace.get("status") or "") != "completed":
        violations.append("trace_not_completed")
    if int(trace.get("codexJsonlEventCount") or 0) <= 0:
        violations.append("jsonl_trace_missing")
    if int(trace.get("codexJsonlInvalidLineCount") or 0) != 0:
        violations.append("invalid_jsonl_lines")
    for field in ("webSearchEnabled", "domainEvidenceMcpEnabled", "agentWorkspaceEnabled"):
        if trace.get(field) is not False:
            violations.append(f"{field}_not_false")
    if trace.get("domainBeta6FrontierEnabled") not in {False, None}:
        violations.append("beta6_frontier_not_false")
    for field, label in (
        ("webSearchEvents", "web_event_present"),
        ("commandExecutionEvents", "command_event_present"),
        ("mcpToolEvents", "mcp_event_present"),
        ("skillEvents", "skill_event_present"),
    ):
        if trace.get(field) != []:
            violations.append(label)
    if trace.get("skillsAvailable") is not None and trace.get("skillsAvailable") != []:
        violations.append("skills_available")
    usage = trace.get("tokenUsage") if isinstance(trace.get("tokenUsage"), dict) else {}
    tokens = int(usage.get("totalTokens") or 0)
    if tokens <= 0:
        violations.append("positive_token_usage_missing")
    if maximum_tokens > 0 and tokens > int(maximum_tokens):
        violations.append("batch_token_budget_exceeded")
    elapsed = float(trace.get("elapsedSec") or 0.0)
    if elapsed > MAX_REALTIME_SECONDS:
        violations.append("batch_realtime_budget_exceeded")
    return {
        "policy": "closed_plain_no_db_v1",
        "passed": not violations,
        "violations": violations,
        "tokens": tokens,
        "elapsedSec": elapsed,
    }


def load_batch_plan(
    registry_path: Path,
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
    max_prompt_chars: int = DEFAULT_MAX_PROMPT_CHARS,
) -> tuple[list[BatchSpec], dict[str, str], dict[str, Any]]:
    registry_path = registry_path.resolve()
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    base = registry_path.parent
    input_hashes = {str(registry_path): sha256_file(registry_path)}
    batches: list[BatchSpec] = []
    ready_count = 0
    total_count = 0
    for entry in registry.get("entries", []):
        if not isinstance(entry, dict):
            continue
        public_path = (base / str(entry.get("publicManifest") or "")).resolve()
        private_path = (base / str(entry.get("privateManifest") or "")).resolve()
        public = json.loads(public_path.read_text(encoding="utf-8"))
        private = json.loads(private_path.read_text(encoding="utf-8"))
        input_hashes[str(public_path)] = sha256_file(public_path)
        input_hashes[str(private_path)] = sha256_file(private_path)
        public_status = {
            str(case.get("id") or ""): str(
                case.get("metadata", {}).get("openResponseConversion", {}).get("status") or ""
            )
            for case in public.get("cases", [])
            if isinstance(case, dict)
        }
        private_status = {
            str(answer.get("caseId") or ""): str(answer.get("conversionStatus") or "")
            for answer in private.get("answers", [])
            if isinstance(answer, dict)
        }
        if public_status != private_status:
            raise ValueError(f"public/private status mismatch: {public_path.name}")
        selected = [case for case in public.get("cases", []) if isinstance(case, dict) and is_official_ready(case)]
        ready_count += len(selected)
        total_count += len(public_status)
        for cases in partition_subject_cases(selected, batch_size=batch_size, max_prompt_chars=max_prompt_chars):
            case_ids = [str(case.get("id") or "") for case in cases]
            batch_id = "plain2-" + canonical_json_sha256(
                {
                    "freezeId": FREEZE_ID,
                    "benchmarkId": public.get("benchmarkId"),
                    "caseIds": case_ids,
                    "builderId": BUILDER_ID,
                    "publicManifestSha256": input_hashes[str(public_path)],
                }
            )[:20]
            batches.append(
                BatchSpec(
                    batch_id=batch_id,
                    benchmark_id=str(public.get("benchmarkId") or ""),
                    public_path=public_path,
                    private_path=private_path,
                    manifest=public,
                    cases=tuple(cases),
                )
            )
    all_case_ids = [case_id for batch in batches for case_id in batch.case_ids]
    if ready_count != EXPECTED_READY_CASES or total_count != EXPECTED_TOTAL_CASES:
        raise ValueError(f"expected {EXPECTED_READY_CASES}/{EXPECTED_TOTAL_CASES} ready/total, found {ready_count}/{total_count}")
    if len(all_case_ids) != ready_count or len(set(all_case_ids)) != ready_count:
        raise ValueError("ready case IDs are missing or duplicated")
    return batches, dict(sorted(input_hashes.items())), registry


def implementation_hashes() -> dict[str, str]:
    paths = [
        Path(__file__).resolve(),
        REPO_ROOT / "tools" / "benchmark_provider.py",
        REPO_ROOT / "tools" / "codex_home_failover.py",
        REPO_ROOT / "tools" / "prompt_identity.py",
        REPO_ROOT / "tools" / "run_subject_batch_benchmark.py",
        REPO_ROOT / "tools" / "score_open_responses.py",
        REPO_ROOT / "tools" / "score_subject_batch_semantic.py",
        REPO_ROOT / "tools" / "score_plain_no_db_full_benchmark.py",
    ]
    return {str(path): sha256_file(path) for path in paths}


def build_freeze_payload(*, registry_path: Path, model: str, reasoning_effort: str) -> dict[str, Any]:
    if model != EXPECTED_MODEL or reasoning_effort != EXPECTED_REASONING_EFFORT:
        raise ValueError("the comparison freeze requires the fixed solver model and reasoning effort")
    batches, inputs, _registry = load_batch_plan(registry_path)
    if len(batches) != EXPECTED_BATCHES:
        raise ValueError(f"expected {EXPECTED_BATCHES} frozen batches, found {len(batches)}")
    plan = [{"batchId": batch.batch_id, "benchmarkId": batch.benchmark_id, "caseIds": batch.case_ids} for batch in batches]
    return {
        "schemaVersion": SCHEMA_VERSION,
        "freezeId": FREEZE_ID,
        "status": "frozen_before_solver_calls",
        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "model": model,
        "reasoningEffort": reasoning_effort,
        "mode": MODE,
        "builderId": BUILDER_ID,
        "registryPath": str(registry_path.resolve()),
        "registrySha256": sha256_file(registry_path.resolve()),
        "canonicalInputs": inputs,
        "implementationFiles": implementation_hashes(),
        "inventory": {"readyCases": EXPECTED_READY_CASES, "totalCases": EXPECTED_TOTAL_CASES, "batches": EXPECTED_BATCHES},
        "batchPolicy": {
            "batchSize": DEFAULT_BATCH_SIZE,
            "maximumPromptCharacters": DEFAULT_MAX_PROMPT_CHARS,
            "maximumBatchTokens": DEFAULT_MAX_BATCH_TOKENS,
            "sequentialCallsOnly": True,
            "freshSolverOpportunityPerCase": True,
            "priorSolverResultsReused": False,
        },
        "toolBoundary": {
            "webSearch": False,
            "shellOrCode": False,
            "mcp": False,
            "readOnlySubjectDatabase": False,
            "customSkills": False,
            "universalEngine": False,
            "beta6Engine": False,
        },
        "planSha256": canonical_json_sha256(plan),
        "plan": plan,
    }


def validate_freeze(freeze: dict[str, Any], *, freeze_path: Path, registry_path: Path) -> list[BatchSpec]:
    batches, inputs, _registry = load_batch_plan(registry_path)
    expected_plan = [{"batchId": batch.batch_id, "benchmarkId": batch.benchmark_id, "caseIds": batch.case_ids} for batch in batches]
    checks = {
        "schemaVersion": SCHEMA_VERSION,
        "freezeId": FREEZE_ID,
        "status": "frozen_before_solver_calls",
        "mode": MODE,
        "builderId": BUILDER_ID,
        "registryPath": str(registry_path.resolve()),
        "registrySha256": sha256_file(registry_path.resolve()),
        "canonicalInputs": inputs,
        "implementationFiles": implementation_hashes(),
        "model": EXPECTED_MODEL,
        "reasoningEffort": EXPECTED_REASONING_EFFORT,
        "inventory": {"readyCases": EXPECTED_READY_CASES, "totalCases": EXPECTED_TOTAL_CASES, "batches": EXPECTED_BATCHES},
        "batchPolicy": {
            "batchSize": DEFAULT_BATCH_SIZE,
            "maximumPromptCharacters": DEFAULT_MAX_PROMPT_CHARS,
            "maximumBatchTokens": DEFAULT_MAX_BATCH_TOKENS,
            "sequentialCallsOnly": True,
            "freshSolverOpportunityPerCase": True,
            "priorSolverResultsReused": False,
        },
        "planSha256": canonical_json_sha256(expected_plan),
        "plan": expected_plan,
    }
    for field, expected in checks.items():
        if freeze.get(field) != expected:
            raise ValueError(f"freeze mismatch: {field}")
    boundary = freeze.get("toolBoundary") if isinstance(freeze.get("toolBoundary"), dict) else {}
    if not boundary or any(value is not False for value in boundary.values()):
        raise ValueError("freeze tool boundary is not fully closed")
    if not freeze_path.is_file():
        raise ValueError("freeze file is missing")
    return batches


def validate_batch_artifact(
    artifact: dict[str, Any],
    *,
    batch: BatchSpec,
    model: str,
    freeze_sha256: str = "",
) -> None:
    query = build_closed_subject_batch_query(manifest=batch.manifest, cases=list(batch.cases))
    expected_ids = batch.case_ids
    if (
        artifact.get("schemaVersion") != SCHEMA_VERSION
        or artifact.get("freezeId") != FREEZE_ID
        or artifact.get("batchId") != batch.batch_id
        or artifact.get("benchmarkId") != batch.benchmark_id
    ):
        raise ValueError(f"batch artifact identity mismatch: {batch.batch_id}")
    if artifact.get("mode") != MODE or artifact.get("model") != model or artifact.get("caseIds") != expected_ids:
        raise ValueError(f"batch artifact contract mismatch: {batch.batch_id}")
    if freeze_sha256 and artifact.get("freezeSha256") != freeze_sha256:
        raise ValueError(f"batch artifact freeze mismatch: {batch.batch_id}")
    if artifact.get("modelInputSha256") != text_sha256(query):
        raise ValueError(f"batch model input changed: {batch.batch_id}")
    raw = str(artifact.get("rawResponse") or "")
    if artifact.get("rawResponseSha256") != text_sha256(raw):
        raise ValueError(f"batch response digest mismatch: {batch.batch_id}")
    if artifact.get("artifactDigest") != artifact_digest(artifact):
        raise ValueError(f"batch artifact digest mismatch: {batch.batch_id}")
    trace = artifact.get("modelTrace")
    audit = audit_closed_solver_trace(trace, maximum_tokens=DEFAULT_MAX_BATCH_TOKENS)
    if artifact.get("closedToolAudit") != audit:
        raise ValueError(f"batch trace audit changed: {batch.batch_id}")
    disposition = str(artifact.get("disposition") or "")
    if disposition not in TERMINAL_DISPOSITIONS | {"infrastructure_failure"}:
        raise ValueError(f"batch disposition invalid: {batch.batch_id}")
    if disposition in TERMINAL_DISPOSITIONS and str(trace.get("status") or "") != "completed":
        raise ValueError(f"terminal batch lacks completion trace: {batch.batch_id}")
    if disposition == "accepted":
        parsed = parse_batch_answer(raw, expected_ids=expected_ids)
        if artifact.get("predictions") != parsed or audit.get("passed") is not True:
            raise ValueError(f"accepted batch no longer validates: {batch.batch_id}")


def ledger_totals(records: list[dict[str, Any]], batches: list[BatchSpec]) -> dict[str, int]:
    terminal = [record for record in records if record.get("disposition") in TERMINAL_DISPOSITIONS]
    terminal_cases = sum(len(record.get("caseIds") or []) for record in terminal)
    return {
        "targetBatches": len(batches),
        "terminalBatches": len(terminal),
        "targetCases": sum(len(batch.case_ids) for batch in batches),
        "terminalCases": terminal_cases,
        "acceptedCases": sum(len(record.get("caseIds") or []) for record in terminal if record.get("disposition") == "accepted"),
        "quarantinedCases": sum(len(record.get("caseIds") or []) for record in terminal if record.get("disposition") != "accepted"),
        "pendingCases": EXPECTED_READY_CASES - terminal_cases,
        "modelCalls": len(terminal),
        "totalTokens": sum(int(record.get("totalTokens") or 0) for record in terminal),
    }


def run_batch(*, batch: BatchSpec, client: CodexHomeFailoverClient, model: str, freeze_sha256: str) -> dict[str, Any]:
    query = build_closed_subject_batch_query(manifest=batch.manifest, cases=list(batch.cases))
    raw = ""
    predictions: dict[str, str] = {}
    response_error = ""
    call_error = ""
    started = time.monotonic()
    try:
        raw = str(client.complete([{"role": "user", "content": query}], model=model) or "")
        try:
            predictions = parse_batch_answer(raw, expected_ids=batch.case_ids)
        except Exception as exc:
            response_error = str(exc)[:1_000]
    except Exception as exc:
        call_error = str(exc)[:1_000]
    trace_value = client.consume_last_call_trace()
    trace = trace_value if isinstance(trace_value, dict) else {}
    audit = audit_closed_solver_trace(trace, maximum_tokens=DEFAULT_MAX_BATCH_TOKENS)
    if call_error or str(trace.get("status") or "") != "completed":
        disposition = "infrastructure_failure"
    elif not audit["passed"]:
        disposition = "policy_quarantine"
    elif response_error:
        disposition = "response_quarantine"
    else:
        disposition = "accepted"
    artifact: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "freezeId": FREEZE_ID,
        "freezeSha256": freeze_sha256,
        "batchId": batch.batch_id,
        "benchmarkId": batch.benchmark_id,
        "mode": MODE,
        "model": model,
        "caseIds": batch.case_ids,
        "modelInputSha256": text_sha256(query),
        "publicQuestionsSha256": text_sha256("\n\n".join(str(case.get("prompt") or "") for case in batch.cases)),
        "rawResponse": raw,
        "rawResponseSha256": text_sha256(raw),
        "predictions": predictions,
        "modelTrace": trace,
        "closedToolAudit": audit,
        "responseError": response_error,
        "callError": call_error,
        "disposition": disposition,
        "elapsedSec": round(time.monotonic() - started, 3),
    }
    artifact["artifactDigest"] = artifact_digest(artifact)
    return artifact


def write_case_results(*, artifact: dict[str, Any], batch: BatchSpec, output_root: Path) -> None:
    query = build_closed_subject_batch_query(manifest=batch.manifest, cases=list(batch.cases))
    results_dir = output_root / "results"
    for case in batch.cases:
        case_id = str(case.get("id") or "")
        prediction = artifact.get("predictions", {}).get(case_id)
        error = "" if artifact.get("disposition") == "accepted" and prediction else str(artifact.get("disposition") or "")
        record = {
            "schemaVersion": SCHEMA_VERSION,
            "id": case_id,
            "caseId": case_id,
            "benchmarkId": batch.benchmark_id,
            "mode": MODE,
            "model": artifact.get("model"),
            "prediction": prediction,
            "gold": None,
            "correct": None,
            "batchId": batch.batch_id,
            "batchArtifactDigest": artifact.get("artifactDigest"),
            "promptIdentity": prompt_identity(
                manifest=batch.manifest,
                case=case,
                model_input=query,
                builder_id=BUILDER_ID,
                builder_source=Path(__file__),
            ),
            "toolAccess": {
                "webSearch": False,
                "shellOrCode": False,
                "mcp": False,
                "readOnlySubjectDatabase": False,
                "customSkills": False,
                "universalEngine": False,
                "beta6Engine": False,
            },
            "closedToolAuditPassed": artifact.get("closedToolAudit", {}).get("passed") is True,
            "error": error,
            "elapsedSec": artifact.get("elapsedSec"),
        }
        write_json(results_dir / f"{case_id}.json", record)


def run_all(
    *,
    registry_path: Path,
    freeze_path: Path,
    output_root: Path,
    explicit_homes: list[Path],
    discovery_root: Path | None,
    maximum_new_batches: int,
    timeout_seconds: float,
    dry_run: bool,
) -> dict[str, Any]:
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    batches = validate_freeze(freeze, freeze_path=freeze_path, registry_path=registry_path)
    freeze_sha = sha256_file(freeze_path)
    model = str(freeze.get("model") or "")
    ledger_path = output_root / "solver-ledger.json"
    ledger_existed = ledger_path.exists()
    ledger: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "supervisorId": SUPERVISOR_ID,
        "freezeId": FREEZE_ID,
        "freezePath": str(freeze_path.resolve()),
        "freezeSha256": freeze_sha,
        "records": [],
    }
    if ledger_path.exists():
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        for field, expected in (("supervisorId", SUPERVISOR_ID), ("freezeId", FREEZE_ID), ("freezeSha256", freeze_sha)):
            if ledger.get(field) != expected:
                raise ValueError(f"solver ledger mismatch: {field}")
    records_by_id = {
        str(record.get("batchId") or ""): record
        for record in ledger.get("records", [])
        if isinstance(record, dict) and record.get("batchId")
    }
    if len(records_by_id) != len(ledger.get("records", [])):
        raise ValueError("solver ledger contains duplicate batch IDs")
    snapshot_added = False
    if not dry_run and not ledger.get("resourceGateAtStart"):
        ledger["resourceGateAtStart"] = collect_resource_snapshot(allow_existing_swap_single_task=True)
        snapshot_added = True
    homes = load_unique_homes(resolve_codex_home_paths(explicit_homes, discovery_root)) if not dry_run else []
    client = None
    if not dry_run:
        client = CodexHomeFailoverClient(
            homes=homes,
            default_model=model,
            timeout_seconds=min(MAX_REALTIME_SECONDS, max(1.0, float(timeout_seconds))),
            reasoning_effort=str(freeze.get("reasoningEffort") or "low"),
            verbosity="low",
            web_search_enabled=False,
            calculation_tools_enabled=False,
            domain_evidence_mcp_enabled=False,
            domain_beta6_frontier_enabled=False,
            skill_paths=[],
            agent_workspace_enabled=False,
            capture_workspace_artifacts=False,
            compact_skill_briefing_enabled=False,
            state_path=output_root / "pool-state.json",
        )
    new_batches = 0
    for index, batch in enumerate(batches, start=1):
        artifact_path = output_root / "batches" / f"{batch.batch_id}.json"
        existing = records_by_id.get(batch.batch_id)
        if existing and existing.get("disposition") in TERMINAL_DISPOSITIONS:
            if not artifact_path.is_file() or existing.get("artifactSha256") != sha256_file(artifact_path):
                raise ValueError(f"terminal batch artifact missing or changed: {batch.batch_id}")
            artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
            validate_batch_artifact(artifact, batch=batch, model=model, freeze_sha256=freeze_sha)
            continue
        if dry_run or (maximum_new_batches > 0 and new_batches >= maximum_new_batches):
            continue
        if client is None:
            raise RuntimeError("solver client is unavailable")
        artifact = run_batch(batch=batch, client=client, model=model, freeze_sha256=freeze_sha)
        write_json(artifact_path, artifact)
        validate_batch_artifact(artifact, batch=batch, model=model, freeze_sha256=freeze_sha)
        new_batches += 1
        trace = artifact.get("modelTrace") if isinstance(artifact.get("modelTrace"), dict) else {}
        record = {
            "batchId": batch.batch_id,
            "benchmarkId": batch.benchmark_id,
            "caseIds": batch.case_ids,
            "disposition": artifact.get("disposition"),
            "artifactPath": str(artifact_path.resolve()),
            "artifactSha256": sha256_file(artifact_path),
            "artifactDigest": artifact.get("artifactDigest"),
            "modelCalls": 1 if str(trace.get("status") or "") == "completed" else 0,
            "totalTokens": int(trace.get("tokenUsage", {}).get("totalTokens") or 0),
            "codexHomeAlias": str(trace.get("codexHomeAlias") or ""),
            "recordedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }
        records_by_id[batch.batch_id] = record
        if artifact.get("disposition") in TERMINAL_DISPOSITIONS:
            write_case_results(artifact=artifact, batch=batch, output_root=output_root)
        ordered = [records_by_id[key] for key in sorted(records_by_id)]
        ledger["records"] = ordered
        ledger["totals"] = ledger_totals(ordered, batches)
        ledger["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        ledger["complete"] = ledger["totals"]["terminalCases"] == EXPECTED_READY_CASES
        write_json(ledger_path, ledger)
        print(
            json.dumps(
                {
                    "index": index,
                    "batchId": batch.batch_id,
                    "benchmarkId": batch.benchmark_id,
                    "cases": len(batch.case_ids),
                    "disposition": artifact.get("disposition"),
                    "totals": ledger["totals"],
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        if artifact.get("disposition") == "infrastructure_failure":
            break
    ordered = [records_by_id[key] for key in sorted(records_by_id)]
    ledger["records"] = ordered
    ledger["totals"] = ledger_totals(ordered, batches)
    ledger["complete"] = ledger["totals"]["terminalCases"] == EXPECTED_READY_CASES
    if not dry_run and (new_batches > 0 or snapshot_added or not ledger_existed):
        ledger["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        write_json(ledger_path, ledger)
    return ledger


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze and run the full 619-case closed-tool Plain Codex no-DB benchmark.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    freeze_parser = subparsers.add_parser("freeze")
    freeze_parser.add_argument("--registry", type=Path, required=True)
    freeze_parser.add_argument("--output", type=Path, required=True)
    freeze_parser.add_argument("--model", default="gpt-5.6-luna")
    freeze_parser.add_argument("--reasoning-effort", default="low")
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--registry", type=Path, required=True)
    run_parser.add_argument("--freeze", type=Path, required=True)
    run_parser.add_argument("--output-root", type=Path, required=True)
    run_parser.add_argument("--codex-home", type=Path, action="append", default=[])
    run_parser.add_argument("--discover-codex-home-root", type=Path)
    run_parser.add_argument("--maximum-new-batches", type=int, default=0)
    run_parser.add_argument("--timeout-seconds", type=float, default=300.0)
    run_parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.command == "freeze":
        if args.output.exists():
            raise ValueError("refusing to overwrite an existing freeze")
        payload = build_freeze_payload(
            registry_path=args.registry,
            model=args.model,
            reasoning_effort=args.reasoning_effort,
        )
        write_json(args.output, payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    ledger = run_all(
        registry_path=args.registry,
        freeze_path=args.freeze,
        output_root=args.output_root,
        explicit_homes=args.codex_home,
        discovery_root=args.discover_codex_home_root,
        maximum_new_batches=args.maximum_new_batches,
        timeout_seconds=args.timeout_seconds,
        dry_run=args.dry_run,
    )
    print(json.dumps({"complete": ledger.get("complete"), "totals": ledger.get("totals")}, ensure_ascii=False, indent=2))
    return 0 if ledger.get("complete") or args.dry_run or args.maximum_new_batches > 0 else 3


if __name__ == "__main__":
    raise SystemExit(main())
