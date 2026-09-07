from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from tools import classeval_ordinary_prefix as prefix_loader
from tools import dependency_separator_overlap as separator
from tools import run_classeval_dependency_separator_mixed as gemma_base
from tools import run_classeval_dependency_separator_overlap as graph
from tools import run_classeval_gemma_luna_paired as paired
from tools import run_classeval_overlap_repair_tail as frozen_tail


REPO = Path(__file__).resolve().parents[1]
PARENT = REPO / "runs/classeval-pro300-text-overlap-20260905-development-v2"
E_CACHE = REPO / "runs/classeval-pro300-overlap-repair-tail-20260905-development-v1"
SCREEN = REPO / "runs/classeval-pro300-gemma-minimal-screen-20260906-development-v1"
O_CACHE = REPO / "runs/classeval-pro300-dependency-separator-overlap-20260905-development-v1"


def _row():
    return {"task_id": "ClassEval_0", "class_name": "Demo", "_dataset": "classeval-pro",
            "_data_sha": paired.base.PRO_SHA, "_data_index": 0,
            "skeleton": "class Demo:\n    def run(self):\n        return 1\n",
            "test": [], "test_classes": []}


def _response():
    return {
        "answer": "```python\nclass Demo:\n    def run(self):\n        return 1\n```",
        "finishReason": "STOP", "usageMetadata": {"promptTokenCount": 2,
        "candidatesTokenCount": 3, "totalTokenCount": 5}, "duration_seconds": 1.0,
        "apiErrorStatus": None, "httpStatus": 200, "modelVersion": paired.GEMMA_MODEL,
        "responseId": "response-test", "modelVersionMatch": True,
        "nonTextItems": [], "overBudget": False, "errorType": None,
    }


def _cached_item(directory: Path, prompt: str):
    directory.mkdir()
    (directory / "prompt.txt").write_text(prompt)
    (directory / "contract.json").write_text(
        json.dumps({"promptSha": paired._sha_text(prompt)}))
    return {"source": "cached source", "report": {"passed": False, "cases": {}},
            "valid": True, "path": directory, "cached": True}


def test_gemma_call_records_arm_correct_label_and_minimal_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(paired, "_minimal_request", lambda prompt, key: _response())
    monkeypatch.setattr(paired.base, "evaluate", lambda row, source:
                        {"passed": False, "cases": {}, "expectedCount": 0})

    result = paired._gemma_call(_row(), tmp_path / "b", "O_B", "prompt",
                                key="not-written", ordinal=0)
    contract = json.loads((tmp_path / "b" / "contract.json").read_text())
    receipt = json.loads((tmp_path / "b" / "receipt.json").read_text())

    assert result["valid"] is True
    assert contract["label"] == receipt["label"] == "O_B"
    assert contract["thinkingLevel"] == paired.GEMMA_THINKING == "minimal"
    assert contract["maxOutputTokens"] == 16_384
    assert "not-written" not in json.dumps(receipt)


def test_screen_cache_validates_all_u32_prompts_and_tamper_guard(tmp_path):
    if not all(path.is_dir() for path in (PARENT, E_CACHE, SCREEN, O_CACHE)):
        pytest.skip("completed development artifacts are not available")
    rows = paired.base.load_data("classeval-pro")
    for ordinal, row in enumerate(rows):
        row["_data_index"] = ordinal
    prefixes = prefix_loader.load_ordinary_prefix(PARENT)
    screen = paired._validate_screen_cache(SCREEN, PARENT, E_CACHE, rows, prefixes)
    assert len(screen["items"]) == 32

    task = "ClassEval_24"
    source = SCREEN / task / "E" / "b"
    tampered = tmp_path / "b"
    shutil.copytree(source, tampered)
    (tampered / "prompt.txt").write_text(
        (tampered / "prompt.txt").read_text() + "\nTAMPERED\n")
    row = next(item for item in rows if item["task_id"] == task)
    with pytest.raises(ValueError, match="prompt mismatch"):
        paired._load_screen_gemma_item(row, tampered, paired._e_prompt(row, prefixes[task]), 24)


def test_frozen_delegation_points_remain_exact():
    assert paired.frozen_tail._execute_arm is frozen_tail._execute_arm
    assert paired.graph.run_task is graph.run_task
    assert paired.gemma_base._gemma_request is gemma_base._gemma_request


