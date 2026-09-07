#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import benchmark_provider
from tools.codex_home_failover import CodexHomeFailoverClient, load_unique_homes, resolve_codex_home_paths
from tools.database_attestation import database_identity
from tools.prompt_identity import canonical_json_sha256, prompt_identity, text_sha256
from tools.resource_gate import collect_resource_snapshot
from tools.run_codex_home_pool import audit_domain_evidence_mcp_trace
from tools.run_open_response_benchmark import PUBLIC_PRODUCT_LABELS, infer_open_response_language
from tools.run_plain_no_db_full_benchmark import (
    BatchSpec,
    DEFAULT_BATCH_SIZE,
    DEFAULT_MAX_BATCH_TOKENS,
    DEFAULT_MAX_PROMPT_CHARS,
    EXPECTED_BATCHES,
    EXPECTED_MODEL,
    EXPECTED_READY_CASES,
    EXPECTED_REASONING_EFFORT,
    EXPECTED_TOTAL_CASES,
    MAX_REALTIME_SECONDS,
    SCHEMA_VERSION,
    artifact_digest,
    load_batch_plan as load_no_db_batch_plan,
    parse_batch_answer,
    sha256_file,
    write_json,
)
from tools.run_subject_batch_benchmark import DB_ENV_BY_PRODUCT, DB_PRODUCT_BY_PUBLIC_PRODUCT


MODE = "codex_native_subject_batch_plain_v7_db_only_optional"
BUILDER_ID = "subject_batch_open_response_query_v7_db_only_optional"
SUPERVISOR_ID = "plain-db-only-full-sequential-v1"
FREEZE_ID = "plain-codex-db-only-full-v2-20260721"
MAX_DOMAIN_TOOL_EVENTS = 2
TERMINAL_DISPOSITIONS = {"accepted", "response_quarantine", "policy_quarantine"}
DEFAULT_DATABASE_PATHS = {
    "lawkey": Path("/home/pineapple/bunjum2/work16/저장파일/unified_precedent_db_2026-04-10_run3/precedents.sqlite3"),
    "tcm": Path("/home/pineapple/bunjum2/tcm/corpus/tcm/tcm.sqlite3"),
    "simli": Path("/home/pineapple/bunjum2/simli/data/db/psych.sqlite"),
    "islam": Path("/home/pineapple/bunjum2/religion/corpus/islam/islam.sqlite3"),
    "catholic": Path("/home/pineapple/bunjum2/religion/corpus/catholic/catholic.sqlite3"),
}


def build_db_only_subject_batch_query(*, manifest: dict[str, Any], cases: list[dict[str, Any]]) -> str:
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
        "No answer choices are available. Do not infer one item's answer from another item. A mounted read-only subject database "
        "is available, but you must decide whether it is useful; using it is optional. Across this entire batch, use at most two "
        "database calls and only for genuinely unresolved items. Database queries must be short abstract concept queries of at most "
        "64 characters and eight tokens. Web search, shell, code, other MCP servers, skills, Universal, and Beta6 are unavailable and "
        "forbidden. Never look up or restate the question, benchmark, exam item, removed choices, or an answer key in a query."
        + response_instruction
        + "\n\nReturn exactly one JSON object with this shape and no extra keys or commentary: "
        + '{"answers":[{"id":"item id","finalAnswer":"concise answer"}]}. '
        + "Return each supplied id exactly once and preserve input order.\n\nPUBLIC_ITEMS_JSON:\n"
        + json.dumps(items, ensure_ascii=False, separators=(",", ":"))
    )


