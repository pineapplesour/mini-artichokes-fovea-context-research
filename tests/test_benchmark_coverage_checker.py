import json
import sqlite3

from tools.check_unified_benchmark_coverage import (
    check_legal_private_manifest_coverage,
    check_mcq_corpus_readiness,
    check_unified_benchmark_coverage,
)


def test_check_legal_private_manifest_coverage_finds_targets_and_required_text(tmp_path):
    private = {
        "schemaVersion": 1,
        "benchmarkId": "legal.coverage.test",
        "graders": [
            {
                "graderId": "g1",
                "primaryTargets": [
                    {
                        "court": "서울행정법원",
                        "caseNumber": "2024구합65355",
                        "decisionDate": "2025-01-21",
                        "requiredAnswerText": "D(여, 64세)",
                    }
                ],
            }
        ],
    }
    private_path = tmp_path / "private.json"
    private_path.write_text(json.dumps(private, ensure_ascii=False), encoding="utf-8")
    db_path = tmp_path / "lawkey.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE precedents (
          canonical_id TEXT PRIMARY KEY,
          case_number TEXT,
          court TEXT,
          decision_date TEXT,
          title TEXT,
          source_path TEXT,
          full_text TEXT
        );
        INSERT INTO precedents VALUES (
          'doc1', '2024구합65355', '서울행정법원', '2025-01-21',
          'target judgment', 'target.pdf', '본문에 D(여, 64세)가 포함됨'
        );
        """
    )
    conn.commit()
    conn.close()

    summary = check_legal_private_manifest_coverage(private_path, db_path)

    assert summary["dbExists"] is True
    assert summary["totalTargets"] == 1
    assert summary["presentTargets"] == 1
    assert summary["requiredAnswerTextPresent"] == 1
    assert summary["targets"][0]["present"] is True
    assert summary["targets"][0]["requiredAnswerTextPresent"] is True


def test_check_legal_private_manifest_coverage_reports_missing_db(tmp_path):
    private = {
        "benchmarkId": "legal.coverage.missing",
        "graders": [{"graderId": "g1", "primaryTargets": [{"caseNumber": "2024구합65355"}]}],
    }
    private_path = tmp_path / "private.json"
    private_path.write_text(json.dumps(private, ensure_ascii=False), encoding="utf-8")

    summary = check_legal_private_manifest_coverage(private_path, tmp_path / "missing.sqlite3")

    assert summary["dbExists"] is False
    assert summary["totalTargets"] == 1
    assert summary["presentTargets"] == 0
    assert summary["error"].startswith("database not found")


def test_check_mcq_corpus_readiness_flags_tiny_sample_db(tmp_path):
    public = {
        "benchmarkId": "mcq.tcm.test",
        "taskType": "mcq",
        "product": "tcm",
        "cases": [{"id": "q1", "prompt": "문제"}],
    }
    public_path = tmp_path / "public.json"
    public_path.write_text(json.dumps(public, ensure_ascii=False), encoding="utf-8")
    db_path = tmp_path / "tiny.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE precedents (canonical_id TEXT PRIMARY KEY, full_text TEXT);
        INSERT INTO precedents VALUES ('one', 'tiny sample');
        """
    )
    conn.close()

    summary = check_mcq_corpus_readiness(public_path, db_path, min_rows=10)

    assert summary["taskType"] == "mcq"
    assert summary["dbExists"] is True
    assert summary["corpusRows"] == 1
    assert summary["minRows"] == 10
    assert summary["readyForRetrievalBenchmark"] is False
    assert "below minimum" in summary["error"]


def test_check_mcq_corpus_readiness_accepts_large_enough_db(tmp_path):
    public = {
        "benchmarkId": "mcq.islam.test",
        "taskType": "mcq",
        "product": "islam",
        "cases": [{"id": "q1", "prompt": "문제"}],
    }
    public_path = tmp_path / "public.json"
    public_path.write_text(json.dumps(public, ensure_ascii=False), encoding="utf-8")
    db_path = tmp_path / "ready.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE passages (passage_id TEXT PRIMARY KEY, text TEXT)")
    conn.executemany("INSERT INTO passages VALUES (?, ?)", [(f"p{i}", "text") for i in range(12)])
    conn.commit()
    conn.close()

    summary = check_mcq_corpus_readiness(public_path, db_path, min_rows=10)

    assert summary["corpusTable"] == "passages"
    assert summary["corpusRows"] == 12
    assert summary["readyForRetrievalBenchmark"] is True
    assert summary["error"] == ""


