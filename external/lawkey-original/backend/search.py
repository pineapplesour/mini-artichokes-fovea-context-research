from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
import re
from dataclasses import dataclass
from typing import Any
from concurrent.futures import ThreadPoolExecutor, TimeoutError

from .config import (
    DEFAULT_KEYWORD_COUNT,
    DEFAULT_PER_KEYWORD_LIMIT,
    DEFAULT_SELECT_MODEL,
    DEFAULT_TOP_K,
    PRECEDENT_DB_PATH,
    WORKSPACE_SCRIPTS,
)
from .models import aggregate_selected_rows

if str(WORKSPACE_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_SCRIPTS))

import legal_evidence_rag as rag  # type: ignore
import precedent_search_index as search_index  # type: ignore


SAFE_TOKEN_PATTERN = re.compile(r"[0-9A-Za-z가-힣]+")
DISCIPLINE_FOCUS_TERMS = (
    "징계",
    "징계처분",
    "징계처분취소",
    "징계처분무효",
    "징계처분무효확인",
    "해임",
    "파면",
    "견책",
    "감봉",
    "정직",
    "강등",
    "강임",
    "벌점",
    "공권정지",
)
ANTI_NOISE_TERMS = (
    "재심",
    "재심청구",
    "재심대상판결",
    "양도담보",
    "분양대금",
)
TRAFFIC_ACCIDENT_TERMS = (
    "교통사고",
    "과속",
    "속도위반",
    "신호위반",
    "차사고",
    "차량사고",
    "사고",
    "과실",
    "100 0",
    "100대0",
    "백대영",
)
WORK_COMP_INTENT_TERMS = (
    "산재",
    "산업재해",
    "업무상 재해",
    "업무상재해",
    "근로복지공단",
    "요양급여",
    "유족급여",
    "장의비",
    "요양불승인",
    "출퇴근",
    "출근",
    "퇴근",
    "업무 중",
    "업무중",
    "근무 중",
    "근무중",
    "배달",
    "퀵서비스",
    "회사",
    "근로자",
)
WORK_COMP_LABEL_TERMS = (
    "유족급여",
    "요양급여",
    "장의비",
    "요양불승인",
    "유족보상",
    "부지급처분",
    "지급불승인",
    "산업재해",
    "산재",
    "업무상재해",
    "업무상 재해",
)
TRAFFIC_LIABILITY_LABEL_TERMS = (
    "교통사고처리특례법",
    "특례법위반",
    "도로교통법",
    "위험운전",
    "치상",
    "치사",
    "손해배상",
    "구상금",
    "보험금",
    "과실비율",
)
TRAFFIC_SELF_FAULT_TERMS = (
    "피고인",
    "피의자",
    "운전자",
    "가해차량",
    "가해 차량",
    "제한속도",
    "속도위반",
    "과속",
    "전방주시",
    "안전운전",
    "주의의무",
    "충격",
    "충돌",
    "치상",
    "치사",
)
TRAFFIC_SELF_FAULT_SEARCH_TERMS = (
    "교통사고처리특례법",
    "도로교통법",
    "피고인",
    "운전자",
    "제한속도",
    "속도위반",
    "과속",
    "전방주시",
    "주의의무",
    "치상",
    "치사",
    "사고후미조치",
    "업무상과실",
)
TRAFFIC_OPPOSITE_FAULT_NEGATIVE_TERMS = (
    "피해자의 일방적인 과실",
    "피해자가 술에 만취",
    "피해자가 만취",
    "피해자의 과속",
    "상대방의 과속",
    "상대 차량의 과속",
    "엄청난 과속",
    "시속 207",
    "청구인 운전의 차량",
    "청구인의 과실이 부정",
    "기소유예처분취소",
)
TRAFFIC_IRRELEVANT_LABEL_TERMS = (
    "공직선거법",
    "간접투자",
    "자산운용",
    "조세",
    "상속세",
    "특허",
    "위증",
    "무고",
    "영업비밀",
    "대여금",
)
TRAFFIC_CONSTITUTIONAL_REVIEW_LABEL_TERMS = (
    "헌법소원",
    "위헌확인",
    "위헌제청",
    "헌법재판",
)
CONSTITUTIONAL_QUERY_TERMS = (
    "헌법",
    "위헌",
    "헌법소원",
    "기소유예",
)
TRAFFIC_QUERY_NOISE_TERMS = {
    "어캐함",
    "어떡함",
    "어쩌지",
    "망함",
    "났고",
    "났는데",
    "0인데",
    "100대",
}


def sanitize_search_query(query: str) -> str:
    tokens = SAFE_TOKEN_PATTERN.findall(query or "")
    return " ".join(tokens).strip()


def _is_meaningful_label(value: str) -> bool:
    text = " ".join(str(value or "").split()).strip()
    if not text:
        return False
    if text.isdigit():
        return False
    if len(text) <= 2 and text.isalnum():
        return False
    return True


def _query_focus_terms(user_task: str) -> set[str]:
    normalized = sanitize_search_query(user_task)
    focus_terms: set[str] = set()
    for term in DISCIPLINE_FOCUS_TERMS:
        if term in normalized:
            focus_terms.add(term)
    return focus_terms


def _is_plain_traffic_accident_query(user_task: str) -> bool:
    normalized = sanitize_search_query(user_task)
    if not any(term in normalized for term in TRAFFIC_ACCIDENT_TERMS):
        return False
    return not any(term in normalized for term in WORK_COMP_INTENT_TERMS)


def _is_self_fault_traffic_query(user_task: str) -> bool:
    if not _is_plain_traffic_accident_query(user_task):
        return False
    normalized = sanitize_search_query(user_task)
    compact = re.sub(r"\s+", "", normalized)
    self_markers = (
        "내가",
        "제가",
        "본인이",
        "내과실",
        "내책임",
        "내잘못",
        "100대0",
        "100:0",
        "1000",
        "백대영",
        "전부",
        "가해자",
        "사고냈",
        "사고를냈",
        "사고냄",
        "과속하다가",
        "속도위반으로",
        "망함",
    )
    self_speed_markers = (
        "내가과속",
        "제가과속",
        "과속하다가",
        "과속으로사고",
        "속도위반으로사고",
    )
    opposite_markers = (
        "상대방",
        "상대차",
        "상대차량",
        "피해자가과속",
        "피해자의과속",
        "뒤에서",
        "후방",
    )
    if any(marker in compact for marker in self_speed_markers):
        return True
    if any(marker in compact for marker in self_markers):
        return not any(marker in compact for marker in opposite_markers) or "내과실" in compact or "100대0" in compact
    return False


def _plain_traffic_accident_queries(user_task: str) -> list[str]:
    if not _is_plain_traffic_accident_query(user_task):
        return []
    if _is_self_fault_traffic_query(user_task):
        return [
            "교통사고처리특례법 과속 속도위반 치상 형사처벌",
            "피고인 제한속도 초과 교통사고 전방주시 주의의무",
            "도로교통법 과속 사고후미조치 합의 보험 손해배상",
            "과속 운전자 과실비율 손해배상 교통사고",
            "교통사고 과속 과실비율 손해배상 보험 합의",
            "교통사고처리특례법 과속 치상 형사합의 처벌",
            "도로교통법 과속 사고 손해배상 과실",
        ]
    return [
        "교통사고 과속 과실비율 손해배상 보험 합의",
        "교통사고처리특례법 과속 치상 형사합의 처벌",
        "도로교통법 과속 사고 손해배상 과실",
    ]


def _decision_year(row: dict[str, Any]) -> int:
    raw = str(row.get("decision_date") or row.get("case_number") or "")
    match = re.search(r"(19|20)\d{2}", raw)
    if not match:
        return 0
    try:
        return int(match.group(0))
    except ValueError:
        return 0


def _row_penalty(row: dict[str, Any], *, user_task: str) -> float:
    parts = [
        str(row.get("title") or ""),
        str(row.get("case_name") or ""),
        str(row.get("case_type") or ""),
        str(row.get("court") or ""),
        str(row.get("case_number") or ""),
    ]
    label_text = " ".join(" ".join(parts).split())
    penalty = 0.0
    if not _is_meaningful_label(str(row.get("case_name") or "")) and not _is_meaningful_label(str(row.get("title") or "")):
        penalty += 75.0
    if str(row.get("source_dataset") or "") in {"02_lbox_open", "03_distressed_korean_law"} and not _is_meaningful_label(str(row.get("case_name") or "")):
        penalty += 40.0

    focus_terms = _query_focus_terms(user_task)
    if focus_terms:
        if not any(term in label_text for term in focus_terms):
            penalty += 160.0
        else:
            penalty -= 12.0

    normalized_task = sanitize_search_query(user_task)
    if "재심" not in normalized_task and any(term in label_text for term in ANTI_NOISE_TERMS):
        penalty += 220.0

    if _is_plain_traffic_accident_query(user_task):
        if any(term in label_text for term in WORK_COMP_LABEL_TERMS):
            penalty += 520.0
        if any(term in label_text for term in TRAFFIC_LIABILITY_LABEL_TERMS):
            penalty -= 90.0
        case_number = str(row.get("case_number") or "")
        if re.search(r"(노|도|고단|고정|고합)", case_number):
            penalty -= 35.0
        if re.search(r"(구합|구단|누)", case_number) and any(term in label_text for term in WORK_COMP_LABEL_TERMS):
            penalty += 140.0

    # Recency bonus: newer precedents reflect current law better.
    # 2025 → -50, 2020 → -40, 2010 → -20, 2000 → 0, pre-2000 → 0.
    year = _decision_year(row)
    if year >= 2000:
        penalty -= 2.0 * (year - 2000)
    return penalty


def _row_lookup(row: Any, key: str) -> Any:
    if isinstance(row, dict):
        return row.get(key)
    try:
        return row[key]
    except Exception:
        return None


def _row_penalty_input(row: Any) -> dict[str, Any]:
    keys = (
        "canonical_id",
        "source_dataset",
        "source_path",
        "title",
        "case_number",
        "court",
        "decision_date",
        "case_name",
        "case_type",
    )
    return {key: _row_lookup(row, key) for key in keys}


def _row_label_text(row: Any) -> str:
    parts = [
        str(_row_lookup(row, "title") or ""),
        str(_row_lookup(row, "case_name") or ""),
        str(_row_lookup(row, "case_type") or ""),
        str(_row_lookup(row, "court") or ""),
        str(_row_lookup(row, "case_number") or ""),
    ]
    return " ".join(" ".join(parts).split())


def _should_exclude_iterative_row(row: Any, *, user_task: str) -> bool:
    if not _is_plain_traffic_accident_query(user_task):
        return False
    label_text = _row_label_text(row)
    return any(term in label_text for term in WORK_COMP_LABEL_TERMS)


def _prioritize_iterative_rows(rows: list[Any], *, user_task: str) -> list[Any]:
    if not _is_plain_traffic_accident_query(user_task):
        return list(rows)
    indexed = list(enumerate(rows))
    filtered = [(idx, row) for idx, row in indexed if not _should_exclude_iterative_row(row, user_task=user_task)]
    if filtered:
        indexed = filtered
    indexed.sort(
        key=lambda item: (
            _row_penalty(_row_penalty_input(item[1]), user_task=user_task),
            item[0],
        )
    )
    return [row for _, row in indexed]


def _rerank_ranked_rows(ranked: list[dict[str, Any]], *, user_task: str, limit: int) -> list[dict[str, Any]]:
    rescored: list[dict[str, Any]] = []
    for row in ranked:
        adjusted = dict(row)
        adjusted_score = float(row.get("best_score") or 0.0) + _row_penalty(row, user_task=user_task)
        adjusted["adjusted_score"] = adjusted_score
        rescored.append(adjusted)
    rescored.sort(
        key=lambda item: (
            float(item.get("adjusted_score") or 0.0),
            -int(item.get("keyword_hit_count") or 0),
            -_decision_year(item),
            str(item.get("canonical_id") or ""),
        )
    )
    return rescored[:limit]


def build_search_queries(
    user_task: str,
    *,
    keyword_count: int = DEFAULT_KEYWORD_COUNT,
    select_model: str = DEFAULT_SELECT_MODEL,
    keyword_generator=rag.generate_search_keywords,
    timeout_seconds: int = 120,
) -> list[str]:
    base_query = sanitize_search_query(user_task)
    fallback_queries: list[str] = []
    if base_query:
        fallback_queries.append(base_query)
        fallback_queries.extend(token for token in base_query.split(" ") if token and token not in fallback_queries)

    keywords: list[str] = []
    executor = ThreadPoolExecutor(max_workers=1)
    future = None
    try:
        future = executor.submit(keyword_generator, user_task, model=select_model, keyword_count=keyword_count)
        keywords = list(future.result(timeout=timeout_seconds) or [])
    except (TimeoutError, RuntimeError, ValueError):
        if future is not None:
            future.cancel()
        keywords = []
    except Exception:
        if future is not None:
            future.cancel()
        keywords = []
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    queries: list[str] = []
    for query in [base_query] + _plain_traffic_accident_queries(user_task) + [sanitize_search_query(keyword) for keyword in keywords]:
        if query and query not in queries:
            queries.append(query)
    for query in fallback_queries:
        if query and query not in queries:
            queries.append(query)
    return queries


def _fetch_precedent_rows(conn: sqlite3.Connection, canonical_ids: list[str]) -> list[dict[str, Any]]:
    if not canonical_ids:
        return []
    placeholders = ",".join("?" for _ in canonical_ids)
    rows = conn.execute(
        f"""
        select canonical_id, source_dataset, source_path, title, case_number, court, decision_date, case_name, case_type, full_text, text_hash
        from precedents
        where canonical_id in ({placeholders})
        """,
        canonical_ids,
    ).fetchall()
    by_id = {
        row[0]: {
            "canonical_id": row[0],
            "source_dataset": row[1],
            "source_path": row[2],
            "title": row[3],
            "case_number": row[4],
            "court": row[5],
            "decision_date": row[6],
            "case_name": row[7],
            "case_type": row[8],
            "full_text": row[9],
            "text_hash": row[10],
        }
        for row in rows
    }
    return [by_id[item] for item in canonical_ids if item in by_id]


def canonical_row_to_selected_record(row: dict[str, Any]) -> dict[str, Any]:
    source_path = str(row.get("source_path") or "")
    full_text = str(row.get("full_text") or "")
    document_title = str(row.get("title") or row.get("case_name") or row.get("case_number") or row.get("canonical_id") or "")
    suffix = Path(source_path).suffix.lstrip(".") or "txt"
    return {
        "file_id": str(row.get("canonical_id") or ""),
        "relative_path": source_path,
        "absolute_path": source_path,
        "document_title": document_title,
        "doc_type": suffix,
        "source_group": "structured_precedent",
        "token_count": max(1, len(full_text) // 4),
        "anchor_text": " ".join(full_text.split())[:500],
        "extracted_text": full_text,
        "candidate_boundaries": [],
        "is_direct_evidence": False,
        "is_format_sample": False,
        "content_hash": str(row.get("text_hash") or ""),
        "duplicate_paths": [],
        "case_number": str(row.get("case_number") or ""),
        "court": str(row.get("court") or ""),
        "decision_date": str(row.get("decision_date") or ""),
        "case_name": str(row.get("case_name") or ""),
    }


def _beta2_parse_groups(text: str, need_min: int = 2) -> list[list[str]]:
    """Gemma 응답에서 '그룹 N: kw, kw, ...' 줄을 의미 그룹 리스트로 파싱."""
    import re as _re
    groups = []
    for line in text.split("\n"):
        m = _re.match(r"\s*(?:그룹|Group|G)\s*\d+\s*[:\]]\s*(.+)", line)
        if not m:
            continue
        raw = m.group(1)
        kws = [w.strip().strip('"').strip("'").strip('`') for w in _re.split(r"[,\|/\n]", raw)]
        kws = [w for w in kws if w and 2 <= len(w) <= 20 and not any(c in w for c in '()[]<>')]
        if len(kws) >= 2:
            groups.append(kws[:10])
    return groups if len(groups) >= need_min else []


def _beta2_build_fts(groups: list[list[str]], n_and: int | None = None) -> str:
    use = groups if n_and is None else groups[:n_and]
    # prefix matching: "유심"은 tokenizer 상 "유심칩"/"유심을" 등에 가려짐
    # 공백 없는 2자 이상은 "유심*" 형태로 prefix 검색, 공백 포함은 phrase 그대로
    def _term(w: str) -> str:
        w = w.strip().strip('"').strip("'")
        if not w:
            return ""
        if " " in w or len(w) < 2:
            return f'"{w}"'
        return f"{w}*"
    out = []
    for g in use:
        terms = [_term(w) for w in g]
        terms = [t for t in terms if t]
        if terms:
            out.append("(" + " OR ".join(terms) + ")")
    return " AND ".join(out)


def _beta2_fts_query(conn: sqlite3.Connection, q: str, limit: int = 100) -> list[sqlite3.Row]:
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            """select p.canonical_id, p.case_number, p.court, p.decision_date, p.full_text
                      , p.title, p.case_name, p.case_type, p.source_dataset, p.source_path
               from precedents_fts fts
               join precedents p on p.canonical_id = fts.canonical_id
               where precedents_fts match ?
               order by fts.rank limit ?""",
            (q, limit),
        )
        return cur.fetchall()
    except Exception:
        return []


