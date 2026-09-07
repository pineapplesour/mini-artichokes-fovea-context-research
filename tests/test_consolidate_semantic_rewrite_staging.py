from __future__ import annotations

import pytest

from tools.consolidate_semantic_rewrite_staging import promote_pair, validate_ledger_shape
from tools.run_semantic_rewrite_staging import RewriteTarget


def _target(case_id: str) -> RewriteTarget:
    return RewriteTarget(
        benchmark_id="fixture",
        case_id=case_id,
        public_path=None,  # type: ignore[arg-type]
        private_path=None,  # type: ignore[arg-type]
        manifest={},
        case={"id": case_id, "prompt": "original"},
        answer_spec={"caseId": case_id},
    )


def test_validate_ledger_shape_requires_exact_unique_terminal_coverage():
    targets = [_target("q1"), _target("q2")]
    ledger = {
        "complete": True,
        "totals": {
            "targetCases": 2,
            "terminalCases": 2,
            "pending": 0,
            "infrastructureFailures": 0,
        },
        "records": [
            {"caseId": "q1", "disposition": "approved"},
            {"caseId": "q2", "disposition": "author_semantic_reject"},
        ],
    }

    assert set(validate_ledger_shape(ledger, targets)) == {"q1", "q2"}
    ledger["records"][1] = {"caseId": "q1", "disposition": "author_semantic_reject"}
    with pytest.raises(ValueError, match="duplicated"):
        validate_ledger_shape(ledger, targets)


def test_promote_pair_changes_only_approved_cases_and_aligns_private_status():
    public = {
        "benchmarkId": "fixture",
        "cases": [
            {
                "id": "approved",
                "prompt": "old approved prompt",
                "metadata": {
                    "openResponseConversion": {
                        "status": "needs_semantic_rewrite",
                        "riskReasons": ["choice_dependent"],
                    }
                },
            },
            {
                "id": "rejected",
                "prompt": "old rejected prompt",
                "metadata": {
                    "openResponseConversion": {
                        "status": "needs_semantic_rewrite",
                        "riskReasons": ["choice_dependent"],
                    }
                },
            },
        ],
    }
    private = {
        "answers": [
            {"caseId": "approved", "conversionStatus": "needs_semantic_rewrite"},
            {"caseId": "rejected", "conversionStatus": "needs_semantic_rewrite"},
        ]
    }
    artifact = {
        "author": {"rewrittenPrompt": "새로운 의미보존형 공개 질문입니다."},
        "inputDigest": "input-digest",
        "artifactDigest": "artifact-digest",
    }

    staged_public, staged_private, counts = promote_pair(
        public,
        private,
        {"approved": artifact},
        model="gpt-5.6-luna",
        review_repeats=2,
    )

    assert staged_public["cases"][0]["prompt"] == "새로운 의미보존형 공개 질문입니다."
    assert staged_public["cases"][1]["prompt"] == "old rejected prompt"
    assert staged_public["cases"][0]["metadata"]["openResponseConversion"]["status"] == "ready_semantic_rewrite"
    assert staged_public["cases"][1]["metadata"]["openResponseConversion"]["status"] == "needs_semantic_rewrite"
    assert staged_private["answers"][0]["conversionStatus"] == "ready_semantic_rewrite"
    assert staged_private["answers"][1]["conversionStatus"] == "needs_semantic_rewrite"
    assert counts == {"needs_semantic_rewrite": 1, "ready_semantic_rewrite": 1}
    assert public["cases"][0]["prompt"] == "old approved prompt"
