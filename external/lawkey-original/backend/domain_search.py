from __future__ import annotations

import os
import re
import sqlite3
import threading
import time
from html import unescape
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
import unicodedata

from .domain_products import PRODUCT_PROFILES, ProductProfile


TOKEN_RE = re.compile(r"[\w\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff\ufb50-\ufdff\ufe70-\ufeff]+", re.UNICODE)
MAX_LIMIT = 30
DEFAULT_TIMEOUT_SECONDS = 2.0
DEFAULT_QUERY_SECONDS = 6.0
DEFAULT_MMAP_BYTES = 64 * 1024 * 1024
DEFAULT_CACHE_KIB = 8 * 1024

PSYCHOLOGY_KO_EXPANSIONS = (
    ("자살", "suicide crisis safety"),
    ("자해", "self harm safety"),
    ("공황", "panic anxiety"),
    ("불안", "anxiety worry"),
    ("걱정", "worry anxiety"),
    ("우울감", "depression mood"),
    ("우울", "depression mood"),
    ("불면", "insomnia sleep"),
    ("수면", "insomnia sleep"),
    ("잠", "insomnia sleep"),
    ("집중", "ADHD attention"),
)
TCM_EXPANSIONS = (
    ("소화", "digestion spleen stomach"),
    ("불면", "insomnia sleep 失眠 不寐"),
    ("insomnia", "sleep 失眠 不寐 睡眠 入睡 多梦 夜寐"),
    ("sleep", "insomnia 失眠 不寐 睡眠 入睡 多梦 夜寐"),
    ("한열", "cold heat pattern"),
    ("침", "acupuncture acupoint 针灸 針灸 침구"),
    ("acupuncture", "acupoint 针灸 針灸 针刺 取穴 安眠 침구 경혈"),
    ("acupoint", "acupuncture 针灸 針灸 针刺 取穴 安眠 침구 경혈"),
    ("약재", "materia medica herb"),
)
ISLAM_EXPANSIONS = (
    ("기도", "prayer salah"),
    ("예배", "prayer worship"),
    ("금식", "fasting sawm"),
    ("자카트", "zakat charity"),
    ("천국", "paradise jannah believe righteous faith deeds gardens salvation mercy allah messenger repentance"),
    ("낙원", "paradise jannah believe righteous faith deeds gardens salvation mercy allah messenger repentance"),
    ("구원", "salvation saved successful paradise believe righteous faith mercy repentance"),
    ("영생", "eternal life paradise believe righteous faith mercy"),
    ("선행", "righteous deeds believe faith paradise gardens"),
    ("의로운", "righteous deeds believe faith paradise gardens"),
    ("믿음", "believe faith righteous deeds paradise gardens"),
    ("회개", "repentance mercy forgiveness paradise allah"),
    ("paradise", "jannah heaven salvation believe righteous faith deeds gardens mercy repentance allah messenger"),
    ("jannah", "paradise heaven salvation believe righteous faith deeds gardens mercy repentance allah"),
    ("heaven", "paradise jannah salvation believe righteous faith deeds gardens mercy repentance allah"),
    ("salvation", "saved successful paradise believe righteous faith mercy repentance guidance"),
)

DOMAIN_CROSS_LINGUAL_FAMILIES: dict[str, tuple[dict[str, Any], ...]] = {
    "islam": (
        {
            "label": "cross_lingual",
            "language": "en",
            "strategy": "ko_salvation_to_en_islamic_terms",
            "markers": (
                "천국",
                "낙원",
                "구원",
                "영생",
                "선행",
                "의로운",
                "믿음",
                "회개",
                "paradise",
                "jannah",
                "heaven",
                "salvation",
                "الجنة",
                "جنة",
            ),
            "query": "paradise jannah heaven salvation believe faith righteous deeds gardens mercy repentance Allah Messenger",
            "fts": "believe righteous paradise",
            "operator": "AND",
        },
        {
            "label": "cross_lingual_gardens",
            "language": "en",
            "strategy": "ko_salvation_to_en_quran_gardens_terms",
            "markers": (
                "천국",
                "낙원",
                "구원",
                "영생",
                "paradise",
                "jannah",
                "heaven",
                "gardens",
                "الجنة",
                "جنة",
            ),
            "query": "gardens beneath rivers believe righteous deeds paradise",
            "fts": "believe righteous gardens",
            "operator": "AND",
        },
        {
            "label": "cross_lingual_success",
            "language": "en",
            "strategy": "ko_salvation_to_en_success_hereafter_terms",
            "markers": ("천국", "낙원", "구원", "영생", "successful", "saved", "salvation"),
            "query": "successful saved hereafter paradise faith guidance",
            "fts": "successful paradise",
            "operator": "AND",
        },
    ),
    "tcm": (
        {
            "label": "cross_lingual_insomnia_acupuncture",
            "language": "zh",
            "strategy": "ko_en_insomnia_acupuncture_to_zh_terms",
            "marker_groups": (
                ("불면", "insomnia", "sleep", "失眠", "不寐"),
                ("침", "acupuncture", "acupoint", "针灸", "針灸", "침구"),
            ),
            "query": "失眠 针灸 不寐 安神 入睡困难",
            "fts": "失眠 针灸",
            "operator": "AND",
        },
    ),
}

