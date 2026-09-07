# The FoveaContext idea and what was actually implemented

## Source of the idea

The exact, unabridged user transcript is preserved at [original_user_idea_chat_2026-09-06.md](original_user_idea_chat_2026-09-06.md). It is the source of the FoveaContext proposal, including the requests to test a visual atlas, image/neuralese/text mixtures, overlap effects, graph structure, and a large legal-case memory. This document is the interpretation and implementation ledger; the transcript itself is intentionally not rewritten.

## User-proposed design, in brief

The proposal was not merely “turn text into PNG.” It described a memory system that:

- stores original events and source versions outside the model context;
- compiles code, logs, and conversations into exact text, structured text, visual overview, readable image, or reference-only views;
- uses a hierarchical visual atlas so a model can survey a large backing store and selectively open exact source regions;
- attaches each visual region to a source range, snapshot/hash, and provenance record;
- requires an exact, current source read before edits or other high-risk actions;
- keeps an epoch/prefix stable to preserve prompt-cache reuse and appends updates instead of repainting old views;
- chooses image versus text using total task cost, retrieval cost, cache effects, and error risk;
- optionally represents relationships as graphs or compact visual maps;
- treats a learned “neuralese” visual codec and a very large legal corpus as research hypotheses, not assumptions.

The intended scientific test was an end-to-end comparison against plain Codex/Luna and strong known controls, with official/public benchmark denominators and no cherry-picking.

## Public implementation in this snapshot

The implemented portion is deliberately narrower and testable:

| Proposed component | Public implementation | Status |
| --- | --- | --- |
| Image/text representation choice | Deterministic code renderer and paired image/text prompt runners | Implemented and smoke-tested |
| Visual overview/readable view distinction | Canonical rendering and region metadata in the C++26 assay | Implemented for the assay |
| Exact source anchoring | Full-denominator Aider C++26 sessions with immutable task IDs, source anchors, hashes, and read-only evidence checks | Implemented for the assay |
| Overlap/independent-route comparison | Text and image arms, paired G/O scoring, and predeclared interaction gates | Implemented; latest gate failed |
| Graph/relationship views | Existing dependency, obligation, ToV, verifier, and overlap tooling | Implemented in development tools; not claimed as one finished Fovea product |
| Cache-aware epochs | Protocol/design documentation and campaign controls | Design-level; no provider-wide causal claim |
| Edit-time read ticket/version enforcement | Native permission and evidence tests; source-level checks | Partial harness prototype, not a universal shell sandbox |
| Hierarchical atlas over tens of millions of tokens | Architecture described in the source idea | Not implemented |
| Learned neuralese/latent visual codec | Research hypothesis only | Not implemented |
| 600k-case legal memory | Public manifests/governance notes only | Not completed; raw corpus excluded |

The latest implementation is therefore an **experimental representation assay**, not a claim that a complete FoveaContext product already exists.

## Latest representation experiment

`tools/run_aider_cpp26_image_representation.py` and its companion tests run a frozen, full official C++26 Aider denominator. The protocol keeps the task set fixed, separates text/text, image/image, and mixed routes, and evaluates the resulting repositories with the same evaluator. The public report is [here](../benchmark_reports/2026-09-06-aider-cpp26-image-representation/RESULTS.md).

The report records completion and all arm totals, but also records failed gates. The mixed route did not beat the strongest pure route, and the planned interaction threshold was not met. This is useful negative evidence: it prevents the paper from turning “images plus overlap” into an unsupported universal claim.

## How this connects to the paper

The `paper_revision/` tree contains Markdown source, evidence ledgers, review notes, protocols, and aggregate results. The paper should present:

1. the overlap mechanism and its strongest supported setting;
2. the official benchmark denominator and evaluator contract;
3. the image representation as a bounded hypothesis with the negative C++26 result;
4. development versus confirmation separation;
5. legal-corpus work as a future/blocked validation path, not an achieved result.

The public snapshot intentionally does not include the original DOCX files, private review-agent traces, hidden answer keys, or raw per-call receipts. Their public-safe Markdown/evidence counterparts are included where available.

