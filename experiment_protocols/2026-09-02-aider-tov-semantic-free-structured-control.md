# Frozen matched-control protocol: semantic overlap versus structured falsification

Status: frozen before any semantic-free structured-control model call. The
existing Plain, Graph, ordinary-repair, generic verified-union, and TOV-v2
outcomes are already known. This is therefore a review-triggered secondary
mechanism control, not a new prospective confirmation of TOV.

## Question

Does TOV v2 outperform a final adjudicator that has the same verified union,
candidate evidence, unresolved-task ledger schema, counterexample-based
falsification, two completion audits, byte-exact anchor restoration, model,
effort, call count, and output cap, but is prohibited from using semantic
agreement or disagreement among candidates as evidence?

This control addresses the ambiguity between a semantic-overlap effect and a
generic effect of more structured output, falsification, or repeated auditing.
The only intended prompt-level treatment is whether candidate convergence and
disagreement guide the decision.

## Frozen artifacts and complete denominators

Reuse the immutable candidate outputs and task/evaluator freezes from:

- all 30 official Rust tasks in
  `runs/aider-rust30-tov-v2-development-20260902`;
- all 34 official Python tasks in
  `runs/aider-python34-tov-v2-confirmation-20260902`;
- all 26 official C++ tasks in
  `runs/aider-cpp26-tov-v2-extension-20260902`.

No candidate is rerun. No task, language, failure trace, anchor, or existing TOV
outcome may be selected, removed, replaced, or topped up. Every complete-track
control result remains in the analysis.

## Exact new calls

Run exactly one `semantic_free_structured_verified_union` whole-track call in
the fixed order Rust30, Python34, C++26. Every call uses `gpt-5.6-luna`, medium
reasoning, web disabled, `CODEX_HOME=/home/pineapple/.codex-new-account`, a
30-minute agent cap, and a 30-minute evaluator cap. No per-task call, retry, or
result-led prompt change is allowed.

The runner SHA-256 is
`2431af17962f6b6b657d0d9a2341d859905b1ac3c41448d9d64d3a5099499950`.
The control starts from the same deterministic verified union and uses the same
fixed passing-candidate priority `ordinary repair > Graph > Plain` as TOV. The
same adapter restores every anchor byte after the call.

The control must write one ledger row per unresolved task using the same fields
as TOV: task ID, candidate outcomes, fault locations, violated invariants,
smallest counterexample classes, edit intents, semantic-overlap field,
falsification attempt, selected evidence, and final action. Its
semantic-overlap field must be the constant `withheld-by-control`; candidate
convergence or disagreement cannot be used as confidence, routing, or
authorization evidence. It performs the same two completion audits.

## Frozen analysis

The primary secondary contrast is existing TOV v2 minus the new semantic-free
structured control over all 90 disjoint official tasks. Report correct counts,
rescues, harms, percentage-point difference, one- and two-sided exact paired
tests, and a 50,000-draw paired bootstrap stratified by track with seed
20260902. Report each complete track separately regardless of direction.

Also verify before interpretation:

- identical candidate patches, bounded failure evidence, and anchor map;
- zero byte mismatch for all restored anchors;
- ledger IDs and order exactly equal the unresolved task list;
- the semantic-overlap field is `withheld-by-control` for every row;
- no forbidden path changed.

Task-level inference conditions on one realized whole-track call per arm. The
language-cluster sign result over only three tracks must be reported. Because
the control was commissioned after TOV outcomes and a reviewer request were
known, a favorable result is secondary mechanism evidence and cannot be labeled
prospective confirmation. Runtime and token use are reported; no exact-token or
efficiency claim is allowed.

Benchmark preparation, masking, anchoring, and ledger validation are provenance
and validity checks, not paper contributions.
