# Review Court v16 — completed adjudication with product-gate failure

## Run status

- Run ID: `run_2638f279442886be8ff6f3ed`
- Model: `gpt-5.6-luna`, high reasoning
- Terminal status: `PRODUCT_FAIL`
- Failure code: `RUNTIME_HARD_GATES_FAILED`
- The pipeline completed upload, parse, map, 3-role specialist review,
  22-finding dual verification, consensus, rating, composition, and final audit.
- This is not an infrastructure failure and not a publishable Court export.
  The composed review was rejected because its own prose audit returned
  `NON_CONCISE_PROSE`, `not_concise`, and `embedded_assessment_rationale`.

The run used a process-local retry around deletion of isolated temporary Codex
directories. No prompt, review schema, verification, consensus, rating,
composition, or paper-scoring logic was changed.

## Ratings produced before the failed export gate

| Dimension | Score |
|---|---:|
| Soundness | 2/4 |
| Presentation | 3/4 |
| Significance | 3/4 |
| Originality | 3/4 |
| Overall recommendation | 3/6 |
| Confidence | 5/5 |

## Verified strengths

- A1--A5 give a clear conditional test-label-preservation property because
  complete passing task states, rather than intersected diff fragments, are
  promoted.
- The study includes Generic and semantic-free controls, complete official
  tracks, rescue/harm accounting, compute, cluster caveats, and artifact hashes.
- The paper correctly narrows its main support to system effectiveness rather
  than a repeatable causal effect of semantic overlap.

## Verified weaknesses and requested revisions

- Five-call versus one-/two-call headline comparisons are effectiveness, not
  compute-matched algorithmic comparisons.
- The original recursive comparison is post hoc; the prospective Go Generic
  arm is transport-null and its replacement remains sensitivity-only.
- TOV and Direct are call-matched but not token- or latency-matched.
- Whole-track calls make task-level p-values conditional on realized sessions.
- The final-arm indicator `V_F(t)`, deterministic promotion state, and model-call
  accounting should be reconciled in one place.
- Exact prompts, ledger schema, parsing rules, and fail-closed behavior should
  be easier to locate.
- Included prompt-level baselines should be distinguished from full external
  implementations of contemporary program-repair systems.

## Stage hashes

- reviewing: `278ada618f050b5b013abf71b18bcefb2955a70681ba3c14c4a522bf24fd0133`
- verifying: `3ff009e3220bf7d785c66fb63ae84ae0b4d13cd87bedee1c2e21d9b0946fac7c`
- composing: `2116f55b9ba8c6c8cd80167ffc88cf821215722fb9186933853d1f683474057e`
- terminal: `2f3ce4f3b58741c30ed96a6339ba8cc7eafa474fa8c17920c69af31b019e4fad`

