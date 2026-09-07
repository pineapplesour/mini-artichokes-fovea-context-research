# Frozen protocol: HumanEvalFix Python164 recursive-TOV confirmation

Status: **frozen before every scored model call**.

## Objective

Test recursive verified redundancy on an official benchmark family distinct
from Aider Polyglot. The primary paired comparison is the same five-call
system ablation used for JavaScript49:

- non-overlap: shared `Plain/Graph/ordinary`, shared semantic-free Direct, and
  Generic verified-union route;
- Mini Artichokes: the identical shared calls and Direct route, with TOV
  replacing Generic;
- final predictions are complete-task verified unions, never fragment merges.

Both systems contain five whole-track model calls, share four calls, and use
the same fixed external verifier.

## Official benchmark and freeze

- Dataset: BigCode HumanEvalPack, commit
  `9a41762f73a8cb23bb5811b73d5aab164efcf378`.
- Variant: `humanevalfixdocs-python`; the official docstring and buggy function
  are visible, while official tests are private.
- Denominator: all 164 Python tasks in numeric task-ID order; no task
  selection, exclusion, or outcome-led rerun.
- Source parquet SHA-256:
  `ed5f15d789156e21222bfcd556c425a39042355c84ae1e8b058abd6a3d7f8075`.
- Starter score: 0/164.
- Model workspace contains no official test strings, failure labels, bug-type
  labels, failure-symptom labels, or canonical solutions.
- Evaluator packet contains only task IDs, entry points, test setup, and
  official tests; canonical solutions are absent.
- Python runtime: `Python 3.13.5`; this differs from the paper's reference
  Python 3.9.13 runtime and is reported as an explicit execution limitation.
- Freeze SHA-256:
  `07c52db96d1017657ac3161e81c9da3606929b7ce18cfea1edb0a7366f392836`.
- Manifest SHA-256:
  `be7fb0c0fab142faa2fc0c9022867f6a113676162f8f111a397f8cc971144a06`.
- Private cases SHA-256:
  `38d32a2cf88f374f991c571e563a508f7667d321458b4c8e904d96393f60001a`.
- Public task SHA-256:
  `19d29a475e830825d8eb7093132de8cf1c2f36f7a82493132549c6314ba136ce`.

## Runtime and treatment freeze

- Model/account: `gpt-5.6-luna`, medium reasoning, low verbosity,
  `CODEX_HOME=/home/pineapple/.codex-new-account`.
- Codex CLI `0.153.0`; web search and optional non-shell capabilities disabled.
- One whole-164-task call per arm; no task-wise or batch-wise model calls.
- Every call has the same 1,800-second hard agent cap and the same 1,800-second
  evaluator cap.
- The validated invocation path does not expose a hard sampled-token cap.
  The study is call- and wall-clock-cap-matched, not realized-token-matched;
  all realized token fields and seconds are mandatory outputs.
- Runner SHA-256:
  `01a0a3ba5d2f64c60631916ad04ef5898a510e680b7edf24930303742b474d80`.
- Preparer SHA-256:
  `ab79a8cc3a37f4e914a2f867b5e835e49c00365f62cf4d51a70fc6dde5efb3a6`.
- Evaluator SHA-256:
  `8d7f8ad1bf030f31210ff4044abfd2cce7f31e41be0dc33f29dc1c399f2a9d48`.

Exactly six scored calls occur once in this order: Plain, Graph, ordinary
repair from Graph feedback, semantic-free Direct, Generic verified union, and
TOV verified union. No prompt, route, anchor rule, evidence-tail cap, model,
effort, timeout, evaluator, or analysis change is allowed after Plain begins.

## Evidence and promotion

Plain and Graph receive only public docstrings and buggy implementations.
Ordinary receives Graph's task labels and bounded failure tails. Direct,
Generic, and TOV receive byte-identical Plain/Graph/ordinary patches, labels,
bounded tails, and the same deterministic `ordinary > Graph > Plain` verified
anchor seed. Every passing anchor file is restored byte-exactly after each
final call. The system union copies the complete `solution.py` from a route
that passes that task's full official test program, with Direct as fixed first
priority when both routes pass.

All six calls must exit normally with no timeout, forbidden path, retry, or
top-up. Final evidence packets must be byte-identical, every anchor must be
byte-exact, and Direct/TOV ledgers must cover the frozen unresolved ID list.
Violations remain in intention-to-treat results and fail promotion.

## Endpoints

Primary: paired full-denominator difference between `Direct union TOV` and
`Direct union Generic`. Report scores, rescues, harms, net tasks, percentage
points, exact one- and two-sided McNemar/binomial values, and a 50,000-draw
paired task bootstrap with seed `20260904`.

- directional superiority gate: one-sided `p < .05`;
- separately labelled strong-effect gate: net at least +33/164 tasks
  (+20.12 percentage points).

Secondary outcomes are every arm score, candidate-floor score, TOV versus
Generic and Direct, Mini versus Plain and ordinary, exact task IDs, actual
calls/tokens/seconds, and materialized-union re-evaluation. Task-level
inference is conditional on six whole-track calls. HumanEval familiarity and
the local Python-version difference are explicit limitations.

## Stopping rule

Stop after the six calls. Do not rerun low scores, failures, timeouts,
transport-null calls, or unfavorable directions. Dependency and evaluator
work are provenance only and are not scientific contributions.

