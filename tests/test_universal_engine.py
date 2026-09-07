import json
import sqlite3

from shared_platform.answer_prompts import direct_answer_messages
from shared_platform.universal_engine import (
    UniversalEngine,
    _append_connected_record_coverage,
    _best_query_window,
    _best_query_windows,
    _close_selected_reference_graph,
    _coverage_candidate_pool,
    _detect_schema,
    _evidence_packet,
    _fts_query_variants,
    _grounded_answer_spans,
    _ensure_verbatim_spans,
    _prioritize_grounded_answer_windows,
    _material_coverage_items,
    _relation_pair_fts_queries,
    _reference_seed_items,
    _reference_like_tokens,
    _merge_ranked_with_diversity_reserve,
    _merge_selection_by_source_id,
    _reserve_explicit_reference_neighbors,
    _reserve_incoming_reference_neighbors,
    _retrieve_candidates,
    _selected_outgoing_reference_neighbors,
    _selected_reference_neighbors,
)


class QueueLLM:
    provider = "fixture_provider"
    default_model = "shared-model"
    decoding = {"temperature": 0.2}

    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []

    def complete(self, messages, *, model="", timeout_seconds=None):
        self.calls.append({"messages": messages, "model": model, "timeoutSeconds": timeout_seconds})
        return self.outputs.pop(0)


def test_universal_engine_uses_exact_closed_book_path_when_retrieval_is_empty(tmp_path):
    db_path = tmp_path / "empty.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE precedents (
          canonical_id TEXT PRIMARY KEY,
          title TEXT,
          case_number TEXT,
          court TEXT,
          decision_date TEXT,
          full_text TEXT
        );
        CREATE VIRTUAL TABLE precedents_fts USING fts5(canonical_id, full_text);
        """
    )
    conn.close()
    question = "Choose one.\n1. alpha\n2. beta"
    llm = QueueLLM(
        [
            json.dumps(
                {
                    "answerShape": "atomic",
                    "queries": ["alpha beta"],
                    "anonymizedStructureQueries": [],
                    "concreteInstanceQueries": [],
                    "answerValueMarkers": [],
                    "candidateCanonicalForms": [],
                    "answerDimensions": [],
                    "coverageFrame": {
                        "authorizationOrScope": "",
                        "procedure": "",
                        "operativeDownstreamConsequence": "",
                        "factSpecificConclusion": "",
                    },
                    "answerDimensionQueries": [],
                    "crossLanguageAliases": [],
                    "relationPairs": [],
                }
            ),
            "정답: 2",
        ]
    )

    result = UniversalEngine(
        corpus_path=db_path,
        llm_client=llm,
        model="shared-model",
    ).answer(question, language="ko")

    assert result["answer"] == "정답: 2"
    assert result["candidateCount"] == 0
    assert result["selectedEvidence"] == []
    assert result["reranker"]["status"] == "no_candidates_closed_book"
    assert len(llm.calls) == 2
    assert llm.calls[1]["messages"] == direct_answer_messages(question, language="ko")


def _precedent_db(path):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE precedents (
          canonical_id TEXT PRIMARY KEY,
          title TEXT,
          case_number TEXT,
          court TEXT,
          decision_date TEXT,
          full_text TEXT
        );
        CREATE VIRTUAL TABLE precedents_fts USING fts5(canonical_id, full_text);
        INSERT INTO precedents VALUES (
          'doc-alpha', 'Alpha authority', '2026-test-1', 'Test Court', '2026-01-01',
          'The alpha remedy requires dual custody and a recorded handover.'
        );
        INSERT INTO precedents VALUES (
          'doc-noise', 'Noise authority', '2026-test-2', 'Test Court', '2026-01-02',
          'Unrelated material about weather and gardens.'
        );
        INSERT INTO precedents VALUES (
          'doc-consequence', 'General consequence authority', '2026-test-3', 'Test Court',
          '2026-01-03',
          'How should the alpha remedy be managed? An unauthorized alpha remedy process makes its resulting record unusable as an operative downstream consequence.'
        );
        INSERT INTO precedents_fts SELECT canonical_id, full_text FROM precedents;
        """
    )
    conn.commit()
    conn.close()


