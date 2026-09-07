from __future__ import annotations

import os
import re
import sqlite3
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .domain_adapters import get_domain_adapter
from .products import ProductProfile


TOKEN_RE = re.compile(r"[\w\u0600-\u06ff]+", re.UNICODE)
DEFAULT_SQLITE_MMAP_BYTES = 64 * 1024 * 1024
DEFAULT_SQLITE_CACHE_KIB = 8 * 1024
DEFAULT_SQLITE_TIMEOUT_SECONDS = 2.0
DEFAULT_SQLITE_QUERY_DEADLINE_SECONDS = 3.0
_SIMLI_ROWID_RANGES_CACHE: dict[str, list[tuple[str, int, int]]] = {}
SIMLI_KO_QUERY_EXPANSIONS = (
    ("자살", "suicide"),
    ("자해", "self harm"),
    ("공황", "panic"),
    ("불안", "anxiety"),
    ("걱정", "worry"),
    ("우울감", "depression"),
    ("우울", "depression"),
    ("불면", "insomnia"),
    ("수면", "insomnia"),
    ("잠", "insomnia"),
    ("주의력", "ADHD"),
    ("집중", "ADHD"),
)
SIMLI_ROLE_HINT_DOC_TYPES = {
    "dsm": ("dsm5_chunk",),
    "guideline": ("guideline_chunk", "guideline"),
    "icd": ("icd11_entity",),
}
SIMLI_ROLE_HINT_TOKENS = {
    "dsm": ("dsm", "dsm5", "dsm-5", "진단통계", "진단 통계"),
    "guideline": ("guideline", "guidelines", "clinical guideline", "practice guideline", "가이드라인", "임상 가이드라인", "지침"),
    "icd": ("icd", "icd11", "icd-11"),
}
SIMLI_ROLE_HINT_LOW_SIGNAL_TOKENS = {
    "dsm",
    "dsm5",
    "clinical",
    "guideline",
    "guidelines",
    "practice",
    "icd",
    "icd11",
    "가이드라인",
    "임상",
    "지침",
    "관점",
    "정리",
    "정리해줘",
    "때",
    "어떤",
    "단서",
}
ISLAM_QUERY_EXPANSIONS = (
    (("기도", "예배", "salah", "salat", "prayer", "الصلاة", "صلاة"), "prayer salah salat صلاة الصلوة صلوات qibla قبلة worship times prayers مواقيت"),
    (("여행", "여행자", "합쳐", "합치", "combine", "travel", "traveller", "جمع", "السفر", "سفر", "مسافر", "قصر"), "combine prayer travel qasr jam سفر مسافر جمع قصر صلاة الظهر العصر المغرب العشاء"),
    (("키블라", "qibla", "قبلة"), "qibla prayer direction المسجد الحرام قبلة صلاة"),
    (("금식", "라마단", "fasting", "sawm", "ramadan", "صوم", "صيام", "رمضان"), "fasting sawm siyam ramadan صوم صيام رمضان"),
    (("자카트", "zakat", "زكاة"), "zakat alms charity زكاة صدقة"),
    (("결혼", "혼인", "보호자", "후견", "wali", "guardian", "marriage", "nikah", "نكاح", "ولي"), "nikah marriage wali guardian consent نكاح زواج ولي الولي عقد"),
    (("이혼", "탈라크", "divorce", "talaq", "طلاق"), "divorce talaq khula iddah طلاق خلع عدة"),
    (("상속", "inheritance", "mirath", "ميراث", "فرائض"), "inheritance mirath faraid heirs ميراث فرائض وارث"),
    (("리바", "이자", "usury", "interest", "riba", "ربا"), "riba usury interest trade ربا بيع"),
    (("정화", "우두", "wudu", "ablution", "purification", "طهارة", "وضوء"), "purification tahara wudu ghusl طهارة وضوء غسل"),
    (("하디스", "전승", "hadith", "isnad", "حديث", "إسناد"), "hadith sunnah isnad narration حديث سنة إسناد"),
    (("학파", "학파별", "madhhab", "school", "مذهب"), "hanafi shafii maliki hanbali jafari madhhab حنفي شافعي مالكي حنبلي جعفري مذهب"),
    (("수니", "시아", "종파", "sunni", "shia", "shi'a", "سني", "شيعة"), "sunni shia shiite sect tradition سنة سني شيعة جعفري"),
    (("할랄", "하람", "halal", "haram", "حلال", "حرام"), "halal haram lawful forbidden حلال حرام"),
    (("배교", "apostasy", "ridda", "ردة"), "apostasy ridda repentance مرتد ردة توبة"),
)
ISLAM_LOW_SIGNAL_SURFACE_TERMS = {
    "꾸란",
    "하디스",
    "주석",
    "근거",
    "근거별",
    "하루",
    "몇번",
    "몇회",
    "몇",
    "번",
    "횟수",
    "해야",
    "해야함",
    "해야하나",
    "해야하나요",
    "단정하지",
    "말고",
    "정리",
    "정리해줘",
    "알려줘",
    "비교해줘",
    "입장",
    "입장을",
    "현대",
    "هل",
    "يجوز",
    "بين",
    "في",
    "اذكر",
    "أقوال",
    "اقوال",
    "ولا",
    "تصدر",
    "فتوى",
    "ملزمة",
    "the",
    "and",
    "how",
    "do",
    "does",
    "without",
    "issuing",
    "ruling",
}
ISLAM_SOURCE_CONTROL_EXPANSION_TERMS = {"hadith", "sunnah", "isnad", "narration", "حديث", "سنة", "إسناد"}
TCM_QUERY_EXPANSIONS = (
    (("감초", "甘草", "licorice", "glycyrrhiza", "gancao"), "감초 甘草 licorice glycyrrhiza gancao 조화제약 諸藥"),
    (("임신", "妊娠", "pregnancy", "gestation"), "임신 妊娠 pregnancy gestation pregnant"),
    (("금기", "禁忌", "contraindication", "주의", "caution"), "금기 禁忌 contraindication caution safety"),
    (("본초", "약재", "本草", "materia", "herb"), "본초 本草 materia medica herb medicinal 약재"),
    (("처방", "방제", "方劑", "方剂", "formula"), "처방 방제 方劑 方剂 formula prescription"),
    (("변증", "辨證", "辨证", "pattern", "syndrome"), "변증 辨證 辨证 pattern differentiation syndrome 證 证"),
    (("한열", "寒熱", "cold", "heat"), "한열 寒熱 cold heat 寒 熱"),
    (("소화", "소화불량", "비위", "脾胃", "消化", "indigestion", "dyspepsia"), "소화불량 소화 비위 脾胃 消化 indigestion dyspepsia stomach spleen"),
    (("변비", "便秘", "대변불통", "大便不通", "constipation"), "변비 便秘 大便不通 constipation"),
    (("복만", "복부창만", "배가 부르", "그득", "腹滿", "腹满", "腹脹", "腹胀"), "복만 腹滿 腹满 腹脹 腹胀"),
    (("다한", "땀", "발한", "汗出", "多汗", "sweating"), "다한 汗出 多汗 sweating"),
    (("식사 양호", "식사는 잘", "식사를 잘", "잘 먹", "식욕이 좋", "식욕 양호", "납가", "納可", "纳可", "appetite"), "식사양호 納可 纳可 appetite"),
    (("활실", "맥활", "활맥", "脈滑", "脉滑", "滑實", "滑实"), "활실 脈滑 脉滑 滑實 滑实"),
    (("불면", "잠", "수면", "失眠", "不眠", "insomnia"), "불면 不眠 失眠 insomnia sleep 심신불교 心腎不交"),
    (("침", "침구", "뜸", "鍼灸", "針灸", "acupuncture", "moxibustion"), "침구 鍼灸 針灸 acupuncture moxibustion meridian 경락"),
    (("사상", "체질", "四象", "sasang", "constitution"), "사상 체질 四象 sasang constitution 태양 태음 소양 소음"),
)
LAWKEY_LOW_SIGNAL_SURFACE_TERMS = {
    "사건",
    "판례",
    "관련",
    "대해",
    "대하여",
    "대한",
    "정보",
    "정리",
    "정리해줘",
    "알려줘",
    "찾아줘",
    "찾기",
    "추정",
    "추정해봐",
    "해봐",
    "해줘",
    "뭐야",
    "무엇",
    "어떻게",
}
LAWKEY_TRAILING_PARTICLES = (
    "에게서",
    "으로서",
    "으로써",
    "에서",
    "에게",
    "부터",
    "까지",
    "처럼",
    "보다",
    "으로",
    "하고",
    "이나",
    "거나",
    "이며",
    "이고",
    "와",
    "과",
    "을",
    "를",
    "은",
    "는",
    "이",
    "가",
    "의",
    "에",
    "로",
    "도",
    "만",
)
TCM_MATERIA_PASSAGE_SOURCE_IDS = (
    "tcm.kmm.mediclassics.boncho-gangmok",
    "tcm.kmm.mediclassics.boncho-jeonghwa",
    "tcm.kmm.mediclassics.boncho-yuhamyo",
)
TCM_FORMULARY_PASSAGE_SOURCE_IDS = (
    "tcm.kmm.mediclassics.bangyak-hapyeon",
    "tcm.kmm.mediclassics.taepyeong-hyemin",
    "tcm.kmm.mediclassics.uibang-hapyeon",
)
SIMLI_EXCLUDED_DOC_TYPES = {
    "counseling_qa",
    "therapy_dialog",
    "social_post",
    "social_post_labeled",
    "faq_qa",
    "mh_text",
    "counseling_preference",
    "classic_text",
    "imhi_instruction",
}
SIMLI_ALLOWED_DOC_TYPES = {
    "research_paper",
    "paper",
    "preprint",
    "patient_case",
    "dsm5_chunk",
    "icd11_entity",
    "guideline",
    "guideline_chunk",
    "benchmark_cbt_qa",
    "benchmark_cbt_distortions",
}
SIMLI_LOW_CONFIDENCE_DOC_TYPES = {
    "benchmark_cbt_qa",
    "benchmark_cbt_distortions",
    "counseling_qa",
    "faq_qa",
    "imhi_instruction",
    "mh_text",
    "social_post",
    "social_post_labeled",
    "therapy_dialog",
    "counseling_preference",
}
SIMLI_QUARANTINED_SOURCES = {
    "hf:phr_mental_therapy",
    "hf:solomon_reddit_mh",
    "hf:psychocounsel_pref",
    "hf:entfane_psychotherapy",
    "hf:fadodr_therapy",
    "hf:jkhedri_psychology",
    "hf:samhog_psychology_10k",
    "hf:marmikpandya_mental_health",
    "hf:zahrizhal_mh_conv",
    "hf:tolu_mh_faq",
    "hf:tvr_mh_data",
    "hf:riyazmk_mh",
    "hf:heliosbrahma_chatbot",
}
SIMLI_LOW_CONFIDENCE_SOURCES = {
    "gh:mentallama",
    "gh:counsel_chat",
    "hf:amod_counseling",
    "hf:cbt_bench_qa",
    "hf:cbt_bench_distortions",
    "hf:mentalchat16k",
}
SIMLI_AUTHORITATIVE_SOURCE_PRIORITY = (
    "apa:dsm5",
    "icd11",
    "who:icd11",
    "guidelines:clinical",
    "pmc:psychiatry",
    "s2:psych",
    "openalex:psych",
    "psyarxiv:preprints",
    "arxiv:psych",
    "biorxiv:psych",
    "hf:pmc_patients",
)
SIMLI_DOC_TYPE_BIAS = {
    "dsm5_chunk": 520.0,
    "icd11_entity": 500.0,
    "guideline_chunk": 480.0,
    "guideline": 460.0,
    "research_paper": 360.0,
    "paper": 340.0,
    "patient_case": 220.0,
    "preprint": 180.0,
    "benchmark_cbt_qa": -140.0,
    "benchmark_cbt_distortions": -140.0,
}