def optional_db_completion_prompt(
    messages: list[dict[str, str]],
    *,
    domain_evidence_product: str,
) -> str:
    normalized = [
        {"role": str(item.get("role") or "user"), "content": str(item.get("content") or "")}
        for item in messages
        if isinstance(item, dict)
    ]
    return (
        "You are serving as a stateless language-model completion endpoint. The mounted read-only domain database is available, "
        "but you decide whether it is useful and may answer without calling it. You may use only search_domain_evidence and "
        "get_domain_source from the domain_evidence MCP server. If you search, set product="
        + json.dumps(domain_evidence_product, ensure_ascii=False)
        + ", keep limit at 3 and snippet_chars at 600, and use one short abstract candidate concept plus at most one distinguishing "
        "fact. Never inspect files, run shell commands, browse the web, use Beta6, or modify anything. Never translate, summarize, "
        "paraphrase, or copy the problem into a query; never search benchmark names, question IDs, exams, options, answer keys, or "
        "historical predictions. Return only the assistant response that follows the conversation.\n\nCONVERSATION_JSON:\n"
        + json.dumps(normalized, ensure_ascii=False, separators=(",", ":"))
    )


class OptionalDbCodexExecLLMClient(benchmark_provider.CodexExecLLMClient):
    """Codex transport exposing the mounted DB without forcing a tool call."""

    def _complete_attempt(
        self,
        prompt: str,
        *,
        active_model: str,
        timeout: float,
        public_question_for_guard: str,
    ) -> str:
        del prompt
        with tempfile.TemporaryDirectory(prefix="plain-db-only-codex-") as temp_dir:
            output_path = Path(temp_dir) / "last_message.txt"
            command = [
                self.executable,
                "exec",
                "--ephemeral",
                "--ignore-user-config",
                "--ignore-rules",
                "--skip-git-repo-check",
                "--sandbox",
                "read-only",
                "--cd",
                temp_dir,
                "--model",
                active_model,
                "--config",
                f'model_reasoning_effort="{self.reasoning_effort}"',
                "--config",
                f'model_verbosity="{self.verbosity}"',
                "--config",
                'web_search="disabled"',
                "--config",
                "features.shell_tool=false",
                "--config",
                f"mcp_servers.domain_evidence.command={json.dumps(sys.executable)}",
                "--config",
                "mcp_servers.domain_evidence.args="
                + json.dumps([str(self.domain_evidence_server)], ensure_ascii=True, separators=(",", ":")),
                "--config",
                f"mcp_servers.domain_evidence.cwd={json.dumps(str(self.domain_evidence_repo_root))}",
                "--config",
                "mcp_servers.domain_evidence.env_vars="
                + json.dumps(
                    [
                        benchmark_provider.DOMAIN_EVIDENCE_DB_ENV_BY_PRODUCT[self.domain_evidence_product],
                        benchmark_provider.DOMAIN_EVIDENCE_PUBLIC_QUESTION_ENV,
                        benchmark_provider.DOMAIN_EVIDENCE_QUERY_GUARD_ENV,
                    ],
                    ensure_ascii=True,
                    separators=(",", ":"),
                ),
                "--config",
                'mcp_servers.domain_evidence.enabled_tools=["search_domain_evidence","get_domain_source"]',
                "--config",
                'mcp_servers.domain_evidence.default_tools_approval_mode="approve"',
                "--config",
                "mcp_servers.domain_evidence.required=true",
                "--config",
                "mcp_servers.domain_evidence.tool_timeout_sec=60.0",
                "--json",
                "--output-last-message",
                str(output_path),
                "-",
            ]
            environment = dict(os.environ)
            environment["TOKIO_WORKER_THREADS"] = str(self.worker_threads)
            environment["RAYON_NUM_THREADS"] = str(self.worker_threads)
            environment["UV_THREADPOOL_SIZE"] = str(self.worker_threads)
            environment[benchmark_provider.DOMAIN_EVIDENCE_PUBLIC_QUESTION_ENV] = public_question_for_guard
            environment[benchmark_provider.DOMAIN_EVIDENCE_QUERY_GUARD_ENV] = "1"
            completed = benchmark_provider._invoke_codex(
                command,
                prompt=optional_db_completion_prompt(
                    [{"role": "user", "content": public_question_for_guard}],
                    domain_evidence_product=self.domain_evidence_product,
                ),
                timeout=timeout,
                environment=environment,
            )
            attempt_trace = benchmark_provider._parse_codex_jsonl_trace(completed.stdout)
            attempt_trace["skillsAvailable"] = []
            self._record_attempt_trace(attempt_trace)
            if completed.returncode != 0:
                detail = str(completed.stderr or completed.stdout or "").strip()[-1_000:]
                raise RuntimeError(f"Codex Exec failed with exit={completed.returncode}: {detail}")
            answer = output_path.read_text(encoding="utf-8").strip() if output_path.exists() else ""
            if not answer:
                raise RuntimeError("Codex Exec returned an empty final message")
            return answer


