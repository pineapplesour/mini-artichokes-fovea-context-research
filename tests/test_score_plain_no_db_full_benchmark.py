from __future__ import annotations

from tools.score_plain_no_db_full_benchmark import (
    collect_unresolved_semantic_rows,
    group_id,
    judge_artifact_digest,
    judge_attempt_errors,
    partition_rows,
    validate_judge_artifact,
)


def _rows(count: int):
    return [
        {
            "id": f"q{index}",
            "question": "질문",
            "canonicalAnswer": "정답",
            "acceptableAliases": [],
            "candidateAnswer": "후보",
            "resultPath": f"/tmp/q{index}.json",
        }
        for index in range(count)
    ]


def _attempt(rows):
    from tools.score_subject_batch_semantic import POLICY_VERSION, semantic_batch_input_sha256

    return {
        "repeat": 1,
        "policyVersion": POLICY_VERSION,
        "semanticBatchInputSha256": semantic_batch_input_sha256(rows=rows, judge_model="judge"),
        "caseIds": [row["id"] for row in rows],
        "judgments": [
            {
                "id": row["id"],
                "equivalent": True,
                "contradiction": False,
                "missingCriticalFacts": [],
                "reason": "동일",
            }
            for row in rows
        ],
        "modelTrace": {
            "provider": "codex_exec",
            "status": "completed",
            "codexJsonlEventCount": 3,
            "codexJsonlInvalidLineCount": 0,
            "webSearchEnabled": False,
            "domainEvidenceMcpEnabled": False,
            "agentWorkspaceEnabled": False,
            "webSearchEvents": [],
            "commandExecutionEvents": [],
            "mcpToolEvents": [],
            "skillEvents": [],
            "tokenUsage": {"totalTokens": 100},
        },
        "closedToolTraceAudit": {
            "policy": "closed_codex_jsonl_no_web_shell_mcp_skill_v1",
            "passed": True,
            "violations": [],
        },
    }


def test_semantic_groups_are_bounded_and_stably_identified():
    rows = _rows(17)
    groups = partition_rows(rows)
    assert [len(group) for group in groups] == [8, 8, 1]
    case_ids = [row["id"] for row in groups[0]]
    assert group_id(benchmark_id="fixture", case_ids=case_ids, judge_model="judge") == group_id(
        benchmark_id="fixture", case_ids=case_ids, judge_model="judge"
    )


def test_judge_attempt_validation_rejects_tool_or_input_drift():
    rows = _rows(2)
    rows_by_id = {row["id"]: row for row in rows}
    attempt = _attempt(rows)
    assert judge_attempt_errors(attempt, rows_by_id=rows_by_id, judge_model="judge") == []
    attempt["semanticBatchInputSha256"] = "changed"
    assert "judge_input_changed" in judge_attempt_errors(attempt, rows_by_id=rows_by_id, judge_model="judge")


def test_partial_judge_artifact_can_resume_completed_repeats_without_new_calls():
    rows = _rows(2)
    attempt = _attempt(rows)
    artifact = {
        "schemaVersion": 1,
        "groupId": "judge-fixture",
        "benchmarkId": "fixture",
        "caseIds": [row["id"] for row in rows],
        "attempts": [attempt],
        "disposition": "in_progress",
    }
    artifact["artifactDigest"] = judge_artifact_digest(artifact)
    assert validate_judge_artifact(
        artifact,
        group_id_value="judge-fixture",
        benchmark_id="fixture",
        rows=rows,
        judge_model="judge",
        terminal=False,
    ) == [attempt]


def test_unresolved_collection_is_not_limited_before_partitioning(tmp_path):
    rows = _rows(17)
    public = {"cases": [{"id": row["id"], "prompt": row["question"]} for row in rows]}
    private = {
        "answers": [
            {"caseId": row["id"], "canonicalAnswer": row["canonicalAnswer"], "aliases": []}
            for row in rows
        ]
    }
    deterministic = {
        "cases": [
            {"caseId": row["id"], "verdict": "unresolved", "gradingPath": "semantic_judge_not_run"}
            for row in rows
        ]
    }
    for row in rows:
        (tmp_path / f"{row['id']}.json").write_text(
            __import__("json").dumps({"prediction": row["candidateAnswer"], "error": ""}), encoding="utf-8"
        )
    collected = collect_unresolved_semantic_rows(
        deterministic_report=deterministic,
        public_manifest=public,
        private_manifest=private,
        results_dir=tmp_path,
    )
    assert len(collected) == 17
    assert [len(group) for group in partition_rows(collected)] == [8, 8, 1]
