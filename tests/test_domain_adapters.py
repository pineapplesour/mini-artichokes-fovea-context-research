from types import SimpleNamespace

from shared_platform import beta6 as beta6_module
from shared_platform.domain_adapters import get_domain_adapter
from shared_platform.products import PRODUCT_PROFILES
from shared_platform.search import SearchResult


def test_default_domain_adapter_is_noop_for_unknown_product():
    adapter = get_domain_adapter("unknown")

    assert adapter.parse_multiple_choice("plain question") is None
    assert adapter.multiple_choice_option_terms("1) a 2) b") == []
    assert adapter.search_text("keep this") == "keep this"
    assert adapter.deterministic_writer_fallback_answer(
        "question",
        [],
        [],
        language="en",
        error="timeout",
    ) is None


def test_default_domain_adapter_strips_generic_mcq_options_from_search_text():
    adapter = get_domain_adapter("unknown")
    query = """006. Which structure best describes the contract?

A. Murabaha deposit role
B. Customer confidentiality
C. Commercial risk
D. Corporate governance

Choose exactly one option ID.
Answer: <option ID>"""

    parsed = adapter.parse_multiple_choice(query)

    assert parsed is not None
    assert parsed.stem == "Which structure best describes the contract?"
    assert [option.number for option in parsed.options] == [1, 2, 3, 4]
    assert [option.marker for option in parsed.options] == ["A", "B", "C", "D"]
    assert adapter.search_text(query) == "Which structure best describes the contract?"
    assert adapter.multiple_choice_option_terms("1) a 2) b") == []


def test_default_domain_adapter_treats_numbered_circled_mcq_stem_as_question():
    adapter = get_domain_adapter("unknown")
    query = """1. 창세기 1장의 천지창조 일정 가운데 광명체들은 몇째 날 창조되었는가?

① 둘째 날
② 셋째 날
③ 넷째 날
④ 다섯째 날

위 객관식 문제의 정답 보기ID 하나만 고르세요.
보기ID 후보: 1, 2, 3, 4
답변 첫 줄은 반드시 `정답: <보기ID>` 형식으로 시작하세요."""

    parsed = adapter.parse_multiple_choice(query)

    assert parsed is not None
    assert parsed.stem == "창세기 1장의 천지창조 일정 가운데 광명체들은 몇째 날 창조되었는가?"
    assert [option.number for option in parsed.options] == [1, 2, 3, 4]
    assert [option.marker for option in parsed.options] == ["1", "2", "3", "4"]
    assert [option.text for option in parsed.options] == ["둘째 날", "셋째 날", "넷째 날", "다섯째 날"]
    assert adapter.search_text(query) == "창세기 1장의 천지창조 일정 가운데 광명체들은 몇째 날 창조되었는가?"


def test_default_domain_adapter_generic_mcq_prompt_block_maps_option_ids():
    adapter = get_domain_adapter("unknown")
    query = """4. 다음 본문은 출애굽기 어디에 기록되어 있는가?

① 13:1-2
② 14:31
③ 15:21
④ 40:35"""

    block = adapter.multiple_choice_prompt_block(query)

    assert "정답: <보기ID>" in block
    assert "보기ID 1: 13:1-2" in block
    assert "보기ID 2: 14:31" in block
    assert "보기ID 3: 15:21" in block
    assert "보기ID는 citation label이나 source label이 아닙니다" in block


def test_domain_adapters_own_role_taxonomy_and_selector_policy():
    islam = get_domain_adapter("islam")
    catholic = get_domain_adapter("catholic")
    tcm = get_domain_adapter("tcm")
    simli = get_domain_adapter("simli")

    assert islam.role_order()[:3] == ["scripture", "hadith", "tafsir"]
    assert islam.source_role(SimpleNamespace(source_kind="scripture_window", source_dataset="quran", title="", school="", tradition="")) == "scripture"
    assert "fatwa" in islam.selector_policy()

    assert catholic.source_role(SimpleNamespace(source_kind="scripture_window", source_dataset="", title="", school="", tradition="")) == "scripture"
    assert "Bible" in catholic.keyword_generation_spec()[0]

    assert tcm.role_order()[:3] == ["classic", "materia", "formulary"]
    assert tcm.source_role(SimpleNamespace(source_kind="materia_medica", source_dataset="", title="本草", school="", tradition="")) == "materia"
    assert "TCM safety" in tcm.selector_policy()

    assert simli.role_order()[:3] == ["diagnostic", "guideline", "research"]
    assert simli.source_role(SimpleNamespace(source_kind="guideline_chunk", source_dataset="", title="", school="", tradition="")) == "guideline"
    assert "Mental-health safety" in simli.selector_policy()