def load_db_batch_plan(registry_path: Path) -> tuple[list[BatchSpec], dict[str, str], dict[str, Any]]:
    source_batches, inputs, registry = load_no_db_batch_plan(registry_path)
    batches: list[BatchSpec] = []
    for source in source_batches:
        public_sha = inputs[str(source.public_path)]
        batch_id = "plaindb2-" + canonical_json_sha256(
            {
                "freezeId": FREEZE_ID,
                "benchmarkId": source.benchmark_id,
                "caseIds": source.case_ids,
                "builderId": BUILDER_ID,
                "publicManifestSha256": public_sha,
            }
        )[:20]
        batches.append(
            BatchSpec(
                batch_id=batch_id,
                benchmark_id=source.benchmark_id,
                public_path=source.public_path,
                private_path=source.private_path,
                manifest=source.manifest,
                cases=source.cases,
            )
        )
    if len(batches) != EXPECTED_BATCHES:
        raise ValueError(f"expected {EXPECTED_BATCHES} database batches, found {len(batches)}")
    return batches, inputs, registry


def attest_databases(paths: dict[str, Path]) -> dict[str, dict[str, Any]]:
    if set(paths) != set(DEFAULT_DATABASE_PATHS):
        raise ValueError("database product set changed")
    identities: dict[str, dict[str, Any]] = {}
    for product, path in sorted(paths.items()):
        identity = database_identity(path)
        if identity.get("fixtureWarning"):
            raise ValueError(f"refusing fixture-sized database: {product}")
        identities[product] = identity
    return identities


def implementation_hashes() -> dict[str, str]:
    paths = [
        Path(__file__).resolve(),
        REPO_ROOT / "tools" / "benchmark_provider.py",
        REPO_ROOT / "tools" / "codex_home_failover.py",
        REPO_ROOT / "tools" / "database_attestation.py",
        REPO_ROOT / "tools" / "domain_evidence_mcp_server.py",
        REPO_ROOT / "tools" / "luna_host_prefetch.py",
        REPO_ROOT / "tools" / "prompt_identity.py",
        REPO_ROOT / "tools" / "run_codex_home_pool.py",
        REPO_ROOT / "tools" / "run_plain_no_db_full_benchmark.py",
        REPO_ROOT / "tools" / "run_subject_batch_benchmark.py",
        REPO_ROOT / "tools" / "score_open_responses.py",
        REPO_ROOT / "tools" / "score_plain_no_db_full_benchmark.py",
        REPO_ROOT / "tools" / "score_subject_batch_semantic.py",
        REPO_ROOT / "tools" / "score_plain_db_only_full_benchmark.py",
        REPO_ROOT / ".agents" / "skills" / "solve-with-domain-evidence" / "scripts" / "search_domain_evidence.py",
        REPO_ROOT / "shared_platform" / "domain_adapters.py",
        REPO_ROOT / "shared_platform" / "products.py",
        REPO_ROOT / "shared_platform" / "search.py",
    ]
    return {str(path): sha256_file(path) for path in paths}