DOMAIN_CONTROL_HINTS: dict[str, dict[str, dict[str, Any]]] = {
    "islam": {
        "source-lineage": {
            "scope": "islam.source-lineage",
            "facets": ("quran", "hadith", "tafsir", "fiqh", "source", "isnad"),
        },
        "original-language": {
            "scope": "islam.original-language",
            "facets": ("arabic", "original", "translation", "quran"),
        },
        "translation-style": {
            "scope": "islam.translation-style",
            "facets": ("translation", "meaning", "study", "citation"),
        },
        "scholarly-boundary": {
            "scope": "islam.scholarly-boundary",
            "facets": ("fatwa", "authority", "religious", "safety"),
            "safetyBoundary": True,
        },
    },
    "tcm": {
        "pattern-map": {
            "scope": "tcm.pattern-map",
            "facets": ("pattern", "辨證", "체질", "spleen", "stomach", "cold", "heat", "한열"),
        },
        "formula-herb": {
            "scope": "tcm.formula-herb",
            "facets": ("herb", "formula", "本草", "처방", "약재", "方劑"),
        },
        "acupuncture-channel": {
            "scope": "tcm.acupuncture-channel",
            "facets": ("acupuncture", "acupoint", "channel", "针灸", "針灸", "침구", "경혈"),
        },
        "contraindication-safety": {
            "scope": "tcm.contraindication-safety",
            "facets": ("contraindication", "safety", "pregnancy", "medication", "禁忌", "금기"),
            "safetyBoundary": True,
        },
    },
    "psychology": {
        "mood-checkin": {
            "scope": "psychology.mood-checkin",
            "facets": ("mood", "depression", "anxiety", "worry", "우울", "불안", "check-in"),
        },
        "grounding-plan": {
            "scope": "psychology.grounding-plan",
            "facets": ("grounding", "panic", "breathing", "coping", "skill", "공황", "호흡"),
        },
        "crisis-boundary": {
            "scope": "psychology.crisis-boundary",
            "facets": ("self harm", "suicide", "crisis", "danger", "자해", "자살", "위기"),
            "safetyBoundary": True,
        },
        "session-notes": {
            "scope": "psychology.session-notes",
            "facets": ("session", "note", "history", "plan", "기록", "follow-up"),
        },
    },
}

LOW_SIGNAL_FACETS = {
    "어떻게",
    "해야",
    "하나요",
    "가나요",
    "되나요",
    "무엇",
    "뭐",
    "어떤",
    "방법",
    "how",
    "do",
    "and",
    "what",
    "should",
    "must",
}

PSYCHOLOGY_SUPPORT_FACETS = {
    "anxiety",
    "worry",
    "panic",
    "grounding",
    "coping",
    "safety",
    "plan",
    "crisis",
    "self",
    "harm",
    "depression",
    "mood",
}

SCRIPT_PATTERNS: dict[str, re.Pattern[str]] = {
    "hangul": re.compile(r"[\uac00-\ud7af]"),
    "gurmukhi": re.compile(r"[\u0a00-\u0a7f]"),
    "bengali": re.compile(r"[\u0980-\u09ff]"),
    "arabic": re.compile(r"[\u0600-\u06ff]"),
    "latin": re.compile(r"[A-Za-z]"),
}

DEFAULT_LANGUAGE_SCRIPT_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("hangul", ("ko",)),
    ("gurmukhi", ("pa",)),
    ("bengali", ("bn",)),
    ("arabic", ("ar", "ur", "fa")),
    ("latin", ("en", "id", "ms", "tr", "sw")),
)


@dataclass(frozen=True)
class DomainQuery:
    product: str
    query: str
    language: str = ""
    limit: int = 8
    controls: tuple[Any, ...] = ()


@dataclass(frozen=True)
class DomainControl:
    id: str
    scope: str
    facets: tuple[str, ...]
    safety_boundary: bool = False


@dataclass(frozen=True)
class QueryFamily:
    label: str
    query: str
    fts: str
    operator: str = ""
    strategy: str = ""
    language: str = ""


@dataclass(frozen=True)
class DomainSource:
    source_id: str
    title: str
    citation: str
    authority_body: str
    source_date: str
    topic: str
    source_type: str
    full_text: str
    source_dataset: str = ""
    source_path: str = ""
    source_url: str = ""
    language: str = ""
    score: float = 0.0
    verdict: str = "rejected"
    reject_reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RejectedCandidate:
    source_id: str
    title: str
    reason: str
    score: float
    family: str