def test_domain_adapters_own_prompt_policy_and_runtime_config_defaults():
    islam = get_domain_adapter("islam")
    tcm = get_domain_adapter("tcm")
    simli = get_domain_adapter("simli")

    islam_task, islam_examples = islam.keyword_generation_spec()
    assert "Islamic source database" in islam_task
    assert "ولي" in islam_examples
    assert "binding ruling" in islam.claim_analyzer_policy()
    assert "binding fatwa" in islam.writer_domain_policy()
    assert islam.default_answer_outline("ko") == ["원문 근거 층위", "학파/종파별 입장", "한계와 검색 공백"]
    assert islam.selector_compact_candidate_lines_config().default is True
    assert islam.claim_analyzer_batch_workers_config(maximum=7).default == 5

    tcm_task, tcm_examples = tcm.keyword_generation_spec()
    assert "Korean/Chinese medicine" in tcm_task
    assert "甘草" in tcm_examples
    assert "Do not diagnose or prescribe" in tcm.writer_return_instruction("ko")
    assert tcm.selector_excerpt_bytes_config().env_names[0] == "RELIGION_TCM_SELECTOR_EXCERPT_BYTES"
    assert tcm.default_answer_outline("ko")[0] == "고전/본초 근거"

    assert "mental-health evidence" in simli.keyword_generation_spec()[0]
    assert simli.source_usage_hint({"metadata": {"sourceKind": "dsm5_chunk"}}) == "SYMPTOM_CATEGORY_NOT_DIAGNOSIS"
    assert simli.source_usage_hint({"document_title": "CBT exposure therapy", "metadata": {}}) == "CBT_EXPLANATION"
    assert simli.selector_timeout_config(chat_timeout=300.0).default == 45.0
    assert simli.selector_rate_limit_retries_config().default == 3
    assert "user-specific diagnosis" in simli.answer_planner_policy()


def test_domain_adapters_own_beta6_search_heuristics():
    islam = get_domain_adapter("islam")
    catholic = get_domain_adapter("catholic")
    tcm = get_domain_adapter("tcm")
    simli = get_domain_adapter("simli")

    assert islam.searchable_keyword("five daily prayers") == "prayers"
    assert islam.searchable_keyword("Islamic ruling perspective") == ""
    assert "fund commingling" in islam.option_aliases("자금 혼합")
    islam_buckets = islam.domain_bucket_queries(
        """제한된 투자 계좌 보유자에게 제공되는 것과 동일한 수준의 정보를 무제한 투자 계좌 보유자에게 제공하는 것은 주로 다음 문제로 인해 어렵습니다.

A. 자금 혼합
B. 고객의 기밀 유지
C. 상업적 위험
D. 기업 지배구조""",
        [],
    )
    assert any("restricted investment account" in query for query in islam_buckets)
    assert any("fund commingling" in query for query in islam_buckets)
    assert islam.candidate_role_floor_required() == 2

    assert "Gen 1:14" in catholic.searchable_keyword("창세기 1장 14절")
    assert "luminaria" in catholic.searchable_keyword("광명체")
    catholic_buckets = catholic.domain_bucket_queries(
        "창세기 1장의 천지창조 일정 가운데 광명체들은 몇째 날 창조되었는가?",
        ["창세기 1장 14절", "광명체", "넷째 날"],
    )
    assert any("Genesis" in query and "luminaria" in query for query in catholic_buckets)

    assert simli.searchable_keyword(
        "DSM-5",
        question="ADHD와 불안장애가 헷갈릴 때 DSM과 가이드라인 관점으로 정리해줘",
    ) == "ADHD anxiety DSM-5"
    assert simli.searchable_keyword(
        "Generalized Anxiety Disorder",
        question="성인 ADHD와 범불안장애가 헷갈릴 때 정리해줘",
    ) == ""
    assert simli.frontier_target_config(top_k=100).default == 400
    assert simli.frontier_stop_floor_config(top_k=100).default == 300
    assert simli.search_plan_query_limit_config(requested=700, max_query_limit=700).env_names == (
        "RELIGION_SIMLI_BETA6_PER_QUERY_LIMIT",
    )

    assert tcm.full_frontier_refine_limit_config(requested=700).env_names == (
        "RELIGION_TCM_BETA6_FULL_FRONTIER_REFINE_LIMIT",
    )
    assert tcm.candidate_role_floor_required() == 2


