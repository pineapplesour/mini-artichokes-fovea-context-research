import json
import sqlite3
from pathlib import Path

from shared_platform.lawkey_graph import rebuild_lawkey_source_graph
from tools.verify_lawkey_hard_bench import matches_target, run_lawkey_search, validate_query


def _case():
    return {
        "id": "yangyang-complainant-age",
        "primaryTarget": {
            "fileName": "춘천지방법원속초지원-2025고합5.pdf",
            "court": "춘천지방법원속초지원",
            "caseNumber": "2025고합5",
            "requiredAnswerText": "D(여, 64세)",
        },
        "relatedTargets": [
            {"fileName": "서울고등법원춘천-2025노158.pdf", "court": "서울고등법원 춘천재판부", "caseNumber": "2025노158"}
        ],
        "rankRules": {
            "candidateLimit": 50,
            "primaryMustAppearWithin": 5,
            "requiredAnswerMustAppearInPrimary": True,
            "forbidSearchMetadataLeakTerms": True,
        },
        "forbiddenSearchMetadataTerms": ["김진하", "양양", "양양군수"],
    }


def _result(rank, *, case_number, court, file_name, full_text=""):
    return {
        "canonical_id": f"doc-{rank}",
        "title": file_name,
        "citation": case_number,
        "authority_body": court,
        "source_path": f"/tmp/{file_name}",
        "full_text": full_text,
    }


def test_hard_bench_passes_when_primary_is_in_rank_window_and_contains_answer_span():
    results = [
        _result(1, case_number="2025고합5", court="춘천지방법원속초지원", file_name="춘천지방법원속초지원-2025고합5.pdf", full_text="피해자 D(여, 64세)"),
        _result(2, case_number="2025노158", court="서울고등법원 춘천재판부", file_name="서울고등법원춘천-2025노158.pdf"),
    ]

    verdict = validate_query(_case(), "김진하 군수 민원인 나이를 추정해봐", results)

    assert verdict.ok is True
    assert verdict.primary_rank == 1
    assert verdict.answer_span_found_in_primary is True
    assert verdict.related_ranks["2025노158"] == 2


def test_hard_bench_fails_when_correct_case_is_only_somewhere_in_large_candidate_set():
    results = [
        _result(i, case_number=f"{i}고단1", court="아무 법원", file_name=f"noise-{i}.pdf")
        for i in range(1, 8)
    ]
    results.append(
        _result(8, case_number="2025고합5", court="춘천지방법원속초지원", file_name="춘천지방법원속초지원-2025고합5.pdf", full_text="피해자 D(여, 64세)")
    )

    verdict = validate_query(_case(), "김진하 군수 민원인 나이를 추정해봐", results)

    assert verdict.ok is False
    assert verdict.primary_rank == 8
    assert any("exceeds allowed window" in failure for failure in verdict.failures)


def test_hard_bench_requires_answer_span_in_primary_not_related_case():
    results = [
        _result(1, case_number="2025고합5", court="춘천지방법원속초지원", file_name="춘천지방법원속초지원-2025고합5.pdf", full_text="정답 문구 없음"),
        _result(2, case_number="2025노158", court="서울고등법원 춘천재판부", file_name="서울고등법원춘천-2025노158.pdf", full_text="피해자 D(여, 64세)"),
    ]

    verdict = validate_query(_case(), "김진하 군수 민원인 나이를 추정해봐", results)

    assert verdict.ok is False
    assert verdict.primary_rank == 1
    assert any("required answer span not found" in failure for failure in verdict.failures)


def test_hard_bench_fails_when_public_case_alias_is_injected_into_search_metadata():
    results = [
        _result(
            1,
            case_number="2025고합5",
            court="춘천지방법원속초지원",
            file_name="춘천지방법원속초지원-2025고합5.pdf",
            full_text="피해자 D(여, 64세)",
        )
    ]
    results[0]["title"] = "춘천지방법원속초지원-2025고합5 | 김진하 양양 양양군수"
    results[0]["case_name"] = "김진하 양양 양양군수 군수 민원인 나이"

    verdict = validate_query(_case(), "김진하 군수 민원인 나이를 추정해봐", results)

    assert verdict.ok is False
    assert verdict.search_metadata_leaks == ["김진하", "양양", "양양군수"]
    assert any("search metadata contains benchmark alias terms" in failure for failure in verdict.failures)


