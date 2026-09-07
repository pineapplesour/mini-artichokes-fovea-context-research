from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.run_plain_no_db_full_benchmark import (
    BUILDER_ID,
    EXPECTED_BATCHES,
    EXPECTED_MODEL,
    EXPECTED_READY_CASES,
    MODE,
    audit_closed_solver_trace,
    build_freeze_payload,
    build_closed_subject_batch_query,
    load_batch_plan,
    parse_batch_answer,
    validate_freeze,
)


def _manifest() -> dict:
    return {"product": "tcm", "language": "ko", "cases": []}


def _trace() -> dict:
    return {
        "provider": "codex_exec",
        "status": "completed",
        "codexJsonlEventCount": 3,
        "codexJsonlInvalidLineCount": 0,
        "webSearchEnabled": False,
        "domainEvidenceMcpEnabled": False,
        "domainBeta6FrontierEnabled": False,
        "agentWorkspaceEnabled": False,
        "webSearchEvents": [],
        "commandExecutionEvents": [],
        "mcpToolEvents": [],
        "skillEvents": [],
        "skillsAvailable": [],
        "tokenUsage": {"totalTokens": 100},
        "elapsedSec": 1.0,
    }


def test_closed_query_and_parser_bind_every_id_without_tools():
    cases = [{"id": "q1", "prompt": "진단은?"}, {"id": "q2", "prompt": "기관은?"}]
    query = build_closed_subject_batch_query(manifest=_manifest(), cases=cases)
    assert "No web search, database, shell, code, MCP, skill" in query
    assert MODE in "codex_native_subject_batch_plain_v6_closed_no_db"
    assert BUILDER_ID.endswith("closed_no_db")
    raw = json.dumps({"answers": [{"id": "q1", "finalAnswer": "A"}, {"id": "q2", "finalAnswer": "B"}]})
    assert parse_batch_answer(raw, expected_ids=["q1", "q2"]) == {"q1": "A", "q2": "B"}
    with pytest.raises(ValueError, match="ids_do_not_match"):
        parse_batch_answer(raw, expected_ids=["q2", "q1"])


def test_closed_trace_audit_rejects_any_database_or_tool_event():
    assert audit_closed_solver_trace(_trace(), maximum_tokens=1_000)["passed"] is True
    unsafe = _trace()
    unsafe["mcpToolEvents"] = [{"tool": "search_domain_evidence"}]
    assert audit_closed_solver_trace(unsafe, maximum_tokens=1_000)["passed"] is False
    over = _trace()
    over["tokenUsage"]["totalTokens"] = 1_001
    assert "batch_token_budget_exceeded" in audit_closed_solver_trace(over, maximum_tokens=1_000)["violations"]


def test_current_staging_plan_contains_exactly_619_unique_ready_cases():
    repo_root = Path(__file__).resolve().parents[1]
    registry = repo_root / "runs/luna-pilot/semantic-rewrite-all-v1/combined/evaluation_registry.open_response.staging.json"
    batches, inputs, _payload = load_batch_plan(registry)
    case_ids = [case_id for batch in batches for case_id in batch.case_ids]
    assert len(batches) == EXPECTED_BATCHES == 80
    assert len(case_ids) == EXPECTED_READY_CASES == 619
    assert len(set(case_ids)) == 619
    assert len(inputs) == 15


def test_freeze_binds_closed_boundary_model_inputs_and_plan(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    registry = repo_root / "runs/luna-pilot/semantic-rewrite-all-v1/combined/evaluation_registry.open_response.staging.json"
    payload = build_freeze_payload(registry_path=registry, model=EXPECTED_MODEL, reasoning_effort="low")
    freeze_path = tmp_path / "freeze.json"
    freeze_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    assert len(validate_freeze(payload, freeze_path=freeze_path, registry_path=registry)) == EXPECTED_BATCHES
    payload["toolBoundary"]["readOnlySubjectDatabase"] = True
    with pytest.raises(ValueError, match="tool boundary"):
        validate_freeze(payload, freeze_path=freeze_path, registry_path=registry)