def test_catholic_exact_citation_mcq_prefers_same_chapter_option_context_over_remote_name_match():
    catholic = get_domain_adapter("catholic")
    query = "창 42:21에서 아우는 누구인가?\n\n① 레위\n② 베냐민\n③ 르우벤\n④ 요셉"

    exact = SearchResult(
        canonical_id="gen-42-21",
        title="Genesis",
        citation="Gen 42:21",
        authority_body="",
        source_date="",
        case_name="",
        case_type="scripture_window",
        full_text="we have sinned against our brother",
        source_kind="scripture",
    )
    nearby_common_noun = SearchResult(
        canonical_id="gen-42-20",
        title="Genesis",
        citation="Gen 42:20",
        authority_body="",
        source_date="",
        case_name="",
        case_type="scripture_window",
        full_text="Bring your youngest brother to me.",
        source_kind="scripture",
    )
    same_chapter_joseph = SearchResult(
        canonical_id="gen-42-6",
        title="Genesis",
        citation="Gen 42:6",
        authority_body="",
        source_date="",
        case_name="",
        case_type="scripture_window",
        full_text="Joseph was governor and his brothers bowed before him.",
        source_kind="scripture",
    )
    remote_benjamin = SearchResult(
        canonical_id="gen-45-14",
        title="Genesis",
        citation="Gen 45:14",
        authority_body="",
        source_date="",
        case_name="",
        case_type="scripture_window",
        full_text="Joseph embraced Benjamin his brother.",
        source_kind="scripture",
    )

    selected = catholic.postprocess_selected_rows(
        query,
        [exact, nearby_common_noun, same_chapter_joseph, remote_benjamin],
        [exact, nearby_common_noun, remote_benjamin],
        limit=3,
    )

    assert [row.canonical_id for row in selected] == ["gen-42-21", "gen-42-6", "gen-42-20"]


def test_catholic_negative_korean_mcq_prioritizes_compact_entity_domain_buckets(monkeypatch):
    monkeypatch.delenv("RELIGION_CATHOLIC_BETA6_CANDIDATE_SCAN_MULTIPLIER", raising=False)
    profile = PRODUCT_PROFILES["catholic"]
    query = """21. 다음은 어느 지파에 대한 기술인가? "그러므로 이스라엘 하나님이 앗수르 왕 불의 마음을 일으키시며 앗수르 왕 디글랏빌레셀의 마음을 일으키시매 곧 ( )과 ( )과 ( ) 지파를 사로잡아 할라와 하볼과 하라와 고산 강가에 옮긴지라 그들이 오늘까지 거기에 있으니라"의 괄호에 들어가지 않는 말은?

① 르우벤
② 시므온
③ 갓
④ 므낫세 반"""

    plan = beta6_module.build_beta6_candidate_search_plan(
        profile,
        query,
        ["앗수르", "디글랏빌레셀", "르우벤", "갓", "므낫세"],
        target_limit=30,
        per_keyword_limit=30,
    )

    assert [label for label, _search_query, _limit in plan[:5]] == [
        "domain_bucket_01",
        "domain_bucket_02",
        "domain_bucket_03",
        "domain_bucket_04",
        "domain_bucket_05",
    ]
    first_queries = [search_query for _label, search_query, _limit in plan[:5]]
    assert "르우벤 갓 므낫세 반 앗수르 디글랏빌레셀" in first_queries
    assert all("마음" not in search_query and "지파" not in search_query for search_query in first_queries)
    assert beta6_module._beta6_candidate_scan_multiplier(profile, query, label="domain_bucket_03") == 12
    assert beta6_module._beta6_candidate_scan_multiplier(profile, "plain search", label="domain_bucket_03") == 1


