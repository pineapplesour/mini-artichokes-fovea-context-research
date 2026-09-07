from __future__ import annotations

import os
import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from typing import Any

from .lawkey_graph import expand_lawkey_event_frame_rows, expand_lawkey_precedent_rows
from .products import ProductProfile
from .tcm_graph import expand_tcm_passage_graph_rows
from .tcm_mcq import parse_tcm_mcq, tcm_mcq_option_terms, tcm_mcq_prompt_block, tcm_mcq_search_text, tcm_option_aliases


@dataclass(frozen=True)
class MultipleChoiceOption:
    number: int
    text: str
    marker: str = ""


@dataclass(frozen=True)
class MultipleChoiceQuestion:
    stem: str
    options: tuple[MultipleChoiceOption, ...]


@dataclass(frozen=True)
class IntEnvConfig:
    env_names: tuple[str, ...]
    default: int
    minimum: int
    maximum: int


@dataclass(frozen=True)
class FloatEnvConfig:
    env_names: tuple[str, ...]
    default: float
    minimum: float
    maximum: float


@dataclass(frozen=True)
class BoolEnvConfig:
    env_names: tuple[str, ...]
    default: bool


class DomainAdapter:
    key = "default"
    surface_token_limit = 8
    surface_term_limit = 8

    def parse_multiple_choice(self, text: str) -> MultipleChoiceQuestion | None:
        return _parse_generic_multiple_choice(text)

    def multiple_choice_prompt_block(self, text: str) -> str:
        parsed = self.parse_multiple_choice(text)
        if parsed is None or not parsed.options:
            return ""
        option_lines: list[str] = []
        for option in parsed.options:
            option_id = str(option.marker or option.number).strip()
            if not option_id:
                continue
            option_lines.append(f"- 보기ID {option_id}: {option.text}")
        if not option_lines:
            return ""
        return (
            "[multiple-choice contract]\n"
            "- 답변 첫 줄은 반드시 `정답: <보기ID>` 형식으로 쓰세요. For English answers, use `Answer: <option ID>`.\n"
            "- 보기ID는 citation label이나 source label이 아닙니다. It is the option ID listed below.\n"
            "- If the evidence supports a verse, date, person, or concept that appears in an option, return that option's 보기ID exactly.\n"
            + "\n".join(option_lines)
        )

    def multiple_choice_option_terms(self, text: str) -> list[str]:
        return []

    def option_aliases(self, option_text: str) -> list[str]:
        cleaned = str(option_text or "").strip()
        return [cleaned] if cleaned else []

    def direct_option_terms(self, terms: list[str]) -> list[str]:
        return [term for term in _unique_terms(terms) if len(term) >= 2]

    def search_text(self, text: str) -> str:
        parsed = self.parse_multiple_choice(text)
        if parsed is None:
            return str(text or "")
        return parsed.stem

    def is_low_signal_surface_term(self, term: str) -> bool:
        return False

    def drop_surface_term(self, term: str) -> bool:
        return False

    def expand_graph_rows(
        self,
        conn: sqlite3.Connection,
        seed_rows: list[sqlite3.Row],
        *,
        query: str = "",
        seed_scores: dict[str, float],
        max_neighbors: int,
        max_expanded: int,
    ) -> tuple[list[sqlite3.Row], dict[str, float]]:
        return [], {}

    def postprocess_selected_rows(
        self,
        query: str,
        candidates: list[Any],
        selected_rows: list[Any],
        *,
        limit: int,
    ) -> list[Any]:
        del query, candidates
        return selected_rows[:limit]

    def priority_context_candidate_rows(self, query: str, rows: list[Any]) -> tuple[list[Any], list[Any]]:
        del query
        return [], rows

    def role_order(self) -> list[str]:
        return ["other"]

    def source_role(self, row: Any) -> str:
        return "other"

    def selector_policy(self) -> str:
        return "- Select directly relevant evidence only."

    def selector_role_diversity_rule(self) -> str:
        return _role_diversity_rule("the distinct source_kind groups present in the candidate batch")

    def keyword_generation_spec(self) -> tuple[str, str]:
        return "Generate short source retrieval keywords.", ""

    def additional_keyword_hint(self) -> str:
        return "Use narrower source-search terms."

    def claim_analyzer_policy(self) -> str:
        return "- Make source-grounded claim cards only."

    def writer_domain_policy(self) -> str:
        return "Respect the source tradition and avoid overstating authority."

    def writer_return_instruction(self, language: str = "") -> str:
        return _language_guard(language) + "Return a concise cited answer, then a short Sources section listing only cited labels."

    def source_usage_hint(self, record: dict[str, Any]) -> str:
        return ""

    def min_answer_chars_default(self) -> int:
        return 0

    def selector_timeout_config(self, *, chat_timeout: float) -> FloatEnvConfig:
        return FloatEnvConfig(("RELIGION_SELECTOR_TIMEOUT_SECONDS",), 90.0, 5.0, chat_timeout)

    def selector_primary_timeout_config(self, *, selector_timeout: float) -> FloatEnvConfig:
        return FloatEnvConfig(("RELIGION_SELECTOR_PRIMARY_TIMEOUT_SECONDS",), selector_timeout, 5.0, selector_timeout)

    def selector_compact_candidate_lines_config(self) -> BoolEnvConfig:
        return BoolEnvConfig(("RELIGION_SELECTOR_COMPACT_LINES",), False)

    def selector_candidate_limit_config(self, *, available: int) -> IntEnvConfig:
        default = available if available else 1200
        maximum = max(120, min(max(default, available), 2000))
        return IntEnvConfig(("RELIGION_SELECTOR_CANDIDATE_LIMIT",), default, 8, maximum)

    def selector_batch_size_config(self, *, candidate_limit: int) -> IntEnvConfig:
        default = min(100, candidate_limit)
        return IntEnvConfig(("RELIGION_SELECTOR_BATCH_SIZE",), default, 8, max(8, candidate_limit))

    def selector_recovery_batch_size_config(self, *, batch_size: int, maximum: int) -> IntEnvConfig:
        default = min(25, max(8, int(batch_size or 1) // 2))
        return IntEnvConfig(("RELIGION_SELECTOR_RECOVERY_BATCH_SIZE",), default, 2, maximum)

    def selector_rate_limit_retries_config(self) -> IntEnvConfig:
        return IntEnvConfig(("RELIGION_SELECTOR_RATE_LIMIT_RETRIES",), 1, 0, 5)

    def selector_rate_limit_backoff_config(self) -> FloatEnvConfig:
        return FloatEnvConfig(("RELIGION_SELECTOR_RATE_LIMIT_BACKOFF_SECONDS",), 3.0, 0.0, 60.0)

    def selector_batch_workers_config(self, *, maximum: int) -> IntEnvConfig:
        return IntEnvConfig(("RELIGION_SELECTOR_BATCH_WORKERS",), min(4, maximum), 1, maximum)

    def selector_recovery_batch_workers_config(self, *, maximum: int) -> IntEnvConfig:
        return IntEnvConfig(("RELIGION_SELECTOR_RECOVERY_BATCH_WORKERS",), min(4, maximum), 1, maximum)

    def selector_excerpt_chars_config(self) -> IntEnvConfig:
        return IntEnvConfig(("RELIGION_SELECTOR_EXCERPT_CHARS",), 560, 280, 900)

    def selector_excerpt_bytes_config(self) -> IntEnvConfig:
        return IntEnvConfig(("RELIGION_SELECTOR_EXCERPT_BYTES",), 0, 0, 2400)

    def claim_analyzer_source_chars_config(self) -> IntEnvConfig:
        return IntEnvConfig(("RELIGION_CLAIM_ANALYZER_SOURCE_CHARS",), 1400, 400, 3000)

    def claim_chunk_text_chars_config(self) -> IntEnvConfig:
        return IntEnvConfig(("RELIGION_CHUNK_CLAIM_ANALYZER_CHARS",), 4800, 800, 12000)

    def claim_chunk_analyzer_workers_config(self, *, maximum: int) -> IntEnvConfig:
        return IntEnvConfig(("RELIGION_CHUNK_CLAIM_ANALYZER_WORKERS",), min(3, maximum), 1, maximum)

    def claim_analyzer_batch_workers_config(self, *, maximum: int) -> IntEnvConfig:
        return IntEnvConfig(("RELIGION_CLAIM_ANALYZER_BATCH_WORKERS",), min(3, maximum), 1, maximum)

    def answer_planner_policy(self) -> str:
        return "- Plan only source-grounded claims and explicit retrieval gaps."

    def default_answer_outline(self, language: str = "") -> list[str]:
        return ["Selected evidence", "Limits", "Sources"]

    def answer_plan_relevance_stopwords(self) -> set[str]:
        return {
            "the",
            "and",
            "or",
            "for",
            "with",
            "about",
            "근거",
            "정리",
            "질문",
            "학파",
            "원칙",
            "입장",
            "halal",
            "haram",
            "حلال",
            "حرام",
            "الإسلام",
            "الاسلام",
            "islam",
            "islamic",
            "principles",
            "school",
            "madhhab",
            "في",
            "من",
            "على",
            "عن",
            "إلى",
            "الأرض",
            "الارض",
            "والمال",
            "و",
        }

    def answer_plan_term_too_short(self, normalized: str) -> bool:
        return len(normalized) < 3

    def answer_plan_relevance_aliases(self, terms: list[str]) -> list[str]:
        return []

    def frontier_target_config(self, *, top_k: int, fast_mode: bool = False) -> IntEnvConfig:
        if fast_mode:
            default = max(1, min(int(top_k or 30), 30))
            return IntEnvConfig(("RELIGION_BETA6_FAST_FRONTIER_TARGET",), default, max(1, int(top_k or 1)), 30)
        default = max(max(1, top_k) * 12, 1000)
        return IntEnvConfig(("RELIGION_BETA6_FRONTIER_TARGET",), default, max(1, top_k), 2000)

    def frontier_stop_floor_config(self, *, top_k: int, fast_mode: bool = False) -> IntEnvConfig:
        if fast_mode:
            default = max(1, min(int(top_k or 30), 30))
            return IntEnvConfig(("RELIGION_BETA6_FAST_FRONTIER_STOP_FLOOR",), default, max(1, int(top_k or 1)), 30)
        default = max(max(1, top_k) * 8, 600)
        return IntEnvConfig(("RELIGION_BETA6_FRONTIER_STOP_FLOOR",), default, max(1, top_k), 2000)

    def search_plan_query_limit_config(self, *, requested: int, max_query_limit: int) -> IntEnvConfig:
        del max_query_limit
        return IntEnvConfig((), requested, requested, requested)

    def full_frontier_refine_limit_config(self, *, requested: int) -> IntEnvConfig:
        return IntEnvConfig((), requested, requested, requested)

    def candidate_scan_multiplier_config(self, query: str, *, label: str = "") -> IntEnvConfig:
        del query, label
        return IntEnvConfig((), 1, 1, 20)

    def searchable_keyword(self, keyword: str, *, question: str = "") -> str:
        del question
        return " ".join(str(keyword or "").strip().split())

    def domain_bucket_queries(self, query: str, keywords: list[str]) -> list[str]:
        del query, keywords
        return []

    def prioritize_question_first_for_mcq(self, query: str) -> bool:
        del query
        return False

    def prioritize_domain_buckets_for_mcq(self, query: str) -> bool:
        del query
        return False

    def force_candidate_scan_for_mcq(self, query: str, label: str, search_query: str) -> bool:
        del query, label, search_query
        return False

    def candidate_role_floor_required(self) -> int:
        return 1

    def gateway_writer_prompt(self, query: str, *, evidence: str = "") -> str:
        return ""

    def deterministic_writer_fallback_answer(
        self,
        query: str,
        selected_records: list[dict[str, Any]],
        claim_cards: list[dict[str, Any]],
        *,
        language: str,
        error: str,
    ) -> str | None:
        return None


class LawkeyDomainAdapter(DomainAdapter):
    key = "lawkey"

    def expand_graph_rows(
        self,
        conn: sqlite3.Connection,
        seed_rows: list[sqlite3.Row],
        *,
        query: str = "",
        seed_scores: dict[str, float],
        max_neighbors: int,
        max_expanded: int,
    ) -> tuple[list[sqlite3.Row], dict[str, float]]:
        graph_rows, graph_scores = expand_lawkey_precedent_rows(
            conn,
            seed_rows,
            seed_scores=seed_scores,
            max_neighbors=max_neighbors,
            max_expanded=max_expanded,
        )
        frame_rows, frame_scores = expand_lawkey_event_frame_rows(
            conn,
            query,
            seed_rows,
            max_expanded=max_expanded,
        )
        if not frame_rows:
            return graph_rows, graph_scores
        seen: set[str] = set()
        merged: list[sqlite3.Row] = []
        for row in frame_rows:
            canonical_id = str(row["canonical_id"] or "")
            if canonical_id and canonical_id not in seen:
                seen.add(canonical_id)
                merged.append(row)
        for row in graph_rows:
            canonical_id = str(row["canonical_id"] or "")
            if canonical_id and canonical_id not in seen:
                seen.add(canonical_id)
                merged.append(row)
        scores = dict(graph_scores)
        for key, value in frame_scores.items():
            scores[key] = max(scores.get(key, 0.0), value)
        return merged[:max_expanded], scores


class IslamDomainAdapter(DomainAdapter):
    key = "islam"

    def role_order(self) -> list[str]:
        return ["scripture", "hadith", "tafsir", "madhhab", "fiqh", "sect", "other"]

    def source_role(self, row: Any) -> str:
        source_kind, dataset, title, school, tradition, text = _row_role_text(row)
        if "tafsir" in text or "commentary" in text or "تفسير" in text:
            return "tafsir"
        if any(marker in text for marker in ("scripture", "quran", "qur'an", "قرآن")):
            return "scripture"
        if "hadith" in text or "حديث" in text or "sunnah" in text:
            return "hadith"
        if any(marker in school for marker in ("hanafi", "shafii", "maliki", "hanbali", "jafari")):
            return "madhhab"
        if "fiqh" in text or "فقه" in text or "legal" in text:
            return "fiqh"
        if any(marker in text for marker in ("sunni", "shia", "shiite", "sect", "سني", "شيعة")):
            return "sect"
        return "other"

    def selector_policy(self) -> str:
        return (
            "- Islamic safety: do not issue a binding fatwa or single final ruling.\n"
            "- Prioritize Qur'an when it directly addresses the topic, then hadith, tafsir/commentary, fiqh/madhhab material, and sect/school evidence relevant to the question.\n"
            "- For Korean/English questions, still select Arabic-source evidence when it is the strongest source.\n"
            "- If a requested school/sect is missing from candidates, select the best available source and let the writer state the retrieval gap."
        )

    def selector_role_diversity_rule(self) -> str:
        return _role_diversity_rule("Qur'an/scripture, hadith, tafsir/commentary, fiqh/madhhab, and sect/school evidence")

    def keyword_generation_spec(self) -> tuple[str, str]:
        task = (
            "Generate retrieval keywords for an Islamic source database. Prefer Arabic source terms first, then common English/Korean terms. "
            "For Korean or English questions, still generate Arabic Qur'an/hadith/fiqh terms because most source texts are Arabic. "
            "Include madhhab/sect terms only when the question asks for them. Do not decide a fatwa."
        )
        examples = 'Example keywords: ["ولي", "نكاح", "hanafi", "shafii", "wali", "marriage"]'
        return task, examples

    def additional_keyword_hint(self) -> str:
        return (
            "Use more precise Arabic Qur'an/hadith/fiqh terms, named doctrines, school names, and concrete issue terms. "
            "Avoid generic words such as islam, quran, hadith, ruling unless attached to a concrete issue."
        )

    def claim_analyzer_policy(self) -> str:
        return (
            "- Prefer cards that separate Qur'an, hadith, tafsir, fiqh, madhhab, and sect/tradition evidence.\n"
            "- For legal/theological issues, describe available school positions and retrieval gaps; do not decide a binding ruling.\n"
            "- Keep Arabic source wording when it is the direct quoted evidence."
        )

    def writer_domain_policy(self) -> str:
        return (
            "For Islam, do not present machine output as a Qur'an translation. "
            "Preserve Qur'anic Arabic as source text when present, avoid irreverent framing, and do not issue binding fatwa. "
            "When legal/theological schools or sects may differ, summarize the retrieved school/tradition positions and state retrieval gaps instead of deciding the ruling."
        )

    def writer_return_instruction(self, language: str = "") -> str:
        return (
            _language_guard(language)
            + "Return a structured cited answer. Start with the strongest source layer, then summarize available school/sect positions or explicitly mark retrieval gaps. "
            "When the user asks for madhhab/sect/school comparison, include a section titled '학파/종파별 자료 범위와 공백' in Korean answers. "
            "If no selected claim card supports a requested school or sect, say that the retrieved set did not contain a direct source for that school/sect; do not collapse all schools into a single ruling. "
            "Do not issue a binding fatwa. Every substantive paragraph should cite the selected source labels it uses, then add a short Sources section listing only cited labels."
        )

    def min_answer_chars_default(self) -> int:
        return 2200

    def selector_compact_candidate_lines_config(self) -> BoolEnvConfig:
        return BoolEnvConfig(("RELIGION_ISLAM_SELECTOR_COMPACT_LINES", "RELIGION_SELECTOR_COMPACT_LINES"), True)

    def selector_batch_size_config(self, *, candidate_limit: int) -> IntEnvConfig:
        default = min(100, candidate_limit)
        return IntEnvConfig(("RELIGION_ISLAM_SELECTOR_BATCH_SIZE", "RELIGION_SELECTOR_BATCH_SIZE"), default, 8, max(8, candidate_limit))

    def selector_batch_workers_config(self, *, maximum: int) -> IntEnvConfig:
        return IntEnvConfig(("RELIGION_ISLAM_SELECTOR_BATCH_WORKERS", "RELIGION_SELECTOR_BATCH_WORKERS"), min(4, maximum), 1, maximum)

    def selector_recovery_batch_workers_config(self, *, maximum: int) -> IntEnvConfig:
        return IntEnvConfig(
            ("RELIGION_ISLAM_SELECTOR_RECOVERY_BATCH_WORKERS", "RELIGION_SELECTOR_RECOVERY_BATCH_WORKERS"),
            min(4, maximum),
            1,
            maximum,
        )

    def selector_excerpt_chars_config(self) -> IntEnvConfig:
        return IntEnvConfig(("RELIGION_ISLAM_SELECTOR_EXCERPT_CHARS", "RELIGION_SELECTOR_EXCERPT_CHARS"), 280, 180, 900)

    def selector_excerpt_bytes_config(self) -> IntEnvConfig:
        return IntEnvConfig(("RELIGION_ISLAM_SELECTOR_EXCERPT_BYTES", "RELIGION_SELECTOR_EXCERPT_BYTES"), 360, 240, 1800)

    def claim_analyzer_source_chars_config(self) -> IntEnvConfig:
        return IntEnvConfig(
            ("RELIGION_ISLAM_CLAIM_ANALYZER_SOURCE_CHARS", "RELIGION_CLAIM_ANALYZER_SOURCE_CHARS"),
            900,
            400,
            3000,
        )

    def claim_chunk_text_chars_config(self) -> IntEnvConfig:
        return IntEnvConfig(
            ("RELIGION_ISLAM_CHUNK_CLAIM_ANALYZER_CHARS", "RELIGION_CHUNK_CLAIM_ANALYZER_CHARS"),
            3200,
            800,
            12000,
        )

    def claim_chunk_analyzer_workers_config(self, *, maximum: int) -> IntEnvConfig:
        return IntEnvConfig(
            ("RELIGION_ISLAM_CHUNK_CLAIM_ANALYZER_WORKERS", "RELIGION_CHUNK_CLAIM_ANALYZER_WORKERS"),
            min(5, maximum),
            1,
            maximum,
        )

    def claim_analyzer_batch_workers_config(self, *, maximum: int) -> IntEnvConfig:
        return IntEnvConfig(
            ("RELIGION_ISLAM_CLAIM_ANALYZER_BATCH_WORKERS", "RELIGION_CLAIM_ANALYZER_BATCH_WORKERS"),
            min(5, maximum),
            1,
            maximum,
        )

    def answer_planner_policy(self) -> str:
        return (
            "- Plan Qur'an/hadith/tafsir/fiqh/school-position coverage before any conclusion.\n"
            "- Prefer a comparative structure: strongest source layer, school/sect positions, limits, retrieval gaps.\n"
            "- The plan must prevent a binding fatwa; it should guide the writer to report retrieved positions."
        )

    def default_answer_outline(self, language: str = "") -> list[str]:
        if language == "ko":
            return ["원문 근거 층위", "학파/종파별 입장", "한계와 검색 공백"]
        if language == "ar":
            return ["طبقات الدليل النصي", "مواقف المذاهب أو الاتجاهات", "الحدود والفجوات"]
        return ["Source layers", "School or sect positions", "Limits and retrieval gaps"]

    def answer_plan_relevance_stopwords(self) -> set[str]:
        return super().answer_plan_relevance_stopwords() | {"أصول", "الفقه", "مقاصد", "الشريعة", "المذهب"}

    def answer_plan_relevance_aliases(self, terms: list[str]) -> list[str]:
        joined = " ".join(terms)
        normalized_ar = _normalize_arabic_for_match(joined)
        aliases: list[str] = []
        if "ربا" in normalized_ar or "ربو" in normalized_ar:
            aliases.extend(["riba", "usury", "interest", "ربا", "ربو", "الربا", "الربوا"])
        if "ثرو" in normalized_ar or "توزيع" in normalized_ar:
            aliases.extend(["wealth", "distribution", "redistribution", "ثروة", "الثروة", "توزيع"])
        if "ملكي" in normalized_ar:
            aliases.extend(["property", "ownership", "private ownership", "أموال", "اموال", "مال", "ملكية"])
        if "عدال" in normalized_ar or "اجتماعي" in normalized_ar:
            aliases.extend(["social justice", "charity", "zakat", "poor", "poverty", "صدقات", "زكاة", "الفقراء"])
        if "اشتراكي" in normalized_ar or "شيوعي" in normalized_ar:
            aliases.extend(["socialism", "communism", "materialism", "atheism", "tawhid", "kufr", "shirk", "faith", "belief"])
        return aliases

    def searchable_keyword(self, keyword: str, *, question: str = "") -> str:
        del question
        value = " ".join(str(keyword or "").strip().split())
        aliases = _islam_context_alias_terms(value)
        if aliases:
            return " ".join(aliases[:8])
        if not value or not re.search(r"[A-Za-z]", value):
            return value
        tokens = [token.lower() for token in re.findall(r"[A-Za-z][A-Za-z0-9'-]*", value)]
        stopwords = {
            "in",
            "of",
            "the",
            "and",
            "or",
            "about",
            "islam",
            "islamic",
            "muslim",
            "muslims",
            "ruling",
            "rule",
            "perspective",
        }
        meaningful = [token for token in tokens if token not in stopwords]
        if not meaningful:
            return ""
        prayer_terms = {"prayer", "prayers", "salah", "salat"}
        count_modifiers = {"five", "daily", "number", "count", "counts"}
        if prayer_terms & set(meaningful) and count_modifiers & set(meaningful):
            meaningful = [token for token in meaningful if token not in count_modifiers]
        if len(meaningful) == 1:
            return meaningful[0]
        return " ".join(meaningful[:3])

    def option_aliases(self, option_text: str) -> list[str]:
        cleaned = str(option_text or "").strip()
        aliases = [cleaned] if cleaned else []
        aliases.extend(_islam_context_alias_terms(cleaned))
        return _unique_terms(aliases)

    def multiple_choice_option_terms(self, text: str) -> list[str]:
        parsed = self.parse_multiple_choice(text)
        if parsed is None:
            return []
        terms: list[str] = []
        for option in parsed.options:
            terms.extend(self.option_aliases(option.text))
        return _unique_terms(terms)

    def domain_bucket_queries(self, query: str, keywords: list[str]) -> list[str]:
        text = " ".join([str(query or ""), *[str(keyword or "") for keyword in keywords]])
        aliases = _islam_context_alias_terms(text)
        if not aliases:
            return []
        buckets = [" ".join(aliases[:12])]
        if len(aliases) > 12:
            buckets.append(" ".join(aliases[12:24]))
        return _unique_terms(buckets)

    def candidate_role_floor_required(self) -> int:
        return 2


class CatholicDomainAdapter(DomainAdapter):
    key = "catholic"

    def role_order(self) -> list[str]:
        return ["scripture", "doctrine", "commentary", "liturgy", "other"]

    def source_role(self, row: Any) -> str:
        source_kind, dataset, title, school, tradition, text = _row_role_text(row)
        if any(marker in text for marker in ("scripture", "bible", "vulgate")):
            return "scripture"
        if any(marker in text for marker in ("catechism", "vatican", "council", "official_doctrine", "magisterium")):
            return "doctrine"
        if any(marker in text for marker in ("aquinas", "augustine", "commentary", "patristic", "thomism")):
            return "commentary"
        if any(marker in text for marker in ("liturgy", "missal", "lectionary")):
            return "liturgy"
        return "other"

    def selector_policy(self) -> str:
        return (
            "- Prioritize directly relevant Bible/scripture, Catholic doctrine, and classical commentary evidence.\n"
            "- Prefer canonical verse citations or official doctrine when the question asks a factual Bible/doctrine item.\n"
            "- When the question names an exact Bible citation, treat that verse and its same-chapter narrative context as controlling evidence; do not prefer a distant verse merely because it contains an option name.\n"
            "- Select commentary only when it directly explains the requested passage or doctrine."
        )

    def selector_role_diversity_rule(self) -> str:
        return _role_diversity_rule("scripture, official doctrine, commentary, and liturgical evidence")

    def keyword_generation_spec(self) -> tuple[str, str]:
        task = (
            "Generate retrieval keywords for a Catholic/Christian source database. Prefer source-language search terms, not only the user's language. "
            "For Bible questions, include English Bible book names and abbreviations, canonical references such as Gen 1:14, and English/Latin source terms likely to appear in scripture/commentary. "
            "For doctrine questions, include English Catholic doctrine terms, Catechism/Vatican keywords, and common Korean/English aliases. Do not answer the question."
        )
        examples = 'Example keywords: ["Genesis", "Gen 1:14", "lights", "luminaries", "luminaria", "Catechism grace"]'
        return task, examples

    def additional_keyword_hint(self) -> str:
        return (
            "Add cross-language Bible/doctrine aliases: English book names, standard abbreviations, verse references, Latin/English terms, and Korean aliases. "
            "Avoid broad words such as Bible, church, or doctrine unless attached to a concrete book, verse, concept, council, or catechism topic."
        )

    def searchable_keyword(self, keyword: str, *, question: str = "") -> str:
        del question
        value = " ".join(str(keyword or "").strip().split())
        aliases = _catholic_context_alias_terms(value)
        if aliases:
            return " ".join(aliases[:10])
        return value

    def option_aliases(self, option_text: str) -> list[str]:
        return _catholic_option_alias_terms(option_text)

    def multiple_choice_option_terms(self, text: str) -> list[str]:
        parsed = self.parse_multiple_choice(text)
        if parsed is None:
            return []
        terms: list[str] = []
        for option in parsed.options:
            terms.extend(_catholic_option_alias_terms(option.text))
        return _unique_terms(terms)

    def domain_bucket_queries(self, query: str, keywords: list[str]) -> list[str]:
        text = " ".join([str(query or ""), *[str(keyword or "") for keyword in keywords]])
        aliases = _catholic_context_alias_terms(text)
        aliases.extend(_catholic_bible_reference_citations(text))
        entity_queries = _catholic_public_mcq_entity_queries(query)
        buckets: list[str] = []
        if not aliases:
            return _unique_terms(entity_queries)
        citation_aliases = [
            alias
            for alias in aliases
            if re.fullmatch(r"[1-3]?[A-Z][A-Za-z0-9]{1,7}\s+\d{1,3}:\d{1,3}", str(alias or ""))
        ]
        lexical_aliases = [alias for alias in aliases if alias not in citation_aliases]
        if citation_aliases:
            stem_query = self.search_text(query)
            for citation in citation_aliases[:8]:
                buckets.append(citation)
                if stem_query:
                    buckets.append(f"{stem_query} {citation}")
                if lexical_aliases:
                    buckets.append(" ".join([*lexical_aliases[:4], citation]))
            buckets.append(" ".join([*lexical_aliases[:8], *citation_aliases[:2]]))
            if _catholic_public_chapter_citations(query):
                buckets.append(str(query or ""))
            buckets.extend(entity_queries)
        else:
            buckets.extend(entity_queries)
            buckets.append(" ".join(lexical_aliases[:8]))
        return _unique_terms(buckets)

    def prioritize_question_first_for_mcq(self, query: str) -> bool:
        return self.parse_multiple_choice(query) is not None and bool(_catholic_explicit_bible_reference_citations(query))

    def prioritize_domain_buckets_for_mcq(self, query: str) -> bool:
        return self.parse_multiple_choice(query) is not None and (
            bool(_catholic_public_option_citations(query))
            or bool(_catholic_public_stem_chapter_citations(query))
            or bool(_catholic_public_mcq_entity_queries(query))
        )

    def force_candidate_scan_for_mcq(self, query: str, label: str, search_query: str) -> bool:
        if self.parse_multiple_choice(query) is None:
            return False
        if str(label or "").startswith("mcq_option_") and re.search(r"[가-힣]", str(query or "")):
            return True
        if not str(label or "").startswith("domain_bucket_"):
            return False
        citations = _catholic_bible_reference_citations(query)
        if not citations and re.search(r"[가-힣]", str(query or "")):
            return True
        return any(citation in str(search_query or "") for citation in citations)

    def candidate_scan_multiplier_config(self, query: str, *, label: str = "") -> IntEnvConfig:
        if self.parse_multiple_choice(query) is None:
            return super().candidate_scan_multiplier_config(query, label=label)
        if re.search(r"[가-힣]", str(query or "")) and (
            str(label or "") == "question"
            or str(label or "").startswith("domain_bucket_")
            or str(label or "").startswith("mcq_option_")
        ):
            return IntEnvConfig(("RELIGION_CATHOLIC_BETA6_CANDIDATE_SCAN_MULTIPLIER",), 12, 1, 20)
        return super().candidate_scan_multiplier_config(query, label=label)

    def expand_graph_rows(
        self,
        conn: sqlite3.Connection,
        seed_rows: list[sqlite3.Row],
        *,
        query: str = "",
        seed_scores: dict[str, float],
        max_neighbors: int,
        max_expanded: int,
    ) -> tuple[list[sqlite3.Row], dict[str, float]]:
        del seed_scores, max_neighbors
        rows: list[sqlite3.Row] = []
        scores: dict[str, float] = {}
        seen: set[str] = set()
        option_terms = self.multiple_choice_option_terms(query)
        stem_anchor_terms = _catholic_public_stem_anchor_terms(query)
        public_chapter_citations = set(_catholic_public_chapter_citations(query))
        if re.search(r"[가-힣]", str(query or "")):
            query_books = set(_catholic_full_book_abbreviations(query))
            sibling_citations: list[str] = []
            sibling_citation_set: set[str] = set()
            for seed in seed_rows:
                citation = _catholic_row_citation(seed)
                parts = _catholic_bible_reference_parts(citation)
                if not citation or parts is None:
                    continue
                if query_books and parts[0] not in query_books:
                    continue
                if citation in sibling_citation_set:
                    continue
                sibling_citation_set.add(citation)
                sibling_citations.append(citation)
                if len(sibling_citations) >= 40:
                    break
            if sibling_citations:
                placeholders = ",".join("?" for _citation in sibling_citations)
                sibling_limit = max(8, min(max_expanded, len(sibling_citations) * 8))
                try:
                    sibling_rows = conn.execute(
                        f"""
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
                        WHERE case_number IN ({placeholders})
                          AND (source_dataset LIKE '%/korean/%' OR title LIKE '%Korean%')
                        LIMIT ?
                        """,
                        (*sibling_citations, sibling_limit),
                    ).fetchall()
                except sqlite3.OperationalError:
                    sibling_rows = []
                citation_order = {citation: index for index, citation in enumerate(sibling_citations)}
                sibling_rows = sorted(
                    sibling_rows,
                    key=lambda row: (
                        citation_order.get(str(row["case_number"] or ""), len(citation_order)),
                        str(row["canonical_id"] or ""),
                    ),
                )
                for row in sibling_rows:
                    canonical_id = str(row["canonical_id"] or "")
                    if not canonical_id or canonical_id in seen:
                        continue
                    seen.add(canonical_id)
                    rows.append(row)
                    scores[canonical_id] = 1180.0
                    if len(rows) >= max_expanded:
                        return rows, scores
        for citation in _catholic_bible_reference_citations(query)[:8]:
            parts = _catholic_bible_reference_parts(citation)
            found = conn.execute(
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
                WHERE case_number = ?
                LIMIT 8
                """,
                (citation,),
            ).fetchall()
            for row in found:
                canonical_id = str(row["canonical_id"] or "")
                if not canonical_id or canonical_id in seen:
                    continue
                seen.add(canonical_id)
                rows.append(row)
                scores[canonical_id] = 1200.0
                if len(rows) >= max_expanded:
                    return rows, scores
            if parts is None:
                continue
            book, chapter, verse = parts
            chapter_rows = _catholic_bible_chapter_context_rows(
                conn,
                book,
                chapter,
                verse,
                limit=72,
                option_terms=option_terms,
                anchor_terms=stem_anchor_terms if citation in public_chapter_citations else [],
            )
            for row, score in chapter_rows:
                canonical_id = str(row["canonical_id"] or "")
                if not canonical_id or canonical_id in seen:
                    continue
                seen.add(canonical_id)
                rows.append(row)
                scores[canonical_id] = score
                if len(rows) >= max_expanded:
                    return rows, scores
        return rows, scores

    def candidate_role_floor_required(self) -> int:
        return 2

    def postprocess_selected_rows(
        self,
        query: str,
        candidates: list[Any],
        selected_rows: list[Any],
        *,
        limit: int,
    ) -> list[Any]:
        parsed = self.parse_multiple_choice(query)
        citations = _catholic_explicit_bible_reference_citations(query)
        if parsed is None or not citations or limit <= 0:
            return selected_rows[:limit]
        parts = _catholic_bible_reference_parts(citations[0])
        if parts is None:
            return selected_rows[:limit]
        book, chapter, _verse = parts
        option_terms = self.multiple_choice_option_terms(query)
        frame_candidates = [
            row
            for row in candidates
            if _catholic_row_same_book_chapter(row, book, chapter)
            and _catholic_row_source_role_text(row).find("scripture") >= 0
        ]
        if len(frame_candidates) < 3:
            return selected_rows[:limit]

        exact_rows = [row for row in frame_candidates if _catholic_row_citation(row) == citations[0]]
        option_anchor_rows = [row for row in frame_candidates if _catholic_row_has_any_term(row, option_terms)]
        selected_frame_rows = [row for row in selected_rows if _catholic_row_same_book_chapter(row, book, chapter)]
        selected_remote_rows = [row for row in selected_rows if not _catholic_row_same_book_chapter(row, book, chapter)]

        ordered: list[Any] = []
        seen: set[str] = set()

        def add(row: Any) -> None:
            if len(ordered) >= limit:
                return
            canonical_id = str(getattr(row, "canonical_id", "") or "")
            if not canonical_id or canonical_id in seen:
                return
            seen.add(canonical_id)
            ordered.append(row)

        for bucket in (exact_rows, option_anchor_rows, selected_frame_rows, frame_candidates, selected_remote_rows):
            for row in bucket:
                add(row)
        return ordered[:limit]

    def priority_context_candidate_rows(self, query: str, rows: list[Any]) -> tuple[list[Any], list[Any]]:
        citations = _catholic_explicit_bible_reference_citations(query)
        if not citations:
            citation_set = set(_catholic_public_option_citations(query))
            chapter_parts = [
                parts
                for citation in _catholic_public_chapter_citations(query)
                if (parts := _catholic_bible_reference_parts(citation)) is not None
            ]
            stem_anchor_terms = _catholic_public_stem_anchor_terms(query)
            option_terms = self.multiple_choice_option_terms(query)
            if not citation_set:
                return _catholic_korean_mcq_scripture_priority_rows(query, rows)
            priority_entries: list[tuple[int, int, int, int, Any]] = []
            ordinary: list[Any] = []
            for index, row in enumerate(rows):
                exact_citation = _catholic_row_citation(row) in citation_set
                anchor_count = _catholic_row_stem_anchor_match_count(row, stem_anchor_terms)
                same_chapter = bool(
                    chapter_parts
                    and any(_catholic_row_same_book_chapter(row, book, chapter) for book, chapter, _verse in chapter_parts)
                )
                same_chapter_anchor = bool(
                    same_chapter
                    and anchor_count >= 2
                )
                same_chapter_option = bool(same_chapter and _catholic_row_has_any_term(row, option_terms))
                if exact_citation or same_chapter_anchor or same_chapter_option:
                    priority_entries.append((anchor_count, 1 if same_chapter_option else 0, 1 if exact_citation else 0, index, row))
                else:
                    ordinary.append(row)
            priority_entries.sort(key=lambda item: (-item[0], -item[1], -item[2], item[3]))
            priority = [row for _anchor_count, _option, _exact, _index, row in priority_entries]
            return priority, ordinary
        parts = _catholic_bible_reference_parts(citations[0])
        if parts is None:
            return [], rows
        book, chapter, _verse = parts
        priority: list[Any] = []
        ordinary: list[Any] = []
        for row in rows:
            if _catholic_row_same_book_chapter(row, book, chapter):
                priority.append(row)
            else:
                ordinary.append(row)
        return priority, ordinary


class SimliDomainAdapter(DomainAdapter):
    key = "simli"

    def role_order(self) -> list[str]:
        return ["diagnostic", "guideline", "research", "therapy", "safety", "case", "other"]

    def source_role(self, row: Any) -> str:
        source_kind, dataset, title, school, tradition, text = _row_role_text(row)
        if any(marker in text for marker in ("dsm", "icd", "diagnostic")):
            return "diagnostic"
        if "guideline" in text or "who:" in dataset:
            return "guideline"
        if any(marker in text for marker in ("research", "paper", "pmc", "s2:", "openalex", "meta")):
            return "research"
        if any(marker in text for marker in ("cbt", "therapy", "treatment", "intervention")):
            return "therapy"
        if any(marker in text for marker in ("crisis", "suicide", "self harm", "safety", "emergency")):
            return "safety"
        if "patient_case" in text or "case" in text:
            return "case"
        return "other"

    def selector_policy(self) -> str:
        return (
            "- Mental-health safety: do not diagnose; crisis and self-harm evidence outranks ordinary psychoeducation.\n"
            "- Prioritize clinical guideline, DSM/ICD-style, CBT/therapy, sleep/anxiety/depression evidence, and safety planning sources.\n"
            "- Select sources that support cautious framing and referral boundaries."
        )

    def selector_role_diversity_rule(self) -> str:
        return _role_diversity_rule("guideline, diagnostic, research, therapy, safety, and case evidence")

    def keyword_generation_spec(self) -> tuple[str, str]:
        task = (
            "Generate retrieval keywords for psychology and mental-health evidence. Prefer clinical English terms plus Korean symptom terms. "
            "Include crisis/safety terms when the user describes self-harm or immediate risk. Do not diagnose."
        )
        examples = 'Example keywords: ["insomnia", "anxiety", "panic", "CBT", "수면", "불안"]'
        return task, examples

    def additional_keyword_hint(self) -> str:
        return (
            "Use clinical terms, guideline terminology, therapy mechanism terms, and safety terms when relevant. "
            "Avoid generic words such as mental health or counseling alone."
        )

    def claim_analyzer_policy(self) -> str:
        return (
            "- Separate diagnostic-category evidence, guideline/safety evidence, CBT/therapy mechanism evidence, research, and patient cases.\n"
            "- Do not diagnose the user; describe literature categories only."
        )

    def writer_domain_policy(self) -> str:
        return (
            "For mental health, do not diagnose or say the user has a disorder. "
            "Phrase diagnostic labels as literature categories only, e.g. 'these symptoms are discussed in sources about anxiety/insomnia', not 'you may have GAD'. "
            "Give cautious psychoeducation and safety/referral boundaries; if crisis or immediate danger is present, direct the user to local emergency support first. "
            "Use DSM/ICD or clinical guidelines for symptom categories and safety boundaries, CBT or therapy outcome papers for CBT explanations, and patient cases only as differential-diagnosis examples."
        )

    def writer_return_instruction(self, language: str = "") -> str:
        clinical_sections = (
            "Use these section headers exactly when answering in Korean:\n"
            "## 1. 가능 가설 (Differential)\n"
            "## 2. 왜 이 가설인가 (Rationale)\n"
            "## 3. 추가 평가 필요 (What to Probe Next)\n"
            "## 4. 다음 세션 개입 (Next-Session Action Plan)\n"
            "## 5. 약물 / 의뢰 고려 (Pharm & Referral)\n"
            "## 6. 안전 계획 + 모니터링 (Safety & Monitoring)\n"
            "## 7. 근거 한계 (Evidence Gaps)\n"
            "## References\n"
        )
        return (
            _language_guard(language)
            + clinical_sections
            + "Return a clinician-shaped, structured cited answer: rank plausible hypotheses/formulations as literature categories, explain what fits and what argues against, list concrete next assessment questions/tools, outline next-session psychoeducation or CBT-style steps when supported, and state referral/safety boundaries. "
            "Cite DSM/ICD or clinical guideline sources for symptom categories and safety checks; cite CBT/therapy papers when explaining CBT; use patient cases only for differential medical examples. "
            "If a selected source is marked writer_use: CBT_EXPLANATION, the CBT formulation paragraph must cite at least one such source. "
            "Do not write verbatim quote text inline; users can open cited source windows for exact highlighted text. "
            "Every substantive paragraph should cite the selected source labels it uses. End with a short Sources section listing only cited labels."
        )

    def source_usage_hint(self, record: dict[str, Any]) -> str:
        metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
        source_kind = str(metadata.get("sourceKind") or record.get("doc_type") or "").lower()
        title = str(record.get("document_title") or "").lower()
        text = f"{title} {source_kind}"
        if source_kind in {"dsm5_chunk", "icd11_entity"}:
            return "SYMPTOM_CATEGORY_NOT_DIAGNOSIS"
        if source_kind in {"guideline", "guideline_chunk"}:
            return "SAFETY_AND_TREATMENT_BOUNDARY"
        if source_kind == "patient_case":
            return "DIFFERENTIAL_MEDICAL_EXAMPLE_ONLY"
        if any(marker in text for marker in ("cbt", "cognitive behavioral", "therapy", "exposure", "anxiety treatment")):
            return "CBT_EXPLANATION"
        if "interocept" in text:
            return "INTEROCEPTION_MECHANISM_LOWER_TIER"
        return ""

    def min_answer_chars_default(self) -> int:
        return 1500

    def selector_timeout_config(self, *, chat_timeout: float) -> FloatEnvConfig:
        return FloatEnvConfig(("RELIGION_SIMLI_SELECTOR_TIMEOUT_SECONDS",), 45.0, 5.0, chat_timeout)

    def selector_candidate_limit_config(self, *, available: int) -> IntEnvConfig:
        default = available if available else 400
        maximum = max(120, min(max(default, available), 1200))
        return IntEnvConfig(("RELIGION_SIMLI_SELECTOR_CANDIDATE_LIMIT",), default, 8, maximum)

    def selector_batch_size_config(self, *, candidate_limit: int) -> IntEnvConfig:
        default = min(25, candidate_limit)
        return IntEnvConfig(("RELIGION_SIMLI_SELECTOR_BATCH_SIZE",), default, 8, max(8, candidate_limit))

    def selector_recovery_batch_size_config(self, *, batch_size: int, maximum: int) -> IntEnvConfig:
        default = min(25, max(8, int(batch_size or 1) // 2))
        return IntEnvConfig(("RELIGION_SIMLI_SELECTOR_RECOVERY_BATCH_SIZE",), default, 2, maximum)

    def selector_rate_limit_retries_config(self) -> IntEnvConfig:
        return IntEnvConfig(("RELIGION_SIMLI_SELECTOR_RATE_LIMIT_RETRIES", "RELIGION_SELECTOR_RATE_LIMIT_RETRIES"), 3, 0, 5)

    def selector_rate_limit_backoff_config(self) -> FloatEnvConfig:
        return FloatEnvConfig(
            ("RELIGION_SIMLI_SELECTOR_RATE_LIMIT_BACKOFF_SECONDS", "RELIGION_SELECTOR_RATE_LIMIT_BACKOFF_SECONDS"),
            5.0,
            0.0,
            60.0,
        )

    def selector_batch_workers_config(self, *, maximum: int) -> IntEnvConfig:
        return IntEnvConfig(("RELIGION_SIMLI_SELECTOR_BATCH_WORKERS",), min(2, maximum), 1, maximum)

    def selector_recovery_batch_workers_config(self, *, maximum: int) -> IntEnvConfig:
        return IntEnvConfig(
            ("RELIGION_SIMLI_SELECTOR_RECOVERY_BATCH_WORKERS", "RELIGION_SELECTOR_RECOVERY_BATCH_WORKERS"),
            min(4, maximum),
            1,
            maximum,
        )

    def answer_planner_policy(self) -> str:
        return (
            "- Plan DSM/guideline category, therapy mechanism, research, patient-case limits, safety/referral, and retrieval-gap coverage.\n"
            "- The plan must prevent user-specific diagnosis."
        )

    def default_answer_outline(self, language: str = "") -> list[str]:
        if language == "ko":
            return ["문헌상 증상 범주", "치료/상담 근거", "안전·평가 경계"]
        return ["Symptom categories in sources", "Therapy and counseling evidence", "Safety and assessment boundary"]

    def frontier_target_config(self, *, top_k: int, fast_mode: bool = False) -> IntEnvConfig:
        if fast_mode:
            return super().frontier_target_config(top_k=top_k, fast_mode=fast_mode)
        default = max(max(1, top_k) * 4, 400)
        return IntEnvConfig(("RELIGION_SIMLI_BETA6_FRONTIER_TARGET",), default, max(1, top_k), 1200)

    def frontier_stop_floor_config(self, *, top_k: int, fast_mode: bool = False) -> IntEnvConfig:
        if fast_mode:
            return super().frontier_stop_floor_config(top_k=top_k, fast_mode=fast_mode)
        default = max(max(1, top_k) * 3, 300)
        return IntEnvConfig(("RELIGION_SIMLI_BETA6_FRONTIER_STOP_FLOOR",), default, max(1, top_k), 1200)

    def search_plan_query_limit_config(self, *, requested: int, max_query_limit: int) -> IntEnvConfig:
        del requested
        return IntEnvConfig(("RELIGION_SIMLI_BETA6_PER_QUERY_LIMIT",), 120, 24, max_query_limit)

    def searchable_keyword(self, keyword: str, *, question: str = "") -> str:
        value = " ".join(str(keyword or "").strip().split())
        if not value:
            return ""
        contextualized = _simli_contextualized_source_role_keyword(question, value)
        if contextualized:
            return contextualized
        sanitized = _simli_sanitized_generated_keyword(value, question=question)
        if sanitized is not None:
            return sanitized
        return value

    def candidate_role_floor_required(self) -> int:
        return 2


class TcmDomainAdapter(DomainAdapter):
    key = "tcm"
    surface_token_limit = 16
    surface_term_limit = 12

    low_signal_surface_terms = {
        "고문헌",
        "근거",
        "정리",
        "정리해줘",
        "알려줘",
        "써도",
        "되는지",
        "중",
        "문헌",
        "기반",
        "what",
        "does",
        "do",
        "say",
        "about",
        "classical",
        "sources",
        "위",
        "한의사",
        "국가시험",
        "객관식",
        "문제의",
        "정답",
        "번호",
        "번호를",
        "고르세요",
        "답변",
        "첫",
        "줄은",
        "반드시",
        "형식으로",
        "시작하세요",
    }

    def role_order(self) -> list[str]:
        return ["classic", "materia", "formulary", "safety", "case", "modern", "other"]

    def source_role(self, row: Any) -> str:
        source_kind, dataset, title, school, tradition, text = _row_role_text(row)
        if any(marker in text for marker in ("classic_canon", "classic_authoritative", "classic", "canon")):
            return "classic"
        if "materia" in text or "本草" in text or "bencao" in text:
            return "materia"
        if "formulary" in text or "formula" in text or "方" in text:
            return "formulary"
        if any(marker in text for marker in ("contra", "safety", "pregnancy", "禁忌", "금기")):
            return "safety"
        if "case_record" in text or "case" in text or "醫案" in text:
            return "case"
        if "modern" in text or "clinical" in text:
            return "modern"
        return "other"

    def selector_policy(self) -> str:
        return (
            "- TCM safety: do not diagnose, prescribe dosage, or tell the user to take/stop herbs.\n"
            "- Prioritize classics, materia medica, formula texts, contraindication/safety passages, and pattern-differentiation evidence.\n"
            "- Select safety evidence when pregnancy, contraindication, toxicity, or modern clinical risk appears."
        )

    def selector_role_diversity_rule(self) -> str:
        return _role_diversity_rule(
            "classic canon, materia_medica, formulary/formula, safety/contraindication, and authoritative commentary evidence"
        )

    def keyword_generation_spec(self) -> tuple[str, str]:
        task = (
            "Generate retrieval keywords for Korean/Chinese medicine sources. Prefer Korean, Hanja/Chinese, and concise English biomedical equivalents. "
            "Separate herb/formula/pattern/safety terms when relevant. Do not diagnose or prescribe."
        )
        examples = 'Example keywords: ["甘草", "감초", "妊娠", "禁忌", "본초", "licorice"]'
        return task, examples

    def additional_keyword_hint(self) -> str:
        return (
            "Use additional herb/formula/pattern/classic Chinese/Korean terms and safety terms. "
            "Avoid generic words such as medicine, source, evidence, or classical unless attached to a concrete term."
        )

    def claim_analyzer_policy(self) -> str:
        return (
            "- Separate classics, materia medica, formulas, contraindication/safety passages, modern cases, and retrieval gaps.\n"
            "- Do not turn historical text into a user prescription."
        )

    def writer_domain_policy(self) -> str:
        return (
            "For Korean/Chinese medicine, do not diagnose or prescribe. "
            "Separate classical text evidence, materia medica/formulary claims, modern case records, and clinical advice. "
            "Always flag contraindication, pregnancy, medication, pediatric, chronic disease, and urgent-symptom boundaries. "
            "If a source describes a historical formula or decoction, explicitly say it is not an instruction for the user to take it."
        )

    def writer_return_instruction(self, language: str = "") -> str:
        return (
            _language_guard(language)
            + "Return a structured cited answer. Separate classical canon, materia medica/formulary, modern cases, contraindication/safety boundary, and retrieval gaps. "
            "Do not diagnose or prescribe. Every substantive paragraph should cite the selected source labels it uses, then add a short Sources section listing only cited labels."
        )

    def min_answer_chars_default(self) -> int:
        return 2400

    def selector_primary_timeout_config(self, *, selector_timeout: float) -> FloatEnvConfig:
        return FloatEnvConfig(("RELIGION_TCM_SELECTOR_PRIMARY_TIMEOUT_SECONDS",), selector_timeout, 5.0, selector_timeout)

    def selector_batch_size_config(self, *, candidate_limit: int) -> IntEnvConfig:
        default = min(100, candidate_limit)
        return IntEnvConfig(("RELIGION_TCM_SELECTOR_BATCH_SIZE", "RELIGION_SELECTOR_BATCH_SIZE"), default, 8, max(8, candidate_limit))

    def selector_batch_workers_config(self, *, maximum: int) -> IntEnvConfig:
        return IntEnvConfig(("RELIGION_TCM_SELECTOR_BATCH_WORKERS", "RELIGION_SELECTOR_BATCH_WORKERS"), min(6, maximum), 1, maximum)

    def selector_recovery_batch_workers_config(self, *, maximum: int) -> IntEnvConfig:
        return IntEnvConfig(
            ("RELIGION_TCM_SELECTOR_RECOVERY_BATCH_WORKERS", "RELIGION_SELECTOR_RECOVERY_BATCH_WORKERS"),
            min(4, maximum),
            1,
            maximum,
        )

    def selector_excerpt_chars_config(self) -> IntEnvConfig:
        return IntEnvConfig(("RELIGION_TCM_SELECTOR_EXCERPT_CHARS", "RELIGION_SELECTOR_EXCERPT_CHARS"), 280, 180, 900)

    def selector_excerpt_bytes_config(self) -> IntEnvConfig:
        return IntEnvConfig(("RELIGION_TCM_SELECTOR_EXCERPT_BYTES", "RELIGION_SELECTOR_EXCERPT_BYTES"), 560, 300, 1800)

    def answer_planner_policy(self) -> str:
        return (
            "- Plan classical, materia medica/formulary, modern case, safety/contraindication, and retrieval-gap coverage.\n"
            "- The plan must prevent diagnosis or prescription."
        )

    def default_answer_outline(self, language: str = "") -> list[str]:
        if language == "ko":
            return ["고전/본초 근거", "방제·현대 사례", "금기와 진료 경계"]
        return ["Classical and materia evidence", "Formulary and modern cases", "Contraindication and care boundary"]

    def answer_plan_relevance_stopwords(self) -> set[str]:
        return super().answer_plan_relevance_stopwords() | {"本草", "본초", "中醫典籍", "중의전적", "고전", "classic", "classical"}

    def answer_plan_term_too_short(self, normalized: str) -> bool:
        if len(normalized) >= 3:
            return False
        return not (len(normalized) >= 2 and _contains_cjk_or_hangul(normalized))

    def answer_plan_relevance_aliases(self, terms: list[str]) -> list[str]:
        joined = " ".join(terms).lower()
        aliases: list[str] = []
        if any(term in joined for term in ("감초", "甘草", "glycyrrhizin", "licorice", "gancao")):
            aliases.extend(["甘草", "감초", "licorice", "gancao", "glycyrrhiza", "glycyrrhizin", "甘草酸"])
        if any(term in joined for term in ("계지", "桂枝", "guizhi", "cinnamon twig")):
            aliases.extend(["桂枝", "계지", "guizhi", "cinnamon twig", "桂枝湯", "桂枝加芍藥湯"])
        if any(term in joined for term in ("임신", "妊娠", "pregnancy", "pregnant")):
            aliases.extend(["妊娠", "임신", "pregnancy", "pregnant", "孕婦", "胎"])
        if any(term in joined for term in ("금기", "禁忌", "contraindication", "safety", "안전")):
            aliases.extend(["禁忌", "금기", "contraindication", "safety", "安全", "毒性"])
        return aliases

    def full_frontier_refine_limit_config(self, *, requested: int) -> IntEnvConfig:
        return IntEnvConfig(("RELIGION_TCM_BETA6_FULL_FRONTIER_REFINE_LIMIT",), 160, 24, requested)

    def candidate_role_floor_required(self) -> int:
        return 2

    def parse_multiple_choice(self, text: str) -> MultipleChoiceQuestion | None:
        parsed = parse_tcm_mcq(text)
        if parsed is None:
            return None
        return MultipleChoiceQuestion(
            stem=parsed.stem,
            options=tuple(
                MultipleChoiceOption(number=option.number, text=option.text, marker=option.marker)
                for option in parsed.options
            ),
        )

    def multiple_choice_prompt_block(self, text: str) -> str:
        return tcm_mcq_prompt_block(text)

    def multiple_choice_option_terms(self, text: str) -> list[str]:
        return tcm_mcq_option_terms(text)

    def option_aliases(self, option_text: str) -> list[str]:
        return tcm_option_aliases(option_text)

    def direct_option_terms(self, terms: list[str]) -> list[str]:
        out: list[str] = []
        for term in _unique_terms(terms):
            cleaned = str(term or "").strip()
            if len(cleaned) < 2:
                continue
            if self.is_low_signal_surface_term(cleaned):
                continue
            if not (
                re.search(r"(탕|환|원|산|전|단|음|丸|元|湯|汤|散|煎|丹|飮|饮)$", cleaned)
                or re.fullmatch(r"[A-Z][A-Z0-9-]{1,12}", cleaned)
                or re.fullmatch(r"[A-Za-z]{2,12}", cleaned)
            ):
                continue
            out.append(cleaned)
        return out

    def search_text(self, text: str) -> str:
        return tcm_mcq_search_text(text)

    def is_low_signal_surface_term(self, term: str) -> bool:
        return str(term or "").strip("؟،,.!?").lower() in self.low_signal_surface_terms

    def drop_surface_term(self, term: str) -> bool:
        return bool(re.fullmatch(r"\d{1,3}", str(term or "")))

    def expand_graph_rows(
        self,
        conn: sqlite3.Connection,
        seed_rows: list[sqlite3.Row],
        *,
        query: str = "",
        seed_scores: dict[str, float],
        max_neighbors: int,
        max_expanded: int,
    ) -> tuple[list[sqlite3.Row], dict[str, float]]:
        return expand_tcm_passage_graph_rows(
            conn,
            seed_rows,
            seed_scores=seed_scores,
            max_neighbors=max_neighbors,
            max_expanded=max_expanded,
        )

    def gateway_writer_prompt(self, query: str, *, evidence: str = "") -> str:
        question_text = _gateway_tcm_exam_question_text(query)
        if not question_text:
            return ""
        prompt = (
            f"다음 객관식 문제의 정답 번호만 답하세요. 문제: {question_text} 답은 정답: 번호 형식."
            f" 정답: 1 또는 정답: 2 또는 정답: 3 또는 정답: 4 또는 정답: 5 중 하나로 쓰세요."
        )
        if evidence:
            prompt += f" 참고자료: {_gateway_sanitize_exam_text(evidence)[:1200]}"
        return prompt[:3500]

    def deterministic_writer_fallback_answer(
        self,
        query: str,
        selected_records: list[dict[str, Any]],
        claim_cards: list[dict[str, Any]],
        *,
        language: str,
        error: str,
    ) -> str | None:
        if not _env_flag_default("RELIGION_MCQ_HEURISTICS_ENABLED", False):
            return None
        parsed = self.parse_multiple_choice(query)
        if parsed is None or not parsed.options:
            return None
        record_texts = [_fallback_record_text(record) for record in selected_records if isinstance(record, dict)]
        claim_texts = [_fallback_claim_card_text(card) for card in claim_cards if isinstance(card, dict)]
        record_compacts = [_compact_text(text) for text in record_texts]
        claim_compacts = [_compact_text(text) for text in claim_texts]
        evidence_compact = "\n".join([*record_compacts, *claim_compacts])
        best_option = parsed.options[0]
        best_score = -1
        score_details: list[tuple[int, int, int, int, int]] = []
        for option in parsed.options:
            needles = [_compact_text(term) for term in self.option_aliases(option.text)]
            needles = [needle for needle in needles if needle]
            name_hits = sum(evidence_compact.count(needle) for needle in needles)
            record_hits = sum(1 for text in record_compacts if any(needle in text for needle in needles))
            claim_hits = sum(1 for text in claim_compacts if any(needle in text for needle in needles))
            first_record_rank = next(
                (index for index, text in enumerate(record_compacts, start=1) if any(needle in text for needle in needles)),
                0,
            )
            rank_bonus = max(0, 8 - first_record_rank) if first_record_rank else 0
            score = (name_hits * 3) + (record_hits * 8) + (claim_hits * 5) + rank_bonus
            score_details.append((option.number, score, name_hits, record_hits, claim_hits))
            if score > best_score:
                best_option = option
                best_score = score
        score_line = ", ".join(
            f"{number}={score}/n{name_hits}/r{record_hits}/c{claim_hits}"
            for number, score, name_hits, record_hits, claim_hits in score_details
        )
        if language == "ko":
            reason = (
                "writer provider 오류로 selected records와 claim cards의 보기명 매칭 점수를 사용한 fallback입니다.\n"
                f"fallback_score: {score_line}"
            )
            return f"정답: {best_option.number}) {best_option.text}\n\n{reason}"
        return (
            f"Answer: {best_option.number}) {best_option.text}\n\n"
            "Fallback used selected records, claim cards, and option-name matching after writer provider failure.\n"
            f"fallback_score: {score_line}"
        )


_DEFAULT_ADAPTER = DomainAdapter()
_ADAPTERS: dict[str, DomainAdapter] = {
    "catholic": CatholicDomainAdapter(),
    "islam": IslamDomainAdapter(),
    "lawkey": LawkeyDomainAdapter(),
    "simli": SimliDomainAdapter(),
    "tcm": TcmDomainAdapter(),
}


def get_domain_adapter(product: ProductProfile | str | None) -> DomainAdapter:
    key = product.key if isinstance(product, ProductProfile) else str(product or "")
    return _ADAPTERS.get(key, _DEFAULT_ADAPTER)


def _unique_terms(terms: list[str]) -> list[str]:
    out: list[str] = []
    for term in terms:
        cleaned = str(term or "").strip()
        if cleaned and cleaned not in out:
            out.append(cleaned)
    return out


_ISLAM_CONTEXT_ALIASES: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (
        ("제한된 투자 계좌", "제한 투자 계좌", "restricted investment account", "restricted investment accounts"),
        ("restricted investment account", "restricted investment accounts", "RIA", "restricted IAH"),
    ),
    (
        ("무제한 투자 계좌", "무제한 투자계좌", "unrestricted investment account", "unrestricted investment accounts"),
        ("unrestricted investment account", "unrestricted investment accounts", "UIA", "unrestricted IAH"),
    ),
    (
        ("투자 계좌 보유자", "투자계좌 보유자", "계좌 보유자", "investment account holder"),
        ("investment account holder", "investment account holders", "IAH"),
    ),
    (
        ("자금 혼합", "자금의 혼합", "혼합된 자금", "fund commingling", "commingling of funds"),
        ("fund commingling", "commingling of funds", "mixing of funds", "commingled funds"),
    ),
    (
        ("고객의 기밀", "고객 기밀", "기밀 유지", "비밀 유지", "confidentiality"),
        ("customer confidentiality", "client confidentiality", "confidentiality of customers", "information disclosure"),
    ),
    (
        ("상업적 위험", "commercial risk"),
        ("commercial risk", "displaced commercial risk", "commercial risk transfer"),
    ),
    (
        ("기업 지배구조", "지배구조", "governance"),
        ("corporate governance", "governance", "shariah governance"),
    ),
    (
        ("무라바하", "murabaha", "murabahah"),
        ("murabaha", "murabahah", "commodity murabaha", "tawarruq"),
    ),
    (
        ("본인 역할", "본인", "principal"),
        ("principal", "as principal", "principal role"),
    ),
    (
        ("대리인 역할", "대리인", "agent", "agency"),
        ("agent", "agency", "wakil", "agency role"),
    ),
    (
        ("이자부 예금", "이자 예금", "interest-bearing deposit", "interest bearing deposit"),
        ("interest-bearing deposits", "interest bearing deposits", "interest based deposits", "riba deposit"),
    ),
    (
        ("재무 심사", "재무 비율", "financial screening", "financial ratio"),
        ("financial screening", "financial ratio screening", "shariah screening", "screening ratio"),
    ),
    (
        ("시가총액", "market capitalization", "market capitalisation"),
        ("market capitalization", "market capitalisation", "market cap"),
    ),
    (
        ("이슬람 은행", "이슬람 금융", "islamic bank", "islamic finance"),
        ("Islamic finance", "Islamic banking", "AAOIFI", "IFSB", "Shariah standard"),
    ),
)


def _islam_context_alias_terms(text: str) -> list[str]:
    value = unicodedata.normalize("NFKC", str(text or "")).casefold()
    if not value:
        return []
    aliases: list[str] = []
    for markers, terms in _ISLAM_CONTEXT_ALIASES:
        if any(marker.casefold() in value for marker in markers):
            aliases.extend(terms)
    return _unique_terms(aliases)


_CATHOLIC_BIBLE_BOOK_ALIASES: tuple[tuple[str, str, str], ...] = (
    ("창세기", "Genesis", "Gen"),
    ("출애굽기", "Exodus", "Exod"),
    ("출애굽", "Exodus", "Exod"),
    ("레위기", "Leviticus", "Lev"),
    ("민수기", "Numbers", "Num"),
    ("신명기", "Deuteronomy", "Deut"),
    ("여호수아", "Joshua", "Josh"),
    ("사사기", "Judges", "Judg"),
    ("룻기", "Ruth", "Ruth"),
    ("사무엘상", "1 Samuel", "1Sam"),
    ("사무엘하", "2 Samuel", "2Sam"),
    ("열왕기상", "1 Kings", "1Kgs"),
    ("열왕기하", "2 Kings", "2Kgs"),
    ("역대상", "1 Chronicles", "1Chr"),
    ("역대하", "2 Chronicles", "2Chr"),
    ("에스라", "Ezra", "Ezra"),
    ("느헤미야", "Nehemiah", "Neh"),
    ("에스더", "Esther", "Esth"),
    ("욥기", "Job", "Job"),
    ("시편", "Psalms", "Ps"),
    ("잠언", "Proverbs", "Prov"),
    ("전도서", "Ecclesiastes", "Eccl"),
    ("아가", "Song of Songs", "Song"),
    ("이사야", "Isaiah", "Isa"),
    ("예레미야", "Jeremiah", "Jer"),
    ("예레미야애가", "Lamentations", "Lam"),
    ("애가", "Lamentations", "Lam"),
    ("에스겔", "Ezekiel", "Ezek"),
    ("다니엘", "Daniel", "Dan"),
    ("호세아", "Hosea", "Hos"),
    ("요엘", "Joel", "Joel"),
    ("아모스", "Amos", "Amos"),
    ("오바댜", "Obadiah", "Obad"),
    ("요나", "Jonah", "Jonah"),
    ("미가", "Micah", "Mic"),
    ("나훔", "Nahum", "Nah"),
    ("하박국", "Habakkuk", "Hab"),
    ("스바냐", "Zephaniah", "Zeph"),
    ("학개", "Haggai", "Hag"),
    ("스가랴", "Zechariah", "Zech"),
    ("말라기", "Malachi", "Mal"),
    ("마태복음", "Matthew", "Matt"),
    ("마가복음", "Mark", "Mark"),
    ("누가복음", "Luke", "Luke"),
    ("요한복음", "John", "John"),
    ("사도행전", "Acts", "Acts"),
    ("로마서", "Romans", "Rom"),
    ("고린도전서", "1 Corinthians", "1Cor"),
    ("고린도후서", "2 Corinthians", "2Cor"),
    ("갈라디아서", "Galatians", "Gal"),
    ("에베소서", "Ephesians", "Eph"),
    ("빌립보서", "Philippians", "Phil"),
    ("골로새서", "Colossians", "Col"),
    ("데살로니가전서", "1 Thessalonians", "1Thess"),
    ("데살로니가후서", "2 Thessalonians", "2Thess"),
    ("디모데전서", "1 Timothy", "1Tim"),
    ("디모데후서", "2 Timothy", "2Tim"),
    ("디도서", "Titus", "Titus"),
    ("빌레몬서", "Philemon", "Phlm"),
    ("히브리서", "Hebrews", "Heb"),
    ("야고보서", "James", "Jas"),
    ("베드로전서", "1 Peter", "1Pet"),
    ("베드로후서", "2 Peter", "2Pet"),
    ("요한일서", "1 John", "1John"),
    ("요한이서", "2 John", "2John"),
    ("요한삼서", "3 John", "3John"),
    ("유다서", "Jude", "Jude"),
    ("요한계시록", "Revelation", "Rev"),
    ("계시록", "Revelation", "Rev"),
)


_CATHOLIC_KOREAN_REFERENCE_ABBREVIATIONS: tuple[tuple[str, str], ...] = (
    ("창", "Gen"),
    ("출", "Exod"),
    ("레", "Lev"),
    ("민", "Num"),
    ("신", "Deut"),
    ("수", "Josh"),
    ("삿", "Judg"),
    ("룻", "Ruth"),
    ("삼상", "1Sam"),
    ("삼하", "2Sam"),
    ("왕상", "1Kgs"),
    ("왕하", "2Kgs"),
    ("대상", "1Chr"),
    ("대하", "2Chr"),
    ("스", "Ezra"),
    ("느", "Neh"),
    ("에", "Esth"),
    ("욥", "Job"),
    ("시", "Ps"),
    ("잠", "Prov"),
    ("전", "Eccl"),
    ("아", "Song"),
    ("사", "Isa"),
    ("렘", "Jer"),
    ("애", "Lam"),
    ("겔", "Ezek"),
    ("단", "Dan"),
    ("호", "Hos"),
    ("욜", "Joel"),
    ("암", "Amos"),
    ("옵", "Obad"),
    ("욘", "Jonah"),
    ("미", "Mic"),
    ("나", "Nah"),
    ("합", "Hab"),
    ("습", "Zeph"),
    ("학", "Hag"),
    ("슥", "Zech"),
    ("말", "Mal"),
    ("마", "Matt"),
    ("막", "Mark"),
    ("눅", "Luke"),
    ("요", "John"),
    ("행", "Acts"),
    ("롬", "Rom"),
    ("고전", "1Cor"),
    ("고후", "2Cor"),
    ("갈", "Gal"),
    ("엡", "Eph"),
    ("빌", "Phil"),
    ("골", "Col"),
    ("살전", "1Thess"),
    ("살후", "2Thess"),
    ("딤전", "1Tim"),
    ("딤후", "2Tim"),
    ("딛", "Titus"),
    ("몬", "Phlm"),
    ("히", "Heb"),
    ("약", "Jas"),
    ("벧전", "1Pet"),
    ("벧후", "2Pet"),
    ("요일", "1John"),
    ("요이", "2John"),
    ("요삼", "3John"),
    ("유", "Jude"),
    ("계", "Rev"),
)


_CATHOLIC_TERM_ALIASES: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("광명체", "광명체들", "천체"), ("lights", "luminaries", "luminaria")),
    (("해와 달", "해와달"), ("sun", "moon")),
    (("별", "별들"), ("stars",)),
    (("넷째 날", "넷째"), ("fourth", "day")),
    (("셋째 날", "셋째"), ("third", "day")),
    (("둘째 날", "둘째"), ("second", "day")),
    (("다섯째 날", "다섯째"), ("fifth", "day")),
    (("창조", "천지창조"), ("creation", "created", "made")),
    (("은혜",), ("grace",)),
    (("성령",), ("Holy Spirit", "Spiritus Sanctus")),
    (("세례",), ("baptism", "baptismus")),
    (("성체", "성찬"), ("Eucharist", "communion")),
    (("부활",), ("resurrection",)),
)

_CATHOLIC_BIBLICAL_NAME_ALIASES: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("아담",), ("Adam",)),
    (("하와", "이브"), ("Eve", "Eva")),
    (("노아",), ("Noah", "Noe")),
    (("아브라함",), ("Abraham", "Abram")),
    (("이삭",), ("Isaac",)),
    (("야곱",), ("Jacob", "Israel")),
    (("요셉",), ("Joseph", "Ioseph")),
    (("베냐민",), ("Benjamin", "Beniamin", "Benoni")),
    (("르우벤", "루우벤"), ("Reuben", "Ruben")),
    (("레위",), ("Levi",)),
    (("유다",), ("Judah", "Judas")),
    (("모세",), ("Moses", "Moyses")),
    (("다윗",), ("David",)),
    (("솔로몬",), ("Solomon", "Salomon")),
    (("마리아",), ("Mary", "Maria")),
    (("예수",), ("Jesus", "Iesus", "Christ")),
    (("베드로",), ("Peter", "Petrus")),
    (("바울", "바오로"), ("Paul", "Paulus")),
)


def _catholic_context_alias_terms(text: str) -> list[str]:
    value = str(text or "")
    aliases: list[str] = []
    book_aliases = _catholic_bible_book_alias_terms(value)
    aliases.extend(book_aliases)
    aliases.extend(_catholic_bible_reference_aliases(value, book_aliases))
    for markers, terms in _CATHOLIC_TERM_ALIASES:
        if any(marker in value for marker in markers):
            aliases.extend(terms)
    aliases.extend(_catholic_option_alias_terms(value))
    return _unique_terms(aliases)


def _catholic_option_alias_terms(text: str) -> list[str]:
    value = str(text or "").strip()
    if not value:
        return []
    aliases = [value]
    for markers, terms in _CATHOLIC_BIBLICAL_NAME_ALIASES:
        if any(marker in value for marker in markers):
            aliases.extend(terms)
    return _unique_terms(aliases)


def _catholic_bible_reference_citations(text: str) -> list[str]:
    citations = _catholic_explicit_bible_reference_citations(text)
    citations.extend(_catholic_public_option_citations(str(text or "")))
    citations.extend(_catholic_public_stem_chapter_citations(str(text or "")))
    return _unique_terms(citations)


def _catholic_explicit_bible_reference_citations(text: str) -> list[str]:
    value = str(text or "")
    citations: list[str] = []
    alias_to_abbreviation = _catholic_book_alias_to_abbreviation()
    book_pattern = "|".join(re.escape(alias) for alias in sorted(alias_to_abbreviation, key=len, reverse=True))
    for match in re.finditer(rf"\b({book_pattern})\s+(\d{{1,3}})\s*[:：]\s*(\d{{1,3}})\b", value, re.IGNORECASE):
        book = alias_to_abbreviation.get(match.group(1).casefold())
        if book:
            citations.append(f"{book} {int(match.group(2))}:{int(match.group(3))}")
    for korean, abbreviation in _CATHOLIC_KOREAN_REFERENCE_ABBREVIATIONS:
        pattern = rf"(?<![가-힣]){re.escape(korean)}\s*(\d{{1,3}})\s*[:：]\s*(\d{{1,3}})"
        for match in re.finditer(pattern, value):
            citations.append(f"{abbreviation} {int(match.group(1))}:{int(match.group(2))}")
    for alias in _catholic_context_alias_terms(value):
        match = re.fullmatch(r"([1-3]?[A-Za-z][A-Za-z0-9]{1,7})\s+(\d{1,3}):(\d{1,3})", alias)
        if match:
            book = alias_to_abbreviation.get(match.group(1).casefold(), match.group(1))
            citations.append(f"{book} {int(match.group(2))}:{int(match.group(3))}")
    return _unique_terms(citations)


def _catholic_public_option_citations(text: str) -> list[str]:
    return _unique_terms(
        [
            *_catholic_public_option_verse_citations(text),
            *_catholic_public_option_chapter_citations(text),
        ]
    )


def _catholic_public_option_verse_citations(text: str) -> list[str]:
    parsed = _parse_generic_multiple_choice(text)
    if parsed is None:
        return []
    books = _catholic_full_book_abbreviations(parsed.stem)
    if not books:
        return []
    citations: list[str] = []
    for option in parsed.options:
        for match in re.finditer(r"(?<!\d)(\d{1,3})\s*[:：]\s*(\d{1,3})(?:\s*[-~]\s*\d{1,3})?(?!\d)", option.text):
            citations.append(f"{books[0]} {int(match.group(1))}:{int(match.group(2))}")
    return _unique_terms(citations)


def _catholic_public_option_chapter_citations(text: str) -> list[str]:
    parsed = _parse_generic_multiple_choice(text)
    if parsed is None:
        return []
    books = _catholic_full_book_abbreviations(parsed.stem)
    if not books:
        return []
    citations: list[str] = []
    for option in parsed.options:
        for match in re.finditer(r"(?<!\d)(\d{1,3})\s*(?:장|편)(?!\d)", option.text):
            citations.append(f"{books[0]} {int(match.group(1))}:1")
    return _unique_terms(citations)


def _catholic_public_chapter_citations(text: str) -> list[str]:
    return _unique_terms(
        [
            *_catholic_public_option_chapter_citations(text),
            *_catholic_public_stem_chapter_citations(text),
        ]
    )


def _catholic_public_stem_chapter_citations(text: str) -> list[str]:
    parsed = _parse_generic_multiple_choice(text)
    if parsed is None:
        return []
    books = _catholic_full_book_abbreviations(parsed.stem)
    if not books:
        return []
    citations: list[str] = []
    for match in re.finditer(r"(?<!\d)(\d{1,3})\s*(?:장|편)(?!\d)", parsed.stem):
        citations.append(f"{books[0]} {int(match.group(1))}:1")
    return _unique_terms(citations)


def _catholic_public_stem_anchor_terms(text: str) -> list[str]:
    parsed = _parse_generic_multiple_choice(text)
    if parsed is None:
        return []
    raw_terms = re.findall(r"[\w가-힣]{2,}", parsed.stem, flags=re.UNICODE)
    stop = {
        "다음",
        "본문",
        "말씀",
        "라는",
        "표현",
        "표현이",
        "나오는가",
        "나오는",
        "어디",
        "어느",
        "몇",
        "기록되어",
        "있는가",
        "출애굽기",
        "신명기",
        "시편",
    }
    terms = [term for term in raw_terms if term not in stop and len(term) >= 2]
    return _unique_terms(terms)[:24]


def _catholic_public_mcq_entity_queries(text: str) -> list[str]:
    parsed = _parse_generic_multiple_choice(text)
    if parsed is None or not re.search(r"[가-힣]", str(text or "")):
        return []
    option_terms = [_catholic_trim_korean_particle(option.text) for option in parsed.options]
    option_terms = [term for term in option_terms if len(term) >= 1]
    stem_terms = _catholic_public_stem_entity_terms(parsed.stem)
    compact_stem_terms = _catholic_public_compact_stem_entity_terms(parsed.stem)
    queries: list[str] = []

    def add(terms: list[str]) -> None:
        query = " ".join(_unique_terms([term for term in terms if term])[:16])
        if query:
            queries.append(query)

    if compact_stem_terms:
        add([*option_terms, *compact_stem_terms])
        if _looks_like_negative_mcq_stem(parsed.stem) and 3 <= len(option_terms) <= 6:
            for drop_index in range(len(option_terms)):
                add([term for index, term in enumerate(option_terms) if index != drop_index] + compact_stem_terms)
    add([*option_terms, *stem_terms])
    if _looks_like_negative_mcq_stem(parsed.stem) and 3 <= len(option_terms) <= 6:
        for drop_index in range(len(option_terms)):
            add([term for index, term in enumerate(option_terms) if index != drop_index] + stem_terms)
    return _unique_terms(queries)


def _catholic_public_stem_entity_terms(stem: str) -> list[str]:
    stop = {
        "다음",
        "본문",
        "말씀",
        "라는",
        "표현",
        "표현이",
        "나오는가",
        "나오는",
        "어디",
        "어느",
        "몇",
        "기록되어",
        "있는가",
        "들어가지",
        "않는",
        "말은",
    }
    raw = [
        _catholic_trim_korean_particle(term)
        for term in re.findall(r"[\w가-힣]{2,}", str(stem or ""), flags=re.UNICODE)
        if term not in stop
    ]
    counts: dict[str, int] = {}
    first_index: dict[str, int] = {}
    for index, term in enumerate(raw):
        if len(term) < 2:
            continue
        counts[term] = counts.get(term, 0) + 1
        first_index.setdefault(term, index)
    candidates = [
        term
        for term, count in counts.items()
        if count >= 2 or len(term) >= 5
    ]
    candidates.sort(key=lambda term: (-counts[term], -len(term), first_index[term]))
    return candidates[:6]


def _catholic_public_compact_stem_entity_terms(stem: str) -> list[str]:
    terms = _catholic_public_stem_entity_terms(stem)
    compact = [
        term
        for term in terms
        if not _catholic_looks_like_korean_predicate_token(term)
        and not _catholic_low_signal_stem_entity_token(term)
    ]
    return compact[:3]


def _catholic_low_signal_stem_entity_token(term: str) -> bool:
    return str(term or "").strip() in {
        "괄호",
        "기술",
        "마음",
        "본문",
        "사람",
        "이스라엘",
        "지파",
        "하나님",
    }


def _catholic_looks_like_korean_predicate_token(term: str) -> bool:
    value = str(term or "").strip()
    return bool(
        re.search(
            r"(?:시며|시매|으며|으매|면서|느니라|니라|하라|하니|하매|하여|하고|하는|된다|되며|되어)$",
            value,
        )
    )


def _looks_like_negative_mcq_stem(stem: str) -> bool:
    value = str(stem or "")
    return bool(re.search(r"(?:들어가지\s*않|아닌|않는|not\s+included|except)", value, re.IGNORECASE))


def _catholic_trim_korean_particle(term: str) -> str:
    value = str(term or "").strip()
    for suffix in ("으로", "에서", "에게", "까지", "부터", "에는", "의", "은", "는", "이", "가", "을", "를", "과", "와", "에"):
        if len(value) > len(suffix) + 1 and value.endswith(suffix):
            return value[: -len(suffix)]
    return value


def _catholic_full_book_abbreviations(text: str) -> list[str]:
    value = str(text or "")
    compact_value = re.sub(r"\s+", "", value)
    abbreviations: list[str] = []
    for korean, _english, abbreviation in _CATHOLIC_BIBLE_BOOK_ALIASES:
        if korean in value or korean in compact_value:
            abbreviations.append(abbreviation)
    return _unique_terms(abbreviations)


def _catholic_bible_reference_parts(citation: str) -> tuple[str, int, int] | None:
    match = re.fullmatch(r"([1-3]?[A-Za-z][A-Za-z0-9]{1,7})\s+(\d{1,3}):(\d{1,3})", str(citation or "").strip())
    if not match:
        return None
    return match.group(1), int(match.group(2)), int(match.group(3))


def _catholic_row_citation(row: Any) -> str:
    citation = str(getattr(row, "citation", "") or "")
    if citation:
        return citation
    try:
        return str(row["case_number"] or "")
    except Exception:
        return ""


def _catholic_row_same_book_chapter(row: Any, book: str, chapter: int) -> bool:
    parts = _catholic_bible_reference_parts(_catholic_row_citation(row))
    return parts is not None and parts[0] == book and parts[1] == chapter


def _catholic_row_source_role_text(row: Any) -> str:
    values = [
        getattr(row, "source_kind", ""),
        getattr(row, "case_type", ""),
        getattr(row, "source_dataset", ""),
        getattr(row, "title", ""),
    ]
    for key in ("source_kind", "case_type", "source_dataset", "title"):
        try:
            values.append(row[key])
        except Exception:
            pass
    return " ".join(str(value or "") for value in values).casefold()


def _catholic_row_search_text(row: Any) -> str:
    values = [
        getattr(row, "title", ""),
        getattr(row, "citation", ""),
        getattr(row, "case_name", ""),
        getattr(row, "case_type", ""),
        getattr(row, "source_kind", ""),
        getattr(row, "full_text", ""),
    ]
    for key in ("title", "case_number", "case_name", "case_type", "source_kind", "full_text"):
        try:
            values.append(row[key])
        except Exception:
            pass
    return " ".join(str(value or "") for value in values).casefold()


def _catholic_row_has_any_term(row: Any, terms: list[str]) -> bool:
    haystack = _catholic_row_search_text(row)
    return any(str(term or "").casefold() in haystack for term in terms if len(str(term or "").strip()) >= 2)


def _catholic_row_stem_anchor_match_count(row: Any, terms: list[str]) -> int:
    haystack = _catholic_row_search_text(row)
    count = 0
    for term in terms:
        value = str(term or "").casefold().strip()
        if len(value) >= 2 and value in haystack:
            count += 1
    return count


def _catholic_korean_mcq_scripture_priority_rows(query: str, rows: list[Any]) -> tuple[list[Any], list[Any]]:
    if _parse_generic_multiple_choice(query) is None or not re.search(r"[가-힣]", str(query or "")):
        return [], rows
    adapter_terms = CatholicDomainAdapter().multiple_choice_option_terms(query)
    terms = _unique_terms([*_catholic_public_stem_anchor_terms(query), *adapter_terms])
    priority_entries: list[tuple[int, int, Any]] = []
    ordinary: list[Any] = []
    for index, row in enumerate(rows):
        score = _catholic_row_stem_anchor_match_count(row, terms)
        if score >= 2 and _catholic_row_is_korean_scripture(row):
            priority_entries.append((score, index, row))
        else:
            ordinary.append(row)
    priority_entries.sort(key=lambda item: (-item[0], item[1]))
    return [row for _score, _index, row in priority_entries], ordinary


def _catholic_row_is_korean_scripture(row: Any) -> bool:
    canonical_id = str(getattr(row, "canonical_id", "") or "")
    try:
        canonical_id = canonical_id or str(row["canonical_id"] or "")
    except Exception:
        pass
    role = _catholic_row_source_role_text(row)
    text = _catholic_row_search_text(row)
    return "scripture" in role and (
        ".kor." in canonical_id
        or "korean revised" in text
        or "primary text — ko" in text
        or "primary text - ko" in text
    )


def _catholic_bible_chapter_context_rows(
    conn: sqlite3.Connection,
    book: str,
    chapter: int,
    verse: int,
    *,
    limit: int,
    option_terms: list[str] | None = None,
    anchor_terms: list[str] | None = None,
) -> list[tuple[sqlite3.Row, float]]:
    try:
        found = conn.execute(
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
            WHERE case_number LIKE ?
            LIMIT 240
            """,
            (f"{book} {chapter}:%",),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    option_needles = [term.casefold() for term in _unique_terms(option_terms or []) if len(str(term).strip()) >= 2]
    anchor_needles = _unique_terms(anchor_terms or [])
    scored: list[tuple[float, int, str, sqlite3.Row, float]] = []
    for row in found:
        parts = _catholic_bible_reference_parts(str(row["case_number"] or ""))
        if parts is None:
            continue
        _row_book, _row_chapter, row_verse = parts
        distance = abs(row_verse - verse)
        if distance == 0:
            continue
        text = " ".join(str(row[field] or "") for field in ("title", "case_name", "full_text") if field in row.keys()).casefold()
        option_hit = bool(option_needles and any(needle in text for needle in option_needles))
        anchor_count = _catholic_row_stem_anchor_match_count(row, anchor_needles)
        if distance > 24 and not option_hit and anchor_count < 2:
            continue
        score = max(700.0, 1060.0 - float(distance * 8))
        if option_hit:
            score = max(score, 1140.0 - float(min(distance, 60) * 3))
        if anchor_count:
            score = max(score, 1120.0 + float(min(anchor_count, 8) * 18) - float(min(distance, 60) * 2))
        scored.append((-score, distance, str(row["canonical_id"] or ""), row, score))
    scored.sort(key=lambda item: (item[0], item[1], item[2]))
    return [(row, score) for _rank, _distance, _canonical_id, row, score in scored[: max(0, int(limit))]]


def _catholic_book_alias_to_abbreviation() -> dict[str, str]:
    aliases: dict[str, str] = {}
    for _korean, english, abbreviation in _CATHOLIC_BIBLE_BOOK_ALIASES:
        aliases[english.casefold()] = abbreviation
        aliases[abbreviation.casefold()] = abbreviation
    return aliases


def _catholic_bible_book_alias_terms(text: str) -> list[str]:
    compact_text = re.sub(r"\s+", "", str(text or ""))
    aliases: list[str] = []
    for korean, english, abbreviation in _CATHOLIC_BIBLE_BOOK_ALIASES:
        if korean in text or korean in compact_text:
            aliases.extend([english, abbreviation])
    return _unique_terms(aliases)


def _catholic_bible_reference_aliases(text: str, book_aliases: list[str]) -> list[str]:
    if not book_aliases:
        return []
    match = re.search(r"(\d{1,3})\s*장(?:\s*(\d{1,3})\s*절)?", str(text or ""))
    if not match:
        return []
    chapter = match.group(1)
    verse = match.group(2) or ""
    aliases: list[str] = []
    for alias in book_aliases[:4]:
        if verse:
            aliases.append(f"{alias} {chapter}:{verse}")
        aliases.append(f"{alias} {chapter}")
    return _unique_terms(aliases)


_GENERIC_CIRCLED_OPTION_MARKERS = {
    "①": "1",
    "②": "2",
    "③": "3",
    "④": "4",
    "⑤": "5",
    "⑥": "6",
    "⑦": "7",
    "⑧": "8",
    "⑨": "9",
    "⑩": "10",
}


def _parse_generic_multiple_choice(text: str) -> MultipleChoiceQuestion | None:
    lines = [line.rstrip() for line in str(text or "").splitlines()]
    option_lines: list[tuple[int, str, str]] = []
    for index, line in enumerate(lines):
        marker, option_text = _generic_option_line(line)
        if marker and option_text:
            option_lines.append((index, marker, option_text))
    leading_question_stem = ""
    if option_lines and option_lines[0][0] == 0 and len(option_lines) >= 3:
        candidate_stem = option_lines[0][2].strip()
        if _looks_like_generic_question_stem(candidate_stem):
            leading_question_stem = candidate_stem
            option_lines = option_lines[1:]
    if len(option_lines) < 2:
        return None
    first_option_index = option_lines[0][0]
    stem_source = lines[:first_option_index] if not leading_question_stem else [leading_question_stem] + lines[1:first_option_index]
    stem_lines = [
        _strip_generic_mcq_instruction(line).strip()
        for line in stem_source
        if _strip_generic_mcq_instruction(line).strip()
    ]
    if not stem_lines:
        return None
    options: list[MultipleChoiceOption] = []
    for ordinal, (_index, marker, option_text) in enumerate(option_lines, start=1):
        options.append(MultipleChoiceOption(number=ordinal, text=option_text.strip(), marker=marker))
    return MultipleChoiceQuestion(stem=_clean_generic_mcq_stem("\n".join(stem_lines)), options=tuple(options))


def _generic_option_line(line: str) -> tuple[str, str]:
    stripped = str(line or "").strip()
    if not stripped:
        return "", ""
    match = re.match(r"^[([]?([A-Ea-e])[)\].、:：]\s+(.+?)\s*$", stripped)
    if match:
        return match.group(1).upper(), match.group(2).strip()
    match = re.match(r"^[([]?([1-9]\d?)[)\].、:：]\s+(.+?)\s*$", stripped)
    if match:
        return str(int(match.group(1))), match.group(2).strip()
    marker = stripped[:1]
    if marker in _GENERIC_CIRCLED_OPTION_MARKERS and stripped[1:].strip():
        return _GENERIC_CIRCLED_OPTION_MARKERS[marker], stripped[1:].strip()
    return "", ""


def _looks_like_generic_question_stem(text: str) -> bool:
    value = str(text or "").strip()
    if not value:
        return False
    if "?" in value or "？" in value:
        return True
    return bool(
        re.search(
            r"(?:다음\s*중|옳은|맞는|아닌|무엇|어느|몇|누구|which|what|when|where|who|how)",
            value,
            re.IGNORECASE,
        )
    )


def _strip_generic_mcq_instruction(line: str) -> str:
    value = str(line or "").strip()
    lowered = value.lower()
    if "answer:" in lowered or "정답:" in value or "정답 :" in value:
        return ""
    if "option id" in lowered or "보기id" in value.lower():
        return ""
    if "choose exactly one" in lowered or "객관식 문제" in value:
        return ""
    return value


def _clean_generic_mcq_stem(stem: str) -> str:
    value = str(stem or "").strip()
    return re.sub(r"^\s*\d{1,4}\s*[.)]\s*", "", value).strip()


def _row_role_text(row: Any) -> tuple[str, str, str, str, str, str]:
    source_kind = str(getattr(row, "source_kind", "") or getattr(row, "case_type", "") or "").lower()
    dataset = str(getattr(row, "source_dataset", "") or "").lower()
    title = str(getattr(row, "title", "") or "").lower()
    school = str(getattr(row, "school", "") or "").lower()
    tradition = str(getattr(row, "tradition", "") or "").lower()
    text = " ".join([source_kind, dataset, title, school, tradition])
    return source_kind, dataset, title, school, tradition, text


def _role_diversity_rule(examples: str) -> str:
    return (
        "- Preserve source_kind diversity when multiple directly relevant evidence families are present; "
        f"compare {examples} before filling remaining slots.\n"
    )


def _language_guard(language: str) -> str:
    return {
        "ko": "Use Korean headings and Korean explanatory prose. Do not output English boilerplate headings such as GEMMA4 CITED ANSWER, PRIMARY TEXT SOURCE, or CROSS-CHECK SOURCE. ",
        "ar": "Use Arabic headings and Arabic explanatory prose. Do not output English boilerplate headings such as GEMMA4 CITED ANSWER, PRIMARY TEXT SOURCE, or CROSS-CHECK SOURCE. ",
    }.get(language, "")


def _simli_contextualized_source_role_keyword(question: str, keyword: str) -> str:
    lowered = keyword.lower()
    role_like = any(
        term in lowered
        for term in (
            "dsm",
            "dsm-5",
            "guideline",
            "clinical guideline",
            "icd",
            "icd-11",
        )
    ) or any(term in keyword for term in ("가이드라인", "임상 가이드라인", "지침"))
    if not role_like:
        return ""
    focus_terms: list[str] = []

    def add(term: str) -> None:
        normalized = str(term or "").strip()
        if normalized and normalized not in focus_terms:
            focus_terms.append(normalized)

    question_text = str(question or "")
    question_lower = question_text.lower()
    if "adhd" in question_lower or "주의력" in question_text or "집중" in question_text:
        add("ADHD")
    if "불안" in question_text or "anxiety" in question_lower:
        add("anxiety")
    if "공황" in question_text or "panic" in question_lower:
        add("panic")
    if "우울" in question_text or "depression" in question_lower:
        add("depression")
    if not focus_terms:
        return ""
    return " ".join([*focus_terms[:3], keyword])


def _simli_sanitized_generated_keyword(keyword: str, *, question: str = "") -> str | None:
    lowered = str(keyword or "").strip().lower()
    if not lowered:
        return None
    canonical = ""
    if "adhd" in lowered or "attention deficit" in lowered or "주의력 결핍" in keyword:
        canonical = "ADHD"
    elif "generalized anxiety" in lowered or "anxiety disorder" in lowered or "범불안" in keyword or "불안장애" in keyword:
        canonical = "anxiety"
    elif "panic disorder" in lowered or "공황" in keyword:
        canonical = "panic"
    elif "major depressive" in lowered or "depressive disorder" in lowered or "우울" in keyword:
        canonical = "depression"
    if not canonical:
        return None
    if _simli_question_already_contains_focus(question, canonical):
        return ""
    return canonical


def _simli_question_already_contains_focus(question: str, canonical: str) -> bool:
    text = str(question or "")
    lowered = text.lower()
    if canonical == "ADHD":
        return "adhd" in lowered or "주의력" in text or "집중" in text
    if canonical == "anxiety":
        return "anxiety" in lowered or "불안" in text or "범불안" in text
    if canonical == "panic":
        return "panic" in lowered or "공황" in text
    if canonical == "depression":
        return "depression" in lowered or "우울" in text
    return False


def _contains_cjk_or_hangul(text: str) -> bool:
    return any(
        "\u3400" <= ch <= "\u9fff"
        or "\uf900" <= ch <= "\ufaff"
        or "\uac00" <= ch <= "\ud7a3"
        for ch in str(text or "")
    )


_ARABIC_MARKS_RE = re.compile(r"[\u064b-\u065f\u0670\u06d6-\u06ed]")


def _normalize_arabic_for_match(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(text or "").lower())
    normalized = _ARABIC_MARKS_RE.sub("", normalized)
    return (
        normalized.replace("ٱ", "ا")
        .replace("أ", "ا")
        .replace("إ", "ا")
        .replace("آ", "ا")
        .replace("ى", "ي")
        .replace("ؤ", "و")
        .replace("ئ", "ي")
    )


def _compact_text(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "")).lower()


def _env_flag_default(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def _fallback_record_text(record: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in (
        "title",
        "citation",
        "caseName",
        "caseType",
        "sourceKind",
        "excerpt",
        "text",
        "fullText",
        "content",
        "document_title",
        "relative_path",
        "absolute_path",
        "doc_type",
        "source_group",
        "anchor_text",
        "extracted_text",
        "case_number",
        "court",
        "decision_date",
        "case_name",
    ):
        parts.append(str(record.get(key) or ""))
    metadata = record.get("metadata")
    if isinstance(metadata, dict):
        for key in (
            "citation",
            "title",
            "tradition",
            "school",
            "sourceKind",
            "authorityLevel",
            "authorityLabel",
            "language",
            "dataset",
            "url",
        ):
            parts.append(str(metadata.get(key) or ""))
    boundaries = record.get("candidate_boundaries")
    if isinstance(boundaries, list):
        for boundary in boundaries[:12]:
            parts.append(_fallback_nested_text(boundary))
    return "\n".join(part for part in parts if part)[:24000]


def _fallback_claim_card_text(card: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in (
        "claimSummary",
        "contextSummary",
        "quote",
        "sourceTitle",
        "sourceLabel",
        "sourceId",
        "citation",
        "role",
        "claimAxis",
        "stance",
        "school",
        "tradition",
        "sourceKind",
    ):
        parts.append(str(card.get(key) or ""))
    span = card.get("span")
    if isinstance(span, dict):
        parts.append(str(span.get("exact") or ""))
    return "\n".join(part for part in parts if part)[:12000]


def _fallback_nested_text(value: Any) -> str:
    if isinstance(value, dict):
        return "\n".join(_fallback_nested_text(item) for item in value.values())
    if isinstance(value, list):
        return "\n".join(_fallback_nested_text(item) for item in value[:20])
    return str(value or "")


def _gateway_tcm_exam_question_text(query: str) -> str:
    raw = re.split(r"\n\s*위 한의사 국가시험 객관식 문제", str(query or ""), maxsplit=1)[0].strip()
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    if not lines:
        return ""
    stem: list[str] = []
    choices: list[list[str]] = []
    current_choice: list[str] | None = None
    for index, line in enumerate(lines):
        if index == 0:
            stem.append(re.sub(r"^\s*\d{1,3}\s*[.．]\s*", "", line).strip())
            continue
        marker_match = _GATEWAY_EXAM_CHOICE_RE.match(line)
        if marker_match:
            if current_choice is not None:
                choices.append(current_choice)
            current_choice = [line[marker_match.end():].strip()]
            continue
        if current_choice is None:
            stem.append(line)
        else:
            current_choice.append(line)
    if current_choice is not None:
        choices.append(current_choice)

    safe_stem = _gateway_sanitize_exam_text(" ".join(stem))
    safe_choices = [_gateway_sanitize_exam_text(" ".join(choice)) for choice in choices[:5]]
    safe_choices = [choice for choice in safe_choices if choice]
    if len(safe_choices) >= 2:
        choice_block = " ".join(f"{index} {choice}" for index, choice in enumerate(safe_choices, start=1))
        return f"{safe_stem} 선택지: {choice_block}".strip()
    return _gateway_sanitize_exam_text(raw)


_GATEWAY_EXAM_CHOICE_RE = re.compile(
    r"^\s*(?:[①②③④⑤]|[@®©]|(?:0[0-9]?|[0OQDQ]|[1-5]|69)[)\].:：ㆍ]?)\s*"
)


def _gateway_sanitize_exam_text(text: str) -> str:
    value = unicodedata.normalize("NFKC", str(text or ""))
    value = re.sub(r"\b[A-Za-z]{1,}\b", " ", value)
    value = re.sub(r"[^\d가-힣一-龥\s.,?~:/()%-]", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()