@dataclass(frozen=True)
class SearchResult:
    canonical_id: str
    title: str
    citation: str
    authority_body: str
    source_date: str
    case_name: str
    case_type: str
    full_text: str
    source_dataset: str = ""
    source_path: str = ""
    score: float = 0.0
    language: str = ""
    source_url: str = ""
    tradition: str = ""
    school: str = ""
    source_kind: str = ""
    authority_level: int = 0
    authority_label: str = ""


def _connect_readonly(path: Path) -> sqlite3.Connection:
    mmap_bytes = _env_int("RELIGION_SQLITE_MMAP_BYTES", DEFAULT_SQLITE_MMAP_BYTES, minimum=0, maximum=1024 * 1024 * 1024)
    cache_kib = _env_int("RELIGION_SQLITE_CACHE_KIB", DEFAULT_SQLITE_CACHE_KIB, minimum=512, maximum=128 * 1024)
    timeout = _env_float("RELIGION_SQLITE_TIMEOUT_SECONDS", DEFAULT_SQLITE_TIMEOUT_SECONDS, minimum=0.1, maximum=30.0)
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False, timeout=timeout)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    conn.execute("PRAGMA temp_store = FILE")
    conn.execute("PRAGMA busy_timeout = 2000")
    conn.execute(f"PRAGMA mmap_size = {mmap_bytes}")
    conn.execute(f"PRAGMA cache_size = -{cache_kib}")
    return conn


def _fetchall_with_deadline(conn: sqlite3.Connection, sql: str, params: list[Any] | tuple[Any, ...]) -> list[sqlite3.Row]:
    deadline_seconds = _env_float(
        "RELIGION_SQLITE_QUERY_DEADLINE_SECONDS",
        DEFAULT_SQLITE_QUERY_DEADLINE_SECONDS,
        minimum=0.2,
        maximum=30.0,
    )
    deadline = time.monotonic() + deadline_seconds

    def abort_if_expired() -> int:
        return 1 if time.monotonic() > deadline else 0

    conn.set_progress_handler(abort_if_expired, 20_000)
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.set_progress_handler(None, 0)


def _env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return max(minimum, min(value, maximum))


