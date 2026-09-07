from __future__ import annotations

from pathlib import Path

from tools.run_plain_db_only_full_benchmark import (
    BUILDER_ID,
    MODE,
    audit_db_only_trace,
    build_db_only_subject_batch_query,
    load_db_batch_plan,
    optional_db_completion_prompt,
)


def _trace() -> dict:
    return {
        "provider": "codex_exec",
        "status": "completed",
        "codexJsonlEventCount": 3,
        "codexJsonlInvalidLineCount": 0,
        "webSearchEnabled": False,
        "domainEvidenceMcpEnabled": True,
        "domainBeta6FrontierEnabled": False,
        "agentWorkspaceEnabled": False,
        "skillsAvailable": [],
        "webSearchEvents": [],
        "commandExecutionEvents": [],
        "mcpToolEvents": [],
        "skillEvents": [],
        "tokenUsage": {"totalTokens": 100},
        "elapsedSec": 1.0,
    }


def test_db_query_and_transport_make_database_use_optional_but_every_other_tool_closed():
    manifest = {"product": "tcm", "language": "ko", "cases": []}
    cases = [{"id": "q1", "prompt": "진단은?"}]
    query = build_db_only_subject_batch_query(manifest=manifest, cases=cases)
    transport = optional_db_completion_prompt(
        [{"role": "user", "content": query}], domain_evidence_product="tcm"
    )
    assert "using it is optional" in query
    assert "you decide whether it is useful and may answer without calling it" in transport
    assert "Web search, shell, code" in query
    assert MODE.endswith("db_only_optional")
    assert BUILDER_ID.endswith("db_only_optional")


def test_db_trace_allows_zero_database_calls_and_rejects_other_tools():
    assert audit_db_only_trace(
        _trace(), public_question="진단은?", db_product="tcm", maximum_tokens=1_000
    )["passed"] is True
    unsafe = _trace()
    unsafe["commandExecutionEvents"] = [{"command": "pwd", "status": "completed"}]
    assert audit_db_only_trace(
        unsafe, public_question="진단은?", db_product="tcm", maximum_tokens=1_000
    )["passed"] is False


def test_db_plan_matches_same_619_cases_in_80_arm_specific_batches():
    root = Path(__file__).resolve().parents[1]
    registry = root / "runs/luna-pilot/semantic-rewrite-all-v1/combined/evaluation_registry.open_response.staging.json"
    batches, inputs, _registry = load_db_batch_plan(registry)
    case_ids = [case_id for batch in batches for case_id in batch.case_ids]
    assert len(batches) == 80
    assert len(case_ids) == len(set(case_ids)) == 619
    assert all(batch.batch_id.startswith("plaindb2-") for batch in batches)
    assert len(inputs) == 15
