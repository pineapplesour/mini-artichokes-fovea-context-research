from __future__ import annotations

import json
from pathlib import Path

from tools.run_semantic_rewrite_staging import (
    RewriteTarget,
    build_child_command,
    case_output_dir,
    classify_artifact,
    ledger_totals,
    load_targets,
)


def _closed_trace(tokens: int = 10) -> dict:
    return {
        "provider": "codex_exec",
        "status": "completed",
        "codexJsonlInvalidLineCount": 0,
        "tokenUsage": {"totalTokens": tokens},
        "webSearchEvents": [],
        "commandExecutionEvents": [],
        "mcpToolEvents": [],
    }


def test_load_targets_keeps_only_rewrite_cases_and_sorts_by_prompt_length(tmp_path: Path):
    public = {
        "benchmarkId": "fixture",
        "taskType": "open_response",
        "cases": [
            {"id": "long", "prompt": "x" * 30, "metadata": {"openResponseConversion": {"status": "needs_semantic_rewrite"}}},
            {"id": "ready", "prompt": "ready", "metadata": {"openResponseConversion": {"status": "ready_hide_options"}}},
            {"id": "short", "prompt": "x" * 12, "metadata": {"openResponseConversion": {"status": "needs_semantic_rewrite"}}},
        ],
    }
    private = {"answers": [{"caseId": "long"}, {"caseId": "ready"}, {"caseId": "short"}]}
    (tmp_path / "public.json").write_text(json.dumps(public), encoding="utf-8")
    (tmp_path / "private.json").write_text(json.dumps(private), encoding="utf-8")
    registry = {"entries": [{"benchmarkId": "fixture", "publicManifest": "public.json", "privateManifest": "private.json"}]}
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(json.dumps(registry), encoding="utf-8")

    targets, inputs = load_targets(registry_path)

    assert [target.case_id for target in targets] == ["short", "long"]
    assert len(inputs) == 3


def test_case_output_dir_reuses_existing_legacy_and_bounds_unsafe_names(tmp_path: Path):
    legacy = tmp_path / "semantic-rewrite-safe-id-v1"
    legacy.mkdir()
    assert case_output_dir(tmp_path, "safe-id") == legacy
    generated = case_output_dir(tmp_path, "매우 긴 문항/식별자" * 30)
    assert generated.parent == tmp_path
    assert len(generated.name.encode("utf-8")) < 255


def test_classify_artifact_distinguishes_approval_and_meaning_rejection():
    approved = {"approved": True}
    rejected = {
        "approved": False,
        "author": {"status": "ok"},
        "authorTrace": _closed_trace(),
        "error": "",
        "deterministicErrors": [],
        "traceErrors": [],
        "reviews": [
            {
                "verdict": "reject",
                "answerableWithoutChoices": True,
                "uniquelyTargetsCanonical": True,
                "canonicalDirectlyAnswers": True,
                "sameKnowledgeTarget": False,
                "factuallyPlausible": True,
                "noAnswerLeakage": True,
                "trace": _closed_trace(),
            },
            {
                "verdict": "reject",
                "answerableWithoutChoices": True,
                "uniquelyTargetsCanonical": True,
                "canonicalDirectlyAnswers": True,
                "sameKnowledgeTarget": False,
                "factuallyPlausible": True,
                "noAnswerLeakage": True,
                "trace": _closed_trace(),
            },
        ],
    }
    assert classify_artifact(approved, review_repeats=2) == "approved"
    assert classify_artifact(rejected, review_repeats=2) == "review_semantic_reject"


def test_build_child_command_is_exactly_one_case_and_three_calls(tmp_path: Path):
    target = RewriteTarget(
        benchmark_id="fixture",
        case_id="q1",
        public_path=tmp_path / "public.json",
        private_path=tmp_path / "private.json",
        manifest={},
        case={"prompt": "question"},
        answer_spec={},
    )
    command = build_child_command(
        target,
        tmp_path / "out",
        model="gpt-5.6-luna",
        reasoning_effort="low",
        timeout_seconds=180,
        review_repeats=2,
        homes=[tmp_path / ".codex-6"],
    )
    assert command[command.index("--case-id") + 1] == "q1"
    assert command[command.index("--max-cases") + 1] == "1"
    assert command[command.index("--max-model-calls") + 1] == "3"
    assert command.count("--case-id") == 1


def test_ledger_totals_do_not_close_infrastructure_failures():
    records = [
        {"disposition": "approved", "modelCalls": 3, "totalTokens": 30},
        {"disposition": "review_semantic_reject", "modelCalls": 3, "totalTokens": 40},
        {"disposition": "infrastructure_failure", "modelCalls": 1, "totalTokens": 5},
    ]
    totals = ledger_totals(records, 4)
    assert totals == {
        "targetCases": 4,
        "terminalCases": 2,
        "approved": 1,
        "rejected": 1,
        "infrastructureFailures": 1,
        "pending": 2,
        "modelCalls": 7,
        "totalTokens": 75,
    }
