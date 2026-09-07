# Memory Engine Requirements

Last updated: 2026-07-24 KST

This document is the standalone requirements handoff for the memory/search/recommendation engine. It is separate from `docs/overall-structure-requirements.md`, which defines the product/API/design structure and treats this engine as a replaceable black box.

## Final Goal

The project-level goal is not a memory engine by itself; it is one fast,
high-accuracy general answer engine. The default starting point is direct Codex
behind a thin generic harness. Memory, search, and databases are optional tools
that Codex may choose. This document specifies that optional capability for
questions such as "organize all information about X": it must select necessary
original evidence with minimal omissions, no hallucinated evidence, acceptable
time/cost, and enough provenance for verification.

The current best-known memory-capability baseline is beta-6, adapted from
Lawkey. It is not the default whole answer engine or a mandatory reasoning
stage. Every added memory path must prove a complete-answer accuracy, latency,
and cost gain against direct Codex.

## Preserved Product Intent And Context

This optional capability is not "make a nicer RAG demo." When external evidence
is needed, it should behave as if a careful expert inspected the available
corpus, selected the right original evidence, understood cross-document
context, and handed Codex/the UI enough proof to quote and explain it.

The operating direction behind this document can be summarized as:

- do not lose the original source;
- do not answer from a summary when an original span is needed;
- do not solve a benchmark by cheating or overfitting to its visible wording;
- do not fix retrieval failures with narrow one-off rules;
- make the engine universal enough for law, school materials, religion, medicine, psychology, and recommendation;
- make every important selection inspectable, reversible, and comparable against prior attempts;
- when the system is unsure about an instruction, state the interpretation and ask instead of guessing;
- report success only after testing through the real app path.

Representative hard situations:

- a lecture recording refers to a slide, circuit image, PDF, or HWP handout that must be matched automatically;
- a professor changes an exam range after saying a broader range earlier;
- a request asks for "all problems", "the exact explanation of this problem", "when is the exam", or "what did the professor emphasize", where generic summarization loses the key evidence;
- the same fact appears in multiple files, and repeated mention may be important rather than duplicate noise;
- a legal query needs the exact KakaoTalk/military-key/snowboard evidence, not just a semantically similar case;
- a recommendation task should approach the choice an expert would make after inspecting the whole corpus, including rejected near misses;
- religious/medical/psychological answers need source hierarchy and safety boundaries, not fluent free-form synthesis.

This is why the current requirement insists on provenance, duplicate/repetition ledgers, reference resolution, time graphs, claim cards, source windows, coverage reports, and benchmark gates. These are not decorative fields. They are protections against the exact ways prior retrieval systems failed: missing a crucial source, binding "that thing" to the wrong file, counting a duplicate twice, treating a superseded statement as current, quoting a summary instead of a source, or producing a plausible answer that cannot be audited.

## What Was Chosen From Prior Work

The following ideas from prior work are explicitly preserved as requirements or trial directions:

| Preserved item | Why it matters | Where it appears in this contract |
|---|---|---|
| beta-6 / Lawkey-style selected-evidence handoff | Current strongest baseline; selects evidence first and avoids pretending summaries are evidence | `Current Beta-6 Shape`, `Required Evidence Objects`, `Promotion Gate` |
| claim cards with context summary, claim summary, quote, and span | Lets the writer choose useful citations and lets the UI explain why a citation matters | `Claim Card`, `Passage Window`, `Evidence Shape Gate` |
| source windows with exact highlight and bounded expansion | User must click a citation and see the exact original span without loading huge files | `Passage Window`, `Full User-Path Gate` |
| top-k 100 selected source handoff | Previous systems depended on rich candidate context; reducing this casually destroyed evidence shape | `Current Beta-6 Shape`, `Evidence Shape Gate` |
| Hit-Thunder coverage patch idea | Retrieval must enumerate missing axes and search again instead of stopping early | `Coverage Patch Loop`, `External Architecture Ideas`, `engine/references/README.md` |
| mini-artichokes redundant convergence idea | High-risk bindings need independent agreement, especially dates/ranges/reversals/quote spans/recommendations | `Redundant Verification`, `Required Engine Work Packages` |
| memory hierarchy: leaf -> section -> document -> collection -> root | Summaries can help navigation only if every parent tracks child coverage and unresolved gaps | `Hierarchical Memory Tree` |
| graph memory / brain-like relations | Cross-file/time/reference questions require relations, not isolated chunks | `Graph Memory`, `Reference Resolution And Time Policy` |
| loss-minimizing compression | Small models/parsers may compress/extract, but instructions/entities/verbs/dates/negations/references must survive | `Loss-Minimizing Compression`, `Exhaustive Small-Model Passes` |
| multimodal ingestion and alignment | Recordings usually point at materials; transcripts alone are incomplete | `Ingestion Requirements`, `Multimodal mismatch` |
| independent hard benchmarks across domains | A better engine must prove generality, not win one visible test | `Benchmark Requirements`, `Anti-Overfit Gate` |