def build_freeze_payload(*, registry_path: Path, model: str, reasoning_effort: str) -> dict[str, Any]:
    if model != EXPECTED_MODEL or reasoning_effort != EXPECTED_REASONING_EFFORT:
        raise ValueError("the comparison freeze requires the fixed solver model and reasoning effort")
    batches, inputs, _registry = load_db_batch_plan(registry_path)
    databases = attest_databases(DEFAULT_DATABASE_PATHS)
    plan = [
        {
            "batchId": batch.batch_id,
            "benchmarkId": batch.benchmark_id,
            "databaseProduct": DB_PRODUCT_BY_PUBLIC_PRODUCT[str(batch.manifest.get("product") or "").lower()],
            "caseIds": batch.case_ids,
        }
        for batch in batches
    ]
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
        "databaseIdentities": databases,
        "implementationFiles": implementation_hashes(),
        "inventory": {"readyCases": EXPECTED_READY_CASES, "totalCases": EXPECTED_TOTAL_CASES, "batches": EXPECTED_BATCHES},
        "batchPolicy": {
            "batchSize": DEFAULT_BATCH_SIZE,
            "maximumPromptCharacters": DEFAULT_MAX_PROMPT_CHARS,
            "maximumBatchTokens": DEFAULT_MAX_BATCH_TOKENS,
            "maximumDatabaseCalls": MAX_DOMAIN_TOOL_EVENTS,
            "databaseUseOptional": True,
            "sequentialCallsOnly": True,
            "freshSolverOpportunityPerCase": True,
            "priorSolverResultsReused": False,
        },
        "toolBoundary": {
            "webSearch": False,
            "shellOrCode": False,
            "mcpOtherThanReadOnlySubjectDatabase": False,
            "readOnlySubjectDatabase": True,
            "customSkills": False,
            "universalEngine": False,
            "beta6Engine": False,
        },
        "planSha256": canonical_json_sha256(plan),
        "plan": plan,
    }