def test_universal_engine_uses_one_domain_neutral_pipeline_and_real_fts_evidence(tmp_path):
    db_path = tmp_path / "corpus.sqlite3"
    _precedent_db(db_path)
    llm = QueueLLM(
        [
            json.dumps(
                {
                    "queries": [
                        "alpha remedy dual custody",
                        "recorded handover",
                        "alpha star astronomy",
                    ],
                    "anonymizedStructureQueries": [
                        "[named remedy] remedy custodian handover procedure",
                        "generic structural alternative one",
                        "generic structural alternative two",
                        "generic structural alternative three",
                    ],
                    "concreteInstanceQueries": [
                        "secured archive cabinet custody procedure",
                        "laboratory cold-storage access procedure",
                    ],
                    "answerValueMarkers": ["required", "unit", "label", "suffix"],
                    "candidateCanonicalForms": ["Alpha Remedy (AR)"],
                    "answerDimensions": [
                        "authorization and scope",
                        "recorded handover procedure",
                        "operative downstream consequence",
                        "bright-star astronomy classification",
                    ],
                    "coverageFrame": {
                        "authorizationOrScope": "alpha remedy authority boundary",
                        "procedure": "required alpha remedy custody procedure",
                        "operativeDownstreamConsequence": (
                            "operative loss of usability after violation"
                        ),
                        "factSpecificConclusion": "fact-specific alpha remedy conclusion",
                    },
                    "answerDimensionQueries": [
                        "alpha remedy violation operative consequence",
                        "alpha remedy authorization scope",
                    ],
                    "crossLanguageAliases": [
                        {"term": "AR", "aliases": ["alpha remedy", "알파 구제"]},
                        {"term": "alpha", "aliases": ["bright star"]},
                    ],
                    "relationPairs": [
                        ["alpha remedy", "dual custody"],
                        ["alpha star", "astronomy"],
                    ],
                }
            ),
            json.dumps(
                {
                    "queries": ["alpha remedy dual custody", "alpha authority handover"],
                    "anonymizedStructureQueries": ["authority handover procedure"],
                    "concreteInstanceQueries": [
                        "records vault cabinet custody",
                    ],
                    "answerValueMarkers": ["authoritative marker"],
                    "candidateCanonicalForms": ["Alpha Remedy (AR)"],
                    "answerDimensions": ["fact-specific conclusion"],
                    "coverageFrame": {
                        "authorizationOrScope": "alpha remedy authority boundary alternative",
                        "procedure": "alternative custody procedure",
                        "operativeDownstreamConsequence": "alternative operative consequence",
                        "factSpecificConclusion": "alternative fact-specific conclusion",
                    },
                    "answerDimensionQueries": [
                        "alpha remedy concrete outcome",
                    ],
                    "crossLanguageAliases": [
                        {"term": "AR", "aliases": ["alpha remedy", "알파 구제"]}
                    ],
                    "relationPairs": [["alpha remedy", "dual custody"]],
                }
            ),
            json.dumps(
                {
                    "selected": [{"id": "doc-alpha", "reason": "direct support"}],
                }
            ),
            json.dumps(
                {
                    "selected": [
                        {"id": "doc-consequence", "reason": "supports a material answer dimension"}
                    ],
                }
            ),
            json.dumps(
                {
                    "resolvedAnswerDimensions": [
                        "authorization and scope",
                        "recorded handover procedure",
                        "operative downstream consequence",
                        "fact-specific conclusion",
                    ],
                }
            ),
            "Dual custody with a recorded handover is required [S1].",
        ]
    )
    engine = UniversalEngine(corpus_path=db_path, llm_client=llm, model="shared-model")

    result = engine.answer("How should the alpha remedy be managed?", language="en")

    assert result["answer"] == "Dual custody with a recorded handover is required [S1]."
    assert [item["sourceId"] for item in result["selectedEvidence"]] == [
        "doc-alpha",
        "doc-consequence",
    ]
    assert "dual custody" in result["selectedEvidence"][0]["exactQuote"]
    assert result["modelMetadata"] == {
        "provider": "fixture_provider",
        "model": "shared-model",
        "decoding": {"temperature": 0.2},
    }
    assert len(llm.calls) == 6
    assert all(call["model"] == "shared-model" for call in llm.calls)
    second_planner_prompt = "\n".join(message["content"] for message in llm.calls[1]["messages"])
    assert "Do not enumerate unrelated dictionary senses" in second_planner_prompt
    assert "Plan to audit" not in second_planner_prompt
    assert "anonymizedStructureQueries" in second_planner_prompt
    assert "concreteInstanceQueries" in second_planner_prompt
    assert "Do not invent the requested answer value" in second_planner_prompt
    assert "first anonymizedStructureQueries item" in second_planner_prompt
    assert "Do not insert bracketed placeholders" in second_planner_prompt
    assert "search headwords" in second_planner_prompt
    assert "answerValueMarkers" in second_planner_prompt
    assert "answerDimensionQueries" in second_planner_prompt
    assert "coverageFrame" in second_planner_prompt
    assert "most directly value-bearing" in second_planner_prompt
    assert "alpha star astronomy" in result["queryPlan"]["queries"]
    assert result["queryPlan"]["anonymizedStructureQueries"] == [
        "remedy custodian handover procedure",
        "authority handover procedure",
        "generic structural alternative one",
        "generic structural alternative two",
    ]
    assert "remedy custodian handover procedure" in result["queryPlan"]["queries"]
    assert result["queryPlan"]["concreteInstanceQueries"] == [
        "secured archive cabinet custody procedure",
        "records vault cabinet custody",
        "laboratory cold-storage access procedure",
    ]
    assert "secured archive cabinet custody procedure" in result["queryPlan"]["queries"]
    assert result["queryPlan"]["answerDimensionQueries"] == [
        "alpha remedy violation operative consequence",
        "alpha remedy concrete outcome",
        "alpha remedy authorization scope",
    ]
    assert result["queryPlan"]["answerDimensionEvidenceQueries"] == [
        "alpha remedy authority boundary",
        "required alpha remedy custody procedure",
        "operative loss of usability after violation",
        "fact-specific alpha remedy conclusion",
        "authorization and scope",
        "recorded handover procedure",
        "operative downstream consequence",
        "bright-star astronomy classification",
    ]
    assert result["queryPlan"]["coverageFrame"]["operativeDownstreamConsequence"] == (
        "operative loss of usability after violation"
    )
    assert "alpha remedy violation operative consequence" not in result["queryPlan"]["queries"]
    assert "operative downstream consequence" not in result["queryPlan"]["queries"]
    assert result["queryPlan"]["answerValueMarkers"] == [
        "required",
        "authoritative marker",
        "unit",
        "label",
    ]
    assert "bright-star astronomy classification" in result["queryPlan"]["answerDimensions"]
    assert "bright-star astronomy classification" not in result["queryPlan"][
        "resolvedAnswerDimensions"
    ]
    reranker_prompt = "\n".join(message["content"] for message in llm.calls[2]["messages"])
    assert "resolvedAnswerDimensions" not in reranker_prompt
    assert "Proposed answer dimensions" not in reranker_prompt
    dimension_reranker_prompt = "\n".join(
        message["content"] for message in llm.calls[3]["messages"]
    )
    assert "doc-consequence" in dimension_reranker_prompt
    assert "doc-alpha" not in dimension_reranker_prompt
    resolver_prompt = "\n".join(message["content"] for message in llm.calls[4]["messages"])
    assert "must not be reselected" in resolver_prompt
    assert "do not keep a meta-dimension" in resolver_prompt
    assert "without naming rejected" in resolver_prompt
    writer_prompt = "\n".join(message["content"] for message in llm.calls[-1]["messages"])
    assert "alpha remedy dual custody" not in writer_prompt
    assert "Alpha Remedy (AR)" in writer_prompt
    assert "dual custody" in writer_prompt
    assert "Answer-coverage hypotheses (not evidence)" in writer_prompt
    assert "operative downstream consequence" in writer_prompt
    assert "fact-specific conclusion" in writer_prompt
    assert "bright-star astronomy classification" not in writer_prompt
    assert "알파 구제" not in writer_prompt
    assert "crossLanguageAliases" not in writer_prompt
    assert "relationPairs" not in writer_prompt
    assert "alpha star astronomy" not in writer_prompt
    prompts = "\n".join(
        str(message.get("content") or "")
        for call in llm.calls
        for message in call["messages"]
    )
    assert "product" not in prompts.lower()
    assert "buddhist" not in prompts.lower()
    assert "islam" not in prompts.lower()
    assert "tcm" not in prompts.lower()
    assert "lawkey" not in prompts.lower()