## Prior Trial Lessons And Failure Patterns

The project memory contains several lessons from beta-6 and related trials. They are carried forward as constraints because they prevent the team from repeating attractive but false shortcuts.

1. **Hot-cache proof is not cold-engine proof.** A fast result after caches are warm does not prove the engine is fast enough for real first-use queries.
2. **Selector-only success can be misleading.** A selector variant may look faster or cleaner in isolation but fail the full app path, change selected source kinds, or starve later evidence.
3. **Worker count alone does not solve latency.** When one selector batch is slow, adding workers only reduces parallel backlog; it does not remove the slow-batch floor.
4. **Lowering keyword rounds is not harmless.** Prior TCM experiments showed evidence composition can change drastically when keyword rounds are reduced.
5. **Late keyword starvation was real.** A broad first round can fill the frontier and prevent later, more specific terms from being considered.
6. **Prompt-size reduction is not automatically better.** It must preserve evidence kinds, overlap, citation quality, and answer usefulness.
7. **Claim count is not enough.** The UI must show candidate/cited claim splits, source windows, and exact highlights.
8. **Summaries are dangerous when treated as memory.** Summaries can index, route, or compress, but final factual claims must trace back to original evidence.
9. **A single wrong binding can ruin everything.** Wrong exam range, wrong "this/that" reference, wrong source ID, or wrong quote span can invalidate a whole answer.
10. **Benchmarks must be hidden/rotating.** If the team optimizes to the known KakaoTalk/snowboard/school examples by name, that is cheating, not a better engine.

These lessons should be read before changing selector size, keyword policy, claim-card construction, source-window behavior, or benchmark definitions.

## Non-Negotiable Principles

1. Original data is always preserved. Summaries, embeddings, graph nodes, and compressed forms are indexes or anchors, never replacements for source text.
2. The answer engine must use selected evidence, not memory summaries alone, for factual claims.
3. Every selected claim must retain provenance: source id, citation, exact quote or span, context summary, claim summary, and source-window coordinates.
4. The system must prefer recall completeness over premature pruning. Importance scoring may prioritize expensive work, but the system must still have an explicit coverage path for all relevant data.
5. A wrong binding at any stage can corrupt the final result. Reference resolution, time ordering, duplicate counting, quote span matching, and source identity must be verified, not assumed.
6. Do not optimize for one benchmark or one known query. Benchmark-targeted hacks are forbidden.
7. Success must be tested through the same user path that the user would use, not only through an isolated internal function.
8. If the user's instruction is ambiguous, the agent or engine must state its interpretation and ask for confirmation before doing risky work.

## Current Engine Boundary

Current entrypoint:

```python
Beta6JobManager.answer_sync(product, query, language="", limit=8)
Beta6JobManager.create_job(product, query, language="", limit=8, session_token, account_subject="")
```

The async product path enters this engine through `POST /api/{product}/jobs`, which calls `Beta6JobManager.create_job(...)` and later exposes status/result through the shared job endpoints. Sync answer exists for tests/dev only.

Current engine inputs:

| Field | Meaning |
|---|---|
| `product` | `ProductProfile` key: currently `islam`, `tcm`, `simli`. |
| `query` | User's natural-language goal/question. |
| `language` | Resolved answer language. If omitted, detected/UI/default language is used. |
| `limit` | Requested selected evidence count. Current beta-6 coerces to effective top-k; default is 100. |
| `ProductProfile.db_path` | Read-only corpus DB path. |
| `ProductProfile.db_shape` | `precedents` or `documents`. |
| `llm_client` | Current default is Lawkey/Gemma4 when configured. Can be disabled for local deterministic selection. |
| `model` | Current production model is `gemma-4-26b-a4b-it`. |
| `runs_root` | Durable artifact root, default `/workspace/bunjum2/religion/runs`. |
| `cache_root` | Batch cache root, currently per-runs-root `_beta6_batch_cache` in app path. |

Current engine output must satisfy `source-grounded-v2`:

```json
{
  "answer": "Markdown with [S#] and/or [C#] citations",
  "answerReadiness": "final_answer",
  "writer": {},
  "selector": {},
  "answerSections": [],
  "citationMap": {},
  "passages": [],
  "selectedEvidence": [],
  "claimCards": [],
  "candidateClaimCards": [],
  "citedClaimCards": [],
  "passageWindows": [],
  "answerPlan": {},
  "coverageReport": {},
  "beta6": {}
}
```

The platform and design layer must not depend on hidden engine internals beyond this result contract.

## Current Beta-6 Shape

The current beta-6 engine stages are:

```text
keyword_generation
candidate_search
source_selection
chunking
claim_cards
answer_plan
writer
coverage
```

Current defaults and shape:

| Setting | Current value/behavior |
|---|---|
| Selected evidence top-k | `LAWKEY_DEFAULT_TOP_K_PRECEDENTS = 100`; effective top-k never below this default unless the code is changed and proven. |
| Keyword count | `10` per round by default. |
| Keyword rounds | up to `3`; minimum rounds default `2`. |
| Islam/TCM frontier target | `max(top_k * 12, 1000)`, normally `1200` for top-k 100. |
| Islam/TCM frontier stop floor | `max(top_k * 8, 600)`, normally `800` for top-k 100. |
| Simli frontier target | `max(top_k * 4, 400)`, normally `400`. |
| Per-keyword FTS limit | `700` by default. |
| Selector candidate limit | Islam/TCM normally up to `1200`, Simli normally `400`. |
| Selector batch size | Islam `100`, TCM `100`, Simli `25`. |
| Selector workers | Islam/default `4`, TCM `6`, Simli `2`, bounded by batch count. |
| Selector timeout | default primary selector timeout `90s`; Simli selector timeout `45s`. |
| Timeout recovery | smaller sub-batches, default recovery workers `min(4, sub_batch_count)`. |
| Selector excerpt bytes | Islam `360`, TCM `560`, Simli/generic `0` unless configured. |
| Islam selector input mode | `raw_excerpt_v1+compact_lines_v1` by default after 2026-05-09. |
| TCM/Simli compact lines | default off unless `RELIGION_SELECTOR_COMPACT_LINES=1`; requires cold proof before promotion. |
| Claim analyzer | chunk-based by default, source mode remains available by env fallback. |
| Claim analyzer source limit | default 100. |
| Claim analyzer source chars | Islam `900`, others `1400` per source in source analyzer; chunk analyzer has separate chunk char defaults. |
| Chunk token budget | `100000`. |
| Answer planner timeout | `90s`. |
| Minimum answer chars | Islam `2200`, TCM `2400`, Simli `1500`; must be source-grounded, not filler. |

These numbers are not arbitrary. Do not change them for speed unless the replacement passes the promotion gates in this document.

## Current Durable Artifacts

Each run must be inspectable and resumable. Current files under `runs/<jobId>/`:

```text
request.json
status.json
selected_records.json
selector_meta.json
claim_cards.json
candidate_claim_cards.json
cited_claim_cards.json
passage_windows.json
claim_analyzer_meta.json
answer_plan.json
coverage_report.json
chunk_plan.json
prompt_input.json
result.json.pending
result.json
```

Durable queue rows:

```text
runs/_beta6_queue/<jobId>.json
runs/_beta6_queue/.<jobId>.claim.lock
```

Every future engine must provide equivalent artifact inspectability or a documented versioned replacement.

## Required Evidence Objects

### Selected Evidence

Each selected source exposed to the UI/writer must include:

```json
{
  "id": "canonical source id",
  "label": "S1",
  "title": "...",
  "citation": "...",
  "authorityBody": "...",
  "date": "",
  "topic": "",
  "type": "",
  "dataset": "",
  "path": "",
  "url": "",
  "score": 0.0,
  "excerpt": "bounded text preview",
  "language": "",
  "school": "",
  "tradition": "",
  "sourceKind": "",
  "authorityLevel": 0,
  "authorityLabel": ""
}
```

Optional selector-ledger enrichments:

```json
{
  "selectorContextSummary": "what context this source belongs to",
  "selectorClaimSummary": "what this source contributes",
  "selectorQuoteCandidate": "possible exact quote",
  "selectorStance": "support|limit|variant|gap|school_position",
  "selectorSourceRole": "scripture|commentary|guideline|..."
}
```

### Claim Card

Each claim card must include:

```json
{
  "claimId": "C1",
  "label": "S1",
  "sourceId": "canonical source id",
  "citation": "human citation",
  "role": "source role",
  "claimAxis": "what issue axis this card covers",
  "stance": "support|limit|variant|gap|school_position|source_claim",
  "contextSummary": "source context",
  "claimSummary": "what the quote contributes to the user query",
  "quote": "exact consecutive substring from the source",
  "span": {"start": 123, "end": 180, "exact": "same quote"},
  "quoteVerified": true,
  "analysisSource": "llm_claim_analyzer or deterministic_source_card",
  "quoteMatch": "exact|retry|force_match",
  "school": "",
  "tradition": "",
  "sourceKind": ""
}
```

Claim cards are the bridge between selected memory and answer writing. They must be rich enough that the writer can choose useful quoted passages while the UI can explain why each citation matters.

### Passage Window

Each quote-bearing claim must map to a bounded source window:

```json
{
  "claimId": "C1",
  "sourceId": "canonical source id",
  "windowStart": 0,
  "windowEnd": 900,
  "text": "bounded original text",
  "highlightStart": 100,
  "highlightEnd": 155,
  "hasBefore": true,
  "hasAfter": true
}
```

The exact quote must be visible and highlighted. Context expansion must be incremental and bounded.

## Universal Retrieval Problems The Engine Must Solve

The system must solve these across law, school materials, religion, medicine, psychology, and future domains:

1. **Atomic unit too large:** a file, lecture transcript, PDF page, or HWP section can exceed one LLM call. The engine must split it without losing order, references, headings, images/tables, or quoteability.
2. **Cross-file references:** phrases like "last time", "two weeks ago", "as said above", "see file 3", "tomorrow", "the earlier slide", and pronouns must be resolved using chronology and document relationships.
3. **Task-specific salience:** what matters depends on the user goal. For exams, raw solved problems, announced exam range/date, professor emphasis, and problem style may matter more than generic summaries.
4. **Order, time, and duplicates:** repeated mentions may be evidence, not noise. Counts must not double-count duplicated summaries. Corrections, reversals, validity windows, and chronology must be modeled.
5. **Core conclusion risk:** the engine must not miss or invert a document's main conclusion.
6. **Cascading binding error:** a single wrong link, transcript error, exam-range reversal, or source-reference mapping can ruin the final result. Critical bindings need redundant verification.
7. **Multimodal mismatch:** recordings often refer to slides, PDFs, HWP handouts, drawings, tables, or circuit images. The engine must align audio/video transcripts to the source materials when possible.
8. **Recommendation accuracy:** recommendation tasks must aim for expert-level selection from the full corpus, not merely semantically similar retrieval.

## Concrete Failure Modes To Eliminate

The engine team should treat the following as the real problem statement, not as optional polish. A system that answers common questions but fails one of these cases is not yet the complete memory engine.

| Failure mode | Example user request | Required countermeasure | Required output evidence |
|---|---|---|---|
| Oversized source unit | "이 3시간 강의에서 시험 문제만 뽑아와" | Leaf-level splitting with stable order, headings, timestamps, and parent document IDs | Leaf span IDs, parent chain, order index, omitted-span report |
| Lost cross-reference / 지시어 | "저번 시간에 말한 그 회로", "앞서 말한 범위" | Reference resolver over chronology, file links, speaker turns, slide/audio alignment, and coreference | `resolvedReferences[]` with confidence, supporting spans, unresolved items |
| Duplicate confusion | Same PDF reuploaded, transcript repeats slide text, quote appears in multiple books | Separate exact duplicate, near duplicate, semantic duplicate, and repeated-mention ledgers | `duplicateLedger`, `countPolicy`, canonical source ID, repeated evidence count |
| Time or reversal error | Professor first says midterm covers Ch.1-4, later changes to Ch.1-3 | Temporal graph with validity windows and supersedes edges | `timeline[]`, active statement, superseded statements, conflict proof |
| Task-specific salience loss | Generic summary misses solved problems, exam hints, professor style | Goal interpreter that creates coverage axes before retrieval | `coverageAxes[]`, satisfied/weak/missing axis report |
| Wrong source binding | A quote is attributed to the wrong file/chapter/speaker | Redundant binding check using source ID, quote span, metadata, and independent pass | quote verification status, alternate candidates, disagreement report |
| Multimodal mismatch | Audio says "this graph" while the graph is in a PDF or image | Transcript-to-document alignment with timestamps, slide/page/image IDs, OCR/object extraction | aligned media spans, image/table IDs, transcript timestamp |
| Recommendation shortcut | "100만 개 중 제일 맞는 변호사/교수/자료 추천해" | Candidate generation + exhaustive coverage/reranking + anti-nearest-neighbor audit | top-k rationale, considered pool, rejected-near-miss reasons |
| Absent evidence hallucination | User asks for a date that was never stated | Negative retrieval path with explicit "not found" proof | inspected scopes, missing-axis report, no-evidence status |

## Required Engine Work Packages

These are the concrete modules a new or improved engine must eventually provide. They may be implemented inside beta-6 first, but the inputs/outputs must stay inspectable so another team can replace one module later.

| Module | Input | Output | Must prove |
|---|---|---|---|
| Ingestion canonicalizer | raw PDF/HWP/DOCX/PPTX/XLSX/audio/video/image/database rows | immutable raw asset registry, canonical document IDs, extracted leaf spans | raw files preserved; no parser output replaces original |
| Leaf splitter | canonical documents and media tracks | ordered leaf nodes with text/image/table/audio spans | no lost headings, page numbers, timestamps, table cells, or image references |
| Deduplication and repetition ledger | leaf nodes, hashes, embeddings, metadata | exact/near/semantic duplicate clusters plus repeated-mention counts | duplicates are not double-counted unless repetition itself is relevant |
| Reference resolver | leaf nodes, chronology, speaker turns, document graph | resolved and unresolved cross-references | "저번/앞서/이것/그 자료/file 3" bindings are explicit and testable |
| Temporal/provenance graph | facts, claims, references, revisions | graph edges with validity windows and provenance | reversals and supersessions are visible, not overwritten |
| Hierarchical memory tree | leaf nodes and summaries | root/collection/document/section/leaf memory hierarchy | every summary lists covered children and unresolved gaps |
| Multi-index retrieval planner | user goal, product profile, corpus stats | keyword/vector/BM25/graph/table/image/audio search plan | all coverage axes have a retrieval strategy |
| Frontier collector | search plan and indexes | audited candidate frontier | candidate count, per-axis coverage, source-kind diversity |
| Selector/reranker | audited candidates and goal axes | selected evidence set, normally 100 records | full audited frontier considered; no late-keyword starvation |
| Claim-card builder | selected evidence and original spans | claim cards with quote, context summary, claim summary, span | writer can quote and UI can open exact source window |
| Coverage auditor / patcher | goal axes, selected evidence, claim cards | missing/weak coverage report and follow-up searches | missing axes cause another search or explicit gap, not invented content |
| Answer planner and writer handoff | claim cards, coverage report, user language | bounded answer plan and cited/candidate claim splits | final text uses original evidence, not summaries alone |
| Recommendation ranker | selected candidate pool, task criteria, user constraints | ranked options with reasons and rejected alternatives | expert-like selection, not just semantic similarity |
| Benchmark harness | hidden/rotating tasks and artifacts | comparable reports across domains | anti-overfit, cold latency, faithfulness, source-window proof |