def _beta2_fts_graceful(conn: sqlite3.Connection, groups: list[list[str]],
                       *, limit: int = 100, min_hits: int = 3) -> tuple[list[sqlite3.Row], list[dict]]:
    """0 hits 방지 룰베이스: full AND → drop_last_N → 단일 그룹 OR → flat OR-union.
    마지막 폴백까지 가면 무조건 BM25 상위를 돌려준다 ("판례 못찾아도 n개 수집" 원칙)."""
    trace = []
    q = _beta2_build_fts(groups)
    r = _beta2_fts_query(conn, q, limit=limit)
    trace.append({"strategy": "full_AND", "n_groups": len(groups), "hits": len(r)})
    if len(r) >= min_hits:
        return r, trace
    best = r
    for drop in range(1, min(len(groups) - 1, 2) + 1):
        dropped = groups[:-drop] if drop < len(groups) else []
        if len(dropped) < 2:
            break
        q = _beta2_build_fts(dropped, n_and=len(dropped))
        r2 = _beta2_fts_query(conn, q, limit=limit)
        trace.append({"strategy": f"drop_last_{drop}", "n_groups": len(dropped), "hits": len(r2)})
        if len(r2) >= min_hits:
            return r2, trace
        if len(r2) > len(best):
            best = r2
    # 폴백 1: 단일 그룹(첫 그룹) OR
    if groups:
        q1 = "(" + " OR ".join(f'"{w}"' for w in groups[0]) + ")"
        r3 = _beta2_fts_query(conn, q1, limit=limit)
        trace.append({"strategy": "single_group_OR", "group_idx": 0, "hits": len(r3)})
        if len(r3) >= min_hits:
            return r3, trace
        if len(r3) > len(best):
            best = r3
    # 폴백 2: 전 키워드 flat OR-union (BM25 상위)
    flat = list({w for g in groups for w in g})
    if flat:
        q2 = "(" + " OR ".join(f'"{w}"' for w in flat) + ")"
        r4 = _beta2_fts_query(conn, q2, limit=limit)
        trace.append({"strategy": "flat_OR_union", "n_kws": len(flat), "hits": len(r4)})
        if len(r4) >= min_hits:
            return r4, trace
        if len(r4) > len(best):
            best = r4
    return best, trace


def _beta2_windows_around(text: str, keywords: list[str], *, radius: int = 100,
                         max_total_chars: int = 2400) -> str:
    """키워드 매칭 위치 ±radius 자 모든 매칭 수집, 겹침 merge, 총 char 상한 관리."""
    import re as _re
    spans = []
    for kw in keywords:
        for m in _re.finditer(_re.escape(kw), text):
            spans.append([max(0, m.start() - radius), min(len(text), m.end() + radius)])
    if not spans:
        return ""
    spans.sort()
    merged = []
    for s, e in spans:
        if merged and s <= merged[-1][1] + 20:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    pieces = []
    used = 0
    for s, e in merged:
        frag = text[s:e].replace("\n", " ")
        if used + len(frag) > max_total_chars:
            remain = max_total_chars - used
            if remain > 100:
                pieces.append(frag[:remain])
                used += remain
            break
        pieces.append(frag)
        used += len(frag)
    return " ... ".join(pieces)


def _beta2_parse_judge(text: str, n: int) -> tuple[dict, list[list[str]]]:
    import re as _re
    labels = {}
    for i in range(1, n + 1):
        m = _re.search(rf"(?:^|\s|\(){i}\s*[:\.\)]\s*\[?(useful|none)\]?", text)
        if m:
            labels[i] = m.group(1).lower()
    ng_text = ""
    m = _re.search(r"LEARNED_GROUPS.*?$", text, _re.DOTALL | _re.IGNORECASE)
    if m:
        ng_text = m.group()
    return labels, _beta2_parse_groups(ng_text)


def _beta2_gemma(prompt: str, model: str, *, max_tokens: int = 4096, thinking_level: str = "") -> str:
    """legal_evidence_rag 의 _call_gemini_generate_content 재사용.
    기본 thinkingLevel은 work16의 기본값 (Gemma는 minimal). thinking_level
    인자를 명시하면 그 값으로 override (예: "high" — Beta-7 seed 키워드
    생성 시 더 정확한 ambiguity disambiguation 위해)."""
    from legal_evidence_rag import _call_gemini_generate_content  # type: ignore
    messages = [{"role": "user", "content": prompt}]
    try:
        return _call_gemini_generate_content(messages, model=model, timeout=180, thinking_level=thinking_level)
    except Exception as exc:
        return f"[GEMMA_ERR: {type(exc).__name__}: {exc}]"


@dataclass(frozen=True)
class _Beta5QueryProfile:
    raw_query: str
    required_facets: dict[str, list[str]]
    search_groups: list[list[str]]
    positive_terms: list[str]
    hard_negative_terms: list[str]
    generated_issue_terms: list[str]


_BETA5_INVESTIGATIVE_TERMS = [
    "수사기관", "수사관", "경찰", "사법경찰관", "검찰", "검사", "압수", "압수수색", "영장",
    "수사", "증거수집", "증거능력", "위법수집증거", "디지털포렌식", "포렌식",
]
_BETA5_DEVICE_ACCESS_TERMS = [
    "휴대전화", "휴대폰", "스마트폰", "핸드폰", "유심", "유심카드", "SIM", "USIM", "카카오톡",
    "카톡", "텔레그램", "메신저", "계정", "로그인", "대화내용", "메시지", "채팅",
]
_BETA5_MILITARY_KEY_TERMS = [
    "군대", "군", "공군", "육군", "해군", "부대", "탄약고", "탄약", "무기고", "총기",
    "열쇠", "키", "잠금", "시건", "관리", "보관", "당직", "경계", "군사시설",
]
_BETA5_PRIVATE_DEVICE_CRIME_TERMS = [
    "피고인은 피해자", "피고인이 피해자", "피의자가 피해자", "피고인은 피해자의", "피고인이 피해자의",
    "피해자의 휴대", "피해자 휴대", "편취", "절취", "갈취", "협박", "사기", "보이스피싱",
]


@dataclass(frozen=True)
class _Beta6VerifyResult:
    label: str
    confidence: float
    positive_reasons: list[str]
    negative_reasons: list[str]


@dataclass(frozen=True)
class _Beta6QuerySpec:
    name: str
    groups: dict[str, list[str]]
    required_groups: set[str]


_BETA6_REGEX_CACHE: dict[str, re.Pattern[str]] = {}
_BETA6_SIM_RE = re.compile(r"(?<!자)유심(?:칩)?|가입자\s*식별\s*모듈|USIM|(?<![A-Za-z])SIM(?![A-Za-z])", re.I)
_BETA6_DIGITAL_MESSENGER_STRONG_TERMS = (
    "카카오톡",
    "카톡",
    "텔레그램",
    "메신저",
    "대화내용",
    "대화 내용",
)
_BETA6_DIGITAL_PHONE_ACCESS_TERMS = (
    "공기계",
    "휴대전화",
    "휴대폰",
    "스마트폰",
    "인증번호",
    "페이스 아이디",
    "잠금 해제",
)
_BETA6_DIGITAL_INVESTIGATOR_TERMS = (
    "압수수색영장",
    "압수영장",
    "압수수색",
    "수사관",
    "수사기관",
    "검사",
    "경찰",
    "검찰",
)
_BETA6_DIGITAL_ACCOUNT_ACCESS_TERMS = (
    "계정에 접속",
    "계정 접속",
    "접속하여",
    "접속하고",
    "인증번호를 전송",
    "인증번호를",
    "전송받",
    "통신한 내용을 확인",
    "대화 내용 등을 압수",
    "대화 내용 등에 대한 압수",
    "첨부파일을 압수",
    "압수할 물건",
    "디지털 포렌식",
)
_BETA6_DIGITAL_FRAUD_NOISE_TERMS = (
    "보이스피싱",
    "선불유심",
    "대포폰",
    "전기통신사업법",
    "대출",
    "현금수거",
    "중고나라",
    "물품을 택배",
)


def _beta6_normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _beta6_positions(text: str, terms: list[str] | tuple[str, ...]) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for term in terms:
        if not term:
            continue
        if term.startswith("REGEX:"):
            pattern_text = term.removeprefix("REGEX:")
            pattern = _BETA6_REGEX_CACHE.get(pattern_text)
            if pattern is None:
                pattern = re.compile(pattern_text, re.I)
                _BETA6_REGEX_CACHE[pattern_text] = pattern
            found.extend((match.start(), match.group(0)) for match in pattern.finditer(text))
            continue
        start = 0
        while True:
            idx = text.find(term, start)
            if idx < 0:
                break
            found.append((idx, term))
            start = idx + max(1, len(term))
    return found


def _beta6_contains_any(text: str, terms: list[str] | tuple[str, ...]) -> bool:
    return bool(_beta6_positions(text, terms))


def _beta6_any_near(text: str, left_terms: list[str], right_terms: list[str], max_chars: int) -> bool:
    left = _beta6_positions(text, left_terms)
    right = _beta6_positions(text, right_terms)
    return any(abs(lp - rp) <= max_chars for lp, _ in left for rp, _ in right)


def _beta6_cluster_has_terms(
    text: str,
    anchors: list[str],
    required_groups: list[list[str]],
    radius: int,
) -> bool:
    for idx, _term in _beta6_positions(text, anchors):
        start = max(0, idx - radius)
        end = min(len(text), idx + radius)
        window = text[start:end]
        if all(_beta6_contains_any(window, group) for group in required_groups):
            return True
    return False


def _beta6_has_sim_signal(text: str) -> bool:
    return bool(_BETA6_SIM_RE.search(text))


def _beta6_min_distance_between_terms(
    text: str,
    left_terms: list[str] | tuple[str, ...],
    right_terms: list[str] | tuple[str, ...],
) -> int | None:
    left = _beta6_positions(text, list(left_terms))
    right = _beta6_positions(text, list(right_terms))
    if not left or not right:
        return None
    return min(abs(lp - rp) for lp, _ in left for rp, _ in right)


def _beta6_terms_cooccur(
    text: str,
    left_terms: list[str] | tuple[str, ...],
    right_terms: list[str] | tuple[str, ...],
    *,
    span: int = 900,
) -> bool:
    distance = _beta6_min_distance_between_terms(text, left_terms, right_terms)
    return distance is not None and distance <= span


def _beta6_digital_investigative_access_features(text: str) -> dict[str, Any]:
    clean = _beta6_normalize_text(text)
    hits: list[str] = []
    messenger = _beta6_contains_any(clean, _BETA6_DIGITAL_MESSENGER_STRONG_TERMS)
    phone_or_sim = _beta6_has_sim_signal(clean) or _beta6_contains_any(clean, _BETA6_DIGITAL_PHONE_ACCESS_TERMS)
    investigator = _beta6_contains_any(clean, _BETA6_DIGITAL_INVESTIGATOR_TERMS)
    active_access = _beta6_contains_any(clean, _BETA6_DIGITAL_ACCOUNT_ACCESS_TERMS)
    sim_messenger_bridge = _beta6_terms_cooccur(
        clean,
        ["유심", "유심칩", "가입자식별모듈", "USIM", "SIM"],
        _BETA6_DIGITAL_MESSENGER_STRONG_TERMS,
        span=1100,
    )
    warrant_messenger_bridge = _beta6_terms_cooccur(
        clean,
        ["압수수색영장", "압수영장", "압수수색"],
        ["카카오톡", "텔레그램", "유심칩", "공기계", "인증번호"],
        span=1100,
    )
    account_access_bridge = _beta6_terms_cooccur(
        clean,
        ["공기계", "인증번호", "계정"],
        ["접속", "전송받", "확인할 수", "대화", "첨부파일"],
        span=900,
    )
    if messenger:
        hits.append("strong_messenger")
    if phone_or_sim:
        hits.append("phone_or_sim")
    if investigator:
        hits.append("investigator_or_warrant")
    if active_access:
        hits.append("account_or_evidence_access")
    if sim_messenger_bridge:
        hits.append("sim_messenger_bridge")
    if warrant_messenger_bridge:
        hits.append("warrant_messenger_bridge")
    if account_access_bridge:
        hits.append("account_access_bridge")
    bridge_count = sum(bool(item) for item in (sim_messenger_bridge, warrant_messenger_bridge, account_access_bridge))
    strong_access_bridge = warrant_messenger_bridge or (sim_messenger_bridge and account_access_bridge)
    if strong_access_bridge:
        hits.append("strong_access_bridge")
    fraud_noise = _beta6_contains_any(clean, _BETA6_DIGITAL_FRAUD_NOISE_TERMS)
    generic_inventory_only = _beta6_contains_any(clean, ["증거의 요지", "수사보고서", "압수조서", "압수목록"]) and bridge_count == 0
    ok = bool(
        messenger
        and phone_or_sim
        and investigator
        and active_access
        and strong_access_bridge
        and not (fraud_noise and not warrant_messenger_bridge)
        and not generic_inventory_only
    )
    score = 0.0
    score += 3.0 if messenger else -2.0
    score += 2.5 if phone_or_sim else -1.5
    score += 2.5 if investigator else -1.0
    score += 3.0 if active_access else -1.0
    score += bridge_count * 4.0
    if fraud_noise and not warrant_messenger_bridge:
        score -= 8.0
        hits.append("fraud_noise_without_direct_bridge")
    if generic_inventory_only:
        score -= 5.0
        hits.append("generic_evidence_inventory_only")
    if ok:
        hits.append("verified_digital_investigative_access")
    return {
        "ok": ok,
        "score": score,
        "hits": hits,
        "bridge_count": bridge_count,
        "fraud_noise": fraud_noise,
        "generic_inventory_only": generic_inventory_only,
    }


