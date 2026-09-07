from __future__ import annotations

import importlib
import json
import signal
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend.models import (
    aggregate_selected_rows,
    build_precedent_detail,
    build_result_payload,
    load_precedent_detail,
    project_live_status,
)
from backend import models as backend_models
from backend import jobs as backend_jobs
from backend.jobs import LawkeyJobManager, rag
from backend import exporters as backend_exporters
from backend import search as backend_search
from backend.search import build_search_queries, sanitize_search_query, _rerank_ranked_rows
from backend.server import create_app
from backend.config import (
    DEFAULT_GLOBAL_MAX_INFLIGHT,
    DEFAULT_ANALYZE_MODEL,
    DEFAULT_DRAFT_MODEL,
    DEFAULT_KEY_MIN_GAP_MS,
    DEFAULT_KEY_RPM_LIMIT,
    DEFAULT_KEY_TPM_LIMIT,
    DEFAULT_SELECT_MODEL,
    DEFAULT_WORKER_COUNT,
    PROJECT_ROOT,
)


def test_aggregate_selected_rows_combines_keyword_hits_and_respects_limit() -> None:
    keyword_hits = {
        "징계시효": [
            {
                "canonical_id": "case-a",
                "case_number": "2020구합12259",
                "title": "감봉 3월 징계처분 무효 확인",
                "court": "서울행정법원",
                "decision_date": "2021-06-17",
                "case_name": "감봉처분무효확인",
                "source_path": "/tmp/a.txt",
                "score": -8.4,
            },
            {
                "canonical_id": "case-b",
                "case_number": "2016구합7279",
                "title": "군 징계처분 취소",
                "court": "서울행정법원",
                "decision_date": "2017-07-14",
                "case_name": "징계처분취소",
                "source_path": "/tmp/b.txt",
                "score": -3.1,
            },
        ],
        "이중징계": [
            {
                "canonical_id": "case-a",
                "case_number": "2020구합12259",
                "title": "감봉 3월 징계처분 무효 확인",
                "court": "서울행정법원",
                "decision_date": "2021-06-17",
                "case_name": "감봉처분무효확인",
                "source_path": "/tmp/a.txt",
                "score": -7.1,
            },
            {
                "canonical_id": "case-c",
                "case_number": "2017구합12068",
                "title": "징계부가금 및 징계처분 취소",
                "court": "의정부지방법원",
                "decision_date": "2018-05-31",
                "case_name": "징계부가금등취소",
                "source_path": "/tmp/c.txt",
                "score": -6.5,
            },
        ],
    }

    rows = aggregate_selected_rows(keyword_hits, limit=2)

    assert [row["canonical_id"] for row in rows] == ["case-a", "case-c"]
    assert rows[0]["keyword_hit_count"] == 2
    assert rows[0]["matched_keywords"] == ["이중징계", "징계시효"]
    assert rows[1]["keyword_hit_count"] == 1


def test_select_top_precedents_overfetches_before_rerank(monkeypatch) -> None:
    rows = []
    for index in range(6):
        rows.append(
            {
                "canonical_id": f"case-{index}",
                "source_dataset": "test",
                "source_path": f"/tmp/case-{index}.txt",
                "title": str(index) if index < 3 else f"징계처분 취소 {index}",
                "case_number": f"2024구합{index}",
                "court": "서울행정법원",
                "decision_date": f"2024-01-0{index + 1}",
                "case_name": "" if index < 3 else "징계처분취소",
                "case_type": "",
                "full_text": "징계 관련 본문",
                "text_hash": f"hash-{index}",
                "score": float(index),
            }
        )

    class FakeConnection:
        def close(self) -> None:
            return None

    monkeypatch.setattr(backend_search, "build_search_queries", lambda *args, **kwargs: ["징계"])
    monkeypatch.setattr(backend_search.sqlite3, "connect", lambda _path: FakeConnection())
    monkeypatch.setattr(backend_search.search_index, "search_precedents", lambda _conn, _query, limit: rows[:limit])
    monkeypatch.setattr(
        backend_search,
        "_fetch_precedent_rows",
        lambda _conn, ids: [
            {row["canonical_id"]: row for row in rows}[canonical_id]
            for canonical_id in ids
            if canonical_id in {row["canonical_id"] for row in rows}
        ],
    )

    selected, meta = backend_search.select_top_precedents("징계 처분", top_k=3, per_keyword_limit=6)

    assert [row["file_id"] for row in selected] == ["case-3", "case-4", "case-5"]
    assert meta["candidate_count"] == 6


def test_select_top_precedents_backfills_when_top_ranked_rows_are_missing(monkeypatch) -> None:
    rows = []
    for index in range(8):
        rows.append(
            {
                "canonical_id": f"case-{index}",
                "source_dataset": "test",
                "source_path": f"/tmp/case-{index}.txt",
                "title": f"징계처분 취소 {index}",
                "case_number": f"2024구합{index}",
                "court": "서울행정법원",
                "decision_date": f"2024-01-0{index + 1}",
                "case_name": "징계처분취소",
                "case_type": "",
                "full_text": "징계 관련 본문",
                "text_hash": f"hash-{index}",
                "score": float(index),
            }
        )

    class FakeConnection:
        def close(self) -> None:
            return None

    monkeypatch.setattr(backend_search, "build_search_queries", lambda *args, **kwargs: ["징계"])
    monkeypatch.setattr(backend_search.sqlite3, "connect", lambda _path: FakeConnection())
    monkeypatch.setattr(backend_search.search_index, "search_precedents", lambda _conn, _query, limit: rows[:limit])
    monkeypatch.setattr(
        backend_search,
        "_fetch_precedent_rows",
        lambda _conn, ids: [
            {row["canonical_id"]: row for row in rows}[canonical_id]
            for canonical_id in ids
            if canonical_id in {row["canonical_id"] for row in rows} and canonical_id != "case-0"
        ],
    )

    selected, meta = backend_search.select_top_precedents("징계 처분", top_k=3, per_keyword_limit=8)

    assert [row["file_id"] for row in selected] == ["case-1", "case-2", "case-3"]
    assert meta["selected_count"] == 3


def test_select_top_precedents_searches_more_than_top_k_when_per_keyword_limit_is_small(monkeypatch) -> None:
    rows = []
    for index in range(12):
        rows.append(
            {
                "canonical_id": f"case-{index}",
                "source_dataset": "test",
                "source_path": f"/tmp/case-{index}.txt",
                "title": f"징계처분 취소 {index}",
                "case_number": f"2024구합{index}",
                "court": "서울행정법원",
                "decision_date": f"2024-01-{index + 1:02d}",
                "case_name": "징계처분취소",
                "case_type": "",
                "full_text": "징계 관련 본문",
                "text_hash": f"hash-{index}",
                "score": float(index),
            }
        )

    class FakeConnection:
        def close(self) -> None:
            return None

    limits: list[int] = []
    rows_by_id = {row["canonical_id"]: row for row in rows}
    monkeypatch.setattr(backend_search, "build_search_queries", lambda *args, **kwargs: ["징계"])
    monkeypatch.setattr(backend_search.sqlite3, "connect", lambda _path: FakeConnection())

    def fake_search(_conn, _query, limit):
        limits.append(limit)
        return rows[:limit]

    monkeypatch.setattr(backend_search.search_index, "search_precedents", fake_search)
    monkeypatch.setattr(
        backend_search,
        "_fetch_precedent_rows",
        lambda _conn, ids: [rows_by_id[canonical_id] for canonical_id in ids if canonical_id in rows_by_id],
    )

    selected, _meta = backend_search.select_top_precedents("징계 처분", top_k=5, per_keyword_limit=2)

    assert limits == [10]
    assert len(selected) == 5


def test_plain_traffic_accident_query_demotes_work_comp_precedents() -> None:
    ranked = [
        {
            "canonical_id": "san-jae",
            "case_number": "2023구합75058",
            "court": "서울행정법원",
            "decision_date": "2024-04-19",
            "case_name": "유족급여및장의비부지급처분취소",
            "title": "유족급여및장의비부지급처분취소",
            "keyword_hit_count": 3,
            "best_score": -10.0,
        },
        {
            "canonical_id": "traffic-criminal",
            "case_number": "2024노652",
            "court": "울산지방법원",
            "decision_date": "2024-05-09",
            "case_name": "교통사고처리특례법위반(치상)",
            "title": "교통사고처리특례법위반(치상)",
            "keyword_hit_count": 1,
            "best_score": 0.0,
        },
    ]

    selected = backend_search._rerank_ranked_rows(
        ranked,
        user_task="내가 과속으로 교통사고가 났는데 어떻게해야해? 100:0이야 내 과실 전부",
        limit=2,
    )

    assert [row["canonical_id"] for row in selected] == ["traffic-criminal", "san-jae"]


def test_plain_traffic_accident_query_injects_non_work_comp_queries() -> None:
    queries = backend_search.build_search_queries(
        "내가 과속으로 교통사고가 났는데 어떻게해야해? 100:0이야 내 과실 전부",
        keyword_generator=lambda *_args, **_kwargs: ["산재 과속 유족급여"],
    )

    assert "교통사고 과속 과실비율 손해배상 보험 합의" in queries
    assert "교통사고처리특례법 과속 치상 형사합의 처벌" in queries
    assert queries.index("교통사고 과속 과실비율 손해배상 보험 합의") < queries.index("산재 과속 유족급여")


def test_beta5_self_fault_traffic_profile_filters_noise_and_locks_actor() -> None:
    profile = backend_search._beta5_build_query_profile(
        "과속하다가 차 사고가 났고 100대 0인데 어캐함 나 망함?"
    )

    assert backend_search._is_self_fault_traffic_query("과속하다가 차 사고가 났고 100대 0인데 어캐함 나 망함?")
    assert "traffic_self_fault_driver" in profile.required_facets
    assert "100대" not in profile.positive_terms
    assert "0인데" not in profile.positive_terms
    assert "망함" not in profile.positive_terms
    flat_groups = " ".join(" ".join(group) for group in profile.search_groups)
    assert "교통사고처리특례법" in flat_groups
    assert "피고인" in flat_groups
    assert "제한속도" in flat_groups
    assert any("피해자의 일방적인 과실" in term for term in profile.hard_negative_terms)


def test_beta5_self_fault_traffic_scores_driver_fault_above_reversed_or_unrelated() -> None:
    profile = backend_search._beta5_build_query_profile(
        "과속하다가 차 사고가 났고 100대 0인데 어캐함 나 망함?"
    )
    self_fault = {
        "canonical_id": "self-fault",
        "title": "교통사고처리특례법위반(치상)",
        "case_number": "2024노652",
        "case_name": "교통사고처리특례법위반(치상)",
        "full_text": (
            "피고인이 제한속도를 초과하여 과속 주행하다 교통사고를 냈고 피해자를 충격하여 "
            "치상 결과가 발생하였다. 피고인의 전방주시의무와 속도위반이 쟁점이다."
        ),
    }
    reversed_frame = {
        "canonical_id": "reversed",
        "title": "기소유예처분취소",
        "case_number": "2013헌마571",
        "case_name": "기소유예처분취소",
        "full_text": (
            "피해자가 술에 만취되어 시속 207킬로미터의 엄청난 과속으로 운행한 피해자의 "
            "일방적인 과실로 발생한 추돌사고일 개연성이 높다. 청구인 운전 차량의 차선변경 과실은 부정된다."
        ),
    }
    unrelated_100 = {
        "canonical_id": "unrelated",
        "title": "공직선거법위반",
        "case_number": "2011노1493",
        "case_name": "공직선거법위반",
        "full_text": "후보자의 100대 공약과 홍보물이 문제된 사건이다. 100대 공약을 선거 공보에 기재하였다.",
    }
    constitutional_review = {
        "canonical_id": "constitutional-review",
        "title": "교통사고처리특례법 제4조 등 에 대한 헌법소원",
        "case_number": "90헌마110",
        "case_name": "교통사고처리특례법 제4조 등 에 대한 헌법소원",
        "full_text": (
            "교통사고처리특례법 조항의 위헌 여부가 문제된 헌법소원 사건이다. "
            "구체적인 피고인의 과속 주행, 제한속도, 전방주시의무 위반 사실관계를 판단한 사건은 아니다."
        ),
    }

    self_score = backend_search._beta5_score_candidate(self_fault, profile)
    reversed_score = backend_search._beta5_score_candidate(reversed_frame, profile)
    unrelated_score = backend_search._beta5_score_candidate(unrelated_100, profile)
    constitutional_score = backend_search._beta5_score_candidate(constitutional_review, profile)

    assert self_score > reversed_score + 80
    assert self_score > unrelated_score + 80
    assert self_score > constitutional_score + 80


def test_iterative_plain_traffic_domain_lock_drops_work_comp_candidates() -> None:
    rows = [
        {
            "canonical_id": "san-jae",
            "case_number": "2023구합75058",
            "court": "서울행정법원",
            "decision_date": "2024-04-19",
            "case_name": "유족급여및장의비부지급처분취소",
            "title": "유족급여및장의비부지급처분취소",
            "case_type": "행정",
        },
        {
            "canonical_id": "traffic-criminal",
            "case_number": "2024노652",
            "court": "울산지방법원",
            "decision_date": "2024-05-09",
            "case_name": "교통사고처리특례법위반(치상)",
            "title": "교통사고처리특례법위반(치상)",
            "case_type": "형사",
        },
    ]

    selected = backend_search._prioritize_iterative_rows(
        rows,
        user_task="내가 과속으로 교통사고가 났는데 어떻게해야해? 100:0이야 내 과실 전부",
    )

    assert [row["canonical_id"] for row in selected] == ["traffic-criminal"]


def test_beta4_plain_traffic_selector_does_not_feed_work_comp_first(monkeypatch) -> None:
    class FakeConnection:
        row_factory = None

        def close(self) -> None:
            return None

    rows = [
        {
            "canonical_id": "san-jae",
            "case_number": "2023구합75058",
            "court": "서울행정법원",
            "decision_date": "2024-04-19",
            "case_name": "유족급여및장의비부지급처분취소",
            "title": "유족급여및장의비부지급처분취소",
            "case_type": "행정",
            "full_text": "과속 교통사고와 업무상 재해 여부가 문제된 유족급여 사건이다.",
        },
        {
            "canonical_id": "traffic-criminal",
            "case_number": "2024노652",
            "court": "울산지방법원",
            "decision_date": "2024-05-09",
            "case_name": "교통사고처리특례법위반(치상)",
            "title": "교통사고처리특례법위반(치상)",
            "case_type": "형사",
            "full_text": "피고인이 제한속도를 초과하여 주행하다 교통사고를 냈고 치상과 인과관계가 문제되었다.",
        },
    ]
    rows_by_id = {row["canonical_id"]: row for row in rows}

    monkeypatch.setattr(backend_search.sqlite3, "connect", lambda _path: FakeConnection())
    monkeypatch.setattr(
        backend_search,
        "_beta2_gemma",
        lambda prompt, *_args, **_kwargs: (
            "JUDGE: 1:[useful]\nLEARNED_GROUPS"
            if "JUDGE:" in prompt
            else "그룹 1: 교통사고, 과속, 속도위반\n그룹 2: 치상, 손해배상, 보험"
        ),
    )
    monkeypatch.setattr(
        backend_search,
        "_beta2_fts_graceful",
        lambda *_args, **_kwargs: (rows, [{"strategy": "fake", "hits": len(rows)}]),
    )
    monkeypatch.setattr(
        backend_search,
        "_fetch_precedent_rows",
        lambda _conn, ids: [rows_by_id[canonical_id] for canonical_id in ids if canonical_id in rows_by_id],
    )

    selected, meta = backend_search.select_top_precedents_beta4(
        "내가 과속으로 교통사고가 났는데 어떻게해야해? 100:0이야 내 과실 전부",
        useful_target=1,
        max_iters=1,
    )

    assert [row["file_id"] for row in selected] == ["traffic-criminal"]
    assert meta["iters"][0]["candidate_filter"] == "plain_traffic_domain_lock"


def test_beta7_plain_traffic_selector_does_not_feed_work_comp_first(monkeypatch) -> None:
    class FakeConnection:
        row_factory = None

        def close(self) -> None:
            return None

    rows = [
        {
            "canonical_id": "san-jae",
            "case_number": "2023구합75058",
            "court": "서울행정법원",
            "decision_date": "2024-04-19",
            "case_name": "유족급여및장의비부지급처분취소",
            "title": "유족급여및장의비부지급처분취소",
            "case_type": "행정",
            "full_text": "과속 교통사고와 업무상 재해 여부가 문제된 유족급여 사건이다.",
        },
        {
            "canonical_id": "traffic-criminal",
            "case_number": "2024노652",
            "court": "울산지방법원",
            "decision_date": "2024-05-09",
            "case_name": "교통사고처리특례법위반(치상)",
            "title": "교통사고처리특례법위반(치상)",
            "case_type": "형사",
            "full_text": "피고인이 제한속도를 초과하여 주행하다 교통사고를 냈고 치상과 인과관계가 문제되었다.",
        },
    ]
    rows_by_id = {row["canonical_id"]: row for row in rows}

    monkeypatch.setattr(backend_search.sqlite3, "connect", lambda _path: FakeConnection())
    monkeypatch.setattr(
        backend_search,
        "_beta2_gemma",
        lambda prompt, *_args, **_kwargs: (
            "JUDGE: 1:[useful]\nLEARNED_GROUPS"
            if "JUDGE:" in prompt
            else "그룹 1: 교통사고, 과속, 속도위반\n그룹 2: 치상, 손해배상, 보험"
        ),
    )
    monkeypatch.setattr(
        backend_search,
        "_beta2_fts_graceful",
        lambda *_args, **_kwargs: (rows, [{"strategy": "fake", "hits": len(rows)}]),
    )
    monkeypatch.setattr(
        backend_search,
        "_fetch_precedent_rows",
        lambda _conn, ids: [rows_by_id[canonical_id] for canonical_id in ids if canonical_id in rows_by_id],
    )

    selected, meta = backend_search.select_top_precedents_beta7(
        "내가 과속으로 교통사고가 났는데 어떻게해야해? 100:0이야 내 과실 전부",
        useful_target=1,
        max_iters=1,
        useful_token_budget=100_000,
        judge_input_token_budget=5_000,
    )

    assert [row["file_id"] for row in selected] == ["traffic-criminal"]
    assert meta["iters"][0]["candidate_filter"] == "plain_traffic_domain_lock"


def test_beta5_scores_investigator_device_access_above_actor_reversal() -> None:
    profile = backend_search._beta5_build_query_profile(
        "수사기관이 피의자 휴대폰에서 유심을 빼서 카카오톡에 로그인해 수사에 사용한 판례"
    )
    target = {
        "canonical_id": "target",
        "title": "압수수색절차 위법 사건",
        "case_number": "2024노100",
        "case_name": "정보통신망법위반",
        "full_text": (
            "경찰 수사관이 피의자의 휴대전화에서 유심카드를 분리하여 카카오톡 계정에 "
            "로그인하고 대화내용을 수사자료로 사용하였다. 압수수색영장 집행과 참여권이 쟁점이다."
        ),
    }
    hard_negative = {
        "canonical_id": "negative",
        "title": "사기 사건",
        "case_number": "2024고단200",
        "case_name": "사기",
        "full_text": (
            "피고인은 피해자의 휴대전화에서 유심카드를 빼낸 뒤 카카오톡에 로그인하여 "
            "피해자를 속이고 금원을 편취하였다."
        ),
    }

    target_score = backend_search._beta5_score_candidate(target, profile)
    negative_score = backend_search._beta5_score_candidate(hard_negative, profile)

    assert target_score > negative_score + 20
    assert profile.required_facets["investigative_actor"]


def test_beta5_generated_issue_terms_boost_self_evidence_destruction_rule() -> None:
    profile = backend_search._beta5_build_query_profile(
        "실수로 범죄를 저지르고 내 증거를 인멸했음 이거 죄임?",
        issue_terms=["증거인멸죄", "자기증거인멸", "자기사건", "타인의 형사사건", "형법 제155조"],
    )
    target = {
        "canonical_id": "target",
        "title": "증거인멸 판결",
        "case_number": "2011도5329",
        "case_name": "증거인멸",
        "full_text": (
            "증거인멸죄에서 타인의 형사사건 또는 징계사건의 의미가 문제되었다. "
            "피고인 자신을 위한 증거인멸 행위가 동시에 다른 공범자에 관한 증거를 인멸한 결과가 되는 경우에도 "
            "증거인멸죄가 성립하는지 여부는 소극으로 판단된다."
        ),
    }
    noise = {
        "canonical_id": "noise",
        "title": "위증 판결",
        "case_number": "2020고단6649",
        "case_name": "위증",
        "full_text": "피고인이 공범의 범행을 숨기기 위하여 법정에서 허위 증언을 한 위증 사건이다.",
    }

    target_score = backend_search._beta5_score_candidate(target, profile)
    noise_score = backend_search._beta5_score_candidate(noise, profile)

    assert "legal_issue" in profile.required_facets
    assert target_score > noise_score + 60


def test_beta5_generated_issue_terms_boost_military_key_management_without_anchor() -> None:
    profile = backend_search._beta5_build_query_profile(
        "군대에서 키는 어캐 관리해야함?",
        issue_terms=["군대 열쇠 관리", "탄약고 열쇠", "무기고 열쇠", "보관 인계 점검"],
    )
    target = {
        "canonical_id": "target",
        "title": "군 열쇠 관리 판결",
        "case_number": "2023구합75301",
        "case_name": "징계처분취소",
        "full_text": (
            "공군 부대 탄약고와 무기고의 열쇠 보관, 인계, 점검 및 시건장치 관리가 문제되었다. "
            "총기 탄약 열쇠 관리소홀에 대한 징계 책임을 판단하였다."
        ),
    }
    noise = {
        "canonical_id": "noise",
        "title": "신체 성장 사건",
        "case_number": "2022가단1",
        "case_name": "손해배상",
        "full_text": "군 복무 중 신체 키와 체격 성장에 관한 일반 건강 상담 내용이다.",
    }

    assert backend_search._beta5_score_candidate(target, profile) > backend_search._beta5_score_candidate(noise, profile) + 50