## Duplicate, Count, And Identity Policy

The engine must not treat "remove duplicates" as a single boolean. It needs a visible ledger:

- **Exact duplicate:** identical bytes or identical normalized text. Keep one canonical source ID, but retain all file locations.
- **Near duplicate:** same document with OCR/parser differences. Merge for retrieval, preserve variants for verification.
- **Semantic duplicate:** same claim expressed differently. Do not collapse unless the task does not care about repeated mention count.
- **Repeated mention:** the same fact repeated across lectures or files. For exam/professor-style tasks, repetition may increase importance and must be counted.
- **Citation duplicate:** the same quoted source cited by many secondary sources. Preserve citation chain; do not pretend every secondary source is independent primary evidence.

Outputs touching duplicates must include:

```json
{
  "duplicateLedger": [],
  "canonicalSourceId": "...",
  "sourceLocations": [],
  "countPolicy": "dedupe_for_identity | count_repetition | preserve_citation_chain",
  "repetitionCount": 0
}
```

## Reference Resolution And Time Policy

The engine must explicitly resolve references before summarizing or answering when the task depends on them.

Required reference types:

- pronouns and Korean omitted subjects;
- "앞서/위에서/저번/다음/내일/2주 전/파일3/슬라이드 오른쪽/이 그림/그 문제";
- speaker references in transcripts;
- document-to-document citations;
- audio/video timestamps that point to slides, handouts, tables, or board drawings;
- corrections, retractions, and changed exam ranges.

Required output:

```json
{
  "resolvedReferences": [
    {
      "surface": "저번 시간에 말한 회로",
      "resolvedTo": "doc:lecture-03-slide-12:image-1",
      "confidence": 0.87,
      "evidenceSpans": ["transcript:lecture-04:00:12:31", "slide:lecture-03:12"],
      "alternatives": [],
      "status": "resolved"
    }
  ],
  "unresolvedReferences": []
}
```

If a critical reference is unresolved, the engine should ask a clarifying question or mark the answer as incomplete instead of guessing.

## Required Algorithmic Capabilities

Future engines should combine these ideas where proven:

### Loss-Minimizing Compression

- Compress chunks only as an index layer.
- Preserve instructions, named entities, verbs, negations, quantities, dates, and source references.
- Track what was compressed, omitted, uncertain, or unresolved.
- Use original text for final quoting.

### Hierarchical Memory Tree

Build a tree:

```text
root corpus summary
  -> collection/domain summaries
    -> document summaries
      -> section/chunk summaries
        -> leaf original text/image/table/audio spans
```

Each parent summary must list children coverage, unresolved references, time range, duplicate policy, and provenance.

### Graph Memory

Build relationships between chunks and documents:

```text
translation_of
commentary_on
cites
applies
explains
same_topic
contrasts
localizes
supersedes
refers_to_previous
refers_to_next
audio_mentions_slide
image_depicts
table_supports
duplicate_of
near_duplicate_of
```

Graph edges need confidence, evidence, and source spans. Time-valid facts need validity windows.

### Coverage Patch Loop

Borrow the principle of coverage patching, including the user-owned Hit-Thunder idea:

1. define the user goal;
2. enumerate required coverage axes;
3. mark which chunks/files/evidence satisfy each axis;
4. detect missing/weak axes;
5. search again or inspect unresolved areas;
6. repeat until all axes are satisfied or explicitly marked unavailable.

The loop must stop with a clear retrieval gap, not with invented content.

### Redundant Verification

Use redundancy like `mini-artichokes` style convergence:

- run independent passes with different prompts/models/indexes when the decision is high impact;
- require agreement for critical bindings such as exam dates, reversed ranges, quoted spans, or recommendation top choices;
- surface disagreement as a gap instead of hiding it.

User-owned references:

- Hit-Thunder coverage patch idea: https://github.com/pineapplesour/Hit-Thunder
- mini-artichokes redundancy/convergence idea: https://github.com/pineapplesour/mini-artichokes

## Exact Benchmark Tasks From User Requirements

These are examples the benchmark suite must eventually encode. Do not tune only to these strings; generate paraphrases, language variants, and hidden equivalents.