def test_universal_engine_falls_back_to_same_rrf_candidates_when_reranker_json_is_invalid(tmp_path):
    db_path = tmp_path / "corpus.sqlite3"
    _precedent_db(db_path)
    llm = QueueLLM(
        [
            "not-json",
            "also-not-json",
            "still-not-json",
            "Answer from the available evidence [S1].",
        ]
    )
    engine = UniversalEngine(corpus_path=db_path, llm_client=llm, model="shared-model")

    result = engine.answer("alpha remedy", language="en")

    assert result["queryPlan"]["queries"] == ["alpha remedy"]
    assert result["selectedEvidence"][0]["sourceId"] == "doc-alpha"
    assert result["reranker"]["status"] == "invalid_json_fallback"


def test_atomic_answer_shape_uses_one_plan_one_selection_and_one_writer_call(tmp_path):
    db_path = tmp_path / "corpus.sqlite3"
    _precedent_db(db_path)
    llm = QueueLLM(
        [
            json.dumps(
                {
                    "answerShape": "atomic",
                    "queries": ["alpha remedy dual custody"],
                    "anonymizedStructureQueries": [],
                    "concreteInstanceQueries": [],
                    "answerValueMarkers": ["A", "B"],
                    "candidateCanonicalForms": [],
                    "answerDimensions": ["compare the supplied alternatives"],
                    "coverageFrame": {
                        "authorizationOrScope": "",
                        "procedure": "",
                        "operativeDownstreamConsequence": "",
                        "factSpecificConclusion": "choose the supported alternative",
                    },
                    "answerDimensionQueries": ["alpha remedy required safeguard"],
                    "crossLanguageAliases": [],
                    "relationPairs": [["alpha remedy", "dual custody"]],
                }
            ),
            json.dumps(
                {
                    "selected": [{"id": "doc-alpha", "reason": "direct support"}],
                }
            ),
            "정답: A",
        ]
    )
    engine = UniversalEngine(corpus_path=db_path, llm_client=llm, model="shared-model")

    result = engine.answer(
        "A와 B 중 근거에 맞는 보기ID 하나만 고르고 첫 줄에 정답을 쓰세요.",
        language="ko",
    )

    assert result["answer"] == "정답: A"
    assert result["queryPlan"]["answerShape"] == "atomic"
    assert result["queryPlan"]["planningRepetitions"] == 1
    assert result["queryPlan"]["resolvedAnswerDimensions"] == []
    assert result["selectedEvidence"][0]["sourceId"] == "doc-alpha"
    assert "coverageAudit" not in result["reranker"]
    assert "dimensionCoverageAudit" not in result["reranker"]
    assert len(llm.calls) == 3
    writer_prompt = "\n".join(message["content"] for message in llm.calls[-1]["messages"])
    assert "Evidence-role analysis" in writer_prompt
    assert "compare the supplied alternatives" not in writer_prompt


def test_retrieval_preserves_each_querys_best_candidate_before_global_rrf_cutoff(tmp_path):
    db_path = tmp_path / "query-diversity.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE precedents (
          canonical_id TEXT PRIMARY KEY,
          title TEXT,
          case_number TEXT,
          court TEXT,
          decision_date TEXT,
          full_text TEXT
        );
        CREATE VIRTUAL TABLE precedents_fts USING fts5(canonical_id, full_text);
        """
    )
    for index in range(10):
        conn.execute(
            "INSERT INTO precedents VALUES (?, ?, ?, ?, ?, ?)",
            (
                f"noise-{index}",
                f"Noise {index}",
                f"N-{index}",
                "Test Court",
                "2026-01-01",
                "common general records analysis management filler",
            ),
        )
    conn.execute(
        "INSERT INTO precedents VALUES (?, ?, ?, ?, ?, ?)",
        (
            "a-structure-distractor",
            "Over-specific structure",
            "D-1",
            "Test Court",
            "2026-01-01",
            "administrator petitioner age estimate",
        ),
    )
    conn.execute(
        "INSERT INTO precedents VALUES (?, ?, ?, ?, ?, ?)",
        (
            "z-target",
            "Masked event",
            "T-1",
            "Test Court",
            "2026-01-01",
            "An administrator handled a petitioner matter and the petitioner age was recorded.",
        ),
    )
    conn.execute(
        "INSERT INTO precedents VALUES (?, ?, ?, ?, ?, ?)",
        (
            "zz-independent-target",
            "Independent hypothesis",
            "T-2",
            "Test Court",
            "2026-01-01",
            "rare independent hypothesis evidence",
        ),
    )
    conn.execute("INSERT INTO precedents_fts SELECT canonical_id, full_text FROM precedents")
    conn.commit()
    conn.row_factory = sqlite3.Row

    candidates = _retrieve_candidates(
        conn,
        _detect_schema(conn),
        [
            "common general records analysis management",
            "administrator petitioner age estimate",
            "rare independent hypothesis evidence",
        ],
        limit=9,
    )

    candidate_ids = {item["sourceId"] for item in candidates}
    assert "z-target" in candidate_ids
    assert "zz-independent-target" in candidate_ids


def test_diversity_reserve_does_not_evict_an_earlier_reserved_hypothesis():
    globally_ranked = [
        {"sourceId": "global-1"},
        {"sourceId": "global-2"},
        {"sourceId": "global-3"},
        {"sourceId": "global-4"},
    ]
    reserved = [
        {"sourceId": "hypothesis-a"},
        {"sourceId": "hypothesis-b"},
    ]

    selected = _merge_ranked_with_diversity_reserve(
        globally_ranked,
        reserved,
        limit=4,
    )

    assert [item["sourceId"] for item in selected] == [
        "hypothesis-a",
        "hypothesis-b",
        "global-1",
        "global-2",
    ]


def test_only_grounded_material_answer_spans_are_preserved_verbatim():
    evidence = [
        {
            "sourceId": "primary",
            "exactQuote": (
                "A different actor is Person C (male, 64 years).\n[…]\n"
                "The record identifies Person Z (female, 64 years) as the petitioner."
            ),
            "exactQuotes": [
                "A different actor is Person C (male, 64 years).",
                "The record identifies Person Z (female, 64 years) as the petitioner.",
            ],
        },
        {
            "sourceId": "unrelated",
            "exactQuote": "Another record identifies Person Q (female, 12 years).",
        },
    ]
    roles = [
        {
            "sourceId": "primary",
            "materialToAnswer": True,
            "answerBearingExactSpans": [
                "Person Z (female, 64 years)",
                "invented span",
            ],
        },
        {
            "sourceId": "unrelated",
            "materialToAnswer": False,
            "answerBearingExactSpans": ["Person Q (female, 12 years)"],
        },
    ]

    spans = _grounded_answer_spans(roles, evidence)

    assert spans == ["Person Z (female, 64 years)"]
    _prioritize_grounded_answer_windows(roles, evidence)
    assert evidence[0]["exactQuote"].startswith(
        "The record identifies Person Z (female, 64 years)"
    )
    answer = _ensure_verbatim_spans("The petitioner was 64 years old.", spans)
    assert "Person Z (female, 64 years)" in answer


def test_evidence_packet_preserves_value_marker_window_from_late_in_long_record():
    early = "".join(
        f"민원인 나이 추정과 100만원에 관한 일반 설명 {index}. " + ("가" * 900)
        for index in range(4)
    )
    full_text = (
        early
        + " 다른 역할의 피해자 C(남, 64세)는 별도의 사실에 등장한다."
        + ("나" * 1800)
        + " 민원인인 피해자 D(여, 64세)는 질문에 답하는 구체 사실에 등장한다."
    )

    packet = _evidence_packet(
        {
            "sourceId": "masked-record",
            "referenceId": "T-1",
            "title": "Masked record",
            "citation": "T-1 · Test Court",
            "fullText": full_text,
            "retrievalRanks": [],
        },
        index=1,
        query="민원인 나이를 추정해봐",
        query_plan={
            "queries": ["민원인 나이 추정"],
            "answerValueMarkers": ["세", "만", "나이", "연령"],
        },
        selection_reason="direct support",
    )

    assert "피해자 D(여, 64세)" in packet["exactQuote"]
    assert any(
        "피해자 C(남, 64세)" in window
        for window in packet["exactQuotes"][:2]
    )
    assert any(
        "피해자 D(여, 64세)" in window
        for window in packet["exactQuotes"][:2]
    )


def test_universal_engine_supports_documents_fts_schema_without_domain_configuration(tmp_path):
    db_path = tmp_path / "documents.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE documents (
          canonical_id TEXT PRIMARY KEY,
          title TEXT,
          question TEXT,
          answer TEXT,
          body TEXT,
          full_text TEXT
        );
        CREATE VIRTUAL TABLE documents_fts USING fts5(title, question, answer, body);
        INSERT INTO documents VALUES (
          'doc-memory', 'Memory consolidation', 'What consolidates memory?',
          'Sleep', 'Sleep supports memory consolidation.', 'Sleep supports memory consolidation.'
        );
        INSERT INTO documents_fts(rowid, title, question, answer, body)
          SELECT rowid, title, question, answer, body FROM documents;
        """
    )
    conn.commit()
    conn.close()
    llm = QueueLLM(
        [
            json.dumps({"queries": ["sleep memory consolidation"]}),
            json.dumps({"queries": ["sleep consolidation"]}),
            json.dumps({"selected": [{"id": "doc-memory"}]}),
            "Sleep",
        ]
    )

    result = UniversalEngine(corpus_path=db_path, llm_client=llm, model="shared-model").answer(
        "What supports memory consolidation?",
        language="en",
    )

    assert result["corpusSchema"] == "documents_fts"
    assert result["selectedEvidence"][0]["sourceId"] == "doc-memory"
    assert result["answer"] == "Sleep"