def test_graph_o_prompt_path_matches_frozen_builder_for_all_u32(tmp_path):
    if not PARENT.is_dir():
        pytest.skip("completed parent artifacts are not available")
    rows = paired.base.load_data("classeval-pro")
    prefixes = prefix_loader.load_ordinary_prefix(PARENT)
    unresolved = [row for row in rows if not prefixes[row["task_id"]]["report"].get("passed")]
    assert len(unresolved) == 32
    captured = {}

    def fake_evaluate(row, source):
        return {"passed": False, "cases": {}, "expectedCount": 0}

    def fake_call(row, out, label, prompt):
        captured.setdefault(row["task_id"], {})[label] = prompt
        return {"source": prefixes[row["task_id"]]["source"],
                "report": prefixes[row["task_id"]]["report"],
                "valid": True, "path": Path(out)}

    for row in unresolved:
        task_id, prefix = row["task_id"], prefixes[row["task_id"]]
        labels = frozen_tail.target_method_labels(row, prefix["source"]) or ("whole_program",)
        ordered, anchor = frozen_tail.choose_failure_anchor(labels, prefix["report"])
        plan = separator.build_separator_plan(prefix["source"], row["class_name"], ordered)
        feedback = frozen_tail.observed_feedback(prefix["report"], ordered)
        feedback["bridgeHint"] = anchor
        expected_b = paired.graph._common_prompt(row, prefix, plan, ordered, feedback, "B", anchor)
        graph.run_task(row, prefix, tmp_path / task_id, call_fn=fake_call,
                       evaluate_fn=fake_evaluate)
        assert captured[task_id]["dependency-O-B"] == expected_b


def test_router_cached_e_and_o_boundaries_match_all_u32_without_calls(tmp_path):
    """Exercise the production cache-return paths, with no model/evaluator call."""

    if not all(path.is_dir() for path in (PARENT, E_CACHE, SCREEN, O_CACHE)):
        pytest.skip("completed development artifacts are not available")
    rows = paired.base.load_data("classeval-pro")
    for ordinal, row in enumerate(rows):
        row["_data_index"] = ordinal
    prefixes = prefix_loader.load_ordinary_prefix(PARENT)
    unresolved = [row for row in rows if not prefixes[row["task_id"]]["report"].get("passed")]
    e_cache = paired._validate_e_cache(E_CACHE, PARENT, rows, prefixes)
    screen_cache = paired._validate_screen_cache(SCREEN, PARENT, E_CACHE, rows, prefixes)
    o_cache = paired._validate_o_cache(O_CACHE, PARENT, E_CACHE, rows, prefixes)
    e_counters = {"cachedA": 0, "cachedB": 0, "newGemma": 0, "newLuna": 0,
                  "freshRawEval": 0}
    o_counters = {"cachedA": 0, "cachedB": 0, "newGemma": 0, "newLuna": 0,
                  "freshRawEval": 0}
    e_paths, o_paths = {}, {}
    e_router = paired._call_router("E", e_cache, screen_cache, o_cache, [], e_counters, e_paths)
    o_router = paired._call_router("O", e_cache, screen_cache, o_cache, ["k"] * 10,
                                   o_counters, o_paths)
    for row in unresolved:
        task_id, prefix = row["task_id"], prefixes[row["task_id"]]
        e_a = e_router(row, tmp_path / "e" / task_id / "a", "tail-E-A",
                       paired._e_prompt(row, prefix, "A"))
        e_b = e_router(row, tmp_path / "e" / task_id / "b", "tail-E-B",
                       paired._e_prompt(row, prefix, "B"))
        o_a = o_router(row, tmp_path / "o" / task_id / "a", "dependency-O-A",
                       paired._o_prompt(row, prefix, "A"))
        assert e_a["path"] == e_cache["items"][task_id]["path"]
        assert e_b["path"] == screen_cache["items"][task_id]["path"]
        assert o_a["path"] == o_cache["items"][task_id]["path"]
    assert e_counters == {"cachedA": 32, "cachedB": 32, "newGemma": 0,
                          "newLuna": 0, "freshRawEval": 0}
    assert o_counters == {"cachedA": 32, "cachedB": 0, "newGemma": 0,
                          "newLuna": 0, "freshRawEval": 0}


def test_call_router_has_e_cached_but_o_fresh_b(tmp_path, monkeypatch):
    row = _row()
    cached_a = _cached_item(tmp_path / "cached-a", "a")
    cached_b = _cached_item(tmp_path / "cached-b", "b")
    counters = {"cachedA": 0, "cachedB": 0, "newGemma": 0, "newLuna": 0,
                "freshRawEval": 0}
    paths = {}
    e_router = paired._call_router("E", {"items": {"ClassEval_0": cached_a}},
                                   {"items": {"ClassEval_0": cached_b}}, {}, [], counters, paths)
    assert e_router(row, tmp_path / "unused-a", "tail-E-A", "a")["cached"] is True
    assert e_router(row, tmp_path / "unused-b", "tail-E-B", "b")["cached"] is True

    monkeypatch.setattr(paired, "_gemma_call", lambda *args, **kwargs:
                        {"source": row["skeleton"], "report": {"passed": False, "cases": {}},
                         "valid": True, "path": Path(args[1]), "cached": False})
    o_counters = {"cachedA": 0, "cachedB": 0, "newGemma": 0, "newLuna": 0,
                  "freshRawEval": 0}
    o_router = paired._call_router("O", {}, {}, {"items": {"ClassEval_0": cached_a}},
                                   ["k"] * 10, o_counters, {})
    result = o_router(row, tmp_path / "o-b", "dependency-O-B", "prompt")
    assert result["cached"] is False
    assert o_counters["newGemma"] == 1
