# Aider Java20 hidden-test confirmation

## Result

On a frozen SHA-ranked 20-task Java subset from the official Aider Polyglot
benchmark, one-call Plain Luna and one-call Graph each solved 3/20 tasks. A
matched structured second pass starting from the Graph patch and its complete
official failure stdout solved 7/20 (35%): +4 tasks and +20 percentage points
versus both Plain and Graph, with four rescues and no harms. The paired exact
test is one-sided `p=.0625`, two-sided `p=.125`; the 100,000-draw paired task
bootstrap interval is [+5,+40] percentage points. This fresh 20-task result is
directionally and quantitatively strong, but not individually significant.

The strict overlap-authorization ablation solved 5/20. It beat Plain and Graph
by two tasks but lost two tasks to the matched structured repair. Therefore the
Java experiment supports the structured test-feedback repair system, not a
claim that a strict two-of-three overlap rule causes the gain.

## Frozen design

- Official source commit: `7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f`
- Final no-model-call freeze SHA-256:
  `b12e7d7a4904084b35cae8bca1f492d9173a46d7ee6c8dcfe8165cd3a27111c0`
- Evaluator SHA-256:
  `997e254b413c4ca248cf68162541843a9a92c0c561539649ab3fc9d681d1475c`
- Selection: 20 lowest SHA-256 ranks from all 47 official Java exercises under
  seed `mini-artichokes-aider-hidden-java20-v1-20260902`.
- Gold `.meta` material and `src/test` were absent from every model workspace.
- In a temporary private copy only, the evaluator removed Exercism's
  progressive-unlock `@Disabled` annotations so every supplied official test
  ran; test bodies and expected values were unchanged.
- The untouched starter solved 1/20 (`tree-building`). This task remained in
  every denominator and every arm.
- All calls used `gpt-5.6-luna`, medium reasoning, and one whole-batch call.
  Plain and Graph saw no tests. Both repair arms received the same Graph patch
  and the same complete 99,934-byte official failure stdout.

## Accuracy

| Arm | Correct | Accuracy | Agent seconds | Patch lines |
|---|---:|---:|---:|---:|
| Plain | 3/20 | 15% | 429.392 | 211 |
| Graph | 3/20 | 15% | 499.927 | 238 |
| Matched structured repair | **7/20** | **35%** | 549.682 | 242 |
| Strict overlap repair | 5/20 | 25% | 436.436 | 243 |

| Comparison | Rescue / harm | Difference | Exact p, one/two-sided | Bootstrap 95% CI |
|---|---:|---:|---:|---:|
| Matched repair vs Plain | 4 / 0 | +4/20 (+20 pp) | .0625 / .125 | [+5,+40] pp |
| Matched repair vs Graph | 4 / 0 | +4/20 (+20 pp) | .0625 / .125 | [+5,+40] pp |
| Strict overlap vs Plain | 2 / 0 | +2/20 (+10 pp) | .25 / .50 | [0,+25] pp |
| Strict overlap vs Graph | 2 / 0 | +2/20 (+10 pp) | .25 / .50 | [0,+25] pp |
| Strict overlap vs matched repair | 0 / 2 | -2/20 (-10 pp) | 1.0 / .50 | [-25,0] pp |

## Three-batch official coding evidence

The prior Python/Rust confirmation and Rust replication used a closely related
Graph-plus-structured-repair realization. The Java lead was strengthened
before its sample was frozen by giving both repair arms the same counterexample
and double-completion-audit operations. Thus the 60-task aggregation is a
descriptive method-family summary, not an identical-prompt replication.

| Frozen 20-task batch | Structured repair | Plain | Graph | Net vs Plain |
|---|---:|---:|---:|---:|
| Python10 + Rust10 | 13 | 8 | 5 | +5 (+25 pp) |
| Disjoint Rust20 | 9 | 6 | 6 | +3 (+15 pp) |
| Java20 | 7 | 3 | 3 | +4 (+20 pp) |
| **All 60 official tasks** | **29** | **17** | **14** | **+12 (+20 pp)** |

Across the 60 tasks, the structured-repair family had 14 rescues and 2 harms
versus Plain: task-level two-sided exact `p=.004181` and a batch-stratified
paired bootstrap 95% interval of [+8.33,+31.67] points. Versus Graph it had 15
rescues and no harms: +25 points, two-sided exact `p=6.10e-5`, bootstrap
[+15,+36.67] points. All three batch effects versus Plain were positive, but
there are only three whole-batch call clusters; the one-sided three-cluster
sign test is `p=.125`. The task-level results are conditional on those realized
sessions and are not cluster-robust population evidence.

## Interpretation

The repeated result is an end-to-end property of a two-call system: a Graph
first patch followed by a bounded, evidence-using completion repair. It is not
evidence that Graph alone helps, that strict overlap authorization helps, or
that infrastructure is a contribution. The new matched ablation instead
suggests that revisiting the original requirements, using actual failure
evidence, deriving minimal counterexamples, preserving passing work, and
performing a second completion audit are the useful components. More calls and
test feedback are real costs and must accompany the accuracy result.

Canonical machine-readable result:
`paper_revision/2026-09-01/evidence/aider_hidden_java20_results.json`, SHA-256
`d1abe2a31712c0d446bba8728118246ce2a262bc44124600de95351df75ed9e6`.