@dataclass(frozen=True)
class DomainSearchResult:
    product: str
    query: str
    language: str
    facets: list[str]
    surface_facets: list[str]
    expanded_facets: list[str]
    query_families: list[QueryFamily]
    selected: list[DomainSource]
    rejected_ledger: list[RejectedCandidate]
    candidate_frontier: dict[str, Any] = field(default_factory=dict)
    verifier: dict[str, Any] = field(default_factory=dict)
    controls: list[dict[str, Any]] = field(default_factory=list)


class DomainSearchEngine:
    def __init__(self, profiles: dict[str, ProductProfile] | None = None) -> None:
        self._profiles = profiles or PRODUCT_PROFILES

    def search(self, query: DomainQuery, *, cancel_event: threading.Event | None = None) -> DomainSearchResult:
        profile = self._profile(query.product)
        self._validate_db_path(profile)
        normalized_query = _bounded_query(query.query)
        language = _resolve_language(profile, query.language, normalized_query)
        limit = _bounded_limit(query.limit)
        controls = normalize_domain_controls(profile.key, query.controls)
        surface_facets = _query_tokens(normalized_query)
        retrieval_control_facets = [] if profile.key == "psychology" else [facet for control in controls for facet in control.facets]
        facets = _dedupe_facets(
            [*build_query_facets(profile, normalized_query), *retrieval_control_facets],
            limit=20,
        )
        families = build_query_families(profile, normalized_query, facets, controls=controls)
        frontier, candidate_frontier = self._candidate_frontier(
            profile,
            families,
            language=language,
            limit=limit,
            cancel_event=cancel_event,
        )
        selected, rejected = verify_and_rank_candidates(frontier, facets, limit=limit)
        expanded_facets = [facet for facet in facets if facet not in surface_facets]
        return DomainSearchResult(
            product=profile.key,
            query=normalized_query,
            language=language,
            facets=facets,
            surface_facets=surface_facets,
            expanded_facets=expanded_facets,
            query_families=families,
            selected=selected,
            rejected_ledger=rejected[:50],
            candidate_frontier={
                **candidate_frontier,
                "candidateCount": len(frontier),
                "selectedCount": len(selected),
                "controlsApplied": [control.id for control in controls],
            },
            verifier={
                "method": "facet-overlap-authority-source-grounded-score",
                "acceptedCount": len(selected),
                "rejectedCount": len(rejected),
                "scoringFacets": _scoring_facets(facets),
                "controlFacets": [facet for control in controls for facet in control.facets],
            },
            controls=[_control_payload(control) for control in controls],
        )

    def _profile(self, key: str) -> ProductProfile:
        normalized = str(key or "").strip().lower()
        if normalized == "simli":
            normalized = "psychology"
        profile = self._profiles.get(normalized)
        if profile is None:
            raise KeyError("unknown product")
        return profile

    def _validate_db_path(self, profile: ProductProfile) -> None:
        db_path = profile.db_path.resolve()
        allowed = {path.resolve() for path in profile.path_allowlist}
        if db_path not in allowed:
            raise ValueError("db path is not allowlisted")
        if not db_path.exists():
            raise FileNotFoundError(str(profile.db_path))

    def _candidate_frontier(
        self,
        profile: ProductProfile,
        families: list[QueryFamily],
        *,
        language: str,
        limit: int,
        cancel_event: threading.Event | None,
    ) -> tuple[list[tuple[DomainSource, str]], dict[str, Any]]:
        seen: set[str] = set()
        frontier: list[tuple[DomainSource, str]] = []
        candidate_window = max(limit * 20, 80)
        family_trace: list[dict[str, Any]] = []
        fallback_count = 0
        with _connect_readonly(profile.db_path, cancel_event=cancel_event) as conn:
            for family in families:
                if cancel_event and cancel_event.is_set():
                    raise RuntimeError("cancelled")
                rows = _run_bounded_query(
                    conn,
                    profile=profile,
                    fts=family.fts,
                    limit=candidate_window,
                    language=language,
                    cancel_event=cancel_event,
                )
                used_language_fallback = False
                if profile.db_shape == "documents" and not rows and language:
                    rows = _run_bounded_query(
                        conn,
                        profile=profile,
                        fts=family.fts,
                        limit=candidate_window,
                        language="",
                        cancel_event=cancel_event,
                    )
                    used_language_fallback = bool(rows)
                before = len(frontier)
                for row in rows:
                    source = _row_to_source(profile, row)
                    if not source.source_id or source.source_id in seen:
                        continue
                    seen.add(source.source_id)
                    frontier.append((source, family.label))
                family_trace.append(
                    {
                        "label": family.label,
                        "strategy": family.strategy,
                        "language": family.language,
                        "operator": family.operator,
                        "fts": family.fts,
                        "hits": len(rows),
                        "newCandidates": len(frontier) - before,
                        "languageFallback": used_language_fallback,
                    }
                )
            if len(frontier) < candidate_window:
                _set_progress_guard(conn, cancel_event=cancel_event, seconds=DEFAULT_QUERY_SECONDS)
                try:
                    fallback = _fallback_rows(conn, profile.db_shape, max(0, min(20, candidate_window - len(frontier))))
                except sqlite3.OperationalError:
                    fallback = []
                fallback_count = len(fallback)
                for row in fallback:
                    source = _row_to_source(profile, row)
                    if not source.source_id or source.source_id in seen:
                        continue
                    seen.add(source.source_id)
                    frontier.append((source, "authority_frontier"))
        return frontier, {
            "searchedFamilies": len(families),
            "families": family_trace,
            "fallbackRows": fallback_count,
            "window": candidate_window,
        }