def test_hard_bench_matches_windows_style_source_path_file_names():
    result = _result(
        1,
        case_number="2025노158",
        court="서울고등법원춘천",
        file_name="ignored",
    )
    result["source_path"] = "G:\\내 드라이브\\양양벤치\\서울고등법원춘천-2025노158.pdf"

    target = {"fileName": "서울고등법원춘천-2025노158.pdf", "court": "서울고등법원 춘천재판부", "caseNumber": "2025노158"}

    assert matches_target(result, target) is True


def test_benchmark_data_encodes_yangyang_primary_and_rank_window():
    data = json.loads(Path("benchmarks/lawkey_hard_retrieval/yangyang-complainant-age.json").read_text(encoding="utf-8"))
    case = data["cases"][0]

    assert case["primaryTarget"]["caseNumber"] == "2025고합5"
    assert case["primaryTarget"]["requiredAnswerText"] == "D(여, 64세)"
    assert case["rankRules"]["primaryMustAppearWithin"] <= 5
    assert case["rankRules"]["candidateLimit"] < 10000
    assert case["rankRules"]["forbidSearchMetadataLeakTerms"] is True


def test_lawkey_product_search_can_use_alias_metadata_but_hard_bench_rejects_that_pass(tmp_path):
    db_path = tmp_path / "lawkey.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE precedents (
          canonical_id TEXT PRIMARY KEY,
          source_dataset TEXT,
          source_path TEXT,
          title TEXT,
          case_number TEXT,
          court TEXT,
          decision_date TEXT,
          case_name TEXT,
          case_type TEXT,
          full_text TEXT NOT NULL,
          text_hash TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE precedents_fts USING fts5(
          canonical_id UNINDEXED,
          title,
          case_name,
          case_number,
          court,
          case_type,
          full_text_head,
          tokenize='unicode61'
        );
        """
    )
    for index in range(90):
        conn.execute(
            "INSERT INTO precedents VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                f"noise-{index}",
                "lawkey_fixture",
                f"/tmp/noise-{index}.pdf",
                f"군수 민원인 일반 잡음 {index}",
                f"2000고단{index}",
                "아무 법원",
                "2000-01-01",
                "군수 민원인 일반 사건",
                "형사",
                "군수 민원인 나이 일반 사건",
                f"hash-{index}",
            ),
        )
        conn.execute(
            "INSERT INTO precedents_fts VALUES (?,?,?,?,?,?,?)",
            (f"noise-{index}", f"군수 민원인 일반 잡음 {index}", "군수 민원인 일반 사건", f"2000고단{index}", "아무 법원", "형사", "군수 민원인 나이 일반 사건"),
        )
    conn.execute(
        "INSERT INTO precedents VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            "target",
            "lawkey_yangyang_bench",
            "/tmp/춘천지방법원속초지원-2025고합5.pdf",
            "춘천지방법원속초지원-2025고합5 | 김진하 양양 양양군수 군수 민원인 나이",
            "2025고합5",
            "춘천지방법원속초지원",
            "2025-06-26",
            "김진하 양양 양양군수 군수 민원인 나이",
            "형사",
            "피해자 D(여, 64세). 나이 관련 원문.",
            "hash-target",
        ),
    )
    conn.execute(
        "INSERT INTO precedents_fts VALUES (?,?,?,?,?,?,?)",
        ("target", "춘천지방법원속초지원-2025고합5 | 김진하 양양 양양군수 군수 민원인 나이", "김진하 양양 양양군수 군수 민원인 나이", "2025고합5", "춘천지방법원속초지원", "형사", "피해자 D(여, 64세). 나이 관련 원문."),
    )
    conn.commit()
    conn.close()

    rows = run_lawkey_search(db_path, "김진하 군수 민원인 나이를 추정해봐", limit=5, candidate_multiplier=1)

    assert rows[0]["canonical_id"] == "target"

    verdict = validate_query(_case(), "김진하 군수 민원인 나이를 추정해봐", rows)

    assert verdict.ok is False
    assert verdict.search_metadata_leaks == ["김진하", "양양", "양양군수"]


def test_lawkey_graph_expansion_promotes_primary_from_related_seed_without_alias_metadata(tmp_path):
    db_path = tmp_path / "lawkey-graph.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE precedents (
          canonical_id TEXT PRIMARY KEY,
          source_dataset TEXT,
          source_path TEXT,
          title TEXT,
          case_number TEXT,
          court TEXT,
          decision_date TEXT,
          case_name TEXT,
          case_type TEXT,
          full_text TEXT NOT NULL,
          text_hash TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE precedents_fts USING fts5(
          canonical_id UNINDEXED,
          title,
          case_name,
          case_number,
          court,
          case_type,
          full_text_head,
          tokenize='unicode61'
        );
        """
    )
    for index in range(25):
        conn.execute(
            "INSERT INTO precedents VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                f"noise-{index}",
                "lawkey_fixture",
                f"/tmp/noise/noise-{index}.pdf",
                f"군수 민원인 나이 잡음 {index}",
                f"2000고단{index}",
                "아무 법원",
                "2000-01-01",
                "군수 민원인 나이 일반 사건",
                "형사",
                "군수 민원인 나이 일반 사건",
                f"hash-noise-{index}",
            ),
        )
        conn.execute(
            "INSERT INTO precedents_fts VALUES (?,?,?,?,?,?,?)",
            (
                f"noise-{index}",
                f"군수 민원인 나이 잡음 {index}",
                "군수 민원인 나이 일반 사건",
                f"2000고단{index}",
                "아무 법원",
                "형사",
                "군수 민원인 나이 일반 사건",
            ),
        )
    conn.execute(
        "INSERT INTO precedents VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            "primary",
            "lawkey_yangyang_bench",
            "/tmp/yangyang/춘천지방법원속초지원-2025고합5.pdf",
            "춘천지방법원속초지원-2025고합5",
            "2025고합5",
            "춘천지방법원속초지원",
            "2025-06-26",
            "익명화 형사 사건",
            "형사",
            "피해자 D(여, 64세).",
            "hash-primary",
        ),
    )
    conn.execute(
        "INSERT INTO precedents_fts VALUES (?,?,?,?,?,?,?)",
        (
            "primary",
            "춘천지방법원속초지원-2025고합5",
            "익명화 형사 사건",
            "2025고합5",
            "춘천지방법원속초지원",
            "형사",
            "피해자 D(여, 64세).",
        ),
    )
    conn.execute(
        "INSERT INTO precedents VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            "appeal",
            "lawkey_yangyang_bench",
            "/tmp/yangyang/서울고등법원춘천-2025노158.pdf",
            "서울고등법원춘천-2025노158",
            "2025노158",
            "서울고등법원 춘천재판부",
            "2025-12-01",
            "김진하 군수 민원인 나이 관련 상급심",
            "형사",
            "김진하 군수 민원인 나이 관련 상급심에는 나이 span이 없다.",
            "hash-appeal",
        ),
    )
    conn.execute(
        "INSERT INTO precedents_fts VALUES (?,?,?,?,?,?,?)",
        (
            "appeal",
            "서울고등법원춘천-2025노158",
            "김진하 군수 민원인 나이 관련 상급심",
            "2025노158",
            "서울고등법원 춘천재판부",
            "형사",
            "김진하 군수 민원인 나이 관련 상급심에는 나이 span이 없다.",
        ),
    )
    rebuild_lawkey_source_graph(conn, graph_version="test-lawkey-graph", activate=True)
    conn.close()

    rows = run_lawkey_search(db_path, "김진하 군수 민원인 나이를 추정해봐", limit=5, candidate_multiplier=1)
    ids = [row["canonical_id"] for row in rows]

    assert "primary" in ids[:5]

    verdict = validate_query(_case(), "김진하 군수 민원인 나이를 추정해봐", rows)

    assert verdict.ok is True
    assert verdict.answer_span_found_in_primary is True
