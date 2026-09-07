# Frozen protocol: JavaScript49 compute-budgeted recursive-TOV confirmation

Status: **frozen before every scored model call**.

## Objective and estimand

Prospectively test Mini Artichokes on the last untouched complete language
track in the pinned Aider Polyglot snapshot. The primary comparison isolates
the final heterogeneous route while matching nominal calls and hard wall-clock
caps:

- non-overlap system: shared `Plain/Graph/ordinary`, shared semantic-free
  Direct route, and Generic verified-union route;
- Mini Artichokes: identical shared calls and Direct route, with TOV replacing
  Generic;
- both outputs are the task-wise official-test verified union of Direct and
  their replaceable final route.

Each compared system therefore has exactly five whole-track calls and shares
four. No model call divides the track into task batches.

## Benchmark freeze

- Source: `Aider-AI/polyglot-benchmark`, commit
  `7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f`.
- Denominator: all 49 official JavaScript exercises in alphabetical order;
  no selection, exclusion, or outcome-led rerun.
- Agent workspace: zero `.spec.js` or `.test.js` files and no `.meta` or
  `.approaches` directory.
- Private evaluator: all 49 declared official test files.
- Starter score: 1/49.
- Node `v22.22.1`; npm `10.9.4`; Jest `29.7.0`.
- Freeze SHA-256:
  `6abd5a0ee1e4792115bec699485e99d2d39064e435d5f621a70802f0291d55ca`.
- Manifest SHA-256:
  `ceced6ab0b227a3505b77a9f89070d69a077e2bc8df609a995d65ada29072fd0`.
- Public task SHA-256:
  `00677d9332c8fd0b0bb3cfaf7ef82b9f6d1cdacfb696c14943581229dad1a7e3`.
- Dependency-lock SHA-256:
  `65e2523ccfa84fb54544c9bea286d8f86a4e052c1ed4f004f9f1be42cfff0fb3`.

## Frozen treatment and runtime

- Model: `gpt-5.6-luna`; reasoning effort: medium; verbosity: low.
- Account: `CODEX_HOME=/home/pineapple/.codex-new-account`.
- Codex CLI: `0.153.0`; web search and non-shell optional features disabled.
- Every call has the same 1,800-second hard agent timeout and the same
  1,800-second external-evaluation timeout.
- The installed CLI does not expose a validated hard sampled-token cap for
  this invocation path. Thus the study is call- and wall-clock-cap-matched,
  not realized-token-matched. Input, cached input, output, reasoning output,
  total tokens, and elapsed seconds will be reported for every call. No
  fixed-compute superiority claim is permitted if the replacement routes have
  materially unequal realized use.
- Runner SHA-256:
  `01a0a3ba5d2f64c60631916ad04ef5898a510e680b7edf24930303742b474d80`.
- Preparer SHA-256:
  `02257eaae715a1d2558e62aae7b6cffd415ac94b4e0d66dac734a78797d7d88a`.
- Evaluator SHA-256:
  `e507f600423aee13cb1d6144fde37d76ceccff678b3ff18f1da3713fd0076263`.

Exactly six new calls occur once, in this order:

1. Plain;
2. Graph;
3. ordinary execution-feedback repair from Graph;
4. semantic-free structured Direct from the verified candidate union;
5. Generic from the identical verified candidate union;
6. TOV from the identical verified candidate union.

No prompt constant, evidence-tail cap, anchor priority, route order, model,
effort, timeout, evaluator, dependency lock, or analysis rule changes after
call 1 begins.

## Isolation and deterministic promotion

Plain and Graph receive only public instructions and starter solution files.
Ordinary repair receives Graph's official per-task pass/fail and bounded
failure tails. Direct, Generic, and TOV start from the same deterministic
`ordinary > Graph > Plain` verified candidate union and receive byte-identical
candidate patches and bounded evidence artifacts. After each final call, all
verified anchor files are restored byte-for-byte before evaluation.

The final system union copies complete declared solution files only from a
route passing the complete official test suite for that task. Fixed priority
is Direct before the replaceable route when both pass; priority cannot affect
the binary pass label. There is no diff-fragment merge.

## Primary endpoint and inference

For task `t`, let `Y_M(t)` denote the Direct-union-TOV pass label and `Y_N(t)`
the Direct-union-Generic label. The primary effect is

`Delta = sum_t [Y_M(t) - Y_N(t)] / 49`.

Report scores, rescues, harms, net tasks, percentage points, exact one- and
two-sided McNemar/binomial values over discordances, and a 50,000-draw paired
task bootstrap interval with seed `20260904`. The directional superiority gate
is one-sided `p < .05`. A separately labelled strong-effect gate requires net
at least +10/49 tasks (+20.41 percentage points). Task-level inference is
conditional on these realized whole-track calls; this single track cannot by
itself justify a language-population claim.

## Secondary outcomes

Report full-denominator scores for Starter, Plain, Graph, ordinary repair,
verified candidate floor, Direct, Generic, TOV, Direct-union-Generic, and
Direct-union-TOV. Report final-route additions above the anchor floor,
TOV-vs-Generic and TOV-vs-Direct discordances, system-vs-Plain and
system-vs-ordinary effects, task IDs, and realized compute. Combine this track
with prior complete tracks only in a clearly labelled descriptive table and a
language/session-level sign analysis whose unit is the complete track.

## Integrity gate and stopping rule

All six calls must be agent-complete without retry or top-up; changed paths
must be declared solution files; evidence artifacts must match across final
routes; all anchors must be restored byte-exactly; Direct and TOV ledgers must
contain the exact unresolved set and order; every Direct semantic field must
equal `withheld-by-control`; final unions must copy only evaluator-passing
complete solution files.

Any violation is retained in intention-to-treat scoring and fails promotion.
Stop after the six calls. Do not rerun a low-scoring, timed-out, transport-null,
or directionally unfavorable call. Tooling and dependency setup are provenance,
not a paper contribution.

