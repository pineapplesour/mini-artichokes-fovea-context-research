import json

import pytest

from tools.summarize_open_response_results import summarize_result_files


def _write_result(tmp_path, case_id, elapsed, total_tokens):
    path = tmp_path / f"{case_id}.json"
    path.write_text(
        json.dumps(
            {
                "caseId": case_id,
                "elapsedSec": elapsed,
                "modelTrace": {
                    "tokenUsage": {
                        "inputTokens": total_tokens - 3,
                        "cachedInputTokens": 0,
                        "outputTokens": 2,
                        "reasoningOutputTokens": 1,
                        "totalTokens": total_tokens,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def test_summarizes_only_explicit_result_files(tmp_path):
    first = _write_result(tmp_path, "a", 2.0, 10)
    second = _write_result(tmp_path, "b", 4.0, 20)

    report = summarize_result_files([first, second])

    assert report["totalCases"] == 2
    assert report["tokenUsage"]["totalTokens"] == 30
    assert report["latencySec"] == {"median": 3.0, "maximum": 4.0, "total": 6.0}
    assert [case["caseId"] for case in report["cases"]] == ["a", "b"]


def test_rejects_duplicate_case_ids(tmp_path):
    first = _write_result(tmp_path, "same", 2.0, 10)
    second_dir = tmp_path / "other"
    second_dir.mkdir()
    second = _write_result(second_dir, "same", 3.0, 12)

    with pytest.raises(ValueError, match="duplicate caseId"):
        summarize_result_files([first, second])