def validate_freeze(freeze: dict[str, Any], *, freeze_path: Path, registry_path: Path) -> list[BatchSpec]:
    batches, inputs, _registry = load_db_batch_plan(registry_path)
    expected_databases = attest_databases(
        {product: Path(identity["path"]) for product, identity in freeze.get("databaseIdentities", {}).items()}
    )
    expected_plan = [
        {
            "batchId": batch.batch_id,
            "benchmarkId": batch.benchmark_id,
            "databaseProduct": DB_PRODUCT_BY_PUBLIC_PRODUCT[str(batch.manifest.get("product") or "").lower()],
            "caseIds": batch.case_ids,
        }
        for batch in batches
    ]
    checks = {
        "schemaVersion": SCHEMA_VERSION,
        "freezeId": FREEZE_ID,
        "status": "frozen_before_solver_calls",
        "model": EXPECTED_MODEL,
        "reasoningEffort": EXPECTED_REASONING_EFFORT,
        "mode": MODE,
        "builderId": BUILDER_ID,
        "registryPath": str(registry_path.resolve()),
        "registrySha256": sha256_file(registry_path.resolve()),
        "canonicalInputs": inputs,
        "databaseIdentities": expected_databases,
        "implementationFiles": implementation_hashes(),
        "inventory": {"readyCases": EXPECTED_READY_CASES, "totalCases": EXPECTED_TOTAL_CASES, "batches": EXPECTED_BATCHES},
        "batchPolicy": {
            "batchSize": DEFAULT_BATCH_SIZE,
            "maximumPromptCharacters": DEFAULT_MAX_PROMPT_CHARS,
            "maximumBatchTokens": DEFAULT_MAX_BATCH_TOKENS,
            "maximumDatabaseCalls": MAX_DOMAIN_TOOL_EVENTS,
            "databaseUseOptional": True,
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
    expected_boundary = {
        "webSearch": False,
        "shellOrCode": False,
        "mcpOtherThanReadOnlySubjectDatabase": False,
        "readOnlySubjectDatabase": True,
        "customSkills": False,
        "universalEngine": False,
        "beta6Engine": False,
    }
    if boundary != expected_boundary:
        raise ValueError("freeze tool boundary changed")
    if not freeze_path.is_file():
        raise ValueError("freeze file is missing")
    return batches


def audit_db_only_trace(
    trace: Any,
    *,
    public_question: str,
    db_product: str,
    maximum_tokens: int,
) -> dict[str, Any]:
    violations: list[str] = []
    if not isinstance(trace, dict) or not trace:
        return {"policy": "db_only_optional_v1", "passed": False, "violations": ["trace_missing"]}
    if str(trace.get("provider") or "") not in {"codex_exec", "openai_codex_exec"}:
        violations.append("provider_not_codex_exec")
    if str(trace.get("status") or "") != "completed":
        violations.append("trace_not_completed")
    if int(trace.get("codexJsonlEventCount") or 0) <= 0 or int(trace.get("codexJsonlInvalidLineCount") or 0) != 0:
        violations.append("jsonl_trace_invalid")
    for field, expected in (
        ("webSearchEnabled", False),
        ("domainEvidenceMcpEnabled", True),
        ("domainBeta6FrontierEnabled", False),
        ("agentWorkspaceEnabled", False),
    ):
        if trace.get(field) is not expected:
            violations.append(f"{field}_changed")
    for field, label in (
        ("webSearchEvents", "web_event_present"),
        ("commandExecutionEvents", "command_event_present"),
        ("skillEvents", "skill_event_present"),
    ):
        if trace.get(field) != []:
            violations.append(label)
    if trace.get("skillsAvailable") is not None and trace.get("skillsAvailable") != []:
        violations.append("skills_available")
    domain = audit_domain_evidence_mcp_trace(
        trace,
        public_question=public_question,
        expected_product=db_product,
        maximum_calls=MAX_DOMAIN_TOOL_EVENTS,
    )
    if not domain["passed"]:
        violations.append("database_anti_cheating_audit_failed")
    events = trace.get("mcpToolEvents") if isinstance(trace.get("mcpToolEvents"), list) else []
    if any(str(event.get("status") or "") != "completed" for event in events if isinstance(event, dict)):
        violations.append("database_call_not_completed")
    if any(str(event.get("tool") or "") not in {"search_domain_evidence", "get_domain_source"} for event in events if isinstance(event, dict)):
        violations.append("non_basic_database_tool_used")
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
        "policy": "db_only_optional_v1",
        "passed": not violations,
        "violations": list(dict.fromkeys(violations)),
        "database": domain,
        "tokens": tokens,
        "elapsedSec": elapsed,
    }


def validate_batch_artifact(
    artifact: dict[str, Any],
    *,
    batch: BatchSpec,
    model: str,
    freeze_sha256: str,
    database: dict[str, Any],
    db_product: str,
) -> None:
    query = build_db_only_subject_batch_query(manifest=batch.manifest, cases=list(batch.cases))
    if (
        artifact.get("schemaVersion") != SCHEMA_VERSION
        or artifact.get("freezeId") != FREEZE_ID
        or artifact.get("freezeSha256") != freeze_sha256
        or artifact.get("batchId") != batch.batch_id
        or artifact.get("benchmarkId") != batch.benchmark_id
        or artifact.get("mode") != MODE
        or artifact.get("model") != model
        or artifact.get("caseIds") != batch.case_ids
        or artifact.get("databaseProduct") != db_product
        or artifact.get("database") != database
    ):
        raise ValueError(f"database batch artifact contract mismatch: {batch.batch_id}")
    if artifact.get("modelInputSha256") != text_sha256(query):
        raise ValueError(f"database batch model input changed: {batch.batch_id}")
    raw = str(artifact.get("rawResponse") or "")
    if artifact.get("rawResponseSha256") != text_sha256(raw) or artifact.get("artifactDigest") != artifact_digest(artifact):
        raise ValueError(f"database batch artifact digest changed: {batch.batch_id}")
    trace = artifact.get("modelTrace")
    audit = audit_db_only_trace(
        trace,
        public_question="\n\n".join(str(case.get("prompt") or "") for case in batch.cases),
        db_product=db_product,
        maximum_tokens=DEFAULT_MAX_BATCH_TOKENS,
    )
    if artifact.get("dbOnlyAudit") != audit:
        raise ValueError(f"database batch trace audit changed: {batch.batch_id}")
    disposition = str(artifact.get("disposition") or "")
    if disposition not in TERMINAL_DISPOSITIONS | {"infrastructure_failure"}:
        raise ValueError(f"database batch disposition invalid: {batch.batch_id}")
    if disposition in TERMINAL_DISPOSITIONS and str(trace.get("status") or "") != "completed":
        raise ValueError(f"terminal database batch lacks completion trace: {batch.batch_id}")
    if disposition == "accepted":
        parsed = parse_batch_answer(raw, expected_ids=batch.case_ids)
        if artifact.get("predictions") != parsed or audit.get("passed") is not True:
            raise ValueError(f"accepted database batch no longer validates: {batch.batch_id}")


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
        "databaseCalls": sum(int(record.get("databaseCalls") or 0) for record in terminal),
        "databaseSearches": sum(int(record.get("databaseSearches") or 0) for record in terminal),
    }