| Area | Required hard task |
|---|---|
| Law | Find the exact KakaoTalk-related evidence; pass the military-key benchmark; pass the snowboard benchmark; preserve exact quote/context and citation source window. |
| School/course | "문제만 다 뽑아와"; "이 문제 설명한 거 그대로 가져와"; "시험범위 가져와"; "시험 언제 보는지 가져와"; "회로 사진 그대로 가져와"; "교수가 중요하다고 말한 것 다 가져와"; "교수가 어떤 문제 내는 성향일지 판단할 근거 다 가져와". |
| Religion | Create Islam/Hindu/Buddhist/Christian hard questions that existing engines and base models miss; for Christianity, separate Catholic, Orthodox, Anglican, and Protestant denominational positions while testing scripture/commentary/tradition hierarchy and multilingual terms. |
| TCM | Separate classic source, formula/herb record, contraindication, safety boundary, and modern reference without prescribing. |
| Simli | Separate DSM/ICD/guideline/research/case material; preserve crisis/safety boundaries; do not diagnose. |
| Recommendation | Match the selection an expert would make after reading the whole corpus, including near-miss rejection reasons. |
| Negative evidence | Prove absence when a claimed date/range/quote/image is not in the corpus. |

### Exhaustive Small-Model Passes

Small local LLMs, parsers, OCR/ASR tools, and streaming processors may do exhaustive first-pass extraction if they are cheaper than large model calls. The large model should spend tokens on unresolved high-value decisions, not on re-reading everything blindly.

## Ingestion Requirements

The memory engine must support or have pluggable ingestion for:

| Data type | Requirement | Candidate references from user research |
|---|---|---|
| PDF | Reading order, tables, formulas, charts/images, scanned OCR, header/footer filtering | OpenDataLoader PDF, Docling, Marker, RAGFlow parsers |
| HWP/HWPX | Korean document text, tables, images/assets, headings, malformed files | kordoc, JDoc, unhwp, DocsRay |
| DOCX/PPTX/XLSX | Structured text, slides, tables, speaker notes | Docling, OmniParse, kordoc |
| Audio/video | ASR, timestamps, diarization, VAD, alignment to referenced documents | WhisperX, pyannote.audio, OmniParse, DocsRay |
| Images/diagrams | OCR/layout, charts, circuit diagrams, visual source spans | dots.ocr, CircuitVision, datasheet-cli |
| Duplicates | Exact hash, near duplicate, semantic duplicate, provenance merge | Epstein Pipeline-style 3-pass dedup |
| Coreference | Korean/English pronouns, ellipsis, speaker references, "this/that" | KoreanCoreferenceResolution, KoBookNLP, fastcoref |

No single public repo currently proves perfect all-format extraction. The engine should be modular so better parsers can be swapped per data type.

## External Architecture Ideas To Evaluate

These are references to study and test, not automatic dependencies:

| Candidate | Useful idea | Caution |
|---|---|---|
| RAGFlow | Deep document understanding, template chunking, traceable citations, fused recall/rerank, KG/RAPTOR/PageIndex/retrieval tests | Product-like but resource/security/version review required. |
| KAG | Knowledge-chunk mutual indexing, schema-constrained knowledge construction, logical-form-guided reasoning, multi-index | Strong fit for reference/time/logic issues; repo may not be fully self-contained for all parts. |
| Graphiti | Temporal graph, raw episode provenance, incremental updates, bi-temporal tracking | Useful for time/reversal/provenance; validate local/model/security constraints. |
| LightRAG | Lightweight graph RAG modes and reranker path | Needs strong LLM/reranker and careful auth/security review. |
| Hindsight | Parallel semantic/BM25/graph/temporal recall with fusion and rerank | Good anti-missing pattern. |
| Pathway llm-app | Live sync search infra for file/db/cloud changes | More infra than full reasoning engine. |
| WeKnora | Enterprise document Q&A, parent-child chunking, preview, tenant isolation | Useful UI/product reference. |
| Semantica/Cognee | Provenance/temporal/reasoning framework ideas | Evaluate maturity before adoption. |
| Microsoft GraphRAG | Community hierarchy, Global/Local/DRIFT ideas | Foundational/demo-like; not a drop-in full product. |
| HippoRAG | Multi-hop/sense-making memory core | Operational pieces may remain. |

Any candidate must be evaluated with this project's benchmarks and source-window contract, not only README claims.

## Benchmark Requirements

The engine is a general engine with light domain adaptation. It must be tested across independent domains.

Current known benchmark families from user instructions/memory:

| Domain | Benchmark/task type | Requirement |
|---|---|---|
| Legal | KakaoTalk evidence, military key benchmark, snowboard benchmark | Must find precise evidence and case/materials without overfitting to benchmark names. |
| School/course materials | "Extract all problems", "bring exact explanation of this problem", "exam range", "exam date", "important statements", "professor problem style", "circuit image" | Must support transcripts, slides, files, images, chronology, and exact quotes. |
| Islam | Questions current engines/models miss; school/sect/source distinctions | Must avoid binding fatwa, preserve Arabic/source hierarchy, retrieve scripture/commentary/fiqh where relevant. |
| Hindu | Independent hard questions current systems miss | Must handle Sanskrit/transliteration/commentary/tradition distinctions. |
| TCM | Herb/formula/classic/safety contraindication queries | Must not prescribe; must separate classics, materia medica, formula, safety, modern references. |
| Simli | Clinical/DSM/ICD/guideline/research/case distinctions | Must not diagnose; must prioritize safety and guideline evidence. |
| Recommendation | Expert top choice from huge corpus | Must approximate expert reading all data, not just nearest-neighbor similarity. |

Benchmark rules:

- Keep hidden or rotating test sets so the engine cannot memorize fixed queries.
- Include adversarial variations, paraphrases, different languages, typos, and misleading broad terms.
- Include negative cases where evidence is absent.
- Evaluate recall, exactness, provenance, citation highlight, answer faithfulness, time/cost, and UI path.
- A variant promoted for one domain must not regress another active product without explicit user approval.

## Promotion Gate For A Better Engine

A new engine or major beta-6 variant can replace the current default only if it passes all relevant gates.

### Mechanical Contract Gate

- Produces `source-grounded-v2` or a documented backward-compatible version.
- Preserves selected source labels and source-window IDs.
- Produces claim cards with exact quote spans.
- Persists durable artifacts and cache metadata.
- Supports async job status/progress/cancel.

### Evidence Shape Gate

Compare against latest accepted baseline:

- selected count remains 100 unless the user explicitly approves a new handoff count;
- candidate frontier and audited candidate counts are recorded;
- source-kind/tradition/school diversity is preserved where the baseline had it;
- selected overlap meets a chosen threshold when the same query/corpus is used;
- new evidence must be explainably better, not merely different.

Current selector comparison tools already enforce some of this:

```text
tools/compare_selector_probe_variants.py
  --require-same-selector-shape
  --require-baseline-kinds
  --require-variant-cold-selector
  --require-clean-selector
  --require-prompt-reduction
  --speed-floor <artifact>
```

### Cold-Engine Latency Gate

Speed claims must use fresh cold-engine artifacts:

- keyword/search/selector/claim/answer-plan/writer cache hits must be zero or explicitly accounted for;
- missing timing fields fail the proof;
- total latency should be checked as `max(engineTotalSec, wallElapsedSec)`;
- source-selection latency must be measured separately.

Current tools:

```text
tools/verify_app_path_gemma4.py --require-cold-engine-cache --max-total-sec ... --max-source-selection-sec ...
tools/verify_app_path_budget_matrix.py --require-cold-engine-cache --require-products islam,tcm,simli ...
tools/compare_app_path_variants.py --max-total-sec ... --max-source-selection-sec ...
```

### Full User-Path Gate

At least one real product path must pass:

```text
landing input -> chat route -> visible progress -> final answer
-> citations -> source-window exact highlight -> local chat persistence
```

For web/PWA use browser submit verifier. For native, use Android/iOS runtime/WebView verifier. API-only success is not enough for user-path success.

### Anti-Overfit Gate

- Run at least one domain not used during variant design.
- Run at least one hidden or newly created hard case.
- Include a negative case.
- Inspect actual answer text, not only counts.

## Current Known Engine Status

Current strengths:

- shared Lawkey/Gemma4 beta-6 path exists for Islam/TCM/Simli;
- async durable jobs, progress, cancellation, local chat persistence, source-window UI, and Android emulator WebView proofs exist;
- top-k 100 selected source handoff exists;
- claim cards, answer plan, citation map, passage windows, and cited/candidate claim splits exist;
- prompt-size telemetry and comparator gates now prevent several false speed claims;
- 10k durable admission and 1k LLM-disabled drain are proven.

Current blockers:

- cold full-answer latency is still minutes on hard queries;
- cold Islam source-selection remains far above `<=30s` in latest proof;
- selector worker-count tuning alone is ruled out by latency analyzer;
- full 10k Gemma4 answer throughput is not proven;
- benchmark coverage is too small;
- real low-end Android hardware and iOS proof are missing;
- full multimodal ingestion and cross-file reference resolution are not implemented as a general engine.

Important negative findings:

- Lowering TCM min keyword rounds changed evidence composition drastically and must not be defaulted.
- Shrinking selector excerpt size can pass selector-only speed but fail full app-path or lose evidence kinds.
- Clean raw + role diversity failed Islam default promotion due to overlap/prompt/timeout issues.
- Selector evidence capsule/ledger variants were useful experiments but failed evidence-shape gates for default promotion.
- Hot-cache app-path artifacts cannot be cited as cold latency proof.

## Required Next Engine Direction

The next serious engine work should focus on structural recall/latency improvements that preserve evidence quality:

1. Hierarchical or two-stage selector that reduces primary prompt cost without reducing audited frontier coverage.
2. Better source summaries/ledgers that are proven not to distort selected evidence.
3. Graph/tree memory that resolves cross-document references and time order before final retrieval.
4. Coverage-driven missing-axis search that explicitly proves what was inspected.
5. Multimodal ingestion and transcript-to-document alignment.
6. Recommendation-specific ranking that uses exhaustive/coverage evidence, not only vector similarity.
7. Broader benchmark harness across law, school, Islam, Hindu, TCM, and Simli.

## Standalone Engine Interface For Future Replacement

Any replacement engine should implement this conceptual interface even if the internal code differs:

```json
{
  "request": {
    "schemaVersion": 1,
    "product": "islam",
    "query": "user goal/question",
    "language": "ko",
    "limit": 100,
    "corpus": {
      "dbPath": "/absolute/path/to/db.sqlite3",
      "dbShape": "precedents"
    },
    "runtime": {
      "runDir": "/absolute/path/runs/job-id",
      "cacheRoot": "/absolute/path/runs/_beta6_batch_cache",
      "llmProvider": "lawkey_gemini_generate_content",
      "model": "gemma-4-26b-a4b-it"
    },
    "policy": {
      "productSafetyNotice": "...",
      "answerMustUseOriginalEvidence": true,
      "noBindingFatwaOrDiagnosis": true
    }
  }
}
```

Response:

```json
{
  "engine": {"name":"new-engine","contractVersion":"source-grounded-v2"},
  "selector": {
    "status": "completed",
    "candidateCount": 1200,
    "auditedCandidateCount": 1200,
    "selectedCount": 100,
    "selectedIds": [],
    "cache": {},
    "timings": {}
  },
  "selectedEvidence": [],
  "claimCards": [],
  "candidateClaimCards": [],
  "citedClaimCards": [],
  "passageWindows": [],
  "answerPlan": {},
  "coverageReport": {},
  "answer": "Markdown answer",
  "writer": {},
  "artifacts": {}
}
```

If an engine cannot produce `answer`, it may return `answerReadiness = evidence_selected_writer_required`, but it must still produce selected evidence and claim cards.

## Development Workflow Requirements

Before changing engine behavior:

1. Read `memory/MEMORY.md`, `tasks/lessons.md`, and this document.
2. Check WSL memory before broad searches or heavy runs.
3. Create a checkpoint.
4. Add a failing test or verifier for the claimed behavior.
5. Make the smallest structural change that addresses the root cause.
6. Run focused tests.
7. Run a real artifact proof when behavior depends on LLM/provider/corpus.
8. Compare against baseline for evidence shape and latency.
9. Update `tasks/todo.md`, daily memory, lessons/wins if applicable.
10. Do not claim completion until verification output proves it.

## Minimal Verification Commands

For beta-6 code changes:

```bash
python3 -m py_compile shared_platform/beta6.py tests/test_beta6_runtime.py
pytest tests/test_beta6_runtime.py -q
```

For app-path proof changes:

```bash
pytest tests/test_app_path_gemma4_verifier.py tests/test_app_path_budget_matrix.py tests/test_app_path_variant_comparator.py -q
```

For selector variant proof:

```bash
python3 tools/probe_beta6_selector.py ... --require-cold-selector --output runs/<variant>.json
python3 tools/compare_selector_probe_variants.py --baseline runs/<baseline>.json --variant runs/<variant>.json --require-same-selector-shape --require-baseline-kinds --require-variant-cold-selector --require-clean-selector --output runs/<compare>.json
```

For full product path:

```bash
python3 tools/verify_app_path_gemma4.py ... --require-cold-engine-cache --output runs/<artifact>.json
python3 tools/verify_browser_submit_path.py ... --output runs/<artifact>.json
```

For final objective:

```bash
python3 tools/verify_completion_audit.py --json --output runs/completion_audit_current_<date>.json
```

## Memory And References To Read

Required repo references:

```text
memory/MEMORY.md
memory/2026-05-06.md
memory/2026-05-07.md
memory/2026-05-08.md
memory/2026-05-09.md
tasks/requirements-audit.md
tasks/completion-audit-2026-05-08.md
tasks/lessons.md
tasks/wins.md
shared_platform/beta6.py
shared_platform/search.py
shared_platform/engine_contract.py
docs/religion-db-architecture.md
```

User-provided research references to evaluate when designing a new engine:

```text
RAGFlow, KAG, Graphiti, LightRAG, Pathway llm-app, WeKnora, Hindsight,
Semantica, Cognee, Microsoft GraphRAG, HippoRAG,
DocsRay, OmniParse, kordoc, JDoc, unhwp, OpenDataLoader PDF,
Docling, Marker, WhisperX, pyannote.audio, Epstein Pipeline,
KoreanCoreferenceResolution, KoBookNLP, fastcoref,
dots.ocr, CircuitVision, datasheet-cli,
Hit-Thunder coverage patch idea, mini-artichokes redundancy idea.
```

These references are not proof. They become useful only after local tests show they improve this project's evidence quality, latency, robustness, or ingestion coverage.