def _connect_readonly(path: Path, *, cancel_event: threading.Event | None = None) -> sqlite3.Connection:
    timeout = _env_float("LAWKEY_DOMAIN_SQLITE_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS, minimum=0.1, maximum=30.0)
    mmap_bytes = _env_int("LAWKEY_DOMAIN_SQLITE_MMAP_BYTES", DEFAULT_MMAP_BYTES, minimum=0, maximum=1024 * 1024 * 1024)
    cache_kib = _env_int("LAWKEY_DOMAIN_SQLITE_CACHE_KIB", DEFAULT_CACHE_KIB, minimum=512, maximum=128 * 1024)
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False, timeout=timeout)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    conn.execute("PRAGMA temp_store = FILE")
    conn.execute("PRAGMA busy_timeout = 2000")
    conn.execute(f"PRAGMA mmap_size = {mmap_bytes}")
    conn.execute(f"PRAGMA cache_size = -{cache_kib}")
    _set_progress_guard(conn, cancel_event=cancel_event, seconds=DEFAULT_QUERY_SECONDS)
    return conn


def _set_progress_guard(
    conn: sqlite3.Connection,
    *,
    cancel_event: threading.Event | None,
    seconds: float,
) -> None:
    deadline = time.monotonic() + max(0.1, seconds)

    def guard() -> int:
        if cancel_event is not None and cancel_event.is_set():
            return 1
        if time.monotonic() > deadline:
            return 1
        return 0

    conn.set_progress_handler(guard, 1000)


def _run_bounded_query(
    conn: sqlite3.Connection,
    *,
    profile: ProductProfile,
    fts: str,
    limit: int,
    language: str,
    cancel_event: threading.Event | None,
) -> list[sqlite3.Row]:
    seconds = _env_float("LAWKEY_DOMAIN_QUERY_SECONDS", DEFAULT_QUERY_SECONDS, minimum=0.1, maximum=60.0)
    _set_progress_guard(conn, cancel_event=cancel_event, seconds=seconds)
    try:
        return (
            _search_precedents(conn, fts, limit)
            if profile.db_shape == "precedents"
            else _search_documents(conn, fts, limit, language=language)
        )
    except sqlite3.OperationalError as exc:
        if "interrupted" in str(exc).lower():
            return []
        raise


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


def _bounded_query(query: str) -> str:
    value = str(query or "").strip()
    if not value:
        raise ValueError("query is required")
    if len(value) > 5000:
        raise ValueError("query too long")
    return value


def _bounded_limit(limit: int) -> int:
    try:
        parsed = int(limit or 8)
    except (TypeError, ValueError):
        parsed = 8
    return max(1, min(parsed, MAX_LIMIT))


def _resolve_language(profile: ProductProfile, language: str, query: str = "") -> str:
    selected = str(language or profile.default_language).strip().lower()
    if selected not in profile.languages:
        raise ValueError("unsupported language")
    if selected != profile.default_language:
        return selected
    detected = _detect_query_language(profile, query, selected_language=selected)
    return detected or selected


def _detect_query_language(profile: ProductProfile, query: str, *, selected_language: str = "") -> str:
    text = str(query or "")
    languages = set(profile.languages)
    selected = selected_language if selected_language in languages else ""
    for script, group in _language_script_groups(profile):
        pattern = SCRIPT_PATTERNS.get(script)
        if pattern is None or not pattern.search(text):
            continue
        supported = tuple(code for code in group if code in languages)
        if not supported:
            continue
        if selected in supported:
            return selected
        return supported[0]
    return ""


def _language_script_groups(profile: ProductProfile) -> tuple[tuple[str, tuple[str, ...]], ...]:
    return profile.language_script_groups or DEFAULT_LANGUAGE_SCRIPT_GROUPS


def build_query_facets(profile: ProductProfile, query: str) -> list[str]:
    facets = _query_tokens(query)
    for marker, expansion in _expansion_table(profile):
        if marker in query:
            facets.extend(_query_tokens(expansion))
    return _dedupe_facets(facets, limit=12)