def run_batch(
    *,
    batch: BatchSpec,
    client: CodexHomeFailoverClient,
    model: str,
    freeze_sha256: str,
    database: dict[str, Any],
    db_product: str,
) -> dict[str, Any]:
    query = build_db_only_subject_batch_query(manifest=batch.manifest, cases=list(batch.cases))
    env_name = DB_ENV_BY_PRODUCT[db_product]
    previous = os.environ.get(env_name)
    os.environ[env_name] = str(database["path"])
    raw = ""
    predictions: dict[str, str] = {}
    response_error = ""
    call_error = ""
    started = time.monotonic()
    try:
        try:
            raw = str(client.complete([{"role": "user", "content": query}], model=model) or "")
            try:
                predictions = parse_batch_answer(raw, expected_ids=batch.case_ids)
            except Exception as exc:
                response_error = str(exc)[:1_000]
        except Exception as exc:
            call_error = str(exc)[:1_000]
        trace_value = client.consume_last_call_trace()
    finally:
        if previous is None:
            os.environ.pop(env_name, None)
        else:
            os.environ[env_name] = previous
    trace = trace_value if isinstance(trace_value, dict) else {}
    public_question = "\n\n".join(str(case.get("prompt") or "") for case in batch.cases)
    audit = audit_db_only_trace(
        trace,
        public_question=public_question,
        db_product=db_product,
        maximum_tokens=DEFAULT_MAX_BATCH_TOKENS,
    )
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
        "databaseProduct": db_product,
        "database": database,
        "modelInputSha256": text_sha256(query),
        "publicQuestionsSha256": text_sha256(public_question),
        "rawResponse": raw,
        "rawResponseSha256": text_sha256(raw),
        "predictions": predictions,
        "modelTrace": trace,
        "dbOnlyAudit": audit,
        "responseError": response_error,
        "callError": call_error,
        "disposition": disposition,
        "elapsedSec": round(time.monotonic() - started, 3),
    }
    artifact["artifactDigest"] = artifact_digest(artifact)
    return artifact