def test_domain_adapters_own_answer_plan_relevance_rules():
    default = get_domain_adapter("unknown")
    islam = get_domain_adapter("islam")
    tcm = get_domain_adapter("tcm")

    assert default.answer_plan_term_too_short("감초") is True
    assert tcm.answer_plan_term_too_short("감초") is False
    assert "本草" in tcm.answer_plan_relevance_stopwords()
    assert "甘草酸" in tcm.answer_plan_relevance_aliases(["감초", "임신"])
    assert "孕婦" in tcm.answer_plan_relevance_aliases(["감초", "임신"])

    assert "أصول" in islam.answer_plan_relevance_stopwords()
    islam_aliases = islam.answer_plan_relevance_aliases(["الربا والاشتراكية", "الملكية"])
    assert "riba" in islam_aliases
    assert "socialism" in islam_aliases
    assert "ownership" in islam_aliases


def test_beta6_runtime_config_wrappers_read_domain_adapter_defaults(monkeypatch):
    for name in (
        "RELIGION_CHAT_TIMEOUT_SECONDS",
        "RELIGION_SELECTOR_TIMEOUT_SECONDS",
        "RELIGION_SIMLI_SELECTOR_TIMEOUT_SECONDS",
        "RELIGION_SELECTOR_RATE_LIMIT_RETRIES",
        "RELIGION_SIMLI_SELECTOR_RATE_LIMIT_RETRIES",
        "RELIGION_SELECTOR_RATE_LIMIT_BACKOFF_SECONDS",
        "RELIGION_SIMLI_SELECTOR_RATE_LIMIT_BACKOFF_SECONDS",
        "RELIGION_SELECTOR_COMPACT_LINES",
        "RELIGION_ISLAM_SELECTOR_COMPACT_LINES",
        "RELIGION_SELECTOR_EXCERPT_BYTES",
        "RELIGION_TCM_SELECTOR_EXCERPT_BYTES",
        "RELIGION_SIMLI_BETA6_FRONTIER_TARGET",
        "RELIGION_SIMLI_BETA6_FRONTIER_STOP_FLOOR",
        "RELIGION_SIMLI_BETA6_PER_QUERY_LIMIT",
        "RELIGION_TCM_BETA6_FULL_FRONTIER_REFINE_LIMIT",
    ):
        monkeypatch.delenv(name, raising=False)

    islam = PRODUCT_PROFILES["islam"]
    tcm = PRODUCT_PROFILES["tcm"]
    simli = PRODUCT_PROFILES["simli"]

    assert beta6_module._selector_timeout_seconds(simli) == 45.0
    assert beta6_module._selector_rate_limit_retries(simli) == 3
    assert beta6_module._selector_rate_limit_backoff_seconds(1, simli) == 5.0
    assert beta6_module._selector_compact_candidate_lines_enabled(islam) is True
    assert beta6_module._selector_excerpt_bytes(tcm) == 560
    assert beta6_module._beta6_frontier_target(simli, 100) == 400
    assert beta6_module._beta6_frontier_stop_floor(simli, 100) == 300
    assert beta6_module._beta6_search_plan_query_limit(simli, "ignored", 700) == 120
    assert beta6_module._full_frontier_refine_query_limit(tcm, 700) == 160

    monkeypatch.setenv("RELIGION_SELECTOR_EXCERPT_BYTES", "777")
    assert beta6_module._selector_excerpt_bytes(tcm) == 777


def test_tcm_domain_adapter_owns_mcq_parsing_and_fallback_scoring(monkeypatch):
    adapter = get_domain_adapter("tcm")
    query = """36. 40M] 남자가 SHO] 자주 나온다며 병원에 왔다. 치방은?
0) 균기환
2 사역산
@3) 여성탕
@® 이진탕
© 청담환
위 한의사 국가시험 객관식 문제의 정답 번호를 1~5 중 하나로 고르세요."""
    parsed = adapter.parse_multiple_choice(query)

    assert parsed is not None
    assert [option.text for option in parsed.options] == ["균기환", "사역산", "여성탕", "이진탕", "청담환"]
    assert "정답 번호" not in adapter.search_text(query)

    monkeypatch.setenv("RELIGION_MCQ_HEURISTICS_ENABLED", "1")
    answer = adapter.deterministic_writer_fallback_answer(
        query,
        [
            {
                "file_id": "s1",
                "anchor_text": "사역산은 흉협고만과 간기울결에 쓴다.",
                "metadata": {"sourceKind": "formulary"},
            }
        ],
        [{"sourceId": "s1", "claimSummary": "사역산 근거", "quote": "사역산"}],
        language="ko",
        error="timeout",
    )

    assert answer is not None
    assert answer.startswith("정답: 2) 사역산")
    assert "fallback_score:" in answer