def test_fts_queries_use_bounded_conjunctions_instead_of_broad_or_scans():
    variants = _fts_query_variants(
        "Sacks describes two women with musical epilepsy hearing songs temporal pathology"
    )

    assert variants
    assert all(" OR " not in query for query in variants)
    assert all(query.count(" AND ") <= 5 for query in variants)
    assert variants[0].startswith('"sacks" AND "describes"')
    assert '"sacks" AND "describes" AND "two"' in variants
    assert '"two"* AND "women"*' in variants


def test_passage_window_prefers_dense_semantic_match_over_first_common_term():
    text = (
        "검찰 일반론만 앞부분에 있다. "
        + ("무관한 내용 " * 400)
        + "검찰이 유심칩을 다른 휴대폰에 넣어 인증번호를 받고 메신저 대화를 열람하였다."
    )

    window = _best_query_window(
        text,
        "검찰이 유심칩을 다른 휴대폰에 넣어 인증번호를 받고 메신저 대화를 본 사건",
        max_chars=500,
    )

    assert "유심칩을 다른 휴대폰" in window
    assert "인증번호" in window
    assert "메신저 대화" in window


def test_best_query_windows_preserve_distinct_relevant_passages():
    text = (
        "first relation alpha login evidence "
        + ("filler " * 80)
        + "second relation beta appeal outcome"
    )

    windows = _best_query_windows(
        text,
        ["alpha login", "beta appeal"],
        max_chars=120,
        max_windows=2,
    )

    assert len(windows) == 2
    assert any("alpha login" in window for window in windows)
    assert any("beta appeal" in window for window in windows)


def test_relation_pair_queries_preserve_cross_side_concept_combinations():
    variants = _relation_pair_fts_queries(
        ["subscriber module separation", "messenger account login"]
    )

    assert '"subscriber"* AND "account"*' in variants
    assert all(" OR " not in query for query in variants)
    assert len(variants) <= 6


def test_relation_pair_queries_drop_redundant_self_conjunctions():
    variants = _relation_pair_fts_queries(
        ["digital evidence", "evidence admissibility"]
    )

    assert variants
    assert '"evidence"* AND "evidence"*' not in variants


def test_relation_pair_queries_propagate_bidirectional_aliases():
    variants = _relation_pair_fts_queries(
        ["SIM separation", "messenger account login"],
        alias_groups=[{"term": "SIM", "aliases": ["유심", "USIM"]}],
    )

    assert '"유심"* AND "login"*' in variants
    assert len(variants) <= 18


def test_relation_alias_replacement_uses_longest_existing_member():
    variants = _relation_pair_fts_queries(
        ["압수수색영장 범위", "전자정보 접근"],
        alias_groups=[
            {"term": "영장 범위", "aliases": ["압수수색영장 범위", "warrant scope"]}
        ],
    )

    assert all("압수수색압수수색영장" not in query for query in variants)


def test_reference_seeds_preserve_a_leader_from_each_relation_stratum():
    consensus = [
        {
            "sourceId": f"consensus-{index}",
            "rrfScore": 1.0 - index / 100,
            "retrievalRanks": [],
        }
        for index in range(12)
    ]
    relation_leader = {
        "sourceId": "relation-leader",
        "rrfScore": 0.01,
        "retrievalRanks": [
            {"source": "relation_pair", "pairIndex": 2, "variantIndex": 0, "rank": 1},
            {"source": "relation_pair", "pairIndex": 2, "variantIndex": 1, "rank": 2},
        ],
    }

    seeds = _reference_seed_items(consensus + [relation_leader], max_items=6)

    assert relation_leader in seeds
    assert len(seeds) == 6