def write_case_results(*, artifact: dict[str, Any], batch: BatchSpec, output_root: Path) -> None:
    query = build_db_only_subject_batch_query(manifest=batch.manifest, cases=list(batch.cases))
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
            "databaseProduct": artifact.get("databaseProduct"),
            "databaseIdentity": artifact.get("database"),
            "toolAccess": {
                "webSearch": False,
                "shellOrCode": False,
                "mcpOtherThanReadOnlySubjectDatabase": False,
                "readOnlySubjectDatabase": True,
                "customSkills": False,
                "universalEngine": False,
                "beta6Engine": False,
            },
            "dbOnlyAuditPassed": artifact.get("dbOnlyAudit", {}).get("passed") is True,
            "databaseCalls": len(artifact.get("modelTrace", {}).get("mcpToolEvents") or []),
            "error": error,
            "elapsedSec": artifact.get("elapsedSec"),
        }
        write_json(output_root / "results" / f"{case_id}.json", record)


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
    databases = freeze["databaseIdentities"]
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
    if ledger_existed:
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
        raise ValueError("solver ledger contains duplicate database batch IDs")
    snapshot_added = False
    if not dry_run and not ledger.get("resourceGateAtStart"):
        ledger["resourceGateAtStart"] = collect_resource_snapshot(allow_existing_swap_single_task=True)
        snapshot_added = True
    homes = load_unique_homes(resolve_codex_home_paths(explicit_homes, discovery_root)) if not dry_run else []
    clients: dict[str, CodexHomeFailoverClient] = {}

    def client_for(product: str) -> CodexHomeFailoverClient:
        if product not in clients:
            clients[product] = CodexHomeFailoverClient(
                homes=homes,
                default_model=model,
                timeout_seconds=min(MAX_REALTIME_SECONDS, max(1.0, float(timeout_seconds))),
                reasoning_effort=str(freeze.get("reasoningEffort") or "low"),
                verbosity="low",
                web_search_enabled=False,
                calculation_tools_enabled=False,
                domain_evidence_mcp_enabled=True,
                domain_beta6_frontier_enabled=False,
                domain_evidence_repo_root=REPO_ROOT,
                domain_evidence_product=product,
                skill_paths=[],
                agent_workspace_enabled=False,
                capture_workspace_artifacts=False,
                compact_skill_briefing_enabled=False,
                state_path=output_root / f"pool-state-{product}.json",
                client_factory=OptionalDbCodexExecLLMClient,
            )
        return clients[product]

    new_batches = 0
    for index, batch in enumerate(batches, start=1):
        public_product = str(batch.manifest.get("product") or "").strip().lower()
        db_product = DB_PRODUCT_BY_PUBLIC_PRODUCT[public_product]
        database = databases[db_product]
        artifact_path = output_root / "batches" / f"{batch.batch_id}.json"
        existing = records_by_id.get(batch.batch_id)
        if existing and existing.get("disposition") in TERMINAL_DISPOSITIONS:
            if not artifact_path.is_file() or existing.get("artifactSha256") != sha256_file(artifact_path):
                raise ValueError(f"terminal database batch artifact missing or changed: {batch.batch_id}")
            validate_batch_artifact(
                json.loads(artifact_path.read_text(encoding="utf-8")),
                batch=batch,
                model=model,
                freeze_sha256=freeze_sha,
                database=database,
                db_product=db_product,
            )
            continue
        if dry_run or (maximum_new_batches > 0 and new_batches >= maximum_new_batches):
            continue
        artifact = run_batch(
            batch=batch,
            client=client_for(db_product),
            model=model,
            freeze_sha256=freeze_sha,
            database=database,
            db_product=db_product,
        )
        write_json(artifact_path, artifact)
        validate_batch_artifact(
            artifact,
            batch=batch,
            model=model,
            freeze_sha256=freeze_sha,
            database=database,
            db_product=db_product,
        )
        new_batches += 1
        trace = artifact.get("modelTrace") if isinstance(artifact.get("modelTrace"), dict) else {}
        mcp_events = trace.get("mcpToolEvents") if isinstance(trace.get("mcpToolEvents"), list) else []
        record = {
            "batchId": batch.batch_id,
            "benchmarkId": batch.benchmark_id,
            "databaseProduct": db_product,
            "caseIds": batch.case_ids,
            "disposition": artifact.get("disposition"),
            "artifactPath": str(artifact_path.resolve()),
            "artifactSha256": sha256_file(artifact_path),
            "artifactDigest": artifact.get("artifactDigest"),
            "modelCalls": 1 if str(trace.get("status") or "") == "completed" else 0,
            "totalTokens": int(trace.get("tokenUsage", {}).get("totalTokens") or 0),
            "databaseCalls": len(mcp_events),
            "databaseSearches": sum(str(event.get("tool") or "") == "search_domain_evidence" for event in mcp_events if isinstance(event, dict)),
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
                    "databaseCalls": len(mcp_events),
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
    parser = argparse.ArgumentParser(description="Freeze and run the full 619-case optional read-only DB Plain Codex benchmark.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    freeze_parser = subparsers.add_parser("freeze")
    freeze_parser.add_argument("--registry", type=Path, required=True)
    freeze_parser.add_argument("--output", type=Path, required=True)
    freeze_parser.add_argument("--model", default=EXPECTED_MODEL)
    freeze_parser.add_argument("--reasoning-effort", default=EXPECTED_REASONING_EFFORT)
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
        print(json.dumps({key: payload[key] for key in ("freezeId", "status", "inventory", "toolBoundary", "planSha256")}, ensure_ascii=False, indent=2))
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