def build_query_families(
    profile: ProductProfile,
    query: str,
    facets: list[str],
    *,
    controls: tuple[DomainControl, ...] = (),
) -> list[QueryFamily]:
    values = [("exact", query, "AND", "surface_exact", "")]
    cross_lingual = _cross_lingual_query_families(profile, query)
    expanded = " ".join(facets)
    if expanded and expanded != query:
        values.append(("expanded", expanded, "OR", "facet_expansion", ""))
    if profile.key == "islam":
        values.append(("authority", " ".join([query, "quran hadith fiqh"]), "OR", "authority_backstop", ""))
    elif profile.key == "tcm":
        values.append(("authority", " ".join([query, "classic formula herb acupuncture"]), "OR", "authority_backstop", ""))
    elif profile.key == "psychology":
        values.append(("authority", " ".join([query, "guideline symptoms safety"]), "OR", "authority_backstop", ""))
    for control in controls:
        if profile.key == "psychology":
            continue
        control_query = " ".join([query, *control.facets])
        operator = "AND" if profile.key == "tcm" and control.id == "acupuncture-channel" else "OR"
        values.append((f"control_{_safe_label(control.id)}", control_query, operator, f"domain_control:{control.scope}", ""))
    families: list[QueryFamily] = []
    seen: set[str] = set()
    for family in cross_lingual:
        if family.fts and family.fts not in seen:
            families.append(family)
            seen.add(family.fts)
    for label, value, operator, strategy, language in values:
        fts = _fts_query(value, operator=operator)
        if fts and fts not in seen:
            families.append(
                QueryFamily(
                    label=label,
                    query=value,
                    fts=fts,
                    operator=operator.upper(),
                    strategy=strategy,
                    language=language,
                )
            )
            seen.add(fts)
    return families or [
        QueryFamily(
            label="exact",
            query=query,
            fts=_fts_query(query, operator="AND"),
            operator="AND",
            strategy="surface_exact",
        )
    ]


def normalize_domain_controls(product: str, controls: Any) -> tuple[DomainControl, ...]:
    if not isinstance(controls, (list, tuple)):
        return ()
    allowed = DOMAIN_CONTROL_HINTS.get(str(product or "").strip().lower(), {})
    out: list[DomainControl] = []
    seen: set[str] = set()
    for item in list(controls)[:4]:
        if isinstance(item, str):
            control_id = item.strip().lower()
        elif isinstance(item, dict):
            control_id = str(item.get("id") or "").strip().lower()
        else:
            continue
        control_id = re.sub(r"[^a-z0-9_-]", "", control_id)[:80]
        config = allowed.get(control_id)
        if not config or control_id in seen:
            continue
        seen.add(control_id)
        facets = tuple(_dedupe_facets([str(facet) for facet in config.get("facets", ())], limit=10))
        out.append(
            DomainControl(
                id=control_id,
                scope=str(config.get("scope") or f"{product}.{control_id}")[:120],
                facets=facets,
                safety_boundary=bool(config.get("safetyBoundary")),
            )
        )
    return tuple(out)


def _control_payload(control: DomainControl) -> dict[str, Any]:
    return {
        "id": control.id,
        "scope": control.scope,
        "facets": list(control.facets),
        "safetyBoundary": control.safety_boundary,
    }


def _dedupe_facets(tokens: list[str], *, limit: int) -> list[str]:
    out: list[str] = []
    for token in tokens:
        lowered = str(token or "").strip().lower()
        if lowered and lowered not in out:
            out.append(lowered)
        if len(out) >= limit:
            break
    return out