def test_beta5_raw_military_key_query_scores_key_management_above_generic_discipline() -> None:
    profile = backend_search._beta5_build_query_profile("군대에서 키는 어캐 관리해야함?")
    assert "legal_issue" in profile.required_facets
    assert "탄약고 열쇠" in profile.required_facets["legal_issue"]
    target = {
        "canonical_id": "target",
        "title": "탄약고 열쇠 관리 징계",
        "case_number": "2023구합75301",
        "case_name": "징계처분취소",
        "full_text": (
            "공군 부대에서 탄약고 열쇠와 무기고 열쇠를 보관·인계·점검하지 않고 "
            "시건장치 관리상태를 소홀히 한 징계처분 사안이다."
        ),
    }
    generic_discipline = {
        "canonical_id": "noise",
        "title": "군인 징계처분취소",
        "case_number": "2012누2403",
        "case_name": "징계처분취소",
        "full_text": "육군 장교가 상관 지시불이행 및 품위유지의무 위반으로 징계를 받은 사건이다.",
    }

    assert backend_search._beta5_score_candidate(target, profile) > backend_search._beta5_score_candidate(generic_discipline, profile) + 50


def test_beta5_raw_kakao_usim_query_scores_direct_investigative_login_above_generic_forensics() -> None:
    profile = backend_search._beta5_build_query_profile("경찰이 피의자 유심 빼서 카톡 로그인하는거 합법임?")
    target = {
        "canonical_id": "target",
        "title": "카카오톡 계정 접속 압수수색",
        "case_number": "2021노1520",
        "case_name": "압수수색절차",
        "full_text": (
            "검사가 압수수색영장 집행 과정에서 피의자의 휴대전화 유심칩을 공기계에 장착하고 "
            "인증번호를 받아 카카오톡 계정에 로그인하여 대화내용을 확인하였다."
        ),
    }
    generic_forensics = {
        "canonical_id": "noise",
        "title": "휴대전화 전자정보 압수수색",
        "case_number": "2016도9596",
        "case_name": "성폭력범죄의처벌등에관한특례법위반",
        "full_text": "수사기관이 임의제출된 휴대전화 전자정보를 탐색하면서 참여권과 관련성 원칙을 준수해야 하는 사안이다.",
    }

    assert backend_search._beta5_score_candidate(target, profile) > backend_search._beta5_score_candidate(generic_forensics, profile) + 50


def test_beta6_verifier_accepts_direct_kakao_usim_and_rejects_supply_noise() -> None:
    direct = (
        "검사는 압수수색영장에 따라 피해자의 휴대전화 유심칩을 압수한 후 이를 별도의 휴대전화 공기계에 "
        "꽂고 인증번호를 받아 텔레그램 및 카카오톡 계정에 접속하여 대화내용과 첨부파일을 확인하였다."
    )
    supply_noise = (
        "피고인은 성명불상자와 공모하여 선불유심을 개통하고 타인 명의 계정정보를 이용하였으며, "
        "증거의 요지에는 카카오톡 대화자료와 경찰 피의자신문조서가 기재되어 있다."
    )

    accepted = backend_search._beta6_verify_kakao_usim(direct)
    rejected = backend_search._beta6_verify_kakao_usim(supply_noise)

    assert accepted.label == "accept"
    assert "direct_investigator_action" in accepted.positive_reasons
    assert rejected.label == "reject"
    assert "telecom_supply_or_opening" in rejected.negative_reasons


def test_beta6_scores_direct_investigative_access_above_supply_noise() -> None:
    spec = backend_search._beta6_query_spec("kakao_usim")
    direct_text = (
        "압수수색영장으로 유심칩을 압수하고 공기계에 장착하여 인증번호를 전송받은 뒤 "
        "카카오톡 계정에 접속하여 대화내용을 증거로 확인하였다. 검사가 위 절차를 진행하였다."
    )
    noise_text = (
        "보이스피싱 조직이 선불유심을 개통하고 카카오톡으로 대출 피해자를 속인 사안이다. "
        "증거의 요지에는 경찰 압수조서가 있다."
    )

    direct_score, direct_hits = backend_search._beta6_score_text(direct_text, spec)
    noise_score, noise_hits = backend_search._beta6_score_text(noise_text, spec)

    assert direct_score > noise_score + 30
    assert any("verified" in hit or "direct" in hit for hit in direct_hits)
    assert any("reject" in hit or "supply" in hit for hit in noise_hits)


def test_create_job_accepts_beta5_analysis_mode(tmp_path: Path, monkeypatch) -> None:
    runs_root = tmp_path / "runs"
    manager = LawkeyJobManager(runs_root=runs_root)
    monkeypatch.setattr(manager, "_run_job", lambda _job: None)

    created = manager.create_job(
        {
            "mode": "question",
            "userTask": "수사기관 유심 카카오톡 판례 찾아줘",
            "analysisMode": "beta5",
        }
    )

    job = manager._jobs[created["jobId"]]
    assert job.analysis_mode == "beta5"


def test_create_job_accepts_beta6_analysis_mode(tmp_path: Path, monkeypatch) -> None:
    runs_root = tmp_path / "runs"
    manager = LawkeyJobManager(runs_root=runs_root)
    monkeypatch.setattr(manager, "_run_job", lambda _job: None)

    created = manager.create_job(
        {
            "mode": "question",
            "userTask": "수사기관 유심 카카오톡 판례 찾아줘",
            "analysisMode": "beta6",
        }
    )

    job = manager._jobs[created["jobId"]]
    assert job.analysis_mode == "beta6"


def test_create_job_accepts_beta8_analysis_mode(tmp_path: Path, monkeypatch) -> None:
    runs_root = tmp_path / "runs"
    manager = LawkeyJobManager(runs_root=runs_root)
    monkeypatch.setattr(manager, "_run_job", lambda _job: None)

    created = manager.create_job(
        {
            "mode": "question",
            "userTask": "견해 설명 연결 문제 풀어줘",
            "analysisMode": "beta8",
        }
    )

    job = manager._jobs[created["jobId"]]
    assert job.analysis_mode == "beta8"


def test_ensure_selected_records_dispatches_beta5(tmp_path: Path, monkeypatch) -> None:
    runs_root = tmp_path / "runs"
    manager = LawkeyJobManager(runs_root=runs_root)
    monkeypatch.setattr(manager, "_run_job", lambda _job: None)
    called: list[str] = []

    def fake_beta5(user_task: str, **_kwargs):
        called.append(user_task)
        return [
            {
                "file_id": "case-beta5",
                "relative_path": "case-beta5.txt",
                "absolute_path": "case-beta5.txt",
                "document_title": "수사기관 유심 로그인 사건",
                "doc_type": "txt",
                "source_group": "structured_precedent",
                "token_count": 10,
                "anchor_text": "경찰 유심 카카오톡",
                "extracted_text": "경찰이 유심을 분리하여 카카오톡에 로그인하였다.",
                "candidate_boundaries": [],
                "is_direct_evidence": False,
                "is_format_sample": False,
                "content_hash": "hash-beta5",
                "duplicate_paths": [],
                "case_number": "2024노100",
                "court": "서울고등법원",
                "decision_date": "2024-01-01",
                "case_name": "압수수색절차",
            }
        ], {"selection_mode": "beta5_agentic_union_verify", "keywords": ["경찰", "유심", "카카오톡"]}

    monkeypatch.setattr(backend_search, "select_top_precedents_beta5", fake_beta5, raising=False)
    created = manager.create_job(
        {
            "mode": "question",
            "userTask": "수사기관 유심 카카오톡 판례 찾아줘",
            "analysisMode": "beta5",
        }
    )
    job = manager._jobs[created["jobId"]]

    manager._ensure_selected_records(job)

    assert called == ["수사기관 유심 카카오톡 판례 찾아줘"]
    assert job.selected_count == 1


def test_ensure_selected_records_dispatches_beta6(tmp_path: Path, monkeypatch) -> None:
    runs_root = tmp_path / "runs"
    manager = LawkeyJobManager(runs_root=runs_root)
    monkeypatch.setattr(manager, "_run_job", lambda _job: None)
    called: list[str] = []

    def fake_beta6(user_task: str, **_kwargs):
        called.append(user_task)
        return [
            {
                "file_id": "case-beta6",
                "relative_path": "case-beta6.txt",
                "absolute_path": "case-beta6.txt",
                "document_title": "검사 유심 카카오톡 접속 사건",
                "doc_type": "txt",
                "source_group": "structured_precedent",
                "token_count": 10,
                "anchor_text": "검사 유심 카카오톡 공기계 인증번호",
                "extracted_text": "검사가 유심칩을 공기계에 장착하여 카카오톡 계정에 접속하였다.",
                "candidate_boundaries": [],
                "is_direct_evidence": False,
                "is_format_sample": False,
                "content_hash": "hash-beta6",
                "duplicate_paths": [],
                "case_number": "2021노1520",
                "court": "서울고등법원",
                "decision_date": "2022-07-21",
                "case_name": "특정범죄가중처벌등에관한법률위반(독직폭행)",
            }
        ], {"selection_mode": "beta6_loop_r133_port", "query_kind": "kakao_usim"}

    monkeypatch.setattr(backend_search, "select_top_precedents_beta6", fake_beta6, raising=False)
    created = manager.create_job(
        {
            "mode": "question",
            "userTask": "수사기관 유심 카카오톡 판례 찾아줘",
            "analysisMode": "beta6",
        }
    )
    job = manager._jobs[created["jobId"]]

    manager._ensure_selected_records(job)

    assert called == ["수사기관 유심 카카오톡 판례 찾아줘"]
    assert job.selected_count == 1
    persisted_meta = json.loads((job.run_dir / "selection_meta.json").read_text(encoding="utf-8"))
    assert "downstream_user_task" not in persisted_meta


def test_ensure_selected_records_dispatches_beta8_through_beta6_selector(tmp_path: Path, monkeypatch) -> None:
    runs_root = tmp_path / "runs"
    manager = LawkeyJobManager(runs_root=runs_root)
    monkeypatch.setattr(manager, "_run_job", lambda _job: None)
    called: list[str] = []

    def fake_beta6(user_task: str, **_kwargs):
        called.append(user_task)
        return [
            {
                "file_id": "case-beta8",
                "relative_path": "case-beta8.txt",
                "absolute_path": "case-beta8.txt",
                "document_title": "오상방위 견해 설명 사건",
                "doc_type": "txt",
                "source_group": "structured_precedent",
                "token_count": 10,
                "anchor_text": "위법성조각사유 전제사실 착오",
                "extracted_text": "위법성조각사유의 전제사실 착오와 형법 제16조가 문제된다.",
                "candidate_boundaries": [],
                "is_direct_evidence": False,
                "is_format_sample": False,
                "content_hash": "hash-beta8",
                "duplicate_paths": [],
                "case_number": "2000도0000",
                "court": "대법원",
                "decision_date": "2000-01-01",
                "case_name": "상해",
            }
        ], {"selection_mode": "beta6_loop_r133_port", "query_kind": "generic"}

    monkeypatch.setattr(backend_search, "select_top_precedents_beta6", fake_beta6, raising=False)
    created = manager.create_job(
        {
            "mode": "question",
            "userTask": "견해 설명 연결 문제 풀어줘",
            "analysisMode": "beta8",
        }
    )
    job = manager._jobs[created["jobId"]]

    manager._ensure_selected_records(job)

    assert called == ["견해 설명 연결 문제 풀어줘"]
    assert job.selected_count == 1
    persisted_meta = json.loads((job.run_dir / "selection_meta.json").read_text(encoding="utf-8"))
    assert persisted_meta["selection_mode"] == "beta8_legal_proposition_guard"
    assert persisted_meta["base_selection_mode"] == "beta6_loop_r133_port"


def test_project_live_status_uses_chunk_plan_for_current_excerpt() -> None:
    runtime_status = {
        "phase": "variant",
        "state": "analyzing_chunks",
        "completed_chunks": 2,
        "chunk_count": 5,
        "selected_file_count": 20,
        "elapsed_seconds": 30,
    }
    chunk_plan = [
        {"case_number": "2020구합12259", "excerpt": "첫 번째 청크"},
        {"case_number": "2016구합7279", "excerpt": "두 번째 청크"},
        {"case_number": "2017구합12068", "excerpt": "세 번째 청크"},
    ]

    projected = project_live_status(runtime_status, chunk_plan=chunk_plan, worker_count=4)

    assert projected["completedChunks"] == 2
    assert projected["totalChunks"] == 5
    assert projected["currentCaseNumber"] == "2017구합12068"
    assert projected["currentExcerpt"] == "세 번째 청크"
    assert projected["etaSeconds"] == 42


def test_project_live_status_caps_chunk_eta_when_job_elapsed_is_large() -> None:
    projected = project_live_status(
        {
            "phase": "variant",
            "state": "analyzing_chunks",
            "completed_chunks": 10,
            "chunk_count": 44,
            "selected_file_count": 100,
            "elapsed_seconds": 1800,
            "runtime_limits": {"gemini_global_max_inflight": 10},
        },
        chunk_plan=[],
        worker_count=10,
    )

    assert 0 < projected["etaSeconds"] <= 180


def test_project_live_status_exposes_scheduler_runtime_fields() -> None:
    runtime_status = {
        "phase": "variant",
        "state": "analyzing_chunks",
        "completed_chunks": 1,
        "chunk_count": 4,
        "elapsed_seconds": 12,
        "selected_file_count": 20,
        "gemini_keys_total": 10,
        "gemini_keys_cooling_down": 3,
        "gemini_scheduler_inflight": 4,
        "gemini_next_ready_in_ms": 1700,
        "runtime_limits": {
            "gemini_key_min_gap_ms": 3000,
            "gemini_key_max_inflight": 1,
            "gemini_key_rpm_limit": 20,
            "gemini_key_tpm_limit": 0,
            "gemini_global_max_inflight": 4,
        },
    }

    projected = project_live_status(runtime_status, chunk_plan=[], worker_count=4)

    assert projected["scheduler"]["keyCount"] == 10
    assert projected["scheduler"]["coolingKeys"] == 3
    assert projected["scheduler"]["inflight"] == 4
    assert projected["scheduler"]["nextReadyInMs"] == 1700
    assert projected["scheduler"]["rpmLimit"] == 20
    assert projected["scheduler"]["tpmLimit"] == 0
    assert projected["scheduler"]["minGapMs"] == 3000
    assert projected["scheduler"]["maxInflightPerKey"] == 1
    assert projected["scheduler"]["globalMaxInflight"] == 4


def test_project_live_status_keeps_tail_eta_after_chunks_complete() -> None:
    projected = project_live_status(
        {
            "state": "writing_final_draft",
            "completed_chunks": 10,
            "chunk_count": 10,
            "elapsed_seconds": 30,
            "selected_file_count": 100,
        },
        chunk_plan=[],
        worker_count=10,
    )

    assert projected["etaSeconds"] == 18


