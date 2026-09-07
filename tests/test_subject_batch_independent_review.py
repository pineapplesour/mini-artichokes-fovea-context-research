import json

import pytest

from tools.review_subject_batch_predictions import (
    MODE,
    build_review_query,
    parse_review_response,
    run_independent_review,
)


def _manifest():
    return {
        "benchmarkId": "open.fixture.v2",
        "sourceBenchmarkId": "mcq.fixture.v1",
        "product": "tcm",
        "cases": [{"id": "q1", "prompt": "진단은?"}, {"id": "q2", "prompt": "기관은?"}],
    }


def _rows():
    return [
        {"id": "q1", "question": "진단은?", "draftAnswer": "돌발진"},
        {"id": "q2", "question": "기관은?", "draftAnswer": "기관 A"},
    ]


def _raw():
    return json.dumps(
        {
            "reviews": [
                {"id": "q1", "verdict": "keep", "finalAnswer": "돌발진", "issue": ""},
                {"id": "q2", "verdict": "correct", "finalAnswer": "기관 B", "issue": "관할 기관 오류"},
            ]
        },
        ensure_ascii=False,
    )


def _trace():
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
        "elapsedSec": 1.0,
    }


class FakeClient:
    def complete(self, messages, *, model):
        return _raw()

    def consume_last_call_trace(self):
        return _trace()


def test_review_contract_requires_exact_keep_and_substantive_correction():
    query = build_review_query(manifest=_manifest(), rows=_rows())
    assert "no answer key or choices" in query
    assert parse_review_response(_raw(), expected_rows=_rows())[1]["finalAnswer"] == "기관 B"

    changed_keep = _raw().replace('"finalAnswer": "돌발진"', '"finalAnswer": "소아 장미진"')
    with pytest.raises(ValueError, match="kept_subject_batch_answer_changed"):
        parse_review_response(changed_keep, expected_rows=_rows())


def test_review_runner_binds_one_draft_batch_and_writes_revised_results(tmp_path):
    public = tmp_path / "public.json"
    public.write_text(json.dumps(_manifest(), ensure_ascii=False), encoding="utf-8")
    draft = tmp_path / "draft"
    draft.mkdir()
    for case_id, prediction in (("q1", "돌발진"), ("q2", "기관 A")):
        (draft / f"{case_id}.json").write_text(
            json.dumps({"prediction": prediction, "error": "", "batchId": "batch-one"}, ensure_ascii=False),
            encoding="utf-8",
        )

    summary = run_independent_review(
        public_path=public,
        draft_results_dir=draft,
        output_dir=tmp_path / "review",
        llm_client=FakeClient(),
        model="fixture",
        case_ids=["q1", "q2"],
    )

    assert summary["mode"] == MODE
    assert summary["total"] == {"cases": 2, "kept": 1, "corrected": 1, "accepted": 2, "errors": 0}
    revised = json.loads((tmp_path / "review/results/q2.json").read_text(encoding="utf-8"))
    assert revised["originalPrediction"] == "기관 A"
    assert revised["prediction"] == "기관 B"
    assert revised["reviewVerdict"] == "correct"
    receipt = json.loads((tmp_path / "review/review-receipt.json").read_text(encoding="utf-8"))
    assert receipt["closedToolTraceAudit"]["passed"] is True
