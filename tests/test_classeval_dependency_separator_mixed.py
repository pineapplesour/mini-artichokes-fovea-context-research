from __future__ import annotations

import json

from tools import run_classeval_dependency_separator_mixed as mixed
from tools import run_classeval_overlap_repair_tail as frozen_tail
from tools import overlap_split_merge_candidate as scope_operator


def test_gemma_payload_keeps_approved_generation_contract():
    payload = mixed._gemma_payload("frozen prompt")

    assert payload["contents"] == [{"role": "user", "parts": [{"text": "frozen prompt"}]}]
    assert payload["generationConfig"]["temperature"] == 0.6
    assert payload["generationConfig"]["maxOutputTokens"] == 16_384
    assert payload["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "high"}


def test_screen_gate_requires_both_usable_threshold_and_novelty():
    def record(usable, novel=False, whole=False):
        return {"usable": usable, "novelCaseTask": novel,
                "newWholePassVsOldE": whole}

    assert mixed._screen_gate([record(True)] * 24 + [record(False)] * 8)["proceed"] is False
    assert mixed._screen_gate([record(True)] * 24 + [record(False)] * 7
                              + [record(True, novel=True)])["proceed"] is True
    assert mixed._screen_gate([record(True)] * 24 + [record(False)] * 7
                              + [record(True, whole=True)])["proceed"] is True
    assert mixed._screen_gate([record(True)] * 23 + [record(False, novel=True)] * 9)["proceed"] is False


def test_screen_is_exactly_one_gemma_call_per_unresolved_task():
    assert mixed.EXPECTED_FAILURES == 32
    assert mixed.GEMMA_KEY_COUNT == 10


def test_gemma_call_uses_stop_and_parse_as_validity_gate(tmp_path, monkeypatch):
    row = {"task_id": "ClassEval_0", "_dataset": "classeval-pro",
           "test": [], "test_classes": []}
    answer = "```python\nclass Demo:\n    pass\n```"
    monkeypatch.setattr(mixed, "_gemma_request", lambda prompt, key: {
        "answer": answer, "finishReason": "STOP", "usageMetadata": {
            "promptTokenCount": 11, "candidatesTokenCount": 7,
            "thoughtsTokenCount": 5, "totalTokenCount": 23,
        }, "duration_seconds": 1.25, "apiErrorStatus": None, "httpStatus": 200,
        "modelVersion": mixed.GEMMA_MODEL, "responseId": "response-1",
        "modelVersionMatch": True, "nonTextItems": [], "overBudget": False,
        "errorType": None,
    })
    monkeypatch.setattr(mixed.base, "evaluate", lambda row, source: {
        "passed": False, "cases": {}, "expectedCount": 0,
    })

    result = mixed._gemma_call(row, tmp_path / "b", "prompt",
                               key="test-key", ordinal=4)
    receipt = json.loads((tmp_path / "b" / "receipt.json").read_text())

    assert result["valid"] is True
    assert receipt["finishReason"] == "STOP"
    assert receipt["modelVersion"] == mixed.GEMMA_MODEL
    assert receipt["responseId"] == "response-1"
    assert receipt["httpStatus"] == 200
    assert receipt["normalizedUsage"]["thoughtsTokenCount"] == 5
    assert receipt["taskOrdinal"] == 4
    assert "test-key" not in json.dumps(receipt)


def test_gemma_call_rejects_truncation_and_model_mismatch(tmp_path, monkeypatch):
    row = {"task_id": "ClassEval_0", "_dataset": "classeval-pro",
           "test": [], "test_classes": []}
    answer = "```python\nclass Demo:\n    pass\n```"
    monkeypatch.setattr(mixed.base, "evaluate", lambda row, source:
                        (_ for _ in ()).throw(AssertionError("invalid output was evaluated")))

    monkeypatch.setattr(mixed, "_gemma_request", lambda prompt, key: {
        "answer": answer, "finishReason": "MAX_TOKENS", "usageMetadata": {},
        "duration_seconds": 1.0, "apiErrorStatus": None, "httpStatus": 200,
        "modelVersion": mixed.GEMMA_MODEL, "responseId": "response-truncated",
        "modelVersionMatch": True, "nonTextItems": [], "overBudget": False,
        "errorType": None,
    })
    truncated = mixed._gemma_call(row, tmp_path / "truncated", "prompt",
                                  key="test-key", ordinal=0)
    assert truncated["valid"] is False
    assert json.loads((tmp_path / "truncated" / "receipt.json").read_text())["finishReason"] == "MAX_TOKENS"

    monkeypatch.setattr(mixed, "_gemma_request", lambda prompt, key: {
        "answer": answer, "finishReason": "STOP", "usageMetadata": {},
        "duration_seconds": 1.0, "apiErrorStatus": None, "httpStatus": 200,
        "modelVersion": "unexpected-model", "responseId": "response-wrong",
        "modelVersionMatch": False, "nonTextItems": [], "overBudget": False,
        "errorType": "ModelVersionMismatch",
    })
    wrong_model = mixed._gemma_call(row, tmp_path / "wrong-model", "prompt",
                                    key="test-key", ordinal=0)
    receipt = json.loads((tmp_path / "wrong-model" / "receipt.json").read_text())
    assert wrong_model["valid"] is False
    assert receipt["modelVersion"] == "unexpected-model"
    assert receipt["errorType"] == "ModelVersionMismatch"


def test_gemma_call_rejects_stop_text_with_function_call_part(tmp_path, monkeypatch):
    row = {"task_id": "ClassEval_0", "_dataset": "classeval-pro",
           "test": [], "test_classes": []}
    answer = "```python\nclass Demo:\n    pass\n```"
    monkeypatch.setattr(mixed.base, "evaluate", lambda row, source:
                        (_ for _ in ()).throw(AssertionError("non-text output was evaluated")))
    monkeypatch.setattr(mixed, "_gemma_request", lambda prompt, key: {
        "answer": answer, "finishReason": "STOP", "usageMetadata": {},
        "duration_seconds": 1.0, "apiErrorStatus": None, "httpStatus": 200,
        "modelVersion": mixed.GEMMA_MODEL, "responseId": "response-function",
        "modelVersionMatch": True, "nonTextItems": ["functionCall"],
        "overBudget": False, "errorType": "NonTextResponse",
    })

    result = mixed._gemma_call(row, tmp_path / "function-call", "prompt",
                               key="test-key", ordinal=0)
    receipt = json.loads((tmp_path / "function-call" / "receipt.json").read_text())
    assert result["valid"] is False
    assert receipt["nonTextItems"] == ["functionCall"]


def test_gemma_request_detects_hidden_non_text_part(monkeypatch):
    payload = {
        "modelVersion": mixed.GEMMA_MODEL, "responseId": "response-function",
        "usageMetadata": {}, "candidates": [{
            "finishReason": "STOP", "content": {"parts": [
                {"text": "```python\nclass Demo: pass\n```"},
                {"functionCall": {"name": "unexpected"}},
            ]},
        }],
    }
    monkeypatch.setattr(mixed.GeminiDirectChatClient, "_post_generate_content",
                        lambda self, model, request: payload)

    response = mixed._gemma_request("prompt", "test-key")
    assert response["nonTextItems"] == ["functionCall"]
    assert response["errorType"] == "NonTextResponse"
    assert response["modelVersionMatch"] is True


def test_gemma_call_rejects_response_over_timeout(tmp_path, monkeypatch):
    row = {"task_id": "ClassEval_0", "_dataset": "classeval-pro",
           "test": [], "test_classes": []}
    monkeypatch.setattr(mixed, "_gemma_request", lambda prompt, key: {
        "answer": "```python\nclass Demo: pass\n```", "finishReason": "STOP",
        "usageMetadata": {}, "duration_seconds": 120.01,
        "apiErrorStatus": None, "httpStatus": 200,
        "modelVersion": mixed.GEMMA_MODEL, "responseId": "response-late",
        "modelVersionMatch": True, "nonTextItems": [], "overBudget": False,
        "errorType": None,
    })
    monkeypatch.setattr(mixed.base, "evaluate", lambda row, source:
                        (_ for _ in ()).throw(AssertionError("late output was evaluated")))

    result = mixed._gemma_call(row, tmp_path / "late", "prompt",
                               key="test-key", ordinal=0)
    receipt = json.loads((tmp_path / "late" / "receipt.json").read_text())
    assert result["valid"] is False
    assert receipt["overBudget"] is True


def test_screen_record_prompt_matches_cached_b_for_anchor_reordering(tmp_path, monkeypatch):
    source = "class Demo:\n    def first(self):\n        pass\n    def second(self):\n        pass\n    def third(self):\n        pass\n"
    row = {"task_id": "ClassEval_0", "class_name": "Demo", "skeleton": source,
           "_dataset": "classeval-pro", "test": [], "test_classes": []}
    prefix = {"source": source, "report": {
        "passed": False,
        "cases": {"case": {"status": "failed", "methods": ["first"]}},
    }}
    labels, ordered, feedback, _ = mixed._e_context(row, prefix)
    plan = scope_operator.build_scope_plans(ordered)["E"]
    cached_b_prompt = frozen_tail._independent_prompt(
        row, prefix, plan, "B", ordered, feedback)
    cache_path = tmp_path / "cached" / "a"
    captured = {}

    cache = {"items": {"ClassEval_0": {
        "source": source, "report": prefix["report"], "valid": True,
        "path": cache_path,
    }}, "states": {"ClassEval_0": {"report": {"passed": False}}}}

    def fake_view(row, prefix, candidate, evaluate_fn):
        return candidate["source"], {"passed": False, "cases": {}}, True, 1, (), ()

    def fake_call(row, out, prompt, *, key, ordinal):
        captured["prompt"] = prompt
        return {"source": source, "report": {"passed": False, "cases": {}},
                "valid": True, "path": tmp_path / "new-b",
                "receipt": {"sourceSha": "b-sha"}}

    monkeypatch.setattr(mixed.frozen_tail, "_full_view", fake_view)
    monkeypatch.setattr(mixed, "_gemma_call", fake_call)
    record = mixed._screen_record(row, prefix, cache, 0, tmp_path / "run", ["k"] * 10)

    assert captured["prompt"] == cached_b_prompt
    assert ordered != labels
    assert record["rawBEvalCalls"] == 1
    assert record["cachedACanonicalEvalCalls"] == 1
    assert record["bCanonicalEvalCalls"] == 1
    assert record["canonicalEvalCalls"] == 2


def test_mixed_runner_reuses_frozen_e_view_and_defers_follow_up():
    assert mixed.frozen_tail._full_view is frozen_tail._full_view
    assert mixed.PROTOCOL.name == "2026-09-05-classeval-dependency-separator-mixed-v1.md"