def _env_float(name: str, default: float, *, minimum: float, maximum: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError:
        return default
    return max(minimum, min(value, maximum))


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return bool(default)
    return raw.strip().lower() not in {"0", "false", "no", "off", ""}


def _mcq_heuristics_enabled() -> bool:
    return _env_flag("RELIGION_MCQ_HEURISTICS_ENABLED", False)


def _mcq_structure_enabled() -> bool:
    return _env_flag("RELIGION_MCQ_STRUCTURE_ENABLED", True)


def _query_tokens(text: str, limit: int = 8) -> list[str]:
    tokens: list[str] = []
    for token in TOKEN_RE.findall(text or ""):
        cleaned = token.strip("_").replace('"', "").replace("'", "")
        if len(cleaned) >= 2 and cleaned not in tokens:
            tokens.append(cleaned)
        if len(tokens) >= limit:
            break
    return tokens


def describe_query_expansion(profile: ProductProfile, query: str) -> dict[str, Any]:
    surface_terms = _effective_surface_terms(profile, query)
    expanded_terms = _expanded_terms(profile, query)
    variants = _precedent_query_variants(profile, query)
    return {
        "product": profile.key,
        "surfaceTerms": surface_terms,
        "expandedTerms": expanded_terms,
        "queryVariants": [
            {"label": label, "fts": fts, "termCount": len(tokens)}
            for label, fts, tokens in variants
        ],
    }


def _fts_query(text: str) -> str:
    tokens = _query_tokens(text)
    if not tokens:
        return '""'
    return " OR ".join(f'"{token}"' for token in tokens)


def _fts_from_terms(terms: list[str], *, operator: str = "OR", limit: int = 14) -> str:
    cleaned: list[str] = []
    for term in terms:
        token = str(term or "").strip().strip("'\"").lower()
        if len(token) >= 2 and token not in cleaned:
            cleaned.append(token)
        if len(cleaned) >= limit:
            break
    if not cleaned:
        return '""'
    joiner = " AND " if operator.upper() == "AND" else " OR "
    return joiner.join(f'"{token}"' for token in cleaned)


def _local_score(row: sqlite3.Row, fields: tuple[str, ...], tokens: list[str]) -> float:
    haystack = "\n".join(str(row[field] or "") for field in fields if field in row.keys()).lower()
    if not haystack or not tokens:
        return 0.0
    score = 0.0
    for token in tokens:
        lowered = token.lower()
        count = haystack.count(lowered)
        if count:
            score += min(count, 8)
    return score


def _authority_level(row: sqlite3.Row) -> float:
    text = "\n".join(str(row[field] or "") for field in ("source_dataset", "case_type", "full_text") if field in row.keys())
    match = re.search(r"authority_level\s*:\s*(\d{1,3})", text)
    if match:
        return max(0.0, min(float(match.group(1)), 100.0))
    dataset = str(row["source_dataset"] or "").lower() if "source_dataset" in row.keys() else ""
    case_type = str(row["case_type"] or "").lower() if "case_type" in row.keys() else ""
    if "scripture" in dataset or "scripture" in case_type:
        return 95.0
    if "classic_canon" in dataset or "classic_canon" in case_type:
        return 100.0
    if "classic_authoritative" in dataset or "classic_authoritative" in case_type:
        return 90.0
    if "hadith" in dataset or "canon" in dataset or "classic" in dataset:
        return 85.0
    if "materia_medica" in dataset or "materia_medica" in case_type or "formulary" in dataset or "formulary" in case_type:
        return 80.0
    if "clinical_guideline" in dataset or "clinical_guideline" in case_type:
        return 70.0
    if "comment" in dataset or "tafsir" in dataset or "shastra" in dataset:
        return 75.0
    if "case_record" in dataset or "case_record" in case_type:
        return 50.0
    if "modern_reference" in dataset or "modern_reference" in case_type:
        return 45.0
    return 40.0


def _rank_score(row: sqlite3.Row, fields: tuple[str, ...], tokens: list[str]) -> float:
    return _local_score(row, fields, tokens) + (_authority_level(row) / 10.0)


def search_documents(
    profile: ProductProfile,
    query: str,
    *,
    limit: int = 8,
    language: str = "",
    max_results: int | None = None,
    candidate_multiplier: int | None = None,
    context_query: str = "",
) -> list[SearchResult]:
    if max_results is None:
        max_results = _env_int("RELIGION_SEARCH_RESULT_LIMIT_MAX", 100, minimum=30, maximum=500)
    else:
        max_results = max(1, min(int(max_results), 2000))
    limit = max(1, min(int(limit or 8), max_results))
    if profile.db_shape == "precedents":
        return _search_precedents(
            profile,
            query,
            limit=limit,
            candidate_multiplier=candidate_multiplier,
            context_query=context_query,
        )
    if profile.db_shape == "documents":
        return _search_document_rows(
            profile,
            query,
            limit=limit,
            language=language,
            candidate_multiplier=candidate_multiplier,
        )
    raise ValueError(f"unsupported db_shape: {profile.db_shape}")


def get_source_by_id(profile: ProductProfile, source_id: str) -> SearchResult | None:
    canonical_id = str(source_id or "").strip()
    if not canonical_id:
        return None
    if profile.db_shape == "precedents":
        result = _get_precedent_by_id(profile, canonical_id)
        if result is None and profile.key == "tcm":
            return _get_tcm_passage_by_id(profile, canonical_id)
        return result
    if profile.db_shape == "documents":
        return _get_document_by_id(profile, canonical_id)
    raise ValueError(f"unsupported db_shape: {profile.db_shape}")


def _get_precedent_by_id(profile: ProductProfile, canonical_id: str) -> SearchResult | None:
    with _connect_readonly(profile.db_path) as conn:
        row = conn.execute(
            """
            SELECT
              canonical_id,
              source_dataset,
              source_path,
              title,
              case_number,
              court,
              decision_date,
              case_name,
              case_type,
              full_text
            FROM precedents
            WHERE canonical_id = ?
            LIMIT 1
            """,
            (canonical_id,),
        ).fetchone()
    if row is None:
        return None
    return _precedent_result(profile, row, [], [])


def _get_document_by_id(profile: ProductProfile, canonical_id: str) -> SearchResult | None:
    with _connect_readonly(profile.db_path) as conn:
        row = conn.execute(
            """
            SELECT
              canonical_id,
              source_dataset,
              source_path,
              source_url,
              doc_type,
              title,
              topic,
              disorder,
              pub_date,
              language,
              full_text
            FROM documents
            WHERE canonical_id = ?
            LIMIT 1
            """,
            (canonical_id,),
        ).fetchone()
    if row is None:
        return None
    return _document_result(profile, row, [])


def _get_tcm_passage_by_id(profile: ProductProfile, passage_id: str) -> SearchResult | None:
    try:
        with _connect_readonly(profile.db_path) as conn:
            row = conn.execute(
                """
                SELECT
                  p.passage_id,
                  p.source_id,
                  p.canonical_ref,
                  p.language,
                  p.text,
                  p.heading,
                  s.tradition,
                  s.school,
                  s.source_kind,
                  s.authority_level,
                  s.authority_label,
                  s.title,
                  s.author_body,
                  s.source_url
                FROM passages p
                JOIN sources s ON s.source_id = p.source_id
                WHERE p.passage_id = ?
                LIMIT 1
                """,
                (passage_id,),
            ).fetchone()
    except sqlite3.OperationalError:
        return None
    if row is None:
        return None
    return _tcm_passage_result(row)


def _search_precedents(
    profile: ProductProfile,
    query: str,
    *,
    limit: int,
    candidate_multiplier: int | None = None,
    context_query: str = "",
) -> list[SearchResult]:
    path = profile.db_path
    adapter = get_domain_adapter(profile)
    expansion_query = str(context_query or query)
    variants = _precedent_query_variants(profile, query)
    surface_tokens = _effective_surface_terms(profile, query)
    tokens = list(surface_tokens)
    multiplier = 20 if candidate_multiplier is None else max(1, int(candidate_multiplier))
    candidate_limit = max(limit * multiplier, 80)
    seen: set[str] = set()
    rows: list[sqlite3.Row] = []
    graph_relation_scores: dict[str, float] = {}
    with _connect_readonly(path) as conn:
        for _label, fts, variant_tokens in variants:
            if not fts or fts == '""':
                continue
            try:
                found = _query_precedents_fts(conn, fts, candidate_limit)
            except sqlite3.OperationalError:
                continue
            for row in found:
                canonical_id = str(row["canonical_id"] or "")
                if not canonical_id or canonical_id in seen:
                    continue
                seen.add(canonical_id)
                rows.append(row)
            tokens.extend(token for token in variant_tokens if token not in tokens)
        if _mcq_heuristics_enabled() and adapter.direct_option_terms(adapter.multiple_choice_option_terms(expansion_query)):
            exact_rows = _query_domain_exact_option_precedents(conn, profile, expansion_query, max(candidate_limit, 80))
            for row in exact_rows:
                canonical_id = str(row["canonical_id"] or "")
                if not canonical_id or canonical_id in seen:
                    continue
                seen.add(canonical_id)
                rows.append(row)
        seed_scores = {
            str(row["canonical_id"] or ""): _precedent_rank_score(profile, row, surface_tokens, tokens)
            for row in rows
            if str(row["canonical_id"] or "")
        }
        expanded_rows, relation_scores = adapter.expand_graph_rows(
            conn,
            rows,
            query=expansion_query,
            seed_scores=seed_scores,
            max_neighbors=max(limit * 3, 30),
            max_expanded=max(candidate_limit, 80),
        )
        graph_relation_scores.update(relation_scores)
        for row in expanded_rows:
            canonical_id = str(row["canonical_id"] or "")
            if not canonical_id or canonical_id in seen:
                continue
            seen.add(canonical_id)
            rows.append(row)
    rank_limit = limit
    if _mcq_structure_enabled() and adapter.parse_multiple_choice(expansion_query) is not None:
        rank_limit = max(limit, min(max(candidate_limit, limit), limit * 12))
    ranked = sorted(
        rows,
        key=lambda row: (
            -(
                _precedent_rank_score(profile, row, surface_tokens, tokens)
                + graph_relation_scores.get(str(row["canonical_id"] or ""), 0.0)
            ),
            str(row["canonical_id"] or ""),
        ),
    )[:rank_limit]
    results = [
        _precedent_result(
            profile,
            row,
            surface_tokens,
            tokens,
            score_bonus=graph_relation_scores.get(str(row["canonical_id"] or ""), 0.0),
        )
        for row in ranked
    ]
    if profile.key == "tcm":
        results = _merge_tcm_authoritative_passages(profile, query, results, limit=limit)
    return results[:limit]


def _precedent_rank_score(profile: ProductProfile, row: sqlite3.Row, surface_tokens: list[str], expanded_tokens: list[str]) -> float:
    fields = ("title", "case_number", "case_name", "case_type", "full_text")
    surface = _presence_score(row, fields, surface_tokens)
    surface_keys = {term.lower() for term in surface_tokens}
    semantic_terms = list(
        dict.fromkeys(term for term in expanded_tokens if term.lower() not in surface_keys)
    )
    semantic_bonus = 0.0
    if profile.key == "tcm":
        semantic_bonus = _tcm_semantic_group_hits(row, fields, semantic_terms) * 35.0
    expanded = _local_score(row, fields, expanded_tokens)
    return (
        (surface * 50.0)
        + semantic_bonus
        + expanded
        + _domain_intent_bonus(profile, row, expanded_tokens)
        + (_authority_level(row) / 10.0)
    )


def _presence_score(row: sqlite3.Row, fields: tuple[str, ...], tokens: list[str]) -> float:
    haystack = "\n".join(str(row[field] or "") for field in fields if field in row.keys()).lower()
    if not haystack or not tokens:
        return 0.0
    return float(sum(1 for token in tokens if token.lower() in haystack))


def _tcm_semantic_group_hits(
    row: sqlite3.Row,
    fields: tuple[str, ...],
    semantic_terms: list[str],
) -> float:
    haystack = "\n".join(str(row[field] or "") for field in fields if field in row.keys()).lower()
    if not haystack or not semantic_terms:
        return 0.0
    active_terms = {term.lower() for term in semantic_terms}
    hits = 0
    for _markers, expansion in TCM_QUERY_EXPANSIONS:
        group_terms = list(dict.fromkeys(token.lower() for token in _query_tokens(expansion)))
        if not active_terms.intersection(group_terms):
            continue
        if any(term in haystack for term in group_terms):
            hits += 1
    return float(hits)


def _query_precedents_fts(conn: sqlite3.Connection, fts: str, limit: int) -> list[sqlite3.Row]:
    return _fetchall_with_deadline(
        conn,
        """
        SELECT
          p.canonical_id,
          p.source_dataset,
          p.source_path,
          p.title,
          p.case_number,
          p.court,
          p.decision_date,
          p.case_name,
          p.case_type,
          p.full_text
        FROM precedents_fts
        JOIN precedents p ON p.canonical_id = precedents_fts.canonical_id
        WHERE precedents_fts MATCH ?
        LIMIT ?
        """,
        (fts, limit),
    )


def _query_domain_exact_option_precedents(
    conn: sqlite3.Connection,
    profile: ProductProfile,
    query: str,
    limit: int,
) -> list[sqlite3.Row]:
    adapter = get_domain_adapter(profile)
    terms = adapter.direct_option_terms(adapter.multiple_choice_option_terms(query))
    if not terms:
        return []
    rows: list[sqlite3.Row] = []
    seen: set[str] = set()
    for term in terms[:12]:
        like = f"%{term}%"
        try:
            found = _fetchall_with_deadline(
                conn,
                """
                SELECT
                  canonical_id,
                  source_dataset,
                  source_path,
                  title,
                  case_number,
                  court,
                  decision_date,
                  case_name,
                  case_type,
                  full_text
                FROM precedents
                WHERE title LIKE ?
                   OR case_number LIKE ?
                   OR case_name LIKE ?
                   OR case_type LIKE ?
                ORDER BY
                  CASE
                    WHEN source_dataset LIKE 'tcm-kmm/%' THEN 0
                    WHEN source_dataset LIKE 'tcm.zh.sylvanl.books%' THEN 1
                    WHEN source_dataset LIKE 'tcm.zh.sylvanl.medrec%' THEN 2
                    ELSE 3
                  END,
                  CASE
                    WHEN case_type LIKE '%classic_canon%' THEN 0
                    WHEN case_type LIKE '%classic_authoritative%' THEN 1
                    WHEN case_type LIKE '%formulary%' THEN 2
                    WHEN case_type LIKE '%case_record%' THEN 4
                    ELSE 3
                  END,
                  canonical_id
                LIMIT ?
                """,
                (like, like, like, like, max(2, limit // 2)),
            )
        except sqlite3.OperationalError:
            continue
        for row in found:
            canonical_id = str(row["canonical_id"] or "")
            if not canonical_id or canonical_id in seen:
                continue
            seen.add(canonical_id)
            rows.append(row)
            if len(rows) >= limit:
                return rows
    return rows


def _precedent_query_variants(profile: ProductProfile, query: str) -> list[tuple[str, str, list[str]]]:
    surface_terms = _effective_surface_terms(profile, query)
    expanded_terms = _expanded_terms(profile, query)
    adapter = get_domain_adapter(profile)
    values: list[tuple[str, list[str], str]] = []
    grouped_values: list[tuple[str, str, list[str]]] = []
    if profile.key == "lawkey" and len(surface_terms) >= 2:
        if len(surface_terms) <= 5:
            all_fts = _fts_from_terms(surface_terms, operator="AND")
            if all_fts:
                grouped_values.append(("lawkey_surface_all", all_fts, list(surface_terms)))
        for left_index, right_index in _bounded_balanced_term_pairs(len(surface_terms), maximum=6):
            pair_terms = [surface_terms[left_index], surface_terms[right_index]]
            pair_fts = _fts_from_terms(pair_terms, operator="AND")
            if pair_fts:
                grouped_values.append(
                    (
                        f"lawkey_surface_pair_{left_index + 1:02d}_{right_index + 1:02d}",
                        pair_fts,
                        pair_terms,
                    )
                )
    if profile.key == "tcm":
        han_groups = _tcm_han_expansion_groups(profile, query)
        if len(han_groups) >= 2:
            all_fts = _fts_from_grouped_terms(han_groups)
            if all_fts:
                grouped_values.append(("tcm_han_all", all_fts, [term for group in han_groups for term in group]))
            pair_count = 0
            for left_index in range(len(han_groups)):
                for right_index in range(left_index + 1, len(han_groups)):
                    pair_fts = _fts_from_grouped_terms([han_groups[left_index], han_groups[right_index]])
                    if pair_fts:
                        grouped_values.append(
                            (
                                f"tcm_han_pair_{left_index + 1:02d}_{right_index + 1:02d}",
                                pair_fts,
                                [*han_groups[left_index], *han_groups[right_index]],
                            )
                        )
                        pair_count += 1
                    if pair_count >= 6:
                        break
                if pair_count >= 6:
                    break
    if surface_terms:
        values.append(("surface", surface_terms, "OR"))
        if profile.key != "lawkey" and len(surface_terms) <= 5:
            values.append(("surface_all", surface_terms, "AND"))
    if expanded_terms:
        values.append(("expanded", [*surface_terms, *expanded_terms], "OR"))
        if profile.key == "tcm":
            han_terms = [term for term in expanded_terms if re.search(r"[\u3400-\u9fff]", term)][:14]
            if han_terms:
                values.append(("tcm_han_terms", han_terms, "OR"))
        focused = [term for term in expanded_terms if _is_arabic_text(term)][:6]
        if focused:
            values.append(("arabic_terms", focused, "OR"))
    option_terms = adapter.multiple_choice_option_terms(query) if _mcq_heuristics_enabled() else []
    if option_terms:
        for index, term in enumerate(option_terms[:10], start=1):
            tokens = _query_tokens(term)
            if tokens:
                values.append((f"{profile.key}_mcq_option_{index:02d}", tokens, "OR"))
    seen: set[str] = set()
    variants: list[tuple[str, str, list[str]]] = []
    for label, fts, terms in grouped_values:
        if fts and fts not in seen:
            variants.append((label, fts, terms))
            seen.add(fts)
    for label, terms, operator in values:
        fts = _fts_from_terms(terms, operator=operator)
        if fts and fts not in seen:
            variants.append((label, fts, terms))
            seen.add(fts)
    if not variants:
        variants.append(("empty", '""', []))
    return variants


def _bounded_balanced_term_pairs(term_count: int, *, maximum: int) -> list[tuple[int, int]]:
    """Prefer adjacent concepts so a long query is not anchored entirely on term zero."""
    pairs: list[tuple[int, int]] = []
    for distance in range(1, max(0, int(term_count))):
        for left_index in range(0, int(term_count) - distance):
            pairs.append((left_index, left_index + distance))
            if len(pairs) >= int(maximum):
                return pairs
    return pairs


def _tcm_han_expansion_groups(profile: ProductProfile, query: str) -> list[list[str]]:
    adapter = get_domain_adapter(profile)
    lowered = str(adapter.search_text(query) or "").lower()
    groups: list[list[str]] = []
    for markers, expansion in TCM_QUERY_EXPANSIONS:
        if not any(marker and marker.lower() in lowered for marker in markers):
            continue
        group: list[str] = []
        for token in _query_tokens(expansion):
            if re.search(r"[\u3400-\u9fff]", token) and token not in group:
                group.append(token)
        if group:
            groups.append(group[:6])
    return groups


def _fts_from_grouped_terms(groups: list[list[str]]) -> str:
    clauses: list[str] = []
    for group in groups:
        clause = _fts_from_terms(group, operator="OR", limit=6)
        if clause:
            clauses.append(f"({clause})")
    if len(clauses) < 2:
        return ""
    return " AND ".join(clauses)


def _expanded_terms(profile: ProductProfile, query: str) -> list[str]:
    if profile.key not in {"islam", "tcm"}:
        return []
    adapter = get_domain_adapter(profile)
    search_text = adapter.search_text(query)
    lowered = str(search_text or "").lower()
    terms: list[str] = []
    expansions = ISLAM_QUERY_EXPANSIONS if profile.key == "islam" else TCM_QUERY_EXPANSIONS
    for markers, expansion in expansions:
        if any(marker and marker.lower() in lowered for marker in markers):
            for token in _query_tokens(expansion):
                if token not in terms:
                    terms.append(token)
    if profile.key == "tcm":
        for term in adapter.multiple_choice_option_terms(query) if _mcq_heuristics_enabled() else []:
            for token in _query_tokens(term):
                if token not in terms:
                    terms.append(token)
    if profile.key == "islam":
        non_source_terms = [term for term in terms if term not in ISLAM_SOURCE_CONTROL_EXPANSION_TERMS]
        if non_source_terms:
            terms = [term for term in terms if term not in ISLAM_SOURCE_CONTROL_EXPANSION_TERMS]
    return terms[:32]


def _effective_surface_terms(profile: ProductProfile, query: str) -> list[str]:
    adapter = get_domain_adapter(profile)
    search_text = adapter.search_text(query)
    if profile.key == "islam":
        terms = _query_tokens(search_text, limit=adapter.surface_token_limit)
        return [term for term in terms if not _is_islam_low_signal_surface_term(term)]
    if profile.key == "tcm":
        terms = _query_tokens(search_text, limit=adapter.surface_token_limit)
        normalized_terms: list[str] = []
        for raw_term in terms:
            term = _normalize_tcm_surface_term(raw_term)
            if (
                not term
                or term in normalized_terms
                or adapter.is_low_signal_surface_term(term)
                or adapter.drop_surface_term(term)
            ):
                continue
            normalized_terms.append(term)
        return normalized_terms[: adapter.surface_term_limit]
    if profile.key == "lawkey":
        terms = _query_tokens(search_text, limit=adapter.surface_token_limit)
        return _lawkey_surface_terms(terms)
    terms = _query_tokens(search_text, limit=adapter.surface_token_limit)
    return terms


def _lawkey_surface_terms(terms: list[str]) -> list[str]:
    selected: list[str] = []
    for term in terms:
        normalized = _normalize_lawkey_surface_term(term)
        if not normalized:
            continue
        if normalized in LAWKEY_LOW_SIGNAL_SURFACE_TERMS:
            continue
        if normalized not in selected:
            selected.append(normalized)
    return selected[:8]


def _normalize_tcm_surface_term(term: str) -> str:
    normalized = str(term or "").strip("`'\"“”‘’()[]{}.,!?！？ㆍ·:;；，。")
    if not normalized or re.fullmatch(r"\d{1,3}세", normalized):
        return ""
    for suffix in (
        "으로",
        "에서",
        "에게",
        "부터",
        "까지",
        "처럼",
        "보다",
        "하며",
        "하고",
        "이며",
        "이고",
        "와",
        "과",
        "을",
        "를",
        "은",
        "는",
        "이",
        "가",
        "의",
        "에",
        "로",
        "도",
        "만",
        "고",
    ):
        if normalized.endswith(suffix) and len(normalized) - len(suffix) >= 1:
            normalized = normalized[: -len(suffix)]
            break
    if normalized in {
        "남자",
        "여자",
        "환자",
        "병원",
        "내원",
        "왔다",
        "오다",
        "배",
        "많이",
        "흘리나",
        "잘한다고",
        "한다",
        "하다",
        "치방",
    }:
        return ""
    return normalized


def _normalize_lawkey_surface_term(term: str) -> str:
    normalized = str(term or "").strip("`'\"“”‘’()[]{}.,!?！？ㆍ·:;；，。")
    if len(normalized) < 2:
        return ""
    for suffix in LAWKEY_TRAILING_PARTICLES:
        if normalized.endswith(suffix) and len(normalized) - len(suffix) >= 2:
            normalized = normalized[: -len(suffix)]
            break
    return normalized


def _is_islam_low_signal_surface_term(term: str) -> bool:
    normalized = str(term or "").strip("؟،,.!?")
    if normalized in ISLAM_LOW_SIGNAL_SURFACE_TERMS:
        return True
    lowered = normalized.lower()
    if lowered in ISLAM_LOW_SIGNAL_SURFACE_TERMS:
        return True
    korean_source_control = (
        "꾸란",
        "쿠란",
        "하디스",
        "주석",
        "타프시르",
        "근거",
        "학파",
        "종파",
        "단정",
        "알려",
        "나눠",
        "정리",
    )
    return any(marker in normalized for marker in korean_source_control)


def _domain_intent_bonus(profile: ProductProfile, row: sqlite3.Row, terms: list[str]) -> float:
    if profile.key == "islam":
        return _islam_intent_bonus(row, terms)
    if profile.key == "tcm":
        return _tcm_intent_bonus(row, terms)
    return 0.0


def _islam_intent_bonus(row: sqlite3.Row, terms: list[str]) -> float:
    term_set = set(terms)
    if not term_set:
        return 0.0
    text = "\n".join(str(row[field] or "") for field in ("title", "case_number", "case_name", "case_type", "full_text") if field in row.keys())
    lowered = text.lower()
    arabic = _arabic_plain(text)
    bonus = 0.0
    if {"riba", "usury", "ربا"} & term_set:
        if any(marker in lowered for marker in ("riba", "usury")) or "ربوا" in arabic:
            bonus += 520.0
    if {"prayer", "salah", "salat", "صلاة", "الصلوة", "صلوات", "times", "مواقيت"} & term_set:
        has_prayer = any(marker in lowered for marker in ("prayer", "salah", "salat")) or any(marker in arabic for marker in ("صلاة", "صلوة"))
        has_time = "time" in lowered or any(marker in arabic for marker in ("وقت", "مواقيت"))
        if has_prayer:
            bonus += 260.0
        if has_prayer and has_time:
            bonus += 220.0
    if {"nikah", "marriage", "wali", "guardian", "نكاح", "ولي"} & term_set:
        if any(marker in lowered for marker in ("nikah", "marriage", "wali", "guardian")) or any(marker in arabic for marker in ("نكاح", "زواج", "ولي")):
            bonus += 360.0
    if {"combine", "travel", "qasr", "سفر", "مسافر", "جمع", "قصر"} & term_set:
        has_travel = any(marker in lowered for marker in ("travel", "traveller", "journey")) or any(marker in arabic for marker in ("سفر", "مسافر"))
        has_prayer = any(marker in lowered for marker in ("prayer", "salah", "salat")) or any(marker in arabic for marker in ("صلاة", "صلوة"))
        has_combine_or_shorten = any(marker in lowered for marker in ("combine", "qasr", "shorten")) or any(marker in arabic for marker in ("جمع", "قصر"))
        if has_travel and has_prayer:
            bonus += 300.0
        if has_combine_or_shorten and has_prayer:
            bonus += 220.0
    return bonus


def _tcm_intent_bonus(row: sqlite3.Row, terms: list[str]) -> float:
    term_set = set(terms)
    if not term_set:
        return 0.0
    text = "\n".join(str(row[field] or "") for field in ("title", "case_number", "case_name", "case_type", "full_text", "source_dataset") if field in row.keys())
    lowered = text.lower()
    bonus = 0.0
    if {"감초", "甘草", "licorice", "glycyrrhiza", "gancao"} & term_set:
        if any(marker in lowered for marker in ("감초", "甘草", "licorice", "glycyrrhiza", "gancao")):
            bonus += 240.0
    if {"임신", "妊娠", "pregnancy", "gestation", "pregnant", "금기", "禁忌", "contraindication"} & term_set:
        if any(marker in lowered for marker in ("임신", "妊娠", "pregnancy", "gestation", "禁忌", "contraindication", "금기")):
            bonus += 220.0
    if {"불면", "不眠", "失眠", "insomnia"} & term_set:
        if any(marker in lowered for marker in ("불면", "不眠", "失眠", "insomnia")):
            bonus += 180.0
    if {"소화불량", "소화", "비위", "脾胃", "消化", "indigestion", "dyspepsia"} & term_set:
        if any(marker in lowered for marker in ("소화", "비위", "脾胃", "消化", "indigestion", "dyspepsia")):
            bonus += 180.0
    option_terms = _tcm_direct_option_terms(terms) if _mcq_heuristics_enabled() else []
    if option_terms:
        direct_hits = [term for term in option_terms if term.lower() in lowered]
        if direct_hits:
            bonus += 1400.0 + min(360.0, 120.0 * len(direct_hits))
            if any(marker in lowered for marker in ("formulary", "classic_authoritative", "classic_canon", "korean-classic")):
                bonus += 260.0
        elif any(marker in lowered for marker in ("소변", "방광", "위완", "분문", "해부", "urine", "bladder", "anatom")):
            bonus -= 180.0
    return bonus


def _merge_tcm_authoritative_passages(
    profile: ProductProfile,
    query: str,
    results: list[SearchResult],
    *,
    limit: int,
) -> list[SearchResult]:
    extra = _search_tcm_authoritative_passages(profile, query, limit=max(4, limit))
    seen: set[str] = set()
    merged: list[SearchResult] = []
    for row in [*extra, *results]:
        if not row.canonical_id or row.canonical_id in seen:
            continue
        seen.add(row.canonical_id)
        merged.append(row)
    ranked = _sort_tcm_results_for_query(query, merged)
    balanced = _balance_tcm_mcq_option_results(query, ranked, limit) if _mcq_heuristics_enabled() else None
    if balanced is not None:
        return balanced
    return _diversify_tcm_results(ranked, limit)


def _search_tcm_authoritative_passages(profile: ProductProfile, query: str, *, limit: int) -> list[SearchResult]:
    lookups = _tcm_passage_lookups(query)
    if not lookups:
        return []
    out: list[SearchResult] = []
    seen: set[str] = set()
    try:
        conn_cm = _connect_readonly(profile.db_path)
    except Exception:
        return []
    with conn_cm as conn:
        for source_ids, term in lookups:
            placeholders = ",".join("?" for _ in source_ids)
            like = f"%{term}%"
            try:
                rows = _fetchall_with_deadline(
                    conn,
                    f"""
                    SELECT
                      p.passage_id,
                      p.source_id,
                      p.canonical_ref,
                      p.language,
                      p.text,
                      p.heading,
                      s.tradition,
                      s.school,
                      s.source_kind,
                      s.authority_level,
                      s.authority_label,
                      s.title,
                      s.author_body,
                      s.source_url
                    FROM passages p
                    JOIN sources s ON s.source_id = p.source_id
                    WHERE p.source_id IN ({placeholders})
                      AND (p.text LIKE ? OR p.heading LIKE ?)
                    LIMIT ?
                    """,
                    [*source_ids, like, like, max(2, limit // 2)],
                )
            except sqlite3.OperationalError:
                continue
            for row in rows:
                canonical_id = str(row["passage_id"] or "")
                if not canonical_id or canonical_id in seen:
                    continue
                seen.add(canonical_id)
                out.append(_tcm_passage_result(row))
                if len(out) >= limit:
                    return out
    return out


def _tcm_passage_lookups(query: str) -> list[tuple[tuple[str, ...], str]]:
    lowered = str(query or "").lower()
    lookups: list[tuple[tuple[str, ...], str]] = []
    if any(marker in lowered for marker in ("감초", "甘草", "licorice", "glycyrrhiza", "gancao")):
        lookups.append((TCM_MATERIA_PASSAGE_SOURCE_IDS, "甘草"))
    if any(marker in lowered for marker in ("금기", "禁忌", "contraindication", "caution", "safety")):
        lookups.append((TCM_MATERIA_PASSAGE_SOURCE_IDS, "禁忌"))
    adapter = get_domain_adapter("tcm")
    if not _mcq_heuristics_enabled():
        return lookups
    for term in adapter.multiple_choice_option_terms(query)[:8]:
        lookups.append((TCM_FORMULARY_PASSAGE_SOURCE_IDS, term))
    return lookups


def _tcm_passage_result(row: sqlite3.Row) -> SearchResult:
    source_kind = str(row["source_kind"] or "")
    title = str(row["title"] or "")
    heading = _strip_markup(str(row["heading"] or ""))
    text = _strip_markup(str(row["text"] or ""))
    metadata = (
        "[META]\n"
        "religion: tcm-kmm\n"
        f"tradition: {row['tradition'] or ''}\n"
        f"school: {row['school'] or ''}\n"
        f"authority_level: {row['authority_level'] or 0}\n"
        f"source_kind: {source_kind}\n"
        f"authority_label: {row['authority_label'] or ''}\n\n"
    )
    return SearchResult(
        canonical_id=str(row["passage_id"] or ""),
        source_dataset=f"tcm-kmm/{row['tradition'] or 'tcm'}/{row['school'] or ''}/{source_kind}",
        source_path=str(row["source_id"] or ""),
        source_url=str(row["source_url"] or ""),
        title=title,
        citation=str(row["canonical_ref"] or row["passage_id"] or ""),
        authority_body=str(row["author_body"] or title),
        source_date="",
        case_name=heading,
        case_type=f"{source_kind}_passage",
        full_text=metadata + f"[HEADING]\n{heading}\n\n[PRIMARY TEXT]\n{text}",
        language=str(row["language"] or ""),
        tradition=str(row["tradition"] or ""),
        school=str(row["school"] or ""),
        source_kind=source_kind,
        authority_level=int(row["authority_level"] or 0),
        authority_label=str(row["authority_label"] or ""),
    )


def _tcm_result_rank_key(row: SearchResult) -> tuple[int, int, str]:
    kind = row.source_kind or row.case_type or ""
    priority = {
        "classic_canon": 0,
        "materia_medica": 1,
        "formulary": 2,
        "clinical_guideline": 3,
        "classic_authoritative": 4,
        "commentary_on_classic": 5,
        "modern_reference": 6,
        "case_record": 8,
    }.get(kind, 7)
    return (priority, -int(row.authority_level or 0), row.canonical_id)


def _sort_tcm_results_for_query(query: str, rows: list[SearchResult]) -> list[SearchResult]:
    adapter = get_domain_adapter("tcm")
    option_terms = adapter.multiple_choice_option_terms(query) if _mcq_heuristics_enabled() else []
    if not option_terms:
        if not rows:
            return []
        best_score = min(float(row.score) for row in rows)

        def open_query_rank_key(row: SearchResult) -> tuple[int, int, int, float, str]:
            authority_key = _tcm_result_rank_key(row)
            return (
                int(max(0.0, float(row.score) - best_score) // 100.0),
                authority_key[0],
                authority_key[1],
                float(row.score),
                authority_key[2],
            )

        return sorted(
            rows,
            key=open_query_rank_key,
        )
    return sorted(
        rows,
        key=lambda row: (
            -_tcm_result_option_match_score(row, option_terms),
            *_tcm_result_rank_key(row),
        ),
    )


def _balance_tcm_mcq_option_results(query: str, rows: list[SearchResult], limit: int) -> list[SearchResult] | None:
    adapter = get_domain_adapter("tcm")
    parsed = adapter.parse_multiple_choice(query)
    if parsed is None or len(parsed.options) < 3:
        return None
    selected: list[SearchResult] = []
    seen: set[str] = set()

    def add(row: SearchResult) -> None:
        if len(selected) >= limit:
            return
        if not row.canonical_id or row.canonical_id in seen:
            return
        seen.add(row.canonical_id)
        selected.append(row)

    for option in parsed.options:
        if len(selected) >= limit:
            break
        terms = adapter.direct_option_terms(adapter.option_aliases(option.text))
        if not terms:
            continue
        match = next((row for row in rows if row.canonical_id not in seen and _tcm_result_has_any_term(row, terms)), None)
        if match is not None:
            add(match)

    for row in _diversify_tcm_results(rows, limit):
        add(row)
    if not selected:
        return None
    return selected[:limit]


def _tcm_result_option_match_score(row: SearchResult, option_terms: list[str]) -> float:
    text = "\n".join(
        [
            row.title or "",
            row.citation or "",
            row.case_name or "",
            row.case_type or "",
            row.source_dataset or "",
            row.full_text or "",
        ]
    ).lower()
    score = 0.0
    adapter = get_domain_adapter("tcm")
    for term in adapter.direct_option_terms(option_terms):
        if term.lower() in text:
            score += 1.0
    kind = row.source_kind or row.case_type or ""
    if score and any(marker in kind for marker in ("formulary", "classic_authoritative", "classic_canon")):
        score += 1.0
    return score


def _tcm_result_has_any_term(row: SearchResult, terms: list[str]) -> bool:
    text = "\n".join(
        [
            row.title or "",
            row.citation or "",
            row.case_name or "",
            row.case_type or "",
            row.source_dataset or "",
            row.full_text or "",
        ]
    ).lower()
    return any(term.lower() in text for term in terms)


def _tcm_direct_option_terms(terms: list[str]) -> list[str]:
    return get_domain_adapter("tcm").direct_option_terms(terms)


def _diversify_tcm_results(rows: list[SearchResult], limit: int) -> list[SearchResult]:
    selected: list[SearchResult] = []
    seen: set[str] = set()
    kind_counts: dict[str, int] = {}
    kind_cap = 3 if limit >= 6 else 2
    case_cap = 2 if limit >= 5 else 1

    def add(row: SearchResult, *, cap: bool) -> None:
        if len(selected) >= limit:
            return
        if not row.canonical_id or row.canonical_id in seen:
            return
        kind = row.source_kind or row.case_type or ""
        if cap and kind_counts.get(kind, 0) >= kind_cap:
            return
        if cap and kind == "case_record" and kind_counts.get(kind, 0) >= case_cap:
            return
        seen.add(row.canonical_id)
        kind_counts[kind] = kind_counts.get(kind, 0) + 1
        selected.append(row)

    for row in rows:
        add(row, cap=True)
    if len(selected) < limit:
        for row in rows:
            add(row, cap=False)
    return selected


def _strip_markup(value: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", "", value or "").split())


def _arabic_plain(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch) and ch != "\u0640")


def _is_arabic_text(value: str) -> bool:
    return re.search(r"[\u0600-\u06ff]", value or "") is not None


def _precedent_result(
    profile: ProductProfile,
    row: sqlite3.Row,
    surface_tokens: list[str],
    tokens: list[str],
    *,
    score_bonus: float = 0.0,
) -> SearchResult:
    metadata = _metadata_from_precedent_row(row)
    return SearchResult(
            canonical_id=str(row["canonical_id"] or ""),
            source_dataset=str(row["source_dataset"] or ""),
            source_path=str(row["source_path"] or ""),
            title=str(row["title"] or ""),
            citation=str(row["case_number"] or ""),
            authority_body=str(row["court"] or ""),
            source_date=str(row["decision_date"] or ""),
            case_name=str(row["case_name"] or ""),
            case_type=str(row["case_type"] or ""),
            full_text=str(row["full_text"] or ""),
            score=-(_precedent_rank_score(profile, row, surface_tokens, tokens) + max(0.0, float(score_bonus or 0.0))),
            tradition=metadata.get("tradition", ""),
            school=metadata.get("school", ""),
            source_kind=metadata.get("source_kind", ""),
            authority_level=int(metadata.get("authority_level") or 0),
            authority_label=metadata.get("authority_label", ""),
        )


def _metadata_from_precedent_row(row: sqlite3.Row) -> dict[str, Any]:
    text = str(row["full_text"] or "") if "full_text" in row.keys() else ""
    metadata: dict[str, Any] = {}
    for key, value in re.findall(r"^[ \t]*([a-z_]+)[ \t]*:[ \t]*([^\r\n]*)", text, flags=re.MULTILINE):
        metadata[key] = value.strip()
    dataset = str(row["source_dataset"] or "") if "source_dataset" in row.keys() else ""
    parts = dataset.split("/")
    if not metadata.get("tradition") and len(parts) > 1:
        metadata["tradition"] = parts[1]
    if not metadata.get("school") and len(parts) > 2:
        metadata["school"] = parts[2]
    if not metadata.get("source_kind") and parts:
        metadata["source_kind"] = parts[-1]
    if not metadata.get("authority_level"):
        metadata["authority_level"] = int(_authority_level(row))
    else:
        try:
            metadata["authority_level"] = int(metadata["authority_level"])
        except ValueError:
            metadata["authority_level"] = int(_authority_level(row))
    return metadata


def _search_document_rows(
    profile: ProductProfile,
    query: str,
    *,
    limit: int,
    language: str = "",
    candidate_multiplier: int | None = None,
) -> list[SearchResult]:
    for query_variant, fts in _document_query_variants(profile, query):
        variant_language = language if query_variant == query else ""
        try:
            rows = _search_documents(
                profile.db_path,
                query_variant,
                fts=fts,
                limit=limit,
                language=variant_language,
                product_key=profile.key,
                candidate_multiplier=candidate_multiplier,
            )
        except sqlite3.OperationalError:
            rows = []
        if not rows and variant_language:
            try:
                rows = _search_documents(
                    profile.db_path,
                    query_variant,
                    fts=fts,
                    limit=limit,
                    language="",
                    product_key=profile.key,
                    candidate_multiplier=candidate_multiplier,
                )
            except sqlite3.OperationalError:
                rows = []
        if rows:
            return rows
    return []


def _document_query_variants(profile: ProductProfile, query: str) -> list[tuple[str, str]]:
    if profile.key != "simli":
        return [(query, _fts_query(query))]
    additions: list[str] = []
    for korean, english in SIMLI_KO_QUERY_EXPANSIONS:
        if korean in query:
            additions.append(english)
    surface_terms = _query_tokens(query)
    variants: list[tuple[str, str]] = []
    if not additions:
        variants.append((query, _fts_query(query)))
        return variants
    focused_terms = []
    for term in additions:
        for token in _query_tokens(term):
            if token not in focused_terms:
                focused_terms.append(token)
    if len(focused_terms) >= 2:
        focused_all = " ".join(focused_terms)
        variants.append((focused_all, _fts_from_terms(focused_terms, operator="AND", limit=5)))
    if focused_terms:
        variants.append((" ".join(focused_terms), _fts_from_terms(focused_terms, operator="OR", limit=5)))
    if surface_terms:
        variants.append((query, _fts_from_terms(surface_terms, operator="AND", limit=5)))
    seen: set[str] = set()
    deduped: list[tuple[str, str]] = []
    for value, fts in variants:
        if fts in seen:
            continue
        seen.add(fts)
        deduped.append((value, fts))
    return deduped or [(query, _fts_query(query))]


def _search_documents(
    path: Path,
    query: str,
    *,
    fts: str | None = None,
    limit: int,
    language: str = "",
    product_key: str = "",
    candidate_multiplier: int | None = None,
) -> list[SearchResult]:
    fts = fts or _fts_query(query)
    tokens = _query_tokens(query)
    source_language = "" if product_key == "simli" else language
    multiplier = 20 if candidate_multiplier is None else max(1, int(candidate_multiplier))
    candidate_limit = max(limit * multiplier, 80)
    if product_key == "simli" and candidate_multiplier is None:
        candidate_limit = _simli_candidate_fetch_limit(limit)
    params: list[Any] = [fts]
    lang_filter = ""
    if source_language:
        lang_filter = " AND COALESCE(d.language, '') IN ('', ?)"
        params.append(source_language)
    params.append(candidate_limit)
    with _connect_readonly(path) as conn:
        if product_key == "simli":
            role_hint_rows = _search_simli_role_hint_rows(conn, query, language=source_language, limit=limit)
            if role_hint_rows:
                rows = _dedupe_document_rows(role_hint_rows)
            else:
                rows = _fetchall_with_deadline(
                    conn,
                    f"""
                    SELECT
                      d.canonical_id,
                      d.source_dataset,
                      d.source_path,
                      d.source_url,
                      d.doc_type,
                      d.title,
                      d.topic,
                      d.disorder,
                      d.pub_date,
                      d.language,
                      d.full_text
                    FROM documents_fts
                    JOIN documents d ON d.rowid = documents_fts.rowid
                    WHERE documents_fts MATCH ?
                    {lang_filter}
                    LIMIT ?
                    """,
                    params,
                )
                default_rows = _simli_default_evidence_rows(rows)
                if len(default_rows) >= _simli_authoritative_skip_floor(limit):
                    rows = _dedupe_document_rows(default_rows)
                else:
                    rows = _dedupe_document_rows(
                        [
                            *default_rows,
                            *_search_simli_authoritative_rows_by_rowid_range(
                                conn,
                                fts,
                                language=language,
                                limit=_simli_authoritative_fetch_limit(limit),
                                db_key=str(path),
                            ),
                        ]
                    )
        else:
            rows = _fetchall_with_deadline(
                conn,
                f"""
                SELECT
                  d.canonical_id,
                  d.source_dataset,
                  d.source_path,
                  d.source_url,
                  d.doc_type,
                  d.title,
                  d.topic,
                  d.disorder,
                  d.pub_date,
                  d.language,
                  d.full_text
                FROM documents_fts
                JOIN documents d ON d.rowid = documents_fts.rowid
                WHERE documents_fts MATCH ?
                {lang_filter}
                LIMIT ?
                """,
                params,
            )
    ordered = sorted(
        rows,
        key=lambda row: _document_rank_key(row, tokens, product_key=product_key),
    )
    ranked = _diversify_simli_rows(ordered, limit) if product_key == "simli" else ordered[:limit]
    return [_document_result_for_product(product_key, row, tokens) for row in ranked]


def _document_result(profile: ProductProfile, row: sqlite3.Row, tokens: list[str]) -> SearchResult:
    return _document_result_for_product(profile.key, row, tokens)


def _document_result_for_product(product_key: str, row: sqlite3.Row, tokens: list[str]) -> SearchResult:
    return SearchResult(
        canonical_id=str(row["canonical_id"] or ""),
        source_dataset=str(row["source_dataset"] or ""),
        source_path=str(row["source_path"] or ""),
        source_url=str(row["source_url"] or ""),
        title=str(row["title"] or ""),
        citation=str(row["canonical_id"] or ""),
        authority_body=str(row["source_dataset"] or ""),
        source_date=str(row["pub_date"] or ""),
        case_name=str(row["topic"] or row["disorder"] or ""),
        case_type=str(row["doc_type"] or ""),
        full_text=str(row["full_text"] or ""),
        score=-_document_rank_score(row, tokens, product_key=product_key),
        language=str(row["language"] or ""),
        source_kind=str(row["doc_type"] or ""),
        authority_level=int(_simli_authority_level(row)) if product_key == "simli" else 0,
        authority_label=_simli_evidence_tier(row) if product_key == "simli" else "",
    )


def _simli_candidate_fetch_limit(limit: int) -> int:
    requested = max(1, int(limit or 1))
    default_cap = _env_int("RELIGION_SIMLI_FTS_CANDIDATE_LIMIT_MAX", 500, minimum=120, maximum=5000)
    candidate_limit = max(requested * 4, min(240, default_cap))
    return min(candidate_limit, default_cap)


def _simli_authoritative_fetch_limit(limit: int) -> int:
    requested = max(1, int(limit or 1))
    default_cap = _env_int("RELIGION_SIMLI_AUTHORITATIVE_CANDIDATE_LIMIT_MAX", 500, minimum=80, maximum=5000)
    candidate_limit = max(requested * 4, 80)
    return min(candidate_limit, default_cap)


def _simli_authoritative_range_budget_seconds() -> float:
    return _env_float(
        "RELIGION_SIMLI_AUTHORITATIVE_RANGE_BUDGET_SECONDS",
        0.3,
        minimum=0.05,
        maximum=30.0,
    )


def _simli_authoritative_skip_floor(limit: int) -> int:
    requested = max(1, int(limit or 1))
    default_floor = min(requested, 20)
    return _env_int("RELIGION_SIMLI_AUTHORITATIVE_SKIP_FLOOR", default_floor, minimum=1, maximum=max(1, requested))


def _document_rank_key(row: sqlite3.Row, tokens: list[str], *, product_key: str) -> tuple[float, int, str]:
    score = _document_rank_score(row, tokens, product_key=product_key)
    priority = _simli_source_priority(row) if product_key == "simli" else 999
    return (-score, priority, str(row["canonical_id"] or ""))


def _document_rank_score(row: sqlite3.Row, tokens: list[str], *, product_key: str) -> float:
    score = _local_score(row, ("title", "topic", "disorder", "full_text"), tokens)
    if product_key == "simli":
        score += _simli_authority_level(row)
        score += SIMLI_DOC_TYPE_BIAS.get(str(row["doc_type"] or ""), 0.0)
    return score


def _dedupe_document_rows(rows: list[sqlite3.Row]) -> list[sqlite3.Row]:
    seen: set[str] = set()
    out: list[sqlite3.Row] = []
    for row in rows:
        canonical_id = str(row["canonical_id"] or "")
        if not canonical_id or canonical_id in seen:
            continue
        seen.add(canonical_id)
        out.append(row)
    return out


def _simli_default_evidence_rows(rows: list[sqlite3.Row]) -> list[sqlite3.Row]:
    return [row for row in rows if _simli_is_default_evidence_row(row)]


def _simli_role_hints(query: str) -> list[str]:
    text = str(query or "").lower()
    roles: list[str] = []
    for role, hints in SIMLI_ROLE_HINT_TOKENS.items():
        if any(hint in text for hint in hints):
            roles.append(role)
    return roles


def _simli_role_hint_result_limit(limit: int) -> int:
    requested = max(1, int(limit or 1))
    default_cap = _env_int("RELIGION_SIMLI_ROLE_HINT_LIMIT_MAX", 24, minimum=10, maximum=500)
    return min(requested, default_cap)


def _simli_focus_terms(query: str) -> list[str]:
    terms: list[str] = []

    def add(term: str) -> None:
        token = str(term or "").strip().lower()
        if len(token) >= 2 and token not in SIMLI_ROLE_HINT_LOW_SIGNAL_TOKENS and token not in terms:
            terms.append(token)

    for korean, english in SIMLI_KO_QUERY_EXPANSIONS:
        if korean in query:
            for token in _query_tokens(english):
                add(token)
    for token in _query_tokens(query):
        add(token)
    return terms[:12]


def _search_simli_role_hint_rows(
    conn: sqlite3.Connection,
    query: str,
    *,
    language: str,
    limit: int,
) -> list[sqlite3.Row]:
    roles = _simli_role_hints(query)
    if not roles or limit <= 0:
        return []
    doc_types: list[str] = []
    for role in roles:
        for doc_type in SIMLI_ROLE_HINT_DOC_TYPES.get(role, ()):
            if doc_type not in doc_types:
                doc_types.append(doc_type)
    if not doc_types:
        return []
    result_limit = _simli_role_hint_result_limit(limit)
    fetch_limit = max(result_limit * 4, 80)
    params: list[Any] = [*doc_types]
    lang_filter = ""
    if language:
        lang_filter = " AND COALESCE(d.language, '') IN ('', ?)"
        params.append(language)
    focus_terms = _simli_focus_terms(query)
    focus_filter = ""
    if focus_terms:
        focus_clauses: list[str] = []
        for term in focus_terms[:6]:
            focus_clauses.append(
                "(COALESCE(d.title, '') LIKE ? OR COALESCE(d.topic, '') LIKE ? "
                "OR COALESCE(d.disorder, '') LIKE ? OR COALESCE(d.full_text, '') LIKE ?)"
            )
            pattern = f"%{term}%"
            params.extend([pattern, pattern, pattern, pattern])
        focus_filter = " AND (" + " OR ".join(focus_clauses) + ")"
    params.append(fetch_limit)
    rows = _fetchall_with_deadline(
        conn,
        f"""
        SELECT
          d.canonical_id,
          d.source_dataset,
          d.source_path,
          d.source_url,
          d.doc_type,
          d.title,
          d.topic,
          d.disorder,
          d.pub_date,
          d.language,
          d.full_text
        FROM documents d INDEXED BY idx_documents_type
        WHERE d.doc_type IN ({",".join("?" for _ in doc_types)})
        {lang_filter}
        {focus_filter}
        LIMIT ?
        """,
        params,
    )
    if not rows:
        return []
    ordered = sorted(rows, key=lambda row: _document_rank_key(row, focus_terms, product_key="simli"))
    return _diversify_simli_rows(ordered, result_limit)


def _simli_is_default_evidence_row(row: sqlite3.Row) -> bool:
    dataset = str(row["source_dataset"] or "") if "source_dataset" in row.keys() else ""
    doc_type = str(row["doc_type"] or "") if "doc_type" in row.keys() else ""
    if dataset in SIMLI_QUARANTINED_SOURCES:
        return False
    if dataset.startswith("gutenberg:"):
        return False
    if doc_type in SIMLI_EXCLUDED_DOC_TYPES:
        return False
    if SIMLI_ALLOWED_DOC_TYPES and doc_type and doc_type not in SIMLI_ALLOWED_DOC_TYPES:
        return False
    if doc_type in SIMLI_LOW_CONFIDENCE_DOC_TYPES:
        return False
    if dataset in SIMLI_LOW_CONFIDENCE_SOURCES:
        return False
    if dataset.startswith("hf:") and dataset != "hf:pmc_patients":
        return False
    if dataset.startswith("gh:"):
        return False
    return True


def _search_simli_authoritative_rows_by_rowid_range(
    conn: sqlite3.Connection,
    fts: str,
    *,
    language: str,
    limit: int,
    db_key: str,
) -> list[sqlite3.Row]:
    if not fts or fts == '""' or limit <= 0:
        return []
    out: list[sqlite3.Row] = []
    seen: set[str] = set()
    per_source = max(6, min(24, limit // 6 or 6))
    started = time.monotonic()
    budget_seconds = _simli_authoritative_range_budget_seconds()
    for _dataset, lo, hi in _simli_authoritative_rowid_ranges(conn, db_key=db_key):
        if len(out) >= limit:
            break
        if time.monotonic() - started >= budget_seconds:
            break
        try:
            rowid_rows = _fetchall_with_deadline(
                conn,
                """
                SELECT rowid
                FROM documents_fts
                WHERE documents_fts MATCH ?
                  AND rowid BETWEEN ? AND ?
                LIMIT ?
                """,
                (fts, lo, hi, per_source),
            )
        except sqlite3.OperationalError:
            continue
        rowids = [int(row[0]) for row in rowid_rows]
        if not rowids:
            continue
        for row in _fetch_simli_document_rows_by_rowid(conn, rowids, language=language):
            canonical_id = str(row["canonical_id"] or "")
            if not canonical_id or canonical_id in seen:
                continue
            if not _simli_is_default_evidence_row(row):
                continue
            seen.add(canonical_id)
            out.append(row)
            if len(out) >= limit:
                break
    return out


def _simli_authoritative_rowid_ranges(conn: sqlite3.Connection, *, db_key: str) -> list[tuple[str, int, int]]:
    cached = _SIMLI_ROWID_RANGES_CACHE.get(db_key)
    if cached is not None:
        return cached
    ranges: list[tuple[str, int, int]] = []
    for dataset in SIMLI_AUTHORITATIVE_SOURCE_PRIORITY:
        try:
            lo = conn.execute(
                "SELECT rowid FROM documents WHERE source_dataset = ? ORDER BY rowid LIMIT 1",
                (dataset,),
            ).fetchone()
            hi = conn.execute(
                "SELECT rowid FROM documents WHERE source_dataset = ? ORDER BY rowid DESC LIMIT 1",
                (dataset,),
            ).fetchone()
        except sqlite3.OperationalError:
            continue
        if lo is not None and hi is not None:
            ranges.append((dataset, int(lo[0]), int(hi[0])))
    _SIMLI_ROWID_RANGES_CACHE[db_key] = ranges
    return ranges


def _fetch_simli_document_rows_by_rowid(
    conn: sqlite3.Connection,
    rowids: list[int],
    *,
    language: str,
) -> list[sqlite3.Row]:
    if not rowids:
        return []
    placeholders = ",".join("?" for _ in rowids)
    params: list[Any] = list(rowids)
    lang_filter = ""
    if language:
        lang_filter = " AND COALESCE(language, '') IN ('', ?)"
        params.append(language)
    rows = conn.execute(
        f"""
        SELECT
          rowid,
          canonical_id,
          source_dataset,
          source_path,
          source_url,
          doc_type,
          title,
          topic,
          disorder,
          pub_date,
          language,
          full_text
        FROM documents
        WHERE rowid IN ({placeholders})
        {lang_filter}
        """,
        params,
    ).fetchall()
    by_rowid_order = {rowid: index for index, rowid in enumerate(rowids)}
    return sorted(rows, key=lambda row: by_rowid_order.get(int(row["rowid"]) if "rowid" in row.keys() else 0, 999999))


def _simli_source_priority(row: sqlite3.Row) -> int:
    dataset = str(row["source_dataset"] or "") if "source_dataset" in row.keys() else ""
    for index, prefix in enumerate(SIMLI_AUTHORITATIVE_SOURCE_PRIORITY):
        if dataset == prefix or dataset.startswith(prefix):
            return index
    return 999


def _simli_authority_level(row: sqlite3.Row) -> float:
    priority = _simli_source_priority(row)
    if priority < 999:
        return max(0.0, 100.0 - (priority * 5.0))
    return 40.0


def _simli_evidence_tier(row: sqlite3.Row) -> str:
    doc_type = str(row["doc_type"] or "") if "doc_type" in row.keys() else ""
    if doc_type in {"guideline", "guideline_chunk", "dsm5_chunk", "icd11_entity"}:
        return "tier A"
    if doc_type in {"research_paper", "paper"}:
        return "tier B"
    if doc_type in {"preprint", "patient_case"}:
        return "tier C"
    return "tier D"


def _diversify_simli_rows(rows: list[sqlite3.Row], limit: int) -> list[sqlite3.Row]:
    if limit <= 0:
        return []
    selected: list[sqlite3.Row] = []
    selected_ids: set[str] = set()
    dataset_counts: dict[str, int] = {}
    first_pass_cap = 2 if limit >= 5 else 1

    def add(row: sqlite3.Row, *, cap: int | None) -> None:
        if len(selected) >= limit:
            return
        canonical_id = str(row["canonical_id"] or "")
        dataset = str(row["source_dataset"] or "")
        if not canonical_id or canonical_id in selected_ids:
            return
        if cap is not None and dataset_counts.get(dataset, 0) >= cap:
            return
        selected_ids.add(canonical_id)
        dataset_counts[dataset] = dataset_counts.get(dataset, 0) + 1
        selected.append(row)

    for row in rows:
        add(row, cap=first_pass_cap)
    if len(selected) < limit:
        for row in rows:
            add(row, cap=None)
    return selected


def to_beta6_selected_record(result: SearchResult) -> dict[str, Any]:
    text = result.full_text
    return {
        "file_id": result.canonical_id,
        "relative_path": result.source_path,
        "absolute_path": result.source_path,
        "document_title": result.title or result.citation or result.canonical_id,
        "doc_type": result.case_type or "txt",
        "source_group": "structured_precedent",
        "token_count": max(1, len(text) // 4),
        "anchor_text": " ".join(text.split())[:500],
        "extracted_text": text,
        "candidate_boundaries": [],
        "is_direct_evidence": False,
        "is_format_sample": False,
        "content_hash": "",
        "duplicate_paths": [],
        "case_number": result.citation,
        "court": result.authority_body,
        "decision_date": result.source_date,
        "case_name": result.case_name,
        "metadata": {
            "tradition": result.tradition,
            "school": result.school,
            "sourceKind": result.source_kind,
            "authorityLevel": result.authority_level,
            "authorityLabel": result.authority_label,
            "language": result.language,
            "dataset": result.source_dataset,
        },
    }
