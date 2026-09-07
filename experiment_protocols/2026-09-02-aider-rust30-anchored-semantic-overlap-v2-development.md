# Frozen development protocol: Aider Rust30 anchored TOV v2

Status: frozen before the first Rust30 model call. This protocol was written
after observing the complete Java47 TOV-v1 development result and before
observing any Rust30 model output.

## Motivation and scientific question

Java47 v1 scored Plain 7/47, Graph 7/47, ordinary repair 10/47, generic
adjudication 10/47, and semantic-overlap adjudication 11/47. TOV added one new
solution over ordinary repair but lost a task already passed by Plain during
manual patch transfer. It therefore failed its predeclared +20-point promotion
threshold.

TOV v2 separates two operations:

1. **verified-anchor preservation** deterministically installs the complete
   solution files of a candidate that passed the official task tests and
   restores those bytes after the adjudicator call;
2. **semantic-overlap repair** spends the adjudicator call only on unresolved
   tasks, comparing candidate fault location, violated invariant,
   counterexample class, and edit intent before counterexample-based repair.

The question is whether the second operation gives a large full-track gain
over Plain and a positive gain over a matched generic reviewer after both arms
receive the same verified anchors. Anchor preservation is deliberately shared
by the generic and TOV arms, so it cannot explain their difference.

## Complete benchmark and freeze

- Official source: `Aider-AI/polyglot-benchmark`, commit
  `7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f`.
- Benchmark: all 30 exercises in the official Rust track, lexicographic order.
  No exercise is selected, deleted, replaced, or topped up.
- Primary denominator: 30.
- Agent workspaces exclude `.meta` and every conventional or configured test
  file. The private evaluator restores the frozen official tests. Gold
  implementations remain absent.
- Freeze SHA-256:
  `0e53b43f5c68f48feb3f01c269de8094e480ffc653a474a0d16ff474e4207cce`.
- Public task SHA-256:
  `9984a717e82443c239396eb3b167613511051f071080f1ff7e58aa949cacc1c0`.
- Manifest SHA-256:
  `25c59bc821a93d1e39e5835e2499c6aa43643fb5b7945c4b8902b52898f42111`.
- Evaluator SHA-256:
  `f628b0ece7e504f6e35c1c85b37de4a0962beeca42035c7d48d671b7a27602dc`.
- Runner SHA-256:
  `b9336d6a8503b0c41f9303a3241b0cc039f9c387c9ca1060484e15f37cb2fb93`.

## Model and exact call plan

Every call uses `gpt-5.6-luna`, medium reasoning, web disabled, and
`CODEX_HOME=/home/pineapple/.codex-new-account`. Each call is responsible for
the complete 30-task track; there are no per-task model calls. Agent and
evaluation timeouts are each 30 minutes.

Exactly five calls are allowed, in this order:

1. **Plain**: direct hidden-test solution.
2. **Graph**: requirements/invariants/counterexamples before editing.
3. **Ordinary repair**: Graph plus its complete official failure output; the
   execution-feedback Reflexion/Self-Refine baseline.
4. **Generic verified-union adjudicator**: deterministic byte-exact union of
   tasks passed by Plain, Graph, or ordinary repair, then a strong generic
   repair of every unresolved task.
5. **TOV verified-union adjudicator**: the byte-identical verified union,
   candidate patches, outcomes, bounded failure evidence, model, effort, and
   call count, with an unresolved-task semantic-overlap/falsification ledger
   and two completion audits as the treatment.

Verified candidate selection uses the fixed priority ordinary repair, then
Graph, then Plain. Because every selected candidate passed that task's full
official test command, exact solution-file bytes are installed before either
adjudicator call. Those anchor bytes are restored after each call and before
evaluation. This is an execution-verified ensemble baseline, not gold-patch
access. Both adjudicators receive the same anchor map and cannot see one
another's output.

No result-led rerun, prompt modification, task top-up, task removal, or
candidate replacement is allowed. Every complete-track outcome remains in the
record.

## Frozen analysis and promotion gate

Report full 30-task pass vectors, rescues, harms, percentage-point differences,
paired exact tests, paired bootstrap intervals, calls, tokens, and latency.
Fixed-order development contrasts are TOV minus Plain, ordinary repair, and
matched generic verified-union adjudication.

Promote v2 unchanged to prospective evaluation on another complete official
track only if all conditions hold:

- TOV beats Plain by at least 6/30 tasks (+20.0 percentage points);
- TOV has more rescues than harms versus ordinary repair;
- TOV beats the matched generic verified-union arm by at least 2/30 tasks
  (+6.7 points), with more rescues than harms;
- every verified anchor remains byte-identical in the evaluated patch;
- the decision ledger contains exactly one entry for every unresolved task and
  all changed paths are allowed solution files.

The Rust30 result is developmental. If promoted, an unchanged v2 policy must
be tested on a different complete official track before a confirmatory paper
claim. Java47 v1 and all earlier 20-task subsets remain separate development
evidence; none is silently pooled with Rust30.

Benchmark preparation and evaluation machinery are provenance only. The paper
contribution, if supported, is the anchored Try–Semantic-Overlap–Verify
decision mechanism and its end-to-end accuracy effect.
