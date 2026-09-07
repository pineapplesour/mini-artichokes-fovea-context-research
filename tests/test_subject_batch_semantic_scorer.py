import json

import pytest

from tools.score_subject_batch_semantic import (
    build_semantic_batch_prompt,
    finalize_semantic_batch,
    parse_semantic_batch_response,
    run_semantic_batch_attempt,
    unresolved_semantic_rows,
)


def _rows():
    return [
        {
            "id": "q1",
            "question": "진단은?",
            "canonicalAnswer": "돌발진",
            "acceptableAliases": [],
            "candidateAnswer": "돌발진(소아 장미진)",
            "resultPath": "/run/q1.json",
        },
        {
            "id": "q2",
            "question": "기관은?",
            "canonicalAnswer": "시·군·구",
            "acceptableAliases": [],
            "candidateAnswer": "다른 기관",
            "resultPath": "/run/q2.json",
        },
    ]


def _closed_trace():
    return {
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
    }


class FakeJudge:
    def __init__(self, raw, trace=None):
        self.raw = raw
        self.trace = trace or _closed_trace()

    def complete(self, messages, *, model):
        return self.raw

    def consume_last_call_trace(self):
        return self.trace


def _raw(first=True, second=False):
    return json.dumps(
        {
            "judgments": [
                {"id": "q1", "equivalent": first, "contradiction": False, "missingCriticalFacts": [], "reason": "one"},
                {"id": "q2", "equivalent": second, "contradiction": False, "missingCriticalFacts": [], "reason": "two"},
            ]
        },
        ensure_ascii=False,
    )


def test_prompt_and_parser_preserve_ids_and_hide_distractors():
    prompt = build_semantic_batch_prompt(rows=_rows(), repeat=1)
    assert "multiple-choice distractors" in prompt
    assert "돌발진(소아 장미진)" in prompt
    parsed = parse_semantic_batch_response(_raw(), expected_ids=["q1", "q2"])
    assert [row["id"] for row in parsed] == ["q1", "q2"]
    with pytest.raises(ValueError, match="ids_do_not_match"):
        parse_semantic_batch_response(_raw(), expected_ids=["q2", "q1"])


def test_attempt_requires_closed_trace_and_finalizer_uses_two_agreeing_batches():
    first = run_semantic_batch_attempt(
        rows=_rows(), repeat=1, judge_client=FakeJudge(_raw()), judge_model="fixture"
    )
    second = run_semantic_batch_attempt(
        rows=_rows(), repeat=2, judge_client=FakeJudge(_raw()), judge_model="fixture"
    )
    deterministic = {
        "benchmarkId": "fixture",
        "cases": [
            {"caseId": "q1", "verdict": "unresolved", "gradingPath": "semantic_judge_not_run"},
            {"caseId": "q2", "verdict": "unresolved", "gradingPath": "semantic_judge_not_run"},
        ],
    }

    report = finalize_semantic_batch(
        deterministic_report=deterministic,
        rows=_rows(),
        attempts=[first, second],
        judge_model="fixture",
    )

    assert report["passed"] == 1
    assert report["failed"] == 1
    assert report["unresolved"] == 0
    assert all(case["gradingPath"] == "semantic_batch_judge_2of2" for case in report["cases"])

    unsafe = _closed_trace()
    unsafe["webSearchEnabled"] = True
    rejected = run_semantic_batch_attempt(
        rows=_rows(), repeat=1, judge_client=FakeJudge(_raw(), trace=unsafe), judge_model="fixture"
    )
    assert "closed_tool_trace_failed" in rejected["error"]


def test_unresolved_rows_exclude_quarantined_artifacts(tmp_path):
    public = {"cases": [{"id": "q1", "prompt": "진단은?"}, {"id": "q2", "prompt": "기관은?"}]}
    private = {
        "answers": [
            {"caseId": "q1", "canonicalAnswer": "돌발진", "aliases": []},
            {"caseId": "q2", "canonicalAnswer": "시군구", "aliases": []},
        ]
    }
    deterministic = {
        "cases": [
            {"caseId": "q1", "verdict": "unresolved", "gradingPath": "semantic_judge_not_run"},
            {"caseId": "q2", "verdict": "unresolved", "gradingPath": "result_artifact_error"},
        ]
    }
    (tmp_path / "q1.json").write_text('{"prediction":"소아 장미진","error":""}', encoding="utf-8")
    (tmp_path / "q2.json").write_text('{"prediction":"시군구","error":"failed"}', encoding="utf-8")

    rows = unresolved_semantic_rows(
        deterministic_report=deterministic,
        public_manifest=public,
        private_manifest=private,
        results_dir=tmp_path,
    )

    assert [row["id"] for row in rows] == ["q1"]