def test_reference_seeds_round_robin_across_relation_variants():
    ranked = [
        {
            "sourceId": "pair-0-variant-0",
            "rrfScore": 0.9,
            "retrievalRanks": [
                {"source": "relation_pair", "pairIndex": 0, "variantIndex": 0, "rank": 1}
            ],
        },
        {
            "sourceId": "pair-1-variant-0",
            "rrfScore": 0.8,
            "retrievalRanks": [
                {"source": "relation_pair", "pairIndex": 1, "variantIndex": 0, "rank": 1}
            ],
        },
        {
            "sourceId": "pair-0-variant-1",
            "rrfScore": 0.1,
            "retrievalRanks": [
                {"source": "relation_pair", "pairIndex": 0, "variantIndex": 1, "rank": 1}
            ],
        },
        {
            "sourceId": "pair-1-variant-1",
            "rrfScore": 0.05,
            "retrievalRanks": [
                {"source": "relation_pair", "pairIndex": 1, "variantIndex": 1, "rank": 1}
            ],
        },
    ]

    seeds = _reference_seed_items(ranked, max_items=4)

    assert {item["sourceId"] for item in seeds} == {
        "pair-0-variant-0",
        "pair-1-variant-0",
        "pair-0-variant-1",
        "pair-1-variant-1",
    }


def test_coverage_selection_replaces_fallback_at_capacity_and_deduplicates_ids():
    primary = [{"sourceId": "connected"}, {"sourceId": "shared"}]
    fallback = [{"sourceId": "shared"}, {"sourceId": "generic"}]

    merged = _merge_selection_by_source_id(primary, fallback, limit=2)

    assert [item["sourceId"] for item in merged] == ["connected", "shared"]


def test_coverage_pool_reintroduces_high_ranked_original_candidates_after_graph_expansion():
    selected = [{"sourceId": "trial"}]
    reference_neighbors = [{"sourceId": "trial"}, {"sourceId": "appeal"}]
    original_candidates = [
        {"sourceId": "trial"},
        {"sourceId": "parallel-proceeding"},
        {"sourceId": "generic"},
    ]

    pool = _coverage_candidate_pool(
        selected,
        reference_neighbors,
        original_candidates,
        limit=4,
    )

    assert [item["sourceId"] for item in pool] == [
        "trial",
        "appeal",
        "parallel-proceeding",
        "generic",
    ]


def test_reference_graph_closure_reserves_capacity_for_explicitly_connected_record():
    selected = [
        {
            "sourceId": "parallel-proceeding",
            "referenceId": "CASE-PARALLEL",
            "retrievalRanks": [
                {
                    "source": "reference_neighbor",
                    "isCrossReference": True,
                    "reference": "CASE-APPEAL",
                }
            ],
        },
        {"sourceId": "generic-a", "referenceId": "GEN-A", "retrievalRanks": []},
        {"sourceId": "generic-b", "referenceId": "GEN-B", "retrievalRanks": []},
    ]
    appeal = {
        "sourceId": "appeal",
        "referenceId": "CASE-APPEAL",
        "retrievalRanks": [],
    }

    closed = _close_selected_reference_graph(
        selected,
        [*selected, appeal],
        limit=3,
    )

    assert [item["sourceId"] for item in closed] == [
        "parallel-proceeding",
        "generic-a",
        "appeal",
    ]


def test_incoming_reference_reserve_requires_both_top_semantic_rank_and_graph_edge():
    selected = [
        {"sourceId": "appeal", "referenceId": "CASE-APPEAL"},
        {"sourceId": "generic-a", "referenceId": "GEN-A"},
        {"sourceId": "generic-b", "referenceId": "GEN-B"},
    ]
    connected_candidate = {
        "sourceId": "later-review",
        "referenceId": "CASE-REVIEW",
        "retrievalRanks": [
            {
                "source": "reference_neighbor",
                "isCrossReference": True,
                "reference": "CASE-APPEAL",
            }
        ],
    }
    unrelated_candidate = {
        "sourceId": "semantic-only",
        "referenceId": "CASE-OTHER",
        "retrievalRanks": [{"queryIndex": 0, "rank": 1}],
    }

    reserved = _reserve_incoming_reference_neighbors(
        selected,
        [unrelated_candidate, connected_candidate],
        limit=3,
        max_additions=1,
    )

    assert [item["sourceId"] for item in reserved] == [
        "appeal",
        "generic-a",
        "later-review",
    ]


def test_connected_coverage_renderer_preserves_structured_semantics_and_citation():
    answer = _append_connected_record_coverage(
        "Existing analysis.",
        [
            {
                "sourceId": "record-appeal",
                "title": "Appeal record CASE-BETA",
                "citation": "CASE-BETA · Appeal Court",
                "selectionReason": "fallback reason",
            }
        ],
        coverage_records=[
            {
                "sourceId": "record-appeal",
                "referenceId": "CASE-BETA",
                "supportedRole": "It is the appeal-stage record.",
                "directIssueAndOutcome": "The appeal reversed on a separate issue.",
                "excerptSupportedOperativeProposition": (
                    "The appeal treats the safeguard as a condition of valid execution."
                ),
                "questionApplication": "The described process must therefore include that safeguard.",
                "factApplication": "It applies the procedure to the described execution.",
                "proceduralPostureOrOutcome": "The appeal affirmed the procedural ruling.",
                "holdingBoundary": "It does not decide the separate storage issue.",
            }
        ],
    )

    assert "CASE-BETA" in answer
    assert "appeal-stage record" in answer
    assert "appeal reversed on a separate issue" in answer
    assert "condition of valid execution" in answer
    assert "must therefore include that safeguard" in answer
    assert "described execution" in answer
    assert "appeal affirmed" in answer
    assert "does not decide" in answer


def test_material_coverage_includes_semantically_same_event_without_explicit_graph_edge():
    graph_item = {"sourceId": "record-appeal", "referenceId": "CASE-APPEAL"}
    same_event_item = {"sourceId": "record-review", "referenceId": "CASE-REVIEW"}
    background_item = {"sourceId": "record-background", "referenceId": "CASE-BACKGROUND"}

    required = _material_coverage_items(
        [graph_item, same_event_item, background_item],
        connected_items=[graph_item],
        coverage_records=[
            {
                "sourceId": "record-review",
                "materialToAnswer": True,
                "sameEventOrProcess": True,
            },
            {
                "sourceId": "record-background",
                "materialToAnswer": False,
                "sameEventOrProcess": False,
            },
        ],
    )

    assert [item["sourceId"] for item in required] == ["record-appeal", "record-review"]


