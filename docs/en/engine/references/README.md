# Memory Engine References And Trial Notes

Last updated: 2026-05-15 KST

This folder is the engine team's starting map. It collects project ideas, prior beta-6 lessons, and external repositories worth testing. Nothing here is automatically accepted; every idea must pass this repo's benchmarks and source-window contract.

## Why These Notes Exist

The project is building a complete memory engine, not a narrow retrieval widget. The intended system should ingest messy real corpora, preserve originals, understand chronology and references, select evidence with expert-level recall, and make the answer auditable through claim cards and source windows.

The notes below preserve the trial directions that should not be forgotten when engine work is split across teams:

- beta-6 is the current baseline because it selected evidence before writing and produced inspectable artifacts, not because its internal implementation is final;
- coverage patching is required because important axes are often missed by a single retrieval pass;
- redundant convergence is required because one wrong binding can corrupt the whole answer;
- tree/graph memory is required because real files refer to each other across time, slides, transcripts, images, and repeated lectures;
- ingestion is part of memory, not a separate afterthought, because a bad transcript/OCR/table parse produces unrecoverable downstream errors;
- benchmarks must be diverse and rotating so the team proves general ability instead of memorizing known examples.

## Project-Owned Ideas To Preserve

### Hit-Thunder Coverage Patch

Reference: https://github.com/pineapplesour/Hit-Thunder

Use the idea as an engine loop:

1. Interpret the user goal.
2. Enumerate required coverage axes.
3. Attach selected evidence to each axis.
4. Detect missing, weak, contradictory, or unresolved axes.
5. Search/inspect again.
6. Stop only when all axes are satisfied or explicitly absent.

Required artifact: `coverageReport` with `axes`, `satisfied`, `weak`, `missing`, `followupSearches`, and `explicitAbsence`.

### mini-artichokes Redundant Convergence

Reference: https://github.com/pineapplesour/mini-artichokes

Use independent passes for high-risk decisions:

- exam range/date extraction;
- reversed or superseded statements;
- quote-span matching;
- cross-file reference resolution;
- recommendation top choice;
- multimodal transcript-to-slide binding.

If passes disagree, report the disagreement. Do not hide it behind a single confident answer.

## External Repo Ideas To Test

| Repo/family | What to study | Local acceptance condition |
|---|---|---|
| RAGFlow | document understanding, traceable citations, fused recall/rerank, KG/RAPTOR/PageIndex | improves recall or source-window provenance without breaking latency gates |
| KAG | knowledge-chunk mutual indexing, schema-constrained construction, logical-form guided retrieval | resolves cross-file/time/logic tasks better than beta-6 on hidden tests |
| Graphiti | temporal graph, raw episode provenance, incremental updates, bi-temporal tracking | handles reversals, chronology, and provenance with inspectable artifacts |
| LightRAG | graph RAG modes and reranker patterns | improves multi-hop recall without requiring unacceptable model/runtime cost |
| Hindsight | semantic/BM25/graph/temporal parallel recall with fusion | reduces missed evidence compared to a single recall path |
| Pathway llm-app | live sync search infra | helps shared DB/live file updates without turning into opaque infra |
| WeKnora | enterprise document Q&A, parent-child chunks, source preview | useful for document preview and tenant-isolated retrieval patterns |
| Microsoft GraphRAG / HippoRAG | hierarchy, community, multi-hop memory ideas | use as design reference, not as a drop-in product claim |

## Ingestion References

| Data type | Candidate references | Test focus |
|---|---|---|
| PDF | OpenDataLoader PDF, Docling, Marker, RAGFlow parsers | reading order, scanned OCR, tables, formulas, charts, headers/footers |
| HWP/HWPX | kordoc, JDoc, unhwp, DocsRay | Korean documents, merged tables, assets, headings, malformed files |
| Office files | Docling, OmniParse, kordoc | slides, speaker notes, tables, structured extraction |
| Audio/video | WhisperX, pyannote.audio, OmniParse, DocsRay | timestamps, diarization, VAD, lecture-to-slide alignment |
| Images/diagrams | dots.ocr, CircuitVision, datasheet-cli | chart/table/circuit source spans and exact image retrieval |
| Dedup/coref | Epstein Pipeline, KoreanCoreferenceResolution, KoBookNLP, fastcoref | duplicate classes, Korean pronouns/ellipsis, speaker references |

## Prior Beta-6 Lessons That Must Not Be Forgotten

- Full frontier audit matters: Islam/TCM normally audit 1200 candidates and select 100 sources.
- Late keyword starvation was a real bug: a broad first round can fill the frontier and starve more specific second-round terms.
- Lowering keyword rounds can change evidence composition drastically; it is not just latency tuning.
- Selector worker count alone cannot meet the latency target; the slowest batch sets a hard floor.
- Hot-cache app-path proof is not cold latency proof.
- Prompt-size telemetry must exist before prompt-shape changes are promoted.
- Selector variants that looked plausible failed when overlap, prompt size, timeout, or source-kind gates were checked.
- Claim count alone is not enough; candidate/cited claim split and source-window highlight must be verified in the UI.
- The writer must answer from selected original evidence, not from summaries alone.

## Benchmarks To Build Next

- Legal: KakaoTalk evidence, military-key benchmark, snowboard benchmark.
- School/course: exact problem extraction, exact explanation retrieval, exam range/date, professor emphasis, professor problem-style inference, circuit image retrieval.
- Religion: Islam/Hindu/Buddhist/Christian questions base models miss, with source hierarchy and tradition or denomination distinctions.
- TCM: classic/herb/formula/safety boundary separation.
- Simli: DSM/ICD/guideline/research/case split and crisis boundary.
- Recommendation: expert-like selection from a huge corpus with rejected near-miss reasons.
- Negative evidence: prove absence of missing date/range/quote/image.
