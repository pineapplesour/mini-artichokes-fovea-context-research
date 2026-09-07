from __future__ import annotations

import json
import re
import sqlite3
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from shared_platform.answer_prompts import direct_answer_messages


class LLMClient(Protocol):
    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        model: str = "",
        timeout_seconds: float | None = None,
    ) -> str: ...


@dataclass(frozen=True)
class _CorpusSchema:
    name: str
    content_table: str
    fts_table: str
    id_column: str
    fts_id_column: str
    text_column: str
    join_by_rowid: bool
    fts_text_column_index: int


class UniversalEngine:
    """One retrieval and answer policy for every supported SQLite corpus.

    The only branching in this class is mechanical storage-schema detection.
    No benchmark identity, subject name, or per-corpus semantic policy is an
    input to the engine.
    """

    def __init__(
        self,
        *,
        corpus_path: Path,
        llm_client: LLMClient,
        model: str,
        candidate_limit: int = 40,
        evidence_limit: int = 12,
        timeout_seconds: float = 300.0,
        planning_repetitions: int = 2,
        fts_query_timeout_seconds: float = 2.0,
    ) -> None:
        self.corpus_path = Path(corpus_path)
        self.llm_client = llm_client
        self.model = str(model or getattr(llm_client, "default_model", "") or "")
        self.candidate_limit = max(1, int(candidate_limit))
        self.evidence_limit = max(1, min(int(evidence_limit), self.candidate_limit))
        self.timeout_seconds = float(timeout_seconds)
        self.planning_repetitions = max(1, min(int(planning_repetitions), 3))
        self.fts_query_timeout_seconds = max(0.05, float(fts_query_timeout_seconds))

    def answer(self, query: str, *, language: str = "") -> dict[str, Any]:
        if not self.corpus_path.exists():
            raise FileNotFoundError(f"corpus not found: {self.corpus_path}")
        question = str(query or "").strip()
        if not question:
            raise ValueError("query is required")
        started = time.monotonic()
        query_plan = self._plan_queries(question, language=language)
        atomic_answer = query_plan.get("answerShape") == "atomic"
        retrieval_started = time.monotonic()
        with sqlite3.connect(f"file:{self.corpus_path}?mode=ro", uri=True, timeout=30.0) as conn:
            conn.row_factory = sqlite3.Row
            schema = _detect_schema(conn)
            primary_candidates = _retrieve_candidates(
                conn,
                schema,
                query_plan["queries"],
                limit=self.candidate_limit,
                relation_pairs=query_plan.get("relationPairs"),
                alias_groups=query_plan.get("crossLanguageAliases"),
                query_timeout_seconds=self.fts_query_timeout_seconds,
            )
            dimension_queries = (
                []
                if atomic_answer
                else _round_robin_unique(
                    [
                        list(query_plan.get("answerDimensionQueries") or []),
                        list(query_plan.get("answerDimensionEvidenceQueries") or []),
                    ],
                    limit=12,
                )
            )
            dimension_candidates = (
                _retrieve_candidates(
                    conn,
                    schema,
                    dimension_queries,
                    limit=self.candidate_limit,
                    relation_pairs=[],
                    alias_groups=[],
                    query_timeout_seconds=self.fts_query_timeout_seconds,
                )
                if dimension_queries
                else []
            )
        retrieval_elapsed = time.monotonic() - retrieval_started
        if not primary_candidates and not dimension_candidates:
            answer_started = time.monotonic()
            answer = self._complete(direct_answer_messages(question, language=language)).strip()
            query_plan["resolvedAnswerDimensions"] = []
            elapsed = time.monotonic() - started
            return {
                "answer": answer,
                "queryPlan": query_plan,
                "corpusSchema": schema.name,
                "candidateCount": 0,
                "candidateIds": [],
                "selectedEvidence": [],
                "reranker": {
                    "status": "no_candidates_closed_book",
                    "selectedIds": [],
                    "reasons": {},
                },
                "modelMetadata": _model_metadata(self.llm_client, self.model),
                "timing": {
                    "retrievalSec": round(retrieval_elapsed, 3),
                    "writerSec": round(max(0.0, time.monotonic() - answer_started), 3),
                    "elapsedSec": round(elapsed, 3),
                },
            }
        selected, reranker = self._rerank(
            question,
            primary_candidates,
            query_plan=query_plan,
            language=language,
        )
        initially_selected_ids = {
            str(item.get("sourceId") or "") for item in selected
        }
        novel_dimension_candidates = [
            item
            for item in dimension_candidates
            if str(item.get("sourceId") or "") not in initially_selected_ids
        ]
        if novel_dimension_candidates:
            dimension_focus_queries = list(
                query_plan.get("answerDimensionEvidenceQueries")
                or query_plan.get("answerDimensionQueries")
                or []
            )
            dimension_focus = "\n".join(dimension_focus_queries) or question
            dimension_query_plan = {
                "queries": dimension_focus_queries,
                "answerDimensions": list(query_plan.get("answerDimensions") or []),
                "answerDimensionQueries": [],
                "answerDimensionEvidenceQueries": dimension_focus_queries,
                "candidateCanonicalForms": [],
                "crossLanguageAliases": [],
                "relationPairs": [],
            }
            dimension_selected, dimension_reranker = self._rerank(
                dimension_focus,
                novel_dimension_candidates,
                query_plan=dimension_query_plan,
                language=language,
            )
            selected = _merge_selection_by_source_id(
                selected,
                dimension_selected,
                limit=self.evidence_limit,
            )
            reranker["dimensionCoverageAudit"] = dimension_reranker
            reranker["selectedIds"] = [str(item.get("sourceId") or "") for item in selected]
            reranker["reasons"].update(dimension_reranker.get("reasons") or {})
        candidates = _merge_selection_by_source_id(
            primary_candidates,
            dimension_candidates,
            limit=len(primary_candidates) + len(dimension_candidates),
        )
        if not atomic_answer:
            with sqlite3.connect(
                f"file:{self.corpus_path}?mode=ro", uri=True, timeout=30.0
            ) as conn:
                conn.row_factory = sqlite3.Row
                reference_coverage_pool = _selected_reference_neighbors(
                    conn,
                    schema,
                    selected,
                    max_neighbors_per_seed=3,
                    query_timeout_seconds=self.fts_query_timeout_seconds,
                )
            coverage_pool = _coverage_candidate_pool(
                selected,
                reference_coverage_pool,
                candidates,
                limit=self.candidate_limit + self.evidence_limit,
            )
            if len(coverage_pool) > len(selected):
                coverage_selected, coverage_reranker = self._rerank(
                    question,
                    coverage_pool,
                    query_plan=query_plan,
                    language=language,
                    coverage_seed_ids=[str(item.get("sourceId") or "") for item in selected],
                )
                selected = _merge_selection_by_source_id(
                    coverage_selected,
                    selected,
                    limit=self.evidence_limit,
                )
                selected = _close_selected_reference_graph(
                    selected,
                    coverage_pool,
                    limit=self.evidence_limit,
                )
                reranker["coverageAudit"] = coverage_reranker
                reranker["selectedIds"] = [str(item.get("sourceId") or "") for item in selected]
                reranker["reasons"].update(coverage_reranker.get("reasons") or {})
            with sqlite3.connect(
                f"file:{self.corpus_path}?mode=ro", uri=True, timeout=30.0
            ) as conn:
                conn.row_factory = sqlite3.Row
                outgoing_reference_pool = _selected_outgoing_reference_neighbors(
                    conn,
                    schema,
                    selected,
                    max_neighbors_per_seed=3,
                )
            selected = _reserve_explicit_reference_neighbors(
                selected,
                outgoing_reference_pool,
                limit=self.evidence_limit,
                max_additions=3,
            )
            selected = _reserve_incoming_reference_neighbors(
                selected,
                candidates,
                limit=self.evidence_limit,
                max_additions=3,
            )
        reranker["selectedIds"] = [str(item.get("sourceId") or "") for item in selected]
        evidence = [
            _evidence_packet(
                item,
                index=index,
                query=question,
                query_plan=query_plan,
                selection_reason=str(
                    (reranker.get("reasons") or {}).get(str(item.get("sourceId") or "")) or ""
                ),
            )
            for index, item in enumerate(selected, start=1)
        ]
        resolved_answer_dimensions = (
            []
            if atomic_answer
            else self._resolve_answer_dimensions(
                question,
                evidence,
                proposed_dimensions=query_plan.get("answerDimensions") or [],
                language=language,
            )
        )
        query_plan["resolvedAnswerDimensions"] = resolved_answer_dimensions
        writer_query_plan = {
            **query_plan,
            "answerDimensions": resolved_answer_dimensions,
        }
        answer_started = time.monotonic()
        answer = self._write_answer(
            question,
            evidence,
            query_plan=writer_query_plan,
            language=language,
        )
        elapsed = time.monotonic() - started
        return {
            "answer": answer,
            "queryPlan": query_plan,
            "corpusSchema": schema.name,
            "candidateCount": len(candidates),
            "candidateIds": [str(item.get("sourceId") or "") for item in candidates],
            "selectedEvidence": evidence,
            "reranker": reranker,
            "modelMetadata": _model_metadata(self.llm_client, self.model),
            "timing": {
                "retrievalSec": round(retrieval_elapsed, 3),
                "writerSec": round(max(0.0, time.monotonic() - answer_started), 3),
                "elapsedSec": round(elapsed, 3),
            },
        }

    def _plan_queries(self, query: str, *, language: str) -> dict[str, Any]:
        planner_schema = (
            '{"answerShape":"atomic|composite","queries":["..."],'
            '"anonymizedStructureQueries":["..."],'
            '"concreteInstanceQueries":["..."],'
            '"answerValueMarkers":["..."],'
            '"candidateCanonicalForms":["..."],'
            '"answerDimensions":["..."],'
            '"coverageFrame":{"authorizationOrScope":"...","procedure":"...",'
            '"operativeDownstreamConsequence":"...","factSpecificConclusion":"..."},'
            '"answerDimensionQueries":["..."],'
            '"crossLanguageAliases":[{"term":"...","aliases":["..."]}],'
            '"relationPairs":[["concept one","concept two"]]}'
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "You are the query-planning stage of a general-purpose evidence engine. "
                    "answerShape is required. Use atomic only when the requested final answer is one compact "
                    "choice, label, name, number, date, identifier, or short value, even if selecting it requires "
                    "comparing evidence. Use composite when the user requests an explanation, analysis, multiple "
                    "material issues, procedures, consequences, or an applied conclusion. This is an answer-structure "
                    "classification only; never infer it from the subject area, corpus, benchmark identity, or "
                    "application label. "
                    "Return JSON only. Produce up to four concise semantic retrieval queries, each using "
                    "two to six high-information terms. Put rare names and identifiers first; omit answer-format "
                    "instructions, option labels, and boilerplate. Preserve the user's entities, relations, "
                    "constraints, and requested distinction. When useful for identifying an exact named concept, "
                    "include canonical terminology, aliases, and original-script spellings. For abbreviations or "
                    "foreign-language terms, include an everyday local-language name used in the likely corpus, "
                    "not only a formal expansion or transliteration. Do not answer. "
                    "anonymizedStructureQueries is required. When a question contains proper names, named places, "
                    "brands, organizations, or named events that a source may mask or anonymize, propose up to four "
                    "additional queries that replace those names with their semantic roles or types while preserving "
                    "the relation, action, constraint, and requested attribute. Do not invent the requested answer "
                    "value. The first anonymizedStructureQueries item must be a lossless masking abstraction: remove "
                    "only proper-name and named-place spans, while keeping the user's non-name role, relation, action, "
                    "and requested-attribute wording. Do not insert bracketed placeholders or invented replacement "
                    "labels. Normalize retained grammatical inflections to corpus search headwords without changing "
                    "their lexical meaning. Put synonym-based alternatives only after it. "
                    "Use an empty list when no masking-resistant structural query is useful. These are "
                    "independent recall hypotheses, not final answers. "
                    "concreteInstanceQueries is required. When the question names an umbrella category but the "
                    "likely corpus may describe common concrete subtypes rather than that umbrella label, propose "
                    "up to four concise queries using plausible common subtypes. Preserve the user's relation, "
                    "action, constraints, and requested attribute. Do not invent the requested answer value, and "
                    "do not specialize a question that is already concrete. Use an empty list when subtype "
                    "expansion would not improve recall. These are independent recall hypotheses, not answers. "
                    "answerValueMarkers is required: propose up to four short literal surface markers that may "
                    "directly surround the requested value in the likely corpus, such as a unit, field label, date "
                    "suffix, or measurement notation. Include only the marker without the concrete answer value. "
                    "Order markers from most directly value-bearing to least. Use an empty list when no compact "
                    "value marker is useful. "
                    "If the question itself describes a term, name, or identifier, also propose complete canonical "
                    "response forms under candidateCanonicalForms, preserving parenthetical original script. These "
                    "are search hypotheses, not final answers. crossLanguageAliases is required: list every foreign "
                    "term or abbreviation that could be expressed differently in the likely corpus language, or an "
                    "empty list if none. relationPairs is also required: propose up to four pairs of concepts whose "
                    "co-occurrence most distinguishes a matching record. For each broad category, include at least "
                    "one commonly named concrete instance in a pair when reasonable; use an empty list if none. "
                    "Resolve a potentially ambiguous surface word from the full relation expressed by the question. "
                    "Do not enumerate unrelated dictionary senses merely because a word is polysemous. Include more "
                    "than one sense only when the complete question remains genuinely underdetermined. "
                    "answerDimensions is required: list up to five concise material issues a complete answer must "
                    "resolve. These are coverage goals, not factual claims. When a question identifies or evaluates "
                    "a concrete action or process, include its authority or scope, required procedure, operative "
                    "downstream consequence of a violation, and a fact-specific conclusion when material. Do not put "
                    "unrelated alternate senses in answerDimensions. answerDimensionQueries is required: propose up "
                    "to four concise retrieval queries aimed at finding evidence for material answerDimensions that "
                    "the ordinary identification queries may miss. Keep the question's core subject, relation, and "
                    "constraints in each query while adding the dimension to be supported. Do not encode an answer "
                    "or assume an outcome. Use an empty list when the ordinary queries already cover every material "
                    "dimension. coverageFrame is required and each value is a concise coverage goal, not an answer. "
                    "For a question about a concrete action or process, fill all four fields: the governing authority "
                    "or scope, required procedure, the operative downstream consequence of a violation, and a "
                    "fact-specific conclusion. The downstream field must ask what actually happens, not merely whether "
                    "a problem arises. Use an empty string for a field only when it is genuinely inapplicable. Schema: "
                    + planner_schema
                    + "."
                ),
            },
            {
                "role": "user",
                "content": f"Answer language hint: {language or 'unspecified'}\nQuestion:\n{query}",
            },
        ]
        parsed_plans: list[dict[str, Any]] = []
        for _ in range(self.planning_repetitions):
            parsed = _json_object(self._complete(messages))
            parsed_plans.append(parsed)
            if str(parsed.get("answerShape") or "").strip().lower() == "atomic":
                break
        planned_queries: list[str] = []
        answer_shapes: list[str] = []
        anonymized_query_groups: list[list[str]] = []
        concrete_query_groups: list[list[str]] = []
        value_marker_groups: list[list[str]] = []
        canonical_forms: list[str] = []
        free_answer_dimensions: list[str] = []
        coverage_fields = (
            "authorizationOrScope",
            "procedure",
            "operativeDownstreamConsequence",
            "factSpecificConclusion",
        )
        coverage_frame_values: dict[str, list[str]] = {
            field: [] for field in coverage_fields
        }
        answer_dimension_query_groups: list[list[str]] = []
        alias_groups: list[dict[str, Any]] = []
        relation_pairs: list[list[str]] = []
        valid_plans = 0
        for parsed in parsed_plans:
            proposed_shape = str(parsed.get("answerShape") or "").strip().lower()
            if proposed_shape in {"atomic", "composite"}:
                answer_shapes.append(proposed_shape)
            proposed = parsed.get("queries") if isinstance(parsed, dict) else None
            proposed_anonymized = (
                parsed.get("anonymizedStructureQueries") if isinstance(parsed, dict) else None
            )
            proposed_concrete = (
                parsed.get("concreteInstanceQueries") if isinstance(parsed, dict) else None
            )
            proposed_value_markers = (
                parsed.get("answerValueMarkers") if isinstance(parsed, dict) else None
            )
            proposed_forms = parsed.get("candidateCanonicalForms") if isinstance(parsed, dict) else None
            proposed_dimensions = parsed.get("answerDimensions") if isinstance(parsed, dict) else None
            proposed_coverage_frame = parsed.get("coverageFrame") if isinstance(parsed, dict) else None
            proposed_dimension_queries = (
                parsed.get("answerDimensionQueries") if isinstance(parsed, dict) else None
            )
            proposed_aliases = parsed.get("crossLanguageAliases") if isinstance(parsed, dict) else None
            proposed_pairs = parsed.get("relationPairs") if isinstance(parsed, dict) else None
            if isinstance(proposed, list):
                valid_plans += 1
                for value in proposed:
                    cleaned = _clean_query(value)
                    if cleaned and cleaned not in planned_queries:
                        planned_queries.append(cleaned)
                    if len(planned_queries) >= 6:
                        break
            if isinstance(proposed_anonymized, list):
                local_anonymized: list[str] = []
                for value in proposed_anonymized:
                    cleaned = _clean_anonymized_query(value)
                    if cleaned and cleaned not in local_anonymized:
                        local_anonymized.append(cleaned)
                    if len(local_anonymized) >= 4:
                        break
                if local_anonymized:
                    anonymized_query_groups.append(local_anonymized)
            if isinstance(proposed_concrete, list):
                local_concrete: list[str] = []
                for value in proposed_concrete:
                    cleaned = _clean_query(value)
                    if cleaned and cleaned not in local_concrete:
                        local_concrete.append(cleaned)
                    if len(local_concrete) >= 4:
                        break
                if local_concrete:
                    concrete_query_groups.append(local_concrete)
            if isinstance(proposed_value_markers, list):
                local_markers: list[str] = []
                for value in proposed_value_markers:
                    cleaned = _clean_query(value)
                    if cleaned and cleaned not in local_markers:
                        local_markers.append(cleaned)
                    if len(local_markers) >= 4:
                        break
                if local_markers:
                    value_marker_groups.append(local_markers)
            if isinstance(proposed_forms, list):
                for value in proposed_forms:
                    cleaned = _clean_query(value)
                    if cleaned and cleaned not in canonical_forms:
                        canonical_forms.append(cleaned)
                    if len(canonical_forms) >= 8:
                        break
            if isinstance(proposed_dimensions, list):
                for value in proposed_dimensions:
                    cleaned = _clean_query(value)
                    if cleaned and cleaned not in free_answer_dimensions:
                        free_answer_dimensions.append(cleaned)
                    if len(free_answer_dimensions) >= 8:
                        break
            if isinstance(proposed_coverage_frame, dict):
                for field in coverage_fields:
                    cleaned = _clean_query(proposed_coverage_frame.get(field))
                    if cleaned and cleaned not in coverage_frame_values[field]:
                        coverage_frame_values[field].append(cleaned)
            if isinstance(proposed_dimension_queries, list):
                local_dimension_queries: list[str] = []
                for value in proposed_dimension_queries:
                    cleaned = _clean_query(value)
                    if cleaned and cleaned not in local_dimension_queries:
                        local_dimension_queries.append(cleaned)
                    if len(local_dimension_queries) >= 4:
                        break
                if local_dimension_queries:
                    answer_dimension_query_groups.append(local_dimension_queries)
            if isinstance(proposed_aliases, list):
                for value in proposed_aliases:
                    if not isinstance(value, dict):
                        continue
                    term = _clean_query(value.get("term"))
                    aliases = []
                    for alias in value.get("aliases") if isinstance(value.get("aliases"), list) else []:
                        cleaned = _clean_query(alias)
                        if cleaned and cleaned not in aliases:
                            aliases.append(cleaned)
                        if len(aliases) >= 4:
                            break
                    if not term or not aliases:
                        continue
                    existing = next(
                        (item for item in alias_groups if str(item.get("term") or "").casefold() == term.casefold()),
                        None,
                    )
                    if existing is None and len(alias_groups) < 6:
                        alias_groups.append({"term": term, "aliases": list(aliases)})
                    elif existing is not None:
                        for alias in aliases:
                            if alias not in existing["aliases"] and len(existing["aliases"]) < 6:
                                existing["aliases"].append(alias)
            if isinstance(proposed_pairs, list):
                for value in proposed_pairs:
                    if not isinstance(value, list) or len(value) != 2:
                        continue
                    pair = [_clean_query(item) for item in value]
                    if all(pair) and pair not in relation_pairs and len(relation_pairs) < 6:
                        relation_pairs.append(pair)
        anonymized_structure_queries = _round_robin_unique(
            anonymized_query_groups,
            limit=4,
        )
        concrete_instance_queries = _round_robin_unique(
            concrete_query_groups,
            limit=4,
        )
        answer_value_markers = _round_robin_unique(
            value_marker_groups,
            limit=4,
        )
        answer_dimension_queries = _round_robin_unique(
            answer_dimension_query_groups,
            limit=4,
        )
        coverage_frame = {
            field: (coverage_frame_values[field][0] if coverage_frame_values[field] else "")
            for field in coverage_fields
        }
        answer_dimensions: list[str] = []
        for value in [*coverage_frame.values(), *free_answer_dimensions]:
            if value and value not in answer_dimensions:
                answer_dimensions.append(value)
            if len(answer_dimensions) >= 8:
                break
        answer_dimension_evidence_queries = list(answer_dimensions[:8])
        answer_shape = (
            "atomic"
            if answer_shapes and all(value == "atomic" for value in answer_shapes)
            else "composite"
        )
        queries = [query]
        for value in [
            *anonymized_structure_queries,
            *concrete_instance_queries,
            *planned_queries,
        ]:
            if value not in queries:
                queries.append(value)
            if len(queries) >= 11:
                break
        for group in alias_groups:
            alias_query = _clean_query(" ".join([group["term"], *group["aliases"]]))
            if alias_query and alias_query not in queries and len(queries) < 12:
                queries.append(alias_query)
        return {
            "status": "completed" if valid_plans else "invalid_json_fallback",
            "planningRepetitions": len(parsed_plans),
            "answerShape": answer_shape,
            "queries": queries,
            "anonymizedStructureQueries": anonymized_structure_queries,
            "concreteInstanceQueries": concrete_instance_queries,
            "answerValueMarkers": answer_value_markers,
            "candidateCanonicalForms": canonical_forms,
            "answerDimensions": answer_dimensions,
            "coverageFrame": coverage_frame,
            "answerDimensionQueries": answer_dimension_queries,
            "answerDimensionEvidenceQueries": answer_dimension_evidence_queries,
            "crossLanguageAliases": alias_groups,
            "relationPairs": relation_pairs,
        }

    def _rerank(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        *,
        query_plan: dict[str, Any],
        language: str,
        coverage_seed_ids: list[str] | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        passage_queries = _passage_queries(query, query_plan)
        blocks = []
        for item in candidates:
            connections = []
            for retrieval_rank in item.get("retrievalRanks") or []:
                if (
                    retrieval_rank.get("source") == "reference_neighbor"
                    and retrieval_rank.get("isCrossReference")
                ):
                    connection = {
                        "reference": str(retrieval_rank.get("reference") or ""),
                        "depth": int(retrieval_rank.get("depth") or 0),
                    }
                    if connection not in connections:
                        connections.append(connection)
            blocks.append(
                json.dumps(
                    {
                        "id": item.get("sourceId", ""),
                        "referenceId": item.get("referenceId", ""),
                        "title": item.get("title", ""),
                        "citation": item.get("citation", ""),
                        "connections": connections,
                        "excerpts": _best_query_windows(
                            str(item.get("fullText") or item.get("searchExcerpt") or ""),
                            passage_queries,
                            max_chars=900,
                            max_windows=2,
                        ),
                    },
                    ensure_ascii=False,
                )
            )
        coverage_instruction = ""
        if coverage_seed_ids:
            coverage_instruction = (
                "This is a connected-record coverage audit. Retain already selected records that remain among "
                "the most material, and add only "
                "connected candidates that are relevant to the question and represent a materially distinct "
                "stage, proceeding, outcome, or primary account of the same concrete event. If the evidence limit "
                "is full, replace a less relevant generic record with the materially distinct connected record. "
                "Already selected "
                f"IDs: {json.dumps(coverage_seed_ids, ensure_ascii=False)}. "
            )
        messages = [
            {
                "role": "system",
                "content": (
                    "You are the evidence-selection stage of a general-purpose engine. Select only sources "
                    "that materially help answer the question or resolve an important ambiguity. Judge semantic "
                    "fit, not word overlap. Prefer records whose concrete entities, actions, relations, dates, or "
                    "procedural posture directly match the question over generic topical discussions. Collectively "
                    "cover the material subquestions and prefer primary records when available. When connected "
                    "primary records concern the same event but represent distinct stages, proceedings, or outcomes, "
                    "preserve every materially distinct record needed for a complete answer. Return JSON only, "
                    "ordered best first. "
                    + coverage_instruction
                    +
                    f'Select at most {self.evidence_limit}. Schema: '
                    '{"selected":[{"id":"source id","reason":"brief reason"}]}.'
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Answer language hint: {language or 'unspecified'}\nQuestion:\n{query}\n\n"
                    "Candidate records (JSONL):\n"
                    + ("\n".join(blocks) if blocks else "(none)")
                ),
            },
        ]
        raw = self._complete(messages)
        parsed = _json_object(raw)
        selected_items = parsed.get("selected") if isinstance(parsed, dict) else None
        by_id = {str(item.get("sourceId") or ""): item for item in candidates}
        selected: list[dict[str, Any]] = []
        reasons: dict[str, str] = {}
        if isinstance(selected_items, list):
            for value in selected_items:
                if isinstance(value, dict):
                    source_id = str(value.get("id") or "").strip()
                    reason = str(value.get("reason") or "").strip()
                else:
                    source_id = str(value or "").strip()
                    reason = ""
                if source_id in by_id and by_id[source_id] not in selected:
                    selected.append(by_id[source_id])
                    reasons[source_id] = reason
                if len(selected) >= self.evidence_limit:
                    break
        valid_json = isinstance(selected_items, list)
        if not selected:
            selected = candidates[: self.evidence_limit]
        return selected, {
            "status": "completed" if valid_json else "invalid_json_fallback",
            "selectedIds": [str(item.get("sourceId") or "") for item in selected],
            "reasons": reasons,
        }

    def _resolve_answer_dimensions(
        self,
        query: str,
        evidence: list[dict[str, Any]],
        *,
        proposed_dimensions: list[Any],
        language: str,
    ) -> list[str]:
        proposed = [
            _clean_query(value)
            for value in proposed_dimensions
            if _clean_query(value)
        ][:8]
        if not proposed:
            return []
        evidence_blocks = [
            json.dumps(
                {
                    "sourceId": item.get("sourceId", ""),
                    "title": item.get("title", ""),
                    "citation": item.get("citation", ""),
                    "exactQuote": item.get("exactQuote", ""),
                    "selectionReason": item.get("selectionReason", ""),
                },
                ensure_ascii=False,
            )
            for item in evidence
        ]
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a coverage-resolution stage of a general-purpose evidence engine. The evidence sources "
                    "have already been selected and must not be reselected, ranked, added, or removed. Return JSON "
                    "only. Resolve the proposed answer dimensions against the whole question and selected evidence. "
                    "Keep every dimension material to a complete answer, including authority or scope, procedure, an "
                    "operative downstream consequence, and a fact-specific conclusion when applicable. A dimension "
                    "may require cautious general reasoning and need not be a verbatim source heading, but it must be "
                    "compatible with the question's contextually dominant sense. Drop dimensions that belong to an "
                    "incompatible alternate sense unsupported by the selected evidence. Once the evidence resolves an "
                    "ambiguity, do not keep a meta-dimension about choosing, comparing, or negating discarded senses. "
                    "Omit it entirely so the final answer addresses the supported sense without naming rejected "
                    "senses. Do not answer the question or make factual claims. Schema: "
                    '{"resolvedAnswerDimensions":["material coverage goal"]}.'
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Answer language hint: {language or 'unspecified'}\nQuestion:\n{query}\n\n"
                    "Proposed answer dimensions (coverage hypotheses, not evidence):\n"
                    + json.dumps(proposed, ensure_ascii=False)
                    + "\n\nSelected evidence packets (JSONL):\n"
                    + ("\n".join(evidence_blocks) if evidence_blocks else "(none)")
                ),
            },
        ]
        parsed = _json_object(self._complete(messages))
        resolved_items = parsed.get("resolvedAnswerDimensions") if isinstance(parsed, dict) else None
        resolved: list[str] = []
        if isinstance(resolved_items, list):
            for value in resolved_items:
                cleaned = _clean_query(value)
                if cleaned and cleaned not in resolved:
                    resolved.append(cleaned)
                if len(resolved) >= 8:
                    break
        return resolved

    def _analyze_evidence_roles(
        self,
        query: str,
        evidence: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        messages = [
            {
                "role": "system",
                "content": (
                    "Analyze the distinct supported role of each selected evidence record before answer writing. "
                    "Use only the supplied excerpts. For each record, separate: its direct issue and outcome; any "
                    "excerpt-supported operative proposition such as a rule, implementation constraint, treatment "
                    "of purpose or intent, validity condition, outcome, or remedy; how that proposition applies to "
                    "the user's question; factual contribution; and the boundary of what the record did not decide. "
                    "Keep event facts strictly separate from operative propositions. What a warrant listed, what a "
                    "party planned, or what happened belongs only in factContribution and is never by itself an "
                    "excerptSupportedOperativeProposition. That operative field must state a court's normative or "
                    "adjudicative treatment: what is permitted, prohibited, required, legally relevant, proven or not "
                    "proven, and the resulting disposition. Inspect the entire excerpt for such reasoning even when "
                    "it concerns a different direct issue, including implementation limits, purpose or intent, validity, "
                    "outcome, or remedy. directIssueAndOutcome must name the actual issue and disposition supported by "
                    "the excerpt, not merely describe the event. "
                    "A record may materially inform the question even when its direct issue differs. In that case, "
                    "do not stop at saying it shares facts or did not decide the exact question: identify and apply "
                    "the distinct supported proposition, then state the boundary. Do not invent a proposition when "
                    "the excerpt supplies only background. crossRecordEntityContinuity must state any supported "
                    "mapping between differently masked labels across supplied records of the same event, using "
                    "the actor's role, acts, chronology, relationships, and procedural linkage. Different letters "
                    "alone do not negate continuity; leave the field empty when the event facts do not support it. "
                    "answerBearingExactSpans must list only the smallest self-contained continuous source substrings "
                    "that directly answer an explicitly requested scalar, name, "
                    "identifier, or other compact value. Copy each substring verbatim, including labels, "
                    "parentheses, qualifiers, punctuation, and units. When an entity attribute appears in a labeled "
                    "parenthetical form, include the entity label and the entire parenthetical; the bare value alone "
                    "is not self-contained. Use an empty list when the record does not "
                    "directly supply such an answer. Never include a similarly shaped fact from an unrelated "
                    "record. Return JSON only with schema "
                    '{"recordRoles":[{"sourceId":"...","referenceId":"...",'
                    '"materialToAnswer":true,"sameEventOrProcess":true,'
                    '"directIssueAndOutcome":"...",'
                    '"excerptSupportedOperativeProposition":"...",'
                    '"questionApplication":"...","factContribution":"...",'
                    '"holdingBoundary":"...","crossRecordEntityContinuity":"...",'
                    '"answerBearingExactSpans":["verbatim span"]}]}. '
                    "Include every supplied record."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Question:\n{query}\n\nSelected evidence packets (JSONL):\n"
                    + "\n".join(
                        json.dumps(
                            {
                                "sourceId": item.get("sourceId"),
                                "referenceId": item.get("referenceId"),
                                "title": item.get("title"),
                                "citation": item.get("citation"),
                                "exactQuote": item.get("exactQuote"),
                                "selectionReason": item.get("selectionReason"),
                                "connectedReferences": item.get("connectedReferences"),
                            },
                            ensure_ascii=False,
                        )
                        for item in evidence
                    )
                ),
            },
        ]
        payload = _json_object(str(self._complete(messages) or ""))
        initial_roles = [
            dict(item)
            for item in payload.get("recordRoles") or []
            if isinstance(item, dict) and str(item.get("sourceId") or "")
        ]
        same_event_ids = {
            str(item.get("sourceId") or "")
            for item in initial_roles
            if item.get("sameEventOrProcess") is True
        }
        focused_evidence = [
            item
            for item in evidence
            if str(item.get("sourceId") or "") in same_event_ids
        ]
        if not focused_evidence:
            return initial_roles
        focused_messages = [
            {
                "role": "system",
                "content": (
                    "Deepen the evidence-role analysis for records identified as the same event or process. Correct "
                    "any field that confused event facts with a judicial or adjudicative proposition. Warrant text, "
                    "plans, and execution history belong only in factContribution. Inspect each entire excerpt for "
                    "the court's actual legal standard, treatment of purpose or intent, implementation constraint, "
                    "validity judgment, disposition, outcome, or remedy, including reasoning on a different direct "
                    "issue. excerptSupportedOperativeProposition must contain that normative or adjudicative treatment "
                    "or be empty if none exists. directIssueAndOutcome must include the actual disposition when the "
                    "excerpt supports one and the decisive excerpt-supported reason for that disposition. When the "
                    "direct issue differs, questionApplication must apply the court's reasoning to the relevant distinct "
                    "dimension of the questioned process, such as its method, purpose or intent, validity, outcome, or "
                    "remedy; it must not merely repeat warrant text or event facts. holdingBoundary prevents overstatement. "
                    "Reassess masked-label continuity across these same-event records from roles, acts, chronology, "
                    "relationships, and procedural linkage; do not treat different letters alone as uncertainty. "
                    "Preserve answerBearingExactSpans only when each span is a verbatim continuous substring of that "
                    "record's excerpt and directly answers the question; otherwise return an empty list. Return JSON only "
                    "with the same recordRoles schema and include every focused record."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Question:\n{query}\n\nInitial role analysis:\n"
                    + json.dumps(initial_roles, ensure_ascii=False)
                    + "\n\nFocused evidence packets (JSONL):\n"
                    + "\n".join(
                        json.dumps(
                            {
                                "sourceId": item.get("sourceId"),
                                "referenceId": item.get("referenceId"),
                                "title": item.get("title"),
                                "citation": item.get("citation"),
                                "exactQuote": item.get("exactQuote"),
                                "selectionReason": item.get("selectionReason"),
                                "connectedReferences": item.get("connectedReferences"),
                            },
                            ensure_ascii=False,
                        )
                        for item in focused_evidence
                    )
                ),
            },
        ]
        focused_payload = _json_object(str(self._complete(focused_messages) or ""))
        focused_roles = [
            dict(item)
            for item in focused_payload.get("recordRoles") or []
            if isinstance(item, dict) and str(item.get("sourceId") or "")
        ]
        merged_by_id: dict[str, dict[str, Any]] = {}
        ordered_ids: list[str] = []
        for item in [*initial_roles, *focused_roles]:
            source_id = str(item.get("sourceId") or "")
            if source_id not in merged_by_id:
                merged_by_id[source_id] = {}
                ordered_ids.append(source_id)
            merged_by_id[source_id].update(
                {
                    str(key): value
                    for key, value in item.items()
                    if value is not None and (not isinstance(value, str) or value.strip())
                }
            )
        return [merged_by_id[source_id] for source_id in ordered_ids]

    def _write_answer(
        self,
        query: str,
        evidence: list[dict[str, Any]],
        *,
        query_plan: dict[str, Any],
        language: str,
    ) -> str:
        atomic_answer = query_plan.get("answerShape") == "atomic"
        connected_references = {
            str(reference)
            for item in evidence
            for reference in item.get("connectedReferences") or []
            if str(reference)
        }
        connected_items = [] if atomic_answer else [
            item
            for item in evidence
            if str(item.get("referenceId") or "")
            and (
                item.get("connectedReferences")
                or str(item.get("referenceId") or "") in connected_references
            )
        ]
        evidence_role_records = (
            self._analyze_evidence_roles(query, evidence)
            if connected_items
            else []
        )
        required_verbatim_spans = _grounded_answer_spans(
            evidence_role_records,
            evidence,
        )
        _prioritize_grounded_answer_windows(evidence_role_records, evidence)
        canonical_forms = [
            str(value).strip()
            for value in query_plan.get("candidateCanonicalForms") or []
            if str(value).strip()
        ]
        answer_dimensions = [
            str(value).strip()
            for value in query_plan.get("answerDimensions") or []
            if str(value).strip()
        ]
        answer_hypotheses = {
            "candidateCanonicalForms": canonical_forms,
            "answerDimensions": answer_dimensions,
        }
        evidence_blocks = [
            json.dumps(
                {
                    "label": item["label"],
                    "sourceId": item["sourceId"],
                    "title": item["title"],
                    "citation": item["citation"],
                    "exactQuote": item["exactQuote"],
                    "selectionReason": item["selectionReason"],
                    "connectedReferences": item["connectedReferences"],
                },
                ensure_ascii=False,
            )
            for item in evidence
        ]
        messages = [
            {
                "role": "system",
                "content": (
                    "You are the final writer of a general-purpose evidence engine. Answer the user's actual "
                    "question directly and obey any output format requested in it. Use supplied evidence only "
                    "when it genuinely supports the statement. Do not force irrelevant evidence. When making "
                    "a source-grounded claim, cite its label such as [S1]. Never invent a source or quote. "
                    "If the evidence is insufficient, use sound general reasoning and state the uncertainty. "
                    "The search-plan terms and candidate canonical forms are hypotheses, not evidence. When the "
                    "requested answer is a term, "
                    "name, identifier, or exact string, preserve the most authoritative canonical spelling and "
                    "any parenthetical original-script form available in the evidence or search plan; do not "
                    "silently simplify that form. If a candidate canonical form directly matches the definition "
                    "in the question and nothing contradicts it, return that complete form exactly, including its "
                    "parenthetical original script. "
                    "When a primary packet explicitly gives the requested compact fact in a labeled, parenthetical, "
                    "or unit-bearing form, reproduce that exact source wording in the direct answer before "
                    "paraphrasing it. Preserve masked labels, qualifiers, and units. Anonymized labels may differ "
                    "across records; resolve continuity from roles and event facts rather than requiring the same "
                    "letter, and never equate unrelated records merely because a label matches. When the grounded "
                    "role analysis establishes cross-record entity continuity from distinctive roles, acts, chronology, "
                    "relationships, and procedural linkage, apply a compact fact to that continuous subject; do not "
                    "downgrade it merely because a later stage uses a different masked letter. "
                    "When evidence packets are identifiable primary records, name "
                    "each materially used record by its supplied title or citation and explain its distinct role; "
                    "do not replace an available identifying citation with only a packet label. If multiple selected "
                    "primary records concern the same factual event, identify and compare every such record instead "
                    "of silently collapsing them into one. The final answer must explicitly include a supplied title "
                    "or citation for every selected primary record concerning that event. When the user asks to find "
                    "or identify records, do not stop at a list: explain each selected record's supported rule or "
                    "procedural significance, apply it to the described facts, and answer the underlying issue when "
                    "the evidence permits. For connected records, distinguish an actual holding or rule from factual "
                    "background merely recited by that record; do not imply that every stage decided the same issue. "
                    "State each record's distinct procedural posture or outcome and only the rule its supplied excerpts "
                    "support. When a same-event record's main issue differs, do not dismiss it as mere background if "
                    "its excerpt contains an applicable rule, procedural constraint, treatment of the questioned "
                    "conduct, or outcome. State that supported proposition, apply it to the question, and then state "
                    "the holding boundary. Merely saying that a record shared the facts or did not decide the exact "
                    "question is not substantive use. A complete explanatory answer separates scope, procedure, and downstream consequences "
                    "when those are material, and gives a fact-dependent conclusion. If a source-identification "
                    "question describes a concrete action or process, always add a distinct analysis of when that "
                    "conduct is authorized or unauthorized, the procedural constraints, and the consequence of a "
                    "violation. State the operative downstream effect; a vague statement that a problem or issue may "
                    "arise is not a complete consequence analysis. Clearly label sound general reasoning instead of "
                    "misattributing it to a source. Resolve an ambiguous surface word from the whole question and "
                    "selected evidence. Do not enumerate alternate dictionary senses unless the question explicitly "
                    "asks for them or the selected evidence establishes a genuine, material ambiguity. Once one "
                    "coherent sense is supported and another is not, omit the unsupported sense entirely. Do not name "
                    "or negate a rejected sense merely to explain the disambiguation; answer the supported sense "
                    "directly."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Answer language: {language or 'same as question'}\nQuestion:\n{query}\n\n"
                    "Answer-coverage hypotheses (not evidence):\n"
                    + json.dumps(answer_hypotheses, ensure_ascii=False)
                    + "\n\n"
                    "Evidence-role analysis (grounded interpretation to verify against the packets):\n"
                    + json.dumps(evidence_role_records, ensure_ascii=False)
                    + "\n\n"
                    "Grounded verbatim answer spans (must appear literally when nonempty):\n"
                    + json.dumps(required_verbatim_spans, ensure_ascii=False)
                    + "\n\n"
                    "Evidence packets (JSONL):\n"
                    + ("\n".join(evidence_blocks) if evidence_blocks else "(none retrieved)")
                ),
            },
        ]
        draft = str(self._complete(messages) or "").strip()
        if not connected_items:
            return _ensure_verbatim_spans(draft, required_verbatim_spans)
        audit_items = [item for item in evidence if str(item.get("referenceId") or "")]
        connected_source_ids = {str(item.get("sourceId") or "") for item in connected_items}
        repair_messages = [
            {
                "role": "system",
                "content": (
                    "Perform a final semantic coverage audit of an evidence-grounded draft. The supplied packets "
                    "are material members of an explicit connected-record graph. If the draft is already complete, "
                    "return it unchanged. Otherwise revise it. For explanatory or source-identification answers, "
                    "do not merely list records: identify each connected record, explain only the rule, procedural "
                    "significance, or outcome supported by its excerpt, and apply that significance to the described "
                    "facts. Distinguish a record's actual holding from factual background it merely recites; never "
                    "pretend all stages decided the same issue. Analyze the underlying disputed conduct by separating "
                    "material scope or authority, procedure, and downstream consequences, and give a fact-dependent "
                    "conclusion. If a source-identification question describes a concrete action or process, the final "
                    "answer must include a distinct analysis of when that conduct is authorized or unauthorized, the "
                    "procedural constraints, and the operative consequence of a violation; do not use a vague phrase "
                    "such as merely saying that a problem or issue may arise. A record list alone is incomplete. "
                    "Sound general reasoning may fill an unresolved issue only if clearly separated from "
                    "what a record itself held. Do not end with only a recommendation to inspect more sources. Never "
                    "invent facts beyond the packets. Treat supplied answerDimensions as coverage goals rather than "
                    "evidence, and resolve every applicable dimension in the answer. Return one dimensionCoverage "
                    "entry for every supplied answerDimension, preserving the dimension text exactly. Its "
                    "answerContribution must be a concrete, final-answer-ready proposition that directly resolves "
                    "that dimension rather than restating the question or merely saying that a supplied record did "
                    "not decide it. When the packets leave the dimension unresolved, use clearly labeled sound "
                    "general reasoning; for a consequence, remedy, or result dimension, state the operative effect. "
                    "If the question requires a "
                    "constrained exact output, preserve "
                    "that output contract and do not add commentary. The answer field must literally contain every "
                    "requested compact fact that a primary packet states in a labeled, parenthetical, or unit-bearing "
                    "form; preserve that exact source wording, including its masked label, qualifier, and unit, "
                    "instead of paraphrasing it away. Anonymized labels may differ across records, so assess identity "
                    "from roles and event continuity without equating unrelated records merely because a label matches. "
                    "Honor a supported crossRecordEntityContinuity mapping and do not turn a grounded compact fact "
                    "into uncertainty merely because the mapped records use different masked letters. "
                    "The answer field must literally contain every "
                    "graph-connected packet's referenceId when the output is explanatory. Semantically assess every "
                    "selected packet: materialToAnswer must be true when it concerns the same event or process as the "
                    "question, supplies a distinct rule or procedure used in the answer, or supports a material "
                    "conclusion. sameEventOrProcess must be true for a record that directly describes the questioned "
                    "event or process even when the record does not cite another record by identifier. Every packet "
                    "marked materialToAnswer or sameEventOrProcess must be identified and substantively used in the "
                    "answer. For an identifiable primary record, proceduralPostureOrOutcome must state the distinct "
                    "stage, result, and direct issue supported by the packet; a generic label such as merely saying "
                    "that it is an appeal or related record is insufficient. questionCoverage must separately resolve "
                    "the questioned conduct's authorization or scope, required procedure, operative downstream "
                    "consequence of a violation, and fact-specific conclusion. The downstream field must state what "
                    "actually happens; a vague statement that an issue may arise is insufficient. Use an empty string "
                    "only when a dimension is genuinely inapplicable. When a same-event record directly decides a "
                    "different issue, inspect its excerpt for a rule, procedural constraint, treatment of the conduct, "
                    "or outcome that materially informs the question. If one exists, state and apply it before stating "
                    "the holding boundary; merely calling the record factual background is not substantive coverage. "
                    "For every material record, excerptSupportedOperativeProposition must state the specific supported "
                    "rule, constraint, treatment, or outcome that does work in the answer, and questionApplication must "
                    "apply that proposition to the user's conduct. Neither field may merely repeat that the record shares "
                    "facts or did not decide the exact question. A record may materially constrain a process through its "
                    "treatment of authorization, implementation, purpose or intent, validity, outcome, or remedy even "
                    "when its direct issue differs; preserve the direct-issue boundary separately. "
                    "Return JSON only with schema "
                    '{"outputMode":"explanatory|constrained_exact","answer":"final answer",'
                    '"recordCoverage":[{"sourceId":"...","referenceId":"...",'
                    '"materialToAnswer":true,"sameEventOrProcess":true,"supportedRole":"...",'
                    '"excerptSupportedOperativeProposition":"...","questionApplication":"...",'
                    '"factApplication":"...","proceduralPostureOrOutcome":"...",'
                    '"holdingBoundary":"..."}],"questionCoverage":{'
                    '"authorizationOrScope":"...","procedure":"...",'
                    '"operativeDownstreamConsequence":"...","factSpecificConclusion":"..."},'
                    '"dimensionCoverage":[{"dimension":"exact supplied answerDimension",'
                    '"answerContribution":"concrete final-answer-ready resolution"}]}. Include '
                    "one dimensionCoverage entry for every supplied answerDimension. "
                    "Include one recordCoverage entry for every selected packet. Resolve a potentially ambiguous "
                    "surface word from the whole question and selected evidence. Do not enumerate alternate "
                    "dictionary senses unless the question explicitly asks for them or the packets establish a "
                    "genuine, material ambiguity. Omit an unsupported competing sense entirely, including a sentence "
                    "that merely names or negates the rejected sense to explain the disambiguation."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Question:\n{query}\n\nDraft:\n{draft}\n\n"
                    "Answer-coverage hypotheses (not evidence):\n"
                    + json.dumps(answer_hypotheses, ensure_ascii=False)
                    + "\n\n"
                    "Prior evidence-role analysis (verify against the packets):\n"
                    + json.dumps(evidence_role_records, ensure_ascii=False)
                    + "\n\n"
                    "Grounded verbatim answer spans (must appear literally when nonempty):\n"
                    + json.dumps(required_verbatim_spans, ensure_ascii=False)
                    + "\n\n"
                    "Required graph-connected source IDs: "
                    + json.dumps(
                        [str(item.get("sourceId") or "") for item in connected_items],
                        ensure_ascii=False,
                    )
                    + "\n\n"
                    "Selected evidence packets (JSONL):\n"
                    + "\n".join(
                        json.dumps(
                            {
                                "label": item["label"],
                                "sourceId": item["sourceId"],
                                "title": item["title"],
                                "citation": item["citation"],
                                "exactQuote": item["exactQuote"],
                                "selectionReason": item["selectionReason"],
                                "graphConnected": str(item.get("sourceId") or "")
                                in connected_source_ids,
                            },
                            ensure_ascii=False,
                        )
                        for item in audit_items
                    )
                ),
            },
        ]
        revised_raw = str(self._complete(repair_messages) or "").strip()
        revised_payload = _json_object(revised_raw)
        coverage_records = [
            dict(item)
            for item in revised_payload.get("recordCoverage") or []
            if isinstance(item, dict)
        ] + evidence_role_records
        question_coverage = (
            dict(revised_payload.get("questionCoverage") or {})
            if isinstance(revised_payload.get("questionCoverage"), dict)
            else {}
        )
        dimension_coverage = [
            dict(item)
            for item in revised_payload.get("dimensionCoverage") or []
            if isinstance(item, dict)
        ]
        audited = str(revised_payload.get("answer") or "").strip() or (
            revised_raw if not revised_payload else draft
        )
        output_mode = str(revised_payload.get("outputMode") or "explanatory").strip()
        coverage_frame = query_plan.get("coverageFrame")
        if (
            output_mode != "constrained_exact"
            and answer_dimensions
            and isinstance(coverage_frame, dict)
            and any(str(value or "").strip() for value in coverage_frame.values())
        ):
            focused_dimension_messages = [
                {
                    "role": "system",
                    "content": (
                        "Perform one focused task for a general-purpose evidence engine: turn every supplied answer "
                        "dimension into a concrete, final-answer-ready contribution. Return JSON only. Preserve each "
                        "dimension string exactly and include one entry for every dimension. Do not merely say that a "
                        "source did not decide the dimension, that an issue may arise, or that the result depends on "
                        "further review. State the operative rule, effect, remedy, or outcome and apply it conditionally "
                        "to the described facts. When an effect has distinct direct and derivative stages, distinguish "
                        "them when material. Use packet-grounded propositions where available. If the packets do not "
                        "resolve a material dimension, supply sound general reasoning but explicitly label it as general "
                        "reasoning and never attribute it to a packet. Do not invent case-specific facts, authorities, "
                        "or quotations. Schema: "
                        '{"dimensionCoverage":[{"dimension":"exact supplied dimension",'
                        '"answerContribution":"concrete final-answer-ready resolution"}]}.'
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Question:\n{query}\n\nCurrent audited answer:\n{audited}\n\n"
                        "Structured coverage frame (coverage goals, not evidence):\n"
                        + json.dumps(coverage_frame, ensure_ascii=False)
                        + "\n\nAnswer dimensions (preserve exactly):\n"
                        + json.dumps(answer_dimensions, ensure_ascii=False)
                        + "\n\nEvidence-role analysis:\n"
                        + json.dumps(evidence_role_records, ensure_ascii=False)
                        + "\n\nSelected evidence packets (JSONL):\n"
                        + "\n".join(evidence_blocks)
                    ),
                },
            ]
            focused_dimension_payload = _json_object(
                str(self._complete(focused_dimension_messages) or "").strip()
            )
            focused_dimension_coverage = [
                dict(item)
                for item in focused_dimension_payload.get("dimensionCoverage") or []
                if isinstance(item, dict)
            ]
            dimension_coverage = focused_dimension_coverage + dimension_coverage
        required_items = _material_coverage_items(
            audit_items,
            connected_items=connected_items,
            coverage_records=coverage_records,
        )
        missing_after_audit = [
            item
            for item in required_items
            if str(item.get("referenceId") or "") not in audited
        ]
        if not missing_after_audit:
            if output_mode == "constrained_exact":
                return _ensure_verbatim_spans(
                    audited,
                    required_verbatim_spans,
                    constrained_exact=True,
                )
            reinforced = _append_connected_record_coverage(
                audited,
                required_items,
                coverage_records=coverage_records,
            )
            return _ensure_verbatim_spans(
                _append_answer_dimension_coverage(
                    _append_question_coverage(reinforced, question_coverage),
                    answer_dimensions,
                    dimension_coverage,
                ),
                required_verbatim_spans,
            )
        completion_messages = [
            {
                "role": "system",
                "content": (
                    "Complete a final answer without discarding its existing analysis. One or more material connected "
                    "records were dropped during revision. Integrate each missing record by its supplied title or "
                    "citation and explain its distinct supported procedural role, outcome, rule, or factual application. "
                    "Do not attribute a holding that its excerpt does not support, and do not merely append a bare "
                    "source list. Preserve the answer's scope, procedure, consequence analysis, and fact-dependent "
                    "conclusion. If a missing same-event record decides a different direct issue, use any excerpt-supported "
                    "rule, procedural constraint, treatment of the questioned conduct, or outcome that still materially "
                    "informs the question, and then state its holding boundary. Do not reduce such a supported role to "
                    "the observation that the record merely shares facts. If the question requires a constrained exact "
                    "output, preserve that contract. Return "
                    "JSON only. The answer must literally contain every missing referenceId. Schema: "
                    '{"outputMode":"explanatory|constrained_exact","answer":"completed final answer",'
                    '"recordCoverage":[{"sourceId":"...",'
                    '"referenceId":"...","supportedRole":"...",'
                    '"excerptSupportedOperativeProposition":"...","questionApplication":"...",'
                    '"factApplication":"...",'
                    '"proceduralPostureOrOutcome":"...","holdingBoundary":"..."}],'
                    '"questionCoverage":{"authorizationOrScope":"...","procedure":"...",'
                    '"operativeDownstreamConsequence":"...","factSpecificConclusion":"..."},'
                    '"dimensionCoverage":[{"dimension":"exact supplied answerDimension",'
                    '"answerContribution":"concrete final-answer-ready resolution"}]}. Include one '
                    "recordCoverage entry for every missing packet and preserve each primary record's distinct stage, "
                    "result, and direct issue. Include one dimensionCoverage entry for every supplied answerDimension; "
                    "each contribution must resolve the dimension rather than restating it or only noting that a "
                    "source did not decide it."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Question:\n{query}\n\nCurrent answer:\n{audited}\n\n"
                    "Missing connected evidence packets (JSONL):\n"
                    + "\n".join(
                        json.dumps(
                            {
                                "label": item["label"],
                                "sourceId": item["sourceId"],
                                "title": item["title"],
                                "citation": item["citation"],
                                "exactQuote": item["exactQuote"],
                                "selectionReason": item["selectionReason"],
                            },
                            ensure_ascii=False,
                        )
                        for item in missing_after_audit
                    )
                ),
            },
        ]
        completed_raw = str(self._complete(completion_messages) or "").strip()
        completed_payload = _json_object(completed_raw)
        coverage_records.extend(
            dict(item)
            for item in completed_payload.get("recordCoverage") or []
            if isinstance(item, dict)
        )
        coverage_records.extend(evidence_role_records)
        completed_question_coverage = completed_payload.get("questionCoverage")
        if isinstance(completed_question_coverage, dict):
            question_coverage.update(
                {
                    str(key): value
                    for key, value in completed_question_coverage.items()
                    if str(value or "").strip()
                }
            )
        dimension_coverage.extend(
            dict(item)
            for item in completed_payload.get("dimensionCoverage") or []
            if isinstance(item, dict)
        )
        completed = str(completed_payload.get("answer") or "").strip() or (
            completed_raw if not completed_payload else ""
        )
        final_answer = completed or audited
        if str(completed_payload.get("outputMode") or "").strip() == "constrained_exact":
            output_mode = "constrained_exact"
        required_items = _material_coverage_items(
            audit_items,
            connected_items=connected_items,
            coverage_records=coverage_records,
        )
        still_missing = [
            item
            for item in required_items
            if str(item.get("referenceId") or "") not in final_answer
        ]
        if output_mode == "constrained_exact":
            return _ensure_verbatim_spans(
                final_answer,
                required_verbatim_spans,
                constrained_exact=True,
            )
        reinforced = _append_connected_record_coverage(
            final_answer,
            _merge_selection_by_source_id(
                required_items,
                still_missing,
                limit=len(required_items) + len(still_missing),
            ),
            coverage_records=coverage_records,
        )
        return _ensure_verbatim_spans(
            _append_answer_dimension_coverage(
                _append_question_coverage(reinforced, question_coverage),
                answer_dimensions,
                dimension_coverage,
            ),
            required_verbatim_spans,
        )

    def _complete(self, messages: list[dict[str, str]]) -> str:
        return str(
            self.llm_client.complete(
                messages,
                model=self.model,
                timeout_seconds=self.timeout_seconds,
            )
            or ""
        ).strip()


def _grounded_answer_spans(
    role_records: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
) -> list[str]:
    quotes_by_id = {
        str(item.get("sourceId") or ""): str(item.get("exactQuote") or "")
        for item in evidence
        if str(item.get("sourceId") or "")
    }
    grounded: list[str] = []
    for record in role_records:
        if record.get("materialToAnswer") is not True:
            continue
        source_id = str(record.get("sourceId") or "")
        quote = quotes_by_id.get(source_id, "")
        proposed = record.get("answerBearingExactSpans")
        if not quote or not isinstance(proposed, list):
            continue
        for value in proposed:
            span = str(value or "").strip()
            if not span or len(span) > 300 or span not in quote or span in grounded:
                continue
            grounded.append(span)
            if len(grounded) >= 8:
                return grounded
    return grounded


def _prioritize_grounded_answer_windows(
    role_records: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
) -> None:
    roles_by_id = {
        str(record.get("sourceId") or ""): record
        for record in role_records
        if record.get("materialToAnswer") is True and str(record.get("sourceId") or "")
    }
    for item in evidence:
        source_id = str(item.get("sourceId") or "")
        role = roles_by_id.get(source_id)
        windows = item.get("exactQuotes")
        if role is None or not isinstance(windows, list) or len(windows) < 2:
            continue
        combined_quote = str(item.get("exactQuote") or "")
        proposed = role.get("answerBearingExactSpans")
        if not combined_quote or not isinstance(proposed, list):
            continue
        spans = [
            str(value or "").strip()
            for value in proposed
            if str(value or "").strip() and str(value or "").strip() in combined_quote
        ]
        if not spans:
            continue
        prioritized = [
            str(window)
            for window in windows
            if any(span in str(window) for span in spans)
        ]
        prioritized.extend(
            str(window)
            for window in windows
            if not any(span in str(window) for span in spans)
        )
        item["exactQuotes"] = prioritized
        item["exactQuote"] = "\n[…]\n".join(prioritized)


def _ensure_verbatim_spans(
    answer: str,
    required_spans: list[str],
    *,
    constrained_exact: bool = False,
) -> str:
    base = str(answer or "").strip()
    missing = [span for span in required_spans if span and span not in base]
    if not missing:
        return base
    if constrained_exact:
        return "\n".join(required_spans).strip()
    suffix = "\n".join(missing)
    return f"{base}\n\n{suffix}".strip() if base else suffix


def _append_connected_record_coverage(
    answer: str,
    missing_items: list[dict[str, Any]],
    *,
    coverage_records: list[dict[str, Any]],
) -> str:
    if not missing_items:
        return str(answer or "").strip()
    coverage_by_id: dict[str, dict[str, Any]] = {}
    for record in coverage_records:
        source_id = str(record.get("sourceId") or "").strip()
        if source_id:
            merged = coverage_by_id.setdefault(source_id, {})
            merged.update(
                {
                    str(key): value
                    for key, value in record.items()
                    if value is not None and (not isinstance(value, str) or value.strip())
                }
            )
    additions: list[str] = []
    for item in missing_items:
        source_id = str(item.get("sourceId") or "").strip()
        record = coverage_by_id.get(source_id, {})
        semantic_parts = [
            str(record.get(field) or "").strip()
            for field in (
                "supportedRole",
                "directIssueAndOutcome",
                "excerptSupportedOperativeProposition",
                "questionApplication",
                "factApplication",
                "proceduralPostureOrOutcome",
                "holdingBoundary",
            )
            if str(record.get(field) or "").strip()
        ]
        if not semantic_parts:
            reason = str(item.get("selectionReason") or "").strip()
            if reason:
                semantic_parts.append(reason)
        identity = str(item.get("title") or item.get("citation") or source_id).strip()
        citation = str(item.get("citation") or "").strip()
        if citation and citation not in identity:
            identity = f"{identity} ({citation})"
        detail = " ".join(semantic_parts).strip()
        additions.append(f"- {identity}: {detail}" if detail else f"- {identity}")
    base = str(answer or "").strip()
    suffix = "\n".join(additions)
    return f"{base}\n\n{suffix}".strip() if base else suffix


def _material_coverage_items(
    audit_items: list[dict[str, Any]],
    *,
    connected_items: list[dict[str, Any]],
    coverage_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    required_ids = {str(item.get("sourceId") or "") for item in connected_items}
    for record in coverage_records:
        if record.get("materialToAnswer") is True or record.get("sameEventOrProcess") is True:
            source_id = str(record.get("sourceId") or "")
            if source_id:
                required_ids.add(source_id)
    return [
        item
        for item in audit_items
        if str(item.get("sourceId") or "") in required_ids
    ]


def _append_question_coverage(answer: str, question_coverage: dict[str, Any]) -> str:
    base = str(answer or "").strip()
    additions: list[str] = []
    for field in (
        "authorizationOrScope",
        "procedure",
        "operativeDownstreamConsequence",
        "factSpecificConclusion",
    ):
        value = str(question_coverage.get(field) or "").strip()
        if value and value not in base and value not in additions:
            additions.append(value)
    if not additions:
        return base
    suffix = "\n".join(f"- {value}" for value in additions)
    return f"{base}\n\n{suffix}".strip() if base else suffix


def _append_answer_dimension_coverage(
    answer: str,
    answer_dimensions: list[str],
    dimension_coverage: list[dict[str, Any]],
) -> str:
    base = str(answer or "").strip()
    contributions_by_dimension: dict[str, str] = {}
    expected = {str(value).strip() for value in answer_dimensions if str(value).strip()}
    for item in dimension_coverage:
        dimension = str(item.get("dimension") or "").strip()
        contribution = str(item.get("answerContribution") or "").strip()
        if dimension in expected and contribution and dimension not in contributions_by_dimension:
            contributions_by_dimension[dimension] = contribution
    additions = [
        contributions_by_dimension[dimension]
        for dimension in answer_dimensions
        if dimension in contributions_by_dimension
        and contributions_by_dimension[dimension] not in base
    ]
    if not additions:
        return base
    suffix = "\n".join(f"- {value}" for value in additions)
    return f"{base}\n\n{suffix}".strip() if base else suffix


def _detect_schema(conn: sqlite3.Connection) -> _CorpusSchema:
    names = {
        str(row[0])
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'view')").fetchall()
    }
    if {"precedents", "precedents_fts"}.issubset(names):
        columns = [str(row[1]) for row in conn.execute("PRAGMA table_info(precedents_fts)").fetchall()]
        if "canonical_id" not in columns:
            raise RuntimeError("precedents_fts is missing canonical_id")
        text_index = columns.index("full_text") if "full_text" in columns else len(columns) - 1
        return _CorpusSchema(
            name="precedents_fts",
            content_table="precedents",
            fts_table="precedents_fts",
            id_column="canonical_id",
            fts_id_column="canonical_id",
            text_column="full_text",
            join_by_rowid=False,
            fts_text_column_index=text_index,
        )
    if {"documents", "documents_fts"}.issubset(names):
        columns = [str(row[1]) for row in conn.execute("PRAGMA table_info(documents_fts)").fetchall()]
        return _CorpusSchema(
            name="documents_fts",
            content_table="documents",
            fts_table="documents_fts",
            id_column="canonical_id",
            fts_id_column="",
            text_column="full_text",
            join_by_rowid=True,
            fts_text_column_index=max(0, len(columns) - 1),
        )
    raise RuntimeError("no supported FTS corpus schema found")


def _retrieve_candidates(
    conn: sqlite3.Connection,
    schema: _CorpusSchema,
    queries: list[str],
    *,
    limit: int,
    relation_pairs: list[list[str]] | None = None,
    alias_groups: list[dict[str, Any]] | None = None,
    query_timeout_seconds: float = 2.0,
) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    per_query_candidate_ids: list[list[str]] = [[] for _ in queries]
    per_query_limit = max(8, min(40, int(limit)))
    for query_index, query in enumerate(queries):
        for variant_index, fts_query in enumerate(_fts_query_variants(query)):
            try:
                hits = _fts_hits(
                    conn,
                    schema,
                    fts_query,
                    limit=per_query_limit,
                    timeout_seconds=query_timeout_seconds,
                )
            except sqlite3.OperationalError:
                hits = []
            for rank, hit in enumerate(hits, start=1):
                _merge_retrieval_hit(
                    by_id,
                    hit,
                    score=1.0 / (60.0 + (variant_index * 12.0) + rank),
                    provenance={"queryIndex": query_index, "variantIndex": variant_index, "rank": rank},
                )
                source_id = str(hit.get("sourceId") or "")
                if source_id and source_id not in per_query_candidate_ids[query_index]:
                    per_query_candidate_ids[query_index].append(source_id)
    for pair_index, pair in enumerate(relation_pairs or []):
        for variant_index, fts_query in enumerate(
            _relation_pair_fts_queries(pair, alias_groups=alias_groups)
        ):
            try:
                hits = _fts_hits(
                    conn,
                    schema,
                    fts_query,
                    limit=per_query_limit,
                    timeout_seconds=query_timeout_seconds,
                )
            except sqlite3.OperationalError:
                hits = []
            for rank, hit in enumerate(hits, start=1):
                _merge_retrieval_hit(
                    by_id,
                    hit,
                    score=1.0 / (58.0 + (variant_index * 4.0) + rank),
                    provenance={
                        "source": "relation_pair",
                        "pairIndex": pair_index,
                        "variantIndex": variant_index,
                        "rank": rank,
                    },
                )
    initial_ranked = sorted(
        by_id.values(),
        key=lambda item: (-float(item.get("rrfScore") or 0.0), str(item.get("sourceId") or "")),
    )
    reference_seed_limit = min(18, max(6, int(limit)))
    references: list[str] = []
    for item in _reference_seed_items(initial_ranked, max_items=reference_seed_limit):
        reference = str(item.get("referenceId") or "").strip()
        if reference and reference not in references:
            references.append(reference)
        if len(references) >= reference_seed_limit:
            break
    seen_references: set[str] = set()
    frontier = references
    for depth in range(1, 3):
        next_frontier: list[str] = []
        scheduled_references = set(seen_references) | set(frontier)
        for reference_index, reference in enumerate(frontier):
            if reference in seen_references:
                continue
            seen_references.add(reference)
            fts_query = _reference_fts_query(reference)
            if not fts_query:
                continue
            try:
                hits = _fts_hits(
                    conn,
                    schema,
                    fts_query,
                    limit=per_query_limit,
                    timeout_seconds=query_timeout_seconds,
                )
            except sqlite3.OperationalError:
                continue
            local_neighbors = 0
            for rank, hit in enumerate(hits, start=1):
                neighbor_reference = str(hit.get("referenceId") or "").strip()
                _merge_retrieval_hit(
                    by_id,
                    hit,
                    score=1.0 / (55.0 + (depth - 1) * 10.0 + rank),
                    provenance={
                        "source": "reference_neighbor",
                        "depth": depth,
                        "referenceIndex": reference_index,
                        "reference": reference,
                        "rank": rank,
                        "isCrossReference": bool(
                            neighbor_reference and neighbor_reference != reference
                        ),
                    },
                )
                if (
                    neighbor_reference
                    and neighbor_reference not in scheduled_references
                    and local_neighbors < 2
                    and len(next_frontier) < 12
                ):
                    next_frontier.append(neighbor_reference)
                    scheduled_references.add(neighbor_reference)
                    local_neighbors += 1
        frontier = next_frontier
        if not frontier:
            break
    ranked = sorted(
        by_id.values(),
        key=lambda item: (-float(item.get("rrfScore") or 0.0), str(item.get("sourceId") or "")),
    )
    cross_reference_neighbors = sorted(
        [
            item
            for item in ranked
            if any(
                rank.get("source") == "reference_neighbor" and rank.get("isCrossReference")
                for rank in item.get("retrievalRanks") or []
            )
        ],
        key=lambda item: (
            min(
                int(rank.get("depth") or 99)
                for rank in item.get("retrievalRanks") or []
                if rank.get("source") == "reference_neighbor" and rank.get("isCrossReference")
            ),
            -float(item.get("rrfScore") or 0.0),
            str(item.get("sourceId") or ""),
        ),
    )
    reserve = min(max(0, int(limit) // 3), len(cross_reference_neighbors))
    base_quota = max(0, int(limit) - reserve)
    per_query_reserve_depth = 2
    diversity_limit = min(
        sum(
            min(per_query_reserve_depth, len(candidate_ids))
            for candidate_ids in per_query_candidate_ids
        ),
        max(1, (base_quota * 2) // 3),
    )
    diversity_items: list[dict[str, Any]] = []
    diversity_ids: set[str] = set()
    for depth in range(per_query_reserve_depth):
        for candidate_ids in per_query_candidate_ids:
            if depth >= len(candidate_ids):
                continue
            source_id = candidate_ids[depth]
            if source_id in diversity_ids:
                continue
            diversity_ids.add(source_id)
            diversity_items.append(by_id[source_id])
            if len(diversity_items) >= diversity_limit:
                break
        if len(diversity_items) >= diversity_limit:
            break
    selected = _merge_ranked_with_diversity_reserve(
        initial_ranked,
        diversity_items,
        limit=base_quota,
    )
    for item in cross_reference_neighbors:
        if item not in selected:
            selected.append(item)
        if len(selected) >= int(limit):
            break
    for item in ranked:
        if item not in selected:
            selected.append(item)
        if len(selected) >= int(limit):
            break
    return selected[:limit]


def _merge_ranked_with_diversity_reserve(
    globally_ranked: list[dict[str, Any]],
    reserved: list[dict[str, Any]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    quota = max(0, int(limit))
    if quota == 0:
        return []
    reserved_by_id: dict[str, dict[str, Any]] = {}
    for item in reserved:
        source_id = str(item.get("sourceId") or "")
        if source_id and source_id not in reserved_by_id:
            reserved_by_id[source_id] = item
        if len(reserved_by_id) >= quota:
            break
    selected = list(reserved_by_id.values())
    selected_ids = set(reserved_by_id)
    for item in globally_ranked:
        if len(selected) >= quota:
            break
        source_id = str(item.get("sourceId") or "")
        if source_id and source_id not in selected_ids:
            selected.append(item)
            selected_ids.add(source_id)
    return selected[:quota]


def _selected_reference_neighbors(
    conn: sqlite3.Connection,
    schema: _CorpusSchema,
    selected: list[dict[str, Any]],
    *,
    max_neighbors_per_seed: int,
    query_timeout_seconds: float = 2.0,
) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    ordered_selected: list[dict[str, Any]] = []
    for item in selected:
        clone = dict(item)
        clone["retrievalRanks"] = [dict(rank) for rank in item.get("retrievalRanks") or []]
        source_id = str(clone.get("sourceId") or "")
        if not source_id or source_id in by_id:
            continue
        by_id[source_id] = clone
        ordered_selected.append(clone)

    neighbor_limit = max(0, int(max_neighbors_per_seed))
    if not neighbor_limit:
        return ordered_selected
    for seed_index, seed in enumerate(ordered_selected):
        seed_source_id = str(seed.get("sourceId") or "")
        seed_reference = str(seed.get("referenceId") or "").strip()
        references = [seed_reference] if seed_reference else []
        for retrieval_rank in seed.get("retrievalRanks") or []:
            reference = str(retrieval_rank.get("reference") or "").strip()
            if (
                retrieval_rank.get("source") == "reference_neighbor"
                and retrieval_rank.get("isCrossReference")
                and reference
                and reference not in references
            ):
                references.append(reference)
        added = 0
        for reference in references:
            fts_query = _reference_fts_query(reference)
            if not fts_query:
                continue
            try:
                hits = _exact_reference_hits(conn, schema, reference)
                seen_hit_ids = {str(hit.get("sourceId") or "") for hit in hits}
                for hit in _fts_hits(
                    conn,
                    schema,
                    fts_query,
                    limit=max(8, neighbor_limit + 1),
                    timeout_seconds=query_timeout_seconds,
                ):
                    hit_source_id = str(hit.get("sourceId") or "")
                    if hit_source_id and hit_source_id not in seen_hit_ids:
                        hits.append(hit)
                        seen_hit_ids.add(hit_source_id)
            except sqlite3.OperationalError:
                continue
            for rank, hit in enumerate(hits, start=1):
                hit_source_id = str(hit.get("sourceId") or "")
                neighbor_reference = str(hit.get("referenceId") or "").strip()
                if not neighbor_reference or hit_source_id == seed_source_id:
                    continue
                _merge_retrieval_hit(
                    by_id,
                    hit,
                    score=1.0 / (50.0 + rank),
                    provenance={
                        "source": "reference_neighbor",
                        "depth": 1,
                        "referenceIndex": seed_index,
                        "reference": reference,
                        "rank": rank,
                        "isCrossReference": neighbor_reference != seed_reference,
                        "selectedSeed": True,
                    },
                )
                added += 1
                if added >= neighbor_limit:
                    break
            if added >= neighbor_limit:
                break
    selected_ids = {str(item.get("sourceId") or "") for item in ordered_selected}
    neighbors = sorted(
        [item for source_id, item in by_id.items() if source_id not in selected_ids],
        key=lambda item: (
            min(
                int(rank.get("rank") or 999999)
                for rank in item.get("retrievalRanks") or []
                if rank.get("source") == "reference_neighbor"
            ),
            -float(item.get("rrfScore") or 0.0),
            str(item.get("sourceId") or ""),
        ),
    )
    return [*ordered_selected, *neighbors]


def _selected_outgoing_reference_neighbors(
    conn: sqlite3.Connection,
    schema: _CorpusSchema,
    selected: list[dict[str, Any]],
    *,
    max_neighbors_per_seed: int,
) -> list[dict[str, Any]]:
    """Close explicit record links without depending on the retrieval route.

    A selected record may name another record even when it was retrieved by a
    broad semantic query rather than by reference expansion.  Exact identifier
    lookup makes that edge deterministic while keeping document selection
    semantic: only records explicitly named by already-selected evidence are
    added.
    """
    by_id: dict[str, dict[str, Any]] = {}
    ordered_selected: list[dict[str, Any]] = []
    for item in selected:
        clone = dict(item)
        clone["retrievalRanks"] = [dict(rank) for rank in item.get("retrievalRanks") or []]
        source_id = str(clone.get("sourceId") or "")
        if not source_id or source_id in by_id:
            continue
        by_id[source_id] = clone
        ordered_selected.append(clone)

    neighbor_limit = max(0, int(max_neighbors_per_seed))
    if not neighbor_limit:
        return ordered_selected

    outgoing_references_by_source = {
        str(item.get("sourceId") or ""): _reference_like_tokens(
            str(item.get("fullText") or "")
        )
        for item in ordered_selected
        if str(item.get("sourceId") or "")
    }
    exact_hits_by_reference = _exact_reference_hits_by_reference(
        conn,
        schema,
        [
            reference
            for item in ordered_selected
            for reference in outgoing_references_by_source.get(
                str(item.get("sourceId") or ""),
                [],
            )
        ],
    )
    selected_by_reference: dict[str, list[dict[str, Any]]] = {}
    for item in ordered_selected:
        reference = str(item.get("referenceId") or "").strip()
        if reference:
            selected_by_reference.setdefault(reference, []).append(item)
    expansion_order: list[dict[str, Any]] = []
    visited_selected_ids: set[str] = set()

    def append_selected_chain(seed: dict[str, Any]) -> None:
        source_id = str(seed.get("sourceId") or "")
        if not source_id or source_id in visited_selected_ids:
            return
        visited_selected_ids.add(source_id)
        expansion_order.append(seed)
        seed_reference = str(seed.get("referenceId") or "").strip()
        for reference in outgoing_references_by_source.get(source_id, []):
            if reference == seed_reference:
                continue
            for connected in selected_by_reference.get(reference, []):
                append_selected_chain(connected)

    for item in ordered_selected:
        append_selected_chain(item)

    addition_ids: list[str] = []
    for seed_index, seed in enumerate(expansion_order):
        seed_source_id = str(seed.get("sourceId") or "")
        seed_reference = str(seed.get("referenceId") or "").strip()
        added = 0
        for reference in outgoing_references_by_source.get(seed_source_id, []):
            if reference == seed_reference:
                continue
            for hit in exact_hits_by_reference.get(reference, []):
                hit_source_id = str(hit.get("sourceId") or "")
                hit_reference = str(hit.get("referenceId") or "").strip()
                if not hit_source_id or hit_source_id == seed_source_id:
                    continue
                was_present = hit_source_id in by_id
                _merge_retrieval_hit(
                    by_id,
                    hit,
                    score=1.0 / (50.0 + added + 1),
                    provenance={
                        "source": "reference_neighbor",
                        "depth": 1,
                        "referenceIndex": seed_index,
                        "reference": seed_reference or reference,
                        "outgoingReference": reference,
                        "rank": added + 1,
                        "isCrossReference": hit_reference != seed_reference,
                        "selectedSeed": True,
                        "selectedSeedSourceId": seed_source_id,
                    },
                )
                if not was_present:
                    addition_ids.append(hit_source_id)
                added += 1
                break
            if added >= neighbor_limit:
                break

    return [*ordered_selected, *(by_id[source_id] for source_id in addition_ids)]


def _reference_like_tokens(text: str, *, limit: int = 64) -> list[str]:
    """Return generic mixed letter/number identifiers in document order."""
    tokens: list[str] = []
    for value in re.findall(r"[\w./-]+", unicodedata.normalize("NFKC", str(text or ""))):
        cleaned = value.strip("._/-")
        if not 5 <= len(cleaned) <= 64:
            continue
        if not any(character.isalpha() for character in cleaned):
            continue
        if not any(character.isdigit() for character in cleaned):
            continue
        if cleaned in tokens:
            continue
        tokens.append(cleaned)
        if len(tokens) >= max(0, int(limit)):
            break
    return tokens


def _merge_selection_by_source_id(
    primary: list[dict[str, Any]],
    fallback: list[dict[str, Any]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in [*primary, *fallback]:
        source_id = str(item.get("sourceId") or "")
        if not source_id or source_id in seen:
            continue
        merged.append(item)
        seen.add(source_id)
        if len(merged) >= max(0, int(limit)):
            break
    return merged


def _coverage_candidate_pool(
    selected: list[dict[str, Any]],
    reference_neighbors: list[dict[str, Any]],
    original_candidates: list[dict[str, Any]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    if len(reference_neighbors) <= len(selected):
        return reference_neighbors
    return _merge_selection_by_source_id(
        reference_neighbors,
        original_candidates,
        limit=max(len(reference_neighbors), int(limit)),
    )


def _close_selected_reference_graph(
    selected: list[dict[str, Any]],
    candidate_pool: list[dict[str, Any]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    selected_ids = {str(item.get("sourceId") or "") for item in selected}
    by_reference: dict[str, list[dict[str, Any]]] = {}
    for item in candidate_pool:
        reference_id = str(item.get("referenceId") or "").strip()
        if reference_id:
            by_reference.setdefault(reference_id, []).append(item)

    pending: list[str] = []
    seen_references: set[str] = set()
    for item in selected:
        for rank in item.get("retrievalRanks") or []:
            reference = str(rank.get("reference") or "").strip()
            if (
                rank.get("source") == "reference_neighbor"
                and rank.get("isCrossReference")
                and reference
                and reference not in seen_references
            ):
                pending.append(reference)
                seen_references.add(reference)

    additions: list[dict[str, Any]] = []
    while pending:
        reference = pending.pop(0)
        for item in by_reference.get(reference, []):
            source_id = str(item.get("sourceId") or "")
            if not source_id or source_id in selected_ids:
                continue
            selected_ids.add(source_id)
            additions.append(item)
            for rank in item.get("retrievalRanks") or []:
                connected_reference = str(rank.get("reference") or "").strip()
                if (
                    rank.get("source") == "reference_neighbor"
                    and rank.get("isCrossReference")
                    and connected_reference
                    and connected_reference not in seen_references
                ):
                    pending.append(connected_reference)
                    seen_references.add(connected_reference)
            break

    if not additions:
        return selected[:limit]
    reserve = min(len(additions), max(0, int(limit)))
    retained = selected[: max(0, int(limit) - reserve)]
    return _merge_selection_by_source_id(
        retained,
        additions,
        limit=max(0, int(limit)),
    )


def _reserve_explicit_reference_neighbors(
    selected: list[dict[str, Any]],
    selected_with_neighbors: list[dict[str, Any]],
    *,
    limit: int,
    max_additions: int | None = None,
) -> list[dict[str, Any]]:
    selected_ids = {str(item.get("sourceId") or "") for item in selected}
    additions = [
        item
        for item in selected_with_neighbors
        if str(item.get("sourceId") or "") not in selected_ids
    ]
    if max_additions is not None:
        additions = additions[: max(0, int(max_additions))]
    if not additions:
        return selected[:limit]
    reserve = min(len(additions), max(0, int(limit)))
    retained_quota = max(0, int(limit) - reserve)
    retained = selected[:retained_quota]
    protected_seed_ids = {
        str(rank.get("selectedSeedSourceId") or "")
        for item in additions
        for rank in item.get("retrievalRanks") or []
        if rank.get("selectedSeed") and str(rank.get("selectedSeedSourceId") or "")
    }
    selected_order = {
        str(item.get("sourceId") or ""): index
        for index, item in enumerate(selected)
    }
    retained_ids = {str(item.get("sourceId") or "") for item in retained}
    for item in selected:
        source_id = str(item.get("sourceId") or "")
        if source_id not in protected_seed_ids or source_id in retained_ids:
            continue
        replacement_index = next(
            (
                index
                for index in range(len(retained) - 1, -1, -1)
                if str(retained[index].get("sourceId") or "") not in protected_seed_ids
            ),
            None,
        )
        if replacement_index is None:
            break
        retained_ids.discard(str(retained[replacement_index].get("sourceId") or ""))
        retained[replacement_index] = item
        retained_ids.add(source_id)
    retained.sort(
        key=lambda item: selected_order.get(
            str(item.get("sourceId") or ""),
            len(selected_order),
        )
    )
    return _merge_selection_by_source_id(
        retained,
        additions,
        limit=max(0, int(limit)),
    )


def _reserve_incoming_reference_neighbors(
    selected: list[dict[str, Any]],
    original_candidates: list[dict[str, Any]],
    *,
    limit: int,
    max_additions: int,
) -> list[dict[str, Any]]:
    """Preserve top semantic candidates that explicitly cite selected records."""
    selected_ids = {str(item.get("sourceId") or "") for item in selected}
    selected_references = {
        str(item.get("referenceId") or "").strip()
        for item in selected
        if str(item.get("referenceId") or "").strip()
    }
    additions: list[dict[str, Any]] = []
    for item in original_candidates[: max(0, int(limit))]:
        source_id = str(item.get("sourceId") or "")
        if not source_id or source_id in selected_ids:
            continue
        has_incoming_edge = any(
            rank.get("source") == "reference_neighbor"
            and rank.get("isCrossReference")
            and str(rank.get("reference") or "").strip() in selected_references
            for rank in item.get("retrievalRanks") or []
        )
        if not has_incoming_edge:
            continue
        additions.append(item)
        if len(additions) >= max(0, int(max_additions)):
            break
    return _reserve_explicit_reference_neighbors(
        selected,
        [*selected, *additions],
        limit=limit,
        max_additions=max_additions,
    )


def _exact_reference_hits(
    conn: sqlite3.Connection,
    schema: _CorpusSchema,
    reference: str,
) -> list[dict[str, Any]]:
    columns = {
        str(row[1])
        for row in conn.execute(f"PRAGMA table_info({schema.content_table})").fetchall()
    }
    reference_column = next(
        (name for name in ("case_number", "canonical_ref") if name in columns),
        "",
    )
    if not reference_column:
        return []
    rows = conn.execute(
        f"SELECT d.*, '' AS search_excerpt FROM {schema.content_table} d "
        f"WHERE d.{reference_column} = ? LIMIT 4",
        (str(reference),),
    ).fetchall()
    return [_normalized_row(row, schema) for row in rows]


def _exact_reference_hits_by_reference(
    conn: sqlite3.Connection,
    schema: _CorpusSchema,
    references: list[str],
) -> dict[str, list[dict[str, Any]]]:
    columns = {
        str(row[1])
        for row in conn.execute(f"PRAGMA table_info({schema.content_table})").fetchall()
    }
    reference_column = next(
        (name for name in ("case_number", "canonical_ref") if name in columns),
        "",
    )
    ordered_references: list[str] = []
    for value in references:
        reference = str(value or "").strip()
        if reference and reference not in ordered_references:
            ordered_references.append(reference)
    if not reference_column or not ordered_references:
        return {}

    hits_by_reference: dict[str, list[dict[str, Any]]] = {}
    chunk_size = 900
    for start in range(0, len(ordered_references), chunk_size):
        chunk = ordered_references[start : start + chunk_size]
        placeholders = ",".join("?" for _ in chunk)
        rows = conn.execute(
            f"SELECT d.*, '' AS search_excerpt FROM {schema.content_table} d "
            f"WHERE d.{reference_column} IN ({placeholders})",
            chunk,
        ).fetchall()
        for row in rows:
            hit = _normalized_row(row, schema)
            reference = str(hit.get("referenceId") or "").strip()
            local_hits = hits_by_reference.setdefault(reference, [])
            if reference and len(local_hits) < 4:
                local_hits.append(hit)
    return hits_by_reference


def _reference_seed_items(
    ranked: list[dict[str, Any]],
    *,
    max_items: int,
) -> list[dict[str, Any]]:
    """Preserve both consensus leaders and one leader per semantic relation.

    Reciprocal-rank fusion can otherwise let documents that match many broad
    formulations crowd out the strongest result for a single relation.  Those
    relation leaders are valuable graph-expansion seeds even when their global
    fused rank is lower.
    """

    limit = max(0, int(max_items))
    if not limit:
        return []
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()

    def append(item: dict[str, Any]) -> None:
        source_id = str(item.get("sourceId") or "")
        if source_id and source_id not in selected_ids and len(selected) < limit:
            selected.append(item)
            selected_ids.add(source_id)

    relation_indices = sorted(
        {
            int(retrieval_rank["pairIndex"])
            for item in ranked
            for retrieval_rank in item.get("retrievalRanks") or []
            if retrieval_rank.get("source") == "relation_pair"
            and isinstance(retrieval_rank.get("pairIndex"), int)
        }
    )
    relation_budget = min(limit, len(relation_indices) * 2)
    variant_indices = sorted(
        {
            int(retrieval_rank["variantIndex"])
            for item in ranked
            for retrieval_rank in item.get("retrievalRanks") or []
            if retrieval_rank.get("source") == "relation_pair"
            and isinstance(retrieval_rank.get("variantIndex"), int)
        }
    )
    for variant_index in variant_indices:
        for pair_index in relation_indices:
            candidates = [
                item
                for item in ranked
                if any(
                    retrieval_rank.get("source") == "relation_pair"
                    and retrieval_rank.get("pairIndex") == pair_index
                    and retrieval_rank.get("variantIndex") == variant_index
                    for retrieval_rank in item.get("retrievalRanks") or []
                )
            ]
            if candidates:
                append(
                    min(
                        candidates,
                        key=lambda item: (
                            min(
                                int(retrieval_rank.get("rank") or 999999)
                                for retrieval_rank in item.get("retrievalRanks") or []
                                if retrieval_rank.get("source") == "relation_pair"
                                and retrieval_rank.get("pairIndex") == pair_index
                                and retrieval_rank.get("variantIndex") == variant_index
                            ),
                            -float(item.get("rrfScore") or 0.0),
                            str(item.get("sourceId") or ""),
                        ),
                    )
                )
            if len(selected) >= relation_budget:
                break
        if len(selected) >= relation_budget:
            break
    for item in ranked:
        append(item)
        if len(selected) >= limit:
            break
    return selected


def _merge_retrieval_hit(
    by_id: dict[str, dict[str, Any]],
    hit: dict[str, Any],
    *,
    score: float,
    provenance: dict[str, Any],
) -> None:
    source_id = str(hit.get("sourceId") or "")
    if not source_id:
        return
    item = by_id.get(source_id)
    if item is None:
        item = dict(hit)
        item["rrfScore"] = 0.0
        item["retrievalRanks"] = []
        by_id[source_id] = item
    item["rrfScore"] = float(item.get("rrfScore") or 0.0) + float(score)
    item["retrievalRanks"].append(dict(provenance))


def _fts_hits(
    conn: sqlite3.Connection,
    schema: _CorpusSchema,
    fts_query: str,
    *,
    limit: int,
    timeout_seconds: float = 2.0,
) -> list[dict[str, Any]]:
    table = schema.fts_table
    if schema.join_by_rowid:
        sql = f"""
            SELECT d.*, snippet({table}, {schema.fts_text_column_index}, '', '', ' … ', 24) AS search_excerpt
            FROM {table}
            JOIN {schema.content_table} d ON d.rowid = {table}.rowid
            WHERE {table} MATCH ?
            ORDER BY bm25({table})
            LIMIT ?
        """
    else:
        sql = f"""
            SELECT d.*, snippet({table}, {schema.fts_text_column_index}, '', '', ' … ', 24) AS search_excerpt
            FROM {table}
            JOIN {schema.content_table} d ON d.{schema.id_column} = {table}.{schema.fts_id_column}
            WHERE {table} MATCH ?
            ORDER BY bm25({table})
            LIMIT ?
        """
    deadline = time.monotonic() + max(0.05, float(timeout_seconds))
    conn.set_progress_handler(lambda: int(time.monotonic() >= deadline), 10_000)
    try:
        rows = conn.execute(sql, (fts_query, int(limit))).fetchall()
    finally:
        conn.set_progress_handler(None, 0)
    return [_normalized_row(row, schema) for row in rows]


def _normalized_row(row: sqlite3.Row, schema: _CorpusSchema) -> dict[str, Any]:
    keys = set(row.keys())

    def value(*names: str) -> str:
        for name in names:
            if name in keys and row[name] is not None:
                text = str(row[name]).strip()
                if text:
                    return text
        return ""

    citation_parts = [value("case_number", "canonical_ref"), value("court"), value("decision_date")]
    citation = " · ".join(part for part in citation_parts if part)
    full_text = value("full_text")
    if not full_text:
        full_text = "\n".join(value(name) for name in ("question", "answer", "body") if value(name))
    return {
        "sourceId": value(schema.id_column),
        "referenceId": value("case_number", "canonical_ref"),
        "title": value("title", "case_name", "topic"),
        "citation": citation,
        "fullText": full_text,
        "searchExcerpt": value("search_excerpt") or full_text[:1200],
    }


def _evidence_packet(
    item: dict[str, Any],
    *,
    index: int,
    query: str,
    query_plan: dict[str, Any],
    selection_reason: str,
) -> dict[str, Any]:
    source_id = str(item.get("sourceId") or "")
    connections = []
    for retrieval_rank in item.get("retrievalRanks") or []:
        if (
            retrieval_rank.get("source") == "reference_neighbor"
            and retrieval_rank.get("isCrossReference")
        ):
            reference = str(retrieval_rank.get("reference") or "")
            if reference and reference not in connections:
                connections.append(reference)
    full_text = str(item.get("fullText") or "")
    passage_queries = _passage_queries(query, query_plan)
    query_windows = _best_query_windows(
        full_text,
        passage_queries,
        max_chars=750,
        max_windows=3,
    )
    value_marker_windows = _best_value_marker_windows(
        full_text,
        [str(value or "") for value in query_plan.get("answerValueMarkers") or []],
        context_queries=passage_queries,
        max_chars=750,
        max_windows=4,
    )
    exact_quotes: list[str] = []
    for window in [*value_marker_windows, *query_windows]:
        if window and window not in exact_quotes:
            exact_quotes.append(window)
    return {
        "label": f"S{index}",
        "packetId": f"S{index}:{source_id}",
        "sourceId": source_id,
        "referenceId": str(item.get("referenceId") or ""),
        "title": str(item.get("title") or ""),
        "citation": str(item.get("citation") or ""),
        "exactQuote": "\n[…]\n".join(exact_quotes),
        "exactQuotes": exact_quotes,
        "selectionReason": str(selection_reason or ""),
        "connectedReferences": connections,
        "relation": "candidate_evidence",
    }


def _exact_window(text: str, query: str, *, max_chars: int) -> str:
    return _best_query_window(text, query, max_chars=max_chars)


def _best_query_window(text: str, query: str, *, max_chars: int) -> str:
    windows = _best_query_windows(text, [query], max_chars=max_chars, max_windows=1)
    return windows[0] if windows else ""


def _passage_queries(query: str, query_plan: dict[str, Any]) -> list[str]:
    values = [str(query or "")]
    values.extend(
        " ".join(str(side or "") for side in pair)
        for pair in query_plan.get("relationPairs") or []
        if isinstance(pair, list) and len(pair) == 2
    )
    for group in query_plan.get("crossLanguageAliases") or []:
        if not isinstance(group, dict):
            continue
        values.append(
            " ".join(
                [str(group.get("term") or "")]
                + [str(alias or "") for alias in group.get("aliases") or []]
            )
        )
    values.extend(str(value or "") for value in query_plan.get("candidateCanonicalForms") or [])
    values.extend(str(value or "") for value in query_plan.get("queries") or [])
    values.extend(str(value or "") for value in query_plan.get("answerDimensionQueries") or [])
    values.extend(
        str(value or "") for value in query_plan.get("answerDimensionEvidenceQueries") or []
    )
    unique: list[str] = []
    for value in values:
        cleaned = _clean_query(value)
        if cleaned and cleaned not in unique:
            unique.append(cleaned)
        if len(unique) >= 24:
            break
    return unique


def _best_query_windows(
    text: str,
    queries: list[str],
    *,
    max_chars: int,
    max_windows: int,
) -> list[str]:
    raw = str(text or "")
    window_limit = max(1, int(max_windows))
    if not raw:
        return []
    if len(raw) <= max_chars:
        return [raw]
    folded = raw.casefold()
    token_groups: list[list[str]] = []
    tokens: list[str] = []
    for query in queries:
        group = [token.casefold() for token in _query_tokens(query) if len(token) >= 2][:16]
        if not group:
            continue
        token_groups.append(group)
        for token in group:
            if token not in tokens:
                tokens.append(token)
            if len(tokens) >= 48:
                break
        if len(tokens) >= 48:
            break
    starts = {0}
    for token in tokens:
        offset = 0
        occurrences = 0
        while occurrences < 24:
            position = folded.find(token, offset)
            if position < 0:
                break
            starts.add(max(0, position - max_chars // 3))
            offset = position + max(1, len(token))
            occurrences += 1
    if len(starts) == 1:
        return [raw[:max_chars]]
    ranked_windows: list[tuple[tuple[int, int, int, int, int], int, int]] = []
    for start in starts:
        end = min(len(raw), start + max_chars)
        start = max(0, end - max_chars)
        window = folded[start:end]
        positions = [window.find(token) for token in tokens]
        matched = [(token, position) for token, position in zip(tokens, positions) if position >= 0]
        if matched:
            span = max(position for _, position in matched) - min(position for _, position in matched)
        else:
            span = max_chars
        group_scores = []
        for group in token_groups:
            group_positions = [window.find(token) for token in group]
            group_matched = [
                (token, position)
                for token, position in zip(group, group_positions)
                if position >= 0
            ]
            if group_matched:
                group_span = max(position for _, position in group_matched) - min(
                    position for _, position in group_matched
                )
            else:
                group_span = max_chars
            group_scores.append(
                (
                    len(group_matched),
                    sum(min(len(token), 16) for token, _ in group_matched),
                    -group_span,
                )
            )
        best_group = max(group_scores, default=(0, 0, -max_chars))
        score = (
            best_group[0],
            best_group[1],
            len(matched),
            sum(min(len(token), 16) for token, _ in matched),
            -span,
        )
        ranked_windows.append((score, start, end))
    ranked_windows.sort(key=lambda value: (value[0], -value[1]), reverse=True)
    selected: list[tuple[int, int]] = []
    for _, start, end in ranked_windows:
        if any(start < prior_end and end > prior_start for prior_start, prior_end in selected):
            continue
        selected.append((start, end))
        if len(selected) >= window_limit:
            break
    if not selected and ranked_windows:
        _, start, end = ranked_windows[0]
        selected.append((start, end))
    return [raw[start:end] for start, end in selected]


def _best_value_marker_windows(
    text: str,
    markers: list[str],
    *,
    context_queries: list[str],
    max_chars: int,
    max_windows: int,
) -> list[str]:
    raw = str(text or "")
    if not raw or not markers or max_windows <= 0:
        return []
    folded = unicodedata.normalize("NFKC", raw).casefold()
    context_tokens: list[str] = []
    for query in context_queries:
        for token in _query_tokens(query):
            folded_token = token.casefold()
            if len(folded_token) >= 2 and folded_token not in context_tokens:
                context_tokens.append(folded_token)
            if len(context_tokens) >= 48:
                break
        if len(context_tokens) >= 48:
            break
    ranked: list[tuple[tuple[int, int, int, int], int, int, int]] = []
    for marker_index, value in enumerate(markers[:8]):
        marker = unicodedata.normalize("NFKC", str(value or "")).casefold().strip()
        if not marker or len(marker) > 64:
            continue
        offset = 0
        occurrences = 0
        while occurrences < 256:
            position = folded.find(marker, offset)
            if position < 0:
                break
            before = folded[max(0, position - 32) : position]
            after = folded[position + len(marker) : position + len(marker) + 32]
            scalar_adjacent = bool(
                re.search(r"\d[\d\s.,:/-]{0,24}$", before)
                or re.match(r"^[\s:=(\[]*\d", after)
            )
            start = max(0, position - max_chars // 2)
            end = min(len(raw), start + max_chars)
            start = max(0, end - max_chars)
            window = folded[start:end]
            matched = [token for token in context_tokens if token in window]
            score = (
                int(scalar_adjacent),
                len(matched),
                sum(min(len(token), 16) for token in matched),
                len(marker),
            )
            ranked.append((score, marker_index, start, end))
            offset = position + max(1, len(marker))
            occurrences += 1
    ranked.sort(key=lambda item: (item[0], -item[2]), reverse=True)
    selected: list[tuple[int, int]] = []
    for marker_index in range(min(8, len(markers))):
        local_count = 0
        for _, candidate_marker_index, start, end in ranked:
            if candidate_marker_index != marker_index:
                continue
            if any(start < prior_end and end > prior_start for prior_start, prior_end in selected):
                continue
            selected.append((start, end))
            local_count += 1
            if local_count >= 2 or len(selected) >= max_windows:
                break
        if len(selected) >= max_windows:
            break
    if len(selected) < max_windows:
        for _, _, start, end in ranked:
            if any(start < prior_end and end > prior_start for prior_start, prior_end in selected):
                continue
            selected.append((start, end))
            if len(selected) >= max_windows:
                break
    return [raw[start:end] for start, end in selected]


def _fts_query(value: str) -> str:
    variants = _fts_query_variants(value)
    return variants[0] if variants else ""


def _fts_query_variants(value: str) -> list[str]:
    tokens = _query_tokens(value)[:6]
    if not tokens:
        return []

    def conjunction(values: list[str], *, prefix: bool = False) -> str:
        suffix = "*" if prefix else ""
        quoted = [f'"{token.replace(chr(34), chr(34) * 2)}"{suffix}' for token in values]
        return " AND ".join(quoted)

    groups: list[tuple[list[str], bool]] = [(tokens, False)]
    if len(tokens) >= 2:
        groups.append((tokens, True))
    if len(tokens) > 3:
        groups.append((tokens[:3], False))
        groups.append((tokens[2:4], True))
    if len(tokens) > 5:
        groups.append((tokens[4:6], True))
    variants: list[str] = []
    for group, prefix in groups:
        query = conjunction(group, prefix=prefix)
        if query and query not in variants:
            variants.append(query)
    return variants


def _reference_fts_query(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).casefold()
    tokens = re.findall(r"[^\W_]+", normalized, flags=re.UNICODE)[:8]
    if not tokens:
        return ""
    phrase = " ".join(token.replace(chr(34), chr(34) * 2) for token in tokens)
    return f'"{phrase}"'


def _relation_pair_fts_queries(
    pair: list[str],
    *,
    alias_groups: list[dict[str, Any]] | None = None,
) -> list[str]:
    if not isinstance(pair, list) or len(pair) != 2:
        return []
    pair_variants = [(str(pair[0]), str(pair[1]))]
    pair_variants.extend(
        (left_variant, str(pair[1]))
        for left_variant in _relation_side_alias_variants(pair[0], alias_groups)[1:]
    )
    pair_variants.extend(
        (str(pair[0]), right_variant)
        for right_variant in _relation_side_alias_variants(pair[1], alias_groups)[1:]
    )
    variants: list[str] = []
    for left_value, right_value in pair_variants:
        left = _query_tokens(left_value)[:3]
        right = _query_tokens(right_value)[:3]
        local_count = 0
        for left_token in left:
            for right_token in right:
                if left_token.casefold() == right_token.casefold():
                    continue
                query = (
                    f'"{left_token.replace(chr(34), chr(34) * 2)}"* AND '
                    f'"{right_token.replace(chr(34), chr(34) * 2)}"*'
                )
                if query not in variants:
                    variants.append(query)
                    local_count += 1
                if local_count >= 6 or len(variants) >= 18:
                    break
            if local_count >= 6 or len(variants) >= 18:
                break
        if len(variants) >= 18:
            break
    return variants


def _relation_side_alias_variants(
    value: str,
    alias_groups: list[dict[str, Any]] | None,
) -> list[str]:
    text = str(value or "").strip()
    variants = [text] if text else []
    for group in alias_groups or []:
        if not isinstance(group, dict):
            continue
        members = [str(group.get("term") or "").strip()]
        members.extend(
            str(alias).strip()
            for alias in group.get("aliases") or []
            if str(alias).strip()
        )
        matched = next(
            (
                member
                for member in sorted(members, key=len, reverse=True)
                if member and re.search(re.escape(member), text, flags=re.IGNORECASE)
            ),
            "",
        )
        if not matched:
            continue
        for replacement in members:
            if not replacement or replacement.casefold() == matched.casefold():
                continue
            candidate = re.sub(
                re.escape(matched),
                replacement,
                text,
                count=1,
                flags=re.IGNORECASE,
            )
            if candidate not in variants:
                variants.append(candidate)
            if len(variants) >= 6:
                return variants
    return variants


def _query_tokens(value: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", str(value or "")).casefold()
    tokens: list[str] = []
    for token in re.findall(r"[^\W_]+", normalized, flags=re.UNICODE):
        if token.isdigit():
            continue
        if len(token) <= 1:
            continue
        if token not in tokens:
            tokens.append(token)
    return tokens


def _round_robin_unique(groups: list[list[str]], *, limit: int) -> list[str]:
    merged: list[str] = []
    depth = 0
    while len(merged) < max(0, int(limit)):
        added = False
        for group in groups:
            if depth >= len(group):
                continue
            value = str(group[depth] or "").strip()
            if value and value not in merged:
                merged.append(value)
                if len(merged) >= int(limit):
                    return merged
            added = True
        if not added:
            break
        depth += 1
    return merged


def _clean_anonymized_query(value: Any) -> str:
    cleaned = _clean_query(value)
    cleaned = re.sub(r"\[[^\]\n]{1,120}\]|\{[^}\n]{1,120}\}|<[^>\n]{1,120}>", " ", cleaned)
    return _clean_query(cleaned)


def _clean_query(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:600]


def _json_object(value: str) -> dict[str, Any]:
    text = str(value or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _model_metadata(client: Any, model: str) -> dict[str, Any]:
    decoding = getattr(client, "decoding", None)
    if decoding is None:
        decoding = getattr(client, "decoding_config", None)
    if not isinstance(decoding, dict):
        decoding = {}
        for name in ("temperature", "top_p", "top_k", "max_tokens", "thinking_level"):
            if hasattr(client, name):
                value = getattr(client, name)
                if value not in (None, ""):
                    decoding[name] = value
    return {
        "provider": str(getattr(client, "provider", "custom_llm") or "custom_llm"),
        "model": str(model or getattr(client, "default_model", "") or ""),
        "decoding": {str(key): value for key, value in sorted(decoding.items())},
    }