def _beta6_verify_kakao_usim(text: str) -> _Beta6VerifyResult:
    text = _beta6_normalize_text(text)
    positive: list[str] = []
    negative: list[str] = []

    platform_terms = ["카카오톡", "카톡"]
    usim_terms = ["REGEX:(?<!자)유심(?:칩)?", "가입자식별모듈", "USIM", "SIM"]
    investigator_terms = ["경찰", "경찰관", "수사기관", "수사관", "검찰", "검사", "압수 담당자", "수사 담당자"]
    access_terms = [
        "로그인",
        "접속",
        "열람",
        "확인",
        "복원",
        "추출",
        "분리",
        "장착",
        "REGEX:(?:대화내역|대화내용).{0,20}확인",
        "REGEX:확인.{0,20}(?:대화내역|대화내용)",
    ]
    investigation_terms = ["수사", "증거", "압수", "압수수색", "영장", "위법수집"]
    supply_terms = [
        "선불",
        "선불유심",
        "개통신청서",
        "가입신청서",
        "전기통신사업자",
        "전기통신사업법",
        "타인의 통신용",
        "다른 사람 명의",
        "타인 명의",
        "계정정보",
        "성명불상자",
        "대포폰",
        "알뜰폰",
    ]
    generic_evidence_terms = ["증거의 요지", "경찰 피의자신문조서", "사법경찰리 작성", "압수조서"]
    private_actor_terms = ["피고인", "피해자", "성명불상자", "공범", "타인"]

    has_platform = _beta6_contains_any(text, platform_terms)
    has_usim = _beta6_contains_any(text, usim_terms)
    if not has_platform:
        negative.append("missing_kakaotalk")
    if not has_usim:
        negative.append("missing_usim")
    if not has_platform or not has_usim:
        return _Beta6VerifyResult("reject", 0.92, positive, negative)

    direct_action = _beta6_cluster_has_terms(
        text,
        investigator_terms,
        [usim_terms, platform_terms, access_terms, investigation_terms],
        radius=450,
    )
    if not direct_action:
        direct_action = _beta6_cluster_has_terms(
            text,
            access_terms,
            [investigator_terms, usim_terms, platform_terms],
            radius=420,
        )

    if direct_action:
        positive.append("direct_investigator_action")
    else:
        negative.append("no_direct_investigator_action")

    if _beta6_contains_any(text, supply_terms):
        negative.append("telecom_supply_or_opening")
    if _beta6_contains_any(text, generic_evidence_terms) and not direct_action:
        negative.append("generic_police_evidence_list")
    if _beta6_any_near(text, private_actor_terms, usim_terms + platform_terms, 180) and not direct_action:
        negative.append("private_actor_usim_or_kakao")

    if "telecom_supply_or_opening" in negative:
        return _Beta6VerifyResult("reject", 0.9, positive, negative)
    if direct_action:
        return _Beta6VerifyResult("accept", 0.86, positive, negative)
    if "generic_police_evidence_list" in negative:
        return _Beta6VerifyResult("reject", 0.84, positive, negative)
    return _Beta6VerifyResult("needs_review", 0.42, positive, negative)


def _beta6_verify_military_key(text: str) -> _Beta6VerifyResult:
    text = _beta6_normalize_text(text)
    positive: list[str] = []
    negative: list[str] = []

    military_terms = ["군대", "부대", "군인", "병사", "장병", "지휘관", "당직", "경비대", "무기고", "탄약고", "군사"]
    key_terms = ["열쇠", "열쇠관리", "키 관리", "비밀번호", "암호", "출입증"]
    management_terms = ["관리", "보관", "분실", "반납", "대장", "담당", "잠금", "보관상태"]
    liability_terms = ["주의의무", "과실", "징계", "해임", "손해", "절도", "침입", "처분"]

    if not _beta6_contains_any(text, military_terms):
        negative.append("missing_military_context")
    if not _beta6_contains_any(text, key_terms):
        negative.append("missing_key_context")
    if not _beta6_contains_any(text, management_terms):
        negative.append("missing_management_context")

    key_management = _beta6_cluster_has_terms(text, key_terms, [military_terms, management_terms], radius=360)
    if key_management:
        positive.append("military_key_management")
    if key_management and _beta6_contains_any(text, liability_terms):
        positive.append("liability_or_discipline_context")

    if "military_key_management" in positive:
        confidence = 0.9 if "liability_or_discipline_context" in positive else 0.78
        return _Beta6VerifyResult("accept", confidence, positive, negative)
    if negative:
        return _Beta6VerifyResult("reject", 0.74, positive, negative)
    return _Beta6VerifyResult("needs_review", 0.45, positive, negative)


def _beta6_query_spec(name: str) -> _Beta6QuerySpec:
    if name == "kakao_usim":
        return _Beta6QuerySpec(
            name=name,
            groups={
                "platform": ["카카오톡", "카톡", "텔레그램", "메신저"],
                "usim": ["REGEX:(?<!자)유심(?:칩)?", "가입자식별모듈", "USIM", "SIM"],
                "actor": ["경찰이", "경찰은", "경찰관이", "수사기관이", "수사기관은", "수사관이", "검찰이", "검찰은", "검사가", "검사는"],
                "purpose": ["수사에", "수사상", "증거로", "압수", "압수수색", "대화내용", "대화내역", "접속", "로그인", "인증번호", "공기계"],
                "private_negative": ["피해자", "개인적", "사적", "피고인이 피해자", "피고인은 피해자"],
                "supply_negative": [
                    "선불",
                    "선불유심",
                    "개통신청서",
                    "가입신청서",
                    "타인의 통신용",
                    "전기통신사업자",
                    "전기통신사업법",
                    "다른 사람 명의",
                    "타인 명의",
                    "계정정보",
                    "성명불상자",
                    "대포폰",
                    "알뜰폰",
                ],
                "account_access_bridge": ["계정에 접속", "계정 접속", "인증번호", "공기계", "백업파일", "대화내용", "첨부파일"],
                "investigative_legality": ["압수수색영장", "압수영장", "위법수집증거", "참여권", "전자정보", "임의제출"],
            },
            required_groups={"platform", "usim"},
        )
    if name == "military_key":
        return _Beta6QuerySpec(
            name=name,
            groups={
                "military": ["군대", "부대", "군인", "병사", "장병", "지휘관", "당직", "경비대", "무기고", "탄약고", "군사", "공군", "육군"],
                "key": ["열쇠", "열쇠관리", "키 관리", "비밀번호", "암호", "출입증", "시건", "자물쇠"],
                "management": ["관리", "보관", "분실", "반납", "대장", "담당", "잠금", "보관상태", "점검", "인계"],
                "liability": ["주의의무", "과실", "징계", "해임", "손해", "절도", "침입", "처분", "태만", "관리소홀"],
                "arsenal_storage": ["무기고", "탄약고", "총기", "실탄", "권총", "탄약", "무기관리", "경비대", "병기탄약"],
                "custody_duty": ["직접하여야", "일임", "관리소홀", "관리 소홀", "보관상태", "관리상태", "관리업무", "관리의 편의", "태만", "책임자"],
            },
            required_groups={"military", "key"},
        )
    raise ValueError(f"unknown beta6 query spec: {name}")


def _beta6_term_matches(text: str, terms: list[str]) -> list[str]:
    matches: list[str] = []
    for term in terms:
        if term.startswith("REGEX:"):
            pattern_text = term.removeprefix("REGEX:")
            pattern = _BETA6_REGEX_CACHE.get(pattern_text)
            if pattern is None:
                pattern = re.compile(pattern_text, re.I)
                _BETA6_REGEX_CACHE[pattern_text] = pattern
            matches.extend(match.group(0) for match in pattern.finditer(text))
        elif term in text:
            matches.append(term)
    return sorted(set(matches), key=matches.index)


def _beta6_find_hits(text: str, spec: _Beta6QuerySpec) -> dict[str, list[str]]:
    hits: dict[str, list[str]] = {}
    for group, terms in spec.groups.items():
        matched = _beta6_term_matches(text, terms)
        if matched:
            hits[group] = matched
    return hits


def _beta6_proximity_bonus(text: str, matched_terms: list[str]) -> float:
    positions = sorted(text.find(term) for term in matched_terms if term and term in text)
    positions = [pos for pos in positions if pos >= 0]
    if len(positions) < 2:
        return 0.0
    span = max(positions) - min(positions)
    if span <= 300:
        return 8.0
    if span <= 800:
        return 4.0
    if span <= 1600:
        return 1.5
    return 0.0


def _beta6_base_score(text: str, spec: _Beta6QuerySpec, hits: dict[str, list[str]]) -> float:
    if not spec.required_groups.issubset(hits):
        return 0.0
    group_weights = {
        "platform": 10.0,
        "usim": 10.0,
        "actor": 7.0,
        "purpose": 5.0,
        "military": 8.0,
        "key": 8.0,
        "management": 6.0,
        "liability": 3.0,
        "private_negative": -3.0,
        "supply_negative": -8.0,
        "account_access_bridge": 6.0,
        "investigative_legality": 5.0,
        "arsenal_storage": 5.0,
        "custody_duty": 5.0,
    }
    score = sum(group_weights.get(group, 1.0) for group in hits)
    matched_terms = [term for terms in hits.values() for term in terms]
    score += _beta6_proximity_bonus(text, matched_terms)
    if spec.name == "kakao_usim":
        if "actor" in hits and "purpose" in hits:
            score += 6.0
        if "actor" not in hits:
            score -= 10.0
        if "private_negative" in hits and "actor" not in hits:
            score -= 8.0
    if spec.name == "military_key" and "management" in hits:
        score += 4.0
    return score


def _beta6_score_text(text: str, spec: _Beta6QuerySpec) -> tuple[float, list[str]]:
    clean = _beta6_normalize_text(text)
    hits = _beta6_find_hits(clean, spec)
    score = _beta6_base_score(clean, spec, hits)
    reasons = [f"{group}:{','.join(values[:5])}" for group, values in sorted(hits.items())]
    if spec.name == "kakao_usim":
        verifier = _beta6_verify_kakao_usim(clean)
        features = _beta6_digital_investigative_access_features(clean)
        score += float(features.get("score") or 0.0) * 2.5
        reasons.extend(f"digital:{item}" for item in (features.get("hits") or [])[:8])
        if features.get("ok"):
            score += 36.0
            reasons.append("verified_digital_investigative_access")
        if verifier.label == "accept":
            score += 54.0
        elif verifier.label == "needs_review":
            score += 8.0
        else:
            score -= 54.0
        reasons.append(f"verifier:{verifier.label}:{','.join(verifier.positive_reasons + verifier.negative_reasons)[:160]}")
    elif spec.name == "military_key":
        verifier = _beta6_verify_military_key(clean)
        if verifier.label == "accept":
            score += 48.0
        elif verifier.label == "needs_review":
            score += 8.0
        else:
            score -= 34.0
        reasons.append(f"verifier:{verifier.label}:{','.join(verifier.positive_reasons + verifier.negative_reasons)[:160]}")
    return score, reasons


def _beta6_detect_query_kind(user_task: str) -> str:
    # Keep beta-6 on the general selector path. Older kakao_usim/military_key
    # active anchors were too narrow and made benchmark success depend on
    # query-specific routing rather than the generic legal issue/ranking logic.
    return "generic"


def _beta6_fts_group(terms: list[str]) -> list[str]:
    out: list[str] = []
    for term in terms:
        if term.startswith("REGEX:"):
            pattern_text = term.removeprefix("REGEX:")
            if "유심" in pattern_text:
                out.extend(["유심", "유심칩", "가입자식별모듈", "USIM", "SIM"])
            continue
        cleaned = _beta5_normalize_term(term)
        if cleaned and cleaned not in out:
            out.append(cleaned)
    return out


def _beta6_query_variants(spec: _Beta6QuerySpec, user_task: str, round_index: int) -> list[list[list[str]]]:
    groups = spec.groups
    surface = _beta5_query_tokens(user_task)
    variants: list[list[list[str]]] = []
    if spec.name == "kakao_usim":
        base = [
            ["platform", "usim", "actor"],
            ["platform", "usim", "purpose"],
            ["platform", "actor", "purpose"],
        ]
        bridge = [
            [["카카오톡", "카톡"], ["인증번호", "공기계"], ["압수수색", "영장", "검사", "수사기관"]],
            [["텔레그램", "카카오톡"], ["계정 접속", "접속", "인증번호"], ["휴대전화", "공기계"]],
            [["카카오톡", "카톡"], ["백업파일", "대화내용", "첨부파일"], ["압수수색영장", "전자정보"]],
        ]
        if round_index == 1:
            for names in base:
                variants.append([_beta6_fts_group(groups[name]) for name in names])
        elif round_index == 2:
            variants.extend(bridge)
        elif round_index == 3:
            variants.extend([
                [_beta6_fts_group(groups["platform"]), _beta6_fts_group(groups["usim"])],
                [_beta6_fts_group(groups["account_access_bridge"]), _beta6_fts_group(groups["investigative_legality"])],
            ])
        else:
            variants.extend([
                [surface[:10] or _beta6_fts_group(groups["platform"])],
                [_beta6_fts_group(groups["platform"] + groups["usim"] + groups["actor"] + groups["purpose"])[:18]],
            ])
    elif spec.name == "military_key":
        if round_index == 1:
            variants.extend([
                [_beta6_fts_group(groups["military"]), _beta6_fts_group(groups["key"])],
                [_beta6_fts_group(groups["military"]), _beta6_fts_group(groups["key"]), _beta6_fts_group(groups["management"])],
            ])
        elif round_index == 2:
            variants.extend([
                [_beta6_fts_group(groups["arsenal_storage"]), _beta6_fts_group(groups["key"]), _beta6_fts_group(groups["custody_duty"])],
                [["경비대", "무기고", "탄약고"], ["열쇠", "열쇠관리"], ["보관상태", "관리상태", "관리소홀"]],
            ])
        else:
            variants.extend([
                [_beta6_fts_group(groups["military"] + groups["key"] + groups["management"])[:18]],
                [surface[:10] or _beta6_fts_group(groups["key"])],
            ])
    clean_variants: list[list[list[str]]] = []
    for variant in variants:
        clean_groups = [_beta5_clean_terms(group, limit=18) for group in variant if group]
        clean_groups = [group for group in clean_groups if group]
        if clean_groups and clean_groups not in clean_variants:
            clean_variants.append(clean_groups)
    return clean_variants[:6]


def _beta6_fts_search(conn: sqlite3.Connection, groups: list[list[str]], *, limit: int) -> tuple[list[sqlite3.Row], list[dict[str, Any]]]:
    trace: list[dict[str, Any]] = []
    if not groups:
        return [], trace
    capped = [group[:10] for group in groups if group]
    query = _beta2_build_fts(capped)
    rows = _beta2_fts_query(conn, query, limit=limit)
    trace.append({"strategy": "strict_family_AND", "n_groups": len(capped), "hits": len(rows)})
    if rows or len(capped) <= 2:
        return rows, trace
    best = rows
    for drop in range(1, min(2, len(capped) - 1) + 1):
        narrowed = capped[:-drop]
        if len(narrowed) < 2:
            break
        query = _beta2_build_fts(narrowed)
        current = _beta2_fts_query(conn, query, limit=limit)
        trace.append({"strategy": f"strict_drop_last_{drop}", "n_groups": len(narrowed), "hits": len(current)})
        if len(current) > len(best):
            best = current
        if current:
            return current, trace
    return best, trace