def test_writer_preserves_structured_semantics_even_when_reference_was_already_named(tmp_path):
    llm = QueueLLM(
        [
            json.dumps(
                {
                    "recordRoles": [
                        {
                            "sourceId": "trial",
                            "referenceId": "CASE-TRIAL",
                            "materialToAnswer": True,
                            "sameEventOrProcess": True,
                            "directIssueAndOutcome": "The trial decided the execution dispute.",
                            "excerptSupportedOperativeProposition": (
                                "The trial treats the method as part of the authorized execution."
                            ),
                            "questionApplication": (
                                "The described secondary-device access must stay within that method."
                            ),
                            "holdingBoundary": "It does not decide the later appeal issue.",
                        },
                        {
                            "sourceId": "appeal",
                            "referenceId": "CASE-APPEAL",
                            "materialToAnswer": True,
                            "sameEventOrProcess": True,
                            "directIssueAndOutcome": "The appeal reversed on a separate issue.",
                            "excerptSupportedOperativeProposition": (
                                "The appeal preserves a distinct procedural safeguard."
                            ),
                            "questionApplication": (
                                "The described execution must also comply with that safeguard."
                            ),
                            "holdingBoundary": "It does not create a universal authorization.",
                        },
                    ]
                }
            ),
            json.dumps(
                {
                    "recordRoles": [
                        {
                            "sourceId": "trial",
                            "referenceId": "CASE-TRIAL",
                            "directIssueAndOutcome": "The trial decided the execution dispute.",
                            "excerptSupportedOperativeProposition": (
                                "The trial treats the method as part of the authorized execution."
                            ),
                            "questionApplication": (
                                "The described secondary-device access must stay within that method."
                            ),
                        },
                        {
                            "sourceId": "appeal",
                            "referenceId": "CASE-APPEAL",
                            "directIssueAndOutcome": "The appeal reversed on a separate issue.",
                            "excerptSupportedOperativeProposition": (
                                "The appeal preserves a distinct procedural safeguard."
                            ),
                            "questionApplication": (
                                "The described execution must also comply with that safeguard."
                            ),
                        },
                    ]
                }
            ),
            "CASE-TRIAL and CASE-APPEAL concern the same event.",
            json.dumps(
                {
                    "outputMode": "explanatory",
                    "answer": "CASE-TRIAL and CASE-APPEAL concern the same event.",
                    "recordCoverage": [
                        {
                            "sourceId": "trial",
                            "referenceId": "CASE-TRIAL",
                            "materialToAnswer": True,
                            "sameEventOrProcess": True,
                            "supportedRole": "The trial record supplies the execution method.",
                            "factApplication": "It applies to the described secondary-device access.",
                            "proceduralPostureOrOutcome": "The trial decided the execution dispute.",
                            "holdingBoundary": "It does not decide the later appeal issue.",
                        },
                        {
                            "sourceId": "appeal",
                            "referenceId": "CASE-APPEAL",
                            "materialToAnswer": True,
                            "sameEventOrProcess": True,
                            "supportedRole": "The appeal record supplies the appellate posture.",
                            "factApplication": "It applies to the same execution sequence.",
                            "proceduralPostureOrOutcome": "The appeal reversed on a separate issue.",
                            "holdingBoundary": "It does not create a universal authorization.",
                        },
                    ],
                    "questionCoverage": {
                        "authorizationOrScope": "The process requires specific authorization.",
                        "procedure": "The described safeguards must be followed.",
                        "operativeDownstreamConsequence": (
                            "The source does not itself decide the downstream consequence."
                        ),
                        "factSpecificConclusion": "The facts require a conditional conclusion.",
                    },
                    "dimensionCoverage": [
                        {
                            "dimension": "What operative effect follows from a violation?",
                            "answerContribution": (
                                "The source does not itself decide that operative effect."
                            ),
                        }
                    ],
                }
            ),
            json.dumps(
                {
                    "dimensionCoverage": [
                        {
                            "dimension": "What operative effect follows from a violation?",
                            "answerContribution": (
                                "As clearly labeled general reasoning, if the process is unauthorized, "
                                "its result cannot be used."
                            ),
                        }
                    ]
                }
            ),
        ]
    )
    evidence = [
        {
            "label": "S1",
            "sourceId": "trial",
            "referenceId": "CASE-TRIAL",
            "title": "Trial CASE-TRIAL",
            "citation": "CASE-TRIAL · Trial Court",
            "exactQuote": "The execution method was described.",
            "selectionReason": "same event",
            "connectedReferences": ["CASE-APPEAL"],
        },
        {
            "label": "S2",
            "sourceId": "appeal",
            "referenceId": "CASE-APPEAL",
            "title": "Appeal CASE-APPEAL",
            "citation": "CASE-APPEAL · Appeal Court",
            "exactQuote": "The appeal reviewed the execution.",
            "selectionReason": "same event appeal",
            "connectedReferences": ["CASE-TRIAL"],
        },
    ]

    answer = UniversalEngine(
        corpus_path=tmp_path / "unused.sqlite3",
        llm_client=llm,
        model="shared-model",
    )._write_answer(
        "Explain the event and its consequences.",
        evidence,
        query_plan={
            "queries": ["event consequences"],
            "answerDimensions": ["What operative effect follows from a violation?"],
            "coverageFrame": {
                "authorizationOrScope": "",
                "procedure": "",
                "operativeDownstreamConsequence": (
                    "What operative effect follows from a violation?"
                ),
                "factSpecificConclusion": "",
            },
        },
        language="en",
    )

    assert "supplies the execution method" in answer
    assert "described secondary-device access" in answer
    assert "does not decide the later appeal issue" in answer
    assert "supplies the appellate posture" in answer
    assert "appeal reversed on a separate issue" in answer
    assert "unauthorized, its result cannot be used" in answer
    audit_instruction = llm.calls[3]["messages"][0]["content"]
    assert "one dimensionCoverage entry for every supplied answerDimension" in audit_instruction
    focused_dimension_instruction = llm.calls[4]["messages"][0]["content"]
    assert "Do not merely say that a source did not decide the dimension" in focused_dimension_instruction
    assert "merely calling the record factual background is not substantive coverage" in audit_instruction
    assert "preserve that exact source wording" in audit_instruction
    writer_instruction = llm.calls[2]["messages"][0]["content"]
    assert "reproduce that exact source wording" in writer_instruction
    assert "Anonymized labels may differ across records" in writer_instruction
    role_instruction = llm.calls[0]["messages"][0]["content"]
    assert "belongs only in factContribution" in role_instruction
    focused_instruction = llm.calls[1]["messages"][0]["content"]
    assert "Deepen the evidence-role analysis" in focused_instruction
    assert "distinct procedural safeguard" in answer