def test_build_result_payload_reads_question_outputs(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    result_dir = run_dir / "question_selected_manual"
    result_dir.mkdir(parents=True)

    selected_files = [
        {
            "file_id": "file-1",
            "document_title": "감봉 3월 징계처분 무효 확인 사건",
            "case_number": "2020구합12259",
            "court": "서울행정법원",
            "decision_date": "2021-06-17",
            "case_name": "감봉처분무효확인",
            "relative_path": "precedents/a.txt",
            "absolute_path": "/tmp/a.txt",
            "extracted_text": "징계권자가 이미 비위를 인지하고도 아무 조치를 하지 아니하였다.",
        }
    ]
    claim_ledger = [
        {
            "claim_axis": "징계권자의 비위 인지 후 미조치 사건의 합산 징계 부당성",
            "claim_text": "뒤늦은 합산 징계는 신뢰보호 문제를 낳을 수 있다.",
            "supporting_cases": [
                {
                    "case_number": "2020구합12259",
                    "court": "서울행정법원",
                    "decision_date": "2021-06-17",
                    "case_name": "감봉처분무효확인",
                }
            ],
        }
    ]
    chunk_output = {
        "file_id": "file-1",
        "claims_proposed": [
            {
                "source_file_id": "file-1",
                "case_number": "2020구합12259",
                "claim_axis": "징계권자의 비위 인지 후 미조치 사건의 합산 징계 부당성",
                "context_summary": "징계권자의 사전 인지가 쟁점이 된다.",
                "case_summary": "방치 후 누적 징계의 부당성을 본 사건이다.",
                "support_spans": [
                    {
                        "quote": "징계권자가 이미 비위를 인지하고도 아무 조치를 하지 아니하였다.",
                        "evidence_id": "근거1",
                    }
                ],
                "oppose_spans": [],
            }
        ],
    }

    (result_dir / "selected_files.json").write_text(json.dumps(selected_files, ensure_ascii=False), encoding="utf-8")
    (result_dir / "claim_ledger.json").write_text(json.dumps(claim_ledger, ensure_ascii=False), encoding="utf-8")
    (result_dir / "comparison_summary.json").write_text(
        json.dumps({"selected_file_count": 1, "chunk_count": 1, "claim_count": 1}, ensure_ascii=False),
        encoding="utf-8",
    )
    (result_dir / "final_answer.md").write_text("# 답변\n\n실제 최종답입니다.", encoding="utf-8")
    (result_dir / "chunk_outputs.jsonl").write_text(json.dumps(chunk_output, ensure_ascii=False) + "\n", encoding="utf-8")

    payload = build_result_payload(run_dir)

    assert payload["answerMarkdown"].startswith("### 가장 가능성 높은 결론")
    assert "# 답변\n\n실제 최종답입니다." in payload["answerMarkdown"]
    assert payload["selectedPrecedents"][0]["precedentId"] == "file-1"
    assert payload["selectedPrecedents"][0]["citation"] == "2020구합12259 판결"
    assert payload["usedPrecedentIds"] == ["file-1"]
    assert payload["claims"][0]["claim_axis"] == claim_ledger[0]["claim_axis"]


def test_build_result_payload_strips_model_meta_leak_prefix(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    result_dir = run_dir / "question_selected_manual"
    result_dir.mkdir(parents=True)
    (result_dir / "selected_files.json").write_text("[]", encoding="utf-8")
    (result_dir / "claim_ledger.json").write_text("[]", encoding="utf-8")
    (result_dir / "comparison_summary.json").write_text("{}", encoding="utf-8")
    (result_dir / "chunk_outputs.jsonl").write_text("", encoding="utf-8")
    (result_dir / "final_answer.md").write_text(
        "\n".join(
            [
                "Input: A draft containing meta-descriptions, instructions, self-checks, and intermediate notes.",
                "Goal: Rewrite the draft into a final, user-ready Korean legal answer.",
                "*Wait, the prompt says claim_groups should be grouped.*",
                "*Let's go.*## 종합 판단",
                "초안이라 버려야 하는 문장입니다.",
                "Self-Correction: revise internally.",
                "## 종합 판단",
                "최종 답변만 남아야 합니다.",
            ]
        ),
        encoding="utf-8",
    )

    payload = build_result_payload(run_dir)

    assert payload["answerMarkdown"] == "## 종합 판단\n최종 답변만 남아야 합니다."
    assert "Input: A draft" not in payload["answerMarkdown"]
    assert "Self-Correction" not in payload["answerMarkdown"]


def test_build_result_payload_self_corrects_view_explanation_mcq_answer(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    result_dir = run_dir / "question_selected_manual"
    result_dir.mkdir(parents=True)
    problem = """【문제】 (다툼이 있는 경우 판례에 의함)
甲은 야간에 자신을 계속 뒤따라오다 갑자기 손을 내뻗는 A를 강제추행범으로 오인하고, 이를 막고자 A를 폭행하여 상해를 가하였다. 그런데 실제로 A는 甲의 친구로서 장난을 치기 위해 위와 같은 행동을 한 것이었다. 이 사례의 해결방식에 관한 다음 견해들과 그 설명의 연결로 옳은 것은?
〈견해〉

가. 甲이 정당방위상황으로 잘못 판단한 데에 정당한 이유가 있으면 책임을 조각하려는 견해
나. 甲 행위의 구성요건적 고의를 인정하면서 고의범으로서의 법효과만을 제한하려는 견해
다. 사실의 착오 근거규정(형법 제15조 제1항)을 유추적용하려는 견해
라. 구성요건적 고의의 인식 대상이 되는 사실과 위법성조각사유의 전제되는 사실을 구별하지 아니하는 견해

〈설명〉

Ⓐ '불법'과 '책임'의 두 단계로 범죄체계를 구성한다면, 형법상 위법성조각사유는 소극적 구성요건표지이다.
Ⓑ 위법성조각사유의 객관적 전제사실에 대한 착오는 위법성의 착오(형법 제16조)에 해당한다.
Ⓒ 고의의 이중적 지위를 인정하여 구성요건적 고의와 책임고의를 구분한다.

선지:

가-Ⓑ, 라-Ⓐ
가-Ⓒ, 다-Ⓑ
나-Ⓒ, 라-Ⓐ
나-Ⓑ, 다-Ⓐ
다-Ⓒ, 라-Ⓑ"""
    (run_dir / "selection_meta.json").write_text(
        json.dumps({"original_user_task": problem}, ensure_ascii=False),
        encoding="utf-8",
    )
    (result_dir / "selected_files.json").write_text("[]", encoding="utf-8")
    (result_dir / "claim_ledger.json").write_text("[]", encoding="utf-8")
    (result_dir / "comparison_summary.json").write_text("{}", encoding="utf-8")
    (result_dir / "chunk_outputs.jsonl").write_text("", encoding="utf-8")
    (result_dir / "final_answer.md").write_text(
        "## 종합 판단\n\n정답은 3번입니다. 나-Ⓒ은 직접 대응하고, 라-Ⓐ도 직접 대응합니다.",
        encoding="utf-8",
    )

    payload = build_result_payload(run_dir, analysis_mode="beta8")
    answer = payload["answerMarkdown"]

    assert "정답: 1번" in answer
    assert "가-Ⓑ, 라-Ⓐ" in answer
    assert "나-Ⓒ" in answer
    assert "직접 지지" in answer
    assert "정답은 3번" not in answer


def test_build_result_payload_keeps_view_explanation_mcq_guard_admin_beta_only(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    result_dir = run_dir / "question_selected_manual"
    result_dir.mkdir(parents=True)
    problem = """〈견해〉

가. 甲이 정당방위상황으로 잘못 판단한 데에 정당한 이유가 있으면 책임을 조각하려는 견해
나. 甲 행위의 구성요건적 고의를 인정하면서 고의범으로서의 법효과만을 제한하려는 견해
라. 구성요건적 고의의 인식 대상이 되는 사실과 위법성조각사유의 전제되는 사실을 구별하지 아니하는 견해

〈설명〉

Ⓐ '불법'과 '책임'의 두 단계로 범죄체계를 구성한다면, 형법상 위법성조각사유는 소극적 구성요건표지이다.
Ⓑ 위법성조각사유의 객관적 전제사실에 대한 착오는 위법성의 착오(형법 제16조)에 해당한다.
Ⓒ 고의의 이중적 지위를 인정하여 구성요건적 고의와 책임고의를 구분한다.

선지:

가-Ⓑ, 라-Ⓐ
나-Ⓒ, 라-Ⓐ"""
    (run_dir / "selection_meta.json").write_text(
        json.dumps({"original_user_task": problem}, ensure_ascii=False),
        encoding="utf-8",
    )
    (result_dir / "selected_files.json").write_text("[]", encoding="utf-8")
    (result_dir / "claim_ledger.json").write_text("[]", encoding="utf-8")
    (result_dir / "comparison_summary.json").write_text("{}", encoding="utf-8")
    (result_dir / "chunk_outputs.jsonl").write_text("", encoding="utf-8")
    (result_dir / "final_answer.md").write_text("정답은 2번입니다. 나-Ⓒ, 라-Ⓐ", encoding="utf-8")

    payload = build_result_payload(run_dir, analysis_mode="beta6")

    assert "정답은 2번" in payload["answerMarkdown"]
    assert "정답: 1번" not in payload["answerMarkdown"]


def test_build_result_payload_strips_document_meta_leak_prefix(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    result_dir = run_dir / "question_selected_manual"
    result_dir.mkdir(parents=True)
    (result_dir / "selected_files.json").write_text("[]", encoding="utf-8")
    (result_dir / "claim_ledger.json").write_text("[]", encoding="utf-8")
    (result_dir / "comparison_summary.json").write_text("{}", encoding="utf-8")
    (result_dir / "chunk_outputs.jsonl").write_text("", encoding="utf-8")
    (result_dir / "final_document.md").write_text(
        "\n".join(
            [
                'Legal Opinion (변호인 의견서) - though the user\'s task is about a "Notice of Demand".',
                "    *   *Wait, let's re-read:* The user wants me to write a legal opinion.",
                "    *   *Subject Matter:* Legal principles for a Notice of Demand.",
                "    *   *Claim 1:* Commercial debt -> 6% + 12%.",
                "    *   *Final Review of the Ledger usage:*",
                "        - Claim 1 (6%/12%) - Included.",
                "    *   *Formatting:* Plain text.",
                "    *   *Drafting the final response...* (Proceeding to generate the Korean text).법률 검토 의견서",
                "",
                "사    건  대여금 반환 청구를 위한 법리 검토",
            ]
        ),
        encoding="utf-8",
    )

    payload = build_result_payload(run_dir, mode="document")

    assert payload["answerMarkdown"].startswith("법률 검토 의견서")
    assert "Wait, let's re-read" not in payload["answerMarkdown"]
    assert "Final Review of the Ledger usage" not in payload["answerMarkdown"]
    assert "Claim 1" not in payload["answerMarkdown"]


def test_build_result_payload_strips_complaint_prompt_leak_prefix(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    result_dir = run_dir / "question_selected_manual"
    result_dir.mkdir(parents=True)
    (result_dir / "selected_files.json").write_text("[]", encoding="utf-8")
    (result_dir / "claim_ledger.json").write_text("[]", encoding="utf-8")
    (result_dir / "comparison_summary.json").write_text("{}", encoding="utf-8")
    (result_dir / "chunk_outputs.jsonl").write_text("", encoding="utf-8")
    (result_dir / "final_document.md").write_text(
        "\n".join(
            [
                "Legal Opinion Writer (Lawyer).",
                'Write a "Complaint" (고소장) based on the provided ledger.',
                'The user\'s task is "Write a complaint" (고소장 작성해달라). *Wait, looking at the prompt again, this is a contradiction.*',
                "",
                "    *   *Contradiction Check:*",
                '        - User Task: "Write a complaint (고소장 작성해달라)."',
                "    *   *Mental Draft:*",
                "        고소장",
                "        1. 고소인: [성명]",
                "    *   *Drafting the final response...* (Ensuring it is plain text).",
                "",
                "    *   *Let's go.*고    소    장",
                "",
                "## 1. 고소인",
                "",
                "- 성명: [고소인 성명]",
            ]
        ),
        encoding="utf-8",
    )

    payload = build_result_payload(run_dir, mode="document")

    assert payload["answerMarkdown"].startswith("고    소    장")
    assert "Legal Opinion Writer" not in payload["answerMarkdown"]
    assert "Contradiction Check" not in payload["answerMarkdown"]
    assert "Mental Draft" not in payload["answerMarkdown"]


def test_live_gemma4_complaint_meta_leak_is_stripped_and_titled(tmp_path: Path) -> None:
    leaked = "\n".join(
        [
            "Legal Professional (Lawyer/Legal Writer).",
            "Complaint (고소장).",
            "Use *only* the provided ledger and section packet. Follow the sample format but do not copy it verbatim.",
            "A person (A) was insulted in a group chat by B.",
            "",
            "* Logic: Use the Section Packet logic for 공연성 and 특정성.",
            "* Check:* Did I use 변호인의견서 style? No, it is a 고소장.",
            "* Final Polish: Ensure Korean legal drafting style.",
            "",
            "## 1. 고소인",
            "- 성명: A",
            "",
            "## 4. 범죄사실",
            "피고소인 B는 2026. 4. 1. 단체 채팅방에서 고소인을 사기꾼 같은 인간, 회사에서 없어져야 할 쓰레기라고 모욕하였습니다.",
        ]
    )

    assert rag.sanitize_document_output(leaked).startswith("고    소    장\n\n## 1. 고소인")

    run_dir = tmp_path / "run"
    result_dir = run_dir / "question_selected_manual"
    result_dir.mkdir(parents=True)
    (result_dir / "selected_files.json").write_text("[]", encoding="utf-8")
    (result_dir / "claim_ledger.json").write_text("[]", encoding="utf-8")
    (result_dir / "comparison_summary.json").write_text("{}", encoding="utf-8")
    (result_dir / "chunk_outputs.jsonl").write_text("", encoding="utf-8")
    (result_dir / "final_document.md").write_text(leaked, encoding="utf-8")

    payload = build_result_payload(run_dir, mode="document")

    assert payload["answerMarkdown"].startswith("고    소    장\n\n## 1. 고소인")
    assert "Legal Professional" not in payload["answerMarkdown"]
    assert "Complaint (고소장)" not in payload["answerMarkdown"]
    assert "Use *only*" not in payload["answerMarkdown"]
    assert "Final Polish" not in payload["answerMarkdown"]
    assert "* Check:*" not in payload["answerMarkdown"]


def test_build_result_payload_does_not_prepend_question_summary_for_document(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    result_dir = run_dir / "question_selected_manual"
    result_dir.mkdir(parents=True)
    (result_dir / "selected_files.json").write_text("[]", encoding="utf-8")
    (result_dir / "claim_ledger.json").write_text(
        json.dumps(
            [
                {
                    "claim_id": "claim-1",
                    "claim_axis": "고소장 작성의 적법성",
                    "claim_text": "고소장에는 처벌을 구하는 범죄사실을 구체적으로 기재해야 한다.",
                    "supporting_case_count": 1,
                    "supporting_cases": [{"case_number": "2005도8976"}],
                    "stance_to_user_goal": "유리",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (result_dir / "answer_plan.json").write_text("{}", encoding="utf-8")
    (result_dir / "comparison_summary.json").write_text("{}", encoding="utf-8")
    (result_dir / "chunk_outputs.jsonl").write_text("", encoding="utf-8")
    (result_dir / "final_document.md").write_text("고    소    장\n\n## 1. 고소인\n\n- 성명: [고소인 성명]", encoding="utf-8")

    payload = build_result_payload(run_dir, mode="document")

    assert payload["answerMarkdown"].startswith("고    소    장")
    assert "### 가장 가능성 높은 결론" not in payload["answerMarkdown"]


def test_render_pdf_preview_images_removes_stale_pngs(tmp_path: Path, monkeypatch) -> None:
    preview_dir = tmp_path / "preview"
    preview_dir.mkdir()
    stale_page = preview_dir / "page-003.png"
    stale_page.write_text("old", encoding="utf-8")
    keep_file = preview_dir / "notes.txt"
    keep_file.write_text("keep", encoding="utf-8")

    class FakePixmap:
        def save(self, out_path: Path) -> None:
            out_path.write_text("new", encoding="utf-8")

    class FakePage:
        def get_pixmap(self, **_kwargs):
            return FakePixmap()

    class FakeDocument:
        page_count = 1

        def load_page(self, _page_index: int):
            return FakePage()

        def close(self) -> None:
            return None

    monkeypatch.setattr(backend_exporters.fitz, "open", lambda _path: FakeDocument())

    written = backend_exporters.render_pdf_preview_images(tmp_path / "document.pdf", preview_dir)

    assert [path.name for path in written] == ["page-001.png"]
    assert not stale_page.exists()
    assert keep_file.exists()
    assert (preview_dir / "page-001.png").read_text(encoding="utf-8") == "new"


def test_document_preflight_route_uses_manager_response() -> None:
    class StubManager:
        def list_document_presets(self) -> list[dict[str, str]]:
            return []

        def document_preflight(self, payload: dict[str, object]) -> dict[str, object]:
            assert payload["userTask"] == "변호인의견서 초안"
            return {
                "ready": False,
                "questions": ["처분 일자를 알려주세요."],
                "retrievalTask": "",
                "draftingGoal": "변호인의견서 초안",
                "summary": "추가 사실이 필요합니다.",
            }

    client = TestClient(create_app(manager=StubManager(), frontend_dist=PROJECT_ROOT / "dist"))
    response = client.post(
        "/api/document-preflight",
        json={"userTask": "변호인의견서 초안", "documentPresetId": "defense_opinion_assault"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is False
    assert payload["questions"] == ["처분 일자를 알려주세요."]


def test_document_preflight_rejects_etc_hosts_before_text_extraction(tmp_path: Path, monkeypatch) -> None:
    manager = LawkeyJobManager(runs_root=tmp_path / "runs")
    extracted_paths: list[str] = []

    def fake_extract_text(path: Path) -> str:
        extracted_paths.append(str(path))
        return "127.0.0.1 localhost"

    monkeypatch.setattr(rag, "extract_text", fake_extract_text)
    monkeypatch.setattr(
        rag,
        "call_chat",
        lambda *_, **__: json.dumps(
            {
                "ready": True,
                "questions": [],
                "retrieval_task": "고소장 판례 검색",
                "drafting_goal": "고소장 작성",
                "summary": "문서 초안을 준비합니다.",
            },
            ensure_ascii=False,
        ),
    )
    client = TestClient(create_app(manager=manager, frontend_dist=PROJECT_ROOT / "dist"))

    response = client.post(
        "/api/document-preflight",
        json={
            "userTask": "고소장 작성해줘",
            "documentPresetId": "complaint",
            "samplePath": "/etc/hosts",
        },
    )

    assert response.status_code == 400
    assert extracted_paths == []


def test_document_sample_path_resolver_rejects_untrusted_file_references(tmp_path: Path) -> None:
    manager = LawkeyJobManager(runs_root=tmp_path / "runs")
    upload_dir = tmp_path / "runs" / "_uploads"
    upload_dir.mkdir(parents=True)
    allowed_upload = upload_dir / "abc123_sample.md"
    allowed_upload.write_text("allowed upload", encoding="utf-8")
    traversal_target = tmp_path / "runs" / "outside.md"
    traversal_target.write_text("escaped", encoding="utf-8")
    nonallowlisted = tmp_path / "local.md"
    nonallowlisted.write_text("not allowlisted", encoding="utf-8")
    symlink = upload_dir / "hosts-link.md"
    symlink.symlink_to(nonallowlisted)

    assert manager._resolve_sample_paths(
        document_preset_id="",
        sample_path="upload:abc123_sample.md",
        user_task="고소장 작성해줘",
    ) == [allowed_upload.resolve()]

    rejected = [
        "/etc/hosts",
        str(upload_dir / ".." / "outside.md"),
        str(symlink),
        str(nonallowlisted),
        "upload:../outside.md",
    ]
    for sample_path in rejected:
        try:
            manager._resolve_sample_paths(
                document_preset_id="",
                sample_path=sample_path,
                user_task="고소장 작성해줘",
            )
        except ValueError as exc:
            assert "samplePath is not allowlisted" in str(exc)
        else:
            raise AssertionError(f"expected samplePath rejection for {sample_path!r}")


def test_document_preflight_prompt_and_retrieval_task_include_continuation_context(tmp_path: Path) -> None:
    manager = LawkeyJobManager(runs_root=tmp_path / "runs")
    conversation = [
        {"role": "user", "text": "변호인의견서 작성"},
        {"role": "assistant", "text": "처분 일자를 알려주세요."},
        {"role": "user", "text": "2025. 3. 1. 기숙사 벌점 처분입니다."},
    ]

    prompt = manager._build_document_preflight_prompt(
        user_task="2025. 3. 1. 기숙사 벌점 처분입니다.",
        conversation=conversation,
        sample_excerpt="변호인의견서 예시 본문",
    )
    retrieval_task = manager._build_document_retrieval_task("기숙사 벌점 처분 취소 변호인의견서", conversation)

    assert "변호인의견서 작성" in prompt
    assert "처분 일자를 알려주세요." in prompt
    assert "2025. 3. 1. 기숙사 벌점 처분입니다." in prompt
    assert "변호인의견서 예시 본문" in prompt
    assert "기숙사 벌점 처분 취소 변호인의견서" in retrieval_task
    assert "2025. 3. 1. 기숙사 벌점 처분입니다." in retrieval_task


def test_document_goal_does_not_duplicate_latest_clarification(tmp_path: Path) -> None:
    manager = LawkeyJobManager(runs_root=tmp_path / "runs")
    latest_facts = (
        "피고소인은 성명불상 공개 발언자이고, 2026. 4. 12. 오후 10시 30분 서울 광장에서 "
        "경찰과 국가에 불충성하라고 공개 발언했습니다. 발언 영상 캡처가 있고 명예훼손 또는 모욕 고소장으로 작성해줘."
    )
    conversation = [
        {"role": "user", "text": "경찰, 국가에 대해서 회의감을 내뱉는 건 죄임?"},
        {"role": "assistant", "text": "표현 대상과 구체적 사실 적시 여부가 핵심입니다."},
        {"role": "user", "text": "그럼 이 사람을 고소하는 고소장 작성해줘"},
        {"role": "assistant", "text": "사건 발생일시와 피고소인, 문제 표현을 알려주세요."},
        {"role": "user", "text": latest_facts},
    ]

    goal = manager._build_document_goal_text(latest_facts, conversation)

    assert goal.count("2026. 4. 12.") == 1
    assert goal.count("성명불상 공개 발언자") == 1
    assert "그럼 이 사람을 고소하는 고소장 작성해줘" in goal


def test_complaint_preflight_requires_concrete_facts_even_if_model_says_ready(tmp_path: Path, monkeypatch) -> None:
    manager = LawkeyJobManager(runs_root=tmp_path / "runs")

    monkeypatch.setattr(manager, "_resolve_sample_paths", lambda **_: [])
    monkeypatch.setattr(
        rag,
        "call_chat",
        lambda *_, **__: json.dumps(
            {
                "ready": True,
                "questions": [],
                "retrieval_task": "카카오톡 단체방 모욕죄 고소장 판례 검색",
                "drafting_goal": "카카오톡 단체방 모욕죄 고소장 작성",
                "summary": "문서 초안 작성을 시작합니다.",
            },
            ensure_ascii=False,
        ),
    )

    generic = manager.document_preflight(
        {
            "userTask": "고소장 작성해줘",
            "documentPresetId": "complaint",
            "conversation": [
                {"role": "user", "text": "카카오톡 단체방에서 모욕죄가 성립하려면 어떤 요건을 봐야해?"},
                {"role": "assistant", "text": "공연성, 특정성, 모욕성이 핵심입니다."},
                {"role": "user", "text": "고소장 작성해줘"},
            ],
        }
    )

    assert generic["ready"] is False
    assert any("날짜" in question or "시각" in question for question in generic["questions"])
    assert any("피고소인" in question or "상대방" in question for question in generic["questions"])
    assert any("어떤 말" in question or "표현" in question for question in generic["questions"])

    concrete = manager.document_preflight(
        {
            "userTask": (
                "2026. 4. 1. 오후 9시, 18명이 있는 카카오톡 단체방에서 회사 동료 B가 "
                "피해자인 저 A를 실명과 팀장 직책으로 지칭하면서 '사기꾼', '쓰레기'라고 말했습니다. "
                "피고소인은 B, 고소인은 A로 표시해주세요."
            ),
            "documentPresetId": "complaint",
            "conversation": [
                {"role": "user", "text": "카카오톡 단체방에서 모욕죄가 성립하려면 어떤 요건을 봐야해?"},
                {"role": "assistant", "text": "공연성, 특정성, 모욕성이 핵심입니다."},
                {"role": "user", "text": "고소장 작성해줘"},
                {"role": "assistant", "text": "사건 발생일시와 피고소인, 문제 표현을 알려주세요."},
                {
                    "role": "user",
                    "text": (
                        "2026. 4. 1. 오후 9시, 18명이 있는 카카오톡 단체방에서 회사 동료 B가 "
                        "피해자인 저 A를 실명과 팀장 직책으로 지칭하면서 '사기꾼', '쓰레기'라고 말했습니다."
                    ),
                },
            ],
        }
    )

    assert concrete["ready"] is True
    assert concrete["questions"] == []


def test_list_jobs_recovers_completed_runs_from_disk(tmp_path: Path) -> None:
    runs_root = tmp_path / "runs"
    run_dir = runs_root / "job-abc123"
    runtime_dir = run_dir / "_runtime"
    runtime_dir.mkdir(parents=True)
    (runtime_dir / "status.json").write_text(
        json.dumps(
            {
                "phase": "done",
                "state": "completed",
                "selected_file_count": 12,
                "completed_chunks": 3,
                "chunk_count": 3,
                "finished_at": 1234567890,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (runtime_dir / "job_meta.json").write_text(
        json.dumps(
            {
                "job_id": "job-abc123",
                "mode": "question",
                "user_task": "징계처분 무효 주장 정리",
                "created_at": 1234567000,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    manager = LawkeyJobManager(runs_root=runs_root)

    rows = manager.list_jobs()

    assert len(rows) == 1
    assert rows[0]["jobId"] == "job-abc123"
    assert rows[0]["state"] == "completed"
    assert rows[0]["userTask"] == "징계처분 무효 주장 정리"


def test_build_result_payload_rewrites_internal_evidence_ids_using_supporting_case_citation(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    result_dir = run_dir / "question_selected_manual"
    result_dir.mkdir(parents=True)

    selected_files = [
        {
            "file_id": "file-1",
            "document_title": "징계처분 취소 사건",
            "case_number": "2022구합30124",
            "court": "춘천지방법원",
            "decision_date": "2022-11-01",
            "case_name": "징계처분취소",
            "relative_path": "precedents/a.txt",
            "absolute_path": "/tmp/a.txt",
            "extracted_text": "원고의 청구를 기각한다.",
        }
    ]
    claim_ledger = [
        {
            "claim_id": "CLAIM-001",
            "claim_axis": "징계권의 정당성 및 재량권",
            "claim_text": "사회통념상 현저히 타당성을 잃지 않은 징계는 정당하다.",
            "case_number": "",
            "court": "",
            "decision_date": "",
            "source_file_id": "",
            "supporting_cases": [
                {
                    "case_number": "2022구합30124",
                    "court": "춘천지방법원",
                    "decision_date": "2022-11-01",
                    "case_name": "징계처분취소",
                }
            ],
            "support_spans": [
                {"quote": "원고의 청구를 기각한다.", "evidence_id": "prd-426fa77359fead42-근거1"}
            ],
        }
    ]

    (result_dir / "selected_files.json").write_text(json.dumps(selected_files, ensure_ascii=False), encoding="utf-8")
    (result_dir / "claim_ledger.json").write_text(json.dumps(claim_ledger, ensure_ascii=False), encoding="utf-8")
    (result_dir / "comparison_summary.json").write_text(json.dumps({}, ensure_ascii=False), encoding="utf-8")
    (result_dir / "final_answer.md").write_text(
        "## 종합 판단\n\n근거 인용 [prd-426fa77359fead42-근거1]",
        encoding="utf-8",
    )
    (result_dir / "chunk_outputs.jsonl").write_text("", encoding="utf-8")

    payload = build_result_payload(run_dir)

    assert "(2022구합30124 판결)" in payload["answerMarkdown"]
    assert "춘천지방법원 2022. 11. 01." not in payload["answerMarkdown"]
    assert "근거 인용" not in payload["answerMarkdown"]
    assert "prd-426fa77359fead42-근거1" not in payload["answerMarkdown"]


def test_build_result_payload_keeps_explicit_case_metadata_when_body_mentions_other_case(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    result_dir = run_dir / "question_selected_manual"
    result_dir.mkdir(parents=True)

    selected_files = [
        {
            "file_id": "file-1",
            "document_title": "징계 사건 묶음",
            "case_number": "2022구합12048",
            "court": "의정부지방법원",
            "decision_date": "2023-04-04",
            "case_name": "징계처분취소",
            "relative_path": "precedents/a.txt",
            "absolute_path": "/tmp/a.txt",
            "extracted_text": "의정부지방법원 2023. 4. 4. 선고 2022구합12048 판결. 참고로 대법원 2021. 12. 16. 선고 2021두48083 판결을 인용하였다.",
        }
    ]

    (result_dir / "selected_files.json").write_text(json.dumps(selected_files, ensure_ascii=False), encoding="utf-8")
    (result_dir / "claim_ledger.json").write_text("[]", encoding="utf-8")
    (result_dir / "comparison_summary.json").write_text("{}", encoding="utf-8")
    (result_dir / "final_answer.md").write_text("ok", encoding="utf-8")
    (result_dir / "chunk_outputs.jsonl").write_text("", encoding="utf-8")

    payload = build_result_payload(run_dir)

    assert payload["selectedPrecedents"][0]["citation"] == "2022구합12048 판결"


def test_build_result_payload_uses_claim_source_file_id_for_packed_chunks(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    result_dir = run_dir / "question_selected_manual"
    result_dir.mkdir(parents=True)

    selected_files = [
        {
            "file_id": "file-1",
            "document_title": "징계처분 취소 사건",
            "case_number": "2020구합12259",
            "court": "서울행정법원",
            "decision_date": "2021-06-17",
            "case_name": "감봉처분무효확인",
            "relative_path": "precedents/a.txt",
            "absolute_path": "/tmp/a.txt",
            "extracted_text": "징계권자가 이미 비위를 인지하였다.",
        }
    ]
    chunk_output = {
        "chunk_id": "question-pack-001",
        "file_id": "question-pack-001",
        "claims_proposed": [
            {
                "source_file_id": "file-1",
                "claim_axis": "징계시효 도과",
                "claim_text": "징계시효가 도과하였다.",
                "support_spans": [
                    {
                        "quote": "징계권자가 이미 비위를 인지하였다.",
                        "evidence_id": "근거1",
                    }
                ],
                "oppose_spans": [],
            }
        ],
    }

    (result_dir / "selected_files.json").write_text(json.dumps(selected_files, ensure_ascii=False), encoding="utf-8")
    (result_dir / "claim_ledger.json").write_text(json.dumps([], ensure_ascii=False), encoding="utf-8")
    (result_dir / "comparison_summary.json").write_text(json.dumps({}, ensure_ascii=False), encoding="utf-8")
    (result_dir / "final_answer.md").write_text("ok", encoding="utf-8")
    (result_dir / "chunk_outputs.jsonl").write_text(json.dumps(chunk_output, ensure_ascii=False) + "\n", encoding="utf-8")

    payload = build_result_payload(run_dir)

    assert payload["usedPrecedentIds"] == ["file-1"]


def test_build_precedent_detail_highlights_used_quotes() -> None:
    precedent = {
        "precedentId": "file-1",
        "caseNumber": "2020구합12259",
        "title": "감봉 3월 징계처분 무효 확인 사건",
        "court": "서울행정법원",
        "decisionDate": "2021-06-17",
        "fullText": "앞문장. 징계권자가 이미 비위를 인지하고도 아무 조치를 하지 아니하였다. 뒷문장.",
        "sourcePath": "/tmp/a.txt",
    }
    chunk_outputs = [
        {
            "file_id": "file-1",
            "claims_proposed": [
                {
                    "source_file_id": "file-1",
                    "claim_axis": "징계권자의 비위 인지 후 미조치 사건의 합산 징계 부당성",
                    "context_summary": "징계권자의 인지 시점과 방치가 핵심이다.",
                    "case_summary": "방치된 비위를 뒤늦게 합산 징계한 사례다.",
                    "support_spans": [
                        {
                            "quote": "징계권자가 이미 비위를 인지하고도 아무 조치를 하지 아니하였다.",
                            "evidence_id": "근거1",
                        }
                    ],
                    "oppose_spans": [],
                }
            ],
        }
    ]

    detail = build_precedent_detail(precedent, chunk_outputs)

    assert detail["precedentId"] == "file-1"
    assert detail["usedQuotes"][0]["charStart"] > 0
    assert detail["usedQuotes"][0]["charEnd"] > detail["usedQuotes"][0]["charStart"]
    assert detail["summaryOverlay"] == "결론적으로 방치된 비위를 뒤늦게 합산 징계한 사례다."
    assert detail["contextOverlay"] == "징계권자의 인지 시점과 방치가 핵심이다."


def test_legacy_answer_rewrite_splits_inline_citation_quote_and_flattens_case_name() -> None:
    claim_ledger = [
        {
            "claim_id": "CLAIM-SKI",
            "source_file_id": "prd-ski",
            "case_number": "95가합60464",
            "court": "서울지법",
            "decision_date": "1992-01-04",
            "case_name": "손해배상(기)",
            "support_spans": [
                {
                    "quote": "위 보호펜스에 충격을 완화해 줄 장치가 없었다.",
                    "evidence_id": "95가합60464-근거1",
                }
            ],
        }
    ]
    raw = (
        "시설 하자가 문제됩니다 "
        '**(서울지법 1992. 01. 04. 선고 95가합60464 판결 (손해배상(기)))** '
        '"위 보호펜스에 충격을 완화해 줄 장치가 없었다.".'
    )

    rewritten = backend_models._rewrite_answer_markdown_citations(raw, claim_ledger)

    assert "**(서울지법" not in rewritten
    assert "(95가합60464 판결)." in rewritten
    assert "\n\n> 위 보호펜스에 충격을 완화해 줄 장치가 없었다." in rewritten
    assert "서울지법 1992. 01. 04." not in rewritten
    assert ")))" not in rewritten


def test_answer_rewrite_drops_adjacent_duplicate_quote_after_blockquote() -> None:
    quote = "교통사고 발생시 필요한 조치를 다하였다고 볼 수 없다."
    short = "필요한 조치를 다하였다고 볼 수 없다."
    raw = f"(2011노1493 판결)\n\n> {quote}\n\n\"{quote}\"\n\n> {quote}\n\n> {short}\n\n따라서 조치 여부가 중요합니다."

    rewritten = backend_models._rewrite_answer_markdown_citations(raw, [])

    assert rewritten.count(quote) == 1
    assert short not in rewritten.replace(quote, "")
    assert f"> {quote}" in rewritten
    assert f"\"{quote}\"" not in rewritten
    assert "따라서 조치 여부가 중요합니다." in rewritten


def test_answer_rewrite_renames_headings_and_moves_glossary_to_easy_overview_bottom() -> None:
    raw = "\n".join(
        [
            "## 한눈에 보는 결론",
            "",
            "경찰이 유심을 써서 로그인하는 방식 자체보다 절차가 중요합니다.",
            "",
            "**참여권**: 수사기관이 디지털 증거를 조사할 때 피의자나 변호인이 과정을 지켜볼 권리.",
            "**위법수집증거**: 정당한 절차 없이 수집되어 유죄 근거로 쓰기 어려운 증거.",
            "",
            "정리하면, 지금 자료로는 절차 준수 여부가 결론을 가를 가능성이 큽니다.",
            "",
            "---",
            "",
            "## 법조인용 상세 분석",
            "",
            "## 종합 판단",
        ]
    )

    rewritten = backend_models._rewrite_answer_markdown_citations(raw, [])

    assert "## 어렵지 않아요" in rewritten
    assert "## 상세 분석" in rewritten
    assert "## 한눈에 보는 결론" not in rewritten
    assert "## 법조인용 상세 분석" not in rewritten
    assert rewritten.index("정리하면, 지금 자료로는") < rewritten.index("**참여권**")
    assert rewritten.index("**위법수집증거**") < rewritten.index("---")


def test_beta6_and_beta7_no_longer_use_kakao_or_military_special_anchors() -> None:
    assert backend_search._beta6_detect_query_kind("경찰이 피의자 유심 빼서 카톡 로그인하는거 합법임?") == "generic"
    assert backend_search._beta6_detect_query_kind("군대에서 키는 어캐 관리해야함?") == "generic"
    assert backend_search._beta7_detect_domain_anchor_kind("경찰이 피의자 유심 빼서 카톡 로그인하는거 합법임?") == ""
    assert backend_search._beta7_detect_domain_anchor_kind("군대에서 키는 어캐 관리해야함?") == ""
    assert (
        backend_search._beta7_detect_domain_anchor_kind(
            "스노우보드 타다가 뒤에서 추돌하려는 사람을 피하려다 스키장 펜스에 부딪혀 어깨가 골절됨"
        )
        == "ski_snowboard_collision"
    )


def test_beta7_ski_collision_score_prefers_slope_collision_and_fence_cases() -> None:
    direct = (
        "용평리조트 스키장 슬로프에서 스키를 타고 내려오던 중 다른 스키어를 피하기 위하여 방향을 전환하는 과정에서 "
        "슬로프 계곡 방향에 설치된 안전망을 넘어 나무와 충돌하였다. 안전망 설치·유지와 손해배상 책임이 문제되었다."
    )
    snowboard_fence = (
        "스키장에서 스노우보드를 타고 슬로프를 활강하다가 보호펜스의 철제기둥에 충돌하였다. "
        "보호펜스에 충격을 완화할 장치가 없었는지와 이용자 과실이 다투어졌다."
    )
    noise = "승용차가 교차로에서 추돌하여 운전자가 어깨 통증을 호소한 교통사고 손해배상 사건이다."

    direct_score, direct_reasons = backend_search._beta7_score_ski_snowboard_collision_text(direct)
    snowboard_score, snowboard_reasons = backend_search._beta7_score_ski_snowboard_collision_text(snowboard_fence)
    noise_score, _noise_reasons = backend_search._beta7_score_ski_snowboard_collision_text(noise)

    assert direct_score > noise_score + 25
    assert snowboard_score > noise_score + 25
    assert "winter_slope" in direct_reasons
    assert "safety_facility" in snowboard_reasons


def test_beta7_ski_collision_score_demotes_criminal_safety_noise() -> None:
    civil_collision = (
        "손해배상 사건에서 스키장 슬로프를 내려오던 원고가 뒤에서 추돌하려는 스키어를 피하기 위해 "
        "방향을 전환하다가 충돌하였다. 이용자의 주의의무와 과실상계가 문제되었다."
    )
    criminal_safety = (
        "업무상과실치사 형사 사건에서 피고인은 스키장 안전시설 관리를 담당하였고, "
        "벌금형과 체육시설의 설치 이용에 관한 법률 위반 여부가 문제되었다."
    )

    civil_score, civil_reasons = backend_search._beta7_score_ski_snowboard_collision_text(civil_collision)
    criminal_score, criminal_reasons = backend_search._beta7_score_ski_snowboard_collision_text(criminal_safety)

    assert civil_score > criminal_score + 25
    assert "rear_collision_avoidance" in civil_reasons
    assert "criminal_safety_noise" in criminal_reasons


def test_simplify_precedent_uses_case_number_only_when_lawgokr_date_is_disposition_date() -> None:
    row = {
        "file_id": "prd-20672df0e0d2f554",
        "document_title": "요양급여부지급처분취소",
        "case_number": "2020누10898",
        "court": "대전고등법원",
        "decision_date": "2019-03-07",
        "case_name": "요양급여부지급처분취소",
        "relative_path": "07_lawgokr_fulltext/411630.json",
        "absolute_path": "/mnt/d/korean-law-data/07_lawgokr_fulltext/411630.json",
        "extracted_text": (
            "피고가 2019. 3. 7. 원고에 대하여 한 요양불승인 처분을 취소한다. "
            "이 사건은 버스운전기사의 졸음운전 중 교통사고에 관한 것이다."
        ),
    }

    simplified = backend_models._simplify_precedent(row)

    assert simplified["citation"] == "2020누10898 판결"
    assert simplified["decisionDate"] == ""
    assert "2019. 03. 07." not in simplified["citation"]
    assert "대전고등법원" not in simplified["citation"]


def test_simplify_precedent_ignores_compact_source_header_for_public_label() -> None:
    row = {
        "file_id": "prd-7eddef71ac2accbd",
        "document_title": "유족급여및장의비부지급처분취소",
        "case_number": "2023구합75058",
        "court": "대법원",
        "decision_date": "2024-03-08",
        "case_name": "3",
        "relative_path": "03_distressed_korean_law/part-000.parquet",
        "absolute_path": "/tmp/03_distressed_korean_law/part-000.parquet",
        "extracted_text": (
            "240853\n"
            "유족급여및장의비부지급처분취소\n"
            "2023구합75058\n"
            "20240419\n"
            "선고\n"
            "서울행법\n"
            "원고의 남편은 퇴근 중 오토바이를 운전하다가 사료 운반 트럭과 충돌하였다."
        ),
    }

    simplified = backend_models._simplify_precedent(row)

    assert simplified["court"] == ""
    assert simplified["decisionDate"] == ""
    assert simplified["citation"] == "2023구합75058 판결"
    assert "대법원" not in simplified["citation"]
    assert "2024. 03. 08." not in simplified["citation"]


def test_simplify_precedent_public_citation_uses_case_number_only_even_with_full_metadata() -> None:
    row = {
        "file_id": "prd-public-case-number-only",
        "document_title": "유족급여및장의비부지급처분취소",
        "case_number": "2023구합75058",
        "court": "서울행정법원",
        "decision_date": "2024-04-19",
        "case_name": "유족급여및장의비부지급처분취소",
        "relative_path": "03_distressed_korean_law/part-000.parquet",
        "absolute_path": "/tmp/03_distressed_korean_law/part-000.parquet",
        "extracted_text": (
            "240853\n"
            "유족급여및장의비부지급처분취소\n"
            "2023구합75058\n"
            "20240419\n"
            "선고\n"
            "서울행법\n"
            "원고의 남편은 퇴근 중 오토바이를 운전하다가 사료 운반 트럭과 충돌하였다."
        ),
    }

    simplified = backend_models._simplify_precedent(row)

    assert simplified["citation"] == "2023구합75058 판결"
    assert simplified["court"] == ""
    assert simplified["decisionDate"] == ""


def test_simplify_precedent_public_citation_anonymizes_without_case_number() -> None:
    row = {
        "file_id": "prd-anonymous",
        "document_title": "서울행정법원 2024. 04. 19. 선고 2023구합75058 판결",
        "case_number": "",
        "court": "서울행정법원",
        "decision_date": "2024-04-19",
        "case_name": "1",
        "relative_path": "03_distressed_korean_law/part-000.parquet",
        "absolute_path": "/tmp/03_distressed_korean_law/part-000.parquet",
        "extracted_text": "본문은 진짜이지만 식별자는 upstream rule-based 추정값일 수 있다.",
    }

    simplified = backend_models._simplify_precedent(row)

    assert simplified["citation"] == "참조 판례"
    assert simplified["caseNumber"] == ""
    assert simplified["court"] == ""
    assert simplified["decisionDate"] == ""


def test_writer_token_substitution_uses_sanitized_claim_citation() -> None:
    claim_ledger = [
        {
            "_writer_claim_index": 1,
            "citation": "2020누10898 판결",
            "source_file_id": "prd-20672df0e0d2f554",
            "case_number": "2020누10898",
            "court": "대전고등법원",
            "decision_date": "2019-03-07",
            "case_name": "요양급여부지급처분취소",
            "support_spans": [
                {
                    "quote": "피고가 2019. 3. 7. 원고에 대하여 한 요양불승인 처분을 취소한다.",
                    "evidence_id": "2020누10898-근거1",
                }
            ],
        }
    ]

    rewritten = backend_models._rewrite_beta7_answer_markdown("이 사건은 [1-S1]에 비추어 위법합니다.", claim_ledger)

    assert "(2020누10898 판결)" in rewritten
    assert "> 피고가 2019. 3. 7. 원고에 대하여 한 요양불승인 처분을 취소한다." in rewritten
    assert "대전고등법원 2019. 03. 07." not in rewritten


def test_writer_token_substitution_ignores_stale_full_claim_citation() -> None:
    claim_ledger = [
        {
            "_writer_claim_index": 1,
            "citation": "대전고등법원 2019. 03. 07. 선고 2020누10898 판결",
            "source_file_id": "prd-20672df0e0d2f554",
            "case_number": "2020누10898",
            "court": "대전고등법원",
            "decision_date": "2019-03-07",
            "case_name": "요양급여부지급처분취소",
            "support_spans": [],
        }
    ]

    rewritten = backend_models._rewrite_beta7_answer_markdown("이 사건은 [1]과 비교됩니다.", claim_ledger)

    assert "(2020누10898 판결)" in rewritten
    assert "대전고등법원" not in rewritten
    assert "2019. 03. 07." not in rewritten


def test_beta7_rewrite_collapses_bare_reference_citations_and_orphan_reference_notes() -> None:
    markdown = """## 불리하게 만들 요소

*   과속의 정도가 불리합니다.

### 과속과 사고 사이의 인과관계

또한 **(참조 판례)** 역시 과속과 사고 사이의 인과관계와 관련하여 최신 판례로서 과속과 사고 사이의 인과관계 부정 사례를 다룸

또한 대법원 2025도1049 판결 역시 과속과 사고 사이의 인과관계와 관련하여 최신 대법원 판례로 과속과 사고 사이의 인과관계 부정 사례를 명시하고 있습니다.

## 참고 판례 목록

### 유사한 판례
*   대법원 2016. 07. 29. 선고 86도583 판결 (교통사고처리특례법위반,도로교통법위반)
*   서울지법 북부지원 1982. 10. 02. 선고 84가합932 판결 (손해배상청구사건)
"""

    rewritten = backend_models._rewrite_beta7_answer_markdown(markdown, [])

    assert "또한 **(참조 판례)** 역시" not in rewritten
    assert "대법원 2025도1049 판결 역시" not in rewritten
    assert "2025도1049 판결 역시" in rewritten
    assert "대법원 2016. 07. 29." not in rewritten
    assert "서울지법 북부지원 1982. 10. 02." not in rewritten
    assert "*   86도583 판결" in rewritten
    assert "*   84가합932 판결" in rewritten
    assert "(교통사고처리특례법위반" not in rewritten
    assert "(손해배상청구사건)" not in rewritten


def test_build_result_payload_sanitizes_answer_plan_claim_ids_and_bucket_citations(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    result_dir = run_dir / "question_selected_manual"
    result_dir.mkdir(parents=True)

    selected_files = [
        {
            "file_id": "file-bad-date",
            "document_title": "교통사고처리특례법위반",
            "case_number": "86도583",
            "court": "대법원",
            "decision_date": "20160729",
            "case_name": "교통사고처리특례법위반",
            "relative_path": "precedents/a.txt",
            "absolute_path": "/tmp/a.txt",
            "extracted_text": "전방 시야가 제한된 도로에서 사고 회피 가능성을 판단하였다.",
        }
    ]
    claim_ledger = [
        {
            "claim_id": "CLAIM-001",
            "claim_axis": "과속과 사고 사이의 인과관계",
            "source_file_id": "file-bad-date",
            "supporting_cases": [
                {
                    "case_number": "86도583",
                    "court": "대법원",
                    "decision_date": "20160729",
                    "case_name": "교통사고처리특례법위반",
                }
            ],
        }
    ]
    answer_plan = {
        "likely_outcome": "사고 회피 가능성이 핵심입니다 (CLAIM-001).",
        "confidence_basis": ["인과관계 부정 사례가 반복됩니다 (CLAIM-001, CLAIM-002)"],
        "helpful_facts": ["정지거리 감정 (CLAIM-001)"],
        "harmful_facts": ["전방주시 태만 CLAIM-003"],
        "body_claim_ids": ["CLAIM-001"],
        "precedent_buckets": {
            "very_similar": [
                {
                    "case_number": "86도583",
                    "court": "대법원",
                    "decision_date": "2016-07-29",
                    "case_name": "교통사고처리특례법위반",
                    "supported_claim_ids": ["CLAIM-001"],
                    "why": "시야 차단 쟁점",
                }
            ],
            "similar": [],
            "usable": [],
            "other": [],
        },
    }

    (result_dir / "selected_files.json").write_text(json.dumps(selected_files, ensure_ascii=False), encoding="utf-8")
    (result_dir / "claim_ledger.json").write_text(json.dumps(claim_ledger, ensure_ascii=False), encoding="utf-8")
    (result_dir / "answer_plan.json").write_text(json.dumps(answer_plan, ensure_ascii=False), encoding="utf-8")
    (result_dir / "comparison_summary.json").write_text(json.dumps({}, ensure_ascii=False), encoding="utf-8")
    (result_dir / "final_answer.md").write_text("ok", encoding="utf-8")
    (result_dir / "chunk_outputs.jsonl").write_text("", encoding="utf-8")

    payload = build_result_payload(run_dir)

    assert "CLAIM-" not in payload["answerPlan"]["likely_outcome"]
    assert all("CLAIM-" not in item for item in payload["answerPlan"]["confidence_basis"])
    assert all("CLAIM-" not in item for item in payload["answerPlan"]["helpful_facts"])
    assert all("CLAIM-" not in item for item in payload["answerPlan"]["harmful_facts"])
    row = payload["answerPlan"]["precedent_buckets"]["very_similar"][0]
    assert row["citation"] == "86도583 판결"
    assert row["court"] == ""
    assert row["decision_date"] == ""
    assert row["case_name"] == ""


def test_build_result_payload_enriches_answer_plan_buckets_with_precedent_metadata(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    result_dir = run_dir / "question_selected_manual"
    result_dir.mkdir(parents=True)

    selected_files = [
        {
            "file_id": "file-1",
            "document_title": "징계처분 취소 사건",
            "case_number": "2020구합12259",
            "court": "서울행정법원",
            "decision_date": "20210617",
            "case_name": "감봉처분무효확인",
            "relative_path": "precedents/a.txt",
            "absolute_path": "/tmp/a.txt",
            "extracted_text": "징계권자가 이미 비위를 인지하고도 아무 조치를 하지 아니하였다.",
        }
    ]
    claim_ledger = [
        {
            "claim_id": "CLAIM-001",
            "claim_axis": "징계시효",
            "case_summary": "징계권자의 사전 인지 후 방치가 인정되어 처분이 무효라고 본 사례다.",
            "supporting_cases": [
                {
                    "case_number": "2020구합12259",
                    "court": "서울행정법원",
                    "decision_date": "20210617",
                    "case_name": "감봉처분무효확인",
                }
            ],
        }
    ]
    answer_plan = {
        "body_claim_ids": ["CLAIM-001"],
        "precedent_buckets": {
            "very_similar": [{"case_number": "2020구합12259", "why": "사실관계와 쟁점이 가장 가깝다."}],
            "similar": [],
            "usable": [],
            "other": [],
        },
    }

    (result_dir / "selected_files.json").write_text(json.dumps(selected_files, ensure_ascii=False), encoding="utf-8")
    (result_dir / "claim_ledger.json").write_text(json.dumps(claim_ledger, ensure_ascii=False), encoding="utf-8")
    (result_dir / "answer_plan.json").write_text(json.dumps(answer_plan, ensure_ascii=False), encoding="utf-8")
    (result_dir / "comparison_summary.json").write_text(json.dumps({}, ensure_ascii=False), encoding="utf-8")
    (result_dir / "final_answer.md").write_text("ok", encoding="utf-8")
    (result_dir / "chunk_outputs.jsonl").write_text("", encoding="utf-8")

    payload = build_result_payload(run_dir)

    bucket_row = payload["answerPlan"]["precedent_buckets"]["very_similar"][0]
    assert bucket_row["precedentId"] == "file-1"
    assert bucket_row["citation"] == "2020구합12259 판결"
    assert "무효라고 본 사례" in bucket_row["summary"]


def test_build_result_payload_prefers_bucket_case_number_over_claim_source_id(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    result_dir = run_dir / "question_selected_manual"
    result_dir.mkdir(parents=True)

    selected_files = [
        {
            "file_id": "file-local",
            "document_title": "하급심 증거인멸교사",
            "case_number": "2016고합1056",
            "relative_path": "precedents/local.txt",
            "absolute_path": "/tmp/local.txt",
            "extracted_text": "비서에게 개인일정을 삭제하라고 지시하였다.",
        },
        {
            "file_id": "file-supreme",
            "document_title": "대법원 증거은닉교사",
            "case_number": "2016도5596",
            "relative_path": "precedents/supreme.txt",
            "absolute_path": "/tmp/supreme.txt",
            "extracted_text": "방어권의 남용이라고 볼 수 있을 때는 증거은닉교사죄로 처벌할 수 있다.",
        },
    ]
    claim_ledger = [
        {
            "claim_id": "CLAIM-001",
            "claim_axis": "자기 증거 인멸 교사",
            "source_file_id": "file-local",
            "supporting_cases": [{"case_number": "2016도5596"}],
        }
    ]
    answer_plan = {
        "body_claim_ids": ["CLAIM-001"],
        "precedent_buckets": {
            "very_similar": [{"case_number": "2016도5596", "supported_claim_ids": ["CLAIM-001"], "why": "대법원 법리"}],
            "similar": [],
            "usable": [],
            "other": [],
        },
    }

    (result_dir / "selected_files.json").write_text(json.dumps(selected_files, ensure_ascii=False), encoding="utf-8")
    (result_dir / "claim_ledger.json").write_text(json.dumps(claim_ledger, ensure_ascii=False), encoding="utf-8")
    (result_dir / "answer_plan.json").write_text(json.dumps(answer_plan, ensure_ascii=False), encoding="utf-8")
    (result_dir / "comparison_summary.json").write_text("{}", encoding="utf-8")
    (result_dir / "final_answer.md").write_text("ok", encoding="utf-8")
    (result_dir / "chunk_outputs.jsonl").write_text("", encoding="utf-8")

    payload = build_result_payload(run_dir)

    bucket_row = payload["answerPlan"]["precedent_buckets"]["very_similar"][0]
    assert bucket_row["precedentId"] == "file-supreme"
    assert bucket_row["citation"] == "2016도5596 판결"
    assert "대법원 증거은닉교사" in bucket_row["title"]


def test_build_result_payload_annotates_lbox_reference_list_items_with_precedent_id(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    result_dir = run_dir / "question_selected_manual"
    result_dir.mkdir(parents=True)

    selected_files = [
        {
            "file_id": "prd-lbox-1",
            "document_title": "LBOX 익명화",
            "case_number": "",
            "relative_path": "precedents/lbox.txt",
            "absolute_path": "/tmp/lbox.txt",
            "extracted_text": "자기의 형사 사건에 관한 증거를 인멸하기 위하여 타인을 교사하면 증거인멸교사죄가 성립한다.",
        }
    ]
    claim_ledger = [
        {
            "claim_id": "CLAIM-001",
            "claim_axis": "증거인멸교사죄 성립",
            "source_file_id": "prd-lbox-1",
            "case_name": "LBOX 익명화",
            "support_spans": [
                {
                    "quote": "자기의 형사 사건에 관한 증거를 인멸하기 위하여 타인을 교사하면 증거인멸교사죄가 성립한다.",
                    "evidence_id": "q1",
                }
            ],
        }
    ]
    answer_plan = {
        "body_claim_ids": ["CLAIM-001"],
        "precedent_buckets": {
            "very_similar": [
                {"case_number": "", "supported_claim_ids": ["CLAIM-001"], "why": "익명화된 대법원 참조 법리"}
            ],
            "similar": [],
            "usable": [],
            "other": [],
        },
    }

    (result_dir / "selected_files.json").write_text(json.dumps(selected_files, ensure_ascii=False), encoding="utf-8")
    (result_dir / "claim_ledger.json").write_text(json.dumps(claim_ledger, ensure_ascii=False), encoding="utf-8")
    (result_dir / "answer_plan.json").write_text(json.dumps(answer_plan, ensure_ascii=False), encoding="utf-8")
    (result_dir / "comparison_summary.json").write_text("{}", encoding="utf-8")
    (result_dir / "final_answer.md").write_text(
        "## 상세 분석\n\n## 참고 판례 목록\n\n### 매우 유사한 판례\n*   참조 판례 (LBOX 익명화)",
        encoding="utf-8",
    )
    (result_dir / "chunk_outputs.jsonl").write_text("", encoding="utf-8")

    payload = build_result_payload(run_dir)

    assert "참조 판례 (LBOX 익명화 [prd:prd-lbox-1])" in payload["answerMarkdown"]


def test_build_result_payload_annotates_lbox_reference_list_from_body_token_when_bucket_missing(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    result_dir = run_dir / "question_selected_manual"
    result_dir.mkdir(parents=True)

    selected_files = [
        {
            "file_id": "prd-1ff6fe8d3d3020c3",
            "document_title": "LBOX 익명화",
            "case_number": "",
            "relative_path": "precedents/lbox-body.txt",
            "absolute_path": "/tmp/lbox-body.txt",
            "extracted_text": "자기의 형사 사건에 관한 증거를 인멸하기 위하여 타인을 교사하면 증거인멸교사죄가 성립한다.",
        },
        {
            "file_id": "file-supreme",
            "document_title": "대법원 증거은닉교사",
            "case_number": "2016도5596",
            "relative_path": "precedents/supreme.txt",
            "absolute_path": "/tmp/supreme.txt",
            "extracted_text": "방어권의 남용이라고 볼 수 있을 때는 증거은닉교사죄로 처벌할 수 있다.",
        },
    ]
    claim_ledger = [
        {
            "claim_id": "CLAIM-001",
            "claim_axis": "증거은닉교사죄 성립",
            "source_file_id": "file-supreme",
            "supporting_cases": [{"case_number": "2016도5596"}],
        }
    ]
    answer_plan = {
        "body_claim_ids": ["CLAIM-001"],
        "precedent_buckets": {
            "very_similar": [{"case_number": "2016도5596", "supported_claim_ids": ["CLAIM-001"]}],
            "similar": [],
            "usable": [],
            "other": [],
        },
    }

    (result_dir / "selected_files.json").write_text(json.dumps(selected_files, ensure_ascii=False), encoding="utf-8")
    (result_dir / "claim_ledger.json").write_text(json.dumps(claim_ledger, ensure_ascii=False), encoding="utf-8")
    (result_dir / "answer_plan.json").write_text(json.dumps(answer_plan, ensure_ascii=False), encoding="utf-8")
    (result_dir / "comparison_summary.json").write_text("{}", encoding="utf-8")
    (result_dir / "final_answer.md").write_text(
        "본문 참조 판례 [prd:prd-1ff6fe8d3d3020c3])\n\n"
        "## 참고 판례 목록\n\n"
        "### 매우 유사한 판례\n"
        "*   참조 판례 (LBOX 익명화)",
        encoding="utf-8",
    )
    (result_dir / "chunk_outputs.jsonl").write_text("", encoding="utf-8")

    payload = build_result_payload(run_dir)

    assert "참조 판례 (LBOX 익명화 [prd:prd-1ff6fe8d3d3020c3])" in payload["answerMarkdown"]


def test_build_result_payload_limits_selected_claims_and_used_precedents_to_body_claims(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    result_dir = run_dir / "question_selected_manual"
    result_dir.mkdir(parents=True)

    selected_files = [
        {
            "file_id": "file-1",
            "document_title": "징계처분 취소 사건",
            "case_number": "2020구합12259",
            "court": "서울행정법원",
            "decision_date": "20210617",
            "case_name": "감봉처분무효확인",
            "relative_path": "precedents/a.txt",
            "absolute_path": "/tmp/a.txt",
            "extracted_text": "징계권자가 이미 비위를 인지하고도 아무 조치를 하지 아니하였다.",
        },
        {
            "file_id": "file-2",
            "document_title": "다른 판례",
            "case_number": "2017구합21310",
            "court": "부산지방법원",
            "decision_date": "20180209",
            "case_name": "해임처분취소",
            "relative_path": "precedents/b.txt",
            "absolute_path": "/tmp/b.txt",
            "extracted_text": "다른 판례 본문.",
        },
    ]
    claim_ledger = [
        {
            "claim_id": "CLAIM-001",
            "claim_axis": "징계시효",
            "supporting_cases": [
                {"case_number": "2020구합12259", "court": "서울행정법원", "decision_date": "20210617", "case_name": "감봉처분무효확인"}
            ],
            "source_file_id": "file-1",
        },
        {
            "claim_id": "CLAIM-002",
            "claim_axis": "재량권 남용",
            "supporting_cases": [
                {"case_number": "2017구합21310", "court": "부산지방법원", "decision_date": "20180209", "case_name": "해임처분취소"}
            ],
            "source_file_id": "file-2",
        },
    ]
    answer_plan = {
        "body_claim_ids": ["CLAIM-001"],
        "precedent_buckets": {"very_similar": [], "similar": [], "usable": [], "other": []},
    }

    (result_dir / "selected_files.json").write_text(json.dumps(selected_files, ensure_ascii=False), encoding="utf-8")
    (result_dir / "claim_ledger.json").write_text(json.dumps(claim_ledger, ensure_ascii=False), encoding="utf-8")
    (result_dir / "answer_plan.json").write_text(json.dumps(answer_plan, ensure_ascii=False), encoding="utf-8")
    (result_dir / "comparison_summary.json").write_text(json.dumps({}, ensure_ascii=False), encoding="utf-8")
    (result_dir / "final_answer.md").write_text("ok", encoding="utf-8")
    (result_dir / "chunk_outputs.jsonl").write_text("", encoding="utf-8")

    payload = build_result_payload(run_dir)

    assert [claim["claim_id"] for claim in payload["selectedClaims"]] == ["CLAIM-001"]
    assert payload["usedPrecedentIds"] == ["file-1"]


def test_duplicate_precedent_ids_resolve_to_retained_detail(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    result_dir = run_dir / "question_selected_manual"
    result_dir.mkdir(parents=True)

    selected_files = [
        {
            "file_id": "file-weak",
            "document_title": "대통령 탄핵",
            "case_number": "2024헌나8",
            "court": "",
            "decision_date": "",
            "case_name": "대통령 탄핵",
            "extracted_text": "짧은 본문.",
        },
        {
            "file_id": "file-retained",
            "document_title": "대통령(윤석열) 탄핵",
            "case_number": "2024헌나8",
            "court": "헌법재판소",
            "decision_date": "20250404",
            "case_name": "대통령(윤석열) 탄핵",
            "extracted_text": "탄핵 사건 본문. 기본권 침해와 권력분립 침해를 판단하였다. 결론.",
        },
    ]
    claim_ledger = [
        {
            "claim_id": "CLAIM-001",
            "claim_axis": "권력분립 침해",
            "claim_text": "권력분립 침해가 문제된다.",
            "source_file_id": "file-weak",
            "supporting_cases": [
                {"case_number": "2024헌나8", "court": "헌법재판소", "decision_date": "20250404", "case_name": "대통령(윤석열) 탄핵"}
            ],
            "support_spans": [{"quote": "권력분립 침해를 판단하였다."}],
        }
    ]
    answer_plan = {
        "body_claim_ids": ["CLAIM-001"],
        "precedent_buckets": {
            "very_similar": [{"case_number": "2024헌나8", "supported_claim_ids": ["CLAIM-001"]}],
            "similar": [],
            "usable": [],
            "other": [],
        },
    }

    (result_dir / "selected_files.json").write_text(json.dumps(selected_files, ensure_ascii=False), encoding="utf-8")
    (result_dir / "claim_ledger.json").write_text(json.dumps(claim_ledger, ensure_ascii=False), encoding="utf-8")
    (result_dir / "answer_plan.json").write_text(json.dumps(answer_plan, ensure_ascii=False), encoding="utf-8")
    (result_dir / "comparison_summary.json").write_text(json.dumps({}, ensure_ascii=False), encoding="utf-8")
    (result_dir / "final_answer.md").write_text("ok", encoding="utf-8")
    chunk_output = {
        "file_id": "file-weak",
        "claims_proposed": [
            {
                "claim_id": "CLAIM-001",
                "claim_axis": "권력분립 침해",
                "claim_text": "권력분립 침해가 문제된다.",
                "source_file_id": "file-weak",
                "case_summary": "권력분립 쟁점을 판단한 사건",
                "context_summary": "탄핵 사건에서 권력분립 침해 여부가 문제되었다.",
                "support_spans": [{"quote": "권력분립 침해를 판단하였다.", "evidence_id": "ev-1"}],
            }
        ],
    }
    (result_dir / "chunk_outputs.jsonl").write_text(json.dumps(chunk_output, ensure_ascii=False) + "\n", encoding="utf-8")

    payload = build_result_payload(run_dir)

    assert payload["selectedPrecedents"][0]["precedentId"] == "file-retained"
    assert "file-weak" in payload["selectedPrecedents"][0]["alternatePrecedentIds"]
    assert payload["selectedClaims"][0]["source_file_id"] == "file-retained"
    assert payload["answerPlan"]["precedent_buckets"]["very_similar"][0]["precedentId"] == "file-retained"
    detail = load_precedent_detail(run_dir, "file-weak")
    assert detail["precedentId"] == "file-retained"
    assert detail["usedQuotes"][0]["quote"] == "권력분립 침해를 판단하였다."
    assert detail["usedQuotes"][0]["charStart"] >= 0
    assert "권력분립 쟁점을 판단한 사건" in detail["summaryOverlay"]


def test_same_case_number_different_cases_do_not_merge_or_mislink_detail(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    result_dir = run_dir / "question_selected_manual"
    result_dir.mkdir(parents=True)

    traffic_quote = "교통사고 발생시 필요한 조치를 다하였다고 볼 수 없다."
    selected_files = [
        {
            "file_id": "traffic-2011-no1493",
            "document_title": "LBOX 익명화",
            "case_number": "",
            "case_name": "LBOX 익명화",
            "relative_path": "precedents/traffic.txt",
            "absolute_path": "/tmp/traffic.txt",
            "extracted_text": f"사고 후 미조치 사건 본문. {traffic_quote} 결론.",
        },
        {
            "file_id": "fund-2011-no1493",
            "document_title": "간접투자자산운용업법 위반",
            "case_number": "2011노1493",
            "case_name": "간접투자자산운용업법 위반",
            "relative_path": "precedents/fund.txt",
            "absolute_path": "/tmp/fund.txt",
            "extracted_text": "간접투자자산운용업법 위반과 투자신탁 재산 운용이 문제된 전혀 다른 사건이다.",
        },
    ]
    claim_ledger = [
        {
            "claim_id": "CLAIM-TRAFFIC",
            "claim_axis": "사고 후 미조치 책임",
            "claim_text": "사고 후 도로교통상 필요한 조치를 해야 한다.",
            "source_file_id": "traffic-2011-no1493",
            "case_summary": "사고 후 미조치 성립 범위를 다룬 교통 사건이다.",
            "context_summary": "교통사고 직후 조치의무가 쟁점이다.",
            "supporting_cases": [
                {
                    "case_number": "2011노1493",
                    "case_name": "도로교통법위반(사고후미조치)",
                }
            ],
            "support_spans": [{"quote": traffic_quote, "evidence_id": "ev-traffic"}],
        }
    ]
    answer_plan = {
        "body_claim_ids": ["CLAIM-TRAFFIC"],
        "precedent_buckets": {
            "very_similar": [{"case_number": "2011노1493", "supported_claim_ids": ["CLAIM-TRAFFIC"]}],
            "similar": [],
            "usable": [],
            "other": [],
        },
    }
    chunk_output = {
        "file_id": "traffic-2011-no1493",
        "claims_proposed": [
            {
                "claim_id": "CLAIM-TRAFFIC",
                "claim_axis": "사고 후 미조치 책임",
                "claim_text": "사고 후 도로교통상 필요한 조치를 해야 한다.",
                "source_file_id": "traffic-2011-no1493",
                "case_summary": "사고 후 미조치 성립 범위를 다룬 교통 사건이다.",
                "context_summary": "교통사고 직후 조치의무가 쟁점이다.",
                "support_spans": [{"quote": traffic_quote, "evidence_id": "ev-traffic"}],
            }
        ],
    }

    (result_dir / "selected_files.json").write_text(json.dumps(selected_files, ensure_ascii=False), encoding="utf-8")
    (result_dir / "claim_ledger.json").write_text(json.dumps(claim_ledger, ensure_ascii=False), encoding="utf-8")
    (result_dir / "answer_plan.json").write_text(json.dumps(answer_plan, ensure_ascii=False), encoding="utf-8")
    (result_dir / "comparison_summary.json").write_text("{}", encoding="utf-8")
    (result_dir / "final_answer.md").write_text("ok", encoding="utf-8")
    (result_dir / "chunk_outputs.jsonl").write_text(json.dumps(chunk_output, ensure_ascii=False) + "\n", encoding="utf-8")

    payload = build_result_payload(run_dir)

    selected_ids = {row["precedentId"] for row in payload["selectedPrecedents"]}
    assert {"traffic-2011-no1493", "fund-2011-no1493"}.issubset(selected_ids)
    fund_row = next(row for row in payload["selectedPrecedents"] if row["precedentId"] == "fund-2011-no1493")
    assert "사고 후 미조치" not in (fund_row.get("summary") or "")
    bucket_row = payload["answerPlan"]["precedent_buckets"]["very_similar"][0]
    assert bucket_row["precedentId"] == "traffic-2011-no1493"
    assert "사고 후 미조치" in bucket_row["summary"]
    detail = load_precedent_detail(run_dir, "traffic-2011-no1493")
    assert "간접투자자산운용업법" not in detail["fullText"]
    assert detail["usedQuotes"][0]["quote"] == traffic_quote
    assert detail["usedQuotes"][0]["charStart"] >= 0
    assert "교통사고 직후 조치의무" in detail["contextOverlay"]


def test_build_result_payload_derives_precedent_buckets_when_plan_is_empty(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    result_dir = run_dir / "question_selected_manual"
    result_dir.mkdir(parents=True)

    selected_files = [
        {
            "file_id": "file-1",
            "document_title": "징계처분 취소 사건",
            "case_number": "2020구합12259",
            "court": "서울행정법원",
            "decision_date": "20210617",
            "case_name": "감봉처분무효확인",
            "relative_path": "precedents/a.txt",
            "absolute_path": "/tmp/a.txt",
            "extracted_text": "징계권자가 이미 비위를 인지하고도 아무 조치를 하지 아니하였다.",
        },
        {
            "file_id": "file-2",
            "document_title": "해임처분 취소 사건",
            "case_number": "2017구합21310",
            "court": "부산지방법원",
            "decision_date": "20180209",
            "case_name": "해임처분취소",
            "relative_path": "precedents/b.txt",
            "absolute_path": "/tmp/b.txt",
            "extracted_text": "징계양정이 지나치면 재량권 남용이 된다.",
        },
    ]
    claim_ledger = [
        {
            "claim_id": "CLAIM-001",
            "claim_axis": "징계시효",
            "claim_text": "징계권자의 사전 인지 후 방치가 있으면 시효 도과 무효 주장이 강해진다.",
            "same_situation_case_exists": True,
            "supporting_case_count": 3,
            "supporting_cases": [
                {"case_number": "2020구합12259", "court": "서울행정법원", "decision_date": "20210617", "case_name": "감봉처분무효확인"}
            ],
            "source_file_id": "file-1",
        },
        {
            "claim_id": "CLAIM-002",
            "claim_axis": "재량권 남용",
            "claim_text": "징계양정이 지나치면 재량권 남용 주장이 가능하다.",
            "supporting_case_count": 1,
            "supporting_cases": [
                {"case_number": "2017구합21310", "court": "부산지방법원", "decision_date": "20180209", "case_name": "해임처분취소"}
            ],
            "source_file_id": "file-2",
        },
    ]
    answer_plan = {
        "body_claim_ids": ["CLAIM-001", "CLAIM-002"],
        "precedent_buckets": {"very_similar": [], "similar": [], "usable": [], "other": []},
    }

    (result_dir / "selected_files.json").write_text(json.dumps(selected_files, ensure_ascii=False), encoding="utf-8")
    (result_dir / "claim_ledger.json").write_text(json.dumps(claim_ledger, ensure_ascii=False), encoding="utf-8")
    (result_dir / "answer_plan.json").write_text(json.dumps(answer_plan, ensure_ascii=False), encoding="utf-8")
    (result_dir / "comparison_summary.json").write_text(json.dumps({}, ensure_ascii=False), encoding="utf-8")
    (result_dir / "final_answer.md").write_text("ok", encoding="utf-8")
    (result_dir / "chunk_outputs.jsonl").write_text("", encoding="utf-8")

    payload = build_result_payload(run_dir)

    very_similar = payload["answerPlan"]["precedent_buckets"]["very_similar"]
    similar = payload["answerPlan"]["precedent_buckets"]["similar"]
    usable = payload["answerPlan"]["precedent_buckets"]["usable"]
    assert very_similar
    assert very_similar[0]["case_number"] == "2020구합12259"
    assert very_similar[0]["supported_claim_ids"] == ["CLAIM-001"]
    assert len(very_similar) + len(similar) + len(usable) >= 2


def test_build_result_payload_prioritizes_same_fact_claim_over_larger_generic_count(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    result_dir = run_dir / "question_selected_manual"
    result_dir.mkdir(parents=True)

    selected_files = [
        {
            "file_id": "file-same",
            "document_title": "특정범죄가중처벌등에관한법률위반(독직폭행)",
            "case_number": "2021노1520",
            "court": "서울고등법원",
            "decision_date": "20220721",
            "case_name": "특정범죄가중처벌등에관한법률위반(독직폭행)",
            "relative_path": "precedents/same.txt",
            "absolute_path": "/tmp/same.txt",
            "extracted_text": "검사가 유심칩을 공기계에 꽂아 인증번호를 받아 카카오톡 계정에 접속하였다.",
        },
        {
            "file_id": "file-generic",
            "document_title": "압수수색 참여권 일반 사건",
            "case_number": "2020도1000",
            "court": "대법원",
            "decision_date": "20200101",
            "case_name": "압수수색",
            "relative_path": "precedents/generic.txt",
            "absolute_path": "/tmp/generic.txt",
            "extracted_text": "전자정보 압수수색은 참여권 보장이 중요하다.",
        },
    ]
    claim_ledger = [
        {
            "claim_id": "CLAIM-SAME",
            "claim_axis": "유심 공기계 인증번호를 이용한 카카오톡 접속",
            "claim_text": "수사기관이 유심칩을 공기계에 장착해 인증번호를 받아 카카오톡 계정에 접속한 사실관계가 직접 등장한다.",
            "same_situation_case_exists": True,
            "supporting_case_count": 1,
            "stance_to_user_goal": "유리",
            "supporting_cases": [
                {"case_number": "2021노1520", "court": "서울고등법원", "decision_date": "20220721", "case_name": "특정범죄가중처벌등에관한법률위반(독직폭행)"}
            ],
            "source_file_id": "file-same",
            "support_spans": [
                {
                    "quote": "유심칩을 별도의 휴대전화 공기계에 꽂고 인증번호를 받아 카카오톡 PC 버전에 접속하였다.",
                    "evidence_id": "same-근거1",
                }
            ],
        },
        {
            "claim_id": "CLAIM-GENERIC",
            "claim_axis": "전자정보 압수수색 참여권 일반론",
            "claim_text": "전자정보 압수수색에서 참여권 보장 여부가 쟁점이 된다.",
            "same_situation_case_exists": True,
            "supporting_case_count": 9,
            "supporting_cases": [
                {"case_number": "2020도1000", "court": "대법원", "decision_date": "20200101", "case_name": "압수수색"}
            ],
            "source_file_id": "file-generic",
        },
    ]
    answer_plan = {
        "body_claim_ids": ["CLAIM-SAME", "CLAIM-GENERIC"],
        "claim_groups": [
            {"label": "전자정보 압수수색 참여권 일반론", "claim_ids": ["CLAIM-GENERIC"]},
            {"label": "유심 공기계 인증번호를 이용한 카카오톡 접속", "claim_ids": ["CLAIM-SAME"]},
        ],
        "precedent_buckets": {"very_similar": [], "similar": [], "usable": [], "other": []},
    }

    (result_dir / "selected_files.json").write_text(json.dumps(selected_files, ensure_ascii=False), encoding="utf-8")
    (run_dir / "selection_meta.json").write_text(
        json.dumps(
            {
                "selection_mode": "beta6_loop_r133_port",
                "query_kind": "kakao_usim",
                "top_debug": [
                    {
                        "canonical_id": "file-same",
                        "verifier": "accept",
                        "score": 193.4,
                        "reasons": ["platform:카카오톡", "usim:유심칩", "actor:검사가", "account_access_bridge:인증번호,공기계"],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (result_dir / "claim_ledger.json").write_text(json.dumps(claim_ledger, ensure_ascii=False), encoding="utf-8")
    (result_dir / "answer_plan.json").write_text(json.dumps(answer_plan, ensure_ascii=False), encoding="utf-8")
    (result_dir / "comparison_summary.json").write_text("{}", encoding="utf-8")
    (result_dir / "final_answer.md").write_text("## 본문\n\n2020도1000 참여권 일반론을 설명합니다.", encoding="utf-8")
    (result_dir / "chunk_outputs.jsonl").write_text("", encoding="utf-8")

    payload = build_result_payload(run_dir)
    answer = payload["answerMarkdown"]

    assert "### 가장 같은 사실관계 판례" in answer
    assert answer.index("2021노1520") < answer.index("2020도1000")
    assert answer.index("선택기가 같은 사실관계로 검증한 판례") < answer.index("2020도1000")
    same_fact_section = answer.split("---", 1)[0]
    assert "질문자에게 유리" not in same_fact_section


def test_beta6_no_longer_rewrites_military_or_kakao_downstream_task() -> None:
    military_question = "군대에서 키는 어캐 관리해야함?"
    kakao_question = "경찰이 피의자 유심 빼서 카톡 로그인하는거 합법임?"
    effective = backend_jobs._effective_question_user_task(
        military_question,
        analysis_mode="beta6",
        selection_meta={"selection_mode": "beta6_loop_r133_port", "query_kind": "military_key"},
    )
    kakao_effective = backend_jobs._effective_question_user_task(
        kakao_question,
        analysis_mode="beta6",
        selection_meta={"selection_mode": "beta6_loop_r133_port", "query_kind": "kakao_usim"},
    )

    assert effective == military_question
    assert kakao_effective == kakao_question


def test_question_writer_prompt_forbids_unsupported_case_overinterpretation() -> None:
    prompt = rag.build_question_answer_prompt(
        user_task="실수로 범죄를 저지르고 내 증거를 인멸했음 이거 죄임?",
        claims=[],
        precedent_buckets={},
        answer_plan={},
        analysis_mode="beta6",
    )

    assert "질문 행위자·대상·법률요건과 직접 맞지 않는 판례" in prompt
    assert "support_spans의 직접 인용문에 없는 법리" in prompt
    assert "형사법 쟁점에서는 구성요건의 주체·객체" in prompt


def test_question_writer_prompt_requires_proposition_verification_for_choice_questions() -> None:
    prompt = rag.build_question_answer_prompt(
        user_task="〈견해〉\n가. A 견해\n\n〈설명〉\nⒶ A 설명\n\n선지:\n가-Ⓐ",
        claims=[],
        precedent_buckets={},
        answer_plan={},
        analysis_mode="beta8",
    )

    assert "선택형·견해-설명형 문제" in prompt
    assert "각 선지는 법률명제" in prompt
    assert "직접 지지·관련이나 직접 아님·충돌·근거 없음" in prompt


def test_question_writer_prompt_keeps_proposition_verification_beta8_only() -> None:
    prompt = rag.build_question_answer_prompt(
        user_task="〈견해〉\n가. A 견해\n\n〈설명〉\nⒶ A 설명\n\n선지:\n가-Ⓐ",
        claims=[],
        precedent_buckets={},
        answer_plan={},
        analysis_mode="beta6",
    )

    assert "선택형·견해-설명형 문제" not in prompt


def test_build_result_payload_prefers_answer_plan_likely_outcome_over_direction_heuristic(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    result_dir = run_dir / "question_selected_manual"
    result_dir.mkdir(parents=True)
    selected_files = [
        {
            "file_id": "file-key",
            "document_title": "해임처분취소",
            "case_number": "85누792",
            "court": "대법원",
            "decision_date": "19851224",
            "case_name": "해임처분취소",
            "relative_path": "precedents/key.txt",
            "absolute_path": "/tmp/key.txt",
            "extracted_text": "무기고 및 탄약고 열쇠관리를 직접하여야 함에도 타인에게 일임하였다.",
        }
    ]
    claim_ledger = [
        {
            "claim_id": "CLAIM-KEY",
            "claim_axis": "열쇠 보관 및 이원화 관리 의무",
            "claim_text": "당직사관은 탄약고 열쇠를 인수하여 보관하고 총기 및 탄약의 무단 반출을 방지할 의무가 있다.",
            "same_situation_case_exists": True,
            "supporting_case_count": 1,
            "stance_to_user_goal": "질문자에게 유리",
            "source_file_id": "file-key",
            "supporting_cases": [
                {"case_number": "85누792", "court": "대법원", "decision_date": "19851224", "case_name": "해임처분취소"}
            ],
        }
    ]
    answer_plan = {
        "likely_outcome": "총기·탄약 열쇠는 이원화 보관, 직접 관리, 인계·점검 절차를 지켜야 한다.",
        "confidence_basis": ["85누792 등 열쇠 관리 판례가 직접 뒷받침한다."],
        "body_claim_ids": ["CLAIM-KEY"],
        "claim_groups": [{"label": "열쇠 보관 및 이원화 관리 의무", "claim_ids": ["CLAIM-KEY"]}],
        "precedent_buckets": {"very_similar": [], "similar": [], "usable": [], "other": []},
    }

    (result_dir / "selected_files.json").write_text(json.dumps(selected_files, ensure_ascii=False), encoding="utf-8")
    (result_dir / "claim_ledger.json").write_text(json.dumps(claim_ledger, ensure_ascii=False), encoding="utf-8")
    (result_dir / "answer_plan.json").write_text(json.dumps(answer_plan, ensure_ascii=False), encoding="utf-8")
    (result_dir / "comparison_summary.json").write_text("{}", encoding="utf-8")
    (result_dir / "final_answer.md").write_text("## 종합 판단\n\n열쇠 관리 본문", encoding="utf-8")
    (result_dir / "chunk_outputs.jsonl").write_text("", encoding="utf-8")

    answer = build_result_payload(run_dir)["answerMarkdown"]

    assert "총기·탄약 열쇠는 이원화 보관" in answer
    assert "질문자에게 유리한 방향" not in answer


def test_strip_user_direction_sentence_handles_truncated_same_fact_summary() -> None:
    assert (
        backend_models._strip_user_direction_sentence("결론적으로 열쇠 관리 판례. 현재 자료상 질문자에게 유리한 방향으로… 선택기 검증")
        == "결론적으로 열쇠 관리 판례. 선택기 검증"
    )


def test_build_result_payload_normalizes_claim_group_labels_and_compact_citations(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    result_dir = run_dir / "question_selected_manual"
    result_dir.mkdir(parents=True)

    selected_files = [
        {
            "file_id": "file-1",
            "document_title": "징계 사건 묶음",
            # Explicit metadata is required — body-text citation inference
            # was producing wrong (mismatched) court/date/case_number when
            # precedent fullText cited OTHER cases first. Test fixtures
            # must mirror real DB rows that store identifiers explicitly.
            "case_number": "2021두48083",
            "court": "대법원",
            "decision_date": "20211216",
            "case_name": "징계처분취소",
            "relative_path": "precedents/a.txt",
            "absolute_path": "/tmp/a.txt",
            "extracted_text": "징계시효를 정한 규정 취지와 기산점.",
        }
    ]
    claim_ledger = [
        {
            "claim_id": "CLAIM-001",
            "claim_axis": "징계시효의 기산점",
            "claim_text": "보고의무를 이행하지 않은 때부터 징계시효가 진행한다.",
            "supporting_case_count": 2,
            "supporting_cases": [
                {"case_number": "2021두48083", "court": "대법원", "decision_date": "20211216", "case_name": "징계처분취소"}
            ],
            "source_file_id": "file-1",
        },
        {
            "claim_id": "CLAIM-002",
            "claim_axis": "징계시효 도과에 따른 무효성",
            "claim_text": "징계시효가 지나면 처분 무효 주장이 강해진다.",
            "supporting_case_count": 1,
            "supporting_cases": [
                {"case_number": "2021두48083", "court": "대법원", "decision_date": "20211216", "case_name": "징계처분취소"}
            ],
            "source_file_id": "file-1",
        },
    ]
    answer_plan = {
        "body_claim_ids": ["CLAIM-001", "CLAIM-002"],
        "claim_groups": [{"label": "징계시효 및 신뢰보호", "claim_ids": ["CLAIM-001", "CLAIM-002"]}],
        "precedent_buckets": {"very_similar": [], "similar": [], "usable": [], "other": []},
    }

    (result_dir / "selected_files.json").write_text(json.dumps(selected_files, ensure_ascii=False), encoding="utf-8")
    (result_dir / "claim_ledger.json").write_text(json.dumps(claim_ledger, ensure_ascii=False), encoding="utf-8")
    (result_dir / "answer_plan.json").write_text(json.dumps(answer_plan, ensure_ascii=False), encoding="utf-8")
    (result_dir / "comparison_summary.json").write_text(json.dumps({}, ensure_ascii=False), encoding="utf-8")
    (result_dir / "final_answer.md").write_text("ok", encoding="utf-8")
    (result_dir / "chunk_outputs.jsonl").write_text("", encoding="utf-8")

    payload = build_result_payload(run_dir)

    assert payload["selectedPrecedents"][0]["citation"] == "2021두48083 판결"
    assert payload["answerPlan"]["claim_groups"] == [{"label": "징계시효", "claim_ids": ["CLAIM-001", "CLAIM-002"]}]


def test_document_presets_point_to_local_anonymized_files() -> None:
    manager = LawkeyJobManager()

    presets = manager.list_document_presets()
    labels = [item["label"] for item in presets]

    assert presets
    assert all(str(item["path"]).startswith(str(PROJECT_ROOT / "data" / "presets")) for item in presets)
    assert all("박형빈" not in str(item["path"]) for item in presets)
    assert labels.count("변호인의견서 프리셋") == 1
    assert labels.count("고소장 프리셋") == 1
    assert "변호인의견서 예시 1" not in labels
    assert "고소장 양식 예시" not in labels
    assert "고소장 예시" not in labels
    defense = next(item for item in presets if item["id"] == "defense_opinion")
    assert len(defense["paths"]) == 2
    assert all(str(path).startswith(str(PROJECT_ROOT / "data" / "presets")) for path in defense["paths"])
    complaint = next(item for item in presets if item["id"] == "complaint")
    assert len(complaint["paths"]) >= 4
    assert "complaint_template" in complaint["aliases"]
    assert "complaint_example" in complaint["aliases"]
    assert any("official_police_simple_complaint" in str(path) for path in complaint["paths"])
    assert any("official_police_simple_complaint_attachment" in str(path) for path in complaint["paths"])


def test_document_preset_inference_keeps_complaint_requests_out_of_defense_samples(tmp_path: Path) -> None:
    manager = LawkeyJobManager(runs_root=tmp_path / "runs")

    assert manager._infer_document_preset_id("고소장 작성해줘", "") == "complaint"
    assert manager._infer_document_preset_id("변호인의견서 초안", "") == "defense_opinion"
    assert manager._infer_document_preset_id("고소장 작성해줘", "defense_opinion") == "defense_opinion"

    complaint_paths = manager._resolve_sample_paths(
        document_preset_id="",
        sample_path="",
        user_task="모욕죄 고소장 작성해줘",
    )

    assert complaint_paths
    assert all("defense_opinion" not in path.name for path in complaint_paths)
    assert any("complaint" in path.name for path in complaint_paths)


def test_complaint_final_prompt_uses_complaint_format_not_defense_opinion() -> None:
    prompt = rag.build_final_opinion_prompt(
        user_task=(
            "모욕죄 고소장 작성해줘\n\n"
            "[추가질문 문서화 맥락]\n"
            "[사용자]\n모욕죄 성립 여부를 분석해줘\n"
            "[기존 Lawkey 답변]\n공연성과 특정성이 핵심입니다.\n"
            "[사용자]\n2026. 4. 1. 단체 채팅방에서 피해자 A와 피고소인 B로 표시해줘"
        ),
        sample_texts=["고    소    장\n1. 고소인", "별지 : 고소인 명단"],
        claims=[],
        section_packets={},
    )

    assert "문서 유형: 고소장" in prompt
    assert "고소장으로 작성할 것" in prompt
    assert "변호인 의견서 샘플" not in prompt
    assert "이번 사건에 대한 변호인 의견서 텍스트를 작성하라" not in prompt
    assert "그대로 베끼지 말 것" in prompt
    assert "피해자 A와 피고소인 B" in prompt


def test_document_writer_context_is_separate_from_retrieval_task(tmp_path: Path) -> None:
    manager = LawkeyJobManager(runs_root=tmp_path / "runs")
    job = SimpleNamespace(
        user_task="모욕죄 고소장 판례 검색",
        document_context=(
            "[추가질문 문서화 맥락]\n"
            "[사용자]\n모욕죄 성립 여부를 분석해줘\n"
            "[기존 Lawkey 답변]\n공연성과 특정성이 핵심입니다.\n"
            "[사용자]\n2026. 4. 1. 단체 채팅방에서 피해자 A와 피고소인 B로 표시해줘"
        ),
    )

    assert manager._infer_document_preset_id(job.user_task, "") == "complaint"
    writer_task = manager._build_document_writer_task(job)  # type: ignore[arg-type]

    assert writer_task.startswith("모욕죄 고소장 판례 검색\n\n[추가질문 문서화 맥락]")
    assert "공연성과 특정성이 핵심입니다." in writer_task
    assert "피해자 A와 피고소인 B" in writer_task


def test_backend_defaults_use_gemma4_models() -> None:
    assert DEFAULT_SELECT_MODEL == "gemma-4-26b-a4b-it"
    assert DEFAULT_ANALYZE_MODEL == "gemma-4-26b-a4b-it"
    assert DEFAULT_DRAFT_MODEL == "gemma-4-26b-a4b-it"


def test_backend_defaults_use_parallel_gemma_runtime_limits() -> None:
    assert DEFAULT_WORKER_COUNT == 10
    assert DEFAULT_KEY_MIN_GAP_MS == 2000
    assert DEFAULT_KEY_RPM_LIMIT == 20
    assert DEFAULT_KEY_TPM_LIMIT == 100000
    assert DEFAULT_GLOBAL_MAX_INFLIGHT == 10


def test_backend_config_allows_aws_deploy_path_overrides(monkeypatch) -> None:
    from backend import config as config_module

    env_names = [
        "LAWKEY_WORKSPACE_ROOT",
        "LAWKEY_WORKSPACE_SCRIPTS",
        "LAWKEY_LEGAL_RAG_SCRIPT",
        "LAWKEY_PRECEDENT_DB_PATH",
        "LAWKEY_RUNS_ROOT",
        "LAWKEY_SELECT_MODEL",
        "LAWKEY_ANALYZE_MODEL",
        "LAWKEY_DRAFT_MODEL",
        "LAWKEY_TOP_K",
        "LAWKEY_WORKER_COUNT",
        "LAWKEY_RETRY_BACKOFF_SECONDS",
    ]
    monkeypatch.setenv("LAWKEY_WORKSPACE_ROOT", "/srv/lawkey/work16")
    monkeypatch.setenv("LAWKEY_WORKSPACE_SCRIPTS", "/srv/lawkey/work16/scripts")
    monkeypatch.setenv("LAWKEY_LEGAL_RAG_SCRIPT", "/srv/lawkey/work16/scripts/legal_evidence_rag.py")
    monkeypatch.setenv(
        "LAWKEY_PRECEDENT_DB_PATH",
        "/srv/lawkey/work16/저장파일/unified_precedent_db_2026-04-10_run3/precedents.sqlite3",
    )
    monkeypatch.setenv("LAWKEY_RUNS_ROOT", "/srv/lawkey/runs")
    monkeypatch.setenv("LAWKEY_SELECT_MODEL", "gemma-test-select")
    monkeypatch.setenv("LAWKEY_ANALYZE_MODEL", "gemma-test-analyze")
    monkeypatch.setenv("LAWKEY_DRAFT_MODEL", "gemma-test-draft")
    monkeypatch.setenv("LAWKEY_TOP_K", "25")
    monkeypatch.setenv("LAWKEY_WORKER_COUNT", "3")
    monkeypatch.setenv("LAWKEY_RETRY_BACKOFF_SECONDS", "1,2,5")

    reloaded = importlib.reload(config_module)
    try:
        assert reloaded.WORKSPACE_ROOT == Path("/srv/lawkey/work16")
        assert reloaded.WORKSPACE_SCRIPTS == Path("/srv/lawkey/work16/scripts")
        assert reloaded.LEGAL_RAG_SCRIPT == Path("/srv/lawkey/work16/scripts/legal_evidence_rag.py")
        assert reloaded.PRECEDENT_DB_PATH == Path(
            "/srv/lawkey/work16/저장파일/unified_precedent_db_2026-04-10_run3/precedents.sqlite3"
        )
        assert reloaded.RUNS_ROOT == Path("/srv/lawkey/runs")
        assert reloaded.DEFAULT_SELECT_MODEL == "gemma-test-select"
        assert reloaded.DEFAULT_ANALYZE_MODEL == "gemma-test-analyze"
        assert reloaded.DEFAULT_DRAFT_MODEL == "gemma-test-draft"
        assert reloaded.DEFAULT_TOP_K == 25
        assert reloaded.DEFAULT_WORKER_COUNT == 3
        assert reloaded.DEFAULT_RETRY_BACKOFF_SECONDS == (1, 2, 5)
    finally:
        for name in env_names:
            monkeypatch.delenv(name, raising=False)
        importlib.reload(config_module)


def test_build_result_payload_exposes_document_export_artifacts(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    result_dir = run_dir / "question_selected_manual"
    exports_dir = result_dir / "exports"
    previews_dir = exports_dir / "preview"
    previews_dir.mkdir(parents=True)
    result_dir.mkdir(parents=True, exist_ok=True)

    (result_dir / "selected_files.json").write_text("[]", encoding="utf-8")
    (result_dir / "claim_ledger.json").write_text("[]", encoding="utf-8")
    (result_dir / "comparison_summary.json").write_text("{}", encoding="utf-8")
    (result_dir / "final_document.md").write_text("# 문서", encoding="utf-8")
    (result_dir / "chunk_outputs.jsonl").write_text("", encoding="utf-8")

    markdown_path = exports_dir / "final_document.md"
    hwpx_path = exports_dir / "final_document.hwpx"
    pdf_path = exports_dir / "final_document.pdf"
    preview_path = previews_dir / "page-001.png"
    markdown_path.write_text("# 문서", encoding="utf-8")
    hwpx_path.write_bytes(b"hwpx")
    pdf_path.write_bytes(b"%PDF-1.4")
    preview_path.write_bytes(b"png")

    payload = build_result_payload(run_dir)

    assert payload["outputPaths"]["markdownPath"].endswith("final_document.md")
    assert payload["outputPaths"]["hwpxPath"].endswith("final_document.hwpx")
    assert payload["outputPaths"]["pdfPath"].endswith("final_document.pdf")
    assert payload["outputPaths"]["previewImagePaths"][0].endswith("page-001.png")


def test_build_result_payload_hides_question_export_artifacts_even_if_legacy_files_exist(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    result_dir = run_dir / "question_selected_manual"
    exports_dir = result_dir / "exports"
    exports_dir.mkdir(parents=True)

    (result_dir / "selected_files.json").write_text("[]", encoding="utf-8")
    (result_dir / "claim_ledger.json").write_text("[]", encoding="utf-8")
    (result_dir / "comparison_summary.json").write_text("{}", encoding="utf-8")
    (result_dir / "final_answer.md").write_text("# 답변", encoding="utf-8")
    (result_dir / "chunk_outputs.jsonl").write_text("", encoding="utf-8")
    (exports_dir / "final_answer.md").write_text("# 답변", encoding="utf-8")
    (exports_dir / "final_answer.hwpx").write_bytes(b"hwpx")
    (exports_dir / "final_answer.pdf").write_bytes(b"%PDF-1.4")

    payload = build_result_payload(run_dir, mode="question")

    assert payload["answerMarkdown"]
    assert payload["outputPaths"]["markdownPath"] == ""
    assert payload["outputPaths"]["hwpxPath"] == ""
    assert payload["outputPaths"]["pdfPath"] == ""


def test_write_export_outputs_skips_question_jobs(tmp_path: Path, monkeypatch) -> None:
    manager = LawkeyJobManager(runs_root=tmp_path / "runs")
    run_dir = tmp_path / "runs" / "job-question"
    variant_dir = run_dir / "question_selected_manual"
    variant_dir.mkdir(parents=True)
    (variant_dir / "final_answer.md").write_text("# 답변", encoding="utf-8")
    job = type(manager)._require_job.__globals__["JobRecord"](
        job_id="job-question",
        mode="question",
        user_task="질문",
        run_dir=run_dir,
        created_at=1.0,
        status_path=run_dir / "_runtime" / "status.json",
        selected_manifest_path=run_dir / "selected_precedents.json",
        chunk_plan=[],
        runtime_control_path=run_dir / "_runtime" / "control.json",
    )

    def _fail_export(*_args, **_kwargs):
        raise AssertionError("question mode must not build document/export artifacts")

    monkeypatch.setattr("backend.jobs.build_export_artifacts", _fail_export)

    manager._write_export_outputs(job)

    assert not (variant_dir / "exports").exists()


def test_write_export_outputs_sanitizes_document_markdown(tmp_path: Path, monkeypatch) -> None:
    manager = LawkeyJobManager(runs_root=tmp_path / "runs")
    run_dir = tmp_path / "runs" / "job-document"
    variant_dir = run_dir / "question_selected_manual"
    variant_dir.mkdir(parents=True)
    (variant_dir / "final_document.md").write_text(
        "\n".join(
            [
                'Legal Opinion (변호인 의견서) - though the user\'s task is about a "Notice of Demand".',
                "    *   *Wait, let's re-read:* The user wants me to write a legal opinion.",
                "    *   *Final Review of the Ledger usage:*",
                "        - Claim 1 (6%/12%) - Included.",
                "    *   *Drafting the final response...* (Proceeding to generate the Korean text).법률 검토 의견서",
                "",
                "사    건  대여금 반환 청구를 위한 법리 검토",
            ]
        ),
        encoding="utf-8",
    )
    job = type(manager)._require_job.__globals__["JobRecord"](
        job_id="job-document",
        mode="document",
        user_task="문서",
        run_dir=run_dir,
        created_at=1.0,
        status_path=run_dir / "_runtime" / "status.json",
        selected_manifest_path=run_dir / "selected_precedents.json",
        chunk_plan=[],
        runtime_control_path=run_dir / "_runtime" / "control.json",
    )
    captured: dict[str, str] = {}

    def _capture_export(markdown: str, **_kwargs):
        captured["markdown"] = markdown
        return {"markdown_path": str(variant_dir / "exports" / "final_document.md")}

    monkeypatch.setattr("backend.jobs.build_export_artifacts", _capture_export)

    manager._write_export_outputs(job)

    assert captured["markdown"].startswith("법률 검토 의견서")
    assert "Wait, let's re-read" not in captured["markdown"]
    assert "Final Review of the Ledger usage" not in captured["markdown"]
    assert (variant_dir / "final_document.md").read_text(encoding="utf-8").startswith("법률 검토 의견서")


def test_sanitize_search_query_removes_fts_breaking_punctuation() -> None:
    sanitized = sanitize_search_query("징계처분, 무효(감봉) 징계시효·이중징계")

    assert sanitized == "징계처분 무효 감봉 징계시효 이중징계"


def test_build_search_queries_falls_back_when_keyword_generator_fails() -> None:
    queries = build_search_queries(
        "징계처분 무효 주장",
        keyword_count=10,
        select_model="unused",
        keyword_generator=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    assert queries[0] == "징계처분 무효 주장"
    assert "징계처분" in queries
    assert "무효" in queries
    assert "주장" in queries


def test_rerank_rows_penalizes_irrelevant_retrial_noise_for_discipline_queries() -> None:
    ranked = [
        {
            "canonical_id": "noise",
            "source_dataset": "02_lbox_open",
            "title": "31327",
            "case_name": "0",
            "case_type": "",
            "court": "대법원",
            "case_number": "99다40319",
            "decision_date": "1999-11-26",
            "keyword_hit_count": 2,
            "best_score": -10.0,
        },
        {
            "canonical_id": "discipline",
            "source_dataset": "01_joonhok_precedents",
            "title": "징계처분취소",
            "case_name": "징계처분취소",
            "case_type": "행정",
            "court": "서울행정법원",
            "case_number": "2020구합12259",
            "decision_date": "2021-06-17",
            "keyword_hit_count": 1,
            "best_score": -4.0,
        },
    ]

    reranked = _rerank_ranked_rows(ranked, user_task="징계처분 무효 주장에 쓸 수 있는 판례를 찾아줘", limit=10)

    assert reranked[0]["canonical_id"] == "discipline"


def test_job_manager_recovers_existing_job_from_disk(tmp_path: Path) -> None:
    runs_root = tmp_path / "runs"
    job_dir = runs_root / "job-existing"
    runtime_dir = job_dir / "_runtime"
    runtime_dir.mkdir(parents=True)
    runtime_dir.joinpath("job_meta.json").write_text(
        json.dumps(
            {
                "job_id": "job-existing",
                "mode": "document",
                "user_task": "징계 처분에 대한 의견서를 작성해줘",
                "created_at": 1234.5,
                "document_preset_id": "defense-opinion",
                "sample_path": "/tmp/sample.md",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    runtime_dir.joinpath("status.json").write_text(
        json.dumps(
            {
                "phase": "variant",
                "state": "analyzing_chunks",
                "selected_file_count": 1,
                "completed_chunks": 2,
                "chunk_count": 4,
                "elapsed_seconds": 20,
                "error": "temporary failure",
                "finished_at": 1250.5,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    job_dir.joinpath("selected_precedents.json").write_text(
        json.dumps(
            [
                {
                    "file_id": "file-1",
                    "relative_path": "/tmp/a.txt",
                    "absolute_path": "/tmp/a.txt",
                    "document_title": "징계처분 취소",
                    "doc_type": "txt",
                    "source_group": "structured_precedent",
                    "token_count": 10,
                    "anchor_text": "징계권자가 이미 비위를 인지하였다.",
                    "extracted_text": "징계권자가 이미 비위를 인지하였다.",
                    "candidate_boundaries": [],
                    "is_direct_evidence": False,
                    "is_format_sample": False,
                    "content_hash": "abc",
                    "duplicate_paths": [],
                    "case_number": "2020구합12259",
                    "court": "서울행정법원",
                    "decision_date": "2021-06-17",
                    "case_name": "감봉처분무효확인",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    manager = LawkeyJobManager(runs_root=runs_root)
    status = manager.get_job_status("job-existing")

    assert status["jobId"] == "job-existing"
    assert status["mode"] == "document"
    assert status["error"] == "temporary failure"
    assert status["selectedPrecedentCount"] == 1
    assert status["completedChunks"] == 2
    assert status["currentCaseNumber"] == "2020구합12259"


def test_job_manager_recovered_unfinished_job_is_marked_interrupted(tmp_path: Path) -> None:
    runs_root = tmp_path / "runs"
    job_dir = runs_root / "job-stale"
    runtime_dir = job_dir / "_runtime"
    runtime_dir.mkdir(parents=True)
    runtime_dir.joinpath("job_meta.json").write_text(
        json.dumps(
            {
                "job_id": "job-stale",
                "mode": "question",
                "user_task": "질문",
                "created_at": 1234.5,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    runtime_dir.joinpath("status.json").write_text(
        json.dumps(
            {
                "phase": "variant",
                "state": "analyzing_chunks",
                "selected_file_count": 1,
                "completed_chunks": 1,
                "chunk_count": 4,
                "elapsed_seconds": 20,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    manager = LawkeyJobManager(runs_root=runs_root)
    status = manager.get_job_status("job-stale")

    # Recovery now silently re-queues unfinished jobs so the worker can resume
    # from existing artifacts; no user-visible "interrupted" error.
    assert status["state"] == "queued"
    assert status["finishedAt"] is None
    assert status["error"] == ""
    persisted = json.loads(runtime_dir.joinpath("status.json").read_text(encoding="utf-8"))
    assert persisted["state"] == "queued"
    assert persisted["error"] == ""


def test_job_manager_promotes_late_variant_completion_after_recovery(tmp_path: Path) -> None:
    runs_root = tmp_path / "runs"
    job_dir = runs_root / "job-late-complete"
    runtime_dir = job_dir / "_runtime"
    runtime_dir.mkdir(parents=True)
    runtime_dir.joinpath("job_meta.json").write_text(
        json.dumps(
            {
                "job_id": "job-late-complete",
                "mode": "question",
                "user_task": "질문",
                "created_at": 1234.5,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    runtime_dir.joinpath("status.json").write_text(
        json.dumps(
            {
                "phase": "variant",
                "state": "analyzing_chunks",
                "selected_file_count": 1,
                "completed_chunks": 1,
                "chunk_count": 4,
                "elapsed_seconds": 20,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    manager = LawkeyJobManager(runs_root=runs_root)
    requeued = manager.get_job_status("job-late-complete")
    assert requeued["state"] == "queued"
    assert requeued["error"] == ""

    variant_dir = job_dir / "question_selected_manual"
    variant_dir.mkdir(parents=True)
    final_answer = variant_dir / "final_answer.md"
    final_answer.write_text("## 종합 판단\n최종 답변입니다.", encoding="utf-8")
    runtime_dir.joinpath("status.json").write_text(
        json.dumps(
            {
                "phase": "done",
                "state": "question_variant_completed",
                "selected_file_count": 1,
                "completed_chunks": 4,
                "chunk_count": 4,
                "final_draft_path": str(final_answer),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    completed = manager.get_job_status("job-late-complete")

    assert completed["state"] == "completed"
    assert completed["error"] == ""
    assert completed["finishedAt"] is not None
    assert completed["completedChunks"] == 4
    persisted = json.loads(runtime_dir.joinpath("status.json").read_text(encoding="utf-8"))
    assert persisted["state"] == "completed"
    assert persisted["error"] == ""


def test_document_job_does_not_promote_question_variant_as_completed(tmp_path: Path) -> None:
    runs_root = tmp_path / "runs"
    job_dir = runs_root / "job-document-still-writing"
    runtime_dir = job_dir / "_runtime"
    variant_dir = job_dir / "question_selected_manual"
    runtime_dir.mkdir(parents=True)
    variant_dir.mkdir(parents=True)
    final_answer = variant_dir / "final_answer.md"
    final_answer.write_text("## 종합 판단\n중간 판례 분석입니다.", encoding="utf-8")
    runtime_dir.joinpath("job_meta.json").write_text(
        json.dumps(
            {
                "job_id": "job-document-still-writing",
                "mode": "document",
                "user_task": "고소장 검색",
                "created_at": 1234.5,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    runtime_dir.joinpath("status.json").write_text(
        json.dumps(
            {
                "phase": "done",
                "state": "question_variant_completed",
                "selected_file_count": 1,
                "completed_chunks": 4,
                "chunk_count": 4,
                "final_draft_path": str(final_answer),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    manager = LawkeyJobManager(runs_root=runs_root)
    status = manager.get_job_status("job-document-still-writing")

    assert status["state"] != "completed"
    persisted = json.loads(runtime_dir.joinpath("status.json").read_text(encoding="utf-8"))
    assert persisted["state"] != "completed"
    assert persisted["final_draft_path"].endswith("final_answer.md")


def test_job_manager_syncs_finished_jobs_from_runtime_status(tmp_path: Path) -> None:
    runs_root = tmp_path / "runs"
    job_dir = runs_root / "job-done"
    runtime_dir = job_dir / "_runtime"
    runtime_dir.mkdir(parents=True)
    runtime_dir.joinpath("job_meta.json").write_text(
        json.dumps(
            {
                "job_id": "job-done",
                "mode": "question",
                "user_task": "질문",
                "created_at": 1234.5,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    runtime_dir.joinpath("status.json").write_text(
        json.dumps(
            {
                "phase": "done",
                "state": "completed",
                "selected_file_count": 1,
                "completed_chunks": 3,
                "chunk_count": 3,
                "elapsed_seconds": 33,
                "finished_at": 2345.6,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    manager = LawkeyJobManager(runs_root=runs_root)
    manager.get_job_status("job-done")
    rows = manager.list_jobs()

    assert rows[0]["state"] == "completed"
    assert rows[0]["finishedAt"] == 2345.6


def test_job_manager_retries_transient_question_failure_and_reuses_selection(tmp_path: Path, monkeypatch) -> None:
    runs_root = tmp_path / "runs"
    manager = LawkeyJobManager(runs_root=runs_root)
    run_dir = runs_root / "job-retry"
    job = manager._recover_job("job-retry")
    if job is None:
        runtime_dir = run_dir / "_runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        job = manager._jobs.setdefault(
            "job-retry",
            type(manager)._require_job.__globals__["JobRecord"](
                job_id="job-retry",
                mode="question",
                user_task="질문",
                run_dir=run_dir,
                created_at=1.0,
                status_path=run_dir / "_runtime" / "status.json",
                selected_manifest_path=run_dir / "selected_precedents.json",
                chunk_plan=[],
                runtime_control_path=run_dir / "_runtime" / "control.json",
            ),
        )

    select_calls = {"count": 0}
    subprocess_calls = {"count": 0}

    def fake_select_top_precedents(*_args, **_kwargs):
        select_calls["count"] += 1
        return ([{"file_id": "file-1", "case_number": "2020구합1"}], {"keywords": ["질문"]})

    def fake_load_selected_question_records(_path):
        return [object()]

    def fake_build_question_chunks_for_records(*_args, **_kwargs):
        return [
            SimpleNamespace(
                chunk_id="chunk-1",
                file_id="file-1",
                case_number="2020구합1",
                text="본문 앞부분",
                source_segments=[{"case_number": "2020구합1", "excerpt": "본문 앞부분"}],
            )
        ]

    def fake_run_question_subprocess(inner_job):
        subprocess_calls["count"] += 1
        if subprocess_calls["count"] == 1:
            raise RuntimeError("question subprocess failed with exit code 1; tail=Read timed out")
        variant_dir = inner_job.run_dir / "question_selected_manual"
        variant_dir.mkdir(parents=True, exist_ok=True)
        (variant_dir / "final_answer.md").write_text("# 답변", encoding="utf-8")

    monkeypatch.setattr("backend.jobs.select_top_precedents", fake_select_top_precedents)
    monkeypatch.setattr("backend.jobs.rag.load_selected_question_records", fake_load_selected_question_records)
    monkeypatch.setattr("backend.jobs.rag.build_question_chunks_for_records", fake_build_question_chunks_for_records)
    monkeypatch.setattr(manager, "_run_question_subprocess", fake_run_question_subprocess)
    monkeypatch.setattr(manager, "_write_export_outputs", lambda _job: None)
    monkeypatch.setattr("backend.jobs.time.sleep", lambda _seconds: None)

    manager._run_job(job)

    status = json.loads(job.status_path.read_text(encoding="utf-8"))
    assert status["state"] == "completed"
    assert status["attempt_count"] == 2
    assert select_calls["count"] == 1
    assert subprocess_calls["count"] == 2


def test_beta6_chunk_plan_uses_large_chunks_without_dropping_records(tmp_path: Path, monkeypatch) -> None:
    runs_root = tmp_path / "runs"
    manager = LawkeyJobManager(runs_root=runs_root)
    run_dir = runs_root / "job-beta6-chunks"
    runtime_dir = run_dir / "_runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    selected_path = run_dir / "selected_precedents.json"
    selected_path.write_text(json.dumps([{"file_id": "file-1"}]), encoding="utf-8")
    job = type(manager)._require_job.__globals__["JobRecord"](
        job_id="job-beta6-chunks",
        mode="question",
        user_task="질문",
        analysis_mode="beta6",
        run_dir=run_dir,
        created_at=1.0,
        status_path=runtime_dir / "status.json",
        selected_manifest_path=selected_path,
        chunk_plan=[],
        runtime_control_path=runtime_dir / "control.json",
    )
    seen: dict[str, object] = {}

    records = [object(), object()]

    def fake_build_question_chunks_for_records(input_records, **kwargs):
        seen["record_count"] = len(input_records)
        seen["max_tokens"] = kwargs.get("max_tokens")
        return [
            SimpleNamespace(
                chunk_id="chunk-1",
                file_id="file-1",
                case_number="",
                text="본문",
                source_segments=[{"excerpt": "본문"}],
            )
        ]

    monkeypatch.setattr("backend.jobs.rag.load_selected_question_records", lambda _path: records)
    monkeypatch.setattr("backend.jobs.rag.build_question_chunks_for_records", fake_build_question_chunks_for_records)

    manager._ensure_chunk_plan(job)

    assert seen["record_count"] == 2
    assert int(seen["max_tokens"]) == 100_000
    assert job.chunk_plan[0]["chunk_id"] == "chunk-1"


def test_beta6_question_subprocess_skips_forced_coverage_patch(tmp_path: Path, monkeypatch) -> None:
    runs_root = tmp_path / "runs"
    manager = LawkeyJobManager(runs_root=runs_root)
    run_dir = runs_root / "job-beta6-command"
    runtime_dir = run_dir / "_runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    selected_path = run_dir / "selected_precedents.json"
    selected_path.write_text("[]", encoding="utf-8")
    (run_dir / "selection_meta.json").write_text(json.dumps({"query_kind": "generic"}), encoding="utf-8")
    job = type(manager)._require_job.__globals__["JobRecord"](
        job_id="job-beta6-command",
        mode="question",
        user_task="질문",
        analysis_mode="beta6",
        run_dir=run_dir,
        created_at=1.0,
        status_path=runtime_dir / "status.json",
        selected_manifest_path=selected_path,
        chunk_plan=[],
        runtime_control_path=runtime_dir / "control.json",
    )
    captured: dict[str, list[str]] = {}

    class FakeProcess:
        pid = 123

        def wait(self) -> int:
            return 0

    def fake_popen(command, **_kwargs):
        captured["command"] = list(command)
        return FakeProcess()

    monkeypatch.setattr("backend.jobs.subprocess.Popen", fake_popen)

    manager._run_question_subprocess(job)

    command = captured["command"]
    assert "--analysis-mode" in command
    assert command[command.index("--analysis-mode") + 1] == "beta6"
    assert "--question-chunk-tokens" in command
    assert command[command.index("--question-chunk-tokens") + 1] == "100000"
    assert "--skip-coverage-patch" in command


def test_beta8_question_subprocess_uses_proposition_guard_runtime_shape(tmp_path: Path, monkeypatch) -> None:
    runs_root = tmp_path / "runs"
    manager = LawkeyJobManager(runs_root=runs_root)
    run_dir = runs_root / "job-beta8-command"
    runtime_dir = run_dir / "_runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    selected_path = run_dir / "selected_precedents.json"
    selected_path.write_text("[]", encoding="utf-8")
    (run_dir / "selection_meta.json").write_text(json.dumps({"query_kind": "generic"}), encoding="utf-8")
    job = type(manager)._require_job.__globals__["JobRecord"](
        job_id="job-beta8-command",
        mode="question",
        user_task="견해 설명 연결 문제",
        analysis_mode="beta8",
        run_dir=run_dir,
        created_at=1.0,
        status_path=runtime_dir / "status.json",
        selected_manifest_path=selected_path,
        chunk_plan=[],
        runtime_control_path=runtime_dir / "control.json",
    )
    captured: dict[str, list[str]] = {}

    class FakeProcess:
        pid = 123

        def wait(self) -> int:
            return 0

    def fake_popen(command, **_kwargs):
        captured["command"] = list(command)
        return FakeProcess()

    monkeypatch.setattr("backend.jobs.subprocess.Popen", fake_popen)

    manager._run_question_subprocess(job)

    command = captured["command"]
    assert command[command.index("--analysis-mode") + 1] == "beta8"
    assert command[command.index("--question-chunk-tokens") + 1] == "100000"
    assert "--skip-coverage-patch" in command


def test_job_manager_does_not_retry_non_transient_failure(tmp_path: Path, monkeypatch) -> None:
    runs_root = tmp_path / "runs"
    manager = LawkeyJobManager(runs_root=runs_root)
    run_dir = runs_root / "job-fail"
    runtime_dir = run_dir / "_runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    job = type(manager)._require_job.__globals__["JobRecord"](
        job_id="job-fail",
        mode="question",
        user_task="질문",
        run_dir=run_dir,
        created_at=1.0,
        status_path=run_dir / "_runtime" / "status.json",
        selected_manifest_path=run_dir / "selected_precedents.json",
        chunk_plan=[],
        runtime_control_path=run_dir / "_runtime" / "control.json",
    )

    subprocess_calls = {"count": 0}

    monkeypatch.setattr("backend.jobs.select_top_precedents", lambda *_args, **_kwargs: ([{"file_id": "file-1"}], {}))
    monkeypatch.setattr("backend.jobs.rag.load_selected_question_records", lambda _path: [object()])
    monkeypatch.setattr(
        "backend.jobs.rag.build_question_chunks_for_records",
        lambda *_args, **_kwargs: [SimpleNamespace(chunk_id="chunk-1", file_id="file-1", case_number="", text="x", source_segments=[{}])],
    )

    def fake_run_question_subprocess(_job):
        subprocess_calls["count"] += 1
        raise RuntimeError("missing claim ledger")

    monkeypatch.setattr(manager, "_run_question_subprocess", fake_run_question_subprocess)
    monkeypatch.setattr(manager, "_write_export_outputs", lambda _job: None)

    manager._run_job(job)

    status = json.loads(job.status_path.read_text(encoding="utf-8"))
    assert status["state"] == "failed"
    assert subprocess_calls["count"] == 1


def test_create_job_keeps_older_active_jobs_and_queues_new_one(tmp_path: Path, monkeypatch) -> None:
    runs_root = tmp_path / "runs"
    manager = LawkeyJobManager(runs_root=runs_root)

    old_run_dir = runs_root / "job-old"
    (old_run_dir / "_runtime").mkdir(parents=True, exist_ok=True)
    old_job = type(manager)._require_job.__globals__["JobRecord"](
        job_id="job-old",
        mode="question",
        user_task="older",
        run_dir=old_run_dir,
        created_at=1.0,
        status_path=old_run_dir / "_runtime" / "status.json",
        selected_manifest_path=old_run_dir / "selected_precedents.json",
        chunk_plan=[],
        selected_count=12,
        process_pid=None,
        runtime_control_path=old_run_dir / "_runtime" / "control.json",
    )
    manager._jobs[old_job.job_id] = old_job

    class FakeThread:
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs

        def start(self) -> None:
            return None

    monkeypatch.setattr("backend.jobs.threading.Thread", FakeThread)

    created = manager.create_job({"mode": "question", "userTask": "newer"})

    assert created["jobId"] != "job-old"
    assert old_job.cancel_requested is False
    assert old_job.cancel_reason == ""
    assert created["jobId"] in manager._jobs


def test_cancel_job_marks_cancelled_and_terminates_process_group(tmp_path: Path, monkeypatch) -> None:
    runs_root = tmp_path / "runs"
    manager = LawkeyJobManager(runs_root=runs_root)
    run_dir = runs_root / "job-cancel"
    (run_dir / "_runtime").mkdir(parents=True, exist_ok=True)
    job = type(manager)._require_job.__globals__["JobRecord"](
        job_id="job-cancel",
        mode="question",
        user_task="cancel me",
        run_dir=run_dir,
        created_at=1.0,
        status_path=run_dir / "_runtime" / "status.json",
        selected_manifest_path=run_dir / "selected_precedents.json",
        chunk_plan=[{"chunk_id": "chunk-1"}],
        selected_count=12,
        process_pid=4321,
        runtime_control_path=run_dir / "_runtime" / "control.json",
    )
    manager._jobs[job.job_id] = job
    job.status_path.write_text(
        json.dumps(
            {
                "phase": "variant",
                "state": "analyzing_chunks",
                "completed_chunks": 1,
                "chunk_count": 4,
                "selected_file_count": 12,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    killed: list[tuple[int, int]] = []
    monkeypatch.setattr("backend.jobs.os.getpgid", lambda pid: pid)
    monkeypatch.setattr("backend.jobs.os.killpg", lambda pgid, sig: killed.append((pgid, sig)))

    result = manager.cancel_job("job-cancel", {"reason": "user_cancelled"})

    assert result["state"] == "cancelled"
    assert job.cancel_requested is True
    assert job.cancel_reason == "사용자가 요청을 취소했습니다."
    assert killed == [(4321, signal.SIGTERM)]
    status = json.loads(job.status_path.read_text(encoding="utf-8"))
    assert status["state"] == "cancelled"
    assert status["completed_chunks"] == 1
    control = json.loads(job.runtime_control_path.read_text(encoding="utf-8"))
    assert control["cancel_requested"] is True


def test_job_manager_filters_server_history_by_browser_client_id(tmp_path: Path, monkeypatch) -> None:
    runs_root = tmp_path / "runs"
    manager = LawkeyJobManager(runs_root=runs_root)

    class FakeThread:
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs

        def start(self) -> None:
            return None

    monkeypatch.setattr("backend.jobs.threading.Thread", FakeThread)

    first = manager.create_job({"mode": "question", "userTask": "첫 사용자 질문", "clientId": "browser-a"})
    second = manager.create_job({"mode": "question", "userTask": "둘째 사용자 질문", "clientId": "browser-b"})

    browser_a_jobs = manager.list_jobs(client_id="browser-a")
    browser_b_jobs = manager.list_jobs(client_id="browser-b")
    all_jobs = manager.list_jobs()

    assert [item["jobId"] for item in browser_a_jobs] == [first["jobId"]]
    assert [item["jobId"] for item in browser_b_jobs] == [second["jobId"]]
    assert {item["jobId"] for item in all_jobs} == {first["jobId"], second["jobId"]}


def test_get_job_status_reports_queue_position(tmp_path: Path) -> None:
    runs_root = tmp_path / "runs"
    manager = LawkeyJobManager(runs_root=runs_root)

    def make_job(job_id: str, created_at: float, finished_at: float | None = None) -> Any:
        run_dir = runs_root / job_id
        (run_dir / "_runtime").mkdir(parents=True, exist_ok=True)
        job = type(manager)._require_job.__globals__["JobRecord"](
            job_id=job_id,
            mode="question",
            user_task=job_id,
            run_dir=run_dir,
            created_at=created_at,
            status_path=run_dir / "_runtime" / "status.json",
            selected_manifest_path=run_dir / "selected_precedents.json",
            chunk_plan=[],
            runtime_control_path=run_dir / "_runtime" / "control.json",
            finished_at=finished_at,
        )
        job.status_path.write_text(json.dumps({"phase": "queue", "state": "queued", "selected_file_count": 0}), encoding="utf-8")
        return job

    first = make_job("job-1", 1.0, None)
    second = make_job("job-2", 2.0, None)
    done = make_job("job-3", 3.0, 4.0)
    manager._jobs = {first.job_id: first, second.job_id: second, done.job_id: done}

    status = manager.get_job_status("job-2")

    assert status["queuePosition"] == 2


def _make_completed_follow_up_job(manager: LawkeyJobManager, runs_root: Path) -> object:
    run_dir = runs_root / "job-old"
    runtime_dir = run_dir / "_runtime"
    variant_dir = run_dir / "question_selected_manual"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    variant_dir.mkdir(parents=True, exist_ok=True)
    selected = [
        {
            "file_id": "file-1",
            "relative_path": "case-a.txt",
            "absolute_path": "/tmp/case-a.txt",
            "document_title": "군 징계처분 취소",
            "source_group": "structured_precedent",
            "token_count": 10,
            "anchor_text": "정신건강 문제로 인한 돌발행위는 보호와 관리가 필요하다.",
            "extracted_text": "정신건강 문제로 인한 돌발행위는 보호와 관리가 필요하다. 지휘관은 위기 징후를 확인해야 한다.",
            "case_number": "2020누52490",
            "court": "서울고등법원",
            "decision_date": "2021-04-07",
            "case_name": "근신처분취소",
        }
    ]
    claims = [
        {
            "claim_id": "CLAIM-001",
            "claim_axis": "심리적 위기 관리",
            "claim_text": "심리적 불안정이 확인되면 지원 중심 관리가 가능하다.",
            "source_file_id": "file-1",
            "case_number": "2020누52490",
            "support_spans": [{"quote": "위기 징후를 확인해야 한다.", "evidence_id": "file-1-q1"}],
        }
    ]
    chunk_output = {
        "chunk_id": "chunk-1",
        "claims_proposed": claims,
        "analysis_text": "기존 청크 분석은 심리적 위기 관리 논리를 포함한다.",
    }
    (run_dir / "selected_precedents.json").write_text(json.dumps(selected, ensure_ascii=False), encoding="utf-8")
    (variant_dir / "selected_files.json").write_text(json.dumps(selected, ensure_ascii=False), encoding="utf-8")
    (variant_dir / "claim_ledger.json").write_text(json.dumps(claims, ensure_ascii=False), encoding="utf-8")
    (variant_dir / "answer_plan.json").write_text(json.dumps({"body_claim_ids": ["CLAIM-001"]}, ensure_ascii=False), encoding="utf-8")
    (variant_dir / "comparison_summary.json").write_text("{}", encoding="utf-8")
    (variant_dir / "chunk_outputs.jsonl").write_text(json.dumps(chunk_output, ensure_ascii=False) + "\n", encoding="utf-8")
    (variant_dir / "final_answer.md").write_text("## 종합 판단\n기존 답변 본문", encoding="utf-8")
    job = type(manager)._require_job.__globals__["JobRecord"](
        job_id="job-old",
        mode="question",
        user_task="군인이 우산을 던진 사안",
        run_dir=run_dir,
        created_at=1.0,
        status_path=runtime_dir / "status.json",
        selected_manifest_path=run_dir / "selected_precedents.json",
        chunk_plan=[],
        selected_count=1,
        finished_at=2.0,
        runtime_control_path=runtime_dir / "control.json",
        client_id="browser-a",
    )
    job.status_path.write_text(json.dumps({"phase": "done", "state": "completed", "selected_file_count": 1}), encoding="utf-8")
    manager._jobs[job.job_id] = job
    return job


def test_follow_up_answers_from_existing_artifact_pack_without_new_search(tmp_path: Path, monkeypatch) -> None:
    runs_root = tmp_path / "runs"
    manager = LawkeyJobManager(runs_root=runs_root)
    _make_completed_follow_up_job(manager, runs_root)
    captured_prompts: list[str] = []

    def fake_call_chat(messages, **_kwargs):
        prompt = messages[-1]["content"]
        captured_prompts.append(prompt)
        assert "추가 질문" in prompt
        assert "이 판례를 반대논리로도 쓸 수 있어?" in prompt
        assert "기존 청크 분석은 심리적 위기 관리 논리를 포함한다." in prompt
        return json.dumps(
            {
                "answerable": True,
                "answer_markdown": "## 추가 답변\n기존 청크와 본문으로 답변 가능합니다.",
                "needed_keywords": [],
            },
            ensure_ascii=False,
        )

    def fail_create_job(_payload):
        raise AssertionError("answerable follow-up must not start a new search job")

    monkeypatch.setattr("backend.jobs.rag.call_chat", fake_call_chat)
    monkeypatch.setattr(manager, "create_job", fail_create_job)

    result = manager.follow_up("job-old", {"userTask": "이 판례를 반대논리로도 쓸 수 있어?", "clientId": "browser-a"})

    assert result["mode"] == "answered_from_existing"
    assert result["answerMarkdown"].startswith("## 추가 답변")
    assert result["sourceJobId"] == "job-old"
    assert captured_prompts


def test_follow_up_starts_new_job_with_needed_keywords_when_existing_packs_cannot_answer(tmp_path: Path, monkeypatch) -> None:
    runs_root = tmp_path / "runs"
    manager = LawkeyJobManager(runs_root=runs_root)
    _make_completed_follow_up_job(manager, runs_root)
    created_payloads: list[dict] = []

    def fake_call_chat(messages, **_kwargs):
        prompt = messages[-1]["content"]
        assert "전혀 다른 명예훼손 쟁점" in prompt
        return json.dumps(
            {
                "answerable": False,
                "answer_markdown": "",
                "missing_information": ["기존 판례 묶음에 명예훼손 판례가 없음"],
                "needed_keywords": ["명예훼손", "공연성", "허위사실 적시"],
            },
            ensure_ascii=False,
        )

    def fake_create_job(payload):
        created_payloads.append(payload)
        return {"jobId": "job-new", "statusUrl": "/api/jobs/job-new", "resultUrl": "/api/jobs/job-new/result"}

    monkeypatch.setattr("backend.jobs.rag.call_chat", fake_call_chat)
    monkeypatch.setattr(manager, "create_job", fake_create_job)

    result = manager.follow_up("job-old", {"userTask": "전혀 다른 명예훼손 쟁점도 알려줘", "clientId": "browser-a"})

    assert result["mode"] == "new_job_started"
    assert result["jobId"] == "job-new"
    assert created_payloads
    assert created_payloads[0]["mode"] == "question"
    assert created_payloads[0]["clientId"] == "browser-a"
    assert "전혀 다른 명예훼손 쟁점도 알려줘" in created_payloads[0]["userTask"]
    assert "명예훼손" in created_payloads[0]["userTask"]


def test_follow_up_force_new_job_skips_synchronous_pack_llm(tmp_path: Path, monkeypatch) -> None:
    runs_root = tmp_path / "runs"
    manager = LawkeyJobManager(runs_root=runs_root)
    _make_completed_follow_up_job(manager, runs_root)
    created_payloads: list[dict] = []

    def fail_call_chat(*_args, **_kwargs):
        raise AssertionError("forceNewJob follow-up must not wait for synchronous LLM classification")

    def fake_create_job(payload):
        created_payloads.append(payload)
        return {"jobId": "job-new", "statusUrl": "/api/jobs/job-new", "resultUrl": "/api/jobs/job-new/result"}

    monkeypatch.setattr("backend.jobs.rag.call_chat", fail_call_chat)
    monkeypatch.setattr(manager, "create_job", fake_create_job)

    result = manager.follow_up("job-old", {"userTask": "추가로 설명해줘", "clientId": "browser-a", "forceNewJob": True})

    assert result["mode"] == "new_job_started"
    assert result["jobId"] == "job-new"
    assert created_payloads
    assert created_payloads[0]["mode"] == "question"
    assert created_payloads[0]["clientId"] == "browser-a"
    assert "추가로 설명해줘" in created_payloads[0]["userTask"]
    assert "시간초과" in created_payloads[0]["userTask"]


def test_follow_up_force_new_document_request_does_not_start_question_search(tmp_path: Path, monkeypatch) -> None:
    runs_root = tmp_path / "runs"
    manager = LawkeyJobManager(runs_root=runs_root)
    old_job = _make_completed_follow_up_job(manager, runs_root)
    old_job.user_task = "경찰, 국가에 대해서 회의감을 내뱉고 이들에 대해서 불충성하라고 공개적으로 발언하는건 죄임?"
    created_payloads: list[dict] = []

    def fail_call_chat(*_args, **_kwargs):
        raise AssertionError("forceNewJob document follow-up must not wait for synchronous LLM classification")

    def fake_create_job(payload):
        created_payloads.append(payload)
        return {"jobId": "job-doc", "statusUrl": "/api/jobs/job-doc", "resultUrl": "/api/jobs/job-doc/result"}

    monkeypatch.setattr("backend.jobs.rag.call_chat", fail_call_chat)
    monkeypatch.setattr(manager, "create_job", fake_create_job)

    result = manager.follow_up(
        "job-old",
        {
            "userTask": "그럼 이 사람을 고소하는 고소장 작성해줘",
            "clientId": "browser-a",
            "forceNewJob": True,
        },
    )

    assert result["mode"] == "new_job_started"
    assert result["jobId"] == "job-doc"
    assert created_payloads
    assert created_payloads[0]["mode"] == "document"
    assert created_payloads[0]["documentPresetId"] == "complaint"
    assert created_payloads[0]["clientId"] == "browser-a"
    assert "경찰, 국가에 대해서 회의감을" in created_payloads[0]["userTask"]
    assert "그럼 이 사람을 고소하는 고소장 작성해줘" in created_payloads[0]["userTask"]
    assert "경찰, 국가에 대해서 회의감을" in created_payloads[0]["documentContext"]
    assert "[이전 분석에서 이어진 새 판례검색 요청]" not in created_payloads[0]["userTask"]
    assert "새 검색 키워드" not in created_payloads[0]["userTask"]


def test_create_job_normalizes_question_document_request_to_document(tmp_path: Path, monkeypatch) -> None:
    runs_root = tmp_path / "runs"
    manager = LawkeyJobManager(runs_root=runs_root)
    monkeypatch.setattr(manager, "_run_job", lambda _job: None)

    created = manager.create_job(
        {
            "mode": "question",
            "userTask": "그럼 이 사람을 고소하는 고소장 작성해줘",
            "clientId": "browser-a",
        }
    )

    job = manager._jobs[created["jobId"]]
    assert job.mode == "document"
    assert job.document_preset_id == "complaint"


class FakeManager:
    def list_jobs(self, client_id: str = "") -> list[dict[str, object]]:
        if client_id and client_id != "browser-a":
            return []
        return [{"jobId": "job-123", "state": "queued", "queuePosition": 1, "clientId": client_id}]

    def create_job(self, payload: dict) -> dict:
        return {"jobId": "job-123", "statusUrl": "/api/jobs/job-123", "resultUrl": "/api/jobs/job-123/result"}

    def get_job_status(self, job_id: str) -> dict:
        assert job_id == "job-123"
        return {"jobId": job_id, "phase": "variant", "state": "analyzing_chunks", "completedChunks": 3}

    def get_job_result(self, job_id: str) -> dict:
        assert job_id == "job-123"
        return {"answerMarkdown": "# 답변", "selectedPrecedents": [], "claims": [], "usedPrecedentIds": []}

    def get_precedent_detail(self, job_id: str, precedent_id: str) -> dict:
        assert job_id == "job-123"
        assert precedent_id == "file-1"
        return {"precedentId": precedent_id, "fullText": "전문", "usedQuotes": []}

    def follow_up(self, job_id: str, payload: dict) -> dict:
        assert job_id == "job-123"
        assert payload["userTask"] == "이어 질문"
        return {"mode": "answered_from_existing", "sourceJobId": job_id, "answerMarkdown": "## 추가 답변"}

    def cancel_job(self, job_id: str, payload: dict) -> dict:
        assert job_id == "job-123"
        return {"jobId": job_id, "phase": "done", "state": "cancelled", "error": "사용자가 요청을 취소했습니다."}


def test_api_lists_jobs() -> None:
    client = TestClient(create_app(FakeManager()))

    response = client.get("/api/jobs")

    assert response.status_code == 200
    assert response.json()[0]["jobId"] == "job-123"


def test_api_filters_jobs_by_browser_client_id() -> None:
    client = TestClient(create_app(FakeManager()))

    response = client.get("/api/jobs?clientId=browser-b")

    assert response.status_code == 200
    assert response.json() == []


def test_api_exposes_job_status_result_and_precedent_detail() -> None:
    client = TestClient(create_app(FakeManager()))

    create_response = client.post("/api/jobs", json={"mode": "question", "userTask": "질문"})
    assert create_response.status_code == 200
    assert create_response.json()["jobId"] == "job-123"

    status_response = client.get("/api/jobs/job-123")
    assert status_response.status_code == 200
    assert status_response.json()["completedChunks"] == 3

    result_response = client.get("/api/jobs/job-123/result")
    assert result_response.status_code == 200
    assert result_response.json()["answerMarkdown"] == "# 답변"

    precedent_response = client.get("/api/jobs/job-123/precedents/file-1")
    assert precedent_response.status_code == 200
    assert precedent_response.json()["precedentId"] == "file-1"

    follow_up_response = client.post("/api/jobs/job-123/follow-up", json={"userTask": "이어 질문"})
    assert follow_up_response.status_code == 200
    assert follow_up_response.json()["mode"] == "answered_from_existing"

    cancel_response = client.post("/api/jobs/job-123/cancel", json={})
    assert cancel_response.status_code == 200
    assert cancel_response.json()["state"] == "cancelled"


def test_api_allows_cross_origin_requests() -> None:
    client = TestClient(create_app(FakeManager()))

    response = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:8081",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"


def test_api_serves_frontend_dist_when_present(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    (dist_dir / "index.html").write_text("<html><body>Lawkey</body></html>", encoding="utf-8")
    (dist_dir / "favicon.ico").write_text("ico", encoding="utf-8")

    client = TestClient(create_app(FakeManager(), frontend_dist=dist_dir))

    root_response = client.get("/")
    assert root_response.status_code == 200
    assert "Lawkey" in root_response.text

    asset_response = client.get("/favicon.ico")
    assert asset_response.status_code == 200
    assert asset_response.text == "ico"

    fallback_response = client.get("/nonexistent/path")
    assert fallback_response.status_code == 200
    assert "Lawkey" in fallback_response.text


def test_job_artifact_route_rejects_run_dir_outside_runs_root(tmp_path: Path) -> None:
    runs_root = tmp_path / "runs"
    outside = tmp_path / "outside-job"
    outside.mkdir(parents=True)
    outside.joinpath("secret.txt").write_text("outside secret", encoding="utf-8")
    manager = LawkeyJobManager(runs_root=runs_root)
    job = backend_jobs.JobRecord(
        job_id="job-outside",
        mode="question",
        user_task="artifact traversal",
        run_dir=outside,
        created_at=0.0,
        status_path=outside / "_runtime" / "status.json",
        selected_manifest_path=outside / "selected_precedents.json",
        chunk_plan=[],
        runtime_control_path=outside / "_runtime" / "control.json",
    )
    with manager._lock:  # type: ignore[attr-defined]
        manager._jobs[job.job_id] = job  # type: ignore[attr-defined]
    client = TestClient(create_app(manager=manager))

    response = client.get("/api/jobs/job-outside/artifacts/secret.txt")

    assert response.status_code == 400
    assert response.json()["detail"] == "invalid artifact path"