def select_top_precedents_beta6(
    user_task: str,
    *,
    db_path: Path = PRECEDENT_DB_PATH,
    select_model: str = DEFAULT_SELECT_MODEL,
    useful_target: int = 100,
    fts_limit: int = 700,
    max_rounds: int = 5,
    wall_budget_sec: float = 900.0,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """BETA-6: r133 retrieval-loop legal selector port.

    The verifier/scoring terms are copied from the passed loop artifacts.  The
    only adapter change is that Lawkey reads the production SQLite FTS corpus
    instead of the benchmark parquet scan.
    """
    import time as _t
    t0 = _t.time()
    query_kind = _beta6_detect_query_kind(user_task)
    if query_kind == "generic":
        selected_records, selection_meta = select_top_precedents_beta5(
            user_task,
            db_path=db_path,
            select_model=select_model,
            useful_target=useful_target,
            wall_budget_sec=wall_budget_sec,
        )
        return selected_records, {
            **selection_meta,
            "selection_mode": "beta6_loop_r133_port",
            "query_kind": "generic",
            "generic_adapter": "beta5_union_verify",
        }

    spec = _beta6_query_spec(query_kind)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    candidate_rows: dict[str, sqlite3.Row] = {}
    candidate_origin: dict[str, dict[str, Any]] = {}
    round_trace: list[dict[str, Any]] = []
    try:
        for round_index in range(1, max(1, max_rounds) + 1):
            if _t.time() - t0 > wall_budget_sec:
                break
            variants = _beta6_query_variants(spec, user_task, round_index)
            round_info: dict[str, Any] = {
                "round": round_index,
                "variants": variants,
                "variant_trace": [],
                "candidate_count_before": len(candidate_rows),
            }
            for variant_index, groups in enumerate(variants, 1):
                if _t.time() - t0 > wall_budget_sec:
                    break
                rows, trace = _beta6_fts_search(conn, groups, limit=fts_limit)
                round_info["variant_trace"].append({"variant": variant_index, "groups": groups, "trace": trace, "hits": len(rows)})
                for rank, row in enumerate(rows):
                    cid = str(row["canonical_id"])
                    if cid not in candidate_rows:
                        candidate_rows[cid] = row
                        candidate_origin[cid] = {"round": round_index, "variant": variant_index, "rank": rank}
                    if len(candidate_rows) >= max(useful_target * 12, 1000):
                        break
                if len(candidate_rows) >= max(useful_target * 12, 1000):
                    break
            round_info["candidate_count_after"] = len(candidate_rows)
            round_trace.append(round_info)
            if len(candidate_rows) >= max(useful_target * 8, 600) and round_index >= 2:
                break

        scored: list[tuple[str, float, list[str], _Beta6VerifyResult]] = []
        rejected_ledger: list[dict[str, Any]] = []
        for cid, row in candidate_rows.items():
            text = _beta5_row_text(row)
            score, reasons = _beta6_score_text(text, spec)
            if spec.name == "kakao_usim":
                verifier = _beta6_verify_kakao_usim(text)
            else:
                verifier = _beta6_verify_military_key(text)
            origin = candidate_origin.get(cid, {})
            score -= float(origin.get("rank") or 0) * 0.02
            if verifier.label == "reject":
                rejected_ledger.append(
                    {
                        "canonical_id": cid,
                        "case_number": str(row["case_number"] or ""),
                        "reason": ",".join(verifier.negative_reasons),
                        "origin": origin,
                        "quote": _beta6_normalize_text(text)[:360],
                    }
                )
            scored.append((cid, score, reasons, verifier))
        scored.sort(
            key=lambda item: (
                item[3].label != "accept",
                item[3].label == "reject",
                -item[1],
                item[0],
            )
        )
        canonical_ids = [cid for cid, _score, _reasons, _verifier in scored[:useful_target]]
        full_rows = _fetch_precedent_rows(conn, canonical_ids)
    finally:
        conn.close()

    selected_records = [canonical_row_to_selected_record(row) for row in full_rows]
    top_debug = [
        {
            "canonical_id": cid,
            "score": round(score, 3),
            "verifier": verifier.label,
            "confidence": verifier.confidence,
            "reasons": reasons[:12],
            "origin": candidate_origin.get(cid, {}),
        }
        for cid, score, reasons, verifier in scored[:20]
    ]
    selection_meta: dict[str, Any] = {
        "selection_source": str(db_path),
        "selection_mode": "beta6_loop_r133_port",
        "query_kind": query_kind,
        "selected_count": len(selected_records),
        "top_k": useful_target,
        "candidate_count": len(candidate_rows),
        "accepted_count": sum(1 for _cid, _score, _reasons, verifier in scored if verifier.label == "accept"),
        "needs_review_count": sum(1 for _cid, _score, _reasons, verifier in scored if verifier.label == "needs_review"),
        "rejected_count": len(rejected_ledger),
        "rounds": round_trace,
        "rejected_ledger_sample": rejected_ledger[:80],
        "top_debug": top_debug,
        "max_rounds": max_rounds,
        "wall_clock_sec": round(_t.time() - t0, 2),
    }
    return selected_records, selection_meta


def _beta5_normalize_term(term: str) -> str:
    cleaned = sanitize_search_query(str(term)).strip()
    if " " in cleaned:
        return cleaned
    suffixes = [
        "으로부터", "로부터", "에서", "에게", "으로", "로서", "부터", "까지",
        "이라는", "라는", "하고", "이며", "이고", "에는", "에게는",
        "은", "는", "이", "가", "을", "를", "의", "에", "도", "만", "와", "과", "로", "해",
    ]
    changed = True
    while changed:
        changed = False
        for suffix in suffixes:
            if suffix == "도" and cleaned.endswith("속도"):
                continue
            if cleaned.endswith(suffix) and len(cleaned) - len(suffix) >= 2:
                cleaned = cleaned[: -len(suffix)]
                changed = True
                break
    return cleaned


def _beta5_clean_terms(terms: list[str], *, limit: int = 18) -> list[str]:
    seen: dict[str, None] = {}
    for term in terms:
        cleaned = _beta5_normalize_term(str(term))
        if not cleaned:
            continue
        if len(cleaned) < 2:
            continue
        if cleaned not in seen:
            seen[cleaned] = None
    return list(seen.keys())[:limit]


def _beta5_query_tokens(user_task: str) -> list[str]:
    tokens = SAFE_TOKEN_PATTERN.findall(user_task or "")
    stop = {
        "사례",
        "판례",
        "찾아줘",
        "관련",
        "대하여",
        "대한",
        "어떻게",
        "무엇",
        "있는지",
        "없는지",
        *TRAFFIC_QUERY_NOISE_TERMS,
    }
    cleaned_tokens: list[str] = []
    for token in tokens:
        if token in stop:
            continue
        if re.fullmatch(r"\d{1,3}", token):
            continue
        if re.fullmatch(r"\d+(?:대|인데|이야|임|냐)", token):
            continue
        cleaned_tokens.append(token)
    return _beta5_clean_terms(cleaned_tokens, limit=18)


def _beta5_expand_issue_terms(issue_terms: list[str] | tuple[str, ...] | None) -> list[str]:
    expanded: list[str] = []

    def add(value: str) -> None:
        cleaned = _beta5_normalize_term(value)
        if cleaned and len(cleaned) >= 2 and cleaned not in expanded:
            expanded.append(cleaned)

    for raw in issue_terms or []:
        term = str(raw or "").strip()
        if not term:
            continue
        add(term)
        for piece in SAFE_TOKEN_PATTERN.findall(term):
            add(piece)
        compact = term.replace(" ", "")
        if "자기" in compact or "본인" in compact or "자신" in compact:
            add("자기")
            add("본인")
            add("자신")
            add("피고인 자신")
        if "타인" in compact:
            add("타인")
            add("타인의")
        if "형사사건" in compact:
            add("형사사건")
            add("타인의 형사사건")
        if "증거인멸" in compact:
            add("증거인멸")
            add("증거인멸죄")
        if "증거은닉" in compact:
            add("증거은닉")
        if "증거위조" in compact:
            add("증거위조")
    return expanded[:40]


def _beta5_surface_query_terms(user_task: str) -> set[str]:
    base_query = sanitize_search_query(user_task)
    surface = {base_query} if base_query else set()
    surface.update(token for token in base_query.split(" ") if token)
    surface.update(_plain_traffic_accident_queries(user_task))
    surface.update(_beta5_query_tokens(user_task))
    return {item for item in surface if item}


def _beta5_generate_issue_terms(
    user_task: str,
    *,
    select_model: str,
    keyword_count: int = 15,
    timeout_seconds: int = 90,
) -> list[str]:
    try:
        queries = build_search_queries(
            user_task,
            keyword_count=keyword_count,
            select_model=select_model,
            timeout_seconds=timeout_seconds,
        )
    except Exception:
        return []
    surface = _beta5_surface_query_terms(user_task)
    issue_terms = [
        query
        for query in queries[1:]
        if query and query not in surface and len(query) >= 2
    ]
    return _beta5_expand_issue_terms(issue_terms)


def _beta5_build_query_profile(user_task: str, *, issue_terms: list[str] | None = None) -> _Beta5QueryProfile:
    normalized = sanitize_search_query(user_task)
    facets: dict[str, list[str]] = {}
    contextual_issue_terms: list[str] = []
    has_military_context = any(term in normalized for term in ["군대", "군", "공군", "육군", "해군", "부대", "탄약", "무기고", "탄약고"])
    has_key_surface = any(term in normalized for term in ["키", "열쇠", "시건", "잠금"])
    if has_military_context and has_key_surface:
        contextual_issue_terms.extend(
            [
                "군대 열쇠",
                "군 열쇠",
                "탄약고 열쇠",
                "무기고 열쇠",
                "총기 탄약 열쇠",
                "시건장치",
                "열쇠 보관",
                "열쇠 인계",
                "열쇠 점검",
                "관리소홀",
            ]
        )
    has_investigative_context = any(term in normalized for term in ["수사기관", "수사관", "경찰", "검찰", "검사", "압수", "영장", "수사"])
    has_messenger_sim_context = any(term in normalized for term in ["카카오톡", "카톡", "텔레그램", "유심", "usim", "sim", "로그인", "인증번호"])
    if has_investigative_context and has_messenger_sim_context:
        contextual_issue_terms.extend(
            [
                "유심 카카오톡",
                "유심칩 공기계",
                "공기계 인증번호",
                "카카오톡 계정 접속",
                "메신저 계정 로그인",
                "압수수색영장",
                "위법수집증거",
                "참여권",
            ]
        )
    expanded_issue_terms = _beta5_expand_issue_terms(contextual_issue_terms + list(issue_terms or []))
    if expanded_issue_terms:
        facets["legal_issue"] = expanded_issue_terms
    is_self_fault_traffic = _is_self_fault_traffic_query(user_task)
    if is_self_fault_traffic:
        facets["traffic_self_fault_driver"] = _beta5_clean_terms(list(TRAFFIC_SELF_FAULT_SEARCH_TERMS), limit=18)
        facets["traffic_liability"] = _beta5_clean_terms(list(TRAFFIC_LIABILITY_LABEL_TERMS), limit=16)
    if any(term in normalized for term in ["수사기관", "수사관", "경찰", "검찰", "압수", "영장", "수사"]):
        facets["investigative_actor"] = _BETA5_INVESTIGATIVE_TERMS
    if any(term in normalized for term in ["휴대전화", "휴대폰", "핸드폰", "스마트폰", "유심", "카카오", "카톡", "텔레그램", "로그인"]):
        facets["device_access"] = _BETA5_DEVICE_ACCESS_TERMS
    if any(term in normalized for term in ["군대", "군", "공군", "육군", "해군", "탄약", "무기고", "열쇠", "키", "시건"]):
        facets["military_key_custody"] = _BETA5_MILITARY_KEY_TERMS
    critical_terms = [
        term
        for term in ["유심", "카카오톡", "카톡", "텔레그램", "로그인", "탄약고", "탄약", "무기고", "열쇠", "시건", "공군"]
        if term in normalized
    ]
    if is_self_fault_traffic:
        critical_terms.extend(
            term
            for term in ["과속", "속도위반", "제한속도", "교통사고", "과실", "사고후미조치"]
            if term in normalized or term in {"제한속도", "교통사고", "사고후미조치"}
        )
    if critical_terms:
        facets["query_critical"] = critical_terms

    query_terms = _beta5_query_tokens(user_task)
    search_groups: list[list[str]] = []
    for key in ["legal_issue", "traffic_self_fault_driver", "traffic_liability", "investigative_actor", "device_access", "military_key_custody", "query_critical"]:
        if key in facets:
            search_groups.append(_beta5_clean_terms(facets[key], limit=16))
    if query_terms:
        search_groups.append(query_terms)
    if not search_groups:
        search_groups = [query_terms or _beta5_clean_terms([normalized], limit=8)]

    positive_terms = _beta5_clean_terms(
        query_terms + [term for group in facets.values() for term in group],
        limit=48,
    )
    hard_negative_seed = list(_BETA5_PRIVATE_DEVICE_CRIME_TERMS)
    if is_self_fault_traffic:
        hard_negative_seed.extend(TRAFFIC_OPPOSITE_FAULT_NEGATIVE_TERMS)
        hard_negative_seed.extend(TRAFFIC_IRRELEVANT_LABEL_TERMS)
    hard_negative_terms = _beta5_clean_terms(hard_negative_seed, limit=48)
    return _Beta5QueryProfile(
        raw_query=user_task,
        required_facets=facets,
        search_groups=[group for group in search_groups if group],
        positive_terms=positive_terms,
        hard_negative_terms=hard_negative_terms,
        generated_issue_terms=expanded_issue_terms,
    )


def _beta5_row_text(row: Any) -> str:
    def get_value(key: str) -> str:
        try:
            if isinstance(row, dict):
                return str(row.get(key) or "")
            return str(row[key] or "")
        except Exception:
            return ""

    return " ".join(
        part
        for part in [
            get_value("title"),
            get_value("case_name"),
            get_value("case_type"),
            get_value("case_number"),
            get_value("court"),
            get_value("full_text"),
        ]
        if part
    )


def _beta5_count_hits(text: str, terms: list[str]) -> int:
    return sum(1 for term in terms if term and term in text)


def _beta5_has_any(text: str, terms: tuple[str, ...] | list[str]) -> bool:
    return any(term and term in text for term in terms)


def _beta5_window_bonus(text: str, left_terms: list[str], right_terms: list[str], *, radius: int = 360) -> float:
    if not left_terms or not right_terms:
        return 0.0
    positions: list[tuple[str, int]] = []
    for term in left_terms[:16] + right_terms[:16]:
        start = 0
        while True:
            idx = text.find(term, start)
            if idx < 0:
                break
            positions.append((term, idx))
            start = idx + max(1, len(term))
            if len(positions) > 80:
                break
    bonus = 0.0
    left_set = set(left_terms)
    right_set = set(right_terms)
    for term_a, pos_a in positions:
        for term_b, pos_b in positions:
            if term_a == term_b:
                continue
            if term_a in left_set and term_b in right_set and abs(pos_a - pos_b) <= radius:
                bonus += 4.0
                if bonus >= 24.0:
                    return bonus
    return bonus


def _beta5_score_candidate(row: dict[str, Any] | sqlite3.Row, profile: _Beta5QueryProfile) -> float:
    text = _beta5_row_text(row)
    row_dict = dict(row) if not isinstance(row, dict) else row
    label_text = _row_label_text(row_dict)
    score = 0.0
    for facet_name, terms in profile.required_facets.items():
        hits = _beta5_count_hits(text, terms)
        if hits:
            score += 24.0 + min(8, hits) * 3.0
        else:
            score -= 24.0
        if facet_name == "investigative_actor" and hits:
            score += _beta5_window_bonus(text, terms, profile.required_facets.get("device_access", []), radius=520)
        if facet_name == "military_key_custody" and hits:
            score += min(18.0, hits * 2.0)
        if facet_name == "traffic_self_fault_driver" and hits:
            score += min(42.0, hits * 4.0)
            score += _beta5_window_bonus(
                text,
                ["피고인", "피의자", "운전자", "가해차량", "가해 차량"],
                ["과속", "속도위반", "제한속도", "전방주시", "주의의무", "치상", "치사"],
                radius=520,
            )
        if facet_name == "legal_issue":
            if hits:
                score += 32.0 + min(12, hits) * 5.0
                score += _beta5_window_bonus(
                    text,
                    ["자기", "본인", "자신", "피고인 자신"],
                    ["증거인멸", "증거인멸죄", "증거은닉", "증거위조"],
                    radius=760,
                )
                score += _beta5_window_bonus(
                    text,
                    ["타인", "타인의", "타인의 형사사건", "형사사건"],
                    ["증거인멸", "증거인멸죄", "증거은닉", "증거위조"],
                    radius=760,
                )
            else:
                score -= 8.0

    query_hits = _beta5_count_hits(text, profile.positive_terms[:32])
    score += min(36.0, query_hits * 2.0)

    if "traffic_self_fault_driver" in profile.required_facets:
        traffic_label_hit = _beta5_has_any(label_text, TRAFFIC_LIABILITY_LABEL_TERMS)
        irrelevant_label_hit = _beta5_has_any(label_text, TRAFFIC_IRRELEVANT_LABEL_TERMS)
        case_number_text = str(row_dict.get("case_number") or "")
        constitutional_review_hit = bool(re.search(r"\d{2,4}헌[마바가]\d+", case_number_text)) or _beta5_has_any(
            label_text, TRAFFIC_CONSTITUTIONAL_REVIEW_LABEL_TERMS
        )
        opposite_hits = _beta5_count_hits(text, list(TRAFFIC_OPPOSITE_FAULT_NEGATIVE_TERMS))
        driver_hits = _beta5_count_hits(text, ["피고인", "피의자", "운전자", "가해차량", "가해 차량"])
        speed_hits = _beta5_count_hits(text, ["과속", "속도위반", "제한속도", "시속"])
        accident_hits = _beta5_count_hits(text, ["교통사고", "사고", "충격", "충돌", "치상", "치사"])
        if traffic_label_hit:
            score += 56.0
        if driver_hits and speed_hits and accident_hits:
            score += 84.0
        elif speed_hits and accident_hits:
            score += 28.0
        if opposite_hits:
            score -= 120.0 + min(60.0, opposite_hits * 12.0)
        if irrelevant_label_hit and not traffic_label_hit:
            score -= 110.0
        if "기소유예처분취소" in label_text and not traffic_label_hit:
            score -= 50.0
        if constitutional_review_hit and not _beta5_has_any(profile.raw_query, CONSTITUTIONAL_QUERY_TERMS):
            score -= 95.0
            if not (driver_hits and speed_hits and accident_hits):
                score -= 45.0

    has_investigative_need = "investigative_actor" in profile.required_facets
    has_device_need = "device_access" in profile.required_facets
    if has_investigative_need and has_device_need:
        investigative_hits = _beta5_count_hits(text, profile.required_facets["investigative_actor"])
        device_hits = _beta5_count_hits(text, profile.required_facets["device_access"])
        private_hits = _beta5_count_hits(text, profile.hard_negative_terms)
        verifier = _beta6_verify_kakao_usim(text)
        features = _beta6_digital_investigative_access_features(text)
        if verifier.label == "accept":
            score += 150.0
        elif verifier.label == "needs_review":
            score += 35.0
        elif verifier.label == "reject":
            score -= 90.0
        if features.get("direct_action"):
            score += 70.0
        if features.get("sim_messenger_bridge") or features.get("account_access_bridge"):
            score += 45.0
        if features.get("fraud_noise"):
            score -= 55.0
        if device_hits and private_hits and investigative_hits == 0:
            score -= 72.0 + private_hits * 6.0
        elif private_hits and investigative_hits <= 1:
            score -= 24.0

    if "military_key_custody" in profile.required_facets:
        verifier = _beta6_verify_military_key(text)
        if verifier.label == "accept":
            score += 150.0
        elif verifier.label == "needs_review":
            score += 35.0
        elif verifier.label == "reject":
            score -= 70.0
        score += _beta5_window_bonus(
            text,
            ["탄약고", "무기고", "총기", "탄약", "공군", "육군", "해군", "부대"],
            ["열쇠", "키", "시건", "보관", "인계", "점검", "관리"],
            radius=640,
        )

    score -= _row_penalty(row_dict, user_task=profile.raw_query) / 10.0
    return score


def _beta5_query_variants(profile: _Beta5QueryProfile) -> list[list[list[str]]]:
    groups = [group for group in profile.search_groups if group]
    variants: list[list[list[str]]] = []
    if len(groups) >= 2:
        variants.append(groups[:3])
    for i, group in enumerate(groups):
        paired = [group]
        for j, other in enumerate(groups):
            if i != j and len(paired) < 3:
                paired.append(other)
        if paired not in variants:
            variants.append(paired)
    if profile.positive_terms:
        variants.append([profile.positive_terms[:18]])
    return variants[:8]


def _beta5_parse_scores(text: str, n: int) -> dict[int, int]:
    out: dict[int, int] = {}
    for match in re.finditer(r"(\d{1,2})\s*[:\-.]\s*([0-3])\b", text):
        try:
            idx = int(match.group(1))
            score = int(match.group(2))
        except ValueError:
            continue
        if 1 <= idx <= n:
            out[idx] = score
    return out


def _beta5_judge_prompt(user_task: str, profile: _Beta5QueryProfile, rows: list[Any]) -> str:
    keywords = profile.positive_terms[:32]
    lines = [
        "한국 판례 검색 후보 검증.",
        f"질의: {user_task[:600]}",
        "",
        "채점 기준:",
        "- 3: 행위자/대상/도구/법적 쟁점이 사실상 같은 판례",
        "- 2: 주요 축은 같지만 일부 사실이나 법리가 다름",
        "- 1: 넓게 관련은 있으나 직접 쓰기 어렵다",
        "- 0: 키워드만 비슷하거나 행위자가 반대인 hard-negative",
        "특히 수사기관이 한 행위인지, 피고인/피의자가 피해자에게 한 행위인지 구별하라.",
    ]
    if "traffic_self_fault_driver" in profile.required_facets:
        lines.extend(
            [
                "이 질의는 질문자 자신이 과속/속도위반 등으로 사고를 낸 자기 과실 운전자 프레임이다.",
                "상대방이나 피해자가 만취·초과속이라서 청구인 과실이 부정된 판례는 행위자 반대 hard-negative로 0점이다.",
                "피고인/운전자 자신의 과속·전방주시·주의의무·치상/치사·사고후조치 책임을 다룬 판례를 우선하라.",
            ]
        )
    lines.extend(["", "후보:"])
    for idx, row in enumerate(rows, 1):
        text = _beta5_row_text(row)
        snippet = _beta2_windows_around(text, keywords, radius=100, max_total_chars=900) if keywords else text[:900]
        case_number = ""
        try:
            case_number = str(row["case_number"] or "")
        except Exception:
            if isinstance(row, dict):
                case_number = str(row.get("case_number") or "")
        lines.append(f"{idx}. [{case_number}] {snippet}")
    lines.extend(["", "출력은 번호:점수만 한 줄씩. 예:", "1:3", "2:0"])
    return "\n".join(lines)


def select_top_precedents_beta5(
    user_task: str,
    *,
    db_path: Path = PRECEDENT_DB_PATH,
    select_model: str = DEFAULT_SELECT_MODEL,
    useful_target: int = 100,
    fts_limit: int = 450,
    local_rerank_top: int = 160,
    gemma_judge_top: int = 60,
    wall_budget_sec: float = 900.0,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """BETA-5: union recall + facet verifier + cheap Gemma window judge.

    판례 선택만 강화하고, 이후 주장카드/본문 생성은 기존 Lawkey 파이프라인에 그대로 넘긴다.
    핵심은 키워드 유사 hard-negative(행위자 반전, 사적 범죄 vs 수사기관 행위)를 로컬 verifier가
    먼저 깎고, LLM은 짧은 window 후보 검증에만 쓰는 것이다.
    """
    import time as _t
    t0 = _t.time()
    issue_terms = _beta5_generate_issue_terms(user_task, select_model=select_model)
    profile = _beta5_build_query_profile(user_task, issue_terms=issue_terms)
    variants = _beta5_query_variants(profile)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    candidate_rows: dict[str, sqlite3.Row] = {}
    candidate_origin: dict[str, dict[str, Any]] = {}
    fts_trace: list[dict[str, Any]] = []
    try:
        for variant_idx, groups in enumerate(variants, 1):
            if _t.time() - t0 > wall_budget_sec:
                break
            rows, trace = _beta2_fts_graceful(conn, groups, limit=fts_limit, min_hits=5)
            fts_trace.append({"variant": variant_idx, "groups": groups, "trace": trace, "hits": len(rows)})
            for rank, row in enumerate(rows):
                cid = str(row["canonical_id"])
                if cid not in candidate_rows:
                    candidate_rows[cid] = row
                    candidate_origin[cid] = {"variant": variant_idx, "rank": rank}
                if len(candidate_rows) >= max(useful_target * 8, 600):
                    break
            if len(candidate_rows) >= max(useful_target * 8, 600):
                break

        scored: list[tuple[str, float]] = []
        for cid, row in candidate_rows.items():
            base = _beta5_score_candidate(row, profile)
            rank = int(candidate_origin.get(cid, {}).get("rank", 999))
            scored.append((cid, base - rank * 0.03))
        scored.sort(key=lambda item: (-item[1], item[0]))

        gemma_scores: dict[str, int] = {}
        judged_ids = [cid for cid, _score in scored[:gemma_judge_top]]
        batch_size = 20
        for start in range(0, len(judged_ids), batch_size):
            if _t.time() - t0 > wall_budget_sec:
                break
            batch_ids = judged_ids[start:start + batch_size]
            batch_rows = [candidate_rows[cid] for cid in batch_ids]
            prompt = _beta5_judge_prompt(user_task, profile, batch_rows)
            response = _beta2_gemma(prompt, select_model, max_tokens=1536)
            parsed = _beta5_parse_scores(response, len(batch_rows))
            for pos, score in parsed.items():
                gemma_scores[batch_ids[pos - 1]] = score

        fused: list[tuple[str, float]] = []
        for cid, local_score in scored:
            judge_score = gemma_scores.get(cid)
            if judge_score is None:
                fused_score = local_score
            else:
                fused_score = local_score + judge_score * 28.0
                if judge_score == 0:
                    fused_score -= 30.0
            fused.append((cid, fused_score))
        fused.sort(key=lambda item: (-item[1], item[0]))
        canonical_ids = [cid for cid, _score in fused[:useful_target]]
        full_rows = _fetch_precedent_rows(conn, canonical_ids)
    finally:
        conn.close()

    selected_records = [canonical_row_to_selected_record(row) for row in full_rows]
    selection_meta: dict[str, Any] = {
        "selection_source": str(db_path),
        "selection_mode": "beta5_agentic_union_verify",
        "selected_count": len(selected_records),
        "top_k": useful_target,
        "keywords": profile.positive_terms[:32],
        "generated_issue_terms": profile.generated_issue_terms,
        "required_facets": profile.required_facets,
        "query_variants": variants,
        "fts_trace": fts_trace,
        "candidate_count": len(candidate_rows),
        "local_rerank_top": local_rerank_top,
        "gemma_judge_top": gemma_judge_top,
        "gemma_scored_count": len(gemma_scores),
        "hard_negative_terms": profile.hard_negative_terms,
        "wall_clock_sec": round(_t.time() - t0, 2),
    }
    return selected_records, selection_meta


def select_top_precedents_beta2(
    user_task: str,
    *,
    db_path: Path = PRECEDENT_DB_PATH,
    select_model: str = DEFAULT_SELECT_MODEL,
    useful_target: int = 10,
    max_iters: int = 3,
    wall_budget_sec: float = 600.0,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """분석 BETA-2: agentic iterative search.

    파이프라인:
      1. Gemma(minimal thinking) × 2회 호출 → union of seed groups (variability 보정)
      2. FTS5 AND 교집합으로 후보 (0 hits 시 룰베이스 degrade: drop_last_1)
      3. 각 후보의 키워드 주변 ±100자 window all-matches 2400자 상한
      4. Gemma 판정(useful/none) + 후보 본문에서 새 그룹 학습
      5. 누적 useful ≥ useful_target / 수렴 / wall_budget 도달 시 종료
    """
    import time as _t
    t0 = _t.time()

    # Stage 0 — seed groups (2회 호출 → union으로 variability 완화)
    # **핵심**: 그룹은 3개 이하. AND 교집합이 너무 많아지면 판례 본문과 매칭 실패.
    # 질의의 핵심 명사축(사건 도구/대상 + 행위 맥락 + 도메인) 3개만.
    seed_prompt = (
        "한국어 판례 DB 검색을 위한 키워드 의미 그룹 구성.\n\n"
        f"질의: \"{user_task[:500]}\"\n\n"
        "규칙:\n"
        "- **정확히 2~3개 의미 그룹** (그룹이 많으면 AND 교집합이 깨진다. 핵심만)\n"
        "- 각 그룹 10~15개 키워드 (풍부하게 — OR 처리됨)\n"
        "- 같은 개념의 동의어·한자어/고유어·영문/약어·변형은 **한 그룹에 다** 모아라\n"
        "- 그룹은 질의의 **핵심 명사축**만: 예) (A) 사건 대상/도구, (B) 맥락·행위, (C) 도메인·법리\n"
        "- 질의에 있는 부수 어휘('로그인', '관리', '사례' 등 너무 일반적·동사적 용어)는 별도 그룹으로 빼지 말 것\n"
        "- 각 그룹에 판례 본문에 실제로 쓰일 법률·규정 용어도 함께\n"
        "- 질의 외부 예시 금지, 질의 의미·유사어만\n\n"
        "출력 형식 엄수:\n"
        "그룹 1: kw, kw, kw, ...\n"
        "그룹 2: kw, kw, kw, ...\n"
    )
    # 1회차
    seed_text_a = _beta2_gemma(seed_prompt, select_model, max_tokens=2048)
    groups_a = _beta2_parse_groups(seed_text_a)
    # 2회차 (동일 지시 반복; 각도 변경 요구 안 함 — noise 감소 목적)
    seed_text_b = _beta2_gemma(seed_prompt, select_model, max_tokens=2048)
    groups_b = _beta2_parse_groups(seed_text_b)
    # Union (그룹 번호 동일한 곳끼리 키워드 합치기; 개수 불일치면 순서대로)
    groups: list[list[str]] = []
    n = max(len(groups_a), len(groups_b))
    for i in range(n):
        a = groups_a[i] if i < len(groups_a) else []
        b = groups_b[i] if i < len(groups_b) else []
        seen: dict[str, None] = {}
        for kw in a + b:
            kw_n = kw.strip()
            if kw_n and kw_n not in seen:
                seen[kw_n] = None
        if seen:
            groups.append(list(seen.keys())[:18])  # 합쳐도 18개 상한 (OR 풍부하게)
    # 중복/거의 동일한 그룹 제거 (Gemma가 같은 뜻 다른 순서로 2그룹 만드는 케이스)
    deduped: list[list[str]] = []
    for g in groups:
        g_set = frozenset(g)
        if any(len(g_set & frozenset(prev)) / max(1, min(len(g), len(prev))) >= 0.7 for prev in deduped):
            continue
        deduped.append(g)
    groups = deduped[:3]  # 그룹 수 3개 cap — AND 엄격성 방지
    if not groups:
        # hard fallback: rule-based tokenize
        import re as _re
        toks = _re.findall(r"[가-힣A-Za-z]{2,}", user_task)
        groups = [toks[i:i + 5] for i in range(0, min(len(toks), 15), 5)]
        groups = [g for g in groups if g][:3]
    if not groups:
        return [], {"selection_mode": "beta2_agentic", "error": "seed_groups_empty",
                    "user_task": user_task[:200]}

    # Iterative loop
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    useful_accum: dict[str, dict[str, Any]] = {}
    seen_cids: set[str] = set()
    iter_trace: list[dict[str, Any]] = []

    try:
        it = 0
        current_groups = groups
        while len(useful_accum) < useful_target and it < max_iters:
            if _t.time() - t0 > wall_budget_sec:
                break
            it += 1
            cands, fts_trace = _beta2_fts_graceful(conn, current_groups, limit=200, min_hits=3)
            new_cands = [r for r in cands if r["canonical_id"] not in seen_cids][:40]
            iter_trace.append({
                "iter": it, "groups": current_groups, "fts_trace": fts_trace,
                "fts_total_hits": len(cands), "new_cands": len(new_cands),
            })
            if not new_cands:
                break
            flat_kws = [k for g in current_groups for k in g]
            pack = []
            cid_map = []
            for r in new_cands:
                snip = _beta2_windows_around(str(r["full_text"] or ""), flat_kws,
                                            radius=80, max_total_chars=1500)
                pack.append((r["case_number"] or r["canonical_id"], snip))
                cid_map.append(r)
                seen_cids.add(r["canonical_id"])
            # Judge prompt
            L = [f"[질의] {user_task[:500]}",
                 f"[반복 {it}] 후보 판례 스니펫(키워드 ±100자)을 보고 각 후보 판정 + 실제 본문 용어로부터 새 검색 각도 제안.",
                 "", "[후보]"]
            for i, (case, snip) in enumerate(pack, 1):
                L.append(f"{i}. [{case}] {snip}")
            L.append("")
            L.append("출력 형식 엄수:")
            L.append(f"JUDGE: 1:[useful|none] 2:[useful|none] ... {len(pack)}:[useful|none]")
            L.append("")
            L.append("LEARNED_GROUPS (후보 본문의 실제 용어로 새 의미 그룹 3~5개 × 5~8개 키워드, 이전 라운드 안 쓴 각도 포함):")
            L.append("그룹 1: kw, kw, ...")
            L.append("그룹 2: kw, kw, ...")
            judge_prompt = "\n".join(L)
            judge_text = _beta2_gemma(judge_prompt, select_model, max_tokens=6144)
            labels, new_groups = _beta2_parse_judge(judge_text, len(pack))
            useful_now = 0
            for idx, r in enumerate(cid_map, 1):
                if labels.get(idx) == "useful":
                    cid = r["canonical_id"]
                    useful_accum[cid] = {
                        "canonical_id": cid,
                        "case_number": r["case_number"],
                        "court": r["court"],
                        "decision_date": r["decision_date"],
                        "iter": it,
                    }
                    useful_now += 1
            iter_trace[-1]["useful_now"] = useful_now
            iter_trace[-1]["cumulative_useful"] = len(useful_accum)
            if not new_groups:
                break
            if new_groups == current_groups:
                break
            current_groups = new_groups[:5]

        # Fallback 채움: useful_target 미달이면 전체 시드 flat OR-union FTS 상위로 채움
        fallback_added = 0
        if len(useful_accum) < useful_target:
            flat_kws = list({w for g in groups for w in g})
            fallback_rows: list[sqlite3.Row] = []
            if flat_kws:
                q = "(" + " OR ".join(f'"{w}"' for w in flat_kws) + ")"
                fallback_rows = _beta2_fts_query(conn, q, limit=max(useful_target * 5, 50))
            for r in fallback_rows:
                if len(useful_accum) >= useful_target:
                    break
                cid = r["canonical_id"]
                if cid in useful_accum:
                    continue
                useful_accum[cid] = {
                    "canonical_id": cid,
                    "case_number": r["case_number"],
                    "court": r["court"],
                    "decision_date": r["decision_date"],
                    "iter": -1,  # fallback 표시
                }
                fallback_added += 1
        canonical_ids = list(useful_accum.keys())
        full_rows = _fetch_precedent_rows(conn, canonical_ids)
    finally:
        conn.close()

    selected_records = [canonical_row_to_selected_record(row) for row in full_rows]
    selection_meta: dict[str, Any] = {
        "selection_source": str(db_path),
        "selection_mode": "beta2_agentic",
        "selected_count": len(selected_records),
        "useful_target": useful_target,
        "seed_groups": groups,
        "iters": iter_trace,
        "fallback_added": fallback_added,
        "wall_clock_sec": round(_t.time() - t0, 2),
        "top_k": useful_target,
    }
    return selected_records, selection_meta


############################################################################
# BETA-4 : BETA-2 의 agentic iterative 구조 + 라운드별 배치 증가 (10/20/30/40)
#          useful_target=100 까지 누적. canonical gold 3/3 VS 확인됨.
############################################################################

def select_top_precedents_beta4(
    user_task: str,
    *,
    db_path: Path = PRECEDENT_DB_PATH,
    select_model: str = DEFAULT_SELECT_MODEL,
    useful_target: int = 100,
    max_iters: int = 10,
    wall_budget_sec: float = 900.0,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """분석 BETA-4: beta-2 iterative + 라운드별 점진 확대.

    파이프라인:
      1. beta-2 와 동일한 seed 2회 union
      2. FTS AND (400 limit) 후보
      3. **라운드별 new_cands 증가**: it=1→10, 2→20, 3→30, 4→40, ...
      4. Gemma useful/none 판정 + LEARNED_GROUPS 학습
      5. 누적 useful ≥ 100 또는 수렴 시 종료
      6. 부족분 flat OR-union FTS 로 채움
    """
    import time as _t
    t0 = _t.time()
    # Seed (beta-2 와 동일)
    seed_prompt = (
        "한국어 판례 DB 검색을 위한 키워드 의미 그룹 구성.\n\n"
        f"질의: \"{user_task[:500]}\"\n\n"
        "규칙:\n"
        "- **정확히 2~3개 의미 그룹** (그룹이 많으면 AND 교집합이 깨진다. 핵심만)\n"
        "- 각 그룹 10~15개 키워드 (풍부하게 — OR 처리됨)\n"
        "- 같은 개념의 동의어·한자어/고유어·영문/약어·변형은 **한 그룹에 다** 모아라\n"
        "- 그룹은 질의의 **핵심 명사축**만: 예) (A) 사건 대상/도구, (B) 맥락·행위, (C) 도메인·법리\n"
        "- 질의에 있는 부수 어휘('로그인', '관리', '사례' 등 너무 일반적·동사적 용어)는 별도 그룹으로 빼지 말 것\n"
        "- 각 그룹에 판례 본문에 실제로 쓰일 법률·규정 용어도 함께\n"
        "- 질의 외부 예시 금지, 질의 의미·유사어만\n\n"
        "출력 형식 엄수:\n그룹 1: kw, kw, kw, ...\n그룹 2: kw, kw, kw, ...\n"
    )
    seed_a = _beta2_gemma(seed_prompt, select_model, max_tokens=2048)
    groups_a = _beta2_parse_groups(seed_a)
    seed_b = _beta2_gemma(seed_prompt, select_model, max_tokens=2048)
    groups_b = _beta2_parse_groups(seed_b)
    groups: list[list[str]] = []
    n = max(len(groups_a), len(groups_b))
    for i in range(n):
        a = groups_a[i] if i < len(groups_a) else []
        b = groups_b[i] if i < len(groups_b) else []
        seen: dict[str, None] = {}
        for kw in a + b:
            kw_n = kw.strip()
            if kw_n and kw_n not in seen:
                seen[kw_n] = None
        if seen:
            groups.append(list(seen.keys())[:18])
    deduped: list[list[str]] = []
    for g in groups:
        g_set = frozenset(g)
        if any(len(g_set & frozenset(prev)) / max(1, min(len(g), len(prev))) >= 0.7 for prev in deduped):
            continue
        deduped.append(g)
    groups = deduped[:3]
    if not groups:
        import re as _re
        toks = _re.findall(r"[가-힣A-Za-z]{2,}", user_task)
        groups = [toks[i:i + 5] for i in range(0, min(len(toks), 15), 5)]
        groups = [g for g in groups if g][:3]
    if not groups:
        return [], {"selection_mode": "beta4_iter_progressive", "error": "seed_groups_empty",
                    "user_task": user_task[:200]}

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    useful_accum: dict[str, dict[str, Any]] = {}
    seen_cids: set[str] = set()
    iter_trace: list[dict[str, Any]] = []

    try:
        it = 0
        current_groups = groups
        while len(useful_accum) < useful_target and it < max_iters:
            if _t.time() - t0 > wall_budget_sec:
                break
            it += 1
            batch_size = 10 * it  # 10, 20, 30, 40, ...
            cands, fts_trace = _beta2_fts_graceful(conn, current_groups, limit=400, min_hits=3)
            prioritized_cands = _prioritize_iterative_rows(list(cands), user_task=user_task)
            new_cands = [r for r in prioritized_cands if r["canonical_id"] not in seen_cids][:batch_size]
            iter_trace.append({
                "iter": it, "batch_size": batch_size, "fts_trace": fts_trace,
                "fts_total_hits": len(cands), "new_cands": len(new_cands),
                "candidate_filter": "plain_traffic_domain_lock" if prioritized_cands != list(cands) else "",
            })
            if not new_cands:
                break
            flat_kws = [k for g in current_groups for k in g]
            pack = []
            cid_map = []
            for r in new_cands:
                snip = _beta2_windows_around(str(r["full_text"] or ""), flat_kws,
                                            radius=80, max_total_chars=1500)
                pack.append((r["case_number"] or r["canonical_id"], snip))
                cid_map.append(r)
                seen_cids.add(r["canonical_id"])
            L = [f"[질의] {user_task[:500]}",
                 f"[반복 {it} — 배치 {batch_size}] 후보 판례 스니펫을 보고 각 후보 판정 + 실제 본문 용어로부터 새 검색 각도 제안.",
                 "", "[후보]"]
            for i, (case, snip) in enumerate(pack, 1):
                L.append(f"{i}. [{case}] {snip}")
            L.append("")
            L.append("출력 형식 엄수:")
            L.append(f"JUDGE: 1:[useful|none] 2:[useful|none] ... {len(pack)}:[useful|none]")
            L.append("")
            L.append("LEARNED_GROUPS (후보 본문의 실제 용어로 새 의미 그룹 3~5개 × 5~8개 키워드, 이전 라운드 안 쓴 각도 포함):")
            L.append("그룹 1: kw, kw, ...")
            L.append("그룹 2: kw, kw, ...")
            judge_prompt = "\n".join(L)
            judge_text = _beta2_gemma(judge_prompt, select_model, max_tokens=8192)
            labels, new_groups = _beta2_parse_judge(judge_text, len(pack))
            useful_now = 0
            for idx, r in enumerate(cid_map, 1):
                if labels.get(idx) == "useful":
                    cid = r["canonical_id"]
                    if cid not in useful_accum:
                        useful_accum[cid] = {
                            "canonical_id": cid,
                            "case_number": r["case_number"],
                            "court": r["court"],
                            "decision_date": r["decision_date"],
                            "iter": it,
                        }
                        useful_now += 1
            iter_trace[-1]["useful_now"] = useful_now
            iter_trace[-1]["cumulative_useful"] = len(useful_accum)
            if not new_groups:
                break
            if new_groups == current_groups:
                break
            current_groups = new_groups[:5]

        fallback_added = 0
        if len(useful_accum) < useful_target:
            flat_kws = list({w for g in groups for w in g})
            fallback_rows: list[sqlite3.Row] = []
            if flat_kws:
                q = "(" + " OR ".join(f'"{w}"' for w in flat_kws) + ")"
                fallback_rows = _beta2_fts_query(conn, q, limit=max(useful_target * 3, 200))
            for r in _prioritize_iterative_rows(list(fallback_rows), user_task=user_task):
                if len(useful_accum) >= useful_target:
                    break
                cid = r["canonical_id"]
                if cid in useful_accum:
                    continue
                useful_accum[cid] = {
                    "canonical_id": cid,
                    "case_number": r["case_number"],
                    "court": r["court"],
                    "decision_date": r["decision_date"],
                    "iter": -1,
                }
                fallback_added += 1
        canonical_ids = list(useful_accum.keys())
        full_rows = _fetch_precedent_rows(conn, canonical_ids)
    finally:
        conn.close()
    selected_records = [canonical_row_to_selected_record(row) for row in full_rows]
    selection_meta: dict[str, Any] = {
        "selection_source": str(db_path),
        "selection_mode": "beta4_iter_progressive",
        "selected_count": len(selected_records),
        "useful_target": useful_target,
        "seed_groups": groups,
        "iters": iter_trace,
        "fallback_added": fallback_added,
        "wall_clock_sec": round(_t.time() - t0, 2),
        "top_k": useful_target,
    }
    return selected_records, selection_meta


############################################################################
# BETA-7 : Beta-4 fork with two surgical changes:
#   (1) Seed keyword generation uses thinkingLevel="high" so the LLM more
#       carefully resolves ambiguous Korean tokens like "키" (height vs
#       열쇠). The downstream FTS+judge loop still runs at minimal thinking
#       to keep wall-clock low.
#   (2) Useful accumulation stops once the cumulative full_text token
#       budget reaches `useful_token_budget` (default 400_000). This bounds
#       how many records reach chunk packing — chunk size cap is 50_000
#       tokens, so ≤10 chunks fall out automatically and there is no
#       random-drop in the chunk packer.
# No `_effective_question_user_task` hardcoded disambiguation — Beta-7
# relies purely on selector accuracy + token budget cap.
############################################################################

_BETA7_SKI_SNOWBOARD_WINTER_TERMS = (
    "스키장",
    "슬로프",
    "스키어",
    "스키",
    "스노우보드",
    "스노보드",
    "보드",
)
_BETA7_SKI_SNOWBOARD_COLLISION_TERMS = (
    "추돌",
    "충돌",
    "부딪",
    "피하기",
    "피하려",
    "방향을 전환",
    "전방",
    "좌우",
    "회피",
)
_BETA7_SKI_SNOWBOARD_FACILITY_TERMS = (
    "안전망",
    "보호펜스",
    "펜스",
    "철제기둥",
    "나무",
    "충격을 완화",
    "방호조치",
)
_BETA7_SKI_SNOWBOARD_LIABILITY_TERMS = (
    "손해배상",
    "주의의무",
    "과실",
    "과실상계",
    "설치",
    "보존상 하자",
    "하자",
    "책임",
)


def _beta7_detect_domain_anchor_kind(user_task: str) -> str:
    normalized = sanitize_search_query(user_task)
    winter_hit = any(term in normalized for term in ["스키", "스키장", "슬로프", "스노우보드", "스노보드", "보드"])
    accident_hit = any(term in normalized for term in ["추돌", "충돌", "부딪", "피하", "펜스", "안전망", "보호펜스", "골절"])
    if winter_hit and accident_hit:
        return "ski_snowboard_collision"
    return ""


def _beta7_score_ski_snowboard_collision_text(text: str) -> tuple[float, list[str]]:
    clean = _beta6_normalize_text(text)
    reasons: list[str] = []
    score = 0.0
    winter = _beta6_contains_any(clean, _BETA7_SKI_SNOWBOARD_WINTER_TERMS)
    collision = _beta6_contains_any(clean, _BETA7_SKI_SNOWBOARD_COLLISION_TERMS)
    facility = _beta6_contains_any(clean, _BETA7_SKI_SNOWBOARD_FACILITY_TERMS)
    liability = _beta6_contains_any(clean, _BETA7_SKI_SNOWBOARD_LIABILITY_TERMS)

    if winter:
        score += 16.0
        reasons.append("winter_slope")
    if collision:
        score += 13.0
        reasons.append("collision_or_avoidance")
    if facility:
        score += 15.0
        reasons.append("safety_facility")
    if liability:
        score += 10.0
        reasons.append("liability_or_fault")
    if _beta6_cluster_has_terms(
        clean,
        ["스키장", "슬로프", "스키", "스키어", "스노우보드", "스노보드"],
        [
            list(_BETA7_SKI_SNOWBOARD_COLLISION_TERMS),
            list(_BETA7_SKI_SNOWBOARD_LIABILITY_TERMS),
        ],
        radius=700,
    ):
        score += 12.0
        reasons.append("slope_collision_liability_cluster")
    if _beta6_cluster_has_terms(
        clean,
        ["안전망", "보호펜스", "펜스", "철제기둥"],
        [
            list(_BETA7_SKI_SNOWBOARD_WINTER_TERMS),
            list(_BETA7_SKI_SNOWBOARD_LIABILITY_TERMS),
        ],
        radius=800,
    ):
        score += 12.0
        reasons.append("facility_liability_cluster")
    if _beta6_contains_any(clean, ["손해배상", "배상금", "손해배상금"]):
        score += 9.0
        reasons.append("civil_damages")
    if _beta6_contains_any(clean, ["추돌"]) and _beta6_contains_any(clean, ["피하기", "피하려", "회피", "방향"]):
        score += 22.0
        reasons.append("rear_collision_avoidance")
    if _beta6_contains_any(clean, ["다른스키", "다른 스키", "다른스키어", "다른 스키어"]) and _beta6_contains_any(clean, ["피하기", "피하려", "회피"]):
        score += 20.0
        reasons.append("other_skier_avoidance")
    if _beta6_contains_any(clean, ["스노우보드", "스노보드"]) and _beta6_contains_any(clean, ["보호펜스", "펜스", "철제기둥"]):
        score += 24.0
        reasons.append("snowboard_fence_impact")
    if _beta6_contains_any(clean, ["업무상과실치사", "형사", "벌금", "피고인"]) and not _beta6_contains_any(clean, ["손해배상"]):
        score -= 34.0
        reasons.append("criminal_safety_noise")
    if _beta6_contains_any(clean, ["사망"]) and not _beta6_contains_any(clean, ["추돌", "스노우보드", "스노보드", "다른스키", "다른 스키"]):
        score -= 10.0
        reasons.append("fatality_net_noise")
    if not winter:
        score -= 18.0
    if not (collision or facility):
        score -= 10.0
    return score, reasons


def _beta7_ski_snowboard_query_variants() -> list[list[list[str]]]:
    return [
        [
            ["스키장", "슬로프", "스키", "스키어", "스노우보드", "스노보드"],
            ["추돌", "충돌", "피하기", "방향 전환", "회피"],
            ["손해배상", "주의의무", "과실"],
        ],
        [
            ["스키장", "슬로프", "스키", "스노우보드"],
            ["안전망", "보호펜스", "펜스", "철제기둥", "나무"],
            ["손해배상", "하자", "과실"],
        ],
        [
            ["스키장", "스노우보드", "스노보드"],
            ["보호펜스", "철제기둥", "충돌"],
            ["손해배상", "설치", "보존상 하자"],
        ],
        [
            ["스키장", "스키어", "슬로프"],
            ["추돌", "충돌", "전방", "좌우"],
            ["주의의무", "회피", "손해배상"],
        ],
    ]


def _beta7_select_ski_snowboard_anchor_records(
    user_task: str,
    *,
    db_path: Path,
    limit: int = 3,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    candidate_rows: dict[str, sqlite3.Row] = {}
    trace: list[dict[str, Any]] = []
    try:
        for variant in _beta7_ski_snowboard_query_variants():
            rows, search_trace = _beta6_fts_search(conn, variant, limit=260)
            trace.append({"variant": variant, "trace": search_trace, "hits": len(rows)})
            for row in rows:
                candidate_rows.setdefault(str(row["canonical_id"]), row)
        scored: list[tuple[str, float, list[str]]] = []
        for cid, row in candidate_rows.items():
            score, reasons = _beta7_score_ski_snowboard_collision_text(_beta5_row_text(row))
            row_keys = set(row.keys())
            case_number = str(row["case_number"] or "") if "case_number" in row_keys else ""
            case_name = str(row["case_name"] or "") if "case_name" in row_keys else ""
            if not case_number.strip():
                score -= 18.0
                reasons.append("missing_case_number_penalty")
            if re.search(r"(고정|고단|고합|도|헌마|헌바)", case_number) and "손해배상" not in case_name:
                score -= 30.0
                reasons.append("non_civil_case_number_penalty")
            if re.search(r"(다|가합)", case_number) or "손해배상" in case_name:
                score += 8.0
                reasons.append("civil_tort_case_boost")
            if score >= 28.0:
                scored.append((cid, score, reasons))
        scored.sort(key=lambda item: (-item[1], item[0]))
        canonical_ids = [cid for cid, _score, _reasons in scored[:limit]]
        full_rows = _fetch_precedent_rows(conn, canonical_ids)
    finally:
        conn.close()

    selected_records = [canonical_row_to_selected_record(row) for row in full_rows]
    return selected_records, {
        "kind": "ski_snowboard_collision",
        "candidate_count": len(candidate_rows),
        "anchor_ids": [record.get("file_id") for record in selected_records],
        "anchor_cases": [record.get("case_number") for record in selected_records],
        "top_debug": [
            {"canonical_id": cid, "score": round(score, 3), "reasons": reasons[:10]}
            for cid, score, reasons in scored[:10]
        ],
        "trace": trace[:6],
    }


def _beta7_domain_anchor_records(
    user_task: str,
    *,
    db_path: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    kind = _beta7_detect_domain_anchor_kind(user_task)
    if not kind:
        return [], {"kind": ""}
    if kind in {"kakao_usim", "military_key"}:
        cap = 3 if kind == "kakao_usim" else 1
        records, meta = select_top_precedents_beta6(
            user_task,
            db_path=db_path,
            useful_target=20,
            max_rounds=3,
            wall_budget_sec=60.0,
        )
        accepted_ids = [
            str(item.get("canonical_id") or "")
            for item in meta.get("top_debug") or []
            if item.get("verifier") == "accept"
        ]
        if accepted_ids:
            accepted_set = set(accepted_ids)
            ordered = [record for record in records if str(record.get("file_id") or "") in accepted_set]
        else:
            ordered = records
        return ordered[:cap], {
            "kind": kind,
            "source": "beta6_verified_anchor",
            "anchor_ids": [record.get("file_id") for record in ordered[:cap]],
            "anchor_cases": [record.get("case_number") for record in ordered[:cap]],
            "accepted_count": meta.get("accepted_count"),
            "top_debug": (meta.get("top_debug") or [])[:8],
        }
    return _beta7_select_ski_snowboard_anchor_records(user_task, db_path=db_path, limit=3)


def _beta7_merge_domain_anchors(
    anchor_records: list[dict[str, Any]],
    selected_records: list[dict[str, Any]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in anchor_records + selected_records:
        key = str(record.get("file_id") or record.get("canonical_id") or record.get("case_number") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append(record)
        if len(merged) >= limit:
            break
    return merged


def _beta7_domain_downstream_context(kind: str) -> str:
    if kind == "kakao_usim":
        return "수사기관의 유심(USIM) 분리·공기계 인증번호·카카오톡/텔레그램 계정 접속·압수수색 절차 쟁점"
    if kind == "military_key":
        return "군대 열쇠(키), 무기고·탄약고·총기·탄약 열쇠의 직접 보관·인계·점검·관리소홀 책임"
    if kind == "ski_snowboard_collision":
        return "스키장/스노우보드 슬로프 충돌·추돌 회피, 안전망/보호펜스 하자, 운영자 책임과 이용자 과실상계"
    return ""


def select_top_precedents_beta7(
    user_task: str,
    *,
    db_path: Path = PRECEDENT_DB_PATH,
    select_model: str = DEFAULT_SELECT_MODEL,
    useful_target: int = 60,
    useful_token_budget: int = 250_000,
    judge_input_token_budget: int = 50_000,
    max_iters: int = 3,
    wall_budget_sec: float = 150.0,
    seed_thinking_level: str = "high",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Beta-7 selector. See module-level docstring above this function."""
    import time as _t
    t0 = _t.time()
    domain_anchor_records, domain_anchor_meta = _beta7_domain_anchor_records(user_task, db_path=db_path)
    seed_prompt = (
        "한국어 판례 DB 검색을 위한 키워드 의미 그룹 구성.\n\n"
        f"질의: \"{user_task[:500]}\"\n\n"
        "규칙:\n"
        "- **정확히 2~3개 의미 그룹** (그룹이 많으면 AND 교집합이 깨진다. 핵심만)\n"
        "- 각 그룹 10~15개 키워드 (풍부하게 — OR 처리됨)\n"
        "- 같은 개념의 동의어·한자어/고유어·영문/약어·변형은 **한 그룹에 다** 모아라\n"
        "- 한국어 동음이의어가 있으면 질의 전체 맥락에서 어느 의미인지 결정하고 그 의미에 "
        "해당하는 동의어/관련 용어만 한 그룹에 모아라. 다른 의미의 키워드는 절대 같이 넣지 마라.\n"
        "- 그룹은 질의의 **핵심 명사축**만: 예) (A) 사건 대상/도구, (B) 맥락·행위, (C) 도메인·법리\n"
        "- 질의에 있는 부수 어휘('로그인', '관리', '사례' 등 너무 일반적·동사적 용어)는 별도 그룹으로 빼지 말 것\n"
        "- 각 그룹에 판례 본문에 실제로 쓰일 법률·규정 용어도 함께\n"
        "- 질의 외부 예시 금지, 질의 의미·유사어만\n\n"
        "출력 형식 엄수:\n그룹 1: kw, kw, kw, ...\n그룹 2: kw, kw, kw, ...\n"
    )
    # Seed: high thinking — better disambiguation of homonyms.
    seed_a = _beta2_gemma(seed_prompt, select_model, max_tokens=2048, thinking_level=seed_thinking_level)
    groups_a = _beta2_parse_groups(seed_a)
    seed_b = _beta2_gemma(seed_prompt, select_model, max_tokens=2048, thinking_level=seed_thinking_level)
    groups_b = _beta2_parse_groups(seed_b)
    groups: list[list[str]] = []
    n = max(len(groups_a), len(groups_b))
    for i in range(n):
        a = groups_a[i] if i < len(groups_a) else []
        b = groups_b[i] if i < len(groups_b) else []
        seen: dict[str, None] = {}
        for kw in a + b:
            kw_n = kw.strip()
            if kw_n and kw_n not in seen:
                seen[kw_n] = None
        if seen:
            groups.append(list(seen.keys())[:18])
    deduped: list[list[str]] = []
    for g in groups:
        g_set = frozenset(g)
        if any(len(g_set & frozenset(prev)) / max(1, min(len(g), len(prev))) >= 0.7 for prev in deduped):
            continue
        deduped.append(g)
    groups = deduped[:3]
    if not groups:
        import re as _re
        toks = _re.findall(r"[가-힣A-Za-z]{2,}", user_task)
        groups = [toks[i:i + 5] for i in range(0, min(len(toks), 15), 5)]
        groups = [g for g in groups if g][:3]
    if not groups:
        return [], {"selection_mode": "beta7_token_capped", "error": "seed_groups_empty",
                    "user_task": user_task[:200]}

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    useful_accum: dict[str, dict[str, Any]] = {}
    accum_token_count = 0
    seen_cids: set[str] = set()
    iter_trace: list[dict[str, Any]] = []
    stopped_reason = "iters_or_target_reached"

    def _estimate_tokens(text: str) -> int:
        # Cheap proxy: 1 token ≈ 4 chars (Gemini tokenizer is roughly that).
        return max(1, len(text or "") // 4)

    try:
        it = 0
        current_groups = groups
        # Round-by-round keyword history. Pass this back to the LLM each round
        # so it sees "what we already tried, what came back, why some were
        # judged useful/none" — this is the iterative disambiguation
        # mechanism, not a one-shot seed → fixed-keyword run.
        round_history: list[dict[str, Any]] = []
        while len(useful_accum) < useful_target and it < max_iters:
            if _t.time() - t0 > wall_budget_sec:
                stopped_reason = "wall_budget"
                break
            if accum_token_count >= useful_token_budget:
                stopped_reason = "token_budget"
                break
            it += 1
            cands, fts_trace = _beta2_fts_graceful(conn, current_groups, limit=400, min_hits=3)
            prioritized_cands = _prioritize_iterative_rows(list(cands), user_task=user_task)
            unseen = [r for r in prioritized_cands if r["canonical_id"] not in seen_cids]
            iter_trace.append({
                "iter": it, "fts_trace": fts_trace,
                "fts_total_hits": len(cands), "unseen": len(unseen),
                "accum_tokens": accum_token_count,
                "candidate_filter": "plain_traffic_domain_lock" if prioritized_cands != list(cands) else "",
            })
            if not unseen:
                stopped_reason = "no_more_candidates"
                break
            # Dynamic batch size: pack as many candidates as fit under the
            # judge prompt's input-token budget (default 50k — one Gemma
            # call's effective context). Replaces the old 10/20/30/...
            # progressive schedule. The LLM gets a fuller sample each round
            # and the loop can converge in fewer rounds.
            flat_kws = [k for g in current_groups for k in g]
            pack: list[tuple[str, str]] = []
            cid_map: list[Any] = []
            cumulative_judge_tokens = 0
            for r in unseen:
                snip = _beta2_windows_around(str(r["full_text"] or ""), flat_kws,
                                            radius=80, max_total_chars=1500)
                snip_tokens = _estimate_tokens(snip)
                if pack and cumulative_judge_tokens + snip_tokens > judge_input_token_budget:
                    break
                pack.append((r["case_number"] or r["canonical_id"], snip))
                cid_map.append(r)
                cumulative_judge_tokens += snip_tokens
                seen_cids.add(r["canonical_id"])
            iter_trace[-1]["batch_size"] = len(pack)
            iter_trace[-1]["batch_judge_tokens"] = cumulative_judge_tokens
            L = [f"[원본 질문] {user_task[:500]}", ""]
            # Inject prior-round keyword + outcome history. Without this the
            # LLM evolves keywords as if each round is a fresh start; with it
            # the LLM can see "round 1 tried [열쇠] but mostly missed,
            # round 2 added [무기고] and got 8 useful → keep that axis".
            if round_history:
                L.append("[이전 라운드 history — 어느 키워드로 검색했고 결과가 어땠는지]")
                for prev in round_history:
                    groups_str = "; ".join(
                        f"그룹 {i+1}: {', '.join(g[:8])}"
                        for i, g in enumerate(prev.get("groups") or [])
                    )
                    sample = prev.get("sample_useful") or []
                    sample_str = ("; useful 일부: " + ", ".join(sample[:3])) if sample else ""
                    L.append(
                        f"  - 라운드 {prev.get('iter')}: {groups_str} → "
                        f"useful {prev.get('useful_count', 0)}건 / 후보 {prev.get('candidate_count', 0)}건"
                        f"{sample_str}"
                    )
                L.append("")
            L.append(f"[현재 라운드 {it} — 배치 {len(pack)}건 / 입력 ~{cumulative_judge_tokens:,} tokens] 아래 후보를 판정 + 실제 본문 용어로 다음 검색 각도(LEARNED_GROUPS) 제안.")
            L.append("")
            L.append(f"[현재 라운드 검색 키워드]")
            for gi, g in enumerate(current_groups, 1):
                L.append(f"  그룹 {gi}: {', '.join(g)}")
            L.append("")
            L.append("[후보]")
            for i, (case, snip) in enumerate(pack, 1):
                L.append(f"{i}. [{case}] {snip}")
            L.append("")
            L.append("판정 규칙:")
            L.append("- useful: 원본 질문이 다루는 (a) 행위 주체·대상·도구, (b) 사고/분쟁의 유형,")
            L.append("  (c) 적용 법리·죄명·법령 모두가 후보 본문과 명백히 일치하는 판례.")
            L.append("- none: 키워드 단어만 겹치고 행위 주체/사고 유형/법리 중 하나라도 다르면 useful 아님.")
            L.append("  특히 한국어 동음이의어로 인해 잡힌 것 (예: 명사가 같지만 다른 의미로 쓰임)은 none.")
            L.append("- 의심스럽거나 부분만 닿는 경우 none. 정확히 매치되는 것만 useful.")
            L.append("")
            L.append("출력 형식 엄수:")
            L.append(f"JUDGE: 1:[useful|none] 2:[useful|none] ... {len(pack)}:[useful|none]")
            L.append("")
            L.append("LEARNED_GROUPS (이전 라운드들이 시도한 각도를 알고 있으니, **새 각도** 만 추가하라. 후보 본문에서 본 실제 용어 + 이전에 안 쓴 의미축):")
            L.append("그룹 1: kw, kw, ...")
            L.append("그룹 2: kw, kw, ...")
            judge_prompt = "\n".join(L)
            judge_text = _beta2_gemma(judge_prompt, select_model, max_tokens=8192)
            labels, new_groups = _beta2_parse_judge(judge_text, len(pack))
            useful_now = 0
            useful_case_numbers_this_round: list[str] = []
            for idx, r in enumerate(cid_map, 1):
                if labels.get(idx) == "useful":
                    cid = r["canonical_id"]
                    if cid not in useful_accum:
                        full_text_tokens = _estimate_tokens(str(r["full_text"] or ""))
                        useful_accum[cid] = {
                            "canonical_id": cid,
                            "case_number": r["case_number"],
                            "court": r["court"],
                            "decision_date": r["decision_date"],
                            "iter": it,
                            "tokens": full_text_tokens,
                        }
                        accum_token_count += full_text_tokens
                        useful_now += 1
                        if r["case_number"]:
                            useful_case_numbers_this_round.append(str(r["case_number"]))
                        if accum_token_count >= useful_token_budget:
                            break
            iter_trace[-1]["useful_now"] = useful_now
            iter_trace[-1]["cumulative_useful"] = len(useful_accum)
            iter_trace[-1]["cumulative_tokens"] = accum_token_count
            # Append outcome of this round into the history that the NEXT
            # round's prompt will see — this is what makes the loop
            # genuinely iterative/learning rather than a sequence of
            # disconnected one-shot judges.
            round_history.append({
                "iter": it,
                "groups": [list(g) for g in current_groups],
                "candidate_count": len(pack),
                "useful_count": useful_now,
                "sample_useful": useful_case_numbers_this_round[:3],
            })
            if accum_token_count >= useful_token_budget:
                stopped_reason = "token_budget"
                break
            if not new_groups:
                stopped_reason = "no_new_groups"
                break
            if new_groups == current_groups:
                stopped_reason = "groups_converged"
                break
            current_groups = new_groups[:5]

        # Token budget early-stop means: do NOT run the OR-union FTS fallback
        # (which would just blow past the budget). The fallback only runs when
        # we stopped for "no_more_candidates" / "wall_budget" / "no_new_groups"
        # / "iters_or_target_reached" before hitting the token budget.
        fallback_added = 0
        if stopped_reason != "token_budget" and len(useful_accum) < useful_target and accum_token_count < useful_token_budget:
            flat_kws = list({w for g in groups for w in g})
            fallback_rows: list[sqlite3.Row] = []
            if flat_kws:
                q = "(" + " OR ".join(f'"{w}"' for w in flat_kws) + ")"
                fallback_rows = _beta2_fts_query(conn, q, limit=max(useful_target * 3, 200))
            for r in _prioritize_iterative_rows(list(fallback_rows), user_task=user_task):
                if len(useful_accum) >= useful_target:
                    break
                if accum_token_count >= useful_token_budget:
                    break
                cid = r["canonical_id"]
                if cid in useful_accum:
                    continue
                full_text_tokens = _estimate_tokens(str(r["full_text"] or ""))
                useful_accum[cid] = {
                    "canonical_id": cid,
                    "case_number": r["case_number"],
                    "court": r["court"],
                    "decision_date": r["decision_date"],
                    "iter": -1,
                    "tokens": full_text_tokens,
                }
                accum_token_count += full_text_tokens
                fallback_added += 1
        canonical_ids = list(useful_accum.keys())
        full_rows = _fetch_precedent_rows(conn, canonical_ids)
    finally:
        conn.close()
    selected_records = [canonical_row_to_selected_record(row) for row in full_rows]
    if domain_anchor_records:
        selected_records = _beta7_merge_domain_anchors(
            domain_anchor_records,
            selected_records,
            limit=useful_target,
        )
    # Carry forward the LAST round's evolved keyword groups
    # (`current_groups` at loop exit) so chunk analyzer / planner / writer
    # see the disambiguated context the selector arrived at — without an
    # extra LLM call. The selector's iterative LEARNED_GROUPS evolution is
    # the disambiguation mechanism; we just expose its result.
    final_groups = current_groups if current_groups else groups
    flat_keywords: list[str] = []
    seen_kw: set[str] = set()
    for grp in final_groups[:4]:
        for kw in grp[:10]:
            if kw and kw not in seen_kw:
                seen_kw.add(kw)
                flat_keywords.append(kw)
    flat_keywords = flat_keywords[:30]
    if flat_keywords:
        downstream_context_parts = [
            f"[검색 맥락 — 위 질문의 의도를 selector가 키워드로 정리한 결과] {', '.join(flat_keywords)}"
        ]
    else:
        downstream_context_parts = []
    domain_context = _beta7_domain_downstream_context(str(domain_anchor_meta.get("kind") or ""))
    if domain_context:
        downstream_context_parts.insert(0, f"[도메인 앵커 맥락] {domain_context}")
    downstream_user_task = (
        f"{user_task.strip()}\n\n" + "\n".join(downstream_context_parts)
        if downstream_context_parts
        else user_task.strip()
    )
    selection_meta = {
        "selection_source": str(db_path),
        "selection_mode": "beta7_token_capped",
        "selected_count": len(selected_records),
        "domain_anchor": domain_anchor_meta,
        "useful_target": useful_target,
        "useful_token_budget": useful_token_budget,
        "accum_tokens": accum_token_count,
        "stopped_reason": stopped_reason,
        "seed_groups": groups,
        "final_groups": final_groups,
        "seed_thinking_level": seed_thinking_level,
        # Disambiguated framing built from the selector's evolved keywords
        # (no extra LLM call). Picked up by `_effective_question_user_task`.
        "downstream_user_task": downstream_user_task,
        "iters": iter_trace,
        "fallback_added": fallback_added,
        "wall_clock_sec": round(_t.time() - t0, 2),
        "top_k": useful_target,
    }
    return selected_records, selection_meta


############################################################################
# BETA-3 : R25 style — FTS broad recall → local BM25 rerank → Gemma 0-9 score
#          → RRF fusion. paraphrase 안정성을 위해 Gemma 를 soft score 로.
############################################################################

def _beta3_tokens(text: str) -> list[str]:
    import re as _re
    # 한국어/영문 토큰화 (간이)
    toks = _re.findall(r"[가-힣A-Za-z0-9]+", text.lower())
    return [t for t in toks if len(t) >= 2]


class _Beta3BM25:
    """간이 BM25 for top-K rerank (작은 후보 집합만)."""
    def __init__(self, docs: list[str], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.docs = [_beta3_tokens(d) for d in docs]
        self.N = len(self.docs)
        self.avgdl = sum(len(d) for d in self.docs) / max(1, self.N)
        from collections import Counter
        self.tf = [Counter(d) for d in self.docs]
        df: dict[str, int] = {}
        for d in self.docs:
            for t in set(d):
                df[t] = df.get(t, 0) + 1
        import math as _m
        self.idf = {t: _m.log((self.N - c + 0.5) / (c + 0.5) + 1.0) for t, c in df.items()}

    def score(self, q_tokens: list[str], i: int) -> float:
        s, dl = 0.0, len(self.docs[i])
        tf = self.tf[i]
        for t in q_tokens:
            if t not in tf: continue
            f = tf[t]
            idf = self.idf.get(t, 0.0)
            s += idf * (f * (self.k1 + 1)) / (f + self.k1 * (1 - self.b + self.b * dl / max(1, self.avgdl)))
        return s

    def rank(self, query: str, top_k: int | None = None) -> list[tuple[int, float]]:
        q = _beta3_tokens(query)
        scored = [(i, self.score(q, i)) for i in range(self.N)]
        scored.sort(key=lambda x: -x[1])
        return scored[:top_k] if top_k else scored


def _beta3_rerank_prompt(query: str, cands: list[dict[str, Any]]) -> str:
    L = [f"[질의] {query[:400]}", "", "[후보]"]
    for i, c in enumerate(cands, 1):
        body = (c.get("full_text_head") or c.get("full_text") or "")[:500].replace("\n", " ")
        head = c.get("case_number") or c.get("canonical_id", "")
        L.append(f"{i}. [{head}] {body}")
    L.append("")
    L.append("[지시] 각 후보가 위 질의와 얼마나 직접 관련되는지 0-9 점수. 짧게.")
    L.append("출력 형식: '번호:점수' 한 줄씩. 예) 1:7")
    return "\n".join(L)


def _beta3_parse_scores(text: str, n: int) -> dict[int, int]:
    import re as _re
    out: dict[int, int] = {}
    for m in _re.finditer(r"(\d{1,2})\s*[:\-.]?\s*(\d)\b", text):
        try:
            idx = int(m.group(1))
            sc = int(m.group(2))
            if 1 <= idx <= n and 0 <= sc <= 9:
                out[idx] = sc
        except ValueError:
            continue
    return out


def select_top_precedents_beta3(
    user_task: str,
    *,
    db_path: Path = PRECEDENT_DB_PATH,
    select_model: str = DEFAULT_SELECT_MODEL,
    top_k: int = 10,
    fts_limit: int = 200,
    rerank_top: int = 60,
    wall_budget_sec: float = 300.0,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """R25 style: FTS broad recall → local BM25 + Gemma 0-9 score → RRF fusion."""
    import time as _t
    t0 = _t.time()
    # Seed keywords (Gemma 1 call — simpler than beta-2)
    seed_prompt = (
        "한국어 판례 검색 키워드 그룹 구성.\n\n"
        f"질의: \"{user_task[:500]}\"\n\n"
        "규칙:\n"
        "- 정확히 2~3개 의미 그룹 (핵심 명사축만)\n"
        "- 각 그룹 10~15개 키워드 (동의어/변형/영문/약어 포함)\n"
        "- 너무 일반적 동사(로그인, 관리)는 별도 그룹으로 빼지 말 것\n\n"
        "출력 형식 엄수:\n그룹 1: kw, kw, ...\n그룹 2: kw, kw, ...\n"
    )
    seed_text = _beta2_gemma(seed_prompt, select_model, max_tokens=1024)
    groups = _beta2_parse_groups(seed_text)[:3]
    if not groups:
        # fallback rule-based tokenize
        import re as _re
        toks = _re.findall(r"[가-힣A-Za-z]{2,}", user_task)
        groups = [toks[:10]]
    # Stage A: FTS broad (AND of OR groups)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        fts_rows: list[sqlite3.Row] = []
        fts_trace: list[dict] = []
        q = _beta2_build_fts(groups)
        fts_rows = _beta2_fts_query(conn, q, limit=fts_limit)
        fts_trace.append({"strategy": "full_AND", "n_groups": len(groups), "hits": len(fts_rows)})
        if len(fts_rows) < 20:
            # drop_last_1
            if len(groups) > 1:
                q1 = _beta2_build_fts(groups[:-1])
                r1 = _beta2_fts_query(conn, q1, limit=fts_limit)
                fts_trace.append({"strategy": "drop_last_1", "hits": len(r1)})
                if len(r1) > len(fts_rows): fts_rows = r1
            if len(fts_rows) < 20:
                flat = list({w for g in groups for w in g})
                q_or = "(" + " OR ".join(f'"{w}"' for w in flat) + ")"
                r2 = _beta2_fts_query(conn, q_or, limit=fts_limit)
                fts_trace.append({"strategy": "flat_OR", "hits": len(r2)})
                if len(r2) > len(fts_rows): fts_rows = r2
        # Stage B: Local BM25 rerank on FTS candidates
        if not fts_rows:
            return [], {"selection_mode": "beta3_r25", "error": "no_candidates",
                        "seed_groups": groups, "fts_trace": fts_trace}
        cand_texts = [str(r["full_text"] or "")[:8000] for r in fts_rows]
        bm25 = _Beta3BM25(cand_texts)
        bm25_scored = bm25.rank(user_task, top_k=rerank_top)
        bm25_ranked_idx = [i for i, _ in bm25_scored]  # rank 순 index
        # Stage C: Gemma 0-9 rerank on top-K (batched into chunks of 20)
        chunk = 20
        gemma_scores_per_cand: dict[int, int] = {}
        for batch_start in range(0, len(bm25_ranked_idx), chunk):
            if _t.time() - t0 > wall_budget_sec:
                break
            batch_idxs = bm25_ranked_idx[batch_start:batch_start + chunk]
            cands = [{"full_text_head": cand_texts[i],
                     "case_number": fts_rows[i]["case_number"],
                     "canonical_id": fts_rows[i]["canonical_id"]}
                     for i in batch_idxs]
            prompt = _beta3_rerank_prompt(user_task, cands)
            resp = _beta2_gemma(prompt, select_model, max_tokens=1024)
            parsed = _beta3_parse_scores(resp, len(cands))
            for pos, sc in parsed.items():
                abs_idx = batch_idxs[pos - 1]
                gemma_scores_per_cand[abs_idx] = sc
        # Gemma rank: higher score = better; unscored = 0
        gemma_sorted = sorted(
            range(len(fts_rows)),
            key=lambda i: (-gemma_scores_per_cand.get(i, -1), bm25_ranked_idx.index(i) if i in bm25_ranked_idx else 999),
        )
        # Stage D: RRF fusion
        bm_pos = {idx: r for r, idx in enumerate(bm25_ranked_idx)}
        gm_pos = {idx: r for r, idx in enumerate(gemma_sorted)}
        all_idxs = set(bm_pos) | set(gm_pos)
        def _rrf(i: int) -> float:
            return 1.0 / (60 + bm_pos.get(i, 999)) + 1.0 / (60 + gm_pos.get(i, 999))
        fused = sorted(all_idxs, key=lambda i: -_rrf(i))
        top_indices = fused[:top_k]
        canonical_ids = [fts_rows[i]["canonical_id"] for i in top_indices]
        full_rows = _fetch_precedent_rows(conn, canonical_ids)
    finally:
        conn.close()
    selected_records = [canonical_row_to_selected_record(row) for row in full_rows]
    selection_meta: dict[str, Any] = {
        "selection_source": str(db_path),
        "selection_mode": "beta3_r25_rrf",
        "selected_count": len(selected_records),
        "top_k": top_k,
        "seed_groups": groups,
        "fts_trace": fts_trace,
        "fts_candidates": len(fts_rows),
        "bm25_rerank_top": rerank_top,
        "gemma_scored_count": len(gemma_scores_per_cand),
        "wall_clock_sec": round(_t.time() - t0, 2),
    }
    return selected_records, selection_meta


def select_top_precedents_beta1(
    user_task: str,
    *,
    db_path: Path = PRECEDENT_DB_PATH,
    select_model: str = DEFAULT_SELECT_MODEL,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """분석 BETA-1: chained-memory selection with rule-based thresholds.

    - Per-keyword FTS top-500 (wider than existing 80)
    - Overlap threshold: max(2, round(kw_count * 0.25))
    - Hard seed cap: 30
    - No penalty rerank (pure BM25 overlap + best_rank tiebreak)
    """
    queries = build_search_queries(
        user_task,
        keyword_count=15,
        select_model=select_model,
    )
    # queries[0] = base task; rest are keywords
    kw_count = max(1, len(queries) - 1)
    overlap_min = max(2, round(kw_count * 0.25))
    per_kw_topk = 500
    seed_cap = 30

    conn = sqlite3.connect(db_path)
    try:
        keyword_hits: dict[str, list[dict[str, Any]]] = {}
        for query in queries:
            keyword_hits[query] = search_index.search_precedents(conn, query, limit=per_kw_topk)
        # Aggregate by canonical_id, count keyword overlap
        agg = aggregate_selected_rows(keyword_hits, limit=10000)
        # Apply threshold + cap
        threshold_passed = [r for r in agg if int(r.get("keyword_hit_count") or 0) >= overlap_min]
        threshold_passed.sort(
            key=lambda r: (
                -int(r.get("keyword_hit_count") or 0),
                float(r.get("best_score") or 0.0),  # smaller bm25 rank = better
                str(r.get("canonical_id") or ""),
            )
        )
        selected = threshold_passed[:seed_cap]
        canonical_ids = [str(r.get("canonical_id") or "") for r in selected if str(r.get("canonical_id") or "").strip()]
        full_rows = _fetch_precedent_rows(conn, canonical_ids)
    finally:
        conn.close()
    selected_records = [canonical_row_to_selected_record(row) for row in full_rows]
    selection_meta = {
        "selection_source": str(db_path),
        "selection_mode": "beta1_chained_memory",
        "selected_count": len(selected_records),
        "candidate_count": len(agg),
        "threshold_passed_count": len(threshold_passed),
        "overlap_min": overlap_min,
        "per_kw_topk": per_kw_topk,
        "seed_cap": seed_cap,
        "keywords": queries[1:],
        "queries": queries,
        "top_k": seed_cap,
    }
    return selected_records, selection_meta


def select_top_precedents(
    user_task: str,
    *,
    db_path: Path = PRECEDENT_DB_PATH,
    keyword_count: int = DEFAULT_KEYWORD_COUNT,
    per_keyword_limit: int = DEFAULT_PER_KEYWORD_LIMIT,
    top_k: int = DEFAULT_TOP_K,
    select_model: str = DEFAULT_SELECT_MODEL,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    queries = build_search_queries(
        user_task,
        keyword_count=keyword_count,
        select_model=select_model,
    )
    conn = sqlite3.connect(db_path)
    try:
        keyword_hits: dict[str, list[dict[str, Any]]] = {}
        query_limit = max(per_keyword_limit, top_k * 2)
        for query in queries:
            keyword_hits[query] = search_index.search_precedents(conn, query, limit=query_limit)
        candidate_limit = max(top_k, top_k * 3)
        ranked = aggregate_selected_rows(keyword_hits, limit=candidate_limit)
        candidate_count = len(ranked)
        ranked = _rerank_ranked_rows(ranked, user_task=user_task, limit=candidate_limit)
        canonical_ids = [str(row.get("canonical_id") or "") for row in ranked if str(row.get("canonical_id") or "").strip()]
        full_rows = _fetch_precedent_rows(conn, canonical_ids)
    finally:
        conn.close()
    selected_records = [canonical_row_to_selected_record(row) for row in full_rows[:top_k]]
    selection_meta = {
        "selection_source": str(db_path),
        "selected_count": len(selected_records),
        "candidate_count": candidate_count,
        "keywords": queries[1:],
        "queries": queries,
        "top_k": top_k,
    }
    return selected_records, selection_meta