def test_writer_restores_a_grounded_exact_span_after_semantic_paraphrase(tmp_path):
    exact_span = "Person Z (female, 64 years)"
    roles = {
        "recordRoles": [
            {
                "sourceId": "trial",
                "referenceId": "CASE-TRIAL",
                "materialToAnswer": True,
                "sameEventOrProcess": True,
                "directIssueAndOutcome": "The trial recorded the petitioner's identity.",
                "factContribution": "The petitioner was identified in a compact field.",
                "holdingBoundary": "It does not update the value after judgment.",
                "answerBearingExactSpans": [exact_span],
            },
            {
                "sourceId": "appeal",
                "referenceId": "CASE-APPEAL",
                "materialToAnswer": True,
                "sameEventOrProcess": True,
                "directIssueAndOutcome": "The appeal reviewed the same event.",
                "holdingBoundary": "It does not restate the compact value.",
                "answerBearingExactSpans": [],
            },
        ]
    }
    llm = QueueLLM(
        [
            json.dumps(roles),
            json.dumps(roles),
            "CASE-TRIAL and CASE-APPEAL show that the petitioner was 64 years old.",
            json.dumps(
                {
                    "outputMode": "explanatory",
                    "answer": (
                        "CASE-TRIAL and CASE-APPEAL show that the petitioner was 64 years old."
                    ),
                    "recordCoverage": roles["recordRoles"],
                    "questionCoverage": {},
                }
            ),
        ]
    )
    evidence = [
        {
            "label": "S1",
            "sourceId": "trial",
            "referenceId": "CASE-TRIAL",
            "title": "Trial",
            "citation": "CASE-TRIAL · Trial Court",
            "exactQuote": f"The record identifies {exact_span} as the petitioner.",
            "selectionReason": "direct compact value",
            "connectedReferences": ["CASE-APPEAL"],
        },
        {
            "label": "S2",
            "sourceId": "appeal",
            "referenceId": "CASE-APPEAL",
            "title": "Appeal",
            "citation": "CASE-APPEAL · Appeal Court",
            "exactQuote": "The appeal reviewed CASE-TRIAL.",
            "selectionReason": "same event appeal",
            "connectedReferences": ["CASE-TRIAL"],
        },
    ]

    answer = UniversalEngine(
        corpus_path=tmp_path / "unused.sqlite3",
        llm_client=llm,
        model="shared-model",
    )._write_answer(
        "What exact compact value identifies the petitioner?",
        evidence,
        query_plan={"queries": ["petitioner compact value"]},
        language="en",
    )

    assert exact_span in answer


def test_retrieval_expands_structured_reference_neighbors(tmp_path):
    db_path = tmp_path / "reference-neighbors.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE precedents (
          canonical_id TEXT PRIMARY KEY,
          title TEXT,
          case_number TEXT,
          court TEXT,
          decision_date TEXT,
          full_text TEXT
        );
        CREATE VIRTUAL TABLE precedents_fts USING fts5(canonical_id, full_text);
        INSERT INTO precedents VALUES (
          'doc-trial', 'Trial authority', 'CASE-2026-ALPHA', 'Test Court', '2026-01-01',
          'The alpha remedy requires dual custody and a recorded handover.'
        );
        INSERT INTO precedents VALUES (
          'doc-appeal', 'Appeal authority', 'CASE-2026-BETA', 'Appeal Court', '2026-02-01',
          'The appeal reviews CASE-2026-ALPHA and confirms the trial authority.'
        );
        INSERT INTO precedents VALUES (
          'doc-review', 'Review authority', 'CASE-2026-GAMMA', 'Review Court', '2026-03-01',
          'The later review discusses CASE-2026-BETA and its treatment of the appeal.'
        );
        INSERT INTO precedents_fts SELECT canonical_id, full_text FROM precedents;
        """
    )
    conn.commit()
    conn.row_factory = sqlite3.Row

    candidates = _retrieve_candidates(
        conn,
        _detect_schema(conn),
        ["alpha remedy dual custody recorded handover"],
        limit=10,
    )

    assert {item["sourceId"] for item in candidates} == {"doc-trial", "doc-appeal", "doc-review"}
    appeal = next(item for item in candidates if item["sourceId"] == "doc-appeal")
    assert any(rank.get("source") == "reference_neighbor" for rank in appeal["retrievalRanks"])
    review = next(item for item in candidates if item["sourceId"] == "doc-review")
    assert any(
        rank.get("source") == "reference_neighbor"
        and rank.get("depth") == 2
        and rank.get("isCrossReference")
        for rank in review["retrievalRanks"]
    )
    selected_pool = _selected_reference_neighbors(
        conn,
        _detect_schema(conn),
        [next(item for item in candidates if item["sourceId"] == "doc-trial")],
        max_neighbors_per_seed=2,
    )
    assert {item["sourceId"] for item in selected_pool} == {"doc-trial", "doc-appeal"}
    reverse_pool = _selected_reference_neighbors(
        conn,
        _detect_schema(conn),
        [appeal],
        max_neighbors_per_seed=2,
    )
    assert {item["sourceId"] for item in reverse_pool} == {
        "doc-trial",
        "doc-appeal",
        "doc-review",
    }

    outgoing_pool = _selected_outgoing_reference_neighbors(
        conn,
        _detect_schema(conn),
        [appeal],
        max_neighbors_per_seed=2,
    )
    assert {item["sourceId"] for item in outgoing_pool} == {"doc-trial", "doc-appeal"}
    trial = next(item for item in outgoing_pool if item["sourceId"] == "doc-trial")
    assert any(
        rank.get("source") == "reference_neighbor"
        and rank.get("selectedSeed")
        and rank.get("outgoingReference") == "CASE-2026-ALPHA"
        for rank in trial["retrievalRanks"]
    )

    retained = _reserve_explicit_reference_neighbors(
        [
            appeal,
            {"sourceId": "generic-a"},
            {"sourceId": "generic-b"},
        ],
        [
            appeal,
            {"sourceId": "generic-a"},
            {"sourceId": "generic-b"},
            trial,
        ],
        limit=3,
    )
    assert [item["sourceId"] for item in retained] == [
        "doc-appeal",
        "generic-a",
        "doc-trial",
    ]

    bounded = _reserve_explicit_reference_neighbors(
        [
            {"sourceId": "semantic-a"},
            {"sourceId": "semantic-b"},
            {"sourceId": "semantic-c"},
        ],
        [
            {"sourceId": "semantic-a"},
            {"sourceId": "semantic-b"},
            {"sourceId": "semantic-c"},
            {"sourceId": "reference-a"},
            {"sourceId": "reference-b"},
            {"sourceId": "reference-c"},
        ],
        limit=3,
        max_additions=1,
    )
    assert [item["sourceId"] for item in bounded] == [
        "semantic-a",
        "semantic-b",
        "reference-a",
    ]
    conn.close()


def test_outgoing_reference_expansion_does_not_follow_a_seed_self_identifier_collision(tmp_path):
    db_path = tmp_path / "reference-collision.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE precedents (
          canonical_id TEXT PRIMARY KEY,
          title TEXT,
          case_number TEXT,
          court TEXT,
          decision_date TEXT,
          full_text TEXT
        );
        CREATE VIRTUAL TABLE precedents_fts USING fts5(canonical_id, full_text);
        INSERT INTO precedents VALUES (
          'seed', 'Seed event', 'SAME-2026-1', 'First Court', '2026-01-01',
          'SAME-2026-1 concerns the alpha petitioner event.'
        );
        INSERT INTO precedents VALUES (
          'collision', 'Different event', 'SAME-2026-1', 'Other Court', '2026-02-01',
          'SAME-2026-1 concerns an unrelated weather event.'
        );
        INSERT INTO precedents_fts SELECT canonical_id, full_text FROM precedents;
        """
    )
    conn.commit()
    conn.row_factory = sqlite3.Row
    schema = _detect_schema(conn)
    seed = next(
        item
        for item in _retrieve_candidates(conn, schema, ["alpha petitioner"], limit=4)
        if item["sourceId"] == "seed"
    )

    expanded = _selected_outgoing_reference_neighbors(
        conn,
        schema,
        [seed],
        max_neighbors_per_seed=3,
    )

    assert [item["sourceId"] for item in expanded] == ["seed"]
    conn.close()