def _safe_label(value: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", str(value or "").strip().lower()).strip("_")[:80] or "control"


def _cross_lingual_query_families(profile: ProductProfile, query: str) -> list[QueryFamily]:
    rules = DOMAIN_CROSS_LINGUAL_FAMILIES.get(profile.key, ())
    if not rules:
        return []
    lowered = query.lower()
    families: list[QueryFamily] = []
    for rule in rules:
        marker_groups = tuple(tuple(str(marker).lower() for marker in group) for group in rule.get("marker_groups") or ())
        if marker_groups:
            if not all(any(marker and marker in lowered for marker in group) for group in marker_groups):
                continue
        else:
            markers = tuple(str(marker).lower() for marker in rule.get("markers") or ())
            if not any(marker and marker in lowered for marker in markers):
                continue
        operator = str(rule.get("operator") or "AND").upper()
        fts_text = str(rule.get("fts") or rule.get("query") or "")
        fts = _fts_query(fts_text, operator=operator)
        if not fts:
            continue
        families.append(
            QueryFamily(
                label=str(rule.get("label") or "cross_lingual"),
                query=str(rule.get("query") or fts_text),
                fts=fts,
                operator=operator,
                strategy=str(rule.get("strategy") or "query_translation"),
                language=str(rule.get("language") or ""),
            )
        )
    return families


def _expansion_table(profile: ProductProfile) -> tuple[tuple[str, str], ...]:
    if profile.key == "psychology":
        return PSYCHOLOGY_KO_EXPANSIONS
    if profile.key == "tcm":
        return TCM_EXPANSIONS
    if profile.key == "islam":
        return ISLAM_EXPANSIONS
    return ()


def _query_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    for token in TOKEN_RE.findall(text or ""):
        cleaned = token.strip("_").strip("'\"").lower()
        if len(cleaned) >= 2 and cleaned not in tokens:
            tokens.append(cleaned)
        if len(tokens) >= 16:
            break
    return tokens


def _fts_query(text: str, *, operator: str = "OR") -> str:
    tokens = _query_tokens(text)
    joiner = " AND " if operator.upper() == "AND" else " OR "
    return joiner.join(f'"{token}"' for token in tokens[:12])


def _search_precedents(conn: sqlite3.Connection, fts: str, limit: int) -> list[sqlite3.Row]:
    if not fts:
        return []
    return conn.execute(
        """
        SELECT
          p.canonical_id,
          p.source_dataset,
          p.source_path,
          '' AS source_url,
          p.title,
          p.case_number,
          p.court,
          p.decision_date,
          p.case_name,
          p.case_type,
          p.full_text,
          '' AS language
        FROM precedents_fts
        JOIN precedents p ON p.canonical_id = precedents_fts.canonical_id
        WHERE precedents_fts MATCH ?
        LIMIT ?
        """,
        (fts, limit),
    ).fetchall()


def _search_documents(conn: sqlite3.Connection, fts: str, limit: int, *, language: str) -> list[sqlite3.Row]:
    if not fts:
        return []
    params: list[Any] = [fts]
    lang_filter = ""
    if language:
        lang_filter = "AND COALESCE(d.language, '') IN ('', ?)"
        params.append(language)
    params.append(limit)
    return conn.execute(
        f"""
        SELECT
          d.canonical_id,
          d.source_dataset,
          d.source_path,
          d.source_url,
          d.title,
          d.canonical_id AS case_number,
          d.source_dataset AS court,
          d.pub_date AS decision_date,
          COALESCE(d.topic, d.disorder, '') AS case_name,
          d.doc_type AS case_type,
          d.full_text,
          d.language
        FROM documents_fts
        JOIN documents d ON d.rowid = documents_fts.rowid
        WHERE documents_fts MATCH ?
        {lang_filter}
        LIMIT ?
        """,
        params,
    ).fetchall()


def _fallback_rows(conn: sqlite3.Connection, db_shape: str, limit: int) -> list[sqlite3.Row]:
    if limit <= 0:
        return []
    if db_shape == "precedents":
        return conn.execute(
            """
            SELECT
              p.canonical_id,
              p.source_dataset,
              p.source_path,
              '' AS source_url,
              p.title,
              p.case_number,
              p.court,
              p.decision_date,
              p.case_name,
              p.case_type,
              p.full_text,
              '' AS language
            FROM precedents p
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return conn.execute(
        """
        SELECT
          d.canonical_id,
          d.source_dataset,
          d.source_path,
          d.source_url,
          d.title,
          d.canonical_id AS case_number,
          d.source_dataset AS court,
          d.pub_date AS decision_date,
          COALESCE(d.topic, d.disorder, '') AS case_name,
          d.doc_type AS case_type,
          d.full_text,
          d.language
        FROM documents d
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


def _row_to_source(profile: ProductProfile, row: sqlite3.Row) -> DomainSource:
    source_id = str(row["canonical_id"] or "")
    return DomainSource(
        source_id=source_id,
        title=str(row["title"] or ""),
        citation=str(row["case_number"] or source_id),
        authority_body=str(row["court"] or ""),
        source_date=str(row["decision_date"] or ""),
        topic=str(row["case_name"] or ""),
        source_type=str(row["case_type"] or ""),
        full_text=str(row["full_text"] or ""),
        source_dataset=str(row["source_dataset"] or ""),
        source_path=str(row["source_path"] or ""),
        source_url=str(row["source_url"] or ""),
        language=str(row["language"] or ""),
        metadata={"product": profile.key, "language": str(row["language"] or "")},
    )


def verify_and_rank_candidates(
    frontier: list[tuple[DomainSource, str]],
    facets: list[str],
    *,
    limit: int,
) -> tuple[list[DomainSource], list[RejectedCandidate]]:
    accepted: list[DomainSource] = []
    rejected: list[RejectedCandidate] = []
    scoring_facets = _scoring_facets(facets)
    for source, family in frontier:
        overlap = _overlap_score(source, scoring_facets)
        authority = _authority_level(source)
        intent_bonus = _intent_bonus(source, scoring_facets)
        score = overlap * 10.0 + authority / 10.0 + intent_bonus
        if overlap <= 0:
            rejected.append(
                RejectedCandidate(
                    source_id=source.source_id,
                    title=source.title,
                    reason="low_overlap",
                    score=round(score, 3),
                    family=family,
                )
            )
            continue
        accepted.append(
            _replace_source(
                source,
                score=score,
                verdict="accepted",
                metadata={**source.metadata, "scoringFacets": scoring_facets},
            )
        )
    accepted.sort(key=lambda item: (-item.score, item.source_id))
    trimmed = accepted[limit:]
    for source in trimmed:
        rejected.append(
            RejectedCandidate(
                source_id=source.source_id,
                title=source.title,
                reason="frontier_trimmed",
                score=round(source.score, 3),
                family="ranked",
            )
        )
    return accepted[:limit], rejected


def _scoring_facets(facets: list[str]) -> list[str]:
    out: list[str] = []
    for facet in facets:
        token = str(facet or "").strip().lower()
        if not token or token in LOW_SIGNAL_FACETS:
            continue
        if token not in out:
            out.append(token)
    return out


def _replace_source(source: DomainSource, **updates: Any) -> DomainSource:
    values = {**source.__dict__, **updates}
    return DomainSource(**values)


def _overlap_score(source: DomainSource, facets: list[str]) -> float:
    haystack = "\n".join(
        [source.title, source.citation, source.authority_body, source.topic, source.source_type, source.full_text]
    ).lower()
    score = 0.0
    for token in facets:
        if token and token.lower() in haystack:
            score += min(haystack.count(token.lower()), 8)
    return score


def _intent_bonus(source: DomainSource, facets: list[str]) -> float:
    facet_set = set(facets)
    text = "\n".join([source.title, source.citation, source.topic, source.source_type, source.full_text]).lower()
    dataset = source.source_dataset.lower()
    source_type = source.source_type.lower()
    bonus = 0.0
    if {"paradise", "believe", "righteous"}.issubset(facet_set):
        if "believe and do righteous deeds" in text or "believe and work righteous" in text:
            bonus += 45.0
        if "gardens beneath" in text or "gardens under" in text:
            bonus += 25.0
        if "quran 2:25" in text or source.citation.lower() == "quran 2:25":
            bonus += 20.0
        if "scripture" in text or "qur'an" in text or "quran" in text:
            bonus += 10.0
    if facet_set & PSYCHOLOGY_SUPPORT_FACETS:
        if "counseling" in source_type or "counseling" in dataset:
            bonus += 420.0
        if "guideline" in source_type or "guideline" in dataset:
            bonus += 120.0
        if "safety plan" in text or "grounding" in text or "coping" in text:
            bonus += 40.0
    if _is_tcm_insomnia_acupuncture_intent(facet_set):
        has_sleep = _has_tcm_sleep_context(text)
        has_primary_sleep_focus = _has_tcm_primary_sleep_focus(text)
        has_acupuncture = any(marker in text for marker in ("acupuncture", "acupoint", "针灸", "針灸", "침구", "取穴"))
        has_wind_stroke = any(marker in text for marker in ("wind stroke", "stroke", "中風", "中风", "風氣", "风气"))
        if has_sleep and has_acupuncture:
            bonus += 220.0
            if has_primary_sleep_focus:
                bonus += 240.0
            else:
                bonus -= 160.0
            if "case_record" in source_type or "case_record" in dataset or "medical record" in dataset:
                bonus += 160.0
            if any(marker in text for marker in ("针刺", "針刺", "留针", "留針", "安眠", "耳穴")):
                bonus += 180.0
            if re.search(r"(针灸|針灸|针刺|針刺).{0,16}(无明显效果|無明顯效果|无效|無效|未效)", text):
                bonus -= 360.0
        elif has_sleep:
            bonus += 15.0
        elif has_acupuncture:
            bonus -= 70.0
        if has_wind_stroke and not has_sleep:
            bonus -= 75.0
        if "失眠穴" in text and not has_sleep:
            bonus -= 180.0
        if not has_primary_sleep_focus and any(
            marker in text for marker in ("脑供血不足", "强直性脊柱炎", "口眼歪斜", "足跟痛", "痛经", "皮肤瘙痒")
        ):
            bonus -= 180.0
    return bonus


def _has_tcm_sleep_context(text: str) -> bool:
    if any(marker in text for marker in ("insomnia", "sleep", "sleepless", "불면", "不寐", "夜寐", "入睡", "多梦", "多夢", "寐差", "睡眠")):
        return True
    return re.search(r"(主诉|诊断|診斷|患者|心烦|心煩|治疗|治療).{0,24}失眠(?!穴)|失眠症", text) is not None


def _has_tcm_primary_sleep_focus(text: str) -> bool:
    return (
        re.search(r"(主诉|主訴|诊断|診斷|疾病|证候|證候).{0,16}(不寐|失眠|睡眠)", text) is not None
        or re.search(r"(症状|症狀)\s*[:：]\s*(不寐|失眠|睡眠)", text) is not None
        or re.search(r"(治疗|治療|常用于治疗|常用於治療).{0,8}(不寐|失眠|多梦|多夢)", text) is not None
        or re.search(r"(不寐|失眠).{0,32}(治法|取穴|针刺|針刺|针灸|針灸|耳针|耳針|神门|神門|安眠)", text) is not None
    )


def _is_tcm_insomnia_acupuncture_intent(facets: set[str]) -> bool:
    sleep = {"불면", "insomnia", "sleep", "失眠", "不寐"} & facets
    acupuncture = {"침", "acupuncture", "acupoint", "针灸", "針灸", "침구"} & facets
    return bool(sleep and acupuncture)


def _authority_level(source: DomainSource) -> float:
    text = "\n".join([source.source_dataset, source.source_type, source.full_text])
    match = re.search(r"authority_level\s*:\s*(\d{1,3})", text, flags=re.IGNORECASE)
    if match:
        return max(0.0, min(float(match.group(1)), 100.0))
    lowered = text.lower()
    if "scripture" in lowered or "quran" in lowered or "동의보감" in lowered:
        return 95.0
    if "hadith" in lowered or "classic" in lowered or "guideline" in lowered:
        return 85.0
    if "pmc" in lowered or "paper" in lowered:
        return 65.0
    return 40.0


def to_selected_evidence(source: DomainSource) -> dict[str, Any]:
    scoring_facets = [str(item) for item in source.metadata.get("scoringFacets", []) if str(item or "").strip()]
    return {
        "id": source.source_id,
        "title": sanitize_public_text(source.title),
        "citation": sanitize_public_text(source.citation),
        "authorityBody": sanitize_public_text(source.authority_body),
        "date": sanitize_public_text(source.source_date),
        "topic": sanitize_public_text(source.topic),
        "type": sanitize_public_text(source.source_type),
        "dataset": sanitize_public_text(source.source_dataset),
        "path": _public_source_path(source.source_path),
        "url": _public_source_url(source.source_url),
        "score": round(source.score, 3),
        "verdict": source.verdict,
        "excerpt": public_text_excerpt(source.full_text, 600, terms=scoring_facets),
    }


def public_text_excerpt(text: str, limit: int, *, terms: list[str] | None = None) -> str:
    value = sanitize_public_text(text)
    if terms:
        value = _focused_excerpt_window(value, terms, limit=limit)
    if len(value) <= limit:
        return value
    clipped = value[: max(0, limit)].rstrip()
    while clipped and unicodedata.combining(clipped[-1]):
        clipped = clipped[:-1]
    return clipped


def _focused_excerpt_window(text: str, terms: list[str], *, limit: int) -> str:
    if len(text) <= limit:
        return text
    lowered = text.lower()
    for term in terms:
        token = str(term or "").strip().lower()
        if len(token) < 2:
            continue
        index = lowered.find(token)
        if index >= 0:
            center = index
            break
    else:
        return text
    start = max(0, center - limit // 4)
    end = min(len(text), start + limit)
    window = text[start:end].strip()
    if start > 0:
        window = "…" + window
    if end < len(text):
        window = window.rstrip() + "…"
    return window


def sanitize_public_text(text: str) -> str:
    value = unicodedata.normalize("NFC", str(text or ""))
    value = unescape(value).replace("\xa0", " ")
    value = re.sub(r"(?is)<(script|style)\b[^>]*>.*?</\1>", " ", value)
    value = re.sub(r"(?is)<[^>]+>", " ", value)
    if re.search(r"\[PRIMARY TEXT[^\]]*\]", value, flags=re.IGNORECASE):
        value = re.sub(
            r"(?is)\[META\].*?(?=\[PRIMARY TEXT[^\]]*\])",
            " ",
            value,
            count=1,
        )
    else:
        value = re.sub(r"(?i)\[META\]\s*", " ", value)
        value = re.sub(r"(?i)\bauthority_level\s*:\s*\d{1,3}\b", " ", value)
    value = re.sub(r"(?i)\[PRIMARY TEXT[^\]]*\]", " ", value)
    value = re.sub(r"(?i)\[/PRIMARY TEXT\]", " ", value)
    value = re.sub(r"(?i)\[(지시|입력|출력|instruction|input|output|boundaries)\]\s*", " ", value)
    value = re.sub(r"(?i)\b(ignore|disregard)\s+previous\s+instructions?\b.*?(?:[.!?。]|$)", " ", value)
    value = re.sub(r"(?i)\b(system|developer)\s+prompt\b.*?(?:[.!?。]|$)", " ", value)
    value = re.sub(r"基于输入[^。！？!?]{0,120}(?:无需给出原因|直接给出你的疾病诊断)[^。！？!?]*(?:[。！？!?]|$)", " ", value)
    value = re.sub(r"直接给出你的疾病诊断[^。！？!?]*(?:[。！？!?]|$)", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _public_source_path(source_path: str) -> str:
    value = str(source_path or "").strip()
    if not value:
        return ""
    normalized = value.replace("\\", "/")
    parts = [part for part in normalized.split("/") if part and part != "."]
    if not parts:
        return ""
    if normalized.startswith("/") or re.match(r"^[A-Za-z]:/", normalized) or ".." in parts or normalized.startswith("~"):
        return parts[-1] if parts[-1] != ".." else ""
    return "/".join(parts[:6])


def _public_source_url(source_url: str) -> str:
    value = str(source_url or "").strip()
    if not value:
        return ""
    lowered = value.lower()
    if any(marker in lowered for marker in ("/home/", "\\home\\", "/mnt/", ".sqlite", ".sqlite3", ".jsonl")):
        return ""
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        return ""
    if not parsed.netloc or parsed.username or parsed.password:
        return ""
    return value[:500]
