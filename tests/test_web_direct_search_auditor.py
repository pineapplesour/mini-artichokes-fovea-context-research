from __future__ import annotations

import json

from tools.audit_web_direct_search import audit


def _write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def test_auditor_accepts_general_fact_search_and_calculation(tmp_path):
    public = tmp_path / "public.json"
    results = tmp_path / "results"
    _write_json(
        public,
        {
            "benchmarkId": "fixture",
            "cases": [
                {
                    "id": "q1",
                    "prompt": "재무 심사에서 이자부 예금 비율 기준은?\nA. 5%\nB. 10%\nC. 25%\nD. 30%",
                }
            ],
        },
    )
    _write_json(
        results / "q1.json",
        {
            "modelTrace": {
                "webSearchEnabled": True,
                "webSearchEvents": [
                    {"query": "Islamic equity screening interest bearing deposits threshold", "action": {"type": "search"}}
                ],
                "commandExecutionEvents": [
                    {"command": "python3 -c 'print(5/100)'", "status": "completed"}
                ],
            }
        },
    )

    report = audit(public_path=public, results_dir=results)

    assert report["passed"] is True
    assert report["webSearchQueryCount"] == 1
    assert report["commandExecutionCount"] == 1


def test_auditor_rejects_question_source_exact_option_and_local_file_search(tmp_path):
    public = tmp_path / "public.json"
    results = tmp_path / "results"
    _write_json(
        public,
        {
            "benchmarkId": "fixture",
            "cases": [
                {
                    "id": "q1",
                    "prompt": "재무 심사에서 이자부 예금 비율 기준은?\nA. 총 시가총액의 5퍼센트\nB. 총 시가총액의 30퍼센트",
                }
            ],
        },
    )
    _write_json(
        results / "q1.json",
        {
            "modelTrace": {
                "webSearchEnabled": True,
                "webSearchEvents": [
                    {"query": "CISI sample questions 총 시가총액의 30퍼센트", "action": {"type": "search"}}
                ],
                "commandExecutionEvents": [{"command": "cat benchmarks/private.json"}],
            }
        },
    )

    report = audit(public_path=public, results_dir=results)
    kinds = {item["kind"] for item in report["violations"]}

    assert report["passed"] is False
    assert "source_or_answer_search" in kinds
    assert "exact_option_search" in kinds
    assert "local_file_access_command" in kinds


def test_auditor_can_limit_a_canary_to_explicit_case_ids(tmp_path):
    public = tmp_path / "public.json"
    results = tmp_path / "results"
    _write_json(
        public,
        {
            "benchmarkId": "fixture",
            "cases": [
                {"id": "q1", "prompt": "첫 문제\nA. 갑\nB. 을"},
                {"id": "q2", "prompt": "둘째 문제\nA. 갑\nB. 을"},
            ],
        },
    )
    _write_json(
        results / "q2.json",
        {"modelTrace": {"webSearchEnabled": True, "webSearchEvents": [], "commandExecutionEvents": []}},
    )

    report = audit(public_path=public, results_dir=results, case_ids=["q2"])

    assert report["passed"] is True
    assert report["cases"] == 1


def test_auditor_can_require_search_trace_and_evidence_summary(tmp_path):
    public = tmp_path / "public.json"
    results = tmp_path / "results"
    _write_json(
        public,
        {"benchmarkId": "fixture", "cases": [{"id": "q1", "prompt": "기준은?\nA. 갑\nB. 을"}]},
    )
    _write_json(
        results / "q1.json",
        {
            "modelTrace": {"webSearchEnabled": True, "webSearchEvents": []},
            "webSearchRequirement": {
                "required": True,
                "satisfied": False,
                "searchEvidence": "",
            },
        },
    )

    report = audit(public_path=public, results_dir=results, require_search_evidence=True)
    kinds = {item["kind"] for item in report["violations"]}

    assert report["passed"] is False
    assert "required_web_search_missing" in kinds
    assert "search_evidence_requirement_unsatisfied" in kinds