def test_outgoing_reference_expansion_closes_selected_chain_before_unrelated_seeds(tmp_path):
    db_path = tmp_path / "selected-reference-chain.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE precedents (
          canonical_id TEXT PRIMARY KEY,
          title TEXT,
          case_number TEXT,
          court TEXT,
          decision_date TEXT,
          full_text TEXT
        );
        CREATE VIRTUAL TABLE precedents_fts USING fts5(canonical_id, full_text);
        INSERT INTO precedents VALUES
          ('root', 'Root record', 'CASE-ROOT-1', 'Court', '2026-01-01',
           'CASE-CHILD-1 CASE-NOISE-A1 CASE-NOISE-B1'),
          ('middle', 'Unrelated selected record', 'CASE-MIDDLE-1', 'Court', '2026-01-02',
           'CASE-NOISE-C1 CASE-NOISE-D1 CASE-NOISE-E1'),
          ('child', 'Connected selected record', 'CASE-CHILD-1', 'Court', '2026-01-03',
           'CASE-TARGET-1'),
          ('generic', 'Generic selected record', 'CASE-GENERIC-1', 'Court', '2026-01-04',
           'No outgoing identifier.'),
          ('noise-a', 'Noise A', 'CASE-NOISE-A1', 'Court', '2026-02-01', 'Noise A.'),
          ('noise-b', 'Noise B', 'CASE-NOISE-B1', 'Court', '2026-02-02', 'Noise B.'),
          ('noise-c', 'Noise C', 'CASE-NOISE-C1', 'Court', '2026-02-03', 'Noise C.'),
          ('noise-d', 'Noise D', 'CASE-NOISE-D1', 'Court', '2026-02-04', 'Noise D.'),
          ('noise-e', 'Noise E', 'CASE-NOISE-E1', 'Court', '2026-02-05', 'Noise E.'),
          ('target', 'Target continuation', 'CASE-TARGET-1', 'Court', '2026-03-01',
           'The connected continuation supplies the requested rule.');
        INSERT INTO precedents_fts SELECT canonical_id, full_text FROM precedents;
        """
    )
    conn.commit()
    conn.row_factory = sqlite3.Row
    schema = _detect_schema(conn)
    selected = [
        {
            "sourceId": "root",
            "referenceId": "CASE-ROOT-1",
            "fullText": "CASE-CHILD-1 CASE-NOISE-A1 CASE-NOISE-B1",
            "retrievalRanks": [],
        },
        {
            "sourceId": "middle",
            "referenceId": "CASE-MIDDLE-1",
            "fullText": "CASE-NOISE-C1 CASE-NOISE-D1 CASE-NOISE-E1",
            "retrievalRanks": [],
        },
        {
            "sourceId": "generic",
            "referenceId": "CASE-GENERIC-1",
            "fullText": "No outgoing identifier.",
            "retrievalRanks": [],
        },
        {
            "sourceId": "child",
            "referenceId": "CASE-CHILD-1",
            "fullText": "CASE-TARGET-1",
            "retrievalRanks": [],
        },
    ]

    traced_sql: list[str] = []
    conn.set_trace_callback(traced_sql.append)
    expanded = _selected_outgoing_reference_neighbors(
        conn,
        schema,
        selected,
        max_neighbors_per_seed=3,
    )
    conn.set_trace_callback(None)
    bounded = _reserve_explicit_reference_neighbors(
        selected,
        expanded,
        limit=6,
        max_additions=3,
    )

    assert "target" in [item["sourceId"] for item in bounded]
    assert "child" in [item["sourceId"] for item in bounded]
    assert "generic" not in [item["sourceId"] for item in bounded]
    assert "noise-c" not in [item["sourceId"] for item in bounded]
    reference_selects = [
        statement
        for statement in traced_sql
        if "SELECT d.*" in statement and "WHERE d.case_number" in statement
    ]
    assert len(reference_selects) == 1
    conn.close()


def test_reference_like_tokens_are_generic_identifiers_not_plain_words_or_years():
    assert _reference_like_tokens(
        "See CASE-2026-ALPHA, 2021노1520 and ordinary prose from 2026."
    ) == ["CASE-2026-ALPHA", "2021노1520"]