def test_check_unified_benchmark_coverage_accepts_short_answer_corpus(tmp_path):
    public = {
        "benchmarkId": "short_answer.buddhist.test",
        "taskType": "short_answer",
        "product": "buddhist",
        "cases": [{"id": "q1", "prompt": "보살의 뜻은 무엇인가?"}],
    }
    public_path = tmp_path / "public.json"
    public_path.write_text(json.dumps(public, ensure_ascii=False), encoding="utf-8")
    db_path = tmp_path / "ready.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE passages (passage_id TEXT PRIMARY KEY, text TEXT)")
    conn.executemany("INSERT INTO passages VALUES (?, ?)", [(f"p{i}", "불교 문헌") for i in range(12)])
    conn.commit()
    conn.close()

    summary = check_unified_benchmark_coverage(public_path, db_path, min_rows=10)

    assert summary["taskType"] == "short_answer"
    assert summary["corpusTable"] == "passages"
    assert summary["corpusRows"] == 12
    assert summary["readyForRetrievalBenchmark"] is True
    assert summary["error"] == ""


def test_check_mcq_corpus_readiness_rejects_large_db_with_zero_topic_probe_hits(tmp_path):
    public = {
        "benchmarkId": "mcq.islam.finance.test",
        "taskType": "mcq",
        "product": "islam",
        "cases": [
            {
                "id": "q1",
                "prompt": "006. 무엇이 문제인가?\n\nA. 자금 혼합\nB. 고객의 기밀 유지\nC. 상업적 위험\nD. 기업 지배구조",
            }
        ],
    }
    public_path = tmp_path / "public.json"
    public_path.write_text(json.dumps(public, ensure_ascii=False), encoding="utf-8")
    db_path = tmp_path / "large_wrong_topic.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE precedents (canonical_id TEXT PRIMARY KEY, full_text TEXT)")
    conn.executemany("INSERT INTO precedents VALUES (?, ?)", [(f"d{i}", "scripture text") for i in range(12)])
    conn.commit()
    conn.close()

    summary = check_mcq_corpus_readiness(public_path, db_path, min_rows=10)

    assert summary["corpusRows"] == 12
    assert summary["readyForRetrievalBenchmark"] is False
    assert summary["topicProbe"]["termCount"] > 0
    assert summary["topicProbe"]["matchedTermCount"] == 0
    assert "topic probe" in summary["error"]


def test_check_mcq_corpus_readiness_accepts_large_db_with_topic_probe_hit(tmp_path):
    public = {
        "benchmarkId": "mcq.islam.finance.test",
        "taskType": "mcq",
        "product": "islam",
        "cases": [
            {
                "id": "q1",
                "prompt": "006. 무엇이 문제인가?\n\nA. 자금 혼합\nB. 고객의 기밀 유지\nC. 상업적 위험\nD. 기업 지배구조",
            }
        ],
    }
    public_path = tmp_path / "public.json"
    public_path.write_text(json.dumps(public, ensure_ascii=False), encoding="utf-8")
    db_path = tmp_path / "large_right_topic.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE precedents (canonical_id TEXT PRIMARY KEY, full_text TEXT)")
    rows = [(f"d{i}", "scripture text") for i in range(11)]
    rows.append(("finance", "Islamic finance manuals discuss fund commingling for investment account holders."))
    conn.executemany("INSERT INTO precedents VALUES (?, ?)", rows)
    conn.commit()
    conn.close()

    summary = check_mcq_corpus_readiness(public_path, db_path, min_rows=10)

    assert summary["readyForRetrievalBenchmark"] is True
    assert summary["topicProbe"]["matchedTermCount"] > 0
    assert summary["error"] == ""


def test_check_mcq_corpus_readiness_uses_largest_supported_table(tmp_path):
    public = {
        "benchmarkId": "mcq.tcm.test",
        "taskType": "mcq",
        "product": "tcm",
        "cases": [{"id": "q1", "prompt": "문제"}],
    }
    public_path = tmp_path / "public.json"
    public_path.write_text(json.dumps(public, ensure_ascii=False), encoding="utf-8")
    db_path = tmp_path / "mixed.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE passages (passage_id TEXT PRIMARY KEY, text TEXT)")
    conn.execute("CREATE TABLE precedents (canonical_id TEXT PRIMARY KEY, full_text TEXT)")
    conn.executemany("INSERT INTO precedents VALUES (?, ?)", [(f"d{i}", "text") for i in range(3)])
    conn.commit()
    conn.close()

    summary = check_mcq_corpus_readiness(public_path, db_path, min_rows=2)

    assert summary["corpusTable"] == "precedents"
    assert summary["corpusRows"] == 3
    assert summary["readyForRetrievalBenchmark"] is True
